"""The board's window: an infinite board, the camera that scrolls it, and the bar.

The board is as large as the player wants it to be — its squares are addressed by
any integer coordinate — and what is drawn is the WINDOW onto it (see
Game.cell_to_screen / Game.pan_board). Dragging empty board space scrolls the
view; the game's furniture lives in a bar along the top of the screen and the
board fills everything under it.
"""

from tests.game_test_case import *  # noqa: F401,F403


class CameraTests(GameTestCase):
    """Screen <-> square conversion, and dragging the board."""

    def _cell_centre(self, gx, gy):
        x, y = self.game.cell_to_screen(gx, gy)
        return (x + main.GRID_SIZE // 2, y + main.GRID_SIZE // 2)

    def _drag(self, start, delta, steps=4):
        """Press at ``start``, move by ``delta`` in steps, and release."""
        self._click(start)
        for step in range(1, steps + 1):
            pos = (start[0] + delta[0] * step // steps,
                   start[1] + delta[1] * step // steps)
            event = mock.Mock()
            event.type = main.pygame.MOUSEMOTION
            event.buttons = (1, 0, 0)
            with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
                 mock.patch("main.pygame.event.get", return_value=[event]):
                self.game.handle_events()
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONUP
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(start[0] + delta[0], start[1] + delta[1])), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def _empty_spot(self):
        """A screen position over the board with no item on it."""
        view = self.game.board_viewport()
        return (view.right - 12, view.bottom - 12)

    def test_a_new_game_starts_with_the_camera_at_rest(self):
        self.assertEqual(self.game.camera, (0, 0))
        # Square (0, 0) is at the window's top-left corner, and any other square
        # is that many grid steps along.
        self.assertEqual(self.game.cell_to_screen(0, 0),
                         (main.MARBLE_BOX_COORDS[0], main.MARBLE_BOX_COORDS[1]))
        self.assertEqual(self.game.cell_to_screen(3, 2),
                         (main.MARBLE_BOX_COORDS[0] + 3 * main.GRID_SIZE,
                          main.MARBLE_BOX_COORDS[1] + 2 * main.GRID_SIZE))

    def test_screen_and_cell_conversions_agree_under_a_pan(self):
        self.game.pan_board(-120, 75)
        for cell in ((0, 0), (5, 3), (-4, 9)):
            x, y = self.game.cell_to_screen(*cell)
            self.assertEqual(
                self.game.screen_to_cell((x + main.GRID_SIZE // 2,
                                          y + main.GRID_SIZE // 2)), cell)

    def test_dragging_empty_board_space_moves_the_board(self):
        start = self._empty_spot()
        self._drag(start, (-120, -60))
        # The board is grabbed, not scrolled: dragging the cursor left/up pulls
        # the board left/up with it, which moves the CAMERA the other way (user
        # request: "reverse the direction that the board moves").
        self.assertEqual(self.game.camera, (120, 60))
        # The window is what moved: no square of the board changed hands, and the
        # item that was lying on one is still on it — now drawn somewhere else.
        item = self.game.owned_items()[0]
        cell = self.game.item_cell(item)
        self.assertIsNotNone(cell)
        self.assertNotEqual(self.game.cell_to_screen(*cell), self._cell_centre(*cell))

    def test_the_board_follows_the_cursor(self):
        # Grab-and-drag: dragging the cursor right/down carries the board right
        # and down with it (user request: "reverse the direction that the board
        # moves").
        start = self._empty_spot()
        cell = (3, 2)
        was = self.game.cell_to_screen(*cell)

        self._drag(start, (80, 40))

        now = self.game.cell_to_screen(*cell)
        self.assertEqual((now[0] - was[0], now[1] - was[1]), (80, 40))

    def test_the_background_scrolls_with_the_board(self):
        # The trial tessellation behind and around the board moves with it, so
        # dragging the board carries the pattern along instead of sliding the
        # world under a fixed backdrop (user request: "make the background also
        # move, matching the same place the board moves").
        game = self.game
        game.trials_enabled = True
        game.current_trial = main.Trial.SPEEDRUN
        game._reset_board_to_start()      # locked squares wear the pattern too

        def paint():
            game.screen.fill(main.BLACK)
            main.ui.draw_background(game)
            main.ui._draw_locked_backdrop(game, game.board_viewport())

        self.assertEqual(main.ui.background_scroll(game), (0, 0))
        paint()
        reference = game.screen.copy()

        game.pan_board(10, 0)             # the board (and its pattern) moves 10px
        paint()

        self.assertNotEqual(self._pixel_hash(game.screen),
                            self._pixel_hash(reference))
        for point in ((200, 300), (401, 512), (1000, 700)):
            self.assertEqual(
                tuple(game.screen.get_at(point))[:3],
                tuple(reference.get_at((point[0] - 10, point[1])))[:3],
                point)

    def test_a_drag_does_not_move_the_item_in_hand(self):
        # A brand-new game's board is locked down to its start region, which is
        # what gives this test a locked square to drag from.
        self.game._reset_board_to_start()
        item = self.game.owned_items()[0]
        self._click(self._cell_centre(*self.game.item_cell(item)))
        self.assertTrue(self.game.in_hand)
        home = self.game.item_cell(item)

        # A drag that STARTS on a locked square: the press deselects everything
        # (a click on anything that is not an item does, user request) and the
        # drag that follows only scrolls the view — the item stays on its own
        # square.
        locked = (0, 0)
        self.assertTrue(self.game.is_cell_locked(*locked))
        self._drag(self._cell_centre(*locked), (-80, 0))

        self.assertNotEqual(self.game.camera, (0, 0))
        self.assertEqual(self.game.item_cell(item), home)
        self.assertFalse(self.game.in_hand)

    def test_a_click_without_a_drag_still_places_the_item_in_hand(self):
        # The press is a click until it moves: putting an item down still takes
        # one click, and only a DRAG scrolls the view.
        item = self.game.owned_items()[0]
        self._click(self._cell_centre(*self.game.item_cell(item)))
        self._click(self._cell_centre(16, 8))

        self.assertEqual(self.game.camera, (0, 0))
        self.assertIsInstance(self.game.grid.get((16, 8)), main.Block)

    def test_an_item_is_clicked_where_the_camera_draws_it(self):
        item = self.game.owned_items()[0]
        cell = self.game.item_cell(item)
        was = self._cell_centre(*cell)
        # A drag of (100, 50) moves the BOARD right/down by that much (see
        # pan_board), so the item stays well inside the window.
        self.game.pan_board(100, 50)
        now = self._cell_centre(*cell)
        self.assertNotEqual(was, now)

        self._click(now)
        self.assertTrue(self.game.is_item_selected(item))

        self.game._clear_toolbox_selection()
        self._click(was)
        self.assertFalse(self.game.is_item_selected(item))


class InfiniteBoardTests(GameTestCase):
    """The board goes on for ever; the window is only what the player sees."""

    def test_a_square_far_outside_the_window_can_be_unlocked_and_used(self):
        far = (-7, 31)
        self.assertTrue(self.game.is_cell_locked(*far))
        self.assertTrue(self.game._unlock_cell(*far))
        self.assertFalse(self.game.is_cell_locked(*far))
        item = main.Component.shape_component(main.Shape.PIPE)
        self.game.toolbox.add(item)

        self.assertTrue(self.game._move_item_to(item, *far))

        self.assertEqual(self.game.item_cell(item), far)
        self.assertIs(self.game.item_at_cell(far), item)

    def test_an_item_can_lie_on_any_unlocked_square_at_all(self):
        # No range check: the square of a block or an item is any pair of ints.
        block = main.Block(-2, 40, scorer=main.Scorer.CHIPS_ADD)
        self.assertEqual(self.game.item_cell(block), (-2, 40))
        item = main.CardItem(main.Card.GARDEN, 36)
        self.game.set_item_cell(item, (-9, -9))
        self.assertEqual(self.game.item_cell(item), (-9, -9))

    def test_the_walls_are_only_the_locked_frontier(self):
        # An infinite board cannot be walled all at once: the only locked squares
        # a marble can reach are the ones touching the unlocked region.
        walls = self.game._board_wall_blocks()
        self.assertEqual({(w.x, w.y) for w in walls},
                         set(self.game._locked_adjacent_cells()))
        self.assertLess(len(walls), main.GRID_WIDTH * main.GRID_HEIGHT)

    def test_the_marble_is_clamped_to_the_unlocked_region(self):
        self.game.unlocked_cells = {(4, 4)}
        self.game._board_walls_dirty = True
        bounds = self.game.board_pixel_bounds()
        self.assertEqual(bounds[2:], (main.GRID_SIZE, main.GRID_SIZE))
        # The clamp sits outside that: phasing into the wall around it is what
        # the Intangible and Matrix cards pay for.
        padded = self.game.board_pixel_bounds(pad=2)
        self.assertEqual(padded[2:], (5 * main.GRID_SIZE, 5 * main.GRID_SIZE))


class TopBarTests(GameTestCase):
    """The game's furniture lives in a bar along the top; the board has the rest."""

    def _cell_centre(self, gx, gy):
        x, y = self.game.cell_to_screen(gx, gy)
        return (x + main.GRID_SIZE // 2, y + main.GRID_SIZE // 2)

    def test_the_board_fills_everything_under_the_bar(self):
        view = self.game.board_viewport()
        self.assertEqual(view.top, main.TOP_BAR_HEIGHT)
        self.assertEqual(view.left, 0)
        self.assertEqual(view.width, main.SCREEN_WIDTH)
        self.assertEqual(view.bottom, main.SCREEN_HEIGHT)

    def test_the_furniture_is_in_the_bar(self):
        bar = main.pygame.Rect(0, 0, main.SCREEN_WIDTH, main.TOP_BAR_HEIGHT)
        pieces = {
            "trial box": main.TRIAL_BOX_RECT,
            "main menu": main.RETURN_TO_MENU_BUTTON_RECT,
            "score": main.SCORE_PANEL_RECT,
            "action upgrade": main.ACTION_UPGRADE_RECT,
            "deck": main.DECK_BUTTON_RECT,
            "board unit": main.BOARD_UNIT_BUTTON_RECT,
        }
        for name, rect in pieces.items():
            with self.subTest(piece=name):
                self.assertTrue(bar.contains(rect), (name, rect))
        # The cash readouts and the shop's messages share the bar's left corner:
        # the shop BOX is gone, and its offers lie on the board (see
        # ui.draw_bar_readouts).
        readout = main.pygame.Rect(main.BAR_TEXT_X, main.BAR_TEXT_Y,
                                   main.BAR_TEXT_WIDTH,
                                   main.TOP_BAR_HEIGHT - main.BAR_TEXT_Y)
        self.assertTrue(bar.contains(readout), readout)
        # ...and so does the run/round display (RUN_DOT_GRID is the first dot).
        x0, y0 = main.RUN_DOT_GRID
        self.assertLess(y0 + 2 * main.RUN_DOT_DY, main.TOP_BAR_HEIGHT)
        self.assertGreater(x0, readout.right)

    def test_a_locked_square_wears_the_backgrounds_pattern(self):
        g = self.game
        g._reset_board_to_start()
        main.ui.draw_background(g)
        behind = g.screen.get_at(self._cell_centre(0, 0))[:3]
        main.ui.draw_board(g)
        self.assertEqual(g.screen.get_at(self._cell_centre(0, 0))[:3], behind)
