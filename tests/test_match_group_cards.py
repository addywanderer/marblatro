"""The match-group card model: one unsplittable card per (group x scorer).

A card is a MATCH GROUP — a group of shapes, or a single effect — plus one card
scorer, both baked in and unsplittable (see components' MATCH GROUPS section).
A card never changes a block: it fires its scorer when the marble collides with
a block the group matches. A card's rarity comes from its GROUP alone, so the
shop draws a group first and its scorer afterwards.
"""

import collections

from tests.game_test_case import *


class MatchGroupCatalogueTests(GameTestCase):
    """The (group x scorer) catalogue the design asks for."""

    def test_the_nine_shape_groups_are_the_ones_the_design_asks_for(self):
        groups = [tuple(main.Shape.name(shape) for shape in group[1])
                  for group in components.MATCH_GROUPS if group[0] == "shape"]
        self.assertEqual(groups, [
            ("Pipe", "Drain", "Pipe Bend"),
            ("Platform", "Corner"),
            ("Key", "Lock"),
            ("Bump", "Circle"),
            ("Curved Slope", "Convex Slope"),
            ("Peg", "Spike", "Sawtooth"),
            ("Slope", "Line"),
            ("None",),
            ("Flat Line", "Curved Slope Line", "Half Pipe"),
        ])

    def test_the_effect_groups_are_every_effect_but_none(self):
        groups = [group[1][0] for group in components.MATCH_GROUPS
                  if group[0] == "effect"]
        self.assertEqual(groups, list(main.Effect.REAL_ORDER))
        self.assertNotIn(main.Effect.NONE, groups)

    def test_every_shape_but_rect_is_in_exactly_one_group(self):
        for shape in main.Shape.ORDER:
            group = main.match_group_for_shape(shape)
            members = [g for g in components.MATCH_GROUPS
                       if g[0] == "shape" and shape in g[1]]
            if shape == main.Shape.RECT:
                # A plain rect wall is the game's inert block: it matches no
                # group at all, by design.
                self.assertIsNone(group, main.Shape.name(shape))
                self.assertEqual(members, [], main.Shape.name(shape))
            else:
                self.assertEqual(members, [group], main.Shape.name(shape))

    def test_every_effect_but_none_is_in_exactly_one_group(self):
        for effect in main.Effect.ORDER:
            group = main.match_group_for_effect(effect)
            members = [g for g in components.MATCH_GROUPS
                       if g[0] == "effect" and g[1] == (effect,)]
            if effect == main.Effect.NONE:
                self.assertIsNone(group, main.Effect.name(effect))
                self.assertEqual(members, [], main.Effect.name(effect))
            else:
                self.assertEqual(members, [group], main.Effect.name(effect))

    def test_every_group_and_scorer_pair_has_exactly_one_card(self):
        cards = components.match_group_card_values()
        self.assertEqual(len(cards),
                         len(components.MATCH_GROUPS) * len(components.CARD_SCORERS))
        self.assertEqual(len(set(cards)), len(cards))  # one card per pair
        self.assertEqual(min(cards), components.MATCH_GROUP_CARD_OFFSET)
        for group in components.MATCH_GROUPS:
            for scorer in components.CARD_SCORERS:
                value = main.match_group_card(group, scorer)
                self.assertIn(value, cards)
                self.assertEqual(components.match_group_card_meta(value),
                                 (group, scorer))
                # A group card is not a whole card, so it can never turn up in
                # the whole-card catalogue or its shop pool.
                self.assertNotIn(value, main.Card.ORDER)

    def test_a_group_card_is_named_priced_and_described_by_its_group(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(pipe, main.Scorer.CHIPS_ADD)
        self.assertEqual(main.Card.name(value),
                         "Pipe/Drain/Pipe Bend card (+Chips)")
        self.assertEqual(main.Card.description(value),
                         "Gives +30 chips when the marble collides with a Pipe, "
                         "Drain or Pipe Bend block")
        self.assertEqual(main.Card.COLORS[value],
                         main.Scorer.color(main.Scorer.CHIPS_ADD))
        # The icon is the group's (its first shape's art, see ui), never the
        # scorer's, so the glyph is the group label's initial.
        self.assertEqual(main.Card.GLYPHS[value], "P")
        self.assertEqual(main.Card.GLYPHS[value],
                         components.match_group_glyph(pipe))

    def test_a_group_card_price_is_the_groups_rarity_plus_its_scorers(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.assertEqual(
            main.Card.PRICES[main.match_group_card(pipe, main.Scorer.CHIPS_ADD)],
            components.match_group_price(pipe)
            + components.scorer_component_price(main.Scorer.CHIPS_ADD))
        # A dearer scorer makes the same group's card dearer (Echo is the most
        # expensive card scorer in the catalogue).
        self.assertGreater(components.scorer_component_price(main.Scorer.ECHO),
                           components.scorer_component_price(main.Scorer.CHIPS_ADD))
        self.assertGreater(
            main.Card.PRICES[main.match_group_card(pipe, main.Scorer.ECHO)],
            main.Card.PRICES[main.match_group_card(pipe, main.Scorer.CHIPS_ADD)])

    def test_every_group_card_states_what_it_does_and_what_it_matches(self):
        for group in components.MATCH_GROUPS:
            trigger = components.match_group_trigger(group)
            for scorer in components.CARD_SCORERS:
                value = main.match_group_card(group, scorer)
                text = main.Card.description(value)
                self.assertTrue(text.startswith("Gives "), text)
                self.assertNotIn("Unknown", text, (group, scorer))
                # Every card is triggered by a collision, and says which block
                # it reads.
                self.assertIn("when the marble collides with", text, text)
                self.assertGreater(main.Card.PRICES[value], 0)
            self.assertIn("collides", trigger)

    def test_the_card_text_reads_the_collided_block(self):
        # A payoff that measures something about the hit block says SO: every
        # card is a collision card now, so nothing measures "the board" or "the
        # run" as if it triggered by itself.
        summit = main.Card.description(
            main.match_group_card(main.match_group_for_shape(main.Shape.SLOPE),
                                  main.Scorer.SUMMIT))
        self.assertIn(components.COLLISION_REFERENCE, summit)


class MatchGroupRarityTests(GameTestCase):
    """A card's rarity is its group's, and never its scorer's."""

    def test_a_cheap_part_makes_a_dear_card(self):
        # The card's price runs INVERSELY to the component it matches (the old
        # collision-condition rule): a rare effect the player hardly ever has on
        # the board is a cheap card, and a common shape a dear one.
        bouncy = main.match_group_for_effect(main.Effect.BOUNCY)
        splitter = main.match_group_for_effect(main.Effect.SPLITTER)
        self.assertGreater(
            main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.SPLITTER)],
            main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.BOUNCY)])
        self.assertLess(components.match_group_price(splitter),
                        components.match_group_price(bouncy))

    def test_a_shape_group_is_priced_off_the_cheapest_shape_it_holds(self):
        # The commonest (cheapest) shape in a group decides the group's rarity,
        # and the relation is INVERSE: a cheap, everywhere part is a dear card.
        line = main.match_group_for_shape(main.Shape.LINE)
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        cheapest_line = min(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)]
                            for shape in line[1])
        cheapest_pipe = min(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)]
                            for shape in pipe[1])
        self.assertEqual(cheapest_line, 11)  # Slope / Line
        self.assertEqual(cheapest_pipe, 9)   # Pipe / Drain / Pipe Bend
        # Dearer part -> cheaper card, exactly as the old collision conditions
        # were priced.
        self.assertGreater(cheapest_line, cheapest_pipe)
        self.assertLess(components.match_group_price(line),
                        components.match_group_price(pipe))

    def test_the_fiddliest_shapes_are_the_cheapest_group_to_match(self):
        # Flat Line / Curved Slope Line / Half Pipe are the expensive, awkward
        # pieces, so their group is the cheapest shape group's card — the one
        # the shop offers most often.
        flat = main.match_group_for_shape(main.Shape.FLAT_LINE)
        self.assertEqual(main.match_group_price(flat),
                         min(components.match_group_price(group)
                             for group in components.MATCH_GROUPS
                             if group[0] == "shape"))

    def test_every_group_is_offered_as_often_as_any_other(self):
        # The offer pool holds each group ONCE and each whole card once, so a
        # plain random choice from the pool is what sets a card's rarity: no
        # group is rarer than another, and no scorer can tilt it.
        random.seed(4242)
        counts = collections.Counter()
        for _ in range(6000):
            value = main.random_card_option_value()
            meta = components.match_group_card_meta(value)
            if meta is not None:
                counts[components.match_group_label(meta[0])] += 1
        self.assertEqual(len(counts), len(components.MATCH_GROUPS))
        average = sum(counts.values()) / len(counts)
        for label, count in counts.items():
            self.assertAlmostEqual(count / average, 1.0, delta=0.35, msg=label)

    def test_the_shop_draws_the_group_first_and_the_scorer_after_it(self):
        # The scorer is drawn AFTER the group (see main.random_prebuilt_card_value
        # and the shop's make_card_item), so all 32 card scorers can ride on one
        # group's card: no scorer is tied to a particular group.
        random.seed(20240607)
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        with mock.patch("main.random_match_group", return_value=pipe):
            seen = {main.random_prebuilt_card_value() for _ in range(600)}
        self.assertEqual(seen, {main.match_group_card(pipe, scorer)
                                for scorer in components.CARD_SCORERS})

    def test_the_offer_pool_is_the_whole_cards_plus_the_groups(self):
        # The pool is still the whole cards plus the groups, but the draw picks
        # a TIER first (see Rarity.WEIGHTS and main.card_offer_entries) and a
        # card inside that tier second, so the whole cards' share is each tier's
        # weighted share times the fraction of that tier's entries that are
        # whole cards.
        random.seed(11)
        draws = [main.random_card_option_value() for _ in range(3000)]
        whole = sum(1 for value in draws if value in main.Card.ORDER)
        weights = [components.Rarity.weight(tier)
                   for tier in components.Rarity.ORDER]
        total = sum(weights)
        share = 0.0
        for tier, weight in zip(components.Rarity.ORDER, weights):
            entries = main.card_offer_entries(tier)
            whole_entries = [entry for entry in entries if entry in main.Card.ORDER]
            share += weight / total * len(whole_entries) / len(entries)
        self.assertAlmostEqual(whole / len(draws), share, delta=0.03)
        # ...and each of a group's 32 scorer variants is offered a 32nd as often
        # as the group is, because the scorer is drawn after the group.
        self.assertEqual(len(components.CARD_SCORERS), 32)

    def test_a_prebuilt_card_offer_is_always_a_group_card(self):
        for _ in range(50):
            value = main.random_prebuilt_card_value()
            self.assertIsNotNone(components.match_group_card_meta(value))

    def test_the_grant_pool_is_the_whole_cards_plus_random_group_cards(self):
        pool = main.prebuilt_card_pool()
        self.assertTrue(set(main.Card.ORDER) <= set(pool))
        self.assertGreater(len(pool), len(main.Card.ORDER))
        for value in pool[len(main.Card.ORDER):]:
            self.assertIsNotNone(components.match_group_card_meta(value))


class MatchGroupFiringTests(GameTestCase):
    """A matching collision pays, and nothing else does."""

    def test_a_shape_group_fires_on_every_shape_in_it(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.game.cards = [_card_item(pipe, main.Scorer.CHIPS_ADD)]
        for shape in pipe[1]:
            self.game.score_chips = 0
            self._card_fire(main.Block(0, 0, shape=shape,
                                       scorer=main.Scorer.NONE))
            self.assertEqual(self.game.score_chips, self.game.cards[0].amount,
                             main.Shape.name(shape))

    def test_a_shape_group_ignores_a_block_of_another_group(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.game.cards = [_card_item(pipe, main.Scorer.CHIPS_ADD)]
        for shape in (main.Shape.SLOPE, main.Shape.CIRCLE, main.Shape.RECT):
            self.game.score_chips = 0
            self._card_fire(main.Block(0, 0, shape=shape,
                                       scorer=main.Scorer.NONE))
            self.assertEqual(self.game.score_chips, 0, main.Shape.name(shape))

    def test_an_effect_group_fires_on_a_block_carrying_the_effect(self):
        # A rect wall is matched by no SHAPE group, but an effect group still
        # fires on it: the block carries the effect.
        bouncy = main.match_group_for_effect(main.Effect.BOUNCY)
        self.game.cards = [_card_item(bouncy, main.Scorer.MULT_ADD)]
        self.game.score_mult = 1
        self._card_fire(main.Block(0, 0, shape=main.Shape.RECT,
                                   effects=[main.Effect.BOUNCY],
                                   scorer=main.Scorer.NONE))
        self.assertEqual(self.game.score_mult, 1 + self.game.cards[0].amount)

    def test_an_effect_group_ignores_a_block_without_the_effect(self):
        bouncy = main.match_group_for_effect(main.Effect.BOUNCY)
        self.game.cards = [_card_item(bouncy, main.Scorer.MULT_ADD)]
        self.game.score_mult = 1
        self._card_fire(main.Block(0, 0, shape=main.Shape.RECT,
                                   effects=[main.Effect.SLIPPERY],
                                   scorer=main.Scorer.NONE))
        self.assertEqual(self.game.score_mult, 1)

    def test_a_block_matched_twice_fires_both_cards(self):
        # A bouncy pipe block matches the Pipe group AND the Bouncy group.
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        bouncy = main.match_group_for_effect(main.Effect.BOUNCY)
        self.game.cards = [_card_item(pipe, main.Scorer.MULT_ADD),
                           _card_item(bouncy, main.Scorer.MULT_ADD)]
        block = main.Block(0, 0, shape=main.Shape.PIPE,
                           effects=[main.Effect.BOUNCY], scorer=main.Scorer.NONE)
        self.game.score_mult = 1
        self._card_fire(block)
        self.assertEqual(self.game.score_mult,
                         1 + 2 * self.game.cards[0].amount)

    def test_two_cards_of_one_group_both_fire(self):
        # Two cards of the same group are two cards (the shop's no-duplicate
        # rule is what keeps that rare, not the card model).
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.game.cards = [_card_item(pipe, main.Scorer.CHIPS_ADD),
                           _card_item(pipe, main.Scorer.CHIPS_ADD)]
        self.game.score_chips = 0
        self._card_fire(main.Block(0, 0, shape=main.Shape.PIPE,
                                   scorer=main.Scorer.NONE))
        self.assertEqual(self.game.score_chips, 2 * self.game.cards[0].amount)

    def test_a_card_fires_once_per_fresh_collision(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.game.cards = [_card_item(pipe, main.Scorer.MULT_ADD)]
        block = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.score_mult = 1
        marble = self._card_fire(block)
        self.assertEqual(self.game.score_mult, 1 + self.game.cards[0].amount)
        # A block still in contact (touched last tick too) is not a fresh hit.
        marble.collisions_last_tick = [block]
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1 + self.game.cards[0].amount)

    def test_the_card_never_gives_the_block_a_scorer(self):
        # The card triggers the scorer; it does not install it on the block.
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.game.cards = [_card_item(pipe, main.Scorer.MULT_ADD)]
        block = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                           scorer_amount=0)
        self.game.score_mult = 1
        self._card_fire(block)
        self.assertEqual(block.scorer, main.Scorer.NONE)
        self.assertEqual(block.scorer_amount, 0)

    def test_each_matching_card_spawns_one_particle_per_hit(self):
        # Every card that affects the score pops exactly one particle, so a
        # block matched by three cards yields three of them.
        self.game.cards = [
            _card_item(main.match_group_for_shape(main.Shape.PIPE),
                       main.Scorer.CHIPS_ADD),
            _card_item(main.match_group_for_effect(main.Effect.BOUNCY),
                       main.Scorer.MULT_ADD),
            _card_item(main.match_group_for_effect(main.Effect.SLIPPERY),
                       main.Scorer.MULT_MUL),
        ]
        block = main.Block(0, 0, shape=main.Shape.PIPE,
                           effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY],
                           scorer=main.Scorer.NONE)
        self.game.score_chips = 0
        self.game.score_mult = 1
        self._card_fire(block)
        self.assertEqual(len(self.game.score_particles), 3)

    def test_a_card_with_a_rolled_magnitude_pays_hits_own_magnitude(self):
        # The card carries its scorer's own rolled magnitude, so the shop's
        # offer pays what it says it pays.
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        card = _card_item(pipe, main.Scorer.CHIPS_ADD, amount=45)
        self.game.cards = [card]
        self.game.score_chips = 0
        self._card_fire(main.Block(0, 0, shape=main.Shape.PIPE,
                                   scorer=main.Scorer.NONE))
        self.assertEqual(self.game.score_chips, 45)

    def test_the_none_group_fires_on_a_block_with_no_shape(self):
        # The no-hitbox Shape.NONE field is a match group of its own. The marble
        # passes straight THROUGH such a block, but physics still registers a
        # field contact while the marble is inside its cell (see
        # physics._collect_field_contacts), so the group's cards do fire.
        group = main.match_group_for_shape(main.Shape.NONE)
        self.assertEqual(components.match_group_label(group), "No Shape")
        self.assertEqual(components.match_group_trigger(group),
                         "when the marble collides with a block with no shape")
        block = main.Block(0, 0, shape=main.Shape.NONE, scorer=main.Scorer.NONE)
        self.assertTrue(components.match_group_matches_block(group, block))
        self.game.cards = [_card_item(group, main.Scorer.CHIPS_ADD)]
        self.game.score_chips = 0
        # A field contact is delivered as a collision, exactly as the physics
        # step delivers one for a marble inside the field's cell.
        self._card_fire(block)
        self.assertEqual(self.game.score_chips, self.game.cards[0].amount)


class MatchGroupTrialTests(GameTestCase):
    """Deal breaker disables a GROUP, which is the new unit of a card."""

    def test_deal_breaker_disables_every_card_of_one_group(self):
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        slope = main.match_group_for_shape(main.Shape.SLOPE)
        c_pipe1 = _card_item(pipe, main.Scorer.CHIPS_ADD)
        c_pipe2 = _card_item(pipe, main.Scorer.MULT_ADD)
        c_slope = _card_item(slope, main.Scorer.MULT_MUL)
        self.game.cards = [c_pipe1, c_pipe2, c_slope]
        self.game.current_trial = main.Trial.DEAL_BREAKER
        # Force the chosen group to be the Pipe group (one the player holds).
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: pipe if pipe in seq else seq[0]):
            self.game._apply_trial()
        self.assertIn(c_pipe1, self.game.deal_broken_cards)
        self.assertIn(c_pipe2, self.game.deal_broken_cards)
        self.assertNotIn(c_slope, self.game.deal_broken_cards)
        # The broken cards are skipped when their block is hit.
        self.game.score_chips = 1
        self.game.score_mult = 1
        self._card_fire(main.Block(0, 0, shape=main.Shape.PIPE,
                                   scorer=main.Scorer.NONE))
        self.assertEqual((self.game.score_chips, self.game.score_mult), (1, 1))
        # A card of another group still fires on its own block: Deal breaker
        # breaks one group, not the whole card area. (An xMult card at its
        # average magnitude multiplies the multiplier by 1 + 0.25.)
        self._card_fire(main.Block(0, 0, shape=main.Shape.SLOPE,
                                   scorer=main.Scorer.NONE))
        self.assertAlmostEqual(self.game.score_mult, 1.25)


class UnsplittableCardTests(GameTestCase):
    """One card, nothing to split, build or disassemble."""

    def test_the_condition_system_is_gone(self):
        for name in ("Condition", "condition_scorer_card", "CONDITION_ORDER",
                     "NAMED_CONDITION_ORDER", "CARD_DISASSEMBLE_COST",
                     "_build_card", "_disassemble_card"):
            self.assertFalse(hasattr(main, name), name)
        for name in ("condition_component", "condition_scorer_card",
                     "is_splittable_card", "splittable_card_condition_scorer"):
            self.assertFalse(hasattr(components, name), name)
        self.assertFalse(hasattr(main.Component, "CONDITION"))
        # ...but the NAMED CONDITIONS came back as whole cards (see
        # test_named_cards): the classic cards exist again, as cards, with no
        # condition behind them.
        self.assertTrue(hasattr(main.Card, "JOKER"))
        self.assertNotIn(main.Card.JOKER, components.match_group_card_values())
        self.assertIsNone(components.card_scorer(main.Card.JOKER))

    def test_a_group_card_cannot_be_split_into_halves(self):
        # There are no halves to return: S does nothing to a group card.
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        card = _card_item(pipe, main.Scorer.MULT_ADD)
        self.game.cards.append(card)
        self.game.cash = 100
        self.game.selected_toolbox_item = card
        before = len(self.game.toolbox.items)
        self._press(main.pygame.K_s)
        self.assertIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100)
        self.assertEqual(len(self.game.toolbox.items), before)

    def test_the_cradle_shape_is_gone(self):
        self.assertFalse(hasattr(main.Shape, "CRADLE"))
        self.assertNotIn("Cradle",
                         [main.Shape.name(shape) for shape in main.Shape.ORDER])
