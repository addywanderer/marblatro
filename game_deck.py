"""The player's DECK: every item they own, and the hand of items drawn from it.

The deck is what a run is built from (user request: "create a deck ... when a
new run begins, draw 4 random cards from the deck onto the board, along with the
shop's offers"). It holds EVERY item the player owns — blocks waiting to be
built, component pieces, cards, actions — while the board shows only the HAND:
the DECK_DRAW_SIZE items currently drawn from it. An item is "in the deck" when
it has no board square (see Game.item_cell); drawing it gives it one, and
returning it takes that square away.

Two kinds of item never leave the board: the START and FINISH blocks, which stay
where the player put them so a run can always begin, and the four TOOLS, which
are the verbs a structure is opened with (see Structure / Game._apply_tool) and
so have to be in reach every run. Spirit tokens stay too: they are live for the
run they were made in.
"""

import random

import ui
from components import Action, Card, Component, Group, Modifier, Scorer, Tool
from config import *
from blocks import Block
from items import ScorerToken


class DeckMixin:
    """The deck: which items are drawn into the hand, and cycling them."""

    def drawn_items(self):
        """The items this run's draw dealt from the deck.

        What is ON the board is the hand, but not all of it was DRAWN: the START
        and FINISH blocks and the four TOOLS are always there, and everything
        gained during a run (a purchase, a pack's pick, a structure's reward) is
        laid out where it lands. ``deck_drawn`` is the draw itself, at most
        DECK_DRAW_SIZE items (see draw_deck_hand), which is what the DECK button
        reports (see ui.deck_button_label).
        """
        return list(getattr(self, "deck_drawn", []))


    def deck_items(self):
        """Every item the player owns that is NOT lying on the board.

        These are the cards a draw can deal: an item off the board has no square
        (see Game.item_cell), so it waits in the deck until it is drawn. The
        player still owns it — a card in the deck still pays its whole-card
        effect (see _has_card), because the deck is the player's collection, and
        the hand is only the part of it they can physically lay out.
        """
        return [item for item in self.owned_items()
                if self.item_cell(item) is None]

    def deck_overlay_items(self):
        """The items the deck overlay lists, sorted into their groups.

        The whole collection, grouped by FAMILY (see components.Group): blocks
        first, then the parts they are built from, then the cards, actions and
        the rest — so the overlay reads like the deck it is rather than like the
        order things were bought in. Inside a group the items are alphabetical.
        """
        return sorted(
            self.owned_items(),
            key=lambda item: (Group.rank(Group.of(item)),
                              self._item_name(item).lower()))

    def deck_item_at(self, pos):
        """The item the deck overlay is showing under a screen position, or None."""
        for index, item in enumerate(self.deck_overlay_items()):
            if ui.deck_item_rect(index).collidepoint(pos):
                return item
        return None

    def hand_items(self):
        """The items currently drawn from the deck: the ones lying on the board."""
        return [item for item in self.owned_items()
                if self.item_cell(item) is not None]

    def _to_deck(self, item):
        """Return one item to the deck: it keeps no board square.

        A shop purchase is deck-building (user request: "when a shop item is
        bought, add it to the deck"), so the item it hands over goes straight
        into the deck rather than onto the board: the player draws it with the
        next hand, and the shelf keeps selling its offer, so several copies can
        be bought.
        """
        if item is None:
            return
        self.set_item_cell(item, None)
        if getattr(item, "placed_cell", None) is not None:
            item.placed_cell = None
        # A deck item is not overflow: it is deliberately off the board, so it
        # must not wait in the stash where the layout would deal it a square as
        # soon as one opened up (see _sync_stash).
        if item in self.toolbox.stash:
            self.toolbox.stash.remove(item)
            self.toolbox.items.append(item)
        self._forget_item(item)

    def _on_item_gained(self, item):
        """A new item joined the player's ownership: put it in the hand.

        Everything the player GAINS during play — an assembled block, the parts a
        disassembly returns, a pack's pick, a reward — joins the hand with a board
        square of its own, so it can be laid out at once. A SHOP purchase is the
        exception and goes to the deck instead (see _to_deck). An item the board
        has no room for waits in the toolbox's stash and takes a square as soon as
        one opens up (see _sync_stash).
        """
        if item is None or self.item_cell(item) is not None:
            return
        claimed = self.ensure_board_cells()
        cell = self._free_board_cell(claimed)
        if cell is not None:
            self.set_item_cell(item, cell)
            return
        if self.toolbox.contains(item) and item not in self.toolbox.stash:
            self.toolbox.items.remove(item)
            self.toolbox.stash.append(item)

    def draw_deck_hand(self):
        """Draw DECK_DRAW_SIZE random items from the deck onto the board.

        The hand is what the player can lay out this run, so it is drawn fresh
        from the whole deck; fewer items simply deal a smaller hand. The draw is
        always AT MOST DECK_DRAW_SIZE items (user request: "make sure that only 4
        items are drawn from the player's deck each run"), and what it dealt is
        remembered in ``deck_drawn`` so the DECK button can report it (see
        ui.deck_button_label). Returns the items drawn.
        """
        self.ensure_board_cells()
        deck = self.drawable_deck_items()
        drawn = random.sample(deck, min(DECK_DRAW_SIZE, len(deck)))
        dealt = []
        for item in drawn:
            claimed = self.ensure_board_cells()
            cell = self._free_board_cell(claimed)
            if cell is None:
                # No square left on the board: the item stays in the deck, and
                # the next run's draw can deal it.
                continue
            self.set_item_cell(item, cell)
            dealt.append(item)
        self.ensure_board_cells()
        self.deck_drawn = dealt
        # A card that costs something to draw charges it now (Smelly Socks hands
        # a cardmate back to the deck -- see _settle_smelly_socks).
        self._settle_smelly_socks(dealt)
        return dealt

    def _draw_one_item(self, cell=None, pool=None):
        """Draw ONE random item from the deck (see draw_deck_hand).

        What Wasteful uses when it throws two items away for a fresh one: the
        item comes out of the deck, just as a run's hand does, and takes ``cell``
        (the square the discarded block was standing on) when it is free, so the
        replacement appears where the sacrifice was made. Returns the item, or
        None when the deck is empty.

        ``pool`` draws from that list of items instead of the whole deck, which
        is how a card that deals one KIND of item does it (Floor plans draws
        blocks — see deck_blocks). The caller passes a fresh pool each time,
        because what it just drew is no longer in the deck.
        """
        deck = self.drawable_deck_items() if pool is None else list(pool)
        if not deck:
            return None
        item = random.choice(deck)
        if cell is not None and self.item_at_cell(cell) is None:
            self.set_item_cell(item, cell)
        else:
            self._on_item_gained(item)
        self._settle_smelly_socks([item])
        return item

    def deck_blocks(self):
        """The BLOCKS waiting in the deck (what a Floor plans draws).

        A block is an item whose kind is "block" (see items.BlockItem): the
        ready-made blocks a run is built from, as opposed to the parts they are
        assembled from and the cards, actions, tools and packs the deck can also
        hold. A FORGOTTEN block is not drawable, exactly as it is not for any
        other draw (see drawable_deck_items).
        """
        return [item for item in self.drawable_deck_items()
                if getattr(item, "kind", None) == "block"]

    def drawable_deck_items(self):
        """The deck items a draw may deal: everything not FORGOTTEN.

        User request: the modifier "forgotten" means "cannot be drawn, remove 1
        stack of forgotten each run" -- so an item carrying it sits in the deck,
        still owned (its whole-card effects still pay, see _has_card), but no
        draw can deal it until the stacks wear off (see _age_modifiers).
        """
        return [item for item in self.deck_items()
                if not Modifier.stacks(item, Modifier.FORGOTTEN)]

    # --- Smelly Socks: what a draw costs while it is in the hand ------------

    def _settle_smelly_socks(self, drawn):
        """A drawn Smelly Socks sends one of its handmates back to the deck.

        User request: "+15 chips and +2 mult at start of run, but discard a
        random card when you draw this card (unplayable)" — and the discard is
        NOT a destruction: "the card goes back into the deck... the player could
        draw it again using cards that draw more cards". So the victim is put
        back in the deck (see _to_deck), where any draw can deal it again, and
        the run simply has one fewer item in its hand.

        The victim is a random CARD drawn with it (this run's hand, see
        deck_drawn): the socks shares a hand with what the draw dealt, so what
        it takes is one of those cards. A draw that brought the socks alone (a
        mid-run draw, a Lantern) takes from the hand it joined. With no other
        card in the hand there is nothing to give up, and nothing happens.
        """
        for item in list(drawn or ()):
            if getattr(item, "kind", None) != "card":
                continue
            if getattr(item, "value", None) != Card.SMELLY_SOCKS:
                continue
            victims = [other for other in self._smelly_socks_pool(item)
                       if self.item_cell(other) is not None]
            if not victims:
                self._set_shop_message(
                    f"{self._item_name(item)} had no other card to give up")
                continue
            victim = random.choice(victims)
            self._to_deck(victim)
            self._set_shop_message(
                f"{self._item_name(item)}: {self._item_name(victim)} went back "
                f"into the deck")
        return drawn

    def _smelly_socks_pool(self, socks):
        """The cards a drawn Smelly Socks may send back to the deck.

        The hand this run drew (deck_drawn), less the socks itself — and the
        cards only: a part, a block or a tool drawn alongside it is not the
        "card" the socks takes. Anything drawn after the hand (a Lantern, an
        Eyeball) is not in deck_drawn, so the socks never eats what a card just
        gave the player. One entry per item, in draw order.
        """
        pool = []
        for item in getattr(self, "deck_drawn", ()):
            if item is socks or getattr(item, "kind", None) != "card":
                continue
            if item not in pool and self.owns_item(item):
                pool.append(item)
        return pool

    # --- Eyeball: picking the cards a draw takes ---------------------------

    def eyeball_cards(self):
        """The deck cards an Eyeball can draw right now.

        Drawn from the DRAWABLE deck (a FORGOTTEN card cannot be drawn at all,
        see drawable_deck_items) and only the cards: the action asks for a card,
        so a part, a block or a tool in the deck is not a choice it offers.
        """
        return [item for item in self.drawable_deck_items()
                if getattr(item, "kind", None) == "card"]

    def arm_deck_pick(self, action):
        """Arm an Eyeball: the deck overlay becomes a picker (the S key).

        User request: "pick a card from your deck to draw (1 energy)". The deck
        is shown in the deck overlay, so that is where the picking happens: this
        opens it and remembers the action, and _click_deck_pick draws whatever
        the player clicks. The action's magnitude is how many picks it grants,
        so a golem-folded Eyeball takes two cards.

        Nothing is spent here — not the action, not the energy: the whole use is
        paid for when the last card is actually drawn (see _finish_deck_pick),
        and closing the overlay keeps the card.
        """
        picks = max(1, int(getattr(action, "amount", 1) or 1))
        self.deck_pick_action = action
        self.deck_pick_left = picks
        self.deck_shown = True
        self._set_shop_message(
            f"{action.name}: click {picks} card{'' if picks == 1 else 's'} in "
            f"the deck to draw — Esc to keep the card for later")
        return True

    def deck_pick_armed(self):
        """True while an Eyeball pick is waiting for the player's click."""
        return getattr(self, "deck_pick_action", None) is not None

    def cancel_deck_pick(self, message=None):
        """Leave an Eyeball pick without drawing: the action is kept.

        A look is free: nothing has been spent yet (see arm_deck_pick), so the
        card goes back to being an ordinary action in the action area.
        """
        action = getattr(self, "deck_pick_action", None)
        self.deck_pick_action = None
        self.deck_pick_left = 0
        self.deck_shown = False
        if action is not None:
            self._set_shop_message(
                message or f"{action.name}: nothing drawn — the card is kept")
        return action

    def _click_deck_pick(self, pos):
        """Handle a click in the deck overlay while an Eyeball pick is armed.

        A click on one of the deck's cards draws it (see _draw_deck_card); a
        click on anything else says what is pickable and stays open; a click off
        the tiles cancels the pick, exactly as Esc does.
        """
        item = self.deck_item_at(pos)
        if item is None:
            self.cancel_deck_pick()
            return False
        if item not in self.eyeball_cards():
            self._set_shop_message(
                "Eyeball draws a CARD — click one of the cards in the deck "
                "(Esc keeps the card)")
            return False
        if not self._draw_deck_card(item):
            self._set_shop_message(
                "There is no free square to draw it onto — kept in the deck")
            return False
        self.deck_pick_left = max(0, self.deck_pick_left - 1)
        if self.deck_pick_left:
            plural = "" if self.deck_pick_left == 1 else "s"
            self._set_shop_message(
                f"Drew {self._item_name(item)} — {self.deck_pick_left} "
                f"pick{plural} left")
            return True
        self._finish_deck_pick(item)
        return True

    def _draw_deck_card(self, item):
        """Draw one CHOSEN card out of the deck onto the board.

        The card is already the player's — drawing it only gives it a board
        square, exactly as the run's draw does (see _on_item_gained). Returns
        False when it cannot be drawn (not in the deck, already drawn, or the
        board has no free square), leaving it where it was.

        The deck's own rules apply to the draw itself: a card drawn this way
        still counts as drawn, so Smelly Socks hands a handmate back (see
        _settle_smelly_socks).
        """
        if item is None or not self.owns_item(item):
            return False
        if self.item_cell(item) is not None:
            return False
        self._on_item_gained(item)
        if self.item_cell(item) is None:
            # No free square: the layout stashed it, so put it back in the deck
            # rather than leave it in limbo (it would never be drawn again).
            self._to_deck(item)
            return False
        self._settle_smelly_socks([item])
        return True

    def _finish_deck_pick(self, drawn):
        """The last pick is made: pay for the Eyeball and spend it.

        The whole use is charged here — the action's energy out of the run's
        budget (see Action.ENERGY) and the action itself (see _consume_action) —
        which is why arming a pick costs nothing.
        """
        action = getattr(self, "deck_pick_action", None)
        self.deck_pick_action = None
        self.deck_shown = False
        if action is None:
            return
        cost = Action.energy(getattr(action, "value", None))
        self.energy = max(0, self.energy - cost)
        self._consume_action(action)
        self._set_shop_message(
            f"{action.name} drew {self._item_name(drawn)} out of the deck")
        return True

    def _stays_out_of_the_deck(self, item):
        """True for the items that are always on the board, never dealt.

        The START and FINISH role blocks (a run can always be built) and Spirit
        tokens (live for the run they were made in). The four TOOLS are items like
        any other (user request: "shovel, flashlight, screwdriver, hammer all
        count as items, meaning they are part of the condition that only 4 items
        can be drawn"), so the draw can deal them and the ones it did not deal
        wait in the deck.
        """
        if isinstance(item, ScorerToken):
            return True
        return getattr(item, "scorer", None) in (Scorer.START, Scorer.FINISH)

    def _return_hand_to_deck(self, keep=None):
        """Put the hand back in the deck: everything but the role blocks and the tokens.

        The one rule for "the board holds a HAND, not the collection": the run
        that ends hands its hand back (see _cycle_deck), the Horseshoe throws it
        back mid-run (see _sweep_board_into_deck), and a brand-new game starts
        with everything it owns in the deck too, so its first hand is a real DRAW
        of DECK_DRAW_SIZE items rather than a layout of whatever happened to be
        standing on the board (user request: "make sure the player always draws 4
        items, besides the start and finish"). The START and FINISH blocks and
        Spirit tokens stay where they are: a run can always begin, and a token is
        live for its own run.

        ``keep`` names the one item that stays put whatever it is (the card being
        USED: a Horseshoe throws the hand back, not itself). Returns the items
        that were ON THE BOARD when it was called — the hand it emptied.
        """
        moved = []
        for item in list(self.owned_items()):
            if item is keep or self._stays_out_of_the_deck(item):
                continue
            # An item with no square is already waiting in the deck (or in the
            # stash the layout overflowed into); it is still put where it
            # belongs — the deck — but it was not one of the hand's items, so it
            # is not reported as one the caller took off the board.
            if self.item_cell(item) is not None:
                moved.append(item)
            self._to_deck(item)
        return moved

    def _sweep_board_into_deck(self, keep=None):
        """Take everything the player owns off the board and into the deck.

        Placed blocks come off first, through the same door erasing uses, so
        each block hands its state back to the item it was built from; then the
        hand goes back to the deck (see _return_hand_to_deck). The START and
        FINISH blocks stay where the player put them and Spirit tokens stay for
        the run they were made in, so a run can always begin.

        Two rules read this: the end of a committed run (see _cycle_deck) and
        the Horseshoe's discard (see Game._action_horseshoe), so "the board
        shows a hand" is one behaviour rather than two. ``keep`` is the item
        being used, which stays on its square. Returns the items it took off the
        board (see _return_hand_to_deck).
        """
        for block in list(self.grid.values()):
            if block.scorer in (Scorer.START, Scorer.FINISH):
                continue
            # The LEVEL's own blocks are not the player's: its props (walls,
            # bouncers, accelerators...) and its enemies stay what they are, and
            # the level that comes next rebuilds them anyway (see _begin_level).
            # Sweeping them here refunded a BlockItem for each one, so a level's
            # furniture turned up in the player's deck after every run.
            if (getattr(block, "is_level_prop", False)
                    or getattr(block, "is_enemy", False)):
                continue
            if keep is not None and getattr(block, "source_item", None) is keep:
                continue
            self._unplace_block(block)
            self.grid.pop((block.x, block.y), None)
        return self._return_hand_to_deck(keep)

    def _cycle_deck(self):
        """End of a committed run: everything goes back in the deck, then a hand.

        User request: "when the run ends, all items owned by the player (except
        the start and finish) are returned to the deck and 4 new random items are
        drawn". Placed blocks come off the board too (their items are what the
        deck holds), so each run is built from its own hand - but the START and
        FINISH blocks stay where the player put them and Spirit tokens stay for the
        run they were made in, so a run can always begin. A TOOL goes back in like
        everything else: the draw may deal it, and a run that does not draw one
        opens its structures next time (user request).
        """
        self._clear_toolbox_selection()
        # The finished run's marbles belong to the board that is coming apart;
        # the next run releases its own from the Start block it is built with.
        self.marbles = []
        self._sweep_board_into_deck()
        self.ensure_board_cells()
        self.draw_deck_hand()

    def deck_open(self):
        """True while the deck overlay is showing (see ui.draw_deck_overlay)."""
        return bool(getattr(self, "deck_shown", False))

    def toggle_deck(self):
        """Open or close the deck overlay."""
        self.deck_shown = not self.deck_open()
        if self.deck_open():
            # Opening the deck is a look, not an action: whatever was picked up
            # stays picked up, but the run does not pause on its own account.
            self._set_shop_message(
                f"Deck: {len(self.owned_items())} item(s), "
                f"{len(self.hand_items())} drawn")
        return self.deck_open()
