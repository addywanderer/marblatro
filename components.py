"""Component definitions and metadata for Marblatro.

This module is the single source of truth for what a component is and how it
is described and priced:

- The ``Shape``, ``Effect``, and ``Scorer`` enums. Each component is
  identified by an integer ID — the class constant itself (e.g.
  ``Shape.PIPE == 6``, ``Effect.ROTATE == 7``, ``Scorer.CHIPS_ADD == 1``).
- Each component's display name (``*.NAMES``).
- Each scorer's color (``Scorer.COLORS``) and default amount
  (``Scorer.DEFAULT_AMOUNT``).
- The one-line descriptions (``shape_description`` / ``effect_description`` /
  ``scorer_description``).
- The ``Component`` purchase piece (kind, value/id, amount, price, name).
- The fixed price table (``COMPONENT_PRICES``) and block pricing
  (``block_price_for``).

Game logic (``Block``, ``Marble``, the shop, the toolbox, the assembler, etc.)
lives in ``main.py`` and imports these names from here.
"""

import math
from typing import ClassVar

# --- Colors used by the component metadata (scorer colors) ---
# Defined here so this module is self-contained (main.py has its own copies
# of the same RGB values for the rest of the game's drawing). GRAY is the
# neutral fallback (the None scorer); ORANGE is Quick's classic hue. Every
# scorer in Scorer.COLORS is chosen to be DIFFERENTIABLE from every other
# scorer: no two share a hue family at a similar brightness, so even a glance
# tells +Chips from xMult or Rubble from Drill. Muted/pastel tones (paper
# tan, brown, steel blue, pale cyan, periwinkle, white ghost, etc.) are used
# on purpose for the non-score scorers, while the vivid pure hues stay on the
# icons (+Chips green, +Mult blue, xMult violet, Cash yellow, Satanic red).
# WHITE is the single face color every condition tile uses.
GRAY = (128, 128, 128)
ORANGE = (255, 165, 0)
WHITE = (255, 255, 255)


def shade(color, factor):
    """Blend a colour toward white (``factor`` > 0) or black (``factor`` < 0).

    ``factor`` is the fraction of the way to the target, so 0.3 is 30% lighter
    and -0.3 is 30% darker. Used to build a tile's palette (and the panels that
    echo it) out of one base colour.
    """
    target = 255 if factor >= 0 else 0
    amount = abs(factor)
    return tuple(round(c + (target - c) * amount) for c in color)


def color_gap(one, other):
    """How easy two colours are to tell apart: the biggest channel difference.

    The codebase's one measure of "are these different enough" — two colours
    are considered tellable apart when some channel differs by 50 or more (see
    the scorer and rarity colour tables).
    """
    return max(abs(a - b) for a, b in zip(one, other))


class Shape:
    """The block's hitbox geometry.

    Each class constant is a shape's ID number (e.g. ``Shape.PIPE == 6``).
    """
    RECT = 0
    SLOPE = 1
    LINE = 2
    NONE = 3  # No hitbox: an invisible field / decorative shape
    CIRCLE = 4
    CURVED_SLOPE = 5
    PIPE = 6
    DRAIN = 7
    PIPE_BEND = 8
    CONVEX_SLOPE = 9
    FLAT_LINE = 10  # a thin flat line along the bottom of the cell
    CURVED_SLOPE_LINE = 11  # the curved slope's arc with its straight legs removed
    HALF_PIPE = 12  # a bottom-semicircle line, open where its diameter would sit
    SPIKE = 13  # an upward triangle (base on the bottom edge, apex top-center)
    PLATFORM = 14  # a thick solid shelf filling the bottom half of the cell
    CORNER = 15  # an L bracket: a left column plus a bottom row
    PEG = 16  # a small solid circle (radius PEG_RADIUS / 5 px) at the cell center
    SAWTOOTH = 17  # a row of small upward teeth along the bottom edge
    # COMMENTED OUT (user request: "comment out the cradle shape"): the cradle.
    # Its id stays out of NAMES/ORDER/COMPONENT_PRICES below, so the shape is
    # never sold, never rolled into a block and never drawn; the collision code
    # and the block art that built it are commented out in physics.py, main.py
    # and ui.py. Id 18 is left free rather than reused, because every shape id
    # is written by hand (adding one never renumbers the others).
    # CRADLE = 18  # a V-shaped valley (two side wedges) that catches the marble
    BUMP = 19  # a solid half-disc dome along the bottom edge (a speed bump)
    KEY = 20  # a pass-through key pickup: touching it opens its matching lock
    LOCK = 21  # a solid locked door: blocks the marble until its key is touched

    NAMES: ClassVar[dict[int, str]] = {RECT: "Rect", SLOPE: "Slope", LINE: "Line", \
                                       NONE: "None", CIRCLE: "Circle", CURVED_SLOPE: "Curved Slope", \
                                       PIPE: "Pipe", DRAIN: "Drain", PIPE_BEND: "Pipe Bend", \
                                       CONVEX_SLOPE: "Convex Slope", FLAT_LINE: "Flat Line", \
                                       CURVED_SLOPE_LINE: "Curved Slope Line", HALF_PIPE: "Half Pipe", \
                                       SPIKE: "Spike", PLATFORM: "Platform", CORNER: "Corner", \
                                       PEG: "Peg", SAWTOOTH: "Sawtooth", \
                                       BUMP: "Bump", KEY: "Key", LOCK: "Lock"}
    ORDER: ClassVar[list[int]] = [RECT, SLOPE, LINE, NONE, CIRCLE, CURVED_SLOPE, PIPE, DRAIN, PIPE_BEND,
                                  CONVEX_SLOPE, FLAT_LINE, CURVED_SLOPE_LINE, HALF_PIPE,
                                  SPIKE, PLATFORM, CORNER, PEG, SAWTOOTH, BUMP,
                                  KEY, LOCK]

    @classmethod
    def name(cls, shape):
        return cls.NAMES.get(shape, "Unknown")

    @classmethod
    def cycle(cls, shape):
        idx = cls.ORDER.index(shape) if shape in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


def paired_shape(shape):
    """The other half of a Key/Lock pair (Key <-> Lock), or None.

    A Key and a Lock always come as a matched pair: they share a pairing
    number, the Lock blocks the marble until a marble touches its Key, and
    every other shape has no pairing half (portals pair by an effect instead).
    """
    if shape == Shape.KEY:
        return Shape.LOCK
    if shape == Shape.LOCK:
        return Shape.KEY
    return None


class Effect:
    """The physical effect a block has on the marble.

    Each class constant is an effect's ID number (e.g. ``Effect.ROTATE == 7``).
    """
    NONE = 0
    BOUNCY = 1
    ACCELERATOR = 2
    PISTON = 3
    GRAVITY = 4
    BLACK_HOLE = 5
    PORTAL = 6
    ROTATE = 7
    SLIPPERY = 8
    FRAGILE = 9
    GROWING = 10
    SHRINKING = 11
    STICKY = 12
    REPULSOR = 13  # the black hole's opposite: pushes marbles away, harder up close
    CONVEYOR = 14  # a belt that pushes marbles along its surface
    ZIPPER = 15  # a one-way gate: pass through in the arrow's direction, solid against it
    PHASE = 16  # touching it makes the marble pass through everything for 1 second
    SPLITTER = 17  # splits the marble in two; the copy leaves the opposite way

    NAMES: ClassVar[dict[int, str]] = {NONE: "None", BOUNCY: "Bouncy", ACCELERATOR: "Accelerator", \
                                       PISTON: "Piston", GRAVITY: "Gravity", BLACK_HOLE: "Black Hole", \
                                       PORTAL: "Portal", ROTATE: "Rotate", SLIPPERY: "Slippery", \
                                       FRAGILE: "Fragile", GROWING: "Growing", SHRINKING: "Shrinking", \
                                       STICKY: "Sticky", REPULSOR: "Repulsor", CONVEYOR: "Conveyor", \
                                       ZIPPER: "Zipper", PHASE: "Phase", SPLITTER: "Splitter"}
    ORDER: ClassVar[list[int]] = [NONE, BOUNCY, ACCELERATOR, PISTON, GRAVITY, BLACK_HOLE, PORTAL, ROTATE,
                                  SLIPPERY, FRAGILE, GROWING, SHRINKING, STICKY, REPULSOR, CONVEYOR,
                                  ZIPPER, PHASE, SPLITTER]
    # The real, non-NONE effects a block can actually have.
    REAL_ORDER: ClassVar[list[int]] = [BOUNCY, ACCELERATOR, PISTON, GRAVITY, BLACK_HOLE, PORTAL, ROTATE,
                                       SLIPPERY, FRAGILE, GROWING, SHRINKING, STICKY, REPULSOR,
                                       CONVEYOR, ZIPPER, PHASE, SPLITTER]
    # The effects whose strength is a NUMBER: each block rolls its own value
    # around the average below (see main.roll_magnitude). Magnitudes roll with
    # the same 1/(x^2+1) distribution scorers use, one step at a time, where a
    # step is 10% of the average — so a piston is usually 1500 px/s of launch,
    # often 1350 or 1650, and once in a while a wild 900 or 2100.
    #
    # On/off effects have no magnitude: Fragile, Portal, Slippery, Zipper,
    # Growing, Shrinking and Splitter either do their thing or don't, and
    # Gravity's strength is the world's gravity, not its own.
    MAGNITUDE: ClassVar[dict[int, float]] = {
        PISTON: 1500,       # px/s launch speed
        ACCELERATOR: 20000,  # px/s^2 of push along its arrow
        BLACK_HOLE: 3000,    # px/s^2 of pull at the edge of its range
        REPULSOR: 3000,      # px/s^2 of push at the edge of its range
        CONVEYOR: 300,       # px/s the belt carries a marble along at
        ROTATE: 900,         # deg/s the shape spins at
        BOUNCY: 100,         # % of the impact speed kept when bouncing
        STICKY: 0.4,         # seconds the marble is held against it
        PHASE: 1.0,          # seconds of phasing a touch grants
    }
    # The unit each magnitude is spoken in (used by the descriptions).
    MAGNITUDE_UNIT: ClassVar[dict[int, str]] = {
        PISTON: "px/s", ACCELERATOR: "px/s^2", BLACK_HOLE: "px/s^2",
        REPULSOR: "px/s^2", CONVEYOR: "px/s", ROTATE: "deg/s",
        BOUNCY: "%", STICKY: "s", PHASE: "s",
    }

    @classmethod
    def magnitude(cls, effect):
        """The AVERAGE magnitude of a scalable effect (0 for the others)."""
        return cls.MAGNITUDE.get(effect, 0)

    @classmethod
    def name(cls, effect):
        return cls.NAMES.get(effect, "Unknown")

    @classmethod
    def cycle(cls, effect):
        idx = cls.ORDER.index(effect) if effect in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


class Scorer:
    """The block's effect on the player's score (plus start/finish run roles).

    Each class constant is a scorer's ID number (e.g. ``Scorer.CHIPS_ADD == 1``).
    """
    NONE = 0
    CHIPS_ADD = 1
    MULT_ADD = 2
    MULT_MUL = 3
    START = 4
    FINISH = 5
    QUICK = 6
    CASH = 7
    SHARP = 8
    PARTS = 9  # 1 component per trigger (granted when the run is continued)
    SHREDS = 10
    RUBBLE = 11
    IDEAS = 12
    RANDOM = 13  # random payoff: +35 chips, +5 mult, or +0.3 xMult
    EFFECTIVE = 14  # +1 xMult when the block has 2+ effects
    FRESH = 15  # 1 free shop reroll when touched
    PICKY = 16  # 1 option point; every 2 add a random shop slot
    VOYAGER = 17  # +0.01 mult per px the marble traveled before the touch (rolled)
    SATANIC = 18  # x6.66 mult; a block dies once a marble leaves, a card after a run
    SUMMIT = 19  # +0.75 mult per unit (row) above the bottom row it sits on
    AIRBALL = 20  # +8 mult per second the marble was airborne before the touch
    SEED = 21  # +3 mult (scorer_amount) per Seed block on the board when touched
    DRILL = 22  # when touched, unlock two locked board squares after the run
    LUCKY = 23  # per trigger, independent rolls: 1/3 chance +130 chips, 1/9 chance +$40
    ROOMY = 24  # +2 chips (scorer_amount) per unlocked board unit when touched
    RALLY = 25  # +1 mult per fresh block touch this run before it (re-touches count)
    ECHO = 26  # re-fires the scorer of the block the marble touched right before it
    POWERLINE = 27  # +25 chips (scorer_amount) per block in its row (incl itself)
    FRONTIER = 28  # +3 mult per locked unit / board border orthogonally adjacent
    GILDED = 29  # +1/6 of current chips as mult
    BOMB = 30  # touched: unlock units within 1 cell after the run, then destroyed
    CLUSTER = 31  # +4 mult per block orthogonally adjacent to it (no diagonals)
    COLOSSUS = 32  # +0.1 xMult per px of marble radius above the base size
    UNDERTAKER = 33  # +15 mult per block destroyed this run
    DEBT = 34  # +60 chips, but the run pays no interest afterwards

    DEFAULT_AMOUNT: ClassVar[dict[int, float]] = {
        NONE: 0,
        CHIPS_ADD: 30,
        MULT_ADD: 4,
        MULT_MUL: 1.5,  # xMult now multiplies the multiplier by 1.5
        START: 0,
        FINISH: 0,
        QUICK: 0,  # speed-based: chips scale with the marble's speed (QUICK_SCALE)
        CASH: 15,  # $15 per trigger
        SHARP: 3,  # 3x mult per trigger
        PARTS: 1,  # 1 component per trigger
        SHREDS: 1,  # banks a third of a shred point a trigger (RESOURCE_RATE)
        RUBBLE: 1,  # banks half a rubble point a trigger
        IDEAS: 1,  # banks half an idea point a trigger
        RANDOM: 0,  # picks among fixed rewards; no single amount
        EFFECTIVE: 2.0,  # multiplies the multiplier by 2 when it fires (+1 xMult)
        FRESH: 1,  # 1 free reroll per trigger
        PICKY: 1,  # banks half an option point a trigger
        VOYAGER: 0.01,  # mult per PIXEL the marble traveled before the touch
        SATANIC: 6.66,  # multiplies the multiplier by 6.66 when touched
        SUMMIT: 0.75,  # +0.75 mult per row above the bottom row
        AIRBALL: 8,  # +8 mult per second of air time before the touch
        SEED: 3,  # +3 mult per Seed block on the board
        DRILL: 2,  # two locked board squares unlocked after the run
        LUCKY: 0,  # rolls fixed rewards (130 chips / $40); no single amount
        ROOMY: 2,  # +2 chips per unlocked board unit
        RALLY: 1,  # +1 mult per fresh touch before it
        ECHO: 0,  # copies the previous block's scorer
        POWERLINE: 25,  # +25 chips per block in its row
        FRONTIER: 3,  # +3 mult per locked unit / board border orthogonally adjacent
        GILDED: 0,  # 1/6 of current chips as mult
        BOMB: 0,  # detonates after the run (unlock radius, then destroyed)
        CLUSTER: 4,  # +4 mult per block orthogonally adjacent to it
        COLOSSUS: 0.1,  # +0.1 xMult per px of radius above the base radius
        UNDERTAKER: 15,  # +15 mult per block destroyed this run
        DEBT: 60,  # 60 chips per trigger
    }
    NAMES: ClassVar[dict[int, str]] = {
        NONE: "None",
        CHIPS_ADD: "+Chips",
        MULT_ADD: "+Mult",
        MULT_MUL: "xMult",
        START: "Start",
        FINISH: "Finish",
        QUICK: "Quick",
        CASH: "Cash",
        SHARP: "Sharp",
        PARTS: "Parts",
        SHREDS: "Shreds",
        RUBBLE: "Rubble",
        IDEAS: "Ideas",
        RANDOM: "Random",
        EFFECTIVE: "Effective",
        FRESH: "Fresh",
        PICKY: "Picky",
        VOYAGER: "Voyager",
        SATANIC: "Satanic",
        SUMMIT: "Summit",
        AIRBALL: "Airball",
        SEED: "Seed",
        DRILL: "Drill",
        LUCKY: "Lucky",
        ROOMY: "Roomy",
        RALLY: "Rally",
        ECHO: "Echo",
        POWERLINE: "Powerline",
        FRONTIER: "Frontier",
        GILDED: "Gilded",
        BOMB: "Bomb",
        CLUSTER: "Cluster",
        COLOSSUS: "Colossus",
        UNDERTAKER: "Undertaker",
        DEBT: "Debt",
    }
    COLORS: ClassVar[dict[int, tuple]] = {
        # Every scorer's color is chosen to be clearly different from every
        # other scorer's (no two share a hue family at a similar brightness),
        # so blocks are identifiable at a glance. The big three score parts
        # keep their classic hues (green/blue/violet) and Cash stays yellow;
        # the rest are spread across pinks, tans, browns, teals, greys and
        # pastels so nothing reads as a duplicate.
        NONE: (150, 150, 150),  # neutral gray (no scorer)
        CHIPS_ADD: (0, 255, 0),  # bright green (classic)
        MULT_ADD: (0, 0, 255),  # blue (classic)
        MULT_MUL: (150, 0, 255),  # violet (classic)
        START: (0, 140, 0),  # deep forest green (run start)
        FINISH: (190, 135, 0),  # bronze gold (run finish)
        QUICK: (255, 120, 0),  # orange
        CASH: (255, 255, 0),  # lemon yellow (money)
        SHARP: (255, 0, 150),  # magenta pink
        PARTS: (150, 255, 0),  # lime
        SHREDS: (215, 185, 140),  # light paper tan
        RUBBLE: (135, 65, 45),  # warm brown
        IDEAS: (255, 0, 255),  # fuchsia
        RANDOM: (0, 255, 255),  # cyan (wildcard)
        EFFECTIVE: (150, 255, 255),  # pale cyan
        FRESH: (0, 200, 80),  # leaf green
        PICKY: (255, 60, 0),  # vermilion
        VOYAGER: (0, 130, 150),  # deep teal
        SATANIC: (255, 0, 0),  # red
        SUMMIT: (170, 150, 230),  # light periwinkle (snowy peak)
        AIRBALL: (0, 160, 255),  # azure
        SEED: (120, 170, 60),  # olive green
        DRILL: (80, 105, 195),  # steel blue
        LUCKY: (255, 185, 0),  # gold coin
        ROOMY: (255, 90, 210),  # rose pink
        RALLY: (255, 170, 255),  # light pink
        ECHO: (245, 245, 245),  # white ghost (mirror)
        POWERLINE: (0, 255, 150),  # bright teal-green (electric)
        FRONTIER: (195, 145, 70),  # desert tan
        GILDED: (245, 205, 80),  # goldenrod
        BOMB: (45, 45, 60),  # near-black slate
        CLUSTER: (95, 45, 190),  # deep indigo (crowded)
        COLOSSUS: (75, 95, 60),  # moss stone (a growing mass)
        UNDERTAKER: (105, 90, 115),  # dusty violet grey (a grave)
        DEBT: (200, 30, 90),  # deep crimson (owed money)
    }
    ORDER: ClassVar[list[int]] = [NONE, CHIPS_ADD, MULT_ADD, MULT_MUL, START, FINISH,
                                  QUICK, CASH, SHARP, PARTS, SHREDS, RUBBLE, IDEAS,
                                  RANDOM, EFFECTIVE, FRESH, PICKY, VOYAGER, SATANIC,
                                  SUMMIT, AIRBALL, SEED, DRILL, LUCKY, ROOMY,
                                  RALLY, ECHO, POWERLINE, FRONTIER, GILDED, BOMB,
                                  CLUSTER, COLOSSUS, UNDERTAKER, DEBT]
    # Scorers the shop can offer. START and FINISH are run roles, but they are
    # sold like anything else: the shop offers them as plain Rect blocks (see
    # main.role_block_parts / Shop._scorer_offer) rather than as scorer
    # components, because a role is bought whole and never assembled onto the
    # physics of another block.
    SHOP_ORDER: ClassVar[list[int]] = [NONE, CHIPS_ADD, MULT_ADD, MULT_MUL, START,
                                       FINISH, QUICK,
                                       CASH, SHARP, PARTS, SHREDS, RUBBLE, IDEAS,
                                       RANDOM, EFFECTIVE, FRESH, PICKY, VOYAGER,
                                       SATANIC, SUMMIT, AIRBALL, SEED, DRILL, LUCKY, ROOMY,
                                       RALLY, ECHO, POWERLINE, FRONTIER, GILDED, BOMB, CLUSTER,
                                       COLOSSUS, UNDERTAKER, DEBT]
    # The scorers whose magnitude is a MULTIPLIER of the score (xMult, Sharp,
    # Satanic, Effective). Their magnitude is never rolled below 1: a factor
    # under 1 would turn the block into a penalty instead of a weak payoff.
    MULTIPLIER_SCORERS: ClassVar[tuple] = (MULT_MUL, SHARP, SATANIC, EFFECTIVE)
    # The scorers that bank RESOURCE POINTS instead of a payoff. A single
    # trigger banks a FRACTION of a point, and one whole point converts into
    # that scorer's reward (see RESOURCE_THRESHOLD): a Shreds trigger banks a
    # third, the others a half, so the reward RATE is exactly what it always
    # was (3 Shreds triggers a card, 2 Rubble triggers a block) while the bank
    # reads as one point a reward. The fraction scales with the scorer's own
    # magnitude, so a 3-magnitude Rubble banks 1.5 points a trigger. Parts
    # banks whole components rather than points and Fresh grants its reroll
    # immediately; neither appears here.
    RESOURCE_RATE: ClassVar[dict[int, float]] = {
        SHREDS: 1.0 / 3.0,
        RUBBLE: 0.5,
        IDEAS: 0.5,
        PICKY: 0.5,
    }

    @classmethod
    def name(cls, scorer):
        return cls.NAMES.get(scorer, "Unknown")

    @classmethod
    def color(cls, scorer):
        return cls.COLORS.get(scorer, GRAY)

    @classmethod
    def cycle(cls, scorer):
        idx = cls.ORDER.index(scorer) if scorer in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


# Resource points: ONE point always converts into a reward (a card, a block, an
# action, a shop slot), whatever fraction of a point a trigger banked (see
# Scorer.RESOURCE_RATE). The Factory whole card halves the points a conversion
# needs, which is now a real half point rather than a rounding-up fudge.
RESOURCE_THRESHOLD = 1.0


class Trial:
    """A run-wide modifier applied to each run, exactly one per run.

    Each class constant is a trial's ID number (e.g. ``Trial.HANDS_TIED == 0``).
    The trial's description explains its effect on the run.
    """
    HANDS_TIED = 0
    CARD_CUTTER = 1
    DEAD_ZONE = 2
    ALL_FINISHES = 3
    SLIM_PICKINGS = 4
    LONG_RUN = 5
    SHUFFLED = 6
    BOUNCY_CASTLE = 7
    CRUMBLING = 8
    MARBLE_WEIGHT = 9
    SPEEDRUN = 10
    REPEATS_ONLY = 11
    INFLATION = 12
    EMPTY_POCKETS = 13
    DEAL_BREAKER = 14

    NAMES: ClassVar[dict[int, str]] = {
        HANDS_TIED: "Hands tied",
        CARD_CUTTER: "Card cutter",
        DEAD_ZONE: "Dead zone",
        ALL_FINISHES: "All finishes",
        SLIM_PICKINGS: "Slim pickings",
        LONG_RUN: "Long run",
        SHUFFLED: "Shuffled",
        BOUNCY_CASTLE: "Bouncy castle",
        CRUMBLING: "Crumbling",
        MARBLE_WEIGHT: "Marble weight",
        SPEEDRUN: "Speedrun",
        REPEATS_ONLY: "Repeats only",
        INFLATION: "Inflation",
        EMPTY_POCKETS: "Empty pockets",
        DEAL_BREAKER: "Deal breaker",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        HANDS_TIED: "A random 1/4 of your blocks can score 1 fewer time per "
                    "run.",
        CARD_CUTTER: "Disables a random card.",
        DEAD_ZONE: "Gravity is tripled in the board's bottom third.",
        ALL_FINISHES: "The board borders count as finish blocks.",
        SLIM_PICKINGS: "Removes two random shop options.",
        LONG_RUN: "Doubles the ideal time for a run.",
        SHUFFLED: "Flips and shuffles your cards.",
        BOUNCY_CASTLE: "Every solid block bounces like a bouncy block.",
        CRUMBLING: "A random 1/4 of your blocks are fragile: they shatter "
                   "when touched.",
        MARBLE_WEIGHT: "The marble is randomly heavier or lighter: effect "
                       "pushes (pistons, bouncy blocks, accelerators, black "
                       "holes) are weaker or stronger, but it falls at the "
                       "same speed.",
        SPEEDRUN: "Halves the ideal time for a run.",
        REPEATS_ONLY: "Only block types touched twice count toward the "
                      "uniqueness score.",
        INFLATION: "Everything costs 50% more: shop prices, rerolls, "
                   "upgrades, and disassembly.",
        EMPTY_POCKETS: "The end-of-run cash award skips its score-based bonus "
                       "(the flat $20, interest, and Cash-card payouts stay).",
        DEAL_BREAKER: "Disables every card of one random condition.",
    }
    ORDER: ClassVar[list[int]] = [HANDS_TIED, CARD_CUTTER, DEAD_ZONE, ALL_FINISHES,
                                  SLIM_PICKINGS, LONG_RUN, SHUFFLED,
                                  BOUNCY_CASTLE, CRUMBLING, MARBLE_WEIGHT,
                                  SPEEDRUN, REPEATS_ONLY, INFLATION,
                                  EMPTY_POCKETS, DEAL_BREAKER]
    # The base colour of each trial's tile: the field its tessellation is built
    # from, and the hue the trial's icon in the collection and the trial-tinted
    # panels (see panel_color) are derived from. One per trial, as unlike each
    # other as the trials are.
    COLORS: ClassVar[dict[int, tuple]] = {
        HANDS_TIED: (58, 62, 76),       # chained slate
        CARD_CUTTER: (150, 60, 120),    # cut magenta
        DEAD_ZONE: (48, 62, 150),       # heavy indigo
        ALL_FINISHES: (245, 245, 245),  # goal white
        SLIM_PICKINGS: (150, 140, 80),  # shelf olive
        LONG_RUN: (45, 120, 95),        # long sea green
        SHUFFLED: (110, 70, 160),       # shuffle purple
        BOUNCY_CASTLE: (200, 90, 140),  # bouncy pink
        CRUMBLING: (105, 105, 115),     # cracked stone
        MARBLE_WEIGHT: (40, 140, 145),  # scale teal
        SPEEDRUN: (215, 110, 35),       # speed orange
        REPEATS_ONLY: (40, 150, 185),   # repeat cyan
        INFLATION: (190, 60, 45),       # inflation red
        EMPTY_POCKETS: (120, 80, 50),   # empty brown
        DEAL_BREAKER: (140, 40, 60),    # broken crimson
    }
    # Which tessellation each trial's tile is drawn with (see
    # ui._TRIAL_TESSELLATIONS): the pattern is always made of SHAPES — rows of
    # triangles, rings, circles, chevrons, scales, diamonds, octagons, split
    # cells — never a plain rectangle of flat colour, and the family is picked
    # to echo what the trial does (interlocked rings for chained hands, circles
    # bouncing in a castle, chevrons for speed, scales for repetition, cut cells
    # for a cutter, climbing bars for inflation ...).
    TILE_STYLES: ClassVar[dict[int, str]] = {
        HANDS_TIED: "rings",         # links of a chain
        CARD_CUTTER: "splits",       # cards cut corner to corner
        DEAD_ZONE: "chevrons",       # bands, with a fall through them
        ALL_FINISHES: "checker",     # the finish checkerboard, in triangles
        SLIM_PICKINGS: "octagons",   # tiles with gaps between them
        LONG_RUN: "bars",            # a long even track of bars
        SHUFFLED: "pinwheel",        # cells rotated every which way
        BOUNCY_CASTLE: "circles",    # balls, touching in a lattice
        CRUMBLING: "cracked",        # a broken triangle lattice
        MARBLE_WEIGHT: "dots",       # big marbles against small ones
        SPEEDRUN: "chevrons",        # speed
        REPEATS_ONLY: "scales",      # the same arc repeated
        INFLATION: "climbers",       # bars climbing, price and all
        EMPTY_POCKETS: "pockets",    # hollow rings
        DEAL_BREAKER: "tears",       # cells torn apart
    }
    # The extra colours a tile may use besides the trial's own: an accent (gold
    # by default: the game's "payoff" colour) and the two ends of the light/dark
    # range. Kept as fractions so every palette is derived from COLORS.
    TILE_LIGHT = 0.34       # how much lighter the light shade is
    TILE_DARK = 0.34        # how much darker the dark shade is
    TILE_ACCENT_LIGHT = 0.72
    PANEL_LIGHT = 0.22      # the board/inventory/shop tint (see panel_color)
    LOCKED_DARK = 0.34      # how far a locked square sinks below a panel
    # A tile brighter than this gets its panels DARKENED instead of lightened:
    # the panels carry white text (the board/inventory/shop titles, prices and
    # messages), so an all-finishes run cannot have near-white panels.
    PANEL_LIGHT_LIMIT = 200

    @classmethod
    def palette(cls, trial):
        """The few colours one trial's tile is built from.

        Four shades derived from the trial's base colour — a light, the base
        itself, a dark, and a pale accent — so a tile reads as one colour FAMILY
        while its shapes still tell each other apart. The mesh lines drawn
        between the shapes use the dark shade, so the same palette covers the
        whole pattern.
        """
        base = cls.COLORS.get(trial, (60, 60, 70))
        return {
            "light": shade(base, cls.TILE_LIGHT),
            "base": base,
            "dark": shade(base, -cls.TILE_DARK),
            "accent": shade(base, cls.TILE_ACCENT_LIGHT),
        }

    @classmethod
    def panel_color(cls, trial):
        """The colour the board/inventory/shop panels are filled with.

        The trial's tile colour, a little lighter, so the panels read as part of
        the run's palette instead of a separate red. The one exception is a tile
        that is already very light (the all-finishes trial is near-white): its
        panels are darkened instead of lightened, because they carry white text
        and near-white panels would swallow it. No trial (or an unknown id)
        keeps the game's own panel colour.
        """
        if trial is None:
            return None
        base = cls.COLORS.get(trial, (60, 60, 70))
        if sum(base) / 3 > cls.PANEL_LIGHT_LIMIT:
            return shade(base, -cls.TILE_DARK)
        return shade(base, cls.PANEL_LIGHT)

    @classmethod
    def locked_color(cls, trial):
        """The colour a LOCKED board square is filled with during that trial.

        Always taken a step DOWN from panel_color (LOCKED_DARK) rather than
        straight from the tile's base: the all-finishes tile is near-white and
        its panel is darkened rather than lightened, so a locked square derived
        from the base could come out the SAME as its own panel — or lighter.
        Deriving from the panel makes a locked square darker than the unlocked
        ones around it for every trial, which is what keeps the playable region
        reading as raised out of the board it sits in. No trial (or an unknown
        id) returns None, and the caller keeps its own locked colour.
        """
        panel = cls.panel_color(trial)
        if panel is None:
            return None
        return shade(panel, -cls.LOCKED_DARK)

    @classmethod
    def name(cls, trial):
        return cls.NAMES.get(trial, "Unknown")

    @classmethod
    def description(cls, trial):
        return cls.DESCRIPTIONS.get(trial, "Unknown trial.")

    @classmethod
    def cycle(cls, trial):
        idx = cls.ORDER.index(trial) if trial in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


class FinalBoss:
    """The final run's boss modifier (the 24th run).

    Exactly one boss is chosen at random when the player reaches the last run.
    Each class constant is a boss's ID number (e.g. ``FinalBoss.SINGULARITY ==
    0``). The boss's description explains its effect on the run.
    """
    SINGULARITY = 0
    SKY_HIGH = 1

    NAMES: ClassVar[dict[int, str]] = {
        SINGULARITY: "Singularity",
        SKY_HIGH: "Sky High",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        SINGULARITY: "The marble gains mass quickly and linearly over time, "
                     "falling ever faster.",
        SKY_HIGH: "The required score is tripled.",
    }
    ORDER: ClassVar[list[int]] = [SINGULARITY, SKY_HIGH]

    @classmethod
    def name(cls, boss):
        return cls.NAMES.get(boss, "Unknown")

    @classmethod
    def description(cls, boss):
        return cls.DESCRIPTIONS.get(boss, "Unknown boss.")

    @classmethod
    def cycle(cls, boss):
        idx = cls.ORDER.index(boss) if boss in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


class Difficulty:
    """How hard a save's runs are, chosen when a new save begins.

    A level sets two knobs: how many of a round's runs play a trial (the
    round's LAST runs — see TRIALS_PER_ROUND, so difficulty 1-2 leave the
    round's first two runs clean) and the factor a run's required score grows
    by for the next run. The hardest level is the game's original balance —
    every run of a round plays its own trial and the target doubles each run —
    and each level below lightens one of those knobs, so difficulty 1 is the
    gentlest (a trial on a round's last run only, and 1.6x targets) and
    difficulty 4 is the game as it has always played.
    """
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4

    ORDER: ClassVar[list[int]] = [LEVEL_1, LEVEL_2, LEVEL_3, LEVEL_4]

    NAMES: ClassVar[dict[int, str]] = {
        LEVEL_1: "Difficulty 1",
        LEVEL_2: "Difficulty 2",
        LEVEL_3: "Difficulty 3",
        LEVEL_4: "Difficulty 4",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        LEVEL_1: ("A trial on the last run of every round, and gentler "
                  "targets: each run asks 1.6x the last run's required score."),
        LEVEL_2: ("A trial on the last run of every round, with the required "
                  "score doubling every run."),
        LEVEL_3: ("The last two runs of every round each play a trial, with "
                  "the required score doubling every run."),
        LEVEL_4: ("Every run of every round plays a trial, with the required "
                  "score doubling every run."),
    }
    # The factor a run's required score grows by each run (see
    # main.get_next_required_score).
    SCORE_GROWTH: ClassVar[dict[int, float]] = {
        LEVEL_1: 1.6,
        LEVEL_2: 2.0,
        LEVEL_3: 2.0,
        LEVEL_4: 2.0,
    }
    # How many of a round's LAST runs play a trial: 1 means only its final run
    # has one, 3 means every run of the round does (see
    # main.Game._choose_trial).
    TRIALS_PER_ROUND: ClassVar[dict[int, int]] = {
        LEVEL_1: 1,
        LEVEL_2: 1,
        LEVEL_3: 2,
        LEVEL_4: 3,
    }

    @classmethod
    def name(cls, level):
        return cls.NAMES.get(level, "Unknown")

    @classmethod
    def description(cls, level):
        return cls.DESCRIPTIONS.get(level, "Unknown difficulty.")

    @classmethod
    def score_growth(cls, level):
        """The factor a level's required score grows by each run."""
        return cls.SCORE_GROWTH.get(level, 2.0)

    @classmethod
    def trials_per_round(cls, level):
        """How many of a level's round's LAST runs play a trial.

        An unknown level falls back to the gentlest count (a round's last run
        only), so an unrecognised difficulty in a save is playable rather than
        broken.
        """
        return cls.TRIALS_PER_ROUND.get(level, 1)


# The level a save starts on when it has no difficulty of its own — the game's
# original balance (a trial per run, doubling targets), which is also how saves
# written before the difficulty picker existed are read.
DEFAULT_DIFFICULTY = Difficulty.LEVEL_4


class MarbleType:
    """The marble the player picks when starting a new save (one per save).

    Each class constant is a marble type's ID number (e.g.
    ``MarbleType.EIGHT_BALL == 1``). The chosen type is persisted with the save
    and drives how the marble looks and behaves.
    """
    VANILLA = 0
    EIGHT_BALL = 1
    RUBBER_BALL = 2
    PING_PONG = 3

    NAMES: ClassVar[dict[int, str]] = {
        VANILLA: "Vanilla",
        EIGHT_BALL: "8 Ball",
        RUBBER_BALL: "Rubber Ball",
        PING_PONG: "Ping-Pong Ball",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        VANILLA: "A plain marble with no special effects.",
        EIGHT_BALL: "1/4 chance to retrigger a block's scoring effect on collision.",
        RUBBER_BALL: "Bounces off blocks and borders.",
        PING_PONG: ("Very light: falls like a normal marble, bounces a little, and "
                    "effect pushes (pistons, bouncy blocks, rotating blocks, "
                    "accelerators, black holes) move it much more."),
    }
    ORDER: ClassVar[list[int]] = [VANILLA, EIGHT_BALL, RUBBER_BALL, PING_PONG]

    @classmethod
    def name(cls, marble_type):
        return cls.NAMES.get(marble_type, "Unknown")

    @classmethod
    def description(cls, marble_type):
        return cls.DESCRIPTIONS.get(marble_type, "Unknown marble.")


class Rarity:
    """How rare a card is: its tier, from Common up to Legendary.

    Every card has one (see Card.RARITIES). The tiers are ORDERED — Common is
    the most ordinary and Legendary the rarest — and the ORDER is also the
    display order, so a list of the tiers reads cheapest first.

    The tier sets how often the shop OFFERS it: WEIGHTS is the relative
    frequency of the TIERS — 1 : 0.7 : 0.5 : 0.3 : 0.2 from Common up to
    Legendary — and the shop's card offers draw the tier first and the card
    inside it second (see main.random_card_option_value). An offer is therefore
    Rare 0.5 times as often as it is Common however many cards carry each tier:
    the CARD COUNT of a tier must not change the tier's own odds, which is
    exactly why the tier is drawn first. Every match-group card — the 832
    shape-group and effect cards — is COMMON, which is what the design asks
    for; the whole cards are tiered by price, the codebase's usual rarity rule
    (a dearer card does more, so it is rarer).
    """
    COMMON = 0
    UNUSUAL = 1
    RARE = 2
    EPIC = 3
    LEGENDARY = 4

    NAMES: ClassVar[dict[int, str]] = {
        COMMON: "Common",
        UNUSUAL: "Unusual",
        RARE: "Rare",
        EPIC: "Epic",
        LEGENDARY: "Legendary",
    }
    # The colour a card's BORDER is drawn in (see ui.draw_card), one per tier:
    # grey for the everyday cards, then progressively warmer and brighter up to
    # gold. A face in a colour too close to its own border is moved aside by
    # Card.face_color, so the border always reads.
    COLORS: ClassVar[dict[int, tuple]] = {
        COMMON: (165, 170, 180),    # plain grey
        UNUSUAL: (80, 200, 110),    # green
        RARE: (70, 140, 235),       # blue
        EPIC: (165, 85, 225),       # purple
        LEGENDARY: (240, 180, 50),  # gold
    }
    # How often each TIER is offered in the shop (user request: "make each card
    # rarity have a relative ratio for shop frequency: for the ratio
    # common:unusual:rare:epic:legendary, the ratios to their frequencies in the
    # shop should be 1:0.7:0.5:0.3:0.2"). The numbers are RELATIVE, so what
    # matters is the ratio between them: the shop draws the tier by these
    # weights FIRST, then a card flat inside the drawn tier, which is what keeps
    # a tier's card count out of its odds. A tier's share of the offers is its
    # weight over the sum of the weights — Common 1/2.7 = 37%, Unusual 26%,
    # Rare 18.5%, Epic 11.1%, Legendary 0.2/2.7 = 7.4% — so all 26 match groups
    # PLUS the 3 cheap whole cards share the Common tier rather than each of
    # them adding a Common-sized chunk of offers.
    WEIGHTS: ClassVar[dict[int, float]] = {
        COMMON: 1.0,
        UNUSUAL: 0.7,
        RARE: 0.5,
        EPIC: 0.3,
        LEGENDARY: 0.2,
    }
    ORDER: ClassVar[list[int]] = [COMMON, UNUSUAL, RARE, EPIC, LEGENDARY]

    @classmethod
    def name(cls, rarity):
        return cls.NAMES.get(rarity, "Unknown")

    @classmethod
    def color(cls, rarity):
        return cls.COLORS.get(rarity, GRAY)

    @classmethod
    def weight(cls, rarity):
        """The tier's shop frequency weight (see WEIGHTS); Common if unknown."""
        return cls.WEIGHTS.get(rarity, cls.WEIGHTS[cls.COMMON])


class Card:
    """An indivisible whole card bought from the shop.

    Every card is whole: nothing splits and nothing is assembled, and no card
    carries a rolled magnitude. Three families live here:

    * the NAMED CARDS (Joker ... Island) — the classic cards. Each is one
      effect that fires at the start of a run, at the end of it, or when a
      fragile block breaks (see Card.NAMED and cards.apply_cards), and each
      keeps the name, the flavour comment and the trigger prose of the named
      CONDITION it was briefly split into.
    * the utility cards (ERR 404's random grant, Blueprint's copy, Showman's
      duplicate rule, Garden's seeds, Coupon's discount, ...), which work
      through a passive rule read with Game._has_card or through the code that
      owns the mechanic, and
    * the MATCH GROUP cards, whose ids are no constants here at all: the
      catalogue at the end of this file generates one per (group x scorer).

    Each constant is the card's ID.
    """
    ERR_404 = 9
    BLUEPRINT = 10
    # --- The named cards ---
    # The fourteen classic cards, each rebuilt as ONE unsplittable card out of
    # the named condition it had become (user request: "add back the named
    # conditions you commented out, as unsplittable cards"): the trigger and the
    # payoff are baked into the card, exactly as the canonical (condition x
    # scorer) pairing used to play it. The ids are the named conditions' own ids
    # (START 0 ... FEW_BLOCKS 9, COZY 79, PAINTING 92, SYNTHESIZER 93, ISLAND
    # 99), so a save or a collection written while the conditions existed still
    # names the same card; Ripped Card (Few Blocks) is the one exception — 9 is
    # ERR 404's id — so it takes the first free id in the 11..77 band. What each
    # one does, and how it is measured, is in Card.NAMED below.
    JOKER = 0          # +4 mult at the start of the run
    EXPLORER = 1       # up to x2 mult at the end, by the distance travelled
    ASTRONAUT = 2      # +4 mult per second pulled by a black hole, at the end
    PLANE = 3          # +15 chips per second in the air, at the end
    PILLAR = 4         # +1 mult per block in the fullest column, at the start
    BANKER = 5         # +1 chip per $10 held, at the start
    WRECKING_BALL = 6  # +3 mult per fragile break, permanent
    SKATER = 7         # x1.2 per slippery block owned, at the end
    GLITCH = 8         # +0..24 mult at random, at the start
    RIPPED_CARD = 11   # +120 chips at the start, on a board of 5 blocks or fewer
    COZY = 79          # +90 chips at the start, while 10 units or fewer are unlocked
    PAINTING = 92      # +3 chips per $1 of the board's sell value, at the start
    SYNTHESIZER = 93   # +3 mult per card in the card area, at the start
    ISLAND = 99        # +0.5 xMult per unconnected group of units, at the start
    # Owning the Showman card lets the player buy more than one copy of any
    # other card (duplicates are otherwise blocked).
    SHOWMAN = 78
    # Garden doubles the per-seed payoff of Seed-scorer blocks (+3 -> +6 mult).
    # New whole-card ids stay in the free 12..77 band, or in the 79..99 one the
    # newer cards share with the named cards — 0..11 are the named cards'.
    GARDEN = 80
    # Rigged Casino re-weights Random blocks toward +xMult and away from +chips.
    RIGGED_CASINO = 81
    # Conquistador unlocks board squares after every run.
    CONQUISTADOR = 82
    # The nine utility whole cards: run-shape and economy modifiers that no
    # condition + scorer pair can express. Their ids continue the free 83..91
    # band that Garden (80), Rigged Casino (81) and Conquistador (82) opened —
    # every whole card shares one small id space (0..99), so a new card must
    # never reuse an id already taken: the named cards hold 0..11, and 12..77
    # are the free ones.
    PEDESTAL = 83  # retriggers the scorer of the first 3 blocks touched per run
    INFERNO = 84  # +0.07 to the total-score exponent
    DOPPELGANGER = 85  # each Start block releases a second marble
    COMPOUND_INTEREST = 86  # doubles the run's interest
    COUPON = 87  # every shop option (except board units) is 25% cheaper
    FACTORY = 88  # resource conversions need half as many points
    MINESHAFT = 89  # board units cost $5
    MARKET = 90  # selling refunds 75% of the price instead of 50%
    WATCH = 91  # the run ends at the ideal time; only the first 5 blocks score
    # The newest whole cards. Their ids continue the shared band upward;
    # Painting (92), Synthesizer (93) and Island (99) belong to the named cards,
    # so the free ids left in the band are 12..77.
    TESSERACT = 94  # permanently +0.1 xMult for every shop reroll
    THOUSAND_HANDED = 95  # creates a random action after every run
    PROCRASTINATION = 96  # ends the run a second late: rewinds it once and refills triggers
    ESSENCE = 97  # $10 a run, one card slot fewer, 2 permanent tokens when sold
    CONCERT = 98  # +1 trigger per run for every block that is not a plain rect

    NAMES: ClassVar[dict[int, str]] = {
        # The named cards (the classic cards).
        JOKER: "Joker",
        EXPLORER: "Explorer",
        ASTRONAUT: "Astronaut",
        PLANE: "Plane",
        PILLAR: "Pillar",
        BANKER: "Banker",
        WRECKING_BALL: "Wrecking Ball",
        SKATER: "Skater",
        GLITCH: "Glitch",
        RIPPED_CARD: "Ripped Card",
        COZY: "Cozy",
        PAINTING: "Painting",
        SYNTHESIZER: "Synthesizer",
        ISLAND: "Island",
        ERR_404: "[ERR 404: CARD NOT FOUND]",
        BLUEPRINT: "Blueprint",
        SHOWMAN: "Showman",
        GARDEN: "Garden",
        RIGGED_CASINO: "Rigged Casino",
        CONQUISTADOR: "Conquistador",
        PEDESTAL: "Pedestal",
        INFERNO: "Inferno",
        DOPPELGANGER: "Doppelganger",
        COMPOUND_INTEREST: "Compound Interest",
        COUPON: "Coupon",
        FACTORY: "Factory",
        MINESHAFT: "Mineshaft",
        MARKET: "Market",
        WATCH: "Watch",
        TESSERACT: "Tesseract",
        THOUSAND_HANDED: "1000-handed",
        PROCRASTINATION: "Procrastination",
        ESSENCE: "Essence",
        CONCERT: "Concert",
    }
    # Short flavor lines, one per whole card. The named cards' lines are the
    # ones their named conditions carried, which are in turn the comments the
    # classic cards had before they were split.
    COMMENTS: ClassVar[dict[int, str]] = {
        JOKER: "Remember me?",
        EXPLORER: "The horizon calls.",
        ASTRONAUT: "Weightless.",
        PLANE: "Up, up and away.",
        PILLAR: "Built to last.",
        BANKER: "Money makes money.",
        WRECKING_BALL: "Demolition expert.",
        SKATER: "Radical.",
        GLITCH: "Now you see me.",
        RIPPED_CARD: "Barely holding together.",
        COZY: "Small and warm.",
        PAINTING: "A masterpiece.",
        SYNTHESIZER: "A chorus of parts.",
        ISLAND: "Surrounded by nothing.",
        ERR_404: "This card does not exist.",
        BLUEPRINT: "Copy of a copy.",
        SHOWMAN: "The more the merrier.",
        GARDEN: "Everything grows.",
        RIGGED_CASINO: "The house always wins.",
        CONQUISTADOR: "More land, more glory.",
        PEDESTAL: "Worthy of an encore.",
        INFERNO: "Let it all burn.",
        DOPPELGANGER: "Two of a kind.",
        COMPOUND_INTEREST: "Money makes money.",
        COUPON: "Clip and save.",
        FACTORY: "Mass production.",
        MINESHAFT: "Dig deeper.",
        MARKET: "Buy low, sell high.",
        WATCH: "Time is money.",
        TESSERACT: "A cube in a cube.",
        THOUSAND_HANDED: "A thousand hands, all helping.",
        PROCRASTINATION: "I'll do it in a second.",
        ESSENCE: "Distilled to the last drop.",
        CONCERT: "Turn it up to eleven.",
    }
    # What each whole card does. A named card's line states the payoff it pays
    # at its own magnitude (the card has no scorer half to roll, so the number
    # is fixed — see Card.NAMED for the arithmetic).
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        JOKER: "Adds 4 mult at the start of the run",
        EXPLORER: "Multiplies the multiplier by up to x2 at the end of the run, in proportion to the distance the marble travelled",
        ASTRONAUT: "Adds 4 mult at the end of the run for each second the marble was pulled by a black hole",
        PLANE: "Adds 15 chips at the end of the run for each second the marble was in the air",
        PILLAR: "Adds 1 mult at the start of the run for each block in the fullest column of the board",
        BANKER: "Adds 1 chip at the start of the run for every $10 you hold",
        WRECKING_BALL: "Adds 3 mult for each fragile block that breaks, permanently (the gains are kept only if the run is continued)",
        SKATER: "Multiplies the multiplier by 1.2 at the end of the run for each slippery block you own",
        GLITCH: "Adds a random 0 to 24 mult at the start of the run",
        RIPPED_CARD: "Adds 120 chips at the start of the run while the board holds 5 blocks or fewer",
        COZY: "Adds 90 chips at the start of the run while 10 or fewer board units are unlocked",
        PAINTING: "Adds 3 chips at the start of the run for each $1 of the total sell price of the blocks on your board",
        SYNTHESIZER: "Adds 3 mult at the start of the run for each card in your card area",
        ISLAND: "Adds 0.5 xMult at the start of the run for each unconnected group of unlocked board units",
        ERR_404: r"\marblatro\main.py, line 2339: 'self._return_card()' CardNotFoundError: Card was not found [FATAL]",
        BLUEPRINT: "Copies the function of the card to its immediate left in the card area",
        SHOWMAN: "Lets cards you already own show up in the shop again, so you can own more than one of the same card",
        GARDEN: "Seed blocks give +6 mult per seed on the board instead of +3",
        RIGGED_CASINO: "Random blocks give +xMult 3x more often and +chips 3x less often",
        CONQUISTADOR: "After each run, unlocks 4 random locked board squares adjacent to unlocked ones",
        PEDESTAL: "Retriggers the scorer of the first 3 blocks the marble touches in a run",
        INFERNO: "Adds 0.07 to the exponent the total score is raised to",
        DOPPELGANGER: "Each Start block releases a second marble, which starts with an x-velocity of 1",
        COMPOUND_INTEREST: "Doubles the interest on your cash: $2 for every $10 you hold at the end of a run",
        COUPON: "Every shop option costs 25% less (board units excluded)",
        FACTORY: "Resource conversions need half as many points (rounded up)",
        MINESHAFT: "Board units cost $5 instead of $8",
        MARKET: "Selling a card, block, or action refunds 75% of its price instead of 50%",
        WATCH: "The run ends automatically at the ideal finish time, but only the first 5 blocks the marble touches contribute to score",
        TESSERACT: "Every shop reroll permanently adds +0.1 xMult, applied at the start of each run",
        THOUSAND_HANDED: "Creates a random action after every run",
        PROCRASTINATION: "The first time every marble has finished a run, the run rewinds 1 second instead of ending: every block gets its triggers back and the marbles fly their last second again",
        ESSENCE: "Gives $10 at the end of every run, but takes a card slot away — selling it leaves 2 random permanent Spirit tokens",
        CONCERT: "Every block that is not a plain rect and has both an effect and a scorer can score 1 more time per run",
    }
    # All whole-card prices are 20% lower (rounded down): 24->19, 42->33,
    # 60->48, 46->36, 48->38, 56->44. The nine utility cards are priced by how
    # much run they give back (Inferno the most, Market the least).
    #
    # A named card costs the same 80% of its parts, where its "parts" are the
    # two halves it used to be composed from: its named condition's price plus
    # its canonical scorer's (see Card.NAMED; the component prices survive in
    # COMPONENT_PRICES). Joker 14+17=31 -> $24, Explorer 16+25=41 -> $32,
    # Astronaut 17+17=34 -> $27, Plane 16+12=28 -> $22, Pillar 16+17=33 -> $26,
    # Banker 14+12=26 -> $20, Wrecking Ball 17+17=34 -> $27, Skater 16+25=41 ->
    # $32, Glitch 12+17=29 -> $23, Ripped Card 12+12=24 -> $19, Cozy 17+12=29 ->
    # $23, Painting 15+12=27 -> $21, Synthesizer 15+17=32 -> $25, Island
    # 16+25=41 -> $32.
    PRICES: ClassVar[dict[int, int]] = {JOKER: 24, EXPLORER: 32, ASTRONAUT: 27,
                                        PLANE: 22, PILLAR: 26, BANKER: 20,
                                        WRECKING_BALL: 27, SKATER: 32,
                                        GLITCH: 23, RIPPED_CARD: 19,
                                        COZY: 23, PAINTING: 21,
                                        SYNTHESIZER: 25, ISLAND: 32,
                                        ERR_404: 19, BLUEPRINT: 33, SHOWMAN: 48,
                                        GARDEN: 36, RIGGED_CASINO: 38,
                                        CONQUISTADOR: 44, PEDESTAL: 44,
                                        INFERNO: 50, DOPPELGANGER: 46,
                                        COMPOUND_INTEREST: 36, COUPON: 46,
                                        FACTORY: 44, MINESHAFT: 28,
                                        MARKET: 26, WATCH: 40, TESSERACT: 44,
                                        THOUSAND_HANDED: 42,
                                        PROCRASTINATION: 46, ESSENCE: 48,
                                        CONCERT: 44}
    # Face colors and center glyphs for the mini-card look (one per card).
    COLORS: ClassVar[dict[int, tuple]] = {
        # The named cards: one identity colour each (the jester's violet, the
        # explorer's teal, the astronaut's space blue, the wrecking ball's iron,
        # ...). Card.face_color moves any of them that lands too close to its
        # rarity border.
        JOKER: (150, 60, 200),      # jester violet
        EXPLORER: (60, 145, 120),   # compass teal
        ASTRONAUT: (70, 90, 170),   # space blue
        PLANE: (120, 195, 235),     # sky blue
        PILLAR: (150, 145, 135),    # stone
        BANKER: (200, 165, 40),     # coin gold
        WRECKING_BALL: (85, 85, 95),  # iron
        SKATER: (60, 190, 190),     # ice cyan
        GLITCH: (120, 220, 90),     # glitch green
        RIPPED_CARD: (205, 175, 150),  # torn paper
        COZY: (200, 120, 70),       # warm clay
        PAINTING: (200, 90, 130),   # canvas rose
        SYNTHESIZER: (140, 90, 210),  # synth violet
        ISLAND: (230, 200, 120),    # sand
        ERR_404: (150, 40, 50),     # error red
        BLUEPRINT: (60, 110, 200),  # blueprint blue
        SHOWMAN: (210, 60, 90),     # showman red
        GARDEN: (90, 170, 70),      # garden green
        RIGGED_CASINO: (180, 45, 40),  # casino red
        CONQUISTADOR: (165, 120, 55),  # conquistador bronze
        PEDESTAL: (110, 105, 120),  # pedestal stone
        INFERNO: (200, 70, 20),     # molten orange
        DOPPELGANGER: (95, 70, 150),  # doubled violet
        COMPOUND_INTEREST: (35, 120, 100),  # banking teal
        COUPON: (170, 190, 60),     # coupon lime
        FACTORY: (80, 80, 95),      # industrial slate
        MINESHAFT: (120, 75, 45),   # mine brown
        MARKET: (60, 130, 80),      # market green
        WATCH: (170, 175, 185),     # watch steel
        TESSERACT: (45, 65, 155),   # hypercube indigo
        THOUSAND_HANDED: (205, 130, 30),  # saffron robe
        PROCRASTINATION: (125, 115, 160),  # sleepy lavender
        ESSENCE: (60, 150, 175),    # distilled cyan
        CONCERT: (185, 75, 150),    # stage magenta
    }
    # How far a card's face has to sit from its rarity border to be worth the
    # name, and the shades that move a face which is too close (smallest first,
    # lighter before darker). 60 is a little above the codebase's "50 in some
    # channel is tellable apart" line, because the border is only 2px wide.
    FACE_GAP = 60
    FACE_SHADES: ClassVar[tuple] = (0.25, 0.4, 0.55, 0.8, 1.0)
    # The fallback letter for a card with no art at all; every card here has
    # art (see ui._build_whole_card_art), so these are a safety net.
    GLYPHS: ClassVar[dict[int, str]] = {
        JOKER: "?", EXPLORER: "*", ASTRONAUT: "O", PLANE: "P", PILLAR: "I",
        BANKER: "$", WRECKING_BALL: "H", SKATER: "S", GLITCH: "#",
        RIPPED_CARD: "R", COZY: "~", PAINTING: "P", SYNTHESIZER: "Y",
        ISLAND: "L",
        ERR_404: "4", BLUEPRINT: "B", SHOWMAN: "!",
        GARDEN: "G", RIGGED_CASINO: "R", CONQUISTADOR: "C",
        PEDESTAL: "P", INFERNO: "I", DOPPELGANGER: "D",
        COMPOUND_INTEREST: "%", COUPON: "C", FACTORY: "F",
        MINESHAFT: "M", MARKET: "S", WATCH: "W",
        TESSERACT: "T", THOUSAND_HANDED: "H",
        PROCRASTINATION: "Z",
        ESSENCE: "E",
        CONCERT: "N",
    }
    # Every whole card, in id order, so the shop pool and the codex list the
    # named cards first and then the utility cards. The match-group cards are
    # not here (they are generated below, see MATCH_GROUP_CARD_OFFSET).
    ORDER: ClassVar[list[int]] = [JOKER, EXPLORER, ASTRONAUT, PLANE, PILLAR,
                                  BANKER, WRECKING_BALL, SKATER, GLITCH,
                                  ERR_404, BLUEPRINT, RIPPED_CARD,
                                  SHOWMAN, COZY, GARDEN,
                                  RIGGED_CASINO, CONQUISTADOR,
                                  PEDESTAL, INFERNO, DOPPELGANGER,
                                  COMPOUND_INTEREST, COUPON, FACTORY,
                                  MINESHAFT, MARKET, WATCH,
                                  PAINTING, SYNTHESIZER,
                                  TESSERACT,
                                  THOUSAND_HANDED, PROCRASTINATION, ESSENCE,
                                  CONCERT, ISLAND]
    # How rare each whole card is. A whole card's tier follows its price, the
    # codebase's usual rarity rule (see component_weight): up to $28 Common,
    # $29-$38 Unusual, $39-$44 Rare, $45-$47 Epic, $48 and up Legendary — so the
    # cheap economy cards are Common and the cards that rewrite how a run is
    # played (Showman, Essence, Inferno) are Legendary. Every match-group card is
    # COMMON instead (set in the MATCH GROUPS catalogue below), so every tier
    # above Common is a whole card.
    RARITIES: ClassVar[dict[int, int]] = {
        # Common: the joke card and the cheap utility.
        ERR_404: Rarity.COMMON, MARKET: Rarity.COMMON,
        MINESHAFT: Rarity.COMMON,
        # The named cards up to $28 are Common too (most of them), the three
        # dearest ($32) are Unusual.
        JOKER: Rarity.COMMON, PLANE: Rarity.COMMON, BANKER: Rarity.COMMON,
        PILLAR: Rarity.COMMON, ASTRONAUT: Rarity.COMMON,
        WRECKING_BALL: Rarity.COMMON, GLITCH: Rarity.COMMON,
        RIPPED_CARD: Rarity.COMMON, COZY: Rarity.COMMON,
        PAINTING: Rarity.COMMON, SYNTHESIZER: Rarity.COMMON,
        EXPLORER: Rarity.UNUSUAL, SKATER: Rarity.UNUSUAL, ISLAND: Rarity.UNUSUAL,
        # Unusual: single-mechanic helpers.
        BLUEPRINT: Rarity.UNUSUAL, GARDEN: Rarity.UNUSUAL,
        COMPOUND_INTEREST: Rarity.UNUSUAL, RIGGED_CASINO: Rarity.UNUSUAL,
        # Rare: cards that change a rule for the whole game.
        WATCH: Rarity.RARE, THOUSAND_HANDED: Rarity.RARE,
        CONQUISTADOR: Rarity.RARE, PEDESTAL: Rarity.RARE,
        FACTORY: Rarity.RARE, TESSERACT: Rarity.RARE, CONCERT: Rarity.RARE,
        # Epic: the economy cards that compound over a whole game.
        COUPON: Rarity.EPIC, DOPPELGANGER: Rarity.EPIC,
        PROCRASTINATION: Rarity.EPIC,
        # Legendary: the most expensive whole cards.
        SHOWMAN: Rarity.LEGENDARY, ESSENCE: Rarity.LEGENDARY,
        INFERNO: Rarity.LEGENDARY,
    }
    # --- The named cards' effects: id -> (phase, scorer, ratio, measure) ---
    # Each named card fires ONCE per run (or once per fragile break) and pays a
    # fixed amount: the canonical pairing it had as a named condition, at the
    # magnitude model every card in the game used then. ``scorer`` and ``ratio``
    # together give the payoff through components.magnitude_payoff(scorer, ratio,
    # units) — the standard bases are +30 chips / +4 mult / +0.25 xMult per unit,
    # scaled by the ratio — and ``measure`` names the per-run number the card
    # scales by (see cards._named_card_units). A whole card has no scorer half to
    # roll, so ``units`` is all that varies: the numbers below are the canonical
    # ones, e.g. Joker 1 unit x ratio 1.0 = +4 mult, Plane ratio 0.5 = +15 chips
    # an air second, Pillar ratio 0.25 = +1 mult a column block, Banker ratio
    # 1/30 = +1 chip per $10, Ripped Card 4.0 = +120 chips, Cozy 3.0 = +90 chips,
    # Painting 0.1 = +3 chips a dollar, Synthesizer 0.75 = +3 mult a card and
    # Island 2.0 = +0.5 xMult a group (1 + 0.25 x 2 x groups).
    #   phase   "start"  -> cards.apply_cards, at the start of every run
    #           "end"    -> cards.apply_cards_on_finish, once the run is over
    #           "fragile"-> cards.on_fragile_broken, each fragile break
    NAMED: ClassVar[dict[int, tuple]] = {
        JOKER: ("start", Scorer.MULT_ADD, 1.0, "start"),
        EXPLORER: ("end", Scorer.MULT_MUL, 1.0, "distance"),
        ASTRONAUT: ("end", Scorer.MULT_ADD, 1.0, "black_hole"),
        PLANE: ("end", Scorer.CHIPS_ADD, 0.5, "air_time"),
        PILLAR: ("start", Scorer.MULT_ADD, 0.25, "fullest_column"),
        BANKER: ("start", Scorer.CHIPS_ADD, 1.0 / 30.0, "cash_held"),
        WRECKING_BALL: ("fragile", Scorer.MULT_ADD, 0.75, "fragile_breaks"),
        SKATER: ("end", Scorer.MULT_MUL, 0.8, "slippery"),
        GLITCH: ("start", Scorer.MULT_ADD, 1.0, "random"),
        RIPPED_CARD: ("start", Scorer.CHIPS_ADD, 4.0, "few_blocks"),
        COZY: ("start", Scorer.CHIPS_ADD, 3.0, "cozy"),
        PAINTING: ("start", Scorer.CHIPS_ADD, 0.1, "painting"),
        SYNTHESIZER: ("start", Scorer.MULT_ADD, 0.75, "synthesizer"),
        ISLAND: ("start", Scorer.MULT_MUL, 2.0, "island"),
    }

    @classmethod
    def name(cls, card):
        return cls.NAMES.get(card, "Unknown")

    @classmethod
    def comment(cls, card):
        return cls.COMMENTS.get(card, "")

    @classmethod
    def description(cls, card):
        return cls.DESCRIPTIONS.get(card, "Unknown card.")

    @classmethod
    def rarity(cls, card):
        """The card's rarity tier (see Rarity); an unknown card is Common."""
        return cls.RARITIES.get(card, Rarity.COMMON)

    @classmethod
    def rarity_name(cls, card):
        return Rarity.name(cls.rarity(card))

    @classmethod
    def rarity_color(cls, card):
        return Rarity.color(cls.rarity(card))

    @classmethod
    def face_color(cls, card):
        """The colour a card's FACE is drawn in (see ui.draw_card).

        A card is outlined in its RARITY colour, so a face too close to that
        outline would swallow it — the Unusual Garden card is green on a green
        border. Such a face is moved away from its border by the SMALLEST shade
        of its own colour that clears FACE_GAP (lighter first, because the card
        colours are muted pastels and a lighter shade keeps the card looking
        like itself), so the tier outline reads while the card stays its own
        colour. A face that is already far enough from its border — almost every
        card — is returned untouched.
        """
        base = cls.COLORS.get(card, GRAY)
        border = Rarity.color(cls.rarity(card))
        if color_gap(base, border) >= cls.FACE_GAP:
            return base
        for factor in cls.FACE_SHADES:
            for direction in (1, -1):
                moved = shade(base, factor * direction)
                if color_gap(moved, border) >= cls.FACE_GAP:
                    return moved
        # Unreachable: a full white or black shade is far from every tier colour
        # (the loop's last factor), but never hand back a face that fights its
        # border.
        return WHITE if color_gap(WHITE, border) >= color_gap((0, 0, 0), border) else (0, 0, 0)


    @classmethod
    def rarity_weight(cls, card):
        """The shop-frequency weight of the card's TIER (see Rarity.WEIGHTS).

        The tier is what the shop weighs and draws first; the card inside the
        tier is then drawn flat, so this is the tier's weight rather than the
        card's own odds (compare main.random_card_option_value).
        """
        return Rarity.weight(cls.rarity(card))


# The named cards, in catalogue order — the list the tests and the collection
# can walk without knowing which ids happen to be named (see Card.NAMED).
NAMED_CARD_ORDER: list[int] = [card for card in Card.ORDER if card in Card.NAMED]


def named_card_meta(card):
    """(phase, scorer, ratio, measure) for a named card, or None.

    None means the card is not one of the fourteen named cards: the utility
    whole cards and the match-group cards have no start/end/fragile effect of
    their own (a match-group card fires on a collision instead).
    """
    return Card.NAMED.get(card)


def named_card_phase(card):
    """When a named card fires: "start", "end", "fragile", or None."""
    meta = named_card_meta(card)
    return meta[0] if meta is not None else None


# ---------------------------------------------------------------------------
# COMMENTED OUT (user request: "comment out all the code for conditions").
# The whole condition system below is kept verbatim as a string literal so it
# can be restored by deleting the two wrapper lines around it; nothing in the
# game reads it. Cards are made of a MATCH GROUP and a scorer now — see the
# MATCH GROUPS section at the end of this file.
# ---------------------------------------------------------------------------
_COMMENTED_OUT_CONDITION_CLASS = r'''
class Condition:
    """The trigger half of a split card.

    Every splittable card splits into a scorer (what it does to the score) and
    a condition (when it does it). The named conditions fire once at the start
    or end of a run (some scaled by a per-run measure such as distance travelled
    or time in a black hole); collision conditions fire once per fresh marble
    collision with a matching block, with one condition per shape and one per
    effect (their ids live past the named triggers so the shape/effect payload
    can be recovered from the id). Each named condition is named after the
    original whole card it was split from (e.g. the start-of-run condition that
    used to be the Joker card is called "Joker"); pairing a condition with its
    original scorer recreates that card's effect exactly, and pairing it with
    any other card scorer gives the same trigger with that scorer's payoff
    scaled by the condition's magnitude (see NAMED_CONDITION_RATIO).
    """
    # Named triggers, each named after the card it was split from, and paired
    # with that card's canonical scorer (recreating it exactly).
    START = 0          # Joker (start of run, +Mult) — one unit
    DISTANCE = 1       # Explorer (end of run, xMult) — 4 units per full board
    BLACK_HOLE = 2     # Astronaut (end of run, +Mult) — one unit per second
    AIR_TIME = 3       # Plane (end of run, +Chips) — one unit per air second
    FULLEST_COLUMN = 4 # Pillar (start of run, +Mult) — one unit per column block
    CASH_HELD = 5      # Banker (start of run, +Chips) — one unit per $10 held
    FRAGILE_BREAKS = 6 # Wrecking Ball (each fragile break, +Mult, permanent)
    SLIPPERY = 7       # Skater (end of run, xMult) — one unit per slippery block owned
    RANDOM = 8         # Glitch (start of run, +Mult) — random units
    FEW_BLOCKS = 9     # Ripped Card (start of run when few blocks, +Chips)
    # Cozy (start of run when the board has few units, 3x base). Its id sits in
    # the free 11..99 band below SHAPE_BASE so it never overlaps a whole-card
    # id (which share this space with the named conditions).
    COZY = 79
    # Painting (start of run, 1/10 base per $1 of the board's total sell value):
    # a board full of expensive blocks paints a big payoff. Its id continues
    # that same shared band, above the whole cards (83..91, 94..95).
    PAINTING = 92
    # Synthesizer (start of run, scaled by the cards you own): at its 3/4 ratio
    # the +Mult scorer pays +3 mult per card in the card area, so the canonical
    # Synthesizer card is "+3 mult at the start of the run for each card".
    SYNTHESIZER = 93
    # Island (start of run, scaled by the separate groups the unlocked board
    # units form): at its 2x ratio the xMult scorer multiplies by 1.5 per
    # group, so the canonical Island card is "+0.5 xMult for each unconnected
    # group of unlocked board units". Its id is the last free one in the shared
    # band below SHAPE_BASE (see class Card).
    ISLAND = 99
    # Collision conditions start here; ids in the SHAPE_BASE.. range map back to
    # a Shape, ids in EFFECT_BASE.. map back to an Effect. EFFECT_BASE is a
    # FIXED id (not SHAPE_BASE + len(Shape.ORDER)) so that adding new shapes to
    # Shape.ORDER — which pushes the shape-condition ids up — never renumbers
    # the effect collision-conditions (saved games and collection entries
    # reference these by id). Shape ids must stay below EFFECT_BASE.
    SHAPE_BASE = 100
    EFFECT_BASE = 140

    NAMES: ClassVar[dict[int, str]] = {
        START: "Joker",
        DISTANCE: "Explorer",
        BLACK_HOLE: "Astronaut",
        AIR_TIME: "Plane",
        FULLEST_COLUMN: "Pillar",
        CASH_HELD: "Banker",
        FRAGILE_BREAKS: "Wrecking Ball",
        SLIPPERY: "Skater",
        RANDOM: "Glitch",
        FEW_BLOCKS: "Ripped Card",
        COZY: "Cozy",
        PAINTING: "Painting",
        SYNTHESIZER: "Synthesizer",
        ISLAND: "Island",
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        START: "?", DISTANCE: "*", BLACK_HOLE: "O", AIR_TIME: "P",
        FULLEST_COLUMN: "I", CASH_HELD: "$", FRAGILE_BREAKS: "H",
        SLIPPERY: "S", RANDOM: "#", FEW_BLOCKS: "R", COZY: "~",
        PAINTING: "P", SYNTHESIZER: "Y", ISLAND: "L",
    }
    # Flavor lines for the named conditions. These are the comments that used
    # to belong to the classic whole cards, moved onto the conditions they were
    # split into (e.g. the Joker's "Remember me?" now lives on the start-of-run
    # condition named "Joker").
    COMMENTS: ClassVar[dict[int, str]] = {
        START: "Remember me?",
        DISTANCE: "The horizon calls.",
        BLACK_HOLE: "Weightless.",
        AIR_TIME: "Up, up and away.",
        FULLEST_COLUMN: "Built to last.",
        CASH_HELD: "Money makes money.",
        FRAGILE_BREAKS: "Demolition expert.",
        SLIPPERY: "Radical.",
        RANDOM: "Now you see me.",
        FEW_BLOCKS: "Barely holding together.",
        COZY: "Small and warm.",
        PAINTING: "A masterpiece.",
        SYNTHESIZER: "A chorus of parts.",
        ISLAND: "Surrounded by nothing.",
    }
    # The trigger phrase for each named condition, used in the collection and
    # the card builder (collision triggers are built from their shape/effect).
    TRIGGERS: ClassVar[dict[int, str]] = {
        START: "at the start of the run",
        DISTANCE: "at the end of the run, scaled up to 4x base by the distance the marble travels",
        BLACK_HOLE: "at the end of the run, for each second the marble is pulled by a black hole",
        AIR_TIME: "at the end of the run, for each second the marble is in the air",
        FULLEST_COLUMN: "at the start of the run, for each block in the fullest column of the board",
        CASH_HELD: "at the start of the run, for every $10 you hold",
        FRAGILE_BREAKS: "each time a fragile block breaks",
        SLIPPERY: "at the end of the run, for each slippery block you own",
        RANDOM: "at the start of the run, choosing a random magnitude",
        FEW_BLOCKS: "at the start of the run, when there are 5 blocks or fewer in the board",
        COZY: "at the start of the run, when the board has 10 unlocked units or fewer",
        PAINTING: "at the start of the run, for each $1 of the total sell price of the blocks on your board",
        SYNTHESIZER: "at the start of the run, for each card in your card area",
        ISLAND: "at the start of the run, for each unconnected group of unlocked board units",
    }
    # The same phrase for a FLAT card (a generic scorer: Cash, Sharp, Parts,
    # Summit, Voyager, ...). A flat card pays ONE block-style trigger instead of
    # scaling with the condition's measured units, so it only states the GATE —
    # the point at which the condition counts at all (the same gate the runtime
    # checks, see cards._condition_fired). A magnitude (unit-scorer) card keeps
    # the TRIGGERS phrasing above, which is accurate because it really does
    # scale per unit. Conditions that are already pure gates (Start, Few Blocks,
    # Cozy, Fragile Breaks) are not listed and read the same either way.
    FLAT_TRIGGERS: ClassVar[dict[int, str]] = {
        DISTANCE: "at the end of the run, once the marble has traveled",
        BLACK_HOLE: "at the end of the run, once the marble has been pulled by a black hole",
        AIR_TIME: "at the end of the run, once the marble has been in the air",
        FULLEST_COLUMN: "at the start of the run, if the board has any blocks",
        CASH_HELD: "at the start of the run, if you hold at least $10",
        SLIPPERY: "at the end of the run, if you own a slippery block",
        RANDOM: "at the start of the run",
        PAINTING: "at the start of the run, if the board is worth anything",
        SYNTHESIZER: "at the start of the run, if you own a card",
        ISLAND: "at the start of the run",
    }

    @classmethod
    def name(cls, condition):
        """A condition's short display name (a shape/effect name for collision)."""
        shape = condition_shape(condition)
        if shape is not None:
            return Shape.name(shape)
        effect = condition_effect(condition)
        if effect is not None:
            return Effect.name(effect)
        return cls.NAMES.get(condition, "Unknown")

    @classmethod
    def comment(cls, condition):
        """A condition's flavor comment (blank for collision conditions)."""
        return cls.COMMENTS.get(condition, "")
'''
# --- end of the commented-out Condition class --------------------------------


class Action:
    """A one-use power-up bought from the shop that modifies a block or a card.

    Each class constant is an action's ID number (e.g. ``Action.DEATH == 0``).
    Actions come in two versions: v1 (as bought) and v2 (upgraded for
    ACTION_UPGRADE_COST), with v2 being much stronger. v2 cannot be upgraded
    further. The player can hold up to MAX_ACTIONS at once, and uses an action
    by selecting it, picking a block/card subject, and pressing S. A newly
    created action is usually v1, but a rare one (ACTION_V2_CHANCE, see
    ``random_action_version`` in main) is handed over already upgraded for
    free — so v2 is both a purchase and an occasional windfall.
    """
    DEATH = 0
    RECOGNITION = 1
    DEJA_VU = 2
    ANOINTMENT = 3
    STRENGTH = 4
    SPIRIT = 5
    CLEANSWEEP = 6

    NAMES: ClassVar[dict[int, str]] = {
        DEATH: "Death",
        RECOGNITION: "Recognition",
        DEJA_VU: "Deja Vu",
        ANOINTMENT: "Anointment",
        STRENGTH: "Strength",
        SPIRIT: "Spirit",
        CLEANSWEEP: "Cleansweep",
    }
    # What the v1 action does. The descriptions mention the v2 upgrade so the
    # shop and collection show both versions at a glance.
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        DEATH: "Sells a chosen block or card for 50% more than its price (v2: 6x).",
        RECOGNITION: "Duplicates a chosen block for a price equal to its cost (v2: duplicates a card).",
        DEJA_VU: "Gives a chosen block +1 trigger (v2: +100 triggers).",
        ANOINTMENT: "Gives a chosen block 2 random effects (v2: gives every block you own one).",
        STRENGTH: "Raises a chosen block's scorer amount by 50% (v2: triples it).",
        SPIRIT: "Destroys a chosen block and applies its scorer at the start of the next 2 runs (v2: permanently).",
        CLEANSWEEP: "Spends every dollar you hold (cash goes to $0) to fill each empty card slot with a "
                    "random card (v2: keeps your cash).",
    }
    # What the upgraded (v2) action does.
    V2_DESCRIPTIONS: ClassVar[dict[int, str]] = {
        DEATH: "Sells a chosen block or card for 6x its price.",
        RECOGNITION: "Duplicates a chosen card for a price equal to its cost.",
        DEJA_VU: "Gives a chosen block +100 triggers.",
        ANOINTMENT: "Gives every block on the board and in the inventory one new random effect.",
        STRENGTH: "Triples a chosen block's scorer amount.",
        SPIRIT: "Destroys a chosen block and applies its scorer at the start of every run, permanently.",
        CLEANSWEEP: "Fills each empty card slot with a random card, without spending your cash.",
    }
    # Short flavor lines, one per action.
    COMMENTS: ClassVar[dict[int, str]] = {
        DEATH: "All things must end.",
        RECOGNITION: "A nod to the familiar.",
        DEJA_VU: "Haven't we been here before?",
        ANOINTMENT: "Blessed with power.",
        STRENGTH: "Swing harder.",
        SPIRIT: "It lingers on.",
        CLEANSWEEP: "The house takes the rest.",
    }
    # Actions are cheap one-use power-ups: their prices were halved (48 -> 24,
    # 56 -> 28), so a run can afford one almost any time. Deja Vu costs a little
    # more than the other two: it is worth about one cash trigger-limit
    # upgrade, and its v2 converts a block into a near-inexhaustible scorer.
    # The three later actions are stronger, so they sit a tier above. Cleansweep
    # sits at the top of that tier: its own price is small next to the purse it
    # sweeps away, and what it buys is up to five cards.
    PRICES: ClassVar[dict[int, int]] = {DEATH: 24, RECOGNITION: 24, DEJA_VU: 28,
                                        ANOINTMENT: 32, STRENGTH: 28, SPIRIT: 36,
                                        CLEANSWEEP: 70}
    # Face colors and center glyphs for the mini-action look (one per action).
    COLORS: ClassVar[dict[int, tuple]] = {
        DEATH: (120, 45, 45),        # deathly red
        RECOGNITION: (60, 100, 180), # recognition blue
        DEJA_VU: (105, 65, 150),     # dizzy violet
        ANOINTMENT: (35, 125, 95),   # blessed emerald
        STRENGTH: (175, 85, 35),     # brawny amber
        SPIRIT: (140, 140, 160),     # spectral grey
        CLEANSWEEP: (40, 140, 160),  # sweeping teal
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        DEATH: "D", RECOGNITION: "R", DEJA_VU: "V",
        ANOINTMENT: "A", STRENGTH: "S", SPIRIT: "P",
        CLEANSWEEP: "C",
    }
    ORDER: ClassVar[list[int]] = [DEATH, RECOGNITION, DEJA_VU, ANOINTMENT,
                                  STRENGTH, SPIRIT, CLEANSWEEP]
    # Actions that act on the game itself rather than on a chosen block or card:
    # they need no subject, so selecting one and pressing S uses it straight
    # away (see Game._apply_action).
    NO_TARGET: ClassVar[tuple[int, ...]] = (CLEANSWEEP,)

    @classmethod
    def name(cls, action):
        return cls.NAMES.get(action, "Unknown")

    @classmethod
    def description(cls, action, version=1):
        """The action's effect text for the given version (v2 is stronger)."""
        if version >= 2:
            return cls.V2_DESCRIPTIONS.get(action, "Unknown action.")
        return cls.DESCRIPTIONS.get(action, "Unknown action.")

    @classmethod
    def comment(cls, action):
        return cls.COMMENTS.get(action, "")

    @classmethod
    def needs_target(cls, action):
        """True when the action must be given a block/card before it fires.

        A target-free action (see NO_TARGET) affects the player rather than one
        of their pieces, so it can be used the moment it is selected.
        """
        return action not in cls.NO_TARGET

    @classmethod
    def cycle(cls, action):
        idx = cls.ORDER.index(action) if action in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


# --- Magnitudes -------------------------------------------------------------
# Every scalable value in the game (a scorer's amount, a piston's launch speed)
# is a MAGNITUDE rolled around its average when the item is created. One STEP is
# 10% of the average, so a magnitude always moves in proportion to itself, and
# the deviation x from the average is CONTINUOUS — any real number of steps, not
# a whole one — with probability falling off as 1/(x^2 + MAGNITUDE_SPREAD): a
# roll lands within half a step of the average about 0.18 of the time, within
# one step 0.35, within two 0.59, within four 0.84, and the widest roll
# (|x| <= MAGNITUDE_MAX_STEPS, i.e. +/- 80% of the average) is roughly 1/17 as
# likely as being right on it. The shape is a Cauchy distribution (whose scale
# is the SQUARE ROOT of the spread) truncated to the cap, so it is sampled
# exactly rather than by rejection (see main.roll_magnitude). A bigger spread
# flattens the middle and thickens the tail — more rolls land far from the
# average — while the cap still holds every deviation to MAGNITUDE_MAX_STEPS.
MAGNITUDE_STEP_FRACTION = 0.1
MAGNITUDE_STEP_DIVISOR = 10  # 1 / MAGNITUDE_STEP_FRACTION, as a whole number
                             # for exact step arithmetic (average / 10)
MAGNITUDE_MAX_STEPS = 8
# The "spread" in the deviation's 1/(x^2 + spread) falloff, and the Cauchy
# scale it implies (the scale is its square root: 4 -> 2). This is the one dial
# on how wild the rolls are: at a spread of 1 the widest roll is about 1/65 as
# likely as landing right on the average, at 4 it is 1/17, so the extremes that
# used to be near-impossible now come up routinely.
MAGNITUDE_SPREAD = 4
MAGNITUDE_SCALE = math.sqrt(MAGNITUDE_SPREAD)
# The widest deviation as an ANGLE: drawing one uniformly in +/- this, scaling it
# by MAGNITUDE_SCALE and taking the tangent lands a deviation on the
# 1/(x^2 + MAGNITUDE_SPREAD) curve above, because the scaled tangent is that
# distribution's inverse. Public so the sampler (main.py) and the distribution's
# tests share one definition of the range.
MAGNITUDE_ATAN_LIMIT = math.atan(MAGNITUDE_MAX_STEPS / MAGNITUDE_SCALE)


def magnitude_step(average):
    """The size of one deviation step for a value whose average is `average`.

    Exactly a tenth of the average, NEVER rounded: a +Chips scorer averages 30
    chips and steps by 3, an xMult averages 1.5 and steps by 0.15, and a +Mult
    scorer averages 4 and steps by 0.4 — rounding that to a whole 1 would
    stretch the whole distribution (the widest +Mult roll would be 12 instead
    of 7.2, i.e. a 25% step rather than the 10% every other magnitude uses).
    The division keeps the step exact for a whole average (30 / 10 is exactly
    3, where 30 * 0.1 is not). A value with no average (a scorer whose amount
    is unused, such as Start or Lucky) has no step and is never rolled.
    """
    if not average:
        return 0
    return average / MAGNITUDE_STEP_DIVISOR


def magnitude_precision(average):
    """The decimals a rolled value of this average is written with.

    A magnitude's deviation moves in a tenth of a step (1% of the average), so
    two significant digits past the average's own scale are all a roll can
    mean. Rounding there is SCALE-FREE — it keeps 0.0137 for a 0.01-average
    Voyager exactly as it keeps 36.6 for a 30-chip scorer — and it strips the
    float dust of the (10 + x)/10 arithmetic, so a rolled value prints, prices
    and saves as the clean number it is meant to be rather than as
    36.60000000000001.
    """
    if not average:
        return 0
    return max(0, 3 - math.floor(math.log10(abs(average))))


def magnitude_floor(average, step, multiplier=False):
    """The lowest magnitude a roll may land on (never zero or negative).

    A MULTIPLIER magnitude (xMult, Sharp, Satanic, Effective) also never drops
    below 1, so a rolled-down xMult block is weak rather than actively harmful.
    """
    if not step:
        return average
    if multiplier:
        return min(average, max(step, 1.0))
    return step


def magnitude_deviation(average, magnitude, precision=None):
    """The "(+2)" / "(-1)" / "(0)" a magnitude is described with, or "".

    Written RIGHT AFTER the magnitude it belongs to ("Adds +6 mult (+2) when
    touched") instead of at the end of the sentence, and the sidebar colours it
    (green above average, red below, grey for exactly average — see
    ui.draw_item_info). It is rounded to the same precision the number it sits
    next to is written with — a magnitude's own (see magnitude_precision), or
    the ``precision`` a caller passes for a number it formats itself (a
    resource-point count prints three decimals, see points_text) — so the token
    always adds up with the value beside it. A value with no average has no
    deviation to show.
    """
    if not average or magnitude is None:
        return ""
    if precision is None:
        precision = magnitude_precision(average)
    diff = round(magnitude - average, precision)
    return f" ({diff:+g})" if diff else " (0)"


def points_text(points):
    """A resource-point count as a decimal, rounded to three places.

    The count lands on the step of a rolled magnitude, so it is not on any
    small fraction's grid: a Rubble trigger banks 0.5 points at the average
    (1 x 1/2), 0.55 one step up, 0.7 four steps up — and a Shreds roll of 1.1
    banks a third of a point more than its own average. A fraction with a
    small denominator states those dishonestly (limit_denominator(6) reads 0.7
    as "2/3" and 1.1/3 as "1 1/6"), and the deviation printed next to the
    count has to add up with it. Three places is finer than the smallest step
    (a Shreds trigger's 1/30 of a point) and absorbs float noise from a bank
    that has been added up over many triggers.
    """
    return f"{round(points, 3):g}"


def resource_points_for(scorer, amount):
    """The resource points ONE trigger of a scorer banks, at its own magnitude.

    A trigger banks a fraction of a point — 1/3 for Shreds and 1/2 for
    Rubble/Ideas/Picky at the average magnitude — and one whole point converts
    into that scorer's reward (see Scorer.RESOURCE_RATE / RESOURCE_THRESHOLD).
    The reward RATE is therefore what it always was (3 Shreds triggers a card,
    2 Rubble triggers a block): the bank now just reads as one point a reward.
    """
    return (amount or 0) * Scorer.RESOURCE_RATE.get(scorer, 0.0)


def resource_points_deviation(scorer, amount=None):
    """The "(+0.2)" token for a resource-point count, or "" when unrolled.

    A resource-point description states the deviation of the POINT count it
    shows, not of the scorer's own magnitude, so the token always adds up with
    the number it sits next to: a Rubble block rolled to 1.4 banks 0.7 points,
    which is (+0.2) over the 0.5 average, even though its magnitude is (+0.4)
    over 1. A missing amount (a catalogue description) states no token at all,
    exactly as a scorer's own average states "" from magnitude_deviation.
    """
    average = resource_points_for(scorer, Scorer.DEFAULT_AMOUNT.get(scorer, 0))
    if not average or not amount:
        return ""
    # The count is written with points_text's three decimals, so the token is
    # rounded to the same three: they have to add up on screen.
    return magnitude_deviation(average, resource_points_for(scorer, amount),
                               precision=3)


def scorer_magnitude_deviation(scorer, amount):
    """The deviation token for a scorer's own amount ("" when unrolled)."""
    return magnitude_deviation(Scorer.DEFAULT_AMOUNT.get(scorer, 0), amount)


def scorer_magnitude_step(scorer):
    """One deviation step for a scorer's amount (0 when it has no magnitude)."""
    return magnitude_step(Scorer.DEFAULT_AMOUNT.get(scorer, 0))


def scorer_magnitude_floor(scorer):
    """The lowest amount a scorer's magnitude may roll to."""
    average = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    return magnitude_floor(average, scorer_magnitude_step(scorer),
                           scorer in Scorer.MULTIPLIER_SCORERS)


def scorer_magnitude_scale(scorer, amount):
    """A scorer's magnitude relative to its average (1.0 when unrolled).

    A composed card scales its payoff by this factor, exactly as a block's
    payoff follows its own amount: a +Chips half rolled to 45 pays 1.5x the
    average card. A scorer with no average (Lucky, Quick, ...) is never
    scaled, so it always comes back as 1.0.
    """
    average = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    if not average or not amount:
        return 1.0
    return amount / average


def effect_magnitude_step(effect):
    """One deviation step for a scalable effect (0 for an on/off effect)."""
    return magnitude_step(Effect.MAGNITUDE.get(effect, 0))


def effect_magnitude_floor(effect):
    """The lowest magnitude a scalable effect's roll may land on."""
    return magnitude_floor(Effect.MAGNITUDE.get(effect, 0),
                           effect_magnitude_step(effect))


def effect_magnitude_deviation(effect, magnitude):
    """The deviation token for a scalable effect's own magnitude ("" if none)."""
    return magnitude_deviation(Effect.MAGNITUDE.get(effect, 0), magnitude)


def _plural(amount):
    """A plural "s" for a whole-number magnitude (1 -> "", 2 -> "s").

    Named _plural rather than _s because the condition-price table below uses
    _s as its shape loop variable.
    """
    return "" if amount == 1 else "s"


def _plural_points(points):
    """A plural "s" for a resource-point count (0.5 -> "", 1.5 -> "s")."""
    return "" if points <= 1 else "s"


def shape_description(shape):
    """A one-line description of what a shape does to the marble."""
    return {
        Shape.RECT: "Solid rectangle: a floor, wall, or platform.",
        Shape.SLOPE: "Slanted triangle: marbles roll downhill along it.",
        Shape.LINE: "Thin line, solid on both sides: marbles ride along it.",
        Shape.NONE: "No hitbox: an invisible field marbles pass straight through.",
        Shape.CIRCLE: "Solid circle: marbles roll around it.",
        Shape.CURVED_SLOPE: "Inward-curving slope: marbles roll down the concave arc.",
        Shape.PIPE: "A vertical pipe: two walls with a gap the marble can pass through.",
        Shape.DRAIN: "A square funnel: curved walls guide marbles down to a marble-wide drain.",
        Shape.PIPE_BEND: "A pipe bend: a marble-wide channel that turns from one side to an adjacent side.",
        Shape.CONVEX_SLOPE: "Outward-curving slope: marbles roll down the convex arc.",
        Shape.FLAT_LINE: "A thin flat line along the bottom: marbles roll along it like a floor.",
        Shape.CURVED_SLOPE_LINE: "The curved slope's arc with no sides: marbles ride the bare curve.",
        Shape.HALF_PIPE: "A half-pipe: a bottom-semicircle line, solid on both sides.",
        Shape.SPIKE: "An upward triangle: a marble landing on it is split left or right.",
        Shape.PLATFORM: "A thick shelf filling the bottom half of the unit: stairs, ledges, and floors.",
        Shape.CORNER: "An L bracket in the bottom-left: a wall and a floor, for pockets and steps.",
        Shape.PEG: "A small solid circle (5 px): a compact obstacle to bounce around.",
        Shape.SAWTOOTH: "A row of small teeth along the bottom: the marble tumbles unpredictably over them.",
        # COMMENTED OUT with the shape itself: Shape.CRADLE would describe a
        # V-shaped valley that catches a marble and settles it at the center.
        Shape.BUMP: "A solid dome along the bottom: the marble rolls up and over it.",
        Shape.KEY: "A pass-through key: a marble that passes through it opens the Lock "
                   "block with the same key number.",
        Shape.LOCK: "A solid locked door filling the unit: it blocks marbles until the "
                    "marble passes through the matching Key block (locks close again at "
                    "the start of every run).",
    }.get(shape, "Unknown shape.")


def effect_description(effect, magnitude=None):
    """A one-line description of what an effect does to the marble.

    A scalable effect (Piston, Accelerator, Black Hole, ...) also says its own
    magnitude and how far that sits from the average (see effect_magnitude_note);
    the average itself is shown when no magnitude is given.
    """
    average = Effect.MAGNITUDE.get(effect, 0)
    if not magnitude:
        magnitude = average
    dev = effect_magnitude_deviation(effect, magnitude)
    text = {
        Effect.NONE: "No special effect.",
        # The scaleable effects state their own magnitude, with the deviation
        # right after it (a green/red/grey "(+2)" in the sidebar).
        Effect.BOUNCY: f"Bounces marbles back at {magnitude:g}% of their impact speed{dev}",
        Effect.ACCELERATOR: f"Pushes marbles in the direction of its arrow at {magnitude:g} px/s^2{dev}",
        Effect.PISTON: f"Launches marbles at {magnitude:g} px/s along its surface{dev}",
        Effect.GRAVITY: "Redirects gravity to the direction of its arrow.",
        Effect.BLACK_HOLE: f"Pulls marbles toward it with {magnitude:g} px/s^2 of gravity"
                           f"{dev}, stronger up close",
        Effect.PORTAL: "Teleports marbles to its matching numbered portal. "
                       "Each portal pair can only be used 100 times per run "
                       "before the portal stops working for that run.",
        Effect.ROTATE: f"Rotates at {magnitude:g} deg/s and flings marbles along its spin{dev}",
        Effect.SLIPPERY: "Marbles slide over it and keep all their speed.",
        Effect.FRAGILE: "Shatters into a no-hitbox field after a marble touches it and leaves.",
        Effect.GROWING: "Doubles the marble's radius when touched.",
        Effect.SHRINKING: "Halves the marble's radius when touched.",
        Effect.STICKY: f"Slows marbles on impact (more at higher speed) and holds them "
                       f"for {magnitude:g} s{dev}",
        Effect.REPULSOR: f"Pushes marbles away from it with {magnitude:g} px/s^2 of force"
                         f"{dev}, harder the closer they get",
        Effect.CONVEYOR: f"Carries marbles along its surface in the direction of its arrow "
                         f"at a constant {magnitude:g} px/s{dev}",
        Effect.ZIPPER: "One-way gate: marbles pass through it moving with its arrow, "
                       "and collide with it moving against the arrow.",
        Effect.PHASE: f"Touching it lets the marble pass through every block for "
                      f"{magnitude:g} second{_plural(magnitude)}{dev}",
        Effect.SPLITTER: "Splits the marble in two when touched: the copy is flung back "
                         "the opposite way (reflected over the block's surface).",
    }.get(effect, "Unknown effect.")
    return f"{text}." if text[-1] != "." else text


def scorer_description(scorer, amount=None):
    """A one-line description of what a scorer does to the score.

    ``amount`` is the scorer's OWN magnitude (the item's rolled amount); a
    missing or zero amount means the average. Every scaleable scorer states its
    magnitude with the deviation right after it — "Adds +6 mult (+2) when
    touched" — which the sidebar colours green/red/grey (see
    magnitude_deviation). A resource-point scorer states the deviation of the
    POINT count instead, the number the player actually reads (see
    resource_points_deviation).
    """
    average = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    if not amount:
        amount = average
    dev = scorer_magnitude_deviation(scorer, amount)
    # A Shreds/Rubble/Ideas/Picky row reads "Gives 0.7 rubble point (+0.2)", so
    # its token follows the point count rather than the scorer's magnitude.
    pdev = resource_points_deviation(scorer, amount)
    return {
        Scorer.NONE: "No scoring effect.",
        Scorer.CHIPS_ADD: f"Adds {amount:g} chips{dev} when touched",
        Scorer.MULT_ADD: f"Adds +{amount:g} mult{dev} when touched",
        Scorer.MULT_MUL: f"Multiplies the multiplier by {amount:g}{dev} when touched",
        Scorer.START: "Start point: marbles are released here.",
        Scorer.FINISH: "Goal: reaching it finishes a marble's run.",
        Scorer.QUICK: "Adds chips based on how fast the marble is moving when it hits.",
        Scorer.CASH: f"Gives ${amount:.0f}{dev} when touched",
        Scorer.SHARP: f"Multiplies the multiplier by {amount:g}{dev} when touched. "
                      "Has a 1/4 chance to destroy its block when moving on from a run.",
        Scorer.PARTS: f"Gives {amount:g} component{_plural(amount)}{dev} when touched, "
                      "handed over once the run is continued",
        Scorer.SHREDS: f"Gives {points_text(resource_points_for(Scorer.SHREDS, amount))} "
                       f"shred point{_plural_points(resource_points_for(Scorer.SHREDS, amount))}"
                       f"{pdev}. 1 point converts into a random card",
        Scorer.RUBBLE: f"Gives {points_text(resource_points_for(Scorer.RUBBLE, amount))} "
                       f"rubble point{_plural_points(resource_points_for(Scorer.RUBBLE, amount))}"
                       f"{pdev}. 1 point converts into a random block",
        Scorer.IDEAS: f"Gives {points_text(resource_points_for(Scorer.IDEAS, amount))} "
                      f"idea point{_plural_points(resource_points_for(Scorer.IDEAS, amount))}"
                      f"{pdev}. 1 point converts into a random action",
        Scorer.RANDOM: "When touched, gives +35 chips, +5 mult, or +0.3 xMult at random.",
        Scorer.EFFECTIVE: f"Gives +{amount - 1:g} xMult{dev} when touched if its block "
                          "has 2 or more effects",
        Scorer.FRESH: f"Gives {amount:g} free reroll{_plural(amount)}{dev} when touched",
        Scorer.PICKY: f"Gives {points_text(resource_points_for(Scorer.PICKY, amount))} "
                      f"option point{_plural_points(resource_points_for(Scorer.PICKY, amount))}"
                      f"{pdev}. 1 point converts into a random shop slot",
        Scorer.VOYAGER: f"Gives +{amount:g} mult{dev} for each pixel the marble traveled before touching it",
        Scorer.SATANIC: f"Multiplies the multiplier by {amount:g}{dev} when touched, then is "
                        "permanently destroyed once a marble leaves it.",
        Scorer.SUMMIT: f"Gives +{amount:g} mult{dev} for each unit above the bottom row it is located on",
        Scorer.AIRBALL: f"Gives +{amount:g} mult{dev} for each second the marble was airborne (touching no block, including Shape.None) before touching it",
        Scorer.SEED: f"Gives +{amount:g} mult{dev} for each Seed block on the board when touched",
        Scorer.DRILL: f"When touched, drills out {amount:g} locked board square{_plural(amount)}"
                      f"{dev} next to unlocked ones — they unlock after the run",
        Scorer.LUCKY: "When touched, has a 1/3 chance to give 130 chips and a 1/9 chance to give $40 (both can land).",
        Scorer.ROOMY: f"Gives +{amount:g} chips{dev} for each unlocked board unit when touched",
        Scorer.RALLY: f"Gives +{amount:g} mult{dev} for each fresh block touch this run before it — re-touches count, its own touch doesn't",
        Scorer.ECHO: "Re-fires the scoring effect of the block the marble touched right before it.",
        Scorer.POWERLINE: f"Gives +{amount:g} chips{dev} for each block in its row (including itself)",
        Scorer.FRONTIER: f"Gives +{amount:g} mult{dev} for each locked board unit or outer board border orthogonally adjacent to it (up/down/left/right, not diagonally)",
        Scorer.GILDED: "Gives 1/6 of your current chips as mult when touched.",
        Scorer.BOMB: "When touched, unlocks every board unit within 1 cell (including diagonally) after a run, then destroys itself.",
        Scorer.CLUSTER: f"Gives +{amount:g} mult{dev} for each block adjacent to it (up/down/left/right, not diagonally)",
        Scorer.COLOSSUS: f"Gives +{amount:g} xMult{dev} for each pixel the marble's radius is above its "
                         "base size (8 px) when touched",
        Scorer.UNDERTAKER: f"Gives +{amount:g} mult{dev} for each block destroyed this run (a fragile block "
                           "breaking or a Satanic block dying) before touching it",
        Scorer.DEBT: f"Gives {amount:.0f} chips{dev} when touched, but the run then pays no interest "
                     "($1 for every $10 you hold is lost after the run).",
    }.get(scorer, "Unknown scorer.")


def card_description(card, amount=None):
    """A one-line description of a card's score effect.

    A match-group card whose scorer carries a rolled magnitude describes THAT
    magnitude, with the deviation right after it ("Gives +45 chips (+15) when
    the marble collides with a Pipe block"); a whole card, or a match-group card
    with no rolled magnitude, describes the catalogue entry it has always had.
    """
    if not amount:
        return Card.DESCRIPTIONS.get(card, "Unknown card.")
    meta = match_group_card_meta(card)
    if meta is None:
        return Card.DESCRIPTIONS.get(card, "Unknown card.")
    group, scorer = meta
    return f"{_match_group_description(group, scorer, amount)}."


class Component:
    """A purchasable building piece: a shape, an effect, a scorer, or a condition.

    ``value`` is the component's ID number (a ``Shape``, ``Effect``, ``Scorer``,
    or ``Condition`` constant).
    """
    SHAPE = "shape"
    EFFECT = "effect"
    SCORER = "scorer"
    # COMMENTED OUT with the conditions: the condition was the trigger half of
    # a split card. Cards now pair a match group with a scorer instead, and a
    # group is not a purchasable component (see the MATCH GROUPS section).
    # CONDITION = "condition"

    def __init__(self, kind, value, amount=0, price=0, name="", col=0, row=0):
        self.kind = kind
        self.value = value
        self.amount = amount
        self.price = price
        self.name = name
        self.col = col
        self.row = row

    @property
    def shape(self):
        return self.value if self.kind == self.SHAPE else Shape.RECT

    @property
    def effect(self):
        return self.value if self.kind == self.EFFECT else Effect.NONE

    @property
    def scorer(self):
        return self.value if self.kind == self.SCORER else Scorer.NONE

    @property
    def scorer_amount(self):
        return self.amount if self.kind == self.SCORER else 0

    @property
    def effect_magnitude(self):
        """An effect piece's own strength (0 for shapes, scorers, conditions).

        A piece that was never rolled (an old save, a piece built by hand
        without a magnitude) reads the effect's average rather than 0: no
        scaleable effect has a zero strength, so the sidebar can never report
        a zero-strength repulsor.
        """
        if self.kind != self.EFFECT:
            return 0
        return self.amount or Effect.MAGNITUDE.get(self.value, 0)

    @classmethod
    def shape_component(cls, value, price=None, name="", col=0, row=0):
        if price is None:
            price = COMPONENT_PRICES.get((cls.SHAPE, value), 0)
        return cls(cls.SHAPE, value, price=price, name=name or Shape.name(value), col=col, row=row)

    @classmethod
    def effect_component(cls, value, price=None, name="", col=0, row=0, magnitude=None):
        """An effect piece. ``magnitude`` is its own rolled strength, which the
        piece CARRIES (its payoff and its description) but never pays for: the
        piece costs the catalog price however strongly it rolled."""
        if price is None:
            price = effect_component_price(value)
        return cls(cls.EFFECT, value, amount=magnitude or 0, price=price,
                   name=name or Effect.name(value), col=col, row=row)

    @classmethod
    def scorer_component(cls, value, amount=0, price=None, name="", col=0, row=0):
        """A scorer piece. ``amount`` is its own rolled magnitude: it sets the
        piece's payoff, but never its price (see scorer_component_price)."""
        if price is None:
            price = scorer_component_price(value)
        return cls(cls.SCORER, value, amount=amount, price=price,
                   name=name or Scorer.name(value), col=col, row=row)

    # COMMENTED OUT with the conditions: the condition component (the trigger
    # half a player bought and paired with a scorer in the card builder).
    #
    # @classmethod
    # def condition_component(cls, value, price=None, name="", col=0, row=0):
    #     if price is None:
    #         price = COMPONENT_PRICES.get((cls.CONDITION, value), 0)
    #     return cls(cls.CONDITION, value, price=price, name=name or condition_name(value), col=col, row=row)


# Fixed price for every component type. A block's price is 90% of the sum of
# the prices of the components it is made from.
COMPONENT_PRICES = {
    # Every price below is already 20% lower than the original (rounded down).
    (Component.SHAPE, Shape.RECT): 6,
    (Component.SHAPE, Shape.SLOPE): 11,
    (Component.SHAPE, Shape.LINE): 12,
    (Component.SHAPE, Shape.NONE): 10,
    (Component.SHAPE, Shape.CIRCLE): 8,
    (Component.SHAPE, Shape.CURVED_SLOPE): 12,
    (Component.SHAPE, Shape.PIPE): 9,
    (Component.SHAPE, Shape.DRAIN): 10,
    (Component.SHAPE, Shape.PIPE_BEND): 12,
    (Component.SHAPE, Shape.CONVEX_SLOPE): 8,
    (Component.SHAPE, Shape.FLAT_LINE): 12,
    (Component.SHAPE, Shape.CURVED_SLOPE_LINE): 12,
    (Component.SHAPE, Shape.HALF_PIPE): 12,
    (Component.SHAPE, Shape.SPIKE): 10,
    (Component.SHAPE, Shape.PLATFORM): 8,
    (Component.SHAPE, Shape.CORNER): 9,
    (Component.SHAPE, Shape.PEG): 7,
    (Component.SHAPE, Shape.SAWTOOTH): 11,
    # COMMENTED OUT with the shape itself: (Component.SHAPE, Shape.CRADLE): 11,
    (Component.SHAPE, Shape.BUMP): 9,
    (Component.SHAPE, Shape.KEY): 8,
    (Component.SHAPE, Shape.LOCK): 10,
    (Component.EFFECT, Effect.NONE): 6,
    (Component.EFFECT, Effect.BOUNCY): 28,
    (Component.EFFECT, Effect.ACCELERATOR): 25,
    (Component.EFFECT, Effect.PISTON): 36,
    (Component.EFFECT, Effect.GRAVITY): 20,
    (Component.EFFECT, Effect.BLACK_HOLE): 23,
    (Component.EFFECT, Effect.PORTAL): 31,
    (Component.EFFECT, Effect.ROTATE): 16,
    (Component.EFFECT, Effect.SLIPPERY): 12,
    (Component.EFFECT, Effect.FRAGILE): 20,
    (Component.EFFECT, Effect.GROWING): 24,
    (Component.EFFECT, Effect.SHRINKING): 24,
    (Component.EFFECT, Effect.STICKY): 22,
    (Component.EFFECT, Effect.REPULSOR): 23,
    (Component.EFFECT, Effect.CONVEYOR): 20,
    (Component.EFFECT, Effect.ZIPPER): 22,
    (Component.EFFECT, Effect.PHASE): 26,
    (Component.EFFECT, Effect.SPLITTER): 124,
    (Component.SCORER, Scorer.NONE): 6,
    (Component.SCORER, Scorer.CHIPS_ADD): 12,
    (Component.SCORER, Scorer.MULT_ADD): 17,
    (Component.SCORER, Scorer.MULT_MUL): 25,
    # The run roles are real goods: the shop sells each as a plain Rect block,
    # so these prices set that block's price (75% of shape + effects + scorer)
    # and its rarity (weight = 1/price): a Start block costs $109 and a Finish
    # block $53, and the Start role is the rarer of the two.
    (Component.SCORER, Scorer.START): 140,
    (Component.SCORER, Scorer.FINISH): 65,
    (Component.SCORER, Scorer.QUICK): 16,
    (Component.SCORER, Scorer.CASH): 14,
    (Component.SCORER, Scorer.SHARP): 24,
    (Component.SCORER, Scorer.PARTS): 11,
    (Component.SCORER, Scorer.SHREDS): 16,
    (Component.SCORER, Scorer.RUBBLE): 12,
    (Component.SCORER, Scorer.IDEAS): 14,
    (Component.SCORER, Scorer.RANDOM): 20,
    (Component.SCORER, Scorer.EFFECTIVE): 27,
    (Component.SCORER, Scorer.FRESH): 14,
    (Component.SCORER, Scorer.PICKY): 17,
    (Component.SCORER, Scorer.VOYAGER): 24,
    (Component.SCORER, Scorer.SATANIC): 32,
    (Component.SCORER, Scorer.SUMMIT): 24,
    (Component.SCORER, Scorer.AIRBALL): 24,
    (Component.SCORER, Scorer.SEED): 22,
    (Component.SCORER, Scorer.DRILL): 24,
    (Component.SCORER, Scorer.LUCKY): 24,
    (Component.SCORER, Scorer.ROOMY): 24,
    (Component.SCORER, Scorer.RALLY): 24,
    (Component.SCORER, Scorer.ECHO): 34,
    (Component.SCORER, Scorer.POWERLINE): 22,
    (Component.SCORER, Scorer.FRONTIER): 22,
    (Component.SCORER, Scorer.GILDED): 30,
    (Component.SCORER, Scorer.BOMB): 30,
    (Component.SCORER, Scorer.CLUSTER): 24,
    (Component.SCORER, Scorer.COLOSSUS): 26,
    (Component.SCORER, Scorer.UNDERTAKER): 26,
    (Component.SCORER, Scorer.DEBT): 24,
    # COMMENTED OUT with the conditions: the condition component prices, which
    # were also the collision conditions' rarity axis. A match group is not a
    # component and is priced by match_group_price instead.
    # (Component.CONDITION, Condition.START): 14,
    # (Component.CONDITION, Condition.DISTANCE): 16,
    # (Component.CONDITION, Condition.BLACK_HOLE): 17,
    # (Component.CONDITION, Condition.AIR_TIME): 16,
    # (Component.CONDITION, Condition.FULLEST_COLUMN): 16,
    # (Component.CONDITION, Condition.CASH_HELD): 14,
    # (Component.CONDITION, Condition.FRAGILE_BREAKS): 17,
    # (Component.CONDITION, Condition.SLIPPERY): 16,
    # (Component.CONDITION, Condition.RANDOM): 12,
    # (Component.CONDITION, Condition.FEW_BLOCKS): 12,
    # (Component.CONDITION, Condition.COZY): 17,
    # (Component.CONDITION, Condition.PAINTING): 15,
    # (Component.CONDITION, Condition.SYNTHESIZER): 15,
    # (Component.CONDITION, Condition.ISLAND): 16,
}
# A shape/effect collision condition is priced INVERSELY to the shape/effect it
# matches: a condition about a cheap, common block (a plain Rect, an effect-less
# block) is pricey to find, while one about a rare, expensive component (a
# Splitter, a Portal) is cheap. The two ways to use a component therefore cost
# about the same overall — buy it as a component and build with it, or pay for
# the condition that rewards hitting it — and no condition is ever free. The
# pool keeps every condition in the same price band as the named conditions.
CONDITION_PRICE_POOL = 160
CONDITION_PRICE_FLOOR = 3


def _condition_price_for(component_price):
    """The price of a collision condition matching a component of this price.

    Inverse to the component: cheap components get expensive conditions, dear
    ones get cheap conditions (never below CONDITION_PRICE_FLOOR).
    """
    return max(CONDITION_PRICE_FLOOR,
               round(CONDITION_PRICE_POOL / max(component_price, 1)))


# COMMENTED OUT with the conditions: the two loops that priced every
# shape/effect collision condition from the component it matched (inverse to
# the component's price). That formula survives as _condition_price_for, which
# match_group_price still uses for the shape groups and effect groups.
#
# for _i, _s in enumerate(Shape.ORDER):
#     COMPONENT_PRICES[(Component.CONDITION, Condition.SHAPE_BASE + _i)] = \
#         _condition_price_for(COMPONENT_PRICES.get((Component.SHAPE, _s), 8))
# for _i, _e in enumerate(Effect.ORDER):
#     COMPONENT_PRICES[(Component.CONDITION, Condition.EFFECT_BASE + _i)] = \
#         _condition_price_for(COMPONENT_PRICES.get((Component.EFFECT, _e), 8))


def scorer_component_price(scorer):
    """A scorer piece's price. A rolled amount NEVER changes it.

    The price is the catalog row for that scorer at its AVERAGE magnitude, and
    it stays there however the piece rolled: a +Chips piece costs the same $12
    whether it rolled 6 chips or 54. So a good roll is a straight upgrade worth
    hunting for in the shop rather than a bigger bill (the same reason the
    rarity weights are built from this table — see main.component_weight). A
    scorer with no magnitude at all (Start, Lucky, ...) has nothing to roll and
    is priced by the table like everything else.
    """
    return COMPONENT_PRICES.get((Component.SCORER, scorer), 0)


def effect_component_price(effect):
    """An effect piece's price. A rolled strength NEVER changes it.

    Like a scorer: a piston that rolled 1800 px/s costs exactly what one at the
    1500 px/s average costs, so the roll is upside rather than a premium.
    """
    return COMPONENT_PRICES.get((Component.EFFECT, effect), 0)


def block_price_for(shape, effects, scorer):
    """A block's price is 75% of the sum of its parts' CATALOG prices.

    Deliberately blind to the rolled magnitudes: two blocks built from the same
    shape, effects and scorer cost the same whether the scorer rolled 6 chips
    or 54 and the piston 900 px/s or 1800, so buying is about WHICH parts to
    buy and the roll on the shelf is free upside (see scorer_component_price).
    A plain shape/scorer lookup still prices the bare block, and the free
    defaults (Rect shape, no effect, no scorer) add nothing.
    """
    total = (COMPONENT_PRICES.get((Component.SHAPE, shape), 0)
             + sum(effect_component_price(e) for e in effects)
             + scorer_component_price(scorer))
    return int(total * 0.75)


# --- Whole cards ---
# A card is either one of the indivisible cards in the Card class above (ERR
# 404 / Blueprint / Showman / Garden / Rigged Casino / Conquistador / ...) or a
# MATCH GROUP card (see the MATCH GROUPS section at the end of this file): a
# group of shapes, or one effect, paired with one scorer, fired when the marble
# collides with a block the group matches. Nothing splits and nothing is
# assembled any more — the condition system that did both is commented out
# below.

# ---------------------------------------------------------------------------
# COMMENTED OUT with the conditions (user request: "comment out all the code
# for conditions"): the condition constants, their shape/effect aliases, the
# catalogue order, and every helper that read a condition (its shape/effect
# payload, its name, glyph, colour, trigger prose, phase and block match).
# Kept verbatim inside the string literal so it can be restored by deleting the
# two wrapper lines; nothing in the game reads it.
# ---------------------------------------------------------------------------
_COMMENTED_OUT_CONDITIONS = r'''
# --- Conditions: the trigger half of split cards (see class Condition) ---
# Named-condition constants are in the class; collision conditions (one per
# shape and per effect) are generated here with ids in Condition.SHAPE_BASE..
# ranges. A shape/effect payload is recovered from a condition id by
# condition_shape / condition_effect.

# Convenience aliases, e.g. Condition.SHAPE_PIPE, Condition.EFFECT_BOUNCY.
for _i, _s in enumerate(Shape.ORDER):
    setattr(Condition, f"SHAPE_{Shape.name(_s).upper().replace(' ', '_')}",
            Condition.SHAPE_BASE + _i)
for _i, _e in enumerate(Effect.ORDER):
    setattr(Condition, f"EFFECT_{Effect.name(_e).upper().replace(' ', '_')}",
            Condition.EFFECT_BASE + _i)

# Every condition, in a stable order (named triggers, then shapes, then
# effects). Used by the collection and the shop's random condition offers.
CONDITION_ORDER = ([Condition.START, Condition.DISTANCE, Condition.BLACK_HOLE,
                    Condition.AIR_TIME, Condition.FULLEST_COLUMN,
                    Condition.CASH_HELD, Condition.FRAGILE_BREAKS,
                    Condition.SLIPPERY, Condition.RANDOM, Condition.FEW_BLOCKS,
                    Condition.COZY, Condition.PAINTING, Condition.SYNTHESIZER,
                    Condition.ISLAND]
                   + [Condition.SHAPE_BASE + _i for _i in range(len(Shape.ORDER))]
                   + [Condition.EFFECT_BASE + _i for _i in range(len(Effect.ORDER))])


def condition_shape(condition):
    """The shape a shape-collision condition triggers on, or None."""
    if Condition.SHAPE_BASE <= condition < Condition.EFFECT_BASE:
        index = condition - Condition.SHAPE_BASE
        if 0 <= index < len(Shape.ORDER):
            return Shape.ORDER[index]
    return None


def condition_effect(condition):
    """The effect an effect-collision condition triggers on, or None."""
    if condition >= Condition.EFFECT_BASE:
        index = condition - Condition.EFFECT_BASE
        if 0 <= index < len(Effect.ORDER):
            return Effect.ORDER[index]
    return None


def condition_name(condition):
    """A condition's short display name (its shape/effect for collision)."""
    shape = condition_shape(condition)
    if shape is not None:
        return Shape.name(shape)
    effect = condition_effect(condition)
    if effect is not None:
        return Effect.name(effect)
    return Condition.NAMES.get(condition, "Unknown")


def condition_glyph(condition):
    """A condition's center glyph (first letter of the shape/effect or a
    named symbol)."""
    shape = condition_shape(condition)
    if shape is not None:
        return Shape.name(shape)[0].upper()
    effect = condition_effect(condition)
    if effect is not None:
        return Effect.name(effect)[0].upper()
    return Condition.GLYPHS.get(condition, "?")


def condition_color(condition):
    """A condition's face color: every condition tile shares the same white
    face — the center icon (a mini shape/effect or a letter glyph) carries the
    condition's identity."""
    return WHITE


def condition_description(condition):
    """The trigger phrase describing when a condition fires.

    This is the MAGNITUDE phrasing: it names the measure a unit-scorer card
    scales by ("for each second the marble is in the air"), which is what such a
    card actually does. Use condition_flat_description for a flat card.
    """
    shape = condition_shape(condition)
    if shape is not None:
        return f"when the marble collides with a {Shape.name(shape)} block"
    effect = condition_effect(condition)
    if effect is not None:
        return f"when the marble collides with a {Effect.name(effect)} block"
    return Condition.TRIGGERS.get(condition, "Unknown condition.")


def condition_flat_description(condition):
    """The trigger phrase for a FLAT card: the gate, with no per-unit measure.

    A flat card pays one block-style trigger rather than scaling with the
    condition's measured units, so claiming "for each second the marble is in
    the air" or "scaled up to 4x base by the distance the marble travels" would
    be a lie; it says only what has to be true for the card to fire at all
    ("once the marble has been in the air"). Collision conditions read the same
    either way, and conditions that are already pure gates fall back to their
    shared trigger phrase.
    """
    shape = condition_shape(condition)
    if shape is not None:
        return f"when the marble collides with a {Shape.name(shape)} block"
    effect = condition_effect(condition)
    if effect is not None:
        return f"when the marble collides with a {Effect.name(effect)} block"
    if condition in Condition.FLAT_TRIGGERS:
        return Condition.FLAT_TRIGGERS[condition]
    return Condition.TRIGGERS.get(condition, "Unknown condition.")


def condition_phase(condition):
    """When a condition's card fires: 'start', 'end', 'fragile', or 'collision'.

    Collision conditions fire once per fresh marble collision with a matching
    block; start-phase conditions fire once at the start of a run; end-phase
    conditions fire once at the end; Fragile Breaks fires once per fragile
    block that shatters.
    """
    if condition_shape(condition) is not None or condition_effect(condition) is not None:
        return "collision"
    if condition in (Condition.START, Condition.FULLEST_COLUMN, Condition.CASH_HELD,
                     Condition.RANDOM, Condition.FEW_BLOCKS, Condition.COZY,
                     Condition.PAINTING, Condition.SYNTHESIZER, Condition.ISLAND):
        return "start"
    if condition in (Condition.DISTANCE, Condition.BLACK_HOLE,
                     Condition.AIR_TIME, Condition.SLIPPERY):
        return "end"
    return "fragile"  # Condition.FRAGILE_BREAKS


def condition_matches_block(condition, block):
    """True when a collision condition's card fires for the given block."""
    shape = condition_shape(condition)
    if shape is not None:
        return block.shape == shape
    effect = condition_effect(condition)
    if effect is not None:
        return effect in block.effects
    return False
'''
# --- end of the commented-out condition catalogue ----------------------------


# --- The card scorers a card can pay with (shared with block assembly) ------
# EVERY block payoff scorer is a card scorer: the three unit scorers (+Chips,
# +Mult, xMult) pay one standard unit per trigger, and every other scorer pays
# one block-style trigger. The only exclusions are NONE (no payoff at all) and
# START/FINISH (run roles, not payoffs — a card can't release or finish a
# marble).
#
# A card has no position, board context or marble of its own, so the payoffs
# that read one take them from the block that fired the card: the block the
# marble collided with (every card is collision-triggered now, see
# match_group_matches_block). That is what makes Powerline's row, Frontier's
# border, Cluster's neighbours, Echo's copied scorer, Bomb's blast and Colossus'
# marble expressible on a card.
_ROLE_OR_NONE = (Scorer.NONE, Scorer.START, Scorer.FINISH)
CARD_SCORERS = tuple(s for s in Scorer.ORDER if s not in _ROLE_OR_NONE)
# The flat scorers (everything that is not a unit scorer) build generic cards.
UNIT_CARD_SCORERS = (Scorer.CHIPS_ADD, Scorer.MULT_ADD, Scorer.MULT_MUL)
FLAT_CARD_SCORERS = tuple(s for s in CARD_SCORERS if s not in UNIT_CARD_SCORERS)
# The three unit scorers' display suffix for magnitude card names (a
# splittable card's face color is its scorer's own color, Scorer.color).
_UNIT_SCORER_META = {
    Scorer.CHIPS_ADD: "+Chips",
    Scorer.MULT_ADD: "+Mult",
    Scorer.MULT_MUL: "xMult",
}

# ---------------------------------------------------------------------------
# COMMENTED OUT with the conditions: the named-condition magnitude model (the
# ratio table that let one trigger pay every scorer proportionally). A match
# group's cards pay one standard unit per matching hit instead, so there is no
# ratio left to look up (see _match_group_description).
# ---------------------------------------------------------------------------
_COMMENTED_OUT_NAMED_CONDITION_RATIO = r'''
# --- Named-condition magnitude model ---
# A named condition fires once per run (or per fragile break) with a per-run
# measure in "units". The standard per-unit bases are +30 chips, +4 mult, and
# +0.25 xMult. Each condition is worth a fixed fraction of those bases (its
# "ratio"), so EVERY scorer stays proportional to the base: a condition with
# ratio 0.5 (Plane) gives +15 chips, +2 mult, and +0.125 xMult per unit — half
# of +30/+4/+0.25. The canonical (condition, scorer) pair reproduces the
# original card the condition is named after exactly; the ratio lets every
# OTHER scorer scale the same trigger.
NAMED_CONDITION_RATIO = {
    Condition.START: 1.0,
    Condition.DISTANCE: 1.0,
    Condition.BLACK_HOLE: 1.0,
    Condition.AIR_TIME: 0.5,
    Condition.FULLEST_COLUMN: 0.25,
    Condition.CASH_HELD: 1.0 / 30,
    Condition.FRAGILE_BREAKS: 0.75,
    Condition.SLIPPERY: 0.8,
    Condition.RANDOM: 1.0,
    Condition.FEW_BLOCKS: 4.0,
    Condition.COZY: 3.0,
    Condition.PAINTING: 0.1,
    # Synthesizer is 3/4 of the base per card owned, so the +Mult scorer pays
    # exactly +3 mult for each card in the card area (+chips pays 22, xMult
    # multiplies by 1.1875 per card).
    Condition.SYNTHESIZER: 0.75,
    # Island is 2x the base, so its canonical xMult pairing multiplies by 1.5
    # per island — "+0.5 xMult for each unconnected group of unlocked board
    # units" (+Chips pays 60 a group, +Mult 8). The count is of GROUPS, not
    # units, so it is the same 1 on the starter 2x3 board as on a board that
    # has been unlocked into one big continent: what it rewards is a board left
    # broken into separate islands.
    Condition.ISLAND: 2.0,
}
# The named conditions, in a stable display order (collision conditions follow
# them in CONDITION_ORDER).
NAMED_CONDITION_ORDER = [Condition.START, Condition.DISTANCE,
                         Condition.BLACK_HOLE, Condition.AIR_TIME,
                         Condition.FULLEST_COLUMN, Condition.CASH_HELD,
                         Condition.FRAGILE_BREAKS, Condition.SLIPPERY,
                         Condition.RANDOM, Condition.FEW_BLOCKS, Condition.COZY,
                         Condition.PAINTING, Condition.SYNTHESIZER,
                         Condition.ISLAND]


def condition_ratio(condition):
    """A condition's payoff fraction of the +30/+4/+0.25 bases.

    Collision conditions fire a standard unit per matching hit (ratio 1); a
    named condition's ratio scales every scorer so rewards stay proportional to
    the base (see NAMED_CONDITION_RATIO).
    """
    return NAMED_CONDITION_RATIO.get(condition, 1.0)
'''
# --- end of the commented-out named-condition model --------------------------


def magnitude_payoff(scorer, ratio, units, scale=1.0):
    """The payoff for (scorer x ratio x units): (chips_add, mult_add, factor).

    +Chips adds a whole number of chips (rounded half-up per unit, so Pillar
    gives +8/column and Wrecking Ball +23/break); +Mult adds a scaled amount;
    xMult MULTIPLIES the multiplier by 1 + 0.25*ratio*units — the +0.25 xMult
    per unit is an ADD, so it never compounds into repeated x1.25s.

    ``scale`` is the card's own scorer magnitude relative to the average (a
    card printed with a 45-chip +Chips half pays 1.5x the average payoff), so
    a composed card pays for the magnitude it carries.
    """
    if scorer == Scorer.CHIPS_ADD:
        per_unit = int(30 * scale * ratio + 0.5)
        return (round(per_unit * units), 0, 1.0)
    if scorer == Scorer.MULT_ADD:
        return (0, 4 * scale * ratio * units, 1.0)
    return (0, 0, 1 + 0.25 * scale * ratio * units)


def _format_amount(scorer, ratio, scale=1.0, dev=""):
    """A short per-unit payoff phrase for a unit scorer at a condition's ratio.

    e.g. (+Chips, 0.5) -> "+15 chips"; (xMult, 0.75) -> "x1.19 mult". ``scale``
    is the card's own scorer magnitude relative to the average, and ``dev`` the
    "(+2)" token that follows the magnitude.
    """
    if scorer == Scorer.CHIPS_ADD:
        n = int(30 * scale * ratio + 0.5)
        return f"+{n} chips{dev}" if n != 1 else f"+1 chip{dev}"
    if scorer == Scorer.MULT_ADD:
        n = 4 * scale * ratio
        s = f"{n:.3f}".rstrip("0").rstrip(".")
        return f"+{s} mult{dev}"
    factor = 1 + 0.25 * scale * ratio
    s = f"{factor:.3f}".rstrip("0").rstrip(".")
    return f"x{s} mult{dev}"


# ---------------------------------------------------------------------------
# COMMENTED OUT with the conditions: the magnitude-card catalogue (the ids for
# every (condition x unit scorer) card) and the prose helper that named the
# block a condition handed the card. A match-group card names the collided
# block instead — see COLLISION_REFERENCE and _match_group_description.
# ---------------------------------------------------------------------------
_COMMENTED_OUT_MAGNITUDE_CARDS = r'''
# --- Magnitude cards ---
# Every condition (the named triggers and the collision conditions) pairs with
# every unit scorer to build a "magnitude" card: the scorer's base (+30 chips /
# +4 mult / +0.25 xMult) scaled by the condition's ratio and unit count (see
# NAMED_CONDITION_RATIO / magnitude_payoff). Collision conditions fire one unit
# per matching hit (ratio 1); named conditions fire once at their phase. These
# ids sit far past every whole card and are not in Card.ORDER — they are
# composed (built by the player or offered pre-built), never a fixed catalog
# entry. Each card's runtime is derived from its (trigger, scorer, condition)
# in cards.py.
#
# A composed card ALSO carries its scorer half's own magnitude (a +Chips half
# rolled to 45 pays 45 chips per unit instead of 30), so the text below is
# generated per card from that magnitude: the catalog entries are simply the
# average-magnitude text (amount None), and _card_payoff_text regenerates them
# for a card that rolled something else.
CONDITION_CARD_OFFSET = 1000
_NEW_COMBO_CARDS = {}    # (condition, scorer) -> card id
# value -> (trigger, scorer, condition); trigger is start/end/fragile/collision
_NEW_COMBO_META = {}


def _reference_block_phrase(condition):
    """The block a card's payoff refers to, in prose.

    A card has no position of its own, so every block-relative payoff reads
    "the block the condition hands the card": the block the marble collided
    with (collision conditions), the run's first block (start conditions), the
    run's last block (end conditions), or the block that shattered (Fragile
    Breaks). See cards.py for the runtime half of the same rule.
    """
    phase = condition_phase(condition)
    if phase == "collision":
        return "the collided block"
    if phase == "start":
        return "the first block the marble hits this run"
    if phase == "end":
        return "the last block the marble hits this run"
    return "the shattered block"
'''
# --- end of the commented-out magnitude-card catalogue -----------------------


def _generic_effect_phrase(scorer, amount=None, dev="", block_phrase=None):
    """A flat scorer card's short payoff phrase, at its own magnitude.

    The phrases are the average-magnitude text; a card carrying a rolled
    magnitude substitutes its own amount ("$22" for a Cash half rolled up from
    $15), so the description always matches what the card actually pays, with
    ``dev`` (the "(+2)" token) right after it. A block-relative scorer names
    ``block_phrase`` in its text — a match-group card passes
    COLLISION_REFERENCE, because it fires on the block the marble collided with
    — and falls back to "its block" when the caller names none. The
    fixed-payoff scorers (Quick, Random, Echo, Gilded, Lucky) have no amount and
    keep their catalog phrase.
    """
    if not amount:
        amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    # A resource-point phrase states the deviation of the POINT count it shows
    # (see resource_points_deviation), and states one only when the caller
    # supplied a magnitude — which is exactly what a non-empty dev means (see
    # _card_payoff_text).
    pdev = resource_points_deviation(scorer, amount) if dev else ""
    block = block_phrase or "its block"
    if scorer == Scorer.CASH:
        return f"${int(amount)}{dev}"
    if scorer == Scorer.SHARP:
        return f"{amount:g}x mult{dev}"
    if scorer == Scorer.PARTS:
        return (f"{amount:g} component{_plural(amount)}{dev} handed over once "
                "the run is continued")
    if scorer == Scorer.SHREDS:
        return (f"{points_text(resource_points_for(Scorer.SHREDS, amount))} shred "
                f"point{_plural_points(resource_points_for(Scorer.SHREDS, amount))}{pdev}")
    if scorer == Scorer.RUBBLE:
        return (f"{points_text(resource_points_for(Scorer.RUBBLE, amount))} rubble "
                f"point{_plural_points(resource_points_for(Scorer.RUBBLE, amount))}{pdev}")
    if scorer == Scorer.IDEAS:
        return (f"{points_text(resource_points_for(Scorer.IDEAS, amount))} idea "
                f"point{_plural_points(resource_points_for(Scorer.IDEAS, amount))}{pdev}")
    if scorer == Scorer.PICKY:
        return (f"{points_text(resource_points_for(Scorer.PICKY, amount))} option "
                f"point{_plural_points(resource_points_for(Scorer.PICKY, amount))}{pdev}")
    if scorer == Scorer.FRESH:
        return f"{amount:g} free reroll{_plural(amount)}{dev}"
    if scorer == Scorer.SATANIC:
        return f"x{amount:g} mult{dev}"
    if scorer == Scorer.SUMMIT:
        return f"{amount:g} mult{dev} for each row above the bottom row"
    if scorer == Scorer.AIRBALL:
        return f"{amount:g} mult{dev} for each second airborne before the touch"
    if scorer == Scorer.EFFECTIVE:
        return (f"+{amount - 1:g} xMult{dev} when {block} has 2 or more "
                "effects")
    # The board/run/marble scorers, which a card pays from the same state a
    # block does (see cards.py).
    if scorer == Scorer.SEED:
        return f"{amount:g} mult{dev} for each Seed block on the board"
    if scorer == Scorer.ROOMY:
        return f"{amount:g} chips{dev} for each unlocked board unit"
    if scorer == Scorer.RALLY:
        return f"{amount:g} mult{dev} for each fresh block touch this run before it"
    if scorer == Scorer.VOYAGER:
        return (f"{amount:g} mult{dev} for each pixel the run's marbles have "
                "traveled so far")
    if scorer == Scorer.DRILL:
        return (f"{amount:g} locked board square{_plural(amount)}{dev} unlocked "
                "after the run")
    if scorer == Scorer.UNDERTAKER:
        return f"{amount:g} mult{dev} for each block destroyed this run"
    if scorer == Scorer.DEBT:
        return (f"{amount:.0f} chips{dev}, and the run then pays no interest "
                "afterwards")
    if scorer == Scorer.POWERLINE:
        return f"{amount:g} chips{dev} for each block in the same row as {block}"
    if scorer == Scorer.FRONTIER:
        return (f"{amount:g} mult{dev} for each locked unit or board border "
                f"next to {block}")
    if scorer == Scorer.CLUSTER:
        return f"{amount:g} mult{dev} for each block adjacent to {block}"
    if scorer == Scorer.COLOSSUS:
        return (f"{amount:g} xMult{dev} for each pixel the marble's radius is "
                "above its base size (8 px)")
    # COMMENTED OUT with the conditions: an end-phase Quick card measured the
    # run's LAST block, because there is no next block after a run. Every card
    # is collision-triggered now, so Quick always means "the next block hit"
    # (see _GENERIC_SCORER_EFFECT).
    # if scorer == Scorer.QUICK and condition_phase(condition) == "end":
    #     return f"chips from the speed of the last block hit{dev}"
    if scorer == Scorer.BOMB:
        return (f"a bomb on {block}, unlocking the units around it after a run")
    return _GENERIC_SCORER_EFFECT.get(scorer, "")


def _trigger_suffix(trigger):
    """The separator plus trigger clause that ends a flat card's description.

    A "when …" / "each time …" trigger reads as part of the sentence ("Gives 25
    chips for each block in the same row as the collided block when the marble
    collides with a Pipe block"), while a time adverbial needs its own comma
    ("… in the same row as the first block the marble hits this run, at the
    start of the run, if the board has any blocks").
    """
    if trigger.startswith(("at the ", "once ")):
        return f", {trigger}"
    return f" {trigger}"


# ---------------------------------------------------------------------------
# COMMENTED OUT with the conditions: the composed-card text builder and the
# loop that catalogued every (condition x unit scorer) pair as a card. A
# match-group card's text comes from _match_group_description instead.
# ---------------------------------------------------------------------------
_COMMENTED_OUT_CARD_PAYOFF_TEXT = r'''
def _card_payoff_text(condition, scorer, amount=None):
    """The body text of a composed card's description, at its own magnitude.

    A unit scorer (a magnitude card) scales per unit, so its text keeps the
    condition's MAGNITUDE phrasing ("for each second the marble is in the
    air"); every flat scorer pays one block-style trigger instead and reads the
    condition's gate (see condition_flat_description).
    """
    dev = scorer_magnitude_deviation(scorer, amount) if amount else ""
    if scorer in UNIT_CARD_SCORERS:
        scale = scorer_magnitude_scale(scorer, amount)
        return (f"Gives {_format_amount(scorer, condition_ratio(condition), scale, dev)} "
                f"{condition_description(condition)}")
    if scorer == Scorer.SUMMIT:
        return _summit_card_description(condition, amount, dev)
    if scorer == Scorer.SATANIC:
        return _satanic_card_description(condition, amount, dev)
    if scorer == Scorer.BOMB:
        return _bomb_card_description(condition, amount, dev)
    return (f"Gives {_generic_effect_phrase(scorer, amount, dev, condition)}"
            f"{_trigger_suffix(condition_flat_description(condition))}")


_MI = 0
for _cond in CONDITION_ORDER:
    for _scorer in UNIT_CARD_SCORERS:
        _value = CONDITION_CARD_OFFSET + _MI
        _MI += 1
        _NEW_COMBO_CARDS[(_cond, _scorer)] = _value
        _NEW_COMBO_META[_value] = (condition_phase(_cond), _scorer, _cond)
        _suffix = _UNIT_SCORER_META[_scorer]
        _name = f"{condition_name(_cond)} {_suffix}"
        Card.NAMES[_value] = _name
        Card.COMMENTS[_value] = "Assembled or found pre-built."
        Card.DESCRIPTIONS[_value] = _card_payoff_text(_cond, _scorer)
        Card.PRICES[_value] = (COMPONENT_PRICES.get((Component.CONDITION, _cond), 20)
                               + COMPONENT_PRICES.get((Component.SCORER, _scorer), 20))
        # A splittable card's face is its scorer's color and its icon is its
        # condition's (rendered by ui._draw_card_icon).
        Card.COLORS[_value] = Scorer.color(_scorer)
        Card.GLYPHS[_value] = condition_glyph(_cond)
'''
# --- end of the commented-out magnitude-card catalogue -----------------------


# --- Generic flat-scorer cards ---
# Every other block scorer (Cash, Sharp, Quick, Parts/Shreds/Rubble/Ideas) is a
# card scorer too, and each pairs with every match group to build a card (see
# the MATCH GROUPS section at the end of this file) — one block-style trigger
# per matching collision.
#
# COMMENTED OUT with the conditions: the generic-card id range and the two maps
# that recorded which (condition, scorer) pair each generic card stood for.
# GENERIC_CARD_OFFSET = 2000
# _GENERIC_CARD_CARDS = {}   # (condition, scorer) -> card id
# _GENERIC_CARD_META = {}    # card id -> (condition, scorer)
# A short phrase for each flat scorer's payoff, used in card descriptions for
# the scorers whose payoff is fixed (no magnitude): Quick, Random, Echo,
# Gilded, Bomb, Lucky. Everything with an amount builds its phrase in
# _generic_effect_phrase instead.
_GENERIC_SCORER_EFFECT = {
    Scorer.QUICK: "chips from the speed of the next block hit",
    Scorer.RANDOM: "+35 chips, +5 mult, or +0.3 xMult at random",
    Scorer.ECHO: "another trigger of the same block's own scorer",
    Scorer.GILDED: "1/6 of your current chips as mult",
    Scorer.BOMB: "a bomb on that block, unlocking the units around it after a run",
    Scorer.LUCKY: "a 1/3 chance of 130 chips and a 1/9 chance of $40",
}

# ---------------------------------------------------------------------------
# COMMENTED OUT with the conditions: the three condition-specific card texts
# (Summit naming the block a condition handed it, Satanic and Bomb describing
# their one-run deal) and the loop that catalogued every (condition x flat
# scorer) pair. _match_group_description writes the same three texts for a
# match-group card.
# ---------------------------------------------------------------------------
_COMMENTED_OUT_GENERIC_CARD_TEXT = r'''
def _summit_card_description(condition, amount=None, dev=""):
    """A generic Summit card's description: mult per row above the bottom.

    Summit cards add their own amount (0.75 mult at the average) for each row
    above the bottom row of the block the card's condition hands them — the
    block the marble collided with (a collision card), the run's first block
    (a start card), the run's last block (an end card), or the block that
    shattered (Fragile Breaks). A block on the bottom row grants nothing.
    """
    if not amount:
        amount = Scorer.DEFAULT_AMOUNT.get(Scorer.SUMMIT, 0.75)
    # Summit is a flat scorer, so the card states the condition's gate only.
    trigger = condition_flat_description(condition)
    phase = condition_phase(condition)
    if phase == "collision":
        measured = "that the collided block sits on"
    elif phase == "start":
        measured = "that the first block the marble hits this run sits on"
    elif phase == "end":
        measured = "that the last block the marble hits this run sits on"
    else:  # Condition.FRAGILE_BREAKS
        measured = "that the shattered block sat on"
    return (f"Gives {amount:g} mult{dev} for each row above the bottom row "
            f"{measured}, {trigger}")


def _satanic_card_description(condition, amount=None, dev=""):
    """A generic Satanic card's description: xMult, then destroyed.

    A Satanic card multiplies the multiplier by its own amount (6.66 at the
    average) when its condition fires, then is permanently destroyed after one
    run — however many times it fired in that run (only a retry keeps it).
    """
    return (f"Gives {_generic_effect_phrase(Scorer.SATANIC, amount, dev)}"
            f"{_trigger_suffix(condition_flat_description(condition))}, then is "
            "permanently destroyed after one run")


def _bomb_card_description(condition, amount=None, dev=""):
    """A generic Bomb card's description: primes a bomb, then is destroyed.

    A Bomb card plants a bomb on the cell of the block its condition hands it
    (the collided, first, last or shattered block), so the units around that
    block unlock after the run — exactly like a Bomb block. The card itself is
    permanently destroyed after that run (only a retry keeps it).
    """
    return (f"Gives {_generic_effect_phrase(Scorer.BOMB, amount, dev, condition)}"
            f"{_trigger_suffix(condition_flat_description(condition))}, then is "
            "permanently destroyed after one run")


_gi = 0
for _scorer in FLAT_CARD_SCORERS:
    for _cond in CONDITION_ORDER:
        _value = GENERIC_CARD_OFFSET + _gi
        _gi += 1
        _GENERIC_CARD_CARDS[(_cond, _scorer)] = _value
        _GENERIC_CARD_META[_value] = (_cond, _scorer)
        Card.NAMES[_value] = f"{condition_name(_cond)} card ({Scorer.name(_scorer)})"
        Card.COMMENTS[_value] = "Assembled or found pre-built."
        if _scorer == Scorer.SUMMIT:
            # A Summit card measures the row of the block its condition hands
            # it, so its description names that block (see
            # _summit_card_description).
            Card.DESCRIPTIONS[_value] = _summit_card_description(_cond)
        elif _scorer == Scorer.SATANIC:
            # A Satanic card is a one-run deal: it is destroyed after a run, so
            # its description says so (see _satanic_card_description).
            Card.DESCRIPTIONS[_value] = _satanic_card_description(_cond)
        elif _scorer == Scorer.BOMB:
            # A Bomb card primes a bomb on its reference block's cell and is
            # then destroyed with it (see _bomb_card_description).
            Card.DESCRIPTIONS[_value] = _bomb_card_description(_cond)
        else:
            Card.DESCRIPTIONS[_value] = _card_payoff_text(_cond, _scorer)
        _cond_price = COMPONENT_PRICES.get((Component.CONDITION, _cond), 20)
        _scorer_price = COMPONENT_PRICES.get((Component.SCORER, _scorer), 20)
        Card.PRICES[_value] = _cond_price + _scorer_price
        # Face = the scorer's color, icon = the condition's (see ui.py).
        Card.COLORS[_value] = Scorer.color(_scorer)
        Card.GLYPHS[_value] = condition_glyph(_cond)
'''
# --- end of the commented-out generic-card catalogue -------------------------


# ---------------------------------------------------------------------------
# COMMENTED OUT with the conditions: the condition card lookups (the pair to
# card id mapping, its reverse, and the "is this card splittable" tests) plus
# the old card_scorer / card_price_for, which read the scorer and the condition
# out of a card's condition half. Every card is unsplittable now, and a
# match-group card's scorer and price come from _MATCH_GROUP_META and
# Card.PRICES: see the MATCH GROUPS section below.
# ---------------------------------------------------------------------------
_COMMENTED_OUT_CONDITION_CARD_LOOKUPS = r'''
def condition_scorer_card(condition, scorer):
    """The card id produced by building (condition, scorer), or None if the
    pair does not describe a card.

    Every condition (named trigger or collision) pairs with every card scorer:
    a unit scorer builds a magnitude card scaled by the condition's ratio and
    units (e.g. Pipe + +Mult -> a "Pipe +Mult" card that adds +4 mult per Pipe
    hit; Start + +Mult -> a "Joker +Mult" card that adds +4 mult at the start),
    and a flat scorer builds a generic card. The only exclusions are the run
    roles: Start and Finish release and finish the marble rather than paying
    anything, and there is no such thing as a card worth zero.
    """
    value = _NEW_COMBO_CARDS.get((condition, scorer))
    if value is not None:
        return value
    return _GENERIC_CARD_CARDS.get((condition, scorer))


def condition_card_meta(value):
    """(trigger, scorer, condition) for a magnitude card, or None for the whole
    cards / generic cards (whose effects live in cards.py)."""
    return _NEW_COMBO_META.get(value)


def generic_card_meta(value):
    """(condition, scorer) for a generic flat-scorer card, or None for whole
    /magnitude cards (whose effects live in cards.py)."""
    return _GENERIC_CARD_META.get(value)


def is_splittable_card(value):
    """True when a card can be rebuilt from a condition + scorer (any card
    except the indivisible whole cards, the Card.ORDER catalog)."""
    return value not in Card.ORDER


def splittable_card_condition_scorer(value):
    """The (condition, scorer) a splittable card splits into, or None.

    Reverses condition_scorer_card: every composed card (a magnitude card or a
    generic flat-scorer card) has exactly one (condition, scorer)
    decomposition. Only the indivisible whole cards (the Card.ORDER catalog)
    return None.
    """
    if value in Card.ORDER:
        return None
    meta = _NEW_COMBO_META.get(value)
    if meta is not None:
        _trigger, scorer, condition = meta
        return (condition, scorer)
    gmeta = _GENERIC_CARD_META.get(value)
    if gmeta is not None:
        return gmeta
    return None


def card_scorer(value):
    """The scorer half of a composed card, or None for a whole card.

    Composed cards (magnitude cards and generic flat-scorer cards) carry their
    scorer's own magnitude and pay/price/describe themselves with it; the
    indivisible whole cards (Coupon, Showman, Garden, ...) have no scorer half
    at all, so there is nothing to roll and nothing to scale.
    """
    parts = splittable_card_condition_scorer(value)
    return parts[1] if parts is not None else None


def card_price_for(card):
    """A composed card's price: its condition's plus its scorer half's.

    The scorer half's rolled magnitude is NOT part of the price, exactly as it
    is not for a bought scorer piece or a block: a +Chips card costs what it
    costs however well that half rolled (see scorer_component_price). A whole
    card, and a card whose scorer half has no magnitude (Lucky, Quick, ...),
    keeps its catalog price.
    """
    base = Card.PRICES.get(card, 20)
    parts = splittable_card_condition_scorer(card)
    if parts is None:
        return base
    condition, scorer = parts
    return max(1, COMPONENT_PRICES.get((Component.CONDITION, condition), 0)
               + scorer_component_price(scorer))
'''
# --- end of the commented-out condition card lookups -------------------------


# =============================================================================
# MATCH GROUPS: the collision a card triggers on
# =============================================================================
# (User request: "create an unsplittable card for each combination of (a group
# of shapes plus each effect that is not the none effect) and all scorers ...
# for each combination, the card makes all blocks that have a shape in the
# given group, or have the given effect, act as if the block also has the given
# scorer. do not give the block a scorer, only trigger the scorer when the
# marble collides with the block. the rarity of these cards should be based
# only on the shape group or effect.")
#
# A MATCH GROUP is either a group of SHAPES — colliding with a block of any
# shape in it fires the card — or one EFFECT — colliding with any block that
# carries it fires the card. Every (group x card scorer) pair is ONE
# UNSPlITTABLE card: there is nothing to split it into, and nothing to combine,
# because the group and the scorer are baked in. A card never changes a block:
# it only fires its scorer when the marble collides with a block the group
# matches, so a block's own scorer (or lack of one) is untouched.
#
# Rect is deliberately in no group (a plain rect wall with no effects is the
# game's inert block) and so is Effect.NONE, so such a block matches nothing at
# all. The nine shape groups cover every other shape — the commented-out cradle
# is in none of them. NONE is a group of its own, for blocks built with the
# no-hitbox Shape.NONE field: the marble passes straight THROUGH such a block,
# but physics still registers a field contact for as long as the marble is
# inside its cell (see physics._collect_field_contacts), so these cards fire on
# a pass-through exactly as every other group's cards fire on a hit.
#
# Every card built here is COMMON (see Rarity and Card.RARITIES): the tier of a
# match-group card belongs to the group, and all 26 groups are common — the
# tiers above Common are the whole cards. Since the shop draws the TIER first
# (Common weighs 1 against a Legendary's 0.2 — see Rarity.WEIGHTS) and the card
# inside it flat, all 26 groups share the ONE Common slice of the offers along
# with the 3 cheap whole cards, instead of each group adding its own.
SHAPE_GROUPS = (
    (Shape.PIPE, Shape.DRAIN, Shape.PIPE_BEND),
    (Shape.PLATFORM, Shape.CORNER),
    (Shape.KEY, Shape.LOCK),
    (Shape.BUMP, Shape.CIRCLE),
    (Shape.CURVED_SLOPE, Shape.CONVEX_SLOPE),
    (Shape.PEG, Shape.SPIKE, Shape.SAWTOOTH),
    (Shape.SLOPE, Shape.LINE),
    (Shape.NONE,),
    (Shape.FLAT_LINE, Shape.CURVED_SLOPE_LINE, Shape.HALF_PIPE),
)
# Every group, as (kind, values): "shape" carries a tuple of shapes, "effect" a
# one-effect tuple. The ORDER here is the display order (the collection, and the
# shop's card offers, which draw one entry of this list at random).
MATCH_GROUPS = (tuple(("shape", _group) for _group in SHAPE_GROUPS)
                + tuple(("effect", (_effect,)) for _effect in Effect.REAL_ORDER))
# A card's text says which block its payoff reads. Every card is triggered by a
# collision, so it is always the block that was hit.
COLLISION_REFERENCE = "the collided block"


def match_group_label(group):
    """A match group's short display name (used in card names and the codex)."""
    kind, values = group
    if kind == "effect":
        return Effect.name(values[0])
    if values == (Shape.NONE,):
        return "No Shape"
    return "/".join(Shape.name(shape) for shape in values)


def match_group_trigger(group):
    """The "when the marble collides with ..." clause a card's text ends with."""
    kind, values = group
    if kind == "effect":
        return f"when the marble collides with a {Effect.name(values[0])} block"
    if values == (Shape.NONE,):
        return "when the marble collides with a block with no shape"
    names = [Shape.name(shape) for shape in values]
    if len(names) == 1:
        return f"when the marble collides with a {names[0]} block"
    return (f"when the marble collides with a {', '.join(names[:-1])} "
            f"or {names[-1]} block")


def match_group_glyph(group):
    """A match group's fallback letter (its icon art is the real marker)."""
    label = match_group_label(group)
    return label[0].upper() if label else "?"


def match_group_for_shape(shape):
    """The shape group that contains ``shape``, or None.

    Rect is in no group at all, so a plain rect wall returns None; every other
    shape (the commented-out cradle excepted) is in exactly one group.
    """
    for group in MATCH_GROUPS:
        if group[0] == "shape" and shape in group[1]:
            return group
    return None


def match_group_for_effect(effect):
    """The effect group for ``effect``, or None (Effect.NONE has no group)."""
    for group in MATCH_GROUPS:
        if group[0] == "effect" and group[1] == (effect,):
            return group
    return None


def match_group_matches_block(group, block):
    """True when the collided block is one this group's cards trigger on.

    A shape group matches the block's SHAPE; an effect group matches any of the
    block's EFFECTS (a block with two effects is matched by both effect groups).
    """
    kind, values = group
    if kind == "effect":
        return any(effect in block.effects for effect in values)
    return block.shape in values


def match_group_price(group):
    """A match group's price — the group half of its cards' price.

    Priced inversely to what it matches, exactly as the collision conditions
    were (see _condition_price_for): a group of cheap, common shapes is a dear
    card, while a rare component's effect is cheap. A shape group is priced off
    its CHEAPEST member, so the commonest shape in the group decides the
    price. The card's rarity does not read this: every group is Common, so they
    all carry one and the same weight in the offer pool (see
    main.random_card_option_value).
    """
    kind, values = group
    if kind == "effect":
        component_price = COMPONENT_PRICES.get((Component.EFFECT, values[0]), 8)
    else:
        component_price = min(COMPONENT_PRICES.get((Component.SHAPE, shape), 8)
                              for shape in values)
    return _condition_price_for(component_price)


def _match_group_description(group, scorer, amount=None):
    """The description text for one (match group x scorer) card.

    Built from the same phrase helpers every other card uses, so a Cash card
    states its own rolled dollars, a Summit card names the row the collided
    block sits on, and so on; the trigger clause is the group's (see
    match_group_trigger).
    """
    dev = scorer_magnitude_deviation(scorer, amount) if amount else ""
    trigger = match_group_trigger(group)
    if scorer in UNIT_CARD_SCORERS:
        # A unit scorer pays ONE standard unit per matching hit: +chips /
        # +mult / xMult, scaled by the card's own rolled magnitude.
        scale = scorer_magnitude_scale(scorer, amount)
        return f"Gives {_format_amount(scorer, 1.0, scale, dev)} {trigger}"
    if scorer == Scorer.SUMMIT:
        # Summit measures the row the collided block sits on.
        gain = amount or Scorer.DEFAULT_AMOUNT.get(Scorer.SUMMIT, 0.75)
        return (f"Gives {gain:g} mult{dev} for each row above the bottom row "
                f"that {COLLISION_REFERENCE} sits on, {trigger}")
    if scorer == Scorer.SATANIC:
        return (f"Gives {_generic_effect_phrase(scorer, amount, dev)}"
                f"{_trigger_suffix(trigger)}, then is permanently destroyed "
                "after one run")
    if scorer == Scorer.BOMB:
        return (f"Gives {_generic_effect_phrase(scorer, amount, dev, COLLISION_REFERENCE)}"
                f"{_trigger_suffix(trigger)}, then is permanently destroyed "
                "after one run")
    return (f"Gives {_generic_effect_phrase(scorer, amount, dev, COLLISION_REFERENCE)}"
            f"{_trigger_suffix(trigger)}")


# The card ids for (match group x scorer). Like the old composed-card ids these
# sit far past every whole card, so they can never collide with a Card.ORDER id,
# and they are NOT in Card.ORDER: Card.ORDER stays the catalogue of the cards
# that are not built on a match group (Coupon, Showman, Tesseract, ...), which
# is the "original cards" pool the shop draws from alongside the groups.
MATCH_GROUP_CARD_OFFSET = 3000
_MATCH_GROUP_CARDS = {}   # (group, scorer) -> card id
_MATCH_GROUP_META = {}    # card id -> (group, scorer)

for _group in MATCH_GROUPS:
    for _scorer in CARD_SCORERS:
        _value = (MATCH_GROUP_CARD_OFFSET + MATCH_GROUPS.index(_group) * len(CARD_SCORERS)
                  + CARD_SCORERS.index(_scorer))
        _MATCH_GROUP_CARDS[(_group, _scorer)] = _value
        _MATCH_GROUP_META[_value] = (_group, _scorer)
        Card.NAMES[_value] = f"{match_group_label(_group)} card ({Scorer.name(_scorer)})"
        Card.COMMENTS[_value] = ("Bound to the effect it matches."
                                 if _group[0] == "effect"
                                 else "Bound to the shapes it matches.")
        Card.DESCRIPTIONS[_value] = _match_group_description(_group, _scorer)
        Card.PRICES[_value] = match_group_price(_group) + scorer_component_price(_scorer)
        # The face is its scorer's colour and the icon is its group's (see
        # ui._draw_card_icon), exactly as a composed card used to be drawn.
        Card.COLORS[_value] = Scorer.color(_scorer)
        Card.GLYPHS[_value] = match_group_glyph(_group)
        # Every match-group card is Common: the tier belongs to the GROUP the
        # card is built on, and the design puts all of them in the common tier.
        Card.RARITIES[_value] = Rarity.COMMON


def match_group_card(group, scorer):
    """The card id for (match group, scorer), or None when there is no card."""
    return _MATCH_GROUP_CARDS.get((group, scorer))


def match_group_card_meta(value):
    """(group, scorer) for a card built on a match group, or None.

    None means the card is not collision-triggered at all: it is one of the
    Card.ORDER cards, whose effect lives in cards.py or in the code that owns
    the mechanic (Tesseract's reroll bonus, Coupon's discount, ...).
    """
    return _MATCH_GROUP_META.get(value)


def match_group_card_values():
    """Every match-group card id, in catalogue order."""
    return list(_MATCH_GROUP_META)


def card_scorer(value):
    """The scorer a card pays with, or None for a card that has no scorer.

    A match-group card carries its scorer's own rolled magnitude, which is why
    the shop rolls one when it builds the offer (see main.make_card_item): the
    card pays, prices and describes itself at the strength it actually has. The
    Card.ORDER cards (Coupon, Showman, Garden, ...) have no scorer at all, so
    there is nothing to roll and nothing to scale.
    """
    meta = match_group_card_meta(value)
    return meta[1] if meta is not None else None


def card_price_for(card):
    """A card's price: its catalog price, which is all it has.

    A match-group card's price is its group's plus its scorer half's, and a
    Card.ORDER card's is its own; both are written into Card.PRICES when the
    catalogue is built, so there is nothing left to compute here. A rolled
    magnitude never changes a price (see scorer_component_price).
    """
    return Card.PRICES.get(card, 20)

