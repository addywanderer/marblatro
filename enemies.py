"""Level enemies: the things a marble has to kill to clear a level.

An enemy is a Block (so the physics engine collides with it for free) that
never scores. When a marble touches one the marble DEALS ITS SCORE as damage —
``chips * mult`` at that moment — and its own chips and mult are wiped back to
zero, so a marble has to build its score up again before its next hit. An enemy
whose HP reaches zero is defeated and leaves the board; the level is won when no
enemies are left and every marble has reached the Finish (see
Game._handle_block_contacts).

The numbers and the names of the kinds live with every other table in
components.py (EnemyKind, ENEMY_HP_SHARE, ENEMY_NAMES, ...); this module is only the
behaviour: how each kind moves, what it does to the marble that touches it, and
how it is drawn.
"""

import math

from components import (
    ARMOURED_HITS,
    ENEMY_COLORS,
    ENEMY_DESCRIPTIONS,
    ENEMY_HP_SHARE,
    ENEMY_NAMES,
    EnemyKind,
    Scorer,
    Shape,
)
from config import *  # noqa: F401,F403
from blocks import Block

PATROL_SPEED = 90.0     # px/s
FLEE_SPEED = 60.0       # px/s


class Enemy(Block):
    """A block the marble fights instead of scoring.

    The enemy is a plain RECT block (no shape, no effect, no scorer) so every
    existing collision, culling and drawing path treats it like any other block;
    ``is_enemy`` is what makes the contact loop fight it instead of scoring it.
    """

    def __init__(self, x, y, kind=EnemyKind.IDLE, hp=None):
        super().__init__(x, y, shape=Shape.RECT, scorer=Scorer.NONE)
        self.kind = kind
        # A level splits its health budget between its enemies and hands each
        # one its share (see components.split_enemy_health); an enemy made
        # without one wears its kind's share as its health.
        self.max_hp = ENEMY_HP_SHARE[kind] if hp is None else hp
        self.hp = self.max_hp
        self.alive = True
        self.is_enemy = True
        # Where the enemy floats: a float copy of the rect's position, so a
        # moving enemy can travel in sub-pixel steps.
        self.float_x = float(self.rect.x)
        self.float_y = float(self.rect.y)
        # Where it started, so a fresh run can put it back on its own cell.
        self.home_x = self.rect.x
        self.home_y = self.rect.y
        # PATROL's direction along its row, and ARMOURED's remaining hits.
        self.drift = 1.0
        self.hits_left = ARMOURED_HITS if kind == EnemyKind.ARMOURED else None
        # Hit feedback: flares for a moment when the marble lands a blow.
        self.hit_flash = 0.0

    # --- state ----------------------------------------------------------

    @property
    def name(self):
        return ENEMY_NAMES[self.kind]

    @property
    def description(self):
        return ENEMY_DESCRIPTIONS[self.kind]

    @property
    def color(self):
        return ENEMY_COLORS[self.kind]

    def can_be_hit(self):
        """True while the enemy can still take damage."""
        if not self.alive:
            return False
        if self.hits_left is not None and self.hits_left <= 0:
            return False
        return True

    # --- behaviour ------------------------------------------------------

    def cell_at(self, x, y):
        """The board square a position of the enemy's top-left corner sits on."""
        return (int((x - MARBLE_BOX_COORDS[0]) // GRID_SIZE),
                int((y - MARBLE_BOX_COORDS[1]) // GRID_SIZE))

    def can_stand(self, x, y, unlocked):
        """True when the enemy may stand with its corner at (x, y).

        ``unlocked`` is the game's set of unlocked board squares (or None to
        allow anywhere, which is what a test that only measures movement
        passes): a moving enemy keeps to the part of the board the player can
        reach, and turns round at the edge of its room rather than sliding over
        locked ground.
        """
        if not unlocked:
            return True
        return self.cell_at(x, y) in unlocked

    def step(self, dt, marbles, unlocked=None):
        """Advance the enemy's own movement for one frame."""
        if not self.alive or dt <= 0:
            return
        self.hit_flash = max(0.0, self.hit_flash - dt)
        left = MARBLE_BOX_COORDS[0]
        right = MARBLE_BOX_COORDS[0] + GRID_SIZE * GRID_WIDTH - self.rect.width
        top = MARBLE_BOX_COORDS[1]
        bottom = MARBLE_BOX_COORDS[1] + GRID_SIZE * GRID_HEIGHT - self.rect.height
        if self.kind == EnemyKind.PATROL:
            step = PATROL_SPEED * self.drift * dt
            target = min(max(self.float_x + step, left), right)
            if self.can_stand(target, self.float_y, unlocked):
                self.float_x = target
            else:
                # The edge of the room (or the box) turns it round: it tries the
                # other way immediately, so it never stalls on a wall.
                self.drift = -self.drift
                target = min(max(self.float_x + PATROL_SPEED * self.drift * dt,
                                 left), right)
                if self.can_stand(target, self.float_y, unlocked):
                    self.float_x = target
                self.rect.x = int(round(self.float_x))
                return
        elif self.kind == EnemyKind.FLEE and marbles:
            marble = min(
                marbles,
                key=lambda m: math.hypot(m.position[0] - self.rect.centerx,
                                         m.position[1] - self.rect.centery))
            dx = self.rect.centerx - float(marble.position[0])
            dy = self.rect.centery - float(marble.position[1])
            away = math.hypot(dx, dy)
            if away > 1.0:
                step = FLEE_SPEED * dt
                # The two axes are tried separately, so a coward cornered against
                # a locked edge still slides along it instead of freezing.
                for move_x, move_y in ((dx / away * step, dy / away * step),
                                       (dx / away * step, 0.0),
                                       (0.0, dy / away * step)):
                    tx = min(max(self.float_x + move_x, left), right)
                    ty = min(max(self.float_y + move_y, top), bottom)
                    if self.can_stand(tx, ty, unlocked):
                        self.float_x, self.float_y = tx, ty
                        break
        else:
            return
        self.rect.x = int(round(self.float_x))
        self.rect.y = int(round(self.float_y))

    def reset(self):
        """Put the enemy back on its own cell at full health (a fresh run)."""
        self.hp = self.max_hp
        self.alive = True
        self.rect.x = self.home_x
        self.rect.y = self.home_y
        self.float_x = float(self.home_x)
        self.float_y = float(self.home_y)
        self.drift = 1.0
        self.hit_flash = 0.0
        if self.kind == EnemyKind.ARMOURED:
            self.hits_left = ARMOURED_HITS
