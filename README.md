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

## Controls

| Input | What it does |
|---|---|
| Left-click a toolbox item | Select it (a block is armed for placement, a component goes to the assembler) |
| Left-drag on the board | Place the armed block — it costs the item's price |
| Right-click a block | Erase it (it goes back to the toolbox as a block) |
| Hover anything | The sidebar describes it: shape, effects, scorer, trigger limit |
| **A** | Rotate the block being placed by 90° |
| **S** | The context action: apply the selected action, split a card, build a card, assemble the assigned parts, disassemble a block — with nothing selected it builds a plain wall |
| **B** | Sell the selected item |
| **D** | Pay cash to raise the selected block's trigger limit |
| **T** | Start a fresh run (rolls a new trial) |
| **R** | Restart the current run, keeping its trial |
| **V** | Send every placed block back to the toolbox |
| **SPACE** | Pause |
| **Y** | Continue after a run (bank the cash, advance the round) |
| Any other key after a run | Retry: undo the run |
| **P** | Save to the active slot |
| **F2** | Toggle the CRT screen filter |
| **ESC** | Back out of menus |

## How the code is laid out

| File | Role |
|---|---|
| `components.py` | **The source of truth for game data.** Enums for shapes, effects, scorers, conditions, cards, actions, trials and final bosses, plus their `NAMES` / `DESCRIPTIONS` / `PRICES` / `COLORS` / `GLYPHS` / `ORDER` tables, the price helpers, and the magnitude roll (see `MAGNITUDE_SPREAD`). |
| `main.py` | Every constant and all the logic: `Game` (run cycle, shop, card area, toolbox, input, saves), `Block`, `BlockItem`, `Marble`, `ScorerToken`, the generic card effects in `cards.py`'s hooks… **It contains zero drawing code.** |
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
* **`ui.py` never includes logic, `main.py` never draws.** Keep it that way.
* **Fonts are built once**, in `Game.__init__` (see `FONT_SIZES`), and handed to
  the UI with `ui.bind_fonts` — nothing anywhere else builds a font.
* **Magnitudes** (a scorer's amount, a piston's speed) are rolled around their
  average with a continuous truncated Cauchy whose tail is set by
  `components.MAGNITUDE_SPREAD` (4 = a deliberately long tail). A roll changes
  what an item DOES, never what it costs.
* **Player data is local**: `profiles/<name>/…` (saves, `collection.json`,
  `achievements.json`, `metagame.json`), with the active profile name in
  `profiles/current.txt`. The tests redirect all of it into a temp folder.

## Tests

```powershell
python -m unittest discover -s tests -q        # 1084 tests, ~30 s
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
| `test_cards.py` | Cards: conditions, whole cards, composed halves, the card area. |
| `test_scorers.py` | Each scorer's payoff, description and shop availability. |
| `test_blocks.py` | Blocks: shapes, effects, triggers, portals, keys and locks, borders, and placing one with `_place_block_at`. |
| `test_runs.py` | A run's life: scoring, cash, marbles, trails, retries and the run cycle. |
| `test_actions.py` | The one-shot actions (Death, Recognition, Deja Vu, Anointment, …). |
| `test_trials.py` | Trials and final bosses. |
| `test_tokens.py` | Spirit tokens kept from sacrificed blocks. |
| `test_collision_behaviors.py` | The physics: what the marble actually does against every shape and effect. |
| `test_save_profiles.py` | Saving/loading and the profile + player-data-path rules. |
| `test_board_units.py` | Board units, locked squares and the locked-board rules. |

A split module only needs:

```python
from tests.game_test_case import *

class MyTests(GameTestCase):
    def test_something(self):
        self.assertEqual(self.game.score_chips, 0)
```
