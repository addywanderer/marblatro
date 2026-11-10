"""The item vocabulary: single words that mean something specific.

User request: "add terminology for items. just include a single word that means
something more specific. 'break', 'fix', 'dig', and 'reveal' are all part of
this group. 'consume' means destroy this item after use. 'unplayable' means that
an item cannot be used (it is a passive item)."

`components.Keyword` is that vocabulary, and an item's keywords are derived from
its own tables (see Keyword.of), so a word never has to be typed twice. These
tests pin the words themselves and the items the request added alongside them:
the passive Concrete, and the one-shot tools' text.
"""

from tests.game_test_case import *  # noqa: F401,F403


class KeywordTests(GameTestCase):
    """The vocabulary itself."""

    def test_every_keyword_is_one_word_with_a_meaning(self):
        for keyword in main.Keyword.ORDER:
            with self.subTest(keyword=main.Keyword.name(keyword)):
                name = main.Keyword.name(keyword)
                # "just include a single word": no spaces, no punctuation.
                self.assertTrue(name)
                self.assertNotIn(" ", name)
                self.assertTrue(name.isalpha())
                self.assertEqual(name, name.lower())
                self.assertTrue(main.Keyword.description(keyword))

    def test_the_four_verbs_are_in_the_vocabulary(self):
        names = {main.Keyword.name(keyword) for keyword in main.Keyword.ORDER}
        self.assertLessEqual({"dig", "reveal", "fix", "break"}, names)
        for verb in main.Verb.ORDER:
            with self.subTest(verb=main.Verb.name(verb)):
                keyword = main.Keyword.for_verb(verb)
                self.assertEqual(main.Keyword.name(keyword),
                                 main.Verb.name(verb))

    def test_consume_and_unplayable_mean_what_the_request_says(self):
        self.assertEqual(main.Keyword.name(main.Keyword.CONSUME), "consume")
        self.assertIn("destroyed",
                      main.Keyword.description(main.Keyword.CONSUME).lower())
        self.assertEqual(main.Keyword.name(main.Keyword.UNPLAYABLE),
                         "unplayable")
        self.assertIn("cannot be used",
                      main.Keyword.description(main.Keyword.UNPLAYABLE).lower())
        for keyword in main.Keyword.ORDER:
            self.assertIn(keyword, main.Keyword.NAMES)
            self.assertIn(keyword, main.Keyword.DESCRIPTIONS)

    def test_the_words_read_as_one_line(self):
        self.assertEqual(
            main.Keyword.text((main.Keyword.BREAK, main.Keyword.DIG,
                               main.Keyword.CONSUME)),
            "break, dig, consume")
        self.assertEqual(
            main.Keyword.text((main.Keyword.REVEAL, main.Keyword.CONSUME,
                               main.Keyword.DRAW), {main.Keyword.DRAW: 1}),
            "reveal, consume, draw 1")
        self.assertEqual(main.Keyword.text(()), "")


class ItemKeywordTests(GameTestCase):
    """An item's keywords come from its tables, never from its text."""

    def _tool(self, value):
        return main.ToolItem(value, main.Tool.PRICES[value])

    def test_a_tools_keywords_are_its_rules(self):
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.SHOVEL)), "dig")
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.BRICK)),
                         "break, dig, consume")
        self.assertEqual(main.Keyword.line(self._tool(main.Tool.MATCH)),
                         "reveal, consume, draw 1")

    def test_a_passive_item_is_unplayable(self):
        concrete = main.PassiveItem(main.Passive.CONCRETE,
                                    main.Passive.PRICES[main.Passive.CONCRETE])
        self.assertEqual(main.Keyword.line(concrete), "unplayable")
        # "it is a passive item": it has no ability at all, so S does nothing.
        self.assertIsNone(main.Ability.of(concrete))

    def test_a_structure_reads_the_verbs_it_answers_to(self):
        for structure in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(structure)):
                self.assertEqual(
                    main.Keyword.of(main.StructureItem(structure, 0)),
                    tuple(main.Keyword.for_verb(verb)
                          for verb in main.Structure.verbs(structure)))

    def test_a_block_or_a_card_has_no_keywords(self):
        # Their behaviour is their own text (a shape, a scorer, a card effect).
        self.assertEqual(main.Keyword.of(main.Block(0, 0)), ())
        self.assertEqual(main.Keyword.of(main.CardItem(main.Card.JOKER, 24)), ())
        self.assertEqual(main.Keyword.of(None), ())

    def test_the_sidebar_prints_the_keywords(self):
        rows = dict(self.game._describe_item(self._tool(main.Tool.BRICK)))
        self.assertEqual(rows["Keywords"], "break, dig, consume")
        self.assertEqual(rows["Energy"], "0 a use (3 left this run)")
        # ...and the ability line states the tool's OWN cost, not the average.
        self.assertIn("Costs nothing.",
                      rows["Ability - Open"])


class ConcreteTests(GameTestCase):
    """The passive item: +30 chips at the start of every run, and unplayable."""

    def _own(self, count=1):
        items = []
        for _ in range(count):
            item = main.PassiveItem(main.Passive.CONCRETE,
                                    main.Passive.PRICES[main.Passive.CONCRETE])
            self.game.toolbox.add(item)
            items.append(item)
        return items

    def test_it_pays_its_magnitude_at_the_start_of_the_run(self):
        self._own(1)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run(False))

        self.assertEqual(self.game._base_chips,
                         main.RUN_BASE_CHIPS + main.MAGNITUDES.CONCRETE_CHIPS)
        self.assertEqual(self.game.score_chips, self.game._base_chips)

    def test_two_of_them_pay_twice(self):
        self._own(2)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run(False))

        self.assertEqual(self.game._base_chips,
                         main.RUN_BASE_CHIPS
                         + 2 * main.MAGNITUDES.CONCRETE_CHIPS)

    def test_it_carries_an_amount_like_every_other_item(self):
        # EVERY item has an amount (a magnitude): Concrete's is the chips it
        # adds, 30, which is what a golem folds and what the sidebar reads.
        item = main.PassiveItem(main.Passive.CONCRETE,
                                main.Passive.PRICES[main.Passive.CONCRETE])
        self.assertEqual(item.amount, main.MAGNITUDES.CONCRETE_CHIPS)
        self.assertEqual(main.Passive.amount(main.Passive.CONCRETE),
                         main.MAGNITUDES.CONCRETE_CHIPS)

    def test_the_run_pays_the_amount_the_item_carries(self):
        self.game.toolbox.add(main.PassiveItem(
            main.Passive.CONCRETE, main.Passive.PRICES[main.Passive.CONCRETE],
            amount=main.MAGNITUDES.CONCRETE_CHIPS * 2))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(self.game.reset_run(False))

        self.assertEqual(self.game._base_chips,
                         main.RUN_BASE_CHIPS
                         + 2 * main.MAGNITUDES.CONCRETE_CHIPS)

    def test_its_description_states_the_magnitude(self):
        text = main.Passive.description(main.Passive.CONCRETE)
        self.assertIn(str(main.MAGNITUDES.CONCRETE_CHIPS), text)
        self.assertIn("cannot be used", text)
        # A combined one reads out the amount it actually carries.
        self.assertIn("60", main.Passive.description(main.Passive.CONCRETE,
                                                     amount=60))

    def test_pressing_s_does_nothing(self):
        item = self._own(1)[0]
        self.game.ensure_board_cells()
        self._click(self._item_pos(item))
        chips = self.game._base_chips

        self._press(main.pygame.K_s)

        self.assertEqual(self.game._base_chips, chips)
        self.assertTrue(self.game.owns_item(item))


class ToolPackTests(GameTestCase):
    """Where the one-shot tools and the passives are found."""

    def test_a_tool_pack_deals_tools_and_passives(self):
        self.assertEqual(main.Pack.name(main.Pack.TOOL), "Tool Pack")
        # The pack deals every tool that is not starting kit, plus the passives,
        # so nothing in the game is out of reach (see Tool.PACK_ORDER).
        self.assertEqual(
            sorted(main.tool_pack_options()),
            sorted([("tool", value) for value in main.Tool.PACK_ORDER]
                   + [("passive", value) for value in main.Passive.ORDER]))

        pack = self.game.shop._roll_pack(main.Pack.TOOL, main.Pack.NORMAL)

        self.assertEqual(pack.pack_type, main.Pack.TOOL)
        self.assertGreaterEqual(len(pack.options), 1)
        for option in pack.options:
            self.assertIn(option.kind, ("tool", "passive"))
            self.assertGreater(option.price, 0)

    def test_a_kept_option_joins_the_inventory(self):
        pack = self.game.shop._roll_pack(main.Pack.TOOL, main.Pack.GIGA)
        self.game.shop.items = [pack]
        self.game.ensure_board_cells()
        option = pack.options[0]

        self.game._receive_pack_item(option)

        self.assertTrue(self.game.owns_item(option))
        self.assertIn(option, self.game.toolbox.items)
