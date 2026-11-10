# Marblatro

A physics-driven deck-builder: you build a board out of blocks (each one a
**shape** × **effect** × **scorer**), release a marble at the Start block, and
watch it score as it falls, bounces and triggers everything it touches. Between
runs each **level** opens its own shape of board and puts its own **structures**
— a pit, a crystal pool, a mirror — on it, which the player's **tools** open into
actions or packs of components, pre-built blocks and cards, and every run plays
under exactly one **trial**.

## Quick start

```powershell
conda activate game          # Python 3.13 + pygame + numpy
python main.py               # play
```

Dependencies are just `pygame` (2.6+) and `numpy`; there is no build step:

```powershell
pip install pygame numpy
```

## The screen

A **bar** along the top of the screen holds the game's own furniture: the cash
readouts, the score readout, the trial box, the run/round display and the MAIN
MENU button. The **board** fills the rest of the screen, and it is
**infinitely large** — a square is any integer coordinate, and the camera decides
which part of it you are looking at. Locked squares are not board at all:
they wear the background's own pattern, so the playable region reads as
a platform floating in the void.

The shop sells **nothing** any more (user request: "add structures as part of
the level. remove the remaining shop items"): the shelf is empty, and the
structures a run offers are the ones its LEVEL put on the board, standing on the
level's own squares. They are **free** — no padlock, no price, a tool simply
opens one where it lies — and every item the player owns comes from their deck
instead. The buying, hoarding and pack-opening code is kept so a save written
before the change still works.

A structure is scenery until a **tool** is used on it: the player starts with four
tools — **Shovel** (dig), **Flashlight** (reveal), **Screwdriver** (fix) and
**Hammer** (break) — one per verb, and never spends one. A pit is dug into a part
pack or revealed into a **Tool Pack**, a crystal pool is revealed or dug into the
**Cleansing** action, and a mirror is fixed into Recognition or broken into
Strength (`components.Structure`). The reward takes the structure's square. The
tools are ordinary items, so the run's draw is what deals them:
`DECK_DRAW_SIZE` (4) items a run, tools included.

Every structure is also drawn as an **icon** of its own (user request: "give each
structure an icon"): `ui._draw_structure_icon` paints all fourteen by hand from
pygame primitives — a hole with a stone falling into it for the pit, a bar of
water with two crystals for the pool, a silvered oval for the mirror, a clay
figure for the golem, a crate for the depot, a coin for the mint — so a board
full of them reads at a glance and no two share a look. The letter glyph is only
the fallback for a value with no art, which is how a save from an older build
still draws.

Every item says what it does in one word apiece (`components.Keyword`): **dig**,
**reveal**, **fix** and **break** are the verbs a tool offers a structure,
**consume** means the item is destroyed by being used, **draw N** means it refills
the square it left behind, **temporary** means it is destroyed at the end of the
run it was made for, and **unplayable** means the item cannot be used at all —
either it is passive (it works by being owned) or it simply does nothing, like a
lump of dirt. The sidebar prints those words under
every item, so a tool's reach and a passive's payoff read at a glance:
**Concrete** is unplayable and pays +30 chips when a run starts
(`components.Passive`), **Brick** breaks or digs for **no energy** and is
consumed, and **Match** reveals for 1 energy, is consumed and draws an item. All
of them arrive in a **Tool Pack**, the one a revealed pit or shed hands over.

The tool catalogue is seventeen (`components.Tool`), and the thirteen beyond the
starters are one per gap the starters leave:

| Tool | Verbs | Energy | Spent? | What it adds |
|---|---|---|---|---|
| **Glowstick** | reveal | 0 | consumed | the free one-shot for the reveal half: a no-energy way into the card, action and tool packs |
| **Pry Bar** | dig + break | 2 | no | the permanent two-verb tool — answers 9 of the 14 structures, at two of a run's three energy |
| **Chisel** | fix | 1 | consumed | **shapes the reward**: the pack comes out `amount` rungs up the size ladder (Normal → Big → Jumbo → Mega → Giga) |
| **Gilding Cloth** | fix + reveal | 2 | consumed | **shapes the reward**: it arrives `amount` QUALITY tiers higher, so what is kept is worth double |
| **Wrecking Bar** | break | 1 | consumed | **sweeps**: opens the target *and* every structure standing in the four squares around it that answers break, for one swing |
| **Multi-Tool** | all four | 3 | no | answers any door there is — for the whole run's energy, once |
| **Drill** | all four | 0 | no | answers any door free, and packs a lump of **Dirt** into the deck each time (`Tool.MAKES`) |
| **Pickaxe** | dig | 1 | no | digs, and strikes a **Spark** into the deck |
| **Spark** | reveal | 0 | consumed | the cheapest opening there is — and **temporary**, so it is gone at the end of the run |
| **Vodka** | — | 1 | consumed | **modifies a card**: 3 stacks of *forgotten*, so it cannot be drawn until they wear off (`Ability.MODIFY`) |
| **Dirt** | — | — | no | does nothing at all: `unplayable`, and the price of a drill |

The two that shape a reward carry an **amount** (`Tool.AMOUNTS`), so a golem can
fold two of them together: a golden Chisel pushes two sizes, and the sidebar
prints what the number means (`Tool.AMOUNT_LABELS`).

Every item carries an **amount** — its magnitude (`items`: a block's is its
scorer's, a card's or an action's is its own, a Concrete's is the 30 chips it
adds) — so one number means the same thing wherever an item is read: the sidebar
prints it, a golem folds it, and the save file writes it down without asking
whether an item has one. A structure and a pack carry 0: what they hand over is a
fixed reward, not a number of their own.

Tools run on **energy**: the bar in the top bar holds `MAX_ENERGY` (3) pips, every
opening spends the tool's own cost (`Tool.ENERGY` — 1 for a starter, 0 for a
brick), and a run that starts is back to full — so a run can open three energy's
worth of structures, and the bar is the count of what is left. Hovering it says
so.

Everything the player owns lives in their **deck**, and the board shows only the
**hand** drawn from it: exactly `DECK_DRAW_SIZE` (4) random items, dealt onto the
board whenever a run is committed — and a brand-new game deals them at once, so
its first hand is the four tools. The two role blocks — the **Start** and
**Finish** blocks — are never dealt; they stay on the board so a run can always
be built. The **DECK** button in the bar opens an overlay listing the whole deck,
with the items currently drawn framed green, and says how many this run drew.
Under it, the **BOARD UNIT** button buys a unit for `$8`, which a click on a
locked square spends to open it.

## Controls

The board is the hand: the four items drawn from the deck lie on board squares,
and the rest of the deck waits behind them. The tools are items like the rest, so
a run that draws one can open structures and a run that does not cannot.

| Input | What it does |
|---|---|
| Click an item on the board | Flip its switch — every item is selected by the same toggle: on turns it green, a second click turns it off, and no other item changes. Any number can be on at once. **The first item switched on is the actor** — the one that gets used up — and every item switched on after it is one of its targets |
| Click anything that is not an item | Turn every switch off: the void around the board, a locked square (even with a Board Unit in hand), the bar |
| Left-click an empty unlocked square | Put the selected item down: a block is built on that square, anything else — a component, a card, an action, a structure, a tool — is moved there |
| Drag from an empty square | Grab the board and drag it: the board (and the background pattern behind it) moves with the cursor, so you can travel anywhere on the infinite board. A press that never moves is still a click |
| Right-click a shop offer (a save from before the change) | Buy it: that very tile is unlocked where it lies and the locked shop item disappears, so it can be used this run; a pack becomes a pack item you open with `S`. A structure is FREE and is not bought at all — arm a tool on it and press `S` |
| Middle-click a shop offer (a save from before the change) | Hoard: hold that offer in place through the next refresh (one offer per copy of the card) |
| Right-click anywhere else | Nothing |
| Hover anything | The sidebar describes it: shape, effects, scorer, trigger limit; for a structure, what opens it; for the cash and energy readouts, what they are made of |
| **A** | Rotate the block being placed by 90° |
| **S** | The context action: use the selected action on its targets, use the selected **tool** on the selected structure, open the selected pack, use a **Wasteful** block with one other item selected, assemble the selected parts into a block, disassemble a selected block — with nothing selected it builds a plain wall. The first four are the ABILITIES (`components.Ability`) and fire through one dispatcher; an action or a tool needs exactly the number of targets it asks for, and nothing happens without them |
| **B** | Sell the selected item (the actor) |
| **D** | Pay cash to raise the selected block's trigger limit |
| **G** | Odyssey: put the selected block/component away for the run |
| Click a locked square with nothing selected | Unlock it if you own a Board Unit (the marble can travel there, and items can be laid out on it); without one, a hint to buy one |
| Click the BOARD UNIT button in the bar | Buy one Board Unit ($8), then click a locked square to open it. The button shows the price and how many you have |
| Click the DECK button in the bar | Open the deck overlay: every item you own, the ones drawn onto the board framed green. Any click (or Esc) closes it |
| **T** | Start a fresh run (rolls a new trial). This is what releases the marble — the build phase has none |
| **R** | Restart the current run, keeping its trial. The run (and its marble) is reset back to the build phase |
| **V** | Turn every placed block back into a loose block |
| **SPACE** | Pause |
| **Y** | Move on. After a level it banks the cash and advances the round; **during** a level it gives up on it, which counts the level as lost |
| Any other key after a level | Retry: undo the level (and its result) |
| **P** | Save to the active slot |
| **F2** | Toggle the CRT screen filter |
| **ESC** | Back out of menus |

## How the code is laid out

| File | Role |
|---|---|
| `components.py` | **The source of truth for game data.** Enums for shapes, effects, scorers, conditions, cards, actions, packs, structures, tools and trials, plus their `NAMES` / `DESCRIPTIONS` / `PRICES` / `COLORS` / `GLYPHS` / `ORDER` tables, the price helpers, the magnitude roll (see `MAGNITUDE_SPREAD`), the `Ability` table (what an item needs, what it costs, and the method that does it), the `Keyword` vocabulary, the `Group` families every item belongs to, the `Modifier` table and `Modifiable` mixin every item's mutable state lives on (golden, forgotten, temporary, token, …) and the `Quality` tiers a golem leaves (see `_draw_quality_mark` in `ui.py`). |
| `main.py` | The **entry point** and the game's single namespace. The pieces below are re-exported from here, because the code and the tests refer to them as `main.Block`, `main.Game`, `main.SHOP_COORDS`, …; it also wires the drawing helpers onto the classes (`Game.draw = ui.draw`) and runs `python main.py`. **It contains zero drawing code and almost no logic.** |
| `config.py` | Every tunable: the colours, the layout geometry (every rect and panel coordinate), the prices, and the score scales. |
| `rolling.py` | The rolls and prices an item is built and valued with: magnitudes, the cards and match groups the shop offers, the key/portal numbers, resale prices. |
| `blocks.py` | `Block`: one square of the board, with its shape, effects, scorer and rolled magnitudes. |
| `enemies.py` | `Enemy`: a `Block` that fights back instead of scoring. A marble's hit deals its `chips x mult` as damage and wipes its own chips and mult; patrollers slide along their row, cowards flee the marble, beetles only take a few hits and maws swallow the marble. The numbers live in `components.py` (`EnemyKind`, `ENEMY_HP_SHARE`, ...), and a level's enemies share out the run's old required score between them (`components.split_enemy_health`). |
| `items.py` | What the player owns: `BlockItem`, `CardItem`, `ActionItem`, `ItemPack`, `StructureItem`, `ToolItem`, `PassiveItem`, `ResourceOption`, `ScorerToken`, `CashBreakdown`. |
| `shop.py` | The `Shop`: the offers standing on the board -- an empty shelf now, since the LEVEL owns the structures -- plus the buying/hoarding paths a save from before the change can still use. |
| `toolbox.py` | `Toolbox`: the player's portable items (loose blocks and components). Ownership only — where an item stands is the game's business, and an item with no square is in the deck (see `game_deck.py`). |
| `game_deck.py` | The deck: which items are drawn into the hand, the draw at the end of a run, and returning a purchase to the deck. |
| `marble.py` | `Marble`: the ball's physics state and its trail. |
| `game.py` | `Game`, assembled from the feature mixins below — one object, but its ~300 methods live in the module that owns their subject. |
| `game_*.py` | The mixins: `game_core` (setup, locked squares, profiles), `game_input` (the event loop), `game_build` (placing and assembling), `game_store` (purchases and packs), `game_slots` (cards, actions, slots), `game_actions` (the one-shot actions and `_use_ability`, the single dispatcher behind `S`), `game_inventory` (Spirit tokens, banking and selling), `game_economy` (money and resource points), `game_describe` (info-box text), `game_frame` (update, autosave, achievements), `game_runs` (runs, trials, score, gondolas), `game_contact` (what touching a block does), `game_payoffs` (xMult, Procrastination, block scoring), `game_ending` (cash out, retry, the main loop). |
| `ui.py` | **All drawing.** Screens (`draw`, `draw_title_screen`, `draw_collection`, …), the board and marble rendering, the sidebar and every info box, the icon art, and the shared font table. Functions take the object they draw as their first argument; `main.py` keeps thin delegating wrappers (`Game.draw`, `Block.draw`, …). |
| `physics.py` | The marble simulation: per-frame integration, every collision shape, effects like portals, magnets and black holes. |
| `cards.py` | The card hooks that fire on collisions, run start/end and sales. |
| `sounds.py` | Every sound effect, synthesized as waveforms at import time (no audio files). |
| `crt.py` | The optional CRT post-process (barrel warp, scanlines, vignette) applied by `Game._present`. |
| `save_system.py` | Serialising a game to `profiles/<profile>/saves/saveN.txt` and reading it back. |
| `profiles.py`, `player_paths.py` | Profiles (each with its own saves, achievements, collection and metagame) and the one place that decides where player data lives. |
| `metagame.py`, `achievements.py`, `collection.py` | The persistent extras: dice and permanent upgrades, achievements, and what the player has discovered. |
| `fonts/` | `garet-heavy.otf` (all UI text) and `MARBLERUN.ttf` (the title face). |

Conventions worth knowing before editing:

* **A run is a LEVEL, and its goal is its enemies.** `components.LEVELS`
  holds the 24 levels (one per run), and every level opens about the same
  NUMBER of board squares in a different SHAPE: a plain arena, a field with
  pits punched in it, two tiers joined by a neck, an hourglass, a tower with
  shelves and an accelerator, a cross, two rooms and a corridor, a ring, four
  corner rooms joined by thin corridors, detached islands. Levels also place
  their own PROPS (`components.PROP_PARTS`): wall pillars, bouncers, ice,
  accelerators to climb with, pistons, phase blocks, slopes, shelves, a cable
  car, and a key with its lock. Props are level furniture, not the player's:
  they cannot be selected, sold, taken up or built over.
* **Enemies stand where their level puts them**, usually at opposite ends, so
  the marble has to be driven up as well as down. An enemy placed on a square
  its level does NOT open is BURIED in the wall: it is drawn inside the wall
  and can only be reached once the player buys that square with a Board Unit,
  which is exactly what those Deep Pits levels are asking about. A moving
  enemy keeps to unlocked squares and turns round at the edge of its room.
* **A level asks for the score its run used to require.** The enemies' health
  IS that number (user request: "make the sum of all enemies' health equal to
  the total required score that was originally there before the system was
  changed to enemies"): `Game._level_health_budget` reads the run's
  `required_score` -- still computed for every run, still doubled by Sky High
  and zeroed by Grace v2 -- and `components.split_enemy_health` divides it
  between the enemies that reach the board, whole numbers summing to it
  EXACTLY, in the proportions `components.ENEMY_HP_SHARE` gives each kind. So
  the old difficulty curve is back: level 1 asks 100, the last level asks the
  8.4M the schedule always ended on, and a level never holds a fixed per-kind
  HP again. `ENEMY_HP_SHARE` is only the SHAPE of the split (a Maw is worth
  about two Slimes); the level decides the total.
* **A level is laid out BEFOREHAND, and starting a run only puts it back.** A
  level becomes current when a brand-new game opens (`_reset_board_to_start`), on
  the CONTINUE between runs (`_continue_run`), after the game-over screen
  (`_begin_endless_play`) and when a save is loaded (`_load_save_data`), and it is
  laid out then — its squares opened, its props, structures and cast standing on
  their own squares — long before the player presses T (user request: "load the
  level beforehand instead of when the game updates so that the level does not
  appear to change randomly"). Laying it out again (`Game._begin_level`) never
  RE-DECIDES anything for the same level: the props go back on the level's own
  offsets (`_place_level_props`), an enemy already on its square is `reset` there
  at full health rather than replaced (`_place_level_enemies`), a structure keeps
  the square it stands on and only a square a player's BLOCK occupies can move
  one (`_place_level_structures` / `_player_block_cells`), and the level's own
  blocks are never counted as "taken" — which is what used to make the second
  layout shuffle everything. A DIFFERENT level replaces what the old one laid
  out (`keep=False`).
* **A marble exists only while its run is being played.** `reset_run` releases
  it (that IS starting a run), and every path that puts the board back into the
  build phase throws it away through `Game._discard_run` — R, a retry, unlocking
  a square, moving an item — so the build phase never shows a marble nobody is
  playing with (user request: "create a marble only when the player presses t to
  start the run. delete the marble when the run is reset"). A run that has
  FINISHED keeps its marble until the next run replaces it, so the results screen
  still shows where it ended.
* **A level is won when every enemy is defeated AND every marble has reached
  the Finish**. A level is never lost by
  playing -- it only becomes impossible -- so **Y** gives up on it at any time
  and counts it as lost, and three lost levels end the game.
* **The score lives on the marbles.** Every marble carries its own `chips`
  and `mult`, seeded from the run's base when it is released, so a block's
  scorer only moves the score of the marble that collided with it (a split
  copy inherits its parent's). `Game.score_chips` / `score_mult` are
  properties over "the marble being scored", which is what lets cards,
  tokens, the HUD and saves keep reading "the score" unchanged.
* **Data lives in `components.py`.** Adding a shape/effect/scorer/card/trial
  means adding its id and its table rows there; the UI, the shop and the
  collection pick it up automatically.
* **`ui.py` never includes logic, the game modules never draw.** Keep it that way.
* **`Game` is one class but many files.** A method belongs in the `game_*.py`
  mixin that owns its subject; every mixin shares the attributes `__init__` (in
  `game_core.py`) creates, so a method in one calls a method in another freely.
* **Fonts are built once**, in `Game.__init__` (see `FONT_SIZES`), and handed to
  the UI with `ui.bind_fonts` — nothing anywhere else builds a font.
* **Magnitudes** (a scorer's amount, a piston's speed) are rolled around their
  average with a continuous truncated Cauchy whose tail is set by
  `components.MAGNITUDE_SPREAD` (4 = a deliberately long tail). A roll changes
  what an item DOES, never what it costs. Every number an item carries is a
  MAGNITUDE, and `components.MAGNITUDES` is the one table they live in: effects,
  scorers, cards (`CARD_RATIOS`, `TRASH_CAN_CHIPS`, `SMELLY_SOCKS_CHIPS`/_MULT)
  and ACTIONS (`LANTERN_DRAWS`, `EYEBALL_DRAWS`, `DEEP_POCKETS_PACKS`,
  `COCKTAIL_ENERGY_PER_MODIFIER`, bound onto `Action.MAGNITUDE`). An action with
  a magnitude
  carries it on the item (`ActionItem.amount`), which is why its text, its
  sidebar row, its upgrade and a golem's doubling all read the same number: two
  Lanterns combined draw four items, and nothing in the code types "4".
* **An ACTION can ask for the run's energy.** Energy is the run's budget
  (`MAX_ENERGY`), which the tools spend to open structures — and the newest
  actions spend it too (`Action.ENERGY`: Eyeball and Deep Pockets 1, the Nasty
  Cocktail 0). `Game._apply_action` charges it before anything fires and spends
  nothing on a refusal, the same rule `_apply_tool` follows, and the item's
  Ability row says so ("Costs the action itself and 1 energy"). An action that
  only ARMS something (Eyeball's pick, below) is charged when the thing it armed
  happens, so backing out of it costs nothing.
* **The board is infinite, and the camera is the window onto it.** A square is
  any pair of integers, so there is no edge, no `GRID_WIDTH` bound and nothing
  to fall off: `Game.cell_to_screen` / `screen_to_cell` convert between a square
  and the screen through `Game.camera`, and `Game.pan_board` drags the board (the
  flat `GRID_WIDTH x GRID_HEIGHT` count is only how many squares fit on screen at
  once). The board is GRABBED, not scrolled: dragging right pulls the board right
  with the cursor, which moves the camera the other way. Pressing on board space
  that holds no item starts the drag; a press that never moves is still a click.
  The trial tessellation behind the board scrolls with it (`ui.background_scroll`),
  so the pattern and the squares move as one.
* **Locked squares are the void, not board.** They are painted with the
  background's own pattern (the run's tessellation, or the flat background
  colour), so the playable region floats in it, and they are solid: only the
  FRONTIER of locked squares around the unlocked region needs a wall, because a
  marble can only reach a locked square through one (`Game._board_wall_blocks`).
  The pattern is drawn from the same scroll offset as the screen behind it (see
  `ui.background_scroll`), so it stays in phase across the boundary and moves
  with the board.
  The marble's hard clamp is the unlocked region plus two squares, which leaves
  room for the Phase effect to carry it into a wall.
* **The board is the HAND; the deck holds everything else.** There is no
  inventory panel, card tray or action row, and the board no longer shows
  everything the player owns: it shows the DECK_DRAW_SIZE items *drawn* from the
  deck (`Game.deck_items` / `hand_items`), each standing on a board square and
  drawn, clicked and selected there. `Game.ensure_board_cells` keeps the hand on
  UNLOCKED squares only (an item never stands on a locked one) and no longer
  deals a square to everything: an item with no square is simply in the deck. A
  block that is placed owns its square and hides its item. `Game._cycle_deck`
  empties the board into the deck when a run is committed and deals a fresh hand;
  the START and FINISH blocks and Spirit tokens are never dealt, and the shop's
  offers are laid out beside the hand. The draw is exactly `DECK_DRAW_SIZE` items
  (`Game.draw_deck_hand`, remembered in `deck_drawn`), and that is the number the
  DECK button reports — the role blocks and whatever the run bought or was
  granted stand on the board without being drawn. The four TOOLS are dealt like
  anything else (user request: "shovel, flashlight, screwdriver, hammer all count
  as items, meaning they are part of the condition that only 4 items can be
  drawn"), and a brand-new game draws its opening hand at once. **The hand is
  always four items, with START and FINISH beside them and never among them**
  (user request: "make sure the player always draws 4 items, besides the start
  and finish"): `Game._return_hand_to_deck` is the one rule for handing the hand
  back — everything but the role blocks and the tokens — and both `_cycle_deck`
  and `_reset_board_to_start` use it, so a new game's opening hand is a real
  DRAW rather than whatever happened to be standing on the board (the four tools
  used to keep the squares they were built on, which left the deck empty and
  dealt a hand of nothing).
* **The newest cards reach outside the score: the deck, the energy budget and the
  level.** Each does it through a door the game already had:
  * **Eyeball** (an action, 1 energy) arms a PICK and opens the DECK overlay
    (`Game.arm_deck_pick`): the overlay becomes a picker, every card the action
    could draw wears a yellow frame, and clicking one draws it
    (`Game._draw_deck_card` — the same `_on_item_gained` a run's draw uses). The
    action's magnitude is how many picks it grants, so a golem-folded Eyeball
    takes two. Nothing is spent until a card is actually drawn — a look that is
    backed out of with Esc keeps both the action and its energy — and a run that
    starts drops a stale pick (`reset_run`).
  * **Deep Pockets** (an action, 1 energy) rolls a pack with the shop's own
    roller and hands it over as an item on the board, and pulls down a random
    level structure in exchange: the structure is taken off the level through
    `_consume_structure` with `discover=False`, so its square is marked SPENT
    (it cannot come back there) but the codex does not learn it — a structure is
    revealed by OPENING it, and this one was never opened. Its magnitude is the
    number of packs, and of structures, one use deals with.
  * **Smelly Socks** (a whole card, unplayable) pays `SMELLY_SOCKS_CHIPS` and
    `SMELLY_SOCKS_MULT` at the start of every run — two currencies at once, which
    a measured `Card.NAMED` row cannot express, so it is a fixed payoff read in
    `cards._apply_smelly_socks` (Blueprint copies it; the Card cutter trial stops
    it) — and charges for it: a card drawn into the same hand goes back INTO THE
    DECK (`Game._settle_smelly_socks` -> `_to_deck`), not out of the game (user's
    answer: "the card goes back into the deck and is not destroyed. The player
    could draw it again using cards that draw more cards"), so any draw can deal
    it again on a later run or through an Eyeball.
  * **Nasty Cocktail** (an action, 0 energy) gains its magnitude in energy for
    every KIND of modifier riding on it (`Modifier.of`: golden, diamond,
    forgotten, temporary, token, retriggerable, v2, flipped, disabled) — so a
    plain one gives nothing and is refused (and kept), while an upgraded (v2) or
    golem-gilded one is a real drink.
  * **Reroll** (an action, 0 energy) is what a reroll IS now: the card is aimed
    at a STRUCTURE (`Action.STRUCTURE_TARGET`, the one kind an action may be
    pointed at besides blocks/cards), turns it into another random structure
    where it stands, discards itself through the ordinary discard door and draws
    a card into the square it gave up (`Game._action_reroll`). Its magnitude is
    the cards it draws, so a golem-folded one draws two.
* **Every reroll mechanic deals the Reroll card** (user request: "make all
  reroll mechanics spawn this card on the board when triggered"). Free shop
  rerolls had nothing to spend them on once the shelf stopped selling, so:
  * **Fresh** deals one Reroll card per `amount` when it triggers
    (`Game._spawn_reroll_cards`), a block or a card alike, and the run OWES it:
    the dealt cards are kept in `Game.reroll_cards_run_gain`, and a retry or a
    restart takes back exactly what the discarded run dealt
    (`Game._take_back_run_rerolls`) — a card already used is simply not
    un-spent, and a CONTINUE clears the ledger without taking anything.
  * **Brainstorm** deals `BRAINSTORM_REROLLS` (v1) or `BRAINSTORM_REROLLS_V2`
    (v2) cards. They were bought, not earned by a run, so a retry keeps them.
  * **Tesseract** counts these: using a Reroll is what grows its permanent xMult
    (`Game._grow_tesseract`).
  * A reroll is written into the LEVEL's PLAN (`Game.structure_rerolls`:
    plan entry -> value, carried in saves), so no later layout pass — an R, a
    board edit, a run start, a load — deals the structure the level authored
    over the top of it.
* **The level owns its structures; tools open them.** Each level declares the
  kinds it puts on its own squares (`components.Level.structures` ->
  `structure_spawns`) and the game lays them out every run, spread through the
  level's shape (`Game._place_level_structures`). **Every run puts out four**
  (user request: "have 4 structures each run instead of 1"): a level authors the
  kinds that suit it and `Level._plan_structures` repeats them up to
  `components.STRUCTURES_PER_RUN`, so a pit level deals four pits and the last
  level deals pit, pool, mirror, pit. Four is deliberately one more than the
  three energy a run is given -- the offer is a choice, not a shopping list. The
  shop deals nothing at all
  any more (user request: "add structures as part of the level. remove the
  remaining shop items (packs generated each run)"). Structures are **FREE**: a
  structure wears no padlock and shows no price, a right-click only says so, and
  a tool opens it where it lies -- the spent structure leaves the board with its
  reward in its square (`Game._apply_tool` / `_consume_structure`). A structure
  answers only to the verbs it is built for (`Structure.RESULTS`): a pit is dug
  -- never broken -- into a part pack, a crystal pool is revealed or dug into
  Cleansing, a mirror is fixed into Recognition or broken into Strength, and a
  wrong tool changes nothing at all (`Game._apply_tool`). The reward REPLACES
  the structure: it takes the very square the structure was standing on, and the
  item is seated there before it is adopted so the square is claimed first; the
  structure itself is spent, and the tool is not: the player owns all four (one
  per `Verb`) and keeps them. The tools are ordinary ITEMS, though, so they are
  drawn with the rest of the deck (user request: "shovel, flashlight,
  screwdriver, hammer all count as items, meaning they are part of the condition
  that only 4 items can be drawn") -- a run that does not draw one simply opens
  no structures. A spawn square never holds one of the level's own props or
  enemies (`Level._structure_spawns` skips them), and a square the PLAYER has
  built on does not shrink the offer: the structure moves to the free level
  square nearest the one its level picked (`Game._free_level_cell`), so a run is
  always dealt four openings -- though the ones it has already opened stay opened
  for the level visit, so what is left is the count of them. **A structure stands on the square its LEVEL chose**
  (user request: "make structures be placed in different areas of the level,
  instead of always at the top"): `_structure_spawns` cuts the level's free  squares into one slice per structure and takes the middle of each, so the four
  are spread through the level's SHAPE -- near its top, its middle and its
  bottom, in different columns -- and `_place_level_structures` seats each one
  with `set_item_cell`, because an item with no BOARD square is dealt one by the
  next layout pass in reading order, which is a row along the top of the board
  (`col`/`row` are the shelf's drawing cells and mean nothing to the board).
  **They can always be moved** (user request): a structure is an offer standing
  on the board, so clicking it picks it up and the next click on an empty
  unlocked square puts it down there (`Game._place_block_at`), which is how a
  player opens one where it suits the marble. A reroll (`Shop.refresh`) and the
  Slim pickings trim (`Game._trim_shop_for_trial`) both leave the level's own
  structures alone: they are scenery the LEVEL put out, not shelf stock.
* **An opened structure stays opened for as long as its level is in play.** User
  report: "if the player unlocks a structure using a tool, and then moves the
  tool, the structure will revert itself back into a locked state" — and the same
  cause made "when the player presses t, the level sometimes resets". Laying a
  level out again kept FILLING IN a structure the player had already opened,
  because "there is a structure of this kind missing" was read as "a structure
  was destroyed, put it back". Opening one now records the square in
  `Game.spent_structures` (`_consume_structure`), and `_place_level_structures`
  skips a spent structure both where the level planned it and where a player's
  block pushed it (`_structure_is_spent`). The set belongs to the level VISIT: it
  is emptied only when the level number changes (`_begin_level`) or on a new game,
  so a board edit, R, a retry and T all leave the opened ones opened, and a save
  carries the set (`save_system`) so a load cannot re-deal them.
* **Placing one item on another SWAPS them; nothing is ever knocked into the
  deck.** User report: "tools can sometimes disappear if the player places a
  structure on a tool". Moving an item onto an occupied square used to set the
  occupant's square to `None` — and `ensure_board_cells` only re-seats the role
  blocks, the stash and the shelf, so the occupant slid into the deck and left the
  player's hand. `Game._move_item_to` now trades the two squares, and when the
  mover has no square to give, `_seat_aside` seats the occupant on the first
  square nobody claims — refusing the move only when the board is genuinely full.
  `_place_block_at` seats an item a block is built over the same way, and so does
  `_place_level_structures` when the level claims a square one of the player's own
  items is standing on — which is what a load looks like, since a save does not
  store the level's structures. Building a block on a tool keeps the tool.
* **One structure per pack: every item in the game is obtainable.** User
  request: "make all items in the game obtainable through structures. For
  example, add a new 'tool pack' that gives tools. for each pack, create a new
  structure." Each `components.Pack` type has a structure of its own in
  `Structure.RESULTS`, so nothing in the game is out of reach:

  | Structure | Opens with | Hands over |
  |---|---|---|
  | **Quarry** | dig | Shape Pack |
  | **Shrine** | fix | Effect Pack |
  | **Vault** | break | Scorer Pack |
  | **Workbench** | fix | Part Pack (shapes, effects and scorers mixed) |
  | **Depot** | break | Block Pack (ready-made blocks) |
  | **Library** | reveal | Card Pack |
  | **Cabinet** | reveal | Action Pack |
  | **Mint** | dig | Resource Pack |
  | **Rift** | any tool | Random Pack |
  | **Shed** | reveal | Tool Pack (every tool that is not starting kit, and the passive items) |

  The pit, pool, mirror and golem keep their own rewards, so several routes
  reach the same goods. Each opens with ONE verb (so a level's board asks for a
  particular tool) except the rift, which answers to anything; `Structure.PRICES`
  keeps every one of them free, `OFFER_WEIGHTS` keeps their odds summing to 100,
  and the levels author them so every structure turns up in play — the last
  level authors all fourteen, which is what lets its bonus slots deal any of
  them (`Shop._level_structures` reads the level's AUTHORED kinds).
* **The golem combines instead of paying out.** It is the one structure whose
  reward is not fixed in the table: `Structure.RESULTS[GOLEM]` says
  `("merge", 2)` for EVERY verb (it is a workbench, not a lock, so any tool
  wakes it), and the opening takes the two same items selected behind it and
  folds them into one with BOTH their magnitudes (`Game._golem_pair` ->
  `_combine_items`). Two Lanterns become a Lantern of 4, two +30 chip scorers a
  +60 one, two identical blocks a block with double its scorer amount and effect
  strengths; the combined item takes the golem's square and the one it was
  folded with is thrown away through `_discard_item`. Nothing is spent on a
  refused combine (one item, two different items, or items with no magnitude at
  all), and the count of items it takes is the table's `2`, not a constant in
  the handler. Levels 6, 9, 12, 16, 18, 21, 22, 23 and 24 put one out.
* **A golem's work is a TIER, not just a number.** `components.Quality` holds
  the three tiers — plain, GOLDEN and DIAMOND — and everything said about one
  comes from its row: the word a name is prefixed with (`Quality.title`:
  "Golden Lantern", "Diamond Rect +Chips v2"), the multiplier it is worth (2x and
  4x), the colour its tile wears, and what it combines INTO (`COMBINES_INTO`;
  DIAMOND has no entry, which is what makes it final). So the first combine
  leaves a golden item, and folding two golden items into a diamond lands on 4x
  the original for free — one fold doubles, and the magnitude the pair already
  carries does the arithmetic. `_golem_pair` refuses a golden paired with a plain
  one and refuses a diamond outright, saying why (`_item_name` already shows the
  tiers, so the message reads "Golden Lantern and Lantern differ"). The tier
  rides the item through the board (`_place_block_at` builds a golden block,
  `_refund_block` carries it back), the sidebar explains it in a `Quality` row,
  `ui._draw_quality_mark` draws a coloured frame and a gem, and `save_system`
  stores it. The two tiers are also modifiers (`Modifier.GOLDEN`, `Modifier.DIAMOND`),
  so `item.quality` is a view over the item's modifier bag rather than a field of
  its own — one home for the state, one drawer, one save field.
* **Energy is the run's budget for the tools.** `MAX_ENERGY` (3) pips sit in the
  top bar (`ui.draw_energy_bar`), every opening spends the tool's own cost
  (`Tool.ENERGY`, spent in `Game._apply_tool`), and a run that starts is back to
  full (`Game.reset_run`) — so a run opens three energy's worth of structures, and
  nothing is spent on a use that was refused (a pit cannot be
  broken, and a tool with no structure selected has nothing to open). Restarting
  or retrying a run hands the same budget back, and the count is saved with the
  run (`save_system`), so a load is not a refill. Hovering the bar explains it
  (`Game._energy_rows`).
* **A pack is an item** (kept for saves from before the change). Selecting one
  and pressing `S` deals its options (`Game._open_owned_pack` ->
  `Shop._roll_pack`), and what is not kept is gone. The options are shapes,
  effects, scorers, blocks, cards, actions and resource points, all rolled by the
  one roller, `Shop._offer_of`. Packs are no longer generated each run, so the
  only packs in a game are the ones a level's structures hand over.
* **Every item kind has a branch of its own in the save file.** `save_system`
  serializes a shop/toolbox/grid item by its `kind` — block, card, action,
  structure, tool, passive, resource, pack — and anything else falls through to
  the Component shape. That fallthrough is safe because **EVERY item carries an
  `amount`** (`items`: a block's is its scorer's magnitude, a passive's is the
  number it pays, a structure's, a tool's and a pack's are 0), so the shape reads
  `item.amount` without asking whether it is there. It used to fall back on a
  default there, which only hid the real gap: a Passive had no amount at all, and
  the autosave died with "AttributeError: 'PassiveItem' object has no attribute
  'amount'" while the player was choosing from a Tool Pack that held a Concrete.
  Now the amount is part of what an item IS — Concrete's is
  `MAGNITUDES.CONCRETE_CHIPS` (30), a golem folds two of them into one of 60, the
  run pays whatever the item carries, and the save writes the number down (a test
  walks every kind the shop can offer through
  `_serialize_item`/`_deserialize_item` and checks the amount survives).
* **One ABILITY table says what every item can do.** `components.Ability` is a
  table of five rows — OPEN (a tool on a structure), APPLY (an action on its
  targets), OPEN_PACK (a pack), DISCARD (a Wasteful block with one other item)
  and MODIFY (a tool laying a modifier on a card, as vodka does) —
  and each row is the whole contract: what it needs (`NEEDS`, printed by
  `needs_text`/`contract`), what it costs (`COSTS`), and which method carries it
  out (`HANDLERS`, e.g. `_apply_tool`). An item's ability is DERIVED from what it
  is (`Ability.of`: an item's `kind` and effects), never stored, so an item
  cannot be created with an ability no one can fire. `S` is one dispatcher,
  `Game._use_ability`, which walks the selection, finds the ability, checks the
  signature (`_ability_is_ready`) and calls the handler — the old if/elif chain
  is gone, and adding DRAW, DAMAGE, BUFF or GROW later means one row plus one
  handler. The sidebar prints the same row (`Game._describe_item` ->
  "Ability - Open: Needs 1 structure. Costs 1 energy. Press S to use it."), so
  the hint and the behaviour cannot drift, and an item with no ability simply
  prints no row and leaves `S` to assembly.
* **One vocabulary describes every item.** `components.Keyword` holds the eight
  words an item can carry — DIG, REVEAL, FIX, BREAK (the verbs, `VERB_KEYWORDS`),
  CONSUME and DRAW (what happens to the item afterwards), UNPLAYABLE (it is
  passive, `components.Passive`) and TEMPORARY (it dies with the run) — each with
  a one-line meaning the sidebar reprints (`Keyword.line`), so "can a brick break
  this?" is answered by the same table that decides what pressing `S` does.
  Keywords are DERIVED, never stored
  (`Keyword.of`: a tool reads `Tool.keywords`, a passive is unplayable, a
  structure reads `Structure.verbs`), and a tool may offer several (`Tool.VERBS`
  is a tuple) — `S` uses the first its structure answers, so a brick breaks a
  mirror and digs a pit. Consuming goes through the ordinary discard
  (`Game._discard_item`), so a spent brick counts for the Trash Can like any
  other item.
* **A MODIFIER is the state riding on an item, and one table holds them all.**
  `components.Modifier` lists the nine kinds — GOLDEN and DIAMOND (the golem's
  tiers), FORGOTTEN (cannot be drawn, one stack off per run), TEMPORARY
  (destroyed when its run ends), TOKEN (a kept block fires every run, once per
  stack), RETRIGGERABLE (one extra trigger per stack), V2 (the upgraded action),
  FLIPPED and DISABLED (what a trial does to a card) — and each row is a name, a
  one-line meaning, a colour, and whether its stacks COUNT DOWN. The item side is
  one mixin, `components.Modifiable`, whose whole state is a `{modifier: stacks}`
  bag: every piece of it the game already kept in a field of its own is now a
  view over that bag, so `item.quality`, `action.version`, `block.trigger_limit`,
  `card.flipped` and `token.runs_left` read and write modifiers while the golem,
  the trials, the sidebar and the save file carry on unchanged. One clock ages
  them (`Game._age_modifiers`, run when a finished run is committed — so a retry
  costs nothing): a forgotten item loses a stack and is skipped by
  `drawable_deck_items` until they are gone, a temporary item is thrown away
  through the ordinary discard. A tool can also apply one (`Ability.MODIFY`:
  vodka puts 3 stacks of *forgotten* on a card and is spent for it), the sidebar
  prints a `Modifier - Forgotten x3` row per kind, `ui._draw_modifier_marks`
  puts the tier frame and an `F3`/`T` plate on the tile, and
  `save_system` writes the bag as `"modifiers"`.
* **Every item belongs to one GROUP, and wears it under its name.**
  `components.Group` is the family table — Block, Part, **Cards**, Structure,
  Pack, Passive, Token, Resource, plus the level's own Foe and Prop — and each
  row is the name the box prints, one line saying what the family is for, and
  the colour it wears. A card, an action and a tool are ONE family (user
  request: "join together cards, tools, and actions into one group called
  'cards'"): all three are what the player keeps and plays, and `Group.KINDS`
  lists the three kinds under the one row. A group is DERIVED from what the item
  is
  (`Group.of`, riding on the item's `kind`; a Block on the board has no `kind`,
  so it reads as a block), which is what stops an item existing in a family
  nobody can read. The description carries one `Group - Cards` row
  (`Game._group_row`), and the info box lifts that row out and draws it as a
  highlighted box directly under the item's name (`ui._draw_group_badge`): the
  family's colour on a dark tint of it, the group's name on the first line and
  that one-line meaning wrapped under it. `ui.info_layout` counts the box in the
  box's own height, and `Group.ORDER` is the reading order the deck overlay
  lists a collection in (`Game.deck_overlay_items`), so the deck reads by family
  instead of by the order things were bought. The COLLECTION says the same in
  every cell: `ui.draw_collection_group` fills a small box in the cell's bottom
  corner with the family's name in its colour (user request: "add a box in each
  entry of the collection that shows which group that item is in (without the
  group's description)") — the name alone, because the cell has no room for the
  line and the entry's own description is right above it. A match-group entry
  reads as Cards (it stands for the cards built on it); a trial is a way to play
  a run, so it wears a family of its own (`Group.TRIAL`) and no cell of the
  codex is left unlabelled.
* **Every item is in the COLLECTION, and every item wears an icon.** User
  request: "make sure all items are in the collection, if they aren't already.
  give all items an icon if they don't already have one." `collection.py` keeps
  one discovered set per SECTION (`_empty`), and `Game._collection_entries`
  prints one entry per value of every table: the components a block is made of
  (shapes, effects, scorers), whole cards, the 26 match groups, actions, packs,
  trials — and the three kinds that are items in their own right, TOOLS,
  PASSIVES and STRUCTURES. Each is revealed by the thing that hands it over: a
  kept tool or passive from a Tool Pack (`_receive_pack_item` ->
  `_discover_tool_or_passive`), an opened structure (`_consume_structure` ->
  `_discover_structure`), and the four starters are known from the first game
  the way the Start and Finish scorers are (`ALWAYS_DISCOVERED_TOOLS`). A kind
  with no section here could never be seen at all, which is what the request was
  about. Every value in every table also draws a picture of its own rather than
  a letter standing in for one: `ui._tool_art` (a spade, a torch, a screwdriver,
  a hammer, a brick, a lit match), `ui._passive_art` (a poured slab of concrete),
  `ui._pack_art` (what the bundle holds), `ui._scorer_art` (a mark per scorer —
  a coin, an arrow, a times sign, a blade, a bolt, a mountain, a gravestone) and
  `ui._draw_structure_icon` (the fourteen). The letter is now only the fallback
  for a value with no art, so a save from an older build still draws, and
  `_scorer_art` returns None for NONE, START and FINISH on purpose: those three
  have faces of their own (a plain tile, a marble, a checkerboard).
* **The level's blocks are never the player's.** Its props and enemies are
  blocks, but nothing refunds them: the end-of-run sweep skips them
  (`Game._cycle_deck`), `_unplace_block` refuses them, and a player's own
  key/portal pair cannot delete the level's (`_delete_paired_key` /
  `_delete_paired_portal`). Each new level builds its own anyway.
* **The board starts partly locked, and the player opens it.** A brand-new
  game unlocks only a centered `BOARD_START_WIDTH x BOARD_START_HEIGHT` region;
  the ring around it is solid wall. Clicking a locked square spends a Board Unit
  to unlock it — that click always means "unlock", whatever is in hand — and
  Board Units come from the bar's BOARD UNIT button (always buyable, `$8`, or
  `$5` with the Mineshaft card), the Drill and Conquistador payoffs and the
  Packed scorer. Unlocking a square re-lays the layout, so a stashed item takes
  it.
* **The board can fill up, and nothing is lost.** `Toolbox.stash` holds the
  items the board had no room for as they were gained; they are still owned and
  still sellable, and they take a square as soon as one opens up. (An item the
  player simply has not drawn is not stashed: it is in the deck.)
* **A placed block and its inventory item are one existence.** Placing does
  not consume the item: it records the square its block stands on
  (`BlockItem.placed_cell`), and the block points back at it
  (`Block.source_item`). `Game.item_cell` reads that square, so the item answers
  only where the block actually stands — never on the square it was laid out (or
  created) in. Clicking that square picks the block up to move it, and erasing
  the block makes the same item placeable again — one item can never field two
  blocks. Anything that removes the item (selling, banking, sacrificing,
  disassembling) takes its block off the board with it.
* **Only blocks are physical.** The marble never meets anything that is not a
  `Block`: the simulation reads `Game.board_blocks()`, not `grid.values()`, so
  a card or a component lying on a square is scenery. A shop offer is scenery
  too, even when it is a BLOCK offer (`Game.in_hand_is_block`): it is moved
  around the board and bought by right-click, never built into a block, and the
  keys that spend cash on a block (sell, disassemble, upgrade) refuse it.
* **Two flush blocks make one surface.** A marble near the seam between two
  blocks used to touch the *corner* of one of them, whose closest-point normal
  points diagonally into the block next door — a phantom corner that threw it
  off sideways. A corner normal whose face is buried under a neighbouring solid
  block falls back to the face that really is exposed
  (`PhysicsEngine._unbury_normal`), one surface is answered once even when
  several blocks make it up (`SAME_SURFACE_DOT`), and one push separates the
  marble from it, so there is no sideways kick, no double bounce and no pop at
  a seam. A contact with no offset at all (centre exactly on a corner) is pushed
  back the way the marble came (`_arrival_direction`).
* **Every item is its own switch.** `Game._toggle_item_selection` is the only
  way an item is selected: a click turns that item's switch ON, another click
  turns it OFF, and no click ever changes any other item's switch — so the
  player can have any number of items on at once. Everything switched on wears
  the green frame (plus a white inner frame on the ACTOR, see `ui.draw`) —
  blocks, components, cards, actions and tokens alike. The selection is a queue
  (`Game.actor` / `Game.selected_targets`): the FIRST item switched on is the
  actor — the one `B` sells, `D` upgrades, `G` banks and `S` uses — and every
  item switched on after it is one of its targets. A click on a square acts with
  the actor: a block is built there, anything else is moved there.
  * An action is used with `S` on the items selected behind it
    (`Game._apply_action`). It needs exactly the number of targets it asks for
    (`Game.required_targets`: one for a targeted action, none for the rest), so
    the wrong number of them makes nothing happen and the action is not spent.
  * A block has one shape and one scorer, so the newest switched-on piece of
    each kind is the one assembled (`Game._sync_assigned_parts`) — but both keep
    their switches, and turning the newest off hands the slot back.
  * A block wearing the **Wasteful** effect is USED with `S` when one other item
    is selected behind it: both are thrown away for good and one random item is
    drawn from the deck onto the block's square (`Game._use_wasteful`). With no
    target the block keeps its ordinary `S` meaning, and with two targets (or an
    empty deck) nothing happens at all.
  * Putting an item down, selling, banking, erasing, destroying or consuming it
    turns that one switch off (`_forget_item`); the rest stay as they were.
  * A click that is not on an item — the void, the bar, a locked square even
    when a Board Unit is owned — is the single "turn everything off" gesture.
* **Two copies are two items.** A purchase hands over the OFFER ITSELF (see
  above), so a second copy of the same kind is a second offer on a later shelf —
  a separate item with its own square. Anything that DUPLICATES an offer instead
  (`items.owned_copy`) makes an independent item, and one object is never
  owned twice (`Game.owns_item`, `Toolbox.add`). A placed block and its
  item are the one exception, and they are one existence:
  whatever removes the block for good — selling it, disassembling it, sacrificing
  it to Spirit, a Bomb, Sharp or Satanic destroying it — removes the item too
  (`Game._release_block_item`), so no ghost is left behind to be fielded a
  second time. Counts that read both the board and the toolbox skip an item
  that is standing as its block, so one existence is never counted twice.
* **Player data is local**: `profiles/<name>/…` (saves, `collection.json`,
  `achievements.json`, `metagame.json`), with the active profile name in
  `profiles/current.txt`. The tests redirect all of it into a temp folder.

## Tests

```powershell
python -m unittest discover -s tests -q        # 1959 tests, ~100 s
python -m unittest discover -s tests -k concert -q     # just one topic
```

They run headless (`SDL_VIDEODRIVER=dummy`) against a real `Game`, asserting on
behaviour, on the pixels a screen draws, and on the numbers the simulation
produces.

| Test file | Covers |
|---|---|
| `game_test_case.py` | The shared `GameTestCase`: the per-test `Game`, its temp player-data paths, and every helper (clicking, key presses, placing blocks, flying a marble into a block, pixel probes). |
| `test_ui.py` | The HUD, sidebar, panels, info boxes, fonts, popups, particles and the CRT filter. |
| `test_shop.py` | The shop, prices and rarity, buying and selling (on a shelf a test stocks by hand, since the game deals nothing now), assembly/disassembly, the economy. |
| `test_deck.py` | The deck, the hand drawn from it, buying into the deck and the DECK overlay. |
| `test_structures.py` | Structures and the tools that open them (the pit, crystal pool, mirror and golem, plus the ten PACK structures: quarry, shrine, vault, workbench, depot, library, cabinet, mint, rift and shed; shovel, flashlight, screwdriver, hammer, brick, match), the wrong-verb refusals, one structure per pack handing over that pack's goods (so every item in the game is obtainable), the golem's combining and the tiers it leaves (golden, then diamond at 4x; two Lanterns make one that draws four and two Concretes one that pays 60 — every item carries an amount), a tool that is spent by being used, the run's energy bar, and the Cleansing action. |
| `test_structure_tools.py` | The bugs the player reported, pinned down: a tool is never knocked into the deck by another item being placed on it (moving onto an occupied square swaps, building a block on a tool seats it, a load that re-places a structure under one seats it, a round of moves leaves the deck empty), an opened structure stays opened through a board edit, R, T, an unlock and a save round trip (and the next level or a new game gets its own four), pressing T leaves the level's props, structures, cast and the player's own squares exactly where they were, opening one hands the reward its square, marks that square spent and cannot be opened twice, opening every one never costs the player a tool, and every structure draws its own icon inside its tile (14 distinct tiles, art never falling back to the glyph). |
| `test_keywords.py` | The item vocabulary (`components.Keyword`): every word has a name and a meaning, keywords are derived from what an item is rather than stored, a multi-verb tool uses the verb its structure answers, a consumed tool leaves play and draws its refill, the unplayable Concrete carries and pays its amount (30 chips, or whatever a golem folded into it) and its description reads that number out, and a revealed pit hands over a Tool Pack. |
| `test_groups.py` | The item groups (`components.Group`): every group is named, explained and coloured, every item kind lands in exactly one group (a card, an action and a tool in the one Cards family), a block on the board reads as a block, a foe and a prop have their own groups, every description carries the group row, the info box draws that row as a highlighted box directly under the item's name, and the deck overlay lists the collection sorted into families. |
| `test_collection.py` | The codex and the icons: every kind of item has a section (tools, passives and structures included), every value of every table is listed once, every entry names and describes its item, and each is revealed by the thing that hands it over (a kept tool or passive, an opened structure, the always-known starters) and survives a reload; every cell says which group its entry is in — a box in the cell's corner carrying the family's name in its colour and nothing else, the one Cards family for cards, match groups, actions and tools, a family of its own for a trial; and every tool, passive, pack, scorer and structure draws a picture of its own — no two alike, none blank, with the letter only as the fallback for a value with no art. |
| `test_tools.py` | The six tools beyond the starters: their catalogue rows (verbs, energy, whether they are spent, prices, pack options, amounts), and each one played — a glowstick opening for no energy and burning out, a pry bar digging and breaking and never being spent (and refusing at one energy), a multi-tool opening any of the four door kinds for the whole bar, a chisel pushing the reward one pack size up (two for a golem-folded one), a gilding cloth handing the reward over golden (every option of a pack), and a wrecking bar taking the breakable neighbours with it while leaving a reveal-only one standing (and spending what it sweeps for the level visit). Plus the golem folding two chisels but not two glowsticks, the sidebar's Magnitude and Sweep rows, the collection entries, the icons and the amount riding through a save. |
| `test_modifiers.py` | The modifier system (`components.Modifier`): every kind is named, explained and coloured, stacks are counted the way they are read (a permanent one never runs out), and the states the game already had are now modifiers — a golden and a diamond item are a `Quality` seen through `Modifier`, a token's runs left are its `token` stacks (and survive a save), one `retriggerable` is one extra trigger, `v2` is the action's version, and a switched-off card is `disabled`; plus the five new tools: a drill opening any door for nothing and packing Dirt into the deck, a pickaxe digging and striking a temporary Spark, a spark revealing for nothing and burning out, a vodka putting 3 stacks of *forgotten* on a card and being spent, and the clocks — a forgotten card is not drawn until its stacks wear off, and a temporary item is destroyed when the run is committed. |
| `test_wasteful.py` | The Wasteful effect: its catalogue row, using it with one other item to throw both away for a draw from the deck, and its refusals. |
| `test_deck_cards.py` | The four newest cards. Eyeball: its row (1 energy, one card), using it opening the deck as a PICKER (through the real keys and mouse too), the card you click being the one drawn, the action and its energy spent exactly once, a backed-out look costing nothing, its refusals (no energy, no card in the deck, a tool clicked instead of a card), and a folded one taking two picks. Deep Pockets: a pack on the board for a structure pulled down (its square marked spent, the wrecked structure NOT revealed, and no structure dealt back onto that square), a pack still made with nothing left to pull down, and out of energy refused. Nasty Cocktail: nothing for a plain one (kept, not wasted), one energy a modifier kind (stacks are not kinds, v2 counts), double for a folded one, and no energy of its own. Smelly Socks: its two-currency row, its chips and mult at the start of every run (twice for two copies, nothing when the trial cuts it), and its cost — a card drawn with it going back into the DECK rather than being destroyed, ready to be drawn again, and never taking a part or a tool. |
| `test_reroll.py` | The Reroll card and the mechanics that deal it: its row (0 energy, one structure, its line stating its own draw), structures being a target for it and for no other action, the structure turning over ON ITS SQUARE (keeping its plan entry and its level flag, spending nothing), the card discarding itself and drawing into the square it gave up (its magnitude doubling for a folded one, and an empty deck still rerolling), its refusals (no structure, nothing left to turn it into), the reroll being written into the level's plan so a fresh layout, an extra deal or a save round trip cannot undo it, Fresh dealing a card per hit (a block or a card), Brainstorm dealing 2 (4 upgraded), the dealt card reaching the codex, a Reroll growing the Tesseract, and the retry ledger — a retried or restarted run takes back the cards it dealt, a used one is not un-spent, and a CONTINUE (or a bought Brainstorm) keeps them. |
| `test_abilities.py` | The `Ability` table: every row has a name, needs, cost and a real handler; an item's ability is derived from what it is; `S` dispatches through it (and falls through to assembly when nothing can fire); the sidebar prints the same contract. |
| `test_toolbox.py` | The inventory: selection, assignment and clicks on the board. |
| `test_board_items.py` | Only blocks being physical, selecting items on the board, assembling there, selling a card from its square, and the save round-trip. |
| `test_inventory.py` | The board as the inventory: the layout, one square per item, the stash when the board is full, moving items, and the card cap. |
| `test_cards.py` | Cards: whole cards, composed halves, the card area, and the named cards' measured end-of-run payouts (the Trash Can counts what the run discarded). |
| `test_scorers.py` | Each scorer's payoff, description and shop availability. |
| `test_blocks.py` | Blocks: shapes, effects, triggers, portals, keys and locks, borders, and placing one with `_place_block_at`. |
| `test_runs.py` | A run's life: scoring, cash, marbles, trails, retries and the run cycle. |
| `test_run_start.py` | When a run starts and when its level is loaded: a marble exists only while the run it plays is in flight (T releases one, R / a retry / an edit takes it away), a brand-new game already has its level, and starting or restarting a run never moves the level's props, structures or cast (and puts a damaged enemy back at full health on its own square). |
| `test_actions.py` | The one-shot actions (Death, Recognition, Deja Vu, Anointment, ...), including the Lantern: a target-free action whose magnitude is the items it draws, which discards itself when used. |
| `test_trials.py` | Trials. |
| `test_tokens.py` | Spirit tokens kept from sacrificed blocks. |
| `test_collision_behaviors.py` | The physics: what the marble actually does against every shape and effect. |
| `test_save_profiles.py` | Saving/loading and the profile + player-data-path rules: every kind of item (block, card, action, structure, tool, passive, resource, pack) round-trips as itself, a passive in the hand survives a save, and the slot, autosave and profile flows. |
| `test_board_units.py` | Board units, locked squares and the locked-board rules. |
| `test_board_camera.py` | The infinite board: screen/square conversion, dragging the view, squares far outside the window, and the top bar's furniture. |
| `test_item_copies.py` | Several copies of one item: copies are items of their own, one object is never owned twice, a block and its item are one existence, and portal/key groups share their count. |
| `test_levels.py` | The levels: their shapes, props, buried enemies, per-marble score and outcome — and the health budget, where a level's enemies add up to exactly the score its run used to require (split by kind, doubled by Sky High, zeroed by Grace v2) and every run puts out four structures. |

A split module only needs:

```python
from tests.game_test_case import *

class MyTests(GameTestCase):
    def test_something(self):
        self.assertEqual(self.game.score_chips, 0)
```
