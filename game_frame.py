"""The frame itself: update, autosave, achievements and pop-ups."""

import math
import random
from collections import deque

import numpy as np
import pygame

import achievements
import cards
import collection
import components
import crt
import metagame
import profiles
import rolling
from rolling import *
import save_system
import sounds
import ui
from ui import Popup, ScoreParticle, TrailParticle
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
from blocks import Block
from items import (
    CASH_BREAKDOWN,
    ActionItem,
    BlockItem,
    CardItem,
    ItemPack,
    ResourceOption,
    ScorerToken,
    CashBreakdown,
    _s,
    make_card_item,
    offer_key,
    resource_point_label,
)
from marble import Marble, _configure_marble_type
from physics import PhysicsEngine
from shop import Shop
from toolbox import Toolbox


class FrameMixin:
    """The frame itself: update, autosave, achievements and pop-ups."""


    def _show_marble_box_title(self):
        """Whether the BOARD title should be drawn.

        It hides while the mouse is over the board panel, so the label never
        sits under the cursor (the panel's bottom-left corner is where the
        player clicks to place blocks).
        """
        return not pygame.Rect(MARBLE_BOX_COORDS).collidepoint(pygame.mouse.get_pos())

    def _tick_autosave(self, dt):
        """Autosave to the current slot every AUTOSAVE_INTERVAL seconds.

        The game otherwise writes a save only when the player asks (P) or
        quits, so a long session — and a crash — can cost everything since the
        last one. The clock runs while the game is being PLAYED: update()
        returns early on the title screen and the full-screen tabs, and a game
        with no slot chosen (the title-screen game itself, a test's bare Game)
        is never written anywhere.

        The save is SILENT: the autosave is not something the player did, and a
        message every 30 seconds would sit over the shop. It also only happens
        while the game is being BUILT — a save of a run in flight, or of a
        finished run awaiting RETRY/CONTINUE, would roll that run back, because
        every save path puts the game into its build state first (see
        _retry_run). An interval that comes due mid-run therefore keeps its
        clock and saves at the next build phase, rather than restarting it.
        """
        if self.save_slot is None:
            return
        self.autosave_timer += dt
        if self.autosave_timer < AUTOSAVE_INTERVAL:
            return
        if not self._autosave_ready():
            return
        self.autosave_timer = 0.0
        self._retry_run()
        save_system.save_game(self, announce=False)

    def _autosave_ready(self):
        """True when the game is in a state an autosave may capture.

        The build phase between runs: a run in flight is being played, and a
        finished run awaiting RETRY/CONTINUE holds a result the player has not
        committed yet — a timer must never take either away.
        """
        return not self.run_active and not self.awaiting_after_run

    def update(self):
        if (self.title_screen or self.achievements_open or self.marble_selecting
                or self.upgrades_open or self.collection_open):
            return
        self._tick_autosave(DT)
        # Achievement unlock conditions are checked every frame while playing.
        self._check_achievements()
        # Bottom popups (achievement unlocks, collection discoveries) animate
        # every frame: slide up from under the screen, hold, then slide down.
        for popup in self.popups:
            popup.update(DT)
        self.popups = [p for p in self.popups if not p.dead()]
        # Score popups float and fade every frame, even between runs.
        for particle in self.score_particles:
            particle.update(DT)
        self.score_particles = [p for p in self.score_particles if not p.dead()]
        # Marble trail dots shrink and fade every frame, even between runs.
        for particle in self.trail_particles:
            particle.update(DT)
        self.trail_particles = [p for p in self.trail_particles if not p.dead()]
        if self.shop_message_timer > 0:
            self.shop_message_timer -= 1
            if self.shop_message_timer <= 0:
                self.shop_message = ""
        if not self.paused and self.run_active:
            self.run_time += DT
            # The cable cars slide before the frame's block list is built, so
            # the marbles meet each gondola where it has just moved to.
            self._update_gondolas(DT)
            # Locked board squares act as solid walls this frame (they confine
            # the marbles to the unlocked region but never score or count as
            # block contacts).
            sim_blocks = self._simulation_blocks()
            # The board is infinite, so what confines a marble is the region of
            # UNLOCKED squares it is walled into (see Game.board_pixel_bounds):
            # the hard clamp sits two squares outside it, so phasing into the
            # walls around the region is still possible.
            bounds = self.board_pixel_bounds(pad=2)
            for marble in self.marbles:
                marble.bounds = bounds
                marble.physics.update(marble, DT, sim_blocks)
                # The Singularity trial makes the marble gain mass, slowly and
                # linearly, so it falls ever faster as the run drags on.
                if self.active_trial == Trial.SINGULARITY:
                    marble.mass += SINGULARITY_MASS_GROWTH * DT
                # The astronaut card grants mult for every second a marble is
                # pulled by a black hole, so accumulate that pull time per run.
                if getattr(marble, "under_black_hole", False):
                    self.black_hole_time += DT
                # The plane card grants chips for every second the marble is
                # in the air, so accumulate air time (no block contact) per run.
                # The airball scorer reads each marble's own airborne streak
                # (seconds since it last touched any block, incl. Shape.None).
                if not marble.collisions_this_tick:
                    marble.air_streak += DT
                    self.air_time += DT
                # The intangible card pays mult for every second a marble
                # spends inside a block, and much more for a second inside a
                # locked board unit, so accumulate both as the run plays.
                self._count_inside_time(marble)
                # The matrix card pays chips for every second a marble spends
                # inside a locked board unit WITHOUT the phase effect, so that
                # time is accumulated apart from the lock time above.
                self._count_locked_no_phase_time(marble)
                # Record the board units the marble's body is in: the Explorer
                # card's xMult is the fraction of the board those units cover,
                # and they are painted the title screen's colour while it is
                # owned (see ui.draw_board).
                self._note_visited_cell(marble)
                # Leave a shrinking trail dot wherever the marble has moved. A
                # dot laid while the marble-box fire is burning carries that
                # fire — and the direction the marble is moving NOW — so the
                # marble's fire trail IS its own trail particles: each one burns
                # where the marble was and keeps pointing the way it was laid,
                # which is what stops the fire from swinging about when the
                # marble bounces off something (see ui.TrailParticle).
                moved = marble.distance - marble._last_trail_distance
                marble._last_trail_distance = marble.distance
                marble._trail_accum += moved
                while marble._trail_accum >= TRAIL_SPACING:
                    marble._trail_accum -= TRAIL_SPACING
                    self.trail_particles.append(TrailParticle(
                        marble.position[0], marble.position[1],
                        max(1.5, marble.radius * TRAIL_RADIUS_SCALE),
                        marble.color, fire=np.log(7*self.fire_intensity + 1),
                        velocity=marble.velocity))
            # Split marbles share the board: separate any that overlap, so a
            # splitter's copy can collide with the marble it came from (a
            # phasing marble passes through the others too).
            if len(self.marbles) > 1:
                self.marbles[0].physics.resolve_marble_collisions(self.marbles)
            # A fragile block that shattered this frame grows the wrecking ball
            # card's permanent +mult bonus (handled once per break).
            for block in self.board_blocks():
                if getattr(block, "broke_fragile_this_frame", False):
                    block.broke_fragile_this_frame = False
                    self._on_fragile_broken(block)
            # A satanic block that a marble touched and then left this frame is
            # permanently destroyed: removed from the board for good (it never
            # comes back on later runs).
            for key, block in list(self.grid.items()):
                if getattr(block, "satanic_leave", False):
                    self.grid.pop(key, None)
                    # A Satanic block dying is a block destroyed this run (the
                    # Undertaker scorer counts them).
                    self.run_blocks_destroyed += 1
            self._handle_block_contacts(self.board_blocks())
            # A marble that touched a block this frame is not airborne: its
            # air streak was read at the fresh contact above (block scorers /
            # Airball cards), so end it so the next air segment starts fresh.
            for marble in self.marbles:
                if marble.collisions_this_tick:
                    marble.air_streak = 0.0
            # Record where every marble ended this frame: the oldest snapshot in
            # each marble's history is one second back, which is exactly where
            # Procrastination sends a finished run (see _procrastination_rewind).
            for marble in self.marbles:
                marble.history.append(marble.motion_state())
        # The marble-box fire animates every frame (growing while the score
        # passes the run, dying down once it is over).
        if not self.paused:
            self._update_fire(DT)

    def _has_all_effects(self, item):
        """True when the item is a block holding every real effect in the game."""
        effects = getattr(item, "effects", None)
        return effects is not None and set(effects) >= set(Effect.REAL_ORDER)

    def _push_popup(self, title, description, color=(255, 215, 0)):
        """Queue a compact bottom popup that slides up, holds, then slides down."""
        self.popups.append(Popup(title, description, color))

    def _show_achievement_popup(self, achievement):
        """Queue the 'achievement unlocked' popup for a newly earned one.

        A secret's real description appears once it is unlocked (not "???").
        """
        self._push_popup(achievement.name, achievements.display_description(achievement),
                         (255, 215, 0))

    def _check_achievements(self):
        """Evaluate each achievement's unlock condition and pop up new ones.

        Achievements persist globally (achievements.json), so "in any run at
        any time" conditions stay unlocked across runs, games, and save slots.
        """
        if achievements.is_disabled():
            return  # the player unlocked the whole collection: no new unlocks
        newly = []
        # Rich: hold more than $1000 in cash at any point in a run.
        if self.cash > 1000 and achievements.unlock("rich"):
            newly.append(achievements.achievement_by_id("rich"))
        # How did we get here?: own a block with every effect in the game.
        for item in self.board_blocks() + list(self.toolbox.items):
            if self._has_all_effects(item):
                if achievements.unlock("how_did_we_get_here"):
                    newly.append(achievements.achievement_by_id("how_did_we_get_here"))
                break
        for achievement in newly:
            if achievement is not None:
                self._show_achievement_popup(achievement)

    def _release_start_marble(self, start_block, vx=0.0):
        """Release one marble from a Start block and return it.

        The marble starts at the Start block's centre with no velocity (or the
        given sideways drift, which the Doppelganger card uses for its second
        marble). The trial modifiers and the save's marble type are applied
        here so every marble a run releases is configured identically.
        """
        marble = Marble(start_block.rect.centerx, start_block.rect.centery)
        marble.velocity = np.array([vx, 0.0])
        marble.start_block = start_block
        # The dead-zone trial triples gravity in the box's bottom third; the
        # all-finishes trial makes the marble-box borders act as a finish.
        # Restarts keep the same trial, so these are read from the current
        # (already chosen/applied) trial each run — and every one of them comes
        # from active_trial, so a game with the trial system switched off plays
        # no trial at all, however its id happens to read.
        trial = self.active_trial
        marble.dead_zone = trial == Trial.DEAD_ZONE
        marble.finish_on_border = trial == Trial.ALL_FINISHES
        # The bouncy-castle trial makes every solid block reflect the
        # marble like a bouncy block (physics.resolve_collision reads it).
        # The marble-weight trial scales how hard the DRIVING effects push the
        # marble (accelerators, pistons, rotating shapes, conveyors, black
        # holes, repulsors) by 1/effect_mass_mult (rolled in _apply_trial);
        # gravity, the marble's own bounce and every other move stay normal.
        marble.bouncy_castle = trial == Trial.BOUNCY_CASTLE
        marble.effect_mass_mult = (self.trial_marble_weight
                                   if trial == Trial.MARBLE_WEIGHT else 1.0)
        # The phantom trial starts the marble INSIDE the phase window a phase
        # block grants, so it passes through every block for the first second;
        # the elephant trial starts it at twice its size, which is what the
        # one-cell gaps (and the Colossus scorer) care about.
        marble.phase_timer = (PHANTOM_PHASE_SECONDS if trial == Trial.PHANTOM
                              else 0.0)
        marble.radius = MARBLE_RADIUS * 2 if trial == Trial.ELEPHANT else MARBLE_RADIUS
        # Growing starts over each run (see physics.update / GROW_MAX_TRIGGERS).
        marble.grow_triggers = 0
        # The vertigo trial pulls in the direction the run rolled (see
        # _apply_trial); every other trial — and no trial at all — leaves the
        # marble's gravity pointing straight down.
        marble.base_gravity_dir = (self.trial_gravity_dir
                                   if trial == Trial.VERTIGO else None)
        # The save's marble type drives the marble's behavior and look: the
        # 8 ball retriggers block scorers, the rubber ball bounces (and
        # wears two random half-colors), the ping-pong ball is very light.
        _configure_marble_type(marble, self.marble_type)
        self.marbles.append(marble)
        return marble
