"""Board units: unlocking squares and the locked-board rules.

Split out of the old tests/test_run_scoring.py; the shared imports live in
tests/game_test_case.py (this class owns its own setUp).
"""

from tests.game_test_case import *  # noqa: F401,F403


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
        # Building a Game also creates the empty save-slot placeholders, so
        # point the slots at the throwaway folder too.
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

    def test_draw_board_paints_locked_squares_as_background_without_a_trial(self):
        g = self._start_locked_game()
        main.ui.draw_board(g)
        # With no trial there is no tile colour to match: locked square (0,0)
        # falls back to the void, exactly as it always has.
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

    def test_locked_squares_take_the_trials_colour_a_step_darker(self):
        # While a trial runs, a locked square is filled with the SAME colour
        # family as the board it sits in — the trial's colour, a step below the
        # panel tint — instead of punching the red void through the palette.
        # It must still read as unlit next to an unlocked square, so locked is
        # darker than the panel for every trial, the near-white all-finishes
        # one included (whose panel is darkened rather than lightened, which is
        # why the locked shade is derived from the panel and not from the tile).
        g = self._start_locked_game()
        g.trials_enabled = True
        for trial in main.Trial.ORDER:
            g.current_trial = trial
            panel = components.Trial.panel_color(trial)
            locked = components.Trial.locked_color(trial)
            self.assertIsNotNone(locked, trial)
            self.assertTrue(all(lo < pa for lo, pa in zip(locked, panel)),
                            (trial, locked, panel))
            main.ui.draw_board(g)
            self.assertEqual(g.screen.get_at(self._cell_center(0, 0))[:3], locked,
                             trial)
            self.assertEqual(g.screen.get_at(self._cell_center(4, 7))[:3], panel,
                             trial)

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
