"""The Shop: the shelf of offers, the item packs, and what is held on it.

The shelf's stock and its held cells live here; the price the player actually
pays (inflation, coupons, the shop's discount) is Game's business.
"""

import random

import pygame

import components
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
import rolling
from rolling import *
from items import (
    ActionItem,
    BlockItem,
    ItemPack,
    ResourceOption,
    make_card_item,
    offer_key,
)




class Shop:
    """A grid-based shop: two random blocks plus two of each component type."""
    def __init__(self, rect, game=None):
        self.rect = pygame.Rect(rect)
        self.cols = rect[2] // GRID_SIZE
        self.rows = rect[3] // GRID_SIZE
        self.items = []
        # Extra offers added by the Picky scorer (one per banked slot). The
        # Game keeps the persistent count and sets this before refreshing.
        self.bonus_slots = 0
        # The cells the Hoard whole card is holding (see Game._toggle_shop_lock):
        # a held cell keeps the offer it holds through every reroll. A list, so
        # the ORDER the player pinned things in survives and the last one pinned
        # is the first to be released when the card's cap falls.
        self.locked = []
        # The Game this shop belongs to, so the card slots can tell which cards
        # the player already owns (and whether the Showman card lifts the
        # one-copy rule). None when a shop is built on its own (in a test):
        # no ownership, so every card is on offer.
        self.game = game
        self.refresh()

    def owned_cards(self):
        """The card values the card slots must not offer again.

        Empty while the player owns the Showman card: that card's whole point is
        owning more than one copy of the same card, so with it the shop may
        offer cards the player already has (and _buy_shop_item lets them be
        bought). See Game._has_card for what owning means for a card the run's
        trial has disabled.
        """
        game = self.game
        # A shop built during Game.reset_game runs before the card area and the
        # trial state exist; nothing is owned yet, so nothing is filtered.
        if (game is None or not hasattr(game, "cards")
                or not hasattr(game, "disabled_card")):
            return set()
        if game._has_card(Card.SHOWMAN):
            return set()
        return {card.value for card in game.cards}

    def owned_actions(self):
        """The actions the shop's action slots must not offer again.

        The same rule the card slots follow (see owned_cards): an action the
        player is already HOLDING is not offered — a second copy of an action
        they have in hand is a wasted slot — unless the Showman card lifts the
        one-copy rule, or the action area has room and they simply want
        another. Actions are one-use goods, so only what is in hand counts
        (there is no permanent ownership of an action); a shop built before the
        game has an action area filters nothing.
        """
        game = self.game
        if game is None or not hasattr(game, "actions"):
            return set()
        if game._has_card(Card.SHOWMAN):
            return set()
        return {action.value for action in game.actions}

    def refresh(self):
        """Reroll the shelf: SHOP_ITEM_SLOTS random offers and SHOP_PACK_SLOTS packs.

        The five item slots each hold ONE offer of a drawn kind — a
        shape/effect/scorer component, a ready-made block, a card or an action
        (see _random_offer) — so the shelf shows a mix rather than a fixed
        layout, and no two slots show the same thing. The kinds are drawn at
        their own odds rather than equally (see components.Pack.SHELF_WEIGHTS:
        a shelf offer is a card 23% of the time, an action 15%, a scorer 22%, a
        block 20%, an effect 12% and a shape 8%). The three pack slots hold
        ITEM PACKS (see components.Pack), each of a randomly drawn type AND
        size, which the player buys and then keeps part of (see _roll_pack).

        The offers the Hoard whole card is holding are put back afterwards, so a
        held cell is the one part of the shelf a reroll does not touch.
        """
        # Hoard's held offers, remembered by CELL: refresh rebuilds the whole
        # row, so the cell is the only thing that can carry an offer across one
        # (see slot_key). The held cells are clipped to what the player may hold
        # right now, so a Hoard that has been sold or cut by the Card cutter
        # releases what it was holding (see Game.shop_lock_cap). Only the HELD
        # cells are remembered: every other cell is about to be rerolled, and
        # carrying those over too would make the reroll a no-op.
        self.locked = self.locked[:self._lock_cap()]
        held_offers = {self.slot_key(item): item for item in self.items
                       if self.slot_key(item) in self.locked}
        self.items = []
        # SHOP_ITEM_SLOTS "any item" offers along the shelf's top row: each is
        # one component, block, card or action, drawn uniformly and kept apart
        # from the other slots (see _random_offer).
        used = set()
        for index in range(SHOP_ITEM_SLOTS):
            self.items.append(self._random_offer(col=1 + index, row=SHOP_ITEM_ROW,
                                                 used=used))
        # SHOP_PACK_SLOTS item packs beside the item offers, on the same row and
        # to their right (see SHOP_PACK_COL), with the fixed Board Unit tile
        # right of them: a pack is a randomly drawn TYPE at a randomly drawn
        # SIZE, and holding one opens it to choose from its options (see
        # _roll_pack).
        for index in range(SHOP_PACK_SLOTS):
            self.items.append(self._roll_pack(random.choice(Pack.ORDER),
                                              random.choice(Pack.SIZE_ORDER),
                                              col=SHOP_PACK_COL + index,
                                              row=SHOP_PACK_ROW))
        # COMMENTED OUT with the conditions: the two condition-component slots
        # and the two-scorers-plus-four-cards layout they sat in. The shelf is
        # now SHOP_ITEM_SLOTS mixed offers rather than a fixed grid of kinds, so
        # those slots are gone; the condition code stays here as history.
        #
        # shape_pool = [s for s in Shape.ORDER if s != Shape.RECT]
        # effect_pool = [e for e in Effect.ORDER if e != Effect.NONE]
        # scorer_pool = [s for s in Scorer.SHOP_ORDER if s != Scorer.NONE]
        # shape_weights = [component_weight(Component.SHAPE, s) for s in shape_pool]
        # effect_weights = [component_weight(Component.EFFECT, e) for e in effect_pool]
        # scorer_weights = [component_weight(Component.SCORER, s) for s in scorer_pool]
        # for shape in weighted_sample_without_replacement(shape_pool, shape_weights, 2):
        #     self.items.append(Component.shape_component(shape, col=col, row=1))
        # for effect in weighted_sample_without_replacement(effect_pool, effect_weights, 2):
        #     self.items.append(Component.effect_component(
        #         effect, magnitude=self._quake_effect(effect), col=col, row=1))
        # for scorer in weighted_sample_without_replacement(scorer_pool, scorer_weights, 3):
        #     self.items.append(self._scorer_offer(scorer, col, 1))
        # card_col = 1
        # for card in random_card_option_values(4, self.owned_cards()):
        #     self.items.append(make_card_item(card, col=card_col, row=3))
        # cond_weights = [component_weight(Component.CONDITION, c) for c in CONDITION_ORDER]
        # for condition in weighted_sample_without_replacement(CONDITION_ORDER,
        #                                                      cond_weights, 2):
        #     self.items.append(Component.condition_component(condition, col=cond_col, row=3))
        # action_pool = [a for a in Action.ORDER if a not in self.owned_actions()]
        # for action in random.sample(action_pool, SHOP_ACTION_SLOTS):
        #     self.items.append(ActionItem(action, Action.PRICES.get(action, 60),
        #                                  version=random_action_version(),
        #                                  col=action_col, row=3))
        # for _ in range(2):
        #     self.items.append(self._random_block_offer(block_col, 3))
        # Picky bonus slots: each banked slot adds one extra random offer to
        # the shop, of a kind drawn at the same odds a shelf slot's is (see
        # components.Pack.SHELF_WEIGHTS). The offers take the cells the panel
        # has room for below the standard rows (see _bonus_cells) and reappear
        # every time the shop refreshes; a slot past the panel's last cell
        # simply deals nothing, rather than an offer drawn outside the panel it
        # belongs to.
        for index, (col, row) in enumerate(self._bonus_cells()):
            if index >= self.bonus_slots:
                break
            self.items.append(self._random_offer(col=col, row=row))
        # Hoard: the held cells take their offers back, unchanged — the same
        # item at the same price, in the cell the player pinned it to. Every
        # other cell keeps what this reroll rolled for it.
        for index, item in enumerate(self.items):
            kept = held_offers.get(self.slot_key(item))
            if kept is not None:
                self.items[index] = kept

    def _bonus_cells(self):
        """The cells an offer may take past the two standard rows, in order.

        Picky's extra offers fill them left to right, row by row (see refresh),
        and they stop at the panel's own edges: an offer in a cell the panel does
        not have — past its bottom row, or in the column past its right edge —
        could be neither drawn nor clicked, so a shelf simply holds fewer.
        """
        return [(col, row) for row in range(SHOP_BONUS_ROW, self.rows)
                for col in range(1, self.cols)]

    def reseat(self):
        """Seat every offer in the cell THIS layout gives it, and say where.

        The shelf's cells belong to the layout, not to a save, and the layout can
        change under a save's feet: offers restored verbatim can land in cells
        this layout does not have — over the cash header, or off the panel's
        right edge. The offer's kind and its place in the row are what decide its
        cell (the same rule refresh deals by): the packs take the pack row beside
        the fixed Board Unit tile, every other offer the "any item" row, and
        anything past those two rows is a Picky bonus slot, which fills the rows
        below both. An offer the panel has no cell left for is DROPPED: a save
        written under an older shelf can hold more offers than this layout has
        places to put them, and one that cannot be seen or clicked is not worth
        keeping in the shelf.

        Returns {(old col, old row): (new col, new row)}, so a caller restoring
        more than the offers — the Hoard card's held cells — can move those along
        with the offers they hold.
        """
        moved = {}
        seated = []
        bonus = iter(self._bonus_cells())
        item_col = 1
        pack_col = SHOP_PACK_COL
        for item in self.items:
            is_pack = getattr(item, "kind", None) == "pack"
            if is_pack and pack_col < SHOP_PACK_COL + SHOP_PACK_SLOTS:
                cell = (pack_col, SHOP_PACK_ROW)
                pack_col += 1
            elif not is_pack and item_col <= SHOP_ITEM_SLOTS:
                cell = (item_col, SHOP_ITEM_ROW)
                item_col += 1
            else:
                cell = next(bonus, None)
                if cell is None:
                    continue
            moved[(item.col, item.row)] = cell
            item.col, item.row = cell
            seated.append(item)
        self.items = seated
        return moved

    @staticmethod
    def slot_key(item):
        """The CELL a shop offer sits in — what the Hoard card holds.

        An offer has no identity to carry across a reroll (refresh rebuilds the
        row from scratch), but its cell does, and the row's layout is fixed: a
        cell always sells the same KIND of thing (the card row always holds
        cards, the component row components), so a held cell keeps holding the
        same sort of offer. This is also what a save stores (see
        save_system._save_data).
        """
        return (item.col, item.row)

    def _lock_cap(self):
        """How many offers may be held right now (see Game.shop_lock_cap).

        A shop built on its own (in a test) has no game to ask, so it holds
        nothing.
        """
        if self.game is None or not hasattr(self.game, "cards"):
            return 0
        return self.game.shop_lock_cap()

    def _quake_factor(self):
        """The factor the shop's magnitudes are rolled at (see Card.EARTHQUAKE).

        A shop built on its own (in a test) has no game to ask, so it rolls at
        the plain average like every other magnitude.
        """
        if self.game is None or not hasattr(self.game, "cards"):
            return 1.0
        if self.game._has_card(Card.EARTHQUAKE):
            return EARTHQUAKE_MAGNITUDE_FACTOR
        return 1.0

    def _quake(self, value, average):
        """One magnitude this shop rolls, raised by the Earthquake whole card.

        Earthquake makes every effect strength and scorer amount the SHOP offers
        10% higher (see EARTHQUAKE_MAGNITUDE_FACTOR). The roll is scaled HERE,
        once, as the offer is built — so a component or block bought while the
        card is owned keeps the raised number for good, and keeps it even if
        the card is later sold. The value is re-rounded to the precision a
        magnitude of its size means, the same rounding the roll itself used, so
        the raised number is as tidy as the rolled one.
        """
        factor = self._quake_factor()
        if factor == 1.0:
            return value
        return round(value * factor, magnitude_precision(average))

    def _quake_scorer(self, scorer):
        """A shop roll of a scorer amount, raised by Earthquake."""
        return self._quake(roll_scorer_amount(scorer),
                           Scorer.DEFAULT_AMOUNT.get(scorer, 0))

    def _quake_effect(self, effect):
        """A shop roll of a scalable effect's strength, raised by Earthquake."""
        return self._quake(roll_effect_magnitude(effect),
                           Effect.MAGNITUDE.get(effect, 0))

    def _quake_effect_amounts(self, effects):
        """A shop roll of a block's {effect: magnitude} map, raised by Earthquake."""
        return {effect: self._quake(value, Effect.MAGNITUDE.get(effect, 0))
                for effect, value in roll_effect_amounts(effects).items()}

    def _scorer_offer(self, scorer, col, row):
        """The shop offer for a drawn scorer.

        An ordinary scorer is sold as a scorer component, to be assembled onto
        a block the player builds. The Start and Finish scorers are run ROLES,
        so they are sold as ready-made blocks instead: a plain Rect with no
        effects, priced by block_price_for like any other block. A role is
        bought whole, never assembled onto someone else's physics.
        """
        if scorer in (Scorer.START, Scorer.FINISH):
            amount = Scorer.DEFAULT_AMOUNT.get(scorer, 0)
            shape, effects = role_block_parts(scorer, Shape.RECT, [])
            name = role_block_name(scorer, shape)
            return BlockItem(col, row, shape, Effect.NONE, scorer, amount,
                             block_price_for(shape, effects, scorer), name,
                             effects=effects)
        amount = self._quake_scorer(scorer)
        return Component.scorer_component(scorer, amount=amount, col=col, row=row)

    def _random_block_offer(self, col, row):
        """A ready-made block, rolled the way the shelf rolls one.

        Every part is drawn by RARITY (see component_weight), so a block's own
        chance is the product of its parts' weights — a Splitter block is far
        rarer than a plain wall. A block has no effect 1/4 of the time
        (rolling.random_effect_count), and otherwise 1, 2, 3 ... effects on the
        geometric schedule. Any shape or scorer may turn up (a plain Rect block
        with no scorer is a legitimately useful wall) except that a block built
        around a run ROLE is always a plain Rect (see role_block_parts). The
        magnitudes are rolled here, once, exactly as a component's are, so
        Earthquake raises them (see _quake_scorer / _quake_effect_amounts).

        The ONE roller for a random block: the shelf's offers, a Picky bonus
        slot and a block pack all deal the same blocks (see _random_offer and
        _roll_pack), so they can never drift apart.
        """
        shape_weights = [component_weight(Component.SHAPE, s) for s in Shape.ORDER]
        scorer_weights = [component_weight(Component.SCORER, s)
                          for s in Scorer.SHOP_ORDER]
        shape = random.choices(Shape.ORDER, weights=shape_weights, k=1)[0]
        effects = random.sample(Effect.REAL_ORDER, random_effect_count())
        scorer = random.choices(Scorer.SHOP_ORDER, weights=scorer_weights, k=1)[0]
        shape, effects = role_block_parts(scorer, shape, effects)
        name = role_block_name(scorer, shape)
        return BlockItem(col, row, shape, Effect.NONE, scorer,
                         self._quake_scorer(scorer),
                         block_price_for(shape, effects, scorer), name,
                         effects=effects,
                         effect_amounts=self._quake_effect_amounts(effects))

    def _random_offer(self, col, row, used=None):
        """One shop offer, of a kind drawn at that kind's own odds.

        ``used`` is the set of offers already on this shelf (or, for a random
        pack, already in that pack), as (kind, value) keys: an offer that is
        already there is re-rolled so two slots never sell the same thing. A
        pool too small to fill every slot with something new (a player who owns
        most of the cards) simply repeats after OFFER_DUPLICATE_TRIES, so a
        slot is never left empty.
        """
        for _ in range(OFFER_DUPLICATE_TRIES if used is not None else 1):
            offer = self._roll_random_offer(col, row)
            key = offer_key(offer)
            if used is None or key not in used:
                if used is not None:
                    used.add(key)
                return offer
        return offer

    def _roll_random_offer(self, col, row):
        """One random offer, of a kind drawn at that kind's own odds.

        The kinds do not come up equally often: a shelf slot is a CARD offer
        23% of the time and a shape offer only 8% of the time (see
        components.Pack.SHELF_WEIGHTS, the one place the odds are set), so the
        shop keeps the mix it has rather than whatever six equally likely kinds
        would give. The weights are read per kind, so they follow the kind list:
        a shelf restricted to a subset of kinds still draws only from it, at
        those kinds' odds relative to each other.
        """
        weights = [Pack.shelf_weight(t) for t in SHELF_OFFER_TYPES]
        return self._offer_of(random.choices(SHELF_OFFER_TYPES, weights=weights,
                                             k=1)[0], col, row)

    def _offer_of(self, source, col, row, parts_only=False):
        """An offer of one PACK TYPE's goods, at this shop's rolls and prices.

        ``source`` is a components.Pack type (Pack.SHAPE, Pack.BLOCK, ...), NOT
        one of the Component kind strings: the one roller behind a shelf slot,
        a Picky bonus slot and every pack option, so a shape pack, a part pack
        and a random pack all deal exactly the shape a shelf slot would deal
        (see _random_offer and _roll_pack_option). A resource option is not a
        shelf item — points are not an item — so it is only ever dealt inside a
        pack (see _roll_resource_option).

        ``parts_only`` asks for a PART rather than whatever the source deals:
        only the scorer branch has anything whole in it (a run role, see
        _scorer_offer), so a part pack passes it to rule the roles out.
        """
        if source == Pack.SHAPE:
            value = random.choice([s for s in Shape.ORDER if s != Shape.RECT])
            return Component.shape_component(value, col=col, row=row)
        if source == Pack.EFFECT:
            value = random.choice([e for e in Effect.ORDER if e != Effect.NONE])
            return Component.effect_component(value,
                                              magnitude=self._quake_effect(value),
                                              col=col, row=row)
        if source == Pack.SCORER:
            pool = [s for s in Scorer.SHOP_ORDER if s != Scorer.NONE]
            if parts_only:
                # The run roles are not parts: they are bought as ready-made
                # blocks and cannot be assembled onto another block's physics
                # (see _scorer_offer), so a part pack never deals one while a
                # scorer pack still may.
                pool = [s for s in pool
                        if s not in (Scorer.START, Scorer.FINISH)]
            return self._scorer_offer(random.choice(pool), col, row)
        if source == Pack.BLOCK:
            return self._random_block_offer(col, row)
        if source == Pack.CARD:
            value = rolling.random_card_option_value(self.owned_cards())
            if value is None:
                value = rolling.random_card_option_value()
            return make_card_item(value, col=col, row=row)
        if source == Pack.RESOURCE:
            return self._roll_resource_option()
        # An action the player is already holding is left out (see
        # owned_actions) — an offer that would be refused is a wasted slot —
        # and the whole catalogue is the fallback when the pool comes up short.
        held = self.owned_actions()
        pool = [a for a in Action.ORDER if a not in held]
        if not pool:
            pool = list(Action.ORDER)
        value = random.choice(pool)
        return ActionItem(value, Action.PRICES.get(value, 60),
                          version=rolling.random_action_version(), col=col, row=row)

    def _roll_resource_option(self, used=None):
        """One resource pack option: points of a random resource scorer.

        The option is worth RESOURCE_PACK_FACTOR times what a trigger of that
        scorer banks, and the scorer's own magnitude is rolled here as it would
        be for a component (so Earthquake raises it — see _quake_scorer), which
        is what the player's "randomized just like their scorer" asks for: a
        Picky option at the default magnitude is worth 2 x 0.5 = one option
        point, and a well-rolled one is worth more.

        ``used`` is what the pack has dealt so far: a scorer the pack has not
        shown YET is preferred, so a resource pack is a real choice between the
        four resources (a giga pack of six shows all four before it repeats
        one) rather than four draws that can all land on Rubbish.
        """
        dealt = {key[1] for key in (used or ())
                 if isinstance(key, tuple) and key[:1] == ("resource",)}
        pool = [s for s in Scorer.RESOURCE_RATE if s not in dealt]
        if not pool:
            pool = list(Scorer.RESOURCE_RATE)
        option = None
        for _ in range(OFFER_DUPLICATE_TRIES):
            scorer = random.choice(pool)
            amount = self._quake_scorer(scorer)
            points = RESOURCE_PACK_FACTOR * resource_points_for(scorer, amount)
            option = ResourceOption(scorer, amount, points)
            if used is None or offer_key(option) not in used:
                return option
        return option

    def _roll_pack(self, pack_type, size, col=0, row=0):
        """Deal a pack: its size's options of its type (see _roll_pack_option)."""
        used = set()
        options = []
        for _ in range(Pack.options(size)):
            option = self._roll_pack_option(pack_type, used)
            if option is None:
                break
            options.append(option)
            key = offer_key(option)
            if key is not None:
                used.add(key)
        return ItemPack(pack_type, size, options, pack_price(pack_type, size),
                        col=col, row=row)

    def _roll_pack_option(self, pack_type, used):
        """One option of a pack: a PART or RANDOM pack deals a mixed bundle.

        A part pack deals any component part and a random pack deals anything
        any other pack might (see components.Pack.PART_SOURCES /
        RANDOM_SOURCES), while every other type deals its own goods; all of
        them go through the same roller a shelf offer does, so a card pack's
        cards obey the shop's ownership rule and a block pack's blocks are the
        shelf's own blocks. ``used`` keeps an option off the ones already dealt.
        """
        if pack_type == Pack.PART:
            source = random.choice(Pack.PART_SOURCES)
            # A part pack deals PARTS: its scorer draw is a piece, never a run
            # role (see _offer_of).
            parts_only = source == Pack.SCORER
        elif pack_type == Pack.RANDOM:
            source = random.choice(Pack.RANDOM_SOURCES)
            parts_only = False
        else:
            source = pack_type
            parts_only = False
        if source == Pack.RESOURCE:
            return self._roll_resource_option(used)
        for _ in range(OFFER_DUPLICATE_TRIES):
            option = self._offer_of(source, 0, 0, parts_only=parts_only)
            key = offer_key(option)
            if key is None or key not in used:
                return option
        return option

    def item_at(self, pos):
        """Return the shop item occupying a screen position, or None."""
        if not self.rect.collidepoint(pos):
            return None
        gx = (pos[0] - self.rect.x) // GRID_SIZE
        gy = (pos[1] - self.rect.y) // GRID_SIZE
        for item in self.items:
            if item.col == gx and item.row == gy:
                return item
        return None
