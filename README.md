# Marblatro

A physics-driven deck-builder: you build a board out of blocks (each one a
**shape** Ã— **effect** Ã— **scorer**), release a marble at the Start block, and
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

A **bar** along the top of the screen holds everything the game owns: the shop,
the score readout, the trial box, the run/round display and the MAIN MENU
button. The **board** fills the rest of the screen, and it is **infinitely
large** â€” a square is any integer coordinate, and the camera decides which part
of it you are looking at. Locked squares are not board at all: they wear the
background's own pattern, so the playable region reads as a platform floating in
the void.

## Controls

Every item the player owns lies on the board â€” the inventory panel, the card
tray and the action row are gone, and the board is the inventory.

| Input | What it does |
|---|---|
| Click an item on the board | Flip its switch â€” every item is selected by the same toggle: on turns it green, a second click turns it off, and no other item changes. Any number can be on at once. A block is picked up (or armed, if it is still a loose block), a component joins the next block, a card or an action is held to be moved |
| Left-click on the board | Put the selected item down: a block is built on that square, anything else â€” a component, a card, an action â€” is moved there |
| Drag from an empty square | Scroll the board: it follows the cursor, so you can travel anywhere on the infinite board. A press that never moves is still a click |
| Right-click a block | Erase it: the block becomes a loose block again, lying on the square it stood on |
| Right-click anything else | Nothing â€” the eraser is for blocks (use B to sell) |
| Hover anything | The sidebar describes it: shape, effects, scorer, trigger limit |
| **A** | Rotate the block being placed by 90Â° |
| **S** | The context action: use the selected action, assemble the selected parts into a block, disassemble a selected block â€” with nothing selected it builds a plain wall |
| **B** | Sell the selected item |
| **D** | Pay cash to raise the selected block's trigger limit |
| **G** | Odyssey: put the selected block/component away for the run |
| Click a locked square with a Board Unit in hand | Unlock it (the marble can travel there, and items can be laid out on it) |
| Click a locked square with no Board Unit | Nothing but a hint: buy one from the shop |
| Click the shop's Board Unit tile | Buy one Board Unit ($8) |
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
| `main.py` | The **entry point** and the game's single namespace. The pieces below are re-exported from here, because the code and the tests refer to them as `main.Block`, `main.Game`, `main.SHOP_COORDS`, â€¦; it also wires the drawing helpers onto the classes (`Game.draw = ui.draw`) and runs `python main.py`. **It contains zero drawing code and almost no logic.** |
| `config.py` | Every tunable: the colours, the layout geometry (every rect and panel coordinate), the prices, and the score scales. |
| `rolling.py` | The rolls and prices an item is built and valued with: magnitudes, the cards and match groups the shop offers, the key/portal numbers, resale prices. |
| `blocks.py` | `Block`: one square of the board, with its shape, effects, scorer and rolled magnitudes. |
| `items.py` | What the player owns: `BlockItem`, `CardItem`, `ActionItem`, `ItemPack`, `ResourceOption`, `ScorerToken`, `CashBreakdown`. |
| `shop.py` | The `Shop`: its shelf of offers, its packs and the cells it holds. |
| `toolbox.py` | `Toolbox`: the player's portable items (loose blocks and components). They lie on board squares â€” the board is the inventory â€” so this is only the ownership list the placement code reads. |
| `marble.py` | `Marble`: the ball's physics state and its trail. |
| `game.py` | `Game`, assembled from the feature mixins below â€” one object, but its ~300 methods live in the module that owns their subject. |
| `game_*.py` | The mixins: `game_core` (setup, locked squares, profiles), `game_input` (the event loop), `game_build` (placing and assembling), `game_store` (purchases and packs), `game_slots` (cards, actions, slots), `game_actions` (the one-shot actions), `game_inventory` (Spirit tokens, banking and selling), `game_economy` (money and resource points), `game_describe` (info-box text), `game_frame` (update, autosave, achievements), `game_runs` (runs, trials, score, gondolas), `game_contact` (what touching a block does), `game_payoffs` (xMult, Procrastination, block scoring), `game_ending` (cash out, retry, the main loop). |
| `ui.py` | **All drawing.** Screens (`draw`, `draw_title_screen`, `draw_collection`, â€¦), the board and marble rendering, the sidebar and every info box, the icon art, and the shared font table. Functions take the object they draw as their first argument; `main.py` keeps thin delegating wrappers (`Game.draw`, `Block.draw`, â€¦). |
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
  the UI with `ui.bind_fonts` â€” nothing anywhere else builds a font.
* **Magnitudes** (a scorer's amount, a piston's speed) are rolled around their
  average with a continuous truncated Cauchy whose tail is set by
  `components.MAGNITUDE_SPREAD` (4 = a deliberately long tail). A roll changes
  what an item DOES, never what it costs.
* **The board is infinite, and the camera is the window onto it.** A square is
  any pair of integers, so there is no edge, no `GRID_WIDTH` bound and nothing
  to fall off: `Game.cell_to_screen` / `screen_to_cell` convert between a square
  and the screen through `Game.camera`, and `Game.pan_board` scrolls the view
  (the flat `GRID_WIDTH x GRID_HEIGHT` count is only how many squares fit on
  screen at once). Dragging with the button down on board space that holds no
  item pans the board; a press that never moves is still a click.
* **Locked squares are the void, not board.** They are painted with the
  background's own pattern (the run's tessellation, or the flat background
  colour), so the playable region floats in it, and they are solid: only the
  FRONTIER of locked squares around the unlocked region needs a wall, because a
  marble can only reach a locked square through one (`Game._board_wall_blocks`).
  The marble's hard clamp is the unlocked region plus two squares, which leaves
  room for the Phase effect to carry it into a wall.
* **The board IS the inventory.** There is no inventory panel, card tray or
  action row: every owned item â€” a loose block (`BlockItem`), a component, a
  card, an action, a Spirit token â€” stands on a board square, and is drawn,
  clicked and selected there. `Game.ensure_board_cells` lays them out on
  UNLOCKED squares only (an item never stands on a locked one): an item keeps
  the square it claims, and a new one takes the first free unlocked square in
  reading order. A block that is placed owns its square and hides its item.
* **The board starts partly locked, and the player opens it.** A brand-new
  game unlocks only a centered `BOARD_START_WIDTH x BOARD_START_HEIGHT` region;
  the ring around it is solid wall. Clicking a locked square spends a Board Unit
  to unlock it â€” that click always means "unlock", whatever is in hand â€” and
  Board Units come from the shop tile, the Drill and Conquistador payoffs and
  the Packed scorer. Unlocking a square re-lays the layout, so a stashed item
  takes it.
* **The board can fill up, and nothing is lost.** `Toolbox.stash` holds the
  portable items the board has no square for; they are still owned and still
  sellable, and they take a square as soon as one opens up.
* **A placed block and its inventory item are one existence.** Placing does
  not consume the item: it records the square its block stands on
  (`BlockItem.placed_cell`), and the block points back at it
  (`Block.source_item`). `Game.item_cell` reads that square, so the item answers
  only where the block actually stands â€” never on the square it was laid out (or
  created) in. Clicking that square picks the block up to move it, and erasing
  the block makes the same item placeable again â€” one item can never field two
  blocks. Anything that removes the item (selling, banking, sacrificing,
  disassembling) takes its block off the board with it.
* **Only blocks are physical.** The marble never meets anything that is not a
  `Block`: the simulation reads `Game.board_blocks()`, not `grid.values()`, so
  a card or a component lying on a square is scenery.
* **Every item is its own switch.** `Game._toggle_item_selection` is the only
  way an item is selected: a click turns that item's switch ON, another click
  turns it OFF, and no click ever changes any other item's switch â€” so the
  player can have any number of items on at once. Everything switched on wears
  the green frame (thick for the one in hand, see `ui.draw`) â€” blocks,
  components, cards, actions and tokens alike. The last item switched on is the
  one in hand, which is also the one a click on a square acts with: a block is
  built there, anything else is moved there. Choosing what `_select_in_hand`
  does for each kind is what keeps `B` (sell), `S` (use or assemble), `D`
  (upgrade) and `G` (bank) working off one selection.
  * An armed action does not block anything: a click on a block or card both
    flips that item's switch and aims the action at it (the gold outline).
  * A block has one shape and one scorer, so the newest switched-on piece of
    each kind is the one assembled â€” but both keep their switches, and turning
    the newest off hands the slot back to the one before it
    (`_reassign_part_of_kind`).
  * Putting an item down, selling, banking, erasing, destroying or consuming it
    turns that one switch off (`_forget_item`); the rest stay as they were.
  * A click on empty space is the single "turn everything off" gesture.
* **Player data is local**: `profiles/<name>/â€¦` (saves, `collection.json`,
  `achievements.json`, `metagame.json`), with the active profile name in
  `profiles/current.txt`. The tests redirect all of it into a temp folder.

## Tests

```powershell
python -m unittest discover -s tests -q        # 1532 tests, ~35 s
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
| `test_toolbox.py` | The inventory: selection, assignment and clicks on the board. |
| `test_board_items.py` | Only blocks being physical, selecting items on the board, assembling there, selling a card from its square, and the save round-trip. |
| `test_inventory.py` | The board as the inventory: the layout, one square per item, the stash when the board is full, moving items, and the card cap. |
| `test_cards.py` | Cards: conditions, whole cards, composed halves, the card area. |
| `test_scorers.py` | Each scorer's payoff, description and shop availability. |
| `test_blocks.py` | Blocks: shapes, effects, triggers, portals, keys and locks, borders, and placing one with `_place_block_at`. |
| `test_runs.py` | A run's life: scoring, cash, marbles, trails, retries and the run cycle. |
| `test_actions.py` | The one-shot actions (Death, Recognition, Deja Vu, Anointment, â€¦). |
| `test_trials.py` | Trials. |
| `test_tokens.py` | Spirit tokens kept from sacrificed blocks. |
| `test_collision_behaviors.py` | The physics: what the marble actually does against every shape and effect. |
| `test_save_profiles.py` | Saving/loading and the profile + player-data-path rules. |
| `test_board_units.py` | Board units, locked squares and the locked-board rules. |
| `test_board_camera.py` | The infinite board: screen/square conversion, dragging the view, squares far outside the window, and the top bar's furniture. |

A split module only needs:

```python
from tests.game_test_case import *

class MyTests(GameTestCase):
    def test_something(self):
        self.assertEqual(self.game.score_chips, 0)
```
