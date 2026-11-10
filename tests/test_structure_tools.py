"""Structures and tools: the bugs the player found, pinned down.

The three user reports, in the user's own words:
  "tools can sometimes disappear if the player places a structure on a tool";
  "if the player unlocks a structure using a tool, and then moves the tool, the
   structure will revert itself back into a locked state";
  "when the player presses t, the level sometimes resets".

Each is a test class below, plus the icon work ("give each structure an icon")
and the smaller bugs found while fixing them.
"""

import save_system

from tests.game_test_case import *  # noqa: F401,F403


class StructureCase(GameTestCase):
    """A brand-new game with the level already laid out, and the ways to touch it."""

    def setUp(self):
        super().setUp()
        save_system.start_new_game_in_slot(self.game, 1)
        self.game.title_screen = False
        self.game.trials_enabled = False
        self.game.ensure_board_cells()
        self._start_block()

    # --- the board ----------------------------------------------------------

    def _start_block(self):
        """A Start block, so a run can actually be started."""
        g = self.game
        cell = next(c for c in sorted(g.unlocked_cells)
                    if g.item_at_cell(c) is None and c not in g.grid)
        block = main.Block(cell[0], cell[1], scorer=main.Scorer.START)
        g.grid[cell] = block
        return block

    def _structures(self):
        return [item for item in self.game.shop.items
                if getattr(item, "is_level_structure", False)]

    def _structure_cells(self):
        return sorted(self.game.item_cell(item) for item in self._structures())

    def _cells_of(self, kind):
        return sorted(self.game.item_cell(item) for item in self.game.toolbox.items
                      if getattr(item, "kind", None) == kind)

    def _tool(self, verb):
        return next(item for item in self.game.toolbox.items
                    if getattr(item, "kind", None) == "tool" and item.verb == verb)

    def _free_cell(self):
        g = self.game
        return next(c for c in sorted(g.unlocked_cells)
                    if g.item_at_cell(c) is None and c not in g.grid)

    def _open(self, structure, verb=None):
        """Open a structure the player's way: click the tool, click it, press S.

        The selection is cleared first, because a click on an armed tool turns it
        OFF (every item has one switch — see Game._toggle_item_selection), so
        opening two structures in a row needs a clean start.
        """
        verb = verb if verb is not None else main.Structure.verbs(structure.value)[0]
        tool = self._tool(verb)
        self.game._clear_toolbox_selection()
        self.game.energy = 99
        self._click(self._item_pos(tool))
        self._click(self._item_pos(structure))
        self._press(main.pygame.K_s)
        return tool

    def _level_layout(self):
        """Everything the LEVEL put on the board: props, structures, enemies."""
        g = self.game
        props = sorted(c for c, b in g.grid.items() if getattr(b, "is_level_prop", False))
        enemies = sorted((c, b.kind) for c, b in g.grid.items() if getattr(b, "is_enemy", False))
        return props, self._structure_cells(), enemies


class ToolsStayInHandTests(StructureCase):
    """Moving an item onto another one never drops it out of the hand.

    User report: "tools can sometimes disappear if the player places a structure
    on a tool."
    """

    def test_moving_a_structure_onto_a_tool_swaps_them(self):
        structure = self._structures()[0]
        tool = self._tool(main.Verb.REVEAL)
        tool_cell, structure_cell = self._item_cell(tool), self._item_cell(structure)

        self.assertTrue(self.game._move_item_to(structure, *tool_cell))

        self.assertEqual(self._item_cell(structure), tool_cell)
        self.assertEqual(self._item_cell(tool), structure_cell)   # the swap
        self.assertIsNotNone(self._item_cell(tool), "the tool lost its square")

    def test_the_tool_is_still_the_players_and_still_usable(self):
        structure = self._structures()[0]
        tool = self._tool(main.Verb.DIG)

        self.game._move_item_to(structure, *self._item_cell(tool))

        self.assertTrue(self.game.owns_item(tool))
        self.assertTrue(self.game.toolbox.contains(tool))
        self.assertIsNotNone(self._item_cell(tool))
        self.assertEqual(tool, self._tool(main.Verb.DIG))

    def test_moving_a_card_onto_a_tool_swaps_them_too(self):
        card = main.CardItem(main.Card.ORDER[0], 20)
        self.game._adopt_card(card)
        self.game.ensure_board_cells()
        tool = self._tool(main.Verb.FIX)
        card_cell, tool_cell = self._item_cell(card), self._item_cell(tool)

        self.game._move_item_to(card, *tool_cell)

        self.assertEqual(self._item_cell(card), tool_cell)
        self.assertEqual(self._item_cell(tool), card_cell)

    def test_building_a_block_on_a_tool_seats_the_tool_elsewhere(self):
        tool = self._tool(main.Verb.FIX)
        tool_cell = self._item_cell(tool)
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "Rect +Chips")
        self.game.toolbox.add(block)
        self.game.ensure_board_cells()
        self.game._equip_block(block)

        self.game._place_block_at(*tool_cell)

        self.assertIn(tool_cell, self.game.grid)            # the block went down
        self.assertIsNotNone(self._item_cell(tool))         # ...and the tool stayed
        self.assertNotEqual(self._item_cell(tool), tool_cell)
        self.assertTrue(self.game.owns_item(tool))

    def test_an_item_standing_where_the_level_puts_a_structure_steps_aside(self):
        # A save does not store the level's structures -- the level puts them
        # back when it is laid out -- so a load can find one of the player's own
        # items standing on the square the plan claims. That item steps aside; it
        # is not pushed into the deck (a tool that vanished was the report).
        structure = self._structures()[0]
        planned = self._item_cell(structure)
        tool = self._tool(main.Verb.DIG)
        self.game._move_item_to(tool, *planned)
        self.game.shop.items.remove(structure)
        self.game.set_item_cell(structure, None)
        self.game._forget_item(structure)

        self.game._place_level_structures(self.game.current_level())

        self.assertIsNotNone(self._item_cell(tool))
        self.assertNotEqual(self._item_cell(tool), planned)
        self.assertIn(planned, self._structure_cells())

    def test_no_item_is_in_the_deck_after_a_round_of_moves(self):
        # Every tool the player owns is on the board: none of them may be pushed
        # into the deck by another item being placed on its square.
        before = {id(item) for item in self.game.hand_items()}
        for _ in range(4):
            structure = self._structures()[0]
            tool = self._tool(main.Verb.DIG)
            self.game._move_item_to(structure, *self._item_cell(tool))
            self.game.ensure_board_cells()

        after = {id(item) for item in self.game.hand_items()}
        self.assertEqual(after, before)
        self.assertEqual(self.game.deck_items(), [])

    def test_a_tool_stays_on_the_board_across_a_save_and_load(self):
        # The hand -- not the deck -- is what stands on the board, so every tool
        # the hand held before the save must be seated again after the load, even
        # where the level re-places a structure underneath one of them.
        structure = self._structures()[0]
        tool = self._tool(main.Verb.DIG)
        self.game._move_item_to(structure, *self._item_cell(tool))
        before = len([item for item in self.game.hand_items()
                      if getattr(item, "kind", None) == "tool"])

        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)

        seated = [item for item in fresh.hand_items()
                  if getattr(item, "kind", None) == "tool"]
        self.assertEqual(len(seated), before)
        for item in seated:
            self.assertIsNotNone(fresh.item_cell(item),
                                 "a tool came back from the save with no square")
        self.assertEqual([item for item in fresh.deck_items()
                          if getattr(item, "kind", None) == "tool"], [])

    def test_a_displaced_item_lands_on_the_first_free_square_when_it_has_nowhere_to_go(self):
        # An item that has no square of its own (just gained, still in the deck)
        # cannot swap: the one it lands on is seated, never dropped.
        occupant = self._tool(main.Verb.BREAK)
        occupant_cell = self._item_cell(occupant)
        newcomer = main.StructureItem(main.Structure.LIBRARY, 0)
        self.game.shop.items.append(newcomer)      # an offer, with no square yet

        self.assertTrue(self.game._seat_aside(occupant, (0, 0)))

        self.assertIsNotNone(self._item_cell(occupant))
        self.assertNotEqual(self._item_cell(occupant), occupant_cell)


class SpentStructuresTests(StructureCase):
    """A structure the player opens stays opened for the level visit.

    User report: "if the player unlocks a structure using a tool, and then moves
    the tool, the structure will revert itself back into a locked state."
    """

    def _open_one(self):
        structure = self._structures()[0]
        cell = self._item_cell(structure)
        self._open(structure)
        return cell

    def test_opening_a_structure_spends_it(self):
        cell = self._open_one()

        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN - 1)
        self.assertIn(cell, {entry[1:] for entry in self.game.spent_structures})

    def test_moving_the_tool_does_not_bring_the_structure_back(self):
        cell = self._open_one()
        tool = self._tool(main.Verb.DIG)

        self.game._move_item_to(tool, *self._free_cell())          # a board edit
        self.game.reset_run(False)                                 # ...resolves the run

        self.assertNotIn(cell, self._structure_cells())
        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN - 1)

    def test_pressing_r_does_not_bring_it_back(self):
        cell = self._open_one()

        self._press(main.pygame.K_r)

        self.assertNotIn(cell, self._structure_cells())

    def test_pressing_t_does_not_bring_it_back(self):
        cell = self._open_one()

        self._press(main.pygame.K_t)

        self.assertNotIn(cell, self._structure_cells())
        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN - 1)

    def test_unlocking_a_square_does_not_bring_it_back(self):
        cell = self._open_one()
        self.game.board_units = 1
        locked = next(c for c in sorted(
            (x, y) for x in range(main.GRID_WIDTH) for y in range(main.GRID_HEIGHT))
            if self.game.is_cell_locked(*c))

        self.game._unlock_cell(*locked)
        self.game.reset_run(False)

        self.assertNotIn(cell, self._structure_cells())

    def test_every_structure_opened_stays_opened(self):
        for structure in list(self._structures()):
            self._open(structure)

        self.assertEqual(self._structures(), [])
        self._press(main.pygame.K_t)
        self._press(main.pygame.K_r)
        self.assertEqual(self._structures(), [])

    def test_a_spent_structure_survives_a_save_and_load(self):
        cell = self._open_one()

        fresh = main.Game()
        save_system._load_save_data(fresh, save_system._save_data(self.game), 1)

        fresh_cells = [fresh.item_cell(item) for item in fresh.shop.items
                       if getattr(item, "is_level_structure", False)]
        self.assertNotIn(cell, fresh_cells)
        self.assertEqual(len(fresh_cells), main.STRUCTURES_PER_RUN - 1)

    def test_the_next_level_gets_its_own_four(self):
        self._open_one()
        self._open(self._structures()[0])

        self.game.run_number += 1
        self.game._refresh_run_target()
        self.game._begin_level()

        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN)
        self.assertEqual(self.game.spent_structures, set())

    def test_a_new_game_gets_four_fresh_structures(self):
        self._open_one()

        save_system.start_new_game_in_slot(self.game, 1)

        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN)
        self.assertEqual(self.game.spent_structures, set())


class TheLevelDoesNotResetTests(StructureCase):
    """Starting a run leaves the level exactly as the player left it."""

    def test_pressing_t_changes_nothing_but_the_marble(self):
        before = self._level_layout()
        items = sorted((id(item), self._item_cell(item)) for item in self.game.owned_items())

        self._press(main.pygame.K_t)

        self.assertEqual(self._level_layout(), before)
        self.assertEqual(
            sorted((id(item), self._item_cell(item)) for item in self.game.owned_items()),
            items)
        self.assertEqual(len(self.game.marbles), 1)

    def test_a_structure_the_player_moved_stays_where_they_put_it(self):
        structure = self._structures()[0]
        home = self._free_cell()
        self.game._move_item_to(structure, *home)

        self._press(main.pygame.K_t)
        self._press(main.pygame.K_r)

        self.assertEqual(self._item_cell(structure), home)
        self.assertEqual(sorted(self._structure_cells()), sorted(
            [self._item_cell(item) for item in self._structures()]))

    def test_a_structure_moved_away_from_its_plan_is_not_duplicated(self):
        structure = self._structures()[0]
        home = self._free_cell()
        self.game._move_item_to(structure, *home)

        self.game.reset_run(False)

        cells = self._structure_cells()
        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN)
        self.assertEqual(len(set(cells)), len(cells))     # nobody shares a square
        self.assertIn(home, cells)                        # it stayed where it was put

    def test_the_enemies_are_still_put_back_on_their_own_squares(self):
        # The level is only kept where it stands: a fresh run still heals its
        # cast (that is what a retry undoes), it just does not RE-DECIDE it.
        self.game.reset_run()
        enemy = self.game.live_enemies()[0]
        home = (enemy.x, enemy.y)
        enemy.hp = 1
        enemy.float_x += 20.0

        self.game.reset_run()

        back = self.game.grid[home]
        self.assertEqual(back.hp, back.max_hp)
        self.assertEqual(back.float_x, float(back.home_x))


class StructureOpeningTests(StructureCase):
    """The bookkeeping around opening one: reward, spent square, repeat use."""

    def test_the_reward_takes_the_structures_square(self):
        structure = self._structures()[0]
        cell = self._item_cell(structure)

        self._open(structure)

        packs = [item for item in self.game.owned_items()
                 if getattr(item, "kind", None) == "pack"]
        self.assertEqual(len(packs), 1)
        self.assertEqual(self._item_cell(packs[0]), cell)

    def test_the_spent_square_is_the_one_the_reward_took(self):
        structure = self._structures()[0]
        cell = self._item_cell(structure)

        self._open(structure)

        self.assertIn((structure.value, cell[0], cell[1]),
                      self.game.spent_structures)

    def test_a_structure_opened_on_its_new_square_is_spent_there(self):
        structure = self._structures()[0]
        new_home = self._free_cell()
        self.game._move_item_to(structure, *new_home)

        self._open(structure)
        self.game.reset_run(False)

        self.assertNotIn(new_home, self._structure_cells())
        self.assertIn((structure.value, new_home[0], new_home[1]),
                      self.game.spent_structures)

    def test_a_spent_structure_cannot_be_opened_twice(self):
        structure = self._structures()[0]
        self._open(structure)

        for _ in range(3):
            self._press(main.pygame.K_s)
            self._press(main.pygame.K_s)

        packs = [item for item in self.game.owned_items()
                 if getattr(item, "kind", None) == "pack"]
        self.assertEqual(len(packs), 1)
        self.assertEqual(len(self._structures()), main.STRUCTURES_PER_RUN - 1)

    def test_opening_every_structure_does_not_cost_the_player_a_tool(self):
        for structure in list(self._structures()):
            self._open(structure)

        tools = [item for item in self.game.toolbox.items
                 if getattr(item, "kind", None) == "tool"]
        self.assertEqual(len(tools), 4)
        for tool in tools:
            self.assertIsNotNone(self._item_cell(tool))

    def test_opening_one_structure_leaves_the_other_three(self):
        first = self._structures()[0]
        others = [self._item_cell(item) for item in self._structures()[1:]]

        self._open(first)

        self.assertEqual(self._structure_cells(), sorted(others))


class StructureIconTests(StructureCase):
    """Every structure wears an icon of its own (user request)."""

    def _tile(self, value, inset=0):
        surface = main.pygame.Surface((main.GRID_SIZE + 2 * inset,
                                      main.GRID_SIZE + 2 * inset))
        surface.fill((0, 0, 0))
        rect = main.pygame.Rect(inset, inset, main.GRID_SIZE, main.GRID_SIZE)
        main.ui.draw_structure(surface, main.StructureItem(value, 0), rect)
        return surface, rect

    def test_every_structure_draws_an_icon(self):
        for value in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(value)):
                surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
                drawn = main.ui._draw_structure_icon(
                    surface, value,
                    main.pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE))
                self.assertTrue(drawn, "no icon art for this structure")

    def test_no_two_structures_look_the_same(self):
        fingerprints = {}
        for value in main.Structure.ORDER:
            surface, _rect = self._tile(value)
            fingerprints[main.Structure.name(value)] = self._pixel_hash(surface)
        self.assertEqual(len(set(fingerprints.values())), len(fingerprints))

    def test_the_icon_is_drawn_inside_the_tile_and_nowhere_else(self):
        for value in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(value)):
                surface, rect = self._tile(value, inset=6)
                outside = [(x, y)
                           for x in range(surface.get_width())
                           for y in range(surface.get_height())
                           if not rect.collidepoint(x, y)]
                self.assertTrue(all(tuple(surface.get_at(pos))[:3] == (0, 0, 0)
                                    for pos in outside))

    def test_the_icon_marks_the_tile_rather_than_leaving_it_plain(self):
        for value in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(value)):
                surface, rect = self._tile(value)
                base = main.Structure.COLORS[value]
                marked = sum(
                    1
                    for x in range(rect.left + 2, rect.right - 2)
                    for y in range(rect.top + 2, rect.bottom - 2)
                    if tuple(surface.get_at((x, y)))[:3] != base)
                self.assertGreater(marked, 60)      # a drawn icon, not a blank tile

    def test_a_known_structure_never_falls_back_to_its_glyph(self):
        # The glyph is only the fallback for a value with no art (an old save):
        # every structure the game ships must have art of its own.
        for value in main.Structure.ORDER:
            with self.subTest(structure=main.Structure.name(value)):
                self.assertTrue(
                    main.ui._draw_structure_icon(
                        main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE)),
                        value,
                        main.pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)))
