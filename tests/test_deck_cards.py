"""The four newest cards: Eyeball, Deep Pockets, Nasty Cocktail and Smelly Socks.

User request: "add a card, 'eyeball': pick a card from your deck to draw (1
energy). add a card, 'deep pockets': create a random pack, destroy a random
structure (1 energy). add a card, 'nasty cocktail': gain 1 energy for each
unique modifier on this card (0 energy). add a card, 'smelly socks': +15 chips
and +2 mult at start of run, but discard a random card when you draw this card
(unplayable)."

Three of them are ACTIONS — they cost the run's energy and are spent when they
fire — and one is a whole CARD, which pays every run and is unplayable. These
tests pin down each catalogue row, what the card does when it is used, and what
it refuses to do.

The discard Smelly Socks charges is NOT a destruction (user's answer: "the card
goes back into the deck and is not destroyed. The player could draw it again
using cards that draw more cards"), so the deck is where a discarded card goes.
"""

from tests.game_test_case import *  # noqa: F401,F403


class EyeballTests(GameTestCase):
    """Eyeball: 1 energy, and the player picks the cards they draw."""

    def _eyeball(self, amount=None):
        item = (main.ActionItem(main.Action.EYEBALL, 28) if amount is None
                else main.ActionItem(main.Action.EYEBALL, 28, amount=amount))
        self.game._adopt_action(item)
        return item

    def _deck_card(self, value=main.Card.JOKER):
        card = main.CardItem(value, main.Card.PRICES.get(value, 24))
        self.game.cards.append(card)
        self.game._to_deck(card)
        return card

    def _tile_of(self, item):
        """The deck overlay's rect for ``item`` (it must be on the overlay)."""
        self.game.ensure_board_cells()
        items = self.game.deck_overlay_items()
        return main.ui.deck_item_rect(items.index(item))

    def _use(self, action):
        self.game.selected_action = action
        return self.game._apply_action()

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.EYEBALL), "Eyeball")
        self.assertEqual(main.Action.energy(main.Action.EYEBALL), 1)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.EYEBALL], 1)
        self.assertGreater(main.Action.PRICES[main.Action.EYEBALL], 0)
        self.assertIn(main.Action.EYEBALL, main.Action.ORDER)
        self.assertFalse(main.Action.needs_target(main.Action.EYEBALL))
        # Its line states both numbers it carries, from the one place they live.
        line = main.Action.description(main.Action.EYEBALL, 1)
        self.assertIn("1 card", line)
        self.assertIn("1 energy", line)
        # ...and a golem-folded one reads the cards it would really draw.
        self.assertIn("2 cards", main.Action.description(main.Action.EYEBALL, 1, 2))

    def test_using_it_opens_the_deck_as_a_picker(self):
        action = self._eyeball()
        card = self._deck_card()
        self.game.energy = 3

        self.assertTrue(self._use(action))

        self.assertTrue(self.game.deck_open(), "the deck overlay was not opened")
        self.assertTrue(self.game.deck_pick_armed())
        self.assertEqual(self.game.deck_pick_left, 1)
        self.assertIn(action, self.game.actions, "the action was spent too early")
        self.assertEqual(self.game.energy, 3, "the energy was spent too early")
        self.assertIsNone(self.game.item_cell(card), "the card was drawn by itself")

    def test_the_card_you_click_is_the_one_that_is_drawn(self):
        action = self._eyeball()
        card = self._deck_card(main.Card.JOKER)
        other = self._deck_card(main.Card.PLANE)
        self.game.energy = 3

        self._use(action)
        self.game._click_deck_pick(self._tile_of(card).center)

        self.assertIsNotNone(self.game.item_cell(card), "the card was not drawn")
        self.assertIsNone(self.game.item_cell(other), "another card was drawn")
        self.assertNotIn(action, self.game.actions, "the action was not spent")
        self.assertEqual(self.game.energy, 2)
        self.assertFalse(self.game.deck_open())

    def test_it_can_be_used_with_the_keys_and_the_mouse(self):
        # The whole use through the real input path: select the action, press S,
        # click the card in the overlay.
        action = self._eyeball()
        card = self._deck_card(main.Card.BANKER)
        self.game.energy = 3

        self._click(self._item_pos(action))
        self._press(main.pygame.K_s)
        self.assertTrue(self.game.deck_open())
        self.assertTrue(self.game.deck_pick_armed())

        self._click(self._tile_of(card).center)

        self.assertIsNotNone(self.game.item_cell(card))
        self.assertNotIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 2)

    def test_looking_is_free(self):
        # Esc (or a click off the tiles) keeps both the action and the energy:
        # nothing is spent until a card is actually drawn.
        action = self._eyeball()
        self._deck_card()
        self.game.energy = 3

        self._use(action)
        self.game.cancel_deck_pick()

        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 3)
        self.assertFalse(self.game.deck_open())
        self.assertFalse(self.game.deck_pick_armed())

    def test_esc_keeps_the_card_through_the_keys(self):
        action = self._eyeball()
        self._deck_card()
        self.game.energy = 3
        self._click(self._item_pos(action))
        self._press(main.pygame.K_s)
        self.assertTrue(self.game.deck_pick_armed())

        self._press(main.pygame.K_ESCAPE)

        self.assertFalse(self.game.deck_open())
        self.assertFalse(self.game.deck_pick_armed())
        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 3)

    def test_a_run_start_drops_a_stale_pick(self):
        # The pick is a look, not a spent action: a run that starts clears it so
        # no overlay or armed pick survives into the next run.
        action = self._eyeball()
        self._deck_card()
        self.game.energy = 3
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self._use(action)

        self.assertTrue(self.game.reset_run())

        self.assertFalse(self.game.deck_pick_armed())
        self.assertFalse(self.game.deck_open())
        self.assertIn(action, self.game.actions)

    def test_the_sidebar_states_the_energy_it_costs(self):
        action = self._eyeball()

        rows = dict(self.game._describe_item(action))

        self.assertIn("1 energy", rows["Ability - Apply"])
        self.assertIn("1 energy", rows["Card - Eyeball"])
        self.assertEqual(rows["Keywords"], "consume")
        self.assertEqual(self.game._action_hint(action, "board"),
                         "Press S to pick a card in your deck to draw "
                         "(1 energy)")

    def test_it_needs_energy(self):
        action = self._eyeball()
        self._deck_card()
        self.game.energy = 0

        self.assertFalse(self._use(action))

        self.assertFalse(self.game.deck_pick_armed())
        self.assertIn(action, self.game.actions)
        self.assertIn("energy", self.game.shop_message.lower())

    def test_it_needs_a_card_in_the_deck(self):
        action = self._eyeball()
        self.game.energy = 3

        self.assertFalse(self._use(action))

        self.assertFalse(self.game.deck_open())
        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 3)

    def test_only_cards_can_be_picked(self):
        action = self._eyeball()
        self._deck_card(main.Card.JOKER)      # so the pick can arm at all
        tool = main.ToolItem(main.Tool.SHOVEL)
        self.game.toolbox.add(tool)
        self.game._to_deck(tool)
        self.game.energy = 3
        self._use(action)

        self.game._click_deck_pick(self._tile_of(tool).center)

        self.assertIsNone(self.game.item_cell(tool), "a tool was drawn")
        self.assertTrue(self.game.deck_pick_armed(), "the pick was given up")
        self.assertIn(action, self.game.actions)
        self.assertIn("CARD", self.game.shop_message)

    def test_a_folded_eyeball_takes_two_cards(self):
        action = self._eyeball(amount=2)
        first = self._deck_card(main.Card.JOKER)
        second = self._deck_card(main.Card.PLANE)
        self.game.energy = 3
        self._use(action)
        self.assertEqual(self.game.deck_pick_left, 2)

        self.game._click_deck_pick(self._tile_of(first).center)

        # One pick spent: still armed, nothing charged yet.
        self.assertEqual(self.game.deck_pick_left, 1)
        self.assertTrue(self.game.deck_pick_armed())
        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 3)

        self.game._click_deck_pick(self._tile_of(second).center)

        self.assertIsNotNone(self.game.item_cell(second))
        self.assertNotIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 2)
        self.assertFalse(self.game.deck_open())


class DeepPocketsTests(GameTestCase):
    """Deep Pockets: 1 energy for a random pack, at a random structure's cost."""

    def _pockets(self):
        item = main.ActionItem(main.Action.DEEP_POCKETS, 40)
        self.game._adopt_action(item)
        return item

    def _structure(self, value=main.Structure.PIT):
        item = main.StructureItem(value, main.Structure.PRICES[value])
        item.is_level_structure = True
        self.game.shop.items.append(item)
        self.game.set_item_cell(item, self.game._first_free_cell())
        return item

    def _packs(self):
        return [item for item in self.game.toolbox.every_item()
                if getattr(item, "kind", None) == "pack"]

    def _use(self, action):
        self.game.selected_action = action
        return self.game._apply_action()

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.DEEP_POCKETS),
                         "Deep Pockets")
        self.assertEqual(main.Action.energy(main.Action.DEEP_POCKETS), 1)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.DEEP_POCKETS], 1)
        self.assertIn(main.Action.DEEP_POCKETS, main.Action.ORDER)
        line = main.Action.description(main.Action.DEEP_POCKETS, 1)
        self.assertIn("1 random pack", line)
        self.assertIn("1 random structure", line)
        self.assertIn("2 random packs",
                      main.Action.description(main.Action.DEEP_POCKETS, 1, 2))

    def test_it_makes_a_pack_and_pulls_a_structure_down(self):
        action = self._pockets()
        structure = self._structure()
        stood = self.game.item_cell(structure)
        self.game.energy = 3

        self.assertTrue(self._use(action))

        packs = self._packs()
        self.assertEqual(len(packs), 1, "no pack was created")
        self.assertIsNotNone(self.game.item_cell(packs[0]),
                             "the pack is not on the board to open")
        self.assertNotIn(structure, self.game.shop.items,
                         "the structure was not destroyed")
        self.assertIn((structure.value, stood[0], stood[1]),
                      self.game.spent_structures,
                      "the square was not marked spent")
        self.assertNotIn(action, self.game.actions)
        self.assertEqual(self.game.energy, 2)
        self.assertEqual(len(self.game.level_structures()), 0)

    def test_the_wrecked_structure_is_not_revealed(self):
        # A structure is revealed by OPENING it (see _consume_structure); one
        # pulled down without being opened teaches nothing.
        action = self._pockets()
        self._structure(main.Structure.RIFT)
        self.assertFalse(collection.is_structure_discovered(main.Structure.RIFT))
        self.game.energy = 3

        self._use(action)

        self.assertFalse(collection.is_structure_discovered(main.Structure.RIFT))

    def test_a_destroyed_structure_does_not_come_back_on_its_square(self):
        action = self._pockets()
        structure = self._structure()
        stood = self.game.item_cell(structure)
        self.game.energy = 3

        self._use(action)
        self.game._place_level_structures(self.game.current_level())

        self.assertNotIn(stood, {self.game.item_cell(item)
                                 for item in self.game.level_structures()},
                         "a structure was dealt back onto the spent square")

    def test_the_pack_still_comes_with_nothing_left_to_pull_down(self):
        action = self._pockets()
        self.game.energy = 3

        self.assertTrue(self._use(action))

        self.assertEqual(len(self._packs()), 1)
        self.assertIn("no structure", self.game.shop_message.lower())

    def test_it_needs_energy(self):
        action = self._pockets()
        self._structure()
        self.game.energy = 0

        self.assertFalse(self._use(action))

        self.assertEqual(self._packs(), [])
        self.assertEqual(len(self.game.level_structures()), 1)
        self.assertIn(action, self.game.actions)
        self.assertIn("energy", self.game.shop_message.lower())


class NastyCocktailTests(GameTestCase):
    """Nasty Cocktail: 0 energy, and pays energy for its own modifiers."""

    def _cocktail(self, amount=None):
        item = (main.ActionItem(main.Action.NASTY_COCKTAIL, 20) if amount is None
                else main.ActionItem(main.Action.NASTY_COCKTAIL, 20, amount=amount))
        self.game._adopt_action(item)
        return item

    def _use(self, action):
        self.game.selected_action = action
        return self.game._apply_action()

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.NASTY_COCKTAIL),
                         "Nasty Cocktail")
        self.assertEqual(main.Action.energy(main.Action.NASTY_COCKTAIL), 0)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.NASTY_COCKTAIL], 1)
        self.assertIn(main.Action.NASTY_COCKTAIL, main.Action.ORDER)
        self.assertIn("0 energy",
                      main.Action.description(main.Action.NASTY_COCKTAIL, 1))

    def test_a_plain_cocktail_is_kept(self):
        # No modifiers means no energy, so the card waits instead of wasting
        # itself on nothing.
        action = self._cocktail()
        self.game.energy = 1

        self.assertFalse(self._use(action))

        self.assertEqual(self.game.energy, 1)
        self.assertIn(action, self.game.actions)
        self.assertIn("kept", self.game.shop_message)

    def test_it_gives_one_energy_per_modifier(self):
        action = self._cocktail()
        self.game.energy = 1
        main.Modifier.add(action, main.Modifier.GOLDEN)

        self.assertTrue(self._use(action))

        self.assertEqual(self.game.energy, 2)
        self.assertNotIn(action, self.game.actions)

    def test_every_kind_of_modifier_counts_once(self):
        # Stacks are not modifiers: two stacks of forgotten are one kind, but a
        # golden and a forgotten one are two. v2 counts as a modifier too, which
        # is what makes an upgraded cocktail worth pouring.
        action = self._cocktail()
        main.Modifier.set_stacks(action, main.Modifier.FORGOTTEN, 3)
        self.game.energy = 0

        self.assertTrue(self._use(action))

        self.assertEqual(self.game.energy, 1)

        upgraded = self._cocktail()
        upgraded.version = 2
        self.game.energy = 0

        self.assertTrue(self._use(upgraded))

        self.assertEqual(self.game.energy, 1)

    def test_a_folded_cocktail_pays_double(self):
        action = self._cocktail(amount=2)
        main.Modifier.add(action, main.Modifier.GOLDEN)
        self.game.energy = 0

        self.assertTrue(self._use(action))

        self.assertEqual(self.game.energy, 2)

    def test_using_it_costs_no_energy_of_its_own(self):
        action = self._cocktail()
        main.Modifier.add(action, main.Modifier.GOLDEN)
        self.game.energy = 0

        self._use(action)

        # Exactly the energy the modifier paid, and not a point less.
        self.assertEqual(self.game.energy, 1)


class SmellySocksTests(GameTestCase):
    """Smelly Socks: a chip and a mult bonus, for a card out of the hand."""

    def _socks(self):
        card = main.CardItem(main.Card.SMELLY_SOCKS,
                             main.Card.PRICES[main.Card.SMELLY_SOCKS])
        self.game.cards.append(card)
        return card

    def _deck_card(self, value):
        card = main.CardItem(value, main.Card.PRICES.get(value, 24))
        self.game.cards.append(card)
        self.game._to_deck(card)
        return card

    def test_the_catalogue_row(self):
        self.assertEqual(main.Card.name(main.Card.SMELLY_SOCKS), "Smelly Socks")
        self.assertIn(main.Card.SMELLY_SOCKS, main.Card.ORDER)
        self.assertGreater(main.Card.PRICES[main.Card.SMELLY_SOCKS], 0)
        # It pays in two currencies, which no measured card row can express.
        self.assertNotIn(main.Card.SMELLY_SOCKS, components.NAMED_CARD_ORDER)
        line = main.Card.DESCRIPTIONS[main.Card.SMELLY_SOCKS]
        self.assertIn(f"{main.MAGNITUDES.SMELLY_SOCKS_CHIPS:g} chips", line)
        self.assertIn(f"{main.MAGNITUDES.SMELLY_SOCKS_MULT:g} mult", line)
        self.assertIn("deck", line)
        self.assertIn("unplayable", line)

    def test_it_pays_chips_and_mult_at_the_start_of_every_run(self):
        self._socks()
        for _ in range(2):
            self.game.score_chips, self.game.score_mult = 0, 1

            main.cards.apply_cards(self.game)

            self.assertEqual(self.game.score_chips,
                             main.MAGNITUDES.SMELLY_SOCKS_CHIPS)
            self.assertEqual(self.game.score_mult,
                             1 + main.MAGNITUDES.SMELLY_SOCKS_MULT)
        # ...and it says so where the score is.
        self.assertEqual(len(self.game.score_particles), 4)

    def test_two_copies_pay_twice_and_a_disabled_one_pays_nothing(self):
        first = self._socks()
        self._socks()
        self.game.score_chips, self.game.score_mult = 0, 1

        main.cards.apply_cards(self.game)
        self.assertEqual(self.game.score_chips,
                         2 * main.MAGNITUDES.SMELLY_SOCKS_CHIPS)
        self.assertEqual(self.game.score_mult,
                         1 + 2 * main.MAGNITUDES.SMELLY_SOCKS_MULT)

        self.game.disabled_card = first
        self.game.score_chips, self.game.score_mult = 0, 1
        main.cards.apply_cards(self.game)
        self.assertEqual(self.game.score_chips,
                         main.MAGNITUDES.SMELLY_SOCKS_CHIPS)

    def test_a_drawn_hand_sends_one_of_its_cards_back_to_the_deck(self):
        socks = self._socks()
        handmates = [self._deck_card(main.Card.JOKER),
                     self._deck_card(main.Card.PLANE)]
        for item in [socks] + handmates:
            self.game._to_deck(item)

        self.game.draw_deck_hand()

        drawn = self.game.drawn_items()
        self.assertIn(socks, drawn)
        back = [card for card in handmates if self.game.item_cell(card) is None]
        self.assertEqual(len(back), 1, "no card was put back in the deck")
        self.assertIn(back[0], self.game.deck_items(),
                      "the card left the player's ownership")
        # It is the SAME card, not a copy: nothing was thrown away.
        self.assertIn(back[0], self.game.cards)
        self.assertIn("went back into the deck", self.game.shop_message)

    def test_the_card_it_takes_goes_back_not_away(self):
        socks = self._socks()
        mate = self._deck_card(main.Card.JOKER)
        for item in (socks, mate):
            self.game._to_deck(item)
        discarded = self.game.discarded_items_run

        self.game.draw_deck_hand()

        self.assertEqual(self.game.discarded_items_run, discarded,
                         "the card was destroyed, not put back")
        if self.game.item_cell(mate) is None:
            # It went back to the deck, so a later draw can deal it again.
            self.assertTrue(self.game._draw_deck_card(mate),
                            "the card could not be drawn again")
            self.assertIsNotNone(self.game.item_cell(mate))

    def test_it_takes_only_a_card_of_the_same_hand(self):
        # With nothing else in the hand to give up, the socks costs nothing —
        # and a part or a tool drawn beside it is not a card it may take.
        socks = self._socks()
        self.game.deck_drawn = []
        self.game._to_deck(socks)

        self.game._draw_one_item()

        self.assertIn(socks, self.game.hand_items())
        self.assertIn("no other card", self.game.shop_message)

    def test_a_tool_in_the_hand_is_not_a_card_it_takes(self):
        socks = self._socks()
        tool = main.ToolItem(main.Tool.SHOVEL)
        self.game.toolbox.add(tool)
        self.game.ensure_board_cells()
        self.game.deck_drawn = [tool]

        self.game._settle_smelly_socks([socks])

        self.assertIsNotNone(self.game.item_cell(tool),
                             "the tool was sent back to the deck")
