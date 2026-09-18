"""Where the player's data lives: one profile folder per player (see profiles).

Everything the game writes between runs — the six save slots and the
achievements / collection / metagame json files — belongs inside a profile
folder under ``profiles/``. This module is the one place those folders are
named, so the persistence modules can point their DEFAULTS at a path inside
``profiles/`` without importing ``profiles`` itself (``profiles`` imports them,
so that would be a cycle).

The defaults are what a module writes to before ``profiles`` has activated the
player's profile: a test, a tool, or a probe that builds a Game without
switching profiles. They used to name the game's own folder, which is why
running the test suite left a stray ``collection.json`` beside main.py.
"""

import os

# The game's own folder (where main.py lives).
GAME_DIR = os.path.dirname(os.path.abspath(__file__))
# The folder holding every profile (see profiles.PROFILES_DIR, which starts
# from the same value but can be redirected by tests).
PROFILES_DIR = os.path.join(GAME_DIR, "profiles")
# The profile a fresh installation uses (see profiles.migrate_legacy).
DEFAULT_PROFILE = "profile_1"


def default_file(filename):
    """The default path of a per-profile file (achievements.json, ...)."""
    return os.path.join(PROFILES_DIR, DEFAULT_PROFILE, filename)


def default_saves_dir():
    """The default folder for a profile's six save slots."""
    return os.path.join(PROFILES_DIR, DEFAULT_PROFILE, "saves")


def ensure_parent(path):
    """Make sure the folder holding ``path`` exists (called before writing)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
