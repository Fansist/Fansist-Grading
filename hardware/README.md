# SlabStation Mini — hardware files

CAD/manufacturing files for the **Fansist SlabStation Mini**, the tabletop
card **imaging + slabbing** device. The full spec/RFQ a manufacturer can quote
from is [`docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md`](../docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md).

Design targets: **< $200 BOM**, **< $500 retail**, fits on a desk
(240 × 240 × 320 mm).

## What's here

```
generate_panels.py     Parametric generator for the laser-cut DXF panels.
dxf/                    Laser-cut outlines (mm, DXF R2010, layers CUT/ENGRAVE):
  bottom.dxf  top.dxf  back.dxf  side_left.dxf  side_right.dxf  front.dxf
  nest_shelf.dxf            5 mm structural panels
  diffuser_3mm.dxf         3 mm frosted acrylic (cut x2)
  background_insert.dxf    board reference
  nest_sheet_5mm.dxf       all 5 mm panels nested on one stock sheet
preview/nest_sheet.png     render of the nest sheet for a quick visual check
```

A laser shop can quote directly from the `dxf/` files. The 3D-printed/moulded
parts (corner brackets, phone cradle, slab nest, press platen, lever,
registration stops) are specified dimensionally in the spec; STEP/STL are to be
modelled on award (see spec §16).

> **Rev A:** geometry is for quoting and a first physical prototype. Verify fit
> and adapt the joinery to the chosen corner brackets / slab holder before any
> production tooling.

## Regenerating the DXFs

Edit the parameters at the top of `generate_panels.py` (enclosure size, material
thickness, hole/aperture sizes) and re-run:

```bash
pip install -r hardware/requirements.txt
python hardware/generate_panels.py
```

This rewrites everything in `dxf/` and refreshes `preview/nest_sheet.png`.
