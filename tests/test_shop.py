"""The shop, prices, buying, selling, assembly and the economy.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class ShopTests(GameTestCase):
    """The shop, prices, buying, selling, assembly and the economy."""


    def test_erasing_broken_fragile_block_refunds_original_shape(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        block.shape = main.Shape.NONE
        block._fragile_shape = main.Shape.RECT
        self.game.grid[(2, 3)] = block

        self.game._erase_block_at(2, 3)

        refunded = self.game.toolbox.items[-1]
        self.assertEqual(refunded.shape, main.Shape.RECT)


    def test_handle_events_places_assembled_block_on_grid_from_mouse_position(self):
        # Assemble a block from assigned components, then place it via a click.
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)
        self.game._assemble_block()
        self.assertTrue(self.game.has_selected)

        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1

        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((1, 1), self.game.grid)
        block = self.game.grid[(1, 1)]
        self.assertEqual(block.shape, main.Shape.RECT)
        self.assertEqual(block.effect, main.Effect.BOUNCY)
        self.assertEqual(block.scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(block.rect.x, main.MARBLE_BOX_COORDS[0] + main.GRID_SIZE)
        self.assertEqual(block.rect.y, main.MARBLE_BOX_COORDS[1] + main.GRID_SIZE)


    def test_cash_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.CASH, main.Scorer.ORDER)
        self.assertIn(main.Scorer.CASH, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.CASH), "Cash")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.CASH], 15)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CASH)], 0)
        self.assertIn("$15", main.scorer_description(main.Scorer.CASH, 15))


    def test_cash_breakdown_records_every_cash_source(self):
        # The breakdown splits a run's earnings into the flat base payment, the
        # interest on the cash held, the over-the-target score bonus, Cash
        # cards, and the Cash/Lucky scorers — and always adds up to the total.
        self.game.trials_enabled = False
        self.game.cash = 100  # -> $10 interest
        self.game.card_cash_run_gain = 15
        self.game.run_cash_gained = 40  # already paid out mid-run
        self.game.score_total = 100
        self.game.required_score = 10
        self.game._award_cash()
        breakdown = self.game.last_run_cash_breakdown
        score_cash = max(0, int(main.CASH_SCALE * (np.log(100) - np.log(10))))
        self.assertEqual(breakdown["base"], 20)
        self.assertEqual(breakdown["interest"], 10)
        self.assertEqual(breakdown["score"], score_cash)
        self.assertEqual(breakdown["cards"], 15)
        self.assertEqual(breakdown["scorers"], 40)
        self.assertEqual(self.game.last_run_cash_gained,
                         sum(breakdown.values()))
        self.assertEqual(self.game.cash, 100 + 20 + 10 + score_cash + 15)
        # A real retry (the results screen's RETRY) undoes the run, so its
        # breakdown goes with it. The save / quit / MAIN MENU paths call
        # _retry_run() too, but while building there is no finished run to
        # undo, so only this awaiting-after-run call rolls anything back.
        cash_before_retry = self.game.cash
        awarded = self.game.last_run_cash_gained
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.last_run_cash_breakdown, {})
        self.assertEqual(self.game.cash, cash_before_retry - awarded)


    def test_cash_breakdown_empty_before_the_first_run(self):
        self.game.last_run_cash_breakdown = {}
        rows = self.game._describe_item(main.CASH_BREAKDOWN)
        self.assertEqual([label for label, _ in rows], ["Last run"])
        self.assertIn("No run", rows[0][1])


    def test_sharp_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SHARP, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SHARP, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SHARP), "Sharp")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SHARP], 3)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SHARP)], 0)
        self.assertIn("destroy", main.scorer_description(main.Scorer.SHARP).lower())


    def test_resource_scorers_are_defined_and_shop_available(self):
        for scorer, name in ((main.Scorer.PARTS, "Parts"), (main.Scorer.SHREDS, "Shreds"),
                             (main.Scorer.RUBBLE, "Rubble"), (main.Scorer.IDEAS, "Ideas")):
            self.assertIn(scorer, main.Scorer.ORDER)
            self.assertIn(scorer, main.Scorer.SHOP_ORDER)
            self.assertEqual(main.Scorer.name(scorer), name)
            self.assertEqual(main.Scorer.DEFAULT_AMOUNT[scorer], 1)
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, scorer)], 0)
            self.assertTrue(main.scorer_description(scorer))


    def test_fresh_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.FRESH, main.Scorer.ORDER)
        self.assertIn(main.Scorer.FRESH, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.FRESH), "Fresh")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.FRESH], 1)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.FRESH)], 0)
        self.assertIn("reroll", main.scorer_description(main.Scorer.FRESH).lower())
        # Fresh is also a card scorer: every match group can offer it (a card
        # that grants a free reroll when the marble collides with the block).
        self.assertIn(main.Scorer.FRESH, components.CARD_SCORERS)
        self.assertIn(main.Scorer.FRESH, components.FLAT_CARD_SCORERS)
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.FRESH)
        self.assertGreaterEqual(value, components.MATCH_GROUP_CARD_OFFSET)
        self.assertEqual(components.match_group_card_meta(value),
                         (group, main.Scorer.FRESH))


    def test_fresh_scorer_gives_a_free_reroll_per_hit(self):
        # Fresh grants one free shop reroll IMMEDIATELY per trigger — its old
        # point system is gone (nothing is banked for a run).
        self.game.run_active = True
        for _ in range(3):
            block = main.Block(0, 0, scorer=main.Scorer.FRESH)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 3)


    def test_fresh_single_hit_reroll_is_immediate(self):
        # One Fresh hit is a full reroll right away; there is no partial bank
        # of "fresh points" that waits for a future run.
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 1)


    def test_free_reroll_refreshes_shop_without_cost_then_costs_again(self):
        # A banked free reroll makes the shop refresh cost $0 for one use;
        # after it is spent the usual $20 fee comes back.
        self.game.free_rerolls = 1
        self.game.cash = 0
        self.game._refresh_shop()
        self.assertEqual(self.game.free_rerolls, 0)
        self.assertEqual(self.game.cash, 0)  # no fee charged
        self.assertIn("Free reroll", self.game.shop_message)
        # No free reroll left: the refresh costs the normal fee again.
        self.game.cash = 60
        self.game._refresh_shop()
        self.assertEqual(self.game.cash, 60 - main.SHOP_REFRESH_COST)
        self.assertIn("Refreshed shop", self.game.shop_message)


    def test_picky_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.PICKY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.PICKY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.PICKY), "Picky")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.PICKY], 1)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.PICKY)], 0)
        self.assertIn("slot", main.scorer_description(main.Scorer.PICKY).lower())
        # Picky is also a card scorer: every match group can offer it (a card
        # that banks an option point when the marble collides with the block).
        self.assertIn(main.Scorer.PICKY, components.CARD_SCORERS)
        self.assertIn(main.Scorer.PICKY, components.FLAT_CARD_SCORERS)
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.PICKY)
        self.assertGreaterEqual(value, components.MATCH_GROUP_CARD_OFFSET)
        self.assertEqual(components.match_group_card_meta(value),
                         (group, main.Scorer.PICKY))


    def test_bonus_slots_add_extra_random_shop_offers(self):
        # Each banked slot adds one extra offer to the shop, of a uniformly
        # chosen kind (shape/effect/scorer/block/card/action).
        self.game.bonus_slots = 3
        self.game.shop.bonus_slots = 3
        self.game.shop.refresh()
        standard = [i for i in self.game.shop.items if i.row < 5]
        bonus = [i for i in self.game.shop.items if i.row >= 5]
        self.assertEqual(len(standard), 15)
        self.assertEqual(len(bonus), 3)
        allowed = {"shape", "effect", "scorer", "block", "card", "action"}
        for item in bonus:
            self.assertIn(getattr(item, "kind", "block"), allowed)


    def test_bonus_shop_offer_kinds_are_equally_likely(self):
        # Over many rolls, each of the six offer kinds appears a comparable
        # share of the time (each should be near 1/6 of the rolls).
        counts = {}
        for _ in range(1200):
            item = self.game.shop._random_offer(col=1, row=5)
            kind = getattr(item, "kind", "block")
            counts[kind] = counts.get(kind, 0) + 1
        self.assertEqual(sorted(counts), ["action", "block", "card", "effect",
                                          "scorer", "shape"])
        for kind, count in counts.items():
            self.assertGreater(count, 100)
            self.assertLess(count, 340)


    def test_retrying_a_run_takes_back_only_the_rerolls_that_run_granted(self):
        # A retry is a do-over of the FINISHED run, so exactly the free rerolls
        # that run's Fresh hits granted come off the bank — rerolls banked by
        # earlier runs are not the retried run's to lose.
        self.game.free_rerolls = 3  # banked by earlier runs
        self.game.free_rerolls_run_gain = 0
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 4)
        self.assertEqual(self.game.free_rerolls_run_gain, 1)
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(self.game.free_rerolls, 3)  # the other three stay
        self.assertEqual(self.game.free_rerolls_run_gain, 0)
        # A later mid-build call (the save/quit/menu path) can't take them
        # again: the finished run is already undone.
        self.game._retry_run()
        self.assertEqual(self.game.free_rerolls, 3)


    def test_a_retry_cannot_push_the_free_rerolls_below_zero(self):
        # Spending a run's rerolls before retrying does not un-spend them: the
        # bank simply can't go negative.
        self.game.free_rerolls = 0
        self.game.free_rerolls_run_gain = 0
        self.game.run_active = True
        for _ in range(2):
            block = main.Block(0, 0, scorer=main.Scorer.FRESH)
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls_run_gain, 2)
        self.game.free_rerolls = 0  # both were spent on shop rerolls
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._retry_run()

        self.assertEqual(self.game.free_rerolls, 0)
        # With no banked reroll the refresh charges its cash fee again.
        self.game.cash = 60
        self.game._refresh_shop()
        self.assertEqual(self.game.cash, 60 - main.SHOP_REFRESH_COST)


    def test_a_committed_run_keeps_its_rerolls_through_the_next_reset(self):
        # Each run counts only its own Fresh hits, and a run that has been
        # CONTINUE'd is settled: its counter is cleared at the commit (see
        # _continue_run), so building/starting the NEXT run cannot take that
        # run's rerolls back. Only a RESTARTED run hands its own back (see
        # test_restarting_a_run_takes_back_the_rerolls_its_blocks_granted).
        self.game.free_rerolls = 2
        self.game.free_rerolls_run_gain = 3  # the run being continued
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(self.game.free_rerolls_run_gain, 0)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.free_rerolls, 2)


    def test_restarting_a_run_takes_back_the_rerolls_its_blocks_granted(self):
        # A Fresh hit banks its reroll the moment it triggers, so restarting
        # the run hands that reroll back — while rerolls banked by earlier
        # runs stay, and one already spent is simply not un-spent.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.free_rerolls = 2  # banked by earlier runs
        self.game.free_rerolls_run_gain = 0
        self.game.run_active = True
        block = main.Block(1, 1, scorer=main.Scorer.FRESH)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.free_rerolls, 3)

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.free_rerolls, 2)
        self.assertEqual(self.game.free_rerolls_run_gain, 0)


    def test_leaving_before_a_run_finishes_keeps_the_free_rerolls(self):
        # Same rule as the point banks: saving/quitting/menu while building has
        # no finished run to undo, so a banked free reroll survives it.
        self.game.free_rerolls = 2
        self.game.run_complete = False
        self.game.awaiting_after_run = False

        self.game._retry_run()

        self.assertEqual(self.game.free_rerolls, 2)


    def test_a_new_run_keeps_the_free_rerolls(self):
        # Only a RETRY empties them; starting the next run (or restarting the
        # current one) leaves the bank alone, like the resource points.
        self.game.free_rerolls = 2
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run())

        self.assertEqual(self.game.free_rerolls, 2)


    def test_quick_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.QUICK, main.Scorer.ORDER)
        self.assertIn(main.Scorer.QUICK, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.QUICK), "Quick")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.QUICK)], 0)
        self.assertIn("fast", main.scorer_description(main.Scorer.QUICK).lower())


    def test_random_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.RANDOM, main.Scorer.ORDER)
        self.assertIn(main.Scorer.RANDOM, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.RANDOM), "Random")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.RANDOM)], 0)
        self.assertIn("35 chips", main.scorer_description(main.Scorer.RANDOM))


    def test_seed_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SEED, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SEED, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SEED), "Seed")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SEED], 3)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SEED)], 0)
        self.assertIn("Seed block", main.scorer_description(main.Scorer.SEED))


    def test_drill_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.DRILL, main.Scorer.ORDER)
        self.assertIn(main.Scorer.DRILL, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.DRILL), "Drill")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.DRILL)], 0)
        self.assertIn("locked", main.scorer_description(main.Scorer.DRILL))


    def test_lucky_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.LUCKY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.LUCKY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.LUCKY), "Lucky")
        self.assertEqual(main.Scorer.color(main.Scorer.LUCKY), (255, 185, 0))
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.LUCKY)], 0)
        desc = main.scorer_description(main.Scorer.LUCKY)
        self.assertIn("1/3", desc)
        self.assertIn("130", desc)
        self.assertIn("$40", desc)
        self.assertIn("1/9", desc)


    def test_a_new_run_rerolls_random_outputs(self):
        # Moving on to the NEXT run chooses fresh outcomes — while replaying the
        # SAME run (R, T) keeps the ones it already decided.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        block = main.Block(1, 0, scorer=main.Scorer.RANDOM)
        self.game.grid[(1, 0)] = block
        with mock.patch("main.random.random", return_value=0.9):  # xMult
            self.game.reset_run(True)
        self.assertEqual(block.random_rolls["reward"], 2)
        # Replaying the run (R / T, same run number) does not re-roll it, even
        # with the RNG rigged the other way.
        with mock.patch("main.random.random", return_value=0.0):
            self.game.reset_run(True)
        self.assertEqual(block.random_rolls["reward"], 2)
        # The next run decides afresh.
        self.game.run_number += 1
        with mock.patch("main.random.random", return_value=0.0):  # chips
            self.game.reset_run(True)
        self.assertEqual(block.random_rolls["reward"], 0)


    def test_roomy_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.ROOMY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.ROOMY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.ROOMY), "Roomy")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.ROOMY], 2)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.ROOMY)], 0)
        desc = main.scorer_description(main.Scorer.ROOMY, 2)
        self.assertIn("2 chips", desc)
        self.assertIn("unlocked board unit", desc)


    def test_roomy_gives_two_chips_per_unlocked_board_unit(self):
        # Roomy pays +2 chips for every unlocked board unit when touched.
        self.game.unlocked_cells = {(0, 0), (0, 1), (1, 0), (1, 1)}  # 4 units
        self.game.score_chips = 100
        block = main.Block(0, 0, scorer=main.Scorer.ROOMY)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, 100 + 2 * 4)
        self.assertEqual(block.triggers_left, 0)


    def test_rally_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.RALLY, main.Scorer.ORDER)
        self.assertIn(main.Scorer.RALLY, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.RALLY), "Rally")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.RALLY], 1)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.RALLY)], 0)
        desc = main.scorer_description(main.Scorer.RALLY, 1)
        self.assertIn("1 mult", desc)
        self.assertIn("fresh block touch", desc)


    def test_echo_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.ECHO, main.Scorer.ORDER)
        self.assertIn(main.Scorer.ECHO, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.ECHO), "Echo")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.ECHO], 0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.ECHO)], 0)
        self.assertIn("before it", main.scorer_description(main.Scorer.ECHO))


    def test_powerline_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.POWERLINE, main.Scorer.ORDER)
        self.assertIn(main.Scorer.POWERLINE, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.POWERLINE), "Powerline")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE], 25)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.POWERLINE)], 0)
        desc = main.scorer_description(main.Scorer.POWERLINE, 25)
        self.assertIn("25 chips", desc)
        self.assertIn("row", desc)


    def test_frontier_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.FRONTIER, main.Scorer.ORDER)
        self.assertIn(main.Scorer.FRONTIER, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.FRONTIER), "Frontier")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.FRONTIER], 3)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.FRONTIER)], 0)
        desc = main.scorer_description(main.Scorer.FRONTIER, 3)
        self.assertIn("3 mult", desc)
        self.assertIn("border", desc)
        self.assertIn("adjacent", desc)


    def test_cluster_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.CLUSTER, main.Scorer.ORDER)
        self.assertIn(main.Scorer.CLUSTER, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.CLUSTER), "Cluster")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.CLUSTER], 4)
        self.assertGreater(
            main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CLUSTER)], 0)
        desc = main.scorer_description(main.Scorer.CLUSTER, 4)
        self.assertIn("4 mult", desc)
        self.assertIn("adjacent", desc)
        # Like its geometry siblings (Powerline/Frontier), Cluster is a block
        # scorer, so it builds no magnitude card — but it IS a card scorer: a
        # generic card pays its payoff for the block the condition hands it.
        self.assertIn(main.Scorer.CLUSTER, components.CARD_SCORERS)
        self.assertIn(main.Scorer.CLUSTER, components.FLAT_CARD_SCORERS)


    def test_buying_a_lock_block_adds_a_matching_key(self):
        # A Key/Lock block is bought as a matched pair (like a portal): both
        # halves share a fresh key number and the pair costs one price.
        self.game.toolbox.items.clear()
        lock = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 30, "Lock Block")
        self.game.cash = 1000

        self.game._buy_shop_item(lock)

        halves = [i for i in self.game.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual(len(halves), 2)
        self.assertEqual({i.shape for i in halves},
                         {main.Shape.KEY, main.Shape.LOCK})
        self.assertEqual(halves[0].key_number, halves[1].key_number)
        self.assertGreater(halves[0].key_number, 0)
        self.assertEqual(self.game.cash, 1000 - lock.price)  # charged once
        self.assertNotIn(lock, self.game.toolbox.items)


    def test_buying_a_key_block_adds_a_matching_lock(self):
        # The other half works the same way round: a Key-shaped offer brings
        # its Lock.
        self.game.toolbox.items.clear()
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.CHIPS_ADD, 30, 40, "Key +Chips")
        self.game.cash = 1000

        self.game._buy_shop_item(key)

        halves = [i for i in self.game.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual({i.shape for i in halves},
                         {main.Shape.KEY, main.Shape.LOCK})
        # Both halves keep the offer's scorer.
        self.assertEqual({i.scorer for i in halves}, {main.Scorer.CHIPS_ADD})
        self.assertGreater(halves[0].key_number, 0)


    def test_buying_a_key_lock_pair_requires_two_free_slots(self):
        self.game.toolbox.items.clear()
        filler = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.NONE, 0, 5, "filler")
        while len(self.game.toolbox.items) < self.game.toolbox.cols * self.game.toolbox.rows - 1:
            self.game.toolbox.add(filler)
        lock = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 30, "Lock Block")
        self.game.cash = 1000

        self.game._buy_shop_item(lock)

        # Nothing is added and nothing is charged: a lone half is useless.
        self.assertEqual(len(self.game.toolbox.items),
                         self.game.toolbox.cols * self.game.toolbox.rows - 1)
        self.assertEqual(self.game.cash, 1000)
        self.assertTrue(self.game.shop_message)


    def test_assembling_a_lock_shape_adds_its_key_half(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.LOCK)
        scorer_c = main.Component.scorer_component(main.Scorer.NONE)
        for component in (shape_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        halves = [i for i in self.game.toolbox.items
                  if main.paired_shape(i.shape) is not None]
        self.assertEqual(len(halves), 2)
        self.assertEqual({i.shape for i in halves},
                         {main.Shape.KEY, main.Shape.LOCK})
        self.assertEqual(halves[0].key_number, halves[1].key_number)
        self.assertGreater(halves[0].key_number, 0)
        self.assertTrue(self.game.has_selected)  # one half is equipped


    def test_assembling_a_plain_shape_stays_a_single_block(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT)
        self.game.toolbox.add(shape_c)
        self.game._use_component(shape_c)

        self.game._assemble_block()

        self.assertEqual(len(self.game.toolbox.items), 1)
        self.assertEqual(self.game.toolbox.items[0].shape, main.Shape.RECT)


    def test_selling_a_key_half_deletes_its_lock(self):
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key", key_number=7)
        lock = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 10, "Lock", key_number=7)
        other = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 10, "Plain")
        for item in (key, lock, other):
            self.game.toolbox.add(item)

        self.game._equip_block(key)
        self.game._sell_selected_item()

        self.assertNotIn(key, self.game.toolbox.items)
        self.assertNotIn(lock, self.game.toolbox.items)  # the partner went too
        self.assertIn(other, self.game.toolbox.items)


    def test_disassembling_a_placed_lock_deletes_its_key(self):
        self.game.cash = 1000
        self.game.toolbox.items.clear()
        key = main.BlockItem(0, 0, main.Shape.KEY, main.Effect.NONE,
                             main.Scorer.NONE, 0, 10, "Key", key_number=9)
        self.game.toolbox.add(key)
        lock = main.Block(3, 3, shape=main.Shape.LOCK, key_number=9)
        self.game.grid[(3, 3)] = lock
        self.game._equip_block(lock)

        self.game._disassemble_block()

        self.assertNotIn((3, 3), self.game.grid)
        self.assertNotIn(key, self.game.toolbox.items)


    # --- Colossus / Undertaker / Debt ---------------------------------------

    def test_new_scorers_are_defined_and_shop_available(self):
        for scorer, name, amount in ((main.Scorer.COLOSSUS, "Colossus", 0.1),
                                     (main.Scorer.UNDERTAKER, "Undertaker", 15),
                                     (main.Scorer.DEBT, "Debt", 60)):
            self.assertIn(scorer, main.Scorer.ORDER)
            self.assertIn(scorer, main.Scorer.SHOP_ORDER)
            self.assertEqual(main.Scorer.name(scorer), name)
            self.assertEqual(main.Scorer.DEFAULT_AMOUNT[scorer], amount)
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.SCORER, scorer)], 0)
            self.assertTrue(main.scorer_description(scorer, amount))
            # Board/run/marble readers, so they build no magnitude card — but
            # they ARE card scorers: a generic card pays them from the block
            # its condition hands the card (see components.CARD_SCORERS).
            self.assertIn(scorer, components.CARD_SCORERS)
            self.assertIn(scorer, components.FLAT_CARD_SCORERS)


    def test_debt_cancels_the_interest_in_the_run_award(self):
        self.game.cash = 500  # would pay $50 of interest
        self.game.debt_run_triggered = True

        self._complete_run(10000, required=1)

        rows = self.game.last_run_cash_breakdown
        self.assertEqual(rows["interest"], 0)
        self.assertTrue(rows["debt"])
        self.assertIn("Debt", dict(self.game._cash_breakdown_rows())["Interest"])


    def test_interest_still_pays_without_a_debt_block(self):
        self.game.cash = 500

        self._complete_run(10000, required=1)

        rows = self.game.last_run_cash_breakdown
        self.assertEqual(rows["interest"], 50)
        self.assertFalse(rows["debt"])
        self.assertNotIn("Debt", dict(self.game._cash_breakdown_rows())["Interest"])


    def test_compound_interest_doubles_the_interest(self):
        self.game.cards.append(main.CardItem(main.Card.COMPOUND_INTEREST, 36))
        self.game.cash = 500  # $1 per $10 would pay $50

        self._complete_run(10000, required=1)

        rows = self.game.last_run_cash_breakdown
        self.assertEqual(rows["interest"], 100)
        # The doubled interest really landed in the cash award.
        self.assertEqual(self.game.cash, 500 + rows["base"] + rows["interest"]
                         + rows["score"] + rows["cards"] + rows["scorers"])
        self.assertTrue(rows["debt"] is False)


    def test_debt_still_cancels_compound_interest(self):
        self.game.cards.append(main.CardItem(main.Card.COMPOUND_INTEREST, 36))
        self.game.cash = 500
        self.game.debt_run_triggered = True

        self._complete_run(10000, required=1)

        self.assertEqual(self.game.last_run_cash_breakdown["interest"], 0)


    def test_coupon_discounts_shop_options_but_not_board_units(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 40, "B")
        card = main.CardItem(main.Card.GARDEN, 40)
        component = main.Component.shape_component(main.Shape.RECT)
        self.assertEqual(self.game._buy_price(block), 40)
        self.assertEqual(self.game._buy_price(card), 40)
        self.assertEqual(self.game._buy_price(component), component.price)

        self.game.cards.append(main.CardItem(main.Card.COUPON, 46))

        self.assertEqual(self.game._buy_price(block), 30)     # 40 x 0.75
        self.assertEqual(self.game._buy_price(card), 30)
        self.assertEqual(self.game._buy_price(component),
                         int(component.price * 0.75))
        # Board Units are bought through their own tile, so they are exempt.
        self.assertEqual(self.game._board_unit_price(), main.BOARD_UNIT_PRICE)
        self.game.cash = 100
        self.game._buy_board_unit()
        self.assertEqual(self.game.cash, 100 - main.BOARD_UNIT_PRICE)


    def test_mineshaft_makes_board_units_cost_five(self):
        self.assertEqual(self.game._board_unit_price(), 8)

        self.game.cards.append(main.CardItem(main.Card.MINESHAFT, 28))

        self.assertEqual(self.game._board_unit_price(), 5)
        self.game.cash = 5
        self.game._buy_board_unit()
        self.assertEqual(self.game.board_units, 1)
        self.assertEqual(self.game.cash, 0)
        # And $4 is no longer enough.
        self.game.cash = 4
        self.game._buy_board_unit()
        self.assertEqual(self.game.board_units, 1)
        self.assertEqual(self.game.cash, 4)


    def test_market_raises_the_sale_refund_to_three_quarters(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 40, "B")
        self.game.toolbox.add(block)
        self.game.cash = 0
        self.game._equip_block(block)
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, 20)  # half by default

        self.game.cards.append(main.CardItem(main.Card.MARKET, 26))
        marker = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                main.Scorer.NONE, 0, 40, "M")
        self.game.toolbox.add(marker)
        self.game._equip_block(marker)
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, 20 + 30)  # 40 x 0.75

        # Cards refund the same fraction.
        card = main.CardItem(main.Card.GARDEN, 40)
        self.game.cards.append(card)
        self.game.selected_toolbox_item = card
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, 50 + 30)
        self.assertNotIn(card, self.game.cards)


    def test_selling_essence_distils_two_permanent_tokens(self):
        random.seed(11)
        self.game.cards = [main.CardItem(main.Card.ESSENCE, 48)]
        self.game.selected_toolbox_item = self.game.cards[0]

        self.game._sell_selected_item()

        self.assertEqual(len(self.game.tokens), main.ESSENCE_TOKENS)
        self.assertIn("Spirit token", self.game.shop_message)
        # Random: the shop's scorers (never a run role, never the no-scorer
        # NONE), each with its own rolled magnitude and like a random block.
        shop_scorers = [s for s in main.Scorer.SHOP_ORDER
                        if s not in (main.Scorer.START, main.Scorer.FINISH,
                                     main.Scorer.NONE)]
        for token in self.game.tokens:
            self.assertIn(token.scorer, shop_scorers)
            self.assertIsNone(token.runs_left)  # permanent
            average = main.Scorer.DEFAULT_AMOUNT[token.scorer]
            self.assertGreaterEqual(token.scorer_amount,
                                    main.scorer_magnitude_floor(token.scorer))
            self.assertLessEqual(token.scorer_amount,
                                 average + main.magnitude_step(average)
                                 * main.MAGNITUDE_MAX_STEPS)
            self.assertTrue(set(token.effects) <= set(main.Effect.REAL_ORDER))
        # A permanent token survives a run (its scorer's own self-destruction
        # rules aside), so the distils really are for every run after this one.
        keeper = [t for t in self.game.tokens
                  if t.scorer not in (main.Scorer.SATANIC, main.Scorer.SHARP)]
        self.assertTrue(keeper)
        self.game.tokens = keeper
        for token in self.game.tokens:
            token.fired = True
        self.game._advance_tokens()
        self.assertEqual(len(self.game.tokens), len(keeper))
        # The rolls are random: selling several Essences gives different keeps.
        scorers = set()
        for _ in range(6):
            self.game.tokens = []
            self.game.cards = [main.CardItem(main.Card.ESSENCE, 48)]
            self.game.selected_toolbox_item = self.game.cards[0]
            self.game._sell_selected_item()
            scorers.update(t.scorer for t in self.game.tokens)
        self.assertGreater(len(scorers), 2)


    def test_selling_essence_stops_at_a_full_token_column(self):
        # Only the tokens that fit are distilled, and the sale says so.
        self.game.tokens = [main.ScorerToken(main.Scorer.CASH, 15, runs_left=None)
                            for _ in range(main.MAX_TOKENS - 1)]
        self.game.cards = [main.CardItem(main.Card.ESSENCE, 48)]
        self.game.selected_toolbox_item = self.game.cards[0]

        self.game._sell_selected_item()

        self.assertEqual(len(self.game.tokens), main.MAX_TOKENS)
        self.assertIn("1 permanent Spirit token", self.game.shop_message)
        # A completely full column has no room at all, and the sale still works.
        self.game.cards = [main.CardItem(main.Card.ESSENCE, 48)]
        self.game.selected_toolbox_item = self.game.cards[0]
        self.game._sell_selected_item()

        self.assertEqual(len(self.game.tokens), main.MAX_TOKENS)
        self.assertEqual(self.game.cards, [])
        self.assertIn("no room", self.game.shop_message)


    def test_buying_concert_mid_run_leaves_the_dealt_triggers_alone(self):
        # The card raises the LIMIT; a trigger already dealt is not handed out
        # again (the same rule the paid trigger upgrade follows). The next refill
        # brings the extra one.
        block = self._concert_block()
        self.game.grid[(1, 5)] = main.Block(1, 5, scorer=main.Scorer.START)
        self.game.grid[(1, 9)] = main.Block(1, 9, scorer=main.Scorer.FINISH)
        self.game.reset_run()
        self.assertEqual(block.triggers_left, 1)

        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]

        self.assertEqual(self.game._trigger_limit(block), 2)   # the limit moved
        self.assertEqual(block.triggers_left, 1)               # the dealt one did not
        self.game.reset_run()
        self.assertEqual(block.triggers_left, 2)


    def test_selling_or_cutting_concert_takes_the_extra_trigger_away(self):
        block = self._concert_block()
        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]
        self.game.grid[(1, 5)] = main.Block(1, 5, scorer=main.Scorer.START)
        self.game.grid[(1, 9)] = main.Block(1, 9, scorer=main.Scorer.FINISH)
        self.game.reset_run()
        self.assertEqual(block.triggers_left, 2)

        # The Card cutter trial silences the card like any other passive card,
        # so the blocks fall back to their own limit (nothing was written to
        # them, so nothing has to be undone).
        self.game.disabled_card = self.game.cards[0]
        self.assertEqual(self.game._trigger_limit(block), 1)
        self.assertEqual(self.game._item_name(block), "Bouncy Pipe +Chips v1")

        self.game.disabled_card = None
        self.assertEqual(self.game._trigger_limit(block), 2)
        # Selling it does the same for good (and the trigger it already dealt
        # stays for this run).
        self.game.selected_toolbox_item = self.game.cards[0]
        self.game._sell_selected_item()
        self.assertEqual(self.game.cards, [])
        self.assertEqual(self.game._trigger_limit(block), 1)
        self.assertEqual(block.triggers_left, 2)


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_board_sell_total_adds_up_each_blocks_sell_price(self):
        priced = main.Block(0, 5, scorer=main.Scorer.NONE)
        priced.resale_price = 30
        self.game.grid[(0, 5)] = priced
        plain = main.Block(1, 5, scorer=main.Scorer.NONE)
        self.game.grid[(1, 5)] = plain
        expected = 30 + main.block_price_for(plain.shape, plain.effects,
                                             plain.scorer)

        self.assertEqual(main.cards.board_sell_total(self.game), expected)
        # An assembled-from-nothing block is worth $0.
        free = main.Block(2, 5, scorer=main.Scorer.NONE)
        free.resale_price = 0
        self.game.grid[(2, 5)] = free
        self.assertEqual(main.cards.board_sell_total(self.game), expected)


    # --- Card magnitudes: a card carries its scorer half's own roll -------

    def test_shop_cards_with_a_scorer_half_roll_a_magnitude(self):
        # A composed card offer (condition x scorer) comes with the scorer
        # half's own rolled magnitude, priced for it; a whole card (Coupon,
        # Showman, ...) has no scorer half and carries none.
        seen = set()
        for _ in range(40):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if getattr(item, "kind", None) != "card":
                    continue
                with self.subTest(card=main.Card.name(item.value)):
                    scorer = main.card_scorer(item.value)
                    if scorer is None:
                        self.assertEqual(item.amount, 0)
                        self.assertEqual(item.price, main.Card.PRICES.get(item.value, 20))
                        continue
                    average = main.Scorer.DEFAULT_AMOUNT[scorer]
                    step = main.magnitude_step(average)
                    if not step:
                        self.assertEqual(item.amount, average)
                    else:
                        floor = main.scorer_magnitude_floor(scorer)
                        self.assertGreaterEqual(item.amount, floor)
                        self.assertLessEqual(item.amount,
                                             average + step * main.MAGNITUDE_MAX_STEPS)
                        self.assertEqual(item.amount, round(item.amount, 9))
                    seen.add(item.amount)
                    self.assertEqual(item.price, main.card_price_for(item.value))
        # The rolls really vary (a flat average would give one value).
        self.assertGreater(len(seen), 1)


    def test_card_description_follows_the_magnitude_but_its_price_does_not(self):
        value = main.match_group_card(main.match_group_for_shape(main.Shape.PIPE),
                                      main.Scorer.CHIPS_ADD)
        catalog = main.Card.PRICES[value]
        strong = main.make_card_item(value, amount=45)
        weak = main.make_card_item(value, amount=15)

        # The roll shows in what the card pays and says...
        rows = dict(self.game._describe_item(strong))
        text = rows[f"Card - {main.Card.name(value)}"]
        self.assertIn("+45 chips (+15)", text)
        # ...but never in what it costs.
        self.assertEqual(strong.price, catalog)
        self.assertEqual(weak.price, catalog)
        self.assertEqual(strong.price, main.card_price_for(value))
        # A whole card keeps its catalog text and price.
        coupon = main.make_card_item(main.Card.COUPON)
        self.assertEqual(coupon.amount, 0)
        self.assertEqual(coupon.price, main.Card.PRICES[main.Card.COUPON])
        self.assertEqual(dict(self.game._describe_item(coupon))
                         [f"Card - {main.Card.name(main.Card.COUPON)}"],
                         main.Card.description(main.Card.COUPON))


    def test_the_death_action_cannot_sell_the_last_role_block(self):
        action = main.ActionItem(main.Action.DEATH, 48)
        self.game.toolbox.items.clear()
        start = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = start
        self.game.cash = 0

        self.assertFalse(self.game._action_death(action, start))
        self.assertIn((3, 3), self.game.grid)
        self.assertEqual(self.game.cash, 0)
        self.assertIn("can't be sold", self.game.shop_message)

        # Death can still sell a spare role block...
        spare = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 109, "Start Block", effects=[])
        self.game.toolbox.add(spare)
        self.assertTrue(self.game._action_death(action, start))
        self.assertNotIn((3, 3), self.game.grid)
        self.assertGreater(self.game.cash, 100)  # 1.5x a ~$109 role block

        # ...and an ordinary block as before.
        self.game.cash = 0
        plain = main.Block(4, 3, scorer=main.Scorer.NONE)
        self.game.grid[(4, 3)] = plain
        self.assertTrue(self.game._action_death(action, plain))
        self.assertNotIn((4, 3), self.game.grid)
        self.assertGreater(self.game.cash, 0)


    def test_unsellable_covers_role_blocks_and_their_scorer_components(self):
        self.assertTrue(self.game._unsellable(
            main.Block(0, 0, scorer=main.Scorer.START)))
        self.assertTrue(self.game._unsellable(
            main.Block(0, 0, scorer=main.Scorer.FINISH)))
        self.assertTrue(self.game._unsellable(
            main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                           main.Scorer.START, 0, 0, "Start")))
        self.assertTrue(self.game._unsellable(
            main.Component.scorer_component(main.Scorer.START)))
        self.assertTrue(self.game._unsellable(
            main.Component.scorer_component(main.Scorer.FINISH)))
        # Ordinary items are sellable as before.
        self.assertFalse(self.game._unsellable(
            main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD)))
        self.assertFalse(self.game._unsellable(
            main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                           main.Scorer.NONE, 0, 20, "Plain")))
        self.assertFalse(self.game._unsellable(
            main.Component.scorer_component(main.Scorer.CHIPS_ADD)))
        self.assertFalse(self.game._unsellable(main.CardItem(main.Card.GARDEN, 36)))


    # --- The roles are priced shop goods -----------------------------------

    def test_run_roles_are_priced_shop_goods(self):
        self.assertIn(main.Scorer.START, main.Scorer.SHOP_ORDER)
        self.assertIn(main.Scorer.FINISH, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.START)], 140)
        self.assertEqual(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.FINISH)], 65)
        # A role block is a plain Rect, so its price is the ordinary block
        # formula over Rect + the role (75% of 6 + 0 + role).
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.START), 109)
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.FINISH), 53)
        # Rarity is the inverse of price: Start is the rarer of the two roles.
        self.assertLess(main.component_weight(main.Component.SCORER, main.Scorer.START),
                        main.component_weight(main.Component.SCORER, main.Scorer.FINISH))


    def test_the_starter_role_blocks_match_the_shop_offer(self):
        roles = [item for item in self.game.toolbox.items
                 if getattr(item, "scorer", None) in (main.Scorer.START, main.Scorer.FINISH)]

        self.assertEqual([role.scorer for role in roles],
                         [main.Scorer.START, main.Scorer.FINISH])
        for role in roles:
            self.assertEqual(role.shape, main.Shape.RECT)
            self.assertEqual(role.effects, [])
            self.assertEqual(role.price,
                             main.block_price_for(main.Shape.RECT, [], role.scorer))


    def test_shop_scorer_slots_offer_role_blocks(self):
        def fake_sample(options, weights, k):
            # The scorer slot's pool is the only one holding the role scorers.
            if main.Scorer.START in options:
                return [main.Scorer.START, main.Scorer.FINISH]
            return options[:k]

        with mock.patch("main.weighted_sample_without_replacement", side_effect=fake_sample):
            self.game.shop.refresh()

        roles = [item for item in self.game.shop.items
                 if getattr(item, "scorer", None) in (main.Scorer.START, main.Scorer.FINISH)]
        self.assertEqual([role.scorer for role in roles],
                         [main.Scorer.START, main.Scorer.FINISH])
        for role in roles:
            self.assertEqual(role.shape, main.Shape.RECT)
            self.assertEqual(role.effects, [])
            self.assertNotIn(role.kind, (main.Component.SCORER, "card", "action"))


    def test_gilded_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.GILDED, main.Scorer.ORDER)
        self.assertIn(main.Scorer.GILDED, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.GILDED), "Gilded")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.GILDED], 0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.GILDED)], 0)
        self.assertIn("1/6", main.scorer_description(main.Scorer.GILDED))


    def test_bomb_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.BOMB, main.Scorer.ORDER)
        self.assertIn(main.Scorer.BOMB, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.BOMB), "Bomb")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.BOMB], 0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.BOMB)], 0)
        desc = main.scorer_description(main.Scorer.BOMB)
        self.assertIn("after a run", desc)
        self.assertIn("within 1", desc)


    def test_rigged_casino_reweights_random_blocks(self):
        # With the Rigged Casino card, Random blocks roll chips:mult:xMult at
        # 1:3:9 odds instead of the even thirds.
        self.game.cards.append(main.CardItem(main.Card.RIGGED_CASINO, 48))

        def trigger(roll):
            block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
            self.game.grid[(0, 0)] = block
            marble = self._add_marble()
            marble.collisions_this_tick = [block]
            self.game.run_active = True
            with mock.patch("main.random.random", return_value=roll):
                self.game._handle_block_contacts([block])
            return block

        # roll 0.05 (< 1/13) -> +35 chips.
        self.game.score_chips = 100
        self.game.score_mult = 2
        trigger(0.05)
        self.assertEqual(self.game.score_chips, 135)
        # roll 0.2 (< 4/13) -> +5 mult.
        trigger(0.2)
        self.assertAlmostEqual(self.game.score_mult, 7)
        # roll 0.5 (>= 4/13) -> the favored +0.3 xMult (x1.3).
        self.game.score_mult = 2
        trigger(0.5)
        self.assertAlmostEqual(self.game.score_mult, 2 * 1.3)


    def test_effective_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.EFFECTIVE, main.Scorer.ORDER)
        self.assertIn(main.Scorer.EFFECTIVE, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.EFFECTIVE), "Effective")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.EFFECTIVE], 2.0)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.EFFECTIVE)], 0)
        self.assertIn("2 or more effects", main.scorer_description(main.Scorer.EFFECTIVE))


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_every_condition_and_component_has_a_price(self):
        # A component missing from COMPONENT_PRICES is priced 0, which makes it
        # free in the shop and the most common draw (rarity weight = 1/price).
        for condition in main.CONDITION_ORDER:
            price = main.COMPONENT_PRICES.get((main.Component.CONDITION, condition))
            self.assertIsNotNone(price,
                                 f"{main.Condition.name(condition)} has no price")
            self.assertGreater(price, 0,
                               f"{main.Condition.name(condition)} is priced 0")
            self.assertGreater(main.component_weight(main.Component.CONDITION, condition),
                               0)
        for shape in main.Shape.ORDER:
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)
        for effect in main.Effect.ORDER:
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, effect)], 0)
        for scorer in main.Scorer.ORDER:
            self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, scorer)], 0)


    def test_shop_refresh_costs_and_rerolls(self):
        self.game.cash = 100
        before = [item.name for item in self.game.shop.items]

        self.game._refresh_shop()

        self.assertEqual(self.game.cash, 100 - main.SHOP_REFRESH_COST)
        self.assertNotEqual([item.name for item in self.game.shop.items], before)


    def test_shop_refresh_fails_without_enough_cash(self):
        self.game.cash = main.SHOP_REFRESH_COST - 1
        before = [item.name for item in self.game.shop.items]

        self.game._refresh_shop()

        self.assertEqual(self.game.cash, main.SHOP_REFRESH_COST - 1)
        self.assertEqual([item.name for item in self.game.shop.items], before)
        self.assertTrue(self.game.shop_message)


    def test_f_key_disassembles_selected_block(self):
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.GRAVITY,
                               main.Scorer.CHIPS_ADD, 10, 20, "Circle +Chips")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self.game._disassemble_block()

        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)
        self.assertNotIn(block, self.game.toolbox.items)
        kinds = {item.kind for item in self.game.toolbox.items}
        self.assertEqual(kinds, {main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER})
        shapes = [item.value for item in self.game.toolbox.items if item.kind == main.Component.SHAPE]
        self.assertEqual(shapes, [main.Shape.CIRCLE])


    def test_f_key_disassembles_placed_block(self):
        placed = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.game.toolbox.items.clear()
        self.game.grid[(2, 3)] = placed
        self.game._select_placed_block(placed)
        self.game.cash = 100

        self.game._disassemble_block()

        self.assertNotIn((2, 3), self.game.grid)
        kinds = {item.kind for item in self.game.toolbox.items}
        self.assertEqual(kinds, {main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER})
        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)


    def test_disassemble_fails_without_enough_cash(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = main.DISASSEMBLE_COST - 1

        self.game._disassemble_block()

        self.assertEqual(self.game.cash, main.DISASSEMBLE_COST - 1)
        self.assertIn(block, self.game.toolbox.items)
        self.assertTrue(self.game.shop_message)


    def test_disassemble_requires_selected_block(self):
        self.game.cash = 100
        self.game.selected_toolbox_item = None
        self.game._disassemble_block()
        self.assertTrue(self.game.shop_message)


    def test_s_key_presses_disassemble_selected_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.GRAVITY,
                               main.Scorer.CHIPS_ADD, 10, 20, "Circle +Chips")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self._press(main.pygame.K_s)

        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)
        self.assertNotIn(block, self.game.toolbox.items)
        parts = [i for i in self.game.toolbox.items if i.kind != "block"]
        self.assertEqual(len(parts), 3)


    def test_clicking_shop_unselects_selected_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        shop = self.game.shop.items[0]
        pos = (self.game.shop.rect.x + shop.col * main.GRID_SIZE + 5,
               self.game.shop.rect.y + shop.row * main.GRID_SIZE + 5)

        self._click(pos)

        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertFalse(self.game.has_selected)


    def test_assembling_keeps_new_block_selected(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertTrue(self.game.has_selected)  # fresh block stays selected
        self.assertIsNotNone(self.game.selected_toolbox_item)
        self.assertEqual(self.game.selected_toolbox_item.kind, "block")


    def test_info_target_at_finds_shop_toolbox_and_grid(self):
        shop = self.game.shop.items[0]
        target, source = self.game._info_target_at(
            (self.game.shop.rect.x + shop.col * main.GRID_SIZE + 5,
             self.game.shop.rect.y + shop.row * main.GRID_SIZE + 5))
        self.assertIs(target, shop)
        self.assertEqual(source, "shop")

        tb = self.game.toolbox.items[0]
        target, source = self.game._info_target_at(
            (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5))
        self.assertIs(target, tb)
        self.assertEqual(source, "toolbox")

        block = main.Block(2, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(2, 3)] = block
        target, source = self.game._info_target_at((block.rect.centerx, block.rect.centery))
        self.assertIs(target, block)
        self.assertEqual(source, "grid")


    def test_left_clicking_shop_item_buys_it(self):
        self.game.toolbox.items.clear()
        item = self.game.shop.items[0]
        cash_before = self.game.cash
        pos = (self.game.shop.rect.x + item.col * main.GRID_SIZE + main.GRID_SIZE // 2,
               self.game.shop.rect.y + item.row * main.GRID_SIZE + main.GRID_SIZE // 2)

        self._click(pos)

        self.assertLess(self.game.cash, cash_before)  # left-click buys the item


    def test_selling_selected_block_refunds_half_price(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game._equip_block(block)  # select the block from the toolbox
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + block.price // 2)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertFalse(self.game.has_selected)
        self.assertTrue(self.game.shop_message)


    def test_selling_component_refunds_half_price(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game.selected_toolbox_item = comp
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + comp.price // 2)
        self.assertNotIn(comp, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertTrue(self.game.shop_message)


    def test_selling_without_selected_item_does_nothing(self):
        self.game.selected_toolbox_item = None
        self.game.cash = 50
        before = len(self.game.toolbox.items)

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50)
        self.assertEqual(len(self.game.toolbox.items), before)


    def test_b_key_sells_selected_block(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.cash = 50

        self._press(main.pygame.K_b)

        self.assertEqual(self.game.cash, 50 + block.price // 2)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_toolbox_item)


    def test_b_key_sells_selected_component(self):
        comp = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp)
        self.game.cash = 50

        self._press(main.pygame.K_b)

        self.assertEqual(self.game.cash, 50 + comp.price // 2)
        self.assertNotIn(comp, self.game.toolbox.items)


    def test_clicking_owned_card_selects_it_for_selling(self):
        # Left-clicking an owned card selects it as the active item, so pressing
        # B sells it for half its original price.
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        self.game.cards.append(card)
        x = main.CARD_AREA_COORDS[0] + main.GRID_SIZE // 2
        y = main.CARD_AREA_COORDS[1] + main.GRID_SIZE // 2
        self._click((x, y))
        self.assertIs(self.game.selected_toolbox_item, card)


    def test_b_key_sells_selected_card_for_half_price(self):
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        self.game.cards.append(card)
        self.game.cash = 50
        self.game.selected_toolbox_item = card

        self._press(main.pygame.K_b)

        self.assertNotIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 50 + card.price // 2)
        self.assertIsNone(self.game.selected_toolbox_item)


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_s_key_disassembles_splittable_card_into_halves(self):
        # Pressing S on a selected splittable card (e.g. Joker = START x
        # +Mult) pays $70 and returns its condition + scorer to the toolbox.
        self.game.toolbox.items.clear()
        card = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(card)
        self.game.cash = 100
        self.game.selected_toolbox_item = card
        before = len(self.game.toolbox.items)

        self._press(main.pygame.K_s)

        self.assertNotIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100 - main.CARD_DISASSEMBLE_COST)
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertEqual(len(self.game.toolbox.items), before + 2)
        kinds = sorted(i.kind for i in self.game.toolbox.items)
        self.assertEqual(kinds, ["condition", "scorer"])
        condition = next(i for i in self.game.toolbox.items if i.kind == "condition")
        scorer = next(i for i in self.game.toolbox.items if i.kind == "scorer")
        self.assertEqual(condition.value, main.Condition.START)
        self.assertEqual(scorer.value, main.Scorer.MULT_ADD)


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_s_key_cannot_disassemble_whole_card(self):
        # Whole cards (ERR 404 / Blueprint / Showman) have no halves to split.
        card = main.CardItem(main.Card.BLUEPRINT, 35)
        self.game.cards.append(card)
        self.game.cash = 100
        self.game.selected_toolbox_item = card
        self._press(main.pygame.K_s)
        self.assertIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100)
        self.assertIn("cannot be split", self.game.shop_message)


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_s_key_card_disassemble_requires_cash(self):
        card = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(card)
        self.game.cash = main.CARD_DISASSEMBLE_COST - 1
        self.game.selected_toolbox_item = card
        self._press(main.pygame.K_s)
        self.assertIn(card, self.game.cards)  # nothing happened
        self.assertEqual(self.game.cash, main.CARD_DISASSEMBLE_COST - 1)
        self.assertIn("Need $", self.game.shop_message)


    def test_assembling_only_a_scorer_defaults_shape_and_effect(self):
        # A lone +Chips scorer assembles a plain Rect +Chips block (the shape
        # defaults to Rect and the effect to None).
        self.game.toolbox.items.clear()
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        self.game.toolbox.add(scorer)
        self.game._use_component(scorer)

        self.game._assemble_block()

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.RECT)   # default shape
        self.assertEqual(blocks[0].effect, main.Effect.NONE)  # default effect
        self.assertEqual(blocks[0].scorer, main.Scorer.CHIPS_ADD)
        self.assertEqual(blocks[0].scorer_amount, 10)
        self.assertNotIn(scorer, self.game.toolbox.items)  # consumed
        # The block is worth 75% of its parts, and the +Chips piece is priced
        # for its OWN magnitude (10 chips, well below the 30 average, is a
        # cheap scorer).
        self.assertEqual(
            blocks[0].price, int(main.scorer_component_price(main.Scorer.CHIPS_ADD) * 0.75))


    def test_assembling_partial_parts_defaults_the_rest(self):
        # A lone effect makes a Rect block with that effect and no scorer.
        self.game.toolbox.items.clear()
        eff = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(eff)
        self.game._use_component(eff)
        self.game._assemble_block()
        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.RECT)   # default shape
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)
        self.assertEqual(blocks[0].scorer, main.Scorer.NONE)  # default scorer

        # A lone shape makes a plain effect-less, scorer-less block of it.
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.SLOPE)
        self.game.toolbox.add(shape_c)
        self.game._use_component(shape_c)
        self.game._assemble_block()
        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.SLOPE)
        self.assertEqual(blocks[0].effect, main.Effect.NONE)
        self.assertEqual(blocks[0].scorer, main.Scorer.NONE)


    def test_s_key_assembles_when_components_assigned(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self._press(main.pygame.K_s)

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)
        self.assertTrue(self.game.has_selected)  # the fresh block is equipped
        # Assigned components were consumed by assembly.
        self.assertNotIn(shape_c, self.game.toolbox.items)
        self.assertNotIn(effect_c, self.game.toolbox.items)
        self.assertNotIn(scorer, self.game.toolbox.items)


    def test_s_key_disassembles_when_block_selected(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.GRAVITY,
                               main.Scorer.CHIPS_ADD, 10, 20, "Circle +Chips")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self._press(main.pygame.K_s)

        self.assertEqual(self.game.cash, 100 - main.DISASSEMBLE_COST)
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind != "block"]), 3)


    def test_s_key_with_nothing_assembles_plain_wall(self):
        # Pressing S with no parts assigned and nothing selected builds the
        # plain default block: a Rect wall with no effect and no scorer.
        self.game.toolbox.items.clear()
        self.game.selected_toolbox_item = None
        self.game.assembler.clear()

        self._press(main.pygame.K_s)

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.RECT)
        self.assertEqual(blocks[0].effect, main.Effect.NONE)
        self.assertEqual(blocks[0].scorer, main.Scorer.NONE)
        self.assertEqual(blocks[0].price, 0)  # free defaults are worth nothing


    def test_selecting_component_assigns_it_to_assembler(self):
        comp = main.Component.shape_component(main.Shape.SLOPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)

        self.game._select_toolbox_component(comp)

        self.assertIs(self.game.selected_toolbox_item, comp)
        self.assertIs(self.game.assembler.shape, comp)  # assigned on selection
        self.assertIn(comp, self.game.toolbox.items)  # stays in the toolbox
        self.assertFalse(self.game.has_selected)


    def test_selling_assigned_component_refunds_half_and_unassigns(self):
        comp = main.Component.shape_component(main.Shape.SLOPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(comp)
        self.game._select_toolbox_component(comp)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + comp.price // 2)
        self.assertIsNone(self.game.assembler.shape)  # unassigned when sold
        self.assertIsNone(self.game.selected_toolbox_item)
        self.assertTrue(self.game.shop_message)


    def test_assembler_has_parts_when_any_part_assigned(self):
        self.game.assembler.clear()
        self.assertFalse(self.game.assembler.has_parts())
        self.game.assembler.shape = main.Component.shape_component(main.Shape.RECT)
        self.assertTrue(self.game.assembler.has_parts())
        self.game.assembler.clear()
        self.game.assembler.effects = [main.Component.effect_component(main.Effect.BOUNCY)]
        self.assertTrue(self.game.assembler.has_parts())
        self.game.assembler.clear()
        self.game.assembler.scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        self.assertTrue(self.game.assembler.has_parts())


    def test_buying_component_adds_to_toolbox_and_deducts_cash(self):
        component = next(item for item in self.game.shop.items if item.kind != "block")
        self.game.cash = 1000

        self.game._buy_shop_item(component)

        self.assertIn(component, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 1000 - component.price)


    def test_shop_purchase_fails_without_enough_cash(self):
        item = self.game.shop.items[0]
        self.game.cash = item.price - 1

        self.game._buy_shop_item(item)

        self.assertEqual(self.game.cash, item.price - 1)
        self.assertTrue(self.game.shop_message)


    def test_buying_plays_coin_sound(self):
        # Every successful purchase clinks coins.
        component = next(item for item in self.game.shop.items
                         if item.kind not in ("block", "card"))
        self.game.cash = 1000
        with mock.patch("main.sounds.play_coin") as play:
            self.game._buy_shop_item(component)
        play.assert_called_once()


    def test_buying_without_enough_cash_does_not_play_sound(self):
        # A failed purchase (not enough cash) makes no coin sound.
        item = self.game.shop.items[0]
        self.game.cash = 0
        with mock.patch("main.sounds.play_coin") as play:
            self.game._buy_shop_item(item)
        play.assert_not_called()


    def test_assembling_plays_mech_sound(self):
        # Assembling a block whirs and crunches.
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer):
            self.game.toolbox.add(component)
            self.game._use_component(component)
        with mock.patch("main.sounds.play_mech") as play:
            self.game._assemble_block()
        play.assert_called_once()


    def test_disassembling_plays_mech_sound(self):
        # Disassembling a block whirs and crunches too.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 1000
        with mock.patch("main.sounds.play_mech") as play:
            self.game._disassemble_block()
        play.assert_called_once()


    def test_shop_item_at_hits_item_cell(self):
        item = self.game.shop.items[0]
        pos = (self.game.shop.rect.x + item.col * main.GRID_SIZE + 5,
               self.game.shop.rect.y + item.row * main.GRID_SIZE + 5)

        self.assertIs(self.game.shop.item_at(pos), item)
        self.assertIsNone(self.game.shop.item_at((self.game.shop.rect.x - 10, self.game.shop.rect.y - 10)))


    def test_shop_sells_individual_components(self):
        kinds = {item.kind for item in self.game.shop.items}

        self.assertIn(main.Component.SHAPE, kinds)
        self.assertIn(main.Component.EFFECT, kinds)
        self.assertIn(main.Component.SCORER, kinds)


    def test_shop_sells_blocks(self):
        blocks = [item for item in self.game.shop.items if item.kind == "block"]

        self.assertGreater(len(blocks), 0)
        self.assertTrue(all(item.shape is not None and item.effect is not None and item.scorer is not None
                            for item in blocks))


    def test_shop_has_two_blocks_two_of_each_component_and_four_cards(self):
        kinds = [item.kind for item in self.game.shop.items]

        self.assertEqual(len(self.game.shop.items), 15)
        # Four card slots: each offer is a match-group (or whole) card with its
        # scorer already attached, so no condition components are sold any more
        # (see Shop.refresh).
        self.assertEqual(kinds.count("card"), 4)
        # One shop slot per offered action (the catalogue is bigger than the
        # room, so a refresh shows SHOP_ACTION_SLOTS of them).
        self.assertEqual(kinds.count("action"), main.SHOP_ACTION_SLOTS)
        self.assertEqual(kinds.count(main.Component.SHAPE), 2)
        self.assertEqual(kinds.count(main.Component.EFFECT), 2)
        # The two block slots and the three scorer slots are five items between
        # them: a scorer slot that rolls a run ROLE (Start/Finish) is sold as a
        # ready-made block instead of a loose scorer piece (see _scorer_offer),
        # so how those five split between the two kinds depends on the roll.
        self.assertEqual(kinds.count(main.Component.SCORER) + kinds.count("block"),
                         5)
        self.assertFalse(hasattr(main.Component, "CONDITION"))


    def test_shop_never_offers_the_free_default_parts(self):
        # The Rect shape, None effect, and None scorer are assembly defaults,
        # so they are never sold as loose components (blocks may still use
        # them — a plain wall is a legitimately useful pre-built block).
        for _ in range(200):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == main.Component.SHAPE:
                    self.assertNotEqual(item.value, main.Shape.RECT)
                elif item.kind == main.Component.EFFECT:
                    self.assertNotEqual(item.value, main.Effect.NONE)
                elif item.kind == main.Component.SCORER:
                    self.assertNotEqual(item.value, main.Scorer.NONE)


    def test_shop_always_offers_four_cards(self):
        cards = [item for item in self.game.shop.items if item.kind == "card"]
        self.assertEqual(len(cards), 4)
        # Four distinct cards are chosen at random from the pre-built pool (the
        # whole Card.ORDER cards plus the (match group x scorer) cards).
        self.assertEqual(len({item.value for item in cards}), 4)
        self.assertTrue(all(item.value in main.Card.NAMES for item in cards))
        # The four cards open the shop's bottom item row, to the left of the
        # actions and pre-built blocks.
        self.assertEqual({item.col for item in cards}, {1, 2, 3, 4})
        self.assertTrue(all(item.row == 3 for item in cards))


    def test_shop_cards_are_four_random_distinct_every_refresh(self):
        # Every reroll yields exactly four DIFFERENT cards from the pre-built pool.
        for _ in range(40):
            self.game.shop.refresh()
            cards = [item for item in self.game.shop.items if item.kind == "card"]
            self.assertEqual(len(cards), 4)
            self.assertEqual(len({item.value for item in cards}), 4)
            self.assertTrue(all(item.value in main.Card.NAMES for item in cards))


    def test_new_shapes_have_names_descriptions_and_prices(self):
        # Each new shape is a first-class component: named, described, priced.
        for shape in self._new_shapes():
            self.assertIn(shape, main.Shape.ORDER)
            self.assertNotEqual(main.Shape.name(shape), "Unknown")
            self.assertTrue(main.shape_description(shape))
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.SHAPE, shape)], 0)


    def test_new_effects_have_names_descriptions_and_prices(self):
        # Each new effect is a first-class component: named, described, priced,
        # and available to random shop blocks (REAL_ORDER).
        for effect in self._new_effects():
            self.assertIn(effect, main.Effect.REAL_ORDER)
            self.assertNotEqual(main.Effect.name(effect), "Unknown")
            self.assertTrue(main.effect_description(effect))
            self.assertGreater(
                main.COMPONENT_PRICES[(main.Component.EFFECT, effect)], 0)
        # The splitter is the expensive one, priced at $124.
        self.assertEqual(
            main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.SPLITTER)], 124)


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_shop_offers_two_conditions_next_to_cards(self):
        # Two random conditions sit next to the two whole cards in the shop.
        conds = [i for i in self.game.shop.items if i.kind == main.Component.CONDITION]
        self.assertEqual(len(conds), 2)
        self.assertTrue(all(i.row == 3 for i in conds))
        self.assertTrue(all(i.value in main.CONDITION_ORDER for i in conds))


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_buying_condition_adds_to_toolbox_and_discovers(self):
        # Buying a condition puts it in the toolbox and reveals it.
        self.game.cash = 1000
        cond = next(i for i in self.game.shop.items
                    if i.kind == main.Component.CONDITION)
        self.game._buy_shop_item(cond)
        self.assertIn(cond, self.game.toolbox.items)
        self.assertTrue(collection.is_condition_discovered(cond.value))
        self.assertTrue(any(p.title == "New condition" for p in self.game.popups))


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_buying_splittable_card_reveals_its_halves(self):
        # Buying a whole splittable card (Joker) reveals its condition + scorer
        # halves instead of the card itself.
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.JOKER, 20))
        self.assertFalse(collection.is_card_discovered(main.Card.JOKER))
        condition, scorer = main.splittable_card_condition_scorer(main.Card.JOKER)
        self.assertEqual(condition, main.Condition.START)
        self.assertEqual(scorer, main.Scorer.MULT_ADD)
        self.assertTrue(collection.is_condition_discovered(condition))
        self.assertTrue(collection.is_component_discovered(main.Component.SCORER, scorer))
        self.assertTrue(any(p.title == "New condition" for p in self.game.popups))


    def test_shop_can_offer_grid_only_prebuilt_cards(self):
        # Over many rerolls the shop's card offers include derived grid cards
        # that were never in the old fixed catalog, proving pre-built
        # splittable cards can carry any scorer.
        seen = set()
        for _ in range(200):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "card":
                    seen.add(item.value)
        grid_only = [v for v in seen if v not in main.Card.ORDER]
        self.assertTrue(grid_only)


    def test_fresh_card_gives_a_free_reroll_on_matching_collision(self):
        value = _group_card(main.match_group_for_shape(main.Shape.PIPE),
                            main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.free_rerolls = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.free_rerolls, 1)


    def test_voyager_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.VOYAGER, main.Scorer.ORDER)
        self.assertIn(main.Scorer.VOYAGER, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.VOYAGER), "Voyager")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.VOYAGER)], 0)
        # The magnitude is the mult per PIXEL of travel, rolled around 0.01.
        self.assertAlmostEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.VOYAGER], 0.01)
        desc = main.scorer_description(main.Scorer.VOYAGER, 0.01)
        self.assertIn("traveled", desc.lower())
        self.assertIn("0.01 mult", desc)
        self.assertIn("pixel", desc.lower())
        # Voyager is also a card scorer: every match group can offer it (a card
        # that adds mult from the run's total travel).
        self.assertIn(main.Scorer.VOYAGER, components.CARD_SCORERS)
        self.assertIn(main.Scorer.VOYAGER, components.FLAT_CARD_SCORERS)
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.VOYAGER)
        self.assertGreaterEqual(value, components.MATCH_GROUP_CARD_OFFSET)
        self.assertEqual(components.match_group_card_meta(value),
                         (group, main.Scorer.VOYAGER))


    def test_summit_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SUMMIT, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SUMMIT, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SUMMIT), "Summit")
        self.assertAlmostEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SUMMIT], 0.75)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SUMMIT)], 0)
        self.assertIn("above the bottom row",
                      main.scorer_description(main.Scorer.SUMMIT, 0.75).lower())
        # Summit is also a card scorer: every match group can offer it (the card
        # measures the triggering block's row).
        self.assertIn(main.Scorer.SUMMIT, components.CARD_SCORERS)
        self.assertIn(main.Scorer.SUMMIT, components.FLAT_CARD_SCORERS)
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.SUMMIT)
        self.assertGreaterEqual(value, components.MATCH_GROUP_CARD_OFFSET)
        self.assertEqual(components.match_group_card_meta(value),
                         (group, main.Scorer.SUMMIT))


    def test_airball_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.AIRBALL, main.Scorer.ORDER)
        self.assertIn(main.Scorer.AIRBALL, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.AIRBALL), "Airball")
        self.assertEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.AIRBALL], 8)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.AIRBALL)], 0)
        self.assertIn("airborne", main.scorer_description(main.Scorer.AIRBALL, 8).lower())
        # Airball is also a card scorer (every match group can offer it; the
        # card rewards the touching marble's air streak).
        self.assertIn(main.Scorer.AIRBALL, components.CARD_SCORERS)
        self.assertIn(main.Scorer.AIRBALL, components.FLAT_CARD_SCORERS)
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.AIRBALL)
        self.assertGreaterEqual(value, components.MATCH_GROUP_CARD_OFFSET)
        self.assertEqual(components.match_group_card_meta(value),
                         (group, main.Scorer.AIRBALL))
        # A match-group card's glyph is its GROUP's (not the scorer's), so this
        # Pipe card carries the Pipe group's glyph.
        self.assertEqual(main.Card.GLYPHS.get(value),
                         components.match_group_glyph(group))
        # ... and its face color is the scorer's own color.
        self.assertEqual(main.Card.COLORS[value], main.Scorer.color(main.Scorer.AIRBALL))


    def test_satanic_scorer_is_defined_and_shop_available(self):
        self.assertIn(main.Scorer.SATANIC, main.Scorer.ORDER)
        self.assertIn(main.Scorer.SATANIC, main.Scorer.SHOP_ORDER)
        self.assertEqual(main.Scorer.name(main.Scorer.SATANIC), "Satanic")
        self.assertAlmostEqual(main.Scorer.DEFAULT_AMOUNT[main.Scorer.SATANIC], 6.66)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.SATANIC)], 0)
        self.assertIn("destroyed", main.scorer_description(main.Scorer.SATANIC).lower())
        # A Satanic CARD says it is destroyed after one run (the block's own
        # description is about a marble leaving it).
        card_desc = main.Card.description(main.match_group_card(
            main.match_group_for_shape(main.Shape.PIPE), main.Scorer.SATANIC))
        self.assertIn("x6.66 mult", card_desc)
        self.assertIn("destroyed after one run", card_desc)
        # Satanic is also a card scorer: every match group can offer it (its
        # card is destroyed after a run).
        self.assertIn(main.Scorer.SATANIC, components.CARD_SCORERS)
        self.assertIn(main.Scorer.SATANIC, components.FLAT_CARD_SCORERS)
        group = main.match_group_for_shape(main.Shape.PIPE)
        value = main.match_group_card(group, main.Scorer.SATANIC)
        self.assertGreaterEqual(value, components.MATCH_GROUP_CARD_OFFSET)
        self.assertEqual(components.match_group_card_meta(value),
                         (group, main.Scorer.SATANIC))


    def test_magnitude_card_prices_scale_with_scorer_and_condition(self):
        # A magnitude card's price is its condition + scorer price, so +Chips
        # is cheapest and xMult most expensive for one condition, while the
        # condition price runs INVERSELY to the component it matches.
        pipe = main.Shape.PIPE
        pipe_chips = main.Card.PRICES[_shape_card_value(pipe, main.Scorer.CHIPS_ADD)]
        pipe_mult = main.Card.PRICES[_shape_card_value(pipe, main.Scorer.MULT_ADD)]
        pipe_xmult = main.Card.PRICES[_shape_card_value(pipe, main.Scorer.MULT_MUL)]
        self.assertLess(pipe_chips, pipe_mult)
        self.assertLess(pipe_mult, pipe_xmult)
        # A pricey effect (Portal, $31 > Bouncy, $28) has the CHEAPER condition,
        # so its magnitude card is cheaper than the cheaper effect's card.
        bouncy = main.Card.PRICES[_effect_card_value(main.Effect.BOUNCY, main.Scorer.MULT_ADD)]
        portal = main.Card.PRICES[_effect_card_value(main.Effect.PORTAL, main.Scorer.MULT_ADD)]
        self.assertGreater(bouncy, portal)
        # The same inversion holds for shapes: Circle ($8) is cheaper than Pipe
        # Bend ($12), so its condition - and its card - costs more.
        circle = main.Card.PRICES[_shape_card_value(main.Shape.CIRCLE, main.Scorer.MULT_MUL)]
        pipe_bend = main.Card.PRICES[_shape_card_value(main.Shape.PIPE_BEND, main.Scorer.MULT_MUL)]
        self.assertGreater(circle, pipe_bend)


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_condition_prices_run_inversely_to_their_component(self):
        # A shape/effect collision condition costs the inverse of the component
        # it matches: the cheapest block's condition is the dearest, and the
        # pricey Splitter's condition is the cheapest — never free.
        def shape_cond(shape):
            return main.COMPONENT_PRICES[
                (main.Component.CONDITION,
                 main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape))]

        def effect_cond(effect):
            return main.COMPONENT_PRICES[
                (main.Component.CONDITION,
                 main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect))]

        rect_price = main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.RECT)]
        splitter_price = main.COMPONENT_PRICES[(main.Component.EFFECT,
                                                main.Effect.SPLITTER)]
        self.assertGreater(shape_cond(main.Shape.RECT), rect_price)
        self.assertLess(effect_cond(main.Effect.SPLITTER), splitter_price)
        self.assertLess(effect_cond(main.Effect.SPLITTER),
                        effect_cond(main.Effect.BOUNCY))
        self.assertGreater(shape_cond(main.Shape.PEG),
                           shape_cond(main.Shape.LINE))
        # The relation holds across the whole table, with a floor under it.
        pairs = [(main.COMPONENT_PRICES[(main.Component.SHAPE, shape)],
                  shape_cond(shape)) for shape in main.Shape.ORDER]
        pairs += [(main.COMPONENT_PRICES[(main.Component.EFFECT, effect)],
                   effect_cond(effect)) for effect in main.Effect.ORDER]
        for price, cond_price in pairs:
            self.assertGreaterEqual(cond_price, components.CONDITION_PRICE_FLOOR)
            for other_price, other_cond_price in pairs:
                if price < other_price:
                    self.assertGreaterEqual(cond_price, other_cond_price)


    def test_buying_card_adds_to_card_area_not_toolbox(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        # The ERR 404 card converts to a random card when bought, so it isn't
        # the same object — skip it and buy a normal card instead.
        card = next(item for item in self.game.shop.items
                    if item.kind == "card" and item.value != main.Card.ERR_404)
        before_cash = self.game.cash
        self.game._buy_shop_item(card)
        self.assertIn(card, self.game.cards)
        self.assertNotIn(card, self.game.toolbox.items)
        self.assertEqual(self.game.cash, before_cash - card.price)


    def test_cannot_buy_duplicate_card_without_showman(self):
        # You can't buy a second copy of a card you already own unless you own
        # the Showman card.
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        self.game.cards.append(card)
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(card.value, card.price,
                                               amount=card.amount))
        self.assertEqual(len(self.game.cards), 1)  # no duplicate added
        self.assertEqual(self.game.cash, 1000)     # not charged
        self.assertEqual(self.game.shop_message, "Already own this card")


    def test_can_buy_duplicate_card_with_showman(self):
        # Owning the Showman card lets you buy duplicates of any card.
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 100))
        self.game.cards.append(card)
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(card.value, card.price,
                                               amount=card.amount))
        self.assertEqual(len(self.game.cards), 3)  # Showman + 2 cards
        self.assertEqual(self.game.cash, 1000 - card.price)


    def test_the_shop_skips_cards_the_player_already_owns(self):
        # An offer the player cannot buy is a wasted slot, and a card they own
        # should not come back around refresh after refresh: the card slots skip
        # the cards the player already owns.
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.assertEqual(self.game.shop.owned_cards(), {main.Card.GARDEN})
        for _ in range(200):
            self.game.shop.refresh()
            offered = [item for item in self.game.shop.items
                       if item.kind == "card"]
            self.assertEqual(len(offered), 4)  # all four slots still fill
            self.assertNotIn(main.Card.GARDEN, {item.value for item in offered})


    def test_showman_lets_owned_cards_back_into_the_shop(self):
        # The Showman card is exactly what allows more than one copy, so with it
        # nothing is filtered: a card the player already owns can be offered
        # again (and bought — see test_can_buy_duplicate_card_with_showman).
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 48))
        self.assertEqual(self.game.shop.owned_cards(), set())
        with mock.patch("main.random_card_option_value",
                        return_value=main.Card.GARDEN):
            self.game.shop.refresh()
        self.assertIn(main.Card.GARDEN,
                      {item.value for item in self.game.shop.items
                       if item.kind == "card"})
        # A Showman the run's trial has disabled cannot lift the rule (the same
        # rule the buy path follows): the owned cards are filtered out again.
        self.game.disabled_card = self.game.cards[1]
        self.assertEqual(self.game.shop.owned_cards(),
                         {main.Card.GARDEN, main.Card.SHOWMAN})
        self.game.disabled_card = None


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_shop_card_slots_combine_conditions_and_unsplittables_equally(self):
        # Each card slot draws equally from a combined pool of conditions and
        # the indivisible whole cards; a condition draw gets a random scorer
        # attached, becoming a composed (condition x scorer) card offer.
        draws = [main.random_card_option_value() for _ in range(5000)]
        whole = [v for v in draws if v in main.Card.ORDER]
        composed = [v for v in draws if v not in whole]
        # The pool is the conditions plus the indivisible whole cards, drawn
        # uniformly. The Few Blocks condition also shares ERR 404's id 9, and
        # that entry resolves to the whole card, so one extra whole-card draw
        # hides in the condition entries.
        expected = ((len(main.Card.ORDER) + 1)
                    / (len(components.CONDITION_ORDER) + len(main.Card.ORDER)))
        self.assertAlmostEqual(len(whole) / len(draws), expected, delta=0.03)
        self.assertTrue(composed)  # conditions dominate the pool
        # Every composed draw attached a scorer: it is exactly the composed
        # card for its (condition, scorer) halves.
        for v in composed:
            condition, scorer = main.splittable_card_condition_scorer(v)
            self.assertEqual(v, main.condition_scorer_card(condition, scorer))


    def test_shop_can_offer_unsplittable_whole_cards(self):
        # The indivisible whole cards (the Card.ORDER catalog, incl. Garden /
        # Rigged Casino / Conquistador) are in the card slots' combined pool,
        # so they appear in the shop sometimes.
        seen = set()
        for _ in range(300):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "card":
                    seen.add(item.value)
        self.assertTrue(seen & set(main.Card.ORDER))
        self.assertTrue(seen & {main.Card.GARDEN, main.Card.RIGGED_CASINO,
                                main.Card.CONQUISTADOR})


    def test_shop_always_offers_some_actions(self):
        actions = [item for item in self.game.shop.items if item.kind == "action"]
        cards = [item for item in self.game.shop.items if item.kind == "card"]
        # The catalogue is bigger than the room left in the shop's bottom row,
        # so each refresh shows a random SHOP_ACTION_SLOTS of them, all
        # different.
        self.assertEqual(len(actions), main.SHOP_ACTION_SLOTS)
        self.assertEqual(len({a.value for a in actions}), main.SHOP_ACTION_SLOTS)
        self.assertTrue(all(a.value in main.Action.ORDER for a in actions))
        # Two slots, two DISTINCT actions, on every single refresh.
        for _ in range(40):
            self.game.shop.refresh()
            offered = [i for i in self.game.shop.items if i.kind == "action"]
            self.assertEqual(len(offered), 2)
            self.assertEqual(len({a.value for a in offered}), 2)
        # Actions sit in row 3 to the right of the four card slots.
        self.assertTrue(all(a.row == 3 for a in actions))
        self.assertEqual({a.col for a in actions}, {5, 6})
        self.assertTrue(max(c.col for c in cards) < min(a.col for a in actions))
        self.assertTrue(all(a.price == main.Action.PRICES[a.value] for a in actions))
        # An action arrives as v1 normally, but now and then it is a free v2.
        self.assertTrue(all(a.version in (1, 2) for a in actions))


    def test_action_prices_are_halved_and_the_upgrade_costs_200(self):
        # The first three action prices were halved (48 -> 24, 56 -> 28) and
        # upgrading an action to v2 is a flat $200 (it used to be $300, then
        # $240). The three later actions are stronger, so they sit a tier up.
        self.assertEqual(main.ACTION_UPGRADE_COST, 200)
        self.assertEqual(main.Action.PRICES[main.Action.DEATH], 24)
        self.assertEqual(main.Action.PRICES[main.Action.RECOGNITION], 24)
        self.assertEqual(main.Action.PRICES[main.Action.DEJA_VU], 28)
        self.assertEqual(main.Action.PRICES[main.Action.ANOINTMENT], 32)
        self.assertEqual(main.Action.PRICES[main.Action.STRENGTH], 28)
        self.assertEqual(main.Action.PRICES[main.Action.SPIRIT], 36)
        shop_actions = [i for i in self.game.shop.items if i.kind == "action"]
        self.assertEqual({a.price for a in shop_actions},
                         {main.Action.PRICES[a.value] for a in shop_actions})


    def test_a_v2_action_on_the_shelf_prices_in_gold(self):
        # The shelf flag has to be readable without hovering: an already-upgraded
        # action's price is drawn in the gold of its own frame, so the tile worth
        # an extra ACTION_UPGRADE_COST stands out across the shop.
        gold = (255, 215, 0)
        self.game.trials_enabled = False  # no Slim pickings trim to shift items
        self.game.shop_message = ""

        def price_gold(version):
            with mock.patch("main.random_action_version", return_value=version):
                self.game.shop.refresh()
            self.game.screen.fill(main.BLACK)
            main.ui.draw_shop(self.game)
            cells = []
            for item in self.game.shop.items:
                if getattr(item, "kind", None) != "action":
                    continue
                cx = (self.game.shop.rect.x + item.col * main.GRID_SIZE
                      + main.GRID_SIZE // 2)
                cy = (self.game.shop.rect.y + (item.row + 1) * main.GRID_SIZE
                      + main.GRID_SIZE // 2)
                cells.append(sum(
                    self.game.screen.get_at((x, y))[:3] == gold
                    for x in range(cx - 18, cx + 18)
                    for y in range(cy - 8, cy + 9)))
            return cells

        plain = price_gold(1)
        self.assertTrue(plain)
        self.assertEqual(plain, [0] * len(plain))  # a plain shelf prices white
        upgraded = price_gold(2)
        self.assertEqual(len(upgraded), len(plain))
        self.assertTrue(all(count > 0 for count in upgraded), upgraded)


    def test_a_reroll_that_shelves_an_upgraded_action_says_so(self):
        # The rare pre-upgraded action is named in the reroll message, so a
        # player who never reads the shelves is still told about the windfall.
        self.game.cash = 1000
        self.game.free_rerolls = 0
        self.game.trials_enabled = False

        with mock.patch("main.random_action_version", return_value=2):
            self.game._refresh_shop()
        self.assertIn("Refreshed shop", self.game.shop_message)
        self.assertIn("already upgraded", self.game.shop_message)
        for item in self.game.shop.items:
            if item.kind == "action":
                self.assertIn(f"{item.name} v2", self.game.shop_message)

        # A shelf of plain v1 actions gets the ordinary message back.
        with mock.patch("main.random_action_version", return_value=1):
            self.game._refresh_shop()
        self.assertNotIn("already upgraded", self.game.shop_message)


    def test_buying_action_adds_to_action_area_not_toolbox(self):
        self.game.cash = 1000
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game._buy_shop_item(action)
        self.assertIn(action, self.game.actions)
        self.assertNotIn(action, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 1000 - 60)


    def test_death_action_v1_sells_block_for_one_and_a_half(self):
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Pipe")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.assertTrue(self.game._apply_action())
        self.assertNotIn(block, self.game.toolbox.items)
        self.assertEqual(self.game.cash, 100 + int(50 * 1.5))
        self.assertEqual(self.game.actions, [])  # consumed


    def test_death_action_v2_sells_block_for_six_times(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.MULT_ADD, 4, 40, "Rect")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEATH, 60, version=2)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.assertTrue(self.game._apply_action())
        self.assertEqual(self.game.cash, 100 + 40 * 6)


    def test_death_action_sells_card_for_one_and_a_half(self):
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.CHIPS_ADD)
        self.game.cards.append(card)
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = card
        self.assertTrue(self.game._apply_action())
        self.assertNotIn(card, self.game.cards)
        self.assertEqual(self.game.cash, 100 + int(card.price * 1.5))


    def test_buying_action_discovers_it_in_collection(self):
        self.game.cash = 1000
        self.game._buy_shop_item(main.ActionItem(main.Action.RECOGNITION, 60))
        self.assertTrue(collection.is_action_discovered(main.Action.RECOGNITION))
        self.assertTrue(any(p.title == "New action" for p in self.game.popups))


    def test_slim_pickings_removes_two_shop_options(self):
        # When the next run's trial is Slim pickings, the shop loses two items.
        self.game.trials_enabled = True
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        before = len(self.game.shop.items)
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: (main.Trial.SLIM_PICKINGS
                                                 if seq is main.Trial.ORDER
                                                 else seq[0])):
            self.game._continue_run()
        self.assertEqual(len(self.game.shop.items), before - 2)


    def test_slim_pickings_leaves_shop_full_for_other_trials(self):
        self.game.trials_enabled = True
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        before = len(self.game.shop.items)
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: (main.Trial.HANDS_TIED
                                                 if seq is main.Trial.ORDER
                                                 else seq[0])):
            self.game._continue_run()
        self.assertEqual(len(self.game.shop.items), before)


    def test_marble_weight_trial_sets_effect_mass_mult(self):
        # Marble weight rolls a factor (2.0 heavy / 0.5 light) each run; the
        # marble uses it to scale only effect pushes (1/effect_mass).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.MARBLE_WEIGHT
        with mock.patch("main.random.choice", return_value=2.0):
            self.game._apply_trial()
        self.assertEqual(self.game.trial_marble_weight, 2.0)
        self.game.reset_run(False)
        self.assertTrue(all(m.effect_mass_mult == 2.0 for m in self.game.marbles))


    def test_inflation_trial_raises_prices_and_fees(self):
        # Inflation applies a 50% surcharge to shop prices and fees while it is
        # the current trial (chosen before the run, so its shop is inflated).
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.INFLATION
        self.assertEqual(self.game._inflated(100), 150)
        self.assertEqual(self.game._inflated(main.SHOP_REFRESH_COST),
                         int(main.SHOP_REFRESH_COST * 1.5 + 0.5))
        item = main.Component.effect_component(main.Effect.BOUNCY)
        self.assertEqual(self.game._buy_price(item),
                         self.game._inflated(item.price))
        # The surcharge disappears when the trial is not inflation.
        self.game.current_trial = main.Trial.HANDS_TIED
        self.assertEqual(self.game._inflated(100), 100)
        self.assertEqual(self.game._buy_price(item), item.price)


    def test_trial_display_left_half_buys_a_different_random_trial(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.cash = 1000
        self.game._apply_trial()
        self.assertEqual(self.game.trial_debuffed_blocks, set())  # empty board
        bought = self.game._click_trial_display(
            (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertTrue(bought)
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.assertNotEqual(self.game.current_trial, main.Trial.HANDS_TIED)
        self.assertIn("Trial changed", self.game.shop_message)


    def test_trial_display_right_half_buys_no_trial(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.cash = 1000
        bought = self.game._click_trial_display(
            (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery))
        self.assertTrue(bought)
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)
        self.assertEqual(self.game.shop_message,
                         f"Trial disabled (${main.TRIAL_DISABLE_COST})")
        # Buying it away twice is refused (and free).
        self.assertFalse(self.game._click_trial_display(
            (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_DISABLE_COST)
        self.assertIn("no trial", self.game.shop_message)


    def test_clicking_the_trial_display_halves_buys_trial_changes(self):
        # The click handler routes the display's two halves to the purchases.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.cash = 1000
        self._click((main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertNotEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self._click((main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery))
        self.assertEqual(
            self.game.cash,
            1000 - main.TRIAL_CHANGE_COST - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)


    def test_shop_blocks_are_made_of_random_valid_components(self):
        blocks = [item for item in self.game.shop.items if item.kind == "block"]

        for block in blocks:
            self.assertIn(block.shape, main.Shape.ORDER)
            self.assertIn(block.effect, main.Effect.ORDER)
            self.assertIn(block.scorer, main.Scorer.ORDER)
            # The scorer arrives with its own rolled magnitude: a continuous
            # deviation from the average (and exactly the average for a scorer
            # whose amount is not a magnitude at all).
            average = main.Scorer.DEFAULT_AMOUNT[block.scorer]
            step = main.magnitude_step(average)
            if not step:
                self.assertEqual(block.scorer_amount, average)
            else:
                self.assertGreaterEqual(block.scorer_amount,
                                        main.scorer_magnitude_floor(block.scorer))
                self.assertLessEqual(abs(block.scorer_amount - average),
                                     step * main.MAGNITUDE_MAX_STEPS)
                # ...and free of arithmetic noise, so a price and a description
                # read the value the block actually pays.
                self.assertEqual(block.scorer_amount, round(block.scorer_amount, 9))
            # A scaleable effect records its strength; an on/off one has none.
            for e in block.effects:
                if e in main.Effect.MAGNITUDE:
                    self.assertIn(e, block.effect_amounts)
                    self.assertGreater(block.effect_amounts[e], 0)
                else:
                    self.assertNotIn(e, block.effect_amounts)


    def test_shop_never_sells_role_scorer_components(self):
        # START and FINISH are shop goods now, but only ever as ready-made
        # plain Rect blocks: a role SCORER component would let the player
        # assemble a role block with an arbitrary shape and effects, and a role
        # block must never carry physics the player did not choose.
        for _ in range(40):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == main.Component.SCORER:
                    self.assertNotIn(item.value, (main.Scorer.START, main.Scorer.FINISH))
                if getattr(item, "scorer", None) in (main.Scorer.START, main.Scorer.FINISH):
                    self.assertEqual(item.shape, main.Shape.RECT)
                    self.assertEqual(item.effects, [])


    def test_component_weight_favors_cheaper_components(self):
        # Rarity is the inverse of price: cheaper components are more common.
        self.assertGreater(main.component_weight(main.Component.SHAPE, main.Shape.RECT),
                           main.component_weight(main.Component.SHAPE, main.Shape.CURVED_SLOPE))
        self.assertGreater(main.component_weight(main.Component.EFFECT, main.Effect.NONE),
                           main.component_weight(main.Component.EFFECT, main.Effect.PORTAL))
        self.assertGreater(main.component_weight(main.Component.SCORER, main.Scorer.NONE),
                           main.component_weight(main.Component.SCORER, main.Scorer.MULT_MUL))


    def test_block_rarity_is_product_of_component_rarities(self):
        # A block's frequency is the product of its components' weights, so
        # each rare part compounds the block's rarity multiplicatively.
        def block_weight(shape, effect, scorer):
            return (main.component_weight(main.Component.SHAPE, shape)
                    * main.component_weight(main.Component.EFFECT, effect)
                    * main.component_weight(main.Component.SCORER, scorer))

        cheap = block_weight(main.Shape.RECT, main.Effect.NONE, main.Scorer.NONE)
        one_rare = block_weight(main.Shape.RECT, main.Effect.NONE, main.Scorer.MULT_MUL)
        two_rare = block_weight(main.Shape.RECT, main.Effect.PORTAL, main.Scorer.MULT_MUL)

        self.assertGreater(cheap, one_rare)
        self.assertGreater(one_rare, two_rare)
        # Each added rare part shrinks the odds by that part's own ratio, so the
        # effect compounds instead of adding.
        self.assertGreater(cheap / one_rare, 1)
        self.assertGreater(one_rare / two_rare, 1)
        self.assertGreater((cheap / one_rare) * (one_rare / two_rare), 1)


    def test_weighted_sample_without_replacement_returns_distinct_items(self):
        with mock.patch("main.random.choices", side_effect=lambda *a, **kw: [a[0][0]]):
            result = main.weighted_sample_without_replacement([1, 2, 3], [1, 1, 1], 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(set(result)), 2)  # distinct items, no duplicates


    def test_shop_weighted_sampling_favors_cheap_components(self):
        # Over many draws the cheapest shape appears more often than the rarest.
        main.random.seed(20240824)
        shape_weights = [main.component_weight(main.Component.SHAPE, s) for s in main.Shape.ORDER]
        picks = [main.random.choices(main.Shape.ORDER, weights=shape_weights, k=1)[0]
                 for _ in range(2000)]
        self.assertGreater(picks.count(main.Shape.RECT), picks.count(main.Shape.CURVED_SLOPE))


    def test_shop_refresh_rerolls_items(self):
        original = [item.name for item in self.game.shop.items]

        self.game.shop.refresh()
        refreshed = [item.name for item in self.game.shop.items]

        self.assertEqual(len(refreshed), 15)
        self.assertNotEqual(original, refreshed)


    def test_shop_refreshes_when_continuing(self):
        marble = self._add_marble()
        marble.distance = 100.0
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.run_time = 3.0
        before = [item.name for item in self.game.shop.items]

        self.game._handle_block_contacts([])

        self.assertTrue(self.game.run_complete)
        # The shop is not rerolled until the player clicks CONTINUE.
        self.assertEqual([item.name for item in self.game.shop.items], before)

        self.game._continue_run()

        after = [item.name for item in self.game.shop.items]
        self.assertNotEqual(before, after)


    def test_every_component_has_a_price(self):
        components = [item for item in self.game.shop.items if item.kind != "block"]

        self.assertTrue(all(item.price > 0 for item in components))


    def test_block_price_is_75_percent_of_component_sum(self):
        # Every part is priced at its CATALOG price, so the block's price never
        # follows the magnitudes its parts rolled on the shelf.
        block = next(item for item in self.game.shop.items if item.kind == "block")
        total = (main.COMPONENT_PRICES[(main.Component.SHAPE, block.shape)]
                 + sum(main.effect_component_price(e) for e in block.effects)
                 + main.scorer_component_price(block.scorer))

        self.assertEqual(block.price, int(total * 0.75))


    def test_block_price_sums_all_effects(self):
        price = main.block_price_for(main.Shape.RECT,
                                     [main.Effect.BOUNCY, main.Effect.PISTON],
                                     main.Scorer.CHIPS_ADD)
        total = (main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.RECT)]
                 + main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.BOUNCY)]
                 + main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.PISTON)]
                 + main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CHIPS_ADD)])
        self.assertEqual(price, int(total * 0.75))


    def test_block_price_with_single_effect_matches_effect_component(self):
        price = main.block_price_for(main.Shape.RECT, [main.Effect.GRAVITY], main.Scorer.CHIPS_ADD)
        total = (main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.RECT)]
                 + main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.GRAVITY)]
                 + main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CHIPS_ADD)])
        self.assertEqual(price, int(total * 0.75))


    def test_buying_block_equips_and_placing_consumes_it(self):
        self.game.toolbox.items.clear()
        # Use a plain (non-portal) block so buying it adds exactly one copy.
        block_item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                    main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.cash = 1000
        self.game._buy_shop_item(block_item)
        self.assertIn(block_item, self.game.toolbox.items)
        self.assertIsNone(self.game.selected_shape)  # not auto-equipped

        # Equip from the toolbox, then place it via a click.
        self.game._equip_block(block_item)
        self.assertTrue(self.game.has_selected)
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((1, 1), self.game.grid)
        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.shape, block_item.shape)
        self.assertEqual(placed.scorer, block_item.scorer)
        self.assertNotIn(block_item, self.game.toolbox.items)
        self.assertFalse(self.game.has_selected)


    def test_toolbox_component_assigns_to_assembler(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.LINE, 0, "Line")
        self.game.toolbox.add(shape_c)

        self.game._use_component(shape_c)

        self.assertIs(self.game.assembler.shape, shape_c)
        self.assertIn(shape_c, self.game.toolbox.items)  # stays in the toolbox
        self.assertFalse(self.game.has_selected)  # components can't be placed directly


    def test_assembler_combines_components_into_block(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.SLOPE, 0, "Slope")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.MULT_MUL, 2, 0, "xMult")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertTrue(self.game.has_selected)
        self.assertEqual(self.game.selected_shape, main.Shape.SLOPE)
        self.assertEqual(self.game.selected_effect, main.Effect.BOUNCY)
        self.assertEqual(self.game.selected_scorer, main.Scorer.MULT_MUL)
        self.assertEqual(self.game.selected_scorer_amount, 2)
        # Assigning a component keeps it in the toolbox; assembling consumes it.
        self.assertNotIn(shape_c, self.game.toolbox.items)
        self.assertNotIn(effect_c, self.game.toolbox.items)
        self.assertNotIn(scorer_c, self.game.toolbox.items)
        # The assembled block is added to the toolbox.
        blocks = [item for item in self.game.toolbox.items if item.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].shape, main.Shape.SLOPE)
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)
        self.assertEqual(blocks[0].scorer, main.Scorer.MULT_MUL)


    def test_assembling_consumes_one_copy_and_keeps_leftover(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        self.game.toolbox.add(shape_c)
        self.game.toolbox.add(shape_c)  # two copies
        self.game.toolbox.add(effect_c)
        self.game.toolbox.add(scorer_c)
        for component in (shape_c, effect_c, scorer_c):
            self.game._use_component(component)

        self.game._assemble_block()

        # Assembly consumed one copy; the leftover duplicate survives.
        self.assertEqual(self.game.toolbox.items.count(shape_c), 1)
        self.assertNotIn(effect_c, self.game.toolbox.items)
        self.assertNotIn(scorer_c, self.game.toolbox.items)
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 1)


    def test_assembled_block_is_added_to_toolbox(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.BOUNCY, 0, "Bouncy")
        scorer_c = main.Component.scorer_component(main.Scorer.FINISH, 0, 0, "Finish")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        # The three components were consumed when assembled; only the block remains.
        self.assertEqual(len(self.game.toolbox.items), 1)
        assembled = self.game.toolbox.items[0]
        self.assertEqual(assembled.kind, "block")
        self.assertEqual(assembled.scorer, main.Scorer.FINISH)


    def test_duplicate_component_reference_survives_assembly(self):
        # Two references to the SAME component object: assigning one and assembling
        # must not delete the other toolbox copy.
        self.game.toolbox.items.clear()
        eff = main.Component.effect_component(main.Effect.BOUNCY)
        shape = main.Component.shape_component(main.Shape.RECT)
        scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        self.game.toolbox.add(eff)
        self.game.toolbox.add(eff)  # same object twice
        self.game.toolbox.add(shape)
        self.game.toolbox.add(scorer)
        for component in (eff, shape, scorer):
            self.game._use_component(component)

        self.game._assemble_block()

        self.assertEqual(self.game.toolbox.items.count(eff), 1)  # leftover copy survives
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 1)


    def test_buying_same_shop_item_twice_is_allowed(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        item = next(i for i in self.game.shop.items if i.kind == main.Component.EFFECT)

        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        second = self.game._buy_price(item)  # duplicates now cost more
        self.game._buy_shop_item(item)

        # Duplicate buys are allowed (the player may own several copies), but
        # the second copy is more expensive.
        self.assertEqual(self.game.toolbox.items.count(item), 2)
        self.assertGreater(second, first)
        self.assertEqual(self.game.cash, 1000 - first - second)


    def test_buying_duplicate_component_costs_more(self):
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        # A fixed-magnitude piece: the shop rolls magnitudes now, and a cheap
        # roll's duplicate increments can round away at these prices.
        item = main.Component.scorer_component(main.Scorer.MULT_MUL, amount=2)

        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        price_second = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        price_third = self.game._buy_price(item)

        self.assertGreater(price_second, first)
        self.assertGreater(price_third, price_second)
        self.assertEqual(self.game.toolbox.items.count(item), 2)


    def test_component_price_increase_is_permanent_after_sale(self):
        # Once a component is bought, its price stays elevated even after the
        # copy leaves the toolbox: the increase is permanent (per-purchase),
        # not tied to how many copies are currently owned.
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        item = next(i for i in self.game.shop.items if i.kind == main.Component.EFFECT)
        base = item.price
        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        self.game.toolbox.items.remove(item)  # the copy is sold / used up
        after = self.game._buy_price(item)
        expected = int(base * (1 + main.DUPLICATE_PRICE_INCREMENT))  # sqrt(1) == 1
        self.assertEqual(after, expected)  # still elevated with the copy gone
        self.assertGreater(after, first)


    def test_buying_block_counts_toward_component_prices(self):
        # Buying a block also counts every component it contains, so the
        # component prices rise even though they weren't bought directly.
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        block = next(i for i in self.game.shop.items if getattr(i, "kind", None) == "block")
        self.assertIsNotNone(block)
        self.game._buy_shop_item(block)
        self.assertGreaterEqual(
            self.game.component_purchases.get((main.Component.SHAPE, block.shape), 0), 1)
        for e in block.effects:
            self.assertGreaterEqual(
                self.game.component_purchases.get((main.Component.EFFECT, e), 0), 1)
        self.assertGreaterEqual(
            self.game.component_purchases.get((main.Component.SCORER, block.scorer), 0), 1)


    def test_duplicate_price_increase_diminishes(self):
        # Each additional copy of the same component adds a smaller increment,
        # so the price keeps rising but more and more slowly (a square-root
        # curve, not linear). A higher-priced scorer keeps the increments
        # distinct after integer rounding.
        self.game.toolbox.items.clear()
        self.game.cash = 100000
        item = main.Component.scorer_component(main.Scorer.MULT_MUL, amount=2)  # base 25
        first = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        second = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        third = self.game._buy_price(item)
        self.game._buy_shop_item(item)
        fourth = self.game._buy_price(item)
        self.assertGreater(second - first, third - second)
        self.assertGreater(third - second, fourth - third)
        self.assertGreater(fourth, third)


    def test_duplicate_pricing_does_not_affect_rarity(self):
        item = next(i for i in self.game.shop.items if i.kind == main.Component.EFFECT)
        before = main.component_weight(item.kind, item.value)
        self.game.cash = 1000
        self.game._buy_shop_item(item)
        self.game._buy_shop_item(item)
        # Rarity is based only on the base price, never on how many you own.
        self.assertEqual(main.component_weight(item.kind, item.value), before)


    def test_trigger_upgrade_cost_is_the_scorers_shop_price_plus_ten_percent(self):
        # The upgrade is priced off the block's SCORER, not the whole block:
        # 10% more than the shop would charge for that scorer component now.
        cheap = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 10, "cheap")
        chips = main.BlockItem(0, 0, main.Shape.CURVED_SLOPE, main.Effect.PORTAL,
                              main.Scorer.CHIPS_ADD, 0, 100, "chips")
        component = main.Component.scorer_component(main.Scorer.CHIPS_ADD)
        expected = int(self.game._buy_price(component) * main.TRIGGER_UPGRADE_MARKUP)

        self.assertEqual(self.game._trigger_upgrade_cost(chips), expected)
        self.assertEqual(self.game._trigger_upgrade_cost(cheap),
                         int(self.game._buy_price(
                             main.Component.scorer_component(main.Scorer.NONE))
                             * main.TRIGGER_UPGRADE_MARKUP))
        # The block's own shape/effects/price no longer matter at all.
        plain_shape = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                     main.Scorer.CHIPS_ADD, 0, 10, "plain")
        self.assertEqual(self.game._trigger_upgrade_cost(plain_shape), expected)


    def test_upgrading_a_trigger_counts_as_buying_the_scorers_component(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 50, "Rect +Chips")
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 1000
        # The upgrade is priced off the block's OWN scorer magnitude, so the
        # comparison piece must carry the same amount (a +Chips block with 10
        # chips is priced as the 10-chip scorer component).
        component = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        before_price = self.game._buy_price(component)
        before_cost = self.game._trigger_upgrade_cost(block)

        self.game._upgrade_trigger_limit()

        # The scorer's shop price rose exactly as if it had been bought.
        self.assertEqual(self.game.component_purchases
                         [(main.Component.SCORER, main.Scorer.CHIPS_ADD)], 1)
        self.assertGreater(self.game._buy_price(component), before_price)
        # ...and so did the next upgrade (10% over the new price).
        after_price = self.game._buy_price(component)
        self.assertEqual(self.game._trigger_upgrade_cost(block),
                         int(after_price * main.TRIGGER_UPGRADE_MARKUP))
        self.assertGreater(self.game._trigger_upgrade_cost(block), before_cost)


    def test_shop_effect_pieces_always_carry_a_real_magnitude(self):
        # Regression: the shop's two effect slots used to build their piece
        # without a roll, so a scaleable effect arrived with magnitude 0 and the
        # sidebar read "0 px/s^2, 3000 below the 3000 px/s^2 average" — a
        # zero-strength repulsor, which no roll can produce (the weakest roll is
        # 8 steps below the average).
        for _ in range(40):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind != main.Component.EFFECT:
                    continue
                if item.value not in main.Effect.MAGNITUDE:
                    self.assertEqual(item.effect_magnitude, 0)  # an on/off effect
                    continue
                average = main.Effect.MAGNITUDE[item.value]
                step = main.magnitude_step(average)
                magnitude = item.effect_magnitude
                self.assertGreaterEqual(magnitude, main.effect_magnitude_floor(item.value))
                self.assertLessEqual(magnitude, average + step * main.MAGNITUDE_MAX_STEPS)
                self.assertEqual(item.price,
                                 main.effect_component_price(item.value))
                # ...and the sidebar never claims a zero strength.
                text = dict(self.game._describe_item(item))["Effect - "
                                                            f"{main.Effect.name(item.value)}"]
                self.assertNotIn(" 0 px/s", text)  # the bug read "0 px/s^2, 3000 below"
        # A repulsor rolled over and over never comes out at 0.
        seen = {main.roll_effect_magnitude(main.Effect.REPULSOR) for _ in range(3000)}
        self.assertNotIn(0, seen)
        self.assertGreaterEqual(min(seen), main.effect_magnitude_floor(main.Effect.REPULSOR))


    def test_disassembling_a_block_hands_back_its_own_magnitudes(self):
        # The pieces you get back are the ones the block was made of: a block
        # holding a 2100 px/s piston gives back a 2100 px/s piston piece.
        self.game.cash = 1000
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 45, 99, "Rect +Chips",
                               effects=[main.Effect.PISTON],
                               effect_amounts={main.Effect.PISTON: 2100})
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block

        self.game._disassemble_block()

        piston = next(i for i in self.game.toolbox.items
                      if getattr(i, "kind", None) == main.Component.EFFECT)
        self.assertEqual(piston.value, main.Effect.PISTON)
        self.assertEqual(piston.effect_magnitude, 2100)
        self.assertEqual(piston.price, main.effect_component_price(main.Effect.PISTON))
        scorer = next(i for i in self.game.toolbox.items
                      if getattr(i, "kind", None) == main.Component.SCORER)
        self.assertEqual(scorer.amount, 45)  # the scorer keeps its amount too


    def test_component_prices_ignore_the_rolled_magnitude(self):
        # A piece costs its catalog price whatever it rolled: a strong roll is
        # free upside to hunt for, never a bigger bill.
        chips = main.COMPONENT_PRICES[(main.Component.SCORER, main.Scorer.CHIPS_ADD)]
        for amount in (6, 15, 30, 45, 54):
            with self.subTest(amount=amount):
                self.assertEqual(main.scorer_component_price(main.Scorer.CHIPS_ADD),
                                 chips)
        # Roles and magnitude-less scorers are priced by the same table.
        self.assertEqual(main.scorer_component_price(main.Scorer.START), 140)
        piston = main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.PISTON)]
        self.assertEqual(main.effect_component_price(main.Effect.PISTON), piston)
        self.assertEqual(main.effect_component_price(main.Effect.FRAGILE),
                         main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.FRAGILE)])
        # The piece itself still CARRIES the strength it rolled.
        strong = main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=45)
        weak = main.Component.scorer_component(main.Scorer.CHIPS_ADD, amount=15)
        self.assertEqual((strong.amount, weak.amount), (45, 15))
        self.assertEqual(strong.price, weak.price)


    def test_block_price_ignores_the_rolled_magnitudes(self):
        # Two blocks with the same parts cost the same however they rolled.
        average = main.block_price_for(main.Shape.RECT, [main.Effect.PISTON],
                                       main.Scorer.CHIPS_ADD)
        strong = main.Component.effect_component(main.Effect.PISTON, magnitude=1800)
        weak = main.Component.effect_component(main.Effect.PISTON, magnitude=900)
        self.assertEqual(strong.price, weak.price)
        self.assertNotEqual(strong.effect_magnitude, weak.effect_magnitude)
        # A role block is priced from the same table as everything else.
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.START), 109)
        self.assertEqual(main.block_price_for(main.Shape.RECT, [], main.Scorer.FINISH), 53)
        # The roll is nowhere in the sum either.
        self.assertEqual(average,
                         main.block_price_for(main.Shape.RECT, [main.Effect.PISTON],
                                              main.Scorer.CHIPS_ADD))


    def test_assembling_keeps_the_effects_own_magnitude(self):
        # The effect piece's rolled strength travels onto the assembled block.
        self.game.toolbox.items.clear()
        effect = main.Component.effect_component(main.Effect.PISTON, magnitude=1800)
        self.game.toolbox.add(effect)
        self.game._use_component(effect)

        self.game._assemble_block()

        block = next(i for i in self.game.toolbox.items if i.kind == "block")
        self.assertEqual(block.effect_magnitude(main.Effect.PISTON), 1800)
        self.assertEqual(block.price, int(main.effect_component_price(
            main.Effect.PISTON) * 0.75))


    def test_upgrade_cost_follows_the_inflation_trial_and_the_coupon_card(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 50, "Rect +Chips")
        base = self.game._trigger_upgrade_cost(block)

        self.game.cards.append(main.CardItem(main.Card.COUPON, 46))
        with_coupon = self.game._trigger_upgrade_cost(block)
        self.assertLess(with_coupon, base)  # Coupon discounts it like any buy

        self.game.cards.clear()
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.INFLATION
        self.assertGreater(self.game._trigger_upgrade_cost(block), base)
        self.game.current_trial = None


    # --- Tesseract: a permanent xMult bonus per shop reroll ---------------

    def test_tesseract_gains_xmult_for_every_reroll_while_owned(self):
        self.game.cash = 1000
        self.game.cards.append(main.CardItem(main.Card.TESSERACT, 44))
        self.assertEqual(self.game.tesseract_bonus, 1.0)

        self.game._refresh_shop()

        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + main.TESSERACT_REROLL_XMULT)
        self.assertIn("Tesseract", self.game.shop_message)
        # A paid reroll and a banked (Fresh) free reroll both count.
        self.game.free_rerolls = 1
        self.game._refresh_shop()
        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + 2 * main.TESSERACT_REROLL_XMULT)


    # --- Anointment: random effects ---------------------------------------

    def test_anointment_gives_two_random_effects_and_reprices_the_block(self):
        block = main.BlockItem(0, 0, main.Shape.CIRCLE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 20, "Circle +Chips",
                               effects=[])
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.ANOINTMENT, 32)

        self.assertTrue(self.game._action_anointment(action, block))

        self.assertEqual(len(block.effects), 2)
        self.assertEqual(len(set(block.effects)), 2)
        self.assertNotIn(main.Effect.PORTAL, block.effects)
        # The two new effects are paid for in the block's price, so a sale,
        # Death and Painting all see the block's real worth — at the catalog
        # price of each new effect, never for the magnitude it rolled.
        added = sum(main.effect_component_price(e) for e in block.effects)
        self.assertEqual(block.price, 20 + added)


    def test_sell_refunds_trigger_upgrade_cash(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips", trigger_limit=3, trigger_paid=150)
        self.game.toolbox.items.append(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 0

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, block.price // 2 + 150)


    def test_placed_block_keeps_trigger_upgrade_through_erase_and_sell(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips", trigger_limit=2, trigger_paid=120)
        self.game.toolbox.items.append(block)
        # Place it with its upgraded trigger data, then erase (refund) it.
        self.game.grid[(2, 2)] = main.Block(2, 2, shape=main.Shape.RECT, effect=main.Effect.NONE,
                                            scorer=main.Scorer.CHIPS_ADD, scorer_amount=10,
                                            trigger_limit=block.trigger_limit,
                                            trigger_paid=block.trigger_paid)
        self.game._erase_block_at(2, 2)
        refunded = self.game.toolbox.items[-1]
        self.assertEqual(refunded.trigger_limit, 2)
        self.assertEqual(refunded.trigger_paid, 120)

        self.game.selected_toolbox_item = refunded
        self.game.cash = 0
        self.game._sell_selected_item()
        self.assertEqual(self.game.cash, refunded.price // 2 + 120)


    def test_placed_block_keeps_the_items_price_not_a_part_recount(self):
        # Placing a block stamps it with the price of the item it came from, so
        # its worth never drifts to a re-summed part total: this item was sold
        # for $7 while its parts would price the block differently.
        placed = self._place_priced_block(1, 1, 7)
        self.assertEqual(placed.resale_price, 7)
        self.assertEqual(main.block_resale_price(placed), 7)
        self.assertNotEqual(
            main.block_price_for(placed.shape, placed.effects, placed.scorer), 7)


    def test_death_and_recognition_use_the_placed_blocks_stored_price(self):
        # Death pays 1.5x the price the block was placed with, and Recognition
        # charges that same price, even though a recount of its parts says more.
        placed = self._place_priced_block(1, 1, 7)
        death = main.ActionItem(main.Action.DEATH, 24)
        self.game.cash = 100
        self.assertTrue(self.game._action_death(death, placed))
        self.assertEqual(self.game.cash, 100 + int(7 * 1.5))

        duplicate = self._place_priced_block(2, 1, 7)
        recognition = main.ActionItem(main.Action.RECOGNITION, 24)
        self.game.cash = 100
        self.assertTrue(self.game._action_recognition(recognition, duplicate))
        self.assertEqual(self.game.cash, 100 - 7)


    def test_moving_and_erasing_a_placed_block_keeps_its_price(self):
        # A move hands the block back to the inventory at its stored price, so
        # the block that lands in the new cell is worth the same $7.
        placed = self._place_priced_block(1, 1, 7)
        self.assertEqual(placed.resale_price, 7)
        self._click(self._grid_pos(1, 1))  # select the placed block
        self.game.drawing = False  # release the button before the move click
        self._click(self._grid_pos(3, 3))  # move it
        self.assertEqual(self.game.grid[(3, 3)].resale_price, 7)

        self.game._erase_block_at(3, 3)
        self.assertEqual(self.game.toolbox.items[-1].price, 7)


    def test_placed_block_price_survives_a_save_round_trip(self):
        placed = self._place_priced_block(1, 1, 7)
        data = save_system._serialize_item(placed)
        self.assertEqual(data["resale_price"], 7)

        restored = save_system._deserialize_item(data)
        self.assertEqual(restored.resale_price, 7)
        self.assertEqual(main.block_resale_price(restored), 7)

        # A save written before the price was stored leaves it unset, and the
        # first read materializes the part total on the block once.
        legacy = dict(data)
        legacy.pop("resale_price")
        old = save_system._deserialize_item(legacy)
        self.assertIsNone(old.resale_price)
        price = main.block_resale_price(old)
        self.assertEqual(old.resale_price, price)
        self.assertEqual(main.block_resale_price(old), price)


    def test_block_resale_price_materializes_for_an_unpriced_block(self):
        # A hand-built block (never placed from an item) has no stored price:
        # the helper derives the part total once and keeps it, so later reads
        # can no longer drift.
        block = main.Block(2, 2, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=30)
        self.assertIsNone(getattr(block, "resale_price", None))
        price = main.block_resale_price(block)
        self.assertEqual(price,
                         main.block_price_for(block.shape, block.effects,
                                              block.scorer))
        self.assertEqual(block.resale_price, price)
        self.assertEqual(main.block_resale_price(block), price)


    def test_shattered_fragile_block_is_priced_by_its_original_shape(self):
        # A shattered fragile block is a Shape.NONE cell; without a stored
        # price it is still worth what it was built as (the shape a refund
        # hands back), not a NONE cell's price.
        block = main.Block(2, 2, shape=main.Shape.RECT, effect=main.Effect.FRAGILE)
        block._fragile_shape = block.shape
        block.shape = main.Shape.NONE
        self.assertEqual(main.block_resale_price(block),
                         main.block_price_for(main.Shape.RECT, block.effects,
                                              block.scorer))


    def test_portal_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.PORTAL, main.Effect.ORDER)
        self.assertEqual(main.Effect.name(main.Effect.PORTAL), "Portal")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.PORTAL)], 0)
        self.assertIn("portal", main.effect_description(main.Effect.PORTAL).lower())


    def test_rotate_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.ROTATE, main.Effect.ORDER)
        self.assertEqual(main.Effect.name(main.Effect.ROTATE), "Rotate")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.ROTATE)], 0)
        self.assertIn("rotat", main.effect_description(main.Effect.ROTATE).lower())


    def test_slippery_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.SLIPPERY, main.Effect.ORDER)
        self.assertIn(main.Effect.SLIPPERY, main.Effect.REAL_ORDER)
        self.assertEqual(main.Effect.name(main.Effect.SLIPPERY), "Slippery")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.SLIPPERY)], 0)
        self.assertIn("slide", main.effect_description(main.Effect.SLIPPERY).lower())


    def test_fragile_effect_is_defined_and_shop_available(self):
        self.assertIn(main.Effect.FRAGILE, main.Effect.ORDER)
        self.assertIn(main.Effect.FRAGILE, main.Effect.REAL_ORDER)
        self.assertEqual(main.Effect.name(main.Effect.FRAGILE), "Fragile")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.FRAGILE)], 0)
        self.assertIn("shatter", main.effect_description(main.Effect.FRAGILE).lower())


    def test_growing_shrinking_effects_are_defined_and_shop_available(self):
        for effect, name in ((main.Effect.GROWING, "Growing"),
                             (main.Effect.SHRINKING, "Shrinking")):
            with self.subTest(effect=name):
                self.assertIn(effect, main.Effect.ORDER)
                self.assertIn(effect, main.Effect.REAL_ORDER)
                self.assertEqual(main.Effect.name(effect), name)
                self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, effect)], 0)
                self.assertTrue(main.effect_description(effect))


    def test_shop_blocks_have_real_or_no_effects(self):
        # A pre-built block's effects are always real ones; it may also roll
        # NO effect at all (a plain wall), but never the literal None effect.
        for item in self.game.shop.items:
            if item.kind == "block":
                self.assertLessEqual(len(item.effects), len(main.Effect.REAL_ORDER))
                self.assertNotIn(main.Effect.NONE, item.effects)
                self.assertTrue(all(e in main.Effect.REAL_ORDER for e in item.effects))


    def test_random_shop_blocks_can_have_no_effect(self):
        # Over many rerolls, pre-built shop blocks sometimes have no effect
        # (a plain wall) and sometimes have real effects.
        plain = effectful = 0
        for _ in range(400):
            self.game.shop.refresh()
            for item in self.game.shop.items:
                if item.kind == "block":
                    if item.effects:
                        effectful += 1
                    else:
                        plain += 1
        self.assertGreater(plain, 0)
        self.assertGreater(effectful, 0)


    def test_buying_portal_block_adds_two_copies_with_same_number(self):
        self.game.toolbox.items.clear()
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL,
                                main.Scorer.NONE, 0, 50, "Portal Block")
        self.game.cash = 1000

        self.game._buy_shop_item(portal)

        # Buying one portal block yields a pair that shares a fresh number.
        portals = [i for i in self.game.toolbox.items if getattr(i, "effect", None) == main.Effect.PORTAL]
        self.assertEqual(len(portals), 2)
        self.assertEqual(portals[0].portal_number, portals[1].portal_number)
        self.assertGreater(portals[0].portal_number, 0)
        self.assertNotIn(portal, self.game.toolbox.items)  # the copies, not the shop item
        self.assertEqual(self.game.cash, 1000 - portal.price)  # charged once
        self.assertEqual(len(self.game.toolbox.items), 2)


    def test_buying_non_portal_block_adds_single_copy(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.cash = 1000

        self.game._buy_shop_item(block)

        self.assertEqual(len(self.game.toolbox.items), 1)
        self.assertIn(block, self.game.toolbox.items)


    def test_buying_portal_block_requires_two_free_slots(self):
        self.game.toolbox.items.clear()
        filler = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.NONE, 0, 5, "filler")
        while len(self.game.toolbox.items) < self.game.toolbox.cols * self.game.toolbox.rows - 1:
            self.game.toolbox.add(filler)
        portal = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL,
                                main.Scorer.NONE, 0, 50, "Portal Block")
        self.game.cash = 1000

        self.game._buy_shop_item(portal)

        self.assertEqual(len(self.game.toolbox.items), self.game.toolbox.cols * self.game.toolbox.rows - 1)
        self.assertTrue(self.game.shop_message)
        self.assertEqual(self.game.cash, 1000)  # not charged when there's no room


    def test_assembling_portal_block_adds_two_copies_with_same_number(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT)
        effect_c = main.Component.effect_component(main.Effect.PORTAL)
        scorer_c = main.Component.scorer_component(main.Scorer.NONE)
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        portals = [i for i in self.game.toolbox.items if i.effect == main.Effect.PORTAL]
        self.assertEqual(len(portals), 2)
        self.assertEqual(portals[0].portal_number, portals[1].portal_number)
        self.assertGreater(portals[0].portal_number, 0)
        self.assertTrue(self.game.has_selected)  # one of the pair is equipped
        self.assertIn(self.game.selected_toolbox_item, portals)


    def test_assembling_multi_effect_block_preserves_all_effects(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT)
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10)
        bouncy = main.Component.effect_component(main.Effect.BOUNCY)
        piston = main.Component.effect_component(main.Effect.PISTON)
        for component in (shape_c, scorer_c, bouncy, piston):
            self.game.toolbox.add(component)
            self.game._use_component(component)

        self.game._assemble_block()

        blocks = [i for i in self.game.toolbox.items if i.kind == "block"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(set(blocks[0].effects), {main.Effect.BOUNCY, main.Effect.PISTON})
        self.assertEqual(blocks[0].effect, main.Effect.BOUNCY)  # first effect
        self.assertTrue(blocks[0].has_effect(main.Effect.PISTON))


    def test_disassembling_multi_effect_block_returns_all_effect_components(self):
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.BOUNCY,
                               main.Scorer.CHIPS_ADD, 10, 20, "B",
                               effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        self.game.toolbox.add(block)
        self.game.selected_toolbox_item = block
        self.game.cash = 100

        self.game._disassemble_block()

        effects = [i for i in self.game.toolbox.items if i.kind == main.Component.EFFECT]
        self.assertEqual(len(effects), 2)
        self.assertEqual({e.value for e in effects}, {main.Effect.BOUNCY, main.Effect.PISTON})


    def test_disassembling_portal_block_deletes_paired_toolbox_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        self.game.toolbox.add(a)
        self.game.toolbox.add(b)
        self.game.cash = 100
        self.game.selected_toolbox_item = a

        self.game._disassemble_block()

        # The paired portal block is deleted; only a's three parts remain.
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 0)
        self.assertEqual(len(self.game.toolbox.items), 3)
        self.assertNotIn(b, self.game.toolbox.items)


    def test_disassembling_portal_block_deletes_paired_grid_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=7)
        self.game.toolbox.add(a)
        self.game.grid[(5, 5)] = b
        self.game.cash = 100
        self.game.selected_toolbox_item = a

        self.game._disassemble_block()

        self.assertNotIn((5, 5), self.game.grid)  # the placed paired portal is deleted


    def test_refunding_portal_block_preserves_number(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                           scorer=main.Scorer.NONE, portal_number=9)
        self.game.toolbox.items.clear()

        self.game._refund_block(block)

        portal = [i for i in self.game.toolbox.items if i.effect == main.Effect.PORTAL]
        self.assertEqual(len(portal), 1)
        self.assertEqual(portal[0].portal_number, 9)


    def test_selling_portal_block_deletes_paired_toolbox_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        self.game.toolbox.add(a)
        self.game.toolbox.add(b)
        self.game._equip_block(a)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertEqual(self.game.cash, 50 + a.price // 2)
        self.assertNotIn(a, self.game.toolbox.items)
        self.assertNotIn(b, self.game.toolbox.items)  # the paired portal is deleted too
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 0)


    def test_selling_portal_block_deletes_paired_grid_block(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=7)
        self.game.toolbox.add(a)
        self.game.grid[(5, 5)] = b
        self.game._equip_block(a)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertNotIn(a, self.game.toolbox.items)
        self.assertNotIn((5, 5), self.game.grid)  # the placed paired portal is deleted


    def test_selling_portal_block_deletes_partner_and_refunds(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        self.game.toolbox.add(a)
        self.game.toolbox.add(b)
        self.game.selected_toolbox_item = a
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertNotIn(a, self.game.toolbox.items)
        self.assertNotIn(b, self.game.toolbox.items)  # the partner is deleted
        self.assertEqual(self.game.cash, 50 + a.price // 2)


    def test_selling_non_portal_block_leaves_portal_pairs_alone(self):
        self.game.toolbox.items.clear()
        a = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal A", portal_number=7)
        b = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.PORTAL, main.Scorer.NONE,
                           0, 50, "Portal B", portal_number=7)
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Plain")
        for item in (a, b, plain):
            self.game.toolbox.add(item)
        self.game._equip_block(plain)
        self.game.cash = 50

        self.game._sell_selected_item()

        self.assertIn(a, self.game.toolbox.items)
        self.assertIn(b, self.game.toolbox.items)  # selling a plain block doesn't touch portals


    def test_placing_assembled_block_via_events(self):
        self.game.toolbox.items.clear()
        shape_c = main.Component.shape_component(main.Shape.RECT, 0, "Rect")
        effect_c = main.Component.effect_component(main.Effect.NONE, 0, "None")
        scorer_c = main.Component.scorer_component(main.Scorer.CHIPS_ADD, 10, 0, "+Chips")
        for component in (shape_c, effect_c, scorer_c):
            self.game.toolbox.add(component)
            self.game._use_component(component)
        self.game._assemble_block()

        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=self._grid_pos(1, 1)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()

        self.assertIn((1, 1), self.game.grid)
        self.assertFalse(self.game.has_selected)  # one block per assembly
        # The assembled block was consumed from the toolbox when placed.
        self.assertEqual(len([i for i in self.game.toolbox.items if i.kind == "block"]), 0)
