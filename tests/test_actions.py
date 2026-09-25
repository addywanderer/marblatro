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
        self.assertEqual(main.Action.PRICES[main.Action.DEATH], 24)
        self.assertEqual(main.Action.PRICES[main.Action.RECOGNITION], 24)
        self.assertEqual(main.Action.PRICES[main.Action.DEJA_VU], 28)
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
                          main.Action.CLEANSWEEP])
        # Deja Vu's two versions add triggers: +1, then +100.
        self.assertIn("+1 trigger", main.Action.description(main.Action.DEJA_VU, 1))
        self.assertIn("+100 triggers", main.Action.description(main.Action.DEJA_VU, 2))


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
        # It acts on the player, not on a piece, so it needs no target — every
        # other action does.
        self.assertFalse(main.Action.needs_target(main.Action.CLEANSWEEP))
        self.assertIn(main.Action.CLEANSWEEP, main.Action.NO_TARGET)
        for action in main.Action.ORDER:
            if action != main.Action.CLEANSWEEP:
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
    def test_explorer_fraction_is_distance_over_total_grid_units(self):
        # Explorer's xMult is 1 + (travelled grid units / total grid cells).
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        marble = self._add_marble()
        marble.distance = 1500.0
        self.game.score_mult = 10
        self.game._apply_cards_on_finish()
        expected = 10 * (1 + (1500 / main.GRID_SIZE) / (main.GRID_WIDTH * main.GRID_HEIGHT))
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
