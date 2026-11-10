"""The MODIFIER system, and the five tools built on top of it.

User request: "add a tool, 'drill': (break, fix, dig, or reveal, but add 'dirt'
to your deck. costs 0 energy). add the tool 'dirt': does nothing. add a tool,
'pickaxe': (dig, make spark. costs 1 energy.) add a tool, 'spark': (reveal,
consume, temporary. costs 0 energy). the keyword 'temporary' means it will be
destroyed next round. add a tool, 'vodka': (select 1 card to give 3 stacks of
'forgotten', consume. costs 1 energy). the modifier 'forgotten' means: cannot be
drawn, remove 1 stack of forgotten each run. create a system of modifiers for
items: 'golden', 'diamond', and 'forgotten' are all modifiers. tokens are just
blocks with the 'token' modifier ... blocks with extra triggers have ... the
'retriggerable' modifier ... v2 actions have the 'v2' modifier. If there are
similar parts of the game you see fit to be interpreted as a modifier, add them
to the modifier system."

Two classes: the TABLE (every modifier is one row with a name, a meaning and a
colour, and every stack count is readable and writable on any item), and the
PLAY (each new tool, and each modifier's clock).
"""

import pygame

from tests.game_test_case import *  # noqa: F401,F403


class ModifierTableTests(GameTestCase):
    """One table of modifiers, and the item state it now holds."""

    def test_every_modifier_has_a_name_a_meaning_and_a_place(self):
        for modifier in main.Modifier.ORDER:
            with self.subTest(modifier=main.Modifier.name(modifier)):
                self.assertTrue(main.Modifier.name(modifier))
                self.assertTrue(main.Modifier.description(modifier))
                self.assertIn(modifier, main.Modifier.COLORS)
        self.assertEqual(len(set(main.Modifier.ORDER)), len(main.Modifier.ORDER))

    def test_the_named_modifiers_are_all_there(self):
        names = {main.Modifier.name(modifier) for modifier in main.Modifier.ORDER}
        self.assertLessEqual(
            {"golden", "diamond", "forgotten", "temporary", "token",
             "retriggerable", "v2", "flipped", "disabled"}, names)

    def test_stacks_are_read_added_and_worn_off_on_any_item(self):
        for item in (main.CardItem(main.Card.JOKER, 24),
                     main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                    main.Scorer.CHIPS_ADD, 10, 20, "Rect"),
                     main.ToolItem(main.Tool.SHOVEL),
                     main.PassiveItem(main.Passive.CONCRETE, 16),
                     main.StructureItem(main.Structure.PIT, 0),
                     main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)):
            with self.subTest(item=type(item).__name__):
                self.assertEqual(main.Modifier.stacks(
                    item, main.Modifier.FORGOTTEN), 0)
                main.Modifier.add(item, main.Modifier.FORGOTTEN, 2)
                self.assertEqual(main.Modifier.stacks(
                    item, main.Modifier.FORGOTTEN), 2)
                main.Modifier.set_stacks(item, main.Modifier.FORGOTTEN, 0)
                self.assertFalse(main.Modifier.has(item, main.Modifier.FORGOTTEN))
                self.assertEqual(main.Modifier.of(item), [])

    def test_the_sidebar_row_names_each_modifier_and_its_stacks(self):
        card = main.CardItem(main.Card.JOKER, 24)
        main.Modifier.add(card, main.Modifier.FORGOTTEN, 3)
        rows = dict(self.game._describe_item(card))
        self.assertIn("Modifier - Forgotten", rows)
        self.assertIn("3 stacks", rows["Modifier - Forgotten"])
        self.assertIn("cannot be drawn", rows["Modifier - Forgotten"].lower())

    def test_the_tile_wears_a_mark_for_a_timed_modifier(self):
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        card = main.CardItem(main.Card.JOKER, 24)
        main.ui.draw_shop_item(surface, card, surface.get_rect())
        plain = pygame.image.tostring(surface, "RGB")
        main.Modifier.add(card, main.Modifier.FORGOTTEN, 2)
        main.ui.draw_shop_item(surface, card, surface.get_rect())
        self.assertNotEqual(pygame.image.tostring(surface, "RGB"), plain)


class QualityAsModifierTests(GameTestCase):
    """The golem's tiers are the golden/diamond modifiers now."""

    def test_golden_and_diamond_are_modifiers(self):
        card = main.CardItem(main.Card.JOKER, 24)
        card.quality = main.Quality.GOLDEN
        self.assertEqual(main.Modifier.stacks(card, main.Modifier.GOLDEN), 1)
        self.assertEqual(main.Quality.of(card), main.Quality.GOLDEN)
        card.quality = main.Quality.DIAMOND
        self.assertEqual(main.Modifier.stacks(card, main.Modifier.GOLDEN), 0)
        self.assertEqual(main.Modifier.stacks(card, main.Modifier.DIAMOND), 1)
        self.assertEqual(main.Quality.of(card), main.Quality.DIAMOND)

    def test_a_modifier_stack_can_make_an_item_golden_too(self):
        card = main.CardItem(main.Card.JOKER, 24)
        main.Modifier.add(card, main.Modifier.GOLDEN)
        self.assertEqual(main.Quality.of(card), main.Quality.GOLDEN)
        self.assertTrue(main.Quality.title(card))


class ExistingStateAsModifiersTests(GameTestCase):
    """The state the game already kept is the same system now."""

    def test_a_block_with_extra_triggers_is_retriggerable(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD, trigger_limit=3)
        self.assertEqual(main.Modifier.stacks(
            block, main.Modifier.RETRIGGERABLE), 2)
        self.assertEqual(block.trigger_limit, 3)
        block.trigger_limit += 1
        self.assertEqual(main.Modifier.stacks(
            block, main.Modifier.RETRIGGERABLE), 3)
        self.assertEqual(block.trigger_limit, 4)

    def test_a_v2_action_carries_the_v2_modifier(self):
        action = main.ActionItem(main.Action.DEJA_VU, 60, version=2)
        self.assertEqual(main.Modifier.stacks(action, main.Modifier.V2), 1)
        self.assertEqual(action.version, 2)
        action.version = 1
        self.assertEqual(main.Modifier.stacks(action, main.Modifier.V2), 0)

    def test_a_token_is_a_block_with_the_token_modifier(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=25)
        token = main.ScorerToken(block, runs_left=2)
        self.assertEqual(main.Modifier.stacks(block, main.Modifier.TOKEN), 2)
        self.assertEqual(token.runs_left, 2)
        # The flag the drawing and firing paths read is the same state.
        self.assertTrue(block.is_token)
        permanent = main.ScorerToken(
            main.Block(1, 1, scorer=main.Scorer.MULT_ADD))
        self.assertEqual(main.Modifier.stacks(
            permanent.block, main.Modifier.TOKEN), main.Modifier.PERMANENT)
        self.assertIsNone(permanent.runs_left)
        self.assertIn("permanent", main.Modifier.line(permanent))
        self.assertFalse(main.Block(2, 2).is_token)

    def test_the_disabled_card_is_the_disabled_modifier(self):
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.disabled_card = card
        self.assertTrue(main.Modifier.has(card, main.Modifier.DISABLED))
        self.assertTrue(self.game._card_disabled(card))
        other = main.CardItem(main.Card.MARKET, 24)
        self.assertFalse(main.Modifier.has(other, main.Modifier.DISABLED))
        self.game.disabled_card = None
        self.assertFalse(main.Modifier.has(card, main.Modifier.DISABLED))

    def test_a_flipped_card_is_the_flipped_modifier(self):
        card = main.CardItem(main.Card.JOKER, 24)
        card.flipped = True
        self.assertTrue(main.Modifier.has(card, main.Modifier.FLIPPED))
        card.flipped = False
        self.assertFalse(main.Modifier.has(card, main.Modifier.FLIPPED))

    def test_every_modifier_rides_through_a_save(self):
        card = main.CardItem(main.Card.JOKER, 24)
        main.Modifier.add(card, main.Modifier.FORGOTTEN, 3)
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD, trigger_limit=2)
        block.quality = main.Quality.GOLDEN
        action = main.ActionItem(main.Action.DEJA_VU, 60, version=2)
        for item in (card, block, action):
            with self.subTest(item=type(item).__name__):
                loaded = save_system._deserialize_item(
                    save_system._serialize_item(item))
                self.assertEqual(main.Modifier.of(loaded), main.Modifier.of(item))


class NewModifierToolTests(GameTestCase):
    """The five tools: what they open, what they leave, what they cost."""

    def setUp(self):
        super().setUp()
        self.game.title_screen = False
        self.game.ensure_board_cells()
        cell = self.game._first_free_cell()
        self.game.grid[cell] = main.Block(cell[0], cell[1],
                                          scorer=main.Scorer.START)

    # --- helpers ------------------------------------------------------------

    def _tool(self, value):
        tool = main.ToolItem(value)
        self.game.toolbox.add(tool)
        self.game.ensure_board_cells()
        self.assertIsNotNone(self._item_cell(tool))
        return tool

    def _structure(self, value):
        structure = main.StructureItem(value, main.Structure.PRICES[value])
        structure.is_level_structure = True
        self.game.toolbox.add(structure)
        self.game.set_item_cell(structure, self.game._first_free_cell())
        self.game.shop.items.append(structure)
        return structure

    def _use(self, tool, target, energy=None):
        self.game._clear_toolbox_selection()
        if energy is not None:
            self.game.energy = energy
        self._click(self._item_pos(tool))
        self._click(self._item_pos(target))
        self._press(main.pygame.K_s)

    def _deck_tools(self, value):
        return [item for item in self.game.deck_items()
                if getattr(item, "kind", None) == "tool" and item.value == value]

    # --- dirt ---------------------------------------------------------------

    def test_dirt_does_nothing(self):
        dirt = main.ToolItem(main.Tool.DIRT)
        self.assertEqual(dirt.verbs, ())
        self.assertIsNone(main.Ability.of(dirt))
        self.assertEqual(main.Keyword.line(dirt), "unplayable")
        self.assertEqual(main.Tool.energy(main.Tool.DIRT), 0)

    # --- drill --------------------------------------------------------------

    def test_a_drill_opens_any_door_for_free_and_packs_dirt(self):
        drill = self._tool(main.Tool.DRILL)
        for value in (main.Structure.QUARRY, main.Structure.SHRINE,
                      main.Structure.VAULT, main.Structure.LIBRARY):
            with self.subTest(structure=main.Structure.name(value)):
                structure = self._structure(value)
                self._use(drill, structure, energy=0)
                self.assertEqual(self.game.energy, 0)
                self.assertTrue(self.game.owns_item(drill))
        self.assertEqual(len(self._deck_tools(main.Tool.DIRT)), 4)

    def test_the_dirt_a_drill_leaves_cannot_be_used(self):
        drill = self._tool(main.Tool.DRILL)
        self._use(drill, self._structure(main.Structure.VAULT), energy=0)
        dirt = self._deck_tools(main.Tool.DIRT)[0]
        self.assertIsNone(main.Ability.of(dirt))

    # --- pickaxe and spark --------------------------------------------------

    def test_a_pickaxe_digs_and_strikes_a_spark(self):
        pickaxe = self._tool(main.Tool.PICKAXE)
        pit = self._structure(main.Structure.PIT)

        self._use(pickaxe, pit, energy=1)

        self.assertEqual(self.game.energy, 0)
        self.assertTrue(self.game.owns_item(pickaxe))
        sparks = self._deck_tools(main.Tool.SPARK)
        self.assertEqual(len(sparks), 1)
        self.assertTrue(main.Modifier.has(sparks[0], main.Modifier.TEMPORARY))

    def test_a_spark_reveals_for_free_and_is_temporary(self):
        spark = self._tool(main.Tool.SPARK)
        self.assertEqual(main.Keyword.line(spark), "reveal, consume, temporary")
        library = self._structure(main.Structure.LIBRARY)

        self._use(spark, library, energy=0)

        self.assertEqual(self.game.energy, 0)
        self.assertFalse(self.game.owns_item(spark))

    def test_a_temporary_item_is_destroyed_when_the_run_is_over(self):
        spark = self._tool(main.Tool.SPARK)
        self.assertTrue(self.game.owns_item(spark))

        self.game._age_modifiers()

        self.assertFalse(self.game.owns_item(spark))

    # --- vodka and forgotten ------------------------------------------------

    def test_vodka_pours_three_forgotten_into_a_card_and_is_drunk(self):
        vodka = self._tool(main.Tool.VODKA)
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        self.game._on_item_gained(card)
        self.game.ensure_board_cells()

        self._use(vodka, card, energy=1)

        self.assertEqual(main.Modifier.stacks(card, main.Modifier.FORGOTTEN),
                         main.MAGNITUDES.VODKA_FORGOTTEN)
        self.assertFalse(self.game.owns_item(vodka))
        self.assertEqual(self.game.energy, 0)

    def test_a_forgotten_card_cannot_be_drawn(self):
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        self.game._to_deck(card)
        main.Modifier.add(card, main.Modifier.FORGOTTEN, 2)

        self.assertNotIn(card, self.game.drawable_deck_items())
        self.assertNotIn(card, self.game.draw_deck_hand())

    def test_a_forgotten_stack_wears_off_every_run(self):
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        self.game._to_deck(card)
        main.Modifier.add(card, main.Modifier.FORGOTTEN, 2)

        self.game._age_modifiers()
        self.assertEqual(main.Modifier.stacks(card, main.Modifier.FORGOTTEN), 1)
        self.game._age_modifiers()
        self.assertEqual(main.Modifier.stacks(card, main.Modifier.FORGOTTEN), 0)
        self.assertIn(card, self.game.drawable_deck_items())

    def test_the_vodka_needs_exactly_one_card(self):
        vodka = self._tool(main.Tool.VODKA)
        first = main.CardItem(main.Card.JOKER, 24)
        second = main.CardItem(main.Card.MARKET, 24)
        for card in (first, second):
            self.game.cards.append(card)
            self.game._on_item_gained(card)
        self.game.ensure_board_cells()

        self.game._clear_toolbox_selection()
        self.game.energy = 1
        self._click(self._item_pos(vodka))
        self._click(self._item_pos(first))
        self._click(self._item_pos(second))
        self._press(main.pygame.K_s)

        self.assertEqual(main.Modifier.of(first), [])
        self.assertTrue(self.game.owns_item(vodka))
        self.assertEqual(self.game.energy, 1)

    # --- the collection and the icons ---------------------------------------

    def test_every_new_tool_is_a_collection_entry_with_an_icon(self):
        self.game._unlock_entire_collection()
        names = {name for kind, value, name, desc, icon, seen
                 in self.game._collection_entries() if kind == "tool"}
        for value in (main.Tool.DIRT, main.Tool.DRILL, main.Tool.PICKAXE,
                      main.Tool.SPARK, main.Tool.VODKA):
            with self.subTest(tool=main.Tool.name(value)):
                self.assertIn(main.Tool.name(value), names)
                art = main.ui._tool_art(value)
                self.assertIsNotNone(art)
                self.assertGreater(art.get_bounding_rect().width, 0)
