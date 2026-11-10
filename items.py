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
    Passive,
    CARD_SCORERS,
    COMPONENT_PRICES,
    DEFAULT_DIFFICULTY,
    MAGNITUDE_ATAN_LIMIT,
    MAGNITUDE_MAX_STEPS,
    MAGNITUDE_SCALE,
    MAGNITUDE_STEP_DIVISOR,
    MAGNITUDES,
    MATCH_GROUPS,
    Modifiable,
    Modifier,
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
    Structure,
    Tool,
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


class BlockItem(Modifiable):
    """A purchasable, pre-assembled block offered by the shop."""
    kind = "block"

    def __init__(self, col, row, shape, effect, scorer, scorer_amount, price, name,
                 portal_number=0, key_number=0, trigger_limit=1, trigger_paid=0,
                 effects=None, effect_amounts=None, angle=None,
                 quality=Quality.NORMAL):
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
        # The tier a golem left the block at (see Quality): the block it builds
        # on the board wears the same word and colour.
        self.quality = quality
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
    def amount(self):
        """The block's single AMOUNT: its scorer's magnitude.

        Every item carries one (see Game._item_magnitudes), and for a block that
        is the number its scorer pays with -- +30 chips, x2 mult. Each effect
        keeps its own strength alongside it (see effect_amounts), because a
        block can carry several magnitudes at once; this is only the scorer's,
        which is what a plain "what is this block worth" question means.
        """
        return self.scorer_amount

    @amount.setter
    def amount(self, value):
        """Setting it sets the scorer's magnitude, so the two never disagree."""
        self.scorer_amount = value

    @property
    def effect(self):
        """The block's primary (first) effect."""
        return self.effects[0] if self.effects else Effect.NONE

    def has_effect(self, effect):
        """True when the block has the given effect (one of possibly many)."""
        return effect in self.effects


class CardItem(Modifiable):
    """A bought card: a permanent score effect applied every run (a Joker)."""
    kind = "card"

    def __init__(self, value, price, col=0, row=0, amount=0,
                 quality=Quality.NORMAL):
        self.value = value  # the card's ID number (a Card constant)
        self.price = price
        self.col = col  # the SHOP cell the offer is drawn in (never a board cell)
        self.row = row
        self.board_cell = None  # the board square the owned card lies on
        self.name = Card.name(value)
        # Its face-down state (the Shuffled trial) is the FLIPPED modifier, a
        # property of Modifiable -- see components.Modifier.
        # The tier a golem left the card at (see Quality).
        self.quality = quality          # the golden/diamond modifiers
        # A composed card's SCORER half magnitude (its own rolled strength): a
        # +Chips half rolled to 45 makes the card pay 45 a unit instead of 30.
        # A whole card has no scorer half, and a card that was never rolled
        # (an old save, a hand-built test card) is 0 — both pay, price and
        # describe at the average, exactly as they did before magnitudes.
        self.amount = amount or 0
        # True while the Shuffled trial has the card turned face over: the card
        # is DRAWN upside down (see ui.draw_card), and pays exactly what it paid
        # — the trial is a handicap, not a change to what the card does.


class ActionItem(Modifiable):
    """A bought action: a one-use power-up that modifies a block or a card.

    Actions come in two versions: v1 (as bought) and v2 (upgraded for
    ACTION_UPGRADE_COST); v2 is much stronger and cannot be upgraded further.
    """
    kind = "action"

    def __init__(self, value, price, version=1, col=0, row=0, amount=None,
                 quality=Quality.NORMAL):
        self.value = value  # the action's ID number (an Action constant)
        self.price = price
        self.version = version  # 1 or 2, held as the V2 modifier
        self.col = col  # the SHOP cell the offer is drawn in (never a board cell)
        self.row = row
        self.board_cell = None  # the board square the owned action lies on
        self.name = Action.name(value)
        # The tier a golem left the action at (see Quality).
        self.quality = quality
        # The action's own MAGNITUDE, for the actions that carry a number (see
        # MAGNITUDES.ACTIONS): the Lantern's is the items it draws, so a golem
        # combining two of them really does draw twice as many. An action with
        # no magnitude, and one restored from before magnitudes existed, is 0.
        if amount is None:
            amount = Action.MAGNITUDE.get(value, 0)
        self.amount = amount


class StructureItem(Modifiable):
    """A bought structure: something on the board a TOOL opens (see Structure).

    A structure is scenery until a tool is used on it: the player selects the
    tool, selects the structure and presses S, and the structure turns into
    what its table says (an action, or a pack to choose from) and is spent.
    """
    kind = "structure"

    def __init__(self, value, price, col=0, row=0):
        self.value = value  # a Structure constant
        self.price = price
        self.col = col
        self.row = row
        self.board_cell = None
        self.name = Structure.name(value)
        # A structure carries no magnitude of its own: what it hands over is a
        # fixed reward (Structure.RESULTS), so its amount is 0 like a tool's and
        # a pack's. It is here because EVERY item has one (see
        # Game._item_magnitudes).
        self.amount = 0


class ToolItem(Modifiable):
    """A tool: the verb(s) a structure is opened with (see Tool).

    The four the player starts with are never spent, so a structure can always
    be opened. The one-shot ones (a brick, a match) are CONSUMED by using them
    and draw for the player afterwards; a tool's own table says which it is (see
    Tool.ENERGY / CONSUMES / DRAWS), so this class only carries the values.
    """
    kind = "tool"

    def __init__(self, value, price=0, col=0, row=0, amount=None):
        self.value = value  # a Tool constant
        self.price = price
        self.col = col
        self.row = row
        self.board_cell = None
        self.name = Tool.name(value)
        # What it does, in the vocabulary the game uses (see Keyword): the verbs
        # it applies, then "consume" and "draw N" when they apply. Kept on the
        # item so the apply code never has to look the tool up twice.
        self.verbs = Tool.verbs(value)
        self.verb = self.verbs[0] if self.verbs else None
        # The tool's AMOUNT (its magnitude, like every other item's): how many
        # steps of REWARD SHAPING one use makes -- a chisel's pack sizes, a
        # gilding cloth's quality tiers -- and 0 for a tool that only opens the
        # door (see Tool.AMOUNT_EFFECT). A golem-folded golden chisel carries 2.
        self.amount = Tool.amount(value) if amount is None else amount
        # The modifiers an item of this kind is made with (see Tool.BORN_WITH):
        # a spark is TEMPORARY whichever door it came through.
        for modifier, stacks in Tool.born_with(value):
            self.set_modifier_stacks(modifier, stacks)

    @property
    def keywords(self):
        """This tool's text, as keywords (see components.Keyword.of)."""
        return Tool.keywords(self.value)

    @property
    def energy(self):
        """What one use of this tool spends of the run's energy."""
        return Tool.energy(self.value)

    @property
    def consumes(self):
        """True when using this tool destroys it."""
        return Tool.consumes(self.value)

    @property
    def draws(self):
        """How many items using this tool draws afterwards."""
        return Tool.draws(self.value)


class PassiveItem(Modifiable):
    """An UNPLAYABLE item: it is never used, it lies in the hand and pays.

    User request: "add an item, 'concrete', that gives +30 chips at the start of
    the run, and is passive." A passive has no ability at all (see
    components.Ability.of and Game._use_ability); its payoff is read at the start
    of every run (see Game._apply_passive_items), which is the whole of what it
    does.
    """
    kind = "passive"

    def __init__(self, value, price=0, col=0, row=0, amount=None):
        self.value = value  # a Passive constant
        self.price = price
        self.col = col
        self.row = row
        self.board_cell = None
        self.name = Passive.name(value)
        # The item's AMOUNT -- its magnitude, like every other item's (see
        # Game._item_magnitudes): the chips a Concrete adds, so 30 unless a
        # golem has folded two of them together (see Game._combine_items).
        self.amount = Passive.amount(value) if amount is None else amount

    @property
    def keywords(self):
        """A passive item's text: "unplayable"."""
        return Passive.keywords(self.value)


def owned_copy(offer):
    """A fresh, independent item carrying exactly what a shop offer sells.

    Two purchases of one KIND must be two items, never one object listed twice:
    a shared object would have a single board square and a single selection
    switch, so the second purchase would add nothing to look at and selling or
    assembling one copy would leave the other behind as a ghost (user report:
    glitches with several copies of the same item).

    Buying an offer no longer needs this — the offer itself becomes the purchase,
    unlocked where it lay (see Game._unlock_offer) — so this is the helper for
    anything that DUPLICATES an offer instead: a reward that grants a second copy
    of what the shelf sells, and the tests that check the "two copies are two
    items" rule.

    Everything a copied item carries is its own — its rolled magnitudes, its
    effects, its pairing numbers — so a copy behaves exactly like the offer it
    came from, without ever being the same thing. The copy stands NOWHERE yet,
    though: it must not inherit the shelf square the offer is lying on (or a
    placed block's link to it), because that square belongs to the offer until
    the copy is dealt one of its own.
    """
    copy = _copy.deepcopy(offer)
    if hasattr(copy, "board_cell"):
        copy.board_cell = None
    if hasattr(copy, "placed_cell"):
        copy.placed_cell = None
    return copy


class ResourceOption(Modifiable):
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


class ItemPack(Modifiable):
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
        # A pack carries no magnitude of its own: what it holds is OPTIONS, and
        # how many it deals is its size (Pack.size). Its amount is 0 so it reads
        # like every other item that has none (see Game._item_magnitudes).
        self.amount = 0

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
    value, a structure its value, a resource option its scorer and magnitude —
    so this is the one answer to "is this the same offer as that one?", used to
    keep the shelf's slots and a pack's options from repeating (see
    Shop._random_offer and Shop._roll_pack). A pack keys on nothing: two packs
    are never the same offer, whatever they hold.
    """
    kind = getattr(offer, "kind", None)
    if kind == "pack":
        return None
    if kind == "block":
        return (kind, offer.shape, tuple(offer.effects), offer.scorer)
    if kind == "resource":
        return (kind, offer.scorer, offer.amount)
    return (kind, getattr(offer, "value", None))


class ScorerToken(Modifiable):
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
        # The runs it still covers ARE its TOKEN stacks (user request: "tokens
        # are just blocks with the 'token' modifier, where the number of stacks
        # a block has is equal to the number of runs more that a block acts as a
        # token"). None means PERMANENT, which the block carries as the
        # Modifier.PERMANENT sentinel.
        self.runs_left = runs_left
        # True once the run's start has picked this token up: a multiplier
        # token is held back for the run's end, so this is what remembers that
        # the run it belongs to has begun. A token created mid-run is never
        # armed, so the run it was born in cannot spend it.
        self.armed = False
        # True once the token has actually paid in the run now in progress.
        self.fired = False

    @property
    def runs_left(self):
        """Runs of coverage left, or None for a permanent (v2) token."""
        stacks = self.block.modifier_stacks(Modifier.TOKEN)
        if not stacks or stacks == Modifier.PERMANENT:
            return None if stacks == Modifier.PERMANENT else 0
        return stacks

    @runs_left.setter
    def runs_left(self, runs):
        self.block.set_modifier_stacks(
            Modifier.TOKEN, Modifier.PERMANENT if runs is None else int(runs))

    # A token IS its block (user request: "tokens are just blocks with the
    # 'token' modifier"), so its modifiers are the block's: one existence, one
    # place the state lives (see Modifiable).
    def modifier_stacks(self, modifier):
        return self.block.modifier_stacks(modifier)

    def set_modifier_stacks(self, modifier, stacks):
        self.block.set_modifier_stacks(modifier, stacks)
        return self

    # The stored block answers for the token, so the drawing, the save file and
    # the sidebar keep reading one thing.
    @property
    def scorer(self):
        return self.block.scorer

    @property
    def scorer_amount(self):
        return self.block.scorer_amount

    @property
    def amount(self):
        """The token's AMOUNT is its kept block's scorer magnitude."""
        return self.block.scorer_amount

    @amount.setter
    def amount(self, value):
        """Setting it sets the kept block's, so the two can never disagree."""
        self.block.scorer_amount = value

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


class EnergyReadout:
    """Hover target for the top bar's ENERGY bar.

    The bar is not an item either, but hovering it opens the same info box an
    item gets (see Game._describe_item), saying what energy is spent on, how
    much the run started with, and that it comes back at the start of the next
    run. Like the cash readout's, the single instance below is never bought,
    sold or drawn; it only gives the bar something to be hovered as.
    """


ENERGY_READOUT = EnergyReadout()
