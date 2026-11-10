"""The shop's counter: what a purchase costs, and what a pack hands over."""

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
    Passive,
    Rarity,
    Scorer,
    Shape,
    Structure,
    Tool,
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


class StoreMixin:
    """The shop's counter: what a purchase costs, and what a pack hands
    over."""


    def _record_component_purchases(self, item):
        """Count a purchase toward each component's permanent price.

        Buying a component directly counts that one component; buying a block
        counts every component it is made of (its shape, each effect, and its
        scorer), so buying blocks also pushes up the component prices.
        """
        if getattr(item, "kind", None) == "block":
            keys = [(Component.SHAPE, item.shape)]
            keys += [(Component.EFFECT, e) for e in item.effects]
            keys.append((Component.SCORER, item.scorer))
        elif getattr(item, "kind", None) in ("pack", "resource"):
            # A pack is not a component and its price does not climb, so buying
            # one counts toward nothing (see _buy_price); a resource option is
            # not bought at all.
            return
        else:
            keys = [(item.kind, item.value)]
        for key in keys:
            self.component_purchases[key] = self.component_purchases.get(key, 0) + 1

    def _inflation_factor(self):
        """The inflation trial's price multiplier: 1.5 while active, else 1.0.

        The inflation trial makes everything money-related cost 50% more while
        it is the current trial (it is chosen before the run, so the shop you
        buy from under it is inflated). Gated by trials_enabled so a random
        trial never leaks into non-trial tests.
        """
        if self.trials_enabled and self.current_trial == Trial.INFLATION:
            return 1.5
        return 1.0

    def _inflated(self, amount):
        """``amount`` rounded up to the nearest dollar under the inflation trial."""
        return int(amount * self._inflation_factor() + 0.5)

    def _buy_price(self, item):
        """Effective buy price for a shop item.

        A component's price rises permanently with every purchase of it — both
        direct buys and copies bought inside blocks. The increase is
        diminishing (a square-root curve), so each additional copy adds a
        smaller increment and prices climb more and more slowly. Rarity is
        unaffected: shop generation uses only the base COMPONENT_PRICES. The
        inflation trial raises the final price 50% on top. The price is only
        ever SHOWN on hover (see ui.info_layout), but it is always this number.
        """
        if getattr(item, "kind", None) in ("block", "card", "action", "pack"):
            return self._inflated(self._shop_discount(item.price))
        bought = self.component_purchases.get((item.kind, item.value), 0)
        base = self._shop_discount(item.price)
        return self._inflated(int(base * (1 + DUPLICATE_PRICE_INCREMENT * math.sqrt(bought))))

    def _shop_discount(self, amount):
        """A shop price after the Coupon card's discount.

        Coupon takes 25% off every shop OPTION — the components, blocks, cards
        and actions on offer. The inflation trial then applies on top (see
        _inflated).
        """
        if not self._has_card(Card.COUPON):
            return amount
        return int(amount * COUPON_PRICE_FACTOR)

    def _consume_shop_offer(self, item, keep_cell=False):
        """Take a bought offer off the shelf — it was never the player's stock.

        Every purchase removes its offer (user request: "buying anything in the
        shop unlocks it and deletes the locked shop item"): the shelf's slot
        stands empty until the next refresh, and no locked copy of what the player
        just bought is left lying on the board.

        ``keep_cell`` hands the offer over AS ITSELF — the bought card, action,
        component or block keeps the square it was lying on, so the padlock comes
        off exactly where the player was looking instead of the purchase appearing
        somewhere else (see _unlock_offer).
        """
        if item in self.shop.items:
            self.shop.items.remove(item)
        if not keep_cell and hasattr(item, "board_cell"):
            # The square it was lying on is free again: it was never owned.
            item.board_cell = None
        # A bought offer cannot be held: its cell stands empty until the next
        # refresh, so the hold it had (if any) is released with it.
        slot = self.shop.slot_key(item)
        if slot in self.shop.locked:
            self.shop.locked.remove(slot)

    def _buy_shop_item(self, item):
        if self.owns_item(item):
            # The same offer, clicked twice before the shelf redrew: the first
            # click already bought it. One object is never owned twice (see
            # Game.owns_item), so the second click is not a purchase.
            return
        price = self._buy_price(item)
        if self.cash < price:
            self._set_shop_message(f"Need ${price} for {item.name}")
            return
        # A STRUCTURE is not for sale (user request: "make all structures free"):
        # the shelf hands it over as scenery and a tool opens it where it lies
        # (see _apply_tool), so a right-click has nothing to do.
        if getattr(item, "kind", None) == "structure":
            self._set_shop_message(
                f"{self._item_name(item)} is free — arm a tool on it and press S")
            return
        # A PACK is an ITEM now (user request: "make packs a type of item that
        # open when the player selects one and presses 's'"): the purchase hands
        # over the pack itself, unlocked where it lies, and the player opens it
        # when they are ready (see _open_owned_pack). Buying one also reveals its
        # TYPE in the collection (its size is not part of the codex entry).
        if getattr(item, "kind", None) == "pack":
            self._discover_pack(item.pack_type)
            self._unlock_offer(item)
            self.cash -= price
            self._set_shop_message(f"Bought {item.name} — press S to open it")
            sounds.play_coin()
            return
        # The ERR 404 card is a joke: it never joins the card area itself —
        # buying it grants a random card instead.
        if getattr(item, "kind", None) == "card" and item.value == Card.ERR_404:
            # The joke card never joins the area itself: it grants a random card
            # instead, drawn from the cards the area can actually hold (Essence
            # and its missing slot included, see _card_capacity_for).
            pool = [v for v in rolling.prebuilt_card_pool()
                    if v != Card.ERR_404
                    and len(self.cards) < self._card_capacity_for(v)]
            if not pool:
                self._set_shop_message(f"You can only hold {self.max_cards} cards")
                return
            value = random.choice(pool)
            # Duplicates are blocked unless the player owns the Showman card.
            if self._owns_card(value) and not self._has_card(Card.SHOWMAN):
                self._set_shop_message("Already own this card")
                return
            # ERR 404 grants a different card, so it cannot be unlocked in place
            # itself; the card it pays out takes the tile's square instead.
            home = self.item_cell(item)
            granted = make_card_item(value)
            self._consume_shop_offer(item)
            self._adopt_card(granted)
            if home is not None and self.item_at_cell(home) is None:
                self.set_item_cell(granted, home)
            self.cash -= price
            self._discover_owned_card(value)
            self._set_shop_message(f"Bought card: {Card.name(value)}")
            sounds.play_coin()
            return
        # A card goes to the card area above the toolbox (max MAX_CARDS, one
        # fewer while Essence is owned), not the toolbox, and doesn't drive
        # component prices.
        if getattr(item, "kind", None) == "card":
            if len(self.cards) >= self._card_capacity_for(item.value):
                self._set_shop_message(f"You can only hold {self.max_cards} cards")
                return
            # Duplicates are blocked unless the player owns the Showman card.
            if self._owns_card(item.value) and not self._has_card(Card.SHOWMAN):
                self._set_shop_message("Already own this card")
                return
            # The card is unlocked ON THE SPOT: it leaves the shelf (it was never
            # the player's stock) and takes the square the locked offer was lying
            # on, so the player can use it during this run (user request: "when
            # an item in the shop is bought, unlock that item on the spot").
            self._unlock_offer(item)
            self.cash -= price
            self._discover_owned_card(item.value)
            self._set_shop_message(f"Bought card: {item.name}")
            sounds.play_coin()
            return
        # An action goes to the action area above the toolbox (max
        # self.max_actions, which Foresight can raise) and doesn't drive
        # component prices.
        if getattr(item, "kind", None) == "action":
            if len(self.actions) >= self.max_actions:
                self._set_shop_message(
                    f"You can only hold {self.max_actions} actions")
                return
            self._unlock_offer(item)
            self.cash -= price
            self._discover_action(item.value)
            self._set_shop_message(f"Bought action: {self._item_name(item)}")
            sounds.play_coin()
            return
        # A portal block is bought as a pair: two identical blocks that share a
        # fresh pairing number (they teleport marbles between each other). The
        # offer itself is the first half, unlocked where it lies; the second is
        # made beside it.
        if getattr(item, "kind", None) == "block" and item.has_effect(Effect.PORTAL):
            number = next_portal_number()
            self._unlock_offer(item)
            item.portal_number = number
            self._unlock_purchase(BlockItem(
                0, 0, item.shape, Effect.NONE, item.scorer,
                item.scorer_amount, item.price, item.name, portal_number=number,
                effects=item.effects,
                effect_amounts=getattr(item, "effect_amounts", None)))
            self._record_component_purchases(item)
            self._discover_block(item)
            self.cash -= price
            self._set_shop_message(
                f"Bought {item.name} (portal pair #{number})")
            sounds.play_coin()
            return
        # A Key/Lock block is bought as a matched pair too: the offer is the
        # bought half (it keeps its shape) and the second half is the other
        # shape, sharing a fresh key number. Both halves keep the offer's effects
        # and scorer.
        pair_shape = paired_shape(getattr(item, "shape", None))
        if getattr(item, "kind", None) == "block" and pair_shape is not None:
            number = next_key_number()
            self._unlock_offer(item)
            item.key_number = number
            self._unlock_purchase(BlockItem(
                0, 0, pair_shape, Effect.NONE, item.scorer,
                item.scorer_amount, item.price,
                f"{Shape.name(pair_shape)} {Scorer.name(item.scorer)}",
                key_number=number, effects=item.effects,
                effect_amounts=getattr(item, "effect_amounts", None)))
            self._record_component_purchases(item)
            self._discover_block(item)
            self._discover_component(Component.SHAPE, pair_shape)
            self.cash -= price
            self._set_shop_message(
                f"Bought {item.name} (key/lock pair #{number})")
            sounds.play_coin()
            return
        # A component or a plain block: the offer IS the purchase.
        self._unlock_offer(item)
        self._record_component_purchases(item)
        if getattr(item, "kind", None) == "block":
            self._discover_block(item)
        else:
            self._discover_component(item.kind, item.value)
        self.cash -= price
        self._set_shop_message(f"Bought {item.name}")
        sounds.play_coin()

    def _unlock_offer(self, item):
        """Turn the shelf's own offer into the player's item, where it lies.

        Buying unlocks the tile the player clicked: the offer leaves the shelf —
        no locked copy of it is left anywhere — and keeps the board square it was
        lying on, so the thing that was padlocked is now the thing the player owns
        (user request: "buying anything in the shop unlocks it and deletes the
        locked shop item ... it should become unlocked, stay in the same place on
        the board as where it was bought, and no locked ... shop item should exist
        anymore").

        Which container it joins depends on what it is: a card and an action have
        a list of their own, everything else is a portable item. An offer that
        was never on the shelf (one a test hands over directly) simply gets its
        own square instead.
        """
        self._consume_shop_offer(item, keep_cell=True)
        kind = getattr(item, "kind", None)
        if kind == "card":
            self._adopt_card(item)
        elif kind == "action":
            self._adopt_action(item)
        elif self.item_cell(item) is None:
            self.toolbox.add(item)
        else:
            # It already stands on the square the player bought it on, so it only
            # has to join the inventory.
            self.toolbox.items.append(item)
        return item

    def _unlock_purchase(self, item):
        """Seat an item a purchase MADE (a pair's second half) on the board.

        A portal or Key/Lock purchase makes a partner beside the offer the player
        clicked; the partner is a brand-new item, so it takes the first free
        square the way anything else the player gains does (see
        Game._on_item_gained).
        """
        self.toolbox.add(item)
        return item

    def _open_owned_pack(self, pack):
        """Open a pack the player OWNS (the S key).

        Packs are items now: buying one hands over the pack, and opening it is a
        separate, deliberate act (user request: "make packs a type of item that
        open when the player selects one and presses 's'"). The pack leaves the
        board as it opens — its options are what the player is choosing from —
        and the overlay holds the screen until the picks are made (see
        _click_pack / _keep_pack_option).
        """
        if pack is None or getattr(pack, "kind", None) != "pack":
            self._set_shop_message("Select a pack first")
            return False
        if not self.owns_item(pack):
            self._set_shop_message("You do not own that pack")
            return False
        if self.open_pack is not None:
            self._set_shop_message("Finish the open pack first")
            return False
        # The pack is spent as it opens: it is not scenery any more, its options
        # are. It is taken out of the inventory first so the layout cannot deal
        # it a square while the overlay is up.
        self._forget_item(pack)
        self.set_item_cell(pack, None)
        if self.toolbox.contains(pack):
            self.toolbox.remove(pack)
        self.open_pack = pack
        sounds.play_mech()
        self._set_shop_message(
            f"{pack.name} — keep {pack.remaining} of {len(pack.options)}"
            f"  •  click SKIP to leave the rest")
        return True

    def _open_pack(self, pack, price):
        """Open a pack that is being BOUGHT (kept for the old call sites).

        The cash buys the pack, not the items inside it: the player then keeps
        what its size allows (see _click_pack / _keep_pack_option), and may skip
        the rest. Purchases hand the pack over as an item now (see
        _buy_shop_item), so this only charges and opens an offer handed in
        directly.
        """
        self.cash -= price
        self._consume_shop_offer(pack)
        self.open_pack = pack
        sounds.play_coin()
        self._set_shop_message(
            f"{pack.name} (${price}) — keep {pack.remaining} of "
            f"{len(pack.options)}  •  click SKIP to leave the rest")

    def pack_option_at(self, pos):
        """Which option of the open pack a screen position is over, or None."""
        if self.open_pack is None:
            return None
        for index, rect in enumerate(ui.pack_option_rects(self)):
            if rect.collidepoint(pos):
                return index
        return None

    def _click_pack(self, pos):
        """Handle a click while a pack is open (see handle_events).

        Clicking an option keeps it, clicking SKIP takes nothing more and
        closes the pack (a click that is not on the panel does the same). The
        pack is closed from here only once nothing is left to pick: a mega pack
        stays open for its second choice.
        """
        index = self.pack_option_at(pos)
        if index is not None:
            if index < len(self.open_pack.options):
                self._keep_pack_option(index)
            return
        self._close_pack()

    def _close_pack(self, message=None):
        """Close the open pack, leaving whatever was not kept behind."""
        pack = self.open_pack
        if pack is None:
            return
        self.open_pack = None
        left = len(pack.options)
        if message is not None:
            self._set_shop_message(message)
        elif left:
            plural = "" if left == 1 else "s"
            self._set_shop_message(
                f"{pack.name}: left {left} option{plural} behind")
        else:
            self._set_shop_message(f"{pack.name}: everything kept")

    def _keep_pack_option(self, index):
        """Keep one option of the open pack: it is granted, then removed.

        An option that cannot be taken right now (a full inventory, a full card
        area, a card already owned) is REFUSED and stays on the table, so the
        player can pick something else or skip it: nothing is ever lost to a
        full shelf, exactly as a refused conversion keeps its points banked.
        """
        pack = self.open_pack
        option = pack.options[index]
        ok, message = self._receive_pack_item(option)
        if not ok:
            self._set_shop_message(message)
            return
        pack.options.pop(index)
        pack.kept += 1
        if not pack.open:
            left = len(pack.options)
            plural = "" if left == 1 else "s"
            message = (f"{message} — pack closed" if not left
                       else f"{message} — left {left} option{plural} behind")
            self.open_pack = None
        self._set_shop_message(message)

    def _receive_pack_item(self, option):
        """Hand one pack option over. Returns (taken, message).

        The options a pack can deal are the same goods the shelf sells, but
        they are already paid for, so this grants them WITHOUT charging (see
        _buy_shop_item, which prices and charges as it goes). A portal or
        Key/Lock block arrives as its matched PAIR, exactly as buying one does,
        and an action kept from an ACTION pack is not shelved at all: it is
        armed to be used (see _keep_action_from_pack).
        """
        kind = getattr(option, "kind", None)
        if kind == "resource":
            self._grant_resource_points(option.scorer, option.points)
            return True, (f"Banked {option.name} ({Scorer.name(option.scorer)} "
                          f"at {option.amount:g})")
        if kind == "card":
            if len(self.cards) >= self._card_capacity_for(option.value):
                return False, f"You can only hold {self.max_cards} cards — kept as an option"
            if self._owns_card(option.value) and not self._has_card(Card.SHOWMAN):
                return False, "Already own this card — kept as an option"
            self._adopt_card(option)
            self._discover_owned_card(option.value)
            return True, f"Kept card: {option.name}"
        if kind == "action":
            if self.open_pack is not None and self.open_pack.pack_type == Pack.ACTION:
                return self._keep_action_from_pack(option)
            if len(self.actions) >= self.max_actions:
                return False, f"You can only hold {self.max_actions} actions — kept as an option"
            self._adopt_action(option)
            self._discover_action(option.value)
            return True, f"Kept action: {self._item_name(option)}"
        if kind == "block":
            pair_shape = paired_shape(option.shape)
            if option.has_effect(Effect.PORTAL) or pair_shape is not None:
                number = (next_portal_number() if option.has_effect(Effect.PORTAL)
                          else next_key_number())
                second = (option.shape if option.has_effect(Effect.PORTAL)
                          else pair_shape)
                for shape in (option.shape, second):
                    self.toolbox.add(
                        BlockItem(0, 0, shape, Effect.NONE, option.scorer,
                                  option.scorer_amount, option.price, option.name,
                                  portal_number=number if option.has_effect(Effect.PORTAL) else 0,
                                  key_number=0 if option.has_effect(Effect.PORTAL) else number,
                                  effects=option.effects,
                                  effect_amounts=getattr(option, "effect_amounts", None)))
                self._discover_block(option)
                return True, f"Kept {option.name} (pair)"
            # The inventory is unbounded: a kept block always has a place (the
            # panel if there is a free cell, else the stash — see Toolbox).
            self.toolbox.add(option)
            self._discover_block(option)
            return True, f"Kept {option.name}"
        if kind in ("tool", "passive"):
            # A one-shot tool or a passive item (see the TOOL pack): both are
            # ordinary items, so they join the inventory where the player can
            # pick them up -- and both are collection entries of their own.
            self.toolbox.add(option)
            self._discover_tool_or_passive(option)
            return True, f"Kept {option.name}"
        # A component part (shape, effect or scorer): into the inventory.
        self.toolbox.add(option)
        self._record_component_purchases(option)
        self._discover_component(option.kind, option.value)
        return True, f"Kept {option.name}"

    def _keep_action_from_pack(self, action):
        """Use a kept action at once: it never takes an action-area slot.

        The user's rule for action packs is that their actions are USED rather
        than shelved, so the action is armed here instead of joining the action
        area: a target-free action fires immediately, and one that needs a
        target waits for the player to click it and press S (exactly like a
        selected action, see _select_action). An action that refuses to fire
        (nothing for it to do — a full board and no expansion left, say) STAYS
        armed so the player can try it again, the same "refused and kept" rule
        the action area follows.
        """
        self.pending_pack_action = action
        self._select_action(action)
        if Action.needs_target(action.value):
            return True, (f"Kept action: {self._item_name(action)} — click a "
                          f"target block/card, then press S")
        if self._apply_action():
            return True, f"Used action: {self._item_name(action)}"
        return True, (f"Kept action: {self._item_name(action)} — press S to use")

    def _discover_tool_or_passive(self, item):
        """Discover a kept tool or passive item; pop it up if it is new.

        The starters are already known (see collection.ALWAYS_DISCOVERED_TOOLS),
        so the only news here is a one-shot tool or a passive from a Tool Pack.
        """
        kind = getattr(item, "kind", None)
        if kind == "tool":
            if collection.discover_tool(item.value):
                self._push_popup("New tool", Tool.name(item.value),
                                 (116, 208, 196))
        elif kind == "passive":
            if collection.discover_passive(item.value):
                self._push_popup("New item", Passive.name(item.value),
                                 (152, 152, 152))

    def _discover_structure(self, value):
        """Discover a structure the player has just opened; pop it up if new.

        A structure is discovered by OPENING one: the codex entry is what the
        opening hands over, so it is news the first time a tool goes into one.
        """
        if collection.discover_structure(value):
            self._push_popup("New structure", Structure.name(value),
                             (170, 148, 126))

    def _discover_component(self, kind, value):
        """Discover a component in the collection; pop it up if it's new."""
        if not collection.discover_component(kind, value):
            return
        if kind == Component.SHAPE:
            name, category = Shape.name(value), "shape"
        elif kind == Component.EFFECT:
            name, category = Effect.name(value), "effect"
        else:
            name, category = Scorer.name(value), "scorer"
        self._push_popup(f"New {category}", name, (120, 200, 255))

    def _discover_match_group(self, group):
        """Discover a match group (a shape group or an effect); pop it up if new.

        A card is built on a match group, and the codex lists the groups rather
        than all 832 (group x scorer) cards, so obtaining a card reveals the
        group it was built on — and its scorer, which is a component in its own
        right (the same two things a splittable card used to reveal).
        """
        index = MATCH_GROUPS.index(group)
        if collection.discover_match_group(index):
            self._push_popup("New match group", match_group_label(group),
                             (140, 190, 190))

    def _discover_owned_card(self, value):
        """Discover an obtained card: its match group (or itself) and its scorer.

        A match-group card reveals the group it is built on plus its scorer (the
        codex tracks the 26 groups, not the 832 cards). A card that is not built
        on a group (Showman / Blueprint / ERR 404 / ...) reveals itself.
        """
        meta = match_group_card_meta(value)
        if meta is None:
            self._discover_card(value)
            return
        group, scorer = meta
        self._discover_match_group(group)
        self._discover_component(Component.SCORER, scorer)

    def _discover_block(self, item):
        """Discover every component that makes up a bought block."""
        self._discover_component(Component.SHAPE, item.shape)
        for effect in item.effects:
            self._discover_component(Component.EFFECT, effect)
        self._discover_component(Component.SCORER, item.scorer)

    def _discover_card(self, value):
        """Discover a bought card in the collection; pop it up if new."""
        if collection.discover_card(value):
            self._push_popup("New card", Card.name(value), (255, 200, 80))

    def _discover_action(self, value):
        """Discover a bought action in the collection; pop it up if new."""
        if collection.discover_action(value):
            self._push_popup("New action", Action.name(value), (200, 120, 255))

    def _discover_pack(self, pack_type):
        """Discover a bought pack TYPE in the collection; pop it up if new.

        The SIZE is not part of the entry (see collection.discover_pack), so
        buying a big card pack reveals the one Card Pack entry.
        """
        if collection.discover_pack(pack_type):
            self._push_popup("New pack", Pack.name(pack_type), (150, 200, 160))

    def _discover_trial(self, trial):
        """Discover a beaten trial in the collection; pop it up if new."""
        if collection.discover_trial(trial):
            self._push_popup("New trial", Trial.name(trial), (180, 120, 255))
