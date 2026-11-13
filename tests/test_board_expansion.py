"""Board squares, Board Units, and the cards that open the board.

User requests in this file:

* "make the drill scorer give 2x board square" — the Drill scorer hands over
  Board Units (its own magnitude, 2 at the average) instead of opening squares;
* "rename the 'drill' card to 'excavator'" — the TOOL is an Excavator now; the
  SCORER is still the Drill;
* "make conquistador give 4x board square when used" — the card hands over 4
  Board Units after every run;
* "make all items that unlock random board squares give board squares instead,
  unless otherwise stated" — Expansion (v1), the Drill scorer and Conquistador
  now pay in Board Units, which each open the square the PLAYER picks, while the
  items that state otherwise keep opening squares themselves: a Bomb's blast,
  Expansion's upgrade, and Dynamite;
* "add a card, 'dynamite': when used with no items selected, unlock 10 random
  board squares adjacent to the unlocked area this card was used in. or, dig or
  reveal. costs 2 energy."
"""

from tests.game_test_case import *  # noqa: F401,F403


class DrillScorerTests(GameTestCase):
    """The Drill scorer pays in Board Units (user request)."""

    def _start_locked_game(self):
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        return self.game

    def _touch(self, block):
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])

    def _continue(self):
        g = self.game
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch.object(main.Game, "_begin_level"), \
                mock.patch("main.random.random", return_value=0.9):
            g._continue_run()

    def test_the_scorer_states_board_units(self):
        self.assertEqual(main.Scorer.name(main.Scorer.DRILL), "Drill")
        line = main.scorer_description(main.Scorer.DRILL,
                                       main.MAGNITUDES.SCORERS[main.Scorer.DRILL])
        self.assertIn("Board Unit", line)
        self.assertNotIn("locked board square", line)
        # ...and a match-group card that carries it reads the same way.
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.DRILL)
        self.assertIn("Board Unit", main.card_description(value, 2))

    def test_a_touch_hands_over_its_magnitude_in_units_after_the_run(self):
        g = self._start_locked_game()
        block = main.Block(2, 2, scorer=main.Scorer.DRILL,
                           scorer_amount=main.MAGNITUDES.SCORERS[main.Scorer.DRILL])
        g.grid[(2, 2)] = block
        before_squares = len(g.unlocked_cells)
        before_units = g.board_units

        self._touch(block)

        # Nothing is paid until the run is committed...
        self.assertEqual(g.board_units, before_units)
        self.assertEqual(g.drill_run_units, 2)
        self._continue()
        # ...then the drill's 2 squares arrive as 2 Board Units, and no square
        # was picked for the player.
        self.assertEqual(g.board_units, before_units + 2)
        self.assertEqual(len(g.unlocked_cells), before_squares)

    def test_the_magnitude_is_the_number_of_units(self):
        # A golem-folded drill (amount 4) hands over four units.
        g = self._start_locked_game()
        block = main.Block(2, 2, scorer=main.Scorer.DRILL, scorer_amount=4)
        g.grid[(2, 2)] = block
        before_units = g.board_units
        self._touch(block)
        self._continue()
        self.assertEqual(g.board_units, before_units + 4)

    def test_a_retry_hands_back_nothing(self):
        g = self._start_locked_game()
        before_units = g.board_units
        g.drill_run_units = 2
        g.run_results.append(True)
        g.runs_cleared = 1
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):
            g._retry_run()
        self.assertEqual(g.board_units, before_units)
        self.assertEqual(g.drill_run_units, 0)


class ConquistadorTests(GameTestCase):
    """Conquistador hands over 4 Board Units after every run (user request)."""

    def test_the_card_states_board_units(self):
        self.assertEqual(main.Card.name(main.Card.CONQUISTADOR), "Conquistador")
        self.assertEqual(main.MAGNITUDES.BOARD_UNITS_PER_CONQUISTADOR, 4)
        line = main.Card.description(main.Card.CONQUISTADOR)
        self.assertIn("4 Board Units", line)
        self.assertNotIn("locked board squares", line)

    def test_it_hands_over_four_units_after_a_run(self):
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        g = self.game
        g.cards.append(main.CardItem(main.Card.CONQUISTADOR,
                                     main.Card.PRICES[main.Card.CONQUISTADOR]))
        before_units = g.board_units
        before_squares = len(g.unlocked_cells)
        g.run_complete = True
        g.awaiting_after_run = True
        with mock.patch.object(main.Game, "_begin_level"), \
                mock.patch("main.random.random", return_value=0.9):
            g._continue_run()
        self.assertEqual(g.board_units,
                         before_units
                         + main.MAGNITUDES.BOARD_UNITS_PER_CONQUISTADOR)
        self.assertEqual(len(g.unlocked_cells), before_squares)


class BoardUnitGrantsTests(GameTestCase):
    """Which items hand over units, and which still open squares themselves."""

    def _action(self, value):
        item = main.ActionItem(value, main.Action.PRICES[value])
        self.game._adopt_action(item)
        return item

    def _use(self, action):
        self.game.selection = [action]
        self.game._refresh_actor()
        return self.game._apply_action()

    def test_expansion_and_the_reroll_less_set_hand_over_units(self):
        # Expansion v1 is one of the "random board squares" items: it gives
        # Board Units rather than picking four squares (see test_actions for the
        # unit-by-unit detail).
        self.game._reset_board_to_start()
        before = len(self.game.unlocked_cells)
        before_units = self.game.board_units
        self.assertTrue(self._use(self._action(main.Action.EXPANSION)))
        self.assertEqual(self.game.board_units,
                         before_units + main.EXPANSION_SQUARES)
        self.assertEqual(len(self.game.unlocked_cells), before)

    def test_the_upgrade_states_otherwise_and_still_opens_the_board(self):
        self.game._reset_board_to_start()
        action = self._action(main.Action.EXPANSION)
        action.version = 2
        before_units = self.game.board_units
        self.assertTrue(self._use(action))
        self.assertFalse(self.game.board_locked())
        self.assertEqual(self.game.board_units, before_units)

    def test_a_bomb_states_otherwise_and_still_blasts(self):
        # The bomb's text names the radius it opens, so it keeps opening
        # squares instead of paying units (see test_board_units).
        self.assertIn("unlocks every board unit within 1 cell",
                      main.scorer_description(main.Scorer.BOMB).lower())

    def test_the_grant_announces_how_many_are_in_hand(self):
        self.game.board_units = 0
        self.assertEqual(self.game._grant_board_units(3), 3)
        self.assertIn("3 Board Units", self.game.shop_message)
        self.assertIn("3 left", self.game.shop_message)


class ExcavatorRenameTests(GameTestCase):
    """The "drill" card is an Excavator now (user request)."""

    def test_the_tool_is_an_excavator_and_the_scorer_is_still_a_drill(self):
        self.assertEqual(main.Tool.name(main.Tool.DRILL), "Excavator")
        self.assertEqual(main.Tool.GLYPHS[main.Tool.DRILL], "E")
        # The SCORER keeps its name: the request renamed the card, not the part.
        self.assertEqual(main.Scorer.name(main.Scorer.DRILL), "Drill")
        # No TOOL is called Drill any more, so the two never read alike.
        names = {main.Tool.name(value) for value in main.Tool.ORDER}
        self.assertNotIn("Drill", names)
        self.assertIn("Excavator", names)

    def test_the_excavator_still_opens_any_door_for_free(self):
        # The rename is a rename: same verbs, same 0 energy, same Dirt.
        self.assertEqual(main.Tool.verbs(main.Tool.DRILL),
                         (main.Verb.BREAK, main.Verb.FIX, main.Verb.DIG,
                          main.Verb.REVEAL))
        self.assertEqual(main.Tool.energy(main.Tool.DRILL), 0)
        self.assertEqual(main.Tool.makes(main.Tool.DRILL),
                         (("tool", main.Tool.DIRT), 1))
        self.assertEqual(main.Keyword.line(main.ToolItem(main.Tool.DRILL)),
                         "break, fix, dig, reveal, reusable")

    def test_the_codex_calls_it_an_excavator_too(self):
        self.game._unlock_entire_collection()
        entries = [entry for entry in self.game._collection_entries()
                   if entry[0] == "tool" and entry[1] == main.Tool.DRILL]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][2], "Excavator")


class DynamiteTests(GameTestCase):
    """Dynamite: opens the board bare, or digs or reveals a structure."""

    def setUp(self):
        super().setUp()
        self._fresh_locked_game()

    def _fresh_locked_game(self):
        # A mid-test reset must not re-run setUp: that would overwrite the
        # captured old player-data paths with the throwaway ones and leave the
        # whole suite reading from a deleted temp folder.
        self.game = main.Game()
        self.game.title_screen = False
        self.game.trials_enabled = False
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.ensure_board_cells()

    def _dynamite(self, amount=None):
        item = (main.ActionItem(main.Action.DYNAMITE,
                                main.Action.PRICES[main.Action.DYNAMITE])
                if amount is None else
                main.ActionItem(main.Action.DYNAMITE,
                                main.Action.PRICES[main.Action.DYNAMITE],
                                amount=amount))
        self.game._adopt_action(item)
        return item

    def _structure(self, value):
        item = main.StructureItem(value, main.Structure.PRICES[value])
        item.is_level_structure = True
        self.game.shop.items.append(item)
        self.game.set_item_cell(item, self.game._first_free_cell())
        return item

    def _use(self, action, subject=None):
        self.game.selection = [action] + ([subject] if subject is not None else [])
        self.game._refresh_actor()
        return self.game._apply_action()

    def test_the_catalogue_row(self):
        self.assertEqual(main.Action.name(main.Action.DYNAMITE), "Dynamite")
        self.assertIn(main.Action.DYNAMITE, main.Action.ORDER)
        self.assertEqual(main.Action.energy(main.Action.DYNAMITE), 2)
        self.assertEqual(main.Action.MAGNITUDE[main.Action.DYNAMITE],
                         main.MAGNITUDES.DYNAMITE_SQUARES)
        self.assertEqual(main.MAGNITUDES.DYNAMITE_SQUARES, 10)
        self.assertGreater(main.Action.PRICES[main.Action.DYNAMITE], 0)
        self.assertIn(main.Action.DYNAMITE, main.Action.GLYPHS)
        self.assertIn(main.Action.DYNAMITE, main.Action.COLORS)
        # It is aimed at a structure but does not need one.
        self.assertTrue(main.Action.targets_structures(main.Action.DYNAMITE))
        self.assertTrue(main.Action.optional_target(main.Action.DYNAMITE))
        line = main.Action.description(main.Action.DYNAMITE, 1)
        self.assertIn("10 random board squares", line)
        self.assertIn("digs or reveals", line)
        self.assertIn("2 energy", line)
        # A golem-folded one reads the squares it would really open.
        self.assertIn("20 random board squares",
                      main.Action.description(main.Action.DYNAMITE, 1, 20))

    def test_used_bare_it_opens_ten_squares(self):
        action = self._dynamite()
        self.game.energy = 3
        before = len(self.game.unlocked_cells)
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action))

        self.assertEqual(len(self.game.unlocked_cells),
                         before + main.MAGNITUDES.DYNAMITE_SQUARES)
        self.assertEqual(self.game.energy, 1, "its 2 energy was not spent")
        self.assertFalse(self.game.owns_item(action), "the card was not discarded")
        self.assertEqual(self.game.discarded_items_run, discarded + 1)
        self.assertIn("blew open 10 board squares", self.game.shop_message)

    def test_a_folded_dynamite_opens_its_own_magnitude(self):
        action = self._dynamite(amount=20)
        self.game.energy = 3
        before = len(self.game.unlocked_cells)

        self.assertTrue(self._use(action))

        self.assertEqual(len(self.game.unlocked_cells), before + 20)

    def test_the_squares_it_opens_are_on_the_frontier(self):
        action = self._dynamite()
        self.game.energy = 3
        before = set(self.game.unlocked_cells)

        self.assertTrue(self._use(action))

        frontier = self.game._locked_adjacent_cells
        gained = self.game.unlocked_cells - before
        self.assertTrue(gained)
        for cell in gained:
            neighbours = {(cell[0] + dx, cell[1] + dy)
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
            self.assertTrue(neighbours & before,
                            f"{cell} is not next to the board it opened from")

    def test_it_digs_or_reveals_a_structure(self):
        for value in (main.Structure.PIT, main.Structure.QUARRY,
                      main.Structure.LIBRARY):
            with self.subTest(structure=main.Structure.name(value)):
                self._fresh_locked_game()
                action = self._dynamite()
                structure = self._structure(value)
                stood = self.game.item_cell(structure)
                self.game.energy = 3
                before_units = len(self.game.unlocked_cells)

                self.assertTrue(self._use(action, structure))

                # The reward took the structure's square, and the structure is
                # spent (its square is marked for the level visit).
                reward = self.game.item_at_cell(stood)
                self.assertIsNotNone(reward)
                self.assertNotEqual(getattr(reward, "kind", None), "structure")
                self.assertIn((structure.value, stood[0], stood[1]),
                              self.game.spent_structures)
                self.assertFalse(self.game.owns_item(action))
                self.assertEqual(self.game.energy, 1)
                self.assertEqual(len(self.game.unlocked_cells), before_units,
                                 "the structure mode opened squares too")

    def test_a_structure_it_cannot_open_is_refused_and_kept(self):
        # A mirror answers fix and break, not dig or reveal.
        action = self._dynamite()
        structure = self._structure(main.Structure.MIRROR)
        self.game.energy = 3

        self.assertFalse(self._use(action, structure))

        self.assertTrue(self.game.owns_item(action), "the card was spent")
        self.assertEqual(self.game.energy, 3, "a refusal cost energy")
        self.assertIn("cannot be dug or revealed", self.game.shop_message)

    def test_the_golem_is_refused(self):
        # A golem needs a tool and TWO items; a blast cannot bring them.
        action = self._dynamite()
        golem = self._structure(main.Structure.GOLEM)
        self.game.energy = 3

        self.assertFalse(self._use(action, golem))

        self.assertTrue(self.game.owns_item(action))
        self.assertIn("two items", self.game.shop_message)

    def test_a_second_structure_is_too_many_targets(self):
        action = self._dynamite()
        first = self._structure(main.Structure.PIT)
        second = self._structure(main.Structure.QUARRY)
        self.game.energy = 3

        self.game.selection = [action, first, second]
        self.game._refresh_actor()
        self.assertFalse(self.game._apply_action())

        self.assertTrue(self.game.owns_item(action))
        self.assertIn("1 structure", self.game.shop_message)

    def test_an_unrelated_item_selected_blocks_the_blast(self):
        # "when used with no items selected": a block in the selection is not
        # nothing, and Dynamite cannot use a block.
        action = self._dynamite()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "b", effects=[])
        self.game.toolbox.add(block)
        self.game.energy = 3
        before = len(self.game.unlocked_cells)

        self.assertFalse(self._use(action, block))

        self.assertEqual(len(self.game.unlocked_cells), before)
        self.assertTrue(self.game.owns_item(action))

    def test_a_full_board_refuses_the_blast(self):
        action = self._dynamite()
        for x in range(main.GRID_WIDTH):
            for y in range(main.GRID_HEIGHT):
                self.game._unlock_cell(x, y)
        self.game.energy = 3

        self.assertFalse(self._use(action))

        self.assertTrue(self.game.owns_item(action))
        self.assertEqual(self.game.energy, 3)
        self.assertIn("already fully unlocked", self.game.shop_message)

    def test_out_of_energy_is_refused(self):
        action = self._dynamite()
        self.game.energy = 1
        before = len(self.game.unlocked_cells)

        self.assertFalse(self._use(action))

        self.assertEqual(len(self.game.unlocked_cells), before)
        self.assertTrue(self.game.owns_item(action))
        self.assertIn("Out of energy", self.game.shop_message)

    def test_the_sidebar_and_hint_state_both_modes(self):
        action = self._dynamite()
        rows = dict(self.game._describe_item(action))
        ability = rows["Ability - Apply"]
        self.assertIn("no target, or 1 structure", ability)
        self.assertIn("2 energy", ability)
        hint = self.game._action_hint(action, "board")
        self.assertIn("nothing selected", hint)
        self.assertIn("dig or reveal", hint)

    def test_a_pack_keeps_it_armed_rather_than_firing_it(self):
        action = main.ActionItem(main.Action.DYNAMITE,
                                 main.Action.PRICES[main.Action.DYNAMITE])
        before = len(self.game.unlocked_cells)

        _ok, message = self.game._keep_action_from_pack(action)

        # It waits for the player, so it can be aimed or blasted on purpose.
        self.assertIs(self.game.pending_pack_action, action)
        self.assertEqual(len(self.game.unlocked_cells), before)
        self.assertIn("nothing selected", message)

    def test_it_has_icon_art(self):
        art = main.ui._build_action_art(main.Action.DYNAMITE)
        self.assertGreater(art.get_bounding_rect().width, 0)
