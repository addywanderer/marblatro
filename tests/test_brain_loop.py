"""Brain Loop: a 1/3 chance of an action when a marble hits a sticky block.

The card data lives in components.py with the other whole cards, and the rule
itself is Game._brain_loop_roll, called from the fresh-contact path in
_handle_block_contacts. These tests cover the data, the roll (and which RNG it
comes from), the sticky requirement, the Card cutter, and the full action area.
"""

from tests.game_test_case import *  # noqa: F401,F403


class BrainLoopTests(GameTestCase):
    """The Brain Loop whole card: actions from sticky collisions."""

    def _sticky(self, effect=main.Effect.STICKY):
        """Put a block with the given effect on the board and return it."""
        block = main.Block(3, 3, shape=main.Shape.RECT, effect=effect,
                           scorer=main.Scorer.NONE)
        self.game.grid[(3, 3)] = block
        return block

    def _own(self):
        self.game.cards = [main.CardItem(main.Card.BRAIN_LOOP, 40)]

    def _touch(self, block, roll):
        """Fire a fresh collision with ``block``, with the run RNG forced."""
        with mock.patch.object(self.game.run_rng, "random", return_value=roll):
            self._card_fire(block)

    def test_the_card_data(self):
        self.assertEqual(main.Card.name(main.Card.BRAIN_LOOP), "Brain Loop")
        self.assertEqual(main.Card.PRICES[main.Card.BRAIN_LOOP], 40)
        self.assertEqual(main.Card.rarity_name(main.Card.BRAIN_LOOP), "Rare")
        self.assertTrue(main.Card.comment(main.Card.BRAIN_LOOP))
        description = main.Card.description(main.Card.BRAIN_LOOP)
        self.assertIn("1/3", description)
        self.assertIn("sticky", description)
        self.assertIn(main.Card.BRAIN_LOOP, main.Card.ORDER)
        self.assertIn(main.Card.BRAIN_LOOP, main.Card.COLORS)
        self.assertIn(main.Card.BRAIN_LOOP, main.Card.GLYPHS)
        # A whole card: no group half and no scorer half to split it into.
        self.assertIsNone(components.match_group_card_meta(main.Card.BRAIN_LOOP))
        self.assertIsNone(components.card_scorer(main.Card.BRAIN_LOOP))

    def test_a_lucky_sticky_touch_hands_over_an_action(self):
        self.assertEqual(main.BRAIN_LOOP_ACTION_CHANCE, 1 / 3)
        self._own()
        self.game.actions = []
        self.game.shop_message = ""

        self._touch(self._sticky(), roll=0.1)

        self.assertEqual(len(self.game.actions), 1)
        self.assertIn("Converted an action", self.game.shop_message)

    def test_a_roll_at_the_chance_or_above_hands_nothing_over(self):
        self._own()
        for roll in (main.BRAIN_LOOP_ACTION_CHANCE, 0.5, 0.9):
            with self.subTest(roll=roll):
                self.game.actions = []
                self.game.shop_message = ""
                self._touch(self._sticky(), roll=roll)
                self.assertEqual(len(self.game.actions), 0)
                self.assertEqual(self.game.shop_message, "")

    def test_only_a_sticky_block_rolls_at_all(self):
        # A plain block never rolls: the run's RNG is not even asked, so the
        # card cannot quietly eat a roll a later card needed.
        self._own()
        self.game.actions = []
        block = self._sticky(effect=main.Effect.BOUNCY)
        with mock.patch.object(self.game.run_rng, "random") as roll:
            self._card_fire(block)
            roll.assert_not_called()
        self.assertEqual(len(self.game.actions), 0)

    def test_without_the_card_nothing_is_rolled(self):
        self.game.cards = []
        self.game.actions = []
        block = self._sticky()
        with mock.patch.object(self.game.run_rng, "random") as roll:
            self._card_fire(block)
            roll.assert_not_called()
        self.assertEqual(len(self.game.actions), 0)

    def test_a_card_cutter_brain_loop_does_nothing(self):
        card = main.CardItem(main.Card.BRAIN_LOOP, 40)
        self.game.cards = [card]
        self.game.disabled_card = card
        self.game.actions = []
        self._touch(self._sticky(), roll=0.1)
        self.assertEqual(len(self.game.actions), 0)

    def test_a_full_action_area_withholds_the_action(self):
        self._own()
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)
                             for _ in range(main.MAX_ACTIONS)]
        self.game.shop_message = ""

        self._touch(self._sticky(), roll=0.1)

        self.assertEqual(len(self.game.actions), main.MAX_ACTIONS)
        self.assertIn("Action area is full", self.game.shop_message)

    def test_the_roll_comes_from_the_runs_own_rng(self):
        # Forcing the GLOBAL random to a value that would always pass must not
        # decide anything: the roll belongs to the run (Game.run_rng), so a
        # replayed run makes the same rolls it made before.
        self._own()
        self.game.actions = []
        with mock.patch("main.random.random", return_value=0.0), \
                mock.patch.object(self.game.run_rng, "random", return_value=0.9):
            self._card_fire(self._sticky())
        self.assertEqual(len(self.game.actions), 0)
        # And the other way round: the run RNG alone can hand one over.
        with mock.patch("main.random.random", return_value=0.99), \
                mock.patch.object(self.game.run_rng, "random", return_value=0.1):
            self._card_fire(self._sticky())
        self.assertEqual(len(self.game.actions), 1)

    def test_it_rolls_once_per_fresh_touch_not_per_frame(self):
        # A marble held against a sticky block is in contact for many frames;
        # only the FRESH touch rolls, so the card cannot farm actions from one
        # block by leaning on it.
        self._own()
        self.game.actions = []
        block = self._sticky()
        with mock.patch.object(self.game.run_rng, "random", return_value=0.1):
            marble = self._card_fire(block)
            for _ in range(5):
                # The block was touched last tick too: held, not fresh.
                marble.collisions_last_tick = [block]
                marble.collisions_this_tick = [block]
                self.game._handle_block_contacts([block])
        self.assertEqual(len(self.game.actions), 1)
