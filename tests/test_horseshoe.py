"""The Horseshoe: throw the hand back into the deck and draw a bigger one.

User request: "add a card: 'horseshoe' (discard all items on the board that you
own, draw the same number plus 3 new items. costs 1 energy)".

A DISCARD is not a destruction here: the answer Smelly Socks' discard gave ("the
card goes back into the deck and is not destroyed. The player could draw it
again using cards that draw more cards") is the rule the whole game follows, so
the Horseshoe is a mulligan with a bonus — everything the player owns on the
board goes back into the DECK, and the card then deals a hand that many items
bigger (see Game._action_horseshoe / Game._sweep_board_into_deck).
"""

from tests.game_test_case import *  # noqa: F401,F403


class HorseshoeCatalogueTests(GameTestCase):
    """Its row in the catalogue, and the one number it carries."""

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.HORSESHOE), "Horseshoe")
        self.assertIn(main.Action.HORSESHOE, main.Action.ORDER)
        self.assertGreater(main.Action.PRICES[main.Action.HORSESHOE], 0)
        self.assertIn(main.Action.HORSESHOE, main.Action.GLYPHS)
        self.assertIn(main.Action.HORSESHOE, main.Action.COLORS)
        self.assertTrue(main.Action.comment(main.Action.HORSESHOE))
        # It acts on the hand, not on a piece, so S uses it as soon as it is
        # selected (user request: "costs 1 energy").
        self.assertFalse(main.Action.needs_target(main.Action.HORSESHOE))
        self.assertEqual(main.Action.energy(main.Action.HORSESHOE), 1)

    def test_the_number_it_carries_is_the_extra_items(self):
        # "+3 new items": the 3 lives in MAGNITUDES, once, and the catalogue
        # line is generated from it, so a golem-folded one reads its own total.
        self.assertEqual(main.MAGNITUDES.HORSESHOE_EXTRA_DRAWS, 3)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.HORSESHOE],
                         main.MAGNITUDES.HORSESHOE_EXTRA_DRAWS)
        item = main.ActionItem(main.Action.HORSESHOE,
                               main.Action.PRICES[main.Action.HORSESHOE])
        self.assertEqual(item.amount, 3)
        line = main.Action.description(main.Action.HORSESHOE, 1)
        self.assertIn("plus 3", line)
        self.assertIn("1 energy", line)
        self.assertIn("deck", line)
        # A golem-folded one says what it would really draw.
        self.assertIn("plus 5", main.Action.description(main.Action.HORSESHOE, 1, 5))

    def test_the_codex_lists_it(self):
        self.game._unlock_entire_collection()
        entries = [entry for entry in self.game._collection_entries()
                   if entry[0] == "action" and entry[1] == main.Action.HORSESHOE]
        self.assertEqual(len(entries), 1)
        _kind, _value, name, desc, has_icon, discovered = entries[0]
        self.assertEqual(name, "Horseshoe")
        self.assertTrue(desc)
        self.assertIn("deck", desc)
        self.assertTrue(discovered)
        self.assertTrue(has_icon, "the Horseshoe has no icon of its own")


class HorseshoeDiscardTests(GameTestCase):
    """What "discard all items on the board that you own" means."""

    def setUp(self):
        super().setUp()
        # A fresh game deals the four tools as its opening hand and leaves the
        # deck empty, so every test fills the deck: a draw off an empty deck
        # would only deal the hand straight back.
        for value in (main.Card.JOKER, main.Card.PLANE, main.Card.BANKER,
                      main.Card.PILLAR, main.Card.COZY, main.Card.PAINTING,
                      main.Card.SYNTHESIZER, main.Card.ISLAND):
            card = main.CardItem(value, main.Card.PRICES.get(value, 24))
            self.game.cards.append(card)
            self.game._to_deck(card)

    def _horseshoe(self, amount=None):
        item = (main.ActionItem(main.Action.HORSESHOE, 36) if amount is None
                else main.ActionItem(main.Action.HORSESHOE, 36, amount=amount))
        self.game._adopt_action(item)
        return item

    def _use(self, action):
        self.game.selection = [action]
        self.game._refresh_actor()
        return self.game._apply_action()

    def _hand_without_roles(self):
        return [item for item in self.game.hand_items()
                if not self.game._stays_out_of_the_deck(item)]

    def test_the_hand_goes_back_into_the_deck(self):
        # The discard itself, without the draw on top: everything the player
        # owned on the board is still theirs, in the deck, and off the board.
        shoe = self._horseshoe()
        hand = [item for item in self._hand_without_roles() if item is not shoe]
        self.assertTrue(hand)
        deck_before = len(self.game.deck_items())

        moved = self.game._sweep_board_into_deck(keep=shoe)

        self.assertCountEqual(moved, hand)
        for item in hand:
            self.assertTrue(self.game.owns_item(item), "an item was destroyed")
            self.assertIsNone(self.game.item_cell(item))
            self.assertIn(item, self.game.deck_items())
        self.assertEqual(len(self.game.deck_items()), deck_before + len(hand))
        self.assertIsNotNone(self.game.item_cell(shoe), "the card left its square")

    def test_it_draws_the_hand_it_threw_back_plus_three(self):
        shoe = self._horseshoe()
        thrown = len([item for item in self._hand_without_roles()
                      if item is not shoe])
        deck_before = len(self.game.deck_items())

        self.assertTrue(self._use(shoe))

        drawn = thrown + main.MAGNITUDES.HORSESHOE_EXTRA_DRAWS
        # START and FINISH never leave the board, so the hand is those two plus
        # everything this card dealt.
        self.assertEqual(len(self.game.hand_items()), 2 + drawn)
        self.assertEqual(len(self.game.deck_items()), deck_before + thrown - drawn)
        self.assertIn(f"threw {thrown} items back", self.game.shop_message)
        self.assertIn(f"drew {drawn}", self.game.shop_message)

    def test_a_folded_one_draws_two_more(self):
        thrown = len(self._hand_without_roles())
        shoe = self._horseshoe(amount=5)

        self.assertTrue(self._use(shoe))

        self.assertEqual(len(self.game.hand_items()), 2 + thrown + 5)

    def test_only_the_card_itself_leaves_the_game(self):
        shoe = self._horseshoe()
        owned_before = len(self.game.owned_items())

        self.assertTrue(self._use(shoe))

        self.assertEqual(len(self.game.owned_items()), owned_before - 1)
        self.assertFalse(self.game.owns_item(shoe))

    def test_the_start_and_finish_blocks_stay_where_they_are(self):
        roles = [item for item in self.game.hand_items()
                 if self.game._stays_out_of_the_deck(item)]
        self.assertTrue(roles)
        cells = [self.game.item_cell(item) for item in roles]
        # ...including the blocks a run is built from, standing on the board.
        blocks = [main.Block(1, 1, scorer=main.Scorer.START),
                  main.Block(4, 1, scorer=main.Scorer.FINISH)]
        for block in blocks:
            self.game.grid[(block.x, block.y)] = block

        self._use(self._horseshoe())

        self.assertEqual([self.game.item_cell(item) for item in roles], cells)
        for block in blocks:
            self.assertIs(self.game.grid.get((block.x, block.y)), block)

    def test_a_spirit_token_stays_for_its_run(self):
        token = _token(main.Scorer.CHIPS_ADD, runs_left=3)
        self.game.tokens.append(token)
        self.game._on_item_gained(token)
        cell = self.game.item_cell(token)
        self.assertIsNotNone(cell)

        self._use(self._horseshoe())

        self.assertIn(token, self.game.tokens)
        self.assertEqual(self.game.item_cell(token), cell)

    def _placed_block(self):
        block_item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                    main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.toolbox.add(block_item)
        self.game.ensure_board_cells()
        cell = self.game.item_cell(block_item)
        self.game.selection = [block_item]
        self.game._refresh_actor()
        self.game._place_block_at(*cell)
        return block_item

    def test_a_placed_block_comes_off_the_board_with_its_item(self):
        block_item = self._placed_block()
        block = next(block for block in self.game.grid.values()
                     if getattr(block, "source_item", None) is block_item)

        self._use(self._horseshoe())

        self.assertIsNone(self.game.grid.get((block.x, block.y)),
                          "the block is still standing on the board")
        self.assertTrue(self.game.owns_item(block_item))
        self.assertIsNone(block_item.placed_cell)

    def test_the_sweep_puts_a_placed_blocks_item_in_the_deck(self):
        # The same rule on its own, so the check does not depend on where the
        # draw happened to deal the item afterwards.
        block_item = self._placed_block()

        moved = self.game._sweep_board_into_deck()

        self.assertIn(block_item, moved)
        self.assertIsNone(self.game.item_cell(block_item))
        self.assertIn(block_item, self.game.deck_items())

    def test_the_level_keeps_its_own_blocks(self):
        # "items that you own": the level's furniture and its enemies are not
        # the player's, so the horseshoe leaves them standing.
        wall = main.Block(2, 7, shape=main.Shape.RECT)
        wall.is_level_prop = True
        self.game.grid[(2, 7)] = wall
        foe = main.Block(6, 7, shape=main.Shape.RECT)
        foe.is_enemy = True
        self.game.grid[(6, 7)] = foe

        self._use(self._horseshoe())

        self.assertIs(self.game.grid.get((2, 7)), wall)
        self.assertIs(self.game.grid.get((6, 7)), foe)
        self.assertEqual(self.game.toolbox.stash, [])

    def test_the_card_itself_is_discarded(self):
        shoe = self._horseshoe()
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(shoe))

        self.assertFalse(self.game.owns_item(shoe), "the card was not spent")
        self.assertEqual(self.game.discarded_items_run, discarded + 1)

    def test_a_reusable_horseshoe_is_used_not_spent(self):
        shoe = self._horseshoe()
        main.Modifier.add(shoe, main.Modifier.REUSABLE, 1)
        cell = self.game.item_cell(shoe)
        self.game.energy = 3

        self.assertTrue(self._use(shoe))

        self.assertTrue(self.game.owns_item(shoe), "a reusable card was spent")
        self.assertEqual(self.game.item_cell(shoe), cell,
                         "the reusable card moved off its own square")
        self.assertEqual(self.game.energy, 2, "it is still paid for")


class HorseshoeDrawTests(GameTestCase):
    """The draw itself, its limits, and what it refuses."""

    def _horseshoe(self):
        item = main.ActionItem(main.Action.HORSESHOE, 36)
        self.game._adopt_action(item)
        return item

    def _use(self, action):
        self.game.selection = [action]
        self.game._refresh_actor()
        return self.game._apply_action()

    def _deck_card(self, value=main.Card.JOKER):
        card = main.CardItem(value, main.Card.PRICES.get(value, 24))
        self.game.cards.append(card)
        self.game._to_deck(card)
        return card

    def _empty_hand(self, destroy=False):
        for item in list(self.game.hand_items()):
            if self.game._stays_out_of_the_deck(item):
                continue
            if destroy:
                self.game._discard_item(item)
            else:
                self.game._to_deck(item)

    def test_it_costs_one_energy(self):
        shoe = self._horseshoe()
        self.game.energy = 3

        self.assertTrue(self._use(shoe))

        self.assertEqual(self.game.energy, 2)

    def test_out_of_energy_it_is_kept(self):
        shoe = self._horseshoe()
        self.game.energy = 0
        before = len(self.game.hand_items())

        self.assertFalse(self._use(shoe))

        self.assertTrue(self.game.owns_item(shoe))
        self.assertEqual(self.game.energy, 0)
        self.assertEqual(len(self.game.hand_items()), before)
        self.assertIn("Out of energy", self.game.shop_message)

    def test_it_stops_when_the_deck_runs_out(self):
        # Four tools on the board and nothing else in the deck: the hand goes
        # back in, so the draw can only deal what is there — seven asked for,
        # four dealt.
        shoe = self._horseshoe()

        self.assertTrue(self._use(shoe))

        self.assertEqual(len(self.game.deck_items()), 0)
        self.assertIn("the deck ran out", self.game.shop_message)

    def test_an_empty_board_still_draws_three(self):
        for _ in range(5):
            self._deck_card()
        self._empty_hand()
        shoe = self._horseshoe()

        self.assertTrue(self._use(shoe))

        # The two role blocks, plus the card's own three.
        self.assertEqual(len(self.game.hand_items()),
                         2 + main.MAGNITUDES.HORSESHOE_EXTRA_DRAWS)

    def test_nothing_anywhere_is_refused(self):
        self._empty_hand(destroy=True)
        shoe = self._horseshoe()
        self.game.energy = 3
        discarded = self.game.discarded_items_run

        self.assertFalse(self._use(shoe))

        self.assertTrue(self.game.owns_item(shoe), "the card was spent")
        self.assertEqual(self.game.energy, 3, "a refusal cost energy")
        self.assertEqual(self.game.discarded_items_run, discarded)
        self.assertIn("needs an item", self.game.shop_message)

    def test_a_selected_target_is_refused(self):
        # It takes no target: another item switched on with it would be one.
        shoe = self._horseshoe()
        card = self._deck_card(main.Card.PLANE)
        self.game._on_item_gained(card)
        self.game.energy = 3
        self.game.selection = [shoe, card]
        self.game._refresh_actor()

        self.assertFalse(self.game._apply_action())

        self.assertTrue(self.game.owns_item(shoe))
        self.assertEqual(self.game.energy, 3)
        self.assertIn("1 selected", self.game.shop_message)
        self.assertIsNotNone(self.game.item_cell(card))

    def test_every_drawn_item_gets_its_own_square(self):
        for _ in range(6):
            self._deck_card(main.Card.PLANE)
        shoe = self._horseshoe()
        self.game.energy = 3

        self.assertTrue(self._use(shoe))

        cells = [self.game.item_cell(item) for item in self.game.hand_items()]
        self.assertTrue(all(cell is not None for cell in cells))
        self.assertEqual(len(cells), len(set(cells)),
                         "two items were dealt the same square")
        for cell in cells:
            self.assertIn(cell, self.game.unlocked_cells)

    def test_it_works_through_the_keys(self):
        for _ in range(6):
            self._deck_card(main.Card.PLANE)
        shoe = self._horseshoe()
        self.game.energy = 3
        before = len(self.game.hand_items())

        self._click(self._item_pos(shoe))
        self._press(main.pygame.K_s)

        self.assertFalse(self.game.owns_item(shoe))
        self.assertEqual(self.game.energy, 2)
        # The hand it threw back came back with the three new items on top,
        # less the card that was spent.
        self.assertEqual(len(self.game.hand_items()), before - 1 + 3)

    def test_a_pack_uses_it_at_once(self):
        # An action pack's actions are USED rather than shelved, and this one
        # needs no target, so keeping it fires it (see _keep_action_from_pack).
        for _ in range(6):
            self._deck_card(main.Card.PLANE)
        shoe = main.ActionItem(main.Action.HORSESHOE, 36)
        self.game.energy = 3
        before = len(self.game.hand_items())

        _kept, message = self.game._keep_action_from_pack(shoe)

        self.assertIn("Used action", message)
        self.assertEqual(self.game.energy, 2)
        self.assertIsNone(self.game.pending_pack_action)
        self.assertGreater(len(self.game.hand_items()), before)
