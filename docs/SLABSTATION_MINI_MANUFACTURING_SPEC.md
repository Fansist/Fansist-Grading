# Fansist SlabStation Mini — Manufacturing Specification & RFQ (Rev B)

**Product:** Tabletop trading-card **imaging + slabbing** device
**Document type:** Manufacturing specification / Request for Quote (RFQ)
**Revision:** B — **all design decisions locked** (was Rev A: choices open)
**Date:** 2026-06-14
**Prepared for:** Contract manufacturer / fabrication & assembly supplier

> **What I'm asking you (the manufacturer) to do:** review this spec, give DFM
> feedback, and quote (a) a first-article prototype and (b) batch pricing at 100 /
> 500 / 1000 units. **Every configuration choice is locked — see §18.** CAD is
> already provided: **laser-cut DXF panels** in `/hardware/dxf/` and **STL solids
> for every printed part** in `/hardware/stl/` (§16). Geometry is Rev B, for
> quoting and a first physical prototype; validate fit before production tooling.

---

## 1. Product summary & intent

The SlabStation Mini lets a user (hobby shop, card seller, collector) **capture a
consistent, glare-controlled photo of a trading card and then encapsulate that
card in a protective "slab" case** — on a desktop, at low cost. The photo is
analysed by companion software (separate product) that grades the card; the
device's job is purely the **physical**: repeatable imaging + clean slab
insertion.

It is deliberately a **semi-automatic, manual-press** device (no robotics, no
ultrasonic welding, no machine-vision camera) so it can hit the cost and size
targets below. Image *quality* comes from controlled, diffuse, cross-polarised
lighting and fixed geometry — not from an expensive camera.

### Two functional modules in one chassis
1. **Imaging bay** (upper) — a small light box: even diffuse LED lighting,
   cross-polariser to kill glare on holo/foil cards, a neutral background, a
   card nest with registration, and a top aperture the user's **phone** (or an
   optional camera module) shoots straight down through.
2. **Slab press** (lower/front) — a registration cradle holding an off-the-shelf
   two-piece card holder; a hand **lever press** seats the card and closes the
   two halves squarely without cracking.

---

## 2. Targets & constraints (hard requirements)

| Requirement | Target | Notes |
|---|---|---|
| **Bill-of-materials cost** | **< US$200 / unit (prototype qty)** | Baseline config lands ≈ $128; see §5 |
| **Retail price** | **< US$500** | BOM drops to ≈ $42 at 500 units → ample margin |
| **Footprint (must fit on a desk)** | **≤ 250 × 250 mm**, **≤ 330 mm tall** | Baseline 240 × 240 × 320 mm |
| **Mass** | ≤ ~3.5 kg | MDF baseline; lighter in acrylic/ABS |
| **Power** | 5 V DC via certified USB adapter (external) | No mains wiring inside the product (keeps compliance simple) |
| **Camera** | User's smartphone (baseline) | Optional integrated module, §4.2 / §18 |
| **Slab** | Off-the-shelf one-touch or screw-down holder | Device does not mould slabs |
| **Assembly** | Flat-pack + hand tools, < 30 min | DFM target |

---

## 3. General arrangement

```
   TOP  (camera aperture Ø75; phone cradle clips on top)
   ┌───────────────────────────────────────────────┐  ← 240 mm wide
   │  [ phone / camera shoots straight DOWN ]       │
   │ ░░░░░░░░░░░░░ diffuser ░░░░░░░░  diffuser ░░░░░ │   IMAGING BAY
   │ ▓ LED ▓                                ▓ LED ▓  │   (cross-polarised,
   │            ┌───── card nest ─────┐             │    even, glare-free)
   │            │  card lies FACE-UP  │             │   height ≈ 200 mm
   │            └─────────────────────┘             │
   │              (neutral background)              │
   ├───────────────────────────────────────────────┤  ← nest shelf @ ~70 mm
   │  SLAB PRESS:  lever ↓                           │
   │     ┌──────────────────────────┐               │   SLAB PRESS
   │     │ slab nest: bottom shell + │  ◀ hand lever │   (manual, square close)
   │     │ inner frame + card + top  │               │
   │     └──────────────────────────┘               │
   └───────────────────────────────────────────────┘  ← 320 mm tall
        USB power in (rear)        4× rubber feet
```

Front panel has a large **access window** so the user reaches in to place the
card and to load/remove the slab. Imaging and pressing are done as two sequential
manual steps.

---

## 4. Sub-assembly specifications

### 4.1 Enclosure (laser-cut flat-pack)
- **Panels:** 7 structural panels (bottom, top, back, 2 sides, front, internal
  nest shelf). **Material:** 5 mm MDF (baseline) **or** 5 mm black acrylic
  (premium finish). DXF geometry supplied — see §16 and `/hardware/dxf/`.
- **Joinery (Rev A):** butt joints with **3D-printed corner brackets / standoffs**
  and M3 screws (holes provided). *DFM option:* convert to finger/tab-and-slot
  joints to cut part count and screws — please advise (§18).
- **Finish:** MDF sealed matte **black** inside (kills stray reflections), exterior
  per brand. Acrylic: matte black interior face mandatory.
- **Top panel:** Ø75 mm camera aperture + 4× M3 phone-cradle fixings + rear
  wiring notch.
- **Front panel:** 180 × 230 mm access window.
- **Nest shelf:** 230 × 230 mm with an 80 × 110 mm card viewing window,
  registration-stop fixings, and side-support fixings.

### 4.2 Imaging module
- **Lighting:** one high-CRI (≥90) **5000–5600 K** LED strip, ~0.5 m, 5 V,
  mounted on the two side walls behind diffuser panels for even, diffuse light.
- **Diffusers:** 2× 3 mm frosted acrylic panels (60 × 280 mm) in front of the LEDs.
- **Cross-polarisation (glare control):** linear polariser film over the LED
  diffusers + a **clip-on linear polariser** on the phone lens, crossed ~90°.
  This is the single most important image-quality feature for foil/holo cards.
- **Background:** interchangeable matte neutral insert (mid-grey default; black &
  white spares) seated under the card nest.
- **Camera — LOCKED: smartphone only.** The user's phone lies screen-up in a
  printed **`phone_cradle`** (STL provided) that clips over the top aperture; the
  rear camera looks straight down through the cradle's Ø40 hole + the Ø75 panel
  aperture. Chosen because it is free, the highest image quality available, and
  adds no electronics or electrical-compliance burden. (An integrated camera is a
  possible *future* SKU, deliberately out of this build.)

### 4.3 Slab press module — LOCKED: manual hinged lever, one-touch holder
- **Slab — LOCKED:** common **"one-touch" magnetic** two-piece acrylic holder,
  **reference outer 86 × 120 × 10 mm** (standard 35 pt card). The device does not
  manufacture holders — they are a cheap consumable accessory; ship 3 starters.
  (Screw-down holders are *not* supported in this build — one mechanism keeps cost
  and part count down.)
- **Mechanism — LOCKED: hinged lever press** (STL parts provided). The user drops
  the open holder (bottom shell + card + top shell resting) into the **`slab_nest`**,
  which registers it on the **`press_base`**; swings the hinged **`press_arm`**
  down; and presses the handle. The **`press_platen`** (with a glued EVA foam pad)
  contacts the top shell and closes the two halves **squarely** so the magnets seat
  without cracking the acrylic. Hinge = one Ø5 steel pin; gravity/hand return.
  Chosen over linear-rail/screw presses: fewest parts, self-aligning, no precision
  bearings, fully 3D-printable, reliable at the low force a magnetic holder needs.
- **Critical function:** even, square closing; the nest holds the card central in
  the holder within **± 0.3 mm** so the slabbed card looks centred. The platen is a
  separate, swappable plate so a future holder size is a one-part change.

---

## 5. Bill of Materials (target < $200)

Prototype-qty unit costs (low-volume, indicative USD) and an estimate at 500
units. The **baseline** config (smartphone camera, one-touch press) is the costed
build; the integrated camera is an **optional** add.

| # | Item | Qty | Material / spec | Process | Proto $ | @500 $ |
|---|---|---|---|---|--:|--:|
| 1 | Enclosure panels (7) | 1 set | 5 mm MDF (or acrylic) | Laser cut | 30 | 8 |
| 2 | Printed parts set | 1 set | PLA/PETG → ABS at volume — `corner_bracket`×8, `phone_cradle`, `slab_nest`, `press_base`, `press_arm`, `press_platen`, `reg_stop`×2 (STL provided) | FDM → injection | 22 | 7 |
| 3 | LED strip, hi-CRI 5000 K | 0.5 m | 5 V, ≥90 CRI + connectors | COTS | 8 | 3 |
| 4 | Diffuser panels (2) | 2 | 3 mm frosted acrylic | Laser cut | 6 | 2 |
| 5 | Polariser film + clip-on lens polariser | 1 | Linear polariser (A5 sheet + clip) | COTS/cut | 11 | 4 |
| 6 | 5 V USB power kit | 1 | **Certified** 5 V/2 A adapter + cable + inline switch | COTS | 9 | 4 |
| 7 | Press hardware | 1 set | Ø5×80 hinge pin (bolt) + locknut; EVA foam platen pad | COTS | 6 | 2 |
| 8 | Fasteners & inserts | 1 set | M3 screws, nuts, heat-set inserts | COTS | 8 | 3 |
| 9 | Feet / adhesive / cable mgmt | 1 set | Rubber feet, VHB, ties | COTS | 6 | 2 |
| 10 | Background inserts (3) | 1 set | Matte board, grey/black/white | Die-cut | 4 | 1.5 |
| 11 | Starter slab holders | 3 | One-touch magnetic, 35 pt | COTS accessory | 5 | 2.5 |
| 12 | Packaging + printed manual | 1 | Box, foam/insert, QSG | COTS/print | 7 | 3 |
| | **BOM TOTAL (as built)** | | | | **≈ 122** | **≈ 42** |

**Comfortably under the < $200 BOM target (~$122 at prototype qty).** At 500 units
the BOM (~$42) supports the < $500 retail price with very healthy margin — and the
product could retail far lower if positioned aggressively. *(An integrated-camera
SKU would add ≈ $35–55 and remain < $200, but is intentionally out of this build.)*

---

## 6. Mechanical drawings, tolerances & CAD

- **Units:** millimetres. **General tolerance:** ±0.3 mm on laser-cut features;
  ±0.2 mm on printed/moulded mating features unless noted.
- **Critical-to-quality (CTQ) dimensions:**
  - Camera aperture concentric with the card-nest centre (±1 mm) — keeps the card
    centred in frame.
  - Card-nest registration → card central in the slab inner frame: **±0.3 mm**.
  - Press platen travel square to the nest: **≤ 0.5°** tilt at full stroke.
  - Camera working distance fixed/repeatable so a card fills the frame
    consistently (±2 mm).
- **Provided now:** **laser-cut DXF** for every flat panel (R2010, mm, layers
  `CUT`/`ENGRAVE`) in `/hardware/dxf/`, and **watertight STL solids for every
  printed part** in `/hardware/stl/`. Previews in `/hardware/preview/`.
- **To be produced for tooling (quote please):** a STEP assembly and dimensioned
  GA/detail drawings carrying the §6 tolerances. Geometry is fully defined by the
  DXF + STL + this spec.

---

## 7. Materials & finishes

**Material — LOCKED:** structural panels are **5 mm MDF, sealed matte black**
(cheapest, robust, and a matte-black interior is exactly what the imaging bay
needs — no reflections). Cast acrylic is an optional premium finish, not the
default.

| Part | Material | Finish |
|---|---|---|
| Structural panels | **5 mm MDF** (acrylic = premium option) | Interior **matte black** (mandatory); exterior matte black |
| Printed/moulded parts | PLA/PETG (proto) → ABS/PC (production) | Matte black |
| Diffusers | 3 mm frosted/opal acrylic | As supplied |
| Background inserts | Matte board / PVC | Non-glossy, neutral |
| Fasteners | Zinc/black steel, M3/M4 | — |

All plastics/colourants **RoHS/REACH** compliant. Avoid glossy interior surfaces
anywhere in the imaging bay (they cause reflections).

---

## 8. Electrical & safety

- **Low-voltage only inside the product:** 5 V DC from an **externally certified**
  USB power adapter. **No mains voltage** is wired inside — this keeps the product
  out of mains-electrical certification scope (the adapter carries its own
  CE/UKCA/FCC/UL marks).
- LED strip current ≤ ~1 A; inline switch on the 5 V line; strain-relieved entry
  at the rear notch.
- Optional camera module powered from the same 5 V rail (verify budget ≤ adapter
  rating).
- **Pinch hazard:** the lever press has a moving platen — add a guard lip and a
  warning label; design lever travel so fingers can't enter the nest at close.

**Target compliance/marks:** RoHS, REACH, FCC Part 15 (if integrated electronics),
CE/UKCA self-declaration for a 5 V LED product. *Engage a compliance reviewer
before sale; this list is a starting point, not certification.*

---

## 9. Assembly sequence (target < 30 min, hand tools)

1. Press heat-set inserts into printed brackets (if used).
2. Screw corner brackets to **bottom**, **back**, and **side** panels.
3. Fit **nest shelf** to the side supports; clip in registration stops.
4. Mount LED strip + diffusers to the side walls; route 5 V to the rear notch +
   switch; apply polariser film over diffusers.
5. Attach **front** (access window) and **top** (aperture) panels; clip on the
   phone cradle.
6. Assemble the **slab press**: bolt `press_base` to the enclosure floor → glue
   the EVA pad into `press_platen` and screw the platen to `press_arm` (40 mm
   centres) → hinge `press_arm` to the base with the Ø5 pin + locknut → drop
   `slab_nest` into the base recess.
7. Insert background, fit feet, attach labels, functional test (§11), pack (§10).

---

## 10. Packaging & labelling

- Retail box sized to the 240 × 240 × 320 mm unit + accessories; foam or moulded-
  pulp insert; ships flat-pack **or** pre-assembled (quote both).
- Includes: 3 starter slab holders, 3 background inserts, clip-on polariser, USB
  adapter + cable, hex driver, printed Quick-Start Guide.
- Carton & label: barcode, model, batch/lot, country of origin, compliance marks.

---

## 11. Quality acceptance & first-article test plan

Every unit (or AQL sample) must pass:
1. **Fit:** all panels assemble without forcing; no rattles; access window clear.
2. **Light:** LEDs even across the nest (no hotspots); cross-polariser visibly
   reduces glare on a reference holo card.
3. **Imaging:** a reference card photographed through the aperture is in focus,
   fills the frame consistently, and is glare-free (pass = companion software
   detects & grades it).
4. **Press:** closes a one-touch holder squarely; card central in the inner frame
   within ±0.3 mm; no acrylic cracking over 20 cycles; return spring lifts fully.
5. **Electrical:** switch works; no flicker; current within adapter rating;
   strain relief secure.
First-article: full dimensional report against the DXF/STEP + the above.

---

## 12. Process / tooling per part

| Part | Prototype | Production (≥500) |
|---|---|---|
| Enclosure panels | Laser cut MDF/acrylic | Laser cut, or thermoform/injection shell |
| Brackets, cradle, press parts | FDM 3D print | Injection mould (ABS/PC) |
| Diffusers | Laser cut acrylic | Laser cut / extruded profile |
| Background inserts | Die/laser cut | Die cut |
| Slab holders | COTS | COTS (or own tooling — out of scope here) |

Injection tooling for the printed-parts family is the main NRE at volume; amortised
across ≥500 units it still lands the BOM well under target.

---

## 13. Volume pricing & cost-down

- Baseline BOM: **~$128 @ proto → ~$44 @ 500 units** (material + COTS savings +
  injection vs. FDM).
- Cost-down levers: injection-mould the printed family; switch MDF→thermoformed
  shell; buy LED/polariser/adapter at volume; combine diffuser+polariser into one
  laminated part.
- Retail at < $500 is comfortable; the design has headroom to retail much lower if
  desired.

---

## 14. Deliverables expected from the manufacturer

1. DFM review + redlines on this spec and the DXF.
2. Itemised quote: NRE/tooling + unit price at 1 (proto) / 100 / 500 / 1000.
3. Lead times (proto + production), MOQ, payment terms.
4. First-article samples + dimensional report.
5. Material certs (RoHS/REACH) and the power-adapter compliance certificates.

---

## 15. What's in/out of scope for this RFQ

- **In:** the device (enclosure, imaging optics/lighting, manual slab press),
  assembly, packaging, starter accessories.
- **Out:** the grading **software** (separate); manufacture of the slab **holders**
  themselves (sourced COTS); any cloud/app services.

---

## 16. File manifest (provided / to-produce)

**Laser-cut (5 mm MDF unless noted) — DXF R2010, mm:**
- `hardware/dxf/bottom.dxf`, `top.dxf`, `back.dxf`, `side_left.dxf`,
  `side_right.dxf`, `front.dxf`, `nest_shelf.dxf` — structural panels.
- `hardware/dxf/diffuser_3mm.dxf` — 3 mm frosted acrylic (×2).
- `hardware/dxf/background_insert.dxf` — board reference.
- `hardware/dxf/nest_sheet_5mm.dxf` — all 5 mm panels nested on one sheet.

**3D-printed parts — STL solids (watertight, mm):**
- `hardware/stl/press_base.stl`, `press_arm.stl`, `press_platen.stl` — hinged press.
- `hardware/stl/slab_nest.stl` — registers the one-touch holder.
- `hardware/stl/phone_cradle.stl` — phone holder over the aperture.
- `hardware/stl/corner_bracket.stl` (×8) — enclosure joinery.
- `hardware/stl/reg_stop.stl` (×2) — imaging-nest card registration.

**Generators & previews (re-run to change any dimension):**
- `hardware/generate_panels.py` → DXF; `hardware/generate_parts.py` → STL.
- `hardware/preview/nest_sheet.png`, `hardware/preview/parts_exploded.png`.

**To produce on award (quoted):** a STEP assembly and GA/detail drawings with the
§6 tolerances, plus the LED wiring diagram. All geometry is fully defined by the
DXF + STL + this spec.

---

## 17. Revision history
- **Rev A (2026-06-14):** initial release; configuration choices left open.
- **Rev B (2026-06-14):** **all decisions locked** (§18); hinged-lever press
  designed; **STL solids provided for every printed part**; BOM finalised (~$122).
  **Not yet validated by a physical prototype** — expect minor changes after first
  article (fit of joints, holder pocket, platen travel).

---

## 18. Locked design decisions (Rev B)

Every previously-open choice is now decided; build to these:

1. **Camera — smartphone only.** Printed `phone_cradle` over the aperture. No
   integrated camera in this build (free, best image, no electronics/compliance).
2. **Slab — one-touch magnetic only**, reference outer **86 × 120 × 10 mm**. No
   screw-down variant (single mechanism = lowest cost/part count).
3. **Press — manual hinged lever** (`press_base` + `press_arm` + `press_platen` +
   `slab_nest`, one Ø5 hinge pin). No linear rails, springs, or motors.
4. **Joinery — printed corner brackets + M3** (`corner_bracket` ×8). Panels carry
   the matching holes; no finger joints.
5. **Material — 5 mm MDF, matte black** (interior mandatory matte to kill
   reflections). Acrylic is an optional premium finish only.
6. **Ship pre-assembled** retail (factory assembles the flat-pack); fold-flat is a
   cost option if the buyer prefers.

*One thing to confirm against your supply chain:* the **exact one-touch holder SKU**
you'll bundle, so we final-tune the `slab_nest` pocket and `press_platen` to its
real measured dimensions (Rev B uses the 86 × 120 × 10 mm reference).

---

*Companion software (card detection, deskew, and four-factor grading —
centering/corners/edges/surface) is a separate product in this repository; the
SlabStation Mini simply produces the consistent image it grades and the slab it
ships in. A larger, fully-automated industrial line is documented separately in
`docs/HARDWARE_BLUEPRINT.md`.*
