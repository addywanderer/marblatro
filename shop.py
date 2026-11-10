"""The Shop: the shelf of offers, the item packs, and what is held on it.

The shelf's stock and its held cells live here; the price the player actually
pays (inflation, coupons, the shop's discount) is Game's business.
"""

import random

import pygame

import rolling
from components import (
    RESOURCE_PACK_FACTOR,
    Action,
    Card,
    Component,
    Effect,
    Pack,
    Passive,
    Scorer,
    Shape,
    Structure,
    Tool,
    block_price_for,
    magnitude_precision,
    pack_price,
    resource_points_for,
    tool_pack_options,
)
from config import *
from items import (
    ActionItem,
    BlockItem,
    ItemPack,
    PassiveItem,
    ResourceOption,
    StructureItem,
    ToolItem,
    make_card_item,
    offer_key,
)
from rolling import *


class Shop:
    """The board's offers: what stands on it, and where.

    There is no shop PANEL, and since the level took the structures over and the
    per-run packs were removed (user request: "add structures as part of the
    level. remove the remaining shop items (packs generated each run)") there is
    no shelf dealing anything either: a refresh empties the shelf and the level
    being played lays its own structures out (see Shop.refresh and
    Game._place_level_structures). What is left here is the offer bookkeeping the
    rest of the game still reads -- where an offer stands, whether a cell holds
    one -- plus the buying and hoarding paths a save from before the change can
    still use.
    """
    def __init__(self, rect, game=None):
        # The logical grid only: no panel is drawn at these coordinates.
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
        """Clear the shelf: nothing is sold any more.

        Structures are part of the LEVEL now (components.Level places them, see
        Game._place_level_structures) and the packs that used to be generated
        every run are gone (user request: "add structures as part of the level.
        remove the remaining shop items (packs generated each run)"). So a
        refresh -- which happens once per run -- empties the shelf, and the level
        that run plays lays its own structures out afterwards (see _begin_level).
        """
        # The LEVEL's structures are not the shelf's to clear: they are scenery
        # it laid out on its own squares (see Game._place_level_structures), and
        # a reroll that wiped them took the run's structures off the board.
        self.items = [item for item in self.items
                      if getattr(item, "is_level_structure", False)]
        self.locked = []

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
        cell (the same rule refresh deals by): the packs take the pack row, every
        other offer (a structure) the offer row, and anything past those two rows
        is a Picky bonus slot, which fills the rows below both. An offer the panel
        has no cell left for is DROPPED: a save written under an older shelf can
        hold more offers than this layout has places to put them, and one that
        cannot be seen or clicked is not worth keeping in the shelf.

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
        """One shelf offer: a STRUCTURE, at the odds Structure.OFFER_WEIGHTS sets.

        Structures are what the shelf shows now (user request: "replace shop
        items with structures"), and they are FREE (user request: "make all
        structures free"): one lies on the board, wearing no padlock, until a
        tool opens it where it is (see Structure / Game._apply_tool). Pits are the
        plainest and most common, mirrors the rarest — the odds live with the
        structure data so there is one place to tune them.

        ``used`` is the set of structure values already on this shelf: they are
        left out of the draw, so a shelf of five slots shows all three kinds
        before it repeats one (and repeats only because there is nothing left to
        deal).
        """
        # A level deals its OWN structures (see components.Level), so each level
        # offers a different set to open; a game with no level (a bare test game)
        # may deal any of them.
        allowed = self._level_structures()
        pool = [value for value in Structure.ORDER
                if allowed is None or value in allowed]
        pool = [value for value in pool if used is None or value not in used]
        if not pool:
            pool = list(Structure.ORDER)
        weights = [Structure.weight(value) for value in pool]
        value = random.choices(pool, weights=weights, k=1)[0]
        if used is not None:
            used.add(value)
        return StructureItem(value, Structure.PRICES[value], col=col, row=row)

    def _level_structures(self):
        """The structures the level being played may deal (None = any of them).

        A level AUTHORED these (see components.Level.authored_structures), not
        just the four its run plans out: a bonus slot is a spare, and it may deal
        any kind the level knows — which is what makes the last level's shelf hold
        every structure in the game.
        """
        game = self.game
        level = game.current_level() if game is not None else None
        if level is None or not level.authored_structures:
            return None
        return set(level.authored_structures)

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

    def _roll_tool_option(self, used=None):
        """One option of a TOOL pack: a one-shot tool or a passive item.

        User request: "add an item, 'concrete' ... add an item, 'brick' ... add an
        item, 'match'". These are the items a TOOL pack deals (see
        components.tool_pack_options), so the level's structures can hand over
        something to use up: a brick to open a structure for free, a match to
        reveal one and draw for it, or a passive that simply pays. ``used`` keeps
        an option off the ones already dealt, exactly as every other pack does.
        """
        pool = [entry for entry in tool_pack_options()
                if entry not in (used or ())]
        if not pool:
            pool = list(tool_pack_options())
        kind, value = random.choice(pool)
        if kind == "passive":
            return PassiveItem(value, Passive.PRICES.get(value, 16))
        return ToolItem(value, Tool.PRICES.get(value, 12))

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
        if source == Pack.TOOL:
            return self._roll_tool_option(used)
        for _ in range(OFFER_DUPLICATE_TRIES):
            option = self._offer_of(source, 0, 0, parts_only=parts_only)
            key = offer_key(option)
            if key is None or key not in used:
                return option
        return option

    def offer_at_cell(self, cell):
        """The offer lying on a board square, or None (see Game.ensure_board_cells).

        Offers are ITEMS on the board now (user request: "make each shop option
        an item ... allow shop items to be selected and moved around"), so the
        square — not a panel cell — is where an offer is found.
        """
        if cell is None:
            return None
        cell = tuple(cell)
        for item in self.items:
            if getattr(item, "board_cell", None) == cell:
                return item
        return None

    def is_offer(self, item):
        """True when ``item`` is one of the shelf's offers."""
        return any(item is offer for offer in self.items)

    def item_at(self, pos):
        """The offer lying on the board square under a screen position, or None."""
        if self.game is None:
            return None
        return self.offer_at_cell(self.game.screen_to_cell(pos))
