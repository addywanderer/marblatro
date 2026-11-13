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
    Modifier,
    Ability,
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
    Group,
    Keyword,
    Passive,
    MarbleType,
    Pack,
    Quality,
    Rarity,
    Structure,
    Tool,
    Verb,
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
    ENERGY_READOUT,
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


def _hit_points(value):
    """An enemy's health in the fewest characters: 8.4M rather than 838860800.

    A level's health is the score its run used to require (see
    components.Level.enemy_health), so a late level's numbers run to nine digits
    and the plain form would push the row out of the sidebar.
    """
    value = max(0, int(value))
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"),
                          (1_000, "k")):
        if value >= limit:
            text = f"{value / limit:.1f}"
            if text.endswith(".0"):
                text = text[:-2]
            return text + suffix
    return str(value)


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
        """The sidebar rows for an item, plus its ABILITY (see components.Ability).

        Everything an item can be USED for comes from the one ability table, so
        an item that gains a capability gains its sidebar row with it: the
        contract line below ("Needs ... Costs ...") is generated, never written
        by hand, which is what keeps the hint and the handler saying the same
        thing.
        """
        rows = list(self._describe_item_parts(item))
        # How RARE it is (user request: "give all items a rarity"): one row for
        # every kind of item, from the one table (see components.Rarity), so a
        # part, an action, a tool, a pack, a structure, a passive, a block and a
        # token all say their tier beside a card. An item with no tier (the bar's
        # Cash and Energy readouts, the level's own things) has no row at all.
        rarity = Rarity.of(item)
        if rarity is not None:
            rows.append(("Rarity", Rarity.name(rarity)))
        # What FAMILY it belongs to, and what that family is for (see Group):
        # every item says which group it is in, right after its own text. The
        # info box lifts this row out and draws it as a highlighted box under the
        # item's name (see ui.draw_item_info / Game._describe_item_rows).
        group_row = self._group_row(item)
        if group_row is not None:
            rows.append(group_row)
        # What has been DONE to it (see components.Modifier): a golem's tier, a
        # vodka's forgotten stacks, a spark's temporary, an action's v2, a
        # token's runs. One row per modifier, from the one table, so an item
        # with no modifiers has no row at all.
        for modifier, stacks in Modifier.of(item):
            text = Modifier.description(modifier)
            if stacks not in (1, Modifier.PERMANENT):
                text = f"{text} ({stacks} stacks)"
            rows.append((f"Modifier - {Modifier.name(modifier).capitalize()}",
                         text))
        ability = Ability.of(item)
        if ability is not None and not getattr(item, "is_enemy", False):
            count = (self.required_targets(item)
                     if ability == Ability.APPLY else None)
            # A card that takes a structure IF there is one (Dynamite) says so
            # in its own words: "Needs 1 target" would be a lie (see
            # Action.OPTIONAL_TARGET).
            needs = None
            if ability == Ability.APPLY and Action.optional_target(
                    getattr(item, "value", None)):
                needs = "no target, or 1 structure"
            # A tool's opening costs ITS energy: 1 for the four the player
            # starts with, nothing for a brick (see Tool.ENERGY).
            cost = None
            if ability == Ability.OPEN and getattr(item, "kind", None) == "tool":
                energy = Tool.energy(item.value)
                cost = f"{energy} energy" if energy else "nothing"
            if ability == Ability.APPLY:
                # An ACTION that asks for energy (the newest ones) says so here.
                # What a used card spends of ITSELF is its own keyword now — a
                # used card says "consume" (see components.Keyword), and a
                # reusable one says "reusable" and is never discarded — so the
                # contract line names the energy alone (user request: "make all
                # cards homogenous").
                asks = Action.energy(getattr(item, "value", None))
                if Keyword.has(item, Keyword.REUSABLE):
                    cost = (f"{asks} energy" if asks
                            else "nothing — it is not discarded")
                elif asks:
                    cost = f"{asks} energy"
            rows.append((f"Ability - {Ability.name(ability)}",
                         f"{Ability.contract(ability, count, cost, needs)} "
                         f"Press S to use it."))
        return rows

    def _group_row(self, item):
        """The description row that names an item's GROUP, or None.

        User request: "sort all items into groups, and show it in their
        description what group they are in" — and then "show an item's group in
        a highlighted box directly under the item's name". The row is written
        here, once, so the info box can draw it as that box (see
        ui.draw_item_info) without writing the group's name or meaning a second
        time (see components.Group).
        """
        group = Group.of(item)
        if group is None:
            return None
        return (f"Group - {Group.name(group)}", Group.description(group))

    def _describe_item_rows(self, item):
        """(the group row, the item's other description rows), for the info box.

        The group is drawn as a highlighted box under the item's name, so the
        box asks for the two halves separately: what goes in the box, and what
        goes below it. A pack's option cells want the second half only, so a
        group's line never stands in for an option's own text.
        """
        group_row = self._group_row(item)
        return (group_row,
                [row for row in self._describe_item(item) if row != group_row])

    def _describe_item_parts(self, item):
        """Return [(label, description)] rows shown in the sidebar.

        Blocks break down into their shape, effect, and scorer so the player
        sees each part's behavior independently; components describe themselves.
        Each label names the part, e.g. "Shape - Slope", followed by the
        description.
        """
        if item is CASH_BREAKDOWN:
            return self._cash_breakdown_rows()
        if item is ENERGY_READOUT:
            return self._energy_rows()
        # The row a state-dependent item needs is the same wherever the item is
        # shown (a placed block, one in hand, a shop component, a card), so it
        # is read once here (see _live_payoff_row).
        live = self._live_payoff_row(item)
        if getattr(item, "is_enemy", False):
            # An enemy is the level's, not the player's: it reads out what it is,
            # how it behaves and how much fight it has left.
            return [
                (f"Enemy - {item.name}", item.description),
                ("Health", f"{_hit_points(item.hp)} of "
                           f"{_hit_points(item.max_hp)} left"),
                ("Damage", "The marble that touches it deals its chips x mult "
                           "as damage, and both are then halved"),
            ]
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
        if getattr(item, "kind", None) == "structure":
            # A structure says what opens it and what comes out: the card is
            # the player's clue to which of the four they need. Every card that
            # can open one is listed — the tools by the verb each carries, and
            # the actions whose tables say they open structures (Dynamite,
            # Stormcloud) — so the row can never leave out a way in.
            openers = [f"{Tool.name(Tool.for_verb(verb))} ({Verb.name(verb)})"
                       for verb in Structure.verbs(item.value)]
            for value in Action.OPENS:
                if any(Structure.result(item.value, verb) is not None
                       for verb in Action.opens_with(value)):
                    openers.append(Action.name(value))
            rows = [(f"Structure - {Structure.name(item.value)}",
                     Structure.description(item.value)),
                    ("Opened by", ", ".join(openers) or "nothing"),
                    ("Cost", ("Free — aim a card that opens structures at it and "
                              "press S; the opening costs that card's energy"))]
            comment = Structure.comment(item.value)
            if comment:
                rows.append(("Note", comment))
            return rows
        if getattr(item, "kind", None) == "tool":
            # Every item in the Cards family reads as a CARD here (user request:
            # "make all cards homogenous, and treat them the same way"): what
            # tells a tool from a whole card is its KEYWORDS and its ability, not
            # a label, so the row is the same shape for all three kinds.
            rows = [(f"Card - {Tool.name(item.value)}",
                     Tool.description(item.value))]
            rows += self._keyword_rows(item)
            rows.append(("Energy", (f"{Tool.energy(item.value)} a use"
                                    f" ({self.energy} left this run)")))
            if Tool.draws(item.value):
                rows.append(("Draw",
                             f"{Tool.draws(item.value):g} item"
                             f"{'' if Tool.draws(item.value) == 1 else 's'}"
                             f" after it is used"))
            if getattr(item, "amount", 0):
                # A tool that SHAPES its reward states the number it holds, and
                # what that number means for this tool (a chisel's pack sizes, a
                # gilding cloth's tiers), so a golem-doubled one reads 2.
                rows.append(("Magnitude",
                             f"{self._particle_amount_text(item.amount)} "
                             f"{Tool.amount_label(item.value)}"))
            if Tool.sweeps(item.value):
                rows.append(("Sweep", "Opens every structure next to the one "
                                      "it is used on"))
            return rows
        if getattr(item, "kind", None) == "passive":
            # An UNPLAYABLE item: it is never used, it pays at the start of the
            # run, and that is the whole of it (user request: the Concrete). It
            # describes the magnitude it actually carries, so a combined one
            # reads out the chips it really adds.
            return ([(f"Item - {Passive.name(item.value)}",
                      Passive.description(item.value, item.amount))]
                    + self._keyword_rows(item))
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
            # A whole card is a CARD like an action or a tool: its own line says
            # what it pays, its keywords say it is unplayable, and the Timing row
            # says when it pays (see _card_timing_row) — so nothing it does is
            # left to the word "card" to imply (user request).
            rows = [(f"Card - {Card.name(item.value)}",
                     card_description(item.value, getattr(item, "amount", 0)))]
            rows += self._keyword_rows(item)
            rows.append(self._card_timing_row(item))
            if live:
                rows.append(live)
            rows.append(("Comment", Card.comment(item.value)))
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
            # An action is a CARD too (user request: "make all cards homogenous"):
            # its own line says what it does, and its keywords say what using it
            # costs it — "consume", or "reusable" when the card is not spent.
            rows = [(f"Card - {Action.name(item.value)}",
                     Action.description(item.value, version,
                                        getattr(item, "amount", 0)))]
            rows += self._keyword_rows(item)
            rows.append(("Version", version_text))
            if getattr(item, "amount", 0):
                # An action that carries a magnitude states the number it is
                # holding, so a Lantern a golem doubled reads out the draws it
                # really gives (see MAGNITUDES.ACTIONS).
                rows.append(("Magnitude",
                             f"{self._particle_amount_text(item.amount)} a use"))
            rows.append(("Comment", Action.comment(item.value)))
            return rows
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

    def _keyword_rows(self, item):
        """An item's KEYWORDS, and a row for each word that needs explaining.

        User request: "make sure everything a card does is shown in its info
        box, using keywords or other explanatory mechanisms." The words
        themselves go on one row (see components.Keyword); a word whose rule is
        not obvious from the noun gets its own row directly under it, from the
        same table, so a whole card explains "unplayable" and a consumed card
        explains "consume" in the very words the vocabulary defines.

        The words are read from the ITEM, not from its kind, so a reusable card
        reads "reusable" and says nothing about being destroyed (see
        components.Keyword.of).
        """
        rows = []
        words = Keyword.line(item)
        if words:
            rows.append(("Keywords", words))
        if Keyword.has(item, Keyword.CONSUME):
            rows.append(("Consume", Keyword.description(Keyword.CONSUME)))
        if Keyword.has(item, Keyword.UNPLAYABLE):
            rows.append(("Passive", Keyword.description(Keyword.UNPLAYABLE)))
        return rows

    def _card_timing_row(self, item):
        """WHEN a whole card acts, in words — every whole card says so.

        A whole card is unplayable (see components.Keyword): nothing is pressed
        to make it fire, so when it fires is the one thing its face cannot show.
        The answer is the card's own row, never a guess: a measured card fires at
        the start or the end of a run, or when a fragile block breaks (see
        Card.NAMED); a match-group card fires when a marble collides with a block
        its group matches (see match_group_trigger); every other whole card is
        always on, and its own text says when it pays.
        """
        value = getattr(item, "value", None)
        meta = Card.NAMED.get(value)
        if meta is not None:
            phase = meta[0]
            if phase == "start":
                return ("Timing", "Fires at the start of every run")
            if phase == "end":
                return ("Timing", "Fires at the end of every run")
            return ("Timing",
                    "Fires whenever one of your fragile blocks breaks")
        meta = match_group_card_meta(value)
        if meta is not None:
            return ("Timing", f"Fires {match_group_trigger(meta[0])}")
        return ("Timing", ("Always on while you own it \u2014 its text says when "
                           "it pays"))

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

    def _energy_rows(self):
        """Sidebar rows for the top bar's ENERGY bar (see ui.draw_energy_bar).

        Energy is the run's budget for every card that asks for it — the four
        tools the player starts with, the one-shot tools, and the actions whose
        table names an energy cost (`Action.ENERGY`) — so the readout says what
        it is for, what it stands at right now, and that it comes back with the
        next run (user request: "the player's max energy is 3, and energy resets
        to max each run").
        """
        spenders = ", ".join(
            f"{Action.name(value)} ({Action.energy(value)} energy)"
            for value in Action.ORDER
            if Action.energy(value))
        return [
            ("Energy", (f"{self.energy} of {self.max_energy} left this run.")),
            ("Spent by", ("Using a card that asks for it: the shovel (digs), "
                          "the flashlight (reveals), the screwdriver (fixes) or "
                          "the hammer (breaks) costs 1 energy a use, and so do "
                          f"{spenders}.")),
            ("Refills", ("Back to full at the start of every run — restarting or "
                         "retrying a run gives the same budget again.")),
        ]


    def _action_hint(self, item, source):
        """A short hint telling the player how to act on the hovered item."""
        if source == "collection":
            # The codex is a reference: hovering one of its cells shows the very
            # info box the item gets in a game (user request), so the hint is
            # about the page rather than about the item — there is nothing to
            # press here.
            return "Codex entry | scroll to browse, RETURN TO MAIN MENU to leave"
        if source == "shop":
            # A shop offer lies on the board like any other item and is BOUGHT by
            # right-clicking it (user request); its price is only shown here, on
            # hover (see ui.info_layout), so the hint is where the player reads
            # it.
            hint = None
            if getattr(item, "kind", None) == "structure":
                # Structures are FREE (user request): there is nothing to buy, so
                # the hint is how to open one instead of what it costs.
                hint = (f"Free — arm a tool on it and press S "
                        f"({Structure.description(item.value)})")
            elif getattr(item, "kind", None) == "pack":
                hint = (f"Right-click to buy and open for ${self._buy_price(item)} "
                        f"({Pack.size_description(item.size)})")
            else:
                hint = (f"Right-click to buy for ${self._buy_price(item)} | "
                        f"click to pick it up and move it")
            # The Hoard card's middle-click pins an offer in place, and the only
            # thing that says so while the tile itself wears the unbought lock is
            # this line (see Game._toggle_shop_lock).
            if self.shop.slot_key(item) in self.shop.locked:
                hint = f"Held through the next refresh — middle-click to release | {hint}"
            return hint
        if source == "deck":
            # The deck overlay's tiles: these are the items waiting in the deck
            # (or the ones already drawn), so the hint says where the item stands
            # and how the overlay closes. While an EYEBALL pick is armed the
            # overlay is a picker, and the hint says what is pickable (see
            # Game.arm_deck_pick).
            if self.deck_pick_armed():
                if item in self.eyeball_cards():
                    return "Click to DRAW this card out of the deck with the Eyeball"
                return ("Eyeball draws a CARD — this one is not | Esc keeps the "
                        "card for later")
            drawn = self.item_cell(item) is not None
            where = ("drawn onto the board this run" if drawn
                     else "in the deck — the next draw may deal it")
            return f"{where} | click anywhere to close the deck"
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
                         f"SKIP to leave the rest")
            return hint
        if source == "tokens":
            if item.fires_at_end:
                return "Fires at the end of each run it covers (xMult)"
            return "Fires at the start of each run it covers"
        if source == "energy":
            # The bar is a resource, not an item: its hint is the one thing the
            # player needs to know when it runs dry.
            if self.energy <= 0:
                return "No energy left this run — it refills at the next run"
            return (f"{self.energy} opening{'' if self.energy == 1 else 's'} left "
                    "this run | one per tool use, refilled every run")
        if source == "board":
            if getattr(item, "kind", None) == "structure":
                return Structure.description(item.value)
            if getattr(item, "kind", None) == "tool":
                verbs = getattr(item, "verbs", None) or (item.verb,)
                return (f"{'/'.join(Verb.name(v) for v in verbs).capitalize()}: "
                        f"select it, then a structure, then press S "
                        f"({Tool.energy(item.value)} energy)")
            if getattr(item, "kind", None) == "pack":
                return "Press S to open it"
            if getattr(item, "kind", None) == "passive":
                # An UNPLAYABLE item: there is nothing to press, and saying so
                # is the whole hint (see components.Keyword).
                return (f"{Keyword.line(item).capitalize()} \u2014 click to move "
                        f"it, B to sell it")
            # Everything the player owns lies on the board, so one hint covers
            # the cards, the actions and the parts (see Game.ensure_board_cells).
            kind = getattr(item, "kind", None)
            if kind == "card":
                # A whole card is never played (see components.Keyword): the
                # hint says so, because "click to select" alone would imply
                # there is something to use it on.
                return ("Unplayable — it pays on its own | click to select, "
                        "B to sell")
            if kind == "action":
                if getattr(item, "value", None) == Action.EYEBALL:
                    return ("Press S to pick a card in your deck to draw "
                            f"({Action.energy(Action.EYEBALL)} energy)")
                if getattr(item, "value", None) == Action.HORSESHOE:
                    return ("Press S to put every item you own on the board back "
                            "in the deck and draw a bigger hand "
                            f"({Action.energy(Action.HORSESHOE)} energy)")
                if getattr(item, "value", None) == Action.RECYCLING:
                    return ("Click the item to recycle, then press S: it goes back "
                            f"in the deck and you draw "
                            f"{Action.MAGNITUDE[Action.RECYCLING]:g} "
                            f"({Action.energy(Action.RECYCLING)} energy)")
                if getattr(item, "value", None) == Action.STORMCLOUD:
                    return ("Click the structure to open, then press S: break, "
                            "fix, dig or reveal works, and the storm tears down "
                            f"a random other one "
                            f"({Action.energy(Action.STORMCLOUD)} energy)")
                if getattr(item, "value", None) == Action.FLOOR_PLANS:
                    return ("Press S to draw "
                            f"{Action.MAGNITUDE[Action.FLOOR_PLANS]:g} blocks out "
                            f"of the deck "
                            f"({Action.energy(Action.FLOOR_PLANS)} energy)")
                if Action.optional_target(getattr(item, "value", None)):
                    return ("Press S with nothing selected to open the board, "
                            "or click a structure to dig or reveal it")
                if Action.targets_structures(getattr(item, "value", None)):
                    return "Click a target structure, then press S to reroll it"
                if not Action.needs_target(getattr(item, "value", None)):
                    return "Press S to use — it needs no target"
                return "Click a target block/card, then press S to use"
            if self.is_wasteful(item):
                # Wasteful is used rather than aimed: the block is the actor and
                # the item selected behind it is what it takes with it.
                hint = ("S with one other item selected: throw both away and draw "
                        "a new item from the deck")
            elif (isinstance(item, Block)
                    or getattr(item, "placed_cell", None) is not None):
                hint = ("Click to pick the block up and move it "
                        "(V takes every block up)")
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
