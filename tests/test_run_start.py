"""When a run starts, and when its level is loaded.

Two user requests:
  "create a marble only when the player presses t to start the run. delete the
   marble when the run is reset."
  "load the level beforehand instead of when the game updates so that the level
   does not appear to change randomly."

The first is about the marble's lifetime: one exists exactly while a run is
being PLAYED, so the build phase never shows one. The second is about the
level's lifetime: it is laid out when it becomes the current level (a brand-new
game, and the CONTINUE between runs) and every later layout only puts that same
one back, so pressing T cannot move the board the player has been building on.
"""

import save_system

from tests.game_test_case import *  # noqa: F401,F403


class RunStartCase(GameTestCase):
    """Helpers: a start block to run from, and the level's own layout."""

    def _start_block(self):
        """Put a Start block on a free unlocked square, so a run can start."""
        g = self.game
        cell = next(c for c in sorted(g.unlocked_cells)
                    if g.item_at_cell(c) is None and c not in g.grid)
        block = main.Block(cell[0], cell[1], scorer=main.Scorer.START)
        g.grid[cell] = block
        return block

    def _level_layout(self, game=None):
        """Where the level's own things stand: (props, structures, enemies)."""
        game = game or self.game
        props = sorted(
            (cell, int(block.shape))
            for cell, block in game.grid.items()
            if getattr(block, "is_level_prop", False))
        structures = sorted(
            (item.value, game.item_cell(item))
            for item in game.shop.items
            if getattr(item, "is_level_structure", False))
        enemies = sorted(
            (cell, block.kind)
            for cell, block in game.grid.items()
            if getattr(block, "is_enemy", False))
        return props, structures, enemies

    def _level_with_props(self):
        """A level whose own furniture is on the board, laid out."""
        g = self.game
        level = next(level for level in main.LEVELS if level.props)
        g.run_number = level.number - 1
        g._refresh_run_target()
        g._begin_level()
        return level


class MarbleLifetimeTests(RunStartCase):
    """A marble exists only while the run it plays is in flight."""

    def test_the_build_phase_has_no_marble(self):
        # GameTestCase starts a game and leaves it in the build phase.
        self.assertFalse(self.game.run_active)
        self.assertEqual(self.game.marbles, [])

    def test_pressing_t_releases_exactly_one_marble(self):
        self._start_block()

        self._press(main.pygame.K_t)

        self.assertTrue(self.game.run_active)
        self.assertEqual(len(self.game.marbles), 1)

    def test_pressing_r_takes_the_marble_away(self):
        self._start_block()
        self._press(main.pygame.K_t)
        self.assertEqual(len(self.game.marbles), 1)

        self._press(main.pygame.K_r)

        # A restart is a reset: back to building, with no marble on the board.
        self.assertEqual(self.game.marbles, [])
        self.assertFalse(self.game.run_active)
        self.assertFalse(self.game.run_complete)

    def test_a_finished_run_keeps_its_marble_until_the_next_one(self):
        # The run that was just played still shows where it ended; it is the
        # NEXT run that starts without one (see _cycle_deck).
        self._start_block()
        self._press(main.pygame.K_t)
        marble = self.game.marbles[0]
        marble.finished = True
        self.game.run_time = main.TIME_IDEAL
        self.game.score_chips = 0
        self.game.score_mult = 1
        self.game._handle_block_contacts([])

        self.assertTrue(self.game.awaiting_after_run)
        self.assertIn(marble, self.game.marbles)

    def test_the_discard_helper_clears_the_marble_and_the_run(self):
        self._start_block()
        self.game.reset_run()
        self.assertTrue(self.game.marbles)

        self.game._discard_run()

        self.assertEqual(self.game.marbles, [])
        self.assertFalse(self.game.run_active)


class LevelLoadedBeforehandTests(RunStartCase):
    """The level is on the board before the run, and laying it out again keeps it."""

    def _brand_new_game(self):
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        return self.game

    def test_a_brand_new_game_already_has_its_level(self):
        g = self._brand_new_game()
        level = g.current_level()
        _props, structures, enemies = self._level_layout(g)

        self.assertEqual(g.level_number, level.number)
        # The level's own squares are open before the first frame...
        self.assertTrue({g._level_cell(dx, dy) for dx, dy in level.cells}
                        <= g.unlocked_cells)
        # ...and its structures and its cast are already standing on it.
        self.assertEqual(len(structures), main.STRUCTURES_PER_RUN)
        self.assertEqual(sorted(kind for _cell, kind in enemies),
                         sorted(level.enemies))

    def test_starting_the_run_does_not_change_the_level(self):
        g = self._brand_new_game()
        self._start_block()
        before = self._level_layout(g)

        self._press(main.pygame.K_t)

        self.assertTrue(g.run_active)
        self.assertEqual(self._level_layout(g), before)

    def test_building_on_the_board_cannot_push_the_level_about(self):
        g = self._brand_new_game()
        self._start_block()
        before = self._level_layout(g)
        # The player builds in the build phase, then starts the run.
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        g.toolbox.add(block)
        g.ensure_board_cells()
        cell = next(c for c in sorted(g.unlocked_cells)
                    if g.item_at_cell(c) is None and c not in g.grid)
        g._equip_block(block)
        g._place_block_at(*cell)

        g.reset_run()

        self.assertEqual(self._level_layout(g), before)

    def test_a_reset_puts_the_enemies_back_at_full_health(self):
        g = self._brand_new_game()
        self._start_block()
        g.reset_run()
        enemy = g.live_enemies()[0]
        cell = (enemy.x, enemy.y)
        enemy.hp = 1
        enemy.float_x += 12.0          # a patroller that has slid along its row

        g.reset_run()

        back = g.grid.get(cell)
        self.assertIsNotNone(back)
        self.assertTrue(back.is_enemy)
        self.assertEqual(back.kind, enemy.kind)
        self.assertEqual(back.hp, back.max_hp)
        self.assertEqual(back.float_x, float(back.home_x))

    def test_a_destroyed_prop_comes_back_on_its_own_square(self):
        self._level_with_props()
        self._start_block()
        prop_cell = next(cell for cell, block in self.game.grid.items()
                         if getattr(block, "is_level_prop", False))
        self.game.grid.pop(prop_cell)

        self.game.reset_run()

        self.assertIn(prop_cell, self.game.grid)
        self.assertTrue(getattr(self.game.grid[prop_cell], "is_level_prop", False))

    def test_the_structures_keep_the_squares_they_stand_on(self):
        g = self._brand_new_game()
        self._start_block()

        def squares():
            return sorted(g.item_cell(item) for item in g.shop.items
                          if getattr(item, "is_level_structure", False))

        first = squares()
        g.reset_run()
        g.reset_run()

        self.assertEqual(squares(), first)
        self.assertEqual(len(first), main.STRUCTURES_PER_RUN)

    def test_the_higher_levels_are_laid_out_the_same_way(self):
        # A run deep into the game (a different level shape and cast) is stable
        # too: CONTINUE lays the next level out once, and the run start puts it
        # back unchanged.
        g = self.game
        self._level_with_props()
        self._start_block()
        before = self._level_layout(g)

        g.reset_run()

        self.assertEqual(self._level_layout(g), before)
