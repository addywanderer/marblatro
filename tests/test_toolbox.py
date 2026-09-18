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

        self.assertIn(offer, self.game.toolbox.items)
        self.assertEqual(offer.shape, main.Shape.RECT)
        self.assertEqual(offer.effects, [])
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


    def test_a_key_rotates_next_placement_when_nothing_selected(self):
        self.assertEqual(self.game.current_block_angle, 0)
        self.game.selected_toolbox_item = None

        self._press(main.pygame.K_a)

        self.assertEqual(self.game.current_block_angle, 90)


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
        # consumes the item and clears the selection — no mouse events needed.
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
        self.assertNotIn(item, self.game.toolbox.items)  # consumed on placement
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
