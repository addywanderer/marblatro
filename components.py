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
    CRADLE = 18  # a V-shaped valley (two side wedges) that catches the marble
    BUMP = 19  # a solid half-disc dome along the bottom edge (a speed bump)
    KEY = 20  # a pass-through key pickup: touching it opens its matching lock
    LOCK = 21  # a solid locked door: blocks the marble until its key is touched

    NAMES: ClassVar[dict[int, str]] = {RECT: "Rect", SLOPE: "Slope", LINE: "Line", \
                                       NONE: "None", CIRCLE: "Circle", CURVED_SLOPE: "Curved Slope", \
                                       PIPE: "Pipe", DRAIN: "Drain", PIPE_BEND: "Pipe Bend", \
                                       CONVEX_SLOPE: "Convex Slope", FLAT_LINE: "Flat Line", \
                                       CURVED_SLOPE_LINE: "Curved Slope Line", HALF_PIPE: "Half Pipe", \
                                       SPIKE: "Spike", PLATFORM: "Platform", CORNER: "Corner", \
                                       PEG: "Peg", SAWTOOTH: "Sawtooth", CRADLE: "Cradle", \
                                       BUMP: "Bump", KEY: "Key", LOCK: "Lock"}
    ORDER: ClassVar[list[int]] = [RECT, SLOPE, LINE, NONE, CIRCLE, CURVED_SLOPE, PIPE, DRAIN, PIPE_BEND,
                                  CONVEX_SLOPE, FLAT_LINE, CURVED_SLOPE_LINE, HALF_PIPE,
                                  SPIKE, PLATFORM, CORNER, PEG, SAWTOOTH, CRADLE, BUMP,
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
    PARTS = 9
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
    DEBT = 34  # +120 chips, but the run pays no interest afterwards

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
        DEBT: 120,  # 120 chips per trigger
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
    # magnitude, so a 3-magnitude Rubble banks 1.5 points a trigger. Parts and
    # Fresh grant their reward instantly and bank nothing.
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
        HANDS_TIED: "Disables the scoring effect of a random 1/4 of blocks.",
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


class Card:
    """An indivisible whole card bought from the shop.

    Only the cards that CANNOT be split into a condition + scorer remain whole
    cards: the ERR 404 joke card (grants a random card when bought), the
    Blueprint (copies the card to its left in the card area), the Showman
    (allows buying duplicates), the Garden (doubles Seed payoffs), the Rigged
    Casino (re-weights Random rolls), and the Conquistador (unlocks board
    squares after each run). Every other card in the game is composed from a
    condition + a scorer (see Condition and condition_scorer_card) — the classic
    splittable cards were removed, with their names and flavor comments now
    living on the conditions they split into. Each constant is the card's ID.
    """
    ERR_404 = 9
    BLUEPRINT = 10
    # Owning the Showman card lets the player buy more than one copy of any
    # other card (duplicates are otherwise blocked).
    SHOWMAN = 78
    # Garden doubles the per-seed payoff of Seed-scorer blocks (+3 -> +6 mult).
    # New whole-card ids stay in the free 79..99 band (below the collision
    # condition base) so they never overlap a named-condition id — conditions
    # and whole cards share the small integer space below Condition.SHAPE_BASE.
    GARDEN = 80
    # Rigged Casino re-weights Random blocks toward +xMult and away from +chips.
    RIGGED_CASINO = 81
    # Conquistador unlocks board squares after every run.
    CONQUISTADOR = 82
    # The nine utility whole cards: run-shape and economy modifiers that no
    # condition + scorer pair can express. Their ids continue the free 83..91
    # band that Garden (80), Rigged Casino (81) and Conquistador (82) opened —
    # whole cards and named conditions SHARE the small integer space below
    # Condition.SHAPE_BASE, so a new whole card must never reuse an id already
    # taken by a condition (0..9, 79, 92) or by another whole card.
    PEDESTAL = 83  # retriggers the scorer of the first 3 blocks touched per run
    INFERNO = 84  # +0.07 to the total-score exponent
    DOPPELGANGER = 85  # each Start block releases a second marble
    COMPOUND_INTEREST = 86  # doubles the run's interest
    COUPON = 87  # every shop option (except board units) is 25% cheaper
    FACTORY = 88  # resource conversions need half as many points
    MINESHAFT = 89  # board units cost $5
    MARKET = 90  # selling refunds 75% of the price instead of 50%
    WATCH = 91  # the run ends at the ideal time; only the first 5 blocks score
    # The newest whole cards. Their ids continue the shared band upward past
    # Painting (93); the free ids left in that band are 11..77 and 96..99.
    TESSERACT = 94  # permanently +0.1 xMult for every shop reroll
    THOUSAND_HANDED = 95  # creates a random action after every run

    NAMES: ClassVar[dict[int, str]] = {
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
    }
    # Short flavor lines, one per whole card.
    COMMENTS: ClassVar[dict[int, str]] = {
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
    }
    # What each whole card does.
    DESCRIPTIONS: ClassVar[dict[int, str]] = {
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
    }
    # All whole-card prices are 20% lower (rounded down): 24->19, 42->33,
    # 60->48, 46->36, 48->38, 56->44. The nine utility cards are priced by how
    # much run they give back (Inferno the most, Market the least).
    PRICES: ClassVar[dict[int, int]] = {ERR_404: 19, BLUEPRINT: 33, SHOWMAN: 48,
                                        GARDEN: 36, RIGGED_CASINO: 38,
                                        CONQUISTADOR: 44, PEDESTAL: 44,
                                        INFERNO: 50, DOPPELGANGER: 46,
                                        COMPOUND_INTEREST: 36, COUPON: 46,
                                        FACTORY: 44, MINESHAFT: 28,
                                        MARKET: 26, WATCH: 40, TESSERACT: 44,
                                        THOUSAND_HANDED: 42}
    # Face colors and center glyphs for the mini-card look (one per card).
    COLORS: ClassVar[dict[int, tuple]] = {
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
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        ERR_404: "4", BLUEPRINT: "B", SHOWMAN: "!",
        GARDEN: "G", RIGGED_CASINO: "R", CONQUISTADOR: "C",
        PEDESTAL: "P", INFERNO: "I", DOPPELGANGER: "D",
        COMPOUND_INTEREST: "%", COUPON: "C", FACTORY: "F",
        MINESHAFT: "M", MARKET: "S", WATCH: "W",
        TESSERACT: "T", THOUSAND_HANDED: "H",
    }
    ORDER: ClassVar[list[int]] = [ERR_404, BLUEPRINT, SHOWMAN, GARDEN,
                                  RIGGED_CASINO, CONQUISTADOR,
                                  PEDESTAL, INFERNO, DOPPELGANGER,
                                  COMPOUND_INTEREST, COUPON, FACTORY,
                                  MINESHAFT, MARKET, WATCH, TESSERACT,
                                  THOUSAND_HANDED]

    @classmethod
    def name(cls, card):
        return cls.NAMES.get(card, "Unknown")

    @classmethod
    def comment(cls, card):
        return cls.COMMENTS.get(card, "")

    @classmethod
    def description(cls, card):
        return cls.DESCRIPTIONS.get(card, "Unknown card.")


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
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        START: "?", DISTANCE: "*", BLACK_HOLE: "O", AIR_TIME: "P",
        FULLEST_COLUMN: "I", CASH_HELD: "$", FRAGILE_BREAKS: "H",
        SLIPPERY: "S", RANDOM: "#", FEW_BLOCKS: "R", COZY: "~",
        PAINTING: "P", SYNTHESIZER: "Y",
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

    NAMES: ClassVar[dict[int, str]] = {
        DEATH: "Death",
        RECOGNITION: "Recognition",
        DEJA_VU: "Deja Vu",
        ANOINTMENT: "Anointment",
        STRENGTH: "Strength",
        SPIRIT: "Spirit",
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
    }
    # What the upgraded (v2) action does.
    V2_DESCRIPTIONS: ClassVar[dict[int, str]] = {
        DEATH: "Sells a chosen block or card for 6x its price.",
        RECOGNITION: "Duplicates a chosen card for a price equal to its cost.",
        DEJA_VU: "Gives a chosen block +100 triggers.",
        ANOINTMENT: "Gives every block on the board and in the inventory one new random effect.",
        STRENGTH: "Triples a chosen block's scorer amount.",
        SPIRIT: "Destroys a chosen block and applies its scorer at the start of every run, permanently.",
    }
    # Short flavor lines, one per action.
    COMMENTS: ClassVar[dict[int, str]] = {
        DEATH: "All things must end.",
        RECOGNITION: "A nod to the familiar.",
        DEJA_VU: "Haven't we been here before?",
        ANOINTMENT: "Blessed with power.",
        STRENGTH: "Swing harder.",
        SPIRIT: "It lingers on.",
    }
    # Actions are cheap one-use power-ups: their prices were halved (48 -> 24,
    # 56 -> 28), so a run can afford one almost any time. Deja Vu costs a little
    # more than the other two: it is worth about one cash trigger-limit
    # upgrade, and its v2 converts a block into a near-inexhaustible scorer.
    # The three later actions are stronger, so they sit a tier above.
    PRICES: ClassVar[dict[int, int]] = {DEATH: 24, RECOGNITION: 24, DEJA_VU: 28,
                                        ANOINTMENT: 32, STRENGTH: 28, SPIRIT: 36}
    # Face colors and center glyphs for the mini-action look (one per action).
    COLORS: ClassVar[dict[int, tuple]] = {
        DEATH: (120, 45, 45),        # deathly red
        RECOGNITION: (60, 100, 180), # recognition blue
        DEJA_VU: (105, 65, 150),     # dizzy violet
        ANOINTMENT: (35, 125, 95),   # blessed emerald
        STRENGTH: (175, 85, 35),     # brawny amber
        SPIRIT: (140, 140, 160),     # spectral grey
    }
    GLYPHS: ClassVar[dict[int, str]] = {
        DEATH: "D", RECOGNITION: "R", DEJA_VU: "V",
        ANOINTMENT: "A", STRENGTH: "S", SPIRIT: "P",
    }
    ORDER: ClassVar[list[int]] = [DEATH, RECOGNITION, DEJA_VU, ANOINTMENT,
                                  STRENGTH, SPIRIT]

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
    def cycle(cls, action):
        idx = cls.ORDER.index(action) if action in cls.ORDER else 0
        return cls.ORDER[(idx + 1) % len(cls.ORDER)]


# --- Magnitudes -------------------------------------------------------------
# Every scalable value in the game (a scorer's amount, a piston's launch speed)
# is a MAGNITUDE rolled around its average when the item is created. The
# deviation x from the average is an integer with probability 1/(x^2 + 1), so
# the average comes up about a third of the time (1/3.15), one step off about
# a sixth, two steps off a sixteenth, and a wild outlier once in a blue moon
# (|x| <= 8 is 1/65 as likely as the average). One step is 10% of the average,
# so a magnitude always moves in proportion to itself.
MAGNITUDE_STEP_FRACTION = 0.1
MAGNITUDE_STEP_DIVISOR = 10  # 1 / MAGNITUDE_STEP_FRACTION, as a whole number
                             # for exact step arithmetic (average / 10)
MAGNITUDE_MAX_STEPS = 8
MAGNITUDE_WEIGHTS = [1.0 / (x * x + 1)
                     for x in range(-MAGNITUDE_MAX_STEPS, MAGNITUDE_MAX_STEPS + 1)]


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


def magnitude_deviation(average, magnitude):
    """The "(+2)" / "(-1)" / "(0)" a magnitude is described with, or "".

    Written RIGHT AFTER the magnitude it belongs to ("Adds +6 mult (+2) when
    touched") instead of at the end of the sentence, and the sidebar colours it
    (green above average, red below, grey for exactly average — see
    ui.draw_item_info). A value with no average has no deviation to show.
    """
    if not average or magnitude is None:
        return ""
    diff = round(magnitude - average, 3)
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
    return magnitude_deviation(average, resource_points_for(scorer, amount))


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
        Shape.CRADLE: "A V-shaped valley: catches a marble and settles it at the center.",
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
        Scorer.PARTS: f"Gives {amount:g} component{_plural(amount)}{dev} when touched",
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

    A composed card (condition x scorer) whose scorer carries a rolled
    magnitude describes THAT magnitude, with the deviation right after it
    ("Gives +45 chips (+15) at the start of the run"); a whole card, or a
    composed card with no magnitude, describes the catalog entry it has always
    had.
    """
    if not amount:
        return Card.DESCRIPTIONS.get(card, "Unknown card.")
    parts = splittable_card_condition_scorer(card)
    if parts is None:
        return Card.DESCRIPTIONS.get(card, "Unknown card.")
    condition, scorer = parts
    return f"{_card_payoff_text(condition, scorer, amount)}."


class Component:
    """A purchasable building piece: a shape, an effect, a scorer, or a condition.

    ``value`` is the component's ID number (a ``Shape``, ``Effect``, ``Scorer``,
    or ``Condition`` constant).
    """
    SHAPE = "shape"
    EFFECT = "effect"
    SCORER = "scorer"
    CONDITION = "condition"

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
        """An effect piece. ``magnitude`` is its own rolled strength (see
        effect_component_price): a stronger piston costs more and a weaker one
        less, so the piece's price always follows what it actually does."""
        if price is None:
            price = effect_component_price(value, magnitude)
        return cls(cls.EFFECT, value, amount=magnitude or 0, price=price,
                   name=name or Effect.name(value), col=col, row=row)

    @classmethod
    def scorer_component(cls, value, amount=0, price=None, name="", col=0, row=0):
        """A scorer piece. ``amount`` is its own rolled magnitude (see
        scorer_component_price), which sets both its payoff and its price."""
        if price is None:
            price = scorer_component_price(value, amount)
        return cls(cls.SCORER, value, amount=amount, price=price,
                   name=name or Scorer.name(value), col=col, row=row)

    @classmethod
    def condition_component(cls, value, price=None, name="", col=0, row=0):
        if price is None:
            price = COMPONENT_PRICES.get((cls.CONDITION, value), 0)
        return cls(cls.CONDITION, value, price=price, name=name or condition_name(value), col=col, row=row)


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
    (Component.SHAPE, Shape.CRADLE): 11,
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
    (Component.CONDITION, Condition.START): 14,
    (Component.CONDITION, Condition.DISTANCE): 16,
    (Component.CONDITION, Condition.BLACK_HOLE): 17,
    (Component.CONDITION, Condition.AIR_TIME): 16,
    (Component.CONDITION, Condition.FULLEST_COLUMN): 16,
    (Component.CONDITION, Condition.CASH_HELD): 14,
    (Component.CONDITION, Condition.FRAGILE_BREAKS): 17,
    (Component.CONDITION, Condition.SLIPPERY): 16,
    (Component.CONDITION, Condition.RANDOM): 12,
    (Component.CONDITION, Condition.FEW_BLOCKS): 12,
    (Component.CONDITION, Condition.COZY): 17,
    (Component.CONDITION, Condition.PAINTING): 15,
    # Synthesizer scales with the card area (up to 5 cards), like Painting
    # scales with the board's value, so it sits in the same price tier. Every
    # named condition MUST have an entry here: a missing one is priced 0, which
    # makes it free in the shop and the most common draw (weight = 1/price).
    (Component.CONDITION, Condition.SYNTHESIZER): 15,
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


for _i, _s in enumerate(Shape.ORDER):
    COMPONENT_PRICES[(Component.CONDITION, Condition.SHAPE_BASE + _i)] = \
        _condition_price_for(COMPONENT_PRICES.get((Component.SHAPE, _s), 8))
for _i, _e in enumerate(Effect.ORDER):
    COMPONENT_PRICES[(Component.CONDITION, Condition.EFFECT_BASE + _i)] = \
        _condition_price_for(COMPONENT_PRICES.get((Component.EFFECT, _e), 8))


def scorer_component_price(scorer, amount=None):
    """A scorer piece's price for its OWN magnitude (proportional to value).

    The table price is the average-magnitude price, so a scorer rolled above
    its average costs proportionally more (a +Chips piece averaging $12 costs
    $13 at 33 chips, $15 at 39) and one rolled below costs less. A scorer with
    no magnitude at all (Start, Lucky, ...) is never scaled.
    """
    base = COMPONENT_PRICES.get((Component.SCORER, scorer), 0)
    average = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    if not amount or not average:
        return base
    return max(1, round(base * amount / average))


def effect_component_price(effect, magnitude=None):
    """An effect piece's price for its OWN magnitude (proportional to value).

    Like scorers: the table price is the average-magnitude price, so a piston
    rolled to 1800 px/s costs a fifth more than one at the 1500 px/s average.
    """
    base = COMPONENT_PRICES.get((Component.EFFECT, effect), 0)
    average = Effect.MAGNITUDE.get(effect, 0)
    if not magnitude or not average:
        return base
    return max(1, round(base * magnitude / average))


def block_price_for(shape, effects, scorer, amount=None, effect_amounts=None):
    """A block's price is 75% of the sum of its components' prices.

    Each component is priced at ITS OWN magnitude when one is given (a block
    with a 1800 px/s piston and a 33-chip scorer is worth more than the same
    block at the averages), and at the average price otherwise — so every
    caller that has the item's magnitudes should pass them, and a plain
    shape/scorer/scorer lookup still prices the average block.
    """
    effects = list(effects)
    amounts = effect_amounts or {}
    total = (
        COMPONENT_PRICES.get((Component.SHAPE, shape), 0)
        + sum(effect_component_price(e, amounts.get(e)) for e in effects)
        + scorer_component_price(scorer, amount)
    )
    return int(total * 0.75)


# --- Whole cards ---
# Every splittable card is composed from a condition + a scorer, so the only
# whole cards are the indivisible ones in the Card class above (ERR 404 /
# Blueprint / Showman / Garden / Rigged Casino / Conquistador). The classic
# named cards (Joker..Skater) and the old
# shape/effect cards ("Pipe card (+Mult)" etc.) were removed: each now exists
# only as a derived (condition x scorer) card — a magnitude card for a unit
# scorer or a generic card for a flat scorer (see CONDITION_CARD_OFFSET /
# GENERIC_CARD_OFFSET below). The classic cards' names and flavor comments now
# live on the conditions they were split into (Condition.NAMES / .COMMENTS).


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
                    Condition.COZY, Condition.PAINTING, Condition.SYNTHESIZER]
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
                     Condition.PAINTING, Condition.SYNTHESIZER):
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


# --- The card scorers a condition can pair with (shared with block assembly) ---
# EVERY block payoff scorer is a card scorer, so every (condition x scorer) pair
# forms a card: the three unit scorers build a magnitude card, and every other
# scorer builds a generic card that fires one block-style trigger per trigger.
# The only exclusions are NONE (no payoff at all) and START/FINISH (run roles,
# not payoffs — a card can't release or finish a marble).
#
# A card has no position, board context or marble of its own, so the payoffs
# that read one take them from "the block the condition hands the card": the
# block the marble collided with (collision conditions), the run's first block
# (start conditions), the run's last block (end conditions), or the block that
# shattered (Fragile Breaks). That is the same reference Summit, Airball and
# Effective already used, and it is what makes Powerline's row, Frontier's
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
}
# The named conditions, in a stable display order (collision conditions follow
# them in CONDITION_ORDER).
NAMED_CONDITION_ORDER = [Condition.START, Condition.DISTANCE,
                         Condition.BLACK_HOLE, Condition.AIR_TIME,
                         Condition.FULLEST_COLUMN, Condition.CASH_HELD,
                         Condition.FRAGILE_BREAKS, Condition.SLIPPERY,
                         Condition.RANDOM, Condition.FEW_BLOCKS, Condition.COZY,
                         Condition.PAINTING, Condition.SYNTHESIZER]


def condition_ratio(condition):
    """A condition's payoff fraction of the +30/+4/+0.25 bases.

    Collision conditions fire a standard unit per matching hit (ratio 1); a
    named condition's ratio scales every scorer so rewards stay proportional to
    the base (see NAMED_CONDITION_RATIO).
    """
    return NAMED_CONDITION_RATIO.get(condition, 1.0)


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


def _generic_effect_phrase(scorer, amount=None, dev="", condition=None):
    """A flat scorer card's short payoff phrase, at its own magnitude.

    The phrases are the average-magnitude text; a card carrying a rolled
    magnitude substitutes its own amount ("$22" for a Cash half rolled up from
    $15), so the description always matches what the card actually pays, with
    ``dev`` (the "(+2)" token) right after it. Block-relative scorers name
    ``condition``'s reference block (see _reference_block_phrase). The
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
    block = _reference_block_phrase(condition) if condition is not None else "its block"
    if scorer == Scorer.CASH:
        return f"${int(amount)}{dev}"
    if scorer == Scorer.SHARP:
        return f"{amount:g}x mult{dev}"
    if scorer == Scorer.PARTS:
        return f"{amount:g} component{_plural(amount)}{dev}"
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
    if scorer == Scorer.QUICK and condition_phase(condition) == "end":
        # There is no NEXT block after the run, so an end-condition Quick card
        # measures the run's LAST block instead.
        return f"chips from the speed of the last block hit{dev}"
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

# --- Generic flat-scorer cards ---
# Every other block scorer (Cash, Sharp, Quick, Parts/Shreds/Rubble/Ideas) is a
# card scorer too. Each pairs with every condition to build a new generic card,
# including Quick with a run-END condition: there is no "next block" after the
# run, so an end-phase Quick card pays from the speed of the run's LAST block
# hit instead. These ids sit far past every other card and,
# like the custom magnitude cards, are NOT in the fixed Card.ORDER catalog —
# but they can still appear pre-built as random (condition x scorer) shop
# offers, so a pre-built splittable card can carry any scorer. The runtime is
# generic: the scorer fires one block-style trigger each time the condition is
# satisfied (cards.py).
GENERIC_CARD_OFFSET = 2000
_GENERIC_CARD_CARDS = {}   # (condition, scorer) -> card id
_GENERIC_CARD_META = {}    # card id -> (condition, scorer)
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


def card_price_for(card, amount=None):
    """A composed card's price for its scorer half's OWN magnitude.

    A card's catalog price is condition + scorer at the averages, so only the
    SCORER half scales: the condition costs the same whoever carries it, and a
    +Chips half rolled to 45 makes the card dearer by exactly what that piece is
    worth (see scorer_component_price). A whole card, or a card with no
    magnitude, keeps its catalog price.
    """
    base = Card.PRICES.get(card, 20)
    parts = splittable_card_condition_scorer(card)
    if parts is None or not amount:
        return base
    condition, scorer = parts
    if not Scorer.DEFAULT_AMOUNT.get(scorer, 0):
        return base  # a scorer with no magnitude (Lucky, Quick, ...) never scales
    return max(1, COMPONENT_PRICES.get((Component.CONDITION, condition), 0)
               + scorer_component_price(scorer, amount))

