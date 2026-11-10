"""The WASTEFUL effect: throw this block and one other item away, draw a new one.

User request: "add an effect, 'wasteful': can use this block to discard this block
and a different item, and draw a new item." It is the one effect the PLAYER uses —
the block is the actor, the item selected behind it is what it takes with it, and
`S` does the rest (see Game._use_wasteful).
"""

from tests.game_test_case import *  # noqa: F401,F403


class WastefulDataTests(GameTestCase):
    """The effect itself: its catalogue row and its place in the lists."""

    def test_wasteful_data_lives_in_components(self):
        self.assertIn(main.Effect.WASTEFUL, main.Effect.ORDER)
        self.assertIn(main.Effect.WASTEFUL, main.Effect.REAL_ORDER)
        self.assertEqual(main.Effect.name(main.Effect.WASTEFUL), "Wasteful")
        self.assertIn("draw a new item",
                      main.effect_description(main.Effect.WASTEFUL))
        self.assertGreater(
            main.COMPONENT_PRICES[(main.Component.EFFECT,
                                   main.Effect.WASTEFUL)], 0)
        # It is on/off: there is no magnitude to roll.
        self.assertNotIn(main.Effect.WASTEFUL, main.Effect.MAGNITUDE)
        # Effects must be APPENDED, never inserted (see
        # test_new_effects_were_appended_to_the_effect_order): the newest one is
        # last, and it is the one it is.
        self.assertEqual(main.Effect.ORDER[-1], main.Effect.WASTEFUL)
        self.assertEqual(main.Effect.REAL_ORDER[-1], main.Effect.WASTEFUL)

    def test_a_block_wearing_it_is_a_wasteful_block(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.WASTEFUL,
                               main.Scorer.CHIPS_ADD, 0, 30, "Wasteful Rect")
        self.assertTrue(self.game.is_wasteful(block))
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.BOUNCY,
                               main.Scorer.CHIPS_ADD, 0, 30, "Bouncy Rect")
        self.assertFalse(self.game.is_wasteful(plain))
        self.assertFalse(self.game.is_wasteful(main.Component.effect_component(
            main.Effect.WASTEFUL)))


class WastefulUseTests(GameTestCase):
    """Using it: the actor, its one target, and the draw that replaces them."""

    def _wasteful(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.WASTEFUL,
                               main.Scorer.CHIPS_ADD, 0, 30, "Wasteful Rect")
        self.game.toolbox.add(block)
        self.game.ensure_board_cells()
        return block

    def _spare(self):
        spare = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(spare)
        self.game.ensure_board_cells()
        return spare

    def _fill_deck(self, count=3):
        """Put ``count`` shapes in the deck (owned, but not drawn)."""
        shapes = [main.Component.shape_component(main.Shape.SLOPE)
                  for _ in range(count)]
        for shape in shapes:
            self.game.toolbox.add(shape)
            self.game._to_deck(shape)
        return shapes

    def _use(self, actor, target):
        self._click(self._item_pos(actor))
        self._click(self._item_pos(target))
        self._press(main.pygame.K_s)

    def test_it_throws_away_the_block_and_one_other_item_and_draws_one(self):
        block = self._wasteful()
        spare = self._spare()
        deck = self._fill_deck(3)
        owned_before = len(self.game.owned_items())

        self._use(block, spare)

        self.assertIn("drew", self.game.shop_message)
        self.assertFalse(self.game.owns_item(block))
        self.assertFalse(self.game.owns_item(spare))
        # Two items are destroyed, and the deck pays for the draw: the item drawn
        # was already owned (it was waiting in the deck), so ownership simply
        # loses the two thrown away.
        self.assertEqual(len(self.game.owned_items()), owned_before - 2)
        self.assertEqual(len(self.game.deck_items()), len(deck) - 1)

    def test_the_drawn_item_takes_the_blocks_square(self):
        block = self._wasteful()
        spare = self._spare()
        self._fill_deck(3)
        home = self._item_cell(block)

        self._use(block, spare)

        here = self.game.item_at_cell(home)
        self.assertIsNotNone(here)
        self.assertNotIn(here, (block, spare))
        self.assertEqual(self._item_cell(here), home)

    def test_it_needs_exactly_one_other_item(self):
        block = self._wasteful()
        self._fill_deck(2)

        # Nothing else selected: the ordinary S meaning is left alone (the block
        # is disassembled), so ask for a target explicitly.
        self._click(self._item_pos(block))
        self.game.selection = [block]
        self.game._refresh_actor()
        self.assertFalse(self.game._use_wasteful())
        self.assertIn("1 other item — 0 selected", self.game.shop_message)
        self.assertTrue(self.game.owns_item(block))

        # Two others is one too many.
        first, second = self._spare(), self._spare()
        self.game.selection = [block, first, second]
        self.game._refresh_actor()
        self.assertFalse(self.game._use_wasteful())
        self.assertIn("1 other item — 2 selected", self.game.shop_message)
        self.assertTrue(self.game.owns_item(block))
        self.assertTrue(self.game.owns_item(first))
        self.assertTrue(self.game.owns_item(second))

    def test_it_needs_an_item_in_the_deck_to_draw(self):
        block = self._wasteful()
        spare = self._spare()
        # Nothing is waiting in the deck: every owned item stands on the board.
        self.assertEqual(self.game.deck_items(), [])

        self._use(block, spare)

        self.assertIn("deck", self.game.shop_message)
        # Nothing happened at all: nothing was thrown away.
        self.assertTrue(self.game.owns_item(block))
        self.assertTrue(self.game.owns_item(spare))

    def test_it_will_not_throw_away_an_item_that_is_not_yours(self):
        self._stock_shelf(2, 1)  # a pack is on sale
        block = self._wasteful()
        self._fill_deck(2)
        self.game.ensure_board_cells()
        offer = next(item for item in self.game.shop.items
                     if getattr(item, "kind", None) == "pack")

        self._use(block, offer)

        self.assertIn("one of your own items", self.game.shop_message)
        self.assertTrue(self.game.owns_item(block))
        self.assertIn(offer, self.game.shop.items)

    def test_a_placed_block_is_used_and_its_item_goes_with_it(self):
        block = self._wasteful()
        spare = self._spare()
        self._fill_deck(2)
        self.game._equip_block(block)
        self.game._place_block_at(3, 3)
        self.assertIn((3, 3), self.game.grid)

        self._use(self.game.grid[(3, 3)], spare)

        self.assertNotIn((3, 3), self.game.grid)
        self.assertFalse(self.game.owns_item(block))   # its item went with it
        self.assertFalse(self.game.owns_item(spare))
        drawn = self.game.item_at_cell((3, 3))
        self.assertIsNotNone(drawn)

    def test_with_no_target_s_still_takes_the_block_apart(self):
        # The effect does not steal S from every other use of a block: with
        # nothing selected behind it the block is disassembled as usual.
        block = self._wasteful()
        self._fill_deck(2)

        self._click(self._item_pos(block))
        self._press(main.pygame.K_s)

        self.assertFalse(self.game.owns_item(block))
        # Disassembling hands its parts back, so nothing was thrown away for a
        # draw.
        self.assertGreaterEqual(len(self.game.toolbox.items), 2)
        self.assertEqual(len(self.game.deck_items()), 2)

    def test_the_hover_says_how_to_use_it(self):
        block = self._wasteful()
        hint = self.game._action_hint(block, "board")
        self.assertIn("S", hint)
        self.assertIn("draw", hint)
        rows = dict(self.game._describe_item(block))
        text = " ".join(rows.values())
        self.assertIn("draw a new item", text)
