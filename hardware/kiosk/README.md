# ScanSlab kiosk — CAD (Rev A, general arrangement)

Parametric CAD for the kiosk in
[`docs/SCANSLAB_KIOSK_DESIGN.md`](../../docs/SCANSLAB_KIOSK_DESIGN.md). Kiosk
envelope **600 × 600 × 1500 mm**. Regenerate any of it from one script:

```bash
pip install -r ../requirements.txt        # ezdxf + trimesh + matplotlib
python generate_kiosk.py
```

## What's here

```
generate_kiosk.py        Parametric generator (edit dims at the top, re-run).
stl/                     3D solids (mm), all watertight:
  cabinet_{front,back,side_left,side_right,top,bottom}.stl  sheet-metal panels (2 mm)
  ipc_bay.stl  laser_station.stl  slab_station.stl          internal module envelopes
  scan_dome.stl                                             LED photometric dome + camera
  hmi.stl  output_tray.stl                                  HMI + slab output tray
  slab_v2.stl                                               redesigned slab (grade panel + code window)
dxf/                     Sheet-metal cabinet flat patterns (R2010, mm; CUT/BEND/ENGRAVE):
  cabinet_front.dxf      HMI window + card slot + tray opening
  cabinet_back.dxf       service door + vents + cable gland
  cabinet_side_left/right.dxf, cabinet_top.dxf, cabinet_bottom.dxf
  cabinet_nest.dxf       all six panels on one stock sheet
preview/                 kiosk_assembly.png, cabinet_nest.png, cabinet_front.png
```

## Scope (be honest)

This is a **Rev A general-arrangement** model — correctly **dimensioned and laid
out** for layout, integration and quoting. The bought-in modules (laser marker,
camera + LED-dome optics, ultrasonic welder, IPC) are represented by their
**envelopes**, not internal-mechanism CAD; swap each envelope for the chosen
COTS unit's real model during detailed design. A sheet-metal shop can quote the
`dxf/` flat patterns directly; the `stl/` give the 3D layout and the new slab.

The **slab_v2** is the actual new part the kiosk produces: a card window, a
sealed **code-label** recess, and a frosted **grade panel** left blank until the
grade is laser-marked at pick-up.
