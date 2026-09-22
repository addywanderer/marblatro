"""Blocks: shapes, effects, triggers, portals, keys and locks.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class BlocksTests(GameTestCase):
    """Blocks: shapes, effects, triggers, portals, keys and locks."""


    def test_slope_effect_adds_mult_on_contact(self):
        block = main.Block(0, 0, shape=main.Shape.SLOPE, scorer=main.Scorer.MULT_ADD)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True

        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 5)
        self.assertEqual(self.game.score_chips, 0)


    def test_scoring_block_triggers_only_once_per_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        marble = self._add_marble()
        self.game.run_active = True

        # First touch (block is new this tick) -> triggers once.
        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 30)
        self.assertEqual(block.triggers_left, 0)

        # Still touching (block in both last and this tick) -> no retrigger.
        marble.collisions_last_tick = [block]
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 30)

        # Marble releases, then re-touches: the block is exhausted for the run,
        # so it does NOT score again.
        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 30)


    def test_none_shape_block_scores_when_marble_passes_through_cell(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(5, 8)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.centery))
        self.game.run_active = True

        # Entering the cell triggers the scorer once.
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 30)

        # Still inside the cell: no retrigger.
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 30)


    def test_fast_marble_scores_on_none_shape_field(self):
        # A 3000px/s marble crosses the whole 40px field cell within one frame;
        # path sampling must register the contact so the scorer still fires.
        block = main.Block(5, 7, shape=main.Shape.NONE, effect=main.Effect.NONE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(5, 7)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.top - 5))
        marble.velocity = np.array([0.0, 3000.0])
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 10)  # no longer phases through
        self.assertEqual(block.triggers_left, 0)


    def test_none_shape_block_does_not_score_outside_cell(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(5, 8)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.top - 40))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 0)


    def test_none_shape_block_does_not_retrigger_after_leaving_cell(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(5, 8)] = block
        marble = self._add_marble((block.rect.centerx, block.rect.centery))
        self.game.run_active = True
        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 30)

        # Move fast leftward out of the cell, then back in: the block is already
        # exhausted for this run, so it does not score again.
        marble.position = np.array([block.rect.right + 60.0, block.rect.centery], dtype=float)
        marble.velocity = np.array([-600.0, 0.0])
        for _ in range(20):
            marble.physics.update(marble, main.DT, list(self.game.grid.values()))
            self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 30)


    def test_trigger_limit_resets_each_run(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(0, 0)] = block
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        block.triggers_left = 0  # used up during a run

        self.assertTrue(self.game.reset_run())

        self.assertEqual(block.triggers_left, block.trigger_limit)


    def test_moving_broken_fragile_block_restores_original_shape(self):
        # A fragile block that shattered (shape -> NONE) keeps its original
        # shape in _fragile_shape; selecting and moving it must come back as
        # that shape, not a permanent Shape.NONE.
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        block.shape = main.Shape.NONE  # shattered during a run
        block._fragile_shape = main.Shape.RECT
        self.game.grid[(2, 3)] = block

        # Selecting the broken block equips its original shape for moving.
        self._click(self._grid_pos(2, 3))
        self.assertEqual(self.game.selected_shape, main.Shape.RECT)

        # Move it to a new cell.
        self._click(self._grid_pos(4, 4))

        moved = self.game.grid.get((4, 4))
        self.assertIsNotNone(moved)
        self.assertEqual(moved.shape, main.Shape.RECT)  # not NONE
        self.assertIsNone(moved._fragile_shape)  # unbroken, ready to shatter again
        self.assertNotIn((2, 3), self.game.grid)  # original cell emptied


    def test_block_borders_can_be_toggled_off(self):
        # BLOCK_BORDERS_ON controls the 3px outline (WHITE normally, RED once a
        # block is triggered). Off means no border is drawn at all, and an
        # exhausted block shows its used state by turning its INTERIOR red
        # instead of a red border.
        block = main.Block(0, 0, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        border_px = (1, main.GRID_SIZE // 2)
        try:
            main.BLOCK_BORDERS_ON = True
            block.draw(surface)
            self.assertEqual(surface.get_at(border_px)[:3], main.WHITE)  # border on

            surface.fill((0, 0, 0))
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            self.assertEqual(surface.get_at(border_px)[:3], main.BLACK)  # border hidden
            # The block's fill still renders with the border off.
            self.assertEqual(surface.get_at((main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3],
                             main.BLACK)

            block.triggers_left = 0  # triggered; with borders off the interior turns red
            surface.fill((0, 0, 0))
            block.draw(surface)
            self.assertEqual(surface.get_at(border_px)[:3], main.RED)  # interior red
        finally:
            main.BLOCK_BORDERS_ON = True


    def test_finish_block_marks_marble_and_ends_run_when_all_finished(self):
        finish = main.Block(0, 0, scorer=main.Scorer.FINISH)
        marble = self._add_marble()
        marble.collisions_this_tick = [finish]
        self.game.run_active = True

        self.game._handle_block_contacts([finish])

        self.assertTrue(marble.finished)
        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.run_complete)


    def test_run_continues_until_all_marbles_finish(self):
        finish = main.Block(0, 0, scorer=main.Scorer.FINISH)
        first = self._add_marble()
        second = self._add_marble()
        self.game.run_active = True

        first.collisions_this_tick = [finish]
        self.game._handle_block_contacts([finish])

        self.assertTrue(first.finished)
        self.assertFalse(second.finished)
        self.assertTrue(self.game.run_active)

        second.collisions_this_tick = [finish]
        self.game._handle_block_contacts([finish])

        self.assertTrue(second.finished)
        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.run_complete)


    def test_multiple_marbles_can_use_same_finish(self):
        finish = main.Block(0, 0, scorer=main.Scorer.FINISH)
        first = self._add_marble()
        second = self._add_marble()
        self.game.run_active = True

        first.collisions_this_tick = [finish]
        second.collisions_this_tick = [finish]
        self.game._handle_block_contacts([finish])

        self.assertTrue(first.finished)
        self.assertTrue(second.finished)
        self.assertFalse(self.game.run_active)


    def test_restarting_a_run_takes_back_the_cash_its_blocks_paid(self):
        # Cash/Lucky blocks pay into the wallet as they trigger, so restarting
        # the run (R) has to take that cash back out with the run-scoped
        # counter: otherwise resetting a run would be a way to print money.
        self.game.cash = 0
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.run_active = True
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        marble = self._add_marble()
        marble.collisions_this_tick = [cash_block]
        self.game._handle_block_contacts([cash_block])  # +$15
        self.assertEqual(self.game.cash, 15)
        self.assertEqual(self.game.run_cash_gained, 15)

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.run_cash_gained, 0)
        self.assertEqual(self.game.cash, 0)


    def test_restarting_cannot_push_the_wallet_below_zero(self):
        # Cash the discarded run already SPENT is not clawed back — the same
        # rule the free rerolls follow — so a restart never leaves the wallet
        # negative.
        self.game.cash = 0
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.run_active = True
        cash_block = main.Block(0, 0, scorer=main.Scorer.CASH)
        marble = self._add_marble()
        marble.collisions_this_tick = [cash_block]
        self.game._handle_block_contacts([cash_block])  # +$15
        self.game.cash = 0  # already spent again on a shop purchase

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.cash, 0)
        self.assertEqual(self.game.run_cash_gained, 0)


    def test_leaving_before_a_run_finishes_keeps_the_resource_bank(self):
        # The save / quit / MAIN MENU paths call _retry_run() while the player
        # is still building, where there is no finished run to undo: the bench
        # of banked points must survive that.
        self.game.shred_points = 3
        self.game.rubble_points = 1
        self.game.idea_points = 2
        self.game.option_points = 1
        self.game.run_complete = False
        self.game.awaiting_after_run = False
        self.game._retry_run()
        self.assertEqual(self.game.shred_points, 3)
        self.assertEqual(self.game.rubble_points, 1)
        self.assertEqual(self.game.idea_points, 2)
        self.assertEqual(self.game.option_points, 1)


    def test_random_block_keeps_one_reward_for_the_whole_run(self):
        # A Random block's reward is chosen before the run (+35 chips here), so
        # its second trigger pays chips again rather than rolling the xMult the
        # patched draw would have given.
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM, trigger_limit=2)
        self.game.grid[(0, 0)] = block
        self.game.score_chips = 100
        self.game.score_mult = 1
        with mock.patch("main.random.random", return_value=0.0):
            self.game._roll_run_random_outputs()
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 135)
        self.assertEqual(self.game.score_mult, 1)
        self._touch_block(block, 0.9)
        self.assertEqual(self.game.score_chips, 170)
        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(block.triggers_left, 0)


    # --- Key / Lock pairs ---------------------------------------------------

    def test_key_and_lock_shapes_are_defined_and_distinct(self):
        self.assertIn(main.Shape.KEY, main.Shape.ORDER)
        self.assertIn(main.Shape.LOCK, main.Shape.ORDER)
        self.assertEqual(main.Shape.name(main.Shape.KEY), "Key")
        self.assertEqual(main.Shape.name(main.Shape.LOCK), "Lock")
        self.assertNotEqual(main.Shape.KEY, main.Shape.LOCK)
        self.assertIn("Lock", main.shape_description(main.Shape.KEY))
        self.assertIn("solid", main.shape_description(main.Shape.LOCK))
        for shape in (main.Shape.KEY, main.Shape.LOCK):
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)
            self.assertTrue(main.shape_description(shape))


    def test_paired_shape_pairs_only_key_and_lock(self):
        self.assertEqual(main.paired_shape(main.Shape.KEY), main.Shape.LOCK)
        self.assertEqual(main.paired_shape(main.Shape.LOCK), main.Shape.KEY)
        for shape in main.Shape.ORDER:
            if shape not in (main.Shape.KEY, main.Shape.LOCK):
                self.assertIsNone(main.paired_shape(shape))


    def test_touching_a_key_opens_only_its_own_lock(self):
        key_a = main.Block(1, 1, shape=main.Shape.KEY, key_number=1)
        lock_a = main.Block(1, 2, shape=main.Shape.LOCK, key_number=1)
        key_b = main.Block(2, 1, shape=main.Shape.KEY, key_number=2)
        lock_b = main.Block(2, 2, shape=main.Shape.LOCK, key_number=2)
        for block in (key_a, lock_a, key_b, lock_b):
            self.game.grid[(block.x, block.y)] = block
        self.game.run_active = True
        self.assertTrue(lock_a.locked and lock_b.locked)
        marble = self._add_marble()

        marble.collisions_this_tick = [key_a]
        self.game._handle_block_contacts([key_a])

        self.assertFalse(lock_a.locked)   # its own key opened it
        self.assertTrue(lock_b.locked)    # the other pair stays shut


    def test_a_key_with_no_number_opens_nothing(self):
        # A lone key (e.g. one granted at random, like a lone portal) has no
        # number, so it has no lock to open and touching it is harmless.
        key = main.Block(1, 1, shape=main.Shape.KEY, key_number=0)
        lock = main.Block(1, 2, shape=main.Shape.LOCK, key_number=0)
        self.game.grid[(1, 1)] = key
        self.game.grid[(1, 2)] = lock
        self.game.run_active = True
        marble = self._add_marble()

        marble.collisions_this_tick = [key]
        self.game._handle_block_contacts([key])

        self.assertTrue(lock.locked)


    def test_locks_close_again_at_the_start_of_each_run(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        lock = main.Block(1, 1, shape=main.Shape.LOCK, key_number=5)
        self.game.grid[(1, 1)] = lock

        self.game.reset_run()
        self.assertTrue(lock.locked)
        lock.locked = False  # opened by its key mid-run
        self.game.reset_run()
        self.assertTrue(lock.locked)
        self.assertFalse(self.game.run_blocks_destroyed)
        self.assertFalse(self.game.debt_run_triggered)


    def test_a_placed_lock_starts_locked(self):
        block = main.Block(2, 2, shape=main.Shape.LOCK)
        self.assertTrue(block.locked)
        self.assertFalse(main.Block(2, 2, shape=main.Shape.KEY).locked)
        self.assertFalse(main.Block(2, 2, shape=main.Shape.RECT).locked)


    def test_key_numbers_survive_a_save_round_trip(self):
        self.game.toolbox.items.clear()
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key", key_number=4)
        self.game.toolbox.add(key)
        self.game.grid[(1, 1)] = main.Block(1, 1, shape=main.Shape.LOCK,
                                            key_number=4)
        self.game.save_slot = 3
        save_system.save_game(self.game)

        fresh = main.Game()
        fresh.title_screen = False
        fresh.trials_enabled = False
        save_system.load_slot(fresh, 3)

        loaded_lock = fresh.grid[(1, 1)]
        self.assertEqual(loaded_lock.shape, main.Shape.LOCK)
        self.assertEqual(loaded_lock.key_number, 4)
        # A loaded lock is shut again (only a key touch opens it, per run).
        self.assertTrue(loaded_lock.locked)
        keys = [i for i in fresh.toolbox.items
                if getattr(i, "key_number", 0) == 4]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].shape, main.Shape.KEY)


    def test_a_fragile_break_counts_as_a_block_destroyed(self):
        self.game.run_active = True
        self.assertEqual(self.game.run_blocks_destroyed, 0)

        self.game._on_fragile_broken(main.Block(0, 0, effect=main.Effect.FRAGILE))

        self.assertEqual(self.game.run_blocks_destroyed, 1)


    def test_the_rewind_keeps_the_clock_and_the_measurements(self):
        # Only the marbles' motion and the trigger counts go back: the run is
        # simply one second longer, so its clock and its accumulated
        # measurements keep the values they had when the run finished.
        marble, _block = self._start_procrastination_run()
        frames = 0
        while not self.game.procrastination_used and frames < 300:
            clock, travelled = self.game.run_time, marble.distance
            self.game.update()
            frames += 1

        self.assertGreater(self.game.run_time, clock)
        self.assertGreaterEqual(marble.distance, travelled)


    def test_a_bought_pair_keeps_its_effect_magnitudes(self):
        # Regression: a portal (or key/lock) block is bought as a hand-built
        # pair, and both halves used to lose the offer's effect magnitudes.
        for shape, effects in ((main.Shape.RECT, [main.Effect.PORTAL,
                                                  main.Effect.PISTON]),
                               (main.Shape.KEY, [main.Effect.PISTON])):
            with self.subTest(shape=main.Shape.name(shape)):
                self.game.toolbox.items.clear()
                self.game.cash = 1000
                item = main.BlockItem(0, 0, shape, main.Effect.NONE,
                                      main.Scorer.CHIPS_ADD, 30, 40, "pair",
                                      effects=effects,
                                      effect_amounts={main.Effect.PISTON: 2100})

                self.game._buy_shop_item(item)

                halves = [i for i in self.game.toolbox.items
                          if getattr(i, "kind", None) == "block"]
                self.assertEqual(len(halves), 2)
                for half in halves:
                    self.assertEqual(half.effect_magnitude(main.Effect.PISTON), 2100)


    # --- Start/Finish blocks are ordinary goods, except the last one -------

    def test_the_last_start_and_finish_blocks_cannot_be_sold(self):
        # One Start block and one Finish block are required to run at all, so
        # the LAST of each is refused even though the shop sells the roles now.
        self.game.toolbox.items.clear()
        start = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 0, "Start")
        finish = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.FINISH, 0, 0, "Finish")
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 20, "Plain")
        for item in (start, finish, plain):
            self.game.toolbox.add(item)
        self.game.cash = 0

        for role in (start, finish):
            self.game._equip_block(role)
            self.game._sell_selected_item()
            self.assertIn(role, self.game.toolbox.items)
            self.assertEqual(self.game.cash, 0)
            self.assertIn("can't be sold", self.game.shop_message)

        # A normal block still sells for half.
        self.game._equip_block(plain)
        self.game._sell_selected_item()
        self.assertNotIn(plain, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 10)


    def test_a_spare_role_block_can_be_sold_but_leaves_the_last_one_in_place(self):
        self.game.toolbox.items.clear()
        first = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 0, "Start A")
        second = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.START, 0, 109, "Start B")
        for item in (first, second):
            self.game.toolbox.add(item)
        self.game.cash = 0

        # While there are two, one can go (half of $109).
        self.game._equip_block(second)
        self.game._sell_selected_item()
        self.assertNotIn(second, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 54)

        # The remaining block is now the only Start the player has.
        self.game._equip_block(first)
        self.game._sell_selected_item()
        self.assertIn(first, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 54)
        self.assertIn("can't be sold", self.game.shop_message)


    def test_a_placed_role_block_counts_toward_the_role_count(self):
        self.game.toolbox.items.clear()
        placed = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = placed
        # The only Start block in the game: not for sale.
        self.assertTrue(self.game._unsellable(placed))

        spare = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 109, "Start Block", effects=[])
        self.game.toolbox.add(spare)
        # Now one of the two is spare, so either may go.
        self.assertFalse(self.game._unsellable(placed))
        self.assertFalse(self.game._unsellable(spare))


    def test_role_block_parts_force_rect_and_no_effects(self):
        self.assertEqual(main.role_block_parts(main.Scorer.START, main.Shape.CIRCLE,
                                               [main.Effect.BOUNCY]),
                         (main.Shape.RECT, []))
        self.assertEqual(main.role_block_parts(main.Scorer.FINISH, main.Shape.SLOPE, []),
                         (main.Shape.RECT, []))
        # Every other scorer keeps the parts it rolled.
        self.assertEqual(main.role_block_parts(main.Scorer.CHIPS_ADD, main.Shape.CIRCLE,
                                               [main.Effect.BOUNCY]),
                         (main.Shape.CIRCLE, [main.Effect.BOUNCY]))


    def test_role_block_name_reads_like_the_starter_blocks(self):
        self.assertEqual(main.role_block_name(main.Scorer.START, main.Shape.RECT),
                         "Start Block")
        self.assertEqual(main.role_block_name(main.Scorer.FINISH, main.Shape.RECT),
                         "Finish Block")
        self.assertEqual(main.role_block_name(main.Scorer.CHIPS_ADD, main.Shape.CIRCLE),
                         f"{main.Shape.name(main.Shape.CIRCLE)} "
                         f"{main.Scorer.name(main.Scorer.CHIPS_ADD)}")


    def test_fire_target_zero_when_run_not_passed(self):
        # No fire while the run hasn't passed the required score (or isn't
        # running at all, e.g. during build or after the run is over).
        self.game.run_active = True
        self.game.score_total = 50
        self.game.required_score = 100
        self.assertEqual(self.game._fire_target(), 0.0)
        self.game.run_active = False
        self.game.score_total = 200  # even a big score after the run is over
        self.assertEqual(self.game._fire_target(), 0.0)


    def test_fire_target_scales_with_how_much_score_passed(self):
        # The fire is larger the more the score beats the required score.
        self.game.run_active = True
        self.game.required_score = 100
        self.game.score_total = 150  # 1.5x -> excess ratio 0.5
        self.assertAlmostEqual(self.game._fire_target(), 0.5)
        self.game.score_total = 200  # 2x -> excess ratio 1.0
        self.assertAlmostEqual(self.game._fire_target(), 1.0)
        self.game.score_total = 400  # 4x -> capped at FIRE_MAX_INTENSITY
        self.assertEqual(self.game._fire_target(), main.FIRE_MAX_INTENSITY)


    def test_fire_rises_when_run_passed_and_dies_after(self):
        # The fire grows toward its target while the run is active and passed,
        # then decays to nothing once the run is over.
        self.game.run_active = True
        self.game.score_total = 200
        self.game.required_score = 100
        for _ in range(60):
            self.game._update_fire(main.DT)  # one second of rising
        self.assertGreater(self.game.fire_intensity, 0.5)
        # The run ends: the fire gradually dies down.
        self.game.run_active = False
        for _ in range(180):
            self.game._update_fire(main.DT)  # three seconds of decay
        self.assertAlmostEqual(self.game.fire_intensity, 0.0)


    def test_fire_clears_on_new_game(self):
        self.game.fire_intensity = 2.0
        self.game.reset_game()
        self.assertEqual(self.game.fire_intensity, 0.0)


    def test_non_scoring_block_has_no_trigger_row(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.START)
        labels = [label for label, _ in self.game._describe_item(block)]
        self.assertNotIn("Trigger", labels)


    def test_moving_placed_block_removes_original(self):
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self._click(self._grid_pos(2, 3))  # select the placed block
        self.assertTrue(self.game.has_selected)

        self._click(self._grid_pos(5, 5))  # move it to an empty cell

        self.assertIn((5, 5), self.game.grid)
        self.assertNotIn((2, 3), self.game.grid)  # the original is removed (a move, not a copy)
        placed = self.game.grid[(5, 5)]
        self.assertEqual(placed.shape, main.Shape.SLOPE)
        self.assertEqual(placed.effect, main.Effect.BOUNCY)
        self.assertFalse(self.game.has_selected)


    def test_moving_placed_block_onto_same_cell_is_noop(self):
        self.game.toolbox.items.clear()
        self.game.grid[(2, 3)] = main.Block(2, 3, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self._click(self._grid_pos(2, 3))  # select the placed block

        self._click(self._grid_pos(2, 3))  # "move" it onto itself

        self.assertIn((2, 3), self.game.grid)
        self.assertEqual(self.game.grid[(2, 3)].shape, main.Shape.SLOPE)
        self.assertEqual(len(self.game.toolbox.items), 0)  # nothing refunded
        self.assertFalse(self.game.has_selected)


    def test_a_key_rotates_next_placement_angle_not_placed_block(self):
        # The A key only rotates the next-placement/ghost angle; it does NOT
        # rotate a block that is already placed on the grid.
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.grid[(2, 3)] = block
        self._click(self._grid_pos(2, 3))  # select the placed block

        self._press(main.pygame.K_a)

        self.assertEqual(block.angle, 0)  # the placed block is unchanged
        self.assertEqual(self.game.current_block_angle, 90)
        self.assertIs(self.game.selected_toolbox_item, block)


    def test_a_key_rotates_again_accumulates_next_placement_angle(self):
        self._press(main.pygame.K_a)
        self._press(main.pygame.K_a)

        self.assertEqual(self.game.current_block_angle, 180)


    def test_a_key_does_not_rotate_placed_pipe_drain_bend(self):
        # The A key does not rotate placed pipe/drain/bend blocks in place; it
        # only rotates the next-placement angle. (The shapes still honor their
        # base angle when one is set directly.)
        for shape in (main.Shape.PIPE, main.Shape.DRAIN, main.Shape.PIPE_BEND):
            with self.subTest(shape=main.Shape.name(shape)):
                block = main.Block(2, 3, shape=shape, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
                self.game.grid[(2, 3)] = block
                self.game.current_block_angle = 0
                self._click(self._grid_pos(2, 3))  # select the placed block
                self._press(main.pygame.K_a)
                self.assertEqual(block.angle, 0)
                self.assertEqual(self.game.current_block_angle, 90)


    def test_8_ball_retriggers_scoring_effect(self):
        # The 8 ball has a 1/4 chance per collision to retrigger a block's
        # scoring effect — a free second score that uses no extra trigger.
        self.game.score_chips = 0
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10)
        block.triggers_left = 1
        self.game.grid[(1, 1)] = block
        marble = self._add_marble()
        marble.marble_type = main.MarbleType.EIGHT_BALL
        self.game.run_active = True
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        with mock.patch.object(self.game.run_rng, "random", return_value=0.1):
            self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 20)  # 10 base + 10 retrigger
        self.assertEqual(block.triggers_left, 0)  # still only one trigger used


    def test_8_ball_retrigger_miss_keeps_single_score(self):
        self.game.score_chips = 0
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10)
        block.triggers_left = 1
        self.game.grid[(1, 1)] = block
        marble = self._add_marble()
        marble.marble_type = main.MarbleType.EIGHT_BALL
        self.game.run_active = True
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        with mock.patch.object(self.game.run_rng, "random", return_value=0.9):
            self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(block.triggers_left, 0)


    def test_vanilla_marble_does_not_retrigger(self):
        self.game.score_chips = 0
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10)
        block.triggers_left = 1
        self.game.grid[(1, 1)] = block
        self.game.run_active = True
        marble = self._add_marble()  # vanilla: no retrigger
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        self.game._handle_block_contacts(list(self.game.grid.values()))
        self.assertEqual(self.game.score_chips, 10)


    def test_rubber_ball_bounces_off_block(self):
        # A rubber-ball marble reflects the full normal velocity off a block;
        # a normal marble just loses it (restitution 0).
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, 0)
        marble.velocity = np.array([0.0, 100.0])  # moving down into the top face
        marble.bouncy = True
        marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
        self.assertEqual(marble.velocity[1], -100.0)  # bounced straight back up


    def test_normal_marble_does_not_bounce_off_block(self):
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, 0)
        marble.velocity = np.array([0.0, 100.0])
        marble.bouncy = False
        marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
        self.assertEqual(marble.velocity[1], 0.0)  # normal marbles stop at walls


    def test_placing_block_plays_plop_sound(self):
        # Placing a block on the grid plops.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        with mock.patch("main.sounds.play_plop") as play:
            self._click(self._grid_pos(1, 1))
        play.assert_called_once()


    def test_every_effect_has_its_own_collision_sound(self):
        import sounds
        self._assert_waves_are_distinct(list(main.Effect.ORDER),
                                       sounds._effect_wave, "effect")


    def test_t_key_starts_a_run_with_a_sound(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        with mock.patch("main.sounds.play_run_start") as play:
            self._press(main.pygame.K_t)
        play.assert_called_once()
        self.assertTrue(self.game.run_active)


    def test_t_key_without_a_start_block_stays_silent(self):
        # No Start block on the board means no run actually starts.
        with mock.patch("main.sounds.play_run_start") as play:
            self._press(main.pygame.K_t)
        play.assert_not_called()


    def test_r_key_resets_the_run_with_a_sound(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        with mock.patch("main.sounds.play_reset") as play:
            self._press(main.pygame.K_r)
        play.assert_called_once()


    def test_plain_block_contact_rings_only_the_neutral_effect_sound(self):
        block = main.Block(0, 0, scorer=main.Scorer.NONE)
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        with mock.patch("main.sounds.play_effect") as effect_sound, \
             mock.patch("main.sounds.play_scorer") as scorer_sound:
            self.game._handle_block_contacts([block])
        effect_sound.assert_called_once_with(main.Effect.NONE)
        scorer_sound.assert_not_called()


    def test_new_shapes_have_a_solid_point_and_an_empty_point(self):
        # A marble placed on each shape's solid collides; one placed clear of it
        # does not. This exercises the per-shape collision dispatch.
        solid_at = {
            main.Shape.SPIKE: lambda b: (b.rect.centerx, b.rect.bottom - 4),
            main.Shape.PLATFORM: lambda b: (b.rect.centerx, b.rect.bottom - 4),
            main.Shape.CORNER: lambda b: (b.rect.left + 4, b.rect.centery),
            main.Shape.PEG: lambda b: (b.rect.centerx, b.rect.centery),
            main.Shape.SAWTOOTH: lambda b: (b.rect.left + 5, b.rect.bottom - 4),
            main.Shape.CRADLE: lambda b: (b.rect.centerx, b.rect.bottom - 4),
        }
        for shape in self._new_shapes():
            block = main.Block(5, 5, shape=shape, scorer=main.Scorer.NONE)
            marble = main.Marble(*solid_at[shape](block))
            self.assertIsNotNone(marble.physics._block_collision(marble, block),
                                 f"{shape} solid point did not collide")
            far = main.Marble(block.rect.centerx, block.rect.top - 200)
            self.assertIsNone(far.physics._block_collision(far, block),
                              f"{shape} collided far from the shape")


    def test_new_shapes_stop_a_falling_marble(self):
        # A marble dropped onto each new shape is caught: it never passes below
        # the block's cell.
        for shape in self._new_shapes():
            block = main.Block(5, 5, shape=shape, scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 70)
            for _ in range(300):
                marble.physics.update(marble, main.DT, [block])
                self.assertLess(marble.position[1], block.rect.bottom,
                                f"{shape} let the marble fall through")


    def test_cradle_catches_and_settles_a_marble(self):
        # The cradle's wide floor catches a dropped marble and settles it there.
        block = main.Block(5, 5, shape=main.Shape.CRADLE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 70)
        for _ in range(300):
            marble.physics.update(marble, main.DT, [block])
        rest_y = block.rect.top + main.CRADLE_FLOOR_DEPTH - marble.radius
        self.assertAlmostEqual(marble.position[1], rest_y, delta=1.0)
        self.assertLess(abs(marble.velocity[1]), 1.0)


    def test_peg_is_a_small_circle_smaller_than_the_circle_shape(self):
        self.assertEqual(main.PEG_RADIUS, 5)
        self.assertLess(main.PEG_RADIUS, main.GRID_SIZE // 2)
        self.assertLess(main.PEG_RADIUS, main.MARBLE_RADIUS)


    def test_rotated_new_shapes_still_collide(self):
        # The A-key angle (and ROTATE spin) rotates the hitbox: a marble at the
        # image of a solid point under that rotation still collides. This
        # exercises the oriented-rect path (platform) and the rotated-polygon
        # path (spike/cradle).
        for shape, local in ((main.Shape.PLATFORM, (0.5, 0.8)),
                             (main.Shape.SPIKE, (0.5, 0.9)),
                             (main.Shape.CRADLE, (0.5, 0.9))):
            block = main.Block(5, 5, shape=shape, scorer=main.Scorer.NONE)
            block.angle = 90
            px = block.rect.left + local[0] * block.rect.width
            py = block.rect.top + local[1] * block.rect.height
            rx = block.rect.centerx - (py - block.rect.centery)
            ry = block.rect.centery + (px - block.rect.centerx)
            marble = main.Marble(rx, ry)
            self.assertIsNotNone(marble.physics._block_collision(marble, block),
                                 f"{shape} rotated solid did not collide")


    def test_new_effects_were_appended_to_the_effect_order(self):
        # Effects must be APPENDED, never inserted: an effect collision
        # condition is EFFECT_BASE + Effect.ORDER.index(effect), so inserting
        # one would renumber every saved effect condition, card, and collection
        # entry. Sticky (the last effect before this batch) must keep id 12.
        self.assertEqual(main.Effect.ORDER.index(main.Effect.STICKY), 12)
        self.assertEqual(main.Effect.ORDER[-len(self._new_effects()):],
                         list(self._new_effects()))


    def test_repulsor_pushes_a_marble_away_and_black_hole_pulls_it_in(self):
        def drift(effect):
            block = main.Block(5, 5, effect=effect, scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 40)
            marble.velocity = np.array([0.0, 0.0])
            before = marble.position.copy()
            for _ in range(5):
                marble.physics.update(marble, main.DT, [block])
            return before[1] - marble.position[1]  # up is positive

        self.assertGreater(drift(main.Effect.REPULSOR), 0.0)
        self.assertLess(drift(main.Effect.BLACK_HOLE), 0.0)


    def test_conveyor_carries_a_marble_along_its_belt(self):
        # A marble resting on a conveyor is carried sideways; rotating the block
        # 180 degrees reverses the belt, so it is carried the other way.
        def drift(angle):
            block = main.Block(5, 5, effect=main.Effect.CONVEYOR,
                               scorer=main.Scorer.NONE)
            block.angle = angle
            marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
            marble.velocity = np.array([0.0, 0.0])
            for _ in range(5):
                marble.physics.update(marble, main.DT, [block])
            return marble.velocity[0]

        self.assertGreater(drift(0), 0.0)
        self.assertLess(drift(180), 0.0)


    def test_conveyor_holds_a_constant_belt_speed_instead_of_accelerating(self):
        # A belt carries the marble at its OWN constant speed: the along-belt
        # speed is set when the marble touches down and then held there, so the
        # marble is never accelerated frame after frame.
        block = main.Block(5, 5, effect=main.Effect.CONVEYOR, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([0.0, 0.0])
        speeds = []
        for _ in range(120):
            # A long belt: keep the marble on it so the speed can be watched.
            marble.position[0] = block.rect.centerx
            marble.physics.update(marble, main.DT, [block])
            speeds.append(float(marble.velocity[0]))
        self.assertAlmostEqual(speeds[0], main.CONVEYOR_SPEED, delta=10.0)
        self.assertAlmostEqual(speeds[-1], main.CONVEYOR_SPEED, delta=10.0)
        self.assertLessEqual(max(speeds), main.CONVEYOR_SPEED + 0.01,
                             "the belt accelerated the marble past its own speed")


    def test_conveyor_does_not_slow_a_faster_marble_or_scale_with_mass(self):
        # A belt only adds speed: a marble already moving faster along the belt
        # keeps its own speed, and the belt speed is the same for every marble
        # (a light marble is not flung harder by a belt).
        block = main.Block(5, 5, effect=main.Effect.CONVEYOR, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([900.0, 0.0])
        marble.mass = 0.35
        marble.effect_mass_mult = 0.5
        marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.velocity[0], main.CONVEYOR_SPEED,
                           "the belt slowed a marble that was already faster")


    def test_zipper_is_passable_with_its_arrow_and_solid_against_it(self):
        block = main.Block(5, 5, effect=main.Effect.ZIPPER, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        # The default arrow points up: travelling up passes straight through...
        marble.velocity = np.array([0.0, -200.0])
        self.assertIsNone(marble.physics._block_collision(marble, block))
        # ...while travelling down (against the arrow) collides.
        marble.velocity = np.array([0.0, 200.0])
        self.assertIsNotNone(marble.physics._block_collision(marble, block))


    def test_zipper_sides_stay_solid_while_moving_along_the_arrow(self):
        # Regression: the gate used to test only the velocity direction, so a
        # marble whose velocity had ANY component along the arrow (one riding a
        # conveyor up, say) was let through the block's solid SIDE and crept out
        # through it a frame at a time. Only the marble-wide door along the
        # arrow is passable.
        block = main.Block(5, 5, effect=main.Effect.ZIPPER, scorer=main.Scorer.NONE)
        for velocity in ((300.0, -20.0), (60.0, -5.0), (0.0, -50.0)):
            marble = main.Marble(block.rect.left - main.MARBLE_RADIUS + 2,
                                 block.rect.centery)
            marble.velocity = np.array(velocity)
            self.assertIsNotNone(
                marble.physics._block_collision(marble, block),
                f"a marble moving {velocity} tunnelled through the zipper's side")
        # The door is still open to a marble in its channel...
        in_door = main.Marble(block.rect.centerx, block.rect.centery)
        in_door.velocity = np.array([0.0, -300.0])
        self.assertIsNone(in_door.physics._block_collision(in_door, block))
        # ...and the closed face stays solid away from the channel.
        for offset in (12, 20):
            off_centre = main.Marble(block.rect.centerx + offset,
                                     block.rect.bottom + main.MARBLE_RADIUS - 2)
            off_centre.velocity = np.array([0.0, -300.0])
            self.assertIsNotNone(
                off_centre.physics._block_collision(off_centre, block),
                f"the zipper door opened {offset}px off centre")


    def test_component_images_of_corner_and_cradle_have_no_inner_lines(self):
        # A component/ghost image draws the shape's own outline: the corner's
        # two legs and the cradle's pieces used to be outlined one by one, which
        # drew a seam inside the shape where they overlap.
        surface = pygame.Surface([main.GRID_SIZE] * 2)

        corner = main.Block(0, 0, shape=main.Shape.CORNER, origin=(0, 0))
        surface.fill(main.BLACK)
        main.ui.draw_block_shape_only(corner, surface)
        self.assertNotEqual(
            surface.get_at((corner.rect.width // 2, corner.rect.height * 3 // 4))[:3],
            main.WHITE, "the corner's legs still show a seam inside the shape")
        self.assertEqual(
            surface.get_at((corner.rect.width // 2, corner.rect.height // 4))[:3],
            main.WHITE, "the corner's L outline is missing")

        cradle = main.Block(0, 0, shape=main.Shape.CRADLE, origin=(0, 0))
        surface.fill(main.BLACK)
        main.ui.draw_block_shape_only(cradle, surface)
        self.assertNotEqual(
            surface.get_at((2, main.CRADLE_FLOOR_DEPTH))[:3], main.WHITE,
            "the cradle's wedges still show a seam on the floor slab")
        self.assertEqual(
            surface.get_at((cradle.rect.width // 2, main.CRADLE_FLOOR_DEPTH))[:3],
            main.WHITE, "the cradle's flat floor outline is missing")


    def test_phase_grants_one_second_of_no_collisions(self):
        # Touching a phase block arms PHASE_DURATION of phasing, which lets the
        # marble fall straight through a solid wall below it.
        phase = main.Block(5, 5, effect=main.Effect.PHASE, scorer=main.Scorer.NONE)
        wall = main.Block(5, 6, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        marble = main.Marble(phase.rect.centerx, phase.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(2):
            marble.physics.update(marble, main.DT, [phase, wall])
        self.assertAlmostEqual(marble.phase_timer, main.PHASE_DURATION,
                               delta=2 * main.DT + 1e-6)
        for _ in range(30):
            marble.physics.update(marble, main.DT, [phase, wall])
        self.assertGreater(marble.phase_timer, 0.0)
        self.assertGreater(marble.position[1], wall.rect.bottom,
                           "a phasing marble did not pass through the wall")


    def test_phase_does_not_rearm_while_the_marble_stays_on_the_block(self):
        # A phase block may not grant another phase until the marble is clear of
        # it, so a marble that stays on it can't phase forever.
        block = main.Block(5, 5, effect=main.Effect.PHASE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.phase_block = block
        marble.phase_timer = 0.0
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(30):
            marble.physics.update(marble, main.DT, [block])
            self.assertEqual(marble.phase_timer, 0.0)


    def test_physics_records_the_arrival_velocity_of_a_contact(self):
        # The splitter reflects the velocity the marble ARRIVED with, so the
        # first record of a contact must survive the rest of the frame (later
        # sub-steps re-collide with an already-stopped velocity).
        block = main.Block(4, 4, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 60)
        marble.velocity = np.array([0.0, 400.0])
        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])
            if block in marble.collisions_this_tick:
                break
        self.assertIn(block, marble.collisions_this_tick)
        incoming = marble.contact_incoming.get(block)
        self.assertIsNotNone(incoming)
        self.assertGreater(float(incoming[1]), 50.0)
        self.assertIn(block, marble.contact_normals)


    def test_splitter_copy_is_the_reversed_reflection_of_the_marble(self):
        block = main.Block(5, 5, effect=main.Effect.SPLITTER, scorer=main.Scorer.NONE)
        marble = self._add_marble((block.rect.centerx,
                                   block.rect.top - main.MARBLE_RADIUS))
        # By the time the splitter fires the collision response has already
        # stopped the marble, so the copy reflects the velocity it ARRIVED with.
        arrived = np.array([60.0, 200.0])
        marble.velocity = np.array([0.0, 0.0])
        normal = np.array([0.0, -1.0])  # the floor normal of the block below
        marble.contact_normals = {block: normal}
        marble.contact_incoming = {block: arrived}
        copy = self.game._split_marble(marble, block)
        self.assertIsNotNone(copy)
        self.assertIsInstance(copy, main.Marble)
        self.assertEqual(len(self.game.marbles), 2)
        expected = -arrived + 2.0 * float(np.dot(arrived, normal)) * normal
        self.assertTrue(np.allclose(copy.velocity, expected),
                        f"copy velocity {copy.velocity} != {expected}")
        # The copy keeps the marble's speed and look, and starts where it was.
        self.assertAlmostEqual(float(np.linalg.norm(copy.velocity)),
                               float(np.linalg.norm(arrived)), places=6)
        self.assertEqual(copy.marble_type, marble.marble_type)
        self.assertTrue(np.allclose(copy.position, marble.position))
        # A copy differs from the original (it is not the same object) and the
        # original is left alone.
        self.assertIsNot(copy, marble)
        self.assertTrue(np.allclose(marble.velocity, np.array([0.0, 0.0])))


    def test_splitter_stops_splitting_at_the_marble_cap(self):
        block = main.Block(5, 5, effect=main.Effect.SPLITTER, scorer=main.Scorer.NONE)
        marble = self._add_marble((block.rect.centerx, block.rect.top - 10))
        for _ in range(main.MAX_MARBLES + 4):
            self.game._split_marble(marble, block)
        self.assertEqual(len(self.game.marbles), main.MAX_MARBLES)
        self.assertIsNone(self.game._split_marble(marble, block))


    def test_splitter_block_splits_the_marble_on_a_fresh_touch(self):
        block = main.Block(5, 5, effect=main.Effect.SPLITTER, scorer=main.Scorer.NONE)
        self.game.grid[(5, 5)] = block
        self.game.run_active = True
        marble = self._add_marble((block.rect.centerx,
                                   block.rect.top - main.MARBLE_RADIUS))
        marble.velocity = np.array([0.0, 100.0])
        marble.collisions_last_tick = []
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(len(self.game.marbles), 2)
        self.assertEqual(block.triggers_left, block.trigger_limit - 1)


    def test_bump_shape_is_a_half_disc_dome(self):
        # The bump is a first-class shape: named, described, priced, drawing
        # both ways, and auto-generating a collision condition that builds a
        # card — the same treatment as the other shapes.
        shape = main.Shape.BUMP
        self.assertIn(shape, main.Shape.ORDER)
        self.assertNotEqual(main.Shape.name(shape), "Unknown")
        self.assertTrue(main.shape_description(shape))
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)
        cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
        self.assertIn(cond, main.CONDITION_ORDER)
        self.assertEqual(components.condition_shape(cond), shape)
        self.assertGreaterEqual(main.condition_scorer_card(cond, main.Scorer.MULT_ADD),
                                components.CONDITION_CARD_OFFSET)
        for borders in (True, False):
            prev = main.BLOCK_BORDERS_ON
            main.BLOCK_BORDERS_ON = borders
            try:
                surface = pygame.Surface([main.GRID_SIZE] * 2)
                block = main.Block(0, 0, shape=shape, scorer=main.Scorer.CHIPS_ADD,
                                   origin=(0, 0))
                block.draw(surface)
                main.ui.draw_block_shape_only(
                    main.Block(0, 0, shape=shape, origin=(0, 0)), surface)
            finally:
                main.BLOCK_BORDERS_ON = prev


    def test_bump_dome_sits_on_the_cell_bottom_edge(self):
        block = main.Block(5, 5, shape=main.Shape.BUMP, scorer=main.Scorer.NONE)
        pts = block.get_bump_points
        self.assertAlmostEqual(max(p[1] for p in pts), block.rect.bottom, delta=0.01)
        self.assertAlmostEqual(min(p[1] for p in pts),
                               block.rect.bottom - main.GRID_SIZE / 2, delta=1.0)
        self.assertAlmostEqual(min(p[0] for p in pts), block.rect.left, delta=1.0)
        self.assertAlmostEqual(max(p[0] for p in pts), block.rect.right, delta=1.0)


    def test_bump_is_solid_in_the_dome_and_empty_above_it(self):
        block = main.Block(5, 5, shape=main.Shape.BUMP, scorer=main.Scorer.NONE)
        apex_y = block.rect.bottom - main.GRID_SIZE // 2
        on_dome = main.Marble(block.rect.centerx + 8, apex_y + 4)
        self.assertIsNotNone(on_dome.physics._block_collision(on_dome, block))
        above = main.Marble(block.rect.centerx, apex_y - main.MARBLE_RADIUS - 2)
        self.assertIsNone(above.physics._block_collision(above, block))


    def test_bump_sheds_an_off_center_marble_sideways(self):
        # A marble landing off the crown slides down the dome instead of staying
        # put; one balanced exactly on the crown rests there (the dome is
        # symmetric), but neither ever falls through the bump.
        block = main.Block(5, 5, shape=main.Shape.BUMP, scorer=main.Scorer.NONE)
        crown = block.rect.bottom - main.GRID_SIZE // 2 - main.MARBLE_RADIUS
        marble = main.Marble(block.rect.centerx + 3, crown)
        for _ in range(120):
            marble.physics.update(marble, main.DT, [block])
        self.assertGreater(abs(marble.position[0] - block.rect.centerx), 5.0)
        balanced = main.Marble(block.rect.centerx, crown)
        for _ in range(120):
            balanced.physics.update(balanced, main.DT, [block])
        self.assertLess(balanced.position[1], block.rect.bottom)


    def test_pillar_plus_chips_scales_proportionally_per_column_block(self):
        # Fullest Column (Pillar) has ratio 0.25, so +Chips pays round(0.25*30)
        # = +8 chips per block in the fullest column at the start of the run.
        value = main.condition_scorer_card(main.Condition.FULLEST_COLUMN,
                                           main.Scorer.CHIPS_ADD)
        self.assertEqual(main.Card.name(value), "Pillar +Chips")
        self.game.cards.append(main.CardItem(value, 40))
        for i in range(3):
            self.game.grid[(2, i)] = main.Block(2, i)
        self.game.score_chips = 0
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 8 * 3)


    def test_same_block_xmult_triggers_multiply(self):
        # A Sharp block (x3 = +2 xMult) with trigger limit 2, fired twice,
        # applies its factor on both triggers (1 -> 3 -> 9): xMult always
        # multiplies (Game._apply_xmult), so an item's own triggers compound.
        self.game.score_mult = 1
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.SHARP, trigger_limit=2)
        self.assertEqual(block.triggers_left, 2)
        for _ in range(2):
            self.game.marbles = []
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(block.triggers_left, 0)
        self.assertAlmostEqual(self.game.score_mult, 9)


    def test_different_blocks_xmult_apply_separately(self):
        # Two different Sharp blocks each triple on their own first trigger,
        # so the multiplier compounds across them (1 -> 3 -> 9).
        self.game.score_mult = 1
        self.game.run_active = True
        for _ in range(2):
            self.game.marbles = []
            block = main.Block(0, 0, scorer=main.Scorer.SHARP)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 9)


    def test_wrecking_ball_bonus_grows_when_fragile_block_breaks(self):
        # Each fragile block break adds 3 to the run's mult gain (applied to
        # the current run live) and pops its particle near the block. It only
        # becomes permanent after a run.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game.score_mult = 1
        self.game.run_active = True
        self.game._on_fragile_broken(block)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)  # not committed
        self.assertEqual(self.game.score_mult, 4)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "3")
        self.assertEqual(p.color, main.BLUE)
        self.assertEqual((p.x, p.y), (block.rect.centerx, block.rect.centery))


    def test_fragile_break_sets_flag_and_grows_wrecking_ball_in_update(self):
        # A real physics shatter marks the block; the game's update() then
        # tracks the wrecking ball's run gain and spawns its particle at the
        # block.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.left - 10, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([400.0, 0.0])
        self.game.grid[(5, 8)] = block
        self.game.marbles.append(marble)
        self.game.run_active = True
        for _ in range(40):
            self.game.update()
            if self.game.wrecking_run_gain[main.Scorer.MULT_ADD] >= 3:
                break
        self.assertEqual(block.shape, main.Shape.NONE)  # the block shattered
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)
        p = self.game.score_particles[0]
        self.assertEqual((p.x, p.y), (block.rect.centerx, block.rect.centery))


    def test_key_during_post_run_retries(self):
        self.game.cash = 100
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self._press(main.pygame.K_t)  # any key during the post-run state retries

        self.assertEqual(self.game.run_results, [])
        self.assertEqual(self.game.runs_cleared, 0)
        self.assertEqual(self.game.cash, 100)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)


    def test_placing_block_during_post_run_retries_then_places(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.cash = 100
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)

        self._click(self._grid_pos(1, 1))  # place a block during the post-run state

        self.assertFalse(self.game.awaiting_after_run)  # retried first
        self.assertEqual(self.game.run_results, [])
        self.assertIn((1, 1), self.game.grid)  # then the action played out


    def test_y_key_does_not_advance_during_active_run(self):
        # Pressing Y while a run is still in progress (marbles not finished)
        # must not skip ahead to the next round.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run(False)
        self.assertTrue(self.game.run_active)
        self.assertFalse(self.game.run_complete)

        self._press(main.pygame.K_y)

        self.assertEqual(self.game.run_number, 0)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[0])
        self.assertFalse(self.game.run_complete)
        self.assertFalse(self.game.awaiting_after_run)


    def test_y_key_continues_after_run_completes(self):
        # Y is the CONTINUE key: after a run finishes it advances to the next
        # run WITHOUT retrying first (the run result is kept).
        self.game.cash = 100
        self.game.run_time = main.TIME_IDEAL
        self._complete_run(10000, required=1)
        self.assertTrue(self.game.awaiting_after_run)

        self._press(main.pygame.K_y)

        self.assertEqual(self.game.run_number, 1)
        self.assertEqual(self.game.required_score, main.REQUIRED_SCORES[1])
        self.assertEqual(self.game.run_results, [True])  # not retried
        self.assertEqual(self.game.runs_cleared, 1)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(self.game.run_complete)


    def test_singularity_makes_marble_gain_mass_linearly(self):
        # The Singularity boss grows the marble's mass at a constant rate per
        # second, so it falls ever faster over the run.
        self.game.final_boss = main.FinalBoss.SINGULARITY
        marble = self._add_marble()
        self.game.run_active = True
        before = marble.mass
        for _ in range(60):  # 60 frames = 1 second at DT
            self.game.update()
        self.assertGreater(marble.mass, before)
        self.assertAlmostEqual(marble.mass, before + main.SINGULARITY_MASS_GROWTH, places=2)


    def test_mass_stays_constant_without_singularity(self):
        # Without the Singularity boss the marble's mass never changes.
        marble = self._add_marble()
        self.game.run_active = True
        for _ in range(60):
            self.game.update()
        self.assertEqual(marble.mass, main.MARBLE_MASS)


    def test_reset_run_blocked_while_awaiting_choice(self):
        self._complete_run(10000, required=1000)
        self.assertTrue(self.game.awaiting_after_run)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertFalse(self.game.reset_run())

        self.assertTrue(self.game.run_complete)  # still waiting for the choice


    def test_effect_descriptions_state_the_deviation_inline(self):
        # An effect states its own magnitude in the text, with the deviation
        # right after it.
        strong = main.effect_description(main.Effect.PISTON, 1800)
        self.assertEqual(strong,
                         "Launches marbles at 1800 px/s along its surface (+300).")
        weak = main.effect_description(main.Effect.PISTON, 900)
        self.assertIn("900 px/s along its surface (-600).", weak)
        average = main.effect_description(main.Effect.BLACK_HOLE)
        self.assertIn("3000 px/s^2 of gravity (0)", average)
        # An on/off effect has no magnitude to report.
        self.assertNotIn("average", main.effect_description(main.Effect.FRAGILE))
        self.assertEqual(main.effect_description(main.Effect.FRAGILE),
                         "Shatters into a no-hitbox field after a marble touches it and leaves.")


    def test_an_unrolled_effect_piece_reads_the_average_not_zero(self):
        # A piece built without a magnitude (an old save, or code that predates
        # the roll) is the average-strength piece, and says so.
        piece = main.Component.effect_component(main.Effect.REPULSOR)
        self.assertEqual(piece.effect_magnitude, main.BLACK_HOLE_FORCE)
        rows = dict(self.game._describe_item(piece))
        self.assertIn("3000 px/s^2 of force (0)", rows["Effect - Repulsor"])
        self.assertNotIn(" 0 px/s", rows["Effect - Repulsor"])
        self.assertNotIn(" 0 px/s", main.effect_description(main.Effect.REPULSOR, 0))
        self.assertIn("3000 px/s^2 of force (0)",
                      main.effect_description(main.Effect.REPULSOR, 0))
        # A stored 0 can never shadow the average on a block either.
        block = main.Block(0, 0, effect=main.Effect.REPULSOR,
                           effects=[main.Effect.REPULSOR],
                           effect_amounts={main.Effect.REPULSOR: 0})
        self.assertEqual(block.effect_magnitude(main.Effect.REPULSOR),
                         main.BLACK_HOLE_FORCE)
        # An on/off effect is still zero, and states no magnitude at all.
        fragile = main.Component.effect_component(main.Effect.FRAGILE)
        self.assertEqual(fragile.effect_magnitude, 0)
        self.assertNotIn("(", main.effect_description(main.Effect.FRAGILE, 0))


    def test_effect_magnitudes_round_trip_through_a_save(self):
        self.game.cash = 100
        placed = main.Block(2, 2, shape=main.Shape.RECT,
                            effects=[main.Effect.PISTON],
                            effect_amounts={main.Effect.PISTON: 1800},
                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=45)
        self.game.grid[(2, 2)] = placed
        self.game.shop.items.clear()
        self.game.shop.items.append(main.BlockItem(
            0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD, 45, 99,
            "Rect +Chips", effects=[main.Effect.BLACK_HOLE],
            effect_amounts={main.Effect.BLACK_HOLE: 3900}))

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(save_system, "SAVES_DIR",
                                  os.path.join(tmp, "saves")):
            save_system.save_game(self.game)
            fresh = main.Game()
            fresh.save_slot = self.game.save_slot
            save_system.load_slot(fresh, self.game.save_slot)

        restored = fresh.grid[(2, 2)]
        self.assertEqual(restored.effect_magnitude(main.Effect.PISTON), 1800)
        self.assertEqual(restored.scorer_amount, 45)
        offer = next(i for i in fresh.shop.items if getattr(i, "kind", None) == "block")
        self.assertEqual(offer.effect_magnitude(main.Effect.BLACK_HOLE), 3900)
        self.assertEqual(offer.scorer_amount, 45)


    def test_upgrade_trigger_limit_deducts_cash_and_raises_limit(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips", trigger_limit=1)
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 1000
        cost = self.game._trigger_upgrade_cost(block)

        self.game._upgrade_trigger_limit()

        self.assertEqual(block.trigger_limit, 2)
        self.assertEqual(block.trigger_paid, cost)
        self.assertEqual(self.game.cash, 1000 - cost)


    def test_upgrade_trigger_limit_requires_cash(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips")
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 0

        self.game._upgrade_trigger_limit()

        self.assertEqual(block.trigger_limit, 1)
        self.assertTrue(self.game.shop_message)


    def test_upgrade_trigger_limit_only_for_blocks(self):
        comp = next(i for i in self.game.shop.items if i.kind == main.Component.SHAPE)
        self.game.selected_toolbox_item = comp
        self.game.cash = 1000

        self.game._upgrade_trigger_limit()

        self.assertEqual(self.game.cash, 1000)  # no charge: components aren't blocks


    def test_place_block_at_refuses_locked_cells_and_empty_hands(self):
        # Nothing selected: no block, no exception.
        self.game._clear_toolbox_selection()
        self.assertFalse(self.game._place_block_at(2, 2))
        self.assertIsNone(self.game.grid.get((2, 2)))

        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 30, 20, "Rect +Chips")
        self.game.toolbox.add(item)
        self.game._equip_block(item)
        self.game.unlocked_cells.discard((2, 2))

        self.assertFalse(self.game._place_block_at(2, 2))  # a locked square
        self.assertIsNone(self.game.grid.get((2, 2)))
        # Out-of-bounds cells never place either.
        self.assertFalse(self.game._place_block_at(-1, 0))
        self.assertFalse(self.game._place_block_at(main.GRID_WIDTH, 0))
        self.assertFalse(self.game._place_block_at(0, main.GRID_HEIGHT))


    def test_place_block_at_swaps_out_whatever_stood_in_the_cell(self):
        old = self._place_priced_block(1, 1, 40)  # a $40 block already standing
        self.game.cash = 0
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 30, 9, "Rect +Chips")
        self.game.toolbox.add(item)
        self.game._equip_block(item)

        self.assertTrue(self.game._place_block_at(1, 1))

        placed = self.game.grid[(1, 1)]
        self.assertIsNot(placed, old)
        self.assertEqual(placed.resale_price, 9)
        # The block it displaced came back to the toolbox at ITS own price.
        self.assertTrue(any(getattr(i, "price", None) == 40
                            for i in self.game.toolbox.items))


    def test_place_block_at_moves_a_placed_block_out_of_its_old_cell(self):
        placed = self._place_priced_block(1, 1, 7)
        self.game._select_placed_block(placed)

        self.assertTrue(self.game._place_block_at(3, 3))

        self.assertNotIn((1, 1), self.game.grid)
        moved = self.game.grid[(3, 3)]
        self.assertEqual(moved.scorer, placed.scorer)
        self.assertEqual(moved.resale_price, 7)  # the price travels with it
        self.assertNotIn(placed, self.game.toolbox.items)  # not also refunded


    def test_upgraded_block_scores_multiple_times_per_run(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.NONE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, trigger_limit=2)
        marble = self._add_marble()  # already appends to self.game.marbles
        self.game.run_active = True
        self.game.score_chips = 0

        # Touch, leave, and touch again: each edge scores (limit 2 -> twice).
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 10)

        marble.collisions_this_tick = []
        marble.collisions_last_tick = [block]
        self.game._handle_block_contacts([block])

        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = []
        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_chips, 20)
        self.assertEqual(block.triggers_left, 0)


    def test_block_effect_property_returns_first_effect(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertEqual(block.effect, main.Effect.BOUNCY)
        self.assertEqual(block.effects, [main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertTrue(block.has_effect(main.Effect.BOUNCY))
        self.assertTrue(block.has_effect(main.Effect.PISTON))
        self.assertFalse(block.has_effect(main.Effect.GRAVITY))


    def test_block_without_effects_falls_back_to_none(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.NONE,
                           scorer=main.Scorer.NONE)
        self.assertEqual(block.effect, main.Effect.NONE)
        self.assertEqual(block.effects, [main.Effect.NONE])


    def test_blockitem_effect_property_returns_first_effect(self):
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.BOUNCY,
                              main.Scorer.CHIPS_ADD, 10, 20, "B",
                              effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertEqual(item.effect, main.Effect.BOUNCY)
        self.assertEqual(item.effects, [main.Effect.BOUNCY, main.Effect.PISTON])
        self.assertTrue(item.has_effect(main.Effect.PISTON))


    def test_random_effect_count_is_bounded(self):
        counts = [main.random_effect_count() for _ in range(800)]
        self.assertTrue(all(0 <= c <= len(main.Effect.REAL_ORDER) for c in counts))
        self.assertIn(0, counts)
        self.assertIn(1, counts)
        self.assertIn(2, counts)


    def test_random_effect_count_geometric_distribution(self):
        random.seed(1234)
        trials = 4000
        observed = {}
        for _ in range(trials):
            c = main.random_effect_count()
            observed[c] = observed.get(c, 0) + 1
        # Roughly 1/4 no-effect, then 1/2 of the rest one-effect (~0.375),
        # 1/4 of the rest two-effect (~0.19), 1/8 three-effect (~0.09)...
        self.assertGreater(observed.get(0, 0) / trials, 0.15)
        self.assertLess(observed.get(0, 0) / trials, 0.35)
        self.assertGreater(observed.get(1, 0) / trials, 0.3)
        self.assertGreater(observed.get(2, 0) / trials, 0.15)
        self.assertGreater(observed.get(3, 0) / trials, 0.07)
        # Fewer blocks with more effects.
        self.assertGreater(observed.get(1, 0), observed.get(2, 0))
        self.assertGreater(observed.get(2, 0), observed.get(3, 0))


    def test_effect_real_order_excludes_none(self):
        self.assertNotIn(main.Effect.NONE, main.Effect.REAL_ORDER)


    def test_placing_portal_block_preserves_number(self):
        self.game.toolbox.items.clear()
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                                0, 50, "Portal", portal_number=5)
        self.game.toolbox.add(portal)
        self.game._equip_block(portal)

        self._click(self._grid_pos(1, 1))

        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.effect, main.Effect.PORTAL)
        self.assertEqual(placed.portal_number, 5)  # the placed block keeps its number
        self.assertNotIn(portal, self.game.toolbox.items)  # consumed on placement


    def test_using_either_portal_of_a_pair_depletes_both(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        # The marble passes through b (which carries the scorer) and exits at a.
        marble = self._add_marble((b.rect.centerx, b.rect.centery))
        self.game.run_active = True

        marble.physics.update(marble, main.DT, list(self.game.grid.values()))
        self.game._handle_block_contacts(list(self.game.grid.values()))

        self.assertEqual(self.game.score_chips, 10)
        self.assertEqual(b.triggers_left, 0)  # the portal that was used
        self.assertEqual(a.triggers_left, 0)  # the partner shares the count


    def test_placing_portal_syncs_trigger_count_with_partner(self):
        self.game.toolbox.items.clear()
        partner = main.Block(2, 2, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                             scorer=main.Scorer.NONE, portal_number=7)
        self.game.grid[(2, 2)] = partner
        partner.triggers_left = 0  # already exhausted this run
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                                0, 50, "Portal", portal_number=7)
        self.game.toolbox.add(portal)
        self.game._equip_block(portal)

        self._click(self._grid_pos(1, 1))

        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.portal_number, 7)
        self.assertEqual(placed.triggers_left, 0)  # inherits the pair's exhausted count
        self.assertEqual(partner.triggers_left, 0)


    def test_portal_travel_budget_refills_each_run(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        self.game.grid[(5, 5)] = a
        self.game.grid[(2, 2)] = b
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(a.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        self.assertEqual(b.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        # A portal pair drained during a run...
        a.portal_uses_left = 0
        b.portal_uses_left = 0
        # ...gets its full 100-travel budget back at the start of the next run.
        self.assertTrue(self.game.reset_run())
        self.assertEqual(a.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        self.assertEqual(b.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)


    def test_portal_description_mentions_the_100_use_cap(self):
        desc = main.effect_description(main.Effect.PORTAL)
        self.assertIn("portal", desc.lower())
        self.assertIn("100", desc)
        self.assertIn("run", desc.lower())


    def test_v_key_clears_marbles(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(2, 1)] = main.Block(2, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 2)

        self._press(main.pygame.K_v)

        self.assertEqual(self.game.marbles, [])  # no start blocks left to run from
        self.assertFalse(self.game.run_active)


    def test_erasing_start_block_removes_its_marble(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(2, 1)] = main.Block(2, 1, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 2)
        # Each marble is tied to its own start block.
        start_a = self.game.grid[(1, 1)]
        start_b = self.game.grid[(2, 1)]
        marble_a = next(m for m in self.game.marbles if m.start_block is start_a)
        marble_b = next(m for m in self.game.marbles if m.start_block is start_b)

        self.game._erase_block_at(1, 1)

        self.assertNotIn((1, 1), self.game.grid)
        self.assertNotIn(marble_a, self.game.marbles)
        self.assertIn(marble_b, self.game.marbles)  # the other start's marble stays


    def test_erasing_non_start_block_keeps_marbles(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
        self.game.grid[(2, 1)] = main.Block(2, 1, scorer=main.Scorer.CHIPS_ADD)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(len(self.game.marbles), 1)

        self.game._erase_block_at(2, 1)

        self.assertEqual(len(self.game.marbles), 1)  # non-start erase leaves the marble
