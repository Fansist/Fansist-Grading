"""generate_kiosk.py

Parametric CAD for the Fansist ScanSlab kiosk (see docs/SCANSLAB_KIOSK_DESIGN.md).
This is a Rev A **general-arrangement (GA)** model — correctly dimensioned and
laid out for quoting, layout and integration; the COTS modules (laser marker,
camera/LED-dome optics, ultrasonic welder) are represented by their *envelopes*,
not internal mechanism CAD.

    python hardware/kiosk/generate_kiosk.py

Outputs (relative to this file):
    stl/<part>.stl            GA solids: cabinet panels, internal module envelopes,
                              and the redesigned slab (slab_v2).
    dxf/<panel>.dxf           sheet-metal cabinet flat patterns (CUT/BEND/ENGRAVE).
    preview/kiosk_assembly.png  rendered GA assembly (cabinet ghosted)
    preview/cabinet_nest.png    rendered cabinet flat patterns

All dimensions are MILLIMETRES. Kiosk: 600 (W) x 600 (D) x 1500 (H).
"""

from __future__ import annotations

import os

import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(HERE, "stl")
DXF_DIR = os.path.join(HERE, "dxf")
PREVIEW_DIR = os.path.join(HERE, "preview")

# --- Master kiosk dimensions (mm) ------------------------------------------
W, D, H = 600.0, 600.0, 1500.0     # outer cabinet envelope
T = 2.0                            # sheet-steel thickness

# Front-face feature windows (X across width, Z up): (x0, z0, x1, z1)
HMI_WINDOW = (120, 1305, 480, 1470)
CARD_SLOT = (250, 1082, 350, 1096)
TRAY_OPENING = (190, 690, 410, 770)

# Internal module bays — (size_x, size_y, size_z, centre_z)
IPC_BAY = (500, 500, 320, 175)
LASER_STATION = (470, 470, 320, 520)
SLAB_STATION = (490, 470, 280, 850)
SCAN_PLATEN = (490, 470, 50, 1030)
DOME_RADIUS = 190.0
DOME_BASE_Z = 1055.0


# ---------------------------------------------------------------------------
# trimesh helpers
# ---------------------------------------------------------------------------

def box(sx, sy, sz, cx, cy, cz):
    b = trimesh.creation.box(extents=(sx, sy, sz))
    b.apply_translation((cx, cy, cz))
    return b


def cyl(d, h, cx, cy, cz, axis="z"):
    c = trimesh.creation.cylinder(radius=d / 2.0, height=h, sections=40)
    if axis == "x":
        c.apply_transform(rotation_matrix(np.pi / 2, (0, 1, 0)))
    elif axis == "y":
        c.apply_transform(rotation_matrix(np.pi / 2, (1, 0, 0)))
    c.apply_translation((cx, cy, cz))
    return c


def cut(solid, holes):
    return trimesh.boolean.difference([solid, *holes])


# ---------------------------------------------------------------------------
# Cabinet panels (2 mm sheet) — placed in world coords; front face at Y=0
# ---------------------------------------------------------------------------

def cab_bottom():
    return box(W, D, T, W / 2, D / 2, T / 2)


def cab_top():
    return box(W, D, T, W / 2, D / 2, H - T / 2)


def cab_back():
    panel = box(W, T, H, W / 2, D - T / 2, H / 2)
    door = box(380, T + 4, 560, W / 2, D - T / 2, 430)        # service-door cutout
    cable = cyl(40, T + 4, W / 2, D - T / 2, 90, axis="y")    # cable entry
    return cut(panel, [door, cable])


def cab_side(x_centre):
    panel = box(T, D, H, x_centre, D / 2, H / 2)
    vents = [box(T + 4, 220, 8, x_centre, D / 2, z) for z in (300, 470, 1180, 1230)]
    return cut(panel, vents)


def cab_front():
    panel = box(W, T, H, W / 2, T / 2, H / 2)
    holes = []
    for (x0, z0, x1, z1) in (HMI_WINDOW, CARD_SLOT, TRAY_OPENING):
        holes.append(box(x1 - x0, T + 4, z1 - z0, (x0 + x1) / 2, T / 2, (z0 + z1) / 2))
    return cut(panel, holes)


# ---------------------------------------------------------------------------
# Internal module envelopes
# ---------------------------------------------------------------------------

def module_box(spec, name=""):
    sx, sy, sz, cz = spec
    return box(sx, sy, sz, W / 2, D / 2, cz)


def scan_dome():
    """LED photometric dome + coaxial down-looking camera over the platen."""
    platen = module_box(SCAN_PLATEN)
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=DOME_RADIUS)
    sphere.apply_translation((W / 2, D / 2, DOME_BASE_Z))
    lower = box(2 * DOME_RADIUS + 20, 2 * DOME_RADIUS + 20, 2 * DOME_RADIUS,
                W / 2, D / 2, DOME_BASE_Z - DOME_RADIUS)        # keep upper hemisphere
    dome = trimesh.boolean.difference([sphere, lower])
    cam_hole = cyl(60, 80, W / 2, D / 2, DOME_BASE_Z + DOME_RADIUS - 20)
    dome = cut(dome, [cam_hole])
    camera = cyl(54, 70, W / 2, D / 2, DOME_BASE_Z + DOME_RADIUS + 5)
    return trimesh.util.concatenate([platen, dome, camera])


def hmi():
    """Angled touchscreen behind the HMI window (tilted ~15deg)."""
    plate = trimesh.creation.box(extents=(360, 18, 175))
    plate.apply_transform(rotation_matrix(np.radians(15), (1, 0, 0)))
    plate.apply_translation((W / 2, 35, 1388))
    return plate


def output_tray():
    """Slab output tray, protruding from the front."""
    return box(220, 130, 55, W / 2, -45, 730)


def slab_v2():
    """Redesigned slab: card window + sealed code-label recess + frosted,
    laser-markable grade panel (blank until pick-up). Modelled flat, z up."""
    ow, oh, ot = 95.0, 135.0, 9.0
    outer = box(ow, oh, ot, ow / 2, oh / 2, ot / 2)
    # Card window (lower portion).
    card_win = box(67, 92, ot + 2, ow / 2, 50, ot / 2)
    # Grade panel recess (top), where the grade is laser-marked later.
    grade_panel = box(78, 22, 2.0, ow / 2, oh - 16, ot - 1.0)
    # Code-label recess (small, beside the grade panel).
    code_win = box(26, 12, 1.5, ow / 2, oh - 38, ot - 0.75)
    return cut(outer, [card_win, grade_panel, code_win])


# (mesh-builder, colour) — modules + product; cabinet handled separately.
MODULES = {
    "ipc_bay": (lambda: module_box(IPC_BAY), "#9ecae1"),
    "laser_station": (lambda: module_box(LASER_STATION), "#fc9272"),
    "slab_station": (lambda: module_box(SLAB_STATION), "#a1d99b"),
    "scan_dome": (scan_dome, "#fdd0a2"),
    "hmi": (hmi, "#bcbddc"),
    "output_tray": (output_tray, "#d9d9d9"),
    "slab_v2": (slab_v2, "#74c476"),
}
PANELS = {
    "cabinet_bottom": cab_bottom, "cabinet_top": cab_top, "cabinet_back": cab_back,
    "cabinet_side_left": lambda: cab_side(T / 2),
    "cabinet_side_right": lambda: cab_side(W - T / 2),
    "cabinet_front": cab_front,
}


def build_stls():
    os.makedirs(STL_DIR, exist_ok=True)
    meshes = {}
    for name, fn in PANELS.items():
        m = fn()
        m.export(os.path.join(STL_DIR, f"{name}.stl"))
        meshes[name] = (m, "#cfcfcf")
    for name, (fn, color) in MODULES.items():
        m = fn()
        m.export(os.path.join(STL_DIR, f"{name}.stl"))
        meshes[name] = (m, color)
    for name, (m, _c) in meshes.items():
        e = m.bounding_box.extents
        print(f"{name:18s} bbox {e[0]:6.0f} x {e[1]:6.0f} x {e[2]:6.0f} mm")
    return meshes


def render_assembly(meshes):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except Exception as exc:  # pragma: no cover
        print(f"(render skipped: {exc})")
        return
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    fig = plt.figure(figsize=(7, 10))
    ax = fig.add_subplot(111, projection="3d")
    for name, (m, color) in meshes.items():
        ghost = name.startswith("cabinet")
        coll = Poly3DCollection(m.triangles, alpha=0.12 if ghost else 0.95,
                                facecolor=color, edgecolor=(0, 0, 0, 0.08), linewidths=0.1)
        ax.add_collection3d(coll)
    # slab_v2 sits on the output tray for the GA shot.
    ax.set_xlim(-100, 700)
    ax.set_ylim(-150, 650)
    ax.set_zlim(0, 1550)
    ax.set_box_aspect((W + 200, D + 200, H))
    ax.view_init(elev=18, azim=-72)
    ax.set_axis_off()
    ax.set_title("Fansist ScanSlab kiosk — GA (cabinet ghosted)", fontsize=11)
    fig.savefig(os.path.join(PREVIEW_DIR, "kiosk_assembly.png"), dpi=130, facecolor="white")
    plt.close(fig)
    print(f"wrote {PREVIEW_DIR}/kiosk_assembly.png")


# ---------------------------------------------------------------------------
# Sheet-metal cabinet flat patterns (DXF)
# ---------------------------------------------------------------------------

def build_dxf():
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    os.makedirs(DXF_DIR, exist_ok=True)

    def new():
        doc = ezdxf.new("R2010")
        doc.units = ezdxf.units.MM
        for nm, col in (("CUT", 1), ("BEND", 3), ("ENGRAVE", 5), ("SHEET", 8)):
            if nm not in doc.layers:
                doc.layers.add(nm, color=col)
        return doc

    def rect(msp, ox, oy, w, h, layer="CUT"):
        msp.add_lwpolyline([(ox, oy), (ox + w, oy), (ox + w, oy + h), (ox, oy + h)],
                           close=True, dxfattribs={"layer": layer})

    def bend(msp, x0, y0, x1, y1):
        msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": "BEND"})

    def label(msp, ox, oy, txt):
        t = msp.add_text(txt, height=12, dxfattribs={"layer": "ENGRAVE"})
        t.set_placement((ox + 10, oy + 10), align=TextEntityAlignment.LEFT)

    def slot_row(msp, x0, y, count, sw, gap, sh):
        for i in range(count):
            rect(msp, x0 + i * (sw + gap), y, sw, sh)

    def save(doc, name):
        doc.saveas(os.path.join(DXF_DIR, f"{name}.dxf"))

    flange = 25.0  # fold flange width (informational bend lines)

    # FRONT (W x H) with the feature windows.
    doc = new(); msp = doc.modelspace()
    rect(msp, 0, 0, W, H)
    for (x0, z0, x1, z1) in (HMI_WINDOW, CARD_SLOT, TRAY_OPENING):
        rect(msp, x0, z0, x1 - x0, z1 - z0)
    for x in (flange, W - flange):
        bend(msp, x, 0, x, H)
    label(msp, 0, 0, "FRONT 2mm steel")
    save(doc, "cabinet_front")

    # BACK with service-door + vents + cable.
    doc = new(); msp = doc.modelspace()
    rect(msp, 0, 0, W, H)
    rect(msp, (W - 380) / 2, 150, 380, 560)              # service door
    msp.add_circle((W / 2, 90), 20, dxfattribs={"layer": "CUT"})  # cable gland
    slot_row(msp, 120, 1180, 8, 30, 14, 120)             # top vents
    for x in (flange, W - flange):
        bend(msp, x, 0, x, H)
    label(msp, 0, 0, "BACK 2mm steel")
    save(doc, "cabinet_back")

    # SIDE (D x H) x2 — vents + bend flanges top/bottom.
    for nm in ("cabinet_side_left", "cabinet_side_right"):
        doc = new(); msp = doc.modelspace()
        rect(msp, 0, 0, D, H)
        for z in (280, 450, 1160, 1210):
            slot_row(msp, 180, z, 6, 28, 14, 8)
        for y in (flange, H - flange):
            bend(msp, 0, y, D, y)
        label(msp, 0, 0, nm.replace("cabinet_", "").upper() + " 2mm steel")
        save(doc, nm)

    # TOP / BOTTOM (W x D).
    for nm, vents in (("cabinet_top", True), ("cabinet_bottom", False)):
        doc = new(); msp = doc.modelspace()
        rect(msp, 0, 0, W, D)
        if vents:
            slot_row(msp, 120, 250, 8, 30, 14, 120)
        else:
            for cx, cy in ((60, 60), (W - 60, 60), (60, D - 60), (W - 60, D - 60)):
                msp.add_circle((cx, cy), 6, dxfattribs={"layer": "CUT"})   # caster mounts
        label(msp, 0, 0, nm.replace("cabinet_", "").upper() + " 2mm steel")
        save(doc, nm)

    # Nest sheet (all six panels on one ~2.2 x 2.2 m steel sheet) + render.
    doc = new(); msp = doc.modelspace()
    _nest_panels(msp, rect, bend, label, slot_row)
    save(doc, "cabinet_nest")
    _render_dxf(os.path.join(DXF_DIR, "cabinet_nest.dxf"))
    print(f"wrote sheet-metal DXF to {DXF_DIR}")


def _nest_panels(msp, rect, bend, label, slot_row):
    """Lay the six panels on one stock sheet for the nest DXF."""
    gap = 25
    # (name, w, h, ox, oy)
    layout = [
        ("FRONT", W, H, 10, 10),
        ("BACK", W, H, 10 + W + gap, 10),
        ("SIDE-L", D, H, 10 + 2 * (W + gap), 10),
        ("SIDE-R", D, H, 10 + 2 * (W + gap) + D + gap, 10),
        ("TOP", W, D, 10, 10 + H + gap),
        ("BOTTOM", W, D, 10 + W + gap, 10 + H + gap),
    ]
    for name, w, h, ox, oy in layout:
        rect(msp, ox, oy, w, h)
        label(msp, ox, oy, name)
    rect(msp, 0, 0, 2200, 2200, layer="SHEET")


def _render_dxf(path):
    try:
        import ezdxf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except Exception as exc:  # pragma: no cover
        print(f"(dxf render skipped: {exc})")
        return
    doc = ezdxf.readfile(path)
    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)
    fig.savefig(os.path.join(PREVIEW_DIR, "cabinet_nest.png"), dpi=110, facecolor="white")
    plt.close(fig)
    print(f"wrote {PREVIEW_DIR}/cabinet_nest.png")


def main():
    meshes = build_stls()
    render_assembly(meshes)
    build_dxf()


if __name__ == "__main__":
    main()
