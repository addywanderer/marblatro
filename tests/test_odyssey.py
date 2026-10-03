"""Odyssey: press G to put a block or component away for the run.

The card data lives in components.py with the other whole cards, the verb is
Game._bank_selected_item (the G key, wired in handle_events), the banked items
are Game.inaccessible — drawn in their own column to the right of the Spirit
tokens (see ui.draw_inaccessible) — and they come back, with cash, when a
finished run is committed (Game._return_inaccessible, called by _continue_run).
These tests cover the card's rule, its cap ("one item per copy"), what happens
on a retry rather than a continue, and the save round-trip.
"""

from tests.game_test_case import *  # noqa: F401,F403


class OdysseyCardTests(GameTestCase):
    """The Odyssey whole card: one banked item per copy of it."""

    def _own_odyssey(self, copies=1):
        for _ in range(copies):
            self.game.cards.append(main.CardItem(main.Card.ODYSSEY, 40))

    def _wall(self, price=40, name="Wall"):
        """A plain Rect block item in the inventory, selected for banking."""
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, price, name)
        self.game.toolbox.add(block)
        return block

    def _select(self, item):
        self.game.selected_toolbox_item = item
        self.game.selected_toolbox_index = (
            self.game.toolbox.items.index(item)
            if item in self.game.toolbox.items else None)

    def test_odyssey_card_data(self):
        self.assertIn(main.Card.ODYSSEY, main.Card.ORDER)
        self.assertEqual(main.Card.name(main.Card.ODYSSEY), "Odyssey")
        self.assertEqual(main.Card.PRICES[main.Card.ODYSSEY], 40)
        self.assertEqual(main.Card.rarity_name(main.Card.ODYSSEY), "Rare")
        self.assertTrue(main.Card.comment(main.Card.ODYSSEY))
        self.assertIn("G", main.Card.description(main.Card.ODYSSEY))
        self.assertIn(main.Card.ODYSSEY, main.Card.COLORS)
        self.assertIn(main.Card.ODYSSEY, main.Card.GLYPHS)
        # A utility whole card with a VERB (like Hoard's right-click): no group
        # half and no scorer half, and not one of the measured cards.
        self.assertIsNone(components.match_group_card_meta(main.Card.ODYSSEY))
        self.assertIsNone(components.card_scorer(main.Card.ODYSSEY))
        self.assertNotIn(main.Card.ODYSSEY, components.NAMED_CARD_ORDER)

    def test_the_cap_is_one_item_per_copy_of_the_card(self):
        # None without the card, one per copy with it — the same rule Hoard's
        # holds follow.
        self.assertEqual(self.game.inaccessible_cap(), 0)
        self._own_odyssey()
        self.assertEqual(self.game.inaccessible_cap(), 1)
        self._own_odyssey()
        self.assertEqual(self.game.inaccessible_cap(), 2)

    def test_it_needs_the_card_and_a_selected_inventory_item(self):
        wall = self._wall()
        self._select(wall)

        # No Odyssey: nothing is banked, and the message says why.
        self.assertFalse(self.game._bank_selected_item())
        self.assertIn("Only the Odyssey card", self.game.shop_message)
        self.assertIn(wall, self.game.toolbox.items)

        self._own_odyssey()
        # Nothing selected at all.
        self.game.selected_toolbox_item = None
        self.assertFalse(self.game._bank_selected_item())
        self.assertIn("Select a block or component", self.game.shop_message)
        # A card is not a block or a component: it is sold, not banked.
        card = main.CardItem(main.Card.MARKET, 26)
        self.game.cards.append(card)
        self._select(card)
        self.assertFalse(self.game.can_bank_selected())
        self.assertFalse(self.game._bank_selected_item())
        # Neither is a block sitting on the board: it is not IN the inventory.
        placed = main.Block(3, 3)
        self.game.grid[(3, 3)] = placed
        self.game.selected_toolbox_item = placed
        self.assertFalse(self.game.can_bank_selected())

    def test_the_selected_item_leaves_the_inventory_until_after_the_run(self):
        self._own_odyssey()
        wall = self._wall()
        self._select(wall)

        self.assertTrue(self.game._bank_selected_item())

        self.assertNotIn(wall, self.game.toolbox.items)
        self.assertEqual(self.game.inaccessible, [wall])
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertIn("waits out this run", self.game.shop_message)

    def test_it_is_refused_at_the_cap(self):
        self._own_odyssey()
        first = self._wall()
        self._select(first)
        self.assertTrue(self.game._bank_selected_item())
        second = self._wall()
        self._select(second)

        self.assertFalse(self.game._bank_selected_item())

        self.assertIn("(1 max)", self.game.shop_message)
        self.assertIn(second, self.game.toolbox.items)
        self.assertEqual(self.game.inaccessible, [first])
        # A second copy of the card banks a second item.
        self._own_odyssey()
        self.assertTrue(self.game._bank_selected_item())
        self.assertEqual(len(self.game.inaccessible), 2)

    def test_banking_unassigns_the_item_from_the_assembler(self):
        # The assembler works by index into the inventory, so a component on its
        # way out cannot stay assigned to it.
        self._own_odyssey()
        shape = main.Component.shape_component(main.Shape.CIRCLE, price=20)
        self.game.toolbox.add(shape)
        self._select(shape)
        self.game._use_component(shape)
        self.assertIs(self.game.assembler.shape, shape)

        self.assertTrue(self.game._bank_selected_item())

        self.assertIsNone(self.game.assembler.shape)
        self.assertNotIn(shape, self.game.assembler.effects)
        self.assertNotIn(shape, self.game.assigned_toolbox_indexes)

    def test_the_item_comes_back_and_pays_half_its_sell_price(self):
        self._own_odyssey()
        wall = self._wall(price=40)
        self._select(wall)
        self.assertTrue(self.game._bank_selected_item())
        cash_before = self.game.cash

        paid = self.game._return_inaccessible()

        # Half of the $20 a plain sale would refund.
        self.assertEqual(paid, 10)
        self.assertEqual(self.game.cash, cash_before + 10)
        self.assertIn(wall, self.game.toolbox.items)
        self.assertEqual(self.game.inaccessible, [])
        self.assertIn("$10", self.game.shop_message)

    def test_market_raises_what_a_banked_item_pays(self):
        # It pays a fraction of the SELL price, so the Market card's 75% raises
        # it exactly as it raises the sale it is a fraction of.
        self._own_odyssey()
        self.game.cards.append(main.CardItem(main.Card.MARKET, 26))
        wall = self._wall(price=40)
        self._select(wall)
        self.assertTrue(self.game._bank_selected_item())
        cash_before = self.game.cash

        self.assertEqual(self.game._bank_value(wall), 15)   # 0.5 x (40 x 0.75)

        self.game._return_inaccessible()
        self.assertEqual(self.game.cash, cash_before + 15)

    def test_nothing_is_paid_while_nothing_is_banked(self):
        self.game.cash = 1000

        self.assertEqual(self.game._return_inaccessible(), 0)
        self.assertEqual(self.game.cash, 1000)

    def test_a_full_inventory_withholds_the_item_until_there_is_room(self):
        # An item that cannot fit back into the inventory stays banked and pays
        # nothing yet — it is never lost, and the message says why. It pays
        # when it finally comes home.
        self._own_odyssey()
        wall = self._wall(price=40)
        self._select(wall)
        self.assertTrue(self.game._bank_selected_item())
        cash_before = self.game.cash
        # Fill every remaining cell of the inventory.
        for _ in range(self.game.toolbox.cols * self.game.toolbox.rows):
            self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT,
                                                 main.Effect.NONE,
                                                 main.Scorer.NONE, 0, 12, "Wall"))
        self.game.shop_message = ""

        paid = self.game._return_inaccessible()

        self.assertEqual(paid, 0)
        self.assertEqual(self.game.cash, cash_before)
        self.assertEqual(self.game.inaccessible, [wall])  # the item waits
        self.assertIn("no room in the inventory", self.game.shop_message)
        # Make room and it comes home with its cash.
        self.game.toolbox.items.pop()

        self.assertEqual(self.game._return_inaccessible(), 10)
        self.assertEqual(self.game.inaccessible, [])

    def test_a_retry_keeps_the_item_banked_and_pays_nothing(self):
        # Banking is build-phase state: the run the item waits out is the run
        # being retried, so a retry neither returns it nor pays (the same rule
        # every other per-run gain follows).
        self._own_odyssey()
        wall = self._wall(price=40)
        self.game.grid[(5, 9)] = main.Block(5, 9, scorer=main.Scorer.START)
        self._select(wall)
        self.assertTrue(self.game._bank_selected_item())
        cash_before = self.game.cash

        self.game._retry_run()

        self.assertEqual(self.game.inaccessible, [wall])
        self.assertNotIn(wall, self.game.toolbox.items)
        self.assertEqual(self.game.cash, cash_before)

    def test_a_continued_run_returns_the_item_and_pays(self):
        # The whole point of the card: put something away for the run and it
        # pays out when the run is over.
        self._own_odyssey()
        wall = self._wall(price=40)
        self._select(wall)
        self.assertTrue(self.game._bank_selected_item())
        cash_before = self.game.cash

        self._play_run(0)                       # a finished run, then CONTINUE

        self.assertEqual(self.game.inaccessible, [])
        self.assertIn(wall, self.game.toolbox.items)
        self.assertGreater(self.game.cash, cash_before)

    def test_a_card_that_leaves_releases_nothing_it_is_still_banking(self):
        # The cap is read live (like Hoard's), so selling the card does not
        # strand an item: the next banking is simply refused, and what is
        # already away still comes back on the next continue.
        card = main.CardItem(main.Card.ODYSSEY, 40)
        self.game.cards.append(card)
        wall = self._wall(price=40)
        self._select(wall)
        self.assertTrue(self.game._bank_selected_item())

        self.game.cards.remove(card)

        self.assertEqual(self.game.inaccessible_cap(), 0)
        self.assertFalse(self.game._bank_selected_item())
        self.assertEqual(self.game._return_inaccessible(), 10)
        self.assertEqual(self.game.inaccessible, [])


class OdysseyWiringTests(GameTestCase):
    """The G key, the drawn column and the save."""

    def _own_odyssey(self):
        self.game.cards.append(main.CardItem(main.Card.ODYSSEY, 40))

    def _select_wall(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 40, "Wall")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.selected_toolbox_index = 0
        return block

    def test_g_puts_the_selected_item_away(self):
        self._own_odyssey()
        wall = self._select_wall()

        self._press(main.pygame.K_g)

        self.assertEqual(self.game.inaccessible, [wall])
        self.assertNotIn(wall, self.game.toolbox.items)

    def test_g_does_nothing_without_the_card(self):
        wall = self._select_wall()

        self._press(main.pygame.K_g)

        self.assertEqual(self.game.inaccessible, [])
        self.assertIn(wall, self.game.toolbox.items)

    def test_the_column_sits_right_of_the_token_column(self):
        self._own_odyssey()
        wall = self._select_wall()
        self.assertTrue(self.game._bank_selected_item())

        first = self.game.inaccessible_rect(0)
        second = self.game.inaccessible_rect(1)
        self.assertEqual(first.x, main.INACCESSIBLE_COORDS[0])
        self.assertEqual(first.y, main.INACCESSIBLE_COORDS[1])
        self.assertGreater(first.x, main.TOKEN_COORDS[0])
        self.assertEqual(second.y - first.y, main.GRID_SIZE)   # one slot each

    def test_the_column_is_drawn_with_the_banked_item(self):
        self._own_odyssey()
        # A component, whose face is its own colour (a plain Rect block is drawn
        # black inside, which would be indistinguishable from an empty screen).
        shape = main.Component.shape_component(main.Shape.CIRCLE, price=20)
        self.game.toolbox.add(shape)
        self.game.selected_toolbox_item = shape
        self.game.selected_toolbox_index = 0
        self.assertTrue(self.game._bank_selected_item())
        self.game.screen.fill(main.BLACK)

        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            main.ui.draw_inaccessible(self.game)

        rect = self.game.inaccessible_rect(0)
        painted = {tuple(self.game.screen.get_at((x, y)))[:3]
                   for x in range(rect.left, rect.right)
                   for y in range(rect.top, rect.bottom)}
        self.assertGreater(len(painted), 1)      # the slot is not left black
        # Nothing is drawn while nothing is banked.
        self.game.screen.fill(main.BLACK)
        self.game.inaccessible = []
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            main.ui.draw_inaccessible(self.game)
        self.assertEqual({tuple(self.game.screen.get_at((x, y)))[:3]
                          for x in range(rect.left, rect.right)
                          for y in range(rect.top, rect.bottom)}, {(0, 0, 0)})

    def test_the_sidebar_offers_the_g_key(self):
        # The hint beside the inventory is where the player is looking when they
        # want the verb, and it only appears when G would do something.
        wall = self._select_wall()
        self.assertNotIn("G to", self.game._action_hint(wall, "toolbox"))
        self._own_odyssey()
        self.assertIn("G to put it away", self.game._action_hint(wall, "toolbox"))
        self.assertIn("Left-click", self.game._action_hint(wall, "toolbox"))
