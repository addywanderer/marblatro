"""Spirit tokens kept from sacrificed blocks.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class TokensTests(GameTestCase):
    """Spirit tokens kept from sacrificed blocks."""


    def test_v2_spirit_token_is_permanent(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CASH, 15, 20, "b", effects=[])
        self.game.toolbox.add(block)

        self.assertTrue(self.game._action_spirit(
            main.ActionItem(main.Action.SPIRIT, 36, version=2), block))

        self.assertIsNone(self.game.tokens[0].runs_left)
        self.assertNotIn(block, self.game.toolbox.items)


    def test_tokens_sit_right_of_the_inventory_and_only_fill_their_own_cells(self):
        self.game.tokens = [_token(main.Scorer.CASH, 15, runs_left=2)]
        rect = self.game._token_rect(0)

        self.assertGreater(rect.left,
                           main.TOOLBOX_COORDS[0] + main.TOOLBOX_COORDS[2])
        self.assertEqual(rect.size, (main.GRID_SIZE, main.GRID_SIZE))
        self.assertIs(self.game.token_at(rect.center), self.game.tokens[0])
        self.assertIsNone(self.game.token_at((rect.centerx, rect.centery + 41)))
        # The chip and the info sidebar render without raising.
        self.game.draw()
        self.assertEqual(self.game._info_target_at(rect.center),
                         (self.game.tokens[0], "tokens"))
        self.assertTrue(self.game._describe_item(self.game.tokens[0]))
        self.assertTrue(self.game._action_hint(self.game.tokens[0], "tokens"))


    def test_tokens_spend_a_run_and_expire(self):
        self.game.tokens = [_token(main.Scorer.MULT_ADD, 4, runs_left=2)]
        self.game.tokens[0].fired = True

        self.game._advance_tokens()

        self.assertEqual([t.runs_left for t in self.game.tokens], [1])
        self.assertFalse(self.game.tokens[0].fired)
        self.game.tokens[0].fired = True
        self.game._advance_tokens()
        self.assertEqual(self.game.tokens, [])


    def test_a_token_created_mid_run_is_not_spent_by_that_run(self):
        seed = main.Block(3, 4, scorer=main.Scorer.MULT_ADD, scorer_amount=4,
                          effects=[])
        self.game.grid[(3, 4)] = seed
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), seed)
        self.assertFalse(self.game.tokens[0].fired)

        self.game._advance_tokens()  # the run that just ended never fired it

        self.assertEqual([t.runs_left for t in self.game.tokens], [2])


    def test_a_token_keeps_its_random_reward_for_every_run(self):
        # A Random/Lucky token's reward is decided when the block is sacrificed
        # and then kept (see main.KEPT_ROLL_RUN): the run it was won in can be
        # retried, and every later run the token covers, without the reward
        # ever being redrawn.
        seed = main.Block(3, 4, scorer=main.Scorer.RANDOM, effects=[])
        self.game.grid[(3, 4)] = seed
        with mock.patch("main.random.random", return_value=0.0):
            self.assertTrue(self.game._action_spirit(
                main.ActionItem(main.Action.SPIRIT, 36), seed))
        token = self.game.tokens[0]
        self.assertEqual(token.block.random_rolls["reward"], 0)      # +35 chips
        self.assertEqual(token.block.random_rolls["run"], main.KEPT_ROLL_RUN)

        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.upgrades_enabled = False
        # A hostile draw would pay +0.3 xMult instead (see _roll_random_output),
        # so the +35 chips prove the sacrificed reward is the one being reused.
        # The run's own starting chips are the game's to set, so they are read
        # from a run with no tokens first (see GameTestCase._start_run_base).
        base_chips, base_mult = self._start_run_base()
        with mock.patch("main.random.random", return_value=0.9):
            self.assertTrue(self.game.reset_run())
            self.assertEqual(self.game.score_chips, base_chips + 35)
            self.assertEqual(self.game.score_mult, base_mult)
            self.game.run_number += 1        # the NEXT run
            self.assertTrue(self.game.reset_run())
            self.assertEqual(self.game.score_chips, base_chips + 35)
            self.assertEqual(self.game.score_mult, base_mult)


    def test_a_token_keeps_the_whole_block(self):
        # Spirit stores the BLOCK, not just its scorer: shape, effects, the
        # rolled magnitudes and the cell it stood in all come with it.
        block = main.Block(3, 4, shape=main.Shape.PIPE, scorer=main.Scorer.EFFECTIVE,
                           scorer_amount=2.0, effects=[main.Effect.BOUNCY,
                                                       main.Effect.SLIPPERY],
                           effect_amounts={main.Effect.BOUNCY: 1200.0})
        self.game.grid[(3, 4)] = block

        self.assertTrue(self.game._action_spirit(
            main.ActionItem(main.Action.SPIRIT, 36), block))

        token = self.game.tokens[0]
        self.assertIsNot(token.block, block)          # a copy, not the board's
        self.assertEqual(token.block.shape, main.Shape.PIPE)
        self.assertEqual(token.block.effects, [main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self.assertEqual(token.block.scorer, main.Scorer.EFFECTIVE)
        self.assertEqual(token.block.scorer_amount, 2.0)
        self.assertEqual((token.block.x, token.block.y), (3, 4))
        self.assertEqual(token.block.effect_magnitude(main.Effect.BOUNCY), 1200.0)
        self.assertTrue(token.block.is_token)


    def test_a_token_fires_its_blocks_matching_cards_too(self):
        # A token fires as if the marble had collided with its block, so the
        # player's cards that match that block fire with it — a Pipe token sets
        # off a Pipe card, exactly as a Pipe on the board would.
        pipe = main.match_group_for_shape(main.Shape.PIPE)
        self.game.cards = [_card_item(pipe, main.Scorer.MULT_ADD)]
        seed = main.Block(3, 4, shape=main.Shape.PIPE, scorer=main.Scorer.MULT_ADD,
                          scorer_amount=4, effects=[])
        self.game.grid[(3, 4)] = seed
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), seed)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.upgrades_enabled = False
        base_chips, base_mult = self._start_run_base()

        self.assertTrue(self.game.reset_run())

        # +4 from the token's own block and +4 from the card that fired with it,
        # on top of the run's own starting mult.
        self.assertEqual(self.game.score_mult, base_mult + 4 + 4)
        self.assertEqual(self.game.score_chips, base_chips)


    def test_an_xmult_token_fires_when_the_run_ends(self):
        # A token whose payoff is a MULTIPLIER waits for the run's end, exactly
        # like the xMult a block on the board banks (see Game._apply_xmult): it
        # is armed at the run's start and pays as the run settles.
        sharp = main.Block(3, 4, scorer=main.Scorer.SHARP, scorer_amount=3,
                           effects=[])
        self.game.grid[(3, 4)] = sharp
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), sharp)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.upgrades_enabled = False
        base_chips, base_mult = self._start_run_base()

        self.assertTrue(self.game.reset_run())

        token = self.game.tokens[0]
        self.assertTrue(token.fires_at_end)
        self.assertTrue(token.armed)
        self.assertFalse(token.fired)                    # nothing paid yet
        self.assertEqual(self.game.score_mult, base_mult)
        self.assertEqual(self.game.run_xmult_pending, 1.0)

        self.game._apply_end_tokens()

        self.assertTrue(token.fired)
        self.assertFalse(token.armed)
        self.assertEqual(self.game.score_mult, base_mult)   # still banked
        self.assertAlmostEqual(self.game.run_xmult_pending, 3)
        self.game._flush_run_xmult()
        self.assertAlmostEqual(self.game.score_mult, base_mult * 3)


    def test_a_mid_run_xmult_token_waits_for_the_next_run(self):
        # A token created mid-run is never armed, so the run it was born in
        # cannot spend it at its end either.
        sharp = main.Block(3, 4, scorer=main.Scorer.SHARP, scorer_amount=3,
                           effects=[])
        self.game.grid[(3, 4)] = sharp
        self.game._action_spirit(main.ActionItem(main.Action.SPIRIT, 36), sharp)
        self.game.run_active = True

        self.game._apply_end_tokens()

        token = self.game.tokens[0]
        self.assertFalse(token.fired)
        self.assertEqual(self.game.run_xmult_pending, 1.0)
        self.game._advance_tokens()                      # the run never fired it
        self.assertEqual([t.runs_left for t in self.game.tokens], [2])


    def test_the_token_is_drawn_as_the_block_it_kept(self):
        # The token column shows the kept block, not a chip: the slot is filled
        # with the block's scorer colour the way a RECT block is on the board,
        # and the drawing copy sits in the slot without moving the stored block.
        token = _token(main.Scorer.CASH, 15, x=3, y=4, runs_left=2)
        self.game.tokens = [token]
        rect = self.game._token_rect(0)

        visual = main.ui._token_visual(token, rect)

        self.assertEqual(visual.rect, rect)
        self.assertEqual(visual.scorer, main.Scorer.CASH)
        self.assertEqual((token.block.x, token.block.y), (3, 4))  # untouched

        self.game.screen.fill(main.BLACK)
        main.ui.draw_token(self.game.screen, token, rect)
        centre = self.game.screen.get_at(rect.center)[:3]
        self.assertEqual(centre, main.Scorer.color(main.Scorer.CASH))


    def test_the_token_info_box_describes_the_kept_block(self):
        token = _token(main.Scorer.CASH, 15, runs_left=2)
        rows = dict(self.game._describe_item(token))
        labels = [label for label, _ in self.game._describe_item(token)]

        self.assertIn("Token - Rect Cash", labels)
        self.assertIn("Scorer - Cash", labels)
        self.assertIn("Shape - Rect", labels)
        self.assertIn("2 more run(s)", rows["Token - Rect Cash"])
        self.assertIn("start of each run", rows["Token - Rect Cash"])
        # A multiplier token's box says when it pays instead.
        sharp = dict(self.game._describe_item(_token(main.Scorer.SHARP, 3)))
        self.assertIn("end of each run", sharp["Token - Rect Sharp"])
        self.assertIn("end of each run it covers (xMult)",
                      self.game._action_hint(_token(main.Scorer.SHARP, 3),
                                             "tokens"))
