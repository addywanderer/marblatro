"""The inventory: selection, assignment and clicks on the board.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class ToolboxTests(GameTestCase):
    """The inventory: selection, assignment and clicks on the board."""


    def test_click_without_selection_does_not_place_block(self):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1

        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertNotIn((1, 1), self.game.grid)


    def test_a_bought_role_block_lands_in_the_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        offer = self.game.shop._scorer_offer(main.Scorer.FINISH, 2, 1)

        self.game._buy_shop_item(offer)

        # The bought item is a copy of the offer (see items.owned_copy): the
        # shelf keeps the offer, the player keeps their own block.
        self.assertEqual(len(self.game.toolbox.items), 1)
        bought = self.game.toolbox.items[0]
        self.assertIsNot(bought, offer)
        self.assertEqual(bought.shape, main.Shape.RECT)
        self.assertEqual(bought.effects, [])
        self.assertEqual(offer.shape, main.Shape.RECT)
        self.assertLess(self.game.cash, 1000)


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


    def test_clicking_a_second_placed_block_selects_it_too(self):
        # Every click on an item is its own switch (see _toggle_item_selection),
        # so clicking a second block with one already selected switches the
        # second one on as a TARGET of the first instead of overwriting it.
        self.game.toolbox.items.clear()
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(5, 5)] = main.Block(5, 5, shape=main.Shape.RECT,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self._click(self._grid_pos(2, 3))  # select the SLOPE block

        self._click(self._grid_pos(5, 5))  # switch the RECT block on as well

        self.assertEqual(self.game.grid[(2, 3)].shape, main.Shape.SLOPE)  # still there
        self.assertEqual(self.game.grid[(5, 5)].shape, main.Shape.RECT)
        self.assertEqual(len(self.game.selection), 2)
        self.assertIs(self.game.actor(), self.game.grid[(2, 3)])
        self.assertIs(self.game.selected_toolbox_item, self.game.grid[(2, 3)])
        self.assertEqual(self.game.toolbox.items, [])  # nothing refunded


    def test_a_block_in_hand_does_not_replace_a_block_clicked_on(self):
        # A click on an item is a switch, not a placement: the fresh block stays
        # in hand and the block that was clicked joins the selection behind it.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        placed = main.Block(2, 3, shape=main.Shape.SLOPE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 3)] = placed

        self._click(self._grid_pos(2, 3))

        self.assertEqual(self.game.grid[(2, 3)].shape, main.Shape.SLOPE)
        self.assertIs(self.game.selected_toolbox_item, block)  # still in hand
        self.assertIs(self.game.selected_targets()[0], placed)


    def test_clicking_a_block_item_arms_it(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)

        self._click(self._item_pos(block))

        self.assertIs(self.game.selected_toolbox_item, block)
        self.assertTrue(self.game.has_selected)  # the block is equipped


    def test_left_clicking_placed_block_selects_it_for_move(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 3)] = block

        self._click(self._grid_pos(2, 3))

        self.assertIs(self.game.selected_toolbox_item, block)  # it equips the placed block
        self.assertTrue(self.game.has_selected)


    def test_a_key_rotates_next_placement_when_nothing_selected(self):
        self.assertEqual(self.game.current_block_angle, 0)
        self.game.selected_toolbox_item = None

        self._press(main.pygame.K_a)

        self.assertEqual(self.game.current_block_angle, 90)


    def test_right_click_does_not_erase_a_block(self):
        # Right-click is the shop's alone now (user request: "remove whatever
        # right-clicking does"): the board is left untouched.
        block = main.Block(2, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(2, 3)] = block
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 3

        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(2, 3)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((2, 3), self.game.grid)  # right-click leaves it alone


    def test_erasing_the_selected_block_deselects_it(self):
        # Picking a placed block up arms it for placement (a MOVE, see
        # _select_placed_block). Erasing that block must drop the selection with
        # it: _refund_block puts the block back in the toolbox, so leaving it
        # armed would let the player place it again while the refunded copy
        # still sits in the inventory — the same block twice.
        block = main.Block(2, 3, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 3)] = block
        self.game.toolbox.items.clear()
        self.game._select_placed_block(block)
        self.assertTrue(self.game.has_selected)
        self.assertIs(self.game.selected_toolbox_item, block)

        self.game._erase_block_at(2, 3)

        self.assertNotIn((2, 3), self.game.grid)
        self.assertFalse(self.game.has_selected)
        self.assertIsNone(self.game.selected_toolbox_item)
        # It came back as exactly one inventory item, and with nothing armed it
        # cannot be fielded a second time.
        self.assertEqual(len(self.game.toolbox.items), 1)
        self.assertFalse(self.game._place_block_at(4, 4))
        self.assertNotIn((4, 4), self.game.grid)
        self.assertEqual(len(self.game.toolbox.items), 1)




    def test_use_component_stays_in_toolbox(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)

        self.game._use_component(comp)

        self.assertIn(comp, self.game.assigned_effects())
        self.assertIn(comp, self.game.toolbox.items)  # kept where it is


    def test_effect_component_toggles_off_when_clicked_again(self):
        # A click is a switch (see _toggle_item_selection): the second one turns
        # the piece off again, and it is no longer part of the next assembly.
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._toggle_item_selection(comp)
        self.assertIn(comp, self.game.assigned_effects())

        self.game._toggle_item_selection(comp)

        self.assertNotIn(comp, self.game.assigned_effects())


    def test_switching_assigned_shape_swaps_assignment(self):
        self.game.toolbox.items.clear()
        first = main.Component.shape_component(main.Shape.SLOPE, 0, "Slope")
        second = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        self.game.toolbox.add(first)
        self.game.toolbox.add(second)

        self.game._use_component(first)
        self.game._use_component(second)

        self.assertIs(self.game.assigned_part(main.Component.SHAPE), second)
        self.assertNotIn(first, self.game.assigned_toolbox_indexes)
        self.assertIn(first, self.game.toolbox.items)  # both kept in the toolbox
        self.assertIn(second, self.game.toolbox.items)


    def test_is_assigned_marks_assigned_components(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game._clear_assigned_parts()
        self.assertFalse(self.game._is_assigned(comp))
        self.game._use_component(comp)
        self.assertTrue(self.game._is_assigned(comp))
        shape = main.Component.shape_component(main.Shape.SLOPE)
        self.game._use_component(shape)
        self.assertTrue(self.game._is_assigned(shape))
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        self.game._use_component(scorer)
        self.assertTrue(self.game._is_assigned(scorer))




    def test_a_selected_block_item_is_framed_on_its_square(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        cell = self._item_cell(block)
        self._click(self._grid_pos(*cell))
        self.assertTrue(self.game.has_selected)

        self.game.screen.fill((0, 0, 0))
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.draw()
        rect = self.game._board_item_rect(*cell)
        self.assertEqual(self.game.screen.get_at((rect.x + 1, rect.y + 1))[:3],
                         main.GREEN)


    def test_an_assigned_component_is_framed_on_its_square(self):
        # Selecting a component draws the same green frame the panel used to,
        # on the square the piece lies on (see Game._toggle_item_selection).
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        cell = self._item_cell(comp)
        self._click(self._grid_pos(*cell))
        self.assertIs(self.game.selected_toolbox_item, comp)

        self.game.screen.fill((0, 0, 0))
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.draw()
        rect = self.game._board_item_rect(*cell)
        self.assertEqual(self.game.screen.get_at((rect.x + 1, rect.y + 1))[:3],
                         main.GREEN)


    def test_every_assigned_component_keeps_its_frame(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.SLOPE)
        eff_c = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(shape_c)
        self.game.toolbox.add(eff_c)
        shape_cell = self._item_cell(shape_c)
        eff_cell = self._item_cell(eff_c)
        self._click(self._grid_pos(*shape_cell))
        self._click(self._grid_pos(*eff_cell))  # selecting a new one keeps the old green

        self.game.screen.fill((0, 0, 0))
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.draw()
        for cell in (shape_cell, eff_cell):
            rect = self.game._board_item_rect(*cell)
            self.assertEqual(self.game.screen.get_at((rect.x + 1, rect.y + 1))[:3],
                             main.GREEN)


    def test_selected_toolbox_index_cleared_on_deselect(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp, 0)
        self.assertEqual(self.game.selected_toolbox_index, 0)

        self._click((20, 20))  # empty space

        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertIsNone(self.game.selected_toolbox_index)


    def test_s_key_applies_selected_action(self):
        # Select an action, pick a block subject, then press S. Both of them lie
        # on the board (see Game.ensure_board_cells).
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game._on_item_gained(action)
        self.game.cash = 100
        # Click the action on its square to select it.
        self._click(self._item_pos(action))
        self.assertIs(self.game.selected_action, action)
        # Click the block to make it the subject.
        self._click(self._item_pos(block))
        self.assertIs(self.game.selected_action_subject, block)
        # Press S to apply (Death sells it for 1.5x).
        self._press(main.pygame.K_s)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 100 + int(40 * 1.5))
        self.assertIsNone(self.game.selected_action)


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


    def test_toolbox_starts_with_start_and_finish(self):
        items = list(self.game.toolbox.items)
        scorers = [item.scorer for item in items]

        self.assertEqual(len(items), 2)
        self.assertTrue(all(item.kind == "block" for item in items))
        self.assertIn(main.Scorer.START, scorers)
        self.assertIn(main.Scorer.FINISH, scorers)


    def test_item_at_cell_finds_an_owned_item(self):
        self.game.toolbox.items.clear()
        item = self.game.shop.items[0]
        self.game.toolbox.add(item)
        cell = self._item_cell(item)

        self.assertIs(self.game.item_at_cell(cell), item)
        self.assertIsNone(self.game.item_at_cell((main.GRID_WIDTH - 1,
                                                  main.GRID_HEIGHT - 1))
                          if self._item_cell(item) != (main.GRID_WIDTH - 1,
                                                       main.GRID_HEIGHT - 1)
                          else None)


    def test_the_board_holds_one_item_per_square_and_stashes_the_rest(self):
        # The board is the inventory now (user request), so its size is the
        # number of squares: an item past the last free square waits in the
        # stash instead of being refused (see Toolbox.add / _sync_stash).
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        self.assertEqual(self.game.toolbox.capacity(),
                         main.GRID_WIDTH * main.GRID_HEIGHT)
        for x in range(main.GRID_WIDTH):
            for y in range(main.GRID_HEIGHT):
                self.game.grid[(x, y)] = main.Block(x, y, scorer=main.Scorer.NONE)
        item = main.Component.shape_component(main.Shape.PIPE)

        self.assertTrue(self.game.toolbox.add(item))     # never refused...
        self.assertEqual(len(self.game.toolbox.stash), 1)  # ...but it has to wait
        self.assertTrue(self.game.toolbox.contains(item))


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


    def test_place_block_at_places_the_armed_block_without_any_clicks(self):
        # Placement is its own method: a direct call builds the block from the
        # armed parts, stamps the item's price on it, hands out its triggers,
        # keeps the item in its inventory spot (marked with the square it stands
        # on) and clears the selection — no mouse events needed.
        self.game.toolbox.items.clear()
        item = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 30, 21, "Pipe +Chips",
                              effects=[main.Effect.BOUNCY],
                              effect_amounts={main.Effect.BOUNCY: 55})
        self.game.toolbox.add(item)
        self.game._equip_block(item)

        self.assertTrue(self.game._place_block_at(2, 3))

        placed = self.game.grid[(2, 3)]
        self.assertEqual((placed.x, placed.y), (2, 3))
        self.assertEqual(placed.shape, main.Shape.PIPE)
        self.assertEqual(placed.effects, [main.Effect.BOUNCY])
        self.assertEqual(placed.effect_magnitude(main.Effect.BOUNCY), 55)
        self.assertEqual(placed.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(placed.resale_price, 21)
        self.assertEqual(placed.triggers_left, 1)
        self.assertIn(item, self.game.toolbox.items)  # keeps its spot
        self.assertEqual(item.placed_cell, (2, 3))
        self.assertFalse(self.game.has_selected)
        self.assertIsNone(self.game.selected_toolbox_item)


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
