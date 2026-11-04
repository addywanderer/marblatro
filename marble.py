"""The marble: the ball a run sends through the board.

Its physics state (position, velocity, radius, the effects it has picked up) and
its trail; the simulation itself lives in physics.py.
"""

from collections import deque

import numpy as np
import pygame

import components
from components import (
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
from config import *
from physics import PhysicsEngine
import rolling
from rolling import *




class Marble:
    def __init__(self, x, y):
        self.position = np.array([x, y], dtype=float)
        self.velocity = np.array([0.0, 0.0])
        self.radius = MARBLE_RADIUS
        self.color = MARBLE_COLOR
        self.color2 = self.color  # second half-color for two-tone marbles
        # The marble type chosen for this save (see MarbleType); it drives the
        # marble's appearance and special behavior (8-ball retriggers scoring,
        # rubber ball bounces off blocks and borders).
        self.marble_type = MarbleType.VANILLA
        # Rubber-ball marbles bounce off blocks and borders with full energy.
        self.bouncy = False
        # The marble's own bounciness when it hits a plain block or border
        # (the fraction of the incoming speed reflected): 0 for a vanilla
        # marble, 0.35 for the ping-pong ball. Bouncy blocks always reflect
        # with full energy regardless of this.
        self.restitution = RESTITUTION
        # Sticky-block state: while sticky_timer > 0 the marble is held in
        # place; when it expires the marble is released with sticky_velocity
        # (its damped impact speed). None once not stuck.
        self.sticky_timer = 0.0
        self.sticky_velocity = None
        # Phase-effect state: phase_timer counts down the seconds of "pass
        # through every block" left after touching a phase block, and
        # phase_block is the block that granted it. That block cannot phase the
        # marble again until the marble is clear of it, so a marble resting on
        # a phase block can't re-arm the phase forever.
        self.phase_timer = 0.0
        self.phase_block = None
        # How many times a Growing block has doubled this marble's radius this
        # run. Growing stops at GROW_MAX_TRIGGERS (see physics.update).
        self.grow_triggers = 0
        # The key numbers this marble has collected this run: passing through a
        # Key block remembers its pairing number (see Game._gate_key_and_lock),
        # and the Gate whole card pays when THIS marble then passes through the
        # matching opened Lock. Per marble, not per run: a lock another marble's
        # key opened pays this one nothing.
        self.collected_keys = set()
        # The collision normal physics resolved against each block this frame
        # (block -> unit normal), and the velocity the marble arrived with, both
        # keyed by block. The splitter reads them to send its copy off the
        # surface the marble actually hit.
        self.contact_normals = {}
        self.contact_incoming = {}
        # Accumulated roll angle (radians) for the 3D rotating marble drawing;
        # advanced by the physics engine from the marble's angular velocity.
        self.spin_angle = 0.0
        # Last motion direction (unit vector), used to orient the roll axis when
        # the marble stops (the painted feature keeps its last orientation).
        self._move_dir = np.array([1.0, 0.0])
        self.angular_velocity = 0.0
        self.mass = MARBLE_MASS
        self.on_slope = False
        self.grounded = False
        self.finished = False
        # Trial modifiers set per run by reset_run: the dead-zone trial triples
        # gravity in the marble box's bottom third; the all-finishes trial makes
        # the marble-box borders act as a finish block; the bouncy-castle trial
        # makes every solid block reflect the marble like a bouncy block.
        self.dead_zone = False
        self.finish_on_border = False
        self.bouncy_castle = False
        # The marble-weight trial scales only EFFECT pushes (pistons, bouncy
        # blocks, rotating shapes, accelerators, black holes) by 1/effect_mass.
        # Fall speed uses marble.mass and is never affected by this field.
        self.effect_mass_mult = 1.0
        # True while a black hole is pulling this marble this frame; the
        # astronaut card times it.
        self.under_black_hole = False
        self.distance = 0.0
        # Decaying peak of the marble's speed, sampled before collision
        # resolution each frame. The Quick scorer reads it so an effect that
        # pins the marble to rest still awards chips for how fast it arrived.
        self.recent_speed = 0.0
        # The marble's current airborne streak (seconds since it last touched
        # any block, including Shape.None/pipes/portals). The Airball scorer
        # rewards +8 mult per second of air before a touch. Grows while the
        # marble has no contact this frame; reset while it is in contact.
        self.air_streak = 0.0
        # Trail bookkeeping: distance moved since the last trail dot was
        # spawned, and the marble's total distance at that time.
        self._trail_accum = 0.0
        self._last_trail_distance = 0.0
        self.collisions_last_tick = []
        self.collisions_this_tick = []
        self._pre_move_position = None
        self.start_block = None  # the START block this marble was released from
        # (cell_a, cell_b) grid-cell rects of the portal pair this marble most
        # recently teleported through; None once it leaves both cells. Only that
        # pair is skipped, so other portal pairs work independently.
        self.last_portal_cells = None
        self.physics = PhysicsEngine()
        # The marble's last second of motion state, one snapshot per frame:
        # oldest first, and a full deque is exactly PROCRASTINATION_REWIND_FRAMES
        # frames — one second — deep (see motion_state / Game._procrastination_rewind).
        self.history = deque(maxlen=PROCRASTINATION_REWIND_FRAMES + 1)

    def motion_state(self):
        """The marble's motion state, as one Procrastination snapshot.

        Covers everything the physics engine moves the marble by: position,
        velocity, spin (angle and rate), size and mass, the sticky hold, the
        phase effect, and the flags effects set for the frame. Measurements the
        run accumulates (distance travelled, airborne streak, the decaying
        recent speed) and the run's clock are deliberately NOT here — the
        rewound second is played on top of them rather than replacing them, so
        a replay never un-earns progress.
        """
        sticky_velocity = self.sticky_velocity
        return (self.position.copy(), self.velocity.copy(), self.radius,
                self.mass, self.angular_velocity, self.spin_angle,
                self._move_dir.copy(), self.sticky_timer,
                None if sticky_velocity is None else sticky_velocity.copy(),
                self.phase_timer, self.phase_block, self.grounded,
                self.on_slope, self.under_black_hole)

    def restore_motion_state(self, state):
        """Put this marble back into a state captured by motion_state."""
        (position, velocity, radius, mass, angular_velocity, spin_angle,
         move_dir, sticky_timer, sticky_velocity, phase_timer, phase_block,
         grounded, on_slope, under_black_hole) = state
        self.position = position.copy()
        self.velocity = velocity.copy()
        self.radius = radius
        self.mass = mass
        self.angular_velocity = angular_velocity
        self.spin_angle = spin_angle
        self._move_dir = move_dir.copy()
        self.sticky_timer = sticky_timer
        self.sticky_velocity = (None if sticky_velocity is None
                                else sticky_velocity.copy())
        self.phase_timer = phase_timer
        self.phase_block = phase_block
        self.grounded = grounded
        self.on_slope = on_slope
        self.under_black_hole = under_black_hole
        # The mid-frame collision bookkeeping is rebuilt by the next physics
        # step, and the previous frame's contacts are gone with the rewound
        # second (a stale one would read as "still touching" on arrival).
        self._pre_move_position = None
        self.collisions_last_tick = []
        self.collisions_this_tick = []


def _configure_marble_type(marble, marble_type):
    """Apply a marble type's look and behavior to a freshly made marble.

    Called when a run spawns its marbles (reset_run). The rubber ball bounces
    and wears two random half-colors; the ping-pong ball is very light (falls
    normally, bounces a little, effect pushes act harder on it) and wears two
    random half-colors too. Vanilla keeps the plain white look.
    """
    marble.marble_type = marble_type
    marble.bouncy = marble_type == MarbleType.RUBBER_BALL
    marble.mass = MARBLE_MASS
    marble.restitution = RESTITUTION
    marble.color = MARBLE_COLOR
    marble.color2 = MARBLE_COLOR
    if marble_type == MarbleType.RUBBER_BALL:
        marble.color = random.choice(RUBBER_BALL_COLORS)
        marble.color2 = random.choice([c for c in RUBBER_BALL_COLORS
                                       if c != marble.color])
    elif marble_type == MarbleType.PING_PONG:
        marble.mass = PING_PONG_MASS
        marble.restitution = PING_PONG_RESTITUTION
        marble.color = random.choice(PING_PONG_COLORS)
        marble.color2 = random.choice([c for c in PING_PONG_COLORS
                                       if c != marble.color])
