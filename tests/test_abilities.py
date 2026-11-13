"""The ABILITY table: one contract every usable item goes through.

User request: "add the ability table". An ability says what an item needs, what
it costs and which method carries it out (components.Ability), and the S key
dispatches through it (Game._use_ability) instead of growing a branch per item
kind. These tests pin the table's own shape, the derivation from an item, the
dispatcher, and the sidebar row the same table generates.
"""

from tests.game_test_case import *  # noqa: F401,F403


class AbilityTableTests(GameTestCase):
    """The table is complete, and every row it has can actually be fired."""

    def test_every_ability_has_a_full_contract(self):
        for ability in main.Ability.ORDER:
            with self.subTest(ability=main.Ability.name(ability)):
                self.assertTrue(main.Ability.name(ability))
                self.assertIn(ability, main.Ability.NEEDS)
                self.assertIn(ability, main.Ability.COSTS)
                self.assertTrue(main.Ability.cost_text(ability))
                # Every row names a Game method, and that method exists.
                handler = main.Ability.handler(ability)
                self.assertTrue(handler)
                self.assertTrue(callable(getattr(self.game, handler)))

    def test_the_order_covers_every_ability_exactly_once(self):
        rows = [main.Ability.OPEN, main.Ability.APPLY,
                main.Ability.OPEN_PACK, main.Ability.DISCARD,
                main.Ability.MODIFY]
        self.assertEqual(sorted(main.Ability.ORDER), sorted(rows))
        self.assertEqual(len(set(main.Ability.ORDER)), len(main.Ability.ORDER))

    def test_the_contract_reads_as_needs_then_cost(self):
        self.assertEqual(main.Ability.contract(main.Ability.OPEN),
                         "Needs 1 structure. Costs 1 energy.")
        self.assertEqual(main.Ability.contract(main.Ability.DISCARD),
                         "Needs 1 other item. "
                         "Costs this item and the one with it.")
        # A pack needs no target, so its line is the cost alone (never a
        # dangling "Needs .").
        self.assertEqual(main.Ability.contract(main.Ability.OPEN_PACK),
                         "Costs nothing.")
        # An action's own count is what the grammar prints. What a used card
        # spends of ITSELF is its own keyword now ("consume"), so the contract
        # names no cost of its own (user request: "make all cards homogenous").
        self.assertEqual(main.Ability.contract(main.Ability.APPLY, 2),
                         "Needs 2 targets. Costs nothing.")
        self.assertEqual(main.Ability.contract(main.Ability.APPLY, 1),
                         "Needs 1 target. Costs nothing.")

    def test_every_ability_is_reachable_from_some_item(self):
        # A row nothing can fire would be dead data: the derivation must reach
        # every ability in the table.
        samples = {
            main.Ability.OPEN: self._tool(),
            main.Ability.APPLY: main.ActionItem(main.Action.DEATH,
                                                main.Action.PRICES[main.Action.DEATH]),
            main.Ability.OPEN_PACK: self._pack(),
            main.Ability.DISCARD: self._wasteful_block(),
            main.Ability.MODIFY: main.ToolItem(main.Tool.VODKA),
        }
        self.assertEqual(sorted(samples), sorted(main.Ability.ORDER))
        for ability, item in samples.items():
            with self.subTest(ability=main.Ability.name(ability)):
                self.assertEqual(main.Ability.of(item), ability)

    # --- the items every test needs ---------------------------------------

    def _tool(self):
        return next(item for item in self.game.toolbox.items
                    if getattr(item, "kind", None) == "tool")

    def _pack(self):
        pack = main.ItemPack(main.Pack.SHAPE, main.Pack.NORMAL, [], 10)
        self.game.toolbox.add(pack)
        return pack

    def _wasteful_block(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.WASTEFUL,
                               main.Scorer.CHIPS_ADD, 0, 30, "Wasteful Rect")
        self.game.toolbox.add(block)
        self.game.ensure_board_cells()
        return block


class AbilityDerivationTests(GameTestCase):
    """An item's ability comes from the table, not from its own code."""

    def test_a_plain_item_has_no_ability(self):
        self.assertIsNone(main.Ability.of(None))
        self.assertIsNone(main.Ability.of(main.Component.shape_component(
            main.Shape.SLOPE)))
        self.assertIsNone(main.Ability.of(main.Block(0, 0)))

    def test_a_block_ability_comes_from_its_effects(self):
        block = main.Block(0, 0, effects=[main.Effect.WASTEFUL])
        self.assertEqual(main.Ability.of(block), main.Ability.DISCARD)
        bouncy = main.Block(0, 0, effects=[main.Effect.BOUNCY])
        self.assertIsNone(main.Ability.of(bouncy))


class AbilityDispatchTests(GameTestCase):
    """S goes through one dispatcher, and falls through when nothing can fire."""

    def _wasteful(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.WASTEFUL,
                               main.Scorer.CHIPS_ADD, 0, 30, "Wasteful Rect")
        self.game.toolbox.add(block)
        self.game.ensure_board_cells()
        return block

    def _spare(self):
        spare = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(spare)
        self.game.ensure_board_cells()
        return spare

    def _fill_deck(self, count=3):
        for _ in range(count):
            shape = main.Component.shape_component(main.Shape.SLOPE)
            self.game.toolbox.add(shape)
            self.game._to_deck(shape)

    def test_the_dispatcher_fires_the_wasteful_ability(self):
        block = self._wasteful()
        spare = self._spare()
        self._fill_deck()
        # Select the way the player does: the block first (it is the actor),
        # the item it throws away second.
        self._click(self._item_pos(block))
        self._click(self._item_pos(spare))

        self.assertTrue(self.game._use_ability())

        # The pair is gone and a fresh item took the block's square: the same
        # outcome the S key has always given (see _use_wasteful).
        self.assertFalse(self.game.owns_item(block))
        self.assertFalse(self.game.owns_item(spare))

    def test_the_dispatcher_leaves_s_to_assembly_when_nothing_can_fire(self):
        block = self._wasteful()          # a Wasteful block alone can do nothing
        self.game.selection = [block]
        self.assertFalse(self.game._use_ability())

        plain = main.Block(1, 1)
        self.game.selection = [plain]
        self.assertFalse(self.game._use_ability())
        self.game.selection = []
        self.assertFalse(self.game._use_ability())

    def test_an_armed_tool_keeps_the_s_press(self):
        # With a tool armed, S belongs to the tool even when no structure is
        # selected: the ability handles the press (and refuses it, spending
        # nothing) rather than falling through to assembling a block.
        tool = next(item for item in self.game.toolbox.items
                    if getattr(item, "kind", None) == "tool")
        self.game.toolbox.add(tool)
        self.game.ensure_board_cells()
        self.game.selected_tool = tool
        self.game.selection = [tool]
        energy = self.game.energy

        self.assertTrue(self.game._use_ability())

        self.assertEqual(self.game.energy, energy)      # a refusal costs nothing
        self.assertTrue(self.game.shop_message)


class AbilitySidebarTests(GameTestCase):
    """The sidebar row is generated from the table, so it cannot drift."""

    def _rows(self, item):
        return dict(self.game._describe_item(item))

    def test_a_tool_reports_the_open_ability(self):
        tool = next(item for item in self.game.toolbox.items
                    if getattr(item, "kind", None) == "tool")
        rows = self._rows(tool)
        self.assertEqual(rows["Ability - Open"],
                         "Needs 1 structure. Costs 1 energy. "
                         "Press S to use it.")

    def test_a_wasteful_block_reports_the_discard_ability(self):
        block = main.Block(0, 0, effects=[main.Effect.WASTEFUL])
        rows = self._rows(block)
        self.assertEqual(rows["Ability - Discard"],
                         "Needs 1 other item. "
                         "Costs this item and the one with it. "
                         "Press S to use it.")

    def test_a_plain_block_has_no_ability_row(self):
        labels = [label for label, _ in self.game._describe_item(main.Block(0, 0))]
        self.assertFalse([label for label in labels if label.startswith("Ability")])
