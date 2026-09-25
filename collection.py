"""Collection codex: the cards, actions, components, and trials the player has seen.

A card, action, or component is discovered the first time the player buys it;
a trial is discovered the first time a run with it is beaten. Discoveries are
persisted per profile in ``collection.json`` inside the active profile's folder
(see ``profiles``), not per save slot. In the collection tab, undiscovered
entries show "???" instead of their name/description/icon.
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

_DATA = None  # {"cards": set, "actions": set, "components": set of (kind, value), "match_groups": set, "trials": set, "final_bosses": set}


def _load():
    """Load the discovered set from disk once (lazily)."""
    global _DATA
    if _DATA is not None:
        return
    _DATA = {"cards": set(), "actions": set(), "components": set(),
             "match_groups": set(), "trials": set(), "final_bosses": set()}
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _DATA["cards"] = set(data.get("cards", []))
        _DATA["actions"] = set(data.get("actions", []))
        _DATA["components"] = {(k, v) for k, v in data.get("components", [])}
        _DATA["match_groups"] = set(data.get("match_groups", []))
        _DATA["trials"] = set(data.get("trials", []))
        _DATA["final_bosses"] = set(data.get("final_bosses", []))
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
            "trials": sorted(_DATA["trials"]),
            "final_bosses": sorted(_DATA["final_bosses"]),
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


def discover_trial(value):
    """Record a trial beaten in a cleared run; returns True if new."""
    _load()
    if value in _DATA["trials"]:
        return False
    _DATA["trials"].add(value)
    _save()
    return True


def discover_final_boss(value):
    """Record a final boss beaten on the 24th run; returns True if new."""
    _load()
    if value in _DATA["final_bosses"]:
        return False
    _DATA["final_bosses"].add(value)
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


def is_trial_discovered(value):
    _load()
    return value in _DATA["trials"]


def is_final_boss_discovered(value):
    _load()
    return value in _DATA["final_bosses"]
