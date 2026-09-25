"""The fourteen named cards: the classic cards, back as unsplittable cards.

Each named CONDITION the card system was built around is one whole card again
(user request: "add back the named conditions you commented out, as
unsplittable cards"), so the trigger and the payoff live in the card: nothing is
composed, nothing splits, and nothing is rolled — a Joker always pays +4 mult.

The payoffs are the canonical (condition x scorer) pairings the named conditions
came from, on the magnitude model every card used then: one unit is
+30 chips / +4 mult / +0.25 xMult, scaled by the card's ratio (see
components.Card.NAMED). So Joker ratio 1.0 is +4 mult, Pillar 0.25 is +1 mult a
column block, Plane 0.5 is +15 chips an air second, Banker 1/30 is +1 chip per
$10, Ripped Card 4.0 is +120 chips, Island 2.0 is +0.5 xMult a group.

Where each card fires: the start of a run (cards.apply_cards, called by
reset_run), the end of it (cards.apply_cards_on_finish, called by the run's
finish path), or each fragile break (cards.on_fragile_broken).
"""

import collections

from tests.game_test_case import *


def _own(*values):
    """Card items for the given whole cards, at their catalog prices."""
    return [main.CardItem(value, main.Card.PRICES[value]) for value in values]


class NamedCardCatalogueTests(GameTestCase):
    """The fourteen cards exist, priced, tiered, drawn and unsplittable."""

    def test_the_fourteen_named_cards_are_whole_cards(self):
        names = [main.Card.name(value) for value in components.NAMED_CARD_ORDER]
        self.assertEqual(names,
                         ["Joker", "Explorer", "Astronaut", "Plane", "Pillar",
                          "Banker", "Wrecking Ball", "Skater", "Glitch",
                          "Ripped Card", "Cozy", "Painting", "Synthesizer",
                          "Island"])
        for value in components.NAMED_CARD_ORDER:
            with self.subTest(card=main.Card.name(value)):
                # A whole card: in the catalogue (so the shop offers it and the
                # codex lists it), with no group and no scorer half — there is
                # nothing to split it into and nothing to roll.
                self.assertIn(value, main.Card.ORDER)
                self.assertIsNone(components.match_group_card_meta(value))
                self.assertIsNone(components.card_scorer(value))
                self.assertNotIn(value, components.match_group_card_values())
                self.assertTrue(main.Card.description(value))
                self.assertTrue(main.Card.comment(value))
                self.assertEqual(main.Card.PRICES[value],
                                 main.card_price_for(value))

    def test_each_card_fires_in_its_own_phase(self):
        phases = {main.Card.name(value): components.named_card_phase(value)
                  for value in components.NAMED_CARD_ORDER}
        starts = {name for name, phase in phases.items() if phase == "start"}
        ends = {name for name, phase in phases.items() if phase == "end"}
        self.assertEqual(starts, {"Joker", "Pillar", "Banker", "Glitch",
                                  "Ripped Card", "Cozy", "Painting",
                                  "Synthesizer", "Island"})
        self.assertEqual(ends, {"Explorer", "Astronaut", "Plane", "Skater"})
        self.assertEqual([name for name, phase in phases.items()
                          if phase == "fragile"], ["Wrecking Ball"])
        # A card that is not named has no start/end/fragile phase at all: the
        # match-group cards fire on a collision and the utility cards are
        # passives.
        for value in (main.Card.ERR_404, main.Card.COUPON,
                      main.Card.GARDEN):
            self.assertIsNone(components.named_card_phase(value))
        self.assertIsNone(components.named_card_meta(
            components.match_group_card_values()[0]))

    def test_the_payoffs_are_the_canonical_pairings(self):
        # (phase, scorer, ratio, measure) per card — the named condition each
        # one came from, whose canonical scorer reproduces the classic card.
        expected = {
            "Joker": ("start", main.Scorer.MULT_ADD, 1.0, "start"),
            "Explorer": ("end", main.Scorer.MULT_MUL, 1.0, "distance"),
            "Astronaut": ("end", main.Scorer.MULT_ADD, 1.0, "black_hole"),
            "Plane": ("end", main.Scorer.CHIPS_ADD, 0.5, "air_time"),
            "Pillar": ("start", main.Scorer.MULT_ADD, 0.25, "fullest_column"),
            "Banker": ("start", main.Scorer.CHIPS_ADD, 1.0 / 30.0, "cash_held"),
            "Wrecking Ball": ("fragile", main.Scorer.MULT_ADD, 0.75,
                              "fragile_breaks"),
            "Skater": ("end", main.Scorer.MULT_MUL, 0.8, "slippery"),
            "Glitch": ("start", main.Scorer.MULT_ADD, 1.0, "random"),
            "Ripped Card": ("start", main.Scorer.CHIPS_ADD, 4.0, "few_blocks"),
            "Cozy": ("start", main.Scorer.CHIPS_ADD, 3.0, "cozy"),
            "Painting": ("start", main.Scorer.CHIPS_ADD, 0.1, "painting"),
            "Synthesizer": ("start", main.Scorer.MULT_ADD, 0.75, "synthesizer"),
            "Island": ("start", main.Scorer.MULT_MUL, 2.0, "island"),
        }
        for value in components.NAMED_CARD_ORDER:
            meta = components.named_card_meta(value)
            self.assertEqual(meta, expected[main.Card.name(value)],
                             main.Card.name(value))

    def test_the_tiers_follow_the_prices(self):
        priced = sorted((main.Card.PRICES[value], value)
                        for value in components.NAMED_CARD_ORDER)
        tiers = collections.Counter()
        for price, value in priced:
            tier = main.Card.rarity(value)
            tiers[tier] += 1
            if price <= 28:
                self.assertEqual(tier, components.Rarity.COMMON,
                                 main.Card.name(value))
            elif price <= 38:
                self.assertEqual(tier, components.Rarity.UNUSUAL,
                                 main.Card.name(value))
            else:
                self.assertLessEqual(tier, components.Rarity.RARE,
                                     main.Card.name(value))
        # Eleven cheap named cards and the three dear ones ($32 each): every
        # named card is a Common or an Unusual, so none of them is a chase card.
        self.assertEqual(tiers[components.Rarity.COMMON], 11)
        self.assertEqual(tiers[components.Rarity.UNUSUAL], 3)
        self.assertEqual({main.Card.rarity(v) for v in
                          (main.Card.EXPLORER, main.Card.SKATER,
                           main.Card.ISLAND)},
                         {components.Rarity.UNUSUAL})

    def test_every_named_card_has_icon_art(self):
        # The card face draws the named condition's own art (the jester's hat,
        # the compass, the column, ...), so no named card falls back to a letter
        # and no two named cards wear the same picture.
        drawings = set()
        for value in components.NAMED_CARD_ORDER:
            art = main.ui._whole_card_art(value)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               main.Card.name(value))
            drawings.add(pygame.image.tobytes(art, "RGBA"))
        self.assertEqual(len(drawings), 14)

    def test_the_shop_pool_holds_the_named_cards(self):
        pool = main.card_offer_entries()
        for value in components.NAMED_CARD_ORDER:
            self.assertIn(value, pool)
        random.seed(20240925)
        seen = {main.random_card_option_value() for _ in range(4000)}
        self.assertTrue(seen & set(components.NAMED_CARD_ORDER))

    def test_the_codex_lists_a_named_card(self):
        # A named card is a codex entry like any other card: undiscovered it
        # shows as ???, and discovering it puts its real name on the entry.
        entries = {entry[1]: entry for entry in self.game._collection_entries()
                   if entry[0] == "card"}
        for value in components.NAMED_CARD_ORDER:
            self.assertIn(value, entries)
            self.assertEqual(entries[value][2], "???")
        collection.discover_card(main.Card.JOKER)
        entries = {entry[1]: entry for entry in self.game._collection_entries()
                   if entry[0] == "card"}
        self.assertEqual(entries[main.Card.JOKER][2], "Joker")


class NamedCardStartTests(GameTestCase):
    """The nine cards that fire at the start of a run."""

    def _start(self, *values):
        """Own ``values`` and fire the start-of-run cards."""
        self.game.cards = _own(*values)
        self.game._apply_cards()

    def test_the_joker_adds_four_mult_at_the_start_of_every_run(self):
        self.game.cards = _own(main.Card.JOKER)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 5)  # 1 + 4
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 5)  # every run, not +4 more

    def test_the_banker_pays_a_chip_per_ten_dollars(self):
        self.game.score_chips = 1
        self.game.cash = 555
        self._start(main.Card.BANKER)
        self.assertEqual(self.game.score_chips, 1 + 55)
        # Less than $10 held is nothing at all — no chips, no particle.
        self.game.cards = _own(main.Card.BANKER)
        self.game.score_chips = 1
        self.game.cash = 9
        self.game.score_particles.clear()
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_pillar_pays_a_mult_a_fullest_column_block(self):
        self.game.grid = {}
        for gy in range(3):
            self.game.grid[(3, gy)] = main.Block(3, gy)
        self.game.grid[(4, 0)] = main.Block(4, 0)
        self.game.score_mult = 1
        self._start(main.Card.PILLAR)
        self.assertEqual(self.game.score_mult, 1 + 3)
        # An empty board measures 0 columns: nothing to pay.
        self.game.grid = {}
        self.game.score_mult = 1
        self.game.score_particles.clear()
        self._start(main.Card.PILLAR)
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_glitch_pays_a_random_zero_to_twenty_four_mult(self):
        self.game.score_mult = 1
        self._start(main.Card.GLITCH)
        gained = self.game.score_mult - 1
        self.assertGreaterEqual(gained, 0)
        self.assertLessEqual(gained, 24)  # 6 units x the +4 base
        self.assertEqual(len(self.game.score_particles), 1)

    def test_the_glitch_pays_the_same_amount_when_the_run_replays(self):
        # The roll comes from the run's own RNG (Game.run_rng), so a replayed
        # run pays what it paid before instead of rerolling until it lands high.
        paid = []
        for _ in range(2):
            self.game.run_rng.seed(self.game.run_seed)
            self.game.score_mult = 1
            self._start(main.Card.GLITCH)
            paid.append(self.game.score_mult)
        self.assertEqual(paid[0], paid[1])

    def test_the_ripped_card_pays_120_chips_on_a_small_board(self):
        self.game.grid = {}
        for gx in range(5):
            self.game.grid[(gx, 0)] = main.Block(gx, 0)
        self.game.score_chips = 1
        self._start(main.Card.RIPPED_CARD)
        self.assertEqual(self.game.score_chips, 1 + 120)
        self.assertEqual(len(self.game.score_particles), 1)

    def test_the_ripped_card_pays_nothing_on_a_big_board(self):
        self.game.grid = {}
        for gx in range(6):
            self.game.grid[(gx, 0)] = main.Block(gx, 0)
        self.game.score_chips = 1
        self.game.score_particles.clear()
        self._start(main.Card.RIPPED_CARD)
        self.assertEqual(self.game.score_chips, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_cozy_card_pays_90_chips_while_the_board_is_small(self):
        self.game.unlocked_cells = {(x, y) for x in range(4) for y in range(2)}
        self.game.score_chips = 1
        self._start(main.Card.COZY)
        self.assertEqual(self.game.score_chips, 1 + 90)
        # One more unlocked unit than the gate allows: no payout at all.
        self.game.unlocked_cells = {(x, y) for x in range(4) for y in range(3)}
        self.assertEqual(len(self.game.unlocked_cells), 12)
        self.game.score_chips = 1
        self.game.score_particles.clear()
        self._start(main.Card.COZY)
        self.assertEqual(self.game.score_chips, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_painting_pays_three_chips_a_dollar_of_board_value(self):
        self.game.grid = {}
        for gx, price in ((0, 60), (1, 40)):
            block = main.Block(gx, 0)
            block.resale_price = price
            self.game.grid[(gx, 0)] = block
        self.assertEqual(main.cards.board_sell_total(self.game), 100)
        self.game.score_chips = 1
        self._start(main.Card.PAINTING)
        self.assertEqual(self.game.score_chips, 1 + 3 * 100)

    def test_the_synthesizer_pays_three_mult_a_card(self):
        self.game.cards = _own(main.Card.SYNTHESIZER)
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 1 + 3)   # one card: itself
        # The measure is the card area, so with two Synthesizers BOTH count the
        # other (each pays for both cards) — the card rewards a full area.
        self.game.cards = _own(main.Card.SYNTHESIZER, main.Card.SYNTHESIZER)
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 1 + 3 * 2 * 2)

    def test_the_island_multiplies_by_one_point_five_a_group(self):
        # Three separated squares: three islands (corners do not connect).
        self.game.unlocked_cells = {(0, 0), (2, 0), (4, 0)}
        self.game.score_mult = 10
        self._start(main.Card.ISLAND)
        self.assertAlmostEqual(self.game.score_mult, 10 * (1 + 0.5 * 3))
        # A solid 2x3 block of units is ONE island, however big: the card
        # rewards a fragmented board, not a large one.
        self.game.unlocked_cells = {(x, y) for x in range(3) for y in range(2)}
        self.game.score_mult = 10
        self._start(main.Card.ISLAND)
        self.assertAlmostEqual(self.game.score_mult, 10 * 1.5)


class NamedCardEndTests(GameTestCase):
    """The four cards whose measure is only final once the run is over."""

    def _finish(self, *values):
        self.game.cards = _own(*values)
        self.game._apply_cards_on_finish()

    def test_the_plane_pays_fifteen_chips_an_air_second(self):
        # 2.5 airborne seconds pay a fractional 37.5 chips, kept as-is (only the
        # particle text rounds) — the rule every unit card follows.
        self.game.air_time = 2.5
        self.game.score_chips = 1
        self._finish(main.Card.PLANE)
        self.assertEqual(self.game.score_chips, 1 + 15 * 2.5)
        # No air time at all: nothing paid, nothing popped.
        self.game.air_time = 0.0
        self.game.score_chips = 1
        self.game.score_particles.clear()
        self._finish(main.Card.PLANE)
        self.assertEqual(self.game.score_chips, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_astronaut_pays_four_mult_a_black_hole_second(self):
        self.game.black_hole_time = 2.5
        self.game.score_mult = 1
        self._finish(main.Card.ASTRONAUT)
        self.assertAlmostEqual(self.game.score_mult, 1 + 4 * 2.5)

    def test_the_skater_multiplies_by_one_point_two_a_slippery_block(self):
        self.game.toolbox.items.clear()
        self.game.toolbox.add(main.BlockItem(
            0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD, 10,
            20, "S1", effects=[main.Effect.SLIPPERY]))
        self.game.grid[(0, 0)] = main.Block(0, 0, effects=[main.Effect.SLIPPERY])
        self.game.grid[(0, 1)] = main.Block(0, 1)
        self.game.score_mult = 1
        # At the start of the run it is a no-op: xMult waits for the end.
        self.game.cards = _own(main.Card.SKATER)
        self.game._apply_cards()
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.2 * 2)
        # Owning no slippery blocks is neutral — and pops nothing.
        self.game.toolbox.items.clear()
        self.game.grid = {}
        self.game.score_mult = 1
        self.game.score_particles.clear()
        self._finish(main.Card.SKATER)
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_explorer_multiplies_by_the_distance_travelled(self):
        # A full board's worth of travel is 4 units, i.e. exactly x2.
        marble = self._add_marble()
        marble.distance = main.GRID_SIZE * main.GRID_WIDTH * main.GRID_HEIGHT
        self.game.score_mult = 1
        self._finish(main.Card.EXPLORER)
        self.assertAlmostEqual(self.game.score_mult, 2.0)
        # A quarter board is x1.25: the units are 4 x the fraction travelled.
        marble.distance /= 4
        self.game.score_mult = 1
        self._finish(main.Card.EXPLORER)
        self.assertAlmostEqual(self.game.score_mult, 1.25)

    def test_the_end_cards_pay_through_a_real_run_finish(self):
        # The end-of-run cards are applied by the run's own finish path (not
        # only when a test calls them by hand): a finished run multiplies the
        # score by the Explorer's distance factor before it is finalized.
        self.game.cards = _own(main.Card.EXPLORER)
        self.game.marbles = []
        marble = self._add_marble()
        # A full board's worth of travel: 4 units, i.e. exactly x2.
        marble.distance = main.GRID_SIZE * main.GRID_WIDTH * main.GRID_HEIGHT
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = 100
        self.game.score_mult = 1
        self.game.required_score = 100
        self.game._handle_block_contacts([])
        self.assertAlmostEqual(self.game.score_mult, 2.0)
        self.assertTrue(self.game.run_complete)


class NamedCardFragileTests(GameTestCase):
    """The Wrecking Ball: +3 mult a break, banked for good."""

    def test_the_wrecking_ball_banks_three_mult_a_break(self):
        self.game.cards = _own(main.Card.WRECKING_BALL)
        self.game.score_mult = 1
        self.game.run_active = True
        self.game._on_fragile_broken(main.Block(0, 0, effect=main.Effect.FRAGILE))
        self.assertEqual(self.game.score_mult, 4)  # live
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)
        particle = self.game.score_particles[-1]
        self.assertEqual((particle.text, particle.color), ("3", main.BLUE))

    def test_the_banked_bonus_applies_at_the_start_of_every_run(self):
        self.game.cards = _own(main.Card.WRECKING_BALL)
        self.game.wrecking_bonus[main.Scorer.MULT_ADD] = 6
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 1 + 6)

    def test_a_retry_discards_the_gains_the_run_earned(self):
        self.game.cards = _own(main.Card.WRECKING_BALL)
        self.game.run_active = True
        self.game._on_fragile_broken(main.Block(0, 0, effect=main.Effect.FRAGILE))
        self._complete_run(10000, required=100)
        self.game._retry_run()
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 0)

    def test_a_blueprint_copies_the_wrecking_ball(self):
        self.game.cards = _own(main.Card.WRECKING_BALL, main.Card.BLUEPRINT)
        self.game.score_mult = 1
        self.game.run_active = True
        self.game._on_fragile_broken(main.Block(0, 0, effect=main.Effect.FRAGILE))
        self.assertEqual(self.game.score_mult, 1 + 6)  # the card and its copy
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 6)


class NamedCardOwnershipTests(GameTestCase):
    """Blueprint, the Card cutter trial, and what a named card does NOT do."""

    def test_a_blueprint_copies_a_start_card(self):
        self.game.cards = _own(main.Card.JOKER, main.Card.BLUEPRINT)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 1 + 4 + 4)
        # A Blueprint in the leftmost slot has nothing to copy.
        self.game.cards = _own(main.Card.BLUEPRINT, main.Card.JOKER)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 1 + 4)

    def test_a_blueprint_copies_an_end_card(self):
        self.game.cards = _own(main.Card.EXPLORER, main.Card.BLUEPRINT)
        marble = self._add_marble()
        marble.distance = 3000.0
        fraction = ((3000.0 / main.GRID_SIZE)
                    / (main.GRID_WIDTH * main.GRID_HEIGHT))
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, (1 + fraction) ** 2)

    def test_the_card_cutter_trial_takes_a_named_card_out_of_the_run(self):
        joker = main.CardItem(main.Card.JOKER, 20)
        self.game.cards = [joker]
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game._apply_trial()
        self.assertIs(self.game.disabled_card, joker)
        self.game.reset_run(False)
        self.assertEqual(self.game.score_mult, 1)   # the Joker was cut
        self.assertEqual(self.game.score_chips, 1)

    def test_a_named_card_does_nothing_on_a_collision(self):
        # A named card fires at its own moment, never on a hit: colliding with a
        # block leaves the score exactly as the block's own scorer left it.
        self.game.cards = _own(main.Card.JOKER, main.Card.BANKER,
                               main.Card.RIPPED_CARD)
        block = main.Block(0, 0, shape=main.Shape.PIPE)
        self.game.score_chips = 0
        self.game.score_mult = 1
        self.game.run_active = True
        block.triggers_left = 1
        main.cards.apply_card_on_collision(self.game, block)
        self.assertEqual(self.game.score_chips, 0)
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_a_named_card_is_never_sold_as_a_scorer_card(self):
        # A named card carries no scorer half, so the shop rolls no magnitude
        # for it and the card pays, prices and describes itself as it stands
        # (see components.card_scorer / make_card_item).
        for value in components.NAMED_CARD_ORDER:
            self.assertIsNone(components.card_scorer(value),
                              main.Card.name(value))
            self.assertEqual(main.CardItem(value, main.Card.PRICES[value]).amount,
                             0, main.Card.name(value))
        self.game.cards = _own(main.Card.JOKER)
        self.assertEqual(main.cards.effective_card_value(self.game, 0),
                         main.Card.JOKER)
        self.assertEqual(main.cards.effective_card_amount(self.game, 0), 0)
