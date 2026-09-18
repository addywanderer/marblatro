import math
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np

import achievements
import collection
import main
import metagame
import save_system


class CollisionBehaviorTests(unittest.TestCase):
    def setUp(self):
        # These tests build Games, and a Game touches the player's data files
        # (it creates the save slots). Point every one of them at a throwaway
        # folder so the suite can never write into a real profile.
        self._tmp = tempfile.mkdtemp()
        self._old_saves_dir = save_system.SAVES_DIR
        self._old_ach_file = achievements.FILE_PATH
        self._old_meta_file = metagame.FILE_PATH
        self._old_collection_file = collection.FILE_PATH
        save_system.SAVES_DIR = os.path.join(self._tmp, "saves")
        achievements.FILE_PATH = os.path.join(self._tmp, "achievements.json")
        metagame.FILE_PATH = os.path.join(self._tmp, "metagame.json")
        collection.FILE_PATH = os.path.join(self._tmp, "collection.json")
        achievements.reset()
        metagame.reset()
        collection.reset()

    def tearDown(self):
        save_system.SAVES_DIR = self._old_saves_dir
        achievements.FILE_PATH = self._old_ach_file
        metagame.FILE_PATH = self._old_meta_file
        collection.FILE_PATH = self._old_collection_file
        achievements.reset()
        metagame.reset()
        collection.reset()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_accelerator_pushes_resting_marble_along_arrow_direction(self):
        # Arrow points right (angle 90): a marble resting on top should be
        # pushed right and roll off, even though it is not penetrating the block.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.ACCELERATOR,
                           scorer=main.Scorer.NONE, angle=90)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS - 1)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])

        self.assertGreater(marble.position[0], block.rect.centerx + 30)

    def test_accelerator_launches_rolling_marble_up(self):
        # Arrow points up (angle 0): a marble rolling across the top gets
        # launched upward.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.ACCELERATOR,
                           scorer=main.Scorer.NONE, angle=0)
        marble = main.Marble(block.rect.left - 20, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([150.0, 0.0])
        min_y = marble.position[1]

        for _ in range(90):
            marble.physics.update(marble, main.DT, [block])
            min_y = min(min_y, marble.position[1])

        self.assertLess(min_y, block.rect.top - 10)

    def test_piston_launches_marble_up_at_fixed_speed(self):
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.PISTON,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 40)
        marble.velocity = np.array([0.0, 300.0])

        min_vy = 0.0
        for _ in range(40):
            marble.physics.update(marble, main.DT, [block])
            min_vy = min(min_vy, float(marble.velocity[1]))

        self.assertLessEqual(min_vy, -main.PISTON_FORCE * 0.9)

    def test_piston_launches_along_surface_normal(self):
        block = main.Block(5, 10, shape=main.Shape.RECT, effect=main.Effect.PISTON,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.left - 40, block.rect.centery)
        marble.velocity = np.array([400.0, 0.0])

        min_vx = 0.0
        for _ in range(15):
            marble.physics.update(marble, main.DT, [block])
            if marble.velocity[0] < 0:
                min_vx = min(min_vx, float(marble.velocity[0]))

        self.assertLessEqual(min_vx, -main.PISTON_FORCE * 0.9)

    def test_piston_launch_is_fixed_not_velocity_dependent(self):
        def rebound(impact_speed):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.PISTON,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 40)
            marble.velocity = np.array([0.0, impact_speed])
            min_vy = 0.0
            for _ in range(40):
                marble.physics.update(marble, main.DT, [block])
                min_vy = min(min_vy, float(marble.velocity[1]))
            return abs(min_vy)

        slow = rebound(200.0)
        fast = rebound(900.0)

        # Both are launched at PISTON_FORCE regardless of incoming speed
        # (unlike bouncy, whose rebound scales with the impact velocity).
        self.assertAlmostEqual(slow, main.PISTON_FORCE, delta=main.PISTON_FORCE * 0.15)
        self.assertAlmostEqual(fast, main.PISTON_FORCE, delta=main.PISTON_FORCE * 0.15)

    def test_gravity_block_redirects_falling_direction(self):
        # A gravity block whose indicator points right (angle 90) pulls a marble
        # resting on it rightward instead of letting it fall straight down.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.GRAVITY,
                           scorer=main.Scorer.NONE, angle=90)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS - 1)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])

        # The marble slid off the right side of the block rather than staying put
        # (with default down-gravity it would rest still at its spawn x).
        self.assertGreater(marble.position[0], block.rect.right)

    def test_gravity_defaults_to_down_without_gravity_block(self):
        start_x = main.MARBLE_BOX_COORDS[0] + main.MARBLE_BOX_COORDS[2] // 2
        marble = main.Marble(start_x, 150)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(30):
            marble.physics.update(marble, main.DT, [])

        # Without any gravity block the marble falls straight down.
        self.assertGreater(marble.position[1], 150.0)
        self.assertAlmostEqual(marble.position[0], start_x, delta=1e-6)

    def test_gravity_effect_is_shop_available_and_priced(self):
        self.assertIn(main.Effect.GRAVITY, main.Effect.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.GRAVITY)], 0)

    def test_dead_zone_trial_triples_gravity_in_bottom_third(self):
        box = main.MARBLE_BOX_COORDS
        bottom_third = box[1] + 2 * box[3] / 3

        normal = main.Marble(box[0] + 100, bottom_third + 20)
        normal.velocity = np.array([0.0, 0.0])
        normal.physics.update(normal, main.DT, [])
        self.assertAlmostEqual(normal.velocity[1], main.GRAVITY * main.DT, places=5)

        zone = main.Marble(box[0] + 100, bottom_third + 20)
        zone.dead_zone = True
        zone.velocity = np.array([0.0, 0.0])
        zone.physics.update(zone, main.DT, [])
        self.assertAlmostEqual(zone.velocity[1], 3 * main.GRAVITY * main.DT, places=5)

        # Above the bottom third the dead zone has no effect.
        above = main.Marble(box[0] + 100, box[1] + 20)
        above.dead_zone = True
        above.velocity = np.array([0.0, 0.0])
        above.physics.update(above, main.DT, [])
        self.assertAlmostEqual(above.velocity[1], main.GRAVITY * main.DT, places=5)

    def test_heavier_marble_falls_faster(self):
        # Mass scales gravity acceleration: a heavier marble (the Singularity
        # final boss) accelerates downward faster, while a normal marble
        # (mass 1) is unchanged.
        box = main.MARBLE_BOX_COORDS
        normal = main.Marble(box[0] + 100, box[1] + 200)
        heavy = main.Marble(box[0] + 100, box[1] + 200)
        heavy.mass = 3.0
        normal.physics.update(normal, main.DT, [])
        heavy.physics.update(heavy, main.DT, [])
        self.assertAlmostEqual(normal.velocity[1], main.GRAVITY * main.DT, places=5)
        self.assertAlmostEqual(heavy.velocity[1], 3 * main.GRAVITY * main.DT, places=5)

    def test_ping_pong_type_is_defined_and_described(self):
        self.assertIn(main.MarbleType.PING_PONG, main.MarbleType.ORDER)
        self.assertEqual(main.MarbleType.PING_PONG, 3)
        self.assertEqual(main.MarbleType.name(main.MarbleType.PING_PONG),
                         "Ping-Pong Ball")
        desc = main.MarbleType.description(main.MarbleType.PING_PONG).lower()
        self.assertIn("light", desc)
        self.assertIn("bounce", desc)

    def test_ping_pong_falls_at_same_speed_as_normal(self):
        # Gravity does not scale below mass 1, so the very light ping-pong ball
        # falls at the same speed as a normal marble (like real life).
        box = main.MARBLE_BOX_COORDS
        normal = main.Marble(box[0] + 100, box[1] + 200)
        light = main.Marble(box[0] + 100, box[1] + 200)
        light.mass = main.PING_PONG_MASS
        normal.physics.update(normal, main.DT, [])
        light.physics.update(light, main.DT, [])
        self.assertAlmostEqual(normal.velocity[1], main.GRAVITY * main.DT, places=5)
        self.assertAlmostEqual(light.velocity[1], main.GRAVITY * main.DT, places=5)

    def test_ping_pong_bounces_slightly_off_block(self):
        # A ping-pong ball bounces back a little off a plain block (0.35 of the
        # incoming normal speed) instead of stopping like a vanilla marble.
        block = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, 0)
        marble.velocity = np.array([0.0, 100.0])
        marble.restitution = main.PING_PONG_RESTITUTION
        marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
        self.assertAlmostEqual(float(marble.velocity[1]),
                               -100.0 * main.PING_PONG_RESTITUTION, places=3)

    def test_ping_pong_bounces_slightly_off_border(self):
        # The slight bounce also applies to the marble-box borders.
        marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 5, 300)
        marble.velocity = np.array([-100.0, 0.0])
        marble.restitution = main.PING_PONG_RESTITUTION
        marble.physics.keep_in_bounds(marble)
        self.assertAlmostEqual(float(marble.velocity[0]),
                               100.0 * main.PING_PONG_RESTITUTION, places=3)

    def test_ping_pong_piston_launches_harder(self):
        # A piston launches a light marble at ~1/mass the speed of a normal one.
        def launch(mass):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.PISTON,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 40)
            marble.velocity = np.array([0.0, 300.0])
            marble.mass = mass
            min_vy = 0.0
            for _ in range(40):
                marble.physics.update(marble, main.DT, [block])
                min_vy = min(min_vy, float(marble.velocity[1]))
            return abs(min_vy)

        normal = launch(1.0)
        light = launch(main.PING_PONG_MASS)
        self.assertGreater(light, normal)
        self.assertGreaterEqual(light, main.PISTON_FORCE / main.PING_PONG_MASS * 0.9)

    def test_ping_pong_accelerator_pushes_much_harder(self):
        def travel(mass, frames):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.ACCELERATOR,
                               scorer=main.Scorer.NONE, angle=90)
            marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS - 1)
            marble.velocity = np.array([0.0, 0.0])
            marble.mass = mass
            for _ in range(frames):
                marble.physics.update(marble, main.DT, [block])
            return float(marble.position[0])

        # A few frames in, the light marble has already been pushed much farther
        # right than a normal one (before either hits the right border).
        normal = travel(1.0, 8)
        light = travel(main.PING_PONG_MASS, 8)
        self.assertGreater(light, normal + 25.0)

    def test_ping_pong_black_hole_pulls_harder(self):
        def travel(mass, frames):
            block = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.BLACK_HOLE,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx - 100, block.rect.centery)
            marble.velocity = np.array([0.0, 0.0])
            marble.mass = mass
            for _ in range(frames):
                marble.physics.update(marble, main.DT, [block])
            return float(marble.position[0]) - (block.rect.centerx - 100)

        # Within the first few frames the light marble is pulled much farther
        # toward the hole than a normal one (before it reaches the block face).
        normal = travel(1.0, 5)
        light = travel(main.PING_PONG_MASS, 5)
        self.assertGreater(light, normal + 15.0)

    def test_ping_pong_bouncy_block_reflects_harder(self):
        # Bouncy reflection is an effect push, so a light marble leaves a
        # bouncy block much faster than it arrived (~1/mass the rebound).
        def rebound(mass):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, 0)
            marble.velocity = np.array([0.0, 100.0])
            marble.mass = mass
            marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
            return abs(float(marble.velocity[1]))

        normal = rebound(1.0)  # full bounce: ~100
        light = rebound(main.PING_PONG_MASS)
        self.assertGreater(light, normal + 50.0)

    def test_ping_pong_rotate_fling_is_harder(self):
        # A rotating shape's tangential fling is also an effect push: a light
        # marble is flung ~1/mass harder than a normal one.
        def fling_speed(mass):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.ROTATE,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
            marble.velocity = np.array([0.0, 200.0])
            marble.mass = mass
            marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
            return float(np.linalg.norm(marble.velocity))

        normal = fling_speed(1.0)
        light = fling_speed(main.PING_PONG_MASS)
        self.assertGreater(light, normal + 5.0)

    def test_flat_line_shape_defined_and_priced(self):
        self.assertIn(main.Shape.FLAT_LINE, main.Shape.ORDER)
        self.assertEqual(main.Shape.name(main.Shape.FLAT_LINE), "Flat Line")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE,
                                                 main.Shape.FLAT_LINE)], 0)
        self.assertIn("bottom", main.shape_description(main.Shape.FLAT_LINE))

    def test_bouncy_castle_trial_reflects_off_plain_block(self):
        # Under bouncy castle every solid block reflects like a bouncy block:
        # a vanilla marble hitting a plain (non-bouncy) RECT bounces back.
        def rebound(bouncy_castle):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.NONE,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, 0)
            marble.velocity = np.array([0.0, 100.0])
            marble.bouncy_castle = bouncy_castle
            marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
            return abs(float(marble.velocity[1]))

        self.assertAlmostEqual(rebound(True), 100.0, delta=1.0)  # full bounce
        self.assertAlmostEqual(rebound(False), 0.0, delta=1.0)  # plain wall stops it

    def test_crumbling_trial_block_shatters_like_fragile(self):
        # A block marked trial_fragile (the crumbling trial) shatters into a
        # no-hitbox field when a marble touches and leaves it, exactly like a
        # real fragile block — but it does NOT count as a wrecking-ball break.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.NONE,
                           scorer=main.Scorer.NONE)
        block.trial_fragile = True
        marble = main.Marble(block.rect.left - 10, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([400.0, 0.0])
        for _ in range(40):
            marble.physics.update(marble, main.DT, [block])
            if block.shape == main.Shape.NONE:
                break
        self.assertEqual(block.shape, main.Shape.NONE)
        self.assertFalse(getattr(block, "broke_fragile_this_frame", False))

    def test_marble_weight_trial_scales_effect_pushes(self):
        # The marble-weight trial multiplies the mass used for effect pushes
        # only: a heavy marble (effect_mass_mult 2.0) is flung less by a
        # piston, a light one (0.5) flung more.
        def fling(mult):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.PISTON,
                               scorer=main.Scorer.NONE)
            marble = main.Marble(block.rect.centerx, block.rect.top - 40)
            marble.velocity = np.array([0.0, 300.0])
            marble.effect_mass_mult = mult
            marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
            return float(np.linalg.norm(marble.velocity))

        heavy = fling(2.0)
        light = fling(0.5)
        self.assertAlmostEqual(heavy, main.PISTON_FORCE / 2.0, delta=main.PISTON_FORCE * 0.1)
        self.assertAlmostEqual(light, main.PISTON_FORCE / 0.5, delta=main.PISTON_FORCE * 0.1)

    def test_marble_weight_trial_does_not_change_fall_speed(self):
        # Fall speed reads marble.mass, not effect_mass_mult, so a "heavy"
        # trial marble still falls at the same rate as a normal one.
        def fall_y(mult):
            marble = main.Marble(300, 100)
            marble.velocity = np.array([0.0, 0.0])
            marble.effect_mass_mult = mult
            for _ in range(20):
                marble.physics.update(marble, main.DT, [])
            return float(marble.position[1])

        self.assertAlmostEqual(fall_y(2.0), fall_y(1.0), delta=1.0)
        self.assertAlmostEqual(fall_y(0.5), fall_y(1.0), delta=1.0)

    def test_flat_line_rests_marble_like_a_floor(self):
        # A flat line sits just inside the bottom of its cell and holds a
        # falling marble on top of it (a thin floor).
        block = main.Block(5, 8, shape=main.Shape.FLAT_LINE, scorer=main.Scorer.NONE)
        line_y = block.rect.bottom - 3  # the line is raised 3px into the cell
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS - 4)
        marble.velocity = np.array([0.0, 40.0])
        for _ in range(140):
            marble.physics.update(marble, main.DT, [block])
        self.assertLess(marble.position[1], block.rect.bottom + 2)  # never falls through
        self.assertAlmostEqual(float(marble.position[1]),
                               line_y - main.MARBLE_RADIUS, delta=6)

    def test_curved_slope_line_collides_only_on_its_arc(self):
        # The curved slope line is the curved slope with its straight legs
        # removed, so it only blocks marbles at the arc (not in the corner
        # region the legs would cover).
        def blocked(shape, px, py):
            block = main.Block(0, 0, shape=shape, scorer=main.Scorer.NONE)
            marble = main.Marble(px, py)
            return marble.physics._block_collision(marble, block) is not None

        center = (main.MARBLE_BOX_COORDS[0], main.MARBLE_BOX_COORDS[1])
        r = main.GRID_SIZE
        on_arc = (center[0] + r * math.cos(math.radians(45)),
                  center[1] + r * math.sin(math.radians(45)))
        self.assertTrue(blocked(main.Shape.CURVED_SLOPE, *on_arc))
        self.assertTrue(blocked(main.Shape.CURVED_SLOPE_LINE, *on_arc))
        # Bottom-right corner: the solid curved slope's legs catch the marble,
        # but the bare curved line (no legs) does not reach it.
        corner = (center[0] + main.GRID_SIZE - 2, center[1] + main.GRID_SIZE - 2)
        self.assertTrue(blocked(main.Shape.CURVED_SLOPE, *corner))
        self.assertFalse(blocked(main.Shape.CURVED_SLOPE_LINE, *corner))

    def test_curved_slope_line_defined_and_priced(self):
        self.assertIn(main.Shape.CURVED_SLOPE_LINE, main.Shape.ORDER)
        self.assertEqual(main.Shape.name(main.Shape.CURVED_SLOPE_LINE),
                         "Curved Slope Line")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE,
                                                 main.Shape.CURVED_SLOPE_LINE)], 0)
        self.assertIn("curve", main.shape_description(main.Shape.CURVED_SLOPE_LINE))

    def test_curved_slope_line_is_solid_on_both_sides(self):
        # The curved slope line used to be one-sided: a marble pressing into it
        # from the OUTER (convex) side passed straight through. Both faces of
        # the arc must now push the marble back to the side it came from.
        block = main.Block(0, 0, shape=main.Shape.CURVED_SLOPE_LINE,
                           scorer=main.Scorer.NONE)
        center = np.array(block.get_curved_center, dtype=float)
        radius = float(block.rect.width)
        u = np.array([math.cos(math.radians(45)), math.sin(math.radians(45))])

        def collide(pos_d, pre_d):
            marble = main.Marble(*(center + u * pos_d))
            marble._pre_move_position = center + u * pre_d
            return marble.physics._block_collision(marble, block)

        # Marble coming from OUTSIDE (pre farther than the arc) must be pushed
        # back outward, never allowed through to the inside.
        outer = collide(radius + 5, radius + 25)
        self.assertIsNotNone(outer)
        self.assertGreater(np.dot(outer[0], u), 0.85)  # outward along the radial
        # Marble coming from INSIDE (pre nearer the center) pushed inward.
        inner = collide(radius - 5, radius - 25)
        self.assertIsNotNone(inner)
        self.assertLess(np.dot(inner[0], u), -0.85)  # inward along the radial

    def test_half_pipe_shape_defined_and_priced(self):
        self.assertIn(main.Shape.HALF_PIPE, main.Shape.ORDER)
        self.assertEqual(main.Shape.name(main.Shape.HALF_PIPE), "Half Pipe")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE,
                                                 main.Shape.HALF_PIPE)], 0)
        desc = main.shape_description(main.Shape.HALF_PIPE).lower()
        self.assertIn("semicircle", desc)

    def test_half_pipe_arc_is_a_bottom_semicircle(self):
        # The half-pipe's diameter would run along the cell's middle horizontal
        # line; the drawn/blocking arc lives entirely in the BOTTOM half. Its
        # first/last sample points are the two ends of that diameter (which are
        # NOT connected by a straight edge) and its middle dips to the bottom.
        block = main.Block(0, 0, shape=main.Shape.HALF_PIPE, scorer=main.Scorer.NONE)
        pts = block.get_half_pipe_points
        self.assertEqual(len(pts), len(range(0, 181, 5)))
        cx, cy = block.rect.center
        first, mid, last = pts[0], pts[len(pts) // 2], pts[-1]
        self.assertAlmostEqual(first[0], block.rect.right, delta=0.5)
        self.assertAlmostEqual(first[1], cy, delta=0.5)
        self.assertAlmostEqual(last[0], block.rect.left, delta=0.5)
        self.assertAlmostEqual(last[1], cy, delta=0.5)
        self.assertAlmostEqual(mid[0], cx, delta=0.5)
        self.assertAlmostEqual(mid[1], block.rect.bottom, delta=0.5)
        # Every sample sits at or below the middle line (bottom half).
        for px, py in pts:
            self.assertGreaterEqual(py, cy - 0.5)
        # No point may peek above the cell's middle into the open mouth.
        self.assertFalse(any(py < cy - 0.5 for p in pts for py in (p[1],)))

    def test_half_pipe_is_solid_from_inside_and_outside(self):
        # The half-pipe arc is a thin line solid on both sides: a marble inside
        # the bowl rests at R - radius below the center, one outside the arc
        # rests at R + radius, and pressing past either face bounces back.
        block = main.Block(0, 0, shape=main.Shape.HALF_PIPE, scorer=main.Scorer.NONE)
        center = np.array(block.rect.center, dtype=float)
        radius = float(block.rect.width) / 2.0
        down = np.array([0.0, 1.0])

        def collide(pos_y, pre_y):
            marble = main.Marble(center[0], pos_y)
            marble._pre_move_position = np.array([center[0], pre_y])
            return marble.physics._block_collision(marble, block)

        # Pressing into the arc from INSIDE (above the bottom curve) -> push up.
        inner = collide(center[1] + (radius - 5), center[1] + (radius - 15))
        self.assertIsNotNone(inner)
        self.assertAlmostEqual(float(inner[0][0]), 0.0, delta=0.01)
        self.assertLess(float(inner[0][1]), 0.0)  # points up (toward the bowl)
        # Pressing into the arc from OUTSIDE (below the curve) -> push down.
        outer = collide(center[1] + (radius + 5), center[1] + (radius + 15))
        self.assertIsNotNone(outer)
        self.assertGreater(float(outer[0][1]), 0.0)  # points down (away)
        # Resting positions on both faces are stable (no overlap).
        self.assertIsNone(collide(center[1] + (radius - main.MARBLE_RADIUS),
                                  center[1] + (radius - main.MARBLE_RADIUS)))
        self.assertIsNone(collide(center[1] + (radius + main.MARBLE_RADIUS),
                                  center[1] + (radius + main.MARBLE_RADIUS)))
        # The mouth is open: a marble above the middle line is never blocked.
        self.assertIsNone(collide(center[1] - (radius - main.MARBLE_RADIUS),
                                  center[1] - (radius - main.MARBLE_RADIUS)))

    def test_marble_dropped_into_half_pipe_is_caught(self):
        # A marble dropped into the bowl falls to the concave floor and stays
        # there — it must never punch through the bottom of the curve.
        block = main.Block(4, 4, shape=main.Shape.HALF_PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top + 2)
        marble.velocity = np.array([0.0, 0.0])
        rest_y = block.rect.centery + block.rect.width / 2.0 - main.MARBLE_RADIUS
        lowest = marble.position[1]
        for _ in range(300):
            marble.physics.update(marble, main.DT, [block])
            lowest = max(lowest, float(marble.position[1]))
        self.assertAlmostEqual(float(marble.position[1]), rest_y, delta=3)
        # The marble's center never dropped past the bowl's floor line.
        self.assertLess(lowest, block.rect.bottom - main.MARBLE_RADIUS + 2)

    def test_sticky_effect_defined_and_priced(self):
        self.assertIn(main.Effect.STICKY, main.Effect.ORDER)
        self.assertIn(main.Effect.STICKY, main.Effect.REAL_ORDER)
        self.assertEqual(main.Effect.name(main.Effect.STICKY), "Sticky")
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT,
                                                 main.Effect.STICKY)], 0)
        # The description states the hold time it is rolled with.
        self.assertIn("holds them for 0.4 s (0)",
                      main.effect_description(main.Effect.STICKY))
        self.assertIn("holds them for 0.6 s (+0.2)",
                      main.effect_description(main.Effect.STICKY, 0.6))

    def test_sticky_damps_more_at_higher_impact(self):
        # A higher-speed collision keeps a smaller fraction of its speed.
        def kept(impact):
            block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.STICKY)
            marble = main.Marble(300, 300)
            marble.velocity = np.array([0.0, float(impact)])
            marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
            return abs(float(marble.sticky_velocity[1]))

        gentle = kept(200.0)
        fast = kept(4000.0)
        self.assertGreater(gentle / 200.0, fast / 4000.0 + 0.1)

    def test_sticky_pins_then_releases(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, effect=main.Effect.STICKY)
        marble = main.Marble(300, 300)
        marble.velocity = np.array([0.0, 200.0])
        marble.physics.resolve_collision(marble, block, np.array([0.0, -1.0]))
        self.assertAlmostEqual(marble.sticky_timer, main.STICKY_DURATION)
        # The next physics frame holds the marble still (pinned).
        marble.physics.update(marble, main.DT, [])
        self.assertAlmostEqual(float(np.linalg.norm(marble.velocity)), 0.0, places=3)
        # Once the stick expires the marble is released with its damped speed.
        for _ in range(int(main.STICKY_DURATION / main.DT) + 2):
            marble.physics.update(marble, main.DT, [])
        self.assertGreater(float(np.linalg.norm(marble.velocity)), 0.0)
        self.assertEqual(marble.sticky_timer, 0.0)

    def test_all_finishes_trial_finishes_marble_on_border(self):
        box = main.MARBLE_BOX_COORDS

        finisher = main.Marble(box[0] + 100, box[1] + 100)
        finisher.finish_on_border = True
        finisher.velocity = np.array([-500.0, 0.0])  # head for the left border
        for _ in range(120):
            finisher.physics.update(finisher, main.DT, [])
            if finisher.finished:
                break
        self.assertTrue(finisher.finished)

        # Without the flag the same marble just stops at the wall.
        plain = main.Marble(box[0] + 100, box[1] + 100)
        plain.velocity = np.array([-500.0, 0.0])
        for _ in range(120):
            plain.physics.update(plain, main.DT, [])
        self.assertFalse(plain.finished)

    def test_black_hole_pulls_marble_toward_block(self):
        block = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.BLACK_HOLE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx - 100, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])
        before_x = marble.position[0]

        for _ in range(30):
            marble.physics.update(marble, main.DT, [block])

        self.assertGreater(marble.position[0], before_x + 10)  # pulled right toward the hole

    def test_black_hole_pulls_marble_upward_against_gravity(self):
        block = main.Block(5, 3, shape=main.Shape.RECT, effect=main.Effect.BLACK_HOLE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery + 150)
        marble.velocity = np.array([0.0, 0.0])
        start_y = marble.position[1]
        min_y = start_y

        for _ in range(50):
            marble.physics.update(marble, main.DT, [block])
            min_y = min(min_y, marble.position[1])

        self.assertLess(min_y, start_y - 20)  # lifted up toward the hole

    def test_black_hole_pull_limited_to_range(self):
        block = main.Block(5, 2, shape=main.Shape.RECT, effect=main.Effect.BLACK_HOLE,
                           scorer=main.Scorer.NONE)
        far = main.Marble(block.rect.centerx, block.rect.centery + main.BLACK_HOLE_RANGE + 20)
        far.velocity = np.array([0.0, 0.0])
        start_x = far.position[0]

        far.physics.update(far, main.DT, [block])

        # Beyond the pull range there is no horizontal attraction.
        self.assertAlmostEqual(far.position[0], start_x, delta=0.5)

    def test_black_hole_effect_is_shop_available_and_priced(self):
        self.assertIn(main.Effect.BLACK_HOLE, main.Effect.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.BLACK_HOLE)], 0)

    def test_rotate_effect_is_shop_available_and_priced(self):
        self.assertIn(main.Effect.ROTATE, main.Effect.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.ROTATE)], 0)

    def test_rotate_block_spins_geometry_over_time(self):
        # A rotating block's effective angle advances every frame during a run.
        block = main.Block(5, 8, shape=main.Shape.LINE, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE, angle=0)
        marble = main.Marble(block.rect.centerx, block.rect.top - 100)
        marble.velocity = np.array([0.0, 0.0])
        start_angle = block.effective_angle

        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])

        self.assertGreater(block.spin, 0.0)
        self.assertNotEqual(block.effective_angle, start_angle)

    def test_reset_run_resets_rotating_block_spin(self):
        # Spin a rotating block, then starting a fresh run snaps it back to its
        # base angle (spin reset to 0).
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE, angle=0)
        marble = main.Marble(block.rect.centerx, block.rect.top - 100)
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])
        self.assertGreater(block.spin, 0.0)

        game = main.Game()
        game.grid[(5, 8)] = block
        game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(game.reset_run())
        self.assertEqual(block.spin, 0.0)
        self.assertEqual(block.effective_angle, 0.0)

    def test_rotate_block_flings_marble_tangentially(self):
        # A marble dropping onto a rotating rect's top face is flung along the
        # spin (tangential), not just bounced straight back.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([0.0, 200.0])  # moving down into the top face
        normal = np.array([0.0, -1.0])  # outward normal from the top face

        marble.physics.resolve_collision(marble, block, normal)

        # No downward (into-the-block) velocity remains, and a strong tangential
        # fling was applied along the spin direction.
        self.assertGreaterEqual(float(marble.velocity[1]), -1.0)
        self.assertGreater(np.linalg.norm(marble.velocity), main.ROTATE_FLING * 0.9)

    def test_rotate_rect_uses_oriented_hitbox(self):
        # At a 45 degree spin the rect is a diamond. Just outside the cell's
        # top-left corner the marble is clear of the diamond (an axis-aligned
        # rect would still collide there), while along the horizontal midline
        # it remains solid.
        block = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE)
        block.spin = 45.0
        block._refresh_geometry()

        empty_corner = main.Marble(block.rect.left - 1, block.rect.top - 1)
        self.assertIsNone(empty_corner.physics._block_collision(empty_corner, block))

        mid = main.Marble(block.rect.right - 2, block.rect.centery)
        self.assertIsNotNone(mid.physics._block_collision(mid, block))

    def test_slippery_effect_is_shop_available_and_priced(self):
        self.assertIn(main.Effect.SLIPPERY, main.Effect.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.SLIPPERY)], 0)

    def test_slippery_block_preserves_marble_speed(self):
        # A marble rolling across a normal rect is slowed by friction, while a
        # slippery rect applies no friction and keeps the marble's speed.
        def roll(frictionless):
            block = main.Block(5, 8, shape=main.Shape.RECT, scorer=main.Scorer.NONE,
                               effects=[main.Effect.SLIPPERY] if frictionless else [main.Effect.NONE])
            marble = main.Marble(block.rect.left - 10, block.rect.top - main.MARBLE_RADIUS)
            marble.velocity = np.array([180.0, 0.0])
            for _ in range(60):
                marble.physics.update(marble, main.DT, [block])
            return float(np.linalg.norm(marble.velocity))

        sticky_speed = roll(False)
        slick_speed = roll(True)
        # Slippery keeps far more of the marble's speed than a normal block.
        self.assertGreater(slick_speed, sticky_speed + 100.0)
        self.assertGreater(slick_speed, 150.0)

    def test_fragile_effect_is_shop_available_and_priced(self):
        self.assertIn(main.Effect.FRAGILE, main.Effect.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.EFFECT, main.Effect.FRAGILE)], 0)

    def test_fragile_block_shatters_after_marble_leaves(self):
        # A marble rolls over the fragile block (touching it), then falls off
        # the far edge; once it stops touching the block, the block shatters
        # into a no-hitbox field.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.left - 10, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([400.0, 0.0])
        touched = False
        for _ in range(40):
            marble.physics.update(marble, main.DT, [block])
            if block in marble.collisions_this_tick:
                touched = True
            if block.shape == main.Shape.NONE:
                break

        self.assertTrue(touched)  # the marble did roll over the block
        self.assertEqual(block.shape, main.Shape.NONE)  # ...then it shattered

    def test_fragile_block_stays_solid_while_touched(self):
        # A marble resting on top of a fragile block keeps touching it every
        # frame, so the block stays solid until the marble actually leaves.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([0.0, 200.0])
        for _ in range(5):
            marble.physics.update(marble, main.DT, [block])

        self.assertEqual(block.shape, main.Shape.RECT)
        self.assertIn(block, marble.collisions_this_tick)

    def test_reset_run_restores_broken_fragile_block(self):
        # A fragile block that shattered stays broken during the run, but
        # starting a fresh run rebuilds it to its original shape.
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.FRAGILE,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.left - 10, block.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([400.0, 0.0])
        for _ in range(40):
            marble.physics.update(marble, main.DT, [block])
            if block.shape == main.Shape.NONE:
                break
        self.assertEqual(block.shape, main.Shape.NONE)  # shattered

        game = main.Game()
        game.grid[(5, 8)] = block
        game.grid[(0, 0)] = main.Block(0, 0, scorer=main.Scorer.START)

        self.assertTrue(game.reset_run())

        self.assertEqual(block.shape, main.Shape.RECT)  # rebuilt
        self.assertIsNone(block._fragile_shape)  # ready to shatter again

    def test_pipe_shape_is_shop_available_and_priced(self):
        self.assertIn(main.Shape.PIPE, main.Shape.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.PIPE)], 0)
        self.assertIn("pipe", main.shape_description(main.Shape.PIPE).lower())

    def test_pipe_center_gap_is_open(self):
        # A pipe is a RECT minus a vertical marble-diameter strip down the
        # middle, so a marble centered in the gap does not collide.
        block = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        self.assertIsNone(marble.physics._block_collision(marble, block))

    def test_pipe_pillars_are_solid(self):
        block = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        # Just inside the left and right pillars.
        left = main.Marble(block.rect.left + 6, block.rect.centery)
        right = main.Marble(block.rect.right - 6, block.rect.centery)
        self.assertIsNotNone(left.physics._block_collision(left, block))
        self.assertIsNotNone(right.physics._block_collision(right, block))

    def test_marble_falls_through_pipe_gap(self):
        # A marble released above the pipe's center falls straight through the
        # gap between the two pillars.
        block = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 30)
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(90):
            marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.position[1], block.rect.bottom + 10)

    def test_pipe_draws_and_honors_rotation(self):
        surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        block = main.Block(0, 0, shape=main.Shape.PIPE, effect=main.Effect.ROTATE,
                           scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        block.draw(surface)  # axis-aligned pillars render
        block.spin = 45.0
        block._refresh_geometry()
        block.draw(surface)  # rotated pillars render without raising

    def test_pipe_base_angle_rotates_hitbox_without_rotate_effect(self):
        # A pipe rotated to 90 degrees via the A key (no ROTATE effect) becomes
        # two horizontal bars with a horizontal gap: the top bar is solid and a
        # marble centered in the horizontal gap passes through.
        block = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        block.angle = 90
        top_bar = main.Marble(block.rect.centerx, block.rect.top + 6)
        gap = main.Marble(block.rect.centerx, block.rect.centery)
        self.assertIsNotNone(top_bar.physics._block_collision(top_bar, block))
        self.assertIsNone(gap.physics._block_collision(gap, block))

    def test_pipe_base_angle_rotates_drawn_pillars(self):
        # Setting the base angle (as the A key does) rotates the drawn pillars.
        block = main.Block(4, 4, shape=main.Shape.PIPE, scorer=main.Scorer.NONE)
        pts_0 = block._get_pipe_pillar_points()
        block.angle = 90
        pts_90 = block._get_pipe_pillar_points()
        self.assertEqual(block.angle, 90)
        self.assertNotEqual(pts_0, pts_90)

    def test_effect_icons_rotate_with_block_angle(self):
        # The A key rotates the block; every effect icon rotates with it so the
        # icon stays aligned with the drawn shape. The portal's concentric
        # circles are rotation-invariant, so it is the only excluded effect.
        rotatable = (main.Effect.BOUNCY, main.Effect.PISTON, main.Effect.ACCELERATOR,
                     main.Effect.GRAVITY, main.Effect.BLACK_HOLE, main.Effect.ROTATE,
                     main.Effect.SLIPPERY, main.Effect.FRAGILE)
        for eff in rotatable:
            with self.subTest(effect=main.Effect.name(eff)):
                s0 = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
                s90 = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
                b0 = main.Block(0, 0, shape=main.Shape.RECT, effect=eff, origin=(0, 0))
                b90 = main.Block(0, 0, shape=main.Shape.RECT, effect=eff, origin=(0, 0), angle=90)
                b0.rect.topleft = (0, 0)
                b90.rect.topleft = (0, 0)
                b0.draw(s0)
                b90.draw(s90)
                self.assertNotEqual(
                    main.pygame.image.tobytes(s0, "RGBA"),
                    main.pygame.image.tobytes(s90, "RGBA"))

    def _drop_onto_size_block(self, effect):
        """Drop a marble onto a size-effect block; runs real physics.

        Returns the marble after its radius has changed (or after a timeout).
        """
        game = main.Game()
        game.title_screen = False
        game.run_active = True
        block = main.Block(4, 5, shape=main.Shape.RECT, effect=effect, scorer=main.Scorer.NONE)
        game.grid[(4, 5)] = block
        marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE + 20,
                             main.MARBLE_BOX_COORDS[1] + 2 * main.GRID_SIZE + 20)
        marble.velocity = np.array([0.0, 200.0])
        game.marbles.append(marble)
        for _ in range(60 * 3):
            game.update()
            if marble.radius != main.MARBLE_RADIUS:
                break
        return marble

    def test_growing_effect_doubles_marble_radius(self):
        marble = self._drop_onto_size_block(main.Effect.GROWING)
        self.assertEqual(marble.radius, main.MARBLE_RADIUS * 2)

    def test_shrinking_effect_halves_marble_radius(self):
        marble = self._drop_onto_size_block(main.Effect.SHRINKING)
        self.assertEqual(marble.radius, main.MARBLE_RADIUS * 0.5)

    def test_size_effect_does_not_stack_while_in_contact(self):
        # The radius change applies once per touch, not every frame while the
        # marble stays in contact, so a resting marble keeps the grown size.
        game = main.Game()
        game.title_screen = False
        game.run_active = True
        block = main.Block(4, 5, shape=main.Shape.RECT, effect=main.Effect.GROWING,
                           scorer=main.Scorer.NONE)
        game.grid[(4, 5)] = block
        marble = main.Marble(main.MARBLE_BOX_COORDS[0] + 4 * main.GRID_SIZE + 20,
                             main.MARBLE_BOX_COORDS[1] + 2 * main.GRID_SIZE + 20)
        marble.velocity = np.array([0.0, 200.0])
        game.marbles.append(marble)
        for _ in range(60 * 3):
            game.update()
            if marble.radius != main.MARBLE_RADIUS:
                break
        self.assertEqual(marble.radius, main.MARBLE_RADIUS * 2)
        for _ in range(60):
            game.update()
        self.assertEqual(marble.radius, main.MARBLE_RADIUS * 2)

    def test_size_effect_icons_render_without_raising(self):
        for effect in (main.Effect.GROWING, main.Effect.SHRINKING):
            surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
            block = main.Block(0, 0, shape=main.Shape.RECT, effect=effect, origin=(0, 0))
            block.rect.topleft = (0, 0)
            block.draw(surface)  # renders without raising

    def test_drain_shape_is_shop_available_and_priced(self):
        self.assertIn(main.Shape.DRAIN, main.Shape.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.DRAIN)], 0)
        self.assertIn("drain", main.shape_description(main.Shape.DRAIN).lower())
        self.assertIn("funnel", main.shape_description(main.Shape.DRAIN).lower())

    def test_drain_walls_are_solid_and_bottom_drain_is_open(self):
        # A drain's two curved walls are solid; the marble-diameter opening at
        # the bottom center is open (like the pipe's gap).
        block = main.Block(4, 4, shape=main.Shape.DRAIN, scorer=main.Scorer.NONE)
        left_wall = main.Marble(block.rect.left + 6, block.rect.bottom - 6)
        right_wall = main.Marble(block.rect.right - 6, block.rect.bottom - 6)
        bottom_drain = main.Marble(block.rect.centerx, block.rect.bottom)
        self.assertIsNotNone(left_wall.physics._block_collision(left_wall, block))
        self.assertIsNotNone(right_wall.physics._block_collision(right_wall, block))
        self.assertIsNone(bottom_drain.physics._block_collision(bottom_drain, block))

    def test_drain_mid_wall_is_solid_from_inside(self):
        # Halfway down the cell the funnel has narrowed: a marble centered
        # there is still clear of the walls, but one near the left edge hits
        # the wall.
        block = main.Block(4, 4, shape=main.Shape.DRAIN, scorer=main.Scorer.NONE)
        center = main.Marble(block.rect.centerx, block.rect.top + 20)
        near_left = main.Marble(block.rect.left + 3, block.rect.top + 10)
        self.assertIsNone(center.physics._block_collision(center, block))
        self.assertIsNotNone(near_left.physics._block_collision(near_left, block))

    def test_marble_falls_through_drain_center(self):
        # A marble released above the drain's center falls straight through the
        # funnel and out the marble-width drain at the bottom.
        block = main.Block(4, 4, shape=main.Shape.DRAIN, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 30)
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(90):
            marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.position[1], block.rect.bottom + 10)

    def test_drain_draws_and_rotates_without_raising(self):
        surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        block = main.Block(0, 0, shape=main.Shape.DRAIN, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        block.draw(surface)  # axis-aligned funnel renders
        walls_0 = block.get_drain_walls
        block.angle = 90
        block.draw(surface)  # rotated funnel renders without raising
        self.assertNotEqual(block.get_drain_walls, walls_0)

    def test_pipe_bend_shape_is_shop_available_and_priced(self):
        self.assertIn(main.Shape.PIPE_BEND, main.Shape.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.PIPE_BEND)], 0)
        self.assertIn("bend", main.shape_description(main.Shape.PIPE_BEND).lower())

    def test_pipe_bend_centerline_is_clear(self):
        # A marble centered in the bend's channel sits at distance 20 from the
        # corner center: its circle exactly fits the marble-wide annulus, so it
        # is clear (or at worst a sub-pixel grazing contact from float error).
        block = main.Block(4, 4, shape=main.Shape.PIPE_BEND, scorer=main.Scorer.NONE)
        cx, cy = block.rect.right, block.rect.top
        marble = main.Marble(cx - 20 * 0.7071, cy + 20 * 0.7071)  # d = 20
        hit = marble.physics._block_collision(marble, block)
        self.assertTrue(hit is None or hit[1] < 1.0)

    def test_pipe_bend_corner_core_is_solid(self):
        # Inside the bend's corner core (within the inner radius 12) is solid.
        block = main.Block(4, 4, shape=main.Shape.PIPE_BEND, scorer=main.Scorer.NONE)
        core = main.Marble(block.rect.right - 4, block.rect.top + 4)  # d ~ 5.7
        self.assertIsNotNone(core.physics._block_collision(core, block))

    def test_pipe_bend_outer_solid_is_solid(self):
        # A marble overlapping the outer wall (d = 30, just past the outer
        # radius 28) collides with it.
        block = main.Block(4, 4, shape=main.Shape.PIPE_BEND, scorer=main.Scorer.NONE)
        cx, cy = block.rect.right, block.rect.top
        outer = main.Marble(cx - 30 * 0.7071, cy + 30 * 0.7071)  # d = 30
        self.assertIsNotNone(outer.physics._block_collision(outer, block))

    def test_marble_travels_through_pipe_bend(self):
        # A marble dropped into the top entrance is guided through the bend's
        # channel and out the right exit (the two adjacent sides).
        block = main.Block(4, 4, shape=main.Shape.PIPE_BEND, scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.right - 20, block.rect.top - 30)  # entrance center
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(300):
            marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.position[0], block.rect.right - 5)

    def test_pipe_bend_draws_and_rotates_without_raising(self):
        surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        block = main.Block(0, 0, shape=main.Shape.PIPE_BEND, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        block.draw(surface)  # axis-aligned bend renders
        arc_0 = block.get_pipe_bend_outer_arc
        center_0 = block.get_pipe_bend_center
        block.angle = 90
        block.draw(surface)  # rotated bend renders without raising
        self.assertNotEqual(block.get_pipe_bend_outer_arc, arc_0)
        self.assertFalse(np.array_equal(block.get_pipe_bend_center, center_0))

    def test_pipe_bend_exit_is_open_beyond_the_cell(self):
        # The outer wall is truncated to the arc's angular span: a marble that
        # has passed through the right exit (its center outside the cell, in
        # the exit band) must not be pinned by a wall that isn't there.
        block = main.Block(4, 4, shape=main.Shape.PIPE_BEND, scorer=main.Scorer.NONE)
        cx, cy = block.rect.right, block.rect.top
        marble = main.Marble(cx + 20, cy + 20)  # d ~ 28.3 > outer, center outside the cell
        self.assertIsNone(marble.physics._block_collision(marble, block))
        # A marble right at the opening (just outside, still in the exit band)
        # is also free.
        marble2 = main.Marble(cx + 5, cy + 20)
        self.assertIsNone(marble2.physics._block_collision(marble2, block))

    def test_portal_block_is_pass_through(self):
        block = main.Block(5, 5, shape=main.Shape.RECT, effect=main.Effect.PORTAL,
                           scorer=main.Scorer.NONE, portal_number=1)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        # A portal block has no physical hitbox: the marble falls straight through.
        self.assertIsNone(marble.physics._block_collision(marble, block))
        start_y = marble.position[1]
        marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.position[1], start_y)  # fell down, not blocked

    def test_portal_teleports_marble_to_paired_portal(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        marble.physics.update(marble, main.DT, [a, b])

        # The marble exited from the matching portal's cell (kept its number).
        self.assertAlmostEqual(marble.position[0], b.rect.centerx, delta=2)
        self.assertAlmostEqual(marble.position[1], b.rect.centery, delta=2)

    def test_portal_pass_through_registers_entry_not_exit_contact(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.CHIPS_ADD, scorer_amount=10, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        marble.physics.update(marble, main.DT, [a, b])

        # The portal the marble passed THROUGH is a contact (so it can score);
        # the exit portal it arrived at is not.
        self.assertIn(a, marble.collisions_this_tick)
        self.assertNotIn(b, marble.collisions_this_tick)

    def test_portal_does_not_teleport_to_different_number(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=2)
        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(5):
            marble.physics.update(marble, main.DT, [a, b])

        # No matching partner (number 2 is a different pair): the marble stays.
        self.assertTrue(a.rect.collidepoint(marble.position))
        self.assertFalse(b.rect.collidepoint(marble.position))

    def test_portal_requires_paired_portal_on_grid(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])
        start_y = marble.position[1]

        for _ in range(5):
            marble.physics.update(marble, main.DT, [a])

        # With no partner placed, a lone portal does not teleport the marble.
        self.assertTrue(a.rect.collidepoint(marble.position))
        self.assertGreater(marble.position[1], start_y)  # just fell a little

    def test_lock_block_is_a_solid_door_while_locked(self):
        # A Lock fills its unit like a wall until its key is touched, so a
        # marble dropped onto it comes to rest on top instead of passing
        # through.
        block = main.Block(5, 8, shape=main.Shape.LOCK, scorer=main.Scorer.NONE)
        self.assertTrue(block.locked)
        marble = main.Marble(block.rect.centerx, block.rect.top - 30)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])

        # The marble rests on top of the door (its center one radius above the
        # door's top edge) instead of falling through.
        self.assertLess(marble.position[1], block.rect.top)
        self.assertAlmostEqual(marble.position[1],
                               block.rect.top - marble.radius, delta=2)

    def test_open_lock_block_is_pass_through(self):
        # Once its key has been touched the door opens: the same block stops
        # colliding and the marble falls straight through the unit.
        block = main.Block(5, 8, shape=main.Shape.LOCK, scorer=main.Scorer.NONE)
        block.locked = False
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])
        start_y = marble.position[1]

        self.assertIsNone(marble.physics._block_collision(marble, block))
        marble.physics.update(marble, main.DT, [block])
        self.assertGreater(marble.position[1], start_y)

    def test_key_block_is_pass_through_and_registers_a_field_contact(self):
        # A Key is a pickup with no hitbox: the marble passes through its unit,
        # but passing through counts as a contact (so the key can score and
        # unlock its lock).
        block = main.Block(5, 8, shape=main.Shape.KEY,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        self.assertIsNone(marble.physics._block_collision(marble, block))
        marble.physics.update(marble, main.DT, [block])
        self.assertIn(block, marble.collisions_this_tick)

    def test_open_lock_still_registers_a_field_contact(self):
        # An opened door is a pass-through field like Shape.NONE, so a marble
        # passing through it still activates the block's scorer.
        block = main.Block(5, 8, shape=main.Shape.LOCK,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        block.locked = False
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        marble.physics.update(marble, main.DT, [block])
        self.assertIn(block, marble.collisions_this_tick)

    def test_lock_is_never_in_contact_and_key_never_blocks(self):
        # The contact helper (used by accelerator/bouncy pushes) agrees with
        # the collision test: a Key and an opened Lock are never "touched", a
        # locked door always is.
        locked = main.Block(5, 8, shape=main.Shape.LOCK, scorer=main.Scorer.NONE)
        open_lock = main.Block(2, 8, shape=main.Shape.LOCK, scorer=main.Scorer.NONE)
        open_lock.locked = False
        key = main.Block(8, 8, shape=main.Shape.KEY, scorer=main.Scorer.NONE)
        on_locked = main.Marble(locked.rect.centerx, locked.rect.centery)
        on_open = main.Marble(open_lock.rect.centerx, open_lock.rect.centery)
        on_key = main.Marble(key.rect.centerx, key.rect.centery)

        self.assertTrue(on_locked.physics._in_contact_with(on_locked, locked))
        self.assertFalse(on_open.physics._in_contact_with(on_open, open_lock))
        self.assertFalse(on_key.physics._in_contact_with(on_key, key))

    def test_portal_does_not_instantly_bounce_back(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(5, 6, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        marble.physics.update(marble, main.DT, [a, b])  # teleports a -> b
        self.assertAlmostEqual(marble.position[1], b.rect.centery, delta=2)

        marble.physics.update(marble, main.DT, [a, b])  # next frame

        # The marble doesn't pop straight back to a; it continues past b.
        self.assertGreater(marble.position[1], a.rect.centery + 30)
        self.assertAlmostEqual(marble.position[0], b.rect.centerx, delta=2)

    def test_portal_does_not_block_other_pairs_after_using_one(self):
        a1 = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                        scorer=main.Scorer.NONE, portal_number=1)
        b1 = main.Block(1, 1, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                        scorer=main.Scorer.NONE, portal_number=1)
        a2 = main.Block(6, 6, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                        scorer=main.Scorer.NONE, portal_number=2)
        b2 = main.Block(3, 3, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                        scorer=main.Scorer.NONE, portal_number=2)
        marble = main.Marble(a1.rect.centerx, a1.rect.centery)
        marble.velocity = np.array([0.0, 0.0])
        # The marble just used pair 1 (still near both of its cells).
        marble.last_portal_cells = (
            (a1.rect.left, a1.rect.top, a1.rect.right, a1.rect.bottom),
            (b1.rect.left, b1.rect.top, b1.rect.right, b1.rect.bottom),
        )

        # Now it reaches pair 2's source portal and should still teleport.
        marble.position = np.array([a2.rect.centerx, a2.rect.centery], dtype=float)
        marble.physics.update(marble, main.DT, [a1, b1, a2, b2])

        self.assertAlmostEqual(marble.position[0], b2.rect.centerx, delta=2)
        self.assertAlmostEqual(marble.position[1], b2.rect.centery, delta=2)

    def test_fast_marble_does_not_phase_through_portal(self):
        portal_a = main.Block(5, 7, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                              scorer=main.Scorer.NONE, portal_number=1)
        portal_b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                              scorer=main.Scorer.NONE, portal_number=1)
        # A 3000px/s marble crosses the whole 40px portal cell within one frame
        # (frame-start and frame-end positions are both outside the cell), so
        # only path sampling catches it.
        marble = main.Marble(portal_a.rect.centerx, portal_a.rect.top - 5)
        marble.velocity = np.array([0.0, 3000.0])

        marble.physics.update(marble, main.DT, [portal_a, portal_b])

        self.assertAlmostEqual(marble.position[0], portal_b.rect.centerx, delta=2)
        self.assertAlmostEqual(marble.position[1], portal_b.rect.centery, delta=2)

    def test_portal_pair_has_a_100_travel_budget_that_both_halves_share(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        # Every portal starts a run with the full 100-travel budget on both
        # halves.
        self.assertEqual(a.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)
        self.assertEqual(b.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS)

        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])
        marble.physics.update(marble, main.DT, [a, b])

        # One travel through the pair consumes one use from BOTH halves, so
        # they stay in lockstep.
        self.assertAlmostEqual(marble.position[0], b.rect.centerx, delta=2)
        self.assertAlmostEqual(marble.position[1], b.rect.centery, delta=2)
        self.assertEqual(a.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS - 1)
        self.assertEqual(b.portal_uses_left, main.PORTAL_MAX_ACTIVATIONS - 1)

    def test_portal_pair_stops_teleporting_once_its_budget_is_spent(self):
        a = main.Block(5, 5, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        b = main.Block(2, 2, shape=main.Shape.NONE, effect=main.Effect.PORTAL,
                       scorer=main.Scorer.NONE, portal_number=1)
        a.portal_uses_left = 1
        b.portal_uses_left = 1  # only one travel left for the pair this run

        # The last allowed travel still happens...
        marble = main.Marble(a.rect.centerx, a.rect.centery)
        marble.velocity = np.array([0.0, 0.0])
        marble.physics.update(marble, main.DT, [a, b])
        self.assertAlmostEqual(marble.position[0], b.rect.centerx, delta=2)
        self.assertEqual(a.portal_uses_left, 0)
        self.assertEqual(b.portal_uses_left, 0)

        # ...but once the pair's budget is spent the portal effect stops
        # working: the marble stays put instead of teleporting back.
        marble.position = np.array([a.rect.centerx, a.rect.centery], dtype=float)
        marble.last_portal_cells = None
        marble.velocity = np.array([0.0, 0.0])
        marble.physics.update(marble, main.DT, [a, b])
        self.assertAlmostEqual(marble.position[0], a.rect.centerx, delta=2)
        self.assertAlmostEqual(marble.position[1], a.rect.centery, delta=2)
        self.assertEqual(a.portal_uses_left, 0)
        self.assertEqual(b.portal_uses_left, 0)

    def test_circle_shape_collides_only_when_overlapping(self):
        block = main.Block(5, 8, shape=main.Shape.CIRCLE, scorer=main.Scorer.CHIPS_ADD)
        inside = main.Marble(block.rect.centerx, block.rect.centery)
        outside = main.Marble(block.rect.centerx, block.rect.top - 60)

        self.assertIsNotNone(inside.physics._block_collision(inside, block))
        self.assertIsNone(outside.physics._block_collision(outside, block))

    def test_marble_rests_on_top_of_circle(self):
        block = main.Block(5, 8, shape=main.Shape.CIRCLE, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, block.rect.top - 25)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(90):
            marble.physics.update(marble, main.DT, [block])

        # The marble's center sits a marble-radius above the circle's top.
        self.assertLessEqual(marble.position[1], block.rect.top + main.MARBLE_RADIUS)
        self.assertGreater(marble.position[1], block.rect.top - main.MARBLE_RADIUS - 2.0)

    def test_curved_slope_collides_only_inside_block(self):
        block = main.Block(5, 8, shape=main.Shape.CURVED_SLOPE, scorer=main.Scorer.CHIPS_ADD)
        # (30,30) from the arc center: beyond the arc (d>R) -> inside the block.
        inside = main.Marble(block.rect.left + 30, block.rect.top + 30)
        # (12,12) from the arc center: well in the open region (d<R) -> no hit.
        open_space = main.Marble(block.rect.left + 12, block.rect.top + 12)

        self.assertIsNotNone(inside.physics._block_collision(inside, block))
        self.assertIsNone(open_space.physics._block_collision(open_space, block))

    def test_marble_rides_curved_surface(self):
        block = main.Block(5, 8, shape=main.Shape.CURVED_SLOPE, scorer=main.Scorer.CHIPS_ADD)
        center = np.array([block.rect.left, block.rect.top], dtype=float)
        radius = float(block.rect.width)  # arc radius
        marble = main.Marble(block.rect.left + 18.4, block.rect.top + 18.4)  # 26 from center
        marble.velocity = np.array([0.0, 0.0])

        min_deviation = 999.0
        for _ in range(90):
            marble.physics.update(marble, main.DT, [block])
            offset = marble.position - center
            if offset[0] >= 0 and offset[1] >= 0:
                d = float(np.linalg.norm(offset))
                min_deviation = min(min_deviation, abs(d - (radius - main.MARBLE_RADIUS)))

        # While on the arc the marble's center stays at R - MARBLE_RADIUS from it.
        self.assertLess(min_deviation, 4.0)

    def test_rotated_curved_slope_honors_angle(self):
        # Rotating 180 deg moves the arc center to the bottom-right corner.
        block = main.Block(5, 8, shape=main.Shape.CURVED_SLOPE, scorer=main.Scorer.CHIPS_ADD,
                           angle=180)
        center = np.array([block.rect.right, block.rect.bottom], dtype=float)
        radius = float(block.rect.width)
        self.assertTrue(np.allclose(block.get_curved_center, center))

        marble = main.Marble(block.rect.centerx - 18.4, block.rect.centery - 18.4)
        marble.velocity = np.array([0.0, 0.0])

        min_deviation = 999.0
        for _ in range(90):
            marble.physics.update(marble, main.DT, [block])
            offset = marble.position - center
            # The rotated arc sits toward the top-left of the cell (offset <= 0, <= 0).
            if offset[0] <= 0 and offset[1] <= 0:
                d = float(np.linalg.norm(offset))
                min_deviation = min(min_deviation, abs(d - (radius - main.MARBLE_RADIUS)))

        self.assertLess(min_deviation, 4.0)

    def test_rotated_curved_slope_arc_span(self):
        # The arc angular span must be 90 deg regardless of rotation.
        for angle in (0, 90, 180, 270):
            block = main.Block(5, 8, shape=main.Shape.CURVED_SLOPE, scorer=main.Scorer.CHIPS_ADD,
                               angle=angle)
            center = block.get_curved_center
            end0 = block.get_curved_arc[0]
            end90 = block.get_curved_arc[-1]
            a0 = math.degrees(math.atan2(end0[1] - center[1], end0[0] - center[0])) % 360
            a90 = math.degrees(math.atan2(end90[1] - center[1], end90[0] - center[0])) % 360
            sweep = (a90 - a0) % 360
            self.assertAlmostEqual(sweep, 90.0, delta=1.0)

    def test_convex_slope_is_shop_available_and_priced(self):
        self.assertIn(main.Shape.CONVEX_SLOPE, main.Shape.ORDER)
        self.assertGreater(main.COMPONENT_PRICES[(main.Component.SHAPE, main.Shape.CONVEX_SLOPE)], 0)
        self.assertIn("convex", main.shape_description(main.Shape.CONVEX_SLOPE).lower())

    def test_convex_slope_quarter_disk_is_solid(self):
        # The convex slope is a solid quarter disk at the cell's top-left.
        block = main.Block(5, 8, shape=main.Shape.CONVEX_SLOPE, scorer=main.Scorer.CHIPS_ADD)
        center = np.array([block.rect.left, block.rect.top], dtype=float)
        inside = main.Marble(*(center + np.array([10.0, 10.0])))  # r ~14, inside the disk
        self.assertIsNotNone(inside.physics._block_collision(inside, block))
        # A marble far in the cell's empty bottom-right region is clear.
        open_space = main.Marble(block.rect.right - 5, block.rect.bottom - 5)
        self.assertIsNone(open_space.physics._block_collision(open_space, block))

    def test_convex_slope_blocks_marble_from_above(self):
        # The disk's top edge blocks a marble falling onto the bump.
        block = main.Block(5, 8, shape=main.Shape.CONVEX_SLOPE, scorer=main.Scorer.CHIPS_ADD)
        above = main.Marble(block.rect.left + 10, block.rect.top - 5)
        self.assertIsNotNone(above.physics._block_collision(above, block))

    def test_marble_lands_on_convex_slope(self):
        # A marble dropped onto the convex slope is caught on the quarter disk
        # (it does not fall through the solid to the bottom of the box).
        block = main.Block(5, 8, shape=main.Shape.CONVEX_SLOPE, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.left + 20, block.rect.top - 30)
        marble.velocity = np.array([0.0, 0.0])
        for _ in range(120):
            marble.physics.update(marble, main.DT, [block])
        self.assertLess(marble.position[1], block.rect.top + 30)

    def test_convex_slope_draws_and_rotates_without_raising(self):
        surface = main.pygame.Surface((main.GRID_SIZE, main.GRID_SIZE))
        block = main.Block(0, 0, shape=main.Shape.CONVEX_SLOPE, scorer=main.Scorer.NONE, origin=(0, 0))
        block.rect.topleft = (0, 0)
        block.draw(surface)  # axis-aligned convex slope renders
        fill_0 = list(block.get_convex_fill)
        block.angle = 90
        block.draw(surface)  # rotated renders without raising
        self.assertNotEqual(block.get_convex_fill, fill_0)

    def test_no_hitbox_shape_has_no_collision(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.centery)

        self.assertIsNone(marble.physics._block_collision(marble, block))
        self.assertFalse(marble.physics._in_contact_with(marble, block))

    def test_fast_marble_does_not_phase_through_none_shape_field(self):
        block = main.Block(5, 7, shape=main.Shape.NONE, effect=main.Effect.NONE,
                           scorer=main.Scorer.CHIPS_ADD, scorer_amount=10)
        # A 3000px/s marble crosses the whole 40px cell within one frame (its
        # frame-start and frame-end positions are both outside the cell), so
        # only path sampling registers the field contact.
        marble = main.Marble(block.rect.centerx, block.rect.top - 5)
        marble.velocity = np.array([0.0, 3000.0])

        marble.physics.update(marble, main.DT, [block])

        self.assertIn(block, marble.collisions_this_tick)

    def test_no_hitbox_bouncy_does_not_affect_marble(self):
        block = main.Block(5, 8, shape=main.Shape.NONE, effect=main.Effect.BOUNCY,
                           scorer=main.Scorer.NONE)
        marble = main.Marble(block.rect.centerx, block.rect.top - 30)
        marble.velocity = np.array([0.0, 300.0])

        for _ in range(30):
            marble.physics.update(marble, main.DT, [block])

        # The marble passes straight through without being deflected or bounced.
        self.assertGreater(marble.position[1], block.rect.bottom + 20)

    def test_no_hitbox_accelerator_field_pushes_inside_cell(self):
        block = main.Block(3, 8, shape=main.Shape.NONE, effect=main.Effect.ACCELERATOR,
                           scorer=main.Scorer.NONE, angle=90)  # arrow points right
        marble = main.Marble(block.rect.centerx, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        # Track the peak rightward speed while in the field; the marble may
        # later cross the box and have its velocity zeroed at the wall.
        max_vx = 0.0
        for _ in range(20):
            marble.physics.update(marble, main.DT, [block])
            max_vx = max(max_vx, float(marble.velocity[0]))

        self.assertGreater(max_vx, 150.0)

    def test_no_hitbox_accelerator_field_ignores_outside_marble(self):
        block = main.Block(3, 8, shape=main.Shape.NONE, effect=main.Effect.ACCELERATOR,
                           scorer=main.Scorer.NONE, angle=90)
        # Marble to the right of the cell (y inside the cell band): the field
        # must not push it horizontally.
        marble = main.Marble(block.rect.right + 20, block.rect.centery)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(10):
            marble.physics.update(marble, main.DT, [block])

        self.assertAlmostEqual(marble.velocity[0], 0.0, delta=1e-6)

    def test_slope_collides_with_vertical_edge(self):
        block = main.Block(0, 0, shape=main.Shape.SLOPE, angle=0)
        # The slope's vertical edge sits at the right side of the block's cell.
        marble = main.Marble(block.rect.right - 7, block.rect.top + 20)

        normal = marble.physics.check_slope_collision(marble, block)

        self.assertIsNotNone(normal)
        self.assertTrue(np.isclose(abs(normal[0]), 1.0))
        self.assertTrue(np.isclose(normal[1], 0.0))

    def test_slope_line_block_collides_with_single_sloped_line(self):
        block = main.Block(0, 0, shape=main.Shape.LINE, angle=0)
        start, end = block.get_slope_line_points
        marble = main.Marble((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 6)

        normal = marble.physics.check_slope_collision(marble, block)

        self.assertIsNotNone(normal)
        self.assertTrue(np.isclose(abs(normal[0]), abs(normal[1])))

    def _line_y_at(self, block, x):
        p1, p2 = block.get_slope_line_points
        p1 = np.array(p1)
        p2 = np.array(p2)
        if p2[0] == p1[0]:
            return None
        return p1[1] + (p2[1] - p1[1]) * (x - p1[0]) / (p2[0] - p1[0])

    def _signed_line_dist(self, block, pos):
        p1, p2 = block.get_slope_line_points
        p1 = np.array(p1, dtype=float)
        p2 = np.array(p2, dtype=float)
        v = p2 - p1
        ref = np.array([-v[1], v[0]])
        ref = ref / np.linalg.norm(ref)
        return np.dot(pos - p1, ref)

    def _line_closest_t(self, block, pos):
        p1, p2 = block.get_slope_line_points
        p1 = np.array(p1, dtype=float)
        p2 = np.array(p2, dtype=float)
        v = p2 - p1
        return np.dot(pos - p1, v) / np.dot(v, v)

    def test_rotated_line_is_solid_on_both_sides(self):
        # A marble pushed into a rotated line from either side must never
        # phase through the segment.
        for angle in (0, 90, 180, 270):
            line = main.Block(5, 8, shape=main.Shape.LINE, scorer=main.Scorer.NONE, angle=angle)
            p1, p2 = line.get_slope_line_points
            p1 = np.array(p1, dtype=float)
            p2 = np.array(p2, dtype=float)
            mid = (p1 + p2) / 2
            d = p2 - p1
            perp = np.array([-d[1], d[0]])
            perp = perp / np.linalg.norm(perp)
            for side in (1, -1):
                marble = main.Marble(mid[0] + perp[0] * side * 3, mid[1] + perp[1] * side * 3)
                marble.velocity = np.array([0.0, 250.0])
                before = None
                for _ in range(120):
                    marble.physics.update(marble, main.DT, [line])
                    t = self._line_closest_t(line, marble.position)
                    sd = self._signed_line_dist(line, marble.position)
                    if 0.0 <= t <= 1.0 and before is not None and np.sign(sd) != np.sign(before):
                        self.fail(f"marble phased through line at angle {angle} side {side}")
                    before = sd

    def test_marble_does_not_gain_energy_when_pinned_on_line_endpoint(self):
        # A line endpoint meeting a rect block's corner forms a crevice that
        # used to pin the marble while gravity kept adding speed (a runaway
        # velocity boost up to the speed clamp). The marble must instead slide
        # along the surface and never exceed its gravitational energy budget.
        line = main.Block(5, 8, shape=main.Shape.LINE, scorer=main.Scorer.NONE, angle=270)
        rect = main.Block(6, 8, shape=main.Shape.RECT, scorer=main.Scorer.NONE)
        marble = main.Marble(340.0, 436.2)
        marble.velocity = np.array([0.0, 0.0])
        bottom = main.MARBLE_BOX_COORDS[1] + main.MARBLE_BOX_COORDS[3]
        budget = np.sqrt(2 * main.GRAVITY * max(0, bottom - marble.position[1]))

        for _ in range(200):
            marble.physics.update(marble, main.DT, [line, rect])
            self.assertLessEqual(float(np.linalg.norm(marble.velocity)), budget + 1.0)

    def test_marble_rides_line_instead_of_falling_through(self):
        line = main.Block(5, 8, shape=main.Shape.LINE, scorer=main.Scorer.NONE)
        xs = sorted(p[0] for p in line.get_slope_line_points)
        marble = main.Marble(line.rect.centerx,
                             self._line_y_at(line, line.rect.centerx) - main.MARBLE_RADIUS - 3)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(240):
            marble.physics.update(marble, main.DT, [line])
            line_y = self._line_y_at(line, marble.position[0])
            if line_y is not None and xs[0] - 2 <= marble.position[0] <= xs[1] + 2:
                # The marble must never sink below the line while over it.
                self.assertLessEqual(marble.position[1] - line_y, main.MARBLE_RADIUS + 6)

    def test_marble_rides_slope_instead_of_being_flung_off(self):
        slope = main.Block(5, 8, shape=main.Shape.SLOPE, scorer=main.Scorer.NONE)
        xs = sorted(p[0] for p in slope.get_slope_line_points)
        marble = main.Marble(slope.rect.centerx,
                             self._line_y_at(slope, slope.rect.centerx) - main.MARBLE_RADIUS - 3)
        marble.velocity = np.array([0.0, 0.0])

        for _ in range(240):
            marble.physics.update(marble, main.DT, [slope])
            line_y = self._line_y_at(slope, marble.position[0])
            if line_y is not None and xs[0] - 2 <= marble.position[0] <= xs[1] + 2:
                self.assertLessEqual(marble.position[1] - line_y, main.MARBLE_RADIUS + 6)

    def test_line_surface_normal_is_two_sided(self):
        line = main.Block(0, 0, shape=main.Shape.LINE, angle=0)
        # Both sides of a line are solid: a marble on the top gets the surface
        # normal and a marble on the bottom gets its exact opposite, so neither
        # side can phase through the line.
        top = main.Marble(line.rect.centerx, line.rect.centery - main.MARBLE_RADIUS)
        bottom = main.Marble(line.rect.centerx, line.rect.centery + main.MARBLE_RADIUS)
        expected = line.get_slope_surface_normal

        n_top = top.physics.check_slope_collision(top, line)
        n_bottom = bottom.physics.check_slope_collision(bottom, line)

        self.assertIsNotNone(n_top)
        self.assertIsNotNone(n_bottom)
        self.assertTrue(np.allclose(n_top, expected))
        self.assertTrue(np.allclose(n_bottom, -expected))

    def test_start_block_is_not_solid(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.START)
        # Marble sits right on top of the start block's center.
        marble = main.Marble(block.rect.centerx, block.rect.centery)

        normal = marble.physics._block_collision(marble, block)

        self.assertIsNone(normal)

    def test_non_start_block_is_solid(self):
        block = main.Block(0, 0, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, block.rect.centery)

        normal = marble.physics._block_collision(marble, block)

        self.assertIsNotNone(normal)

    def test_marble_rolls_over_seam_between_two_blocks(self):
        left = main.Block(4, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        right = main.Block(5, 3, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(left.rect.right - 15, left.rect.top - main.MARBLE_RADIUS)
        marble.velocity = np.array([80.0, 0.0])

        for _ in range(30):
            marble.physics.update(marble, main.DT, [left, right])

        # The marble keeps rolling rightward across the seam instead of stopping
        # or reversing direction.
        self.assertGreater(marble.velocity[0], 20.0)
        self.assertGreater(marble.position[0], right.rect.left)

    def test_marble_pushed_out_of_corner_without_freezing(self):
        floor = main.Block(1, 1, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        wall = main.Block(1, 0, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(floor.rect.left - 6, floor.rect.top + 3)
        marble.velocity = np.array([30.0, 10.0])

        marble.physics.move_with_collision(marble, [floor, wall], main.DT)

        # A corner impact should not zero out the marble's velocity...
        self.assertFalse(np.allclose(marble.velocity, [0.0, 0.0]))
        # ...and the marble should be separated from both blocks.
        self.assertIsNone(marble.physics._block_collision(marble, floor))
        self.assertIsNone(marble.physics._block_collision(marble, wall))

    def test_fast_marble_does_not_tunnel_through_block(self):
        block = main.Block(2, 4, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD)
        marble = main.Marble(block.rect.centerx, 120)
        marble.velocity = np.array([0.0, 20000.0])

        for _ in range(10):
            marble.physics.update(marble, main.DT, [block])

        # The marble rests on top of the block instead of passing through it.
        self.assertLess(marble.position[1], block.rect.top)
        self.assertGreater(marble.position[1], block.rect.top - main.MARBLE_RADIUS - 2.0)

    def test_marble_speed_is_clamped(self):
        marble = main.Marble(200, 120)
        marble.velocity = np.array([0.0, 100000.0])

        marble.physics.move_with_collision(marble, [], main.DT)

        self.assertLessEqual(np.linalg.norm(marble.velocity), main.MAX_MARBLE_SPEED + 1e-6)

    # --- Effect magnitudes: each block uses its OWN rolled strength ---------

    def test_piston_launch_speed_is_the_blocks_own_magnitude(self):
        def rebound(magnitude):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.PISTON,
                               scorer=main.Scorer.NONE,
                               effect_amounts={main.Effect.PISTON: magnitude})
            marble = main.Marble(block.rect.centerx, block.rect.top - 40)
            marble.velocity = np.array([0.0, 300.0])
            min_vy = 0.0
            for _ in range(40):
                marble.physics.update(marble, main.DT, [block])
                min_vy = min(min_vy, float(marble.velocity[1]))
            return abs(min_vy)

        weak = rebound(900)
        average = rebound(main.PISTON_FORCE)
        strong = rebound(2100)

        self.assertLess(weak, average)
        self.assertLess(average, strong)
        self.assertAlmostEqual(average, main.PISTON_FORCE, delta=main.PISTON_FORCE * 0.15)
        self.assertAlmostEqual(strong, 2100, delta=2100 * 0.15)

    def test_accelerator_push_is_the_blocks_own_magnitude(self):
        def push(magnitude):
            block = main.Block(5, 8, shape=main.Shape.RECT,
                               effect=main.Effect.ACCELERATOR,
                               scorer=main.Scorer.NONE, angle=90,
                               effect_amounts={main.Effect.ACCELERATOR: magnitude})
            return float(np.linalg.norm(block.get_acceleration))

        self.assertAlmostEqual(push(main.ACCELERATION_FORCE), main.ACCELERATION_FORCE)
        self.assertGreater(push(24000), push(16000))
        # A block with no roll reads the average, exactly as it always did.
        plain = main.Block(5, 8, shape=main.Shape.RECT,
                           effect=main.Effect.ACCELERATOR, scorer=main.Scorer.NONE)
        self.assertAlmostEqual(float(np.linalg.norm(plain.get_acceleration)),
                              main.ACCELERATION_FORCE)

    def test_black_hole_pull_is_the_blocks_own_magnitude(self):
        def pull(magnitude):
            block = main.Block(5, 8, shape=main.Shape.RECT,
                               effect=main.Effect.BLACK_HOLE, scorer=main.Scorer.NONE,
                               effect_amounts={main.Effect.BLACK_HOLE: magnitude})
            marble = main.Marble(block.rect.centerx,
                                 block.rect.centery + main.BLACK_HOLE_RANGE // 2)
            marble.velocity = np.array([0.0, 0.0])
            marble.physics.update(marble, main.DT, [block])
            return abs(float(marble.velocity[1]))

        weak = pull(900)
        average = pull(main.BLACK_HOLE_FORCE)
        strong = pull(3900)

        self.assertLess(weak, average)
        self.assertLess(average, strong)
        self.assertGreater(average, 0.0)

    def test_conveyor_belt_speed_is_the_blocks_own_magnitude(self):
        def carried(magnitude):
            block = main.Block(5, 5, effect=main.Effect.CONVEYOR,
                               scorer=main.Scorer.NONE,
                               effect_amounts={main.Effect.CONVEYOR: magnitude})
            marble = main.Marble(block.rect.centerx, block.rect.top - main.MARBLE_RADIUS)
            marble.velocity = np.array([0.0, 0.0])
            for _ in range(10):
                # Hold the marble on the belt so its speed can be watched.
                marble.position[0] = block.rect.centerx
                marble.physics.update(marble, main.DT, [block])
            return float(marble.velocity[0])

        self.assertGreater(carried(360), carried(240))
        self.assertAlmostEqual(carried(main.CONVEYOR_SPEED),
                              main.CONVEYOR_SPEED, delta=10.0)

    def test_sticky_hold_time_is_the_blocks_own_magnitude(self):
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.STICKY,
                           scorer=main.Scorer.NONE, effects=[main.Effect.STICKY],
                           effect_amounts={main.Effect.STICKY: 0.6})
        marble = main.Marble(block.rect.centerx, block.rect.top - 20)
        marble.velocity = np.array([0.0, 600.0])

        for _ in range(40):
            marble.physics.update(marble, main.DT, [block])
            if marble.sticky_timer > 0:
                break

        self.assertAlmostEqual(marble.sticky_timer, 0.6)

    def test_phase_duration_is_the_blocks_own_magnitude(self):
        block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.PHASE,
                           scorer=main.Scorer.NONE, effects=[main.Effect.PHASE],
                           effect_amounts={main.Effect.PHASE: 2.0})
        marble = main.Marble(block.rect.centerx, block.rect.top - 20)
        marble.velocity = np.array([0.0, 600.0])

        for _ in range(60):
            marble.physics.update(marble, main.DT, [block])
            if marble.phase_timer > 0:
                break

        self.assertGreater(marble.phase_timer, 0)
        self.assertLessEqual(marble.phase_timer, 2.0)

    def test_bouncy_bounce_strength_is_the_blocks_own_magnitude(self):
        def rebound(magnitude):
            block = main.Block(5, 8, shape=main.Shape.RECT, effect=main.Effect.BOUNCY,
                               scorer=main.Scorer.NONE,
                               effect_amounts={main.Effect.BOUNCY: magnitude})
            marble = main.Marble(block.rect.centerx, block.rect.top - 30)
            marble.velocity = np.array([0.0, 500.0])
            best = 0.0
            for _ in range(40):
                marble.physics.update(marble, main.DT, [block])
                if marble.velocity[1] < 0:
                    best = max(best, abs(float(marble.velocity[1])))
            return best

        weak = rebound(20)
        average = rebound(100)
        strong = rebound(180)

        self.assertLess(weak, average)
        self.assertLess(average, strong)

    def test_rotate_spin_speed_is_the_blocks_own_magnitude(self):
        fast = main.Block(5, 8, shape=main.Shape.CIRCLE, effect=main.Effect.ROTATE,
                          scorer=main.Scorer.NONE,
                          effect_amounts={main.Effect.ROTATE: 1800})
        slow = main.Block(5, 8, shape=main.Shape.CIRCLE, effect=main.Effect.ROTATE,
                          scorer=main.Scorer.NONE,
                          effect_amounts={main.Effect.ROTATE: 180})

        for _ in range(10):
            fast.advance_spin(main.DT)
            slow.advance_spin(main.DT)

        self.assertGreater(fast.spin, slow.spin)
        self.assertAlmostEqual(fast.spin, (1800 * main.DT * 10) % 360.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
