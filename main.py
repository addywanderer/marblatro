"""Marblatro's entry point: the game's namespace, its wiring, and its main loop.

The game itself is split over a few modules:

* config.py    — every tunable: colours, layout geometry, prices, scales.
* rolling.py   — the rolls and prices items are built and valued with.
* blocks.py    — Block, one square of the board.
* items.py     — the things the player owns (blocks, cards, actions, packs, tokens).
* shop.py      — the Shop's shelf, packs and held cells.
* toolbox.py   — the player's portable items (they lie on board squares).
* marble.py    — the marble: its state and its trail.
* game.py      — Game, assembled from the feature mixins in game_*.py.
* components.py, ui.py, cards.py, save_system.py, physics.py, profiles.py,
  metagame.py, achievements.py, collection.py, sounds.py, crt.py — the rest.

This module re-exports all of it, because the code and the tests refer to it as
main.Block, main.Game, main.SHOP_COORDS, ...; the modules that need the game's
values (ui.py, physics.py, cards.py, save_system.py) bind them from here at
import time, which is why the re-exports below are in dependency order.
"""

import math
import random
from collections import deque

import numpy as np
import pygame

import components
import crt
from components import (
    CARD_SCORERS,
    COMPONENT_PRICES,
    DEFAULT_DIFFICULTY,
    MAGNITUDE_ATAN_LIMIT,
    MAGNITUDE_MAX_STEPS,
    MAGNITUDE_SCALE,
    MAGNITUDE_STEP_DIVISOR,
    MAGNITUDES,
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

pygame.init()

# Toggle the 3px outline border drawn around blocks (WHITE, or RED once a block
# runs out of triggers). Set to False to hide all block borders while keeping
# each block's shape fill, effect icon, and portal number. A NONE block's dotted
# outline IS its border, so it hides too; LINE blocks keep their line (that's
# the shape itself).
BLOCK_BORDERS_ON = False

# The game's pieces live in their own modules (config, rolling, blocks, items,
# shop, toolbox, marble — and the Game itself in game.py); this module is the one
# namespace they are re-exported into, because the rest of the code and the tests
# refer to them as main.Block, main.Game, main.SHOP_COORDS, .... The order below
# is the dependency order: the tunables first (ui.py, physics.py, cards.py and
# save_system.py bind them from THIS module at import time), then the rolls and
# prices, then the classes, then the drawing/state modules, then the Game.
from config import *  # noqa: I001  the game's tunables (dependency order below)
import rolling                           # noqa: F401
from rolling import *
from rolling import _random_card_scorer  # noqa: F401  the tests roll with it
from blocks import Block
from items import (                      # noqa: F401
    CASH_BREAKDOWN,
    ActionItem,
    BlockItem,
    BoardUnitOffer,
    CardItem,
    ItemPack,
    ResourceOption,
    ScorerToken,
    CashBreakdown,
    _s,
    make_card_item,
    offer_key,
    owned_copy,
    resource_point_label,
)
import shop                              # noqa: F401
from shop import Shop                    # noqa: F401
import toolbox                           # noqa: F401
from toolbox import Toolbox              # noqa: F401
import marble                            # noqa: F401
from marble import Marble, _configure_marble_type  # noqa: F401


# Sound effects are synthesized in their own module; importing it also starts
# the mixer (it degrades to silent no-ops when no audio device is available).
# These modules are imported for their import-time side effects (achievements
# and collection register their hooks, metagame loads the meta save), and they
# are re-exported from here, so they are deliberately otherwise unused.
import achievements  # noqa: F401
import collection  # noqa: F401
import metagame  # noqa: F401
import sounds  # noqa: F401

# The physics engine lives in its own module (physics.py) and operates on
# Marble instances. It imports the enums/constants defined above, so this
# import must come after them (the tests reach for it through main).
from physics import PhysicsEngine  # noqa: F401


# The save system, card effects, profile system, and drawing helpers live in
# their own modules and need the classes above, so these imports must come
# after them (like the physics import). cards and save_system install their
# effects/handlers at import time, so they are re-exported but unused here;
# profiles and ui are used below.
import cards  # noqa: F401
import profiles
import save_system  # noqa: F401
import ui
from game import Game



# The drawing helpers and particle/popup classes live in ui.py; re-export them
# at module scope so the rest of the code and the tests can keep referring to
# them as main.draw_card / main.ScoreParticle / ... without change.
ScoreParticle = ui.ScoreParticle
TrailParticle = ui.TrailParticle
Popup = ui.Popup

# The match-group lookups live in components.py too; the game itself only uses
# the ones imported at the top, but the tests reach for the rest through main
# (main.match_group_for_shape(...) and friends), so re-export them here rather
# than leaving an unused import in the block above.
match_group_card_values = components.match_group_card_values
match_group_for_effect = components.match_group_for_effect
match_group_for_shape = components.match_group_for_shape
match_group_matches_block = components.match_group_matches_block
match_group_price = components.match_group_price
draw_card = ui.draw_card
draw_card_back = ui.draw_card_back
draw_marble_box = ui.draw_marble_box
draw_shop_item = ui.draw_shop_item
make_icon = ui.make_icon

# Thin delegating method wrappers: all the actual drawing lives in ui.py, but
# call sites and tests can keep using them as methods (block.draw(screen),
# game.draw(), game.draw_sidebar(), ...) unchanged.
Block.draw = ui.draw_block
Block._draw_effect_icon = ui._draw_block_effect_icon
Marble.draw = ui.draw_marble
Game.draw = ui.draw
Game.draw_sidebar = ui.draw_sidebar
Game.draw_trial_box = ui.draw_trial_box
Game._draw_item_info = ui.draw_item_info
Game._info_layout = ui.info_layout
Game._info_box_rect = ui.info_box_rect

if __name__ == "__main__":
    # First real launch: move any legacy root saves/achievements/collection/
    # metagame data into the default profile_1, then activate the remembered
    # current profile before building the game.
    profiles.migrate_legacy()
    profiles.switch_to(profiles.current_profile())
    game = Game()
    game.run()