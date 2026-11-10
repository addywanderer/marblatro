"""The Reroll card, and the reroll mechanics that now deal it.

User request: "add a card, 'reroll': randomize a selected structure, discard
this card, draw a card (0 energy). make all reroll mechanics spawn this card on
the board when triggered."

So there are two halves here:

* the CARD — an action aimed at a STRUCTURE (see Action.STRUCTURE_TARGET) that
  turns it into another random structure where it stands, then discards itself
  and draws a card;
* the MECHANICS — Fresh and Brainstorm used to bank free shop rerolls, which the
  shelf's rework left nothing to spend; they deal the Reroll card onto the board
  instead (see Game._spawn_reroll_cards).

A rerolled structure is remembered in the level's PLAN (see
Game.structure_rerolls), so no later layout pass — an R, a board edit, a run
start, a load — can quietly deal the structure the level authored again.
"""

from tests.game_test_case import *  # noqa: F401,F403


class RerollCardTests(GameTestCase):
    """The card itself: its catalogue row, its target and what using it does."""

    def setUp(self):
        super().setUp()
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        self.game.ensure_board_cells()

    # --- helpers ------------------------------------------------------------

    def _reroll(self, amount=None):
        item = (main.ActionItem(main.Action.REROLL, 26) if amount is None
                else main.ActionItem(main.Action.REROLL, 26, amount=amount))
        self.game._adopt_action(item)
        return item

    def _structure(self):
        """A level structure standing on the board (with its plan entry)."""
        structures = self.game.level_structures()
        self.assertTrue(structures, "the level laid no structures out")
        return structures[0]

    def _deck_card(self, value=main.Card.JOKER):
        card = main.CardItem(value, main.Card.PRICES.get(value, 24))
        self.game.cards.append(card)
        self.game._to_deck(card)
        return card

    def _deck_items(self):
        return [item for item in self.game.toolbox.every_item()
                if self.game.item_cell(item) is None
                and self.game.owns_item(item)]

    def _use(self, action, subject):
        """Use the action on the subject through the real S-key dispatch."""
        self.game.selection = [action, subject]
        self.game._refresh_actor()
        return self.game._apply_action()

    def _reroll_cards(self):
        return [item for item in self.game.actions
                if getattr(item, "value", None) == main.Action.REROLL]

    # --- the catalogue row --------------------------------------------------

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.REROLL), "Reroll")
        self.assertEqual(main.Action.REROLL, 18)
        self.assertIn(main.Action.REROLL, main.Action.ORDER)
        self.assertGreater(main.Action.PRICES[main.Action.REROLL], 0)
        self.assertIn(main.Action.REROLL, main.Action.GLYPHS)
        self.assertIn(main.Action.REROLL, main.Action.COLORS)
        # User request: "(0 energy)".
        self.assertEqual(main.Action.energy(main.Action.REROLL), 0)
        # It is the one action aimed at a structure, and it needs exactly one.
        self.assertTrue(main.Action.needs_target(main.Action.REROLL))
        self.assertTrue(main.Action.targets_structures(main.Action.REROLL))
        for value in main.Action.ORDER:
            if value == main.Action.REROLL:
                continue
            self.assertFalse(main.Action.targets_structures(value),
                             main.Action.name(value))
        # Its line states its own number, from the one place the number lives.
        line = main.Action.description(main.Action.REROLL, 1)
        self.assertIn("structure", line)
        self.assertIn("discards this card", line)
        self.assertIn("1 card", line)
        self.assertIn("0 energy", line)
        self.assertIn("2 cards", main.Action.description(main.Action.REROLL, 1, 2))
        self.assertEqual(main.Action.MAGNITUDE[main.Action.REROLL],
                         main.MAGNITUDES.REROLL_DRAWS)

    def test_a_structure_is_a_target_only_for_the_reroll(self):
        structure = self._structure()
        # Without an action the general question still excludes structures...
        self.assertFalse(self.game.is_action_target(structure))
        # ...and every action but the Reroll refuses one.
        death = main.ActionItem(main.Action.DEATH, 24)
        self.assertFalse(self.game.is_action_target(structure, death))
        self.assertTrue(self.game.is_action_target(
            structure, main.ActionItem(main.Action.REROLL, 26)))
        # A reroll is pointed at a structure, so a card is not a target for it.
        card = main.CardItem(main.Card.JOKER, 24)
        self.assertFalse(self.game.is_action_target(
            card, main.ActionItem(main.Action.REROLL, 26)))

    # --- using it -----------------------------------------------------------

    def test_it_turns_the_structure_into_another_one_where_it_stands(self):
        action = self._reroll()
        structure = self._structure()
        stood = self.game.item_cell(structure)
        was = structure.value

        self.assertTrue(self._use(action, structure))

        self.assertNotEqual(structure.value, was, "the structure was not rerolled")
        self.assertEqual(self.game.item_cell(structure), stood,
                         "the structure left its square")
        self.assertIn(structure, self.game.shop.items,
                      "the structure was taken off the board")
        self.assertTrue(getattr(structure, "is_level_structure", False),
                        "the structure stopped being the level's")
        self.assertEqual(structure.name,
                         main.Structure.name(structure.value),
                         "the structure kept its old name")
        self.assertEqual(self.game.spent_structures, set(),
                         "a reroll spent the structure")

    def test_it_discards_itself_and_draws_a_card(self):
        action = self._reroll()
        structure = self._structure()
        shot = self.game.item_cell(action)
        deck_card = self._deck_card()
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action, structure))

        self.assertNotIn(action, self.game.actions, "the card was not discarded")
        self.assertEqual(self.game.discarded_items_run, discarded + 1,
                         "the discard was not counted")
        self.assertEqual(self.game.item_cell(deck_card), shot,
                         "the draw did not take the square the card gave up")

    def test_a_golem_folded_reroll_draws_its_own_magnitude(self):
        action = self._reroll(amount=2)
        structure = self._structure()
        first = self._deck_card(main.Card.JOKER)
        second = self._deck_card(main.Card.PLANE)

        self.assertTrue(self._use(action, structure))

        self.assertIsNotNone(self.game.item_cell(first))
        self.assertIsNotNone(self.game.item_cell(second))

    def test_an_empty_deck_still_rerolls(self):
        # The reroll is the card's effect; the draw is what it also does. With
        # nothing in the deck the structure still turns over.
        action = self._reroll()
        structure = self._structure()
        was = structure.value
        self.assertEqual(self._deck_items(), [])

        self.assertTrue(self._use(action, structure))

        self.assertNotEqual(structure.value, was)
        self.assertNotIn(action, self.game.actions)

    def test_it_is_refused_and_kept_without_a_structure(self):
        action = self._reroll()
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        self.game.selection = [action, block]
        self.game._refresh_actor()

        self.assertFalse(self.game._apply_action())

        self.assertIn(action, self.game.actions, "the card was spent for nothing")
        self.assertIn("1 target", self.game.shop_message)

    def test_it_is_refused_and_kept_when_there_is_nothing_else_to_roll(self):
        # A catalogue of one structure has nothing to reroll into: nothing
        # happens and the card stays in hand.
        action = self._reroll()
        structure = self._structure()
        was = structure.value
        saved = list(main.Structure.ORDER)
        main.Structure.ORDER[:] = [was]
        try:
            self.assertFalse(self._use(action, structure))
        finally:
            main.Structure.ORDER[:] = saved

        self.assertEqual(structure.value, was)
        self.assertIn(action, self.game.actions)

    def test_using_it_costs_no_energy(self):
        action = self._reroll()
        structure = self._structure()
        self.game.energy = 0

        self.assertTrue(self._use(action, structure))
        self.assertEqual(self.game.energy, 0)

    def test_it_is_used_with_the_mouse_and_the_s_key(self):
        # The whole use through the real input path: click the card, click the
        # structure, press S.
        action = self._reroll()
        structure = self._structure()
        stood = self.game.item_cell(structure)
        was = structure.value

        self._click(self._item_pos(action))
        self._click(self._item_pos(structure))
        self.assertEqual(self.game.selected_action_subject, structure,
                         "the structure was not taken as the card's target")
        self._press(main.pygame.K_s)

        self.assertNotEqual(structure.value, was, "the card did nothing")
        self.assertEqual(self.game.item_cell(structure), stood)
        self.assertNotIn(action, self.game.actions)

    def test_the_sidebar_says_what_it_needs(self):
        action = self._reroll()
        rows = dict(self.game._describe_item(action))
        lines = " ".join(f"{label} {text}" for label, text in rows.items())
        self.assertIn("1 target", lines)
        self.assertIn("structure", self.game._action_hint(action, "board"))

    # --- the reroll sticks --------------------------------------------------

    def test_the_reroll_is_written_into_the_levels_plan(self):
        action = self._reroll()
        structure = self._structure()
        index = structure.plan_index

        self._use(action, structure)

        self.assertEqual(self.game.structure_rerolls.get(index), structure.value)

    def test_laying_the_level_out_again_keeps_the_reroll(self):
        action = self._reroll()
        structure = self._structure()
        stood = self.game.item_cell(structure)
        self._use(action, structure)
        rolled = structure.value

        # An R / a board edit / a run start lays the level out again.
        self.game._begin_level()

        standing = [item for item in self.game.level_structures()
                    if self.game.item_cell(item) == stood]
        self.assertEqual(len(standing), 1, "the rerolled structure is not there")
        self.assertEqual(standing[0].value, rolled,
                         "the layout undid the reroll")

    def test_a_relayout_does_not_deal_the_structure_twice(self):
        action = self._reroll()
        structure = self._structure()
        before = len(self.game.level_structures())
        self._use(action, structure)

        self.game._begin_level()

        self.assertEqual(len(self.game.level_structures()), before,
                         "the reroll handed out an extra structure")

    def test_the_reroll_survives_a_save_and_a_load(self):
        action = self._reroll()
        structure = self._structure()
        stood = self.game.item_cell(structure)
        self._use(action, structure)
        rolled = structure.value
        save_system.save_game(self.game, announce=False)

        fresh = main.Game()
        fresh.title_screen = False
        save_system.load_slot(fresh, self.game.save_slot)

        standing = [item for item in fresh.level_structures()
                    if fresh.item_cell(item) == stood]
        self.assertEqual(len(standing), 1, "the structure is not where it stood")
        self.assertEqual(standing[0].value, rolled,
                         "the load undid the reroll")


class RerollMechanicsTests(GameTestCase):
    """Every reroll mechanic deals the Reroll card (user request)."""

    def setUp(self):
        super().setUp()
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        self.game.ensure_board_cells()

    def _reroll_cards(self):
        return [item for item in self.game.actions
                if getattr(item, "value", None) == main.Action.REROLL]

    def _fresh_hit(self):
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        return block

    def _use_action(self, action):
        self.game.selection = [action]
        self.game._refresh_actor()
        return self.game._apply_action()

    def test_a_fresh_block_deals_a_reroll_card(self):
        self.assertEqual(self._reroll_cards(), [])

        self._fresh_hit()

        cards = self._reroll_cards()
        self.assertEqual(len(cards), 1, "Fresh dealt no Reroll card")
        self.assertIsNotNone(self.game.item_cell(cards[0]),
                             "the card did not land on the board")
        # The old bank is untouched: nothing spends a free shop reroll now.
        self.assertEqual(self.game.free_rerolls, 0)

    def test_a_fresh_card_on_a_matching_collision_deals_one_too(self):
        block = main.Block(2, 2, shape=main.Shape.PIPE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        card = _card_for_block(block, main.Scorer.FRESH)
        self.assertIsNotNone(card, "no Fresh card covers this block")
        self.game.cards.append(card)
        self.game.grid[(2, 2)] = block
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]

        self.game._handle_block_contacts([block])

        self.assertEqual(len(self._reroll_cards()), 1)

    def test_brainstorm_deals_two_reroll_cards(self):
        action = main.ActionItem(main.Action.BRAINSTORM, 25)
        self.game._adopt_action(action)

        self.assertTrue(self._use_action(action))

        self.assertEqual(len(self._reroll_cards()), main.BRAINSTORM_REROLLS)
        self.assertEqual(self.game.free_rerolls, 0)

    def test_v2_brainstorm_deals_four(self):
        action = main.ActionItem(main.Action.BRAINSTORM, 25, version=2)
        self.game._adopt_action(action)

        self.assertTrue(self._use_action(action))

        self.assertEqual(len(self._reroll_cards()),
                         main.BRAINSTORM_REROLLS_V2)

    def test_a_dealt_reroll_is_discovered_in_the_collection(self):
        self._fresh_hit()

        self.assertTrue(collection.is_action_discovered(main.Action.REROLL))

    def test_using_a_reroll_grows_the_tesseract(self):
        tesseract = main.CardItem(main.Card.TESSERACT,
                                  main.Card.PRICES[main.Card.TESSERACT])
        self.game.cards.append(tesseract)
        action = main.ActionItem(main.Action.REROLL, 26)
        self.game._adopt_action(action)
        structure = self.game.level_structures()[0]
        was = self.game.tesseract_bonus

        self.game.selection = [action, structure]
        self.game._refresh_actor()
        self.assertTrue(self.game._apply_action())

        self.assertAlmostEqual(self.game.tesseract_bonus,
                               was + main.TESSERACT_REROLL_XMULT)

    # --- what a retry takes back -------------------------------------------

    def test_retrying_takes_back_the_cards_the_run_dealt(self):
        self._fresh_hit()
        self.assertEqual(len(self._reroll_cards()), 1)
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(self._reroll_cards(), [],
                         "the retried run kept the card it dealt")

    def test_a_card_already_used_is_not_un_spent(self):
        self._fresh_hit()
        card = self._reroll_cards()[0]
        structure = self.game.level_structures()[0]
        self.game.selection = [card, structure]
        self.game._refresh_actor()
        self.assertTrue(self.game._apply_action())
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(self.game.reroll_cards_run_gain, [])

    def test_a_continued_run_keeps_the_card_it_dealt(self):
        self._fresh_hit()
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(len(self._reroll_cards()), 1,
                         "the committed run lost the card it earned")
        self.assertEqual(self.game.reroll_cards_run_gain, [])

    def test_a_bought_reroll_survives_a_retry(self):
        action = main.ActionItem(main.Action.BRAINSTORM, 25)
        self.game._adopt_action(action)
        self._use_action(action)
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(len(self._reroll_cards()), main.BRAINSTORM_REROLLS,
                         "a bought card was taken back with the run")


class FreshTextTests(GameTestCase):
    """What the codex and the sidebar say about a reroll mechanic."""

    def test_the_fresh_lines_name_the_card(self):
        line = main.scorer_description(main.Scorer.FRESH, 1)
        self.assertIn("Reroll card", line)
        self.assertNotIn("free reroll", line.lower())

    def test_brainstorm_describes_the_cards_it_deals(self):
        self.assertIn("Reroll cards",
                      main.Action.description(main.Action.BRAINSTORM, 1))
        self.assertIn("4 Reroll cards",
                      main.Action.description(main.Action.BRAINSTORM, 2))

    def test_the_tesseract_line_states_its_own_number(self):
        line = main.Card.DESCRIPTIONS[main.Card.TESSERACT]
        self.assertIn("Reroll card", line)
        self.assertIn(f"+{main.MAGNITUDES.TESSERACT_REROLL_XMULT:g} xMult", line)

    def test_the_reroll_has_icon_art(self):
        art = main.ui._build_action_art(main.Action.REROLL)
        self.assertGreater(art.get_bounding_rect().width, 0)
