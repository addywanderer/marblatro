"""The measured whole cards: the fourteen classic cards, plus Fountain and
Intangible.

Each named CONDITION the card system was built around is one whole card again
(user request: "add back the named conditions you commented out, as
unsplittable cards"), so the trigger and the payoff live in the card: nothing is
composed, nothing splits, and nothing is rolled — a Joker always pays +4 mult.
The Fountain (user request: "add a card, fountain, that gives +0.25 xmult for
each time a marble consecutively touches 3 different blocks with each one in the
pipe group") and the Intangible (user request: "add a card, 'intangible', which
gives +0.5 mult for each second a marble is inside a block and +15 mult for
each second the marble is inside a locked board unit") are the two cards in that
table which never were named conditions: they are measured exactly the same way,
so they play through the same machinery.

The payoffs are the canonical (condition x scorer) pairings the named conditions
came from, on the magnitude model every card used then: one unit is
+30 chips / +4 mult / +0.25 xMult, scaled by the card's ratio (see
components.Card.NAMED). So Joker ratio 1.0 is +4 mult, Pillar 0.25 is +1 mult a
column block, Plane 0.5 is +15 chips an air second, Banker 1/30 is +1 chip per
$10, Ripped Card 4.0 is +120 chips, Island 2.0 is +0.5 xMult a group, Fountain
1.0 is +0.25 xMult a pipe streak, and Intangible 0.125 is +0.5 mult an inside
second (+15 for a locked-unit second, the same measure weighted 30x).

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
    """The measured cards exist, priced, tiered, drawn and unsplittable."""

    def test_the_measured_cards_are_whole_cards(self):
        names = [main.Card.name(value) for value in components.NAMED_CARD_ORDER]
        self.assertEqual(names,
                         ["Joker", "Explorer", "Astronaut", "Plane", "Pillar",
                          "Banker", "Wrecking Ball", "Skater", "Glitch",
                          "Ripped Card", "Cozy", "Painting", "Synthesizer",
                          "Island", "Fountain", "Intangible",
                          "Swashbuckler", "Stencil"])
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
                                  "Synthesizer", "Swashbuckler", "Stencil"})
        self.assertEqual(ends, {"Explorer", "Astronaut", "Plane", "Skater",
                                "Fountain", "Island", "Intangible"})
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
        # Fountain never was a named condition, so its row is the one card here
        # whose ratio (1.0) was chosen rather than inherited: 1.0 x the standard
        # +0.25 xMult base is the +0.25 the card asks for.
        expected = {
            "Joker": ("start", main.Scorer.MULT_ADD, 1.0, "start"),
            "Explorer": ("end", main.Scorer.MULT_MUL, 1.0, "visited_units"),
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
            "Island": ("end", main.Scorer.MULT_MUL, 2.0, "island"),
            "Fountain": ("end", main.Scorer.MULT_MUL, 1.0, "pipe_streak"),
            "Intangible": ("end", main.Scorer.MULT_ADD, 0.125, "inside_time"),
            "Swashbuckler": ("start", main.Scorer.MULT_ADD, 1.0 / 20.0,
                             "card_sell_total"),
            "Stencil": ("start", main.Scorer.MULT_MUL, 4.0, "stencil_slots"),
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
            elif price <= 44:
                self.assertEqual(tier, components.Rarity.RARE,
                                 main.Card.name(value))
            elif price <= 47:
                self.assertEqual(tier, components.Rarity.EPIC,
                                 main.Card.name(value))
            else:
                self.assertEqual(tier, components.Rarity.LEGENDARY,
                                 main.Card.name(value))
        # Twelve cheap measured cards and the four dear ones ($32/$34): every
        # one of the cheap ones is a Common or an Unusual. The two newest are
        # the measured cards' first dear tiers: Swashbuckler ($42) is Rare and
        # Stencil ($46) is Epic.
        self.assertEqual(tiers[components.Rarity.COMMON], 12)
        self.assertEqual(tiers[components.Rarity.UNUSUAL], 4)
        self.assertEqual({main.Card.rarity(v) for v in
                          (main.Card.EXPLORER, main.Card.SKATER,
                           main.Card.ISLAND, main.Card.FOUNTAIN)},
                         {components.Rarity.UNUSUAL})
        self.assertEqual(main.Card.rarity_name(main.Card.SWASHBUCKLER), "Rare")
        self.assertEqual(main.Card.rarity_name(main.Card.STENCIL), "Epic")

    def test_every_measured_card_has_icon_art(self):
        # The card face draws the named condition's own art (the jester's hat,
        # the compass, the column, ...), so no card here falls back to a letter
        # and no two of them wear the same picture.
        drawings = set()
        for value in components.NAMED_CARD_ORDER:
            art = main.ui._whole_card_art(value)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               main.Card.name(value))
            drawings.add(pygame.image.tobytes(art, "RGBA"))
        self.assertEqual(len(drawings), 18)

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
    """The eleven cards that fire at the start of a run."""

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





class NamedCardEndTests(GameTestCase):
    """The cards whose measure is only final once the run is over."""

    def _finish(self, *values):
        """Own the cards, run the end step, and settle the banked xMult.

        The run's own finish path calls _apply_cards_on_finish and then
        _flush_run_xmult (see Game._handle_block_contacts), so a test that
        reads the multiplier afterwards has to do both.
        """
        self.game.cards = _own(*values)
        self.game._apply_cards_on_finish()
        self.game._flush_run_xmult()

    def test_the_island_multiplies_by_one_point_five_a_group(self):
        # Island is an xMult card, so it fires as the run SETTLES (see the
        # Card.NAMED row): three separated squares are three islands (corners do
        # not connect), and the factor lands with the rest of the xMult bank.
        self.game.unlocked_cells = {(0, 0), (2, 0), (4, 0)}
        self.game.score_mult = 10
        self._finish(main.Card.ISLAND)
        self.assertAlmostEqual(self.game.score_mult, 10 * (1 + 0.5 * 3))
        # A solid 2x3 block of units is ONE island, however big: the card
        # rewards a fragmented board, not a large one.
        self.game.unlocked_cells = {(x, y) for x in range(3) for y in range(2)}
        self.game.score_mult = 10
        self._finish(main.Card.ISLAND)
        self.assertAlmostEqual(self.game.score_mult, 10 * 1.5)


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
        # At the start of the run it is a no-op: Island, Skater and the other
        # xMult cards all wait for the run to settle.
        self.game.cards = _own(main.Card.SKATER)
        self.game._apply_cards()
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        self._finish(main.Card.SKATER)
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.2 * 2)
        # Owning no slippery blocks is neutral — and pops nothing.
        self.game.toolbox.items.clear()
        self.game.grid = {}
        self.game.score_mult = 1
        self.game.score_particles.clear()
        self._finish(main.Card.SKATER)
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_explorer_multiplies_by_the_units_the_marble_has_been_in(self):
        # The measure is the fraction of the board's units a marble has BEEN IN
        # this run, recorded square by square as the run plays: the whole board
        # is 4 units, i.e. exactly x2.
        self.game.visited_cells = {
            (gx, gy) for gx in range(main.GRID_WIDTH)
            for gy in range(main.GRID_HEIGHT)}
        self.game.score_mult = 1
        self._finish(main.Card.EXPLORER)
        self.assertAlmostEqual(self.game.score_mult, 2.0)
        # Half the board is x1.5: the payoff is +1 xMult per whole board.
        self.game.visited_cells = {
            (gx, gy) for gx in range(main.GRID_WIDTH // 2)
            for gy in range(main.GRID_HEIGHT)}
        self.game.score_mult = 1
        self._finish(main.Card.EXPLORER)
        self.assertAlmostEqual(self.game.score_mult, 1.5)
        # One unit of the 150 is x1.0066...: the payoff is exactly
        # +0 xMult to +1 xMult, in proportion to the fraction covered.
        self.game.visited_cells = {(4, 7)}
        self.game.score_mult = 1
        self._finish(main.Card.EXPLORER)
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 1 / (main.GRID_WIDTH * main.GRID_HEIGHT))

    def test_the_explorer_does_not_pay_for_distance_travelled(self):
        # The measure used to be the distance the marble travelled; it is now
        # the units it has been in, so a marble that has covered the whole
        # board's length in pixels but has not recorded a single unit pays
        # nothing (the recorded set — not marble.distance — is the measure).
        marble = self._add_marble()
        marble.distance = main.GRID_SIZE * main.GRID_WIDTH * main.GRID_HEIGHT
        self.game.visited_cells = set()
        self.game.score_mult = 1
        self._finish(main.Card.EXPLORER)
        self.assertAlmostEqual(self.game.score_mult, 1.0)

    def test_the_end_cards_pay_through_a_real_run_finish(self):
        # The end-of-run cards are applied by the run's own finish path (not
        # only when a test calls them by hand): a finished run multiplies the
        # score by the Explorer's visited-units factor before it is finalized.
        self.game.cards = _own(main.Card.EXPLORER)
        self.game.marbles = []
        marble = self._add_marble()
        # The whole board visited: 4 units, i.e. exactly x2.
        self.game.visited_cells = {
            (gx, gy) for gx in range(main.GRID_WIDTH)
            for gy in range(main.GRID_HEIGHT)}
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = 100
        self.game.score_mult = 1
        self.game.required_score = 100
        self.game._handle_block_contacts([])
        self.assertAlmostEqual(self.game.score_mult, 2.0)
        self.assertTrue(self.game.run_complete)


class FountainTests(GameTestCase):
    """The Fountain: +0.25 xMult for every 3 different pipe blocks in a row."""

    def _pipe(self, shape, gx):
        """A plain pipe-group block on the board, at column ``gx``."""
        block = main.Block(gx, 0, shape=shape)
        self.game.grid[(gx, 0)] = block
        return block

    def _touch(self, block):
        """One FRESH contact with a block, through the real contact handler.

        Physics raises and lowers ``collisions_this_tick`` as the marble enters
        and leaves a block, so writing the tick's contact list by hand is how
        every other contact test drives a touch (see GameTestCase._touch_block).
        """
        marble = (self.game.marbles[0] if self.game.marbles
                  else self._add_marble())
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])

    def test_the_fountain_counts_the_pipe_group_of_shapes(self):
        # The group is the three shapes the user named — Pipe Bend, Pipe and
        # Drain — and it is literally the match-group catalogue's pipe group, so
        # the card and the Pipe/Drain/Pipe Bend cards can never disagree about
        # what a pipe is.
        self.assertEqual(components.PIPE_GROUP_SHAPES,
                         (main.Shape.PIPE, main.Shape.DRAIN,
                          main.Shape.PIPE_BEND))
        self.assertIs(components.SHAPE_GROUPS[0], components.PIPE_GROUP_SHAPES)
        self.assertEqual(main.FOUNTAIN_STREAK_LENGTH, 3)
        self.assertIn("Pipe, Drain or Pipe Bend",
                      main.Card.description(main.Card.FOUNTAIN))
        self.assertIn("0.25 xMult", main.Card.description(main.Card.FOUNTAIN))
        self.assertEqual(main.Card.rarity_name(main.Card.FOUNTAIN), "Unusual")

    def test_three_different_pipe_blocks_in_a_row_pay_a_quarter_xmult(self):
        self.game.cards = _own(main.Card.FOUNTAIN)
        for gx, shape in enumerate((main.Shape.PIPE, main.Shape.PIPE_BEND,
                                    main.Shape.DRAIN)):
            self._touch(self._pipe(shape, gx))
        self.assertEqual(self.game.pipe_streak_run_units, 1)
        self.game.score_mult = 10
        self.game._apply_cards_on_finish()
        self.game._flush_run_xmult()
        self.assertAlmostEqual(self.game.score_mult, 10 * 1.25)
        self.assertEqual(len(self.game.score_particles), 2)   # + the settlement

    def test_the_streak_wants_three_DIFFERENT_blocks(self):
        # Touching one pipe block again is not a new block: it neither advances
        # the streak nor breaks it (the marble rolls along a pipe's own wall for
        # many frames), so the group completes on the third DIFFERENT block.
        pipe = self._pipe(main.Shape.PIPE, 0)
        drain = self._pipe(main.Shape.DRAIN, 1)
        bend = self._pipe(main.Shape.PIPE_BEND, 2)
        for block in (pipe, pipe, drain):
            self._touch(block)
        # pipe, pipe, drain is only TWO different blocks: no group yet.
        self.assertEqual(self.game.pipe_streak_run_units, 0)
        self.assertEqual(self.game.pipe_streak_blocks, [pipe, drain])
        self._touch(bend)
        self.assertEqual(self.game.pipe_streak_run_units, 1)
        self.assertEqual(self.game.pipe_streak_blocks, [])

    def test_any_other_block_breaks_the_streak(self):
        pipe = self._pipe(main.Shape.PIPE, 0)
        drain = self._pipe(main.Shape.DRAIN, 1)
        wall = main.Block(5, 0, shape=main.Shape.RECT)
        self.game.grid[(5, 0)] = wall
        for block in (pipe, drain, wall):
            self._touch(block)
        # Two pipe blocks and then something else: the streak is gone, and the
        # next pipe block starts a fresh one from scratch.
        self.assertEqual(self.game.pipe_streak_blocks, [])
        self._touch(self._pipe(main.Shape.PIPE_BEND, 2))
        self.assertEqual(self.game.pipe_streak_run_units, 0)
        self.assertEqual(len(self.game.pipe_streak_blocks), 1)

    def test_a_longer_chain_pays_a_group_for_every_three(self):
        shapes = (main.Shape.PIPE, main.Shape.DRAIN, main.Shape.PIPE_BEND,
                  main.Shape.PIPE, main.Shape.DRAIN, main.Shape.PIPE_BEND)
        for gx, shape in enumerate(shapes):
            self._touch(self._pipe(shape, gx))
        self.game.cards = _own(main.Card.FOUNTAIN)
        self.game.score_mult = 4
        self.game._apply_cards_on_finish()
        self.game._flush_run_xmult()
        # Two groups pay +0.25 each: ONE x1.5 factor, not two compounded x1.25s,
        # exactly as the other measured xMult cards pay (Island's groups, the
        # Skater's slippery blocks, the Explorer's visited units).
        self.assertAlmostEqual(self.game.score_mult, 4 * (1 + 0.25 * 2))

    def test_no_streak_pays_nothing(self):
        self.game.cards = _own(main.Card.FOUNTAIN)
        self.game.score_mult = 7
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_mult, 7)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_streak_belongs_to_the_run(self):
        for gx, shape in enumerate((main.Shape.PIPE, main.Shape.DRAIN,
                                    main.Shape.PIPE_BEND)):
            self._touch(self._pipe(shape, gx))
        self.assertEqual(self.game.pipe_streak_run_units, 1)
        self.game.grid[(9, 9)] = main.Block(9, 9, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.pipe_streak_run_units, 0)
        self.assertEqual(self.game.pipe_streak_blocks, [])


class IntangibleTests(GameTestCase):
    """The Intangible: +0.5 mult an inside second, +15 inside a locked unit."""

    def test_the_card_prices_and_describes_its_two_rates(self):
        self.assertEqual(main.Card.name(main.Card.INTANGIBLE), "Intangible")
        self.assertEqual(main.Card.PRICES[main.Card.INTANGIBLE], 26)
        self.assertEqual(main.Card.rarity_name(main.Card.INTANGIBLE), "Common")
        description = main.Card.description(main.Card.INTANGIBLE)
        self.assertIn("0.5 mult", description)
        self.assertIn("15 a second", description)
        self.assertIn("locked board unit", description)
        self.assertIn("at the end of the run", description)

    def test_it_pays_half_a_mult_for_each_second_inside_a_block(self):
        # 4 inside seconds x 0.5 = +2 mult, paid as the run settles (the measure
        # is only final once the marbles have stopped).
        self.game.cards = _own(main.Card.INTANGIBLE)
        self.game.inside_block_time = 4.0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.5 * 4)
        self.assertEqual(len(self.game.score_particles), 1)
        # The two clauses add up: 4 block seconds and 1 locked-unit second pay
        # +2 and +15 on top of the same run's mult.
        self.game.inside_locked_time = 1.0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.5 * 4 + 15)

    def test_owning_no_intangible_pays_nothing(self):
        # The counters fill up for every run; only the card turns them into mult.
        self.game.inside_block_time = 4.0
        self.game.inside_locked_time = 1.0
        self.game.score_mult = 1
        self.game.score_particles.clear()
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_it_pays_fifteen_mult_for_each_second_in_a_locked_unit(self):
        self.game.cards = _own(main.Card.INTANGIBLE)
        self.game.inside_locked_time = 2.0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 15 * 2)

    def test_no_time_inside_pays_nothing(self):
        self.game.cards = _own(main.Card.INTANGIBLE)
        self.game.score_mult = 7
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_mult, 7)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_the_measure_weights_a_locked_unit_second_thirty_times(self):
        # One ratio has to serve both rates, so the measure counts a locked-unit
        # second as 30 ordinary ones (15 / 0.5) — checked on the measure itself,
        # the way every other card's units are (see cards._named_card_units).
        self.game.inside_block_time = 3.0
        self.game.inside_locked_time = 0.5
        self.assertAlmostEqual(main.cards._named_card_units(self.game, "inside_time"),
                               3.0 + 30 * 0.5)

    def test_a_marble_phasing_through_a_block_banks_inside_time(self):
        # "Inside" is any overlap with a block's HITBOX, which only the phase
        # effect can produce: a phasing marble flies through the solid and banks
        # every frame it is in there, and the end card turns those seconds into
        # mult.
        self.game.cards = _own(main.Card.INTANGIBLE)
        self.game.grid.clear()
        block = main.Block(4, 5, shape=main.Shape.RECT)
        self.game.grid[(4, 5)] = block
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.upgrades_enabled = False
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.inside_block_time, 0.0)
        marble = self.game.marbles[0]
        marble.position = np.array([block.rect.centerx, block.rect.top - 20],
                                   dtype=float)
        marble.velocity = np.array([0.0, 200.0])
        marble.phase_timer = 5.0
        for _ in range(60):
            marble.phase_timer = max(marble.phase_timer, 5.0)  # keep it phasing
            self.game.update()
            if marble.position[1] > block.rect.bottom + 20:
                break
        self.assertGreater(self.game.inside_block_time, 0.0)
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.5 * self.game.inside_block_time)

    def test_touching_or_passing_through_a_block_is_not_inside_it(self):
        # A marble that rests on a block, sits in a pipe's cavity, crosses a
        # Shape.NONE field or is merely inside a block's grid CELL touches no
        # hitbox at all, so none of those seconds count: every position that
        # banks time is one the marble could only reach by phasing.
        self.game.grid.clear()
        resting = main.Block(4, 5, shape=main.Shape.RECT)
        self.game.grid[(4, 5)] = resting
        # Exactly on the surface: the centre sits one radius above the top edge.
        marble = self._add_marble((resting.rect.centerx,
                                   resting.rect.top - main.MARBLE_RADIUS))
        self.assertFalse(marble.physics.overlaps_block(marble, resting))
        self.game._count_inside_time(marble)
        self.assertEqual(self.game.inside_block_time, 0.0)
        # Sitting in the pipe's cavity: inside the CELL, clear of the pillars.
        pipe = main.Block(6, 5, shape=main.Shape.PIPE)
        self.game.grid[(6, 5)] = pipe
        marble.position = np.array([pipe.rect.centerx, pipe.rect.centery], dtype=float)
        self.assertFalse(marble.physics.overlaps_block(marble, pipe))
        self.game._count_inside_time(marble)
        self.assertEqual(self.game.inside_block_time, 0.0)
        # A Shape.NONE field has no hitbox to be inside of.
        field = main.Block(8, 5, shape=main.Shape.NONE)
        self.game.grid[(8, 5)] = field
        marble.position = np.array([field.rect.centerx, field.rect.centery],
                                   dtype=float)
        self.assertFalse(marble.physics.overlaps_block(marble, field))
        self.game._count_inside_time(marble)
        self.assertEqual(self.game.inside_block_time, 0.0)
        # ...and overlapping the block's real solid DOES bank a frame.
        marble.position = np.array([resting.rect.centerx, resting.rect.centery],
                                   dtype=float)
        self.assertTrue(marble.physics.overlaps_block(marble, resting))
        self.game._count_inside_time(marble)
        self.assertAlmostEqual(self.game.inside_block_time, main.DT)

    def test_inside_a_locked_board_unit_banks_that_time_too(self):
        # A locked square is solid, so a marble can only be inside one by
        # phasing — but then the second counts, at the locked rate (the measure
        # weights it 30x), and it is counted apart from the inside-a-block time.
        self.game.grid.clear()
        self.game.unlocked_cells = {(x, y) for x in range(6) for y in range(2)}
        self.game._board_walls_dirty = True
        marble = self._add_marble((main.MARBLE_BOX_COORDS[0] + 5 * main.GRID_SIZE + 20,
                                   main.MARBLE_BOX_COORDS[1] + 5 * main.GRID_SIZE + 20))
        self.game._count_inside_time(marble)
        self.assertEqual(self.game.inside_locked_time, main.DT)
        self.assertEqual(self.game.inside_block_time, 0.0)
        # Resting in an UNLOCKED unit with no blocks around banks nothing (the
        # board holds no placed blocks either).
        marble.position = np.array([main.MARBLE_BOX_COORDS[0] + 20,
                                    main.MARBLE_BOX_COORDS[1] + 20], dtype=float)
        self.game._count_inside_time(marble)
        self.assertEqual(self.game.inside_locked_time, main.DT)
        # A fully unlocked board has no locked units at all.
        self.game.unlocked_cells = {(x, y) for x in range(main.GRID_WIDTH)
                                    for y in range(main.GRID_HEIGHT)}
        self.game._board_walls_dirty = True
        marble.position = np.array([main.MARBLE_BOX_COORDS[0] + 5 * main.GRID_SIZE + 20,
                                    main.MARBLE_BOX_COORDS[1] + 5 * main.GRID_SIZE + 20],
                                   dtype=float)
        self.game._count_inside_time(marble)
        self.assertEqual(self.game.inside_locked_time, main.DT)

    def test_the_inside_time_belongs_to_the_run(self):
        self.game.inside_block_time = 2.0
        self.game.inside_locked_time = 1.0
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.inside_block_time, 0.0)
        self.assertEqual(self.game.inside_locked_time, 0.0)


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
        # Half the board visited: 2 units, i.e. x1.5, paid twice (the card and
        # the Blueprint's copy of it).
        self.game.visited_cells = {
            (gx, gy) for gx in range(main.GRID_WIDTH // 2)
            for gy in range(main.GRID_HEIGHT)}
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.game._flush_run_xmult()
        self.assertAlmostEqual(self.game.score_mult, 1.5 ** 2)

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


class SwashbucklerTests(GameTestCase):
    """Swashbuckler: +mult equal to a fifth of the cards' total sell price."""

    def _sell_total(self):
        """The sell price of every card the player owns."""
        return sum(self.game._sell_price(card) for card in self.game.cards)

    def test_the_card_data(self):
        self.assertEqual(main.Card.name(main.Card.SWASHBUCKLER), "Swashbuckler")
        self.assertEqual(main.Card.PRICES[main.Card.SWASHBUCKLER], 42)
        self.assertEqual(main.Card.rarity_name(main.Card.SWASHBUCKLER), "Rare")
        self.assertTrue(main.Card.comment(main.Card.SWASHBUCKLER))
        self.assertIn("1/5", main.Card.description(main.Card.SWASHBUCKLER))
        self.assertIn("sell price", main.Card.description(main.Card.SWASHBUCKLER))

    def test_it_pays_a_fifth_of_the_cards_sell_price(self):
        # Coupon and Market are passive, so the only start-of-run payoff in the
        # area is the Swashbuckler's own.
        self.game.cards = _own(main.Card.SWASHBUCKLER, main.Card.COUPON,
                               main.Card.MARKET)
        expected = self._sell_total() / 5
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertAlmostEqual(self.game.score_mult, 1 + expected)
        # Its own price counts, so the card is never worth nothing on its own.
        self.game.cards = _own(main.Card.SWASHBUCKLER)
        self.game.score_mult = 1
        self.game._apply_cards()
        alone = self.game.score_mult - 1
        self.assertGreater(alone, 0)
        self.assertAlmostEqual(alone, self._sell_total() / 5)

    def test_a_dearer_card_pays_more(self):
        # The measure is the cards' worth, so swapping a cheap card for a dear
        # one raises the payoff instead of leaving it alone.
        self.game.cards = _own(main.Card.SWASHBUCKLER, main.Card.RIPPED_CARD)
        self.game.score_mult = 1
        self.game._apply_cards()
        cheap = self.game.score_mult
        self.game.cards = _own(main.Card.SWASHBUCKLER, main.Card.INFINITY)
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertGreater(self.game.score_mult, cheap)

    def test_the_measure_is_the_same_sell_price_a_sale_refunds(self):
        # The Market card refunds 75% instead of 50%, and Swashbuckler reads the
        # same number a sale would pay, so Market raises the card's mult too.
        self.game.cards = _own(main.Card.SWASHBUCKLER, main.Card.COUPON)
        self.game.score_mult = 1
        self.game._apply_cards()
        plain = self.game.score_mult - 1
        self.game.cards.append(main.CardItem(main.Card.MARKET, 26))
        expected = self._sell_total() / 5
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertGreater(self.game.score_mult - 1, plain)
        self.assertAlmostEqual(self.game.score_mult - 1, expected)

    def test_the_particle_takes_the_blue_mult_colour(self):
        self.game.cards = _own(main.Card.SWASHBUCKLER)
        self.game.score_particles.clear()
        self.game._apply_cards()
        self.assertEqual(len(self.game.score_particles), 1)
        self.assertEqual(self.game.score_particles[0].color, main.BLUE)


class StencilTests(GameTestCase):
    """Stencil: +1 xMult for each card slot no OTHER card is filling."""

    def _start(self, *values):
        """Own the cards, fire the start of the run, and settle the xMult.

        An xMult a card earns is BANKED for the run and lands when the run
        settles (see Game._apply_xmult / _flush_run_xmult), so a test reading
        the multiplier has to settle it — the same two steps a finished run
        takes (see NamedCardEndTests._finish).
        """
        self.game.cards = _own(*values)
        self.game.score_mult = 1
        self.game._apply_cards()
        self.game._flush_run_xmult()

    def test_the_card_data(self):
        self.assertEqual(main.Card.name(main.Card.STENCIL), "Stencil")
        self.assertEqual(main.Card.PRICES[main.Card.STENCIL], 46)
        self.assertEqual(main.Card.rarity_name(main.Card.STENCIL), "Epic")
        self.assertTrue(main.Card.comment(main.Card.STENCIL))
        self.assertIn("+1 xMult", main.Card.description(main.Card.STENCIL))
        self.assertIn("empty card slot", main.Card.description(main.Card.STENCIL))

    def test_stencil_alone_in_five_slots_multiplies_by_five(self):
        # The user's example: only the Stencil, five card slots in all, so all
        # five count (its own slot included) and the multiplier goes x5.
        self.assertEqual(self.game.max_cards, 5)
        self._start(main.Card.STENCIL)
        self.assertEqual(self.game.score_mult, 5)

    def test_every_other_card_costs_it_a_whole_x_mult(self):
        self._start(main.Card.STENCIL, main.Card.COUPON)
        self.assertEqual(self.game.score_mult, 4)     # four slots, x4
        self._start(main.Card.STENCIL, main.Card.COUPON, main.Card.MARKET,
                    main.Card.MINESHAFT)
        self.assertEqual(self.game.score_mult, 2)     # one slot left, x2

    def test_a_full_card_area_leaves_it_nothing_to_multiply(self):
        # Every other slot taken: there is no headroom left, so the card pays
        # nothing at all (its gate, exactly like Island with no groups).
        self.game.cards = _own(main.Card.STENCIL, main.Card.COUPON,
                               main.Card.MARKET, main.Card.MINESHAFT,
                               main.Card.GARDEN)
        self.assertEqual(len(self.game.cards), self.game.max_cards)
        self.assertEqual(main.cards.stencil_units(self.game), 0)
        self.game.score_mult = 1
        self.game.score_particles.clear()
        self.game._apply_cards()
        self.game._flush_run_xmult()
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(len(self.game.score_particles), 0)

    def test_essence_takes_a_slot_away_from_the_count(self):
        # Essence shrinks the card area itself (Game.max_cards), so the Stencil
        # counts one slot fewer: with Essence beside it there are three slots
        # that no other card is filling, so the multiplier goes x3.
        self.game.cards = _own(main.Card.STENCIL, main.Card.ESSENCE)
        self.assertEqual(self.game.max_cards, 4)
        self.assertEqual(main.cards.stencil_units(self.game), 2)
        self.game.score_mult = 1
        self.game._apply_cards()
        self.game._flush_run_xmult()
        self.assertEqual(self.game.score_mult, 3)

    def test_a_second_stencil_multiplies_by_the_same_number_again(self):
        self._start(main.Card.STENCIL, main.Card.STENCIL)
        self.assertEqual(self.game.score_mult, 25)    # x5 then x5

    def test_a_cut_stencil_does_nothing(self):
        # The Card cutter silences the card's effect, so no xMult lands.
        stencil = main.CardItem(main.Card.STENCIL, 46)
        self.game.cards = [stencil]
        self.game.disabled_card = stencil
        self.game.score_mult = 1
        self.game._apply_cards()
        self.game._flush_run_xmult()
        self.assertEqual(self.game.score_mult, 1)
