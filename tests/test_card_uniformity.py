"""Every card is a card: one family, one info box, one way of reading it.

User requests:

* "when hovering over an item in the collection, show the same pop-up info box
  as when the player hovers over the same item in a real game";
* "make all cards homogenous, and treat them the same way: for example, give all
  original cards (such as joker, explorer, inferno, doppelganger, etc.) the
  keyword 'unplayable' because that is how they behave. give all cards that used
  to be actions the keyword 'consume' because that is how they behave. make sure
  everything a card does is shown in its info box, using keywords or other
  explanatory mechanisms: since the implications of calling an item an 'action'
  or 'tool' have been removed, make their descriptions match this change."

The three kinds that make up the Cards family — a whole card, an action and a
tool — are read out by one info box (see Game._describe_item), labelled the same
way ("Card - <name>"), and told apart by their KEYWORDS (see
components.Keyword.of) rather than by the noun their kind happens to carry.
"""

from tests.game_test_case import *  # noqa: F401,F403


def _whole_cards():
    """Every whole card id: the catalogue's own, then the match-group cards."""
    return list(main.Card.ORDER) + list(main.match_group_card_values())


def _actions():
    return list(main.Action.ORDER)


def _tools():
    return list(main.Tool.ORDER)


class CardKeywordTests(GameTestCase):
    """What the three kinds of card say about themselves."""

    def test_every_whole_card_is_unplayable(self):
        # A whole card is never used: it pays on its own (user request: "give
        # all original cards ... the keyword 'unplayable' because that is how
        # they behave"). That covers the named cards, the utility cards and
        # every card built on a match group.
        for value in _whole_cards():
            with self.subTest(card=main.Card.name(value)):
                item = main.CardItem(value, main.Card.PRICES.get(value, 20))
                self.assertEqual(main.Keyword.of(item),
                                 (main.Keyword.UNPLAYABLE,))
                self.assertEqual(main.Keyword.line(item), "unplayable")
                # ...and it has no ability at all, which is what the word means.
                self.assertIsNone(main.Ability.of(item))

    def test_every_action_is_consumed(self):
        # User request: "give all cards that used to be actions the keyword
        # 'consume' because that is how they behave."
        for value in _actions():
            with self.subTest(action=main.Action.name(value)):
                item = main.ActionItem(value, main.Action.PRICES.get(value, 24))
                self.assertEqual(main.Keyword.of(item),
                                 (main.Keyword.CONSUME,))
                self.assertEqual(main.Keyword.line(item), "consume")

    def test_a_reusable_action_says_reusable_instead(self):
        # The modifier still wins the argument (see components.Keyword.of): the
        # two words are opposites and a reusable card is not destroyed.
        item = main.ActionItem(main.Action.DEATH,
                               main.Action.PRICES[main.Action.DEATH])
        main.Modifier.add(item, main.Modifier.REUSABLE, 1)
        self.assertEqual(main.Keyword.of(item), (main.Keyword.REUSABLE,))

    def test_a_tool_still_reads_its_verbs_and_which_way_it_goes(self):
        for value in _tools():
            with self.subTest(tool=main.Tool.name(value)):
                item = main.ToolItem(value, main.Tool.PRICES.get(value, 0))
                words = main.Keyword.of(item)
                verbs = [main.Keyword.for_verb(verb)
                         for verb in main.Tool.verbs(value)]
                self.assertEqual(list(words[:len(verbs)]), verbs)
                if main.Tool.opens_structures(value) or main.Tool.modifies(value):
                    self.assertIn(
                        main.Keyword.REUSABLE if not main.Tool.consumes(value)
                        else main.Keyword.CONSUME, words)

    def test_the_unplayable_word_covers_whole_cards_too(self):
        meaning = main.Keyword.description(main.Keyword.UNPLAYABLE).lower()
        self.assertIn("cannot be used", meaning)
        self.assertIn("card", meaning)


class CardInfoBoxTests(GameTestCase):
    """One box for all three kinds: same label, same words, same extras."""

    def _rows(self, item):
        return dict(self.game._describe_item(item))

    def test_every_card_is_labelled_a_card(self):
        # "make all cards homogenous, and treat them the same way": the row that
        # names the item is the same for all three kinds, and what tells them
        # apart is the keywords below it.
        cases = [
            (main.CardItem(main.Card.JOKER, 24), "Joker"),
            (main.ActionItem(main.Action.EYEBALL, 28), "Eyeball"),
            (main.ToolItem(main.Tool.SHOVEL, 0), "Shovel"),
        ]
        for item, name in cases:
            with self.subTest(name=name):
                labels = [label for label, _ in self.game._describe_item(item)]
                self.assertEqual(labels[0], f"Card - {name}")
                self.assertIn("Keywords", labels)

    def test_a_whole_card_states_its_keyword_and_when_it_fires(self):
        item = main.CardItem(main.Card.JOKER, 24)
        rows = self._rows(item)
        self.assertEqual(rows["Keywords"], "unplayable")
        self.assertIn("Cannot be used", rows["Passive"])
        self.assertIn("start of every run", rows["Timing"])

    def test_every_whole_card_says_when_it_acts(self):
        # Nothing a card does is left to the word "card" to imply: a measured
        # card fires at the start or the end of a run (or on a fragile break), a
        # match-group card fires on a collision, and every other whole card is
        # always on.
        for value in _whole_cards():
            with self.subTest(card=main.Card.name(value)):
                rows = self._rows(main.CardItem(value,
                                                main.Card.PRICES.get(value, 20)))
                self.assertIn("Timing", rows)
                self.assertTrue(rows["Timing"])
                self.assertNotIn("action", rows["Timing"].lower())
        self.assertIn("collides", self._rows(
            main.CardItem(main.match_group_card(main.MATCH_GROUPS[0],
                                                main.CARD_SCORERS[0]), 20)
        )["Timing"])

    def test_an_action_states_what_using_it_costs_it(self):
        rows = self._rows(main.ActionItem(main.Action.EYEBALL, 28))
        self.assertEqual(rows["Keywords"], "consume")
        self.assertIn("Destroyed", rows["Consume"])
        # The energy it asks for is the contract's business; the card spending
        # ITSELF is the keyword's, so the contract does not say it again.
        self.assertIn("Costs 1 energy.", rows["Ability - Apply"])
        self.assertNotIn("the action itself", rows["Ability - Apply"])

    def test_a_tool_states_its_keywords_energy_and_contract(self):
        rows = self._rows(main.ToolItem(main.Tool.SHOVEL, 0))
        self.assertEqual(rows["Keywords"], "dig, reusable")
        self.assertIn("Energy", rows)
        self.assertIn("Costs 1 energy.", rows["Ability - Open"])

    def test_every_card_in_the_box_wears_a_face(self):
        # The mini face at the top of the box was a card's and an action's; a
        # tool wears one too now, so all three read the same way.
        for item in (main.CardItem(main.Card.JOKER, 24),
                     main.ActionItem(main.Action.EYEBALL, 28),
                     main.ToolItem(main.Tool.SHOVEL, 0)):
            with self.subTest(kind=item.kind):
                self.assertEqual(main.ui.info_face_height(item), 62)
        self.assertEqual(main.ui.info_face_height(main.BlockItem(
            0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
            10, 20, "Rect +Chips")), 0)

    def test_no_card_text_calls_itself_an_action(self):
        # "since the implications of calling an item an 'action' or 'tool' have
        # been removed, make their descriptions match this change": the words
        # belong to the comments that explain the code, not to the text a player
        # reads.
        for value in _actions():
            for version in (1, 2):
                with self.subTest(action=main.Action.name(value), version=version):
                    text = main.Action.description(value, version).lower()
                    self.assertNotIn("this action", text)
                    self.assertNotIn("an action", text)

    def test_the_ability_cost_is_the_energy_alone(self):
        # What a used card spends of itself is its keyword ("consume"), so the
        # table's own cost for applying a card is nothing.
        self.assertEqual(main.Ability.COSTS[main.Ability.APPLY], "nothing")
        self.assertEqual(main.Ability.contract(main.Ability.APPLY, 1),
                         "Needs 1 target. Costs nothing.")


class CodexHoverTests(GameTestCase):
    """The codex shows the very box the item gets in a game."""

    def setUp(self):
        super().setUp()
        self.game._unlock_entire_collection()
        self.game.collection_open = True
        self.game.collection_scroll = 0

    def _entries(self):
        return self.game._collection_entries()

    def _index_of(self, kind, value):
        return next(index for index, entry in enumerate(self._entries())
                    if entry[0] == kind and entry[1] == value)

    def _cell(self, index):
        """The screen rect of a codex cell, as the page is scrolled right now."""
        cell = main.ui.collection_entry_rect(index)
        cell.y -= self.game.collection_scroll
        return cell

    def test_the_cursor_reads_the_entry_under_it(self):
        index = self._index_of("card", main.Card.JOKER)
        cell = self._cell(index)

        entry = self.game.collection_entry_at(cell.center)

        self.assertEqual(entry[:2], ("card", main.Card.JOKER))
        self.assertTrue(entry[5], "the entry is discovered")

    def test_the_page_scrolls_the_hit_test_with_it(self):
        index = self._index_of("tool", main.Tool.SHOVEL)
        cell = main.ui.collection_entry_rect(index)
        # Before scrolling, the cell is far below the page...
        self.assertGreater(cell.top, main.SCREEN_HEIGHT)
        self.game.collection_scroll = max(0, cell.top - 200)
        scrolled = self._cell(index)
        # ...so the cursor reads the shovel only because the page moved.
        self.assertEqual(self.game.collection_entry_at(scrolled.center)[:2],
                         ("tool", main.Tool.SHOVEL))
        self.game.collection_scroll = 0
        entry = self.game.collection_entry_at(scrolled.center)
        self.assertNotEqual(entry[:2] if entry else None,
                            ("tool", main.Tool.SHOVEL))

    def test_the_heading_and_the_button_row_are_not_cells(self):
        top = main.ui.COLLECTION_HOVER_TOP
        bottom = main.SCREEN_HEIGHT - main.ui.COLLECTION_HOVER_BOTTOM
        for y in (4, top - 1, bottom + 1, main.SCREEN_HEIGHT - 4):
            with self.subTest(y=y):
                self.assertIsNone(self.game.collection_entry_at(
                    (main.SCREEN_WIDTH // 2, y)))

    def test_every_entry_that_is_an_item_builds_one(self):
        # A card, an action, a tool, a part, a passive, a structure and a pack
        # are all items; a match group stands for its cards; a trial is a way to
        # play a run rather than an item, so it has no box.
        kinds = {entry[0] for entry in self._entries()}
        for kind in sorted(kinds):
            with self.subTest(kind=kind):
                entry = next(e for e in self._entries() if e[0] == kind)
                item = self.game._collection_entry_item(entry)
                if kind == "trial":
                    self.assertIsNone(item)
                else:
                    self.assertIsNotNone(item, f"a {kind} entry has no item")
                    self.assertTrue(self.game._describe_item(item))

    def test_the_box_is_the_same_one_the_game_shows(self):
        # The same item, read the way the board reads it: the codex turns each
        # entry into the item it lists, so the rows (and the words) cannot
        # differ from the box the player sees in a game.
        cases = [
            ("card", main.Card.JOKER,
             main.CardItem(main.Card.JOKER, main.Card.PRICES[main.Card.JOKER])),
            ("action", main.Action.EYEBALL,
             main.ActionItem(main.Action.EYEBALL,
                             main.Action.PRICES[main.Action.EYEBALL])),
            ("tool", main.Tool.SHOVEL,
             main.ToolItem(main.Tool.SHOVEL,
                           main.Tool.PRICES[main.Tool.SHOVEL])),
            ("passive", main.Passive.CONCRETE,
             main.PassiveItem(main.Passive.CONCRETE,
                              main.Passive.PRICES[main.Passive.CONCRETE])),
            ("structure", main.Structure.PIT,
             main.StructureItem(main.Structure.PIT, 0)),
        ]
        for kind, value, in_game in cases:
            with self.subTest(kind=kind):
                entry = self._entries()[self._index_of(kind, value)]
                codex = self.game._collection_entry_item(entry)
                self.assertEqual(self.game._describe_item(codex),
                                 self.game._describe_item(in_game))
                self.assertEqual(self.game._item_name(codex),
                                 self.game._item_name(in_game))

    def test_hovering_a_cell_draws_the_box(self):
        index = self._index_of("card", main.Card.JOKER)
        cell = self._cell(index)
        self.game.collection_scroll = 0
        with mock.patch("main.pygame.mouse.get_pos", return_value=cell.center):
            with mock.patch.object(self.game, "_draw_item_info") as draw:
                self.game.draw()
        self.assertEqual(draw.call_count, 1)
        item, source, pos = draw.call_args[0]
        self.assertEqual((source, pos), ("collection", cell.center))
        self.assertEqual(getattr(item, "kind", None), "card")
        self.assertEqual(item.value, main.Card.JOKER)

    def test_a_locked_cell_draws_nothing(self):
        # An undiscovered entry has no name, no text and no item yet (see
        # _collection_entries), so the box would leak what the codex is hiding:
        # the page draws nothing for it.
        index = self._index_of("card", main.Card.JOKER)
        cell = self._cell(index)
        entry = self._entries()[index]
        self.assertTrue(entry[5], "the entry is discovered in this game")
        locked = [tuple(entry[:5]) + (False,)]
        with mock.patch.object(self.game, "_collection_entries",
                               return_value=locked):
            with mock.patch("main.pygame.mouse.get_pos",
                            return_value=cell.center):
                with mock.patch.object(self.game, "_draw_item_info") as draw:
                    self.game.draw()
        self.assertEqual(draw.call_count, 0)

    def test_the_codex_hint_says_what_the_page_is(self):
        entry = self._entries()[self._index_of("card", main.Card.JOKER)]
        item = self.game._collection_entry_item(entry)
        hint = self.game._action_hint(item, "collection")
        self.assertIn("Codex entry", hint)
        self.assertIn("scroll", hint)


class EveryCardThatSpendsOrOpensTests(GameTestCase):
    """The readouts beside the cards name every card the rules involve."""

    def test_the_energy_readout_names_every_card_that_spends_it(self):
        # Energy is not a tool's currency any more (the implications of the
        # noun are gone): the bar says so in words, and names the actions that
        # ask for it as well as the tools.
        spent_by = dict(self.game._energy_rows())["Spent by"]
        self.assertIn("shovel", spent_by)
        for value in main.Action.ORDER:
            if main.Action.energy(value):
                self.assertIn(main.Action.name(value), spent_by)

    def test_a_structures_opened_by_row_names_the_actions_too(self):
        # A structure's own row listed only the tools, so a card that can open
        # one — Dynamite or Stormcloud — was a way in the player could not read
        # about.
        pit = dict(self.game._describe_item(
            main.StructureItem(main.Structure.PIT, 0)))
        self.assertIn("Shovel", pit["Opened by"])
        self.assertIn("Dynamite", pit["Opened by"])
        self.assertIn("Stormcloud", pit["Opened by"])
        # A mirror answers fix and break: the storm opens it, the dynamite
        # (which only digs or reveals) does not.
        mirror = dict(self.game._describe_item(
            main.StructureItem(main.Structure.MIRROR, 0)))
        self.assertIn("Stormcloud", mirror["Opened by"])
        self.assertNotIn("Dynamite", mirror["Opened by"])

    def test_the_opens_table_is_what_the_handlers_read(self):
        self.assertEqual(main.Action.opens_with(main.Action.DYNAMITE),
                         (main.Verb.DIG, main.Verb.REVEAL))
        self.assertEqual(main.Action.opens_with(main.Action.STORMCLOUD),
                         (main.Verb.BREAK, main.Verb.FIX, main.Verb.DIG,
                          main.Verb.REVEAL))
        # An action that opens nothing says so, rather than raising.
        self.assertEqual(main.Action.opens_with(main.Action.DEATH), ())
