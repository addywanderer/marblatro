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
    Ability,
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
    Keyword,
    MarbleType,
    Modifier,
    Pack,
    Quality,
    Rarity,
    Scorer,
    Structure,
    Tool,
    Verb,
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
    ToolItem,
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
        if Action.optional_target(action.value):
            # Dynamite: a structure if the player points at one, the board
            # itself if they do not (see _action_dynamite).
            self._set_shop_message(
                f"{action.name} (v{action.version}) — press S to blast the "
                f"board open, or click a structure to dig or reveal it")
        elif Action.needs_target(action.value):
            what = ("structure" if Action.targets_structures(action.value)
                    else "block/card")
            self._set_shop_message(
                f"{action.name} (v{action.version}) — click a target {what}")
        else:
            # A target-free action acts on the player, not on a piece.
            self._set_shop_message(f"{action.name} (v{action.version}) — press S to use")

    def is_action_target(self, item, action=None):
        """True when ``item`` is something an active action can be aimed at.

        A block or a card is the usual subject; a component piece counts too,
        because Cleansing is aimed at a block, an effect or a scorer (see
        _action_cleansing) and each action refuses the targets it cannot use.

        ``action`` is the action being aimed: the kind of target it takes comes
        from its own table (see Action.STRUCTURE_TARGET and Action.ANY_TARGET),
        so a Reroll can only ever be pointed at a structure, a Recycling at any
        item the player owns, and every other action never is. Without an action
        the question is the general one — what an action may be aimed
        at — which is what the selection highlight and the tool prompt ask.
        """
        if item is None or getattr(item, "kind", None) == "action":
            return False
        if Action.targets_structures(getattr(action, "value", None)):
            return self.is_structure(item)
        if Action.targets_anything(getattr(action, "value", None)):
            # Recycling is aimed at whatever the player wants to put back in the
            # deck, so any of their items will do (a tool and a component are
            # items like the rest). An action is still never a target, a Spirit
            # token is LIVE for its run rather than a card in the deck (see
            # _stays_out_of_the_deck), and a thing the player does not own — the
            # level's own blocks, an offer still on the shelf — cannot be picked
            # up by the highlight either.
            if getattr(item, "kind", None) == "token":
                return False
            return self.owns_item(item) or isinstance(item, Block)
        return (isinstance(item, Block)
                or getattr(item, "kind", None) in ("block", "card",
                                                   Component.EFFECT,
                                                   Component.SCORER))

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

    def _use_ability(self):
        """The S key: fire the actor's ABILITY, if it has one it can use.

        This is the one door S comes through (see components.Ability). The actor
        is the first of the items S acts on -- the armed action, then the armed
        tool, then whatever is held -- and the ability table says what it needs,
        what it costs and which method carries it out (Ability.HANDLERS). Every
        capability therefore shares one dispatch, one vocabulary and one hint.

        Returns False when S should fall through to the board-building meanings
        (assembling parts into a block, taking a block apart, building a plain
        wall): that happens when the actor has no ability at all, or has one whose
        targets are not met yet -- a Wasteful block with nothing selected beside
        it keeps the ordinary S meanings (see _use_wasteful).
        """
        for actor in (self.selected_action, getattr(self, "selected_tool", None),
                      self.selected_toolbox_item):
            ability = Ability.of(actor)
            if ability is None or not self._ability_is_ready(ability, actor):
                continue
            # The handler is looked up from the table, so an ability that exists
            # is an ability the game can actually fire.
            getattr(self, Ability.handler(ability))(actor)
            return True
        return False

    def _ability_is_ready(self, ability, actor):
        """True when the actor's ability has the targets it asks for."""
        if ability == Ability.OPEN:
            return getattr(self, "selected_tool", None) is not None
        if ability == Ability.MODIFY:
            return bool([item for item in self.selected_targets()
                         if getattr(item, "kind", None) == "card"])
        if ability == Ability.DISCARD:
            return bool([item for item in self.selected_targets()
                         if item is not actor])
        return True

    def _apply_action(self, actor=None):
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
                   if t is not action and self.is_action_target(t, action)]
        if Action.optional_target(getattr(action, "value", None)):
            # An action that takes a structure IF there is one (Dynamite) is
            # used bare or on exactly one: two structures would be ambiguous,
            # and the card's own handler decides what no target means.
            if len(targets) > 1:
                self._set_shop_message(
                    f"{action.name} takes no target or 1 structure — "
                    f"{len(targets)} selected")
                return False
        elif needed is not None and len(targets) != needed:
            # Not the right number of targets: nothing happens at all.
            self._set_shop_message(
                f"{action.name} needs {needed} target"
                f"{'' if needed == 1 else 's'} — {len(targets)} selected")
            return False
        # An action that asks for ENERGY (see Action.ENERGY) is paid for out of
        # the run's own budget, exactly as a tool is: nothing happens — and
        # nothing is spent — when the budget cannot cover it.
        cost = Action.energy(getattr(action, "value", None))
        if self.energy < cost:
            self._set_shop_message(
                f"Out of energy — {self.max_energy} a run, back at the next one")
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
        elif action.value == Action.LANTERN:
            applied = self._action_lantern(action)
        elif action.value == Action.EYEBALL:
            applied = self._action_eyeball(action)
        elif action.value == Action.DEEP_POCKETS:
            applied = self._action_deep_pockets(action)
        elif action.value == Action.NASTY_COCKTAIL:
            applied = self._action_nasty_cocktail(action)
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
        elif action.value == Action.CLEANSING:
            applied = self._action_cleansing(action, subject)
        elif action.value == Action.REROLL:
            applied = self._action_reroll(action, subject)
        elif action.value == Action.DYNAMITE:
            applied = self._action_dynamite(action, subject)
        elif action.value == Action.HORSESHOE:
            applied = self._action_horseshoe(action)
        elif action.value == Action.RECYCLING:
            applied = self._action_recycling(action, subject)
        elif action.value == Action.STORMCLOUD:
            applied = self._action_stormcloud(action, subject)
        elif action.value == Action.FLOOR_PLANS:
            applied = self._action_floor_plans(action)
        else:
            self._set_shop_message("That action does nothing yet")
            return False
        if applied:
            if getattr(self, "deck_pick_action", None) is action:
                # Eyeball has only ARMED its pick: it is paid for when the
                # cards are actually drawn (see _finish_deck_pick), so closing
                # the deck costs nothing.
                return applied
            self.energy -= cost
            self._consume_action(action)
        return applied

    def _discard_used_card(self, card):
        """Throw a card away BECAUSE IT WAS USED — unless it is reusable.

        The one rule behind every "and discard this card" in the game: a spent
        action (see _consume_action), a Lantern burning out (see _action_lantern)
        and a Reroll turning a structure over (see _action_reroll). User request:
        "when a card is used, discard it unless it has the keyword reusable", so
        the card leaves through the ordinary discard door — the run counts it
        (the Trash Can card pays for those) — and a card whose keywords include
        REUSABLE simply stays where it is: it has been used, not used up.

        An action a PACK handed over never joined the hand, so there is nothing
        of the player's to take off the board: its slot is cleared and the run
        still counts it as an item it threw away.

        Returns True when the card left the game.
        """
        if Keyword.has(card, Keyword.REUSABLE):
            return False
        if card is self.pending_pack_action:
            self.pending_pack_action = None
            self._count_discard()
            return True
        return self._discard_item(card)

    def _consume_action(self, action):
        """Use a card up: it is DISCARDED, unless its keywords say "reusable".

        User request: "when a card is used, discard it unless it has the keyword
        reusable." So a used action goes through the ordinary discard door (see
        _discard_used_card) — it leaves the action area and the run counts it as
        an item it threw away — while a reusable action stays exactly where it
        was (in the action area, or armed on a pack) and can simply be used
        again. Either way its energy has already been spent (see _apply_action).

        Using an action also turns the inventory's selection over (see
        _reshuffle_inventory): the inventory holds everything the player owns,
        and what its panel shows is a random draw from it.
        """
        self._discard_used_card(action)
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
        """Expansion hands over Board Units: 4 of them (v1) or the whole board (v2).

        User request: "make all items that unlock random board squares give
        board squares instead, unless otherwise stated." A v1 no longer picks
        four squares for the player — it gives four Board Units, which each open
        the locked square the player chooses (see _grant_board_units). The
        UPGRADE states otherwise and keeps its own rule: a v2 unlocks every
        locked square on the board, one frontier ring at a time (see
        _grant_locked_units). Either version is refused (and kept) when the
        board is already fully open, so the action is never wasted on a finished
        board.
        """
        if not self.board_locked():
            self._set_shop_message("The board is already fully unlocked — kept")
            return False
        if action.version < 2:
            self._grant_board_units(EXPANSION_SQUARES)
            return True
        total = 0
        while True:
            granted = self._grant_locked_units(GRID_WIDTH * GRID_HEIGHT,
                                               announce=False)
            if not granted:
                break
            total += granted
        plural = "s" if total != 1 else ""
        self._set_shop_message(
            f"{action.name} unlocked the whole board ({total} square{plural})")
        sounds.play_coin()
        return True

    def _action_brainstorm(self, action):
        """Brainstorm puts Reroll cards on the board: 2 of them, or 4 upgraded.

        User request: "make all reroll mechanics spawn this card on the board
        when triggered." Brainstorm used to bank free shop rerolls (and its
        upgrade halve their price), which the shelf's rework left with nothing
        to spend them on; what it hands over now is the reroll itself — the
        Reroll card (see Game._spawn_reroll_cards). The cards are BOUGHT, not
        earned by a run, so retrying the run does not take them back.
        """
        count = (BRAINSTORM_REROLLS_V2 if action.version >= 2
                 else BRAINSTORM_REROLLS)
        self._spawn_reroll_cards(count)
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

    def _action_lantern(self, action):
        """Lantern: draw its magnitude in items from the deck, then discard itself.

        The action's own magnitude is the number of items it draws (see
        MAGNITUDES.ACTIONS), so a Lantern a golem combined with another one
        really does draw twice as many. The items come out of the deck through
        the same door Wasteful uses (see _draw_one_item) and the first takes the
        Lantern's own square, so the draw appears where the light was; the
        Lantern itself is then thrown away through _discard_used_card, which is
        what makes the run's discard count go up (the Trash Can card pays for
        it) — unless it is REUSABLE, in which case it stays lit (see
        Game._discard_used_card). With an empty deck nothing happens and nothing
        is spent.
        """
        if not self.deck_items():
            self._set_shop_message("The Lantern needs an item in the deck to draw")
            return False
        draws = max(0, int(action.amount))
        origin = self.item_cell(action)
        # "and discards this card": the action leaves for good, and the run
        # counts it as one of the items it threw away — unless it is reusable,
        # in which case it merely gave its light and stays.
        thrown = self._discard_used_card(action)
        drawn = []
        for index in range(draws):
            item = self._draw_one_item(origin if index == 0 else None)
            if item is None:
                break
            drawn.append(item)
        names = ", ".join(self._item_name(item) for item in drawn) or "nothing"
        ending = "and burned out" if thrown else "and stayed lit"
        self._set_shop_message(f"Lantern drew {names} {ending}")
        sounds.play_mech()
        return True

    def _action_eyeball(self, action):
        """Eyeball: the player PICKs the cards they draw out of the deck.

        User request: "pick a card from your deck to draw (1 energy)." The pick
        is made where the deck is shown — the DECK overlay — so using this
        action arms a pick and opens it (see Game.arm_deck_pick /
        Game._click_deck_pick). Nothing is spent until a card is actually
        drawn: closing the overlay keeps the action, so a look is free. The
        action's own magnitude is how many cards it may take, so a golem-folded
        Eyeball takes two.
        """
        if not self.eyeball_cards():
            self._set_shop_message(
                "Eyeball needs a card in the deck to draw — kept")
            return False
        self.arm_deck_pick(action)
        return True

    def _action_deep_pockets(self, action):
        """Deep Pockets: a random pack, paid for with a random structure.

        User request: "create a random pack, destroy a random structure (1
        energy)." The pack comes from the shop's own roller, so it obeys the
        same type, size and ownership rules every other pack does, and it joins
        the player's items on the board (ready to open). The structure is taken
        off the level for this visit — marked SPENT exactly as an opened one is
        (see _consume_structure), so laying the level out again cannot bring it
        back — and its square is left empty. A level with nothing left standing
        still hands the pack over: there is simply nothing to pull down.
        """
        packs = max(1, int(getattr(action, "amount", 1) or 1))
        made = []
        for _ in range(packs):
            pack = self.shop._roll_pack(random.choice(Pack.ORDER),
                                        random.choice(Pack.SIZE_ORDER))
            self._adopt_pack(pack)
            self._on_item_gained(pack)
            self._discover_pack(pack.pack_type)
            made.append(pack.name)
        destroyed = []
        for _ in range(packs):
            standing = self.level_structures()
            if not standing:
                break
            victim = random.choice(standing)
            destroyed.append(self._item_name(victim).lower())
            self._consume_structure(victim, discover=False)
        message = f"{action.name} made {', '.join(made)}"
        if destroyed:
            plural = "" if len(destroyed) == 1 else "s"
            message += (f", pulling down the {', '.join(destroyed)} "
                        f"(structure{plural} gone for this level)")
        else:
            message += " — no structure was left to pull down"
        self._set_shop_message(message)
        sounds.play_coin()
        return True

    def _action_nasty_cocktail(self, action):
        """Nasty Cocktail: energy for every modifier riding on the card.

        User request: "gain 1 energy for each unique modifier on this card (0
        energy)". The count is the number of KINDS of modifier the card carries
        (Modifier.of — golden, diamond, forgotten, temporary, token,
        retriggerable, v2, flipped, disabled), however many stacks each has,
        times the action's own magnitude, so a golem-folded cocktail pays
        double. A plain cocktail carries none and would give nothing, so it is
        refused and KEPT rather than wasted — an upgraded (v2) one is a drink
        worth pouring, since v2 is a modifier too.
        """
        kinds = len(Modifier.of(action))
        if not kinds:
            self._set_shop_message(
                f"{action.name} has no modifiers yet — it would give no "
                f"energy, so it is kept")
            return False
        gained = max(1, int(getattr(action, "amount", 1) or 1)) * kinds
        self.energy += gained
        self._set_shop_message(
            f"{action.name} gave {gained} energy "
            f"({kinds} modifier{'' if kinds == 1 else 's'})")
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
            # ...and a copy of a combined card is combined too (see Quality).
            copy = make_card_item(subject.value,
                                  amount=getattr(subject, "amount", 0))
            copy.quality = Quality.of(subject)
            self._adopt_card(copy)
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
                             effect_amounts=getattr(subject, "effect_amounts", None),
                             quality=Quality.of(subject))
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
                             effects=subject.effects,
                             quality=Quality.of(subject))
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

    def _action_cleansing(self, action, subject):
        """Cleansing multiplies a piece's MAGNITUDE by 1.5 (v1) or 2.5 (v2).

        It works on any piece that HAS a magnitude the game reads: a block
        (its scorer amount and every effect strength), an effect component or a
        scorer component. A shape has no magnitude and is refused, and so is a
        block whose scorer and effects are all inert — there is nothing to
        clean.
        """
        if subject is None:
            self._set_shop_message("Cleansing needs a block, effect or scorer")
            return False
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif not self.owns_item(subject):
            self._set_shop_message("Action target is not owned")
            return False
        kind = getattr(subject, "kind", None)
        factor = 2.5 if action.version >= 2 else 1.5
        if kind in (Component.EFFECT, Component.SCORER):
            subject.amount = round(subject.amount * factor, 2)
            self._set_shop_message(
                f"{action.name} raised {self._item_name(subject)} to "
                f"{self._particle_amount_text(subject.amount)}")
            sounds.play_mech()
            return True
        if not (isinstance(subject, Block) or kind == "block"):
            self._set_shop_message("Cleansing works on a block, effect or scorer")
            return False
        cleaned = False
        if getattr(subject, "scorer", Scorer.NONE) not in (Scorer.NONE,
                                                           Scorer.START,
                                                           Scorer.FINISH):
            subject.scorer_amount = self._clean_amount(subject.scorer_amount,
                                                       factor)
            cleaned = True
        amounts = getattr(subject, "effect_amounts", None)
        if amounts:
            subject.effect_amounts = {k: self._clean_amount(v, factor)
                                      for k, v in amounts.items()}
            cleaned = True
        if not cleaned:
            self._set_shop_message("There is nothing on that block to clean")
            return False
        self._set_shop_message(f"{action.name} strengthened {self._item_name(subject)}")
        sounds.play_mech()
        return True

    @staticmethod
    def _clean_amount(amount, factor):
        """One magnitude, multiplied: whole numbers stay whole, rest keep 2dp."""
        if amount is None:
            return amount
        raised = amount * factor
        return int(raised + 0.5) if isinstance(amount, int) else round(raised, 2)

    def _action_reroll(self, action, subject):
        """Reroll: the selected structure becomes another one, where it stands.

        User request: "randomize a selected structure, discard this card, draw a
        card (0 energy)". The structure keeps its square and its place in the
        level's plan (see _reroll_structure), so the board never moves about
        under the player and no later layout pass can undo the reroll. Then the
        card leaves through the ordinary discard door and what it draws takes
        the square it gave up, exactly like the Lantern — unless the card is
        REUSABLE, in which case it stays in hand (see Game._discard_used_card).

        Tesseract pays for a reroll (see Game._grow_tesseract): a reroll is this
        card now, so using one is what the card counts.
        """
        if not self.is_structure(subject):
            self._set_shop_message(
                f"{action.name} needs a structure to reroll — kept")
            return False
        new_value = self._reroll_structure_value(subject)
        if new_value is None:
            self._set_shop_message(
                f"There is no other structure to turn the "
                f"{self._item_name(subject).lower()} into — kept")
            return False
        was = self._item_name(subject).lower()
        self._reroll_structure(subject, new_value)
        note = self._grow_tesseract()
        origin = self.item_cell(action)
        # "discards this card": it leaves for good, and the run counts it as one
        # of the items it threw away (the Trash Can card pays for those) —
        # unless it is REUSABLE (see Game._discard_used_card).
        self._discard_used_card(action)
        drawn = []
        for index in range(max(0, int(action.amount))):
            item = self._draw_one_item(origin if index == 0 else None)
            if item is None:
                break
            drawn.append(self._item_name(item))
        drew = f", drew {', '.join(drawn)}" if drawn else ""
        self._set_shop_message(
            f"The {was} is now a {self._item_name(subject).lower()}{drew}{note}")
        sounds.play_mech()
        return True

    def _reroll_structure_value(self, structure):
        """A random structure other than this one, or None when there is none.

        Every structure is in the pool — "randomize a selected structure" is the
        whole of the card, so a level of four pits may still hand back a mirror
        — less the one already standing there and less anything this level visit
        OPENED on that square (see _structure_is_spent): a reroll must not deal
        back a structure the player has already used up.
        """
        cell = self.item_cell(structure)
        spent = getattr(self, "spent_structures", ())
        options = [value for value in Structure.ORDER
                   if value != structure.value
                   and not (cell is not None
                            and (value, cell[0], cell[1]) in spent)]
        return random.choice(options) if options else None

    def _action_dynamite(self, action, subject):
        """Dynamite: a bang that opens the board — or a structure — wide open.

        User request: "add a card, 'dynamite': when used with no items selected,
        unlock 10 random board squares adjacent to the unlocked area this card
        was used in. or, dig or reveal. costs 2 energy."

        With NOTHING selected the blast opens its own magnitude in random
        locked squares on the frontier of the unlocked board (see
        _grant_locked_units) — one of the few items that still unlocks squares
        rather than handing over a Board Unit, because that is exactly what it
        says it does (the "unless otherwise stated" of _grant_board_units).
        With a structure selected it is used like a tool instead: it digs or
        reveals it, and the reward takes the square it gave up. Either way the
        card's 2 energy is charged and the card discarded by _apply_action.
        """
        others = [item for item in self.selection if item is not action]
        if not others:
            granted = self._grant_locked_units(max(0, int(action.amount)),
                                               announce=False)
            if not granted:
                self._set_shop_message(
                    "The board is already fully unlocked — kept")
                return False
            self._set_shop_message(
                f"{action.name} blew open {granted} board square"
                f"{'' if granted == 1 else 's'}")
            sounds.play_mech()
            return True
        if not self.is_structure(subject) or len(others) != 1:
            self._set_shop_message(
                f"{action.name} needs nothing selected or 1 structure — kept")
            return False
        verbs = Action.opens_with(action.value)
        verb = next((candidate for candidate in verbs
                     if Structure.result(subject.value, candidate) is not None),
                    None)
        kind, value = (Structure.result(subject.value, verb) if verb is not None
                       else (None, None))
        if verb is None:
            self._set_shop_message(
                f"The {self._item_name(subject).lower()} cannot be dug or "
                f"revealed — kept")
            return False
        if kind == "merge":
            # The golem does not hold a reward: it needs TWO of the player's
            # items (see _golem_pair), and a blast cannot bring them.
            self._set_shop_message(
                f"The {self._item_name(subject).lower()} needs a tool and two "
                f"items, not a blast — kept")
            return False
        was = self._item_name(subject).lower()
        origin = self.item_cell(subject)
        reward = self._structure_reward(kind, value)
        self._consume_structure(subject)
        if origin is not None:
            self.set_item_cell(reward, origin)
        self._adopt_reward(reward)
        made = Pack.name(value) if kind == "pack" else Action.name(value)
        self._set_shop_message(
            f"{action.name} {Verb.done(verb)} the {was} — {made}")
        sounds.play_mech()
        return True

    def _action_horseshoe(self, action):
        """Horseshoe: throw the hand back into the deck and draw a bigger one.

        User request: "add a card: 'horseshoe' (discard all items on the board
        that you own, draw the same number plus 3 new items. costs 1 energy)".
        A discard is not a destruction here — the answer Smelly Socks' discard
        gave is the rule the whole game follows — so everything the player owns
        on the board goes back INTO THE DECK (see _sweep_board_into_deck) and the
        very next draw can deal it again: the card is a mulligan with a bonus,
        not a sacrifice. What never leaves the board is what _stays_out_of_the_
        deck names (the role blocks a run is built from and the Spirit tokens),
        and the card itself sits out its own sweep, so a REUSABLE Horseshoe is
        used rather than thrown.

        The draw is the hand it threw back PLUS its own magnitude (see
        MAGNITUDES.HORSESHOE_EXTRA_DRAWS), so a golem-folded one draws two more
        than it discarded. It comes out of the deck through the same door every
        other draw uses (see _draw_one_item) and stops when the deck runs out.
        """
        on_board = [item for item in self.hand_items()
                    if item is not action
                    and not self._stays_out_of_the_deck(item)]
        if not on_board and not self.drawable_deck_items():
            self._set_shop_message(
                f"{action.name} needs an item on the board or in the deck — "
                f"kept")
            return False
        returned = self._sweep_board_into_deck(keep=action)
        wanted = len(returned) + max(0, int(action.amount))
        drawn = []
        for _ in range(wanted):
            item = self._draw_one_item()
            if item is None:
                break
            drawn.append(item)
        self._set_shop_message(
            f"{action.name} threw {len(returned)} item"
            f"{'' if len(returned) == 1 else 's'} back into the deck and drew "
            f"{len(drawn)}"
            + (" (the deck ran out)" if len(drawn) < wanted else ""))
        sounds.play_coin()
        return True

    def _action_recycling(self, action, subject):
        """Recycling: the selected item goes back in the deck, and two come out.

        User request: "add a card, 'recycling' (discard selected item, draw 2
        items for 0 energy)". It is the one action aimed at an item that gives
        the item back: the target is put in the DECK (see _to_deck — the answer
        the Horseshoe's discard gave, so nothing is destroyed), then the card
        draws its magnitude out of that same deck through the ordinary draw (see
        _draw_one_item). The first item drawn takes the square the recycled one
        gave up, so the board does not shuffle about under the player; the
        recycled item is a deck item again, so a draw may deal it straight back.

        A placed BLOCK is recycled as the item it was built from (the block
        comes off the board first, exactly as the end of a run takes it off),
        because a block and its item are one existence. The level's own props and
        enemies, and an offer the player has not bought, are refused — as is a
        deck with nothing in it to draw, where the card would be spent for
        nothing.
        """
        target = subject
        if isinstance(target, Block):
            if (getattr(target, "is_level_prop", False)
                    or getattr(target, "is_enemy", False)
                    or not self.owns_item(getattr(target, "source_item", None))):
                self._set_shop_message(
                    f"{action.name} needs one of your own items to recycle — kept")
                return False
            self._unplace_block(target)
            self.grid.pop((target.x, target.y), None)
            target = target.source_item
        elif target is None or not self.owns_item(target):
            self._set_shop_message(
                f"{action.name} needs one of your own items to recycle — kept")
            return False
        others = [item for item in self.drawable_deck_items()
                  if item is not target]
        if not others:
            self._set_shop_message(
                f"{action.name} needs an item in the deck to draw — kept")
            return False
        was = self._item_name(target)
        origin = self.item_cell(target)
        self._to_deck(target)
        drawn = []
        for index in range(max(0, int(action.amount))):
            item = self._draw_one_item(origin if index == 0 else None)
            if item is None:
                break
            drawn.append(self._item_name(item))
        drew = ", ".join(drawn) if drawn else "nothing"
        self._set_shop_message(
            f"{action.name} put {was} back in the deck and drew {drew}")
        sounds.play_mech()
        return True

    def _action_stormcloud(self, action, subject):
        """Stormcloud: a whole tool's reach, and a structure lost to the wind.

        User request: "add a card, 'stormcloud' (break, fix, dig, or reveal, and
        destroy 1 random structure. costs 1 energy)". It is the one action that
        opens a structure exactly as a tool would: it is aimed at one (see
        STRUCTURE_TARGET) and uses the first of its four verbs the structure
        answers, so any door can be opened with it (a golem still cannot — it
        wants a tool and two items, not weather). The reward REPLACES the
        structure on its square, as every opening's does (see _apply_tool).

        Then the storm brings one down: a random structure still standing — the
        one just opened is already off the board, so a card can never open and
        destroy the same door — is torn down through _consume_structure with
        discover=False, because a structure is revealed by OPENING it and this
        one never was (see _action_deep_pockets). With nothing else left
        standing, the opening still happens and says so. A golem, a structure
        the four verbs cannot open and a missing target are refused before
        anything is spent.
        """
        if not self.is_structure(subject):
            self._set_shop_message(
                f"{action.name} needs a structure to open — kept")
            return False
        verbs = Action.opens_with(action.value)
        verb = next((candidate for candidate in verbs
                     if Structure.result(subject.value, candidate) is not None),
                    None)
        if verb is None:
            self._set_shop_message(
                f"The {self._item_name(subject).lower()} cannot be broken, "
                f"fixed, dug or revealed — kept")
            return False
        kind, value = Structure.result(subject.value, verb)
        if kind == "merge":
            self._set_shop_message(
                f"The {self._item_name(subject).lower()} needs a tool and two "
                f"items, not a storm — kept")
            return False
        was = self._item_name(subject).lower()
        origin = self.item_cell(subject)
        reward = self._structure_reward(kind, value)
        self._consume_structure(subject)
        if origin is not None:
            self.set_item_cell(reward, origin)
        self._adopt_reward(reward)
        made = Pack.name(value) if kind == "pack" else Action.name(value)
        # The storm's own damage: structures still standing, chosen at random.
        torn = []
        for _ in range(max(0, int(action.amount))):
            standing = self.level_structures()
            if not standing:
                break
            victim = random.choice(standing)
            torn.append(self._item_name(victim).lower())
            self._consume_structure(victim, discover=False)
        message = (f"{action.name} {Verb.done(verb)} the {was} — {made}")
        if torn:
            plural = "" if len(torn) == 1 else "s"
            message += (f", and tore down the {', '.join(torn)} "
                        f"(structure{plural} gone for this level)")
        else:
            message += " — no other structure was left to tear down"
        self._set_shop_message(message)
        sounds.play_mech()
        return True

    def _action_floor_plans(self, action):
        """Floor plans: draw BLOCKS — five of them — out of the deck.

        User request: "add a new card, 'floor plans' (draw 5 blocks. costs 1
        energy)". Unlike the Lantern, which draws any item at all, this one
        deals only the ready-made BLOCKS waiting in the deck (see deck_blocks):
        what a run is built from, not the parts, cards, actions and tools a deck
        can also hold. The number is the card's own magnitude (see
        MAGNITUDES.FLOOR_PLANS_BLOCKS), so a golem-folded one draws ten.

        The blocks come out through the ordinary draw (see _draw_one_item with
        its own pool), so each takes an unlocked square of its own and a block
        the deck no longer has simply is not dealt; the draw stops when the deck
        has no blocks left. A deck with no block at all refuses the use and
        keeps the card, so the energy is never spent for nothing.
        """
        if not self.deck_blocks():
            self._set_shop_message(
                f"{action.name} needs a block in the deck to draw — kept")
            return False
        drawn = []
        for _ in range(max(0, int(action.amount))):
            item = self._draw_one_item(pool=self.deck_blocks())
            if item is None:
                break
            drawn.append(self._item_name(item))
        # Five of the same block reads as "5x Block" rather than five names.
        counts = {}
        for name in drawn:
            counts[name] = counts.get(name, 0) + 1
        names = ", ".join(name if count == 1 else f"{count}x {name}"
                          for name, count in counts.items()) or "nothing"
        self._set_shop_message(
            f"{action.name} drew {len(drawn)} block"
            f"{'' if len(drawn) == 1 else 's'}: {names}"
            + (" (the deck has no more blocks)" if len(drawn) < int(action.amount)
               else ""))
        sounds.play_mech()
        return True

    def _reroll_structure(self, structure, new_value):
        """Turn a structure into another one in place, and remember it.

        The ITEM is the same object: the square it stands on, the modifiers
        riding on it and the plan entry it came from are all untouched, so the
        board has nothing to rearrange. What the level's plan remembers is the
        ENTRY it became (see Game.structure_rerolls) — without that, the next
        layout pass (an R, a board edit, a T) would deal the structure the level
        authored all over again and quietly undo the reroll.

        Its switch goes off: the structure the player was pointing at is not the
        one standing there any more, so it must not be left selected for the
        next tool to fire at by accident.
        """
        structure.value = new_value
        structure.name = Structure.name(new_value)
        structure.price = Structure.PRICES.get(new_value, 0)
        index = getattr(structure, "plan_index", None)
        if index is not None:
            self.structure_rerolls[index] = new_value
        self._forget_item(structure)

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
        self._on_item_gained(token)
        left = "permanently" if runs_left is None else f"for {runs_left} run(s)"
        self._set_shop_message(
            f"{action.name} kept {Scorer.name(token.scorer)} from {name} {left}")
        sounds.play_mech()
        return True

    # -----------------------------------------------------------------------
    # Tools and structures: a structure is opened by using a tool on it.
    # -----------------------------------------------------------------------
    def _select_tool(self, tool):
        """Arm a tool as the actor: it is used on a structure with S.

        A tool works exactly like an action (user request: "Similarly to
        actions, items that can do these can be used on structures to turn them
        into something useful"): select the tool first, then the structure, and
        press S. Tools are never spent, so nothing is removed when one is used.
        """
        self._clear_active_selection()
        self.selected_toolbox_item = tool
        self.selected_toolbox_index = self._shown_index_of(tool)
        self.selected_tool = tool
        verbs = tuple(getattr(tool, "verbs", None) or (tool.verb,))
        self._set_shop_message(
            f"{tool.name} ({Keyword.line(tool)}) — click a structure to "
            f"{' or '.join(Verb.name(verb) for verb in verbs)}"
            f" ({getattr(tool, 'energy', 1)} energy, {self.energy} left)")

    def _clear_tool_selection(self, announce=True):
        """Deselect the armed tool, if any (its switches go off with it)."""
        tool = getattr(self, "selected_tool", None)
        self.selected_tool = None
        if tool is not None and self.is_item_selected(tool):
            self._unselect_item(tool, announce=announce)

    def is_structure(self, item):
        """True when ``item`` is a structure a tool can be used on.

        Kind only: a shelf offer is a structure too, and _apply_tool refuses
        one by name so the player is told to buy it rather than told there is
        nothing selected.
        """
        return getattr(item, "kind", None) == "structure"

    def level_structures(self):
        """The level's structures still standing, in board order.

        A structure belongs to the LEVEL (see Game._place_level_structures): it
        is one of the shop's free offers, flagged is_level_structure, and it is
        what a tool opens. This is the list "a random structure" is drawn from
        (Deep Pockets pulls one down) and the list a level's offer of four is
        counted against.
        """
        return [item for item in self.shop.items
                if getattr(item, "is_level_structure", False)]

    def _apply_tool(self, actor=None):
        """Use the armed tool on the selected structure (the S key).

        The tool is the actor and the structure is everything selected behind
        it, exactly like an action and its target: the tool needs exactly one
        structure, and if it has not got one NOTHING happens.

        A tool applies its VERBS in the order its table lists them and uses the
        first one its structure answers to, so a brick (break, dig) digs a pit
        and breaks a mirror, while a shovel only ever digs. A structure that
        answers to none of them is left alone and says so.

        An opening spends the TOOL's energy -- 1 for the four the player starts
        with, 0 for a brick -- and a refused one costs nothing at all. A tool
        whose keywords say CONSUME is destroyed by the opening, after the reward
        is in hand, and one that says DRAW deals its items on the way out (see
        _use_up_tool).

        Structures are FREE (user request): one the shelf is showing is opened
        where it lies, with nothing to buy first.
        """
        tool = getattr(self, "selected_tool", None)
        if tool is None or not self.owns_item(tool):
            self._set_shop_message("Select a tool first")
            return False
        targets = [t for t in self.selection
                   if t is not tool and self.is_structure(t)]
        if len(targets) != 1:
            self._set_shop_message(
                f"{tool.name} needs 1 structure — {len(targets)} selected")
            return False
        structure = targets[0]
        verbs = tuple(getattr(tool, "verbs", None) or (Tool.verb(tool.value),))
        verb = next((candidate for candidate in verbs
                     if Structure.result(structure.value, candidate) is not None),
                    None)
        if verb is None:
            self._set_shop_message(
                f"The {self._item_name(structure).lower()} cannot be "
                f"{' or '.join(Verb.done(candidate) for candidate in verbs)}")
            return False
        result = Structure.result(structure.value, verb)
        # Using a tool costs its own ENERGY (user request: "using any of
        # flashlight, screwdriver, shovel, or hammer consumes 1 energy"), and a
        # run only has MAX_ENERGY of it (see reset_run). A brick costs nothing,
        # which is exactly what makes a 0-energy opening possible. A use that is
        # refused above costs nothing: nothing happened, so nothing is spent.
        cost = getattr(tool, "energy", 1)
        if self.energy < cost:
            self._set_shop_message(
                f"Out of energy — {self.max_energy} a run, back at the next one")
            return False
        kind, value = result
        origin = self.item_cell(structure)
        if kind == "merge":
            # A golem does not hold a reward: it combines what the player brings
            # it (user request: "combine 2 of the same items to create 1 new item
            # with double the magnitude"). Everything is checked BEFORE the
            # energy is spent, so a refused combine costs nothing, and the
            # combined item keeps the square the golem gives up.
            pair = self._golem_pair(tool, structure, value)
            if pair is None:
                return False
            keep, absorb = pair
            self.energy -= cost
            self._consume_structure(structure)
            self._combine_items(keep, absorb)
            if origin is not None:
                self.set_item_cell(keep, origin)
            made = self._item_name(keep)
            swept = []
        else:
            made = Pack.name(value) if kind == "pack" else Action.name(value)
            # The reward REPLACES the structure (user request: "remove the
            # structure and put the reward in its place", the same way a bought
            # offer keeps the tile it was bought from -- see _unlock_offer): it
            # is built first, seated on the square the structure gives up, and
            # only then adopted, so the square is claimed before gaining an item
            # can deal it another (see _on_item_gained). The tool shapes what
            # comes out (see _structure_reward: a chisel's pack sizes, a gilding
            # cloth's tiers).
            # The neighbours a SWEEPING tool (the wrecking bar) also opens are
            # found BEFORE the target is spent: the squares are read from where
            # the target stands, and _consume_structure takes it off the board.
            sweep_targets = self._sweep_targets(tool, structure)
            reward = self._structure_reward(kind, value, tool)
            self.energy -= cost
            self._consume_structure(structure)
            if origin is not None:
                self.set_item_cell(reward, origin)
            self._adopt_reward(reward)
            # ...and they are opened for the one swing already paid for.
            swept = self._sweep_structures(tool, sweep_targets)
        message = (f"The {self._item_name(structure).lower()} is "
                   f"{Verb.done(verb)} — {made}")
        if swept:
            message += f", and with it {', '.join(swept)}"
        # What the tool leaves behind (a drill's dirt, a pickaxe's spark) joins
        # the deck, and "consume" destroys the one-shot tools that say so.
        message += self._make_tool_leftovers(tool)
        message += self._use_up_tool(tool)
        self._set_shop_message(message)
        sounds.play_mech()
        return True

    def _apply_modifier_tool(self, actor=None):
        """Use a tool that pours MODIFIERS onto one card (the vodka).

        User request: "add a tool, 'vodka': (select 1 card to give 3 stacks of
        'forgotten', consume. costs 1 energy)". The tool is the actor and the
        card is everything selected behind it: exactly one CARD, its own energy,
        the stacks its table names (Tool.MODIFIES), and then the tool is drunk
        (see _use_up_tool). A refused pour costs nothing at all.
        """
        tool = getattr(self, "selected_tool", None)
        if tool is None or not self.owns_item(tool):
            self._set_shop_message("Select a tool first")
            return False
        pour = Tool.modifies(tool.value)
        if pour is None:
            self._set_shop_message(f"{self._item_name(tool)} has nothing to pour")
            return False
        cards = [item for item in self.selection
                 if item is not tool and getattr(item, "kind", None) == "card"]
        if len(cards) != 1:
            self._set_shop_message(
                f"{self._item_name(tool)} needs 1 card — {len(cards)} selected")
            return False
        cost = getattr(tool, "energy", 1)
        if self.energy < cost:
            self._set_shop_message(
                f"Out of energy — {self.max_energy} a run, back at the next one")
            return False
        modifier, stacks = pour
        card = cards[0]
        self.energy -= cost
        Modifier.add(card, modifier, stacks)
        held = Modifier.stacks(card, modifier)
        message = (f"{self._item_name(card)} now has "
                   f"{Modifier.name(modifier)} ({held} "
                   f"stack{'' if held == 1 else 's'})")
        message += self._use_up_tool(tool)
        self._set_shop_message(message)
        sounds.play_mech()
        return True

    def _make_tool_leftovers(self, tool):
        """Leave what a tool MAKES in the player's DECK, and say so.

        User request: "add a tool, 'drill': (break, fix, dig, or reveal, but add
        'dirt' to your deck. costs 0 energy)" and "add a tool, 'pickaxe': (dig,
        make spark)". The by-product is built through the ordinary item door and
        put straight into the DECK (see _to_deck): it is not the opening's
        reward, it is what the tool carries with it, and it is revealed in the
        collection the first time one arrives.
        """
        made = Tool.makes(tool.value)
        if made is None:
            return ""
        (_kind, value), count = made
        names = []
        for _ in range(count):
            item = ToolItem(value)
            self.toolbox.add(item)
            self._to_deck(item)
            self._discover_tool_or_passive(item)
            names.append(self._item_name(item))
        return (f" (the {self._item_name(tool).lower()} left "
                f"{', '.join(names)} in your deck)")

    def _use_up_tool(self, tool):
        """Spend a tool whose keywords say consume: destroy it, then draw.

        Returns the note the opening's message ends with ("" for a tool that is
        never spent, which is the four the player starts with). The tool leaves
        through the ordinary discard door, so the run counts it as an item it
        threw away (the Trash Can card pays for those), and what it draws lands
        on the square it gave up -- the same courtesy a structure's reward gets.

        The question is the item's own keyword, not the tool's table: a one-shot
        tool that has been marked REUSABLE survives being used and keeps its
        draw (see components.Keyword.of), which is the same rule every used card
        follows.
        """
        if not Keyword.has(tool, Keyword.CONSUME) or not self.owns_item(tool):
            return ""
        name = self._item_name(tool)
        home = self.item_cell(tool)
        self._discard_item(tool)
        drawn = []
        for index in range(getattr(tool, "draws", 0)):
            item = self._draw_one_item(home if index == 0 else None)
            if item is None:
                break
            drawn.append(self._item_name(item))
        note = f" (the {name.lower()} is used up"
        if drawn:
            note += f", drew {', '.join(drawn)}"
        return note + ")"


    def _consume_structure(self, structure, discover=True):
        """The structure is spent when it opens: it leaves the board for good.

        A shelf structure is one of the shop's FREE offers, so it leaves the shelf
        with it: nothing of it may be left for the next layout pass to deal a new
        square to, and the next refresh deals new structures anyway.

        The square it was spent on is REMEMBERED for the level visit (see
        Game.spent_structures): laying the level out again — a board edit, an R, a
        T — must not put it back (user report: "if the player unlocks a structure
        using a tool, and then moves the tool, the structure will revert itself
        back into a locked state").

        ``discover`` is what opening a structure also does (see
        Game._discover_structure): a structure the player OPENED reveals its
        codex entry. A structure that was DESTROYED instead (Deep Pockets pulls
        one down without opening it) teaches nothing, so it passes False.
        """
        cell = self.item_cell(structure)
        if cell is not None:
            self.spent_structures.add((structure.value, cell[0], cell[1]))
        if getattr(structure, "is_bonus_structure", False):
            # A Picky structure is remembered by its own index as well, so the
            # layout pass that tops them up cannot deal it again this visit (see
            # Game._place_bonus_structures).
            self.spent_bonus_structures.add(structure.bonus_index)
        # Opening one is what reveals it in the collection (see
        # Game._discover_structure): the entry describes what the opening hands
        # over, so a player learns it by opening one.
        if discover:
            self._discover_structure(structure.value)
        self._forget_item(structure)
        if self.toolbox.contains(structure):
            self.toolbox.remove(structure)
        if structure in self.shop.items:
            self.shop.items.remove(structure)
            slot = self.shop.slot_key(structure)
            if slot in self.shop.locked:
                self.shop.locked.remove(slot)
        if cell is not None:
            self.set_item_cell(structure, None)
        self.assigned_toolbox_indexes.pop(structure, None)

    def _structure_reward(self, kind, value, tool=None):
        """The item a structure holds, built and NOT yet the player's.

        A pit hands over a pack of parts at a randomly rolled size (like any pack
        the shop sells, so a pit can be a small handful or a big one); a crystal
        pool and a mirror hand over the action their table names.

        The TOOL that opened it can shape what comes out (see Tool.AMOUNT_EFFECT):
        a chisel pushes the pack's size up the ladder, and a gilding cloth hands
        the reward over a QUALITY tier higher, so what the player keeps is worth
        more than the door usually gives.
        """
        if kind == "pack":
            size = random.choice(Pack.SIZE_ORDER)
            if Tool.amount_effect(getattr(tool, "value", None)) == "pack_size":
                size = Tool.bigger_pack_size(size, tool.amount)
            reward = self.shop._roll_pack(value, size)
        else:
            reward = ActionItem(value, Action.PRICES.get(value, 24))
        self._shape_reward_quality(reward, tool)
        return reward

    def _shape_reward_quality(self, reward, tool):
        """Tier a reward up when the opening tool says so (the gilding cloth).

        A pack's OPTIONS are what the player can keep, so each of them is what
        the cloth touches; a single-item reward (an action) is touched itself.
        """
        if Tool.amount_effect(getattr(tool, "value", None)) != "quality":
            return
        steps = getattr(tool, "amount", 0)
        for item in (list(getattr(reward, "options", ())) or [reward]):
            self._set_quality(item, Tool.better_quality(Quality.of(item), steps))

    def _sweep_structures(self, tool, targets):
        """Open the structures next to a sweeping tool's target; name what came out.

        The neighbours are opened exactly like the target was -- each reward takes
        the square its structure gave up and is adopted, each structure is spent
        for the level visit (see _consume_structure) and revealed in the
        collection -- and none of them costs energy: one swing is one price. The
        targets are found by _sweep_targets BEFORE the first structure is spent.
        """
        names = []
        for other, (kind, value) in targets:
            cell = self.item_cell(other)
            reward = self._structure_reward(kind, value, tool)
            self._consume_structure(other)
            if cell is not None:
                self.set_item_cell(reward, cell)
            self._adopt_reward(reward)
            names.append(Pack.name(value) if kind == "pack" else Action.name(value))
        return names

    def _sweep_targets(self, tool, structure):
        """The structures a sweeping tool opens alongside the one it was used on.

        A wrecking bar takes the whole neighbourhood with it (user request): every
        structure in the four squares around its target that answers one of the
        tool's verbs. A golem is skipped -- its opening is a MERGE of the
        player's own items, not a reward it can hand over unasked.
        """
        if not Tool.sweeps(getattr(tool, "value", None)):
            return []
        cell = self.item_cell(structure)
        if cell is None:
            return []
        verbs = tuple(getattr(tool, "verbs", None) or (Tool.verb(tool.value),))
        found = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            other = self.item_at_cell((cell[0] + dx, cell[1] + dy))
            if not self.is_structure(other):
                continue
            result = next((Structure.result(other.value, verb) for verb in verbs
                           if Structure.result(other.value, verb) is not None),
                          None)
            if result is None or result[0] == "merge":
                continue
            found.append((other, result))
        return found

    def _golem_pair(self, tool, structure, count):
        """The item a golem keeps and the ones it folds into it, or None.

        A golem's opening is the one structure result that is not a fixed
        reward: ``count`` (Structure.merge_count) of the player's OWN items are
        what it works on, so everything selected besides the tool and the golem
        is checked before anything is spent -- there must be that many, they must
        be the same item, they must be at the same TIER (see Quality: a golden
        item never folds with a plain one, and a diamond folds with nothing), and
        they must carry a magnitude, because a magnitude is the only thing the
        golem's answer is made of (two plain Rects would buy nothing). Returns
        (keep, absorb) or None, with the refusal said.
        """
        items = [item for item in self.selection
                 if item is not tool and item is not structure]
        if len(items) != count:
            self._set_shop_message(
                f"The golem combines {count} of the same item — "
                f"{len(items)} selected")
            return None
        keep, absorb = items[0], items[1:]
        for item in [keep] + absorb:
            if not (isinstance(item, Block) or self.owns_item(item)):
                self._set_shop_message("The golem combines your own items")
                return None
        for item in absorb:
            if not self._same_item(keep, item):
                self._set_shop_message(
                    f"The golem combines two of the SAME item — "
                    f"{self._item_name(keep)} and {self._item_name(item)} differ")
                return None
        # A golem's work is a TIER, not just a number (see Quality): two plain
        # items make a golden one and two golden items make a diamond (user
        # request: "combine two golden items into a diamond item"). So the pair
        # has to be in the same tier, and a diamond is final -- nothing is
        # combined out of it.
        quality = Quality.of(keep)
        for item in absorb:
            if Quality.of(item) != quality:
                self._set_shop_message(
                    f"The golem combines two items of the same quality — "
                    f"{self._item_name(keep)} and {self._item_name(item)} differ")
                return None
        made = Quality.combines_into(quality)
        if made is None:
            self._set_shop_message(
                f"{self._item_name(keep)} is a "
                f"{Quality.name(quality).lower()} item and cannot be combined "
                f"again")
            return None
        magnitudes = self._item_magnitudes(keep)
        if not magnitudes or not any(value for value in magnitudes.values()):
            self._set_shop_message(
                f"{self._item_name(keep)} has no magnitude to double")
            return None
        return keep, absorb

    def _same_item(self, first, second):
        """True when two items are the SAME item, so a golem may combine them.

        The kind and the value are the whole test for a component, an action or
        a card (two Lanterns, two +30 chip scorers); two blocks also have to be
        built the same way (shape, effects and scorer), and two actions have to
        be at the same version.
        """
        if first is second:
            return False
        if getattr(first, "kind", None) != getattr(second, "kind", None):
            return False
        if isinstance(first, Block) or isinstance(second, Block):
            if not (isinstance(first, Block) and isinstance(second, Block)):
                return False
            return (first.shape == second.shape
                    and tuple(first.effects) == tuple(second.effects)
                    and first.scorer == second.scorer)
        if getattr(first, "value", None) != getattr(second, "value", None):
            return False
        if getattr(first, "kind", None) == "action":
            return (getattr(first, "version", 1) == getattr(second, "version", 1))
        return True

    def _item_magnitudes(self, item):
        """Every magnitude an item carries, keyed by where it lives.

        ("scorer",) is a block's scorer amount, ("effect", value) one of its
        effect strengths, and ("amount",) the single number every other item
        carries -- the Lantern's draws, a +30 chip scorer's 30, a Concrete's 30
        chips (EVERY item has an amount; those with no magnitude of their own,
        a structure or a tool, carry 0 and so have nothing for a golem to
        double).
        """
        kind = getattr(item, "kind", None)
        if isinstance(item, Block) or kind == "block":
            values = {}
            scorer = getattr(item, "scorer", Scorer.NONE)
            if scorer not in (Scorer.NONE, Scorer.START, Scorer.FINISH):
                values[("scorer",)] = item.scorer_amount
            for effect in (getattr(item, "effects", ()) or ()):
                if Effect.MAGNITUDE.get(effect, 0):
                    values[("effect", effect)] = item.effect_magnitude(effect)
            return values
        amount = item.amount
        return {("amount",): amount} if amount else {}

    def _add_item_magnitudes(self, item, extra):
        """Add a magnitude map (see _item_magnitudes) to what ``item`` carries."""
        kind = getattr(item, "kind", None)
        if isinstance(item, Block) or kind == "block":
            for key, amount in extra.items():
                if key == ("scorer",):
                    item.scorer_amount = self._clean_amount(
                        item.scorer_amount + amount, 1.0)
                    continue
                effect = key[1]
                amounts = dict(getattr(item, "effect_amounts", None) or {})
                current = amounts.get(effect, Effect.MAGNITUDE.get(effect, 0))
                amounts[effect] = self._clean_amount(current + amount, 1.0)
                item.effect_amounts = amounts
            return
        item.amount = self._clean_amount(item.amount + extra.get(("amount",), 0),
                                        1.0)

    def _combine_items(self, keep, absorb):
        """Fold other items' magnitudes into one, then throw the others away.

        The golem's whole payoff: ``keep`` carries every item's numbers now (so
        two Lanterns make a Lantern of 4, two +30 chip scorers a +60 one), and
        what it was combined with leaves the game through the ordinary discard
        door. What is left is also a TIER higher (see Quality): the first fold
        makes it golden, the second a diamond — and because one fold doubles, a
        diamond ends up carrying 4x what the plain item did, exactly as the
        request asked ("combine two golden items into a diamond item, with 4x
        the magnitude of the original item").
        """
        for item in absorb:
            self._add_item_magnitudes(keep, self._item_magnitudes(item))
            self._discard_item(item)
        self._set_quality(keep, Quality.combines_into(Quality.of(keep)))

    def _set_quality(self, item, quality):
        """Mark an item with the tier a golem left it at, wherever it lives.

        A placed block and the inventory item it was built from are one
        existence (see _place_block_at), so the mark is written on both: a
        combine done on the board shows on the item when it is taken up again,
        and one done in hand shows on the block the item puts down.
        """
        if quality is None:
            return
        item.quality = quality
        source = getattr(item, "source_item", None)  # a block -> its item
        if source is not None:
            source.quality = quality
        cell = getattr(item, "placed_cell", None)    # an item -> its block
        if cell is not None:
            block = self.grid.get(cell)
            if block is not None and getattr(block, "source_item", None) is item:
                block.quality = quality

    def is_wasteful(self, item):
        """True when ``item`` is a block wearing the WASTEFUL effect.

        Wasteful is the one effect the PLAYER uses: it does nothing to the marble
        and everything to the build (see _use_wasteful).
        """
        has = getattr(item, "has_effect", None)
        return bool(has is not None and has(Effect.WASTEFUL))

    def _use_wasteful(self, actor=None):
        """Wasteful: throw this block and one other item away, draw a fresh item.

        User request: "add an effect, 'wasteful': can use this block to discard
        this block and a different item, and draw a new item." The block is the
        actor and ONE other selected item is what it takes with it: both leave the
        game for good (see _discard_item — no cash, no components back) and one
        random item is drawn from the deck onto the block's square, so the effect
        is a gamble on the deck rather than a free reroll. With the wrong number
        of items selected, or nothing left in the deck to draw, NOTHING happens
        and nothing is spent.
        """
        actor = self.selected_toolbox_item
        if not self.is_wasteful(actor):
            return False
        targets = [item for item in self.selected_targets() if item is not actor]
        if len(targets) != 1:
            self._set_shop_message(
                f"Wasteful throws away 1 other item — {len(targets)} selected")
            return False
        target = targets[0]
        if not self.owns_item(target) and not isinstance(target, Block):
            self._set_shop_message("Wasteful needs one of your own items to throw away")
            return False
        if not self.deck_items():
            self._set_shop_message("Wasteful needs an item in the deck to draw")
            return False
        origin = self.item_cell(actor)
        actor_name = self._item_name(actor)
        target_name = self._item_name(target)
        self._discard_item(target)
        self._discard_item(actor)
        drawn = self._draw_one_item(origin)
        self._set_shop_message(
            f"Wasteful threw away {actor_name} and {target_name} — drew "
            f"{self._item_name(drawn) if drawn is not None else 'nothing'}")
        sounds.play_mech()
        return True

    def _adopt_reward(self, item):
        """Take ownership of a structure's reward, which already holds its square.

        Cards and actions join their own lists and everything else the toolbox
        (the same doors a purchase uses, see _unlock_offer); an item that already
        stands on a square keeps it (see _on_item_gained).
        """
        if getattr(item, "kind", None) == "pack":
            self._adopt_pack(item)
        else:
            self._adopt_action(item)
