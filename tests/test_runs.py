"""A run's life: scoring, cash, marbles, trails and the run cycle.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class RunsTests(GameTestCase):
    """A run's life: scoring, cash, marbles, trails and the run cycle."""


    def test_reset_run_requires_start_and_spawns_one_marble_per_start(self):
        # No start block: cannot start a run.
        self.assertFalse(self.game.reset_run())

        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = main.Block(3, 3, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 2)
        self.assertEqual(self.game.marbles[0].position[0], self.game.grid[(1, 1)].rect.centerx)
        self.assertEqual(self.game.marbles[1].position[0], self.game.grid[(3, 3)].rect.centerx)


    def test_marble_tracks_recent_speed_during_physics(self):
        game = main.Game()
        game.title_screen = False
        game.run_active = True
        marble = main.Marble(500, 200)
        marble.velocity = np.array([0.0, 2000.0])
        game.marbles.append(marble)
        game.update()
        # The marble's recent peak speed is sampled before collision resolution
        # each physics frame, so it tracks how fast the marble is moving.
        self.assertGreater(marble.recent_speed, 1000)


    def test_saving_mid_build_keeps_the_committed_runs_cash_and_result(self):
        # The save (P) / quit / MAIN MENU paths call _retry_run() while the
        # player is building, where the finished run was already COMMITTED by
        # CONTINUE: its cash award, its result entry and its win/loss all have
        # to survive that (only the results screen's RETRY takes them back).
        self.game.cash = 100
        self.game.score_total = 10000
        self.game.required_score = 1
        self.game._award_cash()          # the finished run's award lands
        cash_after_award = self.game.cash
        awarded = self.game.last_run_cash_gained
        self.game.run_results = [True]
        self.game.runs_cleared = 2
        self.game.failed_runs = 1
        self.game.run_complete = False
        self.game.awaiting_after_run = False   # CONTINUE was already clicked

        self.game._retry_run()                 # the save/quit/menu path

        self.assertEqual(self.game.cash, cash_after_award)
        self.assertEqual(self.game.last_run_cash_gained, awarded)
        self.assertEqual(self.game.run_results, [True])
        self.assertEqual(self.game.runs_cleared, 2)
        self.assertEqual(self.game.failed_runs, 1)


    def test_cash_readout_breakdown_survives_save_and_load(self):
        save_system.start_new_game_in_slot(self.game, 3)
        self.game.trials_enabled = False
        self.game.last_run_cash_gained = 55
        self.game.last_run_cash_breakdown = {"base": 20, "interest": 5,
                                             "score": 0, "cards": 0,
                                             "scorers": 30}
        save_system.save_game(self.game)
        fresh = main.Game()
        save_system.load_slot(fresh, 3)
        self.assertEqual(fresh.last_run_cash_gained, 55)
        self.assertEqual(fresh.last_run_cash_breakdown,
                         {"base": 20, "interest": 5, "score": 0,
                          "cards": 0, "scorers": 30})
        self.assertEqual(sum(fresh.last_run_cash_breakdown.values()), 55)


    def test_resource_points_persist_across_runs(self):
        # Banked resource points are not reset when a new run starts, but this
        # run's pending gain is.
        self.game.shred_points = 3
        self.game.rubble_points = 1
        self.game.shred_run_gain = 5
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.shred_points, 3)
        self.assertEqual(self.game.rubble_points, 1)
        self.assertEqual(self.game.shred_run_gain, 0)


    def test_resource_display_counts_pending_run_points(self):
        # While a run is active, points earned this run count toward the next
        # conversion in the display (the reward itself is granted after a run).
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.RUBBLE, amount=1))
        self.game.run_active = True
        self.game.rubble_run_gain = 0.5
        self.assertEqual(self.game._resource_display(), [(0.5, "block")])
        # A whole point pending reads as a fresh countdown (conversion deferred).
        self.game.rubble_run_gain = 1
        self.assertEqual(self.game._resource_display(), [(1, "block")])


    def test_retry_keeps_the_pre_rolled_random_outcome(self):
        # Retrying a run replays it, so the pre-rolled result must survive the
        # retry (which resets the run back to build state).
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 100
        self.game.score_mult = 1
        with mock.patch("main.random.random", return_value=0.0):  # +35 chips
            self.game._roll_run_random_outputs()
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            self.game._retry_run()  # must NOT re-roll
        self.assertEqual(block.random_rolls.get("reward"), 0)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 135)
        self.assertEqual(self.game.score_mult, 1)


    def test_random_items_entering_mid_run_roll_on_first_use(self):
        # A block placed after the opening roll has no stored result, so it
        # rolls on its first trigger and then keeps that result.
        block = main.Block(2, 2, scorer=main.Scorer.RANDOM, trigger_limit=2)
        self.game.grid[(2, 2)] = block
        self.game.score_chips = 100
        self._touch_block(block, 0.0)  # +35 chips
        self.assertEqual(self.game.score_chips, 135)
        self._touch_block(block, 0.9)  # still chips, not xMult
        self.assertEqual(self.game.score_chips, 170)


    def test_debt_gives_60_chips_and_marks_the_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.DEBT)
        self.game.grid[(0, 0)] = block
        self.game.run_active = True
        self.game.score_chips = 0
        self.assertFalse(self.game.debt_run_triggered)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_chips, 60)
        self.assertTrue(self.game.debt_run_triggered)
        self.assertEqual(block.triggers_left, 0)


    def test_the_rewind_puts_a_marble_back_one_second(self):
        # The rewind is a state restore: the marble returns to the snapshot it
        # took one second ago (the oldest in its history), and the second it
        # left behind is dropped so it can never be replayed twice.
        marble = main.Marble(100, 100)
        marble.position = np.array([300.0, 400.0])
        marble.velocity = np.array([10.0, 20.0])
        marble.angular_velocity = 3.0
        marble.history.append(marble.motion_state())
        # ...then the last second happens, which the rewind undoes:
        marble.position = np.array([500.0, 600.0])
        marble.velocity = np.array([99.0, 99.0])
        marble.sticky_timer = 0.5
        marble.sticky_velocity = np.array([1.0, 1.0])
        marble.history.append(marble.motion_state())
        self.game.marbles = [marble]
        self.game.cards = [main.CardItem(main.Card.PROCRASTINATION, 46)]

        self.assertTrue(self.game._procrastination_rewind())

        self.assertTrue(np.allclose(marble.position, [300.0, 400.0]))
        self.assertTrue(np.allclose(marble.velocity, [10.0, 20.0]))
        self.assertEqual(marble.angular_velocity, 3.0)
        self.assertEqual(marble.sticky_timer, 0.0)      # the hold never happened
        self.assertIsNone(marble.sticky_velocity)
        self.assertEqual(list(marble.history), [])       # the future is gone
        self.assertTrue(self.game.procrastination_used)


    def test_the_rewind_history_is_exactly_one_second_deep(self):
        # One snapshot per frame, so the oldest one a run keeps is exactly a
        # second back — the rewind span — and never further.
        self.assertAlmostEqual(main.PROCRASTINATION_REWIND_FRAMES * main.DT,
                               main.PROCRASTINATION_REWIND_SECONDS)
        # A run with no Finish block never ends, so it just keeps recording.
        self.game.grid.clear()
        self.game.grid[(5, 1)] = main.Block(5, 1, scorer=main.Scorer.START)
        self.game.reset_run()
        marble = self.game.marbles[0]
        self.assertEqual(marble.history.maxlen,
                         main.PROCRASTINATION_REWIND_FRAMES + 1)
        for _ in range(main.PROCRASTINATION_REWIND_FRAMES + 20):
            self.game.update()
        self.assertFalse(self.game.run_complete)
        self.assertEqual(len(marble.history), marble.history.maxlen)


    def test_a_rewind_with_no_history_leaves_the_marble_alone(self):
        # A marble released this frame has nothing behind it (and a new run's
        # marbles start with an empty history, so a rewind can never reach into
        # the previous run): it stays where it is.
        marble = main.Marble(120, 340)
        marble.velocity = np.array([7.0, 8.0])
        self.game.marbles = [marble]
        self.game.cards = [main.CardItem(main.Card.PROCRASTINATION, 46)]

        self.assertTrue(self.game._procrastination_rewind())

        self.assertTrue(np.allclose(marble.position, [120.0, 340.0]))
        self.assertTrue(np.allclose(marble.velocity, [7.0, 8.0]))


    def test_wrecking_ball_banks_three_quarters_of_its_own_magnitude(self):
        # A Fragile Breaks +Mult card rolled to 6 banks 0.75 x 6 = +4.5 mult a
        # break (0.75 x 4 = +3 at the average).
        block = main.Block(1, 1, scorer=main.Scorer.NONE, effects=[main.Effect.FRAGILE])
        value = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS,
                                           main.Scorer.MULT_ADD)
        card = main.make_card_item(value, amount=6)
        self.game.cards.append(card)
        self.game.wrecking_run_gain = {main.Scorer.CHIPS_ADD: 0,
                                       main.Scorer.MULT_ADD: 0,
                                       main.Scorer.MULT_MUL: 1.0}
        self.game.score_mult = 1

        main.cards.on_fragile_broken(self.game, block)

        self.assertEqual(card.amount, 6)
        self.assertAlmostEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 4.5)
        self.assertAlmostEqual(self.game.score_mult, 1)  # no run active


    def test_compute_total_score_is_base_raised_to_linear_exponent(self):
        # base = 300; exponent = (time/2 + dist + uniq) * (4/5), so the total
        # is base ** exponent (chips * mult raised to a linear mix of the
        # run's time, distance, and uniqueness factors).
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE / 2
        self.game.score_chips = 100
        self.game.score_mult = 3
        self.game.run_time = main.TIME_IDEAL  # ideal time -> time_good peaks
        self.game.touched_shapes = {main.Shape.SLOPE}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}  # 3 unique types

        time_good, dist_good, uniq_good, _ = self.game._score_factors()
        exponent = (time_good / 2 + dist_good + uniq_good) * (4 / 5)

        # The total keeps its fractional value internally (rounded only on
        # display), so it equals the raw float base ** exponent.
        self.assertEqual(self.game._compute_total_score(), 300 ** exponent)


    def test_compute_total_score_floor_is_base_to_min_exponent(self):
        # No time/distance/uniqueness -> the exponent drops to ~0, so the
        # score is base ** ~0, essentially 1 (the minimum a run can score).
        # The total is a float now (rounded only on display), so it can sit a
        # hair above 1.0 rather than truncating to exactly 1.
        self.game.score_chips = 50
        self.game.score_mult = 2
        self.game.run_time = 1e6  # far from the ideal time
        total = self.game._compute_total_score()
        self.assertAlmostEqual(total, 1.0)
        self.assertGreaterEqual(total, 1.0)


    def test_compute_total_score_guards_zero_base(self):
        # chips * mult = 0 clamps to a base of 1 so 1 ** anything is 1.
        self.game.score_chips = 0
        self.game.score_mult = 1
        self.game.run_time = 0.0
        self.assertEqual(self.game._compute_total_score(), 1)


    def test_compute_total_score_grows_with_better_run(self):
        # A fast, far, varied run scores strictly higher than a slow, sparse one.
        self.game.score_chips = 50
        self.game.score_mult = 3
        self.game.run_time = 1e6
        self.game.touched_shapes = set()
        self.game.touched_effects = set()
        self.game.touched_scorers = set()
        weak = self.game._compute_total_score()

        self.game.run_time = main.TIME_SCALE  # fast: full time bonus
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE
        self.game.touched_shapes = {main.Shape.RECT, main.Shape.SLOPE, main.Shape.CIRCLE}
        self.game.touched_effects = {main.Effect.BOUNCY, main.Effect.PISTON}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD, main.Scorer.MULT_MUL}
        strong = self.game._compute_total_score()

        self.assertGreater(strong, weak)


    def test_score_factors_are_normalized_zero_to_one(self):
        self.game.run_time = main.TIME_IDEAL  # ideal time -> time_good 1.0
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE * 2
        self.game.touched_shapes = set(main.Shape.ORDER)
        self.game.touched_effects = set(main.Effect.ORDER)
        self.game.touched_scorers = set(main.Scorer.ORDER)

        time_good, dist_good, uniq_good, unique_types = self.game._score_factors()

        self.assertEqual(unique_types,
                         len(main.Shape.ORDER) + len(main.Effect.ORDER) + len(main.Scorer.ORDER))
        # Time peaks just below 1.0 (its modulator makes a zero-length run
        # score 0 on time) and distance saturates toward (but never exceeds)
        # 1.0 via arctan. Uniqueness is LINEAR: uniq_good = unique_types /
        # UNIQUE_SCALE, so it can exceed 1.0 when more than UNIQUE_SCALE types
        # are touched (UNIQUE_SCALE is 1/2 the total component count).
        self.assertAlmostEqual(time_good, 875 / 884, places=6)
        for value in (time_good, dist_good):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
        self.assertEqual(uniq_good, unique_types / main.UNIQUE_SCALE)
        self.assertGreater(dist_good, 0.0)
        self.assertLess(dist_good, 1.0)
        self.assertGreater(uniq_good, 1.0)  # more than UNIQUE_SCALE types touched
        # A zero-length run scores 0 on time (the modulator's purpose).
        self.game.run_time = 0.0
        time_zero, _, _, _ = self.game._score_factors()
        self.assertAlmostEqual(time_zero, 0.0, places=6)


    def test_marble_accumulates_distance(self):
        marble = self._add_marble()
        marble.velocity = np.array([60.0, 0.0])
        marble.physics.update(marble, main.DT, [])
        self.assertGreater(marble.distance, 0.5)


    def test_rubber_ball_bounces_off_border(self):
        # A rubber-ball marble bounces back off the marble-box border with full
        # energy instead of stopping at the edge.
        marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 5, 300)
        marble.velocity = np.array([-100.0, 0.0])
        marble.bouncy = True
        marble.physics.keep_in_bounds(marble)
        self.assertGreater(marble.velocity[0], 0.0)  # reflected to the right


    def test_marble_spin_angle_advances_when_rolling(self):
        # A moving marble that is grounded (rolling on the bottom border)
        # accumulates its spin angle from its angular velocity.
        marble = self._add_marble()
        marble.position = np.array([500.0, main.MARBLE_BOX_COORDS[1] + main.MARBLE_BOX_COORDS[3] + 10])
        marble.velocity = np.array([50.0, 0.0])
        before = marble.spin_angle
        marble.physics.update(marble, main.DT, [])
        self.assertGreater(marble.spin_angle, before)


    def test_marble_does_not_spin_when_stationary(self):
        marble = self._add_marble()
        marble.position = np.array([500.0, main.MARBLE_BOX_COORDS[1] + main.MARBLE_BOX_COORDS[3] + 10])
        marble.velocity = np.array([0.0, 0.0])
        marble.physics.update(marble, main.DT, [])
        self.assertEqual(marble.spin_angle, 0.0)


    def test_reset_run_applies_marble_type_to_spawned_marbles(self):
        # Spawned marbles inherit the save's marble type; rubber balls get two
        # random (distinct) half-colors and the bouncy flag.
        self.game.marble_type = main.MarbleType.RUBBER_BALL
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 1)
        m = self.game.marbles[0]
        self.assertEqual(m.marble_type, main.MarbleType.RUBBER_BALL)
        self.assertTrue(m.bouncy)
        self.assertNotEqual(m.color, m.color2)


    def test_reset_run_spawns_light_ping_pong_marble(self):
        # Spawned ping-pong marbles are very light (low mass + slight
        # restitution) and wear two distinct half-colors, but do not use the
        # rubber ball's full bouncy flag.
        self.game.marble_type = main.MarbleType.PING_PONG
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        m = self.game.marbles[0]
        self.assertEqual(m.marble_type, main.MarbleType.PING_PONG)
        self.assertAlmostEqual(m.mass, main.PING_PONG_MASS)
        self.assertAlmostEqual(m.restitution, main.PING_PONG_RESTITUTION)
        self.assertFalse(m.bouncy)  # not the rubber ball's full bounce
        self.assertNotEqual(m.color, m.color2)


    def test_run_cleared_when_score_meets_requirement(self):
        marble = self._add_marble()
        marble.distance = main.DISTANCE_SCALE  # a far run boosts the score
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.run_time = main.TIME_IDEAL  # ideal time -> full time factor
        self.game.score_chips = 500
        self.game.score_mult = 20
        self.game.touched_shapes = {main.Shape.SLOPE}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}
        self.game.required_score = 1000

        self.game._handle_block_contacts([])

        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.run_complete)
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(self.game.awaiting_after_run)
        # Progression is deferred until the player clicks CONTINUE.
        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.required_score, 1000)
        self.assertEqual(self.game.run_results, [True])
        self.assertEqual(self.game.runs_cleared, 1)

        self.game._continue_run()

        self.assertEqual(self.game.run_number, 1)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])
        self.assertFalse(self.game.run_complete)


    def test_run_not_cleared_when_score_below_requirement(self):
        marble = self._add_marble()
        marble.distance = 100.0
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.run_time = 3.0
        self.game.score_chips = 100
        self.game.score_mult = 2
        self.game.required_score = 10000

        self.game._handle_block_contacts([])

        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.run_cleared)
        self.assertTrue(self.game.awaiting_after_run)
        # A failed run counts as a fail but doesn't advance until CONTINUE.
        self.assertEqual(self.game.run_results, [False])
        self.assertEqual(self.game.failed_runs, 1)
        self.assertEqual(self.game.required_score, 10000)

        self.game._continue_run()

        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])


    def test_reset_run_clears_run_cleared_flag(self):
        self.game.run_cleared = True
        self.game.run_complete = True
        # Seed a valid start + finish so the run can begin.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.grid[(5, 5)] = main.Block(5, 5, scorer=main.Scorer.FINISH)

        self.game.reset_run()

        self.assertFalse(self.game.run_cleared)
        self.assertFalse(self.game.run_complete)
        # The target stays on the current run across resets.
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[0])


    def test_run_results_are_native_bools_for_json(self):
        # A cleared run's result must be a native Python bool. The total score
        # is built from numpy score factors, so without coercion it leaks a
        # numpy float -> numpy bool into run_results, which then breaks JSON
        # saves ("Object of type bool is not JSON serializable").
        self.game.marble_type = main.MarbleType.PING_PONG  # any type triggers it
        self._complete_run(1000000, required=1)
        self.assertEqual(self.game.run_results, [True])
        self.assertIs(type(self.game.run_results[0]), bool)
        self.assertIs(type(self.game.score_total), float)


    def test_required_score_schedule_grows_monotonically(self):
        # The lazily-grown schedule: every run's target DOUBLES the previous
        # one (REQUIRED_SCORES starts as [1] and grows on demand), so the
        # targets keep rising.
        main.REQUIRED_SCORES[:] = [1]
        prev = main.REQUIRED_SCORES[0]
        for run in range(1, main.TOTAL_RUNS):
            expected = prev * 2
            self.assertEqual(main.get_next_required_score(run), expected)
            self.assertGreater(expected, prev)  # targets keep rising
            prev = expected
        # The grown schedule is exactly the doubling series [1, 2, 4, 8, ...].
        self.assertEqual(main.REQUIRED_SCORES,
                         [2 ** i for i in range(main.TOTAL_RUNS)])
        # Asking for an earlier run never re-grows or changes the schedule.
        self.assertEqual(main.get_next_required_score(1), 2)
        main.REQUIRED_SCORES[:] = [1]  # restore for the tests that follow


    def test_three_failed_runs_means_defeat(self):
        # The 3rd lost run ends the game immediately with a defeat game over.
        # (Required scores are set explicitly so each run's outcome is exact.)
        self._complete_run(1000000, required=1)  # run 1: clear
        self.game._continue_run()
        self._complete_run(100, required=1000)  # run 2: fail (1st loss)
        self.game._continue_run()
        self.assertFalse(self.game.game_over)
        self._complete_run(100, required=1000)  # run 3: fail (2nd loss)
        self.game._continue_run()
        self.assertFalse(self.game.game_over)
        self._complete_run(100, required=1000)  # run 4: fail (3rd loss)
        self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertFalse(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.run_number, 4)
        self.assertEqual(self.game.failed_runs, 3)


    def test_perfect_win_when_all_runs_cleared(self):
        for _ in range(main.TOTAL_RUNS):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)
        self.assertEqual(self.game.runs_cleared, main.TOTAL_RUNS)


    def test_game_won_after_22_runs_met_with_two_fails(self):
        # 2 spread-out fails, 22 clears: reaches run 24, clears the boss run,
        # and wins (not perfect). Failing the final run would end in defeat.
        for run in range(main.TOTAL_RUNS):
            if run in (2, 12):
                self._complete_run(100, required=1000)  # fail
            else:
                self._complete_run(1000000, required=1)  # clear
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.runs_cleared, main.REQUIRED_RUNS_TO_WIN)


    def test_reset_game_starts_fresh_game(self):
        # Play a couple runs, then reset.
        self._play_run(0)
        self.game.score_total = 999
        self.game.reset_game()
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.round_index, 0)
        self.assertEqual(self.game.run_in_round, 0)
        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.failed_runs, 0)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[0])
        self.assertEqual(self.game.grid, {})


    def test_sounds_helpers_are_safe_without_audio(self):
        # The sound module loads and its helpers never raise, even headless
        # (where the mixer is unavailable and every sound is None).
        import sounds
        sounds.play_coin()
        sounds.play_mech()
        sounds.play_plop()
        self.assertTrue(sounds.COIN is None or sounds.COIN is not None)


    def test_run_start_and_reset_sounds_are_built(self):
        # A run starting and a run being reset each have their own sound.
        import sounds
        if sounds._mixer_ok:
            self.assertIsNotNone(sounds.RUN_START)
            self.assertIsNotNone(sounds.RESET)
        else:  # no audio device: every sound is a silent None
            self.assertIsNone(sounds.RUN_START)
            self.assertIsNone(sounds.RESET)


    def test_component_sound_helpers_route_through_play(self):
        # Every effect and scorer can be played, plus the two run sounds.
        import sounds
        with mock.patch("sounds.play") as play:
            for effect in main.Effect.ORDER:
                sounds.play_effect(effect)
            for scorer in main.Scorer.ORDER:
                sounds.play_scorer(scorer)
            sounds.play_run_start()
            sounds.play_reset()
        self.assertEqual(play.call_count, len(main.Effect.ORDER)
                         + len(main.Scorer.ORDER) + 2)


    def test_retry_sounds_the_reset_but_other_rollbacks_do_not(self):
        # A real retry (a finished run being undone) rings; the save/quit/menu
        # rollback while building does not.
        with mock.patch("main.sounds.play_reset") as play:
            self.game._retry_run()
        play.assert_not_called()
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.sounds.play_reset") as play:
            self.game._retry_run()
        play.assert_called_once()


    def test_zipper_lets_a_marble_through_only_the_open_way(self):
        # Arrow down (a rotated zipper): a dropped marble falls right through.
        open_block = main.Block(5, 5, effect=main.Effect.ZIPPER,
                                scorer=main.Scorer.NONE)
        open_block.angle = 180
        marble = main.Marble(open_block.rect.centerx, open_block.rect.top - 10)
        for _ in range(60):
            marble.physics.update(marble, main.DT, [open_block])
        self.assertGreater(marble.position[1], open_block.rect.bottom)
        # Arrow up (the default): the same drop is caught on top of it.
        shut_block = main.Block(5, 5, effect=main.Effect.ZIPPER,
                                scorer=main.Scorer.NONE)
        marble = main.Marble(shut_block.rect.centerx, shut_block.rect.top - 10)
        for _ in range(120):
            marble.physics.update(marble, main.DT, [shut_block])
        self.assertLess(marble.position[1], shut_block.rect.bottom)


    def test_marbles_collide_with_each_other(self):
        a = self._add_marble((300.0, 300.0))
        b = self._add_marble((310.0, 300.0))  # overlapping (radius 8 each)
        a.velocity = np.array([50.0, 0.0])
        b.velocity = np.array([-50.0, 0.0])
        a.physics.resolve_marble_collisions(self.game.marbles)
        # Pushed apart along the line between their centers...
        self.assertGreater(b.position[0] - a.position[0], 10.0)
        # ...and their normal speeds swapped (an equal-mass elastic hit).
        self.assertLess(a.velocity[0], 0.0)
        self.assertGreater(b.velocity[0], 0.0)


    def test_a_phasing_marble_passes_through_other_marbles(self):
        a = self._add_marble((300.0, 300.0))
        b = self._add_marble((305.0, 300.0))
        a.phase_timer = 0.5
        a.physics.resolve_marble_collisions(self.game.marbles)
        # Still overlapping: a phasing marble is skipped by the marble-vs-marble
        # separation (the phase effect passes through everything).
        self.assertLess(float(np.linalg.norm(b.position - a.position)),
                        a.radius + b.radius)


    def test_plane_plus_mult_scales_proportionally_with_air_time(self):
        # Air Time (Plane) has ratio 0.5, so +Mult pays half the +4 base = +2
        # mult per air second at the end of the run.
        value = main.condition_scorer_card(main.Condition.AIR_TIME,
                                           main.Scorer.MULT_ADD)
        self.assertEqual(main.Card.name(value), "Plane +Mult")
        self.game.cards.append(main.CardItem(value, 40))
        self.game.air_time = 2.0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_mult, 1 + 2 * 2.0)


    def test_score_display_rounds_to_nearest_tenth_only(self):
        # Chips/mult/total stay fractional internally; the UI text rounds them
        # to the nearest tenth (whole values stay plain).
        import ui
        self.assertEqual(ui._fmt_tenth(38.5), "38.5")
        self.assertEqual(ui._fmt_tenth(40.0), "40")
        self.assertEqual(ui._fmt_tenth(38.53), "38.5")
        self.assertEqual(ui._fmt_tenth(3), "3")
        self.assertEqual(ui._fmt_tenth(7.0), "7")
        self.assertEqual(ui._fmt_tenth(0.26), "0.3")


    def test_xmult_rewards_always_multiply(self):
        # The per-item "later triggers only add" rule is gone: _apply_xmult
        # multiplies, returns the factor (the particle's figure), and no
        # priming state is left to get out of step with a run.
        self.game.score_mult = 2

        self.assertEqual(self.game._apply_xmult(1.25), 1.25)

        self.assertAlmostEqual(self.game.score_mult, 2.5)
        self.assertFalse(hasattr(self.game, "_xmult_primed"))


    def test_wrecking_ball_run_gain_commits_when_continuing(self):
        # The gains earned during a run become permanent only after that run.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game.run_active = True
        self.game._on_fragile_broken(block)
        self.game._on_fragile_broken(block)  # two breaks this run
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 6)
        self._complete_run(10000, required=100)
        self.game._continue_run()
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 6)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 0)


    def test_plane_air_time_accumulates_while_marble_airborne(self):
        # A marble with nothing under it stays airborne, so air time grows.
        self.game.cards.append(main.CardItem(main.Card.PLANE, 25))
        self.game.marbles = [main.Marble(360, 120)]
        self.game.run_active = True
        for _ in range(30):
            self.game.update()
        self.assertGreater(self.game.air_time, 0.2)  # ~0.5s of air time


    def test_plane_air_time_stays_zero_while_marble_rests(self):
        # A marble resting on a floor block is in contact, so no air time.
        self.game.cards.append(main.CardItem(main.Card.PLANE, 25))
        floor = main.Block(5, 8)
        self.game.grid[(5, 8)] = floor
        marble = main.Marble(floor.rect.centerx, floor.rect.top - main.MARBLE_RADIUS - 1)
        self.game.marbles = [marble]
        self.game.run_active = True
        for _ in range(20):
            self.game.update()
        self.assertLess(self.game.air_time, 0.2)


    def test_black_hole_time_accumulates_while_marble_pulled(self):
        # A marble inside a black hole's range accumulates pull time each frame.
        block = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.BLACK_HOLE)
        self.game.grid[(5, 5)] = block
        marble = main.Marble(block.rect.centerx, block.rect.centery + 60)
        self.game.marbles.append(marble)
        self.game.run_active = True
        self.game.black_hole_time = 0.0
        for _ in range(30):
            self.game.update()
        self.assertGreater(self.game.black_hole_time, 0)


    def test_explorer_applies_when_run_completes(self):
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        block = main.Block(0, 0, shape=main.Shape.SLOPE, scorer=main.Scorer.FINISH)
        marble = self._add_marble()
        marble.distance = 3000.0
        marble.collisions_this_tick = [block]
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_mult = 1
        self.game._handle_block_contacts([block])
        fraction = (3000 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT)
        self.assertAlmostEqual(self.game.score_mult, 1 + fraction)
        self.assertTrue(self.game.run_complete)


    def test_marble_leaves_trail_while_moving(self):
        # A moving marble drops shrinking trail dots behind it.
        game = main.Game()
        game.title_screen = False
        game.run_active = True
        marble = main.Marble(500, 200)
        marble.velocity = np.array([200.0, 0.0])
        game.marbles.append(marble)
        for _ in range(30):
            game.update()
        self.assertGreater(len(game.trail_particles), 0)


    def test_trails_clear_on_new_run(self):
        self.game.trail_particles.append(
            main.TrailParticle(100, 100, 4.0, main.MARBLE_COLOR))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run(False)
        self.assertEqual(self.game.trail_particles, [])


    # --- Difficulty (chosen when a new save begins) -------------------------

    def test_difficulty_levels_are_defined(self):
        # Four levels, each naming itself and spelling its rules out, plus the
        # two knobs the game reads: how many of a round's runs play a trial and
        # the factor the required score grows by each run.
        self.assertEqual(main.Difficulty.ORDER, [1, 2, 3, 4])
        for level in main.Difficulty.ORDER:
            with self.subTest(difficulty=level):
                self.assertTrue(main.Difficulty.name(level))
                self.assertTrue(main.Difficulty.description(level))
                self.assertGreaterEqual(main.Difficulty.trials_per_round(level), 1)
                self.assertLessEqual(main.Difficulty.trials_per_round(level),
                                     main.RUNS_PER_ROUND)
                self.assertGreater(main.Difficulty.score_growth(level), 1.0)
        # The ladder the levels describe: 1.6x targets only on level 1, and a
        # trial on the round's last run for 1-2, its last two for 3, and every
        # run for 4.
        self.assertAlmostEqual(main.Difficulty.score_growth(1), 1.6)
        self.assertEqual([main.Difficulty.score_growth(level) for level in (2, 3, 4)],
                         [2.0, 2.0, 2.0])
        self.assertEqual([main.Difficulty.trials_per_round(level)
                          for level in (1, 2, 3, 4)], [1, 1, 2, 3])
        # A save with no difficulty of its own (an old save, a fresh game) is
        # the game's original balance: a trial for every run, doubling targets.
        self.assertEqual(main.DEFAULT_DIFFICULTY, main.Difficulty.LEVEL_4)


    def test_the_difficulty_sets_how_fast_the_target_grows(self):
        # Difficulty 1 asks 1.6x the last run's target, rounded down but never
        # less than one more than the last (so it can't stall at 1); the other
        # levels double it.
        try:
            main.REQUIRED_SCORES[:] = [1]
            gentle = [main.get_next_required_score(run, 1.6) for run in range(6)]
            main.REQUIRED_SCORES[:] = [1]
            doubled = [main.get_next_required_score(run, 2.0) for run in range(5)]
            # ...and a caller with no difficulty to hand still gets the 2x the
            # rest of the game assumes.
            main.REQUIRED_SCORES[:] = [1]
            default = [main.get_next_required_score(run) for run in range(4)]
        finally:
            main.REQUIRED_SCORES[:] = [1]  # the tests that follow expect this

        self.assertEqual(gentle, [1, 2, 3, 4, 6, 9])
        self.assertEqual(doubled, [1, 2, 4, 8, 16])
        self.assertEqual(default, [1, 2, 4, 8])


    def test_the_difficulty_is_saved(self):
        # The save carries the difficulty (the rules the save plays by), so a
        # loaded game keeps them.
        self.game.difficulty = main.Difficulty.LEVEL_3
        self.game.current_trial = main.Trial.SPEEDRUN

        data = save_system._save_data(self.game)

        self.assertEqual(data["difficulty"], main.Difficulty.LEVEL_3)
        fresh = main.Game()
        save_system._load_save_data(fresh, data, 1)
        self.assertEqual(fresh.difficulty, main.Difficulty.LEVEL_3)
        self.assertEqual(fresh.current_trial, main.Trial.SPEEDRUN)
        # ...and the rules that level stands for are the loaded game's own.
        self.assertEqual(fresh.trials_per_round,
                         main.Difficulty.trials_per_round(main.Difficulty.LEVEL_3))
        self.assertEqual(fresh.score_growth,
                         main.Difficulty.score_growth(main.Difficulty.LEVEL_3))

        # A save written before the difficulty existed reads as the default
        # level (the game's original balance).
        legacy = dict(data)
        legacy.pop("difficulty")
        old = main.Game()
        save_system._load_save_data(old, legacy, 1)
        self.assertEqual(old.difficulty, main.DEFAULT_DIFFICULTY)
        self.assertEqual(old.trials_per_round, main.RUNS_PER_ROUND)


    def test_long_run_doubles_ideal_time(self):
        # With Long run, the time factor peaks at double the ideal time and is
        # off-peak at the normal ideal time.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.run_time = main.TIME_IDEAL * 2
        peak, _, _, _ = self.game._score_factors()
        self.game.run_time = main.TIME_IDEAL
        off_peak, _, _, _ = self.game._score_factors()
        self.assertGreater(peak, 0.9)
        self.assertGreater(peak, off_peak)
        self.assertLess(off_peak, 0.5)


    def test_repeats_only_counts_types_only_once_touched_twice(self):
        # Under Repeats only, a type contributes to the uniqueness score only
        # after two distinct fresh touches (each qualifying type counts once).
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.REPEATS_ONLY
        block = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        # One fresh touch: nothing qualifies yet.
        self.game._count_fresh_touch(block)
        _, _, _, unique = self.game._score_factors()
        self.assertEqual(unique, 0)
        # A second fresh touch of the same block type qualifies all three types.
        self.game._count_fresh_touch(block)
        _, _, _, unique = self.game._score_factors()
        self.assertEqual(unique, 3)


    def test_empty_pockets_skips_only_score_based_cash(self):
        # Empty pockets drops the score-ratio part of the end-of-run cash, but
        # the flat $20, interest, and Cash-card payouts still land.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.EMPTY_POCKETS
        self.game.cash = 50
        self.game.score_total = 100
        self.game.required_score = 10
        self.game.card_cash_run_gain = 7
        self.game._award_cash()
        # 0 (score-ratio skipped) + 20 + 50//10 + 7
        self.assertEqual(self.game.last_run_cash_gained, 20 + 5 + 7)
        self.assertEqual(self.game.cash, 50 + 20 + 5 + 7)
        # Without the trial the score-based bonus is included.
        other = main.Game()
        other.trials_enabled = False
        other.cash = 50
        other.score_total = 100
        other.required_score = 10
        other.card_cash_run_gain = 7
        other._award_cash()
        expected_gain = int(main.CASH_SCALE * (np.log(100) - np.log(10))) + 20 + 5 + 7
        self.assertEqual(other.cash, 50 + expected_gain)


    def test_retry_undoes_cleared_run(self):
        self.game.cash = 100
        self._complete_run(10000, required=1)
        self.assertTrue(self.game.awaiting_after_run)
        self.assertEqual(self.game.runs_cleared, 1)

        self.game._retry_run()

        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.runs_cleared, 0)
        self.assertEqual(self.game.last_run_cash_gained, 0)
        self.assertAlmostEqual(self.game.cash, 100)  # award undone
        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.required_score, 1)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)


    def test_retry_undoes_failed_run(self):
        self._complete_run(100, required=1000)
        self.assertEqual(self.game.failed_runs, 1)

        self.game._retry_run()

        self.assertEqual(self.game.failed_runs, 0)
        self.assertEqual(self.game.run_results, [])
        self.assertFalse(self.game.run_complete)


    def test_continue_advances_to_next_run(self):
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self.game._continue_run()  # the player CONTINUEs to the next run

        self.assertEqual(self.game.run_number, 1)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)


    def test_touched_types_recorded_from_contacts(self):
        b1 = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        b2 = main.Block(1, 0, shape=main.Shape.RECT, effect=main.Effect.NONE,
                        scorer=main.Scorer.MULT_ADD, scorer_amount=2)
        marble = self._add_marble()
        marble.collisions_this_tick = [b1, b2]
        self.game.run_active = True

        self.game._handle_block_contacts([b1, b2])

        # Plain/basic parts are excluded from uniqueness: RECT shapes, the NONE
        # effect, and START/FINISH scorers do not count.
        self.assertEqual(self.game.touched_shapes, {main.Shape.SLOPE})
        self.assertEqual(self.game.touched_effects, {main.Effect.BOUNCY})
        self.assertEqual(self.game.touched_scorers, {main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD})


    def test_award_cash_is_log_difference_of_score_to_required(self):
        self.game.cash = 0
        self.game.score_total = 100
        self.game.required_score = 10

        self.game._award_cash()

        expected = int(main.CASH_SCALE * (np.log(100) - np.log(10))) + 20
        self.assertAlmostEqual(self.game.cash, expected)
        self.assertAlmostEqual(self.game.last_run_cash_gained, expected)


    def test_award_cash_never_logs_zero_score(self):
        # A score_total of 0 (run not yet scored) clamps to 1 so no -inf; only
        # the flat +20 bonus is awarded.
        self.game.cash = 0
        self.game.score_total = 0
        self.game.required_score = 4

        self.game._award_cash()

        self.assertAlmostEqual(self.game.cash, 20.0)
        self.assertAlmostEqual(self.game.last_run_cash_gained, 20.0)


    def test_completed_run_awards_log_difference_cash(self):
        self.game.cash = 0
        b1 = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = self._add_marble()
        marble.collisions_this_tick = [b1]
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = 1000
        self.game.score_mult = 2
        self.game.run_time = main.TIME_IDEAL
        self.game.required_score = 2

        self.game._handle_block_contacts([b1])

        self.assertTrue(self.game.run_cleared)
        # Cash is awarded as a whole number (int) plus a flat 20 bonus; the
        # required score clamps to a minimum of 2.
        expected = int(main.CASH_SCALE * (np.log(self.game.score_total) - np.log(2))) + 20
        self.assertAlmostEqual(self.game.last_run_cash_gained, expected)
        self.assertAlmostEqual(self.game.cash, expected)


    def test_touched_types_reset_each_run(self):
        self.game.touched_shapes = {main.Shape.RECT}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run())

        # The type bonus counts only the types touched THIS run.
        self.assertEqual(self.game.touched_shapes, set())
        self.assertEqual(self.game.touched_effects, set())
        self.assertEqual(self.game.touched_scorers, set())


    def test_touched_types_reset_on_new_game(self):
        self.game.touched_shapes = {main.Shape.RECT}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}

        self.game.reset_game()

        self.assertEqual(self.game.touched_shapes, set())
        self.assertEqual(self.game.touched_effects, set())
        self.assertEqual(self.game.touched_scorers, set())


    def test_continue_after_final_run_ends_game(self):
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)

        self._complete_run(1000000, required=1)  # 24th run clears and CONTINUEs
        self.game._continue_run()

        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)


    # --- Magnitudes: every scaleable value rolls around its average -------

    def test_magnitude_step_is_a_tenth_of_the_average(self):
        # A step is EXACTLY 10% of the average, never rounded to a whole number
        # (rounding 0.4 up to a whole 1 would stretch a +Mult scorer's spread
        # to 12 instead of 7.2).
        self.assertEqual(main.magnitude_step(30), 3)
        self.assertEqual(main.magnitude_step(1500), 150)
        self.assertEqual(main.magnitude_step(20000), 2000)
        self.assertEqual(main.magnitude_step(120), 12)
        self.assertEqual(main.magnitude_step(4), 0.4)    # not a whole 1
        self.assertEqual(main.magnitude_step(15), 1.5)   # not 2
        self.assertEqual(main.magnitude_step(8), 0.8)
        self.assertEqual(main.magnitude_step(2), 0.2)
        self.assertAlmostEqual(main.magnitude_step(1.5), 0.15)
        self.assertAlmostEqual(main.magnitude_step(0.75), 0.075)
        self.assertAlmostEqual(main.magnitude_step(0.4), 0.04)
        self.assertEqual(main.magnitude_step(0), 0)      # no average, no magnitude


    def test_magnitude_precision_is_scale_free(self):
        # A rolled value is written with the decimals a deviation of its size
        # can mean — two past the average's own scale — so a 0.01-average
        # Voyager keeps its 0.00919 as exactly as a 30-chip scorer keeps 28.26,
        # and no arithmetic dust ever reaches a price, a description or a save.
        self.assertEqual(main.magnitude_precision(30), 2)
        self.assertEqual(main.magnitude_precision(1500), 0)
        self.assertEqual(main.magnitude_precision(4), 3)
        self.assertEqual(main.magnitude_precision(0.75), 4)
        self.assertEqual(main.magnitude_precision(0.01), 5)
        self.assertEqual(main.magnitude_precision(0), 0)
        for scorer in (main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD,
                       main.Scorer.VOYAGER, main.Scorer.DRILL):
            average = main.Scorer.DEFAULT_AMOUNT[scorer]
            precision = main.magnitude_precision(average)
            for _ in range(50):
                amount = main.roll_scorer_amount(scorer)
                self.assertEqual(amount, round(amount, precision),
                                 main.Scorer.name(scorer))
                # The deviation token beside a magnitude is that same rounded
                # difference, so the two always add up on screen.
                token = components.magnitude_deviation(average, amount)
                if not token:
                    continue
                shown = float(token.strip(" ()").replace("+", ""))
                self.assertEqual(shown, round(amount - average, precision))


    def test_rolled_magnitudes_are_continuous(self):
        # A roll is the average plus a CONTINUOUS deviation, so a magnitude is
        # not confined to whole 10% steps: a whole-average scorer rolls onto
        # fractional amounts too, and a value a roll can land on is not one of
        # a handful of fixed points.
        for scorer in (main.Scorer.MULT_ADD, main.Scorer.SUMMIT,
                       main.Scorer.AIRBALL, main.Scorer.DRILL):
            average = main.Scorer.DEFAULT_AMOUNT[scorer]
            step = main.magnitude_step(average)
            rolls = [main.roll_scorer_amount(scorer) for _ in range(200)]
            fractional = [r for r in rolls if not float(r).is_integer()]
            self.assertTrue(fractional, main.Scorer.name(scorer))
            for amount in rolls:
                # Inside the widest deviation, and free of arithmetic noise.
                self.assertLessEqual(abs(amount - average),
                                     step * main.MAGNITUDE_MAX_STEPS)
                self.assertEqual(amount, round(amount, 9))
        # A whole average with a whole step is no longer pinned to whole values
        # (and far more than the 17 values the stepped roll could produce).
        chips = [main.roll_scorer_amount(main.Scorer.CHIPS_ADD) for _ in range(200)]
        self.assertTrue(any(not float(c).is_integer() for c in chips))
        self.assertGreater(len(set(chips)), 100)
        # A drill counts whole squares even though its magnitude is fractional.
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.DRILL), 0.2)


    def test_magnitude_floors_keep_a_roll_useful(self):
        # A multiplier never rolls below 1 (a factor under 1 would make the
        # block a penalty); every other magnitude never rolls below one step.
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.MULT_MUL), 1.0)
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.SHARP), 1.0)
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.CHIPS_ADD), 3)
        self.assertEqual(main.scorer_magnitude_floor(main.Scorer.NONE), 0)
        self.assertEqual(main.effect_magnitude_floor(main.Effect.PISTON), 150)


    def test_rolls_never_leave_the_allowed_range(self):
        scorers = [main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD, main.Scorer.MULT_MUL,
                   main.Scorer.SHARP, main.Scorer.SUMMIT, main.Scorer.COLOSSUS,
                   main.Scorer.PARTS, main.Scorer.SATANIC]
        for scorer in scorers:
            with self.subTest(scorer=main.Scorer.name(scorer)):
                average = main.Scorer.DEFAULT_AMOUNT[scorer]
                step = main.magnitude_step(average)
                floor = main.scorer_magnitude_floor(scorer)
                amounts = [main.roll_scorer_amount(scorer) for _ in range(500)]
                for amount in amounts:
                    self.assertGreaterEqual(amount, floor)
                    self.assertLessEqual(amount, average + step * main.MAGNITUDE_MAX_STEPS)
                    self.assertEqual(amount, round(amount, 9))
                # The deviations are continuous: they do not snap to whole
                # steps of 10% (the floor-clamped rolls are the exception,
                # which is the floor's whole job).
                off_step = [(a - average) / step for a in amounts
                            if a != floor
                            and abs((a - average) / step
                                    - round((a - average) / step)) > 1e-6]
                self.assertTrue(off_step, main.Scorer.name(scorer))
        # A scorer with no magnitude is left exactly alone.
        for scorer in (main.Scorer.NONE, main.Scorer.START, main.Scorer.LUCKY):
            self.assertEqual(main.roll_scorer_amount(scorer), 0)
        # An on/off effect has nothing to roll.
        self.assertEqual(main.roll_effect_magnitude(main.Effect.FRAGILE), 0)
        self.assertEqual(main.roll_effect_amounts([main.Effect.FRAGILE]), {})


    def test_rolls_follow_the_inverse_square_distribution(self):
        # The deviation is continuous with density proportional to
        # 1/(x^2 + MAGNITUDE_SPREAD) over +/- MAGNITUDE_MAX_STEPS steps: a roll
        # lands right on the average about 0.18 of the time, one step off about
        # 0.15, two steps off about 0.10. The shape is a Cauchy distribution
        # truncated to the cap, so the chance of landing in the step-wide
        # bucket around x is the SCALED arc tangent swept across it, over the
        # whole range — this asserts the spread really is the one in the
        # density, which is the dial on how wild rolls get. Sampled generously
        # so the tolerance never flakes.
        self.assertEqual(components.MAGNITUDE_SPREAD, 4)
        self.assertAlmostEqual(main.MAGNITUDE_SCALE, math.sqrt(components.MAGNITUDE_SPREAD))
        samples = 30000
        average, step = 30, 3
        counts = {}
        for _ in range(samples):
            x = (main.roll_magnitude(average) - average) / step
            # Half-up bucketing: a deviation that lands exactly on a boundary
            # counts as the upper bucket, as the density integral does.
            bucket = math.floor(x + 0.5)
            counts[bucket] = counts.get(bucket, 0) + 1
        total = sum(counts.values())
        span = 2 * main.MAGNITUDE_ATAN_LIMIT
        scale = main.MAGNITUDE_SCALE

        def density_mass(x):
            return (math.atan((x + 0.5) / scale)
                    - math.atan((x - 0.5) / scale)) / span

        for x in (0, 1, -1, 2, -2, 3, 4):
            self.assertAlmostEqual(counts.get(x, 0) / total, density_mass(x),
                                   delta=0.015)
        # The shape of the curve: nearer the average is always likelier.
        self.assertGreater(counts[0], counts[1])
        self.assertGreater(counts[1], counts[2])
        self.assertAlmostEqual(counts[1] / counts[2],
                               (2 ** 2 + components.MAGNITUDE_SPREAD)
                               / (1 ** 2 + components.MAGNITUDE_SPREAD), delta=0.2)
        # Every deviation stays inside the cap...
        self.assertTrue(all(abs(x) <= main.MAGNITUDE_MAX_STEPS for x in counts))
        # ...and the rolls are continuous, not a 17-point grid of whole steps.
        deviations = [round((main.roll_magnitude(average) - average) / step, 3)
                      for _ in range(2000)]
        self.assertTrue(any(d != round(d) for d in deviations))
        self.assertGreater(len(set(deviations)), 200)
        self.assertTrue(all(abs(d) <= main.MAGNITUDE_MAX_STEPS for d in deviations))


    def test_an_old_save_without_magnitudes_reads_the_averages(self):
        # A save made before magnitudes existed has no effect_amounts key: its
        # blocks come back at the averages (exactly what they used to be).
        data = {"kind": "block", "placed": True, "x": 1, "y": 1,
                "shape": main.Shape.RECT, "effects": [main.Effect.PISTON],
                "scorer": main.Scorer.CHIPS_ADD, "scorer_amount": 30}
        block = save_system._deserialize_item(data)
        self.assertEqual(block.effect_amounts, {})
        self.assertEqual(block.effect_magnitude(main.Effect.PISTON), 1500)
        item = save_system._deserialize_item(
            {"kind": "block", "placed": False, "col": 0, "row": 0,
             "shape": main.Shape.RECT, "effects": [main.Effect.BOUNCY],
             "scorer": main.Scorer.CHIPS_ADD, "scorer_amount": 30, "price": 10})
        self.assertEqual(item.effect_magnitude(main.Effect.BOUNCY), 100)
