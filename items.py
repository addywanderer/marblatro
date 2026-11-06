"""The things the player owns: blocks, cards, actions, packs and tokens.

Each is a small record — what it is, what it cost, where it sits and the
magnitudes it was rolled with — plus the labels the info box and the shop print
for it. The rules that use them live on Game.
"""

import copy as _copy
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




def make_card_item(value, col=0, row=0, amount=None):
    """A card item, carrying its scorer's own magnitude.

    A match-group card rolls the SCORER's magnitude when the caller has none —
    the shop rolls one per offer, exactly like a scorer component — so the card
    pays, prices and describes itself at the strength it actually has (see
    components.card_price_for / card_description). A card that is not built on a
    match group (Coupon, Showman, Garden, ...) has no scorer, so it carries no
    magnitude and is unaffected. ``amount`` is passed through by callers that
    already know it: a shop item keeps the magnitude it was offered with, and a
    Recognition copy keeps the original's.
    """
    scorer = card_scorer(value)
    if amount is None:
        amount = roll_scorer_amount(scorer) if scorer else 0
    return CardItem(value, card_price_for(value), col=col, row=row,
                    amount=amount or 0)


class BlockItem:
    """A purchasable, pre-assembled block offered by the shop."""
    kind = "block"

    def __init__(self, col, row, shape, effect, scorer, scorer_amount, price, name,
                 portal_number=0, key_number=0, trigger_limit=1, trigger_paid=0,
                 effects=None, effect_amounts=None, angle=None):
        self.col = col
        self.row = row
        # The board square this item lies on as a loose block, or None when it is
        # off the board (still on the shop's shelf, or standing as a placed
        # block). It is NOT ``col``/``row``: those are the SHOP cell the offer is
        # drawn in, and a bought offer keeps them (see Game.item_cell).
        self.board_cell = None
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
        # The rotation the block already had when it was erased back into the
        # toolbox (see _refund_block). None for a shop block: it has no rotation
        # of its own and takes the build tool's angle when it is placed.
        self.angle = angle
        # The board square this item's block stands on while it is placed (see
        # Game._place_block_at), or None when the item is not on the board. A
        # placed block keeps the inventory spot it was bought into: the item is
        # not consumed, it remembers the square, and clicking that spot picks
        # the block up rather than arming a second copy.
        self.placed_cell = None

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
        self.col = col  # the SHOP cell the offer is drawn in (never a board cell)
        self.row = row
        self.board_cell = None  # the board square the owned card lies on
        self.name = Card.name(value)
        # A composed card's SCORER half magnitude (its own rolled strength): a
        # +Chips half rolled to 45 makes the card pay 45 a unit instead of 30.
        # A whole card has no scorer half, and a card that was never rolled
        # (an old save, a hand-built test card) is 0 — both pay, price and
        # describe at the average, exactly as they did before magnitudes.
        self.amount = amount or 0
        # True while the Shuffled trial has the card turned face over: the card
        # is DRAWN upside down (see ui.draw_card), and pays exactly what it paid
        # — the trial is a handicap, not a change to what the card does.
        self.flipped = False


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
        self.col = col  # the SHOP cell the offer is drawn in (never a board cell)
        self.row = row
        self.board_cell = None  # the board square the owned action lies on
        self.name = Action.name(value)


def owned_copy(offer):
    """A fresh item carrying exactly what a shop offer sells.

    A component or a repeatable block is bought again and again from the SAME
    shelf slot (see Game._buy_shop_item: the offer is not consumed, its price
    just rises), so the offer must stay on the shelf while the player owns
    something of their own. Handing the offer itself to the inventory made the
    shelf and the player the same object, so "two copies" of one item were one
    object listed twice: they shared a single board square and a single
    selection switch, the second purchase added nothing to look at, and selling
    or assembling one copy left the other behind as a ghost (user report:
    glitches with several copies of the same item).

    Everything a copied item carries is its own — its rolled magnitudes, its
    effects, its pairing numbers — so a copy behaves exactly like the offer it
    came from, without ever being the same thing. The copy stands NOWHERE yet,
    though: it must not inherit the shelf square the offer is lying on (or a
    placed block's link to it), because that square belongs to the offer until
    the copy is dealt one of its own (see Game._unlock_purchase).
    """
    copy = _copy.deepcopy(offer)
    if hasattr(copy, "board_cell"):
        copy.board_cell = None
    if hasattr(copy, "placed_cell"):
        copy.placed_cell = None
    return copy


class ResourceOption:
    """One option of a resource pack: points of one scorer, ready to bank.

    A resource pack deals these instead of items (see components.Pack). The
    points are what a trigger of the scorer banks times Pack's
    RESOURCE_PACK_FACTOR, at the magnitude the option rolled, and keeping one
    banks them straight into the permanent bank (see
    Game._grant_resource_points).
    """
    kind = "resource"

    def __init__(self, scorer, amount, points):
        self.scorer = scorer
        self.amount = amount    # the magnitude the option rolled
        self.points = points    # what keeping it banks
        self.name = f"{points_text(points)} {resource_point_label(scorer)} point" \
                    f"{'' if points == 1 else 's'}"


class BoardUnitOffer:
    """The shelf's Board Unit: a locked tile that buys one square of board.

    A Board Unit is not an item the player owns — it is counted in
    ``Game.board_units`` and spent by clicking a locked square — so the shelf's
    tile never leaves the shelf (see Game._buy_shop_item). It stands on a board
    square like every other offer, which is what lets the player buy it by
    right-clicking it where it lies.
    """
    kind = "unit"

    def __init__(self, price, col=0, row=0):
        self.price = price
        self.col = col      # the shelf slot it was dealt into (see Shop.reseat)
        self.row = row
        self.board_cell = None   # the board square the tile lies on
        self.name = "Board Unit"


class ItemPack:
    """A shelf offer that is a bundle of options to choose from.

    A pack is bought like any other offer and then OPENED: the player is shown
    its options and keeps Pack.keep(size) of them (see components.Pack). The
    pack itself is what sits on the shelf, with its size, its type and the
    options it dealt out; the options are removed from ``options`` as they are
    kept, so a mega pack's second pick is made from what is left.
    """
    kind = "pack"

    def __init__(self, pack_type, size, options, price, col=0, row=0,
                 keep=None, kept=0):
        self.pack_type = pack_type
        self.size = size
        self.options = list(options)
        self.price = price
        self.col = col
        self.row = row
        # The board square the pack lies on while it is on the shelf (see
        # Game.ensure_board_cells).
        self.board_cell = None
        # How many options the player keeps (from the size), and how many they
        # already have: a pack saved mid-choice comes back with its count.
        self.keep = Pack.keep(size) if keep is None else keep
        self.kept = kept
        self.name = f"{Pack.size_name(size)} {Pack.name(pack_type)}"

    @property
    def remaining(self):
        """How many options the player still gets to keep."""
        return max(0, self.keep - self.kept)

    @property
    def open(self):
        """True while the player still has a pick to make from this pack."""
        return self.remaining > 0 and bool(self.options)


def _s(amount):
    """A plural "s" for a count, so a sidebar row reads "1 block"/"2 blocks"."""
    return "" if amount == 1 else "s"


def resource_point_label(scorer):
    """What a resource scorer's points are called (see _resource_display).

    Shred points buy a card, rubble points a block, idea points an action and
    option points a permanent shop slot, so the four are named after the
    resource rather than after what they convert into.
    """
    return {Scorer.SHREDS: "shred", Scorer.RUBBLE: "rubble",
            Scorer.IDEAS: "idea", Scorer.PICKY: "option"}.get(scorer, "resource")


def offer_key(offer):
    """A (kind, ...) key telling two shop offers apart, or None.

    Every offer names what it sells in a different place — a component its kind
    and value, a block its shape/effects/scorer, a card and an action their
    value, a resource option its scorer and magnitude — so this is the one
    answer to "is this the same offer as that one?", used to keep the shelf's
    slots and a pack's options from repeating (see Shop._random_offer and
    Shop._roll_pack). A pack keys on nothing: two packs are never the same
    offer, whatever they hold.
    """
    kind = getattr(offer, "kind", None)
    if kind == "pack":
        return None
    if kind == "block":
        return (kind, offer.shape, tuple(offer.effects), offer.scorer)
    if kind == "resource":
        return (kind, offer.scorer, offer.amount)
    return (kind, getattr(offer, "value", None))


class ScorerToken:
    """A Spirit token: a whole sacrificed block, kept firing each run.

    Spirit destroys a block and keeps the BLOCK: the token stores a copy of it
    (``block``), so a run fires it exactly as if a marble had collided with it —
    the block's own scorer pays through the block-scorer path, and the player's
    cards whose group matches the block fire with it (see Game._fire_token).
    The stored block keeps everything the payoffs read: its cell (Summit,
    Powerline, Frontier, Cluster), its shape and effects (Effective), its angle
    and its own rolled magnitudes.

    WHEN it fires follows the payoff: a scorer that pays a MULTIPLIER (xMult,
    Sharp, Satanic, Effective — Scorer.MULTIPLIER_SCORERS) fires as the run
    SETTLES, because its xMult belongs to what the run settles on, and every
    other scorer fires at the START of the run. ``runs_left`` is None for a v2
    token, which never expires.
    """
    kind = "token"

    def __init__(self, block, runs_left=None):
        self.block = block
        # A token is not a marble-touched board block: the flag marks it as a
        # kept copy of a block, so the token's own drawing and firing paths can
        # tell it from the block the player placed (see _fire_token).
        block.is_token = True
        self.runs_left = runs_left  # None = permanent (v2)
        # True once the run's start has picked this token up: a multiplier
        # token is held back for the run's end, so this is what remembers that
        # the run it belongs to has begun. A token created mid-run is never
        # armed, so the run it was born in cannot spend it.
        self.armed = False
        # True once the token has actually paid in the run now in progress.
        self.fired = False

    # The stored block answers for the token, so the drawing, the save file and
    # the sidebar keep reading one thing.
    @property
    def scorer(self):
        return self.block.scorer

    @property
    def scorer_amount(self):
        return self.block.scorer_amount

    @property
    def shape(self):
        return self.block.shape

    @property
    def effects(self):
        return self.block.effects

    @property
    def x(self):
        return self.block.x

    @property
    def y(self):
        return self.block.y

    @property
    def name(self):
        return Scorer.name(self.block.scorer)

    @property
    def fires_at_end(self):
        """True when the token pays as the run settles (a multiplier scorer)."""
        return self.block.scorer in Scorer.MULTIPLIER_SCORERS


class CashBreakdown:
    """Hover target for the shop's "Last run cash gained" readout.

    The readout is not an item, but hovering it opens the same info box an
    item gets (see Game._describe_item), breaking the last run's earnings down
    into base cash, interest, the over-the-target score bonus, and cash from
    cards and scorers. The single instance below is never bought, sold, or
    drawn; it only gives the readout something to be hovered as.
    """


CASH_BREAKDOWN = CashBreakdown()
