"""The inventory: what its panel shows, discards, and the whole-inventory pop-up.

The inventory holds everything the player owns, without a size limit, but its
panel only ever SHOWS a random selection of it (see main.Toolbox): using an
action re-draws that selection, the F key swaps picked items for others from
the whole inventory (two discards a run), and the 1x1 box on the panel's right
edge opens the whole inventory in a pop-up laid out like an opened pack.
"""

from tests.game_test_case import *  # noqa: F401,F403


class InventoryTests(GameTestCase):

    def _fill(self, count, capacity=False):
        """Own ``count`` distinguishable blocks, leaving the panel as add() left it."""
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        items = [main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.NONE, 0, 5, f"Wall {i}")
                 for i in range(count)]
        for item in items:
            self.game.toolbox.add(item)
        return items


    def test_the_inventory_keeps_everything_past_the_panel(self):
        # The panel shows exactly the inventory's size; the rest is kept (the
        # inventory is unbounded) and can be drawn back out.
        capacity = self.game.toolbox.capacity()
        items = self._fill(capacity + 3)

        self.assertEqual(len(self.game.toolbox.items), capacity)
        self.assertEqual(len(self.game.toolbox.stash), 3)
        self.assertEqual(len(self.game.toolbox.every_item()), capacity + 3)
        self.assertEqual([id(i) for i in self.game.toolbox.every_item()],
                         [id(i) for i in items])


    def test_a_purchase_past_the_panel_is_kept_not_refused(self):
        # Buying when the panel is full still works: the item is owned and waits
        # in the stash, so nothing is ever lost to a full shelf.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity)
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Bought")
        self.game.cash = 1000

        self.game._buy_shop_item(block)

        self.assertTrue(self.game.toolbox.contains(block))
        self.assertEqual(self.game.cash, 1000 - block.price)
        self.assertEqual(len(self.game.toolbox.items), capacity)
        self.assertEqual(len(self.game.toolbox.stash), 1)


    def test_using_an_action_redraws_the_panel(self):
        # Every action used turns the selection over, so an item that was
        # waiting in the stash can come into reach.
        capacity = self.game.toolbox.capacity()
        items = self._fill(capacity + 4)
        before = list(self.game.toolbox.items)
        self.game.actions = [main.ActionItem(main.Action.INACTION,
                                             main.Action.PRICES[main.Action.INACTION])]
        action = self.game.actions[0]
        self.game._select_action(action)
        # A reverse "shuffle" makes the draw deterministic: the panel takes the
        # LAST items of the pool, which are the stashed ones.
        with mock.patch.object(main.random, "sample", lambda pool, k: list(reversed(pool))):
            self.assertTrue(self.game._apply_action())

        after = self.game.toolbox.items
        self.assertEqual(len(after), capacity)
        self.assertNotEqual([id(i) for i in after], [id(i) for i in before])
        stashed_before = set(id(i) for i in items[capacity:])
        self.assertTrue(any(id(item) in stashed_before for item in after))


    def test_a_reshuffle_drops_a_pick_that_left_the_panel(self):
        # The selection cannot outlive its cell: a block that is no longer shown
        # stops being selected (and stops being armed for placement).
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 2)
        self.game._equip_block(self.game.toolbox.items[0], 0)
        self.assertTrue(self.game.has_selected)

        with mock.patch.object(main.random, "sample", lambda pool, k: list(reversed(pool))):
            self.game._reshuffle_inventory()

        self.assertFalse(self.game.has_selected)
        self.assertIsNone(self.game.selected_toolbox_item)


    def test_a_click_toggles_an_item(self):
        # The user's rule: one click selects an item, a second click on the same
        # (selected) item unselects it — for a block, a component, or anything
        # else in the panel.
        self._fill(3)
        rect = self.game.toolbox.cell_rect(0)
        block = self.game.toolbox.items[0]

        self._click(rect.center)
        self.assertTrue(self.game.is_toolbox_selected(block))
        self.assertTrue(self.game.has_selected)          # armed for placement
        self.assertIs(self.game.selected_toolbox_item, block)

        self._click(rect.center)
        self.assertFalse(self.game.is_toolbox_selected(block))
        self.assertFalse(self.game.has_selected)         # no longer in hand
        self.assertIsNone(self.game.selected_toolbox_item)

        self._click(rect.center)                         # and back on again
        self.assertTrue(self.game.is_toolbox_selected(block))


    def test_clicking_several_items_toggles_each_one(self):
        # Plain clicks build the multi-item selection a discard acts on: the
        # last one clicked is the one in hand.
        self._fill(4)
        first, second = self.game.toolbox.items[0], self.game.toolbox.items[2]

        self._click(self.game.toolbox.cell_rect(0).center)
        self._click(self.game.toolbox.cell_rect(2).center)

        self.assertEqual([id(i) for i in self.game.selection],
                         [id(first), id(second)])
        self.assertIs(self.game.selected_toolbox_item, second)
        # Clicking the first one again takes it out of the selection and leaves
        # the second in hand.
        self._click(self.game.toolbox.cell_rect(0).center)
        self.assertEqual([id(i) for i in self.game.selection], [id(second)])
        self.assertIs(self.game.selected_toolbox_item, second)


    def test_f_discards_the_selected_items_for_others(self):
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 4)
        picks = [self.game.toolbox.items[0], self.game.toolbox.items[2]]
        for item in picks:
            self.game._toggle_toolbox_selection(item)
        before_items = list(self.game.toolbox.items)
        before_stash = list(self.game.toolbox.stash)

        with mock.patch.object(main.random, "choice", lambda pool: pool[0]):
            self.assertTrue(self.game._discard_items())

        after = self.game.toolbox.items
        self.assertEqual(len(after), capacity)            # the panel stays full
        for item in picks:
            self.assertFalse(any(item is shown for shown in after))
            self.assertTrue(any(item is held for held in self.game.toolbox.stash))
        # The replacements are the items that were waiting.
        for index in (0, 2):
            self.assertTrue(any(after[index] is held for held in before_stash))
        self.assertEqual(len(self.game.toolbox.items), len(before_items))
        self.assertEqual(self.game.discards_left, main.DISCARDS_PER_RUN - 1)
        self.assertEqual(self.game.selection, [])
        self.assertIn("Discarded 2 items", self.game.shop_message)


    def test_a_discarded_item_cannot_be_swapped_back_in_by_the_same_discard(self):
        # Two items are discarded together: the first one goes back to the
        # waiting pool, but the SAME discard never draws it again (that would
        # just put it straight back on the panel).
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 3)
        picks = [self.game.toolbox.items[0], self.game.toolbox.items[1]]
        self.game.selection = list(picks)

        # Take the LAST waiting item each time, which is the one the previous
        # swap just parked at the back of the stash.
        with mock.patch.object(main.random, "choice", lambda pool: pool[-1]):
            self.assertTrue(self.game._discard_items())

        for item in picks:
            self.assertFalse(any(item is shown for shown in self.game.toolbox.items))


    def test_clicking_outside_the_panel_deselects_everything(self):
        # The selection belongs to the panel: a left-click anywhere else drops
        # it (every toggled item and the one in hand).
        self._fill(4)
        for item in self.game.toolbox.items[:2]:
            self.game._toggle_toolbox_selection(item)
        self.assertEqual(len(self.game.selection), 2)
        self.assertIsNotNone(self.game.selected_toolbox_item)

        # Clicking empty space clears it (a click on the BOARD would place the
        # armed block instead — see the next test)...
        self._click((5, 5))

        self.assertEqual(self.game.selection, [])
        self.assertFalse(self.game.has_selected)
        # ...and they really are gone from the panel's own view too.
        self.game.draw()
        panel = pygame.Rect(self.game.toolbox.rect.x,
                            self.game.toolbox.rect.y, self.game.toolbox.rect.width,
                            main.GRID_SIZE)
        self.assertNotIn(main.GREEN, self._colours_in(panel))


    def test_clicking_inside_the_panel_keeps_the_selection(self):
        # A click on the panel itself — an empty cell or its own view button —
        # never drops the selection.
        self._fill(3)
        picked = self.game.toolbox.items[0]
        self.game._toggle_toolbox_selection(picked)

        self._click(self.game.toolbox.cell_rect(3).center)     # empty cell
        self.assertEqual(self.game.selection, [picked])

        self._click(self.game.inventory_view_button_rect().center)  # the view button
        self.assertTrue(self.game.inventory_open)
        self._click(main.ui.inventory_close_rect(self.game).center)
        self.assertEqual(self.game.selection, [picked])


    def test_clicking_the_board_places_the_block_in_hand(self):
        # The armed block is still what a board click places (and the selection
        # is spent with the item) — the toggle did not take that away.
        self._fill(3)
        block = self.game.toolbox.items[0]
        self.game._toggle_toolbox_selection(block, 0)

        self._click(self._grid_pos(3, 3))

        placed = self.game.grid.get((3, 3))
        self.assertIsNotNone(placed)
        self.assertFalse(any(block is shown for shown in self.game.toolbox.items))
        self.assertFalse(self.game.has_selected)


    def test_f_discards_the_item_in_hand_when_nothing_is_toggled(self):
        # A block armed directly (the code path a click on the board uses for a
        # placed block) is still discardable, so F never needs a click first.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 2)
        block = self.game.toolbox.items[1]
        self.game._equip_block(block, 1)

        self.assertTrue(self.game._discard_items())

        self.assertFalse(any(block is shown for shown in self.game.toolbox.items))
        self.assertFalse(self.game.has_selected)
        self.assertEqual(self.game.discards_left, main.DISCARDS_PER_RUN - 1)


    def test_at_most_four_items_in_one_discard(self):
        # The rule is about the SELECTION, not the panel: a wide panel can show
        # more than four items, and picking five is refused.
        self.game.toolbox.base_slots = 6
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 8)
        for item in self.game.toolbox.items[:5]:
            self.game._toggle_toolbox_selection(item)
        before = list(self.game.toolbox.items)

        self.assertFalse(self.game._discard_items())

        self.assertEqual([id(i) for i in self.game.toolbox.items],
                         [id(i) for i in before])
        self.assertEqual(self.game.discards_left, main.DISCARDS_PER_RUN)
        self.assertIn(f"at most {main.DISCARD_COUNT_MAX}", self.game.shop_message)


    def test_a_run_hands_out_two_discards_and_continue_gives_them_back(self):
        # Two discards a run (DISCARDS_PER_RUN): the third is refused, and
        # continuing the run hands the full set back.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 8)
        for _ in range(main.DISCARDS_PER_RUN):
            self.game.selection = [self.game.toolbox.items[0]]
            self.assertTrue(self.game._discard_items())
        self.assertEqual(self.game.discards_left, 0)
        self.game.selection = [self.game.toolbox.items[0]]
        self.assertFalse(self.game._discard_items())
        self.assertIn("No discards left", self.game.shop_message)

        self._complete_run(10 ** 6, required=1)
        self.game._continue_run()
        self.assertEqual(self.game.discards_left, main.DISCARDS_PER_RUN)


    def test_continue_leaves_the_panel_and_hands_the_discards_back(self):
        # Continuing a run is not a reshuffle: the panel keeps the selection the
        # player was building with, and only the discards come back.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 5)
        self.game.discards_left = 0
        before = [id(i) for i in self.game.toolbox.items]
        self._complete_run(10 ** 6, required=1)

        self.game._continue_run()

        self.assertEqual([id(i) for i in self.game.toolbox.items], before)
        self.assertEqual(self.game.discards_left, main.DISCARDS_PER_RUN)


    def test_nothing_to_swap_costs_no_discard(self):
        # Exactly as many items as the panel shows: a discard has no other item
        # to bring in, so it does nothing and the discard is not spent.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity)
        self.game.selection = [self.game.toolbox.items[0]]

        self.assertFalse(self.game._discard_items())

        self.assertEqual(self.game.discards_left, main.DISCARDS_PER_RUN)
        self.assertIn("Nothing else in the inventory", self.game.shop_message)


    def test_the_view_button_opens_the_whole_inventory(self):
        capacity = self.game.toolbox.capacity()
        items = self._fill(capacity + 6)
        self.assertFalse(self.game.inventory_open)

        self._click(self.game.inventory_view_button_rect().center)

        self.assertTrue(self.game.inventory_open)
        listed = [item for page in range(self.game._inventory_view_pages())
                  for item in self._page_items(page)]
        self.assertEqual(len(listed), len(items))
        for item in items:
            self.assertTrue(any(item is shown for shown in listed))

        # CLOSE shuts it again; so does a click off the panel.
        self._click(main.ui.inventory_close_rect(self.game).center)
        self.assertFalse(self.game.inventory_open)
        self._click(self.game.inventory_view_button_rect().center)
        self.assertTrue(self.game.inventory_open)
        self._click((5, 5))
        self.assertFalse(self.game.inventory_open)


    def _page_items(self, page):
        """The whole inventory's items on ``page`` of the pop-up (see ui)."""
        saved = self.game.inventory_page
        self.game.inventory_page = page
        try:
            return main.ui.inventory_view_items(self.game)
        finally:
            self.game.inventory_page = saved


    def test_the_popup_pages_through_the_whole_inventory(self):
        per_page = main.ui.INVENTORY_VIEW_COLS * main.ui.INVENTORY_VIEW_ROWS
        self._fill(per_page + 5)
        self.game.inventory_open = True
        self.assertEqual(self.game._inventory_view_pages(), 2)

        self.game._page_inventory_view(1)

        self.assertEqual(self.game.inventory_page, 1)
        self.assertEqual(len(main.ui.inventory_view_items(self.game)), 5)
        self.game._page_inventory_view(1)          # wraps round
        self.assertEqual(self.game.inventory_page, 0)
        self.assertEqual(len(main.ui.inventory_view_items(self.game)), per_page)


    def test_the_view_button_draws_a_box_on_the_panels_right_edge(self):
        # The whole-inventory box is the BOTTOM cell of the panel's right edge,
        # and the page arrow is the cell directly ABOVE it (user request: "put
        # the box that shows to full inventory directly below this arrow box").
        box = self.game.toolbox.rect
        button = self.game.inventory_view_button_rect()
        self.assertEqual(button.left, box.right)
        self.assertEqual(button.bottom, box.bottom)
        self.assertEqual(button.width, main.GRID_SIZE)
        self.assertEqual(button.height, main.GRID_SIZE)
        arrow = self.game.inventory_page_button_rect()
        self.assertEqual(arrow.left, button.left)
        self.assertEqual(arrow.bottom, button.top)
        # The arrow is only shown (and clickable) once there is a second page.
        self.assertEqual(self.game.toolbox.page_count(), 1)


    def test_the_selection_and_discards_read_out_on_the_title_strip(self):
        # The panel's title strip carries the counts: the green "n selected" line
        # appears only while something is selected, so the player can see what F
        # will act on without hovering anything.
        self._fill(3)
        self.game.discards_left = main.DISCARDS_PER_RUN
        strip = pygame.Rect(self.game.toolbox.rect.x, self.game.toolbox.rect.y - 16,
                            self.game.toolbox.rect.width, 16)
        self.game.draw()
        self.assertNotIn(main.GREEN, self._colours_in(strip))

        self.game._toggle_toolbox_selection(self.game.toolbox.items[0])
        self.game.draw()

        self.assertIn(main.GREEN, self._colours_in(strip))


    def _colours_in(self, rect):
        """Every colour drawn inside ``rect``."""
        return {tuple(self.game.screen.get_at((x, y)))[:3]
                for x in range(rect.left, rect.right)
                for y in range(rect.top, rect.bottom)}


    def test_the_popup_draws_a_panel_with_its_items(self):
        self._fill(4)
        self.game.inventory_open = True
        self.game.draw()
        panel = main.ui.inventory_panel_rect(self.game)
        # The panel's frame is drawn, and every listed item's cell has content
        # (its art and name) rather than the panel's flat fill.
        self.assertEqual(tuple(self.game.screen.get_at(
            (panel.centerx, panel.top)))[:3], main.WHITE)
        for rect in main.ui.inventory_item_rects(self.game):
            colours = self._colours_in(rect)
            self.assertGreater(len(colours), 2, rect)
        self.assertGreater(len(main.ui.inventory_item_rects(self.game)), 0)


    def test_the_sidebar_reads_out_an_item_in_the_popup(self):
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 1)
        self.game.inventory_open = True
        stashed = self.game.toolbox.stash[0]
        index = [i for i, item in enumerate(self.game.toolbox.every_item())
                 if item is stashed][0]
        rect = main.ui.inventory_item_rects(self.game)[index]

        item, source = self.game._info_target_at(rect.center)

        self.assertIs(item, stashed)
        self.assertEqual(source, "inventory")
        self.assertIn("Waiting off the panel",
                      self.game._action_hint(item, source))


    def test_the_popup_footer_never_stacks_its_buttons(self):
        # A small inventory is ONE page: there is nothing to page to, so the
        # arrows are not drawn at all — and CLOSE is never covered by them
        # (user request: they used to overlap and block each other).
        self._fill(2)
        self.game.inventory_open = True
        self.assertEqual(self.game._inventory_view_pages(), 1)
        close = main.ui.inventory_close_rect(self.game)
        for direction in (-1, 1):
            self.assertFalse(main.ui.inventory_pager_rect(self.game,
                                                          direction).colliderect(close))

        # With several pages the arrows sit at the footer's two ends, either
        # side of CLOSE: clear of it and of each other.
        per_page = main.ui.INVENTORY_VIEW_COLS * main.ui.INVENTORY_VIEW_ROWS
        self._fill(per_page * 2 + 3)
        self.assertEqual(self.game._inventory_view_pages(), 3)
        close = main.ui.inventory_close_rect(self.game)
        back = main.ui.inventory_pager_rect(self.game, -1)
        forward = main.ui.inventory_pager_rect(self.game, 1)
        self.assertFalse(back.colliderect(close))
        self.assertFalse(forward.colliderect(close))
        self.assertFalse(back.colliderect(forward))
        panel = main.ui.inventory_panel_rect(self.game)
        for rect in (back, forward, close):
            self.assertTrue(panel.contains(rect))

    def test_the_popup_draws_no_arrows_for_a_single_page(self):
        self._fill(1)
        self.game.inventory_open = True
        self.game.screen.fill(main.BLACK)
        main.ui.draw_inventory_overlay(self.game)
        # The pager positions are inside the bare panel (its own dark fill), not
        # the grey of a button.
        for direction in (-1, 1):
            pager = main.ui.inventory_pager_rect(self.game, direction)
            self.assertNotEqual(tuple(self.game.screen.get_at(pager.center))[:3],
                                (70, 70, 80))
        # ...and a click there neither pages nor closes the pop-up.
        self._click(main.ui.inventory_pager_rect(self.game, 1).center)
        self.assertTrue(self.game.inventory_open)
        self.assertEqual(self.game.inventory_page, 0)


    def test_the_inventory_side_boxes_border_only_their_own_edges(self):
        # The page arrow sits directly on the whole-inventory box, and both hang
        # off the panel's right edge. Their LEFT edges (the panel's own border)
        # and the line they share are not drawn as extra walls, so they read as
        # tabs on the panel instead of blocking each other.
        self.game.cash = 1000
        for _ in range(8):
            self.game._buy_inventory_slot()
        self._fill(self.game.toolbox.capacity())
        box = self.game.toolbox
        self.assertGreater(box.page_count(), 1)
        arrow = self.game.inventory_page_button_rect()
        view = self.game.inventory_view_button_rect()
        self.assertEqual(arrow.bottom, view.top)       # they touch, never overlap
        self.assertEqual(arrow.left, box.rect.right)
        self.assertEqual(view.left, box.rect.right)

        self.game.screen.fill(main.BLACK)
        main.ui.draw_toolbox(self.game)

        fill = tuple(main.ui.panel_fill(self.game))[:3]
        for rect in (arrow, view):
            # No left border: the first column of the box is its own fill, so
            # the panel's right edge is the shared line.
            self.assertEqual(
                tuple(self.game.screen.get_at((rect.left + 2, rect.centery)))[:3],
                fill)
            # Its own right edge IS bordered.
            self.assertEqual(
                tuple(self.game.screen.get_at(
                    (rect.right + main.BORD_WIDTH // 2, rect.centery)))[:3],
                (30, 30, 30))


    def test_placing_a_block_leaves_its_slot_empty(self):
        # User request: placing a block must NOT slide another item into the slot
        # it came from — the panel keeps the hole until a reshuffle or discard
        # fills it from the stash.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 2)
        stashed = list(self.game.toolbox.stash)
        block = self.game.toolbox.items[1]
        self.game._toggle_toolbox_selection(block, 1)

        self.assertTrue(self.game._place_block_at(3, 3))

        self.assertEqual(len(self.game.toolbox.items), capacity - 1)
        self.assertEqual([id(i) for i in self.game.toolbox.stash],
                         [id(i) for i in stashed])      # nothing pulled out
        self.assertFalse(any(block is shown for shown in self.game.toolbox.items))
        self.assertIsNotNone(self.game.grid.get((3, 3)))


    def test_other_removals_still_refill_the_slot(self):
        # Selling (or any other removal) does bring the next item out, so the
        # panel keeps showing as much of the inventory as it has room for.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 2)
        self.game.cash = 0
        item = self.game.toolbox.items[0]
        self.game._toggle_toolbox_selection(item, 0)

        self.game._sell_selected_item()

        self.assertEqual(len(self.game.toolbox.items), capacity)
        self.assertEqual(len(self.game.toolbox.stash), 1)


    def test_a_new_save_starts_with_four_inventory_slots(self):
        self.assertEqual(main.INVENTORY_START_SLOTS, 4)
        self.assertEqual(self.game.inventory_slots_bought, 0)
        self.assertEqual(self.game.toolbox.capacity(), 4)
        # The panel's grid is only as big as the inventory it shows (up to
        # main.INVENTORY_MAX_COLS x main.INVENTORY_MAX_ROWS), so a four-slot
        # inventory is a four-cell panel: no unsold cells to waste room on.
        self.assertEqual(self.game.toolbox.cols, 4)
        self.assertEqual(self.game.toolbox.rows, 1)
        # A brand-new game (a new save) is back to four.
        self.game.inventory_slots_bought = 3
        self.game.toolbox.base_slots = main.INVENTORY_START_SLOTS + 3
        self.game._reset_board_to_start()
        self.game.reset_game()
        self.assertEqual(self.game.inventory_slots_bought, 0)
        self.assertEqual(self.game.toolbox.capacity(), main.INVENTORY_START_SLOTS)
        self.assertEqual(self.game.toolbox.cols, 4)


    def test_the_panel_grows_with_the_slots_it_sells(self):
        # The panel's grid is sized from the inventory: one cell per slot, five
        # to a row, and a second row when one will not do — 5x2 at most.
        sizes = []
        self.game.cash = 1000
        for _ in range(8):
            sizes.append((self.game.toolbox.cols, self.game.toolbox.rows))
            self.game._buy_inventory_slot()
        self.assertEqual(sizes[:3], [(4, 1), (5, 1), (5, 2)])
        self.assertEqual(sizes[-1], (5, 2))
        self.assertEqual(self.game.toolbox.capacity(), 12)
        self.assertEqual(self.game.toolbox.rect.size,
                         (5 * main.GRID_SIZE, 2 * main.GRID_SIZE))
        # The panel grows UP: its bottom edge never moves, so the buttons under
        # it keep their place.
        self.assertEqual(self.game.toolbox.rect.bottom,
                         main.TOOLBOX_COORDS[1] + main.TOOLBOX_COORDS[3])

    def test_the_panel_turns_pages_past_its_largest_size(self):
        # More items than the 5x2 grid can show: the panel keeps its largest
        # size and the arrow box on its right edge swaps the page.
        self.game.cash = 1000
        for _ in range(8):
            self.game._buy_inventory_slot()
        items = self._fill(self.game.toolbox.capacity())
        box = self.game.toolbox
        self.assertEqual(box.page_count(), 2)
        self.assertEqual(len(box.shown_items()), box.per_page)
        first_page = list(box.shown_items())

        self.game._turn_inventory_page()

        self.assertEqual(box.page, 1)
        self.assertEqual(len(box.shown_items()), box.capacity() - box.per_page)
        self.assertFalse(any(item is shown for item in first_page
                             for shown in box.shown_items()))
        # The item on the second page is the one a click on its cell selects.
        second = box.shown_items()[0]
        self.assertIs(box.item_at(box.cell_rect(0).center), second)
        self.assertGreater(box.items.index(second), box.per_page - 1)
        # The arrow box is where it must be: the TOP HALF of the right edge,
        # with the whole-inventory box directly below it.
        arrow = self.game.inventory_page_button_rect()
        view = self.game.inventory_view_button_rect()
        self.assertEqual(arrow.top, box.rect.top)
        self.assertEqual(arrow.bottom, box.rect.centery)
        self.assertEqual(view.top, arrow.bottom)
        # ...and clicking it turns the page (wrapping back to the first).
        self._click(arrow.center)
        self.assertEqual(box.page, 0)
        self.assertEqual(box.shown_items(), items[:box.per_page])

    def test_a_single_page_hides_the_arrow(self):
        # Nothing to swap to, nothing to show: the arrow only appears while the
        # inventory holds more than the panel can display.
        self._fill(self.game.toolbox.capacity())
        box = self.game.toolbox
        self.assertEqual(box.page_count(), 1)
        self.game.screen.fill(main.BLACK)
        main.ui.draw_toolbox(self.game)

        # The view box is drawn on the panel's right edge; the arrow's cell
        # (directly above it) is left untouched.
        self.assertNotEqual(
            tuple(self.game.screen.get_at(
                self.game.inventory_view_button_rect().center))[:3], main.BLACK)
        self.assertEqual(
            tuple(self.game.screen.get_at(
                self.game.inventory_page_button_rect().center))[:3], main.BLACK)

    def test_the_shop_sells_one_inventory_slot_for_thirty(self):
        tile = self.game._inventory_slot_tile()
        shop = self.game.shop.rect
        self.assertTrue(shop.contains(tile))
        self.assertFalse(tile.colliderect(self.game._board_unit_tile()))
        self.assertEqual(main.INVENTORY_SLOT_PRICE, 30)
        before = self.game.toolbox.capacity()

        self.game.cash = 100
        self._click(tile.center)

        self.assertEqual(self.game.cash, 100 - main.INVENTORY_SLOT_PRICE)
        self.assertEqual(self.game.inventory_slots_bought, 1)
        self.assertEqual(self.game.toolbox.capacity(), before + 1)
        self.assertIn("5 slots", self.game.shop_message)
        # Buying it with no cash is refused, and nothing is charged.
        self.game.cash = main.INVENTORY_SLOT_PRICE - 1
        self.assertFalse(self.game._buy_inventory_slot())
        self.assertEqual(self.game.inventory_slots_bought, 1)
        self.assertEqual(self.game.cash, main.INVENTORY_SLOT_PRICE - 1)


    def test_a_bought_slot_brings_a_stashed_item_out(self):
        self._fill(6)                       # 4 shown, 2 waiting
        self.assertEqual(len(self.game.toolbox.items), 4)
        self.game.cash = 100

        self.assertTrue(self.game._buy_inventory_slot())

        self.assertEqual(len(self.game.toolbox.items), 5)
        self.assertEqual(len(self.game.toolbox.stash), 1)


    def test_bought_slots_ride_through_a_save(self):
        self.game.save_slot = 1
        self.game.cash = 100
        self.game._buy_inventory_slot()
        self.game._buy_inventory_slot()

        save_system.save_game(self.game)
        fresh = main.Game()
        save_system.load_slot(fresh, 1)

        self.assertEqual(fresh.inventory_slots_bought, 2)
        self.assertEqual(fresh.toolbox.capacity(),
                         main.INVENTORY_START_SLOTS + 2)


    def test_a_removed_item_is_replaced_from_the_stash(self):
        # Using an item up (placing it, selling it) leaves a hole in the panel,
        # and the panel is a selection of the inventory: the hole is filled from
        # the stash, so the panel keeps showing as much as it has room for.
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 3)
        spent = self.game.toolbox.items[2]
        stashed = list(self.game.toolbox.stash)

        self.assertTrue(self.game.toolbox.remove(spent))

        self.assertEqual(len(self.game.toolbox.items), capacity)
        self.assertFalse(any(spent is shown for shown in self.game.toolbox.items))
        self.assertTrue(any(self.game.toolbox.items[2] is held for held in stashed))


    def test_the_stash_rides_through_a_save(self):
        self.game.save_slot = 1
        capacity = self.game.toolbox.capacity()
        self._fill(capacity + 3)

        save_system.save_game(self.game)
        fresh = main.Game()
        save_system.load_slot(fresh, 1)

        self.assertEqual(len(fresh.toolbox.items), capacity)
        self.assertEqual(len(fresh.toolbox.stash), 3)
        self.assertEqual(len(fresh.toolbox.every_item()), capacity + 3)
        self.assertEqual(fresh.discards_left, self.game.discards_left)


    def test_a_save_wider_than_its_bought_slots_stashes_the_overflow(self):
        # A save written before the shop sold slots can show more items than a
        # fresh panel owns cells for. Loading it moves the overflow to the
        # stash: nothing is lost, and no item sits in an unsold cell.
        self.game.save_slot = 1
        save_system.save_game(self.game)
        data = save_system._read_slot(1)
        width = self.game.toolbox.cols
        data.pop("inventory_slots_bought", None)
        data["toolbox"] = [data["toolbox"][0] for _ in range(width)]

        fresh = main.Game()
        save_system._load_save_data(fresh, data, 1)

        self.assertEqual(fresh.toolbox.capacity(), main.INVENTORY_START_SLOTS)
        self.assertEqual(len(fresh.toolbox.items), main.INVENTORY_START_SLOTS)
        self.assertEqual(len(fresh.toolbox.every_item()), width)
