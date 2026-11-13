"""Board units: unlocking squares and the locked-board rules.

Split out of the old tests/test_run_scoring.py; the shared imports live in
tests/game_test_case.py (this class owns its own setUp).
"""

from tests.game_test_case import *  # noqa: F401,F403


class BoardTests(unittest.TestCase):
    """The dynamic board: a new game starts with a centered unlocked region,
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
        """A brand-new game whose board is locked to its centered start region."""
        # Mirrors save_system.start_new_game_in_slot (no files are written).
        self.game.title_screen = False
        self.game.trials_enabled = False
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        return self.game

    def _start_region(self):
        """The centered starting region: BOARD_START_WIDTH x BOARD_START_HEIGHT."""
        x0 = (main.GRID_WIDTH - main.BOARD_START_WIDTH) // 2
        y0 = (main.GRID_HEIGHT - main.BOARD_START_HEIGHT) // 2
        return {(x0 + dx, y0 + dy)
                for dx in range(main.BOARD_START_WIDTH)
                for dy in range(main.BOARD_START_HEIGHT)}

    def _start_cell(self):
        """A square of the starting region — the top-left one.

        The board's own size decides where the region sits, so a test that needs
        a PLAYABLE square asks for one rather than naming a cell.
        """
        return ((main.GRID_WIDTH - main.BOARD_START_WIDTH) // 2,
                (main.GRID_HEIGHT - main.BOARD_START_HEIGHT) // 2)

    def _level_region(self, level):
        """The board squares a level opens (its own shape, offset from centre)."""
        cells = set()
        for dx, dy in level.cells:
            cell = (main.GRID_WIDTH // 2 + dx, main.GRID_HEIGHT // 2 + dy)
            if 0 <= cell[0] < main.GRID_WIDTH and 0 <= cell[1] < main.GRID_HEIGHT:
                cells.add(cell)
        return cells

    def _far_corner(self):
        """The board's bottom-right square (always locked at the start)."""
        return (main.GRID_WIDTH - 1, main.GRID_HEIGHT - 1)

    def _cell_center(self, gx, gy):
        return (main.MARBLE_BOX_COORDS[0] + gx * main.GRID_SIZE + main.GRID_SIZE // 2,
                main.MARBLE_BOX_COORDS[1] + gy * main.GRID_SIZE + main.GRID_SIZE // 2)

    def _item_pos(self, item):
        """A screen point on the board square ``item`` stands on."""
        self.game.ensure_board_cells()
        cell = self.game.item_cell(item)
        self.assertIsNotNone(cell, f"{item!r} has no board square")
        return self._cell_center(*cell)

    def test_default_game_starts_with_full_board_unlocked(self):
        g = self.game  # a plain Game() (tests construct one directly)
        self.assertEqual(len(g.unlocked_cells), main.GRID_WIDTH * main.GRID_HEIGHT)
        self.assertFalse(g.board_locked())
        self.assertFalse(g.is_cell_locked(0, 0))
        self.assertFalse(g.is_cell_locked(*self._far_corner()))

    def test_new_game_locks_board_to_its_centered_start_region(self):
        g = self._start_locked_game()
        # The region is a real subset of the board, so there is a locked ring to
        # buy open with Board Units.
        self.assertLess(main.BOARD_START_WIDTH, main.GRID_WIDTH)
        self.assertLess(main.BOARD_START_HEIGHT, main.GRID_HEIGHT)
        # A new game opens its start region AND the squares of the level its
        # first run plays: the level is loaded before the first frame, not when
        # the run starts (see Game._reset_board_to_start / _begin_level).
        self.assertTrue(self._start_region() <= g.unlocked_cells)
        self.assertEqual(
            g.unlocked_cells,
            self._start_region() | self._level_region(g.current_level()))
        self.assertTrue(g.board_locked())
        self.assertEqual(g.board_units, 0)
        # Every square of the region is playable, and the squares all around it
        # are still locked.
        x0, y0 = self._start_cell()
        for cell in self._start_region():
            self.assertFalse(g.is_cell_locked(*cell))
        self.assertTrue(g.is_cell_locked(x0 - 1, y0))
        self.assertTrue(g.is_cell_locked(x0 + main.BOARD_START_WIDTH, y0))
        self.assertTrue(g.is_cell_locked(x0, y0 - 1))
        self.assertTrue(g.is_cell_locked(x0, y0 + main.BOARD_START_HEIGHT))
        self.assertTrue(g.is_cell_locked(*self._far_corner()))
        # It is centered: the locked margin above/below (and left/right) is the
        # same, bar the odd square the board cannot split in two.
        self.assertLessEqual(
            abs(y0 - (main.GRID_HEIGHT - main.BOARD_START_HEIGHT - y0)), 1)
        self.assertLessEqual(
            abs(x0 - (main.GRID_WIDTH - main.BOARD_START_WIDTH - x0)), 1)
        # Every item a new game hands the player lies on an unlocked square: the
        # board IS the inventory, and a locked square can hold nothing.
        self.assertTrue(g.owned_items())
        for item in g.owned_items():
            cell = g.item_cell(item)
            self.assertIsNotNone(cell, item)
            self.assertFalse(g.is_cell_locked(*cell), item)
        self.assertEqual(g.toolbox.stash, [])

    def test_unlock_cell_works_on_any_square_and_rebuilds_walls(self):
        g = self._start_locked_game()
        # A far corner square is unlockable even though it is not adjacent.
        far = self._far_corner()
        self.assertTrue(g.is_cell_locked(*far))
        self.assertTrue(g._unlock_cell(*far))
        self.assertFalse(g.is_cell_locked(*far))
        # Unlocking an already-unlocked square reports False.
        self.assertFalse(g._unlock_cell(*far))
        # The wall cache covers the FRONTIER: every locked square that shares an
        # edge with an unlocked one. The board is infinite, so walling every
        # locked square is impossible (and pointless) — a marble can only reach
        # a locked square through the frontier.
        walls = g._board_wall_blocks()
        wall_cells = {(w.x, w.y) for w in walls}
        self.assertEqual(wall_cells, set(g._locked_adjacent_cells()))
        self.assertTrue(wall_cells)
        self.assertFalse(wall_cells & g.unlocked_cells)
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

    def test_the_board_unit_button_is_always_buyable(self):
        g = self._start_locked_game()
        g.cash = 60
        # The Board Unit is a BUTTON in the top bar (user request: "make board
        # slots a button in the top bar instead of a shop item"), so it is not on
        # the shelf at all and can be bought as often as the cash allows.
        self.assertFalse([i for i in g.shop.items
                          if getattr(i, "kind", None) == "unit"])
        self._click(main.BOARD_UNIT_BUTTON_RECT.center)
        self.assertEqual(g.board_units, 1)
        self.assertEqual(g.cash, 52)
        self.assertIn("x1", main.ui.board_unit_button_label(g))
        # It survives a shop refresh (it is not part of the shelf), and the
        # button is still there to be pressed again.
        g._refresh_shop()  # costs $20, so top the cash back up first
        g.cash = 60
        self._click(main.BOARD_UNIT_BUTTON_RECT.center)
        self.assertEqual(g.board_units, 2)
        self.assertEqual(g.cash, 52)

    def test_the_board_unit_button_says_its_price_and_refuses_without_cash(self):
        g = self._start_locked_game()
        g.cash = 3
        self.assertIn(f"${g._board_unit_price()}",
                      main.ui.board_unit_button_label(g))

        self._click(main.BOARD_UNIT_BUTTON_RECT.center)

        self.assertEqual(g.board_units, 0)
        self.assertIn("Need $", g.shop_message)


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

    def test_clicking_a_locked_square_with_a_block_in_hand_deselects(self):
        # A click on anything that is not an item turns every switch off while
        # something is selected (user request), and a locked square is no
        # exception — even with a Board Unit owned. The next click, with nothing
        # selected, is the one that unlocks it.
        g = self._start_locked_game()
        g.cash = 60
        g._buy_board_unit()
        block = g.owned_items()[0]
        g._equip_block(block)
        self.assertTrue(g.has_selected)
        self._click(self._cell_center(0, 0))
        self.assertTrue(g.is_cell_locked(0, 0))  # not unlocked
        self.assertEqual(g.board_units, 1)       # unit kept
        self.assertFalse(g.has_selected)         # the block was deselected
        # With nothing selected the same click unlocks.
        self._click(self._cell_center(0, 0))
        self.assertFalse(g.is_cell_locked(0, 0))
        self.assertEqual(g.board_units, 0)
        self.assertNotIn((0, 0), g.grid)  # nothing was put down


    def test_cannot_place_block_on_locked_square(self):
        g = self._start_locked_game()
        g.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 0, "Wall")
        g.toolbox.add(block)
        g._equip_block(block)
        self.assertTrue(g.has_selected)
        # Clicking a locked square must NOT place the block (and, because the
        # block is selected, it deselects instead — see
        # test_clicking_a_locked_square_with_a_block_in_hand_deselects).
        self._click(self._cell_center(0, 0))
        self.assertNotIn((0, 0), g.grid)
        # Clicking an unlocked square places it normally. (The block's own square
        # is not usable: a click on an item is that item's switch, see
        # _toggle_item_selection, so a free square is picked.)
        g._equip_block(block)
        cell = next(c for c in sorted(self._start_region())
                    if g.item_at_cell(c) is None)
        self._click(self._cell_center(*cell))
        self.assertIn(cell, g.grid)
        self.assertEqual(g.grid[cell].shape, main.Shape.RECT)

    def test_locked_board_resets_each_new_game(self):
        g = self._start_locked_game()
        opened = set(g.unlocked_cells)
        g._unlock_cell(0, 0)
        g._unlock_cell(*self._far_corner())
        g.board_units = 3
        self.assertEqual(len(g.unlocked_cells), len(opened) + 2)
        # Starting a NEW game returns the board to its opening state ? the start
        # region plus the level the first run plays, which is loaded with the
        # game rather than when the run starts (see Game._reset_board_to_start).
        save_system.start_new_game_in_slot(g, 1)
        self.assertEqual(
            g.unlocked_cells,
            self._start_region() | self._level_region(g.current_level()))
        self.assertEqual(g.board_units, 0)
        self.assertNotIn((0, 0), g.unlocked_cells)

    def test_marble_is_confined_to_unlocked_region(self):
        g = self._start_locked_game()
        g.grid.clear()
        # A Start in the top row of the starting region; no Finish, so the
        # marble just falls and must come to rest on the locked floor.
        cell = self._start_cell()
        g.grid[cell] = main.Block(*cell, shape=main.Shape.RECT,
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
        # It should have come to rest well above the wall under the region.
        floor = cell[1] + main.BOARD_START_HEIGHT
        for marble in g.marbles:
            self.assertLess(
                marble.position[1],
                main.MARBLE_BOX_COORDS[1] + floor * main.GRID_SIZE)

    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_cozy_magnitude_card_fires_3x_base_on_a_small_board(self):
        g = self._start_locked_game()
        # A start region is 10 or fewer unlocked units, so a Cozy +Mult card
        # fires at the start of the run with its 3x base (+12 mult).
        value = main.condition_scorer_card(main.Condition.COZY, main.Scorer.MULT_ADD)
        g.cards.append(main.CardItem(value, 50))
        g.grid[self._start_cell()] = main.Block(*self._start_cell(),
                                                scorer=main.Scorer.START)
        self.assertTrue(g.reset_run(False))
        self.assertAlmostEqual(g.score_mult, 1 + 12)  # 3x the +4 mult base

    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_cozy_magnitude_card_is_silent_on_a_big_board(self):
        g = self._start_locked_game()
        value = main.condition_scorer_card(main.Condition.COZY, main.Scorer.MULT_ADD)
        g.cards.append(main.CardItem(value, 50))
        g.grid[self._start_cell()] = main.Block(*self._start_cell(),
                                                scorer=main.Scorer.START)
        # Expand the board past 10 unlocked units; Cozy no longer fires.
        for x, y in ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4)):
            g._unlock_cell(x, y)
        self.assertGreater(len(g.unlocked_cells), 10)
        self.assertTrue(g.reset_run(False))
        self.assertAlmostEqual(g.score_mult, 1)

    def test_locked_adjacent_cells_are_the_reachable_frontier(self):
        g = self._start_locked_game()
        frontier = g._locked_adjacent_cells()
        self.assertTrue(frontier)  # the start region has locked neighbors
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

    def test_continue_hands_over_drill_and_conquistador_board_units(self):
        # User request: "make the drill scorer give 2x board square" and "make
        # conquistador give 4x board square" — the Drill-scorer touches bank
        # drill_run_units that only pay out after a run, and the Conquistador
        # card adds 4 more after every run. Both hand over BOARD UNITS now
        # rather than unlocking squares themselves (user request: "make all
        # items that unlock random board squares give board squares instead").
        g = self._start_locked_game()
        before_squares = len(g.unlocked_cells)  # the start region
        before_units = g.board_units
        g.drill_run_units = 2
        g.cards.append(main.CardItem(main.Card.CONQUISTADOR, 56))
        g.run_complete = True
        g.awaiting_after_run = True
        # The next LEVEL also opens its own squares when CONTINUE makes it
        # current (see Game._begin_level); this test measures the run's own
        # rewards, so the level is left out of it.
        with mock.patch.object(main.Game, "_begin_level"), \
                mock.patch("main.random.random", return_value=0.9):
            g._continue_run()
        self.assertEqual(g.board_units, before_units + 2 + 4)
        self.assertEqual(len(g.unlocked_cells), before_squares,
                         "the run's rewards unlocked squares themselves")
        self.assertEqual(g.drill_run_units, 0)
        self.assertIn("Board Unit", g.shop_message)
        self.assertIn("from the drill", g.shop_message)
        self.assertIn("from Conquistador", g.shop_message)

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

    def test_a_bomb_still_blasts_its_own_radius_beside_a_drill(self):
        # A Bomb is one of the things that still unlocks squares itself ("unless
        # otherwise stated"): it opens the radius around it, while the drill's
        # touches hand over Board Units instead (see _grant_board_units). The
        # blast still resolves first, so its message survives.
        g = self._start_locked_game()
        before = set(g.unlocked_cells)
        # A square on the edge of the start region, so the blast has locked
        # neighbours of its own to open.
        corner = self._start_cell()
        bomb = (corner[0], corner[1] + 1)
        g.bomb_cells = {bomb}
        g.grid[bomb] = main.Block(bomb[0], bomb[1], scorer=main.Scorer.BOMB)
        g.drill_run_units = 2
        before_units = g.board_units

        g.run_complete = True
        g.awaiting_after_run = True
        # (The next level opens its own squares on CONTINUE; this test is about
        # what the bomb and the drill add on top, so the level is left out.)
        with mock.patch.object(main.Game, "_begin_level"), \
                mock.patch("main.random.random", return_value=0.9):
            g._continue_run()

        radius = {(bomb[0] + dx, bomb[1] + dy)
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        gained = g.unlocked_cells - before
        # The whole radius the bomb could open is open, and nothing else...
        self.assertEqual(gained,
                         {cell for cell in radius if cell not in before})
        self.assertEqual(g.bomb_cells, set())
        # ...while the drill paid in units instead of squares.
        self.assertEqual(g.board_units, before_units + 2)
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
                         "Board expanded by 2 Board Units (2 from the drill)")

        g = self._start_locked_game()
        g.cards.append(main.CardItem(main.Card.CONQUISTADOR, 56))
        run_end(g)
        self.assertEqual(g.shop_message,
                         "Board expanded by 4 Board Units (4 from Conquistador)")

        # The bomb's blast (Chebyshev radius 1, so diagonals count) opens the
        # locked squares around it — however many of the eight are still
        # locked.
        g = self._start_locked_game()
        bomb = self._start_cell()
        g.bomb_cells = {bomb}
        g.grid[bomb] = main.Block(bomb[0], bomb[1], scorer=main.Scorer.BOMB)
        blasted = sum(
            1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if (dx or dy)
            and 0 <= bomb[0] + dx < main.GRID_WIDTH
            and 0 <= bomb[1] + dy < main.GRID_HEIGHT
            and g.is_cell_locked(bomb[0] + dx, bomb[1] + dy))
        run_end(g)
        self.assertEqual(g.shop_message,
                         f"Board expanded by {blasted} squares "
                         f"({blasted} from the bomb blast)")

        # Both at once: squares and units are reported side by side.
        g = self._start_locked_game()
        g.bomb_cells = {bomb}
        g.grid[bomb] = main.Block(bomb[0], bomb[1], scorer=main.Scorer.BOMB)
        g.drill_run_units = 2
        run_end(g)
        self.assertEqual(
            g.shop_message,
            f"Board expanded by {blasted} squares and 2 Board Units "
            f"({blasted} from the bomb blast, 2 from the drill)")

        # Nothing unlocked by the run end leaves the message alone, and one
        # square still reads in the singular.
        g = self._start_locked_game()
        g.shop_message = ""
        g._announce_board_expansion(0, 0, 0)
        self.assertEqual(g.shop_message, "")
        g._announce_board_expansion(1, 0, 0)
        self.assertEqual(g.shop_message,
                         "Board expanded by 1 square (1 from the bomb blast)")
        g._announce_board_expansion(0, 0, 2)
        self.assertEqual(g.shop_message,
                         "Board expanded by 2 Board Units (2 from Conquistador)")

    def test_draw_board_paints_locked_squares_as_background_without_a_trial(self):
        g = self._start_locked_game()
        main.ui.draw_board(g)
        # With no trial there is no tile colour to match: locked square (0,0)
        # falls back to the void, exactly as it always has.
        self.assertEqual(g.screen.get_at(self._cell_center(0, 0))[:3], main.BG_COLOR)
        # An unlocked square of the start region keeps the normal board fill.
        cell = self._start_cell()
        self.assertEqual(g.screen.get_at(self._cell_center(*cell))[:3],
                         main.MARBLE_BOX_COLOR)
        # The grid overlay stays across locked squares so the player can see
        # the unit boundaries: a grid line between two locked squares of the
        # margin left of the region is the thin grid-line color.
        line_x = main.MARBLE_BOX_COORDS[0] + 1 * main.GRID_SIZE
        self.assertEqual(g.screen.get_at((line_x,
                                          self._cell_center(*cell)[1]))[:3],
                         (30, 30, 30))

    def test_locked_squares_wear_the_backgrounds_pattern(self):
        # A locked square is not board — it is the void the board floats in — so
        # it is painted with exactly what the screen behind the board is painted
        # with (user request: "locked board squares having the background's
        # pattern on them"). An unlocked square keeps the trial's panel tint, so
        # the playable region still reads as raised.
        g = self._start_locked_game()
        g.trials_enabled = True
        cell = self._start_cell()
        locked_centre = self._cell_center(0, 0)
        for trial in main.Trial.ORDER:
            g.current_trial = trial
            main.ui.draw_background(g)
            behind = g.screen.get_at(locked_centre)[:3]
            main.ui.draw_board(g)
            self.assertEqual(g.screen.get_at(locked_centre)[:3], behind, trial)
            self.assertEqual(
                g.screen.get_at(self._cell_center(*cell))[:3],
                components.Trial.panel_color(trial), trial)

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
        far_x = x0 + 1 * main.GRID_SIZE
        far_y = y0 + main.GRID_SIZE + 5
        self.assertEqual(g.screen.get_at((far_x, far_y))[:3], border)
        self.assertEqual(g.screen.get_at((far_x - 1, far_y))[:3], main.BG_COLOR)
        self.assertEqual(g.screen.get_at((far_x + 1, far_y))[:3], main.BG_COLOR)

    def test_the_locked_boundarys_corners_are_filled(self):
        # Each band runs a full border width past both ends, so the outline's
        # corners are solid instead of notched: the whole corner square just
        # outside the start region's top-left corner is border.
        g = self._start_locked_game()
        main.ui.draw_board(g)
        cell_x, cell_y = self._start_cell()
        left = main.MARBLE_BOX_COORDS[0] + cell_x * main.GRID_SIZE
        top = main.MARBLE_BOX_COORDS[1] + cell_y * main.GRID_SIZE
        for dx in range(1, main.BORD_WIDTH + 1):
            for dy in range(1, main.BORD_WIDTH + 1):
                self.assertEqual(g.screen.get_at((left - dx, top - dy))[:3],
                                 (30, 30, 30), (dx, dy))

    def test_the_all_finishes_trial_keeps_the_locked_boundary_dark(self):
        # The all-finishes trial paints the WINDOW's outer border in the finish
        # colour, because that is the edge a marble finishes on. The walls
        # against the locked squares are invisible physics walls that never
        # finish anything (see Game._board_wall_blocks), so the boundary between
        # the playable region and the void stays the board's dark border colour.
        g = self._start_locked_game()
        finish = main.Scorer.color(main.Scorer.FINISH)
        main.ui.draw_board(g, finish)
        view = g.board_viewport()
        # The frame is drawn inside the window's own edge.
        self.assertEqual(g.screen.get_at((view.left + 2, view.top + 30))[:3],
                         finish)
        cell_x, cell_y = self._start_cell()
        left, top = g.cell_to_screen(cell_x, cell_y)
        right = left + main.BOARD_START_WIDTH * main.GRID_SIZE
        cy = top + 20
        self.assertEqual(g.screen.get_at((left - 1, cy))[:3], (30, 30, 30))
        self.assertEqual(g.screen.get_at((right + 1, cy))[:3], (30, 30, 30))
        self.assertEqual(g.screen.get_at((left + 1, cy))[:3],
                         main.MARBLE_BOX_COLOR)

    def test_draw_board_matches_plain_board_when_fully_unlocked(self):
        g = self.game  # a plain Game() has the whole board unlocked
        main.ui.draw_board(g)
        self.assertEqual(g.screen.get_at(self._cell_center(0, 0))[:3],
                         main.MARBLE_BOX_COLOR)
        far = self._cell_center(*self._far_corner())
        self.assertEqual(g.screen.get_at(far)[:3], main.MARBLE_BOX_COLOR)
        self.assertFalse(g.board_locked())
