"""The board as a surface for ANY item, not only blocks.

The board IS the player's inventory (user request: "remove the card, action, and
inventory ui. move them all to the board"): every owned item — a component, a
card, an action, a Spirit token — stands on a board square, is clicked there and
selected there. Only the blocks are physical.
"""

from tests.game_test_case import *  # noqa: F401,F403


class BoardItemTests(GameTestCase):
    """Laying items out on the board, selecting them and assembling there."""

    def _component(self, kind, value):
        """A component piece of ``kind`` (a shape, effect or scorer)."""
        if kind == main.Component.SHAPE:
            return main.Component.shape_component(value)
        if kind == main.Component.EFFECT:
            return main.Component.effect_component(value)
        return main.Component.scorer_component(value, amount=4)


    def _lay(self, item, gx, gy):
        """Own an item, standing on the given square."""
        self.game.toolbox.add(item)
        self.game.set_item_cell(item, (gx, gy))
        self.game.ensure_board_cells()
        self.assertEqual(self.game.item_cell(item), (gx, gy))
        return item


    def test_clicking_a_component_selects_it_on_the_board(self):
        comp = self._component(main.Component.SHAPE, main.Shape.SLOPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        self.game.toolbox.add(comp)

        self._click(self._item_pos(comp))

        self.assertTrue(self.game.is_item_selected(comp))
        self.assertIs(self.game.item_at_cell(self._item_cell(comp)), comp)
        self.assertIn("press S", self.game.shop_message)


    def test_only_blocks_are_physical(self):
        # The marble only ever meets blocks: a component lying on a square is
        # part of the workbench, and the simulation never sees it.
        comp = self._lay(self._component(main.Component.SCORER, main.Scorer.CHIPS_ADD), 1, 1)
        block = main.Block(2, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(2, 3)] = block

        self.assertEqual(self.game.board_blocks(), [block])
        self.assertEqual(self.game._simulation_blocks(), [block])
        self.assertIn(comp, self.game.board_items())
        self.assertIn(block, self.game.board_items())


    def test_clicking_a_board_component_toggles_its_selection(self):
        # The panel's click rule, ported: one click selects, the next drops it.
        comp = self._lay(self._component(main.Component.EFFECT, main.Effect.BOUNCY), 2, 2)

        self._click(self._grid_pos(2, 2))
        self.assertTrue(self.game.is_item_selected(comp))
        self.assertIn(comp, self.game.assigned_effects())

        self._click(self._grid_pos(2, 2))
        self.assertFalse(self.game.is_item_selected(comp))
        self.assertNotIn(comp, self.game.assigned_effects())
        self.assertEqual(self._item_cell(comp), (2, 2))


    def test_components_on_the_board_assemble_into_a_block_on_the_board(self):
        # The point of laying pieces out: click a shape, click a scorer, press S
        # and the block is built where the pieces lie (the shape's square), the
        # pieces consumed from the board.
        shape = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 2, 2)
        scorer = self._lay(self._component(main.Component.SCORER, main.Scorer.MULT_ADD), 3, 2)

        self._click(self._grid_pos(2, 2))
        self._click(self._grid_pos(3, 2))
        self.assertTrue(self.game.has_assigned_parts())
        self._press(main.pygame.K_s)

        built = self.game.grid.get((2, 2))
        self.assertIsInstance(built, main.Block)
        self.assertEqual(built.shape, main.Shape.PIPE)
        self.assertEqual(built.scorer, main.Scorer.MULT_ADD)
        # The pieces went into the block: neither the board nor the inventory
        # holds them any more.
        self.assertNotIn((3, 2), self.game.grid)
        self.assertFalse(self.game.toolbox.contains(shape))
        self.assertFalse(self.game.toolbox.contains(scorer))
        self.assertFalse(self.game.has_assigned_parts())


    def test_a_component_stays_assigned_when_an_action_is_used(self):
        # Using an action used to re-draw the panel. Nothing re-draws now: the
        # pieces stay where they are and stay part of the next block.
        comp = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 2, 2)
        self._click(self._grid_pos(2, 2))

        self.game._reshuffle_inventory()

        self.assertTrue(self.game.is_item_selected(comp))
        self.assertIs(self.game.assigned_part(main.Component.SHAPE), comp)


    def test_right_clicking_a_board_item_leaves_it_alone(self):
        # The eraser is for blocks: a component (or a card) is scenery the player
        # arranges by moving it.
        comp = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 2, 2)
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 3

        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=self._grid_pos(2, 2)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIs(self.game.item_at_cell((2, 2)), comp)
        self.assertIn("erases blocks", self.game.shop_message)


    def test_a_card_on_the_board_can_be_sold(self):
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        self.game.cards.append(card)
        cash = self.game.cash
        self._click(self._item_pos(card))

        self._press(main.pygame.K_b)

        self.assertNotIn(card, self.game.cards)
        self.assertGreater(self.game.cash, cash)


    def test_every_kind_of_item_is_selected_by_the_one_selection_rule(self):
        # One click on any item selects it — whatever it is — so every item lands
        # in the same selection, which is what draws the green frame (user
        # request: "make all items able to be selected through the same function
        # that highlights selected items in green or yellow").
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.game.actions.append(main.ActionItem(main.Action.EXPANSION, 24))
        items = list(self.game.owned_items())      # blocks, a card and an action

        for item in items:
            self.game._clear_toolbox_selection()
            cell = self._item_cell(item)
            self.assertIsNotNone(cell, item)

            self._click(self._grid_pos(*cell))

            self.assertTrue(self.game.is_item_selected(item), item)
            self.assertIs(self.game.selected_toolbox_item, item, item)


    def test_a_card_is_moved_by_selecting_it_and_clicking_a_square(self):
        card = main.CardItem(main.Card.GARDEN, 36)
        self.game._adopt_card(card)
        home = self._item_cell(card)

        self._click(self._grid_pos(*home))
        self._click(self._grid_pos(6, 5))

        self.assertEqual(self._item_cell(card), (6, 5))
        self.assertIs(self.game.item_at_cell((6, 5)), card)
        self.assertIsNone(self.game.item_at_cell(home))


    def test_an_action_is_selected_and_moved_like_any_other_item(self):
        action = main.ActionItem(main.Action.EXPANSION, 24)
        self.game._adopt_action(action)
        home = self._item_cell(action)

        self._click(self._grid_pos(*home))
        # An action wears the same frame as everything else, so it is in the
        # selection (and armed to be used, see _select_action).
        self.assertTrue(self.game.is_item_selected(action))
        self.assertIs(self.game.selected_action, action)

        self._click(self._grid_pos(7, 4))

        self.assertEqual(self._item_cell(action), (7, 4))
        self.assertIsNone(self.game.item_at_cell(home))


    def test_an_armed_action_still_takes_a_clicked_block_as_its_subject(self):
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game._adopt_action(action)
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect")
        self.game.toolbox.add(block)
        self._click(self._grid_pos(*self._item_cell(action)))

        self._click(self._grid_pos(*self._item_cell(block)))

        # The click does both things it can mean: the block is the action's
        # subject AND its own switch flips on (an armed action never stops the
        # player selecting something).
        self.assertIs(self.game.selected_action_subject, block)
        self.assertTrue(self.game.is_item_selected(block))


    def test_every_item_is_its_own_switch_and_any_number_can_be_on(self):
        # Selection is a bank of switches (user request: "each item acts as a
        # switch that can be turned on and off, where 'on' means 'selected'"):
        # turning one on never turns another off, and any number can be on.
        shape = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 6, 2)
        effect = self._lay(self._component(main.Component.EFFECT, main.Effect.BOUNCY), 7, 2)
        card = main.CardItem(main.Card.GARDEN, 36)
        self.game._adopt_card(card)
        action = main.ActionItem(main.Action.EXPANSION, 24)
        self.game._adopt_action(action)
        everything = (shape, effect, card, action)

        for item in everything:
            self._click(self._grid_pos(*self._item_cell(item)))

        self.assertEqual(len(self.game.selection), len(everything))
        for item in everything:
            self.assertTrue(self.game.is_item_selected(item), item)
        # Only the last one switched on is the item IN HAND.
        self.assertIs(self.game.selected_toolbox_item, action)

        # Switching one off leaves every other switch exactly as it was.
        self._click(self._grid_pos(*self._item_cell(effect)))

        self.assertFalse(self.game.is_item_selected(effect))
        for item in (shape, card, action):
            self.assertTrue(self.game.is_item_selected(item), item)

    def test_every_switched_on_item_is_framed_green(self):
        shape = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 6, 2)
        card = main.CardItem(main.Card.GARDEN, 36)
        self.game._adopt_card(card)
        for item in (shape, card):
            self._click(self._grid_pos(*self._item_cell(item)))

        self.game.screen.fill((0, 0, 0))
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.draw()

        for item in (shape, card):
            rect = self.game._board_item_rect(*self._item_cell(item))
            self.assertEqual(self.game.screen.get_at((rect.x + 1, rect.y + 1))[:3],
                             main.GREEN, item)

    def test_a_second_shape_stays_on_and_the_newest_is_the_one_built(self):
        # A block has ONE shape and ONE scorer, so the newest selected piece is
        # the one S uses — but both switches stay on (they are the player's, not
        # the block's), and switching the newest off hands the slot back.
        first = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 6, 2)
        second = self._lay(self._component(main.Component.SHAPE, main.Shape.SLOPE), 7, 2)

        self._click(self._grid_pos(6, 2))
        self._click(self._grid_pos(7, 2))
        self.assertTrue(self.game.is_item_selected(first))
        self.assertTrue(self.game.is_item_selected(second))
        self.assertIs(self.game.assigned_part(main.Component.SHAPE), second)

        self._click(self._grid_pos(7, 2))

        self.assertIs(self.game.assigned_part(main.Component.SHAPE), first)

    def test_switching_a_block_on_keeps_the_parts_already_on(self):
        # Selecting a block used to clear a half-built assembly. Every item is
        # its own switch now, so the components stay on (and S still prefers the
        # assembly while parts are assigned).
        shape = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 6, 2)
        self._click(self._grid_pos(6, 2))
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect")
        self.game.toolbox.add(block)

        self._click(self._grid_pos(*self._item_cell(block)))

        self.assertTrue(self.game.is_item_selected(shape))
        self.assertTrue(self.game.is_item_selected(block))
        self.assertIs(self.game.assigned_part(main.Component.SHAPE), shape)

    def test_selling_one_item_switches_only_it_off(self):
        shape = self._lay(self._component(main.Component.SHAPE, main.Shape.PIPE), 6, 2)
        card = main.CardItem(main.Card.GARDEN, 36)
        self.game._adopt_card(card)
        self._click(self._grid_pos(6, 2))
        self._click(self._grid_pos(*self._item_cell(card)))
        cash = self.game.cash

        self.game.selected_toolbox_item = card
        self._press(main.pygame.K_b)

        self.assertNotIn(card, self.game.cards)
        self.assertGreater(self.game.cash, cash)
        self.assertFalse(self.game.is_item_selected(card))
        self.assertTrue(self.game.is_item_selected(shape))

    def test_a_moved_block_is_not_selectable_on_the_square_it_left(self):
        # A block whose item was laid out on one square and built on another
        # answers only on the square it STANDS on (user report: "if I move the
        # start block to a different place, I can still select that block by
        # selecting the top left board square").
        block = self.game.toolbox.items[0]
        home = self._item_cell(block)
        self._click(self._grid_pos(*home))
        self._click(self._grid_pos(6, 6))
        self.assertIsInstance(self.game.grid.get((6, 6)), main.Block)
        self.assertEqual(self._item_cell(block), (6, 6))

        self._click(self._grid_pos(*home))

        self.assertIsNone(self.game.item_at_cell(home))
        self.assertFalse(self.game.selection)
        self.assertEqual(sorted(self.game.grid), [(6, 6)])


    def test_a_board_item_rides_through_a_save(self):
        self._lay(self._component(main.Component.SHAPE, main.Shape.DRAIN), 3, 5)
        self.game.save_slot = 4
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)

        fresh.ensure_board_cells()
        loaded = [item for item in fresh.toolbox.items
                  if item.kind == main.Component.SHAPE
                  and item.value == main.Shape.DRAIN]
        self.assertTrue(loaded)
        self.assertEqual(fresh.item_cell(loaded[0]), (3, 5))
