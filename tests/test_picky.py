"""Two changes: a halved score on an enemy hit, and Picky's real reward.

User requests:

* "make the score halve chips and halve score on collision with an enemy instead
  of setting both to 0" — a marble that fights a foe keeps half of what it had
  built (chips and mult are both halved) instead of being left scoring nothing;
* "make the 'picky' scorer reward a permanent new random structure generated
  every run instead of a new 'shop slot'" — a whole structure point buys a
  PERMANENT structure, and each run rolls a new random one and lays it out with
  the level's own (see Game._reroll_bonus_structures /
  Game._place_bonus_structures).

The first blow's arithmetic is covered with the rest of the enemy rules (see
tests/test_levels.py); what is here is what the halving CHANGES from a wipe — the
second blow, a marble that was worth nothing, and the row that says so.
"""

from tests.game_test_case import *  # noqa: F401,F403


class EnemyHalvingTests(GameTestCase):
    """A foe halves the marble's chips and mult; it never wipes them."""

    def _start_level(self):
        """A live run with the first level's cast on the board."""
        self.game.unlocked_cells = set()
        self.game.run_number = 0
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.grid[(0, 10)] = main.Block(0, 10, scorer=main.Scorer.FINISH)
        self.assertTrue(self.game.reset_run(False))
        # A devourer eats the marble it touches, so it cannot show a halving.
        enemy = next((block for block in self.game.live_enemies()
                      if block.kind != main.EnemyKind.DEVOURER), None)
        if enemy is None:
            self.skipTest("this level has no enemy a marble survives")
        return enemy, self.game.marbles[0]

    def _hit(self, enemy, marble):
        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

    def test_the_second_blow_lands_for_a_quarter(self):
        # Both factors halve, so a marble that fights twice is worth a quarter
        # of what it started with — the reason a fight ends.
        enemy, marble = self._start_level()
        enemy.hits_left = None
        enemy.hp = enemy.max_hp = 100_000
        marble.chips = 40
        marble.mult = 2

        self._hit(enemy, marble)
        self.assertEqual((marble.chips, marble.mult), (20, 1))
        before = enemy.hp
        self._hit(enemy, marble)

        self.assertAlmostEqual(before - enemy.hp, 20)
        self.assertEqual((marble.chips, marble.mult), (10, 0.5))

    def test_a_marble_worth_nothing_stays_at_nothing(self):
        enemy, marble = self._start_level()
        marble.chips = 0
        marble.mult = 0

        self._hit(enemy, marble)

        self.assertEqual((marble.chips, marble.mult), (0, 0))

    def test_the_enemys_own_row_says_what_a_hit_does(self):
        enemy, _marble = self._start_level()
        rows = dict(self.game._describe_item(enemy))
        self.assertIn("halved", rows["Damage"])
        self.assertIn("chips x mult", rows["Damage"])


class PickyStructureTests(GameTestCase):
    """Picky's points buy a permanent structure, fresh every run."""

    def _picky_points(self, triggers):
        """Land ``triggers`` Picky hits this run (two bank a whole point)."""
        self.game.run_active = True
        for _ in range(triggers):
            block = main.Block(0, 0, scorer=main.Scorer.PICKY)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.game.run_active = False

    def _continue(self):
        """Click CONTINUE on a finished run: the points convert."""
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()

    def _bonus(self):
        return [item for item in self.game.shop.items
                if getattr(item, "is_bonus_structure", False)]

    def _tool_for(self, structure):
        """A real tool that opens ``structure`` — the player's own way in."""
        wanted = set(main.Structure.verbs(structure.value))
        for tool_value in main.Tool.ORDER:
            if wanted & set(main.Tool.verbs(tool_value)):
                tool = main.ToolItem(tool_value, main.Tool.PRICES[tool_value])
                self.game.toolbox.add(tool)
                self.game.ensure_board_cells()
                return tool
        return None

    def _open_bonus(self):
        """Open the Picky structure the way the player does (tool, then S).

        Returns the plan entry it stood for, and the square it gave up.
        """
        extra = self._bonus()[0]
        index, cell = extra.bonus_index, self.game.item_cell(extra)
        tool = self._tool_for(extra)
        if tool is None:
            self.skipTest("no tool opens this structure")
        self.game.energy = main.MAX_ENERGY
        self.game.selection = [tool, extra]
        self.game._refresh_actor()
        self.assertTrue(self.game._apply_tool())
        return index, cell

    def test_two_points_buy_one_permanent_structure(self):
        self._picky_points(2)
        self.assertEqual(self.game.option_run_gain, 1.0)
        self.assertEqual(self.game.bonus_structures, 0)

        self._continue()

        self.assertEqual(self.game.bonus_structures, 1)
        self.assertEqual(len(self._bonus()), 1,
                         "the structure is not standing on the board")

    def test_it_is_a_real_structure_on_an_open_square(self):
        self._picky_points(2)
        self._continue()
        extra = self._bonus()[0]
        cell = self.game.item_cell(extra)

        self.assertEqual(getattr(extra, "kind", None), "structure")
        self.assertIn(extra.value, main.Structure.ORDER)
        self.assertTrue(getattr(extra, "is_level_structure", False))
        self.assertIn(cell, self.game.unlocked_cells,
                      "it is standing on a square the player cannot use")
        # ...and it is scenery like any other: free, and opened with a tool.
        self.assertTrue(main.Structure.verbs(extra.value))

    def test_a_new_random_structure_is_generated_every_run(self):
        # One permanent point, twelve runs: the structure on the board is not
        # always the same one (the old reward re-rolled its offer, too).
        self.game.bonus_structures = 1
        seen = set()
        for _ in range(12):
            self.game._reroll_bonus_structures()
            seen.add(tuple(self.game.bonus_structure_values))
        self.assertEqual(len(self.game.bonus_structure_values), 1)
        self.assertGreater(len(seen), 1)

    def test_the_structure_keeps_its_square_through_a_layout_pass(self):
        self._picky_points(2)
        self._continue()
        extra = self._bonus()[0]
        cell = self.game.item_cell(extra)
        value = extra.value

        # A board edit re-lays the level: the same structure keeps its square.
        self.game._place_level_structures(self.game.current_level())

        self.assertIn(extra, self._bonus())
        self.assertEqual(self.game.item_cell(extra), cell)
        self.assertEqual(extra.value, value)

    def test_opening_one_leaves_it_gone_for_the_level_visit(self):
        self._picky_points(2)
        self._continue()

        index, cell = self._open_bonus()

        self.assertIn(index, self.game.spent_bonus_structures)
        self.game._place_level_structures(self.game.current_level())
        self.assertEqual(self._bonus(), [], "the opened structure came back")
        self.assertIsNotNone(self.game.item_at_cell(cell),
                             "the reward did not take the square")

    def test_a_new_level_deals_the_structures_again(self):
        self._picky_points(2)
        self._continue()
        self._open_bonus()
        self.game._place_level_structures(self.game.current_level())
        self.assertEqual(self._bonus(), [])

        # The level visit is over: a level's spents are the level's, and the
        # next one gets its structures back.
        self.game.spent_bonus_structures = set()
        self.game._place_bonus_structures(self.game.current_level(),
                                          self.game._player_block_cells())

        self.assertEqual(len(self._bonus()), 1)

    def test_two_structures_never_share_a_square(self):
        self.game.bonus_structures = 2
        self.game._refresh_bonus_structures()

        self.assertEqual(len(self._bonus()), 2)
        cells = [self.game.item_cell(item) for item in self._bonus()]
        self.assertNotIn(None, cells)
        self.assertEqual(len(cells), len(set(cells)))

    def test_it_rides_through_a_save_and_a_load(self):
        self._picky_points(2)
        self._continue()
        self.game.bonus_structures = 2
        self.game._refresh_bonus_structures()
        values = list(self.game.bonus_structure_values)
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, self.game.save_slot)

        self.assertEqual(fresh.bonus_structures, 2)
        self.assertEqual(fresh.bonus_structure_values, values)
        standing = [item for item in fresh.shop.items
                    if getattr(item, "is_bonus_structure", False)]
        self.assertEqual([item.value for item in standing], values)
        for item in standing:
            self.assertIsNotNone(fresh.item_cell(item))

    def test_an_old_saves_bonus_slots_become_structures(self):
        # The reward changed shape, not the points spent on it: a save that
        # still counts "bonus shop slots" reads them as structures.
        self.game.save_slot = 2
        data = save_system._save_data(self.game)
        data.pop("bonus_structures", None)
        data.pop("bonus_structure_values", None)
        data["bonus_slots"] = 2
        save_system.ensure_saves()
        with open(save_system._slot_file_path(2), "w", encoding="utf-8") as f:
            json.dump(data, f)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 2)

        self.assertEqual(fresh.bonus_structures, 2)
        self.assertEqual(len([item for item in fresh.shop.items
                              if getattr(item, "is_bonus_structure", False)]),
                         2)

    def test_the_scorers_text_names_the_reward(self):
        text = main.scorer_description(main.Scorer.PICKY).lower()
        self.assertIn("structure point", text)
        self.assertIn("every run", text)
        self.assertNotIn("slot", text)

    def test_the_readout_under_the_cash_line_says_structure(self):
        self.game.toolbox.add(main.Component.scorer_component(
            main.Scorer.PICKY, amount=1))
        self.game.option_points = 1

        self.assertEqual(self.game._resource_display(),
                         [(1, "structure")])
