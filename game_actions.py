"""The one-shot actions (Death, Recognition, Inaction, Spirit, Anointment, ...)."""

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


class ActionsMixin:
    """The one-shot actions (Death, Recognition, Inaction, Spirit,
    Anointment, ...)."""


    def _select_action(self, action):
        """Arm an action as the actor; its targets are the rest of the selection.

        An action is selected like every other item (see _toggle_item_selection),
        but it is the ACTOR: the targets it acts on are the items selected after
        it (see Game.selected_targets). S applies it, and nothing happens unless
        it has exactly the number of targets it needs (see _apply_action).
        """
        if (self.pending_pack_action is not None
                and action is not self.pending_pack_action):
            # A pack action is armed and unspent: it is not on the board yet, so
            # nothing else may take the selection away from it or it would be
            # lost (see _keep_action_from_pack).
            self._set_shop_message("Use the packed action first (or press S) — "
                                   f"{self.pending_pack_action.name} is waiting")
            return
        self._clear_active_selection()
        self.selected_toolbox_item = action
        self.selected_toolbox_index = self._shown_index_of(action)
        self.selected_action = action
        self.selected_action_subject = None
        if Action.needs_target(action.value):
            self._set_shop_message(
                f"{action.name} (v{action.version}) — click a target block/card")
        else:
            # A target-free action acts on the player, not on a piece.
            self._set_shop_message(f"{action.name} (v{action.version}) — press S to use")

    def is_action_target(self, item):
        """True when ``item`` is something an active action can be aimed at."""
        if item is None or getattr(item, "kind", None) == "action":
            return False
        return (isinstance(item, Block)
                or getattr(item, "kind", None) in ("block", "card"))

    def _clear_action_selection(self, announce=True):
        """Deselect the current action and its subject.

        The action leaves the SELECTION too: it was selected like any other item
        (see _toggle_item_selection), so cancelling it drops the green frame with
        it and leaves the first remaining item as the actor. A used-up action is
        dropped quietly — it is gone, so there is nothing to announce.
        """
        action = self.selected_action
        self.selected_action = None
        self.selected_action_subject = None
        if action is not None and self.is_item_selected(action):
            self._unselect_item(action, announce=announce)

    def _apply_action(self):
        """Apply the actor action to its targets (the S key).

        The action is the FIRST selected item and what it acts on is everything
        selected behind it (user request: "assume all items selected other than
        the first one is a target item"). If there are not the right number of
        targets, NOTHING happens (user request: "if there are not the right
        number of target items, make nothing happen") — the action is not spent.
        An action that acts on the player rather than on a block or card (see
        Action.needs_target) needs no target at all.
        """
        action = self.selected_action
        pending = action is not None and action is self.pending_pack_action
        if action is None or (action not in self.actions and not pending):
            self._set_shop_message("Select an action first")
            return False
        needed = self.required_targets(action)
        # Everything selected BESIDES the action is a target for it (user
        # request: "assume all items selected other than the first one is a
        # target item"). A packed action is not itself in the selection, so all
        # of it counts.
        targets = [t for t in self.selection
                   if t is not action and self.is_action_target(t)]
        if needed is not None and len(targets) != needed:
            # Not the right number of targets: nothing happens at all.
            self._set_shop_message(
                f"{action.name} needs {needed} target"
                f"{'' if needed == 1 else 's'} — {len(targets)} selected")
            return False
        subject = targets[0] if targets else None
        self.selected_action_subject = subject
        applied = False
        if action.value == Action.CLEANSWEEP:
            applied = self._action_cleansweep(action)
        elif action.value == Action.EXPANSION:
            applied = self._action_expansion(action)
        elif action.value == Action.BRAINSTORM:
            applied = self._action_brainstorm(action)
        elif action.value == Action.MASS_PRODUCTION:
            applied = self._action_mass_production(action)
        elif action.value == Action.GRACE:
            applied = self._action_grace(action)
        elif action.value == Action.INACTION:
            applied = self._action_inaction(action)
        elif action.value == Action.FORESIGHT:
            applied = self._action_foresight(action)
        elif action.value == Action.DEATH:
            applied = self._action_death(action, subject)
        elif action.value == Action.RECOGNITION:
            applied = self._action_recognition(action, subject)
        elif action.value == Action.DEJA_VU:
            applied = self._action_deja_vu(action, subject)
        elif action.value == Action.ANOINTMENT:
            applied = self._action_anointment(action, subject)
        elif action.value == Action.STRENGTH:
            applied = self._action_strength(action, subject)
        elif action.value == Action.SPIRIT:
            applied = self._action_spirit(action, subject)
        else:
            self._set_shop_message("That action does nothing yet")
            return False
        if applied:
            self._consume_action(action)
        return applied

    def _consume_action(self, action):
        """Spend a used action: out of the action area, or off the pack.

        An action a PACK handed over is not in the action area at all, so it is
        spent by clearing the pending slot instead (see
        _keep_action_from_pack). Everything else leaves the action area.

        Using an action also turns the inventory's selection over (see
        _reshuffle_inventory): the inventory holds everything the player owns,
        and what its panel shows is a random draw from it.
        """
        if action is self.pending_pack_action:
            self.pending_pack_action = None
        elif action in self.actions:
            self.actions.remove(action)
        self._clear_action_selection(announce=False)
        self._reshuffle_inventory()

    def _action_cleansweep(self, action):
        """Cleansweep fills every empty card slot with a random card.

        The sweep is paid for with the whole purse — v1 leaves the player with
        $0 — while v2 spares it. The cards come from the same pool a converted
        card does (see _draw_random_card_value): a card the player does not
        already own while one is left, so the sweep is not wasted on a
        duplicate. Refused while the card area is full, because then there is
        nothing to sweep and the cash would go for nothing.
        """
        if len(self.cards) >= self.max_cards:
            self._set_shop_message(f"You can only hold {self.max_cards} cards — nothing to sweep")
            return False
        spent = 0 if action.version >= 2 else self.cash
        self.cash -= spent
        drawn = 0
        while len(self.cards) < self.max_cards:
            value = self._draw_random_card_value()
            if value is None:
                break
            self._adopt_card(make_card_item(value))
            self._discover_owned_card(value)
            drawn += 1
        cards_text = f"{drawn} card{'' if drawn == 1 else 's'}"
        if spent:
            self._set_shop_message(f"Cleansweep swept ${spent} into {cards_text}")
        else:
            self._set_shop_message(f"Cleansweep drew {cards_text}")
        if drawn:
            sounds.play_coin()
        return True

    def _action_expansion(self, action):
        """Expansion opens board squares: 4 of them (v1) or the whole board (v2).

        The squares come from the same frontier a Drill trigger or the
        Conquistador card expands into (see _grant_locked_units), so the board
        grows the way it always does — one edge-adjacent ring at a time. v2
        sweeps the whole board: each pass unlocks the current frontier, and the
        loop runs until a pass unlocks nothing, which is what takes it past the
        first ring. Refused (and kept) when nothing is left to unlock, so the
        action is never wasted on a finished board.
        """
        if action.version < 2:
            if not self._grant_locked_units(EXPANSION_SQUARES):
                self._set_shop_message("The board is already fully unlocked")
                return False
            return True
        total = 0
        while True:
            granted = self._grant_locked_units(GRID_WIDTH * GRID_HEIGHT,
                                               announce=False)
            if not granted:
                break
            total += granted
        if not total:
            self._set_shop_message("The board is already fully unlocked")
            return False
        plural = "s" if total != 1 else ""
        self._set_shop_message(
            f"{action.name} unlocked the whole board ({total} square{plural})")
        sounds.play_coin()
        return True

    def _action_brainstorm(self, action):
        """Brainstorm buys shop luck: 2 free rerolls (v1) or half-price ones (v2).

        The free rerolls go straight into the same bank Fresh fills, and they
        are NOT counted in free_rerolls_run_gain: that counter is what a retry
        claws back (rerolls a RUN granted), while these were bought and are the
        player's to keep. v2 lowers the price of every future reroll for the
        rest of the game (see refresh_cost), which is set rather than
        multiplied so a second Brainstorm cannot stack it to free.
        """
        if action.version < 2:
            self.free_rerolls += BRAINSTORM_REROLLS
            left = (f" ({self.free_rerolls} banked)" if self.free_rerolls
                    else "")
            self._set_shop_message(
                f"{action.name} banked {BRAINSTORM_REROLLS} free rerolls{left}")
            return True
        self.reroll_discount = BRAINSTORM_REROLL_FACTOR
        self._set_shop_message(
            f"{action.name} halved the reroll price (now ${self.refresh_cost()})")
        return True

    def _action_mass_production(self, action):
        """Mass production multiplies resource points: x3 this run (v1), x2 for good (v2).

        The run factor is applied where a resource point is BANKED (see
        _add_resource_points), so every Shreds/Rubble/Ideas/Picky trigger of the
        run pays the multiplied fraction, and it is spent when that run's points
        are committed. The permanent factor is set, not multiplied, so a second
        Mass production cannot compound it into a runaway.
        """
        if action.version < 2:
            self.resource_gain_mult = MASS_PRODUCTION_RUN_FACTOR
            self._set_shop_message(
                f"{action.name} tripled this run's resource points")
            return True
        self.resource_gain_bonus = MASS_PRODUCTION_FOREVER_FACTOR
        self._set_shop_message(
            f"{action.name} doubled resource points for the rest of the game")
        return True

    def _action_grace(self, action):
        """Grace makes a run easier: +1 xMult (v1) or a required score of 0 (v2).

        v1 banks xMult the way a Sharp block does, plus one whole point rather
        than a factor ("+1 xMult": a x2.0 bank becomes x3.0, not x4.0), and the
        bonus is recorded on the game so that the run it was used for keeps it
        through a restart, a board edit or a retry — it is spent when that run
        ends (see _continue_run). v2 drops the run's score target to 0, which
        the run's own completion check clears whatever it scores
        (score_total >= 0).
        """
        if action.version < 2:
            self.run_xmult_bonus += GRACE_RUN_XMULT
            self.run_xmult_pending += GRACE_RUN_XMULT
            self._set_shop_message(
                f"{action.name} added +{GRACE_RUN_XMULT:g} xMult to this run "
                f"(x{self.run_xmult_pending:g} banked)")
            return True
        self.required_score = 0
        # An action owns this run's target now: re-deriving it from the run's
        # schedule (see _refresh_run_target, called when the run's trial is
        # bought or changed) must not quietly make the run failable again.
        self.target_forced = True
        self._set_shop_message(
            f"{action.name}: this run needs a score of 0 — it cannot be failed")
        return True

    def _action_inaction(self, action):
        """Inaction does nothing — but five of them win a card slot.

        A v1 use is banked (see Game.inaction_used) and every
        INACTION_USES_PER_SLOT of them let the player hold one more card, for
        the rest of the game (saved). A v2 use HANDS THE SLOT OVER at once
        instead: the upgrade buys the fifth use, not a better nothing.

        Nothing refuses a use for want of room any more: a card lies on a board
        square (see Game.ensure_board_cells), so there is no tray to fill.
        """
        if action.version >= 2:
            self.card_slots_won += 1
            self._set_shop_message(
                f"{action.name} did nothing, and handed over a card slot "
                f"(you may hold {self.max_cards} cards)")
            sounds.play_coin()
            return True
        gains = 1
        completes = ((self.inaction_used + gains) // INACTION_USES_PER_SLOT
                     > self.card_slot_bonus)
        self.inaction_used += gains
        used = self.inaction_used
        left = INACTION_USES_PER_SLOT - (used % INACTION_USES_PER_SLOT)
        if completes:
            self._set_shop_message(
                f"{action.name} did nothing {used} times — you may hold "
                f"{self.max_cards} cards now")
            sounds.play_coin()
        else:
            self._set_shop_message(
                f"{action.name} did nothing ({used} uses — {left} more for a "
                "card slot)")
        return True

    def _action_foresight(self, action):
        """Foresight lets the player hold more actions — for good.

        A v1 adds FORESIGHT_ACTION_SLOTS slot to the game's own MAX_ACTIONS (see
        Game.max_actions), so every path that checks whether there is room for
        an action — a purchase, a 1000-handed grant, a Brain Loop roll — asks
        the game rather than the constant. A v2 removes the limit ALTOGETHER:
        Game.action_slots_unlimited is set, so nothing ever refuses an action
        again. A v2 is refused (and kept) only when the limit is already gone.
        """
        if action.version >= 2:
            if self.action_slots_unlimited:
                self._set_shop_message(
                    "You can already hold as many actions as you like — kept")
                return False
            self.action_slots_unlimited = True
            self._set_shop_message(
                f"{action.name} removed the limit on actions: hold as many as "
                "you like")
            sounds.play_coin()
            return True
        self.action_slots_won += FORESIGHT_ACTION_SLOTS
        self._set_shop_message(
            f"{action.name} added {FORESIGHT_ACTION_SLOTS} action slot"
            f"{'s' if FORESIGHT_ACTION_SLOTS != 1 else ''} — "
            f"{self.max_actions} in all")
        sounds.play_coin()
        return True

    def _action_death(self, action, subject):
        """Death sells a chosen block or card for 1.5x (v1) / 6x (v2) its price."""
        if self._unsellable(subject):
            self._set_shop_message("Your last Start or Finish block can't be sold")
            return False
        multiplier = 6 if action.version >= 2 else 1.5
        if getattr(subject, "kind", None) == "card":
            if subject not in self.cards:
                self._set_shop_message("Action target is not owned")
                return False
            gained = int(subject.price * multiplier)
            self.cards.remove(subject)
            self.cash += gained
            self._set_shop_message(self._card_sold_message(
                subject, f"{action.name} sold {subject.name} for ${gained}"))
            sounds.play_coin()
            return True
        if isinstance(subject, Block):
            # A placed block sells for its own stored price (what it was placed
            # with), never a recount of its parts.
            gained = int(block_resale_price(subject) * multiplier)
            self.grid.pop((subject.x, subject.y), None)
            if subject.scorer == Scorer.START:
                self.marbles = [m for m in self.marbles
                                if getattr(m, "start_block", None) is not subject]
            # Selling the block sells the item it was built from with it (see
            # _release_block_item) — one existence, one sale. Its switch goes off
            # too: the block is not on the board any more.
            self._forget_item(subject)
            self._release_block_item(subject)
            self._delete_pairing_partners(subject)
            self.cash += gained
            self._set_shop_message(f"{action.name} sold {self._item_name(subject)} for ${gained}")
            sounds.play_coin()
            return True
        if subject not in self.toolbox.items:
            self._set_shop_message("Action target is not owned")
            return False
        gained = int(subject.price * multiplier)
        self.toolbox.remove(subject)
        self.assigned_toolbox_indexes.pop(subject, None)
        self._forget_item(subject)
        self._delete_pairing_partners(subject)
        self.cash += gained
        self._set_shop_message(f"{action.name} sold {self._item_name(subject)} for ${gained}")
        sounds.play_coin()
        return True

    def _action_recognition(self, action, subject):
        """Recognition duplicates a block (v1) or a card (v2) for its cost."""
        if action.version >= 2:
            # v2: duplicate a card.
            if getattr(subject, "kind", None) != "card" or subject not in self.cards:
                self._set_shop_message("v2 Recognition targets an owned card")
                return False
            if len(self.cards) >= self._card_capacity_for(subject.value):
                self._set_shop_message(f"You can only hold {self.max_cards} cards")
                return False
            if self.cash < subject.price:
                self._set_shop_message(f"Need ${subject.price} to duplicate {subject.name}")
                return False
            self._adopt_card(make_card_item(
                subject.value, amount=getattr(subject, "amount", 0)))
            self.cash -= subject.price
            self._set_shop_message(f"Recognized a copy of {subject.name} (${subject.price})")
            sounds.play_coin()
            return True
        # v1: duplicate a block.
        if getattr(subject, "kind", None) == "card":
            self._set_shop_message("v1 Recognition targets a block")
            return False
        if isinstance(subject, Block):
            # A placed block is duplicated for its own stored price, matching
            # what the player paid for it (see block_resale_price).
            price = block_resale_price(subject)
            copy = BlockItem(0, 0, subject.shape, Effect.NONE, subject.scorer,
                             subject.scorer_amount, price,
                             f"{Shape.name(subject.shape)} {Scorer.name(subject.scorer)}",
                             portal_number=getattr(subject, "portal_number", 0),
                             key_number=getattr(subject, "key_number", 0),
                             trigger_limit=getattr(subject, "trigger_limit", 1),
                             trigger_paid=getattr(subject, "trigger_paid", 0),
                             effects=subject.effects,
                             effect_amounts=getattr(subject, "effect_amounts", None))
        else:
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
            price = subject.price
            copy = BlockItem(0, 0, subject.shape, Effect.NONE, subject.scorer,
                             subject.scorer_amount, subject.price, subject.name,
                             portal_number=getattr(subject, "portal_number", 0),
                             key_number=getattr(subject, "key_number", 0),
                             trigger_limit=getattr(subject, "trigger_limit", 1),
                             trigger_paid=getattr(subject, "trigger_paid", 0),
                             effects=subject.effects)
        if self.cash < price:
            self._set_shop_message(f"Need ${price} to duplicate this block")
            return False
        self.toolbox.add(copy)
        self.cash -= price
        self._set_shop_message(f"Recognized a copy of {self._item_name(subject)} (${price})")
        sounds.play_coin()
        return True

    def _action_deja_vu(self, action, subject):
        """Deja Vu gives a chosen block more triggers: +1 (v1) or +100 (v2).

        The trigger limit is raised like a paid upgrade, but no cash is paid,
        so nothing is added to the block's refundable trigger_paid. A block on
        the BOARD also gains the extra triggers right now (so the action can
        revive a block that has already spent its triggers), while a toolbox
        block takes the new limit with it when it is placed. Blocks that never
        spend a trigger are refused: the run roles (they score for free every
        time) and a block with no scorer (which has no payoff to trigger), so
        the action is never wasted.
        """
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Deja Vu targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("Role blocks never spend triggers")
            return False
        if subject.scorer == Scorer.NONE:
            self._set_shop_message("That block has no scorer to trigger")
            return False
        gained = 100 if action.version >= 2 else 1
        subject.trigger_limit += gained
        if isinstance(subject, Block):
            subject.triggers_left += gained
        self._add_portal_pair_triggers(subject, gained)
        self._set_shop_message(
            f"{action.name} gave {self._item_name(subject)} +{gained} triggers "
            f"(now {self._trigger_limit(subject)})")
        return True

    def _add_portal_pair_triggers(self, block, amount):
        """Give a portal's partners the same extra triggers (and its new limit).

        A portal pair shares one trigger count, so a Deja Vu upgrade on one
        half has to reach the other halves too: otherwise the next contact would
        sync them back down to the lower count and waste the upgrade. Every
        portal sharing the number is upgraded — Recognition can leave more than
        two of them (see _delete_paired_portal). The partner may be unplaced (a
        toolbox block, which has no trigger count of its own yet), so only its
        limit is carried over then.
        """
        if not getattr(block, "has_effect", lambda e: False)(Effect.PORTAL):
            return
        number = getattr(block, "portal_number", 0)
        if not number:
            return
        for other in list(self.toolbox.items) + self.board_blocks():
            if other is block or getattr(other, "portal_number", 0) != number:
                continue
            if getattr(other, "placed_cell", None) is not None:
                # Its BLOCK is the copy that matters, and that block is in
                # board_blocks(): touching both would upgrade one portal twice.
                continue
            other.trigger_limit = block.trigger_limit
            if hasattr(other, "triggers_left"):
                other.triggers_left += amount

    def _enchant_block(self, item, effect):
        """Give a block one extra effect and reprice it for the new part.

        The effect arrives with its own rolled magnitude (see
        roll_effect_magnitude), and the block is repriced by the effect's
        CATALOG price — never by the strength it rolled — so the block's resale
        value (what a sale, a Death action, and the Painting condition read)
        keeps matching what the block is made of without charging for luck.
        """
        item.effects.append(effect)
        magnitude = roll_effect_magnitude(effect)
        if magnitude:
            item.effect_amounts[effect] = magnitude
        added = effect_component_price(effect)
        for attr in ("price", "resale_price"):
            if hasattr(item, attr):
                setattr(item, attr, getattr(item, attr) + added)

    def _random_new_effects(self, item, count):
        """``count`` random real effects the block does not already have."""
        pool = [e for e in Effect.REAL_ORDER
                if e != Effect.PORTAL and e not in item.effects]
        random.shuffle(pool)
        return pool[:count]

    def _action_anointment(self, action, subject):
        """Anointment adds random effects: 2 to one block (v1), 1 to each (v2).

        A Portal is never handed out (a lone portal is inert), and the Start
        and Finish roles are skipped: their faces ignore effects entirely, so
        blessing them would only waste the action. v2 covers every block on
        the board AND in the inventory, so it needs no single good target.
        """
        if action.version >= 2:
            targets = [b for b in self.board_blocks()
                       if b.scorer not in (Scorer.START, Scorer.FINISH)]
            # A placed block's item is that same block (see _place_block_at), so
            # its item is not a second target — one block gets one effect.
            targets += [i for i in self.toolbox.items
                        if getattr(i, "kind", None) == "block"
                        and getattr(i, "placed_cell", None) is None
                        and i.scorer not in (Scorer.START, Scorer.FINISH)]
            blessed = 0
            for target in targets:
                effects = self._random_new_effects(target, 1)
                if effects:
                    self._enchant_block(target, effects[0])
                    blessed += 1
            if not blessed:
                self._set_shop_message("No block could be blessed")
                return False
            self._set_shop_message(
                f"{action.name} blessed {blessed} block"
                f"{'s' if blessed != 1 else ''}")
            sounds.play_mech()
            return True
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Anointment targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("Role blocks keep a plain Rect")
            return False
        effects = self._random_new_effects(subject, 2)
        if not effects:
            self._set_shop_message("That block already has every effect")
            return False
        for effect in effects:
            self._enchant_block(subject, effect)
        self._set_shop_message(
            f"{action.name} gave {self._item_name(subject)} "
            f"{', '.join(Effect.name(e) for e in effects)}")
        sounds.play_mech()
        return True

    def _action_strength(self, action, subject):
        """Strength raises a block's scorer amount: +50% (v1) or x3 (v2).

        Whole-number amounts stay whole (+4 mult -> +6) and fractional ones stay
        fractional (xMult 1.5 -> 2.25), so the scorer keeps its kind. Blocks
        with nothing to strengthen are refused: the roles (which pay nothing)
        and a scorerless block (whose amount is never read).
        """
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Strength targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("Role blocks have no scorer to strengthen")
            return False
        if subject.scorer == Scorer.NONE:
            self._set_shop_message("That block has no scorer to strengthen")
            return False
        amount = subject.scorer_amount
        factor = 3.0 if action.version >= 2 else 1.5
        raised = amount * factor
        if isinstance(amount, int):
            raised = int(raised + 0.5)
        subject.scorer_amount = raised
        self._set_shop_message(
            f"{action.name} raised {self._item_name(subject)} to "
            f"{self._particle_amount_text(raised)}")
        sounds.play_mech()
        return True

    def _action_spirit(self, action, subject):
        """Spirit destroys a block and keeps its scorer firing for later runs.

        The block is removed and a token is added (see ScorerToken) that fires
        that scorer at the start of each run: the next 2 runs for v1, every run
        for v2. Nothing is paid out now, so the block is not "sold" — it is
        sacrificed. The roles are refused (destroying a Start block would end
        the game) and so is a scorerless block (there is nothing to keep).
        """
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Spirit targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("The run roles can't be sacrificed")
            return False
        if subject.scorer == Scorer.NONE:
            self._set_shop_message("That block has no scorer to keep")
            return False
        if len(self.tokens) >= MAX_TOKENS:
            self._set_shop_message(
                f"Token slots are full ({MAX_TOKENS}) — use one first")
            return False
        name = self._item_name(subject)
        runs_left = None if action.version >= 2 else 2
        # The token keeps the BLOCK itself, not just its scorer: the payoff is
        # then exactly what colliding with that block would do (its cell drives
        # the board-relative scorers, its effects an Effective payoff, its
        # shape the cards that fire along with it). The copy keeps a shattered
        # fragile block's real shape (see block_shape). A block still in the
        # inventory never stood anywhere, so its token keeps the least generous
        # cell: the bottom row of the first column.
        token_block = Block(getattr(subject, "x", 0),
                            getattr(subject, "y", GRID_HEIGHT - 1),
                            shape=block_shape(subject), effect=Effect.NONE,
                            scorer=subject.scorer,
                            scorer_amount=subject.scorer_amount,
                            angle=getattr(subject, "angle", None) or 0,
                            effects=list(subject.effects),
                            effect_amounts=dict(
                                getattr(subject, "effect_amounts", None) or {}))
        # A Random/Lucky block is sacrificed with its reward already decided,
        # and the token keeps that one outcome for every run it covers (see
        # KEPT_ROLL_RUN), so retrying a run or loading a save cannot reroll what
        # the token pays.
        self._roll_kept_reward(token_block)
        token = ScorerToken(token_block, runs_left=runs_left)
        # Remove the sacrificed block exactly like a sale/erase would (a placed
        # block leaves the board; a Start block's marble is gone with it).
        if isinstance(subject, Block):
            self.grid.pop((subject.x, subject.y), None)
            if subject.scorer == Scorer.START:
                self.marbles = [m for m in self.marbles
                                if getattr(m, "start_block", None) is not subject]
            # The sacrificed block's item goes with it (see _release_block_item):
            # the token is what the player keeps now.
            self._release_block_item(subject)
        else:
            self.toolbox.remove(subject)
            self.assigned_toolbox_indexes.pop(subject, None)
        self._forget_item(subject)
        self._delete_pairing_partners(subject)
        self.tokens.append(token)
        left = "permanently" if runs_left is None else f"for {runs_left} run(s)"
        self._set_shop_message(
            f"{action.name} kept {Scorer.name(token.scorer)} from {name} {left}")
        sounds.play_mech()
        return True
