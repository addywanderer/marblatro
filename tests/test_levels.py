"""LEVELS, enemies, and the per-marble score.

A run is a LEVEL now (see components.LEVELS): its goal is the enemies standing
on the board, not a score target, and every marble carries its own chips and
mult so a block's scorer only ever pays the marble that touched it.
"""

from tests.game_test_case import *  # noqa: F401,F403


class LevelCase(GameTestCase):
    def _start_level(self, run_number=0, fresh=True):
        """Start a real run whose level is ``run_number``'s.

        ``fresh`` locks the board down first, so the level's own squares (and
        anything it buries in the wall) start from an empty board; a campaign
        test passes fresh=False so the levels accumulate the way they do in play.
        """
        if fresh:
            self.game.unlocked_cells = set()
        self.game.run_number = run_number
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.grid[(0, 10)] = main.Block(0, 10, scorer=main.Scorer.FINISH)
        self.assertTrue(self.game.reset_run(False))
        return self.game.current_level()

    def _finish_marbles(self):
        for marble in self.game.marbles:
            marble.finished = True
        self.game._handle_block_contacts([])


class LevelTests(LevelCase):
    """A run's level: its squares, its structures and its enemies."""

    def test_a_run_plays_its_own_level(self):
        level = self._start_level(3)
        self.assertEqual(level.number, 4)
        self.assertEqual(self.game.level_number, 4)
        self.assertEqual(level.name, "Crystal Shore")

    def test_every_level_has_its_own_set(self):
        # The user's "each level has a different set of structures and enemies":
        # no two levels deal the same cast and the same structures.
        casts = {(tuple(level.enemies), tuple(level.structures))
                 for level in main.LEVELS}
        self.assertGreater(len(casts), 12)
        self.assertEqual(len(main.LEVELS), main.TOTAL_RUNS)

    def test_enemies_stand_where_their_level_puts_them(self):
        # Every enemy has its own square, so a level decides exactly where its
        # cast stands: level 16 puts one at the very top and one at the very
        # bottom of its tower.
        self._start_level(15)
        level = self.game.current_level()
        spots = {(enemy.x, enemy.y) for enemy in self.game.live_enemies()}
        self.assertEqual(len(spots), level.enemy_count)
        rows = {dy for _, _, dy in level.enemy_spawns}
        self.assertEqual(min(rows), -5)
        self.assertEqual(max(rows), 5)

    def test_a_levels_enemies_sit_in_its_own_areas(self):
        # Different levels put their cast in different places: level 17's five
        # enemies stand in four corner rooms and the middle, so most of them are
        # outside the arena level 1 uses.
        self._start_level(16)
        level = self.game.current_level()
        self.assertEqual(level.enemy_count, 5)
        arena = {(main.GRID_WIDTH // 2 + dx, main.GRID_HEIGHT // 2 + dy)
                 for dx in range(-3, 4) for dy in range(-2, 3)}
        spots = {(enemy.x, enemy.y) for enemy in self.game.live_enemies()}
        self.assertGreaterEqual(len(spots - arena), 4)
        self._start_level(0)
        first = {(enemy.x, enemy.y) for enemy in self.game.live_enemies()}
        self.assertNotEqual(spots, first)

    def test_a_moving_enemy_stays_on_unlocked_squares(self):
        # A patrol is penned in by its room: it may travel its row, but never
        # onto a locked square.
        self._start_level(1)          # level 2: arena plus an east wing
        enemy = main.Enemy(0, 0, main.EnemyKind.PATROL)
        home = sorted(self.game.unlocked_cells)[0]
        enemy.home_x = enemy.float_x = home[0] * main.GRID_SIZE + main.MARBLE_BOX_COORDS[0]
        enemy.home_y = enemy.float_y = home[1] * main.GRID_SIZE + main.MARBLE_BOX_COORDS[1]
        enemy.rect.topleft = (int(enemy.float_x), int(enemy.float_y))
        for _ in range(400):
            enemy.step(0.1, [], self.game.unlocked_cells)
            self.assertIn(enemy.cell_at(enemy.float_x, enemy.float_y),
                          self.game.unlocked_cells)

    def test_a_fleeing_enemy_stays_on_unlocked_squares(self):
        self._start_level(0)
        enemy = main.Enemy(0, 0, main.EnemyKind.FLEE)
        spot = sorted(self.game.unlocked_cells)[10]
        enemy.float_x = float(spot[0] * main.GRID_SIZE + main.MARBLE_BOX_COORDS[0])
        enemy.float_y = float(spot[1] * main.GRID_SIZE + main.MARBLE_BOX_COORDS[1])
        enemy.rect.topleft = (int(enemy.float_x), int(enemy.float_y))
        marble = self.game.marbles[0]
        marble.position = np.array([float(enemy.rect.centerx) - 4.0,
                                    float(enemy.rect.centery)])
        for _ in range(200):
            enemy.step(0.1, [marble], self.game.unlocked_cells)
            self.assertIn(enemy.cell_at(enemy.float_x, enemy.float_y),
                          self.game.unlocked_cells)

    def test_a_level_lays_out_its_enemies(self):
        level = self._start_level()
        enemies = self.game.live_enemies()
        self.assertEqual(len(enemies), level.enemy_count)
        self.assertEqual(
            sorted(enemy.kind for enemy in enemies),
            sorted(level.enemies))
        for enemy in enemies:
            self.assertIs(self.game.grid[(enemy.x, enemy.y)], enemy)

    def _opened(self, level):
        """The squares a level opens from an empty board."""
        self.game.unlocked_cells = set()
        self.game._open_level_region(level.cells)
        return set(self.game.unlocked_cells)

    def test_each_level_pre_unlocks_its_own_squares(self):
        # The user's "make each level have different board squares be
        # pre-unlocked": no two levels open the same set of squares.
        layouts = [frozenset(self._opened(level)) for level in main.LEVELS]
        self.assertEqual(len(set(layouts)), len(main.LEVELS))

    def test_every_level_opens_about_the_same_number_of_squares(self):
        # The user's "the levels should all be about the same size in terms of
        # number of unlocked board squares": the areas sit in a narrow band.
        areas = [len(level.cells) for level in main.LEVELS]
        self.assertLessEqual(max(areas) - min(areas), 12)
        self.assertGreaterEqual(min(areas), 44)

    def test_a_levels_squares_can_be_several_separate_areas(self):
        # Shapes matter, not just size: level 17 opens four corner rooms joined
        # by thin corridors, so its squares fill far less than the rectangle
        # around them, and level 12 opens two rooms with a gap between.
        for index in (16, 11):
            with self.subTest(level=main.LEVELS[index].number):
                level = main.LEVELS[index]
                self.assertLess(len(level.cells), level.size[0] * level.size[1])
        two_rooms = main.LEVELS[11]
        self.assertEqual(sorted({dy for _, _, dy, _, _ in two_rooms.parts}), [-2])

    def test_a_level_opens_its_squares_without_closing_anything(self):
        # A level only ever UNLOCKS squares: a square already open (an earlier
        # level's, a bought Board Unit's) stays open.
        self.game.unlocked_cells = {(0, 0)}
        self.game._open_level_region(main.LEVELS[0].cells)
        small = set(self.game.unlocked_cells)
        self.game._open_level_region(main.LEVELS[-1].cells)
        big = set(self.game.unlocked_cells)
        self.assertGreater(len(big), len(small))
        self.assertTrue(small <= big)
        self.assertIn((0, 0), big)

    def test_the_shelf_sells_nothing_any_more(self):
        # User request: "add structures as part of the level. remove the
        # remaining shop items (packs generated each run)". A fresh game's shelf
        # is empty, and a level's shelf holds only the structures that level put
        # on its own squares -- never a pack.
        self.assertEqual(self.game.shop.items, [])
        level = self._start_level(0)
        kinds = {getattr(item, "kind", None) for item in self.game.shop.items}
        self.assertEqual(kinds, {"structure"})
        self.assertEqual(len(self.game.shop.items), len(level.structure_spawns))

    def test_a_levels_structures_are_its_own(self):
        # Each level puts its OWN structures out (see components.Level), so no
        # two levels offer the same set of things to open.
        sets = {level.number: tuple(sorted(level.structures)) for level in main.LEVELS}
        self.assertGreater(len(set(sets.values())), 1)
        for level in main.LEVELS:
            with self.subTest(level=level.number):
                self.assertEqual(len(level.structure_spawns), len(level.structures))
                for value, dx, dy in level.structure_spawns:
                    self.assertIn(value, main.Structure.ORDER)
                    self.assertIn((dx, dy), level.cells)

class LevelHealthBudgetTests(LevelCase):
    """A level's health IS the score its run used to require.

    User request: "make the sum of all enemies' health equal to the total
    required score that was originally there before the system was changed to
    enemies." The old target is still computed for every run (the schedule, as
    its trial scales it), and the level's enemies always add up to it exactly.
    """

    def test_a_levels_enemies_add_up_to_its_runs_old_score(self):
        for run_number in (0, 2, 9, 16, 23):
            with self.subTest(run=run_number + 1):
                target = main.get_next_required_score(run_number,
                                                      self.game.score_growth)
                self.game.required_score = target
                self._start_level(run_number)
                enemies = self.game.live_enemies()
                self.assertTrue(enemies)
                self.assertEqual(sum(enemy.max_hp for enemy in enemies), target)

    def test_the_split_follows_the_kinds_shares(self):
        # The shares (components.ENEMY_HP_SHARE) decide HOW the level's health
        # is divided; the level only decides the total, so every level asks for
        # the whole of its own old target however many enemies it holds.
        level = main.LEVELS[-1]                     # eight enemies, five kinds
        health = level.enemy_health(840_000)
        self.assertEqual(sum(health), 840_000)
        self.assertEqual(len(health), level.enemy_count)
        by_kind = {}
        for kind, amount in zip(level.enemies, health):
            by_kind.setdefault(kind, []).append(amount)
        self.assertGreater(by_kind[main.EnemyKind.DEVOURER][0],
                           by_kind[main.EnemyKind.IDLE][0])

    def test_a_level_with_no_target_still_puts_up_a_fight(self):
        # Grace v2 sets a run's target to 0; the enemies are then worth almost
        # nothing, but they are still there to be hit.
        self.game.required_score = 0
        self._start_level(11)                       # level 12: four enemies
        enemies = self.game.live_enemies()
        self.assertEqual(len(enemies), self.game.current_level().enemy_count)
        self.assertEqual([enemy.max_hp for enemy in enemies], [1, 1, 1, 1])

    def test_a_doubled_target_is_a_doubled_level(self):
        # Sky High doubles the run's required score, so the level it plays asks
        # for twice the damage: one number drives both.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SKY_HIGH
        self.game.run_number = 4
        self.game._refresh_run_target()
        self._start_level(4)
        base = main.get_next_required_score(4, self.game.score_growth)
        self.assertEqual(self.game.required_score, base * 2)
        total = sum(enemy.max_hp for enemy in self.game.live_enemies())
        self.assertEqual(total, base * 2)

    def test_the_last_level_asks_for_the_original_final_target(self):
        # The end of the game is the end of the old schedule, not a number
        # invented for the levels: 100 doubled 23 times.
        level = main.LEVELS[-1]
        self.assertEqual(level.enemy_health(100 * 2 ** 23).__len__(),
                         level.enemy_count)
        self.assertEqual(sum(level.enemy_health(100 * 2 ** 23)), 838860800)

    def test_an_enemy_reads_its_health_off_the_level_it_stands_in(self):
        # The board's enemies are the level's budget, split -- not a fixed per
        # kind number that never grows.
        self.game.required_score = 5000
        self._start_level(6)                        # level 7: two enemies
        self.assertEqual(sum(enemy.max_hp
                             for enemy in self.game.live_enemies()), 5000)
        self.game.required_score = 100
        self._start_level(6)
        self.assertEqual(sum(enemy.max_hp
                             for enemy in self.game.live_enemies()), 100)

    def test_an_enemy_writes_its_health_into_the_sidebar(self):
        self.game.required_score = 8_400_000
        self._start_level(0)                        # level 1: one enemy
        enemy = self.game.live_enemies()[0]
        rows = dict(self.game._describe_item(enemy))
        self.assertEqual(rows["Health"], "8.4M of 8.4M left")


class StructureOfferingTests(LevelCase):
    """Every run puts out four structures (user request: "have 4 structures
    each run instead of 1")."""

    def _structures(self, run_number=0):
        self.game.unlocked_cells = set()
        self.game.run_number = run_number
        level = self.game.current_level()
        self.game._open_level_region(level.cells)
        self.game._place_level_structures(level)
        return level, [item for item in self.game.shop.items
                       if getattr(item, "is_level_structure", False)]

    def test_every_level_offers_four_structures(self):
        self.assertEqual(main.STRUCTURES_PER_RUN, 4)
        for level in main.LEVELS:
            with self.subTest(level=level.number):
                self.assertEqual(len(level.structures), 4)
                self.assertEqual(len(level.structure_spawns), 4)
                cells = {(dx, dy) for _, dx, dy in level.structure_spawns}
                self.assertEqual(len(cells), 4)

    def test_a_levels_structures_repeat_its_own_kinds(self):
        # A level authors the kinds that suit it, and the plan cycles them up to
        # the four a run lays out: a level with four or fewer authored kinds
        # plans exactly those, and one that authors more (the last level authors
        # every structure in the game) plans the first four of them.
        for level in main.LEVELS:
            with self.subTest(level=level.number):
                self.assertTrue(set(level.structures)
                                <= set(level.authored_structures))
                if len(level.authored_structures) <= main.STRUCTURES_PER_RUN:
                    self.assertEqual(set(level.structures),
                                     set(level.authored_structures))
        level = main.LEVELS[2]                      # pit, pool, pit, pool
        self.assertEqual(tuple(level.authored_structures),
                         (level.structures[0], level.structures[1]))

    def test_a_run_lays_out_all_four(self):
        level, structures = self._structures(0)
        self.assertEqual(len(structures), 4)
        self.assertEqual(sorted(item.value for item in structures),
                         sorted(level.structures))
        self.assertEqual(len({self.game.item_cell(item)
                              for item in structures}), 4)

    def test_a_structure_keeps_out_of_the_levels_own_scenery(self):
        # Four structures need four squares, and never an enemy's or a prop's.
        for level in main.LEVELS:
            with self.subTest(level=level.number):
                cells = {(dx, dy) for _, dx, dy in level.structure_spawns}
                self.assertFalse({(dx, dy) for _, dx, dy in level.enemy_spawns}
                                 & cells)
                self.assertFalse({(dx, dy) for _, dx, dy in level.props} & cells)

    def test_a_levels_structures_stand_where_the_level_puts_them(self):
        # User request: "make structures be placed in different areas of the
        # level, instead of always at the top." The structure's BOARD SQUARE is
        # the one its level picked: col/row are the shelf's drawing cells, and an
        # item with no board square is laid out by the next layout pass in
        # reading order -- which is the top of the board.
        level, structures = self._structures(0)
        spawns = [self.game._level_cell(dx, dy)
                  for _, dx, dy in level.structure_spawns]
        self.assertEqual([self.game.item_cell(item) for item in structures],
                         spawns)
        rows = {cell[1] for cell in spawns}
        self.assertGreater(max(rows) - min(rows), 1)     # spread, not one row

    def test_no_level_lines_its_structures_up_at_the_top(self):
        # Every level's lowest structure reaches its own bottom half, so the
        # offer is never a row of scenery along the top edge.
        for level in main.LEVELS:
            with self.subTest(level=level.number):
                rows = sorted({dy for _, _, dy in level.structure_spawns})
                span = sorted({cell[1] for cell in level.cells})
                self.assertGreaterEqual(rows[-1], span[len(span) // 2])
                self.assertLessEqual(rows[0], span[len(span) // 2])

    def test_a_taken_square_does_not_shrink_the_offer(self):
        # The board is the inventory, so the player's own items can already be
        # standing where a structure was going to go. The structure moves to the
        # free square nearest its own instead of being skipped, so the run still
        # gets its four.
        self.game.run_number = 0
        level = self.game.current_level()
        self.game.unlocked_cells = set()
        self.game._open_level_region(level.cells)
        _value, dx, dy = level.structure_spawns[0]
        cell = self.game._level_cell(dx, dy)
        self.game.grid[cell] = main.Block(cell[0], cell[1])

        self.game._place_level_structures(level)

        structures = [item for item in self.game.shop.items
                      if getattr(item, "is_level_structure", False)]
        self.assertEqual(len(structures), 4)
        self.assertNotIn(cell, {self.game.item_cell(item)
                                for item in structures})
        # ...and it does not take an enemy's square instead: an enemy pushed off
        # the board would take its share of the level's health with it.
        enemy_cells = {self.game._level_cell(dx, dy)
                       for _, dx, dy in level.enemy_spawns}
        self.assertFalse(enemy_cells & {self.game.item_cell(item)
                                        for item in structures})


class LevelBlockOwnershipTests(LevelCase):
    """The level's own blocks are never the player's."""

    def _player_blocks(self):
        return [item for item in self.game.owned_items()
                if isinstance(item, main.BlockItem)]

    def _finish_and_continue(self):
        for enemy in self.game.live_enemies():
            self.game._defeat_enemy(enemy)
        for marble in self.game.marbles:
            marble.finished = True
        self.game._handle_block_contacts([])
        self.assertTrue(self.game.run_complete)
        self.game._continue_run()

    def test_a_levels_blocks_do_not_join_the_deck_after_a_run(self):
        # The end-of-run sweep used to refund a BlockItem for every block on the
        # board, and the level's props and enemies are blocks: a wall pillar or
        # a Slime turned up in the player's deck after every run (user report:
        # "blocks that are part of the level are added to the deck after the end
        # of the run").
        self._start_level(1)                  # level 2: wall props and enemies
        self.assertTrue(any(getattr(block, "is_level_prop", False)
                            for block in self.game.grid.values()))
        self.assertTrue(self.game.live_enemies())
        before = len(self._player_blocks())

        self._finish_and_continue()

        self.assertEqual(len(self._player_blocks()), before)

    def test_a_levels_enemies_do_not_join_the_deck_either(self):
        self._start_level(9)                  # level 10: pits, props and enemies
        before = len(self._player_blocks())
        self._finish_and_continue()
        self.assertEqual(len(self._player_blocks()), before)

    def test_the_next_level_still_has_its_own_blocks(self):
        # ...and the player's deck is not the only thing untouched: the level
        # that comes next still lays out its own props and enemies.
        self._start_level(1)
        self._finish_and_continue()
        level = self.game.current_level()
        props = [block for block in self.game.grid.values()
                 if getattr(block, "is_level_prop", False)]
        self.assertEqual(len(props), len(level.props))
        self.assertEqual(len(self.game.live_enemies()), level.enemy_count)


class LevelPropTests(LevelCase):
    """The blocks a level places for itself: walls, bouncers, accelerators."""

    def _props(self):
        return [(cell, block) for cell, block in self.game.grid.items()
                if getattr(block, "is_level_prop", False)]

    def test_a_level_places_its_own_props(self):
        level = self._start_level(1)          # level 2: two wall pillars
        self.assertEqual(level.number, 2)
        props = self._props()
        self.assertEqual(len(props), len(level.props))
        for cell, block in props:
            self.assertIn(cell, self.game.unlocked_cells)
            self.assertEqual(block.scorer, main.Scorer.NONE)

    def test_a_prop_cannot_be_selected_or_taken_up(self):
        self._start_level(1)
        cell, prop = self._props()[0]
        held = len(self.game.owned_items())
        self._click(self._grid_pos(*cell))
        self.assertFalse(self.game.selection)
        self.assertFalse(self.game._erase_block_at(*cell))
        # The level's prop is still standing there, and the player gained
        # nothing by clicking it: it is scenery, not inventory.
        self.assertTrue(getattr(self.game.grid[cell], "is_level_prop", False))
        self.assertEqual(len(self.game.owned_items()), held)

    def test_a_prop_comes_back_every_run(self):
        self._start_level(1)
        cell, _prop = self._props()[0]
        del self.game.grid[cell]
        self.game.reset_run(False)
        self.assertIn(cell, self.game.grid)
        self.assertTrue(getattr(self.game.grid[cell], "is_level_prop", False))

    def test_the_levels_use_the_whole_prop_vocabulary(self):
        # Every marker a level may use is used by at least one level, so the
        # props really are level furniture rather than decoration on one board.
        used = {marker for level in main.LEVELS for marker, _, _ in level.props}
        for marker in ("w", "o", "^", "x", "/", "-", "k", "l"):
            with self.subTest(prop=marker):
                self.assertIn(marker, used)
        self.assertEqual(used, set(main.PROP_PARTS))

    def test_an_accelerator_prop_pushes_the_way_it_points(self):
        self._start_level(6)                  # level 7 climbs with "^" blocks
        level = self.game.current_level()
        ups = [(dx, dy) for marker, dx, dy in level.props if marker == "^"]
        self.assertTrue(ups)
        for dx, dy in ups:
            block = self.game.grid[self.game._level_cell(dx, dy)]
            vector = block.get_acceleration
            self.assertLess(vector[1], 0)     # upward


class BuriedEnemyTests(LevelCase):
    """An enemy inside the wall: unreachable until its square is opened."""

    def _buried(self, level):
        return [(kind, dx, dy) for kind, dx, dy in level.enemy_spawns
                if level.is_buried(dx, dy)]

    def test_two_levels_bury_an_enemy_in_the_wall(self):
        buried = {level.number: self._buried(level)
                  for level in main.LEVELS if self._buried(level)}
        self.assertIn(10, buried)
        self.assertIn(12, buried)
        for number, spawns in buried.items():
            for kind, dx, dy in spawns:
                self.assertIn(kind, main.EnemyKind.ORDER)

    def test_a_buried_enemy_is_still_in_the_wall_when_its_level_starts(self):
        # The levels only ever UNLOCK squares, so a buried enemy only stays
        # buried if its square was never opened by an earlier level: this walks
        # the campaign to prove the Deep Pits ones are.
        for run_number in range(10):
            self._start_level(run_number, fresh=(run_number == 0))
        level = self.game.current_level()
        self.assertEqual(level.number, 10)
        buried = self._buried(level)
        self.assertTrue(buried)
        for _kind, dx, dy in buried:
            cell = self.game._level_cell(dx, dy)
            self.assertNotIn(cell, self.game.unlocked_cells)
            self.assertIn(cell, self.game.grid)
            self.assertTrue(self.game.grid[cell].is_enemy)

    def test_opening_the_square_makes_the_buried_enemy_hittable(self):
        self._start_level(9)                  # level 10
        level = self.game.current_level()
        _kind, dx, dy = self._buried(level)[0]
        cell = self.game._level_cell(dx, dy)
        enemy = self.game.grid[cell]
        marble = self.game.marbles[0]
        marble.chips = 1000
        marble.mult = 1
        self.game.unlocked_cells.add(cell)
        self.game._board_walls_dirty = True

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertFalse(enemy.alive)
        self.assertNotIn(cell, self.game.grid)


class EnemyTests(LevelCase):
    """The marble fights an enemy: its score is the damage, and it is spent."""

    def test_an_enemy_hit_deals_the_marble_score_as_damage(self):
        self._start_level()
        enemy = self.game.live_enemies()[0]
        marble = self.game.marbles[0]
        marble.chips = 100
        marble.mult = 3

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertEqual(enemy.hp, enemy.max_hp - 300)

    def test_an_enemy_hit_halves_the_marble_chips_and_mult(self):
        # User request: "make the score halve chips and halve score on collision
        # with an enemy instead of setting both to 0."
        self._start_level()
        enemy = self.game.live_enemies()[0]
        marble = self.game.marbles[0]
        marble.chips = 40
        marble.mult = 2

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertEqual((marble.chips, marble.mult), (20, 1))
        # ...so the marble keeps half of what it had built, and the NEXT blow
        # lands for a quarter of what this one dealt.
        self.assertGreater(marble.chips * marble.mult, 0)

    def test_the_blow_is_worth_the_whole_score_it_halved(self):
        # The damage is chips x mult BEFORE the halving, so the enemy takes
        # exactly what the marble was worth when it hit.
        self._start_level()
        enemy = self.game.live_enemies()[0]
        marble = self.game.marbles[0]
        marble.chips = 40
        marble.mult = 2
        before = enemy.hp

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertAlmostEqual(enemy.hp, before - 80)

    def test_a_dead_enemy_leaves_the_board(self):
        self._start_level()
        enemy = self.game.live_enemies()[0]
        marble = self.game.marbles[0]
        marble.chips = 1000
        marble.mult = 1

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertFalse(enemy.alive)
        self.assertNotIn((enemy.x, enemy.y), self.game.grid)
        self.assertEqual(self.game.live_enemies(), [])
        self.assertEqual(self.game.enemies_defeated, 1)

    def test_an_enemy_never_scores_for_the_marble(self):
        self._start_level()
        enemy = self.game.live_enemies()[0]
        marble = self.game.marbles[0]
        marble.chips = 0
        marble.mult = 0

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertEqual((marble.chips, marble.mult), (0, 0))
        self.assertEqual(enemy.hp, enemy.max_hp)

    def test_an_armoured_enemy_only_takes_its_hits(self):
        self._start_level()
        enemy = main.Enemy(0, 0, main.EnemyKind.ARMOURED)
        self.game.grid[(0, 0)] = enemy
        marble = self.game.marbles[0]
        for _ in range(main.ARMOURED_HITS + 2):
            marble.chips = 10
            marble.mult = 1
            marble.collisions_this_tick = [enemy]
            self.game._handle_block_contacts([enemy])
        # Three hits landed (30 damage); the fourth and fifth did nothing.
        self.assertEqual(enemy.hp, enemy.max_hp - 30)

    def test_a_devourer_swallows_the_marble(self):
        self._start_level()
        enemy = main.Enemy(0, 0, main.EnemyKind.DEVOURER)
        self.game.grid[(0, 0)] = enemy
        marble = self.game.marbles[0]
        marble.chips = 10
        marble.mult = 1

        marble.collisions_this_tick = [enemy]
        self.game._handle_block_contacts([enemy])

        self.assertNotIn(marble, self.game.marbles)

    def test_a_patrolling_enemy_slides_along_its_row(self):
        self._start_level()
        enemy = main.Enemy(4, 4, main.EnemyKind.PATROL)
        self.game.grid[(4, 4)] = enemy
        start = enemy.rect.x
        enemy.step(0.5, [])
        self.assertGreater(enemy.rect.x, start)
        self.assertEqual(enemy.rect.y, enemy.home_y)

    def test_a_coward_runs_from_the_marble(self):
        self._start_level()
        enemy = main.Enemy(8, 4, main.EnemyKind.FLEE)
        self.game.grid[(8, 4)] = enemy
        marble = self.game.marbles[0]
        marble.position = np.array([enemy.rect.centerx - 30.0,
                                    float(enemy.rect.centery)])
        start = enemy.rect.x
        enemy.step(0.5, [marble])
        self.assertGreater(enemy.rect.x, start)

    def test_an_enemy_is_drawn_in_its_own_colour(self):
        self._start_level()
        enemy = self.game.live_enemies()[0]
        self.game.draw()
        pixel = self.game.screen.get_at(
            (enemy.rect.centerx, enemy.rect.centery))[:3]
        self.assertEqual(pixel, enemy.color)

    def test_an_enemy_is_not_selectable_or_buyable(self):
        self._start_level()
        enemy = self.game.live_enemies()[0]
        self.assertFalse(self.game.shop.is_offer(enemy))
        self.assertFalse(self.game.owns_item(enemy))


class PerMarbleScoreTests(LevelCase):
    """Two marbles on the board each keep their own chips and mult."""

    def test_a_block_scorer_pays_only_the_marble_that_touched_it(self):
        block = main.Block(3, 3, scorer=main.Scorer.CHIPS_ADD, scorer_amount=35)
        self.game.grid[(3, 3)] = block
        self.game.run_active = True
        first = self._add_marble((100, 100))
        second = self._add_marble((200, 200))

        first.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])

        self.assertEqual(first.chips, 35)
        self.assertEqual(second.chips, 0)

    def test_the_readout_follows_the_marble_being_scored(self):
        block = main.Block(3, 3, scorer=main.Scorer.MULT_ADD, scorer_amount=6)
        self.game.grid[(3, 3)] = block
        self.game.run_active = True
        self._add_marble((100, 100))
        second = self._add_marble((200, 200))
        second.mult = 1

        second.collisions_this_tick = [block]
        self.game._handle_block_contacts([block])

        self.assertEqual(self.game.score_mult, 7)

    def test_a_split_copy_carries_its_parent_score(self):
        self._start_level()
        splitter = main.Block(5, 5, effects=[main.Effect.SPLITTER])
        self.game.grid[(5, 5)] = splitter
        marble = self.game.marbles[0]
        marble.chips = 60
        marble.mult = 3

        marble.collisions_this_tick = [splitter]
        self.game._handle_block_contacts([splitter])

        self.assertEqual(len(self.game.marbles), 2)
        copy = self.game.marbles[1]
        self.assertEqual((copy.chips, copy.mult), (60, 3))

    def test_the_run_total_adds_up_the_marbles(self):
        self._start_level()
        marble = self.game.marbles[0]
        marble.chips = 10
        marble.mult = 2
        before = self.game._compute_total_score()
        copy = self._add_marble((120, 120))
        copy.chips = 10
        copy.mult = 2
        self.assertGreater(self.game._compute_total_score(), before)


class LevelOutcomeTests(LevelCase):
    """A level is won by clearing its enemies and getting every marble home."""

    def test_a_level_with_enemies_left_is_not_cleared(self):
        self._start_level()
        self.game.score_total = 10 ** 9
        self._finish_marbles()

        self.assertTrue(self.game.run_complete)
        self.assertFalse(self.game.run_cleared)
        self.assertEqual(self.game.failed_runs, 1)

    def test_a_cleared_level_needs_no_score(self):
        self._start_level()
        for enemy in self.game.live_enemies():
            self.game._defeat_enemy(enemy)
        marble = self.game.marbles[0]
        marble.chips = 0
        marble.mult = 0
        self._finish_marbles()

        self.assertTrue(self.game.run_cleared)
        self.assertEqual(self.game.runs_cleared, 1)

    def test_y_gives_up_on_a_level_and_counts_it_as_lost(self):
        self._start_level()
        self.assertTrue(self.game._give_up_level())

        self.assertFalse(self.game.run_active)
        self.assertTrue(self.game.awaiting_after_run)
        self.assertEqual(self.game.failed_runs, 1)
        self.assertEqual(self.game.run_results, [False])

    def test_three_lost_levels_end_the_game(self):
        for run in range(3):
            self._start_level(run)
            self.game._give_up_level()
            if run < 2:
                self.game._continue_run()
            else:
                # The third loss ends the game as soon as the run is committed.
                self.game._continue_run()

        self.assertEqual(self.game.failed_runs, 3)
        self.assertTrue(self.game.game_over)

    def test_retry_takes_back_a_given_up_level(self):
        self._start_level()
        self.game._give_up_level()
        self.game._retry_run()

        self.assertEqual(self.game.failed_runs, 0)
        self.assertEqual(self.game.run_results, [])
        self.assertFalse(self.game.awaiting_after_run)
