"""The item GROUPS: every item belongs to one family, and says which.

User request: "sort all items into groups, and show it in their description
what group they are in." The groups live in components.Group — one row per
family, with the name the description prints, the line it prints, and the item
KINDS that make it up — so the sidebar, the deck's reading order and the tests
all read the same table.
"""

from tests.game_test_case import *  # noqa: F401,F403


class GroupTableTests(GameTestCase):
    """The table itself: named, explained, and covering every kind exactly once."""

    def test_every_group_is_named_and_explained(self):
        names = []
        for group in main.Group.ORDER:
            with self.subTest(group=group):
                self.assertIn(group, main.Group.NAMES)
                self.assertIn(group, main.Group.DESCRIPTIONS)
                name = main.Group.name(group)
                self.assertTrue(name)
                self.assertTrue(main.Group.description(group))
                names.append(name)
        # Two groups with one name would be one group.
        self.assertEqual(len(names), len(set(names)))

    def test_every_player_group_is_made_of_at_least_one_kind(self):
        for group in main.Group.ORDER:
            if group in (main.Group.FOE, main.Group.PROP):
                continue          # the level's things, not made of an item kind
            with self.subTest(group=main.Group.name(group)):
                self.assertIn(group, main.Group.KINDS)
                self.assertTrue(main.Group.KINDS[group])

    def test_no_kind_is_in_two_groups(self):
        kinds = [kind for group, kinds_ in main.Group.KINDS.items()
                 for kind in kinds_]
        self.assertEqual(len(kinds), len(set(kinds)))
        for group, made_of in main.Group.KINDS.items():
            for kind in made_of:
                with self.subTest(kind=kind):
                    self.assertEqual(main.Group.of_kind(kind), group)


class ItemGroupTests(GameTestCase):
    """Every item the game can show lands in its group, and prints it."""

    def _one_of_each(self):
        """An item per player group: (group it must read as, the item)."""
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect +Chips")
        token_block = main.Block(0, 0, shape=main.Shape.RECT,
                                 scorer=main.Scorer.CHIPS_ADD, scorer_amount=30)
        return [
            (main.Group.BLOCK, block),
            (main.Group.PART,
             main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=30)),
            (main.Group.CARDS, main.CardItem(main.Card.ORDER[0], 20)),
            (main.Group.CARDS, main.ActionItem(main.Action.LANTERN, 24)),
            (main.Group.CARDS, main.ToolItem(main.Tool.SHOVEL)),
            (main.Group.STRUCTURE,
             main.StructureItem(main.Structure.PIT, main.Structure.PRICES[main.Structure.PIT])),
            (main.Group.PACK, main.ItemPack(main.Pack.PART, 0, [], 10)),
            (main.Group.PASSIVE,
             main.PassiveItem(main.Passive.CONCRETE,
                              main.Passive.PRICES[main.Passive.CONCRETE])),
            (main.Group.TOKEN, main.ScorerToken(token_block)),
            (main.Group.RESOURCE,
             main.ResourceOption(main.Scorer.CHIPS_ADD, 30, 3)),
        ]

    def test_every_player_item_lands_in_its_group(self):
        for expected, item in self._one_of_each():
            with self.subTest(group=main.Group.name(expected)):
                self.assertEqual(main.Group.of(item), expected)

    def test_a_card_an_action_and_a_tool_are_one_group(self):
        # User request: "join together cards, tools, and actions into one group
        # called 'cards'." All three read as the one family, and it is the only
        # group any of them can be in.
        card = main.CardItem(main.Card.ORDER[0], 20)
        action = main.ActionItem(main.Action.LANTERN, 24)
        tool = main.ToolItem(main.Tool.SHOVEL)

        groups = {main.Group.of(item) for item in (card, action, tool)}

        self.assertEqual(groups, {main.Group.CARDS})
        self.assertEqual(main.Group.name(main.Group.CARDS), "Cards")
        self.assertEqual(main.Group.KINDS[main.Group.CARDS],
                         ("card", "action", "tool"))
        # ...and the table has no card/action/tool rows of their own left over.
        for old in ("CARD", "ACTION", "TOOL"):
            with self.subTest(name=old):
                self.assertFalse(hasattr(main.Group, old))

    def test_every_group_can_be_met(self):
        # A foe, a prop and a trial are not items the player owns, so no item in
        # the list reads as one; every other group is reachable.
        met = {main.Group.of(item) for _expected, item in self._one_of_each()}
        self.assertEqual(met, {group for group in main.Group.ORDER
                               if group not in (main.Group.FOE, main.Group.PROP,
                                                main.Group.TRIAL)})

    def test_a_trial_is_a_group_but_not_an_item(self):
        # A trial is a way to play a run, so it has a family of its own for the
        # codex to print — and no item ever reads as one.
        self.assertEqual(main.Group.of_kind("trial"), main.Group.TRIAL)
        self.assertEqual(main.Group.name(main.Group.TRIAL), "Trial")
        for _expected, item in self._one_of_each():
            self.assertNotEqual(main.Group.of(item), main.Group.TRIAL)

    def test_a_block_on_the_board_is_in_the_same_group_as_its_item(self):
        piece = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect +Chips")
        self.game.toolbox.add(piece)
        self.game.ensure_board_cells()
        cell = self.game.item_cell(piece)
        self.game._equip_block(piece)
        self.game._place_block_at(*cell)

        block = self.game.grid.get(cell)
        self.assertIsNotNone(block)
        self.assertEqual(main.Group.of(block), main.Group.BLOCK)

    def test_the_levels_own_things_have_groups_too(self):
        enemy = main.Enemy(0, 0)
        prop = main.Block(0, 0, shape=main.Shape.RECT)
        prop.is_level_prop = True

        self.assertEqual(main.Group.of(enemy), main.Group.FOE)
        self.assertEqual(main.Group.of(prop), main.Group.PROP)

    def test_a_readout_is_not_an_item(self):
        self.assertIsNone(main.Group.of(main.CASH_BREAKDOWN))
        self.assertIsNone(main.Group.of(main.ENERGY_READOUT))
        self.assertIsNone(main.Group.of(None))

    def test_every_description_names_the_group(self):
        for group, item in self._one_of_each():
            with self.subTest(group=main.Group.name(group)):
                rows = dict(self.game._describe_item(item))
                label = f"Group - {main.Group.name(group)}"
                self.assertIn(label, rows)
                self.assertEqual(rows[label], main.Group.description(group))

    def test_a_foe_and_a_prop_say_which_they_are(self):
        enemy = main.Enemy(0, 0)
        prop = main.Block(0, 0, shape=main.Shape.RECT)
        prop.is_level_prop = True

        self.assertIn("Group - Foe", dict(self.game._describe_item(enemy)))
        self.assertIn("Group - Prop", dict(self.game._describe_item(prop)))


class GroupBadgeTests(GameTestCase):
    """The group is a highlighted box directly under the item's name.

    User request: "show an item's group in a highlighted box directly under the
    item's name." The box is drawn by ui._draw_group_badge from the same row the
    description carries (Game._group_row), so its name and its line are never
    written twice.
    """

    def _placed_tool(self):
        tool = main.ToolItem(main.Tool.BRICK)
        self.game.toolbox.add(tool)
        self.game.ensure_board_cells()
        return tool

    def _drawn_badge(self, item):
        """Draw the item's info box and return (its rect, the badge's box)."""
        pos = self.game._board_item_rect(*self.game.item_cell(item)).center
        rect = main.ui.info_box_rect(self.game, item, "toolbox", pos)
        self.game.screen.fill((0, 0, 0))
        main.ui.draw_item_info(self.game, item, "toolbox", pos)
        width, _height, name_lines, _desc, _hint = main.ui.info_layout(
            self.game, item, "toolbox")
        badge = main.ui.group_badge(
            self.game, item, rect.width - 3 * main.ui.INFO_BOX_INSET)
        height = main.ui.group_badge_height(badge) - main.ui.GROUP_BADGE_GAP
        x = rect.x + main.ui.INFO_BOX_INSET
        y = rect.y + main.ui.INFO_BOX_INSET + 26 * len(name_lines)
        width = rect.width - 3 * main.ui.INFO_BOX_INSET
        return rect, main.pygame.Rect(x, y, width, height)

    def test_every_group_has_a_badge_colour(self):
        colours = []
        for group in main.Group.ORDER:
            with self.subTest(group=main.Group.name(group)):
                self.assertIn(group, main.Group.COLORS)
                colour = main.Group.color(group)
                self.assertEqual(len(colour), 3)
                colours.append(colour)
        # No two families wear the same badge colour.
        self.assertEqual(len(colours), len(set(colours)))

    def test_the_badge_names_the_group_and_says_what_it_is_for(self):
        tool = main.ToolItem(main.Tool.BRICK)

        badge = main.ui.group_badge(self.game, tool, 215)

        self.assertEqual(badge[0], "CARDS")
        self.assertEqual(" ".join(badge[1]),
                         main.Group.description(main.Group.CARDS))

    def test_a_readout_has_no_badge(self):
        self.assertIsNone(main.ui.group_badge(self.game, main.CASH_BREAKDOWN, 215))
        self.assertEqual(main.ui.group_badge_height(None), 0)

    def test_the_group_row_is_the_box_not_a_line_of_rows(self):
        tool = main.ToolItem(main.Tool.BRICK)
        group_row, rows = self.game._describe_item_rows(tool)

        self.assertEqual(group_row,
                         ("Group - Cards", main.Group.description(main.Group.CARDS)))
        self.assertNotIn(group_row, rows)
        self.assertEqual(len(rows), len(self.game._describe_item(tool)) - 1)

    def test_the_box_is_drawn_under_the_name_in_the_groups_colour(self):
        tool = self._placed_tool()
        colour = main.Group.color(main.Group.CARDS)

        rect, box = self._drawn_badge(tool)

        # The box wears its group's colour on a dark tint of it... (the top
        # border, away from the rounded corner, is the plain colour).
        self.assertEqual(
            tuple(self.game.screen.get_at((box.centerx, box.top)))[:3], colour)
        inside = (box.centerx, box.top + main.ui.GROUP_BADGE_NAME_LINE)
        self.assertNotEqual(tuple(self.game.screen.get_at(inside))[:3], colour)
        # ...the group's name is written in that colour inside it...
        name_pixels = sum(
            1
            for px in range(box.x + main.ui.GROUP_BADGE_PAD, box.right - 4)
            for py in range(box.y + 2, box.y + main.ui.GROUP_BADGE_NAME_LINE)
            if tuple(self.game.screen.get_at((px, py)))[:3] == colour)
        self.assertGreater(name_pixels, 20)
        # ...and it sits wholly inside the info box, directly under the name.
        self.assertGreaterEqual(box.top, rect.top + 12)
        self.assertLessEqual(box.bottom, rect.bottom)
        self.assertNotEqual(
            tuple(self.game.screen.get_at((box.centerx, box.top - 2)))[:3], colour)


class GroupOrderTests(GameTestCase):
    """The deck lists the collection sorted into its groups (see Group.ORDER)."""

    def test_the_deck_overlay_sorts_items_into_their_groups(self):
        # Owned in a deliberately jumbled order: an action last-bought, then a
        # card, then a part, then a block.
        action = main.ActionItem(main.Action.LANTERN, 24)
        card = main.CardItem(main.Card.ORDER[0], 20)
        part = main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=30)
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Rect +Chips")
        for item in (action, card, part, block):
            self.game.toolbox.add(item)

        groups = [main.Group.of(item) for item in self.game.deck_overlay_items()]

        # Everything is sorted by its group, whatever order it was gained in,
        # and each family is one run of neighbours.
        ranks = [main.Group.rank(group) for group in groups]
        self.assertEqual(ranks, sorted(ranks))
        seen = [group for index, group in enumerate(groups)
                if index == 0 or groups[index - 1] != group]
        self.assertEqual(seen, sorted(set(seen), key=main.Group.rank))
        # ...and the four this test owns all turn up, in Group.ORDER's order.
        # The card and the action are the one CARDS family now (user request:
        # "join together cards, tools, and actions into one group").
        for group in (main.Group.BLOCK, main.Group.PART, main.Group.CARDS):
            self.assertIn(group, seen)

    def test_inside_a_group_the_deck_lists_items_by_name(self):
        part_a = main.Component.scorer_component(main.Scorer.CASH, amount=1)
        part_b = main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=30)
        self.game.toolbox.add(part_a)
        self.game.toolbox.add(part_b)

        parts = [item for item in self.game.deck_overlay_items()
                 if main.Group.of(item) == main.Group.PART]
        names = [self.game._item_name(item).lower() for item in parts]
        self.assertEqual(names, sorted(names))
