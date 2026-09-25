"""The rarity of every card (see components.Rarity).

A card wears one of five tiers — Common, Unusual, Rare, Epic, Legendary. Every
match-group card (the 832 shape-group and effect cards) is Common; the whole
cards are tiered by price, the codebase's usual rarity rule. The tier is also
the card's SHOP FREQUENCY weight: the shop draws the tier first, weighted
1 : 0.7 : 0.5 : 0.3 : 0.2 from Common up to Legendary (see Rarity.WEIGHTS and
main.random_card_option_value), then a card flat inside the drawn tier — so an
offer's rarity follows the ratio no matter how many cards carry the tier.
"""

import collections
import itertools

from tests.game_test_case import *


class CardRarityTests(GameTestCase):
    """Every card has a tier, and the tiers mean what they say."""

    def test_every_card_has_a_rarity(self):
        cards = list(main.Card.ORDER) + components.match_group_card_values()
        # 34 whole cards (the 14 named ones among them) + 832 group cards.
        self.assertEqual(len(cards), 866)
        for value in cards:
            self.assertIn(value, main.Card.RARITIES, main.Card.name(value))
            self.assertIn(main.Card.rarity(value), components.Rarity.ORDER,
                          main.Card.name(value))

    def test_every_match_group_card_is_common(self):
        # The tier of a match-group card belongs to its group, and every group
        # is common — which is what the design asks for.
        for value in components.match_group_card_values():
            self.assertEqual(main.Card.rarity(value), components.Rarity.COMMON,
                             main.Card.name(value))
        for group in components.MATCH_GROUPS:
            for scorer in components.CARD_SCORERS:
                value = main.match_group_card(group, scorer)
                self.assertEqual(main.Card.rarity_name(value), "Common",
                                 main.Card.name(value))
                self.assertEqual(main.Card.rarity_color(value),
                                 components.Rarity.COLORS[components.Rarity.COMMON])

    def test_the_whole_card_tiers_rise_with_the_price(self):
        # A dearer whole card does more, so it is never in a cheaper tier than a
        # cheaper one — the rule the whole-card table is written to.
        ranked = sorted((main.Card.PRICES[v], main.Card.rarity(v), v)
                        for v in main.Card.ORDER)
        for (price, rarity, card), (next_price, next_rarity, next_card) in \
                itertools.pairwise(ranked):
            self.assertLessEqual(
                rarity, next_rarity,
                f"{main.Card.name(card)} (${price}) is "
                f"{components.Rarity.name(rarity)} but {main.Card.name(next_card)} "
                f"(${next_price}) is {components.Rarity.name(next_rarity)}")
        # Every tier is used by a whole card (so no tier is a dead label), and
        # the extremes are pinned so a re-priced card cannot empty one.
        self.assertEqual(sorted({main.Card.rarity(v) for v in main.Card.ORDER}),
                         list(components.Rarity.ORDER))
        self.assertEqual(main.Card.rarity_name(main.Card.ERR_404), "Common")
        self.assertEqual(main.Card.rarity_name(main.Card.INFERNO), "Legendary")
        self.assertEqual(main.Card.rarity_name(main.Card.SHOWMAN), "Legendary")

    def test_the_five_tiers_are_named_and_coloured_differently(self):
        self.assertEqual([components.Rarity.name(r) for r in components.Rarity.ORDER],
                         ["Common", "Unusual", "Rare", "Epic", "Legendary"])
        colors = [components.Rarity.color(r) for r in components.Rarity.ORDER]
        self.assertEqual(len(set(colors)), len(colors))
        for i, one in enumerate(colors):
            for other in colors[i + 1:]:
                # A tier must be tellable from every other: 50+ apart in a
                # channel, the rule the scorer colours follow.
                self.assertGreaterEqual(
                    max(abs(a - b) for a, b in zip(one, other)), 50, (one, other))

    def test_an_unknown_card_reads_as_common(self):
        self.assertEqual(main.Card.rarity_name(-1), "Common")
        self.assertEqual(main.Card.rarity_color(-1),
                         components.Rarity.COLORS[components.Rarity.COMMON])
        self.assertEqual(components.Rarity.name(99), "Unknown")

    def test_the_tiers_carry_the_shop_frequency_ratio(self):
        # A tier's weight IS its shop frequency (see Rarity.WEIGHTS), and the
        # weights are the requested 1 : 0.7 : 0.5 : 0.3 : 0.2 ratio from Common
        # up to Legendary.
        ratio = (1.0, 0.7, 0.5, 0.3, 0.2)
        weights = tuple(components.Rarity.weight(tier)
                        for tier in components.Rarity.ORDER)
        self.assertEqual(weights, ratio)
        self.assertEqual(components.Rarity.ORDER,
                         [components.Rarity.COMMON, components.Rarity.UNUSUAL,
                          components.Rarity.RARE, components.Rarity.EPIC,
                          components.Rarity.LEGENDARY])
        for weight, wanted in zip(weights, ratio):
            self.assertAlmostEqual(weight / weights[0], wanted)
        # A card reports its own tier's weight, an unknown card the Common one,
        # and every group card the Common one (they are all Common).
        self.assertEqual(main.Card.rarity_weight(main.Card.INFERNO), 0.2)
        self.assertEqual(main.Card.rarity_weight(main.Card.SHOWMAN), 0.2)
        self.assertEqual(main.Card.rarity_weight(main.Card.COUPON), 0.3)
        self.assertEqual(main.Card.rarity_weight(main.Card.WATCH), 0.5)
        self.assertEqual(main.Card.rarity_weight(main.Card.GARDEN), 0.7)
        self.assertEqual(main.Card.rarity_weight(main.Card.MINESHAFT), 1.0)
        self.assertEqual(main.Card.rarity_weight(-1), 1.0)
        for value in components.match_group_card_values():
            self.assertEqual(main.Card.rarity_weight(value), 1.0,
                             main.Card.name(value))

    def test_a_rarer_tier_is_offered_the_ratio_less_often(self):
        # Measured through the real offer draw: the share of offers that come
        # out of each TIER follows the weights, 1 : 0.7 : 0.5 : 0.3 : 0.2 — and
        # it follows them even though the tiers hold 40/7/7/3/3 pool entries,
        # which is the point of drawing the tier before the card.
        random.seed(90210)
        draws = [main.random_card_option_value() for _ in range(60000)]
        counted = collections.Counter(main.Card.rarity(value) for value in draws)
        entries = {tier: len(main.card_offer_entries(tier))
                   for tier in components.Rarity.ORDER}
        # 34 whole cards + 26 groups, and the tiers are very unevenly sized.
        self.assertEqual(sum(entries.values()), 60)
        self.assertEqual(entries[components.Rarity.COMMON], 40)
        # The tiers are wildly different sizes, so a count-driven draw would
        # show a different pattern: assert the ratio is what decides.
        self.assertGreater(entries[components.Rarity.COMMON],
                           3 * entries[components.Rarity.LEGENDARY])
        for tier in components.Rarity.ORDER[1:]:
            ratio = counted[tier] / counted[components.Rarity.COMMON]
            self.assertAlmostEqual(
                ratio, components.Rarity.weight(tier), delta=0.03,
                msg=components.Rarity.name(tier))
        # The three-card Legendary tier beats the four-card Unusual one, which
        # only the ratio (0.2 vs 0.7) can explain.
        self.assertGreater(counted[components.Rarity.UNUSUAL],
                           counted[components.Rarity.LEGENDARY])

    def test_a_whole_shop_row_keeps_the_tier_ratio(self):
        # The ratio has to hold for the four offers the shop actually shows, not
        # just for a lone draw: keeping the slots distinct must not tilt it. A
        # collision is resolved inside the drawn tier, never by re-drawing the
        # tier — re-drawing would favour whichever tier holds the most cards
        # (Common) and push the small tiers down, which is exactly what a
        # retry-the-whole-offer row did to Unusual (measured 0.62 instead of
        # 0.70).
        random.seed(4242)
        counted = collections.Counter()
        for _ in range(1000):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "card":
                    counted[main.Card.rarity(item.value)] += 1
        self.assertEqual(sum(counted.values()), 4000)  # every slot filled
        for tier in components.Rarity.ORDER[1:]:
            ratio = counted[tier] / counted[components.Rarity.COMMON]
            self.assertAlmostEqual(ratio, components.Rarity.weight(tier),
                                   delta=0.05,
                                   msg=components.Rarity.name(tier))

    def test_the_info_box_names_the_tier(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        rows = dict(self.game._describe_item(_card_item(pipe, main.Scorer.MULT_ADD)))
        self.assertEqual(rows["Rarity"], "Common")
        legendary = main.CardItem(main.Card.INFERNO, main.Card.PRICES[main.Card.INFERNO])
        rows = dict(self.game._describe_item(legendary))
        self.assertEqual(rows["Rarity"], "Legendary")
        # The tier row sits between what the card does and its flavour line.
        labels = [label for label, _ in self.game._describe_item(legendary)]
        self.assertEqual(labels, [f"Card - {main.Card.name(main.Card.INFERNO)}",
                                  "Rarity", "Comment"])

    def test_the_card_border_is_the_tier_colour(self):
        # Every card is FRAMED in its tier's colour (draw_card), so the tier is
        # visible in the shop, the card area and the codex alike.
        common = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                            main.Scorer.MULT_ADD)
        legendary = main.CardItem(main.Card.INFERNO,
                                  main.Card.PRICES[main.Card.INFERNO])
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        for item, tier in ((common, components.Rarity.COMMON),
                           (legendary, components.Rarity.LEGENDARY)):
            surface.fill((0, 0, 0))
            rect = surface.get_rect()
            main.ui.draw_card(surface, item, rect)
            wanted = components.Rarity.color(tier)
            # The frame is 2px, so its inner rows and columns are the tier's
            # colour; the ranges stop short of the rounded corners, and the
            # centre art (GRID_SIZE*0.62 at most, centred) never reaches them.
            ring = ([tuple(surface.get_at((px, rect.top + 1)))[:3]
                     for px in range(rect.left + 5, rect.right - 5)]
                    + [tuple(surface.get_at((px, rect.bottom - 2)))[:3]
                       for px in range(rect.left + 5, rect.right - 5)]
                    + [tuple(surface.get_at((rect.left + 1, py)))[:3]
                       for py in range(rect.top + 5, rect.bottom - 5)]
                    + [tuple(surface.get_at((rect.right - 2, py)))[:3]
                       for py in range(rect.top + 5, rect.bottom - 5)])
            self.assertTrue(all(px == wanted for px in ring),
                            (main.Card.name(item.value), ring))
            # ...and the face inside the frame is the card's own face colour.
            self.assertEqual(
                tuple(surface.get_at((rect.left + 5, rect.centery)))[:3],
                main.Card.face_color(item.value), main.Card.name(item.value))

    def test_a_face_too_close_to_its_border_is_moved_aside(self):
        # A tier border only reads if the face behind it is a different colour,
        # so a face within FACE_GAP of its own tier colour is shaded away from
        # it: Garden (a green face on the green Unusual border) is the card that
        # made the rule necessary, and the 26 group cards of the two muted
        # scorers on the grey Common border are the rest of it.
        cards = list(main.Card.ORDER) + components.match_group_card_values()
        for value in cards:
            self.assertGreaterEqual(
                components.color_gap(main.Card.face_color(value),
                                     main.Card.rarity_color(value)),
                main.Card.FACE_GAP, main.Card.name(value))
        # Every card that is already far enough from its border keeps its colour
        # exactly — the rule must not repaint the catalogue.
        untouched = [value for value in cards
                     if components.color_gap(main.Card.COLORS[value],
                                             main.Card.rarity_color(value))
                     >= main.Card.FACE_GAP]
        self.assertGreater(len(untouched), 750)
        for value in untouched:
            self.assertEqual(main.Card.face_color(value), main.Card.COLORS[value])
        # Garden: a DEEPER green, so the card still reads as the Garden card
        # (its own colour family) while the bright Unusual border shows.
        base = main.Card.COLORS[main.Card.GARDEN]
        moved = main.Card.face_color(main.Card.GARDEN)
        self.assertNotEqual(moved, base)
        self.assertEqual(max(moved), moved[1])            # still green
        self.assertLess(sum(moved), sum(base))            # and darker
        self.assertGreaterEqual(
            components.color_gap(moved, main.Card.rarity_color(main.Card.GARDEN)),
            main.Card.FACE_GAP)

    def test_the_codex_names_the_tier_of_a_revealed_card(self):
        # The collection entry prints the tier in the tier's own colour under the
        # entry's text: the codex is where the border on a card is explained. The
        # entry grid below mirrors ui.draw_collection (5 columns of 212x92 cells
        # with a 14px gap, starting at y 118) — keep the two in step.
        index = main.Card.ORDER.index(main.Card.INFERNO)
        x = 42 + (index % 5) * 226
        y = 118 + (index // 5) * 106
        collection.discover_card(main.Card.INFERNO)
        main.ui.draw_collection(self.game)
        gold = components.Rarity.COLORS[components.Rarity.LEGENDARY]
        found = any(
            all(abs(a - b) <= 30 for a, b in
                zip(tuple(self.game.screen.get_at((px, py)))[:3], gold))
            for px in range(x + 54, x + 132)
            for py in range(y + 74, y + 90))
        self.assertTrue(found, "no legendary tier tag drawn on the card entry")
        # With every entry revealed, every kind's tier tag draws without raising.
        self.game._unlock_entire_collection()
        self.assertTrue(all(entry[5] for entry in self.game._collection_entries()))
        main.ui.draw_collection(self.game)
