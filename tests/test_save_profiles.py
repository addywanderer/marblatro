"""Saving, loading, and the player-data files under profiles/.

Split out of the old tests/test_run_scoring.py; the shared imports live in
tests/game_test_case.py (these three classes own their own setUp).
"""

from tests.game_test_case import *  # noqa: F401,F403


class SaveSystemTests(unittest.TestCase):
    """Save slots, serialization, and the slot-selection screen flow."""

    def setUp(self):
        # Point the save system at a throwaway folder so tests never touch the
        # real saves/ directory.
        self._tmp = tempfile.mkdtemp()
        self._old_saves_dir = save_system.SAVES_DIR
        save_system.SAVES_DIR = self._tmp
        # Keep the global achievements file out of test runs too.
        self._old_ach_file = achievements.FILE_PATH
        achievements.FILE_PATH = os.path.join(self._tmp, "achievements.json")
        achievements.reset()
        # The metagame (dice + run-start upgrades) is global too; keep it out
        # of test runs so no test inherits a leftover bonus.
        self._old_meta_file = metagame.FILE_PATH
        metagame.FILE_PATH = os.path.join(self._tmp, "metagame.json")
        metagame.reset()
        # The collection (discovered cards/components/trials) is global too.
        self._old_collection_file = collection.FILE_PATH
        collection.FILE_PATH = os.path.join(self._tmp, "collection.json")
        collection.reset()
        self.game = main.Game()
        self.game.title_screen = False
        self.game.trials_enabled = False

    def tearDown(self):
        save_system.SAVES_DIR = self._old_saves_dir
        achievements.FILE_PATH = self._old_ach_file
        achievements.reset()
        metagame.FILE_PATH = self._old_meta_file
        metagame.reset()
        collection.FILE_PATH = self._old_collection_file
        collection.reset()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _click(self, pos):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def _press(self, key):
        event = mock.Mock()
        event.type = main.pygame.KEYDOWN
        event.key = key
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def _close(self):
        event = mock.Mock()
        event.type = main.pygame.QUIT
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def test_quit_autosaves_current_game(self):
        self.game.save_slot = 1
        self.game.cash = 321
        self._close()
        self.assertFalse(self.game.running)
        data = save_system._read_slot(1)
        self.assertEqual(data["cash"], 321)

    def test_quit_without_slot_does_not_save(self):
        # A fresh game has no active slot; closing must not write to slot 1.
        self.game.cash = 999
        self._close()
        self.assertFalse(self.game.running)
        self.assertFalse(save_system._slot_has_save(1))

    def test_serialize_placed_block_round_trip(self):
        block = main.Block(3, 5, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=30, angle=90, portal_number=4, trigger_limit=2,
                           trigger_paid=50, effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE])
        block.spin = 45.0
        block.triggers_left = 0
        loaded = save_system._deserialize_item(save_system._serialize_item(block))
        self.assertIsInstance(loaded, main.Block)
        self.assertEqual((loaded.x, loaded.y), (3, 5))
        self.assertEqual(loaded.shape, main.Shape.PIPE)
        self.assertEqual(loaded.effects, [main.Effect.SLIPPERY, main.Effect.FRAGILE])
        self.assertEqual(loaded.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(loaded.scorer_amount, 30)
        self.assertEqual(loaded.angle, 90)
        self.assertEqual(loaded.portal_number, 4)
        self.assertEqual(loaded.trigger_limit, 2)
        self.assertEqual(loaded.trigger_paid, 50)
        self.assertEqual(loaded.spin, 45.0)
        self.assertEqual(loaded.triggers_left, 0)

    def test_serialize_block_item_component_and_card_round_trip(self):
        item = main.BlockItem(2, 3, main.Shape.CIRCLE, main.Effect.NONE, main.Scorer.MULT_MUL,
                              1.5, 40, "Circle xMult", trigger_limit=3, trigger_paid=100,
                              effects=[main.Effect.BOUNCY])
        loaded = save_system._deserialize_item(save_system._serialize_item(item))
        self.assertIsInstance(loaded, main.BlockItem)
        self.assertEqual(loaded.col, 2)
        self.assertEqual(loaded.shape, main.Shape.CIRCLE)
        self.assertEqual(loaded.effects, [main.Effect.BOUNCY])
        self.assertEqual(loaded.scorer_amount, 1.5)
        self.assertEqual(loaded.trigger_limit, 3)
        self.assertEqual(loaded.trigger_paid, 100)

        comp = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4, price=20)
        loaded_comp = save_system._deserialize_item(save_system._serialize_item(comp))
        self.assertEqual(loaded_comp.kind, main.Component.SCORER)
        self.assertEqual(loaded_comp.value, main.Scorer.MULT_ADD)
        self.assertEqual(loaded_comp.amount, 4)
        self.assertEqual(loaded_comp.price, 20)

        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        loaded_card = save_system._deserialize_item(save_system._serialize_item(card))
        self.assertIsInstance(loaded_card, main.CardItem)
        self.assertEqual(loaded_card.value, card.value)
        self.assertEqual(loaded_card.price, card.price)

    def test_p_key_saves_to_active_slot(self):
        self.game.save_slot = 1
        self.game.cash = 55555
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                                             main.Scorer.CHIPS_ADD, 30, 50, "Pipe"))
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        self.game.cards.append(card)

        self._press(main.pygame.K_p)

        data = save_system._read_slot(1)
        self.assertIsNotNone(data)
        self.assertEqual(data["cash"], 55555)
        self.assertEqual(len(data["grid"]), 1)
        self.assertEqual(len(data["toolbox"]), 3)  # start + finish + pipe
        self.assertEqual(len(data["cards"]), 1)
        self.assertEqual(data["cards"][0]["value"], card.value)
        self.assertTrue(save_system._slot_has_save(1))

    def test_save_records_required_fields(self):
        self.game.save_slot = 2
        self.game.cash = 777
        self.game.run_number = 5
        self.game.round_index = 1
        self.game.run_in_round = 2
        self.game.required_score = 80
        self.game.run_results = [True, False, True, True, False]
        self.game.runs_cleared = 3
        self.game.failed_runs = 2
        self.game.current_trial = main.Trial.HANDS_TIED

        save_system.save_game(self.game)
        data = save_system._read_slot(2)

        self.assertEqual(data["cash"], 777)
        self.assertEqual(data["run_number"], 5)
        self.assertEqual(data["round_index"], 1)
        self.assertEqual(data["run_in_round"], 2)
        self.assertEqual(data["required_score"], 80)
        self.assertEqual(data["run_results"], [True, False, True, True, False])
        self.assertEqual(data["runs_cleared"], 3)
        self.assertEqual(data["failed_runs"], 2)
        self.assertEqual(data["current_trial"], main.Trial.HANDS_TIED)
        for key in ("toolbox", "grid", "shop", "cards", "actions"):
            self.assertIn(key, data)

    def test_load_slot_restores_state(self):
        self.game.save_slot = 3
        self.game.cash = 4321
        self.game.run_number = 7
        self.game.run_results = [True] * 5 + [False, True]
        self.game.runs_cleared = 6
        self.game.failed_runs = 1
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game.grid[(1, 2)] = main.Block(1, 2, shape=main.Shape.DRAIN,
                                            scorer=main.Scorer.MULT_ADD, scorer_amount=4)
        self.game.cards.append(_card_item(
            main.match_group_for_shape(main.Shape.PIPE), main.Scorer.MULT_ADD))
        self.game.toolbox.add(main.Component.shape_component(main.Shape.PIPE))
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)

        self.assertEqual(fresh.cash, 4321)
        self.assertEqual(fresh.run_number, 7)
        self.assertEqual(fresh.run_results, [True] * 5 + [False, True])
        self.assertEqual(fresh.runs_cleared, 6)
        self.assertEqual(fresh.failed_runs, 1)
        self.assertEqual(fresh.current_trial, main.Trial.CARD_CUTTER)
        self.assertIn((1, 2), fresh.grid)
        self.assertEqual(fresh.grid[(1, 2)].shape, main.Shape.DRAIN)
        self.assertEqual(len(fresh.cards), 1)
        self.assertEqual(fresh.cards[0].value,
                         main.match_group_card(
                             main.match_group_for_shape(main.Shape.PIPE),
                             main.Scorer.MULT_ADD))
        self.assertTrue(any(i.kind == main.Component.SHAPE for i in fresh.toolbox.items))
        self.assertEqual(fresh.save_slot, 3)
        self.assertFalse(fresh.run_active)

    def test_board_unlock_state_saves_and_loads(self):
        # A new game locks the board to the centered 2x3; squares unlocked in
        # the shop and Board Units still in hand persist through a save/load
        # instead of snapping back to a fully-unlocked board.
        save_system.start_new_game_in_slot(self.game, 4)
        self.assertTrue(self.game.is_cell_locked(0, 0))
        self.game._unlock_cell(0, 0)
        self.game._unlock_cell(9, 14)
        self.game.board_units = 2
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        self.assertEqual(len(data["unlocked_cells"]), len(self.game.unlocked_cells))
        self.assertEqual(data["board_units"], 2)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)

        # The partially-unlocked board (and the units in hand) come back intact.
        self.assertFalse(fresh.is_cell_locked(0, 0))
        self.assertFalse(fresh.is_cell_locked(9, 14))
        self.assertTrue(fresh.is_cell_locked(4, 5))  # still locked after load
        self.assertTrue(fresh.is_cell_locked(0, 1))  # never unlocked, still locked
        self.assertEqual(fresh.unlocked_cells, self.game.unlocked_cells)
        self.assertEqual(fresh.board_units, 2)
        # Locked squares act as walls again around the restored region.
        fresh._board_walls_dirty = True
        wall_cells = {(w.x, w.y) for w in fresh._board_wall_blocks()}
        self.assertNotIn((0, 0), wall_cells)
        self.assertIn((4, 5), wall_cells)

    def test_a_loaded_save_keeps_its_pairing_numbers_out_of_new_pairs(self):
        # A pairing number is handed out by a counter that lives in the running
        # game while the numbers themselves live in the save, so a pair built
        # after a reload used to be given a number the loaded board already had:
        # one key then opened the locks of BOTH pairs (and, as the collisions
        # piled up over reloads, every key opened every lock).
        self.game.toolbox.items.clear()
        self.game.grid[(1, 1)] = main.Block(1, 1, shape=main.Shape.KEY,
                                            key_number=1)
        self.game.grid[(2, 1)] = main.Block(2, 1, shape=main.Shape.LOCK,
                                            key_number=1)
        self.game.grid[(3, 1)] = main.Block(
            3, 1, effect=main.Effect.PORTAL, portal_number=1,
            effects=[main.Effect.PORTAL])
        self.game.save_slot = 5
        save_system.save_game(self.game)

        main._next_key_number = 0     # what a brand-new process starts from
        main._next_portal_number = 0  # ...for portals too

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 5)

        # The loaded board has claimed its numbers, so the next pair (and the
        # next portal pair) is given fresh ones.
        fresh.toolbox.items.clear()
        fresh.cash = 1000
        fresh._buy_shop_item(main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                                            main.Scorer.NONE, 0, 10, "Key Block"))
        halves = [i for i in fresh.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual(len(halves), 2)
        self.assertGreater(halves[0].key_number, 1)
        self.assertGreater(main.next_portal_number(), 1)

        # So passing through the new key leaves the loaded lock shut.
        number = halves[0].key_number
        new_key = main.Block(5, 5, shape=main.Shape.KEY, key_number=number)
        new_lock = main.Block(5, 7, shape=main.Shape.LOCK, key_number=number)
        fresh.grid[(5, 5)] = new_key
        fresh.grid[(5, 7)] = new_lock
        fresh.run_active = True
        marble = main.Marble(new_key.rect.centerx, new_key.rect.centery)
        fresh.marbles = [marble]
        marble.collisions_this_tick = [new_key]
        fresh._handle_block_contacts([new_key])

        self.assertFalse(new_lock.locked)          # its own lock opened
        self.assertTrue(fresh.grid[(2, 1)].locked)  # the loaded one did not

    def test_loading_a_board_whose_pairs_share_a_number_splits_them(self):
        # The symptom the collision above produces in a real save: two keys and
        # two locks all numbered 1, so any key opened every lock. Loading such a
        # board re-pairs it — one key and one lock keep the old number, the rest
        # are given numbers of their own.
        self.game.toolbox.items.clear()
        self.game.grid.clear()
        for x in (1, 3):
            self.game.grid[(x, 1)] = main.Block(x, 1, shape=main.Shape.KEY,
                                                key_number=1)
            self.game.grid[(x, 2)] = main.Block(x, 2, shape=main.Shape.LOCK,
                                                key_number=1)
        self.game.save_slot = 5
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 5)

        keys = [fresh.grid[(x, 1)] for x in (1, 3)]
        locks = [fresh.grid[(x, 2)] for x in (1, 3)]
        # One key and one lock per number, and the pair that keeps the original
        # number is the one nearest the board's top-left (so the split is the
        # same every load).
        self.assertEqual(sorted(k.key_number for k in keys),
                         sorted(l.key_number for l in locks))
        self.assertEqual(len({k.key_number for k in keys}), 2)
        self.assertEqual(keys[0].key_number, 1)
        self.assertEqual(locks[0].key_number, 1)
        self.assertGreater(keys[1].key_number, 1)

        # Touching the key that kept the old number now opens only its own lock.
        fresh.run_active = True
        marble = main.Marble(keys[0].rect.centerx, keys[0].rect.centery)
        fresh.marbles = [marble]
        marble.collisions_this_tick = [keys[0]]
        fresh._handle_block_contacts([keys[0]])

        self.assertFalse(locks[0].locked)
        self.assertTrue(locks[1].locked)

    def test_a_duplicated_half_keeps_its_pair_number_on_load(self):
        # Recognition deliberately duplicates a half and the copy keeps its
        # number — two keys for one door, or one key that opens two doors. That
        # is not a collision, so loading the board leaves the number alone.
        for extra_shape in (main.Shape.KEY, main.Shape.LOCK):
            self.game.grid.clear()
            self.game.grid[(1, 1)] = main.Block(1, 1, shape=main.Shape.KEY,
                                                key_number=1)
            self.game.grid[(2, 1)] = main.Block(2, 1, shape=main.Shape.LOCK,
                                                key_number=1)
            self.game.grid[(3, 1)] = main.Block(3, 1, shape=extra_shape,
                                                key_number=1)
            fresh = main.Game()
            fresh.title_screen = False
            fresh.trials_enabled = False

            save_system._load_save_data(
                fresh, save_system._save_data(self.game), 5)

            self.assertEqual({fresh.grid[cell].key_number
                              for cell in ((1, 1), (2, 1), (3, 1))}, {1},
                             extra_shape)

    def test_actions_save_and_load(self):
        # Owned actions (with their v1/v2 version) persist with the save.
        self.game.save_slot = 3
        self.game.cash = 5000
        self.game.actions.append(main.ActionItem(main.Action.DEATH, 60))
        self.game.actions.append(main.ActionItem(main.Action.RECOGNITION, 60, version=2))
        save_system.save_game(self.game)
        data = save_system._read_slot(3)
        self.assertEqual(len(data["actions"]), 2)
        self.assertEqual(data["actions"][0]["value"], main.Action.DEATH)
        self.assertEqual(data["actions"][0]["version"], 1)
        self.assertEqual(data["actions"][1]["value"], main.Action.RECOGNITION)
        self.assertEqual(data["actions"][1]["version"], 2)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)
        self.assertEqual(len(fresh.actions), 2)
        self.assertEqual(fresh.actions[0].value, main.Action.DEATH)
        self.assertEqual(fresh.actions[0].version, 1)
        self.assertEqual(fresh.actions[1].value, main.Action.RECOGNITION)
        self.assertEqual(fresh.actions[1].version, 2)

    def test_resource_points_save_and_load(self):
        # Shreds/Rubble/Ideas/Picky points persist with the save, along with
        # free rerolls (granted by Fresh) and bonus shop slots. Parts and
        # Fresh grant immediately, so they save no point banks.
        self.game.save_slot = 3
        self.game.shred_points = 2
        self.game.rubble_points = 3
        self.game.idea_points = 4
        self.game.free_rerolls = 2
        self.game.option_points = 1
        self.game.bonus_slots = 3
        save_system.save_game(self.game)
        data = save_system._read_slot(3)
        self.assertEqual(data["shred_points"], 2)
        self.assertEqual(data["rubble_points"], 3)
        self.assertEqual(data["idea_points"], 4)
        self.assertEqual(data["free_rerolls"], 2)
        self.assertEqual(data["option_points"], 1)
        self.assertEqual(data["bonus_slots"], 3)
        self.assertNotIn("part_points", data)
        self.assertNotIn("fresh_points", data)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)
        self.assertEqual(fresh.shred_points, 2)
        self.assertEqual(fresh.rubble_points, 3)
        self.assertEqual(fresh.idea_points, 4)
        self.assertEqual(fresh.free_rerolls, 2)
        self.assertEqual(fresh.option_points, 1)
        self.assertEqual(fresh.bonus_slots, 3)
        # The shop is synced to show the banked bonus slots on refresh.
        self.assertEqual(fresh.shop.bonus_slots, 3)

    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_condition_component_and_built_card_save_and_load(self):
        # A condition component in the toolbox and a build-only card value
        # round-trip through a save.
        self.game.save_slot = 7
        cond = main.Component.condition_component(main.Condition.SHAPE_PIPE)
        self.game.toolbox.items.append(cond)
        value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 50))
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 7)
        self.assertTrue(any(i.kind == main.Component.CONDITION
                            and i.value == main.Condition.SHAPE_PIPE
                            for i in fresh.toolbox.items))
        self.assertEqual(len(fresh.cards), 1)
        self.assertEqual(fresh.cards[0].value, value)

    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_wrecking_ball_bonus_saves_and_loads(self):
        # The Fragile Breaks (Wrecking Ball) permanent bonuses persist with the
        # save, one per unit scorer.
        self.game.save_slot = 4
        self.game.wrecking_bonus[main.Scorer.MULT_ADD] = 9
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        saved = dict(data["wrecking_bonus"])
        self.assertEqual(saved[main.Scorer.MULT_ADD], 9)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)
        self.assertEqual(fresh.wrecking_bonus[main.Scorer.MULT_ADD], 9)
        self.assertEqual(len(fresh.cards), 1)
        self.assertEqual(fresh.cards[0].value, main.Card.WRECKING_BALL)

    def test_tesseract_bonus_saves_and_loads(self):
        # Tesseract's permanent reroll bonus is a factor: it persists with the
        # save and comes back as 1.0 when the save predates the card.
        self.game.save_slot = 4
        self.game.tesseract_bonus = 1.8
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        self.assertEqual(data["tesseract_bonus"], 1.8)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)
        self.assertEqual(fresh.tesseract_bonus, 1.8)

        del data["tesseract_bonus"]
        fresh.tesseract_bonus = 9.9
        save_system._load_save_data(fresh, data, 4)
        # A save from before the card loads as no bonus at all.
        self.assertEqual(fresh.tesseract_bonus, 1.0)

    def test_spirit_tokens_save_and_load(self):
        # Spirit tokens persist: scorer, amount, the sacrificed block's cell and
        # effects, and how many runs are left (None = permanent).
        self.game.save_slot = 5
        self.game.tokens = [main.ScorerToken(main.Scorer.MULT_ADD, 4,
                                             shape=main.Shape.CIRCLE,
                                             effects=[main.Effect.BOUNCY],
                                             x=3, y=4, runs_left=2),
                            main.ScorerToken(main.Scorer.CASH, 15, runs_left=None)]
        save_system.save_game(self.game)
        data = save_system._read_slot(5)
        self.assertEqual(len(data["tokens"]), 2)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 5)
        self.assertEqual(len(fresh.tokens), 2)
        kept = fresh.tokens[0]
        self.assertEqual(kept.scorer, main.Scorer.MULT_ADD)
        self.assertEqual(kept.scorer_amount, 4)
        self.assertEqual(kept.shape, main.Shape.CIRCLE)
        self.assertEqual(kept.effects, [main.Effect.BOUNCY])
        self.assertEqual((kept.x, kept.y), (3, 4))
        self.assertEqual(kept.runs_left, 2)
        self.assertIsNone(fresh.tokens[1].runs_left)
        # A save from before tokens existed loads with none.
        fresh.tokens = [main.ScorerToken(main.Scorer.CASH, 15)]
        del data["tokens"]
        save_system._load_save_data(fresh, data, 5)
        self.assertEqual(fresh.tokens, [])

    def test_required_scores_are_saved_and_loaded(self):
        # The lazily-grown REQUIRED_SCORES schedule is stored in the save so a
        # loaded game continues the same targets instead of restarting at [1].
        self.game.save_slot = 5
        main.REQUIRED_SCORES[:] = [1, 2, 5]
        self.game.run_number = 2
        self.game.required_score = 5
        save_system.save_game(self.game)
        data = save_system._read_slot(5)
        self.assertEqual(data["required_scores"], [1, 2, 5])

        # A fresh game starts with a clean schedule...
        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        main.REQUIRED_SCORES[:] = [1]
        # ...and loading restores the saved one (module global included).
        save_system.load_slot(fresh, 5)
        self.assertEqual(main.REQUIRED_SCORES, [1, 2, 5])
        self.assertEqual(fresh.required_score, 5)
        # The restored schedule keeps growing from its last value (each run's
        # target doubles the previous one).
        self.assertEqual(main.get_next_required_score(3), 10)
        self.assertEqual(main.REQUIRED_SCORES, [1, 2, 5, 10])
        # Restore the module global so other tests aren't affected.
        main.REQUIRED_SCORES[:] = [1]

    def test_clicking_empty_slot_opens_marble_selection_then_starts(self):
        # A new save asks which marble type to use before starting the game.
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)
        self.assertFalse(game.title_screen)
        self.assertTrue(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        # Pick the 8 ball: the game starts with it and remembers the choice.
        self._click(game.marble_card_rect(1).center)
        self.assertFalse(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        self.assertEqual(game.marble_type, main.MarbleType.EIGHT_BALL)
        self.assertEqual(game.run_number, 0)

    def test_clicking_occupied_slot_confirms_then_loads(self):
        self.game.save_slot = 1
        self.game.cash = 999
        save_system.save_game(self.game)
        fresh = main.Game()
        fresh.title_screen = True
        fresh.trials_enabled = False
        self.game = fresh
        self._click(save_system.slot_rect(0).center)
        self.assertEqual(fresh.slot_confirm_index, 0)
        self._click(save_system.slot_load_button_rect().center)
        self.assertFalse(fresh.title_screen)
        self.assertEqual(fresh.save_slot, 1)
        self.assertEqual(fresh.cash, 999)

    def test_wipe_slot_deletes_save_and_opens_marble_selection(self):
        self.game.save_slot = 1
        self.game.cash = 999
        save_system.save_game(self.game)
        self.assertTrue(save_system._slot_has_save(1))
        fresh = main.Game()
        fresh.title_screen = True
        fresh.trials_enabled = False
        self.game = fresh
        self._click(save_system.slot_rect(0).center)
        self._click(save_system.slot_wipe_button_rect().center)
        self.assertTrue(fresh.marble_selecting)
        self.assertFalse(save_system._slot_has_save(1))  # old save wiped
        # Pick the rubber ball to finish starting the fresh game.
        self._click(fresh.marble_card_rect(2).center)
        self.assertFalse(fresh.marble_selecting)
        self.assertEqual(fresh.save_slot, 1)
        self.assertEqual(fresh.marble_type, main.MarbleType.RUBBER_BALL)
        self.assertEqual(fresh.cash, 60)  # reset to a fresh game

    def test_marble_selection_back_returns_to_title(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)
        self.assertTrue(game.marble_selecting)
        self._click(main.MARBLE_BACK_BUTTON_RECT.center)
        self.assertFalse(game.marble_selecting)
        self.assertTrue(game.title_screen)
        self.assertIsNone(game.save_slot)

    def test_marble_type_saves_and_loads(self):
        # The chosen marble type is one per save and persists with the game.
        self.game.save_slot = 3
        self.game.marble_type = main.MarbleType.EIGHT_BALL
        save_system.save_game(self.game)
        data = save_system._read_slot(3)
        self.assertEqual(data["marble_type"], main.MarbleType.EIGHT_BALL)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)
        self.assertEqual(fresh.marble_type, main.MarbleType.EIGHT_BALL)

    def test_clicking_ping_pong_card_selects_ping_pong(self):
        # The 4th marble-type card (index 3) is the ping-pong ball.
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)
        self.assertTrue(game.marble_selecting)
        self._click(game.marble_card_rect(3).center)
        self.assertFalse(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        self.assertEqual(game.marble_type, main.MarbleType.PING_PONG)

    def test_ping_pong_marble_type_saves_and_loads(self):
        # The chosen ping-pong type persists with the save (one per save).
        self.game.save_slot = 4
        self.game.marble_type = main.MarbleType.PING_PONG
        save_system.save_game(self.game)
        data = save_system._read_slot(4)
        self.assertEqual(data["marble_type"], main.MarbleType.PING_PONG)
        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 4)
        self.assertEqual(fresh.marble_type, main.MarbleType.PING_PONG)

    def test_marble_card_rects_fit_all_types_above_back_button(self):
        # The selection screen stacks every marble type (now 4, incl. the
        # ping-pong ball) above the BACK button / upgrade-toggle rows.
        game = main.Game()
        for i, mt in enumerate(main.MarbleType.ORDER):
            rect = game.marble_card_rect(i)
            self.assertGreater(rect.top, 0)
            self.assertLess(rect.bottom, main.MARBLE_BACK_BUTTON_RECT.top)
            self.assertLess(rect.bottom, main.MARBLE_UPGRADES_TOGGLE_RECT.top)

    def test_title_screen_draws_without_raising(self):
        self.game.save_slot = 1
        save_system.save_game(self.game)
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        game.draw()  # title + save slots
        game.slot_confirm_index = 0
        game.draw()  # confirm panel

    def test_rich_achievement_unlocks_above_1000_cash(self):
        # "Rich": hold more than $1000 in cash at any point in a run.
        self.assertFalse(achievements.is_unlocked("rich"))
        self.game.cash = 1001
        self.game.update()
        self.assertTrue(achievements.is_unlocked("rich"))
        # The unlock pops up at the bottom of the screen.
        self.assertTrue(any(p.title == "Rich" for p in self.game.popups))

    def test_rich_achievement_stays_locked_below_1000(self):
        # Exactly $1000 is NOT more than $1000, so it stays locked.
        self.game.cash = 1000
        self.game.update()
        self.assertFalse(achievements.is_unlocked("rich"))
        self.assertEqual(self.game.popups, [])

    def test_secret_achievement_locked_shows_question_marks(self):
        # Secret achievements hide their description as "???" until unlocked;
        # normal achievements always show their real description.
        secret = achievements.achievement_by_id("how_did_we_get_here")
        rich = achievements.achievement_by_id("rich")
        self.assertTrue(secret.secret)
        self.assertEqual(achievements.display_description(secret), "???")
        self.assertEqual(achievements.display_description(rich), rich.description)

    def test_secret_achievement_reveals_description_after_unlock(self):
        ach = achievements.achievement_by_id("how_did_we_get_here")
        achievements.unlock("how_did_we_get_here")
        self.assertEqual(achievements.display_description(ach), ach.description)

    def test_all_effects_block_unlocks_secret_achievement(self):
        # A single block holding every real effect in the game unlocks the
        # secret achievement (from the grid or the toolbox).
        self.assertFalse(achievements.is_unlocked("how_did_we_get_here"))
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           effects=list(main.Effect.REAL_ORDER))
        self.game.grid[(1, 1)] = block
        self.game.update()
        self.assertTrue(achievements.is_unlocked("how_did_we_get_here"))
        self.assertTrue(any(p.title == "How did we get here?" for p in self.game.popups))

    def test_partial_effects_block_keeps_secret_locked(self):
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           effects=[main.Effect.BOUNCY, main.Effect.PORTAL])
        self.game.grid[(1, 1)] = block
        self.game.update()
        self.assertFalse(achievements.is_unlocked("how_did_we_get_here"))
        self.assertEqual(self.game.popups, [])

    def test_popup_draws_at_bottom_and_clears(self):
        # A queued popup renders without raising and slides away on its own.
        self.game._push_popup("Rich", "Hold more than $1000")
        self.game.draw()
        for _ in range(300):  # ~5s at 60fps > ENTER + HOLD + EXIT
            self.game.update()
        self.assertEqual(self.game.popups, [])

    def test_secret_unlock_popup_shows_real_description(self):
        # Once unlocked, the popup shows the secret's real description.
        ach = achievements.achievement_by_id("how_did_we_get_here")
        achievements.unlock("how_did_we_get_here")
        self.game._show_achievement_popup(ach)
        self.assertTrue(self.game.popups)
        self.assertEqual(self.game.popups[-1].description, ach.description)
        self.game.draw()  # renders with the real description, not "???"

    def test_achievements_tab_opens_and_returns(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(main.ACHIEVEMENTS_BUTTON_RECT.center)
        self.assertTrue(game.achievements_open)
        self.assertFalse(game.title_screen)
        game.draw()  # renders the achievements grid
        self._click(main.ACHIEVEMENTS_RETURN_BUTTON_RECT.center)
        self.assertFalse(game.achievements_open)
        self.assertTrue(game.title_screen)

    def test_achievements_persist_across_games(self):
        # Unlocks are written to the global file and survive a fresh load.
        achievements.unlock("rich")
        achievements.reset()  # drop the in-memory cache
        self.assertTrue(achievements.is_unlocked("rich"))

    def test_game_over_menu_button_returns_to_title(self):
        self.game.game_over = True
        self._click(main.GAME_OVER_MENU_BUTTON_RECT.center)
        self.assertTrue(self.game.title_screen)
        self.assertFalse(self.game.game_over)

    def test_return_to_menu_button_rect_is_bottom_left(self):
        # The play-screen MAIN MENU button lives in the empty bottom-left
        # corner, clear of the board, panels, run dots, and trial box.
        btn = main.RETURN_TO_MENU_BUTTON_RECT
        self.assertTrue(btn.colliderect(
            main.pygame.Rect(0, 0, main.SCREEN_WIDTH, main.SCREEN_HEIGHT)))
        self.assertEqual(btn.bottom, main.SCREEN_HEIGHT)
        self.assertTrue(btn.right < main.MARBLE_BOX_COORDS[0])

    def test_clicking_return_to_menu_button_goes_to_title(self):
        # Clicking the bottom-left MAIN MENU button leaves the play screen,
        # resets the in-memory game, and returns to the title screen.
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.CHIPS_ADD)
        self.game.run_active = True
        self.game.title_screen = False
        self.game.game_over = False
        self._click(main.RETURN_TO_MENU_BUTTON_RECT.center)
        self.assertTrue(self.game.title_screen)
        self.assertFalse(self.game.game_over)
        self.assertFalse(self.game.run_active)
        self.assertEqual(self.game.grid, {})

    def test_return_to_menu_button_renders_on_play_screen(self):
        # The play frame draws the bottom-left MAIN MENU button without raising.
        self.game.title_screen = False
        self.game.game_over = False
        self.game.draw()  # game frame, includes the play-screen menu button

    def test_returning_to_menu_autosaves_the_game(self):
        # Exiting to the main menu from the play screen autosaves the current
        # game to its active slot BEFORE the in-memory state is reset, so
        # loading the slot resumes where the player left off.
        self.game.save_slot = 1
        self.game.cash = 432
        self.game.grid[(2, 2)] = main.Block(2, 2, scorer=main.Scorer.CHIPS_ADD)
        value = main.match_group_card(main.match_group_for_shape(main.Shape.PIPE),
                                      main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(value, 50))
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._return_to_main_menu()
        self.assertTrue(self.game.title_screen)
        self.assertIsNone(self.game.save_slot)
        self.assertEqual(self.game.grid, {})
        # The slot was autosaved with the pre-exit state.
        data = save_system._read_slot(1)
        self.assertEqual(data["cash"], 432)
        self.assertEqual(len(data["grid"]), 1)
        self.assertEqual(len(data["cards"]), 1)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 1)
        self.assertEqual(fresh.cash, 432)
        self.assertEqual(len(fresh.grid), 1)
        self.assertEqual(len(fresh.cards), 1)

    def test_game_over_menu_button_autosaves(self):
        # The game-over MAIN MENU button also autosaves before leaving.
        self.game.save_slot = 2
        self.game.cash = 777
        self.game.run_number = 9
        self.game.game_over = True
        self._click(main.GAME_OVER_MENU_BUTTON_RECT.center)
        self.assertTrue(self.game.title_screen)
        data = save_system._read_slot(2)
        self.assertEqual(data["cash"], 777)
        self.assertEqual(data["run_number"], 9)
        self.assertTrue(data["game_over"])

    def test_return_to_menu_autosaves_cleared_ping_pong_run(self):
        # Regression: starting a run with the ping-pong ball and clearing it
        # stores a run result that used to be a numpy bool (the total score is
        # built from numpy factors); returning to the main menu autosaves that
        # state and used to raise "TypeError: Object of type bool is not JSON
        # serializable". The result must be a native bool and the autosave
        # must succeed and round-trip the run_results.
        self.game.save_slot = 1
        self.game.marble_type = main.MarbleType.PING_PONG
        self.game.marbles = []
        marble = main.Marble(300, 300)
        marble.finished = True
        self.game.marbles.append(marble)
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_chips = 1000000
        self.game.score_mult = 1
        self.game.required_score = 1
        self.game.run_time = main.TIME_IDEAL
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_cleared)
        self.assertIs(type(self.game.run_results[0]), bool)
        # A direct save round-trips that native bool (a numpy bool would raise
        # "Object of type bool is not JSON serializable" here).
        save_system.save_game(self.game)
        self.assertEqual(save_system._read_slot(1)["run_results"], [True])
        # Returning to the main menu autosaves too, but rolls the un-confirmed
        # run back first (mirroring the QUIT autosave and the P key: a run's
        # rewards only stick after a run).
        self.game._return_to_main_menu()  # autosaves; must not raise
        self.assertTrue(self.game.title_screen)
        data = save_system._read_slot(1)
        self.assertEqual(data["run_results"], [])
        self.assertEqual(data["marble_type"], main.MarbleType.PING_PONG)

    def test_game_over_new_button_wipes_and_opens_marble_selection(self):
        # NEW GAME on the game-over screen acts like wiping the save: it clears
        # the save file and shows the marble-selection screen.
        self.game.save_slot = 1
        self.game.cash = 999
        save_system.save_game(self.game)
        self.assertTrue(save_system._slot_has_save(1))
        self.game.run_number = 5
        self.game.game_over = True
        self._click(main.GAME_OVER_NEW_BUTTON_RECT.center)
        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.marble_selecting)
        self.assertEqual(self.game.save_slot, 1)
        self.assertFalse(save_system._slot_has_save(1))  # the old save was wiped

    def test_game_over_continue_button_keeps_playing(self):
        self.game.run_number = 5
        self.game.game_over = True
        self._click(main.GAME_OVER_CONTINUE_BUTTON_RECT.center)
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, 5)  # the board is kept

    def test_continue_on_game_over_never_shows_again(self):
        # Clicking CONTINUE on the game-over screen clears the overlay and sets
        # continue_past_game_over, so a later run's CONTINUE no longer
        # re-triggers the game-over screen for this save.
        self.game.save_slot = 1
        self.game.run_number = 5
        self.game.failed_runs = 3
        self.game.game_over = True
        self._click(main.GAME_OVER_CONTINUE_BUTTON_RECT.center)
        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.continue_past_game_over)
        # Finishing and continuing another (failed) run advances normally
        # instead of showing the game over again.
        main.REQUIRED_SCORES[:] = [1, 2, 5, 12, 29, 70, 170]  # pre-grow for run 6
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game.run_cleared = False
        self.game.failed_runs = 3
        self.game._continue_run()
        main.REQUIRED_SCORES[:] = [1]  # restore the module global
        self.assertFalse(self.game.game_over)
        self.assertEqual(self.game.run_number, 6)
        # The choice persists with the save so a reload keeps it too.
        save_system.save_game(self.game)
        self.assertTrue(save_system._read_slot(1)["continue_past_game_over"])

    def test_game_over_screen_draws_victory_and_defeat(self):
        # Both the victory and defeat game-over overlays render without raising.
        self.game.game_won = True
        self.game.game_over = True
        self.game.draw()
        self.game.game_won = False
        self.game.game_perfect = True
        self.game.game_over_dice_gained = 0
        self.game.draw()

    def test_upgrades_tab_opens_buys_and_returns(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        metagame.add_dice(1000)
        self._click(main.UPGRADES_BUTTON_RECT.center)
        self.assertTrue(game.upgrades_open)
        self.assertFalse(game.title_screen)
        game.draw()  # renders the upgrades tab
        # Buy the +chips upgrade (400 dice): one level, dice reduced.
        self._click(game.upgrade_card_rect(0).center)
        self.assertEqual(metagame.level("chip"), 1)
        self.assertEqual(metagame.chip_bonus(), 30)
        self.assertEqual(metagame.dice(), 1000 - 400)
        # Return to the main menu.
        self._click(main.UPGRADES_BACK_BUTTON_RECT.center)
        self.assertFalse(game.upgrades_open)
        self.assertTrue(game.title_screen)

    def test_upgrades_cannot_buy_without_enough_dice(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        game.upgrades_open = True
        self.assertEqual(metagame.dice(), 0)
        self._click(game.upgrade_card_rect(0).center)
        self.assertEqual(metagame.level("chip"), 0)
        self.assertEqual(metagame.dice(), 0)

    def test_metagame_upgrades_apply_at_run_start(self):
        # Bought upgrades add +chips, +mult, and xMult to every run's start.
        metagame.add_dice(400 + 800 + 1200)
        metagame.buy_upgrade("chip")
        metagame.buy_upgrade("mult")
        metagame.buy_upgrade("xmult")
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_chips, 1 + 30)
        self.assertEqual(self.game.score_mult, (1 + 4) * 1.25)

    def test_metagame_persists_across_reload(self):
        metagame.add_dice(500)
        metagame.buy_upgrade("chip")  # 400 dice -> level 1
        metagame.reset()  # drop the in-memory cache; reloads from the file
        self.assertEqual(metagame.dice(), 100)
        self.assertEqual(metagame.level("chip"), 1)
        self.assertEqual(metagame.chip_bonus(), 30)

    def test_marble_selection_upgrade_toggle_defaults_on_and_toggles_off(self):
        # The marble-selection screen defaults to upgrade effects ON and lets
        # the player turn them off for the new save (persisted with it).
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(save_system.slot_rect(0).center)  # open marble selection
        self.assertTrue(game.marble_selecting)
        self.assertTrue(game.upgrades_enabled)  # on by default
        self._click(main.MARBLE_UPGRADES_TOGGLE_RECT.center)
        self.assertFalse(game.upgrades_enabled)  # toggled off
        self._click(game.marble_card_rect(0).center)  # pick a marble
        self.assertFalse(game.marble_selecting)
        self.assertEqual(game.save_slot, 1)
        self.assertFalse(game.upgrades_enabled)  # survives the game start

    def test_upgrades_enabled_false_skips_meta_bonuses(self):
        metagame.add_dice(400)
        metagame.buy_upgrade("chip")  # +30 chips are available
        self.game.upgrades_enabled = False
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_chips, 1)  # no +30 bonus
        self.assertEqual(self.game.score_mult, 1)

    def test_upgrades_enabled_saves_and_loads(self):
        self.game.save_slot = 2
        self.game.upgrades_enabled = False
        save_system.save_game(self.game)
        data = save_system._read_slot(2)
        self.assertIs(data["upgrades_enabled"], False)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 2)
        self.assertFalse(fresh.upgrades_enabled)

    def test_collection_tab_opens_and_returns(self):
        game = main.Game()
        game.title_screen = True
        game.trials_enabled = False
        self.game = game
        self._click(main.COLLECTION_BUTTON_RECT.center)
        self.assertTrue(game.collection_open)
        self.assertFalse(game.title_screen)
        game.draw()  # renders the collection grid
        self._click(main.COLLECTION_BACK_BUTTON_RECT.center)
        self.assertFalse(game.collection_open)
        self.assertTrue(game.title_screen)

    def test_discovering_card_adds_to_collection_and_pops(self):
        # Buying an indivisible card (Blueprint) reveals it in the collection
        # and pops it up (splittable cards instead reveal their halves).
        self.game.cash = 1000
        card = main.CardItem(main.Card.BLUEPRINT, 42)
        self.assertFalse(collection.is_card_discovered(main.Card.BLUEPRINT))
        self.game._buy_shop_item(card)
        self.assertTrue(collection.is_card_discovered(main.Card.BLUEPRINT))
        self.assertTrue(any(p.title == "New card" and p.description == "Blueprint"
                            for p in self.game.popups))

    def test_discovering_block_reveals_its_components(self):
        # Buying a block reveals the shape/effect/scorer pieces it is made of.
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Pipe +Chips",
                               effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertFalse(collection.is_component_discovered(
            main.Component.SHAPE, main.Shape.PIPE))
        self.game.cash = 1000
        self.game._buy_shop_item(block)
        self.assertTrue(collection.is_component_discovered(
            main.Component.SHAPE, main.Shape.PIPE))
        self.assertTrue(collection.is_component_discovered(
            main.Component.EFFECT, main.Effect.BOUNCY))
        self.assertTrue(collection.is_component_discovered(
            main.Component.SCORER, main.Scorer.CHIPS_ADD))

    def test_undiscovered_entries_show_question_marks(self):
        # Locked collection entries show "???" for name and description. Only
        # the two run-role scorers (Start/Finish) are revealed to begin with —
        # they are reported as known without being written to the file, since
        # every game hands the player those two blocks; everything else stays
        # hidden on a fresh game.
        entries = self.game._collection_entries()
        self.assertTrue(entries)  # every card/component/trial is listed
        self.assertTrue(all(name == "???" and desc == "???"
                            for _, _, name, desc, _, d in entries if not d))
        self.assertTrue(any(not d for _, _, _, _, _, d in entries))  # most are hidden
        revealed = [(kind, value) for kind, value, _, _, _, d in entries if d]
        self.assertEqual(revealed,
                         [("scorer", main.Scorer.START), ("scorer", main.Scorer.FINISH)])

    def test_trial_discovered_on_cleared_run(self):
        # Beating a run with a trial reveals it in the collection.
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.game.marbles[0].finished = True
        self.game.required_score = 1
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(collection.is_trial_discovered(main.Trial.DEAD_ZONE))
        self.assertTrue(any(p.title == "New trial" for p in self.game.popups))

    def test_collection_persists_across_reload(self):
        value = main.match_group_card(main.match_group_for_shape(main.Shape.PIPE),
                                      main.Scorer.MULT_ADD)
        collection.discover_card(value)
        collection.reset()  # drop the in-memory cache
        self.assertTrue(collection.is_card_discovered(value))


class PlayerDataPathTests(unittest.TestCase):
    """Player data belongs inside profiles/ — never beside main.py."""

    def test_no_player_data_defaults_to_the_game_folder(self):
        # A stray collection.json used to appear in the game folder every time
        # the suite ran: the modules defaulted to paths beside main.py, and
        # building a Game (which the tests do constantly) wrote to them before
        # any profile was active. Every default must live under profiles/.
        profiles_root = profiles.PROFILES_DIR + os.sep
        for label, path in (("achievements", achievements.FILE_PATH),
                            ("collection", collection.FILE_PATH),
                            ("metagame", metagame.FILE_PATH),
                            ("saves", save_system.SAVES_DIR)):
            self.assertTrue(path.startswith(profiles_root), (label, path))
            self.assertEqual(os.path.dirname(path),
                             os.path.join(profiles_root, profiles.DEFAULT_PROFILE),
                             label)

    def test_building_a_game_writes_no_player_json(self):
        # Constructing a Game is not a player action, so it must not write the
        # collection/achievements/metagame files (it only creates the empty
        # save-slot placeholders, and those live in profiles/ too).
        tmp = tempfile.mkdtemp()
        old_files = (achievements.FILE_PATH, collection.FILE_PATH,
                     metagame.FILE_PATH, save_system.SAVES_DIR)
        try:
            achievements.FILE_PATH = os.path.join(tmp, "achievements.json")
            collection.FILE_PATH = os.path.join(tmp, "collection.json")
            metagame.FILE_PATH = os.path.join(tmp, "metagame.json")
            save_system.SAVES_DIR = os.path.join(tmp, "saves")
            achievements.reset()
            collection.reset()
            metagame.reset()

            main.Game()

            written = os.listdir(tmp)
            self.assertEqual([name for name in written if name.endswith(".json")],
                             [])
            # ...and the run roles still read as known, with no write needed.
            self.assertTrue(collection.is_component_discovered(
                main.Component.SCORER, main.Scorer.START))
            self.assertTrue(collection.is_component_discovered(
                main.Component.SCORER, main.Scorer.FINISH))
        finally:
            (achievements.FILE_PATH, collection.FILE_PATH,
             metagame.FILE_PATH, save_system.SAVES_DIR) = old_files
            achievements.reset()
            collection.reset()
            metagame.reset()
            shutil.rmtree(tmp, ignore_errors=True)


class ProfileTests(unittest.TestCase):
    """Profile folders: migration of the legacy root data into profile_1,
    per-profile isolation of the saves/achievements/collection/metagame files,
    and the title-screen switcher (button -> expandable list -> '+' name
    prompt)."""

    def setUp(self):
        # Isolate every file the profile system can touch under one temp dir.
        self._tmp = tempfile.mkdtemp()
        self._old_game_dir = profiles.GAME_DIR
        self._old_profiles_dir = profiles.PROFILES_DIR
        profiles.GAME_DIR = self._tmp
        profiles.PROFILES_DIR = os.path.join(self._tmp, "profiles")
        self._old_saves_dir = save_system.SAVES_DIR
        save_system.SAVES_DIR = self._tmp
        self._old_ach_file = achievements.FILE_PATH
        achievements.FILE_PATH = os.path.join(self._tmp, "achievements.json")
        achievements.reset()
        self._old_meta_file = metagame.FILE_PATH
        metagame.FILE_PATH = os.path.join(self._tmp, "metagame.json")
        metagame.reset()
        self._old_collection_file = collection.FILE_PATH
        collection.FILE_PATH = os.path.join(self._tmp, "collection.json")
        collection.reset()
        self.game = main.Game()
        self.game.title_screen = False
        self.game.trials_enabled = False

    def tearDown(self):
        profiles.GAME_DIR = self._old_game_dir
        profiles.PROFILES_DIR = self._old_profiles_dir
        save_system.SAVES_DIR = self._old_saves_dir
        achievements.FILE_PATH = self._old_ach_file
        achievements.reset()
        metagame.FILE_PATH = self._old_meta_file
        metagame.reset()
        collection.FILE_PATH = self._old_collection_file
        collection.reset()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_json(self, folder, name, data):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _click(self, pos):
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def _key(self, key, unicode=""):
        event = mock.Mock()
        event.type = main.pygame.KEYDOWN
        event.key = key
        event.unicode = unicode
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

    def test_migrate_moves_legacy_root_data_into_profile_1(self):
        # A fake pre-profile layout at the game root: the shared saves folder
        # plus the three global json files.
        self._write_json(self._tmp, "achievements.json", {"unlocked": ["rich"]})
        self._write_json(self._tmp, "collection.json",
                         {"cards": [main.match_group_card(
                             main.match_group_for_shape(main.Shape.PIPE),
                             main.Scorer.MULT_ADD)]})
        self._write_json(self._tmp, "metagame.json", {"dice": 5})
        os.makedirs(os.path.join(self._tmp, "saves"))
        for slot in range(1, 7):
            self._write_json(os.path.join(self._tmp, "saves"),
                             f"save{slot}.txt", {"cash": slot * 10})

        profiles.migrate_legacy()

        p1 = os.path.join(profiles.PROFILES_DIR, "profile_1")
        self.assertTrue(os.path.isfile(os.path.join(p1, "achievements.json")))
        self.assertTrue(os.path.isfile(os.path.join(p1, "collection.json")))
        self.assertTrue(os.path.isfile(os.path.join(p1, "metagame.json")))
        self.assertTrue(os.path.isfile(os.path.join(p1, "saves", "save1.txt")))
        # The legacy root copies are gone and the pointer names profile_1.
        self.assertFalse(os.path.exists(os.path.join(self._tmp, "saves")))
        self.assertFalse(os.path.exists(
            os.path.join(self._tmp, "achievements.json")))
        self.assertEqual(profiles.current_profile(), "profile_1")

    def test_profiles_isolate_saves_and_meta_progress(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.save_slot = 1
        self.game.cash = 321
        save_system.save_game(self.game)
        self.assertTrue(achievements.unlock("rich"))
        self.assertTrue(save_system._slot_has_save(1))

        # A brand-new profile starts empty and isolated.
        profiles.create_profile("Second")
        self.assertEqual(profiles.current_profile(), "Second")
        self.assertTrue(os.path.isdir(os.path.join(profiles.PROFILES_DIR,
                                                   "Second")))
        self.assertFalse(achievements.is_unlocked("rich"))
        self.assertFalse(save_system._slot_has_save(1))

        # Switching back to profile_1 brings its data back.
        profiles.switch_to("profile_1")
        self.assertTrue(achievements.is_unlocked("rich"))
        self.assertTrue(save_system._slot_has_save(1))

    def test_create_profile_names_folder_and_points_modules(self):
        profiles.migrate_legacy()
        created = profiles.create_profile("Adrian")
        self.assertEqual(created, "Adrian")
        self.assertEqual(profiles.current_profile(), "Adrian")
        # The save folder has the 6 empty slot placeholders.
        for slot in range(1, 7):
            self.assertTrue(os.path.isfile(os.path.join(
                profiles.PROFILES_DIR, "Adrian", "saves", f"save{slot}.txt")))
        # The persistence modules now point into the new profile.
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "Adrian", "saves"))
        self.assertEqual(achievements.FILE_PATH,
                         os.path.join(profiles.PROFILES_DIR, "Adrian",
                                      "achievements.json"))
        # A repeated name is uniquified instead of overwriting.
        self.assertEqual(profiles.create_profile("Adrian"), "Adrian 2")
        self.assertEqual(profiles.unique_name("A/B?"), "A B")

    def test_profile_button_expands_and_plus_creates_named_profile(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True

        self._click(main.PROFILE_BUTTON_RECT.center)
        self.assertTrue(self.game.profile_menu_open)

        _panel, _rows, plus = main.ui.profile_menu_geometry(
            profiles.list_profiles())
        self._click(plus.center)
        self.assertTrue(self.game.profile_naming)
        self.assertFalse(self.game.profile_menu_open)

        for ch in "Neo":
            self._key(main.pygame.K_a, ch)
        self._key(main.pygame.K_RETURN, "")
        self.assertFalse(self.game.profile_naming)
        self.assertFalse(self.game.profile_menu_open)
        self.assertEqual(profiles.current_profile(), "Neo")
        self.assertTrue(os.path.isdir(os.path.join(profiles.PROFILES_DIR,
                                                   "Neo")))
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "Neo", "saves"))
        # The brand-new profile has no real saves yet.
        self.assertFalse(save_system._slot_has_save(1))

    def test_clicking_a_profile_row_switches_profiles(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # now active
        self.game.title_screen = True

        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        target = names.index("profile_1")
        self._click(rows[target].center)

        self.assertFalse(self.game.profile_menu_open)
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "profile_1", "saves"))

    def test_blank_name_does_not_create_and_escape_cancels(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        _panel, _rows, plus = main.ui.profile_menu_geometry(
            profiles.list_profiles())
        self._click(plus.center)

        # Enter with no typed name keeps the prompt open (nothing created).
        self._key(main.pygame.K_RETURN, "")
        self.assertTrue(self.game.profile_naming)
        self.assertEqual(profiles.current_profile(), "profile_1")

        # Escape abandons the prompt and returns to the profile list.
        self._key(main.pygame.K_ESCAPE, "")
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)

    def test_title_screen_draws_profile_ui_without_raising(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")
        self.game.title_screen = True
        self.game.profile_menu_open = True
        self.game.draw()
        self.game.profile_naming = True
        self.game.profile_name_text = "Test"
        self.game.draw()
        self.game.profile_naming = False
        self.game.profile_menu_open = False
        self.game.draw()

    def test_rename_profile_renames_folder_pointer_and_modules(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        old_dir = profiles.profile_dir("profile_1")
        result = profiles.rename_profile("profile_1", "Main")
        self.assertEqual(result, "Main")
        self.assertFalse(os.path.isdir(old_dir))
        self.assertTrue(os.path.isdir(profiles.profile_dir("Main")))
        self.assertEqual(profiles.current_profile(), "Main")
        # The persistence modules now point at the renamed folder.
        self.assertEqual(save_system.SAVES_DIR,
                         os.path.join(profiles.PROFILES_DIR, "Main", "saves"))
        self.assertEqual(achievements.FILE_PATH,
                         os.path.join(profiles.PROFILES_DIR, "Main",
                                      "achievements.json"))

    def test_rename_profile_dedupes_and_same_name_is_noop(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second
        # Renaming Second to a name another profile (profile_1) uses is
        # deduped with a numeric suffix instead of clobbering the other folder.
        self.assertEqual(profiles.rename_profile("Second", "profile_1"),
                         "profile_1 2")
        self.assertEqual(profiles.current_profile(), "profile_1 2")
        # Renaming a profile to its own current name is a no-op.
        self.assertEqual(profiles.rename_profile("profile_1", "profile_1"),
                         "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_delete_active_profile_activates_a_remaining_one(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Zeta")  # active Zeta
        profiles.delete_profile("Zeta")
        self.assertFalse(os.path.isdir(profiles.profile_dir("Zeta")))
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_delete_last_profile_recreates_fresh_profile_1(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")  # the only profile
        self.game.save_slot = 1
        self.game.cash = 50
        save_system.save_game(self.game)
        self.assertTrue(save_system._slot_has_save(1))
        profiles.delete_profile("profile_1")
        # profile_1 is recreated, empty (its old data was removed with it).
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))
        self.assertFalse(save_system._slot_has_save(1))

    def test_delete_profile_handles_readonly_folder(self):
        # OneDrive marks profile folders read-only (no write bit on Windows),
        # which used to make shutil.rmtree silently fail so the folder survived
        # and the delete appeared to do nothing. Clearing the flag first must
        # let the folder actually go.
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second
        # Make Second read-only (OneDrive style).
        for root, dirs, files in os.walk(profiles.profile_dir("Second")):
            os.chmod(root, 0o555)
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o555)
            for f in files:
                os.chmod(os.path.join(root, f), 0o555)
        self.assertTrue(profiles.delete_profile("Second"))
        self.assertFalse(os.path.isdir(profiles.profile_dir("Second")))
        # The game settles on the remaining profile_1.
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_clicking_active_profile_row_opens_rename_popup(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        # The active profile's row opens its edit popup (pre-filled), not a switch.
        self.assertTrue(self.game.profile_naming)
        self.assertTrue(self.game.profile_renaming)
        self.assertFalse(self.game.profile_menu_open)
        self.assertEqual(self.game.profile_name_text, "profile_1")
        # Clear the pre-filled name, type a new one, and press Enter.
        for _ in range(len("profile_1")):
            self._key(main.pygame.K_BACKSPACE, "")
        for ch in "Main":
            self._key(main.pygame.K_a, ch)
        self._key(main.pygame.K_RETURN, "")
        self.assertFalse(self.game.profile_naming)
        self.assertEqual(profiles.current_profile(), "Main")
        self.assertTrue(os.path.isdir(profiles.profile_dir("Main")))

    def test_delete_button_confirms_then_deletes_active_profile(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        self.assertTrue(self.game.profile_renaming)
        # First Delete click asks for confirmation...
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertTrue(self.game.profile_delete_confirm)
        self.assertTrue(self.game.profile_naming)
        # ...and the second Delete click removes it. It was the only profile,
        # so a fresh profile_1 is recreated in its place.
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertFalse(self.game.profile_naming)
        self.assertFalse(self.game.profile_renaming)
        self.assertFalse(self.game.profile_delete_confirm)
        self.assertEqual(profiles.current_profile(), "profile_1")
        self.assertTrue(os.path.isdir(profiles.profile_dir("profile_1")))

    def test_keep_returns_to_rename_field_and_esc_closes(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second (two profiles exist)
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("Second")].center)
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertTrue(self.game.profile_delete_confirm)
        # Keep (bottom-right) returns to the rename field without deleting.
        self._click(main.ui.profile_name_cancel_rect().center)
        self.assertFalse(self.game.profile_delete_confirm)
        self.assertTrue(self.game.profile_naming)
        self.assertTrue(self.game.profile_renaming)
        self.assertEqual(profiles.current_profile(), "Second")
        self.assertTrue(os.path.isdir(profiles.profile_dir("Second")))
        # Esc closes the popup back to the profile list.
        self._key(main.pygame.K_ESCAPE, "")
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)

    def test_edit_and_delete_popups_draw_without_raising(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        profiles.create_profile("Second")  # active Second
        self.game.title_screen = True
        self.game.profile_naming = True
        self.game.profile_renaming = True
        self.game.profile_name_text = "Second"
        self.game.draw()  # rename popup (with the Delete button)
        self.game.profile_delete_confirm = True
        self.game.draw()  # inline delete confirm
        self.game.profile_naming = False
        self.game.profile_renaming = False
        self.game.profile_delete_confirm = False
        self.game.draw()

    def test_unlock_collection_button_confirms_then_unlocks_and_disables(self):
        # The rename popup's Unlock-collection button (center-bottom) asks for
        # confirmation; confirming reveals every collection entry and
        # disables achievements for the profile.
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        self.assertTrue(self.game.profile_renaming)
        # A brand-new profile has plenty of undiscovered entries.
        self.assertTrue(any(not e[5] for e in self.game._collection_entries()))
        # First click asks for confirmation (like Delete does)...
        self._click(main.ui.profile_name_unlock_rect().center)
        self.assertTrue(self.game.profile_unlock_confirm)
        self.assertTrue(self.game.profile_naming)
        # ...the confirm's Unlock (the bottom-left action rect) reveals
        # everything and turns achievements off.
        self._click(main.ui.profile_name_delete_rect().center)
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)
        self.assertTrue(all(e[5] for e in self.game._collection_entries()))
        self.assertTrue(achievements.is_disabled())
        self.assertFalse(achievements.unlock("rich"))  # blocked now

    def test_unlock_confirm_keep_does_nothing(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self._click(main.PROFILE_BUTTON_RECT.center)
        names = profiles.list_profiles()
        _panel, rows, _plus = main.ui.profile_menu_geometry(names)
        self._click(rows[names.index("profile_1")].center)
        self._click(main.ui.profile_name_unlock_rect().center)
        self.assertTrue(self.game.profile_unlock_confirm)
        # Keep (bottom-right) backs out without unlocking or disabling.
        self._click(main.ui.profile_name_cancel_rect().center)
        self.assertFalse(self.game.profile_unlock_confirm)
        self.assertTrue(self.game.profile_naming)
        self.assertTrue(self.game.profile_renaming)
        self.assertFalse(achievements.is_disabled())
        self.assertTrue(any(not e[5] for e in self.game._collection_entries()))
        # Esc still returns to the profile list.
        self._key(main.pygame.K_ESCAPE, "")
        self.assertFalse(self.game.profile_naming)
        self.assertTrue(self.game.profile_menu_open)

    def test_achievement_disabled_flag_is_per_profile(self):
        # Disabling achievements on one profile must not affect another, and it
        # survives switching back (persisted in the profile's achievements.json).
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        achievements.disable()
        self.assertTrue(achievements.is_disabled())
        self.assertFalse(achievements.unlock("rich"))
        # A second profile still has achievements enabled.
        second = profiles.create_profile("Second")
        self.assertEqual(profiles.current_profile(), second)
        self.assertFalse(achievements.is_disabled())
        self.assertTrue(achievements.unlock("rich"))
        # Switching back to profile_1 re-reads its disabled flag.
        profiles.switch_to("profile_1")
        self.assertTrue(achievements.is_disabled())

    def test_unlock_collection_popup_draws_without_raising(self):
        profiles.migrate_legacy()
        profiles.switch_to("profile_1")
        self.game.title_screen = True
        self.game.profile_naming = True
        self.game.profile_renaming = True
        self.game.profile_name_text = "profile_1"
        self.game.draw()  # rename popup (with the Unlock-collection button)
        self.game.profile_unlock_confirm = True
        self.game.draw()  # inline unlock-collection confirm
        self.game.profile_unlock_confirm = False
        self.game.profile_delete_confirm = True
        self.game.draw()  # delete confirm still draws in the taller popup
        self.game.profile_delete_confirm = False
        self.game.profile_naming = False
        self.game.profile_renaming = False
        self.game.draw()
