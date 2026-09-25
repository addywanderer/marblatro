"""One shared Game and every helper the split test modules use.

The behaviour suite used to be a single 15k-line tests/test_run_scoring.py. It
is now split by topic — test_ui, test_shop, test_cards, test_blocks, … — all
inheriting from the GameTestCase below, which owns:

* the per-test Game (a real ``main.Game()`` on the dummy SDL driver, with the
  player-data paths redirected into a temp folder so a test can never touch a
  real save),
* every helper the tests share (clicking, pressing keys, placing blocks,
  flying a marble into a block, and the pixel probes used by the UI tests).

A split module starts with ``from tests.game_test_case import *`` and defines
one ``class XxxTests(GameTestCase)``; nothing else needs importing.
"""

import inspect
import itertools
import json
import math
import os
import random
import re
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

import achievements
import collection
import components
import main
import metagame
import profiles
import save_system

__all__ = [
    "inspect", "itertools", "json", "math", "os", "random", "re", "shutil",
    "tempfile", "unittest", "mock", "np", "pygame", "achievements",
    "collection", "components", "main", "metagame", "profiles", "save_system",
    "GameTestCase", "CONDITIONS_COMMENTED_OUT", "NAMED_CARDS_GONE",
    "_group_card", "_card_item",
    "_card_for_block", "_shape_card_value", "_effect_card_value",
]


# COMMENTED OUT WITH THE CONDITIONS (user request: "comment out all the code for
# conditions"): every test that exercised the condition system — a composed
# (condition x scorer) card, the card builder, splitting a card into halves, or
# the classic card names the conditions were split from — carries
#
#     @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
#
# so it stays in the file, verbatim and ready to run, and is skipped for exactly
# as long as the condition system is commented out (components.py's
# `_COMMENTED_OUT_CONDITION_CLASS`). Uncommenting the conditions makes
# `main.Condition` exist again and these tests run as they always did.
CONDITIONS_COMMENTED_OUT = ("the condition system is commented out — "
                            "see components.py and main.py")

# The fourteen NAMED CARDS (Joker, Explorer, Astronaut, ... — see
# components.Card.NAMED) are the named conditions' whole-card form: the classic
# cards, unsplittable. A test that only needs a classic card to exist (it uses
# main.Card.JOKER & friends and the ordinary run hooks) carries
#
#     @unittest.skipUnless(hasattr(main.Card, "JOKER"), NAMED_CARDS_GONE)
#
# so it runs while the cards are there and parks itself if they ever go away
# again. Tests that need the CONDITION SYSTEM (a composed condition x scorer
# card, the card builder, splitting) carry the CONDITIONS_COMMENTED_OUT marker
# above instead and stay parked.
NAMED_CARDS_GONE = ("the named cards (Joker, Explorer, ...) are not defined — "
                    "see components.Card.NAMED")


def _group_card(group, scorer):
    """The card value for a (match group x scorer) pair."""
    return main.match_group_card(group, scorer)


def _card_item(group, scorer, amount=None):
    """A CardItem for a (match group x scorer) card, at the AVERAGE magnitude.

    Tests read exact payoffs, so the magnitude is the scorer's default unless a
    test passes its own (a rolled one would make the assertion depend on luck).
    """
    value = _group_card(group, scorer)
    if amount is None:
        amount = main.Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    return main.CardItem(value, main.Card.PRICES[value], amount=amount)


def _card_for_block(block, scorer, amount=None):
    """A card item whose match group covers ``block`` (its shape, else effect).

    The shape is tried first — a block is matched by its shape group as well as
    by every effect group it carries — and an effect is used when the shape is
    in no group (a plain rect wall). Returns None for a block nothing matches.
    """
    group = main.match_group_for_shape(block.shape)
    if group is None:
        for effect in getattr(block, "effects", ()):
            group = main.match_group_for_effect(effect)
            if group is not None:
                break
    return None if group is None else _card_item(group, scorer, amount)


# COMMENTED OUT with the conditions (user request: "comment out all the code for
# conditions"): the composed-card shims. They pointed main.Card.JOKER & friends
# at the (condition x scorer) card that played each removed classic card's role;
# a card is a (match group x scorer) pair now, so the classic cards no longer
# exist in any form and the tests that used them are disabled with the rest of
# the condition tests.
#
# def _magnitude_card(condition, scorer):
#     """The composed magnitude card value for (condition x unit scorer)."""
#     return main.condition_scorer_card(condition, scorer)
#

def _install_card_shims():
    # The legacy score-type aliases -> the unit scorers they correspond to.
    main.Card.SCORE_CHIPS = main.Scorer.CHIPS_ADD
    main.Card.SCORE_MULT = main.Scorer.MULT_ADD
    main.Card.SCORE_XMULT = main.Scorer.MULT_MUL


# The shims must be installed before any test module builds its tests.
_install_card_shims()


def _shape_card_value(shape, scorer):
    """The card value for a shape: the shape group's card for that scorer."""
    return _group_card(main.match_group_for_shape(shape), scorer)


def _effect_card_value(effect, scorer):
    """The card value for an effect: the effect group's card for that scorer."""
    return _group_card(main.match_group_for_effect(effect), scorer)


class GameTestCase(unittest.TestCase):
    """A live Game plus the helpers every split test module shares."""

    def setUp(self):
        self.game = main.Game()
        self.game.title_screen = False  # skip the title screen in tests
        # A fresh Game draws the trial of the run it opens on — and on the
        # default difficulty that run plays one. A Slim pickings draw has
        # already shed two shop options by the time a test sees the game (see
        # Game._trim_shop_for_trial), which would leave the starting shop 13
        # items big 1 draw in 15. Switching the trial system off first is what
        # keeps it full (nothing trims a shop while trials are disabled), so
        # rebuilding the shop puts every test on the same 15-item one.
        self.game.trials_enabled = False  # no random trial in generic tests
        if self.game.current_trial == main.Trial.SLIM_PICKINGS:
            self.game.shop.refresh()
        self.game.run_active = False
        self.game.run_complete = False
        self.game.score_chips = 0
        self.game.score_mult = 1
        # Keep the global achievements file out of test runs: achievements are
        # persisted globally, so each test starts from a clean unlocked set.
        self._ach_tmp = tempfile.mkdtemp()
        self._old_ach_file = achievements.FILE_PATH
        achievements.FILE_PATH = os.path.join(self._ach_tmp, "achievements.json")
        achievements.reset()
        # The metagame (dice + run-start upgrades) is global too; keep it out
        # of test runs so no test inherits a leftover bonus.
        self._old_meta_file = metagame.FILE_PATH
        metagame.FILE_PATH = os.path.join(self._ach_tmp, "metagame.json")
        metagame.reset()
        # The collection (discovered cards/components/trials) is global too.
        self._old_collection_file = collection.FILE_PATH
        collection.FILE_PATH = os.path.join(self._ach_tmp, "collection.json")
        collection.reset()
        # A few tests here save the game (P), so point the save slots at the
        # throwaway folder as well: the suite must never write into a profile.
        self._old_saves_dir = save_system.SAVES_DIR
        save_system.SAVES_DIR = os.path.join(self._ach_tmp, "saves")


    def tearDown(self):
        save_system.SAVES_DIR = self._old_saves_dir
        achievements.FILE_PATH = self._old_ach_file
        achievements.reset()
        metagame.FILE_PATH = self._old_meta_file
        metagame.reset()
        collection.FILE_PATH = self._old_collection_file
        collection.reset()
        shutil.rmtree(self._ach_tmp, ignore_errors=True)


    def _add_marble(self, position=(300, 300)):
        marble = main.Marble(*position)
        self.game.marbles.append(marble)
        return marble


    def _grid_pos(self, gx, gy):
        """A screen point inside the given marble-box grid cell."""
        return (main.MARBLE_BOX_COORDS[0] + gx * main.GRID_SIZE + 5,
                main.MARBLE_BOX_COORDS[1] + gy * main.GRID_SIZE + 5)


    def _region_has_white(self, rect):
        """True when any pure-white pixel appears in the given screen region."""
        return any(self.game.screen.get_at((x, y))[:3] == main.WHITE
                   for x in range(rect.left, rect.right)
                   for y in range(rect.top, rect.bottom))


    def _marble_box_title_region(self):
        """The bottom-left region of the board (marble box) where its title sits."""
        return pygame.Rect(main.MARBLE_BOX_COORDS[0] + 6,
                           main.MARBLE_BOX_COORDS[1] + main.MARBLE_BOX_COORDS[3] - 28,
                           220, 26)


    def _toolbox_title_region(self):
        """The bottom-left region of the inventory (toolbox) where its title sits."""
        return pygame.Rect(main.TOOLBOX_COORDS[0] + 6,
                           main.TOOLBOX_COORDS[1] + main.TOOLBOX_COORDS[3] - 28,
                           220, 26)


    def _shop_title_region(self):
        """The bottom-left region of the shop where its title sits."""
        return pygame.Rect(main.SHOP_COORDS[0] + 6,
                           main.SHOP_COORDS[1] + main.SHOP_COORDS[3] - 28,
                           220, 26)


    def _run_quick_drop(self, effect):
        """Drop a marble onto a Quick block with the given effect and run physics.

        Returns (chips gained, the block). A marble is released above the block
        and the game is stepped until the block's trigger is used up, so the
        physics (forces, collisions, effect behavior) all play out for real.
        """
        game = main.Game()
        game.title_screen = False
        game.score_chips = 0
        game.run_active = True
        block = main.Block(4, 5, shape=main.Shape.RECT, effect=effect, scorer=main.Scorer.QUICK)
        game.grid[(4, 5)] = block
        marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE + 20,
                             main.MARBLE_BOX_COORDS[1] + 2 * main.GRID_SIZE + 20)
        marble.velocity = np.array([0.0, 300.0])
        game.marbles.append(marble)
        for _ in range(60 * 5):
            game.update()
            if block.triggers_left == 0:
                break
        return game.score_chips, block


    def _pipe_drop(self, angle=0):
        """Drop a marble through a pipe's cavity; returns (chips, triggers_left).

        Runs real physics so the marble passes through the pipe's gap without
        touching the pillars.
        """
        game = main.Game()
        game.title_screen = False
        game.score_chips = 0
        game.run_active = True
        pipe = main.Block(4, 5, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                          scorer_amount=30, angle=angle)
        game.grid[(4, 5)] = pipe
        if angle == 0:
            marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE + 20,
                                 main.MARBLE_BOX_COORDS[1] + 2 * main.GRID_SIZE + 20)
            marble.velocity = np.array([0.0, 200.0])
        else:
            # A 90-degree pipe has a horizontal gap at the cell's vertical
            # center: enter from the left and pass through it.
            marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE - 30,
                                 main.MARBLE_BOX_COORDS[1] + 5 * main.GRID_SIZE + 20)
            marble.velocity = np.array([200.0, 0.0])
        game.marbles.append(marble)
        for _ in range(60 * 4):
            game.update()
            if pipe.triggers_left == 0:
                break
        return game.score_chips, pipe.triggers_left


    def _trigger_random_block(self, roll):
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        with mock.patch("main.random.random", return_value=roll):
            self.game._handle_block_contacts([block])
        return block


    def _trigger_lucky(self, rolls):
        """Trigger a Lucky block with the given draws (chips roll, then cash roll)."""
        block = main.Block(0, 0, scorer=main.Scorer.LUCKY)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        with mock.patch("main.random.random", side_effect=rolls):
            self.game._handle_block_contacts([block])
        return block


    def _touch_block(self, block, random_value=0.9):
        """Touch a block once with random.random patched to a constant.

        The patch proves a pre-rolled outcome is being reused: if the block
        rolled now, this value would decide the reward instead.
        """
        self.game.marbles = []
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        with mock.patch("main.random.random", return_value=random_value):
            self.game._handle_block_contacts([block])


    def _touch_frontier(self, block, unlocked_cells):
        """Touch a Frontier block on a board with the given unlocked cells."""
        self.game.run_active = True
        self.game.score_mult = 1
        self.game.unlocked_cells = set(unlocked_cells)
        self.game._board_walls_dirty = True
        self.game.grid[(block.x, block.y)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        return block


    def _touch_cluster(self, block, filled_cells):
        """Place a Cluster block plus the given filled cells and touch it once."""
        self.game.run_active = True
        self.game.score_mult = 1
        self.game.grid[(block.x, block.y)] = block
        for cell in filled_cells:
            self.game.grid[cell] = main.Block(*cell, scorer=main.Scorer.NONE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        return block


    # --- The nine utility whole cards ---------------------------------------

    def _touch_blocks(self, blocks):
        """Fresh-touch each block in turn with one marble, in the given order."""
        self.game.run_active = True
        if not self.game.marbles:
            self._add_marble()
        marble = self.game.marbles[0]
        for block in blocks:
            self.game.grid[(block.x, block.y)] = block
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        return marble


    # --- Procrastination: the run's second chance ---------------------------

    def _start_procrastination_run(self, own_card=True):
        """Fly a one-column ladder run (Start -> scoring field -> Finish).

        The marble falls the whole height of the box through a no-hitbox field
        block and lands on the Finish block, so the run ends about half a second
        in — short enough that a rewind reaches back to its very first frame.
        Returns (marble, scoring block).
        """
        self.game.grid.clear()
        self.game.grid[(5, 1)] = main.Block(5, 1, scorer=main.Scorer.START)
        self.game.grid[(5, 5)] = main.Block(
            5, 5, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD,
            scorer_amount=10)
        self.game.grid[(5, 9)] = main.Block(5, 9, scorer=main.Scorer.FINISH)
        if own_card:
            self.game.cards = [main.CardItem(main.Card.PROCRASTINATION, 46)]
        self.game.reset_run()
        return self.game.marbles[0], self.game.grid[(5, 5)]


    # --- Essence: cash every run, a slot gone, tokens when sold --------------

    def _card_fillers(self, count):
        """Distinct whole cards to fill the card area with."""
        values = [main.Card.SHOWMAN, main.Card.GARDEN, main.Card.COUPON,
                  main.Card.MARKET, main.Card.MINESHAFT]
        return [main.CardItem(value, 30) for value in values[:count]]


    # --- Concert: +1 trigger for the blocks with a shape, effect and scorer --

    def _concert_block(self, shape=main.Shape.PIPE, effects=(main.Effect.BOUNCY,),
                       scorer=main.Scorer.CHIPS_ADD, x=1, y=1):
        """A block on the board built from the given parts (Concert's rule is
        about exactly these three)."""
        block = main.Block(x, y, shape=shape, scorer=scorer, scorer_amount=30,
                           effects=list(effects))
        self.game.grid[(x, y)] = block
        return block


    def _click(self, pos):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()


    def _press(self, key):
        event = mock.Mock()
        event.type = main.pygame.KEYDOWN
        event.key = key
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()


    def _play_run(self, score):
        """Simulate one complete marble run with the given total score, then continue."""
        self.game.marbles = []
        marble = self._add_marble()
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = score
        self.game.score_mult = 1
        # An ideal run time so a large score_chips produces a high total score
        # (the time factor's modulator makes a zero-time run score 0 on time).
        self.game.run_time = main.TIME_IDEAL
        self.game._handle_block_contacts([])
        self.game._continue_run()  # the player clicks CONTINUE to move on


    def _assert_waves_are_distinct(self, ids, wave, name):
        """Every id's waveform is audible, unclipped, and unlike every other."""
        shapes = {}
        for i in ids:
            samples = wave(i)
            self.assertGreater(len(samples), 0)
            peak = float(np.max(np.abs(samples)))
            self.assertGreater(peak, 0.05, f"{name} {i} is silent")
            self.assertLessEqual(peak, 1.0, f"{name} {i} clips")
            shapes[i] = samples / peak  # compare SHAPE, not loudness
        for a, b in itertools.combinations(ids, 2):
            n = min(len(shapes[a]), len(shapes[b]))
            diff = float(np.max(np.abs(shapes[a][:n] - shapes[b][:n])))
            self.assertGreater(diff, 0.2,
                               f"{name} {a} and {b} sound too alike")


    def _new_shapes(self):
        # COMMENTED OUT with the shape itself (user request: "comment out the
        # cradle shape"): main.Shape.CRADLE was the last entry here.
        return (main.Shape.SPIKE, main.Shape.PLATFORM, main.Shape.CORNER,
                main.Shape.PEG, main.Shape.SAWTOOTH)


    def _new_effects(self):
        return (main.Effect.REPULSOR, main.Effect.CONVEYOR, main.Effect.ZIPPER,
                main.Effect.PHASE, main.Effect.SPLITTER)


    # COMMENTED OUT with the conditions: assigning a condition + scorer in the
    # toolbox and pressing S built a card. Cards are whole now, so there is
    # nothing to build (see main.Game's commented-out _build_card).
    #
    # def _assign_and_build(self, condition, scorer):
    #     """Assign a condition + scorer in the toolbox and press S (build)."""
    #     self.game.toolbox.items.clear()
    #     self.game.toolbox.add(condition)
    #     self.game.toolbox.add(scorer)
    #     self.game._select_toolbox_component(condition)
    #     self.game._select_toolbox_component(scorer)
    #     self.game._build_card()


    def _card_fire(self, block, marble=None):
        """Simulate a fresh marble collision with a block (collision cards fire)."""
        for m in self.game.marbles:
            m.collisions_last_tick = []
            m.collisions_this_tick = []
        if marble is None:
            marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        return marble


    def _component_count(self):
        """How many shape/effect/scorer components the toolbox holds.

        Parts rewards land as toolbox components, so this is the count a Parts
        test reads (blocks and card items are ignored).
        """
        kinds = (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)
        return len([i for i in self.game.toolbox.items
                    if getattr(i, "kind", None) in kinds])

    def _complete_run(self, score, required=1000):
        """Finish a run with the given total score against the given target."""
        self.game.marbles = []
        marble = self._add_marble()
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = score
        self.game.score_mult = 1
        self.game.required_score = required
        self.game._handle_block_contacts([])


    def _run_dot_pixel(self, run_index):
        """The screen center of the run dot for the given run index.

        The 8x3 grid lays rounds across (columns) and runs down (rows), so a
        run index maps to col = round, row = run-within-round.
        """
        x0, y0 = main.RUN_DOT_GRID
        col = run_index // main.RUNS_PER_ROUND
        row = run_index % main.RUNS_PER_ROUND
        return (x0 + col * main.RUN_DOT_DX, y0 + row * main.RUN_DOT_DY)


    # --- A placed block's price is the price it was placed with ------------

    def _place_priced_block(self, gx, gy, price):
        """Place a toolbox block bought for ``price`` on the grid, for real."""
        self.game.toolbox.items.clear()
        item = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 30, price, "Pipe +Chips")
        self.game.toolbox.add(item)
        self.game._equip_block(item)
        self._click(self._grid_pos(gx, gy))
        # A real click ends with MOUSEBUTTONUP (which clears `drawing`); the
        # test helper only sends the press, so release it by hand or the next
        # click would place again instead of selecting.
        self.game.drawing = False
        return self.game.grid[(gx, gy)]
