"""Setting up and resetting the game: the window, the board's locked squares,
the meta-game buttons and the profile menu."""

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
from ui import Popup, ScoreParticle, TrailParticle, make_icon
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
import physics
from physics import PhysicsEngine
from shop import Shop
from toolbox import Toolbox


class CoreMixin:
    """Setting up and resetting the game: the window, the fonts, the
    board's locked squares and the player's menus."""

    def __init__(self):
        # The window, and the off-screen surface every frame is drawn into.
        # Drawing off-screen and presenting the finished frame in one blit (see
        # _present) is what keeps the CRT filter from flickering: the filter
        # rewrites the whole frame — it clears it and lays the warped bands back
        # down — and those half-finished states must never reach the window.
        self.display = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        # Every font the game draws with, built ONCE here (see FONT_SIZES). The
        # ui's drawing helpers are handed a bare surface rather than the Game,
        # so they adopt this same table through ui.bind_fonts below instead of
        # building a font of their own: they used to build a throwaway embedded
        # default font on every frame — the marble "+" marker, the key/portal
        # numbers, the Spirit token labels, the 8 ball's digit and the letter
        # glyph an id with no art falls back to — a per-frame allocation in the
        # wrong typeface.
        self.fonts = {role: pygame.font.Font(GARET_FONT_PATH,
                                             max(1, int(size * FONT_SCALE)))
                      for role, size in FONT_SIZES.items()}
        # The title screens' display face is its own typeface, unscaled.
        self.fonts["title"] = pygame.font.Font(TITLE_FONT_PATH, 90)
        self.tiny_font = self.fonts["tiny"]
        self.small_font = self.fonts["small"]
        self.font = self.fonts["font"]
        self.required_font = self.fonts["required"]
        self.total_font = self.fonts["total"]
        self.main_title_font = self.fonts["title"]
        ui.bind_fonts(self.fonts)

        pygame.display.set_caption("Marblatro")
        pygame.display.set_icon(make_icon())
        self.clock = pygame.time.Clock()
        self.running = True

        self.reset_game()
        # Every save slot's file exists from the start (empty placeholders);
        # saving a game fills one in, loading reads one back.
        save_system.ensure_saves()
        # The title screen shows first: the game's name, the 6 save slots the
        # player loads or starts a game from, and an ACHIEVEMENTS button.
        self.title_screen = True
        # The CRT screen filter (see crt.py): on by default, toggled with F2,
        # remembered per profile (metagame.json). It is a post-process over the
        # finished frame, applied by _present below.
        self.crt_filter = metagame.crt_filter()
        # The active save slot (1..6) chosen on the title screen; P saves to
        # it. None until the player picks one.
        self.save_slot = None
        self.slot_confirm_index = None  # slot (0..5) whose LOAD/WIPE panel is open
        # True while the achievements tab (a grid of all achievements) is open.
        self.achievements_open = False
        # True while the marble-type selection screen (shown when starting a
        # new save) is open; the player picks one marble type per save.
        self.marble_selecting = False
        # True while the UPGRADES tab (spend metagame dice on permanent run
        # bonuses) is open from the title screen.
        self.upgrades_open = False
        # True while the COLLECTION tab (the discovered cards, components,
        # packs and trials) is open from the title screen.
        self.collection_open = False
        # The compact bottom-of-screen popups (achievement unlocks, collection
        # discoveries) that slide up from under the screen, hold, then slide
        # back down.
        self.popups = []
        # The bottom-left PROFILE switcher on the title screen: the button
        # expands into the current profile's list (each profile owns its own
        # save slots + achievements/collection/metagame files), and its "+"
        # row opens the name-entry prompt that creates a new profile.
        self.profile_menu_open = False
        self.profile_naming = False
        # True while the popup is editing the ACTIVE profile (rename/delete);
        # False while it is creating a brand-new profile.
        self.profile_renaming = False
        # True while the edit popup shows the inline "delete this profile?"
        # confirm (its bottom buttons become Keep / Delete) instead of the
        # name field.
        self.profile_delete_confirm = False
        # True while the edit popup shows the inline "unlock the whole
        # collection?" confirm (its bottom buttons become Keep / Unlock) —
        # this permanently disables achievements for the profile.
        self.profile_unlock_confirm = False
        # True when the last delete attempt could not remove the folder (e.g.
        # Windows has it locked or read-only); shows a note in the confirm.
        self.profile_delete_error = False
        self.profile_name_text = ""

    def reset_game(self):
        """Start a brand-new game: clear the board and reset all progress."""
        self.marbles = []
        self.grid = {}
        self.score_chips = RUN_BASE_CHIPS
        self.score_mult = RUN_BASE_MULT
        self.run_active = False
        self.run_complete = False
        self.run_cleared = False
        self.awaiting_after_run = False  # True after a run while the player picks RETRY/CONTINUE
        self.score_total = 0
        # Round / run progression: 8 rounds of 3 runs each (24 runs total).
        self.run_number = 0  # total runs completed this game (0..TOTAL_RUNS)
        self.round_index = 0  # current round (0-based)
        self.run_in_round = 0  # current run within the round (0-based)
        self.required_score = REQUIRED_SCORES[0]  # the score target for the current run
        # A fresh game starts with a fresh required-score schedule. The module
        # list is persisted in saves, so loading overwrites it afterward.
        REQUIRED_SCORES[:] = [100]
        self.run_results = []  # True when the run met its score target
        self.runs_cleared = 0
        self.failed_runs = 0
        self.game_over = False
        self.game_won = False
        self.game_perfect = False  # True when every one of the 24 runs was cleared
        # Once the player clicks CONTINUE on the game-over screen, the overlay
        # never auto-shows again for this save (the game keeps going endless).
        self.continue_past_game_over = False
        # Dice earned when this game over was a defeat (shown on the game-over
        # screen; 0 for a victory/perfect win).
        self.game_over_dice_gained = 0
        self.cash = 60  # Start with finite cash for gameplay
        # The marble type chosen for this save (see MarbleType); a fresh game
        # starts vanilla until the player picks one on the selection screen.
        self.marble_type = MarbleType.VANILLA
        # The difficulty chosen for this save (see Difficulty): how many
        # trials a round is played under and how fast the required score
        # grows. A fresh game starts on the game's original balance until the
        # player picks a level on the selection screen; a loaded save restores
        # its own.
        self.difficulty = DEFAULT_DIFFICULTY
        # Whether the permanent metagame upgrade effects (bought with dice on
        # the UPGRADES tab) apply to this save's runs. The player can turn them
        # off for a save on the marble-selection screen; on by default.
        self.upgrades_enabled = True
        # Cash earned during the most recent run: the end-of-run award plus any
        # Cash/Lucky scorer cash paid out during the run (see _award_cash).
        self.last_run_cash_gained = 0
        # Where each dollar of last_run_cash_gained came from: a dict of
        # "base"/"interest"/"score"/"cards"/"scorers" amounts, filled in by
        # _award_cash and shown when the player hovers the shop's cash readout.
        self.last_run_cash_breakdown = {}
        # Cash paid out mid-run by Cash-scorer and Lucky blocks (added to cash
        # at the moment of the trigger). Folded into last_run_cash_gained when
        # the run ends, so retrying undoes it too.
        self.run_cash_gained = 0
        # Resource points banked by Shreds/Rubble/Ideas/Picky scorers. They
        # persist across runs (and saves) and convert into rewards at their
        # thresholds after a run; RETRYING a run resets them all to zero (see
        # _retry_run). (Parts banks whole components instead — granted when the
        # run is continued, see parts_run_gain — and Fresh grants a free reroll
        # immediately, so neither banks any points.)
        self.shred_points = 0
        self.rubble_points = 0
        self.idea_points = 0
        # Free shop rerolls granted by Fresh hits (one per Fresh trigger).
        # Using the shop's REFRESH button spends one instead of the cash fee.
        # They persist across runs and saves; RETRYING a run takes back only
        # the rerolls that run itself granted (see free_rerolls_run_gain).
        self.free_rerolls = 0
        # How many of the free rerolls above were granted THIS RUN. A retry is
        # a do-over of the finished run, so those come back off the bank (the
        # rerolls from earlier runs stay); reset with every fresh run.
        self.free_rerolls_run_gain = 0
        self.option_points = 0
        # Bonus shop slots banked by Picky points (every 2 points). Each slot
        # adds one extra random offer to every shop refresh, drawn at the same
        # kind odds a shelf slot's is (see components.Pack.SHELF_WEIGHTS); the
        # slots are permanent once banked.
        self.bonus_slots = 0
        # Resource points earned THIS RUN. Like the wrecking ball's per-run
        # gain, they only move into the permanent bank — and convert into
        # rewards — after a run; retrying or restarting discards them.
        self.shred_run_gain = 0
        self.rubble_run_gain = 0
        self.idea_run_gain = 0
        self.option_run_gain = 0
        # Bonuses bought with actions (see _action_mass_production,
        # _action_brainstorm and _action_grace).
        #   resource_gain_mult — Mass production v1: a factor on every resource
        #     point THIS RUN banks, set when the action is used and spent when
        #     the run's points are committed (see _commit_resource_points).
        #   resource_gain_bonus — Mass production v2: the same factor, but
        #     permanent for the game (saved).
        #   reroll_discount — Brainstorm v2: the factor every shop reroll costs
        #     from then on (0.5 halves it; saved).
        #   run_xmult_bonus — Grace v1: xMult added to the bank of the run the
        #     action was used for. Read whenever a run starts (see reset_run),
        #     so a restart or a board edit keeps it, and spent when that run
        #     ends (see _continue_run).
        self.resource_gain_mult = 1.0
        self.resource_gain_bonus = 1.0
        self.reroll_discount = 1.0
        self.run_xmult_bonus = 0.0
        # Permanent per-component purchase counts that drive the duplicate-price
        # increase. They only ever go up — never down when a copy is sold or
        # consumed — so a component's price stays elevated once it has risen.
        self.component_purchases = {}
        # Wrecking Ball (Fragile Breaks) permanent bonuses, one per unit scorer.
        # Every Fragile Breaks card permanently grows its scorer's bonus by 3/4
        # of the base every time a fragile block breaks (+3 mult / +23 chips /
        # x1.19 mult); the bonus persists across runs and is SAVED with the
        # game, applied at the start of each run the card is owned. The xMult
        # bonus is the accumulated multiplicative factor (starts at 1.0).
        self.wrecking_bonus = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                               Scorer.MULT_MUL: 1.0}
        # The Fragile Breaks gains earned THIS RUN (chips/mult add; xMult is a
        # factor starting at 1.0). They apply live to the run but only become
        # permanent (folded into wrecking_bonus) after the run; retrying
        # discards them.
        self.wrecking_run_gain = {Scorer.CHIPS_ADD: 0, Scorer.MULT_ADD: 0,
                                  Scorer.MULT_MUL: 1.0}
        # Tesseract (the whole card): a permanent, saved xMult bonus that grows
        # by TESSERACT_REROLL_XMULT every time the shop is rerolled while the
        # card is owned. It applies at the start of every run (like the
        # Wrecking Ball bonus), so it is an xMult factor starting at 1.0.
        self.tesseract_bonus = 1.0
        # Spirit tokens: one per Spirit action, each keeping a destroyed
        # block's scorer firing at the start of the runs it still covers.
        self.tokens = []
        # Locked board squares earned by Drill-scorer blocks touched THIS RUN.
        # They unlock (one per Drill trigger) after the run only; retrying
        # discards them (like cash/resource gains).
        self.drill_run_units = 0
        # Blocks destroyed THIS RUN (a fragile block breaking, or a Satanic
        # block dying): the Undertaker scorer pays +30 mult for each of them
        # before its own touch. Bombs and Sharp blocks destroy themselves AFTER
        # a run, so they never count toward it. Reset every run.
        self.run_blocks_destroyed = 0
        # True once a Debt block has triggered THIS RUN: the run then pays no
        # interest (see _award_cash). Reset at the start of every run.
        self.debt_run_triggered = False
        # How many of this run's Procrastination rewinds have been spent, one
        # per copy whose effect applies (see _procrastination_rewind). Reset at
        # the start of every run.
        self.procrastination_rewinds = 0
        # Fresh block contacts THIS RUN (Rally): every fresh non-role block
        # touch counts (re-touches count); a Rally block subtracts its own.
        self.run_fresh_touches = 0
        # Inaction: how many times the do-nothing action has been used. Every
        # INACTION_USES_PER_SLOT of them win the card area another slot, for the
        # rest of the game (saved), and a v2 use hands one over outright — those
        # are counted separately in card_slots_won, and the action slots
        # Foresight has won in action_slots_won (with action_slots_unlimited set
        # by its v2, which removes the limit altogether).
        self.inaction_used = 0
        self.card_slots_won = 0
        # Packed: board squares won by touching a Packed block or card (saved —
        # the inventory is the board, so "more room" means more board, see
        # _grant_inventory_slots). The squares granted by THIS run are counted
        # separately so a retry can take just those back, the rule Fresh's free
        # rerolls follow.
        self.inventory_slots_won = 0
        self.inventory_slots_run_gain = 0
        # The action slots Foresight has won, and whether its v2 has removed the
        # limit altogether (see Game.max_actions).
        self.action_slots_won = 0
        self.action_slots_unlimited = False
        # The items the player has toggled ON (see _toggle_item_selection: a
        # click selects an item, a second click unselects it).
        self.selection = []
        # Odyssey: the blocks and components the card has put AWAY (see
        # Game._bank_selected_item). They sit out of the inventory — drawn in
        # their own column beside the Spirit tokens — until the run is over,
        # when they come back and pay a fraction of their sell price. Capped by
        # the card's own count, and saved with the game.
        self.inaccessible = []
        # The first WATCH_BLOCK_LIMIT distinct non-role blocks freshly touched
        # THIS RUN, in touch order: the list is capped at the larger of the two
        # cards' limits, Pedestal retriggers the first PEDESTAL_RETRIGGERS of
        # them and Watch lets only these blocks score at all.
        self.run_first_blocks = []
        # The block freshly touched right before the current one (Echo copies
        # its scorer); None until a second block has been contacted.
        self._prev_contact_block = None
        # The pipe streak in progress (the DIFFERENT pipe-group blocks the
        # marble has just touched in a row) and how many groups of three the run
        # has completed — the Fountain whole card's measurement. Both are reset
        # every run; see _count_pipe_streak.
        self.pipe_streak_blocks = []
        self.pipe_streak_run_units = 0
        # The xMult this run has BANKED: the xMult cards and multiplier Spirit
        # tokens multiply into this product and it lands on the multiplier in
        # one go as the run settles (see _apply_xmult / _flush_run_xmult). A
        # scorer never banks — its multiplier lands with the touch that fired it
        # (see _apply_xmult_now).
        self.run_xmult_pending = 1.0
        # Bomb-scorer blocks touched THIS RUN, keyed by their grid cell. They
        # detonate after a run (unlock radius, then destroyed).
        self.bomb_cells = set()
        # Seconds the marble(s) spent airborne THIS RUN (plane card). A marble
        # is in the air when it has no block contact that frame.
        self.air_time = 0.0
        # Seconds the marble(s) spent inside a placed block's HITBOX this run,
        # and inside a LOCKED board unit's this run (intangible card). Both are
        # accumulated per marble per frame while the run plays (see
        # _count_inside_time); a locked unit's second counts 30 of an ordinary
        # one, which is the rate ratio the card pays (see cards._named_card_units)
        # and is applied where the measure is read, not here.
        self.inside_block_time = 0.0
        self.inside_locked_time = 0.0
        # Seconds the marble(s) spent inside a LOCKED board unit while the phase
        # effect was OFF this run (the Matrix card). The same overlap test as the
        # line above, gated on the marble not phasing (see
        # _count_locked_no_phase_time).
        self.inside_locked_no_phase_time = 0.0
        # Board units a marble has BEEN IN this run (see _note_visited_cell).
        # The Explorer card's whole payoff is the fraction of the board this
        # set covers, and while the card is owned ui.draw_board paints these
        # units in the title screen's own colour — so the set is the measure
        # AND the display. Reset with the run, never saved: it is per-run state
        # like air_time (a save is taken in the build phase, where the set is
        # cleared by the next run anyway).
        self.visited_cells = set()
        # Strength of the marble-box fire (0..FIRE_MAX_INTENSITY): it grows
        # while the score passes the required score and dies down after the run.
        self.fire_intensity = 0.0
        # Block types the marbles have touched THIS RUN, for the cash award.
        # They reset at the start of every run (see reset_run).
        self.touched_shapes = set()
        self.touched_effects = set()
        self.touched_scorers = set()
        # The first/last block freshly contacted this run: Effective cards on
        # Start/End conditions inspect them (first after the start / last
        # before the finish). Reset at the start of every run (reset_run).
        self._first_contact_block = None
        self._last_contact_block = None
        # The touching marble's airborne streak at the run's last fresh block
        # contact (Airball end-condition cards reward it). Run-scoped.
        self._last_contact_air = 0.0
        # The marble's speed at that last fresh contact (an end-condition Quick
        # card measures the run's final block hit with it). Run-scoped.
        self._last_contact_speed = 0.0
        self.run_time = 0.0
        # Seconds marbles spent being pulled by black holes THIS RUN (astronaut).
        self.black_hole_time = 0.0
        self.shop = Shop(SHOP_COORDS, self)
        # The shop shows this many extra Picky offers on every refresh.
        self.shop.bonus_slots = self.bonus_slots
        # The dynamic board: which (col, row) squares of the box are playable,
        # and how many Board Units the player holds. It is set up BEFORE the
        # toolbox below, because laying an item out asks whether its square is
        # unlocked (see ensure_board_cells). A fresh game (see
        # save_system.start_new_game_in_slot) locks the board down to its
        # starting region; a Board Unit bought in the shop unlocks any locked
        # square. reset_game starts fully unlocked as a clean base; loading a
        # save then restores its saved unlocked squares and Board Units (see
        # save_system._load_save_data).
        self.unlocked_cells = {
            (x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT)}
        # Board Units currently in hand (each buys one unlocked square).
        self.board_units = 0
        # Cached solid-wall blocks covering the locked squares (see
        # _board_wall_blocks); rebuilt only when the locked set changes.
        self._board_walls = []
        self._board_walls_dirty = True
        # The camera: how far the window has been scrolled across the infinite
        # board, in pixels (see cell_to_screen / pan_board). At rest it sits so
        # that square (0, 0) is at the window's top-left corner.
        self.camera = (0, 0)
        # The player's portable items. There is no inventory panel any more: the
        # board IS the inventory (see ensure_board_cells), so the toolbox is just
        # the list of parts the player owns.
        self.toolbox = Toolbox(self)
        # An item that leaves the inventory takes its placed block with it (see
        # _drop_placed_copy).
        self.toolbox.on_remove = self._drop_placed_copy
        # Bought cards (like Balatro jokers) lie on the board and apply their
        # effects every run while owned.
        self.cards = []
        # Bought actions (one-use power-ups that modify blocks/cards) lie on the
        # board too (max MAX_ACTIONS). An action is used by selecting it, picking
        # a block/card subject, and pressing S.
        self.actions = []
        self.selected_action = None
        self.selected_action_subject = None
        # The pack the player is currently choosing from, or None (see
        # _open_pack / _click_pack): buying a pack opens it, and its overlay
        # holds the screen until the player has kept everything the size
        # allows (or skipped the rest).
        self.open_pack = None
        # The action a pack armed for immediate use (see _keep_action_from_pack):
        # an action kept from an ACTION pack is never shelved in the action
        # area, so it waits here for its target and the S key instead. None
        # when no pack action is pending.
        self.pending_pack_action = None
        # COMMENTED OUT with the conditions: the card builder's state. Selecting
        # an owned Condition component used to start card mode, selecting a
        # Scorer paired it up, and S built the (condition x scorer) card. Every
        # card is whole now, so there is nothing to build.
        # self.card_condition = None
        # self.card_scorer = None
        # self.card_builder_indexes = {}
        # Quick-scorer cards that are armed (their condition was satisfied) and
        # waiting for the marble to hit its NEXT block, so their reward can use
        # that block's impact speed. Cleared at the start and end of each run.
        self.armed_quick = set()
        # Cash earned THIS RUN by Cash-scorer cards. It is not paid out when a
        # card fires: it is folded into the run's end-of-run cash award, so it
        # only sticks after a run (retrying discards it).
        self.card_cash_run_gain = 0
        # Components earned THIS RUN by Parts-scorer blocks and cards. Like the
        # Cash-card money above, a trigger does not hand anything over: every
        # Parts trigger banks one component (a card banks its own magnitude in
        # components), and the bank is granted only once the player CONTINUES
        # the run (see _continue_run), so a run that is retried or restarted
        # hands over nothing at all.
        self.parts_run_gain = 0
        # The current run's trial (a run plays at most one; the difficulty
        # decides which of a round's runs have one — see _choose_trial) and the
        # blocks/card it affects. The trial is CHOSEN before the run starts (at
        # game start and each time a run advances) so the info box can show it
        # during setup; its effects are applied when the run actually begins.
        # The run being set up at game start is run 0 itself (the run_number a
        # fresh game holds), not the run after the last finished one.
        self._choose_trial(self.run_number)
        # Hands tied's chosen blocks: each of them scores one time fewer this
        # run (see _trigger_limit and TRIAL_TRIGGER_PENALTY).
        self.trial_debuffed_blocks = set()
        self.disabled_card = None
        # The deal-breaker trial's gag: while the trial is on and the player
        # has never sold a card, NO block scores (see _deal_breaker_gags). The
        # sale is recorded HERE, on the game, rather than per run — selling a
        # card once frees the board for the rest of the game — and the record
        # is saved with the game, so loading a save cannot put the gag back on
        # a board the player has already freed (see save_system).
        self.card_sold = False
        # The crumbling trial's chosen fragile blocks (see _apply_trial): a
        # random 1/4 of the placed blocks shatter like real fragile blocks.
        self.trial_fragile_blocks = set()
        # The marble-weight trial rolls heavier or lighter once per run; the
        # factor (2.0 heavy / 0.9 light) scales only the DRIVING effects that
        # move the marble (accelerators, pistons, rotating shapes, conveyors,
        # black holes, repulsors), never fall speed or a bounce.
        self.trial_marble_weight = 1.0
        # The vertigo trial's gravity direction, rolled once per run (see
        # _roll_trial_decision / _apply_trial); None means straight down.
        self.trial_gravity_dir = None
        # This run's rolled trial choices (see _roll_trial_decision): every
        # random pick a trial makes is decided ONCE and replayed from here, so
        # restarting (R) or retrying a run can never reroll it. None until the
        # trial is first applied to a run; a new trial or a new run clears it.
        self.trial_decision = None
        # The seed this run's own random choices derive from, and the RNG the
        # run's in-play dice roll on (the 8 ball's retrigger chance, a Random
        # condition's own measure). A run can be replayed at will — R restarts
        # it and a finished run can be retried — so its dice must be a function
        # of the run, not of how many times the player has rolled it. The seed
        # is drawn once per run (see _choose_trial, called just above) and
        # run_rng is re-seeded from it every time the run (re)starts (see
        # reset_run), which makes a retry replay the same run instead of
        # rerolling its luck.
        self.run_rng = random.Random(self.run_seed)
        # The repeats-only trial counts distinct fresh touches per block type
        # (shape/effect/scorer) so only types touched twice contribute to the
        # run's uniqueness score. Reset at the start of each run.
        self.touch_shape_counts = {}
        self.touch_effect_counts = {}
        self.touch_scorer_counts = {}
        # The final boss of the 24th run is gone (user request: "make the final
        # bosses just normal bosses ... for the final boss, just use a random
        # normal boss"): its two modifiers are ordinary trials now, so run 24
        # plays like any other run. This flag records that an ACTION owns the
        # run's target (Grace v2 sets it to 0), so re-deriving the target when
        # the run's trial changes leaves such a run alone (see
        # _refresh_run_target).
        self.target_forced = False
        # Trials can be disabled (used by tests so a random trial can't
        # interfere with a test's expected run behavior).
        self.trials_enabled = True
        # The shop above was built BEFORE this game's opening run drew its
        # trial (see _choose_trial above), so an opening Slim pickings run
        # still has to shed its two options here. Every later shop is a
        # refreshed one, and those trim as they are built (see _refresh_shop
        # and _continue_run).
        self._trim_shop_for_trial()
        # The toolbox starts with one Start block and one Finish block. They
        # are plain Rect blocks with no effects — exactly the shape and price
        # the shop sells a role block in (see Shop._scorer_offer), so a spare
        # role trades at the same value wherever it came from.
        self.toolbox.add(BlockItem(0, 0, Shape.RECT, Effect.NONE, Scorer.START, 0,
                                   block_price_for(Shape.RECT, [], Scorer.START),
                                   "Start Block", effects=[]))
        self.toolbox.add(BlockItem(0, 1, Shape.RECT, Effect.NONE, Scorer.FINISH, 0,
                                   block_price_for(Shape.RECT, [], Scorer.FINISH),
                                   "Finish Block", effects=[]))
        # The Start and Finish run-role scorers need no entry in the player's
        # collection: every game hands the player those two toolbox blocks, so
        # collection.is_component_discovered reports them as known by itself
        # (see collection.ALWAYS_DISCOVERED_COMPONENTS). Building a Game used to
        # record them on disk instead, which wrote a stray collection.json
        # beside main.py whenever a Game was built without an active profile.
        self.shop_message = ""
        self.shop_message_timer = 0

        self.has_selected = False
        self.selected_toolbox_item = None        # The exact toolbox cell of the selection, so a duplicated component only
        # highlights the specific piece that was clicked (see ui.draw).
        self.selected_toolbox_index = None
        # Map of assigned component -> toolbox cell, for the same reason.
        self.assigned_toolbox_indexes = {}
        self.selected_shape = None  # Shape.RECT
        self.selected_effect = None  # Effect.NONE
        self.selected_scorer = None  # Scorer.CHIPS_ADD
        self.selected_scorer_amount = None  # Scorer.DEFAULT_AMOUNT[Scorer.CHIPS_ADD]
        self.current_block_angle = 0
        self.drawing = False
        # The deck overlay (see Game.toggle_deck / ui.draw_deck_overlay) is
        # showing while this is True.
        self.deck_shown = False
        # The pan gesture: a press on board space with no item under it starts
        # one (see InputMixin.handle_events), and a drag from there scrolls the
        # board (see Game.pan_board).
        self.panning = False
        self.pan_from = (0, 0)
        self.pan_moved = False
        self.paused = False
        # Seconds of play since the last autosave (see _tick_autosave). Reset
        # with every game, and only ever counted while the game is being
        # played — a save needs a slot, and the autosave skips the states it
        # would have to roll back (a run in flight, a run awaiting RETRY).
        self.autosave_timer = 0.0
        # Floating score popups spawned by scoring blocks/cards (see
        # ScoreParticle). They are purely cosmetic and clear on a new game.
        self.score_particles = []
        # Shrinking/fading marble trail dots (see TrailParticle), cleared on
        # each new run. A dot laid while the board's fire is burning carries
        # that fire, so these are also the marble's fire trail: the flames stand
        # where the marble has been rather than following its current heading.
        self.trail_particles = []
        # Compact bottom popups (achievement unlocks, collection discoveries)
        # that slide up from under the screen, hold, then slide back down.
        self.popups = []
        self.collection_scroll = 0

    # ---- Dynamic board: unlock state, walls, and expansion ----

    def _reset_board_to_start(self):
        """Lock the board to its starting region and re-lay the inventory.

        Called when a brand-new game begins (see
        save_system.start_new_game_in_slot), so every new game starts with the
        same centered region unlocked (BOARD_START_WIDTH x BOARD_START_HEIGHT
        squares), with a locked ring around it. The region is roomy on purpose:
        the player's items ALL lie on the board now, so it has to hold them — an
        item is never left on a locked square. The ring is what Board Units open
        up (see _unlock_cell).

        Items that were standing on a square the region does not cover are laid
        out again inside it (see ensure_board_cells).
        """
        x0 = (GRID_WIDTH - BOARD_START_WIDTH) // 2
        y0 = (GRID_HEIGHT - BOARD_START_HEIGHT) // 2
        self.unlocked_cells = {
            (x0 + dx, y0 + dy)
            for dx in range(BOARD_START_WIDTH)
            for dy in range(BOARD_START_HEIGHT)}
        self.board_units = 0
        # A square that is locked again cannot hold an item, so the layout is
        # re-made: anything the new region does not cover moves inside it.
        for item in self.owned_items():
            if getattr(item, "placed_cell", None) is None:
                self.set_item_cell(item, None)
        self.ensure_board_cells()
        self._board_walls = []
        self._board_walls_dirty = True
        self.reset_camera()

    def board_locked(self):
        """True while any board square is still locked (not yet unlocked).

        The board is infinite, so this asks whether the player has unlocked a
        whole window's worth of it — which is what decides whether the board is
        drawn with a locked region around the playable one at all.
        """
        return len(self.unlocked_cells) < GRID_WIDTH * GRID_HEIGHT

    # ---- The board's window: the camera, and screen <-> square conversions ----

    def board_viewport(self):
        """The screen rect the board is drawn in (everything under the top bar)."""
        return pygame.Rect(MARBLE_BOX_COORDS)

    def cell_to_screen(self, gx, gy):
        """The screen position of the top-left corner of board square (gx, gy).

        The board is infinitely large and the camera decides which part of it the
        window shows: dragging the board (see pan_board) moves the camera, and
        every square it brings into view is drawn from here.
        """
        return (MARBLE_BOX_COORDS[0] + gx * GRID_SIZE - self.camera[0],
                MARBLE_BOX_COORDS[1] + gy * GRID_SIZE - self.camera[1])

    def screen_to_cell(self, pos):
        """The board square under a screen position — any square, near or far."""
        gx = (pos[0] + self.camera[0] - MARBLE_BOX_COORDS[0]) // GRID_SIZE
        gy = (pos[1] + self.camera[1] - MARBLE_BOX_COORDS[1]) // GRID_SIZE
        return (gx, gy)

    def visible_cells(self):
        """Every board square the window shows right now, in reading order."""
        gx0, gy0 = self.screen_to_cell((MARBLE_BOX_COORDS[0],
                                        MARBLE_BOX_COORDS[1]))
        return [(gx0 + dx, gy0 + dy)
                for dy in range(GRID_HEIGHT + 2)
                for dx in range(GRID_WIDTH + 2)]

    def pan_board(self, dx, dy):
        """Drag the board by a screen delta: it moves WITH the cursor.

        Only the WINDOW moves: the board's squares keep their own coordinates, so
        an item stays on square (3, 4) however far the player drags the view
        (user request: "if the player clicks down on something that is not an
        item, and drags, the board moves with the cursor"). The board is grabbed,
        not scrolled: dragging right pulls the board right with the cursor, which
        means the camera moves the other way (user request: "reverse the direction
        that the board moves").
        """
        self.camera = (self.camera[0] - dx, self.camera[1] - dy)

    def reset_camera(self):
        """Put the window back where a fresh game starts: square (0, 0) at its corner."""
        self.camera = (0, 0)

    def is_cell_locked(self, x, y):
        """True when the given board square is not yet unlocked."""
        return (x, y) not in self.unlocked_cells

    def _unlock_cell(self, x, y):
        """Unlock one board square; returns True if it had been locked.

        A square is the inventory's room as well as the marble's playfield: an
        item waiting in the stash takes the new square at once (see
        ensure_board_cells), so unlocking is how the player makes space for what
        they own.
        """
        if (x, y) in self.unlocked_cells:
            return False
        self.unlocked_cells.add((x, y))
        self._board_walls_dirty = True
        self.ensure_board_cells()
        return True

    def _locked_adjacent_cells(self):
        """Every locked board square that shares an edge with an unlocked one.

        The frontier the player can expand the board into next: only squares
        touching (up/down/left/right of) an already-unlocked square are
        reachable, matching how Board Units unlock a clicked locked square.
        """
        candidates = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                if (x, y) in self.unlocked_cells:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if (x + dx, y + dy) in self.unlocked_cells:
                        candidates.append((x, y))
                        break
        return candidates

    def _grant_locked_units(self, count, announce=True):
        """Unlock up to ``count`` random locked squares next to an unlocked one.

        The Drill scorer earns two such squares per trigger (granted after a
        run) and the Conquistador card earns four after every run. Returns how
        many squares were actually unlocked (0 when the board is already fully
        unlocked or ``count`` is 0).

        The squares are picked off the frontier (see _locked_adjacent_cells) one
        at a time, so what the caller gets is always ``count`` squares the board
        really gained — but only against the board as it stands HERE. A Bomb
        blast that runs afterwards would cover squares this grant already added,
        which is why _continue_run detonates the bombs first.

        ``announce`` is cleared by _continue_run, which grants every source of
        expansion for the finished run together and reports them in one message
        (see _announce_board_expansion); the sound plays either way.
        """
        if count <= 0:
            return 0
        candidates = self._locked_adjacent_cells()
        random.shuffle(candidates)
        granted = 0
        for x, y in candidates[:count]:
            if self._unlock_cell(x, y):
                granted += 1
        if granted:
            if announce:
                plural = "s" if granted != 1 else ""
                self._set_shop_message(
                    f"Board expanded ({granted} square{plural} unlocked)")
            sounds.play_coin()
        return granted

    def _detonate_bombs(self, announce=True):
        """Detonate Bomb blocks primed this run (called after a run).

        Each bomb unlocks every board unit within 1 cell of it (Chebyshev
        distance, so diagonals count), then destroys itself. Retrying a run
        never detonates a bomb — it only goes off after a run.
        Returns how many board units were newly unlocked.

        ``announce`` is cleared by _continue_run, which reports the finished
        run's whole expansion — bomb blasts and drill/Conquistador grants — in
        one message (see _announce_board_expansion).
        """
        if not self.bomb_cells:
            return 0
        cells = list(self.bomb_cells)
        self.bomb_cells.clear()
        unlocked = 0
        for x, y in cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    # The board is infinite, so a blast opens its neighbours
                    # wherever they are.
                    if self._unlock_cell(nx, ny):
                        unlocked += 1
            # A bomb destroys itself, and the item it was built from with it (see
            # _release_block_item): a block whose item stayed behind could be
            # fielded a second time.
            bomb = self.grid.pop((x, y), None)
            if bomb is not None:
                self._forget_item(bomb)
                self._release_block_item(bomb)
        if unlocked:
            if announce:
                plural = "s" if unlocked != 1 else ""
                self._set_shop_message(
                    f"Bombs detonated: {unlocked} unit{plural} unlocked")
            sounds.play_coin()
        return unlocked

    def _announce_board_expansion(self, blasted, drilled, conquered):
        """Report every square the finished run unlocked, and where they came from.

        The three sources are Bombs (a fixed 1-cell blast around each primed
        bomb), the Drill scorer (squares banked by its triggers), and the
        Conquistador card. They are granted as one step and reported as one
        message naming each that contributed, because each grant used to
        announce itself on its own — and with a bomb in the run the blast
        always went last, so its message replaced the drill's and a player whose
        drill had just expanded the board was told only about the bomb.
        """
        total = blasted + drilled + conquered
        if not total:
            return
        sources = []
        if blasted:
            sources.append(f"{blasted} from the bomb blast")
        if drilled:
            sources.append(f"{drilled} from the drill")
        if conquered:
            sources.append(f"{conquered} from Conquistador")
        plural = "s" if total != 1 else ""
        detail = f" ({', '.join(sources)})" if sources else ""
        self._set_shop_message(
            f"Board expanded {total} square{plural}{detail}")

    # The Board Unit tile used to live in the shop panel. There is no panel any
    # more: the tile is a shelf OFFER lying on the board (see
    # items.BoardUnitOffer), bought by right-clicking it like every other offer
    # (see Game._buy_board_unit).

    def _board_wall_blocks(self):
        """The solid wall Blocks covering the locked squares (cached).

        The board is infinitely large, so "every locked square" is infinite and
        cannot be walled: only the squares on the FRONTIER — the locked squares
        that share an edge with an unlocked one — need a wall, because a marble
        can only reach a locked square through the frontier. That ring closes
        around the unlocked region however it is shaped (an island of unlocked
        squares is walled on every side), so the marble still cannot leave.

        The walls are never added to the grid: the physics engine collides the
        marbles against them so the marble stays inside the unlocked region,
        but they are filtered out of all scoring/contact handling (see
        update/_handle_block_contacts). The cache is rebuilt only when the
        unlocked set changes.
        """
        if self._board_walls_dirty:
            origin = (MARBLE_BOX_COORDS[0], MARBLE_BOX_COORDS[1])
            walls = []
            for x, y in self._locked_adjacent_cells():
                wall = Block(x, y, shape=Shape.RECT, effect=Effect.NONE,
                             scorer=Scorer.NONE, scorer_amount=0,
                             origin=origin)
                wall.is_board_wall = True
                walls.append(wall)
            self._board_walls = walls
            self._board_walls_dirty = False
        return self._board_walls

    def board_pixel_bounds(self, pad=0):
        """The pixel rect the marble may move in: the unlocked region's bounds.

        The board itself is infinite, so the only bound the simulation has is the
        squares the player has opened up — the region the marble is walled into
        (see _board_wall_blocks). An empty board falls back to the window.

        ``pad`` grows the rect by that many squares on every side. The marble is
        clamped to a padded rect, not the exact region: the PHASE effect is meant
        to let a marble travel into the locked squares around it (Intangible and
        Matrix both pay for the seconds spent inside one), so the hard clamp has
        to sit a little outside the region the walls enclose.
        """
        if not self.unlocked_cells:
            return (MARBLE_BOX_COORDS[0] - pad * GRID_SIZE,
                    MARBLE_BOX_COORDS[1] - pad * GRID_SIZE,
                    MARBLE_BOX_COORDS[2] + 2 * pad * GRID_SIZE,
                    MARBLE_BOX_COORDS[3] + 2 * pad * GRID_SIZE)
        xs = [cell[0] for cell in self.unlocked_cells]
        ys = [cell[1] for cell in self.unlocked_cells]
        x0, y0 = min(xs) - pad, min(ys) - pad
        w = max(xs) - min(xs) + 1 + 2 * pad
        h = max(ys) - min(ys) + 1 + 2 * pad
        return (MARBLE_BOX_COORDS[0] + x0 * GRID_SIZE,
                MARBLE_BOX_COORDS[1] + y0 * GRID_SIZE,
                w * GRID_SIZE, h * GRID_SIZE)

    def _simulation_blocks(self):
        """The block list physics collides with this frame.

        The locked squares on the frontier act as solid invisible walls (see
        _board_wall_blocks) so marbles stay inside the unlocked region; there are
        only ever as many of them as the region has edges, so they are always
        included.

        Only BLOCKS are physical: the board also holds every other item the
        player owns (a component, a card, an action — see ensure_board_cells),
        and those stand on their square without ever touching the marble.
        """
        return self.board_blocks() + self._board_wall_blocks()

    # -----------------------------------------------------------------------
    # The board as the player's inventory: every owned item stands on a square.
    # -----------------------------------------------------------------------
    def board_area(self):
        """How many squares the board shows at once (the window's size in squares)."""
        return GRID_WIDTH * GRID_HEIGHT

    def owned_items(self):
        """Every item the player owns OUTSIDE the board's blocks.

        The portable items (blocks waiting to be built, component pieces), the
        cards, the actions and the Spirit tokens: everything that used to live in
        the inventory panel, the card area and the action row. They all stand on
        board squares now, but ownership is still theirs to hold — a card's
        effect, a component's assembly and an action's target all read these
        lists.
        """
        return (list(self.toolbox.every_item()) + list(self.cards)
                + list(self.actions) + list(self.tokens))

    def _adopt_card(self, item):
        """Take ownership of a card and deal it a square at once.

        Taking an item is what puts it in the hand: without seating it the card
        would sit with no square until something else happened to run the layout,
        which now means "in the deck" rather than "on the board" (see
        Game._on_item_gained). The very same card object is never owned twice (see
        Game.owns_item): a second reference would share the first one's board
        square and its switch. A purchase returns it to the deck instead (see
        Game._to_deck).
        """
        if self.owns_item(item):
            return
        self.cards.append(item)
        self._on_item_gained(item)

    def _adopt_action(self, item):
        """Take ownership of an action and deal it a square at once."""
        if self.owns_item(item):
            return
        self.actions.append(item)
        self._on_item_gained(item)

    def owns_item(self, item):
        """True when this EXACT object is one of the player's items.

        Identity, not value: two copies of a card are different items, and a
        shelf offer is not the player's until it is bought (see items.owned_copy).
        One object is never owned twice — a double click on a shop offer is one
        purchase, not two, and no item can wear two board squares or two
        switches (user report: glitches with several copies of the same item).
        """
        if item is None:
            return False
        return any(item is owned for owned in self.owned_items())

    def item_cell(self, item):
        """The (x, y) square ``item`` stands on, or None when it has none.

        A Block keeps its square in ``x``/``y`` (it always has); every other item
        keeps the board square it lies on in ``board_cell``. An item whose block
        stands on the board answers with THAT square (see BlockItem.placed_cell):
        the item and its block are one existence, so a square the item used to lie
        on never answers for it — otherwise a block moved elsewhere could still be
        picked up (or a second copy built) on the square it was laid out in.

        ``col``/``row`` are NOT the board square: they are the cell the SHOP draws
        the offer in, and a bought offer keeps them (so a component bought from
        the shelf must not appear on the board square its price tag hung over).
        """
        if isinstance(item, Block):
            x, y = getattr(item, "x", None), getattr(item, "y", None)
        else:
            placed = getattr(item, "placed_cell", None)
            x, y = (tuple(placed) if placed else (None, None))
            if not (isinstance(x, int) and isinstance(y, int)):
                x, y = getattr(item, "board_cell", None) or (None, None)
        if not isinstance(x, int) or not isinstance(y, int):
            return None
        # No range check: the board is infinitely large, so any integer square
        # is a real square. Which of them the player can see is the camera's
        # business (see Game.cell_to_screen), not a bound on the board.
        return (x, y)

    def set_item_cell(self, item, cell):
        """Put ``item`` on a board square (or take it off with ``cell=None``)."""
        x, y = (None, None) if cell is None else cell
        if isinstance(item, Block):
            item.x, item.y = x, y
        else:
            item.board_cell = None if x is None else (x, y)

    def _free_board_cell(self, claimed):
        """The first UNLOCKED square nothing stands on, in reading order.

        Items only ever lie on unlocked squares (user request: "make sure all
        items are always in an unlocked square"): a locked square is outside the
        region the player has opened up, so an item there would be out of reach —
        the player cannot click, move or assemble it, and once the board is
        unlocked it would be buried under the marble's playfield.

        The board is infinitely large, so the squares to try are the ones the
        player has UNLOCKED, not a rectangle of the window: reading order (top to
        bottom, left to right) keeps the layout stable and easy to find, and
        ``claimed`` is the set of squares already spoken for. An item is laid out
        where the marble can reach it, which is exactly what "unlocked" means.
        """
        for y, x in sorted((cell[1], cell[0]) for cell in self.unlocked_cells):
            if (x, y) in claimed:
                continue
            return (x, y)
        return None

    def ensure_board_cells(self):
        """Keep every item that is ON the board on a valid square; say which are taken.

        The board is the player's HAND now (user request: "create a deck ... draw
        4 random cards from the deck onto the board"), so this no longer deals a
        square to everything the player owns: an item lying on the board keeps the
        square it claims unless a BLOCK has taken it or the square is (or has
        become) LOCKED, and an item that has no square is simply IN THE DECK (see
        Game.deck_items) until a draw deals it one. Only two kinds are always
        placed: the START and FINISH role blocks (so a run can always begin) and
        the shop's offers.

        It is idempotent and cheap (a few dozen items over the unlocked squares),
        so the board reads it whenever it draws or hit-tests rather than every
        owner having to remember to call it after a change.

        An item that is standing as its BLOCK (a placed block keeps its item —
        see BlockItem.placed_cell) is not laid out afresh: the block already
        occupies a square, and drawing the item there too would show one block
        twice. Its own spot stays RESERVED for it, though (user request: "when a
        block is placed on the board, make its spot in the inventory still
        occupied with the block"): nothing else may be laid out where the item
        will come back to when its block is taken up.
        """
        items = []
        claimed = set(self.grid)
        for item in self.owned_items():
            if getattr(item, "placed_cell", None) is not None:
                home = getattr(item, "board_cell", None)
                if home is not None:
                    claimed.add(tuple(home))
                continue
            items.append(item)
        for item in items:
            cell = self.item_cell(item)
            if cell is None or cell in claimed or self.is_cell_locked(*cell):
                self.set_item_cell(item, None)
            else:
                claimed.add(cell)
        # A role block is never in the deck: the START and FINISH blocks stay on
        # the board so the player can always build a run (see _cycle_deck).
        for item in items:
            if (self.item_cell(item) is None
                    and getattr(item, "scorer", None) in (Scorer.START,
                                                          Scorer.FINISH)):
                cell = self._free_board_cell(claimed)
                if cell is None:
                    continue
                self.set_item_cell(item, cell)
                claimed.add(cell)
        # The player's own items come before the shelf's: something that was
        # waiting for a square (see _on_item_gained) takes a newly opened one
        # before an offer is dealt it.
        self._sync_stash(claimed)
        # The shop's offers stand on the board too (user request: "make each
        # shop option an item ... allow shop items to be selected and moved
        # around"), and their squares are claimed BEFORE the offered items are
        # dealt squares: a new hand must never be laid out on top of an offer the
        # player can see and click.
        offers = list(self.shop.items) if getattr(self, "shop", None) else []
        # An offer the player already owns (a purchase that has just been adopted
        # while the shelf still lists it) is laid out as the owned item it now
        # is; treating it as an offer too would strip the square it was unlocked
        # in and deal it somewhere else.
        offers = [offer for offer in offers if not self.owns_item(offer)]
        for offer in offers:
            cell = self.item_cell(offer)
            if cell is None or cell in claimed or self.is_cell_locked(*cell):
                self.set_item_cell(offer, None)
            else:
                claimed.add(cell)
        for offer in offers:
            if self.item_cell(offer) is None:
                cell = self._free_board_cell(claimed)
                if cell is None:
                    continue
                self.set_item_cell(offer, cell)
                claimed.add(cell)
        return claimed

    def _sync_stash(self, claimed=None):
        """Seat the stashed items the board has room for; keep them owned otherwise.

        An item only ever lands in the stash when the board had no room for it as
        it was gained (see _on_item_gained), so a square opening up — the player
        unlocking one, or a block being taken off the board — is what brings it
        out. Items with no square that are simply IN THE DECK are not stashed, and
        are never seated here: the deck deals them (see Game.draw_deck_hand).
        """
        if claimed is None:
            claimed = set(self.grid)
        for item in list(self.toolbox.stash):
            if self.item_cell(item) is None:
                cell = self._free_board_cell(claimed)
                if cell is not None:
                    self.set_item_cell(item, cell)
                    claimed.add(cell)
            if (self.item_cell(item) is not None
                    or self.is_item_selected(item)):
                self.toolbox.stash.remove(item)
                self.toolbox.items.append(item)

    def item_at_cell(self, cell):
        """The item standing on a board square, or None.

        Blocks live in ``grid``; every other item laid out on the board — the
        player's own and the shop's offers — is found by the square it claims
        (see ensure_board_cells).
        """
        block = self.grid.get(cell)
        if block is not None:
            return block
        self.ensure_board_cells()
        for item in self.owned_items():
            if self.item_cell(item) == cell:
                return item
        shop = getattr(self, "shop", None)
        return shop.offer_at_cell(cell) if shop is not None else None

    def is_shop_offer(self, item):
        """True when ``item`` is one of the shop's offers (not the player's yet).

        An offer stands on the board and is selected and moved like any other
        item, but it is only UNLOCKED when it is bought (right-click), so the
        rules that treat an item as the player's — selling, banking, assembling
        — check this first.
        """
        return self.shop.is_offer(item)

    def board_blocks(self):
        """The BLOCKS standing on the board — the only board items the marble meets.

        The board also holds every other item the player owns (see
        ensure_board_cells), and those are scenery: everything that simulates,
        scores or reads a board square as a block asks this rather than walking
        ``grid.values()``.
        """
        return [item for item in self.grid.values() if isinstance(item, Block)]

    def board_items(self):
        """Every item standing on the board: the blocks and everything else.

        An item whose block is standing for it (see BlockItem.placed_cell) is
        left out: the block already occupies the square, and the item would
        otherwise be drawn twice. The shop's offers are on the board too (user
        request: each shop option is an item you can select and move), so they
        are drawn and hit-tested here like everything else.
        """
        self.ensure_board_cells()
        laid_out = [item for item in self.owned_items()
                    if self.item_cell(item) is not None
                    and getattr(item, "placed_cell", None) is None]
        shop = getattr(self, "shop", None)
        if shop is not None:
            laid_out += [offer for offer in shop.items
                         if self.item_cell(offer) is not None]
        laid_out.sort(key=lambda item: self.item_cell(item)[::-1])
        return list(self.grid.values()) + laid_out

    def _buy_board_unit(self):
        """Buy one Board Unit (see _board_unit_price): an expansion for any locked square.

        Always available (the shop's fixed Board Unit tile), buyable as many
        times as the player's cash allows. Units in hand are saved/restored
        with the game (see save_system) and only reset when a NEW game starts.
        """
        price = self._board_unit_price()
        if self.cash < price:
            self._set_shop_message(f"Need ${price} for a Board Unit")
            return
        self.cash -= price
        self.board_units += 1
        self._set_shop_message(f"Board Unit ready ({self.board_units} in hand)")
        sounds.play_coin()

    def _board_unit_price(self):
        """The Board Unit price: BOARD_UNIT_PRICE, or the Mineshaft price.

        The Mineshaft whole card makes expanding the board cheaper. The shop's
        Board Unit tile, its price label and every "unlock this square"
        message read this method, so the displayed and charged prices always
        agree.
        """
        if self._has_card(Card.MINESHAFT):
            return MINESHAFT_BOARD_UNIT_PRICE
        return BOARD_UNIT_PRICE

    def _reset_profile_popup(self):
        """Close any profile popup (create/rename/delete/unlock) and reset its fields."""
        self.profile_naming = False
        self.profile_renaming = False
        self.profile_delete_confirm = False
        self.profile_unlock_confirm = False
        self.profile_delete_error = False
        self.profile_name_text = ""

    def _toggle_profile_menu(self):
        """Open/close the expandable profile list (or close the popup)."""
        if self.profile_naming:
            self._reset_profile_popup()
        self.profile_menu_open = not self.profile_menu_open

    def _begin_profile_naming(self):
        """Open the name-entry prompt for a brand-new profile."""
        self._reset_profile_popup()
        self.profile_naming = True
        self.profile_menu_open = False

    def _begin_profile_rename(self):
        """Open the edit popup for the ACTIVE profile: rename it (Enter) or
        delete it (the bottom-left Delete button)."""
        self._reset_profile_popup()
        self.profile_naming = True
        self.profile_renaming = True
        self.profile_name_text = profiles.current_profile()
        self.profile_menu_open = False

    def _cancel_profile_naming(self):
        """Abandon the popup and return to the profile list."""
        self._reset_profile_popup()
        self.profile_menu_open = True

    def _confirm_profile_name(self):
        """Apply the typed name: rename the active profile, or create a new
        one (whichever popup is open)."""
        name = self.profile_name_text.strip()
        if not name:
            return  # a name is required
        if self.profile_renaming:
            profiles.rename_profile(profiles.current_profile(), name)
            self._reset_profile_popup()
            return
        created = profiles.create_profile(name)
        self._switch_profile(created)

    def _request_profile_delete(self):
        """Swap the edit popup's name field for the inline delete confirm."""
        self.profile_delete_confirm = True
        self.profile_delete_error = False  # a fresh attempt hides any old note

    def _confirm_profile_delete(self):
        """Delete the active profile and settle on a remaining one."""
        if not profiles.delete_profile(profiles.current_profile()):
            # The folder could not be removed (a Windows lock or a stubborn
            # read-only folder); keep the confirm open and tell the player so
            # the delete never looks like it worked when it did not.
            self.profile_delete_error = True
            return
        self._reset_profile_popup()
        self.save_slot = None
        self.slot_confirm_index = None
        self.profile_menu_open = False
        self.reset_game()
        self.title_screen = True
        self.achievements_open = False
        self.marble_selecting = False
        self.upgrades_open = False
        self.collection_open = False

    def _request_profile_unlock(self):
        """Swap the edit popup's name field for the unlock-collection confirm."""
        self.profile_unlock_confirm = True

    def _confirm_profile_unlock(self):
        """Reveal every collection entry for the active profile, then disable
        its achievements (no new ones can unlock after this)."""
        self._unlock_entire_collection()
        achievements.disable()
        self._reset_profile_popup()
        self.profile_menu_open = True  # back to the profile list

    def _unlock_entire_collection(self):
        """Discover every entry the COLLECTION tab can show for this profile."""
        for value in Card.ORDER:
            collection.discover_card(value)
        # The condition codex rows are gone; a match group is what a card is
        # built on now, recorded by its index in MATCH_GROUPS.
        for index in range(len(MATCH_GROUPS)):
            collection.discover_match_group(index)
        for value in Action.ORDER:
            collection.discover_action(value)
        for value in Shape.ORDER:
            collection.discover_component(Component.SHAPE, value)
        for value in Effect.ORDER:
            collection.discover_component(Component.EFFECT, value)
        for value in Scorer.ORDER:
            collection.discover_component(Component.SCORER, value)
        for value in Pack.ORDER:
            collection.discover_pack(value)
        for value in Trial.ORDER:
            collection.discover_trial(value)

    @property
    def in_hand(self):
        """True when an item is selected to be put down on the board.

        The item in hand is what a click or drag on the board puts down: a BLOCK
        is built into a block (see _place_block_at), and any other item — a
        component, a card, an action, a shop offer — is MOVED to the square the
        player clicks (see _move_item_to). Every item on the board can be picked
        up that way (user request: "cards and actions should be able to be moved
        around" — and shop offers "moved around just like other items"), so this
        is simply "is the item in hand one that is on the board?".
        """
        item = self.selected_toolbox_item
        if item is None:
            return False
        if isinstance(item, Block):
            return True
        if self.owns_item(item):
            return True
        # A shop offer is not owned yet, but it lies on the board and can be
        # arranged like everything else on it.
        return self.is_shop_offer(item)

    def in_hand_is_block(self):
        """True when the item in hand is a BLOCK to build, not an item to move.

        The two gestures a click on a square can mean are "build this block here"
        (see _place_block_at) and "move this item here" (see _move_item_to), and
        only a block the PLAYER has is built. A shop offer is scenery even when
        it is a block offer — it is not the player's yet — so it is arranged on
        the board and bought by right-click, never stamped into the grid.
        """
        item = self.selected_toolbox_item
        if isinstance(item, Block):
            return True
        return (getattr(item, "kind", None) == "block"
                and not self.is_shop_offer(item))

    def _switch_profile(self, name):
        """Make ``name`` the active profile from the title screen.

        profiles.switch_to re-points save_system / achievements / collection /
        metagame at the new profile's files and resets their caches; here we
        clear any game/slot state that belonged to the old profile.
        """
        profiles.switch_to(name)
        self._reset_profile_popup()
        self.save_slot = None
        self.slot_confirm_index = None
        self.profile_menu_open = False
        self.reset_game()
        self.title_screen = True
        self.achievements_open = False
        self.marble_selecting = False
        self.upgrades_open = False
        self.collection_open = False