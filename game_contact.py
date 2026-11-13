"""What a marble touching a block does: the counters, the key/lock gate, the
split a marble takes, and the contact that scores a block."""

import numpy as np

import sounds
from components import (
    PIPE_GROUP_SHAPES,
    Card,
    Effect,
    MarbleType,
    Scorer,
    Shape,
    Trial,
)
from config import *
from enemies import EnemyKind
from marble import Marble
from rolling import *


class ContactMixin:
    """A marble meeting a block: the counters, the key/lock gate, the
    split a marble takes, and the contact that scores it."""


    def _count_fresh_touch(self, block):
        """Count one fresh touch of a block's types (for the repeats-only trial).

        A marble entering contact with a block counts one distinct touch of the
        block's shape (except the plain Rect wall), each of its real effects,
        and its scorer (except Start/Finish roles) — mirroring exactly which
        types the run's uniqueness ``touched_*`` sets record. The repeats-only
        trial turns a type's uniqueness on only after it has been touched twice.
        """
        if not (self.trials_enabled and self.current_trial == Trial.REPEATS_ONLY):
            return
        if block.shape != Shape.RECT:
            self.touch_shape_counts[block.shape] = self.touch_shape_counts.get(block.shape, 0) + 1
        for e in block.effects:
            if e != Effect.NONE:
                self.touch_effect_counts[e] = self.touch_effect_counts.get(e, 0) + 1
        if block.scorer != Scorer.START and block.scorer != Scorer.FINISH:
            self.touch_scorer_counts[block.scorer] = self.touch_scorer_counts.get(block.scorer, 0) + 1

    def _count_pipe_streak(self, block):
        """Count one fresh contact toward the run's PIPE STREAK (Fountain).

        A pipe streak is a run of FRESH contacts with PIPE-GROUP blocks (Pipe,
        Drain, Pipe Bend — see components.PIPE_GROUP_SHAPES): every
        FOUNTAIN_STREAK_LENGTH different ones in a row complete it, and the
        Fountain whole card pays +0.25 xMult for each completed group when the
        run ends (see cards._named_card_units).

        Touching a pipe block that is ALREADY in the streak neither advances it
        nor breaks it: the marble rolls along a pipe's own walls and sits on the
        same pillar for many frames, and a repeat of a block it has already
        counted is not a new "different block". Touching any block outside the
        group is what breaks the streak. The Start and Finish roles are not
        blocks hit (the same rule the run's first/last block follows, see
        _handle_block_contacts), so they never break a streak.

        Multi-marble runs share ONE streak: it follows the run's contact
        sequence, exactly like the previous-block trail Echo reads.
        """
        if block.shape not in PIPE_GROUP_SHAPES:
            self.pipe_streak_blocks = []
            return
        if block in self.pipe_streak_blocks:
            return
        self.pipe_streak_blocks.append(block)
        if len(self.pipe_streak_blocks) >= FOUNTAIN_STREAK_LENGTH:
            # Three different pipe blocks in a row: one group paid. The next
            # group starts from scratch (the marble has to rack up another
            # three different blocks after these).
            self.pipe_streak_blocks = []
            self.pipe_streak_run_units += 1

    def _marble_overlaps_cell(self, marble, gx, gy):
        """True when ANY point of the marble is inside the board unit (gx, gy).

        The game's one definition of a marble being "inside" a board unit: the
        marble's own BODY (its circle, at whatever radius it currently has)
        overlapping the unit's square at all — not the marble's centre sitting in
        the cell. A marble sitting on the boundary between two columns is inside
        BOTH, and one clipping the corner of a unit is inside it too, while a
        marble merely RESTING against a unit's edge (its centre exactly a radius
        away) is not: it touches, it does not overlap — the same test the
        physics resolves collisions with (PhysicsEngine._circle_vs_rect), on the
        same square.
        """
        left = MARBLE_BOX_COORDS[0] + gx * GRID_SIZE
        top = MARBLE_BOX_COORDS[1] + gy * GRID_SIZE
        x, y = marble.position[0], marble.position[1]
        # The unit's square is [left, left + GRID_SIZE] x [top, top + GRID_SIZE],
        # so the point of it closest to the marble's centre is found by clamping.
        dx = max(left - x, 0.0, x - (left + GRID_SIZE))
        dy = max(top - y, 0.0, y - (top + GRID_SIZE))
        return dx * dx + dy * dy < marble.radius ** 2

    def _overlapped_cells(self, marble):
        """The board units a marble's body is inside (see _marble_overlaps_cell).

        A circle can only reach the units its own bounding box covers, so at most
        four cells are ever tested — which is what keeps this affordable for
        every marble every frame. There is no outer clamp: the board is infinite,
        and a unit off the edge of the WINDOW is still a unit of the board (the
        marble is walled into the unlocked region, so it never sees one).
        """
        radius = marble.radius
        x0 = int((marble.position[0] - radius - MARBLE_BOX_COORDS[0]) // GRID_SIZE)
        x1 = int((marble.position[0] + radius - MARBLE_BOX_COORDS[0]) // GRID_SIZE)
        y0 = int((marble.position[1] - radius - MARBLE_BOX_COORDS[1]) // GRID_SIZE)
        y1 = int((marble.position[1] + radius - MARBLE_BOX_COORDS[1]) // GRID_SIZE)
        cells = []
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                if self._marble_overlaps_cell(marble, gx, gy):
                    cells.append((gx, gy))
        return cells

    def _note_visited_cell(self, marble):
        """Record the board units a marble's body is in this frame (Explorer).

        The units are the board's own grid cells ANY PART of the marble is inside
        (see _marble_overlaps_cell / _overlapped_cells) — the same "inside a unit"
        definition the locked-unit measures use (the user's request: "fix the
        explorer card so that this definition of 'inside' applies to it too") —
        so a marble rolled along a cell boundary has been in both columns it
        straddles, not only the one its centre sits in. A marble outside the
        board counts only the units it still reaches into; one clear of the board
        counts none, since a unit outside the grid is not a board unit.

        The cells are added to visited_cells, a set, so a unit the marble sits in
        for many frames counts once, and two marbles in one unit do not double
        count — "the fraction of grid units a marble has been in", not a
        fraction of marble-time. Reset with the run (see reset_run), so the
        card measures this run only, and never saved: it is per-run state like
        air_time.
        """
        for cell in self._overlapped_cells(marble):
            self.visited_cells.add(cell)

    def _count_inside_time(self, marble):
        """Accumulate the time a marble spends inside a block, and in a lock.

        The Intangible whole card's two measures (see
        cards._named_card_units). "Inside" is the strict, physical sense: any
        part of the marble overlaps the block's HITBOX (PhysicsEngine.
        overlaps_block) — the overlap the physics exists to push the marble out
        of — so the phrase means exactly "a position the marble could not be in
        without the phase effect on". A marble merely resting on a block, sitting
        in a pipe's cavity or a drain's funnel, or passing through a Shape.NONE
        field, a Key, an opened Lock or a portal overlaps no hitbox and banks
        nothing; a phasing marble buried in a block banks every frame it is in
        there, including any frames after its phase has run out (it is still
        physically inside until the physics has pushed it clear).

        "Inside a locked board unit" is the same rule against the unit's own
        solid — a locked square is a board wall (see _board_wall_blocks), and the
        only way into one is phasing through it too — and the two are counted
        apart: a placed block pays the block rate, a locked unit the higher
        locked rate.

        Both are banked for the marble that is there, so two marbles inside a
        block bank twice as fast, exactly as the plane card's air time and the
        astronaut's black-hole time accumulate (see update).
        """
        for block in self.board_blocks():
            if marble.physics.overlaps_block(marble, block):
                self.inside_block_time += DT
                break
        if not self.board_locked():
            return
        for wall in self._board_wall_blocks():
            if marble.physics.overlaps_block(marble, wall):
                self.inside_locked_time += DT
                break

    def _count_locked_no_phase_time(self, marble):
        """Accumulate the time a marble spends inside a locked unit unphased.

        The Matrix whole card's measure (see cards._named_card_units), which is
        Intangible's locked-unit clause with the opposite emphasis: +45 chips a
        second instead of +15 mult, and only while the marble is NOT phasing.

        "Inside a locked board unit" is the user's own definition — any point of
        the marble overlapping any point of the unit (see
        _marble_overlaps_cell) — which for a locked square is also exactly the
        test the square's board wall gives the physics, so the two locked-unit
        measures agree about where a marble is. What separates them is the phase
        effect: a locked square is SOLID, so the only way inside one is to phase
        through it (see _board_wall_blocks), and every frame the marble is
        banking here is a frame it is inside the wall with its phase already
        gone — the frames after a phase runs out, before the physics has pushed
        it clear, and any marble that tunnelled or was squeezed in and is being
        pushed back out. A phasing marble banks nothing: the card pays for being
        stuck in the wall, not for walking through it.

        Banked per marble per frame, once however many locked units the marble
        straddles ("a marble inside a locked board unit" is a yes or no for that
        marble), so two marbles inside walls bank twice as fast, exactly as the
        air time, the black-hole time and the inside-a-block time do.
        """
        if marble.phase_timer > 0:
            return
        for gx, gy in self._overlapped_cells(marble):
            if self.is_cell_locked(gx, gy):
                self.inside_locked_no_phase_time += DT
                return

    def _gate_key_and_lock(self, marble, block):
        """The Gate whole card's two halves: collect a Key, pass through its Lock.

        Passing through a Key block (a pass-through pickup) remembers that key
        number on the MARBLE — the bookkeeping is kept whether or not the card is
        owned, like every other measure in the game — and passing through that
        key's opened Lock pays GATE_PASS_CHIPS. "Corresponding" is the pairing
        number the two halves share (see _unlock_matching_locks): a Lock is only
        ever opened by its own Key, and this looks at the marble that is moving,
        so a lock another marble's key opened pays this marble nothing.

        Every pass pays: the key is not used up, because the card reads "each
        time ... passes through its corresponding open lock". The block's own
        triggers are deliberately not consulted — Gate is about the key/lock
        mechanic, not about the Lock block's scorer half, and a Lock is a doorway
        the marble may cross as many times as it likes once it is open.
        """
        number = getattr(block, "key_number", 0)
        shape = block_shape(block)
        if shape == Shape.KEY:
            marble.collected_keys.add(number)
            return
        if shape != Shape.LOCK or getattr(block, "locked", True):
            return
        if number not in marble.collected_keys:
            return
        if not self._has_card(Card.GATE):
            return
        card = next((c for c in self.cards if c.value == Card.GATE), None)
        self.score_chips += GATE_PASS_CHIPS
        self._spawn_card_particle(card,
                                  self._particle_amount_text(GATE_PASS_CHIPS),
                                  GREEN, block=block)

    def _contact_normal(self, marble, block):
        """The unit collision normal of the marble's contact with a block.

        Physics records the normal it resolved against each block this frame
        (marble.contact_normals). When there is none — a pass-through field, or
        a contact resolved in an earlier frame — fall back to the direction
        from the block's center out to the marble.
        """
        normal = getattr(marble, "contact_normals", {}).get(block)
        if normal is None:
            offset = (np.array(block.rect.center, dtype=float)
                      - np.array(marble.position, dtype=float))
            length = float(np.linalg.norm(offset))
            normal = offset / length if length > 1e-9 else np.array([0.0, -1.0])
        normal = np.array(normal, dtype=float)
        length = float(np.linalg.norm(normal))
        return normal / length if length > 1e-9 else np.array([0.0, -1.0])

    def _split_marble(self, marble, block):
        """Splitter: spawn a copy of the marble travelling the other way.

        The copy's velocity is the velocity the marble ARRIVED at the block
        with, reflected over the collision normal from the block and then
        reversed, ``-reflect(v, n) = -v + 2 (v.n) n``, so the two halves leave
        the surface in opposite directions; the speed is unchanged. The copy is
        a full marble: it is simulated, it scores, it collides with the marble
        it came from (see PhysicsEngine.resolve_marble_collisions), and it must
        reach the finish like any other marble before the run can end.
        Splitting stops at MAX_MARBLES so the board can never grow an unbounded
        marble count.
        """
        if len(self.marbles) >= MAX_MARBLES:
            return None
        normal = self._contact_normal(marble, block)
        # The marble's velocity as it ARRIVED at the block: the collision
        # response has usually already removed the part heading into the
        # surface, so reflecting the post-impact velocity would fling the copy
        # at nearly nothing.
        incoming = np.array(
            getattr(marble, "contact_incoming", {}).get(block, marble.velocity),
            dtype=float)
        reflected = incoming - 2.0 * float(np.dot(incoming, normal)) * normal
        copy = Marble(float(marble.position[0]), float(marble.position[1]))
        # The copy inherits the marble's look and behavior (type, colors, mass,
        # bounciness, radius, size changes) and this run's trial state, so the
        # two halves stay identical apart from their velocity.
        copy.marble_type = marble.marble_type
        copy.color = marble.color
        copy.color2 = marble.color2
        copy.bouncy = marble.bouncy
        copy.restitution = marble.restitution
        copy.mass = marble.mass
        copy.radius = marble.radius
        copy.dead_zone = getattr(marble, "dead_zone", False)
        copy.finish_on_border = getattr(marble, "finish_on_border", False)
        copy.bouncy_castle = getattr(marble, "bouncy_castle", False)
        copy.effect_mass_mult = getattr(marble, "effect_mass_mult", 1.0)
        copy.start_block = getattr(marble, "start_block", None)
        # Both halves are worth what the whole marble was worth: a split copy
        # carries its parent's chips and mult and scores on from there.
        copy.chips = marble.chips
        copy.mult = marble.mult
        # The keys the half came from its parent carrying: a split copy is a full
        # marble, so a key one half collected still opens its lock for it (see
        # _gate_key_and_lock).
        copy.collected_keys = set(marble.collected_keys)
        copy.velocity = -reflected
        self.marbles.append(copy)
        self._spawn_score_particle(marble.position[0], marble.position[1],
                                   "Split", ORANGE)
        sounds.play_mech()
        return copy

    def _damage_enemy(self, marble, enemy):
        """Deal this marble's score to an enemy, then HALVE what it is worth.

        The marble pays with everything it has built: ``chips * mult`` is the
        damage. A blow used to wipe the marble's chips and mult outright; it now
        HALVES both instead (user request: "make the score halve chips and halve
        score on collision with an enemy instead of setting both to 0"), so a
        marble keeps half of what it had built — and the next blow lands for a
        quarter of this one, since both factors are halved. An ARMOURED enemy
        ignores damage once its hits are used up; a DEVOURER swallows the marble
        that touched it either way.
        """
        damage = max(float(marble.chips) * float(marble.mult), 0.0)
        marble.chips = float(marble.chips) / 2.0
        marble.mult = float(marble.mult) / 2.0
        self._spawn_block_particle(
            enemy, self._particle_amount_text(damage), ORANGE)
        sounds.play_mech()
        if enemy.can_be_hit():
            enemy.hp -= damage
            enemy.hit_flash = 0.35
            if enemy.hits_left is not None:
                enemy.hits_left -= 1
            if enemy.hp <= 0:
                self._defeat_enemy(enemy)
        if enemy.kind == EnemyKind.DEVOURER:
            self._swallow_marble(marble)

    def _defeat_enemy(self, enemy):
        """Take a killed enemy off the board."""
        enemy.alive = False
        if self.grid.get((enemy.x, enemy.y)) is enemy:
            del self.grid[(enemy.x, enemy.y)]
        self.enemies_defeated += 1
        sounds.play_mech()

    def _swallow_marble(self, marble):
        """A devourer eats the marble: it is gone from this run for good."""
        if marble in self.marbles:
            self.marbles.remove(marble)
        self._spawn_score_particle(marble.position[0], marble.position[1],
                                   "Eaten", RED)

    def _handle_block_contacts(self, blocks):
        if not self.run_active and not self.run_complete:
            return

        # Iterate over a snapshot: a splitter block adds a marble to
        # self.marbles while this loop runs (the copy is first simulated on the
        # next frame).
        for marble in list(self.marbles):
            # Whatever this marble touches pays into ITS chips and mult (see
            # Game.score_chips), so a card or token payoff fired from its
            # contacts lands on the same marble as the block scorers do.
            self._score_marble = marble
            # Locked-board walls are physical but never score: they are filtered
            # out here so they don't fire quick cards, count as touches, score,
            # or read as the first/last contacted block.
            contacts = [b for b in marble.collisions_this_tick
                        if not getattr(b, "is_board_wall", False)]
            last_contacts = list(marble.collisions_last_tick)
            # An ENEMY is fought, not scored: the marble deals its score to the
            # enemy as damage (chips x mult) and then has both HALVED (user
            # request: "make the score halve chips and halve score on collision
            # with an enemy instead of setting both to 0"), and the enemy is
            # dropped from this list so the scoring path below never sees it.
            enemies = [b for b in contacts if getattr(b, "is_enemy", False)]
            if enemies:
                for enemy in enemies:
                    self._damage_enemy(marble, enemy)
                contacts = [b for b in contacts
                            if not getattr(b, "is_enemy", False)]
                if not contacts:
                    continue
            # Quick cards armed by an earlier condition (their condition was
            # satisfied) pay now: the reward uses THIS (the next) block's hit
            # speed, exactly like a Quick block scorer.
            if self.armed_quick and any(b not in last_contacts for b in contacts):
                speed = max(np.linalg.norm(marble.velocity),
                            getattr(marble, "recent_speed", 0.0))
                gained = speed * QUICK_SCALE
                for card in list(self.armed_quick):
                    self.armed_quick.discard(card)
                    self.score_chips += gained
                    self._spawn_card_particle(card, self._particle_amount_text(gained), GREEN)
            for block in contacts:
                # Every block the marble touches this run contributes its type
                # to the end-of-run cash award (unique shapes/effects/scorers).
                if block.shape != Shape.RECT:
                    self.touched_shapes.add(block.shape)
                for e in block.effects:
                    if e != Effect.NONE:
                        self.touched_effects.add(e)
                if block.scorer != Scorer.START and block.scorer != Scorer.FINISH:
                    self.touched_scorers.add(block.scorer)
                # Shape/effect cards: each fresh collision with a matching
                # block grants +4 mult (once per collision, not every frame).
                if block not in last_contacts:
                    # A Key opens its matching Locks: a marble passing through a
                    # key block opens every lock block sharing its key number
                    # for the rest of this run.
                    if block_shape(block) == Shape.KEY:
                        self._unlock_matching_locks(block)
                    # Gate: passing through a Key remembers it on the marble, and
                    # passing that key's opened Lock pays chips (see
                    # _gate_key_and_lock).
                    self._gate_key_and_lock(marble, block)
                    # Sound the impact: every real effect on the block rings its
                    # own sound (a plain effect-less block rings the neutral
                    # one), so the player hears what the marble just hit.
                    impacts = [e for e in block.effects if e != Effect.NONE]
                    if impacts:
                        for e in impacts:
                            sounds.play_effect(e)
                    else:
                        sounds.play_effect(Effect.NONE)
                    # The repeats-only trial counts DISTINCT fresh touches per
                    # type (a type qualifies once it's been touched twice).
                    self._count_fresh_touch(block)
                    # Brain Loop: a fresh touch of a Sticky block may hand over
                    # a random action (see _brain_loop_roll).
                    self._brain_loop_roll(block)
                    # Track the run's first/last freshly-contacted blocks for
                    # Effective cards (Start cards check the first block after
                    # the start; End cards check the last block before the
                    # finish). Start/FINISH roles are not "blocks hit".
                    if (block.scorer != Scorer.START
                            and block.scorer != Scorer.FINISH):
                        if self._first_contact_block is None:
                            self._first_contact_block = block
                            # Nothing fires here any more: a start-condition card
                            # with a block-relative payoff (Effective, Summit,
                            # Airball) used to wait for the run's first block,
                            # and no card does — the named cards read the run's
                            # board, cash, cards and time, and every card that
                            # needs a block fires on a collision. The FIRST
                            # contact is still remembered (Effective Checks
                            # below read it).
                        # Echo reads the block touched just before this one, so
                        # remember the current last block before overwriting it;
                        # Rally counts every fresh touch this run.
                        self._prev_contact_block = self._last_contact_block
                        self._last_contact_block = block
                        self.run_fresh_touches += 1
                        # The Fountain card's pipe streak: this fresh contact
                        # either extends the run's run of pipe-group blocks or
                        # breaks it (see _count_pipe_streak).
                        self._count_pipe_streak(block)
                        # Remember the run's opening blocks (in touch order) for
                        # Pedestal (retrigger the first few) and Watch (only
                        # these may score). Distinct blocks only: with two
                        # marbles the same block can be freshly touched twice,
                        # and that must not use up two slots. The list is
                        # capped, so a long run never grows it.
                        if (len(self.run_first_blocks) < WATCH_BLOCK_LIMIT
                                and block not in self.run_first_blocks):
                            self.run_first_blocks.append(block)
                        # The touching marble's airborne streak at this fresh
                        # contact: Airball end-condition cards reward the streak
                        # before the run's last block was touched, and an
                        # Airball fragile card rewards the streak before the
                        # broken block itself was touched.
                        self._last_contact_air = marble.air_streak
                        self._last_contact_speed = max(
                            float(np.linalg.norm(marble.velocity)),
                            getattr(marble, "recent_speed", 0.0))
                        block.touch_air_streak = marble.air_streak
                    self._apply_cards_on_collision(block, marble)
                if block.scorer == Scorer.FINISH:
                    marble.finished = True
                    continue
                # Scoring fires on the edge of a touch (block not touched last
                # tick) and only while the block still has triggers left. Each
                # block can score at most its trigger limit (once) per run.
                if block in last_contacts:
                    continue
                if block.triggers_left <= 0:
                    continue
                if self._apply_block_score_effect(marble, block):
                    block.triggers_left = max(0, block.triggers_left - 1)
                    # Portal pairs share one trigger count: using one portal
                    # uses up the pair, so the partner's count moves in step.
                    self._sync_portal_pair_triggers(block, blocks)
                    # A splitter splits the marble once per trigger: the copy is
                    # flung out along -reflect(v, n) (see _split_marble).
                    if block.has_effect(Effect.SPLITTER):
                        self._split_marble(marble, block)
                    # The Pedestal whole card retriggers the scorer of the first
                    # few blocks the marble touches each run: a free second
                    # score that does not consume another trigger (the same
                    # shape as the 8 ball's retrigger below).
                    if (self._has_card(Card.PEDESTAL)
                            and block in self.run_first_blocks[:PEDESTAL_RETRIGGERS]):
                        self._apply_block_score_effect(marble, block)
                    # The 8 ball has a 1/4 chance to retrigger the block's
                    # scoring effect on collision — a free second score that
                    # does not consume another trigger. The roll comes from the
                    # RUN's own RNG (see run_rng), so replaying the run replays
                    # the same lucky retriggers rather than rerolling them.
                    if (getattr(marble, "marble_type", 0) == MarbleType.EIGHT_BALL
                            and self.run_rng.random() < 0.25
                            and block.scorer in (Scorer.CHIPS_ADD, Scorer.MULT_ADD,
                                                 Scorer.MULT_MUL, Scorer.QUICK,
                                                 Scorer.CASH, Scorer.SHARP,
                                                 Scorer.PARTS, Scorer.SHREDS,
                                                 Scorer.RUBBLE, Scorer.IDEAS,
                                                 Scorer.RANDOM, Scorer.EFFECTIVE,
                                                 Scorer.FRESH, Scorer.PICKY, Scorer.VOYAGER,
                                                 Scorer.SATANIC, Scorer.SUMMIT,
                                                 Scorer.AIRBALL, Scorer.SEED,
                                                 Scorer.DRILL, Scorer.LUCKY,
                                                 Scorer.ROOMY, Scorer.RALLY,
                                                 Scorer.ECHO, Scorer.POWERLINE,
                                                 Scorer.FRONTIER, Scorer.GILDED,
                                                 Scorer.BOMB, Scorer.CLUSTER,
                                                 Scorer.COLOSSUS, Scorer.UNDERTAKER,
                                                 Scorer.DEBT)):
                        self._apply_block_score_effect(marble, block)

        self.score_total = self._compute_total_score()

        if self.marbles and all(getattr(marble, "finished", False) for marble in self.marbles):
            # Procrastination gets there late: the run's FIRST completion sends
            # it one second back in time, with every block trigger refilled, and
            # the marbles fly their last second again (see the method).
            if self._procrastination_rewind():
                return
            # The end-of-run steps settle the run before the total is worked
            # out: the Spirit tokens whose payoff is a MULTIPLIER fire first,
            # then the cards that read a finished run (Explorer's visited
            # units, Astronaut's black-hole mult, Plane's air time, Skater's
            # slippery blocks, Fountain's pipe streaks, Island's groups), and
            # finally the xMult those cards banked lands at once (see
            # _flush_run_xmult).
            self._apply_end_tokens()
            self._apply_cards_on_finish()
            self._flush_run_xmult()
            self.score_total = self._compute_total_score()
            # A run may only beat its required score once the xMult its cards
            # banked lands here (Stencil's x5 at the start of the run, an
            # end-of-run card's measured factor, a multiplier token): a
            # SCORER's xMult has already landed with the touch that fired it,
            # so the bank's cards are what this step settles. The run stops
            # being active below, so no frame of the run itself could have lit
            # the fire for a score that is only finished here. Seed the fire
            # with what that score deserves while the run still counts as
            # running, so a run cleared this way lights the board and then dies
            # down exactly like one that passed while playing (see _fire_target
            # / _update_fire).
            self.fire_intensity = max(self.fire_intensity, self._fire_target())
            self.armed_quick.clear()
            self.run_active = False
            self.run_complete = True
            # ``bool(...)`` keeps the result a native Python bool (a numpy
            # comparison would store a numpy.bool_ that breaks JSON saves).
            # The level is WON by clearing its enemies while getting every
            # marble home -- the score target is gone (user request: "instead of
            # having a score requirement ... the player can only win a level
            # when all enemies are defeated and all marbles reach the finish").
            # Enemies left standing mean the level can no longer be won: the
            # player presses Y to move on and it counts as lost.
            cleared = not self.live_enemies()
            self.run_cleared = cleared
            self.run_results.append(cleared)
            self._award_cash()
            if cleared:
                self.runs_cleared += 1
                # Beating a run with a trial reveals it in the collection.
                if self.current_trial is not None:
                    self._discover_trial(self.current_trial)
            else:
                self.failed_runs += 1
            # The run is done but progression is deferred: the player chooses
            # RETRY (undo the run) or CONTINUE (move to the next run).
            self.awaiting_after_run = True
