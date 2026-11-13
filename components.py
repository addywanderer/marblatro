"""Component definitions and metadata for Marblatro.

This module is the single source of truth for what a component is and how it
is described and priced:

- The ``Shape``, ``Effect``, and ``Scorer`` enums. Each component is
  identified by an integer ID — the class constant itself (e.g.
  ``Shape.PIPE == 6``, ``Effect.ROTATE == 7``, ``Scorer.CHIPS_ADD == 1``).
- Each component's display name (``*.NAMES``).
- Each scorer's color (``Scorer.COLORS``).
- Every effect, scorer and card magnitude, in one place: the ``MAGNITUDES``
  section (which binds ``Effect.MAGNITUDE`` and ``Scorer.DEFAULT_AMOUNT``).
- The one-line descriptions (``shape_description`` / ``effect_description`` /
  ``scorer_description``).
- The ``Component`` purchase piece (kind, value/id, amount, price, name).
- The fixed price table (``COMPONENT_PRICES``) and block pricing
  (``block_price_for``).

Game logic (``Block``, ``Marble``, the shop, the toolbox, etc.) lives in
``main.py`` and imports these names from here.
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
    GONDOLA = 18  # slides up/down or left/right along its arrow, turning back at walls
    WASTEFUL = 19  # usable in the build phase: throw this block and one other item away, draw one

    NAMES: ClassVar[dict[int, str]] = {NONE: "None", BOUNCY: "Bouncy", ACCELERATOR: "Accelerator", \
                                       PISTON: "Piston", GRAVITY: "Gravity", BLACK_HOLE: "Black Hole", \
                                       PORTAL: "Portal", ROTATE: "Rotate", SLIPPERY: "Slippery", \
                                       FRAGILE: "Fragile", GROWING: "Growing", SHRINKING: "Shrinking", \
                                       STICKY: "Sticky", REPULSOR: "Repulsor", CONVEYOR: "Conveyor", \
                                       ZIPPER: "Zipper", PHASE: "Phase", SPLITTER: "Splitter", \
                                       GONDOLA: "Gondola", WASTEFUL: "Wasteful"}
    ORDER: ClassVar[list[int]] = [NONE, BOUNCY, ACCELERATOR, PISTON, GRAVITY, BLACK_HOLE, PORTAL, ROTATE,
                                  SLIPPERY, FRAGILE, GROWING, SHRINKING, STICKY, REPULSOR, CONVEYOR,
                                  ZIPPER, PHASE, SPLITTER, GONDOLA, WASTEFUL]
    # The real, non-NONE effects a block can actually have.
    REAL_ORDER: ClassVar[list[int]] = [BOUNCY, ACCELERATOR, PISTON, GRAVITY, BLACK_HOLE, PORTAL, ROTATE,
                                       SLIPPERY, FRAGILE, GROWING, SHRINKING, STICKY, REPULSOR,
                                       CONVEYOR, ZIPPER, PHASE, SPLITTER, GONDOLA,
                                       WASTEFUL]
    # The effects whose strength is a NUMBER: each block rolls its own value
    # around the average in MAGNITUDES.EFFECTS (see the MAGNITUDES section
    # below; that table is bound back onto this class as MAGNITUDE, so every
    # Effect.MAGNITUDE read keeps working). Magnitudes roll with the same
    # 1/(x^2+1) distribution scorers use, one step at a time, where a step is
    # 10% of the average — so a piston is usually 1500 px/s of launch, often
    # 1350 or 1650, and once in a while a wild 900 or 2100.
    #
    # On/off effects have no magnitude: Fragile, Portal, Slippery, Zipper,
    # Growing, Shrinking and Splitter either do their thing or don't, and
    # Gravity's strength is the world's gravity, not its own.
    # The unit each magnitude is spoken in (used by the descriptions).
    MAGNITUDE_UNIT: ClassVar[dict[int, str]] = {
        PISTON: "px/s", ACCELERATOR: "px/s^2", BLACK_HOLE: "px/s^2",
        REPULSOR: "px/s^2", CONVEYOR: "px/s", ROTATE: "deg/s",
        BOUNCY: "%", STICKY: "s", PHASE: "s", GONDOLA: "px/s",
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
    FRESH = 15  # 1 Reroll card on the board when touched
    PICKY = 16  # 1 unit: banks half a structure point a trigger; 1 point = a structure every run
    VOYAGER = 17  # +0.01 mult per px the marble traveled before the touch (rolled)
    SATANIC = 18  # x6.66 mult; a block dies once a marble leaves, a card after a run
    SUMMIT = 19  # +0.75 mult per unit (row) above the bottom row it sits on
    AIRBALL = 20  # +8 mult per second the marble was airborne before the touch
    SEED = 21  # +3 mult (scorer_amount) per Seed block on the board when touched
    DRILL = 22  # when touched, gives two Board Units after the run
    LUCKY = 23  # per trigger, independent rolls: 1/3 chance +130 chips, 1/9 chance +$40
    ROOMY = 24  # +2 chips (scorer_amount) per unlocked board unit when touched
    RALLY = 25  # +1 mult per fresh block touch this run before it (re-touches count)
    ECHO = 26  # re-fires the scorer of the block the marble touched right before it
    POWERLINE = 27  # +25 chips (scorer_amount) per block in its row (incl itself)
    FRONTIER = 28  # +3 mult per locked unit / board border orthogonally adjacent
    GILDED = 29  # +1/6 of current chips as mult
    BOMB = 30  # touched: unlock units within 1 cell after the run, then destroyed
    CLUSTER = 31  # +3 mult per block orthogonally adjacent to it (no diagonals)
    COLOSSUS = 32  # +0.04 xMult per px of marble radius above the base size
    UNDERTAKER = 33  # +30 mult per block destroyed this run
    DEBT = 34  # +60 chips, but the run pays no interest afterwards
    PACKED = 35  # when touched, +1 inventory slot (permanent, saved)

    # Each scorer's AVERAGE magnitude lives in MAGNITUDES.SCORERS (see the
    # MAGNITUDES section below), which is bound back onto this class as
    # DEFAULT_AMOUNT, so every Scorer.DEFAULT_AMOUNT read keeps working. An item
    # rolls its own amount around that average (see main.roll_scorer_amount).
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
        PACKED: "Packed",
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
        PACKED: (30, 60, 140),  # navy (a strapped crate)
    }
    ORDER: ClassVar[list[int]] = [NONE, CHIPS_ADD, MULT_ADD, MULT_MUL, START, FINISH,
                                  QUICK, CASH, SHARP, PARTS, SHREDS, RUBBLE, IDEAS,
                                  RANDOM, EFFECTIVE, FRESH, PICKY, VOYAGER, SATANIC,
                                  SUMMIT, AIRBALL, SEED, DRILL, LUCKY, ROOMY,
                                  RALLY, ECHO, POWERLINE, FRONTIER, GILDED, BOMB,
                                  CLUSTER, COLOSSUS, UNDERTAKER, DEBT, PACKED]
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
                                       COLOSSUS, UNDERTAKER, DEBT, PACKED]
    # The scorers whose magnitude is a MULTIPLIER of the score (xMult, Sharp,
    # Satanic, Effective). Their magnitude is never rolled below 1: a factor
    # under 1 would turn the block into a penalty instead of a weak payoff.
    MULTIPLIER_SCORERS: ClassVar[tuple] = (MULT_MUL, SHARP, SATANIC, EFFECTIVE)
    # The scorers that bank RESOURCE POINTS instead of a payoff. One whole
    # point converts into that scorer's reward (see RESOURCE_THRESHOLD), and the
    # rate says how many points a trigger banks per unit of its magnitude:
    # Shreds, Rubble and Ideas bank a point a unit, Picky half a point. Parts
    # banks whole components rather than points and Fresh deals its Reroll card
    # immediately; neither appears here.
    RESOURCE_RATE: ClassVar[dict[int, float]] = {
        SHREDS: 1,
        RUBBLE: 1,
        IDEAS: 1,
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


class TileArt:
    """The tile art a run modifier wears: its colours and what fills the screen.

    A "tile" is one square LATTICE CELL — big enough that the whole screen tiles
    exactly — drawn as a TESSELLATION of a few shapes in a few shades of the
    modifier's own base colour (see Trial.TILE_STYLES for which shapes, ui for
    the drawing). The tile is both the modifier's ICON (its collection entry)
    and the pattern the whole screen is covered in while that modifier is in
    play, and the panels drawn over it (the board, the inventory, the shop, the
    info box) are filled from the same colour family one step lighter, so a run
    reads as one palette.

    The run modifiers are the TRIALS, so each trial inherits this: it spells out
    its own colour and tile style — as unlike the other trials as it is, and
    never repeating another trial's family — and gets the derived shades
    (palette, panel_color, locked_color) for free.
    """
    # The base colour of each modifier's tile: the field its tessellation is
    # built from, and the hue its icon in the collection and its tinted panels
    # (see panel_color) are derived from. One per modifier.
    COLORS: ClassVar[dict[int, tuple]] = {}
    # Which tessellation each modifier's tile is drawn with (see ui): the pattern
    # is always made of SHAPES — rows of triangles, rings, circles, chevrons,
    # scales, diamonds, octagons, split cells — never a plain rectangle of flat
    # colour, and no two modifiers share a family, so the pattern alone names
    # which one is in play.
    TILE_STYLES: ClassVar[dict[int, str]] = {}
    # The extra colours a tile may use besides the modifier's own: an accent
    # (gold by default: the game's "payoff" colour) and the two ends of the
    # light/dark range. Kept as fractions so every palette is derived from
    # COLORS.
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
    def palette(cls, value):
        """The few colours one tile is built from.

        Four shades derived from the modifier's base colour — a light, the base
        itself, a dark, and a pale accent — so a tile reads as one colour FAMILY
        while its shapes still tell each other apart. The mesh lines drawn
        between the shapes use the dark shade, so the same palette covers the
        whole pattern.
        """
        base = cls.COLORS.get(value, (60, 60, 70))
        return {
            "light": shade(base, cls.TILE_LIGHT),
            "base": base,
            "dark": shade(base, -cls.TILE_DARK),
            "accent": shade(base, cls.TILE_ACCENT_LIGHT),
        }

    @classmethod
    def panel_color(cls, value):
        """The colour the board/inventory/shop panels are filled with.

        The modifier's tile colour, a little lighter, so the panels read as part
        of the run's palette instead of a separate red. The one exception is a
        tile that is already very light (the all-finishes trial is near-white):
        its panels are darkened instead of lightened, because they carry white
        text and near-white panels would swallow it. No modifier at all (or an
        unknown id) keeps the game's own panel colour.
        """
        if value is None:
            return None
        base = cls.COLORS.get(value, (60, 60, 70))
        if sum(base) / 3 > cls.PANEL_LIGHT_LIMIT:
            return shade(base, -cls.TILE_DARK)
        return shade(base, cls.PANEL_LIGHT)

    @classmethod
    def locked_color(cls, value):
        """The colour a LOCKED board square is filled with during that modifier.

        Always taken a step DOWN from panel_color (LOCKED_DARK) rather than
        straight from the tile's base: the all-finishes tile is near-white and
        its panel is darkened rather than lightened, so a locked square derived
        from the base could come out the SAME as its own panel — or lighter.
        Deriving from the panel makes a locked square darker than the unlocked
        ones around it for every modifier, which is what keeps the playable
        region reading as raised out of the board it sits in. No modifier (or an
        unknown id) returns None, and the caller keeps its own locked colour.
        """
        panel = cls.panel_color(value)
        if panel is None:
            return None
        return shade(panel, -cls.LOCKED_DARK)


class Trial(TileArt):
    """A run-wide modifier applied to each run, exactly one per run.

    Each class constant is a trial's ID number (e.g. ``Trial.HANDS_TIED == 0``).
    The trial's description explains its effect on the run, and the tile art it
    wears while it runs — its colour and its tessellation — is the data below
    (see TileArt).
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
    X_RAY = 15
    PHANTOM = 16
    VERTIGO = 17
    ELEPHANT = 18
    # The two that used to be the 24th run's FINAL BOSSES (user request: "make
    # the final bosses just normal bosses ... for the final boss, just use a
    # random normal boss"): they are ordinary run modifiers now, drawn from the
    # same pool as every other trial, with Sky High's target doubled rather than
    # tripled and the Singularity's mass growth slowed down.
    SKY_HIGH = 19
    SINGULARITY = 20

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
        X_RAY: "X-ray",
        PHANTOM: "Phantom",
        VERTIGO: "Vertigo",
        ELEPHANT: "Elephant",
        SKY_HIGH: "Sky High",
        SINGULARITY: "Singularity",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        HANDS_TIED: "A random 1/4 of your blocks can score 1 fewer time per "
                    "run.",
        CARD_CUTTER: "Disables a random card.",
        DEAD_ZONE: "Gravity is tripled in the board's bottom third.",
        ALL_FINISHES: "The board borders count as finish blocks.",
        SLIM_PICKINGS: "Removes two random shop options.",
        LONG_RUN: "Time exponent is penalized after double the normal time.",
        SHUFFLED: "Flips and shuffles your cards.",
        BOUNCY_CASTLE: "Every solid block bounces like a bouncy block.",
        CRUMBLING: "A random 1/4 of your blocks are fragile: they shatter "
                   "when touched.",
        MARBLE_WEIGHT: "Randomly heavier or lighter: effect pushes are weaker "
                       "or stronger, but it falls at the same speed.",
        SPEEDRUN: "Time exponent is penalized after half the normal time.",
        REPEATS_ONLY: "Only block types touched twice count toward the "
                      "uniqueness score.",
        INFLATION: "Everything costs 50% more: upgrades and disassembly.",
        EMPTY_POCKETS: "The end-of-run cash award skips its score-based bonus "
                       "(the flat $20, interest, and Cash-card payouts stay).",
        DEAL_BREAKER: "Blocks never score until you sell a card — one sale is "
                      "enough.",
        X_RAY: "You can't see the marble or its trail.",
        PHANTOM: "The marble starts phasing: it passes through every block for "
                 "the first second of the run.",
        VERTIGO: "Gravity pulls in a random direction.",
        ELEPHANT: "The marble starts at double its size.",
        SKY_HIGH: "The required score is doubled.",
        SINGULARITY: "The marble gains mass over time, falling ever faster.",
    }
    ORDER: ClassVar[list[int]] = [HANDS_TIED, CARD_CUTTER, DEAD_ZONE, ALL_FINISHES,
                                  SLIM_PICKINGS, LONG_RUN, SHUFFLED,
                                  BOUNCY_CASTLE, CRUMBLING, MARBLE_WEIGHT,
                                  SPEEDRUN, REPEATS_ONLY, INFLATION,
                                  EMPTY_POCKETS, DEAL_BREAKER, X_RAY, PHANTOM,
                                  VERTIGO, ELEPHANT, SKY_HIGH, SINGULARITY]
    # The base colour of each trial's tile (see TileArt.COLORS).
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
        X_RAY: (120, 180, 210),         # scanning blue
        PHANTOM: (150, 205, 190),       # spectral green
        VERTIGO: (170, 60, 200),        # dizzy violet
        ELEPHANT: (140, 110, 95),       # heavy taupe
        # The two former final bosses keep the tiles they wore as bosses: the
        # event horizon's indigo and a very high sky's cerulean, neither of them
        # another trial's hue.
        SKY_HIGH: (86, 172, 220),       # sky cerulean
        SINGULARITY: (58, 46, 84),      # event-horizon indigo
    }
    # Which tessellation each trial's tile is drawn with (see ui): the family is
    # picked to echo what the trial does (interlocked rings for chained hands,
    # circles bouncing in a castle, chevrons for speed, scales for repetition,
    # cut cells for a cutter, climbing bars for inflation ...) and NO TWO
    # TRIALS SHARE ONE, so a pattern names its trial.
    TILE_STYLES: ClassVar[dict[int, str]] = {
        HANDS_TIED: "rings",         # links of a chain
        CARD_CUTTER: "splits",       # cards cut corner to corner
        DEAD_ZONE: "bands",          # bands, heavier down the tile
        ALL_FINISHES: "checker",     # the finish checkerboard, in triangles
        SLIM_PICKINGS: "octagons",   # tiles with gaps between them
        LONG_RUN: "bars",            # a long even track of bars
        SHUFFLED: "pinwheel",        # cells rotated every which way
        BOUNCY_CASTLE: "circles",    # balls, touching in a lattice
        CRUMBLING: "cracked",        # a broken triangle lattice
        MARBLE_WEIGHT: "dots",       # big marbles against small ones
        SPEEDRUN: "chevrons",        # speed
        REPEATS_ONLY: "scales",      # the same arc repeated
        INFLATION: "ramps",          # prices climbing, one step at a time
        EMPTY_POCKETS: "pockets",    # hollow rings, nothing inside
        DEAL_BREAKER: "tears",       # cells torn apart
        X_RAY: "mesh",              # the scan grid you look the board through
        PHANTOM: "crescents",       # moons fading in and out
        VERTIGO: "gyres",           # dials, each turned a quarter further
        ELEPHANT: "plates",         # heavy slabs, side by side
        # The two former bosses' own families: unit blocks stacked into a
        # climbing stair for the run whose target is doubled, and rings closing
        # on a black core for the marble that grows heavier.
        SKY_HIGH: "towers",         # blocks stacked into a stair
        SINGULARITY: "cores",       # rings collapsing into a black core
    }

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
    """How rare an ITEM is: its tier, from Common up to Legendary.

    User request: "give all items a rarity." Every item has one — a card, an
    action, a tool, a passive, a part (a shape, an effect, a scorer), a pack and
    a structure (see Rarity.of, which answers for any of them). A block reads the
    tier of its parts and a Spirit token the tier of the block it keeps. The
    level's own things (a foe, its furniture, a trial) and the bar's readouts are
    not items and have no tier. The tiers are ORDERED — Common is the most
    ordinary and Legendary the rarest — and the ORDER is also the display order,
    so a list of the tiers reads cheapest first.

    ONE RULE: an item's tier is its PRICE's tier (see BANDS and from_price), so
    a $28 part and a $28 card and a $28 action are all Common. That is the
    codebase's usual rarity rule, and it is the same number the shop already
    draws by — a part is offered at 1/price (see component_weight) — so an
    item's stripe and its odds can never disagree. Card.RARITIES was authored on
    exactly these bands. The two kinds that are not priced one item at a time
    say so themselves: a STRUCTURE is free (Structure.RARITIES) and a PACK is
    priced by its SIZE (Pack.RARITIES).

    The tier sets how often the shop OFFERS a card: WEIGHTS is the relative
    frequency of the TIERS — 1 : 0.7 : 0.5 : 0.3 : 0.2 from Common up to
    Legendary — and the shop's card offers draw the tier first and the card
    inside it second (see main.random_card_option_value). An offer is therefore
    Rare 0.5 times as often as it is Common however many cards carry each tier:
    the CARD COUNT of a tier must not change the tier's own odds, which is
    exactly why the tier is drawn first. Every match-group card — the 832
    shape-group and effect cards — is COMMON, which is what the design asks for
    (a group card is priced by its group, not by its tier: see match_group_price).
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
    # The price bands every item's tier follows, cheapest first: an item worth
    # up to the ceiling is that tier, and anything dearer is Legendary. Card's
    # whole cards were tiered on exactly these bands (the $28 Gate and Challenger
    # are Common, the $29-$38 helpers Unusual, the $48 Showman Legendary), which
    # is what makes one rule cover every kind of item.
    BANDS: ClassVar[tuple] = ((28, COMMON), (38, UNUSUAL), (44, RARE),
                              (47, EPIC))

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

    @classmethod
    def from_price(cls, price):
        """The tier an item of this price sits in (see BANDS).

        The one rarity rule: the dearer an item is, the rarer it is. A free item
        (a starter tool, a lump of dirt) is Common.
        """
        for ceiling, tier in cls.BANDS:
            if price <= ceiling:
                return tier
        return cls.LEGENDARY

    @classmethod
    def of_kind(cls, kind, value):
        """The tier of an item of this KIND and value, or None (see Rarity.of).

        A card and a match-group card read Card.RARITIES (every card built on a
        group is Common); a structure and a pack read their own table, because
        one is free and the other is priced by its size; everything else is
        priced one item at a time, so its tier is that price's tier.
        """
        if kind == "card":
            return Card.rarity(value)
        if kind == "match_group":
            # The codex's entry for a match group stands for every card built on
            # it, and every one of those is Common (see Card.RARITIES).
            return cls.COMMON
        if kind == "structure":
            return Structure.rarity(value)
        if kind == "pack":
            return Pack.rarity(value)
        if kind in (Component.SHAPE, Component.EFFECT, Component.SCORER):
            return cls.from_price(COMPONENT_PRICES.get((kind, value), 0))
        if kind == "action":
            return cls.from_price(Action.PRICES.get(value, 0))
        if kind == "tool":
            return cls.from_price(Tool.PRICES.get(value, 0))
        if kind == "passive":
            return cls.from_price(Passive.PRICES.get(value, 0))
        return None

    @classmethod
    def of(cls, item):
        """The tier of an ITEM, or None for something that is not an item.

        The kinds without a price table are read from what they are MADE of: a
        block — built, offered or standing on the board — is worth the parts it
        is built from (see block_price_for), and a Spirit token keeps a whole
        block, so it wears that block's tier. The level's own things (an enemy,
        its furniture) are not the player's items and have no tier, exactly as
        they have no price.
        """
        if item is None:
            return None
        if (getattr(item, "is_enemy", False)
                or getattr(item, "is_level_prop", False)):
            return None
        kind = getattr(item, "kind", None)
        if kind == "token":
            return cls.of(getattr(item, "block", None))
        if kind == "pack":
            # A pack names what it holds by its TYPE, not by a `value` (see
            # items.offer_key, which resolves the same difference).
            return cls.of_kind("pack", getattr(item, "pack_type", None))
        if kind is None and hasattr(item, "rect") and hasattr(item, "shape"):
            kind = "block"  # a block standing on the board carries no kind
        if kind == "block":
            effects = getattr(item, "effects", None) or ()
            return cls.from_price(block_price_for(item.shape, effects,
                                                  item.scorer))
        return cls.of_kind(kind, getattr(item, "value", None))


class Card:
    """An indivisible whole card bought from the shop.

    Every card is whole: nothing splits and nothing is assembled, and no card
    carries a rolled magnitude. Three families live here:

    * the NAMED CARDS (Joker ... Island) — the classic cards. Each is one
      effect that fires at the start of a run, at the end of it, or when a
      fragile block breaks (see Card.NAMED and cards.apply_cards), and each
      keeps the name, the flavour comment and the trigger prose of the named
      CONDITION it was briefly split into. Fountain, the one card in that table
      which never was a named condition, is measured exactly the same way, so
      it sits with them.
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
    ISLAND = 99        # +0.5 xMult per unconnected group of units, at the end
    # The measured family's newest member, and the first one that never was a
    # named condition: a whole card whose payoff is a per-run MEASUREMENT,
    # exactly like the named cards above (see Card.NAMED), so it plays through
    # the same start/end machinery. It takes the first free id in the 12..77
    # band: the named conditions' ids are all taken, and Fountain was never one
    # of them.
    FOUNTAIN = 12      # +0.25 xMult per 3 different pipe-group blocks in a row
    # The second measured card that never was a named condition: it pays mult
    # for the TIME a marble spends inside things (see Card.NAMED).
    INTANGIBLE = 13    # +0.5 mult a second inside a block, +15 inside a locked unit
    # Owning the Showman card lets the player buy more than one copy of any
    # other card (duplicates are otherwise blocked).
    SHOWMAN = 78
    # Garden doubles the per-seed payoff of Seed-scorer blocks (+3 -> +6 mult).
    # New whole-card ids stay in the free 12..77 band, or in the 79..99 one the
    # newer cards share with the named cards — 0..11 are the named cards'.
    GARDEN = 80
    # Rigged Casino re-weights Random blocks toward +xMult and away from +chips.
    RIGGED_CASINO = 81
    # Conquistador hands over board units after every run (user request: board
    # squares its owner picks, instead of squares it picked for them).
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
    WATCH = 91  # the run's time score factor is always at its maximum
    # The newest whole cards. Their ids continue the shared band upward;
    # Painting (92), Synthesizer (93) and Island (99) belong to the named cards,
    # so the free ids left in the band are 12..77.
    TESSERACT = 94  # permanently +0.1 xMult for every Reroll card used
    THOUSAND_HANDED = 95  # creates a random action after every run
    PROCRASTINATION = 96  # ends the run a second late: rewinds it once per copy and refills triggers
    ESSENCE = 97  # $10 a run, one card slot fewer, 2 permanent tokens when sold
    CONCERT = 98  # +1 trigger per run for every block that is not a plain rect
    # The two newest whole cards. Hoard takes the first free id of the 12..77
    # band (nothing has claimed 14 yet); Infinity takes the next one.
    HOARD = 14  # middle-click a shop option to hold it across rerolls
    INFINITY = 15  # the distance and uniqueness score factors never level off
    # The two measured cards added after them. Both read a BUILD-state number
    # — the cards' own sell value, and the slots no OTHER card is filling — so
    # they fire at the start of a run like Painting and Synthesizer. They take
    # the next free ids in the 12..77 band.
    SWASHBUCKLER = 16  # +1/5 of the total sell price of your cards, as mult
    STENCIL = 17       # +1 xMult for each card slot no other card fills
    # The newest whole card: a passive rule like Coupon's or Showman's, read
    # where the collision happens (Game._brain_loop_roll), so it takes the next
    # free id in the 12..77 band.
    BRAIN_LOOP = 18  # a sticky touch has a 1/3 chance of handing over an action
    # The four newest whole cards. Claustrophobia is a measured card (it counts
    # the plain walls on the board at the start of a run), so it joins
    # Card.NAMED; the other three are passives read where their mechanic lives —
    # the shop's magnitudes (Earthquake), the trial display's fees (Challenger)
    # and the inventory's own G key (Odyssey, the second card with a VERB, after
    # Hoard). All four take the next free ids in the 12..77 band.
    CLAUSTROPHOBIA = 19  # +3 mult at the start of a run for each plain wall
    EARTHQUAKE = 20      # shop effects and scorers roll 10% higher
    CHALLENGER = 21      # changing or disabling a trial costs half as much
    ODYSSEY = 22         # press G to bank an item for a run, for half its value
    # The two newest whole cards, taking the next free ids in the 12..77 band.
    # Matrix is a measured card (an end-phase one: it counts seconds inside a
    # locked board unit, which is only final once the marbles have stopped), so
    # it joins Card.NAMED; Gate is an event card, read where the key/lock
    # mechanic happens (Game._gate_key_and_lock).
    MATRIX = 23  # +45 chips an unphased second inside a locked board unit
    GATE = 24    # +30 chips each time a marble carries its key through the lock
    # Trash Can is the newest measured card, and an end-phase one: it counts the
    # items the run threw away (Wasteful throwing a pair, a Lantern spending
    # itself — see Game._discard_item) and pays MAGNITUDES.TRASH_CAN_CHIPS a
    # unit for them. It takes the next free id in the 12..77 band.
    TRASH_CAN = 25  # +20 chips per item discarded this run
    # Smelly Socks pays in TWO currencies at once (+15 chips and +2 mult at the
    # start of a run), which no measured row can express — Card.NAMED pays one
    # scorer — so it is a FIXED-payoff card read where its mechanic lives, like
    # Gate's chips and Essence's cash (see cards._apply_smelly_socks). Its other
    # half is a cost: a card drawn with it goes back into the deck. It takes the
    # next free id in the 12..77 band.
    SMELLY_SOCKS = 26

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
        FOUNTAIN: "Fountain",
        INTANGIBLE: "Intangible",
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
        HOARD: "Hoard",
        INFINITY: "Infinity",
        SWASHBUCKLER: "Swashbuckler",
        STENCIL: "Stencil",
        BRAIN_LOOP: "Brain Loop",
        CLAUSTROPHOBIA: "Claustrophobia",
        EARTHQUAKE: "Earthquake",
        CHALLENGER: "Challenger",
        ODYSSEY: "Odyssey",
        MATRIX: "Matrix",
        GATE: "Gate",
        TRASH_CAN: "Trash Can",
        SMELLY_SOCKS: "Smelly Socks",
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
        FOUNTAIN: "Water always finds a way.",
        INTANGIBLE: "Not all there.",
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
        HOARD: "Mine, all mine.",
        INFINITY: "No ceiling.",
        SWASHBUCKLER: "Loot and plunder.",
        STENCIL: "Less is more.",
        BRAIN_LOOP: "Ideas on impact.",
        CLAUSTROPHOBIA: "Walls closing in.",
        EARTHQUAKE: "Everything shakes loose.",
        CHALLENGER: "Bring it on.",
        ODYSSEY: "A long way from home.",
        MATRIX: "Inside the grid.",
        GATE: "The way is open.",
        TRASH_CAN: "One man's junk.",
        SMELLY_SOCKS: "Something died in here.",
    }
    # What each whole card does. A named card's line states the payoff it pays
    # at its own magnitude (the card has no scorer half to roll, so the number
    # is fixed — see Card.NAMED for the arithmetic).
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        JOKER: "Adds 4 mult at the start of the run",
        EXPLORER: "Multiplies the multiplier by up to x2 at the end of the run, by the board units the marble has been in",
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
        ISLAND: "Adds 0.125 xMult at the end of the run for each unconnected group of unlocked board units",
        FOUNTAIN: "Adds 0.25 xMult at the end of the run for every 3 different Pipe, Drain or Pipe Bend blocks the marble touches in a row",
        INTANGIBLE: "Adds, at the end of the run, 0.5 mult a second inside a block and 15 a second inside a locked board unit",
        ERR_404: r"\marblatro\main.py, line 2339: 'self._return_card()' CardNotFoundError: Card was not found [FATAL]",
        BLUEPRINT: "Copies the function of the card to its immediate left in the card area",
        SHOWMAN: "Lets cards you already own show up in the shop again, so you can own more than one of the same card",
        GARDEN: "Seed blocks give +6 mult per seed on the board instead of +3",
        RIGGED_CASINO: "Random blocks give +xMult 3x more often and +chips 3x less often",
        CONQUISTADOR: "After each run, gives 4 Board Units — each one opens a locked board square you pick",
        PEDESTAL: "Retriggers the scorer of the first 3 blocks the marble touches in a run",
        INFERNO: "Adds 0.07 to the exponent the total score is raised to",
        DOPPELGANGER: "Each Start block releases a second marble, which starts with an x-velocity of 1",
        COMPOUND_INTEREST: "Doubles the interest on your cash: $2 for every $10 you hold at the end of a run",
        COUPON: "Every shop option costs 25% less (board units excluded)",
        FACTORY: "Resource conversions need half as many points (rounded up)",
        MINESHAFT: "Board units cost $5 instead of $8",
        MARKET: "Selling a card, block, or action refunds 75% of its price instead of 50%",
        WATCH: "The run's time score factor is always at its maximum, however long the run takes",
        TESSERACT: "Every Reroll card you use permanently adds +0.1 xMult, applied at the start of each run",
        THOUSAND_HANDED: "Creates a random action after every run",
        PROCRASTINATION: "Rewinds the run 1 second each time it finishes, refilling every trigger — one rewind per copy",
        ESSENCE: "Gives $10 at the end of every run, but takes a card slot away — selling it leaves 2 random permanent Spirit tokens",
        CONCERT: "Every block that is not a plain rect and has both an effect and a scorer can score 1 more time per run",
        HOARD: "Middle-click a shop option to hold it through rerolls; one held offer per copy of this card",
        INFINITY: "Distance and uniqueness rise in straight lines instead of levelling off, meeting the usual curve at 0.75",
        SWASHBUCKLER: "Adds mult at the start of the run equal to 1/5 of the total sell price of your cards",
        STENCIL: "Gives +1 xMult at the start of the run for each empty card slot, counting its own",
        BRAIN_LOOP: "Gives a 1/3 chance of a random action each time a marble collides with a sticky block",
        CLAUSTROPHOBIA: "Adds 3 mult at the start of the run for each plain Rect block on your board",
        EARTHQUAKE: "Effects and scorers offered in the shop roll 10% higher",
        CHALLENGER: "Changing or disabling this run's trial costs half as much",
        ODYSSEY: "Press G to put a selected item away for a run; it returns with half its sell price in cash (one per copy)",
        MATRIX: "Adds 45 chips at the end of the run for each second a marble is inside a locked board unit, not phasing",
        GATE: "Adds 30 chips each time a marble that collected a key passes through its opened lock",
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
    # 16+25=41 -> $32. Fountain has no named condition behind it, so it is
    # priced off the two parts it is made of the same way: the PIPE GROUP it
    # watches (18, the price of a Pipe/Drain/Pipe Bend collision condition —
    # see match_group_price) plus the xMult scorer half (25) = 43 -> $34.
    # Intangible measures the time a marble spends inside things, so it is
    # priced the same way off the two parts it is built on: the pass-through
    # field it counts a marble sitting in — the (none) shape group's collision
    # condition (16) — plus the mult scorer half (17) = 33 -> $26. Its
    # locked-unit clause is a second rate on the same measure (see Card.NAMED),
    # not a second component.
    PRICES: ClassVar[dict[int, int]] = {JOKER: 24, EXPLORER: 32, ASTRONAUT: 27,
                                        PLANE: 22, PILLAR: 26, BANKER: 20,
                                        WRECKING_BALL: 27, SKATER: 32,
                                        GLITCH: 23, RIPPED_CARD: 19,
                                        COZY: 23, PAINTING: 21,
                                        SYNTHESIZER: 25, ISLAND: 32,
                                        FOUNTAIN: 34,
                                        INTANGIBLE: 26,
                                        ERR_404: 19, BLUEPRINT: 33, SHOWMAN: 48,
                                        GARDEN: 36, RIGGED_CASINO: 38,
                                        CONQUISTADOR: 44, PEDESTAL: 44,
                                        INFERNO: 50, DOPPELGANGER: 46,
                                        COMPOUND_INTEREST: 36, COUPON: 46,
                                        FACTORY: 44, MINESHAFT: 28,
                                        MARKET: 26, WATCH: 40, TESSERACT: 44,
                                        THOUSAND_HANDED: 42,
                                        PROCRASTINATION: 46, ESSENCE: 48,
                                        CONCERT: 44,
                                        # Hoard is priced as a shop utility
                                        # (cheap next to Coupon's discount) and
                                        # Infinity above Inferno: it rewrites
                                        # two of the three factors the total
                                        # score's exponent is made of, and it
                                        # is the only thing in the game that
                                        # has no ceiling at all.
                                        HOARD: 36, INFINITY: 52,
                                        # Swashbuckler is a mult engine fuelled
                                        # by what the player's cards are worth
                                        # (it counts its own price too, so it
                                        # pays about a Joker's worth even
                                        # alone), and Stencil is priced as a
                                        # build-defining multiplier: five
                                        # empty slots is x5, and it is paid
                                        # for by owning nothing else.
                                        SWASHBUCKLER: 42, STENCIL: 46,
                                        # Brain Loop is a Rare: it hands out
                                        # actions (worth $24-$70 each) for the
                                        # right blocks, where 1000-handed
                                        # ($42) hands one over after every run
                                        # whatever the board looks like.
                                        BRAIN_LOOP: 40,
                                        # Claustrophobia is a mult engine that
                                        # scales with the plainest thing in the
                                        # game (a free Rect wall), so it sits
                                        # beside Swashbuckler at the top of the
                                        # cheap band. Earthquake is a quiet
                                        # always-on buff to what the shop rolls,
                                        # Challenger only pays off for a player
                                        # who buys trials, and Odyssey is an
                                        # income card that never spends the item
                                        # it banks.
                                        CLAUSTROPHOBIA: 40, EARTHQUAKE: 38,
                                        CHALLENGER: 28, ODYSSEY: 40,
                                        # Matrix pays a big rate for a state
                                        # that is rare and easy to lose (a
                                        # marble inside a locked unit with its
                                        # phase off), so it sits beside the
                                        # other measured end cards; Gate is an
                                        # event card worth one standard chip
                                        # unit a pass, so it is priced with the
                                        # cheapest utility whole cards.
                                        MATRIX: 30, GATE: 24,
                                        # Trash Can pays a measured end payout
                                        # like Matrix's, but for something the
                                        # player chooses to do (throw items
                                        # away), so it sits beside the cheap
                                        # utility cards.
                                        TRASH_CAN: 26,
                                        # Smelly Socks pays half a Joker and
                                        # half a chips card at once, but hands
                                        # a drawn card back to the deck to do
                                        # it, so it costs a plain card.
                                        SMELLY_SOCKS: 24}
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
        FOUNTAIN: (70, 155, 205),   # fountain water
        INTANGIBLE: (225, 235, 250),  # ghost pale
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
        HOARD: (170, 140, 45),      # hoarded brass
        INFINITY: (205, 195, 235),  # silver-lilac
        SWASHBUCKLER: (140, 45, 60),  # buccaneer maroon
        STENCIL: (150, 165, 120),   # stencil sage
        BRAIN_LOOP: (205, 115, 170),  # synapse pink
        CLAUSTROPHOBIA: (115, 95, 80),  # crowding brown
        EARTHQUAKE: (135, 105, 70),   # fault-line earth
        CHALLENGER: (215, 120, 45),   # duel orange
        ODYSSEY: (40, 90, 130),       # open sea
        MATRIX: (60, 160, 95),        # terminal green
        GATE: (105, 115, 140),        # portcullis steel
        TRASH_CAN: (95, 120, 90),     # bin green
        SMELLY_SOCKS: (150, 128, 92), # woolly beige
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
        FOUNTAIN: "F",
        INTANGIBLE: "V",
        ERR_404: "4", BLUEPRINT: "B", SHOWMAN: "!",
        GARDEN: "G", RIGGED_CASINO: "R", CONQUISTADOR: "C",
        PEDESTAL: "P", INFERNO: "I", DOPPELGANGER: "D",
        COMPOUND_INTEREST: "%", COUPON: "C", FACTORY: "F",
        MINESHAFT: "M", MARKET: "S", WATCH: "W",
        TESSERACT: "T", THOUSAND_HANDED: "H",
        PROCRASTINATION: "Z",
        ESSENCE: "E",
        CONCERT: "N",
        HOARD: "H", INFINITY: "8",
        SWASHBUCKLER: "X", STENCIL: "A",
        BRAIN_LOOP: "Q",
        CLAUSTROPHOBIA: "C", EARTHQUAKE: "E",
        CHALLENGER: "K", ODYSSEY: "O",
        MATRIX: "M", GATE: "G",
        TRASH_CAN: "T",
        SMELLY_SOCKS: "S",
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
                                  CONCERT, ISLAND, FOUNTAIN, INTANGIBLE,
                                  HOARD, INFINITY,
                                  SWASHBUCKLER, STENCIL, BRAIN_LOOP,
                                  CLAUSTROPHOBIA, EARTHQUAKE, CHALLENGER,
                                  ODYSSEY, MATRIX, GATE, TRASH_CAN,
                                  SMELLY_SOCKS]
    # How rare each whole card is. A whole card's tier follows its price, the
    # codebase's usual rarity rule (see component_weight): up to $28 Common,
    # $29-$38 Unusual, $39-$44 Rare, $45-$47 Epic, $48 and up Legendary — the
    # very bands Rarity.from_price reads (see Rarity.BANDS), so every card's row
    # here is the tier its price would give it anyway. They are written out
    # because a card's tier is also what the shop draws by (see Rarity.WEIGHTS),
    # so the table is the shop's odds, not just a label. The cheap economy cards
    # are Common and the cards that rewrite how a run is played (Showman,
    # Essence, Inferno) are Legendary. Every match-group card is COMMON instead
    # (set in the MATCH GROUPS catalogue below), so every tier above Common is a
    # whole card.
    RARITIES: ClassVar[dict[int, int]] = {
        # Common: the joke card and the cheap utility.
        ERR_404: Rarity.COMMON, MARKET: Rarity.COMMON,
        MINESHAFT: Rarity.COMMON,
        # The named cards and the measured cards added after them: everything
        # whose tier follows a price band, which is every whole card except the
        # three cheap utility ones below. The two dearest measured cards ($32)
        # are Unusual along with Fountain ($34), while Intangible ($26) is one of
        # the cheap measured cards.
        # Trash Can ($26) is a cheap measured card, so it joins this band.
        JOKER: Rarity.COMMON, PLANE: Rarity.COMMON, BANKER: Rarity.COMMON,
        TRASH_CAN: Rarity.COMMON,
        PILLAR: Rarity.COMMON, ASTRONAUT: Rarity.COMMON,
        WRECKING_BALL: Rarity.COMMON, GLITCH: Rarity.COMMON,
        RIPPED_CARD: Rarity.COMMON, COZY: Rarity.COMMON,
        PAINTING: Rarity.COMMON, SYNTHESIZER: Rarity.COMMON,
        INTANGIBLE: Rarity.COMMON,
        EXPLORER: Rarity.UNUSUAL, SKATER: Rarity.UNUSUAL, ISLAND: Rarity.UNUSUAL,
        FOUNTAIN: Rarity.UNUSUAL,
        # Unusual: single-mechanic helpers.
        BLUEPRINT: Rarity.UNUSUAL, GARDEN: Rarity.UNUSUAL,
        COMPOUND_INTEREST: Rarity.UNUSUAL, RIGGED_CASINO: Rarity.UNUSUAL,
        HOARD: Rarity.UNUSUAL,
        # Rare: cards that change a rule for the whole game.
        WATCH: Rarity.RARE, THOUSAND_HANDED: Rarity.RARE,
        CONQUISTADOR: Rarity.RARE, PEDESTAL: Rarity.RARE,
        FACTORY: Rarity.RARE, TESSERACT: Rarity.RARE, CONCERT: Rarity.RARE,
        # Swashbuckler is Rare: the scaling mult engine (its own band), and so
        # is Brain Loop ($40), an action engine that needs sticky blocks.
        SWASHBUCKLER: Rarity.RARE, BRAIN_LOOP: Rarity.RARE,
        # Claustrophobia ($40) is the second Rare engine: it pays for walls,
        # and a wall is the one thing an assembled block is free to be. Odyssey
        # ($40) is Rare too: it is an income card that costs a card slot and
        # ties up an item for a run. Earthquake ($38) and Challenger ($28) are
        # utilities, so they sit in the tiers their prices put them in.
        CLAUSTROPHOBIA: Rarity.RARE, ODYSSEY: Rarity.RARE,
        EARTHQUAKE: Rarity.UNUSUAL, CHALLENGER: Rarity.COMMON,
        # Matrix ($30) is Unusual beside the other measured end cards, and Gate
        # ($24) is a Common, like the cheap utility whole cards it is priced
        # with.
        MATRIX: Rarity.UNUSUAL, GATE: Rarity.COMMON,
        # Smelly Socks is a cheap card ($24) with a real cost attached, so it
        # sits in the Common band with the other cheap whole cards.
        SMELLY_SOCKS: Rarity.COMMON,
        # Epic: the economy cards that compound over a whole game, and Stencil
        # ($46), whose x5 wants a deliberately empty card area.
        COUPON: Rarity.EPIC, DOPPELGANGER: Rarity.EPIC,
        PROCRASTINATION: Rarity.EPIC, STENCIL: Rarity.EPIC,
        # Legendary: the most expensive whole cards.
        SHOWMAN: Rarity.LEGENDARY, ESSENCE: Rarity.LEGENDARY,
        INFERNO: Rarity.LEGENDARY, INFINITY: Rarity.LEGENDARY,
    }
    # The measured whole cards' effects (id -> phase, scorer, ratio, measure)
    # live in the MAGNITUDES section below, where the ratio is the card's own
    # magnitude: see MAGNITUDES.CARD_RATIOS and the Card.NAMED table bound
    # there. Nothing about a card magnitude is written here.

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


# =============================================================================
# MAGNITUDES: the one place every effect, scorer and card magnitude is set
# =============================================================================
# Every NUMBER an item rolls, pays or scales by is defined here and nowhere
# else. A reference anywhere in the codebase reads one of these tables; nothing
# re-types a magnitude. The price tables deliberately do NOT read them: a roll
# changes what an item DOES, never what it costs (see scorer_component_price).
#
#   Effect.MAGNITUDE      <- MAGNITUDES.EFFECTS     (bound below)
#   Scorer.DEFAULT_AMOUNT <- MAGNITUDES.SCORERS     (bound below)
#   Card.NAMED            <- MAGNITUDES.CARD_RATIOS (used by the table below)
class MAGNITUDES:
    # --- Effect magnitudes ---------------------------------------------------
    # The average each block rolls its own strength around (see
    # main.roll_effect_magnitude). On/off effects have no entry: Fragile,
    # Portal, Slippery, Zipper, Growing, Shrinking and Splitter either do their
    # thing or don't, and Gravity's strength is the world's gravity, not its own.
    EFFECTS: ClassVar[dict[int, float]] = {
        Effect.PISTON: 1500,        # px/s launch speed
        Effect.ACCELERATOR: 20000,  # px/s^2 of push along its arrow
        Effect.BLACK_HOLE: 3000,    # px/s^2 of pull at the edge of its range
        Effect.REPULSOR: 1500,      # px/s^2 of push at the edge of its range
        Effect.CONVEYOR: 300,       # px/s the belt carries a marble along at
        Effect.ROTATE: 900,         # deg/s the shape spins at
        Effect.BOUNCY: 100,         # % of the impact speed kept when bouncing
        Effect.STICKY: 0.4,         # seconds the marble is held against it
        Effect.PHASE: 1.0,          # seconds of phasing a touch grants
        Effect.GONDOLA: 100,         # px/s the cable car slides along its lane
    }

    # --- Scorer magnitudes ---------------------------------------------------
    # The average each item rolls its own amount around (see
    # main.roll_scorer_amount). A scorer that pays a FIXED reward rather than a
    # rolled amount (Quick, Random, Lucky, Gilded, Glitch) has 0 here; its
    # magnitude is the matching constant further down this class.
    SCORERS: ClassVar[dict[int, float]] = {
        Scorer.NONE: 0,
        Scorer.CHIPS_ADD: 30,
        Scorer.MULT_ADD: 4,
        Scorer.MULT_MUL: 1.5,  # xMult multiplies the multiplier by this
        Scorer.START: 0,
        Scorer.FINISH: 0,
        Scorer.QUICK: 0,  # speed-based: see QUICK_CHIPS_PER_SPEED
        Scorer.CASH: 15,  # $15 per trigger
        Scorer.SHARP: 2,  # 2x mult per trigger
        Scorer.PARTS: 1,  # 1 component per trigger
        Scorer.SHREDS: 1,  # 1 unit; banks a shred point a trigger (RESOURCE_RATE)
        Scorer.RUBBLE: 1,  # 1 unit; banks a rubble point a trigger
        Scorer.IDEAS: 1,  # 1 unit; banks an idea point a trigger
        Scorer.RANDOM: 0,  # picks among fixed rewards; no single amount
        Scorer.EFFECTIVE: 2.5,  # multiplies the multiplier by 2.5 (+1.5 xMult)
        Scorer.FRESH: 1,  # 1 Reroll card per trigger
        Scorer.PICKY: 1,  # 1 unit; banks PICKY's half a structure point a trigger
        Scorer.VOYAGER: 0.01,  # mult per PIXEL the marble traveled before the touch
        Scorer.SATANIC: 6.66,  # multiplies the multiplier by 6.66 when touched
        Scorer.SUMMIT: 0.75,  # +0.75 mult per row above the bottom row
        Scorer.AIRBALL: 8,  # +8 mult per second of air time before the touch
        Scorer.SEED: 4,  # +4 mult per Seed block on the board
        Scorer.DRILL: 2,  # two Board Units after the run
        Scorer.LUCKY: 0,  # rolls fixed rewards; no single amount
        Scorer.ROOMY: 2,  # +2 chips per unlocked board unit
        Scorer.RALLY: 1,  # +1 mult per fresh touch before it
        Scorer.ECHO: 0,  # copies the previous block's scorer
        Scorer.POWERLINE: 25,  # +25 chips per block in its row
        Scorer.FRONTIER: 3,  # +3 mult per locked unit / border orthogonally adjacent
        Scorer.GILDED: 0,  # 1/GILDED_DIVISOR of current chips as mult
        Scorer.BOMB: 0,  # detonates after the run (unlock radius, then destroyed)
        Scorer.CLUSTER: 3,  # +3 mult per block orthogonally adjacent to it
        Scorer.COLOSSUS: 0.04,  # +0.04 xMult per px of radius above the base
        Scorer.UNDERTAKER: 30,  # +30 mult per block destroyed this run
        Scorer.DEBT: 60,  # 60 chips per trigger
        Scorer.PACKED: 1,  # 1 inventory slot per touch
    }

    # --- Card magnitudes -----------------------------------------------------
    # What one card unit is worth before a card's ratio scales it. Declared
    # first because the ratios below are measured in these units (a card worth
    # +20 chips a unit has a ratio of 20/30).
    CHIPS_PER_UNIT = 30
    MULT_PER_UNIT = 4
    XMULT_PER_UNIT = 0.25
    # The chipper whole cards' own payoff, in chips a unit: the ratio below is
    # this over CHIPS_PER_UNIT, so the number is typed once.
    TRASH_CAN_CHIPS = 20  # Trash Can: +20 chips per item discarded this run

    # The measured whole cards' per-unit ratio. Each card fires once per run (or
    # once per fragile break) and pays a fixed amount, built by
    # components.magnitude_payoff(scorer, ratio, units): the standard bases above
    # (+30 chips / +4 mult / +0.25 xMult per unit) scaled by the ratio, times the
    # per-run number ``measure`` names (see cards._named_card_units). A whole
    # card has no scorer half to roll, so ``units`` is all that varies: Joker's
    # ratio 1.0 is +4 mult, Plane's 0.5 is +15 chips an air second, Pillar's 0.25
    # is +1 mult a column block, Banker's 1/30 is +1 chip per $10, Ripped Card's
    # 4.0 is +120 chips, Cozy's 3.0 is +90 chips, Painting's 0.1 is +3 chips a
    # dollar, Synthesizer's 0.75 is +3 mult a card and Island's 0.5 is +0.125
    # xMult a group (1 + 0.25 x 0.5 x groups). A match-group card has no ratio
    # here: it pays one standard unit per matching collision and carries its
    # scorer's rolled magnitude instead.
    CARD_RATIOS: ClassVar[dict[int, float]] = {
        Card.JOKER: 1.0,
        Card.EXPLORER: 1.0,
        Card.ASTRONAUT: 1.0,
        Card.PLANE: 0.5,
        Card.PILLAR: 0.25,
        Card.BANKER: 1.0 / 30.0,
        Card.WRECKING_BALL: 0.75,
        Card.SKATER: 0.8,
        Card.GLITCH: 1.0,
        Card.RIPPED_CARD: 4.0,
        Card.COZY: 3.0,
        Card.PAINTING: 0.1,
        Card.SYNTHESIZER: 0.75,
        Card.ISLAND: 0.5,
        Card.FOUNTAIN: 1.0,
        Card.INTANGIBLE: 0.125,
        Card.SWASHBUCKLER: 1.0 / 20.0,
        Card.STENCIL: 4.0,
        Card.CLAUSTROPHOBIA: 0.75,
        Card.MATRIX: 1.5,
        Card.TRASH_CAN: TRASH_CAN_CHIPS / CHIPS_PER_UNIT,
    }

    # --- Passive item magnitudes ---------------------------------------------
    # An UNPLAYABLE item's payoff, in the currency its scorer names: Concrete
    # adds this many chips at the start of every run (see Passive.PAYOFFS).
    CONCRETE_CHIPS = 30

    # --- Tool magnitudes -----------------------------------------------------
    # The stacks of FORGOTTEN one shot of vodka pours into a card (see
    # Tool.MODIFIES and components.Modifier).
    VODKA_FORGOTTEN = 3

    # --- Action magnitudes ---------------------------------------------------
    # The one number an ACTION can carry is its own strength. The Lantern's is
    # the items it draws (see Game._action_lantern), so it is what an upgrade
    # doubles and what a golem doubles again: two Lanterns combined draw twice
    # as many items as one (see Structure.GOLEM).
    LANTERN_DRAWS = 2
    # The three energy-costing actions carry the same kind of number: the cards
    # Eyeball draws out of the deck (the player picks which), and the packs Deep
    # Pockets creates — which is also the structures it destroys — so a golem
    # doubles what one use gives.
    EYEBALL_DRAWS = 1
    DEEP_POCKETS_PACKS = 1
    # The Nasty Cocktail's energy an use, for each modifier on the card (see
    # Game._action_nasty_cocktail).
    COCKTAIL_ENERGY_PER_MODIFIER = 1
    # The Reroll's: the cards it draws out of the deck after it has turned the
    # selected structure into another one (see Game._action_reroll), so a golem
    # doubles the draw with the rest of the card.
    REROLL_DRAWS = 1
    # The Dynamite's: the locked board squares one blast opens (user request:
    # "unlock 10 random board squares"). A golem-folded Dynamite opens twice as
    # many (see Game._action_dynamite).
    DYNAMITE_SQUARES = 10
    # The Horseshoe's: the items it draws ON TOP of the hand it threw back (user
    # request: "draw the same number plus 3 new items"), so a golem-folded one
    # draws two more than it threw away (see Game._action_horseshoe).
    HORSESHOE_EXTRA_DRAWS = 3
    # The Recycling's: the items it draws out of the deck after it has put the
    # selected item back (user request: "draw 2 items"), so a golem-folded one
    # draws two more (see Game._action_recycling).
    RECYCLING_DRAWS = 2
    # The Stormcloud's: the random structures it tears down after opening the one
    # it was aimed at (user request: "destroy 1 random structure"), so a
    # golem-folded one brings down two (see Game._action_stormcloud).
    STORMCLOUD_DESTROYS = 1
    # The Floor plans': the BLOCKS it draws out of the deck (user request: "draw
    # 5 blocks"), so a golem-folded one draws ten (see Game._action_floor_plans).
    FLOOR_PLANS_BLOCKS = 5


    # --- Fixed scorer rewards ------------------------------------------------
    # The scorers that pick among fixed payoffs rather than a rolled amount
    # (their SCORERS entry is 0). Both the block version (main.py) and the card
    # version (cards.py) of each read these.
    QUICK_CHIPS_PER_SPEED = 0.05  # Quick: chips per px/s of the marble's speed
    RANDOM_CHIPS = 35  # Random: one of +chips / +mult / +xMult
    RANDOM_MULT = 5
    RANDOM_XMULT = 0.3
    LUCKY_CHIPS = 130  # Lucky: a 1/3 chance of this many chips ...
    LUCKY_CASH = 40  # ... and a 1/9 chance of this much cash
    GILDED_DIVISOR = 6  # Gilded: 1/6 of the current chips as mult
    GLITCH_MAX_UNITS = 6.0  # Glitch: a random 0..this many units

    # --- Fixed whole-card payoffs --------------------------------------------
    # Cards whose payoff is one fixed number, read where their mechanic lives.
    GATE_PASS_CHIPS = 30  # Gate: per pass through a lock whose key was collected
    ESSENCE_RUN_CASH = 10  # Essence: at the end of every run
    TESSERACT_REROLL_XMULT = 0.1  # Tesseract: permanent xMult per shop reroll
    INFERNO_EXPONENT_BONUS = 0.07  # Inferno: added to the total-score exponent
    ODYSSEY_CASH_FRACTION = 0.5  # Odyssey: fraction of a banked item's sell price
    # Smelly Socks pays BOTH of these at the start of every run (see
    # cards._apply_smelly_socks), and charges for it by handing a card drawn
    # with it back to the deck.
    SMELLY_SOCKS_CHIPS = 15
    SMELLY_SOCKS_MULT = 2
    # The Conquistador whole card hands over this many Board Units after every
    # run (user request: "make conquistador give 4x board square when used").
    # The Drill scorer's own magnitude (SCORERS[Scorer.DRILL] = 2) is the number
    # of units it gives per trigger, so its "2x board square" needs no row here.
    BOARD_UNITS_PER_CONQUISTADOR = 4


# Bind the two average tables back onto the classes they describe, so every
# existing Effect.MAGNITUDE / Scorer.DEFAULT_AMOUNT read comes from the single
# section above.
Effect.MAGNITUDE = MAGNITUDES.EFFECTS
Scorer.DEFAULT_AMOUNT = MAGNITUDES.SCORERS


# The measured whole cards' effects: id -> (phase, scorer, ratio, measure).
#   phase   "start"  -> cards.apply_cards, at the start of every run
#           "end"    -> cards.apply_cards_on_finish, once the run is over
#           "fragile"-> cards.on_fragile_broken, each fragile break
# The ratio is the card's own magnitude and comes from MAGNITUDES.CARD_RATIOS;
# nothing here re-types it.
Card.NAMED = {
    Card.JOKER: ("start", Scorer.MULT_ADD,
                 MAGNITUDES.CARD_RATIOS[Card.JOKER], "start"),
    Card.EXPLORER: ("end", Scorer.MULT_MUL,
                    MAGNITUDES.CARD_RATIOS[Card.EXPLORER], "visited_units"),
    Card.ASTRONAUT: ("end", Scorer.MULT_ADD,
                     MAGNITUDES.CARD_RATIOS[Card.ASTRONAUT], "black_hole"),
    Card.PLANE: ("end", Scorer.CHIPS_ADD,
                 MAGNITUDES.CARD_RATIOS[Card.PLANE], "air_time"),
    Card.PILLAR: ("start", Scorer.MULT_ADD,
                  MAGNITUDES.CARD_RATIOS[Card.PILLAR], "fullest_column"),
    Card.BANKER: ("start", Scorer.CHIPS_ADD,
                  MAGNITUDES.CARD_RATIOS[Card.BANKER], "cash_held"),
    Card.WRECKING_BALL: ("fragile", Scorer.MULT_ADD,
                         MAGNITUDES.CARD_RATIOS[Card.WRECKING_BALL],
                         "fragile_breaks"),
    Card.SKATER: ("end", Scorer.MULT_MUL,
                  MAGNITUDES.CARD_RATIOS[Card.SKATER], "slippery"),
    Card.GLITCH: ("start", Scorer.MULT_ADD,
                  MAGNITUDES.CARD_RATIOS[Card.GLITCH], "random"),
    Card.RIPPED_CARD: ("start", Scorer.CHIPS_ADD,
                       MAGNITUDES.CARD_RATIOS[Card.RIPPED_CARD], "few_blocks"),
    Card.COZY: ("start", Scorer.CHIPS_ADD,
                MAGNITUDES.CARD_RATIOS[Card.COZY], "cozy"),
    Card.PAINTING: ("start", Scorer.CHIPS_ADD,
                    MAGNITUDES.CARD_RATIOS[Card.PAINTING], "painting"),
    Card.SYNTHESIZER: ("start", Scorer.MULT_ADD,
                       MAGNITUDES.CARD_RATIOS[Card.SYNTHESIZER], "synthesizer"),
    # Island is an xMult card, and xMult is a run-end calculation: it pays with
    # the other end cards rather than at the start of the run.
    Card.ISLAND: ("end", Scorer.MULT_MUL,
                  MAGNITUDES.CARD_RATIOS[Card.ISLAND], "island"),
    # The first card here that was never a named condition: its ratio is exactly
    # 1.0, which is what makes one unit +0.25 xMult.
    Card.FOUNTAIN: ("end", Scorer.MULT_MUL,
                    MAGNITUDES.CARD_RATIOS[Card.FOUNTAIN], "pipe_streak"),
    # Intangible pays +0.5 mult an inside second (ratio 0.125 = 4 x 0.125), with
    # a second clause 30x that rate, and the measure it reads is weighted to
    # match: one second inside a locked unit counts as 30 ordinary seconds, so
    # the single ratio serves both (see cards._named_card_units).
    Card.INTANGIBLE: ("end", Scorer.MULT_ADD,
                      MAGNITUDES.CARD_RATIOS[Card.INTANGIBLE], "inside_time"),
    # Swashbuckler pays 1/5 of the cards' sell value as mult (4 x 1/20 x
    # dollars).
    Card.SWASHBUCKLER: ("start", Scorer.MULT_ADD,
                        MAGNITUDES.CARD_RATIOS[Card.SWASHBUCKLER],
                        "card_sell_total"),
    Card.STENCIL: ("start", Scorer.MULT_MUL,
                   MAGNITUDES.CARD_RATIOS[Card.STENCIL], "stencil_slots"),
    Card.CLAUSTROPHOBIA: ("start", Scorer.MULT_ADD,
                          MAGNITUDES.CARD_RATIOS[Card.CLAUSTROPHOBIA],
                          "plain_rects"),
    # Matrix is Intangible's locked-unit clause on its own, paying chips: ratio
    # 1.5 x 30 = the +45 chips a second the card asks for, counting only the
    # seconds the marble was NOT phasing (see Game._count_locked_no_phase_time).
    Card.MATRIX: ("end", Scorer.CHIPS_ADD,
                  MAGNITUDES.CARD_RATIOS[Card.MATRIX], "inside_locked_no_phase"),
    # Trash Can pays its own magnitude a unit for what the run threw away, read
    # at the end because discards happen all run long (see Game._discard_item).
    Card.TRASH_CAN: ("end", Scorer.CHIPS_ADD,
                     MAGNITUDES.CARD_RATIOS[Card.TRASH_CAN], "items_discarded"),
}

# Trash Can's catalogue line is generated from its magnitude, exactly as the
# Lantern's is from its own: the per-item chip count is typed once, in
# MAGNITUDES.TRASH_CAN_CHIPS, and this reads it back (the same arithmetic
# magnitude_payoff uses for a chips card).
Card.DESCRIPTIONS[Card.TRASH_CAN] = (
    f"Adds {int(MAGNITUDES.CHIPS_PER_UNIT * MAGNITUDES.CARD_RATIOS[Card.TRASH_CAN] + 0.5)} "
    f"chips at the end of the run for each item you discarded this run")

# Smelly Socks states both of its numbers from the one place they live too: the
# chip bonus, the mult bonus, and what it charges for them.
Card.DESCRIPTIONS[Card.SMELLY_SOCKS] = (
    f"Adds {MAGNITUDES.SMELLY_SOCKS_CHIPS:g} chips and "
    f"{MAGNITUDES.SMELLY_SOCKS_MULT:g} mult at the start of the run, but a "
    f"random card drawn with it goes back into the deck (unplayable)")


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
    EXPANSION = 7
    BRAINSTORM = 8
    MASS_PRODUCTION = 9
    GRACE = 10
    # The two newest actions. Inaction is the joke that pays: it does nothing,
    # but every few of them used wins a card slot (see main.INACTION_USES_PER_SLOT).
    # Foresight is the dear one: a permanent extra action slot.
    INACTION = 11
    FORESIGHT = 12
    # Cleansing never reaches the shelf on its own: it comes out of a crystal
    # pool (see Structure.RESULTS).
    CLEANSING = 13
    # The Lantern is the first action whose strength is a NUMBER (see
    # MAGNITUDES.ACTIONS): it draws its own magnitude in items from the deck and
    # then discards itself, so a golem combining two of them draws twice as
    # many (see Structure.GOLEM).
    LANTERN = 14
    # The three newest actions. Each costs energy from the run's own budget
    # (Action.ENERGY), which is what the four tools spend — an action that asks
    # for energy is a card you pay to play rather than a free one-shot.
    EYEBALL = 15       # 1 energy: draw the cards YOU pick out of your deck
    DEEP_POCKETS = 16  # 1 energy: a random pack, for a random structure
    NASTY_COCKTAIL = 17  # 0 energy: energy for each modifier it carries
    # The Reroll is what a reroll IS now that the shop has no refresh button
    # (see Fresh and Brainstorm, which deal this card instead of banking free
    # rerolls): 0 energy to point at a structure and turn it into another one,
    # then discard itself and draw a card (see Game._action_reroll).
    REROLL = 18
    # The Dynamite is the one card that both opens the BOARD and opens a
    # structure: used with nothing selected it blasts DYNAMITE_SQUARES random
    # locked squares open; used on a structure it digs or reveals it (user
    # request: "add a card, 'dynamite': when used with no items selected, unlock
    # 10 random board squares adjacent to the unlocked area this card was used
    # in. or, dig or reveal. costs 2 energy."). It is the one action that takes
    # a structure (see STRUCTURE_TARGET) without requiring one (OPTIONAL_TARGET).
    DYNAMITE = 19
    # The Horseshoe is the deck's own card (user request: "add a card:
    # 'horseshoe' (discard all items on the board that you own, draw the same
    # number plus 3 new items. costs 1 energy)"): it throws the hand back into
    # the deck and draws a bigger one, so it is a draw rather than a target —
    # no items selected, just S (see Game._action_horseshoe).
    HORSESHOE = 20
    # The Recycling takes ONE item (user request: "add a card, 'recycling'
    # (discard selected item, draw 2 items for 0 energy)"), so unlike the
    # Horseshoe it is aimed at the item it recycles. What it discards goes back
    # into the deck — the answer the Horseshoe's discard gave is the rule for
    # every discard that is not the card being used (see Game._to_deck) — and
    # the two draws come out of the same deck (see Game._action_recycling).
    RECYCLING = 21
    # The Stormcloud is the one action with a TOOL's reach (user request: "add a
    # card, 'stormcloud' (break, fix, dig, or reveal, and destroy 1 random
    # structure. costs 1 energy)"): it is aimed at a structure and opens it with
    # whichever of the four verbs it answers, then tears down one random other
    # structure on its way (see Game._action_stormcloud).
    STORMCLOUD = 22
    # The Floor plans is the deck's block card (user request: "add a new card,
    # 'floor plans' (draw 5 blocks. costs 1 energy)"): it draws BLOCKS — the
    # ready-made ones waiting in the deck, not cards or parts — so a run can be
    # built from what it deals (see Game._action_floor_plans).
    FLOOR_PLANS = 23

    NAMES: ClassVar[dict[int, str]] = {
        DEATH: "Death",
        RECOGNITION: "Recognition",
        DEJA_VU: "Deja Vu",
        ANOINTMENT: "Anointment",
        STRENGTH: "Strength",
        SPIRIT: "Spirit",
        CLEANSWEEP: "Cleansweep",
        EXPANSION: "Expansion",
        BRAINSTORM: "Brainstorm",
        MASS_PRODUCTION: "Mass production",
        GRACE: "Grace",
        INACTION: "Inaction",
        FORESIGHT: "Foresight",
        CLEANSING: "Cleansing",
        LANTERN: "Lantern",
        EYEBALL: "Eyeball",
        DEEP_POCKETS: "Deep Pockets",
        NASTY_COCKTAIL: "Nasty Cocktail",
        REROLL: "Reroll",
        DYNAMITE: "Dynamite",
        HORSESHOE: "Horseshoe",
        RECYCLING: "Recycling",
        STORMCLOUD: "Stormcloud",
        FLOOR_PLANS: "Floor plans",
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
        EXPANSION: "Gives 4 Board Units — each opens one locked board square you pick (v2: unlocks the whole board instead).",
        BRAINSTORM: "Creates 2 Reroll cards (v2: creates 4).",
        MASS_PRODUCTION: "Triples the resource points this run earns (v2: doubles them for the "
                         "rest of the game).",
        GRACE: "Adds +1 xMult to this run (v2: this run's required score drops to 0).",
        INACTION: "...does nothing?",
        FORESIGHT: "Permanently adds 1 action slot (v2: no limit at all).",
        CLEANSING: "Multiplies a chosen block, effect or scorer\u2019s magnitude by 1.5.",
        # The Lantern states its own magnitude, so its line is built from it
        # (see Action.MAGNITUDE_TEXT and Action.description).
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
        EXPANSION: "Unlocks every locked board square.",
        BRAINSTORM: "Creates 4 Reroll cards.",
        MASS_PRODUCTION: "Doubles every resource point you earn, for the rest of the game.",
        GRACE: "This run's required score becomes 0: it is cleared whatever it scores.",
        INACTION: "...does nothing, and hands over a card slot.",
        FORESIGHT: "Removes the limit on owned actions: hold as many as you like.",
        CLEANSING: "Multiplies a chosen block, effect or scorer\u2019s magnitude by 2.5.",
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
        EXPANSION: "Room to grow.",
        BRAINSTORM: "Fresh ideas on demand.",
        MASS_PRODUCTION: "Make more of less.",
        GRACE: "This one's on the house.",
        INACTION: "Doing nothing, deliberately.",
        FORESIGHT: "See what is coming.",
        CLEANSING: "Washed clean.",
        LANTERN: "Light the way.",
        EYEBALL: "I've got my eye on you.",
        DEEP_POCKETS: "There's more where that came from.",
        NASTY_COCKTAIL: "Shaken, not stirred.",
        REROLL: "Roll the bones.",
        DYNAMITE: "Fire in the hole.",
        HORSESHOE: "Lucky for some.",
        RECYCLING: "Reduce, reuse, redraw.",
        STORMCLOUD: "Thunder and lightning.",
        FLOOR_PLANS: "Something to build from.",
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
                                        CLEANSWEEP: 70, EXPANSION: 25, BRAINSTORM: 25,
                                        MASS_PRODUCTION: 36, GRACE: 25,
                                        # Inaction is priced like the cheap
                                        # actions even though five of them buy a
                                        # card slot (five at $24 is $120 a
                                        # slot). Foresight is the dearest
                                        # action in the catalogue by a mile: it
                                        # is the only one that widens the
                                        # action area itself, for good.
                                        INACTION: 24, FORESIGHT: 90,
                                        # Cleansing is not sold: a pool
                                        # holds it. Its price is only what a
                                        # structure holding one is worth.
                                        CLEANSING: 30,
                                        # The Lantern buys cards off the top of
                                        # the deck, so it is priced with the
                                        # cheap actions.
                                        LANTERN: 26,
                                        # Eyeball is the Lantern's better half:
                                        # it lets the player PICK which card
                                        # comes out of the deck, so it costs a
                                        # little more. Deep Pockets hands over a
                                        # whole random pack and charges a
                                        # structure for it, which is worth more
                                        # than any other action on the shelf,
                                        # and the Nasty Cocktail does nothing at
                                        # all until it has been modified.
                                        EYEBALL: 28, DEEP_POCKETS: 40,
                                        NASTY_COCKTAIL: 20,
                                        # The Reroll is a level's furniture in
                                        # another shape plus a card, so it sits
                                        # with the cheap actions.
                                        REROLL: 26,
                                        # Dynamite buys ten board squares in one
                                        # go (or opens a structure), which is
                                        # worth more than any other action that
                                        # does one thing.
                                        DYNAMITE: 38,
                                        # The Horseshoe is a hand refresh plus
                                        # three items, so it is priced with the
                                        # deck's own cards: Eyeball draws one
                                        # card of the player's choice for $28,
                                        # and this draws three nobody chose.
                                        HORSESHOE: 36,
                                        # Recycling costs nothing to use but
                                        # the card itself, and it draws two
                                        # without losing anything (the item it
                                        # recycles goes back in the deck), so
                                        # it is priced as a Rare.
                                        RECYCLING: 42,
                                        # The Stormcloud opens a structure and
                                        # then tears another one down without
                                        # opening it, so it buys a reward with a
                                        # structure the player loses: priced
                                        # with the cheap actions.
                                        STORMCLOUD: 34,
                                        # The Floor plans deals five blocks, and
                                        # blocks are what a run is BUILT from,
                                        # so it is the dearest of the actions
                                        # that reach into the deck.
                                        FLOOR_PLANS: 46}
    # Face colors and center glyphs for the mini-action look (one per action).
    COLORS: ClassVar[dict[int, tuple]] = {
        DEATH: (120, 45, 45),        # deathly red
        RECOGNITION: (60, 100, 180), # recognition blue
        DEJA_VU: (105, 65, 150),     # dizzy violet
        ANOINTMENT: (35, 125, 95),   # blessed emerald
        STRENGTH: (175, 85, 35),     # brawny amber
        SPIRIT: (140, 140, 160),     # spectral grey
        CLEANSWEEP: (40, 140, 160),  # sweeping teal
        EXPANSION: (110, 150, 55),   # survey green
        BRAINSTORM: (205, 165, 45),  # idea gold
        MASS_PRODUCTION: (170, 60, 130),  # industry magenta
        GRACE: (150, 200, 225),      # halo sky
        INACTION: (135, 140, 150),   # empty grey
        FORESIGHT: (85, 75, 165),    # vision indigo
        CLEANSING: (95, 175, 170),   # clear water
        LANTERN: (210, 175, 80),     # lamplight
        EYEBALL: (196, 168, 160),    # an eyeball's white
        DEEP_POCKETS: (130, 96, 62), # a deep coat's brown
        NASTY_COCKTAIL: (205, 90, 155),  # a bright, doubtful drink
        REROLL: (90, 160, 110),      # a fresh green roll
        DYNAMITE: (196, 72, 58),     # a warning red
        HORSESHOE: (168, 124, 52),   # lucky brass
        RECYCLING: (58, 132, 92),    # recycled green
        STORMCLOUD: (74, 84, 112),   # a storm's slate
        FLOOR_PLANS: (38, 92, 124), # drafting blue
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        DEATH: "D", RECOGNITION: "R", DEJA_VU: "V",
        ANOINTMENT: "A", STRENGTH: "S", SPIRIT: "P",
        CLEANSWEEP: "C", EXPANSION: "E", BRAINSTORM: "B",
        MASS_PRODUCTION: "M", GRACE: "G",
        INACTION: "?", FORESIGHT: "F",
        CLEANSING: "L",
        LANTERN: "N",
        EYEBALL: "Y", DEEP_POCKETS: "K", NASTY_COCKTAIL: "X",
        REROLL: "\u21bb", DYNAMITE: "Z",
        HORSESHOE: "U",
        RECYCLING: "O",
        STORMCLOUD: "W",
        FLOOR_PLANS: "Q",
    }
    ORDER: ClassVar[list[int]] = [DEATH, RECOGNITION, DEJA_VU, ANOINTMENT,
                                  STRENGTH, SPIRIT, CLEANSWEEP, EXPANSION,
                                  BRAINSTORM, MASS_PRODUCTION, GRACE,
                                  INACTION, FORESIGHT, CLEANSING, LANTERN,
                                  EYEBALL, DEEP_POCKETS, NASTY_COCKTAIL,
                                  REROLL, DYNAMITE, HORSESHOE, RECYCLING,
                                  STORMCLOUD, FLOOR_PLANS]
    # Actions that act on the game itself rather than on a chosen block or card:
    # they need no subject, so selecting one and pressing S uses it straight
    # away (see Game._apply_action). Eyeball takes its subject from the DECK
    # overlay (see Game._pick_deck_card), Deep Pockets and the Nasty Cocktail
    # act on the game at once.
    NO_TARGET: ClassVar[tuple[int, ...]] = (CLEANSWEEP, EXPANSION, BRAINSTORM,
                                            MASS_PRODUCTION, GRACE, INACTION,
                                            FORESIGHT, LANTERN, EYEBALL,
                                            DEEP_POCKETS, NASTY_COCKTAIL,
                                            HORSESHOE, FLOOR_PLANS)
    # The actions aimed at a STRUCTURE instead of at a block or a card (see
    # Game.is_action_target): a reroll is pointed at the level's own furniture,
    # and Dynamite into a structure to dig or reveal it. Every other action
    # still refuses a structure, which is why the target kind is a table rather
    # than a widening of what an action may be aimed at.
    STRUCTURE_TARGET: ClassVar[tuple[int, ...]] = (REROLL, DYNAMITE,
                                                   STORMCLOUD)
    # The actions that take a structure if there is one, and act on the game
    # itself if there is not (user request: Dynamite unlocks squares "when used
    # with no items selected. or, dig or reveal"). Such an action accepts no
    # target or exactly one; its own handler decides what either means.
    OPTIONAL_TARGET: ClassVar[tuple[int, ...]] = (DYNAMITE,)
    # The actions that may be aimed at ANY of the player's items rather than at a
    # block, a card or a part (see Game.is_action_target): the Recycling takes
    # whatever the player wants to put back in the deck — a tool, a passive, a
    # whole card, a component. An action is never a target, here or anywhere.
    ANY_TARGET: ClassVar[tuple[int, ...]] = (RECYCLING,)
    # The actions that OPEN a structure, and the verbs each one brings (see
    # Game._action_dynamite / _action_stormcloud). A table rather than a tuple
    # in each handler, so the structure's own "Opened by" row is built from the
    # same words the handlers use and can never leave a way in out. It is bound
    # under the class once the Verb table exists (Verb is declared below).
    OPENS: ClassVar[dict[int, tuple]] = {}
    # What using an action costs from the run's ENERGY budget (see
    # Game._apply_action). Actions are one-shot items, so most cost nothing —
    # an action that is still in the table asks for energy on top of itself,
    # and that is the only place the number lives.
    ENERGY: ClassVar[dict[int, int]] = {
        EYEBALL: 1,
        DEEP_POCKETS: 1,
        NASTY_COCKTAIL: 0,   # costs nothing to pour, and gives energy back
        REROLL: 0,           # user request: "(0 energy)"
        DYNAMITE: 2,         # user request: "costs 2 energy"
        HORSESHOE: 1,        # user request: "costs 1 energy"
        RECYCLING: 0,        # user request: "for 0 energy"
        STORMCLOUD: 1,       # user request: "costs 1 energy"
        FLOOR_PLANS: 1,      # user request: "costs 1 energy"
    }
    # The actions whose text states their own MAGNITUDE, as a template for
    # Action.description: the number comes from the item (a merged Lantern
    # describes itself as drawing four), never from this table.
    MAGNITUDE_TEXT: ClassVar[dict[int, str]] = {
        LANTERN: "Draws {amount} item{s} from the deck, then discards this card.",
        EYEBALL: ("Draws {amount} card{s} of your choice from the deck "
                  "({energy} energy)."),
        DEEP_POCKETS: ("Creates {amount} random pack{s} and destroys {amount} "
                       "random structure{s} ({energy} energy)."),
        NASTY_COCKTAIL: ("Gains {amount} energy for each modifier on this "
                         "card ({energy} energy)."),
        REROLL: ("Turns the selected structure into another random one, "
                 "discards this card and draws {amount} card{s} "
                 "({energy} energy)."),
        DYNAMITE: ("With nothing selected, opens {amount} random board squares. "
                   "Or digs or reveals a structure ({energy} energy)."),
        HORSESHOE: ("Discards every item you own on the board back into the "
                    "deck, then draws that many plus {amount} "
                    "({energy} energy)."),
        RECYCLING: ("Puts the selected item back into the deck, then draws "
                    "{amount} item{s} ({energy} energy)."),
        STORMCLOUD: ("Breaks, fixes, digs or reveals the selected structure, and "
                     "destroys {amount} other random structure{s} "
                     "({energy} energy)."),
        FLOOR_PLANS: ("Draws {amount} block{s} out of the deck "
                      "({energy} energy)."),
    }

    @classmethod
    def name(cls, action):
        return cls.NAMES.get(action, "Unknown")

    @classmethod
    def description(cls, action, version=1, amount=None):
        """The action's effect text for the given version (v2 is stronger).

        ``amount`` is the action's own magnitude when it carries one (see
        MAGNITUDES.ACTIONS): the Lantern reads the number IT will draw, so a
        Lantern a golem doubled says four rather than the catalogue's two. An
        action with no magnitude, or none given, describes its catalogue entry.
        """
        template = cls.MAGNITUDE_TEXT.get(action)
        if template is not None:
            if not amount:
                amount = cls.MAGNITUDE.get(action, 0)
            return template.format(amount=f"{amount:g}",
                                   s="" if amount == 1 else "s",
                                   energy=cls.energy(action))
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
    def targets_structures(cls, action):
        """True when the action is aimed at a structure (see STRUCTURE_TARGET).

        Everything else is aimed at a block or a card: the target KIND is what
        Game.is_action_target asks about, so an action can never be pointed at
        something its handler would refuse.
        """
        return action in cls.STRUCTURE_TARGET

    @classmethod
    def optional_target(cls, action):
        """True when the action takes a structure OR nothing (see OPTIONAL_TARGET).

        Such an action is used bare to act on the board and pointed at a
        structure to act on that instead, so Game._apply_action accepts no
        target or exactly one — never two.
        """
        return action in cls.OPTIONAL_TARGET

    @classmethod
    def targets_anything(cls, action):
        """True when the action takes ANY item as its target (see ANY_TARGET).

        Every other action is aimed at one kind of thing — a structure, a block,
        a card, a part — so its handler can name what it refuses. An action that
        acts on an item for its own sake (the Recycling) takes whatever the
        player points at, and Game.is_action_target asks this instead.
        """
        return action in cls.ANY_TARGET

    @classmethod
    def opens_with(cls, action):
        """The verbs an action opens a structure with (see OPENS).

        The empty tuple for an action that opens nothing, so a caller can ask
        without knowing which actions the table covers.
        """
        return cls.OPENS.get(action, ())

    @classmethod
    def energy(cls, action):
        """What USING this action costs from the run's energy (0 for most).

        Energy is the run's budget (see MAX_ENERGY): the four tools spend it to
        open structures, and the three newest actions ask for it too (see
        Game._apply_action). An action missing from the table costs nothing,
        which is every action before them: once used, an action is gone.
        """
        return cls.ENERGY.get(action, 0)

    @classmethod
    def cycle(cls, action):
        idx = cls.ORDER.index(action) if action in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


# Bind the action magnitudes back onto the class, exactly as the effect and
# scorer tables are bound above: an action's number is the ONE place its
# strength lives, so an upgrade or a golem changes the number and nothing else
# has to know what it means. The Lantern's catalogue line is generated from it
# too, so the number is typed once (MAGNITUDES.LANTERN_DRAWS). The three
# energy-costing actions' lines are generated the same way, from the number of
# cards/packs/energy they carry and from Action.ENERGY.
Action.MAGNITUDE = {
    Action.LANTERN: MAGNITUDES.LANTERN_DRAWS,
    Action.EYEBALL: MAGNITUDES.EYEBALL_DRAWS,
    Action.DEEP_POCKETS: MAGNITUDES.DEEP_POCKETS_PACKS,
    Action.NASTY_COCKTAIL: MAGNITUDES.COCKTAIL_ENERGY_PER_MODIFIER,
    Action.REROLL: MAGNITUDES.REROLL_DRAWS,
    Action.DYNAMITE: MAGNITUDES.DYNAMITE_SQUARES,
    Action.HORSESHOE: MAGNITUDES.HORSESHOE_EXTRA_DRAWS,
    Action.RECYCLING: MAGNITUDES.RECYCLING_DRAWS,
    Action.STORMCLOUD: MAGNITUDES.STORMCLOUD_DESTROYS,
    Action.FLOOR_PLANS: MAGNITUDES.FLOOR_PLANS_BLOCKS,
}
Action.DESCRIPTIONS[Action.LANTERN] = Action.description(Action.LANTERN)
Action.DESCRIPTIONS[Action.EYEBALL] = Action.description(Action.EYEBALL)
Action.DESCRIPTIONS[Action.DEEP_POCKETS] = Action.description(Action.DEEP_POCKETS)
Action.DESCRIPTIONS[Action.NASTY_COCKTAIL] = Action.description(
    Action.NASTY_COCKTAIL)
Action.DESCRIPTIONS[Action.REROLL] = Action.description(Action.REROLL)
Action.DESCRIPTIONS[Action.DYNAMITE] = Action.description(Action.DYNAMITE)
Action.DESCRIPTIONS[Action.HORSESHOE] = Action.description(Action.HORSESHOE)
Action.DESCRIPTIONS[Action.RECYCLING] = Action.description(Action.RECYCLING)
Action.DESCRIPTIONS[Action.STORMCLOUD] = Action.description(Action.STORMCLOUD)
Action.DESCRIPTIONS[Action.FLOOR_PLANS] = Action.description(Action.FLOOR_PLANS)
# Tesseract's line states its own number too, so it is built from MAGNITUDES
# instead of typing the same figure in two places.
Card.DESCRIPTIONS[Card.TESSERACT] = (
    f"Every Reroll card you use permanently adds "
    f"+{MAGNITUDES.TESSERACT_REROLL_XMULT:g} xMult, applied at the start of "
    "each run")


# The rate a resource pack pays an option at: twice what a trigger of the
# scorer would bank, so a Picky option at its default magnitude (0.5 of a
# point) is worth one whole structure point.
RESOURCE_PACK_FACTOR = 2.0


class Pack:
    """An item pack: a bundle of offers the player buys and keeps part of.

    A pack is a shelf offer like a component or a card, except that what it
    hands over is a CHOICE: buying one opens it, the player is shown the
    options its size deals out (see SIZE_OPTIONS), and keeps SIZE_KEEP of them.
    A pack's TYPE says what its options are — a shape pack offers shapes, a
    card pack offers cards, a part pack offers any component part (shape,
    effect or scorer, the pieces a block is assembled from), and a RANDOM pack
    offers anything any other pack might, mixed.

    Two rules cut across the types:
    * an ACTION found in an action pack is USED rather than shelved: the pack
      hands it over to be fired at once, so it never takes an action-area slot
      (a targeted action is armed for its target instead — see
      main.Game._keep_pack_action). An action found in a RANDOM pack is not a
      pack action: it goes into the action area like any other;
    * a RESOURCE pack offers resource points rather than items, each worth
      RESOURCE_PACK_FACTOR times what a trigger of that scorer banks, rolled at
      that scorer's own magnitude — so a Picky option at its default magnitude
      is worth 2 x 0.5 = 1 structure point.
    """
    SHAPE = 0
    EFFECT = 1
    SCORER = 2
    PART = 3
    BLOCK = 4
    CARD = 5
    ACTION = 6
    RESOURCE = 7
    RANDOM = 8
    # The one-shot tools and the passive items (user request: the brick, the
    # match and concrete): a pack is where they are found, so a level's
    # structures can hand over something to use up.
    TOOL = 9

    NAMES: ClassVar[dict[int, str]] = {
        SHAPE: "Shape Pack",
        EFFECT: "Effect Pack",
        SCORER: "Scorer Pack",
        PART: "Part Pack",
        BLOCK: "Block Pack",
        CARD: "Card Pack",
        ACTION: "Action Pack",
        RESOURCE: "Resource Pack",
        RANDOM: "Random Pack",
        TOOL: "Tool Pack",
    }
    # What a pack of this type offers. Shown in the sidebar and in the codex.
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        SHAPE: "A choice of shapes to assemble into blocks.",
        EFFECT: "A choice of effects, each at its own rolled strength.",
        SCORER: "A choice of scorers, each at its own rolled amount.",
        PART: "A choice of parts: shapes, effects and scorers mixed.",
        BLOCK: "A choice of ready-made blocks.",
        CARD: "A choice of cards.",
        ACTION: "A choice of actions, used as soon as one is kept (they never "
                "take an action slot).",
        RESOURCE: f"A choice of resource points: each option is worth "
                  f"{RESOURCE_PACK_FACTOR:g}x what a trigger of that scorer "
                  f"banks.",
        RANDOM: "A choice of anything another pack might hold, mixed.",
        TOOL: "A choice of one-shot tools and passive items.",
    }
    # The five sizes, as (options dealt, options kept). A bigger pack deals out
    # more options, and mega and giga let the player keep a second one.
    NORMAL = 0
    BIG = 1
    JUMBO = 2
    MEGA = 3
    GIGA = 4

    SIZE_NAMES: ClassVar[dict[int, str]] = {
        NORMAL: "Normal", BIG: "Big", JUMBO: "Jumbo", MEGA: "Mega", GIGA: "Giga",
    }
    SIZE_OPTIONS: ClassVar[dict[int, int]] = {
        NORMAL: 3, BIG: 4, JUMBO: 5, MEGA: 5, GIGA: 6,
    }
    SIZE_KEEP: ClassVar[dict[int, int]] = {
        NORMAL: 1, BIG: 1, JUMBO: 1, MEGA: 2, GIGA: 2,
    }
    SIZE_ORDER: ClassVar[list[int]] = [NORMAL, BIG, JUMBO, MEGA, GIGA]
    # What a size multiplies the pack's price by (see main.pack_price). The
    # baseline is one option's own value, and the multiplier is where the
    # CHOICE lives: a normal pack charges for one option while handing out the
    # best of three, and each size up charges a little more for a better pick
    # (and, from mega on, for a second one) without ever reaching what that
    # many loose purchases would cost.
    SIZE_PRICE_FACTORS: ClassVar[dict[int, float]] = {
        NORMAL: 1.0, BIG: 1.35, JUMBO: 1.7, MEGA: 2.5, GIGA: 3.1,
    }
    # Face colours and fallback glyphs for the pack tiles (one per type).
    COLORS: ClassVar[dict[int, tuple]] = {
        SHAPE: (90, 140, 200),    # blueprint blue
        EFFECT: (160, 90, 190),   # effect violet
        SCORER: (200, 140, 60),   # scoring amber
        PART: (110, 170, 120),    # assembly green
        BLOCK: (150, 110, 90),    # built-block brown
        CARD: (190, 70, 110),     # card magenta
        ACTION: (70, 150, 160),   # action teal
        RESOURCE: (170, 170, 70),  # resource ochre
        RANDOM: (120, 120, 130),  # anything grey
        TOOL: (140, 156, 172),    # a working tool's steel
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        SHAPE: "S", EFFECT: "E", SCORER: "C", PART: "P", BLOCK: "B",
        CARD: "D", ACTION: "A", RESOURCE: "R", RANDOM: "?", TOOL: "T",
    }
    ORDER: ClassVar[list[int]] = [SHAPE, EFFECT, SCORER, PART, BLOCK, CARD,
                                  ACTION, RESOURCE, RANDOM, TOOL]
    # How rare each pack type is (see Rarity). The tier follows what the type
    # hands over, not the price (which moves with the pack's SIZE): the packs of
    # loose PARTS and points are the ordinary goods, the ones that deal finished
    # items are dearer, and the random pack — which can hold anything any other
    # pack can — is the one Epic.
    RARITIES: ClassVar[dict[int, int]] = {
        SHAPE: Rarity.COMMON, PART: Rarity.COMMON, RESOURCE: Rarity.COMMON,
        EFFECT: Rarity.UNUSUAL, SCORER: Rarity.UNUSUAL, BLOCK: Rarity.UNUSUAL,
        TOOL: Rarity.UNUSUAL,
        CARD: Rarity.RARE, ACTION: Rarity.RARE,
        RANDOM: Rarity.EPIC,
    }
    # The types a RANDOM pack draws from, and the ones a PART pack draws from.
    # A random pack offers anything another pack might, so it includes the
    # resource points; the two "meta" types (part and random) are never an
    # option's own type.
    RANDOM_SOURCES: ClassVar[tuple] = (SHAPE, EFFECT, SCORER, BLOCK, CARD,
                                       ACTION, RESOURCE, TOOL)
    PART_SOURCES: ClassVar[tuple] = (SHAPE, EFFECT, SCORER)

    @classmethod
    def name(cls, pack_type):
        return cls.NAMES.get(pack_type, "Unknown Pack")

    @classmethod
    def description(cls, pack_type):
        return cls.DESCRIPTIONS.get(pack_type, "Unknown pack.")

    @classmethod
    def size_name(cls, size):
        return cls.SIZE_NAMES.get(size, "Normal")

    @classmethod
    def options(cls, size):
        """How many options a pack of this size deals out."""
        return cls.SIZE_OPTIONS.get(size, 3)

    @classmethod
    def keep(cls, size):
        """How many of them the player keeps."""
        return cls.SIZE_KEEP.get(size, 1)

    @classmethod
    def size_description(cls, size):
        """The one-line rule of a size, e.g. "keep 2 of 5"."""
        return f"keep {cls.keep(size)} of {cls.options(size)}"

    @classmethod
    def color(cls, pack_type):
        return cls.COLORS.get(pack_type, (120, 120, 130))

    @classmethod
    def rarity(cls, pack_type):
        """How rare a pack of this type is (see RARITIES); Common if no row.

        A pack is priced by its SIZE (see SIZE_PRICE_FACTORS), so its tier is
        not its price's: it follows what the type HANDS OVER, the same way a
        structure's does.
        """
        return cls.RARITIES.get(pack_type, Rarity.COMMON)

    @classmethod
    def glyph(cls, pack_type):
        return cls.GLYPHS.get(pack_type, "?")


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
    small fraction's grid: a Rubble trigger banks 1 point at the average
    (1 x 1), 1.1 one step up, 1.4 four steps up — and a Picky roll of 1.1
    banks 0.55, half a step above its own average. A fraction with a small
    denominator states those dishonestly (limit_denominator(6) reads 1.1/3 as
    "1 1/6"), and the deviation printed next to the count has to add up with
    it. Three places is finer than the smallest step (a tenth of a point) and
    absorbs float noise from a bank that has been added up over many triggers.
    """
    return f"{round(points, 3):g}"


def resource_points_for(scorer, amount):
    """The resource points ONE trigger of a scorer banks, at its own magnitude.

    A trigger banks its magnitude times its scorer's rate — a point a unit
    for Shreds, Rubble and Ideas, half a point a unit for Picky (see
    Scorer.RESOURCE_RATE) — and one whole point converts into that scorer's
    reward (see RESOURCE_THRESHOLD). So an average Rubble block banks a point a
    trigger and a rolled 1.4 banks 1.4.
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
        Shape.LOCK: "A solid locked door: it blocks marbles until one passes "
                    "through the matching Key block.",
    }.get(shape, "Unknown shape.")


def effect_description(effect, magnitude=None):
    """A one-line description of what an effect does to the marble.

    A scalable effect (Piston, Accelerator, Black Hole, ...) also says its own
    magnitude and how far that sits from the average (see effect_magnitude_note);
    the average itself is shown when no magnitude is given. Wasteful is the one
    effect that never touches the marble: it says how the PLAYER uses the block
    instead (see Game._use_wasteful).
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
        Effect.PORTAL: "Teleports marbles to its matching numbered portal, up to "
                       "100 times per run.",
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
        Effect.GONDOLA: f"Slides at {magnitude:g} px/s along its arrow (up/down or "
                        "left/right), turning back at anything solid.",
        # Wasteful is the one effect that does nothing to the marble: it is an
        # ability the PLAYER uses while building (see Game._use_wasteful).
        Effect.WASTEFUL: "Select it and one other item, then press S to throw both "
                         "away and draw a new item from the deck",
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
        Scorer.RANDOM: f"When touched, gives +{MAGNITUDES.RANDOM_CHIPS} chips, "
                       f"+{MAGNITUDES.RANDOM_MULT:g} mult, or "
                       f"+{MAGNITUDES.RANDOM_XMULT:g} xMult at random.",
        Scorer.EFFECTIVE: f"Gives +{amount - 1:g} xMult{dev} when touched if its block "
                          "has 2 or more effects",
        Scorer.FRESH: f"Gives {amount:g} Reroll card{_plural(amount)}{dev} when touched",
        Scorer.PICKY: f"Gives {points_text(resource_points_for(Scorer.PICKY, amount))} "
                      f"structure point{_plural_points(resource_points_for(Scorer.PICKY, amount))}"
                      f"{pdev}. 1 point adds a permanent structure to every run",
        Scorer.VOYAGER: f"Gives +{amount:g} mult{dev} for each pixel the marble traveled before touching it",
        Scorer.SATANIC: f"Multiplies the multiplier by {amount:g}{dev} when touched, then is "
                        "permanently destroyed once a marble leaves it.",
        Scorer.SUMMIT: f"Gives +{amount:g} mult{dev} for each unit above the bottom row it is located on",
        Scorer.AIRBALL: f"Gives +{amount:g} mult{dev} for each second the marble was airborne before touching it",
        Scorer.SEED: f"Gives +{amount:g} mult{dev} for each Seed block on the board when touched",
        Scorer.DRILL: f"When touched, gives {amount:g} Board Unit{_plural(amount)}"
                      f"{dev} after the run — each opens one locked square you pick",
        Scorer.PACKED: f"When touched, gives {amount:g} inventory slot{_plural(amount)}"
                       f"{dev} to carry more items, for good",
        Scorer.LUCKY: f"When touched, has a 1/3 chance to give {MAGNITUDES.LUCKY_CHIPS} chips "
                      f"and a 1/9 chance to give ${MAGNITUDES.LUCKY_CASH} (both can land).",
        Scorer.ROOMY: f"Gives +{amount:g} chips{dev} for each unlocked board unit when touched",
        Scorer.RALLY: f"Gives +{amount:g} mult{dev} for each fresh block touch this run before it — re-touches count, its own touch doesn't",
        Scorer.ECHO: "Re-fires the scoring effect of the block the marble touched right before it.",
        Scorer.POWERLINE: f"Gives +{amount:g} chips{dev} for each block in its row (including itself)",
        Scorer.FRONTIER: f"Gives +{amount:g} mult{dev} for each locked unit or board border adjacent to it (not diagonal)",
        Scorer.GILDED: f"Gives 1/{MAGNITUDES.GILDED_DIVISOR:g} of your current chips as mult when touched.",
        Scorer.BOMB: "When touched, unlocks every board unit within 1 cell (including diagonally) after a run, then destroys itself.",
        Scorer.CLUSTER: f"Gives +{amount:g} mult{dev} for each block adjacent to it (up/down/left/right, not diagonally)",
        Scorer.COLOSSUS: f"Gives +{amount:g} xMult{dev} for each pixel the marble's radius is above its "
                         "base size (8 px) when touched",
        Scorer.UNDERTAKER: f"Gives +{amount:g} mult{dev} for each block destroyed this run before touching it",
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


class Verb:
    """What a TOOL does to a STRUCTURE (see Structure / Tool).

    A verb is a small, reusable word: a tool CARRIES one (a shovel digs), and a
    structure answers to the verbs it can be opened with. Nothing else in the
    game knows the words — the structure table (see Structure.RESULTS) is the
    one place a verb meets a result.
    """
    DIG = 0
    REVEAL = 1
    FIX = 2
    BREAK = 3

    NAMES: ClassVar[dict[int, str]] = {
        DIG: "dig", REVEAL: "reveal", FIX: "fix", BREAK: "break",
    }
    # The past tense a structure's message reads with ("the pit is dug").
    DONE: ClassVar[dict[int, str]] = {
        DIG: "dug", REVEAL: "revealed", FIX: "fixed", BREAK: "broken",
    }
    ORDER: ClassVar[list[int]] = [DIG, REVEAL, FIX, BREAK]

    @classmethod
    def name(cls, verb):
        return cls.NAMES.get(verb, "use")

    @classmethod
    def done(cls, verb):
        return cls.DONE.get(verb, "opened")


# The actions that open a structure, bound here because the verbs they bring are
# the Verb table's (declared just above: the Action class is written before it).
# Both handlers read it (see Game._action_dynamite / _action_stormcloud) and so
# does a structure's "Opened by" row, so no card that can open a door is left
# out of the list a player reads.
Action.OPENS = {
    Action.DYNAMITE: (Verb.DIG, Verb.REVEAL),
    Action.STORMCLOUD: (Verb.BREAK, Verb.FIX, Verb.DIG, Verb.REVEAL),
}


class Modifier:
    """A MODIFIER: something that has been DONE to an item, and its stacks.

    User request: "create a system of modifiers for items: 'golden', 'diamond'
    and 'forgotten' are all modifiers. tokens are just blocks with the 'token'
    modifier, where the number of stacks a block has is equal to the number of
    runs more that a block acts as a token. blocks with extra triggers have a
    certain number of the 'retriggerable' modifier equal to the number of times
    they can be retriggered. v2 actions have the 'v2' modifier."

    A modifier is not what an item DOES (that is Keyword) and not what it is made
    of (that is the tables above): it is the state riding ON TOP of the item, and
    every one of them is the same shape -- a kind and a number of stacks -- so one
    table, one drawer, one sidebar row and one save field serve them all. The
    state the game already kept in fields of its own lives here now (see
    Modifiable): `quality` is the golden/diamond pair, an action's `version` is
    V2, a block's `trigger_limit` is RETRIGGERABLE stacks + 1, a Spirit token's
    `runs_left` is its TOKEN stacks, and the Shuffled trial's face-down card is
    FLIPPED -- the "similar parts of the game" the request asked to fold in.
    """
    GOLDEN = 0        # a golem folded two items into it (see Quality)
    DIAMOND = 1       # two goldens folded together
    FORGOTTEN = 2     # cannot be drawn; loses a stack every run (vodka)
    TEMPORARY = 3     # destroyed at the end of the run it was made for (a spark)
    TOKEN = 4         # a kept block that fires every run, for its stacks
    RETRIGGERABLE = 5  # extra triggers per run, one per stack
    V2 = 6            # the upgraded version of an action
    FLIPPED = 7       # face down for the run (the Shuffled trial)
    DISABLED = 8      # silenced for the run (the Card cutter trial)
    # Using the item does not throw it away: it stays in hand, ready to use
    # again (user request: "when a card is used, discard it unless it has the
    # keyword reusable"). The keyword of the same name is derived from this, so
    # anything that can carry a modifier can be made reusable (see
    # Game._discard_used_card).
    REUSABLE = 9

    NAMES: ClassVar[dict[int, str]] = {
        GOLDEN: "golden", DIAMOND: "diamond", FORGOTTEN: "forgotten",
        TEMPORARY: "temporary", TOKEN: "token",
        RETRIGGERABLE: "retriggerable", V2: "v2", FLIPPED: "flipped",
        DISABLED: "disabled", REUSABLE: "reusable",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        FORGOTTEN: "Cannot be drawn. It loses 1 stack every run, and can be "
                   "drawn again once they are gone.",
        TEMPORARY: "Destroyed at the end of the run it was made for.",
        TOKEN: "It fires every run, for as many runs as it has stacks left.",
        RETRIGGERABLE: "It can be triggered once more per stack, every run.",
        V2: "The upgraded version of an action.",
        FLIPPED: "Face down: its text and its payoffs are turned over for the run.",
        DISABLED: "Silenced for the run: its score effect does nothing.",
        REUSABLE: "Using it does not discard it: it stays in your hand, ready "
                  "to be used again.",
    }
    # The colour a mark on the tile wears (see ui._draw_modifier_marks). A
    # modifier that already has its own face in the UI (v2's gold frame, a
    # token's chip) carries none.
    COLORS: ClassVar[dict[int, tuple | None]] = {
        GOLDEN: (232, 190, 74),
        DIAMOND: (140, 222, 236),
        FORGOTTEN: (158, 140, 196),
        TEMPORARY: (206, 150, 112),
        TOKEN: (186, 158, 238),
        RETRIGGERABLE: (126, 200, 142),
        V2: None,
        FLIPPED: None,
        DISABLED: (120, 120, 120),
        # Reusable has no mark of its own: its whole point is that the item
        # stays, so a badge would only decorate a tile that never moves.
        REUSABLE: None,
    }
    # A modifier whose stacks are a COUNTDOWN: one is spent at the end of every
    # run (see Game._age_modifiers).
    AGES_PER_RUN: ClassVar[tuple] = (FORGOTTEN,)
    # The stacks a TOKEN carries when it never expires (a v2 token).
    PERMANENT: ClassVar[int] = -1
    ORDER: ClassVar[list[int]] = [GOLDEN, DIAMOND, FORGOTTEN, TEMPORARY,
                                  TOKEN, RETRIGGERABLE, V2, FLIPPED, DISABLED,
                                  REUSABLE]

    @classmethod
    def name(cls, modifier):
        return cls.NAMES.get(modifier, "")

    @classmethod
    def color(cls, modifier):
        return cls.COLORS.get(modifier)

    @classmethod
    def description(cls, modifier):
        """One line: what this modifier does to the item carrying it.

        The two TIERS answer with the Quality text, because that is where the
        ladder (and what it is worth) is explained; every other modifier answers
        with its own row.
        """
        if modifier == cls.GOLDEN:
            return Quality.description(Quality.GOLDEN)
        if modifier == cls.DIAMOND:
            return Quality.description(Quality.DIAMOND)
        return cls.DESCRIPTIONS.get(modifier, "")

    @classmethod
    def stacks(cls, item, modifier):
        """How many stacks of ``modifier`` the item carries (0 for none)."""
        getter = getattr(item, "modifier_stacks", None)
        if getter is None:
            return 0
        return getter(modifier)

    @classmethod
    def has(cls, item, modifier):
        return cls.stacks(item, modifier) != 0

    @classmethod
    def set_stacks(cls, item, modifier, stacks):
        """Give the item exactly this many stacks (0 removes the modifier)."""
        setter = getattr(item, "set_modifier_stacks", None)
        if setter is not None:
            setter(modifier, stacks)
        return item

    @classmethod
    def add(cls, item, modifier, stacks=1):
        return cls.set_stacks(item, modifier, cls.stacks(item, modifier) + stacks)

    @classmethod
    def of(cls, item):
        """Every modifier on the item, as (modifier, stacks) in table order."""
        return [(modifier, cls.stacks(item, modifier)) for modifier in cls.ORDER
                if cls.stacks(item, modifier)]

    @classmethod
    def line(cls, item):
        """What the sidebar prints: "golden, forgotten x3" ("" for none)."""
        words = []
        for modifier, stacks in cls.of(item):
            name = cls.name(modifier)
            if modifier == cls.TOKEN:
                words.append(f"{name} ({stacks if stacks >= 0 else 'permanent'})")
            elif stacks != 1:
                words.append(f"{name} x{stacks}")
            else:
                words.append(name)
        return ", ".join(words)


class Modifiable:
    """The ITEM side of the modifier system: a {modifier: stacks} bag.

    Mixed into every item class (and into a Block), so the state a modifier
    describes is one dictionary on the item rather than a field per feature. The
    properties the rest of the game already reads and writes -- an item's
    ``quality``, an action's ``version``, a block's ``trigger_limit``, a card's
    ``flipped`` -- are views over it, which is why the golem, the sidebar, the
    save file and the trials all work unchanged while the truth lives here.
    """
    # Created on first use, so an item class needs no constructor changes and a
    # hand-built item (a test's, a save's) still has a home for its modifiers.
    _modifiers = None

    def modifier_stacks(self, modifier):
        """How many stacks of ``modifier`` this item carries (0 for none)."""
        return (self._modifiers or {}).get(modifier, 0)

    def set_modifier_stacks(self, modifier, stacks):
        """Give this item exactly this many stacks (0 removes the modifier)."""
        if self._modifiers is None:
            self._modifiers = {}
        stacks = int(stacks)
        if stacks:
            self._modifiers[modifier] = stacks
        else:
            self._modifiers.pop(modifier, None)
        return self

    def add_modifier(self, modifier, stacks=1):
        """Add stacks to this item's modifier (see Modifier.add)."""
        return self.set_modifier_stacks(
            modifier, self.modifier_stacks(modifier) + stacks)

    def modifiers(self):
        """Every modifier on this item, as (modifier, stacks) in table order."""
        return Modifier.of(self)

    @property
    def quality(self):
        """The golem TIER of this item, read from its golden/diamond stacks."""
        if self.modifier_stacks(Modifier.DIAMOND):
            return Quality.DIAMOND
        if self.modifier_stacks(Modifier.GOLDEN):
            return Quality.GOLDEN
        return Quality.NORMAL

    @quality.setter
    def quality(self, quality):
        self.set_modifier_stacks(Modifier.GOLDEN,
                                 1 if quality == Quality.GOLDEN else 0)
        self.set_modifier_stacks(Modifier.DIAMOND,
                                 1 if quality == Quality.DIAMOND else 0)

    @property
    def trigger_limit(self):
        """Triggered times per run: 1 plus its RETRIGGERABLE stacks."""
        return 1 + self.modifier_stacks(Modifier.RETRIGGERABLE)

    @trigger_limit.setter
    def trigger_limit(self, limit):
        self.set_modifier_stacks(Modifier.RETRIGGERABLE, max(0, int(limit) - 1))

    @property
    def version(self):
        """An action's version: 2 while it carries the V2 modifier."""
        return 2 if self.modifier_stacks(Modifier.V2) else 1

    @version.setter
    def version(self, version):
        self.set_modifier_stacks(Modifier.V2, 1 if int(version) >= 2 else 0)

    @property
    def flipped(self):
        """True while the item is face down (the Shuffled trial's FLIPPED)."""
        return bool(self.modifier_stacks(Modifier.FLIPPED))

    @flipped.setter
    def flipped(self, flipped):
        self.set_modifier_stacks(Modifier.FLIPPED, 1 if flipped else 0)


class Quality:
    """What an item has BECOME: the tier a golem leaves it at (see Structure).

    User request: "make items combined by the golem 'golden', and show that in
    their name and appearance. make the player able to combine two golden items
    into a diamond item, with 4x the magnitude of the original item." A golem
    folds two of the same item into one, so the item it makes is GOLDEN, and two
    golden items fold into a DIAMOND.

    The tiers are one small table rather than a flag on each item, because every
    word about them comes from the same row: the word a name is prefixed with,
    the multiplier the tier is worth, the colour a tile wears, and what the tier
    combines INTO. One golem always doubles, so GOLDEN is 2x the plain item and
    DIAMOND (two goldens) 4x — and DIAMOND has no COMBINES_INTO entry, which is
    what makes it the last tier.
    """
    NORMAL = 0
    GOLDEN = 1
    DIAMOND = 2

    # The word an item's name is prefixed with ("" for an untouched item).
    NAMES: ClassVar[dict[int, str]] = {
        NORMAL: "", GOLDEN: "Golden", DIAMOND: "Diamond",
    }
    # What a tier is worth against the PLAIN item it was combined from.
    MULTIPLIERS: ClassVar[dict[int, int]] = {
        NORMAL: 1, GOLDEN: 2, DIAMOND: 4,
    }
    # The tier a golem makes of two items of this one; a missing entry is final,
    # so a diamond is never combined again.
    COMBINES_INTO: ClassVar[dict[int, int]] = {
        NORMAL: GOLDEN, GOLDEN: DIAMOND,
    }
    # The colour a combined item wears, on its frame and its gem (None: plain).
    COLORS: ClassVar[dict[int, tuple]] = {
        NORMAL: None,
        GOLDEN: (232, 190, 74),      # gold
        DIAMOND: (140, 222, 236),    # pale diamond blue
    }
    ORDER: ClassVar[list[int]] = [NORMAL, GOLDEN, DIAMOND]

    @classmethod
    def name(cls, quality):
        return cls.NAMES.get(quality, "")

    @classmethod
    def of(cls, item):
        """An item's tier (NORMAL for anything a golem never touched)."""
        return getattr(item, "quality", cls.NORMAL)

    @classmethod
    def title(cls, item):
        """The word an item's name is prefixed with: "Golden Lantern", ..."""
        name = cls.name(cls.of(item))
        return f"{name} " if name else ""

    @classmethod
    def multiplier(cls, quality):
        return cls.MULTIPLIERS.get(quality, 1)

    @classmethod
    def combines_into(cls, quality):
        """The tier two items of this one make, or None when they make nothing."""
        return cls.COMBINES_INTO.get(quality)

    @classmethod
    def color(cls, quality):
        return cls.COLORS.get(quality)

    @classmethod
    def description(cls, quality):
        """One line: what the tier is worth, and what it can still become."""
        made = cls.combines_into(quality)
        words = (f"A golem's work: {cls.multiplier(quality)}x what the plain "
                 f"item was.")
        if made is None:
            return words + " Nothing combines it further."
        return (words + f" Two {cls.name(quality).lower()} items make a "
                        f"{cls.name(made).lower()} "
                        f"({cls.multiplier(made)}x).")


class Ability:
    """What an ITEM can be used for: the one contract the S key dispatches.

    An ability is the reusable half of an item's behaviour -- WHICH targets it
    needs, WHAT it costs, and which Game method carries it out. The item's KIND
    only decides how often it may fire and what pays for it (a tool is reusable
    and spends energy, an action is spent when it fires, a block's own ability
    fires from the block), so a new capability is one row here plus one handler,
    and nothing else: no new key, no new refusal wording, no new sidebar branch
    (see Game._use_ability and Game._describe_item).

    The TARGET GRAMMAR is deliberately tiny, because the player only has to
    learn it once: an ability needs nothing, one structure, one other item, or
    whatever number of targets the item itself asks for (an action's own
    required_targets). Every "Needs ..." line the sidebar shows, and every
    refusal, is phrased from this table, so the words cannot drift apart.
    """

    OPEN = 0        # a tool's verb, applied to one structure
    APPLY = 1       # an action, applied to the targets it asks for
    OPEN_PACK = 2   # a pack: deal its options and keep part of them
    DISCARD = 3     # throw this item away with one other item, then draw
    MODIFY = 4      # a tool that pours MODIFIERS onto one card (a vodka)

    NAMES: ClassVar[dict[int, str]] = {
        OPEN: "Open", APPLY: "Apply", OPEN_PACK: "Open", DISCARD: "Discard",
        MODIFY: "Modify",
    }
    # The target grammar: what an ability needs, and how many. "target" means
    # the item itself decides (an action's own required_targets).
    NEEDS: ClassVar[dict[int, tuple[str, int]]] = {
        OPEN: ("structure", 1),
        APPLY: ("target", 0),
        OPEN_PACK: ("nothing", 0),
        DISCARD: ("item", 1),
        MODIFY: ("card", 1),
    }
    # What firing it spends, in the game's OWN currencies: energy (per run), the
    # item itself, or the items it throws away. There is no fifth currency.
    # APPLY costs NOTHING by itself now (user request: "make all cards
    # homogenous"): a used card is destroyed because it says "consume" (see
    # Keyword), so the contract line only has to name the energy the card asks
    # for — the keyword row above it already says the card is spent.
    COSTS: ClassVar[dict[int, str]] = {
        OPEN: "1 energy",
        APPLY: "nothing",
        OPEN_PACK: "nothing",
        DISCARD: "this item and the one with it",
        MODIFY: "1 energy",
    }
    # The one Game method that carries each ability out, kept beside the row so
    # an ability cannot exist without a handler (see Game._use_ability).
    HANDLERS: ClassVar[dict[int, str]] = {
        OPEN: "_apply_tool",
        APPLY: "_apply_action",
        OPEN_PACK: "_open_owned_pack",
        DISCARD: "_use_wasteful",
        MODIFY: "_apply_modifier_tool",
    }
    # The words the grammar prints with ("Needs 1 structure").
    TARGET_WORDS: ClassVar[dict[str, tuple[str, str]]] = {
        "structure": ("structure", "structures"),
        "item": ("other item", "other items"),
        "target": ("target", "targets"),
        "card": ("card", "cards"),
    }
    ORDER: ClassVar[list[int]] = [OPEN, APPLY, OPEN_PACK, DISCARD, MODIFY]

    @classmethod
    def name(cls, ability):
        return cls.NAMES.get(ability, "Use")

    @classmethod
    def of(cls, item):
        """The ability ``item`` fires with S, or None when it has none.

        The item's KIND decides, except for a block, whose abilities come from
        its own effects: Wasteful is the first block ability, and every future
        one is a single line here -- which is what keeps the S key from growing
        another branch for each of them.
        """
        if item is None:
            return None
        kind = getattr(item, "kind", None)
        if kind == "tool":
            # A tool OPENS a structure -- unless its table says it pours a
            # modifier onto a card instead (a vodka), or that it has no verbs at
            # all (a lump of dirt, which cannot be used).
            if Tool.modifies(item.value):
                return cls.MODIFY
            return cls.OPEN if Tool.opens_structures(item.value) else None
        if kind == "action":
            return cls.APPLY
        if kind == "pack":
            return cls.OPEN_PACK
        if Effect.WASTEFUL in (getattr(item, "effects", None) or ()):
            return cls.DISCARD
        return None

    @classmethod
    def needs_text(cls, ability, count=None):
        """How the ability's targets read ("1 structure"), or "" for none."""
        what, number = cls.NEEDS.get(ability, ("nothing", 0))
        if what == "nothing":
            return ""
        if what == "target" and count is not None:
            number = count
        singular, plural = cls.TARGET_WORDS[what]
        return f"{number} {singular if number == 1 else plural}"

    @classmethod
    def cost_text(cls, ability, cost=None):
        """What firing the ability spends.

        ``cost`` states the ITEM's own price where the table's row is only the
        default: the OPEN ability is 1 energy for the four tools the player
        starts with, and a brick opens a structure for nothing (see Tool.ENERGY).
        """
        if cost:
            return cost
        return cls.COSTS.get(ability, "nothing")

    @classmethod
    def contract(cls, ability, count=None, cost=None, needs=None):
        """The whole contract in one line: needs (if any), then cost.

        ``needs`` and ``cost`` state the ITEM's own rule where the table's row
        is only the default: a reusable action is never spent (see
        Game._discard_used_card), and an action that takes a structure if there
        is one needs "no target, or 1 structure" rather than the plain number.
        """
        needs = cls.needs_text(ability, count) if needs is None else needs
        spent = cls.cost_text(ability, cost)
        if not needs:
            return f"Costs {spent}."
        return f"Needs {needs}. Costs {spent}."

    @classmethod
    def handler(cls, ability):
        """The Game method that carries the ability out (or None)."""
        return cls.HANDLERS.get(ability)


class Structure:
    """A thing on the board the player OPENS with a tool to get something out.

    Structures are what the shelf sells now (user request: "replace shop items
    with 'structures'"): a bought structure is an item lying on the board, and
    it stays one until the player uses the right tool on it — select the tool,
    select the structure, press S. What comes out is either a finished ITEM
    (an action) or a PACK (a bundle to choose from), and the structure is spent
    when it opens.

    The table is deliberately small and explicit: a structure answers to the
    verbs it is built for and to nothing else, so a pit can be dug but not
    broken, and a mirror can be fixed or broken but not dug.

    ONE STRUCTURE PER PACK. Every item in the game is obtainable through a
    structure (user request: "make all items in the game obtainable through
    structures. For example, add a new 'tool pack' that gives tools. for each
    pack, create a new structure."), so each pack type has a structure of its
    own: QUARRY digs out shapes, SHRINE effects, VAULT scorers, WORKBENCH parts,
    DEPOT ready-made blocks, LIBRARY cards, CABINET actions, MINT resource
    points, RIFT anything at all, and SHED the one-shot tools and passive items.
    The three first structures and the golem keep their own rewards, so there
    are several ways to the same shelf of goods.
    """
    PIT = 0
    CRYSTAL_POOL = 1
    MIRROR = 2
    # The golem is the one structure that asks something of the player instead
    # of handing a fixed reward over: bring it two of the same item and it makes
    # them one, with both their magnitudes (user request: "combine 2 of the same
    # items to create 1 new item with double the magnitude"). It answers to any
    # tool because it is a workbench rather than a lock.
    GOLEM = 3
    # --- One per PACK (see Pack): every kind of item has a way out. ----------
    QUARRY = 4       # Pack.SHAPE    -- a cut face in the rock
    SHRINE = 5       # Pack.EFFECT   -- something glimmers on the altar
    VAULT = 6        # Pack.SCORER   -- a strongbox of scorers
    WORKBENCH = 7    # Pack.PART     -- parts laid out to take
    DEPOT = 8        # Pack.BLOCK    -- ready-made blocks stacked up
    LIBRARY = 9      # Pack.CARD     -- shelves of cards
    CABINET = 10     # Pack.ACTION   -- drawers of actions
    MINT = 11        # Pack.RESOURCE -- stamped resource points
    RIFT = 12        # Pack.RANDOM   -- anything at all
    SHED = 13        # Pack.TOOL     -- tools and passive items

    NAMES: ClassVar[dict[int, str]] = {
        PIT: "Pit",
        CRYSTAL_POOL: "Crystal Pool",
        MIRROR: "Mirror",
        GOLEM: "Golem",
        QUARRY: "Quarry",
        SHRINE: "Shrine",
        VAULT: "Vault",
        WORKBENCH: "Workbench",
        DEPOT: "Depot",
        LIBRARY: "Library",
        CABINET: "Cabinet",
        MINT: "Mint",
        RIFT: "Rift",
        SHED: "Shed",
    }
    # What each structure holds, keyed by the verb that opens it. The result is
    # (kind, value): "pack" names a components.Pack TYPE, "action" a
    # components.Action value. Reading it the other way round is Structure.result.
    RESULTS: ClassVar[dict[int, dict[int, tuple[str, int]]]] = {
        # A pit is a hole to dig in: dig it and what you get out is parts.
        # Shine a light in first and you see what else fell in there: a TOOL
        # pack, which is where the one-shot tools and the passive items come
        # from (user request: the brick, the match and concrete).
        PIT: {Verb.DIG: ("pack", Pack.PART),
              Verb.REVEAL: ("pack", Pack.TOOL)},
        # Still water shows you what is in it: revealing it or digging it out
        # hands over the Cleansing action, which makes a piece 1.5x stronger.
        CRYSTAL_POOL: {Verb.REVEAL: ("action", Action.CLEANSING),
                       Verb.DIG: ("action", Action.CLEANSING)},
        # A mirror shows you yourself: fix it and it Recognises, break it and
        # it is Strength. The two verbs give the two very different halves.
        MIRROR: {Verb.FIX: ("action", Action.RECOGNITION),
                 Verb.BREAK: ("action", Action.STRENGTH)},
        # A golem is a workbench: any tool wakes it, and what it makes is the
        # two items the player brought. The "merge" row's value is how many of
        # them an opening takes, so the number a golem asks for is data too.
        GOLEM: {verb: ("merge", 2) for verb in Verb.ORDER},
        # --- One structure per PACK: nothing in the game is out of reach. -----
        # Each opens with a single verb, so a level's board asks for a
        # particular tool; the rift is the exception, and any tool wakes it.
        QUARRY: {Verb.DIG: ("pack", Pack.SHAPE)},
        SHRINE: {Verb.FIX: ("pack", Pack.EFFECT)},
        VAULT: {Verb.BREAK: ("pack", Pack.SCORER)},
        WORKBENCH: {Verb.FIX: ("pack", Pack.PART)},
        DEPOT: {Verb.BREAK: ("pack", Pack.BLOCK)},
        LIBRARY: {Verb.REVEAL: ("pack", Pack.CARD)},
        CABINET: {Verb.REVEAL: ("pack", Pack.ACTION)},
        MINT: {Verb.DIG: ("pack", Pack.RESOURCE)},
        RIFT: {verb: ("pack", Pack.RANDOM) for verb in Verb.ORDER},
        SHED: {Verb.REVEAL: ("pack", Pack.TOOL)},
    }
    COMMENTS: ClassVar[dict[int, str]] = {
        PIT: "Something is down there.",
        CRYSTAL_POOL: "Look closer.",
        MIRROR: "Who is that?",
        GOLEM: "Two of a kind, made one.",
        QUARRY: "Fresh-cut shapes.",
        SHRINE: "Something glimmers.",
        VAULT: "Locked for a reason.",
        WORKBENCH: "Bits and pieces, laid out.",
        DEPOT: "Stacked and ready.",
        LIBRARY: "Every card wants a run.",
        CABINET: "One use each.",
        MINT: "Stamped and counted.",
        RIFT: "Anything could come out.",
        SHED: "Someone left their kit behind.",
    }
    # The SHORT line the collection prints for a structure whose sidebar
    # description is too long for the codex's five-line box (see
    # codex_description). One entry, because only the golem explains a ladder.
    CODEX: ClassVar[dict[int, str]] = {
        GOLEM: ("Use any tool with 2 of the same item: they become 1 golden "
                "item, then a diamond."),
    }
    # How often a shelf slot deals each structure: pits are the plainest and
    # most common, mirrors the rarest. The odds are relative, so they follow
    # the list of structures the shelf offers.
    OFFER_WEIGHTS: ClassVar[dict[int, int]] = {
        PIT: 14, CRYSTAL_POOL: 10, MIRROR: 8, GOLEM: 8,
        QUARRY: 6, SHRINE: 6, VAULT: 6, WORKBENCH: 6, DEPOT: 6,
        LIBRARY: 6, CABINET: 6, MINT: 6, RIFT: 6, SHED: 6,
    }
    # How rare each structure is (see Rarity). A structure is FREE, so its tier
    # cannot be its price the way an action's or a part's is: it follows what the
    # structure HANDS OVER instead. The plainest doors — the pit, the pool and
    # the workbench of loose parts — are Common; a mirror and the single-pack
    # doors that hand over a finished thing are dearer; and the rift, which can
    # deal anything any other door can, is the one Epic.
    RARITIES: ClassVar[dict[int, int]] = {
        PIT: Rarity.COMMON, CRYSTAL_POOL: Rarity.COMMON,
        QUARRY: Rarity.COMMON, WORKBENCH: Rarity.COMMON, MINT: Rarity.COMMON,
        MIRROR: Rarity.UNUSUAL, SHRINE: Rarity.UNUSUAL, VAULT: Rarity.UNUSUAL,
        DEPOT: Rarity.UNUSUAL,
        LIBRARY: Rarity.RARE, CABINET: Rarity.RARE, SHED: Rarity.RARE,
        GOLEM: Rarity.RARE,
        RIFT: Rarity.EPIC,
    }
    # Structures are FREE (user request: "make all structures free (no need to
    # buy them for them to be used)"): a shelf slot hands one over as scenery the
    # player's tools open, so there is nothing to pay and nothing to unlock. The
    # table stays the one place a structure's price would live.
    PRICES: ClassVar[dict[int, int]] = {structure: 0
                                        for structure in range(SHED + 1)}
    COLORS: ClassVar[dict[int, tuple]] = {
        PIT: (60, 52, 44),             # dug earth
        CRYSTAL_POOL: (40, 110, 130),  # still water
        MIRROR: (150, 160, 178),       # silvered glass
        GOLEM: (140, 128, 112),        # river clay
        QUARRY: (118, 124, 132),       # cut stone
        SHRINE: (150, 110, 190),       # a glimmer of violet
        VAULT: (196, 150, 70),         # brass and amber
        WORKBENCH: (108, 168, 118),    # the assembly green of a part pack
        DEPOT: (150, 112, 88),         # stacked timber
        LIBRARY: (182, 84, 120),       # card magenta
        CABINET: (70, 150, 160),       # action teal
        MINT: (176, 168, 74),          # resource ochre
        RIFT: (128, 128, 138),         # anything grey
        SHED: (140, 156, 172),         # steel
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        PIT: "\u25bc", CRYSTAL_POOL: "\u25c6",
        MIRROR: "\u25a7", GOLEM: "\u25b2",
        QUARRY: "\u25ae", SHRINE: "\u2726", VAULT: "\u25a3",
        WORKBENCH: "\u2b22", DEPOT: "\u25a4", LIBRARY: "\u25a5",
        CABINET: "\u25a6", MINT: "\u25c9", RIFT: "\u2737",
        SHED: "\u2692",
    }
    ORDER: ClassVar[list[int]] = [
        PIT, CRYSTAL_POOL, MIRROR, GOLEM,
        QUARRY, SHRINE, VAULT, WORKBENCH, DEPOT, LIBRARY, CABINET, MINT,
        RIFT, SHED,
    ]

    @classmethod
    def name(cls, structure):
        return cls.NAMES.get(structure, "Unknown structure")

    @classmethod
    def comment(cls, structure):
        return cls.COMMENTS.get(structure, "")

    @classmethod
    def result(cls, structure, verb):
        """What opening ``structure`` with ``verb`` gives, or None.

        None means the structure does not answer to that verb at all: a pit
        cannot be broken, so breaking one does nothing and spends nothing.
        """
        return cls.RESULTS.get(structure, {}).get(verb)

    @classmethod
    def verbs(cls, structure):
        """The verbs this structure answers to, in Verb.ORDER."""
        openers = cls.RESULTS.get(structure, {})
        return [verb for verb in Verb.ORDER if verb in openers]

    @classmethod
    def merges(cls, structure):
        """True when opening this structure COMBINES items instead of paying one out."""
        for verb in cls.verbs(structure):
            kind, _value = cls.result(structure, verb)
            if kind == "merge":
                return True
        return False

    @classmethod
    def merge_count(cls, structure):
        """How many of the player's items an opening takes (0 when it takes none)."""
        for verb in cls.verbs(structure):
            kind, value = cls.result(structure, verb)
            if kind == "merge":
                return value
        return 0

    @classmethod
    def description(cls, structure):
        """One line: what opens it, and what comes out."""
        if cls.merges(structure):
            count = cls.merge_count(structure)
            golden = Quality.name(Quality.GOLDEN).lower()
            diamond = Quality.name(Quality.DIAMOND).lower()
            return (f"Use any tool on it with {count} of the same item selected: "
                    f"they become 1 {golden} item, with both their magnitudes. "
                    f"Two {golden} items make a {diamond} one.")
        parts = []
        for verb in cls.verbs(structure):
            kind, value = cls.result(structure, verb)
            made = (Pack.name(value) if kind == "pack" else Action.name(value))
            parts.append(f"{Verb.name(verb)} \u2192 {made}")
        if not parts:
            return "Nothing opens it."
        # A structure that answers to every verb with the SAME thing (the rift,
        # which is a way to a Random Pack however it is opened) says so once
        # instead of listing the same reward four times.
        made_values = {cls.result(structure, verb) for verb in cls.verbs(structure)}
        if len(cls.verbs(structure)) > 1 and len(made_values) == 1:
            kind, value = made_values.pop()
            made = Pack.name(value) if kind == "pack" else Action.name(value)
            return f"Use any tool on it: {made}."
        return f"Use a tool on it: {', '.join(parts)}."

    @classmethod
    def codex_description(cls, structure):
        """What the collection prints for a structure: a line that FITS.

        The codex box holds five short lines (see ui.COLLECTION_DESC_LINES), and
        a structure's full description is written for the sidebar's wider column
        -- the golem's, in particular, explains the whole tier ladder. This is
        the same rule stated for that box, so no entry is ever cut off.
        """
        return cls.CODEX.get(structure) or cls.description(structure)

    @classmethod
    def weight(cls, structure):
        return cls.OFFER_WEIGHTS.get(structure, 0)

    @classmethod
    def rarity(cls, structure):
        """How rare this structure is (see RARITIES); Common if it has no row.

        A structure is free, so its tier is the one thing about it the price
        cannot answer (see Rarity).
        """
        return cls.RARITIES.get(structure, Rarity.COMMON)


class Tool:
    """A verb, carried by an item: what a structure is opened WITH (see Structure).

    The four the player starts with (user request: "make the player start with
    these 4 items") are never spent, so a structure bought later can still be
    opened. Using one is exactly like using an action: select the tool, select
    the structure, press S (see Game._apply_tool), and an OPENING spends the
    tool's own ENERGY, which is 1 for the four and whatever the table says for
    the rest.

    A tool is an ITEM, though, so the one-shot tools are sold like anything else
    and are CONSUMED when they are used: a brick breaks or digs for no energy,
    and a match reveals a structure and then burns out for a fresh item. Their
    whole text is the vocabulary in Keyword, so an item's keywords ARE its rules:

        Brick   -- break, dig, consume (0 energy)
        Match   -- reveal, consume, draw 1 (1 energy)

    A tool that carries several verbs uses the first one its structure answers
    to, so a brick digs a pit and breaks a mirror.
    """
    SHOVEL = 0
    FLASHLIGHT = 1
    SCREWDRIVER = 2
    HAMMER = 3
    BRICK = 4
    MATCH = 5
    GLOWSTICK = 6
    PRY_BAR = 7
    CHISEL = 8
    GILDING_CLOTH = 9
    WRECKING_BAR = 10
    MULTI_TOOL = 11
    DIRT = 12
    DRILL = 13
    PICKAXE = 14
    SPARK = 15
    VODKA = 16

    NAMES: ClassVar[dict[int, str]] = {
        SHOVEL: "Shovel", FLASHLIGHT: "Flashlight",
        SCREWDRIVER: "Screwdriver", HAMMER: "Hammer",
        BRICK: "Brick", MATCH: "Match",
        GLOWSTICK: "Glowstick", PRY_BAR: "Pry Bar", CHISEL: "Chisel",
        GILDING_CLOTH: "Gilding Cloth", WRECKING_BAR: "Wrecking Bar",
        MULTI_TOOL: "Multi-Tool",
        DIRT: "Dirt", DRILL: "Excavator", PICKAXE: "Pickaxe", SPARK: "Spark",
        VODKA: "Vodka",
    }
    # The verbs each tool applies, in the order it tries them. The four starters
    # carry one each; a brick carries two and uses whichever its structure
    # answers to (so it digs a pit and breaks a mirror).
    VERBS: ClassVar[dict[int, tuple]] = {
        SHOVEL: (Verb.DIG,), FLASHLIGHT: (Verb.REVEAL,),
        SCREWDRIVER: (Verb.FIX,), HAMMER: (Verb.BREAK,),
        BRICK: (Verb.BREAK, Verb.DIG), MATCH: (Verb.REVEAL,),
        # A glowstick is the free way into the REVEAL half (the free one-shot
        # for the other two verbs), a pry bar is the permanent tool with two
        # verbs, and a multi-tool answers every door there is -- once a run.
        GLOWSTICK: (Verb.REVEAL,), PRY_BAR: (Verb.DIG, Verb.BREAK),
        CHISEL: (Verb.FIX,), GILDING_CLOTH: (Verb.FIX, Verb.REVEAL),
        WRECKING_BAR: (Verb.BREAK,),
        MULTI_TOOL: (Verb.DIG, Verb.REVEAL, Verb.FIX, Verb.BREAK),
        # A drill answers every door and pays in deck space (see MAKES); dirt
        # has no verb at all, which is what "does nothing" means here.
        DRILL: (Verb.BREAK, Verb.FIX, Verb.DIG, Verb.REVEAL),
        DIRT: (),
        PICKAXE: (Verb.DIG,),
        SPARK: (Verb.REVEAL,),
        VODKA: (),
    }
    # What one use spends of the run's energy (see MAX_ENERGY). The four starters
    # cost 1; a brick is free, which is what makes a 0-energy opening possible.
    ENERGY: ClassVar[dict[int, int]] = {
        SHOVEL: 1, FLASHLIGHT: 1, SCREWDRIVER: 1, HAMMER: 1,
        BRICK: 0, MATCH: 1,
        # Breadth is what the bigger numbers buy: two verbs a use costs 2 of a
        # run's 3, and a tool that answers ANY door costs all 3.
        GLOWSTICK: 0, PRY_BAR: 2, CHISEL: 1, GILDING_CLOTH: 2,
        WRECKING_BAR: 1, MULTI_TOOL: 3,
        DIRT: 0, DRILL: 0, PICKAXE: 1, SPARK: 0, VODKA: 1,
    }
    # The tools that are DESTROYED by using them: the "consume" keyword.
    CONSUMES: ClassVar[tuple] = (BRICK, MATCH, GLOWSTICK, CHISEL,
                                 GILDING_CLOTH, WRECKING_BAR, SPARK, VODKA)
    # ...and how many items one draws after it is consumed: the match's
    # "discard this item and draw an item".
    DRAWS: ClassVar[dict[int, int]] = {MATCH: 1}
    # The AMOUNT each tool carries (its magnitude, see items.ToolItem.amount and
    # Game._item_magnitudes). A tool that only opens the door holds no number of
    # its own (0); these two shape the REWARD, and their amount is how many
    # steps of that shaping one use makes -- which is also what a golem folds
    # when it combines two of them (see AMOUNT_EFFECT).
    AMOUNTS: ClassVar[dict[int, float]] = {CHISEL: 1, GILDING_CLOTH: 1}
    # What a tool's amount DOES to the opening it makes: the chisel pushes the
    # reward's pack one SIZE up the ladder, the gilding cloth one QUALITY tier
    # up. A tool with no entry only opens the door.
    AMOUNT_EFFECT: ClassVar[dict[int, str]] = {
        CHISEL: "pack_size", GILDING_CLOTH: "quality",
    }
    # The words the sidebar prints for what an amount means (see the Magnitude
    # row in Game._describe_item): "1 pack size bigger a use".
    AMOUNT_LABELS: ClassVar[dict[int, str]] = {
        CHISEL: "pack size bigger a use",
        GILDING_CLOTH: "quality tier higher a use",
    }
    # The tools that take every structure standing NEXT TO the one they are used
    # on with them: one swing, every neighbour that answers the verb.
    SWEEPS: ClassVar[tuple] = (WRECKING_BAR,)
    # What a tool LEAVES BEHIND in the player's DECK when it is used: the item
    # it packs in ((kind, value), how many). A drill answers every door for no
    # energy and pays in deck space; a pickaxe digs and strikes a spark.
    MAKES: ClassVar[dict[int, tuple]] = {
        DRILL: (("tool", DIRT), 1),
        PICKAXE: (("tool", SPARK), 1),
    }
    # The modifiers an item of this kind is BORN with (see components.Modifier).
    # A spark is TEMPORARY however it arrives -- struck by a pickaxe or dealt by
    # a Tool Pack -- so the keyword on its tile is always true.
    BORN_WITH: ClassVar[dict[int, tuple]] = {
        SPARK: ((Modifier.TEMPORARY, 1),),
    }
    # The one tool that does not OPEN anything: it pours stacks of a modifier
    # onto a CARD instead (see Ability.MODIFY / Game._apply_modifier_tool).
    MODIFIES: ClassVar[dict[int, tuple]] = {
        VODKA: (Modifier.FORGOTTEN, MAGNITUDES.VODKA_FORGOTTEN),
    }
    # The tools that are by-products rather than finds: they come out of another
    # tool's MAKES, so a Tool Pack never deals them (dirt is junk).
    BY_PRODUCTS: ClassVar[tuple] = (DIRT,)
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        SHOVEL: "Digs: use it on a structure to open it up.",
        FLASHLIGHT: "Reveals: use it on a structure to show what it holds.",
        SCREWDRIVER: "Fixes: use it on a structure to put it in order.",
        HAMMER: "Breaks: use it on a structure to smash it open.",
        BRICK: "Breaks or digs a structure for no energy, then it is used up.",
        MATCH: "Reveals a structure, then burns out: it is thrown away and you draw an item.",
        GLOWSTICK: "Reveals a structure for no energy, then it is used up.",
        PRY_BAR: "Digs or breaks a structure. It is never spent, but costs 2 energy.",
        CHISEL: "Fixes a structure and pushes its reward one pack size bigger.",
        GILDING_CLOTH: "Fixes or reveals a structure; the reward arrives a quality tier higher.",
        WRECKING_BAR: "Breaks a structure and every structure next to it, then is used up.",
        MULTI_TOOL: "Answers every verb, so it opens any structure -- for all 3 energy.",
        DIRT: "Does nothing at all: a lump of dirt taking up room in your deck.",
        DRILL: "Opens any structure for no energy, but packs a lump of Dirt into your deck.",
        PICKAXE: "Digs a structure open and strikes a Spark into your deck.",
        SPARK: "Reveals a structure for no energy and burns out. It is Temporary: gone after this run.",
        VODKA: "Pours 3 stacks of forgotten into a card, then is drunk.",
    }
    COMMENTS: ClassVar[dict[int, str]] = {
        SHOVEL: "Down we go.",
        FLASHLIGHT: "A little light.",
        SCREWDRIVER: "Tighten it up.",
        HAMMER: "Everything looks like a nail.",
        BRICK: "Good for one thing.",
        MATCH: "Strike it once.",
        GLOWSTICK: "Snap and shine.",
        PRY_BAR: "Leverage.",
        CHISEL: "A little off the top.",
        GILDING_CLOTH: "Make it shine.",
        WRECKING_BAR: "Take the wall with it.",
        MULTI_TOOL: "Everything, once.",
        DIRT: "Just dirt.",
        DRILL: "Loud, and it leaves a mess.",
        PICKAXE: "Strike while the vein is open.",
        SPARK: "One bright moment.",
        VODKA: "You will not remember this.",
    }
    COLORS: ClassVar[dict[int, tuple]] = {
        SHOVEL: (120, 95, 60),
        FLASHLIGHT: (195, 180, 70),
        SCREWDRIVER: (80, 120, 150),
        HAMMER: (120, 80, 80),
        BRICK: (150, 85, 65),
        MATCH: (200, 120, 60),
        GLOWSTICK: (150, 205, 120),
        PRY_BAR: (140, 140, 160),
        CHISEL: (110, 150, 150),
        GILDING_CLOTH: (200, 170, 90),
        WRECKING_BAR: (170, 90, 110),
        MULTI_TOOL: (95, 115, 150),
        DIRT: (110, 90, 70),
        DRILL: (170, 140, 60),
        PICKAXE: (120, 130, 145),
        SPARK: (230, 210, 90),
        VODKA: (150, 190, 210),
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        SHOVEL: "d", FLASHLIGHT: "r", SCREWDRIVER: "f", HAMMER: "b",
        BRICK: "k", MATCH: "m",
        GLOWSTICK: "g", PRY_BAR: "p", CHISEL: "c", GILDING_CLOTH: "l",
        WRECKING_BAR: "w", MULTI_TOOL: "t",
        DIRT: ".", DRILL: "E", PICKAXE: "i", SPARK: "*", VODKA: "v",
    }
    # What a one-shot tool is worth if it is sold, and what a TOOL pack prices
    # its options at (see components.pack_base_price).
    PRICES: ClassVar[dict[int, int]] = {
        SHOVEL: 0, FLASHLIGHT: 0, SCREWDRIVER: 0, HAMMER: 0, BRICK: 12,
        MATCH: 14,
        # What a Tool Pack prices these at: breadth and permanence cost.
        GLOWSTICK: 10, PRY_BAR: 40, CHISEL: 24, GILDING_CLOTH: 34,
        WRECKING_BAR: 22, MULTI_TOOL: 60,
        # Dirt is junk and worth nothing; a spark is a free opening, so it is
        # cheap; the two permanent tools cost what their breadth is worth.
        DIRT: 0, DRILL: 36, PICKAXE: 28, SPARK: 8, VODKA: 26,
    }
    # The tools the player STARTS with. The one-shot ones are not starting kit:
    # they come out of TOOL packs.
    STARTERS: ClassVar[tuple] = (SHOVEL, FLASHLIGHT, SCREWDRIVER, HAMMER)
    # The catalogue, in reading order: the four starters (one verb each), then
    # the one-shots, then the two the golem can fold (the amount tools).
    ORDER: ClassVar[list[int]] = [
        SHOVEL, FLASHLIGHT, SCREWDRIVER, HAMMER,
        BRICK, MATCH, GLOWSTICK, WRECKING_BAR,
        CHISEL, GILDING_CLOTH, PRY_BAR, MULTI_TOOL,
        DRILL, PICKAXE, SPARK, VODKA, DIRT,
    ]
    # What a TOOL pack deals (see components.tool_pack_options): everything but
    # the four starters, so every tool in the game is obtainable from one.
    PACK_ORDER: ClassVar[tuple] = (BRICK, MATCH, GLOWSTICK, WRECKING_BAR,
                                   CHISEL, GILDING_CLOTH, PRY_BAR,
                                   MULTI_TOOL, DRILL, PICKAXE, SPARK, VODKA)

    @classmethod
    def name(cls, tool):
        return cls.NAMES.get(tool, "Unknown tool")

    @classmethod
    def verbs(cls, tool):
        """Every Verb this tool applies, in the order it tries them."""
        return tuple(cls.VERBS.get(tool, (Verb.DIG,)))

    @classmethod
    def verb(cls, tool):
        """The first Verb this tool applies, or None for one that has none.

        A dirt has no verb at all (it "does nothing"), and a vodka does not OPEN
        anything either -- it pours modifiers onto a card (see MODIFIES) -- so
        neither has a first verb to name.
        """
        verbs = cls.verbs(tool)
        return verbs[0] if verbs else None

    @classmethod
    def energy(cls, tool):
        """What one use of the tool spends of the run's energy."""
        return cls.ENERGY.get(tool, 1)

    @classmethod
    def consumes(cls, tool):
        """True when the tool is DESTROYED by using it (the "consume" keyword)."""
        return tool in cls.CONSUMES

    @classmethod
    def draws(cls, tool):
        """How many items one use draws for the player afterwards (0 for none)."""
        return cls.DRAWS.get(tool, 0)

    @classmethod
    def keywords(cls, tool):
        """The tool's text, as keywords (see Keyword).

        A tool that is DESTROYED by using it reads "consume", and one that
        survives reads "reusable": a used card is discarded unless its keywords
        say otherwise (see Game._discard_used_card), so every tool states which
        way it goes and the word is never a decoration. A tool with no verbs and
        nothing to modify -- a lump of DIRT -- reads "unplayable", because that
        is exactly what it does: nothing.
        """
        words = [Keyword.for_verb(verb) for verb in cls.verbs(tool)]
        if not words and cls.modifies(tool) is None:
            return (Keyword.UNPLAYABLE,)
        words.append(Keyword.CONSUME if cls.consumes(tool) else Keyword.REUSABLE)
        if cls.draws(tool):
            words.append(Keyword.DRAW)
        return tuple(words)

    @classmethod
    def description(cls, tool):
        return cls.DESCRIPTIONS.get(tool, "A tool.")

    @classmethod
    def comment(cls, tool):
        return cls.COMMENTS.get(tool, "")

    @classmethod
    def amount(cls, tool):
        """The AMOUNT (magnitude) a tool carries: how many steps its reward is
        shaped by (see AMOUNT_EFFECT), 0 for a tool that only opens the door."""
        return cls.AMOUNTS.get(tool, 0)

    @classmethod
    def amount_effect(cls, tool):
        """What the tool's amount does to its reward ("pack_size"/"quality")."""
        return cls.AMOUNT_EFFECT.get(tool)

    @classmethod
    def amount_label(cls, tool):
        """What the number means, in the sidebar's words (0 has no label)."""
        return cls.AMOUNT_LABELS.get(tool, "")

    @classmethod
    def sweeps(cls, tool):
        """True when one use of the tool opens the structures NEXT to its target."""
        return tool in cls.SWEEPS

    @classmethod
    def makes(cls, tool):
        """What the tool leaves in the deck: ((kind, value), count), or None."""
        return cls.MAKES.get(tool)

    @classmethod
    def born_with(cls, tool):
        """The modifiers an item of this tool is made with (see BORN_WITH)."""
        return cls.BORN_WITH.get(tool, ())

    @classmethod
    def modifies(cls, tool):
        """The (modifier, stacks) this tool pours onto a card, or None."""
        return cls.MODIFIES.get(tool)

    @classmethod
    def opens_structures(cls, tool):
        """True when the tool is used on a STRUCTURE (every tool but dirt/vodka)."""
        return bool(cls.verbs(tool))

    @classmethod
    def bigger_pack_size(cls, size, steps):
        """A pack size ``steps`` rungs up the ladder, never past the biggest.

        The chisel's whole payoff: a structure that rolls its pack at random (see
        Game._structure_reward) comes out one size bigger per point of amount,
        and a Normal pack pushed three rungs is a Mega one.
        """
        order = list(Pack.SIZE_ORDER)
        index = order.index(size) if size in order else 0
        return order[max(0, min(len(order) - 1, index + int(steps)))]

    @classmethod
    def better_quality(cls, quality, steps):
        """A tier ``steps`` rungs up the ladder, never past DIAMOND."""
        for _ in range(max(0, int(steps))):
            made = Quality.combines_into(quality)
            if made is None:
                break
            quality = made
        return quality

    @classmethod
    def for_verb(cls, verb):
        """The STARTER tool that applies ``verb`` (one per verb, see VERBS)."""
        for tool in cls.STARTERS:
            if verb in cls.verbs(tool):
                return tool
        return None

class Passive:
    """An UNPLAYABLE item: it is never used, it just lies in the hand and pays.

    User request: "add an item, 'concrete', that gives +30 chips at the start of
    the run, and is passive." A passive has no ability at all (see
    Game._use_ability), which is exactly what its one keyword says, and its
    payoff is read once at the start of every run (see Game._apply_passive_items),
    at the same moment the cards' start effects fire.
    """
    CONCRETE = 0

    NAMES: ClassVar[dict[int, str]] = {CONCRETE: "Concrete"}
    # The text is a template: a passive carries its own AMOUNT (see the amount
    # classmethod below and items.PassiveItem.amount), so a Concrete a golem
    # folded with another one really says "Adds 60 chips".
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        CONCRETE: ("Adds {amount:g} chips at the start of "
                   "every run. It cannot be used."),
    }
    # The payoff each passive pays at the start of a run: (scorer, magnitude), in
    # the same shape a whole card's row uses (see MAGNITUDES.CARD_RATIOS).
    PAYOFFS: ClassVar[dict[int, tuple[int, float]]] = {
        CONCRETE: (Scorer.CHIPS_ADD, MAGNITUDES.CONCRETE_CHIPS),
    }
    COMMENTS: ClassVar[dict[int, str]] = {CONCRETE: "Set in stone."}
    PRICES: ClassVar[dict[int, int]] = {CONCRETE: 16}
    COLORS: ClassVar[dict[int, tuple]] = {CONCRETE: (150, 150, 145)}
    GLYPHS: ClassVar[dict[int, str]] = {CONCRETE: "c"}
    ORDER: ClassVar[list[int]] = [CONCRETE]

    @classmethod
    def name(cls, passive):
        return cls.NAMES.get(passive, "Unknown item")

    @classmethod
    def description(cls, passive, amount=None):
        """What the passive does, at the magnitude it actually carries.

        A passive has an amount like every other item (Concrete's 30 chips), so
        a combined one describes the number it really pays rather than the
        table's average.
        """
        if amount is None:
            amount = cls.amount(passive)
        return cls.DESCRIPTIONS.get(passive, "An item.").format(amount=amount)

    @classmethod
    def comment(cls, passive):
        return cls.COMMENTS.get(passive, "")

    @classmethod
    def payoff(cls, passive):
        """The (scorer, magnitude) a passive pays at the start of every run."""
        return cls.PAYOFFS.get(passive, (Scorer.NONE, 0))

    @classmethod
    def amount(cls, passive):
        """The AMOUNT (magnitude) a passive carries: its payoff's number.

        Every item in the game carries one (see items.PassiveItem.amount), so
        Concrete's is MAGNITUDES.CONCRETE_CHIPS -- 30 chips -- and a golem that
        folds two of them together leaves a Concrete of 60.
        """
        return cls.PAYOFFS.get(passive, (Scorer.NONE, 0))[1]

    @classmethod
    def keywords(cls, passive):
        """A passive item's whole text is one word: it cannot be used."""
        return (Keyword.UNPLAYABLE,)


def tool_pack_options():
    """The (kind, value) items a TOOL pack offers: the one-shots and the passives."""
    return ([("tool", value) for value in Tool.PACK_ORDER]
            + [("passive", value) for value in Passive.ORDER])


class Keyword:
    """The single words an item's text is made of.

    User request: "add terminology for items. just include a single word that
    means something more specific." Every word is one rule, so an item's keywords
    ARE what it does and the player only has to learn a handful of them:

        dig, reveal, fix, break  -- which verb opens a structure (see Verb)
        consume                  -- the item is destroyed when it is used
        reusable                 -- using it does NOT discard it (see below)
        draw N                   -- using it draws N items
        unplayable               -- it cannot be used: it acts on its own

    Every CARD is written with these words now (user request: "make all cards
    homogenous, and treat them the same way"). The three kinds of card in the
    Cards family — a whole card, an action and a tool — differ in which words
    they carry, not in what the words mean:

    * a WHOLE CARD is unplayable: it is never used, it pays on its own (Joker,
      Explorer, Inferno, ... just as a passive item does);
    * an ACTION is consumed by being used, so it says "consume" (or "reusable"
      when a modifier says otherwise);
    * a TOOL carries its verbs, then which way it goes, and often "draw".

    CONSUME and REUSABLE are opposites, so an item that is used is one or the
    other: a used card is DISCARDED unless its keywords say "reusable" (user
    request: "when a card is used, discard it unless it has the keyword
    reusable" — see Game._discard_used_card). Any item can be made reusable with
    the modifier of the same name (see Modifier.REUSABLE), which prints the word
    here.

    Items never spell these rules out a second time: a tool's, a structure's, a
    passive item's, a whole card's and an action's keywords all come from here
    (see Keyword.of), which is the one place the vocabulary lives.
    """
    # The four verbs share the Verb table's own words, so a verb and its keyword
    # can never drift apart.
    DIG = 0
    REVEAL = 1
    FIX = 2
    BREAK = 3
    CONSUME = 4
    DRAW = 5
    UNPLAYABLE = 6
    TEMPORARY = 7
    REUSABLE = 8

    NAMES: ClassVar[dict[int, str]] = {
        DIG: "dig", REVEAL: "reveal", FIX: "fix", BREAK: "break",
        CONSUME: "consume", DRAW: "draw", UNPLAYABLE: "unplayable",
        TEMPORARY: "temporary", REUSABLE: "reusable",
    }
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        DIG: "Opens a structure by digging it up",
        REVEAL: "Opens a structure by showing what is inside it",
        FIX: "Opens a structure by putting it in order",
        BREAK: "Opens a structure by smashing it open",
        CONSUME: "Destroyed when it is used",
        DRAW: "Using it draws this many items",
        UNPLAYABLE: ("Cannot be used: it acts on its own, without being played "
                     "(a whole card, or a passive item)"),
        TEMPORARY: "Destroyed at the end of the run it was made for",
        REUSABLE: "Using it does not discard it: it stays in your hand",
    }
    # The keyword each Verb is written with.
    VERB_KEYWORDS: ClassVar[dict[int, int]] = {
        Verb.DIG: DIG, Verb.REVEAL: REVEAL, Verb.FIX: FIX, Verb.BREAK: BREAK,
    }
    ORDER: ClassVar[list[int]] = [DIG, REVEAL, FIX, BREAK, CONSUME, DRAW,
                                  UNPLAYABLE, TEMPORARY, REUSABLE]

    @classmethod
    def for_verb(cls, verb):
        """The keyword a Verb is written with."""
        return cls.VERB_KEYWORDS.get(verb, cls.DIG)

    @classmethod
    def name(cls, keyword):
        return cls.NAMES.get(keyword, "")

    @classmethod
    def description(cls, keyword):
        return cls.DESCRIPTIONS.get(keyword, "")

    @classmethod
    def text(cls, keywords, counts=None):
        """The keywords as one line: "break, dig, consume" (or "" for none).

        ``counts`` fills in the number a counted keyword needs, so a match reads
        "reveal, consume, draw 1".
        """
        counts = counts or {}
        words = []
        for keyword in keywords:
            name = cls.name(keyword)
            if keyword == cls.DRAW and counts.get(keyword):
                name = f"{name} {counts[keyword]:g}"
            if name:
                words.append(name)
        return ", ".join(words)

    @classmethod
    def line(cls, item):
        """An item's keywords as the one line the sidebar shows.

        The words come from Keyword.of and the numbers from the item itself, so
        a match reads "reveal, consume, draw 1" and a brick "break, dig,
        consume": the same rules, in the same words, wherever they are shown.
        """
        counts = {}
        if getattr(item, "kind", None) == "tool" and Tool.draws(item.value):
            counts[cls.DRAW] = Tool.draws(item.value)
        return cls.text(cls.of(item), counts)

    @classmethod
    def of(cls, item):
        """The keywords an item is described with, in Keyword.ORDER.

        A tool reads its verbs, whether it is consumed or reusable, and what it
        draws; a passive item and a WHOLE CARD read "unplayable" (neither is ever
        used: both pay on their own); an ACTION reads "consume", because using
        one destroys it; a structure reads the verbs it answers to. User request:
        "make all cards homogenous, and treat them the same way" — a whole card
        says "unplayable" and an action says "consume" because that is how each
        one behaves, rather than leaving the kind's name to imply it.
        """
        kind = getattr(item, "kind", None)
        if kind == "tool":
            words = list(Tool.keywords(item.value))
        elif kind == "passive":
            words = list(Passive.keywords(item.value))
        elif kind == "structure":
            words = [cls.for_verb(verb) for verb in Structure.verbs(item.value)]
        elif kind == "card":
            # A whole card is never played: it pays at the start or the end of a
            # run (or when its trigger happens) simply by being owned, exactly
            # as a passive item does.
            words = [cls.UNPLAYABLE]
        elif kind == "action":
            # Using an action destroys it — that IS what "consume" means, and it
            # is the word the card now wears instead of the kind implying it.
            words = [cls.CONSUME]
        else:
            words = []
        # A modifier can ALSO be a word on the tile: TEMPORARY is one (user
        # request: "the keyword 'temporary' means it will be destroyed next
        # round"), and so is REUSABLE -- an item marked reusable says so
        # wherever it is shown (see Modifier.REUSABLE). The words keep the
        # order the item's own table gave them (a brick reads "break, dig").
        if Modifier.has(item, Modifier.TEMPORARY) and cls.TEMPORARY not in words:
            words.append(cls.TEMPORARY)
        if Modifier.has(item, Modifier.REUSABLE) and cls.REUSABLE not in words:
            words.append(cls.REUSABLE)
        # ...and the two are opposites: an item that is not thrown away when it
        # is used says "reusable", not "consume", whatever its table says.
        if cls.REUSABLE in words and cls.CONSUME in words:
            words = [word for word in words if word != cls.CONSUME]
        return tuple(words)

    @classmethod
    def has(cls, item, keyword):
        """True when ``item`` carries ``keyword`` (see Keyword.of).

        This is the question the game asks about a rule: an item is DISCARDED
        when it is used unless Keyword.has(item, Keyword.REUSABLE) (see
        Game._discard_used_card), so the word and the rule can never disagree.
        """
        return keyword in cls.of(item)



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

    def __init__(self, kind, value, amount=0, price=0, name="", col=0, row=0,
                 quality=Quality.NORMAL):
        self.kind = kind
        self.value = value
        self.amount = amount
        self.price = price
        self.name = name
        self.col = col  # the SHOP cell the offer is drawn in (never a board cell)
        self.row = row
        self.board_cell = None  # the board square the owned component lies on
        # The tier a golem left it at (see Quality): a component a golem has
        # combined wears its word in its name and its colour on its tile.
        self.quality = quality

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
    def shape_component(cls, value, price=None, name="", col=0, row=0,
                        quality=Quality.NORMAL):
        if price is None:
            price = COMPONENT_PRICES.get((cls.SHAPE, value), 0)
        return cls(cls.SHAPE, value, price=price, name=name or Shape.name(value),
                   col=col, row=row, quality=quality)

    @classmethod
    def effect_component(cls, value, price=None, name="", col=0, row=0, magnitude=None,
                         quality=Quality.NORMAL):
        """An effect piece. ``magnitude`` is its own rolled strength, which the
        piece CARRIES (its payoff and its description) but never pays for: the
        piece costs the catalog price however strongly it rolled."""
        if price is None:
            price = effect_component_price(value)
        return cls(cls.EFFECT, value, amount=magnitude or 0, price=price,
                   name=name or Effect.name(value), col=col, row=row,
                   quality=quality)

    @classmethod
    def scorer_component(cls, value, amount=0, price=None, name="", col=0, row=0,
                         quality=Quality.NORMAL):
        """A scorer piece. ``amount`` is its own rolled magnitude: it sets the
        piece's payoff, but never its price (see scorer_component_price)."""
        if price is None:
            price = scorer_component_price(value)
        return cls(cls.SCORER, value, amount=amount, price=price,
                   name=name or Scorer.name(value), col=col, row=row,
                   quality=quality)

    # COMMENTED OUT with the conditions: the condition component (the trigger
    # half a player bought and paired with a scorer in the card builder).
    #
    # @classmethod
    # def condition_component(cls, value, price=None, name="", col=0, row=0):
    #     if price is None:
    #         price = COMPONENT_PRICES.get((cls.CONDITION, value), 0)
    #     return cls(cls.CONDITION, value, price=price, name=name or condition_name(value), col=col, row=row)


class Group:
    """The FAMILY an item belongs to, and what that family is for.

    User request: "sort all items into groups, and show it in their description
    what group they are in." Every item the game can show belongs to exactly one
    group, DERIVED from what it is (Group.of — the same rule Keyword.of and
    Quality.of use), so an item can never be made in a group nobody can read,
    and its description says in one line what the group is for.

    User request: "join together cards, tools, and actions into one group called
    'cards'." A card, an action and a tool are one family (CARDS): they are the
    things the player KEEPS and plays, differing only in what holding one does —
    a card pays every run, an action fires once, a tool opens a structure.

    The group also sorts items: Group.ORDER is the reading order the deck's
    overlay lists a collection in (see Game.deck_overlay_items), so the deck
    reads by family — the block parts first, because they are what a hand is
    built from — rather than in the order things were bought.

    The kinds that are not the player's have groups of their own: a level's FOE
    and its PROPs (the sidebar describes them too, and what they are is the most
    useful thing to say about them) and a TRIAL, which is a way to play a run
    rather than an item — its group is what the collection's cells print on those
    entries, so every cell of the codex says what it is looking at.
    """
    BLOCK = 0
    PART = 1
    CARDS = 2
    STRUCTURE = 3
    PACK = 4
    PASSIVE = 5
    TOKEN = 6
    RESOURCE = 7
    FOE = 8
    PROP = 9
    TRIAL = 10

    NAMES: ClassVar[dict[int, str]] = {
        BLOCK: "Block", PART: "Part", CARDS: "Cards",
        STRUCTURE: "Structure", PACK: "Pack",
        PASSIVE: "Passive", TOKEN: "Token", RESOURCE: "Resource",
        FOE: "Foe", PROP: "Prop", TRIAL: "Trial",
    }
    # What each family is, in the one line its items' descriptions print.
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
        BLOCK: ("A square of board the marble bounces off and scores on: one "
                "shape, its effects and its scorer."),
        PART: ("A piece of a block — a shape, an effect or a scorer — laid out "
               "with the others and assembled into a block with S."),
        CARDS: ("Something you keep and play: it pays on its own, or is used "
                "once and spent, or opens a structure it is aimed at "
                "(the keywords say which)."),
        STRUCTURE: ("Scenery a tool opens into a card or a pack. It costs "
                    "nothing and is spent when it opens."),
        PACK: ("A bundle of offers: press S to deal its options and keep the "
               "ones you choose."),
        PASSIVE: ("Unplayable: it pays at the start of a run simply by being "
                  "owned."),
        TOKEN: ("A kept block: its scorer fires every run on its own, without a "
                "marble ever touching it."),
        RESOURCE: ("Points of one scorer, banked at once instead of kept as an "
                   "item."),
        FOE: ("The level's enemy: it fights back instead of scoring, and a "
              "marble's hit deals its chips x mult as damage."),
        PROP: ("The level's own furniture: it is part of the course and can "
               "never be taken up, sold or upgraded."),
        TRIAL: ("A way to play a run: it changes the rules for the run you "
                "play under it, and is beaten by finishing one."),
    }
    # Which item KIND makes up each group (see Component.SHAPE / _item_name). A
    # board block has no `kind` of its own; Group.of reads it as a "block".
    KINDS: ClassVar[dict[int, tuple]] = {
        BLOCK: ("block",),
        PART: (Component.SHAPE, Component.EFFECT, Component.SCORER),
        CARDS: ("card", "action", "tool"),
        STRUCTURE: ("structure",),
        PACK: ("pack",),
        PASSIVE: ("passive",),
        TOKEN: ("token",),
        RESOURCE: ("resource",),
        TRIAL: ("trial",),
    }
    # The colour a group's badge wears in an item's description (see
    # ui._draw_group_badge): one hue per family, so the group is recognisable
    # before a word of it is read. The whole CARDS family shares one hue, since
    # it is one family now.
    COLORS: ClassVar[dict[int, tuple]] = {
        BLOCK: (124, 172, 232),      # board blue
        PART: (146, 200, 116),       # the pieces a block is built from
        CARDS: (214, 138, 208),      # what you keep and play
        STRUCTURE: (170, 148, 126),  # scenery and clay
        PACK: (198, 198, 118),       # a bundle
        PASSIVE: (152, 152, 152),    # it just lies there
        TOKEN: (186, 158, 238),      # a kept block
        RESOURCE: (118, 190, 220),   # banked points
        FOE: (224, 96, 96),          # the level's enemy
        PROP: (146, 134, 122),       # the level's furniture
        TRIAL: (238, 168, 96),       # a way to play a run
    }
    ORDER: ClassVar[list[int]] = [BLOCK, PART, CARDS, STRUCTURE, PACK, PASSIVE,
                                  TOKEN, RESOURCE, FOE, PROP, TRIAL]

    @classmethod
    def name(cls, group):
        return cls.NAMES.get(group, "Item")

    @classmethod
    def description(cls, group):
        return cls.DESCRIPTIONS.get(group, "")

    @classmethod
    def color(cls, group):
        """The colour this group's badge wears (see ui._draw_group_badge)."""
        return cls.COLORS.get(group, (200, 200, 200))

    @classmethod
    def of_kind(cls, kind):
        """The group a bare item KIND belongs to, or None (see Group.KINDS)."""
        for group, kinds in cls.KINDS.items():
            if kind in kinds:
                return group
        return None

    @classmethod
    def of(cls, item):
        """The group an item is in, or None for something that is not an item.

        The level's own things say so first (an enemy is a Foe and its furniture
        a Prop, whatever they are built from), then the item's own kind decides.
        A Block standing on the board carries no kind, so it reads as a block;
        the top bar's readouts (Cash, Energy) are not items at all and have no
        group.
        """
        if item is None:
            return None
        if getattr(item, "is_enemy", False):
            return cls.FOE
        if getattr(item, "is_level_prop", False):
            return cls.PROP
        kind = getattr(item, "kind", None)
        if kind is None and hasattr(item, "rect"):
            kind = "block"
        return cls.of_kind(kind)

    @classmethod
    def rank(cls, group):
        """Where a group sorts (the index of its row in Group.ORDER)."""
        try:
            return cls.ORDER.index(group)
        except ValueError:
            return len(cls.ORDER)


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
    # A Key/Lock pair is bought as one offer that hands over both halves (see
    # Game._buy_shop_item / _keep_pack_block), so its shape price is what the
    # pair costs: 6x the old $8/$10 (user request: "make locks and keys each
    # cost 6x more"). A block is priced at 75% of its parts, so a bare Key block
    # goes $10 -> $40 and a bare Lock block $12 -> $49.
    (Component.SHAPE, Shape.KEY): 48,
    (Component.SHAPE, Shape.LOCK): 60,
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
    # The gondola is a moving platform: dearer than a static wall effect (it
    # patrols a whole lane and can carry a marble with it), but nowhere near
    # the splitter's "another marble" price.
    (Component.EFFECT, Effect.GONDOLA): 46,
    # Wasteful does nothing to the marble: it is a build-phase ability, worth
    # about an ordinary wall effect.
    (Component.EFFECT, Effect.WASTEFUL): 30,
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
    (Component.SCORER, Scorer.PACKED): 24,
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


# --- Item packs: what one option is worth ------------------------------------
# A pack's price is the average value of ONE of its options times a size
# factor (see Pack.SIZE_PRICE_FACTORS), so the two helpers below answer "what
# is one option of this type worth?" from the catalogue itself rather than from
# a hand-written table: rebalancing a component, a card or an action re-prices
# every pack that deals it, and no pack can drift out of step with the shop it
# sits in.
#
# "Worth" means what a DRAW of that pool is worth, not the plain average: the
# shop weights an offer by 1/price (see main.component_weight — dearer items
# are rarer), so an expensive outlier takes up far less of the pool than it
# would by count. The expected price of a drawn item is therefore the HARMONIC
# mean of the pool's prices, which is what keeps one $124 Splitter from pricing
# every effect pack at Splitter money.
def _drawn_average(prices):
    """The average price of an item drawn the way the shop draws it (see above)."""
    prices = [price for price in prices if price > 0]
    if not prices:
        return 0.0
    return len(prices) / sum(1.0 / price for price in prices)


def _flat_average(prices):
    """The plain average price of a pool drawn evenly (actions, cards a tier)."""
    prices = [price for price in prices if price > 0]
    return sum(prices) / len(prices) if prices else 0.0


# The average number of effects a randomly built block carries, from
# main.random_effect_count: no effect 1/4 of the time, and a geometric count
# after that (1 for 1/2, 2 for 1/4, ...), which averages 1.5.
AVERAGE_BLOCK_EFFECTS = 1.5


def shape_pool_prices():
    """Every shape the shop sells, as a price (Rect is never sold loose)."""
    return [COMPONENT_PRICES.get((Component.SHAPE, shape), 0)
            for shape in Shape.ORDER if shape != Shape.RECT]


def effect_pool_prices():
    """Every effect the shop sells, as a price."""
    return [effect_component_price(effect) for effect in Effect.REAL_ORDER]


def scorer_pool_prices():
    """Every scorer the shop sells, as a price (None is never sold)."""
    return [scorer_component_price(scorer) for scorer in Scorer.SHOP_ORDER
            if scorer != Scorer.NONE]


def card_pool_prices():
    """(price, rarity) for every card the shop can offer.

    The whole cards carry their own tier and price; every match-group card is
    Common (see Rarity) and priced by its group (see match_group_price), so one
    entry per group stands for all the group's cards — the shop draws the group
    and rolls the scorer's magnitude, which never changes the price.
    """
    entries = [(Card.PRICES.get(value, 20), Card.rarity(value))
               for value in Card.ORDER]
    entries += [(match_group_price(group), Rarity.COMMON)
                for group in MATCH_GROUPS]
    return entries


def average_card_price():
    """What one shop card offer is worth, tier odds and all.

    The shop draws the TIER first, by Rarity.WEIGHTS, and the card flat inside
    the drawn tier (see main.random_card_option_value), so the expected price is
    the tier-weighted average of each tier's own average — NOT the plain average
    over every card, which would count the 26 Common match groups 26 times over.
    """
    entries = card_pool_prices()
    if not entries:
        return 0.0
    # The tier weights are RELATIVE to each other, so the divisor is the sum of
    # the TIERS' weights — one term each, however many cards carry the tier.
    total_weight = sum(Rarity.weight(tier) for tier in Rarity.ORDER) or 1.0
    total = 0.0
    for tier in Rarity.ORDER:
        prices = [price for price, rarity in entries if rarity == tier]
        total += Rarity.weight(tier) * _flat_average(prices)
    return total / total_weight


def pack_base_price(pack_type):
    """The average value of ONE option of a pack of this type.

    * a shape/effect/scorer pack deals that pool, drawn as the shop draws it;
    * a PART pack draws its kind evenly, so it is worth the mean of the three;
    * a BLOCK pack deals ready-made blocks, whose price is 75% of the sum of
      their parts (see block_price_for): one shape, one scorer and the average
      1.5 effects a random block rolls (see main.random_effect_count);
    * a CARD pack deals shop card offers (see average_card_price);
    * an ACTION pack deals actions, drawn evenly from the catalogue;
    * a RESOURCE pack deals resource points, each worth RESOURCE_PACK_FACTOR
      times what a trigger banks: the average option is worth that many points
      times the price of ONE conversion (a card, a block or an action — the
      three things a point buys; a permanent shop slot is a fourth reward and
      is left out of this average, so the points are priced a little shy of
      what they can be worth);
    * a RANDOM pack deals any of the above evenly.
    """
    if pack_type == Pack.SHAPE:
        return _drawn_average(shape_pool_prices())
    if pack_type == Pack.EFFECT:
        return _drawn_average(effect_pool_prices())
    if pack_type == Pack.SCORER:
        return _drawn_average(scorer_pool_prices())
    if pack_type == Pack.PART:
        return _flat_average([pack_base_price(kind)
                              for kind in Pack.PART_SOURCES])
    if pack_type == Pack.BLOCK:
        return 0.75 * (_drawn_average(shape_pool_prices())
                       + _flat_average(effect_pool_prices()) * AVERAGE_BLOCK_EFFECTS
                       + _drawn_average(scorer_pool_prices()))
    if pack_type == Pack.CARD:
        return average_card_price()
    if pack_type == Pack.ACTION:
        return _flat_average(list(Action.PRICES.values()))
    if pack_type == Pack.TOOL:
        return _flat_average([Tool.PRICES[value] for value in Tool.PACK_ORDER]
                             + [Passive.PRICES[value] for value in Passive.ORDER])
    if pack_type == Pack.RESOURCE:
        scorers = list(Scorer.RESOURCE_RATE)
        points = _flat_average([RESOURCE_PACK_FACTOR
                                * resource_points_for(scorer,
                                                      Scorer.DEFAULT_AMOUNT.get(scorer, 0))
                                for scorer in scorers])
        conversion = _flat_average([pack_base_price(Pack.CARD),
                                    pack_base_price(Pack.BLOCK),
                                    pack_base_price(Pack.ACTION)])
        return points * conversion
    if pack_type == Pack.RANDOM:
        return _flat_average([pack_base_price(kind)
                              for kind in Pack.RANDOM_SOURCES])
    return 0.0


# What a pack of any type OTHER than a shape pack multiplies its price by: the
# shape pack is the one type sold at what its options are worth (see pack_price).
NON_SHAPE_PACK_PRICE_FACTOR = 0.5


def pack_price(pack_type, size):
    """A pack's price: one option's value x the size's multiplier (see Pack).

    Rounded down to a whole dollar and never free, and blind to the options the
    pack actually rolled: two jumbo shape packs cost the same however well or
    badly their five shapes landed, exactly as a component's own roll never
    changes its price (see scorer_component_price).

    A SHAPE pack is the one type sold at par; every other pack goes for
    NON_SHAPE_PACK_PRICE_FACTOR of what its options are worth.
    """
    base = pack_base_price(pack_type) * Pack.SIZE_PRICE_FACTORS.get(size, 1.0)
    if pack_type != Pack.SHAPE:
        base *= NON_SHAPE_PACK_PRICE_FACTOR
    return max(1, int(base))


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
    # units, so it is the same 1 on the starter board as on a board that
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
        per_unit = int(MAGNITUDES.CHIPS_PER_UNIT * scale * ratio + 0.5)
        return (round(per_unit * units), 0, 1.0)
    if scorer == Scorer.MULT_ADD:
        return (0, MAGNITUDES.MULT_PER_UNIT * scale * ratio * units, 1.0)
    return (0, 0, 1 + MAGNITUDES.XMULT_PER_UNIT * scale * ratio * units)


def payoff_text(chips, mult, factor):
    """A payoff tuple (see magnitude_payoff) as text: "+80 chips", "+12 mult",
    "x5 mult" — or "nothing" when the measure came to nothing at all (a card
    whose gate is shut pays no units, so it pays nothing)."""
    if chips:
        return f"+{chips:g} chip{_plural(chips)}"
    if mult:
        return f"+{mult:g} mult"
    if factor == 1:
        return "nothing"
    return f"x{factor:g} mult"


def _format_amount(scorer, ratio, scale=1.0, dev=""):
    """A short per-unit payoff phrase for a unit scorer at a condition's ratio.

    e.g. (+Chips, 0.5) -> "+15 chips"; (xMult, 0.75) -> "x1.19 mult". ``scale``
    is the card's own scorer magnitude relative to the average, and ``dev`` the
    "(+2)" token that follows the magnitude.
    """
    if scorer == Scorer.CHIPS_ADD:
        n = int(MAGNITUDES.CHIPS_PER_UNIT * scale * ratio + 0.5)
        return f"+{n} chips{dev}" if n != 1 else f"+1 chip{dev}"
    if scorer == Scorer.MULT_ADD:
        n = MAGNITUDES.MULT_PER_UNIT * scale * ratio
        s = f"{n:.3f}".rstrip("0").rstrip(".")
        return f"+{s} mult{dev}"
    factor = 1 + MAGNITUDES.XMULT_PER_UNIT * scale * ratio
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
        return (f"{points_text(resource_points_for(Scorer.PICKY, amount))} structure "
                f"point{_plural_points(resource_points_for(Scorer.PICKY, amount))}{pdev}")
    if scorer == Scorer.FRESH:
        return f"{amount:g} Reroll card{_plural(amount)}{dev}"
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
        return (f"{amount:g} Board Unit{_plural(amount)}{dev} after the run, each "
                "opening a locked square you pick")
    if scorer == Scorer.PACKED:
        return (f"{amount:g} inventory slot{_plural(amount)}{dev} when touched, "
                "kept for good")
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
    Scorer.RANDOM: f"+{MAGNITUDES.RANDOM_CHIPS} chips, "
                   f"+{MAGNITUDES.RANDOM_MULT:g} mult, or "
                   f"+{MAGNITUDES.RANDOM_XMULT:g} xMult at random",
    Scorer.ECHO: "another trigger of the same block's own scorer",
    Scorer.GILDED: f"1/{MAGNITUDES.GILDED_DIVISOR:g} of your current chips as mult",
    Scorer.BOMB: "a bomb on that block, unlocking the units around it after a run",
    Scorer.LUCKY: f"a 1/3 chance of {MAGNITUDES.LUCKY_CHIPS} chips and a 1/9 "
                  f"chance of ${MAGNITUDES.LUCKY_CASH}",
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
# The pipe group, by name: the shapes the Fountain whole card watches (it
# counts the blocks of a marble's contacts that are in it — see Game's pipe
# streak counters) and the first group of SHAPE_GROUPS below, so the card and
# the match-group catalogue can never disagree about what a pipe is.
PIPE_GROUP_SHAPES = (Shape.PIPE, Shape.DRAIN, Shape.PIPE_BEND)
SHAPE_GROUPS = (
    PIPE_GROUP_SHAPES,
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
        gain = amount or Scorer.DEFAULT_AMOUNT.get(Scorer.SUMMIT, 0)
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

# =============================================================================
# LEVELS
#
# A game is 8 rounds of 3 runs (24 RUNS), and every run is one LEVEL (user
# request: "instead of having a score requirement, create levels where each
# level has a different set of structures and enemies, and different parts of
# the board are unlocked"). A level is WON when every enemy in it is defeated
# and every marble has reached the Finish; the player may give up on a level at
# any time with Y, which counts it as lost (three lost levels end the game).
# =============================================================================


class EnemyKind:
    """The kinds of enemy a level can hold (see enemies.Enemy for the brains)."""

    IDLE = 0        # a sitting target
    PATROL = 1      # slides back and forth along its row
    FLEE = 2        # runs away from the nearest marble
    ARMOURED = 3    # only a limited number of hits land on it
    DEVOURER = 4    # eats the marble that touches it

    ORDER = (IDLE, PATROL, FLEE, ARMOURED, DEVOURER)


ENEMY_NAMES = {
    EnemyKind.IDLE: "Slime",
    EnemyKind.PATROL: "Drifter",
    EnemyKind.FLEE: "Coward",
    EnemyKind.ARMOURED: "Beetle",
    EnemyKind.DEVOURER: "Maw",
}

ENEMY_DESCRIPTIONS = {
    EnemyKind.IDLE: "Sits still and takes whatever the marble deals it",
    EnemyKind.PATROL: "Slides back and forth along its row",
    EnemyKind.FLEE: "Runs away from the nearest marble",
    EnemyKind.ARMOURED: "Only a few hits land on it, so each one must count",
    EnemyKind.DEVOURER: "Swallows the marble that touches it",
}

# How much of a LEVEL's health budget one enemy of each kind is worth, relative
# to the others. A level's TOTAL health is what its run used to ask for as a
# score (see Level.enemy_health and Game._level_health_budget), so these shares
# only decide how that total is split between the enemies standing in it: a Maw
# soaks about twice what a Slime does, whatever the level asks for. An enemy
# built with no budget to split (a hand-placed one, a test) wears its share as
# its health, and a marble deals chips x mult with each hit.
ENEMY_HP_SHARE = {
    EnemyKind.IDLE: 240,
    EnemyKind.PATROL: 260,
    EnemyKind.FLEE: 380,
    EnemyKind.ARMOURED: 240,
    EnemyKind.DEVOURER: 520,
}


def split_enemy_health(kinds, budget):
    """Split a level's health budget between its enemies: whole numbers, exact.

    ``kinds`` are the enemies' EnemyKinds and ``budget`` is the damage the level
    asks for in total -- the score its run used to require before levels
    replaced the score target (user request: "make the sum of all enemies'
    health equal to the total required score that was originally there"). The
    split follows ENEMY_HP_SHARE, and the LAST hit of the share-out is what keeps
    the promise: the remainders are handed out one point at a time, largest
    remainder first, so the enemies always add up to the budget exactly rather
    than to "about" it. Every enemy gets at least 1 point, so a run whose target
    is 0 still puts a real (if feeble) obstacle on the board.
    """
    kinds = tuple(kinds)
    if not kinds:
        return ()
    budget = max(int(budget), len(kinds))
    weights = [ENEMY_HP_SHARE.get(kind, ENEMY_HP_SHARE[EnemyKind.IDLE])
               for kind in kinds]
    total = sum(weights)
    health = [budget * weight // total for weight in weights]
    # Hand the rounding remainder to the enemies with the most left over, so no
    # point of the budget is lost to the floor division above.
    remainders = sorted(range(len(kinds)),
                        key=lambda index: (-(budget * weights[index] % total),
                                           index))
    for index in remainders[:budget - sum(health)]:
        health[index] += 1
    return tuple(health)

# How many hits an ARMOURED enemy can take at all (damage past the last one is
# ignored, so a huge single hit cannot carry through).
ARMOURED_HITS = 3

ENEMY_COLORS = {
    EnemyKind.IDLE: (196, 84, 120),
    EnemyKind.PATROL: (188, 132, 72),
    EnemyKind.FLEE: (120, 148, 196),
    EnemyKind.ARMOURED: (96, 128, 96),
    EnemyKind.DEVOURER: (150, 84, 190),
}


# The blocks a level may place as its own furniture, keyed by the marker a
# level's props use. A marker says only WHICH prop stands on a square; the shape,
# effect and angle are the same data every other block is built from (see
# Game._place_level_props). Accelerator angles follow Block's own convention:
# 0 pushes up, 90 right, 180 down, 270 left (the direction its arrow points).
PROP_PARTS = {
    "w": {"shape": Shape.RECT},                                    # plain wall
    "o": {"shape": Shape.RECT, "effects": (Effect.BOUNCY,)},        # bouncy
    "x": {"shape": Shape.RECT, "effects": (Effect.PHASE,)},         # phase
    "t": {"shape": Shape.RECT, "effects": (Effect.PISTON,)},        # piston
    "~": {"shape": Shape.RECT, "effects": (Effect.SLIPPERY,)},      # ice
    "g": {"shape": Shape.RECT, "effects": (Effect.GONDOLA,)},       # cable car
    "^": {"shape": Shape.RECT, "effects": (Effect.ACCELERATOR,), "angle": 0},
    ">": {"shape": Shape.RECT, "effects": (Effect.ACCELERATOR,), "angle": 90},
    "v": {"shape": Shape.RECT, "effects": (Effect.ACCELERATOR,), "angle": 180},
    "<": {"shape": Shape.RECT, "effects": (Effect.ACCELERATOR,), "angle": 270},
    "/": {"shape": Shape.SLOPE, "angle": 0},                        # ramp up-right
    "\\": {"shape": Shape.SLOPE, "angle": 90},                       # ramp up-left
    "-": {"shape": Shape.FLAT_LINE},                                # shelf
    "k": {"shape": Shape.KEY, "key_number": 1},                     # key
    "l": {"shape": Shape.LOCK, "key_number": 1},                    # its lock
}


# How many structures a level puts out every run (user request: "have 4
# structures each run instead of 1"). A level authors the KINDS that suit it and
# Level._plan_structures repeats them up to this many, so the board always holds
# four things worth a tool -- one more than the three energy a run is given,
# which is the choice the structures are there to pose.
STRUCTURES_PER_RUN = 4


class Level:
    """One level: its squares, the props on them, its enemies and structures.

    ``parts`` builds the level's own set of pre-unlocked board squares from
    (kind, dx, dy, width, height) rectangles offset from the CENTRE square of the
    board: "rect" adds squares, "hole" takes them away again. Every level opens
    about the same NUMBER of squares but in a different SHAPE -- a wide arena, a
    hole-punched field, two tiers joined by a neck, an hourglass shaft, a tower, a
    cross, two rooms and a corridor, a ring, corner rooms joined by thin
    corridors, detached islands -- so the board itself is what makes a level feel
    different.

    ``props`` are the blocks the level places for the player, ("^", dx, dy) etc
    (see PROP_PARTS): walls to bounce off, bouncers, accelerators to climb with,
    phase blocks, slopes, shelves, a key and its lock.

    ``enemies`` are (kind, dx, dy) placements. An enemy placed on a square the
    level does NOT open is BURIED: it is drawn inside the wall and can only be
    reached once the player buys that square (or phases into it), which is what
    makes those levels a decision about Board Units. Enemies placed at opposite
    ends of the board force the marble to be driven upwards with pistons and
    accelerators. What an enemy is WORTH in health is not stored here: a level's
    total health is the score its run used to require (see enemy_health), split
    between its enemies by kind.

    ``structures`` are the structure kinds the level puts out, and every level
    offers STRUCTURES_PER_RUN of them: the list repeats until it is four long, so
    a level that authors one pit hands out four pits and a level that authors
    pit/pool/mirror hands out those three plus a second pit.
    """

    def __init__(self, number, name, parts, props, enemies, structures):
        self.number = number
        self.name = name
        self.parts = parts
        self.props = props
        # The structures this level puts on its own squares (user request: "add
        # structures as part of the level"): the shop deals nothing any more, so
        # a pit, a crystal pool or a mirror is a piece of the LEVEL, standing on
        # one of the squares the level opens and opened with a tool like any
        # other structure.
        self.authored_structures = tuple(structures)
        self.structures = self._plan_structures(structures)
        self.cells = self._cells(parts)
        self.enemy_spawns = tuple(enemies)
        self.enemies = tuple(kind for kind, _, _ in enemies)
        self.structure_spawns = self._structure_spawns()

    @staticmethod
    def _plan_structures(values):
        """The structures a run of this level actually lays out.

        Every run gets STRUCTURES_PER_RUN of them (user request: "have 4
        structures each run instead of 1"), so the level's own kinds repeat until
        the board holds four: a pit level hands out four pits, a level that
        authored pit/pool/mirror hands out those three and a pit again.
        """
        values = tuple(values)
        if not values:
            return ()
        return tuple(values[index % len(values)]
                     for index in range(STRUCTURES_PER_RUN))

    @staticmethod
    def _cells(parts):
        """The squares a level's rectangles add and its holes take away."""
        cells = set()
        for kind, dx, dy, width, height in parts:
            for x in range(dx, dx + width):
                for y in range(dy, dy + height):
                    if kind == "rect":
                        cells.add((x, y))
                    else:
                        cells.discard((x, y))
        return frozenset(cells)

    @property
    def enemy_count(self):
        return len(self.enemies)

    def enemy_health(self, budget, kinds=None):
        """How much health each enemy of this level gets out of ``budget``.

        ``budget`` is the damage the whole level asks for -- the score its run
        used to require before levels replaced the score target -- so the
        enemies' health always adds up to it (see split_enemy_health). ``kinds``
        defaults to the level's own cast; the game passes the enemies it actually
        placed, which is how a level whose square was already taken still spends
        its whole budget on the enemies that did make it onto the board.
        """
        if kinds is None:
            kinds = self.enemies
        return split_enemy_health(kinds, budget)

    def _structure_spawns(self):
        """Where this level's structures stand: spread through its own squares.

        The level's free squares (see below) are cut into one slice per
        structure and each structure takes the middle of its slice, so four of
        them land near each end of the level and at even intervals between --
        four structures down one diagonal would leave the rest of the board with
        nothing to open. A square the level already uses for a prop or an enemy
        is passed over: a structure must neither stand on the level's own
        furniture nor take an enemy's square (it is the LEVEL's thing, and the
        level's shape is what decides where its cast and its scenery go).
        """
        cells = sorted(self.cells, key=lambda cell: (cell[1], cell[0]))
        values = getattr(self, "structures", ())
        if not cells or not values:
            return ()
        busy = {(dx, dy) for _, dx, dy in self.enemy_spawns}
        busy |= {(dx, dy) for _, dx, dy in self.props}
        free = [cell for cell in cells if cell not in busy] or cells
        count = len(values)
        spawns = []
        for index, value in enumerate(values):
            start = index * len(free) // count
            stop = max(start + 1, (index + 1) * len(free) // count)
            dx, dy = free[(start + stop - 1) // 2]
            spawns.append((value, dx, dy))
        return tuple(spawns)

    def is_buried(self, dx, dy):
        """True when the square is one the level does NOT open (an enemy in a wall)."""
        return (dx, dy) not in self.cells

    @property
    def size(self):
        """The level's footprint in squares (its bounding box)."""
        xs = [x for x, _ in self.cells]
        ys = [y for _, y in self.cells]
        return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Level({self.number}, {self.name!r})"


LEVELS = (
    # --- Slime Garden: the plain shapes -------------------------------------
    Level(1, "Slime Garden",
          (("rect", -4, -3, 9, 6),),
          (),
          ((EnemyKind.IDLE, 0, 0),),
          (Structure.PIT,)),
    Level(2, "Slime Garden",
          (("rect", -5, -3, 10, 6), ("hole", -1, -1, 2, 2)),
          (("w", 0, -3), ("w", 0, 2)),
          ((EnemyKind.PATROL, -3, 0), (EnemyKind.IDLE, 2, 1)),
          (Structure.PIT, Structure.SHED)),
    Level(3, "Slime Garden",
          (("rect", -4, -3, 8, 7),),
          (("o", -3, 2), ("o", 3, 2), ("o", 0, -3)),
          ((EnemyKind.IDLE, 0, -2), (EnemyKind.PATROL, 0, 2)),
          (Structure.PIT, Structure.CRYSTAL_POOL)),
    # --- Crystal Shore: things separated ------------------------------------
    Level(4, "Crystal Shore",
          (("rect", -5, -4, 9, 3), ("rect", -4, 1, 9, 3), ("rect", -1, -1, 2, 1)),
          (("/", 0, -1), ("<", -4, 2), ("-", -4, -4), ("-", 3, -4)),
          ((EnemyKind.PATROL, -2, -3), (EnemyKind.IDLE, 1, 2)),
          (Structure.CRYSTAL_POOL, Structure.QUARRY)),
    Level(5, "Crystal Shore",
          (("rect", -5, -4, 10, 2), ("rect", -5, 2, 10, 2), ("rect", -1, -2, 2, 4)),
          (("o", -4, -4), ("o", 3, -4), ("o", -4, 3), ("o", 3, 3)),
          ((EnemyKind.FLEE, 0, -4), (EnemyKind.PATROL, 0, 3)),
          (Structure.CRYSTAL_POOL, Structure.SHRINE)),
    Level(6, "Crystal Shore",
          (("rect", -4, -2, 9, 5), ("rect", 0, 4, 2, 2)),
          (("x", 0, 2),),
          ((EnemyKind.IDLE, 0, 0), (EnemyKind.IDLE, 0, 4)),
          (Structure.CRYSTAL_POOL, Structure.MIRROR, Structure.GOLEM)),
    # --- Mirror Halls: vertical play ---------------------------------------
    Level(7, "Mirror Halls",
          (("rect", -4, -4, 8, 3), ("rect", -4, 1, 8, 3),
           ("rect", -4, -1, 1, 2), ("rect", 3, -1, 1, 2)),
          (("^", -4, 2), ("^", 3, 2), ("g", -4, 0), ("-", -4, -4), ("-", 3, -4)),
          ((EnemyKind.IDLE, 0, -3), (EnemyKind.IDLE, -3, 2)),
          (Structure.MIRROR, Structure.VAULT)),
    Level(8, "Mirror Halls",
          (("rect", -2, -4, 4, 9), ("rect", -5, -1, 10, 3)),
          (("o", -5, 0), ("o", 4, 0)),
          ((EnemyKind.IDLE, 0, -4), (EnemyKind.PATROL, -4, 0),
           (EnemyKind.ARMOURED, 0, 4)),
          (Structure.MIRROR, Structure.LIBRARY)),
    Level(9, "Mirror Halls",
          (("rect", -5, -2, 4, 5), ("rect", -1, -1, 4, 2), ("rect", 3, -2, 4, 5)),
          (("x", 0, -1), ("/", -5, -2), ("/", 6, -2)),
          ((EnemyKind.FLEE, -4, 0), (EnemyKind.ARMOURED, 0, 0),
           (EnemyKind.IDLE, 4, 0)),
          (Structure.MIRROR, Structure.PIT, Structure.GOLEM)),
    # --- Deep Pits: holes and buried things --------------------------------
    Level(10, "Deep Pits",
          (("rect", -5, -3, 10, 6), ("hole", -3, -1, 2, 2), ("hole", 1, -1, 2, 2)),
          (("o", -5, 2), ("o", 4, 2)),
          ((EnemyKind.PATROL, 0, -3), (EnemyKind.IDLE, 5, -3)),
          (Structure.PIT, Structure.MINT)),
    Level(11, "Deep Pits",
          (("rect", -5, -4, 2, 9), ("rect", -3, -1, 7, 2), ("rect", 3, -4, 2, 9)),
          (("\\", -5, 0), ("/", 4, 0)),
          ((EnemyKind.IDLE, -5, -4), (EnemyKind.DEVOURER, 0, 0),
           (EnemyKind.IDLE, 4, 4)),
          (Structure.PIT, Structure.DEPOT)),
    Level(12, "Deep Pits",
          (("rect", -5, -2, 5, 5), ("rect", 1, -2, 5, 5)),
          (("-", -4, 2), ("-", 4, 2)),
          ((EnemyKind.DEVOURER, 0, 0), (EnemyKind.IDLE, -3, 0),
           (EnemyKind.ARMOURED, 3, 0), (EnemyKind.DEVOURER, 5, 3)),
          (Structure.PIT, Structure.CRYSTAL_POOL, Structure.GOLEM)),
    # --- The Cold Field: ice, shelves, stairs -------------------------------
    Level(13, "The Cold Field",
          (("rect", -5, -2, 11, 5), ("hole", -4, -2, 2, 2), ("hole", 2, 1, 2, 2)),
          (("~", -3, 2), ("~", -2, 2), ("~", -1, 2), ("~", 1, 2),
           ("-", -5, 0), ("-", 5, 0)),
          ((EnemyKind.FLEE, -4, 0), (EnemyKind.ARMOURED, 0, 0),
           (EnemyKind.IDLE, 4, 2)),
          (Structure.CRYSTAL_POOL, Structure.MIRROR, Structure.CABINET)),
    Level(14, "The Cold Field",
          (("rect", -5, 2, 10, 2), ("rect", -5, 0, 4, 2), ("rect", -2, -2, 4, 2),
           ("rect", 1, -4, 4, 2), ("rect", 4, -2, 2, 4)),
          (("/", -5, 0), ("/", -2, -2), ("/", 1, -4), ("~", 1, 2), ("~", 3, 2)),
          ((EnemyKind.IDLE, 3, -4), (EnemyKind.PATROL, -3, 2)),
          (Structure.CRYSTAL_POOL, Structure.WORKBENCH)),
    Level(15, "The Cold Field",
          (("rect", -5, -4, 10, 8), ("hole", -3, -2, 6, 4)),
          (("~", -2, -4), ("~", 2, -4), ("~", -2, 3), ("~", 2, 3)),
          ((EnemyKind.PATROL, -4, 0), (EnemyKind.ARMOURED, 0, -4),
           (EnemyKind.FLEE, 4, 0)),
          (Structure.MIRROR, Structure.RIFT)),
    # --- Hollow Spire: tall things -----------------------------------------
    Level(16, "Hollow Spire",
          (("rect", -2, -5, 5, 11),),
          (("-", -2, -3), ("-", 2, -1), ("-", -2, 1), ("-", 2, 3), ("^", 0, 4)),
          ((EnemyKind.IDLE, 0, -5), (EnemyKind.ARMOURED, 0, 0),
           (EnemyKind.DEVOURER, 0, 5)),
          (Structure.PIT, Structure.MIRROR, Structure.GOLEM)),
    Level(17, "Hollow Spire",
          (("rect", -5, -4, 3, 3), ("rect", 3, -4, 3, 3),
           ("rect", -5, 2, 3, 3), ("rect", 3, 2, 3, 3),
           ("rect", 0, -3, 1, 1), ("rect", -2, -3, 5, 1), ("rect", 0, 3, 1, 1),
           ("rect", -2, 3, 5, 1), ("rect", 0, 0, 1, 1)),
          (("o", -4, -2), ("o", 4, -2), ("o", -4, 2), ("o", 4, 2)),
          ((EnemyKind.ARMOURED, -4, -4), (EnemyKind.PATROL, 4, -4),
           (EnemyKind.FLEE, -4, 3), (EnemyKind.IDLE, 4, 3),
           (EnemyKind.DEVOURER, 0, 0)),
          (Structure.PIT, Structure.CRYSTAL_POOL, Structure.SHED)),
    Level(18, "Hollow Spire",
          (("rect", -4, -3, 9, 6), ("hole", -2, -1, 2, 2)),
          (("k", -4, -3), ("l", 0, 1)),
          ((EnemyKind.DEVOURER, 0, 2), (EnemyKind.PATROL, -3, 0)),
          (Structure.PIT, Structure.MIRROR, Structure.GOLEM, Structure.QUARRY)),
    # --- Glass Cathedral: naves, columns, rings ----------------------------
    Level(19, "Glass Cathedral",
          (("rect", -5, 1, 10, 3), ("rect", -5, -4, 10, 2),
           ("rect", -4, -2, 1, 3), ("rect", 3, -2, 1, 3)),
          (("o", -5, -4), ("o", 4, -4), ("^", -4, 2), ("^", 3, 2)),
          ((EnemyKind.ARMOURED, -4, -4), (EnemyKind.PATROL, 0, 1),
           (EnemyKind.IDLE, 4, 2)),
          (Structure.MIRROR, Structure.CRYSTAL_POOL)),
    Level(20, "Glass Cathedral",
          (("rect", -5, -2, 5, 5), ("rect", 1, -3, 3, 3), ("rect", 0, 3, 3, 3),
           ("rect", 4, 1, 2, 2)),
          (("x", -3, 0), ("x", 2, -3), ("x", 1, 3), ("v", 4, 1)),
          ((EnemyKind.IDLE, -4, 0), (EnemyKind.ARMOURED, 2, -2),
           (EnemyKind.FLEE, 1, 4)),
          (Structure.MIRROR, Structure.SHRINE, Structure.VAULT)),
    Level(21, "Glass Cathedral",
          (("rect", -5, -4, 10, 2), ("rect", -5, -2, 2, 6), ("rect", 3, -2, 2, 6),
           ("rect", -1, 4, 4, 1)),
          (("^", -4, -1), ("^", 4, 2)),
          ((EnemyKind.IDLE, 0, -4), (EnemyKind.PATROL, -4, 0),
           (EnemyKind.FLEE, 4, 1), (EnemyKind.ARMOURED, 0, 4)),
          (Structure.PIT, Structure.MIRROR, Structure.GOLEM)),
    # --- The Last Marble: the big finishes ---------------------------------
    Level(22, "The Last Marble",
          (("rect", -5, -2, 11, 5),),
          (("w", -3, -2), ("w", 3, -2), ("w", -3, 2), ("w", 3, 2),
           ("o", -5, 0), ("o", 5, 0)),
          ((EnemyKind.ARMOURED, -4, 0), (EnemyKind.FLEE, 4, 0),
           (EnemyKind.PATROL, 0, -2), (EnemyKind.IDLE, 0, 2),
           (EnemyKind.DEVOURER, 0, 0)),
          (Structure.PIT, Structure.CRYSTAL_POOL, Structure.MIRROR, Structure.GOLEM)),
    Level(23, "The Last Marble",
          (("rect", -4, -4, 8, 3), ("rect", -4, 2, 8, 3), ("rect", -1, -1, 2, 3)),
          (("^", -3, 2), ("^", 2, 2), (">", -4, 3), ("t", 0, 1)),
          ((EnemyKind.ARMOURED, -3, -3), (EnemyKind.PATROL, 2, -3),
           (EnemyKind.DEVOURER, 0, 3)),
          (Structure.CRYSTAL_POOL, Structure.MIRROR, Structure.GOLEM,
           Structure.LIBRARY)),
    Level(24, "The Last Marble",
          (("rect", -5, -2, 10, 5), ("rect", -2, -5, 2, 2), ("rect", 2, 4, 2, 2)),
          (("o", -5, -2), ("o", 4, 1), ("^", 0, 2), ("x", -5, 2)),
          ((EnemyKind.DEVOURER, 0, 0), (EnemyKind.ARMOURED, -4, -2),
           (EnemyKind.ARMOURED, 4, 2), (EnemyKind.FLEE, -4, 2),
           (EnemyKind.FLEE, 4, -2), (EnemyKind.IDLE, -2, -5),
           (EnemyKind.IDLE, 2, 4), (EnemyKind.PATROL, 0, -2)),
          (Structure.PIT, Structure.CRYSTAL_POOL, Structure.MIRROR,
           Structure.GOLEM, Structure.QUARRY, Structure.SHRINE,
           Structure.VAULT, Structure.WORKBENCH, Structure.DEPOT,
           Structure.LIBRARY, Structure.CABINET, Structure.MINT,
           Structure.RIFT, Structure.SHED)),
)


def level_for(run_number):
    """The Level a run of the game plays (run 0 is level 1; the last level repeats)."""
    index = min(max(int(run_number), 0), len(LEVELS) - 1)
    return LEVELS[index]
