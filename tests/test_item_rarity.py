"""Every item's rarity (see components.Rarity).

User request: "give all items a rarity."

ONE RULE: an item's tier is its PRICE's tier (`Rarity.from_price`, the bands in
`Rarity.BANDS`). Those are the bands `Card.RARITIES` was already authored on, and
the same number the shop draws a part by (`component_weight` is 1/price), so an
item's stripe and its odds can never disagree. The two kinds that are not priced
one item at a time say so themselves: a STRUCTURE is free (`Structure.RARITIES`)
and a PACK is priced by its size (`Pack.RARITIES`). A block reads the tier of its
parts and a Spirit token the tier of the block it keeps.

The tier is shown where an item is described — a "Rarity" row in the sidebar
(under the item's own text, before its group) and a coloured tag in its codex
cell — so every item the player can own, buy or open says how rare it is.
"""

from tests.game_test_case import *  # noqa: F401,F403

TOLERANCE = 40  # how close a pixel must be to count as the tier's colour


def _priced_kinds():
    """(kind, {value: (name, price)}) for every kind whose tier IS its price."""
    parts = {}
    for (kind, value), price in components.COMPONENT_PRICES.items():
        label = {main.Component.SHAPE: main.Shape.name,
                 main.Component.EFFECT: main.Effect.name,
                 main.Component.SCORER: main.Scorer.name}[kind](value)
        parts.setdefault(kind, {})[value] = (label, price)
    return [
        ("card", {v: (main.Card.name(v), main.Card.PRICES[v])
                  for v in main.Card.ORDER}),
        ("action", {v: (main.Action.name(v), main.Action.PRICES[v])
                    for v in main.Action.ORDER}),
        ("tool", {v: (main.Tool.name(v), main.Tool.PRICES[v])
                  for v in main.Tool.ORDER}),
        ("passive", {v: (main.Passive.name(v), main.Passive.PRICES[v])
                     for v in main.Passive.ORDER}),
    ] + [(kind, rows) for kind, rows in parts.items()]


def _written_kinds():
    """(kind, values, name) for the kinds whose tier is written down instead."""
    return [
        ("structure", main.Structure.ORDER, main.Structure.name),
        ("pack", main.Pack.ORDER, main.Pack.name),
    ]


class ItemRarityTests(GameTestCase):
    """Every kind of item has a tier, and the tier is its price's tier."""

    def test_every_item_kind_has_a_tier(self):
        for kind, rows in _priced_kinds():
            self.assertTrue(rows, f"no {kind} to check")
            for value, (label, _price) in rows.items():
                with self.subTest(kind=kind, item=label):
                    tier = components.Rarity.of_kind(kind, value)
                    self.assertIsNotNone(tier, f"{label} has no rarity")
                    self.assertIn(tier, components.Rarity.ORDER)
        for kind, values, name in _written_kinds():
            for value in values:
                with self.subTest(kind=kind, item=name(value)):
                    tier = components.Rarity.of_kind(kind, value)
                    self.assertIsNotNone(tier, f"{name(value)} has no rarity")
                    self.assertIn(tier, components.Rarity.ORDER)

    def test_every_codex_entry_has_a_tier_but_a_trial(self):
        # A trial is a way to play a run, not an item (see components.Group), so
        # it is the one entry the codex lists without a tier.
        for kind, value, name, _desc, _has_icon, _seen in self.game._collection_entries():
            tier = components.Rarity.of_kind(kind, value)
            if kind == "trial":
                self.assertIsNone(tier)
                continue
            with self.subTest(entry=f"{kind}:{name}"):
                self.assertIsNotNone(tier)

    def test_the_bands_read_cheapest_first(self):
        # An item worth up to the band's ceiling is that tier; anything dearer
        # than the last ceiling is Legendary.
        bands = ((0, components.Rarity.COMMON), (28, components.Rarity.COMMON),
                 (29, components.Rarity.UNUSUAL),
                 (38, components.Rarity.UNUSUAL),
                 (39, components.Rarity.RARE), (44, components.Rarity.RARE),
                 (45, components.Rarity.EPIC), (47, components.Rarity.EPIC),
                 (48, components.Rarity.LEGENDARY),
                 (500, components.Rarity.LEGENDARY))
        for price, tier in bands:
            with self.subTest(price=price):
                self.assertEqual(components.Rarity.from_price(price), tier)
        # ...and the ceilings climb.
        ceilings = [ceiling for ceiling, _tier in components.Rarity.BANDS]
        self.assertEqual(ceilings, sorted(ceilings))

    def test_a_cards_tier_is_its_prices_tier(self):
        # The rule reproduces Card.RARITIES exactly, which is what lets one rule
        # cover every other kind too.
        for value in main.Card.ORDER:
            with self.subTest(card=main.Card.name(value)):
                self.assertEqual(
                    main.Card.rarity(value),
                    components.Rarity.from_price(main.Card.PRICES[value]))
        # A match-group card is Common whatever its group is priced at (the shop
        # draws the group card's tier by its group — see Card.RARITIES).
        self.assertEqual(components.Rarity.of_kind("match_group", 0),
                         components.Rarity.COMMON)

    def test_a_parts_tier_is_its_prices_tier(self):
        for (kind, value), price in components.COMPONENT_PRICES.items():
            label = {main.Component.SHAPE: main.Shape.name,
                     main.Component.EFFECT: main.Effect.name,
                     main.Component.SCORER: main.Scorer.name}[kind](value)
            with self.subTest(kind=kind, part=label):
                self.assertEqual(components.Rarity.of_kind(kind, value),
                                 components.Rarity.from_price(price))

    def test_the_dearer_items_of_a_kind_are_never_the_commoner_ones(self):
        # The rule has to READ as a rarity: nothing Common may cost more than
        # anything Unusual inside the same kind.
        for kind, rows in _priced_kinds():
            by_tier = {tier: [] for tier in components.Rarity.ORDER}
            for _value, (_label, price) in rows.items():
                by_tier[components.Rarity.of_kind(
                    kind, _value)].append(price)
            tiers = [tier for tier in components.Rarity.ORDER if by_tier[tier]]
            for lower, higher in zip(tiers, tiers[1:]):
                with self.subTest(kind=kind,
                                  lower=components.Rarity.name(lower),
                                  higher=components.Rarity.name(higher)):
                    self.assertLess(max(by_tier[lower]), min(by_tier[higher]))

    def test_a_pack_and_a_structure_write_their_tier_down(self):
        # Neither is priced one item at a time (a structure is free, a pack is
        # priced by its size), so each carries its own table — and each spreads
        # over more than one tier, or the label would say nothing.
        for kind, values, name, table in (
                ("structure", main.Structure.ORDER, main.Structure.name,
                 main.Structure.RARITIES),
                ("pack", main.Pack.ORDER, main.Pack.name, main.Pack.RARITIES)):
            with self.subTest(kind=kind):
                for value in values:
                    self.assertIn(value, table, f"{name(value)} has no row")
                self.assertGreaterEqual(len(set(table.values())), 3)
                self.assertIn(components.Rarity.COMMON, table.values())
                self.assertIn(components.Rarity.EPIC, table.values())

    # --- what an ITEM reads ------------------------------------------------

    def test_every_kind_of_item_instance_reports_its_tier(self):
        token_block = main.Block(0, 0, shape=main.Shape.RECT,
                                 scorer=main.Scorer.START, scorer_amount=1)
        items = {
            "card": (main.CardItem(main.Card.INFERNO,
                                   main.Card.PRICES[main.Card.INFERNO]),
                     components.Rarity.LEGENDARY),
            "action": (main.ActionItem(main.Action.FORESIGHT,
                                       main.Action.PRICES[main.Action.FORESIGHT]),
                       components.Rarity.LEGENDARY),
            "tool": (main.ToolItem(main.Tool.BRICK,
                                   main.Tool.PRICES[main.Tool.BRICK]),
                     components.Rarity.COMMON),
            "passive": (main.PassiveItem(main.Passive.CONCRETE, 16, amount=30),
                        components.Rarity.COMMON),
            # A pack names what it holds by its TYPE, not by a value.
            "pack": (main.ItemPack(main.Pack.RANDOM, main.Pack.NORMAL, [], 34),
                     components.Rarity.EPIC),
            "structure": (main.StructureItem(main.Structure.RIFT, 0),
                          components.Rarity.EPIC),
            "token": (main.ScorerToken(token_block, runs_left=None),
                      components.Rarity.LEGENDARY),
        }
        for label, (item, tier) in items.items():
            with self.subTest(kind=label):
                self.assertEqual(components.Rarity.of(item), tier)

    def test_a_block_wears_the_tier_of_its_parts(self):
        plain = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=6)
        role = main.Block(0, 0, shape=main.Shape.RECT,
                          scorer=main.Scorer.START, scorer_amount=1)
        self.assertEqual(components.Rarity.of(plain), components.Rarity.COMMON)
        self.assertEqual(components.Rarity.of(role), components.Rarity.LEGENDARY)
        # An item in hand reads the same, because it is the same parts.
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.START, 1, 140, "Start Block")
        self.assertEqual(components.Rarity.of(item), components.Rarity.LEGENDARY)

    def test_the_levels_own_things_have_no_rarity(self):
        # They are not the player's items and have no price to be tiered by.
        prop = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        prop.is_level_prop = True
        enemy = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        enemy.is_enemy = True
        for label, item in (("prop", prop), ("enemy", enemy),
                            ("cash readout", main.CASH_BREAKDOWN),
                            ("energy readout", main.ENERGY_READOUT),
                            ("nothing", None)):
            with self.subTest(thing=label):
                self.assertIsNone(components.Rarity.of(item))

    # --- what the player READS ---------------------------------------------

    def test_every_item_states_its_tier_in_the_sidebar(self):
        token_block = main.Block(0, 0, shape=main.Shape.RECT,
                                 scorer=main.Scorer.CHIPS_ADD, scorer_amount=6)
        items = {
            "card": main.CardItem(main.Card.INFERNO,
                                  main.Card.PRICES[main.Card.INFERNO]),
            "action": main.ActionItem(main.Action.FORESIGHT,
                                      main.Action.PRICES[main.Action.FORESIGHT]),
            "tool": main.ToolItem(main.Tool.MULTI_TOOL,
                                  main.Tool.PRICES[main.Tool.MULTI_TOOL]),
            "passive": main.PassiveItem(main.Passive.CONCRETE, 16, amount=30),
            "pack": main.ItemPack(main.Pack.CARD, main.Pack.NORMAL, [], 31),
            "structure": main.StructureItem(main.Structure.PIT, 0),
            "block": main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                    main.Scorer.START, 1, 140, "Start Block"),
            "token": main.ScorerToken(token_block, runs_left=None),
        }
        for label, item in items.items():
            with self.subTest(kind=label):
                tier = components.Rarity.of(item)
                rows = dict(self.game._describe_item(item))
                self.assertIn("Rarity", rows, f"a {label} says no rarity")
                self.assertEqual(rows["Rarity"], components.Rarity.name(tier))

    def test_the_rarity_row_sits_before_the_group_row(self):
        # How rare, then what family: the group is drawn as the highlighted box
        # under the item's name, so the tier is the row that leads into it.
        tool = main.ToolItem(main.Tool.PRY_BAR, main.Tool.PRICES[main.Tool.PRY_BAR])
        labels = [label for label, _ in self.game._describe_item(tool)]
        index = labels.index("Rarity")
        self.assertEqual(labels[index + 1], "Group - Cards")

    def test_the_codex_tag_is_written_in_the_tier_colour(self):
        # Every entry's cell prints its tier in the tier's own colour, whatever
        # kind of item it is (see ui.draw_collection) — so the codex is where the
        # player learns what a stripe means, for a part as much as for a card.
        self.game._unlock_entire_collection()
        entries = self.game._collection_entries()
        # One entry of each of three different kinds, so the tag is checked on a
        # card and on kinds that had no tag before.
        wanted = {}
        for index, (kind, _value, _name, _desc, _icon, _seen) in enumerate(entries):
            if kind in ("pack", "structure", "card") and kind not in wanted:
                wanted[kind] = index
        self.assertEqual(sorted(wanted), ["card", "pack", "structure"])
        for index in wanted.values():
            kind, value = entries[index][0], entries[index][1]
            tier = components.Rarity.of_kind(kind, value)
            cell = main.ui.collection_entry_rect(index)
            self.game.collection_scroll = max(0, cell.top - 240)
            main.ui.draw_collection(self.game)
            cell = main.ui.collection_entry_rect(index)
            cell.y -= self.game.collection_scroll
            self.assertGreater(cell.top, 96, "the entry cannot be scrolled into view")
            self.assertLess(cell.bottom, main.SCREEN_HEIGHT - 90)
            color = components.Rarity.color(tier)
            found = any(
                all(abs(a - b) <= TOLERANCE for a, b in
                    zip(tuple(self.game.screen.get_at((px, py)))[:3], color))
                for px in range(cell.left + 54, cell.right - 6)
                for py in range(cell.top + 100, cell.top + 120))
            with self.subTest(kind=kind, tier=components.Rarity.name(tier)):
                self.assertTrue(found, f"no {components.Rarity.name(tier)} tag "
                                       f"on the {kind} entry")
