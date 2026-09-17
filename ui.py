"""Everything that draws on the screen for Marblatro.

All rendering lives here: the block/marble drawing, the marble box / shop /
card drawing helpers, the floating screen elements (TrailParticle,
ScoreParticle, Popup), and every Game screen (title, game, HUD, game over,
marble select, upgrades, collection, achievements). Functions that used to be
methods take the object they draw as their first argument (``draw_block(block,
...)``, ``draw_marble(marble, ...)``, ``draw(game)``). main.py re-exports the
public names and keeps thin delegating method wrappers (``Block.draw``,
``Marble.draw``, ``Game.draw``, ...), so call sites and tests keep working.
"""

import math
import random
import sys

import numpy as np
import pygame

# main.py defines the constants/classes/modules these helpers draw and the
# modules the screens need; bind whatever module is actually running main.py at
# import time (the physics.py sys.modules pattern).
if "main" in sys.modules:
    _ui_source = sys.modules["main"]
elif "__main__" in sys.modules and hasattr(sys.modules["__main__"], "Block"):
    _ui_source = sys.modules["__main__"]
else:  # pragma: no cover - only when ui.py is imported standalone
    import main as _ui_source

BG_COLOR = _ui_source.BG_COLOR
BLACK = _ui_source.BLACK
BLOCK_INTERIOR_COLOR = _ui_source.BLOCK_INTERIOR_COLOR
BLUE = _ui_source.BLUE
BORD_WIDTH = _ui_source.BORD_WIDTH
BOARD_UNIT_COL = _ui_source.BOARD_UNIT_COL
BOARD_UNIT_PRICE = _ui_source.BOARD_UNIT_PRICE
BOARD_UNIT_ROW = _ui_source.BOARD_UNIT_ROW
ACTION_AREA_COORDS = _ui_source.ACTION_AREA_COORDS
ACTION_UPGRADE_COST = _ui_source.ACTION_UPGRADE_COST
ACTION_UPGRADE_RECT = _ui_source.ACTION_UPGRADE_RECT
CARD_AREA_COORDS = _ui_source.CARD_AREA_COORDS
CARD_COLOR = _ui_source.CARD_COLOR
Difficulty = _ui_source.Difficulty
GRAY = _ui_source.GRAY
GREEN = _ui_source.GREEN
GRID_HEIGHT = _ui_source.GRID_HEIGHT
GRID_SIZE = _ui_source.GRID_SIZE
GRID_WIDTH = _ui_source.GRID_WIDTH
MARBLE_BOX_COLOR = _ui_source.MARBLE_BOX_COLOR
MARBLE_BOX_COORDS = _ui_source.MARBLE_BOX_COORDS
MARBLE_RADIUS = _ui_source.MARBLE_RADIUS
MAX_ACTIONS = _ui_source.MAX_ACTIONS
MAX_CARDS = _ui_source.MAX_CARDS
ORANGE = _ui_source.ORANGE
PEG_RADIUS = _ui_source.PEG_RADIUS
points_text = _ui_source.points_text
RED = _ui_source.RED
ROUND_COUNT = _ui_source.ROUND_COUNT
RUN_DOT_DX = _ui_source.RUN_DOT_DX
RUN_DOT_DY = _ui_source.RUN_DOT_DY
RUN_DOT_GRID = _ui_source.RUN_DOT_GRID
RUN_DOT_RADIUS = _ui_source.RUN_DOT_RADIUS
RUNS_PER_ROUND = _ui_source.RUNS_PER_ROUND
SCREEN_HEIGHT = _ui_source.SCREEN_HEIGHT
SCREEN_WIDTH = _ui_source.SCREEN_WIDTH
SHOP_REFRESH_COST = _ui_source.SHOP_REFRESH_COST
TOTAL_RUNS = _ui_source.TOTAL_RUNS
TOKEN_COORDS = _ui_source.TOKEN_COORDS
TRAIL_LIFE = _ui_source.TRAIL_LIFE
TRIAL_BOX_COORDS = _ui_source.TRIAL_BOX_COORDS
TRIAL_CHANGE_COST = _ui_source.TRIAL_CHANGE_COST
TRIAL_DISABLE_COST = _ui_source.TRIAL_DISABLE_COST
WHITE = _ui_source.WHITE
YELLOW = _ui_source.YELLOW
# Fixed UI button/overlay rects (the constant-rect Game methods moved here).
ACHIEVEMENTS_BUTTON_RECT = _ui_source.ACHIEVEMENTS_BUTTON_RECT
ACHIEVEMENTS_RETURN_BUTTON_RECT = _ui_source.ACHIEVEMENTS_RETURN_BUTTON_RECT
ACTION_UPGRADE_RECT = _ui_source.ACTION_UPGRADE_RECT
COLLECTION_BACK_BUTTON_RECT = _ui_source.COLLECTION_BACK_BUTTON_RECT
COLLECTION_BUTTON_RECT = _ui_source.COLLECTION_BUTTON_RECT
PROFILE_BUTTON_RECT = _ui_source.PROFILE_BUTTON_RECT
GAME_OVER_CONTINUE_BUTTON_RECT = _ui_source.GAME_OVER_CONTINUE_BUTTON_RECT
GAME_OVER_MENU_BUTTON_RECT = _ui_source.GAME_OVER_MENU_BUTTON_RECT
GAME_OVER_NEW_BUTTON_RECT = _ui_source.GAME_OVER_NEW_BUTTON_RECT
MARBLE_BACK_BUTTON_RECT = _ui_source.MARBLE_BACK_BUTTON_RECT
MARBLE_UPGRADES_TOGGLE_RECT = _ui_source.MARBLE_UPGRADES_TOGGLE_RECT
RETURN_TO_MENU_BUTTON_RECT = _ui_source.RETURN_TO_MENU_BUTTON_RECT
SELL_OVERLAY_RECT = _ui_source.SELL_OVERLAY_RECT
SHOP_REFRESH_BUTTON_RECT = _ui_source.SHOP_REFRESH_BUTTON_RECT
TRIAL_BOX_RECT = _ui_source.TRIAL_BOX_RECT
UPGRADE_OVERLAY_RECT = _ui_source.UPGRADE_OVERLAY_RECT
UPGRADES_BACK_BUTTON_RECT = _ui_source.UPGRADES_BACK_BUTTON_RECT
UPGRADES_BUTTON_RECT = _ui_source.UPGRADES_BUTTON_RECT
ActionItem = _ui_source.ActionItem
Block = _ui_source.Block
BlockItem = _ui_source.BlockItem
CardItem = _ui_source.CardItem
MarbleType = _ui_source.MarbleType
achievements = _ui_source.achievements
collection = _ui_source.collection
metagame = _ui_source.metagame
profiles = _ui_source.profiles
save_system = _ui_source.save_system

# NOTE: ``_ui_source`` is kept (not deleted) so block_borders_on() can read
# the LIVE toggle value below.


def block_borders_on():
    """Read the live block-borders toggle from the running main module.

    The game and tests flip ``main.BLOCK_BORDERS_ON`` at runtime, so drawing
    must read the current value rather than a cached snapshot.
    """
    return _ui_source.BLOCK_BORDERS_ON

from components import (
    Action,
    Card,
    Component,
    Condition,
    Effect,
    FinalBoss,
    Scorer,
    Shape,
    Trial,
    condition_color,
    condition_effect,
    condition_glyph,
    condition_shape,
    splittable_card_condition_scorer,
)


def _fmt_tenth(value):
    """Format a score value for display, rounded to the nearest tenth.

    The chips/mult/total stay fractional internally; only the on-screen text
    rounds them. A whole number displays plainly (e.g. ``3``), a fractional
    one shows one decimal (e.g. ``3.5``).
    """
    rounded = round(value, 1)
    if float(rounded).is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def draw_marble_box(screen, x, y, w, h, border_color=(30, 30, 30)):
    """Draw a marble-box-styled grid panel.

    The panel's top-left corner sits at (x, y) pixels and it spans
    GRID_SIZE * w by GRID_SIZE * h pixels, divided into a w x h grid of
    cells. The outer border is thick and the interior lines are thin, the
    same look used for the marble box, the toolbox, and the shop.
    ``border_color`` tints the thick outer border (used by the all-finishes
    trial to paint the marble box's edges like a finish). The thick border
    lines are drawn last so they sit in front of the thin interior lines.
    """
    width = GRID_SIZE * w
    height = GRID_SIZE * h
    pygame.draw.rect(screen, MARBLE_BOX_COLOR, (x, y, width, height))
    # Thin interior grid lines first.
    for gx in range(1, w):
        gx_x = x + gx * GRID_SIZE
        pygame.draw.line(screen, (30, 30, 30), (gx_x, y), (gx_x, y + height), 1)
    for gy in range(1, h):
        gy_y = y + gy * GRID_SIZE
        pygame.draw.line(screen, (30, 30, 30), (x, gy_y), (x + width - 1, gy_y), 1)
    # The thick outer border, drawn last so it sits in front of the inner
    # lines at the box's edges (and the all-finishes trial's border color).
    for gx in (0, w):
        gx_x = x + gx * GRID_SIZE
        bord = -BORD_WIDTH // 2 - 1 if gx == 0 else BORD_WIDTH // 2
        line_w = BORD_WIDTH if gx == 0 else BORD_WIDTH + 1
        pygame.draw.line(screen, border_color, (gx_x + bord, y - BORD_WIDTH),
                         (gx_x + bord, y + height + BORD_WIDTH), line_w)
    for gy in (0, h):
        gy_y = y + gy * GRID_SIZE
        bord = -BORD_WIDTH // 2 - 1 if gy == 0 else BORD_WIDTH // 2
        line_w = BORD_WIDTH if gy == 0 else BORD_WIDTH + 1
        pygame.draw.line(screen, border_color, (x, gy_y + bord),
                         (x + width - 1, gy_y + bord), line_w)


def _draw_locked_boundary(game):
    """Outline the edge between the playable region and the locked squares.

    Every side of an unlocked square that faces a LOCKED square is drawn as a
    thick band in the board's own border colour and weight — the same border
    the box's outer edge gets (both use BORD_WIDTH) — so the playable region
    reads as one solid platform seated in the void instead of as tiles whose
    edges the thin grid lines blur together. Only mixed unlocked/locked sides
    are drawn (each boundary is visited from its unlocked side, so no band is
    drawn twice).

    The band sits ENTIRELY in the void just outside the playable region: its
    inner edge is flush with the shared edge, so a block or a marble sitting on
    the region's edge can never cover it — that is why the band starts a whole
    BORD_WIDTH outside the square instead of straddling the shared edge (and
    why it can be drawn with the board, under the blocks, at all). The outline
    hugs the region the way the outer border hugs the box.

    A band only runs past its own square at an end whose 6x6 corner square
    belongs to a LOCKED square (``up_left`` and friends): that is a corner of
    the region which the two bands meeting there have to fill between them, and
    it is also the only end where running on cannot paint the border over a
    square of the playable region. Everywhere else the bands of the neighbouring
    squares already meet edge to edge, so the outline stays continuous without a
    single pixel of it landing on the region.

    The band is always the dark board border colour, NOT the ``border_color``
    draw_board was handed: the all-finishes trial paints that one in the finish
    scorer's colour to say "this edge scores a finish", and the walls against
    the locked squares (see Game._board_wall_blocks) are invisible physics walls
    that never finish anything, so they must not claim to.
    """
    def locked(cx, cy):
        """True when that square exists and is still locked.

        Squares outside the grid read False, so the box's own edges are left to
        the outer border instead of collecting a band of their own.
        """
        return (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT
                and game.is_cell_locked(cx, cy))

    x0, y0 = MARBLE_BOX_COORDS[0], MARBLE_BOX_COORDS[1]
    for gy in range(GRID_HEIGHT):
        for gx in range(GRID_WIDTH):
            if game.is_cell_locked(gx, gy):
                continue
            left = x0 + gx * GRID_SIZE
            top = y0 + gy * GRID_SIZE
            right = left + GRID_SIZE
            bottom = top + GRID_SIZE
            # The four squares diagonal to this one: a band covers the 6x6
            # corner square at one of its ends only when that diagonal square
            # is locked, so no band ever reaches onto the playable region.
            over_up = BORD_WIDTH if locked(gx, gy - 1) else 0
            over_down = BORD_WIDTH if locked(gx, gy + 1) else 0
            over_left = BORD_WIDTH if locked(gx - 1, gy) else 0
            over_right = BORD_WIDTH if locked(gx + 1, gy) else 0
            up_left = BORD_WIDTH if locked(gx - 1, gy - 1) else 0
            up_right = BORD_WIDTH if locked(gx + 1, gy - 1) else 0
            down_left = BORD_WIDTH if locked(gx - 1, gy + 1) else 0
            down_right = BORD_WIDTH if locked(gx + 1, gy + 1) else 0
            bands = []
            if over_left:
                bands.append((left - BORD_WIDTH, top - up_left, BORD_WIDTH,
                              GRID_SIZE + up_left + down_left))
            if over_right:
                bands.append((right, top - up_right, BORD_WIDTH,
                              GRID_SIZE + up_right + down_right))
            if over_up:
                bands.append((left - up_left, top - BORD_WIDTH,
                              GRID_SIZE + up_left + up_right, BORD_WIDTH))
            if over_down:
                bands.append((left - down_left, bottom,
                              GRID_SIZE + down_left + down_right, BORD_WIDTH))
            for band in bands:
                pygame.draw.rect(game.screen, (30, 30, 30), band)


def draw_board(game, border_color=(30, 30, 30)):
    """Draw the dynamic marble box (the board), same look as draw_marble_box.

    Unlocked squares get the normal board fill; LOCKED squares are painted the
    background color so they read as part of the red void. The original thin
    grid overlay stays across the whole 10x15 area — including over locked
    squares — so the player can see every unit they can expand the board into.
    The boundary between the playable region and the locked squares gets a
    thick border of its own (see _draw_locked_boundary), and the thick outer
    border is drawn last exactly like draw_marble_box.
    """
    x, y = MARBLE_BOX_COORDS[0], MARBLE_BOX_COORDS[1]
    width = GRID_SIZE * GRID_WIDTH
    height = GRID_SIZE * GRID_HEIGHT
    # Normal board fill over the whole box, then locked squares repainted in
    # the background color so the playable region looks like it floats.
    pygame.draw.rect(game.screen, MARBLE_BOX_COLOR, (x, y, width, height))
    if game.board_locked():
        for gy in range(GRID_HEIGHT):
            for gx in range(GRID_WIDTH):
                if game.is_cell_locked(gx, gy):
                    pygame.draw.rect(game.screen, BG_COLOR,
                                     (x + gx * GRID_SIZE, y + gy * GRID_SIZE,
                                      GRID_SIZE, GRID_SIZE))
    # Thin interior grid lines (same style as draw_marble_box), across locked
    # squares too so their unit boundaries stay visible.
    for gx in range(1, GRID_WIDTH):
        gx_x = x + gx * GRID_SIZE
        pygame.draw.line(game.screen, (30, 30, 30), (gx_x, y), (gx_x, y + height), 1)
    for gy in range(1, GRID_HEIGHT):
        gy_y = y + gy * GRID_SIZE
        pygame.draw.line(game.screen, (30, 30, 30), (x, gy_y), (x + width - 1, gy_y), 1)
    # The locked squares make a wall around the playable region, outlined with
    # the board's own thick border: it lies just outside the region, so the
    # blocks, marbles and particles drawn after the board (see draw) can never
    # cover it. Drawn over the thin lines above, under the outer border below.
    if game.board_locked():
        _draw_locked_boundary(game)
    # The thick outer border, drawn last so it sits in front of the inner
    # lines at the box's edges (mirrors draw_marble_box).
    for gx in (0, GRID_WIDTH):
        gx_x = x + gx * GRID_SIZE
        bord = -BORD_WIDTH // 2 - 1 if gx == 0 else BORD_WIDTH // 2
        line_w = BORD_WIDTH if gx == 0 else BORD_WIDTH + 1
        pygame.draw.line(game.screen, border_color, (gx_x + bord, y - BORD_WIDTH),
                         (gx_x + bord, y + height + BORD_WIDTH), line_w)
    for gy in (0, GRID_HEIGHT):
        gy_y = y + gy * GRID_SIZE
        bord = -BORD_WIDTH // 2 - 1 if gy == 0 else BORD_WIDTH // 2
        line_w = BORD_WIDTH if gy == 0 else BORD_WIDTH + 1
        pygame.draw.line(game.screen, border_color, (x, gy_y + bord),
                         (x + width - 1, gy_y + bord), line_w)


def draw_shop_item(screen, item, rect):
    """Draw an item in a cell: full block UI for blocks, minimal UI for components."""
    if getattr(item, "kind", None) == "block":
        draw_block(Block(0, 0, shape=item.shape, effect=item.effect, scorer=item.scorer,
              scorer_amount=item.scorer_amount, origin=rect.topleft,
              portal_number=getattr(item, "portal_number", 0),
              key_number=getattr(item, "key_number", 0),
              effects=getattr(item, "effects", None)), screen)
    elif item.kind == Component.SHAPE:
        draw_block_shape_only(Block(0, 0, shape=item.value, origin=rect.topleft), screen)
    elif item.kind == Component.EFFECT:
        _draw_block_effect_icon(Block(0, 0, shape=Shape.RECT, effect=item.value, origin=rect.topleft), screen, color=BLACK)
    elif item.kind == Component.SCORER:
        pygame.draw.rect(screen, Scorer.color(item.value), rect)
        pygame.draw.rect(screen, WHITE, rect, 2)
    elif item.kind == Component.CONDITION:
        # A condition is a trigger tile: its white face with a center mini
        # shape/effect (collision conditions) or letter glyph (named ones).
        pygame.draw.rect(screen, condition_color(item.value), rect)
        pygame.draw.rect(screen, WHITE, rect, 2)
        _draw_condition_center(screen, item.value, rect, glyph_size=20)
    elif getattr(item, "kind", None) == "card":
        draw_card(screen, item, rect)
    elif getattr(item, "kind", None) == "action":
        draw_action(screen, item, rect)


def _draw_condition_mini(screen, shape, effect, center, size):
    """Draw a miniature image of a shape or effect, centered at ``center``.

    The shape is drawn as its black silhouette (the plain-block look) and the
    effect as its black icon — both read clearly on the light condition-tile
    and card faces that used to carry a letter glyph.
    """
    art = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
    block = Block(0, 0,
                  shape=(Shape.RECT if effect is not None else shape),
                  effect=(effect if effect is not None else Effect.NONE),
                  scorer=Scorer.NONE,
                  origin=(0, 0))
    if effect is not None:
        _draw_block_effect_icon(block, art, color=BLACK)
    else:
        _draw_block_shape(block, art, outline=BLACK, fill=BLACK)
    scaled = pygame.transform.smoothscale(art, (size, size))
    screen.blit(scaled, scaled.get_rect(center=center))


# ---------------------------------------------------------------------------
# Name-based icon art for the named conditions and the indivisible whole cards.
# Each icon is a small 40x40 black-on-transparent drawing that illustrates the
# item's NAME in the same hand-drawn style as the effect icons — a pillar for
# the Pillar condition, a paper plane for the Plane condition, a top hat for
# Showman, and so on — replacing the old single-letter glyph. The art is built
# once per item, cached, and scaled to the target size when drawn.
# ---------------------------------------------------------------------------
_ICON_ART_CACHE = {}
_ICON_INK = (0, 0, 0, 255)


def _icon_art_drawers(art, ink=_ICON_INK):
    """Small helpers that draw thick marks onto a 40x40 icon ``art``.

    ``ink`` defaults to the black used by the condition and whole-card icons;
    the action icons pass WHITE because an action's face is a saturated colour
    that black would sink into (the action tiles already draw white text and a
    white border).
    """
    def circle(x, y, rad, width=0):
        pygame.draw.circle(art, ink, (x, y), rad, width)

    def rect(x, y, w, h):
        pygame.draw.rect(art, ink, (x, y, w, h))

    def outline(x, y, w, h, width=3):
        pygame.draw.rect(art, ink, (x, y, w, h), width)

    def line(x1, y1, x2, y2, width=2):
        pygame.draw.line(art, ink, (x1, y1), (x2, y2), width)

    def polygon(points):
        pygame.draw.polygon(art, ink, points)

    def arc(x, y, w, h, start, end, width=3):
        """An elliptical arc, angles in degrees (pygame's own convention)."""
        pygame.draw.arc(art, ink, (x, y, w, h), math.radians(start),
                        math.radians(end), width)
    return circle, rect, outline, line, polygon, arc


def _build_named_condition_art(condition):
    """Draw the name-based icon art for a NAMED condition (a fresh surface)."""
    art = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
    c, r, rr, l, p, _arc = _icon_art_drawers(art)
    if condition == Condition.START:          # Joker -> a jester's hat
        p([(20, 3), (14, 19), (26, 19)])
        p([(6, 10), (10, 19), (17, 19)])
        p([(34, 10), (30, 19), (23, 19)])
        r(5, 19, 30, 4)
        c(8, 25, 3)
        c(32, 25, 3)
    elif condition == Condition.DISTANCE:     # Explorer -> a compass rose
        p([(20, 4), (15, 19), (25, 19)])
        p([(20, 36), (15, 21), (25, 21)])
        p([(36, 20), (21, 15), (21, 25)])
        p([(4, 20), (19, 15), (19, 25)])
        c(20, 20, 2)
    elif condition == Condition.BLACK_HOLE:   # Astronaut -> a suited astronaut figure
        c(20, 9, 5)                     # helmet (filled)
        r(14, 13, 12, 9)                # torso
        l(14, 15, 10, 21, 3)            # arm (left)
        l(26, 15, 30, 21, 3)            # arm (right)
        r(16, 22, 3, 7)                 # leg (left)
        r(21, 22, 3, 7)                 # leg (right)
        l(20, 4, 20, 1, 2)              # antenna
    elif condition == Condition.AIR_TIME:     # Plane -> a paper plane
        p([(36, 10), (6, 27), (21, 33)])
        p([(36, 10), (21, 33), (11, 25)])
    elif condition == Condition.FULLEST_COLUMN:  # Pillar -> a fluted column
        r(10, 4, 20, 3)                 # abacus
        p([(13, 7), (27, 7), (29, 13), (11, 13)])  # capital (flares down)
        l(15, 13, 15, 26, 2)            # shaft flute
        l(20, 13, 20, 26, 2)            # shaft flute
        l(25, 13, 25, 26, 2)            # shaft flute
        p([(11, 26), (29, 26), (31, 30), (9, 30)])  # base (flares down)
        r(8, 30, 24, 4)                 # plinth
    elif condition == Condition.CASH_HELD:    # Banker -> a coin
        c(20, 20, 13, 4)                # raised edge
        c(20, 20, 9, 2)                 # inner rim
    elif condition == Condition.FRAGILE_BREAKS:  # Wrecking Ball -> a ball smashing a wall
        r(30, 6, 6, 28)                 # the wall being broken
        l(32, 12, 34, 16, 2)            # cracks in the wall
        l(34, 16, 31, 21, 2)
        l(31, 21, 33, 25, 2)
        l(15, 4, 20, 11, 2)             # chain from a crane
        c(20, 20, 9)                    # the heavy ball
        l(4, 14, 10, 16, 2)             # motion lines behind the swing
        l(3, 22, 9, 23, 2)
    elif condition == Condition.SLIPPERY:     # Skater -> a skateboard
        pygame.draw.rect(art, _ICON_INK, (6, 14, 28, 6), border_radius=3)  # deck
        c(13, 26, 3)                     # wheel (back)
        c(29, 26, 3)                     # wheel (front)
        l(20, 20, 20, 23, 2)             # truck between the wheels
    elif condition == Condition.RANDOM:       # Glitch -> corrupted scan bars
        r(6, 8, 27, 5)                  # long bar
        r(5, 17, 12, 5)                 # middle row is split by a gap
        r(23, 17, 10, 5)
        r(13, 26, 22, 5)                # lower bar
    elif condition == Condition.FEW_BLOCKS:   # Ripped Card -> a card torn in two
        # Two separated card halves whose facing edges are jagged tears.
        p([(7, 9), (18, 9), (18, 22), (16, 28), (14, 22), (12, 28),
           (10, 23), (8, 28), (7, 24), (7, 9)])
        p([(23, 9), (33, 9), (33, 24), (31, 28), (30, 23), (28, 28),
           (26, 22), (24, 28), (23, 22), (23, 9)])
    elif condition == Condition.COZY:         # Cozy -> a small warm house
        p([(7, 20), (20, 9), (33, 20)])
        r(12, 20, 16, 14)
        r(24, 11, 5, 9)
        c(26, 8, 2)
        c(30, 5, 2)
    elif condition == Condition.PAINTING:     # Painting -> a canvas on an easel
        rr(8, 6, 24, 19, 3)             # canvas
        p([(13, 22), (20, 12), (27, 22)])   # a painted landscape on it
        c(25, 11, 2)                    # a painted sun
        l(20, 25, 13, 37, 3)            # easel leg (left)
        l(20, 25, 27, 37, 3)            # easel leg (right)
        l(20, 25, 20, 33, 2)            # easel leg (centre)
    elif condition == Condition.SYNTHESIZER:  # Synthesizer -> a waveform over a keyboard
        l(5, 13, 11, 6, 2)              # the waveform it generates
        l(11, 6, 17, 16, 2)
        l(17, 16, 23, 6, 2)
        l(23, 6, 29, 16, 2)
        l(29, 16, 35, 9, 2)
        rr(5, 21, 30, 13, 2)            # the keyboard body
        r(12, 21, 3, 8)                 # black keys
        r(20, 21, 3, 8)
        r(28, 21, 3, 8)
    return art


def _build_action_art(action):
    """Draw the icon art for an action (a fresh, white-ink surface).

    Action faces are saturated colours, so these icons are drawn in WHITE like
    the tile's own text and border; every other icon in the game is black on a
    lighter face. Each action gets a picture of what it does rather than a
    letter.
    """
    art = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
    # This builder strokes nothing (the action icons are filled shapes), so the
    # line drawer is unpacked unused.
    c, r, rr, _l, p, arc = _icon_art_drawers(art, WHITE)

    # Punching a fully transparent mark CUTS a hole in what has been drawn, so
    # an icon can be a solid silhouette with holes (a skull's sockets, a
    # ghost's eyes). draw writes the colour straight through, alpha included.
    def punch_circle(x, y, rad):
        pygame.draw.circle(art, (0, 0, 0, 0), (x, y), rad)

    def punch_rect(x, y, w, h):
        pygame.draw.rect(art, (0, 0, 0, 0), (x, y, w, h))

    def punch_polygon(points):
        pygame.draw.polygon(art, (0, 0, 0, 0), points)

    if action == Action.DEATH:                # a skull
        c(20, 15, 10)                   # cranium (solid)
        r(14, 22, 12, 9)                # jaw
        punch_circle(16, 14, 4)         # eye sockets
        punch_circle(24, 14, 4)
        punch_polygon([(20, 18), (18, 23), (22, 23)])   # nose
        punch_rect(17, 26, 2, 5)        # tooth gaps
        punch_rect(21, 26, 2, 5)
    elif action == Action.RECOGNITION:        # two sheets: a duplicate
        rr(6, 7, 16, 20, 3)             # the original
        rr(18, 13, 16, 20, 3)           # its copy, offset
    elif action == Action.DEJA_VU:            # an arrow looping back on itself
        arc(8, 8, 24, 24, -60, 250, 4)  # the loop (an almost-closed ring)
        p([(28, 3), (36, 10), (26, 13)])    # arrowhead at the open end
    elif action == Action.ANOINTMENT:         # sparkles (a blessing)
        p([(18, 5), (22, 18), (35, 22), (22, 26), (18, 39), (14, 26),
           (1, 22), (14, 18)])          # the big four-point sparkle
        p([(31, 26), (33, 31), (38, 33), (33, 35), (31, 40), (29, 35),
           (24, 33), (29, 31)])         # a smaller one beside it
    elif action == Action.STRENGTH:           # a barbell
        r(16, 17, 8, 6)                 # the bar's middle
        r(8, 12, 7, 16)                 # weight plate (left)
        r(25, 12, 7, 16)                # weight plate (right)
        r(4, 16, 4, 8)                  # outer collar (left)
        r(32, 16, 4, 8)                 # outer collar (right)
    elif action == Action.SPIRIT:             # a ghost
        p([(20, 4), (29, 11), (30, 20), (30, 33), (26, 27), (22, 33),
           (18, 27), (14, 33), (10, 27), (10, 20), (11, 11)])
        punch_circle(16, 17, 3)         # eyes, cut out of the body
        punch_circle(24, 17, 3)
    return art


def _build_whole_card_art(card):
    """Draw the name-based icon art for an indivisible whole card."""
    art = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
    c, r, rr, l, p, _arc = _icon_art_drawers(art)
    if card == Card.ERR_404:                  # a card that was not found
        rr(11, 8, 18, 24, 3)
        l(15, 12, 25, 28, 3)
        l(25, 12, 15, 28, 3)
    elif card == Card.BLUEPRINT:              # a drawing sheet with a plan
        rr(9, 6, 22, 26, 3)             # the sheet
        p([(17, 6), (9, 6), (9, 14)])   # folded top-left corner
        l(13, 28, 27, 14, 2)            # a diagonal plan line
        l(15, 24, 17, 26, 2)            # measurement tick
        l(23, 16, 25, 18, 2)            # measurement tick
    elif card == Card.SHOWMAN:                # a top hat
        pygame.draw.rect(art, _ICON_INK, (16, 4, 8, 20), border_radius=2)  # tall crown
        pygame.draw.rect(art, _ICON_INK, (6, 22, 28, 4), border_radius=2)  # wide brim
    elif card == Card.GARDEN:                 # a flower on a stem
        for cx, cy in ((20, 5.5), (25.3, 7.8), (27.5, 13), (25.3, 18.2),
                       (20, 20.5), (14.7, 18.2), (12.5, 13), (14.7, 7.8)):
            c(cx, cy, 3)
        c(20, 13, 4.5)
        l(20, 20.5, 20, 33, 3)
        p([(20, 26), (10, 24), (9, 30), (20, 32)])
        p([(20, 26), (30, 24), (31, 30), (20, 32)])
    elif card == Card.RIGGED_CASINO:          # a die
        rr(9, 9, 22, 22, 4)
        c(15, 15, 2.5)
        c(25, 15, 2.5)
        c(20, 20, 2.5)
        c(15, 25, 2.5)
        c(25, 25, 2.5)
    elif card == Card.CONQUISTADOR:           # a banner claiming the board
        l(10, 5, 10, 35, 3)
        p([(13, 6), (35, 6), (30, 12), (35, 18), (13, 18)])
    elif card == Card.PEDESTAL:               # a trophy on a plinth
        p([(13, 6), (27, 6), (24, 17), (16, 17)])   # the cup
        l(13, 7, 8, 12, 2)              # handle (left)
        l(27, 7, 32, 12, 2)             # handle (right)
        r(18, 17, 4, 4)                 # stem
        r(11, 21, 18, 4)                # plinth cap
        r(15, 25, 10, 6)                # plinth shaft
        r(9, 31, 22, 4)                 # plinth base
    elif card == Card.INFERNO:                # flames rising
        p([(20, 3), (27, 21), (13, 21)])          # centre flame
        p([(8, 11), (14, 23), (4, 23)])           # left flame
        p([(32, 11), (36, 23), (26, 23)])         # right flame
        r(3, 27, 34, 4)                 # burning ground
    elif card == Card.DOPPELGANGER:           # two marbles instead of one
        c(13, 15, 8)                    # the original
        c(28, 24, 8)                    # its double
        l(4, 33, 11, 33, 2)             # motion ticks behind the double
        l(6, 37, 13, 37, 2)
    elif card == Card.COMPOUND_INTEREST:      # growing bars with an up arrow
        r(5, 28, 30, 5)                 # year one
        r(9, 22, 22, 5)                 # year two
        r(13, 16, 14, 5)                # year three
        l(31, 13, 31, 4, 3)             # arrow shaft
        p([(31, 1), (27, 8), (35, 8)])  # arrow head
    elif card == Card.COUPON:                 # a clipped coupon
        rr(6, 12, 28, 16, 3)            # the coupon
        l(20, 12, 20, 16, 2)            # perforation (top half)
        l(20, 24, 20, 28, 2)            # perforation (bottom half)
        l(11, 18, 16, 18, 2)            # printed lines
        l(11, 22, 16, 22, 2)
        l(24, 18, 29, 18, 2)
        l(24, 22, 29, 22, 2)
    elif card == Card.FACTORY:                # a factory with a sawtooth roof
        r(5, 26, 30, 8)                 # the hall
        p([(5, 26), (5, 16), (12, 21), (12, 16), (19, 21),
           (19, 16), (26, 21), (26, 26)])          # sawtooth roof
        r(29, 10, 5, 13)                # chimney
        c(31, 5, 2)                     # smoke
        c(35, 3, 2)
    elif card == Card.MINESHAFT:              # a shaft with a ladder down it
        l(11, 6, 11, 37, 3)             # shaft wall (left)
        l(29, 6, 29, 37, 3)             # shaft wall (right)
        for ry in (13, 20, 27, 34):     # ladder rungs
            l(11, ry, 29, ry, 2)
        c(20, 3, 2)                     # a winch wheel above the shaft
    elif card == Card.MARKET:                 # a market stall
        p([(3, 12), (37, 12), (33, 21), (7, 21)])     # awning
        l(13, 12, 13, 21, 2)            # awning stripes
        l(20, 12, 20, 21, 2)
        l(27, 12, 27, 21, 2)
        r(7, 25, 26, 4)                 # counter
        l(9, 29, 9, 36, 3)              # legs
        l(31, 29, 31, 36, 3)
    elif card == Card.WATCH:                  # a pocket watch
        c(20, 23, 13, 3)                # case
        c(20, 23, 10, 2)                # dial
        l(20, 23, 20, 15, 3)            # minute hand
        l(20, 23, 26, 23, 3)            # hour hand
        r(17, 6, 6, 5)                  # stem
        c(20, 3, 2, 2)                  # bow
    elif card == Card.TESSERACT:              # a cube inside a cube
        rr(4, 11, 32, 26, 2)            # the outer cube
        rr(13, 17, 14, 14, 2)           # the inner cube, nested inside it
        l(4, 11, 13, 17, 2)             # the four edges joining the corners
        l(36, 11, 27, 17, 2)
        l(36, 37, 27, 31, 2)
        l(4, 37, 13, 31, 2)
    elif card == Card.THOUSAND_HANDED:        # the thousand-armed bodhisattva
        # A haloed, seated figure with a fan of arms out of its shoulders (a
        # hand at each tip) on a lotus throne. The bare limbs alone read as a
        # beetle / plant / rook when rendered, so the halo ring, the neck, the
        # wide shoulder bar and the throne all carry the "deity" read.
        for hx, hy in ((4, 6), (2, 12), (2, 18), (5, 24)):
            l(15, 19, hx, hy, 2)            # the left arms
            c(hx, hy, 1)                    # a hand at each tip
            l(25, 19, 40 - hx, hy, 2)       # the right arms (mirrored)
            c(40 - hx, hy, 1)
        pygame.draw.circle(art, _ICON_INK, (20, 10), 7, 2)    # halo
        c(20, 10, 4)                        # head
        r(19, 13, 3, 3)                     # neck
        r(13, 16, 14, 5)                    # broad shoulders
        p([(14, 21), (26, 21), (27, 31), (13, 31)])   # seated robed torso
        p([(9, 32), (31, 32), (27, 37), (13, 37)])    # lotus throne
    return art


def _named_condition_art(condition):
    """The cached 40x40 art icon for a named condition (None when unknown)."""
    if condition not in Condition.NAMES:
        return None
    art = _ICON_ART_CACHE.get(("cond", condition))
    if art is None:
        art = _build_named_condition_art(condition)
        _ICON_ART_CACHE[("cond", condition)] = art
    return art


def _whole_card_art(card):
    """The cached 40x40 art icon for an indivisible whole card."""
    art = _ICON_ART_CACHE.get(("card", card))
    if art is None:
        art = _build_whole_card_art(card)
        _ICON_ART_CACHE[("card", card)] = art
    return art


def _action_art(action):
    """The cached 40x40 art icon for an action (None when unknown)."""
    if action not in Action.NAMES:
        return None
    art = _ICON_ART_CACHE.get(("action", action))
    if art is None:
        art = _build_action_art(action)
        _ICON_ART_CACHE[("action", action)] = art
    return art


def _draw_action_icon(surface, action, center, size):
    """Blit an action's icon (scaled) onto ``surface``; False when unknown."""
    art = _action_art(action)
    if art is None or art.get_bounding_rect().width == 0:
        return False
    return _blit_icon_art(surface, art, center, size)


def _blit_icon_art(surface, art, center, size):
    """Blit a cached 40x40 art icon, scaled to ``size``, centered on surface."""
    if art is None:
        return False
    scaled = pygame.transform.smoothscale(art, (size, size))
    surface.blit(scaled, scaled.get_rect(center=center))
    return True


def _draw_named_condition_icon(surface, condition, center, size):
    """Blit a named condition's name-based icon (scaled) onto ``surface``."""
    return _blit_icon_art(surface, _named_condition_art(condition),
                          center, size)


def _draw_whole_card_icon(surface, card, center, size):
    """Blit an indivisible whole card's name-based icon onto ``surface``."""
    return _blit_icon_art(surface, _whole_card_art(card), center, size)


def _draw_condition_center(screen, condition, rect, glyph_size=18):
    """A condition tile's center art: a mini image of the shape/effect a
    collision condition acts on, or a name-based icon for the named ones (the
    Joker's jester hat, the Pillar condition's pillar, ...)."""
    shape = condition_shape(condition)
    effect = condition_effect(condition)
    if shape is None and effect is None:
        # A named condition carries a small icon drawn from its name; the old
        # letter glyph remains only as a fallback for an unknown condition.
        if _draw_named_condition_icon(
                screen, condition, center=rect.center,
                size=max(6, int(rect.width * 0.66))):
            return
        glyph = pygame.font.Font(None, glyph_size).render(
            condition_glyph(condition), True, BLACK)
        screen.blit(glyph, glyph.get_rect(center=rect.center))
        return
    _draw_condition_mini(screen, shape=shape, effect=effect,
                         center=rect.center, size=max(6, int(rect.width * 0.66)))


def _draw_card_icon(screen, value, rect):
    """Draw a card's center art.

    A splittable card (a condition + scorer combo) shows its CONDITION's icon:
    a mini image of the shape/effect a collision condition acts on, or the
    named condition's name-based icon (a jester hat for the Joker, ...). The
    indivisible whole cards (ERR 404 / Blueprint / Showman / Garden / Rigged
    Casino / Conquistador) each show their own name-based icon too.
    """
    pair = splittable_card_condition_scorer(value)
    if pair is not None:
        condition, _scorer = pair
        shape = condition_shape(condition)
        effect = condition_effect(condition)
        if shape is not None or effect is not None:
            _draw_condition_mini(screen, shape=shape, effect=effect,
                                 center=(rect.centerx, rect.centery + 4),
                                 size=int(GRID_SIZE * 0.62))
            return
        _draw_named_condition_icon(
            screen, condition,
            center=(rect.centerx, rect.centery + 4),
            size=int(GRID_SIZE * 0.62))
        return
    if _draw_whole_card_icon(
            screen, value,
            center=(rect.centerx, rect.centery + 4),
            size=int(GRID_SIZE * 0.62)):
        return
    glyph = pygame.font.Font(None, 22).render(
        Card.GLYPHS.get(value, "?"), True, BLACK)
    screen.blit(glyph, glyph.get_rect(center=(rect.centerx, rect.centery + 4)))


def draw_card(screen, item, rect, selected=False):
    """Draw a card as a mini playing card.

    A colored face with a thin inner border and center art (a shape/effect icon
    for shape/effect cards, or a letter glyph). A green outline marks the
    selected card.
    """
    color = Card.COLORS.get(getattr(item, "value", None), CARD_COLOR)
    pygame.draw.rect(screen, color, rect, border_radius=6)
    pygame.draw.rect(screen, WHITE, rect, 1, border_radius=6)
    pygame.draw.rect(screen, WHITE, rect, 2, border_radius=6)
    if selected:
        pygame.draw.rect(screen, GREEN, rect, 3, border_radius=6)
    _draw_card_icon(screen, getattr(item, "value", None), rect)


def draw_card_back(screen, rect):
    """Draw a plain 'card back' for an empty card slot."""
    pygame.draw.rect(screen, (70, 60, 100), rect, border_radius=6)
    pygame.draw.rect(screen, (130, 120, 170), rect, 2, border_radius=6)
    for gx in range(rect.left + 7, rect.right - 4, 8):
        for gy in range(rect.top + 7, rect.bottom - 4, 8):
            pygame.draw.circle(screen, (100, 90, 140), (gx, gy), 1)


def draw_action(screen, item, rect, selected=False):
    """Draw an action as a mini card (colored face, icon, v1/v2 tag).

    A v2 action is gold-framed and gold-tagged, because it is either one the
    player paid ACTION_UPGRADE_COST to upgrade or one of the rare ones the shop
    rolled ALREADY upgraded (see random_action_version) — a windfall worth the
    whole upgrade, and one the player has to be able to spot in a full shop. The
    frame breathes between two golds so it catches the eye and the tag is a
    solid gold plate with dark text; a v1 keeps the plain white frame and the
    small gold "v1" label it always had.

    The center shows the action's own picture (a skull for Death, a loop for
    Deja Vu, ...); the old letter glyph is only a fallback for an action with
    no art yet.
    """
    value = getattr(item, "value", None)
    color = Action.COLORS.get(value, (90, 60, 120))
    version = getattr(item, "version", 1)
    pygame.draw.rect(screen, color, rect, border_radius=6)
    if version >= 2:
        # The pulse only moves between two golds (a saturated gold and a paler
        # one), so the tile stays gold on every frame while still drawing the
        # eye to a rare already-upgraded action.
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 260.0)
        pygame.draw.rect(screen, (255, int(215 + 35 * pulse), int(140 * pulse)),
                         rect, 3, border_radius=6)
    else:
        pygame.draw.rect(screen, WHITE, rect, 1, border_radius=6)
        pygame.draw.rect(screen, WHITE, rect, 2, border_radius=6)
    if selected:
        pygame.draw.rect(screen, GREEN, rect, 3, border_radius=6)
    if not _draw_action_icon(screen, value, center=(rect.centerx, rect.centery + 2),
                             size=int(GRID_SIZE * 0.7)):
        glyph = pygame.font.Font(None, 22).render(
            Action.GLYPHS.get(value, "?"), True, WHITE)
        screen.blit(glyph, glyph.get_rect(center=(rect.centerx, rect.centery + 2)))
    _draw_version_tag(screen, rect, version)


def action_version_tag_rect(rect):
    """The corner plate a mini action card's version tag is drawn in.

    Exposed (like difficulty_button_rect) so callers and tests can ask where
    the v2 tag is without repeating the arithmetic.
    """
    return pygame.Rect(rect.right - 21, rect.top + 1, 20, 14)


def _draw_version_tag(screen, rect, version):
    """Draw the v1/v2 tag in a mini action card's top-right corner.

    v2 is a solid gold plate with dark text, so an upgraded action reads as
    upgraded at a glance wherever the card is drawn (shop, action area, info
    box); v1 stays the small gold label it always was.
    """
    if version >= 2:
        tag = action_version_tag_rect(rect)
        pygame.draw.rect(screen, (255, 215, 0), tag, border_radius=4)
        pygame.draw.rect(screen, (70, 45, 0), tag, 1, border_radius=4)
        text = pygame.font.Font(None, 16).render("v2", True, (60, 38, 0))
        screen.blit(text, text.get_rect(center=tag.center))
        return
    badge = pygame.font.Font(None, 14).render(f"v{version}", True, (255, 215, 0))
    screen.blit(badge, (rect.right - badge.get_width() - 3, rect.top + 2))


def draw_action_back(screen, rect):
    """Draw a plain 'action back' for an empty action slot."""
    pygame.draw.rect(screen, (60, 50, 80), rect, border_radius=6)
    pygame.draw.rect(screen, (110, 100, 140), rect, 2, border_radius=6)


def make_icon():
    """Build the window icon: a block with a random shape, a real effect, and
    a random scorer. A real effect keeps the icon showing an effect glyph (a
    no-effect block would render as a plain scorer-colored tile)."""
    icon = pygame.Surface([GRID_SIZE] * 2, pygame.SRCALPHA)
    draw_block(Block(0, 0,
          shape=random.choice(Shape.ORDER),
          effect=random.choice([e for e in Effect.ORDER if e != Effect.NONE]),
          scorer=random.choice(Scorer.ORDER),
          origin=(0, 0)), icon)
    return icon


class TrailParticle:
    """A small marble-colored dot that shrinks and fades where the marble passed.

    Rendered once onto an SRCALPHA surface at its starting size; each frame the
    surface is scaled down to the current (shrinking) radius and its overall
    alpha is lowered, so the trail shrinks and fades out together.
    """

    def __init__(self, x, y, radius, color, life=TRAIL_LIFE):
        self.x = float(x)
        self.y = float(y)
        self.radius = float(radius)
        self.color = color
        self.life = life
        self.age = 0.0
        size = max(2, int(radius * 2) + 2)
        self._surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(self._surf, color, (size // 2, size // 2),
                           int(max(radius, 1.0)))

    def update(self, dt):
        self.age += dt

    def dead(self):
        return self.age >= self.life

    def draw(self, screen):
        t = min(self.age / self.life, 1.0)
        radius = self.radius * (1.0 - t)
        if radius < 0.5:
            return
        size = max(2, int(radius * 2) + 2)
        surf = pygame.transform.smoothscale(self._surf, (size, size))
        surf.set_alpha(int(255 * (1.0 - t)))
        screen.blit(surf, surf.get_rect(center=(int(self.x), int(self.y))))


class ScoreParticle:
    """A floating score popup spawned when a block or card contributes score.

    The popup shows "+10" (chips, green), "x2" (add-mult, blue), or "X1.5"
    (mult-mult, red). It jumps upward out of its spawn point, drifts slightly,
    and fades out over its lifetime. The text is rendered once onto an
    antialiased SRCALPHA surface; each frame that surface's overall alpha is
    lowered so the popup gradually fades away.
    """

    def __init__(self, x, y, text, color, font, life=1.1):
        self.x = float(x)
        self.y = float(y)
        self.text = text
        self.color = color
        self.life = life
        self.age = 0.0
        self.vy = -70.0  # px/s initial upward jump
        self.vx = random.uniform(-12.0, 12.0)  # slight sideways drift
        self._surf = font.render(text, True, color)

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 55.0 * dt  # gravity eases the jump to a stop

    def dead(self):
        return self.age >= self.life

    def draw(self, screen):
        # Fade by scaling the whole SRCALPHA text surface's alpha with its
        # remaining life (0 at the end -> fully gone).
        t = min(self.age / self.life, 1.0)
        alpha = int(255 * (1.0 - t))
        self._surf.set_alpha(alpha)
        screen.blit(self._surf, self._surf.get_rect(center=(int(self.x), int(self.y))))
        self._surf.set_alpha(255)  # reset so the cached surface is reusable


class Popup:
    """A compact popup at the bottom of the screen.

    It slides up from below the screen, holds in view for a moment, then slides
    back down. When several are queued they stack upward so none covers another
    (the newest sits at the very bottom).
    """
    HEIGHT = 46
    GAP = 8
    ENTER = 0.35  # seconds to slide up into view
    HOLD = 2.6    # seconds it stays fully visible
    EXIT = 0.4    # seconds to slide back down

    def __init__(self, title, description, color):
        self.title = title
        self.description = description
        self.color = color
        self.age = 0.0

    def update(self, dt):
        self.age += dt

    def dead(self):
        return self.age >= self.ENTER + self.HOLD + self.EXIT

    def offset(self):
        """How far below its resting spot the popup sits (0 = fully in view)."""
        if self.age < self.ENTER:
            t = self.age / self.ENTER
            return (1.0 - t) * (self.HEIGHT + self.GAP)
        if self.age < self.ENTER + self.HOLD:
            return 0.0
        t = (self.age - self.ENTER - self.HOLD) / self.EXIT
        return t * (self.HEIGHT + self.GAP)


# --- Block rendering ---------------------------------------------------------

def _block_has_effect(block):
    """True when a block carries at least one real (non-NONE) effect."""
    return any(e != Effect.NONE for e in block.effects)


def _draw_checkerboard(surface, rect, square_size=8):
    """Fill a rect with alternating white and black squares.

    Used as the Finish block's face (a checkerboard goal instead of a plain
    gold square)."""
    for y in range(rect.top, rect.bottom, square_size):
        for x in range(rect.left, rect.right, square_size):
            parity = ((x - rect.left) // square_size
                      + (y - rect.top) // square_size) % 2
            color = WHITE if parity == 0 else BLACK
            pygame.draw.rect(surface, color,
                             (x, y, min(square_size, rect.right - x),
                              min(square_size, rect.bottom - y)))


def draw_block(block, screen, ghost=False):
    """Draw a block: its shape, its effect icon, and its pairing number."""
    if ghost:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        _draw_block_shape(block, overlay, outline=(255, 255, 255, 200), fill=(255, 255, 255, 36))
        _draw_block_effect_icon(block, overlay, alpha=170)
        _draw_block_pair_number(block, overlay)
        screen.blit(overlay, (0, 0))
        return
    # A block with no scoring triggers left gets a red border. When block
    # borders are turned off (BLOCK_BORDERS_ON = False), the used state is
    # shown by turning the block's interior red instead, so the player can
    # still tell which blocks have run out of triggers.
    # A block with no scoring triggers left is marked used-up: a red border
    # (borders on) or, when block borders are turned off, a red interior.
    exhausted = block.triggers_left <= 0
    has_scorer = block.scorer != Scorer.NONE
    # Outline for LINE shapes and the NONE dotted square (RED once used up).
    outline = RED if exhausted else WHITE
    # A block with a real scorer fills its shape with that scorer's color (the
    # shape advertises the reward); a block with no scorer keeps the dark
    # black shape. A used-up block keeps the red used-state indicator over the
    # scorer color.
    if exhausted and not block_borders_on():
        fill = RED
    elif has_scorer:
        fill = Scorer.color(block.scorer)
    else:
        fill = BLACK
    # Shape.NONE has no fill; its dotted square is always drawn (it IS the
    # block's face) and takes the scorer's color (gray when the block has no
    # scorer). The thin "line" shapes (Line, Flat Line, Curved Slope Line,
    # Half Pipe), the Key, and an opened Lock draw only a stroke with no fill,
    # so the stroke
    # carries the block's face color the way a filled shape's area does: the
    # scorer's color when the block has a scorer, or plain black when it is a
    # bare no-scorer wall (matching the black fill of no-scorer solid shapes).
    # A used-up block keeps the red used indicator over all of these.
    if not exhausted:
        if block.shape in (Shape.LINE, Shape.FLAT_LINE, Shape.KEY,
                           Shape.CURVED_SLOPE_LINE, Shape.HALF_PIPE):
            outline = Scorer.color(block.scorer) if has_scorer else BLACK
        elif block.shape == Shape.LOCK and not getattr(block, "locked", True):
            # An opened door has no fill either, so its frame + padlock carry
            # the face colour like a line shape's stroke does.
            outline = Scorer.color(block.scorer) if has_scorer else BLACK
        elif block.shape == Shape.NONE:
            outline = Scorer.color(block.scorer)
    # The run-role blocks get their own faces instead of a scorer-colored
    # shape: a Start block is an empty unit with a marble in its center, and a
    # Finish block is a white-and-black checkerboard (a goal flag).
    if block.scorer == Scorer.START:
        _draw_marble_icon(screen, block.rect.center, MARBLE_RADIUS)
        return
    if block.scorer == Scorer.FINISH:
        _draw_checkerboard(screen, block.rect)
        if block_borders_on():
            pygame.draw.rect(screen, RED if exhausted else WHITE, block.rect, 3)
        _draw_block_pair_number(block, screen)
        return
    _draw_block_shape(block, screen, outline=outline, fill=fill)
    _draw_block_effect_icon(block, screen)
    _draw_block_pair_number(block, screen)


def _draw_block_pair_number(block, surface):
    """Draw a pairing number on a paired block so its partner is identifiable.

    Portals and Key/Lock blocks come in numbered pairs (two blocks sharing a
    number); the number sits just below the center so the matching half can be
    found at a glance.
    """
    if block.has_effect(Effect.PORTAL):
        number = getattr(block, "portal_number", 0)
    elif block.shape in (Shape.KEY, Shape.LOCK):
        number = getattr(block, "key_number", 0)
    else:
        return
    if not number:
        return
    num = pygame.font.Font(None, 16).render(str(number), True, WHITE)
    # The number sits below the shape's art (the effect icon is at the center).
    surface.blit(num, num.get_rect(center=(block.rect.centerx, block.rect.centery + 16)))


def _draw_key_glyph(block, surface, color):
    """Draw the Key shape's figure: a bow (ring), a shaft, and two teeth.

    The key has no hitbox (it is a pass-through pickup), so it is drawn as a
    bare stroke in the given color — the way the thin line shapes carry their
    face in their stroke instead of a fill.
    """
    bow = _icon_point(block, -11, 0)
    pygame.draw.circle(surface, color, (int(bow[0]), int(bow[1])), 5, 4)
    pygame.draw.line(surface, color, _icon_point(block, -7, 0),
                     _icon_point(block, 12, 0), 4)
    # The bit: two teeth hanging off the shaft's far end.
    pygame.draw.line(surface, color, _icon_point(block, 5, 0),
                     _icon_point(block, 5, 8), 4)
    pygame.draw.line(surface, color, _icon_point(block, 12, 0),
                     _icon_point(block, 12, 8), 4)


def _draw_padlock_glyph(block, surface, color, cut=False):
    """Draw the Lock shape's padlock: a body with a shackle above it.

    With ``cut`` the padlock is ERASED out of the (already filled) door instead
    of stroked, so a locked door reads as a solid slab with a keyhole — the
    trick works on any fill color, including the flat black the condition and
    card tiles use. Otherwise the padlock is stroked in ``color`` (an opened
    lock keeps its padlock, drawn hollow, inside the empty doorway).
    """
    cx, cy = block.rect.center
    ring = (int(cx), int(cy) - 8)
    body = pygame.Rect(block.rect.left + 9, block.rect.top + 18,
                       block.rect.width - 18, 13)
    if cut:
        # Erase the shackle band and the body: their union is the padlock.
        pygame.draw.circle(surface, (0, 0, 0, 0), ring, 7, 4)
        pygame.draw.rect(surface, (0, 0, 0, 0), body)
        return
    pygame.draw.circle(surface, color, ring, 7, 4)
    pygame.draw.rect(surface, color, body, 3)


def _draw_block_shape(block, surface, outline, fill):
    """Draw a block's shape fill and (optionally) its outline border."""
    if block.shape == Shape.RECT:
        if block.has_effect(Effect.ROTATE):
            # A rotating rectangle is drawn as its rotated corners so the
            # spin is visible (collision uses the oriented rect too).
            pts = [block._rotate_point(p, block.angle) for p in [
                (block.rect.left, block.rect.top),
                (block.rect.right, block.rect.top),
                (block.rect.right, block.rect.bottom),
                (block.rect.left, block.rect.bottom),
            ]]
            pygame.draw.polygon(surface, fill, pts)
            if block_borders_on():
                pygame.draw.polygon(surface, outline, pts, 3)
        else:
            pygame.draw.rect(surface, fill, block.rect)
            if block_borders_on():
                pygame.draw.rect(surface, outline, block.rect, 3)
    elif block.shape == Shape.SLOPE:
        if block_borders_on():
            pygame.draw.polygon(surface, outline, block.get_slope_points)
            pygame.draw.polygon(surface, fill, block.get_slope_border_points)
        else:
            pygame.draw.polygon(surface, fill, block.get_slope_points)
    elif block.shape == Shape.LINE:
        start, end = block.get_slope_line_points
        pygame.draw.line(surface, outline, start, end, 5)
    elif block.shape == Shape.FLAT_LINE:
        start, end = block.get_flat_line_points
        pygame.draw.line(surface, outline, start, end, 5)
    elif block.shape == Shape.CURVED_SLOPE_LINE:
        pygame.draw.lines(surface, outline, False, block.get_curved_arc, 5)
    elif block.shape == Shape.HALF_PIPE:
        pygame.draw.lines(surface, outline, False, block.get_half_pipe_points, 5)
    elif block.shape == Shape.CIRCLE:
        pygame.draw.circle(surface, fill, block.rect.center, GRID_SIZE // 2)
        if block_borders_on():
            pygame.draw.circle(surface, outline, block.rect.center, GRID_SIZE // 2, 3)
    elif block.shape == Shape.CURVED_SLOPE:
        # Inward-curving quarter-circle surface (rotated by the angle) plus
        # the right and bottom legs, like the slope triangle.
        pygame.draw.polygon(surface, fill, block.get_curved_fill)
        if block_borders_on():
            pygame.draw.lines(surface, outline, False, block.get_curved_arc, 3)
    elif block.shape == Shape.CONVEX_SLOPE:
        # Outward-curving quarter circle: a solid quarter disk at the cell's
        # top-left corner (rotated by the angle).
        pygame.draw.polygon(surface, fill, block.get_convex_fill)
        if block_borders_on():
            pygame.draw.lines(surface, outline, False, block.get_convex_arc, 3)
    elif block.shape == Shape.PIPE:
        # Two vertical pillars with a marble-diameter gap down the middle.
        for pts in block._get_pipe_pillar_points():
            pygame.draw.polygon(surface, fill, pts)
            if block_borders_on():
                pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.DRAIN:
        # A square exterior with a funnel cavity: two curved walls framing
        # a marble-width drain at the bottom.
        for pts in block.get_drain_walls:
            pygame.draw.polygon(surface, fill, pts)
            if block_borders_on():
                pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.PIPE_BEND:
        # A marble-wide channel enters the top edge and exits the right
        # edge (adjacent sides), curving 90 degrees around the corner core.
        # The solid is drawn with exact circles: the cell is filled, the
        # outer quarter-disk at the corner is cut out (the channel's outer
        # side), then the corner core inside the inner radius is re-filled.
        # Drawing the cutout circles at the rotated corner keeps the drawn
        # channel aligned with the (rotated) hitbox.
        bend_fill = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
        bend_fill.fill(fill)
        corner = block._rotate_point((block.rect.right, block.rect.top), block.angle)
        local_corner = (corner[0] - block.rect.left, corner[1] - block.rect.top)
        pygame.draw.circle(bend_fill, (0, 0, 0, 0), local_corner,
                           GRID_SIZE // 2 + MARBLE_RADIUS)
        pygame.draw.circle(bend_fill, fill, local_corner,
                           GRID_SIZE // 2 - MARBLE_RADIUS)
        surface.blit(bend_fill, block.rect.topleft)
        if block_borders_on():
            for pts in (block.get_pipe_bend_inner_arc, block.get_pipe_bend_outer_arc):
                pygame.draw.lines(surface, outline, False, pts, 3)
            for p1, p2, _ in block.get_pipe_bend_legs:
                pygame.draw.line(surface, outline, p1, p2, 3)
    elif block.shape == Shape.NONE:
        # No hitbox: draw the cell as a square of dotted lines. The dotted
        # outline always shows (it is the NONE block's face) even when block
        # borders are turned off.
        _draw_block_dotted_square(block, surface, outline)
    elif block.shape == Shape.SPIKE:
        # An upward triangle: base on the bottom edge, apex top-center.
        pts = block.get_spike_points
        pygame.draw.polygon(surface, fill, pts)
        if block_borders_on():
            pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.PLATFORM:
        # A thick shelf filling the bottom half of the unit.
        pts = block.get_platform_points
        pygame.draw.polygon(surface, fill, pts)
        if block_borders_on():
            pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.CORNER:
        # An L bracket: a left column plus a bottom row.
        for pts in block.get_corner_points:
            pygame.draw.polygon(surface, fill, pts)
            if block_borders_on():
                pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.PEG:
        # A small solid circle (PEG_RADIUS) at the cell's center.
        pygame.draw.circle(surface, fill, block.rect.center, PEG_RADIUS)
        if block_borders_on():
            pygame.draw.circle(surface, outline, block.rect.center, PEG_RADIUS, 3)
    elif block.shape == Shape.SAWTOOTH:
        # A row of small upward teeth along the bottom edge.
        for pts in block.get_sawtooth_teeth:
            pygame.draw.polygon(surface, fill, pts)
            if block_borders_on():
                pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.CRADLE:
        # Two side wedges framing a downward V valley, backed by a floor slab.
        for pts in block.get_cradle_pieces:
            pygame.draw.polygon(surface, fill, pts)
            if block_borders_on():
                pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.BUMP:
        # A solid dome (half-disc) sitting on the cell's bottom edge.
        pts = block.get_bump_points
        pygame.draw.polygon(surface, fill, pts)
        if block_borders_on():
            pygame.draw.polygon(surface, outline, pts, 3)
    elif block.shape == Shape.KEY:
        # A pass-through key pickup: a key figure, with no fill behind it.
        _draw_key_glyph(block, surface, outline)
    elif block.shape == Shape.LOCK:
        # A locked door is the whole unit filled solid with a padlock cut out
        # of it (a keyhole — cutting works on any fill colour, including the
        # flat black a condition/card tile draws) and the padlock stroked over
        # the cut so it reads against the board too. Once its key has been
        # touched this run the door opens: only the doorway's frame and the
        # hollow padlock remain.
        if getattr(block, "locked", True):
            door = pygame.Surface((block.rect.width, block.rect.height),
                                  pygame.SRCALPHA)
            door.fill(fill)
            _draw_padlock_glyph(block, door, fill, cut=True)
            surface.blit(door, block.rect.topleft)
            _draw_padlock_glyph(block, surface, outline)
            if block_borders_on():
                pygame.draw.rect(surface, outline, block.rect, 3)
        else:
            pygame.draw.rect(surface, outline, block.rect, 3)
            _draw_padlock_glyph(block, surface, outline)


def _draw_block_dotted_square(block, surface, color, dot_length=4, gap_length=4,
                              inset=3):
    """Draw the block's cell as a square of evenly spaced dots.

    The square is inset a few pixels from the cell edges so the thick dashes
    sit inside the unit instead of sticking out past its area.
    """
    x, y = block.rect.left + inset, block.rect.top + inset
    w = block.rect.width - 2 * inset
    h = block.rect.height - 2 * inset
    step = dot_length + gap_length
    # Top and bottom edges.
    for start_x in range(x, x + w, step):
        end_x = min(start_x + dot_length, x + w)
        pygame.draw.line(surface, color, (start_x, y), (end_x, y), 3)
        pygame.draw.line(surface, color, (start_x, y + h), (end_x, y + h), 3)
    # Left and right edges.
    for start_y in range(y, y + h, step):
        end_y = min(start_y + dot_length, y + h)
        pygame.draw.line(surface, color, (x, start_y), (x, end_y), 3)
        pygame.draw.line(surface, color, (x + w, start_y), (x + w, end_y), 3)


def _icon_point(block, dx, dy):
    """An effect-icon point (offset from the cell center), rotated by the block's angle.

    Rotating with the block (and any ROTATE spin) keeps the icon aligned
    with the drawn shape when the A key turns the block.
    """
    cx, cy = block.rect.center
    return block._rotate_point((cx + dx, cy + dy), block.angle)


def _draw_block_effect_icon(block, surface, alpha=255, color=None):
    """Draw a block's effect icon (rotated with the block's angle).

    Blocks with no real effect draw nothing here — their shape is colored by
    the scorer instead (see draw_block).
    """
    if not _block_has_effect(block):
        return
    if color is None:
        # The shape is filled with the scorer's color, so a black glyph reads
        # clearly; a block with no scorer keeps the original gray icon on its
        # black shape.
        color = BLACK if block.scorer != Scorer.NONE else Scorer.color(block.scorer)
    if alpha < 255:
        color = (color[0], color[1], color[2], alpha)
    cx, cy = block.rect.center
    if block.effect == Effect.BOUNCY:
        pygame.draw.line(surface, color, _icon_point(block, -4, 0), _icon_point(block, 4, 0), 2)
        pygame.draw.line(surface, color, _icon_point(block, 0, -6), _icon_point(block, 0, 6), 2)
        pygame.draw.polygon(surface, color, [_icon_point(block, 0, -9), _icon_point(block, -3, -5), _icon_point(block, 3, -5)])
        pygame.draw.polygon(surface, color, [_icon_point(block, 0, 9), _icon_point(block, -3, 5), _icon_point(block, 3, 5)])
    elif block.effect == Effect.ACCELERATOR:
        direction = block._get_angle_vector()
        direction = direction / np.linalg.norm(direction)
        tip = (cx + direction[0] * 8, cy + direction[1] * 8)
        pygame.draw.line(surface, color, (cx, cy), tip)
        perp = np.array([-direction[1], direction[0]])
        p1 = (tip[0] - direction[0] * 4 + perp[0] * 4, tip[1] - direction[1] * 4 + perp[1] * 4)
        p2 = (tip[0] - direction[0] * 4 - perp[0] * 4, tip[1] - direction[1] * 4 - perp[1] * 4)
        pygame.draw.polygon(surface, color, [tip, p1, p2])
    elif block.effect == Effect.PISTON:
        # A spring (zigzag) with an upward arrowhead.
        pts = [_icon_point(block, 0, 6), _icon_point(block, 5, 3), _icon_point(block, -5, 0),
               _icon_point(block, 5, -3), _icon_point(block, 0, -6)]
        pygame.draw.lines(surface, color, False, pts, 2)
        pygame.draw.line(surface, color, _icon_point(block, 0, -8), _icon_point(block, 0, -10), 2)
        pygame.draw.polygon(surface, color, [_icon_point(block, 0, -13), _icon_point(block, -4, -8), _icon_point(block, 4, -8)])
    elif block.effect == Effect.GRAVITY:
        # A planet dot with an arrow showing the direction gravity pulls.
        direction = block._get_angle_vector()
        direction = direction / np.linalg.norm(direction)
        pygame.draw.circle(surface, color, (cx, cy), 4)
        tip = (cx + direction[0] * 15, cy + direction[1] * 15)
        pygame.draw.line(surface, color, (cx + direction[0] * 4.5, cy + direction[1] * 4.5), tip)
        perp = np.array([-direction[1], direction[0]])
        p1 = (tip[0] - direction[0] * 4 + perp[0] * 4, tip[1] - direction[1] * 4 + perp[1] * 4)
        p2 = (tip[0] - direction[0] * 4 - perp[0] * 4, tip[1] - direction[1] * 4 - perp[1] * 4)
        pygame.draw.polygon(surface, color, [tip, p1, p2])
    elif block.effect == Effect.BLACK_HOLE:
        # Saturn: a filled planet with a ring that rotates with the block.
        pygame.draw.circle(surface, color, (cx, cy), 6)
        ring = [_icon_point(block, 10 * math.cos(math.radians(a)),
                            4 * math.sin(math.radians(a)))
                for a in range(0, 360, 15)]
        pygame.draw.polygon(surface, color, ring, 2)
    elif block.effect == Effect.PORTAL:
        # A portal mouth: two concentric rings around the center (rotating
        # a circle is a no-op, so no rotation is needed here).
        pygame.draw.circle(surface, color, (cx, cy), 9, 2)
        pygame.draw.circle(surface, color, (cx, cy), 5, 2)
    elif block.effect == Effect.ROTATE:
        # A circular arrow: two arcs with arrowheads that rotate with the block.
        ring = (cx - 8, cy - 8, 16, 16)
        pygame.draw.arc(surface, color, ring, math.radians(20), math.radians(160), 2)
        pygame.draw.arc(surface, color, ring, math.radians(200), math.radians(340), 2)
        pygame.draw.polygon(surface, color, [_icon_point(block, 8, -1), _icon_point(block, 4, -5), _icon_point(block, 4, 3)])
        pygame.draw.polygon(surface, color, [_icon_point(block, -8, 1), _icon_point(block, -4, -3), _icon_point(block, -4, 5)])
    elif block.effect == Effect.SLIPPERY:
        # Three speed lines that rotate with the block's angle.
        pygame.draw.line(surface, color, _icon_point(block, -8, -5), _icon_point(block, 8, -5), 2)
        pygame.draw.line(surface, color, _icon_point(block, -8, 0), _icon_point(block, 8, 0), 2)
        pygame.draw.line(surface, color, _icon_point(block, -8, 5), _icon_point(block, 8, 5), 2)
    elif block.effect == Effect.FRAGILE:
        # A jagged crack that rotates with the block's angle.
        pygame.draw.lines(surface, color, False, [
            _icon_point(block, -6, -8), _icon_point(block, -2, -3), _icon_point(block, 3, -6),
            _icon_point(block, 0, 0), _icon_point(block, 5, 2), _icon_point(block, 2, 6),
            _icon_point(block, 6, 8)], 2)
    elif block.effect == Effect.GROWING:
        # Four outward-pointing arrows: the marble expands.
        for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tip = _icon_point(block, ax * 8, ay * 8)
            base = _icon_point(block, ax * 3, ay * 3)
            pygame.draw.line(surface, color, base, tip, 2)
            d = (ax, ay)
            perp = (-ay, ax)
            p1 = (tip[0] - d[0] * 3 + perp[0] * 2.5, tip[1] - d[1] * 3 + perp[1] * 2.5)
            p2 = (tip[0] - d[0] * 3 - perp[0] * 2.5, tip[1] - d[1] * 3 - perp[1] * 2.5)
            pygame.draw.polygon(surface, color, [tip, p1, p2])
    elif block.effect == Effect.SHRINKING:
        # Four inward-pointing arrows: the marble contracts.
        for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tip = _icon_point(block, ax * 3, ay * 3)
            base = _icon_point(block, ax * 8, ay * 8)
            pygame.draw.line(surface, color, base, tip, 2)
            d = (-ax, -ay)  # arrowhead points back toward the center
            perp = (-d[1], d[0])
            p1 = (tip[0] - d[0] * 3 + perp[0] * 2.5, tip[1] - d[1] * 3 + perp[1] * 2.5)
            p2 = (tip[0] - d[0] * 3 - perp[0] * 2.5, tip[1] - d[1] * 3 - perp[1] * 2.5)
            pygame.draw.polygon(surface, color, [tip, p1, p2])
    elif block.effect == Effect.STICKY:
        # A glue drop: a teardrop with two small stuck-on dots around it.
        pygame.draw.circle(surface, color, _icon_point(block, 0, 2), 5)
        pygame.draw.polygon(surface, color,
                            [_icon_point(block, 0, -9), _icon_point(block, -4, 1),
                             _icon_point(block, 4, 1)])
        pygame.draw.circle(surface, color, _icon_point(block, 9, -6), 2)
        pygame.draw.circle(surface, color, _icon_point(block, -9, -4), 2)
    elif block.effect == Effect.REPULSOR:
        # Radiating waves: a solid core with two arcs bowing away from it.
        pygame.draw.circle(surface, color, _icon_point(block, 0, 3), 4)
        for radius in (8, 13):
            arc = [_icon_point(block, radius * math.sin(math.radians(a)),
                               3 - radius * math.cos(math.radians(a)))
                   for a in range(-55, 56, 5)]
            pygame.draw.lines(surface, color, False, arc, 2)
    elif block.effect == Effect.CONVEYOR:
        # A belt: two rails with chevrons showing which way it carries marbles.
        pygame.draw.line(surface, color, _icon_point(block, -9, -7),
                         _icon_point(block, 9, -7), 2)
        pygame.draw.line(surface, color, _icon_point(block, -9, 7),
                         _icon_point(block, 9, 7), 2)
        for dx in (-5, 2):
            pygame.draw.lines(surface, color, False, [
                _icon_point(block, dx - 3, -4), _icon_point(block, dx + 2, 0),
                _icon_point(block, dx - 3, 4)], 2)
    elif block.effect == Effect.ZIPPER:
        # A one-way gate: an arrow through a barrier with a gap in it, drawn
        # along the block's arrow (the direction marbles may pass).
        for x0, x1 in ((-11, -4), (4, 11)):
            pygame.draw.line(surface, color, _icon_point(block, x0, 4),
                             _icon_point(block, x1, 4), 3)
        pygame.draw.line(surface, color, _icon_point(block, 0, 9),
                         _icon_point(block, 0, -5), 2)
        pygame.draw.polygon(surface, color, [_icon_point(block, 0, -10),
                                             _icon_point(block, -4, -4),
                                             _icon_point(block, 4, -4)])
    elif block.effect == Effect.PHASE:
        # A ghost marble: a dashed ring with a dashed path running through it.
        for a in range(0, 360, 30):
            pygame.draw.line(surface, color,
                             _icon_point(block, 10 * math.cos(math.radians(a)),
                                         10 * math.sin(math.radians(a))),
                             _icon_point(block, 10 * math.cos(math.radians(a + 18)),
                                         10 * math.sin(math.radians(a + 18))), 2)
        for x in (-13, -6, 1, 8):
            pygame.draw.line(surface, color, _icon_point(block, x, 0),
                             _icon_point(block, x + 4, 0), 2)
    elif block.effect == Effect.SPLITTER:
        # One marble becoming two: a core with arrows leaving opposite ways.
        pygame.draw.circle(surface, color, (cx, cy), 3)
        for sign in (1, -1):
            pygame.draw.line(surface, color, _icon_point(block, sign * 5, 0),
                             _icon_point(block, sign * 12, 0), 2)
            pygame.draw.polygon(surface, color, [
                _icon_point(block, sign * 13, 0), _icon_point(block, sign * 7, -4),
                _icon_point(block, sign * 7, 4)])
    else:
        pygame.draw.circle(surface, color, (cx, cy), 7.5, 3)

    # A "+" marks a block with more than one effect (bottom-right of the icon).
    if len(block.effects) > 1:
        plus = pygame.font.Font(None, 16).render("+", True, WHITE)
        surface.blit(plus, plus.get_rect(center=(cx + 10, cy + 10)))


def draw_block_shape_only(block, surface):
    """Draw just the shape outline (no center icon or color)."""
    if block.shape == Shape.RECT:
        pygame.draw.rect(surface, WHITE, block.rect, 3)
    elif block.shape == Shape.SLOPE:
        pygame.draw.polygon(surface, WHITE, block.get_slope_points, 3)
    elif block.shape == Shape.LINE:
        start, end = block.get_slope_line_points
        pygame.draw.line(surface, WHITE, start, end, 5)
    elif block.shape == Shape.FLAT_LINE:
        start, end = block.get_flat_line_points
        pygame.draw.line(surface, WHITE, start, end, 5)
    elif block.shape == Shape.CURVED_SLOPE_LINE:
        pygame.draw.lines(surface, WHITE, False, block.get_curved_arc, 5)
    elif block.shape == Shape.HALF_PIPE:
        pygame.draw.lines(surface, WHITE, False, block.get_half_pipe_points, 5)
    elif block.shape == Shape.CIRCLE:
        pygame.draw.circle(surface, WHITE, block.rect.center, GRID_SIZE // 2, 3)
    elif block.shape == Shape.CURVED_SLOPE:
        pygame.draw.lines(surface, WHITE, False, block.get_curved_arc, 3)
        for p1, p2, _ in block.get_curved_legs:
            pygame.draw.line(surface, WHITE, p1, p2, 3)
    elif block.shape == Shape.CONVEX_SLOPE:
        pygame.draw.lines(surface, WHITE, False, block.get_convex_arc, 3)
        for p1, p2, _ in block.get_convex_legs:
            pygame.draw.line(surface, WHITE, p1, p2, 3)
    elif block.shape == Shape.PIPE:
        for pts in block._get_pipe_pillar_points():
            pygame.draw.polygon(surface, WHITE, pts, 3)
    elif block.shape == Shape.DRAIN:
        for pts in block.get_drain_walls:
            pygame.draw.polygon(surface, WHITE, pts, 3)
    elif block.shape == Shape.PIPE_BEND:
        for pts in (block.get_pipe_bend_inner_arc, block.get_pipe_bend_outer_arc):
            pygame.draw.lines(surface, WHITE, False, pts, 3)
        for p1, p2, _ in block.get_pipe_bend_legs:
            pygame.draw.line(surface, WHITE, p1, p2, 3)
    elif block.shape == Shape.NONE:
        _draw_block_dotted_square(block, surface, WHITE)
    elif block.shape == Shape.SPIKE:
        pygame.draw.polygon(surface, WHITE, block.get_spike_points, 3)
    elif block.shape == Shape.PLATFORM:
        pygame.draw.polygon(surface, WHITE, block.get_platform_points, 3)
    elif block.shape == Shape.CORNER:
        # ONE L-shaped outline: a component/ghost image shows the shape alone,
        # with no line drawn where the two overlapping legs meet.
        pygame.draw.polygon(surface, WHITE, block.get_corner_silhouette, 3)
    elif block.shape == Shape.PEG:
        pygame.draw.circle(surface, WHITE, block.rect.center, PEG_RADIUS, 3)
    elif block.shape == Shape.SAWTOOTH:
        for pts in block.get_sawtooth_teeth:
            pygame.draw.polygon(surface, WHITE, pts, 3)
    elif block.shape == Shape.CRADLE:
        # ONE silhouette: a component/ghost image shows the shape alone, with no
        # line drawn where either wedge meets the floor slab.
        pygame.draw.polygon(surface, WHITE, block.get_cradle_silhouette, 3)
    elif block.shape == Shape.BUMP:
        pygame.draw.polygon(surface, WHITE, block.get_bump_points, 3)
    elif block.shape == Shape.KEY:
        _draw_key_glyph(block, surface, WHITE)
    elif block.shape == Shape.LOCK:
        # The lock as a shape: its doorway frame with the padlock inside.
        pygame.draw.rect(surface, WHITE, block.rect, 3)
        _draw_padlock_glyph(block, surface, WHITE)


# --- Marble rendering --------------------------------------------------------

def draw_marble(marble, screen):
    """Draw a marble with its 3D rolling surface (type-specific look)."""
    pos = (int(marble.position[0]), int(marble.position[1]))
    r = int(marble.radius)
    md, sin_a, cos_a = _marble_roll(marble)
    if marble.marble_type == MarbleType.EIGHT_BALL:
        # A black sphere with a white circle + "8" painted on its face.
        _draw_marble_shaded_sphere(marble, screen, pos, r, (12, 12, 16))
        _blit_marble_rolling_feature(marble, screen, pos, r, md, sin_a, cos_a,
                                     _draw_marble_eight_feature)
    elif marble.marble_type == MarbleType.RUBBER_BALL:
        _draw_marble_rubber_ball(marble, screen, pos, r, md, sin_a, cos_a)
    elif marble.marble_type == MarbleType.PING_PONG:
        # A ping-pong ball wears two half-colors (white + orange) whose
        # boundary sweeps with the roll — the same rolling look as the
        # two-tone rubber ball.
        _draw_marble_rubber_ball(marble, screen, pos, r, md, sin_a, cos_a)
    else:
        _draw_marble_shaded_sphere(marble, screen, pos, r, marble.color)
        # A small contrasting speck rolls across a vanilla marble so its
        # spin stays visible (it has no painted pattern).
        _blit_marble_rolling_feature(marble, screen, pos, r, md, sin_a, cos_a,
                                     _draw_marble_speck_feature)
    _draw_marble_gloss(marble, screen, pos, r)
    if getattr(marble, "phase_timer", 0.0) > 0:
        # A phasing marble wears a dashed halo so the player can see that it is
        # currently passing through every block.
        _draw_marble_phase_ring(screen, pos, r)


def _draw_marble_phase_ring(screen, pos, r):
    """A dashed halo marking a marble that is phasing (no block collisions)."""
    if r < 2:
        return
    radius = r + 3
    box = (pos[0] - radius, pos[1] - radius, radius * 2, radius * 2)
    for a in range(0, 360, 30):
        pygame.draw.arc(screen, (200, 230, 255), box,
                        math.radians(a), math.radians(a + 16), 2)


def _marble_roll(marble):
    """(move_dir, sin_a, cos_a): the marble's current 3D roll.

    A ball rolls around an axis perpendicular to its motion, so the painted
    feature slides along the direction of travel, foreshortens, then hides as
    it turns around the side of the ball — a tilted 3D axis rather than a flat
    spin around the circle's center. ``sin_a`` drives the feature's sweep along
    the motion axis; ``cos_a`` drives its visibility and foreshortening (front
    when positive).
    """
    speed = np.linalg.norm(marble.velocity)
    if speed > 1e-6:
        marble._move_dir = marble.velocity / speed
    move_dir = marble._move_dir
    a = getattr(marble, "spin_angle", 0.0)
    return move_dir, math.sin(a), math.cos(a)


def _shade(color, factor):
    """Brighten (factor > 1) or darken (factor < 1) an RGB color."""
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _draw_marble_shaded_sphere(marble, screen, pos, r, color):
    """Draw a flat-shaded sphere base (darker rim + fill)."""
    pygame.draw.circle(screen, _shade(color, 0.55), pos, r)
    pygame.draw.circle(screen, color, pos, max(1, r - 1))


def _draw_marble_gloss(marble, screen, pos, r):
    """A glossy highlight near the top-left for a 3D sphere look.

    The highlight is a light reflection, so it stays put as the ball rolls
    (it does not ride the painted pattern).
    """
    if r < 2:
        return
    hr = max(2, int(r * 0.3))
    hx = pos[0] - int(r * 0.35)
    hy = pos[1] - int(r * 0.4)
    surf = pygame.Surface((hr * 2, hr * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, 120), (hr, hr), hr)
    pygame.draw.circle(surf, (255, 255, 255, 70), (hr, hr), max(1, hr - 1))
    screen.blit(surf, surf.get_rect(center=(hx, hy)))


def _draw_marble_icon(surface, center, radius):
    """A small shaded vanilla marble, drawn in a Start block's empty cell."""
    _draw_marble_shaded_sphere(None, surface, center, radius, (232, 232, 238))
    _draw_marble_gloss(None, surface, center, radius)


def _blit_marble_rolling_feature(marble, screen, pos, r, md, sin_a, cos_a, pattern_fn):
    """Blit a painted feature onto the sphere with 3D roll foreshortening.

    The feature is drawn on a small transparent surface, squished along the
    motion axis by ``cos_a`` (it thins as it turns toward the ball's side),
    rotated to align with the motion direction, and slid along the motion axis
    by the roll angle (``sin_a``). It is hidden once it rolls around to the
    back of the ball (``cos_a <= 0``).
    """
    if cos_a <= 0.0:
        return
    size = max(6, int(r * 2))
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pattern_fn(marble, surf, size // 2, size // 2, size)
    w = max(2, int(size * abs(cos_a)))
    surf = pygame.transform.smoothscale(surf, (w, size))
    ang = math.degrees(math.atan2(md[1], md[0]))
    surf = pygame.transform.rotate(surf, -ang)
    off = r * sin_a
    px = int(marble.position[0] + off * md[0])
    py = int(marble.position[1] + off * md[1])
    screen.blit(surf, surf.get_rect(center=(px, py)))


def _draw_marble_eight_feature(marble, surf, cx, cy, size):
    """Paint the 8 ball's white circle with a black 8 (centered at cx, cy)."""
    wr = max(2, int(size * 0.28))
    pygame.draw.circle(surf, WHITE, (cx, cy), wr)
    digit = pygame.font.Font(None, max(8, int(size * 0.4))).render("8", True, BLACK)
    surf.blit(digit, digit.get_rect(center=(cx, cy)))


def _draw_marble_speck_feature(marble, surf, cx, cy, size):
    """Paint a small contrasting dot so a vanilla marble's roll is visible."""
    pygame.draw.circle(surf, _shade(marble.color, 0.55), (cx, cy),
                       max(2, int(size * 0.13)))


def _draw_marble_rubber_ball(marble, screen, pos, r, md, sin_a, cos_a):
    """Draw a two-tone rubber ball whose color boundary sweeps with the roll.

    One half is ``marble.color``, the other ``marble.color2``. The boundary
    between them sits at ``sin_a * R`` along the motion axis (through the
    center at rest) and runs perpendicular to it, so as the ball rolls one
    half is revealed from the side — a 3D roll rather than a flat spin around
    the circle's center.
    """
    c1 = marble.color
    c2 = marble.color2
    _draw_marble_shaded_sphere(marble, screen, pos, r, c1)
    d = r * sin_a  # signed distance from the center to the boundary line
    if d >= r:
        pygame.draw.circle(screen, _shade(c2, 0.92), pos, r)
        return
    if d <= -r:
        return  # color1 fills the whole face
    ang_md = math.atan2(md[1], md[0])
    alpha = math.acos(max(-1.0, min(1.0, d / r)))
    a0 = ang_md + alpha
    a1 = ang_md - alpha + 2 * math.pi
    pts = []
    steps = 20
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((int(marble.position[0] + r * math.cos(a)),
                    int(marble.position[1] + r * math.sin(a))))
    pygame.draw.polygon(screen, _shade(c2, 0.92), pts)
    pygame.draw.circle(screen, _shade(c1, 0.7), pos, r, 1)


# --- Game screens -------------------------------------------------------------

def draw(game):
    """Draw the current screen: a title/menu tab, or the full game frame."""
    if game.title_screen:
        draw_title_screen(game)
        return
    if game.achievements_open:
        draw_achievements(game)
        return
    if game.marble_selecting:
        draw_marble_select(game)
        return
    if game.upgrades_open:
        draw_upgrades(game)
        return
    if game.collection_open:
        draw_collection(game)
        return
    game.screen.fill(RED)
    # The all-finishes trial paints the marble-box border in the finish
    # scorer color so its edges read as a finish.
    box_border = (Scorer.color(Scorer.FINISH)
                  if game.current_trial == Trial.ALL_FINISHES else (30, 30, 30))
    draw_board(game, box_border)
    draw_run_dots(game)

    for block in game.grid.values():
        draw_block(block, game.screen)

    # The subject of an active action (a placed grid block) is gold-outlined.
    subject = game.selected_action_subject
    if (game.selected_action is not None and isinstance(subject, Block)
            and (subject.x, subject.y) in game.grid):
        pygame.draw.rect(game.screen, (255, 215, 0), subject.rect, 3)

    # The board title sits at the bottom-left of the panel. It hides while
    # the mouse is over the board so it never sits under the cursor.
    if game._show_marble_box_title():
        title = game.font.render("BOARD", True, WHITE)
        game.screen.blit(title, (MARBLE_BOX_COORDS[0] + 8,
                                 MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3] - 26))

    # Fire along the top edge of the box while the score passes the run.
    draw_fire(game)

    mouse_pos = pygame.mouse.get_pos()
    grid_x = (mouse_pos[0] - MARBLE_BOX_COORDS[0]) // GRID_SIZE
    grid_y = (mouse_pos[1] - MARBLE_BOX_COORDS[1]) // GRID_SIZE
    inside_grid = (
        MARBLE_BOX_COORDS[0] <= mouse_pos[0] < MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2]
        and MARBLE_BOX_COORDS[1] <= mouse_pos[1] < MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3]
    )
    if (inside_grid and 0 <= grid_x < GRID_WIDTH and 0 <= grid_y < GRID_HEIGHT
            and game.has_selected and not game.is_cell_locked(grid_x, grid_y)):
        ghost = Block(
            grid_x,
            grid_y,
            shape=game.selected_shape,
            effect=game.selected_effect,
            scorer=game.selected_scorer,
            scorer_amount=game.selected_scorer_amount,
            angle=game.current_block_angle,
            portal_number=getattr(game.selected_toolbox_item, "portal_number", 0),
            key_number=getattr(game.selected_toolbox_item, "key_number", 0),
        )
        draw_block(ghost, game.screen, ghost=True)

    for particle in game.trail_particles:
        particle.draw(game.screen)
    for marble in game.marbles:
        draw_marble(marble, game.screen)
    for particle in game.score_particles:
        particle.draw(game.screen)
    draw_score_display(game)
    draw_trial_box(game)
    draw_toolbox(game)
    draw_cards(game)
    draw_action_area(game)
    draw_tokens(game)
    draw_sell_overlay(game)
    draw_upgrade_overlay(game)
    draw_shop(game)
    draw_sidebar(game)
    # The bottom-left MAIN MENU button: clicking it returns to the title screen.
    btn = RETURN_TO_MENU_BUTTON_RECT
    pygame.draw.rect(game.screen, (60, 60, 80), btn, border_radius=8)
    pygame.draw.rect(game.screen, WHITE, btn, 2, border_radius=8)
    label = game.small_font.render("MAIN MENU", True, WHITE)
    game.screen.blit(label, label.get_rect(center=btn.center))
    draw_game_over(game)
    # The bottom popups (achievement unlocks, collection discoveries) draw
    # last so they sit on top of the HUD.
    draw_popups(game)


def draw_fire(game):
    """Draw the marble-box fire along its top edge (Balatro-style).

    Flames rise from the top edge of the marble box, sized by the current fire
    intensity (which grows with how much the score beat the required score and
    dies down after the run). Each flame flickers so the fire dances.
    """
    if game.fire_intensity <= 0.01:
        return
    intensity = game.fire_intensity
    x0, y0 = MARBLE_BOX_COORDS[0], MARBLE_BOX_COORDS[1] - BORD_WIDTH
    width = MARBLE_BOX_COORDS[2]
    now = pygame.time.get_ticks() / 1000.0
    scale = min(intensity, 1.5)
    flames = 16
    for i in range(flames):
        cx = x0 + (i + 0.5) / flames * width + math.sin(now * 8 + i * 2.1) * 2
        flick = 0.7 + 0.3 * math.sin(now * 11 + i * 1.7)
        outer_h = (5 + 30 * scale) * flick
        inner_h = outer_h * 0.55
        w = 8 + 10 * scale
        # Outer orange flame with a smaller yellow core.
        pygame.draw.polygon(game.screen, (255, 120, 20),
                            [(cx - w, y0), (cx + w, y0), (cx, y0 - outer_h)])
        pygame.draw.polygon(game.screen, (255, 205, 55),
                            [(cx - w * 0.5, y0), (cx + w * 0.5, y0), (cx, y0 - inner_h)])


def draw_trial_box(game):
    """Draw the current run's trial (or the final boss on the 24th run) above
    the round/run display, with its buy options while the mouse hovers it."""
    if game.final_boss is not None:
        title = "FINAL BOSS"
        desc = f"{FinalBoss.name(game.final_boss)}: {FinalBoss.description(game.final_boss)}"
    elif game.current_trial is None:
        # No trial: only worth a display when the player could buy one back.
        if not game.trials_enabled:
            return
        title = "NO TRIAL"
        desc = "This run is played without a trial."
    else:
        title = Trial.name(game.current_trial)
        desc = Trial.description(game.current_trial)
    box = TRIAL_BOX_RECT
    pygame.draw.rect(game.screen, (25, 25, 40), box, border_radius=8)
    pygame.draw.rect(game.screen, (255, 215, 0), box, 2, border_radius=8)
    title_surf = game.font.render(title, True, (255, 215, 0))
    game.screen.blit(title_surf, title_surf.get_rect(center=(box.centerx, box.top + 13)))
    lines = game._wrap_text(desc, game.tiny_font, box.width - 16)
    y = box.top + 31
    for line in lines[:3]:
        line_surf = game.tiny_font.render(line, True, (220, 220, 220))
        game.screen.blit(line_surf, line_surf.get_rect(midtop=(box.centerx, y)))
        y += line_surf.get_height() + 2
    # While the trial can still be bought, hovering the display reveals its two
    # options: the left half swaps the trial, the right half turns it off.
    if game.trial_options_available() and box.collidepoint(pygame.mouse.get_pos()):
        draw_trial_options(game, box)


def draw_trial_options(game, box):
    """Overlay the trial display's two buy options (drawn while hovering it).

    The left half buys a DIFFERENT random trial for TRIAL_CHANGE_COST and the
    right half buys no trial at all for TRIAL_DISABLE_COST. An affordable,
    meaningful option is blue like the trigger-limit upgrade overlay; an
    unaffordable one (or the right half while there is no trial to remove) is
    grey. Returns the two rects it drew, (left, right).
    """
    half = box.width // 2
    rects = (pygame.Rect(box.x, box.y, half, box.height),
             pygame.Rect(box.x + half, box.y, box.width - half, box.height))
    options = ((rects[0], "CHANGE", TRIAL_CHANGE_COST, True),
               (rects[1], "DISABLE", TRIAL_DISABLE_COST,
                game.current_trial is not None))
    for rect, label, cost, meaningful in options:
        usable = meaningful and game.cash >= cost
        # Nearly opaque: the option replaces what the display showed, so the
        # trial's own text never reads through the label.
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((45, 55, 175, 250) if usable else (72, 72, 78, 250))
        game.screen.blit(overlay, rect.topleft)
        pygame.draw.rect(game.screen, WHITE, rect, 2)
        text = game.tiny_font.render(label, True, WHITE)
        game.screen.blit(text, text.get_rect(center=(rect.centerx, rect.top + 15)))
        price = game.tiny_font.render(f"${cost}", True,
                                      YELLOW if usable else (255, 120, 120))
        game.screen.blit(price, price.get_rect(center=(rect.centerx, rect.bottom - 15)))
    return rects


def draw_score_display(game):
    """Draw the chips / mult / total / required score panel above the marble box."""
    cx = MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2] // 2  # center of the marble box
    top = MARBLE_BOX_COORDS[1]

    # Required score sits above the total, with distance and time on either side.
    required = game.required_font.render(f"{game.required_score}", True, (255, 215, 0))
    required_rect = required.get_rect(center=(cx, top - 84))
    game.screen.blit(required, required_rect)

    total_distance = sum(getattr(marble, "distance", 0.0) for marble in game.marbles)
    distance = game.small_font.render(f"DIST {int(total_distance)}", True, GREEN)
    game.screen.blit(distance, distance.get_rect(midright=(cx - required_rect.width // 2 - 16, top - 84)))

    time_text = game.small_font.render(f"TIME {game.run_time:.1f}s", True, BLUE)
    game.screen.blit(time_text, time_text.get_rect(midleft=(cx + required_rect.width // 2 + 16, top - 84)))

    # Total score is the centerpiece (rounded to a tenth for display).
    total = game.total_font.render(_fmt_tenth(game.score_total), True, WHITE)
    total_rect = total.get_rect(center=(cx, top - 50))
    game.screen.blit(total, total_rect)

    # Chips sit left of the total, mult sits right of it.
    chips = game.small_font.render(f"CHIPS {_fmt_tenth(game.score_chips)}", True, GREEN)
    game.screen.blit(chips, chips.get_rect(midright=(cx - total_rect.width // 2 - 16, top - 50)))

    mult = game.small_font.render(f"MULT {_fmt_tenth(game.score_mult)}", True, BLUE)
    game.screen.blit(mult, mult.get_rect(midleft=(cx + total_rect.width // 2 + 16, top - 50)))

    # Unique component types touched and each score factor's normalized
    # (0..1) effect on the exponent: distance, time, and uniqueness, shown
    # directly above the marble box.
    time_good, dist_good, uniq_good, unique_types = game._score_factors()
    uniq_label = game.small_font.render(f"UNIQUE {unique_types}", True, (255, 215, 0))
    game.screen.blit(uniq_label, uniq_label.get_rect(center=(cx, top - 24)))
    factors = game.small_font.render(
        f"D {dist_good:.2f}  T {time_good:.2f}  U {uniq_good:.2f}", True, WHITE)
    game.screen.blit(factors, factors.get_rect(center=(cx, top - 10)))

    # Resource points: "[N] points to next [block/card/component/action]" for
    # each owned Parts/Shreds/Rubble/Ideas scorer. (The total cash and the last
    # run's cash gain now live on the shop panel — see draw_shop.) The lines
    # sit in the left margin, right-aligned to the board's left edge.
    res_x = MARBLE_BOX_COORDS[0] - 10
    y = MARBLE_BOX_COORDS[1] + 8
    for to_next, label in game._resource_display():
        res = game.tiny_font.render(
            f"{points_text(to_next)} point{'' if to_next <= 1 else 's'} "
            f"to next {label}", True, ORANGE)
        game.screen.blit(res, res.get_rect(midright=(res_x, y)))
        y += res.get_height() + 3


def draw_run_dots(game):
    """Draw the 8x3 grid of run indicators above the actions display.

    Rounds go across (8 columns), each round's 3 runs go down (3 rows), and the
    24th (final boss) run therefore sits at the bottom right. A dot is gray
    when its run hasn't been played, green when the score target was met, and
    red when it wasn't. The final-boss run stands out: black instead of gray,
    gold when beaten, and a deeper red when lost.
    """
    x0, y0 = RUN_DOT_GRID
    for run_index in range(TOTAL_RUNS):
        # Rounds go across (columns), runs go down (rows): 8 wide x 3 tall.
        col = run_index // RUNS_PER_ROUND
        row = run_index % RUNS_PER_ROUND
        cx = x0 + col * RUN_DOT_DX
        cy = y0 + row * RUN_DOT_DY
        boss = run_index == TOTAL_RUNS - 1  # the 24th run is the final boss
        if run_index < len(game.run_results):
            if boss:
                color = (255, 215, 0) if game.run_results[run_index] else (140, 0, 0)
            else:
                color = GREEN if game.run_results[run_index] else RED
        else:
            color = BLACK if boss else GRAY
        pygame.draw.circle(game.screen, color, (cx, cy), RUN_DOT_RADIUS)
        pygame.draw.circle(game.screen, WHITE, (cx, cy), RUN_DOT_RADIUS, 1)


def draw_toolbox(game):
    """Draw the toolbox panel: its grid, title, and green selection borders."""
    box = game.toolbox
    draw_marble_box(game.screen, box.rect.x, box.rect.y, box.cols, box.rows)

    # The inventory title sits at the bottom-left of the panel. It hides
    # while the mouse is over the inventory so it never sits under the
    # cursor while the player clicks items.
    if game._show_toolbox_title():
        title = game.font.render("INVENTORY", True, WHITE)
        game.screen.blit(title, (box.rect.x + 8, box.rect.bottom - 26))

    # Green border cells: the currently selected item (block or component)
    # plus each assigned component. Index-based, so a duplicated component
    # only lights up the exact cell that was clicked/assigned — not every
    # copy that shares the same identity.
    green_indexes = set()
    si = game.selected_toolbox_index
    if (si is not None and 0 <= si < len(box.items)
            and box.items[si] is game.selected_toolbox_item):
        green_indexes.add(si)
    for comp, idx in game.assigned_toolbox_indexes.items():
        if 0 <= idx < len(box.items) and box.items[idx] is comp:
            green_indexes.add(idx)
        else:
            # The toolbox list shifted; fall back to the first occurrence.
            try:
                green_indexes.add(box.items.index(comp))
            except ValueError:
                pass

    # Gold border cells: the condition + scorer assigned to the card builder.
    gold_indexes = set()
    for comp, idx in getattr(game, "card_builder_indexes", {}).items():
        if 0 <= idx < len(box.items) and box.items[idx] is comp:
            gold_indexes.add(idx)
        else:
            try:
                gold_indexes.add(box.items.index(comp))
            except ValueError:
                pass

    for index, item in enumerate(box.items):
        col = index % box.cols
        row = index // box.cols
        rect = pygame.Rect(box.rect.x + col * GRID_SIZE, box.rect.y + row * GRID_SIZE, GRID_SIZE, GRID_SIZE)
        draw_shop_item(game.screen, item, rect)
        if index in green_indexes:
            pygame.draw.rect(game.screen, GREEN, rect, 3)
        elif index in gold_indexes:
            pygame.draw.rect(game.screen, (255, 215, 0), rect, 3)
        # The subject of an active action (a toolbox block) is gold-outlined.
        if (game.selected_action is not None and getattr(item, "kind", None) == "block"
                and game.selected_action_subject is item):
            pygame.draw.rect(game.screen, (255, 215, 0), rect, 3)


def draw_cards(game):
    """Draw the owned cards in the area above the toolbox (max MAX_CARDS).

    Owned cards render as mini playing cards; empty slots show a card back.
    The card currently selected for selling gets a green outline.
    """
    x, y = CARD_AREA_COORDS[0], CARD_AREA_COORDS[1]
    draw_marble_box(game.screen, x, y, MAX_CARDS, 1)
    title = game.small_font.render("CARDS", True, WHITE)
    game.screen.blit(title, (x + 8, y - 14))
    for i in range(MAX_CARDS):
        rect = pygame.Rect(x + i * GRID_SIZE, y, GRID_SIZE, GRID_SIZE)
        if i < len(game.cards):
            draw_card(game.screen, game.cards[i], rect,
                      selected=game.selected_toolbox_item is game.cards[i])
            # The subject of an active action (an owned card) is gold-outlined.
            if (game.selected_action is not None
                    and game.selected_action_subject is game.cards[i]):
                pygame.draw.rect(game.screen, (255, 215, 0), rect, 3, border_radius=6)
            # A card disabled by the Card cutter / deal breaker trial is dimmed.
            if game._card_disabled(game.cards[i]):
                overlay = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 120))
                game.screen.blit(overlay, rect)
        else:
            draw_card_back(game.screen, rect)


def draw_token(screen, token, rect):
    """Draw one Spirit token as a small circular poker chip.

    The face is the kept scorer's colour, the rim is a ring of dashes (poker
    chip edge spots), the scorer's name sits in the middle, and a limited
    token carries a small gold number badge showing the runs it has left. A
    PERMANENT token (a v2 Spirit) shows a gold rim instead of a badge.
    """
    center = rect.center
    radius = min(rect.width, rect.height) // 2 - 3
    pygame.draw.circle(screen, Scorer.color(token.scorer), center, radius)
    pygame.draw.circle(screen, (255, 215, 0) if token.runs_left is None else WHITE,
                       center, radius, 2)
    for i in range(8):
        angle = math.tau * i / 8
        inner = (center[0] + math.cos(angle) * (radius - 6),
                 center[1] + math.sin(angle) * (radius - 6))
        outer = (center[0] + math.cos(angle) * (radius - 1),
                 center[1] + math.sin(angle) * (radius - 1))
        pygame.draw.line(screen, WHITE, inner, outer, 3)
    label = pygame.font.Font(None, 14).render(Scorer.name(token.scorer), True, WHITE)
    screen.blit(label, label.get_rect(center=center))
    if token.runs_left is not None:
        badge = pygame.font.Font(None, 14).render(str(token.runs_left), True, (255, 215, 0))
        screen.blit(badge, (rect.right - badge.get_width() - 1, rect.top + 1))


def draw_tokens(game):
    """Draw the Spirit token chips in a column right of the inventory.

    One chip per token (see ScorerToken): each fires its kept scorer at the
    start of every run it covers. The column is a panel in the same style as
    the other areas, and nothing is drawn when the player owns no tokens.
    """
    if not game.tokens:
        return
    x, y = TOKEN_COORDS[0], TOKEN_COORDS[1]
    draw_marble_box(game.screen, x, y, 1, len(game.tokens))
    for i, token in enumerate(game.tokens):
        draw_token(game.screen, token, game._token_rect(i))
    label = game.small_font.render("TOKENS", True, WHITE)
    game.screen.blit(label, (x, y + len(game.tokens) * GRID_SIZE + 4))


def draw_action_area(game):
    """Draw the owned actions above the toolbox (max MAX_ACTIONS).

    Owned actions render as mini cards with a v1/v2 tag (a gold frame and a
    gold plate for the upgraded ones — see draw_action); empty slots show a
    back. The selected action gets a green outline, and its upgrade button
    appears beside the area (v1 -> v2 for ACTION_UPGRADE_COST).
    """
    x, y = ACTION_AREA_COORDS[0], ACTION_AREA_COORDS[1]
    draw_marble_box(game.screen, x, y, MAX_ACTIONS, 1)
    title = game.small_font.render("ACTIONS", True, WHITE)
    game.screen.blit(title, (x + 8, y - 14))
    for i in range(MAX_ACTIONS):
        rect = pygame.Rect(x + i * GRID_SIZE, y, GRID_SIZE, GRID_SIZE)
        if i < len(game.actions):
            draw_action(game.screen, game.actions[i], rect,
                        selected=game.selected_action is game.actions[i])
        else:
            draw_action_back(game.screen, rect)
    # The upgrade button shows while an action is selected.
    action = game.selected_action
    if action is not None and action in game.actions:
        btn = ACTION_UPGRADE_RECT
        if action.version >= 2:
            text, affordable = "MAXED (v2)", False
        else:
            # The inflation trial raises the action-upgrade fee.
            cost = game._inflated(ACTION_UPGRADE_COST)
            text = f"UPGRADE ${cost}"
            affordable = game.cash >= cost
        pygame.draw.rect(game.screen, (70, 70, 200) if affordable else (90, 90, 90), btn)
        pygame.draw.rect(game.screen, WHITE, btn, 2)
        label = game.small_font.render(text, True,
                                       WHITE if affordable else (255, 120, 120))
        game.screen.blit(label, label.get_rect(center=btn.center))


def draw_sell_overlay(game):
    """Draw a SELL overlay on the toolbox's bottom-right cell when an item is selected."""
    item = game.selected_toolbox_item
    if item is None:
        return
    if item not in game.toolbox.items:
        return  # a placed block selected in the marble box isn't sellable
    rect = SELL_OVERLAY_RECT
    overlay = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
    # The run's role blocks (Start/Finish) can never be sold: their cell shows
    # a plain refusal instead of a price (see Game._unsellable).
    unsellable = game._unsellable(item)
    overlay.fill((90, 90, 95, 200) if unsellable else (200, 30, 30, 200))
    game.screen.blit(overlay, rect)
    pygame.draw.rect(game.screen, WHITE, rect, 2)
    text1 = game.tiny_font.render("SELL[B]", True, WHITE)
    if unsellable:
        price_text, price_color = "NO SALE", (200, 200, 200)
    else:
        total_price = game._total_price(item)
        total_price = total_price if total_price else item.price
        price_text = f"${int(total_price * game._sell_fraction())}"
        price_color = YELLOW
    text2 = game.tiny_font.render(price_text, True, price_color)
    game.screen.blit(text1, text1.get_rect(center=(rect.centerx, rect.top + 13)))
    game.screen.blit(text2, text2.get_rect(center=(rect.centerx, rect.bottom - 13)))


def draw_upgrade_overlay(game):
    """Draw an UPGRADE overlay (trigger-limit cost) on the toolbox cell left of
    the SELL cell when a block is selected."""
    item = game.selected_toolbox_item
    if item is None or not isinstance(item, (Block, BlockItem)):
        return
    if item not in game.toolbox.items:
        return  # a placed block selected in the marble box isn't sellable/upgradeable here
    rect = UPGRADE_OVERLAY_RECT
    cost = game._trigger_upgrade_cost(item)
    affordable = game.cash >= cost
    overlay = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
    overlay.fill((70, 70, 200, 200) if affordable else (90, 90, 90, 200))
    game.screen.blit(overlay, rect)
    pygame.draw.rect(game.screen, WHITE, rect, 2)
    text1 = game.tiny_font.render("UP[D]", True, WHITE)
    text2 = game.tiny_font.render(f"${cost}", True, YELLOW if affordable else (255, 120, 120))
    game.screen.blit(text1, text1.get_rect(center=(rect.centerx, rect.top + 13)))
    game.screen.blit(text2, text2.get_rect(center=(rect.centerx, rect.bottom - 13)))


def last_run_cash_rect(game):
    """The screen rect of the shop's "Last run cash gained" readout.

    The readout is what the player hovers to see where the last run's cash
    came from (Game._info_target_at turns it into a hover target), so the rect
    is measured here and shared by the drawing and the hit test.
    """
    text = game.small_font.render(
        f"Last run cash gained: {game.last_run_cash_gained}", True, GREEN)
    return text.get_rect(topright=(game.shop.rect.right - 8, game.shop.rect.y + 8))


def shop_message_layout(game, message):
    """Lay a shop message out in the shop panel's bottom strip.

    The message lives in the band between the SHOP title (bottom-left) and the
    REFRESH button (bottom-right), so it never covers the cash header or the
    shop items. A message that fits the gap is one small-font line; a wider one
    wraps onto up to two tiny-font lines. Returns (lines, rect): the rendered
    line surfaces and the rect they are centred on.
    """
    shop = game.shop.rect
    left = shop.x + 8 + game.font.size("SHOP")[0] + 8
    right = SHOP_REFRESH_BUTTON_RECT.left - 8
    gap = max(60, right - left)
    center = ((left + right) // 2, SHOP_REFRESH_BUTTON_RECT.centery)
    msg = game.small_font.render(message, True, YELLOW)
    if msg.get_width() <= gap:
        return [msg], msg.get_rect(center=center)
    lines = [game.tiny_font.render(line, True, YELLOW)
             for line in game._wrap_text(message, game.tiny_font, gap)][:2]
    rect = pygame.Rect(0, 0, max(line.get_width() for line in lines),
                       sum(line.get_height() + 1 for line in lines))
    rect.center = center
    return lines, rect


def draw_shop(game):
    """Draw the shop panel, its items, prices, refresh button, and messages."""
    shop = game.shop
    draw_marble_box(game.screen, shop.rect.x, shop.rect.y, shop.cols, shop.rows)

    # The shop title sits at the bottom-left of the panel. It hides while the
    # mouse is over the shop so it never sits under the cursor.
    if game._show_shop_title():
        title = game.font.render("SHOP", True, WHITE)
        game.screen.blit(title, (shop.rect.x + 8, shop.rect.bottom - 26))

    # Cash header along the shop's (empty) top row: the total cash sits at the
    # top-left and the most recent run's cash gain at the top-right (hovering
    # that readout breaks the run's earnings down — see last_run_cash_rect).
    cash_text = game.small_font.render(f"Cash: {game.cash}", True, WHITE)
    game.screen.blit(cash_text, (shop.rect.x + 8, shop.rect.y + 8))
    gained_text = game.small_font.render(
        f"Last run cash gained: {game.last_run_cash_gained}", True, GREEN)
    game.screen.blit(gained_text, last_run_cash_rect(game))

    # Reroll button above the shop's top-right corner. When a Fresh reroll is
    # banked, it reads FREE (and shows how many are left) instead of the fee.
    refresh_btn = SHOP_REFRESH_BUTTON_RECT
    pygame.draw.rect(game.screen, (60, 60, 160), refresh_btn)
    pygame.draw.rect(game.screen, WHITE, refresh_btn, 2)
    free = getattr(game, "free_rerolls", 0)
    if free > 0:
        label = f"REFRESH FREE ({free})" if free > 1 else "REFRESH FREE"
        refresh_text = game.small_font.render(label, True, YELLOW)
    else:
        # The inflation trial raises the reroll fee (both here and in the
        # charge in _refresh_shop), so the label shows the effective cost.
        cost = game._inflated(SHOP_REFRESH_COST)
        refresh_text = game.small_font.render(f"REFRESH ${cost}", True, WHITE)
    game.screen.blit(refresh_text, refresh_text.get_rect(center=refresh_btn.center))

    for item in shop.items:
        rect = pygame.Rect(shop.rect.x + item.col * GRID_SIZE, shop.rect.y + item.row * GRID_SIZE, GRID_SIZE, GRID_SIZE)
        draw_shop_item(game.screen, item, rect)
        # Show the effective price (component prices rise with each purchase).
        # An already-upgraded action is sold at the normal action price but is
        # worth ACTION_UPGRADE_COST more, so its price is drawn in the gold of
        # its own frame to flag the bargain (see draw_action).
        upgraded = (getattr(item, "kind", None) == "action"
                    and getattr(item, "version", 1) >= 2)
        price = game.small_font.render(f"${game._buy_price(item)}", True,
                                       (255, 215, 0) if upgraded else WHITE)
        center_x = shop.rect.x + item.col * GRID_SIZE + GRID_SIZE // 2
        price_y = shop.rect.y + (item.row + 1) * GRID_SIZE + GRID_SIZE // 2
        game.screen.blit(price, price.get_rect(center=(center_x, price_y)))

    # The shop's always-present Board Unit tile (the rightmost unit of the
    # bottom item row): $4 buys an expansion the player spends by clicking a
    # locked square on the board. A counter shows how many are in hand.
    bcell = pygame.Rect(shop.rect.x + BOARD_UNIT_COL * GRID_SIZE,
                        shop.rect.y + BOARD_UNIT_ROW * GRID_SIZE,
                        GRID_SIZE, GRID_SIZE)
    pygame.draw.rect(game.screen, (45, 95, 55), bcell)
    pygame.draw.rect(game.screen, WHITE, bcell, 2)
    # A plus icon reads as "expand the board" (mini 2x3 grid hint).
    pygame.draw.rect(game.screen, (255, 255, 255), (bcell.x + 9, bcell.y + 7, 22, 26), 1)
    pygame.draw.line(game.screen, (255, 255, 255), (bcell.centerx, bcell.y + 10),
                     (bcell.centerx, bcell.y + 30), 2)
    pygame.draw.line(game.screen, (255, 255, 255), (bcell.x + 12, bcell.centery),
                     (bcell.x + 28, bcell.centery), 2)
    if game.board_units > 0:
        badge = game.tiny_font.render(f"x{game.board_units}", True, YELLOW)
        game.screen.blit(badge, badge.get_rect(bottomright=(bcell.right - 3, bcell.bottom - 3)))
    bu_price = game.small_font.render(f"${game._board_unit_price()}", True, WHITE)
    bu_center_x = bcell.centerx
    bu_price_y = shop.rect.y + (BOARD_UNIT_ROW + 1) * GRID_SIZE + GRID_SIZE // 2
    game.screen.blit(bu_price, bu_price.get_rect(center=(bu_center_x, bu_price_y)))

    if game.shop_message:
        lines, rect = shop_message_layout(game, game.shop_message)
        y = rect.top
        for line in lines:
            game.screen.blit(line, line.get_rect(midtop=(rect.centerx, y)))
            y += line.get_height() + 1


def draw_sidebar(game):
    """Draw the info box for the item the mouse is hovering over.

    The box appears only while the cursor is over a shop item, toolbox
    item, owned card, or placed block, and its size is based on the length
    of the item's description rather than a fixed panel.
    """
    mouse_pos = pygame.mouse.get_pos()
    item, source = game._info_target_at(mouse_pos)
    if item is None:
        return
    game._draw_item_info(item, source, mouse_pos)


def info_layout(game, item, source):
    """Measure an item's info box content.

    Returns (width, height, name_lines, desc_lines, hint). width/height are
    the box's content size (before padding), based on the length of the item's
    description: lines are word-wrapped at a maximum width and the box grows to
    fit the widest line and the total number of lines. desc_lines are (text,
    kind) pairs where kind is "label" or "body".
    """
    max_text_width = 240  # a line wider than this wraps onto the next
    name_lines = game._wrap_text(game._item_name(item), game.font, max_text_width)
    rows = game._describe_item(item)
    desc_lines = []
    for label, text in rows:
        desc_lines.append((label, "label"))
        desc_lines.extend((line, "body")
                          for line in game._wrap_text(text, game.small_font, max_text_width))
    hint = game._action_hint(item, source)

    width = max([game.font.size(line)[0] for line in name_lines] or [0])
    width = max(width, max([game.small_font.size(line)[0] for line, _ in desc_lines] or [0]))
    if hasattr(item, "price"):
        width = max(width, game.small_font.size(f"${item.price}")[0])
        total = game._total_price(item)
        if total is not None:
            width = max(width, game.small_font.size(f"TOTAL ${total}")[0])
    if hint:
        width = max(width, game.small_font.size(hint)[0])
    width = min(width, max_text_width)

    height = len(name_lines) * 26
    if getattr(item, "kind", None) in ("card", "action"):
        height += 62  # mini-card/action face (40x52) + gap
    if hasattr(item, "price"):
        height += 20
        if game._total_price(item) is not None:
            height += 20
    height += len(desc_lines) * 17 + len(rows) * 6  # row text + gaps
    if hint:
        height += 17
    return width + 12, height, name_lines, desc_lines, hint


def info_box_rect(game, item, source, mouse_pos):
    """The on-screen rect for an item's info box.

    Sized to the item's description (via info_layout) and positioned near the
    cursor, clamped to stay fully on-screen.
    """
    width, height, _, _, _ = info_layout(game, item, source)
    pad = 12
    rect = pygame.Rect(0, 0, width + 2 * pad, height + 2 * pad)
    rect.x = mouse_pos[0] - width // 2
    rect.y = mouse_pos[1] + GRID_SIZE
    if rect.right > SCREEN_WIDTH - 8:
        rect.right = max(8, mouse_pos[0] - 14)
    rect.bottom = min(rect.bottom, SCREEN_HEIGHT - 8)
    rect.x = max(rect.x, 8)
    rect.y = max(rect.y, 8)
    return rect


def draw_item_info(game, item, source, mouse_pos):
    """Draw a content-sized info box for the given item near the cursor."""
    rect = info_box_rect(game, item, source, mouse_pos)
    _, _, name_lines, desc_lines, hint = info_layout(game, item, source)
    pygame.draw.rect(game.screen, MARBLE_BOX_COLOR, rect)
    pygame.draw.rect(game.screen, BLACK, rect, 5)
    x = rect.x + 12
    y = rect.y + 12

    # An owned card/action gets a mini face at the top of the box.
    if getattr(item, "kind", None) in ("card", "action"):
        face = pygame.Rect(x, y, 40, 52)
        if getattr(item, "kind", None) == "card":
            draw_card(game.screen, item, face)
        else:
            draw_action(game.screen, item, face)
        y += face.height + 10

    # The name can be long (every effect + shape + scorer + trigger limit),
    # so wrap it onto multiple lines to keep it inside the box.
    for line in name_lines:
        game.screen.blit(game.font.render(line, True, (255, 215, 0)), (x, y))
        y += 26

    if hasattr(item, "price"):
        # Original price (without trigger-limit upgrades).
        price = game.small_font.render(f"${item.price}", True, WHITE)
        game.screen.blit(price, (x, y))
        y += 20
        # Blocks with trigger upgrades also show their total price.
        total = game._total_price(item)
        if total is not None:
            total_text = game.small_font.render(f"TOTAL ${total}", True, (255, 215, 0))
            game.screen.blit(total_text, (x, y))
            y += 20

    for line, kind in desc_lines:
        color = GREEN if kind == "label" else WHITE
        indent = 0 if kind == "label" else 8
        _draw_description_line(game, line, color, x + indent, y)
        y += 17

    if hint:
        hint_surf = game.small_font.render(hint, True, YELLOW)
        game.screen.blit(hint_surf, (x, y))


def _deviation_color(word):
    """The colour for a magnitude deviation token like "(+2)", or None.

    A magnitude describes itself with the deviation right after it — "Adds +6
    mult (+2) when touched" — and the sidebar colours that token: green when
    the item rolled above its average, red when below, and grey when it landed
    exactly on it. Only a bare signed number counts, so the other parentheses
    in the game's text ("(including itself)", "base size (8 px)") stay plain.
    A trailing ".", "," or ";" belongs to the sentence rather than the token
    ("Gives 0.7 rubble point (+0.2). 1 point converts into a random block"), so
    it is set aside before the token itself is read.
    """
    token = word.rstrip(".,;:")
    if len(token) < 3 or token[0] != "(" or token[-1] != ")":
        return None
    inner = token[1:-1]
    if inner[0] in "+-":
        return GREEN if inner[0] == "+" else RED
    return GRAY if inner == "0" else None


def _draw_description_line(game, line, color, x, y, font=None):
    """Draw one description line, colouring any deviation token in it.

    ``font`` defaults to the sidebar's small_font; the collection screen passes
    its own tiny font so its descriptions follow the same colouring rule.
    """
    font = font or game.small_font
    space = font.size(" ")[0]
    for word in line.split():
        tint = _deviation_color(word) or color
        surface = font.render(word, True, tint)
        game.screen.blit(surface, (x, y))
        x += surface.get_width() + space


def _draw_difficulty_picker(game):
    """Draw the new-save screen's difficulty picker (a column of four levels).

    The chosen level is outlined in gold and its own rules are spelled out
    underneath, so the player can see what each level changes: how many trials
    a round is played under and how fast the required score grows (see
    Difficulty).
    """
    label = game.tiny_font.render("DIFFICULTY", True, WHITE)
    game.screen.blit(label, label.get_rect(midtop=(170, 252)))
    for i, level in enumerate(Difficulty.ORDER):
        rect = game.difficulty_button_rect(i)
        chosen = level == game.difficulty
        pygame.draw.rect(game.screen, (30, 32, 46), rect, border_radius=10)
        pygame.draw.rect(game.screen,
                         (255, 215, 0) if chosen else (120, 120, 140),
                         rect, 3 if chosen else 2, border_radius=10)
        name = game.font.render(Difficulty.name(level), True,
                                (255, 215, 0) if chosen else WHITE)
        game.screen.blit(name, name.get_rect(center=rect.center))
    y = game.difficulty_button_rect(len(Difficulty.ORDER) - 1).bottom + 12
    for line in game._wrap_text(Difficulty.description(game.difficulty),
                                game.tiny_font, 280):
        surf = game.tiny_font.render(line, True, (220, 220, 220))
        game.screen.blit(surf, (30, y))
        y += 14


def draw_marble_select(game):
    """Draw the new-save screen: the difficulty picker and the marble types.

    The player picks this save's difficulty (how many trials a round is played
    under and how fast the required score grows — see Difficulty) and exactly
    one marble type; both are persisted with the save. A preview of each marble
    type sits beside its name and description.
    """
    game.screen.fill(BG_COLOR)
    heading = game.main_title_font.render("CHOOSE YOUR MARBLE", True, (255, 215, 0))
    game.screen.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 90)))
    sub = game.font.render("Pick a difficulty, then a marble type", True, WHITE)
    game.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 150)))
    _draw_difficulty_picker(game)
    for i, mt in enumerate(MarbleType.ORDER):
        rect = game.marble_card_rect(i)
        pygame.draw.rect(game.screen, (30, 32, 46), rect, border_radius=14)
        pygame.draw.rect(game.screen, (255, 215, 0), rect, 3, border_radius=14)
        preview = game._marble_preview(mt)
        preview.position = np.array([rect.left + 62, rect.centery], dtype=float)
        draw_marble(preview, game.screen)
        name = game.total_font.render(MarbleType.NAMES[mt], True, WHITE)
        game.screen.blit(name, (rect.left + 122, rect.top + 20))
        desc_lines = game._wrap_text(MarbleType.DESCRIPTIONS[mt], game.small_font,
                                     rect.width - 160)
        y = rect.top + 62
        for line in desc_lines:
            surf = game.small_font.render(line, True, (200, 200, 200))
            game.screen.blit(surf, (rect.left + 122, y))
            y += 18
    back = MARBLE_BACK_BUTTON_RECT
    pygame.draw.rect(game.screen, (60, 60, 80), back)
    pygame.draw.rect(game.screen, WHITE, back, 2)
    text = game.font.render("BACK", True, WHITE)
    game.screen.blit(text, text.get_rect(center=back.center))
    # Toggle for this save's permanent metagame upgrade effects (on by
    # default; off gives a clean, upgrade-free run).
    toggle = MARBLE_UPGRADES_TOGGLE_RECT
    toggle_color = (40, 130, 65) if game.upgrades_enabled else (130, 60, 50)
    pygame.draw.rect(game.screen, toggle_color, toggle, border_radius=10)
    pygame.draw.rect(game.screen, WHITE, toggle, 2, border_radius=10)
    label = game.small_font.render(
        f"UPGRADE EFFECTS: {'ON' if game.upgrades_enabled else 'OFF'}",
        True, WHITE)
    game.screen.blit(label, label.get_rect(center=toggle.center))
def draw_upgrades(game):
    """Draw the UPGRADES tab: the dice balance and the three permanent
    run-start upgrades the player can spend dice on (click a card to buy)."""
    game.screen.fill(BG_COLOR)
    heading = game.main_title_font.render("UPGRADES", True, (255, 215, 0))
    game.screen.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 70)))
    dice_text = game.font.render(f"DICE: {metagame.dice()}", True, WHITE)
    game.screen.blit(dice_text, dice_text.get_rect(center=(SCREEN_WIDTH // 2, 145)))
    for i, upgrade in enumerate(metagame.UPGRADES):
        rect = game.upgrade_card_rect(i)
        pygame.draw.rect(game.screen, (30, 32, 46), rect, border_radius=14)
        pygame.draw.rect(game.screen, (255, 215, 0), rect, 3, border_radius=14)
        name = game.total_font.render(upgrade["name"], True, WHITE)
        game.screen.blit(name, name.get_rect(center=(rect.centerx, rect.top + 36)))
        bonus = game.small_font.render(metagame.bonus_text(upgrade["id"]),
                                       True, (200, 200, 200))
        game.screen.blit(bonus, bonus.get_rect(center=(rect.centerx, rect.top + 80)))
        for j, line in enumerate(game._wrap_text(upgrade["desc"], game.tiny_font,
                                                 rect.width - 24)):
            surf = game.tiny_font.render(line, True, (150, 150, 160))
            game.screen.blit(surf, surf.get_rect(center=(rect.centerx, rect.top + 110 + j * 16)))
        afford = metagame.dice() >= upgrade["cost"]
        cost = game.font.render(f"{upgrade['cost']} DICE",
                                True, GREEN if afford else (220, 80, 80))
        game.screen.blit(cost, cost.get_rect(center=(rect.centerx, rect.bottom - 26)))
    if game.shop_message:
        msg = game.small_font.render(game.shop_message, True, YELLOW)
        game.screen.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, 205)))
    back = UPGRADES_BACK_BUTTON_RECT
    pygame.draw.rect(game.screen, (60, 60, 80), back)
    pygame.draw.rect(game.screen, WHITE, back, 2)
    text = game.font.render("RETURN TO MAIN MENU", True, WHITE)
    game.screen.blit(text, text.get_rect(center=back.center))
def draw_collection_icon(game, kind, value, rect):
    """Draw an entry's icon (a mini card, a shape outline, an effect icon, or a
    scorer tile) into the given rect. Trials and the final boss have no icon."""
    if kind == "card":
        draw_card(game.screen, CardItem(value, 0), rect)
        return
    if kind == "action":
        draw_action(game.screen, ActionItem(value, 0), rect)
        return
    if kind == "condition":
        # A condition tile: its white face with a center mini shape/effect
        # (collision conditions) or letter glyph (named ones).
        pygame.draw.rect(game.screen, condition_color(value), rect)
        pygame.draw.rect(game.screen, BLACK, rect, 2)
        _draw_condition_center(game.screen, value, rect, glyph_size=18)
        return
    if kind == Component.SCORER:
        if value == Scorer.START:
            # A Start block: an empty unit with a marble in its center.
            _draw_marble_icon(game.screen, rect.center, MARBLE_RADIUS)
            return
        if value == Scorer.FINISH:
            # A Finish block: a white-and-black checkerboard goal.
            _draw_checkerboard(game.screen, rect)
            pygame.draw.rect(game.screen, WHITE, rect, 2)
            return
        # Other scorers: a square filled with the scorer's color inside a
        # white border (the same look as the in-game scorer component).
        pygame.draw.rect(game.screen, Scorer.color(value), rect)
        pygame.draw.rect(game.screen, WHITE, rect, 2)
        return
    shape = Shape.RECT if kind == "effect" else value
    block = Block(0, 0, shape=shape,
                  effect=(value if kind == "effect" else Effect.NONE),
                  scorer=Scorer.NONE,
                  origin=(rect.x, rect.y))
    if kind == "effect":
        _draw_block_effect_icon(block, game.screen)
    else:
        draw_block_shape_only(block, game.screen)


def draw_collection(game):
    """Draw the COLLECTION tab: every card, component, and trial the player can
    encounter. Entries are revealed only once bought (cards and components) or
    beaten (trials); the rest show \"???\" with a black question-mark icon.
    Scrollable with the mouse wheel."""
    game.screen.fill(BG_COLOR)
    entries = game._collection_entries()
    cols = 5
    card_w, card_h = 212, 92
    gap_x, gap_y = 14, 14
    x0 = (SCREEN_WIDTH - (cols * card_w + (cols - 1) * gap_x)) // 2
    y0 = 118
    rows = (len(entries) + cols - 1) // cols
    total_h = y0 + rows * (card_h + gap_y)
    max_scroll = max(0, total_h - (SCREEN_HEIGHT - 96))
    game.collection_scroll = max(0, min(game.collection_scroll, max_scroll))
    for i, (kind, value, name, desc, has_icon, discovered) in enumerate(entries):
        col = i % cols
        row = i // cols
        x = x0 + col * (card_w + gap_x)
        y = y0 + row * (card_h + gap_y) - game.collection_scroll
        rect = pygame.Rect(x, y, card_w, card_h)
        if rect.bottom < 96 or rect.top > SCREEN_HEIGHT - 90:
            continue
        if discovered:
            pygame.draw.rect(game.screen, (30, 32, 46), rect, border_radius=10)
            pygame.draw.rect(game.screen, (255, 215, 0), rect, 2, border_radius=10)
        else:
            pygame.draw.rect(game.screen, (20, 20, 28), rect, border_radius=10)
            pygame.draw.rect(game.screen, (110, 110, 120), rect, 2, border_radius=10)
        icon_rect = pygame.Rect(rect.left + 8, rect.top + 8, 40, 40)
        if discovered and has_icon:
            draw_collection_icon(game, kind, value, icon_rect)
        else:
            # A locked entry's icon is a black square with a white "???".
            pygame.draw.rect(game.screen, BLACK, icon_rect)
            pygame.draw.rect(game.screen, (90, 90, 100), icon_rect, 1)
            q = game.tiny_font.render("???", True, WHITE)
            game.screen.blit(q, q.get_rect(center=icon_rect.center))
        name_color = WHITE if discovered else (140, 140, 150)
        name_surf = game.small_font.render(name, True, name_color)
        game.screen.blit(name_surf, (rect.left + 54, rect.top + 10))
        desc_color = (210, 210, 210) if discovered else (110, 110, 120)
        dy = rect.top + 34
        for line in game._wrap_text(desc, game.tiny_font, rect.width - 62)[:3]:
            _draw_description_line(game, line, desc_color, rect.left + 54, dy,
                                   game.tiny_font)
            dy += 14
    pygame.draw.rect(game.screen, BG_COLOR, (0, 0, SCREEN_WIDTH, 110))
    pygame.draw.rect(game.screen, BG_COLOR, (0, SCREEN_HEIGHT - 96, SCREEN_WIDTH, 96))
    heading = game.main_title_font.render("COLLECTION", True, (255, 215, 0))
    game.screen.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 46)))
    hint = game.tiny_font.render(
        "Buy a card/action/component or beat a run with a trial or the final boss to reveal it  •  scroll to browse",
        True, (180, 180, 180))
    game.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 92)))
    back = COLLECTION_BACK_BUTTON_RECT
    pygame.draw.rect(game.screen, (60, 60, 80), back)
    pygame.draw.rect(game.screen, WHITE, back, 2)
    text = game.font.render("RETURN TO MAIN MENU", True, WHITE)
    game.screen.blit(text, text.get_rect(center=back.center))
def profile_menu_geometry(names):
    """Rects for the expandable profile list stacked above the PROFILE button.

    Returns (panel, [one row rect per profile], '+' row rect). The list grows
    upward from the bottom-left button so it never runs off the screen bottom.
    """
    button = PROFILE_BUTTON_RECT
    width = 260
    row_h = 40
    gap = 2
    pad = 6
    count = len(names) + 1  # the profiles plus the '+' row
    panel_h = count * row_h + (count - 1) * gap + 2 * pad
    panel = pygame.Rect(button.left, button.top - 8 - panel_h, width, panel_h)
    rows = []
    y = panel.top + pad
    for _ in range(count):
        rows.append(pygame.Rect(panel.left + 4, y, panel.width - 8, row_h))
        y += row_h + gap
    return panel, rows[:-1], rows[-1]


def profile_name_panel_rects():
    """Rects for the profile name/edit popup:
    (panel, entry, cancel, delete, unlock)."""
    box = pygame.Rect(SCREEN_WIDTH // 2 - 280, 250, 560, 320)
    entry = pygame.Rect(box.left + 70, box.top + 86, box.width - 140, 46)
    cancel = pygame.Rect(box.right - 160, box.bottom - 52, 130, 38)
    delete = pygame.Rect(box.left + 22, box.bottom - 52, 150, 38)
    unlock = pygame.Rect(box.left + 186, box.bottom - 52, 210, 38)
    return box, entry, cancel, delete, unlock


def profile_name_cancel_rect():
    """The Cancel (bottom-right) button on the profile popup; while confirming
    a delete or unlock it acts as the Keep button."""
    return profile_name_panel_rects()[2]


def profile_name_delete_rect():
    """The red Delete (bottom-left) button on the profile edit popup; while
    confirming an unlock it acts as the Unlock button."""
    return profile_name_panel_rects()[3]


def profile_name_unlock_rect():
    """The Unlock-collection (center-bottom) button on the profile edit popup."""
    return profile_name_panel_rects()[4]


def _draw_profile_button(game):
    """The bottom-left PROFILE button showing the active profile's name."""
    rect = PROFILE_BUTTON_RECT
    pygame.draw.rect(game.screen, (45, 45, 70), rect)
    pygame.draw.rect(game.screen,
                     (255, 215, 0) if game.profile_menu_open else WHITE,
                     rect, 2)
    label = f"Profile: {profiles.current_profile()}"
    while game.small_font.size(label)[0] > rect.width - 16 and len(label) > 9:
        label = label[:-1]
    text = game.small_font.render(label, True, WHITE)
    game.screen.blit(text, text.get_rect(midleft=(rect.left + 10, rect.centery)))


def _draw_profile_menu(game):
    """The expandable profile list (current highlighted) plus the '+' row."""
    names = profiles.list_profiles()
    panel, name_rows, plus = profile_menu_geometry(names)
    pygame.draw.rect(game.screen, (22, 22, 38), panel, border_radius=8)
    pygame.draw.rect(game.screen, WHITE, panel, 2, border_radius=8)
    current = profiles.current_profile()
    for i, name in enumerate(names):
        row = name_rows[i]
        if name == current:
            pygame.draw.rect(game.screen, (70, 62, 20), row)
            pygame.draw.rect(game.screen, (255, 215, 0), row, 2)
        else:
            pygame.draw.rect(game.screen, (48, 48, 78), row)
            pygame.draw.rect(game.screen, (120, 120, 140), row, 1)
        row_text = game.small_font.render(name, True, WHITE)
        game.screen.blit(row_text,
                         row_text.get_rect(midleft=(row.left + 12, row.centery)))
    # The '+' row creates a brand-new profile (its name is typed in the prompt).
    pygame.draw.rect(game.screen, (28, 80, 44), plus)
    pygame.draw.rect(game.screen, (110, 190, 130), plus, 2)
    plus_glyph = game.total_font.render("+", True, WHITE)
    game.screen.blit(plus_glyph,
                     plus_glyph.get_rect(midleft=(plus.left + 14, plus.centery)))
    new_label = game.small_font.render("New profile", True, WHITE)
    game.screen.blit(new_label,
                     new_label.get_rect(midleft=(plus.left + 46, plus.centery)))


def _draw_profile_delete_confirm(game, box, keep_rect, delete_rect):
    """The inline confirm shown after Delete is clicked in the edit popup."""
    heading = game.total_font.render("DELETE PROFILE?", True, WHITE)
    game.screen.blit(heading, heading.get_rect(center=(box.centerx, box.top + 44)))
    name = game.profile_name_text.strip() or profiles.current_profile()
    msg = f"Delete '{name}' and all of its data?"
    y = box.top + 112
    for line in game._wrap_text(msg, game.font, box.width - 90):
        surf = game.font.render(line, True, (235, 235, 235))
        game.screen.blit(surf, surf.get_rect(center=(box.centerx, y)))
        y += 30
    if getattr(game, "profile_delete_error", False):
        note = game.small_font.render(
            "Couldn't delete the folder — it may be in use. Try again.",
            True, (255, 130, 130))
        game.screen.blit(note, note.get_rect(center=(box.centerx, box.top + 170)))
    # Bottom-right Keep (cancel rect).
    pygame.draw.rect(game.screen, (70, 70, 95), keep_rect)
    pygame.draw.rect(game.screen, WHITE, keep_rect, 2)
    keep_text = game.font.render("Keep", True, WHITE)
    game.screen.blit(keep_text, keep_text.get_rect(center=keep_rect.center))
    # Bottom-left Delete.
    pygame.draw.rect(game.screen, (190, 45, 45), delete_rect)
    pygame.draw.rect(game.screen, WHITE, delete_rect, 2)
    del_text = game.font.render("Delete", True, WHITE)
    game.screen.blit(del_text, del_text.get_rect(center=delete_rect.center))


def _draw_profile_unlock_confirm(game, box, keep_rect, unlock_rect):
    """The inline confirm shown after the Unlock-collection button is clicked.

    Explains that unlocking everything permanently disables achievements; the
    bottom buttons become Keep (bottom-right) / Unlock (bottom-left).
    """
    heading = game.total_font.render("UNLOCK COLLECTION?", True, WHITE)
    game.screen.blit(heading,
                     heading.get_rect(center=(box.centerx, box.top + 44)))
    msg = ("Reveal every entry in the collection for this profile? This "
           "permanently disables ALL achievements — no new ones can unlock "
           "after this (already-earned ones stay).")
    y = box.top + 112
    for line in game._wrap_text(msg, game.font, box.width - 90):
        color = (255, 190, 150) if "disables ALL" in line else (235, 235, 235)
        surf = game.font.render(line, True, color)
        game.screen.blit(surf, surf.get_rect(center=(box.centerx, y)))
        y += 30
    # Bottom-right Keep (cancel rect).
    pygame.draw.rect(game.screen, (70, 70, 95), keep_rect)
    pygame.draw.rect(game.screen, WHITE, keep_rect, 2)
    keep_text = game.font.render("Keep", True, WHITE)
    game.screen.blit(keep_text, keep_text.get_rect(center=keep_rect.center))
    # Bottom-left Unlock (the edit popup's delete rect).
    pygame.draw.rect(game.screen, (190, 110, 45), unlock_rect)
    pygame.draw.rect(game.screen, WHITE, unlock_rect, 2)
    unlock_text = game.font.render("Unlock", True, WHITE)
    game.screen.blit(unlock_text, unlock_text.get_rect(center=unlock_rect.center))


def _draw_profile_name_prompt(game):
    """The modal popup for creating or editing (renaming/deleting) a profile.

    Create mode shows an empty name field. Edit mode (clicking the active
    profile) pre-fills the field with its name, swaps the heading to RENAME
    PROFILE, and adds a red Delete button (bottom-left) plus an
    Unlock-collection button (center) that disables achievements. Clicking
    Delete or Unlock collection swaps the field for an inline confirm whose
    bottom buttons become Keep (bottom-right) / Delete or Unlock (bottom-left).
    """
    box, entry, cancel, delete, unlock = profile_name_panel_rects()
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    game.screen.blit(overlay, (0, 0))
    pygame.draw.rect(game.screen, (30, 30, 46), box, border_radius=12)
    pygame.draw.rect(game.screen, (255, 215, 0), box, 3, border_radius=12)
    if game.profile_delete_confirm:
        _draw_profile_delete_confirm(game, box, cancel, delete)
        return
    if game.profile_unlock_confirm:
        _draw_profile_unlock_confirm(game, box, cancel, delete)
        return
    if game.profile_renaming:
        heading = game.total_font.render("RENAME PROFILE", True, WHITE)
        hint_text = "Type a new name, then press Enter"
    else:
        heading = game.total_font.render("NEW PROFILE", True, WHITE)
        hint_text = "Type a name, then press Enter"
    game.screen.blit(heading,
                     heading.get_rect(center=(box.centerx, box.top + 40)))
    pygame.draw.rect(game.screen, (8, 8, 18), entry)
    pygame.draw.rect(game.screen, WHITE, entry, 2)
    shown = game.profile_name_text
    while (game.font.size(shown)[0] > entry.width - 24 and len(shown) > 1):
        shown = shown[:-1]
    surf = game.font.render(shown, True, WHITE)
    game.screen.blit(surf,
                     surf.get_rect(midleft=(entry.left + 10, entry.centery)))
    # A static caret so the player can see where typing lands.
    caret_x = entry.left + 12 + surf.get_width()
    pygame.draw.line(game.screen, WHITE, (caret_x, entry.top + 8),
                     (caret_x, entry.bottom - 8), 2)
    hint = game.small_font.render(hint_text, True, (200, 200, 212))
    game.screen.blit(hint, hint.get_rect(center=(box.centerx, box.top + 160)))
    # Bottom-right Cancel (kept from the original create popup).
    pygame.draw.rect(game.screen, (70, 70, 95), cancel)
    pygame.draw.rect(game.screen, WHITE, cancel, 2)
    cancel_text = game.font.render("Cancel", True, WHITE)
    game.screen.blit(cancel_text, cancel_text.get_rect(center=cancel.center))
    # Edit mode only: Delete (bottom-left) and the Unlock-collection button
    # (center) with a caution line above it.
    if game.profile_renaming:
        caution = ("Unlock collection reveals everything, but disables "
                   "achievements for this profile (permanent).")
        cy = box.bottom - 96
        for line in game._wrap_text(caution, game.small_font, box.width - 120):
            note = game.small_font.render(line, True, (255, 175, 130))
            game.screen.blit(note, note.get_rect(center=(box.centerx, cy)))
            cy += 18
        pygame.draw.rect(game.screen, (180, 45, 45), delete)
        pygame.draw.rect(game.screen, WHITE, delete, 2)
        del_text = game.font.render("Delete", True, WHITE)
        game.screen.blit(del_text, del_text.get_rect(center=delete.center))
        pygame.draw.rect(game.screen, (40, 60, 90), unlock)
        pygame.draw.rect(game.screen, WHITE, unlock, 2)
        unl_text = game.small_font.render("Unlock collection", True, WHITE)
        game.screen.blit(unl_text, unl_text.get_rect(center=unlock.center))


def draw_title_screen(game):
    """Draw the title screen: the game's name, the 6 save slots, and the
    ACHIEVEMENTS button.

    The save slots are shown directly here — there is no separate
    PLAY-then-slots step anymore.
    """
    game.screen.fill(BG_COLOR)
    title = game.main_title_font.render("MARBLE RUN", True, (255, 215, 0))
    game.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 110)))
    subtitle = game.font.render("Choose a save slot to play", True, WHITE)
    game.screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 160)))
    if game.slot_confirm_index is not None:
        save_system._draw_slot_confirm(game, game.slot_confirm_index)
    else:
        for i in range(save_system.SAVE_SLOT_COUNT):
            save_system._draw_slot_box(game, i, save_system.slot_rect(i))
        up = UPGRADES_BUTTON_RECT
        pygame.draw.rect(game.screen, (60, 60, 80), up)
        pygame.draw.rect(game.screen, WHITE, up, 2)
        up_text = game.font.render("UPGRADES", True, WHITE)
        game.screen.blit(up_text, up_text.get_rect(center=up.center))
        btn = ACHIEVEMENTS_BUTTON_RECT
        pygame.draw.rect(game.screen, (60, 60, 80), btn)
        pygame.draw.rect(game.screen, WHITE, btn, 2)
        text = game.font.render("ACHIEVEMENTS", True, WHITE)
        game.screen.blit(text, text.get_rect(center=btn.center))
        col = COLLECTION_BUTTON_RECT
        pygame.draw.rect(game.screen, (60, 60, 80), col)
        pygame.draw.rect(game.screen, WHITE, col, 2)
        col_text = game.font.render("COLLECTION", True, WHITE)
        game.screen.blit(col_text, col_text.get_rect(center=col.center))
        # Bottom-left profile switcher (button + expandable list).
        _draw_profile_button(game)
        if game.profile_menu_open:
            _draw_profile_menu(game)
    if game.profile_naming:
        _draw_profile_name_prompt(game)
def draw_achievements(game):
    """Draw the achievements tab: a grid of every achievement (name and
    description; secret descriptions hide as '???' until unlocked) with a
    RETURN TO MAIN MENU button."""
    game.screen.fill(BG_COLOR)
    heading = game.main_title_font.render("ACHIEVEMENTS", True, (255, 215, 0))
    game.screen.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 70)))
    if achievements.is_disabled():
        note = game.small_font.render(
            "Achievements disabled for this profile — the collection was fully "
            "unlocked. No new achievements can unlock.",
            True, (255, 175, 130))
        game.screen.blit(note, note.get_rect(center=(SCREEN_WIDTH // 2, 116)))
    cols = 2
    card_w, card_h = 440, 130
    gap_x, gap_y = 30, 22
    x0 = (SCREEN_WIDTH - (cols * card_w + gap_x)) // 2
    y0 = 150
    for i, ach in enumerate(achievements.all_achievements()):
        col = i % cols
        row = i // cols
        rect = pygame.Rect(x0 + col * (card_w + gap_x), y0 + row * (card_h + gap_y), card_w, card_h)
        unlocked = achievements.is_unlocked(ach.id)
        if unlocked:
            pygame.draw.rect(game.screen, (35, 40, 60), rect, border_radius=10)
            pygame.draw.rect(game.screen, (255, 215, 0), rect, 3, border_radius=10)
        else:
            pygame.draw.rect(game.screen, (25, 25, 35), rect, border_radius=10)
            pygame.draw.rect(game.screen, (120, 120, 130), rect, 2, border_radius=10)
        name_color = WHITE if unlocked else (150, 150, 160)
        name = game.font.render(ach.name, True, name_color)
        game.screen.blit(name, name.get_rect(midtop=(rect.centerx, rect.top + 16)))
        desc = game.small_font.render(achievements.display_description(ach), True,
                                      (200, 200, 200) if unlocked else (120, 120, 130))
        game.screen.blit(desc, desc.get_rect(midtop=(rect.centerx, rect.top + 52)))
        if unlocked:
            mark = game.small_font.render("UNLOCKED", True, GREEN)
            game.screen.blit(mark, mark.get_rect(midbottom=(rect.centerx, rect.bottom - 12)))
    btn = ACHIEVEMENTS_RETURN_BUTTON_RECT
    pygame.draw.rect(game.screen, (60, 60, 80), btn)
    pygame.draw.rect(game.screen, WHITE, btn, 2)
    text = game.font.render("RETURN TO MAIN MENU", True, WHITE)
    game.screen.blit(text, text.get_rect(center=btn.center))
def draw_popups(game):
    """Draw the compact bottom-of-screen popups (achievement unlocks,
    collection discoveries). The newest sits at the bottom touching the screen
    edge; older ones stack above it without overlapping, and each slides up
    from under the screen, holds, then slides back down."""
    count = len(game.popups)
    for i, popup in enumerate(game.popups):
        idx_from_bottom = count - 1 - i
        rest_y = SCREEN_HEIGHT - popup.HEIGHT - idx_from_bottom * (popup.HEIGHT + popup.GAP)
        draw_popup(game, popup, int(rest_y + popup.offset()))


def draw_popup(game, popup, y):
    """Draw one compact popup bar (title on the left, description beside it)."""
    width = 380
    height = popup.HEIGHT
    x = (SCREEN_WIDTH - width) // 2
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(game.screen, (25, 25, 45), rect, border_radius=8)
    pygame.draw.rect(game.screen, popup.color, rect, 2, border_radius=8)
    title = game.small_font.render(popup.title, True, popup.color)
    game.screen.blit(title, title.get_rect(midleft=(rect.left + 12, rect.centery)))
    desc_x = rect.left + 14 + title.get_width()
    max_desc_w = max(20, rect.right - 12 - desc_x)
    desc = popup.description
    while game.tiny_font.size(desc)[0] > max_desc_w and len(desc) > 1:
        desc = desc[:-1]
    desc_surf = game.tiny_font.render(desc, True, WHITE)
    game.screen.blit(desc_surf, desc_surf.get_rect(midleft=(desc_x, rect.centery)))


def draw_game_over(game):
    """Draw the game-over overlay with the player's stats and three options:
    return to the main menu, start a new game, or keep playing. The run-24 end
    reads "VICTORY!" / "PERFECT WIN!"; a defeat reads "GAME OVER"."""
    if not game.game_over:
        return
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 210))
    game.screen.blit(overlay, (0, 0))

    if game.game_perfect:
        title = "PERFECT WIN!"
        color = (255, 215, 0)  # gold
    elif game.game_won:
        title = "VICTORY!"
        color = GREEN
    else:
        title = "GAME OVER"
        color = (255, 80, 80)
    title_surf = game.total_font.render(title, True, color)
    game.screen.blit(title_surf, title_surf.get_rect(center=(SCREEN_WIDTH // 2, 160)))

    stats = [
        f"Runs met: {game.runs_cleared} / {min(game.run_number, TOTAL_RUNS)}",
        f"Runs failed: {game.failed_runs}",
        f"Best total: {_fmt_tenth(game.score_total)}",
        f"Cash: {game.cash}",
    ]
    if not game.game_won and game.game_over_dice_gained:
        stats.append(f"Dice earned: {game.game_over_dice_gained}")
    y = 270
    for line in stats:
        surf = game.font.render(line, True, WHITE)
        game.screen.blit(surf, surf.get_rect(center=(SCREEN_WIDTH // 2, y)))
        y += 36

    for rect, label, color in (
        (GAME_OVER_MENU_BUTTON_RECT, "MAIN MENU", (70, 70, 90)),
        (GAME_OVER_NEW_BUTTON_RECT, "NEW GAME", (40, 160, 40)),
        (GAME_OVER_CONTINUE_BUTTON_RECT, "CONTINUE", (60, 90, 170)),
    ):
        pygame.draw.rect(game.screen, color, rect)
        pygame.draw.rect(game.screen, WHITE, rect, 2)
        text = game.font.render(label, True, WHITE)
        game.screen.blit(text, text.get_rect(center=rect.center))
