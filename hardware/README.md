# SlabStation Mini — hardware files

CAD/manufacturing files for the **Fansist SlabStation Mini**, the tabletop
card **imaging + slabbing** device. The full spec/RFQ a manufacturer can quote
from is [`docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md`](../docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md).

Design targets: **< $200 BOM**, **< $500 retail**, fits on a desk
(240 × 240 × 320 mm).

## What's here

```
generate_panels.py     Parametric generator for the laser-cut DXF panels.
generate_parts.py      Parametric generator for the 3D-printed STL parts.
dxf/                    Laser-cut outlines (mm, DXF R2010, layers CUT/ENGRAVE):
  bottom.dxf  top.dxf  back.dxf  side_left.dxf  side_right.dxf  front.dxf
  nest_shelf.dxf            5 mm structural panels (MDF)
  diffuser_3mm.dxf         3 mm frosted acrylic (cut x2)
  background_insert.dxf    board reference
  nest_sheet_5mm.dxf       all 5 mm panels nested on one stock sheet
stl/                    Watertight 3D-printed solids (mm):
  press_base.stl  press_arm.stl  press_platen.stl   hinged lever press
  slab_nest.stl                                      registers the one-touch holder
  phone_cradle.stl                                   phone over the aperture
  corner_bracket.stl (x8)                            enclosure joinery
  reg_stop.stl (x2)                                  imaging-nest card stops
preview/nest_sheet.png       render of the laser nest sheet
preview/parts_exploded.png   exploded render of the printed parts
```

A laser shop quotes directly from `dxf/`; a print farm / injection moulder from
`stl/`. Full context, BOM and tolerances are in
[`docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md`](../docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md).

> **Rev B:** all design decisions are locked (spec §18). Geometry is for quoting
> and a first physical prototype — verify fit (joint clearances, holder pocket,
> platen travel) before production tooling.

## Regenerating

Edit the parameters at the top of either generator (enclosure size, material
thickness, holder dimensions, hole sizes) and re-run:

```bash
pip install -r hardware/requirements.txt
python hardware/generate_panels.py   # -> dxf/  + preview/nest_sheet.png
python hardware/generate_parts.py    # -> stl/  + preview/parts_exploded.png
```
