"""Physics engine for Marblatro.

Contains all of the marble-vs-block physics (movement, integration, collision
detection, resolution, and bounds clamping) that previously lived on the
``Marble`` class. Each method takes the target ``Marble`` as its first argument,
so the engine is stateless with respect to individual marbles and can be shared.
"""

import copy
import math
import sys

import numpy as np

# main.py defines the enums and physics constants used below. When main.py is
# run directly (python main.py) it executes under the name __main__, so it is
# NOT registered in sys.modules as 'main'. Reuse whichever module is actually
# running main.py; a plain `from main import ...` here would import a second,
# independent copy of main.py, which re-enters this module's import mid-way
# and raises ImportError: cannot import name 'PhysicsEngine' from 'physics'.
if "main" in sys.modules:
    _physics_source = sys.modules["main"]
elif "__main__" in sys.modules and hasattr(sys.modules["__main__"], "Shape"):
    _physics_source = sys.modules["__main__"]
else:  # pragma: no cover - only when physics.py is imported on its own
    import main as _physics_source

AIR_RESISTANCE = _physics_source.AIR_RESISTANCE
BLACK_HOLE_FORCE = _physics_source.BLACK_HOLE_FORCE
BLACK_HOLE_MIN_DIST = _physics_source.BLACK_HOLE_MIN_DIST
BLACK_HOLE_RANGE = _physics_source.BLACK_HOLE_RANGE
BOUNCY_RESTITUTION = _physics_source.BOUNCY_RESTITUTION
CONVEYOR_SPEED = _physics_source.CONVEYOR_SPEED
DT = _physics_source.DT
Effect = _physics_source.Effect
FRICTION_COEFFICIENT = _physics_source.FRICTION_COEFFICIENT
GRAVITY = _physics_source.GRAVITY
GRID_SIZE = _physics_source.GRID_SIZE
GROW_RADIUS_FACTOR = _physics_source.GROW_RADIUS_FACTOR
MARBLE_BOX_COORDS = _physics_source.MARBLE_BOX_COORDS
MAX_MARBLE_RECURSION = _physics_source.MAX_MARBLE_RECURSION
MIN_MARBLE_RADIUS = _physics_source.MIN_MARBLE_RADIUS
MAX_MARBLE_SPEED = _physics_source.MAX_MARBLE_SPEED
MAX_STEP_DISTANCE = _physics_source.MAX_STEP_DISTANCE
MAX_SUB_STEPS = _physics_source.MAX_SUB_STEPS
PEG_RADIUS = _physics_source.PEG_RADIUS
PHASE_DURATION = _physics_source.PHASE_DURATION
PISTON_FORCE = _physics_source.PISTON_FORCE
PORTAL_MAX_ACTIVATIONS = _physics_source.PORTAL_MAX_ACTIVATIONS
RECENT_SPEED_DECAY = _physics_source.RECENT_SPEED_DECAY
RESTITUTION = _physics_source.RESTITUTION
ROLLING_FRICTION = _physics_source.ROLLING_FRICTION
ROTATE_FLING = _physics_source.ROTATE_FLING
ROTATE_SPEED = _physics_source.ROTATE_SPEED
SHRINK_RADIUS_FACTOR = _physics_source.SHRINK_RADIUS_FACTOR
SQRT_2 = _physics_source.SQRT_2
STICKY_DURATION = _physics_source.STICKY_DURATION
STICKY_MIN_KEEP = _physics_source.STICKY_MIN_KEEP
STICKY_SPEED_REF = _physics_source.STICKY_SPEED_REF
Scorer = _physics_source.Scorer
Shape = _physics_source.Shape
del _physics_source


class PhysicsEngine:
    """Stateless physics operations applied to a ``Marble``.

    Methods follow the pattern ``method(marble, ...)``: the first argument is
    the marble being simulated and the rest mirror the original ``Marble``
    method signatures. Internal helper calls pass the marble along.
    """
    def __init__(self):
        self.gravity_dir = np.array([0.0, 1.0])

    def update(self, marble, dt, blocks):
        """Advance the marble by one frame: integrate forces, collide, clamp."""
        # A marble stuck to a sticky block is pinned in place until its stick
        # expires, then released at its damped impact velocity.
        if getattr(marble, "sticky_timer", 0.0) > 0:
            marble.sticky_timer = max(0.0, marble.sticky_timer - dt)
            if marble.sticky_timer <= 0:
                marble.velocity = getattr(marble, "sticky_velocity",
                                          np.array([0.0, 0.0]))
                marble.sticky_timer = 0.0
                marble.sticky_velocity = None
            else:
                # Still stuck: hold it perfectly still this frame (skip all
                # integration/collision) so it cannot drift off the block.
                marble.velocity *= 0.0
                return
        # The phase effect: after touching a phase block the marble passes
        # through EVERY block for PHASE_DURATION seconds. The timer counts down
        # here, and a phase block may only grant a phase again once the marble
        # is clear of it — otherwise a marble resting on the block would re-arm
        # a fresh phase the moment each one ran out and never collide again.
        marble.phase_timer = max(0.0, getattr(marble, "phase_timer", 0.0) - dt)
        phased = marble.phase_timer > 0
        if (not phased and getattr(marble, "phase_block", None) is not None
                and self._block_collision(marble, marble.phase_block) is None):
            marble.phase_block = None
        # Gravity points down by default. A gravity-effect block redirects it to
        # the direction its indicator points while the marble is under its
        # influence (in contact with the shape, or inside the cell for Shape.NONE).
        for block in blocks:
            if block.has_effect(Effect.GRAVITY) and self._accelerating(marble, block):
                self.gravity_dir = block.get_gravity_direction
                break
        # Gravity does not scale below mass 1: a very light marble (the
        # ping-pong ball, mass 0.35) falls at the same speed as a normal one,
        # like real life. Heavier marbles (the Singularity boss) still fall
        # faster as their mass grows.
        gravity_force = self.gravity_dir * GRAVITY * max(1.0, marble.mass)
        # The dead-zone trial triples gravity while the marble is in the bottom
        # third of the marble box.
        if getattr(marble, "dead_zone", False):
            bottom_third = MARBLE_BOX_COORDS[1] + 2 * MARBLE_BOX_COORDS[3] / 3
            if marble.position[1] >= bottom_third:
                gravity_force *= 3

        # Apply air resistance
        speed = np.linalg.norm(marble.velocity)
        if speed > 0:
            air_resistance = -AIR_RESISTANCE * marble.velocity * speed
        else:
            air_resistance = np.array([0.0, 0.0])

        # Gravity is applied as a direct acceleration scaled by mass, so a
        # heavier marble (the Singularity final boss) falls faster. Normal
        # marbles have mass 1, so their behavior is unchanged.
        acceleration = gravity_force + air_resistance / marble.mass
        marble.velocity += acceleration * dt

        for block in blocks:
            if block.has_effect(Effect.ACCELERATOR) and self._accelerating(marble, block):
                # A light marble (ping-pong) is pushed much harder (1 / mass).
                marble.velocity += block.get_acceleration * self._effect_boost(marble) * dt

        # Black-hole blocks pull the marble toward their center with a
        # gravity-like attraction that strengthens as the marble gets closer.
        # under_black_hole tracks (per frame) that a black hole is pulling this
        # marble, so the astronaut card can time it.
        marble.under_black_hole = False
        for block in blocks:
            if block.has_effect(Effect.BLACK_HOLE):
                to_block = np.array(block.rect.center, dtype=float) - marble.position
                dist = np.linalg.norm(to_block)
                if 0 < dist <= BLACK_HOLE_RANGE:
                    marble.under_black_hole = True
                    direction = to_block / dist
                    # The pull is the block's OWN strength (rolled when it was
                    # built), strongest at the edge of the range.
                    force = block.effect_magnitude(Effect.BLACK_HOLE)
                    pull = force * (BLACK_HOLE_RANGE / max(dist, BLACK_HOLE_MIN_DIST))
                    # A light marble (ping-pong) is pulled much harder (1/mass).
                    marble.velocity += direction * pull * self._effect_boost(marble) * dt

        # Repulsor blocks are the black hole's opposite: they push the marble
        # away from their center with the same range and falloff (stronger the
        # closer the marble gets), so a repulsor can slingshot a marble off.
        for block in blocks:
            if block.has_effect(Effect.REPULSOR):
                away = marble.position - np.array(block.rect.center, dtype=float)
                dist = np.linalg.norm(away)
                if 0 < dist <= BLACK_HOLE_RANGE:
                    direction = away / dist
                    force = block.effect_magnitude(Effect.REPULSOR)
                    push = force * (BLACK_HOLE_RANGE / max(dist, BLACK_HOLE_MIN_DIST))
                    marble.velocity += direction * push * self._effect_boost(marble) * dt

        # Conveyor blocks are belts: they carry the marble along the belt
        # direction (the block's arrow turned 90 degrees) at a CONSTANT speed.
        # The marble is brought up to the belt speed and then held there, so a
        # belt never accelerates a marble frame after frame; a marble already
        # travelling faster along the belt keeps its speed (a belt only adds),
        # and the belt speed is the same for every marble, so mass and the
        # effect-push modifiers don't change it.
        for block in blocks:
            if block.has_effect(Effect.CONVEYOR) and self._accelerating(marble, block):
                belt = block.get_belt_direction
                along = float(np.dot(marble.velocity, belt))
                belt_speed = block.effect_magnitude(Effect.CONVEYOR)
                if along < belt_speed:
                    marble.velocity = marble.velocity + belt * (belt_speed - along)

        # Rotating-effect blocks spin continuously; their geometry drives both
        # the drawn shape and the fling (see resolve_collision).
        for block in blocks:
            if block.has_effect(Effect.ROTATE):
                block.advance_spin(dt)

        # Track the marble's recent peak speed (sampled BEFORE any collision
        # resolution this frame). The Quick scorer uses it as a floor so an
        # effect that holds or pins the marble to rest at the scoring moment
        # (rotate, gravity, accelerator, black hole, slippery, fragile) still
        # awards chips for how fast the marble was moving when it hit.
        marble.recent_speed = max(np.linalg.norm(marble.velocity),
                                  marble.recent_speed * RECENT_SPEED_DECAY)

        # on_slope is set True while touching a slope/line this frame; reset it
        # each frame so it does not stay stuck after the marble leaves the surface.
        marble.on_slope = False
        # Marble position at the start of the current movement sub-step, used
        # to pick which side of a thin line the marble is on (see
        # _get_edge_normal). None when not mid-move.
        marble._pre_move_position = None

        marble.collisions_last_tick = copy.copy(marble.collisions_this_tick)
        marble.collisions_this_tick = []
        # The contact normals resolved this frame (block -> unit normal), read
        # by the splitter to send its copy off the surface it actually hit, and
        # the velocity the marble was carrying as it arrived at each block
        # (before the collision response, which usually kills the normal
        # component), so a split still knows which way the marble was going.
        marble.contact_normals = {}
        marble.contact_incoming = {}
        before_move = marble.position.copy()
        if phased:
            # Phasing: move with no blocks at all, so the marble passes through
            # every block (it is still kept inside the marble box).
            self.move_with_collision(marble, [], dt)
        else:
            self.move_with_collision(marble, blocks, dt)
        # Fragile blocks shatter once a marble touches them and then leaves: on
        # the first frame the marble is no longer in contact, the block's shape
        # becomes a pass-through no-hitbox field (marbles pass through it and it
        # can still score via field contacts, but it no longer blocks anything).
        # The crumbling trial marks a random 1/4 of the placed blocks with
        # block.trial_fragile, so they shatter exactly like fragile blocks — but
        # only REAL fragile-effect blocks count as a "break" for the wrecking
        # ball card (crumbling is a handicap, not a source of permanent bonus).
        for block in marble.collisions_last_tick:
            real_fragile = block.has_effect(Effect.FRAGILE)
            if ((real_fragile or getattr(block, "trial_fragile", False))
                    and block not in marble.collisions_this_tick
                    and block.shape != Shape.NONE):
                # Remember the original shape so a run reset can rebuild it.
                if block._fragile_shape is None:
                    block._fragile_shape = block.shape
                block.shape = Shape.NONE
                # Mark the block so the game can react once to the break (e.g.
                # the wrecking ball card grows its permanent +mult bonus).
                if real_fragile:
                    block.broke_fragile_this_frame = True
            # Satanic blocks are destroyed for good once a marble touches them
            # and then leaves: flag it so Game.update can remove the block from
            # the board (it never comes back on later runs).
            if (block.scorer == Scorer.SATANIC
                    and block not in marble.collisions_this_tick):
                block.satanic_leave = True
        self.keep_in_bounds(marble)
        self._collect_field_contacts(marble, blocks)
        # Growing/Shrinking effects change the marble's radius once per fresh
        # touch (not every frame while it stays in contact), so the size change
        # persists for the rest of the run.
        for block in marble.collisions_this_tick:
            if block in marble.collisions_last_tick:
                continue
            if block.has_effect(Effect.GROWING):
                marble.radius *= GROW_RADIUS_FACTOR
            elif block.has_effect(Effect.SHRINKING):
                marble.radius = max(marble.radius * SHRINK_RADIUS_FACTOR,
                                    MIN_MARBLE_RADIUS)
            elif (block.has_effect(Effect.PHASE)
                    and getattr(marble, "phase_block", None) is not block):
                # Touching a phase block lets the marble pass through every
                # block for PHASE_DURATION seconds. The block that granted it is
                # remembered and may not grant another phase until the marble is
                # clear of it, so a marble resting on a phase block can't re-arm
                # a phase the moment each one runs out.
                marble.phase_timer = block.effect_magnitude(Effect.PHASE)
                marble.phase_block = block
        marble.distance += np.linalg.norm(marble.position - before_move)

        # Update rolling state
        if marble.on_slope or marble.grounded:
            marble.angular_velocity = np.linalg.norm(marble.velocity) / marble.radius
        else:
            marble.angular_velocity *= 0.99
        # Accumulate the visible roll angle (radians) from the spin speed, so
        # the marble's painted pattern rotates as it rolls (see Marble.draw).
        marble.spin_angle = (getattr(marble, "spin_angle", 0.0)
                             + marble.angular_velocity * dt) % (2 * math.pi)

    def _in_contact_with(self, marble, block, margin=4.0):
        """True when the marble touches the block's shape (within a small margin).

        Accelerator blocks use this so they keep pushing a marble that is merely
        resting on the surface (its center sits at exactly MARBLE_RADIUS from it)
        and not only one that has penetrated into it. The margin is generous so
        the push keeps acting while the marble lifts off instead of cutting out
        the moment it leaves the surface by a pixel.
        """
        if block.scorer == Scorer.START:
            return False
        if block.shape == Shape.NONE:
            return False
        # A Key has no hitbox (it is a pickup the marble passes through) and an
        # opened Lock is a doorway, so neither is ever "in contact".
        if block.shape == Shape.KEY:
            return False
        if block.shape == Shape.LOCK and not getattr(block, "locked", True):
            return False
        if block.shape == Shape.RECT:
            return self._rect_collision(marble, block, margin) is not None
        if block.shape == Shape.CIRCLE:
            return self._circle_collision(marble, block, margin) is not None
        if block.shape == Shape.CURVED_SLOPE:
            return self._curved_slope_collision(marble, block, margin) is not None
        if block.shape == Shape.CONVEX_SLOPE:
            return self._convex_slope_collision(marble, block, margin) is not None
        if block.shape == Shape.PIPE:
            return self._pipe_collision(marble, block, margin) is not None
        if block.shape == Shape.DRAIN:
            return self._drain_collision(marble, block, margin) is not None
        if block.shape == Shape.PIPE_BEND:
            return self._pipe_bend_collision(marble, block, margin) is not None
        if block.shape == Shape.FLAT_LINE:
            return self._flat_line_collision(marble, block, margin) is not None
        if block.shape == Shape.CURVED_SLOPE_LINE:
            return self._curved_line_collision(marble, block, margin) is not None
        if block.shape == Shape.HALF_PIPE:
            return self._half_pipe_collision(marble, block, margin) is not None
        if block.shape == Shape.SPIKE:
            return self._spike_collision(marble, block, margin) is not None
        if block.shape == Shape.PLATFORM:
            return self._platform_collision(marble, block, margin) is not None
        if block.shape == Shape.CORNER:
            return self._corner_collision(marble, block, margin) is not None
        if block.shape == Shape.PEG:
            return self._peg_collision(marble, block, margin) is not None
        if block.shape == Shape.SAWTOOTH:
            return self._sawtooth_collision(marble, block, margin) is not None
        if block.shape == Shape.CRADLE:
            return self._cradle_collision(marble, block, margin) is not None
        if block.shape == Shape.BUMP:
            return self._bump_collision(marble, block, margin) is not None
        if block.shape == Shape.LOCK:
            return self._rect_collision(marble, block, margin) is not None
        return self._slope_collision(marble, block, margin) is not None

    def _inside_cell(self, marble, block):
        """True when the marble's center is inside the block's grid cell."""
        return (block.rect.left <= marble.position[0] <= block.rect.right
                and block.rect.top <= marble.position[1] <= block.rect.bottom)

    def _inside_pipe_cavity(self, marble, block):
        """True when the marble's center is inside a pipe's central cavity (gap).

        A pipe's scorer should trigger when the marble passes through its
        cavity even if the marble does not touch the pillars (the gap is exactly
        marble-diameter wide). The marble is transformed into the pipe's local
        frame (rotated by the pipe's effective angle) and tested against the
        central strip.
        """
        angle = math.radians(getattr(block, "effective_angle", block.angle))
        cx, cy = block.rect.center
        dx = marble.position[0] - cx
        dy = marble.position[1] - cy
        cos_a, sin_a = math.cos(-angle), math.sin(-angle)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        return abs(lx) <= marble.radius and abs(ly) <= block.rect.height / 2

    def _collect_field_contacts(self, marble, blocks):
        """Register pass-through blocks whose cell the marble is inside.

        No-hitbox (Shape.NONE) blocks have no physical hitbox, so they never
        collide, but their scoring effects should still activate when the marble
        passes through the cell. A Key (a pickup with no hitbox) and an opened
        Lock (a doorway) are pass-through fields in exactly the same way. Portal
        blocks are pass-through too, so a marble
        passing through a portal also activates its scorer. A pipe's scorer
        triggers when the marble passes through its central cavity, even without
        touching the pillars. The portal the marble just arrived at (an exit
        portal) is skipped so it doesn't score. Adding them to
        collisions_this_tick reuses the normal once-per-touch edge detection
        (they trigger on entry and again only after leaving).
        """
        for block in blocks:
            if block in marble.collisions_this_tick:
                continue
            if not self._inside_cell(marble, block):
                continue
            is_portal = block.has_effect(Effect.PORTAL)
            # The pass-through shapes: a no-hitbox field, a Key pickup, and a
            # Lock whose key has already been touched this run.
            pass_through = (block.shape in (Shape.NONE, Shape.KEY)
                            or (block.shape == Shape.LOCK
                                and not getattr(block, "locked", True)))
            # A marble passing through a pipe's cavity triggers the pipe's
            # scorer, even though the marble never touches the pillars.
            if block.shape == Shape.PIPE and self._inside_pipe_cavity(marble, block):
                marble.collisions_this_tick.append(block)
                continue
            if not pass_through and not is_portal:
                continue
            # The portal the marble just arrived at (an exit portal) is skipped
            # so it doesn't score — this applies to portals of ANY shape.
            if is_portal and marble.last_portal_cells is not None:
                cell = (block.rect.left, block.rect.top, block.rect.right, block.rect.bottom)
                if cell in marble.last_portal_cells:
                    continue
            marble.collisions_this_tick.append(block)

    def _portal_teleport(self, marble, blocks):
        """Teleport a marble inside a portal block to its paired portal.

        Portal blocks are pass-through fields: a marble whose center is inside a
        portal's grid cell exits from the matching portal (the other portal with
        the same pairing number). Marbles only teleport between portals that
        share a number. The two cells of the most recently used pair are
        remembered so a marble doesn't instantly bounce back out of the portal
        it just arrived at (or back through the one it came from) until it has
        left BOTH cells. Other portal pairs are never blocked by this, so a
        marble can chain through several pairs in one run. A pair shares one
        travel budget of PORTAL_MAX_ACTIVATIONS per run: once used up, the pair
        stops teleporting (marbles just pass through) until the run resets it.
        Returns True if the marble teleported.
        """
        # Once the marble is outside both cells of the pair it last used, that
        # pair can teleport it again.
        if marble.last_portal_cells is not None:
            ca, cb = marble.last_portal_cells
            in_a = ca[0] <= marble.position[0] <= ca[2] and ca[1] <= marble.position[1] <= ca[3]
            in_b = cb[0] <= marble.position[0] <= cb[2] and cb[1] <= marble.position[1] <= cb[3]
            if not in_a and not in_b:
                marble.last_portal_cells = None
        for block in blocks:
            if not block.has_effect(Effect.PORTAL) or not getattr(block, "portal_number", 0):
                continue
            if not self._inside_cell(marble, block):
                continue
            rect = block.rect
            cell = (rect.left, rect.top, rect.right, rect.bottom)
            if marble.last_portal_cells is not None and cell in marble.last_portal_cells:
                continue  # just used this pair; wait until leaving both its cells
            paired = self._paired_portal(blocks, block)
            if paired is None:
                continue  # the partner portal isn't on the grid
            # A portal pair can be travelled through at most
            # PORTAL_MAX_ACTIVATIONS times per run; the pair shares one count,
            # so both halves must still have uses left. Once a pair is used up
            # the portal effect stops functioning — the marble just passes
            # through the cell without teleporting until the run resets it.
            remaining = min(
                getattr(block, "portal_uses_left", PORTAL_MAX_ACTIVATIONS),
                getattr(paired, "portal_uses_left", PORTAL_MAX_ACTIVATIONS),
            )
            if remaining <= 0:
                continue
            # Passing through a portal activates its scorer (up to its trigger
            # limit per run), so register the entry portal as a contact.
            if block not in marble.collisions_this_tick:
                marble.collisions_this_tick.append(block)
            marble.position = np.array([paired.rect.centerx, paired.rect.centery], dtype=float)
            marble.last_portal_cells = (
                cell,
                (paired.rect.left, paired.rect.top, paired.rect.right, paired.rect.bottom),
            )
            # Count this travel against BOTH halves so the pair stays in
            # lockstep (mirrors how their trigger counts are kept in sync).
            block.portal_uses_left = remaining - 1
            paired.portal_uses_left = remaining - 1
            return True
        return False

    def _paired_portal(self, blocks, block):
        """The other portal block paired with ``block`` (same number), or None."""
        number = getattr(block, "portal_number", 0)
        for other in blocks:
            if other is block:
                continue
            if other.has_effect(Effect.PORTAL) and getattr(other, "portal_number", 0) == number:
                return other
        return None

    def _accelerating(self, marble, block):
        """True if an accelerator block should currently push this marble.

        Normal shapes push while the marble is in contact with their surface; the
        no-hitbox shape acts as an invisible field that pushes whenever the
        marble's center is inside the block's grid cell. A Key (a pickup) and an
        opened Lock (a doorway) are fields in the same way.
        """
        if block.shape in (Shape.NONE, Shape.KEY) or (
                block.shape == Shape.LOCK
                and not getattr(block, "locked", True)):
            return self._inside_cell(marble, block)
        return self._in_contact_with(marble, block)

    def move_with_collision(self, marble, blocks, dt):
        """Move the marble in bounded sub-steps, separating it from blocks positionally."""
        speed = np.linalg.norm(marble.velocity)
        if speed > MAX_MARBLE_SPEED:
            marble.velocity *= MAX_MARBLE_SPEED / speed
            speed = MAX_MARBLE_SPEED
        total_movement = marble.velocity * dt
        if speed == 0:
            # Even a stationary marble should use a portal if it is inside one.
            self._portal_teleport(marble, blocks)
            return
        # Sub-steps of at most MAX_STEP_DISTANCE px keep the cost bounded and
        # prevent tunneling at high speeds (no step can cross a block + margins).
        num_steps = max(1, math.ceil(speed * dt / MAX_STEP_DISTANCE))
        num_steps = min(num_steps, MAX_SUB_STEPS)
        increment = total_movement / num_steps

        for _ in range(num_steps):
            marble._pre_move_position = marble.position.copy()
            marble.position += increment
            self._resolve_block_overlaps(marble, blocks)
            # Pass-through fields (Shape.NONE) and portals are registered by
            # sampling the marble's path after every sub-step (each moves at
            # most MAX_STEP_DISTANCE px), so a fast marble can't skip a whole
            # cell between frame-boundary checks. Once a portal teleports it,
            # stop moving so the rest of this frame plays out from the exit.
            self._collect_field_contacts(marble, blocks)
            if self._portal_teleport(marble, blocks):
                break
        marble._pre_move_position = None

    def _collect_overlaps(self, marble, blocks):
        """Return [(block, normal, penetration)] for every block the marble overlaps."""
        overlaps = []
        for block in blocks:
            result = self._block_collision(marble, block)
            if result is not None:
                overlaps.append((block, result[0], result[1]))
        return overlaps

    def _resolve_block_overlaps(self, marble, blocks):
        """Resolve overlaps: apply velocity response once, then separate positionally."""
        overlaps = self._collect_overlaps(marble, blocks)
        if not overlaps:
            return

        for block, normal, _ in overlaps:
            if block not in marble.collisions_this_tick:
                marble.collisions_this_tick.append(block)
            # Keep the FIRST record of each block this frame: that is the
            # arrival hit. Later sub-steps of the same frame re-collide with a
            # velocity the response has already stopped, which would wipe out
            # the direction the marble actually arrived with.
            if block not in marble.contact_normals:
                marble.contact_normals[block] = normal
                marble.contact_incoming[block] = np.array(marble.velocity, dtype=float)
            self.resolve_collision(marble, block, normal)

        for _ in range(MAX_MARBLE_RECURSION + 1):
            overlaps = self._collect_overlaps(marble, blocks)
            if not overlaps:
                break
            for _, normal, penetration in overlaps:
                marble.position += normal * penetration

    def _block_collision(self, marble, block):
        """Return (normal, penetration) for a block, or None if the marble is clear."""
        if block.scorer == Scorer.START:
            return None
        if block.has_effect(Effect.PORTAL):
            return None  # portals are pass-through teleporters
        if block.shape == Shape.NONE:
            return None
        # A Key is a pass-through pickup and an opened Lock is a doorway: both
        # are registered as field contacts instead (see _collect_field_contacts).
        if block.shape == Shape.KEY:
            return None
        if block.shape == Shape.LOCK and not getattr(block, "locked", True):
            return None
        # A zipper is a one-way gate: open while the marble travels WITH the
        # block's arrow, solid against it (and while it just rests on it).
        if block.has_effect(Effect.ZIPPER) and self._zipper_open(marble, block):
            return None
        if block.shape == Shape.RECT:
            return self._rect_collision(marble, block)
        if block.shape == Shape.CIRCLE:
            return self._circle_collision(marble, block)
        if block.shape == Shape.CURVED_SLOPE:
            return self._curved_slope_collision(marble, block)
        if block.shape == Shape.CONVEX_SLOPE:
            return self._convex_slope_collision(marble, block)
        if block.shape == Shape.PIPE:
            return self._pipe_collision(marble, block)
        if block.shape == Shape.DRAIN:
            return self._drain_collision(marble, block)
        if block.shape == Shape.PIPE_BEND:
            return self._pipe_bend_collision(marble, block)
        if block.shape == Shape.FLAT_LINE:
            return self._flat_line_collision(marble, block)
        if block.shape == Shape.CURVED_SLOPE_LINE:
            return self._curved_line_collision(marble, block)
        if block.shape == Shape.HALF_PIPE:
            return self._half_pipe_collision(marble, block)
        if block.shape == Shape.SPIKE:
            return self._spike_collision(marble, block)
        if block.shape == Shape.PLATFORM:
            return self._platform_collision(marble, block)
        if block.shape == Shape.CORNER:
            return self._corner_collision(marble, block)
        if block.shape == Shape.PEG:
            return self._peg_collision(marble, block)
        if block.shape == Shape.SAWTOOTH:
            return self._sawtooth_collision(marble, block)
        if block.shape == Shape.CRADLE:
            return self._cradle_collision(marble, block)
        if block.shape == Shape.BUMP:
            return self._bump_collision(marble, block)
        if block.shape == Shape.LOCK:
            return self._rect_collision(marble, block)
        return self._slope_collision(marble, block)

    def _rect_collision(self, marble, block, margin=0.0):
        """Circle vs rectangle: return (outward_normal, penetration) or None."""
        if block.has_effect(Effect.ROTATE):
            # A rotating rect uses its oriented (rotated) hitbox so the marble
            # collides with the drawn shape, not the axis-aligned cell.
            return self._obb_collision(marble, block, margin)
        return self._circle_vs_rect(marble, block.rect, margin)

    def _circle_vs_rect(self, marble, rect, margin=0.0):
        """Circle vs an axis-aligned rect: (outward_normal, penetration) or None."""
        cx, cy = marble.position
        left, right, top, bottom = rect.left, rect.right, rect.top, rect.bottom

        closest_x = max(left, min(cx, right))
        closest_y = max(top, min(cy, bottom))
        closest = np.array([closest_x, closest_y])
        dist_vec = marble.position - closest
        distance = np.linalg.norm(dist_vec)

        if distance >= marble.radius + margin:
            return None

        if distance > 1e-9:
            return dist_vec / distance, marble.radius - distance

        # Center inside the rectangle: push out along the nearest face.
        dl, dr = cx - left, right - cx
        dt, db = cy - top, bottom - cy
        min_d = min(dl, dr, dt, db)
        if min_d == dl:
            return np.array([-1.0, 0.0]), marble.radius + dl
        if min_d == dr:
            return np.array([1.0, 0.0]), marble.radius + dr
        if min_d == dt:
            return np.array([0.0, -1.0]), marble.radius + dt
        return np.array([0.0, 1.0]), marble.radius + db

    def _pipe_collision(self, marble, block, margin=0.0):
        """Circle vs a pipe: (outward_normal, penetration) or None.

        A pipe is a RECT minus a vertical strip down the middle (marble-diameter
        wide), leaving two equal vertical pillars. The marble collides with
        whichever pillar is nearest; a marble centered in the gap passes through.
        A pipe rotated by its base angle (the A key) or spinning via the ROTATE
        effect is tested against its rotated pillars, so its hitbox matches the
        drawn shape.
        """
        rotated = block.has_effect(Effect.ROTATE) or block.angle % 360 != 0
        candidates = []
        for pillar in block._get_pipe_rects():
            if rotated:
                hit = self._obb_pillar_collision(marble, block, pillar, margin)
            else:
                hit = self._circle_vs_rect(marble, pillar, margin)
            if hit is not None:
                candidates.append(hit)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _obb_pillar_collision(self, marble, block, pillar, margin=0.0):
        """Circle vs a rotated pipe pillar (rotated about the cell center).

        Transforms the marble into the pillar's local frame (rotate by the
        block's angle around the cell center, then translate to the pillar's
        own center), does an axis-aligned test there, and rotates the normal
        back to world space.
        """
        angle = math.radians(getattr(block, "effective_angle", block.angle))
        cx, cy = block.rect.center
        # Pillar center relative to the cell center (in the unrotated frame).
        pcx = pillar.centerx - cx
        pcy = pillar.centery - cy
        # Marble into the block's local frame (rotate by -angle around the center).
        dx = marble.position[0] - cx
        dy = marble.position[1] - cy
        cos_a, sin_a = math.cos(-angle), math.sin(-angle)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        # Into the pillar's own frame.
        rx = lx - pcx
        ry = ly - pcy
        half_w = pillar.width / 2.0
        half_h = pillar.height / 2.0

        closest_x = max(-half_w, min(rx, half_w))
        closest_y = max(-half_h, min(ry, half_h))
        diff = np.array([rx - closest_x, ry - closest_y])
        d = np.linalg.norm(diff)
        if d >= marble.radius + margin:
            return None
        if d > 1e-9:
            local_normal = diff / d
            penetration = marble.radius - d
        else:
            # Center inside the pillar: push out along the nearest local axis.
            dist_left = rx + half_w
            dist_right = half_w - rx
            dist_top = ry + half_h
            dist_bottom = half_h - ry
            min_d = min(dist_left, dist_right, dist_top, dist_bottom)
            if min_d == dist_left:
                local_normal = np.array([-1.0, 0.0])
            elif min_d == dist_right:
                local_normal = np.array([1.0, 0.0])
            elif min_d == dist_top:
                local_normal = np.array([0.0, -1.0])
            else:
                local_normal = np.array([0.0, 1.0])
            penetration = marble.radius + min_d
        cos2, sin2 = math.cos(angle), math.sin(angle)
        nx = local_normal[0] * cos2 - local_normal[1] * sin2
        ny = local_normal[0] * sin2 + local_normal[1] * cos2
        return np.array([nx, ny]), penetration

    def _obb_collision(self, marble, block, margin=0.0):
        """Circle vs an oriented rectangle (rotated by angle + spin).

        Transforms the marble into the rectangle's local frame, does a normal
        axis-aligned test there, then rotates the normal back to world space.
        """
        angle = math.radians(getattr(block, "effective_angle", block.angle))
        cx, cy = block.rect.center
        dx = marble.position[0] - cx
        dy = marble.position[1] - cy
        cos_a, sin_a = math.cos(-angle), math.sin(-angle)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        half_w = block.rect.width / 2.0
        half_h = block.rect.height / 2.0

        closest_x = max(-half_w, min(lx, half_w))
        closest_y = max(-half_h, min(ly, half_h))
        diff = np.array([lx - closest_x, ly - closest_y])
        d = np.linalg.norm(diff)
        if d >= marble.radius + margin:
            return None
        if d > 1e-9:
            local_normal = diff / d
            penetration = marble.radius - d
        else:
            # Center inside the box: push out along the nearest local axis.
            dist_left = lx + half_w
            dist_right = half_w - lx
            dist_top = ly + half_h
            dist_bottom = half_h - ly
            min_d = min(dist_left, dist_right, dist_top, dist_bottom)
            if min_d == dist_left:
                local_normal = np.array([-1.0, 0.0])
            elif min_d == dist_right:
                local_normal = np.array([1.0, 0.0])
            elif min_d == dist_top:
                local_normal = np.array([0.0, -1.0])
            else:
                local_normal = np.array([0.0, 1.0])
            penetration = marble.radius + min_d
        cos2, sin2 = math.cos(angle), math.sin(angle)
        nx = local_normal[0] * cos2 - local_normal[1] * sin2
        ny = local_normal[0] * sin2 + local_normal[1] * cos2
        return np.array([nx, ny]), penetration

    def _circle_collision(self, marble, block, margin=0.0):
        """Circle vs circle: return (outward_normal, penetration) or None."""
        center = np.array([block.rect.centerx, block.rect.centery], dtype=float)
        radius = GRID_SIZE / 2.0
        offset = marble.position - center
        distance = np.linalg.norm(offset)
        if distance >= radius + marble.radius + margin:
            return None
        if distance > 1e-9:
            return offset / distance, (radius + marble.radius) - distance
        # Marble centered exactly on the block: push it up.
        return np.array([0.0, -1.0]), radius + marble.radius

    def _peg_collision(self, marble, block, margin=0.0):
        """Circle vs a peg: a small solid circle (PEG_RADIUS) at the cell center."""
        center = np.array([block.rect.centerx, block.rect.centery], dtype=float)
        radius = PEG_RADIUS
        offset = marble.position - center
        distance = np.linalg.norm(offset)
        if distance >= radius + marble.radius + margin:
            return None
        if distance > 1e-9:
            return offset / distance, (radius + marble.radius) - distance
        # Marble centered exactly on the peg: push it up.
        return np.array([0.0, -1.0]), radius + marble.radius

    def _platform_collision(self, marble, block, margin=0.0):
        """Circle vs a platform: the solid bar filling the cell's bottom half.

        A rotated platform (its base angle or a ROTATE spin) is tested against
        its rotated bar so the hitbox matches the drawn shape.
        """
        rect = block.get_platform_rect
        if block.has_effect(Effect.ROTATE) or block.angle % 360 != 0:
            return self._obb_pillar_collision(marble, block, rect, margin)
        return self._circle_vs_rect(marble, rect, margin)

    def _corner_collision(self, marble, block, margin=0.0):
        """Circle vs a corner (an L of two legs): the nearest leg's hit.

        The corner's two half-cell legs (a left column and a bottom row) are
        tested separately and the closest hit wins, exactly like the pipe's two
        pillars. A rotated corner uses its rotated legs.
        """
        rotated = block.has_effect(Effect.ROTATE) or block.angle % 360 != 0
        candidates = []
        for rect in block.get_corner_rects:
            if rotated:
                hit = self._obb_pillar_collision(marble, block, rect, margin)
            else:
                hit = self._circle_vs_rect(marble, rect, margin)
            if hit is not None:
                candidates.append(hit)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _spike_collision(self, marble, block, margin=0.0):
        """Circle vs a spike: the upward triangle (a convex polygon)."""
        return self._convex_polygon_collision(marble, block.get_spike_points, margin)

    def _bump_collision(self, marble, block, margin=0.0):
        """Circle vs a bump: the solid half-disc dome on the cell's bottom edge.

        The dome (a sampled top semicircle closed across its diameter) is a
        convex polygon, so the generic convex test handles it — and a rotated
        or spinning bump uses its rotated points, like the spike.
        """
        return self._convex_polygon_collision(marble, block.get_bump_points, margin)

    def _zipper_open(self, marble, block):
        """True while a zipper block is passable for this marble.

        A zipper is a one-way DOOR through the block: a marble-wide channel
        along the block's arrow. The marble may pass only while it travels WITH
        the arrow, only while its centre is inside that channel, and only until
        it has cleared the far face — everywhere else (the sides, the closed
        face, and a marble resting on it) the block is as solid as any other.

        The channel test is what keeps the sides solid: testing the direction
        alone opened the gate for any marble whose velocity had even a small
        component along the arrow, so a marble slowly drifting sideways into a
        solid side crept through it a frame at a time.
        """
        arrow = np.asarray(block._get_angle_vector(), dtype=float)
        if float(np.dot(marble.velocity, arrow)) <= 0.0:
            return False  # moving against the arrow: the gate is shut
        offset = (np.asarray(marble.position, dtype=float)
                  - np.array(block.rect.center, dtype=float))
        half_extent = max(block.rect.width, block.rect.height) / 2.0
        if float(np.dot(offset, arrow)) > half_extent:
            return False  # already out through the far face
        channel = np.array([-arrow[1], arrow[0]], dtype=float)
        return abs(float(np.dot(offset, channel))) <= marble.radius

    def _sawtooth_collision(self, marble, block, margin=0.0):
        """Circle vs a sawtooth: the nearest of the row of triangular teeth."""
        candidates = []
        for tooth in block.get_sawtooth_teeth:
            hit = self._convex_polygon_collision(marble, tooth, margin)
            if hit is not None:
                candidates.append(hit)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _cradle_collision(self, marble, block, margin=0.0):
        """Circle vs a cradle: the nearest of its solid pieces.

        The cradle is a V-shaped valley carved from the cell's top edge down to
        a point above the bottom, backed by a floor slab, so its solid is three
        convex pieces (two side wedges and the slab). A marble in the valley is
        between the wedges and clear; one overlapping a piece collides with the
        nearest piece.
        """
        candidates = []
        for piece in block.get_cradle_pieces:
            hit = self._convex_polygon_collision(marble, piece, margin)
            if hit is not None:
                candidates.append(hit)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _drain_collision(self, marble, block, margin=0.0):
        """Circle vs a drain: (outward_normal, penetration) or None.

        A drain is a square cell with a funnel-shaped cavity: the top opens the
        full cell width and two curved walls taper to a marble-diameter opening
        at the bottom. The solid is the cell minus that cavity — the two walls,
        each a convex wedge. A marble in the funnel (between the walls) is clear
        and falls through; a marble overlapping a wall collides with the nearest
        one.
        """
        candidates = []
        for wall in block.get_drain_walls:
            hit = self._convex_polygon_collision(marble, wall, margin)
            if hit is not None:
                candidates.append(hit)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _pipe_bend_collision(self, marble, block, margin=0.0):
        """Circle vs a pipe-bend block: (outward_normal, penetration) or None.

        A pipe bend is a marble-width (16px) channel that enters the cell's top
        edge and exits its right edge (adjacent sides), turning a smooth 90
        degrees along a quarter-annulus centered at the cell's top-right corner
        (inner radius 12, outer radius 28 = inner + marble diameter). The solid
        is the cell minus that channel: the corner core (inside the inner
        radius) plus the rest of the cell outside the outer radius. Both curved
        walls use exact circle geometry (the same arc test as the curved slope)
        and the straight cell edges are tested as segments. Every collision is
        truncated to the arc's angular span and to the marble being in range,
        so a marble entering the top or leaving the right is never pinned by a
        wall that isn't actually there. Returns the nearest hit.
        """
        center = block.get_pipe_bend_center
        radius = marble.radius
        inner = float(block.rect.width // 2 - radius)   # 12
        outer = float(block.rect.width // 2 + radius)   # 28
        offset = marble.position - center
        d = float(np.linalg.norm(offset))
        candidates = []

        # 1) The inner wall: the corner core's convex quarter-arc. A marble in
        #    the channel that reaches the core is pushed back out (radially
        #    outward), exactly as if it hit the curved edge of a solid disk.
        if d > 1e-9 and self._on_arc(center, block.get_pipe_bend_inner_arc, offset) \
                and d < inner + radius + margin:
            candidates.append((offset / d, inner + radius - d))

        # 2) The outer wall: the surrounding solid's concave quarter-arc. A
        #    marble in the channel that reaches it is pushed back in (radially
        #    inward) to outer - radius, the channel's outer edge. The arc-span
        #    check truncates this so the wall does not extend past the cell: a
        #    marble that has passed through the right exit (its direction from
        #    the corner is now below 90 degrees) is free instead of pinned.
        if d > 1e-9 and self._on_arc(center, block.get_pipe_bend_outer_arc, offset) \
                and outer - radius < d < outer + radius + margin:
            candidates.append((-offset / d, radius + d - outer))

        # 3) The straight boundaries: the cell's edges (split around the
        #    channel's entrance and exit) and the corner core's two straight
        #    edges, using the same segment test as the curved slope's legs.
        for p1, p2, normal in block.get_pipe_bend_legs:
            leg = self._segment_collision_fixed(marble, p1, p2, normal, margin)
            if leg is not None:
                candidates.append(leg)

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _convex_polygon_collision(self, marble, points, margin=0.0):
        """Circle vs a convex polygon (a solid region): (outward_normal, penetration) or None."""
        pts = [np.array(p, dtype=float) for p in points]
        n = len(pts)
        if n < 3:
            return None
        centroid = np.mean(pts, axis=0)
        inside = True
        best_dist = float("inf")
        best_normal = np.array([0.0, -1.0])
        best_closest = None
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            seg = b - a
            seg_len_sq = float(np.dot(seg, seg))
            if seg_len_sq < 1e-12:
                continue
            t = float(np.dot(marble.position - a, seg)) / seg_len_sq
            t = max(0.0, min(1.0, t))
            closest = a + t * seg
            dist_vec = marble.position - closest
            d = np.linalg.norm(dist_vec)
            # Outward edge normal (away from the polygon's centroid).
            edge_normal = np.array([-seg[1], seg[0]], dtype=float)
            if np.dot(edge_normal, centroid - closest) < 0:
                edge_normal = -edge_normal
            edge_normal /= np.linalg.norm(edge_normal)
            # The center is outside if it sits on the far side of any edge.
            if np.dot(marble.position - closest, edge_normal) < -1e-9:
                inside = False
            if d < best_dist:
                best_dist = d
                best_normal = edge_normal
                best_closest = closest
        if inside:
            # Center inside the solid: push out along the nearest edge.
            return best_normal, marble.radius + best_dist
        if best_dist >= marble.radius + margin:
            return None
        if best_dist > 1e-9:
            normal = (marble.position - best_closest) / best_dist
        else:
            normal = best_normal
        return normal, marble.radius - best_dist

    def _segment_collision_fixed(self, marble, p1, p2, normal, margin=0.0):
        """Circle vs a line segment, returning (outward_normal, penetration) or None."""
        p1 = np.array(p1, dtype=float)
        p2 = np.array(p2, dtype=float)
        normal = np.array(normal, dtype=float)
        seg = p2 - p1
        seg_len_sq = np.dot(seg, seg)
        if seg_len_sq == 0:
            return None
        t = np.dot(marble.position - p1, seg) / seg_len_sq
        t = max(0.0, min(1.0, t))
        closest = p1 + t * seg
        dist_vec = marble.position - closest
        distance = np.linalg.norm(dist_vec)
        if distance >= marble.radius + margin:
            return None
        if distance > 1e-9:
            n = dist_vec / distance
        else:
            n = normal
        return n, max(0.0, marble.radius - distance)

    def _curved_slope_collision(self, marble, block, margin=0.0):
        """Return (normal, penetration) for a curved-slope block, or None.

        Like the slope triangle, but the straight hypotenuse is replaced by an
        inward-curving quarter circle (center at the cell's top-left corner,
        radius = cell size). The solid region is bounded by that arc plus the
        cell's right and bottom edges. The whole shape honors the block's angle.
        """
        center = block.get_curved_center
        R = float(block.rect.width)
        candidates = []

        # 1) The curved surface (quarter circle).
        offset = marble.position - center
        d = np.linalg.norm(offset)
        if d > 1e-9:
            arc_dist = abs(d - R)
            if arc_dist < marble.radius + margin and self._on_curved_arc(block, center, offset):
                candidates.append((-offset / d, max(0.0, marble.radius - arc_dist)))

        # 2) The straight legs (right and bottom), rotated with the block.
        for p1, p2, normal in block.get_curved_legs:
            leg = self._segment_collision_fixed(marble, p1, p2, normal, margin)
            if leg is not None:
                candidates.append(leg)

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _convex_slope_collision(self, marble, block, margin=0.0):
        """Return (normal, penetration) for a convex-slope block, or None.

        The convex slope is the curved slope's mirror image: instead of a
        recess, the solid is a quarter-disk (a quarter circle) at the cell's
        top-left corner. A marble that reaches the disk is pushed out, radially
        outward, so its center stays at R + radius on the convex surface, and
        the disk's top and left straight edges block marbles falling onto it.
        """
        center = block.get_convex_center
        R = float(block.rect.width)
        radius = marble.radius
        offset = marble.position - center
        d = float(np.linalg.norm(offset))
        candidates = []

        # 1) The convex surface (quarter circle): push the marble outward.
        if d > 1e-9 and self._on_arc(center, block.get_convex_arc, offset) \
                and d < R + radius + margin:
            candidates.append((offset / d, R + radius - d))

        # 2) The straight legs (top and left), rotated with the block.
        for p1, p2, normal in block.get_convex_legs:
            leg = self._segment_collision_fixed(marble, p1, p2, normal, margin)
            if leg is not None:
                candidates.append(leg)

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1])
        return candidates[0]

    def _on_arc(self, center, arc_pts, offset):
        """True when the marble's direction from an arc's center lies on the arc.

        ``arc_pts`` are the sampled points of a quarter arc; the arc's angular
        span is measured from its first endpoint to its last endpoint around
        the center. This is the shared truncation behind both the curved slope
        and the pipe bend's channel walls: it keeps an arc collision from
        firing beyond the actual solid region.
        """
        end0 = arc_pts[0]
        end1 = arc_pts[-1]
        a0 = math.degrees(math.atan2(end0[1] - center[1], end0[0] - center[0])) % 360
        a1 = math.degrees(math.atan2(end1[1] - center[1], end1[0] - center[0])) % 360
        sweep = (a1 - a0) % 360
        a = math.degrees(math.atan2(offset[1], offset[0])) % 360
        return ((a - a0) % 360) <= sweep

    def _on_curved_arc(self, block, center, offset):
        """True when the marble's direction from the arc center lies on the arc."""
        return self._on_arc(center, block.get_curved_arc, offset)

    def _flat_line_collision(self, marble, block, margin=0.0):
        """Return (normal, penetration) for a flat-line block, or None.

        A flat line is a thin horizontal surface along the bottom of the cell:
        the marble rides/rests on it like a floor but can slip off the ends.
        """
        points = block.get_flat_line_points
        if len(points) < 2:
            return None
        result = self._check_segment_collision(marble, points[0], points[1],
                                               block, margin)
        if result is not None:
            normal, distance = result
            return normal, max(0.0, marble.radius - distance)
        return None

    def _curved_line_collision(self, marble, block, margin=0.0):
        """Return (normal, penetration) for a curved-slope-line block, or None.

        The curved slope line is the curved slope's quarter-arc surface with
        its straight (right/bottom) legs removed, so the only hit surface is
        the arc itself.
        """
        center = block.get_curved_center
        R = float(block.rect.width)
        offset = marble.position - center
        d = float(np.linalg.norm(offset))
        if d <= 1e-9:
            return None
        arc_dist = abs(d - R)
        if arc_dist < marble.radius + margin and self._on_curved_arc(block, center, offset):
            # Two-sided: push the marble back to the side it came from (R -
            # radius inside the curve, R + radius outside it), using the
            # pre-move position so a fast crossing doesn't flip the side.
            pre = (marble._pre_move_position if marble._pre_move_position is not None
                   else marble.position)
            outward = float(np.linalg.norm(pre - center)) >= R
            normal = offset / d if outward else -offset / d
            return (normal, max(0.0, marble.radius - arc_dist))
        return None

    def _half_pipe_collision(self, marble, block, margin=0.0):
        """Return (normal, penetration) for a half-pipe block, or None.

        A half-pipe is the bottom semicircle of the cell: a thin arc line whose
        diameter edge is missing (the top is open). Like the other thin line
        shapes it is solid on BOTH sides — a marble inside the bowl rides the
        concave face at R - radius from the cell center and one outside rides
        the convex face at R + radius.
        """
        center = np.array(block.rect.center, dtype=float)
        R = float(block.rect.width) / 2.0
        offset = marble.position - center
        d = float(np.linalg.norm(offset))
        if d <= 1e-9:
            return None
        arc_dist = abs(d - R)
        if arc_dist < marble.radius + margin \
                and self._on_arc(center, block.get_half_pipe_points, offset):
            pre = (marble._pre_move_position if marble._pre_move_position is not None
                   else marble.position)
            outward = float(np.linalg.norm(pre - center)) >= R
            normal = offset / d if outward else -offset / d
            return (normal, max(0.0, marble.radius - arc_dist))
        return None

    def _slope_collision(self, marble, block, margin=0.0):
        """Return (normal, penetration) for a slope/line block, or None."""
        if block.shape == Shape.SLOPE:
            points = block.get_slope_points
            if len(points) < 2:
                return None
            candidates = []
            for p1, p2 in [(points[0], points[1]), (points[1], points[2]), (points[2], points[0])]:
                result = self._check_segment_collision(marble, p1, p2, block, margin)
                if result is not None:
                    candidates.append(result)
            if candidates:
                candidates.sort(key=lambda item: item[1])
                normal, distance = candidates[0]
                return normal, max(0.0, marble.radius - distance)
            if marble.position[1] > block.rect.bottom and block.is_point_inside_slope(marble.position):
                return block.get_slope_surface_normal, marble.radius
            return None

        if block.shape == Shape.LINE:
            points = block.get_slope_line_points
            if len(points) < 2:
                return None
            result = self._check_segment_collision(marble, points[0], points[1], block, margin)
            if result is not None:
                normal, distance = result
                return normal, max(0.0, marble.radius - distance)
            return None

        return None

    def check_wall_collision(self, marble, block):
        """Check if marble is colliding with a wall/bouncy block. Returns normal if collision."""
        block_rect = block.rect

        closest_x = max(block_rect.left, min(marble.position[0], block_rect.right))
        closest_y = max(block_rect.top, min(marble.position[1], block_rect.bottom))
        closest_point = np.array([closest_x, closest_y])
        dist_vec = marble.position - closest_point
        distance = np.linalg.norm(dist_vec)

        if distance < marble.radius:
            is_corner = (
                np.isclose(closest_x, block_rect.left) or np.isclose(closest_x, block_rect.right)
            ) and (
                np.isclose(closest_y, block_rect.top) or np.isclose(closest_y, block_rect.bottom)
            )

            if is_corner:
                corner_vec = marble.position - closest_point
                corner_distance = np.linalg.norm(corner_vec)
                if corner_distance > 0:
                    return corner_vec / corner_distance
                return np.array([-1.0, -1.0]) / SQRT_2

            if distance > 0:
                if abs(dist_vec[0]) > abs(dist_vec[1]) or (
                    abs(dist_vec[0]) == abs(dist_vec[1])
                    and abs(marble.velocity[0]) >= abs(marble.velocity[1])
                ):
                    return np.array([1.0, 0.0]) if dist_vec[0] > 0 else np.array([-1.0, 0.0])
                return np.array([0.0, 1.0]) if dist_vec[1] > 0 else np.array([0.0, -1.0])

            return self._calculate_rect_normal(marble, block_rect)

        return None

    def _get_edge_normal(self, marble, p1, p2, block):
        """Return an outward normal for a slope edge."""
        p1 = np.array(p1, dtype=float)
        p2 = np.array(p2, dtype=float)
        line_vec = p2 - p1
        perpendicular = np.array([-line_vec[1], line_vec[0]], dtype=float)
        perpendicular_norm = np.linalg.norm(perpendicular)
        if perpendicular_norm == 0:
            return None

        perpendicular = perpendicular / perpendicular_norm
        midpoint = (p1 + p2) / 2.0
        if block.shape == Shape.SLOPE:
            centroid = np.mean(np.array(block.get_slope_points), axis=0)
            vector_to_centroid = centroid - midpoint
            if np.dot(perpendicular, vector_to_centroid) > 0:
                perpendicular = -perpendicular
        else:
            if block.shape == Shape.FLAT_LINE:
                reference = block.get_flat_surface_normal
            else:
                reference = block.get_slope_surface_normal
            probe = marble._pre_move_position if marble._pre_move_position is not None else marble.position
            d = np.dot(probe - midpoint, reference)
            if d < 0:
                reference = -reference
            perpendicular = reference
        return perpendicular

    def _check_segment_collision(self, marble, p1, p2, block, margin=0.0):
        """Check collision against a line segment and return a suitable collision normal and distance."""
        p1 = np.array(p1, dtype=float)
        p2 = np.array(p2, dtype=float)
        line_vec = p2 - p1
        point_vec = marble.position - p1

        line_len_sq = np.dot(line_vec, line_vec)
        if line_len_sq == 0:
            return None

        t = np.dot(point_vec, line_vec) / line_len_sq
        t = max(0.0, min(1.0, t))

        closest = p1 + t * line_vec
        dist_vec = marble.position - closest
        distance = np.linalg.norm(dist_vec)

        if distance < marble.radius + margin:
            if abs(t) < 1e-6 or abs(t - 1.0) < 1e-6:
                corner = p1 if abs(t) < 1e-6 else p2
                corner_vec = marble.position - corner
                corner_distance = np.linalg.norm(corner_vec)
                if corner_distance < marble.radius:
                    if corner_distance > 0:
                        return corner_vec / corner_distance, corner_distance
                    return np.array([-1.0, -1.0]) / SQRT_2, 0.0

            if block.shape in (Shape.SLOPE, Shape.LINE, Shape.FLAT_LINE):
                normal = self._get_edge_normal(marble, p1, p2, block)
                if normal is not None:
                    return normal, distance

            if distance > 0:
                return dist_vec / distance, distance

            perpendicular = np.array([-line_vec[1], line_vec[0]], dtype=float)
            perpendicular_norm = np.linalg.norm(perpendicular)
            if perpendicular_norm == 0:
                return None
            return perpendicular / perpendicular_norm, distance

        return None

    def check_slope_collision(self, marble, block):
        """Check if marble is colliding with a slope or a sloped line segment."""
        if block.shape == Shape.SLOPE:
            points = block.get_slope_points
            if len(points) < 2:
                return None

            candidates = []
            for p1, p2 in [(points[0], points[1]), (points[1], points[2]), (points[2], points[0])]:
                result = self._check_segment_collision(marble, p1, p2, block)
                if result is not None:
                    candidates.append(result)

            if candidates:
                candidates.sort(key=lambda item: item[1])
                return candidates[0][0]

            if marble.position[1] > block.rect.bottom and block.is_point_inside_slope(marble.position):
                return block.get_slope_surface_normal

            return None

        if block.shape == Shape.LINE:
            points = block.get_slope_line_points
            if len(points) < 2:
                return None
            result = self._check_segment_collision(marble, points[0], points[1], block)
            if result is not None:
                return result[0]
            return None

        return None

    def resolve_marble_collisions(self, marbles):
        """Collide marbles with each other.

        Split marbles share the board, so any two that overlap are pushed apart
        along the line between their centers and exchange their velocity along
        that line (a fully elastic hit weighted by mass — equal masses simply
        swap their normal speeds). That is what lets a splitter's copy collide
        with the marble it came from. A phasing marble is skipped entirely: the
        phase effect passes through everything, other marbles included.
        """
        active = [m for m in marbles if getattr(m, "phase_timer", 0.0) <= 0]
        for index, a in enumerate(active):
            for b in active[index + 1:]:
                offset = np.array(b.position, dtype=float) - np.array(a.position, dtype=float)
                distance = float(np.linalg.norm(offset))
                overlap = a.radius + b.radius - distance
                if overlap <= 0:
                    continue
                normal = offset / distance if distance > 1e-9 else np.array([0.0, -1.0])
                total_mass = a.mass + b.mass
                if total_mass <= 0:
                    continue
                # Separate them in proportion to the other marble's mass, so a
                # heavy marble shoves a light one further.
                a.position -= normal * overlap * (b.mass / total_mass)
                b.position += normal * overlap * (a.mass / total_mass)
                # Only respond while they are still moving into each other.
                a_normal = float(np.dot(a.velocity, normal))
                b_normal = float(np.dot(b.velocity, normal))
                if a_normal - b_normal <= 0:
                    continue
                impulse = 2.0 * (a_normal - b_normal) / total_mass
                a.velocity = a.velocity - normal * (impulse * b.mass)
                b.velocity = b.velocity + normal * (impulse * a.mass)

    def _effect_boost(self, marble):
        """How much harder effect pushes act on a light marble (1 / mass).

        A ping-pong ball (mass 0.35) is flung/pulled ~2.86x harder by pistons,
        bouncy blocks, rotating shapes, accelerators, and black holes; a normal
        marble (mass 1) is unchanged, and a heavier marble is pushed less.
        Gravity is NOT boosted (see update), so light marbles fall normally.
        The marble-weight trial multiplies the mass used for these pushes only
        (marble.effect_mass_mult): 2.0 heavy halves them, 0.5 light doubles
        them, and fall speed (which reads marble.mass) is never affected.
        """
        mass = getattr(marble, "mass", 1.0) * getattr(marble, "effect_mass_mult", 1.0)
        return 1.0 / mass if mass > 0 else 1.0

    def resolve_collision(self, marble, block, normal):
        """Resolve a collision with a wall or slope (only when moving into the surface)."""
        is_wall = block.shape == Shape.RECT
        vel_normal_component = np.dot(marble.velocity, normal)
        if vel_normal_component < 0:
            vel_normal = vel_normal_component * normal
            vel_tangent = marble.velocity - vel_normal
            boost = self._effect_boost(marble)
            if block.has_effect(Effect.STICKY):
                # Sticky blocks damp the marble by its impact speed (a faster
                # hit keeps less of its speed) and pin it in place for the
                # block's own rolled hold time (see the pin/release at the top
                # of update).
                speed = float(np.linalg.norm(marble.velocity))
                keep = max(STICKY_MIN_KEEP, 1.0 / (1.0 + speed / STICKY_SPEED_REF))
                marble.sticky_velocity = marble.velocity * keep
                marble.sticky_timer = block.effect_magnitude(Effect.STICKY)
                marble.velocity *= 0.0
            else:
                # Bouncy reflection is an effect push (a light marble is flung
                # back harder, ~1/mass); plain surfaces use the marble's own
                # bounciness. The bouncy-castle trial makes every solid block
                # reflect the marble like a bouncy block.
                if (block.has_effect(Effect.BOUNCY) or getattr(marble, "bouncy", False)
                        or getattr(marble, "bouncy_castle", False)):
                    # The bouncy block's own bounce strength (its rolled % of the
                    # impact speed); the trials/marbles use the average.
                    bouncy = (block.effect_magnitude(Effect.BOUNCY) / 100.0
                              if block.has_effect(Effect.BOUNCY) else BOUNCY_RESTITUTION)
                    restitution = bouncy * boost
                else:
                    restitution = getattr(marble, "restitution", RESTITUTION)
                if block.has_effect(Effect.PISTON):
                    # A piston launches the marble at a fixed speed along the
                    # surface normal, regardless of how fast it arrived (the
                    # block's own rolled launch speed). A light marble
                    # (ping-pong) is launched much harder (1 / mass).
                    marble.velocity = (vel_tangent
                                       + block.effect_magnitude(Effect.PISTON) * boost * normal)
                elif block.has_effect(Effect.ROTATE):
                    # A rotating shape flings the marble along its spin: keep
                    # the normal response and add a strong tangential launch in
                    # the direction the shape is rotating (harder for a light
                    # marble, and harder for a faster-spinning block — the fling
                    # scales with the block's own rolled spin speed).
                    spin = block.effect_magnitude(Effect.ROTATE)
                    fling = ROTATE_FLING * (spin / ROTATE_SPEED) if ROTATE_SPEED else ROTATE_FLING
                    marble.velocity = (vel_tangent - vel_normal * restitution
                                       + fling * boost * self._rotate_tangent(marble, block, normal))
                else:
                    # Bouncy blocks (and rubber-ball marbles) reflect the normal
                    # component; other surfaces reflect it with the marble's own
                    # slight bounciness (ping-pong) or remove it (vanilla).
                    marble.velocity = vel_tangent - vel_normal * restitution
            friction = FRICTION_COEFFICIENT if is_wall else ROLLING_FRICTION
            if block.has_effect(Effect.SLIPPERY):
                # Slippery blocks apply no friction, so the marble keeps all of
                # its tangential speed as it slides/rolls over them.
                friction = 0.0
            if np.linalg.norm(vel_tangent) > 0 and not block.has_effect(Effect.STICKY):
                friction_force = -vel_tangent * friction
                marble.velocity += friction_force * DT
        marble.grounded = True
        marble.on_slope = not is_wall

    def _rotate_tangent(self, marble, block, normal):
        """Unit tangent along a rotating shape's spin direction at the contact point."""
        center = np.array(block.rect.center, dtype=float)
        radius_vec = marble.position - center
        if np.linalg.norm(radius_vec) < 1e-9:
            radius_vec = normal
        tangent = np.array([-radius_vec[1], radius_vec[0]], dtype=float)
        tangent /= np.linalg.norm(tangent)
        return tangent * math.copysign(1.0, ROTATE_SPEED)

    def _calculate_rect_normal(self, marble, rect):
        """Calculate the closest normal from marble to rectangle edge"""
        center = marble.position
        rect_center = np.array([rect.centerx, rect.centery])

        dx = center[0] - rect_center[0]
        dy = center[1] - rect_center[1]

        if abs(dx) * rect.height > abs(dy) * rect.width:
            return np.array([1.0 if dx > 0 else -1.0, 0.0])
        else:
            return np.array([0.0, 1.0 if dy > 0 else -1.0])

    def keep_in_bounds(self, marble):
        """Keep marble within screen bounds"""
        collision = False
        # Rubber-ball marbles bounce off the marble-box borders with full
        # energy; a ping-pong ball bounces back a little (its restitution);
        # other marbles just stop at the edge.
        if getattr(marble, "bouncy", False):
            bounce = BOUNCY_RESTITUTION
        else:
            bounce = getattr(marble, "restitution", RESTITUTION)

        if marble.position[0] - marble.radius < MARBLE_BOX_COORDS[0]:
            marble.position[0] = marble.radius + MARBLE_BOX_COORDS[0]
            marble.velocity[0] = abs(marble.velocity[0]) * bounce
            collision = True
        elif marble.position[0] + marble.radius > MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2]:
            marble.position[0] = MARBLE_BOX_COORDS[0] + MARBLE_BOX_COORDS[2] - marble.radius
            marble.velocity[0] = -abs(marble.velocity[0]) * bounce
            collision = True
        if marble.position[1] - marble.radius < MARBLE_BOX_COORDS[1]:
            marble.position[1] = marble.radius + MARBLE_BOX_COORDS[1]
            marble.velocity[1] = abs(marble.velocity[1]) * bounce
            collision = True
        elif marble.position[1] + marble.radius > MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3]:
            marble.position[1] = MARBLE_BOX_COORDS[1] + MARBLE_BOX_COORDS[3] - marble.radius
            marble.velocity[1] = -abs(marble.velocity[1]) * bounce
            collision = True
            marble.grounded = True

        # The all-finishes trial makes the marble-box borders act as a finish:
        # touching one ends the marble's run.
        if collision and getattr(marble, "finish_on_border", False):
            marble.finished = True

        if not collision and not marble.on_slope:
            marble.grounded = False
