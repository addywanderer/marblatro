"""Item packs: the shelf's bundles of options, and keeping part of one.

A pack is a shop offer that hands over a CHOICE: buying one opens it, the
player is shown the options its size deals out and keeps what the size allows
(see components.Pack and main.ItemPack). These tests cover the pack tables and
their prices, what each type deals, the sizes' option/keep counts, buying and
opening a pack from the shelf, keeping options of every kind, the refusal rules
(a full area leaves the option on the table), the two rules that cut across the
types — an ACTION pack's action is USED rather than shelved, and a random
pack's action is shelved — and the save round trip.
"""

from tests.game_test_case import *  # noqa: F401,F403


def _pack(pack_type, size, options):
    """A hand-built pack holding the given options (see main.ItemPack)."""
    return main.ItemPack(pack_type, size, list(options),
                         components.pack_price(pack_type, size), keep=1)


class PackDataTests(GameTestCase):
    """The pack and size tables, and what they say."""

    def test_every_pack_type_is_defined(self):
        self.assertEqual(len(main.Pack.ORDER), 9)
        expected = ["Shape Pack", "Effect Pack", "Scorer Pack", "Part Pack",
                    "Block Pack", "Card Pack", "Action Pack", "Resource Pack",
                    "Random Pack"]
        self.assertEqual([main.Pack.name(t) for t in main.Pack.ORDER], expected)
        for pack_type in main.Pack.ORDER:
            with self.subTest(pack=main.Pack.name(pack_type)):
                self.assertTrue(main.Pack.description(pack_type))
                self.assertIn(pack_type, main.Pack.COLORS)
                self.assertIn(pack_type, main.Pack.GLYPHS)
        # The nine types are one constant each, numbered from zero.
        self.assertEqual(sorted({main.Pack.SHAPE, main.Pack.EFFECT,
                                 main.Pack.SCORER, main.Pack.PART,
                                 main.Pack.BLOCK, main.Pack.CARD,
                                 main.Pack.ACTION, main.Pack.RESOURCE,
                                 main.Pack.RANDOM}), list(range(9)))

    def test_the_five_sizes_deal_and_keep_what_the_user_asked_for(self):
        # normal (choose 1 of 3), big (1 of 4), jumbo (1 of 5), mega (2 of 5),
        # giga (2 of 6) — the user's own table.
        wanted = {main.Pack.NORMAL: (3, 1), main.Pack.BIG: (4, 1),
                  main.Pack.JUMBO: (5, 1), main.Pack.MEGA: (5, 2),
                  main.Pack.GIGA: (6, 2)}
        for size, (options, keep) in wanted.items():
            with self.subTest(size=main.Pack.size_name(size)):
                self.assertEqual(main.Pack.options(size), options)
                self.assertEqual(main.Pack.keep(size), keep)
                self.assertEqual(main.Pack.size_description(size),
                                 f"keep {keep} of {options}")
        self.assertEqual([main.Pack.size_name(s) for s in main.Pack.SIZE_ORDER],
                         ["Normal", "Big", "Jumbo", "Mega", "Giga"])
        # The sizes are ordered by what they cost (see SIZE_PRICE_FACTORS).
        factors = [main.Pack.SIZE_PRICE_FACTORS[s]
                   for s in main.Pack.SIZE_ORDER]
        self.assertEqual(factors, sorted(factors))
        self.assertEqual(factors[0], 1.0)  # the baseline size

    def test_the_part_and_random_packs_draw_from_the_other_types(self):
        # A part pack deals any component part; a random pack deals anything
        # another pack might, resource points included.
        self.assertEqual(main.Pack.PART_SOURCES,
                         (main.Pack.SHAPE, main.Pack.EFFECT, main.Pack.SCORER))
        self.assertIn(main.Pack.RESOURCE, main.Pack.RANDOM_SOURCES)
        for source in main.Pack.RANDOM_SOURCES:
            self.assertNotIn(source, (main.Pack.PART, main.Pack.RANDOM))

    def test_the_resource_pack_factor_is_two(self):
        # "resource packs contain resource points equivalent to 2x if a marble
        # touched the corresponding resource point's scorer".
        self.assertEqual(components.RESOURCE_PACK_FACTOR, 2.0)
        self.assertIn("2x", main.Pack.description(main.Pack.RESOURCE))


class PackPriceTests(GameTestCase):
    """The price: one option's average value, times the size's multiplier."""

    def test_a_pack_price_is_its_base_times_the_size_factor(self):
        for pack_type in main.Pack.ORDER:
            for size in main.Pack.SIZE_ORDER:
                with self.subTest(pack=main.Pack.name(pack_type),
                                  size=main.Pack.size_name(size)):
                    base = components.pack_base_price(pack_type)
                    self.assertGreater(base, 0)
                    if pack_type != main.Pack.SHAPE:
                        base *= components.NON_SHAPE_PACK_PRICE_FACTOR
                    self.assertEqual(
                        components.pack_price(pack_type, size),
                        max(1, int(base * main.Pack.SIZE_PRICE_FACTORS[size])))

    def test_only_a_shape_pack_is_sold_at_full_price(self):
        # A shape pack is the one type the shelf charges what its options are
        # worth; every other pack goes for half.
        for pack_type in main.Pack.ORDER:
            for size in main.Pack.SIZE_ORDER:
                with self.subTest(pack=main.Pack.name(pack_type),
                                  size=main.Pack.size_name(size)):
                    full = max(1, int(components.pack_base_price(pack_type)
                                       * main.Pack.SIZE_PRICE_FACTORS[size]))
                    price = components.pack_price(pack_type, size)
                    if pack_type == main.Pack.SHAPE:
                        self.assertEqual(price, full)
                    elif full > 1:
                        self.assertEqual(price, full // 2)

    def test_a_bigger_pack_costs_more_and_none_is_free(self):
        for pack_type in main.Pack.ORDER:
            with self.subTest(pack=main.Pack.name(pack_type)):
                prices = [components.pack_price(pack_type, size)
                          for size in main.Pack.SIZE_ORDER]
                self.assertEqual(prices, sorted(prices))
                self.assertGreater(prices[0], 0)
        self.assertGreaterEqual(components.pack_price(main.Pack.SHAPE,
                                                     main.Pack.NORMAL), 1)

    def test_the_price_ignores_what_the_pack_rolled(self):
        # Like a component's own roll, a pack's price is blind to its contents:
        # two jumbo shape packs cost the same however their shapes landed.
        self.game.cash = 100000
        self.game.shop.items = [
            self.game.shop._roll_pack(main.Pack.CARD, main.Pack.JUMBO, 1, 1),
            self.game.shop._roll_pack(main.Pack.CARD, main.Pack.JUMBO, 2, 1),
        ]
        first, second = self.game.shop.items
        self.assertEqual(first.price, second.price)
        self.assertEqual(self.game._buy_price(first), self.game._buy_price(second))

    def test_the_bases_come_from_the_catalogue(self):
        # The bases are read off the game's own tables, so a pack cannot drift
        # out of step with the shop it sits in.
        shapes = [main.COMPONENT_PRICES[(main.Component.SHAPE, s)]
                  for s in main.Shape.ORDER if s != main.Shape.RECT]
        # The expected value of a DRAWN offer is the harmonic mean of the pool
        # (the shop weights an offer by 1/price), which is below the plain
        # average whenever the pool has any spread at all.
        self.assertLess(components.pack_base_price(main.Pack.SHAPE),
                        sum(shapes) / len(shapes))
        effects = [main.effect_component_price(e) for e in main.Effect.REAL_ORDER]
        self.assertLess(components.pack_base_price(main.Pack.EFFECT),
                        sum(effects) / len(effects))
        # A part pack draws the three part kinds evenly, so it sits between the
        # cheapest and the dearest of them; a random pack averages the seven
        # kinds it can deal.
        part = components.pack_base_price(main.Pack.PART)
        self.assertGreater(part, min(components.pack_base_price(main.Pack.SHAPE),
                                     components.pack_base_price(main.Pack.EFFECT)))
        self.assertLess(part, max(components.pack_base_price(main.Pack.EFFECT),
                                  components.pack_base_price(main.Pack.BLOCK)))
        # A block pack deals ready-made blocks, which are worth more than the
        # parts alone (a block is 75% of its parts' sum, and it has several).
        self.assertGreater(components.pack_base_price(main.Pack.BLOCK),
                           components.pack_base_price(main.Pack.PART))

    def test_a_resource_option_is_worth_twice_what_the_scorer_banks(self):
        # The user's own example: one option of a Picky resource pack is worth
        # 2 x 0.5 = one whole option point, because 0.5 is what a Picky trigger
        # banks at its default magnitude.
        self.assertAlmostEqual(
            components.RESOURCE_PACK_FACTOR
            * components.resource_points_for(main.Scorer.PICKY,
                                             main.Scorer.DEFAULT_AMOUNT[main.Scorer.PICKY]),
            1.0)


class PackRollTests(GameTestCase):
    """What each type and size deals."""

    def test_every_type_and_size_deals_its_size_in_options(self):
        for pack_type in main.Pack.ORDER:
            for size in main.Pack.SIZE_ORDER:
                with self.subTest(pack=main.Pack.name(pack_type),
                                  size=main.Pack.size_name(size)):
                    pack = self.game.shop._roll_pack(pack_type, size)
                    self.assertEqual(len(pack.options), main.Pack.options(size))
                    self.assertEqual(pack.keep, main.Pack.keep(size))
                    self.assertEqual(pack.kept, 0)
                    self.assertEqual(pack.remaining, pack.keep)
                    self.assertTrue(pack.name.endswith(main.Pack.name(pack_type)))
                    self.assertTrue(pack.name.startswith(main.Pack.size_name(size)))
                    self.assertIsNone(main.offer_key(pack))  # packs never dedupe

    def test_a_shape_pack_deals_shapes(self):
        pack = self.game.shop._roll_pack(main.Pack.SHAPE, main.Pack.GIGA)
        self.assertEqual(len(pack.options), 6)
        for option in pack.options:
            self.assertEqual(option.kind, main.Component.SHAPE)
            self.assertNotEqual(option.value, main.Shape.RECT)  # the free default
            self.assertGreater(option.price, 0)
            self.assertEqual(main.Shape.name(option.value),
                             main.Shape.name(option.value))

    def test_an_effect_pack_deals_effects_at_their_own_strength(self):
        # Every effect carries the strength a shelf offer would roll for it: a
        # scalable one its own deviation from the average (never zero, never the
        # average copied), and an on/off one none at all (see Effect.MAGNITUDE /
        # roll_effect_amounts, which leaves those out of a block's map too).
        rolled = set()
        for _ in range(40):
            pack = self.game.shop._roll_pack(main.Pack.EFFECT, main.Pack.JUMBO)
            for option in pack.options:
                with self.subTest(effect=main.Effect.name(option.value)):
                    self.assertEqual(option.kind, main.Component.EFFECT)
                    self.assertNotEqual(option.value, main.Effect.NONE)
                    average = main.Effect.MAGNITUDE.get(option.value, 0)
                    if average:
                        self.assertGreater(option.effect_magnitude, 0)
                        self.assertGreaterEqual(option.effect_magnitude,
                                                average * 0.2)
                        self.assertLessEqual(option.effect_magnitude,
                                             average * 1.8)
                        if option.value == main.Effect.PISTON:
                            rolled.add(option.effect_magnitude)
                    else:
                        self.assertEqual(option.effect_magnitude, 0)
        # ...and the strength is ROLLED, not fixed: a piston pack turns up at
        # different speeds from one deal to the next.
        self.assertGreater(len(rolled), 1)

    def test_a_scorer_pack_deals_scorer_pieces_or_their_role_blocks(self):
        seen_piece = False
        for _ in range(40):
            pack = self.game.shop._roll_pack(main.Pack.SCORER, main.Pack.BIG)
            for option in pack.options:
                self.assertIn(getattr(option, "kind", None),
                              (main.Component.SCORER, "block"))
                if option.kind == main.Component.SCORER:
                    self.assertNotEqual(option.value, main.Scorer.NONE)
                    seen_piece = True
                else:
                    # A run role is dealt as its ready-made Rect block.
                    self.assertIn(option.scorer, (main.Scorer.START,
                                                  main.Scorer.FINISH))
                    self.assertEqual(option.shape, main.Shape.RECT)
        self.assertTrue(seen_piece)

    def test_a_block_pack_deals_ready_made_blocks(self):
        pack = self.game.shop._roll_pack(main.Pack.BLOCK, main.Pack.MEGA)
        for option in pack.options:
            self.assertEqual(option.kind, "block")
            self.assertEqual(option.price,
                             main.block_price_for(option.shape, option.effects,
                                                  option.scorer))

    def test_a_card_pack_deals_cards(self):
        pack = self.game.shop._roll_pack(main.Pack.CARD, main.Pack.GIGA)
        for option in pack.options:
            self.assertEqual(option.kind, "card")
            self.assertGreaterEqual(option.value, 0)
        self.assertEqual(len({main.offer_key(o) for o in pack.options}),
                         len(pack.options))  # distinct deal

    def test_an_action_pack_deals_actions(self):
        pack = self.game.shop._roll_pack(main.Pack.ACTION, main.Pack.JUMBO)
        for option in pack.options:
            self.assertEqual(option.kind, "action")
            self.assertIn(option.value, main.Action.ORDER)
            self.assertEqual(option.price, main.Action.PRICES[option.value])
            self.assertIn(option.version, (1, 2))

    def test_a_resource_pack_deals_points_of_the_four_resource_scorers(self):
        pack = self.game.shop._roll_pack(main.Pack.RESOURCE, main.Pack.GIGA)
        self.assertEqual(len(pack.options), 6)
        scorers = set()
        for option in pack.options:
            self.assertEqual(option.kind, "resource")
            self.assertIn(option.scorer, main.Scorer.RESOURCE_RATE)
            self.assertAlmostEqual(
                option.points,
                components.RESOURCE_PACK_FACTOR
                * components.resource_points_for(option.scorer, option.amount))
            self.assertIn("point", option.name)
            scorers.add(option.scorer)
        # Six options from four scorers: every scorer turns up at least once —
        # and it is the FIRST four that cover them, because the roller always
        # prefers a resource the pack has not shown yet (see
        # _roll_resource_option), so a resource pack is a real choice between all
        # four rather than a roll that can miss one.
        self.assertEqual(len(scorers), len(main.Scorer.RESOURCE_RATE))
        self.assertEqual({o.scorer for o in pack.options[:4]},
                         set(main.Scorer.RESOURCE_RATE))

    def test_a_part_pack_deals_any_kind_of_part(self):
        kinds = set()
        for _ in range(40):
            pack = self.game.shop._roll_pack(main.Pack.PART, main.Pack.GIGA)
            kinds |= {option.kind for option in pack.options}
        self.assertEqual(kinds, {main.Component.SHAPE, main.Component.EFFECT,
                                 main.Component.SCORER})

    def test_a_random_pack_deals_anything_another_pack_might(self):
        kinds = set()
        for _ in range(60):
            pack = self.game.shop._roll_pack(main.Pack.RANDOM, main.Pack.GIGA)
            kinds |= {option.kind for option in pack.options}
        # Everything but a pack itself: components (incl. a part pack's mix),
        # blocks, cards, actions and resource points.
        self.assertEqual(kinds, {main.Component.SHAPE, main.Component.EFFECT,
                                 main.Component.SCORER, "block", "card",
                                 "action", "resource"})

    def test_a_pack_never_deals_the_same_option_twice(self):
        # The options are deduped like the shelf's slots (see OFFER_DUPLICATE_TRIES),
        # so a giga pack of six shapes never shows one shape twice.
        for pack_type in (main.Pack.SHAPE, main.Pack.EFFECT, main.Pack.PART,
                          main.Pack.CARD, main.Pack.ACTION):
            for _ in range(30):
                pack = self.game.shop._roll_pack(pack_type, main.Pack.GIGA)
                keys = [main.offer_key(o) for o in pack.options]
                self.assertEqual(len(set(keys)), len(keys), pack_type)


class PackShopTests(GameTestCase):
    """Buying a pack from the shelf, and opening it."""

    def _place_pack(self, pack_type, size):
        """Put one pack on the shelf (in the first pack slot) and return it."""
        pack = self.game.shop._roll_pack(pack_type, size, 1, main.SHOP_PACK_ROW)
        self.game.shop.items = [pack]
        self.game.cash = 100000
        return pack

    def test_the_shelf_holds_five_item_slots_and_three_packs(self):
        items = [i for i in self.game.shop.items if i.row == main.SHOP_ITEM_ROW]
        packs = [i for i in self.game.shop.items if i.row == main.SHOP_PACK_ROW]
        self.assertEqual([i.col for i in items], [1, 2, 3, 4, 5])
        self.assertEqual([i.col for i in packs], [1, 2, 3])
        self.assertTrue(all(i.kind == "pack" for i in packs))
        # The Board Unit's own tile sits beside them and holds no item.
        self.assertEqual(main.BOARD_UNIT_ROW, main.SHOP_PACK_ROW)
        self.assertEqual(main.BOARD_UNIT_COL, 4)
        self.assertIsNone(self.game.shop.item_at(
            self.game._board_unit_tile().center))

    def test_left_clicking_a_pack_buys_and_opens_it(self):
        pack = self._place_pack(main.Pack.SHAPE, main.Pack.JUMBO)
        cash_before = self.game.cash
        rect = pygame.Rect(self.game.shop.rect.x + pack.col * main.GRID_SIZE,
                           self.game.shop.rect.y + pack.row * main.GRID_SIZE,
                           main.GRID_SIZE, main.GRID_SIZE)
        self._click(rect.center)
        self.assertIs(self.game.open_pack, pack)
        self.assertEqual(self.game.cash, cash_before - pack.price)
        self.assertNotIn(pack, self.game.shop.items)  # bought off the shelf
        self.assertIn("keep 1 of 5", self.game.shop_message)

    def test_a_pack_cannot_be_bought_without_the_cash(self):
        pack = self._place_pack(main.Pack.BLOCK, main.Pack.MEGA)
        self.game.cash = pack.price - 1
        self.game._buy_shop_item(pack)
        self.assertIsNone(self.game.open_pack)
        self.assertEqual(self.game.cash, pack.price - 1)
        self.assertIn("Need $", self.game.shop_message)

    def test_a_shelf_slot_offers_its_kind_at_the_asked_for_odds(self):
        # The user's odds for a non-pack shop option: 23% card, 15% action,
        # 8% shape, 12% effect, 22% scorer, 20% block (see
        # components.Pack.SHELF_WEIGHTS — the one place the odds are set).
        self.assertEqual(sum(main.Pack.SHELF_WEIGHTS.values()), 100)
        self.assertEqual(
            main.Pack.SHELF_WEIGHTS,
            {main.Pack.CARD: 23, main.Pack.ACTION: 15, main.Pack.SHAPE: 8,
             main.Pack.EFFECT: 12, main.Pack.SCORER: 22, main.Pack.BLOCK: 20})
        # Every kind a shelf slot may deal has odds of its own, so none of them
        # is drawn as a side effect of a missing weight.
        self.assertTrue(all(main.Pack.shelf_weight(t) > 0
                            for t in main.SHELF_OFFER_TYPES))
        # A long run of rolls lands on those odds: what a roll DEALS is checked
        # elsewhere, so this watches the kind drawn (an undeduped roll, which
        # is the thing the odds belong to — see _roll_random_offer).
        for kinds, wanted in ((main.SHELF_OFFER_TYPES, main.Pack.SHELF_WEIGHTS),
                              # The odds are relative, so a shelf cut down to
                              # two kinds (as some tests do) still splits those
                              # two by their own weights: 23 : 8.
                              ((main.Pack.CARD, main.Pack.SHAPE),
                               {main.Pack.CARD: 23, main.Pack.SHAPE: 8})):
            with self.subTest(kinds=[main.Pack.name(t) for t in kinds]):
                sources = []
                roll = main.Shop._offer_of

                def spy(shop, source, col, row, parts_only=False):
                    sources.append(source)
                    return roll(shop, source, col, row, parts_only=parts_only)

                shop = main.Shop(main.SHOP_COORDS)
                with mock.patch.object(main, "SHELF_OFFER_TYPES", tuple(kinds)):
                    with mock.patch.object(main.Shop, "_offer_of", spy):
                        for _ in range(20000):
                            shop._roll_random_offer(0, 0)
                total = sum(wanted.values())
                self.assertEqual(len(sources), 20000)
                for pack_type, weight in wanted.items():
                    share = sources.count(pack_type) / len(sources)
                    self.assertAlmostEqual(share, weight / total,
                                           delta=0.01, msg=main.Pack.name(pack_type))

    def test_buying_a_pack_reveals_its_type_in_the_collection(self):
        # A pack is revealed by BUYING one, by type: the size is not part of
        # the entry (see collection.discover_pack), so a big card pack and a
        # giga card pack reveal the same one Card Pack.
        pack = self._place_pack(main.Pack.CARD, main.Pack.BIG)
        self.assertFalse(collection.is_pack_discovered(main.Pack.CARD))
        self.game._buy_shop_item(pack)
        self.assertTrue(collection.is_pack_discovered(main.Pack.CARD))
        self.assertTrue(any(p.title == "New pack"
                            and p.description == "Card Pack"
                            for p in self.game.popups))
        # Only that type: every other pack stays hidden.
        self.assertFalse(any(collection.is_pack_discovered(t)
                             for t in main.Pack.ORDER
                             if t != main.Pack.CARD))
        # A second copy of it, at another size, is nothing new.
        self.game.popups = []
        self.game._buy_shop_item(self._place_pack(main.Pack.CARD,
                                                  main.Pack.GIGA))
        self.assertFalse(any(p.title == "New pack" for p in self.game.popups))
        # An unaffordable pack is not bought, so it reveals nothing.
        unaffordable = self._place_pack(main.Pack.RANDOM, main.Pack.NORMAL)
        self.game.cash = 0
        self.game._buy_shop_item(unaffordable)
        self.assertFalse(collection.is_pack_discovered(main.Pack.RANDOM))

    def test_a_bought_pack_type_survives_a_collection_reload(self):
        # Discoveries live in the profile's collection.json, so a bought pack
        # type is still revealed after the cache is dropped (a reload).
        pack = self._place_pack(main.Pack.PART, main.Pack.NORMAL)
        self.game._buy_shop_item(pack)
        collection.reset()
        self.assertTrue(collection.is_pack_discovered(main.Pack.PART))

    def test_the_codex_lists_one_entry_per_pack_type(self):
        # Every pack the shelf can deal is a codex entry of its own, hidden
        # until one of that type is bought (see Game._collection_entries).
        entries = self.game._collection_entries()
        packs = [e for e in entries if e[0] == "pack"]
        self.assertEqual([e[1] for e in packs], main.Pack.ORDER)
        self.assertTrue(all(e[4] for e in packs))          # every one has art
        self.assertTrue(all(e[2] == "???" and e[3] == "???" and not e[5]
                            for e in packs))
        collection.discover_pack(main.Pack.RANDOM)
        entry = next(e for e in self.game._collection_entries()
                     if e[0] == "pack" and e[1] == main.Pack.RANDOM)
        self.assertEqual(entry[2], "Random Pack")
        self.assertEqual(entry[3], main.Pack.description(main.Pack.RANDOM))
        self.assertTrue(entry[5])
        # The revealed entry draws its sealed bundle (its type's colour, band
        # and glyph, and no size: the entry is the TYPE).
        for pack_type in main.Pack.ORDER:
            with self.subTest(pack=main.Pack.name(pack_type)):
                collection.discover_pack(pack_type)
                icon = pygame.Rect(10, 10, main.GRID_SIZE, main.GRID_SIZE)
                main.ui.draw_collection_icon(self.game, "pack", pack_type, icon)
                band = pygame.Rect(icon.x + 2, icon.centery - 3,
                                   icon.width - 4, 7)
                self.assertEqual(self.game.screen.get_at(band.center)[:3],
                                 main.Pack.color(pack_type))

    def test_unlocking_the_collection_reveals_every_pack_type(self):
        self.game._unlock_entire_collection()
        self.assertTrue(all(collection.is_pack_discovered(t)
                            for t in main.Pack.ORDER))
        self.assertTrue(all(e[5] for e in self.game._collection_entries()))

    def test_the_overlay_lists_one_cell_per_option(self):
        pack = self._place_pack(main.Pack.CARD, main.Pack.GIGA)
        self.game._buy_shop_item(pack)
        rects = main.ui.pack_option_rects(self.game)
        self.assertEqual(len(rects), len(pack.options))
        panel = main.ui.pack_panel_rect(self.game)
        for rect in rects:
            self.assertTrue(panel.contains(rect))
            self.assertEqual(rect.size, (main.ui.PACK_OPTION_CELL,
                                         main.ui.PACK_OPTION_CELL))
        # The click maps back to the option it landed on.
        for index, rect in enumerate(rects):
            self.assertEqual(self.game.pack_option_at(rect.center), index)
        self.assertIsNone(self.game.pack_option_at(panel.topleft))
        # The overlay draws without raising.
        self.game.draw()

    def test_clicking_an_option_keeps_it_and_closes_a_finished_pack(self):
        pack = self._place_pack(main.Pack.SHAPE, main.Pack.JUMBO)
        self.game._buy_shop_item(pack)
        option = pack.options[0]
        self.game._click_pack(main.ui.pack_option_rects(self.game)[0].center)
        self.assertIn(option, self.game.toolbox.items)
        self.assertIsNone(self.game.open_pack)  # 1 of 5 was the whole pack
        self.assertNotIn(option, pack.options)

    def test_a_mega_pack_stays_open_for_its_second_pick(self):
        # (The inventory starts holding the game's two run-role blocks, so the
        # count is measured against what was there before.)
        before = len(self.game.toolbox.items)
        pack = self._place_pack(main.Pack.SHAPE, main.Pack.MEGA)
        self.game._buy_shop_item(pack)
        self.game._keep_pack_option(0)
        self.assertIs(self.game.open_pack, pack)
        self.assertEqual(pack.remaining, 1)
        self.assertEqual(len(pack.options), 4)
        self.assertEqual(len(self.game.toolbox.items), before + 1)
        self.game._keep_pack_option(0)
        self.assertIsNone(self.game.open_pack)
        self.assertEqual(len(self.game.toolbox.items), before + 2)

    def test_skipping_leaves_the_rest_of_the_pack(self):
        pack = self._place_pack(main.Pack.SHAPE, main.Pack.JUMBO)
        self.game._buy_shop_item(pack)
        before = len(self.game.toolbox.items)
        self.game._click_pack(main.ui.pack_skip_rect(self.game).center)
        self.assertIsNone(self.game.open_pack)
        self.assertEqual(len(self.game.toolbox.items), before)
        self.assertIn("left", self.game.shop_message)
        # A right-click anywhere leaves the pack too (see handle_events).
        pack2 = self._place_pack(main.Pack.SHAPE, main.Pack.JUMBO)
        self.game._buy_shop_item(pack2)
        self.assertTrue(pack2.options)  # nothing was taken
        self.game._close_pack()
        self.assertIsNone(self.game.open_pack)

    def test_an_open_pack_owns_the_click_and_the_hover(self):
        pack = self._place_pack(main.Pack.SHAPE, main.Pack.JUMBO)
        self.game._buy_shop_item(pack)
        option = pack.options[2]
        rect = main.ui.pack_option_rects(self.game)[2]
        target, source = self.game._info_target_at(rect.center)
        self.assertIs(target, option)
        self.assertEqual(source, "pack")
        rows = dict(self.game._describe_item(option))
        self.assertIn(f"Shape - {main.Shape.name(option.value)}", rows)
        self.assertIn("shape", self.game._action_hint(option, "pack").lower())


class PackKeepTests(GameTestCase):
    """What keeping an option does, for every kind of option."""

    def _open(self, options, pack_type):
        """Open a hand-built pack holding exactly these options."""
        pack = _pack(pack_type, main.Pack.NORMAL, options)
        self.game.cash = 100000
        self.game.shop.items = [pack]
        self.game._buy_shop_item(pack)
        return pack

    def test_keeping_a_component_puts_it_in_the_inventory(self):
        part = main.Component.shape_component(main.Shape.PIPE)
        self._open([part], main.Pack.SHAPE)
        self.game._keep_pack_option(0)
        self.assertIn(part, self.game.toolbox.items)
        self.assertGreaterEqual(
            self.game.component_purchases.get((main.Component.SHAPE,
                                               main.Shape.PIPE), 0), 1)
        self.assertTrue(collection.is_component_discovered(main.Component.SHAPE,
                                                          main.Shape.PIPE))

    def test_keeping_a_block_puts_it_in_the_inventory(self):
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 40, "Pipe +Chips")
        self._open([block], main.Pack.BLOCK)
        self.game._keep_pack_option(0)
        self.assertIn(block, self.game.toolbox.items)

    def test_a_portal_or_key_lock_option_arrives_as_its_pair(self):
        # A pair is bought as a pair from the shelf, and a pack option is no
        # different: one portal is useless on its own (see _buy_shop_item).
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL,
                                main.Scorer.NONE, 0, 60, "Portal",
                                effects=[main.Effect.PORTAL])
        self._open([portal], main.Pack.BLOCK)
        before = len(self.game.toolbox.items)
        self.game._keep_pack_option(0)
        added = self.game.toolbox.items[before:]
        self.assertEqual(len(added), 2)
        self.assertEqual(len({b.portal_number for b in added}), 1)
        self.assertTrue(all(b.has_effect(main.Effect.PORTAL) for b in added))
        # ...and a Key/Lock option arrives as its matched partner shape.
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key")
        self._open([key], main.Pack.BLOCK)
        before = len(self.game.toolbox.items)
        self.game._keep_pack_option(0)
        added = self.game.toolbox.items[before:]
        self.assertEqual({b.shape for b in added}, {main.Shape.KEY, main.Shape.LOCK})
        self.assertEqual(len({b.key_number for b in added}), 1)

    def test_keeping_a_card_puts_it_in_the_card_area(self):
        card = main.CardItem(main.Card.GARDEN, 36)
        self._open([card], main.Pack.CARD)
        self.game._keep_pack_option(0)
        self.assertIn(card, self.game.cards)
        self.assertNotIn(card, self.game.toolbox.items)

    def test_a_card_the_player_owns_is_refused_and_stays_on_the_table(self):
        # An option that cannot be taken right now is refused rather than lost:
        # the pack keeps it so the player can pick another or skip.
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        card = main.CardItem(main.Card.GARDEN, 36)
        pack = self._open([card], main.Pack.CARD)
        self.game._keep_pack_option(0)
        self.assertEqual(pack.options, [card])
        self.assertEqual(pack.kept, 0)
        self.assertIs(self.game.open_pack, pack)
        self.assertIn("Already own", self.game.shop_message)

    def test_a_full_inventory_refuses_a_part_and_keeps_the_pack_open(self):
        part = main.Component.shape_component(main.Shape.PIPE)
        pack = self._open([part], main.Pack.SHAPE)
        self.game.toolbox.items = [main.BlockItem(0, 0, main.Shape.RECT,
                                                 main.Effect.NONE, main.Scorer.NONE,
                                                 0, 0, "wall")] * (
            self.game.toolbox.cols * self.game.toolbox.rows)
        self.game._keep_pack_option(0)
        self.assertEqual(pack.options, [part])
        self.assertIs(self.game.open_pack, pack)
        self.assertIn("full", self.game.shop_message)

    def test_a_full_card_area_refuses_a_card(self):
        card = main.CardItem(main.Card.GARDEN, 36)
        pack = self._open([card], main.Pack.CARD)
        while len(self.game.cards) < self.game.max_cards:
            self.game.cards.append(main.CardItem(main.Card.JOKER, 24))
        self.game._keep_pack_option(0)
        self.assertEqual(pack.options, [card])
        self.assertIn("full", self.game.shop_message)


class PackActionRuleTests(GameTestCase):
    """An action pack's action is USED; a random pack's is shelved."""

    def _open(self, options, pack_type):
        pack = _pack(pack_type, main.Pack.NORMAL, options)
        self.game.cash = 100000
        self.game.shop.items = [pack]
        self.game._buy_shop_item(pack)
        return pack

    def test_a_target_free_action_is_used_at_once(self):
        action = main.ActionItem(main.Action.GRACE, main.Action.PRICES[main.Action.GRACE])
        self._open([action], main.Pack.ACTION)
        before_mult = self.game.score_mult
        self.game._keep_pack_option(0)
        # Grace v1 adds +xMult to this run: it fired, and it never joined the
        # action area (the user's rule: packs' actions are used, not shelved).
        self.assertEqual(self.game.actions, [])
        self.assertIsNone(self.game.pending_pack_action)
        self.assertNotEqual((self.game.score_mult, self.game.run_xmult_pending),
                            (before_mult, 0.0))

    def test_a_targeted_action_is_armed_for_its_target(self):
        # The user's rule for a targeted action: pick the target by clicking it,
        # then press S — exactly like an action in the action area.
        action = main.ActionItem(main.Action.DEJA_VU, main.Action.PRICES[main.Action.DEJA_VU])
        self._open([action], main.Pack.ACTION)
        self.game._keep_pack_option(0)
        self.assertIs(self.game.pending_pack_action, action)
        self.assertIs(self.game.selected_action, action)
        self.assertEqual(self.game.actions, [])  # never shelved
        self.assertIn("click a target", self.game.shop_message)
        # S with no target refuses (and keeps the action armed)...
        self.assertFalse(self.game._apply_action())
        self.assertIs(self.game.pending_pack_action, action)
        # ...and with a target it applies and spends the packed action.
        block = main.Block(2, 2, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 2)] = block
        self.game.run_active = True
        self.game._pick_action_subject(None, None, block)
        self.assertTrue(self.game._apply_action())
        self.assertIsNone(self.game.pending_pack_action)
        self.assertEqual(block.trigger_limit, 2)

    def test_another_action_cannot_take_the_selection_from_a_packed_one(self):
        # A packed action is not in the action area, so losing the selection
        # would lose the action: while one is armed, nothing else may take it.
        action = main.ActionItem(main.Action.DEJA_VU, main.Action.PRICES[main.Action.DEJA_VU])
        self._open([action], main.Pack.ACTION)
        self.game._keep_pack_option(0)
        other = main.ActionItem(main.Action.DEATH, main.Action.PRICES[main.Action.DEATH])
        self.game.actions.append(other)
        self.game._select_action(other)
        self.assertIs(self.game.pending_pack_action, action)
        self.assertIs(self.game.selected_action, action)
        self.assertIn("packed action", self.game.shop_message)
        # Using the packed action frees the selection again. (Deja Vu refuses a
        # block with no scorer and one that is not on the board, so the subject
        # is a real placed block — see _action_deja_vu.)
        subject = main.Block(1, 1, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(1, 1)] = subject
        self.game.selected_action_subject = subject
        self.assertTrue(self.game._apply_action())
        self.assertEqual(subject.trigger_limit, 2)
        self.assertIsNone(self.game.pending_pack_action)
        self.game._select_action(other)
        self.assertIs(self.game.selected_action, other)

    def test_a_random_packs_action_is_shelved_instead(self):
        action = main.ActionItem(main.Action.DEJA_VU, main.Action.PRICES[main.Action.DEJA_VU])
        self._open([action], main.Pack.RANDOM)
        self.game._keep_pack_option(0)
        self.assertIn(action, self.game.actions)
        self.assertIsNone(self.game.pending_pack_action)


class ResourcePackTests(GameTestCase):
    """Kept resource points go into the permanent bank and convert at once."""

    def _open(self, option):
        pack = _pack(main.Pack.RESOURCE, main.Pack.NORMAL, [option])
        self.game.cash = 100000
        self.game.shop.items = [pack]
        self.game._buy_shop_item(pack)

    def test_the_points_are_banked_and_converted_immediately(self):
        # One whole option point buys a permanent shop slot at once — not at the
        # end of the run, which is where a TRIGGER's points are committed.
        self.assertEqual(self.game.bonus_slots, 0)
        self._open(main.ResourceOption(main.Scorer.PICKY, 1.0, 1.0))
        self.game._keep_pack_option(0)
        self.assertEqual(self.game.option_points, 0.0)  # spent on the slot
        self.assertEqual(self.game.bonus_slots, 1)
        self.assertEqual(self.game.shop.bonus_slots, 1)
        self.assertIn("1 option point", self.game.shop_message)

    def test_a_fraction_of_a_point_stays_banked(self):
        self._open(main.ResourceOption(main.Scorer.RUBBLE, 0.9, 0.9))
        self.game._keep_pack_option(0)
        self.assertAlmostEqual(self.game.rubble_points, 0.9)
        # ...and the pending run gains are untouched: a pack's points are not
        # this run's earnings (they are already the player's).
        self.assertEqual(self.game.rubble_run_gain, 0)

    def test_a_banked_point_converts_the_moment_it_arrives(self):
        # A point left banked by an earlier option joins this one.
        self.game.rubble_points = 0.5
        self.game.toolbox.items.clear()
        self._open(main.ResourceOption(main.Scorer.RUBBLE, 0.5, 0.5))
        self.game._keep_pack_option(0)
        self.assertEqual(self.game.rubble_points, 0.0)
        self.assertEqual(len(self.game.toolbox.items), 1)  # a random block

    def test_the_points_are_not_added_to_the_run_gains(self):
        # A pack's points are already the player's, so they land in the permanent
        # bank (see _grant_resource_points) and never in the run's PENDING gains,
        # which are what a retry takes back.
        cases = ((main.Scorer.SHREDS, "shred_run_gain", "shred_points"),
                 (main.Scorer.IDEAS, "idea_run_gain", "idea_points"))
        for scorer, run_gain, banked in cases:
            with self.subTest(scorer=main.Scorer.name(scorer)):
                self._open(main.ResourceOption(scorer, 0.25, 0.25))
                self.game._keep_pack_option(0)
                self.assertEqual(getattr(self.game, run_gain), 0)
                self.assertGreater(getattr(self.game, banked), 0)


class PackSaveTests(GameTestCase):
    """Packs survive a save: on the shelf, mid-choice, and armed."""

    def test_a_pack_on_the_shelf_saves_and_loads(self):
        pack = self.game.shop._roll_pack(main.Pack.PART, main.Pack.MEGA, 1,
                                         main.SHOP_PACK_ROW)
        self.game.shop.items = [pack]
        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)
        loaded = fresh.shop.items[0]
        self.assertEqual(loaded.kind, "pack")
        self.assertEqual(loaded.pack_type, pack.pack_type)
        self.assertEqual(loaded.size, pack.size)
        self.assertEqual(loaded.price, pack.price)
        self.assertEqual(loaded.keep, pack.keep)
        self.assertEqual(sorted(main.offer_key(o) for o in loaded.options),
                         sorted(main.offer_key(o) for o in pack.options))

    def test_an_open_pack_comes_back_mid_choice(self):
        pack = self.game.shop._roll_pack(main.Pack.CARD, main.Pack.GIGA, 1,
                                         main.SHOP_PACK_ROW)
        self.game.cash = 100000
        self.game.shop.items = [pack]
        self.game._buy_shop_item(pack)
        self.game._keep_pack_option(0)
        self.assertEqual(pack.kept, 1)
        left = len(pack.options)
        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)
        self.assertIsNotNone(fresh.open_pack)
        self.assertEqual(fresh.open_pack.kept, 1)
        self.assertEqual(fresh.open_pack.keep, 2)
        self.assertEqual(len(fresh.open_pack.options), left)
        self.assertEqual(fresh.open_pack.pack_type, main.Pack.CARD)
        # The reloaded pack can still be picked from, and that second pick is
        # the one that finishes it (a giga pack keeps 2 of its 6).
        fresh.cash = 100000
        fresh._keep_pack_option(0)
        self.assertIsNone(fresh.open_pack)
        self.assertEqual(len(fresh.cards), 2)   # both kept cards came home

    def test_a_resource_option_saves_its_points_exactly(self):
        option = main.ResourceOption(main.Scorer.PICKY, 1.25, 1.25)
        pack = _pack(main.Pack.RESOURCE, main.Pack.NORMAL, [option])
        self.game.shop.items = [pack]
        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)
        loaded = fresh.shop.items[0].options[0]
        self.assertEqual(loaded.kind, "resource")
        self.assertEqual(loaded.scorer, main.Scorer.PICKY)
        self.assertAlmostEqual(loaded.amount, 1.25)
        self.assertAlmostEqual(loaded.points, 1.25)

    def test_an_armed_pack_action_comes_back_armed(self):
        action = main.ActionItem(main.Action.DEJA_VU, main.Action.PRICES[main.Action.DEJA_VU],
                                 version=1)
        pack = _pack(main.Pack.ACTION, main.Pack.NORMAL, [action])
        self.game.cash = 100000
        self.game.shop.items = [pack]
        self.game._buy_shop_item(pack)
        self.game._keep_pack_option(0)
        self.assertIsNotNone(self.game.pending_pack_action)
        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)
        self.assertIsNotNone(fresh.pending_pack_action)
        self.assertEqual(fresh.pending_pack_action.value, main.Action.DEJA_VU)
        self.assertIs(fresh.selected_action, fresh.pending_pack_action)
