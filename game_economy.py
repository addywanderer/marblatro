"""Money and resources: the shelf's rerolls and held cells, the resource points
the Shreds/Rubble/Ideas/Picky scorers bank, and the rewards those points buy."""

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


class EconomyMixin:
    """Money and resources: the shelf's rerolls and held cells, the
    resource points the scorers bank, and the rewards they buy."""


    def _info_target_at(self, pos):
        """Return (item, source) at a position for the info sidebar, or (None, None).

        The info sidebar is shown for shop items, toolbox items, cards, blocks
        that are already placed in the marble box, and the shop's "Last run
        cash gained" readout (which breaks the run's earnings down).
        """
        # An OPEN PACK owns the hover as well as the clicks: its options are
        # what the player is looking at, so the sidebar reads out the option
        # under the cursor (see _click_pack and ui.draw_pack_overlay).
        index = self.pack_option_at(pos)
        if index is not None and index < len(self.open_pack.options):
            return self.open_pack.options[index], "pack"
        # The cash readout is not an item, so it is checked first: hovering it
        # shows where the last run's dollars came from.
        if ui.last_run_cash_rect(self).collidepoint(pos):
            return CASH_BREAKDOWN, "cash"
        item = self.shop.item_at(pos)
        if item is not None:
            return item, "shop"
        # Every owned item stands on the board (see Game.ensure_board_cells), so
        # one lookup finds a block, a component, a card or an action alike.
        board_item = self.board_item_at(pos)
        if board_item is not None:
            return board_item, "board"
        token = self.token_at(pos)
        if token is not None:
            return token, "tokens"
        return None, None

    def _v2_shelf_note(self):
        """Name any already-upgraded action a fresh shop has just shelved.

        Every action the shop offers is rolled for its version (see
        random_action_version), so roughly one in a hundred actions arrives
        already upgraded — a straight saving of ACTION_UPGRADE_COST, and easy to
        miss among the shop's other tiles. The shelf tile itself is gold-framed
        and tagged (see ui.draw_action), and this appends the name to the reroll
        message so a player who does not read the shelves is still told.
        """
        upgraded = [i for i in self.shop.items
                    if getattr(i, "kind", None) == "action"
                    and getattr(i, "version", 1) >= 2]
        if not upgraded:
            return ""
        names = ", ".join(self._item_name(i) for i in upgraded)
        return (f" — {names} already upgraded "
                f"(a free ${self._inflated(ACTION_UPGRADE_COST)})")

    def _clip_shop_locks(self):
        """Release held shop offers past what the player can hold right now.

        The cap is the Hoard card count, so it falls when a Hoard is sold or
        cut by the Card cutter; the offer pinned LAST gives way first, so what
        the player pinned first is what stays held.
        """
        cap = self.shop_lock_cap()
        if len(self.shop.locked) > cap:
            del self.shop.locked[cap:]

    def _toggle_shop_lock(self, pos):
        """Hoard: hold (or release) the shop offer under the mouse.

        Returns True when the click was this card's business — the offer is now
        held, or released, or the player is told why it cannot be. Middle-click
        is this card's alone (user request: right-click BUYS an offer now), so
        nothing falls through to the board; a middle-click on an EMPTY square
        simply does nothing.
        """
        item = self.shop.item_at(pos)
        if item is None:
            return False
        self._clip_shop_locks()
        slot = self.shop.slot_key(item)
        if slot in self.shop.locked:
            self.shop.locked.remove(slot)
            self._set_shop_message(
                f"Released {item.name} — the next refresh may change it")
            return True
        cap = self.shop_lock_cap()
        if cap <= 0:
            self._set_shop_message(
                "Hoard holds a shop offer in place through a refresh — "
                "you do not own it")
            return True
        if len(self.shop.locked) >= cap:
            self._set_shop_message(
                f"Hoard is already holding {cap} offer"
                f"{'' if cap == 1 else 's'} — release one first")
            return True
        self.shop.locked.append(slot)
        self._set_shop_message(
            f"Holding {item.name} ({len(self.shop.locked)}/{cap}) — it stays "
            "on the board through the next refresh")
        sounds.play_mech()
        return True

    def _refresh_shop(self):
        """Reroll the shop — free while a Fresh reroll is banked, else for cash."""
        if self.free_rerolls > 0:
            self.free_rerolls -= 1
            self.shop.refresh()
            self._trim_shop_for_trial()
            left = f" ({self.free_rerolls} left)" if self.free_rerolls else ""
            self._set_shop_message(f"Free reroll{left}{self._tesseract_reroll_note()}"
                                   f"{self._v2_shelf_note()}")
            return
        cost = self.refresh_cost()
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to refresh the shop")
            return
        self.cash -= cost
        self.shop.refresh()
        self._trim_shop_for_trial()
        self._set_shop_message(f"Refreshed shop (${cost})"
                               f"{self._tesseract_reroll_note()}"
                               f"{self._v2_shelf_note()}")

    def refresh_cost(self):
        """The cash a shop reroll costs right now.

        The inflation trial inflates it (see _inflated) and Brainstorm's v2
        halves it (see reroll_discount), rounded to the nearer dollar and never
        below $1. The shop's REFRESH button reads this too, so the price on the
        button and the price charged can never drift apart.
        """
        cost = self._inflated(SHOP_REFRESH_COST) * self.reroll_discount
        return max(1, int(cost + 0.5))

    def _tesseract_reroll_note(self):
        """Grow the Tesseract bonus for this reroll; a note for the message.

        Called on every shop reroll (paid or free): while the Tesseract whole
        card is owned, its permanent xMult bonus grows by
        TESSERACT_REROLL_XMULT and the reroll message reports the new total so
        the growth is visible while the player rerolls.
        """
        if not self._has_card(Card.TESSERACT):
            return ""
        self.tesseract_bonus += TESSERACT_REROLL_XMULT
        return f" — Tesseract x{self.tesseract_bonus:.1f}"

    def _trim_shop_for_trial(self):
        """Slim pickings: remove two random shop options for this run.

        Called wherever a shop and the run's trial meet: after every shop
        refresh (so each rerolled shop is two options lighter), when a run
        advances onto the fresh shop built for it (see _continue_run), when a
        trial is bought onto the shop already on screen (see
        _click_trial_display), and once at game start — the game's opening shop
        is built before that first run's trial is drawn, so an opening Slim
        pickings run has to shed its options here too (see reset_game). Any
        other trial (and trials switched off) leaves the shop alone, so all of
        those places can simply call this.
        """
        if self.active_trial != Trial.SLIM_PICKINGS:
            return
        # A held offer is left alone: Hoard's whole promise is that the offer it
        # holds stays put, and this trim runs right after every reroll — the
        # exact moment a held offer would otherwise vanish.
        free = [item for item in self.shop.items
                if self.shop.slot_key(item) not in self.shop.locked]
        if len(free) > 2:
            for item in random.sample(free, 2):
                self.shop.items.remove(item)

    def _add_resource_points(self, scorer, amount=1):
        """Bank resource points for a Shreds/Rubble/Ideas/Picky scorer.

        A trigger banks a FRACTION of a point (1/3 for Shreds, 1/2 for the
        others at the average magnitude — see components.resource_points_for),
        because one whole point is what a reward costs. Points earned during a
        run are held in this run's gain counters. They only move into the
        permanent bank — and convert into rewards — after a run (see
        _commit_resource_points); RETRYING a run resets the pending gain and the
        bank alike (see _retry_run). (Parts banks components separately — they
        are granted when the run is continued, see _continue_run — and Fresh
        grants its reroll immediately, so neither is handled here.)
        """
        if scorer == Scorer.SHREDS:
            self.shred_run_gain += amount * self.resource_point_multiplier()
        elif scorer == Scorer.RUBBLE:
            self.rubble_run_gain += amount * self.resource_point_multiplier()
        elif scorer == Scorer.IDEAS:
            self.idea_run_gain += amount * self.resource_point_multiplier()
        elif scorer == Scorer.PICKY:
            self.option_run_gain += amount * self.resource_point_multiplier()

    def _grant_inventory_slots(self, count):
        """Unlock ``count`` board squares (the Packed scorer's payoff).

        The inventory is the board now (user request: everything the player owns
        lies on board squares), so "more room" means more board: the squares come
        off the locked frontier the way a Board Unit does (see
        _grant_locked_units). What THIS run granted is counted separately, so a
        retry takes back only the squares the discarded run won (see reset_run /
        _retry_run), exactly as Fresh's free rerolls work.
        """
        granted = self._grant_locked_units(count, announce=False)
        self.inventory_slots_won += granted
        self.inventory_slots_run_gain += granted
        plural = "" if granted == 1 else "s"
        self._set_shop_message(
            f"Room for {granted} more item{plural} "
            f"({len(self.unlocked_cells)} squares unlocked)")
        sounds.play_coin()
        return granted

    def resource_point_multiplier(self):
        """How much a banked resource point is worth right now.

        The product of Mass production's two bonuses: the factor bought for
        THIS RUN (v1, spent when the run's points are committed) and the
        permanent one (v2). Neither is applied to anything else — the points
        are what their scorers bank, multiplied here (see _add_resource_points).
        """
        return self.resource_gain_mult * self.resource_gain_bonus

    def _commit_resource_points(self):
        """Move this run's resource points into the bank and convert them.

        Called after a finished run. The run's points join the permanent bank,
        then every whole point converts into that scorer's reward (Shreds ->
        card, Rubble -> block, Ideas -> action, Picky -> shop slot). A trigger
        banks a fraction of a point, so the leftover below a point stays banked
        for a future run; if a grant is refused (a full area), its point stays
        banked too.
        """
        self.shred_points += self.shred_run_gain
        self.shred_run_gain = 0
        # Mass production's run factor belongs to the run that just finished:
        # the points it tripled have been folded in above (and the permanent
        # factor, if any, stays).
        self.resource_gain_mult = 1.0
        self.rubble_points += self.rubble_run_gain
        self.rubble_run_gain = 0
        self.idea_points += self.idea_run_gain
        self.idea_run_gain = 0
        self.option_points += self.option_run_gain
        self.option_run_gain = 0
        self._convert_banked_points()

    def _convert_banked_points(self):
        """Spend every whole banked point on its scorer's reward.

        The one conversion loop, run both when a run's points are committed and
        when a resource PACK banks points mid-run (see _grant_resource_points),
        so a pack's points buy exactly what a trigger's points buy. Shreds pay
        a card, Rubble a block, Ideas an action and Picky a permanent shop slot
        (each slot shows an extra random offer on every refresh); a refused
        grant leaves its points banked for next time.
        """
        cost = self._resource_cost()
        while self.shred_points >= cost and self._grant_random_card():
            self.shred_points -= cost
        while self.rubble_points >= cost and self._grant_random_block():
            self.rubble_points -= cost
        while self.idea_points >= cost and self._grant_random_action():
            self.idea_points -= cost
        while self.option_points >= cost:
            self.option_points -= cost
            self.bonus_slots += 1
        self.shop.bonus_slots = self.bonus_slots

    def _grant_resource_points(self, scorer, points):
        """Bank resource points straight away, and convert what they buy.

        What a resource PACK's option does (see ItemPack): the points go into
        the PERMANENT bank — not this run's pending gains — and are converted at
        once, so keeping the option has its effect on the spot rather than at
        the end of the run. The four banks are the ones the scorers fill (see
        _add_resource_points), and the conversion is the same loop a finished
        run uses (see _convert_banked_points).
        """
        if scorer == Scorer.SHREDS:
            self.shred_points += points
        elif scorer == Scorer.RUBBLE:
            self.rubble_points += points
        elif scorer == Scorer.IDEAS:
            self.idea_points += points
        elif scorer == Scorer.PICKY:
            self.option_points += points
        else:
            return
        self._convert_banked_points()

    def _resource_cost(self):
        """Points needed for one resource conversion, after the Factory card.

        Always ONE point, which is exactly what a trigger banks a fraction of.
        Factory ("resource conversions halve") needs half a point instead — a
        real half, since points are fractional now, so a 1/2-point Rubble
        trigger converts on its own.
        """
        if not self._has_card(Card.FACTORY):
            return RESOURCE_THRESHOLD
        return RESOURCE_THRESHOLD / 2

    def _grant_random_component(self):
        """Grant a random shape/effect/scorer component to the toolbox."""
        kind = random.choice([Component.SHAPE, Component.EFFECT, Component.SCORER])
        if kind == Component.SHAPE:
            value = random.choice(Shape.ORDER)
            item = Component.shape_component(value)
        elif kind == Component.EFFECT:
            value = random.choice(Effect.ORDER)
            item = Component.effect_component(value, magnitude=roll_effect_magnitude(value))
        else:
            # Run roles are never handed out as components — the shop sells
            # them as ready-made Rect blocks, and Parts keeps to that rule.
            pool = [s for s in Scorer.SHOP_ORDER if s not in (Scorer.START, Scorer.FINISH)]
            value = random.choice(pool)
            item = Component.scorer_component(value, amount=roll_scorer_amount(value))
        self.toolbox.add(item)
        self._set_shop_message(f"Converted a component: {item.name}")
        sounds.play_coin()
        return True

    def _grant_random_card(self):
        """Grant a random card to the card area (see _draw_random_card_value)."""
        value = self._draw_random_card_value()
        if value is None:
            self._set_shop_message(f"You can only hold {self.max_cards} cards — card withheld")
            return False
        self._adopt_card(make_card_item(value))
        self._discover_owned_card(value)
        self._set_shop_message(f"Converted a card: {Card.name(value)}")
        sounds.play_coin()
        return True

    def _draw_random_card_value(self):
        """A random card value for a grant, or None when none can be drawn.

        Like the shop's card slots, the draw skips the cards the player already
        owns (see Shop.owned_cards): a second copy is the Showman card's perk,
        so without it this hands over a card the player can actually use. If
        every candidate is somehow owned already, the plain pool is used — a
        grant is always delivered while the area has a free slot.
        """
        if len(self.cards) >= self.max_cards:
            return None
        owned = self.shop.owned_cards()
        pool = [v for v in rolling.prebuilt_card_pool()
                if v != Card.ERR_404 and v not in owned
                and len(self.cards) < self._card_capacity_for(v)]
        if not pool:
            pool = [v for v in rolling.prebuilt_card_pool()
                    if v != Card.ERR_404 and len(self.cards) < self._card_capacity_for(v)]
        if not pool:
            return None
        return random.choice(pool)

    def _grant_random_block(self):
        """Grant a random block (like a shop block) to the toolbox."""
        shape = random.choice(Shape.ORDER)
        count = random_effect_count()
        effects = random.sample(Effect.REAL_ORDER, count)
        scorer = random.choice(Scorer.SHOP_ORDER)
        shape, effects = role_block_parts(scorer, shape, effects)
        amount = roll_scorer_amount(scorer)
        amounts = roll_effect_amounts(effects)
        name = role_block_name(scorer, shape)
        item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount,
                         block_price_for(shape, effects, scorer), name,
                         effects=effects, effect_amounts=amounts)
        self.toolbox.add(item)
        self._discover_block(item)
        self._set_shop_message(f"Converted a block: {name}")
        sounds.play_coin()
        return True

    def _grant_random_action(self):
        """Grant a random action to the action area."""
        if len(self.actions) >= self.max_actions:
            self._set_shop_message(f"You can only hold {self.max_actions} actions — action withheld")
            return False
        value = random.choice(Action.ORDER)
        item = ActionItem(value, Action.PRICES.get(value, 60),
                          version=rolling.random_action_version())
        self._adopt_action(item)
        self._discover_action(value)
        self._set_shop_message(f"Converted an action: {self._item_name(item)}")
        sounds.play_coin()
        return True

    def _resource_owned(self, scorer):
        """True when the player owns the given resource scorer as a component,
        inside a block (in the toolbox or the marble box), or as the scorer
        half of an owned card."""
        for item in self.toolbox.items:
            if item.kind == Component.SCORER and item.value == scorer:
                return True
            if getattr(item, "kind", None) == "block" and item.scorer == scorer:
                return True
        if any(block.scorer == scorer for block in self.board_blocks()):
            return True
        for card in self.cards:
            # A match-group card counts when its scorer is the one asked about:
            # the card pays that scorer, so the player owns it.
            if card_scorer(card.value) == scorer:
                return True
        return False

    def _resource_display(self):
        """Lines to show under cash: (points_to_next, reward label) for each
        owned point-banked resource scorer (Shreds/Rubble/Ideas/Picky).
        Parts banks whole components rather than points — they are granted when
        the run is continued (see _continue_run) — and Fresh grants its reroll
        immediately, so neither shows a points line."""
        lines = []
        specs = [
            (Scorer.SHREDS, self.shred_points, self.shred_run_gain, "card"),
            (Scorer.RUBBLE, self.rubble_points, self.rubble_run_gain, "block"),
            (Scorer.IDEAS, self.idea_points, self.idea_run_gain, "action"),
            (Scorer.PICKY, self.option_points, self.option_run_gain, "slot"),
        ]
        threshold = self._resource_cost()
        for scorer, bank, run_gain, label in specs:
            if self._resource_owned(scorer):
                # This run's pending points count toward the next conversion
                # (the reward itself is granted after a run).
                total = bank + run_gain
                to_next = threshold - (total % threshold)
                lines.append((to_next, label))
        return lines

    def _block_parts(self, block):
        """The shape, effect(s), and scorer components that make up a block.

        Each piece keeps the magnitude the block was built with (its own rolled
        strength), so disassembling a block hands back the same goods it was
        made from rather than a set of average-strength parts.
        """
        parts = [Component.shape_component(block.shape),
                 Component.scorer_component(block.scorer, amount=block.scorer_amount)]
        for e in block.effects:
            parts.append(Component.effect_component(
                e, magnitude=block.effect_magnitude(e)))
        return parts

    # -----------------------------------------------------------------------
    # COMMENTED OUT with the conditions (user request: "comment out all the code
    # for conditions"): splitting a card back into its two halves. A card was a
    # condition + a scorer, so it could be taken apart for CARD_DISASSEMBLE_COST;
    # every card is whole and unsplittable now.
    #
    # def _disassemble_card(self):
    #     """Split a selected splittable card back into its halves (for a fee).
    #
    #     The card is removed from the card area and its condition + scorer
    #     components go into the toolbox. Whole cards (ERR 404 / Blueprint /
    #     Showman) cannot be split.
    #     """
    #     item = self.selected_toolbox_item
    #     if item is None or getattr(item, "kind", None) != "card":
    #         self._set_shop_message("Select a splittable card to disassemble")
    #         return
    #     if item not in self.cards:
    #         self._set_shop_message("Item is not owned")
    #         return
    #     parts = splittable_card_condition_scorer(item.value)
    #     if parts is None:
    #         self._set_shop_message("This card cannot be split")
    #         return
    #     cost = self._inflated(CARD_DISASSEMBLE_COST)
    #     if self.cash < cost:
    #         self._set_shop_message(f"Need ${cost} to disassemble")
    #         return
    #     if len(self.toolbox.items) + 2 > self.toolbox.cols * self.toolbox.rows:
    #         self._set_shop_message("Inventory needs room for the halves")
    #         return
    #     condition, scorer = parts
    #     self.cards.remove(item)
    #     self.cash -= cost
    #     self.toolbox.add(Component.condition_component(condition))
    #     # The scorer half comes back at the magnitude the card carried, so a
    #     # card and its halves are always worth the same.
    #     amount = getattr(item, "amount", 0) or Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    #     self.toolbox.add(Component.scorer_component(scorer, amount=amount))
    #     self._clear_toolbox_selection()
    #     self._set_shop_message(f"Disassembled {item.name} (${cost})")
    #     sounds.play_mech()

    def _disassemble_block(self):
        """Break the selected block back into its parts (for a fee).

        Works on a toolbox block or a block placed in the marble box (the F key).
        """
        item = self.selected_toolbox_item
        if item is None or not isinstance(item, (Block, BlockItem)):
            self._set_shop_message("Select a block to disassemble")
            return
        cost = self._inflated(DISASSEMBLE_COST)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to disassemble")
            return
        parts = self._block_parts(item)
        in_toolbox = item in self.toolbox.items
        # Remove the block (from the grid if it was placed, else the toolbox).
        if isinstance(item, Block):
            self.grid.pop((item.x, item.y), None)
            if item.scorer == Scorer.START:
                self.marbles = [m for m in self.marbles if getattr(m, "start_block", None) is not item]
            # The block is parts now, so the item it was built from is gone too
            # (see _release_block_item) — a block and its item are one existence.
            self._forget_item(item)
            self._release_block_item(item)
        elif in_toolbox:
            self.toolbox.remove(item)
        self.cash -= cost
        for part in parts:
            self.toolbox.add(part)
        name = self._item_name(item)
        # A pairing block can't exist without its partner: disassembling one also
        # deletes the matching portal / the other half of its key/lock pair.
        self._delete_pairing_partners(item)
        # The block is parts now, so its own switch goes off; every other item
        # keeps the state the player left it in.
        self._forget_item(item)
        self._set_shop_message(f"Disassembled {name} (${cost})")
        sounds.play_mech()

    def _delete_pairing_partners(self, item):
        """Delete the blocks that pair with a removed block.

        A Portal block and a Key/Lock block are useless without their other
        half, so removing one block (by disassembling it, selling it, or
        selling it with an action) removes its partner too — the block sharing
        its portal or key number, in the toolbox or on the grid.
        """
        if item.has_effect(Effect.PORTAL) and getattr(item, "portal_number", 0):
            self._delete_paired_portal(item.portal_number)
        if getattr(item, "key_number", 0):
            self._delete_paired_key(item.key_number)

    def _delete_paired_key(self, number):
        """Delete every Key/Lock block paired with the given key number.

        A Key and its Lock always come as a pair (two blocks with the same key
        number). Removing one half deletes the other so a lone, unusable half
        never lingers. Recognition can leave MORE than two blocks sharing a
        number (two keys for one door), so every block that shares it goes —
        removing only the first would leave a half with nothing to pair with
        (user report: glitches with several copies of one item).

        The paired blocks live either in the toolbox or, if placed, on the grid.
        """
        if not number:
            return
        # Every owned item is a candidate, not just the ones the panel shows:
        # the inventory is unbounded (see Toolbox), so the partner may be
        # stashed — or placed, in which case its item is still in the inventory
        # and removing it takes the block with it (see _drop_placed_copy).
        for item in list(self.toolbox.every_item()):
            if getattr(item, "key_number", 0) == number:
                self.toolbox.remove(item)
                self.assigned_toolbox_indexes.pop(item, None)
                # The partner is gone, so its switch goes off with it: a
                # selection that outlived the item would be a ghost the player
                # could still act on (see _forget_item).
                self._forget_item(item)
        for key, block in list(self.grid.items()):
            if getattr(block, "key_number", 0) == number:
                self.grid.pop(key, None)
                if block.scorer == Scorer.START:
                    self.marbles = [m for m in self.marbles
                                    if getattr(m, "start_block", None) is not block]
                self._forget_item(block)
                self._release_block_item(block)

    def _delete_paired_portal(self, number):
        """Delete every portal block paired with the given pairing number.

        Portals come in pairs (two blocks with the same number). Removing one
        portal (via disassembly) deletes the rest so a lone, unusable portal
        never lingers — every block sharing the number, because Recognition can
        leave more than two of them (see _delete_paired_key). The paired blocks
        live either in the toolbox or, if placed, on the grid.
        """
        if not number:
            return
        # The whole inventory, not just the panel: the partner may be stashed,
        # or placed (its item is still owned — see _place_block_at).
        for item in list(self.toolbox.every_item()):
            if getattr(item, "portal_number", 0) == number:
                self.toolbox.remove(item)
                self.assigned_toolbox_indexes.pop(item, None)
                # Its partner is gone, so the item's switch goes off with it.
                self._forget_item(item)
        for key, block in list(self.grid.items()):
            if getattr(block, "portal_number", 0) == number:
                self.grid.pop(key, None)
                if block.scorer == Scorer.START:
                    self.marbles = [m for m in self.marbles if getattr(m, "start_block", None) is not block]
                self._forget_item(block)
                self._release_block_item(block)

    def _sell_selected_item(self):
        """Sell the selected item (block, component, card, or action) for half its price."""
        # A selected action is sold first (actions are selected independently).
        if self.selected_action is not None:
            self._sell_selected_action()
            return
        item = self.selected_toolbox_item
        if item is None:
            return
        # A spare Start/Finish block is a normal good; the LAST one is not (see
        # _unsellable).
        if self._unsellable(item):
            self._set_shop_message("Your last Start or Finish block can't be sold")
            return
        # A card sells for a fraction of its original price. Cards live in the
        # card area (not the toolbox), so they are handled separately here.
        if getattr(item, "kind", None) == "card":
            if item not in self.cards:
                self._set_shop_message("Item is not owned")
                return
            sell_price = self._sell_price(item)
            self.cards.remove(item)
            self.cash += sell_price
            self._forget_item(item)
            self._set_shop_message(self._card_sold_message(
                item, f"Sold {item.name} for ${sell_price}"))
            return
        if item not in self.toolbox.items:
            self._set_shop_message("Item is not in the inventory")
            return
        # Resale value includes any cash paid to raise the trigger limit.
        sell_price = self._sell_price(item) + getattr(item, "trigger_paid", 0)
        self.toolbox.remove(item)
        # COMMENTED OUT with the conditions: selling an assigned condition or
        # scorer used to cancel the pending card build.
        #
        # if item is self.card_condition or item is self.card_scorer:
        #     self.card_condition = None
        #     self.card_scorer = None
        #     self.card_builder_indexes.clear()
        # If the sold component was assigned to the next block, unassign it:
        # the cell it was tracked by is stale once the piece is gone.
        self.assigned_toolbox_indexes.pop(item, None)
        # A pairing block can't exist without its partner: selling one also
        # deletes the matching portal / the other half of its key/lock pair.
        if getattr(item, "kind", None) == "block":
            self._delete_pairing_partners(item)
        self.cash += sell_price
        # The sold item is gone, so its switch goes off — and only its own.
        self._forget_item(item)
        self._set_shop_message(f"Sold {item.name} for ${sell_price}")
