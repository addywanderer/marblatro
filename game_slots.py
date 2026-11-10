"""What the player owns and how it is shown: the cards, the actions, the slots
they take and the trigger limits a card can raise."""

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
    Modifier,
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
    Quality,
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
    ENERGY_READOUT,
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


class SlotsMixin:
    """What the player owns and how it is shown: the cards, the actions,
    the slots they take and the trigger limits a card can raise."""


    @property
    def active_trial(self):
        """The trial this run is really playing, or None.

        ``current_trial`` holds an id even when the trial system is switched
        off for the game (the id is drawn when the run is set up), so everything
        that APPLIES a trial — its rolled picks, the marble flags, the panels
        and the tiled background — reads this instead: with trials disabled no
        trial is in effect, whatever id the game happens to be holding.
        """
        return self.current_trial if self.trials_enabled else None

    @property
    def tile_source(self):
        """(class, id) of the tile art the screen and panels wear this run.

        The run's trial, or (None, None) when the run has none — a trial-free
        run, or one whose trial was bought away. The screen, the panels and the
        trial's collection entry all wear the same tile (see ui).
        """
        if self.active_trial is not None:
            return (Trial, self.active_trial)
        return (None, None)

    def _concert_boosts(self, item):
        """True when the Concert whole card's extra trigger applies to a block.

        Concert only helps a block with something worth repeating: a real shape
        (not a plain Rect), a real effect, and a scorer to pay out. A block that
        fails any of the three is left alone, so the run roles (rects), the bare
        Key/Lock shapes (no effect) and a portal or plain chute (no scorer) all
        keep the trigger count they have.
        """
        return (self._has_card(Card.CONCERT)
                and getattr(item, "shape", Shape.RECT) != Shape.RECT
                and getattr(item, "scorer", Scorer.NONE) != Scorer.NONE
                and any(effect != Effect.NONE
                        for effect in getattr(item, "effects", None) or ()))

    def _trigger_limit(self, item):
        """How many times a block scores in one run, trial and Concert included.

        The block's OWN limit — paid upgrades and Deja Vu included — plus the
        Concert whole card's bonus while it is owned and not cut by the Card
        cutter trial, or MINUS the Hands tied trial's penalty
        (TRIAL_TRIGGER_PENALTY, floored at 0) for the blocks that trial debuffed.
        The penalty REPLACES the Concert bonus rather than stacking with it, so
        a debuffed block is never handed an extra trigger by Concert: a 1-limit
        block that Hands tied picks is still silenced under both.

        This is the number to HAND OUT triggers from (a fresh run's refill, a
        Procrastination rewind, and a FRESH block being placed) — a block that
        is only moved or put back down keeps the triggers it has left instead
        (see _place_block_at) — and what the info box reports. Charge rules like
        the trial penalty and the Concert bonus are derived rather than written
        onto the block, so selling Concert, cutting it, or re-rolling the
        trial's choices takes them away again instead of leaving a changed limit
        behind on every block. Triggers already handed out are not taken back —
        a limit only bites when triggers are dealt.
        """
        limit = getattr(item, "trigger_limit", 1)
        if item in self.trial_debuffed_blocks:
            return max(0, limit - TRIAL_TRIGGER_PENALTY)
        bonus = CONCERT_TRIGGER_BONUS if self._concert_boosts(item) else 0
        return limit + bonus

    def _trigger_upgrade_cost(self, item):
        """Cash to raise a block's trigger limit by one.

        The upgrade is priced off the block's SCORER: it costs
        TRIGGER_UPGRADE_MARKUP (10%) more than buying that scorer component from
        the shop right now, so it follows the scorer's duplicate-price rise, the
        Coupon discount and the inflation trial exactly as that purchase would.
        Upgrading also COUNTS as a purchase of the scorer (see
        _upgrade_trigger_limit), so the next upgrade — and the scorer's shop
        price — climb by the usual duplicate-price step.
        """
        component = Component.scorer_component(
            getattr(item, "scorer", Scorer.NONE),
            amount=getattr(item, "scorer_amount", 0))
        return int(self._buy_price(component) * TRIGGER_UPGRADE_MARKUP)

    def _sync_portal_pair_limits(self, item):
        """Give every portal partner the same (upgraded) trigger limit.

        Portal pairs share a trigger count, so their limits must stay in step;
        the upgrade is charged once on the selected portal. Recognition can leave
        more than two portals sharing a number, so every partner is raised, not
        just the first one found (see Game._delete_paired_portal).
        """
        if not getattr(item, "has_effect", lambda e: False)(Effect.PORTAL):
            return
        number = getattr(item, "portal_number", 0)
        if not number:
            return
        for other in list(self.toolbox.items) + self.board_blocks():
            if other is not item and getattr(other, "portal_number", 0) == number:
                other.trigger_limit = item.trigger_limit

    def _upgrade_trigger_limit(self):
        """Pay cash to raise the selected block's trigger limit by one.

        The cost grows with the current limit and with the block's total cost.
        The cash paid is tracked on the block and refunded when it is sold.
        """
        item = self.selected_toolbox_item
        if item is None or not isinstance(item, (Block, BlockItem)):
            self._set_shop_message("Select a block to upgrade")
            return
        if self.is_shop_offer(item):
            # An offer is not the player's block yet: upgrading it would spend
            # cash on something the shelf still owns (see _buy_shop_item).
            self._set_shop_message(
                f"{self._item_name(item)} is not yours yet — right-click to buy it")
            return
        cost = self._trigger_upgrade_cost(item)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to upgrade the trigger")
            return
        self.cash -= cost
        item.trigger_limit += 1
        item.trigger_paid += cost
        # The upgrade counts as one purchase of the block's scorer, so that
        # scorer's shop price (and therefore the next upgrade) climbs by the
        # same duplicate-price step a real purchase causes.
        self._record_component_purchases(
            Component.scorer_component(item.scorer,
                                       amount=getattr(item, "scorer_amount", 0)))
        self._sync_portal_pair_limits(item)
        self._set_shop_message(f"Trigger limit now {self._trigger_limit(item)} (${cost})")

    def _item_name(self, item):
        """A display name for a shop/toolbox item or a placed block.

        Blocks are named by their parts: every real effect, then the shape,
        then the scorer, then "v<trigger limit>" — e.g. a slippery, fragile
        pipe that grants +chips twice per run reads "Slippery Fragile Pipe
        +Chips v2". An upgraded (v2) action carries its version the same way,
        so "Death v2" is what every message about it calls it; a plain v1
        action stays just "Death". The trigger count shown is the block's
        EFFECTIVE one (see _trigger_limit), so a Concert-boosted block reads one
        higher than its own printed limit while the card is owned.

        An item a golem has combined says so in its name (see Quality): "Golden
        Lantern", "Diamond Golden Pipe +Chips v2" — the tier is part of what the
        item IS, so every message about it says it.
        """
        if item is CASH_BREAKDOWN:
            return "Last run cash gained"
        if item is ENERGY_READOUT:
            return "Energy"
        if getattr(item, "kind", None) == "pack":
            # A pack is named for its size AND its type: "Jumbo Shape Pack" is
            # exactly what it holds (see ItemPack.name).
            return item.name
        if getattr(item, "kind", None) == "resource":
            return f"{item.name} ({Scorer.name(item.scorer)})"
        tier = Quality.title(item)
        if isinstance(item, Block) or getattr(item, "kind", None) == "block":
            effects = " ".join(Effect.name(e) for e in item.effects if e != Effect.NONE)
            parts = ([effects, Shape.name(item.shape), Scorer.name(item.scorer)] if effects
                     else [Shape.name(item.shape), Scorer.name(item.scorer)])
            limit = self._trigger_limit(item)
            return f"{tier}{' '.join(parts)} v{limit}"
        name = getattr(item, "name", "")
        if getattr(item, "kind", None) == "action" and name:
            version = getattr(item, "version", 1)
            return f"{tier}{name} v{version}" if version >= 2 else f"{tier}{name}"
        if name:
            return f"{tier}{name}"
        return f"{tier}{Shape.name(item.shape)} {Scorer.name(item.scorer)}"

    def board_item_at(self, pos):
        """The item standing on the board at a screen position, or None.

        Every owned item is laid out on a board square (see
        Game.ensure_board_cells), so this is how the mouse finds a card, an action,
        a component or a block: the square under the pointer holds it.
        """
        gx, gy = self.screen_to_cell(pos)
        return self.item_at_cell((gx, gy))

    def _card_disabled(self, card):
        """True when a card is disabled for this run.

        The Card cutter trial disables one random owned card (see _apply_trial).
        A disabled card is treated as if it were not owned at all, so its
        collision effect (cards.py) and every passive card effect it drives
        (_has_card) stop for the run. The state is cleared when the run advances
        (see _continue_run), so building, buying and selling between runs are
        never affected.
        """
        if card is None:
            return False
        return Modifier.has(card, Modifier.DISABLED)

    @property
    def disabled_card(self):
        """The card the Card-cutter trial has silenced for this run.

        It is kept as the card's own DISABLED modifier (see components.Modifier):
        assigning it marks the card and unmarks the one before, so every reader
        -- the trial, the sidebar, the save file and the tests -- still talks
        about "the disabled card" while there is only one place the state lives.
        """
        return self._disabled_card

    @disabled_card.setter
    def disabled_card(self, card):
        previous = getattr(self, "_disabled_card", None)
        if previous is not None and previous is not card:
            Modifier.set_stacks(previous, Modifier.DISABLED, 0)
        self._disabled_card = card
        if card is not None:
            Modifier.set_stacks(card, Modifier.DISABLED, 1)

    def _owns_card(self, value):
        """True when the player owns a card of this value, disabled or not.

        Ownership is what the duplicate rules care about (you may not own two
        of the same card), so this deliberately ignores the run's disabled
        cards — unlike _has_card, which asks whether a card's effect applies.
        """
        return any(c.value == value for c in self.cards)

    def _has_card(self, value):
        """True when an owned card's EFFECT applies right now (e.g. Showman).

        A card disabled for the run (Card cutter) counts as not
        owned, so every passive whole-card effect it drives — Coupon's discount,
        Market's resale, Inferno's exponent, Watch's time factor, ... — stops
        with it. Use _owns_card when the question is ownership, not effect.
        """
        return any(c.value == value and not self._card_disabled(c)
                   for c in self.cards)

    def _card_count(self, value):
        """How many owned copies of a card currently APPLY (see _has_card).

        _has_card answers "is this card's effect on at all?"; the Hoard whole
        card needs the COUNT instead, because each copy of it holds one more
        shop offer in place. A copy the run's trial has cut (Card cutter) is not
        counted, exactly as it is not counted as having the effect at all.
        """
        return sum(1 for c in self.cards
                   if c.value == value and not self._card_disabled(c))

    def _card_activations(self, value):
        """The card-area indexes at which a card of ``value`` ACTIVATES, in order.

        A card activates once per copy whose effect applies, PLUS once per
        Blueprint that copies it (see cards.effective_card_value) — a Blueprint
        plays the card it sits next to, so it activates that card a second time.
        Two copies, or one copy with a Blueprint beside it, therefore activate
        twice. _card_count answers the narrower question of how many copies of
        the card are OWNED (a Blueprint owns nothing of its own), which is what
        Hoard's cap wants; this is what a card that ACTIVATES asks. A copy the
        Card cutter has cut activates nothing.

        The order is the card area's, so a caller can tell WHICH copy paid: a
        card that activates once per copy pops its particle on the copy spending
        the activation (see Game._procrastination_rewind).
        """
        return [i for i, card in enumerate(self.cards)
                if not self._card_disabled(card)
                and cards.effective_card_value(self, i) == value]

    def shop_lock_cap(self):
        """How many shop offers the player may hold across rerolls.

        The Hoard whole card holds one offer per copy — none at all without it
        — so the cap is simply the card's own count: a second Hoard pins a
        second offer. See Game._toggle_shop_lock and Shop.refresh.
        """
        return self._card_count(Card.HOARD)

    @property
    def max_cards(self):
        """How many cards the player may own: MAX_CARDS, or one fewer.

        The Essence whole card trades a slot away, and its own slot counts, so
        while it is owned the limit is MAX_CARDS - 1 cards in all (Essence plus
        the rest). Every path that adds a card — a shop purchase, a random grant,
        a Recognition copy — asks this (or _card_capacity_for, when the card being
        added may be Essence itself) before adding, so no card is left over.

        Two things can win slots back: every INACTION_USES_PER_SLOT uses of the
        Inaction action, and each v2 use of it outright (see card_slot_bonus).
        A card is a board square now rather than a tray slot, so nothing beyond
        this limit caps how many the player may hold.
        """
        return max(1, self._card_slots_wanted())

    def _card_slots_wanted(self):
        """The card slots the player has EARNED."""
        essence_cost = 1 if self._has_card(Card.ESSENCE) else 0
        return MAX_CARDS - essence_cost + self.card_slot_bonus

    @property
    def card_slot_bonus(self):
        """The card slots Inaction has won: one per INACTION_USES_PER_SLOT uses.

        A v2 Inaction is the fifth use, handed over at once rather than counted
        (see Game._action_inaction), so its slots are banked in card_slots_won.
        """
        return (self.card_slots_won
                + self.inaction_used // INACTION_USES_PER_SLOT)

    def card_slot_room(self):
        """How many more card slots could be won.

        Nothing caps the card slots any more: a card lies on a board square, so
        the counting actions (Inaction) always have room to hand one over.
        """
        return 1

    @property
    def max_actions(self):
        """How many actions the player may own.

        MAX_ACTIONS plus what Foresight has won (see Game._action_foresight) —
        or ACTION_SLOTS_UNLIMITED, which its v2 sets: from then on nothing ever
        refuses an action for lack of room.
        """
        if self.action_slots_unlimited:
            return ACTION_SLOTS_UNLIMITED
        return MAX_ACTIONS + self.action_slots_won

    def action_slot_room(self):
        """How many more action slots could be won (always some: see max_actions)."""
        return 1

    def _card_capacity_for(self, value):
        """The card area's size once ``value`` is owned (Essence shrinks it).

        Buying or finding Essence is what takes the slot away, so a path adding
        Essence has to have room for the SMALLER area, not the one it is looking
        at now: at MAX_CARDS - 1 cards the last slot is exactly the one it
        would give up, and adding it there would put a card outside the area.
        """
        if value == Card.ESSENCE and not self._has_card(Card.ESSENCE):
            return self.max_cards - 1
        return int(self.max_cards)

    def _card_sold_message(self, card, message):
        """``message`` plus whatever the card does when it LEAVES by sale.

        Essence distils into ESSENCE_TOKENS random permanent Spirit tokens when
        it is sold (by the sell key or by the Death action — both go through
        here), and the sale message says so. Every other card just keeps its
        sale message, so a new whole card only has to declare its own rule in
        this one place.

        A sale is also what lifts the Deal breaker trial's gag, so EVERY sale
        is recorded on the game here — this is the one place a card leaves by
        SALE (see Game.card_sold / _deal_breaker_gags). The record is a fact
        about the player rather than about the run, so it is kept (and saved)
        whether or not the trial is in play at the time, and the "paid off"
        note is added on the sale that actually lifts the gag, not on every
        later one.
        """
        lifted = not self.card_sold
        self.card_sold = True
        if lifted and self.active_trial == Trial.DEAL_BREAKER:
            message += " — Deal breaker paid off: your blocks score again"
        if card.value != Card.ESSENCE:
            return message
        granted = self._grant_permanent_tokens(ESSENCE_TOKENS)
        if not granted:
            return (f"{message} — no room for its Spirit tokens "
                    f"({MAX_TOKENS} max)")
        plural = "" if granted == 1 else "s"
        return (f"{message} — {granted} permanent Spirit token{plural} "
                f"distilled from its essence")

    def _grant_permanent_tokens(self, count):
        """Grant ``count`` random PERMANENT Spirit tokens (see ScorerToken).

        A token is a whole random block's scorer kept forever: a scorer from the
        shop's pool (never a run role, which a token cannot use, and never the
        no-scorer NONE), its own rolled magnitude, and random effects like a
        random block carries — so an Effective token can actually pay off. The
        token column caps at MAX_TOKENS; only what fits is granted, and the
        caller reports it. Returns how many were granted.
        """
        pool = [s for s in Scorer.SHOP_ORDER
                if s not in (Scorer.START, Scorer.FINISH, Scorer.NONE)]
        granted = 0
        for _ in range(count):
            if len(self.tokens) >= MAX_TOKENS:
                break
            scorer = random.choice(pool)
            shape = random.choice(Shape.ORDER)
            effects = random.sample(Effect.REAL_ORDER, random_effect_count())
            shape, effects = role_block_parts(scorer, shape, effects)
            block = Block(0, 0, shape=shape, effect=Effect.NONE, scorer=scorer,
                          scorer_amount=roll_scorer_amount(scorer),
                          effects=effects,
                          effect_amounts=roll_effect_amounts(effects))
            # A permanent token's Random/Lucky reward is rolled once, here, and
            # kept for every run the token fires in (see _roll_kept_reward).
            self._roll_kept_reward(block)
            token = ScorerToken(block)
            self.tokens.append(token)
            self._on_item_gained(token)
            granted += 1
        return granted