"""Rolls and prices: the random numbers every item is built and valued with.

Magnitudes, the cards and match groups a shop offers, the pair numbers keys and
portals are filed under, and what a block or a part resells for. Nothing here
touches the game state: these are rolls over the enums and the tables in
components.py.
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
from config import *
import rolling
from rolling import *




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


def roll_magnitude_deviation():
    """A magnitude's deviation from the average, in steps (see roll_magnitude).

    CONTINUOUS: any real number of steps in [-MAGNITUDE_MAX_STEPS,
    MAGNITUDE_MAX_STEPS] whose probability falls off as
    1/(x^2 + MAGNITUDE_SPREAD) — a Cauchy distribution truncated to the cap,
    whose inverse distribution function is a tangent scaled by the
    distribution's own scale (MAGNITUDE_SCALE, the square root of the spread).
    So drawing one uniform angle, scaling it and taking its tangent IS an exact
    draw of it: no rejection loop, no lookup table, and no grid of steps. The
    spread is the dial on how wild rolls get — at 4 the middle is flatter and
    the tail much fatter than the 1 it started at, so a roll far from the
    average is routine rather than a near-impossible outlier. The rolled VALUE
    is what gets rounded, to the precision a magnitude of its size can mean
    (see components.magnitude_precision), so the draw stays as fine as the
    arithmetic allows while descriptions and saves stay tidy.
    """
    angle = random.uniform(-MAGNITUDE_ATAN_LIMIT, MAGNITUDE_ATAN_LIMIT)
    deviation = MAGNITUDE_SCALE * math.tan(angle)
    # Float noise at the extreme angle could step a hair outside the range the
    # game documents, so the cap is re-applied to the draw itself.
    return max(-MAGNITUDE_MAX_STEPS, min(MAGNITUDE_MAX_STEPS, deviation))


def roll_magnitude(average, floor=None):
    """Roll an item's OWN magnitude around the average it is built from.

    The deviation is continuous: any real number of steps with density
    1/(x^2 + MAGNITUDE_SPREAD), so a +Chips piece averaging 30 chips comes out
    at 31.1 or 27.4 as readily as at a whole number — the 10% grid it used to
    snap to is gone (see roll_magnitude_deviation for the draw). One step is
    still 10% of the average, so a +Mult piece (average 4) steps by 0.4, a
    piston (average 1500 px/s) by 150, and a wide roll stays within +/- 80% of
    the average. A value with no average to speak of (a scorer whose amount is
    unused) is returned untouched, and ``floor`` is the lowest value a roll may
    land on. Nothing about the roll reaches the item's PRICE (see
    components.block_price_for): the roll is upside, not cost.
    """
    step = magnitude_step(average)
    if not step:
        return average
    deviation = roll_magnitude_deviation()
    # Scaling by (10 + x)/10 is never rounded to a whole number, because
    # rounding snaps a small magnitude onto a coarser grid than the step it is
    # supposed to move in: a +Mult scorer (average 4, step 0.4) would land on
    # whole mult, losing most of its spread. The result is rounded to the
    # precision a deviation of this size can mean (see magnitude_precision),
    # which strips the arithmetic's float dust without touching the resolution.
    value = (average * (MAGNITUDE_STEP_DIVISOR + deviation)
             / MAGNITUDE_STEP_DIVISOR)
    value = round(value, magnitude_precision(average))
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


def infinity_factor(value, scale):
    """The Infinity whole card's straight-line form of a score factor.

    A measure the game scores by is normally read as ``atan(value / scale) * 2 /
    pi``, which creeps up toward 1 and so has a soft ceiling — past a point, more
    distance (or more unique types) buys almost nothing. Infinity replaces that
    curve with the straight line through the point where the curve reads
    INFINITY_ANCHOR: ``anchor * value / (scale * tan(anchor * pi / 2))``. The two
    agree at exactly that value — 0.75, i.e. 12071 px of travel or 48.3 touched
    types — and the line keeps climbing where the curve would have flattened out.
    """
    return INFINITY_ANCHOR * value / (scale * INFINITY_ANCHOR_TANGENT)


def block_resale_price(block):
    """A placed block's own price: what it was placed with, never a recount.

    Placing a block stamps it with the price of the item it came from (see the
    grid-placement code), and everything that needs that block's worth reads
    THIS value — erasing/refunding it, selling it with Death, duplicating it
    with Recognition, the Painting condition's board sell total. Re-summing the
    block's parts instead drifts away from what the player actually paid: a
    placed role block is recorded with effects=[NONE] and sums to $114 while
    the identical toolbox item is $109, and an effect added by Anointment is
    worth its catalog price rather than whatever the block was bought for.

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
    price = block_price_for(shape, block.effects, block.scorer)
    block.resale_price = price
    return price


def _random_card_scorer():
    """A random scorer for a card offer: drawn AFTER its group.

    The draw is flat, so the scorer never affects how rare a card is — a card's
    rarity comes from its match group alone (see random_card_option_value).
    """
    return random.choice(CARD_SCORERS)


def random_match_group():
    """A random match group, drawn from the groups alone.

    Every group is COMMON, so the group cards share one tier in the shop: each
    group comes up equally often inside it and the 32 scorer variants of a card
    share that one chance — the scorer never affects how rare a card is (see
    random_card_option_value, which draws the tier first and an entry second).
    """
    return random.choice(MATCH_GROUPS)


def random_prebuilt_card_value():
    """A random pre-built card value: a random (match group x scorer).

    Any scorer can pair with any group, so a card can carry any scorer — not
    just +Chips/+Mult/xMult. Used by the random-card grants.
    """
    return match_group_card(random_match_group(), _random_card_scorer())


def prebuilt_card_pool(grid_combos=10):
    """Distinct candidate cards for a random-card grant.

    The cards that are not built on a match group (the Card.ORDER catalog)
    plus ``grid_combos`` random (group x scorer) cards, so a granted card can
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


def card_offer_entries(rarity=None):
    """The entries the shop draws a card offer from: whole cards + groups.

    ``rarity`` narrows the list to one tier (see Card.rarity), which is what
    lets the offer be drawn TIER FIRST: the tiers are drawn by Rarity.WEIGHTS
    and only then is an entry picked inside the drawn tier, so how many cards a
    tier happens to hold cannot change how often that tier comes up.
    """
    pool = list(Card.ORDER) + list(MATCH_GROUPS)
    if rarity is None:
        return pool
    return [entry for entry in pool if Card.rarity(entry) == rarity]


# How many cards an offer tries inside its drawn tier before the slot gives up
# (a card already on the row, or one the player owns, collides; re-picking
# INSIDE the tier is what keeps the rarity ratio intact — see
# random_card_option_value).
CARD_OFFER_TRIES = 8


def _card_option_value(entry):
    """The card the shop offers for one pool entry.

    A match group becomes that group's card with a freshly rolled scorer (see
    _random_card_scorer); a whole card is offered as itself.
    """
    if entry in MATCH_GROUPS:
        return match_group_card(entry, _random_card_scorer())
    return entry


def _random_card_rarity():
    """A tier for a card offer, drawn by Rarity.WEIGHTS.

    This is the step that ties the shop's offers to the rarity ratio, 1 : 0.7 :
    0.5 : 0.3 : 0.2 from Common up to Legendary (see Rarity.WEIGHTS).
    """
    return random.choices(Rarity.ORDER,
                          weights=[Rarity.weight(tier) for tier in Rarity.ORDER],
                          k=1)[0]


def random_card_option_value(excluded=()):
    """A random shop card offer: the tier first, then a card inside it.

    The TIER is drawn first, by Rarity.WEIGHTS, so the chance an offer is
    Common / Unusual / Rare / Epic / Legendary follows the 1 : 0.7 : 0.5 : 0.3
    : 0.2 ratio on its own — how many cards carry a tier must not change how
    often that tier comes up (user request: "the chance that any given card
    option in the shop has a given rarity corresponds to its rarity ratio. The
    number of cards with a given rarity should not affect the chance of drawing
    a card with a given rarity."). Only then is a card picked FLAT inside the
    drawn tier, so every card of a tier is equally likely and no scorer can tilt
    anything: a match group card gets its scorer rolled here (all 26 groups are
    Common, so the group cards share the Common tier).

    ``excluded`` are card values this offer must avoid — the cards already on
    the shop row and the ones the player owns. A collision is resolved by
    re-picking INSIDE the drawn tier, never by drawing the tier again (which is
    what would tilt the odds toward the tier with the most cards), so the ratio
    holds for a whole row of offers, not just for a lone draw. None is returned
    only when every card of every tier is excluded (a player who owns the whole
    catalogue); the shop then falls back to an unrestricted draw.
    """
    taken = set(excluded)
    entries = card_offer_entries(_random_card_rarity()) or card_offer_entries()
    for _ in range(CARD_OFFER_TRIES):
        value = _card_option_value(random.choice(entries))
        if value is not None and value not in taken:
            return value
    return None


def random_card_option_values(count, excluded=()):
    """``count`` shop card offers: distinct, and away from ``excluded``.

    A card slot that cannot be filled from its own tier (the player owns every
    card of it) keeps the row full by falling back to an unrestricted draw, as
    the row did before; the tier of such a slot is the only one that can be
    overridden, and only when its whole tier is unavailable.
    """
    values = []
    taken = set(excluded)
    for _ in range(count):
        value = random_card_option_value(taken)
        if value is None:
            value = random_card_option_value()
        values.append(value)
        taken.add(value)
    return values


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


def reserve_pairing_numbers(items):
    """Advance the pairing counters past every number these items already use.

    A pairing number (see next_key_number / next_portal_number) is handed out by
    a counter that lives in the running game, while the numbers themselves live
    in the save — so a game that has just loaded a board holding pair #1 must
    not hand #1 to the next pair it builds. Without this, the loaded pair and the
    new one share a number and touching the new pair's Key opens the loaded
    pair's Lock too (and, as the collisions pile up over reloads, every key
    opens every lock). See adopt_pairing_numbers.
    """
    global _next_key_number, _next_portal_number
    for item in items:
        _next_key_number = max(
            _next_key_number, int(getattr(item, "key_number", 0) or 0))
        _next_portal_number = max(
            _next_portal_number, int(getattr(item, "portal_number", 0) or 0))


def pairing_position(item):
    """A sort key placing the board's blocks before a toolbox half.

    Used to keep the re-pairing below (see _split_shared_key_numbers) the same
    on every load: halves are paired up in board order, and an unplaced half —
    one waiting in the toolbox, which has no board cell — sorts before the
    board.
    """
    # Imported here, not at the top: blocks.py is built on top of this module's
    # rolls (main imports this one first), so a top-level import would be a cycle.
    from blocks import Block
    if isinstance(item, Block):
        return (item.y, item.x)
    return (0, 0)

def adopt_pairing_numbers(items):
    """Make these items' pairing numbers the game's own, then repair collisions.

    A pairing number (Key/Lock and Portal) is handed out by a counter that lives
    in the RUNNING GAME while the numbers themselves live in a SAVE, so a game
    that has just loaded a board is in two places at once about what is free:

    1. The counters are advanced past every number these items already use, so
       the next pair built is not handed a number the loaded board has. Without
       this the loaded pair and the new one share a number, and touching either
       Key opens the Lock of BOTH pairs — with a few reloads, every key opens
       every lock.
    2. A number shared by more than one Key AND more than one Lock is split into
       separate pairs. Step 1 stops new collisions, but a save written before it
       can still hold one, and such a group is otherwise unfixable in play: any
       of its keys opens all of its locks. Two blocks sharing a number are one
       pair, and a duplicated half (Recognition) keeps its number on purpose —
       two keys for one door, or one key opening two doors — so only the
       ambiguous two-and-two case is touched.

    Returns the number of pairs that had to be split.
    """
    reserve_pairing_numbers(items)
    return _split_shared_key_numbers(items)


def _split_shared_key_numbers(items):
    """Re-pair numbers shared by two Keys AND two Locks (see above).

    The first key and the first lock of such a group keep the number (the
    counters are already clear of it, so the rest get numbers of their own).
    Halves are paired up in board order, so which pair keeps the number is the
    same on every load.
    """
    groups = {}
    for item in items:
        shape = getattr(item, "shape", None)
        if shape not in (Shape.KEY, Shape.LOCK):
            continue
        number = int(getattr(item, "key_number", 0) or 0)
        if not number:
            continue
        group = groups.setdefault(number, {"keys": [], "locks": []})
        group["keys" if shape == Shape.KEY else "locks"].append(item)
    split = 0
    for number in sorted(groups):
        keys = sorted(groups[number]["keys"], key=pairing_position)
        locks = sorted(groups[number]["locks"], key=pairing_position)
        if len(keys) < 2 or len(locks) < 2:
            continue  # a duplicated half is a legitimate one-number group
        for index in range(1, min(len(keys), len(locks))):
            fresh = next_key_number()
            keys[index].key_number = fresh
            locks[index].key_number = fresh
            split += 1
    return split


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
