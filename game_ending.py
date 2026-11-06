"""Finishing a run: the cash award, continuing or retrying, the end of the
profile, and the main loop."""

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


class EndingMixin:
    """Finishing a run: the cash award, continuing or retrying, the end
    of the profile, and the main loop."""


    def _award_cash(self):
        """Award cash at the end of a run based on how much the player beat the required score."""
        # Guard against log(0) / log(1): a score of 0 or a required score of 1
        # must not produce -inf or a divide-by-zero.
        score = max(self.score_total, 1)
        required = max(self.required_score, 2)
        # The Empty pockets trial skips ONLY the score-based part of the award
        # (the log-ratio gain): the flat $20, the interest on cash held, and
        # any Cash-card payouts still land.
        if self.trials_enabled and self.current_trial == Trial.EMPTY_POCKETS:
            score_gain = 0
        else:
            score_gain = max(0, int(CASH_SCALE * (np.log(score) - np.log(required))))
        # Every part of the award is kept separately so the cash readout can
        # show where the run's money came from (see _cash_breakdown_rows).
        base_cash = 20
        # A Debt block that triggered this run cancels the interest entirely:
        # the run pays nothing for the cash the player holds. The Compound
        # Interest whole card doubles what is left.
        interest = 0 if self.debt_run_triggered else self.cash // 10
        if self._has_card(Card.COMPOUND_INTEREST):
            interest *= 2
        # Cash earned by Cash-scorer cards this run is paid out here, folded
        # into the run's end-of-run award. Retrying the run undoes the whole
        # award, so that cash only sticks after a run.
        card_cash = self.card_cash_run_gain
        self.card_cash_run_gain = 0
        # Cash the Cash and Lucky scorer BLOCKS paid out directly during the
        # run was already added to the player's cash as it triggered; it is
        # part of the run's earnings but not of this award.
        scorer_cash = self.run_cash_gained
        self.run_cash_gained = 0
        # The Essence whole card pays a flat sum at the end of every run (it is
        # part of the award, so a retry takes it back with the rest).
        essence_cash = ESSENCE_RUN_CASH if self._has_card(Card.ESSENCE) else 0
        award = score_gain + base_cash + interest + card_cash + essence_cash
        self.cash += award
        # The run's "cash gained" covers every dollar the run earned: the whole
        # award PLUS the scorer cash already paid out mid-run, so the display
        # (and the retry rollback in _retry_run) covers every dollar earned.
        self.last_run_cash_gained = award + scorer_cash
        self.last_run_cash_breakdown = {
            "base": base_cash,
            "interest": interest,
            "score": score_gain,
            "cards": card_cash,
            "scorers": scorer_cash,
            "essence": essence_cash,
            # True when a Debt block cancelled this run's interest, so the
            # breakdown can say why it is $0.
            "debt": bool(self.debt_run_triggered),
        }

    def _reset_wrecking_run_gain(self):
        """Start a fresh run with no Fragile Breaks (Wrecking Ball) gains."""
        self.wrecking_run_gain = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                                  Scorer.MULT_MUL: 1.0}

    def _commit_wrecking_run_gain(self):
        """Fold a finished run's Fragile Breaks gains into the permanent bonus.

        Called after a run: the per-run gains (chips
        and mult added, xMult multiplied) become part of the saved permanent
        wrecking_bonus, which applies at the start of every future run.
        """
        run_gain = self.wrecking_run_gain
        bonus = self.wrecking_bonus
        bonus[Scorer.CHIPS_ADD] += run_gain[Scorer.CHIPS_ADD]
        bonus[Scorer.MULT_ADD] += run_gain[Scorer.MULT_ADD]
        bonus[Scorer.MULT_MUL] *= run_gain[Scorer.MULT_MUL]
        self._reset_wrecking_run_gain()

    def _continue_run(self):
        """Move on to the next run after the player clicks CONTINUE.

        Only advances when a finished run is awaiting the CONTINUE choice, so
        pressing Y mid-run (or during the build phase) can't skip ahead.
        """
        if not (self.run_complete and self.awaiting_after_run):
            return
        # Whether the just-finished run was cleared, captured before it is
        # reset below (the boss-run branch below needs it).
        cleared_this_run = self.run_cleared
        # Wrecking Ball (Fragile Breaks): the gains earned during the finished
        # run become permanent after the run (retrying discards them).
        self._commit_wrecking_run_gain()
        # Cards owned DURING the finished run are destroyed when the player
        # moves on, BEFORE any reward grants below (so a card that the continue
        # itself grants is not instantly destroyed by it).
        # Sharp-scorer blocks in the marble box have a 1/4 chance to be
        # destroyed when the player moves on from a run.
        for block in self.board_blocks():
            if block.scorer == Scorer.SHARP and random.random() < 0.25:
                self.grid.pop((block.x, block.y), None)
                # The block is gone, so its switch goes off with it (and only
                # its own: every other item keeps the state the player left it),
                # and the item it was built from is destroyed with it — a block
                # that outlived its item would be a second copy of a block the
                # player no longer owns (see _release_block_item).
                self._forget_item(block)
                self._release_block_item(block)
        # Sharp-scorer cards (a generic card whose scorer half is Sharp) also
        # have a 1/4 chance to be destroyed after each run.
        if self.cards:
            kept_cards = []
            destroyed = []
            for card in self.cards:
                if card_scorer(card.value) == Scorer.SHARP \
                        and random.random() < 0.25:
                    destroyed.append(card)
                    continue
                kept_cards.append(card)
            if len(kept_cards) != len(self.cards):
                self.cards[:] = kept_cards
                for card in destroyed:
                    self._forget_item(card)
        # Satanic and Bomb cards are a one-run deal: they are destroyed after a
        # run for good (retrying keeps them), whether or not they fired. A Bomb
        # card primes the cell of the block it collided with, exactly like a
        # Bomb block, and goes off with it.
        if self.cards:
            kept_cards = []
            destroyed = []
            for card in self.cards:
                if card_scorer(card.value) in (Scorer.SATANIC, Scorer.BOMB):
                    destroyed.append(card)
                    continue
                kept_cards.append(card)
            if len(kept_cards) != len(self.cards):
                self.cards[:] = kept_cards
                for card in destroyed:
                    self._forget_item(card)
        # Resource points earned by Shreds/Rubble/Ideas/Picky scorers during
        # the finished run move into the bank (and convert into rewards) after
        # a run only; retrying discards them. These grants run
        # AFTER the card destruction above, so a freshly granted card survives.
        self._commit_resource_points()
        # Parts components banked during the finished run are handed over here,
        # one per Parts trigger (a Parts CARD banks its own magnitude). Nothing
        # was granted while the run played, so this is the only moment a Parts
        # reward ever reaches the toolbox — and a run that is retried instead
        # of continued drops the bank with every other per-run gain.
        pending_parts = self.parts_run_gain
        self.parts_run_gain = 0
        for _ in range(pending_parts):
            if not self._grant_random_component():
                # A full inventory withholds the rest, exactly as the instant
                # Parts grant used to.
                break
        # Bomb blocks touched this run detonate after a run: each unlocks its
        # 1-cell radius (diagonals included) and destroys itself. The blast goes
        # FIRST, before the Drill and Conquistador grants below, because it is a
        # fixed shape while those grants PICK squares off the locked frontier
        # (see _grant_locked_units): a drill granted first can have its squares
        # land inside the radius the bomb was about to unlock anyway and be
        # swallowed by it, so the board grows by fewer squares than the drill
        # promised — and with the blast announced last its message buried the
        # drill's, making the block look like it had done nothing at all.
        blasted = self._detonate_bombs(announce=False)
        # Drill-scorer blocks touched this run unlock their locked board
        # squares after a run (retrying discards the pending
        # drills); the Conquistador card unlocks 4 more after every run. The
        # squares only land after a run, so retrying can't farm
        # board expansions.
        drilled = 0
        if self.drill_run_units:
            drilled = self._grant_locked_units(self.drill_run_units,
                                               announce=False)
            self.drill_run_units = 0
        conquered = (self._grant_locked_units(4, announce=False)
                     if self._has_card(Card.CONQUISTADOR) else 0)
        self._announce_board_expansion(blasted, drilled, conquered)
        # 1000-handed: after every run, its thousand hands fetch one random
        # action (the same grant the Ideas conversion gives; a full action area
        # refuses it, and the offer is simply withheld).
        if self._has_card(Card.THOUSAND_HANDED) and self._grant_random_action():
            self._set_shop_message(
                f"1000-handed grants {self._item_name(self.actions[-1])}")
        # Odyssey: every item the card put away for the finished run comes back
        # into the inventory here, and pays a fraction of its sell price. It is
        # part of committing the run, so a retry returns nothing and pays
        # nothing (see _return_inaccessible), and the board-expansion messages
        # above are already out of the way.
        self._return_inaccessible()
        # Spirit tokens spend a run of coverage; Satanic and Sharp tokens obey
        # their scorer's own destruction rules (see _advance_tokens).
        self._advance_tokens()
        self.awaiting_after_run = False
        self.run_complete = False
        self.run_cleared = False
        # The finished run is COMMITTED now, so the free rerolls its Fresh hits
        # banked are the player's to keep: clearing the per-run counter here
        # (rather than leaving reset_run to do it) keeps that rollback from
        # taking a committed run's rerolls back when the next run is built,
        # started and restarted. The inventory slots its Packed blocks won are
        # committed the same way.
        self.free_rerolls_run_gain = 0
        self.inventory_slots_run_gain = 0
        # A continued run leaves the board's items where the player laid them
        # out: nothing about a discard survives — the panel it acted on is gone.
        # Choose the next run's trial now, before the run starts, so the info
        # box shows it during setup (a new round draws its own trials here, see
        # _choose_trial). The 24th run is no exception any more: it used to be a
        # boss run, and that run now plays a normal, drawn trial like the rest.
        self._choose_trial(self.run_number + 1)
        # The just-finished run's trial effects are spent: clear the state so
        # the next run's trial (chosen above, which also re-seeded the run and
        # dropped its decided picks) re-applies fresh when it starts.
        self.trial_debuffed_blocks = set()
        self.disabled_card = None
        self.trial_fragile_blocks = set()
        for block in self.board_blocks():
            block.trial_fragile = False
        self.trial_marble_weight = 1.0
        # ...and nothing of the new trials is left either: no gravity pulled
        # sideways and no card left face over. The deal-breaker gag needs no
        # clearing — a sale frees the board for good (see card_sold), so the
        # next run reads its own state from that record rather than from here.
        self.trial_gravity_dir = None
        for card in self.cards:
            card.flipped = False
        self.trial_decision = None
        # Grace's xMult belonged to the run that just finished (its bank has
        # already been flushed), so the next run starts without it.
        self.run_xmult_bonus = 0.0
        self.shop.refresh()
        # Slim pickings removes two random shop options for this run.
        self._trim_shop_for_trial()
        # The committed run is over, so the board is rebuilt from the deck: every
        # item the player owns goes back in it, and a fresh hand of
        # DECK_DRAW_SIZE is drawn where the shop's new offers are laid out (user
        # request: "when the run ends, all items owned by the player (except the
        # start and finish) are returned to the deck and 4 new random items are
        # drawn"). A RETRY never comes here, so retrying keeps the board it
        # re-runs.
        self._cycle_deck()
        self.run_number += 1
        # Once the player has clicked CONTINUE on a game-over screen, the
        # overlay never shows again for this save: those runs just advance
        # normally (the else below), so the game keeps going endless.
        if not self.continue_past_game_over and self.failed_runs >= 3:
            # Defeat: three lost runs ends the game immediately with a game
            # over screen (the player can retry a just-finished run to undo a
            # loss, but once a third loss is confirmed the game is over).
            self.game_over = True
            self.game_won = False
            self.game_perfect = False
            self._award_defeat_dice()
        elif not self.continue_past_game_over and self.run_number >= TOTAL_RUNS:
            # The last run (24) must be CLEARED to win. Clearing it wins (a
            # perfect win if every run was cleared); failing it is a loss, and a
            # player reaching run 24 has at most 2 prior losses (3 losses ends
            # the game earlier), so failing it ends in defeat.
            self.game_over = True
            if cleared_this_run and self.runs_cleared >= REQUIRED_RUNS_TO_WIN:
                self.game_won = True
                self.game_perfect = self.runs_cleared == TOTAL_RUNS
            else:
                self.game_won = False
                self.game_perfect = False
                self._award_defeat_dice()
        else:
            # Advance to the next run with its (round-based) score target,
            # grown by the save's own difficulty (1.6x on difficulty 1, 2x on
            # the rest — see Difficulty.SCORE_GROWTH) and scaled by the trial
            # that run has been given (Sky High doubles it — see
            # _refresh_run_target).
            self.round_index = self.run_number // RUNS_PER_ROUND
            self.run_in_round = self.run_number % RUNS_PER_ROUND
            # Grace v2's "this run needs a score of 0" belonged to the run that
            # just finished, so it no longer owns the next run's target.
            self.target_forced = False
            self._refresh_run_target()

    def _begin_endless_play(self):
        """Keep playing after the game-over screen: set the next run up.

        The run that ended on the game-over screen never took _continue_run's
        normal advance path (the defeat win/loss branch stopped before it), so
        the next run's target, round and run-in-round are computed here. The
        screen itself never shows again for this save (see
        continue_past_game_over).
        """
        self.game_over = False
        self.game_won = False
        self.game_perfect = False
        self.continue_past_game_over = True
        self.round_index = self.run_number // RUNS_PER_ROUND
        self.run_in_round = self.run_number % RUNS_PER_ROUND
        self.target_forced = False
        self._refresh_run_target()
        # The deck was already cycled by the _continue_run that ended the game
        # (it does that before it decides win or loss), so the hand this run was
        # built from is the one that is on the board: cycling again here would
        # throw it away and deal a different one behind the player's back.

    def _refresh_run_target(self):
        """Re-derive this run's required score: the schedule's number, scaled by
        the run's trial.

        Called wherever a run's target is set (_continue_run,
        _begin_endless_play) and wherever its trial changes — applying a trial
        (see _apply_trial), or buying a different one or no trial at all (see
        _click_trial_display) — because a trial's modifier belongs to the TRIAL
        and not to the run: Sky High doubles the target, and every other trial
        (and none) leaves it at 1x, so the recompute from the run's own
        scheduled number lands on the right answer however the trial got there.

        A target an ACTION has taken over is left alone: Grace v2 sets this
        run's target to 0 to make it unfailable (see _action_grace), and
        re-deriving it would quietly make the run failable again.
        """
        if self.target_forced:
            return
        self.required_score = int(get_next_required_score(self.run_number,
                                                          self.score_growth)
                                  * self._trial_score_factor())

    def _trial_score_factor(self):
        """The factor this run's trial puts on its required score (Sky High: 2).

        Read through active_trial, so a run with trials switched off (or one
        whose trial was bought away) is 1x whatever id the game is holding.
        """
        if self.active_trial == Trial.SKY_HIGH:
            return SKY_HIGH_SCORE_FACTOR
        return 1.0

    def _award_defeat_dice(self):
        """Award metagame dice for a defeat: (run number - 3) squared.

        Run #1 is the first run; ``self.run_number`` was already advanced to
        the just-completed run when the defeat triggered, so this is the run
        the player was on at the game over.
        """
        gained = (self.run_number - 3) ** 2
        gained = max(0, gained)
        self.game_over_dice_gained = gained
        metagame.add_dice(gained)

    def _return_to_main_menu(self):
        """Leave the finished game and go back to the title screen."""
        # Autosave the current game to its slot before leaving, so loading the
        # slot resumes where the player left off (mirrors the QUIT autosave).
        if self.save_slot is not None:
            self._retry_run()
            save_system.save_game(self)
        self.reset_game()
        self.game_over = False
        self.title_screen = True
        self.achievements_open = False
        self.marble_selecting = False
        self.upgrades_open = False
        self.collection_open = False
        self.save_slot = None

    def _buy_metagame_upgrade(self, upgrade_id):
        """Spend dice on a permanent upgrade from the UPGRADES tab."""
        if metagame.buy_upgrade(upgrade_id):
            self._set_shop_message("Upgrade purchased")
        else:
            self._set_shop_message("Not enough dice")

    def _retry_run(self):
        """Undo the completed run so the game acts as if it had not been played."""
        # True only when a FINISHED run is waiting for its RETRY/CONTINUE
        # choice — a real retry. The save/quit/menu paths also call this while
        # the player is still BUILDING (nothing to undo), so the run-scoped
        # rollbacks below must not take anything permanent with them.
        retrying = self.awaiting_after_run
        if retrying:
            # Undoing a run sounds like resetting it.
            sounds.play_reset()
            # The finished run's own records are taken back here — and ONLY
            # here, because every one of them is still standing during the
            # build phase after a CONTINUE: the save (P), quit and MAIN MENU
            # paths all call this too, and must not delete a committed run's
            # result, its win/loss, or the cash award already in the wallet.
            if self.run_results:
                self.run_results.pop()
            if self.run_cleared:
                self.runs_cleared = max(0, self.runs_cleared - 1)
            else:
                self.failed_runs = max(0, self.failed_runs - 1)
            self.cash -= self.last_run_cash_gained
            self.last_run_cash_gained = 0
            # The breakdown describes the run that was just undone, so it goes
            # too (the readout falls back to its "no run finished yet" note).
            self.last_run_cash_breakdown = {}
            # Wrecking Ball: retrying the run discards the gains it earned
            # (they only become permanent after a run).
            self._reset_wrecking_run_gain()
        # Resource points: a retry is a full do-over, so this run's pending
        # gains AND every point banked from earlier runs are reset to zero
        # (a NEW run keeps the bank — see _commit_resource_points). Rewards
        # those points already converted into (a granted card/block/action, or
        # a Picky bonus shop slot) are not points and stay.
        self.shred_run_gain = 0
        self.rubble_run_gain = 0
        self.idea_run_gain = 0
        self.option_run_gain = 0
        if retrying:
            self.shred_points = 0
            self.rubble_points = 0
            self.idea_points = 0
            self.option_points = 0
            # Free rerolls banked by Fresh hits are per-run resources too, but
            # only the ones THIS RUN granted are taken back: rerolls banked by
            # earlier runs are not the retried run's to lose. (Spending is not
            # un-spent — the count just can't go below zero.)
            self.free_rerolls = max(0, self.free_rerolls - self.free_rerolls_run_gain)
        self.free_rerolls_run_gain = 0
        # The inventory slots the retried run's Packed blocks won go back too
        # (see reset_run), so only slots a kept run earned stay won.
        self.inventory_slots_won = max(0, self.inventory_slots_won
                                       - self.inventory_slots_run_gain)
        self.inventory_slots_run_gain = 0
        # Cash earned by Cash cards this run was already folded into the run's
        # award (and undone above by the cash rollback); clear any remainder.
        self.card_cash_run_gain = 0
        # Components banked by Parts triggers this run are discarded too: they
        # are only ever granted when the run is continued (see _continue_run).
        self.parts_run_gain = 0
        # Drill-scorer locked squares earned this run are discarded on retry
        # (they only unlock after a run).
        self.drill_run_units = 0
        # Rally/Echo/Bomb run state is discarded on retry too (it only pays
        # out after a run, and a Bomb never detonates on
        # a retry).
        self.run_fresh_touches = 0
        self._prev_contact_block = None
        self.bomb_cells = set()
        self.awaiting_after_run = False
        self.run_complete = False
        self.run_cleared = False
        # Redoing the run re-applies the same trial.
        self.reset_run(False)
        self.run_active = False

    def upgrade_card_rect(self, index):
        """The screen rect for an upgrade card (index 0..2) on the UPGRADES tab."""
        card_w, card_h = 360, 200
        gap = 28
        x0 = (SCREEN_WIDTH - (3 * card_w + 2 * gap)) // 2
        return pygame.Rect(x0 + index * (card_w + gap), 250, card_w, card_h)

    def _difficulty_at(self, pos):
        """The difficulty level of the new-save screen's button at a position.

        Returns a Difficulty id, or None when the position is off the picker.
        """
        for i, level in enumerate(Difficulty.ORDER):
            if self.difficulty_button_rect(i).collidepoint(pos):
                return level
        return None

    def difficulty_button_rect(self, index):
        """The screen rect for a difficulty button (index into Difficulty.ORDER)
        on the new-save screen.

        The picker is a column down the LEFT margin of the screen: the marble
        cards are centred and 520 wide, so they leave that margin free for the
        four levels and the chosen level's description underneath.
        """
        button_w, button_h, gap = 280, 60, 10
        return pygame.Rect(30, 280 + index * (button_h + gap), button_w, button_h)

    def marble_card_rect(self, index):
        """The screen rect for a marble-type card (index into MarbleType.ORDER)
        on the marble-selection screen.

        The cards stack from a fixed top edge and are sized so every type fits
        above the BACK button row (the toggle sits below it).
        """
        n = max(1, len(MarbleType.ORDER))
        card_w = 520
        gap = 6
        top = 196
        bottom_limit = MARBLE_BACK_BUTTON_RECT.top - 16
        card_h = int((bottom_limit - top - (n - 1) * gap) / n)
        x = (SCREEN_WIDTH - card_w) // 2
        y = top + index * (card_h + gap)
        return pygame.Rect(x, y, card_w, card_h)

    def _marble_preview(self, marble_type):
        """A throwaway marble set up to preview a type on the selection screen."""
        preview = Marble(0, 0)
        preview.marble_type = marble_type
        if marble_type == MarbleType.RUBBER_BALL:
            preview.color = RUBBER_BALL_COLORS[0]
            preview.color2 = RUBBER_BALL_COLORS[1]
        elif marble_type == MarbleType.PING_PONG:
            preview.color = PING_PONG_COLORS[0]
            preview.color2 = PING_PONG_COLORS[1]
        preview.velocity = np.array([0.0, 0.0])
        preview.spin_angle = 0.0
        return preview

    def _match_group_description(self, group):
        """The codex line for a match group: what its cards trigger on.

        A group is not something the player buys, so its entry describes the
        FAMILY the group stands for: the collision every card of it fires on,
        and how many cards that is (one per card scorer, each with its own
        rolled magnitude). A group whose label already names several shapes
        ("Flat Line/Curved Slope Line/Half Pipe") is described by that label
        instead: spelling the same shapes out again is what pushed those lines
        past the box (see ui.draw_collection).
        """
        label = match_group_label(group)
        if "/" in label:
            return (f"Cards that fire on {label} blocks — "
                    f"one per card scorer.")
        return (f"Cards that fire {match_group_trigger(group)} — "
                f"one per card scorer.")

    def _collection_entries(self):
        """Every collection entry: (kind, value, name, description, has_icon,
        discovered). Undiscovered entries show \"???\" for name and description."""
        entries = []
        # The cards that are not built on a match group appear one by one. A
        # match-group card is represented by the GROUP it is built on (plus its
        # scorer, which is a component entry of its own), so the codex lists the
        # 26 groups rather than all 832 cards.
        for value in Card.ORDER:
            d = collection.is_card_discovered(value)
            entries.append(("card", value, Card.name(value) if d else "???",
                            Card.description(value) if d else "???", True, d))
        for index, group in enumerate(MATCH_GROUPS):
            d = collection.is_match_group_discovered(index)
            entries.append(("match_group", index,
                            match_group_label(group) if d else "???",
                            self._match_group_description(group) if d else "???",
                            True, d))
        for value in Action.ORDER:
            d = collection.is_action_discovered(value)
            entries.append(("action", value, Action.name(value) if d else "???",
                            Action.description(value, 1) if d else "???", True, d))
        for value in Shape.ORDER:
            d = collection.is_component_discovered(Component.SHAPE, value)
            entries.append(("shape", value, Shape.name(value) if d else "???",
                            shape_description(value) if d else "???", True, d))
        for value in Effect.ORDER:
            d = collection.is_component_discovered(Component.EFFECT, value)
            entries.append(("effect", value, Effect.name(value) if d else "???",
                            effect_description(value) if d else "???", True, d))
        for value in Scorer.ORDER:
            d = collection.is_component_discovered(Component.SCORER, value)
            entries.append(("scorer", value, Scorer.name(value) if d else "???",
                            scorer_description(value, Scorer.DEFAULT_AMOUNT.get(value, 0))
                            if d else "???", True, d))
        # The pack types the shelf can deal, one entry each: a pack is revealed
        # by buying one of its type, and its SIZE is not part of the entry (a
        # big card pack and a giga card pack) — see collection.discover_pack.
        for value in Pack.ORDER:
            d = collection.is_pack_discovered(value)
            entries.append(("pack", value, Pack.name(value) if d else "???",
                            Pack.description(value) if d else "???", True, d))
        for value in Trial.ORDER:
            d = collection.is_trial_discovered(value)
            entries.append(("trial", value, Trial.name(value) if d else "???",
                            Trial.description(value) if d else "???", True, d))
        return entries

    def _toggle_crt_filter(self):
        """F2: switch the CRT screen filter on and off, and remember it."""
        self.crt_filter = not self.crt_filter
        metagame.set_crt_filter(self.crt_filter)
        self._set_shop_message(
            f"CRT filter {'on' if self.crt_filter else 'off'}")

    def _present(self):
        """Show the frame that has just been drawn (see run).

        Every screen is drawn into the off-screen frame buffer (self.screen),
        filtered there when the CRT filter is on (see crt.apply), and only then
        blitted to the window in one go: the window never shows a half-filtered
        frame, which is what used to make the picture strobe between filtered
        and unfiltered. Nothing else in the game presents a frame, so this is
        the only flip. F2 toggles the filter.
        """
        if self.crt_filter:
            crt.apply(self.screen)
        self.display.blit(self.screen, (0, 0))
        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            ui.draw(self)
            self._present()
            self.clock.tick(FPS)
        
        pygame.quit()
