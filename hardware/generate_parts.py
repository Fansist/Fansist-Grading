"""generate_parts.py

Generate the 3D-printed parts for the Fansist SlabStation Mini as STL files,
plus an exploded preview render. These are the parts a print farm / injection
moulder needs alongside the laser-cut enclosure (see generate_panels.py).

    python hardware/generate_parts.py

Outputs (relative to this file):
    stl/<part>.stl          one watertight solid per part (millimetres)
    preview/parts_exploded.png   exploded render of the press + accessories

Locked Rev B design decisions embodied here:
  * Smartphone camera (printed universal cradle over the top aperture).
  * One-touch magnetic slab holder, reference outer 86 x 120 x 10 mm.
  * Manual HINGED LEVER press: place the open holder + card in the nest, swing
    the arm down and press -- the platen closes the two halves squarely and the
    magnets snap. Simple, few parts, self-aligning, printable.
  * Enclosure joined by printed corner brackets (also designed here).

All solids are watertight; holes >= 3 mm, walls >= 3 mm (FDM-friendly).
"""

from __future__ import annotations

import os

import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(HERE, "stl")
PREVIEW_DIR = os.path.join(HERE, "preview")

# Reference dimensions (mm)
HOLDER_W, HOLDER_H, HOLDER_T = 86.0, 120.0, 10.0   # one-touch holder outer
M3 = 3.4            # M3 clearance hole diameter
PIN_D = 5.2         # hinge-pin (Ø5 bolt) clearance


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def box(sx, sy, sz, cx=0.0, cy=0.0, cz=0.0):
    b = trimesh.creation.box(extents=(sx, sy, sz))
    b.apply_translation((cx, cy, cz))
    return b


def cyl(d, h, cx=0.0, cy=0.0, cz=0.0, axis="z"):
    c = trimesh.creation.cylinder(radius=d / 2.0, height=h, sections=48)
    if axis == "x":
        c.apply_transform(rotation_matrix(np.pi / 2, (0, 1, 0)))
    elif axis == "y":
        c.apply_transform(rotation_matrix(np.pi / 2, (1, 0, 0)))
    c.apply_translation((cx, cy, cz))
    return c


def union(parts):
    return trimesh.boolean.union(parts)


def cut(solid, holes):
    return trimesh.boolean.difference([solid, *holes])


# ---------------------------------------------------------------------------
# Parts  (each returns a watertight mesh; local origin noted in comments)
# ---------------------------------------------------------------------------

def corner_bracket():
    """L-bracket to join two enclosure panels at 90deg. Inner corner at origin."""
    t, w, hgt = 6.0, 30.0, 40.0
    f1 = box(w, t, hgt, w / 2, t / 2, hgt / 2)          # flange in x-z plane
    f2 = box(t, w, hgt, t / 2, w / 2, hgt / 2)          # flange in y-z plane
    solid = union([f1, f2])
    holes = [
        cyl(M3, t + 4, 18, t / 2, 12, axis="y"),        # flange1 fixings
        cyl(M3, t + 4, 18, t / 2, 28, axis="y"),
        cyl(M3, t + 4, t / 2, 18, 12, axis="x"),        # flange2 fixings
        cyl(M3, t + 4, t / 2, 18, 28, axis="x"),
    ]
    return cut(solid, holes)


def reg_stop():
    """Small L stop that locates a card corner on the imaging nest shelf.

    Card corner sits against the inner faces of the two walls at the origin."""
    base = box(20, 20, 3, 10, 10, 1.5)
    wall_x = box(20, 3, 10, 10, 1.5, 5)
    wall_y = box(3, 20, 10, 1.5, 10, 5)
    solid = union([base, wall_x, wall_y])
    return cut(solid, [cyl(M3, 8, 14, 14, 1.5)])         # fixing into shelf


def phone_cradle():
    """Tray that clips on the top panel; phone lies screen-up, rear camera down
    through the central hole over the enclosure aperture. Base sits on z=0."""
    base = box(180, 120, 5, 90, 60, 2.5)
    back_lip = box(180, 5, 18, 90, 117.5, 9)
    side_lip = box(5, 120, 15, 2.5, 60, 7.5)
    solid = union([base, back_lip, side_lip])
    holes = [cyl(40, 10, 90, 60, 2.5)]                   # camera clearance
    # 4 fixings on the top-panel "plus" pattern (45 mm from centre).
    for dx, dy in ((45, 60), (135, 60), (90, 15), (90, 105)):
        holes.append(cyl(M3, 10, dx, dy, 2.5))
    return cut(solid, holes)


def slab_nest():
    """Tray that registers the holder's bottom shell on the press base.

    Pocket holds the 86x120 shell (+clearance); window lets the card show /
    be pushed; front semicircle is a finger relief for removal. Sits on z=0."""
    outer = box(100, 134, 8, 50, 67, 4)
    pocket = box(HOLDER_W + 2, HOLDER_H + 2, 5, 50, 67, 5.5)   # top recess z3..8
    window = box(66, 92, 12, 50, 67, 4)                        # through view
    relief = cyl(30, 12, 50, 0, 4)                             # front finger slot
    return cut(outer, [pocket, window, relief])


def press_base():
    """Base plate with a front nest recess and rear hinge knuckles. Sits on z=0;
    bolts to the enclosure floor. Hinge-pin axis is along X at the rear."""
    base = box(190, 150, 10, 95, 75, 5)
    nest_recess = box(102, 136, 4.5, 95, 73, 7.75)            # holds slab_nest
    relief = cyl(36, 12, 95, 5, 5)                            # front finger relief
    mounts = [cyl(M3, 14, x, y, 5) for x, y in
              ((15, 15), (175, 15), (15, 120), (175, 120))]   # to floor
    plate = cut(base, [nest_recess, relief, *mounts])
    # Rear hinge knuckles (gap between them receives the arm knuckle).
    kn_l = box(24, 9, 24, 67, 145.5, 22)                     # x 55..79
    kn_r = box(24, 9, 24, 123, 145.5, 22)                    # x 111..135
    solid = union([plate, kn_l, kn_r])
    pin = cyl(PIN_D, 120, 95, 145.5, 28, axis="x")           # through both knuckles
    return cut(solid, [pin])


def press_platen():
    """Flat platen that presses the holder's top shell squarely. Foam pad recess
    on the underside (z 0..2). Bolts to the arm via 2 holes. Sits on z=0."""
    plate = box(96, 124, 8, 48, 62, 4)
    foam = box(86, 120, 2, 48, 62, 1)                        # underside recess
    mounts = [cyl(M3, 10, 48, y, 4) for y in (42, 82)]       # to arm, 40 mm apart
    return cut(plate, [foam, *mounts])


def press_arm():
    """Hinged lever. Rear knuckle (pivot, Y-axis hole) fits the base gap; handle
    at the far end; 2 holes mount the platen. Printed flat (z = thickness)."""
    bar = box(210, 40, 12, 105, 20, 6)
    handle = box(34, 40, 16, 193, 20, 12)                    # raised grip end
    solid = union([bar, handle])
    holes = [
        cyl(PIN_D, 60, 14, 20, 6, axis="y"),                 # pivot (Y axis)
        cyl(M3, 16, 55, 20, 6),                              # platen mount
        cyl(M3, 16, 95, 20, 6),                              # platen mount (40 apart)
    ]
    return cut(solid, holes)


PARTS = {
    "corner_bracket": corner_bracket,   # x8
    "reg_stop": reg_stop,               # x2
    "phone_cradle": phone_cradle,       # x1
    "slab_nest": slab_nest,             # x1
    "press_base": press_base,           # x1
    "press_platen": press_platen,       # x1
    "press_arm": press_arm,             # x1
}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_all():
    os.makedirs(STL_DIR, exist_ok=True)
    meshes = {}
    for name, fn in PARTS.items():
        m = fn()
        m.export(os.path.join(STL_DIR, f"{name}.stl"))
        meshes[name] = m
        ext = m.bounding_box.extents
        print(f"{name:16s} watertight={m.is_watertight!s:5s} "
              f"bbox={ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f} mm")
    return meshes


def render_exploded(meshes):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except Exception as exc:  # pragma: no cover
        print(f"(render skipped: {exc})")
        return
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    # Exploded placement: (translation, colour) per part.
    layout = {
        "press_base": ((0, 0, 0), "#9ecae1"),
        "slab_nest": ((0, 0, 70), "#fdae6b"),
        "press_platen": ((0, 0, 150), "#a1d99b"),
        "press_arm": ((-40, 230, 150), "#bcbddc"),
        "phone_cradle": ((230, 0, 0), "#d9d9d9"),
        "corner_bracket": ((230, 200, 0), "#fc9272"),
        "reg_stop": ((150, 200, 0), "#c994c7"),
    }
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    allpts = []
    for name, (offset, color) in layout.items():
        m = meshes[name].copy()
        m.apply_translation(offset)
        tris = m.triangles
        allpts.append(m.vertices)
        coll = Poly3DCollection(tris, alpha=0.92, facecolor=color,
                                edgecolor=(0, 0, 0, 0.12), linewidths=0.2)
        ax.add_collection3d(coll)
        c = m.bounding_box.centroid
        ax.text(c[0], c[1], m.bounds[1][2] + 8, name, fontsize=7, ha="center")
    pts = np.vstack(allpts)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = (hi - lo).max() / 2.0
    mid = (hi + lo) / 2.0
    ax.set_xlim(mid[0] - span, mid[0] + span)
    ax.set_ylim(mid[1] - span, mid[1] + span)
    ax.set_zlim(mid[2] - span, mid[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=22, azim=-60)
    ax.set_axis_off()
    ax.set_title("SlabStation Mini — printed parts (exploded)", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(PREVIEW_DIR, "parts_exploded.png"), dpi=130,
                facecolor="white")
    plt.close(fig)
    print(f"wrote {PREVIEW_DIR}/parts_exploded.png")


def main():
    meshes = build_all()
    render_exploded(meshes)


if __name__ == "__main__":
    main()
