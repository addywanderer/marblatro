"""Hoard: middle-click a shop offer to hold it in place across refreshes.

The card data lives in components.py with the other whole cards, the hold
itself is Game._toggle_shop_lock / Shop.locked, and a held offer says so in its
hover hint (see Game._action_hint) while its tile wears the unbought padlock.
These tests cover the card's rule, its cap ("one held offer per copy of this
card"), what happens when the card leaves, and the event wiring: right-click
BUYS an offer now, so the hold is on the middle button.
"""

from tests.game_test_case import *  # noqa: F401,F403


class HoardCardTests(GameTestCase):
    """The Hoard whole card: one held shop offer per copy of it."""

    def _own_hoard(self, copies=1):
        for _ in range(copies):
            self.game.cards.append(main.CardItem(main.Card.HOARD, 36))

    def _cell_pos(self, item):
        """A point inside a shop offer's board square."""
        return self._item_pos(item)

    def _offer(self, index=0):
        return self.game.shop.items[index]

    def _offer_at(self, item):
        """The offer lying on the square ``item`` occupies (None if it moved on)."""
        return self.game.shop.offer_at_cell(self.game.item_cell(item))

    def test_hoard_card_data(self):
        self.assertIn(main.Card.HOARD, main.Card.ORDER)
        self.assertEqual(main.Card.name(main.Card.HOARD), "Hoard")
        self.assertEqual(main.Card.PRICES[main.Card.HOARD], 36)
        self.assertEqual(main.Card.rarity_name(main.Card.HOARD), "Unusual")
        self.assertTrue(main.Card.comment(main.Card.HOARD))
        self.assertIn("Middle-click", main.Card.description(main.Card.HOARD))
        self.assertIn(main.Card.HOARD, main.Card.COLORS)
        self.assertIn(main.Card.HOARD, main.Card.GLYPHS)
        # A whole card: no group half and no scorer half to split it into.
        self.assertIsNone(components.match_group_card_meta(main.Card.HOARD))
        self.assertIsNone(components.card_scorer(main.Card.HOARD))


    def test_the_cap_is_one_held_offer_per_copy_of_the_card(self):
        # None without the card, one per copy with it — the user's "maximum of 1
        # locked option, with multiple copies raising it".
        self.assertEqual(self.game.shop_lock_cap(), 0)
        self._own_hoard()
        self.assertEqual(self.game.shop_lock_cap(), 1)
        self._own_hoard()
        self.assertEqual(self.game.shop_lock_cap(), 2)


    def test_middle_clicking_an_offer_holds_it_through_a_reroll(self):
        self._own_hoard()
        held = self._offer(0)
        slot = self.game.shop.slot_key(held)
        count_before = len(self.game.shop.items)
        self.assertTrue(self.game._toggle_shop_lock(self._cell_pos(held)))
        self.assertEqual(self.game.shop.locked, [slot])
        self.assertIn("Holding", self.game.shop_message)

        self.game._refresh_shop()

        # The pinned cell holds the very same offer (not a re-rolled one that
        # merely looks the same), and the row is still a full row.
        self.assertIs(self._offer_at(held), held)
        self.assertEqual(len(self.game.shop.items), count_before)
        self.assertEqual(self.game.shop.locked, [slot])


    def test_middle_clicking_a_held_offer_again_releases_it(self):
        self._own_hoard()
        held = self._offer(0)
        self.game._toggle_shop_lock(self._cell_pos(held))
        self.assertTrue(self.game.shop.locked)
        self.assertTrue(self.game._toggle_shop_lock(self._cell_pos(held)))
        self.assertEqual(self.game.shop.locked, [])
        self.assertIn("Released", self.game.shop_message)
        # Released, so the next reroll is free to change it like any other cell.
        self.game._refresh_shop()
        self.assertIsNot(self._offer_at(held), held)


    def test_a_second_hold_needs_a_second_copy_of_the_card(self):
        self._own_hoard()
        first, second = self._offer(0), self._offer(1)
        self.game._toggle_shop_lock(self._cell_pos(first))
        # The cap is full: the click is still the card's business (the player is
        # told why), so the board's erase never sees it.
        self.assertTrue(self.game._toggle_shop_lock(self._cell_pos(second)))
        self.assertEqual(self.game.shop.locked, [self.game.shop.slot_key(first)])
        self.assertIn("release one first", self.game.shop_message)
        # A second copy of the card pins the second offer as well.
        self._own_hoard()
        self.game._toggle_shop_lock(self._cell_pos(second))
        self.assertEqual(len(self.game.shop.locked), 2)


    def test_without_the_card_a_middle_click_holds_nothing(self):
        held = self._offer(0)
        self.assertTrue(self.game._toggle_shop_lock(self._cell_pos(held)))
        self.assertEqual(self.game.shop.locked, [])
        self.assertIn("you do not own it", self.game.shop_message)


    def test_a_middle_click_on_an_empty_square_does_nothing(self):
        # The click only belongs to Hoard when it lands on an offer.
        self._own_hoard()
        cell = (main.GRID_WIDTH - 1, main.GRID_HEIGHT - 1)
        self.assertIsNone(self.game.item_at_cell(cell))
        self.assertFalse(self.game._toggle_shop_lock(self._grid_pos(*cell)))
        self.assertEqual(self.game.shop.locked, [])


    def test_a_hold_the_card_can_no_longer_pay_for_is_released(self):
        # Selling the card drops the cap, and the offer pinned LAST gives way
        # first — what the player pinned first is what stays held.
        self._own_hoard(2)
        first, second = self._offer(0), self._offer(1)
        self.game._toggle_shop_lock(self._cell_pos(first))
        self.game._toggle_shop_lock(self._cell_pos(second))
        self.assertEqual(len(self.game.shop.locked), 2)

        self.game.cards.pop()                 # one copy sold
        self.game._clip_shop_locks()
        self.assertEqual(self.game.shop.locked, [self.game.shop.slot_key(first)])

        self.game.cards = []                  # both copies gone
        self.game._clip_shop_locks()
        self.assertEqual(self.game.shop.locked, [])
        self.game._refresh_shop()
        self.assertIsNot(self._offer_at(first), first)


    def test_a_card_cutter_hoard_holds_nothing(self):
        # The cut card applies no effect, so its hold is released with it.
        hoard = main.CardItem(main.Card.HOARD, 36)
        self.game.cards = [hoard]
        held = self._offer(0)
        self.game._toggle_shop_lock(self._cell_pos(held))
        self.assertTrue(self.game.shop.locked)

        self.game.disabled_card = hoard
        self.assertEqual(self.game.shop_lock_cap(), 0)
        self.game._refresh_shop()
        self.assertEqual(self.game.shop.locked, [])
        self.assertIsNot(self._offer_at(held), held)


    def test_a_held_offer_survives_the_slim_pickings_trim(self):
        # Slim pickings removes two options right after every reroll — the very
        # moment a held offer would otherwise vanish.
        self._own_hoard()
        held = self._offer(0)
        self.game._toggle_shop_lock(self._cell_pos(held))
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SLIM_PICKINGS

        self.game._trim_shop_for_trial()

        self.assertIn(held, self.game.shop.items)


    def test_middle_clicking_a_shop_offer_never_erases_the_board(self):
        # End to end through the real event handler: the middle button is the
        # Hoard card's, so the board is untouched.
        self._own_hoard()
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.CHIPS_ADD)
        held = self._offer(0)
        self._middle_click(self._cell_pos(held))

        self.assertEqual(self.game.shop.locked, [self.game.shop.slot_key(held)])
        self.assertIn((2, 2), self.game.grid)


    def test_right_clicking_a_shop_offer_buys_it_instead_of_holding_it(self):
        # Right-click is the BUY click (user request), so a Hoard player's
        # right-click unlocks the offer rather than pinning it.
        self._own_hoard()
        self.game.cash = 5000
        offer = self._offer(0)
        price = self.game._buy_price(offer)
        self._right_click(self._cell_pos(offer))

        self.assertEqual(self.game.cash, 5000 - price)
        self.assertEqual(self.game.shop.locked, [])


    def test_a_right_click_on_the_board_still_does_nothing(self):
        # Right-clicking the board is not the board's business any more (user
        # request: "remove whatever right-clicking does"). A block stays put and
        # nothing is armed.
        self._own_hoard()
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.CHIPS_ADD)
        self._right_click(self._grid_pos(2, 2))

        self.assertEqual(self.game.shop.locked, [])
        self.assertIn((2, 2), self.game.grid)
        self.assertFalse(self.game.drawing)
