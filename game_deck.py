"""The player's DECK: every item they own, and the hand of items drawn from it.

The deck is what a run is built from (user request: "create a deck ... when a
new run begins, draw 4 random cards from the deck onto the board, along with the
shop's offers"). It holds EVERY item the player owns — blocks waiting to be
built, component pieces, cards, actions — while the board shows only the HAND:
the DECK_DRAW_SIZE items currently drawn from it. An item is "in the deck" when
it has no board square (see Game.item_cell); drawing it gives it one, and
returning it takes that square away.

Two kinds of item never leave the board: the START and FINISH blocks, which stay
where the player put them so a run can always begin, and Spirit tokens, which are
live for the run they were made in.
"""

import random

import ui
from components import Component, Scorer
from config import *
from blocks import Block
from items import ScorerToken


class DeckMixin:
    """The deck: which items are drawn into the hand, and cycling them."""


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
        """The items the deck overlay lists, in reading order.

        The whole collection, grouped by kind — the block parts first (they are
        what a hand is built from), then the cards and the actions — so the
        overlay reads like the deck it is rather than like the order things were
        bought in.
        """
        def rank(item):
            kind = getattr(item, "kind", None)
            if isinstance(item, Block) or kind == "block":
                return 0
            if kind in (Component.SHAPE, Component.EFFECT, Component.SCORER):
                return 1
            if kind == "card":
                return 2
            if kind == "action":
                return 3
            return 4
        return sorted(self.owned_items(),
                      key=lambda item: (rank(item),
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
        from the whole deck; fewer items simply deal a smaller hand. Returns the
        items drawn.
        """
        self.ensure_board_cells()
        deck = self.deck_items()
        drawn = random.sample(deck, min(DECK_DRAW_SIZE, len(deck)))
        for item in drawn:
            claimed = self.ensure_board_cells()
            cell = self._free_board_cell(claimed)
            if cell is None:
                # No square left on the board: the item stays in the deck, and
                # the next run's draw can deal it.
                continue
            self.set_item_cell(item, cell)
        self.ensure_board_cells()
        return drawn

    def _cycle_deck(self):
        """End of a committed run: everything goes back in the deck, then a hand.

        User request: "when the run ends, all items owned by the player (except
        the start and finish) are returned to the deck and 4 new random items are
        drawn". Placed blocks come off the board too (their items are what the
        deck holds), so each run is built from its own hand — but the START and
        FINISH blocks stay where the player put them, and Spirit tokens stay for
        the run they were made in, so a run can always begin.
        """
        self._clear_toolbox_selection()
        # The finished run's marbles belong to the board that is coming apart;
        # the next run releases its own from the Start block it is built with.
        self.marbles = []
        # Placed blocks come off first, through the same door erasing uses, so
        # each block hands its state back to the item it was built from.
        for block in list(self.grid.values()):
            if block.scorer in (Scorer.START, Scorer.FINISH):
                continue
            self._unplace_block(block)
            self.grid.pop((block.x, block.y), None)
        for item in list(self.owned_items()):
            if isinstance(item, ScorerToken):
                continue
            if getattr(item, "scorer", None) in (Scorer.START, Scorer.FINISH):
                continue
            self._to_deck(item)
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
