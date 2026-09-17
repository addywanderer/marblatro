import math
import random

import numpy as np
import pygame

import crt
from components import (
    CARD_SCORERS,
    COMPONENT_PRICES,
    CONDITION_ORDER,
    DEFAULT_DIFFICULTY,
    MAGNITUDE_MAX_STEPS,
    MAGNITUDE_STEP_DIVISOR,
    MAGNITUDE_WEIGHTS,
    RESOURCE_THRESHOLD,
    Action,
    Card,
    Component,
    Condition,
    Difficulty,
    Effect,
    FinalBoss,
    MarbleType,
    Scorer,
    Shape,
    Trial,
    block_price_for,
    card_description,
    card_price_for,
    card_scorer,
    condition_description,
    condition_phase,
    condition_scorer_card,
    effect_component_price,
    effect_description,
    effect_magnitude_floor,
    generic_card_meta,
    magnitude_step,
    paired_shape,
    points_text,
    resource_points_for,
    scorer_component_price,
    scorer_description,
    scorer_magnitude_floor,
    shape_description,
    splittable_card_condition_scorer,
)

pygame.init()

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
RED = (255, 50, 50)
BLUE = (50, 50, 255)
GREEN = (50, 255, 50)
YELLOW = (255, 255, 50)
ORANGE = (255, 165, 0)

SQRT_2 = np.sqrt(2)

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
BG_COLOR = (255, 50, 50)
MARBLE_BOX_COORDS = (180, 150, 400, 600)  # board: 180..580 x, 150..750 y
MARBLE_BOX_COLOR = (255, 100, 100)
FONT_SCALE = 0.7
BORD_WIDTH = 6
REQUIRED_SCORES = [1]
# Total-score exponent: total = (chips * mult) ** exponent, where the exponent
# is an EQUAL-weight linear combination of the run's time, distance, and
# uniqueness. Each factor is normalized to 0..1 and more of it is always
# better (no par time).
TIME_IDEAL = 5.0  # ideal time for max time contribution
TIME_SCALE = 3.0  # leniency on how close time can be for more exponent effect
DISTANCE_SCALE = 10000.0  # px traveled that count as a 1/2 distance contribution
UNIQUE_SCALE = 18  # unique shape/effect/scorer types for a 1/2 uniqueness contribution
                  # should be 1/2 the total number of components (not including start and finish scorer,
                  #  square shape, or none effect)
CASH_SCALE = 25
QUICK_SCALE = 0.05  # chips a Quick scorer grants per px/s of the marble's speed
RECENT_SPEED_DECAY = 0.9
# Growing/Shrinking blocks multiply the marble's radius by these factors on
# each fresh touch. Shrinking clamps at MIN_MARBLE_RADIUS so a marble never
# shrinks to nothing.
GROW_RADIUS_FACTOR = 2.0
SHRINK_RADIUS_FACTOR = 0.5
MIN_MARBLE_RADIUS = 1.0
# Marble trails: small marble-colored dots shrink and fade behind a moving
# marble. TRAIL_SPACING is the distance (px) between dots, TRAIL_LIFE how long
# each dot lasts, and TRAIL_RADIUS_SCALE the dot's starting size as a fraction
# of the marble's radius.
TRAIL_SPACING = 4.0
TRAIL_LIFE = 0.6
TRAIL_RADIUS_SCALE = 0.5
# Trials: exactly one run-wide modifier per run. Hands tied set the
# trigger limit to 0 for a random 1/4 of the marble-box blocks.
TRIAL_MAX_TRIGGERS = 0
GRID_SIZE = 40  # Size of each grid cell in pixels
SHOP_COORDS = (620, 510, 400, 240)  # x, y, width, height of the shop
TRIAL_BOX_COORDS = (620, 50, 200, 80)  # trial box above the cards (top-left stack)
SHOP_GRID_COLS = SHOP_COORDS[2] // GRID_SIZE
SHOP_GRID_ROWS = SHOP_COORDS[3] // GRID_SIZE
SHOP_MESSAGE_DURATION = 90  # Frames a shop purchase message stays visible
TOOLBOX_COORDS = (620, 190, 400, 280)  # x, y, width, height of the toolbox (the inventory)
ASSEMBLER_COORDS = (620, 670, 320, 80)  # x, y, width, height of the assembler/disassembler (overlay on the shop's bottom-left)
MAX_CARDS = 5  # Maximum owned cards the card area can hold at once
# Owned-card row above the inventory's top-LEFT corner.
CARD_AREA_COORDS = (620, 142, MAX_CARDS * GRID_SIZE, GRID_SIZE)
CARD_COLOR = (210, 180, 60)  # gold card look for cards in the shop and card area
MAX_ACTIONS = 2  # Maximum owned actions the action area can hold at once
# How many of the action catalogue the shop offers at once (two distinct
# actions, drawn at random each refresh).
SHOP_ACTION_SLOTS = 2
# Spirit tokens (see Action.SPIRIT): tokens kept out of a destroyed block,
# shown as poker chips in a column to the right of the inventory.
MAX_TOKENS = 5
TOKEN_COORDS = (TOOLBOX_COORDS[0] + TOOLBOX_COORDS[2] + 10, TOOLBOX_COORDS[1],
                GRID_SIZE, GRID_SIZE * MAX_TOKENS)
# Owned-action row above the inventory's top-RIGHT corner (actions modify
# blocks/cards).
ACTION_AREA_COORDS = (940, 142, MAX_ACTIONS * GRID_SIZE, GRID_SIZE)
# Service fees and upgrade costs are all 20% lower than the original
# (rounded down): 25->20, 70->56, 50->40, 40->32. Upgrading an action from v1
# to v2 costs ACTION_UPGRADE_COST (was 300, then 240, now a flat 200).
ACTION_UPGRADE_COST = 200  # Cash to upgrade an action from v1 to v2
# A shop (or granted) action is usually v1; this often it arrives as v2
# already, which is a straight saving of ACTION_UPGRADE_COST (see
# random_action_version).
ACTION_V2_CHANCE = 0.01
SHOP_REFRESH_COST = 20  # Cash cost to reroll the shop
TRIAL_CHANGE_COST = 50  # Cash to swap this run's trial for a different random one
TRIAL_DISABLE_COST = 100  # Cash to play this run with no trial at all
DISASSEMBLE_COST = 56  # Cash cost to break a block back into its parts
CARD_DISASSEMBLE_COST = 56  # Cash cost to split a splittable card into its halves
DUPLICATE_PRICE_INCREMENT = 0.5  # per-purchase price factor: each copy of a component
                                 # bought (directly or inside a block) raises its price
                                 # by this fraction of the base, with diminishing returns
# Raising a block's trigger limit costs this much more than the shop price of
# the block's SCORER component (see _trigger_upgrade_cost). Each upgrade also
# counts as a purchase of that scorer, so both its shop price and the next
# upgrade rise by the same duplicate-price step a real purchase would cause.
TRIGGER_UPGRADE_MARKUP = 1.1
# A portal pair can be travelled through at most this many times per run (a
# marble teleporting through either portal counts once); once the pair is used
# up it stops teleporting until the run resets it. This caps the free movement
# a portal pair can provide each run.
PORTAL_MAX_ACTIVATIONS = 100
ROUND_COUNT = 8  # Rounds in a full game
RUNS_PER_ROUND = 3  # Marble runs per round
TOTAL_RUNS = ROUND_COUNT * RUNS_PER_ROUND  # 24 runs per game
REQUIRED_RUNS_TO_WIN = 22  # Meet the score target in at least 22 of the 24 runs to win (failing 3 runs means defeat)
# Run/round dots: a transposed 8x3 grid (8 rounds across, 3 runs down) that
# sits above the actions display, with the final (boss) run at the bottom
# right. RUN_DOT_GRID is the center of round 1 / run 1 (the top-left dot).
RUN_DOT_GRID = (904, 75)
RUN_DOT_DX = 16  # Horizontal spacing between rounds (columns)
RUN_DOT_DY = 15  # Vertical spacing between a round's runs (rows)
RUN_DOT_RADIUS = 6
# Marble-box fire: when the player's score passes the required score during
# a run, flames rise along the top edge of the marble box (like Balatro). The
# fire is larger the more the score beats the target and gradually dies down
# once the run is over.
FIRE_MAX_INTENSITY = 3.0  # cap on the fire's strength (score-excess ratio)
FIRE_RISE_SPEED = 2.0  # fire strength gained per second while passing the run
FIRE_DECAY_SPEED = 1.5  # fire strength lost per second after the run ends
# Fixed UI button/overlay rects. These used to be Game methods returning a
# constant rect; they are now module-level constants (the parameterized
# marble_card_rect / upgrade_card_rect methods stay, since they depend on an
# index).
SHOP_REFRESH_BUTTON_RECT = pygame.Rect(SHOP_COORDS[0] + SHOP_COORDS[2] - 112,
                                       SHOP_COORDS[1] + SHOP_COORDS[3] - 30, 104, 24)
# The trial display above the cards. Its LEFT half buys a different random
# trial and its RIGHT half buys no trial for the run (see
# _click_trial_display); hovering it shows both prices.
TRIAL_BOX_RECT = pygame.Rect(TRIAL_BOX_COORDS)
SELL_OVERLAY_RECT = pygame.Rect(TOOLBOX_COORDS[0] + TOOLBOX_COORDS[2] - GRID_SIZE,
                                TOOLBOX_COORDS[1] + TOOLBOX_COORDS[3] - GRID_SIZE,
                                GRID_SIZE, GRID_SIZE)
UPGRADE_OVERLAY_RECT = pygame.Rect(TOOLBOX_COORDS[0] + TOOLBOX_COORDS[2] - 2 * GRID_SIZE,
                                   TOOLBOX_COORDS[1] + TOOLBOX_COORDS[3] - GRID_SIZE,
                                   GRID_SIZE, GRID_SIZE)
GAME_OVER_MENU_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 320, 560, 200, 48)
GAME_OVER_NEW_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 100, 560, 200, 48)
GAME_OVER_CONTINUE_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 + 120, 560, 200, 48)
ACHIEVEMENTS_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 100, 580, 200, 48)
UPGRADES_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 320, 580, 200, 48)
COLLECTION_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 + 120, 580, 200, 48)
# The bottom-left PROFILE button on the title screen: opens the expandable
# profile-switch list (see ui.profile_menu_geometry).
PROFILE_BUTTON_RECT = pygame.Rect(12, SCREEN_HEIGHT - 52, 220, 42)
COLLECTION_BACK_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 110, SCREEN_HEIGHT - 80, 220, 48)
UPGRADES_BACK_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 110, SCREEN_HEIGHT - 80, 220, 48)
ACHIEVEMENTS_RETURN_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 110, SCREEN_HEIGHT - 80, 220, 48)
MARBLE_BACK_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 90, 620, 180, 40)
MARBLE_UPGRADES_TOGGLE_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 180, 668, 360, 44)
# Action-upgrade button: appears beside the action area while an action is
# selected, upgrading it from v1 to v2 for ACTION_UPGRADE_COST. Sits at the
# action row's vertical center, to its right.
ACTION_UPGRADE_RECT = pygame.Rect(ACTION_AREA_COORDS[0] + ACTION_AREA_COORDS[2] + 12,
                                  ACTION_AREA_COORDS[1], 150, GRID_SIZE)
# The bottom-left MAIN MENU button on the play screen: leaving the current game
# and returning to the title screen (same action as the game-over screen's
# MAIN MENU button). Sized to stay left of the re-centered board.
RETURN_TO_MENU_BUTTON_RECT = pygame.Rect(0, SCREEN_HEIGHT - 36, 100, 36)
BLOCK_INTERIOR_COLOR = BLACK
MARBLE_COLOR = WHITE
# Toggle the 3px outline border drawn around blocks (WHITE, or RED once a block
# runs out of triggers). Set to False to hide all block borders while keeping
# each block's shape fill, effect icon, and portal number. A NONE block's dotted
# outline IS its border, so it hides too; LINE blocks keep their line (that's
# the shape itself).
BLOCK_BORDERS_ON = False
GRID_WIDTH = MARBLE_BOX_COORDS[2] // GRID_SIZE
GRID_HEIGHT = MARBLE_BOX_COORDS[3] // GRID_SIZE
# The dynamic board: a new game starts with only a small centered region of
# the 10x15 marble box unlocked (BOARD_START_WIDTH x BOARD_START_HEIGHT
# squares, 2 wide x 3 tall = the middle six squares). Buying a Board Unit in
# the shop (BOARD_UNIT_PRICE, always offered in the rightmost cell of the top
# components row) lets the player click any locked square to unlock it so the
# marble can
# travel there. Locked squares act as solid walls. The unlocked state (and
# Board Units in hand) is saved with a game and restored when its slot loads;
# only starting a BRAND-NEW game locks the board back down to this 2x3 start.
BOARD_START_WIDTH = 2
BOARD_START_HEIGHT = 3
BOARD_UNIT_PRICE = 8  # unlocking one locked board square costs $8
# The Mineshaft whole card makes Board Units cost this instead.
MINESHAFT_BOARD_UNIT_PRICE = 5
# The Coupon whole card discounts every shop option (Board Units excluded) to
# this fraction of its price; the Market whole card refunds this fraction of an
# item's price when it is sold (the plain sale is a half).
COUPON_PRICE_FACTOR = 0.75
MARKET_SELL_FRACTION = 0.75
# The Pedestal whole card retriggers the scorer of the first this-many blocks
# the marble touches in a run, and the Watch whole card lets only the first
# this-many touched blocks contribute score at all (so one run keeps a list of
# at most the larger of the two: see Game.run_first_blocks).
PEDESTAL_RETRIGGERS = 3
WATCH_BLOCK_LIMIT = 5
# The Inferno whole card adds this to the total-score exponent.
INFERNO_EXPONENT_BONUS = 0.07
# The Tesseract whole card permanently gains this much xMult for every shop
# reroll (saved with the game; applied at the start of each run).
TESSERACT_REROLL_XMULT = 0.1
# The Doppelganger whole card's extra marble leaves the Start block with this
# sideways drift (px/s), so the two marbles separate instead of overlapping.
DOPPELGANGER_START_VX = 1.0
BOARD_UNIT_ROW = 1  # the shop's top (components) item row
BOARD_UNIT_COL = SHOP_GRID_COLS - 2  # the row's rightmost cell
FPS = 60
DT = 1.0 / FPS

# Physics constants
MAX_MARBLE_RECURSION = 3
MAX_MARBLE_SPEED = 6000  # px/s, clamps runaway speed to bound simulation cost
MAX_SUB_STEPS = 64  # Hard cap on movement sub-steps per update
MAX_STEP_DISTANCE = 4.0  # px per sub-step; <= 2 * MARBLE_RADIUS prevents tunneling
GRAVITY = 2500  # pixels/s^2
MARBLE_RADIUS = 8
MARBLE_MASS = 1 # scales gravity and air resistance
# The Singularity final boss (the 24th run) makes the marble gain mass at this
# rate (mass per second), so it falls ever faster over the course of the run.
SINGULARITY_MASS_GROWTH = 0.5
FRICTION_COEFFICIENT = 1
ROLLING_FRICTION = 0
RESTITUTION = 0  # Bounciness factor for walls
BOUNCY_RESTITUTION = Effect.MAGNITUDE[Effect.BOUNCY] / 100.0  # the AVERAGE: every bouncy block rolls its own % (see roll_effect_magnitude)
# A sticky block slows the marble on impact and holds it in place for a short
# time before releasing it. The slowdown grows with the impact speed: the kept
# fraction is 1 / (1 + speed / STICKY_SPEED_REF), so STICKY_SPEED_REF is the
# impact speed that keeps ~half the speed.
STICKY_DURATION = Effect.MAGNITUDE[Effect.STICKY]  # seconds the marble is held against a sticky block (the AVERAGE; each sticky block rolls its own)
STICKY_SPEED_REF = 1200.0  # px/s impact at which about half the speed is kept
STICKY_MIN_KEEP = 0.05  # never keep less than this fraction of the speed
# The palette used to pick a rubber ball's two random half-colors.
RUBBER_BALL_COLORS = [
    (235, 70, 70), (70, 150, 235), (70, 210, 120), (240, 200, 60),
    (175, 100, 225), (60, 205, 215),
]
# A ping-pong ball is very light (mass 0.35): it bounces a little off blocks
# and borders (restitution 0.35), falls at the same speed as a normal marble
# (gravity does not scale below mass 1), and effect pushes (pistons, bouncy
# blocks, rotating blocks, accelerators, black holes) act ~1/mass = ~2.86x
# harder on it.
PING_PONG_MASS = 0.35
PING_PONG_RESTITUTION = 0.35
# The palette used to pick a ping-pong ball's two random half-colors.
PING_PONG_COLORS = [
    (240, 240, 232), (255, 150, 40), (255, 205, 90),
]
AIR_RESISTANCE = 0
ACCELERATION_FORCE = Effect.MAGNITUDE[Effect.ACCELERATOR]  # the AVERAGE: every accelerator block rolls its own force
PISTON_FORCE = Effect.MAGNITUDE[Effect.PISTON]  # px/s launch speed; the AVERAGE, each piston block rolls its own
BLACK_HOLE_FORCE = Effect.MAGNITUDE[Effect.BLACK_HOLE]  # px/s^2 of pull at the edge of the range; the AVERAGE, each black hole rolls its own
BLACK_HOLE_RANGE = 160  # px: how far a black-hole block pulls the marble
BLACK_HOLE_MIN_DIST = 40  # px: clamps the pull so it doesn't explode at contact
ROTATE_SPEED = Effect.MAGNITUDE[Effect.ROTATE]  # deg/s; the AVERAGE, each rotate block rolls its own spin
ROTATE_FLING = 10  # px/s tangential launch speed from a rotating shape's surface
# Extra shape geometry. The peg is a small solid circle (a compact obstacle);
# the sawtooth is a row of small upward teeth along the bottom of the unit; the
# platform and corner legs are half a cell thick (see the Block geometry).
PEG_RADIUS = 5
SAWTOOTH_TEETH = 4
SAWTOOTH_HEIGHT = 13
# The cradle's valley: how deep the V is cut from the cell's top edge and how
# wide its flat floor is. The floor is wider than a marble so the marble rests
# on it (a single, stable contact) instead of wedging between the walls, and
# the slab below closes the cell so it can never slip out the bottom.
CRADLE_FLOOR_DEPTH = 20
CRADLE_FLOOR_HALF = 12
# Tuning for the newer effects. A conveyor is a BELT: it carries the marble
# along its surface at CONVEYOR_SPEED (a constant, like a real belt, so it does
# not accelerate the marble); a phase block makes the marble pass through every
# block for PHASE_DURATION seconds; a splitter never lets the marble count grow
# past MAX_MARBLES, since every marble is simulated each frame.
CONVEYOR_SPEED = Effect.MAGNITUDE[Effect.CONVEYOR]  # px/s a conveyor carries a marble along at (the AVERAGE; each belt rolls its own)
PHASE_DURATION = Effect.MAGNITUDE[Effect.PHASE]  # seconds of no block collisions after a phase touch (the AVERAGE; each phase block rolls its own)
MAX_MARBLES = 16  # cap on marbles alive at once (splitter copies included)

# Sound effects are synthesized in their own module; importing it also starts
# the mixer (it degrades to silent no-ops when no audio device is available).
import achievements
import collection
import metagame
import sounds

# The physics engine lives in its own module (physics.py) and operates on
# Marble instances. It imports the enums/constants defined above, so this
# import must come after them.
from physics import PhysicsEngine


class Block:
    """A block composed of a Shape, an Effect, and a Scorer."""

    def __init__(self, x, y, shape=Shape.RECT, effect=Effect.NONE,
                 scorer=Scorer.NONE, scorer_amount=None, angle=0, origin=None,
                 portal_number=0, key_number=0, trigger_limit=1, trigger_paid=0,
                 effects=None, effect_amounts=None):
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
        self.get_cradle_pieces = self._get_cradle_pieces()
        self.get_corner_silhouette = self._get_corner_silhouette()
        self.get_cradle_silhouette = self._get_cradle_silhouette()
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

    def _get_cradle_pieces(self):
        """The cradle's solid: two side wedges plus a thick floor slab.

        A wide valley is cut from the cell's top edge down to a flat floor
        (wider than a marble) so a marble that rolls or falls in is caught and
        rests on the floor at the center. The slab below the floor closes the
        cell, so a marble can never slip out the bottom. The solid is therefore
        three convex pieces (a left wedge, a right wedge, and the slab), each
        rotated with the block (and ROTATE spin) so the hitbox matches the drawn
        shape.
        """
        left, top = self.rect.left, self.rect.top
        right, bottom = self.rect.right, self.rect.bottom
        center_x = self.rect.centerx
        floor_y = top + CRADLE_FLOOR_DEPTH
        half = CRADLE_FLOOR_HALF
        base_pieces = [
            [(left, top), (center_x - half, floor_y), (left, floor_y)],
            [(right, top), (center_x + half, floor_y), (right, floor_y)],
            [(left, floor_y), (right, floor_y), (right, bottom), (left, bottom)],
        ]
        return [[self._rotate_point(point, self.angle) for point in piece]
                for piece in base_pieces]

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

    def _get_cradle_silhouette(self):
        """The cradle's whole outline as ONE polygon (no seams between pieces).

        The cradle's solid is two side wedges sitting on a floor slab, so
        outlining the three pieces separately draws a line inside the shape
        where each wedge meets the slab. This outline follows only the outside
        of the union (up the left wedge, across the flat floor, up the right
        wedge, then down the outside), which is what the shape's
        component/ghost image should show.
        """
        left, top = self.rect.left, self.rect.top
        right, bottom = self.rect.right, self.rect.bottom
        center_x = self.rect.centerx
        floor_y = top + CRADLE_FLOOR_DEPTH
        half = CRADLE_FLOOR_HALF
        base_points = [(left, top), (center_x - half, floor_y),
                       (center_x + half, floor_y), (right, top),
                       (right, bottom), (left, bottom)]
        return [self._rotate_point(point, self.angle) for point in base_points]

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
        # The bottom opening is exactly the marble diameter, centered in the cell.
        wall_w = self.rect.centerx - MARBLE_RADIUS - left
        samples = 8
        left_curve = []
        right_curve = []
        for i in range(samples + 1):
            u = i / samples
            y = top + u * self.rect.height
            inset = wall_w * (2 * u - u * u)  # 0 at the top, wall_w at the bottom
            left_curve.append((left + inset, y))
            right_curve.append((right - inset, y))
        # Each wall: down the cell's outer edge, across the bottom face, then up
        # the curved inner surface back to the top corner (a convex wedge).
        left_wall = [(left, top), (left, bottom), (left + wall_w, bottom)] + left_curve[:0:-1]
        right_wall = [(right, top), (right, bottom), (right - wall_w, bottom)] + right_curve[:0:-1]
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


def random_action_version():
    """The version a newly created action starts at: v1, or v2 rarely.

    Every action the shop offers (and every one granted by a conversion or a
    card) is rolled here, so ACTION_V2_CHANCE of them arrive already upgraded —
    a free saving of ACTION_UPGRADE_COST. Actions loaded from a save keep the
    version they were saved with (save_system never rolls).
    """
    return 2 if random.random() < ACTION_V2_CHANCE else 1


def random_effect_count():
    """How many effects a random shop block has.

    No effect for 1/4 of blocks (a plain wall); the rest follow the geometric
    schedule: 1 effect for 1/2, 2 for 1/4, 3 for 1/8, and so on, capped at the
    number of real effects available.
    """
    if random.random() < 0.25:
        return 0
    count = 1
    while count < len(Effect.REAL_ORDER) and random.random() < 0.5:
        count += 1
    return count


def roll_magnitude(average, floor=None):
    """Roll an item's OWN magnitude around the average it is built from.

    The deviation x from the average is an integer with probability
    1/(x^2 + 1) — the average itself about a third of the time, one step off
    about a sixth, two steps off a sixteenth, and (with |x| <= 8) a wild
    outlier once in 65 rolls. One step is 10% of the average (see
    components.magnitude_step): a +Chips piece averages 30 chips and steps by
    3, a +Mult piece averages 4 and steps by 0.4, a piston averages 1500 px/s
    and steps by 150. A value with no average to speak of (a scorer whose
    amount is unused) is returned untouched, and ``floor`` is the lowest value
    a roll may land on.
    """
    step = magnitude_step(average)
    if not step:
        return average
    deviation = random.choices(
        range(-MAGNITUDE_MAX_STEPS, MAGNITUDE_MAX_STEPS + 1),
        weights=MAGNITUDE_WEIGHTS, k=1)[0]
    # The roll is NEVER rounded, because rounding snaps a small magnitude onto
    # a coarser grid than the 10% it is supposed to move in: a +Mult scorer
    # (average 4, step 0.4) would land on whole hundreds of percent — its
    # spread becomes +/- 8 whole mult instead of the designed +/- 7.2. The
    # arithmetic multiplies by the step divisor and divides back, which is the
    # exact decimal (average * 0.1 would carry float noise where average / 10
    # is exact), so a whole answer stays whole and a fractional one carries no
    # arithmetic dust into prices and descriptions.
    value = (average * (MAGNITUDE_STEP_DIVISOR + deviation)
             / MAGNITUDE_STEP_DIVISOR)
    if floor is not None and value < floor:
        value = floor
    return value


def roll_scorer_amount(scorer):
    """A scorer item's own magnitude (the average when it has no magnitude)."""
    return roll_magnitude(Scorer.DEFAULT_AMOUNT.get(scorer, 0),
                          scorer_magnitude_floor(scorer))


def roll_effect_magnitude(effect):
    """A scalable effect's own strength (0 for an on/off effect)."""
    return roll_magnitude(Effect.MAGNITUDE.get(effect, 0),
                          effect_magnitude_floor(effect))


def roll_effect_amounts(effects):
    """The {effect: magnitude} map for a fresh block's effects.

    The one place a block's effects get their strengths, so every path that
    builds a block — the shop, a Rubble grant, an assembly, an Anointment —
    rolls the same way. An on/off effect is left out of the map entirely (it
    has no magnitude to carry).
    """
    return {e: roll_effect_magnitude(e) for e in dict.fromkeys(effects)
            if e in Effect.MAGNITUDE}


def block_effect_magnitude(item, effect):
    """An item's own strength for an effect (the average when unrolled)."""
    return getattr(item, "effect_amounts", {}).get(effect,
                                                    Effect.MAGNITUDE.get(effect, 0))


def role_block_parts(scorer, shape, effects):
    """The shape and effects a randomly built block gets for its scorer.

    The Start and Finish scorers are run ROLES, not payoffs, so a block built
    around one is ALWAYS a plain Rect with no effects — whether the shop rolled
    it or a Rubble conversion granted it. A role can therefore never arrive
    attached to physics the player did not choose (and its price is exactly
    75% of Rect + the role). Every other scorer keeps the parts it rolled.
    """
    if scorer in (Scorer.START, Scorer.FINISH):
        return Shape.RECT, []
    return shape, effects


def role_block_name(scorer, shape):
    """The name a randomly built block gets: "Start Block" for a run role.

    A role block is a Rect by definition (see role_block_parts), so naming it
    after its shape would just add noise ("Rect Start"); it is named the same
    way as the Start/Finish blocks the player is given at the start.
    """
    if scorer in (Scorer.START, Scorer.FINISH):
        return f"{Scorer.name(scorer)} Block"
    return f"{Shape.name(shape)} {Scorer.name(scorer)}"


def component_weight(kind, value):
    """Rarity weight for a component: cheaper components appear more often."""
    price = COMPONENT_PRICES.get((kind, value), 1)
    return 1.0 / max(price, 1)


def weighted_sample_without_replacement(options, weights, k):
    """Pick ``k`` distinct items from ``options``, weighted by ``weights``."""
    result = []
    remaining = list(options)
    remaining_weights = list(weights)
    for _ in range(min(k, len(remaining))):
        chosen = random.choices(remaining, weights=remaining_weights, k=1)[0]
        index = remaining.index(chosen)
        result.append(chosen)
        del remaining[index]
        del remaining_weights[index]
    return result


def block_resale_price(block):
    """A placed block's own price: what it was placed with, never a recount.

    Placing a block stamps it with the price of the item it came from (see the
    grid-placement code), and everything that needs that block's worth reads
    THIS value — erasing/refunding it, selling it with Death, duplicating it
    with Recognition, the Painting condition's board sell total. Re-summing the
    block's parts instead drifts away from what the player actually paid: a
    placed role block is recorded with effects=[NONE] and sums to $114 while
    the identical toolbox item is $109, and an effect added by Anointment is
    priced per roll.

    The part-sum is only a last resort for a block that never got a stored
    price (a hand-built block, a save written before the price was persisted);
    materializing it on the block keeps every later read consistent. It prices
    a shattered fragile block by the shape it was built with, matching the
    shape a refund hands back.
    """
    price = getattr(block, "resale_price", None)
    if price is not None:
        return price
    shape = (block._fragile_shape
             if getattr(block, "_fragile_shape", None) is not None else block.shape)
    price = block_price_for(shape, block.effects, block.scorer,
                            block.scorer_amount,
                            getattr(block, "effect_amounts", None))
    block.resale_price = price
    return price


def _random_card_scorer(condition):
    """A random card scorer that can pair with the given condition.

    Any scorer can pair with any condition now (an end-phase Quick card pays
    off the marble's speed at the run's LAST block hit), so the phase only
    keeps the caller's bookkeeping meaningful and the draw is a flat one.
    """
    condition_phase(condition)
    return random.choice(CARD_SCORERS)


def random_prebuilt_card_value():
    """A random pre-built splittable card value: a random (condition, scorer).

    Any card scorer can pair with any condition, so a pre-built splittable card
    can carry any scorer — not just +Chips/+Mult/xMult. Used by the random-card
    grants.
    """
    condition = random.choice(CONDITION_ORDER)
    return condition_scorer_card(condition, _random_card_scorer(condition))


def prebuilt_card_pool(grid_combos=10):
    """Distinct candidate whole cards for a random-card grant.

    The indivisible whole cards (the Card.ORDER catalog) plus ``size`` random
    (condition x any scorer) grid combos, so a granted splittable card can
    carry any scorer.
    """
    pool = list(Card.ORDER)
    seen = set(pool)
    tries = 0
    while len(pool) - len(Card.ORDER) < grid_combos and tries < grid_combos * 8:
        tries += 1
        value = random_prebuilt_card_value()
        if value is not None and value not in seen:
            seen.add(value)
            pool.append(value)
    return pool


def random_card_option_value():
    """A random shop card offer.

    Chooses equally likely from a combined pool of conditions and the
    indivisible whole cards (the Card.ORDER catalog); a condition pick gets a
    random scorer attached, turning it into a composed (condition x scorer)
    card offer.
    """
    pool = list(CONDITION_ORDER) + list(Card.ORDER)
    choice = random.choice(pool)
    if choice in Card.ORDER:
        return choice
    return condition_scorer_card(choice, _random_card_scorer(choice))


def make_card_item(value, col=0, row=0, amount=None):
    """A card item, carrying its scorer half's own magnitude.

    A composed card (condition x scorer) rolls the SCORER half's magnitude when
    the caller has none — the shop rolls one per offer, exactly like a scorer
    component — so the card pays, prices and describes itself at the strength
    it actually has (see components.card_price_for / card_description). A whole
    card (Coupon, Showman, Garden, ...) has no scorer half, so it carries no
    magnitude and is unaffected. ``amount`` is passed through by callers that
    already know it: a card built from a toolbox scorer keeps that piece's
    magnitude, and a Recognition copy keeps the original's.
    """
    scorer = card_scorer(value)
    if amount is None:
        amount = roll_scorer_amount(scorer) if scorer else 0
    return CardItem(value, card_price_for(value, amount), col=col, row=row,
                    amount=amount or 0)


_next_portal_number = 0


def next_portal_number():
    """Return a fresh, unique pairing number for a new portal pair."""
    global _next_portal_number
    _next_portal_number += 1
    return _next_portal_number


_next_key_number = 0


def next_key_number():
    """Return a fresh, unique pairing number for a new Key/Lock pair."""
    global _next_key_number
    _next_key_number += 1
    return _next_key_number


def block_shape(block):
    """A block's shape, using the shape it had before a fragile break.

    A fragile block that shattered is stored as a no-hitbox Shape.NONE so a run
    reset can rebuild it; anything that reasons about what the block IS (its
    key/lock role, its refund name) asks this instead of reading the shape
    directly.
    """
    original = getattr(block, "_fragile_shape", None)
    return original if original is not None else block.shape


def get_next_required_score(run, growth=None):
    """Return the score needed to reach the next level in the given run.

    ``growth`` is the factor a run's target grows by for the next one: the
    save's own difficulty (see Difficulty.SCORE_GROWTH), or 2x when the caller
    has none to hand (the difficulty-2-and-up doubling every plain test
    expects). Targets are whole numbers and always strictly grow: the gentler
    1.6x growth rounds down, so the ``+ 1`` keeps an early target from
    stalling (1 -> 2 -> 3 -> 4 -> 6 -> 9 ...).
    """
    if growth is None:
        growth = Difficulty.score_growth(DEFAULT_DIFFICULTY)
    if run >= len(REQUIRED_SCORES):
        for _ in range(len(REQUIRED_SCORES), run + 1):
            REQUIRED_SCORES.append(max(REQUIRED_SCORES[-1] + 1,
                                       int(REQUIRED_SCORES[-1] * growth)))
    return REQUIRED_SCORES[run]


class BlockItem:
    """A purchasable, pre-assembled block offered by the shop."""
    kind = "block"

    def __init__(self, col, row, shape, effect, scorer, scorer_amount, price, name,
                 portal_number=0, key_number=0, trigger_limit=1, trigger_paid=0,
                 effects=None, effect_amounts=None):
        self.col = col
        self.row = row
        self.shape = shape
        self.effects = list(effects) if effects is not None else [effect]
        # Each scaleable effect's own rolled strength for this block (see
        # roll_effect_amounts); missing effects read the average.
        self.effect_amounts = dict(effect_amounts or {})
        self.scorer = scorer
        self.scorer_amount = scorer_amount
        self.price = price
        self.name = name
        self.portal_number = portal_number  # portal pairs share a number
        self.key_number = key_number  # key/lock pairs share a number
        # A block's trigger limit can be raised by paying cash; that cash is
        # refunded on top of the resale value when the block is sold.
        self.trigger_limit = trigger_limit
        self.trigger_paid = trigger_paid

    def effect_magnitude(self, effect):
        """This block's own strength for an effect (the average when unrolled)."""
        return self.effect_amounts.get(effect) or Effect.MAGNITUDE.get(effect, 0)

    @property
    def effect(self):
        """The block's primary (first) effect."""
        return self.effects[0] if self.effects else Effect.NONE

    def has_effect(self, effect):
        """True when the block has the given effect (one of possibly many)."""
        return effect in self.effects


class CardItem:
    """A bought card: a permanent score effect applied every run (a Joker)."""
    kind = "card"

    def __init__(self, value, price, col=0, row=0, amount=0):
        self.value = value  # the card's ID number (a Card constant)
        self.price = price
        self.col = col
        self.row = row
        self.name = Card.name(value)
        # A composed card's SCORER half magnitude (its own rolled strength): a
        # +Chips half rolled to 45 makes the card pay 45 a unit instead of 30.
        # A whole card has no scorer half, and a card that was never rolled
        # (an old save, a hand-built test card) is 0 — both pay, price and
        # describe at the average, exactly as they did before magnitudes.
        self.amount = amount or 0


class ActionItem:
    """A bought action: a one-use power-up that modifies a block or a card.

    Actions come in two versions: v1 (as bought) and v2 (upgraded for
    ACTION_UPGRADE_COST); v2 is much stronger and cannot be upgraded further.
    """
    kind = "action"

    def __init__(self, value, price, version=1, col=0, row=0):
        self.value = value  # the action's ID number (an Action constant)
        self.price = price
        self.version = version  # 1 or 2
        self.col = col
        self.row = row
        self.name = Action.name(value)


class ScorerToken:
    """A Spirit token: a destroyed block's scorer, kept firing each run.

    Spirit destroys a block and keeps its scorer: at the start of every run it
    still covers, the token fires that scorer once (see Game._apply_tokens).
    The token carries the destroyed block's own data — its amount, effects and
    the cell it stood in — so board-relative payoffs (Summit, Powerline,
    Frontier, Cluster) and effect-count payoffs (Effective) keep working.
    ``runs_left`` is None for a v2 token, which never expires.
    """
    kind = "token"

    def __init__(self, scorer, amount, shape=Shape.RECT, effects=None,
                 x=0, y=0, runs_left=None):
        self.scorer = scorer
        self.scorer_amount = amount
        self.shape = shape
        self.effects = list(effects) if effects is not None else [Effect.NONE]
        self.x = x
        self.y = y
        self.runs_left = runs_left  # None = permanent (v2)
        # True once the token has fired in the run now in progress, so a token
        # created mid-run is not spent by that same run's end.
        self.fired = False
        self.name = Scorer.name(scorer)


class CashBreakdown:
    """Hover target for the shop's "Last run cash gained" readout.

    The readout is not an item, but hovering it opens the same info box an
    item gets (see Game._describe_item), breaking the last run's earnings down
    into base cash, interest, the over-the-target score bonus, and cash from
    cards and scorers. The single instance below is never bought, sold, or
    drawn; it only gives the readout something to be hovered as.
    """


CASH_BREAKDOWN = CashBreakdown()


# The save system, card effects, profile system, and drawing helpers live in
# their own modules and need the classes above, so these imports must come
# after them (like the physics import).
import cards
import profiles
import save_system
import ui


class Shop:
    """A grid-based shop: two random blocks plus two of each component type."""
    def __init__(self, rect, game=None):
        self.rect = pygame.Rect(rect)
        self.cols = rect[2] // GRID_SIZE
        self.rows = rect[3] // GRID_SIZE
        self.items = []
        # Extra offers added by the Picky scorer (one per banked slot). The
        # Game keeps the persistent count and sets this before refreshing.
        self.bonus_slots = 0
        # The Game this shop belongs to, so the card slots can tell which cards
        # the player already owns (and whether the Showman card lifts the
        # one-copy rule). None when a shop is built on its own (in a test):
        # no ownership, so every card is on offer.
        self.game = game
        self.refresh()

    def owned_cards(self):
        """The card values the card slots must not offer again.

        Empty while the player owns the Showman card: that card's whole point is
        owning more than one copy of the same card, so with it the shop may
        offer cards the player already has (and _buy_shop_item lets them be
        bought). See Game._has_card for what owning means for a card the run's
        trial has disabled.
        """
        game = self.game
        # A shop built during Game.reset_game runs before the card area and the
        # trial state exist; nothing is owned yet, so nothing is filtered.
        if (game is None or not hasattr(game, "cards")
                or not hasattr(game, "disabled_card")):
            return set()
        if game._has_card(Card.SHOWMAN):
            return set()
        return {card.value for card in game.cards}

    def refresh(self):
        """Reroll the shop's random selection of components and blocks.

        Rarer (more expensive) components show up less often, and a block's
        rarity is the product of its components' rarities, so a block made of
        several rare parts is multiplicatively harder to find.
        """
        self.items = []
        # All shop items line up next to each other in a single horizontal row.
        col = 1
        # Two random shapes and effects plus THREE random scorers (cheap ones
        # are more common). The shop never sells the free default parts — the
        # Rect shape, the None effect, or the None scorer — because the
        # assembler fills those in automatically when a part is left out.
        # (Shape.NONE, the invisible field, is a real shape and stays on sale.)
        shape_pool = [s for s in Shape.ORDER if s != Shape.RECT]
        effect_pool = [e for e in Effect.ORDER if e != Effect.NONE]
        scorer_pool = [s for s in Scorer.SHOP_ORDER if s != Scorer.NONE]
        shape_weights = [component_weight(Component.SHAPE, s) for s in shape_pool]
        effect_weights = [component_weight(Component.EFFECT, e) for e in effect_pool]
        scorer_weights = [component_weight(Component.SCORER, s) for s in scorer_pool]
        for shape in weighted_sample_without_replacement(shape_pool, shape_weights, 2):
            self.items.append(Component.shape_component(shape, col=col, row=1))
            col += 1
        for effect in weighted_sample_without_replacement(effect_pool, effect_weights, 2):
            # A scaleable effect is sold at its OWN rolled strength (a 2100 px/s
            # piston, a 2400 px/s^2 repulsor) and priced for it — never at 0,
            # which is not a strength any effect can have.
            self.items.append(Component.effect_component(
                effect, magnitude=roll_effect_magnitude(effect), col=col, row=1))
            col += 1
        for scorer in weighted_sample_without_replacement(scorer_pool, scorer_weights, 3):
            # A role scorer (Start/Finish) is offered as a ready-made block
            # instead of a scorer component — see _scorer_offer.
            self.items.append(self._scorer_offer(scorer, col, 1))
            col += 1
        # Two card slots. Each slot chooses equally likely from a combined pool
        # of conditions and the indivisible whole cards (ERR 404 / Blueprint /
        # Showman); when a slot draws a condition, a random scorer is attached
        # so the offer is a full composed (condition x any scorer) card. The
        # two offers are kept distinct, and neither may be a card the player
        # already owns unless the Showman card lifts the one-copy rule — an
        # offer that cannot be bought is a wasted slot, and a card the player
        # owns should not come back around run after run (see owned_cards).
        card_col = 1
        owned = self.owned_cards()
        offers = []
        tries = 0
        while len(offers) < 2 and tries < 24:
            tries += 1
            value = random_card_option_value()
            if value is not None and value not in offers and value not in owned:
                offers.append(value)
        while len(offers) < 2:
            offers.append(random_card_option_value())
        for card in offers:
            self.items.append(make_card_item(card, col=card_col, row=3))
            card_col += 1
        # Two random conditions sit next to the two whole cards (the condition
        # is the trigger half of a split card; a scorer pairs with it to build
        # a card). Cheaper (common) conditions are offered more often.
        cond_weights = [component_weight(Component.CONDITION, c) for c in CONDITION_ORDER]
        cond_col = 3
        for condition in weighted_sample_without_replacement(CONDITION_ORDER,
                                                             cond_weights, 2):
            self.items.append(Component.condition_component(condition, col=cond_col, row=3))
            cond_col += 1
        # The action slots sit to the right of the conditions in the same row.
        # The catalogue is bigger than the room left in the row, so each refresh
        # shows a random SHOP_ACTION_SLOTS of them — always DISTINCT actions
        # (random.sample never repeats) — and each is rolled for its version, so
        # a v2 action shows up on its own now and then.
        action_col = cond_col
        for action in random.sample(Action.ORDER, SHOP_ACTION_SLOTS):
            self.items.append(ActionItem(action, Action.PRICES.get(action, 60),
                                         version=random_action_version(),
                                         col=action_col, row=3))
            action_col += 1
        # The two random pre-built blocks sit to the right of the actions in
        # the same (bottom) row. Each component is drawn by rarity, so a
        # block's overall chance is the product of its parts' weights. A block
        # has no effect 1/4 of the time (a plain wall); otherwise 1 effect half
        # the time, 2 a quarter, 3 an eighth, and so on. Pre-built blocks may
        # still use any shape or scorer (a plain Rect block with no scorer is a
        # legitimately useful wall) — except a block built around a run role,
        # which is always a plain Rect (see role_block_parts).
        all_shape_weights = [component_weight(Component.SHAPE, s) for s in Shape.ORDER]
        all_scorer_weights = [component_weight(Component.SCORER, s) for s in Scorer.SHOP_ORDER]
        block_col = action_col
        for _ in range(2):
            shape = random.choices(Shape.ORDER, weights=all_shape_weights, k=1)[0]
            count = random_effect_count()
            effects = random.sample(Effect.REAL_ORDER, count)
            scorer = random.choices(Scorer.SHOP_ORDER, weights=all_scorer_weights, k=1)[0]
            shape, effects = role_block_parts(scorer, shape, effects)
            amount = roll_scorer_amount(scorer)
            amounts = roll_effect_amounts(effects)
            name = role_block_name(scorer, shape)
            self.items.append(BlockItem(block_col, 3, shape, Effect.NONE, scorer, amount,
                                        block_price_for(shape, effects, scorer, amount, amounts),
                                        name, effects=effects, effect_amounts=amounts))
            block_col += 1
        # Picky bonus slots: each banked slot adds one extra random offer to
        # the shop, with the offer's kind (shape/effect/scorer/block/card/
        # action) chosen uniformly. The offers sit in the rows below the
        # standard ones and reappear every time the shop refreshes.
        bcol, brow = 1, 5
        for _ in range(self.bonus_slots):
            self.items.append(self._random_offer(col=bcol, row=brow))
            bcol += 1
            if bcol > self.cols:
                bcol = 1
                brow += 1

    def _scorer_offer(self, scorer, col, row):
        """The shop offer for a drawn scorer.

        An ordinary scorer is sold as a scorer component, to be assembled onto
        a block the player builds. The Start and Finish scorers are run ROLES,
        so they are sold as ready-made blocks instead: a plain Rect with no
        effects, priced by block_price_for like any other block. A role is
        bought whole, never assembled onto someone else's physics.
        """
        if scorer in (Scorer.START, Scorer.FINISH):
            amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
            shape, effects = role_block_parts(scorer, Shape.RECT, [])
            name = role_block_name(scorer, shape)
            return BlockItem(col, row, shape, Effect.NONE, scorer, amount,
                             block_price_for(shape, effects, scorer, amount), name,
                             effects=effects)
        amount = roll_scorer_amount(scorer)
        return Component.scorer_component(scorer, amount=amount, col=col, row=row)

    def _random_offer(self, col, row):
        """One random shop offer of a uniformly chosen kind (Picky slots)."""
        kind = random.choice([Component.SHAPE, Component.EFFECT, Component.SCORER,
                              "block", "card", "action"])
        if kind == Component.SHAPE:
            value = random.choice([s for s in Shape.ORDER if s != Shape.RECT])
            return Component.shape_component(value, col=col, row=row)
        if kind == Component.EFFECT:
            value = random.choice([e for e in Effect.ORDER if e != Effect.NONE])
            return Component.effect_component(value, magnitude=roll_effect_magnitude(value),
                                              col=col, row=row)
        if kind == Component.SCORER:
            value = random.choice([s for s in Scorer.SHOP_ORDER if s != Scorer.NONE])
            return self._scorer_offer(value, col, row)
        if kind == "block":
            shape = random.choice(Shape.ORDER)
            count = random_effect_count()
            effects = random.sample(Effect.REAL_ORDER, count)
            scorer = random.choice(Scorer.SHOP_ORDER)
            shape, effects = role_block_parts(scorer, shape, effects)
            amount = roll_scorer_amount(scorer)
            amounts = roll_effect_amounts(effects)
            name = role_block_name(scorer, shape)
            return BlockItem(col, row, shape, Effect.NONE, scorer, amount,
                             block_price_for(shape, effects, scorer, amount, amounts),
                             name, effects=effects, effect_amounts=amounts)
        if kind == "card":
            value = random_card_option_value()
            return make_card_item(value, col=col, row=row)
        value = random.choice(Action.ORDER)
        return ActionItem(value, Action.PRICES.get(value, 60),
                          version=random_action_version(), col=col, row=row)

    def item_at(self, pos):
        """Return the shop item occupying a screen position, or None."""
        if not self.rect.collidepoint(pos):
            return None
        gx = (pos[0] - self.rect.x) // GRID_SIZE
        gy = (pos[1] - self.rect.y) // GRID_SIZE
        for item in self.items:
            if item.col == gx and item.row == gy:
                return item
        return None

class Toolbox:
    """Inventory of bought blocks, styled like the marble box and shop."""
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.cols = rect[2] // GRID_SIZE
        self.rows = rect[3] // GRID_SIZE
        self.items = []

    def add(self, item):
        """Add a bought block config; returns False if the toolbox is full."""
        if len(self.items) >= self.cols * self.rows:
            return False
        self.items.append(item)
        return True

    def item_at(self, pos):
        """Return the owned item at a screen position, or None."""
        if not self.rect.collidepoint(pos):
            return None
        gx = (pos[0] - self.rect.x) // GRID_SIZE
        gy = (pos[1] - self.rect.y) // GRID_SIZE
        index = gy * self.cols + gx
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def index_at(self, pos):
        """Return the toolbox index (cell) at a screen position, or None."""
        if not self.rect.collidepoint(pos):
            return None
        gx = (pos[0] - self.rect.x) // GRID_SIZE
        gy = (pos[1] - self.rect.y) // GRID_SIZE
        index = gy * self.cols + gx
        if 0 <= index < len(self.items):
            return index
        return None

class Assembler:
    """Tracks the toolbox components chosen for a new block.

    Components are NOT moved out of the toolbox: while assigned they stay there
    and are highlighted with a green border (see draw_toolbox). Shape and scorer
    are single-slot; effect components toggle on and off so a block can have
    multiple effects.
    """
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.shape = None
        self.scorer = None
        self.effects = []

    def clear(self):
        self.shape = None
        self.scorer = None
        self.effects = []

    def has_parts(self):
        """True when at least one shape/effect/scorer part is assigned.

        Assembly no longer needs all three kinds: any combination is allowed,
        and a missing part defaults to the Rect shape, no effect, or no scorer.
        """
        return self.shape is not None or self.scorer is not None or bool(self.effects)


# The panel/card/icon drawing helpers and the particle/popup classes moved to
# ui.py (see the re-exports at the bottom of this module).


class Marble:
    def __init__(self, x, y):
        self.position = np.array([x, y], dtype=float)
        self.velocity = np.array([0.0, 0.0])
        self.radius = MARBLE_RADIUS
        self.color = MARBLE_COLOR
        self.color2 = self.color  # second half-color for two-tone marbles
        # The marble type chosen for this save (see MarbleType); it drives the
        # marble's appearance and special behavior (8-ball retriggers scoring,
        # rubber ball bounces off blocks and borders).
        self.marble_type = MarbleType.VANILLA
        # Rubber-ball marbles bounce off blocks and borders with full energy.
        self.bouncy = False
        # The marble's own bounciness when it hits a plain block or border
        # (the fraction of the incoming speed reflected): 0 for a vanilla
        # marble, 0.35 for the ping-pong ball. Bouncy blocks always reflect
        # with full energy regardless of this.
        self.restitution = RESTITUTION
        # Sticky-block state: while sticky_timer > 0 the marble is held in
        # place; when it expires the marble is released with sticky_velocity
        # (its damped impact speed). None once not stuck.
        self.sticky_timer = 0.0
        self.sticky_velocity = None
        # Phase-effect state: phase_timer counts down the seconds of "pass
        # through every block" left after touching a phase block, and
        # phase_block is the block that granted it. That block cannot phase the
        # marble again until the marble is clear of it, so a marble resting on
        # a phase block can't re-arm the phase forever.
        self.phase_timer = 0.0
        self.phase_block = None
        # The collision normal physics resolved against each block this frame
        # (block -> unit normal), and the velocity the marble arrived with, both
        # keyed by block. The splitter reads them to send its copy off the
        # surface the marble actually hit.
        self.contact_normals = {}
        self.contact_incoming = {}
        # Accumulated roll angle (radians) for the 3D rotating marble drawing;
        # advanced by the physics engine from the marble's angular velocity.
        self.spin_angle = 0.0
        # Last motion direction (unit vector), used to orient the roll axis when
        # the marble stops (the painted feature keeps its last orientation).
        self._move_dir = np.array([1.0, 0.0])
        self.angular_velocity = 0.0
        self.mass = MARBLE_MASS
        self.on_slope = False
        self.grounded = False
        self.finished = False
        # Trial modifiers set per run by reset_run: the dead-zone trial triples
        # gravity in the marble box's bottom third; the all-finishes trial makes
        # the marble-box borders act as a finish block; the bouncy-castle trial
        # makes every solid block reflect the marble like a bouncy block.
        self.dead_zone = False
        self.finish_on_border = False
        self.bouncy_castle = False
        # The marble-weight trial scales only EFFECT pushes (pistons, bouncy
        # blocks, rotating shapes, accelerators, black holes) by 1/effect_mass.
        # Fall speed uses marble.mass and is never affected by this field.
        self.effect_mass_mult = 1.0
        # True while a black hole is pulling this marble this frame; the
        # astronaut card times it.
        self.under_black_hole = False
        self.distance = 0.0
        # Decaying peak of the marble's speed, sampled before collision
        # resolution each frame. The Quick scorer reads it so an effect that
        # pins the marble to rest still awards chips for how fast it arrived.
        self.recent_speed = 0.0
        # The marble's current airborne streak (seconds since it last touched
        # any block, including Shape.None/pipes/portals). The Airball scorer
        # rewards +8 mult per second of air before a touch. Grows while the
        # marble has no contact this frame; reset while it is in contact.
        self.air_streak = 0.0
        # Trail bookkeeping: distance moved since the last trail dot was
        # spawned, and the marble's total distance at that time.
        self._trail_accum = 0.0
        self._last_trail_distance = 0.0
        self.collisions_last_tick = []
        self.collisions_this_tick = []
        self._pre_move_position = None
        self.start_block = None  # the START block this marble was released from
        # (cell_a, cell_b) grid-cell rects of the portal pair this marble most
        # recently teleported through; None once it leaves both cells. Only that
        # pair is skipped, so other portal pairs work independently.
        self.last_portal_cells = None
        self.physics = PhysicsEngine()


def _configure_marble_type(marble, marble_type):
    """Apply a marble type's look and behavior to a freshly made marble.

    Called when a run spawns its marbles (reset_run). The rubber ball bounces
    and wears two random half-colors; the ping-pong ball is very light (falls
    normally, bounces a little, effect pushes act harder on it) and wears two
    random half-colors too. Vanilla keeps the plain white look.
    """
    marble.marble_type = marble_type
    marble.bouncy = marble_type == MarbleType.RUBBER_BALL
    marble.mass = MARBLE_MASS
    marble.restitution = RESTITUTION
    marble.color = MARBLE_COLOR
    marble.color2 = MARBLE_COLOR
    if marble_type == MarbleType.RUBBER_BALL:
        marble.color = random.choice(RUBBER_BALL_COLORS)
        marble.color2 = random.choice([c for c in RUBBER_BALL_COLORS
                                       if c != marble.color])
    elif marble_type == MarbleType.PING_PONG:
        marble.mass = PING_PONG_MASS
        marble.restitution = PING_PONG_RESTITUTION
        marble.color = random.choice(PING_PONG_COLORS)
        marble.color2 = random.choice([c for c in PING_PONG_COLORS
                                       if c != marble.color])


class Game:
    def __init__(self):
        # The window, and the off-screen surface every frame is drawn into.
        # Drawing off-screen and presenting the finished frame in one blit (see
        # _present) is what keeps the CRT filter from flickering: the filter
        # rewrites the whole frame — it clears it and lays the warped bands back
        # down — and those half-finished states must never reach the window.
        self.display = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Marblatro")
        pygame.display.set_icon(make_icon())
        self.clock = pygame.time.Clock()
        self.running = True

        self.tiny_font = pygame.font.Font("fonts/garet-heavy.otf", int(16 * FONT_SCALE))
        self.small_font = pygame.font.Font("fonts/garet-heavy.otf", int(18 * FONT_SCALE))
        self.font = pygame.font.Font("fonts/garet-heavy.otf", int(24 * FONT_SCALE))
        self.required_font = pygame.font.Font("fonts/garet-heavy.otf", int(34 * FONT_SCALE))
        self.total_font = pygame.font.Font("fonts/garet-heavy.otf", int(52 * FONT_SCALE))
        self.main_title_font = pygame.font.Font("fonts/MARBLERUN.ttf", 90)

        self.reset_game()
        # Every save slot's file exists from the start (empty placeholders);
        # saving a game fills one in, loading reads one back.
        save_system.ensure_saves()
        # The title screen shows first: the game's name, the 6 save slots the
        # player loads or starts a game from, and an ACHIEVEMENTS button.
        self.title_screen = True
        # The CRT screen filter (see crt.py): on by default, toggled with F2,
        # remembered per profile (metagame.json). It is a post-process over the
        # finished frame, applied by _present below.
        self.crt_filter = metagame.crt_filter()
        # The active save slot (1..6) chosen on the title screen; P saves to
        # it. None until the player picks one.
        self.save_slot = None
        self.slot_confirm_index = None  # slot (0..5) whose LOAD/WIPE panel is open
        # True while the achievements tab (a grid of all achievements) is open.
        self.achievements_open = False
        # True while the marble-type selection screen (shown when starting a
        # new save) is open; the player picks one marble type per save.
        self.marble_selecting = False
        # True while the UPGRADES tab (spend metagame dice on permanent run
        # bonuses) is open from the title screen.
        self.upgrades_open = False
        # True while the COLLECTION tab (cards/components/trials discovered)
        # is open from the title screen.
        self.collection_open = False
        # The compact bottom-of-screen popups (achievement unlocks, collection
        # discoveries) that slide up from under the screen, hold, then slide
        # back down.
        self.popups = []
        # The bottom-left PROFILE switcher on the title screen: the button
        # expands into the current profile's list (each profile owns its own
        # save slots + achievements/collection/metagame files), and its "+"
        # row opens the name-entry prompt that creates a new profile.
        self.profile_menu_open = False
        self.profile_naming = False
        # True while the popup is editing the ACTIVE profile (rename/delete);
        # False while it is creating a brand-new profile.
        self.profile_renaming = False
        # True while the edit popup shows the inline "delete this profile?"
        # confirm (its bottom buttons become Keep / Delete) instead of the
        # name field.
        self.profile_delete_confirm = False
        # True while the edit popup shows the inline "unlock the whole
        # collection?" confirm (its bottom buttons become Keep / Unlock) —
        # this permanently disables achievements for the profile.
        self.profile_unlock_confirm = False
        # True when the last delete attempt could not remove the folder (e.g.
        # Windows has it locked or read-only); shows a note in the confirm.
        self.profile_delete_error = False
        self.profile_name_text = ""

    def reset_game(self):
        """Start a brand-new game: clear the board and reset all progress."""
        self.marbles = []
        self.grid = {}
        self.score_chips = 1
        self.score_mult = 1
        self.run_active = False
        self.run_complete = False
        self.run_cleared = False
        self.awaiting_after_run = False  # True after a run while the player picks RETRY/CONTINUE
        self.score_total = 0
        # Round / run progression: 8 rounds of 3 runs each (24 runs total).
        self.run_number = 0  # total runs completed this game (0..TOTAL_RUNS)
        self.round_index = 0  # current round (0-based)
        self.run_in_round = 0  # current run within the round (0-based)
        self.required_score = 1
        # A fresh game starts with a fresh required-score schedule. The module
        # list is persisted in saves, so loading overwrites it afterward.
        REQUIRED_SCORES[:] = [1]
        self.run_results = []  # True when the run met its score target
        self.runs_cleared = 0
        self.failed_runs = 0
        self.game_over = False
        self.game_won = False
        self.game_perfect = False  # True when every one of the 24 runs was cleared
        # Once the player clicks CONTINUE on the game-over screen, the overlay
        # never auto-shows again for this save (the game keeps going endless).
        self.continue_past_game_over = False
        # Dice earned when this game over was a defeat (shown on the game-over
        # screen; 0 for a victory/perfect win).
        self.game_over_dice_gained = 0
        self.cash = 60  # Start with finite cash for gameplay
        # The marble type chosen for this save (see MarbleType); a fresh game
        # starts vanilla until the player picks one on the selection screen.
        self.marble_type = MarbleType.VANILLA
        # The difficulty chosen for this save (see Difficulty): how many
        # trials a round is played under and how fast the required score
        # grows. A fresh game starts on the game's original balance until the
        # player picks a level on the selection screen; a loaded save restores
        # its own.
        self.difficulty = DEFAULT_DIFFICULTY
        # Whether the permanent metagame upgrade effects (bought with dice on
        # the UPGRADES tab) apply to this save's runs. The player can turn them
        # off for a save on the marble-selection screen; on by default.
        self.upgrades_enabled = True
        # Cash earned during the most recent run: the end-of-run award plus any
        # Cash/Lucky scorer cash paid out during the run (see _award_cash).
        self.last_run_cash_gained = 0
        # Where each dollar of last_run_cash_gained came from: a dict of
        # "base"/"interest"/"score"/"cards"/"scorers" amounts, filled in by
        # _award_cash and shown when the player hovers the shop's cash readout.
        self.last_run_cash_breakdown = {}
        # Cash paid out mid-run by Cash-scorer and Lucky blocks (added to cash
        # at the moment of the trigger). Folded into last_run_cash_gained when
        # the run ends, so retrying undoes it too.
        self.run_cash_gained = 0
        # Resource points banked by Shreds/Rubble/Ideas/Picky scorers. They
        # persist across runs (and saves) and convert into rewards at their
        # thresholds after a run; RETRYING a run resets them all to zero (see
        # _retry_run). (Parts grants a component
        # and Fresh a free reroll immediately, so they bank no points.)
        self.shred_points = 0
        self.rubble_points = 0
        self.idea_points = 0
        # Free shop rerolls granted by Fresh hits (one per Fresh trigger).
        # Using the shop's REFRESH button spends one instead of the cash fee.
        # They persist across runs and saves; RETRYING a run takes back only
        # the rerolls that run itself granted (see free_rerolls_run_gain).
        self.free_rerolls = 0
        # How many of the free rerolls above were granted THIS RUN. A retry is
        # a do-over of the finished run, so those come back off the bank (the
        # rerolls from earlier runs stay); reset with every fresh run.
        self.free_rerolls_run_gain = 0
        self.option_points = 0
        # Bonus shop slots banked by Picky points (every 2 points). Each slot
        # adds one extra random offer (of a uniformly chosen kind) to every
        # shop refresh; the slots are permanent once banked.
        self.bonus_slots = 0
        # Resource points earned THIS RUN. Like the wrecking ball's per-run
        # gain, they only move into the permanent bank — and convert into
        # rewards — after a run; retrying or restarting discards them.
        self.shred_run_gain = 0
        self.rubble_run_gain = 0
        self.idea_run_gain = 0
        self.option_run_gain = 0
        # Permanent per-component purchase counts that drive the duplicate-price
        # increase. They only ever go up — never down when a copy is sold or
        # consumed — so a component's price stays elevated once it has risen.
        self.component_purchases = {}
        # Wrecking Ball (Fragile Breaks) permanent bonuses, one per unit scorer.
        # Every Fragile Breaks card permanently grows its scorer's bonus by 3/4
        # of the base every time a fragile block breaks (+3 mult / +23 chips /
        # x1.19 mult); the bonus persists across runs and is SAVED with the
        # game, applied at the start of each run the card is owned. The xMult
        # bonus is the accumulated multiplicative factor (starts at 1.0).
        self.wrecking_bonus = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                               Scorer.MULT_MUL: 1.0}
        # The Fragile Breaks gains earned THIS RUN (chips/mult add; xMult is a
        # factor starting at 1.0). They apply live to the run but only become
        # permanent (folded into wrecking_bonus) after the run; retrying
        # discards them.
        self.wrecking_run_gain = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                                  Scorer.MULT_MUL: 1.0}
        # Tesseract (the whole card): a permanent, saved xMult bonus that grows
        # by TESSERACT_REROLL_XMULT every time the shop is rerolled while the
        # card is owned. It applies at the start of every run (like the
        # Wrecking Ball bonus), so it is an xMult factor starting at 1.0.
        self.tesseract_bonus = 1.0
        # Spirit tokens: one per Spirit action, each keeping a destroyed
        # block's scorer firing at the start of the runs it still covers.
        self.tokens = []
        # Locked board squares earned by Drill-scorer blocks touched THIS RUN.
        # They unlock (one per Drill trigger) after the run only; retrying
        # discards them (like cash/resource gains).
        self.drill_run_units = 0
        # Blocks destroyed THIS RUN (a fragile block breaking, or a Satanic
        # block dying): the Undertaker scorer pays +15 mult for each of them
        # before its own touch. Bombs and Sharp blocks destroy themselves AFTER
        # a run, so they never count toward it. Reset every run.
        self.run_blocks_destroyed = 0
        # True once a Debt block has triggered THIS RUN: the run then pays no
        # interest (see _award_cash). Reset at the start of every run.
        self.debt_run_triggered = False
        # Fresh block contacts THIS RUN (Rally): every fresh non-role block
        # touch counts (re-touches count); a Rally block subtracts its own.
        self.run_fresh_touches = 0
        # The first WATCH_BLOCK_LIMIT distinct non-role blocks freshly touched
        # THIS RUN, in touch order. Pedestal retriggers the first
        # PEDESTAL_RETRIGGERS of them and Watch lets only these blocks score.
        self.run_first_blocks = []
        # The block freshly touched right before the current one (Echo copies
        # its scorer); None until a second block has been contacted.
        self._prev_contact_block = None
        # Bomb-scorer blocks touched THIS RUN, keyed by their grid cell. They
        # detonate after a run (unlock radius, then destroyed).
        self.bomb_cells = set()
        # Seconds the marble(s) spent airborne THIS RUN (plane card). A marble
        # is in the air when it has no block contact that frame.
        self.air_time = 0.0
        # Strength of the marble-box fire (0..FIRE_MAX_INTENSITY): it grows
        # while the score passes the required score and dies down after the run.
        self.fire_intensity = 0.0
        # Block types the marbles have touched THIS RUN, for the cash award.
        # They reset at the start of every run (see reset_run).
        self.touched_shapes = set()
        self.touched_effects = set()
        self.touched_scorers = set()
        # The first/last block freshly contacted this run: Effective cards on
        # Start/End conditions inspect them (first after the start / last
        # before the finish). Reset at the start of every run (reset_run).
        self._first_contact_block = None
        self._last_contact_block = None
        # The touching marble's airborne streak at the run's last fresh block
        # contact (Airball end-condition cards reward it). Run-scoped.
        self._last_contact_air = 0.0
        # The marble's speed at that last fresh contact (an end-condition Quick
        # card measures the run's final block hit with it). Run-scoped.
        self._last_contact_speed = 0.0
        self.run_time = 0.0
        # Seconds marbles spent being pulled by black holes THIS RUN (astronaut).
        self.black_hole_time = 0.0
        self.shop = Shop(SHOP_COORDS, self)
        # The shop shows this many extra Picky offers on every refresh.
        self.shop.bonus_slots = self.bonus_slots
        self.toolbox = Toolbox(TOOLBOX_COORDS)
        self.assembler = Assembler(ASSEMBLER_COORDS)
        # Bought cards (like Balatro jokers) live in the card area above the
        # toolbox and apply their effects every run while owned.
        self.cards = []
        # Bought actions (one-use power-ups that modify blocks/cards) live in
        # the action area above the toolbox (max MAX_ACTIONS). An action is
        # used by selecting it, picking a block/card subject, and pressing S.
        self.actions = []
        self.selected_action = None
        self.selected_action_subject = None
        # Card builder: selecting an owned Condition component starts card mode,
        # selecting a Scorer while a condition is assigned pairs it up, and
        # pressing S builds the card (assembling condition + scorer, like the
        # block assembler, without a bottom panel).
        self.card_condition = None
        self.card_scorer = None
        self.card_builder_indexes = {}
        # Quick-scorer cards that are armed (their condition was satisfied) and
        # waiting for the marble to hit its NEXT block, so their reward can use
        # that block's impact speed. Cleared at the start and end of each run.
        self.armed_quick = set()
        # Cash earned THIS RUN by Cash-scorer cards. It is not paid out when a
        # card fires: it is folded into the run's end-of-run cash award, so it
        # only sticks after a run (retrying discards it).
        self.card_cash_run_gain = 0
        # The current run's trial (a run plays at most one; the difficulty
        # decides which of a round's runs have one — see _choose_trial) and the
        # blocks/card it affects. The trial is CHOSEN before the run starts (at
        # game start and each time a run advances) so the info box can show it
        # during setup; its effects are applied when the run actually begins.
        # The run being set up at game start is run 0 itself (the run_number a
        # fresh game holds), not the run after the last finished one.
        self._choose_trial(self.run_number)
        self.trial_maxed_blocks = set()
        self.disabled_card = None
        # The deal-breaker trial disables every owned card whose 
        



        # matches one randomly chosen condition. The affected CardItems are
        # resolved at run start (see _apply_trial); cards.py skips them like
        # the Card-cutter's single disabled card.
        self.deal_broken_cards = set()
        # The crumbling trial's chosen fragile blocks (see _apply_trial): a
        # random 1/4 of the placed blocks shatter like real fragile blocks.
        self.trial_fragile_blocks = set()
        # The marble-weight trial rolls heavier or lighter once per run; the
        # factor (2.0 heavy / 0.5 light) scales only effect pushes, not the
        # marble's fall speed.
        self.trial_marble_weight = 1.0
        # The repeats-only trial counts distinct fresh touches per block type
        # (shape/effect/scorer) so only types touched twice contribute to the
        # run's uniqueness score. Reset at the start of each run.
        self.touch_shape_counts = {}
        self.touch_effect_counts = {}
        self.touch_scorer_counts = {}
        # The final boss of the 24th run (a FinalBoss id, or None until the
        # player reaches the last run). Beating it is required to win.
        self.final_boss = None
        # Trials can be disabled (used by tests so a random trial can't
        # interfere with a test's expected run behavior).
        self.trials_enabled = True
        # The toolbox starts with one Start block and one Finish block. They
        # are plain Rect blocks with no effects — exactly the shape and price
        # the shop sells a role block in (see Shop._scorer_offer), so a spare
        # role trades at the same value wherever it came from.
        self.toolbox.add(BlockItem(0, 0, Shape.RECT, Effect.NONE, Scorer.START, 0,
                                   block_price_for(Shape.RECT, [], Scorer.START),
                                   "Start Block", effects=[]))
        self.toolbox.add(BlockItem(0, 1, Shape.RECT, Effect.NONE, Scorer.FINISH, 0,
                                   block_price_for(Shape.RECT, [], Scorer.FINISH),
                                   "Finish Block", effects=[]))
        # The Start and Finish run-role scorers are unlocked automatically:
        # every player owns those two toolbox blocks, so their collection
        # entries are revealed from the very first game.
        collection.discover_component(Component.SCORER, Scorer.START)
        collection.discover_component(Component.SCORER, Scorer.FINISH)
        self.shop_message = ""
        self.shop_message_timer = 0

        self.has_selected = False
        self.selected_toolbox_item = None
        # The exact toolbox cell of the selection, so a duplicated component only
        # highlights the specific cell that was clicked (see draw_toolbox).
        self.selected_toolbox_index = None
        # Map of assigned component -> toolbox cell, for the same reason.
        self.assigned_toolbox_indexes = {}
        self.selected_shape = None  # Shape.RECT
        self.selected_effect = None  # Effect.NONE
        self.selected_scorer = None  # Scorer.CHIPS_ADD
        self.selected_scorer_amount = None  # Scorer.DEFAULT_AMOUNT[Scorer.CHIPS_ADD]
        self.current_block_angle = 0
        self.drawing = False
        self.erasing = False
        self.paused = False
        # The dynamic board: which (col, row) squares of the 10x15 box are
        # playable. A fresh game (see save_system.start_new_game_in_slot) locks
        # the board down to a small centered 2x3 region; a Board Unit bought in
        # the shop unlocks any locked square. reset_game starts fully unlocked
        # as a clean base; loading a save then restores its saved unlocked
        # squares and Board Units (see save_system._load_save_data), while
        # starting a brand-new game locks back down to the 2x3 start.
        self.unlocked_cells = {
            (x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT)}
        # Board Units currently in hand (each buys one unlocked square).
        self.board_units = 0
        # Cached solid-wall blocks covering the locked squares (see
        # _board_wall_blocks); rebuilt only when the locked set changes.
        self._board_walls = []
        self._board_walls_dirty = True
        # Floating score popups spawned by scoring blocks/cards (see
        # ScoreParticle). They are purely cosmetic and clear on a new game.
        self.score_particles = []
        # Shrinking/fading marble trail dots (see TrailParticle), cleared on
        # each new run.
        self.trail_particles = []
        # Compact bottom popups (achievement unlocks, collection discoveries)
        # that slide up from under the screen, hold, then slide back down.
        self.popups = []
        self.collection_scroll = 0

    # ---- Dynamic board: unlock state, walls, and expansion ----

    def _reset_board_to_start(self):
        """Lock the board to its starting centered 2x3 region.

        Called when a brand-new game begins (see save_system.start_new_game_in_slot)
        so every new game starts with only the middle six squares unlocked.
        """
        x0 = (GRID_WIDTH - BOARD_START_WIDTH) // 2
        y0 = (GRID_HEIGHT - BOARD_START_HEIGHT) // 2
        self.unlocked_cells = {
            (x0 + dx, y0 + dy)
            for dx in range(BOARD_START_WIDTH)
            for dy in range(BOARD_START_HEIGHT)}
        self.board_units = 0
        self._board_walls = []
        self._board_walls_dirty = True

    def board_locked(self):
        """True while any board square is still locked (not yet unlocked)."""
        return len(self.unlocked_cells) < GRID_WIDTH * GRID_HEIGHT

    def is_cell_locked(self, x, y):
        """True when the given board square is not yet unlocked."""
        return (x, y) not in self.unlocked_cells

    def _unlock_cell(self, x, y):
        """Unlock one board square; returns True if it had been locked."""
        if (x, y) in self.unlocked_cells:
            return False
        self.unlocked_cells.add((x, y))
        self._board_walls_dirty = True
        return True

    def _locked_adjacent_cells(self):
        """Every locked board square that shares an edge with an unlocked one.

        The frontier the player can expand the board into next: only squares
        touching (up/down/left/right of) an already-unlocked square are
        reachable, matching how Board Units unlock a clicked locked square.
        """
        candidates = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                if (x, y) in self.unlocked_cells:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if (x + dx, y + dy) in self.unlocked_cells:
                        candidates.append((x, y))
                        break
        return candidates

    def _grant_locked_units(self, count, announce=True):
        """Unlock up to ``count`` random locked squares next to an unlocked one.

        The Drill scorer earns two such squares per trigger (granted after a
        run) and the Conquistador card earns four after every run. Returns how
        many squares were actually unlocked (0 when the board is already fully
        unlocked or ``count`` is 0).

        The squares are picked off the frontier (see _locked_adjacent_cells) one
        at a time, so what the caller gets is always ``count`` squares the board
        really gained — but only against the board as it stands HERE. A Bomb
        blast that runs afterwards would cover squares this grant already added,
        which is why _continue_run detonates the bombs first.

        ``announce`` is cleared by _continue_run, which grants every source of
        expansion for the finished run together and reports them in one message
        (see _announce_board_expansion); the sound plays either way.
        """
        if count <= 0:
            return 0
        candidates = self._locked_adjacent_cells()
        random.shuffle(candidates)
        granted = 0
        for x, y in candidates[:count]:
            if self._unlock_cell(x, y):
                granted += 1
        if granted:
            if announce:
                plural = "s" if granted != 1 else ""
                self._set_shop_message(
                    f"Board expanded ({granted} square{plural} unlocked)")
            sounds.play_coin()
        return granted

    def _detonate_bombs(self, announce=True):
        """Detonate Bomb blocks primed this run (called after a run).

        Each bomb unlocks every board unit within 1 cell of it (Chebyshev
        distance, so diagonals count), then destroys itself. Retrying a run
        never detonates a bomb — it only goes off after a run.
        Returns how many board units were newly unlocked.

        ``announce`` is cleared by _continue_run, which reports the finished
        run's whole expansion — bomb blasts and drill/Conquistador grants — in
        one message (see _announce_board_expansion).
        """
        if not self.bomb_cells:
            return 0
        cells = list(self.bomb_cells)
        self.bomb_cells.clear()
        unlocked = 0
        for x, y in cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT
                            and self._unlock_cell(nx, ny)):
                        unlocked += 1
            self.grid.pop((x, y), None)
        if unlocked:
            if announce:
                plural = "s" if unlocked != 1 else ""
                self._set_shop_message(
                    f"Bombs detonated: {unlocked} unit{plural} unlocked")
            sounds.play_coin()
        return unlocked

    def _announce_board_expansion(self, blasted, drilled, conquered):
        """Report every square the finished run unlocked, and where they came from.

        The three sources are Bombs (a fixed 1-cell blast around each primed
        bomb), the Drill scorer (squares banked by its triggers), and the
        Conquistador card. They are granted as one step and reported as one
        message naming each that contributed, because each grant used to
        announce itself on its own — and with a bomb in the run the blast
        always went last, so its message replaced the drill's and a player whose
        drill had just expanded the board was told only about the bomb.
        """
        total = blasted + drilled + conquered
        if not total:
            return
        sources = []
        if blasted:
            sources.append(f"{blasted} from the bomb blast")
        if drilled:
            sources.append(f"{drilled} from the drill")
        if conquered:
            sources.append(f"{conquered} from Conquistador")
        plural = "s" if total != 1 else ""
        detail = f" ({', '.join(sources)})" if sources else ""
        self._set_shop_message(
            f"Board expanded {total} square{plural}{detail}")

    def _board_unit_tile(self):
        """Screen rect of the shop's always-present Board Unit tile."""
        return pygame.Rect(self.shop.rect.x + BOARD_UNIT_COL * GRID_SIZE,
                           self.shop.rect.y + BOARD_UNIT_ROW * GRID_SIZE,
                           GRID_SIZE, GRID_SIZE)

    def _board_wall_blocks(self):
        """The solid wall Blocks covering every locked square (cached).

        The walls are never added to the grid: the physics engine collides the
        marbles against them so the marble stays inside the unlocked region,
        but they are filtered out of all scoring/contact handling (see
        update/_handle_block_contacts). The cache is rebuilt only when the
        unlocked set changes.
        """
        if self._board_walls_dirty:
            origin = (MARBLE_BOX_COORDS[0], MARBLE_BOX_COORDS[1])
            walls = []
            for x in range(GRID_WIDTH):
                for y in range(GRID_HEIGHT):
                    if (x, y) not in self.unlocked_cells:
                        wall = Block(x, y, shape=Shape.RECT, effect=Effect.NONE,
                                     scorer=Scorer.NONE, scorer_amount=0,
                                     origin=origin)
                        wall.is_board_wall = True
                        walls.append(wall)
            self._board_walls = walls
            self._board_walls_dirty = False
        return self._board_walls

    def _simulation_blocks(self):
        """The block list physics collides with this frame.

        While any square is locked, every locked square also acts as a solid
        invisible wall (see _board_wall_blocks) so marbles stay inside the
        unlocked region. When the whole board is unlocked this is just the
        placed blocks, exactly as before.
        """
        if not self.board_locked():
            return list(self.grid.values())
        return list(self.grid.values()) + self._board_wall_blocks()

    def _buy_board_unit(self):
        """Buy one Board Unit (see _board_unit_price): an expansion for any locked square.

        Always available (the shop's fixed Board Unit tile), buyable as many
        times as the player's cash allows. Units in hand are saved/restored
        with the game (see save_system) and only reset when a NEW game starts.
        """
        price = self._board_unit_price()
        if self.cash < price:
            self._set_shop_message(f"Need ${price} for a Board Unit")
            return
        self.cash -= price
        self.board_units += 1
        self._set_shop_message(f"Board Unit ready ({self.board_units} in hand)")
        sounds.play_coin()

    def _board_unit_price(self):
        """The Board Unit price: BOARD_UNIT_PRICE, or the Mineshaft price.

        The Mineshaft whole card makes expanding the board cheaper. The shop's
        Board Unit tile, its price label and every "unlock this square"
        message read this method, so the displayed and charged prices always
        agree.
        """
        if self._has_card(Card.MINESHAFT):
            return MINESHAFT_BOARD_UNIT_PRICE
        return BOARD_UNIT_PRICE

    def _reset_profile_popup(self):
        """Close any profile popup (create/rename/delete/unlock) and reset its fields."""
        self.profile_naming = False
        self.profile_renaming = False
        self.profile_delete_confirm = False
        self.profile_unlock_confirm = False
        self.profile_delete_error = False
        self.profile_name_text = ""

    def _toggle_profile_menu(self):
        """Open/close the expandable profile list (or close the popup)."""
        if self.profile_naming:
            self._reset_profile_popup()
        self.profile_menu_open = not self.profile_menu_open

    def _begin_profile_naming(self):
        """Open the name-entry prompt for a brand-new profile."""
        self._reset_profile_popup()
        self.profile_naming = True
        self.profile_menu_open = False

    def _begin_profile_rename(self):
        """Open the edit popup for the ACTIVE profile: rename it (Enter) or
        delete it (the bottom-left Delete button)."""
        self._reset_profile_popup()
        self.profile_naming = True
        self.profile_renaming = True
        self.profile_name_text = profiles.current_profile()
        self.profile_menu_open = False

    def _cancel_profile_naming(self):
        """Abandon the popup and return to the profile list."""
        self._reset_profile_popup()
        self.profile_menu_open = True

    def _confirm_profile_name(self):
        """Apply the typed name: rename the active profile, or create a new
        one (whichever popup is open)."""
        name = self.profile_name_text.strip()
        if not name:
            return  # a name is required
        if self.profile_renaming:
            profiles.rename_profile(profiles.current_profile(), name)
            self._reset_profile_popup()
            return
        created = profiles.create_profile(name)
        self._switch_profile(created)

    def _request_profile_delete(self):
        """Swap the edit popup's name field for the inline delete confirm."""
        self.profile_delete_confirm = True
        self.profile_delete_error = False  # a fresh attempt hides any old note

    def _confirm_profile_delete(self):
        """Delete the active profile and settle on a remaining one."""
        if not profiles.delete_profile(profiles.current_profile()):
            # The folder could not be removed (a Windows lock or a stubborn
            # read-only folder); keep the confirm open and tell the player so
            # the delete never looks like it worked when it did not.
            self.profile_delete_error = True
            return
        self._reset_profile_popup()
        self.save_slot = None
        self.slot_confirm_index = None
        self.profile_menu_open = False
        self.reset_game()
        self.title_screen = True
        self.achievements_open = False
        self.marble_selecting = False
        self.upgrades_open = False
        self.collection_open = False

    def _request_profile_unlock(self):
        """Swap the edit popup's name field for the unlock-collection confirm."""
        self.profile_unlock_confirm = True

    def _confirm_profile_unlock(self):
        """Reveal every collection entry for the active profile, then disable
        its achievements (no new ones can unlock after this)."""
        self._unlock_entire_collection()
        achievements.disable()
        self._reset_profile_popup()
        self.profile_menu_open = True  # back to the profile list

    def _unlock_entire_collection(self):
        """Discover every entry the COLLECTION tab can show for this profile."""
        for value in Card.ORDER:
            collection.discover_card(value)
        for value in CONDITION_ORDER:
            collection.discover_condition(value)
        for value in Action.ORDER:
            collection.discover_action(value)
        for value in Shape.ORDER:
            collection.discover_component(Component.SHAPE, value)
        for value in Effect.ORDER:
            collection.discover_component(Component.EFFECT, value)
        for value in Scorer.ORDER:
            collection.discover_component(Component.SCORER, value)
        for value in Trial.ORDER:
            collection.discover_trial(value)
        for value in FinalBoss.ORDER:
            collection.discover_final_boss(value)

    def _switch_profile(self, name):
        """Make ``name`` the active profile from the title screen.

        profiles.switch_to re-points save_system / achievements / collection /
        metagame at the new profile's files and resets their caches; here we
        clear any game/slot state that belonged to the old profile.
        """
        profiles.switch_to(name)
        self._reset_profile_popup()
        self.save_slot = None
        self.slot_confirm_index = None
        self.profile_menu_open = False
        self.reset_game()
        self.title_screen = True
        self.achievements_open = False
        self.marble_selecting = False
        self.upgrades_open = False
        self.collection_open = False

    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        grid_x = (mouse_pos[0] - MARBLE_BOX_COORDS[0]) // GRID_SIZE
        grid_y = (mouse_pos[1] - MARBLE_BOX_COORDS[1]) // GRID_SIZE
        inside_grid = (
            MARBLE_BOX_COORDS[0] <= mouse_pos[0] < MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2]
            and MARBLE_BOX_COORDS[1] <= mouse_pos[1] < MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3]
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Autosave the current game to its slot before closing.
                if self.save_slot is not None:
                    self._retry_run()
                    save_system.save_game(self)
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                # F2 works on every screen, and is handled before the per-screen
                # branches so it never also counts as a "post-run" keypress.
                self._toggle_crt_filter()
            elif self.title_screen:
                # The title screen only accepts clicks on a save slot, the
                # ACHIEVEMENTS / UPGRADES / COLLECTION buttons, the bottom-left
                # PROFILE switcher, or QUIT — plus typing while a new profile
                # name is being entered.
                if event.type == pygame.KEYDOWN and self.profile_naming:
                    if self.profile_delete_confirm or self.profile_unlock_confirm:
                        # The inline confirms ignore typing; Esc returns to the
                        # rename field.
                        if event.key == pygame.K_ESCAPE:
                            self.profile_delete_confirm = False
                            self.profile_unlock_confirm = False
                        continue
                    if event.key == pygame.K_RETURN:
                        self._confirm_profile_name()
                    elif event.key == pygame.K_ESCAPE:
                        self._cancel_profile_naming()
                    elif event.key == pygame.K_BACKSPACE:
                        self.profile_name_text = self.profile_name_text[:-1]
                    elif (event.unicode and event.unicode.isprintable()
                            and len(self.profile_name_text) < 40):
                        self.profile_name_text += event.unicode
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.slot_confirm_index is not None:
                        # A slot's LOAD/WIPE panel is open; profile UI is hidden.
                        save_system.handle_slot_click(self, mouse_pos)
                        continue
                    if self.profile_naming:
                        # The edit prompt: Cancel (bottom-right, "Keep" while
                        # confirming), Delete / Unlock (bottom-left, rename mode
                        # only), and the Unlock-collection button (center).
                        if ui.profile_name_cancel_rect().collidepoint(mouse_pos):
                            if self.profile_delete_confirm:
                                self.profile_delete_confirm = False  # keep it
                            elif self.profile_unlock_confirm:
                                self.profile_unlock_confirm = False  # keep it
                            else:
                                self._cancel_profile_naming()
                        elif (self.profile_renaming
                                and ui.profile_name_delete_rect().collidepoint(mouse_pos)):
                            if self.profile_delete_confirm:
                                self._confirm_profile_delete()
                            elif self.profile_unlock_confirm:
                                self._confirm_profile_unlock()
                            else:
                                self._request_profile_delete()
                        elif (self.profile_renaming
                                and not self.profile_delete_confirm
                                and not self.profile_unlock_confirm
                                and ui.profile_name_unlock_rect().collidepoint(mouse_pos)):
                            self._request_profile_unlock()
                        elif PROFILE_BUTTON_RECT.collidepoint(mouse_pos):
                            self._toggle_profile_menu()
                        continue
                    if self.profile_menu_open:
                        _profile_names = profiles.list_profiles()
                        _panel, name_rows, plus = ui.profile_menu_geometry(
                            _profile_names)
                        if PROFILE_BUTTON_RECT.collidepoint(mouse_pos):
                            self._toggle_profile_menu()  # closes the list
                        elif plus.collidepoint(mouse_pos):
                            self._begin_profile_naming()
                        else:
                            picked = None
                            for i, row in enumerate(name_rows):
                                if row.collidepoint(mouse_pos):
                                    picked = i
                                    break
                            if picked is not None:
                                clicked_name = _profile_names[picked]
                                if clicked_name == profiles.current_profile():
                                    # Clicking the ACTIVE profile opens its
                                    # rename/delete popup (it is already
                                    # selected, so nothing to switch to).
                                    self._begin_profile_rename()
                                else:
                                    self._switch_profile(clicked_name)
                            else:
                                # Clicking anywhere else just closes the list.
                                self.profile_menu_open = False
                        continue
                    if PROFILE_BUTTON_RECT.collidepoint(mouse_pos):
                        self._toggle_profile_menu()
                        continue
                    if ACHIEVEMENTS_BUTTON_RECT.collidepoint(mouse_pos):
                        self.achievements_open = True
                        self.title_screen = False
                    elif UPGRADES_BUTTON_RECT.collidepoint(mouse_pos):
                        self.upgrades_open = True
                        self.title_screen = False
                    elif COLLECTION_BUTTON_RECT.collidepoint(mouse_pos):
                        self.collection_open = True
                        self.title_screen = False
                        self.collection_scroll = 0
                    else:
                        save_system.handle_slot_click(self, mouse_pos)
                continue
            elif self.achievements_open:
                # The achievements tab only accepts its return button (or QUIT).
                if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                        and ACHIEVEMENTS_RETURN_BUTTON_RECT.collidepoint(mouse_pos)):
                    self.achievements_open = False
                    self.title_screen = True
                continue
            elif self.marble_selecting:
                # The new-save screen accepts a difficulty button, a marble card
                # (which begins the game with the chosen difficulty), the
                # upgrade toggle, or the BACK button (or QUIT).
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if MARBLE_UPGRADES_TOGGLE_RECT.collidepoint(mouse_pos):
                        self.upgrades_enabled = not self.upgrades_enabled
                    elif MARBLE_BACK_BUTTON_RECT.collidepoint(mouse_pos):
                        self.marble_selecting = False
                        self.save_slot = None
                        self.title_screen = True
                    else:
                        level = self._difficulty_at(mouse_pos)
                        if level is not None:
                            self.difficulty = level
                        else:
                            for i, mt in enumerate(MarbleType.ORDER):
                                if self.marble_card_rect(i).collidepoint(mouse_pos):
                                    save_system.start_new_game_with_marble(self, mt)
                                    break
                continue
            elif self.upgrades_open:
                # The UPGRADES tab accepts buying an upgrade card or the return
                # button (or QUIT).
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if UPGRADES_BACK_BUTTON_RECT.collidepoint(mouse_pos):
                        self.upgrades_open = False
                        self.title_screen = True
                    else:
                        for i, upgrade in enumerate(metagame.UPGRADES):
                            if self.upgrade_card_rect(i).collidepoint(mouse_pos):
                                self._buy_metagame_upgrade(upgrade["id"])
                                break
                continue
            elif self.collection_open:
                # The COLLECTION tab accepts its return button, mouse-wheel
                # scrolling, or QUIT.
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if COLLECTION_BACK_BUTTON_RECT.collidepoint(mouse_pos):
                        self.collection_open = False
                        self.title_screen = True
                elif event.type == pygame.MOUSEWHEEL:
                    self.collection_scroll -= event.y * 40
                continue
            elif event.type == pygame.KEYDOWN:
                # Any key during the post-run state acts as RETRY first (undo
                # the run), then the key's normal action plays out. Y is the
                # CONTINUE key, so it must NOT retry — it moves on instead.
                if (self.run_complete and self.awaiting_after_run
                        and event.key != pygame.K_y):
                    self._retry_run()
                if event.key == pygame.K_a:
                    self.current_block_angle = (self.current_block_angle + 90) % 360
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_r:
                    # Restart the current run, keeping its trial.
                    if self.reset_run():
                        sounds.play_reset()
                    self.run_active = False
                elif event.key == pygame.K_t:
                    # Start a fresh run: exactly one new trial is chosen.
                    if self.reset_run():
                        sounds.play_run_start()
                elif event.key == pygame.K_v:
                    # Move every placed block back to the toolbox instead of
                    # deleting it (erasing each cell refunds it as a block).
                    for (gx, gy) in list(self.grid.keys()):
                        self._erase_block_at(gx, gy)
                    self.marbles = []
                    self.run_active = False
                    self.run_complete = False
                    self.run_cleared = False
                elif event.key == pygame.K_b:
                    # B: sell the selected block or component.
                    self._sell_selected_item()
                elif event.key == pygame.K_s:
                    # S: apply the selected action to its subject, split a
                    # selected splittable card into its halves, build a card
                    # from an assigned condition + scorer, assemble the assigned
                    # toolbox parts into a block (missing parts default to the
                    # free Rect shape / no effect / no scorer), disassemble a
                    # selected block, or — with nothing selected at all — build
                    # the plain default wall.
                    if self.selected_action is not None:
                        self._apply_action()
                    elif (getattr(self.selected_toolbox_item, "kind", None) == "card"):
                        self._disassemble_card()
                    elif self.card_condition is not None:
                        self._build_card()
                    elif self.assembler.has_parts():
                        self._assemble_block()
                    elif isinstance(self.selected_toolbox_item, (Block, BlockItem)):
                        self._disassemble_block()
                    elif self.selected_toolbox_item is None:
                        self._assemble_block()
                    else:
                        self._disassemble_block()
                elif event.key == pygame.K_d:
                    # U: pay cash to raise the selected block's trigger limit.
                    self._upgrade_trigger_limit()
                elif event.key == pygame.K_y:
                    self._continue_run()
                elif event.key == pygame.K_p:
                    # Save the current game to the active save slot.
                    self._retry_run()
                    save_system.save_game(self)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.game_over:
                        if GAME_OVER_MENU_BUTTON_RECT.collidepoint(mouse_pos):
                            self._return_to_main_menu()
                        elif GAME_OVER_NEW_BUTTON_RECT.collidepoint(mouse_pos):
                            # New game acts like wiping the save: clear it and
                            # let the player pick a marble (and upgrade toggle).
                            self.game_over = False
                            self.game_won = False
                            self.game_perfect = False
                            slot = self.save_slot if self.save_slot is not None else 1
                            save_system.begin_new_game_selection(self, slot)
                        elif GAME_OVER_CONTINUE_BUTTON_RECT.collidepoint(mouse_pos):
                            # Keep playing past the game over: the screen won't
                            # show again for this save, and the next run is set
                            # up here (the run that ended never advanced).
                            self._begin_endless_play()
                    else:
                        if RETURN_TO_MENU_BUTTON_RECT.collidepoint(mouse_pos):
                            # Leave the play screen and return to the title screen.
                            self._return_to_main_menu()
                            continue
                        if (self.run_complete and self.awaiting_after_run):
                            self._retry_run()
                        item = self.shop.item_at(mouse_pos)
                        owned = self.toolbox.item_at(mouse_pos)
                        card = self.card_area_item_at(mouse_pos)
                        action = self.action_area_item_at(mouse_pos)
                        grid_block = None
                        if (inside_grid and 0 <= grid_x < GRID_WIDTH
                                and 0 <= grid_y < GRID_HEIGHT):
                            grid_block = self.grid.get((grid_x, grid_y))
                        keep_selection = False
                        if (self.run_complete and self.awaiting_after_run):
                            self._continue_run()
                        elif self._trial_half_at(mouse_pos) is not None:
                            # The trial display is bought from while building:
                            # its left half swaps the trial, its right half
                            # turns it off (see _click_trial_display).
                            keep_selection = True
                            self._click_trial_display(mouse_pos)
                        elif (self.selected_toolbox_item is not None
                                and SELL_OVERLAY_RECT.collidepoint(mouse_pos)):
                            keep_selection = True
                            self._sell_selected_item()
                        elif (self.selected_toolbox_item is not None
                                and isinstance(self.selected_toolbox_item, (Block, BlockItem))
                                and UPGRADE_OVERLAY_RECT.collidepoint(mouse_pos)):
                            keep_selection = True
                            self._upgrade_trigger_limit()
                        elif ACTION_UPGRADE_RECT.collidepoint(mouse_pos):
                            # The action-upgrade button upgrades the selected action.
                            keep_selection = True
                            self._upgrade_action()
                        elif action is not None:
                            # Left-clicking an owned action selects it to apply.
                            keep_selection = True
                            self._select_action(action)
                        elif item is not None:
                            self._buy_shop_item(item)
                        elif self._board_unit_tile().collidepoint(mouse_pos):
                            # The shop's fixed Board Unit tile: buy an expansion
                            # to spend on any locked board square.
                            keep_selection = True
                            self._buy_board_unit()
                        elif self.selected_action is not None:
                            # An action is active: the next block/card click
                            # picks its subject (empty space cancels).
                            keep_selection = True
                            self._pick_action_subject(owned, card, grid_block)
                        elif owned is not None:
                            keep_selection = True
                            if getattr(owned, "kind", None) == "block":
                                self._equip_block(owned, self.toolbox.index_at(mouse_pos))
                            else:
                                self._select_toolbox_component(owned, self.toolbox.index_at(mouse_pos))
                        elif card is not None:
                            # Left-clicking an owned card selects it (B sells it
                            # for half price); clicking another card swaps their
                            # order in the card area (Blueprint copies the card
                            # to its left, so order matters).
                            keep_selection = True
                            selected = self.selected_toolbox_item
                            if (selected is not None
                                    and getattr(selected, "kind", None) == "card"
                                    and selected in self.cards):
                                i = self.cards.index(selected)
                                j = self.cards.index(card)
                                self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
                                self.selected_toolbox_item = card
                                self.selected_toolbox_index = None
                                self._set_shop_message(
                                    f"Swapped {selected.name} and {card.name}")
                            else:
                                self.selected_toolbox_item = card
                                self.selected_toolbox_index = None
                                self.has_selected = False
                        elif SHOP_REFRESH_BUTTON_RECT.collidepoint(mouse_pos):
                            self._refresh_shop()
                        elif grid_block is None and (inside_grid
                                and 0 <= grid_x < GRID_WIDTH
                                and 0 <= grid_y < GRID_HEIGHT
                                and self.is_cell_locked(grid_x, grid_y)):
                            # A click on a locked board square: with a Board
                            # Unit in hand it spends one to unlock the square
                            # (the marble can then travel there); otherwise it
                            # explains what's needed. Building is not allowed on
                            # locked squares, so a selected block just gets a
                            # hint instead of placing.
                            keep_selection = True
                            if self.has_selected:
                                self._set_shop_message(
                                    "Can't build there — square is locked")
                            elif self.board_units > 0:
                                self._unlock_cell(grid_x, grid_y)
                                self.board_units -= 1
                                self._set_shop_message(
                                    f"Square unlocked "
                                    f"({self.board_units} unit(s) left)")
                                sounds.play_mech()
                                # Unlocking edits the board like placing a block:
                                # any active run is reset back to build state.
                                self.reset_run(False)
                                self.run_active = False
                            else:
                                self._set_shop_message(
                                    f"Locked square — buy a Board Unit "
                                    f"(${self._board_unit_price()}) to expand it")
                        elif grid_block is not None and not self.has_selected:
                            keep_selection = True
                            self._select_placed_block(grid_block)
                        else:
                            self.drawing = True
                            keep_selection = inside_grid and self.has_selected
                        if not keep_selection and self.selected_toolbox_item is not None:
                            self._clear_toolbox_selection()
                if event.button == 3 and not self.game_over:
                    # Right-click erases blocks; the info box is hover-driven now.
                    self.erasing = True

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.drawing = False
                elif event.button == 3:
                    self.erasing = False

        if inside_grid \
            and 0 <= grid_x < GRID_WIDTH and 0 <= grid_y < GRID_HEIGHT:
            # Blocks can only be placed (or moved into) unlocked squares.
            if (self.drawing and self.has_selected
                    and not self.is_cell_locked(grid_x, grid_y)):
                item = self.selected_toolbox_item
                moving_placed = isinstance(item, Block)
                old = self.grid.get((grid_x, grid_y))
                if old is not None and not (moving_placed and old is item):
                    self._refund_block(old)
                self.grid[(grid_x, grid_y)] = Block(
                    grid_x,
                    grid_y,
                    shape=self.selected_shape,
                    effect=self.selected_effect,
                    scorer=self.selected_scorer,
                    scorer_amount=self.selected_scorer_amount,
                    angle=self.current_block_angle,
                    portal_number=getattr(item, "portal_number", 0),
                    key_number=getattr(item, "key_number", 0),
                    trigger_limit=getattr(item, "trigger_limit", 1),
                    trigger_paid=getattr(item, "trigger_paid", 0),
                    effects=getattr(item, "effects", None),
                    effect_amounts=self.selected_effect_amounts,
                )
                # The placed block keeps its resale value, so erasing/refunding
                # it later returns the same price (a free, assembled-from-nothing
                # wall is worth $0, not the sum of its default parts), and every
                # later read (Death, Recognition, Painting) sees what the player
                # actually paid instead of re-summing the parts.
                placed = self.grid[(grid_x, grid_y)]
                placed.resale_price = getattr(
                    item, "resale_price", getattr(item, "price", None))
                if placed.resale_price is None:
                    # A block with no stored price of its own (hand-built) gets
                    # one materialized once, so it never drifts afterwards.
                    block_resale_price(placed)
                # A placed portal inherits its partner's trigger count so the
                # pair stays in lockstep (e.g. both exhausted after one use).
                self._sync_portal_pair_triggers(self.grid[(grid_x, grid_y)], list(self.grid.values()))
                sounds.play_plop()
                # A bought block is consumed on placement; an assembled block already
                # consumed its components. Either way, the selection is cleared.
                if item is not None and getattr(item, "kind", None) == "block" and item in self.toolbox.items:
                    self.toolbox.items.remove(item)
                # Moving a placed block removes it from its original cell.
                if moving_placed and (item.x, item.y) != (grid_x, grid_y):
                    self.grid.pop((item.x, item.y), None)
                self.has_selected = False
                self.selected_toolbox_item = None
                self.selected_toolbox_index = None
                self.selected_shape = None
                self.selected_effect = None
                self.selected_scorer = None
                self.selected_scorer_amount = None
                self.selected_effect_amounts = {}
            elif self.erasing:
                self._erase_block_at(grid_x, grid_y)
            if (self.drawing or self.erasing):
                # Building/editing the board keeps the current run's trial.
                self.reset_run(False)
                self.run_active = False

    def _set_scorer(self, scorer):
        self.selected_scorer = scorer
        self.selected_scorer_amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)

    def _set_shop_message(self, text):
        self.shop_message = text
        self.shop_message_timer = SHOP_MESSAGE_DURATION

    def _equip_block(self, item, index=None):
        """Equip a block for placement."""
        self.has_selected = True
        self.selected_toolbox_item = item
        if index is None:
            index = self.toolbox.items.index(item) if item in self.toolbox.items else None
        self.selected_toolbox_index = index
        # Selecting a block switches to block mode: any half-built assembly is
        # dropped so S places/disassembles the block instead of assembling it.
        self.assembler.clear()
        self.assigned_toolbox_indexes.clear()
        # A fragile block that shattered mid-run is stored with its original
        # shape, so moving it comes back as that shape instead of a permanent
        # Shape.NONE.
        self.selected_shape = (item._fragile_shape
                               if getattr(item, "_fragile_shape", None) is not None
                               else item.shape)
        self.selected_effect = item.effect
        self.selected_scorer = item.scorer
        self.selected_scorer_amount = item.scorer_amount
        # The equipped block's own effect strengths travel with the selection,
        # so placing it puts the same piston/black hole/conveyor on the board.
        self.selected_effect_amounts = dict(getattr(item, "effect_amounts", {}))
        self._set_shop_message(f"Selected {self._item_name(item)}")

    def _select_placed_block(self, block):
        """Select a block already placed in the marble box, like a toolbox block."""
        self._clear_toolbox_selection()
        self._equip_block(block)

    def _use_component(self, component):
        """Assign a toolbox component to the assembler.

        The component stays in the toolbox (highlighted green) — it is only
        consumed when a block is actually assembled. Effect components toggle
        on/off so a block can have multiple effects.
        """
        a = self.assembler
        if component.kind == Component.SHAPE:
            a.shape = component
        elif component.kind == Component.SCORER:
            a.scorer = component
        elif component.kind == Component.EFFECT:
            if component in a.effects:
                a.effects.remove(component)
            else:
                a.effects.append(component)
        kind_label = {Component.SHAPE: "Shape", Component.EFFECT: "Effect", Component.SCORER: "Scorer"}[component.kind]
        self._set_shop_message(f"{kind_label}: {component.name} — press S to assemble")

    def _clear_toolbox_selection(self):
        """Deselect the current toolbox item (block or component)."""
        self.has_selected = False
        self.selected_toolbox_item = None
        self.selected_toolbox_index = None
        self.selected_shape = None
        self.selected_effect = None
        self.selected_scorer = None
        self.selected_scorer_amount = None
        self.selected_effect_amounts = {}
        # A deselection also drops any pending card build (assigned condition
        # + scorer highlight in the toolbox until S builds or S clears them).
        self.card_condition = None
        self.card_scorer = None
        self.card_builder_indexes.clear()

    def _select_toolbox_component(self, component, index=None):
        """Select a toolbox component.

        A Condition component starts the card builder (the player then picks a
        card scorer); any other component (shape/effect/scorer) is assigned to
        the block assembler as before. Scorers are shared between the two: a
        Scorer selected while a condition is assigned pairs with the card
        builder instead of the block assembler.
        """
        # Captured before clearing so a scorer can pair with an assigned
        # condition (clearing drops the pending card build).
        pairing_scorer = (component.kind == Component.SCORER
                          and self.card_condition is not None)
        kept_condition = self.card_condition if pairing_scorer else None
        kept_index = (self.card_builder_indexes.get(kept_condition)
                      if kept_condition is not None else None)
        self._clear_toolbox_selection()
        self.selected_toolbox_item = component
        if index is None:
            try:
                index = self.toolbox.items.index(component)
            except ValueError:
                index = None  # not owned by the toolbox; no cell to highlight
        self.selected_toolbox_index = index
        if component.kind == Component.CONDITION:
            # Starting the card builder clears any pending block assembly so S
            # can't mix the two halves.
            self.assembler.clear()
            self.assigned_toolbox_indexes.clear()
            self.card_condition = component
            self.card_scorer = None
            self.card_builder_indexes = {component: index}
            self._set_shop_message(
                f"Condition: {component.name} — now pick a scorer, then press S")
            return
        if pairing_scorer:
            self.card_condition = kept_condition
            self.card_scorer = component
            self.card_builder_indexes = {kept_condition: kept_index, component: index}
            self._set_shop_message(
                f"Scorer: {component.name} — press S to build the card")
            return
        # Block assembly: a shape/effect/scorer click clears the card builder.
        self.card_condition = None
        self.card_scorer = None
        self.card_builder_indexes.clear()
        self._use_component(component)
        # Track the assigned component's cell so draw_toolbox highlights exactly
        # that one, not every copy that shares the same identity.
        a = self.assembler
        if component is a.shape or component is a.scorer or component in a.effects:
            self.assigned_toolbox_indexes[component] = self.selected_toolbox_index
        else:
            self.assigned_toolbox_indexes.pop(component, None)

    def _build_card(self):
        """Combine the assigned condition + scorer into a card (press S).

        Only pairs that describe a real card build (see
        components.condition_scorer_card): collision conditions pair with any
        card scorer, and each named condition recreates its whole card (or, for
        the magnitude conditions, a new custom card). The two components are
        consumed from the toolbox and the card joins the card area.
        """
        condition = self.card_condition
        if condition is None:
            return
        scorer = self.card_scorer
        if scorer is None:
            self._set_shop_message(
                f"Pick a scorer for {condition.name} (then press S)")
            return
        value = condition_scorer_card(condition.value, scorer.value)
        if value is None:
            self._set_shop_message(
                f"{condition.name} + {Scorer.name(scorer.value)} don't form a card")
            return
        # Duplicates are blocked unless the player owns the Showman card.
        # Ownership (not effect) is what matters here: a card disabled for the
        # run is still owned, so it cannot be built a second time.
        if self._owns_card(value) and not self._has_card(Card.SHOWMAN):
            self._set_shop_message("Already own this card")
            return
        if len(self.cards) >= MAX_CARDS:
            self._set_shop_message(f"Card area is full ({MAX_CARDS} cards)")
            return
        # Consume the two halves from the toolbox and clear the builder.
        for c in (condition, scorer):
            if c in self.toolbox.items:
                self.toolbox.items.remove(c)
        self._clear_toolbox_selection()
        # The built card keeps the scorer piece's own magnitude, so building a
        # card is not a way to launder a weak roll into the average card (or the
        # reverse): what the piece pays for is what the card pays.
        self.cards.append(make_card_item(value, amount=scorer.amount))
        self._discover_owned_card(value)
        self._set_shop_message(f"Built card: {Card.name(value)}")
        sounds.play_coin()

    def _assemble_block(self):
        """Combine the assigned toolbox components into a block.

        Uses the assigned shape, scorer, and any toggled effect components (all
        highlighted green in the toolbox), then consumes them into the new
        block, which is added to the toolbox and equipped. A part that is NOT
        assigned becomes its free default — the Rect shape, no effect, or no
        scorer — so any combination of parts (even none at all) assembles: a
        lone +Chips scorer makes a plain Rect +Chips block, and S with nothing
        selected makes a plain wall. A Portal effect or a Key/Lock shape
        assembles a PAIR of blocks (both halves share a fresh pairing number,
        exactly like a bought pair).
        """
        a = self.assembler
        consumed = [c for c in (a.shape, a.scorer, *a.effects) if c is not None]
        # Room check after the assigned components are freed up.
        free = self.toolbox.cols * self.toolbox.rows - (len(self.toolbox.items) - len(consumed))
        # Missing parts become the free defaults: Rect shape, no effect, no scorer.
        effects = [e.value for e in a.effects]
        # Each effect piece carries its own rolled magnitude (a 1350 px/s piston,
        # a 2100 px/s one): the assembled block keeps it, so what the player
        # bought is what the block does.
        amounts = {e.value: e.amount for e in a.effects if getattr(e, "amount", 0)}
        shape = a.shape.value if a.shape is not None else Shape.RECT
        # The other half of a Key/Lock pair (None for every other shape).
        pair_shape = paired_shape(shape)
        needs = 2 if (Effect.PORTAL in effects or pair_shape is not None) else 1
        if free < needs:
            self._set_shop_message("Inventory needs room for the new block")
            return
        scorer = a.scorer.value if a.scorer is not None else Scorer.NONE
        amount = a.scorer.amount if a.scorer is not None else 0
        name = f"{Shape.name(shape)} {Scorer.name(scorer)}"
        price = self._assemble_price(a)
        # Consume the assigned components from the toolbox.
        for c in consumed:
            if c in self.toolbox.items:
                self.toolbox.items.remove(c)
        a.clear()
        self.assigned_toolbox_indexes.clear()
        if Effect.PORTAL in effects:
            # A portal block is assembled as a pair sharing a fresh number.
            number = next_portal_number()
            item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                             portal_number=number, effects=effects,
                             effect_amounts=amounts)
            self.toolbox.add(item)
            self.toolbox.add(BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                                       portal_number=number, effects=effects,
                                       effect_amounts=amounts))
            self._equip_block(item)
            self._set_shop_message(f"Assembled {name} (portal pair #{number})")
            sounds.play_mech()
            return
        if pair_shape is not None:
            # A Key/Lock block is assembled as a matched pair sharing a fresh
            # key number: both halves carry the same effects and scorer, one
            # drawn as the Key and one as the Lock.
            number = next_key_number()
            item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                             key_number=number, effects=effects,
                             effect_amounts=amounts)
            self.toolbox.add(item)
            self.toolbox.add(BlockItem(0, 0, pair_shape, Effect.NONE, scorer, amount, price,
                                       f"{Shape.name(pair_shape)} {Scorer.name(scorer)}",
                                       key_number=number, effects=effects,
                                       effect_amounts=amounts))
            self._discover_component(Component.SHAPE, pair_shape)
            self._equip_block(item)
            self._set_shop_message(f"Assembled {name} (key/lock pair #{number})")
            sounds.play_mech()
            return
        item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount, price, name,
                         effects=effects, effect_amounts=amounts)
        self.toolbox.add(item)
        self._equip_block(item)
        self._set_shop_message(f"Assembled {name}")
        sounds.play_mech()

    def _assemble_price(self, a):
        """The resale value of an assembled block: 75% of its chosen parts.

        Each part is priced at its OWN magnitude, so a block assembled from a
        strong scorer or a fast piston is worth more than the same block at the
        averages. The free defaults (Rect shape, no effect, no scorer) add
        nothing, so a block assembled from nothing is worth $0 and can't be
        sold for profit.
        """
        total = 0
        if a.shape is not None:
            total += COMPONENT_PRICES.get((Component.SHAPE, a.shape.value), 0)
        for e in a.effects:
            total += effect_component_price(e.value, getattr(e, "amount", 0))
        if a.scorer is not None:
            total += scorer_component_price(a.scorer.value, a.scorer.amount)
        return int(total * 0.75)

    def _refund_block(self, block):
        """Return a removed block to the toolbox as a block (not components)."""
        # A fragile block that shattered is stored with its original shape, so
        # erasing/replacing it returns that shape instead of a Shape.NONE.
        shape = block._fragile_shape if getattr(block, "_fragile_shape", None) is not None else block.shape
        name = f"{Shape.name(shape)} {Scorer.name(block.scorer)}"
        # Refund the block's stored resale value (placed blocks carry the price
        # of the toolbox item they came from), so a free default wall stays
        # worth $0 instead of being repriced from its free parts.
        price = block_resale_price(block)
        item = BlockItem(0, 0, shape, Effect.NONE, block.scorer,
                         block.scorer_amount, price, name,
                         portal_number=getattr(block, "portal_number", 0),
                         key_number=getattr(block, "key_number", 0),
                         trigger_limit=getattr(block, "trigger_limit", 1),
                         trigger_paid=getattr(block, "trigger_paid", 0),
                         effects=block.effects,
                         effect_amounts=getattr(block, "effect_amounts", None))
        self.toolbox.add(item)

    def _erase_block_at(self, grid_x, grid_y):
        """Remove a block from the grid and return it to the toolbox as a block."""
        block = self.grid.pop((grid_x, grid_y), None)
        if block is not None:
            self._refund_block(block)
            if block.scorer == Scorer.START:
                # Erasing a start block removes the marble released from it.
                self.marbles = [m for m in self.marbles if getattr(m, "start_block", None) is not block]

    def _record_component_purchases(self, item):
        """Count a purchase toward each component's permanent price.

        Buying a component directly counts that one component; buying a block
        counts every component it is made of (its shape, each effect, and its
        scorer), so buying blocks also pushes up the component prices.
        """
        if getattr(item, "kind", None) == "block":
            keys = [(Component.SHAPE, item.shape)]
            keys += [(Component.EFFECT, e) for e in item.effects]
            keys.append((Component.SCORER, item.scorer))
        else:
            keys = [(item.kind, item.value)]
        for key in keys:
            self.component_purchases[key] = self.component_purchases.get(key, 0) + 1

    def _inflation_factor(self):
        """The inflation trial's price multiplier: 1.5 while active, else 1.0.

        The inflation trial makes everything money-related cost 50% more while
        it is the current trial (it is chosen before the run, so the shop you
        buy from under it is inflated). Gated by trials_enabled so a random
        trial never leaks into non-trial tests.
        """
        if self.trials_enabled and self.current_trial == Trial.INFLATION:
            return 1.5
        return 1.0

    def _inflated(self, amount):
        """``amount`` rounded up to the nearest dollar under the inflation trial."""
        return int(amount * self._inflation_factor() + 0.5)

    def _buy_price(self, item):
        """Effective buy price for a shop item.

        A component's price rises permanently with every purchase of it — both
        direct buys and copies bought inside blocks. The increase is
        diminishing (a square-root curve), so each additional copy adds a
        smaller increment and prices climb more and more slowly. Rarity is
        unaffected: shop generation uses only the base COMPONENT_PRICES. The
        inflation trial raises the final price 50% on top.
        """
        if getattr(item, "kind", None) in ("block", "card", "action"):
            return self._inflated(self._shop_discount(item.price))
        bought = self.component_purchases.get((item.kind, item.value), 0)
        base = self._shop_discount(item.price)
        return self._inflated(int(base * (1 + DUPLICATE_PRICE_INCREMENT * math.sqrt(bought))))

    def _shop_discount(self, amount):
        """A shop price after the Coupon card's discount.

        Coupon takes 25% off every shop OPTION — the components, blocks, cards
        and actions in the shop grid. Board Units are bought through their own
        tile (see _buy_board_unit) and the shop reroll through
        _refresh_shop, so neither is discounted. The inflation trial then
        applies on top (see _inflated).
        """
        if not self._has_card(Card.COUPON):
            return amount
        return int(amount * COUPON_PRICE_FACTOR)

    def _buy_shop_item(self, item):
        price = self._buy_price(item)
        if self.cash < price:
            self._set_shop_message(f"Need ${price} for {item.name}")
            return
        # The ERR 404 card is a joke: it never joins the card area itself —
        # buying it grants a random card instead.
        if getattr(item, "kind", None) == "card" and item.value == Card.ERR_404:
            if len(self.cards) >= MAX_CARDS:
                self._set_shop_message("Card area is full (5 cards)")
                return
            pool = [v for v in prebuilt_card_pool() if v != Card.ERR_404]
            value = random.choice(pool)
            # Duplicates are blocked unless the player owns the Showman card.
            if self._owns_card(value) and not self._has_card(Card.SHOWMAN):
                self._set_shop_message("Already own this card")
                return
            self.cards.append(make_card_item(value))
            self.cash -= price
            self._discover_owned_card(value)
            self._set_shop_message(f"Bought card: {Card.name(value)}")
            sounds.play_coin()
            return
        # A card goes to the card area above the toolbox (max MAX_CARDS), not
        # the toolbox, and doesn't drive component prices.
        if getattr(item, "kind", None) == "card":
            if len(self.cards) >= MAX_CARDS:
                self._set_shop_message("Card area is full (5 cards)")
                return
            # Duplicates are blocked unless the player owns the Showman card.
            if self._owns_card(item.value) and not self._has_card(Card.SHOWMAN):
                self._set_shop_message("Already own this card")
                return
            self.cards.append(item)
            self.cash -= price
            self._discover_owned_card(item.value)
            self._set_shop_message(f"Bought card: {item.name}")
            sounds.play_coin()
            return
        # An action goes to the action area above the toolbox (max
        # MAX_ACTIONS) and doesn't drive component prices.
        if getattr(item, "kind", None) == "action":
            if len(self.actions) >= MAX_ACTIONS:
                self._set_shop_message("Action area is full (2 actions)")
                return
            self.actions.append(item)
            self.cash -= price
            self._discover_action(item.value)
            self._set_shop_message(f"Bought action: {self._item_name(item)}")
            sounds.play_coin()
            return
        # A portal block is bought as a pair: two identical blocks that share a
        # fresh pairing number (they teleport marbles between each other).
        if getattr(item, "kind", None) == "block" and item.has_effect(Effect.PORTAL):
            if len(self.toolbox.items) + 2 > self.toolbox.cols * self.toolbox.rows:
                self._set_shop_message("Inventory needs room for the portal pair")
                return
            number = next_portal_number()
            self.toolbox.add(BlockItem(0, 0, item.shape, Effect.NONE, item.scorer,
                                       item.scorer_amount, item.price, item.name, portal_number=number,
                                       effects=item.effects,
                                       effect_amounts=getattr(item, "effect_amounts", None)))
            self.toolbox.add(BlockItem(0, 0, item.shape, Effect.NONE, item.scorer,
                                       item.scorer_amount, item.price, item.name, portal_number=number,
                                       effects=item.effects,
                                       effect_amounts=getattr(item, "effect_amounts", None)))
            self._record_component_purchases(item)
            self._discover_block(item)
            self.cash -= price
            self._set_shop_message(f"Bought {item.name} (portal pair #{number})")
            sounds.play_coin()
            return
        # A Key/Lock block is bought as a matched pair too: the bought half keeps
        # its shape and its partner half is the other shape, sharing a fresh key
        # number. Both halves keep the offer's effects and scorer.
        pair_shape = paired_shape(getattr(item, "shape", None))
        if getattr(item, "kind", None) == "block" and pair_shape is not None:
            if len(self.toolbox.items) + 2 > self.toolbox.cols * self.toolbox.rows:
                self._set_shop_message("Inventory needs room for the key/lock pair")
                return
            number = next_key_number()
            self.toolbox.add(BlockItem(0, 0, item.shape, Effect.NONE, item.scorer,
                                       item.scorer_amount, item.price, item.name,
                                       key_number=number, effects=item.effects,
                                       effect_amounts=getattr(item, "effect_amounts", None)))
            self.toolbox.add(BlockItem(0, 0, pair_shape, Effect.NONE, item.scorer,
                                       item.scorer_amount, item.price,
                                       f"{Shape.name(pair_shape)} {Scorer.name(item.scorer)}",
                                       key_number=number, effects=item.effects,
                                       effect_amounts=getattr(item, "effect_amounts", None)))
            self._record_component_purchases(item)
            self._discover_block(item)
            self._discover_component(Component.SHAPE, pair_shape)
            self.cash -= price
            self._set_shop_message(f"Bought {item.name} (key/lock pair #{number})")
            sounds.play_coin()
            return
        if not self.toolbox.add(item):
            self._set_shop_message("Inventory is full")
            return
        self._record_component_purchases(item)
        if getattr(item, "kind", None) == "block":
            self._discover_block(item)
        else:
            self._discover_component(item.kind, item.value)
        self.cash -= price
        self._set_shop_message(f"Bought {item.name}")
        sounds.play_coin()

    def _discover_component(self, kind, value):
        """Discover a component in the collection; pop it up if it's new."""
        if kind == Component.CONDITION:
            self._discover_condition(value)
            return
        if not collection.discover_component(kind, value):
            return
        if kind == Component.SHAPE:
            name, category = Shape.name(value), "shape"
        elif kind == Component.EFFECT:
            name, category = Effect.name(value), "effect"
        else:
            name, category = Scorer.name(value), "scorer"
        self._push_popup(f"New {category}", name, (120, 200, 255))

    def _discover_condition(self, value):
        """Discover a condition in the collection; pop it up if it's new."""
        if collection.discover_condition(value):
            self._push_popup("New condition", Condition.name(value), (140, 190, 190))

    def _discover_owned_card(self, value):
        """Discover a whole bought/built card.

        Splittable cards aren't in the collection (they're buildable), so
        obtaining one reveals its two halves instead: the condition and the
        scorer. The indivisible cards (Showman / Blueprint / ERR 404) reveal
        themselves as cards.
        """
        parts = splittable_card_condition_scorer(value)
        if parts is None:
            meta = generic_card_meta(value)
            if meta is not None:
                parts = meta
        if parts is None:
            self._discover_card(value)
            return
        condition, scorer = parts
        self._discover_condition(condition)
        self._discover_component(Component.SCORER, scorer)

    def _discover_block(self, item):
        """Discover every component that makes up a bought block."""
        self._discover_component(Component.SHAPE, item.shape)
        for effect in item.effects:
            self._discover_component(Component.EFFECT, effect)
        self._discover_component(Component.SCORER, item.scorer)

    def _discover_card(self, value):
        """Discover a bought card in the collection; pop it up if new."""
        if collection.discover_card(value):
            self._push_popup("New card", Card.name(value), (255, 200, 80))

    def _discover_action(self, value):
        """Discover a bought action in the collection; pop it up if new."""
        if collection.discover_action(value):
            self._push_popup("New action", Action.name(value), (200, 120, 255))

    def _discover_trial(self, trial):
        """Discover a beaten trial in the collection; pop it up if new."""
        if collection.discover_trial(trial):
            self._push_popup("New trial", Trial.name(trial), (180, 120, 255))

    def _discover_final_boss(self, boss):
        """Discover a beaten final boss in the collection; pop it up if new."""
        if collection.discover_final_boss(boss):
            self._push_popup("Final boss beaten", FinalBoss.name(boss), (255, 140, 0))

    def _trigger_upgrade_cost(self, item):
        """Cash to raise a block's trigger limit by one.

        The upgrade is priced off the block's SCORER: it costs
        TRIGGER_UPGRADE_MARKUP (10%) more than buying that scorer component from
        the shop right now, so it follows the scorer's duplicate-price rise, the
        Coupon discount and the inflation trial exactly as that purchase would.
        Upgrading also COUNTS as a purchase of the scorer (see
        _upgrade_trigger_limit), so the next upgrade — and the scorer's shop
        price — climb by the usual duplicate-price step.
        """
        component = Component.scorer_component(
            getattr(item, "scorer", Scorer.NONE),
            amount=getattr(item, "scorer_amount", 0))
        return int(self._buy_price(component) * TRIGGER_UPGRADE_MARKUP)

    def _sync_portal_pair_limits(self, item):
        """Give a portal's partner the same (upgraded) trigger limit.

        Portal pairs share a trigger count, so their limits must stay in step;
        the upgrade is charged once on the selected portal.
        """
        if not getattr(item, "has_effect", lambda e: False)(Effect.PORTAL):
            return
        number = getattr(item, "portal_number", 0)
        if not number:
            return
        for other in list(self.toolbox.items) + self.grid.values():
            if other is not item and getattr(other, "portal_number", 0) == number:
                other.trigger_limit = item.trigger_limit
                return

    def _upgrade_trigger_limit(self):
        """Pay cash to raise the selected block's trigger limit by one.

        The cost grows with the current limit and with the block's total cost.
        The cash paid is tracked on the block and refunded when it is sold.
        """
        item = self.selected_toolbox_item
        if item is None or not isinstance(item, (Block, BlockItem)):
            self._set_shop_message("Select a block to upgrade")
            return
        cost = self._trigger_upgrade_cost(item)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to upgrade the trigger")
            return
        self.cash -= cost
        item.trigger_limit += 1
        item.trigger_paid += cost
        # The upgrade counts as one purchase of the block's scorer, so that
        # scorer's shop price (and therefore the next upgrade) climbs by the
        # same duplicate-price step a real purchase causes.
        self._record_component_purchases(
            Component.scorer_component(item.scorer,
                                       amount=getattr(item, "scorer_amount", 0)))
        self._sync_portal_pair_limits(item)
        self._set_shop_message(f"Trigger limit now {item.trigger_limit} (${cost})")

    def _item_name(self, item):
        """A display name for a shop/toolbox item or a placed block.

        Blocks are named by their parts: every real effect, then the shape,
        then the scorer, then "v<trigger limit>" — e.g. a slippery, fragile
        pipe that grants +chips twice per run reads "Slippery Fragile Pipe
        +Chips v2". An upgraded (v2) action carries its version the same way,
        so "Death v2" is what every message about it calls it; a plain v1
        action stays just "Death".
        """
        if item is CASH_BREAKDOWN:
            return "Last run cash gained"
        if isinstance(item, Block) or getattr(item, "kind", None) == "block":
            effects = " ".join(Effect.name(e) for e in item.effects if e != Effect.NONE)
            parts = ([effects, Shape.name(item.shape), Scorer.name(item.scorer)] if effects
                     else [Shape.name(item.shape), Scorer.name(item.scorer)])
            limit = getattr(item, "trigger_limit", 1)
            return f"{' '.join(parts)} v{limit}"
        name = getattr(item, "name", "")
        if getattr(item, "kind", None) == "action" and name:
            version = getattr(item, "version", 1)
            return f"{name} v{version}" if version >= 2 else name
        if name:
            return name
        return f"{Shape.name(item.shape)} {Scorer.name(item.scorer)}"

    def card_area_item_at(self, pos):
        """Return the owned card at a screen position, or None."""
        x, y = CARD_AREA_COORDS[0], CARD_AREA_COORDS[1]
        if not (x <= pos[0] < x + MAX_CARDS * GRID_SIZE and y <= pos[1] < y + GRID_SIZE):
            return None
        index = (pos[0] - x) // GRID_SIZE
        if 0 <= index < len(self.cards):
            return self.cards[index]
        return None

    def _card_disabled(self, card):
        """True when a card is disabled for this run.

        The Card cutter trial disables one random owned card and the Deal
        breaker trial disables every card of one random condition (see
        _apply_trial). A disabled card is treated as if it were not owned at
        all, so BOTH its start-of-run score effect (cards.py) and every passive
        whole-card effect it drives (_has_card) stop for the run. The state is
        cleared when the run advances (see _continue_run), so building, buying
        and selling between runs are never affected.
        """
        if card is None:
            return False
        if card is self.disabled_card:
            return True
        return card in getattr(self, "deal_broken_cards", ())

    def _owns_card(self, value):
        """True when the player owns a card of this value, disabled or not.

        Ownership is what the duplicate rules care about (you may not own two
        of the same card), so this deliberately ignores the run's disabled
        cards — unlike _has_card, which asks whether a card's effect applies.
        """
        return any(c.value == value for c in self.cards)

    def _has_card(self, value):
        """True when an owned card's EFFECT applies right now (e.g. Showman).

        A card disabled for the run (Card cutter / Deal breaker) counts as not
        owned, so every passive whole-card effect it drives — Coupon's discount,
        Market's resale, Inferno's exponent, Watch's auto-finish, ... — stops
        with it. Use _owns_card when the question is ownership, not effect.
        """
        return any(c.value == value and not self._card_disabled(c)
                   for c in self.cards)

    def action_area_item_at(self, pos):
        """Return the owned action at a screen position, or None."""
        x, y = ACTION_AREA_COORDS[0], ACTION_AREA_COORDS[1]
        if not (x <= pos[0] < x + MAX_ACTIONS * GRID_SIZE
                and y <= pos[1] < y + GRID_SIZE):
            return None
        index = (pos[0] - x) // GRID_SIZE
        if 0 <= index < len(self.actions):
            return self.actions[index]
        return None

    def _select_action(self, action):
        """Select an owned action; the next block/card click picks its subject."""
        self._clear_toolbox_selection()
        self.selected_action = action
        self.selected_action_subject = None
        self._set_shop_message(
            f"{action.name} (v{action.version}) — click a target block/card")

    def _pick_action_subject(self, owned, card, grid_block):
        """Designate the clicked block/card as the active action's subject."""
        if card is not None:
            self.selected_action_subject = card
            self._set_shop_message(f"Target: {card.name}")
            return
        if owned is not None:
            if getattr(owned, "kind", None) == "block":
                self.selected_action_subject = owned
                self._set_shop_message(f"Target: {self._item_name(owned)}")
            else:
                self._set_shop_message("Action target must be a block or card")
            return
        if grid_block is not None:
            self.selected_action_subject = grid_block
            self._set_shop_message(f"Target: {self._item_name(grid_block)}")
            return
        # Clicking empty space cancels the active action.
        self._clear_action_selection()
        self._set_shop_message("Action canceled")

    def _clear_action_selection(self):
        """Deselect the current action and its subject."""
        self.selected_action = None
        self.selected_action_subject = None

    def _apply_action(self):
        """Apply the selected action to its subject (the S key).

        Using an action consumes it. Returns True when it was applied.
        """
        action = self.selected_action
        if action is None or action not in self.actions:
            self._set_shop_message("Select an action first")
            return False
        subject = self.selected_action_subject
        if subject is None:
            self._set_shop_message("Select a target block or card first")
            return False
        applied = False
        if action.value == Action.DEATH:
            applied = self._action_death(action, subject)
        elif action.value == Action.RECOGNITION:
            applied = self._action_recognition(action, subject)
        elif action.value == Action.DEJA_VU:
            applied = self._action_deja_vu(action, subject)
        elif action.value == Action.ANOINTMENT:
            applied = self._action_anointment(action, subject)
        elif action.value == Action.STRENGTH:
            applied = self._action_strength(action, subject)
        elif action.value == Action.SPIRIT:
            applied = self._action_spirit(action, subject)
        else:
            self._set_shop_message("That action does nothing yet")
            return False
        if applied:
            self.actions.remove(action)
            self._clear_action_selection()
        return applied

    def _action_death(self, action, subject):
        """Death sells a chosen block or card for 1.5x (v1) / 6x (v2) its price."""
        if self._unsellable(subject):
            self._set_shop_message("Your last Start or Finish block can't be sold")
            return False
        multiplier = 6 if action.version >= 2 else 1.5
        if getattr(subject, "kind", None) == "card":
            if subject not in self.cards:
                self._set_shop_message("Action target is not owned")
                return False
            gained = int(subject.price * multiplier)
            self.cards.remove(subject)
            self.cash += gained
            self._set_shop_message(f"{action.name} sold {subject.name} for ${gained}")
            sounds.play_coin()
            return True
        if isinstance(subject, Block):
            # A placed block sells for its own stored price (what it was placed
            # with), never a recount of its parts.
            gained = int(block_resale_price(subject) * multiplier)
            self.grid.pop((subject.x, subject.y), None)
            if subject.scorer == Scorer.START:
                self.marbles = [m for m in self.marbles
                                if getattr(m, "start_block", None) is not subject]
            self._delete_pairing_partners(subject)
            self.cash += gained
            self._set_shop_message(f"{action.name} sold {self._item_name(subject)} for ${gained}")
            sounds.play_coin()
            return True
        if subject not in self.toolbox.items:
            self._set_shop_message("Action target is not owned")
            return False
        gained = int(subject.price * multiplier)
        self.toolbox.items.remove(subject)
        self.assigned_toolbox_indexes.pop(subject, None)
        self._delete_pairing_partners(subject)
        self.cash += gained
        self._set_shop_message(f"{action.name} sold {self._item_name(subject)} for ${gained}")
        sounds.play_coin()
        return True

    def _action_recognition(self, action, subject):
        """Recognition duplicates a block (v1) or a card (v2) for its cost."""
        if action.version >= 2:
            # v2: duplicate a card.
            if getattr(subject, "kind", None) != "card" or subject not in self.cards:
                self._set_shop_message("v2 Recognition targets an owned card")
                return False
            if len(self.cards) >= MAX_CARDS:
                self._set_shop_message("Card area is full (5 cards)")
                return False
            if self.cash < subject.price:
                self._set_shop_message(f"Need ${subject.price} to duplicate {subject.name}")
                return False
            self.cards.append(make_card_item(subject.value,
                                            amount=getattr(subject, "amount", 0)))
            self.cash -= subject.price
            self._set_shop_message(f"Recognized a copy of {subject.name} (${subject.price})")
            sounds.play_coin()
            return True
        # v1: duplicate a block.
        if getattr(subject, "kind", None) == "card":
            self._set_shop_message("v1 Recognition targets a block")
            return False
        if isinstance(subject, Block):
            # A placed block is duplicated for its own stored price, matching
            # what the player paid for it (see block_resale_price).
            price = block_resale_price(subject)
            copy = BlockItem(0, 0, subject.shape, Effect.NONE, subject.scorer,
                             subject.scorer_amount, price,
                             f"{Shape.name(subject.shape)} {Scorer.name(subject.scorer)}",
                             portal_number=getattr(subject, "portal_number", 0),
                             key_number=getattr(subject, "key_number", 0),
                             trigger_limit=getattr(subject, "trigger_limit", 1),
                             trigger_paid=getattr(subject, "trigger_paid", 0),
                             effects=subject.effects,
                             effect_amounts=getattr(subject, "effect_amounts", None))
        else:
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
            price = subject.price
            copy = BlockItem(0, 0, subject.shape, Effect.NONE, subject.scorer,
                             subject.scorer_amount, subject.price, subject.name,
                             portal_number=getattr(subject, "portal_number", 0),
                             key_number=getattr(subject, "key_number", 0),
                             trigger_limit=getattr(subject, "trigger_limit", 1),
                             trigger_paid=getattr(subject, "trigger_paid", 0),
                             effects=subject.effects)
        if self.cash < price:
            self._set_shop_message(f"Need ${price} to duplicate this block")
            return False
        if not self.toolbox.add(copy):
            self._set_shop_message("Inventory is full")
            return False
        self.cash -= price
        self._set_shop_message(f"Recognized a copy of {self._item_name(subject)} (${price})")
        sounds.play_coin()
        return True

    def _action_deja_vu(self, action, subject):
        """Deja Vu gives a chosen block more triggers: +1 (v1) or +100 (v2).

        The trigger limit is raised like a paid upgrade, but no cash is paid,
        so nothing is added to the block's refundable trigger_paid. A block on
        the BOARD also gains the extra triggers right now (so the action can
        revive a block that has already spent its triggers), while a toolbox
        block takes the new limit with it when it is placed. Blocks that never
        spend a trigger are refused: the run roles (they score for free every
        time) and a block with no scorer (which has no payoff to trigger), so
        the action is never wasted.
        """
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Deja Vu targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("Role blocks never spend triggers")
            return False
        if subject.scorer == Scorer.NONE:
            self._set_shop_message("That block has no scorer to trigger")
            return False
        gained = 100 if action.version >= 2 else 1
        subject.trigger_limit += gained
        if isinstance(subject, Block):
            subject.triggers_left += gained
        self._add_portal_pair_triggers(subject, gained)
        self._set_shop_message(
            f"{action.name} gave {self._item_name(subject)} +{gained} triggers "
            f"(now {subject.trigger_limit})")
        return True

    def _add_portal_pair_triggers(self, block, amount):
        """Give a portal's partner the same extra triggers (and its new limit).

        A portal pair shares one trigger count, so a Deja Vu upgrade on one
        half has to reach the other half too: otherwise the next contact would
        sync both halves back down to the lower count and waste the upgrade.
        The partner may be unplaced (a toolbox block, which has no trigger
        count of its own yet), so only its limit is carried over then.
        """
        if not getattr(block, "has_effect", lambda e: False)(Effect.PORTAL):
            return
        number = getattr(block, "portal_number", 0)
        if not number:
            return
        for other in list(self.toolbox.items) + list(self.grid.values()):
            if other is block or getattr(other, "portal_number", 0) != number:
                continue
            other.trigger_limit = block.trigger_limit
            if hasattr(other, "triggers_left"):
                other.triggers_left += amount
            return

    def _enchant_block(self, item, effect):
        """Give a block one extra effect and reprice it for the new part.

        The effect arrives with its own rolled magnitude (see
        roll_effect_magnitude), and the block is repriced for what that
        magnitude is worth, so the block's resale value (what a sale, a Death
        action, and the Painting condition read) keeps matching what the block
        is made of.
        """
        item.effects.append(effect)
        magnitude = roll_effect_magnitude(effect)
        if magnitude:
            item.effect_amounts[effect] = magnitude
        added = effect_component_price(effect, magnitude)
        for attr in ("price", "resale_price"):
            if hasattr(item, attr):
                setattr(item, attr, getattr(item, attr) + added)

    def _random_new_effects(self, item, count):
        """``count`` random real effects the block does not already have."""
        pool = [e for e in Effect.REAL_ORDER
                if e != Effect.PORTAL and e not in item.effects]
        random.shuffle(pool)
        return pool[:count]

    def _action_anointment(self, action, subject):
        """Anointment adds random effects: 2 to one block (v1), 1 to each (v2).

        A Portal is never handed out (a lone portal is inert), and the Start
        and Finish roles are skipped: their faces ignore effects entirely, so
        blessing them would only waste the action. v2 covers every block on
        the board AND in the inventory, so it needs no single good target.
        """
        if action.version >= 2:
            targets = [b for b in self.grid.values()
                       if b.scorer not in (Scorer.START, Scorer.FINISH)]
            targets += [i for i in self.toolbox.items
                        if getattr(i, "kind", None) == "block"
                        and i.scorer not in (Scorer.START, Scorer.FINISH)]
            blessed = 0
            for target in targets:
                effects = self._random_new_effects(target, 1)
                if effects:
                    self._enchant_block(target, effects[0])
                    blessed += 1
            if not blessed:
                self._set_shop_message("No block could be blessed")
                return False
            self._set_shop_message(
                f"{action.name} blessed {blessed} block"
                f"{'s' if blessed != 1 else ''}")
            sounds.play_mech()
            return True
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Anointment targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("Role blocks keep a plain Rect")
            return False
        effects = self._random_new_effects(subject, 2)
        if not effects:
            self._set_shop_message("That block already has every effect")
            return False
        for effect in effects:
            self._enchant_block(subject, effect)
        self._set_shop_message(
            f"{action.name} gave {self._item_name(subject)} "
            f"{', '.join(Effect.name(e) for e in effects)}")
        sounds.play_mech()
        return True

    def _action_strength(self, action, subject):
        """Strength raises a block's scorer amount: +50% (v1) or x3 (v2).

        Whole-number amounts stay whole (+4 mult -> +6) and fractional ones stay
        fractional (xMult 1.5 -> 2.25), so the scorer keeps its kind. Blocks
        with nothing to strengthen are refused: the roles (which pay nothing)
        and a scorerless block (whose amount is never read).
        """
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Strength targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("Role blocks have no scorer to strengthen")
            return False
        if subject.scorer == Scorer.NONE:
            self._set_shop_message("That block has no scorer to strengthen")
            return False
        amount = subject.scorer_amount
        factor = 3.0 if action.version >= 2 else 1.5
        raised = amount * factor
        if isinstance(amount, int):
            raised = int(raised + 0.5)
        subject.scorer_amount = raised
        self._set_shop_message(
            f"{action.name} raised {self._item_name(subject)} to "
            f"{self._particle_amount_text(raised)}")
        sounds.play_mech()
        return True

    def _action_spirit(self, action, subject):
        """Spirit destroys a block and keeps its scorer firing for later runs.

        The block is removed and a token is added (see ScorerToken) that fires
        that scorer at the start of each run: the next 2 runs for v1, every run
        for v2. Nothing is paid out now, so the block is not "sold" — it is
        sacrificed. The roles are refused (destroying a Start block would end
        the game) and so is a scorerless block (there is nothing to keep).
        """
        if isinstance(subject, Block):
            if self.grid.get((subject.x, subject.y)) is not subject:
                self._set_shop_message("Action target is not on the board")
                return False
        elif getattr(subject, "kind", None) == "block":
            if subject not in self.toolbox.items:
                self._set_shop_message("Action target is not owned")
                return False
        else:
            self._set_shop_message("Spirit targets a block")
            return False
        if subject.scorer in (Scorer.START, Scorer.FINISH):
            self._set_shop_message("The run roles can't be sacrificed")
            return False
        if subject.scorer == Scorer.NONE:
            self._set_shop_message("That block has no scorer to keep")
            return False
        if len(self.tokens) >= MAX_TOKENS:
            self._set_shop_message(
                f"Token slots are full ({MAX_TOKENS}) — use one first")
            return False
        name = self._item_name(subject)
        runs_left = None if action.version >= 2 else 2
        # A block still in the inventory never stood anywhere, so its token
        # keeps the least generous cell: the bottom row of the first column.
        token = ScorerToken(subject.scorer, subject.scorer_amount,
                            shape=block_shape(subject), effects=subject.effects,
                            x=getattr(subject, "x", 0),
                            y=getattr(subject, "y", GRID_HEIGHT - 1),
                            runs_left=runs_left)
        # Remove the sacrificed block exactly like a sale/erase would (a placed
        # block leaves the board; a Start block's marble is gone with it).
        if isinstance(subject, Block):
            self.grid.pop((subject.x, subject.y), None)
            if subject.scorer == Scorer.START:
                self.marbles = [m for m in self.marbles
                                if getattr(m, "start_block", None) is not subject]
        else:
            self.toolbox.items.remove(subject)
            self.assigned_toolbox_indexes.pop(subject, None)
        self._delete_pairing_partners(subject)
        self.tokens.append(token)
        left = "permanently" if runs_left is None else f"for {runs_left} run(s)"
        self._set_shop_message(
            f"{action.name} kept {Scorer.name(token.scorer)} from {name} {left}")
        sounds.play_mech()
        return True

    def _token_block(self, token):
        """A throwaway Block standing in for a token, for the scorer code.

        Firing a token reuses the block scorer path, so board-relative payoffs
        read the cell the sacrificed block stood in, and the token is marked so
        the Watch card does not treat it as a marble-touched block.
        """
        block = Block(token.x, token.y, shape=token.shape, effect=Effect.NONE,
                      scorer=token.scorer, scorer_amount=token.scorer_amount,
                      effects=token.effects)
        block.is_token = True
        return block

    def _apply_tokens(self):
        """Fire every Spirit token's scorer once, at the start of a run."""
        if not self.tokens or not self.marbles:
            return
        marble = self.marbles[0]
        for token in list(self.tokens):
            block = self._token_block(token)
            token.fired = True
            # A token with nothing to fire is skipped silently (a Random/Lucky
            # token still needs its pre-rolled result, which is drawn here).
            if token.scorer in (Scorer.LUCKY, Scorer.RANDOM):
                self._set_run_random_result(token, token.scorer)
            self._apply_block_score_effect(marble, block)
            self._spawn_token_particle(token, block)

    def _spawn_token_particle(self, token, block):
        """Pop the token's chip as it fires (so a run start shows it working)."""
        rect = self._token_rect(self.tokens.index(token)) if token in self.tokens else None
        text = self._particle_amount_text(token.scorer_amount)
        if text in ("0", ""):
            text = token.name
        if rect is None:
            self._spawn_block_particle(block, text, Scorer.color(token.scorer))
        else:
            self._spawn_score_particle(rect.centerx, rect.centery, text,
                                       Scorer.color(token.scorer))

    def _token_rect(self, index):
        """Screen rect of the token chip at a slot index (see TOKEN_COORDS)."""
        return pygame.Rect(TOKEN_COORDS[0], TOKEN_COORDS[1] + index * GRID_SIZE,
                           GRID_SIZE, GRID_SIZE)

    def token_at(self, pos):
        """Return the token chip at a screen position, or None."""
        for i, token in enumerate(self.tokens):
            if self._token_rect(i).collidepoint(pos):
                return token
        return None

    def _advance_tokens(self):
        """Spend one run from each Spirit token and drop the expired ones.

        Called after a finished run. A token that did not fire this run keeps
        all of its runs (one created mid-run had nothing to fire for), and the
        scorer's own self-destruction rules apply: a Satanic token dies with
        its scorer after a single run, and a Sharp token has the same 1/4
        chance to be destroyed that a Sharp block or card has.
        """
        kept = []
        for token in self.tokens:
            if not token.fired:
                kept.append(token)
                continue
            token.fired = False
            if token.scorer == Scorer.SATANIC:
                continue  # the scorer destroys itself after a run
            if token.scorer == Scorer.SHARP and random.random() < 0.25:
                continue  # the scorer's 1/4 self-destruction rule
            if token.runs_left is not None:
                token.runs_left -= 1
                if token.runs_left <= 0:
                    continue
            kept.append(token)
        self.tokens = kept

    def _upgrade_action(self):
        """Upgrade the selected action to v2 for ACTION_UPGRADE_COST."""
        action = self.selected_action
        if action is None or action not in self.actions:
            self._set_shop_message("Select an action to upgrade")
            return
        if action.version >= 2:
            self._set_shop_message(f"{action.name} is already v2")
            return
        cost = self._inflated(ACTION_UPGRADE_COST)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to upgrade")
            return
        self.cash -= cost
        action.version = 2
        self._set_shop_message(f"{action.name} upgraded to v2 (${cost})")

    def _sell_fraction(self):
        """The fraction of an item's price a plain sale refunds.

        Half normally; the Market whole card raises it to 75%. The Death action
        has its own multipliers (1.5x / 6x) and deliberately does not read this.
        """
        return MARKET_SELL_FRACTION if self._has_card(Card.MARKET) else 0.5

    def _sell_price(self, item):
        """The cash a plain sale refunds for an item (its price x _sell_fraction)."""
        return int(item.price * self._sell_fraction())

    def _role_blocks_owned(self, scorer):
        """How many Start (or Finish) roles of a kind the player could still field.

        Counts the role blocks on the board and in the toolbox plus the
        matching role SCORER components (the same thing taken apart, and the
        only thing the assembler can build another role block from). A spare
        role is worth one of these; the last one must never be sold, because
        the shop is not guaranteed to offer another and a run needs both a
        Start and a Finish block.
        """
        count = sum(1 for block in self.grid.values()
                    if getattr(block, "scorer", None) == scorer)
        for item in self.toolbox.items:
            role_block = getattr(item, "kind", None) == "block" and item.scorer == scorer
            role_component = item.kind == Component.SCORER and item.value == scorer
            if role_block or role_component:
                count += 1
        return count

    def _unsellable(self, item):
        """True when selling the item would take the player's LAST run role.

        Start and Finish blocks are ordinary goods now: the shop sells them
        (as plain Rect blocks, see Shop._scorer_offer), so a SPARE role can be
        sold back. The last one cannot — selling it would leave the player
        unable to start (or finish) a run, and the shop may never offer
        another. Both plain sales and the Death action refuse it, and the
        Start/Finish SCORER components are held to the same count because they
        can be assembled back into a role block.
        """
        if isinstance(item, Block) or getattr(item, "kind", None) == "block":
            scorer = getattr(item, "scorer", None)
        elif getattr(item, "kind", None) == Component.SCORER:
            scorer = item.value
        else:
            return False
        if scorer not in (Scorer.START, Scorer.FINISH):
            return False
        return self._role_blocks_owned(scorer) <= 1

    def _sell_selected_action(self):
        """Sell the selected action for a fraction of its price."""
        action = self.selected_action
        if action is None or action not in self.actions:
            self._set_shop_message("Item is not owned")
            return
        sell_price = self._sell_price(action)
        self.actions.remove(action)
        self.cash += sell_price
        self._clear_action_selection()
        self._set_shop_message(f"Sold {action.name} for ${sell_price}")

    def _info_target_at(self, pos):
        """Return (item, source) at a position for the info sidebar, or (None, None).

        The info sidebar is shown for shop items, toolbox items, cards, blocks
        that are already placed in the marble box, and the shop's "Last run
        cash gained" readout (which breaks the run's earnings down).
        """
        # The cash readout is not an item, so it is checked first: hovering it
        # shows where the last run's dollars came from.
        if ui.last_run_cash_rect(self).collidepoint(pos):
            return CASH_BREAKDOWN, "cash"
        item = self.shop.item_at(pos)
        if item is not None:
            return item, "shop"
        owned = self.toolbox.item_at(pos)
        if owned is not None:
            return owned, "toolbox"
        card = self.card_area_item_at(pos)
        if card is not None:
            return card, "cards"
        action = self.action_area_item_at(pos)
        if action is not None:
            return action, "actions"
        token = self.token_at(pos)
        if token is not None:
            return token, "tokens"
        if (MARBLE_BOX_COORDS[0] <= pos[0] < MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2]
                and MARBLE_BOX_COORDS[1] <= pos[1] < MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3]):
            gx = (pos[0] - MARBLE_BOX_COORDS[0]) // GRID_SIZE
            gy = (pos[1] - MARBLE_BOX_COORDS[1]) // GRID_SIZE
            block = self.grid.get((gx, gy))
            if block is not None:
                return block, "grid"
        return None, None

    def _v2_shelf_note(self):
        """Name any already-upgraded action a fresh shop has just shelved.

        Every action the shop offers is rolled for its version (see
        random_action_version), so roughly one in a hundred actions arrives
        already upgraded — a straight saving of ACTION_UPGRADE_COST, and easy to
        miss among the shop's other tiles. The shelf tile itself is gold-framed
        and tagged (see ui.draw_action), and this appends the name to the reroll
        message so a player who does not read the shelves is still told.
        """
        upgraded = [i for i in self.shop.items
                    if getattr(i, "kind", None) == "action"
                    and getattr(i, "version", 1) >= 2]
        if not upgraded:
            return ""
        names = ", ".join(self._item_name(i) for i in upgraded)
        return (f" — {names} already upgraded "
                f"(a free ${self._inflated(ACTION_UPGRADE_COST)})")

    def _refresh_shop(self):
        """Reroll the shop — free while a Fresh reroll is banked, else for cash."""
        if self.free_rerolls > 0:
            self.free_rerolls -= 1
            self.shop.refresh()
            if self.trials_enabled and self.current_trial == Trial.SLIM_PICKINGS:
                self._trim_shop_for_trial()
            left = f" ({self.free_rerolls} left)" if self.free_rerolls else ""
            self._set_shop_message(f"Free reroll{left}{self._tesseract_reroll_note()}"
                                   f"{self._v2_shelf_note()}")
            return
        cost = self._inflated(SHOP_REFRESH_COST)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to refresh the shop")
            return
        self.cash -= cost
        self.shop.refresh()
        if self.trials_enabled and self.current_trial == Trial.SLIM_PICKINGS:
            self._trim_shop_for_trial()
        self._set_shop_message(f"Refreshed shop (${cost})"
                               f"{self._tesseract_reroll_note()}"
                               f"{self._v2_shelf_note()}")

    def _tesseract_reroll_note(self):
        """Grow the Tesseract bonus for this reroll; a note for the message.

        Called on every shop reroll (paid or free): while the Tesseract whole
        card is owned, its permanent xMult bonus grows by
        TESSERACT_REROLL_XMULT and the reroll message reports the new total so
        the growth is visible while the player rerolls.
        """
        if not self._has_card(Card.TESSERACT):
            return ""
        self.tesseract_bonus += TESSERACT_REROLL_XMULT
        return f" — Tesseract x{self.tesseract_bonus:.1f}"

    def _trim_shop_for_trial(self):
        """Slim pickings: remove two random shop options for this run."""
        if len(self.shop.items) > 2:
            for item in random.sample(self.shop.items, 2):
                self.shop.items.remove(item)

    def _add_resource_points(self, scorer, amount=1):
        """Bank resource points for a Shreds/Rubble/Ideas/Picky scorer.

        A trigger banks a FRACTION of a point (1/3 for Shreds, 1/2 for the
        others at the average magnitude — see components.resource_points_for),
        because one whole point is what a reward costs. Points earned during a
        run are held in this run's gain counters. They only move into the
        permanent bank — and convert into rewards — after a run (see
        _commit_resource_points); RETRYING a run resets the pending gain and the
        bank alike (see _retry_run). (Parts and Fresh grant their reward
        immediately, so they are not handled here.)
        """
        if scorer == Scorer.SHREDS:
            self.shred_run_gain += amount
        elif scorer == Scorer.RUBBLE:
            self.rubble_run_gain += amount
        elif scorer == Scorer.IDEAS:
            self.idea_run_gain += amount
        elif scorer == Scorer.PICKY:
            self.option_run_gain += amount

    def _commit_resource_points(self):
        """Move this run's resource points into the bank and convert them.

        Called after a finished run. The run's points join the permanent bank,
        then every whole point converts into that scorer's reward (Shreds ->
        card, Rubble -> block, Ideas -> action, Picky -> shop slot). A trigger
        banks a fraction of a point, so the leftover below a point stays banked
        for a future run; if a grant is refused (a full area), its point stays
        banked too.
        """
        cost = self._resource_cost()
        self.shred_points += self.shred_run_gain
        self.shred_run_gain = 0
        while self.shred_points >= cost and self._grant_random_card():
            self.shred_points -= cost
        self.rubble_points += self.rubble_run_gain
        self.rubble_run_gain = 0
        while self.rubble_points >= cost and self._grant_random_block():
            self.rubble_points -= cost
        self.idea_points += self.idea_run_gain
        self.idea_run_gain = 0
        while self.idea_points >= cost and self._grant_random_action():
            self.idea_points -= cost
        # Picky points: every banked point adds a permanent bonus shop slot
        # (each slot shows an extra random offer on every shop refresh).
        self.option_points += self.option_run_gain
        self.option_run_gain = 0
        while self.option_points >= cost:
            self.option_points -= cost
            self.bonus_slots += 1
        self.shop.bonus_slots = self.bonus_slots

    def _resource_cost(self):
        """Points needed for one resource conversion, after the Factory card.

        Always ONE point, which is exactly what a trigger banks a fraction of.
        Factory ("resource conversions halve") needs half a point instead — a
        real half, since points are fractional now, so a 1/2-point Rubble
        trigger converts on its own.
        """
        if not self._has_card(Card.FACTORY):
            return RESOURCE_THRESHOLD
        return RESOURCE_THRESHOLD / 2

    def _grant_random_component(self):
        """Grant a random shape/effect/scorer component to the toolbox."""
        if len(self.toolbox.items) >= self.toolbox.cols * self.toolbox.rows:
            self._set_shop_message("Inventory is full — component withheld")
            return False
        kind = random.choice([Component.SHAPE, Component.EFFECT, Component.SCORER])
        if kind == Component.SHAPE:
            value = random.choice(Shape.ORDER)
            item = Component.shape_component(value)
        elif kind == Component.EFFECT:
            value = random.choice(Effect.ORDER)
            item = Component.effect_component(value, magnitude=roll_effect_magnitude(value))
        else:
            # Run roles are never handed out as components — the shop sells
            # them as ready-made Rect blocks, and Parts keeps to that rule.
            pool = [s for s in Scorer.SHOP_ORDER if s not in (Scorer.START, Scorer.FINISH)]
            value = random.choice(pool)
            item = Component.scorer_component(value, amount=roll_scorer_amount(value))
        self.toolbox.add(item)
        self._set_shop_message(f"Converted a component: {item.name}")
        sounds.play_coin()
        return True

    def _grant_random_card(self):
        """Grant a random card to the card area.

        Like the shop's card slots, the grant skips the cards the player already
        owns (see Shop.owned_cards): a second copy is the Showman card's perk,
        so without it this hands over a card the player can actually use. If
        every candidate is somehow owned already, the plain pool is used — the
        grant is always delivered.
        """
        if len(self.cards) >= MAX_CARDS:
            self._set_shop_message("Card area is full — card withheld")
            return False
        owned = self.shop.owned_cards()
        pool = [v for v in prebuilt_card_pool()
                if v != Card.ERR_404 and v not in owned]
        if not pool:
            pool = [v for v in prebuilt_card_pool() if v != Card.ERR_404]
        value = random.choice(pool)
        self.cards.append(make_card_item(value))
        self._discover_owned_card(value)
        self._set_shop_message(f"Converted a card: {Card.name(value)}")
        sounds.play_coin()
        return True

    def _grant_random_block(self):
        """Grant a random block (like a shop block) to the toolbox."""
        if len(self.toolbox.items) >= self.toolbox.cols * self.toolbox.rows:
            self._set_shop_message("Inventory is full — block withheld")
            return False
        shape = random.choice(Shape.ORDER)
        count = random_effect_count()
        effects = random.sample(Effect.REAL_ORDER, count)
        scorer = random.choice(Scorer.SHOP_ORDER)
        shape, effects = role_block_parts(scorer, shape, effects)
        amount = roll_scorer_amount(scorer)
        amounts = roll_effect_amounts(effects)
        name = role_block_name(scorer, shape)
        item = BlockItem(0, 0, shape, Effect.NONE, scorer, amount,
                         block_price_for(shape, effects, scorer, amount, amounts), name,
                         effects=effects, effect_amounts=amounts)
        self.toolbox.add(item)
        self._discover_block(item)
        self._set_shop_message(f"Converted a block: {name}")
        sounds.play_coin()
        return True

    def _grant_random_action(self):
        """Grant a random action to the action area."""
        if len(self.actions) >= MAX_ACTIONS:
            self._set_shop_message("Action area is full — action withheld")
            return False
        value = random.choice(Action.ORDER)
        item = ActionItem(value, Action.PRICES.get(value, 60),
                          version=random_action_version())
        self.actions.append(item)
        self._discover_action(value)
        self._set_shop_message(f"Converted an action: {self._item_name(item)}")
        sounds.play_coin()
        return True

    def _resource_owned(self, scorer):
        """True when the player owns the given resource scorer as a component,
        inside a block (in the toolbox or the marble box), or as the scorer
        half of an owned card."""
        for item in self.toolbox.items:
            if item.kind == Component.SCORER and item.value == scorer:
                return True
            if getattr(item, "kind", None) == "block" and item.scorer == scorer:
                return True
        if any(block.scorer == scorer for block in self.grid.values()):
            return True
        for card in self.cards:
            meta = generic_card_meta(card.value)
            if meta is not None and meta[1] == scorer:
                return True
        return False

    def _resource_display(self):
        """Lines to show under cash: (points_to_next, reward label) for each
        owned point-banked resource scorer (Shreds/Rubble/Ideas/Picky).
        Parts and Fresh grant immediately, so they show no points line."""
        lines = []
        specs = [
            (Scorer.SHREDS, self.shred_points, self.shred_run_gain, "card"),
            (Scorer.RUBBLE, self.rubble_points, self.rubble_run_gain, "block"),
            (Scorer.IDEAS, self.idea_points, self.idea_run_gain, "action"),
            (Scorer.PICKY, self.option_points, self.option_run_gain, "slot"),
        ]
        threshold = self._resource_cost()
        for scorer, bank, run_gain, label in specs:
            if self._resource_owned(scorer):
                # This run's pending points count toward the next conversion
                # (the reward itself is granted after a run).
                total = bank + run_gain
                to_next = threshold - (total % threshold)
                lines.append((to_next, label))
        return lines

    def _block_parts(self, block):
        """The shape, effect(s), and scorer components that make up a block.

        Each piece keeps the magnitude the block was built with (its own rolled
        strength), so disassembling a block hands back the same goods it was
        made from rather than a set of average-strength parts.
        """
        parts = [Component.shape_component(block.shape),
                 Component.scorer_component(block.scorer, amount=block.scorer_amount)]
        for e in block.effects:
            parts.append(Component.effect_component(
                e, magnitude=block.effect_magnitude(e)))
        return parts

    def _disassemble_card(self):
        """Split a selected splittable card back into its halves (for a fee).

        The card is removed from the card area and its condition + scorer
        components go into the toolbox. Whole cards (ERR 404 / Blueprint /
        Showman) cannot be split.
        """
        item = self.selected_toolbox_item
        if item is None or getattr(item, "kind", None) != "card":
            self._set_shop_message("Select a splittable card to disassemble")
            return
        if item not in self.cards:
            self._set_shop_message("Item is not owned")
            return
        parts = splittable_card_condition_scorer(item.value)
        if parts is None:
            # Only the indivisible whole cards can't be split; every composed
            # card (magnitude 1000+ or generic 2000+) has a condition + scorer.
            self._set_shop_message("This card cannot be split")
            return
        cost = self._inflated(CARD_DISASSEMBLE_COST)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to disassemble")
            return
        if len(self.toolbox.items) + 2 > self.toolbox.cols * self.toolbox.rows:
            self._set_shop_message("Inventory needs room for the halves")
            return
        condition, scorer = parts
        self.cards.remove(item)
        self.cash -= cost
        self.toolbox.add(Component.condition_component(condition))
        # The scorer half comes back at the magnitude the card carried (a card
        # rolled with a 45-chip +Chips half returns a 45-chip piece), so a card
        # and its halves are always worth the same.
        amount = getattr(item, "amount", 0) or Scorer.DEFAULT_AMOUNT.get(scorer, 0)
        self.toolbox.add(Component.scorer_component(scorer, amount=amount))
        self._clear_toolbox_selection()
        self._set_shop_message(
            f"Disassembled {item.name} (${cost})")
        sounds.play_mech()

    def _disassemble_block(self):
        """Break the selected block back into its parts (for a fee).

        Works on a toolbox block or a block placed in the marble box (the F key).
        """
        item = self.selected_toolbox_item
        if item is None or not isinstance(item, (Block, BlockItem)):
            self._set_shop_message("Select a block to disassemble")
            return
        cost = self._inflated(DISASSEMBLE_COST)
        if self.cash < cost:
            self._set_shop_message(f"Need ${cost} to disassemble")
            return
        parts = self._block_parts(item)
        in_toolbox = item in self.toolbox.items
        if len(self.toolbox.items) + len(parts) - (1 if in_toolbox else 0) > self.toolbox.cols * self.toolbox.rows:
            self._set_shop_message("Inventory needs room for the parts")
            return
        # Remove the block (from the grid if it was placed, else the toolbox).
        if isinstance(item, Block):
            self.grid.pop((item.x, item.y), None)
            if item.scorer == Scorer.START:
                self.marbles = [m for m in self.marbles if getattr(m, "start_block", None) is not item]
        elif in_toolbox:
            self.toolbox.items.remove(item)
        self.cash -= cost
        for part in parts:
            self.toolbox.add(part)
        name = self._item_name(item)
        # A pairing block can't exist without its partner: disassembling one also
        # deletes the matching portal / the other half of its key/lock pair.
        self._delete_pairing_partners(item)
        self._clear_toolbox_selection()
        self._set_shop_message(f"Disassembled {name} (${cost})")
        sounds.play_mech()

    def _delete_pairing_partners(self, item):
        """Delete the blocks that pair with a removed block.

        A Portal block and a Key/Lock block are useless without their other
        half, so removing one block (by disassembling it, selling it, or
        selling it with an action) removes its partner too — the block sharing
        its portal or key number, in the toolbox or on the grid.
        """
        if item.has_effect(Effect.PORTAL) and getattr(item, "portal_number", 0):
            self._delete_paired_portal(item.portal_number)
        if getattr(item, "key_number", 0):
            self._delete_paired_key(item.key_number)

    def _delete_paired_key(self, number):
        """Delete the Key/Lock block paired with the given key number.

        A Key and its Lock always come as a pair (two blocks with the same key
        number). Removing one half deletes the other so a lone, unusable half
        never lingers. The paired block lives either in the toolbox or, if it
        was placed, on the grid.
        """
        if not number:
            return
        for item in list(self.toolbox.items):
            if getattr(item, "key_number", 0) == number:
                self.toolbox.items.remove(item)
                return
        for key, block in list(self.grid.items()):
            if getattr(block, "key_number", 0) == number:
                self.grid.pop(key, None)
                if block.scorer == Scorer.START:
                    self.marbles = [m for m in self.marbles
                                    if getattr(m, "start_block", None) is not block]
                return

    def _delete_paired_portal(self, number):
        """Delete the portal block paired with the given pairing number.

        Portals come in pairs (two blocks with the same number). Removing one
        portal (via disassembly) deletes the other so a lone, unusable portal
        never lingers. The paired block lives either in the toolbox or, if it
        was placed, on the grid.
        """
        if not number:
            return
        for item in list(self.toolbox.items):
            if getattr(item, "portal_number", 0) == number:
                self.toolbox.items.remove(item)
                return
        for key, block in list(self.grid.items()):
            if getattr(block, "portal_number", 0) == number:
                self.grid.pop(key, None)
                if block.scorer == Scorer.START:
                    self.marbles = [m for m in self.marbles if getattr(m, "start_block", None) is not block]
                return

    def _sell_selected_item(self):
        """Sell the selected item (block, component, card, or action) for half its price."""
        # A selected action is sold first (actions are selected independently).
        if self.selected_action is not None:
            self._sell_selected_action()
            return
        item = self.selected_toolbox_item
        if item is None:
            return
        # A spare Start/Finish block is a normal good; the LAST one is not (see
        # _unsellable).
        if self._unsellable(item):
            self._set_shop_message("Your last Start or Finish block can't be sold")
            return
        # A card sells for a fraction of its original price. Cards live in the
        # card area (not the toolbox), so they are handled separately here.
        if getattr(item, "kind", None) == "card":
            if item not in self.cards:
                self._set_shop_message("Item is not owned")
                return
            sell_price = self._sell_price(item)
            self.cards.remove(item)
            self.cash += sell_price
            self._clear_toolbox_selection()
            self._set_shop_message(f"Sold {item.name} for ${sell_price}")
            return
        if item not in self.toolbox.items:
            self._set_shop_message("Item is not in the inventory")
            return
        # Resale value includes any cash paid to raise the trigger limit.
        sell_price = self._sell_price(item) + getattr(item, "trigger_paid", 0)
        self.toolbox.items.remove(item)
        # Selling an assigned condition/scorer cancels the pending card build.
        if item is self.card_condition or item is self.card_scorer:
            self.card_condition = None
            self.card_scorer = None
            self.card_builder_indexes.clear()
        # If the sold component was assigned to the assembler, unassign it.
        a = self.assembler
        if item is a.shape:
            a.shape = None
        elif item is a.scorer:
            a.scorer = None
        elif item in a.effects:
            a.effects.remove(item)
        self.assigned_toolbox_indexes.pop(item, None)
        # A pairing block can't exist without its partner: selling one also
        # deletes the matching portal / the other half of its key/lock pair.
        if getattr(item, "kind", None) == "block":
            self._delete_pairing_partners(item)
        self.cash += sell_price
        self._clear_toolbox_selection()
        self._set_shop_message(f"Sold {item.name} for ${sell_price}")

    def _describe_item(self, item):
        """Return [(label, description)] rows shown in the sidebar.

        Blocks break down into their shape, effect, and scorer so the player
        sees each part's behavior independently; components describe themselves.
        Each label names the part, e.g. "Shape - Slope", followed by the
        description.
        """
        if item is CASH_BREAKDOWN:
            return self._cash_breakdown_rows()
        if getattr(item, "kind", None) == "token":
            runs = ("every run, permanently" if item.runs_left is None
                    else f"{item.runs_left} more run(s)")
            return [
                (f"Token - {Scorer.name(item.scorer)}",
                 f"A kept scorer: it fires at the start of each run, {runs}."),
                (f"Scorer - {Scorer.name(item.scorer)}",
                 scorer_description(item.scorer, item.scorer_amount)),
                ("Kept from", (f"{Shape.name(item.shape)} "
                               f"{Scorer.name(item.scorer)}")),
            ]
        if isinstance(item, Block):
            rows = [(f"Shape - {Shape.name(item.shape)}", shape_description(item.shape))]
            for e in item.effects:
                rows.append((f"Effect - {Effect.name(e)}",
                             effect_description(e, item.effect_magnitude(e))))
            rows.append((f"Scorer - {Scorer.name(item.scorer)}", scorer_description(item.scorer, item.scorer_amount)))
            rows += self._pair_description_rows(item)
            if item.scorer in (Scorer.CHIPS_ADD, Scorer.MULT_ADD, Scorer.MULT_MUL,
                               Scorer.QUICK, Scorer.CASH, Scorer.SHARP,
                               Scorer.PARTS, Scorer.SHREDS, Scorer.RUBBLE, Scorer.IDEAS,
                               Scorer.RANDOM, Scorer.EFFECTIVE, Scorer.FRESH,
                               Scorer.PICKY, Scorer.VOYAGER, Scorer.SATANIC,
                               Scorer.SUMMIT, Scorer.AIRBALL):
                limit = getattr(item, "trigger_limit", 1)
                if limit == 1:
                    rows.append(("Trigger", f"Scores once per run ({item.triggers_left} left)"))
                else:
                    rows.append(("Trigger", f"Scores {limit} times per run ({item.triggers_left} left)"))
            return rows
        if getattr(item, "kind", None) == "block":
            rows = [(f"Shape - {Shape.name(item.shape)}", shape_description(item.shape))]
            for e in item.effects:
                rows.append((f"Effect - {Effect.name(e)}",
                             effect_description(e, item.effect_magnitude(e))))
            rows.append((f"Scorer - {Scorer.name(item.scorer)}", scorer_description(item.scorer, item.scorer_amount)))
            rows += self._pair_description_rows(item)
            if item.scorer in (Scorer.CHIPS_ADD, Scorer.MULT_ADD, Scorer.MULT_MUL,
                               Scorer.QUICK, Scorer.CASH, Scorer.SHARP,
                               Scorer.PARTS, Scorer.SHREDS, Scorer.RUBBLE, Scorer.IDEAS,
                               Scorer.RANDOM, Scorer.EFFECTIVE, Scorer.FRESH,
                               Scorer.PICKY, Scorer.VOYAGER, Scorer.SATANIC,
                               Scorer.SUMMIT, Scorer.AIRBALL):
                limit = getattr(item, "trigger_limit", 1)
                if limit == 1:
                    rows.append(("Trigger", "Scores once per run"))
                else:
                    rows.append(("Trigger", f"Scores {limit} times per run"))
            return rows
        if getattr(item, "kind", None) == "card":
            return [
                (f"Card - {Card.name(item.value)}",
                 card_description(item.value, getattr(item, "amount", 0))),
                ("Comment", Card.comment(item.value)),
            ]
        if getattr(item, "kind", None) == "action":
            version = getattr(item, "version", 1)
            # The version row is the whole point of an action's info box: v1
            # still has the upgrade to buy, while a v2 (whether the player paid
            # for it or the shop rolled it already upgraded — see
            # random_action_version) has nothing left to spend on it.
            if version >= 2:
                version_text = "v2 — fully upgraded (the strongest version)"
            else:
                version_text = ("v1 — upgrade to v2 for "
                                f"${self._inflated(ACTION_UPGRADE_COST)}")
            return [
                (f"Action - {Action.name(item.value)}",
                 Action.description(item.value, version)),
                ("Version", version_text),
                ("Comment", Action.comment(item.value)),
            ]
        if item.kind == Component.SHAPE:
            return [(f"Shape - {Shape.name(item.value)}", shape_description(item.value))]
        if item.kind == Component.EFFECT:
            return [(f"Effect - {Effect.name(item.value)}",
                     effect_description(item.value, item.effect_magnitude))]
        if item.kind == Component.SCORER:
            return [(f"Scorer - {Scorer.name(item.value)}", scorer_description(item.value, item.amount))]
        if item.kind == Component.CONDITION:
            return [(f"Condition - {Condition.name(item.value)}",
                     condition_description(item.value))]
        return []

    def _pair_description_rows(self, item):
        """Sidebar rows explaining a block's pairing (key/lock pairs).

        A Key/Lock block's number is its whole point — the two halves only work
        together — so the sidebar names the pair and how it opens.
        """
        number = getattr(item, "key_number", 0)
        if not number or paired_shape(block_shape(item)) is None:
            return []
        return [("Pair", (f"Key/Lock pair #{number} — the Lock is a solid door until "
                          "a marble passes through its Key. Locks close again at the "
                          "start of each run."))]

    def _cash_breakdown_rows(self):
        """Sidebar rows for the shop's "Last run cash gained" readout.

        Every dollar a run pays is listed with where it came from: the flat
        base payment, interest on the cash held at the end of the run, the
        bonus for beating the required score, Cash cards, and the Cash/Lucky
        scorers (which pay out as they trigger rather than at the end).
        """
        rows = self.last_run_cash_breakdown
        if not rows:
            return [("Last run", ("No run has been finished yet — finish a "
                                  "run (or retry it) to see where its cash "
                                  "came from."))]
        # A Debt block cancels the interest, so the readout says so.
        interest_note = " (cancelled by a Debt block)" if rows.get("debt") else ""
        return [
            ("Base cash", (f"${rows.get('base', 0)} — the flat payment for "
                           "finishing a run")),
            ("Interest", (f"${rows.get('interest', 0)} — $1 for every $10 you "
                          f"held at the end of the run{interest_note}")),
            ("Beat the required score", (f"${rows.get('score', 0)} — scaled by "
                                         "how far past the target the run's "
                                         "score went")),
            ("Cash cards", (f"${rows.get('cards', 0)} — from Cash-scorer cards "
                            "(paid out with this award)")),
            ("Cash/Lucky scorers", (f"${rows.get('scorers', 0)} — from Cash "
                                    "blocks and Lucky rolls (paid out as they "
                                    "trigger, and undone by a retry)")),
            ("Total", f"${self.last_run_cash_gained} earned on the last run"),
        ]

    def _action_hint(self, item, source):
        """A short hint telling the player how to act on the hovered item."""
        if source == "shop":
            return "Left-click to buy"
        if source == "cards":
            return "Click another card to swap order | B to sell"
        if source == "actions":
            return "Click a target block/card, then press S to use"
        if source == "tokens":
            return "Fires at the start of each run it covers"
        if source == "toolbox":
            if getattr(item, "kind", None) == "block":
                return "Left-click to place | D to disassemble"
            if getattr(item, "kind", None) == Component.CONDITION:
                return "Condition: click a card scorer, then press S to build"
            return "Left-click to toggle in the assembler | D to assemble"
        return ""  # Placed blocks and other sources have no extra action.

    def _wrap_text(self, text, font, max_width):
        """Word-wrap text into lines that fit within max_width pixels."""
        lines = []
        current = ""
        for word in text.split():
            trial = current + (" " if current else "") + word
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _total_price(self, item):
        """A block's full worth: original price plus cash paid for trigger upgrades.

        Returns None for items without a price or without any upgrades.
        """
        if not hasattr(item, "price"):
            return None
        paid = getattr(item, "trigger_paid", 0)
        if not paid:
            return None
        return item.price + paid

    def _is_assigned(self, item):
        """True when a toolbox component is assigned to the assembler."""
        a = self.assembler
        return item is a.shape or item is a.scorer or item in a.effects

    def _show_marble_box_title(self):
        """Whether the BOARD title should be drawn.

        It hides while the mouse is over the board panel, so the label never
        sits under the cursor (the panel's bottom-left corner is where the
        player clicks to place blocks).
        """
        return not pygame.Rect(MARBLE_BOX_COORDS).collidepoint(pygame.mouse.get_pos())

    def _show_toolbox_title(self):
        """Whether the INVENTORY title should be drawn.

        It hides while the mouse is over the inventory panel, so the label
        never sits under the cursor while the player clicks items there.
        """
        return not pygame.Rect(TOOLBOX_COORDS).collidepoint(pygame.mouse.get_pos())

    def _show_shop_title(self):
        """Whether the SHOP title should be drawn.

        It hides while the mouse is over the shop panel, so the label never
        sits under the cursor while the player clicks items there.
        """
        return not pygame.Rect(SHOP_COORDS).collidepoint(pygame.mouse.get_pos())

    def update(self):
        if (self.title_screen or self.achievements_open or self.marble_selecting
                or self.upgrades_open or self.collection_open):
            return
        # Achievement unlock conditions are checked every frame while playing.
        self._check_achievements()
        # Bottom popups (achievement unlocks, collection discoveries) animate
        # every frame: slide up from under the screen, hold, then slide down.
        for popup in self.popups:
            popup.update(DT)
        self.popups = [p for p in self.popups if not p.dead()]
        # Score popups float and fade every frame, even between runs.
        for particle in self.score_particles:
            particle.update(DT)
        self.score_particles = [p for p in self.score_particles if not p.dead()]
        # Marble trail dots shrink and fade every frame, even between runs.
        for particle in self.trail_particles:
            particle.update(DT)
        self.trail_particles = [p for p in self.trail_particles if not p.dead()]
        if self.shop_message_timer > 0:
            self.shop_message_timer -= 1
            if self.shop_message_timer <= 0:
                self.shop_message = ""
        if not self.paused and self.run_active:
            self.run_time += DT
            # The Watch whole card ends the run exactly at the run's ideal
            # finish time: every marble is marked finished, so the normal
            # end-of-run path (finish cards, cash award, results) runs this
            # same frame. Watch also limits which blocks score — see
            # _watch_blocks_out_of_play.
            if self._has_card(Card.WATCH) and self.run_time >= TIME_IDEAL:
                for marble in self.marbles:
                    marble.finished = True
            # Locked board squares act as solid walls this frame (they confine
            # the marbles to the unlocked region but never score or count as
            # block contacts).
            sim_blocks = self._simulation_blocks()
            for marble in self.marbles:
                marble.physics.update(marble, DT, sim_blocks)
                # The Singularity final boss makes the marble gain mass quickly
                # and linearly over time, so it falls ever faster as the run
                # drags on.
                if self.final_boss == FinalBoss.SINGULARITY:
                    marble.mass += SINGULARITY_MASS_GROWTH * DT
                # The astronaut card grants mult for every second a marble is
                # pulled by a black hole, so accumulate that pull time per run.
                if getattr(marble, "under_black_hole", False):
                    self.black_hole_time += DT
                # The plane card grants chips for every second the marble is
                # in the air, so accumulate air time (no block contact) per run.
                # The airball scorer reads each marble's own airborne streak
                # (seconds since it last touched any block, incl. Shape.None).
                if not marble.collisions_this_tick:
                    marble.air_streak += DT
                    self.air_time += DT
                # Leave a shrinking trail dot wherever the marble has moved.
                moved = marble.distance - marble._last_trail_distance
                marble._last_trail_distance = marble.distance
                marble._trail_accum += moved
                while marble._trail_accum >= TRAIL_SPACING:
                    marble._trail_accum -= TRAIL_SPACING
                    self.trail_particles.append(TrailParticle(
                        marble.position[0], marble.position[1],
                        max(1.5, marble.radius * TRAIL_RADIUS_SCALE), marble.color))
            # Split marbles share the board: separate any that overlap, so a
            # splitter's copy can collide with the marble it came from (a
            # phasing marble passes through the others too).
            if len(self.marbles) > 1:
                self.marbles[0].physics.resolve_marble_collisions(self.marbles)
            # A fragile block that shattered this frame grows the wrecking ball
            # card's permanent +mult bonus (handled once per break).
            for block in self.grid.values():
                if getattr(block, "broke_fragile_this_frame", False):
                    block.broke_fragile_this_frame = False
                    self._on_fragile_broken(block)
            # A satanic block that a marble touched and then left this frame is
            # permanently destroyed: removed from the board for good (it never
            # comes back on later runs).
            for key, block in list(self.grid.items()):
                if getattr(block, "satanic_leave", False):
                    self.grid.pop(key, None)
                    # A Satanic block dying is a block destroyed this run (the
                    # Undertaker scorer counts them).
                    self.run_blocks_destroyed += 1
            self._handle_block_contacts(list(self.grid.values()))
            # A marble that touched a block this frame is not airborne: its
            # air streak was read at the fresh contact above (block scorers /
            # Airball cards), so end it so the next air segment starts fresh.
            for marble in self.marbles:
                if marble.collisions_this_tick:
                    marble.air_streak = 0.0
        # The marble-box fire animates every frame (growing while the score
        # passes the run, dying down once it is over).
        if not self.paused:
            self._update_fire(DT)

    def _has_all_effects(self, item):
        """True when the item is a block holding every real effect in the game."""
        effects = getattr(item, "effects", None)
        return effects is not None and set(effects) >= set(Effect.REAL_ORDER)

    def _push_popup(self, title, description, color=(255, 215, 0)):
        """Queue a compact bottom popup that slides up, holds, then slides down."""
        self.popups.append(Popup(title, description, color))

    def _show_achievement_popup(self, achievement):
        """Queue the 'achievement unlocked' popup for a newly earned one.

        A secret's real description appears once it is unlocked (not "???").
        """
        self._push_popup(achievement.name, achievements.display_description(achievement),
                         (255, 215, 0))

    def _check_achievements(self):
        """Evaluate each achievement's unlock condition and pop up new ones.

        Achievements persist globally (achievements.json), so "in any run at
        any time" conditions stay unlocked across runs, games, and save slots.
        """
        if achievements.is_disabled():
            return  # the player unlocked the whole collection: no new unlocks
        newly = []
        # Rich: hold more than $1000 in cash at any point in a run.
        if self.cash > 1000 and achievements.unlock("rich"):
            newly.append(achievements.achievement_by_id("rich"))
        # How did we get here?: own a block with every effect in the game.
        for item in list(self.grid.values()) + list(self.toolbox.items):
            if self._has_all_effects(item):
                if achievements.unlock("how_did_we_get_here"):
                    newly.append(achievements.achievement_by_id("how_did_we_get_here"))
                break
        for achievement in newly:
            if achievement is not None:
                self._show_achievement_popup(achievement)

    def _release_start_marble(self, start_block, vx=0.0):
        """Release one marble from a Start block and return it.

        The marble starts at the Start block's centre with no velocity (or the
        given sideways drift, which the Doppelganger card uses for its second
        marble). The trial modifiers and the save's marble type are applied
        here so every marble a run releases is configured identically.
        """
        marble = Marble(start_block.rect.centerx, start_block.rect.centery)
        marble.velocity = np.array([vx, 0.0])
        marble.start_block = start_block
        # The dead-zone trial triples gravity in the box's bottom third;
        # the all-finishes trial makes the marble-box borders act as a
        # finish. Restarts keep the same trial, so these are read from the
        # current (already chosen/applied) trial each run.
        marble.dead_zone = self.current_trial == Trial.DEAD_ZONE
        marble.finish_on_border = self.current_trial == Trial.ALL_FINISHES
        # The bouncy-castle trial makes every solid block reflect the
        # marble like a bouncy block (physics.resolve_collision reads it).
        # The marble-weight trial scales only effect pushes by
        # 1/effect_mass_mult (2.0 heavy / 0.5 light, rolled in _apply_trial);
        # fall speed reads marble.mass and stays normal. Both are gated by
        # trials_enabled so a random trial never leaks into non-trial tests.
        marble.bouncy_castle = self.trials_enabled and self.current_trial == Trial.BOUNCY_CASTLE
        marble.effect_mass_mult = (self.trial_marble_weight
                                   if self.trials_enabled
                                   and self.current_trial == Trial.MARBLE_WEIGHT
                                   else 1.0)
        # The save's marble type drives the marble's behavior and look: the
        # 8 ball retriggers block scorers, the rubber ball bounces (and
        # wears two random half-colors), the ping-pong ball is very light.
        _configure_marble_type(marble, self.marble_type)
        self.marbles.append(marble)
        return marble

    def reset_run(self, choose_trial=True):
        if self.game_over or self.awaiting_after_run:
            return False
        starts = [block for block in self.grid.values() if block.scorer == Scorer.START]
        if not starts:
            return False

        # A fresh run leaves a fresh trail (old dots are discarded).
        self.trail_particles = []
        self.run_active = True
        self.run_complete = False
        self.run_cleared = False
        self.score_chips = 1
        self.score_mult = 1
        # Permanent metagame upgrades (bought with dice on the title screen's
        # UPGRADES tab) apply at the start of every run: +chips, +mult, and an
        # xMult multiplier. A save can turn these off on the marble-selection
        # screen (upgrades_enabled), defaulting to on.
        if self.upgrades_enabled:
            self.score_chips += metagame.chip_bonus()
            self.score_mult += metagame.mult_bonus()
            xmult = metagame.xmult_bonus()
            if xmult != 1.0:
                self.score_mult = self.score_mult * xmult
        # The trial is chosen BEFORE the run starts (see _choose_trial, called
        # at game start and after each run); starting the run applies its
        # effects to the current board. Restarts, board edits, and retries keep
        # the already-applied trial so it never changes mid-run.
        if choose_trial and self.trials_enabled:
            self._apply_trial()
        # A fresh run starts with no armed Quick cards and no pending Cash-card
        # cash; cards that fire at the start of the run (below) arm/earn right
        # after this.
        self.armed_quick.clear()
        self.card_cash_run_gain = 0
        # A fresh run starts with no cash earned by Cash/Lucky scorer blocks
        # yet (it accumulates as the run's blocks trigger) — but this run
        # already PAID that cash into the wallet as it triggered, so the money
        # comes back out along with the counter. Restarting the run (R),
        # starting a fresh one (T), and editing the board mid-run all discard
        # the run, so none of them may leave behind what the discarded run was
        # paid. Money already spent is not clawed back: the wallet never goes
        # below $0 (the same rule the Fresh rerolls below follow).
        self.cash = max(0, self.cash - self.run_cash_gained)
        self.run_cash_gained = 0
        # Fresh run: no resource points earned yet (Shreds/Rubble/Ideas/Picky
        # only become banked rewards after a run; see _continue_run). Cleared
        # BEFORE the start-of-run cards fire below.
        self.shred_run_gain = 0
        self.rubble_run_gain = 0
        self.idea_run_gain = 0
        self.option_run_gain = 0
        # Fresh run: it has not granted any free rerolls yet — and the rerolls
        # THIS run's Fresh hits already banked come back off the bank, for the
        # same reason the scorer cash above does: the discarded run did not
        # earn them. A reroll already spent is not un-spent (the bank simply
        # can't go below zero), and a run that was COMMITTED rather than
        # restarted has its counter cleared by _continue_run, so this rollback
        # only ever touches a run that is being thrown away.
        self.free_rerolls = max(0, self.free_rerolls - self.free_rerolls_run_gain)
        self.free_rerolls_run_gain = 0
        # Cards grant their score effects at the start of each run (e.g. Joker
        # gives +4 mult), so they apply right after the mult resets to 1. A
        # card disabled by the Card cutter trial is skipped. Every random
        # OUTPUT scorer (Lucky, Random) also picks its result for this run
        # here, before anything can trigger, so retrying the run replays the
        # same outcome (see _roll_run_random_outputs). Resetting to build state
        # after a board edit or a retry (choose_trial False) keeps the run's
        # already-chosen results.
        if choose_trial:
            self._roll_run_random_outputs()
        self._apply_cards()
        self.run_time = 0.0
        # Fresh run: no black-hole pull time has accumulated yet (astronaut).
        self.black_hole_time = 0.0
        # Fresh run: no Fragile Breaks (Wrecking Ball) gains earned yet. They
        # only become permanent after a run.
        self._reset_wrecking_run_gain()
        # Fresh run: no air time has accumulated yet (plane).
        self.air_time = 0.0
        # Fresh run: no Drill-scorer locked squares earned yet.
        self.drill_run_units = 0
        # Fresh run: no blocks destroyed yet (Undertaker) and no Debt block has
        # cancelled the run's interest yet.
        self.run_blocks_destroyed = 0
        self.debt_run_triggered = False
        # Fresh run: no Rally touches, no previous-contact block for Echo, and
        # no primed Bomb blocks yet.
        self.run_fresh_touches = 0
        self.run_first_blocks = []
        self._prev_contact_block = None
        self.bomb_cells = set()
        # Fresh run: the type bonus counts only the types touched THIS run.
        self.touched_shapes = set()
        self.touched_effects = set()
        self.touched_scorers = set()
        # Fresh run: per-type counts of distinct touch events, used only by the
        # repeats-only trial (a type contributes to uniqueness once touched
        # twice). Incremented on fresh contacts in _handle_block_contacts.
        self.touch_shape_counts = {}
        self.touch_effect_counts = {}
        self.touch_scorer_counts = {}
        # Fresh run: no block has been contacted yet (Effective Start/End
        # condition cards inspect the run's first/last contacted block).
        self._first_contact_block = None
        self._last_contact_block = None
        self._last_contact_air = 0.0
        # The speed of the marble at that last fresh contact, so an
        # end-condition Quick card can measure the run's final block hit (there
        # is no NEXT block after the run for the usual Quick payoff to arm on).
        self._last_contact_speed = 0.0
        # Fresh run: every scoring block gets its triggers back (Hands tied
        # maxes out the chosen blocks' triggers), rotating blocks return to
        # their base angle (continuous spin reset to 0), and fragile blocks
        # that shattered are rebuilt to their original shape.
        for block in self.grid.values():
            block.triggers_left = (TRIAL_MAX_TRIGGERS if block in self.trial_maxed_blocks
                                   else block.trigger_limit)
            # A portal pair's travel budget refills each run (see
            # PORTAL_MAX_ACTIVATIONS): 100 travels are allowed per run.
            if block.has_effect(Effect.PORTAL):
                block.portal_uses_left = PORTAL_MAX_ACTIVATIONS
            if block.has_effect(Effect.ROTATE):
                block.spin = 0.0
                block._refresh_geometry()
            if block._fragile_shape is not None:
                block.shape = block._fragile_shape
                block._fragile_shape = None
            # Every Lock closes again at the start of each run, so the marble
            # must reach its Key again this run (see _unlock_matching_locks).
            block.locked = block.shape == Shape.LOCK
        self.marbles = []
        for start_block in starts:
            self._release_start_marble(start_block)
            # The Doppelganger whole card releases a second marble from every
            # Start block, drifting sideways so the two do not overlap from
            # the first frame. Both must reach the FINISH before the run ends.
            if self._has_card(Card.DOPPELGANGER):
                self._release_start_marble(start_block, vx=DOPPELGANGER_START_VX)
        # Spirit tokens fire once at the start of each run they still cover,
        # after the marbles exist (the scorer path reads the run's marble).
        self._apply_tokens()
        return True

    def _particle_amount_text(self, amount):
        """Format a scored amount for a popup: whole numbers plain, floats trimmed."""
        if float(amount).is_integer():
            return str(int(amount))
        return f"{amount:.2f}".rstrip("0").rstrip(".")

    def _spawn_score_particle(self, x, y, text, color):
        """Spawn a floating score popup at a screen position."""
        self.score_particles.append(
            ScoreParticle(x, y, text, color, self.font))

    def _spawn_block_particle(self, block, text, color):
        """Spawn a score popup jumping out of the middle of a block."""
        self._spawn_score_particle(block.rect.centerx, block.rect.centery, text, color)

    def _spawn_card_particle(self, card, text, color, block=None):
        """Spawn a card's single score popup for one score-affecting event.

        Each card emits exactly one particle per event. When a card's modifier
        is tied to a block (the marble touching or near it), the popup appears
        near that block; otherwise it appears on the owned card in the card
        area.
        """
        if block is not None:
            self._spawn_score_particle(block.rect.centerx, block.rect.centery, text, color)
            return
        try:
            index = self.cards.index(card)
        except ValueError:
            index = 0
        x = CARD_AREA_COORDS[0] + index * GRID_SIZE + GRID_SIZE // 2
        y = CARD_AREA_COORDS[1] + GRID_SIZE // 2
        self._spawn_score_particle(x, y, text, color)

    def _choose_trial(self, next_run=None):
        """Set the trial the given run is played under, before the run starts.

        ``next_run`` is the run being set up (the one after the finished run by
        default). The difficulty decides how many of a round's runs play a
        trial, and they are the round's LAST runs (see
        Difficulty.TRIALS_PER_ROUND): difficulties 1-2 give only a round's
        final run a trial, difficulty 3 its last two runs, and difficulty 4
        every run of the round (the game's original balance). The trial itself
        is drawn fresh per run, exactly as it always was. A run with no trial
        is played clean — the display reads NO TRIAL — though the player can
        still buy one onto it (see _click_trial_display). The shapes a trial
        carries are applied to the board when the run begins (see _apply_trial).
        """
        if next_run is None:
            next_run = self.run_number + 1
        if next_run % RUNS_PER_ROUND < self.trials_without_trial_runs:
            self.current_trial = None
        else:
            self.current_trial = random.choice(Trial.ORDER)

    @property
    def trials_without_trial_runs(self):
        """How many of a round's runs are played with no trial (Difficulty).

        The trials land on the round's LAST runs, so a round with fewer trials
        than runs opens with this many clean (trial-free) runs.
        """
        return max(0, RUNS_PER_ROUND - self.trials_per_round)

    @property
    def trials_per_round(self):
        """How many of a round's last runs play a trial (Difficulty)."""
        return Difficulty.trials_per_round(self.difficulty)

    @property
    def score_growth(self):
        """The factor this save's required score grows by each run (Difficulty)."""
        return Difficulty.score_growth(self.difficulty)

    def trial_options_available(self):
        """True while the trial display's two purchase options can be used.

        A run's trial is fixed once its marbles are rolling, so the display can
        only be bought from while BUILDING the run. It is also unavailable on
        the final boss run (which shows a boss instead of a trial), during the
        post-run RETRY/CONTINUE state, and when trials are switched off for the
        save entirely.
        """
        return (self.trials_enabled and self.final_boss is None
                and not self.game_over and not self.run_active
                and not self.run_complete and not self.awaiting_after_run)

    def _trial_half_at(self, pos):
        """Which half of the trial display a screen position is in.

        Returns "left" (buy a different random trial), "right" (buy no trial
        for this run), or None when the position is off the display.
        """
        if not TRIAL_BOX_RECT.collidepoint(pos):
            return None
        return "left" if pos[0] < TRIAL_BOX_RECT.centerx else "right"

    def _random_other_trial(self):
        """A random trial that is different from the one running now.

        With no trial running (the player bought it away) every trial is a
        candidate, so the left half also brings a trial back.
        """
        choices = [t for t in Trial.ORDER if t != self.current_trial]
        return random.choice(choices or list(Trial.ORDER))

    def _click_trial_display(self, pos):
        """Buy a new trial (left half) or no trial (right half) for cash.

        The left half pays TRIAL_CHANGE_COST for a DIFFERENT random trial; the
        right half pays TRIAL_DISABLE_COST to run with no trial at all. Either
        way the trial's effects are rolled onto the current board immediately,
        so what the player sees while building is what the run will play.
        Returns True when a purchase went through.
        """
        half = self._trial_half_at(pos)
        if half is None:
            return False
        if not self.trial_options_available():
            self._set_shop_message("The trial can only be changed while building")
            return False
        if half == "left":
            if self.cash < TRIAL_CHANGE_COST:
                self._set_shop_message(
                    f"Need ${TRIAL_CHANGE_COST} to change the trial")
                return False
            self.cash -= TRIAL_CHANGE_COST
            self.current_trial = self._random_other_trial()
            self._apply_trial()
            self._set_shop_message(f"Trial changed: {Trial.name(self.current_trial)}"
                                   f" (${TRIAL_CHANGE_COST})")
            sounds.play_coin()
            return True
        if self.current_trial is None:
            self._set_shop_message("This run already has no trial")
            return False
        if self.cash < TRIAL_DISABLE_COST:
            self._set_shop_message(
                f"Need ${TRIAL_DISABLE_COST} to disable the trial")
            return False
        self.cash -= TRIAL_DISABLE_COST
        self.current_trial = None
        self._apply_trial()
        self._set_shop_message(f"Trial disabled (${TRIAL_DISABLE_COST})")
        sounds.play_coin()
        return True

    def _apply_trial(self):
        """Apply the current trial to this run's blocks and cards.

        Hands tied maxes out the trigger limit of a random 1/4 of the blocks
        currently in the marble box (they recharge to TRIAL_MAX_TRIGGERS on
        each reset). Card cutter disables a random owned card, whose score
        effect is skipped for the run. Crumbling marks a random 1/4 of the
        placed blocks as fragile (they shatter like real fragile blocks once a
        marble touches and leaves, then rebuild next run). Deal breaker
        disables every owned card of one randomly chosen condition. Marble
        weight rolls a heavier-or-lighter effect-push factor for the run. The
        trial state is cleared again when the run advances (see _continue_run).
        """
        self.trial_maxed_blocks = set()
        self.disabled_card = None
        self.deal_broken_cards = set()
        # Marble weight re-rolls each run (a non-MARBLE_WEIGHT trial keeps the
        # normal 1.0 factor).
        self.trial_marble_weight = 1.0
        # Crumbling marks a fresh random 1/4 of the placed blocks each run;
        # blocks chosen by an earlier crumbling run are un-marked first so the
        # fragility never lingers into a trial that isn't crumbling.
        for block in self.grid.values():
            block.trial_fragile = False
        self.trial_fragile_blocks = set()
        if self.current_trial == Trial.HANDS_TIED:
            blocks = list(self.grid.values())
            if blocks:
                count = max(1, len(blocks) // 4)
                self.trial_maxed_blocks = set(random.sample(blocks, count))
        elif self.current_trial == Trial.CARD_CUTTER:
            if self.cards:
                self.disabled_card = random.choice(self.cards)
        elif self.current_trial == Trial.SHUFFLED:
            # Flips and shuffles the player's cards (order matters for Blueprint).
            if self.cards:
                self.cards.reverse()
                random.shuffle(self.cards)
        elif self.current_trial == Trial.CRUMBLING:
            # A random 1/4 of the placed blocks become fragile for the run:
            # they shatter into no-hitbox fields when a marble touches and
            # leaves them (physics), and rebuild to their original shape on the
            # next run reset. Only real solid blocks can be picked, and the
            # Start/Finish roles are spared so the run can still be completed.
            blocks = [b for b in self.grid.values()
                      if b.shape != Shape.NONE
                      and b.scorer != Scorer.START and b.scorer != Scorer.FINISH]
            if blocks:
                count = max(1, len(blocks) // 4)
                chosen = random.sample(blocks, count)
                for block in chosen:
                    block.trial_fragile = True
                self.trial_fragile_blocks = set(chosen)
        elif self.current_trial == Trial.MARBLE_WEIGHT:
            # The marble is randomly heavier (2x effect mass -> weaker pushes)
            # or lighter (0.5x -> stronger pushes) for the whole run. Only
            # effect pushes change; fall speed is untouched.
            self.trial_marble_weight = random.choice((2.0, 0.9))
        elif self.current_trial == Trial.DEAL_BREAKER:
            # Disable every owned card whose condition matches one randomly
            # chosen condition. Only splittable cards have a condition (the
            # indivisible ERR 404 / Blueprint / Showman never do); pick from
            # the conditions the player actually owns so the trial bites.
            if self.cards:
                conditions = set()
                for card in self.cards:
                    parts = splittable_card_condition_scorer(card.value)
                    if parts is not None:
                        conditions.add(parts[0])
                if conditions:
                    chosen = random.choice(list(conditions))
                    self.deal_broken_cards = {
                        card for card in self.cards
                        if splittable_card_condition_scorer(card.value) is not None
                        and splittable_card_condition_scorer(card.value)[0] == chosen}

    def _apply_cards(self):
        """Apply every owned card's score effect at the start of a run."""
        cards.apply_cards(self)

    def _apply_cards_on_finish(self):
        """Apply owned cards that trigger when a run ends (e.g. Explorer)."""
        cards.apply_cards_on_finish(self)

    def _apply_cards_on_collision(self, block, marble=None):
        """Apply owned shape/effect cards when the marble collides with a block.

        Each owned card matching the block's shape or one of its effects
        grants +4 mult (once per fresh collision). ``marble`` is the touching
        marble (an Airball card rewards its airborne streak before the hit).
        """
        cards.apply_card_on_collision(self, block, marble)

    def _on_fragile_broken(self, block):
        """A fragile block broke: the wrecking ball card gains +3 mult."""
        # A fragile block shattering counts as a block destroyed this run (the
        # Undertaker scorer pays for each of them).
        self.run_blocks_destroyed += 1
        cards.on_fragile_broken(self, block)

    def _unlock_matching_locks(self, key_block):
        """Open every Lock block paired with the given Key block.

        The two halves of a key/lock pair share a key number; passing through
        the Key opens the Lock — its solid door becomes a pass-through doorway
        for the rest of the run (it closes again at the start of the next one,
        see reset_run). A Key with no matching Lock on the board (a lone half,
        e.g. one granted at random) opens nothing.
        """
        number = getattr(key_block, "key_number", 0)
        if not number:
            return
        for block in self.grid.values():
            if (block.shape == Shape.LOCK and getattr(block, "locked", True)
                    and getattr(block, "key_number", 0) == number):
                block.locked = False

    def _sync_portal_pair_triggers(self, block, blocks):
        """Make a portal share its trigger count with its paired portal.

        Portal pairs have ONE trigger count: a marble passing through either
        portal uses up the whole pair. Both portals are set to the lower of the
        two remaining counts so they stay in lockstep and their red borders
        agree — e.g. a freshly placed portal inherits an exhausted partner's
        count of zero.
        """
        if not block.has_effect(Effect.PORTAL):
            return
        number = getattr(block, "portal_number", 0)
        for other in blocks:
            if (other is not block and other.has_effect(Effect.PORTAL)
                    and getattr(other, "portal_number", 0) == number):
                shared = min(block.triggers_left, other.triggers_left)
                block.triggers_left = shared
                other.triggers_left = shared
                return

    def _score_factors(self):
        """The run's normalized score factors, each in 0..1 (1 = best).

        Returns (time_good, dist_good, uniq_good, unique_types). Time is a
        reciprocal (fast runs are best; a zero run time counts as fastest),
        distance and uniqueness grow with their value.
        """
        total_distance = sum(getattr(m, "distance", 0.0) for m in self.marbles)
        # The uniqueness score counts every distinct type touched — EXCEPT under
        # the repeats-only trial, where a shape/effect/scorer type only counts
        # once it has been freshly touched at least twice this run (each
        # qualifying type counts once toward UNIQUE_SCALE).
        if self.trials_enabled and self.current_trial == Trial.REPEATS_ONLY:
            unique_types = (sum(1 for c in self.touch_shape_counts.values() if c >= 2)
                            + sum(1 for c in self.touch_effect_counts.values() if c >= 2)
                            + sum(1 for c in self.touch_scorer_counts.values() if c >= 2))
        else:
            unique_types = (len(self.touched_shapes) + len(self.touched_effects)
                            + len(self.touched_scorers))
        scale_sq = TIME_SCALE * TIME_SCALE
        # The Long run trial doubles the ideal time, so longer runs still earn
        # the full time contribution; the Speedrun trial halves it, so only a
        # fast run keeps full time contribution (trials are inert in tests).
        if self.trials_enabled and self.current_trial == Trial.LONG_RUN:
            ideal_time = TIME_IDEAL * 2
        elif self.trials_enabled and self.current_trial == Trial.SPEEDRUN:
            ideal_time = TIME_IDEAL / 2
        else:
            ideal_time = TIME_IDEAL
        ideal_sq = ideal_time * ideal_time
        time_good = 1/(((self.run_time - ideal_time) / TIME_SCALE) * ((self.run_time - ideal_time) / TIME_SCALE) + 1)
        time_good -= (scale_sq / (scale_sq + ideal_sq)) * 1/(self.run_time * self.run_time + 1) # modulator: run_time = 0 -> time_good = 0
        dist_good = np.atan(total_distance / DISTANCE_SCALE) * 2 / np.pi
        uniq_good = unique_types / UNIQUE_SCALE
        return time_good, dist_good, uniq_good, unique_types

    def _compute_total_score(self):
        """Total score: (chips * mult) raised to a linear function of time,
        distance, and uniqueness. time_good max is 0.5, other two max are 1.
        Exp ranges from 0 to 2.
        """
        base = max(self.score_chips * self.score_mult, 1)
        time_good, dist_good, uniq_good, _ = self._score_factors()
        exponent = (time_good / 2 + dist_good + uniq_good) * (4 / 5)
        # The Inferno whole card raises the exponent itself, so it multiplies
        # the whole run's score by the chips x mult base raised to 0.07.
        if self._has_card(Card.INFERNO):
            exponent += INFERNO_EXPONENT_BONUS
        # The total stays a float internally (chips and mult can be
        # fractional); the UI rounds it to a tenth for display. Coerce to a
        # PLAIN Python float: _score_factors() returns numpy scalars, and a
        # numpy ``base ** exponent`` would leak a numpy float64 into
        # score_total, whose comparisons return numpy bools that later break
        # JSON saves (``run_results`` is persisted).
        return float(base ** exponent)

    def _fire_target(self):
        """How strong the marble-box fire should be right now (0..FIRE_MAX).

        The fire appears while a run is active and the score has passed the
        required score; it is larger the more the score beats the target (the
        excess as a fraction of the target, capped at FIRE_MAX_INTENSITY). It
        is zero once the run is over, so the fire dies down.
        """
        if not self.run_active or self.score_total < self.required_score:
            return 0.0
        excess = (self.score_total - self.required_score) / max(self.required_score, 1)
        return min(FIRE_MAX_INTENSITY, max(0.0, excess))

    def _update_fire(self, dt):
        """Move the marble-box fire toward its target, then let it die down.

        While a run is active and passed, the fire grows (larger the more the
        score beats the target). Once the run is over (or the score drops back
        below the requirement) it gradually decays to nothing.
        """
        target = self._fire_target()
        if self.fire_intensity < target:
            self.fire_intensity = min(target, self.fire_intensity + FIRE_RISE_SPEED * dt)
        else:
            self.fire_intensity = max(0.0, self.fire_intensity - FIRE_DECAY_SPEED * dt)
        if self.fire_intensity < 0.01:
            self.fire_intensity = 0.0

    def _count_fresh_touch(self, block):
        """Count one fresh touch of a block's types (for the repeats-only trial).

        A marble entering contact with a block counts one distinct touch of the
        block's shape (except the plain Rect wall), each of its real effects,
        and its scorer (except Start/Finish roles) — mirroring exactly which
        types the run's uniqueness ``touched_*`` sets record. The repeats-only
        trial turns a type's uniqueness on only after it has been touched twice.
        """
        if not (self.trials_enabled and self.current_trial == Trial.REPEATS_ONLY):
            return
        if block.shape != Shape.RECT:
            self.touch_shape_counts[block.shape] = self.touch_shape_counts.get(block.shape, 0) + 1
        for e in block.effects:
            if e != Effect.NONE:
                self.touch_effect_counts[e] = self.touch_effect_counts.get(e, 0) + 1
        if block.scorer != Scorer.START and block.scorer != Scorer.FINISH:
            self.touch_scorer_counts[block.scorer] = self.touch_scorer_counts.get(block.scorer, 0) + 1

    def _contact_normal(self, marble, block):
        """The unit collision normal of the marble's contact with a block.

        Physics records the normal it resolved against each block this frame
        (marble.contact_normals). When there is none — a pass-through field, or
        a contact resolved in an earlier frame — fall back to the direction
        from the block's center out to the marble.
        """
        normal = getattr(marble, "contact_normals", {}).get(block)
        if normal is None:
            offset = (np.array(block.rect.center, dtype=float)
                      - np.array(marble.position, dtype=float))
            length = float(np.linalg.norm(offset))
            normal = offset / length if length > 1e-9 else np.array([0.0, -1.0])
        normal = np.array(normal, dtype=float)
        length = float(np.linalg.norm(normal))
        return normal / length if length > 1e-9 else np.array([0.0, -1.0])

    def _split_marble(self, marble, block):
        """Splitter: spawn a copy of the marble travelling the other way.

        The copy's velocity is the velocity the marble ARRIVED at the block
        with, reflected over the collision normal from the block and then
        reversed, ``-reflect(v, n) = -v + 2 (v.n) n``, so the two halves leave
        the surface in opposite directions; the speed is unchanged. The copy is
        a full marble: it is simulated, it scores, it collides with the marble
        it came from (see PhysicsEngine.resolve_marble_collisions), and it must
        reach the finish like any other marble before the run can end.
        Splitting stops at MAX_MARBLES so the board can never grow an unbounded
        marble count.
        """
        if len(self.marbles) >= MAX_MARBLES:
            return None
        normal = self._contact_normal(marble, block)
        # The marble's velocity as it ARRIVED at the block: the collision
        # response has usually already removed the part heading into the
        # surface, so reflecting the post-impact velocity would fling the copy
        # at nearly nothing.
        incoming = np.array(
            getattr(marble, "contact_incoming", {}).get(block, marble.velocity),
            dtype=float)
        reflected = incoming - 2.0 * float(np.dot(incoming, normal)) * normal
        copy = Marble(float(marble.position[0]), float(marble.position[1]))
        # The copy inherits the marble's look and behavior (type, colors, mass,
        # bounciness, radius, size changes) and this run's trial state, so the
        # two halves stay identical apart from their velocity.
        copy.marble_type = marble.marble_type
        copy.color = marble.color
        copy.color2 = marble.color2
        copy.bouncy = marble.bouncy
        copy.restitution = marble.restitution
        copy.mass = marble.mass
        copy.radius = marble.radius
        copy.dead_zone = getattr(marble, "dead_zone", False)
        copy.finish_on_border = getattr(marble, "finish_on_border", False)
        copy.bouncy_castle = getattr(marble, "bouncy_castle", False)
        copy.effect_mass_mult = getattr(marble, "effect_mass_mult", 1.0)
        copy.start_block = getattr(marble, "start_block", None)
        copy.velocity = -reflected
        self.marbles.append(copy)
        self._spawn_score_particle(marble.position[0], marble.position[1],
                                   "Split", ORANGE)
        sounds.play_mech()
        return copy

    def _handle_block_contacts(self, blocks):
        if not self.run_active and not self.run_complete:
            return

        # Iterate over a snapshot: a splitter block adds a marble to
        # self.marbles while this loop runs (the copy is first simulated on the
        # next frame).
        for marble in list(self.marbles):
            # Locked-board walls are physical but never score: they are filtered
            # out here so they don't fire quick cards, count as touches, score,
            # or read as the first/last contacted block.
            contacts = [b for b in marble.collisions_this_tick
                        if not getattr(b, "is_board_wall", False)]
            last_contacts = list(marble.collisions_last_tick)
            # Quick cards armed by an earlier condition (their condition was
            # satisfied) pay now: the reward uses THIS (the next) block's hit
            # speed, exactly like a Quick block scorer.
            if self.armed_quick and any(b not in last_contacts for b in contacts):
                speed = max(np.linalg.norm(marble.velocity),
                            getattr(marble, "recent_speed", 0.0))
                gained = speed * QUICK_SCALE
                for card in list(self.armed_quick):
                    self.armed_quick.discard(card)
                    self.score_chips += gained
                    self._spawn_card_particle(card, self._particle_amount_text(gained), GREEN)
            for block in contacts:
                # Every block the marble touches this run contributes its type
                # to the end-of-run cash award (unique shapes/effects/scorers).
                if block.shape != Shape.RECT:
                    self.touched_shapes.add(block.shape)
                for e in block.effects:
                    if e != Effect.NONE:
                        self.touched_effects.add(e)
                if block.scorer != Scorer.START and block.scorer != Scorer.FINISH:
                    self.touched_scorers.add(block.scorer)
                # Shape/effect cards: each fresh collision with a matching
                # block grants +4 mult (once per collision, not every frame).
                if block not in last_contacts:
                    # A Key opens its matching Locks: a marble passing through a
                    # key block opens every lock block sharing its key number
                    # for the rest of this run.
                    if block_shape(block) == Shape.KEY:
                        self._unlock_matching_locks(block)
                    # Sound the impact: every real effect on the block rings its
                    # own sound (a plain effect-less block rings the neutral
                    # one), so the player hears what the marble just hit.
                    impacts = [e for e in block.effects if e != Effect.NONE]
                    if impacts:
                        for e in impacts:
                            sounds.play_effect(e)
                    else:
                        sounds.play_effect(Effect.NONE)
                    # The repeats-only trial counts DISTINCT fresh touches per
                    # type (a type qualifies once it's been touched twice).
                    self._count_fresh_touch(block)
                    # Track the run's first/last freshly-contacted blocks for
                    # Effective cards (Start cards check the first block after
                    # the start; End cards check the last block before the
                    # finish). Start/FINISH roles are not "blocks hit".
                    if (block.scorer != Scorer.START
                            and block.scorer != Scorer.FINISH):
                        if self._first_contact_block is None:
                            self._first_contact_block = block
                            # A Start-condition Effective/Summit/Airball card
                            # fires now that the first block after the start is
                            # known (Airball uses this marble's air streak).
                            cards.fire_first_block_cards(self, block, marble)
                        # Echo reads the block touched just before this one, so
                        # remember the current last block before overwriting it;
                        # Rally counts every fresh touch this run.
                        self._prev_contact_block = self._last_contact_block
                        self._last_contact_block = block
                        self.run_fresh_touches += 1
                        # Remember the run's opening blocks (in touch order) for
                        # Pedestal (retrigger the first few) and Watch (only the
                        # first few may score). Distinct blocks only: with two
                        # marbles the same block can be freshly touched twice,
                        # and that must not use up two slots. The list is
                        # capped, so a long run never grows it.
                        if (len(self.run_first_blocks) < WATCH_BLOCK_LIMIT
                                and block not in self.run_first_blocks):
                            self.run_first_blocks.append(block)
                        # The touching marble's airborne streak at this fresh
                        # contact: Airball end-condition cards reward the streak
                        # before the run's last block was touched, and an
                        # Airball fragile card rewards the streak before the
                        # broken block itself was touched.
                        self._last_contact_air = marble.air_streak
                        self._last_contact_speed = max(
                            float(np.linalg.norm(marble.velocity)),
                            getattr(marble, "recent_speed", 0.0))
                        block.touch_air_streak = marble.air_streak
                    self._apply_cards_on_collision(block, marble)
                if block.scorer == Scorer.FINISH:
                    marble.finished = True
                    continue
                # Scoring fires on the edge of a touch (block not touched last
                # tick) and only while the block still has triggers left. Each
                # block can score at most its trigger limit (once) per run.
                if block in last_contacts:
                    continue
                if block.triggers_left <= 0:
                    continue
                if self._apply_block_score_effect(marble, block):
                    block.triggers_left = max(0, block.triggers_left - 1)
                    # Portal pairs share one trigger count: using one portal
                    # uses up the pair, so the partner's count moves in step.
                    self._sync_portal_pair_triggers(block, blocks)
                    # A splitter splits the marble once per trigger: the copy is
                    # flung out along -reflect(v, n) (see _split_marble).
                    if block.has_effect(Effect.SPLITTER):
                        self._split_marble(marble, block)
                    # The Pedestal whole card retriggers the scorer of the first
                    # few blocks the marble touches each run: a free second
                    # score that does not consume another trigger (the same
                    # shape as the 8 ball's retrigger below).
                    if (self._has_card(Card.PEDESTAL)
                            and block in self.run_first_blocks[:PEDESTAL_RETRIGGERS]):
                        self._apply_block_score_effect(marble, block)
                    # The 8 ball has a 1/4 chance to retrigger the block's
                    # scoring effect on collision — a free second score that
                    # does not consume another trigger.
                    if (getattr(marble, "marble_type", 0) == MarbleType.EIGHT_BALL
                            and random.random() < 0.25
                            and block.scorer in (Scorer.CHIPS_ADD, Scorer.MULT_ADD,
                                                 Scorer.MULT_MUL, Scorer.QUICK,
                                                 Scorer.CASH, Scorer.SHARP,
                                                 Scorer.PARTS, Scorer.SHREDS,
                                                 Scorer.RUBBLE, Scorer.IDEAS,
                                                 Scorer.RANDOM, Scorer.EFFECTIVE,
                                                 Scorer.FRESH, Scorer.PICKY, Scorer.VOYAGER,
                                                 Scorer.SATANIC, Scorer.SUMMIT,
                                                 Scorer.AIRBALL, Scorer.SEED,
                                                 Scorer.DRILL, Scorer.LUCKY,
                                                 Scorer.ROOMY, Scorer.RALLY,
                                                 Scorer.ECHO, Scorer.POWERLINE,
                                                 Scorer.FRONTIER, Scorer.GILDED,
                                                 Scorer.BOMB, Scorer.CLUSTER,
                                                 Scorer.COLOSSUS, Scorer.UNDERTAKER,
                                                 Scorer.DEBT)):
                        self._apply_block_score_effect(marble, block)

        self.score_total = self._compute_total_score()

        if self.marbles and all(getattr(marble, "finished", False) for marble in self.marbles):
            # End-of-run cards (e.g. Explorer's distance xMult) adjust the score
            # before it is finalized.
            self._apply_cards_on_finish()
            self.score_total = self._compute_total_score()
            self.armed_quick.clear()
            self.run_active = False
            self.run_complete = True
            # ``bool(...)`` keeps the result a native Python bool (a numpy
            # comparison would store a numpy.bool_ that breaks JSON saves).
            cleared = bool(self.score_total >= self.required_score)
            self.run_cleared = cleared
            self.run_results.append(cleared)
            self._award_cash()
            if cleared:
                self.runs_cleared += 1
                # Beating a run with a trial reveals it in the collection.
                if self.current_trial is not None:
                    self._discover_trial(self.current_trial)
                # Beating the final boss (the 24th run) reveals it too.
                if self.final_boss is not None:
                    self._discover_final_boss(self.final_boss)
            else:
                self.failed_runs += 1
            # The run is done but progression is deferred: the player chooses
            # RETRY (undo the run) or CONTINUE (move to the next run).
            self.awaiting_after_run = True

    def _apply_xmult(self, factor):
        """Apply an xMult reward: the multiplier is MULTIPLIED by ``factor``.

        xMult always multiplies — there is no additive fallback. Every trigger
        applies its own factor again, so xMult compounds individually (each
        block or card fires for itself) and exponentially (their factors
        stack): a Slope xMult card hitting two Slope blocks gives
        1.25 x 1.25 = 1.5625, and one Sharp block with a trigger limit of 2
        gives 3 x 3 = 9 rather than 3 then +2. Returns the factor, which is the
        figure the reward particle shows.
        """
        self.score_mult *= factor
        return factor

    def _roll_random_output(self, scorer):
        """Pre-roll the result of a random-output scorer for this run.

        Lucky makes two independent rolls (a 1/3 chance of +130 chips and a
        separate 1/9 chance of $40 — it can win both, either, or neither);
        Random picks one of three rewards (+35 chips, +5 mult, +0.3 xMult),
        with the Rigged Casino card shifting the odds to chips:mult:xMult =
        1:3:9 instead of even thirds.
        """
        if scorer == Scorer.LUCKY:
            return {"chips": random.random() < 1 / 3,
                    "cash": random.random() < 1 / 9}
        roll = random.random()
        if self._has_card(Card.RIGGED_CASINO):
            reward = 0 if roll < 1 / 13 else (1 if roll < 4 / 13 else 2)
        else:
            reward = 0 if roll < 1 / 3 else (1 if roll < 2 / 3 else 2)
        return {"reward": reward}

    def _run_random_result(self, item, scorer):
        """This run's pre-rolled result for a random-output scorer item.

        The result is chosen BEFORE the run (see _roll_run_random_outputs) and
        kept on the item, so a scorer that triggers several times repeats the
        same result and RETRYING the run replays it exactly. An item that
        entered play after the opening roll (a block placed or a card bought
        mid-run) rolls on its first trigger instead.
        """
        rolls = getattr(item, "random_rolls", None)
        if rolls is None or rolls.get("scorer") != scorer:
            rolls = self._set_run_random_result(item, scorer)
        return rolls

    def _set_run_random_result(self, item, scorer):
        """Draw a fresh result for an item, replacing any earlier roll."""
        rolls = self._roll_random_output(scorer)
        rolls["scorer"] = scorer
        item.random_rolls = rolls
        return rolls

    def _roll_run_random_outputs(self):
        """Choose every random-output scorer's result before the run starts.

        Lucky and Random blocks on the board, and Random cards in the card
        area, all get a FRESH result for the coming run up front, so nothing
        about their outcome depends on when they happen to trigger.
        """
        for block in self.grid.values():
            if block.scorer in (Scorer.LUCKY, Scorer.RANDOM):
                self._set_run_random_result(block, block.scorer)
        for card in self.cards:
            meta = generic_card_meta(card.value)
            if meta is not None and meta[1] in (Scorer.RANDOM, Scorer.LUCKY):
                self._set_run_random_result(card, meta[1])

    def _watch_blocks_out_of_play(self, block):
        """True when the Watch card stops this block from contributing score.

        Watch ends the run at the ideal finish time and lets only the first
        WATCH_BLOCK_LIMIT blocks the marble touches contribute score; every
        later block's scorer pays nothing (its trigger is still spent, like any
        block whose reward comes out zero). Watch gates BLOCK scorers only —
        collision cards still fire on the touch, so a Watch run stays a
        card-driven build.
        """
        if not self._has_card(Card.WATCH):
            return False
        # A Spirit token is a start-of-run card-like payoff, not a block the
        # marble touched, so Watch never gates it.
        if getattr(block, "is_token", False):
            return False
        return block not in self.run_first_blocks

    def _apply_block_score_effect(self, marble, block):
        """Apply a block's scoring effect once; returns True if it scored.

        A no-scoring block still counts as "scored" (so it shows its used red
        state) but grants nothing; portals are exempt from the trigger
        behavior. The 8 ball calls this a second time to retrigger a block's
        scoring effect on collision.
        """
        if block.scorer == Scorer.NONE and not block.has_effect(Effect.PORTAL):
            return True
        # Watch: only the run's opening blocks may score (see
        # _watch_blocks_out_of_play). The trigger is still spent, so the block
        # still shows its used-up red state.
        if self._watch_blocks_out_of_play(block):
            return True
        if block.scorer not in (Scorer.NONE, Scorer.START, Scorer.FINISH):
            # Every real scorer rings its own sound as it triggers (the 8 ball's
            # retrigger rings it a second time; the Start/Finish roles pay
            # nothing, so they stay silent).
            sounds.play_scorer(block.scorer)
        if block.scorer == Scorer.CHIPS_ADD:
            self.score_chips += block.scorer_amount
            self._spawn_block_particle(
                block, self._particle_amount_text(block.scorer_amount), GREEN)
            return True
        if block.scorer == Scorer.MULT_ADD:
            self.score_mult += block.scorer_amount
            self._spawn_block_particle(
                block, self._particle_amount_text(block.scorer_amount), BLUE)
            return True
        if block.scorer == Scorer.SUMMIT:
            # Summit adds +0.75 mult for each unit (row) the block is above the
            # bottom row: a bottom-row block (y = GRID_HEIGHT - 1) adds 0, a
            # top-row block adds 0.5 * (GRID_HEIGHT - 1).
            rows_above = max(0, (GRID_HEIGHT - 1) - block.y)
            gained = block.scorer_amount * rows_above
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.AIRBALL:
            # Airball rewards the touching marble's airborne streak: +8 mult
            # (block.scorer_amount) per second the marble had NOT touched any
            # block (including Shape.None / pipes / portals) before this touch.
            # The streak is this marble's continuous air time ending now; a
            # marble that just touched something else has 0 air and grants
            # nothing (the trigger is still spent).
            gained = block.scorer_amount * getattr(marble, "air_streak", 0.0)
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.MULT_MUL:
            # xMult: every trigger multiplies the multiplier by the block's
            # factor, so repeated triggers compound (see _apply_xmult).
            amount = self._apply_xmult(block.scorer_amount)
            self._spawn_block_particle(
                block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer == Scorer.QUICK:
            # Quick blocks reward the marble's speed at impact. Use the marble's
            # recent peak speed as a floor, so effects that hold or pin the
            # marble (rotate, gravity, accelerator, black hole, slippery,
            # fragile) don't read as zero at the exact moment of scoring.
            speed = max(np.linalg.norm(marble.velocity),
                        getattr(marble, "recent_speed", 0.0))
            gained = speed * QUICK_SCALE
            self.score_chips += gained
            self._spawn_block_particle(block, self._particle_amount_text(gained), GREEN)
            return True
        if block.scorer == Scorer.CASH:
            # Cash blocks pay out money instead of score.
            gained = int(block.scorer_amount)
            self.cash += gained
            self.run_cash_gained += gained
            self._spawn_block_particle(block, f"${gained}", YELLOW)
            return True
        if block.scorer == Scorer.SHARP:
            # Sharp blocks triple the multiplier (and may be destroyed later).
            # Repeated triggers triple again, so they compound (see
            # _apply_xmult).
            amount = self._apply_xmult(block.scorer_amount)
            self._spawn_block_particle(
                block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer == Scorer.SATANIC:
            # Satanic blocks multiply the multiplier by 6.66, and are
            # permanently destroyed once a marble touches them and leaves.
            amount = self._apply_xmult(block.scorer_amount)
            self._spawn_block_particle(
                block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer in (Scorer.SHREDS, Scorer.RUBBLE,
                            Scorer.IDEAS, Scorer.PICKY):
            # Point scorers bank a fraction of a point per trigger
            # (auto-converted into a reward after a run).
            points = resource_points_for(block.scorer, block.scorer_amount)
            self._spawn_block_particle(block, points_text(points), ORANGE)
            self._add_resource_points(block.scorer, points)
            return True
        if block.scorer == Scorer.PARTS:
            # Parts grants a random component immediately (no point system).
            self._grant_random_component()
            self._spawn_block_particle(block, "Component", ORANGE)
            return True
        if block.scorer == Scorer.FRESH:
            # Fresh grants one free shop reroll immediately (no point system).
            # The run-gain counter remembers it, so a retry can take it back
            # without touching rerolls banked by earlier runs.
            self.free_rerolls += 1
            self.free_rerolls_run_gain += 1
            self._spawn_block_particle(block, "Reroll", ORANGE)
            return True
        if block.scorer == Scorer.VOYAGER:
            # Voyager adds its own rate for every PIXEL the touching marble had
            # already traveled this run before touching this block: the rolled
            # magnitude IS the mult per pixel (0.01 at the average), so 55 px of
            # travel at 0.01 pays +0.55 mult, kept as a float.
            gained = block.scorer_amount * getattr(marble, "distance", 0.0)
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.RANDOM:
            # Random blocks grant one of three rewards: +35 chips, +5 mult, or
            # +0.3 xMult. The reward is chosen BEFORE the run (see
            # _roll_run_random_outputs), so every trigger of this block gives
            # the same one and retrying the run replays it. The Rigged Casino
            # card rigs the odds of that pre-roll (chips:mult:xMult = 1:3:9,
            # instead of the even thirds).
            reward = self._run_random_result(block, Scorer.RANDOM)["reward"]
            if reward == 0:
                self.score_chips += 35
                self._spawn_block_particle(
                    block, self._particle_amount_text(35), GREEN)
            elif reward == 1:
                self.score_mult += 5
                self._spawn_block_particle(
                    block, self._particle_amount_text(5), BLUE)
            else:
                factor = 1.3  # +0.3 xMult
                amount = self._apply_xmult(factor)
                self._spawn_block_particle(
                    block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer == Scorer.SEED:
            # Seed: +scorer_amount mult for each Seed block on the board (the
            # touched block counts itself). The Garden card doubles the
            # per-seed mult (+3 -> +6).
            seed_count = sum(
                1 for b in self.grid.values() if b.scorer == Scorer.SEED)
            per_seed = block.scorer_amount
            if self._has_card(Card.GARDEN):
                per_seed *= 2
            gained = per_seed * seed_count
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.DRILL:
            # Drill: marks locked board squares to unlock after the run. They
            # are granted after a run only (retrying discards them), matching
            # the cash/resource reward rule. The magnitude rolls in tenths, so
            # the SQUARE COUNT is rounded to a whole square — never 0 — because
            # the run-end grant slices along a list of candidates.
            units = max(1, round(block.scorer_amount))
            self.drill_run_units += units
            self._spawn_block_particle(
                block, self._particle_amount_text(units), ORANGE)
            return True
        if block.scorer == Scorer.LUCKY:
            # Lucky makes two INDEPENDENT rolls: a 1/3 chance to add +130 chips
            # and a separate 1/9 chance to add $40 — it can win both, either,
            # or neither. Both rolls are chosen BEFORE the run (see
            # _roll_run_random_outputs), so a retry replays the same outcome.
            result = self._run_random_result(block, Scorer.LUCKY)
            if result["chips"]:
                self.score_chips += 130
                self._spawn_block_particle(block, self._particle_amount_text(130), GREEN)
            if result["cash"]:
                self.cash += 40
                self.run_cash_gained += 40
                self._spawn_block_particle(block, "$40", YELLOW)
            return True
        if block.scorer == Scorer.ROOMY:
            # Roomy: +scorer_amount chips for each currently-unlocked board
            # unit (the bigger the unlocked region, the more the marble earns).
            gained = block.scorer_amount * len(self.unlocked_cells)
            if gained > 0:
                self.score_chips += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), GREEN)
            return True
        if block.scorer == Scorer.RALLY:
            # Rally: +scorer_amount mult for each fresh block contact this run
            # before this one. Re-touches count; this block's own touch is
            # already in run_fresh_touches, so subtract it.
            gained = block.scorer_amount * max(0, self.run_fresh_touches - 1)
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.ECHO:
            # Echo re-fires the scoring effect of the block the marble touched
            # immediately before this one (its own trigger is still consumed,
            # but the copied block's is not). Roles, None, and other Echo
            # blocks are skipped so copies can't chain.
            prev = getattr(self, "_prev_contact_block", None)
            if (prev is not None and prev is not block
                    and prev.scorer not in (Scorer.NONE, Scorer.START,
                                            Scorer.FINISH, Scorer.ECHO)):
                self._apply_block_score_effect(marble, prev)
            return True
        if block.scorer == Scorer.POWERLINE:
            # Powerline: +scorer_amount chips for each block in its row
            # (including itself).
            row_count = sum(1 for b in self.grid.values() if b.y == block.y)
            gained = block.scorer_amount * row_count
            if gained > 0:
                self.score_chips += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), GREEN)
            return True
        if block.scorer == Scorer.FRONTIER:
            # Frontier: +scorer_amount mult for each ORTHOGONAL neighbour that
            # is still a locked board unit, or that is the outer board border —
            # the unexplored territory the block faces. An unlocked (already
            # settled) neighbour pays nothing, so on a fully unlocked board a
            # block pays only for the outer borders it touches (a corner
            # touches two).
            units = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = block.x + dx, block.y + dy
                if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                    units += 1  # the outer board border
                elif (nx, ny) not in self.unlocked_cells:
                    units += 1  # a locked board unit
            gained = block.scorer_amount * units
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.CLUSTER:
            # Cluster: +scorer_amount mult for each block ORTHOGONALLY adjacent
            # to it (up/down/left/right; diagonals don't count, and its own
            # cell is not a neighbour). A wall or a pillar pays well.
            adjacent = sum(
                1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (block.x + dx, block.y + dy) in self.grid)
            gained = block.scorer_amount * adjacent
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.COLOSSUS:
            # Colossus rewards a marble that has grown past its base size:
            # +scorer_amount (0.1) xMult for each pixel of radius above the base
            # MARBLE_RADIUS, so a marble doubled twice by Growing blocks (radius
            # 32) turns +0.1 into +2.4 xMult. A marble at (or below) its base
            # size gains nothing, but its trigger is still spent.
            gained = max(0.0, marble.radius - MARBLE_RADIUS) * block.scorer_amount
            if gained > 0:
                amount = self._apply_xmult(1 + gained)
                self._spawn_block_particle(
                    block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer == Scorer.UNDERTAKER:
            # Undertaker: +scorer_amount (15) mult for each block destroyed
            # during this run before the touch — a fragile block breaking, or a
            # Satanic block dying (see run_blocks_destroyed).
            gained = block.scorer_amount * self.run_blocks_destroyed
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.DEBT:
            # Debt pays chips up front and takes the run's interest: the
            # $1-per-$10 end-of-run award is cancelled (see _award_cash).
            # Later triggers of the same block still pay their chips.
            gained = int(block.scorer_amount)
            self.score_chips += gained
            self.debt_run_triggered = True
            self._spawn_block_particle(block, self._particle_amount_text(gained), GREEN)
            return True
        if block.scorer == Scorer.GILDED:
            # Gilded: +1/6 of the current chips as mult.
            gained = self.score_chips / 6.0
            if gained > 0:
                self.score_mult += gained
                self._spawn_block_particle(
                    block, self._particle_amount_text(gained), BLUE)
            return True
        if block.scorer == Scorer.BOMB:
            # Bomb: primes this block to detonate after a run — it then unlocks
            # every board unit within 1 cell (diagonals included) and destroys
            # itself.
            self.bomb_cells.add((block.x, block.y))
            self._spawn_block_particle(block, "Bomb", ORANGE)
            return True
        if block.scorer == Scorer.EFFECTIVE:
            # Effective blocks reward blocks built with at least two (real)
            # effects; otherwise the trigger still counts but grants nothing.
            real_effects = [e for e in block.effects if e != Effect.NONE]
            if len(real_effects) >= 2:
                factor = block.scorer_amount  # +1 xMult (default 2.0)
                amount = self._apply_xmult(factor)
                self._spawn_block_particle(
                    block, self._particle_amount_text(amount), RED)
            return True
        return False

    def _award_cash(self):
        """Award cash at the end of a run based on how much the player beat the required score."""
        # Guard against log(0) / log(1): a score of 0 or a required score of 1
        # must not produce -inf or a divide-by-zero.
        score = max(self.score_total, 1)
        required = max(self.required_score, 2)
        # The Empty pockets trial skips ONLY the score-based part of the award
        # (the log-ratio gain): the flat $20, the interest on cash held, and
        # any Cash-card payouts still land.
        if self.trials_enabled and self.current_trial == Trial.EMPTY_POCKETS:
            score_gain = 0
        else:
            score_gain = max(0, int(CASH_SCALE * (np.log(score) - np.log(required))))
        # Every part of the award is kept separately so the cash readout can
        # show where the run's money came from (see _cash_breakdown_rows).
        base_cash = 20
        # A Debt block that triggered this run cancels the interest entirely:
        # the run pays nothing for the cash the player holds. The Compound
        # Interest whole card doubles what is left.
        interest = 0 if self.debt_run_triggered else self.cash // 10
        if self._has_card(Card.COMPOUND_INTEREST):
            interest *= 2
        # Cash earned by Cash-scorer cards this run is paid out here, folded
        # into the run's end-of-run award. Retrying the run undoes the whole
        # award, so that cash only sticks after a run.
        card_cash = self.card_cash_run_gain
        self.card_cash_run_gain = 0
        # Cash the Cash and Lucky scorer BLOCKS paid out directly during the
        # run was already added to the player's cash as it triggered; it is
        # part of the run's earnings but not of this award.
        scorer_cash = self.run_cash_gained
        self.run_cash_gained = 0
        award = score_gain + base_cash + interest + card_cash
        self.cash += award
        # The run's "cash gained" covers every dollar the run earned: the whole
        # award PLUS the scorer cash already paid out mid-run, so the display
        # (and the retry rollback in _retry_run) covers every dollar earned.
        self.last_run_cash_gained = award + scorer_cash
        self.last_run_cash_breakdown = {
            "base": base_cash,
            "interest": interest,
            "score": score_gain,
            "cards": card_cash,
            "scorers": scorer_cash,
            # True when a Debt block cancelled this run's interest, so the
            # breakdown can say why it is $0.
            "debt": bool(self.debt_run_triggered),
        }

    def _reset_wrecking_run_gain(self):
        """Start a fresh run with no Fragile Breaks (Wrecking Ball) gains."""
        self.wrecking_run_gain = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                                  Scorer.MULT_MUL: 1.0}

    def _commit_wrecking_run_gain(self):
        """Fold a finished run's Fragile Breaks gains into the permanent bonus.

        Called after a run: the per-run gains (chips
        and mult added, xMult multiplied) become part of the saved permanent
        wrecking_bonus, which applies at the start of every future run.
        """
        run_gain = self.wrecking_run_gain
        bonus = self.wrecking_bonus
        bonus[Scorer.CHIPS_ADD] += run_gain[Scorer.CHIPS_ADD]
        bonus[Scorer.MULT_ADD] += run_gain[Scorer.MULT_ADD]
        bonus[Scorer.MULT_MUL] *= run_gain[Scorer.MULT_MUL]
        self._reset_wrecking_run_gain()

    def _continue_run(self):
        """Move on to the next run after the player clicks CONTINUE.

        Only advances when a finished run is awaiting the CONTINUE choice, so
        pressing Y mid-run (or during the build phase) can't skip ahead.
        """
        if not (self.run_complete and self.awaiting_after_run):
            return
        # Whether the just-finished run was cleared, captured before it is
        # reset below (the boss-run branch below needs it).
        cleared_this_run = self.run_cleared
        # Wrecking Ball (Fragile Breaks): the gains earned during the finished
        # run become permanent after the run (retrying discards them).
        self._commit_wrecking_run_gain()
        # Cards owned DURING the finished run are destroyed when the player
        # moves on, BEFORE any reward grants below (so a card that the continue
        # itself grants is not instantly destroyed by it).
        # Sharp-scorer blocks in the marble box have a 1/4 chance to be
        # destroyed when the player moves on from a run.
        for key, block in list(self.grid.items()):
            if block.scorer == Scorer.SHARP and random.random() < 0.25:
                self.grid.pop(key, None)
        # Sharp-scorer cards (a generic card whose scorer half is Sharp) also
        # have a 1/4 chance to be destroyed after each run.
        if self.cards:
            kept_cards = []
            destroyed_selected = False
            for card in self.cards:
                meta = generic_card_meta(card.value)
                if meta is not None and meta[1] == Scorer.SHARP \
                        and random.random() < 0.25:
                    if card is self.selected_toolbox_item:
                        destroyed_selected = True
                    continue
                kept_cards.append(card)
            if len(kept_cards) != len(self.cards):
                self.cards[:] = kept_cards
                if destroyed_selected:
                    self._clear_toolbox_selection()
        # Satanic and Bomb cards are a one-run deal: they are destroyed after a
        # run for good (retrying keeps them), whether or not they fired. A Bomb
        # card primes the cell of the block its condition points at, exactly
        # like a Bomb block, and goes off with it.
        if self.cards:
            kept_cards = []
            destroyed_selected = False
            for card in self.cards:
                meta = generic_card_meta(card.value)
                if meta is not None and meta[1] in (Scorer.SATANIC, Scorer.BOMB):
                    if card is self.selected_toolbox_item:
                        destroyed_selected = True
                    continue
                kept_cards.append(card)
            if len(kept_cards) != len(self.cards):
                self.cards[:] = kept_cards
                if destroyed_selected:
                    self._clear_toolbox_selection()
        # Resource points earned by Parts/Shreds/Rubble/Ideas scorers during
        # the finished run move into the bank (and convert into rewards) after
        # a run only; retrying discards them. These grants run
        # AFTER the card destruction above, so a freshly granted card survives.
        self._commit_resource_points()
        # Bomb blocks touched this run detonate after a run: each unlocks its
        # 1-cell radius (diagonals included) and destroys itself. The blast goes
        # FIRST, before the Drill and Conquistador grants below, because it is a
        # fixed shape while those grants PICK squares off the locked frontier
        # (see _grant_locked_units): a drill granted first can have its squares
        # land inside the radius the bomb was about to unlock anyway and be
        # swallowed by it, so the board grows by fewer squares than the drill
        # promised — and with the blast announced last its message buried the
        # drill's, making the block look like it had done nothing at all.
        blasted = self._detonate_bombs(announce=False)
        # Drill-scorer blocks touched this run unlock their locked board
        # squares after a run (retrying discards the pending
        # drills); the Conquistador card unlocks 4 more after every run. The
        # squares only land after a run, so retrying can't farm
        # board expansions.
        drilled = 0
        if self.drill_run_units:
            drilled = self._grant_locked_units(self.drill_run_units,
                                               announce=False)
            self.drill_run_units = 0
        conquered = (self._grant_locked_units(4, announce=False)
                     if self._has_card(Card.CONQUISTADOR) else 0)
        self._announce_board_expansion(blasted, drilled, conquered)
        # 1000-handed: after every run, its thousand hands fetch one random
        # action (the same grant the Ideas conversion gives; a full action area
        # refuses it, and the offer is simply withheld).
        if self._has_card(Card.THOUSAND_HANDED) and self._grant_random_action():
            self._set_shop_message(
                f"1000-handed grants {self._item_name(self.actions[-1])}")
        # Spirit tokens spend a run of coverage; Satanic and Sharp tokens obey
        # their scorer's own destruction rules (see _advance_tokens).
        self._advance_tokens()
        self.awaiting_after_run = False
        self.run_complete = False
        self.run_cleared = False
        # The finished run is COMMITTED now, so the free rerolls its Fresh hits
        # banked are the player's to keep: clearing the per-run counter here
        # (rather than leaving reset_run to do it) keeps that rollback from
        # taking a committed run's rerolls back when the next run is built,
        # started and restarted.
        self.free_rerolls_run_gain = 0
        # Choose the next run's trial now, before the run starts, so the info
        # box shows it during setup (a new round draws its own trials here, see
        # _choose_trial). The final boss run (run 24) has a boss instead of a
        # trial.
        if self.run_number == TOTAL_RUNS - 2:
            self.current_trial = None
        else:
            self._choose_trial(self.run_number + 1)
        # The just-finished run's trial effects are spent: clear the state so
        # the next run's trial (chosen above) re-applies fresh when it starts.
        self.trial_maxed_blocks = set()
        self.disabled_card = None
        self.deal_broken_cards = set()
        self.trial_fragile_blocks = set()
        for block in self.grid.values():
            block.trial_fragile = False
        self.trial_marble_weight = 1.0
        self.shop.refresh()
        # Slim pickings removes two random shop options for this run.
        if self.trials_enabled and self.current_trial == Trial.SLIM_PICKINGS:
            self._trim_shop_for_trial()
        self.run_number += 1
        # Once the player has clicked CONTINUE on a game-over screen, the
        # overlay never shows again for this save: those runs just advance
        # normally (the else below), so the game keeps going endless.
        if not self.continue_past_game_over and self.failed_runs >= 3:
            # Defeat: three lost runs ends the game immediately with a game
            # over screen (the player can retry a just-finished run to undo a
            # loss, but once a third loss is confirmed the game is over).
            self.game_over = True
            self.game_won = False
            self.game_perfect = False
            self._award_defeat_dice()
        elif not self.continue_past_game_over and self.run_number >= TOTAL_RUNS:
            # The 24th run is a boss run: it must be CLEARED to win. Clearing
            # it wins (a perfect win if every run was cleared); failing it is
            # a loss, and a player reaching run 24 has at most 2 prior losses
            # (3 losses ends the game earlier), so failing it ends in defeat.
            self.game_over = True
            if cleared_this_run and self.runs_cleared >= REQUIRED_RUNS_TO_WIN:
                self.game_won = True
                self.game_perfect = self.runs_cleared == TOTAL_RUNS
            else:
                self.game_won = False
                self.game_perfect = False
                self._award_defeat_dice()
        else:
            # Advance to the next run with its (round-based) score target,
            # grown by the save's own difficulty (1.6x on difficulty 1, 2x on
            # the rest — see Difficulty.SCORE_GROWTH).
            self.round_index = self.run_number // RUNS_PER_ROUND
            self.run_in_round = self.run_number % RUNS_PER_ROUND
            self.required_score = get_next_required_score(self.run_number,
                                                          self.score_growth)
            # The 24th (last) run is the final boss run: pick a boss now so its
            # modifier applies when the run starts. Sky High triples the target
            # the player must beat.
            if self.run_number == TOTAL_RUNS - 1:
                self.final_boss = random.choice(FinalBoss.ORDER)
                if self.final_boss == FinalBoss.SKY_HIGH:
                    self.required_score *= 3
            else:
                # Past the boss run the game is endless, and no final boss
                # applies: one left over from run 24 would keep modifying every
                # run that follows and lock the trial display for good.
                self.final_boss = None

    def _begin_endless_play(self):
        """Keep playing after the game-over screen: set the next run up.

        The run that ended on the game-over screen never took _continue_run's
        normal advance path (the defeat win/loss branch stopped before it), so
        the next run's target, round and run-in-round are computed here, and no
        final boss applies. The screen itself never shows again for this save
        (see continue_past_game_over).
        """
        self.game_over = False
        self.game_won = False
        self.game_perfect = False
        self.continue_past_game_over = True
        self.final_boss = None
        self.round_index = self.run_number // RUNS_PER_ROUND
        self.run_in_round = self.run_number % RUNS_PER_ROUND
        self.required_score = get_next_required_score(self.run_number,
                                                      self.score_growth)

    def _award_defeat_dice(self):
        """Award metagame dice for a defeat: (run number - 3) squared.

        Run #1 is the first run; ``self.run_number`` was already advanced to
        the just-completed run when the defeat triggered, so this is the run
        the player was on at the game over.
        """
        gained = (self.run_number - 3) ** 2
        gained = max(0, gained)
        self.game_over_dice_gained = gained
        metagame.add_dice(gained)

    def _return_to_main_menu(self):
        """Leave the finished game and go back to the title screen."""
        # Autosave the current game to its slot before leaving, so loading the
        # slot resumes where the player left off (mirrors the QUIT autosave).
        if self.save_slot is not None:
            self._retry_run()
            save_system.save_game(self)
        self.reset_game()
        self.game_over = False
        self.title_screen = True
        self.achievements_open = False
        self.marble_selecting = False
        self.upgrades_open = False
        self.collection_open = False
        self.save_slot = None

    def _buy_metagame_upgrade(self, upgrade_id):
        """Spend dice on a permanent upgrade from the UPGRADES tab."""
        if metagame.buy_upgrade(upgrade_id):
            self._set_shop_message("Upgrade purchased")
        else:
            self._set_shop_message("Not enough dice")

    def _retry_run(self):
        """Undo the completed run so the game acts as if it had not been played."""
        # True only when a FINISHED run is waiting for its RETRY/CONTINUE
        # choice — a real retry. The save/quit/menu paths also call this while
        # the player is still BUILDING (nothing to undo), so the run-scoped
        # rollbacks below must not take anything permanent with them.
        retrying = self.awaiting_after_run
        if retrying:
            # Undoing a run sounds like resetting it.
            sounds.play_reset()
            # The finished run's own records are taken back here — and ONLY
            # here, because every one of them is still standing during the
            # build phase after a CONTINUE: the save (P), quit and MAIN MENU
            # paths all call this too, and must not delete a committed run's
            # result, its win/loss, or the cash award already in the wallet.
            if self.run_results:
                self.run_results.pop()
            if self.run_cleared:
                self.runs_cleared = max(0, self.runs_cleared - 1)
            else:
                self.failed_runs = max(0, self.failed_runs - 1)
            self.cash -= self.last_run_cash_gained
            self.last_run_cash_gained = 0
            # The breakdown describes the run that was just undone, so it goes
            # too (the readout falls back to its "no run finished yet" note).
            self.last_run_cash_breakdown = {}
            # Wrecking Ball: retrying the run discards the gains it earned
            # (they only become permanent after a run).
            self._reset_wrecking_run_gain()
        # Resource points: a retry is a full do-over, so this run's pending
        # gains AND every point banked from earlier runs are reset to zero
        # (a NEW run keeps the bank — see _commit_resource_points). Rewards
        # those points already converted into (a granted card/block/action, or
        # a Picky bonus shop slot) are not points and stay.
        self.shred_run_gain = 0
        self.rubble_run_gain = 0
        self.idea_run_gain = 0
        self.option_run_gain = 0
        if retrying:
            self.shred_points = 0
            self.rubble_points = 0
            self.idea_points = 0
            self.option_points = 0
            # Free rerolls banked by Fresh hits are per-run resources too, but
            # only the ones THIS RUN granted are taken back: rerolls banked by
            # earlier runs are not the retried run's to lose. (Spending is not
            # un-spent — the count just can't go below zero.)
            self.free_rerolls = max(0, self.free_rerolls - self.free_rerolls_run_gain)
        self.free_rerolls_run_gain = 0
        # Cash earned by Cash cards this run was already folded into the run's
        # award (and undone above by the cash rollback); clear any remainder.
        self.card_cash_run_gain = 0
        # Drill-scorer locked squares earned this run are discarded on retry
        # (they only unlock after a run).
        self.drill_run_units = 0
        # Rally/Echo/Bomb run state is discarded on retry too (it only pays
        # out after a run, and a Bomb never detonates on
        # a retry).
        self.run_fresh_touches = 0
        self._prev_contact_block = None
        self.bomb_cells = set()
        self.awaiting_after_run = False
        self.run_complete = False
        self.run_cleared = False
        # Redoing the run re-applies the same trial.
        self.reset_run(False)
        self.run_active = False

    def upgrade_card_rect(self, index):
        """The screen rect for an upgrade card (index 0..2) on the UPGRADES tab."""
        card_w, card_h = 360, 200
        gap = 28
        x0 = (SCREEN_WIDTH - (3 * card_w + 2 * gap)) // 2
        return pygame.Rect(x0 + index * (card_w + gap), 250, card_w, card_h)

    def _difficulty_at(self, pos):
        """The difficulty level of the new-save screen's button at a position.

        Returns a Difficulty id, or None when the position is off the picker.
        """
        for i, level in enumerate(Difficulty.ORDER):
            if self.difficulty_button_rect(i).collidepoint(pos):
                return level
        return None

    def difficulty_button_rect(self, index):
        """The screen rect for a difficulty button (index into Difficulty.ORDER)
        on the new-save screen.

        The picker is a column down the LEFT margin of the screen: the marble
        cards are centred and 520 wide, so they leave that margin free for the
        four levels and the chosen level's description underneath.
        """
        button_w, button_h, gap = 280, 60, 10
        return pygame.Rect(30, 280 + index * (button_h + gap), button_w, button_h)

    def marble_card_rect(self, index):
        """The screen rect for a marble-type card (index into MarbleType.ORDER)
        on the marble-selection screen.

        The cards stack from a fixed top edge and are sized so every type fits
        above the BACK button row (the toggle sits below it).
        """
        n = max(1, len(MarbleType.ORDER))
        card_w = 520
        gap = 6
        top = 196
        bottom_limit = MARBLE_BACK_BUTTON_RECT.top - 16
        card_h = int((bottom_limit - top - (n - 1) * gap) / n)
        x = (SCREEN_WIDTH - card_w) // 2
        y = top + index * (card_h + gap)
        return pygame.Rect(x, y, card_w, card_h)

    def _marble_preview(self, marble_type):
        """A throwaway marble set up to preview a type on the selection screen."""
        preview = Marble(0, 0)
        preview.marble_type = marble_type
        if marble_type == MarbleType.RUBBER_BALL:
            preview.color = RUBBER_BALL_COLORS[0]
            preview.color2 = RUBBER_BALL_COLORS[1]
        elif marble_type == MarbleType.PING_PONG:
            preview.color = PING_PONG_COLORS[0]
            preview.color2 = PING_PONG_COLORS[1]
        preview.velocity = np.array([0.0, 0.0])
        preview.spin_angle = 0.0
        return preview

    def _collection_entries(self):
        """Every collection entry: (kind, value, name, description, has_icon,
        discovered). Undiscovered entries show \"???\" for name and description."""
        entries = []
        # Only the indivisible whole cards appear in the collection: every
        # splittable card is represented by its condition + scorer halves, and
        # each condition is its own collection entry.
        for value in Card.ORDER:
            d = collection.is_card_discovered(value)
            entries.append(("card", value, Card.name(value) if d else "???",
                            Card.description(value) if d else "???", True, d))
        for value in CONDITION_ORDER:
            d = collection.is_condition_discovered(value)
            entries.append(("condition", value, Condition.name(value) if d else "???",
                            condition_description(value) if d else "???", True, d))
        for value in Action.ORDER:
            d = collection.is_action_discovered(value)
            entries.append(("action", value, Action.name(value) if d else "???",
                            Action.description(value, 1) if d else "???", True, d))
        for value in Shape.ORDER:
            d = collection.is_component_discovered(Component.SHAPE, value)
            entries.append(("shape", value, Shape.name(value) if d else "???",
                            shape_description(value) if d else "???", True, d))
        for value in Effect.ORDER:
            d = collection.is_component_discovered(Component.EFFECT, value)
            entries.append(("effect", value, Effect.name(value) if d else "???",
                            effect_description(value) if d else "???", True, d))
        for value in Scorer.ORDER:
            d = collection.is_component_discovered(Component.SCORER, value)
            entries.append(("scorer", value, Scorer.name(value) if d else "???",
                            scorer_description(value, Scorer.DEFAULT_AMOUNT.get(value, 0))
                            if d else "???", True, d))
        for value in Trial.ORDER:
            d = collection.is_trial_discovered(value)
            entries.append(("trial", value, Trial.name(value) if d else "???",
                            Trial.description(value) if d else "???", False, d))
        for value in FinalBoss.ORDER:
            d = collection.is_final_boss_discovered(value)
            entries.append(("final_boss", value, FinalBoss.name(value) if d else "???",
                            FinalBoss.description(value) if d else "???", False, d))
        return entries

    def _toggle_crt_filter(self):
        """F2: switch the CRT screen filter on and off, and remember it."""
        self.crt_filter = not self.crt_filter
        metagame.set_crt_filter(self.crt_filter)
        self._set_shop_message(
            f"CRT filter {'on' if self.crt_filter else 'off'}")

    def _present(self):
        """Show the frame that has just been drawn (see run).

        Every screen is drawn into the off-screen frame buffer (self.screen),
        filtered there when the CRT filter is on (see crt.apply), and only then
        blitted to the window in one go: the window never shows a half-filtered
        frame, which is what used to make the picture strobe between filtered
        and unfiltered. Nothing else in the game presents a frame, so this is
        the only flip. F2 toggles the filter.
        """
        if self.crt_filter:
            crt.apply(self.screen)
        self.display.blit(self.screen, (0, 0))
        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            ui.draw(self)
            self._present()
            self.clock.tick(FPS)
        
        pygame.quit()


# The drawing helpers and particle/popup classes live in ui.py; re-export them
# at module scope so the rest of the code and the tests can keep referring to
# them as main.draw_card / main.ScoreParticle / ... without change.
ScoreParticle = ui.ScoreParticle
TrailParticle = ui.TrailParticle
Popup = ui.Popup
draw_card = ui.draw_card
draw_card_back = ui.draw_card_back
draw_marble_box = ui.draw_marble_box
draw_shop_item = ui.draw_shop_item
make_icon = ui.make_icon

# Thin delegating method wrappers: all the actual drawing lives in ui.py, but
# call sites and tests can keep using them as methods (block.draw(screen),
# game.draw(), game.draw_toolbox(), ...) unchanged.
Block.draw = ui.draw_block
Block._draw_effect_icon = ui._draw_block_effect_icon
Marble.draw = ui.draw_marble
Game.draw = ui.draw
Game.draw_toolbox = ui.draw_toolbox
Game.draw_sidebar = ui.draw_sidebar
Game.draw_upgrade_overlay = ui.draw_upgrade_overlay
Game.draw_trial_box = ui.draw_trial_box
Game._draw_item_info = ui.draw_item_info
Game._info_layout = ui.info_layout
Game._info_box_rect = ui.info_box_rect

if __name__ == "__main__":
    # First real launch: move any legacy root saves/achievements/collection/
    # metagame data into the default profile_1, then activate the remembered
    # current profile before building the game.
    profiles.migrate_legacy()
    profiles.switch_to(profiles.current_profile())
    game = Game()
    game.run()