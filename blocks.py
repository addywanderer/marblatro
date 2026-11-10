"""The Block: one square of the board, and what it does when a marble hits it.

A block carries its shape, its effects, its scorer and the magnitudes those were
rolled at; the physics and the scoring both read it. Its drawing lives in ui.py
(see the wiring at the bottom of main.py).
"""

import math
import random

import numpy as np
import pygame

import components
from components import (
    CARD_SCORERS,
    COMPONENT_PRICES,
    DEFAULT_DIFFICULTY,
    MAGNITUDE_ATAN_LIMIT,
    MAGNITUDE_MAX_STEPS,
    MAGNITUDE_SCALE,
    MAGNITUDE_STEP_DIVISOR,
    MAGNITUDES,
    MATCH_GROUPS,
    PIPE_GROUP_SHAPES,
    RESOURCE_PACK_FACTOR,
    RESOURCE_THRESHOLD,
    Action,
    Card,
    Component,
    Difficulty,
    Effect,
    MarbleType,
    Pack,
    Quality,
    Rarity,
    Scorer,
    Shape,
    Trial,
    block_price_for,
    card_description,
    card_price_for,
    card_scorer,
    effect_component_price,
    effect_description,
    effect_magnitude_floor,
    magnitude_precision,
    Modifiable,
    Modifier,
    magnitude_step,
    match_group_card,
    match_group_card_meta,
    match_group_label,
    match_group_trigger,
    pack_price,
    paired_shape,
    points_text,
    resource_points_for,
    scorer_component_price,
    scorer_description,
    scorer_magnitude_floor,
    shape_description,
)
from config import *




class Block(Modifiable):
    """A block composed of a Shape, an Effect, and a Scorer."""

    def __init__(self, x, y, shape=Shape.RECT, effect=Effect.NONE,
                 scorer=Scorer.NONE, scorer_amount=None, angle=0, origin=None,
                 portal_number=0, key_number=0, trigger_limit=1, trigger_paid=0,
                 effects=None, effect_amounts=None, quality=Quality.NORMAL):
        self.x = x
        self.y = y
        self.shape = shape
        # The shape a fragile block had before it shattered, so a run reset can
        # rebuild it (None until the block actually breaks).
        self._fragile_shape = None
        self.effects = list(effects) if effects is not None else [effect]
        # Each scaleable effect carries this block's OWN strength for it (a
        # piston's launch speed, a black hole's pull, ...), rolled when the
        # block was built (see roll_effect_amounts); an effect missing from the
        # map uses the average. Effect.NONE and the on/off effects have none.
        self.effect_amounts = dict(effect_amounts or {})
        self.portal_number = portal_number  # portal pairs share a number
        self.key_number = key_number  # key/lock pairs share a number
        # A Lock block is a solid door until a marble passes through the Key
        # block that shares its key number; every lock closes again at the
        # start of each run (see reset_run). No other shape is ever locked.
        self.locked = shape == Shape.LOCK
        self.scorer = scorer
        self.scorer_amount = scorer_amount if scorer_amount is not None else Scorer.DEFAULT_AMOUNT.get(scorer, 0)
        # The tier the player's item was at when this block was built (see
        # components.Quality): a golden block is drawn golden.
        self.quality = quality
        origin_x, origin_y = origin if origin is not None else (MARBLE_BOX_COORDS[0], MARBLE_BOX_COORDS[1])
        self.rect = pygame.Rect(
            x * GRID_SIZE + origin_x,
            y * GRID_SIZE + origin_y,
            GRID_SIZE,
            GRID_SIZE,
        )
        self._angle = 0
        # Continuous rotation offset (degrees) for rotating-effect blocks; the
        # block's geometry includes it, so drawing and physics stay in sync.
        self.spin = 0.0
        self.angle = angle % 360
        # A scoring block can trigger a limited number of times per run; the
        # limit can be raised by paying cash (see _upgrade_trigger_limit), and
        # trigger_paid is refunded when the block is sold.
        self.trigger_limit = trigger_limit
        self.trigger_paid = trigger_paid
        self.triggers_left = trigger_limit
        # A portal pair can be travelled through at most PORTAL_MAX_ACTIVATIONS
        # times per run; both portals share one count, and reset_run tops it
        # back up at the start of each run. Non-portal blocks never use it.
        self.portal_uses_left = (
            PORTAL_MAX_ACTIVATIONS if Effect.PORTAL in self.effects else 0)
        # A cable car (Effect.GONDOLA) slides along a lane of its own for the
        # length of a run. Its travel is kept as a FLOAT of pixels from its own
        # cell — a car rolling at 24 px/s covers 0.4 of a pixel a frame, which
        # a whole-pixel rect cannot hold — and its direction is learned from its
        # arrow the first time it moves (see Game._slide_gondola, which explains
        # why the travel cannot live in the rect, and Game._reset_gondola).
        self.gondola_travel = 0.0
        self.gondola_dir = None
        # The inventory item this block was placed FROM, if any (see
        # Game._place_block_at): the item keeps the spot it was bought into, and
        # the block remembers it so erasing the block puts that same item back
        # in reach instead of refunding a second copy.
        self.source_item = None

# =============================================================================

    @property
    def effect(self):
        """The block's primary (first) effect."""
        return self.effects[0] if self.effects else Effect.NONE

    def has_effect(self, effect):
        """True when the block has the given effect (one of possibly many)."""
        return effect in self.effects

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = int(value) % 360
        self._refresh_geometry()

    def _refresh_geometry(self):
        # The effective rotation is the base angle plus any continuous spin, so
        # rotating-effect blocks can animate their geometry frame to frame.
        self.effective_angle = (self._angle + getattr(self, "spin", 0.0)) % 360
        self.get_slope_points = self._get_slope_points()
        self.get_slope_border_points = self._get_slope_border_points()
        self.get_slope_line_points = self._get_slope_line_points()
        self.get_slope_surface_normal = self._get_slope_surface_normal()
        self.get_flat_line_points = self._get_flat_line_points()
        self.get_flat_surface_normal = self._get_flat_surface_normal()
        self.get_slope_direction = self._get_slope_direction()
        self.get_acceleration = self._get_acceleration()
        self.get_gravity_direction = self._get_angle_vector()
        self.get_curved_center = self._get_curved_center()
        self.get_curved_arc = self._get_curved_arc()
        self.get_curved_fill = self._get_curved_fill()
        self.get_curved_legs = self._get_curved_legs()
        self.get_drain_walls = self._get_drain_walls()
        self.get_pipe_bend_center = self._get_pipe_bend_center()
        self.get_pipe_bend_inner_arc = self._get_pipe_bend_arc(GRID_SIZE // 2 - MARBLE_RADIUS)
        self.get_pipe_bend_outer_arc = self._get_pipe_bend_arc(GRID_SIZE // 2 + MARBLE_RADIUS)
        self.get_pipe_bend_legs = self._get_pipe_bend_legs()
        # The convex slope shares the curved slope's center and arc (a quarter
        # circle), but its solid is the quarter DISK on the arc, not the recess.
        self.get_convex_center = self._get_curved_center()
        self.get_convex_arc = self._get_curved_arc()
        self.get_convex_fill = self._get_convex_fill()
        self.get_convex_legs = self._get_convex_legs()
        self.get_half_pipe_points = self._get_half_pipe_points()
        self.get_spike_points = self._get_spike_points()
        self.get_platform_rect = self._get_platform_rect()
        self.get_platform_points = self._get_platform_points()
        self.get_corner_rects = self._get_corner_rects()
        self.get_corner_points = self._get_corner_points()
        self.get_sawtooth_teeth = self._get_sawtooth_teeth()
        # COMMENTED OUT with the shape itself: the cradle's pieces/silhouette.
        # self.get_cradle_pieces = self._get_cradle_pieces()
        self.get_corner_silhouette = self._get_corner_silhouette()
        # self.get_cradle_silhouette = self._get_cradle_silhouette()
        self.get_bump_points = self._get_bump_points()
        self.get_belt_direction = self._get_belt_direction()

    def effect_magnitude(self, effect):
        """This block's own strength for an effect (the average when unrolled).

        The magnitude was rolled when the block was built; a block that has no
        roll for the effect (an old save, a hand-built test block, an on/off
        effect) reads the average, which is exactly the fixed value the game
        used before magnitudes existed. A stored 0 counts as unrolled too: no
        scaleable effect has a zero strength, so a 0 must never shadow the
        average.
        """
        return self.effect_amounts.get(effect) or Effect.MAGNITUDE.get(effect, 0)

    @property
    def amount(self):
        """The block's single AMOUNT: its scorer's magnitude.

        Every item carries one (see Game._item_magnitudes); for a block that is
        the number its scorer pays with. Each effect keeps its own strength
        alongside it (see effect_amounts), because a block can carry several
        magnitudes at once -- this is the scorer's.
        """
        return self.scorer_amount

    @amount.setter
    def amount(self, value):
        """Setting it sets the scorer's magnitude, so the two never disagree."""
        self.scorer_amount = value

    @property
    def is_token(self):
        """True when this block is a kept copy that fires every run.

        A token IS a block carrying the ``token`` modifier (user request:
        "tokens are just blocks with the 'token' modifier"), so the flag the
        drawing and firing paths read is a view over its stacks rather than a
        field of its own. A permanent (v2) token carries
        ``Modifier.PERMANENT``, which is non-zero, so it reads as a token too.
        """
        return Modifier.stacks(self, Modifier.TOKEN) != 0

    @is_token.setter
    def is_token(self, value):
        """Marking a block as a token gives it one run of coverage."""
        if value and not self.is_token:
            Modifier.set_stacks(self, Modifier.TOKEN, 1)
        elif not value:
            Modifier.set_stacks(self, Modifier.TOKEN, 0)

    def advance_spin(self, dt):
        """Advance the continuous rotation of a rotating-effect block (per frame)."""
        if not self.has_effect(Effect.ROTATE):
            return
        self.spin = (self.spin + self.effect_magnitude(Effect.ROTATE) * dt) % 360.0
        self._refresh_geometry()

    def _rotate_point(self, point, angle):
        """Rotate a point around the block center by the given angle (plus any spin)."""
        angle += getattr(self, "spin", 0.0)
        angle_rad = math.radians(angle)
        cx, cy = self.rect.centerx, self.rect.centery
        dx = point[0] - cx
        dy = point[1] - cy
        return (
            cx + dx * math.cos(angle_rad) - dy * math.sin(angle_rad),
            cy + dx * math.sin(angle_rad) + dy * math.cos(angle_rad),
        )

    def _rotate_vector(self, vector, angle):
        """Rotate a 2D vector by the given angle (plus any spin)."""
        angle += getattr(self, "spin", 0.0)
        angle_rad = math.radians(angle)
        x, y = vector
        return np.array([
            x * math.cos(angle_rad) - y * math.sin(angle_rad),
            x * math.sin(angle_rad) + y * math.cos(angle_rad),
        ])

    def _get_angle_vector(self):
        """Return the direction vector for this block's angle."""
        base_vector = np.array([0, -1])
        return self._rotate_vector(base_vector, self.angle)

    def _get_slope_points(self):
        """Get the points that define the slope triangle."""
        x, y = self.rect.x, self.rect.y
        w, h = self.rect.width, self.rect.height

        base_points = [(x, y + h), (x + w, y), (x + w, y + h)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_slope_border_points(self):
        """Get the points that define the slope triangle."""
        x, y = self.rect.x, self.rect.y
        w, h = self.rect.width, self.rect.height

        base_points = [(x + 6, y + h - 3), (x + w - 3, y + 6), (x + w - 3, y + h - 3)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_slope_line_points(self):
        """Get the endpoints of the single sloped line segment."""
        x, y = self.rect.x, self.rect.y
        w, h = self.rect.width, self.rect.height

        base_points = [(x, y + h), (x + w, y)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_flat_line_points(self):
        """The endpoints of the flat line along the bottom of the cell.

        The line sits a few pixels above the cell's bottom edge so its thick
        stroke stays inside the unit instead of poking out below it.
        """
        x, y = self.rect.x, self.rect.y
        w = self.rect.width
        h = self.rect.height
        raise_by = 3
        base_points = [(x, y + h - raise_by), (x + w, y + h - raise_by)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_flat_surface_normal(self):
        """The normal pointing up out of the flat line's surface."""
        return self._rotate_vector(np.array([0.0, -1.0]), self.angle)

    def _get_half_pipe_points(self):
        """Sampled points along the half-pipe's bottom semicircle, rotated.

        The arc is centered on the unit's center (its diameter would run along
        the middle horizontal line) with radius half the cell width, so it
        sweeps the bottom half of the cell from the right midpoint through the
        bottom center to the left midpoint. Only the curved edge exists —
        there is no edge along the diameter (the top is open).
        """
        cx, cy = self.rect.centerx, self.rect.centery
        R = self.rect.width / 2.0
        return [self._rotate_point((cx + R * math.cos(math.radians(a)),
                                    cy + R * math.sin(math.radians(a))), self.angle)
                for a in range(0, 181, 5)]

    def _get_acceleration(self):
        """Get acceleration vector for accelerator blocks."""
        return self._get_angle_vector() * self.effect_magnitude(Effect.ACCELERATOR)

    def _get_spike_points(self):
        """The upward-triangle spike's corners (base on the bottom, apex on top).

        The solid fills the bottom triangle: the cell's full bottom edge is the
        base and the apex sits at the top-center, so a marble landing on it is
        split to the left or right. Rotated with the block's angle (and any
        ROTATE spin), exactly like the slope triangle.
        """
        x, y = self.rect.left, self.rect.top
        w, h = self.rect.width, self.rect.height
        base_points = [(x, y + h), (x + w, y + h), (x + w / 2.0, y)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_platform_rect(self):
        """The platform's solid bar: the bottom half of the cell.

        A platform is a thick shelf along the bottom of the unit (half the cell
        tall, full width) that the player builds stairs, ledges, and floors
        from. Collision rotates it with the block; the points helper below
        returns its rotated corners for drawing.
        """
        return pygame.Rect(self.rect.left, self.rect.top + self.rect.height // 2,
                           self.rect.width, self.rect.height // 2)

    def _get_platform_points(self):
        """The platform bar's four corners, rotated with the block (for drawing)."""
        r = self._get_platform_rect()
        base_points = [(r.left, r.top), (r.right, r.top),
                       (r.right, r.bottom), (r.left, r.bottom)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_corner_rects(self):
        """The corner's two legs: a left column plus a bottom row (an L bracket).

        Each leg is half a cell thick; together they form the bottom-left corner
        of the unit, giving the marble a wall to lean on and a floor to settle
        onto. Collision tests each leg as a rectangle; the points helper below
        returns the rotated legs for drawing.
        """
        leg = self.rect.width // 2
        column = pygame.Rect(self.rect.left, self.rect.top, leg, self.rect.height)
        floor = pygame.Rect(self.rect.left, self.rect.bottom - leg,
                            self.rect.width, leg)
        return column, floor

    def _get_corner_points(self):
        """The corner legs' corners, rotated with the block (for drawing)."""
        points = []
        for rect in self._get_corner_rects():
            base_points = [(rect.left, rect.top), (rect.right, rect.top),
                           (rect.right, rect.bottom), (rect.left, rect.bottom)]
            points.append([self._rotate_point(point, self.angle)
                           for point in base_points])
        return points

    def _get_sawtooth_teeth(self):
        """The sawtooth's row of upward triangular teeth along the bottom edge.

        Each tooth is a small triangle with its base on the cell's bottom edge
        and its apex centered above the base; the teeth sit side by side so the
        marble tumbles over them. Rotated with the block's angle (and ROTATE
        spin).
        """
        x = self.rect.left
        bottom = self.rect.bottom
        step = self.rect.width / SAWTOOTH_TEETH
        teeth = []
        for i in range(SAWTOOTH_TEETH):
            x0 = x + i * step
            x1 = x0 + step
            apex = (x0 + step / 2.0, bottom - SAWTOOTH_HEIGHT)
            base_points = [(x0, bottom), (x1, bottom), apex]
            teeth.append([self._rotate_point(point, self.angle)
                          for point in base_points])
        return teeth

    # -------------------------------------------------------------------
    # COMMENTED OUT with the shape itself (user request: "comment out the
    # cradle shape"). Both builders were only ever reached through
    # Block._refresh_geometry for a CRADLE block.
    #
    # def _get_cradle_pieces(self):
    #     """The cradle's solid: two side wedges plus a thick floor slab.
    #
    #     A wide valley is cut from the cell's top edge down to a flat floor
    #     (wider than a marble) so a marble that rolls or falls in is caught and
    #     rests on the floor at the center. The slab below the floor closes the
    #     cell, so a marble can never slip out the bottom. The solid is therefore
    #     three convex pieces (a left wedge, a right wedge, and the slab), each
    #     rotated with the block (and ROTATE spin) so the hitbox matches the drawn
    #     shape.
    #     """
    #     left, top = self.rect.left, self.rect.top
    #     right, bottom = self.rect.right, self.rect.bottom
    #     center_x = self.rect.centerx
    #     floor_y = top + CRADLE_FLOOR_DEPTH
    #     half = CRADLE_FLOOR_HALF
    #     base_pieces = [
    #         [(left, top), (center_x - half, floor_y), (left, floor_y)],
    #         [(right, top), (center_x + half, floor_y), (right, floor_y)],
    #         [(left, floor_y), (right, floor_y), (right, bottom), (left, bottom)],
    #     ]
    #     return [[self._rotate_point(point, self.angle) for point in piece]
    #             for piece in base_pieces]

    def _get_corner_silhouette(self):
        """The corner's whole outline as ONE polygon (no seam between its legs).

        The corner's solid is a left column plus a bottom row that OVERLAP, so
        outlining the two legs separately draws a line inside the shape where
        they meet. This L-shaped outline follows only the outside of the union,
        which is what the shape's component/ghost image should show.
        """
        leg = self.rect.width // 2
        left, top = self.rect.left, self.rect.top
        right, bottom = self.rect.right, self.rect.bottom
        base_points = [(left, top), (left + leg, top), (left + leg, bottom - leg),
                       (right, bottom - leg), (right, bottom), (left, bottom)]
        return [self._rotate_point(point, self.angle) for point in base_points]

    # COMMENTED OUT with the shape itself: the cradle's single outline polygon
    # (a left wedge, the flat floor, a right wedge, then the outside down).
    #
    # def _get_cradle_silhouette(self):
    #     """The cradle's whole outline as ONE polygon (no seams between pieces).
    #
    #     The cradle's solid is two side wedges sitting on a floor slab, so
    #     outlining the three pieces separately draws a line inside the shape
    #     where each wedge meets the slab. This outline follows only the outside
    #     of the union (up the left wedge, across the flat floor, up the right
    #     wedge, then down the outside), which is what the shape's
    #     component/ghost image should show.
    #     """
    #     left, top = self.rect.left, self.rect.top
    #     right, bottom = self.rect.right, self.rect.bottom
    #     center_x = self.rect.centerx
    #     floor_y = top + CRADLE_FLOOR_DEPTH
    #     half = CRADLE_FLOOR_HALF
    #     base_points = [(left, top), (center_x - half, floor_y),
    #                    (center_x + half, floor_y), (right, top),
    #                    (right, bottom), (left, bottom)]
    #     return [self._rotate_point(point, self.angle) for point in base_points]

    def _get_bump_points(self):
        """The bump's solid dome: a half-disc sitting on the cell's bottom edge.

        The dome is the top half of a circle whose diameter runs along the
        bottom edge of the unit (radius = half the cell width), so the marble
        has to roll up and over it — a speed bump. The sampled arc closes
        straight across the diameter, making a CONVEX polygon, so collision
        reuses _convex_polygon_collision. Rotated with the block's angle (and
        any ROTATE spin) like the other shapes.
        """
        cx, cy = self.rect.centerx, self.rect.bottom
        radius = self.rect.width / 2.0
        return [self._rotate_point((cx + radius * math.cos(math.radians(a)),
                                    cy + radius * math.sin(math.radians(a))), self.angle)
                for a in range(180, 361, 5)]

    def _get_belt_direction(self):
        """The unit direction a conveyor pushes marbles along.

        A conveyor drags marbles sideways along its surface, so its belt runs
        at a right angle to the block's facing arrow: the arrow's direction
        turned 90 degrees. The block's base angle (the A key) therefore aims
        the belt, and a ROTATE spin sweeps the push around with the shape.
        """
        return self._rotate_vector(np.array([1.0, 0.0]), self.angle)

    def _get_curved_center(self):
        """The curved-slope arc center (cell top-left corner) rotated by the angle."""
        return np.array(self._rotate_point((self.rect.left, self.rect.top), self.angle), dtype=float)

    def _get_curved_arc(self):
        """Sampled points along the curved surface, rotated by the angle."""
        R = float(self.rect.width)
        left, top = self.rect.left, self.rect.top
        return [self._rotate_point((left + R * math.cos(math.radians(a)), top + R * math.sin(math.radians(a))), self.angle)
                for a in range(0, 91, 5)]

    def _get_curved_fill(self):
        """Polygon filling the curved-slope region: the arc plus the bottom-right corner."""
        pts = self._get_curved_arc()
        pts.append(self._rotate_point((self.rect.right, self.rect.bottom), self.angle))
        return pts

    def _get_curved_legs(self):
        """The two straight legs (right and bottom) as (p1, p2, outward_normal), rotated."""
        left, top, w, h = self.rect.left, self.rect.top, self.rect.width, self.rect.height
        return [
            (self._rotate_point((left + w, top), self.angle),
             self._rotate_point((left + w, top + h), self.angle),
             self._rotate_vector((1.0, 0.0), self.angle)),
            (self._rotate_point((left + w, top + h), self.angle),
             self._rotate_point((left, top + h), self.angle),
             self._rotate_vector((0.0, 1.0), self.angle)),
        ]

    def _get_convex_fill(self):
        """Polygon filling the convex-slope quarter disk: the arc plus the corner."""
        pts = list(self.get_convex_arc)
        pts.append(self._rotate_point((self.rect.left, self.rect.top), self.angle))
        return pts

    def _get_convex_legs(self):
        """The two straight edges (top and left) as (p1, p2, outward_normal), rotated."""
        left, top, w, h = self.rect.left, self.rect.top, self.rect.width, self.rect.height
        return [
            (self._rotate_point((left, top), self.angle),
             self._rotate_point((left + w, top), self.angle),
             self._rotate_vector((0.0, -1.0), self.angle)),
            (self._rotate_point((left, top), self.angle),
             self._rotate_point((left, top + h), self.angle),
             self._rotate_vector((-1.0, 0.0), self.angle)),
        ]

    def _get_slope_surface_normal(self):
        """Get the normal vector pointing OUT from the slope surface."""
        base_vector = np.array([-1, -1]) / SQRT_2
        return self._rotate_vector(base_vector, self.angle)
    
    def _get_slope_direction(self):
        """Get the direction vector along the slope surface (downhill)."""
        base_vector = np.array([-1, 1]) / SQRT_2
        return self._rotate_vector(base_vector, self.angle)

    def _get_pipe_rects(self):
        """The two vertical pillars of a pipe block, axis-aligned in the cell.

        A pipe is the cell minus a vertical strip down the middle that is one
        marble diameter wide, splitting the square into two equal pillars. The
        marble can fall through the gap between them.
        """
        gap = 2 * MARBLE_RADIUS
        w = (self.rect.width - gap) // 2
        left = pygame.Rect(self.rect.left, self.rect.top, w, self.rect.height)
        right = pygame.Rect(self.rect.right - w, self.rect.top, w, self.rect.height)
        return left, right

    def _get_pipe_pillar_points(self):
        """Corner points of each pipe pillar, rotated with the block (and spin).

        The pipe honors its base angle (set by the A key) as well as the ROTATE
        effect's continuous spin, so rotating a pipe turns its vertical gap
        into a horizontal one.
        """
        points = []
        for pillar in self._get_pipe_rects():
            pts = [(pillar.left, pillar.top), (pillar.right, pillar.top),
                   (pillar.right, pillar.bottom), (pillar.left, pillar.bottom)]
            if self.angle % 360 != 0 or self.has_effect(Effect.ROTATE):
                pts = [self._rotate_point(p, self.angle) for p in pts]
            points.append(pts)
        return points

    def drain_cavity_half_width(self, offset):
        """Half-width of a drain's funnel cavity at a local y offset.

        ``offset`` is measured along the funnel's own axis in the block's frame:
        -height/2 at the cell's open top edge (where the funnel is the full cell
        wide) to +height/2 at its bottom edge (where the walls leave a hole
        exactly the marble's diameter wide). The walls inset by
        ``wall_w * (2u - u * u)``, which is what leaves half the cell minus that
        inset as the cavity, so this is the gap a marble has to be inside to
        count as passing through the drain (see physics._inside_drain_cavity).
        The drawn walls and the tested cavity both come from here, so the shape
        a marble flows through and the shape it collides with cannot drift
        apart.
        """
        wall_w = self.rect.width / 2 - MARBLE_RADIUS
        u = (offset + self.rect.height / 2) / self.rect.height
        u = min(1.0, max(0.0, u))  # beyond an edge: that edge's own width
        return self.rect.width / 2 - wall_w * (2 * u - u * u)

    def _get_drain_walls(self):
        """The two funnel walls of a drain block, as convex polygons.

        A drain is a square cell with a funnel-shaped cavity: the top opens the
        full cell width and the two curved (concave) walls taper inward down to
        a marble-diameter opening at the bottom. The solid is the cell minus
        that cavity — two curved side walls, each a convex wedge. The wall
        points are rotated with the block (and any ROTATE spin) so the hitbox
        matches the drawn shape.
        """
        left, top = self.rect.left, self.rect.top
        right, bottom = self.rect.right, self.rect.bottom
        samples = 8
        left_curve = []
        right_curve = []
        for i in range(samples + 1):
            y = top + i / samples * self.rect.height
            # The cavity's own half-width, so the drawn walls are exactly the
            # gap a marble is tested against (see drain_cavity_half_width).
            half = self.drain_cavity_half_width(y - self.rect.centery)
            left_curve.append((self.rect.centerx - half, y))
            right_curve.append((self.rect.centerx + half, y))
        # Each wall: down the cell's outer edge, across the bottom face, then up
        # the curved inner surface back to the top corner (a convex wedge). The
        # bottom face spans the cavity's own width there — the marble-diameter
        # opening the funnel tapers to.
        opening_half = self.drain_cavity_half_width(self.rect.height / 2)
        left_wall = ([(left, top), (left, bottom),
                      (self.rect.centerx - opening_half, bottom)]
                     + left_curve[:0:-1])
        right_wall = ([(right, top), (right, bottom),
                       (self.rect.centerx + opening_half, bottom)]
                      + right_curve[:0:-1])
        # The drain honors its base angle (the A key) and any ROTATE spin, so a
        # rotated drain's hitbox matches its drawn shape.
        if self.angle % 360 != 0 or self.has_effect(Effect.ROTATE):
            left_wall = [self._rotate_point(p, self.angle) for p in left_wall]
            right_wall = [self._rotate_point(p, self.angle) for p in right_wall]
        return [left_wall, right_wall]

    def _get_pipe_bend_center(self):
        """The pipe-bend annulus center (the cell's top-right corner), rotated.

        A pipe bend is a marble-wide (16px) channel that enters the cell's top
        edge and exits its right edge (adjacent sides), turning a smooth 90
        degrees along a quarter-annulus centered at the cell's top-right corner
        (inner radius 12, outer radius 28 = inner + marble diameter). The solid
        is the cell minus that channel: the corner core (inside the inner
        radius) plus the rest of the cell outside the outer radius. The center
        is rotated with the block (and any ROTATE spin) so the hitbox matches
        the drawn shape.
        """
        return np.array(self._rotate_point((self.rect.right, self.rect.top), self.angle),
                        dtype=float)

    def _get_pipe_bend_arc(self, radius):
        """Sampled points on a quarter arc of the given radius from the corner.

        The arc runs from the cell's right edge (90 degrees) around to its top
        edge (180 degrees), i.e. the channel wall of a pipe bend. The sampled
        points are rotated with the block (and any ROTATE spin).
        """
        right, top = self.rect.right, self.rect.top
        return [self._rotate_point(
            (right + radius * math.cos(math.radians(a)),
             top + radius * math.sin(math.radians(a))), self.angle)
            for a in range(90, 181, 5)]

    def _get_pipe_bend_legs(self):
        """The straight boundary segments of a pipe-bend's solid.

        Each is (p1, p2, outward_normal), rotated with the block. The solid
        touches all four cell edges, but the channel's entrance (the top edge)
        and exit (the right edge) are left open: the top edge is split around
        the entrance and the right edge around the exit, and the corner core's
        own two straight edges cover the rest.
        """
        left, top = self.rect.left, self.rect.top
        right, bottom = self.rect.right, self.rect.bottom
        inner = self.rect.width // 2 - MARBLE_RADIUS   # 12
        outer = self.rect.width // 2 + MARBLE_RADIUS   # 28
        segments = [
            # The surrounding solid's cell edges (channel entrance/exit open).
            ((left, top), (right - outer, top), (0.0, -1.0)),          # top strip
            ((right, top + outer), (right, bottom), (1.0, 0.0)),       # right strip
            ((left, bottom), (right, bottom), (0.0, 1.0)),             # bottom
            ((left, top), (left, bottom), (-1.0, 0.0)),                # left
            # The corner core's straight edges (the rest of the top/right edges).
            ((right - inner, top), (right, top), (0.0, -1.0)),         # core top
            ((right, top), (right, top + inner), (1.0, 0.0)),          # core right
        ]
        return [
            (self._rotate_point(p1, self.angle), self._rotate_point(p2, self.angle),
             self._rotate_vector(n, self.angle))
            for p1, p2, n in segments
        ]

# =============================================================================

    def is_point_inside_slope(self, point):
        """Check if a point is inside the slope triangle"""
        points = self.get_slope_points
        if len(points) < 3:
            return False
        
        p = np.array(point)
        a = np.array(points[0])
        b = np.array(points[1])
        c = np.array(points[2])
        
        v0 = c - a
        v1 = b - a
        v2 = p - a
        
        dot00 = np.dot(v0, v0)
        dot01 = np.dot(v0, v1)
        dot02 = np.dot(v0, v2)
        dot11 = np.dot(v1, v1)
        dot12 = np.dot(v1, v2)
        
        denom = dot00 * dot11 - dot01 * dot01
        if denom == 0:
            return False
        
        inv_denom = 1.0 / denom
        u = (dot11 * dot02 - dot01 * dot12) * inv_denom
        v = (dot00 * dot12 - dot01 * dot02) * inv_denom
        
        return (u >= 0) and (v >= 0) and (u + v <= 1)
