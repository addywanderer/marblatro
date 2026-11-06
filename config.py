"""The game's tunables: its colours, layout geometry, prices and score scales.

Every number the game is balanced or laid out with lives here. They are plain
module-level values, read by name (the drawing code binds them at import time —
see ui.py), so retuning the game or moving a panel is an edit to this file alone.
"""

import math

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
GRID_SIZE = 40  # Size of each grid cell in pixels
# How far (px) the mouse has to move with the button down before a press on the
# board counts as a DRAG that scrolls the view rather than a click (see
# InputMixin.handle_events / Game.pan_board). Small enough to feel immediate,
# large enough that a shaky click never scrolls the board.
PAN_THRESHOLD = 4

MAX_CARDS = 5  # Maximum owned cards the card area can hold at once
MAX_ACTIONS = 2  # Maximum owned actions the action area can hold at once

MARGIN_TOP = 0
# The top bar: every piece of the game's furniture — the shop, the score, the
# trial box, the run/round display and the MAIN MENU button — lives in a strip
# along the top of the screen, and the BOARD fills everything under it (user
# request). The bar's height is the shop's own height (SHOP_COORDS below), so
# the shop is exactly as tall as the strip it sits in.
TOP_BAR_HEIGHT = 200
# The board: the whole rest of the screen. It is INFINITELY large (its squares
# are addressed by any integer coordinate — see Game.board_cell_at), and this
# rect is only the WINDOW onto it: the part the player can see at once. The
# camera (Game.camera) decides which squares are in the window, so dragging the
# board scrolls it, and (0, 0) is simply the square at the window's top-left
# corner when the camera is at rest.
MARBLE_BOX_COORDS = (0, TOP_BAR_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - TOP_BAR_HEIGHT)
# The right-hand column: the trial box at the top, then the shop. The inventory
# panel, the card tray and the action row used to live between them; the board
# IS the inventory now (user request), so those areas are gone and every owned
# item stands on a board square instead.
CARD_COLOR = (210, 180, 60)  # gold card look for cards in the shop and on the board
# The shelf's LOGICAL grid: the shape Shop.refresh deals into (5 item slots,
# 3 pack slots, the Board Unit tile and Picky's bonus offers below them). The
# panel that used to be drawn here is gone (user request: "completely remove the
# shop's box") — every offer is an item lying on the board now — but the grid
# still decides how many offers a shelf holds and which slot each one came from
# (see Shop.reseat / Shop.slot_key).
SHOP_COORDS = (0, 0, 400, TOP_BAR_HEIGHT)  # x, y, width, height of the old panel
# The trial box, right of the score readout in the top bar.
TRIAL_BOX_COORDS = (810, 14, 200, 92)
SHOP_GRID_COLS = SHOP_COORDS[2] // GRID_SIZE
SHOP_GRID_ROWS = SHOP_COORDS[3] // GRID_SIZE

BG_COLOR = (255, 50, 50)
MARBLE_BOX_COLOR = (255, 100, 100)
# The top bar's backplate: a dark strip the game's furniture sits on, so the bar
# reads as a HUD over the board rather than a part of it.
BAR_COLOR = (26, 26, 32)
FONT_SCALE = 0.7
GARET_FONT_PATH = "fonts/garet-heavy.otf"
TITLE_FONT_PATH = "fonts/MARBLERUN.ttf"
# The nominal size behind every font in the game, keyed by the role that draws
# with it: Game.__init__ builds one Font per entry, ONCE, and hands the table
# to ui (see ui.bind_fonts). The numbers are the sizes the ui's own small text
# used to be built at through pygame's EMBEDDED default font — garet-heavy's
# glyphs are a good deal taller than that font's at the same nominal size (an
# 11px garet-heavy "Chips" is as tall as a 16px default-font one), so
# FONT_SCALE is what brings a role's ink back to the size it already had.
FONT_SIZES = {
    "mini": 14,      # a Spirit token's label and badge, the "v1" tag
    "tiny": 16,      # key/portal numbers, the "+" marker, the "v2" tag
    "small": 18,     # the sidebar's text
    "tile": 20,      # a condition tile's letter glyph (an unknown condition)
    "glyph": 22,     # a card/action letter glyph, and the 8 ball's digit
    "font": 24,      # the standard text
    "required": 34,  # the required score
    "total": 52,     # score totals
}
BORD_WIDTH = 6
REQUIRED_SCORES = [100]
# The score every run starts from, before a card, scorer or upgrade adds to it:
# the chips and mult that _compute_total_score raises to the exponent. Kept here
# so the reset paths and the tests read one number.
RUN_BASE_CHIPS = 30
RUN_BASE_MULT = 4
# Total-score exponent: total = (chips * mult) ** exponent, where the exponent
# is an EQUAL-weight linear combination of the run's time, distance, and
# uniqueness. Each factor is normalized to 0..1 and more of it is always
# better (no par time).
TIME_IDEAL = 2.0  # ideal time for max time contribution
TIME_SCALE = 50.0  # leniency on how close time can be for more exponent effect
DISTANCE_SCALE = 5000.0  # px traveled that count as a 1/2 distance contribution
UNIQUE_SCALE = 20  # unique shape/effect/scorer types for a 1/2 uniqueness contribution
CASH_SCALE = 25
# The Watch whole card pins the run's TIME factor at its ceiling — the value the
# ideal window pays (see Game._score_factors). The run's length then never costs
# score again; it simply cannot earn more than the ceiling, so a long slow build
# scores as well as a fast one (both far better than the quadratic penalty the
# time factor hands a slow run without the card).
TIME_GOOD_MAX = 1.0
# The Infinity whole card swaps the DISTANCE and UNIQUENESS factors — both
# saturating curves, `atan(value / scale) * 2 / pi` — for straight lines. Each
# line is pinned to its curve at INFINITY_ANCHOR: the factor value where the
# line and the curve agree, so the card changes the curve's SHAPE and not its
# scale. Below the anchor the line pays LESS than the curve did, above it more,
# and it never levels off (see infinity_factor / Game._score_factors).
INFINITY_ANCHOR = 0.75
# tan() of the angle the anchor sits at, so the pinned point is exact: the
# saturating curve reads INFINITY_ANCHOR at SCALE * tan(INFINITY_ANCHOR * pi/2)
# — 12071 px of travel, or 48.3 types, for the game's own two scales.
INFINITY_ANCHOR_TANGENT = math.tan(INFINITY_ANCHOR * math.pi / 2)
QUICK_SCALE = MAGNITUDES.QUICK_CHIPS_PER_SPEED  # chips a Quick scorer grants per px/s
RECENT_SPEED_DECAY = 0.9
# Growing/Shrinking blocks multiply the marble's radius by these factors on
# each fresh touch. Shrinking clamps at MIN_MARBLE_RADIUS so a marble never
# shrinks to nothing, and Growing stops after GROW_MAX_TRIGGERS touches (user
# request: "make the growing effect trigger a maximum of 4 times") so a marble
# cannot grow without bound.
GROW_RADIUS_FACTOR = 2.0
GROW_MAX_TRIGGERS = 4
SHRINK_RADIUS_FACTOR = 0.5
MIN_MARBLE_RADIUS = 1.0
# Marble trails: small marble-colored dots shrink and fade behind a moving
# marble. TRAIL_SPACING is the distance (px) between dots, TRAIL_LIFE how long
# each dot lasts, and TRAIL_RADIUS_SCALE the dot's starting size as a fraction
# of the marble's radius.
TRAIL_SPACING = 4.0
TRAIL_LIFE = 0.6
TRAIL_RADIUS_SCALE = 0.5
# Trials: exactly one run-wide modifier per run. Hands tied takes this many
# triggers away from a random 1/4 of the marble-box blocks: a block that could
# score 3 times scores twice instead, and one out of triggers entirely (0) is
# silenced for the run (see Game._trigger_limit).
TRIAL_TRIGGER_PENALTY = 1
# The Concert whole card hands every block that is not a plain rect AND has both
# an effect and a scorer one extra trigger per run (see Game._trigger_limit).
CONCERT_TRIGGER_BONUS = 1
SHOP_MESSAGE_DURATION = 90  # Frames a shop purchase message stays visible
# Seconds between autosaves while a game is being played (see
# Game._tick_autosave): the game otherwise only saves when the player presses P
# or quits, so a long session could lose everything since the last one.
AUTOSAVE_INTERVAL = 30.0
# The shop's shelf: SHOP_ITEM_SLOTS "any item" offers — one random component,
# block, card or action each (see Shop._random_offer) — plus SHOP_PACK_SLOTS
# item packs, plus the fixed Board Unit offer. All of them share the offer row
# (SHOP_ITEM_ROW), the packs to the right of the items and the Board Unit right
# of the packs. The offers lie on the BOARD now (the panel is gone, user
# request), so these cells only decide which slot a shelf's offer came from and
# where a restored save's offers are re-seated; the price is shown on hover.
SHOP_ITEM_SLOTS = 5
SHOP_PACK_SLOTS = 3
SHOP_ITEM_ROW = 1
# The packs share the offer row, to the RIGHT of the item offers: the top bar
# has room for one row of tiles, and the fixed Board Unit tile sits right of the
# packs (see BOARD_UNIT_COL). The row under it carries every price.
SHOP_PACK_ROW = SHOP_ITEM_ROW
SHOP_PACK_COL = SHOP_ITEM_SLOTS + 1
# The row Picky's extra offers start on, below the offers' price row (they fill
# it left to right and wrap onto the rows under it — see Shop.refresh/reseat).
SHOP_BONUS_ROW = 3
# How many times a shelf slot or a pack option re-rolls to avoid repeating
# something already on the shelf (or already in the pack) before accepting the
# duplicate: enough to keep a full shelf varied, few enough that a pool which
# cannot fill every slot (a player who owns most of the cards) still fills them.
OFFER_DUPLICATE_TRIES = 8
# The kinds a shelf slot (and a Picky bonus slot) may offer, as components.Pack
# types: the goods an "any item" slot deals. Resource points are NOT here — a
# shelf slot sells items, and points are only ever dealt inside a pack (see
# Shop._offer_of). Each kind's odds live with the pack data (see
# components.Pack.SHELF_WEIGHTS: 23% card, 15% action, 8% shape, 12% effect,
# 22% scorer, 20% block), and are read per kind, so they follow this list.
SHELF_OFFER_TYPES = (Pack.SHAPE, Pack.EFFECT, Pack.SCORER, Pack.BLOCK,
                     Pack.CARD, Pack.ACTION)
# The player's DECK: every item they own. The board shows a HAND of
# DECK_DRAW_SIZE items drawn from it (see Game._cycle_deck), and the rest wait in
# the deck until the next run draws them again. The Start and Finish blocks are
# never in the deck — they stay on the board so a run can always be built.
DECK_DRAW_SIZE = 4
SHOP_ACTION_SLOTS = 2
# Spirit tokens (see Action.SPIRIT): a token keeps the whole block a Spirit
# destroyed and is drawn as that block (see ui.draw_token). A token is PART of
# the inventory rather than an area of its own: it takes the inventory cell
# right after the items the inventory holds (see Game._token_rect), and the
# panel is drawn large enough to hold both. MAX_TOKENS is how many the
# inventory can hold in all.
MAX_TOKENS = 999
# The "run" a Spirit token's Random/Lucky block is tagged with: the reward was
# decided when the block was sacrificed and is KEPT for every run the token
# covers, so its tag is not a run number and never goes stale — replaying a run
# or loading a save cannot reroll what the token pays (see
# Game._run_random_result / _roll_kept_reward).
KEPT_ROLL_RUN = "kept"
# Service fees and upgrade costs are all 20% lower than the original
# (rounded down): 25->20, 70->56, 50->40, 40->32. Upgrading an action from v1
# to v2 costs ACTION_UPGRADE_COST (was 300, then 240, now a flat 200).
ACTION_UPGRADE_COST = 200  # Cash to upgrade an action from v1 to v2
# A shop (or granted) action is usually v1; this often it arrives as v2
# already, which is a straight saving of ACTION_UPGRADE_COST (see
# random_action_version).
ACTION_V2_CHANCE = 0.01
SHOP_REFRESH_COST = 20  # Cash cost to reroll the shop
# What the four later actions move (see their handlers in Game._action_*).
EXPANSION_SQUARES = 4            # locked squares Expansion (v1) unlocks
BRAINSTORM_REROLLS = 2           # free rerolls Brainstorm (v1) banks
BRAINSTORM_REROLL_FACTOR = 0.5   # Brainstorm's v2 reroll price factor
MASS_PRODUCTION_RUN_FACTOR = 3.0      # Mass production's v1 resource factor
MASS_PRODUCTION_FOREVER_FACTOR = 2.0  # ...and the permanent one its v2 sets
GRACE_RUN_XMULT = 1.0            # xMult Grace (v1) adds to the run
TRIAL_CHANGE_COST = 50  # Cash to swap this run's trial for a different random one
TRIAL_DISABLE_COST = 100  # Cash to play this run with no trial at all
DISASSEMBLE_COST = 56  # Cash cost to break a block back into its parts
# COMMENTED OUT with the conditions: the cash cost to split a splittable card
# back into its two halves. A card is unsplittable now (see the card builder's
# note below), so nothing charges this fee.
# CARD_DISASSEMBLE_COST = 56
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
# sits in the top bar, with the final (boss) run at the bottom right.
# RUN_DOT_GRID is the center of round 1 / run 1 (the top-left dot).
RUN_DOT_GRID = (440, 66)
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
# COMMENTED OUT: shop rerolling (user request: "comment out shop rerolling for
# now"). The reroll button is not drawn and its click is not wired (see
# ui.draw_bar_readouts / InputMixin.handle_events).
# SHOP_REFRESH_BUTTON_RECT = pygame.Rect(SHOP_COORDS[0] + SHOP_COORDS[2] - 112,
#                                        SHOP_COORDS[1] + 8, 104, 24)
# Where the bar's readouts start: the cash caption, the last run's earnings
# under it and the game's message line under that. The shop panel used to own
# this corner; the panel is gone (every offer is an item on the board now), so
# the captions simply stay where the player already looked for them.
BAR_TEXT_X = 10
BAR_TEXT_Y = 10
BAR_TEXT_WIDTH = 380
# The DECK button: a bar button that opens the deck overlay, showing every item
# the player owns and which DECK_DRAW_SIZE of them are drawn into the hand for
# the run (see ui.draw_deck_button / ui.draw_deck_overlay).
DECK_BUTTON_RECT = pygame.Rect(440, 120, 140, 34)
DECK_OVERLAY_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 90, SCREEN_HEIGHT - 60,
                                      180, 36)
# The trial display above the cards. Its LEFT half buys a different random
# trial and its RIGHT half buys no trial for the run (see
# _click_trial_display); hovering it shows both prices.
TRIAL_BOX_RECT = pygame.Rect(TRIAL_BOX_COORDS)
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
# Action-upgrade button: a tile in the top bar, drawn while an action is
# selected, upgrading it from v1 to v2 for ACTION_UPGRADE_COST.
ACTION_UPGRADE_RECT = pygame.Rect(810, 116, 200, 40)
# --- Slots that cards and actions can win (Inaction, Foresight) ----------------
# Inaction does nothing, five times over: every INACTION_USES_PER_SLOT uses win
# the card area one more slot, and a v2 Inaction hands one over outright (see
# Game._action_inaction).
INACTION_USES_PER_SLOT = 5
# Foresight's permanent gift: one action slot, or — as a v2 — no limit on owned
# actions at all, which is what ACTION_SLOTS_UNLIMITED stands in for. Everything
# the player owns lies on the board now, so the board's own squares are what
# bound the counts (see Game.max_actions).
FORESIGHT_ACTION_SLOTS = 1
ACTION_SLOTS_UNLIMITED = 999
# The Earthquake whole card: the factor the magnitudes the SHOP rolls are raised
# by (see Shop._quake).
EARTHQUAKE_MAGNITUDE_FACTOR = 1.1
# The Challenger whole card: the factor the trial display's two fees are
# charged at (see Game.trial_change_cost / trial_disable_cost).
CHALLENGER_COST_FACTOR = 0.5
# The Odyssey whole card: the fraction of an item's SELL price the banked item
# pays when it comes back after a run, and the column its banked items are
# shown in. That column is an area of its own, at the right-hand end of the top
# bar, because those items are put AWAY for the run rather than carried.
ODYSSEY_CASH_FRACTION = MAGNITUDES.ODYSSEY_CASH_FRACTION
INACCESSIBLE_COORDS = (1160, 20, GRID_SIZE, GRID_SIZE * 4)
# The MAIN MENU button on the play screen (bottom right of the bar): leaving the
# current game and returning to the title screen (same action as the game-over
# screen's MAIN MENU button).
RETURN_TO_MENU_BUTTON_RECT = pygame.Rect(1020, TOP_BAR_HEIGHT - 44, 130, 32)
BLOCK_INTERIOR_COLOR = BLACK
MARBLE_COLOR = WHITE
# The board's own extent, in squares: the WINDOW onto the infinite board (see
# MARBLE_BOX_COORDS). Nothing is bounded by it — the board's squares go on for
# ever in every direction — it only says how many of them fit on screen, which
# is what the drawing and the mouse handling walk.
GRID_WIDTH = MARBLE_BOX_COORDS[2] // GRID_SIZE
GRID_HEIGHT = MARBLE_BOX_COORDS[3] // GRID_SIZE
# The top bar's pieces, left to right: the shop panel (SHOP_COORDS), the run and
# round display, the score readout, the trial box and the MAIN MENU button. The
# score readout is the one that needs a region of its own — it stacks five lines
# — so its rect lives here too.
SCORE_PANEL_RECT = pygame.Rect(600, 4, 200, TOP_BAR_HEIGHT - 8)
# The dynamic board: a new game starts with a block of squares unlocked
# (BOARD_START_WIDTH x BOARD_START_HEIGHT), centered in the window, leaving a
# locked ring all around it. The start region has to be roomy because the
# player's items all lie ON the board now (see Game.ensure_board_cells) — items
# never sit on a locked square. Buying a Board Unit in the shop
# (BOARD_UNIT_PRICE, always offered in the rightmost cell of the shop's offer
# row) lets the player click any locked square to unlock it so the marble can
# travel there and items can be laid out on it. Locked squares act as solid
# walls. The unlocked state (and Board Units in hand) is saved with a game and
# restored when its slot loads; only starting a BRAND-NEW game locks the board
# back down to this starting region.
BOARD_START_WIDTH = 8
BOARD_START_HEIGHT = 8
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
WATCH_BLOCK_LIMIT = 8
# The Brain Loop whole card's chance of handing over a random action on a fresh
# touch of a Sticky block (see Game._brain_loop_roll).
BRAIN_LOOP_ACTION_CHANCE = 1 / 3
# The Gate whole card's reward for one trip through a lock: one standard chips
# unit (+30 chips), paid by Game._gate_key_and_lock every time a marble that
# collected the lock's Key passes through it.
GATE_PASS_CHIPS = MAGNITUDES.GATE_PASS_CHIPS
# The Fountain whole card pays +0.25 xMult for every this-many PIPE-GROUP blocks
# (Pipe, Drain, Pipe Bend — see components.PIPE_GROUP_SHAPES) a marble touches in
# a row without touching anything else; the run's sightings are counted in
# Game._count_pipe_streak and read at the end of the run.
FOUNTAIN_STREAK_LENGTH = 3
# The Inferno whole card adds this to the total-score exponent.
INFERNO_EXPONENT_BONUS = MAGNITUDES.INFERNO_EXPONENT_BONUS
# The Tesseract whole card permanently gains this much xMult for every shop
# reroll (saved with the game; applied at the start of each run).
TESSERACT_REROLL_XMULT = MAGNITUDES.TESSERACT_REROLL_XMULT
# The Doppelganger whole card's extra marble leaves the Start block with this
# sideways drift (px/s), so the two marbles separate instead of overlapping.
DOPPELGANGER_START_VX = 1.0
# The Essence whole card: $10 at the end of every run, one card slot fewer in
# the area while it is owned, and this many random permanent Spirit tokens when
# it is sold (see Game._card_sold_message / _grant_permanent_tokens).
ESSENCE_RUN_CASH = MAGNITUDES.ESSENCE_RUN_CASH
ESSENCE_TOKENS = 2
BOARD_UNIT_ROW = SHOP_PACK_ROW  # the offer row
BOARD_UNIT_COL = SHOP_PACK_COL + SHOP_PACK_SLOTS  # right of the three pack slots
FPS = 60
DT = 1.0 / FPS
# The Procrastination whole card sends a finished run back in time: when every
# marble has finished, each one returns to the motion state it had this many
# seconds ago and flies again with every block trigger refilled (see
# Game._procrastination_rewind). One snapshot is kept per frame, so this also
# sets how much history a run carries: a marble's oldest snapshot is exactly
# this far back.
PROCRASTINATION_REWIND_SECONDS = 1.0
PROCRASTINATION_REWIND_FRAMES = max(1, round(PROCRASTINATION_REWIND_SECONDS / DT))

# Physics constants
MAX_MARBLE_RECURSION = 3
MAX_MARBLE_SPEED = 6000  # px/s, clamps runaway speed to bound simulation cost
MAX_SUB_STEPS = 64  # Hard cap on movement sub-steps per update
MAX_STEP_DISTANCE = 4.0  # px per sub-step; <= 2 * MARBLE_RADIUS prevents tunneling
GRAVITY = 2500  # pixels/s^2
MARBLE_RADIUS = 8
MARBLE_MASS = 1 # scales gravity and air resistance
# The Singularity trial makes the marble gain mass at this rate (mass per
# second), so it falls ever faster over the course of the run. It used to be
# 0.5, a FINAL boss's rate; as an ordinary run modifier it climbs more slowly
# (user request: "make singularity increase mass more slowly").
SINGULARITY_MASS_GROWTH = 0.2
# The Sky High trial's factor on the run's required score (user request: "make
# sky high give 2x required score"; it tripled the target as a final boss).
SKY_HIGH_SCORE_FACTOR = 2.0
FRICTION_COEFFICIENT = 1
ROLLING_FRICTION = 0
RESTITUTION = 0  # Bounciness factor for walls
# Two contact normals at least this parallel (cos 5 degrees) are ONE surface:
# adjacent blocks that make up a single flat floor bounce the marble once,
# not once per block (see PhysicsEngine._resolve_block_overlaps).
SAME_SURFACE_DOT = 0.996
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
# COMMENTED OUT with the shape itself (user request: "comment out the cradle
# shape"): the two floor constants and everything that used them.
# CRADLE_FLOOR_DEPTH = 20
# CRADLE_FLOOR_HALF = 12
# Tuning for the newer effects. A conveyor is a BELT: it carries the marble
# along its surface at CONVEYOR_SPEED (a constant, like a real belt, so it does
# not accelerate the marble); a phase block makes the marble pass through every
# block for PHASE_DURATION seconds; a splitter never lets the marble count grow
# past MAX_MARBLES, since every marble is simulated each frame.
CONVEYOR_SPEED = Effect.MAGNITUDE[Effect.CONVEYOR]  # px/s a conveyor carries a marble along at (the AVERAGE; each belt rolls its own)
PHASE_DURATION = Effect.MAGNITUDE[Effect.PHASE]  # seconds of no block collisions after a phase touch (the AVERAGE; each phase block rolls its own)
MAX_MARBLES = 16  # cap on marbles alive at once (splitter copies included)
# The Phantom trial starts every marble inside a block pass-through window for
# this many seconds (see Game._release_start_marble): a plain second, not a
# phase block's rolled PHASE_DURATION, because the trial grants it rather than a
# block the player built.
PHANTOM_PHASE_SECONDS = 1.0
# The Vertigo trial's gravity: every direction EXCEPT straight down (the
# trial-free default — a Vertigo run that changed nothing would just be a
# missing trial), as unit vectors. Which one a run pulls in is rolled once by
# Game._roll_trial_decision and stored as an index in the run's trial decision,
# so a replay (R, T, a retry) and a loaded save pull the same way.
VERTIGO_DIRECTIONS = ((0.0, -1.0), (-1.0, 0.0), (1.0, 0.0))