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


    def test_every_trial_has_its_own_tile_of_shapes_and_colours(self):
        # A trial's tile is its icon AND the pattern the whole screen is tiled
        # with while it runs: a square LATTICE CELL (not one grid unit — it is
        # big enough that the screen tiles exactly) built from tessellating
        # shapes in a few shades of the trial's own colour.
        size = main.ui.TRIAL_TILE_SIZE
        self.assertEqual(main.SCREEN_WIDTH % size, 0)
        self.assertEqual(main.SCREEN_HEIGHT % size, 0)
        self.assertNotEqual(size, main.GRID_SIZE)      # no longer one grid unit
        self.assertEqual(len(main.Trial.COLORS), len(main.Trial.ORDER))
        self.assertEqual(set(main.Trial.TILE_STYLES), set(main.Trial.ORDER))
        fingerprints = {}
        for trial in main.Trial.ORDER:
            with self.subTest(trial=main.Trial.name(trial)):
                tile = main.ui._trial_tile(trial)
                self.assertEqual(tile.get_size(), (size, size))
                colours = {tuple(tile.get_at((x, y)))[:3]
                           for x in range(0, size, 2)
                           for y in range(0, size, 2)}
                # A tessellation of a few shapes in a few colours, never a flat
                # fill and never so busy that it stops reading as a pattern.
                self.assertGreaterEqual(len(colours), 2,
                                        "a tile must be shapes, not one colour")
                self.assertLessEqual(len(colours), 12,
                                     "a tile is a few shapes, not noise")
                palette = set(main.Trial.palette(trial).values())
                self.assertTrue(colours & palette,
                                "a tile is drawn in its own palette")
                fingerprints[trial] = pygame.image.tostring(tile, "RGB")
        # No two trials share a tile, and the art is built once.
        self.assertEqual(len(set(fingerprints.values())), len(main.Trial.ORDER))
        self.assertIs(main.ui._trial_tile(main.Trial.DEAD_ZONE),
                      main.ui._trial_tile(main.Trial.DEAD_ZONE))

    def test_tiles_are_tessellations_that_meet_across_their_seams(self):
        # The whole point of the lattice: two tiles side by side and stacked
        # read as ONE pattern rather than as squares, because every family is
        # periodic inside the tile. A seam is continuous when the tile's own
        # left column and its right column would sit next to each other without
        # a discontinuity, which for a periodic pattern means the columns on
        # either side of the join continue an edge of the same shapes.
        size = main.ui.TRIAL_TILE_SIZE
        for trial in main.Trial.ORDER:
            with self.subTest(trial=main.Trial.name(trial)):
                tile = main.ui._trial_tile(trial)
                # Stitching four copies must not introduce a colour that is not
                # already the pattern's own: no seam line, no background gap.
                stitched = pygame.Surface((size * 2, size * 2))
                for cx in range(2):
                    for cy in range(2):
                        stitched.blit(tile, (cx * size, cy * size))
                inner = {tuple(stitched.get_at((x, y)))[:3]
                         for x in range(1, size * 2 - 1)
                         for y in range(1, size * 2 - 1)}
                self.assertEqual(inner, {tuple(tile.get_at((x, y)))[:3]
                                        for x in range(size)
                                        for y in range(size)})
                # The squares never read as frames: the pixels along a seam
                # belong to shapes that cross it (the row/column just inside one
                # tile's edge is the same family of colours as the row/column
                # just inside the other tile's opposite edge).
                left = {tuple(tile.get_at((1, y)))[:3] for y in range(size)}
                right = {tuple(tile.get_at((size - 2, y)))[:3] for y in range(size)}
                self.assertTrue(left & right,
                                "the lattice does not continue over the seam")

    def test_the_all_finishes_tile_is_the_finish_checkerboard(self):
        # The tile the user described: white with its top-left and bottom-right
        # quadrants black, exactly like a Finish block — now built out of
        # triangles instead of squares.
        size = main.ui.TRIAL_TILE_SIZE
        cell = size // 2
        tile = main.ui._trial_tile(main.Trial.ALL_FINISHES)
        dark = components.shade((245, 245, 245), -0.92)
        # Each quadrant is one square of the checkerboard, split by a diagonal
        # into two shades. Sample inside the cell's OWN triangle, which is the
        # one hugging the cell's RIGHT edge on the even cells and its LEFT edge
        # on the odd ones (see ui._tess_checker).
        cases = (((0, 0), dark), ((1, 0), (245, 245, 245)),
                 ((0, 1), (245, 245, 245)), ((1, 1), dark))
        for index, expected in cases:
            with self.subTest(cell=index):
                even = (index[0] + index[1]) % 2 == 0
                px = index[0] * cell + (cell * 3 // 4 if even else cell // 4)
                py = index[1] * cell + cell // 4
                got = tuple(tile.get_at((px, py)))[:3]
                for channel, want in zip(got, expected):
                    self.assertLessEqual(abs(channel - want), 6,
                                         f"cell {index} is not {expected}: {got}")
        # The whole tile uses those two colours (each with its triangle facet),
        # and each quadrant is split into two triangles.
        colours = {tuple(tile.get_at((x, y)))[:3]
                   for x in range(size) for y in range(size)}
        for expected in (dark, components.shade(dark, -0.22),
                         (245, 245, 245),
                         components.shade((245, 245, 245), -0.22)):
            self.assertIn(expected, colours)
        self.assertEqual(len(colours), 4)

    def test_a_trial_tile_is_only_drawn_in_the_background_and_the_collection(self):
        # The user's rule: the tile may appear as the screen's background
        # while the trial runs and as the collection's icon — nowhere else.
        source = inspect.getsource(main.ui)
        self.assertEqual(source.count("draw_trial_tile("), 3)   # def + 2 uses
        self.assertEqual(source.count("def _build_trial_tile("), 1)
        # ...and the two uses are the screen background and the collection.
        background = inspect.getsource(main.ui._trial_background)
        self.assertIn("draw_trial_tile(background, trial,", background)
        self.assertIn("draw_background(game)",
                      inspect.getsource(main.ui.draw))
        self.assertIn("draw_trial_tile(game.screen, value, rect)",
                      inspect.getsource(main.ui.draw_collection_icon))
        # The trial display itself never carries a tile.
        self.assertNotIn("draw_trial_tile", inspect.getsource(main.ui.draw_trial_box))

    def test_hands_tied_trial_debuffs_a_quarter_of_blocks(self):
        # Exactly 1/4 of the marble-box blocks lose one trigger for the run.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        # One block upgraded to 3 triggers: Hands tied takes one away, it does
        # not silence the block.
        strong = self.game.grid[(0, 0)]
        strong.trigger_limit = 3
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game._apply_trial()
        self.assertEqual(len(self.game.trial_debuffed_blocks), 2)  # 9 // 4
        # The description states the new rule (one fewer trigger, not silence).
        self.assertIn("1 fewer time", main.Trial.description(main.Trial.HANDS_TIED))

        self.game.reset_run(False)
        for block in self.game.grid.values():
            if block in self.game.trial_debuffed_blocks:
                self.assertEqual(block.triggers_left,
                                 max(0, block.trigger_limit
                                     - main.TRIAL_TRIGGER_PENALTY))
            else:
                self.assertEqual(block.triggers_left, block.trigger_limit)
        if strong in self.game.trial_debuffed_blocks:
            self.assertEqual(strong.triggers_left, 2)
        self.assertTrue(all(block.triggers_left >= 0
                            for block in self.game.grid.values()))


    def test_hands_tied_keeps_the_same_blocks_when_the_run_replays(self):
        # Restarting the run (R / T) or retrying it re-applies the SAME choice:
        # the debuffed blocks are decided once per run, so they cannot be
        # rerolled by replaying.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game._apply_trial()
        first = set(self.game.trial_debuffed_blocks)
        self.assertTrue(first)
        for _ in range(3):        # R, T, and a retry both re-apply the trial
            self.game._apply_trial()
            self.assertEqual(set(self.game.trial_debuffed_blocks), first)
            self.game.reset_run(True)
            self.assertEqual(set(self.game.trial_debuffed_blocks), first)
        # ...and the decision itself is what is kept.
        self.assertEqual(self.game.trial_decision.get("cells"),
                         {(block.x, block.y) for block in first})
        # A DIFFERENT trial decides afresh (the memo belongs to the trial).
        self.game.current_trial = main.Trial.CRUMBLING
        self.game._apply_trial()
        self.assertNotEqual(self.game.trial_decision.get("trial"),
                            main.Trial.HANDS_TIED)


    def test_shuffled_trial_keeps_one_order_when_the_run_replays(self):
        # "Flips and shuffles your cards" happens ONCE for the run: re-applying
        # the trial (R, T, a retry) must not shuffle the cards a second time, or
        # the player could keep re-rolling the order (and the Blueprint that
        # depends on it) for free.
        self.game.cards = [main.CardItem(value, 40) for value in
                           (main.Card.JOKER, main.Card.MINESHAFT,
                            main.Card.COUPON, main.Card.MARKET)]
        self.game.current_trial = main.Trial.SHUFFLED
        self.game._apply_trial()
        order = [card.value for card in self.game.cards]
        self.assertCountEqual(order, (main.Card.JOKER, main.Card.MINESHAFT,
                                      main.Card.COUPON, main.Card.MARKET))
        for _ in range(3):
            self.game._apply_trial()
            self.assertEqual([card.value for card in self.game.cards], order)
        self.assertEqual([card.value for card in self.game.trial_decision["order"]],
                         order)
        # A card bought after the decision follows the decided ones.
        bought = main.CardItem(main.Card.SHOWMAN, 40)
        self.game.cards.append(bought)
        self.game._apply_trial()
        self.assertEqual([card.value for card in self.game.cards],
                         order + [main.Card.SHOWMAN])


    def test_the_runs_dice_replay_identically(self):
        # The run's own RNG (the 8 ball's retrigger chance, a Random condition's
        # measure) is re-seeded every time the run (re)starts, so replaying a
        # run replays its luck instead of rolling until it lands well.
        # (A run needs a Start block to be built at all — reset_run refuses
        # without one, and a refused reset is not a replay.)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        first = [self.game.run_rng.random() for _ in range(5)]
        self.assertTrue(self.game.reset_run(False))   # R / T / a retry
        self.assertEqual([self.game.run_rng.random() for _ in range(5)], first)
        # A NEW run (a new seed, drawn when its trial is chosen) rolls its own.
        self.game._choose_trial(self.game.run_number + 1)
        self.game.reset_run(False)
        self.assertNotEqual([self.game.run_rng.random() for _ in range(5)], first)


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
        # finish_on_border flag (physics does the actual border finish). The
        # trial must be ENABLED for its physics to apply at all.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.reset_run(False)
        self.assertTrue(all(m.finish_on_border for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.reset_run(False)
        self.assertTrue(all(m.dead_zone for m in self.game.marbles))
        self.assertFalse(any(m.finish_on_border for m in self.game.marbles))
        # With the trial system switched off, no trial flag applies, even
        # though the game still holds a trial id.
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.trials_enabled = False
        self.game.reset_run(False)
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
