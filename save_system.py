"""Save system for Marblatro.

Owns the 6 save slots (JSON text files under SAVES_DIR), the serialization of
every shop/toolbox/grid item, and the save-slot selection screen the player
sees after clicking PLAY. The game (main.py) imports the functions here and
passes the ``Game`` instance as the first argument where a function needs to
read or change game state.

- Pressing P calls ``save_game(game)`` to write the active slot.
- The title screen shows the save slots directly; its clicks live here as
  ``handle_slot_click(game, pos)`` and the slot boxes / confirm panel render as
  ``_draw_slot_box(game, index, rect)`` / ``_draw_slot_confirm(game, index)``.
"""

import json
import os
import random
import sys

import pygame

import player_paths

# main.py defines the Block/BlockItem/CardItem classes, the component enums,
# and the drawing constants used below. Reuse whichever module is actually
# running main.py — a plain `from main import ...` here would import a second,
# independent copy of main.py, which re-enters this module's import mid-way
# and raises ImportError (see physics.py for the same pattern).
if "main" in sys.modules:
    _save_source = sys.modules["main"]
elif "__main__" in sys.modules and hasattr(sys.modules["__main__"], "Block"):
    _save_source = sys.modules["__main__"]
else:  # pragma: no cover - only when save_system.py is imported on its own
    import main as _save_source

BG_COLOR = _save_source.BG_COLOR
ActionItem = _save_source.ActionItem
Block = _save_source.Block
BlockItem = _save_source.BlockItem
CardItem = _save_source.CardItem
Component = _save_source.Component
DEFAULT_DIFFICULTY = _save_source.DEFAULT_DIFFICULTY
Difficulty = _save_source.Difficulty
Effect = _save_source.Effect
GREEN = _save_source.GREEN
ItemPack = _save_source.ItemPack
PORTAL_MAX_ACTIVATIONS = _save_source.PORTAL_MAX_ACTIVATIONS
REQUIRED_SCORES = _save_source.REQUIRED_SCORES
ResourceOption = _save_source.ResourceOption
ROUND_COUNT = _save_source.ROUND_COUNT
RUNS_PER_ROUND = _save_source.RUNS_PER_ROUND
SCREEN_HEIGHT = _save_source.SCREEN_HEIGHT
SCREEN_WIDTH = _save_source.SCREEN_WIDTH
ScorerToken = _save_source.ScorerToken
Scorer = _save_source.Scorer
Shape = _save_source.Shape
Trial = _save_source.Trial
WHITE = _save_source.WHITE
del _save_source

# The 6 save slots, each a JSON text file. The player picks the active slot on
# the title screen; pressing P writes the whole game state to that slot. Tests
# redirect this, and it defaults INSIDE profiles/ (see player_paths) so the
# empty slot files a Game creates can never land beside main.py.
SAVES_DIR = player_paths.default_saves_dir()
SAVE_SLOT_COUNT = 6


def _slot_file_path(slot):
    """Absolute path to a save slot's file (slot is 1-based)."""
    return os.path.join(SAVES_DIR, f"save{slot}.txt")


def _slot_has_save(slot):
    """True when the given slot holds a real saved run (not an empty placeholder).

    Every slot's file exists (it is created empty at startup), so a slot only
    counts as occupied when its file parses to actual game data (it has cash).
    """
    data = _read_slot(slot)
    return isinstance(data, dict) and "cash" in data


def _read_slot(slot):
    """Read a slot's save dict, or None if the slot is empty/unreadable."""
    path = _slot_file_path(slot)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _serialize_effect_amounts(item):
    """A block's own effect magnitudes as a JSON-safe {effect id: magnitude} map.

    Each scaleable effect carries the strength the item was rolled with (a
    1500 px/s piston, a 2100 px/s one), so a save must keep it or a loaded
    block would silently snap back to the averages. Effect ids become strings
    because JSON object keys are strings (and are read back as ints).
    """
    amounts = getattr(item, "effect_amounts", None) or {}
    return {str(int(e)): value for e, value in amounts.items()}


def _deserialize_effect_amounts(data):
    """Read a save's effect-magnitude map back (an old save has none)."""
    return {int(e): value for e, value in (data.get("effect_amounts") or {}).items()}


def _serialize_random_rolls(item):
    """An item's pre-rolled RANDOM/LUCKY outcome, or None (see main.py).

    A Random/Lucky block or card has its reward chosen once for the run and
    kept on the item, tagged with the run it belongs to (see
    main.Game._roll_run_random_outputs / _run_random_result). Saving it means
    loading a save is never a reroll: without it the outcome would be lost on
    the way out (a loaded save draws a fresh run seed, so the block would roll
    again the next time it triggered).
    """
    rolls = getattr(item, "random_rolls", None)
    return dict(rolls) if rolls else None


def _restore_random_rolls(item, data):
    """Give a rebuilt item back the outcome a save stored for it (if any)."""
    rolls = data.get("random_rolls")
    if rolls:
        item.random_rolls = dict(rolls)
    return item


def _serialize_item(item):
    """Turn a toolbox/shop/grid item into a JSON-safe dict."""
    if isinstance(item, Block):
        return {
            "kind": "block",
            "placed": True,
            "x": item.x, "y": item.y,
            "shape": int(item.shape),
            "effects": [int(e) for e in item.effects],
            "effect_amounts": _serialize_effect_amounts(item),
            "scorer": int(item.scorer),
            "scorer_amount": float(item.scorer_amount) if item.scorer_amount is not None else None,
            "angle": int(item.angle),
            "portal_number": int(getattr(item, "portal_number", 0)),
            "key_number": int(getattr(item, "key_number", 0)),
            "trigger_limit": int(getattr(item, "trigger_limit", 1)),
            "trigger_paid": int(getattr(item, "trigger_paid", 0)),
            "spin": float(getattr(item, "spin", 0.0)),
            "triggers_left": int(getattr(item, "triggers_left", item.trigger_limit)),
            "portal_uses_left": int(getattr(item, "portal_uses_left",
                                            PORTAL_MAX_ACTIVATIONS)),
            "fragile_shape": (int(item._fragile_shape)
                              if getattr(item, "_fragile_shape", None) is not None else None),
            # The price the block was placed with: a loaded block is never
            # repriced from its parts (see main.block_resale_price).
            "resale_price": getattr(item, "resale_price", None),
            # This run's RANDOM/LUCKY outcome, so loading cannot reroll it.
            "random_rolls": _serialize_random_rolls(item),
        }
    kind = getattr(item, "kind", None)
    if kind == "block":
        return {
            "kind": "block",
            "placed": False,
            "col": item.col, "row": item.row,
            "shape": int(item.shape),
            "effects": [int(e) for e in item.effects],
            "effect_amounts": _serialize_effect_amounts(item),
            "scorer": int(item.scorer),
            "scorer_amount": float(item.scorer_amount) if item.scorer_amount is not None else None,
            "price": int(item.price),
            "name": item.name,
            "portal_number": int(getattr(item, "portal_number", 0)),
            "key_number": int(getattr(item, "key_number", 0)),
            "trigger_limit": int(getattr(item, "trigger_limit", 1)),
            "trigger_paid": int(getattr(item, "trigger_paid", 0)),
            # A block erased to the toolbox carries the triggers it had left,
            # this run's RANDOM/LUCKY outcome (see main._refund_block) and the
            # rotation it had, so putting it back down after a save is still a
            # move in every respect. A shop block has no angle of its own.
            "angle": (None if getattr(item, "angle", None) is None
                      else int(item.angle)),
            "triggers_left": (int(item.triggers_left)
                              if getattr(item, "triggers_left", None) is not None
                              else None),
            "random_rolls": _serialize_random_rolls(item),
        }
    if kind == "card":
        return {
            "kind": "card",
            "value": int(item.value),
            "price": int(item.price),
            # The card's own scorer magnitude (a composed card pays, prices and
            # describes itself with it); 0 for a whole card.
            "amount": getattr(item, "amount", 0),
            "col": item.col, "row": item.row,
            "name": item.name,
            # This run's RANDOM/LUCKY outcome (see _serialize_random_rolls).
            "random_rolls": _serialize_random_rolls(item),
        }
    if kind == "action":
        return {
            "kind": "action",
            "value": int(item.value),
            "price": int(item.price),
            "version": int(getattr(item, "version", 1)),
            "col": item.col, "row": item.row,
            "name": item.name,
        }
    if kind == "resource":
        # A resource pack option: points of one scorer, at the magnitude the
        # option rolled (the points themselves are stored, so a save cannot
        # reroll what the option is worth).
        return {
            "kind": "resource",
            "scorer": int(item.scorer),
            "amount": float(item.amount),
            "points": float(item.points),
            "name": item.name,
        }
    if kind == "pack":
        # A pack, with everything it holds: the shop's pack slots and a pack the
        # player is in the middle of choosing from are the same object (see
        # Game.open_pack), so one branch covers both.
        return {
            "kind": "pack",
            "pack_type": int(item.pack_type),
            "size": int(item.size),
            "keep": int(item.keep),
            "kept": int(item.kept),
            "price": int(item.price),
            "col": item.col, "row": item.row,
            "name": item.name,
            "options": [_serialize_item(option) for option in item.options],
        }
    # A Component (shape/effect/scorer piece).
    return {
        "kind": item.kind,
        "value": int(item.value),
        "amount": float(item.amount) if item.amount else 0,
        "price": int(item.price),
        "name": item.name,
        "col": item.col, "row": item.row,
    }


def _deserialize_item(data):
    """Rebuild a toolbox/shop/grid item from a serialized dict."""
    if data["kind"] == "resource":
        return ResourceOption(data["scorer"], data.get("amount", 0),
                              data.get("points", 0))
    if data["kind"] == "pack":
        return ItemPack(data["pack_type"], data["size"],
                        [_deserialize_item(option)
                         for option in data.get("options", [])],
                        data.get("price", 0),
                        col=data.get("col", 0), row=data.get("row", 0),
                        keep=data.get("keep"),
                        kept=data.get("kept", 0))
    if data["kind"] == "card":
        return _restore_random_rolls(
            CardItem(data["value"], data.get("price", 20),
                     col=data.get("col", 0), row=data.get("row", 0),
                     amount=data.get("amount", 0)), data)
    if data["kind"] == "action":
        return ActionItem(data["value"], data.get("price", 60),
                          version=data.get("version", 1),
                          col=data.get("col", 0), row=data.get("row", 0))
    if data["kind"] == "block":
        if data.get("placed"):
            block = Block(
                data["x"], data["y"],
                shape=data["shape"],
                effect=Effect.NONE,
                scorer=data["scorer"],
                scorer_amount=data.get("scorer_amount"),
                angle=data.get("angle", 0),
                portal_number=data.get("portal_number", 0),
                key_number=data.get("key_number", 0),
                trigger_limit=data.get("trigger_limit", 1),
                trigger_paid=data.get("trigger_paid", 0),
                effects=data.get("effects") or [Effect.NONE],
                effect_amounts=_deserialize_effect_amounts(data),
            )
            block.spin = data.get("spin", 0.0)
            block._refresh_geometry()  # include the restored spin
            block.triggers_left = data.get("triggers_left", block.trigger_limit)
            block.portal_uses_left = data.get("portal_uses_left",
                                              PORTAL_MAX_ACTIVATIONS)
            block._fragile_shape = data.get("fragile_shape")
            # The price it was placed with; a save from before this was stored
            # leaves it unset, and the first read materializes one (see
            # main.block_resale_price).
            block.resale_price = data.get("resale_price")
            return _restore_random_rolls(block, data)
        item = BlockItem(
            data.get("col", 0), data.get("row", 0),
            data["shape"], data.get("effect", Effect.NONE), data["scorer"],
            data.get("scorer_amount", 0), data.get("price", 0), data.get("name", ""),
            portal_number=data.get("portal_number", 0),
            key_number=data.get("key_number", 0),
            trigger_limit=data.get("trigger_limit", 1),
            trigger_paid=data.get("trigger_paid", 0),
            effects=data.get("effects") or [Effect.NONE],
            effect_amounts=_deserialize_effect_amounts(data),
            angle=data.get("angle"),
        )
        # A block refunded to the toolbox keeps what it had left (see
        # main._refund_block); a save from before this simply has none.
        if data.get("triggers_left") is not None:
            item.triggers_left = int(data["triggers_left"])
        return _restore_random_rolls(item, data)
    return Component(
        data["kind"], data["value"],
        amount=data.get("amount", 0),
        price=data.get("price", 0),
        name=data.get("name", ""),
        col=data.get("col", 0),
        row=data.get("row", 0),
    )


def ensure_saves():
    """Create the saves folder and its 6 empty slot files if missing."""
    os.makedirs(SAVES_DIR, exist_ok=True)
    for slot in range(1, SAVE_SLOT_COUNT + 1):
        path = _slot_file_path(slot)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 1}, f)


def _serialize_trial_decision(game):
    """The run's decided trial picks as a JSON-safe dict, or None.

    A trial decides every random choice it makes ONCE for the run (which cells
    Hands tied debuffs, which slot Card cutter cuts, the order Shuffled leaves
    the cards in, which cells Crumbling makes fragile, Marble weight's heavier
    or lighter factor, which way Vertigo pulls gravity — see
    main.Game._roll_trial_decision) and then replays that decision, so it has to
    ride through a save: without it, loading the save would hand the player a
    free reroll of the very picks a replay is not allowed to change.

    The picks are stored the way they are held: cells as [x, y] pairs, the
    Shuffled order as card-area SLOT numbers (the card items themselves are
    rebuilt on load, so a slot is what keeps pointing at the same card), and
    Vertigo's direction as an index into main.VERTIGO_DIRECTIONS.
    """
    decision = getattr(game, "trial_decision", None)
    if not decision:
        return None
    out = {"trial": (None if decision.get("trial") is None
                     else int(decision["trial"]))}
    if "cells" in decision:
        out["cells"] = [[int(x), int(y)] for x, y in sorted(decision["cells"])]
    if "card_index" in decision:
        out["card_index"] = int(decision["card_index"])
    if "order" in decision:
        out["order"] = [game.cards.index(card) for card in decision["order"]
                        if card in game.cards]
    if "weight" in decision:
        out["weight"] = decision["weight"]
    if "gravity" in decision:
        out["gravity"] = int(decision["gravity"])
    return out


def _restore_trial_decision(data, game):
    """Read a save's decided trial picks back (an old save has none).

    Called AFTER the save's cards are rebuilt: the Shuffled order is stored as
    card-area slots, so it is pointed back at the loaded card items here.
    """
    saved = data.get("trial_decision")
    if not saved:
        return None
    decision = {"trial": saved.get("trial")}
    if "cells" in saved:
        decision["cells"] = {(int(x), int(y)) for x, y in saved["cells"]}
    if "card_index" in saved:
        decision["card_index"] = int(saved["card_index"])
    if "order" in saved:
        decision["order"] = [game.cards[index] for index in saved["order"]
                             if 0 <= index < len(game.cards)]
    if "weight" in saved:
        decision["weight"] = saved["weight"]
    if "gravity" in saved:
        decision["gravity"] = int(saved["gravity"])
    return decision


def _save_data(game):
    """Collect the game's whole persistent state into a JSON-safe dict.

    Records the current trial, the toolbox and marble-box blocks, the round/run
    plus which runs were passed/lost, owned cards, cash, and the shop's current
    options (plus the component-purchase counts that drive shop prices).
    """
    return {
        "version": 1,
        "cash": game.cash,
        "run_number": game.run_number,
        "round_index": game.round_index,
        "run_in_round": game.run_in_round,
        "required_score": game.required_score,
        # True while an ACTION owns this run's target (Grace v2's 0), so loading
        # does not re-derive it from the schedule (see _refresh_run_target).
        "target_forced": bool(game.target_forced),
        "required_scores": list(REQUIRED_SCORES),
        "run_results": list(game.run_results),
        "runs_cleared": game.runs_cleared,
        "failed_runs": game.failed_runs,
        "current_trial": (int(game.current_trial)
                          if game.current_trial is not None else None),
        # The trial's decided random picks for this run (see
        # _serialize_trial_decision): loading a save must not reroll them.
        "trial_decision": _serialize_trial_decision(game),
        # The save's difficulty (chosen when it was started): how many of a
        # round's runs play a trial and the score growth per run.
        "difficulty": int(game.difficulty),
        "cards": [_serialize_item(c) for c in game.cards],
        "actions": [_serialize_item(a) for a in game.actions],
        "toolbox": [_serialize_item(i) for i in game.toolbox.items],
        "grid": [_serialize_item(b) for b in game.grid.values()],
        "shop": [_serialize_item(i) for i in game.shop.items],
        # The pack the player is choosing from, if any (it has already left the
        # shelf, so it is saved on its own — see Game.open_pack), and the action
        # an action pack armed for immediate use (see Game.pending_pack_action).
        "open_pack": (_serialize_item(game.open_pack)
                      if game.open_pack is not None else None),
        "pending_pack_action": (_serialize_item(game.pending_pack_action)
                                if getattr(game, "pending_pack_action", None)
                                is not None else None),
        # The shop offers the Hoard whole card is holding, as the CELLS they
        # were held in (see main.Shop.slot_key): the offers themselves are
        # already in the key above, so this is what keeps them held through a
        # load rather than merely on the shelf.
        "shop_locked": [list(slot) for slot in game.shop.locked],
        "component_purchases": [[k, v, c] for (k, v), c in game.component_purchases.items()],
        # Fragile Breaks (Wrecking Ball) permanent bonuses, one per unit scorer
        # (chips/mult add; the xMult bonus is a multiplicative factor).
        "wrecking_bonus": [[int(s), game.wrecking_bonus[s]]
                           for s in game.wrecking_bonus],
        # Tesseract's permanent reroll bonus: an xMult factor (starts at 1.0).
        "tesseract_bonus": game.tesseract_bonus,
        # Spirit tokens: each is a whole kept block plus the runs it has left
        # (None = permanent, a v2 Spirit), stored as an item dict so the block
        # comes back exactly as it was (see _serialize_item).
        "tokens": [{"block": _serialize_item(t.block),
                    "runs_left": (None if t.runs_left is None
                                  else int(t.runs_left))}
                   for t in game.tokens],
        "shred_points": game.shred_points,
        "rubble_points": game.rubble_points,
        "idea_points": game.idea_points,
        "free_rerolls": game.free_rerolls,
        "option_points": game.option_points,
        "bonus_slots": game.bonus_slots,
        # The slots cards and actions have won: Inaction's banked uses (every
        # INACTION_USES_PER_SLOT of them is a card slot, and a v2 use hands one
        # over outright), Foresight's action slots, and whether its v2 has
        # removed the action limit altogether. All permanent for the game.
        "inaction_used": game.inaction_used,
        "card_slots_won": game.card_slots_won,
        "inventory_slots_won": game.inventory_slots_won,
        # Whether the player has ever sold a card. Not a run or trial effect:
        # the Deal breaker trial's gag checks it (see Game._deal_breaker_gags),
        # so keeping it in the save is what stops a reload from gagging a board
        # the player has already freed.
        "card_sold": game.card_sold,
        "action_slots_won": game.action_slots_won,
        "action_slots_unlimited": game.action_slots_unlimited,
        # Odyssey's banked items, as whole items (see _serialize_item), in the
        # order they were put away: they are out of the inventory until the run
        # they are waiting out is continued, so a save has to keep them.
        "inaccessible": [_serialize_item(i) for i in game.inaccessible],
        # Action bonuses (see Game._action_mass_production / _action_brainstorm
        # / _action_grace): Mass production's factor for the run being played
        # and its permanent one, Brainstorm's reroll-price factor, and the
        # xMult Grace banked for that run.
        "resource_gain_mult": game.resource_gain_mult,
        "resource_gain_bonus": game.resource_gain_bonus,
        "reroll_discount": game.reroll_discount,
        "run_xmult_bonus": game.run_xmult_bonus,
        "marble_type": game.marble_type,
        "upgrades_enabled": game.upgrades_enabled,
        "game_over": game.game_over,
        "game_won": game.game_won,
        "game_perfect": game.game_perfect,
        "continue_past_game_over": game.continue_past_game_over,
        "score_chips": game.score_chips,
        "score_mult": game.score_mult,
        "last_run_cash_gained": game.last_run_cash_gained,
        # Where that cash came from (base/interest/score/cards/scorers), shown
        # when the player hovers the shop's cash readout.
        "last_run_cash_breakdown": dict(getattr(game, "last_run_cash_breakdown", {})),
        # The dynamic board's unlocked squares (which parts of the board the
        # marble can reach) persist, so a partially-locked board stays locked
        # after a save/load instead of snapping back to fully unlocked.
        "unlocked_cells": [list(c) for c in game.unlocked_cells],
        # Board Units still in hand (each buys one locked square) persist too.
        "board_units": game.board_units,
    }


def save_game(game, announce=True):
    """Write the game's state to its active slot (the P key).

    ``announce`` is cleared by the AUTOSAVE (see Game._tick_autosave): the
    autosave is not something the player did, and a "Saved to slot N" message
    every 30 seconds would sit over the shop.
    """
    slot = game.save_slot if game.save_slot is not None else 1
    game.save_slot = slot
    ensure_saves()
    with open(_slot_file_path(slot), "w", encoding="utf-8") as f:
        json.dump(_save_data(game), f, indent=2)
    if announce:
        game._set_shop_message(f"Saved to slot {slot}")


def load_slot(game, slot):
    """Load the given slot's saved run (1-based), or start fresh if empty."""
    data = _read_slot(slot)
    if data is None or "cash" not in data:
        start_new_game_in_slot(game, slot)
        return
    _load_save_data(game, data, slot)


def _load_save_data(game, data, slot):
    """Restore a saved game state (a slot's dict) into the given Game."""
    game.reset_game()  # a clean base; every field below is overwritten
    game.save_slot = slot
    # The board's unlocked squares and Board Units in hand persist (a loaded
    # save keeps the board exactly as it was locked/unlocked). Old saves made
    # before the dynamic board have no such key, so they keep reset_game's
    # fully-unlocked default. reset_game (above) just wiped the wall cache, so
    # mark it dirty to rebuild around the restored locked squares.
    cells = data.get("unlocked_cells")
    if cells is not None:
        game.unlocked_cells = {tuple(c) for c in cells}
        game._board_walls_dirty = True
    game.board_units = data.get("board_units", 0)
    game.cash = data.get("cash", game.cash)
    game.run_number = data.get("run_number", 0)
    game.round_index = data.get("round_index", 0)
    game.run_in_round = data.get("run_in_round", 0)
    game.required_score = data.get("required_score", game.required_score)
    game.target_forced = bool(data.get("target_forced", False))
    # The lazily-grown required-score schedule persists so a loaded game
    # continues the same targets. reset_game (called above) clears it first;
    # a fresh game keeps the clean [1] default.
    REQUIRED_SCORES[:] = data.get("required_scores", [1])
    game.run_results = list(data.get("run_results", []))
    game.runs_cleared = data.get("runs_cleared", sum(game.run_results))
    game.failed_runs = data.get("failed_runs", len(game.run_results) - sum(game.run_results))
    game.game_over = data.get("game_over", False)
    game.game_won = data.get("game_won", False)
    game.game_perfect = data.get("game_perfect", False)
    game.continue_past_game_over = data.get("continue_past_game_over", False)
    game.score_chips = data.get("score_chips", 1)
    game.score_mult = data.get("score_mult", 1)
    game.last_run_cash_gained = data.get("last_run_cash_gained", 0)
    game.last_run_cash_breakdown = dict(data.get("last_run_cash_breakdown", {}))
    game.current_trial = data.get("current_trial")
    game.component_purchases = {}
    for k, v, c in data.get("component_purchases", []):
        game.component_purchases[(k, v)] = c
    # Fragile Breaks (Wrecking Ball) permanent bonuses persist across saves:
    # chips/mult are added, xMult is a factor that multiplies (starts at 1.0).
    game.wrecking_bonus = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                           Scorer.MULT_MUL: 1.0}
    for _s, _v in data.get("wrecking_bonus", []):
        game.wrecking_bonus[int(_s)] = _v
    # Tesseract's permanent reroll bonus persists too (a factor; 1.0 when the
    # save predates the card).
    game.tesseract_bonus = data.get("tesseract_bonus", 1.0)
    # Spirit tokens persist: each keeps the whole block it was made from, so a
    # save from before tokens stored their block (a plain [scorer, amount,
    # shape, effects, x, y, runs_left] list) is read back into one.
    game.tokens = []
    for entry in data.get("tokens", []):
        if isinstance(entry, dict):
            game.tokens.append(ScorerToken(
                _deserialize_item(entry["block"]),
                runs_left=entry.get("runs_left")))
            continue
        _s, _a, _sh, _ef, _x, _y, _runs = entry
        game.tokens.append(ScorerToken(
            Block(_x, _y, shape=_sh, effect=Effect.NONE, scorer=_s,
                  scorer_amount=_a, effects=_ef),
            runs_left=None if _runs < 0 else _runs))
    # Resource points from Shreds/Rubble/Ideas scorers persist too, as do free
    # rerolls (granted by Fresh) and Picky points / bonus shop slots. A legacy
    # part_points key from before Parts granted components directly is ignored.
    game.shred_points = data.get("shred_points", 0)
    game.rubble_points = data.get("rubble_points", 0)
    game.idea_points = data.get("idea_points", 0)
    game.free_rerolls = data.get("free_rerolls", 0)
    game.option_points = data.get("option_points", 0)
    game.bonus_slots = data.get("bonus_slots", 0)
    game.shop.bonus_slots = game.bonus_slots
    # The gained slots (Inaction's uses and handed-over slots, Foresight's
    # action slots and its unlimited flag, Packed's inventory slots) persist; a
    # save written before any of them existed simply has none of them.
    game.inaction_used = data.get("inaction_used", 0)
    game.card_slots_won = data.get("card_slots_won", 0)
    game.inventory_slots_won = data.get("inventory_slots_won", 0)
    game.inventory_slots_run_gain = 0
    game.toolbox.slot_bonus = game.inventory_slots_won
    # A sale recorded before the save keeps the Deal breaker trial beaten, so a
    # save written before the record existed just reads as "never sold".
    game.card_sold = data.get("card_sold", False)
    game.action_slots_won = data.get("action_slots_won", 0)
    game.action_slots_unlimited = data.get("action_slots_unlimited", False)
    game.action_area_page = 0
    # The action bonuses above: a save written before they existed reads as an
    # untouched game (no factor, full reroll price, no banked xMult).
    game.resource_gain_mult = data.get("resource_gain_mult", 1.0)
    game.resource_gain_bonus = data.get("resource_gain_bonus", 1.0)
    game.reroll_discount = data.get("reroll_discount", 1.0)
    game.run_xmult_bonus = data.get("run_xmult_bonus", 0.0)
    # The marble type chosen for this save (one per save).
    game.marble_type = data.get("marble_type", 0)
    # The save's difficulty (see Difficulty): how many of a round's runs play a
    # trial and how fast the required score grows. A save written before the
    # difficulty existed reads as the game's original balance.
    game.difficulty = data.get("difficulty", DEFAULT_DIFFICULTY)
    # Whether the permanent upgrade effects apply to this save's runs.
    game.upgrades_enabled = data.get("upgrades_enabled", True)
    # The trial's applied effects re-apply when a run starts, so the state they
    # derive is cleared here. The DECIDED picks they derive from are not: a
    # trial decides every random choice it makes once for the run (see
    # main.Game._roll_trial_decision) and then replays it, so dropping the
    # decision on load would be a free reroll. It is restored below, once the
    # save's cards are back (a Shuffled order is stored as card-area slots and
    # has to be pointed at the rebuilt cards). The run SEED is drawn afresh
    # instead: the run is being set up again from the save, so its IN-PLAY dice
    # (the 8 ball's retriggers, a Glitch card's random mult) roll anew rather
    # than staying tied to the choices the (unloaded) session had made. The
    # rewards an item already rolled are not dropped either: a Random/Lucky
    # block, card or Spirit token carries its own outcome through the save (see
    # _serialize_random_rolls), so loading is never a reroll of a reward the
    # player could already see.
    game.trial_debuffed_blocks = set()
    game.disabled_card = None
    game.trial_fragile_blocks = set()
    game.trial_marble_weight = 1.0
    # Nothing of the deal-breaker gag is cleared here on purpose: whether the
    # player has sold a card is restored from the save (see card_sold, restored
    # with the other permanent gains), so a load cannot re-gag a board a sale
    # has already freed.
    game.trial_gravity_dir = None
    for card in game.cards:
        card.flipped = False
    game.trial_decision = None
    game.run_seed = random.randrange(1 << 31)
    game.run_rng = random.Random(game.run_seed)
    game.touch_shape_counts = {}
    game.touch_effect_counts = {}
    game.touch_scorer_counts = {}
    # Rebuild the owned/shop collections from the save.
    game.toolbox.items = [_deserialize_item(d) for d in data.get("toolbox", [])]
    # Odyssey's banked items come back before anything asks the toolbox for
    # room (see Game._return_inaccessible), and a save written before the card
    # existed banks nothing.
    game.inaccessible = [_deserialize_item(d) for d in data.get("inaccessible", [])]
    game.shop.items = [_deserialize_item(d) for d in data.get("shop", [])]
    game.cards = [_deserialize_item(d) for d in data.get("cards", [])]
    game.actions = [_deserialize_item(d) for d in data.get("actions", [])]
    # The shelf's CELLS belong to the layout rather than to the save: re-seat the
    # offers the save hands back, so a save written under a different shelf — an
    # older one, or one whose offers all sat in a single row — cannot bring
    # offers back in cells this layout does not have, drawn over the cash header
    # or past the panel's edge (see Shop.reseat).
    reseated = game.shop.reseat()
    # The Hoard card's held shop offers come back with the shop: a save written
    # before the card existed holds nothing, and the holds are clipped once the
    # cards are back, so a hold can never outlive the Hoard that pays for it
    # (see Game.shop_lock_cap). A hold follows the offer it holds to that offer's
    # new cell, so the reroll it was pinned against still finds it.
    held = [(int(slot[0]), int(slot[1]))
            for slot in data.get("shop_locked", [])]
    game.shop.locked = [reseated.get(cell, cell) for cell in held]
    game._clip_shop_locks()
    # A pack the player was choosing from comes back open, with the options it
    # had left, and the action an action pack armed comes back armed (both are
    # saved on their own — see Game.open_pack / pending_pack_action).
    open_pack = data.get("open_pack")
    game.open_pack = _deserialize_item(open_pack) if open_pack else None
    pending = data.get("pending_pack_action")
    game.pending_pack_action = _deserialize_item(pending) if pending else None
    if game.pending_pack_action is not None:
        # The armed action is the selected one again, so S picks up where the
        # save left off (see Game._keep_action_from_pack).
        game.selected_action = game.pending_pack_action
    game.grid = {}
    for d in data.get("grid", []):
        block = _deserialize_item(d)
        game.grid[(block.x, block.y)] = block
    # The decided trial picks come back now that the items above exist: a
    # Shuffled order is stored as card-area slots and is resolved against the
    # loaded cards here (see _restore_trial_decision).
    game.trial_decision = _restore_trial_decision(data, game)
    # Pairing numbers (Key/Lock and Portal) are handed out by a counter that
    # lives in the running game while the numbers themselves live in this save,
    # so the loaded board claims its numbers before any new pair is built:
    # otherwise a pair bought after a reload reuses a number the save already
    # has and one key opens the locks of two different pairs (see
    # Game._adopt_pairing_numbers).
    game._adopt_pairing_numbers()
    # A loaded game starts in the build state: no active run.
    game.marbles = []
    game.run_active = False
    game.run_complete = False
    game.run_cleared = False
    game.awaiting_after_run = False
    game.run_time = 0.0
    game.assigned_toolbox_indexes = {}
    game._clear_toolbox_selection()


def wipe_slot(game, slot):
    """Delete a slot's save and start a brand-new game in it."""
    path = _slot_file_path(slot)
    if os.path.exists(path):
        os.remove(path)
    start_new_game_in_slot(game, slot)


def start_new_game_in_slot(game, slot):
    """Start a fresh game assigned to the given slot (no save written yet)."""
    game.reset_game()
    # Every new game begins with the board locked to its starting centered 2x2
    # region; buying Board Units unlocks squares. (Starting a NEW game always
    # resets the board to this 2x2 start — an existing game's unlocked state is
    # only restored when its slot is loaded, not when another game begins.)
    game._reset_board_to_start()
    game.save_slot = slot
    game.slot_confirm_index = None
    game.title_screen = False


def begin_new_game_selection(game, slot):
    """Start a brand-new save in ``slot``: clear any existing save and open the
    new-save screen, where the player picks the save's difficulty and marble
    type and whether permanent upgrade effects apply (on by default)."""
    path = _slot_file_path(slot)
    if os.path.exists(path):
        os.remove(path)
    game.save_slot = slot
    game.slot_confirm_index = None
    game.title_screen = False
    game.marble_selecting = True
    game.upgrades_enabled = True  # a fresh save defaults to upgrades on
    game.difficulty = DEFAULT_DIFFICULTY  # and to the picker's default level


def start_new_game_with_marble(game, marble_type):
    """Start the pending fresh game (in ``game.save_slot``) using the marble type.

    ``start_new_game_in_slot`` resets the game (which turns upgrades back on and
    the difficulty back to its default), so the new-save screen's upgrade
    toggle and difficulty pick are restored afterward.
    """
    slot = game.save_slot if game.save_slot is not None else 1
    upgrades_enabled = game.upgrades_enabled
    difficulty = game.difficulty
    start_new_game_in_slot(game, slot)
    game.marble_type = marble_type
    game.upgrades_enabled = upgrades_enabled
    game.difficulty = difficulty
    game.marble_selecting = False


def handle_slot_click(game, pos):
    """Route a click on the title screen's save slots (or confirm panel)."""
    if game.slot_confirm_index is not None:
        slot = game.slot_confirm_index + 1
        if slot_load_button_rect().collidepoint(pos):
            load_slot(game, slot)
            game.title_screen = False  # a loaded game leaves the title screen
            game.slot_confirm_index = None
        elif slot_wipe_button_rect().collidepoint(pos):
            begin_new_game_selection(game, slot)
        elif slot_back_button_rect().collidepoint(pos):
            game.slot_confirm_index = None
        return
    for i in range(SAVE_SLOT_COUNT):
        if slot_rect(i).collidepoint(pos):
            if _slot_has_save(i + 1):
                game.slot_confirm_index = i
            else:
                begin_new_game_selection(game, i + 1)
            return


def slot_rect(index):
    """The screen rect for a save slot (index 0..5) on the slot screen."""
    cols = 2
    slot_w, slot_h = 280, 100
    gap_x, gap_y = 30, 30
    total_w = cols * slot_w + gap_x
    x0 = (SCREEN_WIDTH - total_w) // 2
    y0 = 180
    col = index % cols
    row = index // cols
    return pygame.Rect(x0 + col * (slot_w + gap_x), y0 + row * (slot_h + gap_y), slot_w, slot_h)


def slot_load_button_rect():
    """The LOAD button on a slot's confirm panel."""
    return pygame.Rect(SCREEN_WIDTH // 2 - 220, 470, 200, 48)


def slot_wipe_button_rect():
    """The WIPE & NEW button on a slot's confirm panel."""
    return pygame.Rect(SCREEN_WIDTH // 2 + 20, 470, 200, 48)


def slot_back_button_rect():
    """The BACK button on a slot's confirm panel."""
    return pygame.Rect(SCREEN_WIDTH // 2 - 90, 560, 180, 36)


def _draw_slot_box(game, index, rect):
    """Draw one save slot's box on the slot-select screen."""
    has = _slot_has_save(index + 1)
    data = _read_slot(index + 1)
    if has:
        pygame.draw.rect(game.screen, (35, 40, 60), rect, border_radius=10)
        pygame.draw.rect(game.screen, (255, 215, 0), rect, 3, border_radius=10)
    else:
        pygame.draw.rect(game.screen, (25, 25, 35), rect, border_radius=10)
        pygame.draw.rect(game.screen, (120, 120, 130), rect, 3, border_radius=10)
    slot_label = game.required_font.render(f"SLOT {index + 1}", True, WHITE)
    game.screen.blit(slot_label, (rect.x + 14, rect.y + 10))
    if has and data is not None:
        line1 = game.small_font.render(
            f"Round {data.get('round_index', 0) + 1}/{ROUND_COUNT}  "
            f"Run {data.get('run_in_round', 0) + 1}/{RUNS_PER_ROUND}",
            True, (200, 200, 200))
        line2 = game.small_font.render(f"Cash ${data.get('cash', 0)}", True, GREEN)
        line3 = game.small_font.render(
            f"Trial: {Trial.name(data['current_trial']) if data.get('current_trial') is not None else 'None'}"
            f"  •  Diff {data.get('difficulty', DEFAULT_DIFFICULTY)}",
            True, (200, 200, 200))
        game.screen.blit(line1, (rect.x + 14, rect.y + 34))
        game.screen.blit(line2, (rect.x + 14, rect.y + 54))
        game.screen.blit(line3, (rect.x + 14, rect.y + 74))
    else:
        empty = game.tiny_font.render("Empty — click to start a new run", True, (150, 150, 160))
        game.screen.blit(empty, (rect.x + 14, rect.y + 52))


def _draw_slot_confirm(game, index):
    """Draw the confirm panel for a non-empty slot (LOAD / WIPE & NEW)."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    game.screen.blit(overlay, (0, 0))
    panel = pygame.Rect(SCREEN_WIDTH // 2 - 260, 180, 520, 360)
    pygame.draw.rect(game.screen, (30, 30, 45), panel, border_radius=14)
    pygame.draw.rect(game.screen, (255, 215, 0), panel, 3, border_radius=14)
    heading = game.total_font.render(f"SLOT {index + 1}", True, WHITE)
    game.screen.blit(heading, heading.get_rect(center=(panel.centerx, panel.top + 44)))
    data = _read_slot(index + 1)
    if data is not None:
        trial_name = (Trial.name(data['current_trial'])
                      if data.get('current_trial') is not None else 'None')
        # The difficulty line spells its two knobs out rather than the level's
        # full description, which is too wide for the panel.
        level = data.get('difficulty', DEFAULT_DIFFICULTY)
        trials = Difficulty.trials_per_round(level)
        lines = [
            (f"Round {data.get('round_index', 0) + 1}/{ROUND_COUNT}  "
             f"Run {data.get('run_in_round', 0) + 1}/{RUNS_PER_ROUND}"),
            f"Cash ${data.get('cash', 0)}",
            f"Runs passed {data.get('runs_cleared', 0)}  •  failed {data.get('failed_runs', 0)}",
            f"Trial: {trial_name}",
            (f"Difficulty {level}: {trials} trial{'' if trials == 1 else 's'} "
             f"a round, {Difficulty.score_growth(level):g}x targets"),
        ]
        y = panel.top + 120
        for line in lines:
            surf = game.font.render(line, True, (220, 220, 220))
            game.screen.blit(surf, surf.get_rect(midtop=(panel.centerx, y)))
            y += 30
    load_btn = slot_load_button_rect()
    pygame.draw.rect(game.screen, (40, 160, 40), load_btn)
    pygame.draw.rect(game.screen, WHITE, load_btn, 2)
    load_text = game.font.render("LOAD", True, WHITE)
    game.screen.blit(load_text, load_text.get_rect(center=load_btn.center))
    wipe_btn = slot_wipe_button_rect()
    pygame.draw.rect(game.screen, (180, 40, 40), wipe_btn)
    pygame.draw.rect(game.screen, WHITE, wipe_btn, 2)
    wipe_text = game.font.render("WIPE & NEW", True, WHITE)
    game.screen.blit(wipe_text, wipe_text.get_rect(center=wipe_btn.center))
    back_btn = slot_back_button_rect()
    pygame.draw.rect(game.screen, (60, 60, 80), back_btn)
    pygame.draw.rect(game.screen, WHITE, back_btn, 2)
    back_text = game.small_font.render("BACK", True, WHITE)
    game.screen.blit(back_text, back_text.get_rect(center=back_btn.center))
