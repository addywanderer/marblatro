"""Paying a run's score: xMult, the random outputs an item rolled, the
Procrastination rewind, the Deal breaker and Watch blocks, and block scoring."""

import math
import random
from collections import deque

import numpy as np
import pygame

import achievements
import cards
import collection
import components
import crt
import metagame
import profiles
import rolling
from rolling import *
import save_system
import sounds
import ui
from ui import Popup, ScoreParticle, TrailParticle
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
from blocks import Block
from items import (
    CASH_BREAKDOWN,
    ActionItem,
    BlockItem,
    CardItem,
    ItemPack,
    ResourceOption,
    ScorerToken,
    CashBreakdown,
    _s,
    make_card_item,
    offer_key,
    resource_point_label,
)
from marble import Marble, _configure_marble_type
from physics import PhysicsEngine
from shop import Shop
from toolbox import Toolbox


class PayoffsMixin:
    """Paying a run's score: xMult, the random outputs an item rolled,
    Procrastination, Deal breaker, Watch and the block payoffs."""


    def _apply_xmult(self, factor):
        """Bank a run-END xMult reward: the multiplier is multiplied by it later.

        Only the payoffs that belong to the run's END bank here — the xMult
        CARDS (Explorer, Skater, Fountain, Island, Stencil and the other
        measured cards, a Colossus or match-group xMult card, the Grace card's
        bonus, the Wrecking Ball's permanent bonus) and an xMult Spirit token.
        They record their factor here instead of touching the multiplier where
        they fired, and the whole product lands when the run ends (see
        _flush_run_xmult).

        A SCORER never banks: a block's own xMult payoff lands with the
        collision that fired it, because a scorer pays out when the marble
        touches it (see _apply_xmult_now).

        Every banking call multiplies into the same pending product, so
        repeated triggers still compound exponentially (two different cards'
        factors stack), and the particle still pops where it fired so the
        player sees it register. Returns the factor, which is the figure that
        particle shows.
        """
        self.run_xmult_pending *= factor
        return factor

    def _flush_run_xmult(self):
        """Apply the run's banked xMult product, once, as the run settles.

        Called by the run's finish path after the end-of-run cards have paid, so
        every xMult the run BANKED (the xMult and token cards alike, see
        _apply_xmult) lands in the same place: the multiplier is multiplied
        ONCE by the pending product before the total score is computed. Nothing
        banked (the common case, a product of exactly 1.0) pops nothing.
        """
        factor = self.run_xmult_pending
        self.run_xmult_pending = 1.0
        if factor == 1.0:
            return
        self._apply_xmult_now(factor)
        fx, fy = cards.run_finish_pos(self)
        self._spawn_score_particle(fx, fy, self._particle_amount_text(factor), RED)

    def _apply_xmult_now(self, factor):
        """Multiply the multiplier by ``factor`` this instant.

        This is how a SCORER pays: its multiplier lands where it fires — the
        collision that set it off (see _apply_block_score_effect), the Echo
        block re-firing it, or the token firing it — so the multiplier readout
        moves while the run plays, exactly as the scorer's own description
        ("Multiplies the multiplier by 3 when touched") says.

        The run-END settlements also come through here: the banked product the
        cards left (_flush_run_xmult) and the permanent bonuses the Wrecking
        Ball and Tesseract cards carry into a run.
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

        The result is chosen when the run is set up (see
        _roll_run_random_outputs) and kept on the item, tagged with the run it
        belongs to, so a scorer that triggers several times repeats the same
        result and REPLAYING the run — rushing R, pressing T, or retrying a
        finished run — replays it exactly instead of rerolling it. An item that
        entered play after the opening roll (a block placed or a card bought
        mid-run) rolls on its first trigger instead. The roll travels with the
        block the player BUILT (see _place_block_at / _refund_block), so moving
        a Random block on the board — or erasing it and putting it down again —
        keeps the reward it already had rather than drawing a new one.
        """
        rolls = getattr(item, "random_rolls", None)
        if (rolls is None or rolls.get("scorer") != scorer
                or rolls.get("run") not in (self.run_number, KEPT_ROLL_RUN)):
            rolls = self._set_run_random_result(item, scorer)
        return rolls

    def _roll_kept_reward(self, block):
        """Decide a sacrificed Random/Lucky block's reward, once and for good.

        A Spirit token keeps a whole block, and a Random/Lucky block's reward is
        part of what the player built: the token pays the SAME outcome for every
        run it covers, so retrying the run it was won in — or loading a save —
        can never reroll what the token gives. The roll is tagged KEPT_ROLL_RUN
        rather than a run number, which is what makes it never stale (see
        _run_random_result).
        """
        if block.scorer in (Scorer.LUCKY, Scorer.RANDOM):
            self._set_run_random_result(block, block.scorer, run=KEPT_ROLL_RUN)
        return block

    def _set_run_random_result(self, item, scorer, run=None):
        """Draw a fresh result for an item, replacing any earlier roll.

        ``run`` tags the roll with the run it belongs to (the default: this
        run), or with KEPT_ROLL_RUN for a Spirit token's block, whose reward is
        decided when the block is sacrificed and then stands for every run (see
        _roll_kept_reward).
        """
        rolls = self._roll_random_output(scorer)
        rolls["scorer"] = scorer
        # The run the roll was made for: a roll from an earlier run is stale and
        # is redrawn, but a roll made for THIS run survives every replay of it —
        # and a KEPT roll is never stale at all.
        rolls["run"] = self.run_number if run is None else run
        item.random_rolls = rolls
        return rolls

    def _roll_run_random_outputs(self):
        """Choose every random-output scorer's result before the run starts.

        Lucky and Random blocks on the board, and Lucky/Random cards in the card
        area, all get their result for the coming run up front, so nothing about
        their outcome depends on when they happen to trigger. An item that
        ALREADY carries this run's result keeps it: these rolls are decided once
        per run (run_seed / _run_random_result), and replaying the run — R, T,
        or the retry after a finished run — is not a chance to roll them again.
        """
        for block in self.board_blocks():
            if (block.scorer in (Scorer.LUCKY, Scorer.RANDOM)
                    and getattr(block, "random_rolls", {}).get("run") != self.run_number):
                self._set_run_random_result(block, block.scorer)
        for card in self.cards:
            card_scorer_value = card_scorer(card.value)
            if (card_scorer_value in (Scorer.RANDOM, Scorer.LUCKY)
                    and getattr(card, "random_rolls", {}).get("run") != self.run_number):
                self._set_run_random_result(card, card_scorer_value)

    def _procrastination_rewind(self):
        """Procrastination: hand the run back its last second (once per copy).

        Called when every marble has just finished. Instead of ending, the run
        rewinds: each marble returns to the motion state it had one second ago
        (the oldest snapshot in its history) and flies again, and every block
        gets its full trigger count back, so the second that just ended is
        played again with the blocks able to score. The score, the measurements
        (distance travelled, air time) and the run clock keep their values: the
        run is simply one second longer.

        EVERY copy of the card rewinds once, because a card activates once per
        copy the player owns: a second Procrastination, or a Blueprint that
        copies the first (see _card_activations), hands the run a second extra
        second — the run finishes again, and rewinds again, until the copies run
        out. Without that cap a rewound run could never end — the marbles would
        reach the finish again about a second later and rewind forever — so a
        copy the Card cutter has cut takes its rewind with it. A marble that
        finished more than a second before the run did was already resting on
        its finish back then, so it starts the replay there and finishes again
        immediately; the marble that ended the run replays its whole approach.

        Portal travel budgets (Effect.PORTAL's per-run activations) are not
        trigger counts and are left as they are; destroyed blocks stay
        destroyed — only trigger counts and the marbles' motion come back.

        The particle pops on the copy that PAYS, so a second copy is visibly the
        one paying for the second rewind. Returns True when the run was rewound
        (and is therefore still going).
        """
        payers = self._card_activations(Card.PROCRASTINATION)
        if self.procrastination_rewinds >= len(payers):
            return False
        self.procrastination_rewinds += 1
        # Every block can score its trigger limit again — the Concert card's
        # bonus and the Hands tied trial's cap included, exactly as a fresh run
        # would set it (see _trigger_limit).
        for block in self.board_blocks():
            block.triggers_left = self._trigger_limit(block)
        for marble in self.marbles:
            if marble.history:
                marble.restore_motion_state(marble.history[0])
            # The second just rewound never happened, so its snapshots go too
            # (they are the future now) — and the marbles are flying again, so
            # the run is not over.
            marble.history.clear()
            marble.finished = False
        # With more than one copy to spend, the message says how many rewinds
        # are left, so a second copy reads as a second chance rather than a
        # repeat of the first.
        spent = ""
        if len(payers) > 1:
            spent = f" ({self.procrastination_rewinds} of {len(payers)})"
        self._set_shop_message(
            f"Procrastination{spent}: rewound 1 second — every block's triggers"
            " are back")
        self._spawn_card_particle(self.cards[payers[self.procrastination_rewinds - 1]],
                                  "-1s", BLUE)
        return True

    def _deal_breaker_gags(self):
        """True while the Deal breaker trial is stopping every block scoring.

        The trial's rule is "blocks never score until you sell a card": with it
        active and no sale yet, EVERY block scorer pays nothing. The trigger is
        still spent, so the block shows its used-up red state and a run cannot
        bank triggers.

        Selling any card frees the board — the sale is registered in
        _card_sold_message, the one place a card leaves by sale — and the
        freedom is PERMANENT: it is recorded on the game and saved with it,
        so a later Deal breaker run (or a reload) starts already free rather
        than gagged again.
        """
        return (self.active_trial == Trial.DEAL_BREAKER
                and not self.card_sold)

    def _watch_blocks_out_of_play(self, block):
        """True when the Watch card stops this block from contributing score.

        Watch lets only the first WATCH_BLOCK_LIMIT distinct blocks the marble
        touches contribute score; every later block's scorer pays nothing (its
        trigger is still spent, like any block whose reward comes out zero).
        Watch gates BLOCK scorers only — collision cards still fire on the
        touch, so a Watch run stays a card-driven build.
        """
        if not self._has_card(Card.WATCH):
            return False
        # A Spirit token is a start-of-run card-like payoff, not a block the
        # marble touched, so Watch never gates it.
        if getattr(block, "is_token", False):
            return False
        return block not in self.run_first_blocks

    # ---- The units a state-dependent scorer pays for ------------------------
    # A scorer that pays per SOMETHING (a board unit, a Seed block, a
    # neighbouring block) reads its count from these, so the count the payoff
    # uses and the count the sidebar reports for it can never drift apart (see
    # _live_payoff_row). Each one takes the block the way the payoff branch
    # does; the position-free ones ignore it.

    def _roomy_units(self):
        """The unlocked board units a Roomy trigger pays for."""
        return len(self.unlocked_cells)

    def _seed_units(self):
        """The Seed blocks on the board a Seed trigger pays for (itself too)."""
        return sum(1 for b in self.board_blocks() if b.scorer == Scorer.SEED)

    def _summit_units(self, block):
        """The rows above the bottom row a Summit block pays for."""
        return max(0, (GRID_HEIGHT - 1) - block.y)

    def _powerline_units(self, block):
        """The blocks in its row (itself included) a Powerline trigger pays for."""
        return sum(1 for b in self.board_blocks() if b.y == block.y)

    def _frontier_units(self, block):
        """The locked neighbours a Frontier trigger pays for.

        An unlocked (already settled) neighbour pays nothing. The board is
        infinite, so there is no "edge of the board" to pay for any more: every
        neighbour that is not unlocked is a locked square (the squares outside
        the window are locked too, which is why a block on the window's edge
        still pays one for the space beyond it).
        """
        units = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (block.x + dx, block.y + dy) not in self.unlocked_cells:
                units += 1
        return units

    def _cluster_units(self, block):
        """The orthogonally adjacent blocks (up/down/left/right) a Cluster
        trigger pays for — diagonals and its own cell do not count.

        Only BLOCKS are neighbours: a component lying on a square is part of the
        workbench, not part of the cluster (see Game.ensure_board_cells)."""
        neighbours = {(near.x, near.y) for near in self.board_blocks()}
        return sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if (block.x + dx, block.y + dy) in neighbours)

    def _apply_block_score_effect(self, marble, block):
        """Apply a block's scoring effect once; returns True if it scored.

        A no-scoring block still counts as "scored" (so it shows its used red
        state) but grants nothing; portals are exempt from the trigger
        behavior. The 8 ball calls this a second time to retrigger a block's
        scoring effect on collision.
        """
        if block.scorer == Scorer.NONE and not block.has_effect(Effect.PORTAL):
            return True
        # Deal breaker: while the board is gagged nothing scores (see
        # _deal_breaker_gags). The trigger is still spent, so the block still
        # shows its used-up red state.
        if self._deal_breaker_gags():
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
            rows_above = self._summit_units(block)
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
            # xMult: a scorer pays its multiplier the instant it fires, so this
            # touch multiplies the multiplier on the spot — and every further
            # trigger multiplies it again (see _apply_xmult_now).
            amount = self._apply_xmult_now(block.scorer_amount)
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
            # Cash blocks pay out money instead of score. The rolled magnitude
            # is fractional (a Cash block averages $120 and can now come out at
            # $132.4), so it is paid as the whole dollar its description states
            # rather than truncated to $132.
            gained = round(block.scorer_amount)
            self.cash += gained
            self.run_cash_gained += gained
            self._spawn_block_particle(block, f"${gained}", YELLOW)
            return True
        if block.scorer == Scorer.SHARP:
            # Sharp blocks multiply the multiplier by their own factor (and may
            # be destroyed later). The payoff lands with the touch, and repeated
            # triggers multiply again, so they compound (see _apply_xmult_now).
            amount = self._apply_xmult_now(block.scorer_amount)
            self._spawn_block_particle(
                block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer == Scorer.SATANIC:
            # Satanic blocks multiply the multiplier by 6.66 the moment they
            # are touched, and are permanently destroyed once a marble touches
            # them and leaves.
            amount = self._apply_xmult_now(block.scorer_amount)
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
            # Parts banks one component per trigger. The component itself is
            # NOT handed over now: the run's bank is granted only when the
            # player continues the run (see _continue_run), so a retried or
            # restarted run cannot walk off with free parts.
            self.parts_run_gain += 1
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
            # Random blocks grant one of three fixed rewards (their magnitudes
            # are in components.MAGNITUDES). The reward is chosen BEFORE the run
            # (see _roll_run_random_outputs), so every trigger of this block
            # gives the same one and retrying the run replays it. The Rigged
            # Casino card rigs the odds of that pre-roll (chips:mult:xMult =
            # 1:3:9, instead of the even thirds).
            reward = self._run_random_result(block, Scorer.RANDOM)["reward"]
            if reward == 0:
                self.score_chips += MAGNITUDES.RANDOM_CHIPS
                self._spawn_block_particle(
                    block, self._particle_amount_text(MAGNITUDES.RANDOM_CHIPS), GREEN)
            elif reward == 1:
                self.score_mult += MAGNITUDES.RANDOM_MULT
                self._spawn_block_particle(
                    block, self._particle_amount_text(MAGNITUDES.RANDOM_MULT), BLUE)
            else:
                factor = 1 + MAGNITUDES.RANDOM_XMULT
                amount = self._apply_xmult_now(factor)
                self._spawn_block_particle(
                    block, self._particle_amount_text(amount), RED)
            return True
        if block.scorer == Scorer.SEED:
            # Seed: +scorer_amount mult for each Seed block on the board (the
            # touched block counts itself). The Garden card doubles the
            # per-seed mult (+3 -> +6).
            seed_count = self._seed_units()
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
        if block.scorer == Scorer.PACKED:
            # Packed: the inventory gains slots for good, so more items fit (the
            # magnitude rolls in tenths, so the slot count is rounded, never 0).
            # The slots land at once — this is a build-time gain, not a score —
            # and the count granted by THIS run is remembered so a retry can
            # take back what the discarded run won (see inventory_slots_run_gain).
            self._grant_inventory_slots(max(1, round(block.scorer_amount)))
            self._spawn_block_particle(
                block, f"+{max(1, round(block.scorer_amount))}", ORANGE)
            return True
        if block.scorer == Scorer.LUCKY:
            # Lucky makes two INDEPENDENT rolls: a 1/3 chance to add +130 chips
            # and a separate 1/9 chance to add $40 — it can win both, either,
            # or neither. Both rolls are chosen BEFORE the run (see
            # _roll_run_random_outputs), so a retry replays the same outcome.
            result = self._run_random_result(block, Scorer.LUCKY)
            if result["chips"]:
                self.score_chips += MAGNITUDES.LUCKY_CHIPS
                self._spawn_block_particle(
                    block,
                    self._particle_amount_text(MAGNITUDES.LUCKY_CHIPS), GREEN)
            if result["cash"]:
                self.cash += MAGNITUDES.LUCKY_CASH
                self.run_cash_gained += MAGNITUDES.LUCKY_CASH
                self._spawn_block_particle(block, f"${MAGNITUDES.LUCKY_CASH}", YELLOW)
            return True
        if block.scorer == Scorer.ROOMY:
            # Roomy: +scorer_amount chips for each currently-unlocked board
            # unit (the bigger the unlocked region, the more the marble earns).
            gained = block.scorer_amount * self._roomy_units()
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
            row_count = self._powerline_units(block)
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
            units = self._frontier_units(block)
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
            adjacent = self._cluster_units(block)
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
                amount = self._apply_xmult_now(1 + gained)
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
            gained = self.score_chips / MAGNITUDES.GILDED_DIVISOR
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
                amount = self._apply_xmult_now(factor)
                self._spawn_block_particle(
                    block, self._particle_amount_text(amount), RED)
            return True
        return False
