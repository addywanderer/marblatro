"""Card score-effect logic for Marblatro.

The owned-card score effects live here: the measured whole cards that fire at
the start of a run, at the end of it or on a fragile break (see
components.Card.NAMED), the collision-triggered scorer cards (a match group plus
a scorer — see components' MATCH GROUPS section), Blueprint copying, and the
small block/board helpers and per-run measures they use. Each function takes the
``Game`` as its first argument (mirroring the physics.py pattern); main.py's
Game keeps thin wrappers (_apply_cards, _apply_cards_on_finish,
_apply_cards_on_collision, _on_fragile_broken) that delegate to this module, so
the rest of the code and the tests call them as before.
"""

import sys

from components import (
    UNIT_CARD_SCORERS,
    magnitude_payoff,
    match_group_card_meta,
    match_group_matches_block,
    points_text,
    resource_points_for,
    scorer_magnitude_scale,
)

# main.py defines the enums, the layout constants, and the Game methods these
# functions call (see physics.py for the sys.modules pattern). Bind whatever
# module is actually running main.py at import time.
if "main" in sys.modules:
    _card_source = sys.modules["main"]
elif "__main__" in sys.modules and hasattr(sys.modules["__main__"], "CardItem"):
    _card_source = sys.modules["__main__"]
else:  # pragma: no cover - only when cards.py is imported standalone
    import main as _card_source

BLUE = _card_source.BLUE
block_resale_price = _card_source.block_resale_price
Card = _card_source.Card
Effect = _card_source.Effect
GREEN = _card_source.GREEN
GRID_HEIGHT = _card_source.GRID_HEIGHT
GRID_SIZE = _card_source.GRID_SIZE
GRID_WIDTH = _card_source.GRID_WIDTH
MARBLE_BOX_COORDS = _card_source.MARBLE_BOX_COORDS
MARBLE_RADIUS = _card_source.MARBLE_RADIUS
ORANGE = _card_source.ORANGE
QUICK_SCALE = _card_source.QUICK_SCALE
RED = _card_source.RED
Scorer = _card_source.Scorer
YELLOW = _card_source.YELLOW
del _card_source


def _card_disabled(game, card):
    """True when a card is disabled for the run.

    The Card-cutter trial disables one random card (game.disabled_card); the
    deal-breaker trial disables every card of one random condition
    (game.deal_broken_cards). Either way the card's score effect is skipped,
    and a Blueprint cannot copy it. The predicate itself lives on Game so the
    passive whole-card effects (Game._has_card) share this single rule.
    """
    return game._card_disabled(card)


def apply_cards(game):
    """Apply the start-of-run card effects.

    A Fragile Breaks (Wrecking Ball) card first applies its permanent, saved
    bonus (the +3 mult a break has banked across the game), then Tesseract's
    reroll bonus, then every owned card whose effect fires at the START of a run
    (Joker's +4 mult, Pillar's fullest column, Banker's cash, Glitch's random
    mult, Ripped Card, Cozy, Painting, Synthesizer, Island) in card-area order,
    so a card's particle pops on the card that paid. End-of-run and
    fragile-break cards fire elsewhere (see apply_cards_on_finish /
    on_fragile_broken).
    """
    if _owns_wrecking_ball_card(game):
        _apply_wrecking_bonus(game)
    _apply_tesseract_bonus(game)
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        if value is not None:
            apply_card_start(game, card, value)


def _owns_wrecking_ball_card(game):
    """True when the player owns a live Wrecking Ball card.

    A Blueprint copy counts (it plays the card it sits next to), and a card the
    run's trial disabled does not — the same rule every other card effect
    follows.
    """
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        if effective_card_value(game, i) == Card.WRECKING_BALL:
            return True
    return False


def _apply_wrecking_bonus(game):
    """Apply the permanent Fragile Breaks (Wrecking Ball) bonus at run start.

    The bonus has grown by +3 mult for every fragile block that broke across the
    whole game (saved with the game, see Game.wrecking_bonus), and applies to
    the multiplier once at the start of each run. The chips/xMult keys are still
    carried in that dict for old saves; a Wrecking Ball card only pays mult now.
    """
    bonus = getattr(game, "wrecking_bonus", None)
    if not bonus:
        return
    chips = bonus.get(Scorer.CHIPS_ADD, 0)
    mult = bonus.get(Scorer.MULT_ADD, 0)
    factor = bonus.get(Scorer.MULT_MUL, 1.0)
    if chips:
        game.score_chips += chips
    if mult:
        game.score_mult += mult
    if factor != 1.0:
        game.score_mult *= factor


def _named_card_units(game, measure):
    """A named card's magnitude in card-scorer units this run.

    One unit is one standard payoff (+30 chips / +4 mult / +0.25 xMult) and the
    card's own ratio scales it (see components.Card.NAMED). A return of 0 means
    the card's measure came to nothing, which is its gate: no units, no payoff,
    no particle (a Ripped Card on a board of 6 blocks, a Skater with no slippery
    blocks, an empty board for Pillar). The measures are the ones the named
    conditions used:

    * start = 1 (the card simply fires);
    * distance = 4 x the fraction of the board the marble(s) travelled;
    * black_hole / air_time = seconds pulled by a black hole / spent airborne;
    * fullest_column = the blocks in the fullest column;
    * cash_held = whole $10 held;  slippery = slippery blocks owned;
    * random = the run RNG's 0..6 (so replaying a run pays the same amount —
      see Game.run_rng, the same rule every random output follows);
    * few_blocks = 1 while the board holds 5 blocks or fewer;
    * cozy = 1 while 10 or fewer board units are unlocked;
    * painting = the board's total sell price in whole dollars;
    * synthesizer = the cards in the card area;  island = the groups the
      unlocked board units form;
    * pipe_streak = the groups of PIPE-GROUP blocks the run's contacts
      completed (counted live by Game._count_pipe_streak, see
      FOUNTAIN_STREAK_LENGTH — three different Pipe/Drain/Pipe Bend blocks in a
      row, anything else breaking the run).
    """
    if measure == "start":
        return 1.0
    if measure == "distance":
        return 4 * card_distance_fraction(game)
    if measure == "black_hole":
        return getattr(game, "black_hole_time", 0.0)
    if measure == "air_time":
        return getattr(game, "air_time", 0.0)
    if measure == "fullest_column":
        return fullest_column_count(game)
    if measure == "cash_held":
        return max(0, game.cash) // 10
    if measure == "slippery":
        return owned_slippery_block_count(game)
    if measure == "random":
        # Glitch's 0..6 units come from the RUN's own RNG (see Game.run_rng),
        # so replaying the run pays the same amount instead of rerolling until
        # it lands high.
        return game.run_rng.uniform(0, 6.0)
    if measure == "fragile_breaks":
        return 1.0
    if measure == "few_blocks":
        return 1.0 if len(game.grid) <= 5 else 0.0
    if measure == "cozy":
        return 1.0 if len(getattr(game, "unlocked_cells", set())) <= 10 else 0.0
    if measure == "painting":
        return board_sell_total(game)
    if measure == "synthesizer":
        return len(game.cards)
    if measure == "island":
        return island_group_count(game)
    if measure == "pipe_streak":
        # Counted as the run goes (the contacts that make a streak happen long
        # before the run ends), never re-derived here: the streak is over by the
        # time this is read, and a run that is retried replays the same touches
        # (see Game.reset_run).
        return getattr(game, "pipe_streak_run_units", 0)
    return 0.0


def _apply_named_card(game, card, value, fx=None, fy=None, units=None):
    """Pay one named card's payoff, and say whether it paid anything.

    The card's table row gives the scorer, the ratio and the measure (see
    components.Card.NAMED), and magnitude_payoff turns those into chips / mult /
    an xMult factor. A whole card has no rolled scorer half, so the scale is
    always 1.0: a Joker adds exactly +4 mult. A card whose measure came to 0
    pays nothing and pops nothing. ``fx``/``fy`` place the particle where the
    run ended (an end-of-run card); with none it pops on the card area.
    """
    meta = Card.NAMED.get(value)
    if meta is None:
        return False
    _phase, scorer, ratio, measure = meta
    if units is None:
        units = _named_card_units(game, measure)
    if not units:
        return False
    # The three standard bases, at scale 1.0 (a whole card has no scorer half to
    # roll) — the same arithmetic _apply_unit_card pays for a unit card. The
    # per-unit chip count is whole, but a fractional unit count (Plane's air
    # time, Astronaut's black-hole seconds, Explorer's distance) keeps its
    # fractional payoff: nothing is rounded internally, only the particle text.
    if scorer == Scorer.CHIPS_ADD:
        gained = int(30 * ratio + 0.5) * units
        text, color = game._particle_amount_text(gained), GREEN
        game.score_chips += gained
    elif scorer == Scorer.MULT_ADD:
        gained = 4 * ratio * units
        text, color = game._particle_amount_text(gained), BLUE
        game.score_mult += gained
    else:  # Scorer.MULT_MUL
        factor = 1 + 0.25 * ratio * units
        text, color = game._particle_amount_text(factor), RED
        game._apply_xmult(factor)
    if fx is None:
        game._spawn_card_particle(card, text, color)
    else:
        game._spawn_score_particle(fx, fy, text, color)
    return True


def apply_card_start(game, card, value):
    """Apply one card value's start-of-run effect (from ``card``).

    Only the named cards do anything here (see Card.NAMED), and only the ones
    whose phase is "start": Joker, Pillar, Banker, Glitch, Ripped Card, Cozy,
    Painting, Synthesizer and Island. `card` is the card that triggers the
    effect (possibly a Blueprint copying its left neighbour), so the particle
    appears on that card in the card area.
    """
    meta = Card.NAMED.get(value)
    if meta is None or meta[0] != "start":
        return
    _apply_named_card(game, card, value)


def _apply_tesseract_bonus(game):
    """Apply the permanent Tesseract bonus at the start of a run.

    The Tesseract whole card permanently gains +0.1 xMult for every shop
    reroll the player makes while owning it (saved with the game, see
    Game._tesseract_reroll_note). The accumulated factor multiplies the run's
    multiplier once, at the start of the run, like the Wrecking Ball bonus.
    """
    if not game._has_card(Card.TESSERACT):
        return
    factor = getattr(game, "tesseract_bonus", 1.0)
    if factor != 1.0:
        game.score_mult *= factor


def _card_effect_source(game, index):
    """The card object whose effect fires at ``index``, or None.

    A Blueprint copies the card to its immediate left, so the effect, the value
    AND the scorer magnitude that fires all belong to that card. Returns None
    when there is nothing to copy: no left neighbour, a Blueprint there, or a
    card disabled by the Card cutter / Deal breaker trial.
    """
    card = game.cards[index]
    if card.value != Card.BLUEPRINT:
        return card
    if index == 0:
        return None
    left = game.cards[index - 1]
    if _card_disabled(game, left) or left.value == Card.BLUEPRINT:
        return None
    return left


def effective_card_value(game, index):
    """The effective card value at a card-area index, following Blueprint.

    A Blueprint copies the card to its immediate left. If there is no card
    to the left, that card is itself a Blueprint, or it is disabled by the
    Card cutter trial, the Blueprint does nothing. Non-Blueprint cards use
    their own value.
    """
    source = _card_effect_source(game, index)
    return source.value if source is not None else None


def effective_card_amount(game, index):
    """The scorer magnitude the card firing at ``index`` pays with.

    A composed card carries its SCORER half's own rolled magnitude (the shop
    rolls one per offer; a card built from a toolbox scorer keeps that piece's),
    and a Blueprint copies it along with the value. Whole cards have no scorer
    half, and a card that was never rolled has no magnitude: both pay exactly
    as they did before magnitudes existed (see scorer_magnitude_scale).
    """
    source = _card_effect_source(game, index)
    return getattr(source, "amount", 0) or 0 if source is not None else 0


# ---------------------------------------------------------------------------
# The per-run measures the named cards scale by (see _named_card_units): the
# islands the unlocked board units form, the board's total sell value, the
# distance the marble travelled, the fullest column, the slippery blocks owned,
# ... A match-group card measures nothing — it pays one standard unit per
# matching collision.
#
# They used to be read through `_condition_units(game, condition)`: one
# condition id in, a unit count out. The named conditions are whole cards now
# (see components.Card.NAMED), so that dispatch is _named_card_units above and
# only the measures themselves are left here.
# ---------------------------------------------------------------------------
def island_group_count(game):
    """How many separate islands the unlocked board units form.

    An island is a group of unlocked units that reach each other through shared
    SIDES (up/down/left/right). Two groups that only touch at a CORNER are
    different islands — the corner between them is water — so a board cut along
    a diagonal counts as two. The count is of GROUPS, not units: the starter
    2x3 region is one island, and so is the whole board once it has been
    unlocked into one continent. A board with nothing unlocked has none.

    Counted with a flood fill rather than by walking the board in order, so a
    group is followed around corners of its own shape (an L-shaped island is
    one, however the rows happen to be ordered).
    """
    remaining = set(getattr(game, "unlocked_cells", ()))
    islands = 0
    while remaining:
        islands += 1
        stack = [remaining.pop()]
        while stack:
            x, y = stack.pop()
            for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbour in remaining:
                    remaining.discard(neighbour)
                    stack.append(neighbour)
    return islands


def board_sell_total(game):
    """The total sell price of every block on the board, in whole dollars.

    A placed block's sell price is the resale value it was placed with, so a
    block assembled from nothing is worth $0 (the game would pay nothing for
    it) while a bought block keeps what it cost. A block carrying no stored
    resale value (one built directly, e.g. in a test) falls back to the price
    of its own parts. The Start/Finish role blocks count like any other block
    (they are free, so they normally add nothing).
    """
    total = 0
    for block in game.grid.values():
        # The block's own stored price; the helper materializes one for a block
        # that never got a stored value (see main.block_resale_price).
        total += max(0, block_resale_price(block))
    return total


def _apply_unit_card(game, card, value, scorer, fx, fy, units=None, amount=None):
    """Apply one match-group card's UNIT-scorer payoff (+Chips/+Mult/xMult).

    Called once per matching collision (units = 1, see apply_card_on_collision).
    Every unit scorer stays proportional to the standard base: chips add
    round(30 * scale) a unit, +Mult adds 4 * scale a unit, and xMult multiplies
    the multiplier by (1 + 0.25 * scale a unit) — the xMult is an ADD, never a
    stack of x1.25s. ``amount`` is the card's own scorer magnitude, which scales
    the whole payoff (a +Chips card rolled to 45 pays 45 a hit instead of 30),
    and the popup appears on the card in the card area.
    """
    if units is None:
        units = 1.0
    # A match-group card pays ONE standard unit per matching hit: the ratio the
    # old conditions carried (some paid a fraction, some a multiple) is gone.
    ratio = 1.0
    scale = scorer_magnitude_scale(scorer, amount)
    if scorer == Scorer.CHIPS_ADD:
        per_unit = int(30 * scale * ratio + 0.5)
        # The per-unit chip count is whole, but a fractional unit count (e.g.
        # air time) keeps its fractional chips: nothing is rounded internally.
        gained = per_unit * units
        if not gained:
            return
        game.score_chips += gained
        text = game._particle_amount_text(gained)
        color = GREEN
    elif scorer == Scorer.MULT_ADD:
        gained = 4 * scale * ratio * units
        if not gained:
            return
        game.score_mult += gained
        text = game._particle_amount_text(gained)
        color = BLUE
    else:  # Scorer.MULT_MUL
        factor = 1 + 0.25 * scale * ratio * units
        if factor == 1.0:
            return
        # Every xMult trigger multiplies, so a card that fires on several
        # matching collisions compounds its factor (see Game._apply_xmult).
        amount = game._apply_xmult(factor)
        text = game._particle_amount_text(amount)
        color = RED
    if fx is None:
        game._spawn_card_particle(card, text, color)
    else:
        game._spawn_score_particle(fx, fy, text, color)


def _fire_flat_scorer(game, card, scorer, fx=None, fy=None, amount=None):
    """Fire one trigger of a flat (non +Chips/+Mult/xMult) card scorer.

    Cash pays out, Sharp multiplies the multiplier, Shreds/Rubble/Ideas/Picky
    bank resource points (converted after a run), Parts banks components (granted
    when the run is continued), Fresh grants free rerolls, and Quick arms a
    payout that resolves at the
    marble's NEXT block hit, keyed to that impact's speed. The board/run
    scorers (Seed, Roomy, Rally, Drill, Undertaker, Gilded, Debt, Voyager,
    Random, Satanic, Lucky) pay from the same state their block version reads.
    ``amount`` is the card's own scorer magnitude (a Cash card rolled to $24
    pays $24); a card with no magnitude uses the scorer's average, exactly as
    before. Particles pop on the card (start/collision) or where the run ended.
    """
    if not amount:
        amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    if scorer == Scorer.CASH:
        gained = int(amount)
        # Cash is deferred: it is paid out with the run's end-of-run award
        # (only sticks after a run), not added the moment the card
        # fires.
        game.card_cash_run_gain += gained
        text, color = f"${gained}", YELLOW
    elif scorer == Scorer.SHARP:
        factor = amount
        # Sharp multiplies the multiplier by its own rolled amount; every
        # trigger multiplies again.
        text, color = game._particle_amount_text(game._apply_xmult(factor)), RED
    elif scorer == Scorer.QUICK:
        # Payoff is deferred: chips come from the speed of the NEXT block the
        # marble hits after this card fired (see cards.py on how the armed card
        # resolves in _handle_block_contacts).
        armed = getattr(game, "armed_quick", None)
        if armed is not None:
            armed.add(card)
        return
    elif scorer in (Scorer.SHREDS, Scorer.RUBBLE, Scorer.IDEAS, Scorer.PICKY):
        # A resource card banks its own fraction of a point (1/2 for most,
        # 1/3 for Shreds, at the average magnitude).
        points = resource_points_for(scorer, amount)
        game._add_resource_points(scorer, points)
        text, color = points_text(points), ORANGE
    elif scorer == Scorer.PARTS:
        # Parts cards bank one component per point of their own magnitude.
        # Like the Cash cards above, the grant is deferred: nothing reaches the
        # toolbox until the player continues the run (see Game._continue_run),
        # so a retried run hands nothing over.
        game.parts_run_gain += max(1, int(amount))
        text, color = "Component", ORANGE
    elif scorer == Scorer.FRESH:
        # Fresh cards grant their own magnitude in free shop rerolls
        # immediately (no point system).
        rerolls = max(1, int(amount))
        game.free_rerolls += rerolls
        text, color = f"{rerolls}", ORANGE
    elif scorer == Scorer.RANDOM:
        # Random cards pick one of three rewards; the pick is chosen BEFORE
        # the run (see Game._roll_run_random_outputs) and kept on the card, so
        # every trigger of the card gives the same reward and retrying the run
        # replays it.
        reward = game._run_random_result(card, Scorer.RANDOM)["reward"]
        if reward == 0:
            game.score_chips += 35
            text, color = game._particle_amount_text(35), GREEN
        elif reward == 1:
            game.score_mult += 5
            text, color = game._particle_amount_text(5), BLUE
        else:
            factor = 1.3  # +0.3 xMult
            text, color = game._particle_amount_text(game._apply_xmult(factor)), RED
    elif scorer == Scorer.VOYAGER:
        # Voyager cards add their own rolled rate per pixel the run's marbles
        # have traveled in total when the card fires (a card has no single
        # touching marble, so it measures the whole run's travel).
        total = sum(getattr(m, "distance", 0.0) for m in game.marbles)
        gained = amount * total
        if gained <= 0:
            return
        game.score_mult += gained
        text, color = game._particle_amount_text(gained), BLUE
    elif scorer == Scorer.SATANIC:
        # Satanic cards multiply the multiplier by their own rolled amount per
        # trigger, and every trigger multiplies again. They are
        # a one-run deal: they are permanently destroyed after a run, whatever
        # they did in it (see _continue_run in main.py).
        factor = amount
        text, color = game._particle_amount_text(game._apply_xmult(factor)), RED
    elif scorer == Scorer.SEED:
        # Seed: the card pays per Seed block on the board, exactly as the block
        # scorer does (the Garden card doubles the per-seed mult).
        per_seed = amount
        if game._has_card(Card.GARDEN):
            per_seed *= 2
        gained = per_seed * sum(1 for b in game.grid.values()
                                if b.scorer == Scorer.SEED)
        if gained <= 0:
            return
        game.score_mult += gained
        text, color = game._particle_amount_text(gained), BLUE
    elif scorer == Scorer.ROOMY:
        # Roomy: chips for each unlocked board unit.
        gained = amount * len(getattr(game, "unlocked_cells", ()))
        if gained <= 0:
            return
        game.score_chips += gained
        text, color = game._particle_amount_text(gained), GREEN
    elif scorer == Scorer.RALLY:
        # Rally: mult for each fresh block touch this run before this trigger.
        gained = amount * max(0, game.run_fresh_touches - 1)
        if gained <= 0:
            return
        game.score_mult += gained
        text, color = game._particle_amount_text(gained), BLUE
    elif scorer == Scorer.DRILL:
        # Drill: marks whole locked board squares to unlock after the run (the
        # rolled magnitude is a rate, so the count is rounded, never 0).
        units = max(1, round(amount))
        game.drill_run_units += units
        text, color = game._particle_amount_text(units), ORANGE
    elif scorer == Scorer.UNDERTAKER:
        # Undertaker: mult for each block destroyed this run.
        gained = amount * game.run_blocks_destroyed
        if gained <= 0:
            return
        game.score_mult += gained
        text, color = game._particle_amount_text(gained), BLUE
    elif scorer == Scorer.GILDED:
        # Gilded: 1/6 of the current chips as mult.
        gained = game.score_chips / 6.0
        if gained <= 0:
            return
        game.score_mult += gained
        text, color = game._particle_amount_text(gained), BLUE
    elif scorer == Scorer.DEBT:
        # Debt pays chips now and cancels the run's interest (see _award_cash).
        gained = int(amount)
        game.score_chips += gained
        game.debt_run_triggered = True
        text, color = game._particle_amount_text(gained), GREEN
    elif scorer == Scorer.LUCKY:
        # Lucky: two independent pre-rolled outcomes (1/3 +130 chips, 1/9 $40),
        # chosen before the run like a Lucky block's rolls.
        result = game._run_random_result(card, Scorer.LUCKY)
        if result["chips"]:
            game.score_chips += 130
            text, color = game._particle_amount_text(130), GREEN
            if fx is None:
                game._spawn_card_particle(card, text, color)
            else:
                game._spawn_score_particle(fx, fy, text, color)
        if result["cash"]:
            game.card_cash_run_gain += 40
            if fx is None:
                game._spawn_card_particle(card, "$40", YELLOW)
            else:
                game._spawn_score_particle(fx, fy, "$40", YELLOW)
        return
    else:
        return
    if fx is None:
        game._spawn_card_particle(card, text, color)
    else:
        game._spawn_score_particle(fx, fy, text, color)


# The scorers whose card payoff reads a BLOCK. A card has no position, row,
# border or marble of its own, so these read "the block the condition hands the
# card" — see _fire_card_scorer and components._reference_block_phrase. A
# start-condition card of this kind cannot fire at run start (no block has been
# hit yet), so it waits for the run's first block (fire_first_block_cards).
_BLOCK_PAYOFF_SCORERS = (Scorer.EFFECTIVE, Scorer.SUMMIT, Scorer.AIRBALL,
                         Scorer.POWERLINE, Scorer.FRONTIER, Scorer.CLUSTER,
                         Scorer.COLOSSUS, Scorer.ECHO, Scorer.BOMB)


# The gate a card used to check ("did the condition happen at all") is gone: a
# named card's own unit count IS its gate (a Ripped Card on a board of six
# blocks measures 0 and pays nothing — see _named_card_units), and a match-group
# card's gate is the collision itself (match_group_matches_block).


def _fire_card_scorer(game, card, scorer, amount=None, block=None, marble=None,
                      air=None, fx=None, fy=None):
    """Fire one card trigger for ANY card scorer.

    Block-relative scorers go through _fire_block_payoff with the block the
    condition handed the card; a block-relative card with no such block (a
    start card before any block is hit, a run that never touched one) grants
    nothing at all. Every other scorer is a flat payoff that reads the board,
    the run or the score (see _fire_flat_scorer).
    """
    if scorer in _BLOCK_PAYOFF_SCORERS:
        if block is None:
            return
        _fire_block_payoff(game, card, scorer, amount, block, marble, air, fx, fy)
        return
    _fire_flat_scorer(game, card, scorer, fx, fy, amount)


def _fire_block_payoff(game, card, scorer, amount, block, marble=None, air=None,
                       fx=None, fy=None):
    """A card payoff that reads ``block`` (the condition's reference block).

    Mirrors the block version of the scorer, with the card's own magnitude in
    place of the block's amount: Powerline counts the blocks in that block's
    row, Frontier its locked/border neighbours, Cluster its neighbours,
    Colossus the marble's grown radius, Echo re-fires that block's scorer and
    Bomb primes its cell to detonate after the run.
    """
    if not amount:
        amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
    if scorer == Scorer.EFFECTIVE:
        _fire_effective(game, card, block, fx, fy, amount=amount)
        return
    if scorer == Scorer.SUMMIT:
        _fire_summit(game, card, block, fx, fy, amount=amount)
        return
    if scorer == Scorer.AIRBALL:
        streak = air if air is not None else getattr(marble, "air_streak", 0.0)
        _fire_airball(game, card, streak, fx, fy, block=block, amount=amount)
        return
    if scorer == Scorer.POWERLINE:
        gained = amount * sum(1 for b in game.grid.values() if b.y == block.y)
        if gained > 0:
            game.score_chips += gained
            _pop(game, card, game._particle_amount_text(gained), GREEN, block, fx, fy)
        return
    if scorer == Scorer.FRONTIER:
        units = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = block.x + dx, block.y + dy
            if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                units += 1  # the outer board border
            elif (nx, ny) not in getattr(game, "unlocked_cells", ()):
                units += 1  # a locked board unit
        gained = amount * units
        if gained > 0:
            game.score_mult += gained
            _pop(game, card, game._particle_amount_text(gained), BLUE, block, fx, fy)
        return
    if scorer == Scorer.CLUSTER:
        adjacent = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if (block.x + dx, block.y + dy) in game.grid)
        gained = amount * adjacent
        if gained > 0:
            game.score_mult += gained
            _pop(game, card, game._particle_amount_text(gained), BLUE, block, fx, fy)
        return
    if scorer == Scorer.COLOSSUS:
        # The marble the trigger involves (the touching one, or the run's if the
        # card fires at run start/end), so a grown marble multiplies harder.
        target = marble if marble is not None else next(iter(game.marbles), None)
        radius = getattr(target, "radius", MARBLE_RADIUS)
        gained = max(0.0, radius - MARBLE_RADIUS) * amount
        if gained > 0:
            factor = game._apply_xmult(1 + gained)
            _pop(game, card, game._particle_amount_text(factor), RED, block, fx, fy)
        return
    if scorer == Scorer.ECHO:
        # Echo re-fires the reference block's own scorer (a card has no "block
        # touched before it", so it copies the block its condition is about).
        # Roles, None and other Echo blocks are skipped so copies can't chain.
        if (block.scorer not in (Scorer.NONE, Scorer.START, Scorer.FINISH,
                                 Scorer.ECHO)):
            game._apply_block_score_effect(target_marble(game, marble), block)
        return
    # Scorer.BOMB: prime the reference block's cell, exactly like a Bomb block.
    game.bomb_cells.add((block.x, block.y))
    _pop(game, card, "Bomb", ORANGE, block, fx, fy)


def target_marble(game, marble):
    """The marble an Echo card re-fires with (the touching one, else the run's)."""
    if marble is not None:
        return marble
    return next(iter(game.marbles), None)


def _pop(game, card, text, color, block=None, fx=None, fy=None):
    """Pop a card particle (on the card area or where the run ended)."""
    if fx is None:
        game._spawn_card_particle(card, text, color, block=block)
    else:
        game._spawn_score_particle(fx, fy, text, color)


def _real_effect_count(block):
    """The number of real (non-None) effects on a block."""
    return sum(1 for e in block.effects if e != Effect.NONE)


def _fire_quick_card(game, card, speed, fx=None, fy=None):
    """A Quick card's payoff: chips from the speed of a block contact.

    A start/collision Quick card arms for the NEXT block hit (the classic
    behaviour, see _fire_flat_scorer); an end-condition Quick card has no next
    block, so it pays from the speed of the run's LAST block contact (see
    apply_card_finish).
    """
    gained = max(0.0, speed) * QUICK_SCALE
    if gained <= 0:
        return
    game.score_chips += gained
    _pop(game, card, game._particle_amount_text(gained), GREEN, None, fx, fy)


def _fire_effective(game, card, block, fx=None, fy=None, amount=None):
    """Effective scorer payoff: xMult if the block has 2+ effects.

    Called on a card trigger that involves a block (a matching collision hit, a
    fragile break, the run's first block for a Start-condition card, or the
    run's last block for an End-condition card). Grants nothing (and pops no
    particle) when the block has fewer than two real effects. ``amount`` is the
    card's own magnitude: Effective's average is 2.0 (x2 = +1 xMult), so a
    rolled 3.0 triples instead.
    """
    if _real_effect_count(block) < 2:
        return
    factor = amount or 2.0  # +1 xMult at the average
    text = game._particle_amount_text(game._apply_xmult(factor))
    color = RED
    if fx is None:
        game._spawn_card_particle(card, text, color, block=block)
    else:
        game._spawn_score_particle(fx, fy, text, color)


def _summit_rows(block):
    """How many units (rows) above the bottom row a grid block sits.

    The bottom row is y = GRID_HEIGHT - 1 (0 units above); the top row is y = 0
    (GRID_HEIGHT - 1 units above).
    """
    return max(0, (GRID_HEIGHT - 1) - block.y)


def _fire_summit(game, card, block, fx=None, fy=None, amount=None):
    """Summit scorer payoff: its amount in mult per row above the bottom.

    A block on the bottom row grants nothing (and pops no particle); a block
    higher up grants the card's own amount (0.75 mult at the average) for every
    row it sits above the bottom row. Called on a card trigger that involves a
    block (a matching collision hit, a fragile break, the run's first block for
    a Start-condition card, or the run's last block for an End-condition card).
    """
    gained = (amount or 0.75) * _summit_rows(block)
    if gained <= 0:
        return
    game.score_mult += gained
    text = game._particle_amount_text(gained)
    color = BLUE
    if fx is None:
        game._spawn_card_particle(card, text, color, block=block)
    else:
        game._spawn_score_particle(fx, fy, text, color)


def _fire_airball(game, card, air_streak, fx=None, fy=None, block=None, amount=None):
    """Airball scorer payoff: its amount in mult per second airborne.

    ``air_streak`` is the touching marble's continuous airborne seconds
    (touching no block, including Shape.None / pipes / portals) immediately
    before the touch the card is rewarding. Fractional seconds count and stay
    a float. ``amount`` is the card's own magnitude (8 mult per second at the
    average). A 0-streak (the marble just touched something else) grants
    nothing and pops no particle.
    """
    gained = (amount or Scorer.DEFAULT_AMOUNT.get(Scorer.AIRBALL, 8)) \
        * max(0.0, air_streak)
    if gained <= 0:
        return
    game.score_mult += gained
    text = game._particle_amount_text(gained)
    color = BLUE
    if fx is None:
        game._spawn_card_particle(card, text, color, block=block)
    else:
        game._spawn_score_particle(fx, fy, text, color)


# The start-of-run path is live again for the named cards (apply_cards /
# apply_card_start, at the top of this file). What is NOT back is
# `fire_first_block_cards`: it existed because a start-phase card could carry a
# BLOCK-relative flat scorer (Effective, Summit, Airball, ...), which cannot
# decide at run start because no block has been hit yet. No named card reads a
# block — they read the run's board, cash, cards and time — so nothing waits for
# the first block any more, and a match-group card fires on a collision when it
# needs a block (see _BLOCK_PAYOFF_SCORERS).


def _block_feeds_collision_cards(block):
    """True while a collided block may still trigger a collision card.

    A shape/effect collision card rides on the block's own triggers: it fires
    only while the block has one left to spend, so a block that has used them
    all up (it wears the used-up red border) stops feeding cards even if the
    marble touches it again.

    Blocks that never spend a trigger can never run out, so they are refused
    outright rather than firing forever:

    - the run's Start/Finish role blocks, which are not scoring blocks at all
      (the shop never sells their scorers, and a role block's triggers are
      never spent); and
    - a Portal block with no scorer, whose pass-through is deliberately exempt
      from the trigger behaviour (it may be travelled through 100 times a run).
    """
    if block.scorer in (Scorer.START, Scorer.FINISH):
        return False
    if block.scorer == Scorer.NONE and block.has_effect(Effect.PORTAL):
        return False
    return block.triggers_left > 0


def apply_card_on_collision(game, block, marble=None):
    """Apply owned cards when the marble collides with a block.

    Every card is built on a MATCH GROUP — a group of shapes, or one effect — so
    this fires each owned card whose group matches the collided block: a unit
    scorer (+Chips/+Mult/xMult) pays one standard unit, and every other scorer
    fires one block-style trigger (Cash, Sharp, Quick, a resource point, or any
    board/run/block-relative scorer, with the collided block as its reference
    block). A card only fires while the collided block can still spend a trigger
    (see _block_feeds_collision_cards), so a block feeds cards once per trigger
    it has. A Blueprint copies the card to its immediate left; a card disabled
    by the Card cutter or Deal breaker trial is skipped. Called once per fresh
    collision (the marble newly entering contact with the block). ``marble`` is
    the touching marble (an Airball card rewards its airborne streak).
    """
    if not _block_feeds_collision_cards(block):
        return
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        if value is None:
            continue
        meta = match_group_card_meta(value)
        if meta is None:
            # A card that is not built on a match group is passive: it pays
            # nothing on a collision (Coupon, Tesseract, Showman, ...).
            continue
        group, scorer = meta
        if not match_group_matches_block(group, block):
            continue
        amount = effective_card_amount(game, i)
        if scorer in UNIT_CARD_SCORERS:
            _apply_unit_card(game, card, value, scorer, None, None, units=1.0,
                             amount=amount)
        else:
            _fire_card_scorer(game, card, scorer, amount, block=block,
                              marble=marble)


# ---------------------------------------------------------------------------
# The moments that are NOT a collision: the end of the run and a fragile block
# breaking. The named cards that fire then are Explorer, Astronaut, Plane and
# Skater (at the end) and Wrecking Ball (on each break); main.py calls
# apply_cards_on_finish once the run is over and on_fragile_broken from the
# block-shatter path.
# ---------------------------------------------------------------------------
def run_finish_pos(game):
    """A screen position where the run ended, for the end-of-run popup.

    Uses the first finished marble (resting on its FINISH block) so the popup
    appears where the player is looking — the marble box — instead of at the
    top-of-screen card area, where it would be easy to miss.
    """
    for marble in game.marbles:
        if getattr(marble, "finished", False):
            return (float(marble.position[0]), float(marble.position[1]))
    return (MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2] // 2,
            MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3] // 2)


def apply_cards_on_finish(game):
    """Apply the end-of-run card effects.

    The named cards whose phase is "end" pay here — Explorer's distance xMult,
    Astronaut's black-hole mult, Plane's air-time chips, Skater's slippery
    xMult and Fountain's pipe streaks — because their measures are only final
    once the marbles have stopped. A Blueprint copies the card to its immediate left; a card disabled
    by the Card cutter or Deal breaker trial is skipped (and can't be copied
    either). Their popups appear where the run ended (on the finished marble),
    so they are visible instead of lost at the top-of-screen card area.
    """
    fx, fy = run_finish_pos(game)
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        if value is not None:
            apply_card_finish(game, card, value, fx, fy)


def apply_card_finish(game, card, value, fx, fy):
    """Apply one card value's end-of-run effect (from ``card``).

    Only the named cards do anything here, and only the ones whose phase is
    "end" (see components.Card.NAMED). Every other card is either a start or a
    fragile-break card, a collision card, or one of the passive whole cards
    (ERR 404 / Blueprint / Showman / Coupon / ...), which do nothing at the end
    of a run.
    """
    meta = Card.NAMED.get(value)
    if meta is None or meta[0] != "end":
        return
    _apply_named_card(game, card, value, fx, fy)


def card_distance_fraction(game):
    """The fraction of the marble box's total grid units the marble(s) travelled.

    Explorer's units are 4x this fraction (so a full board is 4 units, i.e. the
    x2 the card tops out at).
    """
    total_px = sum(getattr(m, "distance", 0.0) for m in game.marbles)
    total_grid_units = GRID_WIDTH * GRID_HEIGHT
    return (total_px / GRID_SIZE) / total_grid_units


def fullest_column_count(game):
    """The number of blocks in the marble box's fullest column.

    Columns are the grid's x positions; the fullest column is the one with the
    most blocks in it. The Pillar card grants +1 mult per block there.
    """
    counts = {}
    for (gx, _) in game.grid:
        counts[gx] = counts.get(gx, 0) + 1
    return max(counts.values()) if counts else 0


def owned_slippery_block_count(game):
    """The number of blocks the player owns that have the slippery effect.

    Counts blocks in the toolbox and blocks placed in the marble box (each
    block once, even if it also has other effects). The Skater card grants
    xMult based on this count.
    """
    count = 0
    for item in game.toolbox.items:
        if getattr(item, "kind", None) == "block" and item.has_effect(Effect.SLIPPERY):
            count += 1
    for block in game.grid.values():
        if block.has_effect(Effect.SLIPPERY):
            count += 1
    return count


def on_fragile_broken(game, block):
    """A fragile block broke: Wrecking Ball cards fire.

    The Wrecking Ball card permanently grows its saved bonus by +3 mult a break
    (its table row: ratio 0.75 of the +4 mult base — see components.Card.NAMED).
    The gain applies live to the running score and is banked into the per-run
    gain, which only becomes permanent when the run is continued — retrying
    discards it (main._commit_wrecking_run_gain / _reset_wrecking_run_gain). A
    Blueprint copy plays the card it sits next to, so it banks a second +3.
    """
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        if effective_card_value(game, i) == Card.WRECKING_BALL:
            _accumulate_wrecking_break(game, card, block)


def _accumulate_wrecking_break(game, card, block):
    """A Wrecking Ball card earned one break: +3 mult, live and banked.

    The gain is the card's own payoff (magnitude_payoff of its table row at one
    unit), so the number that pops, the score it adds and the amount it banks
    can never drift apart. It applies to the running score only while the run is
    active — a break outside a run (a board edit) still banks for the next one.
    """
    _phase, scorer, ratio, _measure = Card.NAMED[Card.WRECKING_BALL]
    chips, mult, factor = magnitude_payoff(scorer, ratio, 1.0)
    if scorer == Scorer.CHIPS_ADD:
        text, color = str(chips), GREEN
    elif scorer == Scorer.MULT_ADD:
        text, color = game._particle_amount_text(mult), BLUE
    else:  # Scorer.MULT_MUL
        text, color = game._particle_amount_text(factor), RED
    if game.run_active:
        if scorer == Scorer.CHIPS_ADD:
            game.score_chips += chips
        elif scorer == Scorer.MULT_ADD:
            game.score_mult += mult
        else:
            game.score_mult *= factor
    run_gain = game.wrecking_run_gain
    if scorer == Scorer.CHIPS_ADD:
        run_gain[Scorer.CHIPS_ADD] += chips
    elif scorer == Scorer.MULT_ADD:
        run_gain[Scorer.MULT_ADD] += mult
    else:
        run_gain[Scorer.MULT_MUL] *= factor
    game._spawn_card_particle(card, text, color, block=block)
