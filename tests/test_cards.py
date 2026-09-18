"""Cards: conditions, whole cards and the composed card halves.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class CardsTests(GameTestCase):
    """Cards: conditions, whole cards and the composed card halves."""


    def test_sharp_scorer_card_destroyed_on_continue(self):
        # Sharp cards (a generic card whose scorer half is Sharp) each have a
        # 1/4 chance to be destroyed after every run; other cards always
        # survive the move-on.
        sharp_pipe = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        sharp_start = main.condition_scorer_card(
            main.Condition.START, main.Scorer.SHARP)
        cash_pipe = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.CASH)
        mult_pipe = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.MULT_ADD)
        self.game.cards = [
            main.CardItem(sharp_pipe, 40), main.CardItem(sharp_start, 40),
            main.CardItem(cash_pipe, 40), main.CardItem(mult_pipe, 40),
        ]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.0):  # always destroyed
            self.game._continue_run()
        values = [card.value for card in self.game.cards]
        self.assertNotIn(sharp_pipe, values)
        self.assertNotIn(sharp_start, values)
        self.assertIn(cash_pipe, values)
        self.assertIn(mult_pipe, values)


    def test_sharp_scorer_card_survives_continue_when_lucky(self):
        sharp = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards = [main.CardItem(sharp, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.9):  # no destruction
            self.game._continue_run()
        self.assertEqual([card.value for card in self.game.cards], [sharp])


    def test_sharp_scorer_card_survives_retry(self):
        # Retrying a run discards it, so no Sharp card is destroyed (destruction
        # only happens after a run).
        sharp = main.condition_scorer_card(
            main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards = [main.CardItem(sharp, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        with mock.patch("main.random.random", return_value=0.0):
            self.game._retry_run()
        self.assertEqual([card.value for card in self.game.cards], [sharp])


    def test_resource_points_discarded_on_retry(self):
        # A retry is a full do-over for resource points: the run's pending gain
        # AND the points banked from earlier runs are all reset (a NEW run
        # keeps the bank — see test_resource_points_persist_across_runs).
        self.game.toolbox.items.clear()
        self.game.shred_points = 2
        self.game.rubble_points = 3
        self.game.idea_points = 1
        self.game.option_points = 4
        self.game.bonus_slots = 1  # already converted: not a point any more
        self.game.run_active = True
        block = main.Block(0, 0, scorer=main.Scorer.RUBBLE)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.rubble_run_gain, 0.5)
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.rubble_run_gain, 0)
        self.assertEqual(self.game.shred_run_gain, 0)
        self.assertEqual(self.game.idea_run_gain, 0)
        self.assertEqual(self.game.option_run_gain, 0)
        self.assertEqual(self.game.shred_points, 0)
        self.assertEqual(self.game.rubble_points, 0)
        self.assertEqual(self.game.idea_points, 0)
        self.assertEqual(self.game.option_points, 0)
        # A reward the bank already paid for stays (it is no longer a point).
        self.assertEqual(self.game.bonus_slots, 1)
        blocks = [i for i in self.game.toolbox.items if getattr(i, "kind", None) == "block"]
        self.assertEqual(blocks, [])


    def test_garden_card_doubles_the_per_seed_mult(self):
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 46))
        self.game.grid[(0, 0)] = touched = main.Block(0, 0, scorer=main.Scorer.SEED)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.SEED)
        marble = self._add_marble()
        marble.collisions_this_tick = [touched]
        self.game.run_active = True
        self.game.score_mult = 2
        self.game._handle_block_contacts([touched])
        # Garden: +6 mult per seed x 2 seeds = +12 mult.
        self.assertEqual(self.game.score_mult, 14)


    def test_the_nine_utility_whole_cards_are_defined(self):
        expected = [(main.Card.PEDESTAL, "Pedestal", 44),
                    (main.Card.INFERNO, "Inferno", 50),
                    (main.Card.DOPPELGANGER, "Doppelganger", 46),
                    (main.Card.COMPOUND_INTEREST, "Compound Interest", 36),
                    (main.Card.COUPON, "Coupon", 46),
                    (main.Card.FACTORY, "Factory", 44),
                    (main.Card.MINESHAFT, "Mineshaft", 28),
                    (main.Card.MARKET, "Market", 26),
                    (main.Card.WATCH, "Watch", 40)]
        for value, name, price in expected:
            self.assertIn(value, main.Card.ORDER)
            self.assertEqual(main.Card.name(value), name)
            self.assertEqual(main.Card.PRICES[value], price)
            self.assertTrue(main.Card.comment(value))
            self.assertTrue(main.Card.description(value))
            self.assertIn(value, main.Card.COLORS)
            self.assertIn(value, main.Card.GLYPHS)
            # Every whole card is indivisible: no (condition, scorer) rebuilds it.
            self.assertFalse(components.is_splittable_card(value))
            self.assertIsNone(components.splittable_card_condition_scorer(value))
        # The nine ids are unique and never collide with a condition's id (the
        # two namespaces share the space below Condition.SHAPE_BASE, where the
        # only pre-existing overlap is Few Blocks / ERR 404 on id 9).
        new_ids = {value for value, _, _ in expected}
        self.assertEqual(len(new_ids), 9)
        self.assertFalse(new_ids & {c for c in components.CONDITION_ORDER if c < 100})


    def test_pedestal_retriggers_the_first_three_blocks(self):
        self.game.cards.append(main.CardItem(main.Card.PEDESTAL, 44))
        self.game.score_mult = 1
        for i in range(3):
            block = main.Block(i, 5, scorer=main.Scorer.MULT_ADD, scorer_amount=4)
            self._touch_blocks([block])
            # Every one of the first three blocks scored twice (+4 and +4).
            self.assertEqual(self.game.score_mult, 1 + 8 * (i + 1))
        # The fourth block is past the pedestal and scores only once.
        self._touch_blocks([main.Block(4, 5, scorer=main.Scorer.MULT_ADD,
                                       scorer_amount=4)])
        self.assertEqual(self.game.score_mult, 1 + 8 * 3 + 4)


    def test_pedestal_needs_the_card_and_retriggers_only_real_scores(self):
        # Without the card each block scores once.
        self.game.score_mult = 1
        self._touch_blocks([main.Block(0, 5, scorer=main.Scorer.MULT_ADD,
                                       scorer_amount=4)])
        self.assertEqual(self.game.score_mult, 5)
        # With the card a no-scorer block (a plain wall) is retriggered into
        # nothing — it has no scorer to fire twice.
        self.game.cards.append(main.CardItem(main.Card.PEDESTAL, 44))
        self.game.score_mult = 1
        self._touch_blocks([main.Block(1, 5, scorer=main.Scorer.NONE)])
        self.assertEqual(self.game.score_mult, 1)


    def test_inferno_raises_the_total_score_exponent(self):
        self.game.score_chips = 100
        self.game.score_mult = 1
        self.game.run_time = main.TIME_IDEAL
        plain = self.game._compute_total_score()
        self.game.cards.append(main.CardItem(main.Card.INFERNO, 50))
        boosted = self.game._compute_total_score()
        # total = (chips * mult) ** exponent, so Inferno multiplies the score
        # by the base raised to 0.07.
        self.assertAlmostEqual(boosted, plain * (100 * 1) ** 0.07, places=6)
        self.assertGreater(boosted, plain)


    def test_doppelganger_releases_a_second_marble_per_start_block(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(len(self.game.marbles), 1)
        self.assertEqual(float(self.game.marbles[0].velocity[0]), 0.0)

        self.game.cards.append(main.CardItem(main.Card.DOPPELGANGER, 46))
        self.game.reset_run()

        self.assertEqual(len(self.game.marbles), 2)
        first, second = self.game.marbles
        self.assertIs(first.start_block, second.start_block)
        self.assertEqual(float(first.velocity[0]), 0.0)
        self.assertEqual(float(second.velocity[0]), 1.0)  # the new marble drifts
        self.assertEqual(float(second.velocity[1]), 0.0)
        # Both are configured like the save's marble type (same radius/mass).
        self.assertEqual(first.radius, second.radius)
        self.assertEqual(first.mass, second.mass)


    def test_doppelganger_doubles_every_start_block(self):
        # Two Start blocks plus Doppelganger release four marbles.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.grid[(1, 0)] = main.Block(1, 0, scorer=main.Scorer.START)
        self.game.cards.append(main.CardItem(main.Card.DOPPELGANGER, 46))

        self.game.reset_run()

        self.assertEqual(len(self.game.marbles), 4)


    def test_factory_halves_resource_conversion_costs(self):
        # Every conversion costs ONE point, whatever the reward.
        self.assertEqual(self.game._resource_cost(), 1)

        self.game.cards.append(main.CardItem(main.Card.FACTORY, 44))

        # Factory needs half a point instead. That is a real half now that
        # points are fractional, so a single 1/2-point Rubble trigger converts
        # on its own.
        self.assertEqual(self.game._resource_cost(), 0.5)


    def test_factory_converts_resources_at_the_halved_cost(self):
        self.game.cards.append(main.CardItem(main.Card.FACTORY, 44))
        self.game.toolbox.items.clear()
        self.game.rubble_points = 1
        self.game.rubble_run_gain = 0

        self.game._commit_resource_points()

        # One point at half a point per block buys two blocks, not one.
        self.assertEqual(self.game.rubble_points, 0)
        self.assertEqual(len(self.game.toolbox.items), 2)


    def test_watch_ends_the_run_at_the_ideal_finish_time(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.game.run_time = main.TIME_IDEAL - main.DT

        self.game.update()

        # Without Watch the run is still going at the ideal time ...
        self.assertFalse(self.game.run_complete)
        self.assertTrue(self.game.run_active)
        # ... with Watch it ends right there.
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        self.game.run_time = main.TIME_IDEAL - main.DT
        self.game.update()
        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.awaiting_after_run)


    def test_watch_lets_only_the_first_five_blocks_score(self):
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        self.game.score_mult = 1
        blocks = [main.Block(i, 5, scorer=main.Scorer.MULT_ADD, scorer_amount=4)
                  for i in range(6)]

        self._touch_blocks(blocks)

        # The first five blocks pay +4 each; the sixth pays nothing, though its
        # trigger is still spent (so it shows as used up).
        self.assertEqual(self.game.score_mult, 1 + 4 * 5)
        self.assertEqual(blocks[5].triggers_left, 0)
        self.assertEqual(blocks[4].triggers_left, 0)


    def test_watch_leaves_collision_cards_alone(self):
        # Watch gates the BLOCKS' scorers: a card that reacts to a collision
        # still fires on every matching hit, including past the fifth block.
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        blocks = [main.Block(i, 5, shape=main.Shape.PIPE,
                             scorer=main.Scorer.CHIPS_ADD, scorer_amount=30,
                             trigger_limit=2) for i in range(6)]

        self._touch_blocks(blocks)

        # Five blocks scored their +30 chips; the Pipe card paid on all six.
        self.assertEqual(self.game.score_chips, 5 * 30 + 6 * 30)


    def test_watch_state_resets_each_run(self):
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.run_first_blocks = [main.Block(9, 9, scorer=main.Scorer.NONE)]

        self.game.reset_run()

        self.assertEqual(self.game.run_first_blocks, [])


    def test_procrastination_rewinds_the_run_instead_of_ending_it(self):
        # The run's FIRST completion rewinds it: the marbles fly their last
        # second again with every block trigger refilled, so the run carries on
        # instead of ending.
        marble, block = self._start_procrastination_run()
        frames = 0
        while not self.game.procrastination_used and frames < 300:
            self.game.update()
            frames += 1

        self.assertTrue(self.game.procrastination_used)
        self.assertTrue(self.game.run_active)          # still going
        self.assertFalse(self.game.run_complete)
        self.assertFalse(self.game.awaiting_after_run)
        self.assertFalse(marble.finished)              # flying, not parked
        self.assertEqual(block.triggers_left, block.trigger_limit)  # refilled
        # The second that was rewound is gone: the replayed frames start over.
        self.assertLess(len(marble.history),
                        main.PROCRASTINATION_REWIND_FRAMES + 1)
        # The refilled trigger pays again as the marble replays the fall...
        chips_at_rewind = self.game.score_chips
        frames = 0
        while not self.game.run_complete and frames < 300:
            self.game.update()
            frames += 1
        self.assertGreater(self.game.score_chips, chips_at_rewind)
        # ...and the run really ends the second time (no second rewind).
        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.run_active)
        self.assertIn("Procrastination", self.game.shop_message)


    def test_without_the_card_the_first_completion_ends_the_run(self):
        _marble, _block = self._start_procrastination_run(own_card=False)
        frames = 0
        while not self.game.run_complete and frames < 300:
            self.game.update()
            frames += 1

        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.procrastination_used)


    def test_the_card_cutter_silences_the_rewind(self):
        marble, block = self._start_procrastination_run()
        self.game.disabled_card = self.game.cards[0]

        self.assertFalse(self.game._procrastination_rewind())

        self.assertFalse(self.game.procrastination_used)
        block.triggers_left = 0
        frames = 0
        while not self.game.run_complete and frames < 300:
            self.game.update()
            frames += 1
        self.assertTrue(self.game.run_complete)  # the run just ended as usual


    def test_essence_card_data(self):
        self.assertIn(main.Card.ESSENCE, main.Card.ORDER)
        self.assertEqual(main.Card.name(main.Card.ESSENCE), "Essence")
        self.assertEqual(main.Card.PRICES[main.Card.ESSENCE], 48)
        self.assertTrue(main.Card.comment(main.Card.ESSENCE))
        self.assertIn(main.Card.ESSENCE, main.Card.COLORS)
        self.assertIn(main.Card.ESSENCE, main.Card.GLYPHS)
        description = main.Card.description(main.Card.ESSENCE)
        for part in ("$10", "card slot", "2", "Spirit token"):
            self.assertIn(part, description)
        # Every whole card is indivisible: no (condition, scorer) rebuilds it.
        self.assertFalse(components.is_splittable_card(main.Card.ESSENCE))


    def test_essence_takes_a_card_slot_away(self):
        # The area holds MAX_CARDS cards; Essence trades one away and its own
        # slot counts, so it needs room for the SMALLER area to be bought.
        self.assertEqual(self.game.max_cards, main.MAX_CARDS)
        self.assertEqual(self.game._card_capacity_for(main.Card.ESSENCE),
                         main.MAX_CARDS - 1)
        self.game.cash = 1000
        # At MAX_CARDS - 1 cards there is no room for it at all.
        self.game.cards = self._card_fillers(main.MAX_CARDS - 1)
        self.game._buy_shop_item(main.CardItem(main.Card.ESSENCE, 48))
        self.assertEqual(len(self.game.cards), main.MAX_CARDS - 1)
        self.assertTrue(self.game.shop_message)
        # One slot free and it fits: the area is now a slot smaller.
        self.game.cards = self._card_fillers(main.MAX_CARDS - 2)
        self.game._buy_shop_item(main.CardItem(main.Card.ESSENCE, 48))
        self.assertEqual(len(self.game.cards), main.MAX_CARDS - 1)
        self.assertEqual(self.game.max_cards, main.MAX_CARDS - 1)
        # ...so nothing else fits either, and the missing slot is not clickable.
        self.game._buy_shop_item(self._card_fillers(1)[0])
        self.assertEqual(len(self.game.cards), main.MAX_CARDS - 1)
        self.assertIn(str(main.MAX_CARDS - 1), self.game.shop_message)
        gone = pygame.Rect(main.CARD_AREA_COORDS[0] + (main.MAX_CARDS - 1) * main.GRID_SIZE,
                           main.CARD_AREA_COORDS[1], main.GRID_SIZE, main.GRID_SIZE)
        self.assertIsNone(self.game.card_area_item_at(gone.center))
        self.assertEqual(self.game.card_area_item_at(
            pygame.Rect(main.CARD_AREA_COORDS[0], main.CARD_AREA_COORDS[1],
                        main.GRID_SIZE, main.GRID_SIZE).center),
            self.game.cards[0])
        # Selling it gives the slot back.
        essence = next(c for c in self.game.cards
                       if c.value == main.Card.ESSENCE)
        self.game.selected_toolbox_item = essence
        self.game._sell_selected_item()
        self.assertEqual(self.game.max_cards, main.MAX_CARDS)


    def test_essence_pays_ten_at_the_end_of_every_run(self):
        # The $10 is part of the end-of-run cash award, with its own line in the
        # breakdown (and a retry takes it back with the rest of the award).
        self.game.grid[(5, 1)] = main.Block(5, 1, scorer=main.Scorer.START)
        self.game.grid[(5, 9)] = main.Block(5, 9, scorer=main.Scorer.FINISH)
        self.game.cards = [main.CardItem(main.Card.ESSENCE, 48)]
        self.game.cash = 100
        self.game.reset_run()
        frames = 0
        while not self.game.run_complete and frames < 300:
            self.game.update()
            frames += 1

        self.assertTrue(self.game.run_complete)
        self.assertEqual(self.game.last_run_cash_breakdown["essence"],
                         main.ESSENCE_RUN_CASH)
        rows = dict(self.game._cash_breakdown_rows())
        self.assertIn("Essence", rows)
        self.assertIn(f"${main.ESSENCE_RUN_CASH}", rows["Essence"])
        # 20 base + 10 interest + 10 essence.
        self.assertEqual(self.game.cash, 100 + 20 + 10 + main.ESSENCE_RUN_CASH)
        self.assertEqual(self.game.last_run_cash_gained, 20 + 10 + main.ESSENCE_RUN_CASH)

        # Without the card the same run pays no essence line.
        self.game.cards = []
        self.game.awaiting_after_run = False
        self.game.cash = 100
        self.game.reset_run()
        self.game.run_time = main.TIME_IDEAL
        for _ in range(300):
            self.game.update()
            if self.game.run_complete:
                break
        self.assertEqual(self.game.last_run_cash_breakdown["essence"], 0)


    def test_the_death_action_also_distils_essence(self):
        # "Sold" covers every sale: the Death action goes through the same rule.
        self.game.cards = [main.CardItem(main.Card.ESSENCE, 48)]
        action = main.ActionItem(main.Action.DEATH, 60)

        self.assertTrue(self.game._action_death(action, self.game.cards[0]))

        self.assertEqual(self.game.cards, [])
        self.assertEqual(len(self.game.tokens), main.ESSENCE_TOKENS)
        self.assertIn("Spirit token", self.game.shop_message)


    def test_concert_card_data(self):
        self.assertIn(main.Card.CONCERT, main.Card.ORDER)
        self.assertEqual(main.Card.name(main.Card.CONCERT), "Concert")
        self.assertEqual(main.Card.PRICES[main.Card.CONCERT], 44)
        self.assertTrue(main.Card.comment(main.Card.CONCERT))
        self.assertIn(main.Card.CONCERT, main.Card.COLORS)
        self.assertIn(main.Card.CONCERT, main.Card.GLYPHS)
        description = main.Card.description(main.Card.CONCERT)
        for part in ("rect", "effect", "scorer", "1 more time per run"):
            self.assertIn(part, description)
        # Every whole card is indivisible: no (condition, scorer) rebuilds it.
        self.assertFalse(components.is_splittable_card(main.Card.CONCERT))
        self.assertEqual(main.CONCERT_TRIGGER_BONUS, 1)


    def test_concert_boosts_only_blocks_with_a_shape_an_effect_and_a_scorer(self):
        # The rule is all three at once: a real shape (not a plain rect), a real
        # effect, and a scorer. Without the card, none of them are boosted.
        qualifies = self._concert_block()
        rect = self._concert_block(shape=main.Shape.RECT, x=2, y=1)
        bare = self._concert_block(effects=(main.Effect.NONE,), x=3, y=1)
        scorerless = self._concert_block(scorer=main.Scorer.NONE, x=4, y=1)
        for block in (qualifies, rect, bare, scorerless):
            self.assertEqual(self.game._trigger_limit(block), 1)
        self.assertFalse(self.game._concert_boosts(qualifies))

        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]

        self.assertEqual(self.game._trigger_limit(qualifies), 2)
        self.assertEqual(self.game._trigger_limit(rect), 1)       # a plain rect
        self.assertEqual(self.game._trigger_limit(bare), 1)       # no effect
        self.assertEqual(self.game._trigger_limit(scorerless), 1)  # no scorer
        # The bonus is visible wherever the block's limit is shown, and it is
        # derived rather than written onto the block.
        self.assertEqual(self.game._item_name(qualifies), "Bouncy Pipe +Chips v2")
        self.assertEqual(qualifies.trigger_limit, 1)
        rows = dict(self.game._describe_item(qualifies))
        self.assertEqual(rows["Trigger"], "Scores 2 times per run (1 left)")
        # ...and the toolbox copy of a qualifying block shows it too.
        item = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 30, 20, "Pipe +Chips",
                              effects=[main.Effect.BOUNCY])
        self.assertEqual(self.game._trigger_limit(item), 2)
        self.assertIn("Scores 2 times per run",
                      dict(self.game._describe_item(item))["Trigger"])


    def test_concert_hands_out_the_extra_trigger_when_triggers_are_dealt(self):
        # A fresh run hands every block its limit, so a Concert block starts the
        # run with one more trigger than its own limit.
        block = self._concert_block()
        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]
        self.game.grid[(1, 5)] = main.Block(1, 5, scorer=main.Scorer.START)
        self.game.grid[(1, 9)] = main.Block(1, 9, scorer=main.Scorer.FINISH)
        block.triggers_left = 0  # spent in an earlier run

        self.assertTrue(self.game.reset_run())

        self.assertEqual(block.trigger_limit, 1)      # its own limit is untouched
        self.assertEqual(block.triggers_left, 2)      # the card's extra one is dealt
        # A Procrastination rewind hands them out again the same way.
        self.game.cards.append(main.CardItem(main.Card.PROCRASTINATION, 46))
        block.triggers_left = 0
        self.assertTrue(self.game._procrastination_rewind())
        self.assertEqual(block.triggers_left, 2)


    def test_a_block_placed_under_concert_arrives_with_the_extra_trigger(self):
        # Placing is where a block's triggers are dealt, so a qualifying block
        # placed while Concert is owned arrives with the extra one already.
        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]
        self.game.toolbox.items.clear()
        item = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 30, 20, "Pipe +Chips",
                              effects=[main.Effect.BOUNCY])
        self.game.toolbox.add(item)
        self.game._equip_block(item)
        self._click(self._grid_pos(1, 1))
        self.game.drawing = False

        placed = self.game.grid[(1, 1)]
        self.assertEqual(placed.trigger_limit, 1)
        self.assertEqual(placed.triggers_left, 2)


    def test_concert_blocks_really_spend_both_triggers(self):
        # End to end: the trigger Concert hands out is a real, spendable one, so
        # a touch, a leave and a re-touch pays twice in the same run.
        block = self._concert_block(shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD)
        block.scorer_amount = 10
        self.game.grid[(1, 5)] = main.Block(1, 5, scorer=main.Scorer.START)
        self.game.grid[(1, 9)] = main.Block(1, 9, scorer=main.Scorer.FINISH)
        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]
        self.assertTrue(self.game.reset_run())
        marble = self.game.marbles[0]
        self.assertEqual(block.triggers_left, 2)

        paid = []
        for this_tick, last_tick in (([block], []), ([], [block]), ([block], [])):
            self.game.score_chips = 0
            marble.collisions_this_tick = this_tick
            marble.collisions_last_tick = last_tick
            self.game._handle_block_contacts([block])
            paid.append(self.game.score_chips)

        self.assertEqual(paid, [10, 0, 10])   # the middle frame is a leave, not a touch
        self.assertEqual(block.triggers_left, 0)   # both triggers are spent


    def test_concert_stacks_with_a_paid_upgrade_and_deja_vu(self):
        block = self._concert_block()
        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]
        self.game.cash = 1000
        # A paid upgrade raises the block's OWN limit by one...
        self.game.selected_toolbox_item = block
        self.game._upgrade_trigger_limit()
        self.assertEqual(block.trigger_limit, 2)
        self.assertEqual(self.game._trigger_limit(block), 3)
        self.assertIn("Trigger limit now 3", self.game.shop_message)
        # ...and Deja Vu's +1 lands on top of both.
        self.assertTrue(self.game._action_deja_vu(
            main.ActionItem(main.Action.DEJA_VU, 24), block))
        self.assertEqual(block.trigger_limit, 3)
        self.assertEqual(self.game._trigger_limit(block), 4)
        self.assertIn("(now 4)", self.game.shop_message)


    def test_hands_tied_still_disables_a_concert_block(self):
        # The trial's cap is applied after Concert's bonus, so a disabled block
        # is not handed the extra trigger back.
        block = self._concert_block()
        self.game.cards = [main.CardItem(main.Card.CONCERT, 44)]
        self.game.grid[(1, 5)] = main.Block(1, 5, scorer=main.Scorer.START)
        self.game.grid[(1, 9)] = main.Block(1, 9, scorer=main.Scorer.FINISH)
        self.game.trial_maxed_blocks = {block}

        self.assertEqual(self.game._trigger_limit(block),
                         main.TRIAL_MAX_TRIGGERS)
        self.game.reset_run()

        self.assertEqual(block.triggers_left, 0)
        self.assertTrue(self.game._concert_boosts(block))  # still a Concert block


    # --- The Painting condition ---------------------------------------------

    def test_painting_condition_metadata(self):
        self.assertEqual(main.Condition.name(main.Condition.PAINTING), "Painting")
        self.assertEqual(main.condition_phase(main.Condition.PAINTING), "start")
        self.assertAlmostEqual(components.condition_ratio(main.Condition.PAINTING),
                               0.1)
        self.assertIn("total sell price",
                      main.condition_description(main.Condition.PAINTING))
        self.assertGreater(main.COMPONENT_PRICES[
            (main.Component.CONDITION, main.Condition.PAINTING)], 0)
        # Its id shares the small band with the whole cards without colliding.
        self.assertNotIn(main.Condition.PAINTING, main.Card.ORDER)
        self.assertEqual(main.Condition.GLYPHS[main.Condition.PAINTING], "P")


    def test_a_card_pays_its_own_scorer_magnitude(self):
        # A +Chips half rolled to 45 makes the start card add 45 chips, and a
        # +Mult half rolled to 6 adds +6 mult (30 and 4 at the averages).
        chips = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        mult = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        self.game.cards.append(main.make_card_item(chips, amount=45))
        self.game.cards.append(main.make_card_item(mult, amount=6))
        self.game.score_chips = 0
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertEqual(self.game.score_chips, 45)
        self.assertEqual(self.game.score_mult, 7)


    def test_a_card_without_a_magnitude_pays_the_average(self):
        # A card built by hand (or read from an old save) has no magnitude and
        # pays exactly what it always did.
        chips = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(chips, 30))
        self.game.score_chips = 0

        self.game._apply_cards()

        self.assertEqual(self.game.score_chips, 30)
        self.assertEqual(self.game.cards[0].amount, 0)


    def test_a_blueprint_copies_the_magnitude_too(self):
        # A Blueprint copies the card to its left — its value AND its roll.
        mult = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        self.game.cards.append(main.make_card_item(mult, amount=9))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 33))
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertEqual(self.game.score_mult, 1 + 9 + 9)  # both copies pay +9


    def test_a_card_built_from_a_component_keeps_the_pieces_magnitude(self):
        # Building a card consumes the scorer piece, so the card PAYS the
        # strength that piece was bought at: no laundering a cheap roll into
        # the average card (or the reverse). Its price is the catalog price
        # either way — a roll is never part of what something costs.
        for amount, expected in ((45, 45), (15, 15)):
            with self.subTest(amount=amount):
                self.game.toolbox.items.clear()
                self.game.cards.clear()
                condition = main.Component.condition_component(main.Condition.START)
                scorer = main.Component.scorer_component(main.Scorer.CHIPS_ADD,
                                                         amount=amount)
                self.game.toolbox.add(condition)
                self.game.toolbox.add(scorer)
                self.game.card_condition = condition
                self.game.card_scorer = scorer

                self.game._build_card()

                card = self.game.cards[-1]
                self.assertEqual(card.amount, amount)
                self.assertEqual(card.price, main.card_price_for(card.value))
                self.game.score_chips = 0
                self.game._apply_cards()
                self.assertEqual(self.game.score_chips, expected)


    def test_flat_scorer_cards_pay_their_own_magnitude(self):
        # Cash pays the card's own amount, and Sharp multiplies by it.
        cash = main.condition_scorer_card(main.Condition.START, main.Scorer.CASH)
        self.game.cards.append(main.make_card_item(cash, amount=24))
        self.game.card_cash_run_gain = 0
        self.game._apply_cards()
        self.assertEqual(self.game.card_cash_run_gain, 24)

        self.game.cards.clear()
        sharp = main.condition_scorer_card(main.Condition.START, main.Scorer.SHARP)
        self.game.cards.append(main.make_card_item(sharp, amount=5))
        self.game.score_mult = 2
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 10)

        # A resource card banks as many points as its magnitude says.
        self.game.cards.clear()
        shreds = main.condition_scorer_card(main.Condition.START, main.Scorer.SHREDS)
        self.game.cards.append(main.make_card_item(shreds, amount=3))
        self.game.shred_points = 0
        self.game.shred_run_gain = 0
        self.game._apply_cards()
        # A 3-magnitude Shreds banks 3 x 1/3 = a whole point.
        self.assertAlmostEqual(self.game.shred_points + self.game.shred_run_gain, 1.0)


    def test_granted_cards_roll_a_magnitude(self):
        random.seed(7)
        self.game.cards.clear()
        for _ in range(20):
            self.game._grant_random_card()
        composed = [c for c in self.game.cards if main.card_scorer(c.value)]
        self.assertTrue(composed)
        for card in composed:
            scorer = main.card_scorer(card.value)
            self.assertGreaterEqual(card.amount, main.scorer_magnitude_floor(scorer))
            self.assertEqual(card.price, main.card_price_for(card.value))


    def test_a_cards_magnitude_round_trips_through_a_save(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        self.game.cash = 100
        card = main.make_card_item(value, amount=45)
        self.game.cards.append(card)

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(save_system, "SAVES_DIR",
                                  os.path.join(tmp, "saves")):
            save_system.save_game(self.game)
            fresh = main.Game()
            fresh.save_slot = self.game.save_slot
            save_system.load_slot(fresh, self.game.save_slot)

        restored = fresh.cards[-1]
        self.assertEqual(restored.value, value)
        self.assertEqual(restored.amount, 45)
        self.assertEqual(restored.price, card.price)
        # An old save (no amount key) reads as a card with no magnitude, which
        # pays the average exactly as it used to.
        old = save_system._deserialize_item({"kind": "card", "value": value,
                                             "price": 30, "col": 0, "row": 0})
        self.assertEqual(old.amount, 0)


    def test_recognition_copies_a_cards_magnitude(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        original = main.make_card_item(value, amount=45)
        self.game.cards.append(original)
        self.game.cash = 1000
        action = main.ActionItem(main.Action.RECOGNITION, 24, version=2)
        self.game.actions.append(action)

        self.assertTrue(self.game._action_recognition(action, original))

        copy = self.game.cards[-1]
        self.assertIsNot(copy, original)
        self.assertEqual(copy.amount, 45)
        self.assertEqual(copy.price, original.price)


    def test_painting_pays_per_dollar_of_board_value(self):
        # A board worth $100 pays +0.4 mult per dollar x 100 = +40 mult.
        for i in range(4):
            block = main.Block(i, 5, scorer=main.Scorer.NONE)
            block.resale_price = 25
            self.game.grid[(i, 5)] = block
        self.assertEqual(main.cards.board_sell_total(self.game), 100)
        value = main.condition_scorer_card(main.Condition.PAINTING,
                                           main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertAlmostEqual(self.game.score_mult, 1 + 0.4 * 100)


    def test_painting_chips_card_scales_the_same_way(self):
        # +Chips pays 3 chips per dollar: a $50 board adds 150 chips.
        block = main.Block(0, 5, scorer=main.Scorer.NONE)
        block.resale_price = 50
        self.game.grid[(0, 5)] = block
        value = main.condition_scorer_card(main.Condition.PAINTING,
                                           main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0

        self.game._apply_cards()

        self.assertEqual(self.game.score_chips, 150)


    def test_rigged_casino_card_does_not_affect_plain_random_odds(self):
        # Without the card the even thirds still hold (0.9 -> xMult).
        block = main.Block(0, 0, scorer=main.Scorer.RANDOM)
        self.game.grid[(0, 0)] = block
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_mult = 2
        with mock.patch("main.random.random", return_value=0.5):  # middle -> mult
            self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.score_mult, 7)


    def test_cozy_condition_metadata(self):
        self.assertEqual(main.Condition.name(main.Condition.COZY), "Cozy")
        self.assertEqual(main.condition_phase(main.Condition.COZY), "start")
        self.assertAlmostEqual(components.condition_ratio(main.Condition.COZY), 3.0)
        self.assertIn("10 unlocked", main.condition_description(main.Condition.COZY))
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.CONDITION, main.Condition.COZY)], 0)


    def test_random_and_effective_are_card_scorers(self):
        # Random and Effective are now card scorers: they build a generic card
        # with any condition.
        for scorer in (main.Scorer.RANDOM, main.Scorer.EFFECTIVE):
            self.assertIn(scorer, components.CARD_SCORERS)
            self.assertIn(scorer, components.FLAT_CARD_SCORERS)
            value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, scorer)
            self.assertIsNotNone(value)
            self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
            self.assertIn(main.Scorer.name(scorer), main.Card.name(value))


    def test_random_card_fires_random_reward_on_collision(self):
        # A Pipe + Random generic card fires its one pre-rolled reward on every
        # matching pipe collision (the roll is chosen before the run).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.RANDOM)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 100
        self.game.score_mult = 2
        # v2 pipe: the block must still have a trigger left for the second
        # collision, since a collision card only fires while its block can.
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                          trigger_limit=2)
        with mock.patch("cards.random.random", return_value=0.0):  # +35 chips
            self._card_fire(pipe)
        self.assertEqual(self.game.score_chips, 135)
        # A second collision re-uses that same reward (the patched 0.9 would
        # have been +0.3 xMult).
        with mock.patch("cards.random.random", return_value=0.9):
            self._card_fire(pipe, self._add_marble())
        self.assertEqual(self.game.score_chips, 170)
        self.assertEqual(self.game.score_mult, 2)
        # A fresh run re-rolls it, so the card can pay the xMult this time.
        with mock.patch("cards.random.random", return_value=0.9):
            self.game._roll_run_random_outputs()
        self.assertEqual(self.game.cards[-1].random_rolls["reward"], 2)
        fresh_pipe = main.Block(1, 0, shape=main.Shape.PIPE,
                                scorer=main.Scorer.NONE)
        with mock.patch("cards.random.random", return_value=0.0):
            self._card_fire(fresh_pipe, self._add_marble())
        self.assertAlmostEqual(self.game.score_mult, 2 * 1.3)


    def test_effective_collision_card_checks_the_block_effects(self):
        # A Pipe + Effective card grants +1 xMult only when the hit pipe
        # block has 2+ effects.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.EFFECTIVE)
        self.game.cards.append(main.CardItem(value, 40))
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                          effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self.game.score_mult = 2
        self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult, 4.0)  # +1 xMult
        # A pipe with a single effect grants nothing (the mult stays 4.0).
        plain = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY])
        self._card_fire(plain, self._add_marble())
        self.assertAlmostEqual(self.game.score_mult, 4.0)


    def test_effective_start_card_fires_on_first_block_after_start(self):
        # A Start + Effective card can't fire at run start (no block known);
        # it fires once the run's first block is hit, if that block has 2+
        # effects.
        value = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.EFFECTIVE)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 2
        self.game._apply_cards()  # start phase: no block yet, so no reward
        self.assertEqual(self.game.score_mult, 2)
        first = main.Block(0, 0, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self._card_fire(first)
        self.assertAlmostEqual(self.game.score_mult, 4.0)


    def test_effective_end_card_checks_last_block_before_finish(self):
        # A Distance + Effective card checks the last block the marble hit
        # before finishing: +1 xMult when that block has 2+ effects.
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.EFFECTIVE)
        self.game.cards.append(main.CardItem(value, 40))
        # The run has to have travelled for the Distance condition to hold.
        self._add_marble().distance = 4000.0
        last = main.Block(0, 0, scorer=main.Scorer.NONE,
                          effects=[main.Effect.BOUNCY, main.Effect.SLIPPERY])
        self.game._last_contact_block = last
        self.game.score_mult = 2
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 4.0)
        # With a single-effect last block it grants nothing.
        plain = main.Block(0, 0, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY])
        self.game._last_contact_block = plain
        self.game.score_mult = 2
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_mult, 2)


    def test_start_parts_card_grants_component_at_run_start(self):
        # Regression: a start-of-run resource card (Ripped Card + Parts =
        # FEW_BLOCKS x Parts) fires when the run starts and grants its reward
        # (a component) immediately.
        value = main.condition_scorer_card(main.Condition.FEW_BLOCKS, main.Scorer.PARTS)
        self.game.cards.append(main.CardItem(value, 50))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.toolbox.items.clear()
        self.assertTrue(self.game.reset_run())
        comps = [i for i in self.game.toolbox.items if getattr(i, "kind", None)
                 in (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)]
        self.assertEqual(len(comps), 1)


    def test_card_data_lives_in_components(self):
        # Only the indivisible whole cards (the Card.ORDER catalog) remain as
        # whole cards; every splittable card is now composed from a condition +
        # a scorer.
        self.assertEqual(main.Card.ORDER,
                         [main.Card.ERR_404, main.Card.BLUEPRINT, main.Card.SHOWMAN,
                          main.Card.GARDEN, main.Card.RIGGED_CASINO,
                          main.Card.CONQUISTADOR, main.Card.PEDESTAL,
                          main.Card.INFERNO, main.Card.DOPPELGANGER,
                          main.Card.COMPOUND_INTEREST, main.Card.COUPON,
                          main.Card.FACTORY, main.Card.MINESHAFT, main.Card.MARKET,
                          main.Card.WATCH, main.Card.TESSERACT,
                          main.Card.THOUSAND_HANDED, main.Card.PROCRASTINATION,
                          main.Card.ESSENCE, main.Card.CONCERT])
        for value in main.Card.ORDER:
            self.assertTrue(main.Card.name(value))
            self.assertTrue(main.Card.comment(value))
            self.assertTrue(main.Card.description(value))
            self.assertGreater(main.Card.PRICES[value], 0)
            self.assertIn(value, main.Card.GLYPHS)
            self.assertIn(value, main.Card.COLORS)
        self.assertEqual(main.Card.description(main.Card.SHOWMAN),
                         "Lets cards you already own show up in the shop again, "
                         "so you can own more than one of the same card")
        # The three passive whole cards keep their exact descriptions.
        self.assertIn("+6 mult", main.Card.description(main.Card.GARDEN))
        self.assertIn("+xMult 3x more often",
                      main.Card.description(main.Card.RIGGED_CASINO))
        self.assertIn("4 random locked board squares",
                      main.Card.description(main.Card.CONQUISTADOR))
        # The ERR 404 card keeps its exact fake-fatal-error description.
        self.assertEqual(
            main.Card.description(main.Card.ERR_404),
            r"\marblatro\main.py, line 2339: 'self._return_card()' CardNotFoundError: Card was not found [FATAL]")
        # The classic splittable cards were removed: the conditions they split
        # into now carry their names AND their flavor comments.
        self.assertEqual(main.Condition.name(main.Condition.START), "Joker")
        self.assertEqual(main.Condition.comment(main.Condition.START), "Remember me?")
        self.assertEqual(main.Condition.comment(main.Condition.FRAGILE_BREAKS),
                         "Demolition expert.")
        self.assertEqual(main.Condition.comment(main.Condition.CASH_HELD),
                         "Money makes money.")
        # A composed magnitude card (Joker condition x +Mult) has full
        # metadata: a name, description, price, glyph, and color.
        value = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.MULT_ADD)
        self.assertEqual(main.Card.name(value), "Joker +Mult")
        self.assertIn("+4 mult", main.Card.description(value))
        self.assertGreater(main.Card.PRICES[value], 0)
        self.assertIn(value, main.Card.NAMES)
        self.assertIn(value, main.Card.GLYPHS)
        self.assertIn(value, main.Card.COLORS)


    def test_condition_data_lives_in_components(self):
        # Conditions are a purchasable component kind with the full catalogue:
        # the named triggers plus one collision condition per shape/effect.
        self.assertEqual(main.Component.CONDITION, "condition")
        # 13 named triggers (incl. Cozy, Painting and Synthesizer) + one
        # collision condition per shape/effect.
        self.assertEqual(len(main.CONDITION_ORDER),
                         13 + len(main.Shape.ORDER) + len(main.Effect.ORDER))
        # Named conditions are named after the card they were split from.
        self.assertEqual(main.Condition.name(main.Condition.COZY), "Cozy")
        self.assertEqual(main.Condition.name(main.Condition.START), "Joker")
        self.assertEqual(main.Condition.name(main.Condition.DISTANCE), "Explorer")
        self.assertEqual(main.Condition.name(main.Condition.FULLEST_COLUMN), "Pillar")
        self.assertIn("collides with a Pipe block",
                      main.condition_description(main.Condition.SHAPE_PIPE))
        self.assertGreater(main.COMPONENT_PRICES[
            (main.Component.CONDITION, main.Condition.START)], 0)
        comp = main.Component.condition_component(main.Condition.START)
        self.assertEqual(comp.kind, main.Component.CONDITION)
        self.assertEqual(comp.value, main.Condition.START)
        # Every shape/effect collision condition resolves back to its payload.
        for shape in main.Shape.ORDER:
            cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_shape(cond), shape)
        for effect in main.Effect.ORDER:
            cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_effect(cond), effect)


    def test_new_shapes_and_sticky_generate_card_conditions(self):
        # The two new line shapes and the sticky effect each auto-generate a
        # collision condition that builds a magnitude card like any other.
        for shape in (main.Shape.FLAT_LINE, main.Shape.CURVED_SLOPE_LINE):
            cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_shape(cond), shape)
            value = main.condition_scorer_card(cond, main.Scorer.MULT_ADD)
            self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)
        cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(main.Effect.STICKY)
        self.assertIn(cond, main.CONDITION_ORDER)
        self.assertEqual(components.condition_effect(cond), main.Effect.STICKY)


    def test_half_pipe_generates_card_condition(self):
        # The half-pipe shape auto-generates a collision condition that builds
        # a magnitude card like any other shape.
        shape = main.Shape.HALF_PIPE
        cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
        self.assertIn(cond, main.CONDITION_ORDER)
        self.assertEqual(components.condition_shape(cond), shape)
        value = main.condition_scorer_card(cond, main.Scorer.MULT_ADD)
        self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)


    def test_new_shapes_generate_card_conditions(self):
        # Each new shape auto-generates a collision condition that builds a
        # magnitude card like every other shape, and resolves back to the shape.
        for shape in self._new_shapes():
            cond = main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_shape(cond), shape)
            value = main.condition_scorer_card(cond, main.Scorer.MULT_ADD)
            self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)


    def test_effect_condition_ids_are_pinned_below_shape_growth(self):
        # EFFECT_BASE is a fixed id (not derived from len(Shape.ORDER)) so that
        # adding shapes never renumbers the effect collision conditions.
        self.assertGreater(main.Condition.EFFECT_BASE,
                           main.Condition.SHAPE_BASE + len(main.Shape.ORDER) - 1)


    def test_new_effects_generate_card_conditions(self):
        # Each new effect auto-generates a collision condition that resolves
        # back to the effect and builds a card like every other effect.
        for effect in self._new_effects():
            cond = main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect)
            self.assertIn(cond, main.CONDITION_ORDER)
            self.assertEqual(components.condition_effect(cond), effect)
            self.assertGreaterEqual(
                main.condition_scorer_card(cond, main.Scorer.MULT_ADD),
                components.CONDITION_CARD_OFFSET)


    def test_building_collision_card_from_condition_and_scorer(self):
        # Pipe condition + +Mult scorer builds the Pipe +Mult magnitude card.
        cond = main.Component.condition_component(main.Condition.SHAPE_PIPE)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self._assign_and_build(cond, scorer)
        expected = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                              main.Scorer.MULT_ADD)
        self.assertGreaterEqual(expected, components.CONDITION_CARD_OFFSET)
        self.assertEqual(len(self.game.cards), 1)
        self.assertEqual(self.game.cards[0].value, expected)
        self.assertEqual(main.Card.name(expected), "Pipe +Mult")
        self.assertNotIn(cond, self.game.toolbox.items)
        self.assertNotIn(scorer, self.game.toolbox.items)


    def test_building_canonical_named_card_recreates_whole_card(self):
        # Start condition + +Mult scorer recreates the Joker (a whole card).
        cond = main.Component.condition_component(main.Condition.START)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self._assign_and_build(cond, scorer)
        self.assertEqual(len(self.game.cards), 1)
        self.assertEqual(self.game.cards[0].value, main.Card.JOKER)


    def test_building_magnitude_card_creates_custom_card(self):
        # Explorer (Distance) + +Mult builds a derived custom card.
        cond = main.Component.condition_component(main.Condition.DISTANCE)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self._assign_and_build(cond, scorer)
        self.assertEqual(len(self.game.cards), 1)
        value = self.game.cards[0].value
        self.assertEqual(value, main.condition_scorer_card(main.Condition.DISTANCE,
                                                           main.Scorer.MULT_ADD))
        self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)
        self.assertEqual(main.Card.name(value), "Explorer +Mult")


    def test_card_builder_requires_a_scorer_and_known_combo(self):
        # A condition alone can't build anything.
        cond = main.Component.condition_component(main.Condition.SHAPE_PIPE)
        self.game.toolbox.items.clear()
        self.game.toolbox.add(cond)
        self.game._select_toolbox_component(cond)
        self.game._build_card()
        self.assertEqual(self.game.cards, [])
        self.assertTrue(self.game.shop_message)
        # Quick DOES pair with a run-END condition now: there is no next block
        # after the run, so the card pays from the run's last block hit instead.
        dist = main.Component.condition_component(main.Condition.DISTANCE)
        quick = main.Component.scorer_component(main.Scorer.QUICK, amount=5)
        self.game.toolbox.add(dist)
        self.game.toolbox.add(quick)
        self.game._select_toolbox_component(dist)
        self.game._select_toolbox_component(quick)
        self.game._build_card()
        self.assertEqual(len(self.game.cards), 1)
        self.assertEqual(main.Card.name(self.game.cards[0].value),
                         "Explorer card (Quick)")
        # Air Time (Plane) pairs with ANY scorer too: +Mult builds a
        # proportional Plane +Mult card (half the +4 base = +2 mult/air sec).
        air = main.Component.condition_component(main.Condition.AIR_TIME)
        scorer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=4)
        self.game.toolbox.add(air)
        self.game.toolbox.add(scorer)
        self.game._select_toolbox_component(air)
        self.game._select_toolbox_component(scorer)
        self.game._build_card()
        self.assertEqual(len(self.game.cards), 2)
        value = self.game.cards[1].value
        self.assertEqual(main.Card.name(value), "Plane +Mult")
        self.assertGreaterEqual(value, components.CONDITION_CARD_OFFSET)


    def test_start_chips_custom_card_gives_chips_at_run_start(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 50))
        self.game.score_chips = 0
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 30)


    def test_distance_custom_cards_scale_with_distance_travelled(self):
        # A full board (fraction 1.0) is 4 units: +120 chips or +16 mult.
        marble = self._add_marble()
        marble.distance = main.GRID_SIZE * main.GRID_WIDTH * main.GRID_HEIGHT
        chips_value = main.condition_scorer_card(main.Condition.DISTANCE,
                                                 main.Scorer.CHIPS_ADD)
        mult_value = main.condition_scorer_card(main.Condition.DISTANCE,
                                                main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(chips_value, 50))
        self.game.cards.append(main.CardItem(mult_value, 50))
        self.game.score_chips = 0
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_chips, 120)
        self.assertEqual(self.game.score_mult, 17)


    def test_collection_entries_hide_splittable_cards_and_list_conditions(self):
        # Only the indivisible cards appear as card entries; conditions are
        # their own collection entries.
        entries = self.game._collection_entries()
        card_entries = [e for e in entries if e[0] == "card"]
        self.assertEqual(len(card_entries), len(main.Card.ORDER))
        self.assertEqual({e[1] for e in card_entries}, set(main.Card.ORDER))
        cond_entries = [e for e in entries if e[0] == "condition"]
        self.assertEqual(len(cond_entries), len(components.CONDITION_ORDER))


    def test_every_block_scorer_is_a_card_scorer(self):
        # The card scorer set covers every block payoff scorer, and a flat
        # scorer builds a generic card with a collision condition.
        self.assertIn(main.Scorer.CASH, components.CARD_SCORERS)
        self.assertIn(main.Scorer.SHARP, components.CARD_SCORERS)
        self.assertIn(main.Scorer.QUICK, components.CARD_SCORERS)
        self.assertIn(main.Scorer.PARTS, components.CARD_SCORERS)
        self.assertIn(main.Scorer.IDEAS, components.CARD_SCORERS)
        for scorer in (main.Scorer.CASH, main.Scorer.SHARP, main.Scorer.QUICK,
                       main.Scorer.PARTS, main.Scorer.SHREDS,
                       main.Scorer.RUBBLE, main.Scorer.IDEAS):
            value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, scorer)
            self.assertIsNotNone(value)
            self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
            self.assertEqual(main.Card.name(value),
                             f"Pipe card ({main.Scorer.name(scorer)})")
        # Quick pairs with a run-end condition too: the card pays from the
        # speed of the run's LAST block hit (there is no next block then).
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.QUICK)
        self.assertIsNotNone(value)
        self.assertEqual(main.Card.name(value), "Explorer card (Quick)")


    def test_every_condition_and_card_scorer_pair_forms_a_card(self):
        # The whole grid: EVERY condition pairs with EVERY card scorer to form
        # a real card (a name, a description, a price and a split back into its
        # two halves), so no combination a player can assemble is a dead end.
        self.assertEqual(len(components.CARD_SCORERS),
                         len(main.Scorer.ORDER) - 3)  # NONE, START, FINISH
        for role in (main.Scorer.NONE, main.Scorer.START, main.Scorer.FINISH):
            self.assertNotIn(role, components.CARD_SCORERS)
        pairs = 0
        for cond in components.CONDITION_ORDER:
            cond_desc = main.condition_description(cond)
            flat_desc = components.condition_flat_description(cond)
            for scorer in components.CARD_SCORERS:
                value = main.condition_scorer_card(cond, scorer)
                self.assertIsNotNone(value, (cond, scorer))
                desc = main.Card.description(value)
                self.assertTrue(main.Card.name(value))
                self.assertTrue(desc, (cond, scorer))
                self.assertGreater(main.Card.PRICES[value], 0)
                # Every card says what makes its condition fire: a unit scorer
                # scales per unit (the magnitude phrasing), while a flat scorer
                # pays one trigger and reads the condition's gate.
                expected = (cond_desc if scorer in components.UNIT_CARD_SCORERS
                            else flat_desc)
                self.assertIn(expected, desc)
                # ...and no card falls back to the "unknown scorer" text or
                # leaks the no-condition placeholder.
                self.assertNotIn("Unknown", desc)
                self.assertNotIn("its block", desc)
                # The card splits back into exactly the pair that built it.
                self.assertEqual(
                    main.splittable_card_condition_scorer(value), (cond, scorer))
                pairs += 1
        self.assertEqual(pairs, len(components.CONDITION_ORDER)
                         * len(components.CARD_SCORERS))


    def test_flat_cards_state_the_gate_not_a_per_unit_measure(self):
        # A flat card pays ONE trigger, so it must not claim to scale with the
        # condition's measured units ("for each second the marble is in the
        # air", "scaled up to 4x base by the distance the marble travels"):
        # it states the gate instead. The magnitude (unit scorer) version of
        # the same condition keeps the measure, because it really scales.
        distance_measure = "scaled up to 4x base by the distance the marble travels"
        air_measure = "for each second the marble is in the air"

        flat_end = main.Card.description(
            main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.SUMMIT))
        self.assertNotIn(distance_measure, flat_end)
        self.assertIn("once the marble has traveled", flat_end)

        unit_end = main.Card.description(
            main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.MULT_ADD))
        self.assertIn(distance_measure, unit_end)

        flat_air = main.Card.description(
            main.condition_scorer_card(main.Condition.AIR_TIME, main.Scorer.PARTS))
        self.assertNotIn(air_measure, flat_air)
        self.assertIn("once the marble has been in the air", flat_air)

        unit_air = main.Card.description(
            main.condition_scorer_card(main.Condition.AIR_TIME, main.Scorer.CHIPS_ADD))
        self.assertIn(air_measure, unit_air)

        # Conditions that never had a measure read the same either way, and a
        # collision condition is untouched.
        for scorer in (main.Scorer.PARTS, main.Scorer.MULT_ADD):
            cozy = main.Card.description(
                main.condition_scorer_card(main.Condition.COZY, scorer))
            self.assertIn("when the board has 10 unlocked units or fewer", cozy)
        pipe = main.Card.description(
            main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.CASH))
        self.assertIn("when the marble collides with a Pipe block", pipe)
        self.assertIn("$15 when the marble collides", pipe)  # no comma: a clause
        # A time adverbial gets its own comma instead of running the two
        # clauses together ("… the first block the marble hits this run at the
        # start of the run").
        row = main.Card.description(
            main.condition_scorer_card(main.Condition.FULLEST_COLUMN,
                                       main.Scorer.POWERLINE))
        self.assertIn("this run, at the start of the run", row)
        # The magnitude phrasing is still available for the unit cards and for
        # anything else that asks for it (the collection's condition rows).
        self.assertIn(distance_measure,
                      main.condition_description(main.Condition.DISTANCE))
        self.assertEqual(components.condition_flat_description(main.Condition.START),
                         main.condition_description(main.Condition.START))


    def test_block_relative_cards_name_the_block_their_condition_hands_them(self):
        # A card has no position of its own, so a position-reading payoff (a
        # row, a border, neighbours, a bomb) says which block it reads.
        for scorer in (main.Scorer.POWERLINE, main.Scorer.FRONTIER,
                       main.Scorer.CLUSTER, main.Scorer.BOMB):
            collision = main.Card.description(
                main.condition_scorer_card(main.Condition.SHAPE_PIPE, scorer))
            self.assertIn("the collided block", collision)
            start = main.Card.description(
                main.condition_scorer_card(main.Condition.START, scorer))
            self.assertIn("the first block the marble hits this run", start)
            end = main.Card.description(
                main.condition_scorer_card(main.Condition.DISTANCE, scorer))
            self.assertIn("the last block the marble hits this run", end)
            fragile = main.Card.description(
                main.condition_scorer_card(main.Condition.FRAGILE_BREAKS, scorer))
            self.assertIn("the shattered block", fragile)


    def test_powerline_card_counts_the_blocks_in_the_collided_row(self):
        # A Pipe x Powerline card pays its chips for every block in the row of
        # the block the marble hit (the collided block included).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.POWERLINE)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        for x in (2, 5):
            self.game.grid[(x, 4)] = main.Block(x, 4, scorer=main.Scorer.NONE)
        pipe = main.Block(0, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.grid[(0, 4)] = pipe
        self._card_fire(pipe)
        self.assertEqual(self.game.score_chips,
                         main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE] * 3)


    def test_cluster_card_counts_the_blocks_next_to_the_collided_block(self):
        # A Cluster card pays its mult for each block orthogonally adjacent to
        # the collided block (two here, one of them diagonal and not counted).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.CLUSTER)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        for cell in ((3, 4), (4, 5), (3, 5)):  # (3,5) is diagonal
            self.game.grid[cell] = main.Block(cell[0], cell[1],
                                              scorer=main.Scorer.NONE)
        pipe = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.grid[(4, 4)] = pipe
        self._card_fire(pipe)
        self.assertEqual(self.game.score_mult,
                         1 + main.Scorer.DEFAULT_AMOUNT[main.Scorer.CLUSTER] * 2)


    def test_colossus_card_scales_with_the_touching_marble_radius(self):
        # A Colossus card pays its xMult for each pixel the touching marble's
        # radius is above the base size (a card measures the marble it fires
        # with, or the run's own marble when the condition hands it none).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.COLOSSUS)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 2
        marble = self._add_marble()
        marble.radius = main.MARBLE_RADIUS + 5
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=marble)
        self.assertAlmostEqual(self.game.score_mult,
                               2 * (1 + 5 * main.Scorer.DEFAULT_AMOUNT[main.Scorer.COLOSSUS]))


    def test_echo_card_refires_the_collided_block_scorer(self):
        # An Echo card has no "block touched before it", so it copies the block
        # its condition is about: a Pipe x Echo card re-fires the collided
        # block's own scorer (here a Cash block, paid twice over).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.ECHO)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.cash = 0
        self.game.run_cash_gained = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.CASH)
        self.game.grid[(0, 0)] = pipe
        self._card_fire(pipe)
        self.assertEqual(self.game.run_cash_gained,
                         2 * main.Scorer.DEFAULT_AMOUNT[main.Scorer.CASH])


    def test_bomb_card_primes_the_collided_cell(self):
        # A Bomb card plants a bomb on the cell of the block its condition
        # hands it, exactly like a Bomb block (the units around it unlock after
        # the run).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.BOMB)
        self.game.cards.append(main.CardItem(value, 40))
        pipe = main.Block(3, 2, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.assertNotIn((3, 2), self.game.bomb_cells)
        self._card_fire(pipe)
        self.assertIn((3, 2), self.game.bomb_cells)


    def test_bomb_card_is_destroyed_after_the_run(self):
        # A Bomb card is a one-run deal: it goes off with the block it primed,
        # so it is destroyed after the run for good (only a retry keeps it).
        bomb = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                         main.Scorer.BOMB)
        cash = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                         main.Scorer.CASH)
        self.game.cards = [main.CardItem(bomb, 40), main.CardItem(cash, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        values = [card.value for card in self.game.cards]
        self.assertNotIn(bomb, values)
        self.assertIn(cash, values)


    def test_bomb_card_survives_retry(self):
        # Retrying the run discards it, so the Bomb card is kept.
        bomb = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                         main.Scorer.BOMB)
        self.game.cards = [main.CardItem(bomb, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual([card.value for card in self.game.cards], [bomb])


    def test_start_block_relative_card_waits_for_the_first_block(self):
        # A start-phase Powerline card has no row to read at run start, so it
        # waits for the run's first contacted block and pays from that row.
        value = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.POWERLINE)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game._apply_cards()  # run start: no block has been hit yet
        self.assertEqual(self.game.score_chips, 0)
        import cards
        first = main.Block(1, 6, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self.game.grid[(1, 6)] = first
        self.game.grid[(7, 6)] = main.Block(7, 6, scorer=main.Scorer.NONE)
        cards.fire_first_block_cards(self.game, first)
        self.assertEqual(self.game.score_chips,
                         main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE] * 2)


    def test_end_quick_card_pays_from_the_last_contact_speed(self):
        # There is no NEXT block after the run, so an end-phase Quick card pays
        # from the speed the marble had at its last block contact.
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_speed = 400.0
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_chips, 400 * main.QUICK_SCALE)


    def test_end_quick_card_grants_nothing_without_a_block_contact(self):
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_speed = 0.0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_chips, 0)


    def test_lucky_card_keeps_its_pre_rolled_outcome_for_the_whole_run(self):
        # A Lucky card's two rolls are chosen BEFORE the run (like a Lucky
        # block's), so the patched draw below can't change the outcome.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.LUCKY)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.cash = 0
        with mock.patch("main.random.random", side_effect=[0.0, 0.9]):
            self.game._roll_run_random_outputs()
        # Two matching blocks are hit (each with a trigger to spend), so the
        # card fires twice and pays the SAME pre-rolled 130 chips both times.
        for x in (0, 2):
            pipe = main.Block(x, 0, shape=main.Shape.PIPE,
                              scorer=main.Scorer.NONE)
            self.game.grid[(x, 0)] = pipe
            self._card_fire(pipe)
        self.assertEqual(self.game.score_chips, 260)
        self.assertEqual(self.game.cash, 0)


    def test_every_named_condition_pairs_with_every_unit_scorer(self):
        # The full grid: every named condition can build a card with every unit
        # scorer, and every produced value has metadata (it could be offered
        # pre-built in the shop).
        for cond in components.NAMED_CONDITION_ORDER:
            for scorer in (main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD,
                           main.Scorer.MULT_MUL):
                value = main.condition_scorer_card(cond, scorer)
                self.assertIsNotNone(value)
                self.assertIn(value, main.Card.NAMES)
                self.assertGreater(main.Card.PRICES[value], 0)


    def test_condition_scorer_card_splits_back_into_its_pair(self):
        # (condition, scorer) maps to one card, and that card decomposes back
        # into exactly that pair (only the indivisible cards lack a split).
        for cond in components.NAMED_CONDITION_ORDER:
            for scorer in (main.Scorer.CHIPS_ADD, main.Scorer.MULT_ADD,
                           main.Scorer.MULT_MUL):
                value = main.condition_scorer_card(cond, scorer)
                if value in (main.Card.ERR_404, main.Card.BLUEPRINT,
                             main.Card.SHOWMAN):
                    continue
                self.assertEqual(components.splittable_card_condition_scorer(value),
                                 (cond, scorer))


    def test_canonical_combo_recreates_original_card_value(self):
        # Building (Joker condition, +Mult) still yields the classic Joker card.
        self.assertEqual(main.condition_scorer_card(main.Condition.START,
                                                    main.Scorer.MULT_ADD),
                         main.Card.JOKER)


    def test_wrecking_ball_chips_card_pays_proportional_chips_per_break(self):
        # Fragile Breaks at ratio 0.75: a +Chips version pays int(0.75*30 + .5)
        # = +23 chips per fragile block that breaks.
        value = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS,
                                           main.Scorer.CHIPS_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.run_active = True
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game._on_fragile_broken(block)
        self.assertEqual(self.game.score_chips, 23)


    def test_flat_collision_card_is_a_prebuilt_candidate(self):
        # Building (Pipe condition, Cash) produces a generic card that is also a
        # valid pre-built shop candidate: one family, any scorer.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                           main.Scorer.CASH)
        self.assertGreaterEqual(value, components.GENERIC_CARD_OFFSET)
        self.assertEqual(main.Card.name(value), "Pipe card (Cash)")
        self.assertEqual(components.splittable_card_condition_scorer(value),
                         (main.Condition.SHAPE_PIPE, main.Scorer.CASH))
        self.assertIn(value, main.Card.NAMES)


    def test_pipe_cash_card_earns_toward_the_run_award_on_matching_collision(self):
        # A Cash card doesn't pay out mid-run: it banks toward the run's
        # end-of-run cash award (paid only after a run).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.CASH)
        self.game.cards.append(main.CardItem(value, 40))
        cash = self.game.cash
        self.game.card_cash_run_gain = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.card_cash_run_gain, 15)
        self.assertEqual(self.game.cash, cash)  # nothing paid mid-run
        # A non-pipe block doesn't trigger the card.
        rect = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        self._card_fire(rect)
        self.assertEqual(self.game.card_cash_run_gain, 15)


    def test_start_cash_card_banks_toward_run_award_at_run_start(self):
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.CASH)
        self.game.cards.append(main.CardItem(value, 40))
        cash = self.game.cash
        self.game.card_cash_run_gain = 0
        self.game._apply_cards()
        self.assertEqual(self.game.card_cash_run_gain, 15)
        self.assertEqual(self.game.cash, cash)


    def test_sharp_card_triples_mult_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.score_mult, 3)


    def test_parts_card_grants_a_component_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.PARTS)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.toolbox.items.clear()
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        comps = [i for i in self.game.toolbox.items if getattr(i, "kind", None)
                 in (main.Component.SHAPE, main.Component.EFFECT, main.Component.SCORER)]
        self.assertEqual(len(comps), 1)


    def test_picky_card_banks_a_point_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.PICKY)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.option_run_gain = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertEqual(self.game.option_run_gain, 0.5)


    def test_voyager_card_adds_mult_per_pixel_of_total_run_distance(self):
        # A Voyager card has no single touching marble, so it measures the
        # total distance all of the run's marbles have traveled when it fires.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.VOYAGER)
        self.game.cards.append(main.CardItem(value, 40, amount=0.01))
        self.game.score_mult = 1
        m1 = self._add_marble()
        m1.distance = 1600.0
        m2 = self._add_marble()
        m2.distance = 800.0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=m1)
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.01 * 2400)


    def test_voyager_card_uses_its_own_rolled_rate(self):
        # A card's Voyager half keeps its own magnitude, so a card rolled above
        # the average rate pays more for the same travel.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.VOYAGER)
        self.game.cards.append(main.CardItem(value, 40, amount=0.018))
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.distance = 1000.0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=marble)
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.018 * 1000)


    def test_summit_card_descriptions_name_the_measured_block(self):
        # A Summit card's description explains that it measures the row of the
        # block its condition hands it.
        collision = main.condition_scorer_card(main.Condition.SHAPE_PIPE,
                                               main.Scorer.SUMMIT)
        cdesc = main.Card.description(collision).lower()
        self.assertIn("collided block", cdesc)
        self.assertIn("bottom row", cdesc)
        start = main.condition_scorer_card(main.Condition.START,
                                           main.Scorer.SUMMIT)
        sdesc = main.Card.description(start).lower()
        self.assertIn("first block", sdesc)
        self.assertIn("bottom row", sdesc)
        end = main.condition_scorer_card(main.Condition.DISTANCE,
                                         main.Scorer.SUMMIT)
        self.assertIn("last block", main.Card.description(end).lower())
        breaks = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS,
                                            main.Scorer.SUMMIT)
        self.assertIn("shattered block", main.Card.description(breaks).lower())


    def test_summit_card_collision_uses_collided_block_row(self):
        # A Summit collision card measures the row of the block the marble
        # actually hit (a card has no row of its own).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)  # top row
        self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.75 * (main.GRID_HEIGHT - 1))


    def test_summit_card_collision_bottom_row_gives_nothing(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, main.GRID_HEIGHT - 1, shape=main.Shape.PIPE,
                          scorer=main.Scorer.NONE)  # bottom row
        self._card_fire(pipe)
        self.assertEqual(self.game.score_mult, 1)


    def test_summit_start_card_waits_for_first_contact_block(self):
        # A start-phase Summit card can't measure a row at run start (no block
        # has been hit yet), so it waits until the run's first contacted block.
        import cards
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self.game._apply_cards()  # run start: no block yet, so no Summit reward
        self.assertEqual(self.game.score_mult, 1)
        first = main.Block(0, 2, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        cards.fire_first_block_cards(self.game, first)
        self.assertAlmostEqual(self.game.score_mult,
                               1 + 0.75 * ((main.GRID_HEIGHT - 1) - 2))


    def test_summit_end_card_uses_last_contact_block(self):
        # An end-phase Summit card measures the last block the marble hit
        # before finishing.
        value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.SUMMIT)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_block = main.Block(
            0, main.GRID_HEIGHT - 1 - 4, scorer=main.Scorer.NONE)  # 4 rows up
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.75 * 4)


    def test_airball_card_collision_uses_touching_marble_air(self):
        # A Pipe x Airball card pays +8 mult per second of the touching
        # marble's air streak before it hit the matching pipe.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        marble = self._add_marble()
        marble.air_streak = 1.5
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe, marble=marble)
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 1.5)


    def test_airball_card_collision_with_no_air_grants_nothing(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)  # fresh marble with no air streak
        self.assertEqual(self.game.score_mult, 1)


    def test_airball_start_card_fires_on_first_contact_with_air(self):
        # A start-condition Airball card waits for the run's first contacted
        # block and rewards that marble's air streak before the touch.
        import cards
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self.game._apply_cards()  # run start: no block yet -> no reward
        self.assertEqual(self.game.score_mult, 1)
        marble = self._add_marble()
        marble.air_streak = 2.0
        first = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        cards.fire_first_block_cards(self.game, first, marble)
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 2.0)


    def test_airball_end_card_uses_last_contact_air(self):
        # An end-condition Airball card rewards the air streak the marble had
        # before its last block contact before finishing.
        value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        self._add_marble().distance = 4000.0  # the run must have travelled
        self.game._last_contact_block = main.Block(0, 0, scorer=main.Scorer.NONE)
        self.game._last_contact_air = 2.5
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 2.5)


    def test_airball_fragile_card_uses_broken_block_touch_air(self):
        # A Fragile Breaks x Airball card rewards the air streak the marble had
        # before it first touched the fragile block that later broke.
        value = main.condition_scorer_card(main.Condition.FRAGILE_BREAKS, main.Scorer.AIRBALL)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        block.touch_air_streak = 3.0
        self.game._on_fragile_broken(block)
        self.assertAlmostEqual(self.game.score_mult, 1 + 8 * 3.0)


    def test_satanic_card_multiplies_mult_on_matching_collision(self):
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_mult = 1
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult, 6.66)


    def test_satanic_card_destroyed_on_continue(self):
        # A run destroys an owned Satanic card (a one-run deal);
        # non-Satanic cards survive.
        satanic = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        cash = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.CASH)
        self.game.cards = [main.CardItem(satanic, 40), main.CardItem(cash, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._continue_run()
        values = [card.value for card in self.game.cards]
        self.assertNotIn(satanic, values)
        self.assertIn(cash, values)


    def test_satanic_card_survives_retry(self):
        # Retrying the run discards it, so the Satanic card is kept.
        satanic = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SATANIC)
        self.game.cards = [main.CardItem(satanic, 40)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual([card.value for card in self.game.cards], [satanic])


    def test_same_card_xmult_triggers_multiply(self):
        # A single Sharp card that fires on two pipe hits multiplies twice
        # (1 -> 3 -> 9); xMult always multiplies, never adds (Game._apply_xmult).
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.SHARP)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        for _ in range(2):
            pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
            self._card_fire(pipe)
        self.assertAlmostEqual(self.game.score_mult, 9)


    def test_collision_xmult_card_compounds_per_collision(self):
        # A Slope xMult card hitting 2 slopes gives 1.25 * 1.25 = 1.5625: every
        # collision applies the card's own factor again, individually and
        # exponentially.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.assertIn("x1.25", main.Card.description(value))
        self.game.score_mult = 1

        for slopes in range(1, 4):
            self._card_fire(main.Block(slopes, 5, shape=main.Shape.SLOPE,
                                       scorer=main.Scorer.NONE))
            self.assertAlmostEqual(self.game.score_mult, 1.25 ** slopes)

        self.assertAlmostEqual(self.game.score_mult, 1.5625 * 1.25)


    def test_collision_card_fires_once_per_block_trigger(self):
        # A collision card rides on the block's triggers: a slope with a limit
        # of 3 feeds the card three times and then stops.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        slope = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE,
                           trigger_limit=3)

        for _ in range(4):
            self._card_fire(slope)

        self.assertEqual(slope.triggers_left, 0)
        self.assertAlmostEqual(self.game.score_mult, 1.25 ** 3)
        self.assertNotAlmostEqual(self.game.score_mult, 1.25 ** 4)


    def test_collision_card_needs_a_trigger_left_on_the_block(self):
        # A block that has already spent its triggers (its used-up red state)
        # no longer feeds collision cards.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        spent = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE)
        spent.triggers_left = 0

        self._card_fire(spent)

        self.assertEqual(self.game.score_mult, 1)


    def test_collision_cards_ignore_role_blocks(self):
        # Start/Finish blocks are not scoring blocks and never spend a trigger,
        # so a collision card must not fire on them at all — otherwise a
        # slope-shaped Start block would feed a Slope xMult card on every touch.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        start = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.START)
        finish = main.Block(1, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.FINISH)

        for _ in range(3):
            self._card_fire(start)
            self._card_fire(finish)

        self.assertEqual(self.game.score_mult, 1)
        self.assertEqual(start.triggers_left, 1)   # never spent
        self.assertEqual(finish.triggers_left, 1)


    def test_collision_cards_ignore_a_scorerless_portal(self):
        # A Portal with no scorer is exempt from the trigger behaviour (its
        # pass-through never spends a trigger), so it would feed a card on
        # every one of its travels in a run; collision cards refuse it. A
        # portal WITH a scorer spends its trigger as usual, so it fires once.
        value = main.condition_scorer_card(main.Condition.SHAPE_SLOPE, main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1
        free_portal = main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE,
                                 effect=main.Effect.PORTAL, portal_number=1)

        for _ in range(3):
            self._card_fire(free_portal)

        self.assertEqual(self.game.score_mult, 1)

        scoring_portal = main.Block(1, 5, shape=main.Shape.SLOPE,
                                    scorer=main.Scorer.CHIPS_ADD, scorer_amount=10,
                                    effect=main.Effect.PORTAL, portal_number=2)
        self._card_fire(scoring_portal)
        self.assertAlmostEqual(self.game.score_mult, 1.25)
        self._card_fire(scoring_portal)   # its trigger is spent now
        self.assertAlmostEqual(self.game.score_mult, 1.25)


    def test_end_flat_card_fires_at_run_end(self):
        # A Distance x Cash card banks toward the run award once the run ends;
        # a Distance x Fresh card grants a free reroll. The run has to have
        # travelled, or the Distance condition never happened.
        cash_value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.CASH)
        fresh_value = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(cash_value, 40))
        self.game.cards.append(main.CardItem(fresh_value, 40))
        self._add_marble().distance = 4000.0
        cash = self.game.cash
        self.game.card_cash_run_gain = 0
        self.game.free_rerolls = 0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.card_cash_run_gain, 15)
        self.assertEqual(self.game.cash, cash)  # not paid until the run award
        self.assertEqual(self.game.free_rerolls, 1)


    # --- Flat cards honour their condition's gate -------------------------

    def test_flat_start_card_respects_its_conditions_gate(self):
        # A flat card fires one block-style trigger, but only when its condition
        # actually happened: a Ripped Card (Parts) pays nothing on a board with
        # more than 5 blocks, and pays again once the board is small enough.
        value = main.condition_scorer_card(main.Condition.FEW_BLOCKS,
                                           main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        for x in range(6):  # 6 blocks: the Ripped Card condition fails
            self.game.grid[(x, 0)] = main.Block(x, 0, scorer=main.Scorer.NONE)
        self.game.free_rerolls = 0
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 0)

        # Shrink the board to 5 blocks: the condition holds and the card pays.
        self.game.grid.pop((5, 0))
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 1)


    def test_flat_start_card_respects_the_cozy_board_gate(self):
        # Cozy holds while the board has 10 or fewer unlocked units.
        value = main.condition_scorer_card(main.Condition.COZY, main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.free_rerolls = 0
        self.game.unlocked_cells = {(x, y) for x in range(11) for y in range(1)}
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 0)  # 11 units: Cozy is broken

        self.game.unlocked_cells = {(x, y) for x in range(10) for y in range(1)}
        self.game._apply_cards()
        self.assertEqual(self.game.free_rerolls, 1)  # 10 units: Cozy holds


    def test_flat_end_card_does_not_fire_when_the_run_measured_nothing(self):
        # A run that never travelled has not satisfied the Distance condition,
        # so its flat card pays nothing (the magnitude version scales to zero).
        value = main.condition_scorer_card(main.Condition.DISTANCE,
                                           main.Scorer.FRESH)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.free_rerolls = 0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.free_rerolls, 0)

        self._add_marble().distance = 4000.0
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.free_rerolls, 1)


    def test_flat_start_block_payoff_card_respects_the_gate(self):
        # A block-relative start card waits for the run's first block, and is
        # still refused when its condition's gate is not met: a Ripped Card
        # (Powerline) pays nothing on a crowded board, and pays once the board
        # is small enough.
        import cards
        value = main.condition_scorer_card(main.Condition.FEW_BLOCKS,
                                           main.Scorer.POWERLINE)
        self.game.cards.append(main.CardItem(value, 40))
        row = 3
        for x in range(3):
            self.game.grid[(x, row)] = main.Block(x, row, scorer=main.Scorer.NONE)
        first = self.game.grid[(0, row)]
        for x in range(3, 6):  # 6 blocks total: the condition fails
            self.game.grid[(x, row)] = main.Block(x, row, scorer=main.Scorer.NONE)
        self.game.score_chips = 0
        cards.fire_first_block_cards(self.game, first)
        self.assertEqual(self.game.score_chips, 0)

        self.game.grid.pop((5, row))  # 5 blocks: the card fires
        cards.fire_first_block_cards(self.game, first)
        self.assertEqual(self.game.score_chips,
                         main.Scorer.DEFAULT_AMOUNT[main.Scorer.POWERLINE] * 5)


    def test_cash_card_reward_folds_into_run_award_and_retry_discards(self):
        # Cash earned by Cash cards is added at _award_cash (part of the run's
        # end award), so retrying the run undoes it — it only sticks after a run.
        self.game.score_total = 10000
        self.game.required_score = 1
        self.game.card_cash_run_gain = 9
        cash0 = self.game.cash
        self.game._award_cash()
        self.assertEqual(self.game.card_cash_run_gain, 0)
        self.assertGreaterEqual(self.game.last_run_cash_gained, 9)
        self.assertGreater(self.game.cash, cash0)
        # Retrying the run rolls the whole award (including the card cash) back.
        # Only a real retry does: the run has to be finished and waiting for
        # the player's RETRY/CONTINUE choice.
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.game._retry_run()
        self.assertEqual(self.game.cash, cash0)


    def test_quick_card_pays_the_speed_of_the_next_block_hit(self):
        # A Pipe x Quick card arms when the pipe is hit; the marble's NEXT
        # fresh block contact pays chips from that block's impact speed.
        value = main.condition_scorer_card(main.Condition.SHAPE_PIPE, main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        pipe = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = self._card_fire(pipe)
        # Arming only, no payout yet.
        self.assertIn(self.game.cards[0], self.game.armed_quick)
        self.assertEqual(self.game.score_chips, 0)
        # Hitting the next block (a rect) resolves using its impact speed.
        marble.recent_speed = 240.0
        rect = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        self._card_fire(rect, marble)
        self.assertEqual(self.game.armed_quick, set())
        self.assertEqual(self.game.score_chips, int(240.0 * main.QUICK_SCALE))


    def test_quick_card_resolves_an_armed_start_quick_on_first_hit(self):
        # A Start x Quick card arms at run start and pays on the first block hit.
        value = main.condition_scorer_card(main.Condition.START, main.Scorer.QUICK)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.armed_quick = set()
        self.game._apply_cards()
        self.assertIn(self.game.cards[0], self.game.armed_quick)
        marble = self._add_marble()
        marble.recent_speed = 200.0
        rect = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        self._card_fire(rect, marble)
        self.assertEqual(self.game.score_chips, int(200.0 * main.QUICK_SCALE))


    def test_shape_and_effect_cards_exist_for_every_shape_and_effect(self):
        # Every shape and effect collision condition has a magnitude card for
        # each unit scorer (+Chips / +Mult / xMult), decomposing back into the
        # exact (condition, scorer) pair it was built from.
        for scorer, suffix in ((main.Scorer.CHIPS_ADD, "+Chips"),
                               (main.Scorer.MULT_ADD, "+Mult"),
                               (main.Scorer.MULT_MUL, "xMult")):
            for shape in main.Shape.ORDER:
                value = _shape_card_value(shape, scorer)
                self.assertEqual(main.Card.name(value),
                                 f"{main.Shape.name(shape)} {suffix}")
                self.assertIn(main.Shape.name(shape), main.Card.description(value))
                self.assertEqual(
                    components.splittable_card_condition_scorer(value),
                    (main.Condition.SHAPE_BASE + main.Shape.ORDER.index(shape),
                     scorer))
            for effect in main.Effect.ORDER:
                value = _effect_card_value(effect, scorer)
                self.assertEqual(main.Card.name(value),
                                 f"{main.Effect.name(effect)} {suffix}")
                self.assertEqual(
                    components.splittable_card_condition_scorer(value),
                    (main.Condition.EFFECT_BASE + main.Effect.ORDER.index(effect),
                     scorer))


    def test_shape_card_grants_mult_on_matching_collision(self):
        # A "Pipe card" grants +4 mult when the marble collides with a pipe.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 4)


    def test_effect_card_grants_mult_on_matching_collision(self):
        # A "Bouncy card" grants +4 mult when the marble collides with a
        # bouncy block (the effect can be one of several on the block).
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_MULT), 30))
        block = main.Block(1, 1, shape=main.Shape.RECT, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 4)


    def test_chips_card_grants_30_chips_on_matching_collision(self):
        # The +chips version of the Pipe card grants +30 chips per collision.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_CHIPS), 12))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_chips
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_chips, before + 30)
        self.assertEqual(self.game.score_mult, 1)  # no mult change


    def test_xmult_card_multiplies_mult_on_matching_collision(self):
        # The xMult version of the Bouncy card multiplies mult by 1.25.
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_XMULT), 40))
        block = main.Block(1, 1, shape=main.Shape.RECT, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        self.game.score_mult = 4
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, 5)


    def test_shape_card_ignores_non_matching_shape(self):
        # A Pipe card does nothing when the marble hits a non-pipe block.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before)


    def test_none_effect_card_fires_on_plain_block(self):
        # A "None card" (effect) grants +4 mult when hitting a block with no
        # effect.
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.NONE, components.Card.SCORE_MULT), 7))
        block = main.Block(1, 1, shape=main.Shape.RECT, effects=[main.Effect.NONE],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 4)


    def test_collision_card_fires_once_per_collision_not_every_frame(self):
        # A block already in contact (present in last tick too) is not a fresh
        # collision, so the card does not stack +4 every frame.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        marble.collisions_last_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before)


    def test_multiple_matching_cards_stack_on_one_collision(self):
        # A bouncy pipe block triggers both the Pipe card and the Bouncy card.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        self.game.cards.append(main.CardItem(
            _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_MULT), 30))
        block = main.Block(1, 1, shape=main.Shape.PIPE, effects=[main.Effect.BOUNCY],
                           scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 8)


    def test_blueprint_copies_a_shape_card(self):
        # A Blueprint to the right of a Pipe card copies it: colliding with a
        # pipe block triggers both the card and its Blueprint.
        self.game.cards.append(main.CardItem(
            _shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT), 18))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 70))
        block = main.Block(1, 1, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [block]
        self.game.marbles.append(marble)
        self.game.run_active = True
        before = self.game.score_mult
        self.game._handle_block_contacts([block])
        self.assertEqual(self.game.score_mult, before + 8)


    def test_card_area_caps_at_five(self):
        self.game.cash = 100000
        # Own Showman so duplicate Jokers can be bought; the card area still
        # caps at MAX_CARDS.
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 100))
        for _ in range(main.MAX_CARDS + 2):
            self.game._buy_shop_item(main.CardItem(main.Card.JOKER, 20))
        self.assertEqual(len(self.game.cards), main.MAX_CARDS)  # Showman + 4 Jokers
        self.assertTrue(self.game.shop_message)


    def test_a_granted_card_is_not_one_the_player_already_owns(self):
        # The Ideas conversion's random card follows the same rule as the shop:
        # a second copy is the Showman card's perk, so the grant skips the cards
        # the player already has.
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        with mock.patch("main.prebuilt_card_pool",
                        return_value=[main.Card.GARDEN, main.Card.COUPON]):
            self.assertTrue(self.game._grant_random_card())
        self.assertEqual(self.game.cards[-1].value, main.Card.COUPON)


    def test_recognition_action_v2_duplicates_card_for_its_cost(self):
        card = main.CardItem(main.Card.JOKER, 24)
        self.game.cards.append(card)
        action = main.ActionItem(main.Action.RECOGNITION, 60, version=2)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = card
        self.assertTrue(self.game._apply_action())
        self.assertEqual(len(self.game.cards), 2)  # original + copy
        self.assertEqual(self.game.cash, 100 - 24)


    def test_joker_gives_plus_four_mult_at_run_start(self):
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.assertTrue(self.game.reset_run())
        self.assertEqual(self.game.score_mult, 5)  # 1 + 4
        self.assertEqual(self.game.score_chips, 1)


    def test_joker_mult_applies_every_run(self):
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 5)


    def test_banker_card_gives_chip_per_ten_dollars(self):
        self.game.cards.append(main.CardItem(main.Card.BANKER, 25))
        self.game.score_chips = 1
        self.game.cash = 555
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1 + 555 // 10)


    def test_pillar_card_gives_mult_for_fullest_column(self):
        # Column 3 holds the most blocks (3), so Pillar adds +3 mult.
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(1, 0)] = main.Block(1, 0)
        self.game.grid[(1, 1)] = main.Block(1, 1)
        self.game.grid[(2, 0)] = main.Block(2, 0)
        self.game.grid[(3, 0)] = main.Block(3, 0)
        self.game.grid[(3, 1)] = main.Block(3, 1)
        self.game.grid[(3, 2)] = main.Block(3, 2)
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 1 + 3)


    def test_pillar_card_with_empty_board_adds_no_mult(self):
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_mult, 1)


    def test_wrecking_ball_card_gives_accumulated_mult_at_run_start(self):
        # The wrecking ball's +mult is permanent: whatever bonus has built up
        # from fragile breaks applies at the start of every run.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        self.game.wrecking_bonus[main.Scorer.MULT_ADD] = 6
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1 + 6)


    def test_wrecking_ball_run_gain_discarded_when_retrying(self):
        # Retrying a run discards the gains the wrecking ball earned during it.
        self.game.cards.append(main.CardItem(main.Card.WRECKING_BALL, 30))
        block = main.Block(0, 0, effect=main.Effect.FRAGILE)
        self.game.run_active = True
        self.game._on_fragile_broken(block)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 3)
        self._complete_run(10000, required=100)
        self.game._retry_run()
        self.assertEqual(self.game.wrecking_bonus[main.Scorer.MULT_ADD], 0)
        self.assertEqual(self.game.wrecking_run_gain[main.Scorer.MULT_ADD], 0)


    def test_glitch_card_gives_random_mult_between_zero_and_six_times_base(self):
        # Glitch pays a random 0..6 units, so the +4 mult base gives at most
        # +24 mult (6x base).
        self.game.cards.append(main.CardItem(main.Card.GLITCH, 20))
        self.game.score_mult = 1
        self.game._apply_cards()
        gained = self.game.score_mult - 1
        self.assertGreaterEqual(gained, 0)
        self.assertLessEqual(gained, 24)
        self.assertEqual(len(self.game.score_particles), 1)


    def test_ripped_card_gives_120_chips_when_fewer_than_five_blocks(self):
        self.game.cards.append(main.CardItem(main.Card.RIPPED_CARD, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(0, 1)] = main.Block(0, 1)
        self.game.score_chips = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1 + 120)
        self.assertEqual(len(self.game.score_particles), 1)


    def test_ripped_card_gives_nothing_with_more_than_five_blocks(self):
        # Ripped card grants 120 chips only with 5 blocks or fewer; with 6 it
        # grants nothing and spawns no particle.
        self.game.cards.append(main.CardItem(main.Card.RIPPED_CARD, 20))
        for i in range(6):
            self.game.grid[(i, 0)] = main.Block(i, 0)
        self.game.score_chips = 1
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1)
        self.assertEqual(len(self.game.score_particles), 0)


    def test_plane_card_gives_chips_for_air_time_at_finish(self):
        # Plane gives +15 chips for each second the marble was in the air. The
        # 2.5s of air time pays a fractional 37.5 chips, kept as-is (only the
        # UI rounds to a tenth).
        self.game.cards.append(main.CardItem(main.Card.PLANE, 25))
        self.game.air_time = 2.5
        self.game.score_chips = 1
        self.game._apply_cards_on_finish()
        self.assertEqual(self.game.score_chips, 1 + 15 * 2.5)


    def test_err_404_card_grants_random_card_when_bought(self):
        # Buying the ERR 404 card grants a random (different) card instead of
        # joining the card area itself. The grant draws from the pre-built pool,
        # so a splittable grid card can carry any scorer.
        self.game.cards.clear()
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.ERR_404, 10))
        self.assertEqual(len(self.game.cards), 1)
        self.assertNotEqual(self.game.cards[0].value, main.Card.ERR_404)
        self.assertIn(self.game.cards[0].value, main.Card.NAMES)
        self.assertEqual(self.game.cash, 1000 - 10)


    def test_blueprint_copies_left_card_at_run_start(self):
        # A Blueprint next to a Joker behaves like a second Joker.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))      # left
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))  # copies it
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1 + 4 + 4)


    def test_blueprint_with_no_left_card_does_nothing(self):
        # A Blueprint in the leftmost slot has no card to copy.
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1)


    def test_blueprint_copies_finish_card(self):
        # A Blueprint next to an Explorer copies its end-of-run xMult.
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        marble = self._add_marble()
        marble.distance = 3000.0
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        fraction = (3000 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT)
        factor = 1 + fraction
        self.assertAlmostEqual(self.game.score_mult, factor * factor)  # Explorer + copy


    def test_blueprint_does_not_chain_another_blueprint(self):
        # Two Blueprints can't copy each other: each has a Blueprint (or
        # nothing) to its left, so neither does anything.
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        self.assertEqual(self.game.score_mult, 1)


    def test_skater_card_gives_xmult_based_on_slippery_blocks_at_finish(self):
        # Skater gives (1 + 0.2 * slippery blocks owned) xMult at the END of
        # the run: xMult cards apply late, +mult cards apply at the start.
        self.game.cards.append(main.CardItem(main.Card.SKATER, 30))
        self.game.toolbox.items.clear()
        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                             main.Scorer.CHIPS_ADD, 10, 20, "S1",
                                             effects=[main.Effect.SLIPPERY]))
        self.game.grid[(0, 0)] = main.Block(0, 0, effects=[main.Effect.SLIPPERY])
        self.game.grid[(0, 1)] = main.Block(0, 1)
        self.game.score_mult = 1
        # At the start it is a no-op (xMult waits for the end of the run)...
        self.game._apply_cards()
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        # ...and at the end it applies the xMult.
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 0.2 * 2)


    def test_skater_card_with_no_slippery_blocks_is_neutral(self):
        # With no slippery blocks, Skater's xMult is exactly 1 (no effect).
        self.game.cards.append(main.CardItem(main.Card.SKATER, 30))
        self.game.score_mult = 1
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1.0)
        self.assertEqual(len(self.game.score_particles), 0)


    def test_astronaut_card_gives_mult_for_black_hole_time(self):
        self.game.cards.append(main.CardItem(main.Card.ASTRONAUT, 30))
        self.game.score_mult = 1
        self.game.black_hole_time = 2.5
        self.game._apply_cards_on_finish()
        self.assertAlmostEqual(self.game.score_mult, 1 + 4 * 2.5)


    def test_card_cutter_trial_disables_random_card(self):
        # With a single owned card, Card cutter always disables it, so its
        # score effect is skipped for the run.
        joker = main.CardItem(main.Card.JOKER, 20)
        self.game.cards.append(joker)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game._apply_trial()
        self.assertIs(self.game.disabled_card, joker)

        self.game.reset_run(False)
        self.assertEqual(self.game.score_mult, 1)  # Joker disabled: no +4
        self.assertEqual(self.game.score_chips, 1)


    def test_card_cutter_switches_off_passive_whole_card_effects(self):
        # A whole card has no start-of-run score effect: it works through a
        # passive rule read with _has_card. Card cutter has to switch those off
        # too (it used to only stop the composed condition+scorer cards).
        cases = (
            (main.Card.MINESHAFT, lambda: self.game._board_unit_price(),
             main.MINESHAFT_BOARD_UNIT_PRICE, main.BOARD_UNIT_PRICE),
            (main.Card.COUPON, lambda: self.game._shop_discount(100),
             int(100 * main.COUPON_PRICE_FACTOR), 100),
            (main.Card.MARKET, lambda: self.game._sell_fraction(),
             main.MARKET_SELL_FRACTION, 0.5),
            (main.Card.FACTORY, lambda: self.game._resource_cost(), 0.5, 1),
        )
        for value, read, with_card, without_card in cases:
            with self.subTest(card=main.Card.name(value)):
                self.game.cards = [main.CardItem(value, 30)]
                self.assertEqual(read(), with_card)
                # With a single owned card, Card cutter always cuts that one.
                self.game.current_trial = main.Trial.CARD_CUTTER
                self.game._apply_trial()
                self.assertTrue(self.game._card_disabled(self.game.cards[0]))
                self.assertTrue(main.cards._card_disabled(self.game,
                                                         self.game.cards[0]))
                self.assertEqual(read(), without_card)
                # The card is still OWNED, so the duplicate rules and the build
                # phase are untouched: only its effect is off.
                self.assertTrue(self.game._owns_card(value))
                self.assertFalse(self.game._has_card(value))


    def test_card_cutter_covers_every_passive_whole_card(self):
        # Every passive whole card is read through _has_card, so cutting it
        # silences it — and cutting one card never silences another.
        passive = [main.Card.SHOWMAN, main.Card.GARDEN, main.Card.RIGGED_CASINO,
                   main.Card.CONQUISTADOR, main.Card.COMPOUND_INTEREST,
                   main.Card.INFERNO, main.Card.WATCH, main.Card.PEDESTAL,
                   main.Card.DOPPELGANGER, main.Card.TESSERACT,
                   main.Card.THOUSAND_HANDED, main.Card.PROCRASTINATION,
                   main.Card.ESSENCE, main.Card.CONCERT]
        for value in passive:
            with self.subTest(card=main.Card.name(value)):
                self.game.cards = [main.CardItem(value, 30),
                                   main.CardItem(main.Card.JOKER, 20)]
                self.assertTrue(self.game._has_card(value))
                self.game.disabled_card = self.game.cards[0]
                self.assertFalse(self.game._has_card(value))
                self.assertTrue(self.game._has_card(main.Card.JOKER))
                self.assertTrue(self.game._owns_card(value))
                # The disable is a run-time state: clearing it revives the card.
                self.game.disabled_card = None
                self.assertTrue(self.game._has_card(value))


    def test_a_cut_card_stops_feeding_its_own_effects(self):
        # The trial can be rolled while the player is still building (buying a
        # trial change applies it immediately), so a cut Tesseract must stop
        # growing its reroll bonus in the shop too.
        self.game.cash = 1000
        self.game.cards = [main.CardItem(main.Card.TESSERACT, 44)]
        self.game._refresh_shop()
        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + main.TESSERACT_REROLL_XMULT)
        self.game.disabled_card = self.game.cards[0]
        self.game._refresh_shop()
        self.assertAlmostEqual(self.game.tesseract_bonus,
                               1.0 + main.TESSERACT_REROLL_XMULT)
        self.assertNotIn("Tesseract", self.game.shop_message)


    def test_a_cut_card_still_cannot_be_bought_again(self):
        # A disabled card is still owned, so the duplicate rule keeps biting: a
        # Card cutter run can't be used to buy a second copy of the cut card.
        self.game.cards = [main.CardItem(main.Card.COUPON, 46)]
        self.game.disabled_card = self.game.cards[0]
        self.game.cash = 1000
        self.game._buy_shop_item(main.CardItem(main.Card.COUPON, 46))
        self.assertEqual(len(self.game.cards), 1)  # no duplicate added
        self.assertEqual(self.game.cash, 1000)     # not charged
        self.assertEqual(self.game.shop_message, "Already own this card")
        # Showman's own effect is what lifts the rule, so a cut Showman can't
        # lift it either.
        showman = main.CardItem(main.Card.SHOWMAN, 100)
        self.game.cards.append(showman)
        self.game.disabled_card = showman
        self.game._buy_shop_item(main.CardItem(main.Card.COUPON, 46))
        self.assertEqual(len(self.game.cards), 2)   # still no duplicate
        self.game.disabled_card = None
        self.game._buy_shop_item(main.CardItem(main.Card.COUPON, 46))
        self.assertEqual(len(self.game.cards), 3)   # Showman lifts it again


    def test_shuffled_trial_reorders_cards(self):
        # Shuffled flips and shuffles the player's cards when the run starts.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.cards.append(main.CardItem(main.Card.BLUEPRINT, 35))
        before = [c.value for c in self.game.cards]
        self.game.current_trial = main.Trial.SHUFFLED
        # With shuffle stubbed out, the flip (reverse) is deterministic.
        with mock.patch("main.random.shuffle"):
            self.game._apply_trial()
        after = [c.value for c in self.game.cards]
        self.assertEqual(after, list(reversed(before)))


    def test_deal_breaker_disables_all_cards_of_one_condition(self):
        # Deal breaker picks a condition the player owns and disables every
        # card whose condition matches it.
        start_chips = main.condition_scorer_card(main.Condition.START, main.Scorer.CHIPS_ADD)
        start_mult = main.condition_scorer_card(main.Condition.START, main.Scorer.MULT_ADD)
        dist_mult = main.condition_scorer_card(main.Condition.DISTANCE, main.Scorer.MULT_MUL)
        c_start1 = main.CardItem(start_chips, 20)
        c_start2 = main.CardItem(start_mult, 20)
        c_dist = main.CardItem(dist_mult, 25)
        self.game.cards = [c_start1, c_start2, c_dist]
        self.game.current_trial = main.Trial.DEAL_BREAKER
        # Force the chosen condition to be START (present in the owned cards).
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: main.Condition.START
                        if main.Condition.START in seq else seq[0]):
            self.game._apply_trial()
        self.assertIn(c_start1, self.game.deal_broken_cards)
        self.assertIn(c_start2, self.game.deal_broken_cards)
        self.assertNotIn(c_dist, self.game.deal_broken_cards)
        # The disabled cards are skipped when the run applies its cards.
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game._apply_cards()
        self.assertEqual(self.game.score_chips, 1)  # START+chips disabled
        self.assertEqual(self.game.score_mult, 1)   # START+mult disabled


    def test_tesseract_only_grows_while_the_card_is_owned(self):
        self.game.cash = 1000
        self.game._refresh_shop()  # no Tesseract

        self.assertEqual(self.game.tesseract_bonus, 1.0)
        self.assertNotIn("Tesseract", self.game.shop_message)


    def test_tesseract_bonus_applies_at_the_start_of_a_run(self):
        self.game.cards.append(main.CardItem(main.Card.TESSERACT, 44))
        self.game.tesseract_bonus = 1.5
        self.game.score_mult = 2.0

        self.game._apply_cards()

        self.assertAlmostEqual(self.game.score_mult, 3.0)


    def test_tesseract_bonus_does_nothing_without_the_card(self):
        self.game.tesseract_bonus = 1.5
        self.game.score_mult = 2.0

        self.game._apply_cards()

        self.assertEqual(self.game.score_mult, 2.0)


    # --- Synthesizer: a start-of-run payoff scaled by your cards ----------

    def test_synthesizer_metadata_and_units(self):
        self.assertEqual(main.Condition.name(main.Condition.SYNTHESIZER),
                         "Synthesizer")
        self.assertEqual(main.condition_phase(main.Condition.SYNTHESIZER), "start")
        self.assertAlmostEqual(components.condition_ratio(main.Condition.SYNTHESIZER), 0.75)
        self.assertEqual(main.CONDITION_ORDER.count(main.Condition.SYNTHESIZER), 1)
        self.assertIn("for each card in your card area",
                      main.condition_description(main.Condition.SYNTHESIZER))
        self.assertEqual(main.cards._condition_units(
            self.game, main.Condition.SYNTHESIZER), 0)

        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 48))
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        self.assertEqual(main.cards._condition_units(
            self.game, main.Condition.SYNTHESIZER), 2)


    def test_synthesizer_card_pays_three_mult_per_card_owned(self):
        # Two other cards plus the Synthesizer card itself = 3 cards, and the
        # condition's 3/4 ratio makes the +Mult payoff exactly +3 mult a card.
        self.game.cards.append(main.CardItem(main.Card.SHOWMAN, 48))
        self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        value = main.condition_scorer_card(main.Condition.SYNTHESIZER,
                                           main.Scorer.MULT_ADD)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.score_chips = 0
        self.game.score_mult = 1

        self.game._apply_cards()

        self.assertEqual(self.game.score_mult, 1 + 9)


    # --- 1000-handed: a random action after every run --------------------

    def test_thousand_handed_grants_a_random_action_after_every_run(self):
        self.game.cards.append(main.CardItem(main.Card.THOUSAND_HANDED, 42))
        self.game.actions.clear()
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(len(self.game.actions), 1)
        self.assertIn(self.game.actions[0].value, main.Action.ORDER)
        self.assertIn("1000-handed", self.game.shop_message)


    def test_thousand_handed_withholds_the_action_when_the_area_is_full(self):
        self.game.cards.append(main.CardItem(main.Card.THOUSAND_HANDED, 42))
        self.game.actions = [main.ActionItem(main.Action.DEATH, 48),
                             main.ActionItem(main.Action.RECOGNITION, 48)]
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(len(self.game.actions), main.MAX_ACTIONS)


    def test_anointment_refuses_role_blocks_and_cards(self):
        action = main.ActionItem(main.Action.ANOINTMENT, 32)
        start = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = start

        self.assertFalse(self.game._action_anointment(action, start))
        self.assertFalse(self.game._action_anointment(
            action, main.CardItem(main.Card.GARDEN, 36)))
        self.assertEqual(start.effects, [main.Effect.NONE])


    def test_a_token_fires_even_with_the_watch_card(self):
        # Watch limits which TOUCHED blocks score; a token is a start-of-run
        # payoff like a card, so it is never gated.
        ghost = main.Block(3, 4, scorer=main.Scorer.MULT_ADD, scorer_amount=4)
        ghost.is_token = True
        self.game.cards.append(main.CardItem(main.Card.WATCH, 40))

        self.assertFalse(self.game._watch_blocks_out_of_play(ghost))
        self.assertTrue(self.game._watch_blocks_out_of_play(
            main.Block(5, 5, scorer=main.Scorer.MULT_ADD, scorer_amount=4)))
