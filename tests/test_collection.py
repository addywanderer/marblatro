"""The collection, and the icons every item wears.

User request: "make sure all items are in the collection, if they aren't
already. give all items an icon if they don't already have one."

A codex entry is one SECTION per kind of item (see collection._empty): the
components a block is made of, whole cards, match groups, actions, packs,
trials, and the three kinds that are items in their own right -- TOOLS, the
unplayable PASSIVES, and the STRUCTURES a level stands on the board. These
tests pin down that nothing is missing from that list, that every kind is
revealed by doing the thing that hands it over, and that every value in every
table draws a picture of its own rather than a letter standing in for one.
"""

import pygame

from tests.game_test_case import *  # noqa: F401,F403


class CollectionCoverageTests(GameTestCase):
    """Every item is in the collection, and each is revealed by obtaining one."""

    # --- helpers ------------------------------------------------------------

    def _entries(self):
        return self.game._collection_entries()

    def _values_by_kind(self):
        found = {}
        for kind, value, name, desc, has_icon, discovered in self._entries():
            found.setdefault(kind, []).append(value)
        return found

    def _free_cell(self):
        game = self.game
        return next(c for c in sorted(game.unlocked_cells)
                    if game.item_at_cell(c) is None and c not in game.grid)

    def _tool(self, verb):
        return next(item for item in self.game.toolbox.items
                    if getattr(item, "kind", None) == "tool" and item.verb == verb)

    def _open_structure(self, value):
        """Stand a structure on the board and open it with the player's clicks."""
        game = self.game
        structure = main.StructureItem(value, main.Structure.PRICES[value])
        game.toolbox.add(structure)
        game.ensure_board_cells()
        verb = main.Structure.verbs(value)[0]
        tool = self._tool(verb)
        game._clear_toolbox_selection()
        game.energy = 99
        self._click(self._item_pos(tool))
        self._click(self._item_pos(structure))
        self._press(main.pygame.K_s)
        return structure

    # --- every kind of item is a section ------------------------------------

    def test_every_kind_of_item_has_a_section_of_its_own(self):
        kinds = self._values_by_kind()
        for kind in ("card", "match_group", "action", "shape", "effect",
                     "scorer", "tool", "passive", "structure", "pack", "trial"):
            with self.subTest(kind=kind):
                self.assertIn(kind, kinds, "this kind can never be seen")

    def test_every_tool_is_listed_once(self):
        listed = self._values_by_kind()["tool"]
        self.assertEqual(sorted(listed), sorted(main.Tool.ORDER))

    def test_every_passive_is_listed_once(self):
        listed = self._values_by_kind()["passive"]
        self.assertEqual(sorted(listed), sorted(main.Passive.ORDER))

    def test_every_structure_is_listed_once(self):
        listed = self._values_by_kind()["structure"]
        self.assertEqual(sorted(listed), sorted(main.Structure.ORDER))

    def test_every_listed_entry_names_and_describes_its_item(self):
        self.game._unlock_entire_collection()
        for kind, value, name, desc, has_icon, discovered in self._entries():
            with self.subTest(entry=f"{kind}:{value}"):
                self.assertTrue(discovered)
                self.assertNotEqual(name, "???")
                self.assertNotEqual(desc, "???")
                self.assertTrue(has_icon)

    def test_an_unseen_entry_says_question_marks(self):
        self.assertFalse(collection.is_structure_discovered(main.Structure.RIFT))
        for kind, value, name, desc, has_icon, discovered in self._entries():
            if kind == "structure" and value == main.Structure.RIFT:
                self.assertEqual(name, "???")
                self.assertEqual(desc, "???")
                self.assertFalse(discovered)

    # --- what reveals what ---------------------------------------------------

    def test_the_starter_tools_are_known_from_the_first_game(self):
        # Every game deals all four starters into the first hand, so the player
        # has seen them before the codex is ever opened.
        for value in main.Tool.STARTERS:
            with self.subTest(tool=main.Tool.name(value)):
                self.assertTrue(collection.is_tool_discovered(value))
        self.assertFalse(collection.is_tool_discovered(main.Tool.BRICK))

    def test_keeping_a_tool_from_a_pack_reveals_it(self):
        option = main.ToolItem(main.Tool.BRICK)
        self.assertFalse(collection.is_tool_discovered(main.Tool.BRICK))

        self.game._receive_pack_item(option)

        self.assertTrue(collection.is_tool_discovered(main.Tool.BRICK))
        self.assertTrue(any(popup.title == "New tool"
                            and popup.description == "Brick"
                            for popup in self.game.popups))

    def test_keeping_a_passive_from_a_pack_reveals_it(self):
        option = main.PassiveItem(main.Passive.CONCRETE,
                                  main.Passive.PRICES[main.Passive.CONCRETE])
        self.assertFalse(collection.is_passive_discovered(main.Passive.CONCRETE))

        self.game._receive_pack_item(option)

        self.assertTrue(collection.is_passive_discovered(main.Passive.CONCRETE))
        self.assertTrue(any(popup.title == "New item"
                            and popup.description == "Concrete"
                            for popup in self.game.popups))

    def test_opening_a_structure_reveals_it(self):
        value = main.Structure.LIBRARY
        self.assertFalse(collection.is_structure_discovered(value))

        self._open_structure(value)

        self.assertTrue(collection.is_structure_discovered(value))
        self.assertTrue(any(popup.title == "New structure"
                            and popup.description == main.Structure.name(value)
                            for popup in self.game.popups))

    def test_opening_the_same_structure_twice_only_pops_once(self):
        value = main.Structure.QUARRY
        self._open_structure(value)
        self.game.popups = []

        self._open_structure(value)

        self.assertFalse(any(popup.title == "New structure"
                             for popup in self.game.popups))

    def test_a_discovery_survives_a_reload(self):
        self.game._receive_pack_item(main.ToolItem(main.Tool.MATCH))
        self.game._receive_pack_item(main.PassiveItem(
            main.Passive.CONCRETE, main.Passive.PRICES[main.Passive.CONCRETE]))
        self._open_structure(main.Structure.MINT)

        collection.reset()          # the next game reads the file again

        self.assertTrue(collection.is_tool_discovered(main.Tool.MATCH))
        self.assertTrue(collection.is_passive_discovered(main.Passive.CONCRETE))
        self.assertTrue(collection.is_structure_discovered(main.Structure.MINT))

    def test_the_unlock_button_reveals_every_item_kind(self):
        self.game._unlock_entire_collection()
        for value in main.Tool.ORDER:
            self.assertTrue(collection.is_tool_discovered(value))
        for value in main.Passive.ORDER:
            self.assertTrue(collection.is_passive_discovered(value))
        for value in main.Structure.ORDER:
            self.assertTrue(collection.is_structure_discovered(value))

    # --- the screen ----------------------------------------------------------

    def test_the_codex_draws_every_entry_revealed(self):
        self.game._unlock_entire_collection()
        self.game.collection_scroll = 0
        main.ui.draw_collection(self.game)
        self.assertGreater(len(self._entries()), 200)


class CollectionGroupBoxTests(GameTestCase):
    """Every codex cell says which GROUP its entry is in, and says it short.

    User request: "add a box in each entry of the collection that shows which
    group that item is in (without the group's description)." The box lives in
    the cell's bottom corner and carries the family's name ALONE
    (ui.draw_collection_group) — the info box's badge prints the family's line
    under that name (ui._draw_group_badge), and a cell has no room for it.
    """

    def _index_of(self, kind, value):
        for index, entry in enumerate(self.game._collection_entries()):
            if entry[0] == kind and entry[1] == value:
                return index
        self.fail(f"no {kind} entry for {value}")

    def _drawn_box(self, cell, group, discovered=True):
        """Draw one box on a blank screen and return (its rect, the surface)."""
        self.game.screen.fill((0, 0, 0))
        main.ui.draw_collection_group(self.game, cell, group, discovered)
        return main.ui.collection_group_rect(self.game, cell, group)

    def test_every_entry_shows_a_box(self):
        kinds = {entry[0] for entry in self.game._collection_entries()}
        for kind in kinds:
            with self.subTest(kind=kind):
                self.assertIn(main.ui.collection_entry_group(kind),
                              main.Group.ORDER)
        # A trial is a way to play a run, not an item: its box says so...
        self.assertEqual(main.ui.collection_entry_group("trial"),
                         main.Group.TRIAL)
        # ...and something that is neither has no box at all.
        self.assertIsNone(main.ui.collection_entry_group("nonsense"))

    def test_cards_actions_and_tools_share_one_box(self):
        # User request: "join together cards, tools, and actions into one group
        # called 'cards'" — so all four entry kinds name the one family, and a
        # match-group entry (the cards built on that group) names it too.
        groups = {kind: main.ui.collection_entry_group(kind)
                  for kind in ("card", "match_group", "action", "tool")}

        self.assertEqual(set(groups.values()), {main.Group.CARDS})
        self.assertEqual(main.Group.name(main.Group.CARDS), "Cards")

    def test_the_box_carries_the_name_and_not_the_family_line(self):
        cell = main.ui.collection_entry_rect(0)
        group = main.Group.CARDS

        box = self._drawn_box(cell, group)

        # Only the name fits: the box is shorter than the info box's badge needs
        # just to write the name, before it starts on the family's line.
        self.assertEqual(box.height, main.ui.COLLECTION_GROUP_H)
        self.assertLess(box.height, main.ui.group_badge_height(("CARDS", [])))
        # ...and what it drew is the name in the family's colour, with none of
        # the grey the description under it would have been drawn in.
        colour = main.Group.color(group)
        inside = [(x, y) for x in range(box.left + 2, box.right - 2)
                  for y in range(box.top + 2, box.bottom - 2)]
        name_pixels = [pos for pos in inside
                       if tuple(self.game.screen.get_at(pos))[:3] == colour]
        self.assertGreater(len(name_pixels), 10, "the group's name was not drawn")
        grey = (214, 214, 214)      # the badge's description ink
        self.assertEqual(
            [pos for pos in inside
             if tuple(self.game.screen.get_at(pos))[:3] == grey], [],
            "the box printed the group's description")

    def test_the_box_sits_in_the_cells_corner_in_the_groups_colour(self):
        value = main.Tool.BRICK
        collection.discover_tool(value)        # so the cell is not dimmed
        index = self._index_of("tool", value)
        cell = main.ui.collection_entry_rect(index)
        # The tool entries sit far down the list, so scroll them into view (the
        # codex skips a cell that is off-screen entirely).
        self.game.collection_scroll = max(0, cell.top - 200)
        main.ui.draw_collection(self.game)
        cell = cell.move(0, -self.game.collection_scroll)
        group = main.Group.CARDS
        colour = main.Group.color(group)
        box = main.ui.collection_group_rect(self.game, cell, group)

        # The border wears the family's colour, on a dark tint of it...
        self.assertEqual(
            tuple(self.game.screen.get_at((box.centerx, box.top)))[:3], colour)
        # ...(sampled inside the border, clear of the centred name)...
        self.assertEqual(
            tuple(self.game.screen.get_at((box.left + 2, box.centery)))[:3],
            components.shade(colour, -0.72))
        # ...and it is wholly inside the cell, below the description's last line
        # and clear of the tier tag the cards print beside it.
        self.assertGreaterEqual(box.left, cell.left)
        self.assertLessEqual(box.right, cell.right)
        self.assertLessEqual(box.bottom, cell.bottom)
        self.assertGreaterEqual(box.top, cell.top + 34 + 5 * 14)

    def test_an_unseen_entry_wears_a_dimmed_box(self):
        box = self._drawn_box(main.ui.collection_entry_rect(0),
                              main.Group.STRUCTURE, discovered=False)

        border = tuple(self.game.screen.get_at((box.centerx, box.top)))[:3]

        self.assertEqual(border, (110, 110, 120))
        self.assertNotEqual(border, main.Group.color(main.Group.STRUCTURE))


class ItemIconTests(GameTestCase):
    """Every item wears an icon of its own: nothing is a bare letter."""

    def _fingerprint(self, art):
        rect = art.get_bounding_rect()
        return (rect.width, rect.height,
                pygame.image.tostring(art, "RGBA"))

    def _assert_own_icons(self, arts, label):
        seen = {}
        for value, art in arts:
            with self.subTest(item=f"{label}:{value}"):
                self.assertIsNotNone(art, "no icon art")
                width, height, _ = self._fingerprint(art)
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
            seen.setdefault(self._fingerprint(art)[2], []).append(value)
        duplicates = [values for values in seen.values() if len(values) > 1]
        self.assertEqual(duplicates, [], f"two {label}s share one picture")

    def test_every_tool_has_its_own_icon(self):
        self._assert_own_icons(
            [(value, main.ui._tool_art(value)) for value in main.Tool.ORDER],
            "tool")

    def test_every_passive_has_its_own_icon(self):
        self._assert_own_icons(
            [(value, main.ui._passive_art(value))
             for value in main.Passive.ORDER], "passive")

    def test_every_pack_has_its_own_icon(self):
        self._assert_own_icons(
            [(value, main.ui._pack_art(value)) for value in main.Pack.ORDER],
            "pack")

    def test_every_scorer_has_its_own_icon(self):
        # The three run roles have faces of their own (a marble, a checkerboard,
        # a plain tile), so they are the only values with no art.
        roles = {main.Scorer.NONE, main.Scorer.START, main.Scorer.FINISH}
        arts = [(value, main.ui._scorer_art(value)) for value in main.Scorer.ORDER
                if value not in roles]
        self._assert_own_icons(arts, "scorer")
        for value in roles:
            self.assertIsNone(main.ui._scorer_art(value))

    def test_every_structure_still_has_its_own_icon(self):
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        for value in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(value)):
                self.assertTrue(main.ui._draw_structure_icon(
                    surface, value,
                    pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)))

    def test_an_unknown_value_falls_back_to_its_letter(self):
        self.assertIsNone(main.ui._tool_art(99))
        self.assertIsNone(main.ui._passive_art(99))
        self.assertIsNone(main.ui._pack_art(99))
        self.assertIsNone(main.ui._scorer_art(99))
        # ...and drawing one is still a tile, not a crash.
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        main.ui.draw_tool(surface, main.ToolItem(99), surface.get_rect())
        main.ui.draw_passive(surface, main.PassiveItem(99), surface.get_rect())
        main.ui.draw_pack_bundle(surface, 99, surface.get_rect())

    def test_a_tool_tile_shows_a_picture_not_a_flat_face(self):
        rect = pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)
        for value in main.Tool.ORDER:
            with self.subTest(tool=main.Tool.name(value)):
                surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
                surface.fill((0, 0, 0))
                main.ui.draw_tool(surface, main.ToolItem(value), rect)
                flat = main.Tool.COLORS[value]
                marked = sum(
                    1
                    for x in range(2, rect.width - 2)
                    for y in range(2, rect.height - 2)
                    if tuple(surface.get_at((x, y)))[:3] != flat)
                self.assertGreater(marked, 20)

    def test_a_scorer_tile_shows_its_mark_on_its_colour(self):
        item = main.Component.scorer_component(main.Scorer.CASH, amount=30)
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        surface.fill((0, 0, 0))
        main.ui.draw_shop_item(surface, item, surface.get_rect())
        colour = main.Scorer.color(main.Scorer.CASH)
        marked = sum(
            1
            for x in range(2, main.GRID_SIZE - 2)
            for y in range(2, main.GRID_SIZE - 2)
            if tuple(surface.get_at((x, y)))[:3] not in (colour, (0, 0, 0)))
        self.assertGreater(marked, 20)
