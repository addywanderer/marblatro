"""The one-shot actions (Death, Recognition, Deja Vu, ...).

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class ActionsTests(GameTestCase):
    """The one-shot actions (Death, Recognition, Deja Vu, ...)."""


    def test_a_trigger_banks_a_decimal_fraction_of_a_point(self):
        # A trigger banks a fraction of a point and one point always converts:
        # a third for Shreds, a half for the rest, scaled by the scorer's
        # magnitude. The count reads as a decimal, because a rolled magnitude
        # lands off any small fraction's grid — a Rubble trigger's 0.7 points
        # would read "2/3", and a Shreds 1.1/3 would read "1 1/6".
        self.assertEqual(main.points_text(0.5), "0.5")
        self.assertEqual(main.points_text(0.7), "0.7")
        self.assertEqual(main.points_text(1.5), "1.5")
        self.assertEqual(main.points_text(1 / 3), "0.333")
        self.assertEqual(main.points_text(2), "2")
        self.assertEqual(self.game._resource_cost(), 1)
        for scorer, rate in ((main.Scorer.SHREDS, 1 / 3),
                             (main.Scorer.RUBBLE, 0.5),
                             (main.Scorer.IDEAS, 0.5),
                             (main.Scorer.PICKY, 0.5)):
            with self.subTest(scorer=main.Scorer.name(scorer)):
                self.assertAlmostEqual(components.resource_points_for(scorer, 1),
                                       rate)
                # ...and a 3-magnitude scorer banks three times that.
                self.assertAlmostEqual(components.resource_points_for(scorer, 3),
                                       rate * 3)
        # Parts and Fresh are not point scorers: Parts banks whole components
        # (see parts_run_gain) and Fresh grants its reroll right away.
        self.assertEqual(components.resource_points_for(main.Scorer.PARTS, 3), 0)
        self.assertEqual(components.resource_points_for(main.Scorer.FRESH, 3), 0)


    def test_a_trigger_banks_the_fraction_the_description_states(self):
        # The description and the bank agree: a 1-magnitude Rubble block says
        # "0.5 rubble point (0)" and banks exactly that.
        block = main.Block(0, 0, scorer=main.Scorer.RUBBLE)
        self.assertIn("0.5 rubble point (0)",
                      main.scorer_description(block.scorer, block.scorer_amount))
        self.game.run_active = True
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])
        self.assertAlmostEqual(self.game.rubble_run_gain, 0.5)


    def test_action_data_lives_in_components(self):
        # Every action has a name, price, glyph, colors, and v1/v2 text.
        self.assertEqual(main.Action.name(main.Action.DEATH), "Death")
        self.assertEqual(main.Action.name(main.Action.RECOGNITION), "Recognition")
        self.assertEqual(main.Action.name(main.Action.DEJA_VU), "Deja Vu")
        self.assertEqual(main.Action.name(main.Action.ANOINTMENT), "Anointment")
        self.assertEqual(main.Action.name(main.Action.STRENGTH), "Strength")
        self.assertEqual(main.Action.name(main.Action.SPIRIT), "Spirit")
        self.assertEqual(main.Action.name(main.Action.CLEANSWEEP), "Cleansweep")
        self.assertEqual(main.Action.name(main.Action.EXPANSION), "Expansion")
        self.assertEqual(main.Action.name(main.Action.BRAINSTORM), "Brainstorm")
        self.assertEqual(main.Action.name(main.Action.MASS_PRODUCTION),
                         "Mass production")
        self.assertEqual(main.Action.name(main.Action.GRACE), "Grace")
        self.assertEqual(main.Action.name(main.Action.INACTION), "Inaction")
        self.assertEqual(main.Action.name(main.Action.FORESIGHT), "Foresight")
        self.assertEqual(main.Action.PRICES[main.Action.DEATH], 24)
        self.assertEqual(main.Action.PRICES[main.Action.RECOGNITION], 24)
        self.assertEqual(main.Action.PRICES[main.Action.DEJA_VU], 28)
        self.assertEqual(main.Action.PRICES[main.Action.EXPANSION], 25)
        self.assertEqual(main.Action.PRICES[main.Action.BRAINSTORM], 25)
        self.assertEqual(main.Action.PRICES[main.Action.GRACE], 25)
        # Inaction is priced like the cheap actions and Foresight is the
        # dearest in the catalogue: it widens the action area itself.
        self.assertEqual(main.Action.PRICES[main.Action.INACTION], 24)
        self.assertEqual(main.Action.PRICES[main.Action.FORESIGHT], 90)
        self.assertGreater(main.Action.PRICES[main.Action.FORESIGHT],
                           max(main.Action.PRICES[value]
                               for value in main.Action.ORDER
                               if value != main.Action.FORESIGHT))
        for value in main.Action.ORDER:
            self.assertGreater(main.Action.PRICES[value], 0)
            self.assertIn(value, main.Action.GLYPHS)
            self.assertIn(value, main.Action.COLORS)
            self.assertTrue(main.Action.description(value, 1))
            self.assertTrue(main.Action.description(value, 2))
        self.assertEqual(main.Action.ORDER,
                         [main.Action.DEATH, main.Action.RECOGNITION,
                          main.Action.DEJA_VU, main.Action.ANOINTMENT,
                          main.Action.STRENGTH, main.Action.SPIRIT,
                          main.Action.CLEANSWEEP, main.Action.EXPANSION,
                          main.Action.BRAINSTORM, main.Action.MASS_PRODUCTION,
                          main.Action.GRACE, main.Action.INACTION,
                          main.Action.FORESIGHT])
        # Deja Vu's two versions add triggers: +1, then +100.
        self.assertIn("+1 trigger", main.Action.description(main.Action.DEJA_VU, 1))
        self.assertIn("+100 triggers", main.Action.description(main.Action.DEJA_VU, 2))

    def test_the_later_actions_description_their_versions(self):
        # Each of the four later actions says what v1 does and what the upgrade
        # buys, in the shop's and collection's own words.
        self.assertIn("4 locked board squares",
                      main.Action.description(main.Action.EXPANSION, 1))
        self.assertIn("every locked board square",
                      main.Action.description(main.Action.EXPANSION, 2))
        self.assertIn("2 free shop rerolls",
                      main.Action.description(main.Action.BRAINSTORM, 1))
        self.assertIn("Halves the price of every shop reroll",
                      main.Action.description(main.Action.BRAINSTORM, 2))
        self.assertIn("Triples the resource points",
                      main.Action.description(main.Action.MASS_PRODUCTION, 1))
        self.assertIn("Doubles every resource point",
                      main.Action.description(main.Action.MASS_PRODUCTION, 2))
        self.assertIn("+1 xMult",
                      main.Action.description(main.Action.GRACE, 1))
        self.assertIn("required score",
                      main.Action.description(main.Action.GRACE, 2))


    def test_a_new_action_is_rolled_for_the_free_v2(self):
        # random_action_version is the single roll behind every new action.
        self.assertEqual(main.ACTION_V2_CHANCE, 0.01)
        random.seed(4242)
        rolls = [main.random_action_version() for _ in range(20000)]
        self.assertIn(1, rolls)
        self.assertIn(2, rolls)
        share = rolls.count(2) / len(rolls)
        self.assertAlmostEqual(share, main.ACTION_V2_CHANCE, delta=0.004)


    def test_an_upgraded_action_is_gold_framed_and_gold_tagged(self):
        # An upgraded action has to be recognisable at a glance on a full shelf:
        # a v2 is drawn with a gold frame and a solid gold tag in its corner,
        # while a v1 keeps the plain white frame and its small "v1" label.
        gold = (255, 215, 0)
        rect = pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)
        canvas = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA)
        tag = main.ui.action_version_tag_rect(rect)

        def draw(version):
            canvas.fill((0, 0, 0, 0))
            main.ui.draw_action(canvas, main.ActionItem(main.Action.DEATH, 24,
                                                        version=version), rect)
            return (canvas.get_at((rect.left, rect.centery))[:3],
                    canvas.get_at((tag.left + 2, tag.centery))[:3])

        v1_frame, v1_tag = draw(1)
        self.assertEqual(v1_frame, main.WHITE)
        self.assertNotEqual(v1_tag, gold)  # a small label, not a plate

        v2_frame, v2_tag = draw(2)
        self.assertEqual(v2_tag, gold)     # the plate is solid gold
        self.assertNotEqual(v2_frame, main.WHITE)
        # The frame pulses so it catches the eye, but only between two golds.
        frames = set()
        for ticks in (0, 130, 260, 390, 520):
            with mock.patch("main.pygame.time.get_ticks", return_value=ticks):
                frames.add(draw(2)[0])
        self.assertGreater(len(frames), 1)
        for frame in frames:
            self.assertEqual(frame[0], 255)
            self.assertLess(frame[2], 200)  # never pulses all the way to white


    def test_action_area_caps_at_two(self):
        self.game.cash = 10000
        for _ in range(3):
            self.game._buy_shop_item(main.ActionItem(main.Action.DEATH, 60))
        self.assertEqual(len(self.game.actions), main.MAX_ACTIONS)
        self.assertTrue(self.game.shop_message)


    def test_action_upgrade_to_v2_costs_200(self):
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.cash = 1000
        self.game.selected_action = action
        self.game._upgrade_action()
        self.assertEqual(action.version, 2)
        self.assertEqual(self.game.cash, 1000 - main.ACTION_UPGRADE_COST)


    def test_v2_action_cannot_be_upgraded(self):
        action = main.ActionItem(main.Action.RECOGNITION, 60, version=2)
        self.game.actions.append(action)
        self.game.cash = 1000
        self.game.selected_action = action
        self.game._upgrade_action()
        self.assertEqual(action.version, 2)
        self.assertEqual(self.game.cash, 1000)  # no charge, already v2


    def test_recognition_action_v1_duplicates_block_for_its_cost(self):
        block = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Pipe")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.RECOGNITION, 60)
        self.game.actions.append(action)
        self.game.cash = 100
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.assertTrue(self.game._apply_action())
        # The original stays and a paid copy joins the toolbox.
        self.assertIn(block, self.game.toolbox.items)
        copies = [i for i in self.game.toolbox.items if i is not block
                  and i.shape == block.shape and i.scorer == block.scorer]
        self.assertEqual(len(copies), 1)
        self.assertEqual(self.game.cash, 100 - 50)
        self.assertEqual(self.game.actions, [])  # consumed


    def test_apply_action_requires_subject(self):
        action = main.ActionItem(main.Action.DEATH, 60)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.game.selected_action_subject = None
        self.assertFalse(self.game._apply_action())
        self.assertIn(action, self.game.actions)  # not consumed without a target


    # --- Cleansweep: an action that spends the purse on cards -------------

    def test_cleansweep_data_lives_in_components(self):
        self.assertEqual(main.Action.name(main.Action.CLEANSWEEP), "Cleansweep")
        self.assertGreater(main.Action.PRICES[main.Action.CLEANSWEEP], 0)
        self.assertIn("card slot", main.Action.description(main.Action.CLEANSWEEP, 1))
        self.assertIn("cash", main.Action.description(main.Action.CLEANSWEEP, 1))
        # v2 does the same sweep without the cost.
        self.assertIn("without spending your cash",
                      main.Action.description(main.Action.CLEANSWEEP, 2))
        # It acts on the player, not on a piece, so it needs no target — and so
        # do the four later actions, which act on the board, the shop, the
        # resource banks and the run itself.
        for action in main.Action.NO_TARGET:
            self.assertFalse(main.Action.needs_target(action),
                             main.Action.name(action))
        self.assertEqual(set(main.Action.NO_TARGET),
                         {main.Action.CLEANSWEEP, main.Action.EXPANSION,
                          main.Action.BRAINSTORM, main.Action.MASS_PRODUCTION,
                          main.Action.GRACE, main.Action.INACTION,
                          main.Action.FORESIGHT})
        for action in main.Action.ORDER:
            if action not in main.Action.NO_TARGET:
                self.assertTrue(main.Action.needs_target(action),
                                main.Action.name(action))


    def test_cleansweep_spends_the_cash_to_fill_every_empty_slot(self):
        # A Cleansweep is paid for with the whole purse and fills every empty
        # card slot with a random card — no target, so it fires from the bare
        # selection. The cards are drawn without repeats (the pool skips what
        # the player owns), so a sweep is never wasted on a duplicate.
        self.game.cash = 250
        owned = main.CardItem(main.Card.SHOWMAN, 48)
        self.game.cards.append(owned)
        action = main.ActionItem(main.Action.CLEANSWEEP, 36)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.assertIsNone(self.game.selected_action_subject)

        self.assertTrue(self.game._apply_action())

        self.assertEqual(self.game.cash, 0)
        self.assertEqual(len(self.game.cards), self.game.max_cards)
        drawn = [c.value for c in self.game.cards if c is not owned]
        self.assertEqual(len(drawn), self.game.max_cards - 1)
        self.assertEqual(len(set(drawn)), len(drawn))  # all different
        for value in drawn:
            self.assertTrue(main.Card.name(value))
        self.assertIn("$250", self.game.shop_message)
        self.assertNotIn(action, self.game.actions)  # consumed
        self.assertIsNone(self.game.selected_action)


    def test_v2_cleansweep_fills_the_slots_without_spending_the_cash(self):
        self.game.cash = 250
        action = main.ActionItem(main.Action.CLEANSWEEP, 36, version=2)
        self.game.actions.append(action)
        self.game.selected_action = action

        self.assertTrue(self.game._apply_action())

        self.assertEqual(self.game.cash, 250)
        self.assertEqual(len(self.game.cards), self.game.max_cards)
        self.assertNotIn("$", self.game.shop_message)


    def test_cleansweep_says_it_needs_no_target(self):
        # Selecting an action and the info-box hint both tell the player what
        # to do next: a targeted action asks for a target, Cleansweep doesn't.
        cleansweep = main.ActionItem(main.Action.CLEANSWEEP, 36)
        death = main.ActionItem(main.Action.DEATH, 24)
        self.game.actions.append(cleansweep)

        self.game._select_action(cleansweep)
        self.assertIn("press S to use", self.game.shop_message)
        self.assertIn("no target", self.game._action_hint(cleansweep, "actions"))

        self.game._select_action(death)
        self.assertIn("click a target block/card", self.game.shop_message)
        self.assertIn("Click a target", self.game._action_hint(death, "actions"))


    def test_cleansweep_is_refused_while_the_card_area_is_full(self):
        # Nothing to sweep: the action is kept and the purse is untouched.
        self.game.cash = 250
        for _ in range(self.game.max_cards):
            self.game.cards.append(main.CardItem(main.Card.GARDEN, 36))
        action = main.ActionItem(main.Action.CLEANSWEEP, 36)
        self.game.actions.append(action)
        self.game.selected_action = action

        self.assertFalse(self.game._apply_action())

        self.assertEqual(self.game.cash, 250)
        self.assertIn(action, self.game.actions)
        self.assertIn("full", self.game.shop_message)


    def _use_action(self, value, version=1):
        """Select and fire an action the way the S key does; returns (ok, item)."""
        item = main.ActionItem(value, main.Action.PRICES[value], version=version)
        self.game.actions.append(item)
        self.game.selected_action = item
        return self.game._apply_action(), item

    def test_expansion_unlocks_four_squares(self):
        # A brand-new game's board is the centered 2x2 region; the four squares
        # come off the frontier next to it (see _grant_locked_units).
        self.game._reset_board_to_start()
        before = len(self.game.unlocked_cells)
        applied, item = self._use_action(main.Action.EXPANSION)
        self.assertTrue(applied)
        self.assertEqual(len(self.game.unlocked_cells),
                         before + main.EXPANSION_SQUARES)
        self.assertNotIn(item, self.game.actions)      # the action is spent
        self.assertIn("Board expanded", self.game.shop_message)

    def test_v2_expansion_unlocks_the_whole_board(self):
        self.game._reset_board_to_start()
        applied, _item = self._use_action(main.Action.EXPANSION, version=2)
        self.assertTrue(applied)
        self.assertEqual(len(self.game.unlocked_cells),
                         main.GRID_WIDTH * main.GRID_HEIGHT)
        self.assertFalse(self.game.board_locked())
        self.assertIn("whole board", self.game.shop_message)

    def test_expansion_is_refused_and_kept_on_a_full_board(self):
        # The harness game's board starts fully unlocked: there is nothing to
        # unlock, so the action is not spent.
        self.assertEqual(len(self.game.unlocked_cells),
                         main.GRID_WIDTH * main.GRID_HEIGHT)
        applied, item = self._use_action(main.Action.EXPANSION)
        self.assertFalse(applied)
        self.assertIn(item, self.game.actions)
        self.assertIn("already fully unlocked", self.game.shop_message)

    def test_brainstorm_banks_free_rerolls(self):
        self.assertEqual(self.game.free_rerolls, 0)
        applied, _item = self._use_action(main.Action.BRAINSTORM)
        self.assertTrue(applied)
        self.assertEqual(self.game.free_rerolls, main.BRAINSTORM_REROLLS)
        # They are BOUGHT, not earned by the run, so they are not in the counter
        # a retry claws back (see free_rerolls_run_gain).
        self.assertEqual(self.game.free_rerolls_run_gain, 0)
        # A refresh spends a banked reroll instead of cash.
        self.game.cash = 100
        self.game._refresh_shop()
        self.assertEqual(self.game.free_rerolls, main.BRAINSTORM_REROLLS - 1)
        self.assertEqual(self.game.cash, 100)
        self.assertIn("Free reroll", self.game.shop_message)

    def test_v2_brainstorm_halves_the_reroll_price(self):
        self.assertEqual(self.game.refresh_cost(), main.SHOP_REFRESH_COST)
        applied, _item = self._use_action(main.Action.BRAINSTORM, version=2)
        self.assertTrue(applied)
        self.assertEqual(self.game.reroll_discount,
                         main.BRAINSTORM_REROLL_FACTOR)
        self.assertEqual(self.game.refresh_cost(), main.SHOP_REFRESH_COST // 2)
        self.game.cash = 100
        self.game._refresh_shop()
        self.assertEqual(self.game.cash, 100 - main.SHOP_REFRESH_COST // 2)
        # The inflation trial still inflates the halved price: the charge in
        # _refresh_shop and the shop's REFRESH button both read refresh_cost.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.INFLATION
        self.assertEqual(self.game.refresh_cost(),
                         self.game._inflated(main.SHOP_REFRESH_COST) // 2)

    def test_mass_production_triples_this_runs_resource_points(self):
        applied, _item = self._use_action(main.Action.MASS_PRODUCTION)
        self.assertTrue(applied)
        self.assertEqual(self.game.resource_point_multiplier(),
                         main.MASS_PRODUCTION_RUN_FACTOR)
        self.game._add_resource_points(main.Scorer.SHREDS, 0.25)
        self.assertAlmostEqual(self.game.shred_run_gain,
                               0.25 * main.MASS_PRODUCTION_RUN_FACTOR)
        # The points bank when the run ends, and the run's factor is spent with
        # them (the fraction stays under the conversion threshold of 1).
        self.game._commit_resource_points()
        self.assertAlmostEqual(self.game.shred_points, 0.75)
        self.assertEqual(self.game.resource_gain_mult, 1.0)
        self.game._add_resource_points(main.Scorer.SHREDS, 0.25)
        self.assertAlmostEqual(self.game.shred_run_gain, 0.25)

    def test_v2_mass_production_doubles_every_point_for_good(self):
        applied, _item = self._use_action(main.Action.MASS_PRODUCTION, version=2)
        self.assertTrue(applied)
        self.assertEqual(self.game.resource_gain_bonus,
                         main.MASS_PRODUCTION_FOREVER_FACTOR)
        # Three runs of fractional triggers, each below the conversion point,
        # all banked at twice their worth. A second copy cannot compound it.
        for _ in range(3):
            self.game._add_resource_points(main.Scorer.RUBBLE, 0.1)
            self.game._commit_resource_points()
        self.assertAlmostEqual(
            self.game.rubble_points,
            3 * 0.1 * main.MASS_PRODUCTION_FOREVER_FACTOR)
        self.assertEqual(self.game.resource_gain_mult, 1.0)
        self._use_action(main.Action.MASS_PRODUCTION, version=2)
        self.assertEqual(self.game.resource_gain_bonus,
                         main.MASS_PRODUCTION_FOREVER_FACTOR)

    def test_grace_adds_one_xmult_to_the_run(self):
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        applied, _item = self._use_action(main.Action.GRACE)
        self.assertTrue(applied)
        self.assertEqual(self.game.run_xmult_bonus, main.GRACE_RUN_XMULT)
        # The run's bank carries it from its first frame — including after a
        # restart or a re-set-up of the same run.
        self.game.reset_run(False)
        self.assertEqual(self.game.run_xmult_pending,
                         1.0 + main.GRACE_RUN_XMULT)
        # It is a whole +1 xMult on top of whatever the run banks, and it lands
        # with the rest of the run's xMult as the run settles.
        self.game._apply_xmult(3.0)
        self.game.score_mult = 10
        self.game._flush_run_xmult()
        self.assertEqual(self.game.score_mult, 10 * 3.0 * 2.0)
        # The bonus belonged to that run: the next one starts without it.
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.assertEqual(self.game.run_xmult_bonus, 0.0)
        self.game.reset_run(False)
        self.assertEqual(self.game.run_xmult_pending, 1.0)

    def test_v2_grace_drops_the_runs_required_score_to_zero(self):
        self.game.required_score = 1000
        applied, _item = self._use_action(main.Action.GRACE, version=2)
        self.assertTrue(applied)
        self.assertEqual(self.game.required_score, 0)
        # A run that scores nothing at all is still cleared (score >= 0), so
        # the run is free but counts as met.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self._complete_run(0, required=0)
        self.assertTrue(self.game.run_cleared)
        self.assertTrue(self.game.run_results[-1])

    def test_actions_appear_in_collection_entries(self):
        entries = self.game._collection_entries()
        actions = [e for e in entries if e[0] == "action"]
        self.assertEqual(len(actions), len(main.Action.ORDER))
        for kind, value, name, desc, has_icon, discovered in actions:
            self.assertIn(value, main.Action.ORDER)
            self.assertEqual(name, "???")
            self.assertEqual(desc, "???")
            self.assertTrue(has_icon)
            self.assertFalse(discovered)


    @unittest.skipUnless(hasattr(main.Card, "JOKER"), NAMED_CARDS_GONE)
    def test_explorer_fraction_is_visited_units_over_total_grid_units(self):
        # Explorer's xMult is 1 + (units the marble has been in / total grid
        # units), and it lands as the run settles (the finish path flushes the
        # xMult bank). 30 of the board's 150 units is a fifth of the board, so
        # the multiplier goes up by +0.2: x1.2, and 10 x 1.2 = 12.
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.visited_cells = {(gx, gy) for gx in range(5)
                                   for gy in range(6)}
        self.game.score_mult = 10
        self.game._apply_cards_on_finish()
        self.game._flush_run_xmult()
        expected = 10 * (1 + 30 / (main.GRID_WIDTH * main.GRID_HEIGHT))
        self.assertAlmostEqual(self.game.score_mult, expected)


    def test_anointment_rolls_a_magnitude_for_each_new_effect(self):
        random.seed(99)
        action = main.ActionItem(main.Action.ANOINTMENT, 32)
        scalable = []
        # Anointment hands out random effects, so bless several blocks to be
        # sure some of them are scaleable ones.
        for i in range(8):
            block = main.BlockItem(0, i, main.Shape.RECT, main.Effect.NONE,
                                   main.Scorer.CHIPS_ADD, 30, 20, "Rect +Chips",
                                   effects=[])
            self.game.toolbox.items.append(block)
            self.game._action_anointment(action, block)
            scalable += [e for e in block.effects if e in main.Effect.MAGNITUDE]

        self.assertTrue(scalable)
        for block in self.game.toolbox.items:
            for e in block.effects:
                if e not in main.Effect.MAGNITUDE:
                    self.assertNotIn(e, block.effect_amounts)
                    continue
                # Each blessed effect carries its own rolled magnitude.
                magnitude = block.effect_amounts[e]
                average = main.Effect.MAGNITUDE[e]
                step = main.magnitude_step(average)
                self.assertGreaterEqual(magnitude, main.effect_magnitude_floor(e))
                self.assertLessEqual(magnitude, average + step * main.MAGNITUDE_MAX_STEPS)


    def test_no_1000_handed_means_no_free_action_after_a_run(self):
        self.game.actions.clear()
        self.game.run_complete = True
        self.game.awaiting_after_run = True

        self.game._continue_run()

        self.assertEqual(self.game.actions, [])


    # --- Deja Vu: an action that grants trigger-limit upgrades ------------

    def test_deja_vu_gives_a_block_one_extra_trigger(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEJA_VU, 56)

        self.assertTrue(self.game._action_deja_vu(action, block))

        self.assertEqual(block.trigger_limit, 2)
        # The action is free once bought: no cash is tracked as refundable.
        self.assertEqual(block.trigger_paid, 0)


    def test_v2_deja_vu_gives_a_hundred_triggers(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEJA_VU, 56, version=2)

        self.assertTrue(self.game._action_deja_vu(action, block))

        self.assertEqual(block.trigger_limit, 101)


    def test_deja_vu_revives_a_spent_block_on_the_board(self):
        placed = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD)
        self.game.grid[(3, 3)] = placed
        placed.triggers_left = 0
        action = main.ActionItem(main.Action.DEJA_VU, 56)

        self.assertTrue(self.game._action_deja_vu(action, placed))

        self.assertEqual(placed.trigger_limit, 2)
        self.assertEqual(placed.triggers_left, 1)  # usable again this run


    def test_deja_vu_upgrades_both_halves_of_a_portal_pair(self):
        number = main.next_portal_number()
        placed = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD, portal_number=number,
                            effects=[main.Effect.PORTAL])
        partner = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                 main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips",
                                 portal_number=number, effects=[main.Effect.PORTAL])
        self.game.grid[(3, 3)] = placed
        self.game.toolbox.add(partner)
        action = main.ActionItem(main.Action.DEJA_VU, 56)

        self.assertTrue(self.game._action_deja_vu(action, placed))

        self.assertEqual(placed.trigger_limit, 2)
        self.assertEqual(partner.trigger_limit, 2)


    def test_deja_vu_refuses_blocks_that_never_spend_a_trigger(self):
        action = main.ActionItem(main.Action.DEJA_VU, 56)
        start = main.Block(3, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = start
        plain = main.Block(4, 3, scorer=main.Scorer.NONE)
        self.game.grid[(4, 3)] = plain
        card = main.CardItem(main.Card.GARDEN, 36)

        self.assertFalse(self.game._action_deja_vu(action, start))
        self.assertFalse(self.game._action_deja_vu(action, plain))
        self.assertFalse(self.game._action_deja_vu(action, card))

        self.assertEqual(start.trigger_limit, 1)
        self.assertEqual(plain.trigger_limit, 1)


    def test_applying_deja_vu_consumes_the_action(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 50, "Rect +Chips")
        self.game.toolbox.add(block)
        action = main.ActionItem(main.Action.DEJA_VU, 56)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.game.selected_action_subject = block
        self.game.cash = 100

        self.assertTrue(self.game._apply_action())

        self.assertEqual(block.trigger_limit, 2)
        self.assertNotIn(action, self.game.actions)
        self.assertEqual(self.game.cash, 100)  # the action was already bought


    def test_anointment_never_hands_out_a_lone_portal(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 20, "b", effects=[])
        self.game.toolbox.add(block)
        for _ in range(40):
            for effect in self.game._random_new_effects(block, 2):
                self.assertNotEqual(effect, main.Effect.PORTAL)


    def test_anointment_v2_blesses_every_block_on_the_board_and_in_the_inventory(self):
        board = main.Block(2, 2, shape=main.Shape.RECT, scorer=main.Scorer.MULT_ADD,
                           effects=[])
        self.game.grid[(2, 2)] = board
        owned = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CASH, 15, 20, "b", effects=[])
        self.game.toolbox.add(owned)
        action = main.ActionItem(main.Action.ANOINTMENT, 32, version=2)

        self.assertTrue(self.game._action_anointment(action, owned))

        self.assertEqual(len(board.effects), 1)
        self.assertEqual(len(owned.effects), 1)


    # --- Strength: scorer amounts -----------------------------------------

    def test_strength_raises_whole_amounts_by_half_and_then_triples(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 30, 20, "b", effects=[])
        self.game.toolbox.add(block)

        self.assertTrue(self.game._action_strength(
            main.ActionItem(main.Action.STRENGTH, 28), block))
        self.assertEqual(block.scorer_amount, 45)  # +50%

        self.assertTrue(self.game._action_strength(
            main.ActionItem(main.Action.STRENGTH, 28, version=2), block))
        self.assertEqual(block.scorer_amount, 135)  # tripled


    def test_strength_keeps_fractional_amounts_fractional(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.MULT_MUL, 1.5, 20, "b", effects=[])
        self.game.toolbox.add(block)

        self.game._action_strength(main.ActionItem(main.Action.STRENGTH, 28), block)

        self.assertAlmostEqual(block.scorer_amount, 2.25)


    def test_strength_refuses_blocks_with_nothing_to_strengthen(self):
        action = main.ActionItem(main.Action.STRENGTH, 28)
        plain = main.Block(3, 3, scorer=main.Scorer.NONE)
        start = main.Block(4, 3, scorer=main.Scorer.START)
        self.game.grid[(3, 3)] = plain
        self.game.grid[(4, 3)] = start

        self.assertFalse(self.game._action_strength(action, plain))
        self.assertFalse(self.game._action_strength(action, start))
        self.assertFalse(self.game._action_strength(
            action, main.CardItem(main.Card.GARDEN, 36)))
        self.assertEqual(start.scorer_amount, 0)


class InactionTests(GameTestCase):
    """The Inaction action: it does nothing, five times over."""

    def _use(self, version=1):
        """Select a fresh Inaction and use it; return whether it applied."""
        action = main.ActionItem(main.Action.INACTION, 24, version=version)
        self.game.actions.append(action)
        self.game.selected_action = action
        return self.game._apply_action()

    def test_the_action_data(self):
        self.assertEqual(main.Action.name(main.Action.INACTION), "Inaction")
        # The description is the joke, word for word.
        self.assertEqual(main.Action.description(main.Action.INACTION, 1),
                         "...does nothing?")
        self.assertEqual(main.Action.PRICES[main.Action.INACTION], 24)
        self.assertIn(main.Action.INACTION, main.Action.ORDER)
        self.assertEqual(main.INACTION_USES_PER_SLOT, 5)
        # It acts on the player, not on a piece: selecting it and pressing S
        # uses it, with no target to pick (see Action.NO_TARGET).
        self.assertFalse(main.Action.needs_target(main.Action.INACTION))
        self.game.actions.append(main.ActionItem(main.Action.INACTION, 24))
        self.game._select_action(self.game.actions[-1])
        self.assertIn("press S", self.game.shop_message)

    def test_five_uses_win_a_card_slot(self):
        self.assertEqual(self.game.max_cards, main.MAX_CARDS)
        # The first four are a step toward the fifth, not a partial slot.
        for use in range(1, main.INACTION_USES_PER_SLOT):
            self.assertTrue(self._use())
            self.assertEqual(self.game.inaction_used, use)
            self.assertEqual(self.game.max_cards, main.MAX_CARDS)
            self.assertIn("for a card slot", self.game.shop_message)
        self.assertTrue(self._use())
        self.assertEqual(self.game.inaction_used, 5)
        self.assertEqual(self.game.max_cards, main.MAX_CARDS + 1)
        self.assertIn("card area grew", self.game.shop_message)
        # It keeps counting: five more uses is another slot.
        for _ in range(main.INACTION_USES_PER_SLOT):
            self.assertTrue(self._use())
        self.assertEqual(self.game.max_cards, main.MAX_CARDS + 2)

    def test_each_use_is_consumed_like_any_other_action(self):
        action = main.ActionItem(main.Action.INACTION, 24)
        self.game.actions.append(action)
        self.game.selected_action = action

        self.assertTrue(self.game._apply_action())

        self.assertNotIn(action, self.game.actions)
        self.assertIsNone(self.game.selected_action)

    def test_a_v2_inaction_hands_over_a_card_slot(self):
        # The v2 buys the fifth use outright: one use, one slot.
        self.assertTrue(self._use(version=2))
        self.assertEqual(self.game.card_slots_won, 1)
        self.assertEqual(self.game.inaction_used, 0)     # not banked, handed over
        self.assertEqual(self.game.max_cards, main.MAX_CARDS + 1)
        self.assertIn("handed over a card slot", self.game.shop_message)
        # ...and every further v2 is another slot.
        self.assertTrue(self._use(version=2))
        self.assertEqual(self.game.max_cards, main.MAX_CARDS + 2)
        # The v1 counter still works alongside it: five uses, one more slot.
        for _ in range(main.INACTION_USES_PER_SLOT):
            self.assertTrue(self._use())
        self.assertEqual(self.game.max_cards, main.MAX_CARDS + 3)
        self.assertIn("hands over a card slot",
                      main.Action.description(main.Action.INACTION, 2))

    def test_it_is_refused_when_the_panel_cannot_show_another_slot(self):
        # The tray's slots and the action row's add up to SLOT_ROW_SLOTS in all:
        # with the tray already as wide as the panel column allows, a use that
        # would win a slot is refused and the action KEPT, rather than spent on a
        # slot that could not be drawn.
        for _ in range(3 * main.INACTION_USES_PER_SLOT):
            self.assertTrue(self._use())
        self.assertEqual(self.game.max_cards,
                         main.SLOT_ROW_SLOTS - self.game.max_actions)
        self.assertEqual(self.game.card_slot_room(), 0)
        # Four more uses are just counted (no slot is due yet)...
        for _ in range(main.INACTION_USES_PER_SLOT - 1):
            self.assertTrue(self._use())
        # ...and the one that would have completed a slot is refused.
        action = main.ActionItem(main.Action.INACTION, 24)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.assertFalse(self.game._apply_action())
        self.assertIn("as wide as the panel allows", self.game.shop_message)
        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.inaction_used,
                         4 * main.INACTION_USES_PER_SLOT - 1)

    def test_essence_still_takes_its_slot_away(self):
        # The Essence card's slot is still gone; Inaction's slots are counted on
        # top of the smaller tray.
        self.game.cards.append(main.CardItem(main.Card.ESSENCE, 48))
        self.assertEqual(self.game.max_cards, main.MAX_CARDS - 1)
        for _ in range(main.INACTION_USES_PER_SLOT):
            self.assertTrue(self._use())
        self.assertEqual(self.game.max_cards, main.MAX_CARDS)


class ForesightTests(GameTestCase):
    """The Foresight action: a permanent extra action slot."""

    def _use(self, version=1):
        action = main.ActionItem(main.Action.FORESIGHT, 90, version=version)
        self.game.actions.append(action)
        self.game.selected_action = action
        return self.game._apply_action()

    def test_the_action_data(self):
        self.assertEqual(main.Action.name(main.Action.FORESIGHT), "Foresight")
        self.assertIn(main.Action.FORESIGHT, main.Action.ORDER)
        # Relatively expensive: the dearest action in the catalogue.
        others = [main.Action.PRICES[v] for v in main.Action.ORDER
                  if v != main.Action.FORESIGHT]
        self.assertEqual(main.Action.PRICES[main.Action.FORESIGHT], 90)
        self.assertGreater(main.Action.PRICES[main.Action.FORESIGHT], max(others))
        self.assertFalse(main.Action.needs_target(main.Action.FORESIGHT))
        self.assertIn("action slot", main.Action.description(main.Action.FORESIGHT, 1))

    def test_it_permanently_adds_an_action_slot(self):
        self.assertEqual(self.game.max_actions, main.MAX_ACTIONS)
        self.assertEqual(self.game.action_area_x(), main.ACTION_AREA_COORDS[0])

        self.assertTrue(self._use())

        self.assertEqual(self.game.max_actions, main.MAX_ACTIONS + 1)
        self.assertEqual(self.game.action_slots_won, 1)
        self.assertIn("added 1 action slot", self.game.shop_message)
        # The row is its own line in the panel column, so a wider row does not
        # move it: it still starts beside the card tray's left edge, and the
        # slot past the ones that fit before the upgrade button is reached by
        # paging the row (see Game.action_row_window).
        self.assertEqual(self.game.action_area_x(), main.ACTION_AREA_COORDS[0])
        self.assertEqual(self.game.action_slots_shown(), main.ACTION_BAND_SLOTS)
        self.assertEqual(self.game.action_area_x()
                         + self.game.action_slots_shown() * main.GRID_SIZE
                         + 12,
                         main.ACTION_UPGRADE_RECT.left)

    def test_the_extra_slot_really_holds_an_action(self):
        # Every path that fills the action area asks the GAME for its size, so
        # the wider row is not just decoration: one more action fits, and the
        # hit test finds the action the row shows in its first slot.
        self.game.actions = []
        self.assertTrue(self._use())
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)
                             for _ in range(self.game.max_actions)]
        self.assertFalse(self.game._grant_random_action())
        self.assertIn("full", self.game.shop_message)
        # A click in the leftmost (new) slot selects the action drawn there.
        rect = pygame.Rect(self.game.action_area_x(), main.ACTION_AREA_COORDS[1],
                           main.GRID_SIZE, main.GRID_SIZE)
        self.assertIs(self.game.action_area_item_at(rect.center),
                      self.game.actions[0])

    def test_a_v2_foresight_removes_the_limit(self):
        self.assertFalse(self.game.action_slots_unlimited)

        self.assertTrue(self._use(version=2))

        self.assertTrue(self.game.action_slots_unlimited)
        self.assertEqual(self.game.max_actions, main.ACTION_SLOTS_UNLIMITED)
        self.assertIn("removed the limit", self.game.shop_message)
        self.assertIn("no limit at all",
                      main.Action.description(main.Action.FORESIGHT, 1))
        # Nothing refuses an action for room any more: fill far past the line
        # and both the purchase path and the grant path still say yes.
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)
                             for _ in range(main.SLOT_ROW_SLOTS + 4)]
        self.assertTrue(self.game._grant_random_action())
        self.assertGreater(len(self.game.actions), main.SLOT_ROW_SLOTS)
        # A second v2 has nothing left to give, so it is refused and kept.
        action = main.ActionItem(main.Action.FORESIGHT, 90, version=2)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.assertFalse(self.game._apply_action())
        self.assertIn("already unlimited", self.game.shop_message)
        self.assertIn(action, self.game.actions)

    def test_a_full_row_pages_every_action_into_reach(self):
        # The row's line can only SHOW so many slots, so the row pages through
        # the rest: every held action stays clickable, which is what makes an
        # unlimited action area usable (see Game.action_row_window).
        self._use(version=2)
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)
                             for _ in range(9)]
        slots = self.game.action_slots_shown()
        per_page = slots - 1
        pages = -(-len(self.game.actions) // per_page)

        start, count, paging = self.game.action_row_window()

        self.assertTrue(paging)
        self.assertEqual((start, count), (0, per_page))
        # The pager slot is the last one, and holds no action of its own.
        self.assertTrue(self.game.action_area_pager_at(
            self.game.action_slot_rect(slots - 1).center))
        self.assertIsNone(self.game.action_area_item_at(
            self.game.action_slot_rect(slots - 1).center))
        # Turning the pages reaches every action, then wraps round again.
        seen = []
        for _ in range(2 * pages):
            start, count, _paging = self.game.action_row_window()
            self.assertGreater(count, 0)
            seen.extend(self.game.action_area_item_at(
                self.game.action_slot_rect(i).center) for i in range(count))
            self.game._page_action_row()
        self.assertEqual({id(action) for action in seen},
                         {id(action) for action in self.game.actions})
        self.assertEqual(self.game.action_area_page, 2 * pages)
        self.assertEqual(self.game.action_row_window()[0], 0)   # wrapped round

    def test_a_row_that_fits_does_not_page(self):
        self._use(version=2)
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)]

        start, count, paging = self.game.action_row_window()

        self.assertEqual((start, count), (0, 1))
        self.assertFalse(paging)
        self.assertFalse(self.game.action_area_pager_at(
            self.game.action_slot_rect(self.game.action_slots_shown() - 1).center))
        # An empty slot past the actions is empty, pager or not.
        self.assertIsNone(self.game.action_area_item_at(
            self.game.action_slot_rect(1).center))

    def test_the_pager_says_which_page_is_on_show(self):
        self._use(version=2)
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)
                             for _ in range(self.game.action_slots_shown() + 1)]

        self.game._page_action_row()

        self.assertEqual(self.game.action_area_page, 1)
        self.assertIn("Showing actions", self.game.shop_message)

    def test_the_set_pager_exists_only_when_the_row_overflows(self):
        self._use(version=2)
        self.game.actions = [main.ActionItem(main.Action.DEATH, 24)
                             for _ in range(self.game.action_slots_shown() + 1)]
        slots = self.game.action_slots_shown()
        self.assertTrue(self.game.action_area_pager_at(
            self.game.action_slot_rect(slots - 1).center))
        self.assertFalse(self.game.action_area_pager_at(
            self.game.action_slot_rect(0).center))

    def test_it_is_refused_when_the_band_has_no_room(self):
        # The cards-and-actions band holds SLOT_ROW_SLOTS slots in all, so a
        # Foresight that would push the pair past it is refused and kept. Three
        # Inaction slots fill the band: 8 cards + 2 actions is all it holds.
        self.game.inaction_used = (main.SLOT_ROW_SLOTS - main.MAX_ACTIONS
                                   - main.MAX_CARDS) * main.INACTION_USES_PER_SLOT
        self.assertEqual(self.game.max_cards + self.game.max_actions,
                         main.SLOT_ROW_SLOTS)
        self.assertEqual(self.game.action_slot_room(), 0)

        action = main.ActionItem(main.Action.FORESIGHT, 90)
        self.game.actions.append(action)
        self.game.selected_action = action
        self.assertFalse(self.game._apply_action())

        self.assertIn("as wide as the panel allows", self.game.shop_message)
        self.assertIn(action, self.game.actions)  # kept, not spent
        self.assertEqual(self.game.max_actions, main.MAX_ACTIONS)

