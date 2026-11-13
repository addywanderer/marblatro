"""Recycling: put the selected item back in the deck, and draw two for free.

User request: "add a card, 'recycling' (discard selected item, draw 2 items for 0
energy)".

The discard gives the item BACK: the answer the Horseshoe's discard gave ("back
into the deck — same as the Horseshoe's discard") is the rule, so nothing is
destroyed — the target becomes a deck item again and any later draw can deal it.
What pays for the card is the card itself (it is spent like every other action)
and nothing else: no energy, no lost item.
"""

from tests.game_test_case import *  # noqa: F401,F403


class RecyclingCatalogueTests(GameTestCase):
    """Its catalogue row, and the one number it carries."""

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.RECYCLING), "Recycling")
        self.assertIn(main.Action.RECYCLING, main.Action.ORDER)
        self.assertGreater(main.Action.PRICES[main.Action.RECYCLING], 0)
        self.assertIn(main.Action.RECYCLING, main.Action.GLYPHS)
        self.assertIn(main.Action.RECYCLING, main.Action.COLORS)
        self.assertTrue(main.Action.comment(main.Action.RECYCLING))
        self.assertEqual(main.Action.energy(main.Action.RECYCLING), 0)

    def test_it_is_aimed_at_one_item(self):
        # The card recycles something, so unlike the Horseshoe it is NOT a
        # target-free action: it takes exactly one item.
        self.assertTrue(main.Action.needs_target(main.Action.RECYCLING))
        self.assertNotIn(main.Action.RECYCLING, main.Action.NO_TARGET)
        self.assertNotIn(main.Action.RECYCLING, main.Action.STRUCTURE_TARGET)
        item = main.ActionItem(main.Action.RECYCLING,
                               main.Action.PRICES[main.Action.RECYCLING])
        self.assertEqual(self.game.required_targets(item), 1)

    def test_the_number_it_carries_is_the_draw(self):
        self.assertEqual(main.MAGNITUDES.RECYCLING_DRAWS, 2)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.RECYCLING],
                         main.MAGNITUDES.RECYCLING_DRAWS)
        item = main.ActionItem(main.Action.RECYCLING,
                               main.Action.PRICES[main.Action.RECYCLING])
        self.assertEqual(item.amount, 2)
        line = main.Action.description(main.Action.RECYCLING, 1)
        self.assertIn("draws 2 items", line)
        self.assertIn("0 energy", line)
        self.assertIn("deck", line)
        # A golem-folded one says what it would really draw.
        self.assertIn("draws 4 items",
                      main.Action.description(main.Action.RECYCLING, 1, 4))

    def test_the_codex_lists_it(self):
        self.game._unlock_entire_collection()
        entries = [entry for entry in self.game._collection_entries()
                   if entry[0] == "action" and entry[1] == main.Action.RECYCLING]
        self.assertEqual(len(entries), 1)
        _kind, _value, name, desc, has_icon, discovered = entries[0]
        self.assertEqual(name, "Recycling")
        self.assertTrue(desc)
        self.assertTrue(discovered)
        self.assertTrue(has_icon, "Recycling has no icon of its own")

    def test_the_sidebar_states_its_contract(self):
        item = main.ActionItem(main.Action.RECYCLING,
                               main.Action.PRICES[main.Action.RECYCLING])
        rows = dict(self.game._describe_item(item))
        self.assertIn("Needs 1 target", rows["Ability - Apply"])
        # 0 energy means the card costs nothing to use; what it spends of ITSELF
        # is its own keyword (see components.Keyword).
        self.assertIn("Costs nothing.", rows["Ability - Apply"])
        self.assertEqual(rows["Keywords"], "consume")
        self.assertIn("Magnitude", rows)


class RecyclingUseTests(GameTestCase):
    """What using it does: the item goes back, two come out."""

    def setUp(self):
        super().setUp()
        for value in (main.Card.JOKER, main.Card.PLANE, main.Card.BANKER,
                      main.Card.PILLAR, main.Card.COZY, main.Card.PAINTING):
            card = main.CardItem(value, main.Card.PRICES.get(value, 24))
            self.game.cards.append(card)
            self.game._to_deck(card)
        self.game.energy = main.MAX_ENERGY

    def _recycling(self, amount=None):
        item = (main.ActionItem(main.Action.RECYCLING,
                                main.Action.PRICES[main.Action.RECYCLING])
                if amount is None else
                main.ActionItem(main.Action.RECYCLING,
                                main.Action.PRICES[main.Action.RECYCLING],
                                amount=amount))
        self.game._adopt_action(item)
        return item

    def _use(self, action, subject=None):
        self.game.selection = [action] + ([subject] if subject is not None else [])
        self.game._refresh_actor()
        return self.game._apply_action()

    def _a_tool(self):
        return next(item for item in self.game.hand_items()
                    if getattr(item, "kind", None) == "tool")

    def _picked_from_the_top(self):
        """Draw from the END of the deck, so a test knows what came out.

        The deck is held in ownership order (the toolbox first, the cards last),
        so always taking the last drawable item takes CARDS — the recycled item,
        which stays in the toolbox, is never dealt straight back unless a test
        means to (see test_the_recycled_item_can_be_drawn_straight_back).
        """
        return mock.patch("main.random.choice", side_effect=lambda seq: seq[-1])

    def test_the_selected_item_goes_back_into_the_deck(self):
        action = self._recycling()
        tool = self._a_tool()

        with self._picked_from_the_top():
            self.assertTrue(self._use(action, tool))

        self.assertTrue(self.game.owns_item(tool), "the item was destroyed")
        self.assertIn(tool, self.game.deck_items())

    def test_it_draws_two_items(self):
        action = self._recycling()
        tool = self._a_tool()
        deck = list(self.game.deck_items())
        expected = deck[-2:]

        with self._picked_from_the_top():
            self.assertTrue(self._use(action, tool))

        for item in expected:
            self.assertIsNotNone(self.game.item_cell(item),
                                 f"{self.game._item_name(item)} was not drawn")
            self.assertIn(self.game._item_name(item), self.game.shop_message)
        self.assertIn("back in the deck", self.game.shop_message)

    def test_it_costs_no_energy(self):
        action = self._recycling()
        tool = self._a_tool()
        self.game.energy = 1

        self.assertTrue(self._use(action, tool))

        self.assertEqual(self.game.energy, 1, "Recycling charged energy")

    def test_it_is_spent_like_any_other_action(self):
        action = self._recycling()
        tool = self._a_tool()
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action, tool))

        self.assertFalse(self.game.owns_item(action))
        self.assertEqual(self.game.discarded_items_run, discarded + 1)
        self.assertIsNone(self.game.selected_action)

    def test_a_folded_one_draws_four(self):
        action = self._recycling(amount=4)
        tool = self._a_tool()
        before = len(self.game.hand_items())

        self.assertTrue(self._use(action, tool))

        # The card and the recycled tool leave the board; four come back.
        self.assertEqual(len(self.game.hand_items()), before - 2 + 4)

    def test_the_first_draw_takes_the_square_it_freed(self):
        action = self._recycling()
        tool = self._a_tool()
        cell = self.game.item_cell(tool)

        self.assertTrue(self._use(action, tool))

        self.assertIsNotNone(self.game.item_at_cell(cell),
                             "the square the recycled item gave up stayed empty")
        cells = [self.game.item_cell(item) for item in self.game.hand_items()]
        self.assertTrue(all(found is not None for found in cells))
        self.assertEqual(len(cells), len(set(cells)))

    def test_the_recycled_item_can_be_drawn_straight_back(self):
        # Nothing is destroyed, so the deck may deal it again at once: with one
        # card left in the deck, recycling a tool leaves exactly two drawable
        # items and the card draws both, the tool among them.
        for item in list(self.game.deck_items())[1:]:
            self.game._discard_item(item)
        action = self._recycling()
        tool = self._a_tool()
        before = len(self.game.hand_items())

        self.assertTrue(self._use(action, tool))

        self.assertTrue(self.game.owns_item(tool))
        self.assertIsNotNone(self.game.item_cell(tool), "the tool did not come back")
        # The card and the tool left the board, the two draws came back.
        self.assertEqual(len(self.game.hand_items()), before)

    def test_it_works_through_the_keys(self):
        action = self._recycling()
        tool = self._a_tool()
        before = len(self.game.hand_items())
        deck = list(self.game.deck_items())
        expected = deck[-2:]

        with self._picked_from_the_top():
            self._click(self._item_pos(action))
            self._click(self._item_pos(tool))
            self._press(main.pygame.K_s)

        self.assertFalse(self.game.owns_item(action))
        self.assertTrue(self.game.owns_item(tool))
        for item in expected:
            self.assertIsNotNone(self.game.item_cell(item))
        self.assertEqual(len(self.game.hand_items()), before)


class RecyclingTargetTests(GameTestCase):
    """What it can be aimed at, and what it refuses."""

    def setUp(self):
        super().setUp()
        for value in (main.Card.JOKER, main.Card.PLANE, main.Card.BANKER,
                      main.Card.PILLAR):
            card = main.CardItem(value, main.Card.PRICES.get(value, 24))
            self.game.cards.append(card)
            self.game._to_deck(card)
        self.game.energy = main.MAX_ENERGY

    def _recycling(self):
        item = main.ActionItem(main.Action.RECYCLING,
                               main.Action.PRICES[main.Action.RECYCLING])
        self.game._adopt_action(item)
        return item

    def _use(self, action, subject=None):
        self.game.selection = [action] + ([subject] if subject is not None else [])
        self.game._refresh_actor()
        return self.game._apply_action()

    def _a_card(self):
        return next(item for item in self.game.hand_items()
                    if getattr(item, "kind", None) == "card")

    def _picked_from_the_top(self):
        return mock.patch("main.random.choice", side_effect=lambda seq: seq[-1])

    def test_with_nothing_selected_nothing_happens(self):
        action = self._recycling()
        self.game.energy = 2

        self.assertFalse(self._use(action))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, 2)
        self.assertIn("0 selected", self.game.shop_message)

    def test_two_targets_are_refused(self):
        action = self._recycling()
        tools = [item for item in self.game.hand_items()
                 if getattr(item, "kind", None) == "tool"][:2]
        self.assertEqual(len(tools), 2)

        self.game.selection = [action] + tools
        self.game._refresh_actor()

        self.assertFalse(self.game._apply_action())
        self.assertTrue(self.game.owns_item(action))
        self.assertIn("2 selected", self.game.shop_message)

    def test_an_empty_deck_is_refused(self):
        action = self._recycling()
        for item in list(self.game.deck_items()):
            self.game._on_item_gained(item)
        self.assertEqual(self.game.deck_items(), [])
        card = self._a_card()

        self.assertFalse(self._use(action, card))

        self.assertTrue(self.game.owns_item(action), "the card was spent")
        self.assertIn("needs an item in the deck", self.game.shop_message)
        self.assertIsNotNone(self.game.item_cell(card))

    def test_an_unbought_offer_is_refused(self):
        # An offer on the shelf is not the player's item yet, so the card cannot
        # even be aimed at it: it is not a target at all.
        action = self._recycling()
        offer = main.CardItem(main.Card.STENCIL, 48)
        self.game.shop.items.append(offer)
        self.game.set_item_cell(offer, self.game._first_free_cell())

        self.assertFalse(self.game.is_action_target(offer, action))
        self.assertFalse(self._use(action, offer))

        self.assertTrue(self.game.owns_item(action))
        self.assertIn(offer, self.game.shop.items)
        self.assertIn("0 selected", self.game.shop_message)

    def test_a_placed_block_is_recycled_as_its_item(self):
        action = self._recycling()
        block_item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                    main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.toolbox.add(block_item)
        self.game.ensure_board_cells()
        cell = self.game.item_cell(block_item)
        self.game.selection = [block_item]
        self.game._refresh_actor()
        self.game._place_block_at(*cell)
        block = next(b for b in self.game.grid.values()
                     if getattr(b, "source_item", None) is block_item)

        with self._picked_from_the_top():
            self.assertTrue(self._use(action, block))

        self.assertIsNone(self.game.grid.get((cell[0], cell[1])),
                          "the block is still standing on the board")
        self.assertTrue(self.game.owns_item(block_item))
        self.assertIn(block_item, self.game.deck_items())

    def test_the_levels_own_blocks_are_refused(self):
        action = self._recycling()
        wall = main.Block(2, 7, shape=main.Shape.RECT)
        wall.is_level_prop = True
        self.game.grid[(2, 7)] = wall

        self.assertFalse(self._use(action, wall))

        self.assertIs(self.game.grid.get((2, 7)), wall)
        self.assertTrue(self.game.owns_item(action))
        self.assertIn("your own items", self.game.shop_message)

    def test_a_part_can_be_recycled(self):
        # A shape/effect/scorer piece is an item like any other: it goes back in
        # the deck and the draw takes its square.
        action = self._recycling()
        part = main.Component.shape_component(main.Shape.PIPE)
        self.game.toolbox.add(part)
        self.game._on_item_gained(part)
        cell = self.game.item_cell(part)

        with self._picked_from_the_top():
            self.assertTrue(self._use(action, part))

        self.assertIn(part, self.game.deck_items())
        self.assertIsNotNone(self.game.item_at_cell(cell))

    def test_a_spirit_token_is_not_an_item_to_recycle(self):
        # A token is live for its run rather than a card in the deck (see
        # _stays_out_of_the_deck), so it is not a target at all.
        action = self._recycling()
        token = _token(main.Scorer.CHIPS_ADD, runs_left=2)
        self.game.tokens.append(token)
        self.game._on_item_gained(token)

        self.assertFalse(self.game.is_action_target(token, action))
        self.assertFalse(self._use(action, token))

        self.assertTrue(self.game.owns_item(action))
        self.assertIsNotNone(self.game.item_cell(token))
        self.assertIn(token, self.game.tokens)
