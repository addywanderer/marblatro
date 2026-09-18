"""Profile system for Marblatro.

Each profile is an isolated "player": a folder under ``PROFILES_DIR`` that
owns its own ``saves/`` folder (the 6 save slots) plus ``achievements.json``,
``collection.json``, and ``metagame.json``. The game keeps exactly one active
profile (remembered in ``profiles/current.txt``); switching profiles swaps
which files ``save_system`` / ``achievements`` / ``collection`` / ``metagame``
read and write, so the title screen's save slots and every tab (achievements,
collection, upgrades) belong to the current profile.

The first run migrates the legacy layout (root-level ``saves/`` and the three
global json files, which used to be shared by every save) into the default
profile ``profile_1`` so no progress is lost.
"""

import os
import shutil
import stat
import time

import achievements
import collection
import metagame
import player_paths
import save_system

# The paths themselves are named in player_paths, which the persistence modules
# also use for their own defaults. They are re-exported here (rather than
# redefined) so there is one place that knows the layout; tests redirect the
# module attributes below.
GAME_DIR = player_paths.GAME_DIR
PROFILES_DIR = player_paths.PROFILES_DIR
DEFAULT_PROFILE = player_paths.DEFAULT_PROFILE


def profile_dir(name):
    """Absolute path to a profile's folder."""
    return os.path.join(PROFILES_DIR, name)


def profile_saves_dir(name):
    """Absolute path to a profile's 6-slot saves folder."""
    return os.path.join(profile_dir(name), "saves")


def current_file():
    """Path of the tiny file that records the active profile's folder name."""
    return os.path.join(PROFILES_DIR, "current.txt")


def ensure_profiles_dir():
    """Create the profiles root folder if missing."""
    os.makedirs(PROFILES_DIR, exist_ok=True)


def list_profiles():
    """The profile folder names, sorted, excluding hidden entries."""
    ensure_profiles_dir()
    names = []
    for entry in sorted(os.listdir(PROFILES_DIR)):
        path = os.path.join(PROFILES_DIR, entry)
        if os.path.isdir(path) and not entry.startswith("."):
            names.append(entry)
    return names


def sanitize_name(name):
    """A profile folder name safe to use on disk (letters/digits/spaces)."""
    cleaned = "".join(ch if (ch.isalnum() or ch in " _-") else " " for ch in name)
    return " ".join(cleaned.split())


def unique_name(name):
    """A sanitized, collision-free folder name for a new profile."""
    base = sanitize_name(name) or DEFAULT_PROFILE
    existing = set(list_profiles())
    if base not in existing:
        return base
    i = 2
    while f"{base} {i}" in existing:
        i += 1
    return f"{base} {i}"


def _ensure_profile_folder(name):
    """Make sure a profile's folder and 6 empty slot files exist."""
    os.makedirs(profile_dir(name), exist_ok=True)
    # save_system.ensure_saves creates SAVES_DIR + the empty slot placeholders.
    save_system.ensure_saves()


def _point_modules(name):
    """Point every persistence module at this profile's files and clear caches.

    Achievements/collection/metagame load lazily and cache, so each must be
    reset after re-pointing or the new profile would read the old profile's
    cached data.
    """
    folder = profile_dir(name)
    save_system.SAVES_DIR = profile_saves_dir(name)
    achievements.FILE_PATH = os.path.join(folder, "achievements.json")
    collection.FILE_PATH = os.path.join(folder, "collection.json")
    metagame.FILE_PATH = os.path.join(folder, "metagame.json")
    achievements.reset()
    collection.reset()
    metagame.reset()


def switch_to(name):
    """Make ``name`` the active profile, creating/ensuring its folder."""
    ensure_profiles_dir()
    # Point save_system at the profile's saves folder FIRST so the slot
    # placeholders are created inside it (not the previous profile's).
    _point_modules(name)
    _ensure_profile_folder(name)
    with open(current_file(), "w", encoding="utf-8") as f:
        f.write(name)


def current_profile():
    """The active profile's folder name (defaults to profile_1)."""
    ensure_profiles_dir()
    try:
        with open(current_file(), "r", encoding="utf-8") as f:
            name = f.read().strip()
        if name and os.path.isdir(profile_dir(name)):
            return name
    except OSError:
        pass
    return DEFAULT_PROFILE


def create_profile(name):
    """Create a profile from a player-chosen name and switch to it.

    The folder name is the sanitized, uniquified version of the typed name;
    returns that folder name.
    """
    folder = unique_name(name)
    switch_to(folder)
    return folder


def _pointer():
    """The raw profile folder name stored in current.txt, or None."""
    try:
        with open(current_file(), "r", encoding="utf-8") as f:
            name = f.read().strip()
        return name or None
    except OSError:
        return None


def rename_profile(old_name, new_name):
    """Rename a profile folder (renaming the active profile re-points modules).

    The new folder name is the sanitized version of ``new_name``, deduped
    against every OTHER profile (renaming a profile back to its own name is a
    no-op). Returns the profile's folder name after the rename.
    """
    target = sanitize_name(new_name) or old_name
    if target == old_name:
        return old_name
    others = [n for n in list_profiles() if n != old_name]
    if target in others:
        i = 2
        while f"{target} {i}" in others:
            i += 1
        target = f"{target} {i}"
    was_active = _pointer() == old_name
    os.rename(profile_dir(old_name), profile_dir(target))
    if was_active:
        with open(current_file(), "w", encoding="utf-8") as f:
            f.write(target)
        # The modules still pointed at the old (now gone) folder path.
        _point_modules(target)
    return target


def _remove_tree(path):
    """Recursively remove ``path``, clearing Windows read-only flags first.

    Profile folders kept under OneDrive are often marked read-only (mode
    0o40555), which makes ``shutil.rmtree`` raise PermissionError and silently
    leave the folder behind. Clear the read-only flag on every file and folder
    (including the top one) and retry a few times to ride out transient locks.
    Returns True only when the path is actually gone.
    """
    for _ in range(5):
        if not os.path.exists(path):
            return True
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            for root, _dirs, files in os.walk(path):
                for name in _dirs + files:
                    os.chmod(os.path.join(root, name), stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        try:
            shutil.rmtree(path)
        except OSError:
            time.sleep(0.1)
            continue
        return not os.path.exists(path)
    return not os.path.exists(path)


def delete_profile(name):
    """Delete a profile folder and settle on a remaining one.

    Returns True when the folder was removed. If removal fails (a Windows lock
    or a stubborn read-only folder), returns False and leaves the active
    profile untouched so the caller can tell the player instead of pretending
    the delete worked while the folder survives.
    """
    if not _remove_tree(profile_dir(name)):
        return False
    remaining = list_profiles()
    switch_to(remaining[0] if remaining else DEFAULT_PROFILE)
    return True


def migrate_legacy():
    """One-time move of the legacy root data into the default profile.

    Before profiles, ``saves/`` and the three global json files lived at the
    game root. On the first run they are moved (not copied) into
    ``PROFILES_DIR/profile_1`` so the player's existing progress becomes their
    first profile. Idempotent: it does nothing once profile_1 exists.
    """
    ensure_profiles_dir()
    if not os.path.isdir(profile_dir(DEFAULT_PROFILE)):
        os.makedirs(profile_dir(DEFAULT_PROFILE), exist_ok=True)
        for rel in ("saves", "achievements.json", "collection.json",
                    "metagame.json"):
            src = os.path.join(GAME_DIR, rel)
            dst = os.path.join(profile_dir(DEFAULT_PROFILE), rel)
            if os.path.exists(src):
                shutil.move(src, dst)
    # Remember the default profile unless a profile was already active.
    if not os.path.exists(current_file()):
        with open(current_file(), "w", encoding="utf-8") as f:
            f.write(DEFAULT_PROFILE)
