"""Trials and final bosses: the run-wide modifiers.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class TrialsTests(GameTestCase):
    """Trials and final bosses: the run-wide modifiers."""


    def test_defeat_awards_dice_squared_of_run_minus_three(self):
        # A game over in defeat awards dice = (run number - 3)^2. A defeat on
        # run 4 (the 3rd loss) gives (4 - 3)^2 = 1 die.
        self.assertEqual(metagame.dice(), 0)
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertEqual(metagame.dice(), (4 - 3) ** 2)
        self.assertEqual(self.game.game_over_dice_gained, 1)


    def test_victory_does_not_award_dice(self):
        # Winning all 24 runs ends in a perfect win; no dice are awarded.
        self.assertEqual(metagame.dice(), 0)
        for _ in range(main.TOTAL_RUNS):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)
        self.assertEqual(metagame.dice(), 0)
        self.assertEqual(self.game.game_over_dice_gained, 0)


    def test_trial_data_is_defined(self):
        self.assertEqual(main.Trial.name(main.Trial.HANDS_TIED), "Hands tied")
        self.assertEqual(main.Trial.name(main.Trial.CARD_CUTTER), "Card cutter")
        self.assertEqual(main.Trial.name(main.Trial.DEAD_ZONE), "Dead zone")
        self.assertEqual(main.Trial.name(main.Trial.ALL_FINISHES), "All finishes")
        self.assertEqual(main.Trial.name(main.Trial.SLIM_PICKINGS), "Slim pickings")
        self.assertEqual(main.Trial.name(main.Trial.LONG_RUN), "Long run")
        self.assertEqual(main.Trial.name(main.Trial.SHUFFLED), "Shuffled")
        self.assertEqual(main.Trial.name(main.Trial.BOUNCY_CASTLE), "Bouncy castle")
        self.assertEqual(main.Trial.name(main.Trial.CRUMBLING), "Crumbling")
        self.assertEqual(main.Trial.name(main.Trial.MARBLE_WEIGHT), "Marble weight")
        self.assertEqual(main.Trial.name(main.Trial.SPEEDRUN), "Speedrun")
        self.assertEqual(main.Trial.name(main.Trial.REPEATS_ONLY), "Repeats only")
        self.assertEqual(main.Trial.name(main.Trial.INFLATION), "Inflation")
        self.assertEqual(main.Trial.name(main.Trial.EMPTY_POCKETS), "Empty pockets")
        self.assertEqual(main.Trial.name(main.Trial.DEAL_BREAKER), "Deal breaker")
        for trial in main.Trial.ORDER:
            self.assertTrue(main.Trial.description(trial))
        self.assertEqual(len(main.Trial.ORDER), 15)
        self.assertIn(main.Trial.DEAD_ZONE, main.Trial.ORDER)
        self.assertIn(main.Trial.ALL_FINISHES, main.Trial.ORDER)
        self.assertIn(main.Trial.SLIM_PICKINGS, main.Trial.ORDER)
        self.assertIn(main.Trial.LONG_RUN, main.Trial.ORDER)
        self.assertIn(main.Trial.SHUFFLED, main.Trial.ORDER)
        self.assertIn(main.Trial.BOUNCY_CASTLE, main.Trial.ORDER)
        self.assertIn(main.Trial.CRUMBLING, main.Trial.ORDER)
        self.assertIn(main.Trial.MARBLE_WEIGHT, main.Trial.ORDER)
        self.assertIn(main.Trial.SPEEDRUN, main.Trial.ORDER)
        self.assertIn(main.Trial.REPEATS_ONLY, main.Trial.ORDER)
        self.assertIn(main.Trial.INFLATION, main.Trial.ORDER)
        self.assertIn(main.Trial.EMPTY_POCKETS, main.Trial.ORDER)
        self.assertIn(main.Trial.DEAL_BREAKER, main.Trial.ORDER)


    def test_hands_tied_trial_maxes_quarter_of_blocks(self):
        # Exactly 1/4 of the marble-box blocks get their trigger limit maxed.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game._apply_trial()
        self.assertEqual(len(self.game.trial_maxed_blocks), 2)  # 8 // 4

        self.game.reset_run(False)
        for block in self.game.grid.values():
            if block in self.game.trial_maxed_blocks:
                self.assertEqual(block.triggers_left, main.TRIAL_MAX_TRIGGERS)
            else:
                self.assertEqual(block.triggers_left, block.trigger_limit)


    def test_trial_is_chosen_before_run_starts(self):
        # A fresh game picks the trial up front (so the info box can show it
        # during setup); starting the run applies it without re-rolling it.
        self.game.trials_enabled = True
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        trial_before = self.game.current_trial
        self.game.reset_run()  # choose_trial defaults to True
        self.assertEqual(self.game.current_trial, trial_before)


    def test_a_round_gives_trials_to_its_last_runs(self):
        # The difficulty decides how many of a round's runs play a trial, and
        # they are the round's LAST runs: difficulties 1-2 give only the final
        # run of a round a trial, difficulty 3 gives the last two, and
        # difficulty 4 gives every run of the round one.
        expected = {main.Difficulty.LEVEL_1: 1, main.Difficulty.LEVEL_2: 1,
                    main.Difficulty.LEVEL_3: 2, main.Difficulty.LEVEL_4: 3}
        for level, with_trial in expected.items():
            with self.subTest(difficulty=level):
                game = main.Game()
                game.trials_enabled = True
                game.difficulty = level
                trials = []
                for run in range(main.RUNS_PER_ROUND):
                    game._choose_trial(run)  # the run being set up
                    trials.append(game.current_trial)
                self.assertEqual(sum(t is not None for t in trials), with_trial,
                                 trials)
                for run, trial in enumerate(trials):
                    if run >= main.RUNS_PER_ROUND - with_trial:
                        self.assertIn(trial, main.Trial.ORDER)
                    else:
                        self.assertIsNone(trial, f"run {run + 1} is trial-free")


    def test_bouncy_castle_trial_marks_marble_bouncy_castle(self):
        # Starting a run under the bouncy-castle trial gives each marble the
        # bouncy_castle flag (physics reflects it off every solid block).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.BOUNCY_CASTLE
        self.game.reset_run(False)
        self.assertTrue(all(m.bouncy_castle for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.reset_run(False)
        self.assertFalse(any(m.bouncy_castle for m in self.game.marbles))


    def test_crumbling_trial_marks_quarter_of_blocks(self):
        # Crumbling marks ~1/4 of the placed solid (non-role) blocks fragile.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.FINISH)
        self.game.current_trial = main.Trial.CRUMBLING
        with mock.patch("main.random.sample",
                        side_effect=lambda seq, k: seq[:k]):
            self.game._apply_trial()
        # 8 scoring blocks -> 8 // 4 = 2 marked; START/FINISH never marked.
        self.assertEqual(len(self.game.trial_fragile_blocks), 2)
        for block in self.game.trial_fragile_blocks:
            self.assertTrue(block.trial_fragile)
            self.assertNotIn(block.scorer, (main.Scorer.START, main.Scorer.FINISH))
        self.assertFalse(self.game.grid[(0, 1)].trial_fragile)
        self.assertFalse(self.game.grid[(1, 1)].trial_fragile)


    def test_speedrun_trial_halves_ideal_time(self):
        # With Speedrun the time factor peaks at half the ideal time, so a run
        # that takes TIME_IDEAL/2 scores the full time contribution while one
        # taking the normal ideal time scores much less.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SPEEDRUN
        self.game.run_time = main.TIME_IDEAL / 2
        peak, _, _, _ = self.game._score_factors()
        self.game.run_time = main.TIME_IDEAL * 2  # well off the halved ideal
        off_peak, _, _, _ = self.game._score_factors()
        self.assertGreater(peak, 0.9)
        self.assertGreater(peak, off_peak)
        self.assertLess(off_peak, 0.5)


    def test_trial_change_never_offers_the_trial_already_running(self):
        # The reroll passes only OTHER trials to random.choice, so the bought
        # trial is always a different one.
        self.game.trials_enabled = True
        self.game.cash = 100000
        seen = {}

        def pick(sequence):
            seen["candidates"] = list(sequence)
            return sequence[0]

        self.game.current_trial = main.Trial.DEAD_ZONE
        with mock.patch("main.random.choice", side_effect=pick):
            self.game._click_trial_display(
                (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertNotIn(main.Trial.DEAD_ZONE, seen["candidates"])
        self.assertEqual(len(seen["candidates"]), len(main.Trial.ORDER) - 1)
        self.assertNotEqual(self.game.current_trial, main.Trial.DEAD_ZONE)


    def test_trial_display_needs_cash_and_the_build_phase(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        # Too little cash: nothing changes and both fees are named.
        self.game.cash = 10
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.shop_message,
                         f"Need ${main.TRIAL_CHANGE_COST} to change the trial")
        self.assertFalse(self.game._click_trial_display(right))
        self.assertEqual(self.game.shop_message,
                         f"Need ${main.TRIAL_DISABLE_COST} to disable the trial")
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 10)
        # A run in progress fixes its trial: the display is display-only.
        self.game.cash = 1000
        self.game.run_active = True
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 1000)
        self.assertIn("while building", self.game.shop_message)
        # The post-run RETRY/CONTINUE state and the final boss run are out too.
        self.game.run_active = False
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.assertFalse(self.game._click_trial_display(right))
        self.assertEqual(self.game.cash, 1000)
        self.game.awaiting_after_run = False
        self.game.run_complete = False
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 1000)


    def test_all_finishes_trial_marks_marbles_finish_on_border(self):
        # Starting a run under the all-finishes trial gives each marble the
        # finish_on_border flag (physics does the actual border finish).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.reset_run(False)
        self.assertTrue(all(m.finish_on_border for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.reset_run(False)
        self.assertTrue(all(m.dead_zone for m in self.game.marbles))
        self.assertFalse(any(m.finish_on_border for m in self.game.marbles))


    def test_failing_boss_run_ends_in_defeat(self):
        # The 24th run is a boss run: it must be CLEARED to win. With only one
        # prior loss, failing it ends the game in defeat (not a win) and
        # awards defeat dice like any other loss.
        for run in range(main.TOTAL_RUNS - 1):
            if run == 5:
                self._complete_run(100, required=1000)  # 1 prior loss
            else:
                self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertFalse(self.game.game_over)

        self._complete_run(100, required=1000)  # fail the 24th (boss) run
        self.game._continue_run()

        self.assertTrue(self.game.game_over)
        self.assertFalse(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.game_over_dice_gained, (main.TOTAL_RUNS - 3) ** 2)
        self.assertEqual(metagame.dice(), (main.TOTAL_RUNS - 3) ** 2)


    def test_final_boss_data_is_defined(self):
        self.assertEqual(main.FinalBoss.name(main.FinalBoss.SINGULARITY), "Singularity")
        self.assertEqual(main.FinalBoss.name(main.FinalBoss.SKY_HIGH), "Sky High")
        for boss in main.FinalBoss.ORDER:
            self.assertTrue(main.FinalBoss.description(boss))
        self.assertEqual(len(main.FinalBoss.ORDER), 2)
        self.assertIn(main.FinalBoss.SINGULARITY, main.FinalBoss.ORDER)
        self.assertIn(main.FinalBoss.SKY_HIGH, main.FinalBoss.ORDER)


    def test_final_boss_is_chosen_on_the_24th_run(self):
        # Reaching the last run picks a final boss (randomly) for run 24.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)
        self.assertIn(self.game.final_boss, main.FinalBoss.ORDER)


    def test_boss_run_has_no_trial(self):
        # The 24th run has a final boss instead of a trial.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)
        self.assertIsNone(self.game.current_trial)


    def test_sky_high_triples_required_score_on_boss_run(self):
        # Forcing the Sky High boss triples the 24th run's required score.
        def fake_choice(seq):
            return main.FinalBoss.SKY_HIGH if seq == main.FinalBoss.ORDER else seq[0]
        with mock.patch("main.random.choice", side_effect=fake_choice):
            for _ in range(main.TOTAL_RUNS - 1):
                self._complete_run(1000000, required=1)
                self.game._continue_run()
        self.assertEqual(self.game.final_boss, main.FinalBoss.SKY_HIGH)
        base = main.get_next_required_score(main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.required_score, base * 3)


    def test_endless_play_drops_the_boss_and_hands_the_run_back_to_a_trial(self):
        # Past the boss run the game keeps going, and the boss must not linger:
        # it would keep applying and lock the trial display forever.
        def fake_choice(seq):
            return main.FinalBoss.SINGULARITY if seq == main.FinalBoss.ORDER \
                else seq[0]
        with mock.patch("main.random.choice", side_effect=fake_choice):
            for _ in range(main.TOTAL_RUNS - 1):
                self._complete_run(1000000, required=1)
                self.game._continue_run()
        self.assertEqual(self.game.final_boss, main.FinalBoss.SINGULARITY)
        self.game.trials_enabled = True
        self.game.continue_past_game_over = True  # the player keeps playing

        self._complete_run(1000000, required=1)
        self.game._continue_run()  # advance into the first endless run

        self.assertEqual(self.game.run_number, main.TOTAL_RUNS)
        self.assertIsNone(self.game.final_boss)
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.assertTrue(self.game.trial_options_available())


    def test_endless_play_trial_display_can_be_changed_and_disabled(self):
        # The two halves of the trial display work again once the boss run is
        # behind the player.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.game.trials_enabled = True
        self.game.continue_past_game_over = True
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.assertTrue(self.game.trial_options_available())

        self.game.cash = 1000
        was = self.game.current_trial
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(left))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertNotEqual(self.game.current_trial, was)

        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(right))
        self.assertEqual(self.game.cash,
                         1000 - main.TRIAL_CHANGE_COST - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)
        # And a trial can be bought back onto the endless run.
        self.assertTrue(self.game._click_trial_display(left))
        self.assertIn(self.game.current_trial, main.Trial.ORDER)


    def test_endless_singularity_stops_growing_the_marble(self):
        # A boss cleared before endless play no longer applies.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.game.final_boss = main.FinalBoss.SINGULARITY
        self.game.continue_past_game_over = True
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.assertIsNone(self.game.final_boss)

        marble = self._add_marble()
        self.game.run_active = True
        before = marble.mass
        for _ in range(60):
            self.game.update()
        self.assertEqual(marble.mass, before)


    def test_a_loaded_endless_save_drops_a_stale_boss(self):
        # An old endless save that still carried a boss loads without it, while
        # a save made during the boss run keeps its boss.
        data = {"run_number": main.TOTAL_RUNS,
                "final_boss": int(main.FinalBoss.SINGULARITY)}
        fresh = main.Game()
        save_system._load_save_data(fresh, data, 1)
        self.assertIsNone(fresh.final_boss)

        boss_data = {"run_number": main.TOTAL_RUNS - 1,
                     "final_boss": int(main.FinalBoss.SKY_HIGH)}
        boss_save = main.Game()
        save_system._load_save_data(boss_save, boss_data, 1)
        self.assertEqual(boss_save.final_boss, main.FinalBoss.SKY_HIGH)


    def test_beating_final_boss_discovers_it_in_collection(self):
        # Clearing the 24th run reveals its final boss in the collection.
        self.game.final_boss = main.FinalBoss.SINGULARITY
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.game.marbles[0].finished = True
        self.game.required_score = 1
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(collection.is_final_boss_discovered(main.FinalBoss.SINGULARITY))
        self.assertTrue(any(p.title == "Final boss beaten" for p in self.game.popups))


    def test_final_bosses_appear_in_collection_entries(self):
        # Both bosses show up in the collection, hidden until beaten.
        entries = self.game._collection_entries()
        bosses = [e for e in entries if e[0] == "final_boss"]
        self.assertEqual(len(bosses), len(main.FinalBoss.ORDER))
        for kind, value, name, desc, has_icon, discovered in bosses:
            self.assertIn(value, main.FinalBoss.ORDER)
            self.assertEqual(name, "???")
            self.assertEqual(desc, "???")
            self.assertFalse(has_icon)
            self.assertFalse(discovered)


    def test_boss_run_dot_is_black_until_played(self):
        # The 24th run's dot is black instead of gray until it is played.
        self.game.run_results = []
        main.ui.draw_run_dots(self.game)
        cx, cy = self._run_dot_pixel(main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], main.BLACK)
        nx, ny = self._run_dot_pixel(0)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.GRAY)


    def test_boss_run_dot_is_gold_when_cleared_and_deep_red_when_lost(self):
        # Clearing the 24th run turns its dot gold; losing turns it deep red.
        self.game.run_results = [True] * main.TOTAL_RUNS
        main.ui.draw_run_dots(self.game)
        cx, cy = self._run_dot_pixel(main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], (255, 215, 0))
        nx, ny = self._run_dot_pixel(0)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.GREEN)

        self.game.run_results = [False] + [True] * (main.TOTAL_RUNS - 2) + [False]
        main.ui.draw_run_dots(self.game)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], (140, 0, 0))  # boss lost: deep red
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.RED)     # normal lost: red
