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
        self.game.tokens = [main.ScorerToken(main.Scorer.CASH, 15, runs_left=2)]
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
        self.game.tokens = [main.ScorerToken(main.Scorer.MULT_ADD, 4, runs_left=2)]
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
