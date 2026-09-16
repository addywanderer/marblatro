"""Synthesized sound effects for Marblatro.

Generates the game's sound effects at import time as ``pygame.mixer.Sound``
objects: a coin clink when buying, a mechanical whir + crunch when assembling
or disassembling a block, a plop when placing a block, a rising fanfare when a
run starts, and a falling pair of tones when a run is reset. The effects are
tiny waveforms synthesized with numpy, so no audio asset files are needed.

Every effect and scorer type also has its own short sound, built from the
component's stable enum id and synthesized on first use (see ``play_effect`` /
``play_scorer``), so the player can hear what the marble just hit.

If the mixer can't start (no audio device, e.g. under a headless test driver),
every sound is ``None`` and the play helpers are silent no-ops — the game
never crashes without audio.
"""

import numpy as np
import pygame

from components import Effect, Scorer

SAMPLE_RATE = 22050  # fallback sample rate when the mixer isn't already running

# The mixer's actual settings (filled in by _init_mixer), so the synthesized
# waveforms always match whatever format pygame.init() left the mixer in.
_RATE = SAMPLE_RATE
_CHANNELS = 1


def _init_mixer():
    """Start the pygame mixer if it isn't already; False when no audio device."""
    global _RATE, _CHANNELS
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=256)
        _RATE, _format, _CHANNELS = pygame.mixer.get_init()
        return True
    except pygame.error:
        return False


def _tone(freq, duration, volume=0.5, decay=10.0, slide=0.0):
    """A sine tone with exponential decay and an optional linear freq slide (Hz/s)."""
    n = int(_RATE * duration)
    t = np.linspace(0.0, duration, n, endpoint=False)
    phase = 2 * np.pi * (freq * t + 0.5 * slide * t * t)
    return np.sin(phase) * np.exp(-decay * t) * volume


def _noise(duration, volume=0.3, decay=12.0):
    """A burst of white noise with exponential decay."""
    n = int(_RATE * duration)
    t = np.linspace(0.0, duration, n, endpoint=False)
    return np.random.uniform(-1.0, 1.0, n) * np.exp(-decay * t) * volume


def _mix(*layers):
    """Sum (wave, start_time) layers into one mono float sample buffer."""
    duration = max((offset + len(wave) / _RATE) for wave, offset in layers)
    n = int(_RATE * duration) + 1
    buf = np.zeros(n)
    for wave, offset in layers:
        start = int(offset * _RATE)
        end = min(start + len(wave), n)
        if end > start:
            buf[start:end] += wave[: end - start]
    return buf


def _build(wave):
    """Convert a float sample buffer into a Sound matching the mixer format."""
    wave = np.clip(wave, -1.0, 1.0)
    data = (wave * 32767).astype(np.int16)
    data = data[:, None]
    if _CHANNELS == 2:
        data = np.repeat(data, 2, axis=1)
    return pygame.sndarray.make_sound(data)


def _coin_wave():
    """Two bright, quick dings like coins knocking together."""
    return _mix(
        (_tone(2600, 0.10, volume=0.6, decay=38.0), 0.00),
        (_tone(3600, 0.09, volume=0.45, decay=42.0), 0.05),
    )


def _mech_wave():
    """A mechanical whir (noise) with a low crunch (decaying low tones)."""
    return _mix(
        (_noise(0.20, volume=0.5, decay=9.0), 0.00),    # the whir
        (_tone(100, 0.24, volume=0.7, decay=6.0), 0.02),  # low crunch thud
        (_tone(220, 0.12, volume=0.5, decay=14.0), 0.08),
        (_noise(0.06, volume=0.6, decay=30.0), 0.13),   # crunch crackle
    )


def _plop_wave():
    """A quick downward pitch drop — a soft plop."""
    return _mix(
        (_tone(420, 0.18, volume=0.6, decay=7.0, slide=-1600.0), 0.0),
    )


def _run_start_wave():
    """A bright three-note rise: a run is starting."""
    return _mix(
        (_noise(0.03, volume=0.2, decay=40.0), 0.00),
        (_tone(330, 0.12, volume=0.45, decay=14.0), 0.00),
        (_tone(440, 0.12, volume=0.45, decay=14.0), 0.07),
        (_tone(587, 0.26, volume=0.5, decay=9.0), 0.14),
    )


def _reset_wave():
    """A short falling pair of tones: the run is being reset."""
    return _mix(
        (_noise(0.04, volume=0.22, decay=28.0), 0.00),
        (_tone(520, 0.10, volume=0.45, decay=20.0), 0.00),
        (_tone(300, 0.18, volume=0.45, decay=13.0), 0.06),
    )


# --- Per-effect impact sounds -----------------------------------------------
# Effects are physical, so they sound like impacts: a noise transient for the
# moment of contact plus a body tone. The effects with a strong character get a
# hand-made waveform; every other one falls back to a parametric thump whose
# pitch, decay and tail come from the effect's id, so no effect is ever silent.
def _tick(duration, volume, decay):
    """A noise transient: the attack of an impact."""
    return _noise(duration, volume=volume, decay=decay)


def _bouncy_wave():
    """A boing: a springy upward bend with a second, smaller bounce."""
    return _mix(
        (_tick(0.012, 0.3, 60.0), 0.00),
        (_tone(300, 0.16, volume=0.5, decay=9.0, slide=900.0), 0.00),
        (_tone(520, 0.10, volume=0.28, decay=16.0, slide=700.0), 0.07),
    )


def _sticky_wave():
    """A squelch: a muffled noise swell with a falling low tone."""
    return _mix(
        (_noise(0.16, volume=0.4, decay=14.0), 0.00),
        (_tone(150, 0.18, volume=0.45, decay=11.0, slide=-260.0), 0.01),
    )


def _black_hole_wave():
    """A suck: a deep tone falling away under a soft noise tail."""
    return _mix(
        (_tone(220, 0.30, volume=0.5, decay=8.0, slide=-420.0), 0.0),
        (_noise(0.22, volume=0.18, decay=12.0), 0.0),
    )


def _repulsor_wave():
    """A shove: the black hole's suck played the other way — rising and short."""
    return _mix(
        (_noise(0.10, volume=0.22, decay=20.0), 0.0),
        (_tone(110, 0.22, volume=0.5, decay=9.0, slide=520.0), 0.0),
    )


def _portal_wave():
    """A zap: a very fast rising tone with a bright shimmer on top."""
    return _mix(
        (_tone(420, 0.20, volume=0.4, decay=12.0, slide=2600.0), 0.00),
        (_tone(1400, 0.10, volume=0.2, decay=22.0), 0.02),
    )


def _conveyor_wave():
    """A belt: a short low motor rumble with its rhythmic tick."""
    return _mix(
        (_tone(90, 0.22, volume=0.4, decay=7.0), 0.00),
        (_tone(180, 0.20, volume=0.22, decay=9.0), 0.01),
        (_tick(0.02, 0.35, 40.0), 0.02),
        (_tick(0.02, 0.3, 40.0), 0.10),
    )


def _zipper_wave():
    """A zip: a burst of evenly spaced ticks, like the gate's teeth."""
    return _mix(*[(_tick(0.012, 0.4, 55.0), i * 0.022) for i in range(7)])


def _phase_wave():
    """A shimmer: thin high tones beating against each other, then a whisper."""
    return _mix(
        (_tone(1200, 0.26, volume=0.22, decay=9.0), 0.00),
        (_tone(1500, 0.26, volume=0.20, decay=9.0), 0.00),
        (_tone(2400, 0.16, volume=0.12, decay=14.0), 0.02),
    )


def _splitter_wave():
    """A split: one click answered by a second, higher one."""
    return _mix(
        (_tick(0.02, 0.45, 45.0), 0.000),
        (_tone(700, 0.08, volume=0.3, decay=26.0), 0.005),
        (_tick(0.02, 0.40, 45.0), 0.060),
        (_tone(1000, 0.08, volume=0.3, decay=26.0), 0.065),
    )


# The effects with a hand-made sound; the rest use the parametric thump.
_EFFECT_SPECIALS = {
    Effect.BOUNCY: _bouncy_wave,
    Effect.BLACK_HOLE: _black_hole_wave,
    Effect.PORTAL: _portal_wave,
    Effect.STICKY: _sticky_wave,
    Effect.REPULSOR: _repulsor_wave,
    Effect.CONVEYOR: _conveyor_wave,
    Effect.ZIPPER: _zipper_wave,
    Effect.PHASE: _phase_wave,
    Effect.SPLITTER: _splitter_wave,
}


def _effect_wave(effect):
    """The impact sound of one effect type.

    A hand-made waveform when the effect has one (see _EFFECT_SPECIALS),
    otherwise a contact thump: a noise transient plus a low body tone whose
    pitch, decay, and ringing tail come from the effect's id.
    """
    special = _EFFECT_SPECIALS.get(effect)
    if special is not None:
        return special()
    pitch = 96.0 * 2 ** ((effect * 5) % 19 / 12.0)
    slide = (-420.0 if effect % 2 else 200.0) * (1 + effect % 3) * 0.5
    layers = [
        (_tick(0.020 + 0.004 * (effect % 3), 0.45, 26.0 + 4.0 * (effect % 3)), 0.0),
        (_tone(pitch, 0.16 + 0.01 * (effect % 3), volume=0.5,
               decay=9.0 + 3.0 * (effect % 4), slide=slide), 0.004),
    ]
    if effect % 3 == 0:
        layers.append((_tone(pitch * 2.0, 0.09, volume=0.20, decay=30.0), 0.012))
    if effect % 5 == 2:
        # A quiet bell-like partial gives this one a ringing tail.
        layers.append((_tone(pitch * 2.76, 0.14, volume=0.12, decay=18.0), 0.010))
    return _mix(*layers)


# --- Per-scorer trigger sounds ----------------------------------------------
# Scorers are rewards, so they ring: a bright note from a fixed scale with a
# quiet harmonic above it. The id scrambles the note order (so two scorers with
# neighbouring ids never sound alike), how long the tone rings, and its flavour.
_SCORER_SCALE = (0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24)  # semitones, 2 octaves
# The three core payoffs get the cleanest tones, low (+chips) to high (xMult).
_CORE_SCORER_PITCH = {Scorer.CHIPS_ADD: 392.0, Scorer.MULT_ADD: 494.0,
                      Scorer.MULT_MUL: 587.0}


def _core_scorer_wave(scorer):
    """A core payoff: one clean tone with a light octave above it."""
    freq = _CORE_SCORER_PITCH[scorer]
    return _mix(
        (_tone(freq, 0.16, volume=0.45, decay=13.0), 0.000),
        (_tone(freq * 2.0, 0.10, volume=0.16, decay=22.0), 0.008),
    )


def _cash_wave():
    """Money lands: a three-note coin cascade."""
    return _mix(
        (_tone(1300, 0.12, volume=0.5, decay=30.0), 0.00),
        (_tone(1800, 0.11, volume=0.4, decay=34.0), 0.05),
        (_tone(2600, 0.07, volume=0.2, decay=44.0), 0.09),
    )


def _sharp_wave():
    """A blade: a bright noise shing with a short metallic ring."""
    return _mix(
        (_noise(0.10, volume=0.35, decay=22.0), 0.00),
        (_tone(2200, 0.16, volume=0.25, decay=16.0, slide=-1400.0), 0.01),
    )


def _satanic_wave():
    """The devil's interval: a low tritone with a long, dark decay."""
    return _mix(
        (_tone(98, 0.40, volume=0.30, decay=5.0), 0.0),
        (_tone(196, 0.34, volume=0.45, decay=7.0), 0.0),
        (_tone(196 * 2 ** 0.5, 0.34, volume=0.40, decay=7.0), 0.0),
    )


def _echo_wave():
    """An echo: one blip answered by two quieter copies of itself."""
    return _mix(
        (_tone(660, 0.10, volume=0.40, decay=18.0), 0.00),
        (_tone(660, 0.10, volume=0.22, decay=18.0), 0.10),
        (_tone(660, 0.10, volume=0.10, decay=18.0), 0.20),
    )


def _lucky_wave():
    """A lucky jingle: two quick bright notes, the second higher."""
    return _mix(
        (_tone(880, 0.09, volume=0.4, decay=24.0), 0.00),
        (_tone(1320, 0.14, volume=0.4, decay=18.0), 0.06),
    )


def _colossus_wave():
    """A giant's footfall: a deep, heavy boom that dies away slowly."""
    return _mix(
        (_tone(58, 0.42, volume=0.45, decay=5.5), 0.0),
        (_tone(87, 0.36, volume=0.22, decay=7.0), 0.0),
        (_noise(0.16, volume=0.20, decay=11.0), 0.0),
    )


def _undertaker_wave():
    """A funeral bell: two slow tolls, the second with a long, mournful tail."""
    return _mix(
        (_tone(196, 0.34, volume=0.42, decay=5.5), 0.00),
        (_tone(392, 0.30, volume=0.18, decay=7.0), 0.01),
        (_tone(294, 0.34, volume=0.30, decay=5.0), 0.22),
        (_tone(196, 0.50, volume=0.22, decay=4.0), 0.23),
    )


def _debt_wave():
    """Money owed: two dull, falling clunks (a coin dropped into a ledger)."""
    return _mix(
        (_tone(430, 0.11, volume=0.42, decay=26.0, slide=-200.0), 0.00),
        (_tone(330, 0.16, volume=0.36, decay=20.0, slide=-150.0), 0.08),
    )


# The scorers with a hand-made sound; the rest use the parametric blip.
_SCORER_SPECIALS = {
    Scorer.CASH: _cash_wave,
    Scorer.SHARP: _sharp_wave,
    Scorer.ECHO: _echo_wave,
    Scorer.LUCKY: _lucky_wave,
    Scorer.SATANIC: _satanic_wave,
    Scorer.COLOSSUS: _colossus_wave,
    Scorer.UNDERTAKER: _undertaker_wave,
    Scorer.DEBT: _debt_wave,
}


def _scorer_wave(scorer):
    """The trigger sound of one scorer type.

    A hand-made waveform when the scorer has one (see _SCORER_SPECIALS), one of
    the three core tones for +Chips/+Mult/xMult, otherwise a ringing blip whose
    note, length, and flavour come from the scorer's id.
    """
    special = _SCORER_SPECIALS.get(scorer)
    if special is not None:
        return special()
    if scorer in _CORE_SCORER_PITCH:
        return _core_scorer_wave(scorer)
    freq = 330.0 * 2 ** (_SCORER_SCALE[(scorer * 7) % len(_SCORER_SCALE)] / 12.0)
    length = 0.10 + 0.02 * (scorer % 3)
    decay = 16.0 + 7.0 * (scorer % 4)
    layers = [(_tone(freq, length, volume=0.45, decay=decay), 0.0)]
    flavour = scorer % 3
    if flavour == 0:
        layers.append((_tone(freq * 2.0, length * 0.7, volume=0.22,
                             decay=decay * 1.5), 0.006))
    elif flavour == 1:
        layers.append((_tone(freq * 1.5, length * 0.8, volume=0.26,
                             decay=decay * 1.3), 0.008))
    else:
        layers.append((_tone(freq * 2.52, length * 0.8, volume=0.16,
                             decay=decay * 1.6), 0.005))
    if scorer % 4 == 3:
        layers.append((_tick(0.012, 0.25, 60.0), 0.0))
    return _mix(*layers)


# Sounds are built on first use and cached: a component that never shows up in
# a game costs nothing, and a component id added later needs no code here.
_EFFECT_SOUNDS = {}
_SCORER_SOUNDS = {}


_mixer_ok = _init_mixer()

if _mixer_ok:
    COIN = _build(_coin_wave())
    MECH = _build(_mech_wave())
    PLOP = _build(_plop_wave())
    RUN_START = _build(_run_start_wave())
    RESET = _build(_reset_wave())
else:
    COIN = MECH = PLOP = RUN_START = RESET = None


def play(sound):
    """Play a Sound if audio is available (no-op otherwise)."""
    if sound is not None:
        sound.play()


def _component_sound(cache, key, wave):
    """The cached Sound for a component id, synthesizing it on first use."""
    if not _mixer_ok:
        return None
    sound = cache.get(key)
    if sound is None:
        sound = _build(wave(key))
        cache[key] = sound
    return sound


def play_coin():
    """Play the coins-clinking buy sound (no-op without audio)."""
    play(COIN)


def play_mech():
    """Play the mechanical whir + crunch (dis)assemble sound (no-op without audio)."""
    play(MECH)


def play_plop():
    """Play the block-placing plop sound (no-op without audio)."""
    play(PLOP)


def play_run_start():
    """Play the rising fanfare that starts a run (no-op without audio)."""
    play(RUN_START)


def play_reset():
    """Play the falling tones of a run being reset (no-op without audio)."""
    play(RESET)


def play_effect(effect):
    """Play the impact sound of the effect a marble just hit (no-op without audio)."""
    play(_component_sound(_EFFECT_SOUNDS, effect, _effect_wave))


def play_scorer(scorer):
    """Play the trigger sound of the scorer that just fired (no-op without audio)."""
    play(_component_sound(_SCORER_SOUNDS, scorer, _scorer_wave))
