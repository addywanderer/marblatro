"""Card score-effect logic for Marblatro.

The owned-card score effects live here: the start-of-run (+mult / +chips)
cards, the end-of-run (xMult / data-dependent) cards, Blueprint copying, and
the small block/board helpers they use. Each function takes the ``Game`` as
its first argument (mirroring the physics.py pattern); main.py's Game keeps
thin wrappers (_apply_cards / _apply_cards_on_finish / _on_fragile_broken)
that delegate to this module, so the rest of the code and the tests call them
as before.
"""

import random
import sys

from components import (
    condition_card_meta,
    condition_matches_block,
    condition_phase,
    condition_ratio,
    generic_card_meta,
    magnitude_payoff,
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
Condition = _card_source.Condition
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
    """Apply every owned card's score effect at the start of a run.

    A Fragile Breaks (Wrecking Ball) card first applies its permanent, saved
    bonus (chips/mult/xMult that have accumulated across the game from fragile
    breaks). A Blueprint copies the card to its immediate left; a card disabled
    by the Card cutter or Deal breaker trial is skipped (and can't be copied).
    """
    if _owns_fragile_breaks_card(game):
        _apply_wrecking_bonus(game)
    # Tesseract's bonus is an aggregate too (one factor per reroll, whole card
    # or not), so it is applied once here rather than per card in the loop.
    _apply_tesseract_bonus(game)
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        if value is not None:
            apply_card_start(game, card, value, effective_card_amount(game, i))


def _owns_fragile_breaks_card(game):
    """True when the player owns a Fragile Breaks magnitude card (any scorer)."""
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        meta = condition_card_meta(value)
        if meta is not None and meta[2] == Condition.FRAGILE_BREAKS:
            return True
    return False


def _apply_wrecking_bonus(game):
    """Apply the permanent Fragile Breaks (Wrecking Ball) bonus at run start.

    The bonus has grown by 3/4 of each scorer's base per fragile break across
    the whole game (saved with the game): chips are added, mult is added, and
    xMult multiplies by the accumulated factor.
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


def _condition_units(game, condition):
    """A named condition's magnitude in card-scorer units this run.

    One unit equals one standard payoff (+30 chips / +4 mult / +0.25 xMult),
    scaled by the condition's ratio (see components.condition_ratio). Start = 1;
    Fullest Column = its block count; Distance = 4x the board-travel fraction
    (so a full board is 4 units, matching Explorer's max x2); Black Hole and
    Air Time = seconds spent pulled / airborne; Cash Held = dollars held / 10;
    Slippery = owned slippery blocks; Random = a random 0..6 (0 to 6x base); Few Blocks = 1
    when the board has 5 blocks or fewer, else 0 (it never fires otherwise);
    Painting = the board's total sell price in whole dollars (see
    board_sell_total); Synthesizer = the cards in the card area. A return of 0
    means the condition did not happen, which is the gate a FLAT card checks
    (see _condition_fired) and what a magnitude card scales its payoff to.
    """
    if condition == Condition.START:
        return 1
    if condition == Condition.FULLEST_COLUMN:
        return fullest_column_count(game)
    if condition == Condition.DISTANCE:
        return 4 * card_distance_fraction(game)
    if condition == Condition.BLACK_HOLE:
        return getattr(game, "black_hole_time", 0.0)
    if condition == Condition.AIR_TIME:
        return getattr(game, "air_time", 0.0)
    if condition == Condition.CASH_HELD:
        # One unit per $10 held (a card pays per whole $10, mirroring the old
        # Banker card's "1 chip for every 10 dollars").
        return max(0, game.cash) // 10
    if condition == Condition.SLIPPERY:
        return owned_slippery_block_count(game)
    if condition == Condition.RANDOM:
        # Glitch pays a random 0..6 units (between 0 and 6x the base payoff).
        return random.uniform(0, 6.0)
    if condition == Condition.FEW_BLOCKS:
        return 1.0 if len(game.grid) <= 5 else 0.0
    if condition == Condition.COZY:
        # One unit (at Cozy's 3x base ratio) when the board has 10 or fewer
        # unlocked squares; 0 units once the board has been expanded past 10.
        return 1.0 if len(getattr(game, "unlocked_cells", set())) <= 10 else 0.0
    if condition == Condition.PAINTING:
        # One unit per whole dollar of the board's total sell price; Painting's
        # 1/10 ratio then pays 1/10 of the base per dollar.
        return board_sell_total(game)
    if condition == Condition.SYNTHESIZER:
        # One unit per card in the card area; Synthesizer's 3/4 ratio then pays
        # +3 mult per card (+22 chips, or x1.1875 per card for the other unit
        # scorers), so the Synthesizer card is "+3 mult per card owned".
        return len(game.cards)
    return 0


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


def _apply_condition_card(game, card, value, scorer, condition, fx, fy, units=None,
                          amount=None):
    """Apply a built condition card: the scorer's payoff x the condition's units.

    Called once at the card's trigger (run start or end, or once per matching
    collision hit). Every scorer stays proportional to the standard base: chips
    add round(ratio*30) per unit, +Mult adds ratio*4 per unit, and xMult
    multiplies the multiplier by (1 + ratio*0.25 per unit) — the xMult per unit
    is an ADD, never a stack of x1.25s. ``amount`` is the card's own scorer
    magnitude, which scales the whole payoff (a 45-chip +Chips half pays 45 a
    unit instead of 30). ``units`` defaults to the condition's measured
    magnitude (_condition_units); a collision card passes units=1 (one standard
    payoff per matching hit). Start-phase/collision popups appear on the card in
    the card area; end-phase popups appear where the run ended.
    """
    if units is None:
        units = _condition_units(game, condition)
    ratio = condition_ratio(condition)
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
    bank resource points (converted after a run), Parts grants components,
    Fresh grants free rerolls, and Quick arms a payout that resolves at the
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
        # marble hits after this condition was satisfied (see cards.py on how
        # the armed card resolves in _handle_block_contacts).
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
        # Parts cards grant random components immediately (no point system),
        # one per point of the card's own magnitude.
        for _ in range(max(1, int(amount))):
            game._grant_random_component()
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


def _condition_fired(game, condition, units=None):
    """True when a named condition actually happened at this trigger.

    A magnitude (unit-scorer) card scales to zero when its condition measured
    nothing, so it already pays nothing for an unmet gate. A FLAT card fires
    one block-style trigger regardless of how much the condition measured, so
    it has to be told: a Ripped Card (Parts) pays nothing on a board with more
    than 5 blocks, a Cozy card nothing once the board has grown past 10 units,
    a Banker card nothing with less than $10 held, and an end-phase card
    nothing on a run that never travelled / flew / got caught by a black hole.

    Collision and Fragile Breaks triggers are their own gate — the marble hit
    the block, or the block broke — so they always pass.
    """
    if condition_phase(condition) not in ("start", "end"):
        return True
    if units is None:
        units = _condition_units(game, condition)
    return units > 0


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


def fire_first_block_cards(game, block, marble=None):
    """Fire start-condition cards whose payoff reads a block.

    A start-phase block-relative card cannot decide at run start (no block has
    been hit yet), so main.py calls this once the run's first block is
    contacted. Each such card resolves with that block as its reference block:
    Effective grants its xMult when that first block has 2+ effects, Summit
    grants its mult per row it sits above the bottom row, Airball its mult per
    second of ``marble``'s airborne streak before the touch, Powerline its
    chips per block in that block's row, and so on (see _fire_block_payoff).
    """
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        gmeta = generic_card_meta(value)
        if gmeta is not None:
            condition, scorer = gmeta
            if condition_phase(condition) != "start":
                continue
            amount = effective_card_amount(game, i)
            if scorer not in _BLOCK_PAYOFF_SCORERS:
                continue  # it waits for a block (see _fire_card_scorer)
            if not _condition_fired(game, condition):
                continue  # the start condition did not happen this run
            _fire_card_scorer(game, card, scorer, amount, block=block, marble=marble)


def apply_card_start(game, card, value, amount=None):
    """Apply one card value's start-of-run score effect (from ``card``).

    Magnitude cards whose condition fires at the start of the run apply their
    scaled payoff; generic flat-scorer start cards fire their scorer once, and
    only while their condition's gate is met (see _condition_fired — a Ripped
    Card pays nothing on a board with more than 5 blocks). Effective/Summit
    start cards wait for the run's first block (see fire_first_block_cards).
    The whole cards (ERR 404 / Blueprint / Showman)
    do nothing here — Blueprints are resolved by ``effective_card_value`` and
    Showman only enables buying duplicates. ``card`` is the card that triggers
    the effect (possibly a Blueprint copying a neighbor), so its popup appears
    on that card in the card area. ``value`` is the effective card value, and
    ``amount`` the effective scorer magnitude it pays with.
    """
    meta = condition_card_meta(value)
    if meta is not None:
        trigger, scorer, condition = meta
        if trigger == "start":
            _apply_condition_card(game, card, value, scorer, condition, None, None,
                                  amount=amount)
        return
    gmeta = generic_card_meta(value)
    if gmeta is not None:
        condition, scorer = gmeta
        # A flat card pays one block-style trigger, so it only fires when the
        # condition actually measured something (see _condition_fired).
        if (condition_phase(condition) == "start"
                and scorer not in _BLOCK_PAYOFF_SCORERS
                and _condition_fired(game, condition)):
            _fire_flat_scorer(game, card, scorer, amount=amount)


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

    Collision-condition cards matching the block's shape or any of its effects
    fire: a magnitude (unit scorer) card adds +30 chips / +4 mult / x1.25 mult,
    and a generic card fires its scorer (Cash, Sharp, Quick, a resource point,
    or any board/run/block-relative scorer — the collided block is the card's
    reference block). A card only fires while the collided block can still spend
    a trigger (see _block_feeds_collision_cards), so a block feeds cards once
    per trigger it has. A Blueprint copies the card to its immediate left; a
    card disabled by the Card cutter trial is skipped. Called once per fresh
    collision (the marble newly entering contact with the block). ``marble``
    is the touching marble (an Airball card rewards its airborne streak).
    """
    if not _block_feeds_collision_cards(block):
        return
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        if value is None:
            continue
        amount = effective_card_amount(game, i)
        meta = condition_card_meta(value)
        if meta is not None:
            trigger, scorer, condition = meta
            if trigger == "collision" and condition_matches_block(condition, block):
                _apply_condition_card(game, card, value, scorer, condition, None, None,
                                      units=1.0, amount=amount)
            continue
        gmeta = generic_card_meta(value)
        if gmeta is not None:
            condition, scorer = gmeta
            if (condition_phase(condition) == "collision"
                    and condition_matches_block(condition, block)):
                _fire_card_scorer(game, card, scorer, amount, block=block,
                                  marble=marble)


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
    """Apply owned cards that trigger when a run ends (e.g. Explorer).

    A Blueprint copies the card to its immediate left; a card disabled by the
    Card cutter trial is skipped (and can't be copied either).
    """
    fx, fy = run_finish_pos(game)
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        if value is not None:
            apply_card_finish(game, card, value, fx, fy, effective_card_amount(game, i))


def apply_card_finish(game, card, value, fx, fy, amount=None):
    """Apply one card value's end-of-run score effect (from ``card``).

    Holds the multiplicative (xMult) cards plus the additive cards whose
    values are only known once the run is over (Astronaut's black-hole time,
    Plane's air time). A flat end card whose condition measured nothing this
    run does not fire at all (see _condition_fired). End-of-run popups appear
    where the run ended (on the
    finished marble), so they are visible instead of lost at the top-of-screen
    card area.
    """
    meta = condition_card_meta(value)
    if meta is not None:
        trigger, scorer, condition = meta
        if trigger == "end":
            _apply_condition_card(game, card, value, scorer, condition, fx, fy,
                                  amount=amount)
        return
    gmeta = generic_card_meta(value)
    if gmeta is not None:
        condition, scorer = gmeta
        if condition_phase(condition) == "end":
            # The run has to have measured something for the end condition to
            # have happened at all (see _condition_fired).
            if not _condition_fired(game, condition):
                return
            if scorer == Scorer.QUICK:
                # There is no NEXT block after the run, so an end-condition
                # Quick card pays from the speed of the run's LAST block
                # contact instead of arming for a next one.
                _fire_quick_card(game, card,
                                 getattr(game, "_last_contact_speed", 0.0), fx, fy)
            else:
                # An End-condition block-relative card checks the last block the
                # marble hit before finishing (Airball also rewards the
                # airborne streak that marble had before that touch).
                _fire_card_scorer(game, card, scorer, amount,
                                  block=getattr(game, "_last_contact_block", None),
                                  air=getattr(game, "_last_contact_air", 0.0),
                                  fx=fx, fy=fy)
        return
    # The whole cards (ERR 404 / Blueprint / Showman) do nothing at run end.


def card_distance_fraction(game):
    """The fraction of the marble box's total grid units the marble(s) travelled.

    A Distance-condition magnitude card's units are 4x this fraction (so a full
    board is 4 units of payoff).
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


def fullest_column_block(game):
    """A block in the marble box's fullest column (Pillar's trigger block).

    Returns the first block found in the column with the most blocks, or None
    when the board is empty. A block-based card's particle should appear near
    this block instead of in the card area.
    """
    counts = {}
    first_in_column = {}
    for (gx, _), block in game.grid.items():
        if gx not in counts:
            first_in_column[gx] = block
        counts[gx] = counts.get(gx, 0) + 1
    if not counts:
        return None
    fullest = max(counts, key=counts.get)
    return first_in_column[fullest]


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
    """A fragile block broke: Fragile Breaks (Wrecking Ball) cards fire.

    A Fragile Breaks magnitude card permanently grows its saved bonus by 3/4 of
    its scorer's base per break (+3 mult / +23 chips / x1.19). The gain applies
    live to the running score and is banked into the per-run gain, which only
    becomes permanent after a run — retrying discards it. Generic Fragile
    Breaks flat cards (Cash, Sharp, Quick, resource) fire their scorer once
    per break too.
    """
    for i, card in enumerate(game.cards):
        if _card_disabled(game, card):
            continue
        value = effective_card_value(game, i)
        amount = effective_card_amount(game, i)
        meta = condition_card_meta(value)
        if meta is not None:
            _trigger, scorer, condition = meta
            if condition == Condition.FRAGILE_BREAKS:
                _accumulate_wrecking_break(game, card, scorer, block, amount=amount)
            continue
        gmeta = generic_card_meta(value)
        if gmeta is not None:
            condition, scorer = gmeta
            if condition == Condition.FRAGILE_BREAKS:
                _fire_card_scorer(game, card, scorer, amount, block=block,
                                  air=getattr(block, "touch_air_streak", 0.0))


def _accumulate_wrecking_break(game, card, scorer, block, amount=None):
    """A Fragile Breaks (Wrecking Ball) magnitude card earned one break.

    Each break adds 3/4 of the scorer's OWN magnitude to the card's permanent
    reward: +3 mult (0.75 x 4), +23 chips (0.75 x 30, rounded up), and x1.19
    mult (multiplies by 1 + 0.75 x 0.25) at the averages — so a Wrecking Ball
    whose +Mult half rolled to 6 banks +4.5 a break instead of +3. The gain
    applies live to the running score and is banked into the per-run gain,
    which is folded into the permanent saved bonus only after a run.
    """
    ratio = 0.75
    scale = scorer_magnitude_scale(scorer, amount)
    chips, mult, factor = magnitude_payoff(scorer, ratio, 1.0, scale)
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
