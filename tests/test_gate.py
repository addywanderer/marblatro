"""Gate: +30 chips each time a marble carries its key through the open lock.

The card data lives in components.py with the other whole cards, and the rule
itself is Game._gate_key_and_lock, called from the fresh-contact path in
_handle_block_contacts beside the Key/Lock mechanic it reads. These tests cover
the data, the key-then-lock sequence, whose key counts (the SAME marble's), that
a still-locked Lock pays nothing, that every pass pays, the Card cutter and the
card not being owned at all.
"""

from tests.game_test_case import *  # noqa: F401,F403


class GateTests(GameTestCase):
    """The Gate whole card: chips for a key-carrying marble's passage."""

    def _own(self, value=None):
        self.game.cards = [main.CardItem(value or main.Card.GATE, 24)]

    def _pair(self, number=7, key_cell=(2, 2), lock_cell=(2, 4)):
        """A Key/Lock pair sharing a pairing number, placed and registered."""
        key = main.Block(*key_cell, shape=main.Shape.KEY, key_number=number)
        lock = main.Block(*lock_cell, shape=main.Shape.LOCK, key_number=number)
        self.game.grid[key_cell] = key
        self.game.grid[lock_cell] = lock
        return key, lock

    def test_the_card_data(self):
        self.assertEqual(main.Card.name(main.Card.GATE), "Gate")
        self.assertEqual(main.Card.PRICES[main.Card.GATE], 24)
        self.assertEqual(main.Card.rarity_name(main.Card.GATE), "Common")
        self.assertTrue(main.Card.comment(main.Card.GATE))
        description = main.Card.description(main.Card.GATE)
        self.assertIn("30 chips", description)
        self.assertIn("key", description)
        self.assertIn("lock", description)
        self.assertIn(main.Card.GATE, main.Card.ORDER)
        self.assertIn(main.Card.GATE, main.Card.COLORS)
        self.assertIn(main.Card.GATE, main.Card.GLYPHS)
        # A whole card with no measured phase: it pays on an event, not at the
        # start or the end of a run, and it has no group or scorer half.
        self.assertIsNone(components.match_group_card_meta(main.Card.GATE))
        self.assertIsNone(components.card_scorer(main.Card.GATE))
        self.assertIsNone(components.named_card_phase(main.Card.GATE))
        self.assertNotIn(main.Card.GATE, components.NAMED_CARD_ORDER)
        self.assertEqual(main.GATE_PASS_CHIPS, 30)

    def test_a_key_then_its_lock_pays_thirty_chips(self):
        self._own()
        key, lock = self._pair()
        self.game.score_chips = 100
        self.game.score_particles.clear()

        marble = self._card_fire(key)          # the marble collects the key
        self.assertIn(7, marble.collected_keys)
        self.assertFalse(lock.locked)         # ...which opens the lock
        self.assertEqual(self.game.score_chips, 100)   # the key itself pays 0

        self._card_fire(lock, marble)         # ...and the passage pays
        self.assertEqual(self.game.score_chips, 130)
        particle = self.game.score_particles[-1]
        self.assertEqual((particle.text, particle.color), ("30", main.GREEN))

    def test_every_pass_pays(self):
        # "each time ... passes through": the key is not used up, so a marble
        # crossing the opened lock again pays again.
        self._own()
        key, lock = self._pair()
        self.game.score_chips = 0
        marble = self._card_fire(key)
        for _ in range(3):
            self._card_fire(lock, marble)
        self.assertEqual(self.game.score_chips, 3 * main.GATE_PASS_CHIPS)

    def test_only_the_marble_that_collected_the_key_is_paid(self):
        # The lock is open for the whole run once ANY marble's key touches it,
        # but the card reads the sequence on ONE marble: a second marble walking
        # through the doorway the first one opened pays nothing (the user's
        # "a marble collects a key and then passes through its corresponding
        # open lock").
        self._own()
        key, lock = self._pair()
        self.game.score_chips = 0
        collector = self._card_fire(key)
        self.game.score_chips = 0
        other = self._card_fire(lock)         # a fresh marble, no key
        self.assertIsNot(other, collector)
        self.assertNotIn(7, other.collected_keys)
        self.assertEqual(self.game.score_chips, 0)
        # ...while the collector still is.
        self._card_fire(lock, collector)
        self.assertEqual(self.game.score_chips, main.GATE_PASS_CHIPS)

    def test_a_still_locked_lock_pays_nothing(self):
        # No key has been collected, so the lock is a solid door. (The contact
        # cannot happen in play — a locked Lock has a hitbox — but the rule is
        # "passes through its corresponding OPEN lock", so the gate is pinned.)
        self._own()
        key, lock = self._pair()
        self.assertTrue(lock.locked)
        self.game.score_chips = 0
        self._card_fire(lock)
        self.assertEqual(self.game.score_chips, 0)

    def test_a_lock_with_another_number_is_not_its_key(self):
        self._own()
        key, _ = self._pair(number=7)
        _, other_lock = self._pair(number=8, key_cell=(4, 2), lock_cell=(4, 4))
        self.game.score_chips = 0
        marble = self._card_fire(key)
        self.assertIn(7, marble.collected_keys)
        self._card_fire(other_lock, marble)
        self.assertEqual(self.game.score_chips, 0)

    def test_a_lock_left_locked_by_a_keyless_number_pays_nothing(self):
        # A key with no pairing number (a lone half) opens nothing, so its lock
        # stays shut and there is nothing to pass through.
        self._own()
        key, lock = self._pair(number=0)
        self.game.score_chips = 0
        marble = self._card_fire(key)
        self.assertEqual(marble.collected_keys, {0})
        self.assertTrue(lock.locked)
        self._card_fire(lock, marble)
        self.assertEqual(self.game.score_chips, 0)

    def test_without_the_card_nothing_is_paid(self):
        self.game.cards = []
        key, lock = self._pair()
        self.game.score_chips = 0
        marble = self._card_fire(key)
        self._card_fire(lock, marble)
        self.assertEqual(self.game.score_chips, 0)
        # The key is still remembered (the bookkeeping is the game's, not the
        # card's): owning the card later in the run starts paying at once.
        self.assertIn(7, marble.collected_keys)

    def test_a_card_cutter_gate_pays_nothing(self):
        card = main.CardItem(main.Card.GATE, 24)
        self.game.cards = [card]
        self.game.disabled_card = card
        key, lock = self._pair()
        self.game.score_chips = 0
        marble = self._card_fire(key)
        self._card_fire(lock, marble)
        self.assertEqual(self.game.score_chips, 0)

    def test_a_split_copy_keeps_the_keys_its_parent_carried(self):
        # A split copy is a full marble, so a key its parent collected opens the
        # lock for the copy too (see Game._split_marble).
        self._own()
        key, lock = self._pair()
        self.game.score_chips = 0
        marble = self._card_fire(key)
        copy = self.game._split_marble(marble, key)
        self.assertIsNotNone(copy)
        self.assertIn(7, copy.collected_keys)
        self._card_fire(lock, copy)
        self.assertEqual(self.game.score_chips, main.GATE_PASS_CHIPS)
