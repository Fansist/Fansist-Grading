"""generate_panels.py

Generate laser-cut DXF panels for the Fansist SlabStation Mini enclosure
(Rev A). Run this to (re)produce the DXF files a laser shop can quote from, plus
a single nesting sheet and a PNG preview.

    python hardware/generate_panels.py

Outputs (relative to this file):
    dxf/<panel>.dxf        one file per panel (5 mm structural unless noted)
    dxf/nest_sheet_5mm.dxf all 5 mm structural panels nested on one sheet
    preview/nest_sheet.png a render of the nest sheet for visual check

All dimensions are MILLIMETRES. Geometry is Rev A, intended for quoting and for
cutting a first physical prototype -- verify fit and adjust joinery to the chosen
corner brackets / slab holder before any production tooling. Layer convention:
    CUT      (red)  -> through-cut outlines and cut-outs
    ENGRAVE  (blue) -> part-name marking (optional; ignore if not engraving)
    SHEET    (grey) -> reference stock outline on the nest sheet only
"""

from __future__ import annotations

import os

import ezdxf
from ezdxf.enums import TextEntityAlignment

# ---------------------------------------------------------------------------
# Master parameters (edit here)
# ---------------------------------------------------------------------------

OUTER_W = 240.0      # enclosure width  (X)
OUTER_D = 240.0      # enclosure depth  (Y of top/bottom)
OUTER_H = 320.0      # enclosure height (Y of side/back/front panels)

MAT_T = 5.0          # structural panel thickness (MDF or acrylic)
DIFFUSER_T = 3.0     # diffuser panel thickness (frosted acrylic) -- separate file

SCREW_CLEAR_D = 3.2  # M3 clearance hole
FOOT_HOLE_D = 4.0    # rubber-foot fixing
CAMERA_APERTURE_D = 75.0  # top-panel hole the phone/camera shoots through

EDGE_INSET = 12.0    # how far corner bracket holes sit in from the edges

HERE = os.path.dirname(os.path.abspath(__file__))
DXF_DIR = os.path.join(HERE, "dxf")
PREVIEW_DIR = os.path.join(HERE, "preview")


# ---------------------------------------------------------------------------
# Low-level drawing helpers (everything draws into a modelspace at an offset)
# ---------------------------------------------------------------------------

def _new_doc():
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    for name, color in (("CUT", 1), ("ENGRAVE", 5), ("SHEET", 8)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    return doc


def rect(msp, ox, oy, w, h, layer="CUT"):
    pts = [(ox, oy), (ox + w, oy), (ox + w, oy + h), (ox, oy + h)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


def hole(msp, cx, cy, dia, layer="CUT"):
    msp.add_circle((cx, cy), dia / 2.0, dxfattribs={"layer": layer})


def label(msp, ox, oy, text):
    t = msp.add_text(text, height=7.0, dxfattribs={"layer": "ENGRAVE"})
    t.set_placement((ox + 8, oy + 8), align=TextEntityAlignment.LEFT)


def corner_bracket_holes(msp, ox, oy, w, h, inset=EDGE_INSET):
    """Four M3 holes inset from each corner (generic bracket/standoff fixing)."""
    for dx, dy in ((inset, inset), (w - inset, inset),
                   (inset, h - inset), (w - inset, h - inset)):
        hole(msp, ox + dx, oy + dy, SCREW_CLEAR_D)


# ---------------------------------------------------------------------------
# Panel builders -- each draws one panel with its features at offset (ox, oy)
# ---------------------------------------------------------------------------

def panel_bottom(msp, ox=0.0, oy=0.0):
    w, h = OUTER_W, OUTER_D
    rect(msp, ox, oy, w, h)
    corner_bracket_holes(msp, ox, oy, w, h)
    for dx, dy in ((25, 25), (w - 25, 25), (25, h - 25), (w - 25, h - 25)):
        hole(msp, ox + dx, oy + dy, FOOT_HOLE_D)        # rubber feet
    label(msp, ox, oy, "BOTTOM 5mm")


def panel_top(msp, ox=0.0, oy=0.0):
    w, h = OUTER_W, OUTER_D
    rect(msp, ox, oy, w, h)
    corner_bracket_holes(msp, ox, oy, w, h)
    hole(msp, ox + w / 2, oy + h / 2, CAMERA_APERTURE_D)  # camera/phone aperture
    for dx, dy in ((w / 2 - 45, h / 2), (w / 2 + 45, h / 2),
                   (w / 2, h / 2 - 45), (w / 2, h / 2 + 45)):
        hole(msp, ox + dx, oy + dy, SCREW_CLEAR_D)        # phone-cradle fixing
    rect(msp, ox + w / 2 - 11, oy + h - 10, 22, 10)       # wiring notch at rear edge
    label(msp, ox, oy, "TOP 5mm")


def panel_back(msp, ox=0.0, oy=0.0):
    w, h = OUTER_W, OUTER_H
    rect(msp, ox, oy, w, h)
    corner_bracket_holes(msp, ox, oy, w, h)
    rect(msp, ox + w / 2 - 12, oy + 6, 24, 12)            # USB cable cut-out
    label(msp, ox, oy, "BACK 5mm")


def _panel_side(msp, ox, oy, name):
    w, h = OUTER_D, OUTER_H
    rect(msp, ox, oy, w, h)
    corner_bracket_holes(msp, ox, oy, w, h)
    # Nest-shelf support holes (horizontal row at shelf height = 70 mm).
    for dx in (30, w / 2, w - 30):
        hole(msp, ox + dx, oy + 70, SCREW_CLEAR_D)
    # LED-strip standoff holes (vertical line near the front edge).
    for dy in (120, 180, 240, 290):
        hole(msp, ox + 15, oy + dy, SCREW_CLEAR_D)
    label(msp, ox, oy, name)


def panel_side_left(msp, ox=0.0, oy=0.0):
    _panel_side(msp, ox, oy, "SIDE-L 5mm")


def panel_side_right(msp, ox=0.0, oy=0.0):
    # Mirror-symmetric hole pattern -> identical part; mark it differently.
    _panel_side(msp, ox, oy, "SIDE-R 5mm")


def panel_front(msp, ox=0.0, oy=0.0):
    w, h = OUTER_W, OUTER_H
    rect(msp, ox, oy, w, h)
    corner_bracket_holes(msp, ox, oy, w, h)
    rect(msp, ox + 30, oy + 40, w - 60, h - 90)          # access window
    label(msp, ox, oy, "FRONT 5mm")


def panel_nest_shelf(msp, ox=0.0, oy=0.0):
    w = h = 230.0
    rect(msp, ox, oy, w, h)
    # Card viewing window (centred); the card sits on the shelf above it.
    win_w, win_h = 80.0, 110.0
    wx, wy = (w - win_w) / 2, (h - win_h) / 2
    rect(msp, ox + wx, oy + wy, win_w, win_h)
    # Registration-stop fixing holes around the card pocket.
    for dx, dy in ((wx - 6, wy - 6), (wx + win_w + 6, wy - 6),
                   (wx - 6, wy + win_h + 6), (wx + win_w + 6, wy + win_h + 6)):
        hole(msp, ox + dx, oy + dy, SCREW_CLEAR_D)
    # Side-support fixing holes (screw the shelf to the side panels).
    for dx in (8, w - 8):
        for dy in (40, h - 40):
            hole(msp, ox + dx, oy + dy, SCREW_CLEAR_D)
    label(msp, ox, oy, "NEST-SHELF 5mm")


def panel_diffuser(msp, ox=0.0, oy=0.0):
    w, h = 60.0, 280.0
    rect(msp, ox, oy, w, h)
    for dy in (15, h - 15):
        hole(msp, ox + w / 2, oy + dy, SCREW_CLEAR_D)
    label(msp, ox, oy, "DIFFUSER 3mm x2")


def panel_background(msp, ox=0.0, oy=0.0):
    rect(msp, ox, oy, 120.0, 160.0)
    label(msp, ox, oy, "BG-INSERT card/board")


# Structural 5 mm panels that nest on one sheet.
STRUCTURAL = [
    ("bottom", panel_bottom),
    ("top", panel_top),
    ("back", panel_back),
    ("side_left", panel_side_left),
    ("side_right", panel_side_right),
    ("front", panel_front),
    ("nest_shelf", panel_nest_shelf),
]
# Different-material parts -> separate files only.
OTHER = [
    ("diffuser_3mm", panel_diffuser),
    ("background_insert", panel_background),
]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_individual():
    os.makedirs(DXF_DIR, exist_ok=True)
    for fname, builder in STRUCTURAL + OTHER:
        doc = _new_doc()
        builder(doc.modelspace(), 0.0, 0.0)
        doc.saveas(os.path.join(DXF_DIR, f"{fname}.dxf"))


def save_nest_sheet():
    """Lay the 5 mm structural panels on one stock sheet."""
    doc = _new_doc()
    msp = doc.modelspace()
    gap = 15.0
    # (builder, offset_x, offset_y) -- hand-placed to fit a ~800x950 sheet.
    placements = [
        (panel_bottom, 10, 10),
        (panel_top, 10 + OUTER_W + gap, 10),
        (panel_nest_shelf, 10 + 2 * (OUTER_W + gap), 10),
        (panel_back, 10, 10 + OUTER_D + gap),
        (panel_side_left, 10 + OUTER_D + gap, 10 + OUTER_D + gap),
        (panel_side_right, 10 + 2 * (OUTER_D + gap), 10 + OUTER_D + gap),
        (panel_front, 10, 10 + OUTER_D + gap + OUTER_H + gap),
    ]
    for builder, ox, oy in placements:
        builder(msp, ox, oy)
    rect(msp, 0, 0, 800, 950, layer="SHEET")  # reference stock outline
    doc.saveas(os.path.join(DXF_DIR, "nest_sheet_5mm.dxf"))
    return doc, msp


def render_preview(doc, msp):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except Exception as exc:  # pragma: no cover
        print(f"(preview skipped: {exc})")
        return
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    fig = plt.figure(figsize=(8, 9.5))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    fig.savefig(os.path.join(PREVIEW_DIR, "nest_sheet.png"), dpi=130, facecolor="white")
    plt.close(fig)


def main():
    save_individual()
    doc, msp = save_nest_sheet()
    render_preview(doc, msp)
    n = len(STRUCTURAL + OTHER) + 1
    print(f"Wrote {n} DXF files to {DXF_DIR} and a preview to {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
