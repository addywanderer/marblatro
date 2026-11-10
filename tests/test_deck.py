"""The DECK: every item the player owns, and the hand drawn from it.

The board shows a HAND of DECK_DRAW_SIZE items drawn from the deck (user
request: "create a deck ... when a new run begins, draw 4 random cards from the
deck onto the board, along with the shop's offers"), so what the player owns is
split in two: the items lying on board squares, and the deck behind them. These
tests cover the split, the draw at the end of a committed run, buying into the
deck, and the DECK button that shows the whole thing.
"""

from tests.game_test_case import *  # noqa: F401,F403


class DeckTests(GameTestCase):
    """The deck, the hand, and the draw between runs."""

    def _component(self, shape=main.Shape.PIPE):
        return main.Component.shape_component(shape)

    def _own(self, count=6):
        """Own ``count`` items (they join the hand through Toolbox.add)."""
        items = [self._component()]
        for _ in range(count - 1):
            items.append(main.Component.effect_component(main.Effect.BOUNCY))
        for item in items:
            self.game.toolbox.add(item)
        return items

    def _start_block_item(self):
        return next(item for item in self.game.owned_items()
                    if getattr(item, "scorer", None) == main.Scorer.START)

    def test_a_new_game_draws_a_full_hand(self):
        # User request: "make sure the player always draws 4 items, besides the
        # start and finish." A brand-new game used to keep the four tools on the
        # squares they were built on, which left the deck empty and dealt a hand
        # of nothing: the tools go into the deck first now, and the opening hand
        # is a real draw.
        main.save_system.start_new_game_in_slot(self.game, 5)

        drawn = self.game.drawn_items()
        self.assertEqual(len(drawn), main.DECK_DRAW_SIZE)
        self.assertEqual(len([item for item in drawn
                              if self.game.item_cell(item) is not None]),
                         main.DECK_DRAW_SIZE)
        # The START and FINISH blocks are on the board AND not part of the draw.
        roles = [item for item in self.game.hand_items()
                 if getattr(item, "scorer", None) in (main.Scorer.START,
                                                     main.Scorer.FINISH)]
        self.assertEqual(len(roles), 2)
        self.assertFalse([item for item in drawn
                          if getattr(item, "scorer", None) in (main.Scorer.START,
                                                               main.Scorer.FINISH)])

    def test_every_run_opens_with_a_full_hand(self):
        # The end-of-run cycle hands everything back and deals a fresh hand of
        # DECK_DRAW_SIZE: what the player owns is split into exactly that many
        # items on the board and the rest waiting in the deck.
        self._own(12)
        playable = [item for item in self.game.owned_items()
                    if not self.game._stays_out_of_the_deck(item)]

        self.game._cycle_deck()

        self.assertEqual(len(self.game.drawn_items()), main.DECK_DRAW_SIZE)
        self.assertEqual(len(self.game.deck_items()),
                         len(playable) - main.DECK_DRAW_SIZE)

    def test_a_new_game_has_the_two_role_blocks_on_the_board_and_an_empty_deck(self):
        # The Start and Finish blocks are what a run is built around, so they are
        # never dealt: they live on the board, outside the deck (user request).
        self.game.ensure_board_cells()
        scorers = sorted(
            item.scorer for item in self.game.hand_items()
            if getattr(item, "kind", None) == "block"
            and item.scorer in (main.Scorer.START, main.Scorer.FINISH))
        self.assertEqual(scorers, sorted([main.Scorer.START, main.Scorer.FINISH]))
        self.assertEqual(self.game.deck_items(), [])

    def test_buying_a_shop_item_unlocks_it_in_place_and_deletes_the_offer(self):
        self._stock_shelf(2, 1)  # a pack is on sale
        # "Buying anything in the shop unlocks it and deletes the locked shop
        # item ... it should become unlocked, stay in the same place on the board
        # as where it was bought, and no locked ... shop item should exist
        # anymore" (user request). A structure needs no buying (it is free), so
        # the thing on sale here is a PACK.
        self.game.cash = 100000
        self.game.ensure_board_cells()   # the offers are laid out on the board
        offer = next(o for o in self.game.shop.items
                     if getattr(o, "kind", None) == "pack")
        home = self.game.item_cell(offer)
        self.assertIsNotNone(home)

        self.game._buy_shop_item(offer)

        # The very tile the player clicked is now theirs: same square, unlocked.
        self.assertTrue(self.game.owns_item(offer))
        self.assertEqual(self.game.item_cell(offer), home)
        self.assertIn(offer, self.game.hand_items())
        # ...and no locked copy of it is left anywhere.
        self.assertNotIn(offer, self.game.shop.items)
        self.assertIsNone(self.game.shop.offer_at_cell(home))

        # A second, separate offer of the same kind is a second item, with a
        # square of its own.
        second = self.game.shop._roll_pack(offer.pack_type, main.Pack.SIZE_ORDER[0])
        self.game.shop.items = [second]
        self.game._buy_shop_item(second)
        self.assertTrue(self.game.owns_item(second))
        self.assertIsNot(second, offer)
        self.assertNotEqual(self.game.item_cell(second), home)

    def test_the_start_and_finish_blocks_stay_out_of_the_deck(self):
        # Even when everything else is in the deck, the role blocks are on the
        # board: a run can always begin. The TOOLS are items like any other (user
        # request: "shovel, flashlight, screwdriver, hammer all count as items"),
        # so they go into the deck with everything else.
        self._own(6)
        for item in list(self.game.owned_items()):
            if self.game._stays_out_of_the_deck(item):
                continue
            self.game._to_deck(item)

        stuck = [item for item in self.game.hand_items()
                 if self.game._stays_out_of_the_deck(item)]
        self.assertEqual(len(stuck), 2)   # the 2 role blocks
        self.assertEqual(len(self.game.deck_items()), 10)   # 6 owned + 4 tools

    def test_the_end_of_a_run_returns_everything_and_draws_four(self):
        # "When the run ends, all items owned by the player (except the start and
        # finish) are returned to the deck and 4 new random items are drawn." The
        # four TOOLS go back in too, and the draw may deal one of them.
        items = self._own(8)
        self.game.cash = 100000
        owned = len(self.game.owned_items())

        self.game._cycle_deck()

        self.assertEqual(len(self.game.owned_items()), owned)   # nothing lost
        hand = self.game.hand_items()
        # + the two role blocks, which never leave the board.
        self.assertEqual(len(hand), main.DECK_DRAW_SIZE + 2)
        roles = [item for item in hand
                 if getattr(item, "scorer", None) in (main.Scorer.START,
                                                      main.Scorer.FINISH)]
        self.assertEqual(len(roles), 2)
        drawn = [item for item in hand if item not in roles]
        self.assertEqual(len(drawn), main.DECK_DRAW_SIZE)
        self.assertEqual(sorted(self.game.drawn_items(), key=id),
                         sorted(drawn, key=id))
        # Every drawn item had a board square dealt to it, and the rest waited.
        for item in drawn:
            self.assertIn(item, items + [i for i in self.game.owned_items()
                                         if getattr(i, "kind", None) == "tool"])
            self.assertIsNotNone(self.game.item_cell(item))
        self.assertEqual(len(self.game.deck_items()),
                         owned - 2 - main.DECK_DRAW_SIZE)
        # No two items share a square.
        cells = [self.game.item_cell(item) for item in hand]
        self.assertEqual(len(cells), len(set(cells)))

    def test_a_placed_block_comes_off_the_board_when_the_run_is_continued(self):
        # "Everything comes off — placed blocks too — so each run is rebuilt from
        # the 4 drawn items" (user request), except the Start block the run needs.
        self.game.cash = 100000
        self._own(4)
        start = self._start_block_item()
        self.game._equip_block(start)
        self.game._place_block_at(3, 3)
        wall = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(wall)
        self.game._equip_block(wall)
        self.game._place_block_at(5, 5)
        self.assertIn((3, 3), self.game.grid)
        self.assertIn((5, 5), self.game.grid)

        self.game._cycle_deck()

        self.assertEqual([cell for cell, block in self.game.grid.items()
                          if getattr(block, "scorer", None) == main.Scorer.START],
                         [(3, 3)])
        self.assertEqual(len(self.game.grid), 1)        # the wall came off
        self.assertIn(wall, self.game.deck_items() + self.game.hand_items())

    def test_a_run_that_is_retried_keeps_its_hand(self):
        # A retry undoes the run, so the board it re-runs is the one the player
        # built: the deck is only cycled by CONTINUE.
        self._own(6)
        self.game._cycle_deck()
        hand_before = list(self.game.hand_items())
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(list(self.game.hand_items()), hand_before)

    def test_fewer_items_than_the_draw_size_deals_the_whole_deck(self):
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        self.game.toolbox.add(self._component())
        self.game.toolbox.add(self._component(main.Shape.SLOPE))

        self.game._cycle_deck()

        self.assertEqual(len(self.game.deck_items()), 0)

    def test_the_hand_and_the_deck_ride_through_a_save(self):
        self._own(6)
        self.game._cycle_deck()
        hand = sorted(self.game.item_cell(item) for item in self.game.hand_items())
        deck = len(self.game.deck_items())
        self.game.save_slot = 5
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 5)

        fresh.ensure_board_cells()
        self.assertEqual(sorted(fresh.item_cell(item)
                                for item in fresh.hand_items()), hand)
        self.assertEqual(len(fresh.deck_items()), deck)
        self.assertIsNotNone(save_system._save_data(fresh))

    def test_the_deck_button_shows_and_closes_the_overlay(self):
        # The button in the top bar is the way into the deck (user request: "add
        # a button in the top bar that shows the player's whole deck").
        self._own(5)
        self.game.cycle_note = ""
        self.assertFalse(self.game.deck_open())

        self._click(main.DECK_BUTTON_RECT.center)

        self.assertTrue(self.game.deck_open())
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            self.game.draw()          # the overlay draws over the play screen

        self._click((5, 5))           # any click closes it
        self.assertFalse(self.game.deck_open())

    def test_the_bar_button_counts_the_whole_deck(self):
        self._own(5)
        label = main.ui.deck_button_label(self.game)
        self.assertIn(str(len(self.game.owned_items())), label)
        self.assertIn(f"{len(self.game.drawn_items())} drawn", label)

    def test_only_four_items_are_drawn_from_the_deck_each_run(self):
        # "make sure that only 4 items are drawn from the player's deck each run"
        # (user request). The board also holds the two role blocks, the four
        # tools and whatever the run gained, so the DRAW is what the button
        # reports (see Game.drawn_items / ui.deck_button_label).
        self._own(10)
        for run in range(3):
            self.game._cycle_deck()
            drawn = self.game.drawn_items()
            self.assertEqual(len(drawn), main.DECK_DRAW_SIZE, run)
            # Everything else on the board is an item that never leaves it.
            for item in self.game.hand_items():
                if item not in drawn:
                    self.assertTrue(self.game._stays_out_of_the_deck(item), item)
            # No item is in two places at once: what was not drawn waits.
            self.assertEqual(
                len(drawn) + len(self.game.deck_items()),
                len([item for item in self.game.owned_items()
                     if not self.game._stays_out_of_the_deck(item)]))
        self.assertIn(f"{main.DECK_DRAW_SIZE} drawn",
                      main.ui.deck_button_label(self.game))

    def test_a_new_game_draws_four_of_its_starting_items(self):
        # The four TOOLS are items like any other (user request: "shovel,
        # flashlight, screwdriver, hammer all count as items, meaning they are
        # part of the condition that only 4 items can be drawn"), so a brand-new
        # game deals them through the same DECK_DRAW_SIZE draw a run uses.
        save_system.start_new_game_in_slot(self.game, 1)

        drawn = self.game.drawn_items()
        self.assertEqual(len(drawn), main.DECK_DRAW_SIZE)
        self.assertEqual(sorted(item.kind for item in drawn), ["tool"] * 4)
        # Only the two role blocks stand on the board without being drawn.
        leftovers = [item for item in self.game.hand_items()
                     if item not in drawn]
        self.assertEqual(sorted(item.scorer for item in leftovers),
                         sorted([main.Scorer.START, main.Scorer.FINISH]))

    def test_a_tool_goes_back_in_the_deck_at_the_end_of_a_run(self):
        # Tools are not always on the board any more: the run's draw is what
        # deals them, and the ones it does not deal wait in the deck.
        self._own(8)
        for _ in range(12):
            self.game._cycle_deck()
            self.assertLessEqual(len(self.game.drawn_items()), main.DECK_DRAW_SIZE)
            self.assertEqual(
                len(self.game.deck_items()),
                len(self.game.owned_items()) - 2 - len(self.game.drawn_items()))

    def test_a_short_deck_draws_only_what_it_has(self):
        # A deck with fewer items than the draw deals hands over fewer. (The
        # tools are in the deck now, so they are cleared out for this one.)
        for tool in [item for item in self.game.owned_items()
                     if getattr(item, "kind", None) == "tool"]:
            self.game.toolbox.remove(tool)
        self._own(2)
        for item in list(self.game.owned_items()):
            if not self.game._stays_out_of_the_deck(item):
                self.game._to_deck(item)
        self.assertEqual(len(self.game.deck_items()), 2)
        drawn = self.game.draw_deck_hand()
        self.assertEqual(len(drawn), 2)
        self.assertEqual(len(self.game.drawn_items()), 2)

    def test_the_overlay_lists_every_item_once(self):
        items = self._own(5)
        self.game.ensure_board_cells()
        drawn = self.game.hand_items()
        self.assertEqual(len(drawn) + len(self.game.deck_items()),
                         len(self.game.owned_items()))
        rects = [main.ui.deck_item_rect(i) for i in range(len(items) + 2)]
        self.assertEqual(len(rects), len(set(map(tuple, rects))))
