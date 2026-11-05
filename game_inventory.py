"""The Spirit tokens the player holds, and banking or selling what is selected."""

import math
import random
from collections import deque

import numpy as np
import pygame

import achievements
import cards
import collection
import components
import crt
import metagame
import profiles
import rolling
from rolling import *
import save_system
import sounds
import ui
from ui import Popup, ScoreParticle, TrailParticle
from components import (
    CARD_SCORERS,
    COMPONENT_PRICES,
    DEFAULT_DIFFICULTY,
    MAGNITUDE_ATAN_LIMIT,
    MAGNITUDE_MAX_STEPS,
    MAGNITUDE_SCALE,
    MAGNITUDE_STEP_DIVISOR,
    MAGNITUDES,
    MATCH_GROUPS,
    PIPE_GROUP_SHAPES,
    RESOURCE_PACK_FACTOR,
    RESOURCE_THRESHOLD,
    Action,
    Card,
    Component,
    Difficulty,
    Effect,
    MarbleType,
    Pack,
    Rarity,
    Scorer,
    Shape,
    Trial,
    block_price_for,
    card_description,
    card_price_for,
    card_scorer,
    effect_component_price,
    effect_description,
    effect_magnitude_floor,
    magnitude_precision,
    magnitude_step,
    match_group_card,
    match_group_card_meta,
    match_group_label,
    match_group_trigger,
    pack_price,
    paired_shape,
    points_text,
    resource_points_for,
    scorer_component_price,
    scorer_description,
    scorer_magnitude_floor,
    shape_description,
)
from config import *
from blocks import Block
from items import (
    CASH_BREAKDOWN,
    ActionItem,
    BlockItem,
    CardItem,
    ItemPack,
    ResourceOption,
    ScorerToken,
    CashBreakdown,
    _s,
    make_card_item,
    offer_key,
    resource_point_label,
)
from marble import Marble, _configure_marble_type
from physics import PhysicsEngine
from shop import Shop
from toolbox import Toolbox


class InventoryMixin:
    """The inventory panel's state: the page it shows, its buttons, the
    Spirit tokens it holds, and selling or upgrading a selection."""


    def _fire_token(self, token, marble):
        """Fire one Spirit token: its block, exactly as a collision would.

        The block's own scorer pays through the same path a marble's touch uses
        (so every board-relative payoff reads the token's cell), and the cards
        whose group matches the block fire with it. A Random/Lucky token's block
        already carries its reward — decided when the block was sacrificed and
        kept for every run (see _roll_kept_reward), so it repeats here rather
        than rolling afresh — and a multiplier token pays its xMult where it
        fires, exactly as the collision its block would have got (see
        _apply_xmult_now).
        """
        block = token.block
        token.fired = True
        if block.scorer in (Scorer.LUCKY, Scorer.RANDOM):
            self._run_random_result(block, block.scorer)
        self._apply_block_score_effect(marble, block)
        self._apply_cards_on_collision(block, marble)
        self._spawn_token_particle(token, block)

    def _apply_tokens(self):
        """Fire every Spirit token whose payoff belongs to the run's start.

        Each token fires as if a marble had collided with its kept block (see
        _fire_token). A token whose payoff is a MULTIPLIER is held back for the
        run's END instead — its xMult is part of what the run settles on — and
        is only ARMED here, which is also what makes the run it belongs to the
        one that spends it: a token created mid-run is never armed (see
        _apply_end_tokens).
        """
        if not self.tokens or not self.marbles:
            return
        marble = self.marbles[0]
        for token in list(self.tokens):
            # A token with nothing to fire is skipped silently (a Random/Lucky
            # token still needs its pre-rolled result, drawn when it fires).
            token.armed = False
            if token.fires_at_end:
                token.armed = True
                continue
            self._fire_token(token, marble)

    def _apply_end_tokens(self):
        """Fire the Spirit tokens whose payoff belongs to the run's END.

        Called by the run's finish path before the banked cards' xMult lands
        (see _flush_run_xmult): a multiplier token is a run-end payoff, so this
        is where its xMult — and the cards that fire with it — is paid. Only a
        token the run's start ARMED fires here, so a token created mid-run is
        left for the next run.
        """
        if not self.tokens or not self.marbles:
            return
        marble = self.marbles[0]
        for token in list(self.tokens):
            if not token.armed:
                continue
            token.armed = False
            self._fire_token(token, marble)

    def _spawn_token_particle(self, token, block):
        """Pop the token's chip as it fires (so a run start shows it working)."""
        rect = self._token_rect(self.tokens.index(token)) if token in self.tokens else None
        text = self._particle_amount_text(token.scorer_amount)
        if text in ("0", ""):
            text = token.name
        if rect is None:
            self._spawn_block_particle(block, text, Scorer.color(token.scorer))
        else:
            self._spawn_score_particle(rect.centerx, rect.centery, text,
                                       Scorer.color(token.scorer))

    def _token_rect(self, index):
        """Screen rect of the Spirit token at ``index``: the square it stands on.

        A token is part of what the player owns, so it lies on a board square
        like every other item (see Game.ensure_board_cells). None when the board
        had no room for it.
        """
        token = self.tokens[index] if 0 <= index < len(self.tokens) else None
        if token is None:
            return None
        self.ensure_board_cells()
        cell = self.item_cell(token)
        if cell is None:
            return None
        return self._board_item_rect(*cell)

    def inaccessible_rect(self, index):
        """Screen rect of one Odyssey-banked item (see INACCESSIBLE_COORDS).

        The items the Odyssey card has put away sit in their own column to the
        RIGHT of the token column, one slot each, in the order they were put
        away — the same panel language the tokens use (see ui.draw_inaccessible).
        """
        return pygame.Rect(INACCESSIBLE_COORDS[0],
                           INACCESSIBLE_COORDS[1] + index * GRID_SIZE,
                           GRID_SIZE, GRID_SIZE)

    def inaccessible_cap(self):
        """How many items Odyssey may put away at once: one per copy of it.

        The same rule every other capacity in the game follows (Hoard's holds):
        a second copy of the card banks a second item.
        """
        return self._card_count(Card.ODYSSEY)

    def can_bank_selected(self):
        """True when the selected item is one Odyssey could put away (the G key).

        A bankable item is a block or a component (never a card or an action)
        that is actually IN the inventory — a block lifted off the board is not
        in the inventory, so G has nothing to put away.
        """
        item = self.selected_toolbox_item
        if item is None or item not in self.toolbox.items:
            return False
        return getattr(item, "kind", None) in ("block", Component.SHAPE,
                                                Component.EFFECT, Component.SCORER)

    def _bank_selected_item(self):
        """Odyssey: put the selected item away for the run (the G key).

        The item leaves the inventory and waits in its own column beside the
        Spirit tokens (see Game.inaccessible_rect) until the run is over: after
        a finished, CONTINUED run it comes back into the inventory and pays
        ODYSSEY_CASH_FRACTION of its sell price in cash (see
        _return_inaccessible) — a retry is a do-over, so a banked item stays
        banked through one, exactly like every other piece of build state.
        Only Odyssey may do this, and only inaccessible_cap-many items at a time:
        one per copy of the card, the rule Hoard's holds follow. An item on its
        way out is dropped from the block being built, so that assignment can
        never point at something that is not in the inventory.
        """
        if not self._has_card(Card.ODYSSEY):
            self._set_shop_message("Only the Odyssey card can put an item away")
            return False
        if not self.can_bank_selected():
            self._set_shop_message(
                "Select a block or component in your inventory first")
            return False
        if len(self.inaccessible) >= self.inaccessible_cap():
            self._set_shop_message(
                f"Odyssey already has {len(self.inaccessible)} item(s) away "
                f"({self.inaccessible_cap()} max)")
            return False
        item = self.selected_toolbox_item
        self.toolbox.remove(item)
        # An item on its way out must not stay assigned to the next block, and
        # the assigned CELL it was tracked by is stale once it is gone.
        self.assigned_toolbox_indexes.pop(item, None)
        self.inaccessible.append(item)
        self._forget_item(item)
        self._set_shop_message(
            f"Odyssey: {self._item_name(item)} waits out this run "
            f"(${self._bank_value(item)} when it returns)")
        sounds.play_coin()
        return True

    def _bank_value(self, item):
        """The cash a banked item pays when it comes back (half its sell price)."""
        return int(self._sell_price(item) * ODYSSEY_CASH_FRACTION)

    def _return_inaccessible(self):
        """Give every Odyssey-banked item back after a run, and pay for each.

        Called once a finished run is COMMITTED (see _continue_run), so a retry
        neither returns the items nor pays — the same rule every other per-run
        gain follows. An item comes back into the inventory (which is unbounded,
        so it always fits: see Toolbox) and pays ODYSSEY_CASH_FRACTION of its
        sell price. Returns the cash paid.
        """
        if not self.inaccessible:
            return 0
        paid = 0
        for item in list(self.inaccessible):
            self.toolbox.add(item)
            self.inaccessible.remove(item)
            paid += self._bank_value(item)
        if paid:
            self.cash += paid
        self._set_shop_message(f"Odyssey returned your item(s): ${paid}")
        return paid

    def token_at(self, pos):
        """Return the token chip at a screen position, or None."""
        for i, token in enumerate(self.tokens):
            rect = self._token_rect(i)
            if rect is not None and rect.collidepoint(pos):
                return token
        return None

    def _advance_tokens(self):
        """Spend one run from each Spirit token and drop the expired ones.

        Called after a finished run. A token that did not fire this run keeps
        all of its runs (one created mid-run had nothing to fire for), and the
        scorer's own self-destruction rules apply: a Satanic token dies with
        its scorer after a single run, and a Sharp token has the same 1/4
        chance to be destroyed that a Sharp block or card has.
        """
        kept = []
        for token in self.tokens:
            if not token.fired:
                kept.append(token)
                continue
            token.fired = False
            if token.scorer == Scorer.SATANIC:
                continue  # the scorer destroys itself after a run
            if token.scorer == Scorer.SHARP and random.random() < 0.25:
                continue  # the scorer's 1/4 self-destruction rule
            if token.runs_left is not None:
                token.runs_left -= 1
                if token.runs_left <= 0:
                    continue
            kept.append(token)
        self.tokens = kept

    def _upgrade_action(self):
        """Upgrade the selected action to v2 for ACTION_UPGRADE_COST."""
        action = self.selected_action
        if action is None or action not in self.actions:
            self._set_shop_message("Select an action to upgrade")
            return
        if action.version >= 2:
            self._set_shop_message(f"{action.name} is already v2")
            return
        cost = self._inflated(ACTION_UPGRADE_COST)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to upgrade")
            return
        self.cash -= cost
        action.version = 2
        self._set_shop_message(f"{action.name} upgraded to v2 (${cost})")

    def _sell_fraction(self):
        """The fraction of an item's price a plain sale refunds.

        Half normally; the Market whole card raises it to 75%. The Death action
        has its own multipliers (1.5x / 6x) and deliberately does not read this.
        """
        return MARKET_SELL_FRACTION if self._has_card(Card.MARKET) else 0.5

    def _sell_price(self, item):
        """The cash a plain sale refunds for an item (its price x _sell_fraction)."""
        return int(item.price * self._sell_fraction())

    def _role_blocks_owned(self, scorer):
        """How many Start (or Finish) roles of a kind the player could still field.

        Counts the role blocks on the board and in the toolbox plus the
        matching role SCORER components (the same thing taken apart, and the
        only thing an assembled block can become another role block from). A
        spare role is worth one of these; the last one must never be sold,
        because the shop is not guaranteed to offer another and a run needs
        both a Start and a Finish block.
        """
        count = sum(1 for block in self.board_blocks()
                    if getattr(block, "scorer", None) == scorer)
        for item in self.toolbox.items:
            # A block standing on the board is counted above; the item it was
            # built from is that same block, so counting it here would make one
            # placed Start block look like a spare one (and let the player sell
            # the only role the game has left).
            if getattr(item, "placed_cell", None) is not None:
                continue
            role_block = getattr(item, "kind", None) == "block" and item.scorer == scorer
            role_component = item.kind == Component.SCORER and item.value == scorer
            if role_block or role_component:
                count += 1
        return count

    def _unsellable(self, item):
        """True when selling the item would take the player's LAST run role.

        Start and Finish blocks are ordinary goods now: the shop sells them
        (as plain Rect blocks, see Shop._scorer_offer), so a SPARE role can be
        sold back. The last one cannot — selling it would leave the player
        unable to start (or finish) a run, and the shop may never offer
        another. Both plain sales and the Death action refuse it, and the
        Start/Finish SCORER components are held to the same count because they
        can be assembled back into a role block.
        """
        if isinstance(item, Block) or getattr(item, "kind", None) == "block":
            scorer = getattr(item, "scorer", None)
        elif getattr(item, "kind", None) == Component.SCORER:
            scorer = item.value
        else:
            return False
        if scorer not in (Scorer.START, Scorer.FINISH):
            return False
        return self._role_blocks_owned(scorer) <= 1

    def _sell_selected_action(self):
        """Sell the selected action for a fraction of its price."""
        action = self.selected_action
        if action is None or action not in self.actions:
            self._set_shop_message("Item is not owned")
            return
        sell_price = self._sell_price(action)
        self.actions.remove(action)
        self.cash += sell_price
        self._clear_action_selection()
        self._set_shop_message(f"Sold {action.name} for ${sell_price}")