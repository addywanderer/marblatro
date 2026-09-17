import inspect
import itertools
import json
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


def _magnitude_card(condition, scorer):
    """The composed magnitude card value for (condition x unit scorer)."""
    return main.condition_scorer_card(condition, scorer)


# The classic whole cards (Joker, Explorer, ...) and the old shape/effect
# collision cards were removed — every splittable card is now composed from a
# condition + a scorer (see components.condition_scorer_card). These shims make
# ``main.Card.JOKER`` & friends point at the composed magnitude card that now
# plays each removed card's role, so behavior tests keep working unchanged, and
# keep the legacy SCORE_* aliases resolving to the unit scorers.
def _install_card_shims():
    main.Card.JOKER = _magnitude_card(main.Condition.START, main.Scorer.MULT_ADD)
    main.Card.EXPLORER = _magnitude_card(main.Condition.DISTANCE, main.Scorer.MULT_MUL)
    main.Card.ASTRONAUT = _magnitude_card(main.Condition.BLACK_HOLE, main.Scorer.MULT_ADD)
    main.Card.PLANE = _magnitude_card(main.Condition.AIR_TIME, main.Scorer.CHIPS_ADD)
    main.Card.PILLAR = _magnitude_card(main.Condition.FULLEST_COLUMN, main.Scorer.MULT_ADD)
    main.Card.BANKER = _magnitude_card(main.Condition.CASH_HELD, main.Scorer.CHIPS_ADD)
    main.Card.WRECKING_BALL = _magnitude_card(main.Condition.FRAGILE_BREAKS, main.Scorer.MULT_ADD)
    main.Card.SKATER = _magnitude_card(main.Condition.SLIPPERY, main.Scorer.MULT_MUL)
    main.Card.GLITCH = _magnitude_card(main.Condition.RANDOM, main.Scorer.MULT_ADD)
    main.Card.RIPPED_CARD = _magnitude_card(main.Condition.FEW_BLOCKS, main.Scorer.CHIPS_ADD)
    # Legacy score-type aliases -> the unit scorers they correspond to.
    main.Card.SCORE_CHIPS = main.Scorer.CHIPS_ADD
    main.Card.SCORE_MULT = main.Scorer.MULT_ADD
    main.Card.SCORE_XMULT = main.Scorer.MULT_MUL


_install_card_shims()


def _shape_card_value(shape, scorer):
    """The magnitude card for a shape collision condition and a unit scorer."""
    cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
    return main.condition_scorer_card(cond, scorer)


def _effect_card_value(effect, scorer):
    """The magnitude card for an effect collision condition and a unit scorer."""
    cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect)
    return main.condition_scorer_card(cond, scorer)


class RunScoringTests(unittest.TestCase):
    def setUp(self):
        self.game = main.Game()
        self.game.title_screen = False  # skip the title screen in tests
        self.game.trials_enabled = False  # no random trial in generic tests
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

    def tearDown(self):
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

    def test_slope_effect_adds_mult_on_contact(self):
        block = main.Block(0, 0, shape=main.Shape.SLOPE, scorer=main.Scorer.MULT_ADD)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 5)
        self.assertEqual(self.game.score_chips, 0)

    def test_scoring_block_triggers_only_once_per_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        marble = self._add_marble()
        self.game.run_active = True

        # First touch (block is new this tick) -> triggers once.
        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 30)
        self.assertEqual(block.triggers_left, 0)

        # Still touching (block in both last and this tick) -> no retrigger.
        marble.collisions_last_tick = [block]
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 30)

        # Marble releases, then re-touches: the block is exhausted for the run,
        # so it does NOT score again.
        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 30)

    def test_none_shape_block_scores_when_marble_passes_through_cell(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(5, 8)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.centery))
        self.game.run_active = True

        # Entering the cell triggers the scorer once.
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 30)

        # Still inside the cell: no retrigger.
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 30)

    def test_fast_marble_scores_on_none_shape_field(self):
        # A 3000px/s marble crosses the whole 40px field cell within one frame;
        # path sampling must register the contact so the scorer still fires.
        block = main.Block(5, 7, shape=main.Shape.NONE, effect=main.Effect.NONE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(5, 7)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.top - 5))
        marble.velocity = np.array([0.0, 3000.0])
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 10)  # no longer phases through
        self.assertEqual(block.triggers_left, 0)

    def test_none_shape_block_does_not_score_outside_cell(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(5, 8)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.top - 40))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 0)

    def test_none_shape_block_does_not_retrigger_after_leaving_cell(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(5, 8)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.centery))
        self.game.run_active = True
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 30)

        # Move fast leftward out of the cell, then back in: the block is already
        # exhausted for this run, so it does not score again.
        marble.position = np.array([block.rect.right + 60.0, block.rect.centery], dtype=float)
        marble.velocity = np.array([-600.0, 0.0])
        for _ in range(20):
            marble.physics.update(marble, main.DT, list(self.game.grid.values()))
            self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 30)

    def test_trigger_limit_resets_each_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(0, 0)] = block
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        block.triggers_left = 0  # used up during a run

        self.assertTrue(self.game.reset_run())

        self.assertEqual(block.triggers_left, block.trigger_limit)

    def test_moving_broken_fragile_block_restores_original_shape(self):
        # A fragile block that shattered (shape -> NONE) keeps its original
        # shape in _fragile_shape; selecting and moving it must come back as
        # that shape, not a permanent Shape.NONE.
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        block.shape = main.Shape.NONE  # shattered during a run
        block._fragile_shape = main.Shape.RECT
        self.game.grid[(2, 3)] = block

        # Selecting the broken block equips its original shape for moving.
        self._click(self._grid_pos(2, 3))
        self.assertEqual(self.game.selected_shape, main.Shape.RECT)

        # Move it to a new cell.
        self._click(self._grid_pos(4, 4))

        moved = self.game.grid.get((4, 4))
        self.assertIsNotNone(moved)
        self.assertEqual(moved.shape, main.Shape.RECT)  # not NONE
        self.assertIsNone(moved._fragile_shape)  # unbroken, ready to shatter again
        self.assertNotIn((2, 3), self.game.grid)  # original cell emptied

    def test_erasing_broken_fragile_block_refunds_original_shape(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        block.shape = main.Shape.NONE
        block._fragile_shape = main.Shape.RECT
        self.game.grid[(2, 3)] = block

        self.game._erase_block_at(2, 3)

        refunded = self.game.toolbox.items[-1]
        self.assertEqual(refunded.shape, main.Shape.RECT)

    def test_none_scorer_block_still_triggers_for_red_border(self):
        # A Scorer.NONE block grants no chips, but it still "triggers" when a
        # marble touches it, so it shows the used (red border) state.
        block = main.Block(0, 0, scorer=main.Scorer.NONE)
        marble = self._add_marble()
        self.game.run_active = True
        self.assertEqual(block.triggers_left, 1)

        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])

        self.assertEqual(block.triggers_left, 0)  # red border state
        self.assertEqual(self.game.score_chips, 0)  # no score effect
        self.assertEqual(self.game.score_mult, 1)

    def test_none_scorer_block_draws_red_border_after_trigger(self):
        block = main.Block(0, 0, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)

        block.draw(surface)  # untriggered: white border
        self.assertEqual(surface.get_at((1, main.GRID_SIZE // 2))[:3], main.WHITE)

        block.triggers_left = 0  # triggered during a run
        surface.fill((0, 0, 0))
        block.draw(surface)
        self.assertEqual(surface.get_at((1, main.GRID_SIZE // 2))[:3], main.RED)

    def test_block_borders_can_be_toggled_off(self):
        # BLOCK_BORDERS_ON controls the 3px outline (WHITE normally, RED once a
        # block is triggered). Off means no border is drawn at all, and an
        # exhausted block shows its used state by turning its INTERIOR red
        # instead of a red border.
        block = main.Block(0, 0, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        border_px = (1, main.GRID_SIZE // 2)
        try:
            main.BLOCK_BORDERS_ON = True
            block.draw(surface)
            self.assertEqual(surface.get_at(border_px)[:3], main.WHITE)  # border on

            surface.fill((0, 0, 0))
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            self.assertEqual(surface.get_at(border_px)[:3], main.BLACK)  # border hidden
            # The block's fill still renders with the border off.
            self.assertEqual(surface.get_at((main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3],
                             main.BLACK)

            block.triggers_left = 0  # triggered; with borders off the interior turns red
            surface.fill((0, 0, 0))
            block.draw(surface)
            self.assertEqual(surface.get_at(border_px)[:3], main.RED)  # interior red
        finally:
            main.BLOCK_BORDERS_ON = True

    def test_no_effect_block_shape_is_scorer_colored(self):
        # A block with no effect has no center icon, so its shape is filled
        # with its scorer's color instead of a plain black interior.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            self.assertEqual(surface.get_at(
                (main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3], expected)
            self.assertEqual(surface.get_at((2, 2))[:3], expected)
        finally:
            main.BLOCK_BORDERS_ON = prev

    def test_no_effect_none_scorer_block_stays_black(self):
        # A plain wall (no effect, scorer None) keeps the dark wall look.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            self.assertEqual(surface.get_at(
                (main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3], main.BLACK)
        finally:
            main.BLOCK_BORDERS_ON = prev

    def test_no_scorer_line_shapes_draw_black_stroke(self):
        # The thin line shapes draw only a stroke (no fill). A bare no-scorer
        # line block is a plain black wall, matching the black fill of a
        # no-scorer solid shape. A scorer-colored line still paints its
        # scorer's color and a used-up line keeps the red indicator.
        for shape in (main.Shape.LINE, main.Shape.FLAT_LINE,
                      main.Shape.CURVED_SLOPE_LINE, main.Shape.HALF_PIPE):
            block = main.Block(0, 0, shape=shape, scorer=main.Scorer.NONE,
                               origin=(0, 0))
            surface = pygame.Surface([main.GRID_SIZE] * 2)
            surface.fill(main.MARBLE_BOX_COLOR)  # the board behind a wall
            block.draw(surface)
            black_px = [p for p in [(x, y) for x in range(main.GRID_SIZE)
                                    for y in range(main.GRID_SIZE)]
                        if surface.get_at(p)[:3] == main.BLACK]
            self.assertTrue(black_px, f"{shape} no-scorer drew no black stroke")
            # The stroke must be black, never the old white line.
            self.assertFalse(any(surface.get_at(p)[:3] == main.WHITE
                                 for p in black_px),
                             f"{shape} no-scorer line is white")
        # A scorer-colored line keeps its scorer color (not black).
        block = main.Block(0, 0, shape=main.Shape.LINE,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        surface.fill(main.MARBLE_BOX_COLOR)
        block.draw(surface)
        colored = sum(1 for x in range(main.GRID_SIZE) for y in range(main.GRID_SIZE)
                      if surface.get_at((x, y))[:3]
                      == main.Scorer.color(main.Scorer.CHIPS_ADD))
        self.assertGreater(colored, 0)
        # A used-up line keeps the red used indicator.
        block.triggers_left = 0
        surface.fill(main.BLACK)
        block.draw(surface)
        red = sum(1 for x in range(main.GRID_SIZE) for y in range(main.GRID_SIZE)
                  if surface.get_at((x, y))[:3] == main.RED)
        self.assertGreater(red, 0)

    def test_no_effect_block_draws_no_effect_icon(self):
        # _draw_block_effect_icon draws nothing for a no-effect block (its
        # shape carries the scorer color instead).
        plain = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        plain.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        plain._draw_effect_icon(surface)
        self.assertTrue(all(surface.get_at((x, y))[:3] == (0, 0, 0)
                            for x in range(0, main.GRID_SIZE, 2)
                            for y in range(0, main.GRID_SIZE, 2)))

    def test_effect_block_shape_is_scorer_colored_with_black_icon(self):
        # A full block (shape + effect + scorer): the shape fills with the
        # scorer's color and the effect glyph is drawn in black on top.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            self.assertEqual(surface.get_at((2, 2))[:3], expected)      # colored shape
            self.assertEqual(surface.get_at((20, 20))[:3], main.BLACK)  # black icon
        finally:
            main.BLOCK_BORDERS_ON = prev

    def test_no_scorer_effect_block_keeps_black_shape_gray_icon(self):
        # A block with no scorer keeps the original look: a black shape with
        # a gray effect icon on top.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            self.assertEqual(surface.get_at((2, 2))[:3], main.BLACK)  # black shape
            self.assertEqual(surface.get_at((20, 20))[:3],
                             main.Scorer.color(main.Scorer.NONE))     # gray icon
        finally:
            main.BLOCK_BORDERS_ON = prev

    def test_none_shape_with_effect_dots_are_scorer_colored(self):
        # A Shape.NONE block with an effect draws its dotted square in the
        # scorer's color (the effect icon sits inside the dotted face), and the
        # dots are always drawn even when block borders are turned off. The
        # dotted square is inset 3px so it does not stick out of the cell.
        block = main.Block(0, 0, shape=main.Shape.NONE,
                           effect=main.Effect.BLACK_HOLE,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            # The top dashed edge starts 3px in, so (5, 3) is on a dot.
            self.assertEqual(surface.get_at((5, 3))[:3], expected)
            # The inset means the very edge of the cell is not dotted.
            self.assertEqual(surface.get_at((2, 2))[:3], main.BLACK)
        finally:
            main.BLOCK_BORDERS_ON = prev

    def test_none_shape_no_effect_dots_are_scorer_colored(self):
        # A Shape.NONE block with no effect has no icon, so its dotted lines
        # are drawn in the scorer's color (inset 3px inside the cell).
        block = main.Block(0, 0, shape=main.Shape.NONE,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            self.assertEqual(surface.get_at((5, 3))[:3], expected)
            # No effect -> no icon at the center (the background shows).
            self.assertEqual(surface.get_at(
                (main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3], main.BLACK)
        finally:
            main.BLOCK_BORDERS_ON = prev

    def test_board_title_hides_when_mouse_over_board(self):
        # The BOARD title shows while the mouse is outside the board panel and
        # hides while the mouse is over the board.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.assertTrue(self.game._show_marble_box_title())
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.MARBLE_BOX_COORDS[0] + 5,
                                      main.MARBLE_BOX_COORDS[1] + 5)):
            self.assertFalse(self.game._show_marble_box_title())

    def test_inventory_title_hides_when_mouse_over_inventory(self):
        # The INVENTORY title shows while the mouse is outside the inventory
        # panel and hides while the mouse is over it.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.assertTrue(self.game._show_toolbox_title())
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.TOOLBOX_COORDS[0] + 5,
                                      main.TOOLBOX_COORDS[1] + 5)):
            self.assertFalse(self.game._show_toolbox_title())

    def test_shop_title_hides_when_mouse_over_shop(self):
        # The SHOP title shows while the mouse is outside the shop panel and
        # hides while the mouse is over it.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.assertTrue(self.game._show_shop_title())
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.SHOP_COORDS[0] + 5,
                                      main.SHOP_COORDS[1] + 5)):
            self.assertFalse(self.game._show_shop_title())

    def test_titles_render_in_bottom_left_of_their_panels(self):
        # A fresh frame (mouse outside all three panels): BOARD, INVENTORY,
        # and SHOP titles all appear at the bottom-left of their panels.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.draw()
        self.assertTrue(self._region_has_white(self._marble_box_title_region()))
        self.assertTrue(self._region_has_white(self._toolbox_title_region()))
        self.assertTrue(self._region_has_white(self._shop_title_region()))

    def test_panel_titles_hide_when_mouse_over_their_panels(self):
        # Mousing over a panel hides only that panel's bottom-left title.
        # Over the board -> the board title hides, the others stay.
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.MARBLE_BOX_COORDS[0] + 5,
                                      main.MARBLE_BOX_COORDS[1] + 5)):
            self.game.draw()
        self.assertFalse(self._region_has_white(self._marble_box_title_region()))
        self.assertTrue(self._region_has_white(self._toolbox_title_region()))
        self.assertTrue(self._region_has_white(self._shop_title_region()))
        # Over the inventory -> the inventory title hides, the others stay.
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.TOOLBOX_COORDS[0] + 5,
                                      main.TOOLBOX_COORDS[1] + 5)):
            self.game.draw()
        self.assertTrue(self._region_has_white(self._marble_box_title_region()))
        self.assertFalse(self._region_has_white(self._toolbox_title_region()))
        self.assertTrue(self._region_has_white(self._shop_title_region()))
        # Over the shop -> the shop title hides, the others stay.
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.SHOP_COORDS[0] + 5,
                                      main.SHOP_COORDS[1] + 5)):
            self.game.draw()
        self.assertTrue(self._region_has_white(self._marble_box_title_region()))
        self.assertTrue(self._region_has_white(self._toolbox_title_region()))
        self.assertFalse(self._region_has_white(self._shop_title_region()))

    def test_finish_block_marks_marble_and_ends_run_when_all_finished(self):
        finish = main.Block(0, 0, scorer=main.Scorer.FINISH)
        marble = self._add_marble()
        marble.collisions_this_tick = [finish]
        self.game.run_active = True

        self.game._handle_block_contacts([finish])

        self.assertTrue(marble.finished)
        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.run_complete)

    def test_run_continues_until_all_marbles_finish(self):
        finish = main.Block(0, 0, scorer=main.Scorer.FINISH)
        first = self._add_marble()
        second = self._add_marble()
        self.game.run_active = True

        first.collisions_this_tick = [finish]
        self.game._handle_block_contacts([finish])

        self.assertTrue(first.finished)
        self.assertFalse(second.finished)
        self.assertTrue(self.game.run_active)

        second.collisions_this_tick = [finish]
        self.game._handle_block_contacts([finish])

        self.assertTrue(second.finished)
        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.run_complete)

    def test_multiple_marbles_can_use_same_finish(self):
        finish = main.Block(0, 0, scorer=main.Scorer.FINISH)
        first = self._add_marble()
        second = self._add_marble()
        self.game.run_active = True

        first.collisions_this_tick = [finish]
        second.collisions_this_tick = [finish]
        self.game._handle_block_contacts([finish])

        self.assertTrue(first.finished)
        self.assertTrue(second.finished)
        self.assertFalse(self.game.run_active)

    def test_handle_events_places_assembled_block_on_grid_from_mouse_position(self):
        # Assemble a block from assigned components, then place it via a click.
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)
        self.game._assemble_block()
        self.assertTrue(self.game.has_selected)

        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1

        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((1, 1), self.game.grid)
        block = self.game.grid[(1, 1)]
        self.assertEqual(block.shape, main.Shape.RECT)
        self.assertEqual(block.effect, main.Effect.BOUNCY)
        self.assertEqual(block.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(block.rect.x, main.MARBLE_BOX_COORDS[0] + main.GRID_SIZE)
        self.assertEqual(block.rect.y, main.MARBLE_BOX_COORDS[1] + main.GRID_SIZE)

    def test_click_without_selection_does_not_place_block(self):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1

        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertNotIn((1, 1), self.game.grid)

    def test_reset_run_requires_start_and_spawns_one_marble_per_start(self):
        # No start block: cannot start a run.
        self.assertFalse(self.game.reset_run())

        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = main.Block(3, 3, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 2)
        self.assertEqual(self.game.marbles[0].position[0], self.game.grid[(1, 1)].rect.centerx)
        self.assertEqual(self.game.marbles[1].position[0], self.game.grid[(3, 3)].rect.centerx)

    def test_mult_scorer_multiplies_score(self):
        block = main.Block(0, 0, scorer=main.Scorer.MULT_MUL)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 1.5)
        self.assertEqual(self.game.score_chips, 0)

    def test_quick_scorer_adds_chips_based_on_marble_speed(self):
        block = main.Block(0, 0, scorer=main.Scorer.QUICK)
        marble = self._add_marble()
        marble.velocity = np.array([2000.0, 0.0])
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_chips = 0

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_chips, int(2000.0 * main.QUICK_SCALE))
        self.assertEqual(block.triggers_left, 0)  # a scoring block, once per run

    def test_quick_scorer_rewards_faster_marbles_more(self):
        self.game.run_active = True
        gains = []
        for speed in (1000.0, 4000.0):
            block = main.Block(0, 0, scorer=main.Scorer.QUICK)
            marble = self._add_marble()
            marble.velocity = np.array([speed, 0.0])
            marble.collisions_this_tick = [block]
            self.game.score_chips = 0
            self.game._handle_block_contacts([block])
            gains.append(self.game.score_chips)

        self.assertGreater(gains[1], gains[0])

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

    def test_quick_scorer_scores_with_effects_that_pin_marble(self):
        # Effects that hold the marble to rest at the scoring moment (gravity,
        # accelerator, black hole, slippery, fragile) used to read as zero speed
        # and award 0 chips. Quick now measures the marble's recent peak speed
        # at impact, so every effect still scores.
        for eff in (main.Effect.GRAVITY, main.Effect.ACCELERATOR,
                    main.Effect.BLACK_HOLE, main.Effect.SLIPPERY,
                    main.Effect.FRAGILE):
            chips, block = self._run_quick_drop(eff)
            self.assertGreater(chips, 0, f"{main.Effect.name(eff)} Quick should score")
            self.assertEqual(block.triggers_left, 0)

    def test_quick_scorer_scores_on_rotating_block(self):
        chips, block = self._run_quick_drop(main.Effect.ROTATE)
        self.assertGreater(chips, 0, "Rotate Quick should score")
        self.assertEqual(block.triggers_left, 0)

    def test_marble_tracks_recent_speed_during_physics(self):
        game = main.Game()
        game.title_screen = False
        game.run_active = True
        marble = main.Marble(500, 200)
        marble.velocity = np.array([0.0, 2000.0])
        game.marbles.append(marble)
        game.update()
        # The marble's recent peak speed is sampled before collision resolution
        # each physics frame, so it tracks how fast the marble is moving.
        self.assertGreater(marble.recent_speed, 1000)

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

    def test_pipe_scorer_triggers_when_marble_passes_through_gap(self):
        # A marble passing through a pipe's central cavity (without touching
        # the pillars) still triggers the pipe's scorer.
        chips, left = self._pipe_drop()
        self.assertEqual(chips, 30)
        self.assertEqual(left, 0)

    def test_pipe_scorer_triggers_through_rotated_gap(self):
        # The A key rotates a pipe to a horizontal gap; passing through that
        # cavity also triggers the scorer.
        chips, left = self._pipe_drop(angle=90)
        self.assertEqual(chips, 30)
        self.assertEqual(left, 0)

    def test_cash_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.CASH, main.Scorer.ORDER)
        self.assertIn(main.Scorer.CASH, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.CASH), "Cash")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.CASH], 15)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CASH)], 0)
        self.assertIn("$15", main.scorer_description(main.Scorer.CASH, 15))

    def test_cash_scorer_gives_dollars_when_touched(self):
        block = main.Block(0, 0, scorer=main.Scorer.CASH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.cash = 100

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.cash, 115)  # $15 per trigger
        self.assertEqual(block.triggers_left, 0)

    def test_cash_and_lucky_cash_count_to_last_run_cash_gained(self):
        # Cash-scorer and Lucky $40 payouts are added to cash as they happen,
        # tracked in run_cash_gained, and then folded into last_run_cash_gained
        # when the run is awarded — so every dollar earned shows up there.
        self.game.cash = 0
        # Touch a Cash block: +$15.
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        m = self._add_marble()
        m.collisions_this_tick = [cash_block]
        self.game.run_active = True
        self.game._handle_block_contacts([cash_block])
        # Land a Lucky cash roll: +$40.
        lucky = main.Block(0, 0, scorer=main.Scorer.LUCKY)
        m2 = self._add_marble()
        m2.collisions_this_tick = [lucky]
        with mock.patch("main.random.random", side_effect=[0.9, 0.0]):
            self.game._handle_block_contacts([lucky])
        self.assertEqual(self.game.run_cash_gained, 55)
        self.assertEqual(self.game.cash, 55)

        # Award a run with no score-based gain: flat $20 + 10% interest on the
        # 55 held ($5). The whole 55 is folded into last_run_cash_gained.
        self.game.score_total = 1
        self.game._award_cash()
        self.assertEqual(self.game.run_cash_gained, 0)  # folded & cleared
        self.assertEqual(self.game.cash, 55 + 20 + 5)
        self.assertEqual(self.game.last_run_cash_gained, 55 + 20 + 5)

    def test_retry_rolls_back_cash_and_lucky_cash_too(self):
        # Because mid-run Cash/Lucky cash is folded into last_run_cash_gained,
        # retrying the run removes it all — a retry can't farm scorer cash.
        self.game.cash = 0
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        m = self._add_marble()
        m.collisions_this_tick = [cash_block]
        self.game.run_active = True
        self.game._handle_block_contacts([cash_block])  # +$15
        self.game.score_total = 1
        self.game._award_cash()  # $20 + $1 interest folds the $15 in
        self.assertEqual(self.game.last_run_cash_gained, 36)
        self.assertEqual(self.game.cash, 36)
        self.game.run_results.append(True)
        self.game.runs_cleared = 1
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            self.game._retry_run()
        self.assertEqual(self.game.cash, 0)
        self.assertEqual(self.game.last_run_cash_gained, 0)

    def test_restarting_a_run_takes_back_the_cash_its_blocks_paid(self):
        # Cash/Lucky blocks pay into the wallet as they trigger, so restarting
        # the run (R) has to take that cash back out with the run-scoped
        # counter: otherwise resetting a run would be a way to print money.
        self.game.cash = 0
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.run_active = True
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        marble = self._add_marble()
        marble.collisions_this_tick = [cash_block]
        self.game._handle_block_contacts([cash_block])  # +$15
        self.assertEqual(self.game.cash, 15)
        self.assertEqual(self.game.run_cash_gained, 15)

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.run_cash_gained, 0)
        self.assertEqual(self.game.cash, 0)

    def test_restarting_cannot_push_the_wallet_below_zero(self):
        # Cash the discarded run already SPENT is not clawed back — the same
        # rule the free rerolls follow — so a restart never leaves the wallet
        # negative.
        self.game.cash = 0
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.run_active = True
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        marble = self._add_marble()
        marble.collisions_this_tick = [cash_block]
        self.game._handle_block_contacts([cash_block])  # +$15
        self.game.cash = 0  # already spent again on a shop purchase

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.cash, 0)
        self.assertEqual(self.game.run_cash_gained, 0)

    def test_cash_breakdown_records_every_cash_source(self):
        # The breakdown splits a run's earnings into the flat base payment, the
        # interest on the cash held, the over-the-target score bonus, Cash
        # cards, and the Cash/Lucky scorers — and always adds up to the total.
        self.game.trials_enabled = False
        self.game.cash = 100  # -> $10 interest
        self.game.card_cash_run_gain = 15
        self.game.run_cash_gained = 40  # already paid out mid-run
        self.game.score_total = 100
        self.game.required_score = 10
        self.game._award_cash()
        breakdown = self.game.last_run_cash_breakdown
        score_cash = max(0, int(main.CASH_SCALE * (np.log(100) - np.log(10))))
        self.assertEqual(breakdown["base"], 20)
        self.assertEqual(breakdown["interest"], 10)
        self.assertEqual(breakdown["score"], score_cash)
        self.assertEqual(breakdown["cards"], 15)
        self.assertEqual(breakdown["scorers"], 40)
        self.assertEqual(self.game.last_run_cash_gained,
                         sum(breakdown.values()))
        self.assertEqual(self.game.cash, 100 + 20 + 10 + score_cash + 15)
        # A real retry (the results screen's RETRY) undoes the run, so its
        # breakdown goes with it. The save / quit / MAIN MENU paths call
        # _retry_run() too, but while building there is no finished run to
        # undo, so only this awaiting-after-run call rolls anything back.
        cash_before_retry = self.game.cash
        awarded = self.game.last_run_cash_gained
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.last_run_cash_breakdown, {})
        self.assertEqual(self.game.cash, cash_before_retry - awarded)

    def test_saving_mid_build_keeps_the_committed_runs_cash_and_result(self):
        # The save (P) / quit / MAIN MENU paths call _retry_run() while the
        # player is building, where the finished run was already COMMITTED by
        # CONTINUE: its cash award, its result entry and its win/loss all have
        # to survive that (only the results screen's RETRY takes them back).
        self.game.cash = 100
        self.game.score_total = 10000
        self.game.required_score = 1
        self.game._award_cash()          # the finished run's award lands
        cash_after_award = self.game.cash
        awarded = self.game.last_run_cash_gained
        self.game.run_results = [True]
        self.game.runs_cleared = 2
        self.game.failed_runs = 1
        self.game.run_complete = False
        self.game.awaiting_after_run = False   # CONTINUE was already clicked

        self.game._retry_run()                 # the save/quit/menu path

        self.assertEqual(self.game.cash, cash_after_award)
        self.assertEqual(self.game.last_run_cash_gained, awarded)
        self.assertEqual(self.game.run_results, [True])
        self.assertEqual(self.game.runs_cleared, 2)
        self.assertEqual(self.game.failed_runs, 1)

    def test_cash_breakdown_empty_before_the_first_run(self):
        self.game.last_run_cash_breakdown = {}
        rows = self.game._describe_item(main.CASH_BREAKDOWN)
        self.assertEqual([label for label, _ in rows], ["Last run"])
        self.assertIn("No run", rows[0][1])

    def test_cash_readout_hover_opens_the_breakdown(self):
        # Hovering the shop's "Last run cash gained" readout targets the
        # breakdown, which reads like any other item's info box.
        self.game.last_run_cash_gained = 99
        self.game.last_run_cash_breakdown = {"base": 20, "interest": 4,
                                             "score": 30, "cards": 15,
                                             "scorers": 30}
        rect = main.ui.last_run_cash_rect(self.game)
        target, source = self.game._info_target_at(rect.center)
        self.assertIs(target, main.CASH_BREAKDOWN)
        self.assertEqual(source, "cash")
        self.assertEqual(self.game._item_name(target), "Last run cash gained")
        rows = self.game._describe_item(target)
        self.assertEqual([label for label, _ in rows],
                         ["Base cash", "Interest", "Beat the required score",
                          "Cash cards", "Cash/Lucky scorers", "Total"])
        body = " ".join(text for _, text in rows)
        for amount in ("$20", "$4", "$30", "$15", "$99"):
            self.assertIn(amount, body)
        # The box lays out and draws like any other hover box.
        width, height, name_lines, desc_lines, hint = self.game._info_layout(
            target, "cash")
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertEqual(name_lines, ["Last run cash gained"])
        self.assertTrue(desc_lines)
        self.assertEqual(hint, "")
        with mock.patch("main.pygame.mouse.get_pos", return_value=rect.center), \
             mock.patch.object(self.game, "_draw_item_info") as draw:
            self.game.draw_sidebar()
        draw.assert_called_once()
        self.assertIs(draw.call_args[0][0], main.CASH_BREAKDOWN)
        self.assertEqual(draw.call_args[0][1], "cash")

    def test_cash_readout_breakdown_survives_save_and_load(self):
        save_system.start_new_game_in_slot(self.game, 3)
        self.game.trials_enabled = False
        self.game.last_run_cash_gained = 55
        self.game.last_run_cash_breakdown = {"base": 20, "interest": 5,
                                             "score": 0, "cards": 0,
                                             "scorers": 30}
        save_system.save_game(self.game)
        fresh = main.Game()
        save_system.load_slot(fresh, 3)
        self.assertEqual(fresh.last_run_cash_gained, 55)
        self.assertEqual(fresh.last_run_cash_breakdown,
                         {"base": 20, "interest": 5, "score": 0,
                          "cards": 0, "scorers": 30})
        self.assertEqual(sum(fresh.last_run_cash_breakdown.values()), 55)

    def test_sharp_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SHARP, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SHARP, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SHARP), "Sharp")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SHARP], 3)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SHARP)], 0)
        self.assertIn("destroy", main.scorer_description(main.Scorer.SHARP).lower())

    def test_sharp_scorer_triples_mult_when_touched(self):
        block = main.Block(0, 0, scorer=main.Scorer.SHARP)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 3)  # 1 * 3
        self.assertEqual(block.triggers_left, 0)

    def test_sharp_scorer_block_destroyed_on_continue(self):
        # Sharp blocks have a 1/4 chance to be destroyed when the player moves
        # on from a run; non-Sharp blocks always survive.
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.SHARP)
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.SHARP)
        self.game.grid[(3, 3)] = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD,
                                             scorer_amount=10)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.0):  # always destroyed
            self.game._continue_run()
        self.assertNotIn((1, 1), self.game.grid)
        self.assertNotIn((2, 2), self.game.grid)
        self.assertIn((3, 3), self.game.grid)

    def test_sharp_scorer_block_survives_continue_when_lucky(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.SHARP)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):  # no destruction
            self.game._continue_run()
        self.assertIn((1, 1), self.game.grid)

    def test_sharp_scorer_card_destroyed_on_continue(self):
        # Sharp cards (a generic card whose scorer half is Sharp) each have a
        # 1/4 chance to be destroyed after every run; other cards always
        # survive the move-on.
        sharp_pipe = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        sharp_start = main.condition_scorer_card(
            main.Condition.START, main.Scorer.SHARP)
        cash_pipe = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.CASH)
        mult_pipe = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.MULT_ADD)
        self.game.cards = [
            main.CardItem(sharp_pipe, 40), main.CardItem(sharp_start, 40),
            main.CardItem(cash_pipe, 40), main.CardItem(mult_pipe, 40),
        ]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.0):  # always destroyed
            self.game._continue_run()
        values = [card.value for card in self.game.cards]
        self.assertNotIn(sharp_pipe, values)
        self.assertNotIn(sharp_start, values)
        self.assertIn(cash_pipe, values)
        self.assertIn(mult_pipe, values)

    def test_sharp_scorer_card_survives_continue_when_lucky(self):
        sharp = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards = [main.CardItem(sharp, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):  # no destruction
            self.game._continue_run()
        self.assertEqual([card.value for card in self.game.cards], [sharp])

    def test_sharp_scorer_card_survives_retry(self):
        # Retrying a run discards it, so no Sharp card is destroyed (destruction
        # only happens after a run).
        sharp = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards = [main.CardItem(sharp, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.0):
            self.game._retry_run()
        self.assertEqual([card.value for card in self.game.cards], [sharp])

    def test_resource_scorers_are_defined_and_shop_available(self):
        for scorer, name in ((main.Scorer.PARTS, "Parts"), (main.Scorer.SHREDS, "Shreds"),
                             (main.Scorer.RUBBLE, "Rubble"), (main.Scorer.IDEAS, "Ideas")):
            self.assertIn(scorer, main.Scorer.ORDER)
            self.assertIn(scorer, main.Scorer.SHOP_ORDER)
            self.assertEqual(main.Scorer.name(scorer), name)
            self.assertEqual(main.Scorer.DEFAULT_AMOUNT[scorer], 1)
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, scorer)], 0)
            self.assertTrue(main.scorer_description(scorer))

    def test_parts_scorer_grants_a_component_per_trigger(self):
        # Parts grants a random component IMMEDIATELY on each trigger — its
        # old point system is gone (nothing is banked for a run).
        self.game.toolbox.items.clear()
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.PARTS)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        comps = [i for i in self.game.toolbox.items if getattr(i, "kind", None)
                 in (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)]
        self.assertEqual(len(comps), 2)
        self.assertNotIn("point", main.scorer_description(main.Scorer.PARTS).lower())

    def test_parts_scorer_grants_one_component_per_single_trigger(self):
        # Even a lone Parts trigger pays out immediately (no partial bank).
        self.game.toolbox.items.clear()
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.PARTS)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        comps = [i for i in self.game.toolbox.items if getattr(i, "kind", None)
                 in (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)]
        self.assertEqual(len(comps), 1)

    def test_fresh_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.FRESH, main.Scorer.ORDER)
        self.assertIn(main.Scorer.FRESH, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.FRESH), "Fresh")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.FRESH], 1)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.FRESH)], 0)
        self.assertIn("reroll", main.scorer_description(main.Scorer.FRESH).lower())
        # Fresh is also a card scorer: it builds a generic card with any
        # condition (a card that grants a free reroll per trigger).
        self.assertIn(main.Scorer.FRESH, components.CARD_SCORERS)
        self.assertIn(main.Scorer.FRESH, components.FLAT_CARD_SCORERS)
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.FRESH)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.generic_card_meta(value), (main.Condition.SHAPE_PIPE,
                                                          main.Scorer.FRESH))

    def test_fresh_scorer_gives_a_free_reroll_per_hit(self):
        # Fresh grants one free shop reroll IMMEDIATELY per trigger — its old
        # point system is gone (nothing is banked for a run).
        self.game.run_active = True
        for _ in range(3):
            block = main.Block(0, 0, scorer=main.Scorer.FRESH)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 3)

    def test_fresh_single_hit_reroll_is_immediate(self):
        # One Fresh hit is a full reroll right away; there is no partial bank
        # of "fresh points" that waits for a future run.
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 1)

    def test_free_reroll_refreshes_shop_without_cost_then_costs_again(self):
        # A banked free reroll makes the shop refresh cost $0 for one use;
        # after it is spent the usual $20 fee comes back.
        self.game.free_rerolls = 1
        self.game.cash = 0
        self.game._refresh_shop()
        self.assertEqual(self.game.free_rerolls, 0)
        self.assertEqual(self.game.cash, 0)  # no fee charged
        self.assertIn("Free reroll", self.game.shop_message)
        # No free reroll left: the refresh costs the normal fee again.
        self.game.cash = 60
        self.game._refresh_shop()
        self.assertEqual(self.game.cash, 60 - main.SHOP_REFRESH_COST)
        self.assertIn("Refreshed shop", self.game.shop_message)

    def test_fresh_shows_no_resource_point_line(self):
        # Fresh pays instantly, so owning it adds no points-to-next display.
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.FRESH, amount=1))
        self.assertEqual(self.game._resource_display(), [])

    def test_picky_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.PICKY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.PICKY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.PICKY), "Picky")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.PICKY], 1)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.PICKY)], 0)
        self.assertIn("slot", main.scorer_description(main.Scorer.PICKY).lower())
        # Picky is also a card scorer: it builds a generic card with any
        # condition (a card that banks an option point per trigger).
        self.assertIn(main.Scorer.PICKY, components.CARD_SCORERS)
        self.assertIn(main.Scorer.PICKY, components.FLAT_CARD_SCORERS)
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.PICKY)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.generic_card_meta(value), (main.Condition.SHAPE_PIPE,
                                                          main.Scorer.PICKY))

    def test_picky_points_convert_to_bonus_slot_on_continue(self):
        # Two Picky points earned during a run convert into one bonus shop
        # slot after a run.
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.PICKY)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.option_run_gain, 1.0)
        self.assertEqual(self.game.bonus_slots, 0)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.option_run_gain, 0)
        self.assertEqual(self.game.option_points, 0)
        self.assertEqual(self.game.bonus_slots, 1)
        self.assertEqual(self.game.shop.bonus_slots, 1)

    def test_picky_leftover_points_bank_on_continue(self):
        # Points below a whole point stay banked for a future run: three Picky
        # triggers bank 1.5 points, one converts and the 0.5 stays.
        self.game.run_active = True
        for _ in range(3):
            block = main.Block(0, 0, scorer=main.Scorer.PICKY)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.option_run_gain, 1.5)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.option_run_gain, 0)
        self.assertEqual(self.game.option_points, 0.5)  # 1.5 - one point
        self.assertEqual(self.game.bonus_slots, 1)

    def test_bonus_slots_add_extra_random_shop_offers(self):
        # Each banked slot adds one extra offer to the shop, of a uniformly
        # chosen kind (shape/effect/scorer/block/card/action).
        self.game.bonus_slots = 3
        self.game.shop.bonus_slots = 3
        self.game.shop.refresh()
        standard = [i for i in self.game.shop.items if i.row < 5]
        bonus = [i for i in self.game.shop.items if i.row >= 5]
        self.assertEqual(len(standard), 15)
        self.assertEqual(len(bonus), 3)
        allowed = {"shape", "effect", "scorer", "block", "card", "action"}
        for item in bonus:
            self.assertIn(getattr(item, "kind", "block"), allowed)

    def test_bonus_shop_offer_kinds_are_equally_likely(self):
        # Over many rolls, each of the six offer kinds appears a comparable
        # share of the time (each should be near 1/6 of the rolls).
        counts = {}
        for _ in range(1200):
            item = self.game.shop._random_offer(col=1, row=5)
            kind = getattr(item, "kind", "block")
            counts[kind] = counts.get(kind, 0) + 1
        self.assertEqual(sorted(counts), ["action", "block", "card", "effect",
                                          "scorer", "shape"])
        for kind, count in counts.items():
            self.assertGreater(count, 100)
            self.assertLess(count, 340)

    def test_picky_resource_display_shows_slot_when_owned(self):
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.PICKY, amount=1))
        self.game.option_points = 1
        self.assertEqual(self.game._resource_display(), [(1, "slot")])

    def test_shreds_scorer_points_convert_only_on_continue(self):
        # Three shred triggers bank 1/3 of a point each: one whole point, which
        # converts into a random card after a run.
        self.game.cards.clear()
        self.game.run_active = True
        for _ in range(3):
            block = main.Block(0, 0, scorer=main.Scorer.SHREDS)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.shred_run_gain, 1.0)
        self.assertEqual(self.game.cards, [])
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.shred_run_gain, 0)
        self.assertEqual(self.game.shred_points, 0)
        self.assertEqual(len(self.game.cards), 1)

    def test_rubble_scorer_points_convert_only_on_continue(self):
        # Two rubble triggers bank 1/2 a point each: one whole point, which
        # converts into a random block after a run.
        self.game.toolbox.items.clear()
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.RUBBLE)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.rubble_run_gain, 1.0)
        self.assertEqual(self.game.rubble_points, 0)
        blocks = [i for i in self.game.toolbox.items if getattr(i, "kind", None) == "block"]
        self.assertEqual(blocks, [])
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.rubble_run_gain, 0)
        self.assertEqual(self.game.rubble_points, 0)
        blocks = [i for i in self.game.toolbox.items if getattr(i, "kind", None) == "block"]
        self.assertEqual(len(blocks), 1)

    def test_ideas_scorer_points_convert_only_on_continue(self):
        # Two idea points earned during a run convert into one random action
        # after a run.
        self.game.actions.clear()
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.IDEAS)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.idea_run_gain, 1.0)
        self.assertEqual(self.game.actions, [])
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.idea_run_gain, 0)
        self.assertEqual(self.game.idea_points, 0)
        self.assertEqual(len(self.game.actions), 1)

    def test_resource_points_discarded_on_retry(self):
        # A retry is a full do-over for resource points: the run's pending gain
        # AND the points banked from earlier runs are all reset (a NEW run
        # keeps the bank — see test_resource_points_persist_across_runs).
        self.game.toolbox.items.clear()
        self.game.shred_points = 2
        self.game.rubble_points = 3
        self.game.idea_points = 1
        self.game.option_points = 4
        self.game.bonus_slots = 1  # already converted: not a point any more
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.RUBBLE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.rubble_run_gain, 0.5)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.rubble_run_gain, 0)
        self.assertEqual(self.game.shred_run_gain, 0)
        self.assertEqual(self.game.idea_run_gain, 0)
        self.assertEqual(self.game.option_run_gain, 0)
        self.assertEqual(self.game.shred_points, 0)
        self.assertEqual(self.game.rubble_points, 0)
        self.assertEqual(self.game.idea_points, 0)
        self.assertEqual(self.game.option_points, 0)
        # A reward the bank already paid for stays (it is no longer a point).
        self.assertEqual(self.game.bonus_slots, 1)
        blocks = [i for i in self.game.toolbox.items if getattr(i, "kind", None) == "block"]
        self.assertEqual(blocks, [])

    def test_leaving_before_a_run_finishes_keeps_the_resource_bank(self):
        # The save / quit / MAIN MENU paths call _retry_run() while the player
        # is still building, where there is no finished run to undo: the bench
        # of banked points must survive that.
        self.game.shred_points = 3
        self.game.rubble_points = 1
        self.game.idea_points = 2
        self.game.option_points = 1
        self.game.run_complete = False
        self.game.awaiting_after_run = False
        self.game._retry_run()
        self.assertEqual(self.game.shred_points, 3)
        self.assertEqual(self.game.rubble_points, 1)
        self.assertEqual(self.game.idea_points, 2)
        self.assertEqual(self.game.option_points, 1)

    def test_retrying_a_run_takes_back_only_the_rerolls_that_run_granted(self):
        # A retry is a do-over of the FINISHED run, so exactly the free rerolls
        # that run's Fresh hits granted come off the bank — rerolls banked by
        # earlier runs are not the retried run's to lose.
        self.game.free_rerolls = 3  # banked by earlier runs
        self.game.free_rerolls_run_gain = 0
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 4)
        self.assertEqual(self.game.free_rerolls_run_gain, 1)
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(self.game.free_rerolls, 3)  # the other three stay
        self.assertEqual(self.game.free_rerolls_run_gain, 0)
        # A later mid-build call (the save/quit/menu path) can't take them
        # again: the finished run is already undone.
        self.game._retry_run()
        self.assertEqual(self.game.free_rerolls, 3)

    def test_a_retry_cannot_push_the_free_rerolls_below_zero(self):
        # Spending a run's rerolls before retrying does not un-spend them: the
        # bank simply can't go negative.
        self.game.free_rerolls = 0
        self.game.free_rerolls_run_gain = 0
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.FRESH)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls_run_gain, 2)
        self.game.free_rerolls = 0  # both were spent on shop rerolls
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(self.game.free_rerolls, 0)
        # With no banked reroll the refresh charges its cash fee again.
        self.game.cash = 60
        self.game._refresh_shop()
        self.assertEqual(self.game.cash, 60 - main.SHOP_REFRESH_COST)

    def test_a_committed_run_keeps_its_rerolls_through_the_next_reset(self):
        # Each run counts only its own Fresh hits, and a run that has been
        # CONTINUE'd is settled: its counter is cleared at the commit (see
        # _continue_run), so building/starting the NEXT run cannot take that
        # run's rerolls back. Only a RESTARTED run hands its own back (see
        # test_restarting_a_run_takes_back_the_rerolls_its_blocks_granted).
        self.game.free_rerolls = 2
        self.game.free_rerolls_run_gain = 3  # the run being continued
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(self.game.free_rerolls_run_gain, 0)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.free_rerolls, 2)

    def test_restarting_a_run_takes_back_the_rerolls_its_blocks_granted(self):
        # A Fresh hit banks its reroll the moment it triggers, so restarting
        # the run hands that reroll back — while rerolls banked by earlier
        # runs stay, and one already spent is simply not un-spent.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.free_rerolls = 2  # banked by earlier runs
        self.game.free_rerolls_run_gain = 0
        self.game.run_active = True
        block = main.Block(1, 1, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 3)

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.free_rerolls, 2)
        self.assertEqual(self.game.free_rerolls_run_gain, 0)

    def test_leaving_before_a_run_finishes_keeps_the_free_rerolls(self):
        # Same rule as the point banks: saving/quitting/menu while building has
        # no finished run to undo, so a banked free reroll survives it.
        self.game.free_rerolls = 2
        self.game.run_complete = False
        self.game.awaiting_after_run = False

        self.game._retry_run()

        self.assertEqual(self.game.free_rerolls, 2)

    def test_a_new_run_keeps_the_free_rerolls(self):
        # Only a RETRY empties them; starting the next run (or restarting the
        # current one) leaves the bank alone, like the resource points.
        self.game.free_rerolls = 2
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.free_rerolls, 2)

    def test_resource_points_persist_across_runs(self):
        # Banked resource points are not reset when a new run starts, but this
        # run's pending gain is.
        self.game.shred_points = 3
        self.game.rubble_points = 1
        self.game.shred_run_gain = 5
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.shred_points, 3)
        self.assertEqual(self.game.rubble_points, 1)
        self.assertEqual(self.game.shred_run_gain, 0)

    def test_resource_display_shows_when_scorer_owned(self):
        # No point-banked resource scorer owned -> no lines under cash.
        self.assertEqual(self.game._resource_display(), [])
        # Owning the Shreds scorer as a component shows its points-to-next.
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.SHREDS, amount=1))
        self.game.shred_points = 1
        self.assertEqual(self.game._resource_display(), [(1, "card")])
        # Owning the Rubble scorer inside a block shows it too.
        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                             main.Scorer.RUBBLE, 1, 10, "Rubble Rect"))
        self.game.rubble_points = 1
        self.assertEqual(self.game._resource_display(), [(1, "card"), (1, "block")])

    def test_resource_display_shows_for_grid_block(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.IDEAS)
        self.game.idea_points = 3
        self.assertEqual(self.game._resource_display(), [(1, "action")])

    def test_resource_display_counts_pending_run_points(self):
        # While a run is active, points earned this run count toward the next
        # conversion in the display (the reward itself is granted after a run).
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.RUBBLE, amount=1))
        self.game.run_active = True
        self.game.rubble_run_gain = 0.5
        self.assertEqual(self.game._resource_display(), [(0.5, "block")])
        # A whole point pending reads as a fresh countdown (conversion deferred).
        self.game.rubble_run_gain = 1
        self.assertEqual(self.game._resource_display(), [(1, "block")])

    def test_quick_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.QUICK, main.Scorer.ORDER)
        self.assertIn(main.Scorer.QUICK, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.QUICK), "Quick")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.QUICK)], 0)
        self.assertIn("fast", main.scorer_description(main.Scorer.QUICK).lower())

    def test_random_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.RANDOM, main.Scorer.ORDER)
        self.assertIn(main.Scorer.RANDOM, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.RANDOM), "Random")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.RANDOM)], 0)
        self.assertIn("35 chips", main.scorer_description(main.Scorer.RANDOM))

    def _trigger_random_block(self, roll):
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        with mock.patch("main.random.random", return_value=roll):
            self.game._handle_block_contacts([block])
        return block

    def test_random_scorer_chips_branch_adds_thirty_five(self):
        self.game.score_chips = 100
        self.game.score_mult = 2
        self._trigger_random_block(0.0)  # first third -> +35 chips
        self.assertEqual(self.game.score_chips, 135)
        self.assertEqual(self.game.score_mult, 2)
        self.assertEqual(self._trigger_random_block(0.0).triggers_left, 0)

    def test_random_scorer_mult_branch_adds_five(self):
        self.game.score_chips = 100
        self.game.score_mult = 2
        self._trigger_random_block(0.5)  # middle third -> +5 mult
        self.assertEqual(self.game.score_chips, 100)
        self.assertEqual(self.game.score_mult, 7)

    def test_random_scorer_xmult_branch_multiplies_by_one_point_three(self):
        self.game.score_chips = 100
        self.game.score_mult = 2
        self._trigger_random_block(0.9)  # last third -> +0.3 xMult (x1.3)
        self.assertEqual(self.game.score_chips, 100)
        self.assertAlmostEqual(self.game.score_mult, 2 * 1.3)

    def test_random_scorer_uses_all_three_rewards_over_many_triggers(self):
        # Across many random triggers every reward appears (chips/mult/xMult
        # particles are green/blue/red respectively).
        colors = set()
        for _ in range(90):
            block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game.run_active = True
            self.game._handle_block_contacts([block])
            colors.add(self.game.score_particles[-1].color)
        self.assertEqual(colors, {main.GREEN, main.BLUE, main.RED})

    def test_seed_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SEED, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SEED, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SEED), "Seed")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SEED], 3)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SEED)], 0)
        self.assertIn("Seed block", main.scorer_description(main.Scorer.SEED))

    def test_drill_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.DRILL, main.Scorer.ORDER)
        self.assertIn(main.Scorer.DRILL, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.DRILL), "Drill")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.DRILL)], 0)
        self.assertIn("locked", main.scorer_description(main.Scorer.DRILL))

    def test_seed_scorer_gives_mult_for_each_seed_on_board(self):
        # Seed grants +3 mult (scorer_amount) for EVERY Seed block placed on
        # the board, including the touched block itself.
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.SEED)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.SEED)
        self.game.grid[(0, 2)] = main.Block(0, 2, scorer=main.Scorer.MULT_ADD)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([touched])
        # 2 Seed blocks x +3 mult = +6 mult.
        self.assertEqual(self.game.score_mult, 8)
        self.assertEqual(touched.triggers_left, 0)

    def test_seed_with_no_other_seed_counts_itself(self):
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.SEED)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([touched])
        self.assertEqual(self.game.score_mult, 5)  # 1 seed x +3

    def test_garden_card_doubles_the_per_seed_mult(self):
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 46))
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.SEED)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.SEED)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([touched])
        # Garden: +6 mult per seed x 2 seeds = +12 mult.
        self.assertEqual(self.game.score_mult, 14)

    def test_drill_scorer_marks_two_locked_squares_for_continue(self):
        # Touching a Drill block during a run banks two pending locked-square
        # unlocks (granted after a run, discarded on retry).
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.DRILL)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.drill_run_units = 0
        self.game._handle_block_contacts([touched])
        self.assertEqual(self.game.drill_run_units, 2)
        self.assertEqual(touched.triggers_left, 0)

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

    def test_lucky_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.LUCKY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.LUCKY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.LUCKY), "Lucky")
        self.assertEqual(main.Scorer.color(main.Scorer.LUCKY), (255, 185, 0))
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.LUCKY)], 0)
        desc = main.scorer_description(main.Scorer.LUCKY)
        self.assertIn("1/3", desc)
        self.assertIn("130", desc)
        self.assertIn("$40", desc)
        self.assertIn("1/9", desc)

    def test_lucky_can_land_both_rolls_together(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.0, 0.0])  # chips roll hits AND cash roll hits
        self.assertEqual(self.game.score_chips, 230)
        self.assertEqual(self.game.cash, 90)

    def test_lucky_can_land_neither_roll(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.9, 0.9])  # neither roll hits
        self.assertEqual(self.game.score_chips, 100)
        self.assertEqual(self.game.cash, 50)

    def test_lucky_can_land_chips_only(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.1, 0.9])  # chips roll hits, cash roll misses
        self.assertEqual(self.game.score_chips, 230)
        self.assertEqual(self.game.cash, 50)

    def test_lucky_can_land_cash_only(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.9, 0.0])  # chips roll misses, cash roll hits
        self.assertEqual(self.game.score_chips, 100)
        self.assertEqual(self.game.cash, 90)

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

    def test_lucky_keeps_its_pre_rolled_outcome_for_the_whole_run(self):
        # The two Lucky rolls are chosen BEFORE the run (1/3 chips hit, 1/9
        # cash miss here), so the block pays 130 chips on every trigger and
        # never the $40 — even though these draws would have missed both.
        block = main.Block(0, 0, scorer=main.Scorer.LUCKY, trigger_limit=2)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 0
        self.game.cash = 0
        with mock.patch("main.random.random", side_effect=[0.0, 0.9]):
            self.game._roll_run_random_outputs()
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 130)
        self.assertEqual(self.game.cash, 0)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 260)
        self.assertEqual(self.game.cash, 0)
        self.assertEqual(block.triggers_left, 0)

    def test_lucky_cash_roll_repeats_and_counts_in_run_cash(self):
        # The cash roll is pre-rolled too: two triggers of one Lucky block pay
        # $40 twice, and both dollars land in the run's cash gain.
        block = main.Block(0, 0, scorer=main.Scorer.LUCKY, trigger_limit=2)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 0
        self.game.cash = 0
        with mock.patch("main.random.random", side_effect=[0.9, 0.0]):
            self.game._roll_run_random_outputs()
        self._touch_block(block, 0.9)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 0)
        self.assertEqual(self.game.cash, 80)
        self.assertEqual(self.game.run_cash_gained, 80)

    def test_random_block_keeps_one_reward_for_the_whole_run(self):
        # A Random block's reward is chosen before the run (+35 chips here), so
        # its second trigger pays chips again rather than rolling the xMult the
        # patched draw would have given.
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM, trigger_limit=2)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 100
        self.game.score_mult = 1
        with mock.patch("main.random.random", return_value=0.0):
            self.game._roll_run_random_outputs()
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 135)
        self.assertEqual(self.game.score_mult, 1)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 170)
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_retry_keeps_the_pre_rolled_random_outcome(self):
        # Retrying a run replays it, so the pre-rolled result must survive the
        # retry (which resets the run back to build state).
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 100
        self.game.score_mult = 1
        with mock.patch("main.random.random", return_value=0.0):  # +35 chips
            self.game._roll_run_random_outputs()
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            self.game._retry_run()  # must NOT re-roll
        self.assertEqual(block.random_rolls.get("reward"), 0)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 135)
        self.assertEqual(self.game.score_mult, 1)

    def test_a_new_run_rerolls_random_outputs(self):
        # Moving on to the next run chooses fresh outcomes.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        block = main.Block(1, 0, scorer=main.Scorer.RANDOM)
        self.game.grid[(1, 0)] = block
        with mock.patch("main.random.random", return_value=0.9):  # xMult
            self.game.reset_run(True)
        self.assertEqual(block.random_rolls["reward"], 2)
        with mock.patch("main.random.random", return_value=0.0):  # chips
            self.game.reset_run(True)
        self.assertEqual(block.random_rolls["reward"], 0)

    def test_random_items_entering_mid_run_roll_on_first_use(self):
        # A block placed after the opening roll has no stored result, so it
        # rolls on its first trigger and then keeps that result.
        block = main.Block(2, 2, scorer=main.Scorer.RANDOM, trigger_limit=2)
        self.game.grid[(2, 2)] = block
        self.game.score_chips = 100
        self._touch_block(block, 0.0)  # +35 chips
        self.assertEqual(self.game.score_chips, 135)
        self._touch_block(block, 0.9)  # still chips, not xMult
        self.assertEqual(self.game.score_chips, 170)

    def test_roomy_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.ROOMY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.ROOMY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.ROOMY), "Roomy")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.ROOMY], 2)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.ROOMY)], 0)
        desc = main.scorer_description(main.Scorer.ROOMY, 2)
        self.assertIn("2 chips", desc)
        self.assertIn("unlocked board unit", desc)

    def test_roomy_gives_two_chips_per_unlocked_board_unit(self):
        # Roomy pays +2 chips for every unlocked board unit when touched.
        self.game.unlocked_cells = {(0, 0), (0, 1), (1, 0), (1, 1)}  # 4 units
        self.game.score_chips = 100
        block = main.Block(0, 0, scorer=main.Scorer.ROOMY)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 100 + 2 * 4)
        self.assertEqual(block.triggers_left, 0)

    def test_roomy_scales_with_more_unlocked_units(self):
        # A bigger unlocked region pays out proportionally more.
        self.game.unlocked_cells = {(x, y) for x in range(3) for y in range(3)}  # 9 units
        self.game.score_chips = 0
        block = main.Block(0, 0, scorer=main.Scorer.ROOMY)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 2 * 9)

    def test_rally_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.RALLY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.RALLY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.RALLY), "Rally")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.RALLY], 1)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.RALLY)], 0)
        desc = main.scorer_description(main.Scorer.RALLY, 1)
        self.assertIn("1 mult", desc)
        self.assertIn("fresh block touch", desc)

    def test_rally_pays_mult_for_fresh_touches_before_it(self):
        # A Rally block grants +1 mult per fresh block contact this run that
        # happened before it; its own touch never counts.
        self.game.run_active = True
        self.game.score_mult = 2
        first = main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=1)
        rally = main.Block(0, 1, scorer=main.Scorer.RALLY)
        self.game.grid[(0, 0)] = first
        self.game.grid[(0, 1)] = rally
        marble = self._add_marble()
        # Fresh touch #1: the plain mult block scores +1 mult.
        marble.collisions_this_tick = [first]
        self.game._handle_block_contacts([first])
        # Fresh touch #2: Rally pays for the 1 earlier touch.
        marble.collisions_this_tick = [rally]
        self.game._handle_block_contacts([rally])
        self.assertEqual(self.game.score_mult, 2 + 1 + 1)  # first +1, rally +1
        self.assertEqual(self.game.run_fresh_touches, 2)

    def test_rally_counts_re_touches_but_not_its_own(self):
        # Re-touching a block adds another fresh contact, so a later Rally
        # block pays more; its own touch is still excluded.
        self.game.run_active = True
        self.game.score_mult = 1
        first = main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=1)
        rally = main.Block(0, 1, scorer=main.Scorer.RALLY)
        self.game.grid[(0, 0)] = first
        self.game.grid[(0, 1)] = rally
        marble = self._add_marble()
        marble.collisions_this_tick = [first]
        self.game._handle_block_contacts([first])   # touch 1 (+1 mult)
        marble.collisions_this_tick = [first]
        self.game._handle_block_contacts([first])   # touch 2 (re-touch, no score)
        marble.collisions_this_tick = [rally]
        self.game._handle_block_contacts([rally])   # touch 3, pays 2
        self.assertEqual(self.game.score_mult, 1 + 1 + 2)

    def test_rally_touches_reset_each_run(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.run_active = True
        block = main.Block(0, 1, scorer=main.Scorer.MULT_ADD, scorer_amount=1)
        self.game.grid[(0, 1)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.run_fresh_touches, 1)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.run_fresh_touches, 0)

    def test_echo_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.ECHO, main.Scorer.ORDER)
        self.assertIn(main.Scorer.ECHO, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.ECHO), "Echo")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.ECHO], 0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.ECHO)], 0)
        self.assertIn("before it", main.scorer_description(main.Scorer.ECHO))

    def test_echo_refires_the_previous_blocks_scorer(self):
        # Echo replays the scoring effect of the block the marble touched
        # right before it (that previous block also scored normally itself).
        self.game.run_active = True
        self.game.score_chips = 0
        prev = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        echo = main.Block(0, 1, scorer=main.Scorer.ECHO)
        self.game.grid[(0, 0)] = prev
        self.game.grid[(0, 1)] = echo
        marble = self._add_marble()
        marble.collisions_this_tick = [prev]
        self.game._handle_block_contacts([prev])
        marble.collisions_this_tick = [echo]
        self.game._handle_block_contacts([echo])
        self.assertEqual(self.game.score_chips, 10 + 10)
        self.assertEqual(echo.triggers_left, 0)

    def test_echo_ignores_plain_and_role_blocks(self):
        # Echo only copies real scoring blocks: plain (NONE), START/FINISH,
        # and other Echo blocks are skipped, but its own trigger is spent.
        self.game.run_active = True
        self.game.score_mult = 3
        plain = main.Block(0, 0, scorer=main.Scorer.NONE)
        echo = main.Block(0, 1, scorer=main.Scorer.ECHO)
        self.game.grid[(0, 0)] = plain
        self.game.grid[(0, 1)] = echo
        marble = self._add_marble()
        marble.collisions_this_tick = [plain]
        self.game._handle_block_contacts([plain])
        marble.collisions_this_tick = [echo]
        self.game._handle_block_contacts([echo])
        self.assertEqual(self.game.score_mult, 3)
        self.assertEqual(echo.triggers_left, 0)

    def test_powerline_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.POWERLINE, main.Scorer.ORDER)
        self.assertIn(main.Scorer.POWERLINE, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.POWERLINE), "Powerline")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE], 25)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.POWERLINE)], 0)
        desc = main.scorer_description(main.Scorer.POWERLINE, 25)
        self.assertIn("25 chips", desc)
        self.assertIn("row", desc)

    def test_powerline_pays_per_block_in_its_row(self):
        # +25 chips for every block in the same row (including itself); other
        # rows don't count.
        self.game.run_active = True
        self.game.score_chips = 0
        touched = main.Block(1, 0, scorer=main.Scorer.POWERLINE)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.MULT_ADD)
        self.game.grid[(1, 0)] = touched
        self.game.grid[(2, 0)] = main.Block(2, 0, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.CHIPS_ADD)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game._handle_block_contacts([touched])
        self.assertEqual(self.game.score_chips, 25 * 3)  # 3 blocks in row 0

    def test_frontier_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.FRONTIER, main.Scorer.ORDER)
        self.assertIn(main.Scorer.FRONTIER, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.FRONTIER), "Frontier")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.FRONTIER], 3)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.FRONTIER)], 0)
        desc = main.scorer_description(main.Scorer.FRONTIER, 3)
        self.assertIn("3 mult", desc)
        self.assertIn("border", desc)
        self.assertIn("adjacent", desc)

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

    def test_frontier_corner_pays_two_borders_on_a_full_board(self):
        # Fully unlocked board: nothing is locked any more, so a corner block
        # pays only for its two outer borders.
        block = main.Block(0, 0, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(x, y) for x in range(main.GRID_WIDTH)
                                     for y in range(main.GRID_HEIGHT)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 2)
        self.assertEqual(block.triggers_left, 0)

    def test_frontier_edge_pays_one_border_on_a_full_board(self):
        # Fully unlocked board: a non-corner edge block pays for one border.
        block = main.Block(0, 1, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(x, y) for x in range(main.GRID_WIDTH)
                                     for y in range(main.GRID_HEIGHT)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 1)

    def test_frontier_interior_pays_nothing_on_a_full_board(self):
        # Fully unlocked board: an interior block faces no locked unit and no
        # border, so it pays nothing (trigger still spent).
        block = main.Block(1, 1, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(x, y) for x in range(main.GRID_WIDTH)
                                     for y in range(main.GRID_HEIGHT)})
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_frontier_pays_for_locked_neighbours(self):
        # Unlocked region is the L {(0,0), (1,0), (0,1)}. At (1,0) the
        # neighbours are (0,0) unlocked (pays nothing), (1,-1) the outer
        # border, and the two locked squares (2,0)/(1,1) — three units.
        block = main.Block(1, 0, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(0, 0), (1, 0), (0, 1)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 3)

    def test_frontier_surrounded_by_locked_units_pays_four(self):
        # A lone unlocked square in the middle of the board faces locked units
        # on all four sides, so all four directions pay.
        block = main.Block(3, 3, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(3, 3)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 4)

    def test_cluster_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.CLUSTER, main.Scorer.ORDER)
        self.assertIn(main.Scorer.CLUSTER, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.CLUSTER), "Cluster")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.CLUSTER], 4)
        self.assertGreater(
            main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CLUSTER)], 0)
        desc = main.scorer_description(main.Scorer.CLUSTER, 4)
        self.assertIn("4 mult", desc)
        self.assertIn("adjacent", desc)
        # Like its geometry siblings (Powerline/Frontier), Cluster is a block
        # scorer, so it builds no magnitude card — but it IS a card scorer: a
        # generic card pays its payoff for the block the condition hands it.
        self.assertIn(main.Scorer.CLUSTER, components.CARD_SCORERS)
        self.assertIn(main.Scorer.CLUSTER, components.FLAT_CARD_SCORERS)

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

    def test_cluster_pays_four_mult_per_adjacent_block(self):
        # +4 mult for each of the four orthogonal neighbours.
        block = main.Block(2, 2, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ((1, 2), (3, 2), (2, 1), (2, 3)))
        self.assertEqual(self.game.score_mult, 1 + 4 * 4)
        self.assertEqual(block.triggers_left, 0)

    def test_cluster_ignores_diagonal_neighbours(self):
        # A diagonal block is not adjacent: four diagonals pay nothing.
        block = main.Block(2, 2, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ((1, 1), (3, 1), (1, 3), (3, 3)))
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_cluster_counts_only_orthogonal_neighbours(self):
        # Three orthogonal neighbours + all four diagonals -> only the three.
        block = main.Block(2, 2, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ((1, 2), (2, 1), (2, 3),
                                    (1, 1), (3, 1), (1, 3), (3, 3)))
        self.assertEqual(self.game.score_mult, 1 + 4 * 3)

    def test_cluster_alone_gives_nothing(self):
        # A lone Cluster block (and its own cell, which never counts) is worth
        # nothing, but the trigger is still spent.
        block = main.Block(5, 5, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ())
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    # --- Key / Lock pairs ---------------------------------------------------

    def test_key_and_lock_shapes_are_defined_and_distinct(self):
        self.assertIn(main.Shape.KEY, main.Shape.ORDER)
        self.assertIn(main.Shape.LOCK, main.Shape.ORDER)
        self.assertEqual(main.Shape.name(main.Shape.KEY), "Key")
        self.assertEqual(main.Shape.name(main.Shape.LOCK), "Lock")
        self.assertNotEqual(main.Shape.KEY, main.Shape.LOCK)
        self.assertIn("Lock", main.shape_description(main.Shape.KEY))
        self.assertIn("solid", main.shape_description(main.Shape.LOCK))
        for shape in (main.Shape.KEY, main.Shape.LOCK):
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)
            self.assertTrue(main.shape_description(shape))

    def test_paired_shape_pairs_only_key_and_lock(self):
        self.assertEqual(main.paired_shape(main.Shape.KEY), main.Shape.LOCK)
        self.assertEqual(main.paired_shape(main.Shape.LOCK), main.Shape.KEY)
        for shape in main.Shape.ORDER:
            if shape not in (main.Shape.KEY, main.Shape.LOCK):
                self.assertIsNone(main.paired_shape(shape))

    def test_buying_a_lock_block_adds_a_matching_key(self):
        # A Key/Lock block is bought as a matched pair (like a portal): both
        # halves share a fresh key number and the pair costs one price.
        self.game.toolbox.items.clear()
        lock = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 30, "Lock Block")
        self.game.cash = 1000

        self.game._buy_shop_item(lock)

        halves = [i for i in self.game.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual(len(halves), 2)
        self.assertEqual({i.shape for i in halves},
                         {main.Shape.KEY, main.Shape.LOCK})
        self.assertEqual(halves[0].key_number, halves[1].key_number)
        self.assertGreater(halves[0].key_number, 0)
        self.assertEqual(self.game.cash, 1000 - lock.price)  # charged once
        self.assertNotIn(lock, self.game.toolbox.items)

    def test_buying_a_key_block_adds_a_matching_lock(self):
        # The other half works the same way round: a Key-shaped offer brings
        # its Lock.
        self.game.toolbox.items.clear()
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.CHIPS_ADD, 30, 40, "Key +Chips")
        self.game.cash = 1000

        self.game._buy_shop_item(key)

        halves = [i for i in self.game.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual({i.shape for i in halves},
                         {main.Shape.KEY, main.Shape.LOCK})
        # Both halves keep the offer's scorer.
        self.assertEqual({i.scorer for i in halves}, {main.Scorer.CHIPS_ADD})
        self.assertGreater(halves[0].key_number, 0)

    def test_buying_a_key_lock_pair_requires_two_free_slots(self):
        self.game.toolbox.items.clear()
        filler = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.NONE, 0, 5, "filler")
        while len(self.game.toolbox.items) < self.game.toolbox.cols * self.game.toolbox.rows - 1:
            self.game.toolbox.add(filler)
        lock = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 30, "Lock Block")
        self.game.cash = 1000

        self.game._buy_shop_item(lock)

        # Nothing is added and nothing is charged: a lone half is useless.
        self.assertEqual(len(self.game.toolbox.items),
                         self.game.toolbox.cols * self.game.toolbox.rows - 1)
        self.assertEqual(self.game.cash, 1000)
        self.assertTrue(self.game.shop_message)

    def test_assembling_a_lock_shape_adds_its_key_half(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.LOCK)
        scorer_c = main.Component.scorer_component(main.Scorer.NONE)
        for component in (shape_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        halves = [i for i in self.game.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual(len(halves), 2)
        self.assertEqual({i.shape for i in halves},
                         {main.Shape.KEY, main.Shape.LOCK})
        self.assertEqual(halves[0].key_number, halves[1].key_number)
        self.assertGreater(halves[0].key_number, 0)
        self.assertTrue(self.game.has_selected)  # one half is equipped

    def test_assembling_a_plain_shape_stays_a_single_block(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT)
        self.game.toolbox.add(shape_c)
        self.game._use_component(shape_c)

        self.game._assemble_block()

        self.assertEqual(len(self.game.toolbox.items), 1)
        self.assertEqual(self.game.toolbox.items[0].shape, main.Shape.RECT)

    def test_touching_a_key_opens_only_its_own_lock(self):
        key_a = main.Block(1, 1, shape=main.Shape.KEY, key_number=1)
        lock_a = main.Block(1, 2, shape=main.Shape.LOCK, key_number=1)
        key_b = main.Block(2, 1, shape=main.Shape.KEY, key_number=2)
        lock_b = main.Block(2, 2, shape=main.Shape.LOCK, key_number=2)
        for block in (key_a, lock_a, key_b, lock_b):
            self.game.grid[(block.x, block.y)] = block
        self.game.run_active = True
        self.assertTrue(lock_a.locked and lock_b.locked)
        marble = self._add_marble()

        marble.collisions_this_tick = [key_a]
        self.game._handle_block_contacts([key_a])

        self.assertFalse(lock_a.locked)   # its own key opened it
        self.assertTrue(lock_b.locked)    # the other pair stays shut

    def test_a_key_with_no_number_opens_nothing(self):
        # A lone key (e.g. one granted at random, like a lone portal) has no
        # number, so it has no lock to open and touching it is harmless.
        key = main.Block(1, 1, shape=main.Shape.KEY, key_number=0)
        lock = main.Block(1, 2, shape=main.Shape.LOCK, key_number=0)
        self.game.grid[(1, 1)] = key
        self.game.grid[(1, 2)] = lock
        self.game.run_active = True
        marble = self._add_marble()

        marble.collisions_this_tick = [key]
        self.game._handle_block_contacts([key])

        self.assertTrue(lock.locked)

    def test_locks_close_again_at_the_start_of_each_run(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        lock = main.Block(1, 1, shape=main.Shape.LOCK, key_number=5)
        self.game.grid[(1, 1)] = lock

        self.game.reset_run()
        self.assertTrue(lock.locked)
        lock.locked = False  # opened by its key mid-run
        self.game.reset_run()
        self.assertTrue(lock.locked)
        self.assertFalse(self.game.run_blocks_destroyed)
        self.assertFalse(self.game.debt_run_triggered)

    def test_a_placed_lock_starts_locked(self):
        block = main.Block(2, 2, shape=main.Shape.LOCK)
        self.assertTrue(block.locked)
        self.assertFalse(main.Block(2, 2, shape=main.Shape.KEY).locked)
        self.assertFalse(main.Block(2, 2, shape=main.Shape.RECT).locked)

    def test_selling_a_key_half_deletes_its_lock(self):
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key", key_number=7)
        lock = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 10, "Lock", key_number=7)
        other = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 10, "Plain")
        for item in (key, lock, other):
            self.game.toolbox.add(item)

        self.game._equip_block(key)
        self.game._sell_selected_item()

        self.assertNotIn(key, self.game.toolbox.items)
        self.assertNotIn(lock, self.game.toolbox.items)  # the partner went too
        self.assertIn(other, self.game.toolbox.items)

    def test_disassembling_a_placed_lock_deletes_its_key(self):
        self.game.cash = 1000
        self.game.toolbox.items.clear()
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key", key_number=9)
        self.game.toolbox.add(key)
        lock = main.Block(3, 3, shape=main.Shape.LOCK, key_number=9)
        self.game.grid[(3, 3)] = lock
        self.game._equip_block(lock)

        self.game._disassemble_block()

        self.assertNotIn((3, 3), self.game.grid)
        self.assertNotIn(key, self.game.toolbox.items)

    def test_key_numbers_survive_a_save_round_trip(self):
        self.game.toolbox.items.clear()
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key", key_number=4)
        self.game.toolbox.add(key)
        self.game.grid[(1, 1)] = main.Block(1, 1, shape=main.Shape.LOCK,
                                            key_number=4)
        self.game.save_slot = 3
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)

        loaded_lock = fresh.grid[(1, 1)]
        self.assertEqual(loaded_lock.shape, main.Shape.LOCK)
        self.assertEqual(loaded_lock.key_number, 4)
        # A loaded lock is shut again (only a key touch opens it, per run).
        self.assertTrue(loaded_lock.locked)
        keys = [i for i in fresh.toolbox.items
                if getattr(i, "key_number", 0) == 4]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].shape, main.Shape.KEY)

    def test_sidebar_describes_a_key_lock_pair(self):
        item = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 20, "Lock", key_number=5)
        rows = dict(self.game._describe_item(item))
        self.assertIn("Pair", rows)
        self.assertIn("#5", rows["Pair"])
        self.assertIn("Key", rows["Pair"])
        # A placed half describes its pair too.
        block = main.Block(2, 2, shape=main.Shape.KEY, key_number=5)
        self.assertIn("Pair", dict(self.game._describe_item(block)))
        # A block with no pair has no Pair row.
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 20, "Plain")
        self.assertNotIn("Pair", dict(self.game._describe_item(plain)))

    # --- Colossus / Undertaker / Debt ---------------------------------------

    def test_new_scorers_are_defined_and_shop_available(self):
        for scorer, name, amount in ((main.Scorer.COLOSSUS, "Colossus", 0.1),
                                     (main.Scorer.UNDERTAKER, "Undertaker", 15),
                                     (main.Scorer.DEBT, "Debt", 120)):
            self.assertIn(scorer, main.Scorer.ORDER)
            self.assertIn(scorer, main.Scorer.SHOP_ORDER)
            self.assertEqual(main.Scorer.name(scorer), name)
            self.assertEqual(main.Scorer.DEFAULT_AMOUNT[scorer], amount)
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.SCORER, scorer)], 0)
            self.assertTrue(main.scorer_description(scorer, amount))
            # Board/run/marble readers, so they build no magnitude card — but
            # they ARE card scorers: a generic card pays them from the block
            # its condition hands the card (see components.CARD_SCORERS).
            self.assertIn(scorer, components.CARD_SCORERS)
            self.assertIn(scorer, components.FLAT_CARD_SCORERS)

    def test_colossus_description_names_its_payoff(self):
        desc = main.scorer_description(main.Scorer.COLOSSUS, 0.1)
        self.assertIn("0.1", desc)
        self.assertIn("radius", desc)

    def test_colossus_pays_xmult_per_pixel_above_the_base_radius(self):
        # A marble grown to 16 px (8 px above the base 8) pays +0.8 xMult.
        block = main.Block(0, 0, scorer=main.Scorer.COLOSSUS)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 2
        marble = self._add_marble()
        marble.radius = main.MARBLE_RADIUS + 8
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertAlmostEqual(self.game.score_mult, 2 * (1 + 0.1 * 8))
        self.assertEqual(block.triggers_left, 0)

    def test_colossus_keeps_scaling_with_a_huge_marble(self):
        block = main.Block(0, 0, scorer=main.Scorer.COLOSSUS)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.radius = main.MARBLE_RADIUS * 4  # doubled twice by Growing blocks
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertAlmostEqual(self.game.score_mult, 1 + 0.1 * 24)

    def test_colossus_gives_nothing_at_the_base_radius(self):
        # A marble at (or below) its base size gains nothing, but the trigger
        # is still spent.
        block = main.Block(0, 0, scorer=main.Scorer.COLOSSUS)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 3
        marble = self._add_marble()  # radius == MARBLE_RADIUS
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 3)
        self.assertEqual(block.triggers_left, 0)

    def test_undertaker_pays_mult_per_block_destroyed_this_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.UNDERTAKER)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 1
        self.game.run_blocks_destroyed = 2
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 1 + 15 * 2)
        self.assertEqual(block.triggers_left, 0)

    def test_undertaker_gives_nothing_with_no_destroyed_blocks(self):
        block = main.Block(0, 0, scorer=main.Scorer.UNDERTAKER)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_a_fragile_break_counts_as_a_block_destroyed(self):
        self.game.run_active = True
        self.assertEqual(self.game.run_blocks_destroyed, 0)

        self.game._on_fragile_broken(main.Block(0, 0, effect=main.Effect.FRAGILE))

        self.assertEqual(self.game.run_blocks_destroyed, 1)

    def test_a_satanic_death_counts_as_a_block_destroyed(self):
        block = main.Block(1, 1, scorer=main.Scorer.SATANIC, origin=(0, 0))
        block.rect.topleft = (0, 0)
        marble = main.Marble(200, 200)  # far away this frame
        marble.collisions_this_tick = [block]  # ...but it touched last frame
        marble.physics.update(marble, main.DT, [block])
        self.assertTrue(getattr(block, "satanic_leave", False))
        self.game.grid[(1, 1)] = block
        self.game.run_active = True
        self.game.marbles = []

        self.game.update()

        self.assertNotIn((1, 1), self.game.grid)
        self.assertEqual(self.game.run_blocks_destroyed, 1)

    def test_debt_gives_120_chips_and_marks_the_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.DEBT)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_chips = 0
        self.assertFalse(self.game.debt_run_triggered)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_chips, 120)
        self.assertTrue(self.game.debt_run_triggered)
        self.assertEqual(block.triggers_left, 0)

    def test_debt_cancels_the_interest_in_the_run_award(self):
        self.game.cash = 500  # would pay $50 of interest
        self.game.debt_run_triggered = True

        self._complete_run(10000, required=1)

        rows = self.game.last_run_cash_breakdown
        self.assertEqual(rows["interest"], 0)
        self.assertTrue(rows["debt"])
        self.assertIn("Debt", dict(self.game._cash_breakdown_rows())["Interest"])

    def test_interest_still_pays_without_a_debt_block(self):
        self.game.cash = 500

        self._complete_run(10000, required=1)

        rows = self.game.last_run_cash_breakdown
        self.assertEqual(rows["interest"], 50)
        self.assertFalse(rows["debt"])
        self.assertNotIn("Debt", dict(self.game._cash_breakdown_rows())["Interest"])

    def test_retrying_a_run_clears_the_debt_and_undertaker_state(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.debt_run_triggered = True
        self.game.run_blocks_destroyed = 4
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertFalse(self.game.debt_run_triggered)
        self.assertEqual(self.game.run_blocks_destroyed, 0)
        self.assertEqual(self.game.last_run_cash_breakdown, {})

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

    def test_the_nine_utility_whole_cards_are_defined(self):
        expected = [(main.Card.PEDESTAL, "Pedestal", 44),
                    (main.Card.INFERNO, "Inferno", 50),
                    (main.Card.DOPPELGANGER, "Doppelganger", 46),
                    (main.Card.COMPOUND_INTEREST, "Compound Interest", 36),
                    (main.Card.COUPON, "Coupon", 46),
                    (main.Card.FACTORY, "Factory", 44),
                    (main.Card.MINESHAFT, "Mineshaft", 28),
                    (main.Card.MARKET, "Market", 26),
                    (main.Card.WATCH, "Watch", 40)]
        for value, name, price in expected:
            self.assertIn(value, main.Card.ORDER)
            self.assertEqual(main.Card.name(value), name)
            self.assertEqual(main.Card.PRICES[value], price)
            self.assertTrue(main.Card.comment(value))
            self.assertTrue(main.Card.description(value))
            self.assertIn(value, main.Card.COLORS)
            self.assertIn(value, main.Card.GLYPHS)
            # Every whole card is indivisible: no (condition, scorer) rebuilds it.
            self.assertFalse(components.is_splittable_card(value))
            self.assertIsNone(components.splittable_card_condition_scorer(value))
        # The nine ids are unique and never collide with a condition's id (the
        # two namespaces share the space below Condition.SHAPE_BASE, where the
        # only pre-existing overlap is Few Blocks / ERR 404 on id 9).
        new_ids = {value for value, _, _ in expected}
        self.assertEqual(len(new_ids), 9)
        self.assertFalse(new_ids & {c for c in components.CONDITION_ORDER if c < 100})

    def test_pedestal_retriggers_the_first_three_blocks(self):
        self.game.cards.append(main.CardItem(main.Card.PEDESTAL, 44))
        self.game.score_mult = 1
        for i in range(3):
            block = main.Block(i, 5, scorer=main.Scorer.MULT_ADD, scorer_amount=4)
            self._touch_blocks([block])
            # Every one of the first three blocks scored twice (+4 and +4).
            self.assertEqual(self.game.score_mult, 1 + 8 * (i + 1))
        # The fourth block is past the pedestal and scores only once.
        self._touch_blocks([main.Block(4, 5, scorer=main.Scorer.MULT_ADD,
                                       scorer_amount=4)])
        self.assertEqual(self.game.score_mult, 1 + 8 * 3 + 4)

    def test_pedestal_needs_the_card_and_retriggers_only_real_scores(self):
        # Without the card each block scores once.
        self.game.score_mult = 1
        self._touch_blocks([main.Block(0, 5, scorer=main.Scorer.MULT_ADD,
                                       scorer_amount=4)])
        self.assertEqual(self.game.score_mult, 5)
        # With the card a no-scorer block (a plain wall) is retriggered into
        # nothing — it has no scorer to fire twice.
        self.game.cards.append(main.CardItem(main.Card.PEDESTAL, 44))
        self.game.score_mult = 1
        self._touch_blocks([main.Block(1, 5, scorer=main.Scorer.NONE)])
        self.assertEqual(self.game.score_mult, 1)

    def test_inferno_raises_the_total_score_exponent(self):
        self.game.score_chips = 100
        self.game.score_mult = 1
        self.game.run_time = main.TIME_IDEAL
        plain = self.game._compute_total_score()
        self.game.cards.append(main.CardItem(main.Card.INFERNO, 50))
        boosted = self.game._compute_total_score()
        # total = (chips * mult) ** exponent, so Inferno multiplies the score
        # by the base raised to 0.07.
        self.assertAlmostEqual(boosted, plain * (100 * 1) ** 0.07, places=6)
        self.assertGreater(boosted, plain)

    def test_doppelganger_releases_a_second_marble_per_start_block(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(len(self.game.marbles), 1)
        self.assertEqual(float(self.game.marbles[0].velocity[0]), 0.0)

        self.game.cards.append(main.CardItem(main.Card.DOPPELGANGER, 46))
        self.game.reset_run()

        self.assertEqual(len(self.game.marbles), 2)
        first, second = self.game.marbles
        self.assertIs(first.start_block, second.start_block)
        self.assertEqual(float(first.velocity[0]), 0.0)
        self.assertEqual(float(second.velocity[0]), 1.0)  # the new marble drifts
        self.assertEqual(float(second.velocity[1]), 0.0)
        # Both are configured like the save's marble type (same radius/mass).
        self.assertEqual(first.radius, second.radius)
        self.assertEqual(first.mass, second.mass)

    def test_doppelganger_doubles_every_start_block(self):
        # Two Start blocks plus Doppelganger release four marbles.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.grid[(1, 0)] = main.Block(1, 0, scorer=main.Scorer.START)
        self.game.cards.append(main.CardItem(main.Card.DOPPELGANGER, 46))

        self.game.reset_run()

        self.assertEqual(len(self.game.marbles), 4)

    def test_compound_interest_doubles_the_interest(self):
        self.game.cards.append(main.CardItem(main.Card.COMPOUND_INTEREST, 36))
        self.game.cash = 500  # $1 per $10 would pay $50

        self._complete_run(10000, required=1)

        rows = self.game.last_run_cash_breakdown
        self.assertEqual(rows["interest"], 100)
        # The doubled interest really landed in the cash award.
        self.assertEqual(self.game.cash, 500 + rows["base"] + rows["interest"]
                         + rows["score"] + rows["cards"] + rows["scorers"])
        self.assertTrue(rows["debt"] is False)

    def test_debt_still_cancels_compound_interest(self):
        self.game.cards.append(main.CardItem(main.Card.COMPOUND_INTEREST, 36))
        self.game.cash = 500
        self.game.debt_run_triggered = True

        self._complete_run(10000, required=1)

        self.assertEqual(self.game.last_run_cash_breakdown["interest"], 0)

    def test_coupon_discounts_shop_options_but_not_board_units(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 40, "B")
        card = main.CardItem(main.Card.GARDEN, 40)
        component = main.Component.shape_component(main.Shape.RECT)
        self.assertEqual(self.game._buy_price(block), 40)
        self.assertEqual(self.game._buy_price(card), 40)
        self.assertEqual(self.game._buy_price(component), component.price)

        self.game.cards.append(main.CardItem(main.Card.COUPON, 46))

        self.assertEqual(self.game._buy_price(block), 30)     # 40 x 0.75
        self.assertEqual(self.game._buy_price(card), 30)
        self.assertEqual(self.game._buy_price(component),
                         int(component.price * 0.75))
        # Board Units are bought through their own tile, so they are exempt.
        self.assertEqual(self.game._board_unit_price(), main.BOARD_UNIT_PRICE)
        self.game.cash = 100
        self.game._buy_board_unit()
        self.assertEqual(self.game.cash, 100 - main.BOARD_UNIT_PRICE)

    def test_factory_halves_resource_conversion_costs(self):
        # Every conversion costs ONE point, whatever the reward.
        self.assertEqual(self.game._resource_cost(), 1)

        self.game.cards.append(main.CardItem(main.Card.FACTORY, 44))

        # Factory needs half a point instead. That is a real half now that
        # points are fractional, so a single 1/2-point Rubble trigger converts
        # on its own.
        self.assertEqual(self.game._resource_cost(), 0.5)

    def test_factory_converts_resources_at_the_halved_cost(self):
        self.game.cards.append(main.CardItem(main.Card.FACTORY, 44))
        self.game.toolbox.items.clear()
        self.game.rubble_points = 1
        self.game.rubble_run_gain = 0

        self.game._commit_resource_points()

        # One point at half a point per block buys two blocks, not one.
        self.assertEqual(self.game.rubble_points, 0)
        self.assertEqual(len(self.game.toolbox.items), 2)

    def test_mineshaft_makes_board_units_cost_five(self):
        self.assertEqual(self.game._board_unit_price(), 8)

        self.game.cards.append(main.CardItem(main.Card.MINESHAFT, 28))

        self.assertEqual(self.game._board_unit_price(), 5)
        self.game.cash = 5
        self.game._buy_board_unit()
        self.assertEqual(self.game.board_units, 1)
        self.assertEqual(self.game.cash, 0)
        # And $4 is no longer enough.
        self.game.cash = 4
        self.game._buy_board_unit()
        self.assertEqual(self.game.board_units, 1)
        self.assertEqual(self.game.cash, 4)

    def test_market_raises_the_sale_refund_to_three_quarters(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 40, "B")
        self.game.toolbox.add(block)
        self.game.cash = 0
        self.game._equip_block(block)
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, 20)  # half by default

        self.game.cards.append(main.CardItem(main.Card.MARKET, 26))
        marker = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.NONE, 0, 40, "M")
        self.game.toolbox.add(marker)
        self.game._equip_block(marker)
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, 20 + 30)  # 40 x 0.75

        # Cards refund the same fraction.
        card = main.CardItem(main.Card.GARDEN, 40)
        self.game.cards.append(card)
        self.game.selected_toolbox_item = card
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, 50 + 30)
        self.assertNotIn(card, self.game.cards)

    def test_watch_ends_the_run_at_the_ideal_finish_time(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.game.run_time = main.TIME_IDEAL - main.DT

        self.game.update()

        # Without Watch the run is still going at the ideal time ...
        self.assertFalse(self.game.run_complete)
        self.assertTrue(self.game.run_active)
        # ... with Watch it ends right there.
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        self.game.run_time = main.TIME_IDEAL - main.DT
        self.game.update()
        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.awaiting_after_run)

    def test_watch_lets_only_the_first_five_blocks_score(self):
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        self.game.score_mult = 1
        blocks = [main.Block(i, 5, scorer=main.Scorer.MULT_ADD, scorer_amount=4)
                  for i in range(6)]

        self._touch_blocks(blocks)

        # The first five blocks pay +4 each; the sixth pays nothing, though its
        # trigger is still spent (so it shows as used up).
        self.assertEqual(self.game.score_mult, 1 + 4 * 5)
        self.assertEqual(blocks[5].triggers_left, 0)
        self.assertEqual(blocks[4].triggers_left, 0)

    def test_watch_leaves_collision_cards_alone(self):
        # Watch gates the BLOCKS' scorers: a card that reacts to a collision
        # still fires on every matching hit, including past the fifth block.
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        blocks = [main.Block(i, 5, shape=main.Shape.PIPE,
                             scorer=main.Scorer.CHIPS_ADD, scorer_amount=30,
                             trigger_limit=2) for i in range(6)]

        self._touch_blocks(blocks)

        # Five blocks scored their +30 chips; the Pipe card paid on all six.
        self.assertEqual(self.game.score_chips, 5 * 30 + 6 * 30)

    def test_watch_state_resets_each_run(self):
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.run_first_blocks = [main.Block(9, 9, scorer=main.Scorer.NONE)]

        self.game.reset_run()

        self.assertEqual(self.game.run_first_blocks, [])

    # --- The Painting condition ---------------------------------------------

    def test_painting_condition_metadata(self):
        self.assertEqual(main.Condition.name(main.Condition.PAINTING), "Painting")
        self.assertEqual(main.condition_phase(main.Condition.PAINTING), "start")
        self.assertAlmostEqual(components.condition_ratio(main.Condition.PAINTING),
                               0.1)
        self.assertIn("total sell price",
                      main.condition_description(main.Condition.PAINTING))
        self.assertGreater(main.COMPONENT_PRICES[
            (main.Component.CONDITION, main.Condition.PAINTING)], 0)
        # Its id shares the small band with the whole cards without colliding.
        self.assertNotIn(main.Condition.PAINTING, main.Card.ORDER)
        self.assertEqual(main.Condition.GLYPHS[main.Condition.PAINTING], "P")

    def test_board_sell_total_adds_up_each_blocks_sell_price(self):
        priced = main.Block(0, 5, scorer=main.Scorer.NONE)
        priced.resale_price = 30
        self.game.grid[(0, 5)] = priced
        plain = main.Block(1, 5, scorer=main.Scorer.NONE)
        self.game.grid[(1, 5)] = plain
        expected = 30 + main.block_price_for(plain.shape, plain.effects,
                                             plain.scorer)

        self.assertEqual(main.cards.board_sell_total(self.game), expected)
        # An assembled-from-nothing block is worth $0.
        free = main.Block(2, 5, scorer=main.Scorer.NONE)
        free.resale_price = 0
        self.game.grid[(2, 5)] = free
        self.assertEqual(main.cards.board_sell_total(self.game), expected)

    def test_the_deviation_token_is_coloured_by_its_sign(self):
        # The sidebar colours the deviation token: green above the average, red
        # below, grey for exactly average. Only a bare signed number counts, so
        # the game's other parentheses stay plain.
        self.assertEqual(main.ui._deviation_color("(+2)"), main.GREEN)
        self.assertEqual(main.ui._deviation_color("(-1)"), main.RED)
        self.assertEqual(main.ui._deviation_color("(0)"), main.GRAY)
        # A sentence mark after a token belongs to the sentence, not the token:
        # a resource-point row ends its count with one ("Gives 0.7 rubble point
        # (+0.2). 1 point converts into a random block").
        self.assertEqual(main.ui._deviation_color("(+0.2)."), main.GREEN)
        self.assertEqual(main.ui._deviation_color("(-0.2),"), main.RED)
        self.assertEqual(main.ui._deviation_color("(0);"), main.GRAY)
        for word in ("(including", "itself)", "(8", "px)", "(+35", "chips)",
                     "(both", "(1/4", "(2)", "???"):
            self.assertIsNone(main.ui._deviation_color(word), word)

    def test_the_info_box_paints_a_deviation_in_its_colour(self):
        # A rendered block sidebar: the green "(+15)" of a rolled-up +Chips
        # scorer must actually be painted green in the box.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=45)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_item_info(self.game, block, "toolbox", (5, 5))
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(self.game.screen.get_width())
                  for y in range(self.game.screen.get_height())}
        self.assertIn(main.GREEN, colors)
        self.assertNotIn(main.RED, colors)

    def test_the_info_box_paints_a_resource_points_deviation(self):
        # A resource-point row's token is coloured too, even though the sentence
        # carries on after it: "Gives 0.3 rubble point (-0.2). 1 point converts
        # into a random block". Nothing else in the box is red (the labels are
        # green, the body white), so a red pixel proves the token was painted.
        block = main.Block(0, 0, scorer=main.Scorer.RUBBLE, scorer_amount=0.6)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_item_info(self.game, block, "toolbox", (5, 5))
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(self.game.screen.get_width())
                  for y in range(self.game.screen.get_height())}
        self.assertIn(main.RED, colors)

    def test_a_trigger_banks_a_decimal_fraction_of_a_point(self):
        # A trigger banks a fraction of a point and one point always converts:
        # a third for Shreds, a half for the rest, scaled by the scorer's
        # magnitude. The count reads as a decimal, because a rolled magnitude
        # lands off any small fraction's grid — a Rubble trigger's 0.7 points
        # would read "2/3", and a Shreds 1.1/3 would read "1 1/6".
        self.assertEqual(main.points_text(0.5), "0.5")
        self.assertEqual(main.points_text(0.7), "0.7")
        self.assertEqual(main.points_text(1.5), "1.5")
        self.assertEqual(main.points_text(1 / 3), "0.333")
        self.assertEqual(main.points_text(2), "2")
        self.assertEqual(self.game._resource_cost(), 1)
        for scorer, rate in ((main.Scorer.SHREDS, 1 / 3),
                             (main.Scorer.RUBBLE, 0.5),
                             (main.Scorer.IDEAS, 0.5),
                             (main.Scorer.PICKY, 0.5)):
            with self.subTest(scorer=main.Scorer.name(scorer)):
                self.assertAlmostEqual(components.resource_points_for(scorer, 1),
                                       rate)
                # ...and a 3-magnitude scorer banks three times that.
                self.assertAlmostEqual(components.resource_points_for(scorer, 3),
                                       rate * 3)
        # Parts and Fresh grant instantly, so they bank nothing.
        self.assertEqual(components.resource_points_for(main.Scorer.PARTS, 3), 0)
        self.assertEqual(components.resource_points_for(main.Scorer.FRESH, 3), 0)

    def test_a_trigger_banks_the_fraction_the_description_states(self):
        # The description and the bank agree: a 1-magnitude Rubble block says
        # "0.5 rubble point (0)" and banks exactly that.
        block = main.Block(0, 0, scorer=main.Scorer.RUBBLE)
        self.assertIn("0.5 rubble point (0)",
                      main.scorer_description(block.scorer, block.scorer_amount))
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.rubble_run_gain, 0.5)

    def test_a_resource_scorers_deviation_follows_its_point_count(self):
        # The modifier after a resource-point count belongs to THAT count, so it
        # always adds up with the number it sits next to: a Rubble block rolled
        # to 1.4 banks 0.7 points, which is (+0.2) over the 0.5 average — not
        # the (+0.4) its own magnitude is over 1.
        desc = main.scorer_description(main.Scorer.RUBBLE, 1.4)
        self.assertIn("Gives 0.7 rubble point (+0.2).", desc)
        self.assertNotIn("+0.4", desc)
        # A Shreds trigger's third of a point steps by a thirtieth.
        self.assertIn("Gives 0.367 shred point (+0.033).",
                      main.scorer_description(main.Scorer.SHREDS, 1.1))
        self.assertIn("Gives 0.3 shred point (-0.033).",
                      main.scorer_description(main.Scorer.SHREDS, 0.9))
        # An average-magnitude item reads its own count as (0)...
        self.assertIn("Gives 0.5 rubble point (0).",
                      main.scorer_description(main.Scorer.RUBBLE, 1))
        # ...and a composed card with a rolled resource magnitude does too.
        card_text = components._card_payoff_text(main.Condition.START,
                                                 main.Scorer.RUBBLE, 1.4)
        self.assertIn("Gives 0.7 rubble point (+0.2)", card_text)
        # A catalogue card (no rolled magnitude) states no token at all.
        token = re.compile(r"\([+-]?\d+(\.\d+)?\)")
        catalogue = main.Card.description(
            main.condition_scorer_card(main.Condition.START, main.Scorer.RUBBLE))
        self.assertIsNone(token.search(catalogue), catalogue)

    def test_a_bought_pair_keeps_its_effect_magnitudes(self):
        # Regression: a portal (or key/lock) block is bought as a hand-built
        # pair, and both halves used to lose the offer's effect magnitudes.
        for shape, effects in ((main.Shape.RECT, [main.Effect.PORTAL,
                                                  main.Effect.PISTON]),
                               (main.Shape.KEY, [main.Effect.PISTON])):
            with self.subTest(shape=main.Shape.name(shape)):
                self.game.toolbox.items.clear()
                self.game.cash = 1000
                item = main.BlockItem(0, 0, shape, main.Effect.NONE,
                                      main.Scorer.CHIPS_ADD, 30, 40, "pair",
                                      effects=effects,
                                      effect_amounts={main.Effect.PISTON: 2100})

                self.game._buy_shop_item(item)

                halves = [i for i in self.game.toolbox.items
                          if getattr(i, "kind", None) == "block"]
                self.assertEqual(len(halves), 2)
                for half in halves:
                    self.assertEqual(half.effect_magnitude(main.Effect.PISTON), 2100)

    # --- Card magnitudes: a card carries its scorer half's own roll -------

    def test_shop_cards_with_a_scorer_half_roll_a_magnitude(self):
        # A composed card offer (condition x scorer) comes with the scorer
        # half's own rolled magnitude, priced for it; a whole card (Coupon,
        # Showman, ...) has no scorer half and carries none.
        seen = set()
        for _ in range(40):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if getattr(item, "kind", None) != "card":
                    continue
                with self.subTest(card=main.Card.name(item.value)):
                    scorer = main.card_scorer(item.value)
                    if scorer is None:
                        self.assertEqual(item.amount, 0)
                        self.assertEqual(item.price, main.Card.PRICES.get(item.value, 20))
                        continue
                    average = main.Scorer.DEFAULT_AMOUNT[scorer]
                    step = main.magnitude_step(average)
                    if not step:
                        self.assertEqual(item.amount, average)
                    else:
                        floor = main.scorer_magnitude_floor(scorer)
                        self.assertGreaterEqual(item.amount, floor)
                        self.assertLessEqual(item.amount,
                                             average + step * main.MAGNITUDE_MAX_STEPS)
                        if item.amount != floor:
                            self.assertAlmostEqual((item.amount - average) / step,
                                                  round((item.amount - average) / step))
                    seen.add(item.amount)
                    self.assertEqual(item.price,
                                     main.card_price_for(item.value, item.amount))
        # The rolls really vary (a flat average would give one value).
        self.assertGreater(len(seen), 1)

    def test_a_card_pays_its_own_scorer_magnitude(self):
        # A +Chips half rolled to 45 makes the start card add 45 chips, and a
        # +Mult half rolled to 6 adds +6 mult (30 and 4 at the averages).
        chips = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        mult = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        self.game.cards.append(main.make_card_item(chips, amount=45))
        self.game.cards.append(main.make_card_item(mult, amount=6))
        self.game.score_chips = 0
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertEqual(self.game.score_chips, 45)
        self.assertEqual(self.game.score_mult, 7)

    def test_a_card_without_a_magnitude_pays_the_average(self):
        # A card built by hand (or read from an old save) has no magnitude and
        # pays exactly what it always did.
        chips = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(chips, 30))
        self.game.score_chips = 0

        self.game._apply_cards()

        self.assertEqual(self.game.score_chips, 30)
        self.assertEqual(self.game.cards[0].amount, 0)

    def test_a_blueprint_copies_the_magnitude_too(self):
        # A Blueprint copies the card to its left — its value AND its roll.
        mult = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        self.game.cards.append(main.make_card_item(mult, amount=9))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 33))
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertEqual(self.game.score_mult, 1 + 9 + 9)  # both copies pay +9

    def test_a_card_built_from_a_component_keeps_the_pieces_magnitude(self):
        # Building a card consumes the scorer piece, so the card pays the
        # strength that piece was bought at: no laundering a cheap roll into
        # the average card (or the reverse).
        for amount, expected in ((45, 45), (15, 15)):
            with self.subTest(amount=amount):
                self.game.toolbox.items.clear()
                self.game.cards.clear()
                condition = main.Component.condition_component(main.Condition.START)
                scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD,
                                                         amount=amount)
                self.game.toolbox.add(condition)
                self.game.toolbox.add(scorer)
                self.game.card_condition = condition
                self.game.card_scorer = scorer

                self.game._build_card()

                card = self.game.cards[-1]
                self.assertEqual(card.amount, amount)
                self.assertEqual(card.price,
                                 main.card_price_for(card.value, amount))
                self.game.score_chips = 0
                self.game._apply_cards()
                self.assertEqual(self.game.score_chips, expected)

    def test_card_price_and_description_follow_the_magnitude(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        catalog = main.Card.PRICES[value]
        strong = main.make_card_item(value, amount=45)
        weak = main.make_card_item(value, amount=15)

        self.assertGreater(strong.price, catalog)
        self.assertLess(weak.price, catalog)
        rows = dict(self.game._describe_item(strong))
        text = rows[f"Card - {main.Card.name(value)}"]
        self.assertIn("+45 chips (+15)", text)
        # A whole card keeps its catalog text and price.
        coupon = main.make_card_item(main.Card.COUPON)
        self.assertEqual(coupon.amount, 0)
        self.assertEqual(coupon.price, main.Card.PRICES[main.Card.COUPON])
        self.assertEqual(dict(self.game._describe_item(coupon))
                         [f"Card - {main.Card.name(main.Card.COUPON)}"],
                         main.Card.description(main.Card.COUPON))

    def test_flat_scorer_cards_pay_their_own_magnitude(self):
        # Cash pays the card's own amount, and Sharp multiplies by it.
        cash = main.condition_scorer_card(main.Condition.START, main.Scorer.CASH)
        self.game.cards.append(main.make_card_item(cash, amount=24))
        self.game.card_cash_run_gain = 0
        self.game._apply_cards()
        self.assertEqual(self.game.card_cash_run_gain, 24)

        self.game.cards.clear()
        sharp = main.condition_scorer_card(main.Condition.START, main.Scorer.SHARP)
        self.game.cards.append(main.make_card_item(sharp, amount=5))
        self.game.score_mult = 2
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 10)

        # A resource card banks as many points as its magnitude says.
        self.game.cards.clear()
        shreds = main.condition_scorer_card(main.Condition.START, main.Scorer.SHREDS)
        self.game.cards.append(main.make_card_item(shreds, amount=3))
        self.game.shred_points = 0
        self.game.shred_run_gain = 0
        self.game._apply_cards()
        # A 3-magnitude Shreds banks 3 x 1/3 = a whole point.
        self.assertAlmostEqual(self.game.shred_points + self.game.shred_run_gain, 1.0)

    def test_wrecking_ball_banks_three_quarters_of_its_own_magnitude(self):
        # A Fragile Breaks +Mult card rolled to 6 banks 0.75 x 6 = +4.5 mult a
        # break (0.75 x 4 = +3 at the average).
        block = main.Block(1, 1, scorer=main.Scorer.NONE, effects=[main.Effect.FRAGILE])
        value = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS,
                                           main.Scorer.MULT_ADD)
        card = main.make_card_item(value, amount=6)
        self.game.cards.append(card)
        self.game.wrecking_run_gain = {main.Scorer.CHIPS_ADD: 0,
                                       main.Scorer.MULT_ADD: 0,
                                       main.Scorer.MULT_MUL: 1.0}
        self.game.score_mult = 1

        main.cards.on_fragile_broken(self.game, block)

        self.assertEqual(card.amount, 6)
        self.assertAlmostEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 4.5)
        self.assertAlmostEqual(self.game.score_mult, 1)  # no run active

    def test_granted_cards_roll_a_magnitude(self):
        random.seed(7)
        self.game.cards.clear()
        for _ in range(20):
            self.game._grant_random_card()
        composed = [c for c in self.game.cards if main.card_scorer(c.value)]
        self.assertTrue(composed)
        for card in composed:
            scorer = main.card_scorer(card.value)
            self.assertGreaterEqual(card.amount, main.scorer_magnitude_floor(scorer))
            self.assertEqual(card.price, main.card_price_for(card.value, card.amount))

    def test_a_cards_magnitude_round_trips_through_a_save(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        self.game.cash = 100
        card = main.make_card_item(value, amount=45)
        self.game.cards.append(card)

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(save_system, "SAVES_DIR",
                                  os.path.join(tmp, "saves")):
            save_system.save_game(self.game)
            fresh = main.Game()
            fresh.save_slot = self.game.save_slot
            save_system.load_slot(fresh, self.game.save_slot)

        restored = fresh.cards[-1]
        self.assertEqual(restored.value, value)
        self.assertEqual(restored.amount, 45)
        self.assertEqual(restored.price, card.price)
        # An old save (no amount key) reads as a card with no magnitude, which
        # pays the average exactly as it used to.
        old = save_system._deserialize_item({"kind": "card", "value": value,
                                             "price": 30, "col": 0, "row": 0})
        self.assertEqual(old.amount, 0)

    def test_recognition_copies_a_cards_magnitude(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        original = main.make_card_item(value, amount=45)
        self.game.cards.append(original)
        self.game.cash = 1000
        action = main.ActionItem(main.Action.RECOGNITION, 24, version=2)
        self.game.actions.append(action)

        self.assertTrue(self.game._action_recognition(action, original))

        copy = self.game.cards[-1]
        self.assertIsNot(copy, original)
        self.assertEqual(copy.amount, 45)
        self.assertEqual(copy.price, original.price)

    def test_painting_pays_per_dollar_of_board_value(self):
        # A board worth $100 pays +0.4 mult per dollar x 100 = +40 mult.
        for i in range(4):
            block = main.Block(i, 5, scorer=main.Scorer.NONE)
            block.resale_price = 25
            self.game.grid[(i, 5)] = block
        self.assertEqual(main.cards.board_sell_total(self.game), 100)
        value = main.condition_scorer_card(main.Condition.PAINTING,
                                           main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertAlmostEqual(self.game.score_mult, 1 + 0.4 * 100)

    def test_painting_chips_card_scales_the_same_way(self):
        # +Chips pays 3 chips per dollar: a $50 board adds 150 chips.
        block = main.Block(0, 5, scorer=main.Scorer.NONE)
        block.resale_price = 50
        self.game.grid[(0, 5)] = block
        value = main.condition_scorer_card(main.Condition.PAINTING,
                                           main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0

        self.game._apply_cards()

        self.assertEqual(self.game.score_chips, 150)

    # --- Start/Finish blocks are ordinary goods, except the last one -------

    def test_the_last_start_and_finish_blocks_cannot_be_sold(self):
        # One Start block and one Finish block are required to run at all, so
        # the LAST of each is refused even though the shop sells the roles now.
        self.game.toolbox.items.clear()
        start = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 0, "Start")
        finish = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.FINISH, 0, 0, "Finish")
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 20, "Plain")
        for item in (start, finish, plain):
            self.game.toolbox.add(item)
        self.game.cash = 0

        for role in (start, finish):
            self.game._equip_block(role)
            self.game._sell_selected_item()
            self.assertIn(role, self.game.toolbox.items)
            self.assertEqual(self.game.cash, 0)
            self.assertIn("can't be sold", self.game.shop_message)

        # A normal block still sells for half.
        self.game._equip_block(plain)
        self.game._sell_selected_item()
        self.assertNotIn(plain, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 10)

    def test_a_spare_role_block_can_be_sold_but_leaves_the_last_one_in_place(self):
        self.game.toolbox.items.clear()
        first = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 0, "Start A")
        second = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.START, 0, 109, "Start B")
        for item in (first, second):
            self.game.toolbox.add(item)
        self.game.cash = 0

        # While there are two, one can go (half of $109).
        self.game._equip_block(second)
        self.game._sell_selected_item()
        self.assertNotIn(second, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 54)

        # The remaining block is now the only Start the player has.
        self.game._equip_block(first)
        self.game._sell_selected_item()
        self.assertIn(first, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 54)
        self.assertIn("can't be sold", self.game.shop_message)

    def test_a_placed_role_block_counts_toward_the_role_count(self):
        self.game.toolbox.items.clear()
        placed = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = placed
        # The only Start block in the game: not for sale.
        self.assertTrue(self.game._unsellable(placed))

        spare = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 109, "Start Block", effects=[])
        self.game.toolbox.add(spare)
        # Now one of the two is spare, so either may go.
        self.assertFalse(self.game._unsellable(placed))
        self.assertFalse(self.game._unsellable(spare))

    def test_a_role_scorer_component_counts_as_a_way_to_field_the_role(self):
        self.game.toolbox.items.clear()
        component = main.Component.scorer_component(main.Scorer.START)
        self.game.toolbox.add(component)
        # A role component can be assembled back into a role block, so it is
        # the last way to field the role and cannot be sold.
        self.assertTrue(self.game._unsellable(component))

        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                             main.Scorer.START, 0, 109, "Start Block",
                                             effects=[]))
        self.assertFalse(self.game._unsellable(component))

    def test_the_death_action_cannot_sell_the_last_role_block(self):
        action = main.ActionItem(main.Action.DEATH, 48)
        self.game.toolbox.items.clear()
        start = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = start
        self.game.cash = 0

        self.assertFalse(self.game._action_death(action, start))
        self.assertIn((3, 3), self.game.grid)
        self.assertEqual(self.game.cash, 0)
        self.assertIn("can't be sold", self.game.shop_message)

        # Death can still sell a spare role block...
        spare = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 109, "Start Block", effects=[])
        self.game.toolbox.add(spare)
        self.assertTrue(self.game._action_death(action, start))
        self.assertNotIn((3, 3), self.game.grid)
        self.assertGreater(self.game.cash, 100)  # 1.5x a ~$109 role block

        # ...and an ordinary block as before.
        self.game.cash = 0
        plain = main.Block(4, 3, scorer=main.Scorer.NONE)
        self.game.grid[(4, 3)] = plain
        self.assertTrue(self.game._action_death(action, plain))
        self.assertNotIn((4, 3), self.game.grid)
        self.assertGreater(self.game.cash, 0)

    def test_unsellable_covers_role_blocks_and_their_scorer_components(self):
        self.assertTrue(self.game._unsellable(
            main.Block(0, 0, scorer=main.Scorer.START)))
        self.assertTrue(self.game._unsellable(
            main.Block(0, 0, scorer=main.Scorer.FINISH)))
        self.assertTrue(self.game._unsellable(
            main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                           main.Scorer.START, 0, 0, "Start")))
        self.assertTrue(self.game._unsellable(
            main.Component.scorer_component(main.Scorer.START)))
        self.assertTrue(self.game._unsellable(
            main.Component.scorer_component(main.Scorer.FINISH)))
        # Ordinary items are sellable as before.
        self.assertFalse(self.game._unsellable(
            main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)))
        self.assertFalse(self.game._unsellable(
            main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                           main.Scorer.NONE, 0, 20, "Plain")))
        self.assertFalse(self.game._unsellable(
            main.Component.scorer_component(main.Scorer.CHIPS_ADD)))
        self.assertFalse(self.game._unsellable(main.CardItem(main.Card.GARDEN, 36)))

    def test_start_scorer_component_cannot_be_sold(self):
        self.game.toolbox.items.clear()
        component = main.Component.scorer_component(main.Scorer.START)
        self.game.toolbox.add(component)
        self.game.cash = 0

        self.game._equip_block(component)
        self.game._sell_selected_item()

        self.assertIn(component, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 0)

    def test_sell_overlay_draws_no_sale_for_role_blocks(self):
        self.game.toolbox.items.clear()
        start = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 0, "Start")
        self.game.toolbox.add(start)
        self.game._equip_block(start)

        self.game.draw()  # the grey NO SALE overlay renders without raising

        self.assertTrue(self.game._unsellable(self.game.selected_toolbox_item))

    # --- The roles are priced shop goods -----------------------------------

    def test_run_roles_are_priced_shop_goods(self):
        self.assertIn(main.Scorer.START, main.Scorer.SHOP_ORDER)
        self.assertIn(main.Scorer.FINISH, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.START)], 140)
        self.assertEqual(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.FINISH)], 65)
        # A role block is a plain Rect, so its price is the ordinary block
        # formula over Rect + the role (75% of 6 + 0 + role).
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.START), 109)
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.FINISH), 53)
        # Rarity is the inverse of price: Start is the rarer of the two roles.
        self.assertLess(main.component_weight(main.Component.SCORER, main.Scorer.START),
                        main.component_weight(main.Component.SCORER, main.Scorer.FINISH))

    def test_the_starter_role_blocks_match_the_shop_offer(self):
        roles = [item for item in self.game.toolbox.items
                 if getattr(item, "scorer", None) in (main.Scorer.START, main.Scorer.FINISH)]

        self.assertEqual([role.scorer for role in roles],
                         [main.Scorer.START, main.Scorer.FINISH])
        for role in roles:
            self.assertEqual(role.shape, main.Shape.RECT)
            self.assertEqual(role.effects, [])
            self.assertEqual(role.price,
                             main.block_price_for(main.Shape.RECT, [], role.scorer))

    def test_a_drawn_role_scorer_becomes_a_plain_rect_block_in_the_shop(self):
        start = self.game.shop._scorer_offer(main.Scorer.START, 2, 1)

        self.assertEqual(start.kind, "block")
        self.assertEqual(start.shape, main.Shape.RECT)
        self.assertEqual(start.effects, [])
        self.assertEqual(start.scorer, main.Scorer.START)
        self.assertEqual(start.price, 109)
        self.assertEqual(start.name, "Start Block")

        finish = self.game.shop._scorer_offer(main.Scorer.FINISH, 2, 1)
        self.assertEqual(finish.kind, "block")
        self.assertEqual(finish.effects, [])
        self.assertEqual(finish.price, 53)
        self.assertEqual(finish.name, "Finish Block")

        # An ordinary scorer is still offered as a scorer component, carrying
        # its OWN rolled magnitude: a whole number of steps from the average.
        chips = self.game.shop._scorer_offer(main.Scorer.CHIPS_ADD, 2, 1)
        self.assertEqual(chips.kind, main.Component.SCORER)
        self.assertEqual(chips.value, main.Scorer.CHIPS_ADD)
        average = main.Scorer.DEFAULT_AMOUNT[main.Scorer.CHIPS_ADD]
        step = main.magnitude_step(average)
        self.assertAlmostEqual((chips.amount - average) / step,
                              round((chips.amount - average) / step))
        self.assertLessEqual(abs(chips.amount - average),
                             step * main.MAGNITUDE_MAX_STEPS)
        self.assertEqual(chips.price,
                         main.scorer_component_price(main.Scorer.CHIPS_ADD, chips.amount))

    def test_shop_scorer_slots_offer_role_blocks(self):
        def fake_sample(options, weights, k):
            # The scorer slot's pool is the only one holding the role scorers.
            if main.Scorer.START in options:
                return [main.Scorer.START, main.Scorer.FINISH]
            return options[:k]

        with mock.patch("main.weighted_sample_without_replacement", side_effect=fake_sample):
            self.game.shop.refresh()

        roles = [item for item in self.game.shop.items
                 if getattr(item, "scorer", None) in (main.Scorer.START, main.Scorer.FINISH)]
        self.assertEqual([role.scorer for role in roles],
                         [main.Scorer.START, main.Scorer.FINISH])
        for role in roles:
            self.assertEqual(role.shape, main.Shape.RECT)
            self.assertEqual(role.effects, [])
            self.assertNotIn(role.kind, (main.Component.SCORER, "card", "action"))

    def test_role_block_parts_force_rect_and_no_effects(self):
        self.assertEqual(main.role_block_parts(main.Scorer.START, main.Shape.CIRCLE,
                                               [main.Effect.BOUNCY]),
                         (main.Shape.RECT, []))
        self.assertEqual(main.role_block_parts(main.Scorer.FINISH, main.Shape.SLOPE, []),
                         (main.Shape.RECT, []))
        # Every other scorer keeps the parts it rolled.
        self.assertEqual(main.role_block_parts(main.Scorer.CHIPS_ADD, main.Shape.CIRCLE,
                                               [main.Effect.BOUNCY]),
                         (main.Shape.CIRCLE, [main.Effect.BOUNCY]))

    def test_role_block_name_reads_like_the_starter_blocks(self):
        self.assertEqual(main.role_block_name(main.Scorer.START, main.Shape.RECT),
                         "Start Block")
        self.assertEqual(main.role_block_name(main.Scorer.FINISH, main.Shape.RECT),
                         "Finish Block")
        self.assertEqual(main.role_block_name(main.Scorer.CHIPS_ADD, main.Shape.CIRCLE),
                         f"{main.Shape.name(main.Shape.CIRCLE)} "
                         f"{main.Scorer.name(main.Scorer.CHIPS_ADD)}")

    def test_a_bought_role_block_lands_in_the_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        offer = self.game.shop._scorer_offer(main.Scorer.FINISH, 2, 1)

        self.game._buy_shop_item(offer)

        self.assertIn(offer, self.game.toolbox.items)
        self.assertEqual(offer.shape, main.Shape.RECT)
        self.assertEqual(offer.effects, [])
        self.assertLess(self.game.cash, 1000)

    def test_gilded_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.GILDED, main.Scorer.ORDER)
        self.assertIn(main.Scorer.GILDED, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.GILDED), "Gilded")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.GILDED], 0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.GILDED)], 0)
        self.assertIn("1/6", main.scorer_description(main.Scorer.GILDED))

    def test_gilded_adds_one_sixth_of_chips_as_mult(self):
        # 60 chips -> +10 mult (1/6 of the current chips).
        self.game.run_active = True
        self.game.score_chips = 60
        self.game.score_mult = 1
        block = main.Block(0, 0, scorer=main.Scorer.GILDED)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 10)
        self.assertEqual(block.triggers_left, 0)

    def test_bomb_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.BOMB, main.Scorer.ORDER)
        self.assertIn(main.Scorer.BOMB, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.BOMB), "Bomb")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.BOMB], 0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.BOMB)], 0)
        desc = main.scorer_description(main.Scorer.BOMB)
        self.assertIn("after a run", desc)
        self.assertIn("within 1", desc)

    def test_bomb_touch_primes_a_detonation(self):
        # Touching a Bomb during a run banks its cell; it doesn't explode yet.
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.BOMB)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.bomb_cells, {(0, 0)})
        self.assertEqual(block.triggers_left, 0)
        self.assertIn((0, 0), self.game.grid)  # still present mid-run

    def test_every_scorer_color_is_differentiable(self):
        # Every scorer's color must be clearly distinct from every other's:
        # each pair has to differ by at least 50 in at least one RGB channel
        # (e.g. two near-identical grays like old Rubble/Drill, or three
        # same-family blues like +Mult/Random/Summit, would fail this).
        colors = main.Scorer.COLORS
        scorers = list(main.Scorer.ORDER)
        worst = None
        worst_gap = 256
        for i, a in enumerate(scorers):
            for b in scorers[i + 1:]:
                gap = max(abs(colors[a][0] - colors[b][0]),
                          abs(colors[a][1] - colors[b][1]),
                          abs(colors[a][2] - colors[b][2]))
                if gap < worst_gap:
                    worst_gap = gap
                    worst = (main.Scorer.name(a), main.Scorer.name(b))
        self.assertGreaterEqual(
            worst_gap, 50,
            f"Scorer colors too similar: {worst} differ by only {worst_gap} "
            "in every channel")
        self.assertEqual(len(set(colors.values())), len(scorers))  # all unique

    def test_rigged_casino_reweights_random_blocks(self):
        # With the Rigged Casino card, Random blocks roll chips:mult:xMult at
        # 1:3:9 odds instead of the even thirds.
        self.game.cards.append(main.CardItem(main.Card.RIGGED_CASINO, 48))

        def trigger(roll):
            block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
            self.game.grid[(0, 0)] = block
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game.run_active = True
            with mock.patch("main.random.random", return_value=roll):
                self.game._handle_block_contacts([block])
            return block

        # roll 0.05 (< 1/13) -> +35 chips.
        self.game.score_chips = 100
        self.game.score_mult = 2
        trigger(0.05)
        self.assertEqual(self.game.score_chips, 135)
        # roll 0.2 (< 4/13) -> +5 mult.
        trigger(0.2)
        self.assertAlmostEqual(self.game.score_mult, 7)
        # roll 0.5 (>= 4/13) -> the favored +0.3 xMult (x1.3).
        self.game.score_mult = 2
        trigger(0.5)
        self.assertAlmostEqual(self.game.score_mult, 2 * 1.3)

    def test_rigged_casino_card_does_not_affect_plain_random_odds(self):
        # Without the card the even thirds still hold (0.9 -> xMult).
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_mult = 2
        with mock.patch("main.random.random", return_value=0.5):  # middle -> mult
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 7)

    def test_cozy_condition_metadata(self):
        self.assertEqual(main.Condition.name(main.Condition.COZY), "Cozy")
        self.assertEqual(main.condition_phase(main.Condition.COZY), "start")
        self.assertAlmostEqual(components.condition_ratio(main.Condition.COZY), 3.0)
        self.assertIn("10 unlocked", main.condition_description(main.Condition.COZY))
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.CONDITION, main.Condition.COZY)], 0)

    def test_effective_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.EFFECTIVE, main.Scorer.ORDER)
        self.assertIn(main.Scorer.EFFECTIVE, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.EFFECTIVE), "Effective")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.EFFECTIVE], 2.0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.EFFECTIVE)], 0)
        self.assertIn("2 or more effects", main.scorer_description(main.Scorer.EFFECTIVE))

    def test_effective_scorer_gives_xmult_with_two_effects(self):
        block = main.Block(0, 0, effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY],
                           scorer=main.Scorer.EFFECTIVE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 2 * 2.0)  # +1 xMult
        self.assertEqual(block.triggers_left, 0)

    def test_effective_scorer_gives_nothing_with_one_effect(self):
        block = main.Block(0, 0, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.EFFECTIVE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 2)  # no reward
        self.assertEqual(block.triggers_left, 0)    # but the trigger is spent

    def test_random_and_effective_are_card_scorers(self):
        # Random and Effective are now card scorers: they build a generic card
        # with any condition.
        for scorer in (main.Scorer.RANDOM, main.Scorer.EFFECTIVE):
            self.assertIn(scorer, components.CARD_SCORERS)
            self.assertIn(scorer, components.FLAT_CARD_SCORERS)
            value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, scorer)
            self.assertIsNotNone(value)
            self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
            self.assertIn(main.Scorer.name(scorer), main.Card.name(value))

    def test_random_card_fires_random_reward_on_collision(self):
        # A Pipe + Random generic card fires its one pre-rolled reward on every
        # matching pipe collision (the roll is chosen before the run).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.RANDOM)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 100
        self.game.score_mult = 2
        # v2 pipe: the block must still have a trigger left for the second
        # collision, since a collision card only fires while its block can.
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                          trigger_limit=2)
        with mock.patch("cards.random.random", return_value=0.0):  # +35 chips
            self._card_fire(pipe)
        self.assertEqual(self.game.score_chips, 135)
        # A second collision re-uses that same reward (the patched 0.9 would
        # have been +0.3 xMult).
        with mock.patch("cards.random.random", return_value=0.9):
            self._card_fire(pipe, self._add_marble())
        self.assertEqual(self.game.score_chips, 170)
        self.assertEqual(self.game.score_mult, 2)
        # A fresh run re-rolls it, so the card can pay the xMult this time.
        with mock.patch("cards.random.random", return_value=0.9):
            self.game._roll_run_random_outputs()
        self.assertEqual(self.game.cards[-1].random_rolls["reward"], 2)
        fresh_pipe = main.Block(1, 0, shape=main.Shape.PIPE,
                                scorer=main.Scorer.NONE)
        with mock.patch("cards.random.random", return_value=0.0):
            self._card_fire(fresh_pipe, self._add_marble())
        self.assertAlmostEqual(self.game.score_mult, 2 * 1.3)

    def test_effective_collision_card_checks_the_block_effects(self):
        # A Pipe + Effective card grants +1 xMult only when the hit pipe
        # block has 2+ effects.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.EFFECTIVE)
        self.game.cards.append(main.CardItem(value, 40))
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                          effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self.game.score_mult = 2
        self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult, 4.0)  # +1 xMult
        # A pipe with a single effect grants nothing (the mult stays 4.0).
        plain = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY])
        self._card_fire(plain, self._add_marble())
        self.assertAlmostEqual(self.game.score_mult, 4.0)

    def test_effective_start_card_fires_on_first_block_after_start(self):
        # A Start + Effective card can't fire at run start (no block known);
        # it fires once the run's first block is hit, if that block has 2+
        # effects.
        value = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.EFFECTIVE)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 2
        self.game._apply_cards()  # start phase: no block yet, so no reward
        self.assertEqual(self.game.score_mult, 2)
        first = main.Block(0, 0, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self._card_fire(first)
        self.assertAlmostEqual(self.game.score_mult, 4.0)

    def test_effective_end_card_checks_last_block_before_finish(self):
        # A Distance + Effective card checks the last block the marble hit
        # before finishing: +1 xMult when that block has 2+ effects.
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.EFFECTIVE)
        self.game.cards.append(main.CardItem(value, 40))
        # The run has to have travelled for the Distance condition to hold.
        self._add_marble().distance = 4000.0
        last = main.Block(0, 0, scorer=main.Scorer.NONE,
                          effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self.game._last_contact_block = last
        self.game.score_mult = 2
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 4.0)
        # With a single-effect last block it grants nothing.
        plain = main.Block(0, 0, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY])
        self.game._last_contact_block = plain
        self.game.score_mult = 2
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_mult, 2)

    def test_block_composes_shape_effect_and_scorer(self):
        block = main.Block(1, 2, shape=main.Shape.LINE, effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=25)

        self.assertEqual(block.shape, main.Shape.LINE)
        self.assertEqual(block.effect, main.Effect.BOUNCY)
        self.assertEqual(block.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(block.scorer_amount, 25)

    def test_scorer_has_default_amount(self):
        chips = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        mult_add = main.Block(0, 0, scorer=main.Scorer.MULT_ADD)
        mult_mul = main.Block(0, 0, scorer=main.Scorer.MULT_MUL)

        self.assertEqual(chips.scorer_amount, 30)
        self.assertEqual(mult_add.scorer_amount, 4)
        self.assertEqual(mult_mul.scorer_amount, 1.5)

    def test_score_display_draws_with_current_scores(self):
        self.assertGreater(len(main.REQUIRED_SCORES), 0)
        self.game.score_chips = 123
        self.game.score_mult = 4
        self.game.score_total = 492

        # Should render without raising for both below and above the required score.
        self.game.draw()
        self.game.score_total = main.REQUIRED_SCORES[0] + 10
        self.game.draw()

    def test_compute_total_score_is_base_raised_to_linear_exponent(self):
        # base = 300; exponent = (time/2 + dist + uniq) * (4/5), so the total
        # is base ** exponent (chips * mult raised to a linear mix of the
        # run's time, distance, and uniqueness factors).
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE / 2
        self.game.score_chips = 100
        self.game.score_mult = 3
        self.game.run_time = main.TIME_IDEAL  # ideal time -> time_good peaks
        self.game.touched_shapes = {main.Shape.SLOPE}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}  # 3 unique types

        time_good, dist_good, uniq_good, _ = self.game._score_factors()
        exponent = (time_good / 2 + dist_good + uniq_good) * (4 / 5)

        # The total keeps its fractional value internally (rounded only on
        # display), so it equals the raw float base ** exponent.
        self.assertEqual(self.game._compute_total_score(), 300 ** exponent)

    def test_compute_total_score_floor_is_base_to_min_exponent(self):
        # No time/distance/uniqueness -> the exponent drops to ~0, so the
        # score is base ** ~0, essentially 1 (the minimum a run can score).
        # The total is a float now (rounded only on display), so it can sit a
        # hair above 1.0 rather than truncating to exactly 1.
        self.game.score_chips = 50
        self.game.score_mult = 2
        self.game.run_time = 1e6  # far from the ideal time
        total = self.game._compute_total_score()
        self.assertAlmostEqual(total, 1.0)
        self.assertGreaterEqual(total, 1.0)

    def test_compute_total_score_guards_zero_base(self):
        # chips * mult = 0 clamps to a base of 1 so 1 ** anything is 1.
        self.game.score_chips = 0
        self.game.score_mult = 1
        self.game.run_time = 0.0
        self.assertEqual(self.game._compute_total_score(), 1)

    def test_compute_total_score_grows_with_better_run(self):
        # A fast, far, varied run scores strictly higher than a slow, sparse one.
        self.game.score_chips = 50
        self.game.score_mult = 3
        self.game.run_time = 1e6
        self.game.touched_shapes = set()
        self.game.touched_effects = set()
        self.game.touched_scorers = set()
        weak = self.game._compute_total_score()

        self.game.run_time = main.TIME_SCALE  # fast: full time bonus
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE
        self.game.touched_shapes = {main.Shape.RECT, main.Shape.SLOPE, main.Shape.CIRCLE}
        self.game.touched_effects = {main.Effect.BOUNCY, main.Effect.PISTON}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD, main.Scorer.MULT_MUL}
        strong = self.game._compute_total_score()

        self.assertGreater(strong, weak)

    def test_score_factors_are_normalized_zero_to_one(self):
        self.game.run_time = main.TIME_IDEAL  # ideal time -> time_good 1.0
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE * 2
        self.game.touched_shapes = set(main.Shape.ORDER)
        self.game.touched_effects = set(main.Effect.ORDER)
        self.game.touched_scorers = set(main.Scorer.ORDER)

        time_good, dist_good, uniq_good, unique_types = self.game._score_factors()

        self.assertEqual(unique_types,
                         len(main.Shape.ORDER) + len(main.Effect.ORDER) + len(main.Scorer.ORDER))
        # Time peaks just below 1.0 (its modulator makes a zero-length run
        # score 0 on time) and distance saturates toward (but never exceeds)
        # 1.0 via arctan. Uniqueness is LINEAR: uniq_good = unique_types /
        # UNIQUE_SCALE, so it can exceed 1.0 when more than UNIQUE_SCALE types
        # are touched (UNIQUE_SCALE is 1/2 the total component count).
        self.assertAlmostEqual(time_good, 875 / 884, places=6)
        for value in (time_good, dist_good):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
        self.assertEqual(uniq_good, unique_types / main.UNIQUE_SCALE)
        self.assertGreater(dist_good, 0.0)
        self.assertLess(dist_good, 1.0)
        self.assertGreater(uniq_good, 1.0)  # more than UNIQUE_SCALE types touched
        # A zero-length run scores 0 on time (the modulator's purpose).
        self.game.run_time = 0.0
        time_zero, _, _, _ = self.game._score_factors()
        self.assertAlmostEqual(time_zero, 0.0, places=6)

    def test_score_display_draws_unique_count_and_normalized_factors(self):
        # The HUD renders the unique-type count and the D/T/U factor line (each
        # normalized 0..1) without raising.
        self.game.run_time = 2.0
        marble = self._add_marble()
        marble.distance = 500.0
        self.game.touched_shapes = {main.Shape.RECT, main.Shape.SLOPE}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}
        self.game.draw()

    def test_draw_marble_box_spans_w_and_h_cells_from_topleft(self):
        surface = pygame.Surface((400, 400))
        surface.fill((0, 0, 0))
        x, y, w, h = 12, 20, 3, 2
        main.draw_marble_box(surface, x, y, w, h)
        # Background fills the whole panel interior, inside the border frame.
        self.assertEqual(surface.get_at((x + 8, y + 8))[:3], main.MARBLE_BOX_COLOR)
        self.assertEqual(surface.get_at((x + 8, y + main.GRID_SIZE * h - 8))[:3], main.MARBLE_BOX_COLOR)
        self.assertEqual(surface.get_at((x + main.GRID_SIZE * w - 8, y + 8))[:3], main.MARBLE_BOX_COLOR)
        # ...but nothing is drawn well beyond the panel: the border frame is
        # BORD_WIDTH thick and sits just outside each edge (so sample farther
        # out than the old 5px border test did).
        self.assertEqual(surface.get_at((x - 9, y))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((x, y - 9))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((x + main.GRID_SIZE * w + 9, y))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((x, y + main.GRID_SIZE * h + 9))[:3], (0, 0, 0))

    def test_draw_marble_box_draws_thick_outer_border_and_thin_inner_lines(self):
        surface = pygame.Surface((400, 400))
        surface.fill((0, 0, 0))
        x, y, w, h = 12, 12, 2, 2
        main.draw_marble_box(surface, x, y, w, h)
        grid = (30, 30, 30)
        # The thick outer border is drawn just OUTSIDE the panel's edges: each
        # border line is centered ~4px beyond its edge (a frame around the
        # grid), so sample each line's center along the box's midline.
        mid = main.GRID_SIZE  # halfway across the 2x2 panel
        left = x - main.BORD_WIDTH // 2 - 1
        right = x + w * main.GRID_SIZE + main.BORD_WIDTH // 2
        top = y - main.BORD_WIDTH // 2 - 1
        bottom = y + h * main.GRID_SIZE + main.BORD_WIDTH // 2
        self.assertEqual(surface.get_at((left, y + mid))[:3], grid)
        self.assertEqual(surface.get_at((right, y + mid))[:3], grid)
        self.assertEqual(surface.get_at((x + mid, top))[:3], grid)
        self.assertEqual(surface.get_at((x + mid, bottom))[:3], grid)
        # A single thin interior grid line splits the panel in half.
        self.assertEqual(surface.get_at((x + mid, y + mid))[:3], grid)
        self.assertEqual(surface.get_at((x + mid, y + 2))[:3], grid)
        self.assertEqual(surface.get_at((x + 2, y + mid))[:3], grid)

    def test_fire_target_zero_when_run_not_passed(self):
        # No fire while the run hasn't passed the required score (or isn't
        # running at all, e.g. during build or after the run is over).
        self.game.run_active = True
        self.game.score_total = 50
        self.game.required_score = 100
        self.assertEqual(self.game._fire_target(), 0.0)
        self.game.run_active = False
        self.game.score_total = 200  # even a big score after the run is over
        self.assertEqual(self.game._fire_target(), 0.0)

    def test_fire_target_scales_with_how_much_score_passed(self):
        # The fire is larger the more the score beats the required score.
        self.game.run_active = True
        self.game.required_score = 100
        self.game.score_total = 150  # 1.5x -> excess ratio 0.5
        self.assertAlmostEqual(self.game._fire_target(), 0.5)
        self.game.score_total = 200  # 2x -> excess ratio 1.0
        self.assertAlmostEqual(self.game._fire_target(), 1.0)
        self.game.score_total = 400  # 4x -> capped at FIRE_MAX_INTENSITY
        self.assertEqual(self.game._fire_target(), main.FIRE_MAX_INTENSITY)

    def test_fire_rises_when_run_passed_and_dies_after(self):
        # The fire grows toward its target while the run is active and passed,
        # then decays to nothing once the run is over.
        self.game.run_active = True
        self.game.score_total = 200
        self.game.required_score = 100
        for _ in range(60):
            self.game._update_fire(main.DT)  # one second of rising
        self.assertGreater(self.game.fire_intensity, 0.5)
        # The run ends: the fire gradually dies down.
        self.game.run_active = False
        for _ in range(180):
            self.game._update_fire(main.DT)  # three seconds of decay
        self.assertAlmostEqual(self.game.fire_intensity, 0.0)

    def test_fire_clears_on_new_game(self):
        self.game.fire_intensity = 2.0
        self.game.reset_game()
        self.assertEqual(self.game.fire_intensity, 0.0)

    def test_fire_draws_flames_when_passing(self):
        self.game.fire_intensity = 1.0
        self.game.draw()  # renders the flames along the top edge without raising

    def test_make_icon_draws_a_block_filling_the_surface(self):
        icon = main.make_icon()
        self.assertEqual(icon.get_size(), (main.GRID_SIZE, main.GRID_SIZE))
        # Something is really drawn, whatever random block the icon rolled:
        # at least one opaque pixel exists.
        self.assertTrue(any(icon.get_at((x, y))[3] > 0
                            for x in range(main.GRID_SIZE)
                            for y in range(main.GRID_SIZE)))
        # The "more than one colour" check is done on a FIXED block instead of
        # the random roll: peg + black hole (and any solid shape with borders
        # off) legitimately fills its cell with a single flat colour, which made
        # this test fail whenever the icon happened to roll one of those.
        prev = main.BLOCK_BORDERS_ON
        main.BLOCK_BORDERS_ON = True
        try:
            icon = pygame.Surface([main.GRID_SIZE] * 2, pygame.SRCALPHA)
            main.ui.draw_block(main.Block(0, 0, shape=main.Shape.RECT,
                                          effect=main.Effect.BOUNCY,
                                          scorer=main.Scorer.CHIPS_ADD,
                                          origin=(0, 0)), icon)
        finally:
            main.BLOCK_BORDERS_ON = prev
        colours = {icon.get_at((x, y))[:3] for x in range(main.GRID_SIZE)
                   for y in range(main.GRID_SIZE)}
        self.assertGreater(len(colours), 1)

    def test_make_icon_accepts_all_blocks_without_raising(self):
        # Every shape/effect/scorer combination must render onto the icon.
        for shape in main.Shape.ORDER:
            for effect in main.Effect.ORDER:
                for scorer in main.Scorer.ORDER:
                    icon = pygame.Surface([main.GRID_SIZE] * 2)
                    main.Block(0, 0, shape=shape, effect=effect, scorer=scorer,
                               origin=(0, 0)).draw(icon)

    def test_every_condition_and_component_has_a_price(self):
        # A component missing from COMPONENT_PRICES is priced 0, which makes it
        # free in the shop and the most common draw (rarity weight = 1/price).
        for condition in main.CONDITION_ORDER:
            price = main.COMPONENT_PRICES.get((main.Component.CONDITION, condition))
            self.assertIsNotNone(price,
                                 f"{main.Condition.name(condition)} has no price")
            self.assertGreater(price, 0,
                               f"{main.Condition.name(condition)} is priced 0")
            self.assertGreater(main.component_weight(main.Component.CONDITION, condition),
                               0)
        for shape in main.Shape.ORDER:
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)
        for effect in main.Effect.ORDER:
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, effect)], 0)
        for scorer in main.Scorer.ORDER:
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, scorer)], 0)

    def test_every_named_condition_and_whole_card_has_icon_art(self):
        # Every named condition, whole card and action must draw SOMETHING onto
        # its icon surface: a new item with no art branch renders as a blank
        # tile (a condition would fall back to its letter glyph, but an action
        # icon is the only thing on the tile besides the version badge).
        for condition in components.NAMED_CONDITION_ORDER:
            art = main.ui._build_named_condition_art(condition)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               f"no icon art for condition "
                               f"{main.Condition.name(condition)}")
        for card in main.Card.ORDER:
            art = main.ui._build_whole_card_art(card)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               f"no icon art for card {main.Card.name(card)}")
        for action in main.Action.ORDER:
            art = main.ui._build_action_art(action)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               f"no icon art for action {main.Action.name(action)}")
            # And each action's tile renders its icon (never the letter glyph).
            self.assertTrue(main.ui._draw_action_icon(
                pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA),
                action, (main.GRID_SIZE // 2, main.GRID_SIZE // 2),
                main.GRID_SIZE))
        # draw_action draws every action (shop/action area/info box/collection).
        canvas = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA)
        for action in main.Action.ORDER:
            main.ui.draw_action(canvas, main.ActionItem(action, 24),
                                pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE))

    def test_marble_accumulates_distance(self):
        marble = self._add_marble()
        marble.velocity = np.array([60.0, 0.0])
        marble.physics.update(marble, main.DT, [])
        self.assertGreater(marble.distance, 0.5)

    def test_descriptions_exist_for_all_shapes_effects_scorers(self):
        for shape in main.Shape.ORDER:
            self.assertTrue(main.shape_description(shape))
        for effect in main.Effect.ORDER:
            self.assertTrue(main.effect_description(effect))
        for scorer in main.Scorer.ORDER:
            self.assertTrue(main.scorer_description(scorer, main.Scorer.DEFAULT_AMOUNT.get(scorer, 0)))

    def test_sidebar_describes_block_components_independently(self):
        item = main.BlockItem(0, 0, main.Shape.CURVED_SLOPE, main.Effect.GRAVITY,
                              main.Scorer.CHIPS_ADD, 10, 20, "Curved Slope +Chips")
        rows = self.game._describe_item(item)
        self.assertEqual([label for label, _ in rows],
                         ["Shape - Curved Slope", "Effect - Gravity", "Scorer - +Chips", "Trigger"])
        self.assertIn("arc", main.shape_description(item.shape))
        self.assertIn("gravity", main.effect_description(item.effect).lower())
        self.assertIn("10", main.scorer_description(item.scorer, item.scorer_amount))

    def test_sidebar_describes_component(self):
        shape = main.Component.shape_component(main.Shape.SLOPE)
        self.assertEqual([label for label, _ in self.game._describe_item(shape)], ["Shape - Slope"])
        effect = main.Component.effect_component(main.Effect.BOUNCY)
        self.assertEqual([label for label, _ in self.game._describe_item(effect)], ["Effect - Bouncy"])
        scorer = main.Component.scorer_component(main.Scorer.MULT_MUL, amount=3)
        self.assertEqual([label for label, _ in self.game._describe_item(scorer)], ["Scorer - xMult"])

    def test_info_box_targets_hovered_shop_item_without_buying(self):
        item = self.game.shop.items[0]
        cash_before = self.game.cash
        pos = (self.game.shop.rect.x + item.col * main.GRID_SIZE + 5,
               self.game.shop.rect.y + item.row * main.GRID_SIZE + 5)
        target, source = self.game._info_target_at(pos)
        self.assertIs(target, item)
        self.assertEqual(source, "shop")
        self.assertEqual(self.game.cash, cash_before)

    def test_info_box_layout_describes_item(self):
        # The hover info box lays out the item's name, price, description
        # rows, and a per-item action hint.
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        width, height, name_lines, desc_lines, hint = self.game._info_layout(block, "toolbox")
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertTrue(name_lines)
        self.assertTrue(desc_lines)
        self.assertTrue(hint)

    def test_draw_sidebar_is_noop_without_hovered_item(self):
        # The info box only appears when the cursor is over an item; hovering
        # empty space draws nothing.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)), \
             mock.patch.object(self.game, "_draw_item_info") as draw:
            self.game.draw_sidebar()
        draw.assert_not_called()

    def test_draw_sidebar_renders_hovered_item(self):
        # Hovering over a toolbox item draws its info box.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        pos = (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5)
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch.object(self.game, "_draw_item_info") as draw:
            self.game.draw_sidebar()
        draw.assert_called_once()
        self.assertIs(draw.call_args[0][0], block)
        self.assertEqual(draw.call_args[0][1], "toolbox")

    def test_info_box_size_scales_with_description(self):
        # The box is sized to the description: an item with more effects and
        # more description text produces a taller (and wider) box.
        short = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "S")
        long = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 20, "L",
                              effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE,
                                       main.Effect.GRAVITY, main.Effect.BOUNCY,
                                       main.Effect.ROTATE])
        w1, h1, *_ = self.game._info_layout(short, "toolbox")
        w2, h2, *_ = self.game._info_layout(long, "toolbox")
        self.assertGreater(h2, h1)  # more description rows -> taller box
        self.assertGreaterEqual(w2, w1)

    def test_info_box_rect_stays_onscreen(self):
        # A box near a screen edge is clamped so it stays fully on-screen.
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 20, "B")
        rect = self.game._info_box_rect(
            item, "toolbox", (main.SCREEN_WIDTH - 5, main.SCREEN_HEIGHT - 5))
        self.assertGreaterEqual(rect.left, 0)
        self.assertGreaterEqual(rect.top, 0)
        self.assertLessEqual(rect.right, main.SCREEN_WIDTH)
        self.assertLessEqual(rect.bottom, main.SCREEN_HEIGHT)

    def test_sidebar_describes_placed_block(self):
        block = main.Block(2, 3, shape=main.Shape.CURVED_SLOPE, effect=main.Effect.GRAVITY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        rows = self.game._describe_item(block)
        self.assertEqual([label for label, _ in rows],
                         ["Shape - Curved Slope", "Effect - Gravity", "Scorer - +Chips", "Trigger"])
        self.assertIn("arc", main.shape_description(block.shape))

    def test_sidebar_shows_trigger_limit_for_placed_block(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        block.triggers_left = 0
        rows = self.game._describe_item(block)
        trigger = next(text for label, text in rows if label == "Trigger")
        self.assertIn("once per run", trigger)
        self.assertIn("0 left", trigger)

    def test_sidebar_shows_trigger_limit_for_blockitem(self):
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD, 10, 20, "B")
        labels = [label for label, _ in self.game._describe_item(item)]
        self.assertIn("Trigger", labels)

    def test_non_scoring_block_has_no_trigger_row(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.START)
        labels = [label for label, _ in self.game._describe_item(block)]
        self.assertNotIn("Trigger", labels)

    def test_item_name_includes_effects_shape_scorer_and_trigger_limit(self):
        # A slippery, fragile pipe that grants +chips twice per run.
        item = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                              10, 20, "Pipe +Chips", trigger_limit=2,
                              effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE])
        self.assertEqual(self.game._item_name(item), "Slippery Fragile Pipe +Chips v2")

    def test_item_name_for_placed_block_uses_parts(self):
        block = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10, trigger_limit=2,
                           effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE])
        self.assertEqual(self.game._item_name(block), "Slippery Fragile Pipe +Chips v2")

    def test_item_name_omits_none_effect_and_shows_v1(self):
        # A block with no real effects reads "Shape Scorer v1".
        block = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.assertEqual(self.game._item_name(block), "Rect +Chips v1")

    def test_item_name_for_component_keeps_its_name(self):
        comp = main.Component.shape_component(main.Shape.PIPE)
        self.assertEqual(self.game._item_name(comp), "Pipe")

    def test_sidebar_renders_full_effect_name_title(self):
        # Hovering over a block with a long name renders the info box with the
        # title wrapped onto multiple lines without raising.
        self.game.toolbox.items.clear()
        self.game.toolbox.add(main.BlockItem(
            0, 0, main.Shape.PIPE, main.Effect.NONE, main.Scorer.CHIPS_ADD, 10, 20, "P",
            trigger_limit=2, effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE]))
        pos = (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5)
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos):
            self.game.draw_sidebar()  # the long title wraps without raising

    def test_shop_refresh_costs_and_rerolls(self):
        self.game.cash = 100
        before = [item.name for item in self.game.shop.items]

        self.game._refresh_shop()

        self.assertEqual(self.game.cash, 100 - main.SHOP_REFRESH_COST)
        self.assertNotEqual([item.name for item in self.game.shop.items], before)

    def test_shop_refresh_fails_without_enough_cash(self):
        self.game.cash = main.SHOP_REFRESH_COST - 1
        before = [item.name for item in self.game.shop.items]

        self.game._refresh_shop()

        self.assertEqual(self.game.cash, main.SHOP_REFRESH_COST - 1)
        self.assertEqual([item.name for item in self.game.shop.items], before)
        self.assertTrue(self.game.shop_message)

    def test_f_key_disassembles_selected_block(self):
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.GRAVITY,
                               main.Scorer.CHIPS_ADD, 10, 20, "Circle +Chips")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self.game._disassemble_block()

        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)
        self.assertNotIn(block, self.game.toolbox.items)
        kinds = {item.kind for item in self.game.toolbox.items}
        self.assertEqual(kinds, {main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER})
        shapes = [item.value for item in self.game.toolbox.items if item.kind == main.Component.SHAPE]
        self.assertEqual(shapes, [main.Shape.CIRCLE])

    def test_f_key_disassembles_placed_block(self):
        placed = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.toolbox.items.clear()
        self.game.grid[(2, 3)] = placed
        self.game._select_placed_block(placed)
        self.game.cash = 100

        self.game._disassemble_block()

        self.assertNotIn((2, 3), self.game.grid)
        kinds = {item.kind for item in self.game.toolbox.items}
        self.assertEqual(kinds, {main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER})
        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)

    def test_disassemble_fails_without_enough_cash(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = main.DISASSEMBLE_COST - 1

        self.game._disassemble_block()

        self.assertEqual(self.game.cash, main.DISASSEMBLE_COST - 1)
        self.assertIn(block, self.game.toolbox.items)
        self.assertTrue(self.game.shop_message)

    def test_disassemble_requires_selected_block(self):
        self.game.cash = 100
        self.game.selected_toolbox_item = None
        self.game._disassemble_block()
        self.assertTrue(self.game.shop_message)

    def test_s_key_presses_disassemble_selected_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.GRAVITY,
                               main.Scorer.CHIPS_ADD, 10, 20, "Circle +Chips")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self._press(main.pygame.K_s)

        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)
        self.assertNotIn(block, self.game.toolbox.items)
        parts = [i for i in self.game.toolbox.items if i.kind != "block"]
        self.assertEqual(len(parts), 3)

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

    def test_clicking_empty_space_deselects_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)

        self._click((20, 20))  # neutral spot outside every panel

        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertFalse(self.game.has_selected)

    def test_clicking_empty_space_deselects_component(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game._select_toolbox_component(comp)

        self._click((20, 20))

        self.assertIsNone(self.game.selected_toolbox_item)

    def test_clicking_away_clears_selection(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)

        self._click((20, 20))

        self.assertIsNone(self.game.selected_toolbox_item)

    def test_clicking_shop_unselects_selected_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        shop = self.game.shop.items[0]
        pos = (self.game.shop.rect.x + shop.col * main.GRID_SIZE + 5,
               self.game.shop.rect.y + shop.row * main.GRID_SIZE + 5)

        self._click(pos)

        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertFalse(self.game.has_selected)

    def test_clicking_on_grid_places_block_and_clears_selection(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)

        self._click(self._grid_pos(1, 1))  # inside the marble box

        self.assertIn((1, 1), self.game.grid)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertFalse(self.game.has_selected)

    def test_clicking_placed_block_selects_it(self):
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)

        self._click(self._grid_pos(2, 3))

        self.assertTrue(self.game.has_selected)
        self.assertIs(self.game.selected_toolbox_item, self.game.grid[(2, 3)])
        self.assertEqual(self.game.selected_shape, main.Shape.SLOPE)
        self.assertEqual(self.game.selected_effect, main.Effect.BOUNCY)
        self.assertEqual(self.game.selected_scorer, main.Scorer.CHIPS_ADD)
        self.assertTrue(self.game.shop_message)

    def test_moving_placed_block_removes_original(self):
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self._click(self._grid_pos(2, 3))  # select the placed block
        self.assertTrue(self.game.has_selected)

        self._click(self._grid_pos(5, 5))  # move it to an empty cell

        self.assertIn((5, 5), self.game.grid)
        self.assertNotIn((2, 3), self.game.grid)  # the original is removed (a move, not a copy)
        placed = self.game.grid[(5, 5)]
        self.assertEqual(placed.shape, main.Shape.SLOPE)
        self.assertEqual(placed.effect, main.Effect.BOUNCY)
        self.assertFalse(self.game.has_selected)

    def test_moving_placed_block_onto_same_cell_is_noop(self):
        self.game.toolbox.items.clear()
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self._click(self._grid_pos(2, 3))  # select the placed block

        self._click(self._grid_pos(2, 3))  # "move" it onto itself

        self.assertIn((2, 3), self.game.grid)
        self.assertEqual(self.game.grid[(2, 3)].shape, main.Shape.SLOPE)
        self.assertEqual(len(self.game.toolbox.items), 0)  # nothing refunded
        self.assertFalse(self.game.has_selected)

    def test_moving_placed_block_displaces_other_block_to_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(5, 5)] = main.Block(5, 5, shape=main.Shape.RECT,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self._click(self._grid_pos(2, 3))  # select the SLOPE block

        self._click(self._grid_pos(5, 5))  # move it onto the RECT block

        self.assertIn((5, 5), self.game.grid)
        self.assertNotIn((2, 3), self.game.grid)  # moved away
        self.assertEqual(self.game.grid[(5, 5)].shape, main.Shape.SLOPE)
        # The displaced RECT block was refunded to the toolbox.
        self.assertEqual(len(self.game.toolbox.items), 1)
        self.assertEqual(self.game.toolbox.items[0].shape, main.Shape.RECT)
        self.assertFalse(self.game.has_selected)

    def test_equipped_block_still_replaces_placed_block_on_click(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)

        self._click(self._grid_pos(2, 3))

        # The equipped block replaces the placed one (existing placement behavior).
        self.assertEqual(self.game.grid[(2, 3)].shape, main.Shape.RECT)
        self.assertFalse(self.game.has_selected)

    def test_assembling_keeps_new_block_selected(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertTrue(self.game.has_selected)  # fresh block stays selected
        self.assertIsNotNone(self.game.selected_toolbox_item)
        self.assertEqual(self.game.selected_toolbox_item.kind, "block")

    def test_info_target_at_finds_shop_toolbox_and_grid(self):
        shop = self.game.shop.items[0]
        target, source = self.game._info_target_at(
            (self.game.shop.rect.x + shop.col * main.GRID_SIZE + 5,
             self.game.shop.rect.y + shop.row * main.GRID_SIZE + 5))
        self.assertIs(target, shop)
        self.assertEqual(source, "shop")

        tb = self.game.toolbox.items[0]
        target, source = self.game._info_target_at(
            (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5))
        self.assertIs(target, tb)
        self.assertEqual(source, "toolbox")

        block = main.Block(2, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(2, 3)] = block
        target, source = self.game._info_target_at((block.rect.centerx, block.rect.centery))
        self.assertIs(target, block)
        self.assertEqual(source, "grid")

    def test_left_clicking_shop_item_buys_it(self):
        self.game.toolbox.items.clear()
        item = self.game.shop.items[0]
        cash_before = self.game.cash
        pos = (self.game.shop.rect.x + item.col * main.GRID_SIZE + main.GRID_SIZE // 2,
               self.game.shop.rect.y + item.row * main.GRID_SIZE + main.GRID_SIZE // 2)

        self._click(pos)

        self.assertLess(self.game.cash, cash_before)  # left-click buys the item

    def test_left_clicking_toolbox_item_equips_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        pos = (self.game.toolbox.rect.x + main.GRID_SIZE // 2,
               self.game.toolbox.rect.y + main.GRID_SIZE // 2)

        self._click(pos)

        self.assertIs(self.game.selected_toolbox_item, block)
        self.assertTrue(self.game.has_selected)  # the block is equipped

    def test_left_clicking_placed_block_selects_it_for_move(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 3)] = block

        self._click(self._grid_pos(2, 3))

        self.assertIs(self.game.selected_toolbox_item, block)  # it equips the placed block
        self.assertTrue(self.game.has_selected)

    def test_a_key_rotates_next_placement_angle_not_placed_block(self):
        # The A key only rotates the next-placement/ghost angle; it does NOT
        # rotate a block that is already placed on the grid.
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 3)] = block
        self._click(self._grid_pos(2, 3))  # select the placed block

        self._press(main.pygame.K_a)

        self.assertEqual(block.angle, 0)  # the placed block is unchanged
        self.assertEqual(self.game.current_block_angle, 90)
        self.assertIs(self.game.selected_toolbox_item, block)

    def test_a_key_rotates_again_accumulates_next_placement_angle(self):
        self._press(main.pygame.K_a)
        self._press(main.pygame.K_a)

        self.assertEqual(self.game.current_block_angle, 180)

    def test_a_key_does_not_rotate_placed_pipe_drain_bend(self):
        # The A key does not rotate placed pipe/drain/bend blocks in place; it
        # only rotates the next-placement angle. (The shapes still honor their
        # base angle when one is set directly.)
        for shape in (main.Shape.PIPE, main.Shape.DRAIN, main.Shape.PIPE_BEND):
            with self.subTest(shape=main.Shape.name(shape)):
                block = main.Block(2, 3, shape=shape, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
                self.game.grid[(2, 3)] = block
                self.game.current_block_angle = 0
                self._click(self._grid_pos(2, 3))  # select the placed block
                self._press(main.pygame.K_a)
                self.assertEqual(block.angle, 0)
                self.assertEqual(self.game.current_block_angle, 90)

    def test_a_key_rotates_next_placement_when_nothing_selected(self):
        self.assertEqual(self.game.current_block_angle, 0)
        self.game.selected_toolbox_item = None

        self._press(main.pygame.K_a)

        self.assertEqual(self.game.current_block_angle, 90)

    def test_marble_types_draw_without_raising(self):
        # Every marble type renders (shaded sphere + rolling feature) without
        # raising, at rest and while spinning.
        for mt in main.MarbleType.ORDER:
            marble = main.Marble(400, 300)
            marble.marble_type = mt
            if mt == main.MarbleType.RUBBER_BALL:
                marble.color = (200, 50, 50)
                marble.color2 = (50, 50, 200)
            elif mt == main.MarbleType.PING_PONG:
                marble.color = main.PING_PONG_COLORS[0]
                marble.color2 = main.PING_PONG_COLORS[1]
            marble.spin_angle = 1.0
            marble.velocity = np.array([40.0, 0.0])
            marble.draw(self.game.screen)

    def test_8_ball_retriggers_scoring_effect(self):
        # The 8 ball has a 1/4 chance per collision to retrigger a block's
        # scoring effect — a free second score that uses no extra trigger.
        self.game.score_chips = 0
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10)
        block.triggers_left = 1
        self.game.grid[(1, 1)] = block
        marble = self._add_marble()
        marble.marble_type = main.MarbleType.EIGHT_BALL
        self.game.run_active = True
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        with mock.patch("main.random.random", return_value=0.1):  # under 0.25 -> retrigger
            self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 20)  # 10 base + 10 retrigger
        self.assertEqual(block.triggers_left, 0)  # still only one trigger used

    def test_8_ball_retrigger_miss_keeps_single_score(self):
        self.game.score_chips = 0
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10)
        block.triggers_left = 1
        self.game.grid[(1, 1)] = block
        marble = self._add_marble()
        marble.marble_type = main.MarbleType.EIGHT_BALL
        self.game.run_active = True
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        with mock.patch("main.random.random", return_value=0.9):  # 25%+ -> no retrigger
            self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(block.triggers_left, 0)

    def test_vanilla_marble_does_not_retrigger(self):
        self.game.score_chips = 0
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10)
        block.triggers_left = 1
        self.game.grid[(1, 1)] = block
        self.game.run_active = True
        marble = self._add_marble()  # vanilla: no retrigger
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)

    def test_rubber_ball_bounces_off_block(self):
        # A rubber-ball marble reflects the full normal velocity off a block;
        # a normal marble just loses it (restitution 0).
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, 0)
        marble.velocity = np.array([0.0, 100.0])  # moving down into the top face
        marble.bouncy = True
        marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
        self.assertEqual(marble.velocity[1], -100.0)  # bounced straight back up

    def test_normal_marble_does_not_bounce_off_block(self):
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, 0)
        marble.velocity = np.array([0.0, 100.0])
        marble.bouncy = False
        marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
        self.assertEqual(marble.velocity[1], 0.0)  # normal marbles stop at walls

    def test_rubber_ball_bounces_off_border(self):
        # A rubber-ball marble bounces back off the marble-box border with full
        # energy instead of stopping at the edge.
        marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 5, 300)
        marble.velocity = np.array([-100.0, 0.0])
        marble.bouncy = True
        marble.physics.keep_in_bounds(marble)
        self.assertGreater(marble.velocity[0], 0.0)  # reflected to the right

    def test_marble_spin_angle_advances_when_rolling(self):
        # A moving marble that is grounded (rolling on the bottom border)
        # accumulates its spin angle from its angular velocity.
        marble = self._add_marble()
        marble.position = np.array([500.0, main.MARBLE_BOX_COORDS[1] + main.MARBLE_BOX_COORDS[3] + 10])
        marble.velocity = np.array([50.0, 0.0])
        before = marble.spin_angle
        marble.physics.update(marble, main.DT, [])
        self.assertGreater(marble.spin_angle, before)

    def test_marble_does_not_spin_when_stationary(self):
        marble = self._add_marble()
        marble.position = np.array([500.0, main.MARBLE_BOX_COORDS[1] + main.MARBLE_BOX_COORDS[3] + 10])
        marble.velocity = np.array([0.0, 0.0])
        marble.physics.update(marble, main.DT, [])
        self.assertEqual(marble.spin_angle, 0.0)

    def test_reset_run_applies_marble_type_to_spawned_marbles(self):
        # Spawned marbles inherit the save's marble type; rubber balls get two
        # random (distinct) half-colors and the bouncy flag.
        self.game.marble_type = main.MarbleType.RUBBER_BALL
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 1)
        m = self.game.marbles[0]
        self.assertEqual(m.marble_type, main.MarbleType.RUBBER_BALL)
        self.assertTrue(m.bouncy)
        self.assertNotEqual(m.color, m.color2)

    def test_reset_run_spawns_light_ping_pong_marble(self):
        # Spawned ping-pong marbles are very light (low mass + slight
        # restitution) and wear two distinct half-colors, but do not use the
        # rubber ball's full bouncy flag.
        self.game.marble_type = main.MarbleType.PING_PONG
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        m = self.game.marbles[0]
        self.assertEqual(m.marble_type, main.MarbleType.PING_PONG)
        self.assertAlmostEqual(m.mass, main.PING_PONG_MASS)
        self.assertAlmostEqual(m.restitution, main.PING_PONG_RESTITUTION)
        self.assertFalse(m.bouncy)  # not the rubber ball's full bounce
        self.assertNotEqual(m.color, m.color2)

    def test_right_click_erases_block(self):
        block = main.Block(2, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(2, 3)] = block
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 3

        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(2, 3)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertNotIn((2, 3), self.game.grid)  # right-click erases

    def test_selling_selected_block_refunds_half_price(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game._equip_block(block)  # select the block from the toolbox
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + block.price // 2)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertFalse(self.game.has_selected)
        self.assertTrue(self.game.shop_message)

    def test_selling_component_refunds_half_price(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game.selected_toolbox_item = comp
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + comp.price // 2)
        self.assertNotIn(comp, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertTrue(self.game.shop_message)

    def test_selling_without_selected_item_does_nothing(self):
        self.game.selected_toolbox_item = None
        self.game.cash = 50
        before = len(self.game.toolbox.items)

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50)
        self.assertEqual(len(self.game.toolbox.items), before)

    def test_b_key_sells_selected_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.cash = 50

        self._press(main.pygame.K_b)

        self.assertEqual(self.game.cash, 50 + block.price // 2)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_toolbox_item)

    def test_b_key_sells_selected_component(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp)
        self.game.cash = 50

        self._press(main.pygame.K_b)

        self.assertEqual(self.game.cash, 50 + comp.price // 2)
        self.assertNotIn(comp, self.game.toolbox.items)

    def test_clicking_owned_card_selects_it_for_selling(self):
        # Left-clicking an owned card selects it as the active item, so pressing
        # B sells it for half its original price.
        card = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(card)
        x = main.CARD_AREA_COORDS[0] + main.GRID_SIZE // 2
        y = main.CARD_AREA_COORDS[1] + main.GRID_SIZE // 2
        self._click((x, y))
        self.assertIs(self.game.selected_toolbox_item, card)

    def test_clicking_two_cards_swaps_their_order(self):
        # Select one card, then click another to swap their order in the card
        # area (Blueprint copies the card to its left, so order matters).
        card_a = main.CardItem(main.Card.JOKER, 20)
        card_b = main.CardItem(main.Card.EXPLORER, 25)
        self.game.cards.append(card_a)
        self.game.cards.append(card_b)
        y = main.CARD_AREA_COORDS[1] + 5
        ax = main.CARD_AREA_COORDS[0] + 5
        bx = main.CARD_AREA_COORDS[0] + main.GRID_SIZE + 5

        self._click((ax, y))
        self.assertIs(self.game.selected_toolbox_item, card_a)
        self._click((bx, y))

        self.assertEqual(self.game.cards, [card_b, card_a])
        self.assertIs(self.game.selected_toolbox_item, card_b)

    def test_b_key_sells_selected_card_for_half_price(self):
        card = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(card)
        self.game.cash = 50
        self.game.selected_toolbox_item = card

        self._press(main.pygame.K_b)

        self.assertNotIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 50 + card.price // 2)
        self.assertIsNone(self.game.selected_toolbox_item)

    def test_start_parts_card_grants_component_at_run_start(self):
        # Regression: a start-of-run resource card (Ripped Card + Parts =
        # FEW_BLOCKS x Parts) fires when the run starts and grants its reward
        # (a component) immediately.
        value = main.condition_scorer_card(main.Condition.FEW_BLOCKS, main.Scorer.PARTS)
        self.game.cards.append(main.CardItem(value, 50))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.toolbox.items.clear()
        self.assertTrue(self.game.reset_run())
        comps = [i for i in self.game.toolbox.items if getattr(i, "kind", None)
                 in (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)]
        self.assertEqual(len(comps), 1)

    def test_s_key_disassembles_splittable_card_into_halves(self):
        # Pressing S on a selected splittable card (e.g. Joker = START x
        # +Mult) pays $70 and returns its condition + scorer to the toolbox.
        self.game.toolbox.items.clear()
        card = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(card)
        self.game.cash = 100
        self.game.selected_toolbox_item = card
        before = len(self.game.toolbox.items)

        self._press(main.pygame.K_s)

        self.assertNotIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100 - main.CARD_DISASSEMBLE_COST)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertEqual(len(self.game.toolbox.items), before + 2)
        kinds = sorted(i.kind for i in self.game.toolbox.items)
        self.assertEqual(kinds, ["condition", "scorer"])
        condition = next(i for i in self.game.toolbox.items if i.kind == "condition")
        scorer = next(i for i in self.game.toolbox.items if i.kind == "scorer")
        self.assertEqual(condition.value, main.Condition.START)
        self.assertEqual(scorer.value, main.Scorer.MULT_ADD)

    def test_s_key_cannot_disassemble_whole_card(self):
        # Whole cards (ERR 404 / Blueprint / Showman) have no halves to split.
        card = main.CardItem(main.Card.BLUEPRINT, 35)
        self.game.cards.append(card)
        self.game.cash = 100
        self.game.selected_toolbox_item = card
        self._press(main.pygame.K_s)
        self.assertIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100)
        self.assertIn("cannot be split", self.game.shop_message)

    def test_s_key_card_disassemble_requires_cash(self):
        card = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(card)
        self.game.cash = main.CARD_DISASSEMBLE_COST - 1
        self.game.selected_toolbox_item = card
        self._press(main.pygame.K_s)
        self.assertIn(card, self.game.cards)  # nothing happened
        self.assertEqual(self.game.cash, main.CARD_DISASSEMBLE_COST - 1)
        self.assertIn("Need $", self.game.shop_message)

    def test_assembling_only_a_scorer_defaults_shape_and_effect(self):
        # A lone +Chips scorer assembles a plain Rect +Chips block (the shape
        # defaults to Rect and the effect to None).
        self.game.toolbox.items.clear()
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        self.game.toolbox.add(scorer)
        self.game._use_component(scorer)

        self.game._assemble_block()

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.RECT)   # default shape
        self.assertEqual(blocks[0].effect, main.Effect.NONE)  # default effect
        self.assertEqual(blocks[0].scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(blocks[0].scorer_amount, 10)
        self.assertNotIn(scorer, self.game.toolbox.items)  # consumed
        # The block is worth 75% of its parts, and the +Chips piece is priced
        # for its OWN magnitude (10 chips, well below the 30 average, is a
        # cheap scorer).
        self.assertEqual(blocks[0].price,
                         int(main.scorer_component_price(main.Scorer.CHIPS_ADD, 10) * 0.75))

    def test_assembling_partial_parts_defaults_the_rest(self):
        # A lone effect makes a Rect block with that effect and no scorer.
        self.game.toolbox.items.clear()
        eff = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(eff)
        self.game._use_component(eff)
        self.game._assemble_block()
        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.RECT)   # default shape
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)
        self.assertEqual(blocks[0].scorer, main.Scorer.NONE)  # default scorer

        # A lone shape makes a plain effect-less, scorer-less block of it.
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.SLOPE)
        self.game.toolbox.add(shape_c)
        self.game._use_component(shape_c)
        self.game._assemble_block()
        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.SLOPE)
        self.assertEqual(blocks[0].effect, main.Effect.NONE)
        self.assertEqual(blocks[0].scorer, main.Scorer.NONE)

    def test_s_key_assembles_when_components_assigned(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self._press(main.pygame.K_s)

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)
        self.assertTrue(self.game.has_selected)  # the fresh block is equipped
        # Assigned components were consumed by assembly.
        self.assertNotIn(shape_c, self.game.toolbox.items)
        self.assertNotIn(effect_c, self.game.toolbox.items)
        self.assertNotIn(scorer, self.game.toolbox.items)

    def test_s_key_disassembles_when_block_selected(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.GRAVITY,
                               main.Scorer.CHIPS_ADD, 10, 20, "Circle +Chips")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self._press(main.pygame.K_s)

        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind != "block"]), 3)

    def test_s_key_with_nothing_assembles_plain_wall(self):
        # Pressing S with no parts assigned and nothing selected builds the
        # plain default block: a Rect wall with no effect and no scorer.
        self.game.toolbox.items.clear()
        self.game.selected_toolbox_item = None
        self.game.assembler.clear()

        self._press(main.pygame.K_s)

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.RECT)
        self.assertEqual(blocks[0].effect, main.Effect.NONE)
        self.assertEqual(blocks[0].scorer, main.Scorer.NONE)
        self.assertEqual(blocks[0].price, 0)  # free defaults are worth nothing

    def test_selecting_component_assigns_it_to_assembler(self):
        comp = main.Component.shape_component(main.Shape.SLOPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)

        self.game._select_toolbox_component(comp)

        self.assertIs(self.game.selected_toolbox_item, comp)
        self.assertIs(self.game.assembler.shape, comp)  # assigned on selection
        self.assertIn(comp, self.game.toolbox.items)  # stays in the toolbox
        self.assertFalse(self.game.has_selected)

    def test_use_component_stays_in_toolbox(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)

        self.game._use_component(comp)

        self.assertIn(comp, self.game.assembler.effects)
        self.assertIn(comp, self.game.toolbox.items)  # kept where it is

    def test_effect_component_toggles_off_when_clicked_again(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp)
        self.assertIn(comp, self.game.assembler.effects)

        self.game._select_toolbox_component(comp)

        self.assertNotIn(comp, self.game.assembler.effects)

    def test_selling_assigned_component_refunds_half_and_unassigns(self):
        comp = main.Component.shape_component(main.Shape.SLOPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + comp.price // 2)
        self.assertIsNone(self.game.assembler.shape)  # unassigned when sold
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertTrue(self.game.shop_message)

    def test_switching_assigned_shape_swaps_assignment(self):
        self.game.toolbox.items.clear()
        first = main.Component.shape_component(main.Shape.SLOPE, 0, "Slope")
        second = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        self.game.toolbox.add(first)
        self.game.toolbox.add(second)

        self.game._use_component(first)
        self.game._use_component(second)

        self.assertIs(self.game.assembler.shape, second)  # last one wins
        self.assertIn(first, self.game.toolbox.items)  # both kept in the toolbox
        self.assertIn(second, self.game.toolbox.items)

    def test_assembler_has_parts_when_any_part_assigned(self):
        self.game.assembler.clear()
        self.assertFalse(self.game.assembler.has_parts())
        self.game.assembler.shape = main.Component.shape_component(main.Shape.RECT)
        self.assertTrue(self.game.assembler.has_parts())
        self.game.assembler.clear()
        self.game.assembler.effects = [main.Component.effect_component(main.Effect.BOUNCY)]
        self.assertTrue(self.game.assembler.has_parts())
        self.game.assembler.clear()
        self.game.assembler.scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        self.assertTrue(self.game.assembler.has_parts())

    def test_is_assigned_marks_assigned_components(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.assembler.clear()
        self.assertFalse(self.game._is_assigned(comp))
        self.game.assembler.effects = [comp]
        self.assertTrue(self.game._is_assigned(comp))
        shape = main.Component.shape_component(main.Shape.SLOPE)
        self.game.assembler.shape = shape
        self.assertTrue(self.game._is_assigned(shape))
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        self.game.assembler.scorer = scorer
        self.assertTrue(self.game._is_assigned(scorer))

    def test_toolbox_index_at_resolves_cell(self):
        self.game.toolbox.items.clear()
        filler = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.NONE, 0, 5, "f")
        while len(self.game.toolbox.items) < 13:
            self.game.toolbox.add(filler)
        box = self.game.toolbox
        pos = (box.rect.x + 2 * main.GRID_SIZE + 5, box.rect.y + main.GRID_SIZE + 5)
        self.assertEqual(box.index_at(pos), 12)  # col 2, row 1
        self.assertIsNone(box.index_at((box.rect.x - 5, box.rect.y - 5)))

    def test_selecting_block_highlights_its_cell_green(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        box = self.game.toolbox
        self._click((box.rect.x + main.GRID_SIZE // 2, box.rect.y + main.GRID_SIZE // 2))
        self.assertTrue(self.game.has_selected)
        self.assertEqual(self.game.selected_toolbox_index, 0)

        self.game.screen.fill((0, 0, 0))
        self.game.draw_toolbox()
        r0 = pygame.Rect(box.rect.x, box.rect.y, main.GRID_SIZE, main.GRID_SIZE)
        self.assertEqual(self.game.screen.get_at((r0.x + 1, r0.y + 1))[:3], main.GREEN)

    def test_selecting_duplicate_component_highlights_only_clicked_cell(self):
        # Two copies of the SAME component object live in the toolbox. Selecting
        # one must highlight only the exact cell that was clicked, not both.
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game.toolbox.add(comp)
        box = self.game.toolbox
        self._click((box.rect.x + main.GRID_SIZE + main.GRID_SIZE // 2,
                     box.rect.y + main.GRID_SIZE // 2))  # second cell
        self.assertIs(self.game.selected_toolbox_item, comp)
        self.assertEqual(self.game.selected_toolbox_index, 1)

        self.game.screen.fill((0, 0, 0))
        self.game.draw_toolbox()
        r0 = pygame.Rect(box.rect.x, box.rect.y, main.GRID_SIZE, main.GRID_SIZE)
        r1 = r0.move(main.GRID_SIZE, 0)
        self.assertNotEqual(self.game.screen.get_at((r0.x + 1, r0.y + 1))[:3], main.GREEN)
        self.assertEqual(self.game.screen.get_at((r1.x + 1, r1.y + 1))[:3], main.GREEN)

    def test_assigned_component_stays_green_at_its_cell(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.SLOPE)
        eff_c = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(shape_c)
        self.game.toolbox.add(eff_c)
        self.game._select_toolbox_component(shape_c, 0)
        self.game._select_toolbox_component(eff_c, 1)  # selecting a new one keeps the old green

        self.game.screen.fill((0, 0, 0))
        self.game.draw_toolbox()
        box = self.game.toolbox
        r0 = pygame.Rect(box.rect.x, box.rect.y, main.GRID_SIZE, main.GRID_SIZE)
        r1 = r0.move(main.GRID_SIZE, 0)
        self.assertEqual(self.game.screen.get_at((r0.x + 1, r0.y + 1))[:3], main.GREEN)
        self.assertEqual(self.game.screen.get_at((r1.x + 1, r1.y + 1))[:3], main.GREEN)

    def test_selected_toolbox_index_cleared_on_deselect(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp, 0)
        self.assertEqual(self.game.selected_toolbox_index, 0)

        self._click((20, 20))  # empty space

        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertIsNone(self.game.selected_toolbox_index)

    def test_sell_overlay_rect_is_bottom_right_toolbox_cell(self):
        rect = main.SELL_OVERLAY_RECT
        self.assertEqual(rect.right, self.game.toolbox.rect.right)
        self.assertEqual(rect.bottom, self.game.toolbox.rect.bottom)
        self.assertEqual((rect.width, rect.height), (main.GRID_SIZE, main.GRID_SIZE))

    def test_run_cleared_when_score_meets_requirement(self):
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE  # a far run boosts the score
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.run_time = main.TIME_IDEAL  # ideal time -> full time factor
        self.game.score_chips = 500
        self.game.score_mult = 20
        self.game.touched_shapes = {main.Shape.SLOPE}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}
        self.game.required_score = 1000

        self.game._handle_block_contacts([])

        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.run_complete)
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(self.game.awaiting_after_run)
        # Progression is deferred until the player clicks CONTINUE.
        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.required_score, 1000)
        self.assertEqual(self.game.run_results, [True])
        self.assertEqual(self.game.runs_cleared, 1)

        self.game._continue_run()

        self.assertEqual(self.game.run_number, 1)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])
        self.assertFalse(self.game.run_complete)

    def test_run_not_cleared_when_score_below_requirement(self):
        marble = self._add_marble()
        marble.distance = 100.0
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.run_time = 3.0
        self.game.score_chips = 100
        self.game.score_mult = 2
        self.game.required_score = 10000

        self.game._handle_block_contacts([])

        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.run_cleared)
        self.assertTrue(self.game.awaiting_after_run)
        # A failed run counts as a fail but doesn't advance until CONTINUE.
        self.assertEqual(self.game.run_results, [False])
        self.assertEqual(self.game.failed_runs, 1)
        self.assertEqual(self.game.required_score, 10000)

        self.game._continue_run()

        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])

    def test_reset_run_clears_run_cleared_flag(self):
        self.game.run_cleared = True
        self.game.run_complete = True
        # Seed a valid start + finish so the run can begin.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.grid[(5, 5)] = main.Block(5, 5, scorer=main.Scorer.FINISH)

        self.game.reset_run()

        self.assertFalse(self.game.run_cleared)
        self.assertFalse(self.game.run_complete)
        # The target stays on the current run across resets.
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[0])

    def test_run_results_are_native_bools_for_json(self):
        # A cleared run's result must be a native Python bool. The total score
        # is built from numpy score factors, so without coercion it leaks a
        # numpy float -> numpy bool into run_results, which then breaks JSON
        # saves ("Object of type bool is not JSON serializable").
        self.game.marble_type = main.MarbleType.PING_PONG  # any type triggers it
        self._complete_run(1000000, required=1)
        self.assertEqual(self.game.run_results, [True])
        self.assertIs(type(self.game.run_results[0]), bool)
        self.assertIs(type(self.game.score_total), float)

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

    def test_required_score_schedule_grows_monotonically(self):
        # The lazily-grown schedule: every run's target DOUBLES the previous
        # one (REQUIRED_SCORES starts as [1] and grows on demand), so the
        # targets keep rising.
        main.REQUIRED_SCORES[:] = [1]
        prev = main.REQUIRED_SCORES[0]
        for run in range(1, main.TOTAL_RUNS):
            expected = prev * 2
            self.assertEqual(main.get_next_required_score(run), expected)
            self.assertGreater(expected, prev)  # targets keep rising
            prev = expected
        # The grown schedule is exactly the doubling series [1, 2, 4, 8, ...].
        self.assertEqual(main.REQUIRED_SCORES,
                         [2 ** i for i in range(main.TOTAL_RUNS)])
        # Asking for an earlier run never re-grows or changes the schedule.
        self.assertEqual(main.get_next_required_score(1), 2)
        main.REQUIRED_SCORES[:] = [1]  # restore for the tests that follow

    def test_three_failed_runs_means_defeat(self):
        # The 3rd lost run ends the game immediately with a defeat game over.
        # (Required scores are set explicitly so each run's outcome is exact.)
        self._complete_run(1000000, required=1)  # run 1: clear
        self.game._continue_run()
        self._complete_run(100, required=1000)  # run 2: fail (1st loss)
        self.game._continue_run()
        self.assertFalse(self.game.game_over)
        self._complete_run(100, required=1000)  # run 3: fail (2nd loss)
        self.game._continue_run()
        self.assertFalse(self.game.game_over)
        self._complete_run(100, required=1000)  # run 4: fail (3rd loss)
        self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertFalse(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.run_number, 4)
        self.assertEqual(self.game.failed_runs, 3)

    def test_defeat_awards_dice_squared_of_run_minus_three(self):
        # A game over in defeat awards dice = (run number - 3)^2. A defeat on
        # run 4 (the 3rd loss) gives (4 - 3)^2 = 1 die.
        self.assertEqual(metagame.dice(), 0)
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertEqual(metagame.dice(), (4 - 3) ** 2)
        self.assertEqual(self.game.game_over_dice_gained, 1)

    def test_victory_does_not_award_dice(self):
        # Winning all 24 runs ends in a perfect win; no dice are awarded.
        self.assertEqual(metagame.dice(), 0)
        for _ in range(main.TOTAL_RUNS):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)
        self.assertEqual(metagame.dice(), 0)
        self.assertEqual(self.game.game_over_dice_gained, 0)

    def test_perfect_win_when_all_runs_cleared(self):
        for _ in range(main.TOTAL_RUNS):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)
        self.assertEqual(self.game.runs_cleared, main.TOTAL_RUNS)

    def test_game_won_after_22_runs_met_with_two_fails(self):
        # 2 spread-out fails, 22 clears: reaches run 24, clears the boss run,
        # and wins (not perfect). Failing the final run would end in defeat.
        for run in range(main.TOTAL_RUNS):
            if run in (2, 12):
                self._complete_run(100, required=1000)  # fail
            else:
                self._complete_run(1000000, required=1)  # clear
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.runs_cleared, main.REQUIRED_RUNS_TO_WIN)

    def test_reset_game_starts_fresh_game(self):
        # Play a couple runs, then reset.
        self._play_run(0)
        self.game.score_total = 999
        self.game.reset_game()
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.round_index, 0)
        self.assertEqual(self.game.run_in_round, 0)
        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.failed_runs, 0)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[0])
        self.assertEqual(self.game.grid, {})

    def test_buying_component_adds_to_toolbox_and_deducts_cash(self):
        component = next(item for item in self.game.shop.items if item.kind != "block")
        self.game.cash = 1000

        self.game._buy_shop_item(component)

        self.assertIn(component, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 1000 - component.price)

    def test_shop_purchase_fails_without_enough_cash(self):
        item = self.game.shop.items[0]
        self.game.cash = item.price - 1

        self.game._buy_shop_item(item)

        self.assertEqual(self.game.cash, item.price - 1)
        self.assertTrue(self.game.shop_message)

    def test_buying_plays_coin_sound(self):
        # Every successful purchase clinks coins.
        component = next(item for item in self.game.shop.items
                         if item.kind not in ("block", "card"))
        self.game.cash = 1000
        with mock.patch("main.sounds.play_coin") as play:
            self.game._buy_shop_item(component)
        play.assert_called_once()

    def test_buying_without_enough_cash_does_not_play_sound(self):
        # A failed purchase (not enough cash) makes no coin sound.
        item = self.game.shop.items[0]
        self.game.cash = 0
        with mock.patch("main.sounds.play_coin") as play:
            self.game._buy_shop_item(item)
        play.assert_not_called()

    def test_assembling_plays_mech_sound(self):
        # Assembling a block whirs and crunches.
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer):
            self.game.toolbox.add(component)
            self.game._use_component(component)
        with mock.patch("main.sounds.play_mech") as play:
            self.game._assemble_block()
        play.assert_called_once()

    def test_disassembling_plays_mech_sound(self):
        # Disassembling a block whirs and crunches too.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 1000
        with mock.patch("main.sounds.play_mech") as play:
            self.game._disassemble_block()
        play.assert_called_once()

    def test_placing_block_plays_plop_sound(self):
        # Placing a block on the grid plops.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        with mock.patch("main.sounds.play_plop") as play:
            self._click(self._grid_pos(1, 1))
        play.assert_called_once()

    def test_sounds_helpers_are_safe_without_audio(self):
        # The sound module loads and its helpers never raise, even headless
        # (where the mixer is unavailable and every sound is None).
        import sounds
        sounds.play_coin()
        sounds.play_mech()
        sounds.play_plop()
        self.assertTrue(sounds.COIN is None or sounds.COIN is not None)

    def test_run_start_and_reset_sounds_are_built(self):
        # A run starting and a run being reset each have their own sound.
        import sounds
        if sounds._mixer_ok:
            self.assertIsNotNone(sounds.RUN_START)
            self.assertIsNotNone(sounds.RESET)
        else:  # no audio device: every sound is a silent None
            self.assertIsNone(sounds.RUN_START)
            self.assertIsNone(sounds.RESET)

    def test_component_sound_helpers_route_through_play(self):
        # Every effect and scorer can be played, plus the two run sounds.
        import sounds
        with mock.patch("sounds.play") as play:
            for effect in main.Effect.ORDER:
                sounds.play_effect(effect)
            for scorer in main.Scorer.ORDER:
                sounds.play_scorer(scorer)
            sounds.play_run_start()
            sounds.play_reset()
        self.assertEqual(play.call_count, len(main.Effect.ORDER)
                         + len(main.Scorer.ORDER) + 2)

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

    def test_every_effect_has_its_own_collision_sound(self):
        import sounds
        self._assert_waves_are_distinct(list(main.Effect.ORDER),
                                       sounds._effect_wave, "effect")

    def test_every_scorer_has_its_own_trigger_sound(self):
        import sounds
        self._assert_waves_are_distinct(list(main.Scorer.ORDER),
                                       sounds._scorer_wave, "scorer")

    def test_t_key_starts_a_run_with_a_sound(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        with mock.patch("main.sounds.play_run_start") as play:
            self._press(main.pygame.K_t)
        play.assert_called_once()
        self.assertTrue(self.game.run_active)

    def test_t_key_without_a_start_block_stays_silent(self):
        # No Start block on the board means no run actually starts.
        with mock.patch("main.sounds.play_run_start") as play:
            self._press(main.pygame.K_t)
        play.assert_not_called()

    def test_r_key_resets_the_run_with_a_sound(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        with mock.patch("main.sounds.play_reset") as play:
            self._press(main.pygame.K_r)
        play.assert_called_once()

    def test_retry_sounds_the_reset_but_other_rollbacks_do_not(self):
        # A real retry (a finished run being undone) rings; the save/quit/menu
        # rollback while building does not.
        with mock.patch("main.sounds.play_reset") as play:
            self.game._retry_run()
        play.assert_not_called()
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.sounds.play_reset") as play:
            self.game._retry_run()
        play.assert_called_once()

    def test_block_contact_plays_the_effect_and_scorer_sounds(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD,
                           effects=[main.Effect.BOUNCY, main.Effect.STICKY])
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        with mock.patch("main.sounds.play_effect") as effect_sound, \
             mock.patch("main.sounds.play_scorer") as scorer_sound:
            self.game._handle_block_contacts([block])
        # Every effect on the block rings, then the scorer that fired.
        self.assertEqual([call.args[0] for call in effect_sound.call_args_list],
                         [main.Effect.BOUNCY, main.Effect.STICKY])
        scorer_sound.assert_called_once_with(main.Scorer.CHIPS_ADD)
        # Staying in contact is not a new collision: no sound at all.
        marble.collisions_last_tick = [block]
        with mock.patch("main.sounds.play_effect") as effect_sound, \
             mock.patch("main.sounds.play_scorer") as scorer_sound:
            self.game._handle_block_contacts([block])
        effect_sound.assert_not_called()
        scorer_sound.assert_not_called()

    def test_plain_block_contact_rings_only_the_neutral_effect_sound(self):
        block = main.Block(0, 0, scorer=main.Scorer.NONE)
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        with mock.patch("main.sounds.play_effect") as effect_sound, \
             mock.patch("main.sounds.play_scorer") as scorer_sound:
            self.game._handle_block_contacts([block])
        effect_sound.assert_called_once_with(main.Effect.NONE)
        scorer_sound.assert_not_called()

    def test_start_and_finish_blocks_do_not_ring_a_scorer_sound(self):
        self.game.run_active = True
        for scorer in (main.Scorer.START, main.Scorer.FINISH):
            block = main.Block(0, 0, scorer=scorer)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            with mock.patch("main.sounds.play_scorer") as scorer_sound:
                self.game._handle_block_contacts([block])
            scorer_sound.assert_not_called()

    def test_shop_item_at_hits_item_cell(self):
        item = self.game.shop.items[0]
        pos = (self.game.shop.rect.x + item.col * main.GRID_SIZE + 5,
               self.game.shop.rect.y + item.row * main.GRID_SIZE + 5)

        self.assertIs(self.game.shop.item_at(pos), item)
        self.assertIsNone(self.game.shop.item_at((self.game.shop.rect.x - 10, self.game.shop.rect.y - 10)))

    def test_shop_sells_individual_components(self):
        kinds = {item.kind for item in self.game.shop.items}

        self.assertIn(main.Component.SHAPE, kinds)
        self.assertIn(main.Component.EFFECT, kinds)
        self.assertIn(main.Component.SCORER, kinds)

    def test_shop_sells_blocks(self):
        blocks = [item for item in self.game.shop.items if item.kind == "block"]

        self.assertGreater(len(blocks), 0)
        self.assertTrue(all(item.shape is not None and item.effect is not None and item.scorer is not None
                            for item in blocks))

    def test_shop_has_two_blocks_and_two_of_each_component_plus_third_scorer(self):
        kinds = [item.kind for item in self.game.shop.items]

        self.assertEqual(len(self.game.shop.items), 15)
        self.assertEqual(kinds.count("block"), 2)
        self.assertEqual(kinds.count("card"), 2)
        # One shop slot per offered action (the catalogue is bigger than the
        # room, so a refresh shows SHOP_ACTION_SLOTS of them).
        self.assertEqual(kinds.count("action"), main.SHOP_ACTION_SLOTS)
        self.assertEqual(kinds.count(main.Component.SHAPE), 2)
        self.assertEqual(kinds.count(main.Component.EFFECT), 2)
        self.assertEqual(kinds.count(main.Component.SCORER), 3)
        self.assertEqual(kinds.count(main.Component.CONDITION), 2)

    def test_shop_never_offers_the_free_default_parts(self):
        # The Rect shape, None effect, and None scorer are assembly defaults,
        # so they are never sold as loose components (blocks may still use
        # them — a plain wall is a legitimately useful pre-built block).
        for _ in range(200):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == main.Component.SHAPE:
                    self.assertNotEqual(item.value, main.Shape.RECT)
                elif item.kind == main.Component.EFFECT:
                    self.assertNotEqual(item.value, main.Effect.NONE)
                elif item.kind == main.Component.SCORER:
                    self.assertNotEqual(item.value, main.Scorer.NONE)

    def test_shop_always_offers_two_cards(self):
        cards = [item for item in self.game.shop.items if item.kind == "card"]
        self.assertEqual(len(cards), 2)
        # Two distinct cards are chosen at random from the pre-built pool (the
        # indivisible whole cards plus random (condition x scorer) combos).
        self.assertEqual(len({item.value for item in cards}), 2)
        self.assertTrue(all(item.value in main.Card.NAMES for item in cards))
        # The cards sit in the shop's bottom item row (with the conditions,
        # actions, and pre-built blocks).
        self.assertTrue(all(item.row == 3 for item in cards))

    def test_shop_cards_are_two_random_distinct_every_refresh(self):
        # Every reroll yields exactly two DIFFERENT cards from the pre-built pool.
        for _ in range(40):
            self.game.shop.refresh()
            cards = [item for item in self.game.shop.items if item.kind == "card"]
            self.assertEqual(len(cards), 2)
            self.assertEqual(len({item.value for item in cards}), 2)
            self.assertTrue(all(item.value in main.Card.NAMES for item in cards))

    def test_card_data_lives_in_components(self):
        # Only the indivisible whole cards (the Card.ORDER catalog) remain as
        # whole cards; every splittable card is now composed from a condition +
        # a scorer.
        self.assertEqual(main.Card.ORDER,
                         [main.Card.ERR_404, main.Card.BLUEPRINT, main.Card.SHOWMAN,
                          main.Card.GARDEN, main.Card.RIGGED_CASINO,
                          main.Card.CONQUISTADOR, main.Card.PEDESTAL,
                          main.Card.INFERNO, main.Card.DOPPELGANGER,
                          main.Card.COMPOUND_INTEREST, main.Card.COUPON,
                          main.Card.FACTORY, main.Card.MINESHAFT, main.Card.MARKET,
                          main.Card.WATCH, main.Card.TESSERACT,
                          main.Card.THOUSAND_HANDED])
        for value in main.Card.ORDER:
            self.assertTrue(main.Card.name(value))
            self.assertTrue(main.Card.comment(value))
            self.assertTrue(main.Card.description(value))
            self.assertGreater(main.Card.PRICES[value], 0)
            self.assertIn(value, main.Card.GLYPHS)
            self.assertIn(value, main.Card.COLORS)
        self.assertEqual(main.Card.description(main.Card.SHOWMAN),
                         "Lets cards you already own show up in the shop again, "
                         "so you can own more than one of the same card")
        # The three passive whole cards keep their exact descriptions.
        self.assertIn("+6 mult", main.Card.description(main.Card.GARDEN))
        self.assertIn("+xMult 3x more often",
                      main.Card.description(main.Card.RIGGED_CASINO))
        self.assertIn("4 random locked board squares",
                      main.Card.description(main.Card.CONQUISTADOR))
        # The ERR 404 card keeps its exact fake-fatal-error description.
        self.assertEqual(
            main.Card.description(main.Card.ERR_404),
            r"\marblatro\main.py, line 2339: 'self._return_card()' CardNotFoundError: Card was not found [FATAL]")
        # The classic splittable cards were removed: the conditions they split
        # into now carry their names AND their flavor comments.
        self.assertEqual(main.Condition.name(main.Condition.START), "Joker")
        self.assertEqual(main.Condition.comment(main.Condition.START), "Remember me?")
        self.assertEqual(main.Condition.comment(main.Condition.FRAGILE_BREAKS),
                         "Demolition expert.")
        self.assertEqual(main.Condition.comment(main.Condition.CASH_HELD),
                         "Money makes money.")
        # A composed magnitude card (Joker condition x +Mult) has full
        # metadata: a name, description, price, glyph, and color.
        value = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.MULT_ADD)
        self.assertEqual(main.Card.name(value), "Joker +Mult")
        self.assertIn("+4 mult", main.Card.description(value))
        self.assertGreater(main.Card.PRICES[value], 0)
        self.assertIn(value, main.Card.NAMES)
        self.assertIn(value, main.Card.GLYPHS)
        self.assertIn(value, main.Card.COLORS)

    def test_condition_data_lives_in_components(self):
        # Conditions are a purchasable component kind with the full catalogue:
        # the named triggers plus one collision condition per shape/effect.
        self.assertEqual(main.Component.CONDITION, "condition")
        # 13 named triggers (incl. Cozy, Painting and Synthesizer) + one
        # collision condition per shape/effect.
        self.assertEqual(len(main.CONDITION_ORDER),
                         13 + len(main.Shape.ORDER) + len(main.Effect.ORDER))
        # Named conditions are named after the card they were split from.
        self.assertEqual(main.Condition.name(main.Condition.COZY), "Cozy")
        self.assertEqual(main.Condition.name(main.Condition.START), "Joker")
        self.assertEqual(main.Condition.name(main.Condition.DISTANCE), "Explorer")
        self.assertEqual(main.Condition.name(main.Condition.FULLEST_COLUMN), "Pillar")
        self.assertIn("collides with a Pipe block",
                      main.condition_description(main.Condition.SHAPE_PIPE))
        self.assertGreater(main.COMPONENT_PRICES[
            (main.Component.CONDITION, main.Condition.START)], 0)
        comp = main.Component.condition_component(main.Condition.START)
        self.assertEqual(comp.kind, main.Component.CONDITION)
        self.assertEqual(comp.value, main.Condition.START)
        # Every shape/effect collision condition resolves back to its payload.
        for shape in main.Shape.ORDER:
            cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_shape(cond), shape)
        for effect in main.Effect.ORDER:
            cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_effect(cond), effect)

    def test_new_shapes_and_sticky_generate_card_conditions(self):
        # The two new line shapes and the sticky effect each auto-generate a
        # collision condition that builds a magnitude card like any other.
        for shape in (main.Shape.FLAT_LINE, main.Shape.CURVED_SLOPE_LINE):
            cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_shape(cond), shape)
            value = main.condition_scorer_card(cond, main.Scorer.MULT_ADD)
            self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)
        cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(main.Effect.STICKY)
        self.assertIn(cond, main.CONDITION_ORDER)
        self.assertEqual(components.condition_effect(cond), main.Effect.STICKY)

    def test_half_pipe_generates_card_condition(self):
        # The half-pipe shape auto-generates a collision condition that builds
        # a magnitude card like any other shape.
        shape = main.Shape.HALF_PIPE
        cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
        self.assertIn(cond, main.CONDITION_ORDER)
        self.assertEqual(components.condition_shape(cond), shape)
        value = main.condition_scorer_card(cond, main.Scorer.MULT_ADD)
        self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)

    def _new_shapes(self):
        return (main.Shape.SPIKE, main.Shape.PLATFORM, main.Shape.CORNER,
                main.Shape.PEG, main.Shape.SAWTOOTH, main.Shape.CRADLE)

    def test_new_shapes_have_names_descriptions_and_prices(self):
        # Each new shape is a first-class component: named, described, priced.
        for shape in self._new_shapes():
            self.assertIn(shape, main.Shape.ORDER)
            self.assertNotEqual(main.Shape.name(shape), "Unknown")
            self.assertTrue(main.shape_description(shape))
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)

    def test_new_shapes_generate_card_conditions(self):
        # Each new shape auto-generates a collision condition that builds a
        # magnitude card like every other shape, and resolves back to the shape.
        for shape in self._new_shapes():
            cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_shape(cond), shape)
            value = main.condition_scorer_card(cond, main.Scorer.MULT_ADD)
            self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)

    def test_effect_condition_ids_are_pinned_below_shape_growth(self):
        # EFFECT_BASE is a fixed id (not derived from len(Shape.ORDER)) so that
        # adding shapes never renumbers the effect collision conditions.
        self.assertGreater(main.Condition.EFFECT_BASE,
                           main.Condition.SHAPE_BASE + len(main.Shape.ORDER) - 1)

    def test_new_shapes_have_a_solid_point_and_an_empty_point(self):
        # A marble placed on each shape's solid collides; one placed clear of it
        # does not. This exercises the per-shape collision dispatch.
        solid_at = {
            main.Shape.SPIKE: lambda b: (b.rect.centerx, b.rect.bottom - 4),
            main.Shape.PLATFORM: lambda b: (b.rect.centerx, b.rect.bottom - 4),
            main.Shape.CORNER: lambda b: (b.rect.left + 4, b.rect.centery),
            main.Shape.PEG: lambda b: (b.rect.centerx, b.rect.centery),
            main.Shape.SAWTOOTH: lambda b: (b.rect.left + 5, b.rect.bottom - 4),
            main.Shape.CRADLE: lambda b: (b.rect.centerx, b.rect.bottom - 4),
        }
        for shape in self._new_shapes():
            block = main.Block(5, 5, shape=shape, scorer=main.Scorer.NONE)
            marble = main.Marble(*solid_at[shape](block))
            self.assertIsNotNone(marble.physics._block_collision(marble, block),
                                 f"{shape} solid point did not collide")
            far = main.Marble(block.rect.centerx, block.rect.top - 200)
            self.assertIsNone(far.physics._block_collision(far, block),
                              f"{shape} collided far from the shape")

    def test_new_shapes_stop_a_falling_marble(self):
        # A marble dropped onto each new shape is caught: it never passes below
        # the block's cell.
        for shape in self._new_shapes():
            block = main.Block(5, 5, shape=shape, scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 70)
            for _ in range(300):
                marble.physics.update(marble, main.DT, [block])
                self.assertLess(marble.position[1], block.rect.bottom,
                                f"{shape} let the marble fall through")

    def test_cradle_catches_and_settles_a_marble(self):
        # The cradle's wide floor catches a dropped marble and settles it there.
        block = main.Block(5, 5, shape=main.Shape.CRADLE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 70)
        for _ in range(300):
            marble.physics.update(marble, main.DT, [block])
        rest_y = block.rect.top + main.CRADLE_FLOOR_DEPTH - marble.radius
        self.assertAlmostEqual(marble.position[1], rest_y, delta=1.0)
        self.assertLess(abs(marble.velocity[1]), 1.0)

    def test_peg_is_a_small_circle_smaller_than_the_circle_shape(self):
        self.assertEqual(main.PEG_RADIUS, 5)
        self.assertLess(main.PEG_RADIUS, main.GRID_SIZE // 2)
        self.assertLess(main.PEG_RADIUS, main.MARBLE_RADIUS)

    def test_new_shapes_draw_without_raising(self):
        # Both the filled block draw and the outline-only icon draw handle each
        # new shape (borders on and off).
        for shape in self._new_shapes():
            for borders in (True, False):
                prev = main.BLOCK_BORDERS_ON
                main.BLOCK_BORDERS_ON = borders
                try:
                    surface = pygame.Surface([main.GRID_SIZE] * 2)
                    block = main.Block(0, 0, shape=shape,
                                       scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
                    block.draw(surface)
                    main.ui.draw_block_shape_only(
                        main.Block(0, 0, shape=shape, origin=(0, 0)), surface)
                finally:
                    main.BLOCK_BORDERS_ON = prev

    def test_rotated_new_shapes_still_collide(self):
        # The A-key angle (and ROTATE spin) rotates the hitbox: a marble at the
        # image of a solid point under that rotation still collides. This
        # exercises the oriented-rect path (platform) and the rotated-polygon
        # path (spike/cradle).
        for shape, local in ((main.Shape.PLATFORM, (0.5, 0.8)),
                             (main.Shape.SPIKE, (0.5, 0.9)),
                             (main.Shape.CRADLE, (0.5, 0.9))):
            block = main.Block(5, 5, shape=shape, scorer=main.Scorer.NONE)
            block.angle = 90
            px = block.rect.left + local[0] * block.rect.width
            py = block.rect.top + local[1] * block.rect.height
            rx = block.rect.centerx - (py - block.rect.centery)
            ry = block.rect.centery + (px - block.rect.centerx)
            marble = main.Marble(rx, ry)
            self.assertIsNotNone(marble.physics._block_collision(marble, block),
                                 f"{shape} rotated solid did not collide")

    def _new_effects(self):
        return (main.Effect.REPULSOR, main.Effect.CONVEYOR, main.Effect.ZIPPER,
                main.Effect.PHASE, main.Effect.SPLITTER)

    def test_new_effects_have_names_descriptions_and_prices(self):
        # Each new effect is a first-class component: named, described, priced,
        # and available to random shop blocks (REAL_ORDER).
        for effect in self._new_effects():
            self.assertIn(effect, main.Effect.REAL_ORDER)
            self.assertNotEqual(main.Effect.name(effect), "Unknown")
            self.assertTrue(main.effect_description(effect))
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.EFFECT, effect)], 0)
        # The splitter is the expensive one, priced at $124.
        self.assertEqual(
            main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.SPLITTER)], 124)

    def test_new_effects_generate_card_conditions(self):
        # Each new effect auto-generates a collision condition that resolves
        # back to the effect and builds a card like every other effect.
        for effect in self._new_effects():
            cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_effect(cond), effect)
            self.assertGreaterEqual(
                main.condition_scorer_card(cond, main.Scorer.MULT_ADD),
                components.CONDITION_CARD_OFFSET)

    def test_new_effects_were_appended_to_the_effect_order(self):
        # Effects must be APPENDED, never inserted: an effect collision
        # condition is EFFECT_BASE + Effect.ORDER.index(effect), so inserting
        # one would renumber every saved effect condition, card, and collection
        # entry. Sticky (the last effect before this batch) must keep id 12.
        self.assertEqual(main.Effect.ORDER.index(main.Effect.STICKY), 12)
        self.assertEqual(main.Effect.ORDER[-len(self._new_effects()):],
                         list(self._new_effects()))

    def test_repulsor_pushes_a_marble_away_and_black_hole_pulls_it_in(self):
        def drift(effect):
            block = main.Block(5, 5, effect=effect, scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 40)
            marble.velocity = np.array([0.0, 0.0])
            before = marble.position.copy()
            for _ in range(5):
                marble.physics.update(marble, main.DT, [block])
            return before[1] - marble.position[1]  # up is positive

        self.assertGreater(drift(main.Effect.REPULSOR), 0.0)
        self.assertLess(drift(main.Effect.BLACK_HOLE), 0.0)

    def test_conveyor_carries_a_marble_along_its_belt(self):
        # A marble resting on a conveyor is carried sideways; rotating the block
        # 180 degrees reverses the belt, so it is carried the other way.
        def drift(angle):
            block = main.Block(5, 5, effect=main.Effect.CONVEYOR,
                               scorer=main.Scorer.NONE)
            block.angle = angle
            marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
            marble.velocity = np.array([0.0, 0.0])
            for _ in range(5):
                marble.physics.update(marble, main.DT, [block])
            return marble.velocity[0]

        self.assertGreater(drift(0), 0.0)
        self.assertLess(drift(180), 0.0)

    def test_conveyor_holds_a_constant_belt_speed_instead_of_accelerating(self):
        # A belt carries the marble at its OWN constant speed: the along-belt
        # speed is set when the marble touches down and then held there, so the
        # marble is never accelerated frame after frame.
        block = main.Block(5, 5, effect=main.Effect.CONVEYOR, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([0.0, 0.0])
        speeds = []
        for _ in range(120):
            # A long belt: keep the marble on it so the speed can be watched.
            marble.position[0] = block.rect.centerx
            marble.physics.update(marble, main.DT, [block])
            speeds.append(float(marble.velocity[0]))
        self.assertAlmostEqual(speeds[0], main.CONVEYOR_SPEED, delta=10.0)
        self.assertAlmostEqual(speeds[-1], main.CONVEYOR_SPEED, delta=10.0)
        self.assertLessEqual(max(speeds), main.CONVEYOR_SPEED + 0.01,
                             "the belt accelerated the marble past its own speed")

    def test_conveyor_does_not_slow_a_faster_marble_or_scale_with_mass(self):
        # A belt only adds speed: a marble already moving faster along the belt
        # keeps its own speed, and the belt speed is the same for every marble
        # (a light marble is not flung harder by a belt).
        block = main.Block(5, 5, effect=main.Effect.CONVEYOR, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([900.0, 0.0])
        marble.mass = 0.35
        marble.effect_mass_mult = 0.5
        marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.velocity[0], main.CONVEYOR_SPEED,
                           "the belt slowed a marble that was already faster")

    def test_zipper_is_passable_with_its_arrow_and_solid_against_it(self):
        block = main.Block(5, 5, effect=main.Effect.ZIPPER, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        # The default arrow points up: travelling up passes straight through...
        marble.velocity = np.array([0.0, -200.0])
        self.assertIsNone(marble.physics._block_collision(marble, block))
        # ...while travelling down (against the arrow) collides.
        marble.velocity = np.array([0.0, 200.0])
        self.assertIsNotNone(marble.physics._block_collision(marble, block))

    def test_zipper_lets_a_marble_through_only_the_open_way(self):
        # Arrow down (a rotated zipper): a dropped marble falls right through.
        open_block = main.Block(5, 5, effect=main.Effect.ZIPPER,
                                scorer=main.Scorer.NONE)
        open_block.angle = 180
        marble = main.Marble(open_block.rect.centerx, open_block.rect.top - 10)
        for _ in range(60):
            marble.physics.update(marble, main.DT, [open_block])
        self.assertGreater(marble.position[1], open_block.rect.bottom)
        # Arrow up (the default): the same drop is caught on top of it.
        shut_block = main.Block(5, 5, effect=main.Effect.ZIPPER,
                                scorer=main.Scorer.NONE)
        marble = main.Marble(shut_block.rect.centerx, shut_block.rect.top - 10)
        for _ in range(120):
            marble.physics.update(marble, main.DT, [shut_block])
        self.assertLess(marble.position[1], shut_block.rect.bottom)

    def test_zipper_sides_stay_solid_while_moving_along_the_arrow(self):
        # Regression: the gate used to test only the velocity direction, so a
        # marble whose velocity had ANY component along the arrow (one riding a
        # conveyor up, say) was let through the block's solid SIDE and crept out
        # through it a frame at a time. Only the marble-wide door along the
        # arrow is passable.
        block = main.Block(5, 5, effect=main.Effect.ZIPPER, scorer=main.Scorer.NONE)
        for velocity in ((300.0, -20.0), (60.0, -5.0), (0.0, -50.0)):
            marble = main.Marble(block.rect.left - main.MARBLE_RADIUS + 2,
                                 block.rect.centery)
            marble.velocity = np.array(velocity)
            self.assertIsNotNone(
                marble.physics._block_collision(marble, block),
                f"a marble moving {velocity} tunnelled through the zipper's side")
        # The door is still open to a marble in its channel...
        in_door = main.Marble(block.rect.centerx, block.rect.centery)
        in_door.velocity = np.array([0.0, -300.0])
        self.assertIsNone(in_door.physics._block_collision(in_door, block))
        # ...and the closed face stays solid away from the channel.
        for offset in (12, 20):
            off_centre = main.Marble(block.rect.centerx + offset,
                                     block.rect.bottom + main.MARBLE_RADIUS - 2)
            off_centre.velocity = np.array([0.0, -300.0])
            self.assertIsNotNone(
                off_centre.physics._block_collision(off_centre, block),
                f"the zipper door opened {offset}px off centre")

    def test_component_images_of_corner_and_cradle_have_no_inner_lines(self):
        # A component/ghost image draws the shape's own outline: the corner's
        # two legs and the cradle's pieces used to be outlined one by one, which
        # drew a seam inside the shape where they overlap.
        surface = pygame.Surface([main.GRID_SIZE] * 2)

        corner = main.Block(0, 0, shape=main.Shape.CORNER, origin=(0, 0))
        surface.fill(main.BLACK)
        main.ui.draw_block_shape_only(corner, surface)
        self.assertNotEqual(
            surface.get_at((corner.rect.width // 2, corner.rect.height * 3 // 4))[:3],
            main.WHITE, "the corner's legs still show a seam inside the shape")
        self.assertEqual(
            surface.get_at((corner.rect.width // 2, corner.rect.height // 4))[:3],
            main.WHITE, "the corner's L outline is missing")

        cradle = main.Block(0, 0, shape=main.Shape.CRADLE, origin=(0, 0))
        surface.fill(main.BLACK)
        main.ui.draw_block_shape_only(cradle, surface)
        self.assertNotEqual(
            surface.get_at((2, main.CRADLE_FLOOR_DEPTH))[:3], main.WHITE,
            "the cradle's wedges still show a seam on the floor slab")
        self.assertEqual(
            surface.get_at((cradle.rect.width // 2, main.CRADLE_FLOOR_DEPTH))[:3],
            main.WHITE, "the cradle's flat floor outline is missing")

    def test_phase_grants_one_second_of_no_collisions(self):
        # Touching a phase block arms PHASE_DURATION of phasing, which lets the
        # marble fall straight through a solid wall below it.
        phase = main.Block(5, 5, effect=main.Effect.PHASE, scorer=main.Scorer.NONE)
        wall = main.Block(5, 6, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        marble = main.Marble(phase.rect.centerx, phase.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(2):
            marble.physics.update(marble, main.DT, [phase, wall])
        self.assertAlmostEqual(marble.phase_timer, main.PHASE_DURATION,
                               delta=2 * main.DT + 1e-6)
        for _ in range(30):
            marble.physics.update(marble, main.DT, [phase, wall])
        self.assertGreater(marble.phase_timer, 0.0)
        self.assertGreater(marble.position[1], wall.rect.bottom,
                           "a phasing marble did not pass through the wall")

    def test_phase_does_not_rearm_while_the_marble_stays_on_the_block(self):
        # A phase block may not grant another phase until the marble is clear of
        # it, so a marble that stays on it can't phase forever.
        block = main.Block(5, 5, effect=main.Effect.PHASE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.phase_block = block
        marble.phase_timer = 0.0
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(30):
            marble.physics.update(marble, main.DT, [block])
            self.assertEqual(marble.phase_timer, 0.0)

    def test_physics_records_the_arrival_velocity_of_a_contact(self):
        # The splitter reflects the velocity the marble ARRIVED with, so the
        # first record of a contact must survive the rest of the frame (later
        # sub-steps re-collide with an already-stopped velocity).
        block = main.Block(4, 4, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 60)
        marble.velocity = np.array([0.0, 400.0])
        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])
            if block in marble.collisions_this_tick:
                break
        self.assertIn(block, marble.collisions_this_tick)
        incoming = marble.contact_incoming.get(block)
        self.assertIsNotNone(incoming)
        self.assertGreater(float(incoming[1]), 50.0)
        self.assertIn(block, marble.contact_normals)

    def test_splitter_copy_is_the_reversed_reflection_of_the_marble(self):
        block = main.Block(5, 5, effect=main.Effect.SPLITTER, scorer=main.Scorer.NONE)
        marble = self._add_marble((block.rect.centerx,
                                   block.rect.top - main.MARBLE_RADIUS))
        # By the time the splitter fires the collision response has already
        # stopped the marble, so the copy reflects the velocity it ARRIVED with.
        arrived = np.array([60.0, 200.0])
        marble.velocity = np.array([0.0, 0.0])
        normal = np.array([0.0, -1.0])  # the floor normal of the block below
        marble.contact_normals = {block: normal}
        marble.contact_incoming = {block: arrived}
        copy = self.game._split_marble(marble, block)
        self.assertIsNotNone(copy)
        self.assertIsInstance(copy, main.Marble)
        self.assertEqual(len(self.game.marbles), 2)
        expected = -arrived + 2.0 * float(np.dot(arrived, normal)) * normal
        self.assertTrue(np.allclose(copy.velocity, expected),
                        f"copy velocity {copy.velocity} != {expected}")
        # The copy keeps the marble's speed and look, and starts where it was.
        self.assertAlmostEqual(float(np.linalg.norm(copy.velocity)),
                               float(np.linalg.norm(arrived)), places=6)
        self.assertEqual(copy.marble_type, marble.marble_type)
        self.assertTrue(np.allclose(copy.position, marble.position))
        # A copy differs from the original (it is not the same object) and the
        # original is left alone.
        self.assertIsNot(copy, marble)
        self.assertTrue(np.allclose(marble.velocity, np.array([0.0, 0.0])))

    def test_splitter_stops_splitting_at_the_marble_cap(self):
        block = main.Block(5, 5, effect=main.Effect.SPLITTER, scorer=main.Scorer.NONE)
        marble = self._add_marble((block.rect.centerx, block.rect.top - 10))
        for _ in range(main.MAX_MARBLES + 4):
            self.game._split_marble(marble, block)
        self.assertEqual(len(self.game.marbles), main.MAX_MARBLES)
        self.assertIsNone(self.game._split_marble(marble, block))

    def test_splitter_block_splits_the_marble_on_a_fresh_touch(self):
        block = main.Block(5, 5, effect=main.Effect.SPLITTER, scorer=main.Scorer.NONE)
        self.game.grid[(5, 5)] = block
        self.game.run_active = True
        marble = self._add_marble((block.rect.centerx,
                                   block.rect.top - main.MARBLE_RADIUS))
        marble.velocity = np.array([0.0, 100.0])
        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(len(self.game.marbles), 2)
        self.assertEqual(block.triggers_left, block.trigger_limit - 1)

    def test_marbles_collide_with_each_other(self):
        a = self._add_marble((300.0, 300.0))
        b = self._add_marble((310.0, 300.0))  # overlapping (radius 8 each)
        a.velocity = np.array([50.0, 0.0])
        b.velocity = np.array([-50.0, 0.0])
        a.physics.resolve_marble_collisions(self.game.marbles)
        # Pushed apart along the line between their centers...
        self.assertGreater(b.position[0] - a.position[0], 10.0)
        # ...and their normal speeds swapped (an equal-mass elastic hit).
        self.assertLess(a.velocity[0], 0.0)
        self.assertGreater(b.velocity[0], 0.0)

    def test_a_phasing_marble_passes_through_other_marbles(self):
        a = self._add_marble((300.0, 300.0))
        b = self._add_marble((305.0, 300.0))
        a.phase_timer = 0.5
        a.physics.resolve_marble_collisions(self.game.marbles)
        # Still overlapping: a phasing marble is skipped by the marble-vs-marble
        # separation (the phase effect passes through everything).
        self.assertLess(float(np.linalg.norm(b.position - a.position)),
                        a.radius + b.radius)

    def test_bump_shape_is_a_half_disc_dome(self):
        # The bump is a first-class shape: named, described, priced, drawing
        # both ways, and auto-generating a collision condition that builds a
        # card — the same treatment as the other shapes.
        shape = main.Shape.BUMP
        self.assertIn(shape, main.Shape.ORDER)
        self.assertNotEqual(main.Shape.name(shape), "Unknown")
        self.assertTrue(main.shape_description(shape))
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)
        cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
        self.assertIn(cond, main.CONDITION_ORDER)
        self.assertEqual(components.condition_shape(cond), shape)
        self.assertGreaterEqual(main.condition_scorer_card(cond, main.Scorer.MULT_ADD),
                                components.CONDITION_CARD_OFFSET)
        for borders in (True, False):
            prev = main.BLOCK_BORDERS_ON
            main.BLOCK_BORDERS_ON = borders
            try:
                surface = pygame.Surface([main.GRID_SIZE] * 2)
                block = main.Block(0, 0, shape=shape, scorer=main.Scorer.CHIPS_ADD,
                                   origin=(0, 0))
                block.draw(surface)
                main.ui.draw_block_shape_only(
                    main.Block(0, 0, shape=shape, origin=(0, 0)), surface)
            finally:
                main.BLOCK_BORDERS_ON = prev

    def test_bump_dome_sits_on_the_cell_bottom_edge(self):
        block = main.Block(5, 5, shape=main.Shape.BUMP, scorer=main.Scorer.NONE)
        pts = block.get_bump_points
        self.assertAlmostEqual(max(p[1] for p in pts), block.rect.bottom, delta=0.01)
        self.assertAlmostEqual(min(p[1] for p in pts),
                               block.rect.bottom - main.GRID_SIZE / 2, delta=1.0)
        self.assertAlmostEqual(min(p[0] for p in pts), block.rect.left, delta=1.0)
        self.assertAlmostEqual(max(p[0] for p in pts), block.rect.right, delta=1.0)

    def test_bump_is_solid_in_the_dome_and_empty_above_it(self):
        block = main.Block(5, 5, shape=main.Shape.BUMP, scorer=main.Scorer.NONE)
        apex_y = block.rect.bottom - main.GRID_SIZE // 2
        on_dome = main.Marble(block.rect.centerx + 8, apex_y + 4)
        self.assertIsNotNone(on_dome.physics._block_collision(on_dome, block))
        above = main.Marble(block.rect.centerx, apex_y - main.MARBLE_RADIUS - 2)
        self.assertIsNone(above.physics._block_collision(above, block))

    def test_bump_sheds_an_off_center_marble_sideways(self):
        # A marble landing off the crown slides down the dome instead of staying
        # put; one balanced exactly on the crown rests there (the dome is
        # symmetric), but neither ever falls through the bump.
        block = main.Block(5, 5, shape=main.Shape.BUMP, scorer=main.Scorer.NONE)
        crown = block.rect.bottom - main.GRID_SIZE // 2 - main.MARBLE_RADIUS
        marble = main.Marble(block.rect.centerx + 3, crown)
        for _ in range(120):
            marble.physics.update(marble, main.DT, [block])
        self.assertGreater(abs(marble.position[0] - block.rect.centerx), 5.0)
        balanced = main.Marble(block.rect.centerx, crown)
        for _ in range(120):
            balanced.physics.update(balanced, main.DT, [block])
        self.assertLess(balanced.position[1], block.rect.bottom)

    def test_shop_offers_two_conditions_next_to_cards(self):
        # Two random conditions sit next to the two whole cards in the shop.
        conds = [i for i in self.game.shop.items if i.kind == main.Component.CONDITION]
        self.assertEqual(len(conds), 2)
        self.assertTrue(all(i.row == 3 for i in conds))
        self.assertTrue(all(i.value in main.CONDITION_ORDER for i in conds))

    def test_buying_condition_adds_to_toolbox_and_discovers(self):
        # Buying a condition puts it in the toolbox and reveals it.
        self.game.cash = 1000
        cond = next(i for i in self.game.shop.items
                    if i.kind == main.Component.CONDITION)
        self.game._buy_shop_item(cond)
        self.assertIn(cond, self.game.toolbox.items)
        self.assertTrue(collection.is_condition_discovered(cond.value))
        self.assertTrue(any(p.title == "New condition" for p in self.game.popups))

    def _assign_and_build(self, condition, scorer):
        """Assign a condition + scorer in the toolbox and press S (build)."""
        self.game.toolbox.items.clear()
        self.game.toolbox.add(condition)
        self.game.toolbox.add(scorer)
        self.game._select_toolbox_component(condition)
        self.game._select_toolbox_component(scorer)
        self.game._build_card()

    def test_building_collision_card_from_condition_and_scorer(self):
        # Pipe condition + +Mult scorer builds the Pipe +Mult magnitude card.
        cond = main.Component.condition_component(main.Condition.SHAPE_PIPE)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self._assign_and_build(cond, scorer)
        expected = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                              main.Scorer.MULT_ADD)
        self.assertGreaterEqual(expected, components.CONDITION_CARD_OFFSET)
        self.assertEqual(len(self.game.cards), 1)
        self.assertEqual(self.game.cards[0].value, expected)
        self.assertEqual(main.Card.name(expected), "Pipe +Mult")
        self.assertNotIn(cond, self.game.toolbox.items)
        self.assertNotIn(scorer, self.game.toolbox.items)

    def test_building_canonical_named_card_recreates_whole_card(self):
        # Start condition + +Mult scorer recreates the Joker (a whole card).
        cond = main.Component.condition_component(main.Condition.START)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self._assign_and_build(cond, scorer)
        self.assertEqual(len(self.game.cards), 1)
        self.assertEqual(self.game.cards[0].value, main.Card.JOKER)

    def test_building_magnitude_card_creates_custom_card(self):
        # Explorer (Distance) + +Mult builds a derived custom card.
        cond = main.Component.condition_component(main.Condition.DISTANCE)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self._assign_and_build(cond, scorer)
        self.assertEqual(len(self.game.cards), 1)
        value = self.game.cards[0].value
        self.assertEqual(value, main.condition_scorer_card(main.Condition.DISTANCE,
                                                           main.Scorer.MULT_ADD))
        self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)
        self.assertEqual(main.Card.name(value), "Explorer +Mult")

    def test_card_builder_requires_a_scorer_and_known_combo(self):
        # A condition alone can't build anything.
        cond = main.Component.condition_component(main.Condition.SHAPE_PIPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(cond)
        self.game._select_toolbox_component(cond)
        self.game._build_card()
        self.assertEqual(self.game.cards, [])
        self.assertTrue(self.game.shop_message)
        # Quick DOES pair with a run-END condition now: there is no next block
        # after the run, so the card pays from the run's last block hit instead.
        dist = main.Component.condition_component(main.Condition.DISTANCE)
        quick = main.Component.scorer_component(main.Scorer.QUICK, amount=5)
        self.game.toolbox.add(dist)
        self.game.toolbox.add(quick)
        self.game._select_toolbox_component(dist)
        self.game._select_toolbox_component(quick)
        self.game._build_card()
        self.assertEqual(len(self.game.cards), 1)
        self.assertEqual(main.Card.name(self.game.cards[0].value),
                         "Explorer card (Quick)")
        # Air Time (Plane) pairs with ANY scorer too: +Mult builds a
        # proportional Plane +Mult card (half the +4 base = +2 mult/air sec).
        air = main.Component.condition_component(main.Condition.AIR_TIME)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self.game.toolbox.add(air)
        self.game.toolbox.add(scorer)
        self.game._select_toolbox_component(air)
        self.game._select_toolbox_component(scorer)
        self.game._build_card()
        self.assertEqual(len(self.game.cards), 2)
        value = self.game.cards[1].value
        self.assertEqual(main.Card.name(value), "Plane +Mult")
        self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)

    def test_start_chips_custom_card_gives_chips_at_run_start(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 50))
        self.game.score_chips = 0
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 30)

    def test_distance_custom_cards_scale_with_distance_travelled(self):
        # A full board (fraction 1.0) is 4 units: +120 chips or +16 mult.
        marble = self._add_marble()
        marble.distance = main.GRID_SIZE * main.GRID_WIDTH * main.GRID_HEIGHT
        chips_value = main.condition_scorer_card(main.Condition.DISTANCE,
                                                 main.Scorer.CHIPS_ADD)
        mult_value = main.condition_scorer_card(main.Condition.DISTANCE,
                                                main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(chips_value, 50))
        self.game.cards.append(main.CardItem(mult_value, 50))
        self.game.score_chips = 0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_chips, 120)
        self.assertEqual(self.game.score_mult, 17)

    def test_collection_entries_hide_splittable_cards_and_list_conditions(self):
        # Only the indivisible cards appear as card entries; conditions are
        # their own collection entries.
        entries = self.game._collection_entries()
        card_entries = [e for e in entries if e[0] == "card"]
        self.assertEqual(len(card_entries), len(main.Card.ORDER))
        self.assertEqual({e[1] for e in card_entries}, set(main.Card.ORDER))
        cond_entries = [e for e in entries if e[0] == "condition"]
        self.assertEqual(len(cond_entries), len(components.CONDITION_ORDER))

    def test_buying_splittable_card_reveals_its_halves(self):
        # Buying a whole splittable card (Joker) reveals its condition + scorer
        # halves instead of the card itself.
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.JOKER, 20))
        self.assertFalse(collection.is_card_discovered(main.Card.JOKER))
        condition, scorer = main.splittable_card_condition_scorer(main.Card.JOKER)
        self.assertEqual(condition, main.Condition.START)
        self.assertEqual(scorer, main.Scorer.MULT_ADD)
        self.assertTrue(collection.is_condition_discovered(condition))
        self.assertTrue(collection.is_component_discovered(main.Component.SCORER, scorer))
        self.assertTrue(any(p.title == "New condition" for p in self.game.popups))

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

    def test_every_block_scorer_is_a_card_scorer(self):
        # The card scorer set covers every block payoff scorer, and a flat
        # scorer builds a generic card with a collision condition.
        self.assertIn(main.Scorer.CASH, components.CARD_SCORERS)
        self.assertIn(main.Scorer.SHARP, components.CARD_SCORERS)
        self.assertIn(main.Scorer.QUICK, components.CARD_SCORERS)
        self.assertIn(main.Scorer.PARTS, components.CARD_SCORERS)
        self.assertIn(main.Scorer.IDEAS, components.CARD_SCORERS)
        for scorer in (main.Scorer.CASH, main.Scorer.SHARP, main.Scorer.QUICK,
                       main.Scorer.PARTS, main.Scorer.SHREDS,
                       main.Scorer.RUBBLE, main.Scorer.IDEAS):
            value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, scorer)
            self.assertIsNotNone(value)
            self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
            self.assertEqual(main.Card.name(value),
                             f"Pipe card ({main.Scorer.name(scorer)})")
        # Quick pairs with a run-end condition too: the card pays from the
        # speed of the run's LAST block hit (there is no next block then).
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.QUICK)
        self.assertIsNotNone(value)
        self.assertEqual(main.Card.name(value), "Explorer card (Quick)")

    def test_every_condition_and_card_scorer_pair_forms_a_card(self):
        # The whole grid: EVERY condition pairs with EVERY card scorer to form
        # a real card (a name, a description, a price and a split back into its
        # two halves), so no combination a player can assemble is a dead end.
        self.assertEqual(len(components.CARD_SCORERS),
                         len(main.Scorer.ORDER) - 3)  # NONE, START, FINISH
        for role in (main.Scorer.NONE, main.Scorer.START, main.Scorer.FINISH):
            self.assertNotIn(role, components.CARD_SCORERS)
        pairs = 0
        for cond in components.CONDITION_ORDER:
            cond_desc = main.condition_description(cond)
            flat_desc = components.condition_flat_description(cond)
            for scorer in components.CARD_SCORERS:
                value = main.condition_scorer_card(cond, scorer)
                self.assertIsNotNone(value, (cond, scorer))
                desc = main.Card.description(value)
                self.assertTrue(main.Card.name(value))
                self.assertTrue(desc, (cond, scorer))
                self.assertGreater(main.Card.PRICES[value], 0)
                # Every card says what makes its condition fire: a unit scorer
                # scales per unit (the magnitude phrasing), while a flat scorer
                # pays one trigger and reads the condition's gate.
                expected = (cond_desc if scorer in components.UNIT_CARD_SCORERS
                            else flat_desc)
                self.assertIn(expected, desc)
                # ...and no card falls back to the "unknown scorer" text or
                # leaks the no-condition placeholder.
                self.assertNotIn("Unknown", desc)
                self.assertNotIn("its block", desc)
                # The card splits back into exactly the pair that built it.
                self.assertEqual(
                    main.splittable_card_condition_scorer(value), (cond, scorer))
                pairs += 1
        self.assertEqual(pairs, len(components.CONDITION_ORDER)
                         * len(components.CARD_SCORERS))

    def test_flat_cards_state_the_gate_not_a_per_unit_measure(self):
        # A flat card pays ONE trigger, so it must not claim to scale with the
        # condition's measured units ("for each second the marble is in the
        # air", "scaled up to 4x base by the distance the marble travels"):
        # it states the gate instead. The magnitude (unit scorer) version of
        # the same condition keeps the measure, because it really scales.
        distance_measure = "scaled up to 4x base by the distance the marble travels"
        air_measure = "for each second the marble is in the air"

        flat_end = main.Card.description(
            main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.SUMMIT))
        self.assertNotIn(distance_measure, flat_end)
        self.assertIn("once the marble has traveled", flat_end)

        unit_end = main.Card.description(
            main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.MULT_ADD))
        self.assertIn(distance_measure, unit_end)

        flat_air = main.Card.description(
            main.condition_scorer_card(main.Condition.AIR_TIME, main.Scorer.PARTS))
        self.assertNotIn(air_measure, flat_air)
        self.assertIn("once the marble has been in the air", flat_air)

        unit_air = main.Card.description(
            main.condition_scorer_card(main.Condition.AIR_TIME, main.Scorer.CHIPS_ADD))
        self.assertIn(air_measure, unit_air)

        # Conditions that never had a measure read the same either way, and a
        # collision condition is untouched.
        for scorer in (main.Scorer.PARTS, main.Scorer.MULT_ADD):
            cozy = main.Card.description(
                main.condition_scorer_card(main.Condition.COZY, scorer))
            self.assertIn("when the board has 10 unlocked units or fewer", cozy)
        pipe = main.Card.description(
            main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.CASH))
        self.assertIn("when the marble collides with a Pipe block", pipe)
        self.assertIn("$15 when the marble collides", pipe)  # no comma: a clause
        # A time adverbial gets its own comma instead of running the two
        # clauses together ("… the first block the marble hits this run at the
        # start of the run").
        row = main.Card.description(
            main.condition_scorer_card(main.Condition.FULLEST_COLUMN,
                                       main.Scorer.POWERLINE))
        self.assertIn("this run, at the start of the run", row)
        # The magnitude phrasing is still available for the unit cards and for
        # anything else that asks for it (the collection's condition rows).
        self.assertIn(distance_measure,
                      main.condition_description(main.Condition.DISTANCE))
        self.assertEqual(components.condition_flat_description(main.Condition.START),
                         main.condition_description(main.Condition.START))

    def test_block_relative_cards_name_the_block_their_condition_hands_them(self):
        # A card has no position of its own, so a position-reading payoff (a
        # row, a border, neighbours, a bomb) says which block it reads.
        for scorer in (main.Scorer.POWERLINE, main.Scorer.FRONTIER,
                       main.Scorer.CLUSTER, main.Scorer.BOMB):
            collision = main.Card.description(
                main.condition_scorer_card(main.Condition.SHAPE_PIPE, scorer))
            self.assertIn("the collided block", collision)
            start = main.Card.description(
                main.condition_scorer_card(main.Condition.START, scorer))
            self.assertIn("the first block the marble hits this run", start)
            end = main.Card.description(
                main.condition_scorer_card(main.Condition.DISTANCE, scorer))
            self.assertIn("the last block the marble hits this run", end)
            fragile = main.Card.description(
                main.condition_scorer_card(main.Condition.FRAGILE_BREAKS, scorer))
            self.assertIn("the shattered block", fragile)

    def test_powerline_card_counts_the_blocks_in_the_collided_row(self):
        # A Pipe x Powerline card pays its chips for every block in the row of
        # the block the marble hit (the collided block included).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.POWERLINE)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        for x in (2, 5):
            self.game.grid[(x, 4)] = main.Block(x, 4, scorer=main.Scorer.NONE)
        pipe = main.Block(0, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.grid[(0, 4)] = pipe
        self._card_fire(pipe)
        self.assertEqual(self.game.score_chips,
                         main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE] * 3)

    def test_cluster_card_counts_the_blocks_next_to_the_collided_block(self):
        # A Cluster card pays its mult for each block orthogonally adjacent to
        # the collided block (two here, one of them diagonal and not counted).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.CLUSTER)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        for cell in ((3, 4), (4, 5), (3, 5)):  # (3,5) is diagonal
            self.game.grid[cell] = main.Block(cell[0], cell[1],
                                              scorer=main.Scorer.NONE)
        pipe = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.grid[(4, 4)] = pipe
        self._card_fire(pipe)
        self.assertEqual(self.game.score_mult,
                         1 + main.Scorer.DEFAULT_AMOUNT[main.Scorer.CLUSTER] * 2)

    def test_colossus_card_scales_with_the_touching_marble_radius(self):
        # A Colossus card pays its xMult for each pixel the touching marble's
        # radius is above the base size (a card measures the marble it fires
        # with, or the run's own marble when the condition hands it none).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.COLOSSUS)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 2
        marble = self._add_marble()
        marble.radius = main.MARBLE_RADIUS + 5
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=marble)
        self.assertAlmostEqual(self.game.score_mult,
                               2 * (1 + 5 * main.Scorer.DEFAULT_AMOUNT[main.Scorer.COLOSSUS]))

    def test_echo_card_refires_the_collided_block_scorer(self):
        # An Echo card has no "block touched before it", so it copies the block
        # its condition is about: a Pipe x Echo card re-fires the collided
        # block's own scorer (here a Cash block, paid twice over).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.ECHO)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.cash = 0
        self.game.run_cash_gained = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.CASH)
        self.game.grid[(0, 0)] = pipe
        self._card_fire(pipe)
        self.assertEqual(self.game.run_cash_gained,
                         2 * main.Scorer.DEFAULT_AMOUNT[main.Scorer.CASH])

    def test_bomb_card_primes_the_collided_cell(self):
        # A Bomb card plants a bomb on the cell of the block its condition
        # hands it, exactly like a Bomb block (the units around it unlock after
        # the run).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.BOMB)
        self.game.cards.append(main.CardItem(value, 40))
        pipe = main.Block(3, 2, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.assertNotIn((3, 2), self.game.bomb_cells)
        self._card_fire(pipe)
        self.assertIn((3, 2), self.game.bomb_cells)

    def test_bomb_card_is_destroyed_after_the_run(self):
        # A Bomb card is a one-run deal: it goes off with the block it primed,
        # so it is destroyed after the run for good (only a retry keeps it).
        bomb = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                         main.Scorer.BOMB)
        cash = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                         main.Scorer.CASH)
        self.game.cards = [main.CardItem(bomb, 40), main.CardItem(cash, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        values = [card.value for card in self.game.cards]
        self.assertNotIn(bomb, values)
        self.assertIn(cash, values)

    def test_bomb_card_survives_retry(self):
        # Retrying the run discards it, so the Bomb card is kept.
        bomb = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                         main.Scorer.BOMB)
        self.game.cards = [main.CardItem(bomb, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual([card.value for card in self.game.cards], [bomb])

    def test_start_block_relative_card_waits_for_the_first_block(self):
        # A start-phase Powerline card has no row to read at run start, so it
        # waits for the run's first contacted block and pays from that row.
        value = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.POWERLINE)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game._apply_cards()  # run start: no block has been hit yet
        self.assertEqual(self.game.score_chips, 0)
        import cards
        first = main.Block(1, 6, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.grid[(1, 6)] = first
        self.game.grid[(7, 6)] = main.Block(7, 6, scorer=main.Scorer.NONE)
        cards.fire_first_block_cards(self.game, first)
        self.assertEqual(self.game.score_chips,
                         main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE] * 2)

    def test_end_quick_card_pays_from_the_last_contact_speed(self):
        # There is no NEXT block after the run, so an end-phase Quick card pays
        # from the speed the marble had at its last block contact.
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_speed = 400.0
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_chips, 400 * main.QUICK_SCALE)

    def test_end_quick_card_grants_nothing_without_a_block_contact(self):
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_speed = 0.0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_chips, 0)

    def test_lucky_card_keeps_its_pre_rolled_outcome_for_the_whole_run(self):
        # A Lucky card's two rolls are chosen BEFORE the run (like a Lucky
        # block's), so the patched draw below can't change the outcome.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.LUCKY)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.cash = 0
        with mock.patch("main.random.random", side_effect=[0.0, 0.9]):
            self.game._roll_run_random_outputs()
        # Two matching blocks are hit (each with a trigger to spend), so the
        # card fires twice and pays the SAME pre-rolled 130 chips both times.
        for x in (0, 2):
            pipe = main.Block(x, 0, shape=main.Shape.PIPE,
                              scorer=main.Scorer.NONE)
            self.game.grid[(x, 0)] = pipe
            self._card_fire(pipe)
        self.assertEqual(self.game.score_chips, 260)
        self.assertEqual(self.game.cash, 0)

    def test_card_scorer_draw_covers_every_scorer_for_every_phase(self):
        # The shop's random card scorers are drawn from the full set for every
        # condition phase (Quick included: an end-phase Quick card pays from the
        # last block hit), so no scorer is quietly excluded from a phase.
        random.seed(20240607)
        for cond in (main.Condition.SHAPE_PIPE, main.Condition.START,
                     main.Condition.DISTANCE, main.Condition.FRAGILE_BREAKS):
            rolled = {main._random_card_scorer(cond) for _ in range(400)}
            self.assertEqual(rolled, set(components.CARD_SCORERS))

    def test_every_named_condition_pairs_with_every_unit_scorer(self):
        # The full grid: every named condition can build a card with every unit
        # scorer, and every produced value has metadata (it could be offered
        # pre-built in the shop).
        for cond in components.NAMED_CONDITION_ORDER:
            for scorer in (main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD,
                           main.Scorer.MULT_MUL):
                value = main.condition_scorer_card(cond, scorer)
                self.assertIsNotNone(value)
                self.assertIn(value, main.Card.NAMES)
                self.assertGreater(main.Card.PRICES[value], 0)

    def test_condition_scorer_card_splits_back_into_its_pair(self):
        # (condition, scorer) maps to one card, and that card decomposes back
        # into exactly that pair (only the indivisible cards lack a split).
        for cond in components.NAMED_CONDITION_ORDER:
            for scorer in (main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD,
                           main.Scorer.MULT_MUL):
                value = main.condition_scorer_card(cond, scorer)
                if value in (main.Card.ERR_404, main.Card.BLUEPRINT,
                             main.Card.SHOWMAN):
                    continue
                self.assertEqual(components.splittable_card_condition_scorer(value),
                                 (cond, scorer))

    def test_canonical_combo_recreates_original_card_value(self):
        # Building (Joker condition, +Mult) still yields the classic Joker card.
        self.assertEqual(main.condition_scorer_card(main.Condition.START,
                                                    main.Scorer.MULT_ADD),
                         main.Card.JOKER)

    def test_plane_plus_mult_scales_proportionally_with_air_time(self):
        # Air Time (Plane) has ratio 0.5, so +Mult pays half the +4 base = +2
        # mult per air second at the end of the run.
        value = main.condition_scorer_card(main.Condition.AIR_TIME,
                                           main.Scorer.MULT_ADD)
        self.assertEqual(main.Card.name(value), "Plane +Mult")
        self.game.cards.append(main.CardItem(value, 40))
        self.game.air_time = 2.0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_mult, 1 + 2 * 2.0)

    def test_pillar_plus_chips_scales_proportionally_per_column_block(self):
        # Fullest Column (Pillar) has ratio 0.25, so +Chips pays round(0.25*30)
        # = +8 chips per block in the fullest column at the start of the run.
        value = main.condition_scorer_card(main.Condition.FULLEST_COLUMN,
                                           main.Scorer.CHIPS_ADD)
        self.assertEqual(main.Card.name(value), "Pillar +Chips")
        self.game.cards.append(main.CardItem(value, 40))
        for i in range(3):
            self.game.grid[(2, i)] = main.Block(2, i)
        self.game.score_chips = 0
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 8 * 3)

    def test_wrecking_ball_chips_card_pays_proportional_chips_per_break(self):
        # Fragile Breaks at ratio 0.75: a +Chips version pays int(0.75*30 + .5)
        # = +23 chips per fragile block that breaks.
        value = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS,
                                           main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.run_active = True
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game._on_fragile_broken(block)
        self.assertEqual(self.game.score_chips, 23)

    def test_flat_collision_card_is_a_prebuilt_candidate(self):
        # Building (Pipe condition, Cash) produces a generic card that is also a
        # valid pre-built shop candidate: one family, any scorer.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.CASH)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.Card.name(value), "Pipe card (Cash)")
        self.assertEqual(components.splittable_card_condition_scorer(value),
                         (main.Condition.SHAPE_PIPE, main.Scorer.CASH))
        self.assertIn(value, main.Card.NAMES)

    def test_shop_can_offer_grid_only_prebuilt_cards(self):
        # Over many rerolls the shop's card offers include derived grid cards
        # that were never in the old fixed catalog, proving pre-built
        # splittable cards can carry any scorer.
        seen = set()
        for _ in range(200):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "card":
                    seen.add(item.value)
        grid_only = [v for v in seen if v not in main.Card.ORDER]
        self.assertTrue(grid_only)

    def test_pipe_cash_card_earns_toward_the_run_award_on_matching_collision(self):
        # A Cash card doesn't pay out mid-run: it banks toward the run's
        # end-of-run cash award (paid only after a run).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.CASH)
        self.game.cards.append(main.CardItem(value, 40))
        cash = self.game.cash
        self.game.card_cash_run_gain = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.card_cash_run_gain, 15)
        self.assertEqual(self.game.cash, cash)  # nothing paid mid-run
        # A non-pipe block doesn't trigger the card.
        rect = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        self._card_fire(rect)
        self.assertEqual(self.game.card_cash_run_gain, 15)

    def test_start_cash_card_banks_toward_run_award_at_run_start(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CASH)
        self.game.cards.append(main.CardItem(value, 40))
        cash = self.game.cash
        self.game.card_cash_run_gain = 0
        self.game._apply_cards()
        self.assertEqual(self.game.card_cash_run_gain, 15)
        self.assertEqual(self.game.cash, cash)

    def test_sharp_card_triples_mult_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.score_mult, 3)

    def test_parts_card_grants_a_component_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.PARTS)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.toolbox.items.clear()
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        comps = [i for i in self.game.toolbox.items if getattr(i, "kind", None)
                 in (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)]
        self.assertEqual(len(comps), 1)

    def test_fresh_card_gives_a_free_reroll_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.free_rerolls = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.free_rerolls, 1)

    def test_picky_card_banks_a_point_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.PICKY)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.option_run_gain = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.option_run_gain, 0.5)

    def test_voyager_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.VOYAGER, main.Scorer.ORDER)
        self.assertIn(main.Scorer.VOYAGER, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.VOYAGER), "Voyager")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.VOYAGER)], 0)
        # The magnitude is the mult per PIXEL of travel, rolled around 0.01.
        self.assertAlmostEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.VOYAGER], 0.01)
        desc = main.scorer_description(main.Scorer.VOYAGER, 0.01)
        self.assertIn("traveled", desc.lower())
        self.assertIn("0.01 mult", desc)
        self.assertIn("pixel", desc.lower())
        # Voyager is also a card scorer: it builds a generic card with any
        # condition (a card that adds mult from the run's total travel).
        self.assertIn(main.Scorer.VOYAGER, components.CARD_SCORERS)
        self.assertIn(main.Scorer.VOYAGER, components.FLAT_CARD_SCORERS)
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.VOYAGER)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.generic_card_meta(value), (main.Condition.SHAPE_PIPE,
                                                          main.Scorer.VOYAGER))

    def test_voyager_magnitude_is_rolled_around_the_average_rate(self):
        # The rate rolls like every other scalar: 0.01 steps by 0.001, capped
        # at 8 steps either side and never reaching zero.
        self.assertAlmostEqual(main.magnitude_step(main.Scorer.DEFAULT_AMOUNT[
            main.Scorer.VOYAGER]), 0.001)
        self.assertAlmostEqual(main.scorer_magnitude_floor(main.Scorer.VOYAGER), 0.001)
        rolls = [main.roll_scorer_amount(main.Scorer.VOYAGER) for _ in range(200)]
        # 17 possible rates (the average +/- up to 8 steps), so a sample
        # repeats; it must still cover a spread of them rather than one value.
        self.assertGreater(len(set(rolls)), 5, "rolls should vary")
        self.assertLessEqual(len(set(rolls)), 17)
        for amount in rolls:
            self.assertGreaterEqual(amount, 0.002)
            self.assertLessEqual(amount, 0.018)
            self.assertAlmostEqual(round(amount / 0.001), amount / 0.001, places=6)
        # A piece is priced for the rate it rolled (the table price is the
        # average-rate price).
        base = main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.VOYAGER)]
        strong = main.Component.scorer_component(main.Scorer.VOYAGER, amount=0.018)
        weak = main.Component.scorer_component(main.Scorer.VOYAGER, amount=0.002)
        self.assertGreater(strong.price, base)
        self.assertLess(weak.price, base)
        # The description names the rolled rate with its deviation token.
        desc = main.scorer_description(main.Scorer.VOYAGER, 0.018)
        self.assertIn("0.018 mult", desc)
        self.assertIn("(+0.008)", desc)

    def test_voyager_block_adds_mult_per_pixel_traveled(self):
        # A Voyager block adds its own rate (0.01 mult at the average) for each
        # pixel the touching marble had already traveled this run.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 2400.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.01 * 2400)
        self.assertEqual(block.triggers_left, 0)

    def test_voyager_block_pays_a_fraction_of_a_pixel_of_travel(self):
        # The rate is per pixel, not per whole unit of distance: 55 px of
        # travel at the rolled 0.01 rate is +0.55 mult, kept as a float.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 55.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1.55)
        self.assertNotEqual(self.game.score_mult, int(self.game.score_mult))

    def test_voyager_block_counts_only_the_touching_marble(self):
        # The reward uses the marble that touched the block, not every marble.
        self.game.score_mult = 1
        self.game.run_active = True
        other = self._add_marble()
        other.distance = 8000.0  # traveled far but never touches the block
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 800.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.01 * 800)

    def test_voyager_block_gives_nothing_without_travel(self):
        # A marble that has not moved yet adds no mult, but the trigger is
        # still spent (the block shows its used state).
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 0.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_voyager_card_adds_mult_per_pixel_of_total_run_distance(self):
        # A Voyager card has no single touching marble, so it measures the
        # total distance all of the run's marbles have traveled when it fires.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.VOYAGER)
        self.game.cards.append(main.CardItem(value, 40, amount=0.01))
        self.game.score_mult = 1
        m1 = self._add_marble()
        m1.distance = 1600.0
        m2 = self._add_marble()
        m2.distance = 800.0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=m1)
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.01 * 2400)

    def test_voyager_card_uses_its_own_rolled_rate(self):
        # A card's Voyager half keeps its own magnitude, so a card rolled above
        # the average rate pays more for the same travel.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.VOYAGER)
        self.game.cards.append(main.CardItem(value, 40, amount=0.018))
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.distance = 1000.0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=marble)
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.018 * 1000)

    def test_summit_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SUMMIT, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SUMMIT, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SUMMIT), "Summit")
        self.assertAlmostEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SUMMIT], 0.75)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SUMMIT)], 0)
        self.assertIn("above the bottom row",
                      main.scorer_description(main.Scorer.SUMMIT, 0.75).lower())
        # Summit is also a card scorer: it builds a generic card with any
        # condition (the card measures the triggering block's row).
        self.assertIn(main.Scorer.SUMMIT, components.CARD_SCORERS)
        self.assertIn(main.Scorer.SUMMIT, components.FLAT_CARD_SCORERS)
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SUMMIT)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.generic_card_meta(value), (main.Condition.SHAPE_PIPE,
                                                         main.Scorer.SUMMIT))

    def test_summit_card_descriptions_name_the_measured_block(self):
        # A Summit card's description explains that it measures the row of the
        # block its condition hands it.
        collision = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                               main.Scorer.SUMMIT)
        cdesc = main.Card.description(collision).lower()
        self.assertIn("collided block", cdesc)
        self.assertIn("bottom row", cdesc)
        start = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.SUMMIT)
        sdesc = main.Card.description(start).lower()
        self.assertIn("first block", sdesc)
        self.assertIn("bottom row", sdesc)
        end = main.condition_scorer_card(main.Condition.DISTANCE,
                                         main.Scorer.SUMMIT)
        self.assertIn("last block", main.Card.description(end).lower())
        breaks = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS,
                                            main.Scorer.SUMMIT)
        self.assertIn("shattered block", main.Card.description(breaks).lower())

    def test_summit_block_adds_three_quarter_mult_per_row_above_bottom(self):
        # A Summit block at row 0 (the top row) sits GRID_HEIGHT - 1 rows
        # above the bottom row, so it adds 0.75 * (GRID_HEIGHT - 1) mult.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.SUMMIT)  # row 0 = top row
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.75 * (main.GRID_HEIGHT - 1))
        self.assertEqual(block.triggers_left, 0)

    def test_summit_block_mid_board_scales_with_row(self):
        # A block partway up adds 0.75 mult for each row above the bottom row.
        self.game.score_mult = 1
        self.game.run_active = True
        row = main.GRID_HEIGHT - 1 - 10  # ten rows above the bottom row
        block = main.Block(0, row, scorer=main.Scorer.SUMMIT, scorer_amount=0.5)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.5 * 10)

    def test_summit_block_on_bottom_row_gives_nothing(self):
        # A Summit block on the bottom row (row GRID_HEIGHT - 1) is 0 units
        # above it, so it grants no mult; the trigger is still spent.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, main.GRID_HEIGHT - 1, scorer=main.Scorer.SUMMIT)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_summit_block_fractional_mult_is_kept_as_float(self):
        # The 0.75-per-row mult stays fractional internally (nothing rounds the
        # reward); only the UI display rounds to a tenth.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, main.GRID_HEIGHT - 1 - 7, scorer=main.Scorer.SUMMIT)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.75 * 7)
        self.assertNotEqual(self.game.score_mult, int(self.game.score_mult))

    def test_summit_card_collision_uses_collided_block_row(self):
        # A Summit collision card measures the row of the block the marble
        # actually hit (a card has no row of its own).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)  # top row
        self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.75 * (main.GRID_HEIGHT - 1))

    def test_summit_card_collision_bottom_row_gives_nothing(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, main.GRID_HEIGHT - 1, shape=main.Shape.PIPE,
                          scorer=main.Scorer.NONE)  # bottom row
        self._card_fire(pipe)
        self.assertEqual(self.game.score_mult, 1)

    def test_summit_start_card_waits_for_first_contact_block(self):
        # A start-phase Summit card can't measure a row at run start (no block
        # has been hit yet), so it waits until the run's first contacted block.
        import cards
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self.game._apply_cards()  # run start: no block yet, so no Summit reward
        self.assertEqual(self.game.score_mult, 1)
        first = main.Block(0, 2, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        cards.fire_first_block_cards(self.game, first)
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.75 * ((main.GRID_HEIGHT - 1) - 2))

    def test_summit_end_card_uses_last_contact_block(self):
        # An end-phase Summit card measures the last block the marble hit
        # before finishing.
        value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_block = main.Block(
            0, main.GRID_HEIGHT - 1 - 4, scorer=main.Scorer.NONE)  # 4 rows up
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.75 * 4)

    def test_score_display_rounds_to_nearest_tenth_only(self):
        # Chips/mult/total stay fractional internally; the UI text rounds them
        # to the nearest tenth (whole values stay plain).
        import ui
        self.assertEqual(ui._fmt_tenth(38.5), "38.5")
        self.assertEqual(ui._fmt_tenth(40.0), "40")
        self.assertEqual(ui._fmt_tenth(38.53), "38.5")
        self.assertEqual(ui._fmt_tenth(3), "3")
        self.assertEqual(ui._fmt_tenth(7.0), "7")
        self.assertEqual(ui._fmt_tenth(0.26), "0.3")

    def test_airball_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.AIRBALL, main.Scorer.ORDER)
        self.assertIn(main.Scorer.AIRBALL, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.AIRBALL), "Airball")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.AIRBALL], 8)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.AIRBALL)], 0)
        self.assertIn("airborne", main.scorer_description(main.Scorer.AIRBALL, 8).lower())
        # Airball is also a card scorer (it builds a generic card with any
        # condition; the card rewards the touching marble's air streak).
        self.assertIn(main.Scorer.AIRBALL, components.CARD_SCORERS)
        self.assertIn(main.Scorer.AIRBALL, components.FLAT_CARD_SCORERS)
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.AIRBALL)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.generic_card_meta(value), (main.Condition.SHAPE_PIPE,
                                                         main.Scorer.AIRBALL))
        # A splittable card's icon is its CONDITION's symbol (not the scorer's),
        # so this Pipe x Airball generic card carries the Pipe condition glyph.
        self.assertEqual(main.Card.GLYPHS.get(value),
                         components.condition_glyph(main.Condition.SHAPE_PIPE))
        # ... and its face color is the scorer's own color.
        self.assertEqual(main.Card.COLORS[value], main.Scorer.color(main.Scorer.AIRBALL))

    def test_airball_block_adds_eight_mult_per_air_second(self):
        # An Airball block rewards the touching marble's airborne streak: 2.5s
        # of air right before the touch -> +8 * 2.5 = +20 mult.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL, scorer_amount=8)
        marble = self._add_marble()
        marble.air_streak = 2.5
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 2.5)
        self.assertEqual(block.triggers_left, 0)

    def test_airball_block_counts_only_the_touching_marble(self):
        # The reward uses the marble that touched the block, not every marble.
        self.game.score_mult = 1
        self.game.run_active = True
        other = self._add_marble()
        other.air_streak = 50.0  # lots of air, but never touches this block
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL)
        marble = self._add_marble()
        marble.air_streak = 0.5
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 0.5)

    def test_airball_block_gives_nothing_when_marble_had_no_air(self):
        # A marble that just touched another block has a 0 air streak, so the
        # Airball block grants nothing but still spends its trigger.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL)
        marble = self._add_marble()
        marble.air_streak = 0.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)

    def test_airball_block_fractional_mult_is_kept_as_float(self):
        # Fractional air seconds count: 0.6s -> 8 * 0.6 = 4.8 mult, kept as a
        # float (only the UI rounds it to a tenth).
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL)
        marble = self._add_marble()
        marble.air_streak = 0.6
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 0.6)
        self.assertNotEqual(self.game.score_mult, int(self.game.score_mult))

    def test_airball_air_streak_accumulates_while_marble_airborne(self):
        # A marble with nothing under it stays airborne, so its air streak
        # grows every frame it has no block contact.
        self.game.marbles = [main.Marble(360, 120)]
        self.game.run_active = True
        for _ in range(30):
            self.game.update()
        self.assertGreater(self.game.marbles[0].air_streak, 0.2)

    def test_airball_air_streak_resets_while_marble_rests_on_block(self):
        # A marble resting on a floor block is in contact, so its air streak is
        # zeroed (an Airball touch right after it would reward 0 air).
        floor = main.Block(5, 8)
        self.game.grid[(5, 8)] = floor
        marble = main.Marble(floor.rect.centerx, floor.rect.top - main.MARBLE_RADIUS - 1)
        self.game.marbles = [marble]
        self.game.run_active = True
        for _ in range(20):
            self.game.update()
        self.assertLess(marble.air_streak, 0.2)

    def test_airball_card_collision_uses_touching_marble_air(self):
        # A Pipe x Airball card pays +8 mult per second of the touching
        # marble's air streak before it hit the matching pipe.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.air_streak = 1.5
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=marble)
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 1.5)

    def test_airball_card_collision_with_no_air_grants_nothing(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)  # fresh marble with no air streak
        self.assertEqual(self.game.score_mult, 1)

    def test_airball_start_card_fires_on_first_contact_with_air(self):
        # A start-condition Airball card waits for the run's first contacted
        # block and rewards that marble's air streak before the touch.
        import cards
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self.game._apply_cards()  # run start: no block yet -> no reward
        self.assertEqual(self.game.score_mult, 1)
        marble = self._add_marble()
        marble.air_streak = 2.0
        first = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        cards.fire_first_block_cards(self.game, first, marble)
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 2.0)

    def test_airball_end_card_uses_last_contact_air(self):
        # An end-condition Airball card rewards the air streak the marble had
        # before its last block contact before finishing.
        value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_block = main.Block(0, 0, scorer=main.Scorer.NONE)
        self.game._last_contact_air = 2.5
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 2.5)

    def test_airball_fragile_card_uses_broken_block_touch_air(self):
        # A Fragile Breaks x Airball card rewards the air streak the marble had
        # before it first touched the fragile block that later broke.
        value = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        block.touch_air_streak = 3.0
        self.game._on_fragile_broken(block)
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 3.0)

    def test_satanic_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SATANIC, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SATANIC, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SATANIC), "Satanic")
        self.assertAlmostEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SATANIC], 6.66)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SATANIC)], 0)
        self.assertIn("destroyed", main.scorer_description(main.Scorer.SATANIC).lower())
        # A Satanic CARD says it is destroyed after one run (the block's own
        # description is about a marble leaving it).
        card_desc = main.Card.description(
            main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                       main.Scorer.SATANIC))
        self.assertIn("x6.66 mult", card_desc)
        self.assertIn("destroyed after one run", card_desc)
        # Satanic is also a card scorer (its card is destroyed after a run).
        self.assertIn(main.Scorer.SATANIC, components.CARD_SCORERS)
        self.assertIn(main.Scorer.SATANIC, components.FLAT_CARD_SCORERS)
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.generic_card_meta(value), (main.Condition.SHAPE_PIPE,
                                                          main.Scorer.SATANIC))

    def test_satanic_block_multiplies_mult_by_6_66_when_touched(self):
        block = main.Block(0, 0, scorer=main.Scorer.SATANIC)
        self.game.score_mult = 2
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 2 * 6.66)
        self.assertEqual(block.triggers_left, 0)

    def test_satanic_block_is_removed_after_marble_touches_and_leaves(self):
        # A marble that touched the block last frame and is no longer touching
        # flags it; the game then removes the block from the board for good.
        block = main.Block(0, 0, scorer=main.Scorer.SATANIC, origin=(0, 0))
        block.rect.topleft = (0, 0)
        marble = main.Marble(200, 200)  # far from the block this frame
        marble.collisions_this_tick = [block]  # ...but it touched last frame
        marble.physics.update(marble, main.DT, [block])
        self.assertTrue(getattr(block, "satanic_leave", False))
        # The game removes the flagged block from the grid on its next update.
        self.game.grid[(1, 1)] = block
        self.game.run_active = True
        self.game.marbles = []
        self.game.update()
        self.assertNotIn((1, 1), self.game.grid)

    def test_satanic_card_multiplies_mult_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult, 6.66)

    def test_satanic_card_destroyed_on_continue(self):
        # A run destroys an owned Satanic card (a one-run deal);
        # non-Satanic cards survive.
        satanic = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        cash = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.CASH)
        self.game.cards = [main.CardItem(satanic, 40), main.CardItem(cash, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        values = [card.value for card in self.game.cards]
        self.assertNotIn(satanic, values)
        self.assertIn(cash, values)

    def test_satanic_card_survives_retry(self):
        # Retrying the run discards it, so the Satanic card is kept.
        satanic = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        self.game.cards = [main.CardItem(satanic, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual([card.value for card in self.game.cards], [satanic])

    def test_same_block_xmult_triggers_multiply(self):
        # A Sharp block (x3 = +2 xMult) with trigger limit 2, fired twice,
        # applies its factor on both triggers (1 -> 3 -> 9): xMult always
        # multiplies (Game._apply_xmult), so an item's own triggers compound.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.SHARP, trigger_limit=2)
        self.assertEqual(block.triggers_left, 2)
        for _ in range(2):
            self.game.marbles = []
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(block.triggers_left, 0)
        self.assertAlmostEqual(self.game.score_mult, 9)

    def test_different_blocks_xmult_apply_separately(self):
        # Two different Sharp blocks each triple on their own first trigger,
        # so the multiplier compounds across them (1 -> 3 -> 9).
        self.game.score_mult = 1
        self.game.run_active = True
        for _ in range(2):
            self.game.marbles = []
            block = main.Block(0, 0, scorer=main.Scorer.SHARP)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 9)

    def test_sharp_then_mult_then_sharp_sequence(self):
        # A Sharp block, then a +Mult block, then a (different) Sharp block:
        # triple, add 4 to the multiplier, then triple (1 -> 3 -> 7 -> 21).
        self.game.score_mult = 1
        self.game.run_active = True

        def fire(block):
            self.game.marbles = []
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])

        fire(main.Block(0, 0, scorer=main.Scorer.SHARP))
        self.assertAlmostEqual(self.game.score_mult, 3)
        fire(main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=4))
        self.assertAlmostEqual(self.game.score_mult, 7)
        fire(main.Block(0, 0, scorer=main.Scorer.SHARP))
        self.assertAlmostEqual(self.game.score_mult, 21)

    def test_same_card_xmult_triggers_multiply(self):
        # A single Sharp card that fires on two pipe hits multiplies twice
        # (1 -> 3 -> 9); xMult always multiplies, never adds (Game._apply_xmult).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        for _ in range(2):
            pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
            self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult, 9)

    def test_collision_xmult_card_compounds_per_collision(self):
        # A Slope xMult card hitting 2 slopes gives 1.25 * 1.25 = 1.5625: every
        # collision applies the card's own factor again, individually and
        # exponentially.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.assertIn("x1.25", main.Card.description(value))
        self.game.score_mult = 1

        for slopes in range(1, 4):
            self._card_fire(main.Block(slopes, 5, shape=main.Shape.SLOPE,
                                       scorer=main.Scorer.NONE))
            self.assertAlmostEqual(self.game.score_mult, 1.25 ** slopes)

        self.assertAlmostEqual(self.game.score_mult, 1.5625 * 1.25)

    def test_collision_card_fires_once_per_block_trigger(self):
        # A collision card rides on the block's triggers: a slope with a limit
        # of 3 feeds the card three times and then stops.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        slope = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE,
                           trigger_limit=3)

        for _ in range(4):
            self._card_fire(slope)

        self.assertEqual(slope.triggers_left, 0)
        self.assertAlmostEqual(self.game.score_mult, 1.25 ** 3)
        self.assertNotAlmostEqual(self.game.score_mult, 1.25 ** 4)

    def test_collision_card_needs_a_trigger_left_on_the_block(self):
        # A block that has already spent its triggers (its used-up red state)
        # no longer feeds collision cards.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        spent = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE)
        spent.triggers_left = 0

        self._card_fire(spent)

        self.assertEqual(self.game.score_mult, 1)

    def test_collision_cards_ignore_role_blocks(self):
        # Start/Finish blocks are not scoring blocks and never spend a trigger,
        # so a collision card must not fire on them at all — otherwise a
        # slope-shaped Start block would feed a Slope xMult card on every touch.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        start = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.START)
        finish = main.Block(1, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.FINISH)

        for _ in range(3):
            self._card_fire(start)
            self._card_fire(finish)

        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(start.triggers_left, 1)   # never spent
        self.assertEqual(finish.triggers_left, 1)

    def test_collision_cards_ignore_a_scorerless_portal(self):
        # A Portal with no scorer is exempt from the trigger behaviour (its
        # pass-through never spends a trigger), so it would feed a card on
        # every one of its travels in a run; collision cards refuse it. A
        # portal WITH a scorer spends its trigger as usual, so it fires once.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        free_portal = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE,
                                 effect=main.Effect.PORTAL, portal_number=1)

        for _ in range(3):
            self._card_fire(free_portal)

        self.assertEqual(self.game.score_mult, 1)

        scoring_portal = main.Block(1, 5, shape=main.Shape.SLOPE,
                                    scorer=main.Scorer.CHIPS_ADD, scorer_amount=10,
                                    effect=main.Effect.PORTAL, portal_number=2)
        self._card_fire(scoring_portal)
        self.assertAlmostEqual(self.game.score_mult, 1.25)
        self._card_fire(scoring_portal)   # its trigger is spent now
        self.assertAlmostEqual(self.game.score_mult, 1.25)

    def test_xmult_rewards_always_multiply(self):
        # The per-item "later triggers only add" rule is gone: _apply_xmult
        # multiplies, returns the factor (the particle's figure), and no
        # priming state is left to get out of step with a run.
        self.game.score_mult = 2

        self.assertEqual(self.game._apply_xmult(1.25), 1.25)

        self.assertAlmostEqual(self.game.score_mult, 2.5)
        self.assertFalse(hasattr(self.game, "_xmult_primed"))

    def test_xmult_collision_card_particles_are_red(self):
        # xMult rewards always multiply now, so their particle is always RED
        # (the removed add path was the only BLUE one).
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1

        self._card_fire(main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE))

        self.assertEqual(self.game.score_particles[-1].color, main.RED)

    def test_end_flat_card_fires_at_run_end(self):
        # A Distance x Cash card banks toward the run award once the run ends;
        # a Distance x Fresh card grants a free reroll. The run has to have
        # travelled, or the Distance condition never happened.
        cash_value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.CASH)
        fresh_value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(cash_value, 40))
        self.game.cards.append(main.CardItem(fresh_value, 40))
        self._add_marble().distance = 4000.0
        cash = self.game.cash
        self.game.card_cash_run_gain = 0
        self.game.free_rerolls = 0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.card_cash_run_gain, 15)
        self.assertEqual(self.game.cash, cash)  # not paid until the run award
        self.assertEqual(self.game.free_rerolls, 1)

    # --- Flat cards honour their condition's gate -------------------------

    def test_flat_start_card_respects_its_conditions_gate(self):
        # A flat card fires one block-style trigger, but only when its condition
        # actually happened: a Ripped Card (Parts) pays nothing on a board with
        # more than 5 blocks, and pays again once the board is small enough.
        value = main.condition_scorer_card(main.Condition.FEW_BLOCKS,
                                           main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        for x in range(6):  # 6 blocks: the Ripped Card condition fails
            self.game.grid[(x, 0)] = main.Block(x, 0, scorer=main.Scorer.NONE)
        self.game.free_rerolls = 0
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 0)

        # Shrink the board to 5 blocks: the condition holds and the card pays.
        self.game.grid.pop((5, 0))
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 1)

    def test_flat_start_card_respects_the_cozy_board_gate(self):
        # Cozy holds while the board has 10 or fewer unlocked units.
        value = main.condition_scorer_card(main.Condition.COZY, main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.free_rerolls = 0
        self.game.unlocked_cells = {(x, y) for x in range(11) for y in range(1)}
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 0)  # 11 units: Cozy is broken

        self.game.unlocked_cells = {(x, y) for x in range(10) for y in range(1)}
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 1)  # 10 units: Cozy holds

    def test_flat_end_card_does_not_fire_when_the_run_measured_nothing(self):
        # A run that never travelled has not satisfied the Distance condition,
        # so its flat card pays nothing (the magnitude version scales to zero).
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.free_rerolls = 0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.free_rerolls, 0)

        self._add_marble().distance = 4000.0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.free_rerolls, 1)

    def test_flat_start_block_payoff_card_respects_the_gate(self):
        # A block-relative start card waits for the run's first block, and is
        # still refused when its condition's gate is not met: a Ripped Card
        # (Powerline) pays nothing on a crowded board, and pays once the board
        # is small enough.
        import cards
        value = main.condition_scorer_card(main.Condition.FEW_BLOCKS,
                                           main.Scorer.POWERLINE)
        self.game.cards.append(main.CardItem(value, 40))
        row = 3
        for x in range(3):
            self.game.grid[(x, row)] = main.Block(x, row, scorer=main.Scorer.NONE)
        first = self.game.grid[(0, row)]
        for x in range(3, 6):  # 6 blocks total: the condition fails
            self.game.grid[(x, row)] = main.Block(x, row, scorer=main.Scorer.NONE)
        self.game.score_chips = 0
        cards.fire_first_block_cards(self.game, first)
        self.assertEqual(self.game.score_chips, 0)

        self.game.grid.pop((5, row))  # 5 blocks: the card fires
        cards.fire_first_block_cards(self.game, first)
        self.assertEqual(self.game.score_chips,
                         main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE] * 5)

    def test_cash_card_reward_folds_into_run_award_and_retry_discards(self):
        # Cash earned by Cash cards is added at _award_cash (part of the run's
        # end award), so retrying the run undoes it — it only sticks after a run.
        self.game.score_total = 10000
        self.game.required_score = 1
        self.game.card_cash_run_gain = 9
        cash0 = self.game.cash
        self.game._award_cash()
        self.assertEqual(self.game.card_cash_run_gain, 0)
        self.assertGreaterEqual(self.game.last_run_cash_gained, 9)
        self.assertGreater(self.game.cash, cash0)
        # Retrying the run rolls the whole award (including the card cash) back.
        # Only a real retry does: the run has to be finished and waiting for
        # the player's RETRY/CONTINUE choice.
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.cash, cash0)

    def test_resource_display_shows_for_resource_scorer_card(self):
        # Owning a card built with a point-banked scorer shows its line.
        self.game.toolbox.items.clear()
        self.game.cards.clear()
        self.assertEqual(self.game._resource_display(), [])
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.IDEAS)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.idea_run_gain = 1
        self.assertEqual(self.game._resource_display(), [(1, "action")])

    def test_quick_card_pays_the_speed_of_the_next_block_hit(self):
        # A Pipe x Quick card arms when the pipe is hit; the marble's NEXT
        # fresh block contact pays chips from that block's impact speed.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = self._card_fire(pipe)
        # Arming only, no payout yet.
        self.assertIn(self.game.cards[0], self.game.armed_quick)
        self.assertEqual(self.game.score_chips, 0)
        # Hitting the next block (a rect) resolves using its impact speed.
        marble.recent_speed = 240.0
        rect = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        self._card_fire(rect, marble)
        self.assertEqual(self.game.armed_quick, set())
        self.assertEqual(self.game.score_chips, int(240.0 * main.QUICK_SCALE))

    def test_quick_card_resolves_an_armed_start_quick_on_first_hit(self):
        # A Start x Quick card arms at run start and pays on the first block hit.
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.armed_quick = set()
        self.game._apply_cards()
        self.assertIn(self.game.cards[0], self.game.armed_quick)
        marble = self._add_marble()
        marble.recent_speed = 200.0
        rect = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        self._card_fire(rect, marble)
        self.assertEqual(self.game.score_chips, int(200.0 * main.QUICK_SCALE))

    def test_shape_and_effect_cards_exist_for_every_shape_and_effect(self):
        # Every shape and effect collision condition has a magnitude card for
        # each unit scorer (+Chips / +Mult / xMult), decomposing back into the
        # exact (condition, scorer) pair it was built from.
        for scorer, suffix in ((main.Scorer.CHIPS_ADD, "+Chips"),
                               (main.Scorer.MULT_ADD, "+Mult"),
                               (main.Scorer.MULT_MUL, "xMult")):
            for shape in main.Shape.ORDER:
                value = _shape_card_value(shape, scorer)
                self.assertEqual(main.Card.name(value),
                                 f"{main.Shape.name(shape)} {suffix}")
                self.assertIn(main.Shape.name(shape), main.Card.description(value))
                self.assertEqual(
                    components.splittable_card_condition_scorer(value),
                    (main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape),
                     scorer))
            for effect in main.Effect.ORDER:
                value = _effect_card_value(effect, scorer)
                self.assertEqual(main.Card.name(value),
                                 f"{main.Effect.name(effect)} {suffix}")
                self.assertEqual(
                    components.splittable_card_condition_scorer(value),
                    (main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect),
                     scorer))

    def test_magnitude_card_prices_scale_with_scorer_and_condition(self):
        # A magnitude card's price is its condition + scorer price, so +Chips
        # is cheapest and xMult most expensive for one condition, while the
        # condition price runs INVERSELY to the component it matches.
        pipe = main.Shape.PIPE
        pipe_chips = main.Card.PRICES[_shape_card_value(pipe, main.Scorer.CHIPS_ADD)]
        pipe_mult = main.Card.PRICES[_shape_card_value(pipe, main.Scorer.MULT_ADD)]
        pipe_xmult = main.Card.PRICES[_shape_card_value(pipe, main.Scorer.MULT_MUL)]
        self.assertLess(pipe_chips, pipe_mult)
        self.assertLess(pipe_mult, pipe_xmult)
        # A pricey effect (Portal, $31 > Bouncy, $28) has the CHEAPER condition,
        # so its magnitude card is cheaper than the cheaper effect's card.
        bouncy = main.Card.PRICES[_effect_card_value(main.Effect.BOUNCY, main.Scorer.MULT_ADD)]
        portal = main.Card.PRICES[_effect_card_value(main.Effect.PORTAL, main.Scorer.MULT_ADD)]
        self.assertGreater(bouncy, portal)
        # The same inversion holds for shapes: Circle ($8) is cheaper than Pipe
        # Bend ($12), so its condition - and its card - costs more.
        circle = main.Card.PRICES[_shape_card_value(main.Shape.CIRCLE, main.Scorer.MULT_MUL)]
        pipe_bend = main.Card.PRICES[_shape_card_value(main.Shape.PIPE_BEND, main.Scorer.MULT_MUL)]
        self.assertGreater(circle, pipe_bend)

    def test_condition_prices_run_inversely_to_their_component(self):
        # A shape/effect collision condition costs the inverse of the component
        # it matches: the cheapest block's condition is the dearest, and the
        # pricey Splitter's condition is the cheapest — never free.
        def shape_cond(shape):
            return main.COMPONENT_PRICES[
                (main.Component.CONDITION,
                 main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape))]

        def effect_cond(effect):
            return main.COMPONENT_PRICES[
                (main.Component.CONDITION,
                 main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect))]

        rect_price = main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.RECT)]
        splitter_price = main.COMPONENT_PRICES[(main.Component.EFFECT,
                                                main.Effect.SPLITTER)]
        self.assertGreater(shape_cond(main.Shape.RECT), rect_price)
        self.assertLess(effect_cond(main.Effect.SPLITTER), splitter_price)
        self.assertLess(effect_cond(main.Effect.SPLITTER),
                        effect_cond(main.Effect.BOUNCY))
        self.assertGreater(shape_cond(main.Shape.PEG),
                           shape_cond(main.Shape.LINE))
        # The relation holds across the whole table, with a floor under it.
        pairs = [(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)],
                  shape_cond(shape)) for shape in main.Shape.ORDER]
        pairs += [(main.COMPONENT_PRICES[(main.Component.EFFECT, effect)],
                   effect_cond(effect)) for effect in main.Effect.ORDER]
        for price, cond_price in pairs:
            self.assertGreaterEqual(cond_price, components.CONDITION_PRICE_FLOOR)
            for other_price, other_cond_price in pairs:
                if price < other_price:
                    self.assertGreaterEqual(cond_price, other_cond_price)

    def test_shape_card_grants_mult_on_matching_collision(self):
        # A "Pipe card" grants +4 mult when the marble collides with a pipe.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 4)

    def test_effect_card_grants_mult_on_matching_collision(self):
        # A "Bouncy card" grants +4 mult when the marble collides with a
        # bouncy block (the effect can be one of several on the block).
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_MULT), 30))
        block = main.Block(1, 1, shape=main.Shape.RECT, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 4)

    def test_chips_card_grants_30_chips_on_matching_collision(self):
        # The +chips version of the Pipe card grants +30 chips per collision.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_CHIPS), 12))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_chips
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, before + 30)
        self.assertEqual(self.game.score_mult, 1)  # no mult change

    def test_xmult_card_multiplies_mult_on_matching_collision(self):
        # The xMult version of the Bouncy card multiplies mult by 1.25.
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_XMULT), 40))
        block = main.Block(1, 1, shape=main.Shape.RECT, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        self.game.score_mult = 4
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 5)

    def test_shape_card_ignores_non_matching_shape(self):
        # A Pipe card does nothing when the marble hits a non-pipe block.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before)

    def test_none_effect_card_fires_on_plain_block(self):
        # A "None card" (effect) grants +4 mult when hitting a block with no
        # effect.
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.NONE, components.Card.SCORE_MULT), 7))
        block = main.Block(1, 1, shape=main.Shape.RECT, effects=[main.Effect.NONE],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 4)

    def test_collision_card_fires_once_per_collision_not_every_frame(self):
        # A block already in contact (present in last tick too) is not a fresh
        # collision, so the card does not stack +4 every frame.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before)

    def test_multiple_matching_cards_stack_on_one_collision(self):
        # A bouncy pipe block triggers both the Pipe card and the Bouncy card.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_MULT), 30))
        block = main.Block(1, 1, shape=main.Shape.PIPE, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 8)

    def test_blueprint_copies_a_shape_card(self):
        # A Blueprint to the right of a Pipe card copies it: colliding with a
        # pipe block triggers both the card and its Blueprint.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 70))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 8)

    def test_shape_effect_cards_draw_their_shape_or_effect_icon(self):
        # Shape/effect cards render the icon of the shape/effect they are
        # based on (instead of a letter glyph) while keeping the card's
        # colored background.
        for value in (_shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT),
                      _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_MULT)):
            surf = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
            main.ui.draw_card(surf, main.CardItem(value, 18), surf.get_rect())
            bg = main.Card.COLORS[value]
            # A spot left of the centered icon keeps the card's background.
            self.assertEqual(surf.get_at((5, surf.get_height() // 2))[:3], bg)
            # The shape/effect icon is drawn somewhere in the card's interior.
            self.assertTrue(any(
                surf.get_at((x, y))[:3] != bg
                for x in range(8, surf.get_width() - 8)
                for y in range(8, surf.get_height() - 8)))

    def test_buying_card_adds_to_card_area_not_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        # The ERR 404 card converts to a random card when bought, so it isn't
        # the same object — skip it and buy a normal card instead.
        card = next(item for item in self.game.shop.items
                    if item.kind == "card" and item.value != main.Card.ERR_404)
        before_cash = self.game.cash
        self.game._buy_shop_item(card)
        self.assertIn(card, self.game.cards)
        self.assertNotIn(card, self.game.toolbox.items)
        self.assertEqual(self.game.cash, before_cash - card.price)

    def test_card_area_caps_at_five(self):
        self.game.cash = 100000
        # Own Showman so duplicate Jokers can be bought; the card area still
        # caps at MAX_CARDS.
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 100))
        for _ in range(main.MAX_CARDS + 2):
            self.game._buy_shop_item(main.CardItem(main.Card.JOKER, 20))
        self.assertEqual(len(self.game.cards), main.MAX_CARDS)  # Showman + 4 Jokers
        self.assertTrue(self.game.shop_message)

    def test_cannot_buy_duplicate_card_without_showman(self):
        # You can't buy a second copy of a card you already own unless you own
        # the Showman card.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 40))
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.JOKER, 40))
        self.assertEqual(len(self.game.cards), 1)  # no duplicate added
        self.assertEqual(self.game.cash, 1000)     # not charged
        self.assertEqual(self.game.shop_message, "Already own this card")

    def test_can_buy_duplicate_card_with_showman(self):
        # Owning the Showman card lets you buy duplicates of any card.
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 100))
        self.game.cards.append(main.CardItem(main.Card.JOKER, 40))
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.JOKER, 40))
        self.assertEqual(len(self.game.cards), 3)  # Showman + 2 Jokers
        self.assertEqual(self.game.cash, 1000 - 40)

    def test_the_shop_skips_cards_the_player_already_owns(self):
        # An offer the player cannot buy is a wasted slot, and a card they own
        # should not come back around refresh after refresh: the card slots skip
        # the cards the player already owns.
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.assertEqual(self.game.shop.owned_cards(), {main.Card.GARDEN})
        for _ in range(200):
            self.game.shop.refresh()
            offered = [item for item in self.game.shop.items
                       if item.kind == "card"]
            self.assertEqual(len(offered), 2)  # both slots still fill
            self.assertNotIn(main.Card.GARDEN, {item.value for item in offered})

    def test_showman_lets_owned_cards_back_into_the_shop(self):
        # The Showman card is exactly what allows more than one copy, so with it
        # nothing is filtered: a card the player already owns can be offered
        # again (and bought — see test_can_buy_duplicate_card_with_showman).
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 48))
        self.assertEqual(self.game.shop.owned_cards(), set())
        with mock.patch("main.random_card_option_value",
                        return_value=main.Card.GARDEN):
            self.game.shop.refresh()
        self.assertIn(main.Card.GARDEN,
                      {item.value for item in self.game.shop.items
                       if item.kind == "card"})
        # A Showman the run's trial has disabled cannot lift the rule (the same
        # rule the buy path follows): the owned cards are filtered out again.
        self.game.disabled_card = self.game.cards[1]
        self.assertEqual(self.game.shop.owned_cards(),
                         {main.Card.GARDEN, main.Card.SHOWMAN})
        self.game.disabled_card = None

    def test_a_granted_card_is_not_one_the_player_already_owns(self):
        # The Ideas conversion's random card follows the same rule as the shop:
        # a second copy is the Showman card's perk, so the grant skips the cards
        # the player already has.
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        with mock.patch("main.prebuilt_card_pool",
                        return_value=[main.Card.GARDEN, main.Card.COUPON]):
            self.assertTrue(self.game._grant_random_card())
        self.assertEqual(self.game.cards[-1].value, main.Card.COUPON)

    # --- CRT screen filter (F2) -----------------------------------------

    def test_the_crt_filter_bends_darkens_and_scanlines_the_frame(self):
        # A flat frame makes the filter's own marks easy to read: the glass
        # curves the picture, the scanlines thin every other row, and the
        # vignette dims the sides and corners.
        width, height = main.SCREEN_WIDTH, main.SCREEN_HEIGHT
        surface = pygame.Surface((width, height))
        surface.fill((200, 200, 200))
        main.crt.apply(surface)
        middle = (width // 2, height // 2)
        # The middle keeps its colour, but on only one of two adjacent rows: the
        # other is a scanline gap.
        rows = [surface.get_at((middle[0], middle[1] + step))[0]
                for step in (0, 1)]
        self.assertGreater(max(rows), 190)
        self.assertLess(min(rows), max(rows) - 20)
        # The screen stays FILLED with the picture: curving the glass crops the
        # picture's own outer part away instead of framing it in black, so not
        # one pixel of the whole frame — corners and edges included — is dark.
        pixels = pygame.surfarray.array3d(surface)
        self.assertGreater(int(pixels.min()), 0)
        # The corners and the top/bottom edges are dimmer than the middle (the
        # vignette), but still clearly lit.
        for point in ((2, 2), (width - 3, 2), (2, height - 3),
                      (width // 2, 1), (width // 2, height - 2)):
            lit = max(surface.get_at((point[0], point[1] + step))[0]
                      for step in (0, 1))
            self.assertGreater(lit, 60, point)
            self.assertLess(lit, max(rows), point)
        # ...and the sides are dimmed the same way.
        side = max(surface.get_at((width - 30, middle[1] + step))[0]
                   for step in (0, 1))
        self.assertGreater(side, 0)
        self.assertLess(side, max(rows))
        # Running it again (a second frame) is harmless.
        main.crt.apply(surface)

    def test_the_crt_filter_magnifies_the_picture_to_fill_the_screen(self):
        # Sampling inwards along the tube's curve magnifies the picture, so
        # content close to an edge is pushed further out — past the edge, where
        # the curve crops it away — rather than pulled inwards and shrunk.
        width, height = main.SCREEN_WIDTH, main.SCREEN_HEIGHT
        surface = pygame.Surface((width, height))
        surface.fill((40, 40, 40))
        surface.fill(main.WHITE, pygame.Rect(0, 30, width, 3))
        main.crt.apply(surface)
        bright = [y for y in range(60)
                  if surface.get_at((width // 2, y))[:3][0] > 150]
        self.assertTrue(bright)
        # The line started at row 30 and has been pulled up the screen.
        self.assertLess(max(bright), 30)
        # Its mirror image near the bottom is pulled down the same way.
        surface.fill((40, 40, 40))
        surface.fill(main.WHITE, pygame.Rect(0, height - 33, width, 3))
        main.crt.apply(surface)
        bright = [y for y in range(height - 60, height)
                  if surface.get_at((width // 2, y))[:3][0] > 150]
        self.assertTrue(bright)
        self.assertGreater(min(bright), height - 33)

    def test_f2_toggles_the_crt_filter_and_remembers_it(self):
        # F2 flips the filter on every screen and the choice is stored with the
        # profile's other data, so it survives a relaunch.
        old_path, old_flag = metagame.FILE_PATH, self.game.crt_filter
        metagame.FILE_PATH = os.path.join(tempfile.mkdtemp(), "metagame.json")
        metagame.reset()
        try:
            self._press(pygame.K_F2)
            self.assertNotEqual(self.game.crt_filter, old_flag)
            self.assertEqual(metagame.crt_filter(), self.game.crt_filter)
            self.assertIn("CRT filter", self.game.shop_message)
            # Persisted: a fresh load of the same file agrees.
            metagame.reset()
            self.assertEqual(metagame.crt_filter(), self.game.crt_filter)
            self._press(pygame.K_F2)
            self.assertEqual(self.game.crt_filter, old_flag)
            metagame.reset()
            self.assertEqual(metagame.crt_filter(), old_flag)
        finally:
            metagame.FILE_PATH = old_path
            metagame.reset()
            self.game.crt_filter = old_flag

    def test_present_filters_the_frame_only_while_it_is_on(self):
        # The filter is the last thing done to a finished frame, and only while
        # it is switched on; the finished frame is then blitted to the window in
        # one go, so the window never shows a half-filtered (or unfiltered)
        # frame — that used to make the picture strobe.
        old_flag = self.game.crt_filter
        frame, display = self.game.screen, self.game.display
        try:
            # The game draws off-screen: the frame buffer is not the window.
            self.assertIsNot(frame, display)
            self.assertIs(display, pygame.display.get_surface())
            self.assertEqual(frame.get_size(),
                             (main.SCREEN_WIDTH, main.SCREEN_HEIGHT))
            with mock.patch("main.crt.apply") as apply, \
                    mock.patch("main.pygame.display.flip") as flip:
                self.game.crt_filter = True
                self.game._present()
                apply.assert_called_once_with(frame)
                self.assertTrue(flip.called)
                apply.reset_mock()
                self.game.crt_filter = False
                self.game._present()
                apply.assert_not_called()
                self.assertTrue(flip.called)
            # What the window shows is the FINISHED frame: with the filter off
            # it is the frame as drawn, and with it on it is the filtered one
            # (not the unfiltered one that was just drawn over).
            self.game.crt_filter = False
            frame.fill((10, 20, 30))
            self.game._present()
            self.assertEqual(display.get_at((5, 5))[:3], (10, 20, 30))
            self.game.crt_filter = True
            with mock.patch("main.crt.apply",
                            side_effect=lambda surface: surface.fill((0, 200, 0))):
                self.game._present()
            self.assertEqual(display.get_at((5, 5))[:3], (0, 200, 0))
        finally:
            self.game.crt_filter = old_flag

    def test_drawing_a_screen_does_not_present_it(self):
        # Presenting is _present's job ALONE (see run): a screen's draw function
        # that flipped the window itself would show its unfinished, unfiltered
        # frame for a moment before the filtered one, which is the flicker.
        old_title = self.game.title_screen
        try:
            with mock.patch("main.pygame.display.flip") as flip:
                self.game.title_screen = False
                main.ui.draw(self.game)
                flip.assert_not_called()
                self.game.title_screen = True
                main.ui.draw(self.game)
                flip.assert_not_called()
        finally:
            self.game.title_screen = old_title
        # ...and no screen in ui presents at all (the ones that used to be able
        # to are the menu screens).
        self.assertNotIn("pygame.display.flip", inspect.getsource(main.ui))

    def test_shop_card_slots_combine_conditions_and_unsplittables_equally(self):
        # Each card slot draws equally from a combined pool of conditions and
        # the indivisible whole cards; a condition draw gets a random scorer
        # attached, becoming a composed (condition x scorer) card offer.
        draws = [main.random_card_option_value() for _ in range(5000)]
        whole = [v for v in draws if v in main.Card.ORDER]
        composed = [v for v in draws if v not in whole]
        # The pool is the conditions plus the indivisible whole cards, drawn
        # uniformly. The Few Blocks condition also shares ERR 404's id 9, and
        # that entry resolves to the whole card, so one extra whole-card draw
        # hides in the condition entries.
        expected = ((len(main.Card.ORDER) + 1)
                    / (len(components.CONDITION_ORDER) + len(main.Card.ORDER)))
        self.assertAlmostEqual(len(whole) / len(draws), expected, delta=0.03)
        self.assertTrue(composed)  # conditions dominate the pool
        # Every composed draw attached a scorer: it is exactly the composed
        # card for its (condition, scorer) halves.
        for v in composed:
            condition, scorer = main.splittable_card_condition_scorer(v)
            self.assertEqual(v, main.condition_scorer_card(condition, scorer))

    def test_shop_can_offer_unsplittable_whole_cards(self):
        # The indivisible whole cards (the Card.ORDER catalog, incl. Garden /
        # Rigged Casino / Conquistador) are in the card slots' combined pool,
        # so they appear in the shop sometimes.
        seen = set()
        for _ in range(300):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "card":
                    seen.add(item.value)
        self.assertTrue(seen & set(main.Card.ORDER))
        self.assertTrue(seen & {main.Card.GARDEN, main.Card.RIGGED_CASINO,
                                main.Card.CONQUISTADOR})

    def test_action_data_lives_in_components(self):
        # Every action has a name, price, glyph, colors, and v1/v2 text.
        self.assertEqual(main.Action.name(main.Action.DEATH), "Death")
        self.assertEqual(main.Action.name(main.Action.RECOGNITION), "Recognition")
        self.assertEqual(main.Action.name(main.Action.DEJA_VU), "Deja Vu")
        self.assertEqual(main.Action.name(main.Action.ANOINTMENT), "Anointment")
        self.assertEqual(main.Action.name(main.Action.STRENGTH), "Strength")
        self.assertEqual(main.Action.name(main.Action.SPIRIT), "Spirit")
        self.assertEqual(main.Action.PRICES[main.Action.DEATH], 24)
        self.assertEqual(main.Action.PRICES[main.Action.RECOGNITION], 24)
        self.assertEqual(main.Action.PRICES[main.Action.DEJA_VU], 28)
        for value in main.Action.ORDER:
            self.assertGreater(main.Action.PRICES[value], 0)
            self.assertIn(value, main.Action.GLYPHS)
            self.assertIn(value, main.Action.COLORS)
            self.assertTrue(main.Action.description(value, 1))
            self.assertTrue(main.Action.description(value, 2))
        self.assertEqual(main.Action.ORDER,
                         [main.Action.DEATH, main.Action.RECOGNITION,
                          main.Action.DEJA_VU, main.Action.ANOINTMENT,
                          main.Action.STRENGTH, main.Action.SPIRIT])
        # Deja Vu's two versions add triggers: +1, then +100.
        self.assertIn("+1 trigger", main.Action.description(main.Action.DEJA_VU, 1))
        self.assertIn("+100 triggers", main.Action.description(main.Action.DEJA_VU, 2))

    def test_shop_always_offers_some_actions(self):
        actions = [item for item in self.game.shop.items if item.kind == "action"]
        conds = [item for item in self.game.shop.items if item.kind == main.Component.CONDITION]
        # The catalogue is bigger than the room left in the shop's bottom row,
        # so each refresh shows a random SHOP_ACTION_SLOTS of them, all
        # different.
        self.assertEqual(len(actions), main.SHOP_ACTION_SLOTS)
        self.assertEqual(len({a.value for a in actions}), main.SHOP_ACTION_SLOTS)
        self.assertTrue(all(a.value in main.Action.ORDER for a in actions))
        # Two slots, two DISTINCT actions, on every single refresh.
        for _ in range(40):
            self.game.shop.refresh()
            offered = [i for i in self.game.shop.items if i.kind == "action"]
            self.assertEqual(len(offered), 2)
            self.assertEqual(len({a.value for a in offered}), 2)
        # Actions sit in row 3 to the right of the conditions.
        self.assertTrue(all(a.row == 3 for a in actions))
        self.assertEqual({a.col for a in actions}, {5, 6})
        self.assertTrue(max(c.col for c in conds) < min(a.col for a in actions))
        self.assertTrue(all(a.price == main.Action.PRICES[a.value] for a in actions))
        # An action arrives as v1 normally, but now and then it is a free v2.
        self.assertTrue(all(a.version in (1, 2) for a in actions))

    def test_action_prices_are_halved_and_the_upgrade_costs_200(self):
        # The first three action prices were halved (48 -> 24, 56 -> 28) and
        # upgrading an action to v2 is a flat $200 (it used to be $300, then
        # $240). The three later actions are stronger, so they sit a tier up.
        self.assertEqual(main.ACTION_UPGRADE_COST, 200)
        self.assertEqual(main.Action.PRICES[main.Action.DEATH], 24)
        self.assertEqual(main.Action.PRICES[main.Action.RECOGNITION], 24)
        self.assertEqual(main.Action.PRICES[main.Action.DEJA_VU], 28)
        self.assertEqual(main.Action.PRICES[main.Action.ANOINTMENT], 32)
        self.assertEqual(main.Action.PRICES[main.Action.STRENGTH], 28)
        self.assertEqual(main.Action.PRICES[main.Action.SPIRIT], 36)
        shop_actions = [i for i in self.game.shop.items if i.kind == "action"]
        self.assertEqual({a.price for a in shop_actions},
                         {main.Action.PRICES[a.value] for a in shop_actions})

    def test_a_new_action_is_rolled_for_the_free_v2(self):
        # random_action_version is the single roll behind every new action.
        self.assertEqual(main.ACTION_V2_CHANCE, 0.01)
        random.seed(4242)
        rolls = [main.random_action_version() for _ in range(20000)]
        self.assertIn(1, rolls)
        self.assertIn(2, rolls)
        share = rolls.count(2) / len(rolls)
        self.assertAlmostEqual(share, main.ACTION_V2_CHANCE, delta=0.004)

    def test_a_rolled_v2_action_shows_up_in_the_shop_and_in_grants(self):
        with mock.patch("main.random_action_version", return_value=2):
            self.game.shop.refresh()
            shop_actions = [i for i in self.game.shop.items if i.kind == "action"]
            self.assertTrue(shop_actions)
            self.assertTrue(all(a.version == 2 for a in shop_actions))
            self.game.actions.clear()
            self.assertTrue(self.game._grant_random_action())
            self.assertEqual(self.game.actions[-1].version, 2)

        with mock.patch("main.random_action_version", return_value=1):
            self.game.shop.refresh()
            self.assertTrue(all(a.version == 1 for a in self.game.shop.items
                                if a.kind == "action"))

    def test_a_naturally_v2_action_is_already_maxed(self):
        with mock.patch("main.random_action_version", return_value=2):
            self.game.shop.refresh()
        action = next(i for i in self.game.shop.items if i.kind == "action")
        self.game.actions.append(action)
        self.game.selected_action = action
        self.game.cash = 1000

        self.game._upgrade_action()

        self.assertEqual(action.version, 2)
        self.assertEqual(self.game.cash, 1000)  # nothing to pay: already v2

    def test_an_upgraded_action_is_gold_framed_and_gold_tagged(self):
        # An upgraded action has to be recognisable at a glance on a full shelf:
        # a v2 is drawn with a gold frame and a solid gold tag in its corner,
        # while a v1 keeps the plain white frame and its small "v1" label.
        gold = (255, 215, 0)
        rect = pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)
        canvas = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA)
        tag = main.ui.action_version_tag_rect(rect)

        def draw(version):
            canvas.fill((0, 0, 0, 0))
            main.ui.draw_action(canvas, main.ActionItem(main.Action.DEATH, 24,
                                                        version=version), rect)
            return (canvas.get_at((rect.left, rect.centery))[:3],
                    canvas.get_at((tag.left + 2, tag.centery))[:3])

        v1_frame, v1_tag = draw(1)
        self.assertEqual(v1_frame, main.WHITE)
        self.assertNotEqual(v1_tag, gold)  # a small label, not a plate

        v2_frame, v2_tag = draw(2)
        self.assertEqual(v2_tag, gold)     # the plate is solid gold
        self.assertNotEqual(v2_frame, main.WHITE)
        # The frame pulses so it catches the eye, but only between two golds.
        frames = set()
        for ticks in (0, 130, 260, 390, 520):
            with mock.patch("main.pygame.time.get_ticks", return_value=ticks):
                frames.add(draw(2)[0])
        self.assertGreater(len(frames), 1)
        for frame in frames:
            self.assertEqual(frame[0], 255)
            self.assertLess(frame[2], 200)  # never pulses all the way to white

    def test_a_v2_action_on_the_shelf_prices_in_gold(self):
        # The shelf flag has to be readable without hovering: an already-upgraded
        # action's price is drawn in the gold of its own frame, so the tile worth
        # an extra ACTION_UPGRADE_COST stands out across the shop.
        gold = (255, 215, 0)
        self.game.trials_enabled = False  # no Slim pickings trim to shift items
        self.game.shop_message = ""

        def price_gold(version):
            with mock.patch("main.random_action_version", return_value=version):
                self.game.shop.refresh()
            self.game.screen.fill(main.BLACK)
            main.ui.draw_shop(self.game)
            cells = []
            for item in self.game.shop.items:
                if getattr(item, "kind", None) != "action":
                    continue
                cx = (self.game.shop.rect.x + item.col * main.GRID_SIZE
                      + main.GRID_SIZE // 2)
                cy = (self.game.shop.rect.y + (item.row + 1) * main.GRID_SIZE
                      + main.GRID_SIZE // 2)
                cells.append(sum(
                    self.game.screen.get_at((x, y))[:3] == gold
                    for x in range(cx - 18, cx + 18)
                    for y in range(cy - 8, cy + 9)))
            return cells

        plain = price_gold(1)
        self.assertTrue(plain)
        self.assertEqual(plain, [0] * len(plain))  # a plain shelf prices white
        upgraded = price_gold(2)
        self.assertEqual(len(upgraded), len(plain))
        self.assertTrue(all(count > 0 for count in upgraded), upgraded)

    def test_a_reroll_that_shelves_an_upgraded_action_says_so(self):
        # The rare pre-upgraded action is named in the reroll message, so a
        # player who never reads the shelves is still told about the windfall.
        self.game.cash = 1000
        self.game.free_rerolls = 0
        self.game.trials_enabled = False

        with mock.patch("main.random_action_version", return_value=2):
            self.game._refresh_shop()
        self.assertIn("Refreshed shop", self.game.shop_message)
        self.assertIn("already upgraded", self.game.shop_message)
        for item in self.game.shop.items:
            if item.kind == "action":
                self.assertIn(f"{item.name} v2", self.game.shop_message)

        # A shelf of plain v1 actions gets the ordinary message back.
        with mock.patch("main.random_action_version", return_value=1):
            self.game._refresh_shop()
        self.assertNotIn("already upgraded", self.game.shop_message)

    def test_an_upgraded_action_says_so_in_its_name_and_info_box(self):
        v1 = main.ActionItem(main.Action.DEATH, 24)
        v2 = main.ActionItem(main.Action.DEATH, 24, version=2)
        # Only the upgraded one carries its version in its name, so it reads as
        # upgraded in the messages and the info box's title.
        self.assertEqual(self.game._item_name(v1), "Death")
        self.assertEqual(self.game._item_name(v2), "Death v2")
        self.assertEqual(dict(self.game._describe_item(v1))["Version"],
                         "v1 — upgrade to v2 for "
                         f"${self.game._inflated(main.ACTION_UPGRADE_COST)}")
        upgraded_row = dict(self.game._describe_item(v2))["Version"]
        self.assertIn("v2", upgraded_row)
        self.assertIn("fully upgraded", upgraded_row)

    def test_buying_action_adds_to_action_area_not_toolbox(self):
        self.game.cash = 1000
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game._buy_shop_item(action)
        self.assertIn(action, self.game.actions)
        self.assertNotIn(action, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 1000 - 60)

    def test_action_area_caps_at_two(self):
        self.game.cash = 10000
        for _ in range(3):
            self.game._buy_shop_item(main.ActionItem(main.Action.DEATH, 60))
        self.assertEqual(len(self.game.actions), main.MAX_ACTIONS)
        self.assertTrue(self.game.shop_message)

    def test_action_upgrade_to_v2_costs_200(self):
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 1000
        self.game.selected_action = action
        self.game._upgrade_action()
        self.assertEqual(action.version, 2)
        self.assertEqual(self.game.cash, 1000 - main.ACTION_UPGRADE_COST)

    def test_v2_action_cannot_be_upgraded(self):
        action = main.ActionItem(main.Action.RECOGNITION, 60, version=2)
        self.game.actions.append(action)
        self.game.cash = 1000
        self.game.selected_action = action
        self.game._upgrade_action()
        self.assertEqual(action.version, 2)
        self.assertEqual(self.game.cash, 1000)  # no charge, already v2

    def test_death_action_v1_sells_block_for_one_and_a_half(self):
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Pipe")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.assertTrue(self.game._apply_action())
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 100 + int(50 * 1.5))
        self.assertEqual(self.game.actions, [])  # consumed

    def test_death_action_v2_sells_block_for_six_times(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.MULT_ADD, 4, 40, "Rect")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEATH, 60, version=2)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.assertTrue(self.game._apply_action())
        self.assertEqual(self.game.cash, 100 + 40 * 6)

    def test_death_action_sells_card_for_one_and_a_half(self):
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = card
        self.assertTrue(self.game._apply_action())
        self.assertNotIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100 + int(24 * 1.5))

    def test_recognition_action_v1_duplicates_block_for_its_cost(self):
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Pipe")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.RECOGNITION, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.assertTrue(self.game._apply_action())
        # The original stays and a paid copy joins the toolbox.
        self.assertIn(block, self.game.toolbox.items)
        copies = [i for i in self.game.toolbox.items if i is not block
                  and i.shape == block.shape and i.scorer == block.scorer]
        self.assertEqual(len(copies), 1)
        self.assertEqual(self.game.cash, 100 - 50)
        self.assertEqual(self.game.actions, [])  # consumed

    def test_recognition_action_v2_duplicates_card_for_its_cost(self):
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        action = main.ActionItem(main.Action.RECOGNITION, 60, version=2)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = card
        self.assertTrue(self.game._apply_action())
        self.assertEqual(len(self.game.cards), 2)  # original + copy
        self.assertEqual(self.game.cash, 100 - 24)

    def test_apply_action_requires_subject(self):
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.game.selected_action_subject = None
        self.assertFalse(self.game._apply_action())
        self.assertIn(action, self.game.actions)  # not consumed without a target

    def test_s_key_applies_selected_action(self):
        # Select an action, pick a toolbox block subject, then press S.
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        # Click the action in the action area to select it.
        self._click((main.ACTION_AREA_COORDS[0] + 5, main.ACTION_AREA_COORDS[1] + 5))
        self.assertIs(self.game.selected_action, action)
        # Click the toolbox block to make it the subject.
        idx = self.game.toolbox.items.index(block)
        col = idx % self.game.toolbox.cols
        self._click((main.TOOLBOX_COORDS[0] + col * main.GRID_SIZE + 5,
                     main.TOOLBOX_COORDS[1] + 5))
        self.assertIs(self.game.selected_action_subject, block)
        # Press S to apply (Death sells it for 1.5x).
        self._press(main.pygame.K_s)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 100 + int(40 * 1.5))
        self.assertIsNone(self.game.selected_action)

    def test_actions_appear_in_collection_entries(self):
        entries = self.game._collection_entries()
        actions = [e for e in entries if e[0] == "action"]
        self.assertEqual(len(actions), len(main.Action.ORDER))
        for kind, value, name, desc, has_icon, discovered in actions:
            self.assertIn(value, main.Action.ORDER)
            self.assertEqual(name, "???")
            self.assertEqual(desc, "???")
            self.assertTrue(has_icon)
            self.assertFalse(discovered)

    def test_buying_action_discovers_it_in_collection(self):
        self.game.cash = 1000
        self.game._buy_shop_item(main.ActionItem(main.Action.RECOGNITION, 60))
        self.assertTrue(collection.is_action_discovered(main.Action.RECOGNITION))
        self.assertTrue(any(p.title == "New action" for p in self.game.popups))

    def test_joker_gives_plus_four_mult_at_run_start(self):
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 5)  # 1 + 4
        self.assertEqual(self.game.score_chips, 1)

    def test_joker_mult_applies_every_run(self):
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 5)

    def test_banker_card_gives_chip_per_ten_dollars(self):
        self.game.cards.append(main.CardItem(main.Card.BANKER, 25))
        self.game.score_chips = 1
        self.game.cash = 555
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1 + 555 // 10)

    def test_pillar_card_gives_mult_for_fullest_column(self):
        # Column 3 holds the most blocks (3), so Pillar adds +3 mult.
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(1, 0)] = main.Block(1, 0)
        self.game.grid[(1, 1)] = main.Block(1, 1)
        self.game.grid[(2, 0)] = main.Block(2, 0)
        self.game.grid[(3, 0)] = main.Block(3, 0)
        self.game.grid[(3, 1)] = main.Block(3, 1)
        self.game.grid[(3, 2)] = main.Block(3, 2)
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 1 + 3)

    def test_pillar_card_with_empty_board_adds_no_mult(self):
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 1)

    def test_pillar_card_particle_appears_near_fullest_column(self):
        # Pillar's start-phase particle pops when it adds mult for the fullest
        # column's blocks.
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(3, 0)] = main.Block(3, 0)
        self.game.grid[(3, 1)] = main.Block(3, 1)
        self.game.grid[(3, 2)] = main.Block(3, 2)  # column 3 is fullest
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(len(self.game.score_particles), 1)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "3")
        self.assertEqual(p.color, main.BLUE)

    def test_cards_spawn_one_particle_each_when_affecting_score(self):
        # Each card emits exactly one particle per score-affecting event, so
        # three cards affecting the score yield exactly three particles.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.cards.append(main.CardItem(main.Card.BANKER, 25))
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(3, 0)] = main.Block(3, 0)
        self.game.grid[(3, 1)] = main.Block(3, 1)  # fullest column
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.cash = 100
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(len(self.game.score_particles), 3)

    def test_wrecking_ball_card_gives_accumulated_mult_at_run_start(self):
        # The wrecking ball's +mult is permanent: whatever bonus has built up
        # from fragile breaks applies at the start of every run.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        self.game.wrecking_bonus[main.Scorer.MULT_ADD] = 6
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1 + 6)

    def test_wrecking_ball_bonus_grows_when_fragile_block_breaks(self):
        # Each fragile block break adds 3 to the run's mult gain (applied to
        # the current run live) and pops its particle near the block. It only
        # becomes permanent after a run.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game.score_mult = 1
        self.game.run_active = True
        self.game._on_fragile_broken(block)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)  # not committed
        self.assertEqual(self.game.score_mult, 4)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "3")
        self.assertEqual(p.color, main.BLUE)
        self.assertEqual((p.x, p.y), (block.rect.centerx, block.rect.centery))

    def test_fragile_break_sets_flag_and_grows_wrecking_ball_in_update(self):
        # A real physics shatter marks the block; the game's update() then
        # tracks the wrecking ball's run gain and spawns its particle at the
        # block.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.left - 10, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([400.0, 0.0])
        self.game.grid[(5, 8)] = block
        self.game.marbles.append(marble)
        self.game.run_active = True
        for _ in range(40):
            self.game.update()
            if self.game.wrecking_run_gain[main.Scorer.MULT_ADD] >= 3:
                break
        self.assertEqual(block.shape, main.Shape.NONE)  # the block shattered
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)
        p = self.game.score_particles[0]
        self.assertEqual((p.x, p.y), (block.rect.centerx, block.rect.centery))

    def test_wrecking_ball_run_gain_commits_when_continuing(self):
        # The gains earned during a run become permanent only after that run.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game.run_active = True
        self.game._on_fragile_broken(block)
        self.game._on_fragile_broken(block)  # two breaks this run
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 6)
        self._complete_run(10000, required=100)
        self.game._continue_run()
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 6)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 0)

    def test_wrecking_ball_run_gain_discarded_when_retrying(self):
        # Retrying a run discards the gains the wrecking ball earned during it.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game.run_active = True
        self.game._on_fragile_broken(block)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self._complete_run(10000, required=100)
        self.game._retry_run()
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 0)

    def test_glitch_card_gives_random_mult_between_zero_and_six_times_base(self):
        # Glitch pays a random 0..6 units, so the +4 mult base gives at most
        # +24 mult (6x base).
        self.game.cards.append(main.CardItem(main.Card.GLITCH, 20))
        self.game.score_mult = 1
        self.game._apply_cards()
        gained = self.game.score_mult - 1
        self.assertGreaterEqual(gained, 0)
        self.assertLessEqual(gained, 24)
        self.assertEqual(len(self.game.score_particles), 1)

    def test_ripped_card_gives_120_chips_when_fewer_than_five_blocks(self):
        self.game.cards.append(main.CardItem(main.Card.RIPPED_CARD, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(0, 1)] = main.Block(0, 1)
        self.game.score_chips = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1 + 120)
        self.assertEqual(len(self.game.score_particles), 1)

    def test_ripped_card_gives_nothing_with_more_than_five_blocks(self):
        # Ripped card grants 120 chips only with 5 blocks or fewer; with 6 it
        # grants nothing and spawns no particle.
        self.game.cards.append(main.CardItem(main.Card.RIPPED_CARD, 20))
        for i in range(6):
            self.game.grid[(i, 0)] = main.Block(i, 0)
        self.game.score_chips = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_plane_card_gives_chips_for_air_time_at_finish(self):
        # Plane gives +15 chips for each second the marble was in the air. The
        # 2.5s of air time pays a fractional 37.5 chips, kept as-is (only the
        # UI rounds to a tenth).
        self.game.cards.append(main.CardItem(main.Card.PLANE, 25))
        self.game.air_time = 2.5
        self.game.score_chips = 1
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_chips, 1 + 15 * 2.5)

    def test_plane_air_time_accumulates_while_marble_airborne(self):
        # A marble with nothing under it stays airborne, so air time grows.
        self.game.cards.append(main.CardItem(main.Card.PLANE, 25))
        self.game.marbles = [main.Marble(360, 120)]
        self.game.run_active = True
        for _ in range(30):
            self.game.update()
        self.assertGreater(self.game.air_time, 0.2)  # ~0.5s of air time

    def test_plane_air_time_stays_zero_while_marble_rests(self):
        # A marble resting on a floor block is in contact, so no air time.
        self.game.cards.append(main.CardItem(main.Card.PLANE, 25))
        floor = main.Block(5, 8)
        self.game.grid[(5, 8)] = floor
        marble = main.Marble(floor.rect.centerx, floor.rect.top - main.MARBLE_RADIUS - 1)
        self.game.marbles = [marble]
        self.game.run_active = True
        for _ in range(20):
            self.game.update()
        self.assertLess(self.game.air_time, 0.2)

    def test_err_404_card_grants_random_card_when_bought(self):
        # Buying the ERR 404 card grants a random (different) card instead of
        # joining the card area itself. The grant draws from the pre-built pool,
        # so a splittable grid card can carry any scorer.
        self.game.cards.clear()
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.ERR_404, 10))
        self.assertEqual(len(self.game.cards), 1)
        self.assertNotEqual(self.game.cards[0].value, main.Card.ERR_404)
        self.assertIn(self.game.cards[0].value, main.Card.NAMES)
        self.assertEqual(self.game.cash, 1000 - 10)

    def test_blueprint_copies_left_card_at_run_start(self):
        # A Blueprint next to a Joker behaves like a second Joker.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))      # left
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))  # copies it
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1 + 4 + 4)

    def test_blueprint_with_no_left_card_does_nothing(self):
        # A Blueprint in the leftmost slot has no card to copy.
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1)

    def test_blueprint_copies_finish_card(self):
        # A Blueprint next to an Explorer copies its end-of-run xMult.
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        marble = self._add_marble()
        marble.distance = 3000.0
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        fraction = (3000 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT)
        factor = 1 + fraction
        self.assertAlmostEqual(self.game.score_mult, factor * factor)  # Explorer + copy

    def test_blueprint_does_not_chain_another_blueprint(self):
        # Two Blueprints can't copy each other: each has a Blueprint (or
        # nothing) to its left, so neither does anything.
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1)

    def test_skater_card_gives_xmult_based_on_slippery_blocks_at_finish(self):
        # Skater gives (1 + 0.2 * slippery blocks owned) xMult at the END of
        # the run: xMult cards apply late, +mult cards apply at the start.
        self.game.cards.append(main.CardItem(main.Card.SKATER, 30))
        self.game.toolbox.items.clear()
        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                             main.Scorer.CHIPS_ADD, 10, 20, "S1",
                                             effects=[main.Effect.SLIPPERY]))
        self.game.grid[(0, 0)] = main.Block(0, 0, effects=[main.Effect.SLIPPERY])
        self.game.grid[(0, 1)] = main.Block(0, 1)
        self.game.score_mult = 1
        # At the start it is a no-op (xMult waits for the end of the run)...
        self.game._apply_cards()
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        # ...and at the end it applies the xMult.
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.2 * 2)

    def test_skater_card_with_no_slippery_blocks_is_neutral(self):
        # With no slippery blocks, Skater's xMult is exactly 1 (no effect).
        self.game.cards.append(main.CardItem(main.Card.SKATER, 30))
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_astronaut_card_gives_mult_for_black_hole_time(self):
        self.game.cards.append(main.CardItem(main.Card.ASTRONAUT, 30))
        self.game.score_mult = 1
        self.game.black_hole_time = 2.5
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 4 * 2.5)

    def test_black_hole_time_accumulates_while_marble_pulled(self):
        # A marble inside a black hole's range accumulates pull time each frame.
        block = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.BLACK_HOLE)
        self.game.grid[(5, 5)] = block
        marble = main.Marble(block.rect.centerx, block.rect.centery + 60)
        self.game.marbles.append(marble)
        self.game.run_active = True
        self.game.black_hole_time = 0.0
        for _ in range(30):
            self.game.update()
        self.assertGreater(self.game.black_hole_time, 0)

    def test_explorer_fraction_is_distance_over_total_grid_units(self):
        # Explorer's xMult is 1 + (travelled grid units / total grid cells).
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        marble = self._add_marble()
        marble.distance = 1500.0
        self.game.score_mult = 10
        self.game._apply_cards_on_finish()
        expected = 10 * (1 + (1500 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT))
        self.assertAlmostEqual(self.game.score_mult, expected)

    def test_explorer_applies_when_run_completes(self):
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        block = main.Block(0, 0, shape=main.Shape.SLOPE, scorer=main.Scorer.FINISH)
        marble = self._add_marble()
        marble.distance = 3000.0
        marble.collisions_this_tick = [block]
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_mult = 1
        self.game._handle_block_contacts([block])
        fraction = (3000 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT)
        self.assertAlmostEqual(self.game.score_mult, 1 + fraction)
        self.assertTrue(self.game.run_complete)

    def test_chips_block_spawns_green_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(len(self.game.score_particles), 1)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "10")
        self.assertEqual(p.color, main.GREEN)
        self.assertEqual((p.x, p.y), (block.rect.centerx, block.rect.centery))

    def test_mult_add_block_spawns_blue_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=2)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "2")
        self.assertEqual(p.color, main.BLUE)

    def test_mult_mul_block_spawns_red_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.MULT_MUL, scorer_amount=1.5)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "1.5")
        self.assertEqual(p.color, main.RED)

    def test_quick_block_spawns_green_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.QUICK)
        marble = self._add_marble()
        marble.velocity = np.array([2000.0, 0.0])
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_chips = 0
        self.game._handle_block_contacts([block])
        gained = int(2000.0 * main.QUICK_SCALE)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, str(gained))
        self.assertEqual(p.color, main.GREEN)

    def test_joker_card_spawns_blue_particle_at_card_area(self):
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "4")
        self.assertEqual(p.color, main.BLUE)
        expected_x = main.CARD_AREA_COORDS[0] + main.GRID_SIZE // 2
        expected_y = main.CARD_AREA_COORDS[1] + main.GRID_SIZE // 2
        self.assertEqual((p.x, p.y), (expected_x, expected_y))

    def test_explorer_card_spawns_red_particle_at_finish(self):
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        block = main.Block(0, 0, shape=main.Shape.SLOPE, scorer=main.Scorer.FINISH)
        marble = self._add_marble()
        marble.distance = 3000.0
        marble.collisions_this_tick = [block]
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_mult = 1
        self.game._handle_block_contacts([block])
        fraction = (3000 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT)
        factor = 1 + fraction
        p = self.game.score_particles[0]
        self.assertEqual(p.text, self.game._particle_amount_text(factor))
        self.assertEqual(p.color, main.RED)
        # The popup appears where the run ended (on the marble), so it is
        # visible instead of being lost at the top-of-screen card area.
        self.assertEqual((p.x, p.y), (float(marble.position[0]), float(marble.position[1])))

    def test_score_particles_jump_up_fade_and_get_pruned(self):
        p = main.ScoreParticle(100, 100, "+10", main.GREEN, self.game.font)
        start_y = p.y
        for _ in range(60):
            p.update(main.DT)
        self.assertLess(p.y, start_y)  # jumped upward out of the block
        self.assertGreater(p.age, 0)
        self.assertFalse(p.dead())  # still fading
        self.game.score_particles.append(p)
        for _ in range(240):
            self.game.update()
        self.assertEqual(self.game.score_particles, [])  # faded away and pruned

    def test_score_particles_clear_on_new_game(self):
        self.game.score_particles.append(
            main.ScoreParticle(100, 100, "+10", main.GREEN, self.game.font))
        self.game.reset_game()
        self.assertEqual(self.game.score_particles, [])

    def test_marble_leaves_trail_while_moving(self):
        # A moving marble drops shrinking trail dots behind it.
        game = main.Game()
        game.title_screen = False
        game.run_active = True
        marble = main.Marble(500, 200)
        marble.velocity = np.array([200.0, 0.0])
        game.marbles.append(marble)
        for _ in range(30):
            game.update()
        self.assertGreater(len(game.trail_particles), 0)

    def test_trail_particle_shrinks_fades_and_dies(self):
        p = main.TrailParticle(100, 100, 4.0, main.MARBLE_COLOR)
        self.assertFalse(p.dead())
        # The trail dot is rendered on an SRCALPHA surface so it can fade.
        self.assertTrue(p._surf.get_flags() & main.pygame.SRCALPHA)
        surf = main.pygame.Surface((40, 40))
        p.draw(surf)  # draws without raising
        for _ in range(50):  # 50 frames = 0.83s > life 0.6s
            p.update(main.DT)
        self.assertTrue(p.dead())
        # After death the game prunes it from the trail list.
        game = main.Game()
        game.title_screen = False
        game.trail_particles = [p]
        for _ in range(10):
            game.update()
        self.assertEqual(game.trail_particles, [])

    def test_trails_clear_on_new_run(self):
        self.game.trail_particles.append(
            main.TrailParticle(100, 100, 4.0, main.MARBLE_COLOR))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run(False)
        self.assertEqual(self.game.trail_particles, [])

    def test_card_describes_and_draws(self):
        # A composed magnitude card (Joker condition x +Mult) has a name and
        # description, draws, and renders in the card area.
        card = main.CardItem(main.Card.JOKER, 20)
        rows = self.game._describe_item(card)
        self.assertTrue(any("Joker" in label for label, _ in rows))
        self.assertTrue(any("+4 mult" in text for _, text in rows))
        surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        main.draw_shop_item(surface, card, surface.get_rect())
        self.game.cards.append(card)
        self.game.draw()  # renders the card area
        self.assertIn("Joker", self.game._item_name(card))

    def test_trial_data_is_defined(self):
        self.assertEqual(main.Trial.name(main.Trial.HANDS_TIED), "Hands tied")
        self.assertEqual(main.Trial.name(main.Trial.CARD_CUTTER), "Card cutter")
        self.assertEqual(main.Trial.name(main.Trial.DEAD_ZONE), "Dead zone")
        self.assertEqual(main.Trial.name(main.Trial.ALL_FINISHES), "All finishes")
        self.assertEqual(main.Trial.name(main.Trial.SLIM_PICKINGS), "Slim pickings")
        self.assertEqual(main.Trial.name(main.Trial.LONG_RUN), "Long run")
        self.assertEqual(main.Trial.name(main.Trial.SHUFFLED), "Shuffled")
        self.assertEqual(main.Trial.name(main.Trial.BOUNCY_CASTLE), "Bouncy castle")
        self.assertEqual(main.Trial.name(main.Trial.CRUMBLING), "Crumbling")
        self.assertEqual(main.Trial.name(main.Trial.MARBLE_WEIGHT), "Marble weight")
        self.assertEqual(main.Trial.name(main.Trial.SPEEDRUN), "Speedrun")
        self.assertEqual(main.Trial.name(main.Trial.REPEATS_ONLY), "Repeats only")
        self.assertEqual(main.Trial.name(main.Trial.INFLATION), "Inflation")
        self.assertEqual(main.Trial.name(main.Trial.EMPTY_POCKETS), "Empty pockets")
        self.assertEqual(main.Trial.name(main.Trial.DEAL_BREAKER), "Deal breaker")
        for trial in main.Trial.ORDER:
            self.assertTrue(main.Trial.description(trial))
        self.assertEqual(len(main.Trial.ORDER), 15)
        self.assertIn(main.Trial.DEAD_ZONE, main.Trial.ORDER)
        self.assertIn(main.Trial.ALL_FINISHES, main.Trial.ORDER)
        self.assertIn(main.Trial.SLIM_PICKINGS, main.Trial.ORDER)
        self.assertIn(main.Trial.LONG_RUN, main.Trial.ORDER)
        self.assertIn(main.Trial.SHUFFLED, main.Trial.ORDER)
        self.assertIn(main.Trial.BOUNCY_CASTLE, main.Trial.ORDER)
        self.assertIn(main.Trial.CRUMBLING, main.Trial.ORDER)
        self.assertIn(main.Trial.MARBLE_WEIGHT, main.Trial.ORDER)
        self.assertIn(main.Trial.SPEEDRUN, main.Trial.ORDER)
        self.assertIn(main.Trial.REPEATS_ONLY, main.Trial.ORDER)
        self.assertIn(main.Trial.INFLATION, main.Trial.ORDER)
        self.assertIn(main.Trial.EMPTY_POCKETS, main.Trial.ORDER)
        self.assertIn(main.Trial.DEAL_BREAKER, main.Trial.ORDER)

    def test_hands_tied_trial_maxes_quarter_of_blocks(self):
        # Exactly 1/4 of the marble-box blocks get their trigger limit maxed.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game._apply_trial()
        self.assertEqual(len(self.game.trial_maxed_blocks), 2)  # 8 // 4

        self.game.reset_run(False)
        for block in self.game.grid.values():
            if block in self.game.trial_maxed_blocks:
                self.assertEqual(block.triggers_left, main.TRIAL_MAX_TRIGGERS)
            else:
                self.assertEqual(block.triggers_left, block.trigger_limit)

    def test_card_cutter_trial_disables_random_card(self):
        # With a single owned card, Card cutter always disables it, so its
        # score effect is skipped for the run.
        joker = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(joker)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game._apply_trial()
        self.assertIs(self.game.disabled_card, joker)

        self.game.reset_run(False)
        self.assertEqual(self.game.score_mult, 1)  # Joker disabled: no +4
        self.assertEqual(self.game.score_chips, 1)

    def test_card_cutter_switches_off_passive_whole_card_effects(self):
        # A whole card has no start-of-run score effect: it works through a
        # passive rule read with _has_card. Card cutter has to switch those off
        # too (it used to only stop the composed condition+scorer cards).
        cases = (
            (main.Card.MINESHAFT, lambda: self.game._board_unit_price(),
             main.MINESHAFT_BOARD_UNIT_PRICE, main.BOARD_UNIT_PRICE),
            (main.Card.COUPON, lambda: self.game._shop_discount(100),
             int(100 * main.COUPON_PRICE_FACTOR), 100),
            (main.Card.MARKET, lambda: self.game._sell_fraction(),
             main.MARKET_SELL_FRACTION, 0.5),
            (main.Card.FACTORY, lambda: self.game._resource_cost(), 0.5, 1),
        )
        for value, read, with_card, without_card in cases:
            with self.subTest(card=main.Card.name(value)):
                self.game.cards = [main.CardItem(value, 30)]
                self.assertEqual(read(), with_card)
                # With a single owned card, Card cutter always cuts that one.
                self.game.current_trial = main.Trial.CARD_CUTTER
                self.game._apply_trial()
                self.assertTrue(self.game._card_disabled(self.game.cards[0]))
                self.assertTrue(main.cards._card_disabled(self.game,
                                                         self.game.cards[0]))
                self.assertEqual(read(), without_card)
                # The card is still OWNED, so the duplicate rules and the build
                # phase are untouched: only its effect is off.
                self.assertTrue(self.game._owns_card(value))
                self.assertFalse(self.game._has_card(value))

    def test_card_cutter_covers_every_passive_whole_card(self):
        # Every passive whole card is read through _has_card, so cutting it
        # silences it — and cutting one card never silences another.
        passive = [main.Card.SHOWMAN, main.Card.GARDEN, main.Card.RIGGED_CASINO,
                   main.Card.CONQUISTADOR, main.Card.COMPOUND_INTEREST,
                   main.Card.INFERNO, main.Card.WATCH, main.Card.PEDESTAL,
                   main.Card.DOPPELGANGER, main.Card.TESSERACT,
                   main.Card.THOUSAND_HANDED]
        for value in passive:
            with self.subTest(card=main.Card.name(value)):
                self.game.cards = [main.CardItem(value, 30),
                                   main.CardItem(main.Card.JOKER, 20)]
                self.assertTrue(self.game._has_card(value))
                self.game.disabled_card = self.game.cards[0]
                self.assertFalse(self.game._has_card(value))
                self.assertTrue(self.game._has_card(main.Card.JOKER))
                self.assertTrue(self.game._owns_card(value))
                # The disable is a run-time state: clearing it revives the card.
                self.game.disabled_card = None
                self.assertTrue(self.game._has_card(value))

    def test_a_cut_card_stops_feeding_its_own_effects(self):
        # The trial can be rolled while the player is still building (buying a
        # trial change applies it immediately), so a cut Tesseract must stop
        # growing its reroll bonus in the shop too.
        self.game.cash = 1000
        self.game.cards = [main.CardItem(main.Card.TESSERACT, 44)]
        self.game._refresh_shop()
        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + main.TESSERACT_REROLL_XMULT)
        self.game.disabled_card = self.game.cards[0]
        self.game._refresh_shop()
        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + main.TESSERACT_REROLL_XMULT)
        self.assertNotIn("Tesseract", self.game.shop_message)

    def test_a_cut_card_still_cannot_be_bought_again(self):
        # A disabled card is still owned, so the duplicate rule keeps biting: a
        # Card cutter run can't be used to buy a second copy of the cut card.
        self.game.cards = [main.CardItem(main.Card.COUPON, 46)]
        self.game.disabled_card = self.game.cards[0]
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.COUPON, 46))
        self.assertEqual(len(self.game.cards), 1)  # no duplicate added
        self.assertEqual(self.game.cash, 1000)     # not charged
        self.assertEqual(self.game.shop_message, "Already own this card")
        # Showman's own effect is what lifts the rule, so a cut Showman can't
        # lift it either.
        showman = main.CardItem(main.Card.SHOWMAN, 100)
        self.game.cards.append(showman)
        self.game.disabled_card = showman
        self.game._buy_shop_item(main.CardItem(main.Card.COUPON, 46))
        self.assertEqual(len(self.game.cards), 2)   # still no duplicate
        self.game.disabled_card = None
        self.game._buy_shop_item(main.CardItem(main.Card.COUPON, 46))
        self.assertEqual(len(self.game.cards), 3)   # Showman lifts it again

    def test_trial_is_chosen_before_run_starts(self):
        # A fresh game picks the trial up front (so the info box can show it
        # during setup); starting the run applies it without re-rolling it.
        self.game.trials_enabled = True
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        trial_before = self.game.current_trial
        self.game.reset_run()  # choose_trial defaults to True
        self.assertEqual(self.game.current_trial, trial_before)

    def test_slim_pickings_removes_two_shop_options(self):
        # When the next run's trial is Slim pickings, the shop loses two items.
        self.game.trials_enabled = True
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        before = len(self.game.shop.items)
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: (main.Trial.SLIM_PICKINGS
                                                 if seq is main.Trial.ORDER
                                                 else seq[0])):
            self.game._continue_run()
        self.assertEqual(len(self.game.shop.items), before - 2)

    def test_slim_pickings_leaves_shop_full_for_other_trials(self):
        self.game.trials_enabled = True
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        before = len(self.game.shop.items)
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: (main.Trial.HANDS_TIED
                                                 if seq is main.Trial.ORDER
                                                 else seq[0])):
            self.game._continue_run()
        self.assertEqual(len(self.game.shop.items), before)

    # --- Difficulty (chosen when a new save begins) -------------------------

    def test_difficulty_levels_are_defined(self):
        # Four levels, each naming itself and spelling its rules out, plus the
        # two knobs the game reads: how many of a round's runs play a trial and
        # the factor the required score grows by each run.
        self.assertEqual(main.Difficulty.ORDER, [1, 2, 3, 4])
        for level in main.Difficulty.ORDER:
            with self.subTest(difficulty=level):
                self.assertTrue(main.Difficulty.name(level))
                self.assertTrue(main.Difficulty.description(level))
                self.assertGreaterEqual(main.Difficulty.trials_per_round(level), 1)
                self.assertLessEqual(main.Difficulty.trials_per_round(level),
                                     main.RUNS_PER_ROUND)
                self.assertGreater(main.Difficulty.score_growth(level), 1.0)
        # The ladder the levels describe: 1.6x targets only on level 1, and a
        # trial on the round's last run for 1-2, its last two for 3, and every
        # run for 4.
        self.assertAlmostEqual(main.Difficulty.score_growth(1), 1.6)
        self.assertEqual([main.Difficulty.score_growth(level) for level in (2, 3, 4)],
                         [2.0, 2.0, 2.0])
        self.assertEqual([main.Difficulty.trials_per_round(level)
                          for level in (1, 2, 3, 4)], [1, 1, 2, 3])
        # A save with no difficulty of its own (an old save, a fresh game) is
        # the game's original balance: a trial for every run, doubling targets.
        self.assertEqual(main.DEFAULT_DIFFICULTY, main.Difficulty.LEVEL_4)

    def test_the_difficulty_sets_how_fast_the_target_grows(self):
        # Difficulty 1 asks 1.6x the last run's target, rounded down but never
        # less than one more than the last (so it can't stall at 1); the other
        # levels double it.
        try:
            main.REQUIRED_SCORES[:] = [1]
            gentle = [main.get_next_required_score(run, 1.6) for run in range(6)]
            main.REQUIRED_SCORES[:] = [1]
            doubled = [main.get_next_required_score(run, 2.0) for run in range(5)]
            # ...and a caller with no difficulty to hand still gets the 2x the
            # rest of the game assumes.
            main.REQUIRED_SCORES[:] = [1]
            default = [main.get_next_required_score(run) for run in range(4)]
        finally:
            main.REQUIRED_SCORES[:] = [1]  # the tests that follow expect this

        self.assertEqual(gentle, [1, 2, 3, 4, 6, 9])
        self.assertEqual(doubled, [1, 2, 4, 8, 16])
        self.assertEqual(default, [1, 2, 4, 8])

    def test_a_round_gives_trials_to_its_last_runs(self):
        # The difficulty decides how many of a round's runs play a trial, and
        # they are the round's LAST runs: difficulties 1-2 give only the final
        # run of a round a trial, difficulty 3 gives the last two, and
        # difficulty 4 gives every run of the round one.
        expected = {main.Difficulty.LEVEL_1: 1, main.Difficulty.LEVEL_2: 1,
                    main.Difficulty.LEVEL_3: 2, main.Difficulty.LEVEL_4: 3}
        for level, with_trial in expected.items():
            with self.subTest(difficulty=level):
                game = main.Game()
                game.trials_enabled = True
                game.difficulty = level
                trials = []
                for run in range(main.RUNS_PER_ROUND):
                    game._choose_trial(run)  # the run being set up
                    trials.append(game.current_trial)
                self.assertEqual(sum(t is not None for t in trials), with_trial,
                                 trials)
                for run, trial in enumerate(trials):
                    if run >= main.RUNS_PER_ROUND - with_trial:
                        self.assertIn(trial, main.Trial.ORDER)
                    else:
                        self.assertIsNone(trial, f"run {run + 1} is trial-free")

    def test_only_a_rounds_covered_runs_draw_a_trial(self):
        # A run that plays a trial draws it fresh, run by run (exactly as the
        # game always did), while a run that plays no trial draws nothing.
        self.game.difficulty = main.Difficulty.LEVEL_3  # last two runs only
        with mock.patch("main.random.choice",
                        return_value=main.Trial.SPEEDRUN) as choice:
            self.game._choose_trial(0)  # the round's first run: no trial
            self.assertIsNone(self.game.current_trial)
            self.game._choose_trial(1)
            self.assertEqual(self.game.current_trial, main.Trial.SPEEDRUN)
            self.game._choose_trial(2)
            self.assertEqual(self.game.current_trial, main.Trial.SPEEDRUN)
        self.assertEqual(choice.call_count, 2, "one draw per trial run")

    def test_the_new_save_screen_picks_the_difficulty(self):
        # The picker's buttons set the level of the save about to begin (the
        # marble click then starts it with that level), and opening the screen
        # for a new save starts from the default level.
        old_saves = save_system.SAVES_DIR
        save_system.SAVES_DIR = tempfile.mkdtemp()
        try:
            save_system.begin_new_game_selection(self.game, 3)
            self.assertTrue(self.game.marble_selecting)
            self.assertEqual(self.game.difficulty, main.DEFAULT_DIFFICULTY)

            self._click(self.game.difficulty_button_rect(2).center)
            self.assertEqual(self.game.difficulty, main.Difficulty.LEVEL_3)

            # Picking the marble begins the save, and the chosen level (like
            # the upgrade toggle) survives the game reset that does it.
            save_system.start_new_game_with_marble(self.game, main.MarbleType.EIGHT_BALL)
            self.assertFalse(self.game.marble_selecting)
            self.assertEqual(self.game.difficulty, main.Difficulty.LEVEL_3)
            self.assertEqual(self.game.marble_type, main.MarbleType.EIGHT_BALL)
            self.assertEqual(self.game.save_slot, 3)
        finally:
            shutil.rmtree(save_system.SAVES_DIR, ignore_errors=True)
            save_system.SAVES_DIR = old_saves

    def test_the_difficulty_is_saved(self):
        # The save carries the difficulty (the rules the save plays by), so a
        # loaded game keeps them.
        self.game.difficulty = main.Difficulty.LEVEL_3
        self.game.current_trial = main.Trial.SPEEDRUN

        data = save_system._save_data(self.game)

        self.assertEqual(data["difficulty"], main.Difficulty.LEVEL_3)
        fresh = main.Game()
        save_system._load_save_data(fresh, data, 1)
        self.assertEqual(fresh.difficulty, main.Difficulty.LEVEL_3)
        self.assertEqual(fresh.current_trial, main.Trial.SPEEDRUN)
        # ...and the rules that level stands for are the loaded game's own.
        self.assertEqual(fresh.trials_per_round,
                         main.Difficulty.trials_per_round(main.Difficulty.LEVEL_3))
        self.assertEqual(fresh.score_growth,
                         main.Difficulty.score_growth(main.Difficulty.LEVEL_3))

        # A save written before the difficulty existed reads as the default
        # level (the game's original balance).
        legacy = dict(data)
        legacy.pop("difficulty")
        old = main.Game()
        save_system._load_save_data(old, legacy, 1)
        self.assertEqual(old.difficulty, main.DEFAULT_DIFFICULTY)
        self.assertEqual(old.trials_per_round, main.RUNS_PER_ROUND)

    def test_long_run_doubles_ideal_time(self):
        # With Long run, the time factor peaks at double the ideal time and is
        # off-peak at the normal ideal time.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.run_time = main.TIME_IDEAL * 2
        peak, _, _, _ = self.game._score_factors()
        self.game.run_time = main.TIME_IDEAL
        off_peak, _, _, _ = self.game._score_factors()
        self.assertGreater(peak, 0.9)
        self.assertGreater(peak, off_peak)
        self.assertLess(off_peak, 0.5)

    def test_shuffled_trial_reorders_cards(self):
        # Shuffled flips and shuffles the player's cards when the run starts.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        before = [c.value for c in self.game.cards]
        self.game.current_trial = main.Trial.SHUFFLED
        # With shuffle stubbed out, the flip (reverse) is deterministic.
        with mock.patch("main.random.shuffle"):
            self.game._apply_trial()
        after = [c.value for c in self.game.cards]
        self.assertEqual(after, list(reversed(before)))

    def test_bouncy_castle_trial_marks_marble_bouncy_castle(self):
        # Starting a run under the bouncy-castle trial gives each marble the
        # bouncy_castle flag (physics reflects it off every solid block).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.BOUNCY_CASTLE
        self.game.reset_run(False)
        self.assertTrue(all(m.bouncy_castle for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.reset_run(False)
        self.assertFalse(any(m.bouncy_castle for m in self.game.marbles))

    def test_crumbling_trial_marks_quarter_of_blocks(self):
        # Crumbling marks ~1/4 of the placed solid (non-role) blocks fragile.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.FINISH)
        self.game.current_trial = main.Trial.CRUMBLING
        with mock.patch("main.random.sample",
                        side_effect=lambda seq, k: seq[:k]):
            self.game._apply_trial()
        # 8 scoring blocks -> 8 // 4 = 2 marked; START/FINISH never marked.
        self.assertEqual(len(self.game.trial_fragile_blocks), 2)
        for block in self.game.trial_fragile_blocks:
            self.assertTrue(block.trial_fragile)
            self.assertNotIn(block.scorer, (main.Scorer.START, main.Scorer.FINISH))
        self.assertFalse(self.game.grid[(0, 1)].trial_fragile)
        self.assertFalse(self.game.grid[(1, 1)].trial_fragile)

    def test_marble_weight_trial_sets_effect_mass_mult(self):
        # Marble weight rolls a factor (2.0 heavy / 0.5 light) each run; the
        # marble uses it to scale only effect pushes (1/effect_mass).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.MARBLE_WEIGHT
        with mock.patch("main.random.choice", return_value=2.0):
            self.game._apply_trial()
        self.assertEqual(self.game.trial_marble_weight, 2.0)
        self.game.reset_run(False)
        self.assertTrue(all(m.effect_mass_mult == 2.0 for m in self.game.marbles))

    def test_speedrun_trial_halves_ideal_time(self):
        # With Speedrun the time factor peaks at half the ideal time, so a run
        # that takes TIME_IDEAL/2 scores the full time contribution while one
        # taking the normal ideal time scores much less.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SPEEDRUN
        self.game.run_time = main.TIME_IDEAL / 2
        peak, _, _, _ = self.game._score_factors()
        self.game.run_time = main.TIME_IDEAL * 2  # well off the halved ideal
        off_peak, _, _, _ = self.game._score_factors()
        self.assertGreater(peak, 0.9)
        self.assertGreater(peak, off_peak)
        self.assertLess(off_peak, 0.5)

    def test_repeats_only_counts_types_only_once_touched_twice(self):
        # Under Repeats only, a type contributes to the uniqueness score only
        # after two distinct fresh touches (each qualifying type counts once).
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.REPEATS_ONLY
        block = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        # One fresh touch: nothing qualifies yet.
        self.game._count_fresh_touch(block)
        _, _, _, unique = self.game._score_factors()
        self.assertEqual(unique, 0)
        # A second fresh touch of the same block type qualifies all three types.
        self.game._count_fresh_touch(block)
        _, _, _, unique = self.game._score_factors()
        self.assertEqual(unique, 3)

    def test_inflation_trial_raises_prices_and_fees(self):
        # Inflation applies a 50% surcharge to shop prices and fees while it is
        # the current trial (chosen before the run, so its shop is inflated).
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.INFLATION
        self.assertEqual(self.game._inflated(100), 150)
        self.assertEqual(self.game._inflated(main.SHOP_REFRESH_COST),
                         int(main.SHOP_REFRESH_COST * 1.5 + 0.5))
        item = main.Component.effect_component(main.Effect.BOUNCY)
        self.assertEqual(self.game._buy_price(item),
                         self.game._inflated(item.price))
        # The surcharge disappears when the trial is not inflation.
        self.game.current_trial = main.Trial.HANDS_TIED
        self.assertEqual(self.game._inflated(100), 100)
        self.assertEqual(self.game._buy_price(item), item.price)

    def test_empty_pockets_skips_only_score_based_cash(self):
        # Empty pockets drops the score-ratio part of the end-of-run cash, but
        # the flat $20, interest, and Cash-card payouts still land.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.EMPTY_POCKETS
        self.game.cash = 50
        self.game.score_total = 100
        self.game.required_score = 10
        self.game.card_cash_run_gain = 7
        self.game._award_cash()
        # 0 (score-ratio skipped) + 20 + 50//10 + 7
        self.assertEqual(self.game.last_run_cash_gained, 20 + 5 + 7)
        self.assertEqual(self.game.cash, 50 + 20 + 5 + 7)
        # Without the trial the score-based bonus is included.
        other = main.Game()
        other.trials_enabled = False
        other.cash = 50
        other.score_total = 100
        other.required_score = 10
        other.card_cash_run_gain = 7
        other._award_cash()
        expected_gain = int(main.CASH_SCALE * (np.log(100) - np.log(10))) + 20 + 5 + 7
        self.assertEqual(other.cash, 50 + expected_gain)

    def test_deal_breaker_disables_all_cards_of_one_condition(self):
        # Deal breaker picks a condition the player owns and disables every
        # card whose condition matches it.
        start_chips = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        start_mult = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        dist_mult = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.MULT_MUL)
        c_start1 = main.CardItem(start_chips, 20)
        c_start2 = main.CardItem(start_mult, 20)
        c_dist = main.CardItem(dist_mult, 25)
        self.game.cards = [c_start1, c_start2, c_dist]
        self.game.current_trial = main.Trial.DEAL_BREAKER
        # Force the chosen condition to be START (present in the owned cards).
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: main.Condition.START
                        if main.Condition.START in seq else seq[0]):
            self.game._apply_trial()
        self.assertIn(c_start1, self.game.deal_broken_cards)
        self.assertIn(c_start2, self.game.deal_broken_cards)
        self.assertNotIn(c_dist, self.game.deal_broken_cards)
        # The disabled cards are skipped when the run applies its cards.
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1)  # START+chips disabled
        self.assertEqual(self.game.score_mult, 1)   # START+mult disabled

    def test_trial_box_draws_title_and_description(self):
        # With no trial, the box draws nothing; with a trial it renders the
        # title + description without raising.
        self.game.current_trial = None
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.draw_trial_box()

    def test_trial_box_shows_no_trial_once_it_is_disabled(self):
        # Buying the trial away leaves the display up (showing NO TRIAL) so the
        # player can still click its halves; with trials switched off for the
        # save, the box disappears entirely.
        self.game.trials_enabled = True
        self.game.current_trial = None
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.screen.fill(main.BLACK)
            self.game.draw_trial_box()
        box = main.TRIAL_BOX_RECT
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(box.left, box.right)
                  for y in range(box.top, box.bottom)}
        self.assertIn((255, 215, 0), colors)  # the box border/title
        self.game.trials_enabled = False
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.screen.fill(main.BLACK)
            self.game.draw_trial_box()
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(box.left, box.right)
                  for y in range(box.top, box.bottom)}
        self.assertEqual(colors, {(0, 0, 0)})

    def test_trial_display_hover_shows_the_buy_options(self):
        # Hovering the display while building overlays the two options; a run
        # in progress (or the cursor elsewhere) shows none.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.cash = 1000
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=main.TRIAL_BOX_RECT.center), \
             mock.patch("main.ui.draw_trial_options") as draw:
            self.game.draw_trial_box()
        draw.assert_called_once()
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)), \
             mock.patch("main.ui.draw_trial_options") as draw:
            self.game.draw_trial_box()
        draw.assert_not_called()
        self.game.run_active = True
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=main.TRIAL_BOX_RECT.center), \
             mock.patch("main.ui.draw_trial_options") as draw:
            self.game.draw_trial_box()
        draw.assert_not_called()

    def test_trial_display_options_draw_without_raising(self):
        # The overlay renders in every combination (affordable / not, trial
        # running / not) and covers each half of the display.
        self.game.trials_enabled = True
        for trial in (main.Trial.LONG_RUN, None):
            for cash in (0, 1000):
                self.game.current_trial = trial
                self.game.cash = cash
                left, right = main.ui.draw_trial_options(
                    self.game, main.TRIAL_BOX_RECT)
                self.assertEqual(left.width, main.TRIAL_BOX_RECT.width // 2)
                self.assertEqual(right.right, main.TRIAL_BOX_RECT.right)

    def test_trial_display_left_half_buys_a_different_random_trial(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.cash = 1000
        self.game._apply_trial()
        self.assertEqual(self.game.trial_maxed_blocks, set())  # empty board
        bought = self.game._click_trial_display(
            (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertTrue(bought)
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.assertNotEqual(self.game.current_trial, main.Trial.HANDS_TIED)
        self.assertIn("Trial changed", self.game.shop_message)

    def test_trial_change_never_offers_the_trial_already_running(self):
        # The reroll passes only OTHER trials to random.choice, so the bought
        # trial is always a different one.
        self.game.trials_enabled = True
        self.game.cash = 100000
        seen = {}

        def pick(sequence):
            seen["candidates"] = list(sequence)
            return sequence[0]

        self.game.current_trial = main.Trial.DEAD_ZONE
        with mock.patch("main.random.choice", side_effect=pick):
            self.game._click_trial_display(
                (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertNotIn(main.Trial.DEAD_ZONE, seen["candidates"])
        self.assertEqual(len(seen["candidates"]), len(main.Trial.ORDER) - 1)
        self.assertNotEqual(self.game.current_trial, main.Trial.DEAD_ZONE)

    def test_trial_display_right_half_buys_no_trial(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.cash = 1000
        bought = self.game._click_trial_display(
            (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery))
        self.assertTrue(bought)
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)
        self.assertEqual(self.game.shop_message,
                         f"Trial disabled (${main.TRIAL_DISABLE_COST})")
        # Buying it away twice is refused (and free).
        self.assertFalse(self.game._click_trial_display(
            (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_DISABLE_COST)
        self.assertIn("no trial", self.game.shop_message)

    def test_trial_display_needs_cash_and_the_build_phase(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        # Too little cash: nothing changes and both fees are named.
        self.game.cash = 10
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.shop_message,
                         f"Need ${main.TRIAL_CHANGE_COST} to change the trial")
        self.assertFalse(self.game._click_trial_display(right))
        self.assertEqual(self.game.shop_message,
                         f"Need ${main.TRIAL_DISABLE_COST} to disable the trial")
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 10)
        # A run in progress fixes its trial: the display is display-only.
        self.game.cash = 1000
        self.game.run_active = True
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 1000)
        self.assertIn("while building", self.game.shop_message)
        # The post-run RETRY/CONTINUE state and the final boss run are out too.
        self.game.run_active = False
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.assertFalse(self.game._click_trial_display(right))
        self.assertEqual(self.game.cash, 1000)
        self.game.awaiting_after_run = False
        self.game.run_complete = False
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 1000)

    def test_clicking_the_trial_display_halves_buys_trial_changes(self):
        # The click handler routes the display's two halves to the purchases.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.cash = 1000
        self._click((main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertNotEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self._click((main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery))
        self.assertEqual(
            self.game.cash,
            1000 - main.TRIAL_CHANGE_COST - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)

    def test_shop_message_sits_between_the_shop_title_and_the_refresh_button(self):
        # A shop dialog lives in the panel's bottom strip: right of the SHOP
        # title (bottom-left) and left of the REFRESH button (bottom-right).
        title_right = (main.SHOP_COORDS[0] + 8
                       + self.game.font.size("SHOP")[0])
        lines, rect = main.ui.shop_message_layout(self.game, "Refreshed shop ($20)")
        self.assertEqual(len(lines), 1)
        self.assertGreaterEqual(rect.left, title_right)
        self.assertLessEqual(rect.right, main.SHOP_REFRESH_BUTTON_RECT.left)
        self.assertEqual(rect.centery, main.SHOP_REFRESH_BUTTON_RECT.centery)
        self.assertGreater(rect.top, main.SHOP_COORDS[1] + 4 * main.GRID_SIZE)
        # A message too long for the gap wraps onto two tiny lines that both
        # stay inside it.
        long_lines, long_rect = main.ui.shop_message_layout(
            self.game, "Disassembled Slippery Fragile Pipe +Chips v2 ($56)")
        self.assertEqual(len(long_lines), 2)
        self.assertGreaterEqual(long_rect.left, title_right)
        self.assertLessEqual(long_rect.right, main.SHOP_REFRESH_BUTTON_RECT.left)
        self.assertEqual(long_rect.centery, main.SHOP_REFRESH_BUTTON_RECT.centery)

    def test_shop_message_draws_in_the_bottom_strip(self):
        # Drawing the shop with a message paints it where the layout puts it.
        self.game.shop_message = "Refreshed shop ($20)"
        _lines, rect = main.ui.shop_message_layout(self.game, self.game.shop_message)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_shop(self.game)
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(rect.left, rect.right)
                  for y in range(rect.top, rect.bottom)}
        self.assertIn(main.YELLOW, colors)

    def test_all_finishes_trial_marks_marbles_finish_on_border(self):
        # Starting a run under the all-finishes trial gives each marble the
        # finish_on_border flag (physics does the actual border finish).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.reset_run(False)
        self.assertTrue(all(m.finish_on_border for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.reset_run(False)
        self.assertTrue(all(m.dead_zone for m in self.game.marbles))
        self.assertFalse(any(m.finish_on_border for m in self.game.marbles))

    def test_all_finishes_trial_draws_yellow_marble_box_border(self):
        # The marble-box outer border is gold (the finish scorer color) while
        # the all-finishes trial is active, and the normal dark gray otherwise.
        # The thick border sits just above the box (centered at
        # y - BORD_WIDTH//2), so sample inside it rather than the fill below.
        border_px = (main.MARBLE_BOX_COORDS[0] + 20,
                     main.MARBLE_BOX_COORDS[1] - main.BORD_WIDTH // 2)
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.draw()
        self.assertEqual(self.game.screen.get_at(border_px)[:3],
                         main.Scorer.color(main.Scorer.FINISH))
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.draw()
        self.assertEqual(self.game.screen.get_at(border_px)[:3], (30, 30, 30))

    def test_disabled_card_draws_dimmed(self):
        joker = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(joker)
        self.game.disabled_card = joker
        self.game.draw()  # renders the dimmed card without raising

        # A card disabled by either trial (Card cutter's disabled_card or Deal
        # breaker's deal_broken_cards) is dimmed, so the player can see which
        # card got cut.
        rect = main.pygame.Rect(main.CARD_AREA_COORDS[0], main.CARD_AREA_COORDS[1],
                                main.GRID_SIZE, main.GRID_SIZE)

        def brightness():
            return sum(sum(self.game.screen.get_at((x, y))[:3])
                       for x in range(rect.left, rect.right)
                       for y in range(rect.top, rect.bottom))

        self.game.disabled_card = None
        self.game.deal_broken_cards = set()
        self.game.draw()
        plain = brightness()
        self.game.disabled_card = joker
        self.game.draw()
        cut = brightness()
        self.game.disabled_card = None
        self.game.deal_broken_cards = {joker}
        self.game.draw()
        self.assertLess(cut, plain)
        self.assertEqual(brightness(), cut)

    def test_cards_render_mini_card_and_card_back(self):
        # The mini-card look renders without raising for a filled slot (with
        # selection) and an empty slot (card back).
        card = main.CardItem(main.Card.JOKER, 20)
        face = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        main.draw_card(face, card, face.get_rect(), selected=True)
        back = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        main.draw_card_back(back, back.get_rect())
        self.game.cards.append(card)
        self.game.draw()  # renders the card face in the card area

    def test_title_screen_achievements_button_opens_tab(self):
        # The title screen's ACHIEVEMENTS button opens the achievements tab.
        self.game.title_screen = True
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        pos = main.ACHIEVEMENTS_BUTTON_RECT.center
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()
        self.assertFalse(self.game.title_screen)
        self.assertTrue(self.game.achievements_open)

    def test_title_screen_ignores_clicks_away_from_slots(self):
        self.game.title_screen = True
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=(20, 20)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()
        self.assertTrue(self.game.title_screen)  # still on the title screen

    def test_title_screen_draws_slots_and_achievements_button(self):
        self.game.title_screen = True
        self.game.draw()  # renders the title + save slots + ACHIEVEMENTS button
        self.assertTrue(main.ACHIEVEMENTS_BUTTON_RECT.collidepoint(main.ACHIEVEMENTS_BUTTON_RECT.center))
        # After starting a game the normal game draws.
        self.game.title_screen = False
        self.game.draw()

    def test_shop_blocks_are_made_of_random_valid_components(self):
        blocks = [item for item in self.game.shop.items if item.kind == "block"]

        for block in blocks:
            self.assertIn(block.shape, main.Shape.ORDER)
            self.assertIn(block.effect, main.Effect.ORDER)
            self.assertIn(block.scorer, main.Scorer.ORDER)
            # The scorer arrives with its own rolled magnitude: the average
            # plus or minus a whole number of steps (and exactly the average
            # for a scorer whose amount is not a magnitude at all).
            average = main.Scorer.DEFAULT_AMOUNT[block.scorer]
            step = main.magnitude_step(average)
            if not step:
                self.assertEqual(block.scorer_amount, average)
            else:
                floor = main.scorer_magnitude_floor(block.scorer)
                if block.scorer_amount != floor:
                    self.assertAlmostEqual((block.scorer_amount - average) / step,
                                          round((block.scorer_amount - average) / step))
                self.assertLessEqual(abs(block.scorer_amount - average),
                                     step * main.MAGNITUDE_MAX_STEPS)
            # A scaleable effect records its strength; an on/off one has none.
            for e in block.effects:
                if e in main.Effect.MAGNITUDE:
                    self.assertIn(e, block.effect_amounts)
                    self.assertGreater(block.effect_amounts[e], 0)
                else:
                    self.assertNotIn(e, block.effect_amounts)

    def test_shop_never_sells_role_scorer_components(self):
        # START and FINISH are shop goods now, but only ever as ready-made
        # plain Rect blocks: a role SCORER component would let the player
        # assemble a role block with an arbitrary shape and effects, and a role
        # block must never carry physics the player did not choose.
        for _ in range(40):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == main.Component.SCORER:
                    self.assertNotIn(item.value, (main.Scorer.START, main.Scorer.FINISH))
                if getattr(item, "scorer", None) in (main.Scorer.START, main.Scorer.FINISH):
                    self.assertEqual(item.shape, main.Shape.RECT)
                    self.assertEqual(item.effects, [])

    def test_component_weight_favors_cheaper_components(self):
        # Rarity is the inverse of price: cheaper components are more common.
        self.assertGreater(main.component_weight(main.Component.SHAPE, main.Shape.RECT),
                           main.component_weight(main.Component.SHAPE, main.Shape.CURVED_SLOPE))
        self.assertGreater(main.component_weight(main.Component.EFFECT, main.Effect.NONE),
                           main.component_weight(main.Component.EFFECT, main.Effect.PORTAL))
        self.assertGreater(main.component_weight(main.Component.SCORER, main.Scorer.NONE),
                           main.component_weight(main.Component.SCORER, main.Scorer.MULT_MUL))

    def test_block_rarity_is_product_of_component_rarities(self):
        # A block's frequency is the product of its components' weights, so
        # each rare part compounds the block's rarity multiplicatively.
        def block_weight(shape, effect, scorer):
            return (main.component_weight(main.Component.SHAPE, shape)
                    * main.component_weight(main.Component.EFFECT, effect)
                    * main.component_weight(main.Component.SCORER, scorer))

        cheap = block_weight(main.Shape.RECT, main.Effect.NONE, main.Scorer.NONE)
        one_rare = block_weight(main.Shape.RECT, main.Effect.NONE, main.Scorer.MULT_MUL)
        two_rare = block_weight(main.Shape.RECT, main.Effect.PORTAL, main.Scorer.MULT_MUL)

        self.assertGreater(cheap, one_rare)
        self.assertGreater(one_rare, two_rare)
        # Each added rare part shrinks the odds by that part's own ratio, so the
        # effect compounds instead of adding.
        self.assertGreater(cheap / one_rare, 1)
        self.assertGreater(one_rare / two_rare, 1)
        self.assertGreater((cheap / one_rare) * (one_rare / two_rare), 1)

    def test_weighted_sample_without_replacement_returns_distinct_items(self):
        with mock.patch("main.random.choices", side_effect=lambda *a, **kw: [a[0][0]]):
            result = main.weighted_sample_without_replacement([1, 2, 3], [1, 1, 1], 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(set(result)), 2)  # distinct items, no duplicates

    def test_shop_weighted_sampling_favors_cheap_components(self):
        # Over many draws the cheapest shape appears more often than the rarest.
        main.random.seed(20240824)
        shape_weights = [main.component_weight(main.Component.SHAPE, s) for s in main.Shape.ORDER]
        picks = [main.random.choices(main.Shape.ORDER, weights=shape_weights, k=1)[0]
                 for _ in range(2000)]
        self.assertGreater(picks.count(main.Shape.RECT), picks.count(main.Shape.CURVED_SLOPE))

    def test_shop_refresh_rerolls_items(self):
        original = [item.name for item in self.game.shop.items]

        self.game.shop.refresh()
        refreshed = [item.name for item in self.game.shop.items]

        self.assertEqual(len(refreshed), 15)
        self.assertNotEqual(original, refreshed)

    def test_shop_refreshes_when_continuing(self):
        marble = self._add_marble()
        marble.distance = 100.0
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.run_time = 3.0
        before = [item.name for item in self.game.shop.items]

        self.game._handle_block_contacts([])

        self.assertTrue(self.game.run_complete)
        # The shop is not rerolled until the player clicks CONTINUE.
        self.assertEqual([item.name for item in self.game.shop.items], before)

        self.game._continue_run()

        after = [item.name for item in self.game.shop.items]
        self.assertNotEqual(before, after)

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

    def test_retry_undoes_cleared_run(self):
        self.game.cash = 100
        self._complete_run(10000, required=1)
        self.assertTrue(self.game.awaiting_after_run)
        self.assertEqual(self.game.runs_cleared, 1)

        self.game._retry_run()

        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.runs_cleared, 0)
        self.assertEqual(self.game.last_run_cash_gained, 0)
        self.assertAlmostEqual(self.game.cash, 100)  # award undone
        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.required_score, 1)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)

    def test_retry_undoes_failed_run(self):
        self._complete_run(100, required=1000)
        self.assertEqual(self.game.failed_runs, 1)

        self.game._retry_run()

        self.assertEqual(self.game.failed_runs, 0)
        self.assertEqual(self.game.run_results, [])
        self.assertFalse(self.game.run_complete)

    def test_non_continue_click_during_post_run_retries(self):
        self.game.cash = 100
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self._click((20, 20))  # any action that isn't CONTINUE acts as RETRY

        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.runs_cleared, 0)
        self.assertEqual(self.game.cash, 100)  # award undone
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)

    def test_key_during_post_run_retries(self):
        self.game.cash = 100
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self._press(main.pygame.K_t)  # any key during the post-run state retries

        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.runs_cleared, 0)
        self.assertEqual(self.game.cash, 100)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)

    def test_placing_block_during_post_run_retries_then_places(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.cash = 100
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self._click(self._grid_pos(1, 1))  # place a block during the post-run state

        self.assertFalse(self.game.awaiting_after_run)  # retried first
        self.assertEqual(self.game.run_results, [])
        self.assertIn((1, 1), self.game.grid)  # then the action played out

    def test_continue_advances_to_next_run(self):
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self.game._continue_run()  # the player CONTINUEs to the next run

        self.assertEqual(self.game.run_number, 1)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)

    def test_y_key_does_not_advance_during_active_run(self):
        # Pressing Y while a run is still in progress (marbles not finished)
        # must not skip ahead to the next round.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run(False)
        self.assertTrue(self.game.run_active)
        self.assertFalse(self.game.run_complete)

        self._press(main.pygame.K_y)

        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[0])
        self.assertFalse(self.game.run_complete)
        self.assertFalse(self.game.awaiting_after_run)

    def test_y_key_continues_after_run_completes(self):
        # Y is the CONTINUE key: after a run finishes it advances to the next
        # run WITHOUT retrying first (the run result is kept).
        self.game.cash = 100
        self.game.run_time = main.TIME_IDEAL
        self._complete_run(10000, required=1)
        self.assertTrue(self.game.awaiting_after_run)

        self._press(main.pygame.K_y)

        self.assertEqual(self.game.run_number, 1)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])
        self.assertEqual(self.game.run_results, [True])  # not retried
        self.assertEqual(self.game.runs_cleared, 1)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)

    def test_touched_types_recorded_from_contacts(self):
        b1 = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        b2 = main.Block(1, 0, shape=main.Shape.RECT, effect=main.Effect.NONE,
                        scorer=main.Scorer.MULT_ADD, scorer_amount=2)
        marble = self._add_marble()
        marble.collisions_this_tick = [b1, b2]
        self.game.run_active = True

        self.game._handle_block_contacts([b1, b2])

        # Plain/basic parts are excluded from uniqueness: RECT shapes, the NONE
        # effect, and START/FINISH scorers do not count.
        self.assertEqual(self.game.touched_shapes, {main.Shape.SLOPE})
        self.assertEqual(self.game.touched_effects, {main.Effect.BOUNCY})
        self.assertEqual(self.game.touched_scorers, {main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD})

    def test_award_cash_is_log_difference_of_score_to_required(self):
        self.game.cash = 0
        self.game.score_total = 100
        self.game.required_score = 10

        self.game._award_cash()

        expected = int(main.CASH_SCALE * (np.log(100) - np.log(10))) + 20
        self.assertAlmostEqual(self.game.cash, expected)
        self.assertAlmostEqual(self.game.last_run_cash_gained, expected)

    def test_award_cash_never_logs_zero_score(self):
        # A score_total of 0 (run not yet scored) clamps to 1 so no -inf; only
        # the flat +20 bonus is awarded.
        self.game.cash = 0
        self.game.score_total = 0
        self.game.required_score = 4

        self.game._award_cash()

        self.assertAlmostEqual(self.game.cash, 20.0)
        self.assertAlmostEqual(self.game.last_run_cash_gained, 20.0)

    def test_completed_run_awards_log_difference_cash(self):
        self.game.cash = 0
        b1 = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = self._add_marble()
        marble.collisions_this_tick = [b1]
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = 1000
        self.game.score_mult = 2
        self.game.run_time = main.TIME_IDEAL
        self.game.required_score = 2

        self.game._handle_block_contacts([b1])

        self.assertTrue(self.game.run_cleared)
        # Cash is awarded as a whole number (int) plus a flat 20 bonus; the
        # required score clamps to a minimum of 2.
        expected = int(main.CASH_SCALE * (np.log(self.game.score_total) - np.log(2))) + 20
        self.assertAlmostEqual(self.game.last_run_cash_gained, expected)
        self.assertAlmostEqual(self.game.cash, expected)

    def test_touched_types_reset_each_run(self):
        self.game.touched_shapes = {main.Shape.RECT}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run())

        # The type bonus counts only the types touched THIS run.
        self.assertEqual(self.game.touched_shapes, set())
        self.assertEqual(self.game.touched_effects, set())
        self.assertEqual(self.game.touched_scorers, set())

    def test_touched_types_reset_on_new_game(self):
        self.game.touched_shapes = {main.Shape.RECT}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}

        self.game.reset_game()

        self.assertEqual(self.game.touched_shapes, set())
        self.assertEqual(self.game.touched_effects, set())
        self.assertEqual(self.game.touched_scorers, set())

    def test_touched_types_are_per_run_and_filtered(self):
        # A SLOPE block records its shape; each game starts with empty sets.
        game1 = main.Game()
        b1 = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [b1]
        game1.marbles.append(marble)
        game1.run_active = True
        game1._handle_block_contacts([b1])
        self.assertEqual(game1.touched_shapes, {main.Shape.SLOPE})
        self.assertEqual(len(game1.touched_shapes) + len(game1.touched_effects) + len(game1.touched_scorers), 3)

        # A fresh game touching a RECT block records no shape (RECT is excluded
        # by the uniqueness filter), so only its effect and scorer count.
        game2 = main.Game()
        b2 = main.Block(1, 1, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble2 = main.Marble(300, 300)
        marble2.collisions_this_tick = [b2]
        game2.marbles.append(marble2)
        game2.run_active = True
        game2._handle_block_contacts([b2])
        self.assertEqual(game2.touched_shapes, set())
        self.assertEqual(len(game2.touched_shapes) + len(game2.touched_effects) + len(game2.touched_scorers), 2)

    def test_continue_after_final_run_ends_game(self):
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)

        self._complete_run(1000000, required=1)  # 24th run clears and CONTINUEs
        self.game._continue_run()

        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)

    def test_failing_boss_run_ends_in_defeat(self):
        # The 24th run is a boss run: it must be CLEARED to win. With only one
        # prior loss, failing it ends the game in defeat (not a win) and
        # awards defeat dice like any other loss.
        for run in range(main.TOTAL_RUNS - 1):
            if run == 5:
                self._complete_run(100, required=1000)  # 1 prior loss
            else:
                self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertFalse(self.game.game_over)

        self._complete_run(100, required=1000)  # fail the 24th (boss) run
        self.game._continue_run()

        self.assertTrue(self.game.game_over)
        self.assertFalse(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.game_over_dice_gained, (main.TOTAL_RUNS - 3) ** 2)
        self.assertEqual(metagame.dice(), (main.TOTAL_RUNS - 3) ** 2)

    def _run_dot_pixel(self, run_index):
        """The screen center of the run dot for the given run index.

        The 8x3 grid lays rounds across (columns) and runs down (rows), so a
        run index maps to col = round, row = run-within-round.
        """
        x0, y0 = main.RUN_DOT_GRID
        col = run_index // main.RUNS_PER_ROUND
        row = run_index % main.RUNS_PER_ROUND
        return (x0 + col * main.RUN_DOT_DX, y0 + row * main.RUN_DOT_DY)

    def test_final_boss_data_is_defined(self):
        self.assertEqual(main.FinalBoss.name(main.FinalBoss.SINGULARITY), "Singularity")
        self.assertEqual(main.FinalBoss.name(main.FinalBoss.SKY_HIGH), "Sky High")
        for boss in main.FinalBoss.ORDER:
            self.assertTrue(main.FinalBoss.description(boss))
        self.assertEqual(len(main.FinalBoss.ORDER), 2)
        self.assertIn(main.FinalBoss.SINGULARITY, main.FinalBoss.ORDER)
        self.assertIn(main.FinalBoss.SKY_HIGH, main.FinalBoss.ORDER)

    def test_final_boss_is_chosen_on_the_24th_run(self):
        # Reaching the last run picks a final boss (randomly) for run 24.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)
        self.assertIn(self.game.final_boss, main.FinalBoss.ORDER)

    def test_boss_run_has_no_trial(self):
        # The 24th run has a final boss instead of a trial.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)
        self.assertIsNone(self.game.current_trial)

    def test_sky_high_triples_required_score_on_boss_run(self):
        # Forcing the Sky High boss triples the 24th run's required score.
        def fake_choice(seq):
            return main.FinalBoss.SKY_HIGH if seq == main.FinalBoss.ORDER else seq[0]
        with mock.patch("main.random.choice", side_effect=fake_choice):
            for _ in range(main.TOTAL_RUNS - 1):
                self._complete_run(1000000, required=1)
                self.game._continue_run()
        self.assertEqual(self.game.final_boss, main.FinalBoss.SKY_HIGH)
        base = main.get_next_required_score(main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.required_score, base * 3)

    def test_endless_play_drops_the_boss_and_hands_the_run_back_to_a_trial(self):
        # Past the boss run the game keeps going, and the boss must not linger:
        # it would keep applying and lock the trial display forever.
        def fake_choice(seq):
            return main.FinalBoss.SINGULARITY if seq == main.FinalBoss.ORDER \
                else seq[0]
        with mock.patch("main.random.choice", side_effect=fake_choice):
            for _ in range(main.TOTAL_RUNS - 1):
                self._complete_run(1000000, required=1)
                self.game._continue_run()
        self.assertEqual(self.game.final_boss, main.FinalBoss.SINGULARITY)
        self.game.trials_enabled = True
        self.game.continue_past_game_over = True  # the player keeps playing

        self._complete_run(1000000, required=1)
        self.game._continue_run()  # advance into the first endless run

        self.assertEqual(self.game.run_number, main.TOTAL_RUNS)
        self.assertIsNone(self.game.final_boss)
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.assertTrue(self.game.trial_options_available())

    def test_endless_play_trial_display_can_be_changed_and_disabled(self):
        # The two halves of the trial display work again once the boss run is
        # behind the player.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.game.trials_enabled = True
        self.game.continue_past_game_over = True
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.assertTrue(self.game.trial_options_available())

        self.game.cash = 1000
        was = self.game.current_trial
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(left))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertNotEqual(self.game.current_trial, was)

        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(right))
        self.assertEqual(self.game.cash,
                         1000 - main.TRIAL_CHANGE_COST - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)
        # And a trial can be bought back onto the endless run.
        self.assertTrue(self.game._click_trial_display(left))
        self.assertIn(self.game.current_trial, main.Trial.ORDER)

    def test_endless_singularity_stops_growing_the_marble(self):
        # A boss cleared before endless play no longer applies.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.game.final_boss = main.FinalBoss.SINGULARITY
        self.game.continue_past_game_over = True
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.assertIsNone(self.game.final_boss)

        marble = self._add_marble()
        self.game.run_active = True
        before = marble.mass
        for _ in range(60):
            self.game.update()
        self.assertEqual(marble.mass, before)

    def test_continuing_past_the_game_over_overlay_sets_up_the_next_run(self):
        # CONTINUE on the game-over screen resumes endless play with the next
        # run's own target and no boss (the run that ended there never got the
        # normal advance).
        self.game.run_number = main.TOTAL_RUNS
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.game.required_score = 12345
        self.game.game_over = True

        self._click(main.GAME_OVER_CONTINUE_BUTTON_RECT.center)

        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.continue_past_game_over)
        self.assertIsNone(self.game.final_boss)
        self.assertEqual(self.game.required_score,
                         main.get_next_required_score(main.TOTAL_RUNS))
        self.assertEqual(self.game.round_index,
                         main.TOTAL_RUNS // main.RUNS_PER_ROUND)
        self.assertEqual(self.game.run_in_round,
                         main.TOTAL_RUNS % main.RUNS_PER_ROUND)

    def test_a_loaded_endless_save_drops_a_stale_boss(self):
        # An old endless save that still carried a boss loads without it, while
        # a save made during the boss run keeps its boss.
        data = {"run_number": main.TOTAL_RUNS,
                "final_boss": int(main.FinalBoss.SINGULARITY)}
        fresh = main.Game()
        save_system._load_save_data(fresh, data, 1)
        self.assertIsNone(fresh.final_boss)

        boss_data = {"run_number": main.TOTAL_RUNS - 1,
                     "final_boss": int(main.FinalBoss.SKY_HIGH)}
        boss_save = main.Game()
        save_system._load_save_data(boss_save, boss_data, 1)
        self.assertEqual(boss_save.final_boss, main.FinalBoss.SKY_HIGH)

    def test_singularity_makes_marble_gain_mass_linearly(self):
        # The Singularity boss grows the marble's mass at a constant rate per
        # second, so it falls ever faster over the run.
        self.game.final_boss = main.FinalBoss.SINGULARITY
        marble = self._add_marble()
        self.game.run_active = True
        before = marble.mass
        for _ in range(60):  # 60 frames = 1 second at DT
            self.game.update()
        self.assertGreater(marble.mass, before)
        self.assertAlmostEqual(marble.mass, before + main.SINGULARITY_MASS_GROWTH, places=2)

    def test_mass_stays_constant_without_singularity(self):
        # Without the Singularity boss the marble's mass never changes.
        marble = self._add_marble()
        self.game.run_active = True
        for _ in range(60):
            self.game.update()
        self.assertEqual(marble.mass, main.MARBLE_MASS)

    def test_beating_final_boss_discovers_it_in_collection(self):
        # Clearing the 24th run reveals its final boss in the collection.
        self.game.final_boss = main.FinalBoss.SINGULARITY
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.game.marbles[0].finished = True
        self.game.required_score = 1
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(collection.is_final_boss_discovered(main.FinalBoss.SINGULARITY))
        self.assertTrue(any(p.title == "Final boss beaten" for p in self.game.popups))

    def test_final_bosses_appear_in_collection_entries(self):
        # Both bosses show up in the collection, hidden until beaten.
        entries = self.game._collection_entries()
        bosses = [e for e in entries if e[0] == "final_boss"]
        self.assertEqual(len(bosses), len(main.FinalBoss.ORDER))
        for kind, value, name, desc, has_icon, discovered in bosses:
            self.assertIn(value, main.FinalBoss.ORDER)
            self.assertEqual(name, "???")
            self.assertEqual(desc, "???")
            self.assertFalse(has_icon)
            self.assertFalse(discovered)

    def test_boss_run_dot_is_black_until_played(self):
        # The 24th run's dot is black instead of gray until it is played.
        self.game.run_results = []
        main.ui.draw_run_dots(self.game)
        cx, cy = self._run_dot_pixel(main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], main.BLACK)
        nx, ny = self._run_dot_pixel(0)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.GRAY)

    def test_boss_run_dot_is_gold_when_cleared_and_deep_red_when_lost(self):
        # Clearing the 24th run turns its dot gold; losing turns it deep red.
        self.game.run_results = [True] * main.TOTAL_RUNS
        main.ui.draw_run_dots(self.game)
        cx, cy = self._run_dot_pixel(main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], (255, 215, 0))
        nx, ny = self._run_dot_pixel(0)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.GREEN)

        self.game.run_results = [False] + [True] * (main.TOTAL_RUNS - 2) + [False]
        main.ui.draw_run_dots(self.game)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], (140, 0, 0))  # boss lost: deep red
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.RED)     # normal lost: red

    def test_boss_box_draws_title_and_description(self):
        # The trial box shows the final boss on the boss run without raising.
        self.game.final_boss = main.FinalBoss.SINGULARITY
        self.game.draw_trial_box()
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.game.draw_trial_box()
        self.game.final_boss = None
        self.game.current_trial = None
        self.game.draw_trial_box()  # nothing to draw

    def test_reset_run_blocked_while_awaiting_choice(self):
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertFalse(self.game.reset_run())

        self.assertTrue(self.game.run_complete)  # still waiting for the choice

    def test_every_component_has_a_price(self):
        components = [item for item in self.game.shop.items if item.kind != "block"]

        self.assertTrue(all(item.price > 0 for item in components))

    def test_block_price_is_75_percent_of_component_sum(self):
        # Every part is priced at the magnitude the block was built with, so a
        # block with a fast piston and a big +Chips scorer costs more than the
        # same block at the averages.
        block = next(item for item in self.game.shop.items if item.kind == "block")
        total = (main.COMPONENT_PRICES[(main.Component.SHAPE, block.shape)]
                 + sum(main.effect_component_price(e, block.effect_amounts.get(e))
                       for e in block.effects)
                 + main.scorer_component_price(block.scorer, block.scorer_amount))

        self.assertEqual(block.price, int(total * 0.75))

    def test_block_price_sums_all_effects(self):
        price = main.block_price_for(main.Shape.RECT,
                                     [main.Effect.BOUNCY, main.Effect.PISTON],
                                     main.Scorer.CHIPS_ADD)
        total = (main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.RECT)]
                 + main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.BOUNCY)]
                 + main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.PISTON)]
                 + main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CHIPS_ADD)])
        self.assertEqual(price, int(total * 0.75))

    def test_block_price_with_single_effect_matches_effect_component(self):
        price = main.block_price_for(main.Shape.RECT, [main.Effect.GRAVITY], main.Scorer.CHIPS_ADD)
        total = (main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.RECT)]
                 + main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.GRAVITY)]
                 + main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CHIPS_ADD)])
        self.assertEqual(price, int(total * 0.75))

    def test_buying_block_equips_and_placing_consumes_it(self):
        self.game.toolbox.items.clear()
        # Use a plain (non-portal) block so buying it adds exactly one copy.
        block_item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                    main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.cash = 1000
        self.game._buy_shop_item(block_item)
        self.assertIn(block_item, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_shape)  # not auto-equipped

        # Equip from the toolbox, then place it via a click.
        self.game._equip_block(block_item)
        self.assertTrue(self.game.has_selected)
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((1, 1), self.game.grid)
        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.shape, block_item.shape)
        self.assertEqual(placed.scorer, block_item.scorer)
        self.assertNotIn(block_item, self.game.toolbox.items)
        self.assertFalse(self.game.has_selected)

    def test_toolbox_starts_with_start_and_finish(self):
        items = list(self.game.toolbox.items)
        scorers = [item.scorer for item in items]

        self.assertEqual(len(items), 2)
        self.assertTrue(all(item.kind == "block" for item in items))
        self.assertIn(main.Scorer.START, scorers)
        self.assertIn(main.Scorer.FINISH, scorers)

    def test_toolbox_item_at_returns_owned_item(self):
        self.game.toolbox.items.clear()
        item = self.game.shop.items[0]
        self.game.toolbox.add(item)
        pos = (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5)

        self.assertIs(self.game.toolbox.item_at(pos), item)
        self.assertIsNone(self.game.toolbox.item_at((self.game.toolbox.rect.x - 10, self.game.toolbox.rect.y - 10)))

    def test_toolbox_is_full_cap(self):
        self.game.toolbox.items.clear()
        item = self.game.shop.items[0]
        for _ in range(self.game.toolbox.cols * self.game.toolbox.rows):
            self.assertTrue(self.game.toolbox.add(item))
        self.assertFalse(self.game.toolbox.add(item))

    def test_toolbox_component_assigns_to_assembler(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.LINE, 0, "Line")
        self.game.toolbox.add(shape_c)

        self.game._use_component(shape_c)

        self.assertIs(self.game.assembler.shape, shape_c)
        self.assertIn(shape_c, self.game.toolbox.items)  # stays in the toolbox
        self.assertFalse(self.game.has_selected)  # components can't be placed directly

    def test_assembler_combines_components_into_block(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.SLOPE, 0, "Slope")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.MULT_MUL, 2, 0, "xMult")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertTrue(self.game.has_selected)
        self.assertEqual(self.game.selected_shape, main.Shape.SLOPE)
        self.assertEqual(self.game.selected_effect, main.Effect.BOUNCY)
        self.assertEqual(self.game.selected_scorer, main.Scorer.MULT_MUL)
        self.assertEqual(self.game.selected_scorer_amount, 2)
        # Assigning a component keeps it in the toolbox; assembling consumes it.
        self.assertNotIn(shape_c, self.game.toolbox.items)
        self.assertNotIn(effect_c, self.game.toolbox.items)
        self.assertNotIn(scorer_c, self.game.toolbox.items)
        # The assembled block is added to the toolbox.
        blocks = [item for item in self.game.toolbox.items if item.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.SLOPE)
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)
        self.assertEqual(blocks[0].scorer, main.Scorer.MULT_MUL)

    def test_assembling_consumes_one_copy_and_keeps_leftover(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        self.game.toolbox.add(shape_c)
        self.game.toolbox.add(shape_c)  # two copies
        self.game.toolbox.add(effect_c)
        self.game.toolbox.add(scorer_c)
        for component in (shape_c, effect_c, scorer_c):
            self.game._use_component(component)

        self.game._assemble_block()

        # Assembly consumed one copy; the leftover duplicate survives.
        self.assertEqual(self.game.toolbox.items.count(shape_c), 1)
        self.assertNotIn(effect_c, self.game.toolbox.items)
        self.assertNotIn(scorer_c, self.game.toolbox.items)
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 1)

    def test_assembled_block_is_added_to_toolbox(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.FINISH, 0, 0, "Finish")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        # The three components were consumed when assembled; only the block remains.
        self.assertEqual(len(self.game.toolbox.items), 1)
        assembled = self.game.toolbox.items[0]
        self.assertEqual(assembled.kind, "block")
        self.assertEqual(assembled.scorer, main.Scorer.FINISH)

    def test_duplicate_component_reference_survives_assembly(self):
        # Two references to the SAME component object: assigning one and assembling
        # must not delete the other toolbox copy.
        self.game.toolbox.items.clear()
        eff = main.Component.effect_component(main.Effect.BOUNCY)
        shape = main.Component.shape_component(main.Shape.RECT)
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        self.game.toolbox.add(eff)
        self.game.toolbox.add(eff)  # same object twice
        self.game.toolbox.add(shape)
        self.game.toolbox.add(scorer)
        for component in (eff, shape, scorer):
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertEqual(self.game.toolbox.items.count(eff), 1)  # leftover copy survives
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 1)

    def test_distinct_duplicate_components_other_copy_survives(self):
        self.game.toolbox.items.clear()
        e1 = main.Component.effect_component(main.Effect.BOUNCY)
        e2 = main.Component.effect_component(main.Effect.BOUNCY)  # distinct object, same value
        shape = main.Component.shape_component(main.Shape.RECT)
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        for component in (e1, e2, shape, scorer):
            self.game.toolbox.add(component)
        for component in (e1, shape, scorer):
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertIn(e2, self.game.toolbox.items)  # the distinct duplicate survives
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 1)

    def test_buying_same_shop_item_twice_is_allowed(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        item = next(i for i in self.game.shop.items if i.kind == main.Component.EFFECT)

        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        second = self.game._buy_price(item)  # duplicates now cost more
        self.game._buy_shop_item(item)

        # Duplicate buys are allowed (the player may own several copies), but
        # the second copy is more expensive.
        self.assertEqual(self.game.toolbox.items.count(item), 2)
        self.assertGreater(second, first)
        self.assertEqual(self.game.cash, 1000 - first - second)

    def test_buying_duplicate_component_costs_more(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        # A fixed-magnitude piece: the shop rolls magnitudes now, and a cheap
        # roll's duplicate increments can round away at these prices.
        item = main.Component.scorer_component(main.Scorer.MULT_MUL, amount=2)

        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        price_second = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        price_third = self.game._buy_price(item)

        self.assertGreater(price_second, first)
        self.assertGreater(price_third, price_second)
        self.assertEqual(self.game.toolbox.items.count(item), 2)

    def test_component_price_increase_is_permanent_after_sale(self):
        # Once a component is bought, its price stays elevated even after the
        # copy leaves the toolbox: the increase is permanent (per-purchase),
        # not tied to how many copies are currently owned.
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        item = next(i for i in self.game.shop.items if i.kind == main.Component.EFFECT)
        base = item.price
        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        self.game.toolbox.items.remove(item)  # the copy is sold / used up
        after = self.game._buy_price(item)
        expected = int(base * (1 + main.DUPLICATE_PRICE_INCREMENT))  # sqrt(1) == 1
        self.assertEqual(after, expected)  # still elevated with the copy gone
        self.assertGreater(after, first)

    def test_buying_block_counts_toward_component_prices(self):
        # Buying a block also counts every component it contains, so the
        # component prices rise even though they weren't bought directly.
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        block = next(i for i in self.game.shop.items if getattr(i, "kind", None) == "block")
        self.assertIsNotNone(block)
        self.game._buy_shop_item(block)
        self.assertGreaterEqual(
            self.game.component_purchases.get((main.Component.SHAPE, block.shape), 0), 1)
        for e in block.effects:
            self.assertGreaterEqual(
                self.game.component_purchases.get((main.Component.EFFECT, e), 0), 1)
        self.assertGreaterEqual(
            self.game.component_purchases.get((main.Component.SCORER, block.scorer), 0), 1)

    def test_duplicate_price_increase_diminishes(self):
        # Each additional copy of the same component adds a smaller increment,
        # so the price keeps rising but more and more slowly (a square-root
        # curve, not linear). A higher-priced scorer keeps the increments
        # distinct after integer rounding.
        self.game.toolbox.items.clear()
        self.game.cash = 100000
        item = main.Component.scorer_component(main.Scorer.MULT_MUL, amount=2)  # base 25
        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        second = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        third = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        fourth = self.game._buy_price(item)
        self.assertGreater(second - first, third - second)
        self.assertGreater(third - second, fourth - third)
        self.assertGreater(fourth, third)

    def test_duplicate_pricing_does_not_affect_rarity(self):
        item = next(i for i in self.game.shop.items if i.kind == main.Component.EFFECT)
        before = main.component_weight(item.kind, item.value)
        self.game.cash = 1000
        self.game._buy_shop_item(item)
        self.game._buy_shop_item(item)
        # Rarity is based only on the base price, never on how many you own.
        self.assertEqual(main.component_weight(item.kind, item.value), before)

    def test_trigger_upgrade_cost_is_the_scorers_shop_price_plus_ten_percent(self):
        # The upgrade is priced off the block's SCORER, not the whole block:
        # 10% more than the shop would charge for that scorer component now.
        cheap = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 10, "cheap")
        chips = main.BlockItem(0, 0, main.Shape.CURVED_SLOPE, main.Effect.PORTAL,
                              main.Scorer.CHIPS_ADD, 0, 100, "chips")
        component = main.Component.scorer_component(main.Scorer.CHIPS_ADD)
        expected = int(self.game._buy_price(component) * main.TRIGGER_UPGRADE_MARKUP)

        self.assertEqual(self.game._trigger_upgrade_cost(chips), expected)
        self.assertEqual(self.game._trigger_upgrade_cost(cheap),
                         int(self.game._buy_price(
                             main.Component.scorer_component(main.Scorer.NONE))
                             * main.TRIGGER_UPGRADE_MARKUP))
        # The block's own shape/effects/price no longer matter at all.
        plain_shape = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                     main.Scorer.CHIPS_ADD, 0, 10, "plain")
        self.assertEqual(self.game._trigger_upgrade_cost(plain_shape), expected)

    def test_upgrading_a_trigger_counts_as_buying_the_scorers_component(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 50, "Rect +Chips")
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 1000
        # The upgrade is priced off the block's OWN scorer magnitude, so the
        # comparison piece must carry the same amount (a +Chips block with 10
        # chips is priced as the 10-chip scorer component).
        component = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        before_price = self.game._buy_price(component)
        before_cost = self.game._trigger_upgrade_cost(block)

        self.game._upgrade_trigger_limit()

        # The scorer's shop price rose exactly as if it had been bought.
        self.assertEqual(self.game.component_purchases
                         [(main.Component.SCORER, main.Scorer.CHIPS_ADD)], 1)
        self.assertGreater(self.game._buy_price(component), before_price)
        # ...and so did the next upgrade (10% over the new price).
        after_price = self.game._buy_price(component)
        self.assertEqual(self.game._trigger_upgrade_cost(block),
                         int(after_price * main.TRIGGER_UPGRADE_MARKUP))
        self.assertGreater(self.game._trigger_upgrade_cost(block), before_cost)

    # --- Magnitudes: every scaleable value rolls around its average -------

    def test_magnitude_step_is_a_tenth_of_the_average(self):
        # A step is EXACTLY 10% of the average, never rounded to a whole number
        # (rounding 0.4 up to a whole 1 would stretch a +Mult scorer's spread
        # to 12 instead of 7.2).
        self.assertEqual(main.magnitude_step(30), 3)
        self.assertEqual(main.magnitude_step(1500), 150)
        self.assertEqual(main.magnitude_step(20000), 2000)
        self.assertEqual(main.magnitude_step(120), 12)
        self.assertEqual(main.magnitude_step(4), 0.4)    # not a whole 1
        self.assertEqual(main.magnitude_step(15), 1.5)   # not 2
        self.assertEqual(main.magnitude_step(8), 0.8)
        self.assertEqual(main.magnitude_step(2), 0.2)
        self.assertAlmostEqual(main.magnitude_step(1.5), 0.15)
        self.assertAlmostEqual(main.magnitude_step(0.75), 0.075)
        self.assertAlmostEqual(main.magnitude_step(0.4), 0.04)
        self.assertEqual(main.magnitude_step(0), 0)      # no average, no magnitude

    def test_rolled_magnitudes_are_not_rounded(self):
        # A roll is the exact average +/- 10% steps, so a small-average scorer
        # lands on fractional magnitudes instead of snapping to whole numbers.
        for scorer in (main.Scorer.MULT_ADD, main.Scorer.SUMMIT,
                       main.Scorer.AIRBALL, main.Scorer.DRILL):
            average = main.Scorer.DEFAULT_AMOUNT[scorer]
            step = main.magnitude_step(average)
            rolls = [main.roll_scorer_amount(scorer) for _ in range(200)]
            fractional = [r for r in rolls if not float(r).is_integer()]
            self.assertTrue(fractional, main.Scorer.name(scorer))
            for amount in rolls:
                # On the step grid, and free of arithmetic noise.
                self.assertAlmostEqual((amount - average) / step,
                                       round((amount - average) / step), places=6)
                self.assertEqual(amount, round(amount, 9))
        # A whole average with a whole step still lands on whole values (the
        # arithmetic stays exact rather than noisy).
        for _ in range(100):
            amount = main.roll_scorer_amount(main.Scorer.CHIPS_ADD)
            self.assertTrue(float(amount).is_integer())
            self.assertEqual(amount % 3, 0)
        # A drill counts whole squares even though its magnitude is fractional.
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.DRILL), 0.2)

    def test_magnitude_floors_keep_a_roll_useful(self):
        # A multiplier never rolls below 1 (a factor under 1 would make the
        # block a penalty); every other magnitude never rolls below one step.
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.MULT_MUL), 1.0)
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.SHARP), 1.0)
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.CHIPS_ADD), 3)
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.NONE), 0)
        self.assertEqual(main.effect_magnitude_floor(main.Effect.PISTON), 150)

    def test_rolls_never_leave_the_allowed_range(self):
        scorers = [main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD, main.Scorer.MULT_MUL,
                   main.Scorer.SHARP, main.Scorer.SUMMIT, main.Scorer.COLOSSUS,
                   main.Scorer.PARTS, main.Scorer.SATANIC]
        for scorer in scorers:
            with self.subTest(scorer=main.Scorer.name(scorer)):
                average = main.Scorer.DEFAULT_AMOUNT[scorer]
                step = main.magnitude_step(average)
                floor = main.scorer_magnitude_floor(scorer)
                for _ in range(500):
                    amount = main.roll_scorer_amount(scorer)
                    self.assertGreaterEqual(amount, floor)
                    self.assertLessEqual(amount, average + step * main.MAGNITUDE_MAX_STEPS)
                    # Every roll lands on a step (except where the floor clamps
                    # it, which is the floor's whole job).
                    if amount == floor:
                        continue
                    self.assertAlmostEqual((amount - average) / step,
                                          round((amount - average) / step))
        # A scorer with no magnitude is left exactly alone.
        for scorer in (main.Scorer.NONE, main.Scorer.START, main.Scorer.LUCKY):
            self.assertEqual(main.roll_scorer_amount(scorer), 0)
        # An on/off effect has nothing to roll.
        self.assertEqual(main.roll_effect_magnitude(main.Effect.FRAGILE), 0)
        self.assertEqual(main.roll_effect_amounts([main.Effect.FRAGILE]), {})

    def test_rolls_follow_the_inverse_square_distribution(self):
        # P(x) is proportional to 1/(x^2 + 1), so the average is about a third
        # of rolls, one step off about a sixth, and two steps off about a
        # sixteenth. Sampled generously so the tolerance never flakes.
        samples = 30000
        average, step = 30, 3
        counts = {}
        for _ in range(samples):
            x = round((main.roll_magnitude(average) - average) / step)
            counts[x] = counts.get(x, 0) + 1
        total = sum(counts.values())
        norm = sum(1.0 / (x * x + 1) for x in range(-main.MAGNITUDE_MAX_STEPS,
                                                    main.MAGNITUDE_MAX_STEPS + 1))
        for x in (0, 1, -1, 2, -2, 3):
            expected = (1.0 / (x * x + 1)) / norm
            self.assertAlmostEqual(counts.get(x, 0) / total, expected, delta=0.015)
        # The shape of the curve: nearer the average is always likelier.
        self.assertGreater(counts[0], counts[1])
        self.assertGreater(counts[1], counts[2])
        self.assertAlmostEqual(counts[1] / counts[2], 2.5, delta=0.35)  # (2^2+1)/(1^2+1)
        # Every deviation stays inside the cap.
        self.assertTrue(all(abs(x) <= main.MAGNITUDE_MAX_STEPS for x in counts))

    def test_scorer_descriptions_state_the_deviation_inline(self):
        # The deviation sits right after the magnitude it belongs to, as a bare
        # signed token — "Adds +6 mult (+2) when touched" — which the sidebar
        # colours green/red/grey. No trailing "above the average" sentence.
        above = main.scorer_description(main.Scorer.CHIPS_ADD, 33)
        self.assertEqual(above, "Adds 33 chips (+3) when touched")
        below = main.scorer_description(main.Scorer.MULT_ADD, 3)
        self.assertEqual(below, "Adds +3 mult (-1) when touched")
        even = main.scorer_description(main.Scorer.CHIPS_ADD, 30)
        self.assertEqual(even, "Adds 30 chips (0) when touched")
        for text in (above, below, even):
            self.assertNotIn("average", text)
        # A scorer with no magnitude never mentions a deviation.
        deviation = re.compile(r"\([+-]?\d+(\.\d+)?\)")
        for scorer in (main.Scorer.LUCKY, main.Scorer.START, main.Scorer.QUICK):
            self.assertIsNone(deviation.search(main.scorer_description(scorer)),
                              f"{main.Scorer.name(scorer)} has no magnitude")
        # A rolled xMult reads its own factor.
        self.assertIn("by 4 (+1)", main.scorer_description(main.Scorer.SHARP, 4))
        self.assertIn("(+1)", main.scorer_description(main.Scorer.EFFECTIVE, 3))
        # The amount-dependent scorers all follow their own magnitude.
        self.assertIn("Gives 2 components (+1)", main.scorer_description(main.Scorer.PARTS, 2))
        self.assertIn("Gives 1 component (0)", main.scorer_description(main.Scorer.PARTS, 1))
        self.assertIn("drills out 3 locked board squares (+1)",
                      main.scorer_description(main.Scorer.DRILL, 3))

    def test_effect_descriptions_state_the_deviation_inline(self):
        # An effect states its own magnitude in the text, with the deviation
        # right after it.
        strong = main.effect_description(main.Effect.PISTON, 1800)
        self.assertEqual(strong,
                         "Launches marbles at 1800 px/s along its surface (+300).")
        weak = main.effect_description(main.Effect.PISTON, 900)
        self.assertIn("900 px/s along its surface (-600).", weak)
        average = main.effect_description(main.Effect.BLACK_HOLE)
        self.assertIn("3000 px/s^2 of gravity (0)", average)
        # An on/off effect has no magnitude to report.
        self.assertNotIn("average", main.effect_description(main.Effect.FRAGILE))
        self.assertEqual(main.effect_description(main.Effect.FRAGILE),
                         "Shatters into a no-hitbox field after a marble touches it and leaves.")

    def test_shop_effect_pieces_always_carry_a_real_magnitude(self):
        # Regression: the shop's two effect slots used to build their piece
        # without a roll, so a scaleable effect arrived with magnitude 0 and the
        # sidebar read "0 px/s^2, 3000 below the 3000 px/s^2 average" — a
        # zero-strength repulsor, which no roll can produce (the weakest roll is
        # 8 steps below the average).
        for _ in range(40):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind != main.Component.EFFECT:
                    continue
                if item.value not in main.Effect.MAGNITUDE:
                    self.assertEqual(item.effect_magnitude, 0)  # an on/off effect
                    continue
                average = main.Effect.MAGNITUDE[item.value]
                step = main.magnitude_step(average)
                magnitude = item.effect_magnitude
                self.assertGreaterEqual(magnitude, main.effect_magnitude_floor(item.value))
                self.assertLessEqual(magnitude, average + step * main.MAGNITUDE_MAX_STEPS)
                if magnitude != main.effect_magnitude_floor(item.value):
                    self.assertAlmostEqual((magnitude - average) / step,
                                          round((magnitude - average) / step))
                self.assertEqual(item.price,
                                 main.effect_component_price(item.value, magnitude))
                # ...and the sidebar never claims a zero strength.
                text = dict(self.game._describe_item(item))["Effect - "
                                                            f"{main.Effect.name(item.value)}"]
                self.assertNotIn(" 0 px/s", text)  # the bug read "0 px/s^2, 3000 below"
        # A repulsor rolled over and over never comes out at 0.
        seen = {main.roll_effect_magnitude(main.Effect.REPULSOR) for _ in range(3000)}
        self.assertNotIn(0, seen)
        self.assertGreaterEqual(min(seen), main.effect_magnitude_floor(main.Effect.REPULSOR))

    def test_an_unrolled_effect_piece_reads_the_average_not_zero(self):
        # A piece built without a magnitude (an old save, or code that predates
        # the roll) is the average-strength piece, and says so.
        piece = main.Component.effect_component(main.Effect.REPULSOR)
        self.assertEqual(piece.effect_magnitude, main.BLACK_HOLE_FORCE)
        rows = dict(self.game._describe_item(piece))
        self.assertIn("3000 px/s^2 of force (0)", rows["Effect - Repulsor"])
        self.assertNotIn(" 0 px/s", rows["Effect - Repulsor"])
        self.assertNotIn(" 0 px/s", main.effect_description(main.Effect.REPULSOR, 0))
        self.assertIn("3000 px/s^2 of force (0)",
                      main.effect_description(main.Effect.REPULSOR, 0))
        # A stored 0 can never shadow the average on a block either.
        block = main.Block(0, 0, effect=main.Effect.REPULSOR,
                           effects=[main.Effect.REPULSOR],
                           effect_amounts={main.Effect.REPULSOR: 0})
        self.assertEqual(block.effect_magnitude(main.Effect.REPULSOR),
                         main.BLACK_HOLE_FORCE)
        # An on/off effect is still zero, and states no magnitude at all.
        fragile = main.Component.effect_component(main.Effect.FRAGILE)
        self.assertEqual(fragile.effect_magnitude, 0)
        self.assertNotIn("(", main.effect_description(main.Effect.FRAGILE, 0))

    def test_disassembling_a_block_hands_back_its_own_magnitudes(self):
        # The pieces you get back are the ones the block was made of: a block
        # holding a 2100 px/s piston gives back a 2100 px/s piston piece.
        self.game.cash = 1000
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 45, 99, "Rect +Chips",
                               effects=[main.Effect.PISTON],
                               effect_amounts={main.Effect.PISTON: 2100})
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block

        self.game._disassemble_block()

        piston = next(i for i in self.game.toolbox.items
                      if getattr(i, "kind", None) == main.Component.EFFECT)
        self.assertEqual(piston.value, main.Effect.PISTON)
        self.assertEqual(piston.effect_magnitude, 2100)
        self.assertEqual(piston.price, main.effect_component_price(main.Effect.PISTON, 2100))
        scorer = next(i for i in self.game.toolbox.items
                      if getattr(i, "kind", None) == main.Component.SCORER)
        self.assertEqual(scorer.amount, 45)  # the scorer keeps its amount too

    def test_component_prices_follow_the_magnitude(self):
        # A piece is priced proportionally to its own magnitude: a strong one
        # costs more, a weak one less, and the average pays the table price.
        chips = main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CHIPS_ADD)]
        self.assertEqual(main.scorer_component_price(main.Scorer.CHIPS_ADD, 30), chips)
        self.assertGreater(main.scorer_component_price(main.Scorer.CHIPS_ADD, 45), chips)
        self.assertLess(main.scorer_component_price(main.Scorer.CHIPS_ADD, 15), chips)
        self.assertEqual(main.scorer_component_price(main.Scorer.CHIPS_ADD, 45),
                         round(chips * 1.5))
        # A scorer with no magnitude is never scaled (roles stay $109/$53).
        self.assertEqual(main.scorer_component_price(main.Scorer.START, 0), 140)
        piston = main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.PISTON)]
        self.assertEqual(main.effect_component_price(main.Effect.PISTON, 1500), piston)
        self.assertGreater(main.effect_component_price(main.Effect.PISTON, 1800), piston)
        self.assertEqual(main.effect_component_price(main.Effect.FRAGILE, None),
                         main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.FRAGILE)])

    def test_block_price_uses_each_parts_own_magnitude(self):
        average = main.block_price_for(main.Shape.RECT, [main.Effect.PISTON],
                                       main.Scorer.CHIPS_ADD)
        strong = main.block_price_for(main.Shape.RECT, [main.Effect.PISTON],
                                      main.Scorer.CHIPS_ADD, 45,
                                      {main.Effect.PISTON: 1800})
        weak = main.block_price_for(main.Shape.RECT, [main.Effect.PISTON],
                                    main.Scorer.CHIPS_ADD, 15,
                                    {main.Effect.PISTON: 900})
        self.assertGreater(strong, average)
        self.assertLess(weak, average)
        # A role block is never scaled: it is the same good wherever it came from.
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.START), 109)
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.FINISH), 53)

    def test_a_bought_block_keeps_its_own_effects_and_scorer(self):
        # A shop block's components carry their own rolled magnitudes, and the
        # block keeps them when it is bought, placed, erased and returned.
        block = next(i for i in self.game.shop.items if i.kind == "block")
        amount = block.scorer_amount
        amounts = dict(block.effect_amounts)
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        self.game._buy_shop_item(block)
        self.game._equip_block(block)
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=self._grid_pos(3, 3)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        placed = self.game.grid[(3, 3)]
        self.assertEqual(placed.scorer_amount, amount)
        for e, magnitude in amounts.items():
            self.assertEqual(placed.effect_magnitude(e), magnitude)
        # Erasing it hands the same block (and the same magnitudes) back, at
        # the price it came in with.
        self.game._erase_block_at(3, 3)
        returned = next(i for i in self.game.toolbox.items
                        if getattr(i, "kind", None) == "block")
        self.assertEqual(returned.scorer_amount, amount)
        self.assertEqual(returned.effect_amounts, amounts)
        self.assertEqual(returned.price, block.price)

    def test_assembling_keeps_the_effects_own_magnitude(self):
        # The effect piece's rolled strength travels onto the assembled block.
        self.game.toolbox.items.clear()
        effect = main.Component.effect_component(main.Effect.PISTON, magnitude=1800)
        self.game.toolbox.add(effect)
        self.game._use_component(effect)

        self.game._assemble_block()

        block = next(i for i in self.game.toolbox.items if i.kind == "block")
        self.assertEqual(block.effect_magnitude(main.Effect.PISTON), 1800)
        self.assertEqual(block.price, int(main.effect_component_price(
            main.Effect.PISTON, 1800) * 0.75))

    def test_anointment_rolls_a_magnitude_for_each_new_effect(self):
        random.seed(99)
        action = main.ActionItem(main.Action.ANOINTMENT, 32)
        scalable = []
        # Anointment hands out random effects, so bless several blocks to be
        # sure some of them are scaleable ones.
        for i in range(8):
            block = main.BlockItem(0, i, main.Shape.RECT, main.Effect.NONE,
                                   main.Scorer.CHIPS_ADD, 30, 20, "Rect +Chips",
                                   effects=[])
            self.game.toolbox.items.append(block)
            self.game._action_anointment(action, block)
            scalable += [e for e in block.effects if e in main.Effect.MAGNITUDE]

        self.assertTrue(scalable)
        for block in self.game.toolbox.items:
            for e in block.effects:
                if e not in main.Effect.MAGNITUDE:
                    self.assertNotIn(e, block.effect_amounts)
                    continue
                # Each blessed effect carries its own roll, on the step grid.
                magnitude = block.effect_amounts[e]
                average = main.Effect.MAGNITUDE[e]
                step = main.magnitude_step(average)
                if magnitude != main.effect_magnitude_floor(e):
                    self.assertAlmostEqual((magnitude - average) / step,
                                          round((magnitude - average) / step))
                self.assertLessEqual(magnitude, average + step * main.MAGNITUDE_MAX_STEPS)

    def test_parts_and_rubble_grants_roll_magnitudes(self):
        # The reward paths roll magnitudes exactly like the shop does, so a
        # granted piece is never a flat average and always stays on the grid.
        random.seed(4242)
        amounts = set()
        self.game.toolbox.items.clear()
        for _ in range(80):
            self.game._grant_random_component()
        for item in self.game.toolbox.items:
            if getattr(item, "kind", None) != main.Component.SCORER:
                continue
            step = main.magnitude_step(main.Scorer.DEFAULT_AMOUNT[item.value])
            if not step:
                continue
            amounts.add(item.amount)
            self.assertGreaterEqual(item.amount,
                                    main.scorer_magnitude_floor(item.value))
            self.assertLessEqual(item.amount,
                                 main.Scorer.DEFAULT_AMOUNT[item.value]
                                 + step * main.MAGNITUDE_MAX_STEPS)
            self.assertEqual(item.price,
                             main.scorer_component_price(item.value, item.amount))
        self.assertGreater(len(amounts), 1)  # 80 grants never all roll alike

        # A Rubble block carries a magnitude for each scaleable effect.
        self.game.toolbox.items.clear()
        self.game._grant_random_block()
        granted = self.game.toolbox.items[-1]
        for e in granted.effects:
            if e in main.Effect.MAGNITUDE:
                magnitude = granted.effect_amounts[e]
                self.assertGreaterEqual(magnitude, main.effect_magnitude_floor(e))
                self.assertLessEqual(magnitude,
                                     main.Effect.MAGNITUDE[e]
                                     + main.magnitude_step(main.Effect.MAGNITUDE[e])
                                     * main.MAGNITUDE_MAX_STEPS)

    def test_effect_magnitudes_round_trip_through_a_save(self):
        self.game.cash = 100
        placed = main.Block(2, 2, shape=main.Shape.RECT,
                            effects=[main.Effect.PISTON],
                            effect_amounts={main.Effect.PISTON: 1800},
                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=45)
        self.game.grid[(2, 2)] = placed
        self.game.shop.items.clear()
        self.game.shop.items.append(main.BlockItem(
            0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD, 45, 99,
            "Rect +Chips", effects=[main.Effect.BLACK_HOLE],
            effect_amounts={main.Effect.BLACK_HOLE: 3900}))

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(save_system, "SAVES_DIR",
                                  os.path.join(tmp, "saves")):
            save_system.save_game(self.game)
            fresh = main.Game()
            fresh.save_slot = self.game.save_slot
            save_system.load_slot(fresh, self.game.save_slot)

        restored = fresh.grid[(2, 2)]
        self.assertEqual(restored.effect_magnitude(main.Effect.PISTON), 1800)
        self.assertEqual(restored.scorer_amount, 45)
        offer = next(i for i in fresh.shop.items if getattr(i, "kind", None) == "block")
        self.assertEqual(offer.effect_magnitude(main.Effect.BLACK_HOLE), 3900)
        self.assertEqual(offer.scorer_amount, 45)

    def test_an_old_save_without_magnitudes_reads_the_averages(self):
        # A save made before magnitudes existed has no effect_amounts key: its
        # blocks come back at the averages (exactly what they used to be).
        data = {"kind": "block", "placed": True, "x": 1, "y": 1,
                "shape": main.Shape.RECT, "effects": [main.Effect.PISTON],
                "scorer": main.Scorer.CHIPS_ADD, "scorer_amount": 30}
        block = save_system._deserialize_item(data)
        self.assertEqual(block.effect_amounts, {})
        self.assertEqual(block.effect_magnitude(main.Effect.PISTON), 1500)
        item = save_system._deserialize_item(
            {"kind": "block", "placed": False, "col": 0, "row": 0,
             "shape": main.Shape.RECT, "effects": [main.Effect.BOUNCY],
             "scorer": main.Scorer.CHIPS_ADD, "scorer_amount": 30, "price": 10})
        self.assertEqual(item.effect_magnitude(main.Effect.BOUNCY), 100)

    def test_the_info_box_reports_each_items_own_magnitude(self):
        # The sidebar (the game's only way to read a magnitude) names it for
        # both a placed block and a toolbox piece.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           effects=[main.Effect.PISTON],
                           effect_amounts={main.Effect.PISTON: 1800},
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=45)
        rows = dict(self.game._describe_item(block))
        self.assertIn("1800 px/s along its surface (+300)", rows["Effect - Piston"])
        self.assertIn("Adds 45 chips (+15)", rows["Scorer - +Chips"])
        piece = main.Component.effect_component(main.Effect.PISTON, magnitude=1800)
        rows = dict(self.game._describe_item(piece))
        self.assertIn("1800 px/s along its surface (+300)", rows["Effect - Piston"])

    def test_upgrade_cost_follows_the_inflation_trial_and_the_coupon_card(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 50, "Rect +Chips")
        base = self.game._trigger_upgrade_cost(block)

        self.game.cards.append(main.CardItem(main.Card.COUPON, 46))
        with_coupon = self.game._trigger_upgrade_cost(block)
        self.assertLess(with_coupon, base)  # Coupon discounts it like any buy

        self.game.cards.clear()
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.INFLATION
        self.assertGreater(self.game._trigger_upgrade_cost(block), base)
        self.game.current_trial = None

    # --- Tesseract: a permanent xMult bonus per shop reroll ---------------

    def test_tesseract_gains_xmult_for_every_reroll_while_owned(self):
        self.game.cash = 1000
        self.game.cards.append(main.CardItem(main.Card.TESSERACT, 44))
        self.assertEqual(self.game.tesseract_bonus, 1.0)

        self.game._refresh_shop()

        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + main.TESSERACT_REROLL_XMULT)
        self.assertIn("Tesseract", self.game.shop_message)
        # A paid reroll and a banked (Fresh) free reroll both count.
        self.game.free_rerolls = 1
        self.game._refresh_shop()
        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + 2 * main.TESSERACT_REROLL_XMULT)

    def test_tesseract_only_grows_while_the_card_is_owned(self):
        self.game.cash = 1000
        self.game._refresh_shop()  # no Tesseract

        self.assertEqual(self.game.tesseract_bonus, 1.0)
        self.assertNotIn("Tesseract", self.game.shop_message)

    def test_tesseract_bonus_applies_at_the_start_of_a_run(self):
        self.game.cards.append(main.CardItem(main.Card.TESSERACT, 44))
        self.game.tesseract_bonus = 1.5
        self.game.score_mult = 2.0

        self.game._apply_cards()

        self.assertAlmostEqual(self.game.score_mult, 3.0)

    def test_tesseract_bonus_does_nothing_without_the_card(self):
        self.game.tesseract_bonus = 1.5
        self.game.score_mult = 2.0

        self.game._apply_cards()

        self.assertEqual(self.game.score_mult, 2.0)

    # --- Synthesizer: a start-of-run payoff scaled by your cards ----------

    def test_synthesizer_metadata_and_units(self):
        self.assertEqual(main.Condition.name(main.Condition.SYNTHESIZER),
                         "Synthesizer")
        self.assertEqual(main.condition_phase(main.Condition.SYNTHESIZER), "start")
        self.assertAlmostEqual(components.condition_ratio(main.Condition.SYNTHESIZER), 0.75)
        self.assertEqual(main.CONDITION_ORDER.count(main.Condition.SYNTHESIZER), 1)
        self.assertIn("for each card in your card area",
                      main.condition_description(main.Condition.SYNTHESIZER))
        self.assertEqual(main.cards._condition_units(
            self.game, main.Condition.SYNTHESIZER), 0)

        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 48))
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.assertEqual(main.cards._condition_units(
            self.game, main.Condition.SYNTHESIZER), 2)

    def test_synthesizer_card_pays_three_mult_per_card_owned(self):
        # Two other cards plus the Synthesizer card itself = 3 cards, and the
        # condition's 3/4 ratio makes the +Mult payoff exactly +3 mult a card.
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 48))
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        value = main.condition_scorer_card(main.Condition.SYNTHESIZER,
                                           main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertEqual(self.game.score_mult, 1 + 9)

    # --- 1000-handed: a random action after every run --------------------

    def test_thousand_handed_grants_a_random_action_after_every_run(self):
        self.game.cards.append(main.CardItem(main.Card.THOUSAND_HANDED, 42))
        self.game.actions.clear()
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(len(self.game.actions), 1)
        self.assertIn(self.game.actions[0].value, main.Action.ORDER)
        self.assertIn("1000-handed", self.game.shop_message)

    def test_no_1000_handed_means_no_free_action_after_a_run(self):
        self.game.actions.clear()
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(self.game.actions, [])

    def test_thousand_handed_withholds_the_action_when_the_area_is_full(self):
        self.game.cards.append(main.CardItem(main.Card.THOUSAND_HANDED, 42))
        self.game.actions = [main.ActionItem(main.Action.DEATH, 48),
                             main.ActionItem(main.Action.RECOGNITION, 48)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(len(self.game.actions), main.MAX_ACTIONS)

    # --- Deja Vu: an action that grants trigger-limit upgrades ------------

    def test_deja_vu_gives_a_block_one_extra_trigger(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEJA_VU, 56)

        self.assertTrue(self.game._action_deja_vu(action, block))

        self.assertEqual(block.trigger_limit, 2)
        # The action is free once bought: no cash is tracked as refundable.
        self.assertEqual(block.trigger_paid, 0)

    def test_v2_deja_vu_gives_a_hundred_triggers(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEJA_VU, 56, version=2)

        self.assertTrue(self.game._action_deja_vu(action, block))

        self.assertEqual(block.trigger_limit, 101)

    def test_deja_vu_revives_a_spent_block_on_the_board(self):
        placed = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(3, 3)] = placed
        placed.triggers_left = 0
        action = main.ActionItem(main.Action.DEJA_VU, 56)

        self.assertTrue(self.game._action_deja_vu(action, placed))

        self.assertEqual(placed.trigger_limit, 2)
        self.assertEqual(placed.triggers_left, 1)  # usable again this run

    def test_deja_vu_upgrades_both_halves_of_a_portal_pair(self):
        number = main.next_portal_number()
        placed = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD, portal_number=number,
                            effects=[main.Effect.PORTAL])
        partner = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                 main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips",
                                 portal_number=number, effects=[main.Effect.PORTAL])
        self.game.grid[(3, 3)] = placed
        self.game.toolbox.add(partner)
        action = main.ActionItem(main.Action.DEJA_VU, 56)

        self.assertTrue(self.game._action_deja_vu(action, placed))

        self.assertEqual(placed.trigger_limit, 2)
        self.assertEqual(partner.trigger_limit, 2)

    def test_deja_vu_refuses_blocks_that_never_spend_a_trigger(self):
        action = main.ActionItem(main.Action.DEJA_VU, 56)
        start = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = start
        plain = main.Block(4, 3, scorer=main.Scorer.NONE)
        self.game.grid[(4, 3)] = plain
        card = main.CardItem(main.Card.GARDEN, 36)

        self.assertFalse(self.game._action_deja_vu(action, start))
        self.assertFalse(self.game._action_deja_vu(action, plain))
        self.assertFalse(self.game._action_deja_vu(action, card))

        self.assertEqual(start.trigger_limit, 1)
        self.assertEqual(plain.trigger_limit, 1)

    def test_applying_deja_vu_consumes_the_action(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEJA_VU, 56)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.game.cash = 100

        self.assertTrue(self.game._apply_action())

        self.assertEqual(block.trigger_limit, 2)
        self.assertNotIn(action, self.game.actions)
        self.assertEqual(self.game.cash, 100)  # the action was already bought

    # --- Anointment: random effects ---------------------------------------

    def test_anointment_gives_two_random_effects_and_reprices_the_block(self):
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 20, "Circle +Chips",
                               effects=[])
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.ANOINTMENT, 32)

        self.assertTrue(self.game._action_anointment(action, block))

        self.assertEqual(len(block.effects), 2)
        self.assertEqual(len(set(block.effects)), 2)
        self.assertNotIn(main.Effect.PORTAL, block.effects)
        # The two new effects are paid for in the block's price, so a sale,
        # Death and Painting all see the block's real worth — at the magnitude
        # each new effect was rolled with.
        added = sum(main.effect_component_price(e, block.effect_amounts.get(e))
                    for e in block.effects)
        self.assertEqual(block.price, 20 + added)

    def test_anointment_never_hands_out_a_lone_portal(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 20, "b", effects=[])
        self.game.toolbox.add(block)
        for _ in range(40):
            for effect in self.game._random_new_effects(block, 2):
                self.assertNotEqual(effect, main.Effect.PORTAL)

    def test_anointment_v2_blesses_every_block_on_the_board_and_in_the_inventory(self):
        board = main.Block(2, 2, shape=main.Shape.RECT, scorer=main.Scorer.MULT_ADD,
                           effects=[])
        self.game.grid[(2, 2)] = board
        owned = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CASH, 15, 20, "b", effects=[])
        self.game.toolbox.add(owned)
        action = main.ActionItem(main.Action.ANOINTMENT, 32, version=2)

        self.assertTrue(self.game._action_anointment(action, owned))

        self.assertEqual(len(board.effects), 1)
        self.assertEqual(len(owned.effects), 1)

    def test_anointment_refuses_role_blocks_and_cards(self):
        action = main.ActionItem(main.Action.ANOINTMENT, 32)
        start = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = start

        self.assertFalse(self.game._action_anointment(action, start))
        self.assertFalse(self.game._action_anointment(
            action, main.CardItem(main.Card.GARDEN, 36)))
        self.assertEqual(start.effects, [main.Effect.NONE])

    # --- Strength: scorer amounts -----------------------------------------

    def test_strength_raises_whole_amounts_by_half_and_then_triples(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 20, "b", effects=[])
        self.game.toolbox.add(block)

        self.assertTrue(self.game._action_strength(
            main.ActionItem(main.Action.STRENGTH, 28), block))
        self.assertEqual(block.scorer_amount, 45)  # +50%

        self.assertTrue(self.game._action_strength(
            main.ActionItem(main.Action.STRENGTH, 28, version=2), block))
        self.assertEqual(block.scorer_amount, 135)  # tripled

    def test_strength_keeps_fractional_amounts_fractional(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.MULT_MUL, 1.5, 20, "b", effects=[])
        self.game.toolbox.add(block)

        self.game._action_strength(main.ActionItem(main.Action.STRENGTH, 28), block)

        self.assertAlmostEqual(block.scorer_amount, 2.25)

    def test_strength_refuses_blocks_with_nothing_to_strengthen(self):
        action = main.ActionItem(main.Action.STRENGTH, 28)
        plain = main.Block(3, 3, scorer=main.Scorer.NONE)
        start = main.Block(4, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = plain
        self.game.grid[(4, 3)] = start

        self.assertFalse(self.game._action_strength(action, plain))
        self.assertFalse(self.game._action_strength(action, start))
        self.assertFalse(self.game._action_strength(
            action, main.CardItem(main.Card.GARDEN, 36)))
        self.assertEqual(start.scorer_amount, 0)

    # --- Spirit: tokens that keep a scorer firing -------------------------

    def test_spirit_destroys_the_block_and_keeps_its_scorer_as_a_token(self):
        block = main.Block(3, 4, shape=main.Shape.RECT, scorer=main.Scorer.MULT_ADD,
                           scorer_amount=4, effects=[main.Effect.BOUNCY])
        self.game.grid[(3, 4)] = block
        action = main.ActionItem(main.Action.SPIRIT, 36)
        cash_before = self.game.cash

        self.assertTrue(self.game._action_spirit(action, block))

        self.assertNotIn((3, 4), self.game.grid)
        self.assertEqual(len(self.game.tokens), 1)
        token = self.game.tokens[0]
        self.assertEqual(token.scorer, main.Scorer.MULT_ADD)
        self.assertEqual(token.scorer_amount, 4)
        self.assertEqual(token.runs_left, 2)
        self.assertEqual((token.x, token.y), (3, 4))  # the cell it stood in
        self.assertEqual(token.effects, [main.Effect.BOUNCY])
        self.assertEqual(self.game.cash, cash_before)  # a sacrifice pays nothing

    def test_v2_spirit_token_is_permanent(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CASH, 15, 20, "b", effects=[])
        self.game.toolbox.add(block)

        self.assertTrue(self.game._action_spirit(
            main.ActionItem(main.Action.SPIRIT, 36, version=2), block))

        self.assertIsNone(self.game.tokens[0].runs_left)
        self.assertNotIn(block, self.game.toolbox.items)

    def test_spirit_refuses_roles_scorerless_blocks_and_a_full_token_column(self):
        action = main.ActionItem(main.Action.SPIRIT, 36)
        start = main.Block(3, 3, scorer=main.Scorer.START)
        plain = main.Block(4, 3, scorer=main.Scorer.NONE)
        self.game.grid[(3, 3)] = start
        self.game.grid[(4, 3)] = plain

        self.assertFalse(self.game._action_spirit(action, start))
        self.assertFalse(self.game._action_spirit(action, plain))
        self.assertFalse(self.game._action_spirit(
            action, main.CardItem(main.Card.GARDEN, 36)))

        self.game.tokens = [main.ScorerToken(main.Scorer.CASH, 15)
                            for _ in range(main.MAX_TOKENS)]
        keeper = main.Block(5, 3, scorer=main.Scorer.CASH, scorer_amount=15)
        self.game.grid[(5, 3)] = keeper
        self.assertFalse(self.game._action_spirit(action, keeper))
        self.assertIn((5, 3), self.game.grid)  # the block was not consumed

    def test_tokens_sit_right_of_the_inventory_and_only_fill_their_own_cells(self):
        self.game.tokens = [main.ScorerToken(main.Scorer.CASH, 15, runs_left=2)]
        rect = self.game._token_rect(0)

        self.assertGreater(rect.left,
                           main.TOOLBOX_COORDS[0] + main.TOOLBOX_COORDS[2])
        self.assertEqual(rect.size, (main.GRID_SIZE, main.GRID_SIZE))
        self.assertIs(self.game.token_at(rect.center), self.game.tokens[0])
        self.assertIsNone(self.game.token_at((rect.centerx, rect.centery + 41)))
        # The chip and the info sidebar render without raising.
        self.game.draw()
        self.assertEqual(self.game._info_target_at(rect.center),
                         (self.game.tokens[0], "tokens"))
        self.assertTrue(self.game._describe_item(self.game.tokens[0]))
        self.assertTrue(self.game._action_hint(self.game.tokens[0], "tokens"))

    def test_a_token_fires_its_scorer_at_the_start_of_each_run(self):
        seed = main.Block(3, 4, scorer=main.Scorer.MULT_ADD, scorer_amount=4,
                          effects=[])
        self.game.grid[(3, 4)] = seed
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), seed)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.upgrades_enabled = False
        self.game.score_mult = 1

        self.assertTrue(self.game.reset_run())

        # +4 mult from the kept scorer, on top of the fresh run's x1.
        self.assertEqual(self.game.score_mult, 5)
        self.assertTrue(self.game.tokens[0].fired)

    def test_tokens_spend_a_run_and_expire(self):
        self.game.tokens = [main.ScorerToken(main.Scorer.MULT_ADD, 4, runs_left=2)]
        self.game.tokens[0].fired = True

        self.game._advance_tokens()

        self.assertEqual([t.runs_left for t in self.game.tokens], [1])
        self.assertFalse(self.game.tokens[0].fired)
        self.game.tokens[0].fired = True
        self.game._advance_tokens()
        self.assertEqual(self.game.tokens, [])

    def test_a_token_created_mid_run_is_not_spent_by_that_run(self):
        seed = main.Block(3, 4, scorer=main.Scorer.MULT_ADD, scorer_amount=4,
                          effects=[])
        self.game.grid[(3, 4)] = seed
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), seed)
        self.assertFalse(self.game.tokens[0].fired)

        self.game._advance_tokens()  # the run that just ended never fired it

        self.assertEqual([t.runs_left for t in self.game.tokens], [2])

    def test_a_satanic_token_dies_with_its_scorer_and_a_sharp_one_usually_survives(self):
        # Saturnic scorers destroy themselves after a run, so the token does
        # too; a Sharp scorer only has its usual 1/4 destruction chance.
        satanic = main.ScorerToken(main.Scorer.SATANIC, 6.66, runs_left=None)
        satanic.fired = True
        sharp = main.ScorerToken(main.Scorer.SHARP, 3, runs_left=None)
        sharp.fired = True
        self.game.tokens = [satanic, sharp]

        with mock.patch("main.random.random", return_value=0.9):
            self.game._advance_tokens()
        self.assertNotIn(satanic, self.game.tokens)
        self.assertIn(sharp, self.game.tokens)

        sharp.fired = True
        with mock.patch("main.random.random", return_value=0.1):
            self.game._advance_tokens()
        self.assertEqual(self.game.tokens, [])

    def test_a_token_fires_even_with_the_watch_card(self):
        # Watch limits which TOUCHED blocks score; a token is a start-of-run
        # payoff like a card, so it is never gated.
        ghost = main.Block(3, 4, scorer=main.Scorer.MULT_ADD, scorer_amount=4)
        ghost.is_token = True
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))

        self.assertFalse(self.game._watch_blocks_out_of_play(ghost))
        self.assertTrue(self.game._watch_blocks_out_of_play(
            main.Block(5, 5, scorer=main.Scorer.MULT_ADD, scorer_amount=4)))

    def test_upgrade_trigger_limit_deducts_cash_and_raises_limit(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips", trigger_limit=1)
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 1000
        cost = self.game._trigger_upgrade_cost(block)

        self.game._upgrade_trigger_limit()

        self.assertEqual(block.trigger_limit, 2)
        self.assertEqual(block.trigger_paid, cost)
        self.assertEqual(self.game.cash, 1000 - cost)

    def test_upgrade_trigger_limit_requires_cash(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips")
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 0

        self.game._upgrade_trigger_limit()

        self.assertEqual(block.trigger_limit, 1)
        self.assertTrue(self.game.shop_message)

    def test_upgrade_trigger_limit_only_for_blocks(self):
        comp = next(i for i in self.game.shop.items if i.kind == main.Component.SHAPE)
        self.game.selected_toolbox_item = comp
        self.game.cash = 1000

        self.game._upgrade_trigger_limit()

        self.assertEqual(self.game.cash, 1000)  # no charge: components aren't blocks

    def test_upgrade_overlay_rect_is_left_of_sell_rect(self):
        sell = main.SELL_OVERLAY_RECT
        up = main.UPGRADE_OVERLAY_RECT
        # Same row and size, sitting directly left of the SELL cell.
        self.assertEqual(up.top, sell.top)
        self.assertEqual(up.bottom, sell.bottom)
        self.assertEqual(up.height, sell.height)
        self.assertEqual(up.right, sell.left)

    def test_clicking_upgrade_overlay_raises_trigger_limit(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.cash = 1000
        cost = self.game._trigger_upgrade_cost(block)

        self._click(main.UPGRADE_OVERLAY_RECT.center)

        self.assertEqual(block.trigger_limit, 2)
        self.assertEqual(self.game.cash, 1000 - cost)
        # Selection is preserved so the player can upgrade again.
        self.assertIs(self.game.selected_toolbox_item, block)

    def test_clicking_upgrade_overlay_with_component_does_nothing(self):
        comp = next(i for i in self.game.shop.items if i.kind == main.Component.SHAPE)
        self.game.selected_toolbox_item = comp
        self.game.cash = 1000

        self._click(main.UPGRADE_OVERLAY_RECT.center)

        self.assertEqual(self.game.cash, 1000)

    def test_draw_upgrade_overlay_handles_block_and_component(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "B")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.draw_upgrade_overlay()  # block -> draws the cost without raising

        comp = next(i for i in self.game.shop.items if i.kind == main.Component.SHAPE)
        self.game.selected_toolbox_item = comp
        self.game.draw_upgrade_overlay()  # component -> no-op

    def test_sidebar_total_price_includes_trigger_upgrade_cash(self):
        upgraded = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                                  10, 50, "Rect +Chips", trigger_paid=120)
        # Total = original price + cash paid for trigger upgrades.
        self.assertEqual(self.game._total_price(upgraded), 170)

        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips")
        self.assertIsNone(self.game._total_price(plain))  # no upgrades -> no total line

        # The info box renders an upgraded block (price + total) without raising.
        self.game.toolbox.items.clear()
        self.game.toolbox.add(upgraded)
        pos = (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5)
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos):
            self.game.draw_sidebar()

    def test_sell_refunds_trigger_upgrade_cash(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips", trigger_limit=3, trigger_paid=150)
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 0

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, block.price // 2 + 150)

    def test_placed_block_keeps_trigger_upgrade_through_erase_and_sell(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips", trigger_limit=2, trigger_paid=120)
        self.game.toolbox.items.append(block)
        # Place it with its upgraded trigger data, then erase (refund) it.
        self.game.grid[(2, 2)] = main.Block(2, 2, shape=main.Shape.RECT, effect=main.Effect.NONE,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10,
                                            trigger_limit=block.trigger_limit,
                                            trigger_paid=block.trigger_paid)
        self.game._erase_block_at(2, 2)
        refunded = self.game.toolbox.items[-1]
        self.assertEqual(refunded.trigger_limit, 2)
        self.assertEqual(refunded.trigger_paid, 120)

        self.game.selected_toolbox_item = refunded
        self.game.cash = 0
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, refunded.price // 2 + 120)

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

    def test_placed_block_keeps_the_items_price_not_a_part_recount(self):
        # Placing a block stamps it with the price of the item it came from, so
        # its worth never drifts to a re-summed part total: this item was sold
        # for $7 while its parts would price the block differently.
        placed = self._place_priced_block(1, 1, 7)
        self.assertEqual(placed.resale_price, 7)
        self.assertEqual(main.block_resale_price(placed), 7)
        self.assertNotEqual(
            main.block_price_for(placed.shape, placed.effects, placed.scorer,
                                 placed.scorer_amount, placed.effect_amounts), 7)

    def test_death_and_recognition_use_the_placed_blocks_stored_price(self):
        # Death pays 1.5x the price the block was placed with, and Recognition
        # charges that same price, even though a recount of its parts says more.
        placed = self._place_priced_block(1, 1, 7)
        death = main.ActionItem(main.Action.DEATH, 24)
        self.game.cash = 100
        self.assertTrue(self.game._action_death(death, placed))
        self.assertEqual(self.game.cash, 100 + int(7 * 1.5))

        duplicate = self._place_priced_block(2, 1, 7)
        recognition = main.ActionItem(main.Action.RECOGNITION, 24)
        self.game.cash = 100
        self.assertTrue(self.game._action_recognition(recognition, duplicate))
        self.assertEqual(self.game.cash, 100 - 7)

    def test_moving_and_erasing_a_placed_block_keeps_its_price(self):
        # A move hands the block back to the inventory at its stored price, so
        # the block that lands in the new cell is worth the same $7.
        placed = self._place_priced_block(1, 1, 7)
        self.assertEqual(placed.resale_price, 7)
        self._click(self._grid_pos(1, 1))  # select the placed block
        self.game.drawing = False  # release the button before the move click
        self._click(self._grid_pos(3, 3))  # move it
        self.assertEqual(self.game.grid[(3, 3)].resale_price, 7)

        self.game._erase_block_at(3, 3)
        self.assertEqual(self.game.toolbox.items[-1].price, 7)

    def test_placed_block_price_survives_a_save_round_trip(self):
        placed = self._place_priced_block(1, 1, 7)
        data = save_system._serialize_item(placed)
        self.assertEqual(data["resale_price"], 7)

        restored = save_system._deserialize_item(data)
        self.assertEqual(restored.resale_price, 7)
        self.assertEqual(main.block_resale_price(restored), 7)

        # A save written before the price was stored leaves it unset, and the
        # first read materializes the part total on the block once.
        legacy = dict(data)
        legacy.pop("resale_price")
        old = save_system._deserialize_item(legacy)
        self.assertIsNone(old.resale_price)
        price = main.block_resale_price(old)
        self.assertEqual(old.resale_price, price)
        self.assertEqual(main.block_resale_price(old), price)

    def test_block_resale_price_materializes_for_an_unpriced_block(self):
        # A hand-built block (never placed from an item) has no stored price:
        # the helper derives the part total once and keeps it, so later reads
        # can no longer drift.
        block = main.Block(2, 2, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=30)
        self.assertIsNone(getattr(block, "resale_price", None))
        price = main.block_resale_price(block)
        self.assertEqual(price,
                         main.block_price_for(block.shape, block.effects,
                                              block.scorer, block.scorer_amount,
                                              block.effect_amounts))
        self.assertEqual(block.resale_price, price)
        self.assertEqual(main.block_resale_price(block), price)

    def test_shattered_fragile_block_is_priced_by_its_original_shape(self):
        # A shattered fragile block is a Shape.NONE cell; without a stored
        # price it is still worth what it was built as (the shape a refund
        # hands back), not a NONE cell's price.
        block = main.Block(2, 2, shape=main.Shape.RECT, effect=main.Effect.FRAGILE)
        block._fragile_shape = block.shape
        block.shape = main.Shape.NONE
        self.assertEqual(main.block_resale_price(block),
                         main.block_price_for(main.Shape.RECT, block.effects,
                                              block.scorer, block.scorer_amount,
                                              block.effect_amounts))

    def test_upgraded_block_scores_multiple_times_per_run(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.NONE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, trigger_limit=2)
        marble = self._add_marble()  # already appends to self.game.marbles
        self.game.run_active = True
        self.game.score_chips = 0

        # Touch, leave, and touch again: each edge scores (limit 2 -> twice).
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 10)

        marble.collisions_this_tick = []
        marble.collisions_last_tick = [block]
        self.game._handle_block_contacts([block])

        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_chips, 20)
        self.assertEqual(block.triggers_left, 0)

    def test_portal_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.PORTAL, main.Effect.ORDER)
        self.assertEqual(main.Effect.name(main.Effect.PORTAL), "Portal")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.PORTAL)], 0)
        self.assertIn("portal", main.effect_description(main.Effect.PORTAL).lower())

    def test_rotate_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.ROTATE, main.Effect.ORDER)
        self.assertEqual(main.Effect.name(main.Effect.ROTATE), "Rotate")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.ROTATE)], 0)
        self.assertIn("rotat", main.effect_description(main.Effect.ROTATE).lower())

    def test_slippery_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.SLIPPERY, main.Effect.ORDER)
        self.assertIn(main.Effect.SLIPPERY, main.Effect.REAL_ORDER)
        self.assertEqual(main.Effect.name(main.Effect.SLIPPERY), "Slippery")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.SLIPPERY)], 0)
        self.assertIn("slide", main.effect_description(main.Effect.SLIPPERY).lower())

    def test_fragile_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.FRAGILE, main.Effect.ORDER)
        self.assertIn(main.Effect.FRAGILE, main.Effect.REAL_ORDER)
        self.assertEqual(main.Effect.name(main.Effect.FRAGILE), "Fragile")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.FRAGILE)], 0)
        self.assertIn("shatter", main.effect_description(main.Effect.FRAGILE).lower())

    def test_growing_shrinking_effects_are_defined_and_shop_available(self):
        for effect, name in ((main.Effect.GROWING, "Growing"),
                             (main.Effect.SHRINKING, "Shrinking")):
            with self.subTest(effect=name):
                self.assertIn(effect, main.Effect.ORDER)
                self.assertIn(effect, main.Effect.REAL_ORDER)
                self.assertEqual(main.Effect.name(effect), name)
                self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, effect)], 0)
                self.assertTrue(main.effect_description(effect))

    def test_rotate_block_draws_effect_icon_and_geometry(self):
        # A rotating rect draws without raising and its effect icon renders.
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.draw(surface)
        # Geometry carries an effective angle that reflects the spin.
        block.spin = 30.0
        block._refresh_geometry()
        self.assertAlmostEqual(block.effective_angle, 30.0)

    def test_block_effect_property_returns_first_effect(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertEqual(block.effect, main.Effect.BOUNCY)
        self.assertEqual(block.effects, [main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertTrue(block.has_effect(main.Effect.BOUNCY))
        self.assertTrue(block.has_effect(main.Effect.PISTON))
        self.assertFalse(block.has_effect(main.Effect.GRAVITY))

    def test_block_without_effects_falls_back_to_none(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.NONE,
                           scorer=main.Scorer.NONE)
        self.assertEqual(block.effect, main.Effect.NONE)
        self.assertEqual(block.effects, [main.Effect.NONE])

    def test_blockitem_effect_property_returns_first_effect(self):
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.BOUNCY,
                              main.Scorer.CHIPS_ADD, 10, 20, "B",
                              effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertEqual(item.effect, main.Effect.BOUNCY)
        self.assertEqual(item.effects, [main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertTrue(item.has_effect(main.Effect.PISTON))

    def test_multi_effect_icon_draws_plus_marker(self):
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        single = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                            effects=[main.Effect.BOUNCY])
        single.rect.topleft = (0, 0)  # center = (20, 20); plus would be at (30, 30)
        single._draw_effect_icon(surface)
        self.assertEqual(surface.get_at((30, 30))[:3], (0, 0, 0))  # no + for one effect

        multi = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        multi.rect.topleft = (0, 0)
        multi._draw_effect_icon(surface)
        self.assertNotEqual(surface.get_at((30, 30))[:3], (0, 0, 0))  # + marks >1 effect

    def test_random_effect_count_is_bounded(self):
        counts = [main.random_effect_count() for _ in range(800)]
        self.assertTrue(all(0 <= c <= len(main.Effect.REAL_ORDER) for c in counts))
        self.assertIn(0, counts)
        self.assertIn(1, counts)
        self.assertIn(2, counts)

    def test_random_effect_count_geometric_distribution(self):
        random.seed(1234)
        trials = 4000
        observed = {}
        for _ in range(trials):
            c = main.random_effect_count()
            observed[c] = observed.get(c, 0) + 1
        # Roughly 1/4 no-effect, then 1/2 of the rest one-effect (~0.375),
        # 1/4 of the rest two-effect (~0.19), 1/8 three-effect (~0.09)...
        self.assertGreater(observed.get(0, 0) / trials, 0.15)
        self.assertLess(observed.get(0, 0) / trials, 0.35)
        self.assertGreater(observed.get(1, 0) / trials, 0.3)
        self.assertGreater(observed.get(2, 0) / trials, 0.15)
        self.assertGreater(observed.get(3, 0) / trials, 0.07)
        # Fewer blocks with more effects.
        self.assertGreater(observed.get(1, 0), observed.get(2, 0))
        self.assertGreater(observed.get(2, 0), observed.get(3, 0))

    def test_shop_blocks_have_real_or_no_effects(self):
        # A pre-built block's effects are always real ones; it may also roll
        # NO effect at all (a plain wall), but never the literal None effect.
        for item in self.game.shop.items:
            if item.kind == "block":
                self.assertLessEqual(len(item.effects), len(main.Effect.REAL_ORDER))
                self.assertNotIn(main.Effect.NONE, item.effects)
                self.assertTrue(all(e in main.Effect.REAL_ORDER for e in item.effects))

    def test_random_shop_blocks_can_have_no_effect(self):
        # Over many rerolls, pre-built shop blocks sometimes have no effect
        # (a plain wall) and sometimes have real effects.
        plain = effectful = 0
        for _ in range(400):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "block":
                    if item.effects:
                        effectful += 1
                    else:
                        plain += 1
        self.assertGreater(plain, 0)
        self.assertGreater(effectful, 0)

    def test_effect_real_order_excludes_none(self):
        self.assertNotIn(main.Effect.NONE, main.Effect.REAL_ORDER)

    def test_buying_portal_block_adds_two_copies_with_same_number(self):
        self.game.toolbox.items.clear()
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL,
                                main.Scorer.NONE, 0, 50, "Portal Block")
        self.game.cash = 1000

        self.game._buy_shop_item(portal)

        # Buying one portal block yields a pair that shares a fresh number.
        portals = [i for i in self.game.toolbox.items if getattr(i, "effect", None) == main.Effect.PORTAL]
        self.assertEqual(len(portals), 2)
        self.assertEqual(portals[0].portal_number, portals[1].portal_number)
        self.assertGreater(portals[0].portal_number, 0)
        self.assertNotIn(portal, self.game.toolbox.items)  # the copies, not the shop item
        self.assertEqual(self.game.cash, 1000 - portal.price)  # charged once
        self.assertEqual(len(self.game.toolbox.items), 2)

    def test_buying_non_portal_block_adds_single_copy(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.cash = 1000

        self.game._buy_shop_item(block)

        self.assertEqual(len(self.game.toolbox.items), 1)
        self.assertIn(block, self.game.toolbox.items)

    def test_buying_portal_block_requires_two_free_slots(self):
        self.game.toolbox.items.clear()
        filler = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.NONE, 0, 5, "filler")
        while len(self.game.toolbox.items) < self.game.toolbox.cols * self.game.toolbox.rows - 1:
            self.game.toolbox.add(filler)
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL,
                                main.Scorer.NONE, 0, 50, "Portal Block")
        self.game.cash = 1000

        self.game._buy_shop_item(portal)

        self.assertEqual(len(self.game.toolbox.items), self.game.toolbox.cols * self.game.toolbox.rows - 1)
        self.assertTrue(self.game.shop_message)
        self.assertEqual(self.game.cash, 1000)  # not charged when there's no room

    def test_assembling_portal_block_adds_two_copies_with_same_number(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT)
        effect_c = main.Component.effect_component(main.Effect.PORTAL)
        scorer_c = main.Component.scorer_component(main.Scorer.NONE)
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        portals = [i for i in self.game.toolbox.items if i.effect == main.Effect.PORTAL]
        self.assertEqual(len(portals), 2)
        self.assertEqual(portals[0].portal_number, portals[1].portal_number)
        self.assertGreater(portals[0].portal_number, 0)
        self.assertTrue(self.game.has_selected)  # one of the pair is equipped
        self.assertIn(self.game.selected_toolbox_item, portals)

    def test_assembling_multi_effect_block_preserves_all_effects(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT)
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        bouncy = main.Component.effect_component(main.Effect.BOUNCY)
        piston = main.Component.effect_component(main.Effect.PISTON)
        for component in (shape_c, scorer_c, bouncy, piston):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(set(blocks[0].effects), {main.Effect.BOUNCY, main.Effect.PISTON})
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)  # first effect
        self.assertTrue(blocks[0].has_effect(main.Effect.PISTON))

    def test_disassembling_multi_effect_block_returns_all_effect_components(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.BOUNCY,
                               main.Scorer.CHIPS_ADD, 10, 20, "B",
                               effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self.game._disassemble_block()

        effects = [i for i in self.game.toolbox.items if i.kind == main.Component.EFFECT]
        self.assertEqual(len(effects), 2)
        self.assertEqual({e.value for e in effects}, {main.Effect.BOUNCY, main.Effect.PISTON})

    def test_disassembling_portal_block_deletes_paired_toolbox_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        self.game.toolbox.add(a)
        self.game.toolbox.add(b)
        self.game.cash = 100
        self.game.selected_toolbox_item = a

        self.game._disassemble_block()

        # The paired portal block is deleted; only a's three parts remain.
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 0)
        self.assertEqual(len(self.game.toolbox.items), 3)
        self.assertNotIn(b, self.game.toolbox.items)

    def test_disassembling_portal_block_deletes_paired_grid_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=7)
        self.game.toolbox.add(a)
        self.game.grid[(5, 5)] = b
        self.game.cash = 100
        self.game.selected_toolbox_item = a

        self.game._disassemble_block()

        self.assertNotIn((5, 5), self.game.grid)  # the placed paired portal is deleted

    def test_refunding_portal_block_preserves_number(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                           scorer=main.Scorer.NONE, portal_number=9)
        self.game.toolbox.items.clear()

        self.game._refund_block(block)

        portal = [i for i in self.game.toolbox.items if i.effect == main.Effect.PORTAL]
        self.assertEqual(len(portal), 1)
        self.assertEqual(portal[0].portal_number, 9)

    def test_placing_portal_block_preserves_number(self):
        self.game.toolbox.items.clear()
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                                0, 50, "Portal", portal_number=5)
        self.game.toolbox.add(portal)
        self.game._equip_block(portal)

        self._click(self._grid_pos(1, 1))

        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.effect, main.Effect.PORTAL)
        self.assertEqual(placed.portal_number, 5)  # the placed block keeps its number
        self.assertNotIn(portal, self.game.toolbox.items)  # consumed on placement

    def test_sidebar_describes_portal_block(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                           scorer=main.Scorer.NONE, portal_number=4)
        rows = self.game._describe_item(block)
        labels = [label for label, _ in rows]
        self.assertIn("Effect - Portal", labels)
        desc = next(text for label, text in rows if label == "Effect - Portal")
        self.assertIn("portal", desc.lower())

    def test_portal_scorer_activates_when_marble_passes_through(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        # Passing through the entry portal fires its scorer once.
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(a.triggers_left, 0)
        self.assertEqual(b.triggers_left, 0)  # the pair shares one trigger count

    def test_portal_scorer_does_not_activate_on_exit_portal(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        # Arriving at the exit portal does NOT score it (the marble didn't pass through).
        self.assertEqual(self.game.score_chips, 0)
        self.assertEqual(b.triggers_left, 1)

    def test_portal_scorer_stops_after_trigger_limit(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        # First pass-through: scores and exhausts the portal (border turns red).
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(a.triggers_left, 0)
        self.assertEqual(b.triggers_left, 0)  # the pair shares one trigger count

        # A fresh pass-through: the scorer no longer fires.
        marble.position = np.array([a.rect.centerx, a.rect.centery], dtype=float)
        marble.velocity = np.array([0.0, 0.0])
        marble.collisions_last_tick = []
        marble.collisions_this_tick = []
        marble.last_portal_cells = None
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)  # unchanged

    def test_using_either_portal_of_a_pair_depletes_both(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        # The marble passes through b (which carries the scorer) and exits at a.
        marble = self._add_marble((b.rect.centerx, b.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(b.triggers_left, 0)  # the portal that was used
        self.assertEqual(a.triggers_left, 0)  # the partner shares the count

    def test_placing_portal_syncs_trigger_count_with_partner(self):
        self.game.toolbox.items.clear()
        partner = main.Block(2, 2, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                             scorer=main.Scorer.NONE, portal_number=7)
        self.game.grid[(2, 2)] = partner
        partner.triggers_left = 0  # already exhausted this run
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                                0, 50, "Portal", portal_number=7)
        self.game.toolbox.add(portal)
        self.game._equip_block(portal)

        self._click(self._grid_pos(1, 1))

        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.portal_number, 7)
        self.assertEqual(placed.triggers_left, 0)  # inherits the pair's exhausted count
        self.assertEqual(partner.triggers_left, 0)

    def test_lone_portal_scorer_activates_on_pass_through(self):
        a = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        # A portal with no partner still scores a marble that passes through it.
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(a.triggers_left, 0)

    def test_portal_scorer_resets_each_run(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        a.triggers_left = 0  # used up during a run

        self.assertTrue(self.game.reset_run())
        self.assertEqual(a.triggers_left, 1)  # the portal can score again next run

    def test_portal_travel_budget_refills_each_run(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(a.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        self.assertEqual(b.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        # A portal pair drained during a run...
        a.portal_uses_left = 0
        b.portal_uses_left = 0
        # ...gets its full 100-travel budget back at the start of the next run.
        self.assertTrue(self.game.reset_run())
        self.assertEqual(a.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        self.assertEqual(b.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)

    def test_portal_description_mentions_the_100_use_cap(self):
        desc = main.effect_description(main.Effect.PORTAL)
        self.assertIn("portal", desc.lower())
        self.assertIn("100", desc)
        self.assertIn("run", desc.lower())

    def test_selling_portal_block_deletes_paired_toolbox_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        self.game.toolbox.add(a)
        self.game.toolbox.add(b)
        self.game._equip_block(a)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + a.price // 2)
        self.assertNotIn(a, self.game.toolbox.items)
        self.assertNotIn(b, self.game.toolbox.items)  # the paired portal is deleted too
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 0)

    def test_selling_portal_block_deletes_paired_grid_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=7)
        self.game.toolbox.add(a)
        self.game.grid[(5, 5)] = b
        self.game._equip_block(a)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertNotIn(a, self.game.toolbox.items)
        self.assertNotIn((5, 5), self.game.grid)  # the placed paired portal is deleted

    def test_selling_portal_block_deletes_partner_and_refunds(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        self.game.toolbox.add(a)
        self.game.toolbox.add(b)
        self.game.selected_toolbox_item = a
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertNotIn(a, self.game.toolbox.items)
        self.assertNotIn(b, self.game.toolbox.items)  # the partner is deleted
        self.assertEqual(self.game.cash, 50 + a.price // 2)

    def test_selling_non_portal_block_leaves_portal_pairs_alone(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Plain")
        for item in (a, b, plain):
            self.game.toolbox.add(item)
        self.game._equip_block(plain)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertIn(a, self.game.toolbox.items)
        self.assertIn(b, self.game.toolbox.items)  # selling a plain block doesn't touch portals

    def test_erasing_block_returns_block_to_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.grid[(1, 1)] = main.Block(1, 1, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)

        self.game._erase_block_at(1, 1)

        self.assertNotIn((1, 1), self.game.grid)
        self.assertEqual(len(self.game.toolbox.items), 1)
        returned = self.game.toolbox.items[0]
        self.assertEqual(returned.kind, "block")
        self.assertEqual(returned.shape, main.Shape.RECT)
        self.assertEqual(returned.effect, main.Effect.BOUNCY)
        self.assertEqual(returned.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(returned.scorer_amount, 10)

    def test_v_key_moves_blocks_back_to_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.grid[(1, 1)] = main.Block(1, 1, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 2)] = main.Block(2, 2, shape=main.Shape.SLOPE, effect=main.Effect.NONE,
                                            scorer=main.Scorer.MULT_ADD, scorer_amount=2)

        self._press(main.pygame.K_v)

        self.assertEqual(self.game.grid, {})  # the marble box is emptied
        self.assertEqual(len(self.game.toolbox.items), 2)  # blocks returned, not deleted
        scorers = {item.scorer for item in self.game.toolbox.items}
        self.assertEqual(scorers, {main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD})

    def test_v_key_clears_marbles(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(2, 1)] = main.Block(2, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 2)

        self._press(main.pygame.K_v)

        self.assertEqual(self.game.marbles, [])  # no start blocks left to run from
        self.assertFalse(self.game.run_active)

    def test_black_hole_icon_is_filled_circle_with_ring(self):
        surface = main.pygame.Surface((40, 40))
        blk = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.BLACK_HOLE,
                         scorer=main.Scorer.NONE)
        blk.rect.topleft = (0, 0)  # center = (20, 20)

        blk._draw_effect_icon(surface)

        self.assertNotEqual(surface.get_at((20, 20))[:3], (0, 0, 0))  # planet is filled
        # The ring extends left/right beyond the planet (planet radius 6).
        left_band = [surface.get_at((x, 20))[:3] for x in range(7, 14)]
        right_band = [surface.get_at((x, 20))[:3] for x in range(27, 34)]
        self.assertTrue(any(p != (0, 0, 0) for p in left_band))
        self.assertTrue(any(p != (0, 0, 0) for p in right_band))

    def test_erasing_start_block_removes_its_marble(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(2, 1)] = main.Block(2, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 2)
        # Each marble is tied to its own start block.
        start_a = self.game.grid[(1, 1)]
        start_b = self.game.grid[(2, 1)]
        marble_a = next(m for m in self.game.marbles if m.start_block is start_a)
        marble_b = next(m for m in self.game.marbles if m.start_block is start_b)

        self.game._erase_block_at(1, 1)

        self.assertNotIn((1, 1), self.game.grid)
        self.assertNotIn(marble_a, self.game.marbles)
        self.assertIn(marble_b, self.game.marbles)  # the other start's marble stays

    def test_erasing_non_start_block_keeps_marbles(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(2, 1)] = main.Block(2, 1, scorer=main.Scorer.CHIPS_ADD)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 1)

        self.game._erase_block_at(2, 1)

        self.assertEqual(len(self.game.marbles), 1)  # non-start erase leaves the marble

    def test_placing_assembled_block_via_events(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.NONE, 0, "None")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)
        self.game._assemble_block()

        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((1, 1), self.game.grid)
        self.assertFalse(self.game.has_selected)  # one block per assembly
        # The assembled block was consumed from the toolbox when placed.
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 0)


class SaveSystemTests(unittest.TestCase):
    """Save slots, serialization, and the slot-selection screen flow."""

    def setUp(self):
        # Point the save system at a throwaway folder so tests never touch the
        # real saves/ directory.
        self._tmp = tempfile.mkdtemp()
        self._old_saves_dir = save_system.SAVES_DIR
        save_system.SAVES_DIR = self._tmp
        # Keep the global achievements file out of test runs too.
        self._old_ach_file = achievements.FILE_PATH
        achievements.FILE_PATH = os.path.join(self._tmp, "achievements.json")
        achievements.reset()
        # The metagame (dice + run-start upgrades) is global too; keep it out
        # of test runs so no test inherits a leftover bonus.
        self._old_meta_file = metagame.FILE_PATH
        metagame.FILE_PATH = os.path.join(self._tmp, "metagame.json")
        metagame.reset()
        # The collection (discovered cards/components/trials) is global too.
        self._old_collection_file = collection.FILE_PATH
        collection.FILE_PATH = os.path.join(self._tmp, "collection.json")
        collection.reset()
        self.game = main.Game()
        self.game.title_screen = False
        self.game.trials_enabled = False

    def tearDown(self):
        save_system.SAVES_DIR = self._old_saves_dir
        achievements.FILE_PATH = self._old_ach_file
        achievements.reset()
        metagame.FILE_PATH = self._old_meta_file
        metagame.reset()
        collection.FILE_PATH = self._old_collection_file
        collection.reset()
        shutil.rmtree(self._tmp, ignore_errors=True)

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

    def _close(self):
        event = mock.Mock()
        event.type = main.pygame.QUIT
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def test_quit_autosaves_current_game(self):
        self.game.save_slot = 1
        self.game.cash = 321
        self._close()
        self.assertFalse(self.game.running)
        data = save_system._read_slot(1)
        self.assertEqual(data["cash"], 321)

    def test_quit_without_slot_does_not_save(self):
        # A fresh game has no active slot; closing must not write to slot 1.
        self.game.cash = 999
        self._close()
        self.assertFalse(self.game.running)
        self.assertFalse(save_system._slot_has_save(1))

    def test_serialize_placed_block_round_trip(self):
        block = main.Block(3, 5, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=30, angle=90, portal_number=4, trigger_limit=2,
                           trigger_paid=50, effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE])
        block.spin = 45.0
        block.triggers_left = 0
        loaded = save_system._deserialize_item(save_system._serialize_item(block))
        self.assertIsInstance(loaded, main.Block)
        self.assertEqual((loaded.x, loaded.y), (3, 5))
        self.assertEqual(loaded.shape, main.Shape.PIPE)
        self.assertEqual(loaded.effects, [main.Effect.SLIPPERY, main.Effect.FRAGILE])
        self.assertEqual(loaded.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(loaded.scorer_amount, 30)
        self.assertEqual(loaded.angle, 90)
        self.assertEqual(loaded.portal_number, 4)
        self.assertEqual(loaded.trigger_limit, 2)
        self.assertEqual(loaded.trigger_paid, 50)
        self.assertEqual(loaded.spin, 45.0)
        self.assertEqual(loaded.triggers_left, 0)

    def test_serialize_block_item_component_and_card_round_trip(self):
        item = main.BlockItem(2, 3, main.Shape.CIRCLE, main.Effect.NONE, main.Scorer.MULT_MUL,
                              1.5, 40, "Circle xMult", trigger_limit=3, trigger_paid=100,
                              effects=[main.Effect.BOUNCY])
        loaded = save_system._deserialize_item(save_system._serialize_item(item))
        self.assertIsInstance(loaded, main.BlockItem)
        self.assertEqual(loaded.col, 2)
        self.assertEqual(loaded.shape, main.Shape.CIRCLE)
        self.assertEqual(loaded.effects, [main.Effect.BOUNCY])
        self.assertEqual(loaded.scorer_amount, 1.5)
        self.assertEqual(loaded.trigger_limit, 3)
        self.assertEqual(loaded.trigger_paid, 100)

        comp = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4, price=20)
        loaded_comp = save_system._deserialize_item(save_system._serialize_item(comp))
        self.assertEqual(loaded_comp.kind, main.Component.SCORER)
        self.assertEqual(loaded_comp.value, main.Scorer.MULT_ADD)
        self.assertEqual(loaded_comp.amount, 4)
        self.assertEqual(loaded_comp.price, 20)

        card = main.CardItem(main.Card.EXPLORER, 25)
        loaded_card = save_system._deserialize_item(save_system._serialize_item(card))
        self.assertIsInstance(loaded_card, main.CardItem)
        self.assertEqual(loaded_card.value, main.Card.EXPLORER)
        self.assertEqual(loaded_card.price, 25)

    def test_p_key_saves_to_active_slot(self):
        self.game.save_slot = 1
        self.game.cash = 55555
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                                             main.Scorer.CHIPS_ADD, 30, 50, "Pipe"))
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))

        self._press(main.pygame.K_p)

        data = save_system._read_slot(1)
        self.assertIsNotNone(data)
        self.assertEqual(data["cash"], 55555)
        self.assertEqual(len(data["grid"]), 1)
        self.assertEqual(len(data["toolbox"]), 3)  # start + finish + pipe
        self.assertEqual(len(data["cards"]), 1)
        self.assertEqual(data["cards"][0]["value"], main.Card.JOKER)
        self.assertTrue(save_system._slot_has_save(1))

    def test_save_records_required_fields(self):
        self.game.save_slot = 2
        self.game.cash = 777
        self.game.run_number = 5
        self.game.round_index = 1
        self.game.run_in_round = 2
        self.game.required_score = 80
        self.game.run_results = [True, False, True, True, False]
        self.game.runs_cleared = 3
        self.game.failed_runs = 2
        self.game.current_trial = main.Trial.HANDS_TIED

        save_system.save_game(self.game)
        data = save_system._read_slot(2)

        self.assertEqual(data["cash"], 777)
        self.assertEqual(data["run_number"], 5)
        self.assertEqual(data["round_index"], 1)
        self.assertEqual(data["run_in_round"], 2)
        self.assertEqual(data["required_score"], 80)
        self.assertEqual(data["run_results"], [True, False, True, True, False])
        self.assertEqual(data["runs_cleared"], 3)
        self.assertEqual(data["failed_runs"], 2)
        self.assertEqual(data["current_trial"], main.Trial.HANDS_TIED)
        for key in ("toolbox", "grid", "shop", "cards", "actions"):
            self.assertIn(key, data)

    def test_load_slot_restores_state(self):
        self.game.save_slot = 3
        self.game.cash = 4321
        self.game.run_number = 7
        self.game.run_results = [True] * 5 + [False, True]
        self.game.runs_cleared = 6
        self.game.failed_runs = 1
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game.grid[(1, 2)] = main.Block(1, 2, shape=main.Shape.DRAIN,
                                            scorer=main.Scorer.MULT_ADD, scorer_amount=4)
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.toolbox.add(main.Component.shape_component(main.Shape.PIPE))
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)

        self.assertEqual(fresh.cash, 4321)
        self.assertEqual(fresh.run_number, 7)
        self.assertEqual(fresh.run_results, [True] * 5 + [False, True])
        self.assertEqual(fresh.runs_cleared, 6)
        self.assertEqual(fresh.failed_runs, 1)
        self.assertEqual(fresh.current_trial, main.Trial.CARD_CUTTER)
        self.assertIn((1, 2), fresh.grid)
        self.assertEqual(fresh.grid[(1, 2)].shape, main.Shape.DRAIN)
        self.assertEqual(len(fresh.cards), 1)
        self.assertEqual(fresh.cards[0].value, main.Card.EXPLORER)
        self.assertTrue(any(i.kind == main.Component.SHAPE for i in fresh.toolbox.items))
        self.assertEqual(fresh.save_slot, 3)
        self.assertFalse(fresh.run_active)

    def test_board_unlock_state_saves_and_loads(self):
        # A new game locks the board to the centered 2x3; squares unlocked in
        # the shop and Board Units still in hand persist through a save/load
        # instead of snapping back to a fully-unlocked board.
        save_system.start_new_game_in_slot(self.game, 4)
        self.assertTrue(self.game.is_cell_locked(0, 0))
        self.game._unlock_cell(0, 0)
        self.game._unlock_cell(9, 14)
        self.game.board_units = 2
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        self.assertEqual(len(data["unlocked_cells"]), len(self.game.unlocked_cells))
        self.assertEqual(data["board_units"], 2)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)

        # The partially-unlocked board (and the units in hand) come back intact.
        self.assertFalse(fresh.is_cell_locked(0, 0))
        self.assertFalse(fresh.is_cell_locked(9, 14))
        self.assertTrue(fresh.is_cell_locked(4, 5))  # still locked after load
        self.assertTrue(fresh.is_cell_locked(0, 1))  # never unlocked, still locked
        self.assertEqual(fresh.unlocked_cells, self.game.unlocked_cells)
        self.assertEqual(fresh.board_units, 2)
        # Locked squares act as walls again around the restored region.
        fresh._board_walls_dirty = True
        wall_cells = {(w.x, w.y) for w in fresh._board_wall_blocks()}
        self.assertNotIn((0, 0), wall_cells)
        self.assertIn((4, 5), wall_cells)

    def test_actions_save_and_load(self):
        # Owned actions (with their v1/v2 version) persist with the save.
        self.game.save_slot = 3
        self.game.cash = 5000
        self.game.actions.append(main.ActionItem(main.Action.DEATH, 60))
        self.game.actions.append(main.ActionItem(main.Action.RECOGNITION, 60, version=2))
        save_system.save_game(self.game)
        data = save_system._read_slot(3)
        self.assertEqual(len(data["actions"]), 2)
        self.assertEqual(data["actions"][0]["value"], main.Action.DEATH)
        self.assertEqual(data["actions"][0]["version"], 1)
        self.assertEqual(data["actions"][1]["value"], main.Action.RECOGNITION)
        self.assertEqual(data["actions"][1]["version"], 2)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)
        self.assertEqual(len(fresh.actions), 2)
        self.assertEqual(fresh.actions[0].value, main.Action.DEATH)
        self.assertEqual(fresh.actions[0].version, 1)
        self.assertEqual(fresh.actions[1].value, main.Action.RECOGNITION)
        self.assertEqual(fresh.actions[1].version, 2)

    def test_resource_points_save_and_load(self):
        # Shreds/Rubble/Ideas/Picky points persist with the save, along with
        # free rerolls (granted by Fresh) and bonus shop slots. Parts and
        # Fresh grant immediately, so they save no point banks.
        self.game.save_slot = 3
        self.game.shred_points = 2
        self.game.rubble_points = 3
        self.game.idea_points = 4
        self.game.free_rerolls = 2
        self.game.option_points = 1
        self.game.bonus_slots = 3
        save_system.save_game(self.game)
        data = save_system._read_slot(3)
        self.assertEqual(data["shred_points"], 2)
        self.assertEqual(data["rubble_points"], 3)
        self.assertEqual(data["idea_points"], 4)
        self.assertEqual(data["free_rerolls"], 2)
        self.assertEqual(data["option_points"], 1)
        self.assertEqual(data["bonus_slots"], 3)
        self.assertNotIn("part_points", data)
        self.assertNotIn("fresh_points", data)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)
        self.assertEqual(fresh.shred_points, 2)
        self.assertEqual(fresh.rubble_points, 3)
        self.assertEqual(fresh.idea_points, 4)
        self.assertEqual(fresh.free_rerolls, 2)
        self.assertEqual(fresh.option_points, 1)
        self.assertEqual(fresh.bonus_slots, 3)
        # The shop is synced to show the banked bonus slots on refresh.
        self.assertEqual(fresh.shop.bonus_slots, 3)

    def test_condition_component_and_built_card_save_and_load(self):
        # A condition component in the toolbox and a build-only card value
        # round-trip through a save.
        self.game.save_slot = 7
        cond = main.Component.condition_component(main.Condition.SHAPE_PIPE)
        self.game.toolbox.items.append(cond)
        value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 50))
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 7)
        self.assertTrue(any(i.kind == main.Component.CONDITION
                            and i.value == main.Condition.SHAPE_PIPE
                            for i in fresh.toolbox.items))
        self.assertEqual(len(fresh.cards), 1)
        self.assertEqual(fresh.cards[0].value, value)

    def test_wrecking_ball_bonus_saves_and_loads(self):
        # The Fragile Breaks (Wrecking Ball) permanent bonuses persist with the
        # save, one per unit scorer.
        self.game.save_slot = 4
        self.game.wrecking_bonus[main.Scorer.MULT_ADD] = 9
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        saved = dict(data["wrecking_bonus"])
        self.assertEqual(saved[main.Scorer.MULT_ADD], 9)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)
        self.assertEqual(fresh.wrecking_bonus[main.Scorer.MULT_ADD], 9)
        self.assertEqual(len(fresh.cards), 1)
        self.assertEqual(fresh.cards[0].value, main.Card.WRECKING_BALL)

    def test_tesseract_bonus_saves_and_loads(self):
        # Tesseract's permanent reroll bonus is a factor: it persists with the
        # save and comes back as 1.0 when the save predates the card.
        self.game.save_slot = 4
        self.game.tesseract_bonus = 1.8
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        self.assertEqual(data["tesseract_bonus"], 1.8)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)
        self.assertEqual(fresh.tesseract_bonus, 1.8)

        del data["tesseract_bonus"]
        fresh.tesseract_bonus = 9.9
        save_system._load_save_data(fresh, data, 4)
        # A save from before the card loads as no bonus at all.
        self.assertEqual(fresh.tesseract_bonus, 1.0)

    def test_spirit_tokens_save_and_load(self):
        # Spirit tokens persist: scorer, amount, the sacrificed block's cell and
        # effects, and how many runs are left (None = permanent).
        self.game.save_slot = 5
        self.game.tokens = [main.ScorerToken(main.Scorer.MULT_ADD, 4,
                                             shape=main.Shape.CIRCLE,
                                             effects=[main.Effect.BOUNCY],
                                             x=3, y=4, runs_left=2),
                            main.ScorerToken(main.Scorer.CASH, 15, runs_left=None)]
        save_system.save_game(self.game)
        data = save_system._read_slot(5)
        self.assertEqual(len(data["tokens"]), 2)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 5)
        self.assertEqual(len(fresh.tokens), 2)
        kept = fresh.tokens[0]
        self.assertEqual(kept.scorer, main.Scorer.MULT_ADD)
        self.assertEqual(kept.scorer_amount, 4)
        self.assertEqual(kept.shape, main.Shape.CIRCLE)
        self.assertEqual(kept.effects, [main.Effect.BOUNCY])
        self.assertEqual((kept.x, kept.y), (3, 4))
        self.assertEqual(kept.runs_left, 2)
        self.assertIsNone(fresh.tokens[1].runs_left)
        # A save from before tokens existed loads with none.
        fresh.tokens = [main.ScorerToken(main.Scorer.CASH, 15)]
        del data["tokens"]
        save_system._load_save_data(fresh, data, 5)
        self.assertEqual(fresh.tokens, [])

    def test_required_scores_are_saved_and_loaded(self):
        # The lazily-grown REQUIRED_SCORES schedule is stored in the save so a
        # loaded game continues the same targets instead of restarting at [1].
        self.game.save_slot = 5
        main.REQUIRED_SCORES[:] = [1, 2, 5]
        self.game.run_number = 2
        self.game.required_score = 5
        save_system.save_game(self.game)
        data = save_system._read_slot(5)
        self.assertEqual(data["required_scores"], [1, 2, 5])

        # A fresh game starts with a clean schedule...
        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        main.REQUIRED_SCORES[:] = [1]
        # ...and loading restores the saved one (module global included).
        save_system.load_slot(fresh, 5)
        self.assertEqual(main.REQUIRED_SCORES, [1, 2, 5])
        self.assertEqual(fresh.required_score, 5)
        # The restored schedule keeps growing from its last value (each run's
        # target doubles the previous one).
        self.assertEqual(main.get_next_required_score(3), 10)
        self.assertEqual(main.REQUIRED_SCORES, [1, 2, 5, 10])
        # Restore the module global so other tests aren't affected.
        main.REQUIRED_SCORES[:] = [1]

    def test_clicking_empty_slot_opens_marble_selection_then_starts(self):
        # A new save asks which marble type to use before starting the game.
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)
        self.assertFalse(game.title_screen)
        self.assertTrue(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        # Pick the 8 ball: the game starts with it and remembers the choice.
        self._click(game.marble_card_rect(1).center)
        self.assertFalse(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        self.assertEqual(game.marble_type, main.MarbleType.EIGHT_BALL)
        self.assertEqual(game.run_number, 0)

    def test_clicking_occupied_slot_confirms_then_loads(self):
        self.game.save_slot = 1
        self.game.cash = 999
        save_system.save_game(self.game)
        fresh = main.Game()
        fresh.title_screen = True
        fresh.trials_enabled = False
        self.game = fresh
        self._click(save_system.slot_rect(0).center)
        self.assertEqual(fresh.slot_confirm_index, 0)
        self._click(save_system.slot_load_button_rect().center)
        self.assertFalse(fresh.title_screen)
        self.assertEqual(fresh.save_slot, 1)
        self.assertEqual(fresh.cash, 999)

    def test_wipe_slot_deletes_save_and_opens_marble_selection(self):
        self.game.save_slot = 1
        self.game.cash = 999
        save_system.save_game(self.game)
        self.assertTrue(save_system._slot_has_save(1))
        fresh = main.Game()
        fresh.title_screen = True
        fresh.trials_enabled = False
        self.game = fresh
        self._click(save_system.slot_rect(0).center)
        self._click(save_system.slot_wipe_button_rect().center)
        self.assertTrue(fresh.marble_selecting)
        self.assertFalse(save_system._slot_has_save(1))  # old save wiped
        # Pick the rubber ball to finish starting the fresh game.
        self._click(fresh.marble_card_rect(2).center)
        self.assertFalse(fresh.marble_selecting)
        self.assertEqual(fresh.save_slot, 1)
        self.assertEqual(fresh.marble_type, main.MarbleType.RUBBER_BALL)
        self.assertEqual(fresh.cash, 60)  # reset to a fresh game

    def test_marble_selection_back_returns_to_title(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)
        self.assertTrue(game.marble_selecting)
        self._click(main.MARBLE_BACK_BUTTON_RECT.center)
        self.assertFalse(game.marble_selecting)
        self.assertTrue(game.title_screen)
        self.assertIsNone(game.save_slot)

    def test_marble_type_saves_and_loads(self):
        # The chosen marble type is one per save and persists with the game.
        self.game.save_slot = 3
        self.game.marble_type = main.MarbleType.EIGHT_BALL
        save_system.save_game(self.game)
        data = save_system._read_slot(3)
        self.assertEqual(data["marble_type"], main.MarbleType.EIGHT_BALL)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)
        self.assertEqual(fresh.marble_type, main.MarbleType.EIGHT_BALL)

    def test_clicking_ping_pong_card_selects_ping_pong(self):
        # The 4th marble-type card (index 3) is the ping-pong ball.
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)
        self.assertTrue(game.marble_selecting)
        self._click(game.marble_card_rect(3).center)
        self.assertFalse(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        self.assertEqual(game.marble_type, main.MarbleType.PING_PONG)

    def test_ping_pong_marble_type_saves_and_loads(self):
        # The chosen ping-pong type persists with the save (one per save).
        self.game.save_slot = 4
        self.game.marble_type = main.MarbleType.PING_PONG
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        self.assertEqual(data["marble_type"], main.MarbleType.PING_PONG)
        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)
        self.assertEqual(fresh.marble_type, main.MarbleType.PING_PONG)

    def test_marble_card_rects_fit_all_types_above_back_button(self):
        # The selection screen stacks every marble type (now 4, incl. the
        # ping-pong ball) above the BACK button / upgrade-toggle rows.
        game = main.Game()
        for i, mt in enumerate(main.MarbleType.ORDER):
            rect = game.marble_card_rect(i)
            self.assertGreater(rect.top, 0)
            self.assertLess(rect.bottom, main.MARBLE_BACK_BUTTON_RECT.top)
            self.assertLess(rect.bottom, main.MARBLE_UPGRADES_TOGGLE_RECT.top)

    def test_title_screen_draws_without_raising(self):
        self.game.save_slot = 1
        save_system.save_game(self.game)
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        game.draw()  # title + save slots
        game.slot_confirm_index = 0
        game.draw()  # confirm panel

    def test_rich_achievement_unlocks_above_1000_cash(self):
        # "Rich": hold more than $1000 in cash at any point in a run.
        self.assertFalse(achievements.is_unlocked("rich"))
        self.game.cash = 1001
        self.game.update()
        self.assertTrue(achievements.is_unlocked("rich"))
        # The unlock pops up at the bottom of the screen.
        self.assertTrue(any(p.title == "Rich" for p in self.game.popups))

    def test_rich_achievement_stays_locked_below_1000(self):
        # Exactly $1000 is NOT more than $1000, so it stays locked.
        self.game.cash = 1000
        self.game.update()
        self.assertFalse(achievements.is_unlocked("rich"))
        self.assertEqual(self.game.popups, [])

    def test_secret_achievement_locked_shows_question_marks(self):
        # Secret achievements hide their description as "???" until unlocked;
        # normal achievements always show their real description.
        secret = achievements.achievement_by_id("how_did_we_get_here")
        rich = achievements.achievement_by_id("rich")
        self.assertTrue(secret.secret)
        self.assertEqual(achievements.display_description(secret), "???")
        self.assertEqual(achievements.display_description(rich), rich.description)

    def test_secret_achievement_reveals_description_after_unlock(self):
        ach = achievements.achievement_by_id("how_did_we_get_here")
        achievements.unlock("how_did_we_get_here")
        self.assertEqual(achievements.display_description(ach), ach.description)

    def test_all_effects_block_unlocks_secret_achievement(self):
        # A single block holding every real effect in the game unlocks the
        # secret achievement (from the grid or the toolbox).
        self.assertFalse(achievements.is_unlocked("how_did_we_get_here"))
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           effects=list(main.Effect.REAL_ORDER))
        self.game.grid[(1, 1)] = block
        self.game.update()
        self.assertTrue(achievements.is_unlocked("how_did_we_get_here"))
        self.assertTrue(any(p.title == "How did we get here?" for p in self.game.popups))

    def test_partial_effects_block_keeps_secret_locked(self):
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           effects=[main.Effect.BOUNCY, main.Effect.PORTAL])
        self.game.grid[(1, 1)] = block
        self.game.update()
        self.assertFalse(achievements.is_unlocked("how_did_we_get_here"))
        self.assertEqual(self.game.popups, [])

    def test_popup_draws_at_bottom_and_clears(self):
        # A queued popup renders without raising and slides away on its own.
        self.game._push_popup("Rich", "Hold more than $1000")
        self.game.draw()
        for _ in range(300):  # ~5s at 60fps > ENTER + HOLD + EXIT
            self.game.update()
        self.assertEqual(self.game.popups, [])

    def test_secret_unlock_popup_shows_real_description(self):
        # Once unlocked, the popup shows the secret's real description.
        ach = achievements.achievement_by_id("how_did_we_get_here")
        achievements.unlock("how_did_we_get_here")
        self.game._show_achievement_popup(ach)
        self.assertTrue(self.game.popups)
        self.assertEqual(self.game.popups[-1].description, ach.description)
        self.game.draw()  # renders with the real description, not "???"

    def test_achievements_tab_opens_and_returns(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(main.ACHIEVEMENTS_BUTTON_RECT.center)
        self.assertTrue(game.achievements_open)
        self.assertFalse(game.title_screen)
        game.draw()  # renders the achievements grid
        self._click(main.ACHIEVEMENTS_RETURN_BUTTON_RECT.center)
        self.assertFalse(game.achievements_open)
        self.assertTrue(game.title_screen)

    def test_achievements_persist_across_games(self):
        # Unlocks are written to the global file and survive a fresh load.
        achievements.unlock("rich")
        achievements.reset()  # drop the in-memory cache
        self.assertTrue(achievements.is_unlocked("rich"))

    def test_game_over_menu_button_returns_to_title(self):
        self.game.game_over = True
        self._click(main.GAME_OVER_MENU_BUTTON_RECT.center)
        self.assertTrue(self.game.title_screen)
        self.assertFalse(self.game.game_over)

    def test_return_to_menu_button_rect_is_bottom_left(self):
        # The play-screen MAIN MENU button lives in the empty bottom-left
        # corner, clear of the board, panels, run dots, and trial box.
        btn = main.RETURN_TO_MENU_BUTTON_RECT
        self.assertTrue(btn.colliderect(
            main.pygame.Rect(0, 0, main.SCREEN_WIDTH, main.SCREEN_HEIGHT)))
        self.assertEqual(btn.bottom, main.SCREEN_HEIGHT)
        self.assertTrue(btn.right < main.MARBLE_BOX_COORDS[0])

    def test_clicking_return_to_menu_button_goes_to_title(self):
        # Clicking the bottom-left MAIN MENU button leaves the play screen,
        # resets the in-memory game, and returns to the title screen.
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.CHIPS_ADD)
        self.game.run_active = True
        self.game.title_screen = False
        self.game.game_over = False
        self._click(main.RETURN_TO_MENU_BUTTON_RECT.center)
        self.assertTrue(self.game.title_screen)
        self.assertFalse(self.game.game_over)
        self.assertFalse(self.game.run_active)
        self.assertEqual(self.game.grid, {})

    def test_return_to_menu_button_renders_on_play_screen(self):
        # The play frame draws the bottom-left MAIN MENU button without raising.
        self.game.title_screen = False
        self.game.game_over = False
        self.game.draw()  # game frame, includes the play-screen menu button

    def test_returning_to_menu_autosaves_the_game(self):
        # Exiting to the main menu from the play screen autosaves the current
        # game to its active slot BEFORE the in-memory state is reset, so
        # loading the slot resumes where the player left off.
        self.game.save_slot = 1
        self.game.cash = 432
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.CHIPS_ADD)
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(value, 50))
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._return_to_main_menu()
        self.assertTrue(self.game.title_screen)
        self.assertIsNone(self.game.save_slot)
        self.assertEqual(self.game.grid, {})
        # The slot was autosaved with the pre-exit state.
        data = save_system._read_slot(1)
        self.assertEqual(data["cash"], 432)
        self.assertEqual(len(data["grid"]), 1)
        self.assertEqual(len(data["cards"]), 1)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 1)
        self.assertEqual(fresh.cash, 432)
        self.assertEqual(len(fresh.grid), 1)
        self.assertEqual(len(fresh.cards), 1)

    def test_game_over_menu_button_autosaves(self):
        # The game-over MAIN MENU button also autosaves before leaving.
        self.game.save_slot = 2
        self.game.cash = 777
        self.game.run_number = 9
        self.game.game_over = True
        self._click(main.GAME_OVER_MENU_BUTTON_RECT.center)
        self.assertTrue(self.game.title_screen)
        data = save_system._read_slot(2)
        self.assertEqual(data["cash"], 777)
        self.assertEqual(data["run_number"], 9)
        self.assertTrue(data["game_over"])

    def test_return_to_menu_autosaves_cleared_ping_pong_run(self):
        # Regression: starting a run with the ping-pong ball and clearing it
        # stores a run result that used to be a numpy bool (the total score is
        # built from numpy factors); returning to the main menu autosaves that
        # state and used to raise "TypeError: Object of type bool is not JSON
        # serializable". The result must be a native bool and the autosave
        # must succeed and round-trip the run_results.
        self.game.save_slot = 1
        self.game.marble_type = main.MarbleType.PING_PONG
        self.game.marbles = []
        marble = main.Marble(300, 300)
        marble.finished = True
        self.game.marbles.append(marble)
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = 1000000
        self.game.score_mult = 1
        self.game.required_score = 1
        self.game.run_time = main.TIME_IDEAL
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_cleared)
        self.assertIs(type(self.game.run_results[0]), bool)
        # A direct save round-trips that native bool (a numpy bool would raise
        # "Object of type bool is not JSON serializable" here).
        save_system.save_game(self.game)
        self.assertEqual(save_system._read_slot(1)["run_results"], [True])
        # Returning to the main menu autosaves too, but rolls the un-confirmed
        # run back first (mirroring the QUIT autosave and the P key: a run's
        # rewards only stick after a run).
        self.game._return_to_main_menu()  # autosaves; must not raise
        self.assertTrue(self.game.title_screen)
        data = save_system._read_slot(1)
        self.assertEqual(data["run_results"], [])
        self.assertEqual(data["marble_type"], main.MarbleType.PING_PONG)

    def test_game_over_new_button_wipes_and_opens_marble_selection(self):
        # NEW GAME on the game-over screen acts like wiping the save: it clears
        # the save file and shows the marble-selection screen.
        self.game.save_slot = 1
        self.game.cash = 999
        save_system.save_game(self.game)
        self.assertTrue(save_system._slot_has_save(1))
        self.game.run_number = 5
        self.game.game_over = True
        self._click(main.GAME_OVER_NEW_BUTTON_RECT.center)
        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.marble_selecting)
        self.assertEqual(self.game.save_slot, 1)
        self.assertFalse(save_system._slot_has_save(1))  # the old save was wiped

    def test_game_over_continue_button_keeps_playing(self):
        self.game.run_number = 5
        self.game.game_over = True
        self._click(main.GAME_OVER_CONTINUE_BUTTON_RECT.center)
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, 5)  # the board is kept

    def test_continue_on_game_over_never_shows_again(self):
        # Clicking CONTINUE on the game-over screen clears the overlay and sets
        # continue_past_game_over, so a later run's CONTINUE no longer
        # re-triggers the game-over screen for this save.
        self.game.save_slot = 1
        self.game.run_number = 5
        self.game.failed_runs = 3
        self.game.game_over = True
        self._click(main.GAME_OVER_CONTINUE_BUTTON_RECT.center)
        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.continue_past_game_over)
        # Finishing and continuing another (failed) run advances normally
        # instead of showing the game over again.
        main.REQUIRED_SCORES[:] = [1, 2, 5, 12, 29, 70, 170]  # pre-grow for run 6
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game.run_cleared = False
        self.game.failed_runs = 3
        self.game._continue_run()
        main.REQUIRED_SCORES[:] = [1]  # restore the module global
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, 6)
        # The choice persists with the save so a reload keeps it too.
        save_system.save_game(self.game)
        self.assertTrue(save_system._read_slot(1)["continue_past_game_over"])

    def test_game_over_screen_draws_victory_and_defeat(self):
        # Both the victory and defeat game-over overlays render without raising.
        self.game.game_won = True
        self.game.game_over = True
        self.game.draw()
        self.game.game_won = False
        self.game.game_perfect = True
        self.game.game_over_dice_gained = 0
        self.game.draw()

    def test_upgrades_tab_opens_buys_and_returns(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        metagame.add_dice(1000)
        self._click(main.UPGRADES_BUTTON_RECT.center)
        self.assertTrue(game.upgrades_open)
        self.assertFalse(game.title_screen)
        game.draw()  # renders the upgrades tab
        # Buy the +chips upgrade (400 dice): one level, dice reduced.
        self._click(game.upgrade_card_rect(0).center)
        self.assertEqual(metagame.level("chip"), 1)
        self.assertEqual(metagame.chip_bonus(), 30)
        self.assertEqual(metagame.dice(), 1000 - 400)
        # Return to the main menu.
        self._click(main.UPGRADES_BACK_BUTTON_RECT.center)
        self.assertFalse(game.upgrades_open)
        self.assertTrue(game.title_screen)

    def test_upgrades_cannot_buy_without_enough_dice(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        game.upgrades_open = True
        self.assertEqual(metagame.dice(), 0)
        self._click(game.upgrade_card_rect(0).center)
        self.assertEqual(metagame.level("chip"), 0)
        self.assertEqual(metagame.dice(), 0)

    def test_metagame_upgrades_apply_at_run_start(self):
        # Bought upgrades add +chips, +mult, and xMult to every run's start.
        metagame.add_dice(400 + 800 + 1200)
        metagame.buy_upgrade("chip")
        metagame.buy_upgrade("mult")
        metagame.buy_upgrade("xmult")
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_chips, 1 + 30)
        self.assertEqual(self.game.score_mult, (1 + 4) * 1.25)

    def test_metagame_persists_across_reload(self):
        metagame.add_dice(500)
        metagame.buy_upgrade("chip")  # 400 dice -> level 1
        metagame.reset()  # drop the in-memory cache; reloads from the file
        self.assertEqual(metagame.dice(), 100)
        self.assertEqual(metagame.level("chip"), 1)
        self.assertEqual(metagame.chip_bonus(), 30)

    def test_marble_selection_upgrade_toggle_defaults_on_and_toggles_off(self):
        # The marble-selection screen defaults to upgrade effects ON and lets
        # the player turn them off for the new save (persisted with it).
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)  # open marble selection
        self.assertTrue(game.marble_selecting)
        self.assertTrue(game.upgrades_enabled)  # on by default
        self._click(main.MARBLE_UPGRADES_TOGGLE_RECT.center)
        self.assertFalse(game.upgrades_enabled)  # toggled off
        self._click(game.marble_card_rect(0).center)  # pick a marble
        self.assertFalse(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        self.assertFalse(game.upgrades_enabled)  # survives the game start

    def test_upgrades_enabled_false_skips_meta_bonuses(self):
        metagame.add_dice(400)
        metagame.buy_upgrade("chip")  # +30 chips are available
        self.game.upgrades_enabled = False
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_chips, 1)  # no +30 bonus
        self.assertEqual(self.game.score_mult, 1)

    def test_upgrades_enabled_saves_and_loads(self):
        self.game.save_slot = 2
        self.game.upgrades_enabled = False
        save_system.save_game(self.game)
        data = save_system._read_slot(2)
        self.assertIs(data["upgrades_enabled"], False)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 2)
        self.assertFalse(fresh.upgrades_enabled)

    def test_collection_tab_opens_and_returns(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(main.COLLECTION_BUTTON_RECT.center)
        self.assertTrue(game.collection_open)
        self.assertFalse(game.title_screen)
        game.draw()  # renders the collection grid
        self._click(main.COLLECTION_BACK_BUTTON_RECT.center)
        self.assertFalse(game.collection_open)
        self.assertTrue(game.title_screen)

    def test_discovering_card_adds_to_collection_and_pops(self):
        # Buying an indivisible card (Blueprint) reveals it in the collection
        # and pops it up (splittable cards instead reveal their halves).
        self.game.cash = 1000
        card = main.CardItem(main.Card.BLUEPRINT, 42)
        self.assertFalse(collection.is_card_discovered(main.Card.BLUEPRINT))
        self.game._buy_shop_item(card)
        self.assertTrue(collection.is_card_discovered(main.Card.BLUEPRINT))
        self.assertTrue(any(p.title == "New card" and p.description == "Blueprint"
                            for p in self.game.popups))

    def test_discovering_block_reveals_its_components(self):
        # Buying a block reveals the shape/effect/scorer pieces it is made of.
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Pipe +Chips",
                               effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertFalse(collection.is_component_discovered(
            main.Component.SHAPE, main.Shape.PIPE))
        self.game.cash = 1000
        self.game._buy_shop_item(block)
        self.assertTrue(collection.is_component_discovered(
            main.Component.SHAPE, main.Shape.PIPE))
        self.assertTrue(collection.is_component_discovered(
            main.Component.EFFECT, main.Effect.BOUNCY))
        self.assertTrue(collection.is_component_discovered(
            main.Component.SCORER, main.Scorer.CHIPS_ADD))

    def test_undiscovered_entries_show_question_marks(self):
        # Locked collection entries show "???" for name and description. Only
        # the two run-role scorers (Start/Finish) are auto-unlocked at game
        # start; everything else stays hidden on a fresh game.
        entries = self.game._collection_entries()
        self.assertTrue(entries)  # every card/component/trial is listed
        self.assertTrue(all(name == "???" and desc == "???"
                            for _, _, name, desc, _, d in entries if not d))
        self.assertTrue(any(not d for _, _, _, _, _, d in entries))  # most are hidden
        revealed = [(kind, value) for kind, value, _, _, _, d in entries if d]
        self.assertEqual(revealed,
                         [("scorer", main.Scorer.START), ("scorer", main.Scorer.FINISH)])

    def test_trial_discovered_on_cleared_run(self):
        # Beating a run with a trial reveals it in the collection.
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.game.marbles[0].finished = True
        self.game.required_score = 1
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(collection.is_trial_discovered(main.Trial.DEAD_ZONE))
        self.assertTrue(any(p.title == "New trial" for p in self.game.popups))

    def test_collection_persists_across_reload(self):
        collection.discover_card(main.Card.JOKER)
        collection.reset()  # drop the in-memory cache
        self.assertTrue(collection.is_card_discovered(main.Card.JOKER))


class ProfileTests(unittest.TestCase):
    """Profile folders: migration of the legacy root data into profile_1,
    per-profile isolation of the saves/achievements/collection/metagame files,
    and the title-screen switcher (button -> expandable list -> '+' name
    prompt)."""

    def setUp(self):
        # Isolate every file the profile system can touch under one temp dir.
        self._tmp = tempfile.mkdtemp()
        self._old_game_dir = profiles.GAME_DIR
        self._old_profiles_dir = profiles.PROFILES_DIR
        profiles.GAME_DIR = self._tmp
        profiles.PROFILES_DIR = os.path.join(self._tmp, "profiles")
        self._old_saves_dir = save_system.SAVES_DIR
        save_system.SAVES_DIR = self._tmp
        self._old_ach_file = achievements.FILE_PATH
        achievements.FILE_PATH = os.path.join(self._tmp, "achievements.json")
        achievements.reset()
        self._old_meta_file = metagame.FILE_PATH
        metagame.FILE_PATH = os.path.join(self._tmp, "metagame.json")
        metagame.reset()
        self._old_collection_file = collection.FILE_PATH
        collection.FILE_PATH = os.path.join(self._tmp, "collection.json")
        collection.reset()
        self.game = main.Game()
        self.game.title_screen = False
        self.game.trials_enabled = False

    def tearDown(self):
        profiles.GAME_DIR = self._old_game_dir
        profiles.PROFILES_DIR = self._old_profiles_dir
        save_system.SAVES_DIR = self._old_saves_dir
        achievements.FILE_PATH = self._old_ach_file
        achievements.reset()
        metagame.FILE_PATH = self._old_meta_file
        metagame.reset()
        collection.FILE_PATH = self._old_collection_file
        collection.reset()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_json(self, folder, name, data):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _click(self, pos):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def _key(self, key, unicode=""):
        event = mock.Mock()
        event.type = main.pygame.KEYDOWN
        event.key = key
        event.unicode = unicode
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def test_migrate_moves_legacy_root_data_into_profile_1(self):
        # A fake pre-profile layout at the game root: the shared saves folder
        # plus the three global json files.
        self._write_json(self._tmp, "achievements.json", {"unlocked": ["rich"]})
        self._write_json(self._tmp, "collection.json", {"cards": [main.Card.JOKER]})
        self._write_json(self._tmp, "metagame.json", {"dice": 5})
        os.makedirs(os.path.join(self._tmp, "saves"))
        for slot in range(1, 7):
            self._write_json(os.path.join(self._tmp, "saves"),
                             f"save{slot}.txt", {"cash": slot * 10})

        profiles.migrate_legacy()

        p1 = os.path.join(profiles.PROFILES_DIR, "profile_1")
        self.assertTrue(os.path.isfile(os.path.join(p1, "achievements.json")))
        self.assertTrue(os.path.isfile(os.path.join(p1, "collection.json")))
        self.assertTrue(os.path.isfile(os.path.join(p1, "metagame.json")))
        self.assertTrue(os.path.isfile(os.path.join(p1, "saves", "save1.txt")))
        # The legacy root copies are gone and the pointer names profile_1.
        self.assertFalse(os.path.exists(os.path.join(self._tmp, "saves")))
        self.assertFalse(os.path.exists(
            os.path.join(self._tmp, "achievements.json")))
        self.assertEqual(profiles.current_profile(), "profile_1")

    def test_profiles_isolate_saves_and_meta_progress(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.save_slot = 1
        self.game.cash = 321
        save_system.save_game(self.game)
        self.assertTrue(achievements.unlock("rich"))
        self.assertTrue(save_system._slot_has_save(1))

        # A brand-new profile starts empty and isolated.
        profiles.create_profile("Second")
        self.assertEqual(profiles.current_profile(), "Second")
        self.assertTrue(os.path.isdir(os.path.join(profiles.PROFILES_DIR,
                                                   "Second")))
        self.assertFalse(achievements.is_unlocked("rich"))
        self.assertFalse(save_system._slot_has_save(1))

        # Switching back to profile_1 brings its data back.
        profiles.switch_to("profile_1")
        self.assertTrue(achievements.is_unlocked("rich"))
        self.assertTrue(save_system._slot_has_save(1))

    def test_create_profile_names_folder_and_points_modules(self):
        profiles.migrate_legacy()
        created = profiles.create_profile("Adrian")
        self.assertEqual(created, "Adrian")
        self.assertEqual(profiles.current_profile(), "Adrian")
        # The save folder has the 6 empty slot placeholders.
        for slot in range(1, 7):
            self.assertTrue(os.path.isfile(os.path.join(
                profiles.PROFILES_DIR, "Adrian", "saves", f"save{slot}.txt")))
        # The persistence modules now point into the new profile.
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "Adrian", "saves"))
        self.assertEqual(achievements.FILE_PATH,
                         os.path.join(profiles.PROFILES_DIR, "Adrian",
                                      "achievements.json"))
        # A repeated name is uniquified instead of overwriting.
        self.assertEqual(profiles.create_profile("Adrian"), "Adrian 2")
        self.assertEqual(profiles.unique_name("A/B?"), "A B")

    def test_profile_button_expands_and_plus_creates_named_profile(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True

        self._click(main.PROFILE_BUTTON_RECT.center)
        self.assertTrue(self.game.profile_menu_open)

        _panel, _rows, plus = main.ui.profile_menu_geometry(
            profiles.list_profiles())
        self._click(plus.center)
        self.assertTrue(self.game.profile_naming)
        self.assertFalse(self.game.profile_menu_open)

        for ch in "Neo":
            self._key(main.pygame.K_a, ch)
        self._key(main.pygame.K_RETURN, "")
        self.assertFalse(self.game.profile_naming)
        self.assertFalse(self.game.profile_menu_open)
        self.assertEqual(profiles.current_profile(), "Neo")
        self.assertTrue(os.path.isdir(os.path.join(profiles.PROFILES_DIR,
                                                   "Neo")))
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "Neo", "saves"))
        # The brand-new profile has no real saves yet.
        self.assertFalse(save_system._slot_has_save(1))

    def test_clicking_a_profile_row_switches_profiles(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # now active
        self.game.title_screen = True

        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        target = names.index("profile_1")
        self._click(rows[target].center)

        self.assertFalse(self.game.profile_menu_open)
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "profile_1", "saves"))

    def test_blank_name_does_not_create_and_escape_cancels(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        _panel, _rows, plus = main.ui.profile_menu_geometry(
            profiles.list_profiles())
        self._click(plus.center)

        # Enter with no typed name keeps the prompt open (nothing created).
        self._key(main.pygame.K_RETURN, "")
        self.assertTrue(self.game.profile_naming)
        self.assertEqual(profiles.current_profile(), "profile_1")

        # Escape abandons the prompt and returns to the profile list.
        self._key(main.pygame.K_ESCAPE, "")
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)

    def test_title_screen_draws_profile_ui_without_raising(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")
        self.game.title_screen = True
        self.game.profile_menu_open = True
        self.game.draw()
        self.game.profile_naming = True
        self.game.profile_name_text = "Test"
        self.game.draw()
        self.game.profile_naming = False
        self.game.profile_menu_open = False
        self.game.draw()

    def test_rename_profile_renames_folder_pointer_and_modules(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        old_dir = profiles.profile_dir("profile_1")
        result = profiles.rename_profile("profile_1", "Main")
        self.assertEqual(result, "Main")
        self.assertFalse(os.path.isdir(old_dir))
        self.assertTrue(os.path.isdir(profiles.profile_dir("Main")))
        self.assertEqual(profiles.current_profile(), "Main")
        # The persistence modules now point at the renamed folder.
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "Main", "saves"))
        self.assertEqual(achievements.FILE_PATH,
                         os.path.join(profiles.PROFILES_DIR, "Main",
                                      "achievements.json"))

    def test_rename_profile_dedupes_and_same_name_is_noop(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second
        # Renaming Second to a name another profile (profile_1) uses is
        # deduped with a numeric suffix instead of clobbering the other folder.
        self.assertEqual(profiles.rename_profile("Second", "profile_1"),
                         "profile_1 2")
        self.assertEqual(profiles.current_profile(), "profile_1 2")
        # Renaming a profile to its own current name is a no-op.
        self.assertEqual(profiles.rename_profile("profile_1", "profile_1"),
                         "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_delete_active_profile_activates_a_remaining_one(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Zeta")  # active Zeta
        profiles.delete_profile("Zeta")
        self.assertFalse(os.path.isdir(profiles.profile_dir("Zeta")))
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_delete_last_profile_recreates_fresh_profile_1(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")  # the only profile
        self.game.save_slot = 1
        self.game.cash = 50
        save_system.save_game(self.game)
        self.assertTrue(save_system._slot_has_save(1))
        profiles.delete_profile("profile_1")
        # profile_1 is recreated, empty (its old data was removed with it).
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))
        self.assertFalse(save_system._slot_has_save(1))

    def test_delete_profile_handles_readonly_folder(self):
        # OneDrive marks profile folders read-only (no write bit on Windows),
        # which used to make shutil.rmtree silently fail so the folder survived
        # and the delete appeared to do nothing. Clearing the flag first must
        # let the folder actually go.
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second
        # Make Second read-only (OneDrive style).
        for root, dirs, files in os.walk(profiles.profile_dir("Second")):
            os.chmod(root, 0o555)
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o555)
            for f in files:
                os.chmod(os.path.join(root, f), 0o555)
        self.assertTrue(profiles.delete_profile("Second"))
        self.assertFalse(os.path.isdir(profiles.profile_dir("Second")))
        # The game settles on the remaining profile_1.
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_clicking_active_profile_row_opens_rename_popup(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        # The active profile's row opens its edit popup (pre-filled), not a switch.
        self.assertTrue(self.game.profile_naming)
        self.assertTrue(self.game.profile_renaming)
        self.assertFalse(self.game.profile_menu_open)
        self.assertEqual(self.game.profile_name_text, "profile_1")
        # Clear the pre-filled name, type a new one, and press Enter.
        for _ in range(len("profile_1")):
            self._key(main.pygame.K_BACKSPACE, "")
        for ch in "Main":
            self._key(main.pygame.K_a, ch)
        self._key(main.pygame.K_RETURN, "")
        self.assertFalse(self.game.profile_naming)
        self.assertEqual(profiles.current_profile(), "Main")
        self.assertTrue(os.path.isdir(profiles.profile_dir("Main")))

    def test_delete_button_confirms_then_deletes_active_profile(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        self.assertTrue(self.game.profile_renaming)
        # First Delete click asks for confirmation...
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertTrue(self.game.profile_delete_confirm)
        self.assertTrue(self.game.profile_naming)
        # ...and the second Delete click removes it. It was the only profile,
        # so a fresh profile_1 is recreated in its place.
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertFalse(self.game.profile_naming)
        self.assertFalse(self.game.profile_renaming)
        self.assertFalse(self.game.profile_delete_confirm)
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_keep_returns_to_rename_field_and_esc_closes(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second (two profiles exist)
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("Second")].center)
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertTrue(self.game.profile_delete_confirm)
        # Keep (bottom-right) returns to the rename field without deleting.
        self._click(main.ui.profile_name_cancel_rect().center)
        self.assertFalse(self.game.profile_delete_confirm)
        self.assertTrue(self.game.profile_naming)
        self.assertTrue(self.game.profile_renaming)
        self.assertEqual(profiles.current_profile(), "Second")
        self.assertTrue(os.path.isdir(profiles.profile_dir("Second")))
        # Esc closes the popup back to the profile list.
        self._key(main.pygame.K_ESCAPE, "")
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)

    def test_edit_and_delete_popups_draw_without_raising(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second
        self.game.title_screen = True
        self.game.profile_naming = True
        self.game.profile_renaming = True
        self.game.profile_name_text = "Second"
        self.game.draw()  # rename popup (with the Delete button)
        self.game.profile_delete_confirm = True
        self.game.draw()  # inline delete confirm
        self.game.profile_naming = False
        self.game.profile_renaming = False
        self.game.profile_delete_confirm = False
        self.game.draw()

    def test_unlock_collection_button_confirms_then_unlocks_and_disables(self):
        # The rename popup's Unlock-collection button (center-bottom) asks for
        # confirmation; confirming reveals every collection entry and
        # disables achievements for the profile.
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        self.assertTrue(self.game.profile_renaming)
        # A brand-new profile has plenty of undiscovered entries.
        self.assertTrue(any(not e[5] for e in self.game._collection_entries()))
        # First click asks for confirmation (like Delete does)...
        self._click(main.ui.profile_name_unlock_rect().center)
        self.assertTrue(self.game.profile_unlock_confirm)
        self.assertTrue(self.game.profile_naming)
        # ...the confirm's Unlock (the bottom-left action rect) reveals
        # everything and turns achievements off.
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)
        self.assertTrue(all(e[5] for e in self.game._collection_entries()))
        self.assertTrue(achievements.is_disabled())
        self.assertFalse(achievements.unlock("rich"))  # blocked now

    def test_unlock_confirm_keep_does_nothing(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        self._click(main.ui.profile_name_unlock_rect().center)
        self.assertTrue(self.game.profile_unlock_confirm)
        # Keep (bottom-right) backs out without unlocking or disabling.
        self._click(main.ui.profile_name_cancel_rect().center)
        self.assertFalse(self.game.profile_unlock_confirm)
        self.assertTrue(self.game.profile_naming)
        self.assertTrue(self.game.profile_renaming)
        self.assertFalse(achievements.is_disabled())
        self.assertTrue(any(not e[5] for e in self.game._collection_entries()))
        # Esc still returns to the profile list.
        self._key(main.pygame.K_ESCAPE, "")
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)

    def test_achievement_disabled_flag_is_per_profile(self):
        # Disabling achievements on one profile must not affect another, and it
        # survives switching back (persisted in the profile's achievements.json).
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        achievements.disable()
        self.assertTrue(achievements.is_disabled())
        self.assertFalse(achievements.unlock("rich"))
        # A second profile still has achievements enabled.
        second = profiles.create_profile("Second")
        self.assertEqual(profiles.current_profile(), second)
        self.assertFalse(achievements.is_disabled())
        self.assertTrue(achievements.unlock("rich"))
        # Switching back to profile_1 re-reads its disabled flag.
        profiles.switch_to("profile_1")
        self.assertTrue(achievements.is_disabled())

    def test_unlock_collection_popup_draws_without_raising(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self.game.profile_naming = True
        self.game.profile_renaming = True
        self.game.profile_name_text = "profile_1"
        self.game.draw()  # rename popup (with the Unlock-collection button)
        self.game.profile_unlock_confirm = True
        self.game.draw()  # inline unlock-collection confirm
        self.game.profile_unlock_confirm = False
        self.game.profile_delete_confirm = True
        self.game.draw()  # delete confirm still draws in the taller popup
        self.game.profile_delete_confirm = False
        self.game.profile_naming = False
        self.game.profile_renaming = False
        self.game.draw()


class BoardTests(unittest.TestCase):
    """The dynamic board: a new game starts with a centered 2x3 unlocked region,
    locked squares are solid walls, and Board Units bought in the shop
    (BOARD_UNIT_PRICE) unlock any square. The unlocked state resets when a NEW
    game starts but
    persists through a save/load (see SaveSystemTests)."""

    def setUp(self):
        self.game = main.Game()
        self.game.title_screen = False  # skip the title screen in tests
        self.game.trials_enabled = False  # no random trial in generic tests
        # Keep the global achievements/metagame/collection files out of tests.
        self._ach_tmp = tempfile.mkdtemp()
        self._old_ach_file = achievements.FILE_PATH
        achievements.FILE_PATH = os.path.join(self._ach_tmp, "achievements.json")
        achievements.reset()
        self._old_meta_file = metagame.FILE_PATH
        metagame.FILE_PATH = os.path.join(self._ach_tmp, "metagame.json")
        metagame.reset()
        self._old_collection_file = collection.FILE_PATH
        collection.FILE_PATH = os.path.join(self._ach_tmp, "collection.json")
        collection.reset()

    def tearDown(self):
        achievements.FILE_PATH = self._old_ach_file
        achievements.reset()
        metagame.FILE_PATH = self._old_meta_file
        metagame.reset()
        collection.FILE_PATH = self._old_collection_file
        collection.reset()
        shutil.rmtree(self._ach_tmp, ignore_errors=True)

    def _click(self, pos):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def _start_locked_game(self):
        """A brand-new game whose board is locked to the centered 2x3 region."""
        # Mirrors save_system.start_new_game_in_slot (no files are written).
        self.game.title_screen = False
        self.game.trials_enabled = False
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        return self.game

    def _start_region(self):
        """The centered starting 2x3 region (BOARD_START_WIDTH x BOARD_START_HEIGHT)."""
        x0 = (main.GRID_WIDTH - main.BOARD_START_WIDTH) // 2
        y0 = (main.GRID_HEIGHT - main.BOARD_START_HEIGHT) // 2
        return {(x0 + dx, y0 + dy)
                for dx in range(main.BOARD_START_WIDTH)
                for dy in range(main.BOARD_START_HEIGHT)}

    def _cell_center(self, gx, gy):
        return (main.MARBLE_BOX_COORDS[0] + gx * main.GRID_SIZE + main.GRID_SIZE // 2,
                main.MARBLE_BOX_COORDS[1] + gy * main.GRID_SIZE + main.GRID_SIZE // 2)

    def test_default_game_starts_with_full_board_unlocked(self):
        g = self.game  # a plain Game() (tests construct one directly)
        self.assertEqual(len(g.unlocked_cells), main.GRID_WIDTH * main.GRID_HEIGHT)
        self.assertFalse(g.board_locked())
        self.assertFalse(g.is_cell_locked(0, 0))
        self.assertFalse(g.is_cell_locked(9, 14))

    def test_new_game_locks_board_to_centered_2x3(self):
        g = self._start_locked_game()
        self.assertEqual(g.unlocked_cells, self._start_region())
        self.assertTrue(g.board_locked())
        self.assertEqual(g.board_units, 0)
        # The 2x3 region is centered: cols 4-5, rows 6-8.
        self.assertFalse(g.is_cell_locked(4, 6))
        self.assertFalse(g.is_cell_locked(5, 8))
        self.assertTrue(g.is_cell_locked(0, 0))
        self.assertTrue(g.is_cell_locked(9, 14))
        self.assertTrue(g.is_cell_locked(4, 5))  # just above the region

    def test_unlock_cell_works_on_any_square_and_rebuilds_walls(self):
        g = self._start_locked_game()
        # A far corner square is unlockable even though it is not adjacent.
        self.assertTrue(g.is_cell_locked(9, 14))
        self.assertTrue(g._unlock_cell(9, 14))
        self.assertFalse(g.is_cell_locked(9, 14))
        # Unlocking an already-unlocked square reports False.
        self.assertFalse(g._unlock_cell(9, 14))
        # The wall cache now covers every still-locked square (and none of the
        # unlocked ones).
        walls = g._board_wall_blocks()
        locked = main.GRID_WIDTH * main.GRID_HEIGHT - len(g.unlocked_cells)
        self.assertEqual(len(walls), locked)
        wall_cells = {(w.x, w.y) for w in walls}
        self.assertEqual(wall_cells, {(x, y)
                                      for x in range(main.GRID_WIDTH)
                                      for y in range(main.GRID_HEIGHT)}
                          - g.unlocked_cells)
        self.assertTrue(all(getattr(w, "is_board_wall", False) for w in walls))

    def test_buy_board_unit_costs_eight_and_stacks_in_hand(self):
        g = self._start_locked_game()
        g.cash = 60
        g._buy_board_unit()
        self.assertEqual(g.cash, 52)
        self.assertEqual(g.board_units, 1)
        g._buy_board_unit()
        self.assertEqual(g.cash, 44)
        self.assertEqual(g.board_units, 2)
        # Not enough cash -> no purchase.
        g.cash = 3
        g._buy_board_unit()
        self.assertEqual(g.cash, 3)
        self.assertEqual(g.board_units, 2)

    def test_shop_board_unit_tile_is_always_buyable(self):
        g = self._start_locked_game()
        g.cash = 60
        # The fixed tile sits in the rightmost cell of the shop's top row.
        tile = g._board_unit_tile()
        self.assertEqual(tile.centerx,
                         g.shop.rect.x + main.BOARD_UNIT_COL * main.GRID_SIZE
                         + main.GRID_SIZE // 2)
        self._click(tile.center)
        self.assertEqual(g.board_units, 1)
        self.assertEqual(g.cash, 52)
        # It survives a shop refresh (it is always offered, not a random slot).
        g._refresh_shop()  # costs $20, so top the cash back up first
        g.cash = 60
        self._click(tile.center)
        self.assertEqual(g.board_units, 2)
        self.assertEqual(g.cash, 52)

    def test_shop_layout_three_scorers_blocks_bottom_board_unit_top(self):
        g = self._start_locked_game()
        g.shop.refresh()
        # The top row's scorer slots (cols 5-7) are filled by scorer pieces —
        # or, when the draw is a run role, by that role's ready-made block.
        slots = [i for i in g.shop.items if i.row == 1 and i.col in (5, 6, 7)]
        self.assertEqual(sorted(i.col for i in slots), [5, 6, 7])
        self.assertTrue(all(getattr(i, "kind", None) in (main.Component.SCORER, "block")
                           for i in slots))
        # The two pre-made blocks sit at the END of the bottom row (cols 7-8,
        # just right of the two action slots).
        blocks = [i for i in g.shop.items if i.kind == "block" and i.row == 3]
        self.assertEqual(len(blocks), 2)
        self.assertEqual([i.col for i in blocks], [7, 8])
        # The middle row stays empty.
        self.assertEqual([i for i in g.shop.items if i.row == 2], [])
        # The Board Unit is on the top row and its cell holds no shop item.
        tile = g._board_unit_tile()
        self.assertEqual((tile.x - g.shop.rect.x) // main.GRID_SIZE,
                         main.BOARD_UNIT_COL)
        self.assertEqual((tile.y - g.shop.rect.y) // main.GRID_SIZE,
                         main.BOARD_UNIT_ROW)
        self.assertEqual(main.BOARD_UNIT_ROW, 1)
        self.assertIsNone(g.shop.item_at((tile.centerx, tile.centery)))

    def test_clicking_locked_square_spends_a_board_unit(self):
        g = self._start_locked_game()
        g.cash = 60
        g._buy_board_unit()  # one unit in hand
        self.assertTrue(g.is_cell_locked(0, 0))
        self._click(self._cell_center(0, 0))
        self.assertFalse(g.is_cell_locked(0, 0))
        self.assertEqual(g.board_units, 0)

    def test_clicking_locked_square_without_unit_just_hints(self):
        g = self._start_locked_game()
        self.assertTrue(g.is_cell_locked(1, 1))
        self._click(self._cell_center(1, 1))
        self.assertTrue(g.is_cell_locked(1, 1))  # still locked
        self.assertEqual(g.board_units, 0)
        self.assertTrue(g.shop_message)  # a "buy a Board Unit" hint

    def test_cannot_place_block_on_locked_square(self):
        g = self._start_locked_game()
        g.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 0, "Wall")
        g.toolbox.add(block)
        g._equip_block(block)
        self.assertTrue(g.has_selected)
        # Clicking a locked square must NOT place the block.
        self._click(self._cell_center(0, 0))
        self.assertNotIn((0, 0), g.grid)
        self.assertTrue(g.has_selected)
        # Clicking an unlocked square places it normally.
        self._click(self._cell_center(4, 6))
        self.assertIn((4, 6), g.grid)
        self.assertEqual(g.grid[(4, 6)].shape, main.Shape.RECT)

    def test_locked_board_resets_each_new_game(self):
        g = self._start_locked_game()
        g._unlock_cell(0, 0)
        g._unlock_cell(9, 14)
        g.board_units = 3
        self.assertEqual(len(g.unlocked_cells), 8)
        # Starting a NEW game returns the board to the centered 2x3 (units and
        # expansions reset here; they only persist when the game is saved and
        # its slot loaded).
        save_system.start_new_game_in_slot(g, 1)
        self.assertEqual(g.unlocked_cells, self._start_region())
        self.assertEqual(g.board_units, 0)
        self.assertNotIn((0, 0), g.unlocked_cells)

    def test_marble_is_confined_to_unlocked_region(self):
        g = self._start_locked_game()
        g.grid.clear()
        # A Start in the top row of the starting region; no Finish, so the
        # marble just falls and must come to rest on the locked floor.
        g.grid[(4, 6)] = main.Block(4, 6, shape=main.Shape.RECT,
                                    effect=main.Effect.NONE,
                                    scorer=main.Scorer.START, scorer_amount=0)
        self.assertTrue(g.reset_run(False))
        self.assertTrue(g.run_active)
        # Simulate several seconds: after every resolved frame the marble's
        # center must sit inside an unlocked square (locked squares are walls).
        for _ in range(360):
            g.update()
            for marble in g.marbles:
                gx = int((marble.position[0] - main.MARBLE_BOX_COORDS[0])
                         // main.GRID_SIZE)
                gy = int((marble.position[1] - main.MARBLE_BOX_COORDS[1])
                         // main.GRID_SIZE)
                self.assertFalse(
                    g.is_cell_locked(gx, gy),
                    f"marble escaped into locked square ({gx}, {gy})")
        # It should have come to rest well above the locked row 9 wall.
        for marble in g.marbles:
            self.assertLess(
                marble.position[1],
                main.MARBLE_BOX_COORDS[1] + 9 * main.GRID_SIZE)

    def test_cozy_magnitude_card_fires_3x_base_on_a_small_board(self):
        g = self._start_locked_game()
        # The 2x3 start is 6 unlocked units (10 or fewer), so a Cozy +Mult card
        # fires at the start of the run with its 3x base (+12 mult).
        value = main.condition_scorer_card(main.Condition.COZY, main.Scorer.MULT_ADD)
        g.cards.append(main.CardItem(value, 50))
        g.grid[(4, 6)] = main.Block(4, 6, scorer=main.Scorer.START)
        self.assertTrue(g.reset_run(False))
        self.assertAlmostEqual(g.score_mult, 1 + 12)  # 3x the +4 mult base

    def test_cozy_magnitude_card_is_silent_on_a_big_board(self):
        g = self._start_locked_game()
        value = main.condition_scorer_card(main.Condition.COZY, main.Scorer.MULT_ADD)
        g.cards.append(main.CardItem(value, 50))
        g.grid[(4, 6)] = main.Block(4, 6, scorer=main.Scorer.START)
        # Expand the board past 10 unlocked units; Cozy no longer fires.
        for x, y in ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4)):
            g._unlock_cell(x, y)
        self.assertGreater(len(g.unlocked_cells), 10)
        self.assertTrue(g.reset_run(False))
        self.assertAlmostEqual(g.score_mult, 1)

    def test_locked_adjacent_cells_are_the_reachable_frontier(self):
        g = self._start_locked_game()
        frontier = g._locked_adjacent_cells()
        self.assertTrue(frontier)  # the 2x3 region has locked neighbors
        for x, y in frontier:
            self.assertTrue(g.is_cell_locked(x, y))
            # Each candidate shares an edge with an unlocked square.
            self.assertTrue(
                any((x + dx, y + dy) in g.unlocked_cells
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))

    def test_grant_locked_units_unlocks_random_frontier_squares(self):
        g = self._start_locked_game()
        before = len(g.unlocked_cells)
        granted = g._grant_locked_units(3)
        self.assertEqual(granted, 3)
        self.assertEqual(len(g.unlocked_cells), before + 3)
        self.assertTrue(g.board_locked())  # far squares stay locked
        # Granting more than the frontier size still only unlocks the current
        # frontier cells, so the board can never fully unlock in one grant.
        granted_all = g._grant_locked_units(999)
        self.assertGreaterEqual(granted_all, 0)
        self.assertTrue(g.board_locked())
        # A fully-unlocked board grants nothing.
        for x in range(main.GRID_WIDTH):
            for y in range(main.GRID_HEIGHT):
                g._unlock_cell(x, y)
        self.assertEqual(g._grant_locked_units(6), 0)

    def test_continue_grants_drill_and_conquistador_locked_units(self):
        # Drill-scorer touches bank drill_run_units that only unlock after a
        # run; the Conquistador card adds 4 more after each run. (Board stays
        # locked, so the grants expand the frontier.)
        g = self._start_locked_game()
        before = len(g.unlocked_cells)  # the 6-cell 2x3 start
        g.drill_run_units = 2
        g.cards.append(main.CardItem(main.Card.CONQUISTADOR, 56))
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            g._continue_run()
        self.assertEqual(len(g.unlocked_cells) - before, 2 + 4)
        self.assertEqual(g.drill_run_units, 0)

    def test_retry_discards_pending_drill_units(self):
        # Retrying a run throws away the Drill-scorer unlocks banked for it.
        g = self._start_locked_game()
        before = len(g.unlocked_cells)
        g.drill_run_units = 2
        g.run_results.append(True)
        g.runs_cleared = 1
        g.last_run_cash_gained = 0
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            g._retry_run()
        self.assertEqual(g.drill_run_units, 0)
        self.assertEqual(len(g.unlocked_cells), before)  # nothing unlocked

    def test_continue_detonates_bomb_and_unlocks_its_radius(self):
        # A Bomb primed during a locked-board run unlocks every square within
        # 1 cell (Chebyshev, diagonals included) of it after a run, then
        # destroys the block. No drills or Conquistador here, so the whole
        # expansion comes from the detonation.
        g = self._start_locked_game()
        planted = g._locked_adjacent_cells()[0]  # a locked frontier square
        g.bomb_cells = {planted}
        g.grid[planted] = main.Block(planted[0], planted[1], scorer=main.Scorer.BOMB)
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            g._continue_run()
        # Every in-bounds neighbor within Chebyshev 1 of the bomb is unlocked.
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = planted[0] + dx, planted[1] + dy
                if 0 <= nx < main.GRID_WIDTH and 0 <= ny < main.GRID_HEIGHT:
                    self.assertIn((nx, ny), g.unlocked_cells)
        self.assertNotIn(planted, g.grid)  # the bomb destroyed itself
        self.assertEqual(g.bomb_cells, set())

    def test_continue_leaves_bomb_on_board_when_blocked_square_unlocked(self):
        # Detonation unlocks cells that are already unlocked harmlessly, and
        # the bomb block is removed from the grid either way.
        g = self._start_locked_game()
        start = self._start_region()
        planted = next(iter(start))  # already-unlocked cell holds a bomb
        g.bomb_cells = {planted}
        g.grid[planted] = main.Block(planted[0], planted[1], scorer=main.Scorer.BOMB)
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            g._continue_run()
        self.assertNotIn(planted, g.grid)
        self.assertEqual(g.bomb_cells, set())

    def test_retry_discards_primed_bombs(self):
        # Retrying a run throws away primed Bombs (they only detonate after a
        # run), so no locked squares are unlocked.
        g = self._start_locked_game()
        before = len(g.unlocked_cells)
        planted = g._locked_adjacent_cells()[0]
        g.bomb_cells = {planted}
        g.drill_run_units = 0
        g.run_results.append(True)
        g.runs_cleared = 1
        g.last_run_cash_gained = 0
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            g._retry_run()
        self.assertEqual(g.bomb_cells, set())
        self.assertEqual(len(g.unlocked_cells), before)  # nothing unlocked

    def test_a_bomb_blasts_before_the_drill_picks_its_squares(self):
        # The drill picks its squares off the locked frontier, so a Bomb's blast
        # has to resolve FIRST: blasted afterwards, it unlocks the radius the
        # drill's squares can sit in, the board grows by fewer squares than the
        # drill promised, and the block reads as broken whenever the two fire in
        # the same run. The frontier is ordered here so the drill would pick the
        # squares nearest the bomb first — exactly the overlap the ordering
        # avoids.
        g = self._start_locked_game()
        before = set(g.unlocked_cells)
        bomb = (5, 7)  # the start region's right-middle square
        g.bomb_cells = {bomb}
        g.grid[bomb] = main.Block(bomb[0], bomb[1], scorer=main.Scorer.BOMB)
        g.drill_run_units = 2

        def nearest_first(candidates):
            candidates.sort(key=lambda cell: abs(cell[0] - bomb[0])
                            + abs(cell[1] - bomb[1]))

        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.shuffle", side_effect=nearest_first), \
                mock.patch("main.random.random", return_value=0.9):
            g._continue_run()

        radius = {(bomb[0] + dx, bomb[1] + dy)
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        gained = g.unlocked_cells - before
        # The whole radius the bomb could open is open...
        self.assertEqual(gained & radius,
                         {cell for cell in radius if cell not in before})
        # ...and the drill's two squares are new ones ON TOP of it, none of them
        # inside what the blast was going to cover anyway.
        self.assertEqual(len(gained - radius), 2)
        self.assertEqual(len(gained), len(gained & radius) + 2)
        self.assertEqual(g.bomb_cells, set())
        self.assertIn("from the bomb blast", g.shop_message)
        self.assertIn("from the drill", g.shop_message)

    def test_the_run_end_names_every_source_of_board_expansion(self):
        # One message reports the finished run's whole expansion, naming each
        # source that contributed: a blast used to be announced after the drill
        # and replace its message, so a drill that had just expanded the board
        # was never mentioned.
        def run_end(g):
            g.run_complete = True
            g.awaiting_after_run = True
            with mock.patch("main.random.random", return_value=0.9):
                g._continue_run()

        g = self._start_locked_game()
        g.drill_run_units = 2
        run_end(g)
        self.assertEqual(g.shop_message,
                         "Board expanded 2 squares (2 from the drill)")

        g = self._start_locked_game()
        g.cards.append(main.CardItem(main.Card.CONQUISTADOR, 56))
        run_end(g)
        self.assertEqual(g.shop_message,
                         "Board expanded 4 squares (4 from Conquistador)")

        # The bomb's radius around (5, 7) opens its three locked neighbours.
        g = self._start_locked_game()
        bomb = (5, 7)
        g.bomb_cells = {bomb}
        g.grid[bomb] = main.Block(bomb[0], bomb[1], scorer=main.Scorer.BOMB)
        run_end(g)
        self.assertEqual(g.shop_message,
                         "Board expanded 3 squares (3 from the bomb blast)")

        # Both at once: the counts are listed side by side.
        g = self._start_locked_game()
        g.bomb_cells = {bomb}
        g.grid[bomb] = main.Block(bomb[0], bomb[1], scorer=main.Scorer.BOMB)
        g.drill_run_units = 2
        run_end(g)
        self.assertEqual(
            g.shop_message,
            "Board expanded 5 squares (3 from the bomb blast, 2 from the drill)")

        # Nothing unlocked by the run end leaves the message alone, and one
        # square still reads in the singular.
        g = self._start_locked_game()
        g.shop_message = ""
        g._announce_board_expansion(0, 0, 0)
        self.assertEqual(g.shop_message, "")
        g._announce_board_expansion(1, 0, 0)
        self.assertEqual(g.shop_message,
                         "Board expanded 1 square (1 from the bomb blast)")
        g._announce_board_expansion(0, 0, 2)
        self.assertEqual(g.shop_message,
                         "Board expanded 2 squares (2 from Conquistador)")

    def test_draw_board_paints_locked_squares_as_background(self):
        g = self._start_locked_game()
        main.ui.draw_board(g)
        # Locked square (0,0) matches the background color.
        self.assertEqual(g.screen.get_at(self._cell_center(0, 0))[:3], main.BG_COLOR)
        # Unlocked square (4,7) keeps the normal board fill.
        self.assertEqual(g.screen.get_at(self._cell_center(4, 7))[:3],
                         main.MARBLE_BOX_COLOR)
        # The grid overlay stays across locked squares so the player can see
        # the unit boundaries: the vertical line between locked col 3 and
        # unlocked col 4 is the thin grid-line color.
        line_x = main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE
        self.assertEqual(g.screen.get_at((line_x, self._cell_center(4, 7)[1]))[:3],
                         (30, 30, 30))

    def test_draw_board_borders_the_playable_region_thickly(self):
        # Every side of an unlocked square that faces a LOCKED one gets the
        # board's own thick border (BORD_WIDTH thick, the outer border's own
        # weight and colour), and the band lies ENTIRELY in the void just
        # outside the playable region — flush with the shared edge — so a block
        # or marble placed on the region's edge can never cover it.
        g = self._start_locked_game()
        main.ui.draw_board(g)
        border = (30, 30, 30)
        width = main.BORD_WIDTH
        x0, y0 = main.MARBLE_BOX_COORDS[0], main.MARBLE_BOX_COORDS[1]
        checked = 0
        for gy in range(main.GRID_HEIGHT):
            for gx in range(main.GRID_WIDTH):
                if g.is_cell_locked(gx, gy):
                    continue
                left, top = x0 + gx * main.GRID_SIZE, y0 + gy * main.GRID_SIZE
                right, bottom = left + main.GRID_SIZE, top + main.GRID_SIZE
                cx = left + main.GRID_SIZE // 2
                cy = top + main.GRID_SIZE // 2
                sides = []
                if gx > 0 and g.is_cell_locked(gx - 1, gy):
                    sides.append([(left - step, cy) for step in range(1, width + 1)]
                                 + [(left - width - 1, cy), (left + 1, cy)])
                if gx < main.GRID_WIDTH - 1 and g.is_cell_locked(gx + 1, gy):
                    sides.append([(right + step, cy) for step in range(width)]
                                 + [(right + width, cy), (right - 1, cy)])
                if gy > 0 and g.is_cell_locked(gx, gy - 1):
                    sides.append([(cx, top - step) for step in range(1, width + 1)]
                                 + [(cx, top - width - 1), (cx, top + 1)])
                if gy < main.GRID_HEIGHT - 1 and g.is_cell_locked(gx, gy + 1):
                    sides.append([(cx, bottom + step) for step in range(width)]
                                 + [(cx, bottom + width), (cx, bottom - 1)])
                for points in sides:
                    checked += 1
                    band, just_outside, inside = points[:-2], points[-2], points[-1]
                    for point in band:
                        self.assertEqual(g.screen.get_at(point)[:3], border,
                                         (gx, gy, point))
                    # ...one pixel further out is void again, and the square
                    # itself is untouched right from its edge inwards.
                    self.assertEqual(g.screen.get_at(just_outside)[:3],
                                     main.BG_COLOR, (gx, gy))
                    self.assertEqual(g.screen.get_at(inside)[:3],
                                     main.MARBLE_BOX_COLOR, (gx, gy))
        self.assertGreater(checked, 0)
        # The overlay across the locked squares themselves stays thin: two
        # squares away from the playable region only the line's own pixel is
        # dark, and its neighbours are still the void colour (sampled mid-cell
        # so the perpendicular grid line is not in the way).
        far_x = x0 + 2 * main.GRID_SIZE
        far_y = y0 + 2 * main.GRID_SIZE + 5
        self.assertEqual(g.screen.get_at((far_x, far_y))[:3], border)
        self.assertEqual(g.screen.get_at((far_x - 1, far_y))[:3], main.BG_COLOR)
        self.assertEqual(g.screen.get_at((far_x + 1, far_y))[:3], main.BG_COLOR)

    def test_the_locked_boundarys_corners_are_filled(self):
        # Each band runs a full border width past both ends, so the outline's
        # corners are solid instead of notched: the whole corner square just
        # outside the start region's top-left corner is border.
        g = self._start_locked_game()
        main.ui.draw_board(g)
        left = main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE
        top = main.MARBLE_BOX_COORDS[1] + 6 * main.GRID_SIZE
        for dx in range(1, main.BORD_WIDTH + 1):
            for dy in range(1, main.BORD_WIDTH + 1):
                self.assertEqual(g.screen.get_at((left - dx, top - dy))[:3],
                                 (30, 30, 30), (dx, dy))

    def test_the_all_finishes_trial_keeps_the_locked_boundary_dark(self):
        # The all-finishes trial paints the box's OUTER border in the finish
        # colour, because that is the edge a marble finishes on. The walls
        # against the locked squares are invisible physics walls that never
        # finish anything (see Game._board_wall_blocks), so the boundary between
        # the playable region and the void stays the board's dark border colour.
        g = self._start_locked_game()
        finish = main.Scorer.color(main.Scorer.FINISH)
        main.ui.draw_board(g, finish)
        x0, y0 = main.MARBLE_BOX_COORDS[0], main.MARBLE_BOX_COORDS[1]
        self.assertEqual(g.screen.get_at((x0 + 20, y0 - main.BORD_WIDTH // 2))[:3],
                         finish)
        left = x0 + 4 * main.GRID_SIZE
        right = x0 + 6 * main.GRID_SIZE
        cy = y0 + 6 * main.GRID_SIZE + 20
        self.assertEqual(g.screen.get_at((left - 1, cy))[:3], (30, 30, 30))
        self.assertEqual(g.screen.get_at((right + 1, cy))[:3], (30, 30, 30))
        self.assertEqual(g.screen.get_at((left + 1, cy))[:3],
                         main.MARBLE_BOX_COLOR)

    def test_draw_board_matches_plain_board_when_fully_unlocked(self):
        g = self.game  # a plain Game() has the whole board unlocked
        main.ui.draw_board(g)
        self.assertEqual(g.screen.get_at(self._cell_center(0, 0))[:3],
                         main.MARBLE_BOX_COLOR)
        self.assertEqual(g.screen.get_at(self._cell_center(9, 14))[:3],
                         main.MARBLE_BOX_COLOR)
        self.assertFalse(g.board_locked())


if __name__ == "__main__":
    unittest.main()
