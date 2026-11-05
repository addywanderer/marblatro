"""Putting blocks on the board: placing, assembling, unplacing and erasing them."""

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


def _cell_label(cell):
    """A board square as the player reads it (column letter, then row number)."""
    x, y = cell
    return f"{chr(ord('A') + x)}{y + 1}"


class BuildMixin:
    """Putting blocks on the board: placing, assembling, unplacing and
    erasing them."""


    def _place_block_at(self, gx, gy):
        """Place (or move) the selected block onto the grid cell (gx, gy).

        Returns True when a block was placed. The click handler decides WHEN a
        drag means "place" (see _handle_mouse); this is the placement itself,
        kept a plain method so it can be called — and tested — directly.

        The board IS the inventory (user request: "remove the card, action, and
        inventory ui. move them all to the board"), so when the item in hand is
        not a block — a component, a card, an action — this MOVES it to the
        square instead (see _move_item_to): the player arranges their items on
        the board, and only blocks are physical (see Game.board_blocks).

        For a block it: swaps out whatever stood in the cell (returning it to the
        inventory), builds the block from the armed parts, stamps it with the
        price of the item it came FROM (so a sale, Death and Painting read what
        the player actually paid rather than a re-summed part total), carries
        over a RANDOM/LUCKY outcome and the remaining triggers the item already
        had for this run, hands out its triggers when it is a FRESH block (the
        Concert card's bonus included), keeps a portal in step with its partner,
        leaves the item in the inventory (marked with the square the block
        stands on — see BlockItem.placed_cell), relocates any laid-out item that
        was lying on the square, unsets the old cell when an already-placed block
        is moved, and clears the selection. It refuses a locked cell or nothing
        selected, so a direct call can never place a block where a click could
        not.
        """
        if not self.in_hand or self.is_cell_locked(gx, gy):
            return False
        item = self.selected_toolbox_item
        # A Block (picked up off the board) and a BlockItem are both blocks to
        # build; anything else is simply moved to the square.
        if not (isinstance(item, Block) or getattr(item, "kind", None) == "block"):
            return self._move_item_to(item, gx, gy)
        moving_placed = isinstance(item, Block)
        old = self.grid.get((gx, gy))
        # A block that stood in this cell leaves the board first — through the
        # same door erasing uses, so a block placed from the inventory goes back
        # to its own spot rather than being refunded as a second copy (see
        # _unplace_block).
        if old is not None and not (moving_placed and old is item):
            self._unplace_block(old)
        # Anything else lying on the square (a component, a card, an action) is
        # laid out somewhere else: it is scenery, the block has the square.
        for other in self.owned_items():
            if other is not item and self.item_cell(other) == (gx, gy):
                self.set_item_cell(other, None)
        self.grid[(gx, gy)] = Block(
            gx,
            gy,
            shape=self.selected_shape,
            effect=self.selected_effect,
            scorer=self.selected_scorer,
            scorer_amount=self.selected_scorer_amount,
            angle=self.current_block_angle,
            portal_number=getattr(item, "portal_number", 0),
            key_number=getattr(item, "key_number", 0),
            trigger_limit=getattr(item, "trigger_limit", 1),
            trigger_paid=getattr(item, "trigger_paid", 0),
            effects=getattr(item, "effects", None),
            effect_amounts=self.selected_effect_amounts,
        )
        # The placed block keeps its resale value, so erasing/refunding it later
        # returns the same price (a free, assembled-from-nothing wall is worth
        # $0, not the sum of its default parts).
        placed = self.grid[(gx, gy)]
        placed.resale_price = getattr(item, "resale_price", getattr(item, "price", None))
        if placed.resale_price is None:
            # A block with no stored price of its own (hand-built) gets one
            # materialized once, so it never drifts afterwards.
            block_resale_price(placed)
        # A block the player MOVED keeps the trial's mark on it (see
        # _carry_trial_mark): the block standing in the new cell is a new object
        # built from the selection, so the mark has to be handed over here —
        # BEFORE the trigger count below, which reads it (a Hands tied block is
        # debuffed by an identity test, see _trigger_limit).
        self._carry_trial_mark(item, gx, gy, placed)
        # A block the player ALREADY had keeps the RANDOM/LUCKY outcome it
        # rolled for this run: the roll belongs to the block they built, not to
        # the cell it happens to sit in, so picking a Random block up and
        # putting it down again must not reroll its reward (see
        # _run_random_result). Erasing a block and putting it back down goes
        # through the same door — the roll rides along on the toolbox item (see
        # _refund_block). A block that has not rolled yet carries nothing, and
        # an item from an earlier run carries a STALE roll: its tag makes the
        # next run roll it fresh like everything else.
        rolls = getattr(item, "random_rolls", None)
        if rolls is not None:
            placed.random_rolls = dict(rolls)
        # Placing a FRESH block is where its triggers are handed out, so a
        # block placed while Concert is owned arrives with its extra one (and a
        # block that never scores keeps its limit either way). MOVING a block —
        # or putting an erased one back down — is not a fresh placement: it
        # keeps the triggers it had left, so nudging a half-spent block around
        # the board cannot refill it. The carried count is clamped to the limit
        # the block has NOW (in case Concert went away in between), and starting
        # a run hands every block its triggers back anyway (see reset_run), so
        # the carried count only ever lives in the build state.
        limit = self._trigger_limit(placed)
        remaining = getattr(item, "triggers_left", None)
        placed.triggers_left = (limit if remaining is None
                                else max(0, min(int(remaining), limit)))
        # A placed portal inherits its partner's trigger count so the pair stays
        # in lockstep (e.g. both exhausted after one use).
        self._sync_portal_pair_triggers(placed, self.board_blocks())
        sounds.play_plop()
        # The block's spot in the inventory stays OCCUPIED by it (user request:
        # "when a block is placed on the board, make its spot in the inventory
        # still occupied with the block"). The item is NOT consumed: it keeps
        # its cell and remembers the square its block stands on, and the block
        # remembers the item. That pair is what keeps one item from fielding two
        # blocks — clicking the spot picks the block up (a move) instead of
        # arming a copy (see _toggle_item_selection) — and what lets erasing
        # the block make that same item placeable again (see _unplace_block).
        if (item is not None and getattr(item, "kind", None) == "block"
                and self.toolbox.contains(item)):
            item.placed_cell = (gx, gy)
            placed.source_item = item
        elif moving_placed:
            source = getattr(item, "source_item", None)
            if source is not None and self.toolbox.contains(source):
                placed.source_item = source
                source.placed_cell = (gx, gy)
        # Moving a placed block removes it from its original cell.
        if moving_placed and (item.x, item.y) != (gx, gy):
            self.grid.pop((item.x, item.y), None)
        # Putting the item down is the end of that switch's turn: it is off again
        # (the block it built stands on the board now), and every OTHER item the
        # player had switched on stays on.
        self._forget_item(item)
        return True

    # -----------------------------------------------------------------------
    # The board as the inventory: every owned item stands on a square, and one
    # selection rule (see _toggle_item_selection) selects it there.
    # -----------------------------------------------------------------------
    def _board_item_rect(self, gx, gy):
        """The screen rect of a board square (the one a block would stand in)."""
        x, y = self.cell_to_screen(gx, gy)
        return pygame.Rect(x, y, GRID_SIZE, GRID_SIZE)

    def _board_cell_of(self, item):
        """The (x, y) square ``item`` stands on, or None when it has none."""
        return self.item_cell(item)

    def _move_item_to(self, item, gx, gy):
        """Move an owned item that is not a block to another board square.

        Items live on the board already (see Game.ensure_board_cells), so the
        square the player clicks is where the item is put: a component can be
        laid out next to the piece it will be assembled with, a card can be moved
        out of the way, and nothing physical moves with it (only a Block is ever
        the marble's business — see Game.board_blocks). A square holding a block
        is refused, because the block is the thing standing there, and so is a
        LOCKED square: items only ever lie on squares the player has unlocked
        (user request: "make sure all items are always in an unlocked square").
        """
        if item is None or not self.toolbox.contains(item) and item not in (
                self.cards + self.actions + self.tokens) and not self.is_shop_offer(item):
            return False
        if self.is_cell_locked(gx, gy):
            self._set_shop_message(
                f"Locked square — buy a Board Unit "
                f"(${self._board_unit_price()}) to expand the board")
            return False
        if self.item_cell(item) == (gx, gy):
            # The square the item already lies on: nothing to move, and the
            # selection it was picked up with stays.
            return True
        if (gx, gy) in self.grid:
            self._set_shop_message("A block stands there already")
            return False
        occupant = self.item_at_cell((gx, gy))
        if occupant is not None and occupant is not item:
            self.set_item_cell(occupant, None)
        self.set_item_cell(item, (gx, gy))
        self.ensure_board_cells()
        cell = self.item_cell(item)
        # The item has been put down, so its own switch goes off; the items the
        # player switched on before it stay on.
        self._forget_item(item)
        if cell is None:
            self._set_shop_message(f"No room to move {self._item_name(item)}")
            return False
        self._set_shop_message(
            f"Moved {self._item_name(item)} to {_cell_label(cell)}")
        sounds.play_plop()
        return True

    def _selection_key(self, item):
        """The one entry that stands for ``item`` in the selection.

        An item whose block is standing on the board IS that block (see
        BlockItem.placed_cell / Block.source_item), so the BLOCK is what the
        selection holds: turning the switch on for either of them lights up the
        same switch, and no item can be "on" twice.
        """
        placed = getattr(item, "placed_cell", None)
        if placed is not None and not isinstance(item, Block):
            block = self.grid.get(tuple(placed))
            if block is not None:
                return block
        return item

    def actor(self):
        """The item that will be USED when the player acts: the first selected.

        The selection is a queue (user request: "make the first item selected be
        the one to be used up"): the head of it is the ACTOR — the item S applies,
        B sells and D upgrades — and everything behind it is a TARGET for the
        actor (see selected_targets).
        """
        return self.selection[0] if self.selection else None

    def selected_targets(self):
        """Every selected item except the actor: what the actor is aimed at."""
        return list(self.selection[1:])

    def required_targets(self, item=None):
        """How many targets ``item`` (the actor by default) needs, None = any.

        An action that acts on a piece needs exactly one target (see
        Action.needs_target) and a target-free action needs none; a component is
        assembled with whatever other parts were selected, so any number is fine;
        a block, a card or a token is applied by being put down rather than aimed,
        so it needs none.
        """
        actor = self.actor() if item is None else item
        kind = getattr(actor, "kind", None)
        if kind == "action":
            return 1 if Action.needs_target(actor.value) else 0
        if kind in (Component.SHAPE, Component.EFFECT, Component.SCORER):
            return None
        return 0

    def _refresh_actor(self):
        """Re-arm the selection: the FIRST selected item is the one in hand.

        Called after every switch flip. It never changes WHICH items are on — only
        which of them is the actor and what that actor is aimed at.
        """
        self._clear_active_selection()
        actor = self.actor()
        if actor is not None:
            self._select_in_hand(actor)
        self._sync_assigned_parts()
        self._sync_action_selection()

    def _sync_assigned_parts(self):
        """The parts the next assembly uses: every selected component.

        The selected components ARE the targets of a shape/scorer actor, so the
        assignment follows the selection rather than the other way round: a block
        has one shape and one scorer (the most recently selected of each wins) and
        any number of effects.
        """
        assigned = {}
        for item in self.selection:
            kind = getattr(item, "kind", None)
            if kind not in (Component.SHAPE, Component.EFFECT, Component.SCORER):
                continue
            if kind in (Component.SHAPE, Component.SCORER):
                for other in [c for c in assigned
                              if getattr(c, "kind", None) == kind]:
                    del assigned[other]
            assigned[item] = self._shown_index_of(item)
        self.assigned_toolbox_indexes = assigned

    def _sync_action_selection(self):
        """Keep the armed action and its subject in step with the selection.

        The actor is the action being used (if it is an action at all), and its
        subject is the FIRST target — which is what the gold outline marks. An
        action a PACK armed is not in the selection at all (it was never put on
        the board), so it stays armed and every selected item is its target.
        """
        pending = self.pending_pack_action
        if pending is not None:
            self.selected_action = pending
            targets = [t for t in self.selection if self.is_action_target(t)]
            self.selected_action_subject = targets[0] if targets else None
            return
        actor = self.actor()
        if getattr(actor, "kind", None) == "action":
            self.selected_action = actor
            targets = [t for t in self.selected_targets()
                       if self.is_action_target(t)]
            self.selected_action_subject = targets[0] if targets else None
        else:
            self.selected_action = None
            self.selected_action_subject = None

    def _toggle_item_selection(self, item):
        """Click an item: turn its switch ON, or OFF again.

        Selection is a bank of switches (user request: "each item acts as a
        switch that can be turned on and off, where 'on' means 'selected'"): every
        item keeps its own state, clicking one never changes another, and the
        player can have any number of them on at once. This is the ONE way an
        item is selected — a loose block, a block standing on the board, a
        component, a card, an action and a Spirit token all come through here,
        land in ``Game.selection``, and wear the same green frame, with a white
        inner frame on the one IN HAND (see ui.draw).

        The FIRST item switched on is the ACTOR — the one that is used up — and
        every item switched on after it is a target of that actor (user request:
        "make the first item selected be the one to be used up. assume all items
        selected other than the first one is a target item").

        What the actor then does:

        * a block — a loose one is armed so a click on a square builds it (see
          _equip_block), one already standing on the board is taken hold of so it
          can be moved (see _select_placed_block);
        * a component is assembled with the other selected parts (see
          _assemble_block);
        * an action is used on its targets with S (see _apply_action);
        * a card or a token is held as itself: a click on a square MOVES it (see
          _move_item_to), B sells it.

        Returns True when the item ended up ON.
        """
        if item is None:
            return False
        item = self._selection_key(item)
        if self.is_item_selected(item):
            return self._unselect_item(item)
        self.selection.append(item)
        self._refresh_actor()
        return True

    def _select_in_hand(self, item):
        """Arm ``item`` as the one IN HAND, doing what that kind of item does.

        The single counterpart to _refresh_actor: whatever the item is, this is
        what makes it the item a click on the board acts with, so the green frame
        and the next click always agree. It never switches anything else OFF.
        """
        kind = getattr(item, "kind", None)
        if not self.owns_item(item) and not isinstance(item, Block):
            # A shop offer: the player does not own it yet, so selecting it does
            # nothing but pick it up — it can be moved around the board like any
            # other item (user request), and bought by right-clicking it (see
            # InputMixin.handle_events).
            self._clear_active_selection()
            self.selected_toolbox_item = item
            self.selected_toolbox_index = None
            self._set_shop_message(
                f"{self._item_name(item)} — right-click to buy it for "
                f"${self._buy_price(item)}")
            return
        if isinstance(item, Block):
            self._select_placed_block(item)
        elif kind == "block":
            self._equip_block(item, self._shown_index_of(item))
        elif kind in (Component.SHAPE, Component.EFFECT, Component.SCORER):
            self._select_toolbox_component(item, self._shown_index_of(item))
        elif kind == "action":
            self._select_action(item)
        else:
            # A card (or a token): held as itself, so a click on a square moves
            # it there (see _move_item_to) and B sells it.
            self._clear_active_selection()
            self.selected_toolbox_item = item
            self.selected_toolbox_index = self._shown_index_of(item)
            self._set_shop_message(
                f"Selected {self._item_name(item)} — click a square to move it")

    def _consume_board_part(self, item):
        """Consume one component that stood on the board into an assembly.

        The piece leaves the board for good (it is part of the new block now), so
        it is not taken off the board and kept the way an item that merely moves
        is: it is dropped from the inventory entirely by the caller.
        """
        self.set_item_cell(item, None)
        self.selection = [other for other in self.selection if other is not item]
        if self.selected_toolbox_item is item:
            self._clear_active_selection()

    def _assemble_anchor_cell(self):
        """The board square an assembly of parts lands on, or None.

        The parts lie on the board, so the new block takes the square of the
        assigned SHAPE (a block looks like its shape), or the square of the first
        assigned piece when no shape was picked — as long as a BLOCK may stand
        there: a locked square is not playable (see _place_block_at), and one
        already holding a block belongs to that block. When no such square is
        free the block simply joins the inventory in hand, and the player puts it
        down where they want it, exactly like a bought block.
        """
        assigned = list(self.assigned_toolbox_indexes)
        on_board = [c for c in assigned if self.item_cell(c) is not None]
        if not on_board:
            return None
        shape = self.assigned_part(Component.SHAPE)
        cell = self.item_cell(shape) if shape is not None else None
        if cell is None:
            cell = self.item_cell(on_board[0])
        if cell is None or self.is_cell_locked(*cell) or cell in self.grid:
            return None
        return cell

    def _carry_trial_mark(self, item, gx, gy, placed):
        """Hand a trial's mark to the block the player has just put down.

        Hands tied and Crumbling pick board CELLS and remember the blocks they
        marked (see _roll_trial_decision / _apply_trial). Picking a marked block
        up would otherwise leave that mark behind twice over: its decided cell
        stayed on the square it left (marking whatever is put there next) while
        the block — a NEW object, rebuilt by _place_block_at from the selection —
        was not in the trial's sets at all, so a Crumbling block stopped
        shattering and a Hands tied block got its trigger back.

        Taking a block up carries the mark on the item (see _refund_block), and
        this puts it back where the block now stands: the decided cell moves with
        the block, the marked block in the trial's sets is swapped for the one
        now on the board, and the block's own fragility flag rides along. A block
        the trial never marked carries nothing, and neither does an item whose
        mark is spent (the sets are rebuilt from the board every run, see
        _apply_trial), so a fresh placement is left alone.
        """
        debuffed = item in self.trial_debuffed_blocks
        fragile = item in self.trial_fragile_blocks
        if not (debuffed or fragile):
            return
        decision = self.trial_decision
        cells = decision.get("cells") if decision else None
        source = ((item.x, item.y) if isinstance(item, Block)
                  else getattr(item, "trial_cell", None))
        if cells is not None and source is not None and source in cells:
            cells.discard(source)
            cells.add((gx, gy))
        if debuffed:
            self.trial_debuffed_blocks.discard(item)
            self.trial_debuffed_blocks.add(placed)
        if fragile:
            self.trial_fragile_blocks.discard(item)
            self.trial_fragile_blocks.add(placed)
        placed.trial_fragile = fragile

    def _set_scorer(self, scorer):
        self.selected_scorer = scorer
        self.selected_scorer_amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)

    def _set_shop_message(self, text):
        self.shop_message = text
        self.shop_message_timer = SHOP_MESSAGE_DURATION

    def _arm_block(self, item, index=None):
        """Make ``item`` the block IN HAND (see _equip_block).

        The in-hand block is what a click on the board places, what D upgrades
        and what B sells. ``index`` is the panel cell it sits in (None for a
        block that is on the board rather than in the inventory).

        A marked inventory item is a block that is ON the board (see
        _place_block_at), so the BLOCK is what gets armed: an item can never
        field a second copy of itself.
        """
        cell = getattr(item, "placed_cell", None)
        if cell is not None:
            block = self.grid.get(cell)
            if block is not None:
                item, index = block, None
        self.has_selected = True
        self.selected_toolbox_item = item
        if index is None:
            index = self._shown_index_of(item)
        self.selected_toolbox_index = index
        # A block the player can click in the panel is one of the SELECTED items
        # (see _toggle_item_selection), so the highlight and the next click's
        # toggle agree; a block lifted off the board is not in the inventory and
        # is in hand alone.
        if self.toolbox.contains(item) and not self.is_item_selected(item):
            self.selection.append(item)
        # A fragile block that shattered mid-run is stored with its original
        # shape, so moving it comes back as that shape instead of a permanent
        # Shape.NONE.
        self.selected_shape = (item._fragile_shape
                               if getattr(item, "_fragile_shape", None) is not None
                               else item.shape)
        self.selected_effect = item.effect
        self.selected_scorer = item.scorer
        self.selected_scorer_amount = item.scorer_amount
        # The equipped block's own effect strengths travel with the selection,
        # so placing it puts the same piston/black hole/conveyor on the board.
        self.selected_effect_amounts = dict(getattr(item, "effect_amounts", {}))
        # A block with a rotation of its OWN (one picked up from the board, or
        # one erased back into the toolbox) hands it to the build tool: placing
        # it down again then keeps the rotation it had instead of re-stamping
        # the tool's, and A rotates on from the block's own angle. A fresh shop
        # block has no angle of its own (see BlockItem.angle) and leaves the
        # tool's angle alone.
        own_angle = getattr(item, "angle", None)
        if own_angle is not None:
            self.current_block_angle = own_angle

    def _shown_index_of(self, item):
        """The inventory cell ``item`` sits in right now, or None.

        Matched by IDENTITY: two identical pieces are different items. The board
        highlights a piece by the square it lies on (see ui.draw), so the index
        is only kept for the callers that still pass one.
        """
        return next((index for index, shown in enumerate(self.toolbox.items)
                     if shown is item), None)

    def _equip_block(self, item, index=None):
        """Equip a block for placement.

        Selecting a block does NOT drop a half-built assembly any more: every
        selected item is its own switch (see _toggle_item_selection), so the
        components the player has switched on stay on. S still prefers an
        assembly when there are parts, and disassembles the block otherwise.
        """
        self._arm_block(item, index)
        self._set_shop_message(f"Selected {self._item_name(item)}")

    def _select_placed_block(self, block):
        """Hold a block that is standing on the board, ready to move it.

        The block joins the selection and becomes the item in hand — a switch
        turned on like any other (see _toggle_item_selection). Nothing else is
        switched off with it.
        """
        if not self.is_item_selected(block):
            self.selection.append(block)
        self._equip_block(block)

    # -----------------------------------------------------------------------
    # The inventory has no display of its own any more: every owned item stands
    # on the board (see Game.ensure_board_cells), so there is no page to turn,
    # no pop-up to open and nothing to discard.
    # -----------------------------------------------------------------------
    def _reshuffle_inventory(self):
        """Re-read the inventory. It is all on the board, so nothing moves.

        Using an action used to re-draw which part of the inventory the panel
        showed; now that the board shows all of it (see
        Game.ensure_board_cells) this only re-checks the layout and reports the
        portable items, which is what its callers ask for.
        """
        self.ensure_board_cells()
        return self.toolbox.items


    def _use_component(self, component, index=None):
        """Add one component to the block S will build, or drop it again.

        The component stays on its square (highlighted green) — it is only
        consumed when a block is actually assembled. A shape or a scorer takes
        its slot from whatever piece held it (a block has one of each, so a later
        piece replaces the earlier one), while an effect TOGGLES on and off, so a
        block can carry several. ``index`` is the inventory cell the piece used
        to sit in; the board highlights it by its own square now, so it is kept
        only because the panel-era callers pass it.

        In play a click goes through _toggle_item_selection instead, and the
        parts are re-derived from the whole selection (see _sync_assigned_parts);
        this helper assigns a single piece directly, which is what the tests use
        it for.
        """
        assigned = self.assigned_toolbox_indexes
        if component.kind in (Component.SHAPE, Component.SCORER):
            for other in [c for c in assigned if c.kind == component.kind]:
                del assigned[other]
            assigned[component] = index
        elif component in assigned:
            del assigned[component]
        else:
            assigned[component] = index
        kind_label = {Component.SHAPE: "Shape", Component.EFFECT: "Effect",
                      Component.SCORER: "Scorer"}.get(component.kind,
                                                     "Component")
        self._set_shop_message(
            f"{kind_label}: {component.name} — press S to assemble")

    def has_assigned_parts(self):
        """True when any component is assigned to the block S would build.

        Any combination assembles: a part that is not assigned becomes its free
        default (see _assemble_block).
        """
        return bool(self.assigned_toolbox_indexes)

    def assigned_part(self, kind):
        """The shape or scorer component assigned to the next block, or None.

        A block has one shape and one scorer, and _use_component keeps it that
        way (a later piece of the same kind replaces the earlier one), so there
        is at most one piece to find.
        """
        return next((c for c in self.assigned_toolbox_indexes
                     if c.kind == kind), None)

    def assigned_effects(self):
        """The effect components assigned to the next block, in click order."""
        return [c for c in self.assigned_toolbox_indexes
                if c.kind == Component.EFFECT]

    def _clear_assigned_parts(self):
        """Drop every component assigned to the next block.

        The pieces also leave the SELECTION (see _toggle_item_selection):
        a piece that is no longer part of the next block is not highlighted as
        though it were.
        """
        for comp in list(self.assigned_toolbox_indexes):
            self.selection = [item for item in self.selection if item is not comp]
        self.assigned_toolbox_indexes.clear()

    def _clear_active_selection(self):
        """Drop the item IN HAND, leaving the selected items themselves alone."""
        self.has_selected = False
        self.selected_toolbox_item = None
        self.selected_toolbox_index = None
        self.selected_shape = None
        self.selected_effect = None
        self.selected_scorer = None
        self.selected_scorer_amount = None
        self.selected_effect_amounts = {}

    def _clear_toolbox_selection(self):
        """Deselect EVERYTHING: the selected items, the one in hand, the action."""
        self.selection = []
        self._clear_active_selection()
        if (self.selected_action is not None
                and self.selected_action is not self.pending_pack_action):
            # An armed action is one of the selected items (see _select_action),
            # so dropping the selection drops it too. An action a PACK armed is
            # not on the board and stays armed until it is spent.
            self._clear_action_selection(announce=False)
        # A deselection also drops any pending card build (see the commented-out
        # `_build_card` below); the builder's state is commented out with the
        # conditions.
        # self.card_condition = None
        # self.card_scorer = None
        # self.card_builder_indexes.clear()

    def is_item_selected(self, item):
        """True when this item's switch is ON (see _toggle_item_selection).

        An item whose block is standing on the board answers for the BLOCK (see
        _selection_key), so the item and the block it became are one switch.
        """
        item = self._selection_key(item)
        return any(item is picked for picked in self.selection)

    def _selection_entry(self, item):
        """The exact entry in the selection that IS ``item`` (by identity), or None.

        Identity, not the canonical key: two identical components are different
        switches, and a block and the item that built it are one.
        """
        return next((picked for picked in self.selection if picked is item), None)

    def _unselect_item(self, item, announce=True):
        """Turn one item's switch OFF — the second click on it.

        Only this item changes: every other switch keeps the state it was in, and
        the first item still on becomes (or stays) the actor.
        """
        item = self._selection_entry(item) or self._selection_key(item)
        self.selection = [picked for picked in self.selection if picked is not item]
        self.assigned_toolbox_indexes.pop(item, None)
        if self.selected_action is item:
            # The action is no longer selected, so there is nothing left to aim.
            self._clear_action_selection(announce=False)
        if self.selected_toolbox_item is item:
            self._clear_active_selection()
        # The actor is always the first item still switched on (see _refresh_actor).
        self._refresh_actor()
        if announce:
            self._set_shop_message(f"Deselected {self._item_name(item)} "
                                   f"({len(self.selection)} selected)")
        return False

    def _forget_item(self, item, announce=False):
        """Switch an item OFF because it has left the player's ownership.

        Selling, banking, erasing, destroying and consuming all take an item out
        of the game, so its switch cannot outlive it — and no other item's switch
        is touched (user request: every item is its own switch). An item that was
        only held (never switched on) still lets go of the hand.
        """
        entry = self._selection_entry(item)
        if entry is not None:
            self._unselect_item(entry, announce=announce)
        elif self.selected_toolbox_item is item:
            self._clear_active_selection()
            self._refresh_actor()

    def prune_toolbox_selection(self):
        """Drop selected items the player no longer owns.

        The board shows everything the player owns (see Game.ensure_board_cells),
        so a selection only goes stale when an item leaves the inventory or the
        board runs out of squares for it: it stops being selected, and the item
        in hand moves to the most recently selected item left (or nothing is
        left in hand). A block lifted off the board is not inventory at all, so
        it is left alone.
        """
        owned = self.owned_items() + self.board_blocks()

        def visible(item):
            return any(item is owned_item for owned_item in owned)

        self.selection = [item for item in self.selection if visible(item)]
        active = self.selected_toolbox_item
        if active is not None and not visible(active):
            self._clear_active_selection()
            self._refresh_actor()
        return self.selection

    def _select_toolbox_component(self, component, index=None):
        """Make a component the item in hand — a part of the next assembly.

        A shape/effect/scorer click makes the piece part of the block S will
        build (see _sync_assigned_parts, which derives the parts from the whole
        selection rather than from this click). Only the item IN HAND moves: the
        components already selected stay selected and stay assigned, which is
        what lets a block be assembled from several pieces.
        """
        self._clear_active_selection()
        self.selected_toolbox_item = component
        if index is None:
            index = self._shown_index_of(component)
        self.selected_toolbox_index = index
        if self.toolbox.contains(component) and not self.is_item_selected(component):
            self.selection.append(component)
        # COMMENTED OUT with the conditions: a Condition component started the
        # card builder here, and a Scorer picked while a condition was assigned
        # paired with it instead of the next block. Both are commented out
        # below (see _build_card).
        #
        # pairing_scorer = (component.kind == Component.SCORER
        #                   and self.card_condition is not None)
        # kept_condition = self.card_condition if pairing_scorer else None
        # kept_index = (self.card_builder_indexes.get(kept_condition)
        #               if kept_condition is not None else None)
        # if component.kind == Component.CONDITION:
        #     # Starting the card builder clears any pending block assembly so S
        #     # can't mix the two halves.
        #     self._clear_assigned_parts()
        #     self.card_condition = component
        #     self.card_scorer = None
        #     self.card_builder_indexes = {component: index}
        #     self._set_shop_message(
        #         f"Condition: {component.name} — now pick a scorer, then press S")
        #     return
        # if pairing_scorer:
        #     self.card_condition = kept_condition
        #     self.card_scorer = component
        #     self.card_builder_indexes = {kept_condition: kept_index, component: index}
        #     self._set_shop_message(
        #         f"Scorer: {component.name} — press S to build the card")
        #     return
        # The assigned pieces are re-derived from the whole selection, so the
        # board lights up exactly the components the next block is built from
        # (the actor first, its targets behind it).
        self._sync_assigned_parts()
        kind_label = {Component.SHAPE: "Shape", Component.EFFECT: "Effect",
                      Component.SCORER: "Scorer"}.get(component.kind,
                                                     "Component")
        self._set_shop_message(
            f"{kind_label}: {component.name} — press S to assemble")

    # -----------------------------------------------------------------------
    # COMMENTED OUT with the conditions (user request: "comment out all the code
    # for conditions"): the card builder. A card was built by assigning a
    # Condition component and a Scorer component in the toolbox and pressing S;
    # both were consumed and the (condition x scorer) card joined the card area.
    # Every card is whole and unsplittable now, so there is nothing to build —
    # the two components no longer exist (the condition is gone, and a scorer
    # assigned in the toolbox goes to the next block as it always did).
    #
    # def _build_card(self):
    #     """Combine the assigned condition + scorer into a card (press S).
    #
    #     Only pairs that describe a real card build (see
    #     components.condition_scorer_card): collision conditions pair with any
    #     card scorer, and each named condition recreates its whole card (or, for
    #     the magnitude conditions, a new custom card). The two components are
    #     consumed from the toolbox and the card joins the card area.
    #     """
    #     condition = self.card_condition
    #     if condition is None:
    #         return
    #     scorer = self.card_scorer
    #     if scorer is None:
    #         self._set_shop_message(
    #             f"Pick a scorer for {condition.name} (then press S)")
    #         return
    #     value = condition_scorer_card(condition.value, scorer.value)
    #     if value is None:
    #         self._set_shop_message(
    #             f"{condition.name} + {Scorer.name(scorer.value)} don't form a card")
    #         return
    #     # Duplicates are blocked unless the player owns the Showman card.
    #     # Ownership (not effect) is what matters here: a card disabled for the
    #     # run is still owned, so it cannot be built a second time.
    #     if self._owns_card(value) and not self._has_card(Card.SHOWMAN):
    #         self._set_shop_message("Already own this card")
    #         return
    #     if len(self.cards) >= self.max_cards:
    #         self._set_shop_message(f"Card area is full ({self.max_cards} cards)")
    #         return
    #     # Consume the two halves from the toolbox and clear the builder.
    #     for c in (condition, scorer):
    #         if c in self.toolbox.items:
    #             self.toolbox.remove(c)
    #     self._clear_toolbox_selection()
    #     # The built card keeps the scorer piece's own magnitude, so building a
    #     # card is not a way to launder a weak roll into the average card (or the
    #     # reverse): what the piece pays for is what the card pays.
    #     self.cards.append(make_card_item(value, amount=scorer.amount))
    #     self._discover_owned_card(value)
    #     self._set_shop_message(f"Built card: {Card.name(value)}")
    #     sounds.play_coin()

    def _assemble_block(self):
        """Combine the assigned components into a block.

        Uses the assigned shape, scorer, and any toggled effect components (all
        highlighted green on the board), then consumes them into the new block,
        which joins the inventory and is equipped. A part that is NOT assigned
        becomes its free default — the Rect shape, no effect, or no scorer — so
        any combination of parts (even none at all) assembles: a lone +Chips
        scorer makes a plain Rect +Chips block, and S with nothing selected makes
        a plain wall. A Portal effect or a Key/Lock shape assembles a PAIR of
        blocks (both halves share a fresh pairing number, exactly like a bought
        pair).

        The block is built WHERE the parts were laid out (see
        _assemble_anchor_cell): it takes the square of the shape (or else of the
        first assigned piece) and the pieces are consumed from the board — that
        is the whole point of laying components out on it.
        """
        anchor = self._assemble_anchor_cell()
        shape_piece = self.assigned_part(Component.SHAPE)
        scorer_piece = self.assigned_part(Component.SCORER)
        effect_pieces = self.assigned_effects()
        consumed = [c for c in (shape_piece, scorer_piece, *effect_pieces)
                    if c is not None]
        # Missing parts become the free defaults: Rect shape, no effect, no scorer.
        effects = [e.value for e in effect_pieces]
        # Each effect piece carries its own rolled magnitude (a 1350 px/s piston,
        # a 2100 px/s one): the assembled block keeps it, so what the player
        # bought is what the block does.
        amounts = {e.value: e.amount for e in effect_pieces
                   if getattr(e, "amount", 0)}
        shape = shape_piece.value if shape_piece is not None else Shape.RECT
        # The other half of a Key/Lock pair (None for every other shape).
        pair_shape = paired_shape(shape)
        scorer = scorer_piece.value if scorer_piece is not None else Scorer.NONE
        amount = scorer_piece.amount if scorer_piece is not None else 0
        name = f"{Shape.name(shape)} {Scorer.name(scorer)}"
        price = self._assemble_price()
        # Consume the assigned components: a piece is part of the new block now,
        # so it leaves the board for good (see _consume_board_part).
        for c in consumed:
            self._consume_board_part(c)
            self.toolbox.remove(c)
        self._clear_assigned_parts()
        if Effect.PORTAL in effects:
            # A portal block is assembled as a pair sharing a fresh number.
            number = next_portal_number()
            item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                             portal_number=number, effects=effects,
                             effect_amounts=amounts)
            self.toolbox.add(item)
            self.toolbox.add(BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                                       portal_number=number, effects=effects,
                                       effect_amounts=amounts))
            self._finish_assembly(item, anchor)
            self._set_shop_message(f"Assembled {name} (portal pair #{number})")
            sounds.play_mech()
            return
        if pair_shape is not None:
            # A Key/Lock block is assembled as a matched pair sharing a fresh
            # key number: both halves carry the same effects and scorer, one
            # drawn as the Key and one as the Lock.
            number = next_key_number()
            item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                             key_number=number, effects=effects,
                             effect_amounts=amounts)
            self.toolbox.add(item)
            self.toolbox.add(BlockItem(0, 0, pair_shape, Effect.NONE, scorer, amount, price,
                                       f"{Shape.name(pair_shape)} {Scorer.name(scorer)}",
                                       key_number=number, effects=effects,
                                       effect_amounts=amounts))
            self._discover_component(Component.SHAPE, pair_shape)
            self._finish_assembly(item, anchor)
            self._set_shop_message(f"Assembled {name} (key/lock pair #{number})")
            sounds.play_mech()
            return
        item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                         effects=effects, effect_amounts=amounts)
        self.toolbox.add(item)
        self._finish_assembly(item, anchor)
        self._set_shop_message(f"Assembled {name}")
        sounds.play_mech()

    def _finish_assembly(self, item, anchor):
        """Hand an assembled block to the player, on the board when it was built there.

        ``anchor`` is the square the block's parts were laid out on (see
        _assemble_anchor_cell), or None when no square there could hold a block:
        the block then simply joins the inventory in hand. Either way the block
        is IN HAND afterwards — the one just built is the one the player is
        holding, so the next click can move it.
        """
        self._equip_block(item)
        if anchor is not None:
            self._place_block_at(*anchor)
            block = self.grid.get(anchor)
            if block is not None:
                self._select_placed_block(block)

    def _assemble_price(self):
        """The resale value of an assembled block: 75% of its chosen parts.

        Each part is priced at the CATALOG price for its kind, never for the
        magnitude it rolled (see block_price_for), so an assembled block is
        worth what its parts are worth however well they rolled. The free
        defaults (Rect shape, no effect, no scorer) add nothing, so a block
        assembled from nothing is worth $0 and can't be sold for profit.
        """
        total = 0
        shape_piece = self.assigned_part(Component.SHAPE)
        scorer_piece = self.assigned_part(Component.SCORER)
        if shape_piece is not None:
            total += COMPONENT_PRICES.get((Component.SHAPE, shape_piece.value),
                                          0)
        for e in self.assigned_effects():
            total += effect_component_price(e.value)
        if scorer_piece is not None:
            total += scorer_component_price(scorer_piece.value)
        return int(total * 0.75)

    def _refund_block(self, block):
        """Return a removed block to the toolbox as a block (not components).

        The returned block keeps the RANDOM/LUCKY outcome it had already rolled
        for this run and the triggers it had left (see _place_block_at /
        _run_random_result): erasing a block and putting it back down is a move,
        not a chance to roll its reward or refill its triggers again. Both are
        tagged by the run (the roll) or re-handed by it (the triggers, see
        reset_run), so a block that sits in the toolbox while the next run
        starts arrives fresh. Its own ROTATION and the mark the trial put on it
        (see _carry_trial_mark) ride along too, so putting the block down again
        is a move in those respects as well.
        """
        # A fragile block that shattered is stored with its original shape, so
        # erasing/replacing it returns that shape instead of a Shape.NONE.
        shape = block._fragile_shape if getattr(block, "_fragile_shape", None) is not None else block.shape
        name = f"{Shape.name(shape)} {Scorer.name(block.scorer)}"
        # Refund the block's stored resale value (placed blocks carry the price
        # of the toolbox item they came from), so a free default wall stays
        # worth $0 instead of being repriced from its free parts.
        price = block_resale_price(block)
        item = BlockItem(0, 0, shape, Effect.NONE, block.scorer,
                         block.scorer_amount, price, name,
                         portal_number=getattr(block, "portal_number", 0),
                         key_number=getattr(block, "key_number", 0),
                         trigger_limit=getattr(block, "trigger_limit", 1),
                         trigger_paid=getattr(block, "trigger_paid", 0),
                         effects=block.effects,
                         effect_amounts=getattr(block, "effect_amounts", None),
                         angle=getattr(block, "angle", 0))
        # The block becomes a portable item again, lying on the square it stood
        # on (the board is the inventory: there is nowhere else for it to go).
        self.set_item_cell(item, (block.x, block.y))
        rolls = getattr(block, "random_rolls", None)
        if rolls is not None:
            item.random_rolls = dict(rolls)
        remaining = getattr(block, "triggers_left", None)
        if remaining is not None:
            item.triggers_left = int(remaining)
        # A block the trial marked hands its mark to the toolbox item the same
        # way (the marked block in the trial's sets becomes the item), with the
        # cell it stood in, so putting it back down puts the mark where the block
        # now stands instead of leaving it on the square it was taken from (see
        # _carry_trial_mark). Nothing is carried for a block the trial never
        # marked, and the sets are rebuilt from the board every run (see
        # _apply_trial), so a mark cannot outlive the run it belongs to.
        if (block in self.trial_debuffed_blocks
                or block in self.trial_fragile_blocks):
            item.trial_cell = (block.x, block.y)
            for group in (self.trial_debuffed_blocks, self.trial_fragile_blocks):
                if block in group:
                    group.discard(block)
                    group.add(item)
        self.toolbox.add(item)

    def _drop_placed_copy(self, item):
        """An item left the inventory: the block it put on the board goes too.

        A placed block keeps the inventory spot it came from (see
        _place_block_at), so the two are one existence. Selling, banking,
        sacrificing or disassembling the item must not leave an orphaned block
        on the board — that block could later be erased into a second copy of
        something the player no longer owns.
        """
        cell = getattr(item, "placed_cell", None)
        if cell is None:
            return
        item.placed_cell = None
        block = self.grid.get(cell)
        if block is None or getattr(block, "source_item", None) is not item:
            return
        self.grid.pop(cell, None)
        # The block's switch goes off with it (it is the same existence as the
        # item that just left), so no selection outlives the board.
        self._forget_item(block)
        if block.scorer == Scorer.START:
            self.marbles = [m for m in self.marbles
                            if getattr(m, "start_block", None) is not block]

    def _release_block_item(self, block):
        """A block that leaves the board for good takes its item with it.

        A placed block keeps the inventory item it was built from (see
        _place_block_at): the two are one existence. So a block that is SOLD,
        disassembled, sacrificed or destroyed has to take that item out of the
        inventory too — otherwise the item lingers as a ghost: still owned, still
        marked as placed, drawn nowhere and clickable nowhere, and the square it
        still claims is never given to another item. Worse, erasing a square
        something else later stands on would refund the ghost as a second copy of
        a block the player no longer had (user report: glitches with several
        copies of one item).

        A block with no item of its own (one an older save restored, or one an
        effect put down) has nothing to take.
        """
        source = getattr(block, "source_item", None)
        if source is None:
            return
        block.source_item = None
        source.placed_cell = None
        if self.toolbox.contains(source):
            # Taking the item out of the inventory is the ordinary door: the
            # toolbox's own hook clears the item's square (see _drop_placed_copy).
            self.toolbox.remove(source)
        self.assigned_toolbox_indexes.pop(source, None)
        self._forget_item(source)

    def _unplace_block(self, block):
        """Take a block off the board and give it back to the inventory.

        A block placed from the inventory never left it (see _place_block_at),
        so its item is still sitting in its own spot: the item simply becomes
        placeable again, taking back the state the board block built up (its
        RANDOM/LUCKY roll, the triggers it has left, its rotation and any mark
        the trial put on it). A block with no spot of its own — a save written
        before blocks kept one, or a block another effect put down — is refunded
        into the inventory the way it always was (see _refund_block).

        An ORPHAN block — one whose item has already left the player's ownership
        (see _release_block_item) — is refunded to nobody: giving it back would
        hand out a second copy of something the player no longer owns.
        """
        source = getattr(block, "source_item", None)
        if source is not None and self.toolbox.contains(source):
            self._restore_item_from_block(block, source)
        elif block.source_item is None:
            self._refund_block(block)

    def _restore_item_from_block(self, block, item):
        """Hand a board block's state back to the inventory item it came from.

        Most of the item's own fields never changed (it is the block's source),
        so only what the BOARD built up is brought back: the rotation the player
        turned it to, a fragile block's original shape, this run's RANDOM/LUCKY
        outcome, the triggers it has left, and the trial mark (Hands tied /
        Crumbling track the block itself, so the mark moves back to the item
        with the cell it now stands in — see _carry_trial_mark).
        """
        item.placed_cell = None
        if getattr(block, "_fragile_shape", None) is not None:
            item.shape = block._fragile_shape
            block._fragile_shape = None
        item.angle = getattr(block, "angle", getattr(item, "angle", None))
        rolls = getattr(block, "random_rolls", None)
        if rolls is not None:
            item.random_rolls = dict(rolls)
        remaining = getattr(block, "triggers_left", None)
        if remaining is not None:
            item.triggers_left = int(remaining)
        if (block in self.trial_debuffed_blocks
                or block in self.trial_fragile_blocks):
            item.trial_cell = (block.x, block.y)
            for group in (self.trial_debuffed_blocks, self.trial_fragile_blocks):
                if block in group:
                    group.discard(block)
                    group.add(item)

    def _erase_block_at(self, grid_x, grid_y):
        """Remove a block from the board and give it back as a portable block.

        Only a BLOCK is the eraser's business: the other items on the board (a
        component, a card, an action) are scenery the player arranges by moving
        it, so erasing one leaves it where it is.
        """
        standing = self.item_at_cell((grid_x, grid_y))
        if standing is not None and not isinstance(standing, Block):
            self._set_shop_message(
                f"{self._item_name(standing)} stays where it is — only blocks "
                f"can be taken up")
            return False
        block = self.grid.pop((grid_x, grid_y), None)
        if block is not None:
            # A block the player was holding (see _select_placed_block) has left
            # the board, so its switch goes off with it: leaving it on would let
            # the player place it again while its inventory copy lies on the
            # board — the same block fielded twice. Nothing else is switched off.
            self._forget_item(block)
            # The item the block came from is still in the inventory, so it
            # simply becomes placeable again (see _unplace_block); a block with
            # no item of its own is refunded as a new one.
            self._unplace_block(block)
            if block.scorer == Scorer.START:
                # Erasing a start block removes the marble released from it.
                self.marbles = [m for m in self.marbles if getattr(m, "start_block", None) is not block]
