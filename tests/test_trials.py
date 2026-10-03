"""Trials: the run-wide modifiers.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


class NewTrialTests(GameTestCase):
    """The second batch of trials and the reworked Deal breaker.

    X-ray, Phantom, Vertigo and Elephant join the fifteen original trials, the
    Shuffled trial really turns the cards over, Marble weight is narrowed to the
    effects that DRIVE the marble, and Deal breaker becomes a board gag.
    """

    def _run_under(self, trial, randrange=0):
        """Start a run under ``trial`` and return its released marble.

        The run is started for real (the start block sits in the marble box, so
        reset_run releases a marble into it) with the trial's draw patched, the
        same setup the Marble weight test uses.
        """
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = trial
        with mock.patch("main.random.randrange", return_value=randrange):
            self.game._apply_trial()
        self.game.reset_run(False)
        return self.game.marbles[0]

    def _fingerprint(self):
        """A short fingerprint of one drawn frame (see _pixel_hash)."""
        self.game.draw()
        return self._pixel_hash(self.game.screen)

    def test_x_ray_trial_hides_the_marble_and_its_trail(self):
        marble = self._run_under(main.Trial.X_RAY)
        self.game.trail_particles.append(
            main.TrailParticle(marble.position[0], marble.position[1], 4.0,
                               main.MARBLE_COLOR))
        hidden = self._fingerprint()
        # A frame of an X-ray run is IDENTICAL to a frame the marble and its
        # trail were never in: the trial hides both and hides nothing else.
        self.game.marbles = []
        self.game.trail_particles = []
        nothing = self._fingerprint()
        self.assertEqual(hidden, nothing)
        # With the trial switched off the very same marble IS drawn, so the
        # hiding is the trial's doing and not something else about the frame.
        self.game.trials_enabled = False
        self.game.marbles = [marble]
        self.assertNotEqual(self._fingerprint(), nothing)

    def test_phantom_trial_starts_the_marble_phased_for_one_second(self):
        marble = self._run_under(main.Trial.PHANTOM)
        self.assertAlmostEqual(marble.phase_timer, main.PHANTOM_PHASE_SECONDS)
        self.assertAlmostEqual(main.PHANTOM_PHASE_SECONDS, 1.0)
        # Phasing means no collisions: the marble falls straight through a solid
        # wall it starts right on top of.
        wall = main.Block(5, 6, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        marble.position = np.array([float(wall.rect.centerx),
                                    float(wall.rect.top - main.MARBLE_RADIUS)])
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(30):
            marble.physics.update(marble, main.DT, [wall])
        self.assertGreater(marble.position[1], wall.rect.bottom,
                           "a phantom marble did not pass through the wall")
        self.assertGreater(marble.phase_timer, 0.0)
        # ...and once the second is up the marble is solid again: the same fall
        # now lands on the wall instead of going through it.
        for _ in range(40):
            marble.physics.update(marble, main.DT, [wall])
        self.assertEqual(marble.phase_timer, 0.0)
        marble.position = np.array([float(wall.rect.centerx),
                                    float(wall.rect.top - main.MARBLE_RADIUS)])
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(30):
            marble.physics.update(marble, main.DT, [wall])
        self.assertLess(marble.position[1], wall.rect.bottom,
                        "the marble was still phasing after its second was up")

    def test_elephant_trial_starts_the_marble_at_double_size(self):
        marble = self._run_under(main.Trial.ELEPHANT)
        self.assertAlmostEqual(marble.radius, main.MARBLE_RADIUS * 2)
        # A run with no trial is the ordinary size: it is the trial, not the
        # marble type, that doubles it.
        plain = self._run_under(None)
        self.assertAlmostEqual(plain.radius, main.MARBLE_RADIUS)

    def test_vertigo_trial_rolls_a_direction_that_is_never_straight_down(self):
        # Every compass direction but down (the default gravity already pulls
        # that way, so "randomised" would mean nothing there).
        self.assertNotIn((0.0, 1.0), main.VERTIGO_DIRECTIONS)
        self.assertGreater(len(main.VERTIGO_DIRECTIONS), 3)
        marble = self._run_under(main.Trial.VERTIGO)
        self.assertEqual(self.game.trial_gravity_dir, main.VERTIGO_DIRECTIONS[0])
        self.assertEqual(marble.base_gravity_dir, main.VERTIGO_DIRECTIONS[0])
        # Gravity really pulls that way: a marble left alone moves along the
        # rolled direction, and not one pixel the other way.
        direction = np.array(self.game.trial_gravity_dir, dtype=float)
        start = marble.position.copy()
        for _ in range(10):
            marble.physics.update(marble, main.DT, [])
        delta = marble.position - start
        self.assertGreater(float(np.dot(delta, direction)), 0.0)
        across = np.array([direction[1], -direction[0]])
        self.assertAlmostEqual(float(np.dot(delta, across)), 0.0, delta=1e-3)

    def test_vertigo_direction_is_decided_once_for_the_run(self):
        self._run_under(main.Trial.VERTIGO)
        first = self.game.trial_gravity_dir
        # Re-applying the run's trial replays the DECIDED direction (a restart
        # or a retry must not reroll it): the patched draw would answer
        # differently if the direction rolled again.
        with mock.patch("main.random.randrange", return_value=4):
            self.game._apply_trial()
        self.assertEqual(self.game.trial_gravity_dir, first)

    def test_shuffled_trial_turns_every_card_face_over(self):
        cards = [main.CardItem(main.Card.COUPON, 40),
                 main.CardItem(main.Card.JOKER, 40)]
        self.game.cards = list(cards)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SHUFFLED
        self.game._apply_trial()
        self.assertTrue(all(card.flipped for card in self.game.cards))
        # The flip is a real one: a flipped card is drawn as its own face turned
        # upside down (drawn to its own surface and rotated as one piece, so the
        # art, the rarity border and the corners all turn over together)...
        rect = pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)
        cards[0].flipped = False
        upright = pygame.Surface(rect.size)
        main.draw_card(upright, cards[0], rect)
        cards[0].flipped = True
        flipped = pygame.Surface(rect.size)
        main.draw_card(flipped, cards[0], rect)
        self.assertEqual(pygame.image.tostring(flipped, "RGB"),
                         pygame.image.tostring(
                             pygame.transform.rotate(upright, 180), "RGB"))
        # ...and it is visible (the Joker's glyph is not symmetric).
        cards[1].flipped = False
        joker_up = pygame.Surface(rect.size)
        main.draw_card(joker_up, cards[1], rect)
        cards[1].flipped = True
        joker_flipped = pygame.Surface(rect.size)
        main.draw_card(joker_flipped, cards[1], rect)
        self.assertNotEqual(pygame.image.tostring(joker_flipped, "RGB"),
                            pygame.image.tostring(joker_up, "RGB"))
        # An upright card draws exactly as it always did...
        cards[0].flipped = False
        again = pygame.Surface(rect.size)
        main.draw_card(again, cards[0], rect)
        self.assertEqual(pygame.image.tostring(again, "RGB"),
                         pygame.image.tostring(upright, "RGB"))
        # ...and the flip is a HANDICAP only: the card still fires.
        self.assertFalse(self.game._card_disabled(cards[0]))
        # A new run applies the trial again and the cards are the right way up.
        self.game.current_trial = None
        self.game._apply_trial()
        self.assertFalse(any(card.flipped for card in self.game.cards))

    def test_deal_breaker_trial_gags_the_board_until_a_card_is_sold(self):
        marble = self._run_under(main.Trial.DEAL_BREAKER)
        self.assertFalse(self.game.deal_breaker_released)
        self.assertTrue(self.game._deal_breaker_gags())
        # Nothing the board does pays out while it is gagged, but the block's
        # trigger is still spent (exactly like a Watch-gated block).
        self.game.score_chips = 0
        spent = main.Block(5, 5, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble.collisions_this_tick = [spent]
        self.game._handle_block_contacts([spent])
        self.assertEqual(self.game.score_chips, 0)
        self.assertEqual(spent.triggers_left, 0)
        # Selling a card releases the board for the rest of the run, and the
        # sale says so.
        card = main.CardItem(main.Card.COUPON, 40)
        self.game.cards.append(card)
        self.game.selected_toolbox_item = card
        self.game._sell_selected_item()
        self.assertTrue(self.game.deal_breaker_released)
        self.assertFalse(self.game._deal_breaker_gags())
        self.assertIn("Deal breaker", self.game.shop_message)
        paid = main.Block(6, 5, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble.collisions_this_tick = [paid]
        self.game._handle_block_contacts([paid])
        self.assertEqual(self.game.score_chips, 10)
        # A new run (a restart, a retry, or the next run's start) applies the
        # trial again, so the board is gagged once more.
        self.game._apply_trial()
        self.assertFalse(self.game.deal_breaker_released)
        self.assertTrue(self.game._deal_breaker_gags())


class TrialsTests(GameTestCase):
    """Trials and final bosses: the run-wide modifiers."""


    def test_defeat_awards_dice_squared_of_run_minus_three(self):
        # A game over in defeat awards dice = (run number - 3)^2. A defeat on
        # run 4 (the 3rd loss) gives (4 - 3)^2 = 1 die.
        self.assertEqual(metagame.dice(), 0)
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self._complete_run(100, required=1000)
        self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertEqual(metagame.dice(), (4 - 3) ** 2)
        self.assertEqual(self.game.game_over_dice_gained, 1)


    def test_victory_does_not_award_dice(self):
        # Winning all 24 runs ends in a perfect win; no dice are awarded.
        self.assertEqual(metagame.dice(), 0)
        for _ in range(main.TOTAL_RUNS):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertTrue(self.game.game_over)
        self.assertTrue(self.game.game_won)
        self.assertTrue(self.game.game_perfect)
        self.assertEqual(metagame.dice(), 0)
        self.assertEqual(self.game.game_over_dice_gained, 0)


    def test_trial_data_is_defined(self):
        self.assertEqual(main.Trial.name(main.Trial.HANDS_TIED), "Hands tied")
        self.assertEqual(main.Trial.name(main.Trial.CARD_CUTTER), "Card cutter")
        self.assertEqual(main.Trial.name(main.Trial.DEAD_ZONE), "Dead zone")
        self.assertEqual(main.Trial.name(main.Trial.ALL_FINISHES), "All finishes")
        self.assertEqual(main.Trial.name(main.Trial.SLIM_PICKINGS), "Slim pickings")
        self.assertEqual(main.Trial.name(main.Trial.LONG_RUN), "Long run")
        self.assertEqual(main.Trial.name(main.Trial.SHUFFLED), "Shuffled")
        self.assertEqual(main.Trial.name(main.Trial.BOUNCY_CASTLE), "Bouncy castle")
        self.assertEqual(main.Trial.name(main.Trial.CRUMBLING), "Crumbling")
        self.assertEqual(main.Trial.name(main.Trial.MARBLE_WEIGHT), "Marble weight")
        self.assertEqual(main.Trial.name(main.Trial.SPEEDRUN), "Speedrun")
        self.assertEqual(main.Trial.name(main.Trial.REPEATS_ONLY), "Repeats only")
        self.assertEqual(main.Trial.name(main.Trial.INFLATION), "Inflation")
        self.assertEqual(main.Trial.name(main.Trial.EMPTY_POCKETS), "Empty pockets")
        self.assertEqual(main.Trial.name(main.Trial.DEAL_BREAKER), "Deal breaker")
        self.assertEqual(main.Trial.name(main.Trial.X_RAY), "X-ray")
        self.assertEqual(main.Trial.name(main.Trial.PHANTOM), "Phantom")
        self.assertEqual(main.Trial.name(main.Trial.VERTIGO), "Vertigo")
        self.assertEqual(main.Trial.name(main.Trial.ELEPHANT), "Elephant")
        # The two that used to be the 24th run's final bosses are ordinary
        # trials now.
        self.assertEqual(main.Trial.name(main.Trial.SKY_HIGH), "Sky High")
        self.assertEqual(main.Trial.name(main.Trial.SINGULARITY), "Singularity")
        for trial in main.Trial.ORDER:
            self.assertTrue(main.Trial.description(trial))
        self.assertEqual(len(main.Trial.ORDER), 21)
        self.assertIn(main.Trial.DEAD_ZONE, main.Trial.ORDER)
        self.assertIn(main.Trial.ALL_FINISHES, main.Trial.ORDER)
        self.assertIn(main.Trial.SLIM_PICKINGS, main.Trial.ORDER)
        self.assertIn(main.Trial.LONG_RUN, main.Trial.ORDER)
        self.assertIn(main.Trial.SHUFFLED, main.Trial.ORDER)
        self.assertIn(main.Trial.BOUNCY_CASTLE, main.Trial.ORDER)
        self.assertIn(main.Trial.CRUMBLING, main.Trial.ORDER)
        self.assertIn(main.Trial.MARBLE_WEIGHT, main.Trial.ORDER)
        self.assertIn(main.Trial.SPEEDRUN, main.Trial.ORDER)
        self.assertIn(main.Trial.REPEATS_ONLY, main.Trial.ORDER)
        self.assertIn(main.Trial.INFLATION, main.Trial.ORDER)
        self.assertIn(main.Trial.EMPTY_POCKETS, main.Trial.ORDER)
        self.assertIn(main.Trial.DEAL_BREAKER, main.Trial.ORDER)
        self.assertIn(main.Trial.X_RAY, main.Trial.ORDER)
        self.assertIn(main.Trial.PHANTOM, main.Trial.ORDER)
        self.assertIn(main.Trial.VERTIGO, main.Trial.ORDER)
        self.assertIn(main.Trial.ELEPHANT, main.Trial.ORDER)
        self.assertIn(main.Trial.SKY_HIGH, main.Trial.ORDER)
        self.assertIn(main.Trial.SINGULARITY, main.Trial.ORDER)
        # The reworked Deal breaker is a board gag; its description says so.
        self.assertEqual(main.Trial.description(main.Trial.DEAL_BREAKER),
                         "Blocks never score until you sell a card.")


    def test_every_trial_has_its_own_tile_of_shapes_and_colours(self):
        # A trial's tile is its icon AND the pattern the whole screen is tiled
        # with while it runs: a square LATTICE CELL (not one grid unit — it is
        # big enough that the screen tiles exactly) built from tessellating
        # shapes in a few shades of the trial's own colour.
        size = main.ui.TILE_SIZE
        self.assertEqual(main.SCREEN_WIDTH % size, 0)
        self.assertEqual(main.SCREEN_HEIGHT % size, 0)
        self.assertNotEqual(size, main.GRID_SIZE)      # no longer one grid unit
        self.assertEqual(len(main.Trial.COLORS), len(main.Trial.ORDER))
        self.assertEqual(set(main.Trial.TILE_STYLES), set(main.Trial.ORDER))
        fingerprints = {}
        for trial in main.Trial.ORDER:
            with self.subTest(trial=main.Trial.name(trial)):
                tile = main.ui._tile_art(main.Trial, trial)
                self.assertEqual(tile.get_size(), (size, size))
                colours = {tuple(tile.get_at((x, y)))[:3]
                           for x in range(0, size, 2)
                           for y in range(0, size, 2)}
                # A tessellation of a few shapes in a few colours, never a flat
                # fill and never so busy that it stops reading as a pattern.
                self.assertGreaterEqual(len(colours), 2,
                                        "a tile must be shapes, not one colour")
                self.assertLessEqual(len(colours), 12,
                                     "a tile is a few shapes, not noise")
                palette = set(main.Trial.palette(trial).values())
                self.assertTrue(colours & palette,
                                "a tile is drawn in its own palette")
                fingerprints[trial] = self._pixel_hash(tile)
        # No two trials share a tile, and the art is built once.
        self.assertEqual(len(set(fingerprints.values())), len(main.Trial.ORDER))
        self.assertIs(main.ui._tile_art(main.Trial, main.Trial.DEAD_ZONE),
                      main.ui._tile_art(main.Trial, main.Trial.DEAD_ZONE))

    def test_no_two_trials_share_a_tessellation_pattern(self):
        # The user's rule: every trial has a tessellation of its own — not the
        # same family drawn twice in another colour (which now includes Sky
        # High and Singularity, the two former final bosses).
        modifiers = [(main.Trial, trial) for trial in main.Trial.ORDER]
        styles = [source.TILE_STYLES[value] for source, value in modifiers]
        self.assertEqual(len(set(styles)), len(modifiers),
                         f"a pattern is used twice: {sorted(styles)}")
        # ...and each family name belongs to its OWN drawer, so no two can ever
        # drift into the same art.
        drawers = [main.ui._TILE_TESSELLATIONS[style] for style in styles]
        self.assertEqual(len(set(drawers)), len(modifiers))
        # The rendered tiles are all different as well.
        fingerprints = {self._pixel_hash(main.ui._tile_art(source, value))
                        for source, value in modifiers}
        self.assertEqual(len(fingerprints), len(modifiers))

    def test_tiles_are_tessellations_that_meet_across_their_seams(self):
        # The whole point of the lattice: two tiles side by side and stacked
        # read as ONE pattern rather than as squares, because every family is
        # periodic inside the tile. A seam is continuous when the tile's own
        # left column and its right column would sit next to each other without
        # a discontinuity, which for a periodic pattern means the columns on
        # either side of the join continue an edge of the same shapes.
        size = main.ui.TILE_SIZE
        for trial in main.Trial.ORDER:
            with self.subTest(trial=main.Trial.name(trial)):
                tile = main.ui._tile_art(main.Trial, trial)
                # Stitching four copies must not introduce a colour that is not
                # already the pattern's own: no seam line, no background gap.
                stitched = pygame.Surface((size * 2, size * 2))
                for cx in range(2):
                    for cy in range(2):
                        stitched.blit(tile, (cx * size, cy * size))
                inner = {tuple(stitched.get_at((x, y)))[:3]
                         for x in range(1, size * 2 - 1)
                         for y in range(1, size * 2 - 1)}
                self.assertEqual(inner, {tuple(tile.get_at((x, y)))[:3]
                                        for x in range(size)
                                        for y in range(size)})
                # The squares never read as frames: the pixels along a seam
                # belong to shapes that cross it (the row/column just inside one
                # tile's edge is the same family of colours as the row/column
                # just inside the other tile's opposite edge).
                left = {tuple(tile.get_at((1, y)))[:3] for y in range(size)}
                right = {tuple(tile.get_at((size - 2, y)))[:3] for y in range(size)}
                self.assertTrue(left & right,
                                "the lattice does not continue over the seam")

    def test_the_all_finishes_tile_is_the_finish_checkerboard(self):
        # The tile the user described: white with its top-left and bottom-right
        # quadrants black, exactly like a Finish block — now built out of
        # triangles instead of squares.
        size = main.ui.TILE_SIZE
        cell = size // 2
        tile = main.ui._tile_art(main.Trial, main.Trial.ALL_FINISHES)
        dark = components.shade((245, 245, 245), -0.92)
        # Each quadrant is one square of the checkerboard, split by a diagonal
        # into two shades. Sample inside the cell's OWN triangle, which is the
        # one hugging the cell's RIGHT edge on the even cells and its LEFT edge
        # on the odd ones (see ui._tess_checker).
        cases = (((0, 0), dark), ((1, 0), (245, 245, 245)),
                 ((0, 1), (245, 245, 245)), ((1, 1), dark))
        for index, expected in cases:
            with self.subTest(cell=index):
                even = (index[0] + index[1]) % 2 == 0
                px = index[0] * cell + (cell * 3 // 4 if even else cell // 4)
                py = index[1] * cell + cell // 4
                got = tuple(tile.get_at((px, py)))[:3]
                for channel, want in zip(got, expected):
                    self.assertLessEqual(abs(channel - want), 6,
                                         f"cell {index} is not {expected}: {got}")
        # The whole tile uses those two colours (each with its triangle facet),
        # and each quadrant is split into two triangles.
        colours = {tuple(tile.get_at((x, y)))[:3]
                   for x in range(size) for y in range(size)}
        for expected in (dark, components.shade(dark, -0.22),
                         (245, 245, 245),
                         components.shade((245, 245, 245), -0.22)):
            self.assertIn(expected, colours)
        self.assertEqual(len(colours), 4)

    def test_a_tile_is_only_drawn_in_the_background_and_the_collection(self):
        # The user's rule: a tile may appear as the screen's background while
        # its modifier is in play and as the collection's icon — nowhere else.
        source = inspect.getsource(main.ui)
        self.assertEqual(source.count("draw_tile("), 3)   # def + 2 uses
        self.assertEqual(source.count("def _build_tile("), 1)
        # ...and the two uses are the screen background and the collection.
        background = inspect.getsource(main.ui._tile_background)
        self.assertIn("draw_tile(background, source, value,", background)
        self.assertIn("draw_background(game)",
                      inspect.getsource(main.ui.draw))
        self.assertIn("draw_tile(game.screen, _TILE_SOURCES[kind], value, rect)",
                      inspect.getsource(main.ui.draw_collection_icon))
        # The trial display itself never carries a tile.
        self.assertNotIn("draw_tile", inspect.getsource(main.ui.draw_trial_box))

    def test_hands_tied_trial_debuffs_a_quarter_of_blocks(self):
        # Exactly 1/4 of the marble-box blocks lose one trigger for the run.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        # One block upgraded to 3 triggers: Hands tied takes one away, it does
        # not silence the block.
        strong = self.game.grid[(0, 0)]
        strong.trigger_limit = 3
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game._apply_trial()
        self.assertEqual(len(self.game.trial_debuffed_blocks), 2)  # 9 // 4
        # The description states the new rule (one fewer trigger, not silence).
        self.assertIn("1 fewer time", main.Trial.description(main.Trial.HANDS_TIED))

        self.game.reset_run(False)
        for block in self.game.grid.values():
            if block in self.game.trial_debuffed_blocks:
                self.assertEqual(block.triggers_left,
                                 max(0, block.trigger_limit
                                     - main.TRIAL_TRIGGER_PENALTY))
            else:
                self.assertEqual(block.triggers_left, block.trigger_limit)
        if strong in self.game.trial_debuffed_blocks:
            self.assertEqual(strong.triggers_left, 2)
        self.assertTrue(all(block.triggers_left >= 0
                            for block in self.game.grid.values()))


    def test_hands_tied_keeps_the_same_blocks_when_the_run_replays(self):
        # Restarting the run (R / T) or retrying it re-applies the SAME choice:
        # the debuffed blocks are decided once per run, so they cannot be
        # rerolled by replaying.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game._apply_trial()
        first = set(self.game.trial_debuffed_blocks)
        self.assertTrue(first)
        for _ in range(3):        # R, T, and a retry both re-apply the trial
            self.game._apply_trial()
            self.assertEqual(set(self.game.trial_debuffed_blocks), first)
            self.game.reset_run(True)
            self.assertEqual(set(self.game.trial_debuffed_blocks), first)
        # ...and the decision itself is what is kept.
        self.assertEqual(self.game.trial_decision.get("cells"),
                         {(block.x, block.y) for block in first})
        # A DIFFERENT trial decides afresh (the memo belongs to the trial).
        self.game.current_trial = main.Trial.CRUMBLING
        self.game._apply_trial()
        self.assertNotEqual(self.game.trial_decision.get("trial"),
                            main.Trial.HANDS_TIED)


    def test_shuffled_trial_keeps_one_order_when_the_run_replays(self):
        # "Flips and shuffles your cards" happens ONCE for the run: re-applying
        # the trial (R, T, a retry) must not shuffle the cards a second time, or
        # the player could keep re-rolling the order (and the Blueprint that
        # depends on it) for free.
        values = [main.match_group_card(main.match_group_for_shape(shape),
                                        main.Scorer.MULT_ADD)
                  for shape in (main.Shape.PIPE, main.Shape.SLOPE)]
        values += [main.Card.COUPON, main.Card.MARKET]
        self.game.cards = [main.CardItem(value, 40) for value in values]
        self.game.current_trial = main.Trial.SHUFFLED
        self.game._apply_trial()
        order = [card.value for card in self.game.cards]
        self.assertCountEqual(order, values)
        for _ in range(3):
            self.game._apply_trial()
            self.assertEqual([card.value for card in self.game.cards], order)
        self.assertEqual([card.value for card in self.game.trial_decision["order"]],
                         order)
        # A card bought after the decision follows the decided ones.
        bought = main.CardItem(main.Card.SHOWMAN, 40)
        self.game.cards.append(bought)
        self.game._apply_trial()
        self.assertEqual([card.value for card in self.game.cards],
                         order + [main.Card.SHOWMAN])


    def test_the_runs_dice_replay_identically(self):
        # The run's own RNG (the 8 ball's retrigger chance, a Random condition's
        # measure) is re-seeded every time the run (re)starts, so replaying a
        # run replays its luck instead of rolling until it lands well.
        # (A run needs a Start block to be built at all — reset_run refuses
        # without one, and a refused reset is not a replay.)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        first = [self.game.run_rng.random() for _ in range(5)]
        self.assertTrue(self.game.reset_run(False))   # R / T / a retry
        self.assertEqual([self.game.run_rng.random() for _ in range(5)], first)
        # A NEW run (a new seed, drawn when its trial is chosen) rolls its own.
        self.game._choose_trial(self.game.run_number + 1)
        self.game.reset_run(False)
        self.assertNotEqual([self.game.run_rng.random() for _ in range(5)], first)


    def test_trial_is_chosen_before_run_starts(self):
        # A fresh game picks the trial up front (so the info box can show it
        # during setup); starting the run applies it without re-rolling it.
        self.game.trials_enabled = True
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        trial_before = self.game.current_trial
        self.game.reset_run()  # choose_trial defaults to True
        self.assertEqual(self.game.current_trial, trial_before)


    def test_a_round_gives_trials_to_its_last_runs(self):
        # The difficulty decides how many of a round's runs play a trial, and
        # they are the round's LAST runs: difficulties 1-2 give only the final
        # run of a round a trial, difficulty 3 gives the last two, and
        # difficulty 4 gives every run of the round one.
        expected = {main.Difficulty.LEVEL_1: 1, main.Difficulty.LEVEL_2: 1,
                    main.Difficulty.LEVEL_3: 2, main.Difficulty.LEVEL_4: 3}
        for level, with_trial in expected.items():
            with self.subTest(difficulty=level):
                game = main.Game()
                game.trials_enabled = True
                game.difficulty = level
                trials = []
                for run in range(main.RUNS_PER_ROUND):
                    game._choose_trial(run)  # the run being set up
                    trials.append(game.current_trial)
                self.assertEqual(sum(t is not None for t in trials), with_trial,
                                 trials)
                for run, trial in enumerate(trials):
                    if run >= main.RUNS_PER_ROUND - with_trial:
                        self.assertIn(trial, main.Trial.ORDER)
                    else:
                        self.assertIsNone(trial, f"run {run + 1} is trial-free")


    def test_slim_pickings_trims_the_shop_of_the_games_first_run(self):
        # The game's opening run draws its trial as the Game is built, and the
        # shop is built BEFORE that draw: an opening Slim pickings run has to
        # shed its two options after the fact (see reset_game), or the very
        # first trial of a game would do nothing at all.
        full = len(self.game.shop.items)  # the setUp game's untrimmed shop
        self.game.trials_enabled = True
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: (main.Trial.SLIM_PICKINGS
                                                 if seq is main.Trial.ORDER
                                                 else seq[0])):
            self.game.reset_game()
        self.assertEqual(self.game.current_trial, main.Trial.SLIM_PICKINGS)
        self.assertEqual(len(self.game.shop.items), full - 2)


    def test_any_other_trial_leaves_the_games_first_shop_full(self):
        full = len(self.game.shop.items)
        self.game.trials_enabled = True
        with mock.patch("main.random.choice",
                        side_effect=lambda seq: (main.Trial.HANDS_TIED
                                                 if seq is main.Trial.ORDER
                                                 else seq[0])):
            self.game.reset_game()
        self.assertEqual(self.game.current_trial, main.Trial.HANDS_TIED)
        self.assertEqual(len(self.game.shop.items), full)


    def test_buying_slim_pickings_trims_the_shop_on_screen(self):
        # The trial display's left half buys a different trial onto the shop
        # the player is already looking at, so landing on Slim pickings must
        # bite THAT shop rather than wait for the next reroll.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.cash = 1000
        full = len(self.game.shop.items)
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        with mock.patch.object(main.Game, "_random_other_trial",
                               return_value=main.Trial.SLIM_PICKINGS):
            self.assertTrue(self.game._click_trial_display(left))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertEqual(len(self.game.shop.items), full - 2)


    def test_a_slim_run_rerolls_the_shop_two_options_short(self):
        # Every shop a Slim pickings run rerolls into is two options lighter,
        # and nothing is trimmed at all while the trial system is switched off.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SLIM_PICKINGS
        self.game.cash = 1000
        full = len(self.game.shop.items)
        self.game._refresh_shop()
        self.assertEqual(len(self.game.shop.items), full - 2)
        self.game.trials_enabled = False
        self.game.shop.refresh()
        self.game._trim_shop_for_trial()
        self.assertEqual(len(self.game.shop.items), full)


    def test_bouncy_castle_trial_marks_marble_bouncy_castle(self):
        # Starting a run under the bouncy-castle trial gives each marble the
        # bouncy_castle flag (physics reflects it off every solid block).
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.BOUNCY_CASTLE
        self.game.reset_run(False)
        self.assertTrue(all(m.bouncy_castle for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.reset_run(False)
        self.assertFalse(any(m.bouncy_castle for m in self.game.marbles))


    def test_crumbling_trial_marks_quarter_of_blocks(self):
        # Crumbling marks ~1/4 of the placed solid (non-role) blocks fragile.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.FINISH)
        self.game.current_trial = main.Trial.CRUMBLING
        with mock.patch("main.random.sample",
                        side_effect=lambda seq, k: seq[:k]):
            self.game._apply_trial()
        # 8 scoring blocks -> 8 // 4 = 2 marked; START/FINISH never marked.
        self.assertEqual(len(self.game.trial_fragile_blocks), 2)
        for block in self.game.trial_fragile_blocks:
            self.assertTrue(block.trial_fragile)
            self.assertNotIn(block.scorer, (main.Scorer.START, main.Scorer.FINISH))
        self.assertFalse(self.game.grid[(0, 1)].trial_fragile)
        self.assertFalse(self.game.grid[(1, 1)].trial_fragile)


    def test_crumbling_keeps_its_mark_when_the_block_moves(self):
        # Moving a fragile block carries the trial's mark with it: the decided
        # CELL moves, so the block does not stop shattering and a re-apply marks
        # the block where it now stands (see Game._carry_trial_mark).
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.CRUMBLING
        with mock.patch("main.random.sample",
                        side_effect=lambda seq, k: seq[:k]):
            self.game._apply_trial()
        fragile = self.game.grid[(0, 0)]
        self.assertTrue(fragile.trial_fragile)
        self.assertEqual(self.game.trial_decision["cells"], {(0, 0), (1, 0)})

        self._click(self._grid_pos(0, 0))  # pick the fragile block up...
        self._click(self._grid_pos(4, 4))  # ...and put it down three cells over

        moved = self.game.grid[(4, 4)]
        self.assertIsNot(moved, fragile)     # a move rebuilds the block
        self.assertTrue(moved.trial_fragile)
        self.assertIn(moved, self.game.trial_fragile_blocks)
        self.assertNotIn(fragile, self.game.trial_fragile_blocks)
        self.assertEqual(self.game.trial_decision["cells"], {(1, 0), (4, 4)})

        self.game._apply_trial()             # a replay marks the same blocks
        self.assertTrue(self.game.grid[(4, 4)].trial_fragile)
        self.assertIn(self.game.grid[(4, 4)], self.game.trial_fragile_blocks)


    def test_hands_tied_keeps_its_mark_when_the_block_moves(self):
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.HANDS_TIED
        with mock.patch("main.random.sample",
                        side_effect=lambda seq, k: seq[:k]):
            self.game._apply_trial()
        debuffed = self.game.grid[(0, 0)]
        self.assertEqual(self.game._trigger_limit(debuffed), 0)  # 1 - the penalty

        self._click(self._grid_pos(0, 0))
        self._click(self._grid_pos(4, 4))

        moved = self.game.grid[(4, 4)]
        self.assertIn(moved, self.game.trial_debuffed_blocks)
        self.assertNotIn(debuffed, self.game.trial_debuffed_blocks)
        self.assertEqual(self.game._trigger_limit(moved), 0)
        # ...while a block the trial never picked keeps its full limit.
        self.assertEqual(self.game._trigger_limit(self.game.grid[(7, 0)]), 1)
        self.assertEqual(self.game.trial_decision["cells"], {(0, 1), (4, 4)})


    def test_erasing_a_marked_block_keeps_its_mark_in_the_toolbox(self):
        # Erasing a marked block carries the mark to the toolbox item, together
        # with the cell it stood in (see _refund_block / _carry_trial_mark), so
        # putting the block down elsewhere puts the mark there. The mark does NOT
        # outlive the run it belongs to: the next application rebuilds the marks
        # from the board, where an erased block no longer is.
        self.game.grid.clear()
        for gx in range(8):
            self.game.grid[(gx, 0)] = main.Block(gx, 0, scorer=main.Scorer.CHIPS_ADD,
                                                 scorer_amount=10)
        self.game.grid[(0, 1)] = main.Block(0, 1, scorer=main.Scorer.START)
        self.game.current_trial = main.Trial.CRUMBLING
        with mock.patch("main.random.sample",
                        side_effect=lambda seq, k: seq[:k]):
            self.game._apply_trial()
        self.game._erase_block_at(0, 0)

        item = self.game.toolbox.items[-1]
        self.assertIn(item, self.game.trial_fragile_blocks)
        self.assertEqual(item.trial_cell, (0, 0))
        self.game._equip_block(item)
        self.assertTrue(self.game._place_block_at(4, 4))
        self.assertTrue(self.game.grid[(4, 4)].trial_fragile)
        self.assertNotIn(item, self.game.trial_fragile_blocks)
        self.assertEqual(self.game.trial_decision["cells"], {(1, 0), (4, 4)})

        # A block erased again and left in the toolbox keeps nothing once the
        # marks are rebuilt: the trial marks the board, not the inventory.
        self.game._erase_block_at(4, 4)
        item = self.game.toolbox.items[-1]
        self.game._apply_trial()
        self.assertNotIn(item, self.game.trial_fragile_blocks)
        self.game._equip_block(item)
        self.assertTrue(self.game._place_block_at(6, 6))
        self.assertNotIn(self.game.grid[(6, 6)], self.game.trial_fragile_blocks)
        self.assertFalse(getattr(self.game.grid[(6, 6)], "trial_fragile", False))


    def test_speedrun_trial_halves_ideal_time(self):
        # With Speedrun the time factor peaks at half the ideal time, so a run
        # that takes TIME_IDEAL/2 scores the full time contribution while one
        # taking the normal ideal time scores much less.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SPEEDRUN
        self.game.run_time = main.TIME_IDEAL / 2
        peak, _, _, _ = self.game._score_factors()
        self.game.run_time = main.TIME_IDEAL * 2  # well off the halved ideal
        off_peak, _, _, _ = self.game._score_factors()
        self.assertGreater(peak, 0.9)
        self.assertGreater(peak, off_peak)
        self.assertLess(off_peak, 0.5)


    def test_trial_change_never_offers_the_trial_already_running(self):
        # The reroll passes only OTHER trials to random.choice, so the bought
        # trial is always a different one.
        self.game.trials_enabled = True
        self.game.cash = 100000
        seen = {}

        def pick(sequence):
            seen["candidates"] = list(sequence)
            return sequence[0]

        self.game.current_trial = main.Trial.DEAD_ZONE
        with mock.patch("main.random.choice", side_effect=pick):
            self.game._click_trial_display(
                (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery))
        self.assertNotIn(main.Trial.DEAD_ZONE, seen["candidates"])
        self.assertEqual(len(seen["candidates"]), len(main.Trial.ORDER) - 1)
        self.assertNotEqual(self.game.current_trial, main.Trial.DEAD_ZONE)


    def test_trial_display_needs_cash_and_the_build_phase(self):
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        # Too little cash: nothing changes and both fees are named.
        self.game.cash = 10
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.shop_message,
                         f"Need ${main.TRIAL_CHANGE_COST} to change the trial")
        self.assertFalse(self.game._click_trial_display(right))
        self.assertEqual(self.game.shop_message,
                         f"Need ${main.TRIAL_DISABLE_COST} to disable the trial")
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 10)
        # A run in progress fixes its trial: the display is display-only.
        self.game.cash = 1000
        self.game.run_active = True
        self.assertFalse(self.game._click_trial_display(left))
        self.assertEqual(self.game.current_trial, main.Trial.LONG_RUN)
        self.assertEqual(self.game.cash, 1000)
        self.assertIn("while building", self.game.shop_message)
        # The post-run RETRY/CONTINUE state is out too.
        self.game.run_active = False
        self.game.run_complete = True
        self.game.awaiting_after_run = True
        self.assertFalse(self.game._click_trial_display(right))
        self.assertEqual(self.game.cash, 1000)
        self.game.awaiting_after_run = False
        self.game.run_complete = False


    def test_all_finishes_trial_marks_marbles_finish_on_border(self):
        # Starting a run under the all-finishes trial gives each marble the
        # finish_on_border flag (physics does the actual border finish). The
        # trial must be ENABLED for its physics to apply at all.
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.reset_run(False)
        self.assertTrue(all(m.finish_on_border for m in self.game.marbles))
        # Other trials don't set it.
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.reset_run(False)
        self.assertTrue(all(m.dead_zone for m in self.game.marbles))
        self.assertFalse(any(m.finish_on_border for m in self.game.marbles))
        # With the trial system switched off, no trial flag applies, even
        # though the game still holds a trial id.
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.trials_enabled = False
        self.game.reset_run(False)
        self.assertFalse(any(m.finish_on_border for m in self.game.marbles))


    def test_failing_the_last_run_ends_in_defeat(self):
        # The 24th run must be CLEARED to win. With only one prior loss,
        # failing it ends the game in defeat (not a win) and awards defeat dice
        # like any other loss. It is an ordinary run now — it used to be the
        # boss run — so nothing about it is special except that it is last.
        for run in range(main.TOTAL_RUNS - 1):
            if run == 5:
                self._complete_run(100, required=1000)  # 1 prior loss
            else:
                self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.assertFalse(self.game.game_over)

        self._complete_run(100, required=1000)  # fail the 24th (last) run
        self.game._continue_run()

        self.assertTrue(self.game.game_over)
        self.assertFalse(self.game.game_won)
        self.assertFalse(self.game.game_perfect)
        self.assertEqual(self.game.game_over_dice_gained, (main.TOTAL_RUNS - 3) ** 2)
        self.assertEqual(metagame.dice(), (main.TOTAL_RUNS - 3) ** 2)


    def test_the_two_former_bosses_are_ordinary_trials(self):
        # The user's request: "make the final bosses just normal bosses ... for
        # the final boss, just use a random normal boss". Sky High and
        # Singularity are trials like the rest — same tables, same pool — and
        # there is no FinalBoss class left holding them.
        self.assertFalse(hasattr(main, "FinalBoss"))
        self.assertFalse(hasattr(components, "FinalBoss"))
        for trial in (main.Trial.SKY_HIGH, main.Trial.SINGULARITY):
            with self.subTest(trial=main.Trial.name(trial)):
                self.assertIn(trial, main.Trial.ORDER)
                self.assertTrue(main.Trial.description(trial))
                self.assertIn(trial, main.Trial.COLORS)
                self.assertIn(trial, main.Trial.TILE_STYLES)
        self.assertEqual(main.Trial.description(main.Trial.SKY_HIGH),
                         "The required score is doubled.")
        # Both are drawable like any other trial: the pool the shop-side draw
        # reads (Trial.ORDER) is all there is.
        self.assertIn(main.Trial.SKY_HIGH, main.Trial.ORDER)
        self.assertIn(main.Trial.SINGULARITY, main.Trial.ORDER)


    def test_the_24th_run_plays_a_normal_trial(self):
        # Reaching the last run draws a trial from the ordinary pool, exactly
        # as every other run does (the draw is pinned here so it is checkable),
        # and that run's trial display is live like any other run's.
        def fake_choice(sequence):
            return (main.Trial.SKY_HIGH if sequence == main.Trial.ORDER
                    else sequence[0])

        with mock.patch("main.random.choice", side_effect=fake_choice):
            for _ in range(main.TOTAL_RUNS - 1):
                self._complete_run(1000000, required=1)
                self.game._continue_run()
        self.assertEqual(self.game.run_number, main.TOTAL_RUNS - 1)
        self.assertEqual(self.game.current_trial, main.Trial.SKY_HIGH)
        # The 24th run used to show a FINAL BOSS and lock the display; it is
        # bought from like any other run now.
        self.game.trials_enabled = True
        self.assertTrue(self.game.trial_options_available())
        self.assertIsNotNone(self.game.tile_source[0])


    def test_sky_high_doubles_the_required_score(self):
        # The user's request: "make sky high give 2x required score". The trial
        # puts the factor on the RUN's target wherever the run's trial changes,
        # so buying Sky High on doubles it and buying it away puts the run's
        # own scheduled target back.
        self.assertEqual(main.SKY_HIGH_SCORE_FACTOR, 2.0)
        self.game.trials_enabled = True
        self.game.run_number = main.TOTAL_RUNS - 1
        base = main.get_next_required_score(self.game.run_number,
                                            self.game.score_growth)
        self.game.required_score = base

        self.game.current_trial = main.Trial.SKY_HIGH
        self.game._apply_trial()
        self.assertEqual(self.game.required_score, base * 2)
        self.assertEqual(self.game._trial_score_factor(), 2.0)

        # Any other trial is 1x, and so is no trial at all.
        for trial in (main.Trial.DEAD_ZONE, main.Trial.SINGULARITY, None):
            with self.subTest(trial=trial):
                self.game.current_trial = trial
                self.game._apply_trial()
                self.assertEqual(self.game.required_score, base)
                self.assertEqual(self.game._trial_score_factor(), 1.0)
        # And the same holds through the display's own purchase: a Sky High run
        # bought away drops back to the scheduled target.
        self.game.current_trial = main.Trial.SKY_HIGH
        self.game._apply_trial()
        self.assertEqual(self.game.required_score, base * 2)
        self.game.cash = 1000
        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(right))
        self.assertIsNone(self.game.current_trial)
        self.assertEqual(self.game.required_score, base)

    def test_a_forced_target_survives_a_trial_change(self):
        # Grace v2 makes this run unfailable by taking its target over (0).
        # Re-deriving the target when the run's trial changes must leave such a
        # run alone, or buying a trial would quietly make it failable again.
        self.game.trials_enabled = True
        self.game.run_number = 5
        self.game.required_score = main.get_next_required_score(
            5, self.game.score_growth)
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game._apply_trial()
        self.assertFalse(self.game.target_forced)

        self.assertTrue(self.game._action_grace(
            main.ActionItem(main.Action.GRACE, 1, version=2)))
        self.assertEqual(self.game.required_score, 0)
        self.assertTrue(self.game.target_forced)

        # A trial buy and a trial apply both leave the 0 alone.
        self.game.current_trial = main.Trial.SKY_HIGH
        self.game._apply_trial()
        self.assertEqual(self.game.required_score, 0)
        self.game.cash = 1000
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(left))
        self.assertEqual(self.game.required_score, 0)

        # Advancing to the next run hands the target back to the schedule: the
        # forced target belonged to the run it was used on.
        self._complete_run(1, required=0)
        self.game._continue_run()
        self.assertFalse(self.game.target_forced)
        self.assertGreater(self.game.required_score, 0)


    def test_endless_play_hands_every_run_a_trial(self):
        # Past the last run the game keeps going, and the endless runs play
        # trials exactly like the runs before them (there is no boss run to
        # leave anything behind any more).
        self.game.trials_enabled = True
        for _ in range(main.TOTAL_RUNS):
            self._complete_run(1000000, required=1)
            self.game.continue_past_game_over = True  # the player keeps playing
            self.game._continue_run()

        self.assertEqual(self.game.run_number, main.TOTAL_RUNS)
        self.assertIn(self.game.current_trial, main.Trial.ORDER)
        self.assertTrue(self.game.trial_options_available())


    def test_endless_play_trial_display_can_be_changed_and_disabled(self):
        # The two halves of the trial display work again once the boss run is
        # behind the player.
        for _ in range(main.TOTAL_RUNS - 1):
            self._complete_run(1000000, required=1)
            self.game._continue_run()
        self.game.trials_enabled = True
        self.game.continue_past_game_over = True
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.assertTrue(self.game.trial_options_available())

        self.game.cash = 1000
        was = self.game.current_trial
        left = (main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(left))
        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)
        self.assertNotEqual(self.game.current_trial, was)

        right = (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery)
        self.assertTrue(self.game._click_trial_display(right))
        self.assertEqual(self.game.cash,
                         1000 - main.TRIAL_CHANGE_COST - main.TRIAL_DISABLE_COST)
        self.assertIsNone(self.game.current_trial)
        # And a trial can be bought back onto the endless run.
        self.assertTrue(self.game._click_trial_display(left))
        self.assertIn(self.game.current_trial, main.Trial.ORDER)


    def test_endless_singularity_stops_growing_the_marble(self):
        # The Singularity trial's mass growth belongs to the run that plays it:
        # once that run is over the marble is back to its own mass.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.SINGULARITY
        marble = self._add_marble()
        self.game.run_active = True
        before = marble.mass
        for _ in range(60):  # one second at DT
            self.game.update()
        self.assertGreater(marble.mass, before)
        self.assertAlmostEqual(marble.mass,
                               before + main.SINGULARITY_MASS_GROWTH, places=2)

        # The next run plays a different trial, so nothing grows any more.
        self._complete_run(1000000, required=1)
        self.game._continue_run()
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game._apply_trial()
        marble = self._add_marble()
        self.game.run_active = True
        settled = marble.mass
        for _ in range(60):
            self.game.update()
        self.assertEqual(marble.mass, settled)


    def test_a_loaded_save_keeps_a_forced_target(self):
        # Grace v2's taken-over target rides through a save, so reloading a run
        # it was used on does not quietly make that run failable again.
        data = {"run_number": 5, "required_score": 0, "target_forced": True}
        forced = main.Game()
        save_system._load_save_data(forced, data, 1)
        self.assertEqual(forced.required_score, 0)
        self.assertTrue(forced.target_forced)

        # An ordinary save (and an older one with no such key at all) is not
        # forced, and re-derives its target when its trial changes.
        plain_data = {"run_number": 5, "required_score": 500}
        plain = main.Game()
        save_system._load_save_data(plain, plain_data, 1)
        self.assertEqual(plain.required_score, 500)
        self.assertFalse(plain.target_forced)
        plain.trials_enabled = True
        plain.current_trial = main.Trial.SKY_HIGH
        plain._apply_trial()
        scheduled = main.get_next_required_score(5, plain.score_growth)
        self.assertEqual(plain.required_score, scheduled * 2)


    def test_beating_a_run_under_a_former_boss_discovers_it(self):
        # Clearing a run played under Sky High (or Singularity) reveals that
        # TRIAL in the collection, exactly as any other trial's run does.
        for trial in (main.Trial.SKY_HIGH, main.Trial.SINGULARITY):
            with self.subTest(trial=main.Trial.name(trial)):
                self.game.trials_enabled = True
                self.game.current_trial = trial
                self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.START)
                self.assertTrue(self.game.reset_run())
                self.game.marbles[0].finished = True
                self.game.required_score = 1
                self.game.score_chips = 1
                self.game.score_mult = 1
                self.game._handle_block_contacts([])
                self.assertTrue(self.game.run_cleared)
                self.assertTrue(collection.is_trial_discovered(trial))
                # Commit the run, so the next trial starts from a clean
                # post-run state (reset_run refuses while RETRY/CONTINUE is up).
                self.game._continue_run()
        # ...and both show up in the collection's TRIAL entries, not a category
        # of their own.
        entries = self.game._collection_entries()
        kinds = {kind for kind, *_ in entries}
        self.assertNotIn("final_boss", kinds)
        by_value = {e[1]: e for e in entries if e[0] == "trial"}
        for trial in (main.Trial.SKY_HIGH, main.Trial.SINGULARITY):
            with self.subTest(trial=main.Trial.name(trial)):
                entry = by_value[trial]
                self.assertEqual(entry[2], main.Trial.name(trial))
                self.assertTrue(entry[4], "a trial needs an icon in the collection")


    def test_the_24th_run_dot_reads_like_every_other(self):
        # The 24th run used to stand out (a black dot, gold when beaten, deep
        # red when lost); it is an ordinary run now, so its dot is gray until
        # played and green/red afterwards, exactly like run 1's.
        last = main.TOTAL_RUNS - 1
        self.game.run_results = []
        main.ui.draw_run_dots(self.game)
        cx, cy = self._run_dot_pixel(last)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], main.GRAY)
        nx, ny = self._run_dot_pixel(0)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.GRAY)

        self.game.run_results = [True] * main.TOTAL_RUNS
        main.ui.draw_run_dots(self.game)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], main.GREEN)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.GREEN)

        self.game.run_results = [False] + [True] * (main.TOTAL_RUNS - 2) + [False]
        main.ui.draw_run_dots(self.game)
        self.assertEqual(self.game.screen.get_at((cx, cy))[:3], main.RED)
        self.assertEqual(self.game.screen.get_at((nx, ny))[:3], main.RED)


class ChallengerTests(GameTestCase):
    """Challenger: buying the trial display's two options costs half as much."""

    def _own_challenger(self):
        self.game.cards.append(main.CardItem(main.Card.CHALLENGER, 28))

    def _trial_half(self, side):
        """A point inside the trial display's left/right half.

        The display's two halves are bought by clicking them, and the trial
        system has to be ON for the display to be live at all (see
        trial_options_available), so every test here enables it first.
        """
        self.game.trials_enabled = True
        return ((main.TRIAL_BOX_RECT.left + 5, main.TRIAL_BOX_RECT.centery)
                if side == "left" else
                (main.TRIAL_BOX_RECT.right - 5, main.TRIAL_BOX_RECT.centery))

    def test_challenger_card_data(self):
        self.assertIn(main.Card.CHALLENGER, main.Card.ORDER)
        self.assertEqual(main.Card.name(main.Card.CHALLENGER), "Challenger")
        self.assertEqual(main.Card.PRICES[main.Card.CHALLENGER], 28)
        self.assertEqual(main.Card.rarity_name(main.Card.CHALLENGER), "Common")
        self.assertTrue(main.Card.comment(main.Card.CHALLENGER))
        self.assertIn("half", main.Card.description(main.Card.CHALLENGER))
        self.assertIn(main.Card.CHALLENGER, main.Card.COLORS)
        self.assertIn(main.Card.CHALLENGER, main.Card.GLYPHS)
        self.assertEqual(main.CHALLENGER_COST_FACTOR, 0.5)
        # A passive utility card: the trial display owns the fees and reads it.
        self.assertIsNone(components.match_group_card_meta(main.Card.CHALLENGER))
        self.assertIsNone(components.card_scorer(main.Card.CHALLENGER))
        self.assertNotIn(main.Card.CHALLENGER, components.NAMED_CARD_ORDER)

    def test_the_two_fees_are_halved(self):
        self.assertEqual(self.game.trial_change_cost(), main.TRIAL_CHANGE_COST)
        self.assertEqual(self.game.trial_disable_cost(), main.TRIAL_DISABLE_COST)

        self._own_challenger()

        self.assertEqual(self.game.trial_change_cost(),
                         main.TRIAL_CHANGE_COST // 2)
        self.assertEqual(self.game.trial_disable_cost(),
                         main.TRIAL_DISABLE_COST // 2)
        # The Card cutter silences it like every other card effect.
        self.game.disabled_card = self.game.cards[-1]
        self.assertEqual(self.game.trial_change_cost(), main.TRIAL_CHANGE_COST)

    def test_changing_a_trial_charges_the_halved_fee(self):
        self._own_challenger()
        self.game.cash = 1000
        before = self.game.current_trial

        self.assertTrue(self.game._click_trial_display(self._trial_half("left")))

        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST // 2)
        self.assertNotEqual(self.game.current_trial, before)
        self.assertIn(f"(${main.TRIAL_CHANGE_COST // 2})",
                      self.game.shop_message)

    def test_disabling_a_trial_charges_the_halved_fee(self):
        self._own_challenger()
        self.game.cash = 1000

        self.assertTrue(self.game._click_trial_display(self._trial_half("right")))

        self.assertEqual(self.game.cash, 1000 - main.TRIAL_DISABLE_COST // 2)
        self.assertIsNone(self.game.current_trial)
        self.assertIn(f"(${main.TRIAL_DISABLE_COST // 2})",
                      self.game.shop_message)

    def test_the_halved_fee_is_what_the_display_shows(self):
        # The overlay reads the game's own fees, so the price on the button is
        # the price charged.
        self._own_challenger()
        self._trial_half("left")          # turns the trial system on
        self.game.screen.fill(main.BLACK)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            rects = main.ui.draw_trial_options(self.game, main.TRIAL_BOX_RECT)
        self.assertEqual(len(rects), 2)
        # The halved fee is affordable at $30, which the full price is not.
        self.game.cash = 30
        self.assertGreaterEqual(30, self.game.trial_change_cost())
        self.assertLess(30, main.TRIAL_CHANGE_COST)

    def test_a_player_without_the_card_pays_in_full(self):
        self.game.cash = 1000
        half = self._trial_half("left")

        self.assertTrue(self.game._click_trial_display(half))

        self.assertEqual(self.game.cash, 1000 - main.TRIAL_CHANGE_COST)

