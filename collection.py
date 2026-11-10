"""Collection codex: the cards, actions, components, packs and trials the player
has seen.

A card, action, component or pack is discovered the first time the player buys
it (a pack by its TYPE: its size is not a separate entry); a trial is discovered
the first time a run with it is beaten. Discoveries are persisted per profile in
``collection.json`` inside the active profile's folder (see ``profiles``), not
per save slot. In the collection tab, undiscovered entries show "???" instead of
their name/description/icon.
"""

import json

import components
import player_paths

# Where the discovered set lives. Tests redirect this, and it defaults INSIDE
# profiles/ (see player_paths) so a write from a tool that has not activated a
# profile can never land beside main.py.
FILE_PATH = player_paths.default_file("collection.json")

# The Start and Finish scorers are RUN ROLES rather than things to discover:
# every game hands the player a Start block and a Finish block, so their
# collection entries are always known. Reading them as discovered (rather than
# writing them to the file) keeps BUILDING a Game — which happens in tests,
# tools and probes as well as in play — from touching the player's data.
ALWAYS_DISCOVERED_COMPONENTS = frozenset({
    (components.Component.SCORER, components.Scorer.START),
    (components.Component.SCORER, components.Scorer.FINISH),
})

# The four STARTER tools are the same kind of thing: every game deals them into
# the first hand (see components.Tool.STARTERS), so the player has seen them
# before they ever open the codex. Read as discovered rather than written to the
# file, for the same reason as the two role scorers above.
ALWAYS_DISCOVERED_TOOLS = frozenset(components.Tool.STARTERS)

_DATA = None  # {"cards": set, "actions": set, "components": set of (kind, value), "match_groups": set, "packs": set, "trials": set, "tools": set, "passives": set, "structures": set}


def _empty():
    """The shape of the discovered set: one set per codex SECTION.

    Every kind of item the game can put in a player's hands has a section of
    its own -- the components a block is made of, whole cards, match groups,
    actions, packs, trials, and the three kinds that are items in their own
    right: TOOLS (the verbs), PASSIVES (unplayable items) and STRUCTURES (what
    the level stands on the board). A kind with no section here could never
    appear in the collection, which is what "make sure all items are in the
    collection" asks for.
    """
    return {"cards": set(), "actions": set(), "components": set(),
            "match_groups": set(), "packs": set(), "trials": set(),
            "tools": set(), "passives": set(), "structures": set()}


def _load():
    """Load the discovered set from disk once (lazily)."""
    global _DATA
    if _DATA is not None:
        return
    _DATA = _empty()
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _DATA["cards"] = set(data.get("cards", []))
        _DATA["actions"] = set(data.get("actions", []))
        _DATA["components"] = {(k, v) for k, v in data.get("components", [])}
        _DATA["match_groups"] = set(data.get("match_groups", []))
        _DATA["packs"] = set(data.get("packs", []))
        _DATA["trials"] = set(data.get("trials", []))
        _DATA["tools"] = set(data.get("tools", []))
        _DATA["passives"] = set(data.get("passives", []))
        _DATA["structures"] = set(data.get("structures", []))
    except (OSError, ValueError):
        pass


def _save():
    """Write the discovered set to disk."""
    player_paths.ensure_parent(FILE_PATH)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "cards": sorted(_DATA["cards"]),
            "actions": sorted(_DATA["actions"]),
            "components": sorted([list(c) for c in _DATA["components"]]),
            "match_groups": sorted(_DATA["match_groups"]),
            "packs": sorted(_DATA["packs"]),
            "trials": sorted(_DATA["trials"]),
            "tools": sorted(_DATA["tools"]),
            "passives": sorted(_DATA["passives"]),
            "structures": sorted(_DATA["structures"]),
        }, f)


def reset():
    """Forget everything (used by tests for isolation)."""
    global _DATA
    _DATA = None


def discover_card(value):
    """Record a bought card; returns True only if it was newly discovered."""
    _load()
    if value in _DATA["cards"]:
        return False
    _DATA["cards"].add(value)
    _save()
    return True


def discover_action(value):
    """Record a bought action; returns True only if it was newly discovered."""
    _load()
    if value in _DATA["actions"]:
        return False
    _DATA["actions"].add(value)
    _save()
    return True


def discover_component(kind, value):
    """Record a bought component (kind, value); returns True if new."""
    _load()
    key = (kind, value)
    if key in _DATA["components"]:
        return False
    _DATA["components"].add(key)
    _save()
    return True


def discover_match_group(index):
    """Record a discovered match group (a shape group or an effect); True if new.

    A match group is a card's trigger half (see components' MATCH GROUPS
    section), recorded by its index in components.MATCH_GROUPS.
    """
    _load()
    if index in _DATA["match_groups"]:
        return False
    _DATA["match_groups"].add(index)
    _save()
    return True


# COMMENTED OUT with the conditions (user request: "comment out all the code for
# conditions"): the condition codex entry, replaced by the match-group one above.
#
# def discover_condition(value):
#     """Record a discovered condition; returns True only if it was new."""
#     _load()
#     if value in _DATA["conditions"]:
#         return False
#     _DATA["conditions"].add(value)
#     _save()
#     return True


def discover_pack(value):
    """Record a bought pack TYPE (see components.Pack); returns True if new.

    Only the type is recorded, never the size: the codex lists the kinds of pack
    the shop can deal ("Card Pack"), and a big card pack and a giga card pack
    reveal the same entry.
    """
    _load()
    if value in _DATA["packs"]:
        return False
    _DATA["packs"].add(value)
    _save()
    return True


def discover_trial(value):
    """Record a trial beaten in a cleared run; returns True if new."""
    _load()
    if value in _DATA["trials"]:
        return False
    _DATA["trials"].add(value)
    _save()
    return True


def is_card_discovered(value):
    _load()
    return value in _DATA["cards"]


def is_action_discovered(value):
    _load()
    return value in _DATA["actions"]


def is_component_discovered(kind, value):
    _load()
    return ((kind, value) in ALWAYS_DISCOVERED_COMPONENTS
            or (kind, value) in _DATA["components"])


def is_match_group_discovered(index):
    _load()
    return index in _DATA["match_groups"]


# COMMENTED OUT with the conditions: the condition lookup, replaced above.
#
# def is_condition_discovered(value):
#     _load()
#     return value in _DATA["conditions"]


def is_pack_discovered(value):
    _load()
    return value in _DATA["packs"]


def is_trial_discovered(value):
    _load()
    return value in _DATA["trials"]


def discover_tool(value):
    """Record a tool the player has obtained (a starter counts as seen)."""
    _load()
    if value in _DATA["tools"]:
        return False
    _DATA["tools"].add(value)
    _save()
    return True


def discover_passive(value):
    """Record an unplayable (passive) item the player has obtained."""
    _load()
    if value in _DATA["passives"]:
        return False
    _DATA["passives"].add(value)
    _save()
    return True


def discover_structure(value):
    """Record a structure the player has opened (or laid eyes on)."""
    _load()
    if value in _DATA["structures"]:
        return False
    _DATA["structures"].add(value)
    _save()
    return True


def is_tool_discovered(value):
    _load()
    return value in ALWAYS_DISCOVERED_TOOLS or value in _DATA["tools"]


def is_passive_discovered(value):
    _load()
    return value in _DATA["passives"]


def is_structure_discovered(value):
    _load()
    return value in _DATA["structures"]
