"""Floor plans: draw five BLOCKS out of the deck, for one energy.

User request: "add a new card, 'floor plans' (draw 5 blocks. costs 1 energy)".

Unlike the Lantern, which draws any item, this one deals only the ready-made
blocks the deck is holding (see Game.deck_blocks) — what a run is built from —
and its number is its own magnitude, so a golem-folded one draws ten.
"""

from tests.game_test_case import *  # noqa: F401,F403


class FloorPlansCase(GameTestCase):
    """A live game with the card and a deck a test can stock."""

    def setUp(self):
        super().setUp()
        self.game.energy = main.MAX_ENERGY

    def _floor_plans(self, amount=None):
        item = (main.ActionItem(main.Action.FLOOR_PLANS,
                                main.Action.PRICES[main.Action.FLOOR_PLANS])
                if amount is None else
                main.ActionItem(main.Action.FLOOR_PLANS,
                                main.Action.PRICES[main.Action.FLOOR_PLANS],
                                amount=amount))
        self.game._adopt_action(item)
        return item

    def _block(self, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
               amount=10, name="Rect +Chips"):
        """A loose block waiting in the DECK (see _to_deck)."""
        item = main.BlockItem(0, 0, shape, main.Effect.NONE, scorer, amount,
                              20, name)
        self.game.toolbox.add(item)
        self.game._to_deck(item)
        return item

    def _card(self, value=main.Card.JOKER):
        item = main.CardItem(value, main.Card.PRICES.get(value, 24))
        self.game.cards.append(item)
        self.game._to_deck(item)
        return item

    def _use(self, action):
        self.game.selection = [action]
        self.game._refresh_actor()
        return self.game._apply_action()

    def _drawn(self, items):
        return [item for item in items
                if self.game.item_cell(item) is not None]


class FloorPlansCatalogueTests(FloorPlansCase):
    """Its catalogue row, and the one number it carries."""

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.FLOOR_PLANS),
                         "Floor plans")
        self.assertIn(main.Action.FLOOR_PLANS, main.Action.ORDER)
        self.assertGreater(main.Action.PRICES[main.Action.FLOOR_PLANS], 0)
        self.assertIn(main.Action.FLOOR_PLANS, main.Action.GLYPHS)
        self.assertIn(main.Action.FLOOR_PLANS, main.Action.COLORS)
        self.assertTrue(main.Action.comment(main.Action.FLOOR_PLANS))
        # User request: "costs 1 energy".
        self.assertEqual(main.Action.energy(main.Action.FLOOR_PLANS), 1)

    def test_it_needs_no_target(self):
        # It reaches into the deck, not at a piece: S uses it as soon as it is
        # selected.
        self.assertFalse(main.Action.needs_target(main.Action.FLOOR_PLANS))
        self.assertIn(main.Action.FLOOR_PLANS, main.Action.NO_TARGET)
        self.assertFalse(main.Action.targets_structures(
            main.Action.FLOOR_PLANS))
        action = self._floor_plans()
        self.assertEqual(self.game.required_targets(action), 0)

    def test_the_number_it_carries_is_the_blocks(self):
        self.assertEqual(main.MAGNITUDES.FLOOR_PLANS_BLOCKS, 5)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.FLOOR_PLANS],
                         main.MAGNITUDES.FLOOR_PLANS_BLOCKS)
        item = self._floor_plans()
        self.assertEqual(item.amount, 5)
        line = main.Action.description(main.Action.FLOOR_PLANS, 1)
        self.assertIn("5 blocks", line)
        self.assertIn("1 energy", line)
        self.assertIn("deck", line)
        # A golem-folded one says what it would really draw.
        self.assertIn("10 blocks",
                      main.Action.description(main.Action.FLOOR_PLANS, 1, 10))

    def test_the_codex_lists_it(self):
        self.game._unlock_entire_collection()
        entries = [entry for entry in self.game._collection_entries()
                   if entry[0] == "action"
                   and entry[1] == main.Action.FLOOR_PLANS]
        self.assertEqual(len(entries), 1)
        _kind, _value, name, desc, has_icon, discovered = entries[0]
        self.assertEqual(name, "Floor plans")
        self.assertTrue(desc)
        self.assertTrue(discovered)
        self.assertTrue(has_icon, "Floor plans has no icon of its own")

    def test_the_sidebar_states_its_contract(self):
        rows = dict(self.game._describe_item(self._floor_plans()))
        self.assertIn("Needs 0 targets", rows["Ability - Apply"])
        self.assertIn("1 energy", rows["Ability - Apply"])
        self.assertIn("Magnitude", rows)


class FloorPlansUseTests(FloorPlansCase):
    """What it deals, out of what it is allowed to deal."""

    def test_it_draws_five_blocks(self):
        blocks = [self._block(name=f"Block {index}") for index in range(5)]
        action = self._floor_plans()

        self.assertTrue(self._use(action))

        self.assertEqual(len(self._drawn(blocks)), 5,
                         "five blocks should have come out of the deck")
        self.assertIn("drew 5 blocks", self.game.shop_message)

    def test_it_draws_blocks_and_nothing_else(self):
        # The deck holds cards too: the draw must leave every one of them alone.
        blocks = [self._block(name=f"Block {index}") for index in range(5)]
        cards = [self._card(value) for value in (main.Card.JOKER,
                                                main.Card.PLANE,
                                                main.Card.BANKER)]
        action = self._floor_plans()

        self.assertTrue(self._use(action))

        self.assertEqual(len(self._drawn(blocks)), 5)
        for card in cards:
            self.assertIsNone(self.game.item_cell(card),
                              "a card was drawn by a block draw")
            self.assertIn(card, self.game.deck_items())
        for item in self.game.hand_items():
            self.assertNotIn(item, cards)

    def test_it_draws_fewer_when_the_deck_has_fewer(self):
        blocks = [self._block(name=f"Block {index}") for index in range(3)]
        action = self._floor_plans()

        self.assertTrue(self._use(action))

        self.assertEqual(len(self._drawn(blocks)), 3)
        self.assertIn("drew 3 blocks", self.game.shop_message)
        self.assertIn("no more blocks", self.game.shop_message)

    def test_a_deck_with_no_block_is_refused(self):
        self._card(main.Card.JOKER)
        action = self._floor_plans()
        self.game.energy = 2
        discarded = self.game.discarded_items_run

        self.assertFalse(self._use(action))

        self.assertTrue(self.game.owns_item(action), "the card was spent")
        self.assertEqual(self.game.energy, 2, "a refusal cost energy")
        self.assertEqual(self.game.discarded_items_run, discarded)
        self.assertIn("needs a block in the deck", self.game.shop_message)

    def test_out_of_energy_it_is_kept(self):
        blocks = [self._block()]
        action = self._floor_plans()
        self.game.energy = 0

        self.assertFalse(self._use(action))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, 0)
        self.assertEqual(self._drawn(blocks), [])

    def test_it_costs_one_energy_and_is_spent(self):
        for index in range(2):
            self._block(name=f"Block {index}")
        action = self._floor_plans()
        self.game.energy = 3
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action))

        self.assertEqual(self.game.energy, 2)
        self.assertFalse(self.game.owns_item(action))
        self.assertEqual(self.game.discarded_items_run, discarded + 1)

    def test_a_folded_one_draws_ten(self):
        blocks = [self._block(name=f"Block {index}") for index in range(12)]
        action = self._floor_plans(amount=10)

        self.assertTrue(self._use(action))

        self.assertEqual(len(self._drawn(blocks)), 10)

    def test_every_drawn_block_gets_its_own_square(self):
        blocks = [self._block(name=f"Block {index}") for index in range(5)]
        action = self._floor_plans()

        self.assertTrue(self._use(action))

        cells = [self.game.item_cell(item) for item in self._drawn(blocks)]
        self.assertEqual(len(cells), 5)
        self.assertEqual(len(cells), len(set(cells)),
                         "two blocks were dealt the same square")
        for cell in cells:
            self.assertIn(cell, self.game.unlocked_cells)

    def test_it_works_through_the_keys(self):
        blocks = [self._block(name=f"Block {index}") for index in range(5)]
        action = self._floor_plans()

        self._click(self._item_pos(action))
        self._press(main.pygame.K_s)

        self.assertFalse(self.game.owns_item(action))
        self.assertEqual(len(self._drawn(blocks)), 5)
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)

    def test_a_forgotten_block_cannot_be_drawn(self):
        # The Forgotten modifier means "cannot be drawn" (see
        # drawable_deck_items), and a block draw obeys it like any other.
        blocked = self._block(name="Forgotten")
        main.Modifier.add(blocked, main.Modifier.FORGOTTEN, 1)
        open_block = self._block(name="Open")
        action = self._floor_plans()

        self.assertTrue(self._use(action))

        self.assertIsNone(self.game.item_cell(blocked))
        self.assertIsNotNone(self.game.item_cell(open_block))

    def test_it_works_from_a_pack(self):
        # An action pack's actions are USED rather than shelved, and this one
        # needs no target, so keeping it fires it (see _keep_action_from_pack).
        blocks = [self._block(name=f"Block {index}") for index in range(5)]
        action = main.ActionItem(main.Action.FLOOR_PLANS,
                                 main.Action.PRICES[main.Action.FLOOR_PLANS])

        _kept, message = self.game._keep_action_from_pack(action)

        self.assertIn("Used action", message)
        self.assertEqual(len(self._drawn(blocks)), 5)
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)
