"""Drawing: the HUD, sidebar, panels, fonts, popups and the CRT filter.

Split out of the old tests/test_run_scoring.py; the shared Game, helpers and
imports live in tests/game_test_case.py.
"""

from tests.game_test_case import *  # noqa: F401,F403


def _flame_pixel(surface, x, y, tol=3):
    """True when a board-fire coloured pixel is within ``tol`` px of (x, y).

    The marble's flames are drawn in the fire's two colours exactly
    (``pygame.draw`` writes them raw), but they flicker and wander, so a sample
    is taken as a small patch rather than a single pixel.
    """
    fire = (main.ui.FIRE_BODY_COLOR, main.ui.FIRE_CORE_COLOR)
    return any(surface.get_at((x + dx, y + dy))[:3] in fire
               for dx in range(-tol, tol + 1)
               for dy in range(-tol, tol + 1))


def _flame_reach(surface, x, y, dx, dy, limit=16):
    """How far a flame reaches from (x, y) along (dx, dy), in pixels."""
    fire = (main.ui.FIRE_BODY_COLOR, main.ui.FIRE_CORE_COLOR)
    reach = 0
    for dist in range(limit + 1):
        if surface.get_at((x + dx * dist, y + dy * dist))[:3] in fire:
            reach = dist
    return reach


class UiTests(GameTestCase):
    """Drawing: the HUD, sidebar, panels, fonts, popups and the CRT filter."""


    def test_none_scorer_block_draws_red_border_after_trigger(self):
        block = main.Block(0, 0, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)

        block.draw(surface)  # untriggered: white border
        self.assertEqual(surface.get_at((1, main.GRID_SIZE // 2))[:3], main.WHITE)

        block.triggers_left = 0  # triggered during a run
        surface.fill((0, 0, 0))
        block.draw(surface)
        self.assertEqual(surface.get_at((1, main.GRID_SIZE // 2))[:3], main.RED)


    def test_no_effect_block_shape_is_scorer_colored(self):
        # A block with no effect has no center icon, so its shape is filled
        # with its scorer's color instead of a plain black interior.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            self.assertEqual(surface.get_at(
                (main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3], expected)
            self.assertEqual(surface.get_at((2, 2))[:3], expected)
        finally:
            main.BLOCK_BORDERS_ON = prev


    def test_no_scorer_line_shapes_draw_black_stroke(self):
        # The thin line shapes draw only a stroke (no fill). A bare no-scorer
        # line block is a plain black wall, matching the black fill of a
        # no-scorer solid shape. A scorer-colored line still paints its
        # scorer's color and a used-up line keeps the red indicator.
        for shape in (main.Shape.LINE, main.Shape.FLAT_LINE,
                      main.Shape.CURVED_SLOPE_LINE, main.Shape.HALF_PIPE):
            block = main.Block(0, 0, shape=shape, scorer=main.Scorer.NONE,
                               origin=(0, 0))
            surface = pygame.Surface([main.GRID_SIZE] * 2)
            surface.fill(main.MARBLE_BOX_COLOR)  # the board behind a wall
            block.draw(surface)
            black_px = [p for p in [(x, y) for x in range(main.GRID_SIZE)
                                    for y in range(main.GRID_SIZE)]
                        if surface.get_at(p)[:3] == main.BLACK]
            self.assertTrue(black_px, f"{shape} no-scorer drew no black stroke")
            # The stroke must be black, never the old white line.
            self.assertFalse(any(surface.get_at(p)[:3] == main.WHITE
                                 for p in black_px),
                             f"{shape} no-scorer line is white")
        # A scorer-colored line keeps its scorer color (not black).
        block = main.Block(0, 0, shape=main.Shape.LINE,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        surface.fill(main.MARBLE_BOX_COLOR)
        block.draw(surface)
        colored = sum(1 for x in range(main.GRID_SIZE) for y in range(main.GRID_SIZE)
                      if surface.get_at((x, y))[:3]
                      == main.Scorer.color(main.Scorer.CHIPS_ADD))
        self.assertGreater(colored, 0)
        # A used-up line keeps the red used indicator.
        block.triggers_left = 0
        surface.fill(main.BLACK)
        block.draw(surface)
        red = sum(1 for x in range(main.GRID_SIZE) for y in range(main.GRID_SIZE)
                  if surface.get_at((x, y))[:3] == main.RED)
        self.assertGreater(red, 0)


    def test_no_effect_block_draws_no_effect_icon(self):
        # _draw_block_effect_icon draws nothing for a no-effect block (its
        # shape carries the scorer color instead).
        plain = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        plain.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        plain._draw_effect_icon(surface)
        self.assertTrue(all(surface.get_at((x, y))[:3] == (0, 0, 0)
                            for x in range(0, main.GRID_SIZE, 2)
                            for y in range(0, main.GRID_SIZE, 2)))


    def test_effect_block_shape_is_scorer_colored_with_black_icon(self):
        # A full block (shape + effect + scorer): the shape fills with the
        # scorer's color and the effect glyph is drawn in black on top.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            self.assertEqual(surface.get_at((2, 2))[:3], expected)      # colored shape
            self.assertEqual(surface.get_at((20, 20))[:3], main.BLACK)  # black icon
        finally:
            main.BLOCK_BORDERS_ON = prev


    def test_no_scorer_effect_block_keeps_black_shape_gray_icon(self):
        # A block with no scorer keeps the original look: a black shape with
        # a gray effect icon on top.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            self.assertEqual(surface.get_at((2, 2))[:3], main.BLACK)  # black shape
            self.assertEqual(surface.get_at((20, 20))[:3],
                             main.Scorer.color(main.Scorer.NONE))     # gray icon
        finally:
            main.BLOCK_BORDERS_ON = prev


    def test_none_shape_with_effect_dots_are_scorer_colored(self):
        # A Shape.NONE block with an effect draws its dotted square in the
        # scorer's color (the effect icon sits inside the dotted face), and the
        # dots are always drawn even when block borders are turned off. The
        # dotted square is inset 3px so it does not stick out of the cell.
        block = main.Block(0, 0, shape=main.Shape.NONE,
                           effect=main.Effect.BLACK_HOLE,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            # The top dashed edge starts 3px in, so (5, 3) is on a dot.
            self.assertEqual(surface.get_at((5, 3))[:3], expected)
            # The inset means the very edge of the cell is not dotted.
            self.assertEqual(surface.get_at((2, 2))[:3], main.BLACK)
        finally:
            main.BLOCK_BORDERS_ON = prev


    def test_none_shape_no_effect_dots_are_scorer_colored(self):
        # A Shape.NONE block with no effect has no icon, so its dotted lines
        # are drawn in the scorer's color (inset 3px inside the cell).
        block = main.Block(0, 0, shape=main.Shape.NONE,
                           scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
        block.rect.topleft = (0, 0)
        surface = pygame.Surface([main.GRID_SIZE] * 2)
        prev = main.BLOCK_BORDERS_ON
        try:
            main.BLOCK_BORDERS_ON = False
            block.draw(surface)
            expected = main.Scorer.color(main.Scorer.CHIPS_ADD)
            self.assertEqual(surface.get_at((5, 3))[:3], expected)
            # No effect -> no icon at the center (the background shows).
            self.assertEqual(surface.get_at(
                (main.GRID_SIZE // 2, main.GRID_SIZE // 2))[:3], main.BLACK)
        finally:
            main.BLOCK_BORDERS_ON = prev


    def test_board_title_hides_when_mouse_over_board(self):
        # The BOARD title shows while the mouse is outside the board panel and
        # hides while the mouse is over the board.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.assertTrue(self.game._show_marble_box_title())
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.MARBLE_BOX_COORDS[0] + 5,
                                      main.MARBLE_BOX_COORDS[1] + 5)):
            self.assertFalse(self.game._show_marble_box_title())


    def test_inventory_title_hides_when_mouse_over_inventory(self):
        # The INVENTORY title shows while the mouse is outside the inventory
        # panel and hides while the mouse is over it.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.assertTrue(self.game._show_toolbox_title())
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.TOOLBOX_COORDS[0] + 5,
                                      main.TOOLBOX_COORDS[1] + 5)):
            self.assertFalse(self.game._show_toolbox_title())


    def test_shop_title_hides_when_mouse_over_shop(self):
        # The SHOP title shows while the mouse is outside the shop panel and
        # hides while the mouse is over it.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.assertTrue(self.game._show_shop_title())
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.SHOP_COORDS[0] + 5,
                                      main.SHOP_COORDS[1] + 5)):
            self.assertFalse(self.game._show_shop_title())


    def test_titles_render_in_bottom_left_of_their_panels(self):
        # A fresh frame (mouse outside all three panels): BOARD, INVENTORY,
        # and SHOP titles all appear at the bottom-left of their panels.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.draw()
        self.assertTrue(self._region_has_white(self._marble_box_title_region()))
        self.assertTrue(self._region_has_white(self._toolbox_title_region()))
        self.assertTrue(self._region_has_white(self._shop_title_region()))


    def test_panel_titles_hide_when_mouse_over_their_panels(self):
        # Mousing over a panel hides only that panel's bottom-left title.
        # Over the board -> the board title hides, the others stay.
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.MARBLE_BOX_COORDS[0] + 5,
                                      main.MARBLE_BOX_COORDS[1] + 5)):
            self.game.draw()
        self.assertFalse(self._region_has_white(self._marble_box_title_region()))
        self.assertTrue(self._region_has_white(self._toolbox_title_region()))
        self.assertTrue(self._region_has_white(self._shop_title_region()))
        # Over the inventory -> the inventory title hides, the others stay.
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.TOOLBOX_COORDS[0] + 5,
                                      main.TOOLBOX_COORDS[1] + 5)):
            self.game.draw()
        self.assertTrue(self._region_has_white(self._marble_box_title_region()))
        self.assertFalse(self._region_has_white(self._toolbox_title_region()))
        self.assertTrue(self._region_has_white(self._shop_title_region()))
        # Over the shop -> the shop title hides, the others stay.
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=(main.SHOP_COORDS[0] + 5,
                                      main.SHOP_COORDS[1] + 5)):
            self.game.draw()
        self.assertTrue(self._region_has_white(self._marble_box_title_region()))
        self.assertTrue(self._region_has_white(self._toolbox_title_region()))
        self.assertFalse(self._region_has_white(self._shop_title_region()))


    def test_cash_readout_hover_opens_the_breakdown(self):
        # Hovering the shop's "Last run cash gained" readout targets the
        # breakdown, which reads like any other item's info box.
        self.game.last_run_cash_gained = 99
        self.game.last_run_cash_breakdown = {"base": 20, "interest": 4,
                                             "score": 30, "cards": 15,
                                             "scorers": 30}
        rect = main.ui.last_run_cash_rect(self.game)
        target, source = self.game._info_target_at(rect.center)
        self.assertIs(target, main.CASH_BREAKDOWN)
        self.assertEqual(source, "cash")
        self.assertEqual(self.game._item_name(target), "Last run cash gained")
        rows = self.game._describe_item(target)
        self.assertEqual([label for label, _ in rows],
                         ["Base cash", "Interest", "Beat the required score",
                          "Cash cards", "Cash/Lucky scorers", "Essence",
                          "Total"])
        body = " ".join(text for _, text in rows)
        # The Essence line is always shown (a run without the card pays $0),
        # and its prose names the flat amount the card itself would add.
        for amount in ("$20", "$4", "$30", "$15", "$10", "$99"):
            self.assertIn(amount, body)
        # The box lays out and draws like any other hover box.
        width, height, name_lines, desc_lines, hint = self.game._info_layout(
            target, "cash")
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertEqual(name_lines, ["Last run cash gained"])
        self.assertTrue(desc_lines)
        self.assertEqual(hint, "")
        with mock.patch("main.pygame.mouse.get_pos", return_value=rect.center), \
             mock.patch.object(self.game, "_draw_item_info") as draw:
            self.game.draw_sidebar()
        draw.assert_called_once()
        self.assertIs(draw.call_args[0][0], main.CASH_BREAKDOWN)
        self.assertEqual(draw.call_args[0][1], "cash")


    def test_fresh_shows_no_resource_point_line(self):
        # Fresh pays instantly, so owning it adds no points-to-next display.
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.FRESH, amount=1))
        self.assertEqual(self.game._resource_display(), [])


    def test_picky_resource_display_shows_slot_when_owned(self):
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.PICKY, amount=1))
        self.game.option_points = 1
        self.assertEqual(self.game._resource_display(), [(1, "slot")])


    def test_resource_display_shows_when_scorer_owned(self):
        # No point-banked resource scorer owned -> no lines under cash.
        self.assertEqual(self.game._resource_display(), [])
        # Owning the Shreds scorer as a component shows its points-to-next.
        self.game.toolbox.add(main.Component.scorer_component(main.Scorer.SHREDS, amount=1))
        self.game.shred_points = 1
        self.assertEqual(self.game._resource_display(), [(1, "card")])
        # Owning the Rubble scorer inside a block shows it too.
        self.game.toolbox.add(main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                             main.Scorer.RUBBLE, 1, 10, "Rubble Rect"))
        self.game.rubble_points = 1
        self.assertEqual(self.game._resource_display(), [(1, "card"), (1, "block")])


    def test_resource_display_shows_for_grid_block(self):
        self.game.grid[(1, 1)] = main.Block(1, 1, scorer=main.Scorer.IDEAS)
        self.game.idea_points = 3
        self.assertEqual(self.game._resource_display(), [(1, "action")])


    def test_sidebar_describes_a_key_lock_pair(self):
        item = main.BlockItem(0, 0, main.Shape.LOCK, main.Effect.NONE,
                              main.Scorer.NONE, 0, 20, "Lock", key_number=5)
        rows = dict(self.game._describe_item(item))
        self.assertIn("Pair", rows)
        self.assertIn("#5", rows["Pair"])
        self.assertIn("Key", rows["Pair"])
        # A placed half describes its pair too.
        block = main.Block(2, 2, shape=main.Shape.KEY, key_number=5)
        self.assertIn("Pair", dict(self.game._describe_item(block)))
        # A block with no pair has no Pair row.
        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.NONE, 0, 20, "Plain")
        self.assertNotIn("Pair", dict(self.game._describe_item(plain)))


    def test_the_deviation_token_is_coloured_by_its_sign(self):
        # The sidebar colours the deviation token: green above the average, red
        # below, grey for exactly average. Only a bare signed number counts, so
        # the game's other parentheses stay plain.
        self.assertEqual(main.ui._deviation_color("(+2)"), main.GREEN)
        self.assertEqual(main.ui._deviation_color("(-1)"), main.RED)
        self.assertEqual(main.ui._deviation_color("(0)"), main.GRAY)
        # A sentence mark after a token belongs to the sentence, not the token:
        # a resource-point row ends its count with one ("Gives 0.7 rubble point
        # (+0.2). 1 point converts into a random block").
        self.assertEqual(main.ui._deviation_color("(+0.2)."), main.GREEN)
        self.assertEqual(main.ui._deviation_color("(-0.2),"), main.RED)
        self.assertEqual(main.ui._deviation_color("(0);"), main.GRAY)
        for word in ("(including", "itself)", "(8", "px)", "(+35", "chips)",
                     "(both", "(1/4", "(2)", "???"):
            self.assertIsNone(main.ui._deviation_color(word), word)


    def test_the_info_box_paints_a_deviation_in_its_colour(self):
        # A rendered block sidebar: the green "(+15)" of a rolled-up +Chips
        # scorer must actually be painted green in the box.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=45)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_item_info(self.game, block, "toolbox", (5, 5))
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(self.game.screen.get_width())
                  for y in range(self.game.screen.get_height())}
        self.assertIn(main.GREEN, colors)
        self.assertNotIn(main.RED, colors)


    def test_the_info_box_paints_a_resource_points_deviation(self):
        # A resource-point row's token is coloured too, even though the sentence
        # carries on after it: "Gives 0.3 rubble point (-0.2). 1 point converts
        # into a random block". Nothing else in the box is red (the labels are
        # green, the body white), so a red pixel proves the token was painted.
        block = main.Block(0, 0, scorer=main.Scorer.RUBBLE, scorer_amount=0.6)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_item_info(self.game, block, "toolbox", (5, 5))
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(self.game.screen.get_width())
                  for y in range(self.game.screen.get_height())}
        self.assertIn(main.RED, colors)


    def test_sell_overlay_draws_no_sale_for_role_blocks(self):
        self.game.toolbox.items.clear()
        start = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.START, 0, 0, "Start")
        self.game.toolbox.add(start)
        self.game._equip_block(start)

        self.game.draw()  # the grey NO SALE overlay renders without raising

        self.assertTrue(self.game._unsellable(self.game.selected_toolbox_item))


    def test_a_drawn_role_scorer_becomes_a_plain_rect_block_in_the_shop(self):
        start = self.game.shop._scorer_offer(main.Scorer.START, 2, 1)

        self.assertEqual(start.kind, "block")
        self.assertEqual(start.shape, main.Shape.RECT)
        self.assertEqual(start.effects, [])
        self.assertEqual(start.scorer, main.Scorer.START)
        self.assertEqual(start.price, 109)
        self.assertEqual(start.name, "Start Block")

        finish = self.game.shop._scorer_offer(main.Scorer.FINISH, 2, 1)
        self.assertEqual(finish.kind, "block")
        self.assertEqual(finish.effects, [])
        self.assertEqual(finish.price, 53)
        self.assertEqual(finish.name, "Finish Block")

        # An ordinary scorer is still offered as a scorer component, carrying
        # its OWN rolled magnitude: a continuous deviation from the average.
        chips = self.game.shop._scorer_offer(main.Scorer.CHIPS_ADD, 2, 1)
        self.assertEqual(chips.kind, main.Component.SCORER)
        self.assertEqual(chips.value, main.Scorer.CHIPS_ADD)
        average = main.Scorer.DEFAULT_AMOUNT[main.Scorer.CHIPS_ADD]
        step = main.magnitude_step(average)
        self.assertGreaterEqual(chips.amount, main.scorer_magnitude_floor(main.Scorer.CHIPS_ADD))
        self.assertLessEqual(abs(chips.amount - average),
                             step * main.MAGNITUDE_MAX_STEPS)
        self.assertEqual(chips.price,
                         main.scorer_component_price(main.Scorer.CHIPS_ADD))


    def test_every_scorer_color_is_differentiable(self):
        # Every scorer's color must be clearly distinct from every other's:
        # each pair has to differ by at least 50 in at least one RGB channel
        # (e.g. two near-identical grays like old Rubble/Drill, or three
        # same-family blues like +Mult/Random/Summit, would fail this).
        colors = main.Scorer.COLORS
        scorers = list(main.Scorer.ORDER)
        worst = None
        worst_gap = 256
        for i, a in enumerate(scorers):
            for b in scorers[i + 1:]:
                gap = max(abs(colors[a][0] - colors[b][0]),
                          abs(colors[a][1] - colors[b][1]),
                          abs(colors[a][2] - colors[b][2]))
                if gap < worst_gap:
                    worst_gap = gap
                    worst = (main.Scorer.name(a), main.Scorer.name(b))
        self.assertGreaterEqual(
            worst_gap, 50,
            f"Scorer colors too similar: {worst} differ by only {worst_gap} "
            "in every channel")
        self.assertEqual(len(set(colors.values())), len(scorers))  # all unique


    def test_score_display_draws_with_current_scores(self):
        self.assertGreater(len(main.REQUIRED_SCORES), 0)
        self.game.score_chips = 123
        self.game.score_mult = 4
        self.game.score_total = 492

        # Should render without raising for both below and above the required score.
        self.game.draw()
        self.game.score_total = main.REQUIRED_SCORES[0] + 10
        self.game.draw()


    def test_score_display_draws_unique_count_and_normalized_factors(self):
        # The HUD renders the unique-type count and the D/T/U factor line (each
        # normalized 0..1) without raising.
        self.game.run_time = 2.0
        marble = self._add_marble()
        marble.distance = 500.0
        self.game.touched_shapes = {main.Shape.RECT, main.Shape.SLOPE}
        self.game.touched_effects = {main.Effect.BOUNCY}
        self.game.touched_scorers = {main.Scorer.CHIPS_ADD}
        self.game.draw()


    def test_draw_marble_box_spans_w_and_h_cells_from_topleft(self):
        surface = pygame.Surface((400, 400))
        surface.fill((0, 0, 0))
        x, y, w, h = 12, 20, 3, 2
        main.draw_marble_box(surface, x, y, w, h)
        # Background fills the whole panel interior, inside the border frame.
        self.assertEqual(surface.get_at((x + 8, y + 8))[:3], main.MARBLE_BOX_COLOR)
        self.assertEqual(surface.get_at((x + 8, y + main.GRID_SIZE * h - 8))[:3], main.MARBLE_BOX_COLOR)
        self.assertEqual(surface.get_at((x + main.GRID_SIZE * w - 8, y + 8))[:3], main.MARBLE_BOX_COLOR)
        # ...but nothing is drawn well beyond the panel: the border frame is
        # BORD_WIDTH thick and sits just outside each edge (so sample farther
        # out than the old 5px border test did).
        self.assertEqual(surface.get_at((x - 9, y))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((x, y - 9))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((x + main.GRID_SIZE * w + 9, y))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((x, y + main.GRID_SIZE * h + 9))[:3], (0, 0, 0))


    def test_draw_marble_box_draws_thick_outer_border_and_thin_inner_lines(self):
        surface = pygame.Surface((400, 400))
        surface.fill((0, 0, 0))
        x, y, w, h = 12, 12, 2, 2
        main.draw_marble_box(surface, x, y, w, h)
        grid = (30, 30, 30)
        # The thick outer border is drawn just OUTSIDE the panel's edges: each
        # border line is centered ~4px beyond its edge (a frame around the
        # grid), so sample each line's center along the box's midline.
        mid = main.GRID_SIZE  # halfway across the 2x2 panel
        left = x - main.BORD_WIDTH // 2 - 1
        right = x + w * main.GRID_SIZE + main.BORD_WIDTH // 2
        top = y - main.BORD_WIDTH // 2 - 1
        bottom = y + h * main.GRID_SIZE + main.BORD_WIDTH // 2
        self.assertEqual(surface.get_at((left, y + mid))[:3], grid)
        self.assertEqual(surface.get_at((right, y + mid))[:3], grid)
        self.assertEqual(surface.get_at((x + mid, top))[:3], grid)
        self.assertEqual(surface.get_at((x + mid, bottom))[:3], grid)
        # A single thin interior grid line splits the panel in half.
        self.assertEqual(surface.get_at((x + mid, y + mid))[:3], grid)
        self.assertEqual(surface.get_at((x + mid, y + 2))[:3], grid)
        self.assertEqual(surface.get_at((x + 2, y + mid))[:3], grid)


    def test_fire_draws_flames_when_passing(self):
        self.game.fire_intensity = 1.0
        self.game.draw()  # renders the flames along the top edge without raising


    def test_a_burning_trail_particle_burns_where_it_was_laid(self):
        # The marble's fire trail is the marble's OWN TRAIL PARTICLES: a dot laid
        # while the board is burning carries its own flame (see ui.TrailParticle),
        # standing where the marble was and streaming back the way the marble was
        # travelling THEN. So the fire lies along the path the marble actually
        # took and cannot swing about when the marble bounces — the dots already
        # laid burn on where they are, and only the dots laid afterwards take the
        # new direction.
        right = np.array([200.0, 0.0])
        down = np.array([0.0, 200.0])
        # One burning dot leans BACK the way its marble was going: its flame
        # reaches further behind the dot than in front of it, whether the marble
        # was travelling right or down.
        for velocity, back, front in ((right, (-1, 0), (1, 0)),
                                      (down, (0, -1), (0, 1))):
            single = pygame.Surface(self.game.screen.get_size())
            single.fill((0, 0, 0))
            main.ui.TrailParticle(200, 240, 4.0, main.WHITE, fire=2.0,
                                  velocity=velocity).draw(single)
            self.assertGreater(_flame_reach(single, 200, 240, *back), 2)
            self.assertGreater(_flame_reach(single, 200, 240, *back),
                               _flame_reach(single, 200, 240, *front))
        # A plain dot (the default) draws no fire at all.
        plain = pygame.Surface(self.game.screen.get_size())
        plain.fill((0, 0, 0))
        main.ui.TrailParticle(200, 240, 4.0, main.WHITE).draw(plain)
        self.assertFalse(_flame_pixel(plain, 200, 240, tol=1))
        # A chain of the dots a marble rolling right leaves behind it (4px apart,
        # see main.TRAIL_SPACING): the fire follows the whole path...
        trail = pygame.Surface(self.game.screen.get_size())
        trail.fill((0, 0, 0))
        for i in range(16):
            main.ui.TrailParticle(200 - i * 4, 240, 4.0, main.WHITE, fire=2.0,
                                  velocity=right).draw(trail)
        for dist in range(0, 60, 4):
            self.assertTrue(_flame_pixel(trail, 200 - dist, 240),
                            f"no flame {dist}px along the path")
        # ...and every pixel of it is the board fire's own palette: a burning dot
        # IS its flame, not a marble-coloured dot with a flame painted over it.
        for x in range(200 - 66, 200 + 8):
            for y in range(240 - 8, 240 + 8):
                self.assertIn(trail.get_at((x, y))[:3],
                              ((0, 0, 0), main.ui.FIRE_BODY_COLOR,
                               main.ui.FIRE_CORE_COLOR),
                              f"a stray pixel at {x},{y}")
        # A marble that turns around leaves the fire it has laid where it was:
        # with the marble back at the head of the trail and now travelling the
        # other way, the fire is still BEHIND it along the path it came down,
        # and there is none in the direction it is now heading.
        marble = main.Marble(200, 240)
        marble.velocity = np.array([-200.0, 0.0])  # bounced: heading back left
        main.ui.draw_marble(marble, trail, fire=2.0)
        self.assertTrue(_flame_pixel(trail, 200 - 40, 240))
        self.assertFalse(_flame_pixel(trail, 200 + 12, 240))
        # The halo and the wash are the marble's own (translucent heat, not
        # palette pixels): a warm ring beside it, and its face bluer than cold.
        cold = pygame.Surface(self.game.screen.get_size())
        lit = pygame.Surface(self.game.screen.get_size())
        cold.fill((0, 0, 0))
        lit.fill((0, 0, 0))
        main.ui.draw_marble(marble, lit, fire=2.0)
        main.ui.draw_marble(marble, cold)
        beside = (200, 240 - (int(marble.radius) + 2))
        self.assertEqual(cold.get_at(beside)[:3], (0, 0, 0))
        self.assertNotEqual(lit.get_at(beside)[:3], (0, 0, 0))
        face = (200 + int(marble.radius) // 2, 240)
        self.assertLess(lit.get_at(face)[2], cold.get_at(face)[2])
        # The game lays these particles itself — with the fire's strength at the
        # moment each dot was laid — and paints them, so a marble rolling while
        # the board burns leaves fire behind it.
        self.game.marbles = []
        self.game.run_active = True
        self.game.fire_intensity = 1.0
        rolling = self._add_marble((300, 500))
        rolling.velocity = np.array([300.0, 0.0])
        for _ in range(4):
            self.game.update()
        burning = [p for p in self.game.trail_particles if p.fire > 0]
        self.assertTrue(burning, "the rolling marble laid no burning dots")
        # The newest dot is still under the marble itself; the trail is what it
        # has left behind it and the marble's draw cannot cover.
        behind = [p for p in burning
                  if math.hypot(p.x - rolling.position[0],
                                p.y - rolling.position[1]) > rolling.radius + 2]
        self.assertTrue(behind, "no burning dot was left behind the marble")
        self.game.draw()
        for particle in behind:
            self.assertTrue(
                _flame_pixel(self.game.screen, int(particle.x),
                             int(particle.y)),
                f"the fire at {particle.x},{particle.y} is missing")


    def test_make_icon_draws_a_block_filling_the_surface(self):
        icon = main.make_icon()
        self.assertEqual(icon.get_size(), (main.GRID_SIZE, main.GRID_SIZE))
        # Something is really drawn, whatever random block the icon rolled:
        # at least one opaque pixel exists.
        self.assertTrue(any(icon.get_at((x, y))[3] > 0
                            for x in range(main.GRID_SIZE)
                            for y in range(main.GRID_SIZE)))
        # The "more than one colour" check is done on a FIXED block instead of
        # the random roll: peg + black hole (and any solid shape with borders
        # off) legitimately fills its cell with a single flat colour, which made
        # this test fail whenever the icon happened to roll one of those.
        prev = main.BLOCK_BORDERS_ON
        main.BLOCK_BORDERS_ON = True
        try:
            icon = pygame.Surface([main.GRID_SIZE] * 2, pygame.SRCALPHA)
            main.ui.draw_block(main.Block(0, 0, shape=main.Shape.RECT,
                                          effect=main.Effect.BOUNCY,
                                          scorer=main.Scorer.CHIPS_ADD,
                                          origin=(0, 0)), icon)
        finally:
            main.BLOCK_BORDERS_ON = prev
        colours = {icon.get_at((x, y))[:3] for x in range(main.GRID_SIZE)
                   for y in range(main.GRID_SIZE)}
        self.assertGreater(len(colours), 1)


    def test_make_icon_accepts_all_blocks_without_raising(self):
        # Every shape/effect/scorer combination must render onto the icon.
        for shape in main.Shape.ORDER:
            for effect in main.Effect.ORDER:
                for scorer in main.Scorer.ORDER:
                    icon = pygame.Surface([main.GRID_SIZE] * 2)
                    main.Block(0, 0, shape=shape, effect=effect, scorer=scorer,
                               origin=(0, 0)).draw(icon)


    def test_every_whole_card_match_group_and_action_has_icon_art(self):
        # Every whole card, match group and action must draw SOMETHING onto its
        # icon surface: a new item with no art branch renders as a blank tile
        # (a match-group card falls back to its letter glyph, but an action
        # icon is the only thing on the tile besides the version badge).
        canvas = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA)
        for group in components.MATCH_GROUPS:
            canvas.fill((0, 0, 0, 0))
            label = components.match_group_label(group)
            drawn = main.ui._draw_match_group_mini(
                canvas, group, (main.GRID_SIZE // 2, main.GRID_SIZE // 2),
                main.GRID_SIZE)
            if not drawn:
                # The "No Shape" group has no art of its own: its cards are
                # drawn with the group's letter glyph instead.
                self.assertEqual(group, ("shape", (main.Shape.NONE,)), label)
                continue
            self.assertGreater(canvas.get_bounding_rect().width, 0,
                               f"no icon art for the {label} group")
        for card in main.Card.ORDER:
            art = main.ui._build_whole_card_art(card)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               f"no icon art for card {main.Card.name(card)}")
        for action in main.Action.ORDER:
            art = main.ui._build_action_art(action)
            self.assertGreater(art.get_bounding_rect().width, 0,
                               f"no icon art for action {main.Action.name(action)}")
            # And each action's tile renders its icon (never the letter glyph).
            self.assertTrue(main.ui._draw_action_icon(
                pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA),
                action, (main.GRID_SIZE // 2, main.GRID_SIZE // 2),
                main.GRID_SIZE))
        # draw_action draws every action (shop/action area/info box/collection).
        canvas = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE), pygame.SRCALPHA)
        for action in main.Action.ORDER:
            main.ui.draw_action(canvas, main.ActionItem(action, 24),
                                pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE))


    def test_sidebar_describes_block_components_independently(self):
        item = main.BlockItem(0, 0, main.Shape.CURVED_SLOPE, main.Effect.GRAVITY,
                              main.Scorer.CHIPS_ADD, 10, 20, "Curved Slope +Chips")
        rows = self.game._describe_item(item)
        self.assertEqual([label for label, _ in rows],
                         ["Shape - Curved Slope", "Effect - Gravity", "Scorer - +Chips", "Trigger"])
        self.assertIn("arc", main.shape_description(item.shape))
        self.assertIn("gravity", main.effect_description(item.effect).lower())
        self.assertIn("10", main.scorer_description(item.scorer, item.scorer_amount))


    def test_sidebar_describes_component(self):
        shape = main.Component.shape_component(main.Shape.SLOPE)
        self.assertEqual([label for label, _ in self.game._describe_item(shape)], ["Shape - Slope"])
        effect = main.Component.effect_component(main.Effect.BOUNCY)
        self.assertEqual([label for label, _ in self.game._describe_item(effect)], ["Effect - Bouncy"])
        scorer = main.Component.scorer_component(main.Scorer.MULT_MUL, amount=3)
        self.assertEqual([label for label, _ in self.game._describe_item(scorer)], ["Scorer - xMult"])


    def test_info_box_targets_hovered_shop_item_without_buying(self):
        item = self.game.shop.items[0]
        cash_before = self.game.cash
        pos = (self.game.shop.rect.x + item.col * main.GRID_SIZE + 5,
               self.game.shop.rect.y + item.row * main.GRID_SIZE + 5)
        target, source = self.game._info_target_at(pos)
        self.assertIs(target, item)
        self.assertEqual(source, "shop")
        self.assertEqual(self.game.cash, cash_before)


    def test_info_box_layout_describes_item(self):
        # The hover info box lays out the item's name, price, description
        # rows, and a per-item action hint.
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        width, height, name_lines, desc_lines, hint = self.game._info_layout(block, "toolbox")
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertTrue(name_lines)
        self.assertTrue(desc_lines)
        self.assertTrue(hint)


    def test_draw_sidebar_is_noop_without_hovered_item(self):
        # The info box only appears when the cursor is over an item; hovering
        # empty space draws nothing.
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)), \
             mock.patch.object(self.game, "_draw_item_info") as draw:
            self.game.draw_sidebar()
        draw.assert_not_called()


    def test_draw_sidebar_renders_hovered_item(self):
        # Hovering over a toolbox item draws its info box.
        self.game.toolbox.items.clear()
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "B")
        self.game.toolbox.add(block)
        pos = (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5)
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch.object(self.game, "_draw_item_info") as draw:
            self.game.draw_sidebar()
        draw.assert_called_once()
        self.assertIs(draw.call_args[0][0], block)
        self.assertEqual(draw.call_args[0][1], "toolbox")


    def test_info_box_size_scales_with_description(self):
        # The box is sized to the description: an item with more effects and
        # more description text produces a taller (and wider) box.
        short = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 20, "S")
        long = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 20, "L",
                              effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE,
                                       main.Effect.GRAVITY, main.Effect.BOUNCY,
                                       main.Effect.ROTATE])
        w1, h1, *_ = self.game._info_layout(short, "toolbox")
        w2, h2, *_ = self.game._info_layout(long, "toolbox")
        self.assertGreater(h2, h1)  # more description rows -> taller box
        self.assertGreaterEqual(w2, w1)


    def test_info_box_rect_stays_onscreen(self):
        # A box near a screen edge is clamped so it stays fully on-screen.
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 20, "B")
        rect = self.game._info_box_rect(
            item, "toolbox", (main.SCREEN_WIDTH - 5, main.SCREEN_HEIGHT - 5))
        self.assertGreaterEqual(rect.left, 0)
        self.assertGreaterEqual(rect.top, 0)
        self.assertLessEqual(rect.right, main.SCREEN_WIDTH)
        self.assertLessEqual(rect.bottom, main.SCREEN_HEIGHT)


    def test_the_explorer_paints_the_units_a_marble_has_been_in(self):
        # While Explorer is owned, every board unit a marble has been in this
        # run is repainted in the title screen's own background colour, so the
        # player watches the card's measure fill square by square. draw_board
        # paints it, so it sits under the grid lines and every placed block.
        self.game.visited_cells = {(2, 3)}
        visited = self._grid_pos(2, 3)
        neighbour = self._grid_pos(3, 3)
        self.game.screen.fill(main.BG_COLOR)
        main.ui.draw_board(self.game)
        # Without the card every unit keeps the plain board colour.
        self.assertEqual(tuple(self.game.screen.get_at(visited))[:3],
                         main.MARBLE_BOX_COLOR)
        # The title screen's own background, read off a real title-screen draw.
        self.game.title_screen = True
        self.game.draw()
        title_bg = tuple(self.game.screen.get_at((4, 4)))[:3]
        self.game.title_screen = False
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        self.game.screen.fill(main.BG_COLOR)
        main.ui.draw_board(self.game)
        self.assertEqual(tuple(self.game.screen.get_at(visited))[:3], title_bg)
        # An unvisited unit is untouched, so the trail reads as a trail.
        self.assertEqual(tuple(self.game.screen.get_at(neighbour))[:3],
                         main.MARBLE_BOX_COLOR)
        # A card disabled for the run (Card cutter) applies no effect, so it
        # paints no trail either — see Game._has_card.
        self.game.disabled_card = self.game.cards[-1]
        self.game.screen.fill(main.BG_COLOR)
        main.ui.draw_board(self.game)
        self.assertEqual(tuple(self.game.screen.get_at(visited))[:3],
                         main.MARBLE_BOX_COLOR)


    def test_the_info_box_takes_the_same_colour_as_the_inventory(self):
        # The hover box is a panel like the inventory and the shop, so it is
        # filled with their colour (see panel_fill) — the running trial's own
        # tint — rather than the game's own panel colour, which under a trial
        # left it the only red box on a tinted screen.
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 20, "B")
        pos = (main.SCREEN_WIDTH // 2, main.SCREEN_HEIGHT // 2)
        self.game.trials_enabled = True
        self.game.final_boss = None
        self.game.current_trial = main.Trial.CRUMBLING
        self.game.screen.fill(main.BG_COLOR)
        self.game._draw_item_info(item, "toolbox", pos)
        rect = self.game._info_box_rect(item, "toolbox", pos)
        tint = main.ui.panel_fill(self.game)
        self.assertEqual(tint, main.Trial.panel_color(main.Trial.CRUMBLING))
        self.assertNotEqual(tint, main.MARBLE_BOX_COLOR)
        # Just inside the box's 5px black border, clear of the text (which
        # stops 12px short of the edge, see info_layout).
        inside = (rect.right - 8, rect.centery)
        self.assertEqual(tuple(self.game.screen.get_at(inside))[:3], tint)
        # Without a trial both the inventory and the box go back to the game's
        # own panel colour.
        self.game.current_trial = None
        self.game.screen.fill(main.BG_COLOR)
        self.game._draw_item_info(item, "toolbox", pos)
        self.assertEqual(tuple(self.game.screen.get_at(inside))[:3],
                         main.MARBLE_BOX_COLOR)


    def test_sidebar_describes_placed_block(self):
        block = main.Block(2, 3, shape=main.Shape.CURVED_SLOPE, effect=main.Effect.GRAVITY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        rows = self.game._describe_item(block)
        self.assertEqual([label for label, _ in rows],
                         ["Shape - Curved Slope", "Effect - Gravity", "Scorer - +Chips", "Trigger"])
        self.assertIn("arc", main.shape_description(block.shape))


    def test_sidebar_shows_trigger_limit_for_placed_block(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        block.triggers_left = 0
        rows = self.game._describe_item(block)
        trigger = next(text for label, text in rows if label == "Trigger")
        self.assertIn("once per run", trigger)
        self.assertIn("0 left", trigger)


    def test_sidebar_shows_trigger_limit_for_blockitem(self):
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD, 10, 20, "B")
        labels = [label for label, _ in self.game._describe_item(item)]
        self.assertIn("Trigger", labels)


    def test_item_name_includes_effects_shape_scorer_and_trigger_limit(self):
        # A slippery, fragile pipe that grants +chips twice per run.
        item = main.BlockItem(0, 0, main.Shape.PIPE, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                              10, 20, "Pipe +Chips", trigger_limit=2,
                              effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE])
        self.assertEqual(self.game._item_name(item), "Slippery Fragile Pipe +Chips v2")


    def test_item_name_for_placed_block_uses_parts(self):
        block = main.Block(0, 0, shape=main.Shape.PIPE, scorer=main.Scorer.CHIPS_ADD,
                           scorer_amount=10, trigger_limit=2,
                           effects=[main.Effect.SLIPPERY, main.Effect.FRAGILE])
        self.assertEqual(self.game._item_name(block), "Slippery Fragile Pipe +Chips v2")


    def test_item_name_omits_none_effect_and_shows_v1(self):
        # A block with no real effects reads "Shape Scorer v1".
        block = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        self.assertEqual(self.game._item_name(block), "Rect +Chips v1")


    def test_item_name_for_component_keeps_its_name(self):
        comp = main.Component.shape_component(main.Shape.PIPE)
        self.assertEqual(self.game._item_name(comp), "Pipe")


    def test_marble_types_draw_without_raising(self):
        # Every marble type renders (shaded sphere + rolling feature) without
        # raising, at rest and while spinning.
        for mt in main.MarbleType.ORDER:
            marble = main.Marble(400, 300)
            marble.marble_type = mt
            if mt == main.MarbleType.RUBBER_BALL:
                marble.color = (200, 50, 50)
                marble.color2 = (50, 50, 200)
            elif mt == main.MarbleType.PING_PONG:
                marble.color = main.PING_PONG_COLORS[0]
                marble.color2 = main.PING_PONG_COLORS[1]
            marble.spin_angle = 1.0
            marble.velocity = np.array([40.0, 0.0])
            marble.draw(self.game.screen)


    def test_sell_overlay_rect_is_bottom_right_toolbox_cell(self):
        rect = main.SELL_OVERLAY_RECT
        self.assertEqual(rect.right, self.game.toolbox.rect.right)
        self.assertEqual(rect.bottom, self.game.toolbox.rect.bottom)
        self.assertEqual((rect.width, rect.height), (main.GRID_SIZE, main.GRID_SIZE))


    def test_new_shapes_draw_without_raising(self):
        # Both the filled block draw and the outline-only icon draw handle each
        # new shape (borders on and off).
        for shape in self._new_shapes():
            for borders in (True, False):
                prev = main.BLOCK_BORDERS_ON
                main.BLOCK_BORDERS_ON = borders
                try:
                    surface = pygame.Surface([main.GRID_SIZE] * 2)
                    block = main.Block(0, 0, shape=shape,
                                       scorer=main.Scorer.CHIPS_ADD, origin=(0, 0))
                    block.draw(surface)
                    main.ui.draw_block_shape_only(
                        main.Block(0, 0, shape=shape, origin=(0, 0)), surface)
                finally:
                    main.BLOCK_BORDERS_ON = prev


    def test_card_scorer_draw_covers_every_scorer(self):
        # The shop's random card scorers are drawn from the full set, so no
        # scorer is quietly excluded from every card offer. (The per-condition
        # phase pools went with the conditions: there is one pool now.)
        random.seed(20240607)
        rolled = {main._random_card_scorer() for _ in range(400)}
        self.assertEqual(rolled, set(components.CARD_SCORERS))


    def test_xmult_collision_card_particles_are_red(self):
        # xMult rewards always multiply now, so their particle is always RED
        # (the removed add path was the only BLUE one).
        value = _group_card(main.match_group_for_shape(main.Shape.SLOPE),
                            main.Scorer.MULT_MUL)
        self.game.cards = [main.CardItem(value, 40)]
        self.game.score_mult = 1

        self._card_fire(main.Block(0, 5, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE))

        self.assertEqual(self.game.score_particles[-1].color, main.RED)


    def test_resource_display_shows_for_resource_scorer_card(self):
        # Owning a card built with a point-banked scorer shows its line.
        self.game.toolbox.items.clear()
        self.game.cards.clear()
        self.assertEqual(self.game._resource_display(), [])
        value = _group_card(main.match_group_for_shape(main.Shape.PIPE),
                            main.Scorer.IDEAS)
        self.game.cards.append(main.CardItem(value, 40))
        self.game.idea_run_gain = 1
        self.assertEqual(self.game._resource_display(), [(1, "action")])


    def test_shape_effect_cards_draw_their_shape_or_effect_icon(self):
        # Shape/effect cards render the icon of the shape/effect they are
        # based on (instead of a letter glyph) while keeping the card's
        # colored background.
        for value in (_shape_card_value(main.Shape.PIPE, components.Card.SCORE_MULT),
                      _effect_card_value(main.Effect.BOUNCY, components.Card.SCORE_MULT)):
            surf = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
            main.ui.draw_card(surf, main.CardItem(value, 18), surf.get_rect())
            bg = main.Card.COLORS[value]
            # A spot left of the centered icon keeps the card's background.
            self.assertEqual(surf.get_at((5, surf.get_height() // 2))[:3], bg)
            # The shape/effect icon is drawn somewhere in the card's interior.
            self.assertTrue(any(
                surf.get_at((x, y))[:3] != bg
                for x in range(8, surf.get_width() - 8)
                for y in range(8, surf.get_height() - 8)))


    # --- CRT screen filter (F2) -----------------------------------------

    def test_the_crt_filter_bends_darkens_and_scanlines_the_frame(self):
        # A flat frame makes the filter's own marks easy to read: the glass
        # curves the picture, the scanlines thin every other row, and the
        # vignette dims the sides and corners.
        width, height = main.SCREEN_WIDTH, main.SCREEN_HEIGHT
        surface = pygame.Surface((width, height))
        surface.fill((200, 200, 200))
        main.crt.apply(surface)
        middle = (width // 2, height // 2)
        # The middle keeps its colour, but on only one of two adjacent rows: the
        # other is a scanline gap.
        rows = [surface.get_at((middle[0], middle[1] + step))[0]
                for step in (0, 1)]
        self.assertGreater(max(rows), 190)
        self.assertLess(min(rows), max(rows) - 20)
        # The screen stays FILLED with the picture: curving the glass crops the
        # picture's own outer part away instead of framing it in black, so not
        # one pixel of the whole frame — corners and edges included — is dark.
        pixels = pygame.surfarray.array3d(surface)
        self.assertGreater(int(pixels.min()), 0)
        # The corners and the top/bottom edges are dimmer than the middle (the
        # vignette), but still clearly lit.
        for point in ((2, 2), (width - 3, 2), (2, height - 3),
                      (width // 2, 1), (width // 2, height - 2)):
            lit = max(surface.get_at((point[0], point[1] + step))[0]
                      for step in (0, 1))
            self.assertGreater(lit, 60, point)
            self.assertLess(lit, max(rows), point)
        # ...and the sides are dimmed the same way.
        side = max(surface.get_at((width - 30, middle[1] + step))[0]
                   for step in (0, 1))
        self.assertGreater(side, 0)
        self.assertLess(side, max(rows))
        # Running it again (a second frame) is harmless.
        main.crt.apply(surface)


    def test_the_crt_filter_magnifies_the_picture_to_fill_the_screen(self):
        # Sampling inwards along the tube's curve magnifies the picture, so
        # content close to an edge is pushed further out — past the edge, where
        # the curve crops it away — rather than pulled inwards and shrunk.
        width, height = main.SCREEN_WIDTH, main.SCREEN_HEIGHT
        surface = pygame.Surface((width, height))
        surface.fill((40, 40, 40))
        surface.fill(main.WHITE, pygame.Rect(0, 30, width, 3))
        main.crt.apply(surface)
        bright = [y for y in range(60)
                  if surface.get_at((width // 2, y))[:3][0] > 150]
        self.assertTrue(bright)
        # The line started at row 30 and has been pulled up the screen.
        self.assertLess(max(bright), 30)
        # Its mirror image near the bottom is pulled down the same way.
        surface.fill((40, 40, 40))
        surface.fill(main.WHITE, pygame.Rect(0, height - 33, width, 3))
        main.crt.apply(surface)
        bright = [y for y in range(height - 60, height)
                  if surface.get_at((width // 2, y))[:3][0] > 150]
        self.assertTrue(bright)
        self.assertGreater(min(bright), height - 33)


    def test_f2_toggles_the_crt_filter_and_remembers_it(self):
        # F2 flips the filter on every screen and the choice is stored with the
        # profile's other data, so it survives a relaunch.
        old_path, old_flag = metagame.FILE_PATH, self.game.crt_filter
        metagame.FILE_PATH = os.path.join(tempfile.mkdtemp(), "metagame.json")
        metagame.reset()
        try:
            self._press(pygame.K_F2)
            self.assertNotEqual(self.game.crt_filter, old_flag)
            self.assertEqual(metagame.crt_filter(), self.game.crt_filter)
            self.assertIn("CRT filter", self.game.shop_message)
            # Persisted: a fresh load of the same file agrees.
            metagame.reset()
            self.assertEqual(metagame.crt_filter(), self.game.crt_filter)
            self._press(pygame.K_F2)
            self.assertEqual(self.game.crt_filter, old_flag)
            metagame.reset()
            self.assertEqual(metagame.crt_filter(), old_flag)
        finally:
            metagame.FILE_PATH = old_path
            metagame.reset()
            self.game.crt_filter = old_flag


    def test_present_filters_the_frame_only_while_it_is_on(self):
        # The filter is the last thing done to a finished frame, and only while
        # it is switched on; the finished frame is then blitted to the window in
        # one go, so the window never shows a half-filtered (or unfiltered)
        # frame — that used to make the picture strobe.
        old_flag = self.game.crt_filter
        frame, display = self.game.screen, self.game.display
        try:
            # The game draws off-screen: the frame buffer is not the window.
            self.assertIsNot(frame, display)
            self.assertIs(display, pygame.display.get_surface())
            self.assertEqual(frame.get_size(),
                             (main.SCREEN_WIDTH, main.SCREEN_HEIGHT))
            with mock.patch("main.crt.apply") as apply, \
                    mock.patch("main.pygame.display.flip") as flip:
                self.game.crt_filter = True
                self.game._present()
                apply.assert_called_once_with(frame)
                self.assertTrue(flip.called)
                apply.reset_mock()
                self.game.crt_filter = False
                self.game._present()
                apply.assert_not_called()
                self.assertTrue(flip.called)
            # What the window shows is the FINISHED frame: with the filter off
            # it is the frame as drawn, and with it on it is the filtered one
            # (not the unfiltered one that was just drawn over).
            self.game.crt_filter = False
            frame.fill((10, 20, 30))
            self.game._present()
            self.assertEqual(display.get_at((5, 5))[:3], (10, 20, 30))
            self.game.crt_filter = True
            with mock.patch("main.crt.apply",
                            side_effect=lambda surface: surface.fill((0, 200, 0))):
                self.game._present()
            self.assertEqual(display.get_at((5, 5))[:3], (0, 200, 0))
        finally:
            self.game.crt_filter = old_flag


    def test_drawing_a_screen_does_not_present_it(self):
        # Presenting is _present's job ALONE (see run): a screen's draw function
        # that flipped the window itself would show its unfinished, unfiltered
        # frame for a moment before the filtered one, which is the flicker.
        old_title = self.game.title_screen
        try:
            with mock.patch("main.pygame.display.flip") as flip:
                self.game.title_screen = False
                main.ui.draw(self.game)
                flip.assert_not_called()
                self.game.title_screen = True
                main.ui.draw(self.game)
                flip.assert_not_called()
        finally:
            self.game.title_screen = old_title
        # ...and no screen in ui presents at all (the ones that used to be able
        # to are the menu screens).
        self.assertNotIn("pygame.display.flip", inspect.getsource(main.ui))


    def test_every_font_is_the_shared_garet_heavy_one(self):
        # ui's small labels used to build pygame's EMBEDDED default font inline
        # (Font(None, n)), so they were the one part of the game not drawn in
        # garet-heavy — and one Font per frame.
        source = inspect.getsource(main)
        self.assertEqual(source.count("Font(None"), 0)
        for module in (main.ui, main.cards, main.save_system, main.profiles,
                       main.achievements, main.collection, main.metagame, main.crt):
            self.assertEqual(inspect.getsource(module).count("pygame.font"), 0)
        # The only creation sites are the two lines of the table Game.__init__
        # builds (the garet-heavy roles, then the title face).
        self.assertEqual(source.count("pygame.font.Font"), 2)
        self.assertEqual(source.count("pygame.font.Font"),
                         inspect.getsource(main.Game.__init__).count(
                             "pygame.font.Font"))

        # Every role is bound to a garet-heavy font of the size it asks for...
        for role, size in main.FONT_SIZES.items():
            bound = main.ui.font(role)
            self.assertIs(bound, main.ui.FONTS[role])
            wanted = max(1, int(size * main.FONT_SCALE))
            self.assertEqual(bound.size("Hxg1"),
                             pygame.font.Font(main.GARET_FONT_PATH,
                                              wanted).size("Hxg1"))
            # ...which is not what the default font would have drawn for it.
            self.assertNotEqual(bound.size("Hxg1"),
                                pygame.font.Font(None, wanted).size("Hxg1"))
        # The title face is its own typeface, and every named attribute is the
        # very object in the table (so main's own screens and ui agree).
        self.assertEqual(main.ui.FONTS["title"].size("Hxg1"),
                         pygame.font.Font(main.TITLE_FONT_PATH, 90).size("Hxg1"))
        self.assertIs(main.ui.FONTS["tiny"], self.game.tiny_font)
        self.assertIs(main.ui.FONTS["small"], self.game.small_font)
        self.assertIs(main.ui.FONTS["font"], self.game.font)
        self.assertIs(main.ui.FONTS["required"], self.game.required_font)
        self.assertIs(main.ui.FONTS["total"], self.game.total_font)
        self.assertIs(main.ui.FONTS["title"], self.game.main_title_font)
        # Asking for a role nobody bound is a clear error, not a silent
        # fallback to some font built on the spot.
        with self.assertRaises(KeyError):
            main.ui.font("no-such-role")


    def test_drawing_never_builds_a_font(self):
        # The regression itself: each of these draws used to build a throwaway
        # default font of its own — for an 8 ball, one per marble per frame.
        screen = self.game.screen
        rect = pygame.Rect(0, 0, main.GRID_SIZE, main.GRID_SIZE)
        with mock.patch("main.pygame.font.Font") as build:
            key = main.Block(2, 2, shape=main.Shape.KEY, scorer=main.Scorer.CASH,
                             scorer_amount=15, origin=(80, 80))
            key.key_number = 3
            main.ui.draw_block(key, screen)
            portal = main.Block(3, 2, scorer=main.Scorer.CASH, scorer_amount=15,
                                origin=(120, 80),
                                effects=[main.Effect.PORTAL, main.Effect.BOUNCY])
            portal.portal_number = 2       # a pairing number AND the "+" mark
            main.ui.draw_block(portal, screen)
            main.ui.draw_token(screen, _token(main.Scorer.CASH, 15,
                                               runs_left=2), rect)
            main.ui.draw_action(screen, main.ActionItem(main.Action.DEATH, 24,
                                                        version=2), rect)
            # Ids with no art at all fall back to a letter glyph, and a version
            # tag rides on every action tile.
            for item in (main.CardItem(0, 24), main.ActionItem(0, 24)):
                main.ui.draw_card(screen, item, rect)
                main.ui.draw_action(screen, item, rect)
            main.ui._draw_match_group_mini(
                screen, main.match_group_for_shape(main.Shape.PIPE),
                rect.center, 12)
            main.ui._draw_marble_eight_feature(
                main.Marble(20, 20), pygame.Surface((40, 40), pygame.SRCALPHA),
                20, 20, 2 * main.MARBLE_RADIUS)
            build.assert_not_called()

        # The 8 ball's digit is cached per size instead of rebuilt per frame,
        # and a bigger marble gets a bigger digit.
        self.assertIs(main.ui._eight_digit(10), main.ui._eight_digit(10))
        self.assertGreater(main.ui._eight_digit(20).get_width(),
                           main.ui._eight_digit(10).get_width())


    def test_binding_hands_the_ui_the_live_games_fonts(self):
        # The table follows whichever Game is running (a fresh Game rebinds it).
        old = dict(main.ui.FONTS)
        try:
            fresh = main.Game()
            self.assertIs(main.ui.font("tiny"), fresh.tiny_font)
            self.assertIsNot(main.ui.font("tiny"), old["tiny"])
            self.assertIs(main.ui.font("mini"), fresh.fonts["mini"])
        finally:
            main.ui.bind_fonts(old)
        self.assertIs(main.ui.font("tiny"), self.game.tiny_font)


    def test_a_rolled_v2_action_shows_up_in_the_shop_and_in_grants(self):
        with mock.patch("main.random_action_version", return_value=2):
            self.game.shop.refresh()
            shop_actions = [i for i in self.game.shop.items if i.kind == "action"]
            self.assertTrue(shop_actions)
            self.assertTrue(all(a.version == 2 for a in shop_actions))
            self.game.actions.clear()
            self.assertTrue(self.game._grant_random_action())
            self.assertEqual(self.game.actions[-1].version, 2)

        with mock.patch("main.random_action_version", return_value=1):
            self.game.shop.refresh()
            self.assertTrue(all(a.version == 1 for a in self.game.shop.items
                                if a.kind == "action"))


    def test_an_upgraded_action_says_so_in_its_name_and_info_box(self):
        v1 = main.ActionItem(main.Action.DEATH, 24)
        v2 = main.ActionItem(main.Action.DEATH, 24, version=2)
        # Only the upgraded one carries its version in its name, so it reads as
        # upgraded in the messages and the info box's title.
        self.assertEqual(self.game._item_name(v1), "Death")
        self.assertEqual(self.game._item_name(v2), "Death v2")
        self.assertEqual(dict(self.game._describe_item(v1))["Version"],
                         "v1 — upgrade to v2 for "
                         f"${self.game._inflated(main.ACTION_UPGRADE_COST)}")
        upgraded_row = dict(self.game._describe_item(v2))["Version"]
        self.assertIn("v2", upgraded_row)
        self.assertIn("fully upgraded", upgraded_row)


    @unittest.skipUnless(hasattr(main.Card, "JOKER"), NAMED_CARDS_GONE)
    def test_pillar_card_particle_appears_near_fullest_column(self):
        # Pillar's start-phase particle pops when it adds mult for the fullest
        # column's blocks.
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(3, 0)] = main.Block(3, 0)
        self.game.grid[(3, 1)] = main.Block(3, 1)
        self.game.grid[(3, 2)] = main.Block(3, 2)  # column 3 is fullest
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(len(self.game.score_particles), 1)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "3")
        self.assertEqual(p.color, main.BLUE)


    @unittest.skipUnless(hasattr(main.Card, "JOKER"), NAMED_CARDS_GONE)
    def test_cards_spawn_one_particle_each_when_affecting_score(self):
        # Each card emits exactly one particle per score-affecting event, so
        # three cards affecting the score yield exactly three particles.
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.cards.append(main.CardItem(main.Card.BANKER, 25))
        self.game.grid[(0, 0)] = main.Block(0, 0)
        self.game.grid[(3, 0)] = main.Block(3, 0)
        self.game.grid[(3, 1)] = main.Block(3, 1)  # fullest column
        self.game.cards.append(main.CardItem(main.Card.PILLAR, 25))
        self.game.cash = 100
        self.game.score_chips = 1
        self.game.score_mult = 1
        self.game._apply_cards()
        self.assertEqual(len(self.game.score_particles), 3)


    def test_chips_block_spawns_green_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        self.assertEqual(len(self.game.score_particles), 1)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "10")
        self.assertEqual(p.color, main.GREEN)
        self.assertEqual((p.x, p.y), (block.rect.centerx, block.rect.centery))


    def test_mult_add_block_spawns_blue_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.MULT_ADD, scorer_amount=2)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "2")
        self.assertEqual(p.color, main.BLUE)


    def test_mult_mul_block_spawns_red_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.MULT_MUL, scorer_amount=1.5)
        marble = self._add_marble()
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game._handle_block_contacts([block])
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "1.5")
        self.assertEqual(p.color, main.RED)


    def test_quick_block_spawns_green_particle(self):
        block = main.Block(0, 0, scorer=main.Scorer.QUICK)
        marble = self._add_marble()
        marble.velocity = np.array([2000.0, 0.0])
        marble.collisions_this_tick = [block]
        self.game.run_active = True
        self.game.score_chips = 0
        self.game._handle_block_contacts([block])
        gained = int(2000.0 * main.QUICK_SCALE)
        p = self.game.score_particles[0]
        self.assertEqual(p.text, str(gained))
        self.assertEqual(p.color, main.GREEN)


    @unittest.skipUnless(hasattr(main.Card, "JOKER"), NAMED_CARDS_GONE)
    def test_joker_card_spawns_blue_particle_at_card_area(self):
        self.game.cards.append(main.CardItem(main.Card.JOKER, 20))
        self.game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)
        self.game.reset_run()
        p = self.game.score_particles[0]
        self.assertEqual(p.text, "4")
        self.assertEqual(p.color, main.BLUE)
        expected_x = main.CARD_AREA_COORDS[0] + main.GRID_SIZE // 2
        expected_y = main.CARD_AREA_COORDS[1] + main.GRID_SIZE // 2
        self.assertEqual((p.x, p.y), (expected_x, expected_y))


    @unittest.skipUnless(hasattr(main, "Condition"), CONDITIONS_COMMENTED_OUT)
    def test_explorer_card_spawns_red_particle_at_finish(self):
        self.game.cards.append(main.CardItem(main.Card.EXPLORER, 25))
        block = main.Block(0, 0, shape=main.Shape.SLOPE, scorer=main.Scorer.FINISH)
        marble = self._add_marble()
        # Half the board visited: 2 units, i.e. a x1.5 factor.
        self.game.visited_cells = {(gx, gy) for gx in range(main.GRID_WIDTH // 2)
                                   for gy in range(main.GRID_HEIGHT)}
        marble.collisions_this_tick = [block]
        marble.finished = True
        self.game.run_active = True
        self.game.run_complete = False
        self.game.score_mult = 1
        self.game._handle_block_contacts([block])
        factor = 1.5
        p = self.game.score_particles[0]
        self.assertEqual(p.text, self.game._particle_amount_text(factor))
        self.assertEqual(p.color, main.RED)
        # The popup appears where the run ended (on the marble), so it is
        # visible instead of being lost at the top-of-screen card area.
        self.assertEqual((p.x, p.y), (float(marble.position[0]), float(marble.position[1])))


    def test_score_particles_jump_up_fade_and_get_pruned(self):
        p = main.ScoreParticle(100, 100, "+10", main.GREEN, self.game.font)
        start_y = p.y
        for _ in range(60):
            p.update(main.DT)
        self.assertLess(p.y, start_y)  # jumped upward out of the block
        self.assertGreater(p.age, 0)
        self.assertFalse(p.dead())  # still fading
        self.game.score_particles.append(p)
        for _ in range(240):
            self.game.update()
        self.assertEqual(self.game.score_particles, [])  # faded away and pruned


    def test_score_particles_clear_on_new_game(self):
        self.game.score_particles.append(
            main.ScoreParticle(100, 100, "+10", main.GREEN, self.game.font))
        self.game.reset_game()
        self.assertEqual(self.game.score_particles, [])


    def test_trail_particle_shrinks_fades_and_dies(self):
        p = main.TrailParticle(100, 100, 4.0, main.MARBLE_COLOR)
        self.assertFalse(p.dead())
        # The trail dot is rendered on an SRCALPHA surface so it can fade.
        self.assertTrue(p._surf.get_flags() & main.pygame.SRCALPHA)
        surf = main.pygame.Surface((40, 40))
        p.draw(surf)  # draws without raising
        for _ in range(50):  # 50 frames = 0.83s > life 0.6s
            p.update(main.DT)
        self.assertTrue(p.dead())
        # After death the game prunes it from the trail list.
        game = main.Game()
        game.title_screen = False
        game.trail_particles = [p]
        for _ in range(10):
            game.update()
        self.assertEqual(game.trail_particles, [])


    def test_card_describes_and_draws(self):
        # A match-group card (Pipe x +Mult) has a name and description, draws,
        # and renders in the card area.
        card = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                          main.Scorer.MULT_ADD)
        rows = self.game._describe_item(card)
        self.assertTrue(any("Pipe" in label for label, _ in rows))
        self.assertTrue(any("+4 mult" in text for _, text in rows))
        surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        main.draw_shop_item(surface, card, surface.get_rect())
        self.game.cards.append(card)
        self.game.draw()  # renders the card area
        self.assertIn("Pipe", self.game._item_name(card))


    def test_only_a_rounds_covered_runs_draw_a_trial(self):
        # A run that plays a trial draws it fresh, run by run (exactly as the
        # game always did), while a run that plays no trial draws nothing.
        self.game.difficulty = main.Difficulty.LEVEL_3  # last two runs only
        with mock.patch("main.random.choice",
                        return_value=main.Trial.SPEEDRUN) as choice:
            self.game._choose_trial(0)  # the round's first run: no trial
            self.assertIsNone(self.game.current_trial)
            self.game._choose_trial(1)
            self.assertEqual(self.game.current_trial, main.Trial.SPEEDRUN)
            self.game._choose_trial(2)
            self.assertEqual(self.game.current_trial, main.Trial.SPEEDRUN)
        self.assertEqual(choice.call_count, 2, "one draw per trial run")


    def test_the_new_save_screen_picks_the_difficulty(self):
        # The picker's buttons set the level of the save about to begin (the
        # marble click then starts it with that level), and opening the screen
        # for a new save starts from the default level.
        old_saves = save_system.SAVES_DIR
        save_system.SAVES_DIR = tempfile.mkdtemp()
        try:
            save_system.begin_new_game_selection(self.game, 3)
            self.assertTrue(self.game.marble_selecting)
            self.assertEqual(self.game.difficulty, main.DEFAULT_DIFFICULTY)

            self._click(self.game.difficulty_button_rect(2).center)
            self.assertEqual(self.game.difficulty, main.Difficulty.LEVEL_3)

            # Picking the marble begins the save, and the chosen level (like
            # the upgrade toggle) survives the game reset that does it.
            save_system.start_new_game_with_marble(self.game, main.MarbleType.EIGHT_BALL)
            self.assertFalse(self.game.marble_selecting)
            self.assertEqual(self.game.difficulty, main.Difficulty.LEVEL_3)
            self.assertEqual(self.game.marble_type, main.MarbleType.EIGHT_BALL)
            self.assertEqual(self.game.save_slot, 3)
        finally:
            shutil.rmtree(save_system.SAVES_DIR, ignore_errors=True)
            save_system.SAVES_DIR = old_saves


    def test_trial_box_draws_title_and_description(self):
        # With no trial, the box draws nothing; with a trial it renders the
        # title + description without raising.
        self.game.current_trial = None
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.CARD_CUTTER
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.DEAD_ZONE
        self.game.draw_trial_box()
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.draw_trial_box()


    def test_the_screen_background_is_a_grid_of_the_running_trials_tile(self):
        # The WHOLE screen is covered in the running trial's tessellation, one
        # tile per lattice cell and nothing else drawn over it: the pattern is
        # the background as it is, with no shading pass on top.
        self.game.trials_enabled = True
        self.game.final_boss = None
        self.game.current_trial = main.Trial.SPEEDRUN
        size = main.ui.TILE_SIZE

        self.game.screen.fill((1, 2, 3))
        main.ui.draw_background(self.game)
        tile = main.ui._tile_art(main.Trial, main.Trial.SPEEDRUN)
        columns = main.SCREEN_WIDTH // size
        rows = main.SCREEN_HEIGHT // size
        for cell_x, cell_y, px, py in ((0, 0, 10, 10),
                                       (columns - 1, 0, size - 10, 10),
                                       (columns // 2, rows // 2, 40, 40),
                                       (0, rows - 1, 10, size - 10),
                                       (columns - 1, rows - 1, size - 10,
                                        size - 10)):
            with self.subTest(cell=(cell_x, cell_y)):
                self.assertEqual(
                    tuple(self.game.screen.get_at((cell_x * size + px,
                                                   cell_y * size + py)))[:3],
                    tuple(tile.get_at((px, py)))[:3],
                    f"cell ({cell_x}, {cell_y}) is not the trial's tile")

        # The whole screen is covered, edge to edge: the very last pixel is a
        # tile pixel too, not a leftover of the old flat fill.
        self.assertEqual(
            tuple(self.game.screen.get_at(
                (main.SCREEN_WIDTH - 1, main.SCREEN_HEIGHT - 1)))[:3],
            tuple(tile.get_at((size - 1, size - 1)))[:3])

        # A different trial paints a different pattern, and the background is
        # built once per trial.
        corner = (10, 10)
        self.game.current_trial = main.Trial.ALL_FINISHES
        main.ui.draw_background(self.game)
        self.assertNotEqual(tuple(self.game.screen.get_at(corner))[:3],
                            tuple(tile.get_at(corner))[:3])
        self.assertEqual(
            tuple(self.game.screen.get_at(corner))[:3],
            tuple(main.ui._tile_art(main.Trial,
                                    main.Trial.ALL_FINISHES).get_at(corner))[:3])
        self.assertIs(main.ui._tile_background(main.Trial, main.Trial.ALL_FINISHES),
                      main.ui._tile_background(main.Trial,
                                               main.Trial.ALL_FINISHES))

    def test_a_boss_run_wears_the_bosses_own_tile(self):
        # The final boss REPLACES the trial in the run's display, so the 24th
        # run is covered in — and tinted by — the boss's tile rather than the
        # rolled trial's. The trial's RULES still apply: only the art changes.
        self.game.trials_enabled = True
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.game.current_trial = main.Trial.SPEEDRUN
        size = main.ui.TILE_SIZE
        self.game.screen.fill((1, 2, 3))
        main.ui.draw_background(self.game)
        boss_tile = main.ui._tile_art(main.FinalBoss, main.FinalBoss.SKY_HIGH)
        trial_tile = main.ui._tile_art(main.Trial, main.Trial.SPEEDRUN)
        for cell_x, cell_y, px, py in ((0, 0, 10, 10),
                                       (main.SCREEN_WIDTH // size - 1, 0,
                                        size - 10, 10),
                                       (3, main.SCREEN_HEIGHT // size - 1, 40,
                                        size - 10)):
            with self.subTest(cell=(cell_x, cell_y)):
                got = tuple(self.game.screen.get_at(
                    (cell_x * size + px, cell_y * size + py)))[:3]
                self.assertEqual(got, tuple(boss_tile.get_at((px, py)))[:3])
        self.assertNotEqual(self._pixel_hash(boss_tile),
                            self._pixel_hash(trial_tile))
        # The panels take the boss's colour, and the trial the run is really
        # playing is still the one its effects come from.
        self.assertEqual(main.ui.panel_fill(self.game),
                         main.FinalBoss.panel_color(main.FinalBoss.SKY_HIGH))
        self.assertEqual(main.ui.locked_fill(self.game),
                         main.FinalBoss.locked_color(main.FinalBoss.SKY_HIGH))
        self.assertEqual(self.game.active_trial, main.Trial.SPEEDRUN)
        # With no boss (the endless runs after it, or any earlier run) the
        # trial's own tile is back.
        self.game.final_boss = None
        main.ui.draw_background(self.game)
        self.assertEqual(tuple(self.game.screen.get_at((10, 10)))[:3],
                         tuple(trial_tile.get_at((10, 10)))[:3])

    def test_a_running_trials_panels_take_its_own_colour(self):
        # The board, the inventory and the shop are filled with the running
        # trial's tile colour, a little lighter, so the play areas take the
        # run's palette instead of the game's own panel colour.
        self.game.trials_enabled = True
        self.game.final_boss = None
        self.game.unlocked_cells = {(x, y) for x in range(main.GRID_WIDTH)
                                    for y in range(main.GRID_HEIGHT)}
        self.game.screen.fill((1, 2, 3))
        self.game.current_trial = main.Trial.SPEEDRUN
        main.ui.draw(self.game)
        tint = main.Trial.panel_color(main.Trial.SPEEDRUN)
        self.assertEqual(tint, components.shade(main.Trial.COLORS[main.Trial.SPEEDRUN],
                                                main.Trial.PANEL_LIGHT))
        self.assertNotEqual(tint, main.MARBLE_BOX_COLOR)
        for label, pos in (("board", (main.MARBLE_BOX_COORDS[0] + 3,
                                      main.MARBLE_BOX_COORDS[1] + 3)),
                           ("inventory", (main.TOOLBOX_COORDS[0] + 3,
                                          main.TOOLBOX_COORDS[1] + 3)),
                           ("shop", (main.SHOP_COORDS[0] + 3,
                                     main.SHOP_COORDS[1] + 3))):
            with self.subTest(panel=label):
                self.assertEqual(tuple(self.game.screen.get_at(pos))[:3], tint)
        # A different trial tints them differently, and no trial at all keeps
        # the game's own panel colour.
        self.game.current_trial = main.Trial.CRUMBLING
        main.ui.draw(self.game)
        self.assertEqual(tuple(self.game.screen.get_at(
            (main.MARBLE_BOX_COORDS[0] + 3, main.MARBLE_BOX_COORDS[1] + 3)))[:3],
            main.Trial.panel_color(main.Trial.CRUMBLING))
        self.game.current_trial = None
        main.ui.draw(self.game)
        self.assertEqual(tuple(self.game.screen.get_at(
            (main.MARBLE_BOX_COORDS[0] + 3, main.MARBLE_BOX_COORDS[1] + 3)))[:3],
            main.MARBLE_BOX_COLOR)

    def test_the_panels_stay_readable_under_every_trial(self):
        # The panels carry white text, so no trial may tint them so light that
        # the text disappears — the near-white all-finishes tile goes the other
        # way and darkens them instead.
        for trial in main.Trial.ORDER:
            with self.subTest(trial=main.Trial.name(trial)):
                tint = main.Trial.panel_color(trial)
                brightness = sum(tint) / 3
                self.assertGreaterEqual(brightness, 40)
                self.assertLessEqual(brightness, main.Trial.PANEL_LIGHT_LIMIT + 40)
                if sum(main.Trial.COLORS[trial]) / 3 > main.Trial.PANEL_LIGHT_LIMIT:
                    self.assertLess(brightness,
                                    sum(main.Trial.COLORS[trial]) / 3,
                                    "a near-white tile darkens its panels")

    def test_locked_squares_take_a_darker_shade_only_while_a_trial_runs(self):
        # A locked board square is filled with a darker shade of the same trial
        # colour (see locked_fill), so it stays in the run's palette while still
        # reading as unlit. With the trial system switched off it goes back to
        # the void however the id happens to read — the same gate panel_fill has
        # (see Game.active_trial).
        self.game.current_trial = main.Trial.SPEEDRUN
        self.game.trials_enabled = False
        self.assertEqual(main.ui.locked_fill(self.game), main.BG_COLOR)
        self.assertEqual(main.ui.panel_fill(self.game), main.MARBLE_BOX_COLOR)
        self.game.trials_enabled = True
        locked = main.ui.locked_fill(self.game)
        panel = main.ui.panel_fill(self.game)
        self.assertEqual(locked, main.Trial.locked_color(main.Trial.SPEEDRUN))
        self.assertNotEqual(locked, panel)
        self.assertTrue(all(lo < pa for lo, pa in zip(locked, panel)),
                        (locked, panel))
        self.game.current_trial = None
        self.assertEqual(main.ui.locked_fill(self.game), main.BG_COLOR)

    def test_the_background_is_the_plain_colour_without_a_trial(self):
        # No trial running: the screen keeps the game's flat background colour.
        self.game.current_trial = None
        self.game.final_boss = None
        self.game.screen.fill((1, 2, 3))
        main.ui.draw_background(self.game)
        for pos in ((0, 0), (main.SCREEN_WIDTH - 1, 0),
                    (main.SCREEN_WIDTH // 2, main.SCREEN_HEIGHT // 2),
                    (0, main.SCREEN_HEIGHT - 1)):
            self.assertEqual(tuple(self.game.screen.get_at(pos))[:3],
                             main.BG_COLOR)

    def test_the_trial_display_takes_the_same_panel_colour_as_the_shop(self):
        # The display is a panel like the inventory and the shop, so it takes
        # the same fill (see panel_fill) — the trial's own colour while one runs,
        # and the game's own panel colour with none. It never carries the tile
        # itself: the tile is the SCREEN's background (see draw_background).
        box = main.TRIAL_BOX_RECT
        cases = (("trial", None, main.Trial.SPEEDRUN),
                 ("boss", main.FinalBoss.SINGULARITY, main.Trial.SPEEDRUN),
                 ("no trial", None, None))
        for label, boss, trial in cases:
            with self.subTest(case=label):
                self.game.final_boss = boss
                self.game.trials_enabled = True
                self.game.current_trial = trial
                self.game.screen.fill(main.BG_COLOR)
                self.game.draw_trial_box()
                fill = main.ui.panel_fill(self.game)
                if boss is None:
                    expected = (main.Trial.panel_color(trial)
                                if trial is not None else main.MARBLE_BOX_COLOR)
                else:
                    # The boss replaces the trial: its run wears the boss's own
                    # colour (see Game.tile_source).
                    expected = main.FinalBoss.panel_color(boss)
                self.assertEqual(fill, expected)
                # A 4px strip down the panel's left edge, clear of the rounded
                # corners: inside the panel, and out of reach of the centred
                # title and description, so a tile painted into the box would
                # show up here immediately.
                for pos in ((box.left + 4, box.top + 10),
                            (box.left + 4, box.top + 40),
                            (box.left + 4, box.bottom - 16)):
                    self.assertEqual(
                        tuple(self.game.screen.get_at(pos))[:3], fill)
        self.game.final_boss = None
        self.game.current_trial = main.Trial.SPEEDRUN

    def test_a_discovered_trials_collection_icon_is_its_tile(self):
        # The collection shows the same tile as the trial's icon...
        collection.discover_trial(main.Trial.SHUFFLED)
        entries = self.game._collection_entries()
        entry = next(e for e in entries
                     if e[0] == "trial" and e[1] == main.Trial.SHUFFLED)
        self.assertTrue(entry[4], "a trial needs an icon in the collection")
        self.assertTrue(entry[5], "the trial was just discovered")

        self.game.screen.fill(main.BG_COLOR)
        icon_rect = pygame.Rect(40, 40, main.GRID_SIZE, main.GRID_SIZE)
        main.ui.draw_collection_icon(self.game, "trial", main.Trial.SHUFFLED,
                                     icon_rect)
        tile = main.ui._tile_art(main.Trial, main.Trial.SHUFFLED)
        for px, py in ((10, 10), (30, 20), (20, 35)):
            self.assertEqual(tuple(self.game.screen.get_at(
                (icon_rect.x + px, icon_rect.y + py)))[:3],
                tuple(tile.get_at((px, py)))[:3])
        # ...while an undiscovered trial still shows the ??? square.
        entry = next(e for e in entries
                     if e[0] == "trial" and e[1] == main.Trial.INFLATION)
        self.assertTrue(entry[4])
        self.assertFalse(entry[5])

    def test_a_discovered_final_boss_icon_is_its_tile(self):
        # A final boss has icon art of its own now: its collection entry shows
        # the same tile its run is covered in, not the "???" square.
        collection.discover_final_boss(main.FinalBoss.SINGULARITY)
        entries = self.game._collection_entries()
        entry = next(e for e in entries
                     if e[0] == "final_boss"
                     and e[1] == main.FinalBoss.SINGULARITY)
        self.assertTrue(entry[4], "a final boss needs an icon in the collection")
        self.assertTrue(entry[5], "the boss was just discovered")

        self.game.screen.fill(main.BG_COLOR)
        icon_rect = pygame.Rect(40, 40, main.GRID_SIZE, main.GRID_SIZE)
        main.ui.draw_collection_icon(self.game, "final_boss",
                                     main.FinalBoss.SINGULARITY, icon_rect)
        tile = main.ui._tile_art(main.FinalBoss, main.FinalBoss.SINGULARITY)
        for px, py in ((10, 10), (30, 20), (20, 35)):
            self.assertEqual(tuple(self.game.screen.get_at(
                (icon_rect.x + px, icon_rect.y + py)))[:3],
                tuple(tile.get_at((px, py)))[:3])
        # The other boss wears its own tile, and an undiscovered boss still
        # shows the ??? square.
        self.assertNotEqual(
            self._pixel_hash(tile),
            self._pixel_hash(main.ui._tile_art(main.FinalBoss,
                                               main.FinalBoss.SKY_HIGH)))
        entry = next(e for e in entries
                     if e[0] == "final_boss" and e[1] == main.FinalBoss.SKY_HIGH)
        self.assertTrue(entry[4])
        self.assertFalse(entry[5])

    def test_trial_box_shows_no_trial_once_it_is_disabled(self):
        # Buying the trial away leaves the display up (showing NO TRIAL) so the
        # player can still click its halves; with trials switched off for the
        # save, the box disappears entirely.
        self.game.trials_enabled = True
        self.game.current_trial = None
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.screen.fill(main.BLACK)
            self.game.draw_trial_box()
        box = main.TRIAL_BOX_RECT
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(box.left, box.right)
                  for y in range(box.top, box.bottom)}
        self.assertIn((255, 215, 0), colors)  # the box border/title
        self.game.trials_enabled = False
        with mock.patch("main.pygame.mouse.get_pos", return_value=(0, 0)):
            self.game.screen.fill(main.BLACK)
            self.game.draw_trial_box()
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(box.left, box.right)
                  for y in range(box.top, box.bottom)}
        self.assertEqual(colors, {(0, 0, 0)})


    def test_trial_display_hover_shows_the_buy_options(self):
        # Hovering the display while building overlays the two options; a run
        # in progress (or the cursor elsewhere) shows none.
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.LONG_RUN
        self.game.cash = 1000
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=main.TRIAL_BOX_RECT.center), \
             mock.patch("main.ui.draw_trial_options") as draw:
            self.game.draw_trial_box()
        draw.assert_called_once()
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)), \
             mock.patch("main.ui.draw_trial_options") as draw:
            self.game.draw_trial_box()
        draw.assert_not_called()
        self.game.run_active = True
        with mock.patch("main.pygame.mouse.get_pos",
                        return_value=main.TRIAL_BOX_RECT.center), \
             mock.patch("main.ui.draw_trial_options") as draw:
            self.game.draw_trial_box()
        draw.assert_not_called()


    def test_trial_display_options_draw_without_raising(self):
        # The overlay renders in every combination (affordable / not, trial
        # running / not) and covers each half of the display.
        self.game.trials_enabled = True
        for trial in (main.Trial.LONG_RUN, None):
            for cash in (0, 1000):
                self.game.current_trial = trial
                self.game.cash = cash
                left, right = main.ui.draw_trial_options(
                    self.game, main.TRIAL_BOX_RECT)
                self.assertEqual(left.width, main.TRIAL_BOX_RECT.width // 2)
                self.assertEqual(right.right, main.TRIAL_BOX_RECT.right)


    def test_shop_message_sits_between_the_shop_title_and_the_refresh_button(self):
        # A shop dialog lives in the panel's bottom strip: right of the SHOP
        # title (bottom-left) and left of the REFRESH button (bottom-right).
        title_right = (main.SHOP_COORDS[0] + 8
                       + self.game.font.size("SHOP")[0])
        lines, rect = main.ui.shop_message_layout(self.game, "Refreshed shop ($20)")
        self.assertEqual(len(lines), 1)
        self.assertGreaterEqual(rect.left, title_right)
        self.assertLessEqual(rect.right, main.SHOP_REFRESH_BUTTON_RECT.left)
        self.assertEqual(rect.centery, main.SHOP_REFRESH_BUTTON_RECT.centery)
        self.assertGreater(rect.top, main.SHOP_COORDS[1] + 4 * main.GRID_SIZE)
        # A message too long for the gap wraps onto two tiny lines that both
        # stay inside it.
        long_lines, long_rect = main.ui.shop_message_layout(
            self.game, "Disassembled Slippery Fragile Pipe +Chips v2 ($56)")
        self.assertEqual(len(long_lines), 2)
        self.assertGreaterEqual(long_rect.left, title_right)
        self.assertLessEqual(long_rect.right, main.SHOP_REFRESH_BUTTON_RECT.left)
        self.assertEqual(long_rect.centery, main.SHOP_REFRESH_BUTTON_RECT.centery)


    def test_shop_message_draws_in_the_bottom_strip(self):
        # Drawing the shop with a message paints it where the layout puts it.
        self.game.shop_message = "Refreshed shop ($20)"
        _lines, rect = main.ui.shop_message_layout(self.game, self.game.shop_message)
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.screen.fill(main.BLACK)
            main.ui.draw_shop(self.game)
        colors = {self.game.screen.get_at((x, y))[:3]
                  for x in range(rect.left, rect.right)
                  for y in range(rect.top, rect.bottom)}
        self.assertIn(main.YELLOW, colors)


    def test_all_finishes_trial_draws_yellow_marble_box_border(self):
        # The marble-box outer border is gold (the finish scorer color) while
        # the all-finishes trial is ACTIVE, and the normal dark gray otherwise.
        # The thick border sits just above the box (centered at
        # y - BORD_WIDTH//2), so sample inside it rather than the fill below.
        border_px = (main.MARBLE_BOX_COORDS[0] + 20,
                     main.MARBLE_BOX_COORDS[1] - main.BORD_WIDTH // 2)
        self.game.trials_enabled = True
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.draw()
        self.assertEqual(self.game.screen.get_at(border_px)[:3],
                         main.Scorer.color(main.Scorer.FINISH))
        self.game.current_trial = main.Trial.HANDS_TIED
        self.game.draw()
        self.assertEqual(self.game.screen.get_at(border_px)[:3], (30, 30, 30))
        # A game with the trial system switched off holds an id it never plays
        # (see Game.active_trial), so the border must stay dark for it too.
        self.game.current_trial = main.Trial.ALL_FINISHES
        self.game.trials_enabled = False
        self.game.draw()
        self.assertEqual(self.game.screen.get_at(border_px)[:3], (30, 30, 30))


    def test_the_card_and_action_slots_share_one_square_back(self):
        # An empty action slot shows the very same back as an empty card slot
        # (they are the same slot in two trays), and a slot is a SQUARE cell of
        # its tray rather than a rounded card: with rounded corners the tray's
        # own fill would show through at the slot's corners.
        self.game.cards.clear()
        self.game.actions.clear()
        main.ui.draw(self.game)
        slot = main.GRID_SIZE
        card_slot = pygame.Rect(main.CARD_AREA_COORDS[0], main.CARD_AREA_COORDS[1],
                                slot, slot)
        action_slot = pygame.Rect(main.ACTION_AREA_COORDS[0],
                                  main.ACTION_AREA_COORDS[1], slot, slot)
        for dx in range(slot):
            for dy in range(slot):
                self.assertEqual(
                    tuple(self.game.screen.get_at(
                        (card_slot.left + dx, card_slot.top + dy)))[:3],
                    tuple(self.game.screen.get_at(
                        (action_slot.left + dx, action_slot.top + dy)))[:3],
                    (dx, dy))
        # Every corner is the back's own colour (its fill or its 2px border),
        # never the tray showing through a rounded corner.
        back = ((70, 60, 100), (130, 120, 170))
        for px, py in ((0, 0), (slot - 1, 0), (0, slot - 1), (slot - 1, slot - 1)):
            self.assertIn(tuple(self.game.screen.get_at(
                (card_slot.left + px, card_slot.top + py)))[:3], back, (px, py))

    def test_disabled_card_draws_dimmed(self):
        joker = _card_item(main.match_group_for_shape(main.Shape.PIPE),
                           main.Scorer.MULT_ADD)
        self.game.cards.append(joker)
        self.game.disabled_card = joker
        self.game.draw()  # renders the dimmed card without raising

        # A card disabled by the Card cutter trial is dimmed, so the player can
        # see which card got cut.
        rect = main.pygame.Rect(main.CARD_AREA_COORDS[0], main.CARD_AREA_COORDS[1],
                                main.GRID_SIZE, main.GRID_SIZE)

        def brightness():
            return sum(sum(self.game.screen.get_at((x, y))[:3])
                       for x in range(rect.left, rect.right)
                       for y in range(rect.top, rect.bottom))

        self.game.disabled_card = None
        self.game.draw()
        plain = brightness()
        self.game.disabled_card = joker
        self.game.draw()
        cut = brightness()
        self.assertLess(cut, plain)


    def test_title_screen_achievements_button_opens_tab(self):
        # The title screen's ACHIEVEMENTS button opens the achievements tab.
        self.game.title_screen = True
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        pos = main.ACHIEVEMENTS_BUTTON_RECT.center
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()
        self.assertFalse(self.game.title_screen)
        self.assertTrue(self.game.achievements_open)


    def test_title_screen_ignores_clicks_away_from_slots(self):
        self.game.title_screen = True
        event = mock.Mock()
        event.type = main.pygame.MOUSEBUTTONDOWN
        event.button = 1
        with mock.patch("main.pygame.mouse.get_pos", return_value=(20, 20)), \
             mock.patch("main.pygame.event.get", return_value=[event]):
            self.game.handle_events()
        self.assertTrue(self.game.title_screen)  # still on the title screen


    def test_title_screen_draws_slots_and_achievements_button(self):
        self.game.title_screen = True
        self.game.draw()  # renders the title + save slots + ACHIEVEMENTS button
        self.assertTrue(main.ACHIEVEMENTS_BUTTON_RECT.collidepoint(main.ACHIEVEMENTS_BUTTON_RECT.center))
        # After starting a game the normal game draws.
        self.game.title_screen = False
        self.game.draw()


    def test_touched_types_are_per_run_and_filtered(self):
        # A SLOPE block records its shape; each game starts with empty sets.
        game1 = main.Game()
        b1 = main.Block(0, 0, shape=main.Shape.SLOPE, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = main.Marble(300, 300)
        marble.collisions_this_tick = [b1]
        game1.marbles.append(marble)
        game1.run_active = True
        game1._handle_block_contacts([b1])
        self.assertEqual(game1.touched_shapes, {main.Shape.SLOPE})
        self.assertEqual(len(game1.touched_shapes) + len(game1.touched_effects) + len(game1.touched_scorers), 3)

        # A fresh game touching a RECT block records no shape (RECT is excluded
        # by the uniqueness filter), so only its effect and scorer count.
        game2 = main.Game()
        b2 = main.Block(1, 1, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                        scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble2 = main.Marble(300, 300)
        marble2.collisions_this_tick = [b2]
        game2.marbles.append(marble2)
        game2.run_active = True
        game2._handle_block_contacts([b2])
        self.assertEqual(game2.touched_shapes, set())
        self.assertEqual(len(game2.touched_shapes) + len(game2.touched_effects) + len(game2.touched_scorers), 2)


    def test_continuing_past_the_game_over_overlay_sets_up_the_next_run(self):
        # CONTINUE on the game-over screen resumes endless play with the next
        # run's own target and no boss (the run that ended there never got the
        # normal advance).
        self.game.run_number = main.TOTAL_RUNS
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.game.required_score = 12345
        self.game.game_over = True

        self._click(main.GAME_OVER_CONTINUE_BUTTON_RECT.center)

        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.continue_past_game_over)
        self.assertIsNone(self.game.final_boss)
        self.assertEqual(self.game.required_score,
                         main.get_next_required_score(main.TOTAL_RUNS))
        self.assertEqual(self.game.round_index,
                         main.TOTAL_RUNS // main.RUNS_PER_ROUND)
        self.assertEqual(self.game.run_in_round,
                         main.TOTAL_RUNS % main.RUNS_PER_ROUND)


    def test_boss_box_draws_title_and_description(self):
        # The trial box shows the final boss on the boss run without raising.
        self.game.final_boss = main.FinalBoss.SINGULARITY
        self.game.draw_trial_box()
        self.game.final_boss = main.FinalBoss.SKY_HIGH
        self.game.draw_trial_box()
        self.game.final_boss = None
        self.game.current_trial = None
        self.game.draw_trial_box()  # nothing to draw


    def test_the_info_box_reports_each_items_own_magnitude(self):
        # The sidebar (the game's only way to read a magnitude) names it for
        # both a placed block and a toolbox piece.
        block = main.Block(0, 0, shape=main.Shape.RECT,
                           effects=[main.Effect.PISTON],
                           effect_amounts={main.Effect.PISTON: 1800},
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=45)
        rows = dict(self.game._describe_item(block))
        self.assertIn("1800 px/s along its surface (+300)", rows["Effect - Piston"])
        self.assertIn("Adds 45 chips (+15)", rows["Scorer - +Chips"])
        piece = main.Component.effect_component(main.Effect.PISTON, magnitude=1800)
        rows = dict(self.game._describe_item(piece))
        self.assertIn("1800 px/s along its surface (+300)", rows["Effect - Piston"])


    def test_upgrade_overlay_rect_is_left_of_sell_rect(self):
        sell = main.SELL_OVERLAY_RECT
        up = main.UPGRADE_OVERLAY_RECT
        # Same row and size, sitting directly left of the SELL cell.
        self.assertEqual(up.top, sell.top)
        self.assertEqual(up.bottom, sell.bottom)
        self.assertEqual(up.height, sell.height)
        self.assertEqual(up.right, sell.left)


    def test_clicking_upgrade_overlay_raises_trigger_limit(self):
        block = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips")
        self.game.toolbox.items.clear()
        self.game.toolbox.add(block)
        self.game._equip_block(block)
        self.game.cash = 1000
        cost = self.game._trigger_upgrade_cost(block)

        self._click(main.UPGRADE_OVERLAY_RECT.center)

        self.assertEqual(block.trigger_limit, 2)
        self.assertEqual(self.game.cash, 1000 - cost)
        # Selection is preserved so the player can upgrade again.
        self.assertIs(self.game.selected_toolbox_item, block)


    def test_clicking_upgrade_overlay_with_component_does_nothing(self):
        comp = next(i for i in self.game.shop.items if i.kind == main.Component.SHAPE)
        self.game.selected_toolbox_item = comp
        self.game.cash = 1000

        self._click(main.UPGRADE_OVERLAY_RECT.center)

        self.assertEqual(self.game.cash, 1000)


    def test_sidebar_total_price_includes_trigger_upgrade_cash(self):
        upgraded = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                                  10, 50, "Rect +Chips", trigger_paid=120)
        # Total = original price + cash paid for trigger upgrades.
        self.assertEqual(self.game._total_price(upgraded), 170)

        plain = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE, main.Scorer.CHIPS_ADD,
                               10, 50, "Rect +Chips")
        self.assertIsNone(self.game._total_price(plain))  # no upgrades -> no total line

        # The info box renders an upgraded block (price + total) without raising.
        self.game.toolbox.items.clear()
        self.game.toolbox.add(upgraded)
        pos = (self.game.toolbox.rect.x + 5, self.game.toolbox.rect.y + 5)
        with mock.patch("main.pygame.mouse.get_pos", return_value=pos):
            self.game.draw_sidebar()


    def test_rotate_block_draws_effect_icon_and_geometry(self):
        # A rotating rect draws without raising and its effect icon renders.
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.draw(surface)
        # Geometry carries an effective angle that reflects the spin.
        block.spin = 30.0
        block._refresh_geometry()
        self.assertAlmostEqual(block.effective_angle, 30.0)


    def test_multi_effect_icon_draws_plus_marker(self):
        surface = pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        single = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                            effects=[main.Effect.BOUNCY])
        single.rect.topleft = (0, 0)  # center = (20, 20); plus would be at (30, 30)
        single._draw_effect_icon(surface)
        self.assertEqual(surface.get_at((30, 30))[:3], (0, 0, 0))  # no + for one effect

        multi = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                           effects=[main.Effect.BOUNCY, main.Effect.PISTON])
        multi.rect.topleft = (0, 0)
        multi._draw_effect_icon(surface)
        self.assertNotEqual(surface.get_at((30, 30))[:3], (0, 0, 0))  # + marks >1 effect


    def test_sidebar_describes_portal_block(self):
        block = main.Block(2, 3, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                           scorer=main.Scorer.NONE, portal_number=4)
        rows = self.game._describe_item(block)
        labels = [label for label, _ in rows]
        self.assertIn("Effect - Portal", labels)
        desc = next(text for label, text in rows if label == "Effect - Portal")
        self.assertIn("portal", desc.lower())


    def test_black_hole_icon_is_filled_circle_with_ring(self):
        surface = main.pygame.Surface((40, 40))
        blk = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.BLACK_HOLE,
                         scorer=main.Scorer.NONE)
        blk.rect.topleft = (0, 0)  # center = (20, 20)

        blk._draw_effect_icon(surface)

        self.assertNotEqual(surface.get_at((20, 20))[:3], (0, 0, 0))  # planet is filled
        # The ring extends left/right beyond the planet (planet radius 6).
        left_band = [surface.get_at((x, 20))[:3] for x in range(7, 14)]
        right_band = [surface.get_at((x, 20))[:3] for x in range(27, 34)]
        self.assertTrue(any(p != (0, 0, 0) for p in left_band))
        self.assertTrue(any(p != (0, 0, 0) for p in right_band))


    def test_the_codex_description_box_holds_five_lines(self):
        # The box grew from three lines to five, so a description that needs the
        # fifth line has it drawn (it used to be cut off after the third).
        # Showman is the entry used here: its description is exactly five lines
        # at the box's width (pinned below, so shortening it is noticed).
        self.assertEqual(main.ui.COLLECTION_DESC_LINES, 5)
        self.assertEqual(main.ui.COLLECTION_DESC_WIDTH,
                         main.ui.COLLECTION_CARD_W - 62)
        index = main.Card.ORDER.index(main.Card.SHOWMAN)
        description = main.Card.description(main.Card.SHOWMAN)
        lines = self.game._wrap_text(description, self.game.tiny_font,
                                    main.ui.COLLECTION_DESC_WIDTH)
        self.assertEqual(len(lines), 5, lines)
        collection.discover_card(main.Card.SHOWMAN)

        main.ui.draw_collection(self.game)

        x = 42 + (index % 5) * 226
        y = 118 + (index // 5) * (main.ui.COLLECTION_CARD_H + 14)
        # The fifth line's band: the lines start 34 px into the cell and step
        # 14 px, so line five sits at +90 (its ink stops well above the rarity
        # tag at +104).
        grey = (210, 210, 210)
        drawn = any(
            all(abs(a - b) <= 20 for a, b in
                zip(tuple(self.game.screen.get_at((px, py)))[:3], grey))
            for px in range(x + 54, x + 190)
            for py in range(y + 88, y + 102))
        self.assertTrue(drawn, "the fifth description line was not drawn")


    def test_every_codex_description_fits_its_box(self):
        # Every description in the codex is written to fit the box, so no
        # revealed entry has its text cut off (see ui.COLLECTION_DESC_LINES).
        self.game._unlock_entire_collection()
        for kind, value, name, desc, has_icon, discovered in self.game._collection_entries():
            with self.subTest(entry=f"{kind}:{name}"):
                lines = self.game._wrap_text(desc, self.game.tiny_font,
                                            main.ui.COLLECTION_DESC_WIDTH)
                self.assertLessEqual(len(lines), main.ui.COLLECTION_DESC_LINES,
                                     "\n".join(lines))


    def test_a_gondola_draws_two_cables_along_its_lane(self):
        # The user's rule: two cables spanning the area a gondola moves, in the
        # same direction as its motion (see ui._draw_gondola_cables). One car
        # sliding left/right and one sliding up/down cover both orientations.
        self.game.unlocked_cells = {(x, y) for x in range(main.GRID_WIDTH)
                                    for y in range(main.GRID_HEIGHT)}
        self.game.grid = {
            (2, 9): main.Block(2, 9, shape=main.Shape.RECT,
                               effect=main.Effect.GONDOLA, angle=90),
            (6, 9): main.Block(6, 9, shape=main.Shape.RECT,
                               effect=main.Effect.GONDOLA, angle=0),
            # A wall above the vertical car's lane, so its cable stops short of
            # the top of the board where its car could never go.
            (6, 3): main.Block(6, 3, shape=main.Shape.RECT),
        }
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.draw()
        cable = main.ui.GONDOLA_CABLE_COLOR
        x0, y0 = main.MARBLE_BOX_COORDS[0], main.MARBLE_BOX_COORDS[1]
        size = main.GRID_SIZE

        def pixel(x, y):
            return tuple(self.game.screen.get_at((x, y)))[:3]

        # The horizontal car: two lines along its own row, at the two sides of
        # its cell, reaching from the board's left edge to the vertical car's
        # cell — as far as its car can slide — and no further.
        lane = y0 + 9 * size + 3
        for y in (lane, lane + size - 6):
            for x in (x0 + 6, x0 + 6 * size - 6):     # the reachable span
                self.assertEqual(pixel(x, y), cable, (x, y))
            self.assertNotEqual(pixel(x0 + 8 * size + 5, y), cable, y)

        # The vertical car: two lines down its own column, stopping at the wall
        # above it (its car turns around under the wall's cell).
        column = x0 + 6 * size
        reach_top = y0 + 3 * size + size          # the wall's bottom edge
        for x in (column + 3, column + size - 3):
            for y in (reach_top + 1, y0 + 10 * size + 20):
                self.assertEqual(pixel(x, y), cable, (x, y))
            # Above the wall there is no cable: the car cannot get up there.
            self.assertNotEqual(pixel(x, y0 + 2 * size + 20), cable, x)

        # The cables go UNDER the blocks: inside the car's own cell the block
        # covers them, so the car reads as riding along its lane.
        car_middle = (x0 + 2 * size + size // 2, lane)
        self.assertNotEqual(pixel(*car_middle), cable)

        # Without a gondola there is no cable anywhere on the board.
        self.game.grid = {}
        with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
            self.game.draw()
        on_board = {pixel(x, y)
                    for x in range(x0, x0 + main.MARBLE_BOX_COORDS[2], 5)
                    for y in range(y0, y0 + main.MARBLE_BOX_COORDS[3], 5)}
        self.assertNotIn(cable, on_board)


    def test_a_held_shop_offer_is_framed_and_padlocked(self):
        # Hoard's held cell wears a gold frame and a padlock, so the player can
        # tell at a glance which offers a reroll will leave alone (see
        # ui._draw_shop_held_marker).
        self.game.cards.append(main.CardItem(main.Card.HOARD, 36))
        held = self.game.shop.items[0]
        rect = pygame.Rect(self.game.shop.rect.x + held.col * main.GRID_SIZE,
                           self.game.shop.rect.y + held.row * main.GRID_SIZE,
                           main.GRID_SIZE, main.GRID_SIZE)

        def draw():
            with mock.patch("main.pygame.mouse.get_pos", return_value=(5, 5)):
                self.game.screen.fill(main.BLACK)
                main.ui.draw_shop(self.game)

        draw()
        plain = self._pixel_hash(self.game.screen.subsurface(rect).copy())

        self.game.shop.locked = [self.game.shop.slot_key(held)]
        draw()
        marked = self._pixel_hash(self.game.screen.subsurface(rect).copy())

        self.assertNotEqual(marked, plain)
        # The frame sits on the cell's own edge, in the game's gold.
        self.assertEqual(
            tuple(self.game.screen.get_at((rect.left, rect.centery)))[:3],
            (255, 215, 0))
        # The padlock's dark plate and its gold body are both in the corner,
        # clear of the item's own art in the middle of the cell.
        corner = {(tuple(self.game.screen.get_at((x, y)))[:3])
                  for x in range(rect.left + 1, rect.left + 17)
                  for y in range(rect.top + 1, rect.top + 17)}
        self.assertIn((20, 20, 28), corner)
        self.assertIn((255, 215, 0), corner)
