"""Stormcloud: any tool's verb on one structure, and a random one wrecked.

User request: "add a card, 'stormcloud' (break, fix, dig, or reveal, and destroy
1 random structure. costs 1 energy)".

It is the one ACTION with a tool's reach: it is aimed at a structure, opens it
with whichever of the four verbs that structure answers, and then brings one
random structure that is still standing down without opening it (see
Game._action_stormcloud).
"""

from tests.game_test_case import *  # noqa: F401,F403


class StormcloudCase(GameTestCase):
    """A live game with the card, its target and its accomplices to hand."""

    def setUp(self):
        super().setUp()
        self._fresh_game()

    def _fresh_game(self):
        """A brand-new game without re-running setUp.

        setUp captures the player-data paths it replaced, so a second call would
        capture its own throwaway paths and leave the whole suite reading a temp
        folder that is about to be deleted (see test_board_expansion).
        """
        self.game = main.Game()
        self.game.title_screen = False
        self.game.trials_enabled = False
        self.game.energy = main.MAX_ENERGY

    def _stormcloud(self, amount=None):
        item = (main.ActionItem(main.Action.STORMCLOUD,
                                main.Action.PRICES[main.Action.STORMCLOUD])
                if amount is None else
                main.ActionItem(main.Action.STORMCLOUD,
                                main.Action.PRICES[main.Action.STORMCLOUD],
                                amount=amount))
        self.game._adopt_action(item)
        return item

    def _structure(self, value):
        item = main.StructureItem(value, main.Structure.PRICES[value])
        item.is_level_structure = True
        self.game.shop.items.append(item)
        self.game.set_item_cell(item, self.game._first_free_cell())
        return item

    def _use(self, action, *subjects):
        self.game.selection = [action] + list(subjects)
        self.game._refresh_actor()
        return self.game._apply_action()

    def _standing(self):
        return list(self.game.level_structures())


class StormcloudCatalogueTests(StormcloudCase):
    """Its catalogue row, and the one number it carries."""

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.STORMCLOUD), "Stormcloud")
        self.assertIn(main.Action.STORMCLOUD, main.Action.ORDER)
        self.assertGreater(main.Action.PRICES[main.Action.STORMCLOUD], 0)
        self.assertIn(main.Action.STORMCLOUD, main.Action.GLYPHS)
        self.assertIn(main.Action.STORMCLOUD, main.Action.COLORS)
        self.assertTrue(main.Action.comment(main.Action.STORMCLOUD))
        # User request: "costs 1 energy".
        self.assertEqual(main.Action.energy(main.Action.STORMCLOUD), 1)

    def test_it_is_aimed_at_one_structure(self):
        self.assertTrue(main.Action.needs_target(main.Action.STORMCLOUD))
        self.assertTrue(main.Action.targets_structures(main.Action.STORMCLOUD))
        # ...and it needs one, unlike the Dynamite, which may be used bare.
        self.assertFalse(main.Action.optional_target(main.Action.STORMCLOUD))
        action = self._stormcloud()
        self.assertEqual(self.game.required_targets(action), 1)
        card = main.CardItem(main.Card.JOKER, 24)
        self.assertFalse(self.game.is_action_target(card, action))

    def test_the_number_it_carries_is_the_structures_it_destroys(self):
        self.assertEqual(main.MAGNITUDES.STORMCLOUD_DESTROYS, 1)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.STORMCLOUD],
                         main.MAGNITUDES.STORMCLOUD_DESTROYS)
        item = self._stormcloud()
        self.assertEqual(item.amount, 1)
        line = main.Action.description(main.Action.STORMCLOUD, 1)
        self.assertIn("breaks, fixes, digs or reveals", line.lower())
        self.assertIn("1 other random structure", line)
        self.assertIn("1 energy", line)
        # A golem-folded one tears two down, and says so.
        self.assertIn("2 other random structures",
                      main.Action.description(main.Action.STORMCLOUD, 1, 2))

    def test_the_codex_lists_it(self):
        self.game._unlock_entire_collection()
        entries = [entry for entry in self.game._collection_entries()
                   if entry[0] == "action" and entry[1] == main.Action.STORMCLOUD]
        self.assertEqual(len(entries), 1)
        _kind, _value, name, desc, has_icon, discovered = entries[0]
        self.assertEqual(name, "Stormcloud")
        self.assertTrue(desc)
        self.assertTrue(discovered)
        self.assertTrue(has_icon, "the Stormcloud has no icon of its own")

    def test_the_sidebar_states_its_contract(self):
        rows = dict(self.game._describe_item(self._stormcloud()))
        self.assertIn("Needs 1 target", rows["Ability - Apply"])
        self.assertIn("1 energy", rows["Ability - Apply"])
        self.assertIn("Magnitude", rows)


class StormcloudUseTests(StormcloudCase):
    """What it opens, and what it wrecks on the way out."""

    def test_it_opens_a_structure_with_whichever_verb_fits(self):
        # A pit is dug, a mirror broken, a workbench fixed, a library revealed:
        # the card carries all four verbs, so every door but the golem opens.
        for value in (main.Structure.PIT, main.Structure.MIRROR,
                      main.Structure.WORKBENCH, main.Structure.LIBRARY):
            with self.subTest(structure=main.Structure.name(value)):
                self._fresh_game()
                action = self._stormcloud()
                structure = self._structure(value)
                stood = self.game.item_cell(structure)

                self.assertTrue(self._use(action, structure))

                self.assertIsNotNone(self.game.item_at_cell(stood),
                                     "the reward did not take the square")
                self.assertIn((structure.value, stood[0], stood[1]),
                              self.game.spent_structures)
                self.assertFalse(self.game.owns_item(action),
                                 "the card was not spent")
                self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)

    def test_it_reveals_the_structure_it_opened(self):
        action = self._stormcloud()
        structure = self._structure(main.Structure.PIT)
        self.assertFalse(collection.is_structure_discovered(main.Structure.PIT))

        self.assertTrue(self._use(action, structure))

        self.assertTrue(collection.is_structure_discovered(main.Structure.PIT))

    def test_it_destroys_one_random_structure(self):
        action = self._stormcloud()
        opened = self._structure(main.Structure.PIT)
        victims = [self._structure(main.Structure.QUARRY),
                   self._structure(main.Structure.LIBRARY)]
        standing = self._standing()
        self.assertEqual(len(standing), 3)

        self.assertTrue(self._use(action, opened))

        self.assertEqual(len(self._standing()), 1,
                         "the opened one and one random one should be gone")
        survivors = [item for item in victims if item in self._standing()]
        self.assertEqual(len(survivors), 1, "exactly one was destroyed")
        self.assertIn("tore down the", self.game.shop_message)
        self.assertIn("gone for this level", self.game.shop_message)

    def test_it_never_destroys_the_one_it_opened(self):
        # One structure and nothing else: opening it leaves nothing standing, so
        # nothing is torn down and the reward still lands.
        action = self._stormcloud()
        structure = self._structure(main.Structure.VAULT)
        stood = self.game.item_cell(structure)

        self.assertTrue(self._use(action, structure))

        self.assertEqual(self._standing(), [])
        self.assertIn("no other structure was left", self.game.shop_message)
        self.assertIsNotNone(self.game.item_at_cell(stood))

    def test_a_destroyed_structure_teaches_nothing(self):
        # A structure is revealed by OPENING it (see _action_deep_pockets), so
        # the one the storm wrecks stays unknown in the codex. With only the two
        # standing, opening the pit leaves the mint as the only one to wreck.
        action = self._stormcloud()
        opened = self._structure(main.Structure.PIT)
        wrecked = self._structure(main.Structure.MINT)
        self.assertFalse(collection.is_structure_discovered(main.Structure.MINT))

        self.assertTrue(self._use(action, opened))

        self.assertNotIn(wrecked, self._standing())
        self.assertFalse(collection.is_structure_discovered(main.Structure.MINT))
        self.assertTrue(collection.is_structure_discovered(main.Structure.PIT))

    def test_a_folded_one_tears_two_down(self):
        action = self._stormcloud(amount=2)
        opened = self._structure(main.Structure.PIT)
        for value in (main.Structure.QUARRY, main.Structure.LIBRARY,
                      main.Structure.VAULT):
            self._structure(value)
        standing = len(self._standing())

        self.assertTrue(self._use(action, opened))

        self.assertEqual(len(self._standing()), standing - 3)

    def test_it_costs_one_energy_and_is_spent(self):
        action = self._stormcloud()
        opened = self._structure(main.Structure.PIT)
        self.game.energy = 2
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action, opened))

        self.assertEqual(self.game.energy, 1)
        self.assertFalse(self.game.owns_item(action))
        self.assertEqual(self.game.discarded_items_run, discarded + 1)

    def test_it_works_through_the_keys(self):
        action = self._stormcloud()
        opened = self._structure(main.Structure.PIT)
        stood = self.game.item_cell(opened)

        self._click(self._item_pos(action))
        self._click(self._item_pos(opened))
        self._press(main.pygame.K_s)

        self.assertFalse(self.game.owns_item(action))
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)
        self.assertEqual(self._standing(), [])
        self.assertIsNotNone(self.game.item_at_cell(stood),
                             "the reward did not land on the square")


class StormcloudRefusalTests(StormcloudCase):
    """What it will not do, and what that costs (nothing)."""

    def test_out_of_energy_it_is_kept(self):
        action = self._stormcloud()
        opened = self._structure(main.Structure.PIT)
        self.game.energy = 0
        standing = len(self._standing())

        self.assertFalse(self._use(action, opened))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, 0)
        self.assertEqual(len(self._standing()), standing)
        self.assertIn("Out of energy", self.game.shop_message)

    def test_with_nothing_selected_nothing_happens(self):
        action = self._stormcloud()
        self._structure(main.Structure.PIT)

        self.assertFalse(self._use(action))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, main.MAX_ENERGY)
        self.assertIn("0 selected", self.game.shop_message)

    def test_two_structures_are_refused(self):
        action = self._stormcloud()
        first = self._structure(main.Structure.PIT)
        second = self._structure(main.Structure.QUARRY)

        self.assertFalse(self._use(action, first, second))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, main.MAX_ENERGY)
        self.assertEqual(len(self._standing()), 2)
        self.assertIn("2 selected", self.game.shop_message)

    def test_the_golem_is_refused(self):
        # A golem wants a tool and two of the player's items, not a storm.
        action = self._stormcloud()
        golem = self._structure(main.Structure.GOLEM)

        self.assertFalse(self._use(action, golem))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, main.MAX_ENERGY)
        self.assertIn("not a storm", self.game.shop_message)
        self.assertIn(golem, self._standing())

    def test_a_card_is_not_a_target(self):
        action = self._stormcloud()
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        self.game._on_item_gained(card)
        self._structure(main.Structure.PIT)

        self.assertFalse(self.game.is_action_target(card, action))
        self.assertFalse(self._use(action, card))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, main.MAX_ENERGY)
