"""Structures, the tools that open them, and the Cleansing action.

The shop sells STRUCTURES now (user request: "replace shop items with
'structures'"): a pit, a crystal pool, a mirror. A structure is scenery until a
TOOL is used on it — select the tool, select the structure, press S — and what
comes out is either a finished item (an action) or a pack to choose from. The
player starts with the four tools (shovel, flashlight, screwdriver, hammer), one
per verb, and never spends one.
"""

from tests.game_test_case import *  # noqa: F401,F403


class StructureDataTests(GameTestCase):
    """The tables: what opens what, and what comes out."""

    def test_structure_data_lives_in_components(self):
        for structure in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(structure)):
                self.assertIn(structure, main.Structure.NAMES)
                self.assertIn(structure, main.Structure.RESULTS)
                self.assertIn(structure, main.Structure.COMMENTS)
                self.assertIn(structure, main.Structure.PRICES)
                self.assertIn(structure, main.Structure.COLORS)
                self.assertIn(structure, main.Structure.GLYPHS)
                # Structures are free (user request), so nothing is charged.
                self.assertEqual(main.Structure.PRICES[structure], 0)
                self.assertTrue(main.Structure.description(structure))
                self.assertTrue(main.Structure.verbs(structure))
        # One structure per pack comes after the four the game opened with (see
        # the PACK STRUCTURES test below), in Pack.ORDER's own order.
        self.assertEqual(list(main.Structure.ORDER),
                         [main.Structure.PIT, main.Structure.CRYSTAL_POOL,
                          main.Structure.MIRROR, main.Structure.GOLEM,
                          main.Structure.QUARRY, main.Structure.SHRINE,
                          main.Structure.VAULT, main.Structure.WORKBENCH,
                          main.Structure.DEPOT, main.Structure.LIBRARY,
                          main.Structure.CABINET, main.Structure.MINT,
                          main.Structure.RIFT, main.Structure.SHED])

    def test_a_structure_only_answers_to_its_own_verbs(self):
        # The table is explicit: a pit can be dug and nothing else, the pool
        # pays out either way it is opened, and the mirror's two verbs give two
        # very different halves (user request).
        # A pit is dug into, and a light shown down it reveals what else fell
        # in (see Structure.RESULTS).
        self.assertEqual(main.Structure.verbs(main.Structure.PIT),
                         [main.Verb.DIG, main.Verb.REVEAL])
        self.assertEqual(sorted(main.Structure.verbs(main.Structure.CRYSTAL_POOL)),
                         sorted([main.Verb.REVEAL, main.Verb.DIG]))
        self.assertEqual(sorted(main.Structure.verbs(main.Structure.MIRROR)),
                         sorted([main.Verb.FIX, main.Verb.BREAK]))
        self.assertIsNone(main.Structure.result(main.Structure.PIT,
                                                main.Verb.BREAK))
        self.assertEqual(main.Structure.result(main.Structure.PIT, main.Verb.DIG),
                         ("pack", main.Pack.PART))
        self.assertEqual(
            main.Structure.result(main.Structure.CRYSTAL_POOL, main.Verb.REVEAL),
            ("action", main.Action.CLEANSING))
        self.assertEqual(
            main.Structure.result(main.Structure.MIRROR, main.Verb.FIX),
            ("action", main.Action.RECOGNITION))
        self.assertEqual(
            main.Structure.result(main.Structure.MIRROR, main.Verb.BREAK),
            ("action", main.Action.STRENGTH))

    def test_every_verb_has_exactly_one_tool(self):
        # The four the player starts with are one per verb; every other tool in
        # the catalogue is a Tool Pack find, and each carries its own verbs (see
        # Tool.VERBS -- a pry bar two, a multi-tool all four).
        self.assertEqual(sorted(main.Tool.STARTERS),
                         sorted([main.Tool.SHOVEL, main.Tool.FLASHLIGHT,
                                 main.Tool.SCREWDRIVER, main.Tool.HAMMER]))
        # Every tool is either starting kit, a Tool Pack find, or a by-product
        # another tool leaves behind (a drill's dirt).
        self.assertEqual(sorted(main.Tool.ORDER),
                         sorted(list(main.Tool.STARTERS)
                                + list(main.Tool.PACK_ORDER)
                                + list(main.Tool.BY_PRODUCTS)))
        for verb in main.Verb.ORDER:
            with self.subTest(verb=main.Verb.name(verb)):
                tool = main.Tool.for_verb(verb)
                self.assertIsNotNone(tool)
                self.assertEqual(main.Tool.verb(tool), verb)
                self.assertTrue(main.Tool.description(tool))
                self.assertIn(main.Tool.name(tool), ("Shovel", "Flashlight",
                                                     "Screwdriver", "Hammer"))
        # A tool with no verb (the dirt) has no first verb, so the SET of first
        # verbs covers every verb and nothing else.
        self.assertEqual({main.Tool.verb(tool) for tool in main.Tool.ORDER
                          if main.Tool.verbs(tool)},
                         set(main.Verb.ORDER))
        self.assertIsNone(main.Tool.verb(main.Tool.DIRT))


class ToolCase(GameTestCase):
    """Shared helpers for the tool classes: the tool, the structure, the clicks."""

    def _seat(self, item):
        """Make sure ``item`` stands on a board square a test can click.

        A level opens its own squares, so an item seated on the old region may
        have been put back in the deck (see ensure_board_cells); a test that
        clicks it needs it on the board again.
        """
        if self.game.item_cell(item) is not None:
            return item
        taken = set(self.game.grid)
        taken |= {self.game.item_cell(other) for other in self.game.owned_items()}
        for cell in sorted(self.game.unlocked_cells):
            if cell not in taken:
                self.game.set_item_cell(item, cell)
                break
        self.assertIsNotNone(self.game.item_cell(item))
        return item

    def _tool(self, verb):
        return self._seat(next(item for item in self.game.toolbox.items
                              if getattr(item, "kind", None) == "tool"
                              and item.verb == verb))

    def _structure(self, value, cell=(4, main.SHOP_ITEM_ROW)):
        structure = main.StructureItem(value, main.Structure.PRICES[value],
                                      col=cell[0], row=cell[1])
        self.game.toolbox.add(structure)
        self.game.ensure_board_cells()
        self.assertIsNotNone(self._item_cell(structure))
        return structure

    def _use_tool(self, verb, structure, tool=None):
        """Select the tool, then the structure, then press S (the player's way).

        A tool stays armed after it opens something (it is never spent), so it is
        only clicked when it is not the one in hand already — clicking it again
        would turn its switch off. A DIFFERENT tool has to be switched off first:
        the first item selected is always the actor, so a second tool would
        otherwise become a target of the first (user request: a click never
        changes another item's switch).
        """
        if tool is None:
            tool = self._tool(verb)
        armed = self.game.selected_tool
        if armed is not tool:
            if armed is not None:
                self._click(self._item_pos(armed))   # switch the other tool off
            self._click(self._item_pos(tool))
        self._click(self._item_pos(structure))
        self._press(main.pygame.K_s)

    def _packs(self):
        return [item for item in self.game.toolbox.items
                if getattr(item, "kind", None) == "pack"]


class GolemTests(ToolCase):
    """The golem: two of the same item become one with both their magnitudes.

    User request: "add a structure, 'golem': combine 2 of the same items to
    create 1 new item with double the magnitude", and "make sure ALL numbers are
    encoded as magnitudes: using a golem on 2 lanterns should create a new
    lantern that draws 4 items".
    """

    def _lantern(self, amount=None):
        lantern = main.ActionItem(main.Action.LANTERN,
                                  main.Action.PRICES[main.Action.LANTERN],
                                  amount=amount)
        self.game._adopt_action(lantern)
        return self._seat(lantern)

    def _scorer(self, amount=30):
        piece = main.Component.scorer_component(main.Scorer.CHIPS_ADD,
                                                amount=amount)
        self.game.toolbox.add(piece)
        self.game.ensure_board_cells()
        return self._seat(piece)

    def _clear_selection(self):
        """Unselect everything, so a loop over verbs starts from nothing.

        Clicking each selected item again is what the player does; the tail of
        the queue is dropped by hand because a merged item stays selected and a
        second S press would fire ITS ability (a Lantern would burn out).
        """
        for item in list(self.game.selection):
            self._click(self._item_pos(item))
        self.game.selection = []
        self.game.selected_tool = None
        self.game.selected_action = None

    def _combine(self, verb, golem, *items):
        """Arm a tool, select the golem and the items, then press S."""
        self._clear_selection()
        tool = self._tool(verb)
        self._click(self._item_pos(tool))
        self._click(self._item_pos(golem))
        for item in items:
            self._click(self._item_pos(item))
        self._press(main.pygame.K_s)

    def _concrete(self, amount=None):
        item = main.PassiveItem(main.Passive.CONCRETE,
                                main.Passive.PRICES[main.Passive.CONCRETE],
                                amount=amount)
        self.game.toolbox.add(item)
        self.game.ensure_board_cells()
        return self._seat(item)

    def test_two_concretes_become_one_golden_concrete_of_sixty(self):
        # EVERY item carries an amount, so a passive is a magnitude like any
        # other and the golem folds two Concretes into one of 2 x 30 (user
        # request: "make sure EVERY item has an amount").
        golem = self._structure(main.Structure.GOLEM)
        first, second = self._concrete(), self._concrete()
        self.assertEqual(first.amount, main.MAGNITUDES.CONCRETE_CHIPS)

        self._combine(main.Verb.FIX, golem, first, second)

        kept = [item for item in self.game.toolbox.items
                if getattr(item, "kind", None) == "passive"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].amount, main.MAGNITUDES.CONCRETE_CHIPS * 2)
        self.assertEqual(main.Quality.of(kept[0]), main.Quality.GOLDEN)
        self.assertFalse(self.game.owns_item(second))

    def test_the_golem_takes_two_of_the_same_item(self):
        self.assertEqual(main.Structure.merge_count(main.Structure.GOLEM),
                         main.Structure.result(main.Structure.GOLEM,
                                               main.Verb.DIG)[1])
        self.assertEqual(main.Structure.merge_count(main.Structure.GOLEM), 2)
        self.assertTrue(main.Structure.merges(main.Structure.GOLEM))
        self.assertIn("same item", main.Structure.description(main.Structure.GOLEM))

    def test_two_lanterns_become_one_that_draws_four(self):
        golem = self._structure(main.Structure.GOLEM)
        first, second = self._lantern(), self._lantern()

        self._combine(main.Verb.FIX, golem, first, second)

        lanterns = [action for action in self.game.actions
                    if action.value == main.Action.LANTERN]
        self.assertEqual(len(lanterns), 1)
        self.assertEqual(lanterns[0].amount, main.MAGNITUDES.LANTERN_DRAWS * 2)
        self.assertEqual(lanterns[0], first)          # one of the two, kept
        self.assertFalse(self.game.owns_item(second))
        self.assertFalse(self.game.owns_item(golem))
        self.assertIn("fixed", self.game.shop_message)
        # The much that matters: the combined Lantern really draws four.
        self.assertIn("4 items",
                      main.Action.description(main.Action.LANTERN, 1,
                                              lanterns[0].amount))

    def test_the_combined_item_takes_the_golems_square(self):
        golem = self._structure(main.Structure.GOLEM)
        home = self._item_cell(golem)
        first, second = self._lantern(), self._lantern()

        self._combine(main.Verb.DIG, golem, first, second)

        self.assertEqual(self._item_cell(first), home)

    def test_a_scorer_piece_doubles_its_amount(self):
        golem = self._structure(main.Structure.GOLEM)
        first, second = self._scorer(30), self._scorer(30)

        self._combine(main.Verb.REVEAL, golem, first, second)

        kept = [piece for piece in self.game.toolbox.items
                if getattr(piece, "kind", None) == main.Component.SCORER]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].amount, 60)
        self.assertFalse(self.game.owns_item(second))

    def test_a_block_is_combined_the_same_way(self):
        golem = self._structure(main.Structure.GOLEM)
        build = dict(shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                     scorer_amount=30)
        first = main.Block(0, 0, **build)
        second = main.Block(1, 1, **build)
        self.game.grid[(0, 0)] = first
        self.game.grid[(1, 1)] = second

        self._combine(main.Verb.BREAK, golem, first, second)

        self.assertEqual(first.scorer_amount, 60)
        self.assertNotIn((1, 1), self.game.grid)

    def test_the_golem_answers_to_any_tool(self):
        # It is a workbench, not a lock: every verb wakes it.
        for verb in main.Verb.ORDER:
            with self.subTest(verb=main.Verb.name(verb)):
                self.game.energy = 3
                golem = self._structure(main.Structure.GOLEM)
                first, second = self._lantern(), self._lantern()
                self._combine(verb, golem, first, second)
                self.assertFalse(self.game.owns_item(golem))
                self.assertEqual(first.amount,
                                 main.MAGNITUDES.LANTERN_DRAWS * 2)

    def test_two_different_items_are_refused_and_nothing_is_spent(self):
        golem = self._structure(main.Structure.GOLEM)
        lantern = self._lantern()
        other = main.ActionItem(main.Action.CLEANSING,
                                main.Action.PRICES[main.Action.CLEANSING])
        self.game._adopt_action(other)
        self._seat(other)
        energy = self.game.energy

        self._combine(main.Verb.FIX, golem, lantern, other)

        self.assertIn("SAME item", self.game.shop_message)
        self.assertTrue(self.game.owns_item(golem))
        self.assertEqual(self.game.energy, energy)
        self.assertEqual(lantern.amount, main.MAGNITUDES.LANTERN_DRAWS)

    def test_one_item_is_not_enough(self):
        golem = self._structure(main.Structure.GOLEM)
        lantern = self._lantern()
        energy = self.game.energy

        self._combine(main.Verb.FIX, golem, lantern)

        self.assertIn("combines 2", self.game.shop_message)
        self.assertTrue(self.game.owns_item(golem))
        self.assertEqual(self.game.energy, energy)

    def test_an_item_with_no_magnitude_is_refused(self):
        # Two plain Rects have nothing for the golem to double.
        golem = self._structure(main.Structure.GOLEM)
        pieces = []
        for _ in range(2):
            piece = main.Component.shape_component(main.Shape.SLOPE)
            self.game.toolbox.add(piece)
            pieces.append(self._seat(piece))
        energy = self.game.energy

        self._combine(main.Verb.FIX, golem, *pieces)

        self.assertIn("no magnitude", self.game.shop_message)
        self.assertTrue(self.game.owns_item(golem))
        self.assertEqual(self.game.energy, energy)


class GoldenTests(GolemTests):
    """A golem's work is a TIER: golden at first, diamond at the second fold.

    User requests: "make items combined by the golem 'golden', and show that in
    their name and appearance. make the player able to combine two golden items
    into a diamond item, with 4x the magnitude of the original item."
    """

    def test_the_tier_table_says_everything_about_a_tier(self):
        for quality in main.Quality.ORDER:
            with self.subTest(quality=quality):
                self.assertIn(quality, main.Quality.NAMES)
                self.assertIn(quality, main.Quality.MULTIPLIERS)
                self.assertIn(quality, main.Quality.COLORS)
                if quality != main.Quality.NORMAL:
                    self.assertTrue(main.Quality.name(quality))
                    self.assertIsNotNone(main.Quality.color(quality))
                    self.assertTrue(main.Quality.description(quality))
        self.assertEqual(main.Quality.ORDER,
                         [main.Quality.NORMAL, main.Quality.GOLDEN,
                          main.Quality.DIAMOND])
        # One golem doubles, so the tiers are 1x, 2x and 4x the plain item.
        self.assertEqual(main.Quality.multiplier(main.Quality.GOLDEN), 2)
        self.assertEqual(main.Quality.multiplier(main.Quality.DIAMOND), 4)
        self.assertEqual(main.Quality.combines_into(main.Quality.NORMAL),
                         main.Quality.GOLDEN)
        self.assertEqual(main.Quality.combines_into(main.Quality.GOLDEN),
                         main.Quality.DIAMOND)
        self.assertIsNone(main.Quality.combines_into(main.Quality.DIAMOND))

    def test_a_combined_item_is_golden_in_name_and_sidebar(self):
        golem = self._structure(main.Structure.GOLEM)
        first, second = self._lantern(), self._lantern()

        self._combine(main.Verb.FIX, golem, first, second)

        self.assertEqual(main.Quality.of(first), main.Quality.GOLDEN)
        self.assertEqual(self.game._item_name(first), "Golden Lantern")
        rows = dict(self.game._describe_item(first))
        self.assertIn("Modifier - Golden", rows)
        self.assertIn("2x", rows["Modifier - Golden"])
        self.assertIn("Golden", self.game.shop_message)

    def test_two_golden_items_become_a_diamond_worth_four_times_the_original(self):
        pair = self._lantern(), self._lantern()
        self._combine(main.Verb.FIX, self._structure(main.Structure.GOLEM), *pair)
        golden = pair[0]
        self.assertEqual(golden.amount, main.MAGNITUDES.LANTERN_DRAWS * 2)

        second_golden = self._lantern(main.MAGNITUDES.LANTERN_DRAWS * 2)
        second_golden.quality = main.Quality.GOLDEN
        self._combine(main.Verb.FIX, self._structure(main.Structure.GOLEM),
                      golden, second_golden)

        self.assertEqual(main.Quality.of(golden), main.Quality.DIAMOND)
        self.assertEqual(golden.amount, main.MAGNITUDES.LANTERN_DRAWS * 4)
        self.assertEqual(self.game._item_name(golden), "Diamond Lantern")
        self.assertFalse(self.game.owns_item(second_golden))
        # ...and the diamond really draws what it says it does.
        self.assertIn("8 items",
                      main.Action.description(main.Action.LANTERN, 1,
                                              golden.amount))

    def test_a_golden_item_and_a_plain_one_are_refused(self):
        golem = self._structure(main.Structure.GOLEM)
        pair = self._lantern(), self._lantern()
        self._combine(main.Verb.FIX, self._structure(main.Structure.GOLEM), *pair)
        golden = pair[0]
        plain = self._lantern()
        energy = self.game.energy

        self._combine(main.Verb.FIX, golem, golden, plain)

        self.assertIn("same quality", self.game.shop_message)
        self.assertEqual(self.game.energy, energy)
        self.assertTrue(self.game.owns_item(golem))
        self.assertEqual(main.Quality.of(golden), main.Quality.GOLDEN)

    def test_a_diamond_is_final(self):
        first = self._lantern(main.MAGNITUDES.LANTERN_DRAWS * 4)
        second = self._lantern(main.MAGNITUDES.LANTERN_DRAWS * 4)
        first.quality = main.Quality.DIAMOND
        second.quality = main.Quality.DIAMOND
        golem = self._structure(main.Structure.GOLEM)
        energy = self.game.energy

        self._combine(main.Verb.FIX, golem, first, second)

        self.assertIn("cannot be combined again", self.game.shop_message)
        self.assertEqual(first.amount, main.MAGNITUDES.LANTERN_DRAWS * 4)
        self.assertTrue(self.game.owns_item(golem))
        self.assertEqual(self.game.energy, energy)

    def test_a_combined_block_is_golden_on_the_board_and_back_in_hand(self):
        golem = self._structure(main.Structure.GOLEM)
        build = dict(shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                     scorer_amount=30)
        first = main.Block(0, 0, **build)
        second = main.Block(1, 1, **build)
        self.game.grid[(0, 0)] = first
        self.game.grid[(1, 1)] = second

        self._combine(main.Verb.BREAK, golem, first, second)

        self.assertEqual(main.Quality.of(first), main.Quality.GOLDEN)
        self.assertTrue(self.game._item_name(first).startswith("Golden "))
        # The block is the board's, so taking it up keeps the tier on the item.
        self.game._unplace_block(first)
        items = [item for item in self.game.toolbox.items
                 if getattr(item, "kind", None) == "block"
                 and item.scorer == main.Scorer.CHIPS_ADD]
        self.assertEqual([main.Quality.of(item) for item in items],
                         [main.Quality.GOLDEN])

    def test_an_item_put_down_on_the_board_is_built_golden(self):
        piece = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 60, 40, "Rect +Chips",
                               quality=main.Quality.GOLDEN)
        self.game.toolbox.add(piece)
        self.game.ensure_board_cells()
        cell = self._item_cell(piece)

        self.game._equip_block(piece)
        self.game._place_block_at(*cell)

        block = self.game.grid.get(cell)
        self.assertIsNotNone(block)
        self.assertEqual(main.Quality.of(block), main.Quality.GOLDEN)
        self.assertTrue(self.game._item_name(block).startswith("Golden "))

    def test_a_combined_item_is_drawn_differently(self):
        rect = main.pygame.Rect(0, 0, 50, 50)
        plain_surface = main.pygame.Surface((50, 50))
        golden_surface = main.pygame.Surface((50, 50))
        gold = main.Quality.COLORS[main.Quality.GOLDEN]
        plain = main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=30)
        golden = main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=60,
                                                 quality=main.Quality.GOLDEN)

        main.ui.draw_shop_item(plain_surface, plain, rect)
        main.ui.draw_shop_item(golden_surface, golden, rect)

        self.assertEqual(tuple(golden_surface.get_at((38, 12))[:3]), gold)
        self.assertNotEqual(tuple(plain_surface.get_at((38, 12))[:3]), gold)

    def test_the_tier_survives_a_save(self):
        golem = self._structure(main.Structure.GOLEM)
        first, second = self._lantern(), self._lantern()
        self._combine(main.Verb.FIX, golem, first, second)

        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)

        kept = [action for action in fresh.actions
                if action.value == main.Action.LANTERN]
        self.assertEqual([main.Quality.of(action) for action in kept],
                         [main.Quality.GOLDEN])
        self.assertEqual(kept[0].amount, main.MAGNITUDES.LANTERN_DRAWS * 2)


class PackStructureTests(ToolCase):
    """One structure per pack: EVERY item in the game is obtainable.

    User request: "make all items in the game obtainable through structures.
    For example, add a new 'tool pack' that gives tools. for each pack, create a
    new structure." Each pack type has a structure of its own, and opening it
    with the right tool really deals that pack's goods.
    """

    # What a structure's pack deals, per pack type (see Shop._roll_pack_option).
    # A SCORER pack may also deal a READY-MADE BLOCK: the run roles (Start,
    # Finish) are not parts, so they come as blocks (see Shop._scorer_offer).
    WARES = {
        main.Pack.SHAPE: (main.Component.SHAPE,),
        main.Pack.EFFECT: (main.Component.EFFECT,),
        main.Pack.SCORER: (main.Component.SCORER, "block"),
        main.Pack.PART: (main.Component.SHAPE, main.Component.EFFECT,
                         main.Component.SCORER),
        main.Pack.BLOCK: ("block",),
        main.Pack.CARD: ("card",),
        main.Pack.ACTION: ("action",),
        main.Pack.RESOURCE: ("resource",),
        main.Pack.TOOL: ("tool", "passive"),
    }

    def _structure_for(self, pack_type):
        """The structure that hands this pack type over (see Structure.RESULTS)."""
        for structure in main.Structure.ORDER:
            for verb in main.Structure.verbs(structure):
                if main.Structure.result(structure, verb) == ("pack", pack_type):
                    return structure, verb
        return None, None

    def test_every_pack_has_a_structure_of_its_own(self):
        for pack_type in main.Pack.ORDER:
            with self.subTest(pack=main.Pack.name(pack_type)):
                structure, verb = self._structure_for(pack_type)
                self.assertIsNotNone(structure,
                                     f"no structure hands over a "
                                     f"{main.Pack.name(pack_type)}")
                self.assertIn(verb, main.Verb.ORDER)
                # ...and the structure says so in its own description.
                self.assertIn(main.Pack.name(pack_type),
                              main.Structure.description(structure))

    def test_every_structure_opens_with_a_tool_that_exists(self):
        for structure in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(structure)):
                self.assertTrue(main.Structure.verbs(structure))
                for verb in main.Structure.verbs(structure):
                    self.assertIsNotNone(main.Tool.for_verb(verb))

    def test_every_structure_is_offered_by_some_level(self):
        offered = {value for level in main.LEVELS
                   for value in level.authored_structures}
        self.assertEqual(offered, set(main.Structure.ORDER))
        # The last level knows every one of them, so its bonus slots can deal
        # any structure in the game (see Shop._level_structures).
        last = main.LEVELS[-1]
        self.assertEqual(sorted(set(last.authored_structures)),
                         sorted(main.Structure.ORDER))

    def test_opening_each_pack_structure_deals_that_packs_goods(self):
        self.game.energy = 99          # one opening per structure, all in a row
        for pack_type in main.Pack.ORDER:
            with self.subTest(pack=main.Pack.name(pack_type)):
                structure, verb = self._structure_for(pack_type)
                self.game.shop.items = [
                    item for item in self.game.shop.items
                    if not getattr(item, "is_level_structure", False)]
                target = self._structure(structure)

                self._use_tool(verb, target)

                packs = [item for item in self._packs()
                         if item.pack_type == pack_type]
                self.assertEqual(len(packs), 1)
                pack = packs[0]
                self.assertIn(pack.size, main.Pack.SIZE_ORDER)
                self.assertTrue(pack.options)
                kinds = {getattr(option, "kind", None) for option in pack.options}
                expected = self.WARES.get(pack_type)
                if expected is None:       # RANDOM deals anything at all
                    allowed = set().union(*self.WARES.values())
                    self.assertTrue(kinds <= allowed,
                                    f"a Random Pack dealt {kinds}")
                    continue
                self.assertTrue(kinds <= set(expected),
                                f"{kinds} is not what a "
                                f"{main.Pack.name(pack_type)} deals")

    def test_the_tool_pack_structure_hands_over_a_tool(self):
        # The user's own example: "add a new 'tool pack' that gives tools".
        shed = self._structure(main.Structure.SHED)
        self.game.energy = 3

        self._use_tool(main.Verb.REVEAL, shed)

        pack = self._packs()[0]
        self.assertEqual(pack.pack_type, main.Pack.TOOL)
        self.assertTrue({option.kind for option in pack.options}
                        <= {"tool", "passive"})
        self.assertEqual(main.Pack.name(main.Pack.TOOL), "Tool Pack")


class OneShotToolTests(ToolCase):
    """The one-shot tools: the brick and the match (see Tool / Keyword).

    User request: add an item "brick" (0 energy): break or dig, consume; and an
    item "match" (1 energy): reveal, discard this item and draw an item.
    """

    def _tool_item(self, value):
        item = main.ToolItem(value, main.Tool.PRICES[value])
        self.game.toolbox.add(item)
        self.game.ensure_board_cells()
        return self._seat(item)

    def _deck(self, count=5):
        for _ in range(count):
            piece = main.Component.shape_component(main.Shape.SLOPE)
            self.game.toolbox.add(piece)
            self.game._to_deck(piece)
        return len(self.game.deck_items())

    def test_a_brick_opens_for_no_energy_and_is_used_up(self):
        brick = self._tool_item(main.Tool.BRICK)
        mirror = self._structure(main.Structure.MIRROR)
        energy = self.game.energy

        self._use_tool(main.Verb.BREAK, mirror, brick)

        self.assertEqual(self.game.energy, energy)         # 0 energy
        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.STRENGTH])
        self.assertFalse(self.game.owns_item(brick))       # consume

    def test_a_brick_uses_whichever_verb_its_structure_answers_to(self):
        # A brick is "break, dig": it breaks a mirror and digs a pit.
        pit = self._structure(main.Structure.PIT)
        brick = self._tool_item(main.Tool.BRICK)

        self._use_tool(main.Verb.DIG, pit, brick)

        self.assertIn("dug", self.game.shop_message)
        packs = [item for item in self.game.toolbox.items
                 if getattr(item, "kind", None) == "pack"]
        self.assertEqual([pack.pack_type for pack in packs], [main.Pack.PART])
        self.assertFalse(self.game.owns_item(brick))

    def test_a_match_reveals_then_burns_out_for_an_item(self):
        pool = self._structure(main.Structure.CRYSTAL_POOL)
        match = self._tool_item(main.Tool.MATCH)
        deck = self._deck()
        energy = self.game.energy

        self._use_tool(main.Verb.REVEAL, pool, match)

        self.assertEqual(self.game.energy, energy - 1)     # 1 energy
        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.CLEANSING])
        self.assertFalse(self.game.owns_item(match))       # consume
        self.assertEqual(len(self.game.deck_items()), deck - 1)   # draw 1
        self.assertIn("drew", self.game.shop_message)

    def test_a_used_up_tool_counts_as_a_discard(self):
        # It leaves through the ordinary discard door, so the run's count moves
        # (the Trash Can card pays for it).
        mirror = self._structure(main.Structure.MIRROR)
        brick = self._tool_item(main.Tool.BRICK)
        self.assertEqual(self.game.discarded_items_run, 0)

        self._use_tool(main.Verb.BREAK, mirror, brick)

        self.assertEqual(self.game.discarded_items_run, 1)

    def test_a_match_still_opens_with_nothing_to_draw(self):
        pool = self._structure(main.Structure.CRYSTAL_POOL)
        match = self._tool_item(main.Tool.MATCH)
        self.assertEqual(self.game.deck_items(), [])

        self._use_tool(main.Verb.REVEAL, pool, match)

        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.CLEANSING])
        self.assertFalse(self.game.owns_item(match))

    def test_the_four_starters_are_never_used_up(self):
        for tool in main.Tool.STARTERS:
            self.assertFalse(main.Tool.consumes(tool))
            self.assertEqual(main.Tool.draws(tool), 0)
            self.assertEqual(main.Tool.energy(tool), 1)
        pit = self._structure(main.Structure.PIT)
        shovel = self._tool(main.Verb.DIG)

        self._use_tool(main.Verb.DIG, pit, shovel)

        self.assertTrue(self.game.owns_item(shovel))

    def test_a_pit_revealed_hands_over_a_tool_pack(self):
        # The one-shot tools and the passives come out of a TOOL pack, and a pit
        # shows you what else fell into it when it is lit up.
        pit = self._structure(main.Structure.PIT)
        flashlight = self._tool(main.Verb.REVEAL)

        self._use_tool(main.Verb.REVEAL, pit, flashlight)

        packs = [item for item in self.game.toolbox.items
                 if getattr(item, "kind", None) == "pack"]
        self.assertEqual([pack.pack_type for pack in packs], [main.Pack.TOOL])
        options = packs[0].options
        self.assertTrue(options)
        for option in options:
            self.assertIn(option.kind, ("tool", "passive"))


class StructureToolTests(ToolCase):
    """Using a tool on a structure: the click flow and its refusals."""

    def test_digging_a_pit_yields_a_part_pack(self):
        pit = self._structure(main.Structure.PIT)

        self._use_tool(main.Verb.DIG, pit)

        self.assertIn("dug", self.game.shop_message)
        packs = self._packs()
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0].pack_type, main.Pack.PART)
        # The structure is spent: it is gone and nothing is left on its square.
        self.assertFalse(self.game.owns_item(pit))
        self.assertIsNone(self._item_cell(pit))

    def test_revealing_a_crystal_pool_yields_cleansing(self):
        pool = self._structure(main.Structure.CRYSTAL_POOL)

        self._use_tool(main.Verb.REVEAL, pool)

        self.assertIn("revealed", self.game.shop_message)
        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.CLEANSING])
        self.assertFalse(self.game.owns_item(pool))

    def test_digging_a_crystal_pool_yields_cleansing_too(self):
        pool = self._structure(main.Structure.CRYSTAL_POOL)

        self._use_tool(main.Verb.DIG, pool)

        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.CLEANSING])

    def test_fixing_a_mirror_yields_recognition(self):
        mirror = self._structure(main.Structure.MIRROR)

        self._use_tool(main.Verb.FIX, mirror)

        self.assertIn("fixed", self.game.shop_message)
        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.RECOGNITION])

    def test_breaking_a_mirror_yields_strength(self):
        mirror = self._structure(main.Structure.MIRROR)

        self._use_tool(main.Verb.BREAK, mirror)

        self.assertIn("broken", self.game.shop_message)
        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.STRENGTH])

    def test_a_wrong_verb_does_nothing_at_all(self):
        # "a pit cannot be broken": the tool is turned away, the structure is
        # left standing, and nothing is spent.
        pit = self._structure(main.Structure.PIT)

        self._use_tool(main.Verb.BREAK, pit)

        self.assertIn("cannot be broken", self.game.shop_message)
        self.assertTrue(self.game.owns_item(pit))
        self.assertIsNotNone(self._item_cell(pit))
        self.assertEqual(self.game.actions, [])
        self.assertEqual(self._packs(), [])

    def test_a_tool_needs_exactly_one_structure(self):
        pit = self._structure(main.Structure.PIT)
        shovel = self._tool(main.Verb.DIG)
        self._click(self._item_pos(shovel))
        self._click(self._item_pos(pit))
        self.assertTrue(self.game._apply_tool())
        # ...and with no structure selected there is nothing to open.
        self.assertFalse(self.game._apply_tool())
        self.assertIn("needs 1 structure", self.game.shop_message)
        self.assertEqual(self.game.shop_message,
                         f"{shovel.name} needs 1 structure — 0 selected")

    def test_two_structures_are_one_too_many(self):
        pit = self._structure(main.Structure.PIT)
        pool = self._structure(main.Structure.CRYSTAL_POOL, cell=(5,
                                                                 main.SHOP_ITEM_ROW))
        shovel = self._tool(main.Verb.DIG)
        self._click(self._item_pos(shovel))
        self._click(self._item_pos(pit))
        self._click(self._item_pos(pool))

        self.assertFalse(self.game._apply_tool())

        self.assertIn("needs 1 structure — 2 selected", self.game.shop_message)
        self.assertTrue(self.game.owns_item(pit))
        self.assertTrue(self.game.owns_item(pool))

    def test_a_tool_needs_selecting_first(self):
        self.assertIsNone(self.game.selected_tool)
        self.assertFalse(self.game._apply_tool())
        self.assertEqual(self.game.shop_message, "Select a tool first")

    def test_a_tool_is_never_spent(self):
        pit = self._structure(main.Structure.PIT)
        shovel = self._tool(main.Verb.DIG)

        self._use_tool(main.Verb.DIG, pit)

        self.assertTrue(self.game.owns_item(shovel))
        self.assertIsNotNone(self._item_cell(shovel))
        # ...so it opens a second structure just as well.
        pool = self._structure(main.Structure.CRYSTAL_POOL, cell=(5,
                                                                 main.SHOP_ITEM_ROW))
        self._use_tool(main.Verb.REVEAL, pool)
        self.assertEqual([action.value for action in self.game.actions],
                         [main.Action.CLEANSING])

    def test_the_reward_appears_where_the_structure_stood(self):
        # "remove the structure and put the reward in its place" (user request):
        # every kind of reward takes the square the structure was standing on.
        cases = ((main.Structure.PIT, main.Verb.DIG, "pack"),
                 (main.Structure.CRYSTAL_POOL, main.Verb.REVEAL, "action"),
                 (main.Structure.MIRROR, main.Verb.FIX, "action"))
        for index, (value, verb, kind) in enumerate(cases):
            with self.subTest(structure=main.Structure.name(value)):
                structure = self._structure(value,
                                            cell=(4 + index, main.SHOP_ITEM_ROW))
                home = self._item_cell(structure)
                before = set(self.game.owned_items())

                self._use_tool(verb, structure)

                reward = [item for item in self.game.owned_items()
                          if item not in before]
                self.assertEqual(len(reward), 1)
                self.assertEqual(getattr(reward[0], "kind", None), kind)
                self.assertEqual(self._item_cell(reward[0]), home)
                self.assertIs(self.game.item_at_cell(home), reward[0])
                self.assertIsNone(self.game.item_cell(structure))

    def test_the_reward_does_not_go_to_the_first_free_square(self):
        # The reward replaces the structure, so it lands on the structure's own
        # square even when an EARLIER square is free: gaining an item normally
        # deals it the first free one (see _on_item_gained), which is what a
        # structure's reward used to get.
        pit = self._structure(main.Structure.PIT, cell=(4, main.SHOP_ITEM_ROW))
        hole = self._item_cell(pit)          # the first free square, as dealt
        self.assertIsNotNone(hole)
        # Move the pit to a LATER square, so the one it came from is free and
        # comes first in the layout's reading order (see _free_board_cell).
        claimed = {self._item_cell(item) for item in self.game.owned_items()}
        home = self.game._free_board_cell(claimed)
        self.assertIsNotNone(home)
        self.assertNotEqual(home, hole)
        self.game.set_item_cell(pit, home)

        self._use_tool(main.Verb.DIG, pit)

        packs = self._packs()
        self.assertEqual(len(packs), 1)
        self.assertEqual(self._item_cell(packs[0]), home)
        self.assertNotEqual(self._item_cell(packs[0]), hole)

    def _start_level_with_structures(self, run_number=0):
        """Lay out a level and return the structures it places.

        Structures are part of the LEVEL now (user request: "add structures as
        part of the level"), so they come from the level being played rather
        than from a shop shelf. The level is laid out without starting its run,
        so the player's items stay seated where the tests click them.
        """
        self.game.unlocked_cells = set()
        self.game.run_number = run_number
        level = self.game.current_level()
        self.game._open_level_region(level.cells)
        self.game._place_level_structures(level)
        self.game.ensure_board_cells()
        structures = [item for item in self.game.shop.items
                      if getattr(item, "is_level_structure", False)]
        self.assertTrue(structures)
        return structures

    def test_a_levels_structure_stands_on_the_levels_own_square(self):
        # The level puts its structures on its own squares: they are free, wear
        # no padlock and belong to nobody until a tool opens one.
        structures = self._start_level_with_structures()
        level = self.game.current_level()
        self.assertEqual(len(structures), len(level.structure_spawns))
        for item in structures:
            self.assertEqual(item.price, 0)
            self.assertIn(self._item_cell(item), self.game.unlocked_cells)
            self.assertFalse(self.game.owns_item(item))
            self.assertIn(item, self.game.shop.items)

    def test_a_structure_can_always_be_moved(self):
        # User request: "make sure they can always be moved." A structure is an
        # offer standing on the board, so it is picked up and put down like any
        # other item, and keeps the square the player chose.
        structures = self._start_level_with_structures()
        offer = structures[0]
        home = self._item_cell(offer)
        free = next(cell for cell in sorted(self.game.unlocked_cells)
                    if self.game.item_at_cell(cell) is None)

        self._click(self._item_pos(offer))
        self._click(self._grid_pos(*free))

        self.assertEqual(self._item_cell(offer), free)
        self.assertIn("Moved", self.game.shop_message)
        # It is still the level's, still free, and still openable where it lies.
        self.assertIn(offer, self.game.shop.items)
        self.assertFalse(self.game.owns_item(offer))

        # ...and back again: a move puts the item down, so it is picked up again
        # the way the player would.
        self._click(self._item_pos(offer))
        self._click(self._grid_pos(*home))
        self.assertEqual(self._item_cell(offer), home)

    def test_a_levels_structure_is_free_to_open_where_it_lies(self):
        # No purchase: a tool opens the level's structure where it stands, and
        # the reward replaces it on that square.
        self.game.cash = 0
        structures = self._start_level_with_structures(3)   # level 4: crystal pool
        offer = structures[0]
        home = self._item_cell(offer)
        self.assertIsNotNone(home)

        # Right-clicking it buys nothing: it is already free to use.
        self._right_click(self._item_pos(offer))
        self.assertIn("free", self.game.shop_message)
        self.assertFalse(self.game.owns_item(offer))
        self.assertEqual(self._item_cell(offer), home)

        verb = main.Structure.verbs(offer.value)[0]
        self._use_tool(verb, offer)

        self.assertFalse(self.game.owns_item(offer))
        self.assertNotIn(offer, self.game.shop.items)
        reward = [item for item in self.game.owned_items()
                  if getattr(item, "kind", None) in ("pack", "action")]
        self.assertEqual(len(reward), 1)
        self.assertEqual(self._item_cell(reward[0]), home)

    def test_opening_a_level_structure_costs_no_cash_and_one_energy(self):
        # End to end, the way a player does it: click the tool, click the
        # level's structure, press S. Nothing is bought, so the only thing an
        # opening costs is 1 energy.
        self.game.cash = 0
        structures = self._start_level_with_structures()
        pits = [item for item in structures if item.value == main.Structure.PIT]
        self.assertTrue(pits)
        home = self._item_cell(pits[0])

        self._use_tool(main.Verb.DIG, pits[0])

        self.assertIn("dug", self.game.shop_message)
        self.assertEqual(self.game.cash, 0)
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)
        packs = self._packs()
        self.assertEqual(len(packs), 1)
        self.assertEqual(self._item_cell(packs[0]), home)

    def _cleansing(self, version=1):
        action = main.ActionItem(main.Action.CLEANSING,
                                 main.Action.PRICES[main.Action.CLEANSING],
                                 version=version)
        self.game.actions.append(action)
        return action

    def _apply(self, action, subject):
        self.game.selection = [subject]
        self.game.selected_action = action
        self.game.selected_action_subject = subject
        return self.game._apply_action()

    def _cleansing_block(self):
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.PISTON,
                               main.Scorer.CHIPS_ADD, 20, 40, "Pipe",
                               effects=[main.Effect.PISTON],
                               effect_amounts={main.Effect.PISTON: 400})
        self.game.toolbox.add(block)
        return block

    def test_cleansing_data_lives_in_components(self):
        self.assertIn(main.Action.CLEANSING, main.Action.ORDER)
        self.assertEqual(main.Action.name(main.Action.CLEANSING), "Cleansing")
        self.assertTrue(main.Action.comment(main.Action.CLEANSING))
        self.assertIn("by 1.5", main.Action.description(main.Action.CLEANSING, 1))
        self.assertIn("by 2.5", main.Action.description(main.Action.CLEANSING, 2))
        self.assertIn(main.Action.CLEANSING, main.Action.PRICES)
        self.assertIn(main.Action.CLEANSING, main.Action.COLORS)
        self.assertIn(main.Action.CLEANSING, main.Action.GLYPHS)

    def test_cleansing_raises_a_blocks_scorer_and_every_effect(self):
        action = self._cleansing()
        block = self._cleansing_block()

        self.assertTrue(self._apply(action, block))

        self.assertEqual(block.scorer_amount, 30)                 # 20 * 1.5
        self.assertEqual(block.effect_amounts[main.Effect.PISTON], 600)  # 400
        self.assertEqual(self.game.actions, [])                   # consumed

    def test_cleansing_v2_is_two_and_a_half_times(self):
        action = self._cleansing(version=2)
        block = self._cleansing_block()

        self.assertTrue(self._apply(action, block))

        self.assertEqual(block.scorer_amount, 50)                 # 20 * 2.5
        self.assertEqual(block.effect_amounts[main.Effect.PISTON], 1000)

    def test_cleansing_works_on_a_loose_effect_and_scorer(self):
        effect = main.Component.effect_component(main.Effect.PISTON)
        effect.amount = 40
        self.game.toolbox.add(effect)
        self.assertTrue(self._apply(self._cleansing(), effect))
        self.assertEqual(effect.amount, 60)

        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD)
        scorer.amount = 18
        self.game.toolbox.add(scorer)
        self.assertTrue(self._apply(self._cleansing(), scorer))
        self.assertEqual(scorer.amount, 27)

    def test_cleansing_refuses_a_piece_with_no_magnitude(self):
        shape = main.Component.shape_component(main.Shape.PIPE)
        self.game.toolbox.add(shape)
        action = self._cleansing()

        self.assertFalse(self._apply(action, shape))

        # A shape is not something an action can be aimed at at all, so nothing
        # happens and the action is not spent.
        self.assertIn("needs 1 target", self.game.shop_message)
        self.assertEqual(self.game.actions, [action])   # not consumed

    def test_cleansing_refuses_a_card(self):
        card = main.CardItem(main.Card.GARDEN, 36)
        self.game.cards.append(card)
        action = self._cleansing()

        self.assertFalse(self._apply(action, card))

        self.assertIn("block, effect or scorer", self.game.shop_message)
        self.assertEqual(self.game.actions, [action])


class EnergyTests(ToolCase):
    """ENERGY: the run's budget for the four tools.

    "give the player an energy bar, located in the top bar. the player's max
    energy is 3, and energy resets to max each run. using any of flashlight,
    screwdriver, shovel, or hammer consumes 1 energy" (user request).
    """

    def test_a_new_run_starts_with_full_energy(self):
        self.assertEqual(main.MAX_ENERGY, 3)
        self.assertEqual(self.game.max_energy, main.MAX_ENERGY)
        self.assertEqual(self.game.energy, main.MAX_ENERGY)

    def test_each_opening_spends_one_energy(self):
        pits = [self._structure(main.Structure.PIT,
                                cell=(4 + index, main.SHOP_ITEM_ROW))
                for index in range(main.MAX_ENERGY)]

        for spent, pit in enumerate(pits, start=1):
            with self.subTest(spent=spent):
                self._use_tool(main.Verb.DIG, pit)
                self.assertEqual(self.game.energy, main.MAX_ENERGY - spent)
                self.assertFalse(self.game.owns_item(pit))

    def test_a_spent_out_run_refuses_the_next_tool_use(self):
        pits = [self._structure(main.Structure.PIT,
                                cell=(4 + index, main.SHOP_ITEM_ROW))
                for index in range(main.MAX_ENERGY + 1)]
        for pit in pits[:-1]:
            self._use_tool(main.Verb.DIG, pit)
        self.assertEqual(self.game.energy, 0)

        last = pits[-1]
        self._use_tool(main.Verb.DIG, last)

        self.assertIn("Out of energy", self.game.shop_message)
        self.assertEqual(self.game.energy, 0)
        # Nothing happened: the pit is still there, and no pack was handed over.
        self.assertTrue(self.game.owns_item(last))
        self.assertEqual(len(self._packs()), main.MAX_ENERGY)

    def test_a_refused_use_costs_no_energy(self):
        # A pit cannot be broken, and a tool with no structure selected has
        # nothing to open: nothing happened, so nothing is spent.
        pit = self._structure(main.Structure.PIT)
        self._use_tool(main.Verb.BREAK, pit)
        self.assertEqual(self.game.energy, main.MAX_ENERGY)

        self._click(self._item_pos(self._tool(main.Verb.DIG)))
        self.assertFalse(self.game._apply_tool())
        self.assertEqual(self.game.energy, main.MAX_ENERGY)

    def _place_start_block(self):
        """Put the Start block on the board, so a run can be started."""
        start = next(item for item in self.game.owned_items()
                     if getattr(item, "scorer", None) == main.Scorer.START)
        self.game._equip_block(start)
        self.game._place_block_at(3, 3)

    def test_energy_refills_at_the_start_of_every_run(self):
        self._place_start_block()
        self._use_tool(main.Verb.DIG, self._structure(main.Structure.PIT))
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)

        # Starting a run (T) refills it: the run that was thrown away does not
        # keep what it spent.
        self._press(main.pygame.K_t)
        self.assertEqual(self.game.energy, main.MAX_ENERGY)

        # ...and restarting the run (R) hands the same budget back.
        self._use_tool(main.Verb.DIG, self._structure(main.Structure.PIT))
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)
        self._press(main.pygame.K_r)
        self.assertEqual(self.game.energy, main.MAX_ENERGY)

        # A retry of a finished run is a do-over too.
        self._use_tool(main.Verb.DIG, self._structure(main.Structure.PIT))
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.energy, main.MAX_ENERGY)

    def test_energy_saves_and_loads(self):
        self._use_tool(main.Verb.DIG, self._structure(main.Structure.PIT))
        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)

        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)

        self.assertEqual(fresh.energy, main.MAX_ENERGY - 1)
        self.assertEqual(fresh.max_energy, main.MAX_ENERGY)

    def test_a_save_without_energy_loads_a_full_bar(self):
        data = save_system._save_data(self.game)
        data.pop("energy")
        fresh = main.Game()
        save_system._load_save_data(fresh, data, 1)
        self.assertEqual(fresh.energy, main.MAX_ENERGY)


class EnergyBarTests(GameTestCase):
    """The bar itself: the pips, where it sits, and what hovering it says."""

    def test_the_bar_is_in_the_top_bar_and_one_pip_per_energy(self):
        rect = main.ENERGY_BAR_RECT
        self.assertLessEqual(rect.bottom, main.TOP_BAR_HEIGHT)
        pips = main.ui.energy_pip_rects(self.game)
        self.assertEqual(len(pips), main.MAX_ENERGY)
        for pip in pips:
            self.assertTrue(rect.contains(pip), pip)
        for left, right in zip(pips, pips[1:]):
            self.assertLess(left.right, right.left)   # no overlap
        # It sits under the cash captions and clear of the bar's buttons.
        self.assertGreater(rect.y, main.ui.last_run_cash_rect(self.game).bottom)
        for other in (main.DECK_BUTTON_RECT, main.BOARD_UNIT_BUTTON_RECT,
                      main.SCORE_PANEL_RECT, main.TRIAL_BOX_RECT):
            self.assertFalse(rect.colliderect(other), other)

    def test_the_label_reads_the_pips(self):
        self.assertEqual(main.ui.energy_bar_label(self.game), "ENERGY 3/3")
        self.game.energy = 1
        self.assertEqual(main.ui.energy_bar_label(self.game), "ENERGY 1/3")

    def test_the_pips_draw_charged_and_spent(self):
        self.game.energy = 2
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_energy_bar(self.game)
        pips = main.ui.energy_pip_rects(self.game)
        for pip, charged in zip(pips, (True, True, False)):
            pixel = self.game.screen.get_at(pip.center)
            if charged:
                self.assertEqual(tuple(pixel)[:3], main.ENERGY_COLOR)
            else:
                self.assertNotEqual(tuple(pixel)[:3], main.ENERGY_COLOR)

    def test_hovering_the_bar_explains_energy(self):
        item, source = self.game._info_target_at(
            main.ui.energy_bar_rect(self.game).center)
        self.assertIs(item, main.ENERGY_READOUT)
        self.assertEqual(source, "energy")
        rows = dict(self.game._describe_item(item))
        self.assertIn(f"{self.game.energy} of {self.game.max_energy}",
                      rows["Energy"])
        self.assertIn("start of every run", rows["Refills"])
        self.assertIn(f"{self.game.energy} opening",
                      self.game._action_hint(item, source))
        self.game.energy = 1
        self.assertIn("1 opening", self.game._action_hint(item, source))
        self.game.energy = 0
        self.assertIn("No energy left",
                      self.game._action_hint(item, source))


class StructureSaveTests(GameTestCase):
    """A structure, a tool and a pack survive a save/load round trip."""

    def test_structures_and_tools_save_and_load(self):
        structure = main.StructureItem(main.Structure.MIRROR,
                                       main.Structure.PRICES[main.Structure.MIRROR])
        self.game.toolbox.add(structure)
        self.game.ensure_board_cells()

        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)

        structures = [item for item in fresh.toolbox.items
                      if getattr(item, "kind", None) == "structure"]
        self.assertEqual([item.value for item in structures],
                         [main.Structure.MIRROR])
        self.assertEqual(structures[0].price,
                         main.Structure.PRICES[main.Structure.MIRROR])
        tools = [item for item in fresh.toolbox.items
                 if getattr(item, "kind", None) == "tool"]
        self.assertEqual(sorted(tool.value for tool in tools),
                         sorted(main.Tool.STARTERS))
        self.assertEqual(sorted(tool.verb for tool in tools),
                         sorted(main.Verb.ORDER))
