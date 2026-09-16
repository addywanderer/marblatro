"""Metagame persistence: the dice currency and permanent run-start upgrades.

Dice are earned when a game ends in defeat (the square of the run number they
were on minus 3), then spent on the title screen's UPGRADES tab for permanent
bonuses that apply to the start of every run in every save of the current
profile. The metagame is not per save slot — it is stored per profile in
``metagame.json`` inside the active profile's folder (see ``profiles``).
"""

import json
import os

# Where the metagame state lives. Tests redirect this for isolation.
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metagame.json")

_DATA = None  # {"dice": int, "chip_level": int, "mult_level": int, "xmult_level": int}

# The upgrades shown on the title screen's UPGRADES tab. Each upgrade's id is
# also its "_level" key in the persisted data.
UPGRADES = [
    {"id": "chip", "name": "+Chips", "cost": 400,
     "desc": "Start each run with +30 chips"},
    {"id": "mult", "name": "+Mult", "cost": 800,
     "desc": "Start each run with +4 mult"},
    {"id": "xmult", "name": "xMult", "cost": 1200,
     "desc": "Start each run with a higher xMult (starts at x1)"},
]


def _load():
    """Load the metagame state from disk once (lazily)."""
    global _DATA
    if _DATA is not None:
        return
    _DATA = {"dice": 0, "chip_level": 0, "mult_level": 0, "xmult_level": 0}
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in _DATA:
            _DATA[key] = int(data.get(key, _DATA[key]))
    except (OSError, ValueError):
        pass


def _save():
    """Write the metagame state to disk."""
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(_DATA, f)


def reset():
    """Forget the metagame (used by tests for isolation)."""
    global _DATA
    _DATA = None


def dice():
    """The player's current dice balance."""
    _load()
    return _DATA["dice"]


def add_dice(amount):
    """Add to the dice balance and persist."""
    _load()
    _DATA["dice"] += int(amount)
    _save()


def chip_bonus():
    """The permanent +chips applied at the start of every run (30 per level)."""
    _load()
    return 30 * _DATA["chip_level"]


def mult_bonus():
    """The permanent +mult applied at the start of every run (4 per level)."""
    _load()
    return 4 * _DATA["mult_level"]


def xmult_bonus():
    """The permanent xMult applied at the start of every run (1 + 0.25/level)."""
    _load()
    return 1.0 + 0.25 * _DATA["xmult_level"]


def level(upgrade_id):
    """How many levels an upgrade has been bought to."""
    _load()
    return _DATA[upgrade_id + "_level"]


def bonus_text(upgrade_id):
    """The current run-start bonus an upgrade grants, as display text."""
    if upgrade_id == "chip":
        return f"Current: +{chip_bonus()} chips"
    if upgrade_id == "mult":
        return f"Current: +{mult_bonus()} mult"
    if upgrade_id == "xmult":
        return f"Current: x{xmult_bonus():.2f}"
    return ""


def buy_upgrade(upgrade_id):
    """Spend dice to buy one level of an upgrade; returns True on success."""
    _load()
    for upgrade in UPGRADES:
        if upgrade["id"] == upgrade_id:
            if _DATA["dice"] < upgrade["cost"]:
                return False
            _DATA["dice"] -= upgrade["cost"]
            _DATA[upgrade_id + "_level"] += 1
            _save()
            return True
    return False
