# Marblatro

A physics-driven deck-builder: you build a board out of blocks (each one a
**shape** × **effect** × **scorer**), release a marble at the Start block, and
watch it score as it falls, bounces and triggers everything it touches. Between
runs the shop sells components, pre-built blocks, cards and one-shot actions,
and every run plays under exactly one **trial**.

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

The shop has no box of its own: every offer is a **locked item lying on the
board**, drawn with a padlock and chain until it is bought. The price is shown
only on hover, the offer can be picked up and moved like any other item, and a
right-click unlocks it.

Everything the player owns lives in their **deck**, and the board shows only the
**hand** drawn from it: `DECK_DRAW_SIZE` (4) random items, dealt onto the board
whenever a run is committed. The two role blocks — the **Start** and **Finish**
blocks — are never dealt; they stay on the board so a run can always be built.
The **DECK** button in the bar opens an overlay listing the whole deck, with the
items currently drawn framed green.

## Controls

The board is the hand: the four items drawn from the deck lie on board squares,
and the rest of the deck waits behind them.

| Input | What it does |
|---|---|
| Click an item on the board | Flip its switch — every item is selected by the same toggle: on turns it green, a second click turns it off, and no other item changes. Any number can be on at once. **The first item switched on is the actor** — the one that gets used up — and every item switched on after it is one of its targets |
| Click anything that is not an item | Turn every switch off: the void around the board, a locked square (even with a Board Unit in hand), the bar |
| Left-click an empty unlocked square | Put the selected item down: a block is built on that square, anything else — a component, a card, an action — is moved there |
| Drag from an empty square | Grab the board and drag it: the board (and the background pattern behind it) moves with the cursor, so you can travel anywhere on the infinite board. A press that never moves is still a click |
| Right-click a shop offer | Buy it: the item is unlocked on the board at once, so it can be used this run, and the offer stays on sale so the same slot can be bought again; a pack opens its overlay |
| Middle-click a shop offer | Hoard: hold that offer in place through the next refresh (one offer per copy of the card) |
| Right-click anywhere else | Nothing |
| Hover anything | The sidebar describes it: shape, effects, scorer, trigger limit |
| **A** | Rotate the block being placed by 90° |
| **S** | The context action: use the selected action on its targets (nothing happens unless it has exactly the number of targets it needs), assemble the selected parts into a block, disassemble a selected block — with nothing selected it builds a plain wall |
| **B** | Sell the selected item (the actor) |
| **D** | Pay cash to raise the selected block's trigger limit |
| **G** | Odyssey: put the selected block/component away for the run |
| Click a locked square with nothing selected | Unlock it if you own a Board Unit (the marble can travel there, and items can be laid out on it); without one, a hint to buy one |
| Right-click the Board Unit offer | Buy one Board Unit ($8), then click a locked square to open it |
| Click the DECK button in the bar | Open the deck overlay: every item you own, the ones drawn onto the board framed green. Any click (or Esc) closes it |
| **T** | Start a fresh run (rolls a new trial) |
| **R** | Restart the current run, keeping its trial |
| **V** | Turn every placed block back into a loose block |
| **SPACE** | Pause |
| **Y** | Continue after a run (bank the cash, advance the round) |
| Any other key after a run | Retry: undo the run |
| **P** | Save to the active slot |
| **F2** | Toggle the CRT screen filter |
| **ESC** | Back out of menus |

## How the code is laid out

| File | Role |
|---|---|
| `components.py` | **The source of truth for game data.** Enums for shapes, effects, scorers, conditions, cards, actions and trials, plus their `NAMES` / `DESCRIPTIONS` / `PRICES` / `COLORS` / `GLYPHS` / `ORDER` tables, the price helpers, and the magnitude roll (see `MAGNITUDE_SPREAD`). |
| `main.py` | The **entry point** and the game's single namespace. The pieces below are re-exported from here, because the code and the tests refer to them as `main.Block`, `main.Game`, `main.SHOP_COORDS`, …; it also wires the drawing helpers onto the classes (`Game.draw = ui.draw`) and runs `python main.py`. **It contains zero drawing code and almost no logic.** |
| `config.py` | Every tunable: the colours, the layout geometry (every rect and panel coordinate), the prices, and the score scales. |
| `rolling.py` | The rolls and prices an item is built and valued with: magnitudes, the cards and match groups the shop offers, the key/portal numbers, resale prices. |
| `blocks.py` | `Block`: one square of the board, with its shape, effects, scorer and rolled magnitudes. |
| `items.py` | What the player owns: `BlockItem`, `CardItem`, `ActionItem`, `ItemPack`, `ResourceOption`, `ScorerToken`, `CashBreakdown`. |
| `shop.py` | The `Shop`: its shelf of offers — every one of them an item lying on the board — and the logical cells they are dealt from. |
| `toolbox.py` | `Toolbox`: the player's portable items (loose blocks and components). Ownership only — where an item stands is the game's business, and an item with no square is in the deck (see `game_deck.py`). |
| `game_deck.py` | The deck: which items are drawn into the hand, the draw at the end of a run, and returning a purchase to the deck. |
| `marble.py` | `Marble`: the ball's physics state and its trail. |
| `game.py` | `Game`, assembled from the feature mixins below — one object, but its ~300 methods live in the module that owns their subject. |
| `game_*.py` | The mixins: `game_core` (setup, locked squares, profiles), `game_input` (the event loop), `game_build` (placing and assembling), `game_store` (purchases and packs), `game_slots` (cards, actions, slots), `game_actions` (the one-shot actions), `game_inventory` (Spirit tokens, banking and selling), `game_economy` (money and resource points), `game_describe` (info-box text), `game_frame` (update, autosave, achievements), `game_runs` (runs, trials, score, gondolas), `game_contact` (what touching a block does), `game_payoffs` (xMult, Procrastination, block scoring), `game_ending` (cash out, retry, the main loop). |
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
  what an item DOES, never what it costs.
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
  offers are laid out beside the hand.
* **Buying unlocks on the spot.** A shop purchase is laid out on the board at
  once (`Game._unlock_purchase`), so it can be used during the run being built;
  the shelf keeps its own offer, so the same slot can be bought again and again,
  each purchase a separate copy (`items.owned_copy`, which never inherits the
  offer's square). Anything else GAINED during play (an assembled block, the
  parts of a disassembly, a pack's pick, a reward) joins the hand the same way.
  The next deck cycle takes all of it back into the deck with everything else.
* **The board starts partly locked, and the player opens it.** A brand-new
  game unlocks only a centered `BOARD_START_WIDTH x BOARD_START_HEIGHT` region;
  the ring around it is solid wall. Clicking a locked square spends a Board Unit
  to unlock it — that click always means "unlock", whatever is in hand — and
  Board Units come from the Board Unit offer on the shelf (bought by
  right-clicking it), the Drill and Conquistador payoffs and the Packed scorer.
  Unlocking a square re-lays the layout, so a stashed item takes it.
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
  * Putting an item down, selling, banking, erasing, destroying or consuming it
    turns that one switch off (`_forget_item`); the rest stay as they were.
  * A click that is not on an item — the void, the bar, a locked square even
    when a Board Unit is owned — is the single "turn everything off" gesture.
* **Two copies are two items.** The shop keeps selling a component or block
  slot after it is bought (its price just rises), so a purchase hands over a
  fresh copy of the offer (`items.owned_copy`) and the shelf keeps its own
  object; one object is never owned twice (`Game.owns_item`, `Toolbox.add`).
  A placed block and its item are the one exception, and they are one existence:
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
python -m unittest discover -s tests -q        # 1580 tests, ~37 s
python -m unittest discover -s tests -k concert -q     # just one topic
```

They run headless (`SDL_VIDEODRIVER=dummy`) against a real `Game`, asserting on
behaviour, on the pixels a screen draws, and on the numbers the simulation
produces.

| Test file | Covers |
|---|---|
| `game_test_case.py` | The shared `GameTestCase`: the per-test `Game`, its temp player-data paths, and every helper (clicking, key presses, placing blocks, flying a marble into a block, pixel probes). |
| `test_ui.py` | The HUD, sidebar, panels, info boxes, fonts, popups, particles and the CRT filter. |
| `test_shop.py` | The shop, prices and rarity, buying, selling, assembly/disassembly, the economy. |
| `test_deck.py` | The deck, the hand drawn from it, buying into the deck and the DECK overlay. |
| `test_toolbox.py` | The inventory: selection, assignment and clicks on the board. |
| `test_board_items.py` | Only blocks being physical, selecting items on the board, assembling there, selling a card from its square, and the save round-trip. |
| `test_inventory.py` | The board as the inventory: the layout, one square per item, the stash when the board is full, moving items, and the card cap. |
| `test_cards.py` | Cards: conditions, whole cards, composed halves, the card area. |
| `test_scorers.py` | Each scorer's payoff, description and shop availability. |
| `test_blocks.py` | Blocks: shapes, effects, triggers, portals, keys and locks, borders, and placing one with `_place_block_at`. |
| `test_runs.py` | A run's life: scoring, cash, marbles, trails, retries and the run cycle. |
| `test_actions.py` | The one-shot actions (Death, Recognition, Deja Vu, Anointment, …). |
| `test_trials.py` | Trials. |
| `test_tokens.py` | Spirit tokens kept from sacrificed blocks. |
| `test_collision_behaviors.py` | The physics: what the marble actually does against every shape and effect. |
| `test_save_profiles.py` | Saving/loading and the profile + player-data-path rules. |
| `test_board_units.py` | Board units, locked squares and the locked-board rules. |
| `test_board_camera.py` | The infinite board: screen/square conversion, dragging the view, squares far outside the window, and the top bar's furniture. |
| `test_item_copies.py` | Several copies of one item: copies are items of their own, one object is never owned twice, a block and its item are one existence, and portal/key groups share their count. |

A split module only needs:

```python
from tests.game_test_case import *

class MyTests(GameTestCase):
    def test_something(self):
        self.assertEqual(self.game.score_chips, 0)
```
