"""Achievement definitions and persistence for Marblatro.

Achievements are meta-goals that unlock once and stay unlocked forever (across
runs and games). The unlocked set is persisted per profile in a small JSON file
inside the active profile's folder (see ``profiles``); switching profiles
re-points this module at that profile's file.

The unlock conditions themselves are evaluated by the game (main.py) each
frame; this module only defines the achievements, tracks which are unlocked,
and renders the display description (secret achievements show "???" in the
achievements tab until they are unlocked).
"""

import json
import os


class Achievement:
    """A single achievement: an id, display name, and description.

    ``secret`` hides the description (as "???") in the achievements tab until
    the achievement is unlocked.
    """

    def __init__(self, id, name, description, secret=False):
        self.id = id
        self.name = name
        self.description = description
        self.secret = secret


# Every achievement in the game. New ones just get appended here; the
# achievements tab renders them all in a grid.
ACHIEVEMENTS = [
    Achievement(
        "rich",
        "Rich",
        "Hold more than $1000 in cash at any point in a run.",
    ),
    Achievement(
        "how_did_we_get_here",
        "How did we get here?",
        "Assemble a single block that has every effect in the game.",
        secret=True,
    ),
]

# Where the unlocked set lives. Global (not per save slot): an achievement
# stays unlocked no matter which slot you play. Tests redirect this.
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "achievements.json")

_UNLOCKED = None  # set of unlocked achievement ids; lazily loaded once
# True once achievements have been disabled for this profile (unlocking the
# whole collection turns them off): no NEW achievements can unlock from then
# on, but already-earned ones stay. Persisted with the unlocked set.
_DISABLED = None  # bool, or None until the file has been loaded


def _load():
    """Load the unlocked set and disabled flag from disk once (lazily)."""
    global _UNLOCKED, _DISABLED
    if _UNLOCKED is not None and _DISABLED is not None:
        return
    _UNLOCKED = set()
    _DISABLED = False
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _UNLOCKED = set(data.get("unlocked", []))
        _DISABLED = bool(data.get("disabled", False))
    except (OSError, ValueError):
        _UNLOCKED = set()
        _DISABLED = False


def _save():
    """Write the unlocked set and disabled flag to disk."""
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"unlocked": sorted(_UNLOCKED),
                   "disabled": bool(_DISABLED)}, f)


def reset():
    """Forget every unlocked achievement (used by tests for isolation).

    Sets the cache to None so the next access re-reads the (redirected) file.
    """
    global _UNLOCKED, _DISABLED
    _UNLOCKED = None
    _DISABLED = None


def disable():
    """Permanently turn achievements off for this profile.

    New achievements can no longer be unlocked; already-earned ones stay.
    Persisted per profile (the module is re-pointed on profile switch).
    """
    _load()
    global _DISABLED
    _DISABLED = True
    try:
        _save()
    except OSError:
        pass  # never crash the game over a failed achievement save


def is_disabled():
    """True when achievements are disabled for this profile."""
    _load()
    return bool(_DISABLED)


def is_unlocked(achievement_id):
    """True when the given achievement has been unlocked."""
    _load()
    return achievement_id in _UNLOCKED


def unlock(achievement_id):
    """Unlock an achievement; returns True only if it was newly unlocked.

    Once achievements are disabled for the profile, nothing new can unlock.
    """
    _load()
    if _DISABLED:
        return False
    if achievement_id in _UNLOCKED:
        return False
    _UNLOCKED.add(achievement_id)
    try:
        _save()
    except OSError:
        pass  # never crash the game over a failed achievement save
    return True


def achievement_by_id(achievement_id):
    """The Achievement record for an id, or None if it doesn't exist."""
    for achievement in ACHIEVEMENTS:
        if achievement.id == achievement_id:
            return achievement
    return None


def all_achievements():
    """Every achievement, in display order."""
    return list(ACHIEVEMENTS)


def display_description(achievement):
    """The description to show for an achievement.

    A locked secret achievement hides its description as "???"; once unlocked
    (or for a non-secret achievement) the real description is shown.
    """
    if achievement.secret and not is_unlocked(achievement.id):
        return "???"
    return achievement.description
