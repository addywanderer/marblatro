"""The tools beyond the four starters and the two one-shots.

User request: "add all 6 tools." They are the six the design conversation picked,
one per gap in the catalogue (see components.Tool):

    Glowstick      -- reveal, 0 energy, consumed: the free one-shot
    Pry Bar        -- dig + break, 2 energy, never spent: the two-verb tool
    Chisel         -- fix, 1 energy, consumed, AMOUNT = pack sizes up the reward
    Gilding Cloth  -- fix + reveal, 2 energy, consumed, AMOUNT = quality tiers up
    Wrecking Bar   -- break, 1 energy, consumed, takes the neighbours with it
    Multi-Tool     -- every verb, 3 energy, never spent: answers any door, once

These tests pin the table rows down and then play each tool: what it opens, what
it spends, whether it survives, and what it does to the reward.
"""

import random

from tests.game_test_case import *  # noqa: F401,F403


class ToolTableTests(GameTestCase):
    """The rows the six new tools live in."""

    NEW_TOOLS = None  # filled in setUp from components.Tool

    def setUp(self):
        super().setUp()
        tool = main.Tool
        self.NEW_TOOLS = (tool.GLOWSTICK, tool.PRY_BAR, tool.CHISEL,
                          tool.GILDING_CLOTH, tool.WRECKING_BAR, tool.MULTI_TOOL)

    def test_the_six_new_tools_are_in_the_catalogue(self):
        for value in self.NEW_TOOLS:
            with self.subTest(tool=main.Tool.name(value)):
                self.assertIn(value, main.Tool.ORDER)
                self.assertNotIn(value, main.Tool.STARTERS)
                self.assertIn(value, main.Tool.PACK_ORDER)
                self.assertTrue(main.Tool.description(value))
                self.assertTrue(main.Tool.comment(value))
                self.assertIn(value, main.Tool.COLORS)
                self.assertIn(value, main.Tool.GLYPHS)
                self.assertGreater(main.Tool.PRICES[value], 0)

    def test_the_energy_and_breadth_of_each(self):
        tool = main.Tool
        expected = {
            tool.GLOWSTICK: (0, (main.Verb.REVEAL,), True),
            tool.PRY_BAR: (2, (main.Verb.DIG, main.Verb.BREAK), False),
            tool.CHISEL: (1, (main.Verb.FIX,), True),
            tool.GILDING_CLOTH: (2, (main.Verb.FIX, main.Verb.REVEAL), True),
            tool.WRECKING_BAR: (1, (main.Verb.BREAK,), True),
            tool.MULTI_TOOL: (3, tuple(main.Verb.ORDER), False),
        }
        for value, (energy, verbs, consumes) in expected.items():
            with self.subTest(tool=tool.name(value)):
                self.assertEqual(tool.energy(value), energy)
                self.assertEqual(tool.verbs(value), verbs)
                self.assertEqual(tool.consumes(value), consumes)

    def test_the_two_amount_tools_carry_their_number(self):
        tool = main.Tool
        self.assertEqual(tool.amount(tool.CHISEL), 1)
        self.assertEqual(tool.amount(tool.GILDING_CLOTH), 1)
        for value in (tool.GLOWSTICK, tool.PRY_BAR, tool.WRECKING_BAR,
                      tool.MULTI_TOOL, tool.SHOVEL):
            self.assertEqual(tool.amount(value), 0)
        self.assertEqual(main.ToolItem(tool.CHISEL).amount, 1)
        self.assertEqual(main.ToolItem(tool.SHOVEL).amount, 0)

    def test_only_the_wrecking_bar_sweeps(self):
        for value in main.Tool.ORDER:
            with self.subTest(tool=main.Tool.name(value)):
                self.assertEqual(main.Tool.sweeps(value),
                                 value == main.Tool.WRECKING_BAR)

    def test_a_pack_size_moves_up_the_ladder_and_stops_at_the_top(self):
        tool = main.Tool
        self.assertEqual(tool.bigger_pack_size(main.Pack.NORMAL, 1),
                         main.Pack.BIG)
        self.assertEqual(tool.bigger_pack_size(main.Pack.GIGA, 1),
                         main.Pack.GIGA)
        self.assertEqual(
            tool.bigger_pack_size(main.Pack.NORMAL, 20), main.Pack.SIZE_ORDER[-1])

    def test_a_quality_moves_up_the_tiers_and_stops_at_diamond(self):
        tool = main.Tool
        self.assertEqual(tool.better_quality(main.Quality.NORMAL, 1),
                         main.Quality.GOLDEN)
        self.assertEqual(tool.better_quality(main.Quality.GOLDEN, 1),
                         main.Quality.DIAMOND)
        self.assertEqual(tool.better_quality(main.Quality.DIAMOND, 3),
                         main.Quality.DIAMOND)


class NewToolPlayTests(GameTestCase):
    """Each tool, played the way the player plays it."""

    def setUp(self):
        super().setUp()
        self.game.title_screen = False
        self.game.ensure_board_cells()
        self._start_block()

    # --- helpers ------------------------------------------------------------

    def _start_block(self):
        game = self.game
        cell = next(c for c in sorted(game.unlocked_cells)
                    if game.item_at_cell(c) is None and c not in game.grid)
        game.grid[cell] = main.Block(cell[0], cell[1], scorer=main.Scorer.START)
        return cell

    def _tool(self, value):
        tool = main.ToolItem(value)
        self.game.toolbox.add(tool)
        self.game.ensure_board_cells()
        self.assertIsNotNone(self._item_cell(tool))
        return tool

    def _structure(self, value, cell):
        """Stand a structure on a square NOBODY else claims (see Game.ensure_board_cells).

        A forced square that another item already claims is dropped by the next
        layout pass, so a test that wants to click one has to pick a square that
        is really free.
        """
        self.assertTrue(self._is_free(cell), f"{cell} is already taken")
        structure = main.StructureItem(value, main.Structure.PRICES[value])
        structure.is_level_structure = True
        self.game.toolbox.add(structure)
        self.game.set_item_cell(structure, cell)
        self.game.shop.items.append(structure)
        return structure

    def _is_free(self, cell):
        game = self.game
        return (cell in game.unlocked_cells and cell not in game.grid
                and game.item_at_cell(cell) is None)

    def _free_cell(self, away_from=()):
        """A free unlocked square (the game's own rule, see _first_free_cell)."""
        cell = self.game._first_free_cell(blocked=set(away_from))
        self.assertIsNotNone(cell, "the board has no free square")
        return cell

    def _free_cells(self, offsets):
        """Free squares laid out at the given offsets from one another."""
        game = self.game
        for cell in sorted(game.unlocked_cells):
            cells = [cell] + [(cell[0] + dx, cell[1] + dy) for dx, dy in offsets]
            if all(self._is_free(other) for other in cells):
                return cells
        self.fail("no free squares are laid out like that")

    def _use(self, tool, structure, energy=None):
        self.game._clear_toolbox_selection()
        if energy is not None:
            self.game.energy = energy
        self._click(self._item_pos(tool))
        self._click(self._item_pos(structure))
        self._press(main.pygame.K_s)

    def _structures(self):
        return [item for item in self.game.shop.items
                if getattr(item, "is_level_structure", False)]

    def _rewards(self, kind):
        if kind == "action":
            return list(self.game.actions)
        if kind == "card":
            return list(self.game.cards)
        return [item for item in self.game.toolbox.items
                if getattr(item, "kind", None) == kind]

    # --- Glowstick ----------------------------------------------------------

    def test_a_glowstick_reveals_for_no_energy_and_is_used_up(self):
        glowstick = self._tool(main.Tool.GLOWSTICK)
        library = self._structure(main.Structure.LIBRARY, self._free_cell())

        self._use(glowstick, library, energy=0)

        self.assertEqual(self.game.energy, 0)          # it cost nothing
        self.assertFalse(self.game.owns_item(glowstick))
        self.assertEqual(len(self._rewards("pack")), 1)
        self.assertNotIn(library, self._structures())

    # --- Pry bar ------------------------------------------------------------

    def test_a_pry_bar_digs_and_breaks_and_is_never_spent(self):
        pry_bar = self._tool(main.Tool.PRY_BAR)
        pit = self._structure(main.Structure.PIT, self._free_cell())
        mirror = self._structure(main.Structure.MIRROR, self._free_cell())

        self._use(pry_bar, pit, energy=2)
        self.assertEqual(self.game.energy, 0)
        self.assertTrue(self.game.owns_item(pry_bar))

        self.game.energy = 2
        self._use(pry_bar, mirror)

        self.assertEqual(len(self._rewards("action")), 1)      # Strength
        self.assertTrue(self.game.owns_item(pry_bar))

    def test_a_pry_bar_is_refused_without_its_two_energy(self):
        pry_bar = self._tool(main.Tool.PRY_BAR)
        vault = self._structure(main.Structure.VAULT, self._free_cell())

        self._use(pry_bar, vault, energy=1)

        self.assertEqual(self.game.energy, 1)
        self.assertIn(vault, self._structures())
        self.assertTrue(self.game.owns_item(pry_bar))

    # --- Multi-tool ---------------------------------------------------------

    def test_a_multi_tool_opens_any_door_for_all_three_energy(self):
        multi_tool = self._tool(main.Tool.MULTI_TOOL)
        for index, value in enumerate((main.Structure.QUARRY,
                                       main.Structure.SHRINE,
                                       main.Structure.VAULT,
                                       main.Structure.LIBRARY)):
            with self.subTest(structure=main.Structure.name(value)):
                structure = self._structure(value, self._free_cell())
                self._use(multi_tool, structure, energy=main.MAX_ENERGY)
                self.assertEqual(self.game.energy, 0)
                self.assertTrue(self.game.owns_item(multi_tool))
                self.assertNotIn(structure, self._structures())

    def test_a_multi_tool_needs_the_whole_run_s_energy(self):
        multi_tool = self._tool(main.Tool.MULTI_TOOL)
        quarry = self._structure(main.Structure.QUARRY, self._free_cell())

        self._use(multi_tool, quarry, energy=main.MAX_ENERGY - 1)

        self.assertEqual(self.game.energy, main.MAX_ENERGY - 1)
        self.assertIn(quarry, self._structures())

    # --- Chisel -------------------------------------------------------------

    def test_a_chisel_pushes_the_reward_one_pack_size_up(self):
        # The roller is pinned to the smallest size, so the only thing that can
        # move the pack up the ladder is the chisel itself.
        chisel = self._tool(main.Tool.CHISEL)
        original = random.choice
        random.choice = lambda _sizes: main.Pack.NORMAL
        try:
            plain = self.game._structure_reward("pack", main.Pack.PART, None)
            chiselled = self.game._structure_reward("pack", main.Pack.PART, chisel)
        finally:
            random.choice = original

        self.assertEqual(plain.size, main.Pack.NORMAL)
        self.assertEqual(chiselled.size, main.Pack.BIG)

    def test_a_golden_chisel_pushes_two_sizes_up(self):
        # Two chisels folded by a golem carry an amount of 2 (see
        # Game._combine_items), so the same pinned roll comes out two rungs up.
        chisel = self._tool(main.Tool.CHISEL)
        chisel.amount = 2
        original = random.choice
        random.choice = lambda _sizes: main.Pack.NORMAL
        try:
            chiselled = self.game._structure_reward("pack", main.Pack.PART, chisel)
        finally:
            random.choice = original

        self.assertEqual(chiselled.size, main.Pack.JUMBO)

    def test_a_chisel_opens_a_fix_structure_and_is_used_up(self):
        chisel = self._tool(main.Tool.CHISEL)
        shrine = self._structure(main.Structure.SHRINE, self._free_cell())

        self._use(chisel, shrine, energy=1)

        self.assertEqual(self.game.energy, 0)
        self.assertFalse(self.game.owns_item(chisel))
        packs = self._rewards("pack")
        self.assertEqual(len(packs), 1)
        self.assertGreaterEqual(packs[0].size, main.Pack.BIG)

    # --- Gilding cloth ------------------------------------------------------

    def test_a_gilding_cloth_brings_the_reward_up_a_tier(self):
        cloth = self._tool(main.Tool.GILDING_CLOTH)
        pool = self._structure(main.Structure.CRYSTAL_POOL, self._free_cell())

        self._use(cloth, pool, energy=2)

        actions = [item for item in self.game.actions
                   if item.value == main.Action.CLEANSING]
        self.assertEqual(len(actions), 1)
        self.assertEqual(main.Quality.of(actions[0]), main.Quality.GOLDEN)
        self.assertFalse(self.game.owns_item(cloth))

    def test_a_gilding_cloth_tiers_up_every_option_of_a_pack(self):
        cloth = self._tool(main.Tool.GILDING_CLOTH)
        shed = self._structure(main.Structure.SHED, self._free_cell())

        self._use(cloth, shed, energy=2)

        pack = self._rewards("pack")[0]
        self.assertTrue(pack.options)
        for option in pack.options:
            self.assertEqual(main.Quality.of(option), main.Quality.GOLDEN)

    # --- Wrecking bar -------------------------------------------------------

    def test_a_wrecking_bar_opens_the_neighbours_too(self):
        bar = self._tool(main.Tool.WRECKING_BAR)
        anchor, right, below, _further = self._free_cells(
            ((1, 0), (0, 1), (0, 2)))
        vault = self._structure(main.Structure.VAULT, anchor)
        depot = self._structure(main.Structure.DEPOT, right)
        library = self._structure(main.Structure.LIBRARY, below)

        self._use(bar, vault, energy=1)

        self.assertNotIn(vault, self._structures())
        self.assertNotIn(depot, self._structures())      # opened with it
        self.assertIn(library, self._structures())       # a reveal-only door
        self.assertEqual(len(self._rewards("pack")), 2)
        self.assertFalse(self.game.owns_item(bar))

    def test_a_wrecking_bar_leaves_a_lone_structure_alone(self):
        bar = self._tool(main.Tool.WRECKING_BAR)
        vault_cell = self._free_cell()
        vault = self._structure(main.Structure.VAULT, vault_cell)
        far_cell = self._free_cell(away_from=(
            vault_cell, (vault_cell[0] + 1, vault_cell[1]),
            (vault_cell[0] - 1, vault_cell[1]),
            (vault_cell[0], vault_cell[1] + 1),
            (vault_cell[0], vault_cell[1] - 1)))
        far = self._structure(main.Structure.DEPOT, far_cell)

        self._use(bar, vault, energy=1)

        self.assertIn(far, self._structures())
        self.assertEqual(len(self._rewards("pack")), 1)

    def test_a_swept_structure_is_spent_for_the_level_too(self):
        bar = self._tool(main.Tool.WRECKING_BAR)
        _anchor, right, below = self._free_cells(((1, 0), (0, 1)))
        vault = self._structure(main.Structure.VAULT, right)
        depot = self._structure(main.Structure.DEPOT, below)

        self._use(bar, vault, energy=1)
        self.game.reset_run(False)

        self.assertNotIn(vault, self._structures())
        self.assertNotIn(depot, self._structures())

    # --- the collection, the icon and the save ------------------------------

    def test_every_new_tool_is_a_collection_entry_and_has_an_icon(self):
        self.game._unlock_entire_collection()
        names = {name for kind, value, name, desc, icon, seen
                 in self.game._collection_entries() if kind == "tool"}
        for value in (main.Tool.GLOWSTICK, main.Tool.PRY_BAR, main.Tool.CHISEL,
                      main.Tool.GILDING_CLOTH, main.Tool.WRECKING_BAR,
                      main.Tool.MULTI_TOOL):
            with self.subTest(tool=main.Tool.name(value)):
                self.assertIn(main.Tool.name(value), names)
                self.assertIsNotNone(main.ui._tool_art(value))

    def test_a_tool_s_amount_rides_through_a_save(self):
        chisel = self._tool(main.Tool.CHISEL)
        chisel.amount = 2
        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)
        kept = [item for item in fresh.hand_items()
                if getattr(item, "kind", None) == "tool"
                and item.value == main.Tool.CHISEL]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].amount, 2)

    def test_the_sidebar_states_what_a_tools_amount_does(self):
        chisel = self._tool(main.Tool.CHISEL)
        rows = dict(self.game._describe_item(chisel))
        self.assertIn("Magnitude", rows)
        self.assertIn("pack size", rows["Magnitude"])

        bar = self._tool(main.Tool.WRECKING_BAR)
        rows = dict(self.game._describe_item(bar))
        self.assertIn("Sweep", rows)

    def test_the_golem_folds_two_chisels_and_not_two_glowsticks(self):
        chisel = main.ToolItem(main.Tool.CHISEL)
        self.assertEqual(self.game._item_magnitudes(chisel), {("amount",): 1})
        glowstick = main.ToolItem(main.Tool.GLOWSTICK)
        self.assertEqual(self.game._item_magnitudes(glowstick), {})
