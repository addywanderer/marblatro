"""The event loop: what a click, a key or the wheel does to the game."""

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


class InputMixin:
    """The event loop: what a click, a key or the wheel does to the game."""


    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        grid_x, grid_y = self.screen_to_cell(mouse_pos)
        _view = self.board_viewport()
        inside_grid = _view.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Autosave the current game to its slot before closing.
                if self.save_slot is not None:
                    self._retry_run()
                    save_system.save_game(self)
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                # F2 works on every screen, and is handled before the per-screen
                # branches so it never also counts as a "post-run" keypress.
                self._toggle_crt_filter()
            elif self.title_screen:
                # The title screen only accepts clicks on a save slot, the
                # ACHIEVEMENTS / UPGRADES / COLLECTION buttons, the bottom-left
                # PROFILE switcher, or QUIT — plus typing while a new profile
                # name is being entered.
                if event.type == pygame.KEYDOWN and self.profile_naming:
                    if self.profile_delete_confirm or self.profile_unlock_confirm:
                        # The inline confirms ignore typing; Esc returns to the
                        # rename field.
                        if event.key == pygame.K_ESCAPE:
                            self.profile_delete_confirm = False
                            self.profile_unlock_confirm = False
                        continue
                    if event.key == pygame.K_RETURN:
                        self._confirm_profile_name()
                    elif event.key == pygame.K_ESCAPE:
                        self._cancel_profile_naming()
                    elif event.key == pygame.K_BACKSPACE:
                        self.profile_name_text = self.profile_name_text[:-1]
                    elif (event.unicode and event.unicode.isprintable()
                            and len(self.profile_name_text) < 40):
                        self.profile_name_text += event.unicode
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.slot_confirm_index is not None:
                        # A slot's LOAD/WIPE panel is open; profile UI is hidden.
                        save_system.handle_slot_click(self, mouse_pos)
                        continue
                    if self.profile_naming:
                        # The edit prompt: Cancel (bottom-right, "Keep" while
                        # confirming), Delete / Unlock (bottom-left, rename mode
                        # only), and the Unlock-collection button (center).
                        if ui.profile_name_cancel_rect().collidepoint(mouse_pos):
                            if self.profile_delete_confirm:
                                self.profile_delete_confirm = False  # keep it
                            elif self.profile_unlock_confirm:
                                self.profile_unlock_confirm = False  # keep it
                            else:
                                self._cancel_profile_naming()
                        elif (self.profile_renaming
                                and ui.profile_name_delete_rect().collidepoint(mouse_pos)):
                            if self.profile_delete_confirm:
                                self._confirm_profile_delete()
                            elif self.profile_unlock_confirm:
                                self._confirm_profile_unlock()
                            else:
                                self._request_profile_delete()
                        elif (self.profile_renaming
                                and not self.profile_delete_confirm
                                and not self.profile_unlock_confirm
                                and ui.profile_name_unlock_rect().collidepoint(mouse_pos)):
                            self._request_profile_unlock()
                        elif PROFILE_BUTTON_RECT.collidepoint(mouse_pos):
                            self._toggle_profile_menu()
                        continue
                    if self.profile_menu_open:
                        _profile_names = profiles.list_profiles()
                        _panel, name_rows, plus = ui.profile_menu_geometry(
                            _profile_names)
                        if PROFILE_BUTTON_RECT.collidepoint(mouse_pos):
                            self._toggle_profile_menu()  # closes the list
                        elif plus.collidepoint(mouse_pos):
                            self._begin_profile_naming()
                        else:
                            picked = None
                            for i, row in enumerate(name_rows):
                                if row.collidepoint(mouse_pos):
                                    picked = i
                                    break
                            if picked is not None:
                                clicked_name = _profile_names[picked]
                                if clicked_name == profiles.current_profile():
                                    # Clicking the ACTIVE profile opens its
                                    # rename/delete popup (it is already
                                    # selected, so nothing to switch to).
                                    self._begin_profile_rename()
                                else:
                                    self._switch_profile(clicked_name)
                            else:
                                # Clicking anywhere else just closes the list.
                                self.profile_menu_open = False
                        continue
                    if PROFILE_BUTTON_RECT.collidepoint(mouse_pos):
                        self._toggle_profile_menu()
                        continue
                    if ACHIEVEMENTS_BUTTON_RECT.collidepoint(mouse_pos):
                        self.achievements_open = True
                        self.title_screen = False
                    elif UPGRADES_BUTTON_RECT.collidepoint(mouse_pos):
                        self.upgrades_open = True
                        self.title_screen = False
                    elif COLLECTION_BUTTON_RECT.collidepoint(mouse_pos):
                        self.collection_open = True
                        self.title_screen = False
                        self.collection_scroll = 0
                    else:
                        save_system.handle_slot_click(self, mouse_pos)
                continue
            elif self.achievements_open:
                # The achievements tab only accepts its return button (or QUIT).
                if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                        and ACHIEVEMENTS_RETURN_BUTTON_RECT.collidepoint(mouse_pos)):
                    self.achievements_open = False
                    self.title_screen = True
                continue
            elif self.marble_selecting:
                # The new-save screen accepts a difficulty button, a marble card
                # (which begins the game with the chosen difficulty), the
                # upgrade toggle, or the BACK button (or QUIT).
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if MARBLE_UPGRADES_TOGGLE_RECT.collidepoint(mouse_pos):
                        self.upgrades_enabled = not self.upgrades_enabled
                    elif MARBLE_BACK_BUTTON_RECT.collidepoint(mouse_pos):
                        self.marble_selecting = False
                        self.save_slot = None
                        self.title_screen = True
                    else:
                        level = self._difficulty_at(mouse_pos)
                        if level is not None:
                            self.difficulty = level
                        else:
                            for i, mt in enumerate(MarbleType.ORDER):
                                if self.marble_card_rect(i).collidepoint(mouse_pos):
                                    save_system.start_new_game_with_marble(self, mt)
                                    break
                continue
            elif self.upgrades_open:
                # The UPGRADES tab accepts buying an upgrade card or the return
                # button (or QUIT).
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if UPGRADES_BACK_BUTTON_RECT.collidepoint(mouse_pos):
                        self.upgrades_open = False
                        self.title_screen = True
                    else:
                        for i, upgrade in enumerate(metagame.UPGRADES):
                            if self.upgrade_card_rect(i).collidepoint(mouse_pos):
                                self._buy_metagame_upgrade(upgrade["id"])
                                break
                continue
            elif self.collection_open:
                # The COLLECTION tab accepts its return button, mouse-wheel
                # scrolling, or QUIT.
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if COLLECTION_BACK_BUTTON_RECT.collidepoint(mouse_pos):
                        self.collection_open = False
                        self.title_screen = True
                elif event.type == pygame.MOUSEWHEEL:
                    self.collection_scroll -= event.y * 40
                continue
            elif event.type == pygame.KEYDOWN:
                # Any key during the post-run state acts as RETRY first (undo
                # the run), then the key's normal action plays out. Y is the
                # CONTINUE key, so it must NOT retry — it moves on instead.
                if (self.run_complete and self.awaiting_after_run
                        and event.key != pygame.K_y):
                    self._retry_run()
                if event.key == pygame.K_a:
                    self.current_block_angle = (self.current_block_angle + 90) % 360
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_r:
                    # Restart the current run, keeping its trial.
                    if self.reset_run():
                        sounds.play_reset()
                    self.run_active = False
                elif event.key == pygame.K_t:
                    # Start a fresh run: exactly one new trial is chosen.
                    if self.reset_run():
                        sounds.play_run_start()
                elif event.key == pygame.K_v:
                    # Move every placed block back onto the board as a portable
                    # block instead of deleting it (erasing each cell refunds it
                    # as a block lying on its own square). The items that are not
                    # blocks are left where the player laid them out.
                    for cell, item in list(self.grid.items()):
                        if isinstance(item, Block):
                            self._erase_block_at(*cell)
                    self.marbles = []
                    self.run_active = False
                    self.run_complete = False
                    self.run_cleared = False
                elif event.key == pygame.K_b:
                    # B: sell the selected block or component.
                    self._sell_selected_item()
                elif event.key == pygame.K_g:
                    # G: Odyssey puts the selected block/component away for the
                    # run (it comes back, and pays, after the run is continued).
                    self._bank_selected_item()
                elif event.key == pygame.K_s:
                    # S: apply the selected action to its subject, assemble the
                    # assigned toolbox parts into a block (missing parts default
                    # to the free Rect shape / no effect / no scorer), disassemble
                    # a selected block, or — with nothing selected at all — build
                    # the plain default wall.
                    #
                    # COMMENTED OUT with the conditions: S also used to split a
                    # selected splittable card into its halves, and to build a
                    # card from an assigned condition + scorer.
                    if self.selected_action is not None:
                        self._apply_action()
                    # elif (getattr(self.selected_toolbox_item, "kind", None) == "card"):
                    #     self._disassemble_card()
                    # elif self.card_condition is not None:
                    #     self._build_card()
                    elif self.has_assigned_parts():
                        self._assemble_block()
                    elif isinstance(self.selected_toolbox_item, (Block, BlockItem)):
                        self._disassemble_block()
                    elif self.selected_toolbox_item is None:
                        self._assemble_block()
                    else:
                        self._disassemble_block()
                elif event.key == pygame.K_d:
                    # U: pay cash to raise the selected block's trigger limit.
                    self._upgrade_trigger_limit()
                elif event.key == pygame.K_y:
                    self._continue_run()
                elif event.key == pygame.K_p:
                    # Save the current game to the active save slot.
                    self._retry_run()
                    save_system.save_game(self)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # A fresh press starts a fresh click: whatever the previous
                    # press began (a placement drag) is over. Only the branch
                    # that means "put the item down" below turns it back on.
                    self.drawing = False
                    if self.game_over:
                        if GAME_OVER_MENU_BUTTON_RECT.collidepoint(mouse_pos):
                            self._return_to_main_menu()
                        elif GAME_OVER_NEW_BUTTON_RECT.collidepoint(mouse_pos):
                            # New game acts like wiping the save: clear it and
                            # let the player pick a marble (and upgrade toggle).
                            self.game_over = False
                            self.game_won = False
                            self.game_perfect = False
                            slot = self.save_slot if self.save_slot is not None else 1
                            save_system.begin_new_game_selection(self, slot)
                        elif GAME_OVER_CONTINUE_BUTTON_RECT.collidepoint(mouse_pos):
                            # Keep playing past the game over: the screen won't
                            # show again for this save, and the next run is set
                            # up here (the run that ended never advanced).
                            self._begin_endless_play()
                    else:
                        if RETURN_TO_MENU_BUTTON_RECT.collidepoint(mouse_pos):
                            # Leave the play screen and return to the title screen.
                            self._return_to_main_menu()
                            continue
                        if self.open_pack is not None:
                            # An OPEN PACK owns the click: its overlay is what
                            # the player is looking at, so every click goes to
                            # picking an option or leaving the rest (see
                            # _click_pack) until the pack is closed.
                            self._click_pack(mouse_pos)
                            continue
                        if (self.run_complete and self.awaiting_after_run):
                            self._retry_run()
                        # Every item on the board — the player's, and the shop's
                        # locked offers (see Game.ensure_board_cells) — is found
                        # by the square it lies on.
                        cell = (grid_x, grid_y) if inside_grid else None
                        board_item = self.item_at_cell(cell) if cell else None
                        # A press on board space that holds no item starts a
                        # PAN: with the board infinitely large, dragging empty
                        # space is how the player travels across it (user
                        # request). The click itself still does what it did (a
                        # locked square unlocks, a held item is put down); the
                        # drag that follows scrolls the view instead of
                        # dragging the item along.
                        if inside_grid and board_item is None:
                            self.panning = True
                            self.pan_from = mouse_pos
                            self.pan_moved = False
                        else:
                            self.panning = False
                        keep_selection = False
                        if (self.run_complete and self.awaiting_after_run):
                            self._continue_run()
                        elif self._trial_half_at(mouse_pos) is not None:
                            # The trial display is bought from while building:
                            # its left half swaps the trial, its right half
                            # turns it off (see _click_trial_display).
                            keep_selection = True
                            self._click_trial_display(mouse_pos)
                        elif ACTION_UPGRADE_RECT.collidepoint(mouse_pos):
                            # The action-upgrade button upgrades the selected action.
                            keep_selection = True
                            self._upgrade_action()
                        elif (cell is not None and self.is_cell_locked(*cell)
                                and not self.selection
                                and self.selected_toolbox_item is None):
                            # With NOTHING selected, a click on a locked square
                            # means "open it": with a Board Unit in hand the unit
                            # is spent and the square becomes playable. While an
                            # item IS selected the same click is not an unlock at
                            # all — it deselects everything, like any other click
                            # that is not on an item (user request).
                            keep_selection = True
                            if self.board_units > 0:
                                self._unlock_cell(*cell)
                                self.board_units -= 1
                                self._set_shop_message(
                                    f"Square unlocked "
                                    f"({self.board_units} unit(s) left)")
                                sounds.play_mech()
                                # Unlocking edits the board like placing a block:
                                # any active run is reset back to build state.
                                self.reset_run(False)
                                self.run_active = False
                            else:
                                self._set_shop_message(
                                    f"Locked square — buy a Board Unit "
                                    f"(${self._board_unit_price()}) to expand it")
                        elif board_item is not None:
                            # Clicking an item flips that item's own switch (see
                            # _toggle_item_selection): the first click turns it
                            # on, a second one turns it off, and no other item
                            # changes. The FIRST item switched on is the actor —
                            # the one that gets used up — and every item switched
                            # on after it is one of its targets.
                            keep_selection = True
                            self._toggle_item_selection(board_item)
                        elif cell is not None and not self.is_cell_locked(*cell):
                            # An empty UNLOCKED square is the "put it down"
                            # gesture: a block is built there, anything else is
                            # moved there (see _place_block_at).
                            self.drawing = True
                            keep_selection = inside_grid and self.in_hand
                        else:
                            # Anything else that is not an item — the void
                            # around the board, or a locked square while an item
                            # is selected — turns every switch off.
                            keep_selection = False
                        # A left-click on empty space is the one gesture that
                        # turns EVERY switch off at once (see
                        # _clear_toolbox_selection): the selected items and the
                        # one in hand. A click that flipped an item's switch
                        # leaves every other item alone.
                        if (not keep_selection
                                and (self.selection
                                     or self.selected_toolbox_item is not None)):
                            self._clear_toolbox_selection()
                # Right-click BUYS the shop offer under the cursor (user request:
                # "Buy a shop item by right-clicking on it"). Every offer is an
                # item lying on the board now, so this is a plain lookup: an
                # owned item (or empty space) does nothing.
                if (event.button == 3 and not self.game_over
                        and self.open_pack is None and inside_grid):
                    offer = self.shop.offer_at_cell((grid_x, grid_y))
                    if offer is not None:
                        self._buy_shop_item(offer)
                # Middle-click is the Hoard card's: it holds an offer in place
                # through the next refresh (see _toggle_shop_lock). Right-click
                # is the buy click now, so the hold needed a button of its own.
                elif (event.button == 2 and not self.game_over
                      and self.open_pack is None and inside_grid):
                    self._toggle_shop_lock(mouse_pos)

            elif event.type == pygame.MOUSEMOTION:
                # Dragging the view: the board follows the cursor (see
                # Game.pan_board). Only a press that began on board space with
                # no item on it pans — pressing an item picks the item up
                # instead.
                if self.panning:
                    dx = mouse_pos[0] - self.pan_from[0]
                    dy = mouse_pos[1] - self.pan_from[1]
                    if abs(dx) >= PAN_THRESHOLD or abs(dy) >= PAN_THRESHOLD:
                        self.pan_moved = True
                    if self.pan_moved:
                        self.pan_board(dx, dy)
                        self.pan_from = mouse_pos
                        self.drawing = False

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.drawing = False
                    self.panning = False

        if inside_grid and not self.pan_moved:
            # Blocks can only be built on unlocked squares (see
            # _place_block_at); any other item simply moves to the square the
            # player dropped it on.
            if (self.drawing and self.in_hand
                    and not self.is_cell_locked(grid_x, grid_y)):
                self._place_block_at(grid_x, grid_y)
            if self.drawing:
                # Building/editing the board keeps the current run's trial.
                self.reset_run(False)
                self.run_active = False
