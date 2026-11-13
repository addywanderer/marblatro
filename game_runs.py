"""A run: starting one, the trial it plays under, its score, the marble-box fire
and the gondolas that slide across the board."""

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
    PROP_PARTS,
    Structure,
    Trial,
    block_price_for,
    level_for,
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
from enemies import Enemy
from items import StructureItem
from marble import Marble, _configure_marble_type
from physics import PhysicsEngine
from shop import Shop
from toolbox import Toolbox


class RunsMixin:
    """A run: starting one, the trial it plays under, its score, the
    marble-box fire and the gondolas on the board."""


    def reset_run(self, choose_trial=True):
        if self.game_over or self.awaiting_after_run:
            return False
        starts = [block for block in self.board_blocks()
                  if block.scorer == Scorer.START]
        if not starts:
            return False

        # A fresh run leaves a fresh trail (old dots are discarded).
        self.trail_particles = []
        self.run_active = True
        self.run_complete = False
        self.run_cleared = False
        # A run that starts is no place to still be choosing cards from the
        # deck: an Eyeball pick armed before it is dropped with its overlay (the
        # ACTION is untouched — nothing was spent on a pick that never drew).
        self.deck_pick_action = None
        self.deck_pick_left = 0
        self.deck_shown = False
        # The run's BASE score (chips x mult): every marble this run releases is
        # seeded from it, and a payoff paid while no marble exists (a card that
        # fires at the start of the run) moves it. The live score lives on the
        # marbles themselves (see the score_chips / score_mult properties).
        base_chips = RUN_BASE_CHIPS
        base_mult = RUN_BASE_MULT
        # Permanent metagame upgrades (bought with dice on the title screen's
        # UPGRADES tab) apply at the start of every run: +chips, +mult, and an
        # xMult multiplier. A save can turn these off on the marble-selection
        # screen (upgrades_enabled), defaulting to on.
        if self.upgrades_enabled:
            base_chips += metagame.chip_bonus()
            base_mult += metagame.mult_bonus()
            xmult = metagame.xmult_bonus()
            if xmult != 1.0:
                base_mult = base_mult * xmult
        self._score_marble = None
        self._base_chips = base_chips
        self._base_mult = base_mult
        # Any marble left over from the previous run is cleared BEFORE the
        # start-of-run payoffs below, so those payoffs move the base score
        # rather than a stale marble's.
        self.marbles = []
        # The run's own dice are reset here, so replaying the run (R, T, a
        # retry) rolls the same luck it had the first time round instead of a
        # fresh set (see run_rng / _choose_trial). This has to happen BEFORE the
        # trial and the random-output rolls below, which draw on it.
        self.run_rng.seed(self.run_seed)
        # The trial is chosen BEFORE the run starts (see _choose_trial, called
        # at game start and after each run); starting the run applies its
        # effects to the current board. Restarts, board edits, and retries keep
        # the already-applied trial — and its decided random picks — so neither
        # the trial nor what it debuffs can be rerolled by replaying the run.
        if choose_trial and self.trials_enabled:
            self._apply_trial()
        # A fresh run starts with no armed Quick cards, no pending Cash-card
        # cash and no banked Parts components; cards that fire at the start of
        # the run (below) arm/earn right after this.
        self.armed_quick.clear()
        self.card_cash_run_gain = 0
        self.parts_run_gain = 0
        # A fresh run starts with no cash earned by Cash/Lucky scorer blocks
        # yet (it accumulates as the run's blocks trigger) — but this run
        # already PAID that cash into the wallet as it triggered, so the money
        # comes back out along with the counter. Restarting the run (R),
        # starting a fresh one (T), and editing the board mid-run all discard
        # the run, so none of them may leave behind what the discarded run was
        # paid. Money already spent is not clawed back: the wallet never goes
        # below $0 (the same rule the Fresh rerolls below follow).
        self.cash = max(0, self.cash - self.run_cash_gained)
        self.run_cash_gained = 0
        # Fresh run: no resource points earned yet (Shreds/Rubble/Ideas/Picky
        # only become banked rewards after a run; see _continue_run). Cleared
        # BEFORE the start-of-run cards fire below.
        self.shred_run_gain = 0
        self.rubble_run_gain = 0
        self.idea_run_gain = 0
        self.option_run_gain = 0
        # Fresh run: it has not granted any free rerolls yet — and the rerolls
        # THIS run's Fresh hits already banked come back off the bank, for the
        # same reason the scorer cash above does: the discarded run did not
        # earn them. A reroll already spent is not un-spent (the bank simply
        # can't go below zero), and a run that was COMMITTED rather than
        # restarted has its counter cleared by _continue_run, so this rollback
        # only ever touches a run that is being thrown away.
        self.free_rerolls = max(0, self.free_rerolls - self.free_rerolls_run_gain)
        self.free_rerolls_run_gain = 0
        # The Reroll cards that run dealt come off the board for the same
        # reason (see _spawn_reroll_cards): the discarded run did not earn them.
        self._take_back_run_rerolls()
        # The inventory slots THIS run's Packed blocks won come back off the
        # total for the same reason: the discarded run did not earn them. They
        # are kept once the run is continued (see _continue_run), so a committed
        # run's slots are never clawed back here.
        self.inventory_slots_won = max(0, self.inventory_slots_won
                                       - self.inventory_slots_run_gain)
        self.inventory_slots_run_gain = 0
        # Fresh run: no xMult banked yet. This bank holds what the xMult CARDS
        # and multiplier tokens leave behind (a scorer pays its xMult with the
        # touch that fires it and never banks, see _apply_xmult_now), and the
        # finish path multiplies the multiplier by it once, as the run settles
        # (see _apply_xmult / _flush_run_xmult). Grace's v1 bonus is part of the
        # run's bank from the first frame (see run_xmult_bonus), so a run
        # started after the action carries it too.
        #
        # This has to be set BEFORE the start-of-run cards below: a card that
        # pays xMult at the start of a run (Stencil) banks it into this product,
        # and a later assignment would silently drop everything the cards paid.
        self.run_xmult_pending = 1.0 + self.run_xmult_bonus
        # Cards grant their score effects at the start of each run (e.g. Joker
        # gives +4 mult), so they apply right after the mult resets to 1. A
        # card disabled by the Card cutter trial is skipped. Every random
        # OUTPUT scorer (Lucky, Random) also picks its result for this run
        # here, before anything can trigger, so retrying the run replays the
        # same outcome (see _roll_run_random_outputs). Resetting to build state
        # after a board edit or a retry (choose_trial False) keeps the run's
        # already-chosen results.
        if choose_trial:
            self._roll_run_random_outputs()
        self._apply_cards()
        # ...and every UNPLAYABLE item the player owns pays its start-of-run
        # payoff at the same moment (user request: the passive Concrete).
        self._apply_passive_items()
        self.run_time = 0.0
        # Fresh run: no black-hole pull time has accumulated yet (astronaut).
        self.black_hole_time = 0.0
        # Fresh run: no time inside blocks or inside locked board units has
        # accumulated yet (intangible), and none inside a locked unit with the
        # phase effect off either (matrix).
        self.inside_block_time = 0.0
        self.inside_locked_time = 0.0
        self.inside_locked_no_phase_time = 0.0
        # Fresh run: no Fragile Breaks (Wrecking Ball) gains earned yet. They
        # only become permanent after a run.
        self._reset_wrecking_run_gain()
        # Fresh run: no air time has accumulated yet (plane).
        self.air_time = 0.0
        # Fresh run: no board unit has been visited yet (Explorer). The marble
        # records the unit it is in every frame (see _note_visited_cell).
        self.visited_cells = set()
        # Fresh run: no Drill-scorer locked squares earned yet.
        self.drill_run_units = 0
        # Fresh run: the TOOLS are back to full energy (user request: "energy
        # resets to max each run"). Every use of a tool spends one (see
        # _apply_tool), so this is what makes opening structures a per-run
        # decision, and restarting or retrying a run gives the same budget back
        # — the run being thrown away did not keep what it spent.
        self.energy = self.max_energy
        # Fresh run: no blocks destroyed yet (Undertaker) and no Debt block has
        # cancelled the run's interest yet.
        self.run_blocks_destroyed = 0
        self.debt_run_triggered = False
        # Fresh run: nothing has been thrown away yet, so the Trash Can card
        # starts the run paying nothing (see _discard_item).
        self.discarded_items_run = 0
        # Fresh run: the Procrastination rewinds have not been spent yet. The
        # marbles below are newly built, so their motion-history deques start
        # empty too — a new run can never rewind into the last one's past.
        self.procrastination_rewinds = 0
        # Fresh run: no Rally touches, no previous-contact block for Echo, no
        # primed Bomb blocks yet, and no opening blocks remembered for
        # Pedestal/Watch.
        self.run_fresh_touches = 0
        self.run_first_blocks = []
        self._prev_contact_block = None
        self.bomb_cells = set()
        # Fresh run: no pipe streak in progress and no completed streaks yet.
        # A streak is the run of FRESH contacts that are PIPE-GROUP blocks (see
        # _count_pipe_streak): its completed groups of three are what the
        # Fountain whole card pays +0.25 xMult for.
        self.pipe_streak_blocks = []
        self.pipe_streak_run_units = 0
        # Fresh run: the type bonus counts only the types touched THIS run.
        self.touched_shapes = set()
        self.touched_effects = set()
        self.touched_scorers = set()
        # Fresh run: per-type counts of distinct touch events, used only by the
        # repeats-only trial (a type contributes to uniqueness once touched
        # twice). Incremented on fresh contacts in _handle_block_contacts.
        self.touch_shape_counts = {}
        self.touch_effect_counts = {}
        self.touch_scorer_counts = {}
        # Fresh run: no block has been contacted yet (Effective Start/End
        # condition cards inspect the run's first/last contacted block).
        self._first_contact_block = None
        self._last_contact_block = None
        self._last_contact_air = 0.0
        # The speed of the marble at that last fresh contact, so an
        # end-condition Quick card can measure the run's final block hit (there
        # is no NEXT block after the run for the usual Quick payoff to arm on).
        self._last_contact_speed = 0.0
        # Fresh run: every scoring block gets its triggers back — its own limit
        # plus the Concert card's bonus, or one fewer for the blocks Hands tied
        # debuffed (see _trigger_limit) — rotating blocks
        # return to their base angle (continuous spin reset to 0), and fragile
        # blocks that shattered are rebuilt to their original shape.
        for block in self.board_blocks():
            block.triggers_left = self._trigger_limit(block)
            # A cable car starts every run back on its own cell, facing the way
            # its arrow points (see _reset_gondola).
            if block.has_effect(Effect.GONDOLA):
                self._reset_gondola(block)
            # A portal pair's travel budget refills each run (see
            # PORTAL_MAX_ACTIVATIONS): 100 travels are allowed per run.
            if block.has_effect(Effect.PORTAL):
                block.portal_uses_left = PORTAL_MAX_ACTIVATIONS
            if block.has_effect(Effect.ROTATE):
                block.spin = 0.0
                block._refresh_geometry()
            if block._fragile_shape is not None:
                block.shape = block._fragile_shape
                block._fragile_shape = None
            # Every Lock closes again at the start of each run, so the marble
            # must reach its Key again this run (see _unlock_matching_locks).
            block.locked = block.shape == Shape.LOCK
        # Picky's permanent structures are rolled fresh for this run (user
        # request: "a permanent new random structure generated every run"), so
        # each run is offered a different one. It has to happen BEFORE the level
        # is laid out below, which is what puts them on the board.
        self._reroll_bonus_structures()
        # The level is put back BEFORE the marble exists (user request: "load the
        # level beforehand"), so the run starts on the board the player has been
        # building on: its squares are opened, its props are rebuilt on their own
        # cells, its enemies come back to theirs at full health and its
        # structures stay where they stand (see _begin_level — a level is planned
        # once, when it becomes current, and never re-decided here). A level is
        # won by clearing its enemies while getting every marble to the Finish —
        # there is no score target any more.
        self._begin_level()
        # (self.marbles was already cleared at the top of the run, before the
        # start-of-run payoffs, so they landed on the base score.) The marble is
        # released HERE, which is what starting a run means (user request:
        # "create a marble only when the player presses t to start the run").
        for start_block in starts:
            self._release_start_marble(start_block)
            # The Doppelganger whole card releases a second marble from every
            # Start block, drifting sideways so the two do not overlap from
            # the first frame. Both must reach the FINISH before the run ends.
            if self._has_card(Card.DOPPELGANGER):
                self._release_start_marble(start_block, vx=DOPPELGANGER_START_VX)
        # Spirit tokens fire once at the start of each run they still cover,
        # after the marbles exist (the scorer path reads the run's marble).
        self._apply_tokens()
        return True

    def _discard_run(self):
        """Go back to building: the run in flight is thrown away with its marble.

        User request: "create a marble only when the player presses t to start
        the run. delete the marble when the run is reset." A marble lives exactly
        as long as the run it is playing: reset_run releases it, and every path
        that resets the board back to the build phase — R, a retry, unlocking a
        square, moving an item about — takes it away again, so the build phase
        never shows a marble nobody is playing with.
        """
        self.marbles = []
        self.run_active = False

    # --- levels ---------------------------------------------------------

    def current_level(self):
        """The Level this run plays (a run IS a level; see components.LEVELS)."""
        return level_for(self.run_number)

    def live_enemies(self):
        """Every enemy still standing on the board."""
        return [block for block in self.board_blocks()
                if getattr(block, "is_enemy", False) and block.alive]

    def _begin_level(self):
        """Lay out the level this run plays: its squares, props, structures and cast.

        User request: "load the level beforehand instead of when the game
        updates so that the level does not appear to change randomly." A level is
        laid out when it becomes the current one — a brand-new game (see
        _reset_board_to_start) and the CONTINUE that advances to the next run
        (see _continue_run) — and starting a run only puts that same layout BACK:
        the props go on their own offsets, the enemies come back to their own
        squares at full health and the structures keep the squares they stand on
        (see _place_level_props / _place_level_enemies / _place_level_structures).
        Nothing here reads the board to decide where things go, so the level the
        player builds against is the level they play.
        """
        level = self.current_level()
        # A DIFFERENT level replaces everything the previous one laid out; the
        # SAME level (a run start, a retry, a load) keeps what is standing, so
        # nothing about it can move.
        same_level = getattr(self, "level_number", None) == level.number
        if not same_level:
            # A level that is only now being laid out owes its full cast of
            # structures: the ones the last level spent were the last level's,
            # and so were the ones it rerolled into something else.
            self.spent_structures = set()
            self.spent_bonus_structures = set()
            self.structure_rerolls = {}
        self.level_number = level.number
        self.enemies_defeated = 0
        self._open_level_region(level.cells)
        self._place_level_props(level)
        self._place_level_structures(level, keep=same_level)
        self._place_level_enemies(level, keep=same_level)

    def _open_level_region(self, cells):
        """Unlock the board squares this level opens up.

        ``cells`` are the level's own squares, offset from the centre square of
        the board (see components.Level), so each level pre-unlocks a different
        SHAPE of board. A level only ever UNLOCKS squares: anything already
        unlocked (an earlier level's squares, a Board Unit the player bought)
        stays unlocked.
        """
        for dx, dy in cells:
            cell = (GRID_WIDTH // 2 + dx, GRID_HEIGHT // 2 + dy)
            if 0 <= cell[0] < GRID_WIDTH and 0 <= cell[1] < GRID_HEIGHT:
                self.unlocked_cells.add(cell)
        self._board_walls_dirty = True

    def _level_cell(self, dx, dy):
        """The board square a level's offset lands on."""
        return (GRID_WIDTH // 2 + dx, GRID_HEIGHT // 2 + dy)

    def _player_cells(self):
        """The squares the PLAYER's own things stand on — never the level's.

        A level lays itself out against this, so its furniture and its cast never
        land on something the player built, and the player's build never pushes
        them about: the level's plan is its own offsets, and it is only ever
        filled IN, never re-decided (user request: "load the level beforehand
        ... so that the level does not appear to change randomly"). Counting the
        level's own blocks here is what used to make the second layout move
        everything.
        """
        cells = set()
        for item in self.owned_items():
            cell = self.item_cell(item)
            if cell is not None:
                cells.add(cell)
        for cell, block in self.grid.items():
            if (getattr(block, "is_level_prop", False)
                    or getattr(block, "is_enemy", False)):
                continue
            cells.add(cell)
        return cells

    def _player_block_cells(self):
        """The squares the player's own BLOCKS stand on (their items aside).

        A structure is placed on its level's own square whatever item happens to
        lie there — an item is scenery and takes another square on the next
        layout pass — but never on a block the player built, which is why this is
        the narrower question (see _place_level_structures).
        """
        return {cell for cell, block in self.grid.items()
                if not getattr(block, "is_level_prop", False)
                and not getattr(block, "is_enemy", False)}

    def _place_level_props(self, level):
        """Build the blocks the level places for the player.

        A level's props are its own furniture -- walls, bouncers, accelerators to
        climb with, phase blocks, slopes, shelves, a key and its lock. They are
        not the player's: they cannot be selected, taken up or sold (see
        _erase_block_at), and they are REBUILT on their own squares whenever the
        level is put back, so a broken or bombed one comes back exactly where it
        was. Their square is the level's own offset and never the board's state,
        so laying the level out twice cannot move it; only a square the PLAYER
        has built on is left to the player.
        """
        for cell in [cell for cell, block in self.grid.items()
                     if getattr(block, "is_level_prop", False)]:
            del self.grid[cell]
        taken = self._player_cells()
        for marker, dx, dy in level.props:
            cell = self._level_cell(dx, dy)
            if cell not in self.unlocked_cells or cell in taken:
                continue
            parts = PROP_PARTS.get(marker)
            if parts is None:
                continue
            block = Block(cell[0], cell[1],
                          shape=parts.get("shape", Shape.RECT),
                          effects=parts.get("effects"),
                          angle=parts.get("angle", 0),
                          key_number=parts.get("key_number", 0))
            block.is_level_prop = True
            self.grid[cell] = block
            taken.add(cell)

    def _place_level_structures(self, level, keep=True):
        """Put the level's structures on the board, where its plan puts them.

        A structure is part of the LEVEL now (user request: "add structures as
        part of the level"): a pit, a crystal pool or a mirror stands on one of
        the level's own squares, wears no padlock and costs nothing, and a tool
        opens it where it lies (see Game._apply_tool). Every run clears the
        previous level's structures and lays out this level's own.

        The level offers STRUCTURES_PER_RUN of them (user request: "have 4
        structures each run instead of 1"), so a square the player has already
        built on does not shrink the offer: the structure moves to the free
        square nearest the one the level picked. A structure the level ALREADY
        has keeps the square it stands on — the plan is filled in, never
        re-decided — so starting or retrying a run cannot shuffle them.

        A structure the player REROLLED is the plan's own entry in another
        shape (see Game.structure_rerolls): the plan deals what the reroll made
        of it, so the reroll survives every later layout pass exactly as an
        opened structure's absence does.
        """
        rerolled = getattr(self, "structure_rerolls", None) or {}
        planned = [(index, rerolled.get(index, value), dx, dy)
                   for index, (value, dx, dy)
                   in enumerate(level.structure_spawns)]
        still_needed = {}
        for _index, value, _dx, _dy in planned:
            still_needed[value] = still_needed.get(value, 0) + 1
        # What the level already has stays, and takes one of its plan's entries;
        # anything over belongs to a level (or a run) that is over. A structure
        # Picky put out is not the level's to count: it has its own plan (see
        # _place_bonus_structures).
        kept = []
        for item in [item for item in self.shop.items
                     if getattr(item, "is_level_structure", False)
                     and not getattr(item, "is_bonus_structure", False)]:
            if keep and still_needed.get(item.value, 0) > 0:
                still_needed[item.value] -= 1
                kept.append(item)
                continue
            if item in self.shop.items:
                self.shop.items.remove(item)
            self.set_item_cell(item, None)
            self._forget_item(item)
        # The structures Picky generated for this run keep their squares too.
        bonus_cells = {self.item_cell(item) for item in self.shop.items
                       if getattr(item, "is_bonus_structure", False)}
        taken = (self._player_block_cells()
                 | {self.item_cell(item) for item in kept}
                 | {cell for cell in bonus_cells if cell is not None})
        for index, value, dx, dy in planned:
            if still_needed.get(value, 0) <= 0:
                continue
            still_needed[value] -= 1
            cell = self._level_cell(dx, dy)
            # A structure the player has already OPENED this level visit stays
            # gone, wherever it stood: laying the level out again (a board edit,
            # an R, a T) must not hand out another pack (user report: moving the
            # tool used to put the structure back).
            if self._structure_is_spent(value, cell):
                continue
            if cell not in self.unlocked_cells or cell in taken:
                cell = self._free_level_cell(level, taken, dx, dy)
                if cell is None:
                    continue
                if self._structure_is_spent(value, cell):
                    continue
            # The structure's square is the level's, but the item standing on it
            # is the PLAYER's: it steps aside to another square rather than
            # being pushed into the deck, exactly like an item a block is built
            # or a structure is moved over (a tool that vanished into the deck
            # was a bug, not a layout).
            for other in self.owned_items():
                if self.item_cell(other) == cell:
                    self._seat_aside(other, cell)
            item = StructureItem(value, Structure.PRICES[value])
            item.is_level_structure = True
            # Which entry of the level's plan this is: a reroll (see
            # Game._action_reroll) rewrites that entry rather than moving the
            # structure, so the layout pass below keeps dealing what the reroll
            # made of it.
            item.plan_index = index
            # The structure stands on the square its LEVEL picked (user request:
            # "make structures be placed in different areas of the level, instead
            # of always at the top"). It has to be the item's BOARD SQUARE, not
            # its shelf col/row: those are the shop's drawing cells, and an item
            # with no board square is laid out by the next ensure_board_cells in
            # reading order -- which is the top of the board.
            self.set_item_cell(item, cell)
            self.shop.items.append(item)
            taken.add(cell)
        # ...and Picky's permanent structures stand alongside the level's own.
        self._place_bonus_structures(level, taken)

    def _reroll_bonus_structures(self):
        """Roll this run's Picky structures: one random structure per point.

        User request: "make the 'picky' scorer reward a permanent new random
        structure generated every run instead of a new 'shop slot'." The COUNT
        (``bonus_structures``) is permanent — one per whole Picky point banked —
        while the structure itself is NEW every run, which is what the old bonus
        shop slot did with an offer. Called at the start of a run, before the
        level is laid out, so the roll lands on the board the player then builds
        against and nothing in the run can reshuffle it.
        """
        count = max(0, int(getattr(self, "bonus_structures", 0)))
        self.bonus_structure_values = [
            random.choice(Structure.ORDER) for _ in range(count)]

    def _refresh_bonus_structures(self):
        """Top this run's Picky structures up after another one is banked.

        A Picky point that converts mid-run (a resource pack can bank the last
        half of one — see Game._convert_banked_points) buys a structure for the
        run being played as well as for every run after it, so the plan grows by
        one value and the board is topped up at once. The full re-roll still
        happens at the start of the next run (see _reroll_bonus_structures).
        """
        while len(getattr(self, "bonus_structure_values", [])) < int(
                getattr(self, "bonus_structures", 0)):
            self.bonus_structure_values.append(random.choice(Structure.ORDER))
        taken = set(self._player_block_cells())
        for item in self.shop.items:
            cell = self.item_cell(item)
            if cell is not None and getattr(item, "is_level_structure", False):
                taken.add(cell)
        self._place_bonus_structures(self.current_level(), taken)

    def _place_bonus_structures(self, level, taken):
        """Put this run's Picky structures on the board, next to the level's own.

        They are the player's REWARD rather than the level's furniture, but they
        live in the same place (a free square of the level, standing free and
        opened with a card like any other structure — see Game._apply_tool), so
        they are marked ``is_level_structure`` too: nothing refunds them, nothing
        sells them, and the level's own layout passes leave them alone. What
        marks them apart is ``is_bonus_structure``, so the level's plan never
        counts them against its own four and a re-roll can replace them.

        One that already stands where its plan entry put it is KEPT, so an
        unlock, a board edit, an R or a load cannot move it: only the run's own
        re-roll (see _reroll_bonus_structures) changes what is standing. One the
        player has already OPENED this visit stays gone (see
        Game.spent_bonus_structures), exactly as an opened level structure does.
        """
        values = list(getattr(self, "bonus_structure_values", []))
        count = max(0, int(getattr(self, "bonus_structures", 0)))
        # The plan must be exactly as long as the permanent count: a save from
        # before this reward (or a test that set only the count) has no values,
        # and an old count may have left extras behind.
        while len(values) < count:
            values.append(random.choice(Structure.ORDER))
        del values[count:]
        self.bonus_structure_values = list(values)
        spent = getattr(self, "spent_bonus_structures", set())
        standing = [item for item in list(self.shop.items)
                    if getattr(item, "is_bonus_structure", False)]
        # Keep the ones that still match the plan, in order; everything else
        # (an extra from an old count, or one the re-roll replaced) goes.
        kept = []
        for index, value in enumerate(values):
            match = next((item for item in standing
                          if getattr(item, "bonus_index", None) == index
                          and item.value == value), None)
            if match is not None:
                kept.append(match)
                standing.remove(match)
                continue
        for item in standing:
            if item in self.shop.items:
                self.shop.items.remove(item)
            self.set_item_cell(item, None)
            self._forget_item(item)
        placed = {getattr(item, "bonus_index", None) for item in kept}
        for index, value in enumerate(values):
            if index in placed or index in spent:
                continue
            cell = self._free_level_cell(level, taken, 0, 0)
            if cell is None:
                # The level has no square left: the structure waits for a run
                # with room rather than being forced onto the player's build.
                continue
            for other in self.owned_items():
                if self.item_cell(other) == cell:
                    self._seat_aside(other, cell)
            item = StructureItem(value, Structure.PRICES[value])
            item.is_level_structure = True
            item.is_bonus_structure = True
            item.bonus_index = index
            self.set_item_cell(item, cell)
            self.shop.items.append(item)
            taken.add(cell)

    def _structure_is_spent(self, value, cell):
        """True when this structure was already opened on this square.

        The level visit's record of spents is `(value, x, y)` (see
        Game.spent_structures / _consume_structure): a structure is a thing the
        player OPENED, not a reward to be re-dealt by the next layout pass.
        """
        return (value, cell[0], cell[1]) in self.spent_structures

    def _free_level_cell(self, level, taken, dx, dy):
        """The free square of a level closest to (dx, dy), or None if it has none.

        Used when a structure's own square is already spoken for, so the run
        still gets the four structures it is owed. An enemy's square is never
        used either: a structure standing where its level's cast has to spawn
        would push an enemy -- and its share of the level's health -- off the
        board.
        """
        reserved = {(ex, ey) for _, ex, ey in level.enemy_spawns}
        best = None
        for level_cell in sorted(level.cells, key=lambda cell: (cell[1], cell[0])):
            if level_cell in reserved:
                continue
            cell = self._level_cell(*level_cell)
            if cell not in self.unlocked_cells or cell in taken:
                continue
            distance = abs(level_cell[0] - dx) + abs(level_cell[1] - dy)
            if best is None or distance < best[0]:
                best = (distance, cell)
        return None if best is None else best[1]

    def _place_level_enemies(self, level, keep=True):
        """Put the level's enemies on their own squares, at full health.

        Each enemy has its own square, so a level can put one at the top of the
        board and another at the bottom, and every level's cast sits somewhere
        different. An enemy whose square the level does not open is BURIED in the
        wall (see components.Level): it is drawn there, and the marble can only
        reach it once the player buys that square or phases into it.

        An enemy already standing on its own square is RESET rather than rebuilt
        (see Enemy.reset), so laying the level out again — the start of a run, a
        retry — puts the same enemy back on the same square with its whole share
        of health instead of re-deciding where the cast goes.

        The level's health is the SCORE its run used to require -- the target the
        game asked for before levels replaced it (user request: "make the sum of
        all enemies' health equal to the total required score that was originally
        there"). That total is split between the enemies that actually reach the
        board by kind, so a level's enemies always add up to exactly the run's
        target however many of them there are.
        """
        planned = []
        for kind, dx, dy in level.enemy_spawns:
            cell = self._level_cell(dx, dy)
            if not (0 <= cell[0] < GRID_WIDTH and 0 <= cell[1] < GRID_HEIGHT):
                continue
            planned.append((kind, cell))
        # An enemy that no longer belongs to this level leaves the board, and the
        # ones that do are kept as they are (they are about to be reset).
        planned_cells = {cell for _kind, cell in planned}
        for cell in [cell for cell, block in self.grid.items()
                     if getattr(block, "is_enemy", False)]:
            if cell not in planned_cells:
                del self.grid[cell]
        taken = self._player_cells()
        enemies = []
        for kind, cell in planned:
            enemy = self.grid.get(cell) if keep else None
            if enemy is not None and getattr(enemy, "is_enemy", False):
                if enemy.kind != kind:
                    del self.grid[cell]
                    enemy = None
            if enemy is None:
                if cell in taken:
                    continue
                enemy = Enemy(cell[0], cell[1], kind)
                self.grid[cell] = enemy
            enemies.append(enemy)
        health = level.enemy_health(self._level_health_budget(),
                                    [enemy.kind for enemy in enemies])
        for enemy, hp in zip(enemies, health):
            enemy.max_hp = hp
            enemy.reset()

    def _level_health_budget(self):
        """The damage a level asks for in total: the run's required score.

        The score target is still computed and kept for every run (see
        _refresh_run_target): it is what the run's trial scales (Sky High
        doubles it, Grace v2 drops it to 0) and what the cash award measures the
        run's score against, so reading the level's health off it keeps the two
        in step -- a doubled target is a level with twice the health.
        """
        return max(0, int(getattr(self, "required_score", 0) or 0))

    def _update_enemies(self, dt):
        """Let every enemy on the board move for a frame.

        Enemies are handed the unlocked squares, so a moving enemy keeps to the
        board the player can actually reach: it turns round at the edge of its
        room instead of sliding over locked squares.
        """
        for block in self.board_blocks():
            if getattr(block, "is_enemy", False):
                block.step(dt, self.marbles, self.unlocked_cells)

    def _particle_amount_text(self, amount):
        """Format a scored amount for a popup: whole numbers plain, floats trimmed."""
        if float(amount).is_integer():
            return str(int(amount))
        return f"{amount:.2f}".rstrip("0").rstrip(".")

    def _spawn_score_particle(self, x, y, text, color):
        """Spawn a floating score popup at a screen position."""
        self.score_particles.append(
            ScoreParticle(x, y, text, color, self.font))

    def _spawn_block_particle(self, block, text, color):
        """Spawn a score popup jumping out of the middle of a block."""
        self._spawn_score_particle(block.rect.centerx, block.rect.centery, text, color)

    def _spawn_card_particle(self, card, text, color, block=None):
        """Spawn a card's single score popup for one score-affecting event.

        Each card emits exactly one particle per event. When a card's modifier
        is tied to a block (the marble touching or near it), the popup appears
        near that block; otherwise it appears on the owned card itself, which
        lies on a board square (see Game.ensure_board_cells).
        """
        if block is not None:
            self._spawn_score_particle(block.rect.centerx, block.rect.centery, text, color)
            return
        self.ensure_board_cells()
        cell = self.item_cell(card)
        if cell is None:
            self._spawn_score_particle(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2,
                                       text, color)
            return
        rect = self._board_item_rect(*cell)
        self._spawn_score_particle(rect.centerx, rect.centery, text, color)

    def _choose_trial(self, next_run=None):
        """Set the trial the given run is played under, before the run starts.

        ``next_run`` is the run being set up (the one after the finished run by
        default). The difficulty decides how many of a round's runs play a
        trial, and they are the round's LAST runs (see
        Difficulty.TRIALS_PER_ROUND): difficulties 1-2 give only a round's
        final run a trial, difficulty 3 its last two runs, and difficulty 4
        every run of the round (the game's original balance). The trial itself
        is drawn fresh per run, exactly as it always was. A run with no trial
        is played clean — the display reads NO TRIAL — though the player can
        still buy one onto it (see _click_trial_display). The shapes a trial
        carries are applied to the board when the run begins (see _apply_trial).

        The run being set up also gets its own random seed here (``run_seed``),
        which every run-scoped decision derives from — the trial's own picks and
        the run's in-play dice — so a run replays identically instead of
        rerolling its luck (see _roll_trial_decision and Game.run_rng). The seed
        belongs to the RUN, so pressing R/T, retrying the run and editing the
        board all keep it; only setting a run up afresh (this method) or buying
        a different trial re-seeds it.
        """
        if next_run is None:
            next_run = self.run_number + 1
        if next_run % RUNS_PER_ROUND < self.trials_without_trial_runs:
            self.current_trial = None
        else:
            self.current_trial = random.choice(Trial.ORDER)
        self.run_seed = random.randrange(1 << 31)
        self.run_rng = random.Random(self.run_seed)
        # The trial's own random picks belong to the trial that was just chosen.
        self.trial_decision = None

    @property
    def trials_without_trial_runs(self):
        """How many of a round's runs are played with no trial (Difficulty).

        The trials land on the round's LAST runs, so a round with fewer trials
        than runs opens with this many clean (trial-free) runs.
        """
        return max(0, RUNS_PER_ROUND - self.trials_per_round)

    @property
    def trials_per_round(self):
        """How many of a round's last runs play a trial (Difficulty)."""
        return Difficulty.trials_per_round(self.difficulty)

    @property
    def score_growth(self):
        """The factor this save's required score grows by each run (Difficulty)."""
        return Difficulty.score_growth(self.difficulty)

    def trial_options_available(self):
        """True while the trial display's two purchase options can be used.

        A run's trial is fixed once its marbles are rolling, so the display can
        only be bought from while BUILDING the run. It is also unavailable
        during the post-run RETRY/CONTINUE state, and when trials are switched
        off for the save entirely. (The 24th run used to show a final boss
        instead of a trial and lock this; it plays a normal trial now.)
        """
        return (self.trials_enabled
                and not self.game_over and not self.run_active
                and not self.run_complete and not self.awaiting_after_run)

    def _trial_half_at(self, pos):
        """Which half of the trial display a screen position is in.

        Returns "left" (buy a different random trial), "right" (buy no trial
        for this run), or None when the position is off the display.
        """
        if not TRIAL_BOX_RECT.collidepoint(pos):
            return None
        return "left" if pos[0] < TRIAL_BOX_RECT.centerx else "right"

    def _random_other_trial(self):
        """A random trial that is different from the one running now.

        With no trial running (the player bought it away) every trial is a
        candidate, so the left half also brings a trial back.
        """
        choices = [t for t in Trial.ORDER if t != self.current_trial]
        return random.choice(choices or list(Trial.ORDER))

    def trial_change_cost(self):
        """Cash the trial display's CHANGE half charges (Challenger halves it).

        The Challenger whole card halves both fees (see _trial_cost_factor), and
        the display reads these rather than the constants so the price it shows
        is the price it charges.
        """
        return int(TRIAL_CHANGE_COST * self._trial_cost_factor())

    def trial_disable_cost(self):
        """Cash the trial display's DISABLE half charges (Challenger halves it)."""
        return int(TRIAL_DISABLE_COST * self._trial_cost_factor())

    def _trial_cost_factor(self):
        """The factor the two trial fees are charged at (see Card.CHALLENGER).

        Read through _has_card, so the Card cutter restores the full price like
        it restores every other card effect.
        """
        return CHALLENGER_COST_FACTOR if self._has_card(Card.CHALLENGER) else 1.0

    def _click_trial_display(self, pos):
        """Buy a new trial (left half) or no trial (right half) for cash.

        The left half pays trial_change_cost() for a DIFFERENT random trial;
        the right half pays trial_disable_cost() to run with no trial at all.
        Either way the trial's effects are rolled onto the current board
        immediately, so what the player sees while building is what the run will
        play. Returns True when a purchase went through.
        """
        half = self._trial_half_at(pos)
        if half is None:
            return False
        if not self.trial_options_available():
            self._set_shop_message("The trial can only be changed while building")
            return False
        change_cost = self.trial_change_cost()
        disable_cost = self.trial_disable_cost()
        if half == "left":
            if self.cash < change_cost:
                self._set_shop_message(
                    f"Need ${change_cost} to change the trial")
                return False
            self.cash -= change_cost
            self.current_trial = self._random_other_trial()
            self._apply_trial()
            # A bought Slim pickings bites the shop already on screen, exactly
            # as a rerolled one would (see _trim_shop_for_trial).
            self._trim_shop_for_trial()
            self._set_shop_message(f"Trial changed: {Trial.name(self.current_trial)}"
                                   f" (${change_cost})")
            sounds.play_coin()
            return True
        if self.current_trial is None:
            self._set_shop_message("This run already has no trial")
            return False
        if self.cash < disable_cost:
            self._set_shop_message(
                f"Need ${disable_cost} to disable the trial")
            return False
        self.cash -= disable_cost
        self.current_trial = None
        self._apply_trial()
        self._set_shop_message(f"Trial disabled (${disable_cost})")
        sounds.play_coin()
        return True

    def _roll_trial_decision(self):
        """Decide every random pick this trial makes, ONCE for the run.

        One dict per run, stored in ``trial_decision`` and re-applied by
        _apply_trial. The picks are recorded as POSITIONS rather than objects
        wherever the board or card area can change under them — the chosen
        blocks are board CELLS and the cut card is an index into the card area —
        so re-applying the decision to a board the player has edited since still
        means "the blocks in these cells", and the same trial keeps cutting the
        same slot. A block the player MOVES takes its decided cell with it (see
        _carry_trial_mark), so the pick stays on the block it chose. That is what
        makes the decision stable: a restart or a retry replays it, and only a
        new run (or a bought trial) re-rolls it.

        The picks are: which cells Hands tied debuffs, which card slot Card
        cutter disables, the order Shuffled leaves the cards in, which cells
        Crumbling makes fragile, whether Marble weight is heavy or light, and
        which way Vertigo's gravity pulls. A trial that makes no random pick
        (the rest of them) returns just its own id.
        """
        decision = {"trial": self.current_trial}
        if self.current_trial == Trial.HANDS_TIED:
            # Only BLOCK squares are picked: a component laid out on the board is
            # not physical, so debuffing it would mean nothing (see
            # Game.ensure_board_cells).
            block_cells = sorted((block.x, block.y) for block in self.board_blocks())
            if block_cells:
                count = max(1, len(block_cells) // 4)
                decision["cells"] = set(random.sample(block_cells, count))
        elif self.current_trial == Trial.CARD_CUTTER:
            if self.cards:
                decision["card_index"] = random.randrange(len(self.cards))
        elif self.current_trial == Trial.SHUFFLED:
            # Flips and shuffles the player's cards (order matters for
            # Blueprint), so the decided order is a shuffle of the reversed
            # card area.
            if self.cards:
                order = list(self.cards)
                order.reverse()
                random.shuffle(order)
                decision["order"] = order
        elif self.current_trial == Trial.CRUMBLING:
            # Only real solid blocks can be picked, and the Start/Finish roles
            # are spared so the run can still be completed.
            cells = sorted(
                (block.x, block.y) for block in self.board_blocks()
                if block.shape != Shape.NONE
                and block.scorer != Scorer.START and block.scorer != Scorer.FINISH)
            if cells:
                count = max(1, len(cells) // 4)
                decision["cells"] = set(random.sample(cells, count))
        elif self.current_trial == Trial.MARBLE_WEIGHT:
            # Heavier (2x effect mass -> weaker pushes) or lighter (0.9x ->
            # stronger pushes) for the whole run. Only effect pushes change;
            # fall speed is untouched.
            decision["weight"] = random.choice((2.0, 0.9))
        elif self.current_trial == Trial.VERTIGO:
            # Which way gravity pulls for the whole run: an INDEX into
            # VERTIGO_DIRECTIONS (every direction but straight down), so the
            # pick rides through a save as a plain number.
            decision["gravity"] = random.randrange(len(VERTIGO_DIRECTIONS))
        return decision

    def _apply_shuffled_order(self, order):
        """Put the card area into the order the Shuffled trial settled on.

        The trial's order is decided once per run, so re-applying it (a restart
        or a retry) must not shuffle the cards again — and it must survive a
        card being sold or bought afterwards, which is what the merge at the
        end is for: the decided cards keep their decided order and anything
        that came later follows them.
        """
        if not order:
            return
        cards = list(self.cards)
        decided = [card for card in order if card in cards]
        self.cards[:] = decided + [c for c in cards if c not in decided]

    def _apply_trial(self):
        """Apply the current trial to this run's blocks and cards.

        Every random choice a trial makes is decided ONCE for the run (see
        _roll_trial_decision) and only APPLIED here, so applying the trial again
        — which is what restarting the run (R), starting it anew (T) or
        retrying a finished run does — re-applies the same choices instead of
        rolling new ones. A run therefore cannot be rerolled by replaying it;
        only a new run, or buying a different trial (which decides afresh),
        changes these picks.

        Hands tied debuffs a random 1/4 of the blocks in the marble box: each
        of them scores TRIAL_TRIGGER_PENALTY fewer times this run. Card cutter
        disables a random owned card, whose score effect is skipped for the run.
        Shuffled shuffles the card area into one decided order AND turns every
        owned card face over (see CardItem.flipped). Crumbling marks a random
        1/4 of the placed blocks as fragile (they shatter like real fragile
        blocks once a marble touches and leaves, then rebuild next run). Marble
        weight uses a decided heavier-or-lighter drive-push factor (read when
        each marble is released). Vertigo sets the direction the run's gravity
        pulls in. Deal breaker gags the board — no block scores until a card
        is sold (see _deal_breaker_gags) — and because that sale is recorded
        on the game and saved with it, applying the trial cannot re-gag a
        board the player has already freed: a later Deal breaker run simply
        starts free.

        Three trials have nothing to apply here: Slim pickings acts on the SHOP
        rather than on the board or the card area, so it is applied wherever a
        shop is built or met instead (see _trim_shop_for_trial), and Phantom and
        Elephant are applied to each marble as it is released (see
        _release_start_marble).

        Sky High is not applied to the board either — it acts on the RUN's
        required score, which _refresh_run_target re-derives here so that buying
        a different trial (or none) restores the target the run would otherwise
        have had (see _trial_score_factor).

        The trial state is cleared again when the run advances (see
        _continue_run), so the NEXT run decides its own picks.
        """
        decision = self.trial_decision
        if decision is None or decision.get("trial") != self.current_trial:
            # First application of this trial to this run (or the player bought
            # a different trial): decide its picks now, once.
            decision = self.trial_decision = self._roll_trial_decision()
        self.trial_debuffed_blocks = set()
        self.disabled_card = None
        # A non-MARBLE_WEIGHT trial keeps the normal 1.0 factor.
        self.trial_marble_weight = 1.0
        # Nothing of the trial's deal-breaker gag is reset here: the freedom a
        # sale wins is the player's for the rest of the game (see card_sold).
        # Only a Vertigo run redraws gravity (see _release_start_marble).
        self.trial_gravity_dir = None
        # Shuffled turns the player's cards face over for the run; every other
        # trial (and none at all) leaves them the right way up.
        for card in self.cards:
            card.flipped = False
        # Blocks chosen by an earlier crumbling run are un-marked first so the
        # fragility never lingers into a trial that isn't crumbling.
        for block in self.board_blocks():
            block.trial_fragile = False
        self.trial_fragile_blocks = set()
        if self.current_trial == Trial.HANDS_TIED:
            # The decided CELLS, not the block objects: a block the player has
            # since put in one of them is debuffed too, and a cell left empty
            # simply has nothing to debuff. Moving a chosen block moves the cell
            # with it (see _carry_trial_mark), so the debuff stays on the block
            # the trial picked.
            self.trial_debuffed_blocks = {
                self.grid[cell] for cell in decision.get("cells", ())
                if isinstance(self.grid.get(cell), Block)}
        elif self.current_trial == Trial.CARD_CUTTER:
            # The decided card SLOT (clamped, so the trial keeps cutting one
            # card even if the area has shrunk since).
            if self.cards:
                index = min(decision.get("card_index", 0), len(self.cards) - 1)
                self.disabled_card = self.cards[index]
        elif self.current_trial == Trial.SHUFFLED:
            self._apply_shuffled_order(decision.get("order"))
            # "Flips and shuffles your cards": the shuffle is the decided order
            # above, and the FLIP is a real one — every owned card is drawn face
            # over (upside down) for the run. It is a handicap, not a change to
            # what a card does: a flipped card still pays exactly what it paid.
            for card in self.cards:
                card.flipped = True
        elif self.current_trial == Trial.CRUMBLING:
            for cell in decision.get("cells", ()):
                block = self.grid.get(cell)
                if isinstance(block, Block):
                    block.trial_fragile = True
                    self.trial_fragile_blocks.add(block)
        elif self.current_trial == Trial.MARBLE_WEIGHT:
            self.trial_marble_weight = decision.get("weight", 1.0)
        elif self.current_trial == Trial.VERTIGO:
            index = min(int(decision.get("gravity", 0)),
                        len(VERTIGO_DIRECTIONS) - 1)
            self.trial_gravity_dir = VERTIGO_DIRECTIONS[index]
        # Sky High (and the trial changing at all) decides the run's target: a
        # bought trial change lands here too (see _click_trial_display), so the
        # target follows whatever trial the run ends up playing.
        self._refresh_run_target()

    def _apply_cards(self):
        """Apply the start-of-run card effects.

        The named cards that fire at the start of a run (Joker's +4 mult, the
        Pillar, the Banker, Glitch, Ripped Card, Cozy, Painting, Synthesizer,
        Island), plus Tesseract's saved reroll bonus and the Wrecking Ball's
        banked mult — see cards.apply_cards.
        """
        cards.apply_cards(self)

    def _apply_cards_on_finish(self):
        """Apply the cards that fire when the run ends (Explorer's visited-units
        xMult, Astronaut's black-hole mult, Plane's air-time chips, Skater's
        slippery xMult) — see cards.apply_cards_on_finish."""
        cards.apply_cards_on_finish(self)

    def _apply_cards_on_collision(self, block, marble=None):
        """Apply owned cards whose match group covers the collided block.

        A card fires once per fresh collision: a unit scorer pays one standard
        unit and every other scorer fires its block-style payoff (see
        cards.apply_card_on_collision). ``marble`` is the touching marble (an
        Airball card rewards its airborne streak before the hit).
        """
        cards.apply_card_on_collision(self, block, marble)

    def _on_fragile_broken(self, block):
        """A fragile block broke.

        The shattering counts as a block destroyed this run (the Undertaker
        scorer pays for each of them) and fires the Wrecking Ball card, which
        banks +3 mult a break (see cards.on_fragile_broken).
        """
        self.run_blocks_destroyed += 1
        cards.on_fragile_broken(self, block)

    def _unlock_matching_locks(self, key_block):
        """Open every Lock block paired with the given Key block.

        The two halves of a key/lock pair share a key number; passing through
        the Key opens the Lock — its solid door becomes a pass-through doorway
        for the rest of the run (it closes again at the start of the next one,
        see reset_run). A Key with no matching Lock on the board (a lone half,
        e.g. one granted at random) opens nothing.
        """
        number = getattr(key_block, "key_number", 0)
        if not number:
            return
        for block in self.board_blocks():
            if (block.shape == Shape.LOCK and getattr(block, "locked", True)
                    and getattr(block, "key_number", 0) == number):
                block.locked = False

    def _adopt_pairing_numbers(self):
        """Claim the pairing numbers the loaded state already uses.

        Called once a save has been loaded (see save_system._load_save_data):
        the pairing numbers are handed out by a counter that lives in this
        process while the numbers themselves come from the save, so the loaded
        board's numbers are claimed here before any new pair is built — and a
        board saved with two pairs sharing a number is re-paired on the way in
        (see adopt_pairing_numbers).
        """
        adopt_pairing_numbers(self.board_blocks()
                              + list(self.toolbox.items)
                              + list(self.shop.items))

    def _sync_portal_pair_triggers(self, block, blocks):
        """Make a portal share its trigger count with every portal it pairs with.

        Portal pairs have ONE trigger count: a marble passing through either
        portal uses up the whole pair. Both portals are set to the lowest of the
        remaining counts so they stay in lockstep and their red borders agree —
        e.g. a freshly placed portal inherits an exhausted partner's count of
        zero. Recognition can leave more than two portals sharing a number (see
        _delete_paired_portal), so EVERY partner is synced, not just the first
        one found: a third copy left at its own count would spend triggers its
        partners never agreed to.
        """
        if not block.has_effect(Effect.PORTAL):
            return
        number = getattr(block, "portal_number", 0)
        partners = [other for other in blocks
                    if other is not block and other.has_effect(Effect.PORTAL)
                    and getattr(other, "portal_number", 0) == number]
        if not partners:
            return
        shared = min([block.triggers_left]
                     + [other.triggers_left for other in partners])
        block.triggers_left = shared
        for other in partners:
            other.triggers_left = shared

    def _score_factors(self):
        """The run's normalized score factors, each in 0..1 (1 = best).

        Returns (time_good, dist_good, uniq_good, unique_types). Time is full
        credit for anything at or under the ideal time (so a fast run, and a
        zero-length one, is best) and a quadratic penalty past it; distance and
        uniqueness grow with their value. The three are the whole of the total
        score's exponent (see _compute_total_score), so the cards that rewrite
        them are rewriting the run's final payoff: Watch pins time at its best,
        Infinity un-caps distance and uniqueness.
        """
        total_distance = sum(getattr(m, "distance", 0.0) for m in self.marbles)
        # The uniqueness score counts every distinct type touched — EXCEPT under
        # the repeats-only trial, where a shape/effect/scorer type only counts
        # once it has been freshly touched at least twice this run (each
        # qualifying type counts once toward UNIQUE_SCALE).
        if self.trials_enabled and self.current_trial == Trial.REPEATS_ONLY:
            unique_types = (sum(1 for c in self.touch_shape_counts.values() if c >= 2)
                            + sum(1 for c in self.touch_effect_counts.values() if c >= 2)
                            + sum(1 for c in self.touch_scorer_counts.values() if c >= 2))
        else:
            unique_types = (len(self.touched_shapes) + len(self.touched_effects)
                            + len(self.touched_scorers))
        # The Long run trial doubles the ideal time, so longer runs still earn
        # the full time contribution; the Speedrun trial halves it, so only a
        # very fast run keeps full time contribution.
        if self.trials_enabled and self.current_trial == Trial.LONG_RUN:
            ideal_time = TIME_IDEAL * 2
        elif self.trials_enabled and self.current_trial == Trial.SPEEDRUN:
            ideal_time = TIME_IDEAL / 2
        else:
            ideal_time = TIME_IDEAL
        # Time is the only factor the run itself can push NEGATIVE: anything at
        # or under the ideal time earns the whole contribution, and past it the
        # run pays a quadratic penalty (which a hopelessly slow run drives under
        # zero, taking the total score's exponent with it).
        if 0 <= self.run_time <= ideal_time:
            time_good = 1.0
        else:
            time_good = 1 - (self.run_time - ideal_time) ** 2 / TIME_SCALE
        # The Watch whole card makes the time factor always the best it can be:
        # the run's LENGTH never costs score again (it still earns no more than
        # the ceiling). Without it the factor is a quadratic penalty on a long
        # run, so this is the card that makes a slow, long build legal.
        if self._has_card(Card.WATCH):
            time_good = TIME_GOOD_MAX
        # The Infinity whole card swaps the two saturating curves for straight
        # lines pinned to them at INFINITY_ANCHOR — traded for a slower start in
        # exchange for never levelling off (see infinity_factor).
        if self._has_card(Card.INFINITY):
            dist_good = infinity_factor(total_distance, DISTANCE_SCALE)
            uniq_good = infinity_factor(unique_types, UNIQUE_SCALE)
        else:
            dist_good = np.atan(total_distance / DISTANCE_SCALE) * 2 / np.pi
            uniq_good = np.atan(unique_types / UNIQUE_SCALE) * 2 / np.pi
        return time_good, dist_good, uniq_good, unique_types

    def _compute_total_score(self):
        """Total score: (chips * mult) raised to a linear function of time,
        distance, and uniqueness.

        Each factor is 0..1 and the exponent is a flat 0.5 plus half their sum,
        so it runs from 0.5 (a slow, short, samey run) to 2 (a fast, long, varied
        one) — lower still if the time penalty has gone negative. Two cards
        rewrite it: the Inferno card raises it (see INFERNO_EXPONENT_BONUS) and
        Infinity lifts the 1-point ceiling off distance and uniqueness entirely.
        """
        # The score is per MARBLE, so the run's payoff is what every marble on
        # the board is worth added up (a split therefore pays for both halves);
        # with no marble at all it is the run's base pair.
        if self.marbles:
            worth = sum(max(marble.chips * marble.mult, 0)
                        for marble in self.marbles)
        else:
            worth = self._base_chips * self._base_mult
        base = max(worth, 1)
        time_good, dist_good, uniq_good, _ = self._score_factors()
        exponent = 0.5 + (time_good + dist_good + uniq_good) * (1/2)
        # The Inferno whole card raises the exponent itself, so it multiplies
        # the whole run's score by the chips x mult base raised to 0.07.
        if self._has_card(Card.INFERNO):
            exponent += INFERNO_EXPONENT_BONUS
        # The total stays a float internally (chips and mult can be
        # fractional); the UI rounds it to a tenth for display. Coerce to a
        # PLAIN Python float: _score_factors() returns numpy scalars, and a
        # numpy ``base ** exponent`` would leak a numpy float64 into
        # score_total, whose comparisons return numpy bools that later break
        # JSON saves (``run_results`` is persisted).
        return float(base ** exponent)

    def _fire_target(self):
        """How strong the marble-box fire should be right now (0..FIRE_MAX).

        The fire appears while a run is active and the score has passed the
        required score; it is larger the more the score beats the target (the
        excess as a fraction of the target, capped at FIRE_MAX_INTENSITY). It
        is zero once the run is over, so the fire dies down.

        A run whose required score is only beaten by a payoff that fires as the
        run SETTLES (the banked xMult, an end-of-run card's factor) never gets
        such a frame, so the finish path seeds the fire with this target while
        the run is still active (see _handle_block_contacts).
        """
        if not self.run_active or self.score_total < self.required_score:
            return 0.0
        excess = (self.score_total - self.required_score) / max(self.required_score, 1)
        return min(FIRE_MAX_INTENSITY, max(0.0, excess))

    def _update_fire(self, dt):
        """Move the marble-box fire toward its target, then let it die down.

        While a run is active and passed, the fire grows (larger the more the
        score beats the target). Once the run is over (or the score drops back
        below the requirement) it gradually decays to nothing — a run cleared
        only by an end-of-run payoff is seeded as it settles, so it burns from
        the finish onwards instead of never lighting (see _fire_target).
        """
        target = self._fire_target()
        if self.fire_intensity < target:
            self.fire_intensity = min(target, self.fire_intensity + FIRE_RISE_SPEED * dt)
        else:
            self.fire_intensity = max(0.0, self.fire_intensity - FIRE_DECAY_SPEED * dt)
        if self.fire_intensity < 0.01:
            self.fire_intensity = 0.0

    def _brain_loop_roll(self, block):
        """Brain Loop: a fresh touch of a Sticky block may hand over an action.

        A BRAIN_LOOP_ACTION_CHANCE roll per fresh contact with a block carrying
        the Sticky effect, taken from the RUN's own RNG (Game.run_rng) so a
        replayed run makes the same rolls it made before — the rule every other
        random output follows (see Glitch, the 8 ball's retrigger). The ACTION
        itself is drawn like any other grant (see _grant_random_action, which
        also refuses it, with a message, when the action area is full), so a
        full area never silently swallows the roll. Read through _has_card, so
        the Card cutter silences the card like any other passive.
        """
        if not self._has_card(Card.BRAIN_LOOP):
            return
        if not block.has_effect(Effect.STICKY):
            return
        if self.run_rng.random() < BRAIN_LOOP_ACTION_CHANCE:
            self._grant_random_action()

    def _gondola_axis(self, block):
        """The (axis, sign) a cable car slides on, read from its arrow.

        The effect's whole rule is "up and down, or left to right, depending on
        the block's angle": the block's own arrow (the vector the Accelerator
        pushes along and the Gravity block pulls along, see
        Block._get_angle_vector, which includes a Rotate block's spin) decides
        which axis the car travels on — the longer of its two components — and
        which way it sets off first. "x" means left/right and "y" up/down.
        """
        vector = block._get_angle_vector()
        dx, dy = float(vector[0]), float(vector[1])
        if abs(dx) >= abs(dy):
            return "x", 1 if dx >= 0 else -1
        return "y", 1 if dy >= 0 else -1

    def _gondola_solids(self, block):
        """The blocks a cable car must not slide into.

        Every placed block plus, while the board is locked, the solid walls
        covering the locked squares (see _simulation_blocks) — which is what
        makes a locked square turn a gondola around without any extra rule.
        Only the blocks that are physically THERE stop it: a Shape.NONE field
        and an opened Lock are pass-through for the marble, so the car sails
        through them too. OTHER CABLE CARS ARE NOT SOLIDS: a car's lane, its
        turning points and its cables are about the board it was built on, so
        two cars sharing a lane cross straight through each other rather than
        turning around at one another — the marbles still collide with both of
        them, since this list is only the effect's own geography.
        """
        solids = []
        for other in self._simulation_blocks():
            if other is block or other.shape == Shape.NONE:
                continue
            if other.shape == Shape.LOCK and not other.locked:
                continue
            if other.has_effect(Effect.GONDOLA):
                continue
            solids.append(other)
        return solids

    def _update_gondolas(self, dt):
        """Slide every cable car one frame along its lane (see Effect.GONDOLA).

        Called once a frame while a run is in play — not once per marble, which
        would make the cars faster the more marbles a run has — and before the
        frame's block list is built, so the marbles meet each car where it has
        just moved to. Their travel is per-run state, undone by _reset_gondola.
        """
        gondolas = [block for block in self.board_blocks()
                    if block.has_effect(Effect.GONDOLA)]
        if not gondolas:
            return
        for block in gondolas:
            self._slide_gondola(block, dt)

    @staticmethod
    def _gondola_home_rect(block):
        """The rect a cable car sits on in its own cell, before it has moved.

        A car only ever leaves its cell for the length of a run: the cell — the
        key it is stored under, and where it is rebuilt from — is what its lane
        is measured from, exactly as _reset_gondola puts it back there.
        """
        return pygame.Rect(block.x * GRID_SIZE + MARBLE_BOX_COORDS[0],
                           block.y * GRID_SIZE + MARBLE_BOX_COORDS[1],
                           GRID_SIZE, GRID_SIZE)

    def _gondola_rect(self, block, travel):
        """The rect a cable car occupies after sliding ``travel`` px from its cell.

        The travel is measured along the car's own axis and is floored here into
        the whole pixels a rect holds. A SLOW car — the roll can land as low as a
        tenth of the average speed, a tenth of a pixel a frame — is why the
        travel is a float at all: flooring it once, on the way into the rect,
        keeps a tenth of a pixel from being thrown away on EVERY frame.
        """
        rect = self._gondola_home_rect(block)
        offset = math.floor(travel)
        axis, _sign = self._gondola_axis(block)
        if axis == "x":
            rect.x += offset
        else:
            rect.y += offset
        return rect

    def _gondola_lane(self, block):
        """How far a cable car may slide each way, as pixel travel from its cell.

        Returns ``(low, high)``: the most the car can slide backwards (negative
        or zero) and forwards (positive or zero) before its next step would put
        it into something solid — a block, a locked square's wall or the board's
        border (see _gondola_solids). It is the whole of the effect's geography:
        the car turns around at these two ends, and they are where the cables
        stop, so the drawn track spans exactly the ground the car can cover.
        Another cable car is not one of these ends, so a lane is the same shape
        whether or not other cars are sharing it.
        """
        axis, _sign = self._gondola_axis(block)
        home = self._gondola_home_rect(block)
        # The board is infinite, so the outer ends of a lane are the edges of the
        # UNLOCKED region — the playfield the marble itself is walled into.
        bounds = self.board_pixel_bounds()
        if axis == "x":
            low = bounds[0] - home.left
            high = bounds[0] + bounds[2] - home.right
        else:
            low = bounds[1] - home.top
            high = bounds[1] + bounds[3] - home.bottom
        for other in self._gondola_solids(block):
            rect = other.rect
            if axis == "x":
                if rect.bottom <= home.top or rect.top >= home.bottom:
                    continue
                if rect.right <= home.left:
                    low = max(low, rect.right - home.left)
                elif rect.left >= home.right:
                    high = min(high, rect.left - home.right)
                else:
                    # It covers the car's own cell already (a shape that reaches
                    # outside it): there is nowhere to go.
                    low = high = 0
                    break
            else:
                if rect.right <= home.left or rect.left >= home.right:
                    continue
                if rect.bottom <= home.top:
                    low = max(low, rect.bottom - home.top)
                elif rect.top >= home.bottom:
                    high = min(high, rect.top - home.bottom)
                else:
                    low = high = 0
                    break
        # Both ends always include the car's own cell: a car wedged where it
        # stands (or one on a board so small it has no room) still has a lane,
        # it is just a lane of no length.
        return min(low, 0), max(high, 0)

    def _slide_gondola(self, block, dt):
        """Move one cable car, turning it around at the end of its lane.

        The car slides along its own axis at its rolled speed until the next
        frame of travel would take it past the end of its lane — a block, a
        locked square's wall or the board's border (see _gondola_lane; another
        cable car is not one of them, so cars sharing a lane cross) — where it
        reverses and uses the rest of the frame on the way back, so a car parked
        against a wall is never stuck. The travel itself is kept as a
        float and only floored into the rect (see _gondola_rect): quantizing it
        into the rect every frame, which is what Rect.move does, throws away the
        fraction and leaves a slow car standing still forever. Only the rect
        moves: its cell — the key it is stored under, and where it is rebuilt
        from — never changes, exactly like a rotating block keeps its cell.
        """
        _axis, sign = self._gondola_axis(block)
        if block.gondola_dir is None:
            block.gondola_dir = sign
        speed = block.effect_magnitude(Effect.GONDOLA)
        low, high = self._gondola_lane(block)
        travel = block.gondola_travel + speed * dt * block.gondola_dir
        if travel < low or travel > high:
            # Blocked: turn around and use the rest of this frame going back.
            block.gondola_dir = -block.gondola_dir
            travel = block.gondola_travel + speed * dt * block.gondola_dir
        block.gondola_travel = min(high, max(low, travel))
        moved = self._gondola_rect(block, block.gondola_travel)
        if moved != block.rect:
            block.rect = moved
            # The block's geometry (its shape's cached points, walls, arcs) is
            # built from the rect, so it has to be rebuilt to move.
            block._refresh_geometry()

    @staticmethod
    def _reset_gondola(block):
        """Put one cable car back on its own cell, facing its arrow again.

        The build phase shows the board the player built, so a run's travel is
        undone with the rest of the run's state (triggers, locked doors, spin)
        — and the direction is forgotten rather than stored, so rotating a
        block between runs sends the car off along the new arrow the first time
        it moves (see _gondola_axis).
        """
        block.rect = RunsMixin._gondola_home_rect(block)
        block.gondola_travel = 0.0
        block.gondola_dir = None
        block._refresh_geometry()
