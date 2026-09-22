"""One scorer's payoff, behaviour and description.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class ScorersTests(GameTestCase):
    """One scorer's payoff, behaviour and description."""


    def test_none_scorer_block_still_triggers_for_red_border(self):
        # A Scorer.NONE block grants no chips, but it still "triggers" when a
        # marble touches it, so it shows the used (red border) state.
        block = main.Block(0, 0, scorer=main.Scorer.NONE)
        marble = self._add_marble()
        self.game.run_active = True
        self.assertEqual(block.triggers_left, 1)

        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])

        self.assertEqual(block.triggers_left, 0)  # red border state
        self.assertEqual(self.game.score_chips, 0)  # no score effect
        self.assertEqual(self.game.score_mult, 1)


    def test_no_effect_none_scorer_block_stays_black(self):
        # A plain wall (no effect, scorer None) keeps the dark wall look.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            self.assertEqual(surface.get_at(
                (main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3], main.BLACK)
        finally:
            main.BLOCK_BORDERS_ON = prev


    def test_mult_scorer_multiplies_score(self):
        block = main.Block(0, 0, scorer=main.Scorer.MULT_MUL)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 1.5)
        self.assertEqual(self.game.score_chips, 0)


    def test_quick_scorer_adds_chips_based_on_marble_speed(self):
        block = main.Block(0, 0, scorer=main.Scorer.QUICK)
        marble = self._add_marble()
        marble.velocity = np.array([2000.0, 0.0])
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_chips = 0

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_chips, int(2000.0 * main.QUICK_SCALE))
        self.assertEqual(block.triggers_left, 0)  # a scoring block, once per run


    def test_quick_scorer_rewards_faster_marbles_more(self):
        self.game.run_active = True
        gains = []
        for speed in (1000.0, 4000.0):
            block = main.Block(0, 0, scorer=main.Scorer.QUICK)
            marble = self._add_marble()
            marble.velocity = np.array([speed, 0.0])
            marble.collisions_this_tick = [block]
            self.game.score_chips = 0
            self.game._handle_block_contacts([block])
            gains.append(self.game.score_chips)

        self.assertGreater(gains[1], gains[0])


    def test_quick_scorer_scores_with_effects_that_pin_marble(self):
        # Effects that hold the marble to rest at the scoring moment (gravity,
        # accelerator, black hole, slippery, fragile) used to read as zero speed
        # and award 0 chips. Quick now measures the marble's recent peak speed
        # at impact, so every effect still scores.
        for eff in (main.Effect.GRAVITY, main.Effect.ACCELERATOR,
                    main.Effect.BLACK_HOLE, main.Effect.SLIPPERY,
                    main.Effect.FRAGILE):
            chips, block = self._run_quick_drop(eff)
            self.assertGreater(chips, 0, f"{main.Effect.name(eff)} Quick should score")
            self.assertEqual(block.triggers_left, 0)


    def test_quick_scorer_scores_on_rotating_block(self):
        chips, block = self._run_quick_drop(main.Effect.ROTATE)
        self.assertGreater(chips, 0, "Rotate Quick should score")
        self.assertEqual(block.triggers_left, 0)


    def test_pipe_scorer_triggers_when_marble_passes_through_gap(self):
        # A marble passing through a pipe's central cavity (without touching
        # the pillars) still triggers the pipe's scorer.
        chips, left = self._pipe_drop()
        self.assertEqual(chips, 30)
        self.assertEqual(left, 0)


    def test_pipe_scorer_triggers_through_rotated_gap(self):
        # The A key rotates a pipe to a horizontal gap; passing through that
        # cavity also triggers the scorer.
        chips, left = self._pipe_drop(angle=90)
        self.assertEqual(chips, 30)
        self.assertEqual(left, 0)


    def test_cash_scorer_gives_dollars_when_touched(self):
        block = main.Block(0, 0, scorer=main.Scorer.CASH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.cash = 100

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.cash, 115)  # $15 per trigger
        self.assertEqual(block.triggers_left, 0)


    def test_cash_and_lucky_cash_count_to_last_run_cash_gained(self):
        # Cash-scorer and Lucky $40 payouts are added to cash as they happen,
        # tracked in run_cash_gained, and then folded into last_run_cash_gained
        # when the run is awarded — so every dollar earned shows up there.
        self.game.cash = 0
        # Touch a Cash block: +$15.
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        m = self._add_marble()
        m.collisions_this_tick = [cash_block]
        self.game.run_active = True
        self.game._handle_block_contacts([cash_block])
        # Land a Lucky cash roll: +$40.
        lucky = main.Block(0, 0, scorer=main.Scorer.LUCKY)
        m2 = self._add_marble()
        m2.collisions_this_tick = [lucky]
        with mock.patch("main.random.random", side_effect=[0.9, 0.0]):
            self.game._handle_block_contacts([lucky])
        self.assertEqual(self.game.run_cash_gained, 55)
        self.assertEqual(self.game.cash, 55)

        # Award a run with no score-based gain: flat $20 + 10% interest on the
        # 55 held ($5). The whole 55 is folded into last_run_cash_gained.
        self.game.score_total = 1
        self.game._award_cash()
        self.assertEqual(self.game.run_cash_gained, 0)  # folded & cleared
        self.assertEqual(self.game.cash, 55 + 20 + 5)
        self.assertEqual(self.game.last_run_cash_gained, 55 + 20 + 5)


    def test_retry_rolls_back_cash_and_lucky_cash_too(self):
        # Because mid-run Cash/Lucky cash is folded into last_run_cash_gained,
        # retrying the run removes it all — a retry can't farm scorer cash.
        self.game.cash = 0
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        m = self._add_marble()
        m.collisions_this_tick = [cash_block]
        self.game.run_active = True
        self.game._handle_block_contacts([cash_block])  # +$15
        self.game.score_total = 1
        self.game._award_cash()  # $20 + $1 interest folds the $15 in
        self.assertEqual(self.game.last_run_cash_gained, 36)
        self.assertEqual(self.game.cash, 36)
        self.game.run_results.append(True)
        self.game.runs_cleared = 1
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            self.game._retry_run()
        self.assertEqual(self.game.cash, 0)
        self.assertEqual(self.game.last_run_cash_gained, 0)


    def test_sharp_scorer_triples_mult_when_touched(self):
        block = main.Block(0, 0, scorer=main.Scorer.SHARP)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 3)  # 1 * 3
        self.assertEqual(block.triggers_left, 0)


    def test_sharp_scorer_block_destroyed_on_continue(self):
        # Sharp blocks have a 1/4 chance to be destroyed when the player moves
        # on from a run; non-Sharp blocks always survive.
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.SHARP)
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.SHARP)
        self.game.grid[(3, 3)] = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD,
                                             scorer_amount=10)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.0):  # always destroyed
            self.game._continue_run()
        self.assertNotIn((1, 1), self.game.grid)
        self.assertNotIn((2, 2), self.game.grid)
        self.assertIn((3, 3), self.game.grid)


    def test_sharp_scorer_block_survives_continue_when_lucky(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.SHARP)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):  # no destruction
            self.game._continue_run()
        self.assertIn((1, 1), self.game.grid)


    def test_parts_scorer_banks_a_component_per_trigger(self):
        # Parts banks one component per trigger and hands NOTHING over while
        # the run plays: the bank is granted only once the player continues
        # the run. (Its old point system stays gone — no points are banked.)
        self.game.toolbox.items.clear()
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.PARTS)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self._component_count(), 0)      # nothing granted yet
        self.assertEqual(self.game.parts_run_gain, 2)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self._component_count(), 2)      # granted on continue
        self.assertEqual(self.game.parts_run_gain, 0)
        self.assertNotIn("point", main.scorer_description(main.Scorer.PARTS).lower())


    def test_parts_scorer_banks_one_component_per_single_trigger(self):
        # A lone Parts trigger banks exactly one whole component, and a retried
        # run drops the bank: only continuing hands it over.
        self.game.toolbox.items.clear()
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.PARTS)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.parts_run_gain, 1)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.parts_run_gain, 0)
        self.assertEqual(self._component_count(), 0)


    def test_parts_bank_is_dropped_when_the_run_is_restarted(self):
        # Only a CONTINUE hands the bank over: restarting the run (R) or
        # starting a fresh one discards it with every other per-run gain.
        # (reset_run refuses to build a run with no Start block on the board.)
        self.game.toolbox.items.clear()
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.PARTS)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.parts_run_gain, 1)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.parts_run_gain, 0)
        self.assertEqual(self._component_count(), 0)


    def test_parts_reward_is_withheld_when_the_inventory_is_full(self):
        # A full inventory withholds the banked components (the same rule the
        # instant grant followed) rather than overfilling the toolbox.
        self.game.toolbox.items.clear()
        filler = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.NONE, 0, 5, "filler")
        capacity = self.game.toolbox.cols * self.game.toolbox.rows
        while len(self.game.toolbox.items) < capacity:
            self.game.toolbox.add(filler)
        self.game.parts_run_gain = 2
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self._component_count(), 0)
        self.assertEqual(len(self.game.toolbox.items), capacity)
        self.assertEqual(self.game.parts_run_gain, 0)
        self.assertIn("withheld", self.game.shop_message)


    def test_parts_description_states_when_the_reward_arrives(self):
        # The rule is in the text the player reads: a Parts piece says its
        # component is handed over once the run is continued, both on a block
        # and as a card's payoff.
        self.assertIn("handed over once the run is continued",
                      main.scorer_description(main.Scorer.PARTS, 1))
        card = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                          main.Scorer.PARTS)
        self.assertIn("handed over once the run is continued",
                      main.Card.description(card))


    def test_picky_points_convert_to_bonus_slot_on_continue(self):
        # Two Picky points earned during a run convert into one bonus shop
        # slot after a run.
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.PICKY)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.option_run_gain, 1.0)
        self.assertEqual(self.game.bonus_slots, 0)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.option_run_gain, 0)
        self.assertEqual(self.game.option_points, 0)
        self.assertEqual(self.game.bonus_slots, 1)
        self.assertEqual(self.game.shop.bonus_slots, 1)


    def test_picky_leftover_points_bank_on_continue(self):
        # Points below a whole point stay banked for a future run: three Picky
        # triggers bank 1.5 points, one converts and the 0.5 stays.
        self.game.run_active = True
        for _ in range(3):
            block = main.Block(0, 0, scorer=main.Scorer.PICKY)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.option_run_gain, 1.5)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.option_run_gain, 0)
        self.assertEqual(self.game.option_points, 0.5)  # 1.5 - one point
        self.assertEqual(self.game.bonus_slots, 1)


    def test_shreds_scorer_points_convert_only_on_continue(self):
        # Three shred triggers bank 1/3 of a point each: one whole point, which
        # converts into a random card after a run.
        self.game.cards.clear()
        self.game.run_active = True
        for _ in range(3):
            block = main.Block(0, 0, scorer=main.Scorer.SHREDS)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.shred_run_gain, 1.0)
        self.assertEqual(self.game.cards, [])
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.shred_run_gain, 0)
        self.assertEqual(self.game.shred_points, 0)
        self.assertEqual(len(self.game.cards), 1)


    def test_rubble_scorer_points_convert_only_on_continue(self):
        # Two rubble triggers bank 1/2 a point each: one whole point, which
        # converts into a random block after a run.
        self.game.toolbox.items.clear()
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.RUBBLE)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.rubble_run_gain, 1.0)
        self.assertEqual(self.game.rubble_points, 0)
        blocks = [i for i in self.game.toolbox.items if getattr(i, "kind", None) == "block"]
        self.assertEqual(blocks, [])
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.rubble_run_gain, 0)
        self.assertEqual(self.game.rubble_points, 0)
        blocks = [i for i in self.game.toolbox.items if getattr(i, "kind", None) == "block"]
        self.assertEqual(len(blocks), 1)


    def test_ideas_scorer_points_convert_only_on_continue(self):
        # Two idea points earned during a run convert into one random action
        # after a run.
        self.game.actions.clear()
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.IDEAS)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.idea_run_gain, 1.0)
        self.assertEqual(self.game.actions, [])
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        self.assertEqual(self.game.idea_run_gain, 0)
        self.assertEqual(self.game.idea_points, 0)
        self.assertEqual(len(self.game.actions), 1)


    def test_random_scorer_chips_branch_adds_thirty_five(self):
        self.game.score_chips = 100
        self.game.score_mult = 2
        self._trigger_random_block(0.0)  # first third -> +35 chips
        self.assertEqual(self.game.score_chips, 135)
        self.assertEqual(self.game.score_mult, 2)
        self.assertEqual(self._trigger_random_block(0.0).triggers_left, 0)


    def test_random_scorer_mult_branch_adds_five(self):
        self.game.score_chips = 100
        self.game.score_mult = 2
        self._trigger_random_block(0.5)  # middle third -> +5 mult
        self.assertEqual(self.game.score_chips, 100)
        self.assertEqual(self.game.score_mult, 7)


    def test_random_scorer_xmult_branch_multiplies_by_one_point_three(self):
        self.game.score_chips = 100
        self.game.score_mult = 2
        self._trigger_random_block(0.9)  # last third -> +0.3 xMult (x1.3)
        self.assertEqual(self.game.score_chips, 100)
        self.assertAlmostEqual(self.game.score_mult, 2 * 1.3)


    def test_random_scorer_uses_all_three_rewards_over_many_triggers(self):
        # Across many random triggers every reward appears (chips/mult/xMult
        # particles are green/blue/red respectively).
        colors = set()
        for _ in range(90):
            block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game.run_active = True
            self.game._handle_block_contacts([block])
            colors.add(self.game.score_particles[-1].color)
        self.assertEqual(colors, {main.GREEN, main.BLUE, main.RED})


    def test_seed_scorer_gives_mult_for_each_seed_on_board(self):
        # Seed grants +3 mult (scorer_amount) for EVERY Seed block placed on
        # the board, including the touched block itself.
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.SEED)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.SEED)
        self.game.grid[(0, 2)] = main.Block(0, 2, scorer=main.Scorer.MULT_ADD)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([touched])
        # 2 Seed blocks x +3 mult = +6 mult.
        self.assertEqual(self.game.score_mult, 8)
        self.assertEqual(touched.triggers_left, 0)


    def test_seed_with_no_other_seed_counts_itself(self):
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.SEED)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([touched])
        self.assertEqual(self.game.score_mult, 5)  # 1 seed x +3


    def test_drill_scorer_marks_two_locked_squares_for_continue(self):
        # Touching a Drill block during a run banks two pending locked-square
        # unlocks (granted after a run, discarded on retry).
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.DRILL)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.drill_run_units = 0
        self.game._handle_block_contacts([touched])
        self.assertEqual(self.game.drill_run_units, 2)
        self.assertEqual(touched.triggers_left, 0)


    def test_lucky_can_land_both_rolls_together(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.0, 0.0])  # chips roll hits AND cash roll hits
        self.assertEqual(self.game.score_chips, 230)
        self.assertEqual(self.game.cash, 90)


    def test_lucky_can_land_neither_roll(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.9, 0.9])  # neither roll hits
        self.assertEqual(self.game.score_chips, 100)
        self.assertEqual(self.game.cash, 50)


    def test_lucky_can_land_chips_only(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.1, 0.9])  # chips roll hits, cash roll misses
        self.assertEqual(self.game.score_chips, 230)
        self.assertEqual(self.game.cash, 50)


    def test_lucky_can_land_cash_only(self):
        self.game.score_chips = 100
        self.game.cash = 50
        self._trigger_lucky([0.9, 0.0])  # chips roll misses, cash roll hits
        self.assertEqual(self.game.score_chips, 100)
        self.assertEqual(self.game.cash, 90)


    def test_lucky_keeps_its_pre_rolled_outcome_for_the_whole_run(self):
        # The two Lucky rolls are chosen BEFORE the run (1/3 chips hit, 1/9
        # cash miss here), so the block pays 130 chips on every trigger and
        # never the $40 — even though these draws would have missed both.
        block = main.Block(0, 0, scorer=main.Scorer.LUCKY, trigger_limit=2)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 0
        self.game.cash = 0
        with mock.patch("main.random.random", side_effect=[0.0, 0.9]):
            self.game._roll_run_random_outputs()
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 130)
        self.assertEqual(self.game.cash, 0)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 260)
        self.assertEqual(self.game.cash, 0)
        self.assertEqual(block.triggers_left, 0)


    def test_lucky_cash_roll_repeats_and_counts_in_run_cash(self):
        # The cash roll is pre-rolled too: two triggers of one Lucky block pay
        # $40 twice, and both dollars land in the run's cash gain.
        block = main.Block(0, 0, scorer=main.Scorer.LUCKY, trigger_limit=2)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 0
        self.game.cash = 0
        with mock.patch("main.random.random", side_effect=[0.9, 0.0]):
            self.game._roll_run_random_outputs()
        self._touch_block(block, 0.9)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 0)
        self.assertEqual(self.game.cash, 80)
        self.assertEqual(self.game.run_cash_gained, 80)


    def test_roomy_scales_with_more_unlocked_units(self):
        # A bigger unlocked region pays out proportionally more.
        self.game.unlocked_cells = {(x, y) for x in range(3) for y in range(3)}  # 9 units
        self.game.score_chips = 0
        block = main.Block(0, 0, scorer=main.Scorer.ROOMY)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 2 * 9)


    def test_rally_pays_mult_for_fresh_touches_before_it(self):
        # A Rally block grants +1 mult per fresh block contact this run that
        # happened before it; its own touch never counts.
        self.game.run_active = True
        self.game.score_mult = 2
        first = main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=1)
        rally = main.Block(0, 1, scorer=main.Scorer.RALLY)
        self.game.grid[(0, 0)] = first
        self.game.grid[(0, 1)] = rally
        marble = self._add_marble()
        # Fresh touch #1: the plain mult block scores +1 mult.
        marble.collisions_this_tick = [first]
        self.game._handle_block_contacts([first])
        # Fresh touch #2: Rally pays for the 1 earlier touch.
        marble.collisions_this_tick = [rally]
        self.game._handle_block_contacts([rally])
        self.assertEqual(self.game.score_mult, 2 + 1 + 1)  # first +1, rally +1
        self.assertEqual(self.game.run_fresh_touches, 2)


    def test_rally_counts_re_touches_but_not_its_own(self):
        # Re-touching a block adds another fresh contact, so a later Rally
        # block pays more; its own touch is still excluded.
        self.game.run_active = True
        self.game.score_mult = 1
        first = main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=1)
        rally = main.Block(0, 1, scorer=main.Scorer.RALLY)
        self.game.grid[(0, 0)] = first
        self.game.grid[(0, 1)] = rally
        marble = self._add_marble()
        marble.collisions_this_tick = [first]
        self.game._handle_block_contacts([first])   # touch 1 (+1 mult)
        marble.collisions_this_tick = [first]
        self.game._handle_block_contacts([first])   # touch 2 (re-touch, no score)
        marble.collisions_this_tick = [rally]
        self.game._handle_block_contacts([rally])   # touch 3, pays 2
        self.assertEqual(self.game.score_mult, 1 + 1 + 2)


    def test_rally_touches_reset_each_run(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.run_active = True
        block = main.Block(0, 1, scorer=main.Scorer.MULT_ADD, scorer_amount=1)
        self.game.grid[(0, 1)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.run_fresh_touches, 1)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.run_fresh_touches, 0)


    def test_echo_refires_the_previous_blocks_scorer(self):
        # Echo replays the scoring effect of the block the marble touched
        # right before it (that previous block also scored normally itself).
        self.game.run_active = True
        self.game.score_chips = 0
        prev = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        echo = main.Block(0, 1, scorer=main.Scorer.ECHO)
        self.game.grid[(0, 0)] = prev
        self.game.grid[(0, 1)] = echo
        marble = self._add_marble()
        marble.collisions_this_tick = [prev]
        self.game._handle_block_contacts([prev])
        marble.collisions_this_tick = [echo]
        self.game._handle_block_contacts([echo])
        self.assertEqual(self.game.score_chips, 10 + 10)
        self.assertEqual(echo.triggers_left, 0)


    def test_echo_ignores_plain_and_role_blocks(self):
        # Echo only copies real scoring blocks: plain (NONE), START/FINISH,
        # and other Echo blocks are skipped, but its own trigger is spent.
        self.game.run_active = True
        self.game.score_mult = 3
        plain = main.Block(0, 0, scorer=main.Scorer.NONE)
        echo = main.Block(0, 1, scorer=main.Scorer.ECHO)
        self.game.grid[(0, 0)] = plain
        self.game.grid[(0, 1)] = echo
        marble = self._add_marble()
        marble.collisions_this_tick = [plain]
        self.game._handle_block_contacts([plain])
        marble.collisions_this_tick = [echo]
        self.game._handle_block_contacts([echo])
        self.assertEqual(self.game.score_mult, 3)
        self.assertEqual(echo.triggers_left, 0)


    def test_powerline_pays_per_block_in_its_row(self):
        # +25 chips for every block in the same row (including itself); other
        # rows don't count.
        self.game.run_active = True
        self.game.score_chips = 0
        touched = main.Block(1, 0, scorer=main.Scorer.POWERLINE)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.MULT_ADD)
        self.game.grid[(1, 0)] = touched
        self.game.grid[(2, 0)] = main.Block(2, 0, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.CHIPS_ADD)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game._handle_block_contacts([touched])
        self.assertEqual(self.game.score_chips, 25 * 3)  # 3 blocks in row 0


    def test_frontier_corner_pays_two_borders_on_a_full_board(self):
        # Fully unlocked board: nothing is locked any more, so a corner block
        # pays only for its two outer borders.
        block = main.Block(0, 0, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(x, y) for x in range(main.GRID_WIDTH)
                                     for y in range(main.GRID_HEIGHT)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 2)
        self.assertEqual(block.triggers_left, 0)


    def test_frontier_edge_pays_one_border_on_a_full_board(self):
        # Fully unlocked board: a non-corner edge block pays for one border.
        block = main.Block(0, 1, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(x, y) for x in range(main.GRID_WIDTH)
                                     for y in range(main.GRID_HEIGHT)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 1)


    def test_frontier_interior_pays_nothing_on_a_full_board(self):
        # Fully unlocked board: an interior block faces no locked unit and no
        # border, so it pays nothing (trigger still spent).
        block = main.Block(1, 1, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(x, y) for x in range(main.GRID_WIDTH)
                                     for y in range(main.GRID_HEIGHT)})
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_frontier_pays_for_locked_neighbours(self):
        # Unlocked region is the L {(0,0), (1,0), (0,1)}. At (1,0) the
        # neighbours are (0,0) unlocked (pays nothing), (1,-1) the outer
        # border, and the two locked squares (2,0)/(1,1) — three units.
        block = main.Block(1, 0, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(0, 0), (1, 0), (0, 1)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 3)


    def test_frontier_surrounded_by_locked_units_pays_four(self):
        # A lone unlocked square in the middle of the board faces locked units
        # on all four sides, so all four directions pay.
        block = main.Block(3, 3, scorer=main.Scorer.FRONTIER)
        self._touch_frontier(block, {(3, 3)})
        self.assertEqual(self.game.score_mult, 1 + 3 * 4)


    def test_cluster_pays_four_mult_per_adjacent_block(self):
        # +4 mult for each of the four orthogonal neighbours.
        block = main.Block(2, 2, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ((1, 2), (3, 2), (2, 1), (2, 3)))
        self.assertEqual(self.game.score_mult, 1 + 4 * 4)
        self.assertEqual(block.triggers_left, 0)


    def test_cluster_ignores_diagonal_neighbours(self):
        # A diagonal block is not adjacent: four diagonals pay nothing.
        block = main.Block(2, 2, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ((1, 1), (3, 1), (1, 3), (3, 3)))
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_cluster_counts_only_orthogonal_neighbours(self):
        # Three orthogonal neighbours + all four diagonals -> only the three.
        block = main.Block(2, 2, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ((1, 2), (2, 1), (2, 3),
                                    (1, 1), (3, 1), (1, 3), (3, 3)))
        self.assertEqual(self.game.score_mult, 1 + 4 * 3)


    def test_cluster_alone_gives_nothing(self):
        # A lone Cluster block (and its own cell, which never counts) is worth
        # nothing, but the trigger is still spent.
        block = main.Block(5, 5, scorer=main.Scorer.CLUSTER)
        self._touch_cluster(block, ())
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_colossus_description_names_its_payoff(self):
        desc = main.scorer_description(main.Scorer.COLOSSUS, 0.1)
        self.assertIn("0.1", desc)
        self.assertIn("radius", desc)


    def test_colossus_pays_xmult_per_pixel_above_the_base_radius(self):
        # A marble grown to 16 px (8 px above the base 8) pays +0.8 xMult.
        block = main.Block(0, 0, scorer=main.Scorer.COLOSSUS)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 2
        marble = self._add_marble()
        marble.radius = main.MARBLE_RADIUS + 8
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertAlmostEqual(self.game.score_mult, 2 * (1 + 0.1 * 8))
        self.assertEqual(block.triggers_left, 0)


    def test_colossus_keeps_scaling_with_a_huge_marble(self):
        block = main.Block(0, 0, scorer=main.Scorer.COLOSSUS)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.radius = main.MARBLE_RADIUS * 4  # doubled twice by Growing blocks
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertAlmostEqual(self.game.score_mult, 1 + 0.1 * 24)


    def test_colossus_gives_nothing_at_the_base_radius(self):
        # A marble at (or below) its base size gains nothing, but the trigger
        # is still spent.
        block = main.Block(0, 0, scorer=main.Scorer.COLOSSUS)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 3
        marble = self._add_marble()  # radius == MARBLE_RADIUS
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 3)
        self.assertEqual(block.triggers_left, 0)


    def test_undertaker_pays_mult_per_block_destroyed_this_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.UNDERTAKER)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 1
        self.game.run_blocks_destroyed = 2
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 1 + 15 * 2)
        self.assertEqual(block.triggers_left, 0)


    def test_undertaker_gives_nothing_with_no_destroyed_blocks(self):
        block = main.Block(0, 0, scorer=main.Scorer.UNDERTAKER)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_a_satanic_death_counts_as_a_block_destroyed(self):
        block = main.Block(1, 1, scorer=main.Scorer.SATANIC, origin=(0, 0))
        block.rect.topleft = (0, 0)
        marble = main.Marble(200, 200)  # far away this frame
        marble.collisions_this_tick = [block]  # ...but it touched last frame
        marble.physics.update(marble, main.DT, [block])
        self.assertTrue(getattr(block, "satanic_leave", False))
        self.game.grid[(1, 1)] = block
        self.game.run_active = True
        self.game.marbles = []

        self.game.update()

        self.assertNotIn((1, 1), self.game.grid)
        self.assertEqual(self.game.run_blocks_destroyed, 1)


    def test_retrying_a_run_clears_the_debt_and_undertaker_state(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.debt_run_triggered = True
        self.game.run_blocks_destroyed = 4
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertFalse(self.game.debt_run_triggered)
        self.assertEqual(self.game.run_blocks_destroyed, 0)
        self.assertEqual(self.game.last_run_cash_breakdown, {})


    def test_a_resource_scorers_deviation_follows_its_point_count(self):
        # The modifier after a resource-point count belongs to THAT count, so it
        # always adds up with the number it sits next to: a Rubble block rolled
        # to 1.4 banks 0.7 points, which is (+0.2) over the 0.5 average — not
        # the (+0.4) its own magnitude is over 1.
        desc = main.scorer_description(main.Scorer.RUBBLE, 1.4)
        self.assertIn("Gives 0.7 rubble point (+0.2).", desc)
        self.assertNotIn("+0.4", desc)
        # A Shreds trigger's third of a point steps by a thirtieth.
        self.assertIn("Gives 0.367 shred point (+0.033).",
                      main.scorer_description(main.Scorer.SHREDS, 1.1))
        self.assertIn("Gives 0.3 shred point (-0.033).",
                      main.scorer_description(main.Scorer.SHREDS, 0.9))
        # An average-magnitude item reads its own count as (0)...
        self.assertIn("Gives 0.5 rubble point (0).",
                      main.scorer_description(main.Scorer.RUBBLE, 1))
        # ...and a composed card with a rolled resource magnitude does too.
        card_text = components._card_payoff_text(main.Condition.START,
                                                 main.Scorer.RUBBLE, 1.4)
        self.assertIn("Gives 0.7 rubble point (+0.2)", card_text)
        # A catalogue card (no rolled magnitude) states no token at all.
        token = re.compile(r"\([+-]?\d+(\.\d+)?\)")
        catalogue = main.Card.description(
            main.condition_scorer_card(main.Condition.START, main.Scorer.RUBBLE))
        self.assertIsNone(token.search(catalogue), catalogue)


    def test_a_role_scorer_component_counts_as_a_way_to_field_the_role(self):
        self.game.toolbox.items.clear()
        component = main.Component.scorer_component(main.Scorer.START)
        self.game.toolbox.add(component)
        # A role component can be assembled back into a role block, so it is
        # the last way to field the role and cannot be sold.
        self.assertTrue(self.game._unsellable(component))

        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                             main.Scorer.START, 0, 109, "Start Block",
                                             effects=[]))
        self.assertFalse(self.game._unsellable(component))


    def test_start_scorer_component_cannot_be_sold(self):
        self.game.toolbox.items.clear()
        component = main.Component.scorer_component(main.Scorer.START)
        self.game.toolbox.add(component)
        self.game.cash = 0

        self.game._equip_block(component)
        self.game._sell_selected_item()

        self.assertIn(component, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 0)


    def test_gilded_adds_one_sixth_of_chips_as_mult(self):
        # 60 chips -> +10 mult (1/6 of the current chips).
        self.game.run_active = True
        self.game.score_chips = 60
        self.game.score_mult = 1
        block = main.Block(0, 0, scorer=main.Scorer.GILDED)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 10)
        self.assertEqual(block.triggers_left, 0)


    def test_bomb_touch_primes_a_detonation(self):
        # Touching a Bomb during a run banks its cell; it doesn't explode yet.
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.BOMB)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.bomb_cells, {(0, 0)})
        self.assertEqual(block.triggers_left, 0)
        self.assertIn((0, 0), self.game.grid)  # still present mid-run


    def test_effective_scorer_gives_xmult_with_two_effects(self):
        block = main.Block(0, 0, effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY],
                           scorer=main.Scorer.EFFECTIVE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 2 * 2.0)  # +1 xMult
        self.assertEqual(block.triggers_left, 0)


    def test_effective_scorer_gives_nothing_with_one_effect(self):
        block = main.Block(0, 0, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.EFFECTIVE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 2)  # no reward
        self.assertEqual(block.triggers_left, 0)    # but the trigger is spent


    def test_block_composes_shape_effect_and_scorer(self):
        block = main.Block(1, 2, shape=main.Shape.LINE, effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=25)

        self.assertEqual(block.shape, main.Shape.LINE)
        self.assertEqual(block.effect, main.Effect.BOUNCY)
        self.assertEqual(block.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(block.scorer_amount, 25)


    def test_scorer_has_default_amount(self):
        chips = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        mult_add = main.Block(0, 0, scorer=main.Scorer.MULT_ADD)
        mult_mul = main.Block(0, 0, scorer=main.Scorer.MULT_MUL)

        self.assertEqual(chips.scorer_amount, 30)
        self.assertEqual(mult_add.scorer_amount, 4)
        self.assertEqual(mult_mul.scorer_amount, 1.5)


    def test_descriptions_exist_for_all_shapes_effects_scorers(self):
        for shape in main.Shape.ORDER:
            self.assertTrue(main.shape_description(shape))
        for effect in main.Effect.ORDER:
            self.assertTrue(main.effect_description(effect))
        for scorer in main.Scorer.ORDER:
            self.assertTrue(main.scorer_description(scorer, main.Scorer.DEFAULT_AMOUNT.get(scorer, 0)))


    def test_every_scorer_has_its_own_trigger_sound(self):
        import sounds
        self._assert_waves_are_distinct(list(main.Scorer.ORDER),
                                       sounds._scorer_wave, "scorer")


    def test_block_contact_plays_the_effect_and_scorer_sounds(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD,
                           effects=[main.Effect.BOUNCY, main.Effect.STICKY])
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        with mock.patch("main.sounds.play_effect") as effect_sound, \
             mock.patch("main.sounds.play_scorer") as scorer_sound:
            self.game._handle_block_contacts([block])
        # Every effect on the block rings, then the scorer that fired.
        self.assertEqual([call.args[0] for call in effect_sound.call_args_list],
                         [main.Effect.BOUNCY, main.Effect.STICKY])
        scorer_sound.assert_called_once_with(main.Scorer.CHIPS_ADD)
        # Staying in contact is not a new collision: no sound at all.
        marble.collisions_last_tick = [block]
        with mock.patch("main.sounds.play_effect") as effect_sound, \
             mock.patch("main.sounds.play_scorer") as scorer_sound:
            self.game._handle_block_contacts([block])
        effect_sound.assert_not_called()
        scorer_sound.assert_not_called()


    def test_start_and_finish_blocks_do_not_ring_a_scorer_sound(self):
        self.game.run_active = True
        for scorer in (main.Scorer.START, main.Scorer.FINISH):
            block = main.Block(0, 0, scorer=scorer)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            with mock.patch("main.sounds.play_scorer") as scorer_sound:
                self.game._handle_block_contacts([block])
            scorer_sound.assert_not_called()


    def test_voyager_magnitude_is_rolled_around_the_average_rate(self):
        # The rate rolls like every other scalar: 0.01 steps by 0.001, capped
        # at 8 steps either side and never reaching zero.
        self.assertAlmostEqual(main.magnitude_step(main.Scorer.DEFAULT_AMOUNT[
            main.Scorer.VOYAGER]), 0.001)
        self.assertAlmostEqual(main.scorer_magnitude_floor(main.Scorer.VOYAGER), 0.001)
        rolls = [main.roll_scorer_amount(main.Scorer.VOYAGER) for _ in range(200)]
        # The roll is continuous, so a sample of these tiny rates spreads over
        # far more than the 17 whole-step values the rolled grid used to hold.
        self.assertGreater(len(set(rolls)), 5, "rolls should vary")
        self.assertGreater(len(set(rolls)), 17)
        for amount in rolls:
            self.assertGreaterEqual(amount, 0.002)
            self.assertLessEqual(amount, 0.018)
            # A rate is written with five decimals (2% of its own average is
            # finer than that), so a roll carries no arithmetic dust.
            self.assertEqual(amount, round(amount, 5))
        # A piece costs the catalog price whatever rate it rolled (the table
        # price is the average-rate price): the roll is upside, not cost.
        base = main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.VOYAGER)]
        strong = main.Component.scorer_component(main.Scorer.VOYAGER, amount=0.018)
        weak = main.Component.scorer_component(main.Scorer.VOYAGER, amount=0.002)
        self.assertEqual(strong.price, base)
        self.assertEqual(weak.price, base)
        self.assertEqual((strong.amount, weak.amount), (0.018, 0.002))
        # The description names the rolled rate with its deviation token.
        desc = main.scorer_description(main.Scorer.VOYAGER, 0.018)
        self.assertIn("0.018 mult", desc)
        self.assertIn("(+0.008)", desc)


    def test_voyager_block_adds_mult_per_pixel_traveled(self):
        # A Voyager block adds its own rate (0.01 mult at the average) for each
        # pixel the touching marble had already traveled this run.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 2400.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.01 * 2400)
        self.assertEqual(block.triggers_left, 0)


    def test_voyager_block_pays_a_fraction_of_a_pixel_of_travel(self):
        # The rate is per pixel, not per whole unit of distance: 55 px of
        # travel at the rolled 0.01 rate is +0.55 mult, kept as a float.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 55.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1.55)
        self.assertNotEqual(self.game.score_mult, int(self.game.score_mult))


    def test_voyager_block_counts_only_the_touching_marble(self):
        # The reward uses the marble that touched the block, not every marble.
        self.game.score_mult = 1
        self.game.run_active = True
        other = self._add_marble()
        other.distance = 8000.0  # traveled far but never touches the block
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 800.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.01 * 800)


    def test_voyager_block_gives_nothing_without_travel(self):
        # A marble that has not moved yet adds no mult, but the trigger is
        # still spent (the block shows its used state).
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.VOYAGER, scorer_amount=0.01)
        marble = self._add_marble()
        marble.distance = 0.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_summit_block_adds_three_quarter_mult_per_row_above_bottom(self):
        # A Summit block at row 0 (the top row) sits GRID_HEIGHT - 1 rows
        # above the bottom row, so it adds 0.75 * (GRID_HEIGHT - 1) mult.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.SUMMIT)  # row 0 = top row
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.75 * (main.GRID_HEIGHT - 1))
        self.assertEqual(block.triggers_left, 0)


    def test_summit_block_mid_board_scales_with_row(self):
        # A block partway up adds 0.75 mult for each row above the bottom row.
        self.game.score_mult = 1
        self.game.run_active = True
        row = main.GRID_HEIGHT - 1 - 10  # ten rows above the bottom row
        block = main.Block(0, row, scorer=main.Scorer.SUMMIT, scorer_amount=0.5)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.5 * 10)


    def test_summit_block_on_bottom_row_gives_nothing(self):
        # A Summit block on the bottom row (row GRID_HEIGHT - 1) is 0 units
        # above it, so it grants no mult; the trigger is still spent.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, main.GRID_HEIGHT - 1, scorer=main.Scorer.SUMMIT)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_summit_block_fractional_mult_is_kept_as_float(self):
        # The 0.75-per-row mult stays fractional internally (nothing rounds the
        # reward); only the UI display rounds to a tenth.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, main.GRID_HEIGHT - 1 - 7, scorer=main.Scorer.SUMMIT)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.75 * 7)
        self.assertNotEqual(self.game.score_mult, int(self.game.score_mult))


    def test_airball_block_adds_eight_mult_per_air_second(self):
        # An Airball block rewards the touching marble's airborne streak: 2.5s
        # of air right before the touch -> +8 * 2.5 = +20 mult.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL, scorer_amount=8)
        marble = self._add_marble()
        marble.air_streak = 2.5
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 2.5)
        self.assertEqual(block.triggers_left, 0)


    def test_airball_block_counts_only_the_touching_marble(self):
        # The reward uses the marble that touched the block, not every marble.
        self.game.score_mult = 1
        self.game.run_active = True
        other = self._add_marble()
        other.air_streak = 50.0  # lots of air, but never touches this block
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL)
        marble = self._add_marble()
        marble.air_streak = 0.5
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 0.5)


    def test_airball_block_gives_nothing_when_marble_had_no_air(self):
        # A marble that just touched another block has a 0 air streak, so the
        # Airball block grants nothing but still spends its trigger.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL)
        marble = self._add_marble()
        marble.air_streak = 0.0
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    def test_airball_block_fractional_mult_is_kept_as_float(self):
        # Fractional air seconds count: 0.6s -> 8 * 0.6 = 4.8 mult, kept as a
        # float (only the UI rounds it to a tenth).
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.AIRBALL)
        marble = self._add_marble()
        marble.air_streak = 0.6
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 0.6)
        self.assertNotEqual(self.game.score_mult, int(self.game.score_mult))


    def test_airball_air_streak_accumulates_while_marble_airborne(self):
        # A marble with nothing under it stays airborne, so its air streak
        # grows every frame it has no block contact.
        self.game.marbles = [main.Marble(360, 120)]
        self.game.run_active = True
        for _ in range(30):
            self.game.update()
        self.assertGreater(self.game.marbles[0].air_streak, 0.2)


    def test_airball_air_streak_resets_while_marble_rests_on_block(self):
        # A marble resting on a floor block is in contact, so its air streak is
        # zeroed (an Airball touch right after it would reward 0 air).
        floor = main.Block(5, 8)
        self.game.grid[(5, 8)] = floor
        marble = main.Marble(floor.rect.centerx, floor.rect.top - main.MARBLE_RADIUS - 1)
        self.game.marbles = [marble]
        self.game.run_active = True
        for _ in range(20):
            self.game.update()
        self.assertLess(marble.air_streak, 0.2)


    def test_satanic_block_multiplies_mult_by_6_66_when_touched(self):
        block = main.Block(0, 0, scorer=main.Scorer.SATANIC)
        self.game.score_mult = 2
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 2 * 6.66)
        self.assertEqual(block.triggers_left, 0)


    def test_satanic_block_is_removed_after_marble_touches_and_leaves(self):
        # A marble that touched the block last frame and is no longer touching
        # flags it; the game then removes the block from the board for good.
        block = main.Block(0, 0, scorer=main.Scorer.SATANIC, origin=(0, 0))
        block.rect.topleft = (0, 0)
        marble = main.Marble(200, 200)  # far from the block this frame
        marble.collisions_this_tick = [block]  # ...but it touched last frame
        marble.physics.update(marble, main.DT, [block])
        self.assertTrue(getattr(block, "satanic_leave", False))
        # The game removes the flagged block from the grid on its next update.
        self.game.grid[(1, 1)] = block
        self.game.run_active = True
        self.game.marbles = []
        self.game.update()
        self.assertNotIn((1, 1), self.game.grid)


    def test_sharp_then_mult_then_sharp_sequence(self):
        # A Sharp block, then a +Mult block, then a (different) Sharp block:
        # triple, add 4 to the multiplier, then triple (1 -> 3 -> 7 -> 21).
        self.game.score_mult = 1
        self.game.run_active = True

        def fire(block):
            self.game.marbles = []
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])

        fire(main.Block(0, 0, scorer=main.Scorer.SHARP))
        self.assertAlmostEqual(self.game.score_mult, 3)
        fire(main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=4))
        self.assertAlmostEqual(self.game.score_mult, 7)
        fire(main.Block(0, 0, scorer=main.Scorer.SHARP))
        self.assertAlmostEqual(self.game.score_mult, 21)


    def test_a_naturally_v2_action_is_already_maxed(self):
        with mock.patch("main.random_action_version", return_value=2):
            self.game.shop.refresh()
        action = next(i for i in self.game.shop.items if i.kind == "action")
        self.game.actions.append(action)
        self.game.selected_action = action
        self.game.cash = 1000

        self.game._upgrade_action()

        self.assertEqual(action.version, 2)
        self.assertEqual(self.game.cash, 1000)  # nothing to pay: already v2


    def test_scorer_descriptions_state_the_deviation_inline(self):
        # The deviation sits right after the magnitude it belongs to, as a bare
        # signed token — "Adds +6 mult (+2) when touched" — which the sidebar
        # colours green/red/grey. No trailing "above the average" sentence.
        above = main.scorer_description(main.Scorer.CHIPS_ADD, 33)
        self.assertEqual(above, "Adds 33 chips (+3) when touched")
        below = main.scorer_description(main.Scorer.MULT_ADD, 3)
        self.assertEqual(below, "Adds +3 mult (-1) when touched")
        even = main.scorer_description(main.Scorer.CHIPS_ADD, 30)
        self.assertEqual(even, "Adds 30 chips (0) when touched")
        for text in (above, below, even):
            self.assertNotIn("average", text)
        # A scorer with no magnitude never mentions a deviation.
        deviation = re.compile(r"\([+-]?\d+(\.\d+)?\)")
        for scorer in (main.Scorer.LUCKY, main.Scorer.START, main.Scorer.QUICK):
            self.assertIsNone(deviation.search(main.scorer_description(scorer)),
                              f"{main.Scorer.name(scorer)} has no magnitude")
        # A rolled xMult reads its own factor.
        self.assertIn("by 4 (+1)", main.scorer_description(main.Scorer.SHARP, 4))
        self.assertIn("(+1)", main.scorer_description(main.Scorer.EFFECTIVE, 3))
        # The amount-dependent scorers all follow their own magnitude.
        self.assertIn("Gives 2 components (+1)", main.scorer_description(main.Scorer.PARTS, 2))
        self.assertIn("Gives 1 component (0)", main.scorer_description(main.Scorer.PARTS, 1))
        self.assertIn("drills out 3 locked board squares (+1)",
                      main.scorer_description(main.Scorer.DRILL, 3))


    def test_a_bought_block_keeps_its_own_effects_and_scorer(self):
        # A shop block's components carry their own rolled magnitudes, and the
        # block keeps them when it is bought, placed, erased and returned.
        block = next(i for i in self.game.shop.items if i.kind == "block")
        amount = block.scorer_amount
        amounts = dict(block.effect_amounts)
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        self.game._buy_shop_item(block)
        self.game._equip_block(block)
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=self._grid_pos(3, 3)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        placed = self.game.grid[(3, 3)]
        self.assertEqual(placed.scorer_amount, amount)
        for e, magnitude in amounts.items():
            self.assertEqual(placed.effect_magnitude(e), magnitude)
        # Erasing it hands the same block (and the same magnitudes) back, at
        # the price it came in with.
        self.game._erase_block_at(3, 3)
        returned = next(i for i in self.game.toolbox.items
                        if getattr(i, "kind", None) == "block")
        self.assertEqual(returned.scorer_amount, amount)
        self.assertEqual(returned.effect_amounts, amounts)
        self.assertEqual(returned.price, block.price)


    def test_parts_and_rubble_grants_roll_magnitudes(self):
        # The reward paths roll magnitudes exactly like the shop does, so a
        # granted piece is never a flat average and always inside the range.
        random.seed(4242)
        amounts = set()
        self.game.toolbox.items.clear()
        for _ in range(80):
            self.game._grant_random_component()
        for item in self.game.toolbox.items:
            if getattr(item, "kind", None) != main.Component.SCORER:
                continue
            step = main.magnitude_step(main.Scorer.DEFAULT_AMOUNT[item.value])
            if not step:
                continue
            amounts.add(item.amount)
            self.assertGreaterEqual(item.amount,
                                    main.scorer_magnitude_floor(item.value))
            self.assertLessEqual(item.amount,
                                 main.Scorer.DEFAULT_AMOUNT[item.value]
                                 + step * main.MAGNITUDE_MAX_STEPS)
            self.assertEqual(item.price,
                             main.scorer_component_price(item.value))
        self.assertGreater(len(amounts), 1)  # 80 grants never all roll alike

        # A Rubble block carries a magnitude for each scaleable effect.
        self.game.toolbox.items.clear()
        self.game._grant_random_block()
        granted = self.game.toolbox.items[-1]
        for e in granted.effects:
            if e in main.Effect.MAGNITUDE:
                magnitude = granted.effect_amounts[e]
                self.assertGreaterEqual(magnitude, main.effect_magnitude_floor(e))
                self.assertLessEqual(magnitude,
                                     main.Effect.MAGNITUDE[e]
                                     + main.magnitude_step(main.Effect.MAGNITUDE[e])
                                     * main.MAGNITUDE_MAX_STEPS)


    # --- Spirit: tokens that keep a scorer firing -------------------------

    def test_spirit_destroys_the_block_and_keeps_its_scorer_as_a_token(self):
        block = main.Block(3, 4, shape=main.Shape.RECT, scorer=main.Scorer.MULT_ADD,
                           scorer_amount=4, effects=[main.Effect.BOUNCY])
        self.game.grid[(3, 4)] = block
        action = main.ActionItem(main.Action.SPIRIT, 36)
        cash_before = self.game.cash

        self.assertTrue(self.game._action_spirit(action, block))

        self.assertNotIn((3, 4), self.game.grid)
        self.assertEqual(len(self.game.tokens), 1)
        token = self.game.tokens[0]
        self.assertEqual(token.scorer, main.Scorer.MULT_ADD)
        self.assertEqual(token.scorer_amount, 4)
        self.assertEqual(token.runs_left, 2)
        self.assertEqual((token.x, token.y), (3, 4))  # the cell it stood in
        self.assertEqual(token.effects, [main.Effect.BOUNCY])
        self.assertEqual(self.game.cash, cash_before)  # a sacrifice pays nothing


    def test_spirit_refuses_roles_scorerless_blocks_and_a_full_token_column(self):
        action = main.ActionItem(main.Action.SPIRIT, 36)
        start = main.Block(3, 3, scorer=main.Scorer.START)
        plain = main.Block(4, 3, scorer=main.Scorer.NONE)
        self.game.grid[(3, 3)] = start
        self.game.grid[(4, 3)] = plain

        self.assertFalse(self.game._action_spirit(action, start))
        self.assertFalse(self.game._action_spirit(action, plain))
        self.assertFalse(self.game._action_spirit(
            action, main.CardItem(main.Card.GARDEN, 36)))

        self.game.tokens = [main.ScorerToken(main.Scorer.CASH, 15)
                            for _ in range(main.MAX_TOKENS)]
        keeper = main.Block(5, 3, scorer=main.Scorer.CASH, scorer_amount=15)
        self.game.grid[(5, 3)] = keeper
        self.assertFalse(self.game._action_spirit(action, keeper))
        self.assertIn((5, 3), self.game.grid)  # the block was not consumed


    def test_a_token_fires_its_scorer_at_the_start_of_each_run(self):
        seed = main.Block(3, 4, scorer=main.Scorer.MULT_ADD, scorer_amount=4,
                          effects=[])
        self.game.grid[(3, 4)] = seed
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), seed)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.upgrades_enabled = False
        self.game.score_mult = 1

        self.assertTrue(self.game.reset_run())

        # +4 mult from the kept scorer, on top of the fresh run's x1.
        self.assertEqual(self.game.score_mult, 5)
        self.assertTrue(self.game.tokens[0].fired)


    def test_a_satanic_token_dies_with_its_scorer_and_a_sharp_one_usually_survives(self):
        # Saturnic scorers destroy themselves after a run, so the token does
        # too; a Sharp scorer only has its usual 1/4 destruction chance.
        satanic = main.ScorerToken(main.Scorer.SATANIC, 6.66, runs_left=None)
        satanic.fired = True
        sharp = main.ScorerToken(main.Scorer.SHARP, 3, runs_left=None)
        sharp.fired = True
        self.game.tokens = [satanic, sharp]

        with mock.patch("main.random.random", return_value=0.9):
            self.game._advance_tokens()
        self.assertNotIn(satanic, self.game.tokens)
        self.assertIn(sharp, self.game.tokens)

        sharp.fired = True
        with mock.patch("main.random.random", return_value=0.1):
            self.game._advance_tokens()
        self.assertEqual(self.game.tokens, [])


    def test_portal_scorer_activates_when_marble_passes_through(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        # Passing through the entry portal fires its scorer once.
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(a.triggers_left, 0)
        self.assertEqual(b.triggers_left, 0)  # the pair shares one trigger count


    def test_portal_scorer_does_not_activate_on_exit_portal(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        # Arriving at the exit portal does NOT score it (the marble didn't pass through).
        self.assertEqual(self.game.score_chips, 0)
        self.assertEqual(b.triggers_left, 1)


    def test_portal_scorer_stops_after_trigger_limit(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        # First pass-through: scores and exhausts the portal (border turns red).
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(a.triggers_left, 0)
        self.assertEqual(b.triggers_left, 0)  # the pair shares one trigger count

        # A fresh pass-through: the scorer no longer fires.
        marble.position = np.array([a.rect.centerx, a.rect.centery], dtype=float)
        marble.velocity = np.array([0.0, 0.0])
        marble.collisions_last_tick = []
        marble.collisions_this_tick = []
        marble.last_portal_cells = None
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)  # unchanged


    def test_lone_portal_scorer_activates_on_pass_through(self):
        a = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        marble = self._add_marble((a.rect.centerx, a.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        # A portal with no partner still scores a marble that passes through it.
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(a.triggers_left, 0)


    def test_portal_scorer_resets_each_run(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        a.triggers_left = 0  # used up during a run

        self.assertTrue(self.game.reset_run())
        self.assertEqual(a.triggers_left, 1)  # the portal can score again next run
