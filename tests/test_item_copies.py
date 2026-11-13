"""Several copies of one item: two of a kind are two items, one existence each.

The player can own more than one of almost anything — the shop keeps selling a
component slot, a pack can deal the same piece again, Recognition duplicates a
block, Showman lifts the card limit and the Hoard/Portal/Key rules count copies.
Every one of those copies must be a real item of its own: its own board square,
its own selection switch, its own sale. A block and the inventory item it was
built from are the ONE pair that shares an existence, so whatever happens to one
(the block is sold, disassembled, sacrificed, destroyed) has to happen to the
other (user report: glitches with several copies of the same item).
"""

from tests.game_test_case import *  # noqa: F401,F403


class ItemCopyTests(GameTestCase):
    """Copies of one item: bought, duplicated, and paired blocks in groups."""

    def _buy_block(self, shape=main.Shape.RECT, scorer=main.Scorer.CHIPS_ADD):
        """Buy a plain block from the shelf; return the item the player owns."""
        self.game.toolbox.items.clear()
        self.game.toolbox.stash.clear()
        self.game.cash = 1000
        offer = main.BlockItem(0, 0, shape, main.Effect.NONE, scorer, 10, 30,
                               f"{main.Shape.name(shape)} Test")
        self.game.shop.items = [offer]
        self.game._buy_shop_item(offer)
        return next(i for i in self.game.toolbox.items
                    if getattr(i, "kind", None) == "block")


    def _place(self, item, gx, gy):
        """Pick ``item`` up and put it down on the given square."""
        self.game._toggle_item_selection(item)
        self.assertTrue(self.game._place_block_at(gx, gy), (gx, gy))
        return self.game.grid[(gx, gy)]


    # --- two copies are two items ---------------------------------------

    def test_buying_two_offers_of_a_kind_gives_two_items(self):
        # The shelf sells one tile at a time — buying it deletes that tile (see
        # Game._unlock_offer) — but a refresh can offer the same kind again, and
        # the second purchase is a second, independent item with a square and a
        # switch of its own.
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        first = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.shop.items = [first]
        self.game._buy_shop_item(first)
        second = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.shop.items = [second]
        self.game._buy_shop_item(second)

        copies = [item for item in self.game.toolbox.items
                  if item.kind == first.kind and item.value == first.value]
        self.assertEqual(len(copies), 2)
        self.assertIs(copies[0], first)
        self.assertIs(copies[1], second)
        self.assertNotEqual(self.game.item_cell(copies[0]),
                            self.game.item_cell(copies[1]))
        self.assertEqual(self.game.shop.items, [])

        # Each copy is its own switch: clicking one selects exactly it.
        self._click(self._grid_pos(*self.game.item_cell(copies[0])))
        self.assertTrue(self.game.is_item_selected(copies[0]))
        self.assertFalse(self.game.is_item_selected(copies[1]))

        # And each copy sells on its own.
        cash = self.game.cash
        self.game._sell_selected_item()
        self.assertGreater(self.game.cash, cash)
        self.assertIn(copies[1], self.game.toolbox.items)


    def test_one_object_added_twice_is_still_one_item(self):
        # The inventory holds items, not references (see Toolbox.add): adding
        # the very same object again leaves the inventory alone, so it cannot
        # stand on two squares or wear two switches.
        self.game.toolbox.items.clear()
        piece = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(piece)
        self.game.toolbox.add(piece)

        self.assertEqual(self.game.toolbox.items, [piece])
        self.game.ensure_board_cells()
        self.assertEqual(len([i for i in self.game.board_items() if i is piece]), 1)


    def test_a_purchase_keeps_the_offers_own_rolls(self):
        # What is bought is the offer itself, so the magnitude it was drawn with
        # is exactly what the player pays (see Game._unlock_offer).
        self.game.toolbox.items.clear()
        self.game.cash = 1000
        offer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=7)
        self.game.shop.items = [offer]

        self.game._buy_shop_item(offer)

        self.assertTrue(self.game.owns_item(offer))
        self.assertEqual(offer.amount, 7)
        self.assertEqual(offer.value, main.Scorer.MULT_ADD)


    def test_a_copy_still_carries_the_offers_own_rolls(self):
        # items.owned_copy makes a second, independent item with the same goods —
        # what a REWARD that duplicates an offer uses (see the packs).
        offer = main.Component.scorer_component(main.Scorer.MULT_ADD, amount=7)

        copy = main.owned_copy(offer)

        self.assertEqual(copy.amount, 7)
        self.assertEqual(copy.value, main.Scorer.MULT_ADD)
        self.assertIsNot(copy, offer)
        self.assertIsNone(getattr(copy, "board_cell", None))


    def test_one_offer_clicked_twice_is_one_purchase(self):
        # A double click lands twice before the shelf redraws. The offer is one
        # object, and an object is never owned twice (see Game.owns_item), so the
        # second click is not a second purchase — the player pays once and owns
        # one card, laid out on one square.
        self.game.cash = 1000
        card = main.CardItem(main.Card.GARDEN, 36)
        self.game.shop.items = [card]

        self.game._buy_shop_item(card)
        cash_after_one = self.game.cash
        self.game._buy_shop_item(card)

        self.assertEqual(self.game.cards, [card])
        self.assertEqual(self.game.cash, cash_after_one)


    # --- a placed block and its item are one existence ------------------

    def test_a_sold_placed_block_takes_its_item_with_it(self):
        # Death sells the block on the board. The item it was built from is the
        # same existence, so it leaves the inventory too — no ghost left behind
        # that could be fielded again.
        item = self._buy_block()
        self._place(item, 6, 6)
        block = self.game.grid[(6, 6)]
        self.game.cash = 500
        action = main.ActionItem(main.Action.DEATH, 60)

        self.assertTrue(self.game._action_death(action, block))

        self.assertNotIn((6, 6), self.game.grid)
        self.assertNotIn(item, self.game.toolbox.items)
        self.assertFalse(self.game.is_item_selected(item))
        self.assertIsNone(item.placed_cell)
        # Nothing was left to conjure a block from: erasing the square is a no-op
        # and the player owns no block at all.
        self.assertFalse(self.game._erase_block_at(6, 6))
        self.assertEqual([i for i in self.game.toolbox.items
                          if getattr(i, "kind", None) == "block"], [])


    def test_disassembling_a_placed_block_takes_its_item_with_it(self):
        item = self._buy_block()
        self._place(item, 6, 6)
        self.game.cash = 500
        self.game._toggle_item_selection(self.game.grid[(6, 6)])

        self.game._disassemble_block()

        self.assertNotIn((6, 6), self.game.grid)
        # The parts came back and the block item did not: one existence, and the
        # board cannot end up holding the block twice.
        self.assertNotIn(item, self.game.toolbox.items)
        self.assertIsNone(item.placed_cell)
        self.assertNotIn("block", [getattr(i, "kind", None)
                                   for i in self.game.toolbox.items])


    def test_a_sacrificed_block_takes_its_item_with_it(self):
        item = self._buy_block()
        self._place(item, 6, 6)
        block = self.game.grid[(6, 6)]
        action = main.ActionItem(main.Action.SPIRIT, 60)

        self.assertTrue(self.game._action_spirit(action, block))

        self.assertNotIn((6, 6), self.game.grid)
        self.assertNotIn(item, self.game.toolbox.items)
        self.assertIsNone(item.placed_cell)
        self.assertEqual(len(self.game.tokens), 1)


    def test_a_bomb_takes_its_item_with_it(self):
        # A bomb destroys itself after the run it was primed in; the item it was
        # built from goes with it, so the board cannot conjure a second bomb.
        item = self._buy_block()
        block = self._place(item, 6, 6)
        self.game.bomb_cells = [(6, 6)]

        self.game._detonate_bombs()

        self.assertNotIn((6, 6), self.game.grid)
        self.assertNotIn(item, self.game.toolbox.items)
        self.assertIsNone(item.placed_cell)


    def test_two_copies_of_a_block_are_two_blocks_on_the_board(self):
        # Two identical loose blocks: each is placed on its own square and keeps
        # its own item, so taking one up leaves the other alone.
        self.game.toolbox.items.clear()
        first = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                               main.Scorer.CHIPS_ADD, 10, 30, "Rect")
        second = main.owned_copy(first)
        self.game.toolbox.add(first)
        self.game.toolbox.add(second)

        self._place(first, 6, 6)
        self._place(second, 7, 6)
        self.assertEqual(sorted(self.game.grid), [(6, 6), (7, 6)])
        self.assertEqual(first.placed_cell, (6, 6))
        self.assertEqual(second.placed_cell, (7, 6))
        self.assertIs(self.game.grid[(7, 6)].source_item, second)

        self.game._erase_block_at(6, 6)

        self.assertEqual(sorted(self.game.grid), [(7, 6)])
        self.assertIsNone(first.placed_cell)
        self.assertEqual(second.placed_cell, (7, 6))
        self.assertIn(first, self.game.toolbox.items)
        self.assertIn(second, self.game.toolbox.items)


    def test_a_placed_items_square_stays_reserved_for_it(self):
        # The inventory spot of a placed block stays occupied by it (user
        # request), so a piece bought afterwards is laid out somewhere else —
        # otherwise taking the block up would drop it on top of that piece.
        item = self._buy_block()
        home = self.game.item_cell(item)
        self._place(item, 6, 6)

        self.game.toolbox.add(main.Component.effect_component(main.Effect.BOUNCY))
        piece = [i for i in self.game.toolbox.items
                 if i.kind == main.Component.EFFECT][0]
        self.assertNotEqual(self.game.item_cell(piece), home)

        self.game._erase_block_at(6, 6)

        self.assertEqual(self.game.item_cell(item), home)
        self.assertNotEqual(self.game.item_cell(piece), home)


    # --- a reserved square never swallows an item -----------------------

    def _tool(self):
        """A screwdriver of the player's own, standing on the board."""
        tool = main.ToolItem(main.Tool.SCREWDRIVER,
                             main.Tool.PRICES[main.Tool.SCREWDRIVER])
        self.game.toolbox.add(tool)
        self.game.ensure_board_cells()
        self.assertIsNotNone(self.game.item_cell(tool),
                             "the screwdriver got no square")
        return tool

    def test_an_item_on_a_placed_items_old_square_is_not_deleted(self):
        # User report: "when I selected the start block and a screwdriver at the
        # same time, and tried to place them into a different square, the
        # screwdriver was deleted." The square a placed block came from is only
        # RESERVED (nothing is drawn there), so an item standing on it must step
        # aside to a free square -- never be knocked into the deck, where the
        # player cannot see it at all.
        item = self._buy_block()
        home = self.game.item_cell(item)
        self._place(item, 6, 6)
        tool = self._tool()
        self.game.set_item_cell(tool, home)         # the screwdriver there now

        block = self.game.grid[(6, 6)]
        self.game.selection = [block, tool]
        self.game.selected_toolbox_item = block
        self.game._refresh_actor()
        self.assertTrue(self.game._place_block_at(7, 6))
        self.game.ensure_board_cells()

        self.assertTrue(self.game.owns_item(tool), "the screwdriver was deleted")
        self.assertIsNotNone(self.game.item_cell(tool),
                             "the screwdriver was knocked off the board")
        self.assertNotIn(tool, self.game.deck_items())
        # ...and it is somewhere a player can click, not under the new block.
        self.assertNotEqual(self.game.item_cell(tool), (7, 6))
        # The block it stood on kept the square it moved to.
        self.assertIn((7, 6), self.game.grid)

    def test_moving_an_item_onto_a_reserved_square_hops_it_aside(self):
        # The same reservation, met from the other side: the player moves a tool
        # onto the empty square a placed block came from. The square is free to
        # look at, so the move happens -- and the layout pass then gives the tool
        # another square instead of dropping it into the deck.
        item = self._buy_block()
        home = self.game.item_cell(item)
        self._place(item, 6, 6)
        tool = self._tool()

        self.assertTrue(self.game._move_item_to(tool, *home))

        self.assertTrue(self.game.owns_item(tool))
        cell = self.game.item_cell(tool)
        self.assertIsNotNone(cell)
        self.assertNotIn(tool, self.game.deck_items())
        self.assertNotEqual(cell, home)
        self.assertIn(tool, self.game.toolbox.items)

    def test_two_items_never_stand_on_one_square(self):
        # However an item ends up on a square another item claims, the layout
        # pass resolves it by seating the LATER one somewhere free: both stay
        # owned, both stay on the board, and no square answers for two items.
        item = self._buy_block()
        self._place(item, 6, 6)
        tool = self._tool()
        loose = main.Component.effect_component(main.Effect.BOUNCY)
        self.game.toolbox.add(loose)
        self.game.ensure_board_cells()
        tool_cell = self.game.item_cell(tool)
        self.game.set_item_cell(loose, tool_cell)

        self.game.ensure_board_cells()

        cells = [self.game.item_cell(tool), self.game.item_cell(loose)]
        self.assertNotIn(None, cells)
        self.assertEqual(len(set(cells)), 2)
        self.assertTrue(self.game.owns_item(tool))
        self.assertTrue(self.game.owns_item(loose))

    def test_a_square_holding_a_block_still_returns_the_item_to_the_deck(self):
        # What has NOT changed: a square a BLOCK actually stands on is taken.
        # An item found there (a level prop put down over it, say) has no square
        # to lie on, so it goes back into the deck where a draw can deal it.
        tool = self._tool()
        cell = self.game.item_cell(tool)
        self.game.grid[cell] = main.Block(cell[0], cell[1],
                                          scorer=main.Scorer.START,
                                          scorer_amount=0)

        self.game.ensure_board_cells()

        self.assertIsNone(self.game.item_cell(tool))
        self.assertIn(tool, self.game.deck_items())
        self.assertTrue(self.game.owns_item(tool))

    def test_the_first_free_cell_skips_a_placed_items_old_square(self):
        # Nothing may be SEATED on a reserved square either (see _seat_aside), so
        # the free-square search counts it as taken.
        item = self._buy_block()
        home = self.game.item_cell(item)
        self._place(item, 6, 6)

        self.assertNotEqual(self.game._first_free_cell(), home)
        self.assertNotEqual(self.game._first_free_cell(blocked={home}), home)


    def test_selling_a_placed_blocks_item_switches_the_block_off(self):
        # The block on the board and the item it was built from are one switch
        # (see _selection_key). Selling that item takes the block with it, so the
        # block's switch goes off too — a selection outliving the board would let
        # the player act on something that no longer exists.
        item = self._buy_block()
        self._place(item, 6, 6)
        block = self.game.grid[(6, 6)]
        self.game.selection = [block, item]
        self.game.selected_toolbox_item = item
        self.game.selected_shape = block.shape

        self.game._sell_selected_item()

        self.assertNotIn((6, 6), self.game.grid)
        self.assertNotIn(item, self.game.toolbox.items)
        self.assertEqual(self.game.selection, [])
        self.assertIsNone(self.game.selected_toolbox_item)


    # --- portals and key/lock pairs in groups ---------------------------

    def _portal_group(self, copies=3):
        """``copies`` portal blocks sharing one pairing number, on the board."""
        self.game.toolbox.items.clear()
        self.game.grid.clear()
        number = main.next_portal_number()
        blocks = []
        for x in range(copies):
            block = main.Block(6 + x, 6, shape=main.Shape.RECT,
                               scorer=main.Scorer.CHIPS_ADD,
                               scorer_amount=10,
                               effects=[main.Effect.PORTAL],
                               portal_number=number)
            block.triggers_left = block.trigger_limit
            self.game.grid[(6 + x, 6)] = block
            blocks.append(block)
        return blocks


    def test_portal_copies_share_the_lowest_trigger_count(self):
        blocks = self._portal_group(3)
        blocks[0].triggers_left = 4
        blocks[1].triggers_left = 2
        blocks[2].triggers_left = 9

        self.game._sync_portal_pair_triggers(blocks[2], self.game.board_blocks())

        # EVERY copy in the group agrees, not just the first one found.
        self.assertEqual([b.triggers_left for b in blocks], [2, 2, 2])


    def test_a_portal_upgrade_reaches_every_copy(self):
        blocks = self._portal_group(3)
        # Deja Vu raises the subject's own limit (and, for a placed block, its
        # triggers) before handing the gain to the pair (see _action_deja_vu).
        blocks[0].trigger_limit += 5
        blocks[0].triggers_left += 5

        self.game._add_portal_pair_triggers(blocks[0], 5)

        self.assertEqual([b.trigger_limit for b in blocks], [6, 6, 6])
        self.assertEqual([b.triggers_left for b in blocks], [6, 6, 6])


    def test_removing_a_portal_copy_removes_the_whole_group(self):
        # A lone portal is unusable, so the group goes as a group — every block
        # sharing the number, not just the first partner found.
        blocks = self._portal_group(3)

        self.game._delete_paired_portal(blocks[0].portal_number)

        self.assertEqual(self.game.grid, {})
        self.assertFalse(any(getattr(b, "portal_number", 0)
                             for b in self.game.toolbox.every_item()))


    def test_removing_a_key_copy_removes_the_whole_group(self):
        self.game.toolbox.items.clear()
        self.game.grid.clear()
        number = main.next_key_number()
        for x, shape in enumerate((main.Shape.KEY, main.Shape.LOCK,
                                   main.Shape.KEY)):
            self.game.grid[(6 + x, 6)] = main.Block(6 + x, 6, shape=shape,
                                                    key_number=number)

        self.game._delete_paired_key(number)

        self.assertEqual(self.game.grid, {})


    def test_a_portal_limit_upgrade_reaches_every_copy(self):
        blocks = self._portal_group(3)

        blocks[0].trigger_limit = 4
        self.game._sync_portal_pair_limits(blocks[0])

        self.assertEqual([b.trigger_limit for b in blocks], [4, 4, 4])


    # --- one existence is counted once ----------------------------------

    def test_placing_the_last_role_block_does_not_invent_a_spare(self):
        # A placed block and its item are the same Start/Finish role, so the
        # count must not double: a "spare" that does not exist would let the
        # player sell the only block a run can start from.
        item = next(i for i in self.game.toolbox.items
                    if getattr(i, "scorer", None) == main.Scorer.START)
        self.assertEqual(self.game._role_blocks_owned(main.Scorer.START), 1)

        self._place(item, 8, 8)
        block = self.game.grid[(8, 8)]

        self.assertEqual(self.game._role_blocks_owned(main.Scorer.START), 1)
        self.assertTrue(self.game._unsellable(block))
        self.assertTrue(self.game._unsellable(item))


    def test_a_placed_slippery_block_counts_once(self):
        # Skater pays per slippery block the player owns; the block on the board
        # and the item it was built from are one block (see
        # cards.owned_slippery_block_count).
        self.game.toolbox.items.clear()
        self.game.grid.clear()
        item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                              main.Scorer.CHIPS_ADD, 10, 30, "Slippery",
                              effects=[main.Effect.SLIPPERY])
        self.game.toolbox.add(item)
        self.assertEqual(main.cards.owned_slippery_block_count(self.game), 1)

        self._place(item, 6, 6)

        self.assertEqual(main.cards.owned_slippery_block_count(self.game), 1)


    def test_anointment_blesses_a_placed_block_once(self):
        # v2 Anointment blesses every block once. A placed block is not also its
        # own item, so it gets ONE effect, exactly like a loose block.
        action = main.ActionItem(main.Action.ANOINTMENT, 60, version=2)

        def bless(placed):
            self.game.toolbox.items.clear()
            self.game.grid.clear()
            item = main.BlockItem(0, 0, main.Shape.RECT, main.Effect.NONE,
                                  main.Scorer.CHIPS_ADD, 10, 30, "Plain")
            self.game.toolbox.add(item)
            if placed:
                self._place(item, 6, 6)
            with mock.patch.object(main.Game, "_random_new_effects",
                                   lambda game, target, count: [
                                       main.Effect.BOUNCY][:count]):
                self.assertTrue(self.game._action_anointment(action, None))
            return self.game.grid[(6, 6)] if placed else self.game.toolbox.items[0]

        def real_effects(block):
            return [e for e in block.effects if e != main.Effect.NONE]

        self.assertEqual(len(real_effects(bless(False))), 1)
        # Put the loose block away first: the second run starts from an empty
        # board, so only the placed block can be blessed.
        self.game.toolbox.items.clear()
        self.game.grid.clear()
        placed = bless(True)
        self.assertEqual(len(real_effects(placed)), 1)
