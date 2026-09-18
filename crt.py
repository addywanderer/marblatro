"""A CRT screen filter: curvature, scanlines, and a vignette.

Balatro-flavoured: the finished frame comes out of a tube television — bowed as
if the glass were curved, thinned by horizontal scanlines, and lit brighter in
the middle than at the corners. The picture is magnified towards the edges so
the screen stays FILLED edge to edge: curving the glass crops the picture's own
corners away rather than leaving black bars, exactly as a real tube does.

It is a POST-process: ``Game._present`` runs it on the off-screen frame buffer
right after ``ui.draw`` has finished a frame, and only then blits that buffer to
the window — so every screen (title, board, shop, popups and overlays alike) is
filtered the same way, no drawing code has to know the filter exists, and the
window never shows a half-filtered frame. F2 turns it on and off, and the
choice is remembered per profile (see ``metagame``).

WHY BLITS AND NOT A SHADER. The exact Balatro-style warp is a per-pixel remap of
the whole frame, and in pygame that means gathering ~1M pixels through numpy on
the CPU: measured at ~12 ms a frame for this 1200x800 screen. That would push
the game under 60 fps — and because ``update`` steps the physics by a fixed DT,
it would slow the marbles down with it. So the warp is approximated with a
handful of cheap C blits instead: the frame is cut into horizontal bands and
each band is stretched in place by the barrel term at its own height. Everything
that does not vary along a row (the scanlines, the vignette) is built once per
surface size, so a frame costs one copy plus ~40 scale+blit pairs (~2 ms).
"""

import numpy as np
import pygame

# How far the frame's edges bow inwards (0 = a flat screen). 0.05 is a visible
# but gentle tube: the picture is magnified about 5% at the sides and 10% in the
# corners to keep the screen filled as the glass curves away.
CURVATURE = 0.02
# How much darker every other row is (the scanline thinning), 0..1. Kept
# gentle: the game's labels are small and have to stay readable.
SCANLINE = 0.25
# How much darker the corners are than the middle.
VIGNETTE = 0.25
# Rows per warp band. Smaller bands follow the curve more closely and cost one
# more scale+blit each; 20 rows (40 bands at this screen height) keeps the
# steps between neighbouring bands under a pixel.
BAND = 20

# Warp bands and shading overlay, per surface size.
_CACHE = {"bands": {}, "shading": {}, "frame": {}}


def _barrel(height):
    """The vertical barrel map: (v, bend, source row) per destination row.

    ``v`` runs -1..1 from the top edge to the bottom; ``bend`` is the barrel
    term at that row and the source row a destination row samples is ``v /
    bend`` — sampling INWARDS, which magnifies the picture towards the edges and
    keeps the screen filled (the picture's outermost rows fall outside it). The
    horizontal coordinate squared is averaged over the row (it is 1/3 for a -1..1
    range), which is what lets the warp be done a whole row at a time.
    """
    v = np.linspace(-1.0, 1.0, height)
    bend = 1.0 + CURVATURE * (v * v + 1.0 / 3.0)
    return v, bend, (v / bend * 0.5 + 0.5) * (height - 1)


def _warp_bands(size):
    """(source rect, destination rect) for every band of the tube warp.

    Bands are cut along the SOURCE rows and each is stretched to where those
    rows land on the screen (the inverse of the barrel map, which is monotone).
    A band beside the middle lands roughly where it started; a band near the top
    or bottom lands slightly outside the screen and is stretched inwards to
    reach it, which both magnifies the picture and bows it. The source rows the
    curve pushes off the screen are dropped, and the bands that remain tile the
    screen exactly, edge to edge (see the shared ``edges`` below): nothing is
    ever drawn smaller than the screen, so there are no black bars and no black
    corners.
    """
    cached = _CACHE["bands"].get(size)
    if cached is not None:
        return cached
    width, height = size
    _v, bend, source_rows = _barrel(height)
    # Where each source row ends up on the screen (rows the curve pushes off the
    # screen clamp to the edges and are dropped by the range below).
    dest_rows = np.interp(np.arange(height), source_rows, np.arange(height))
    first = max(0, int(np.ceil(source_rows[0])))
    last = min(height, int(np.floor(source_rows[-1])) + 1)
    # Band boundaries are computed once and shared, so neighbouring bands meet
    # exactly: rounding each band's own ends would leave one-row black seams.
    tops = list(range(first, last, BAND))
    edges = [round(dest_rows[top]) for top in tops]
    edges.append(round(dest_rows[last - 1]) + 1)
    # Rounding can leave the outermost rows short of the screen's own edge; the
    # bands have to tile it exactly, or a black hairline shows along the edge.
    edges[0], edges[-1] = 0, height
    bands = []
    for index, source_top in enumerate(tops):
        source_bottom = min(source_top + BAND, last)
        top, bottom = edges[index], edges[index + 1]
        if bottom - top < 1:
            continue
        # The band's own horizontal magnification: the barrel term at the row
        # it lands on. The source strip is narrower than the screen, so
        # stretching it to the full width pulls the picture's sides out to the
        # edges (and crops whatever the curve pushes past them).
        middle = max(0, min(height - 1, (top + bottom) // 2))
        source_width = width / bend[middle]
        bands.append((
            pygame.Rect(round((width - source_width) * 0.5), source_top,
                        max(1, round(source_width)), source_bottom - source_top),
            pygame.Rect(0, top, width, bottom - top)))
    _CACHE["bands"][size] = bands
    return bands


def _shading(size):
    """The scanline + vignette darkening, as one BLEND_MULT overlay.

    A multiply blit is the cheapest way to darken a whole frame in pygame
    (~0.3 ms), so both shades are baked into one greyscale surface: 255 keeps a
    pixel, 0 blackens it.
    """
    cached = _CACHE["shading"].get(size)
    if cached is not None:
        return cached
    width, height = size
    # surfarray order: the arrays are (width, height), x first.
    columns = np.arange(width, dtype=np.float32)[:, None]
    rows = np.arange(height, dtype=np.float32)[None, :]
    u = columns / max(width - 1, 1) * 2.0 - 1.0
    v = rows / max(height - 1, 1) * 2.0 - 1.0
    radius2 = u * u + v * v
    shade = 1.0 - VIGNETTE * np.clip(radius2 / 2.0, 0.0, 1.0)
    # Every other row keeps its colour: the rows between them are the dark gaps
    # between the scanlines.
    shade = np.where(np.arange(height)[None, :] % 2 == 0, shade,
                     shade * (1.0 - SCANLINE))
    overlay = pygame.Surface(size)
    grey = (np.clip(shade, 0.0, 1.0) * 255.0).astype(np.uint8)
    pygame.surfarray.blit_array(overlay, np.repeat(grey[:, :, None], 3, axis=2))
    _CACHE["shading"][size] = overlay
    return overlay


def apply(surface):
    """Filter ``surface`` in place, as if it were a curved CRT picture.

    Called once per finished frame (see Game._present). The frame is copied
    aside first (the bands are read back out of it while it is being rewritten),
    then the bands are stretched from it across the whole surface and the
    shading overlay is multiplied over the result. The bands and the overlay are
    cached per size, so only the master copy and the blits cost anything, and
    the screen comes out filled edge to edge every time.
    """
    size = surface.get_size()
    if not pygame.display.get_init():
        return  # nothing to warp or blend
    frame = _CACHE["frame"].get(size)
    if frame is None:
        frame = pygame.Surface(size)
        _CACHE["frame"][size] = frame
    frame.blit(surface, (0, 0))  # read the frame while drawing over it
    surface.fill((0, 0, 0))  # insurance: the bands cover the screen exactly
    for source, dest in _warp_bands(size):
        surface.blit(pygame.transform.scale(frame.subsurface(source), dest.size),
                     dest.topleft)
    surface.blit(_shading(size), (0, 0), special_flags=pygame.BLEND_MULT)
