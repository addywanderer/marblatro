"""The player's portable items: every one of them stands on a board square.

There is no inventory panel any more (user request: "remove the card, action, and
inventory ui. move them all to the board"). The board IS the inventory: a block
waiting to be built (BlockItem) and a component piece are items lying on board
squares, drawn there and clicked there, exactly like the cards and actions are.

This class is the inventory as the rest of the game reads it — the list of
portable items and the handful of operations the placement, selection and sale
code uses. It owns no layout of its own: which SQUARE an item stands on belongs
to the game (see Game.ensure_board_cells), so an item can be picked up, moved and
put down anywhere on the board without the inventory knowing.
"""


class Toolbox:
    """The portable items the player owns: block parts and components.

    ``items`` holds them in the order the player got them, and ``stash`` is the
    overflow that could not be given a square (the board can be full). Both are
    plain lists — the game's board layout reads them, it never stores its own
    copy — so nothing has to be kept in step with anything else.
    """
    def __init__(self, game=None):
        self.game = game
        # The portable items, in the order they joined the inventory.
        self.items = []
        # Items with no square free yet (a full board). They are owned and can be
        # sold, and take a square as soon as one opens up (see
        # Game.ensure_board_cells).
        self.stash = []
        # Called with an item that has just left the inventory, so the game can
        # take that item's block off the board with it (see Game._drop_placed_copy).
        self.on_remove = None

    def every_item(self):
        """Every portable item the player owns."""
        return list(self.items) + list(self.stash)

    def contains(self, item):
        """True when the player owns this exact item."""
        return any(item is owned for owned in self.every_item())

    def add(self, item):
        """Take an item into the inventory; it can never be refused.

        The item joins the list at once and takes a board square as soon as one
        is free (see Game._on_item_gained); a full board leaves it waiting in
        ``stash``, which never costs the player the item.

        The inventory holds ITEMS, never two references to one item: an object
        that is already the player's is left alone, because a second reference
        would share that item's board square and its selection switch, and
        selling or assembling one reference would silently take the other with
        it (user report: glitches with several copies of the same item). Two
        copies are two items — see items.owned_copy.
        """
        if self.contains(item):
            return True
        self.items.append(item)
        if self.game is not None:
            self.game._on_item_gained(item)
        return True

    def remove(self, item, refill=True):
        """Take an item out of the inventory; returns True when the player owned it.

        Removing by IDENTITY (``is``) matters: two identical components or blocks
        are different items, and only the one that was clicked may leave.
        ``on_remove`` runs last, so the game can take the item's block off the
        board with it (a placed block shares its item's existence — see
        Game._drop_placed_copy).
        """
        for bucket in (self.items, self.stash):
            for owned in list(bucket):
                if owned is item:
                    bucket.remove(owned)
                    if self.on_remove is not None:
                        self.on_remove(item)
                    return True
        return False

    def capacity(self):
        """How many items the board can show: one per board square."""
        if self.game is None:
            return len(self.items)
        return self.game.board_area()
