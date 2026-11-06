"""The inventory IS the board: what the player owns stands on board squares.

The inventory panel, the card tray and the action row are gone (user request:
"remove the card, action, and inventory ui. move them all to the board"), so
every owned item is laid out on the board, clicked there and selected there.
This module covers that layout and the rules around it; the drawing and the
selection itself are covered by test_board_items / test_toolbox / test_ui.
"""

from tests.game_test_case import *  # noqa: F401,F403


class BoardInventoryTests(GameTestCase):
    """Every owned item stands on its own board square."""

    def _component(self, shape=main.Shape.PIPE):
        return main.Component.shape_component(shape)

    def _cells_of(self, items):
        self.game.ensure_board_cells()
        return [self.game.item_cell(item) for item in items]


    def test_the_starting_blocks_lie_on_the_board(self):
        # A new game hands the player a Start and a Finish block; with no panel
        # to hold them they are laid out on board squares of their own.
        starts = [item for item in self.game.toolbox.items
                  if getattr(item, "scorer", None) == main.Scorer.START]
        finishes = [item for item in self.game.toolbox.items
                    if getattr(item, "scorer", None) == main.Scorer.FINISH]
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(finishes), 1)
        cells = self._cells_of([starts[0], finishes[0]])
        self.assertNotIn(None, cells)
        self.assertNotEqual(cells[0], cells[1])


    def test_a_bought_item_shows_up_on_the_board(self):
        # Nothing is left in a panel: whatever joins the inventory is given a
        # square the moment it arrives.
        comp = self._component()
        self.game.toolbox.add(comp)

        cell = self._item_cell(comp)

        self.assertIsNotNone(cell)
        self.assertIs(self.game.item_at_cell(cell), comp)
        self.assertIn(comp, self.game.board_items())


    def test_a_card_and_an_action_lie_on_the_board_too(self):
        card = main.CardItem(main.Card.COUPON, 40)
        action = main.ActionItem(main.Action.INACTION, 24)
        self.game.cards.append(card)
        self.game.actions.append(action)
        self.game._on_item_gained(card)
        self.game._on_item_gained(action)

        card_cell = self._item_cell(card)
        action_cell = self._item_cell(action)

        self.assertIsNotNone(card_cell)
        self.assertIsNotNone(action_cell)
        self.assertNotEqual(card_cell, action_cell)
        self.assertIs(self.game.item_at_cell(card_cell), card)
        self.assertIs(self.game.item_at_cell(action_cell), action)


    def test_every_owned_item_is_either_on_the_board_or_in_the_deck(self):
        # The board shows the HAND (the items drawn from the deck), so an item
        # the player owns either lies on a square of its own or waits in the
        # deck — never on top of another item (user request: "create a deck").
        for shape in (main.Shape.PIPE, main.Shape.SLOPE, main.Shape.RECT):
            self.game.toolbox.add(self._component(shape))
        self.game.cards.append(main.CardItem(main.Card.COUPON, 40))

        hand = self.game.hand_items()
        deck = self.game.deck_items()
        cells = self._cells_of(hand)

        self.assertNotIn(None, cells)
        self.assertEqual(len(cells), len(set(cells)))
        self.assertEqual(len(hand) + len(deck), len(self.game.owned_items()))
        # What the board has no room for is IN THE DECK, not lost: a card the
        # player owns is a card in the deck.
        self.assertIn(self.game.cards[0], deck)
        self.assertEqual(len(deck), 1)


    def test_items_never_lie_on_a_locked_square(self):
        # A locked square is solid wall, so nothing can be put down on it: an
        # item laid out after the board is locked down stays inside the start
        # region, and any item previously outside it is re-laid inside.
        self.game._reset_board_to_start()
        comp = self._component()
        self.game.toolbox.add(comp)

        cell = self._item_cell(comp)

        self.assertIsNotNone(cell)
        self.assertFalse(self.game.is_cell_locked(*cell))
        for item in self.game.owned_items():
            laid = self._item_cell(item)
            self.assertFalse(self.game.is_cell_locked(*laid), item)


    def test_a_block_keeps_the_square_it_stands_on(self):
        # A placed block owns its square: the item it came from is not laid out
        # anywhere else (one block is never drawn twice).
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.assertTrue(self.game._place_block_at(1, 1))

        self.game.ensure_board_cells()

        self.assertNotIn(block, self.game.board_items())
        self.assertIsInstance(self.game.grid[(1, 1)], main.Block)
        self.assertEqual(block.placed_cell, (1, 1))


    def test_clicking_an_item_moves_it_to_the_clicked_square(self):
        comp = self._component()
        self.game.toolbox.add(comp)
        self._click(self._item_pos(comp))          # select it
        self._click(self._grid_pos(4, 4))          # put it down there

        self.assertEqual(self._item_cell(comp), (4, 4))
        self.assertIs(self.game.item_at_cell((4, 4)), comp)


    def test_a_block_square_refuses_a_moved_item(self):
        comp = self._component()
        self.game.toolbox.add(comp)
        self.game.grid[(4, 4)] = main.Block(4, 4, scorer=main.Scorer.CHIPS_ADD)
        self._click(self._item_pos(comp))

        self._click(self._grid_pos(4, 4))

        self.assertNotEqual(self._item_cell(comp), (4, 4))
        self.assertIsInstance(self.game.grid[(4, 4)], main.Block)


    def test_a_locked_square_refuses_a_moved_item(self):
        # Clicking a locked square asks to unlock it, never to put an item down:
        # nothing may ever stand on a locked square.
        self.game._reset_board_to_start()
        comp = self._component()
        self.game.toolbox.add(comp)

        self._click(self._item_pos(comp))
        self._click(self._grid_pos(0, 0))

        self.assertTrue(self.game.is_cell_locked(0, 0))
        self.assertNotEqual(self._item_cell(comp), (0, 0))


    def test_an_unlocked_square_brings_a_stashed_item_out(self):
        # Items only lie on unlocked squares, so opening one is what makes room
        # for an item that was waiting.
        self.game._reset_board_to_start()
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        for cell in self.game.unlocked_cells:
            self.game.grid[cell] = main.Block(cell[0], cell[1],
                                              scorer=main.Scorer.NONE)
        extra = self._component()
        self.game.toolbox.add(extra)
        self.assertIsNone(self._item_cell(extra))

        self.game._unlock_cell(0, 0)

        self.assertEqual(self._item_cell(extra), (0, 0))
        self.assertNotIn(extra, self.game.toolbox.stash)


    def test_the_stash_catches_what_the_board_cannot_hold(self):
        # The board is finite now, so a full board leaves the item waiting
        # (still owned and sellable) instead of refusing it.
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        for x in range(main.GRID_WIDTH):
            for y in range(main.GRID_HEIGHT):
                self.game.grid[(x, y)] = main.Block(
                    x, y, scorer=main.Scorer.NONE)
        extra = self._component()
        self.game.toolbox.add(extra)

        self.assertIsNone(self._item_cell(extra))
        self.assertTrue(self.game.toolbox.contains(extra))
        self.assertIn(extra, self.game.toolbox.stash)


    def test_a_freed_square_brings_a_stashed_item_out(self):
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        for x in range(main.GRID_WIDTH):
            for y in range(main.GRID_HEIGHT):
                self.game.grid[(x, y)] = main.Block(
                    x, y, scorer=main.Scorer.NONE)
        self.game.ensure_board_cells()
        extra = self._component()
        self.game.toolbox.add(extra)
        self.assertIsNone(self._item_cell(extra))

        self.game.grid.pop((5, 5))
        self.game.ensure_board_cells()

        self.assertIsNotNone(self._item_cell(extra))
        self.assertNotIn(extra, self.game.toolbox.stash)


    def test_an_items_square_rides_through_a_save(self):
        comp = self._component()
        self.game.toolbox.add(comp)
        self.game.save_slot = 6
        save_system.save_game(self.game)
        cell = self._item_cell(comp)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 6)

        fresh.ensure_board_cells()
        loaded = [item for item in fresh.toolbox.items
                  if item.kind == main.Component.SHAPE
                  and item.value == main.Shape.PIPE]
        self.assertTrue(loaded)
        self.assertEqual(fresh.item_cell(loaded[0]), cell)


    def test_the_card_cap_still_refuses_a_card(self):
        # A card lies on a board square, but how MANY cards the player may own
        # is still the card cap (Essence and Inaction move it).
        for i in range(self.game.max_cards):
            self.game.cards.append(main.CardItem(main.Card.COUPON + i, 40))
        extra = main.CardItem(main.Card.MARKET, 40)

        self.game._receive_pack_item(extra)

        self.assertNotIn(extra, self.game.cards)
