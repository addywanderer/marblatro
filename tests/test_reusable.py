"""When a card is used it is DISCARDED — unless it has the keyword "reusable".

User request: "when a card is used, discard it unless it has the keyword
'reusable'."

So there are two halves:

* the RULE — a used card leaves through the ordinary discard door
  (`Game._discard_used_card`), which takes it out of play and counts it among
  the items the run threw away (the Trash Can card pays for those). Every
  "discard this card" in the game goes through that one door: a spent action
  (`Game._consume_action`), a Lantern burning out and a Reroll turning a
  structure over. An action a pack handed over never joined the hand, so its
  slot is cleared instead — but the run still counts it;
* the WORD — `components.Keyword.REUSABLE`, the counterpart of CONSUME. Every
  tool says which of the two it is (a brick is used up, a shovel is not), and any
  item can be marked with `components.Modifier.REUSABLE`, which prints the word
  and makes the rule leave it alone.
"""

from tests.game_test_case import *  # noqa: F401,F403


class ReusableKeywordTests(GameTestCase):
    """The word itself, and which tools wear it."""

    def _tool(self, value):
        return main.ToolItem(value, main.Tool.PRICES[value])

    def test_the_word_is_one_word_and_says_what_it_does(self):
        name = main.Keyword.name(main.Keyword.REUSABLE)
        self.assertEqual(name, "reusable")
        self.assertTrue(name.isalpha())
        self.assertEqual(name, name.lower())
        self.assertIn(main.Keyword.REUSABLE, main.Keyword.ORDER)
        self.assertIn(main.Keyword.REUSABLE, main.Keyword.NAMES)
        description = main.Keyword.description(main.Keyword.REUSABLE).lower()
        self.assertIn("discard", description)
        self.assertIn("not", description)

    def test_every_tool_says_consume_or_reusable(self):
        # "when a card is used, discard it unless it has the keyword reusable":
        # every tool that can be used states which way it goes, and no tool
        # claims both.
        for value in main.Tool.ORDER:
            with self.subTest(tool=main.Tool.name(value)):
                item = self._tool(value)
                words = main.Keyword.of(item)
                consume = main.Keyword.CONSUME in words
                reusable = main.Keyword.REUSABLE in words
                self.assertFalse(consume and reusable)
                if main.Tool.consumes(value):
                    self.assertTrue(consume)
                elif main.Tool.opens_structures(value) or main.Tool.modifies(value):
                    self.assertTrue(reusable)
                else:
                    # A lump of dirt can never be used at all, so neither word
                    # applies: it is simply unplayable.
                    self.assertEqual(words, (main.Keyword.UNPLAYABLE,))

    def test_the_starters_and_permanent_tools_read_reusable(self):
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.SHOVEL)),
                         "dig, reusable")
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.HAMMER)),
                         "break, reusable")
        # A multi-verb tool keeps its verbs in order and ends with the word.
        self.assertEqual(
            main.Keyword.line(self._tool(main.Tool.MULTI_TOOL)),
            "dig, reveal, fix, break, reusable")

    def test_a_one_shot_tool_still_reads_consume(self):
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.BRICK)),
                         "break, dig, consume")
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.MATCH)),
                         "reveal, consume, draw 1")

    def test_a_plain_action_reads_consume(self):
        # User request: "give all cards that used to be actions the keyword
        # 'consume' because that is how they behave."
        action = main.ActionItem(main.Action.DEATH, main.Action.PRICES[main.Action.DEATH])
        self.assertEqual(main.Keyword.of(action), (main.Keyword.CONSUME,))
        self.assertEqual(main.Keyword.line(action), "consume")
        self.assertFalse(main.Keyword.has(action, main.Keyword.REUSABLE))

    def test_the_modifier_prints_the_word_and_beats_consume(self):
        brick = self._tool(main.Tool.BRICK)
        main.Modifier.add(brick, main.Modifier.REUSABLE, 1)
        self.assertTrue(main.Modifier.has(brick, main.Modifier.REUSABLE))
        self.assertEqual(main.Keyword.line(brick), "break, dig, reusable")
        # The two words are opposites, so an item that survives its use never
        # also claims to be destroyed by it...
        self.assertFalse(main.Keyword.has(brick, main.Keyword.CONSUME))
        # ...and the item agrees: using it no longer destroys it.
        self.assertFalse(brick.consumes)

    def test_the_modifier_has_a_name_and_a_meaning(self):
        self.assertEqual(main.Modifier.name(main.Modifier.REUSABLE), "reusable")
        self.assertIn(main.Modifier.REUSABLE, main.Modifier.ORDER)
        self.assertIn("discard",
                      main.Modifier.description(main.Modifier.REUSABLE).lower())


class UsedCardTests(GameTestCase):
    """Using a card throws it away — unless it is reusable."""

    def _block(self, amount=30):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, amount, 20, "b",
                               effects=[])
        self.game.toolbox.add(block)
        return block

    def _action(self, value, reusable=False, **kwargs):
        item = main.ActionItem(value, main.Action.PRICES[value], **kwargs)
        self.game._adopt_action(item)
        if reusable:
            main.Modifier.add(item, main.Modifier.REUSABLE, 1)
        return item

    def _use(self, action, subject=None):
        """Use the action on the subject through the real S-key dispatch."""
        self.game.selection = [action] + ([subject] if subject is not None else [])
        self.game._refresh_actor()
        return self.game._apply_action()

    def test_a_used_card_is_discarded(self):
        block = self._block()
        action = self._action(main.Action.STRENGTH)
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action, block))

        self.assertFalse(self.game.owns_item(action), "the used card is still owned")
        self.assertNotIn(action, self.game.actions)
        self.assertEqual(block.scorer_amount, 45)     # the effect still happened
        self.assertEqual(self.game.discarded_items_run, discarded + 1,
                         "the used card was not counted as discarded")

    def test_a_reusable_card_is_not_discarded(self):
        block = self._block()
        action = self._action(main.Action.STRENGTH, reusable=True)
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action, block))

        self.assertTrue(self.game.owns_item(action), "a reusable card was thrown away")
        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.discarded_items_run, discarded,
                         "a reusable card was counted as discarded")
        self.assertEqual(block.scorer_amount, 45)

    def test_a_reusable_card_can_be_used_again(self):
        block = self._block()
        action = self._action(main.Action.STRENGTH, reusable=True)

        self.assertTrue(self._use(action, block))
        self.assertTrue(self._use(action, block))

        self.assertEqual(block.scorer_amount, 68)     # 30 -> 45 -> 68 (+50% twice)
        self.assertIn(action, self.game.actions)

    def test_a_reusable_card_still_pays_its_energy(self):
        action = self._action(main.Action.DEEP_POCKETS, reusable=True)
        self.game.energy = 3

        self.assertTrue(self._use(action))

        self.assertEqual(self.game.energy, 2, "the energy was not spent")
        self.assertTrue(self.game.owns_item(action))
        packs = [item for item in self.game.toolbox.every_item()
                 if getattr(item, "kind", None) == "pack"]
        self.assertEqual(len(packs), 1, "the reusable action did not fire")

    def test_using_a_reusable_card_turns_the_selection_over(self):
        # The card is not left armed: a second S must not fire it by accident.
        block = self._block()
        action = self._action(main.Action.STRENGTH, reusable=True)

        self._use(action, block)

        self.assertIsNone(self.game.selected_action)
        self.assertFalse(self.game.is_item_selected(action))

    def test_the_lantern_stays_lit_when_it_is_reusable(self):
        for _ in range(3):
            card = main.CardItem(main.Card.JOKER, main.Card.PRICES[main.Card.JOKER])
            self.game.cards.append(card)
            self.game._to_deck(card)
        action = self._action(main.Action.LANTERN, reusable=True)
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action))

        self.assertIn(action, self.game.actions)
        self.assertEqual(self.game.discarded_items_run, discarded)
        self.assertIn("stayed lit", self.game.shop_message)

    def test_the_reroll_card_is_kept_when_it_is_reusable(self):
        structure = main.StructureItem(main.Structure.PIT,
                                      main.Structure.PRICES[main.Structure.PIT])
        self.game.shop.items.append(structure)
        self.game.set_item_cell(structure, self.game._first_free_cell())
        action = self._action(main.Action.REROLL, reusable=True)
        was = structure.value
        discarded = self.game.discarded_items_run

        self.assertTrue(self._use(action, structure))

        self.assertNotEqual(structure.value, was, "the structure was not rerolled")
        self.assertIn(action, self.game.actions, "the reusable card was thrown away")
        self.assertEqual(self.game.discarded_items_run, discarded)

    def test_a_reusable_tool_is_not_used_up(self):
        # The rule is the same for a tool: a one-shot tool marked reusable opens
        # its structure and then stays in hand instead of being destroyed.
        structure = main.StructureItem(main.Structure.MIRROR,
                                       main.Structure.PRICES[main.Structure.MIRROR])
        structure.is_level_structure = True
        self.game.shop.items.append(structure)
        self.game.set_item_cell(structure, self.game._first_free_cell())
        brick = main.ToolItem(main.Tool.BRICK, main.Tool.PRICES[main.Tool.BRICK])
        self.game.toolbox.add(brick)
        main.Modifier.add(brick, main.Modifier.REUSABLE, 1)
        discarded = self.game.discarded_items_run

        self.game.selection = [brick, structure]
        self.game._refresh_actor()
        self.assertTrue(self.game._apply_tool())

        self.assertTrue(self.game.owns_item(brick), "the reusable tool was used up")
        self.assertEqual(self.game.discarded_items_run, discarded)
        self.assertEqual([item.value for item in self.game.actions],
                         [main.Action.STRENGTH])

    def test_a_packed_action_is_discarded_when_it_is_used(self):
        action = main.ActionItem(main.Action.GRACE, main.Action.PRICES[main.Action.GRACE])
        discarded = self.game.discarded_items_run

        self.game._keep_action_from_pack(action)

        self.assertIsNone(self.game.pending_pack_action)
        self.assertEqual(self.game.actions, [])
        self.assertEqual(self.game.discarded_items_run, discarded + 1,
                         "the packed action was not counted as discarded")

    def test_a_reusable_packed_action_stays_armed(self):
        action = main.ActionItem(main.Action.GRACE, main.Action.PRICES[main.Action.GRACE])
        main.Modifier.add(action, main.Modifier.REUSABLE, 1)
        discarded = self.game.discarded_items_run

        self.game._keep_action_from_pack(action)

        self.assertIs(self.game.pending_pack_action, action)
        self.assertEqual(self.game.discarded_items_run, discarded)

    def test_a_reusable_card_survives_a_save_and_a_load(self):
        action = self._action(main.Action.STRENGTH, reusable=True)
        save_system.save_game(self.game, announce=False)

        fresh = main.Game()
        fresh.title_screen = False
        save_system.load_slot(fresh, self.game.save_slot)

        loaded = [item for item in fresh.actions
                  if getattr(item, "kind", None) == "action"
                  and item.value == main.Action.STRENGTH]
        self.assertEqual(len(loaded), 1)
        self.assertTrue(main.Keyword.has(loaded[0], main.Keyword.REUSABLE))


class ReusableSidebarTests(GameTestCase):
    """What the player is told: the words, and what using the card costs."""

    def test_the_info_box_names_the_keyword(self):
        # A plain action says "consume"; a reusable one replaces the word (user
        # request: "give all cards that used to be actions the keyword
        # 'consume' because that is how they behave").
        action = main.ActionItem(main.Action.STRENGTH, main.Action.PRICES[main.Action.STRENGTH])
        rows = dict(self.game._describe_item(action))
        self.assertEqual(rows["Keywords"], "consume")
        self.assertIn("Consume", rows)
        main.Modifier.add(action, main.Modifier.REUSABLE, 1)
        rows = dict(self.game._describe_item(action))
        self.assertEqual(rows["Keywords"], "reusable")
        self.assertNotIn("Consume", rows)
        # ...and the ability line says the card is not discarded.
        ability = rows["Ability - Apply"]
        self.assertIn("not discarded", ability)

    def test_a_plain_actions_ability_states_the_energy_alone(self):
        # What a used card spends of ITSELF is its keyword now ("consume"), so
        # the contract names no cost of its own (user request: "make all cards
        # homogenous").
        action = main.ActionItem(main.Action.STRENGTH, main.Action.PRICES[main.Action.STRENGTH])
        rows = dict(self.game._describe_item(action))
        self.assertIn("Costs nothing.", rows["Ability - Apply"])

    def test_a_reusable_energy_card_states_the_energy_alone(self):
        action = main.ActionItem(main.Action.EYEBALL, main.Action.PRICES[main.Action.EYEBALL])
        main.Modifier.add(action, main.Modifier.REUSABLE, 1)
        rows = dict(self.game._describe_item(action))
        self.assertIn("1 energy", rows["Ability - Apply"])

    def test_a_tools_keywords_row_carries_the_word(self):
        rows = dict(self.game._describe_item(
            main.ToolItem(main.Tool.SHOVEL, main.Tool.PRICES[main.Tool.SHOVEL])))
        self.assertEqual(rows["Keywords"], "dig, reusable")

    def test_a_reusable_one_shot_tool_drops_its_consume_row(self):
        # The sidebar is consistent with the word: a brick marked reusable says
        # "reusable" in its keywords and no longer claims to be consumed.
        brick = main.ToolItem(main.Tool.BRICK, main.Tool.PRICES[main.Tool.BRICK])
        self.assertIn("Consume", dict(self.game._describe_item(brick)))
        main.Modifier.add(brick, main.Modifier.REUSABLE, 1)
        rows = dict(self.game._describe_item(brick))
        self.assertEqual(rows["Keywords"], "break, dig, reusable")
        self.assertNotIn("Consume", rows)
