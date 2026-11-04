"""The text the info box shows: an item's rows, the payoff it is worth right now,
and the cash breakdown."""

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


class DescribeMixin:
    """The info box's text: an item's rows, the payoff it is worth right
    now, and the cash breakdown."""


    def _live_payoff_row(self, item):
        """The row saying what a state-dependent item pays as things stand.

        Some scorers and cards pay for the STATE of the game rather than a fixed
        amount — Roomy pays for every unlocked board unit, Stencil for every
        free card slot — so their descriptions can only state the rate ("+2
        chips for each unlocked board unit"). This row is the other half: what
        that rate comes to right now, e.g. "Gives +80 chips (2 x 40 unlocked
        units)", so two offers can be compared without the player doing the
        arithmetic. Returns None for an item whose payoff is already a fixed
        number (a +30 chips block, a card with no measure of its own).

        The counts come from the very helpers the payoffs use (see
        _roomy_units and cards._named_card_units), so the row can never report a
        number the payoff would not pay. A scorer that pays for the TOUCHING
        MARBLE (Quick's speed, Airball's air time, Voyager's distance, Colossus'
        size, a Gilded block's chips are the game's, not the marble's) has no
        value until the marble touches it, so those get no row: there is nothing
        settled to report.
        """
        kind = getattr(item, "kind", None)
        if kind == "card":
            row = self._card_payoff_row(item.value)
        elif kind == "token":
            row = self._scorer_payoff_row(item.block.scorer,
                                          item.block.scorer_amount)
        elif isinstance(item, Block):
            row = self._scorer_payoff_row(item.scorer, item.scorer_amount,
                                          block=item)
        elif kind == "block":
            row = self._scorer_payoff_row(item.scorer, item.scorer_amount)
        elif kind == Component.SCORER:
            row = self._scorer_payoff_row(item.value, item.amount)
        else:
            row = None
        return ("Now", row) if row else None

    def _scorer_payoff_row(self, scorer, amount, block=None):
        """What a state-dependent scorer's rate comes to right now, or None.

        ``block`` is the block the scorer sits on, for the scorers that pay for
        WHERE they are placed (Summit, Powerline, Frontier, Cluster); a scorer
        in the shop or the inventory has no square yet, so those four say
        nothing about a number the player could still change by placing it
        elsewhere.
        """
        if scorer == Scorer.ROOMY:
            units = self._roomy_units()
            return (f"Gives +{amount * units:g} chips "
                    f"({amount:g} x {units} unlocked units)")
        if scorer == Scorer.SEED:
            per_seed = amount * (2 if self._has_card(Card.GARDEN) else 1)
            units = self._seed_units()
            return (f"Gives +{per_seed * units:g} mult "
                    f"({per_seed:g} x {units} Seed block{_s(units)})")
        if scorer == Scorer.GILDED:
            gained = self.score_chips / MAGNITUDES.GILDED_DIVISOR
            return (f"Gives +{gained:g} mult (1/{MAGNITUDES.GILDED_DIVISOR:g} "
                    f"of {self.score_chips:g} chips)")
        if scorer == Scorer.UNDERTAKER:
            units = self.run_blocks_destroyed
            return (f"Gives +{amount * units:g} mult "
                    f"({amount:g} x {units} block{_s(units)} destroyed this run)")
        if scorer == Scorer.RALLY:
            # Its own touch is already counted (see _apply_block_score_effect).
            units = max(0, self.run_fresh_touches - 1)
            return (f"Gives +{amount * units:g} mult "
                    f"({amount:g} x {units} earlier fresh touches this run)")
        if block is None:
            return None
        if scorer == Scorer.SUMMIT:
            units = self._summit_units(block)
            return (f"Gives +{amount * units:g} mult "
                    f"({amount:g} x {units} row{_s(units)} above the bottom row)")
        if scorer == Scorer.POWERLINE:
            units = self._powerline_units(block)
            return (f"Gives +{amount * units:g} chips "
                    f"({amount:g} x {units} block{_s(units)} in its row)")
        if scorer == Scorer.FRONTIER:
            units = self._frontier_units(block)
            return (f"Gives +{amount * units:g} mult "
                    f"({amount:g} x {units} locked or bordered side{_s(units)})")
        if scorer == Scorer.CLUSTER:
            units = self._cluster_units(block)
            return (f"Gives +{amount * units:g} mult "
                    f"({amount:g} x {units} adjacent block{_s(units)})")
        return None

    def _card_payoff_row(self, value):
        """What a measured card pays with things as they are, or None.

        A named card pays for a MEASURE of the game — Stencil for the free card
        slots, Cozy for the board units still locked — so its description can
        only state the rate. This reads the same measure the payoff does (see
        cards._named_card_units) and turns it into the same payoff the card
        would pay (components.magnitude_payoff), with the measure itself in
        brackets, so the number can be checked against the board.
        """
        meta = Card.NAMED.get(value)
        if meta is None:
            return None
        phase, scorer, ratio, measure = meta
        # "start" is a card with no measure at all (it simply fires, for a
        # fixed payoff the description already gives) and "fragile_breaks" is a
        # rate the card pays per break, not a total. Both read the same on every
        # reading, so neither needs a "now" number.
        if measure in ("start", "fragile_breaks"):
            return None
        units = cards._named_card_units(self, measure)
        payoff = components.magnitude_payoff(scorer, ratio, units)
        when = ("at the start of the run" if phase == "start"
                else "at the end of the run")
        return (f"Pays {components.payoff_text(*payoff)} {when} "
                f"({self._measure_now_text(measure, units)})")

    def _measure_now_text(self, measure, units):
        """How a card's measure reads right now, e.g. "4 free card slots".

        One line per measure (see cards._named_card_units for what each one
        counts); the count is what the card's payoff is multiplied by.
        """
        if measure == "visited_units":
            return f"{units / 4:.0%} of the board visited this run"
        if measure == "black_hole":
            return f"{units:.1f}s pulled by a black hole this run"
        if measure == "air_time":
            return f"{units:.1f}s airborne this run"
        if measure == "fullest_column":
            return f"{units:g} blocks in the fullest column"
        if measure == "cash_held":
            return f"${units * 10:g} held"
        if measure == "slippery":
            return f"{units:g} slippery block{'' if units == 1 else 's'} owned"
        if measure == "random":
            return f"{units:.2f} units rolled for this run"
        if measure == "few_blocks":
            blocks = len(self.board_blocks())
            return (f"{blocks} blocks on the board (5 or fewer)" if units
                    else f"{blocks} blocks on the board (more than 5)")
        if measure == "cozy":
            unlocked = len(self.unlocked_cells)
            return (f"{unlocked} unlocked units (10 or fewer)" if units
                    else f"{unlocked} unlocked units (more than 10)")
        if measure == "painting":
            return f"${units:g} of board sell value"
        if measure == "synthesizer":
            return f"{units:g} card{'' if units == 1 else 's'} held"
        if measure == "island":
            plural = "" if units == 1 else "s"
            return f"{units:g} group{plural} of unlocked units"
        if measure == "pipe_streak":
            return (f"{units:g} pipe streak{'' if units == 1 else 's'} "
                    f"completed this run")
        if measure == "inside_time":
            return (f"{getattr(self, 'inside_block_time', 0.0):.1f}s inside "
                    f"blocks + {getattr(self, 'inside_locked_time', 0.0):.1f}s "
                    f"inside locked units")
        if measure == "card_sell_total":
            return f"${units:g} of card sell value"
        if measure == "stencil_slots":
            return f"{units:g} free card slot{'' if units == 1 else 's'}"
        if measure == "plain_rects":
            return (f"{units:g} plain Rect block"
                    f"{'' if units == 1 else 's'} on the board")
        if measure == "inside_locked_no_phase":
            return f"{units:.1f}s inside locked units this run"
        return f"{units:g} units"

    def _describe_item(self, item):
        """Return [(label, description)] rows shown in the sidebar.

        Blocks break down into their shape, effect, and scorer so the player
        sees each part's behavior independently; components describe themselves.
        Each label names the part, e.g. "Shape - Slope", followed by the
        description.
        """
        if item is CASH_BREAKDOWN:
            return self._cash_breakdown_rows()
        # The row a state-dependent item needs is the same wherever the item is
        # shown (a placed block, one in hand, a shop component, a card), so it
        # is read once here (see _live_payoff_row).
        live = self._live_payoff_row(item)
        if getattr(item, "kind", None) == "pack":
            # A pack describes itself by what it holds and by its size's rule:
            # how many options it deals out and how many of them are kept.
            return [
                (f"Pack - {Pack.name(item.pack_type)}",
                 Pack.description(item.pack_type)),
                (f"Size - {Pack.size_name(item.size)}",
                 (f"{Pack.options(item.size)} options, "
                  f"{Pack.size_description(item.size)}")),
                ("Kept", f"{item.kept} of {item.keep} kept so far"),
            ]
        if getattr(item, "kind", None) == "resource":
            # A resource option is POINTS rather than a component, so it says
            # what the scorer banks and what the option is worth: the factor
            # times that, at the magnitude the option rolled.
            plural = "" if item.points == 1 else "s"
            return [
                (f"Resource - {Scorer.name(item.scorer)}",
                 scorer_description(item.scorer, item.amount)),
                ("Option", (f"Banks {points_text(item.points)} "
                            f"{resource_point_label(item.scorer)} point{plural} "
                            f"at once")),
            ]
        if getattr(item, "kind", None) == "token":
            # A token is a whole kept block, so it describes itself the way that
            # block did on the board (shape, effects, scorer), plus when it
            # fires. The trigger count is not reported: a token fires once per
            # run whatever the block's own limit was.
            block = item.block
            runs = ("every run, permanently" if item.runs_left is None
                    else f"{item.runs_left} more run(s)")
            timing = ("at the end of each run, when the run's xMult lands"
                      if item.fires_at_end else "at the start of each run")
            label = f"Token - {Shape.name(block.shape)} {Scorer.name(block.scorer)}"
            rows = [(label,
                     (f"A kept block: it fires {timing}, exactly as if a marble "
                      f"collided with it ({runs})."))]
            rows.append((f"Shape - {Shape.name(block.shape)}",
                         shape_description(block.shape)))
            for e in block.effects:
                rows.append((f"Effect - {Effect.name(e)}",
                             effect_description(e, block.effect_magnitude(e))))
            rows.append((f"Scorer - {Scorer.name(block.scorer)}",
                         scorer_description(block.scorer, block.scorer_amount)))
            if live:
                rows.append(live)
            return rows
        if isinstance(item, Block):
            rows = [(f"Shape - {Shape.name(item.shape)}", shape_description(item.shape))]
            for e in item.effects:
                rows.append((f"Effect - {Effect.name(e)}",
                             effect_description(e, item.effect_magnitude(e))))
            rows.append((f"Scorer - {Scorer.name(item.scorer)}", scorer_description(item.scorer, item.scorer_amount)))
            if live:
                rows.append(live)
            rows += self._pair_description_rows(item)
            if item.scorer in (Scorer.CHIPS_ADD, Scorer.MULT_ADD, Scorer.MULT_MUL,
                               Scorer.QUICK, Scorer.CASH, Scorer.SHARP,
                               Scorer.PARTS, Scorer.SHREDS, Scorer.RUBBLE, Scorer.IDEAS,
                               Scorer.RANDOM, Scorer.EFFECTIVE, Scorer.FRESH,
                               Scorer.PICKY, Scorer.VOYAGER, Scorer.SATANIC,
                               Scorer.SUMMIT, Scorer.AIRBALL):
                limit = self._trigger_limit(item)
                if limit == 1:
                    rows.append(("Trigger", f"Scores once per run ({item.triggers_left} left)"))
                else:
                    rows.append(("Trigger", f"Scores {limit} times per run ({item.triggers_left} left)"))
            return rows
        if getattr(item, "kind", None) == "block":
            rows = [(f"Shape - {Shape.name(item.shape)}", shape_description(item.shape))]
            for e in item.effects:
                rows.append((f"Effect - {Effect.name(e)}",
                             effect_description(e, item.effect_magnitude(e))))
            rows.append((f"Scorer - {Scorer.name(item.scorer)}", scorer_description(item.scorer, item.scorer_amount)))
            if live:
                rows.append(live)
            rows += self._pair_description_rows(item)
            if item.scorer in (Scorer.CHIPS_ADD, Scorer.MULT_ADD, Scorer.MULT_MUL,
                               Scorer.QUICK, Scorer.CASH, Scorer.SHARP,
                               Scorer.PARTS, Scorer.SHREDS, Scorer.RUBBLE, Scorer.IDEAS,
                               Scorer.RANDOM, Scorer.EFFECTIVE, Scorer.FRESH,
                               Scorer.PICKY, Scorer.VOYAGER, Scorer.SATANIC,
                               Scorer.SUMMIT, Scorer.AIRBALL):
                limit = self._trigger_limit(item)
                if limit == 1:
                    rows.append(("Trigger", "Scores once per run"))
                else:
                    rows.append(("Trigger", f"Scores {limit} times per run"))
            return rows
        if getattr(item, "kind", None) == "card":
            rows = [
                (f"Card - {Card.name(item.value)}",
                 card_description(item.value, getattr(item, "amount", 0))),
            ]
            if live:
                rows.append(live)
            rows += [("Rarity", Card.rarity_name(item.value)),
                     ("Comment", Card.comment(item.value))]
            return rows
        if getattr(item, "kind", None) == "action":
            version = getattr(item, "version", 1)
            # The version row is the whole point of an action's info box: v1
            # still has the upgrade to buy, while a v2 (whether the player paid
            # for it or the shop rolled it already upgraded — see
            # random_action_version) has nothing left to spend on it.
            if version >= 2:
                version_text = "v2 — fully upgraded (the strongest version)"
            else:
                version_text = ("v1 — upgrade to v2 for "
                                f"${self._inflated(ACTION_UPGRADE_COST)}")
            return [
                (f"Action - {Action.name(item.value)}",
                 Action.description(item.value, version)),
                ("Version", version_text),
                ("Comment", Action.comment(item.value)),
            ]
        if item.kind == Component.SHAPE:
            return [(f"Shape - {Shape.name(item.value)}", shape_description(item.value))]
        if item.kind == Component.EFFECT:
            return [(f"Effect - {Effect.name(item.value)}",
                     effect_description(item.value, item.effect_magnitude))]
        if item.kind == Component.SCORER:
            rows = [(f"Scorer - {Scorer.name(item.value)}",
                     scorer_description(item.value, item.amount))]
            if live:
                rows.append(live)
            return rows
        # COMMENTED OUT with the conditions: the sidebar row for a condition
        # component (its name and its trigger prose).
        #
        # if item.kind == Component.CONDITION:
        #     return [(f"Condition - {Condition.name(item.value)}",
        #              condition_description(item.value))]
        return []

    def _pair_description_rows(self, item):
        """Sidebar rows explaining a block's pairing (key/lock pairs).

        A Key/Lock block's number is its whole point — the two halves only work
        together — so the sidebar names the pair and how it opens.
        """
        number = getattr(item, "key_number", 0)
        if not number or paired_shape(block_shape(item)) is None:
            return []
        return [("Pair", (f"Key/Lock pair #{number} — the Lock is a solid door until "
                          "a marble passes through its Key. Locks close again at the "
                          "start of each run."))]

    def _cash_breakdown_rows(self):
        """Sidebar rows for the shop's "Last run cash gained" readout.

        Every dollar a run pays is listed with where it came from: the flat
        base payment, interest on the cash held at the end of the run, the
        bonus for beating the required score, Cash cards, and the Cash/Lucky
        scorers (which pay out as they trigger rather than at the end).
        """
        rows = self.last_run_cash_breakdown
        if not rows:
            return [("Last run", ("No run has been finished yet — finish a "
                                  "run (or retry it) to see where its cash "
                                  "came from."))]
        # A Debt block cancels the interest, so the readout says so.
        interest_note = " (cancelled by a Debt block)" if rows.get("debt") else ""
        return [
            ("Base cash", (f"${rows.get('base', 0)} — the flat payment for "
                           "finishing a run")),
            ("Interest", (f"${rows.get('interest', 0)} — $1 for every $10 you "
                          f"held at the end of the run{interest_note}")),
            ("Beat the required score", (f"${rows.get('score', 0)} — scaled by "
                                         "how far past the target the run's "
                                         "score went")),
            ("Cash cards", (f"${rows.get('cards', 0)} — from Cash-scorer cards "
                            "(paid out with this award)")),
            ("Cash/Lucky scorers", (f"${rows.get('scorers', 0)} — from Cash "
                                    "blocks and Lucky rolls (paid out as they "
                                    "trigger, and undone by a retry)")),
            ("Essence", (f"${rows.get('essence', 0)} — the flat "
                          f"${ESSENCE_RUN_CASH} the Essence card pays at the "
                          "end of every run")),
            ("Total", f"${self.last_run_cash_gained} earned on the last run"),
        ]

    def _action_hint(self, item, source):
        """A short hint telling the player how to act on the hovered item."""
        if source == "shop":
            # A pack is bought to be opened, so the hint says so rather than
            # offering Hoard's hold (a pack that is opened leaves the shelf
            # anyway — see _open_pack).
            if getattr(item, "kind", None) == "pack":
                return f"Left-click to buy and open ({Pack.size_description(item.size)})"
            if self._has_card(Card.HOARD):
                return ("Left-click to buy | Right-click to hold it in place "
                        "across rerolls")
            return "Left-click to buy"
        if source == "pack":
            # The open pack's overlay: the hovered OPTION is one click away, and
            # it is named by its own kind — a pack deals the same goods the
            # shelf sells — so the player can tell a card from a shape before
            # spending one of the pack's picks on it.
            kind = getattr(item, "kind", None)
            what = {"card": "this card", "action": "this action",
                    "block": "this block",
                    "resource": "these resource points"}.get(kind)
            if what is None:
                part = {"shape": "shape", "effect": "effect",
                        "scorer": "scorer"}.get(kind, "part")
                what = f"this {part}"
            hint = f"Left-click to keep {what}"
            pack = self.open_pack
            if pack is not None and pack.remaining > 0:
                plural = "" if pack.remaining == 1 else "s"
                hint += (f" ({pack.remaining} pick{plural} left) | "
                         f"Right-click to leave the rest")
            return hint
        if source == "tokens":
            if item.fires_at_end:
                return "Fires at the end of each run it covers (xMult)"
            return "Fires at the start of each run it covers"
        if source == "board":
            # Everything the player owns lies on the board, so one hint covers
            # the cards, the actions and the parts (see Game.ensure_board_cells).
            kind = getattr(item, "kind", None)
            if kind == "card":
                return "Click to select (click again to deselect) | B to sell"
            if kind == "action":
                if not Action.needs_target(getattr(item, "value", None)):
                    return "Press S to use — it needs no target"
                return "Click a target block/card, then press S to use"
            if (isinstance(item, Block)
                    or getattr(item, "placed_cell", None) is not None):
                hint = ("Click to pick the block up and move it "
                        "(right-click it to erase it)")
            elif kind == "block":
                hint = ("Click to select it, then click a square to build it "
                        "| D to disassemble")
            else:
                hint = "Click to select it for the next block | S to assemble"
            # Odyssey's own verb, where the player is looking when they use it.
            if self._has_card(Card.ODYSSEY) and self.can_bank_selected():
                hint += " | G to put it away for the run"
            return hint
        return ""  # Anything else has no extra action.

    def _wrap_text(self, text, font, max_width):
        """Word-wrap text into lines that fit within max_width pixels."""
        lines = []
        current = ""
        for word in text.split():
            trial = current + (" " if current else "") + word
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _total_price(self, item):
        """A block's full worth: original price plus cash paid for trigger upgrades.

        Returns None for items without a price or without any upgrades.
        """
        if not hasattr(item, "price"):
            return None
        paid = getattr(item, "trigger_paid", 0)
        if not paid:
            return None
        return item.price + paid

    def _is_assigned(self, item):
        """True when a toolbox component is assigned to the next block."""
        return item in self.assigned_toolbox_indexes
