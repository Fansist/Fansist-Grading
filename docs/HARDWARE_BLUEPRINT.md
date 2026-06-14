# Automated Card Imaging & Slabbing Machine — Full Blueprint (v1)

> **Codename:** *Fansist AutoSlab*
> **Purpose:** Take a raw trading card, capture grading-quality images of both
> faces, run the grading software, then encapsulate ("slab") the card in a
> sealed, labelled case — with full per-card traceability.
>
> This document is the **engineering blueprint**: system architecture,
> mechanical/optical/electrical design, the encapsulation mechanism, control &
> software integration, bill of materials, process sequence, cycle-time budget,
> safety, calibration, a phased build roadmap, a risk register, and the open
> design decisions with recommended defaults.
>
> It is the hardware companion to this repo's software pipeline
> (`card_detector.py` → `centering.py` → `grading.py`). The imaging station is
> the physical front-end that *feeds* that pipeline; the slabbing station is the
> physical back-end that acts on its verdict.

---

## Table of contents

1. [Scope, goals & assumptions](#1-scope-goals--assumptions)
2. [Open design decisions & recommended baseline](#2-open-design-decisions--recommended-baseline)
3. [System architecture & general arrangement](#3-system-architecture--general-arrangement)
4. [Process sequence (station-by-station)](#4-process-sequence-station-by-station)
5. [Subsystem 1 — Card infeed & singulation](#5-subsystem-1--card-infeed--singulation)
6. [Subsystem 2 — Transport & handling](#6-subsystem-2--transport--handling)
7. [Subsystem 3 — Cleaning / de-dust](#7-subsystem-3--cleaning--de-dust)
8. [Subsystem 4 — Imaging station (the critical one)](#8-subsystem-4--imaging-station-the-critical-one)
9. [Subsystem 5 — Slab assembly & sealing](#9-subsystem-5--slab-assembly--sealing)
10. [Subsystem 6 — Label printing & application](#10-subsystem-6--label-printing--application)
11. [Subsystem 7 — Outfeed & reject handling](#11-subsystem-7--outfeed--reject-handling)
12. [Electrical & control architecture](#12-electrical--control-architecture)
13. [Software integration with the grading pipeline](#13-software-integration-with-the-grading-pipeline)
14. [Cycle-time & throughput budget](#14-cycle-time--throughput-budget)
15. [Tolerances & key engineering challenges](#15-tolerances--key-engineering-challenges)
16. [Calibration & quality assurance](#16-calibration--quality-assurance)
17. [Safety & compliance](#17-safety--compliance)
18. [Bill of materials (representative)](#18-bill-of-materials-representative)
19. [Phased build roadmap](#19-phased-build-roadmap)
20. [Risk register](#20-risk-register)
21. [Reference data & drawing sheet list](#21-reference-data--drawing-sheet-list)

---

## 1. Scope, goals & assumptions

### In scope
- Single-card-at-a-time automated flow: **load → clean → image (both faces) →
  grade → encapsulate → label → eject**.
- Grading-quality, glare-controlled imaging of front and back.
- Mechanical encapsulation into a sealed slab.
- Tight coupling to the existing software pipeline and a clean extension path
  for the future corner/edge/surface graders.

### Out of scope (v1 of the machine)
- Bulk/parallel processing of many cards simultaneously (the line is serial).
- Automatic *removal* of cards from existing sleeves/toploaders/old slabs
  (cards are presented raw or in a soft penny sleeve).
- Authentication / counterfeit detection (label/cert traceability only).
- Robotic palletising of finished slabs into long-term storage.

### Baseline card & material assumptions
| Parameter | Value / range | Note |
|---|---|---|
| Card footprint | 63.5 × 88.9 mm (2.5 × 3.5 in), standard | Mini/tarot/oversize are a future fixture-swap |
| Card thickness | 0.30 mm (35 pt) typical; support 0.30–1.2 mm (35–130 pt) | Thick/relic/patch cards need a deeper slab cavity & adjustable nest |
| Card flatness | ≤ 1.5 mm bow over diagonal | Heavily warped cards are flagged, not forced |
| Presentation | Raw or in a soft penny sleeve, face-up stack | Sleeve-on changes optics slightly (see §8) |
| Slab outer (baseline) | ~ 91 × 130 × 6 mm "credit-card-case" form | Tooling-defined; see §9 |

**Governing assumption (inherited from the software):** imaging quality
dominates result quality. The machine's reason-to-exist is to make lighting,
geometry, and background *repeatable* so the classic-CV pipeline is reliable —
something a handheld phone photo cannot guarantee.

---

## 2. Open design decisions & recommended baseline

These four choices fork the build. The blueprint is written around the
**Recommended** column; alternatives are carried where they materially change a
subsystem.

| # | Decision | Options | **Recommended baseline** | Why |
|---|---|---|---|---|
| D1 | **Sealing method** | (a) Ultrasonic-welded shell (industry standard, permanent, tamper-evident) · (b) Screw-down acrylic holder (reusable, no welder) · (c) Magnetic "one-touch" (press-fit) | **(a) Ultrasonic weld**, with **(b) screw-down** as the Phase-2 bring-up stand-in | Welded = a "real" slab; screw-down lets us automate everything *except* custom shell tooling first |
| D2 | **Transport topology** | (a) Rotary indexing dial w/ fixed stations · (b) Linear gantry pick-and-place · (c) Vacuum conveyor | **(a) Rotary dial** for the production cell; **(b) gantry** for the Phase-1 imaging-only prototype | Fixed sequence + high repeatability + easy pipelining |
| D3 | **Both-sides imaging** | (a) Dual camera over a glass platen (no flip) · (b) Single camera + mechanical flip | **(a) Dual camera**, AR-coated platen, cross-polarised | Removes a moving subsystem & a major defect/cycle-time source |
| D4 | **Throughput target** | (a) Benchtop, sequential ~80–120 cards/h · (b) Pipelined dial ~300–450 cards/h | **Design for (b), commission at (a)** | Same mechanics; pipelining is a controls/staffing decision later |

> If any of these should change (e.g. you specifically want a *screw-down*
> product, or only ever a benchtop single-shot rig), the affected subsystems are
> self-contained and called out below.

---

## 3. System architecture & general arrangement

The machine is one enclosed cell built on an aluminium-extrusion frame with a
central **rotary indexing dial** carrying card **nests**. Stations sit around
the dial; the imaging station and the slab-sealing station are the two
"expensive" stations and get the most engineering attention.

```
                       ENCLOSURE (interlocked, light-shrouded)
   ┌───────────────────────────────────────────────────────────────────────┐
   │                                                                         │
   │   [S1] INFEED            [S2] CLEAN          [S3] IMAGE                  │
   │   hopper + vacuum  ──▶   ionizer + air  ──▶  dome + cross-pol           │
   │   singulator             knife + brush       dual camera (F/B)          │
   │        │                                          │                     │
   │        ▼                ROTARY  INDEXING  DIAL     ▼                     │
   │     ┌──────────────────────────────────────────────────┐               │
   │     │   ( 8 nests on a precision index, ~45° pitch )    │               │
   │     └──────────────────────────────────────────────────┘               │
   │        ▲                                          │                     │
   │        │                                          ▼                     │
   │   [S8] OUTFEED          [S7] WELD          [S5/6] ASSEMBLE + LABEL       │
   │   good / reject  ◀──  ultrasonic horn  ◀──  shell halves + inner        │
   │   bins / stacker         + anvil nest        frame + printed label      │
   │                                                                         │
   │   IPC + GPU (grading) │ EtherCAT motion │ HMI touchscreen │ E-stop       │
   └───────────────────────────────────────────────────────────────────────┘
            Air @ 6 bar (clean/dry)        Mains 230 VAC 1Ø, ~16 A
            Footprint ≈ 1300 × 900 mm bench cell;  ≈ 1700 mm tall with light tower
```

**Subsystems (logical):**
1. Infeed & singulation (S1)
2. Transport & handling — the dial + nests (spans all stations)
3. Cleaning / de-dust (S2)
4. Imaging (S3) — feeds the software
5. Slab assembly & sealing (S5–S7)
6. Label printing & application (S6)
7. Outfeed & reject (S8)
8. Electrical/control + software integration (cross-cutting)

A serial **single-card** machine can also be built by laying these stations out
linearly with a gantry instead of a dial (Phase-1 prototype) — same subsystems,
simpler controls.

---

## 4. Process sequence (station-by-station)

| Step | Station | Action | Key sensors / feedback |
|---|---|---|---|
| 1 | S1 Infeed | Vacuum cup lifts the top card off the hopper; double-feed check; place onto nest; nest vacuum-clamps | Stack-present, vacuum-confirm, double-feed (ultrasonic/load-cell) |
| 2 | S2 Clean | Ionised air knife + soft anti-static brush remove dust/static from face-up side; (dial flips exposure or both faces cleaned at platen) | Ionizer OK, airflow OK |
| 3 | S3 Image | Dome + cross-polarised flash; **dual cameras** capture front (top cam) and back (bottom cam, through AR platen). Optional multi-angle grazing flashes for future surface module | Trigger-confirm, exposure histogram QA |
| 4 | (IPC) | Software runs detect → centering → grade; assigns cert #; decides **pass / reject / re-image** | Grading result, confidence/QA flags |
| 5 | S5 Assemble | Bottom shell half indexed into anvil nest; inner frame placed; **card transferred** from dial nest into bottom shell, vision-verified centred | Card-in-shell vision check, presence |
| 6 | S6 Label | Thermal printer prints cert label (grade, QR/cert #, date); pick-place inserts label into the label window | Print-OK, label-present, barcode read-back |
| 7 | S7 Weld | Top shell half placed; ultrasonic horn descends; **weld + hold/cool**; weld-energy/collapse monitored | Weld energy J, collapse distance, peak force |
| 8 | S8 Outfeed | Finished slab ejected to **good stacker** or **reject bin**; record written to DB; QR links to image+grade record | Slab-present, bin full |

Rejected-at-grading cards are diverted **before** assembly (returned to a reject
tray with the reason), so no shells/labels are consumed on a no-grade.

---

## 5. Subsystem 1 — Card infeed & singulation

Singulating thin, statically-charged cards reliably is the hardest *handling*
problem (worse than the slab). Design defensively.

- **Hopper:** vertical, gravity-fed, face-up magazine, capacity ~100 cards,
  spring-loaded follower or weighted pusher keeping the top card at a fixed
  pick plane. Adjustable side walls for card width tolerance.
- **Pick:** servo/pneumatic **vacuum cup** (Ø8–12 mm, low-marking silicone,
  bellows) on a short Z-axis lifts the *single* top card. Ionising bar at the
  pick zone first to break static cling between cards.
- **Double-feed detection (mandatory):** ultrasonic double-sheet sensor *or* a
  thickness gate *or* a load cell on the pick. Two-card lift → return both,
  re-pick. Cards' thickness variation (35–130 pt) means a fixed thickness gate
  must be **per-job configurable**, not hard-set.
- **Anti-stick aids:** edge air-fluffer (gentle air jet at the stack top corner)
  to float the top card; corner separators.
- **Failure handling:** N consecutive mis-picks → pause + HMI alert. No card
  present → graceful idle.

> **Sleeve-on variant:** if cards arrive in penny sleeves, the vacuum pick grabs
> the sleeve; imaging then sees through one matte/gloss sleeve layer (acceptable
> with cross-pol; flag glossy sleeves). Slab insertion must account for the
> sleeve thickness or strip it (out of v1 scope).

---

## 6. Subsystem 2 — Transport & handling

**Recommended: rotary indexing dial (D2-a).**

- **Indexer:** cam-driven or servo-driven rotary index table, 8 stops (45°
  pitch), index repeatability **≤ ±0.02 mm** at the nest. Cam indexers give
  rock-solid repeatability and a built-in dwell; a servo index gives flexible
  recipes. Baseline: **servo + harmonic/cycloidal reducer** for recipe freedom.
- **Nests (×8):** kinematic card pockets with **two fixed datum edges** + a
  spring/vacuum pull to seat the card against the datums, giving a known card
  origin for both imaging and pick-out. Vacuum hold during indexing. Nest is a
  **quick-change fixture** for different card sizes.
- **Platen at imaging:** the imaging station nest exposes the card on an
  **AR-coated optical platen** so the bottom camera sees the back face cleanly
  (D3-a, no flip). Card edges supported on a thin ledge so the imaged area isn't
  pressed against glass (avoids Newton's rings / contact marks).
- **Card transfer to slab (S5):** a second vacuum end-effector lifts the graded
  card off the dial nest and lowers it into the bottom shell half, **vision-
  guided** to centre it in the inner frame within ±0.1 mm.

*Linear-gantry alternative (Phase-1 prototype):* a 2–3 axis Cartesian gantry
with one vacuum tool moves the card between a few fixed stations. Cheaper to
build, lower throughput, but it is the fastest way to validate imaging+grading
before committing to dial tooling.

---

## 7. Subsystem 3 — Cleaning / de-dust

Dust is both a cosmetic slab defect and a false **surface** defect for the
future grader, so clean *before* imaging.

- **Ioniser bar** (DC/AC) to neutralise static so dust releases.
- **Air knife / filtered air jet** (oil-free, 0.01 µm filtered) grazing across
  the face to blow particulate off; extraction hood + filter catches it.
- **Soft anti-static brush** (goat-hair / conductive bristle) on a slow roller
  for stubborn particles — *contactless preferred for high-value cards*; make
  the brush an optional, height-set, recipe-controlled pass.
- Both faces cleaned: at the platen, top air knife + a bottom jet, or clean
  pre-flip in the gantry variant.

---

## 8. Subsystem 4 — Imaging station (the critical one)

This station is the physical embodiment of the README's imaging guidelines:
**plain background, even diffuse glare-free light, camera parallel to the card,
max resolution.** It is engineered so every capture is identical.

### 8.1 Optical geometry
- **Cameras:** two industrial machine-vision cameras (top = front, bottom =
  back through platen), **global shutter**, **24–45 MP** (e.g. Sony IMX
  Pregius/Starvis-class). 45 MP on an 89 mm long edge ≈ **~2000+ px/inch**,
  ample for corner/edge/surface detail later; 24 MP is the practical floor.
- **Lens:** for the lowest geometric distortion of the centering measurement,
  a **bi-telecentric lens** (object-space telecentric, FOV ≥ 95 mm) is ideal —
  no perspective error, constant magnification regardless of card bow/thickness.
  Telecentric optics this size are **bulky and costly**; the pragmatic baseline
  is a **low-distortion fixed focal lens** at a calibrated working distance with
  **flat-field + distortion calibration** (§16), because the software *already*
  perspective-corrects via `card_detector.four_point_transform`. **Spec
  telecentric for the centering-critical front camera if budget allows; fixed
  focal + calibration otherwise.**
- **Working distance / mount:** rigid, vibration-isolated camera bracket;
  optical axis **perpendicular** to the platen to <0.2°. No autofocus — fixed
  focus locked at the card plane (repeatability).

### 8.2 Lighting (the glare problem)
Glossy and foil/holo cards throw specular glare that destroys both centering
edges and surface inspection. Use **multiple, switchable** lighting modes,
strobed per capture:

| Mode | Hardware | Used for |
|---|---|---|
| **Diffuse dome / "cloudy-day"** | Hemispherical diffuse dome illuminator (coaxial aperture for the lens) | Even, glare-free base image → centering, full-card capture |
| **Cross-polarised** | Linear polariser film on the lights + analyser on the lens, crossed | Kills specular glare on gloss/foil → clean colour & edges |
| **Low-angle dark-field (grazing)** | Ring of LEDs at a shallow angle, 4 quadrants switchable | Reveals **scratches, dents, print lines, edge whitening** (future surface/edge module) — photometric-stereo set |
| **Back/edge light** | Edge-lit platen or rim light | **Edge chipping / whitening** silhouette (future edge module) |

All LED illuminators are **strobed** (flash) synchronously with the global-
shutter exposure for crisp, repeatable, motion-tolerant captures and long LED
life. Colour temperature fixed (e.g. 5000–5600 K, high-CRI) and **white-balance
calibrated** against a reference card.

### 8.3 Capture recipe (per face)
1. Diffuse-dome shot — primary image (feeds `card_detector` → `centering`).
2. Cross-polarised shot — glare-free colour/edge reference.
3. (Phase-3) four grazing-light shots (N/E/S/W) — surface photometric set.

The diffuse shot is the only one v1 software consumes; the rest are captured and
**stored now** so the corner/edge/surface modules can be developed against real
data without re-running cards.

### 8.4 Background
The platen/nest backdrop is a **matte, neutral, high-contrast** surface chosen
per card (dark mat behind light cards; light behind dark) — selectable insert or
a switchable back-light. This directly satisfies `card_detector`'s
high-contrast-background assumption *by construction*.

---

## 9. Subsystem 5 — Slab assembly & sealing

This is the "insert into a slab" core. A real grading slab is a **rigid clear
case that permanently and tamper-evidently encapsulates the card plus its grade
label.** The industry-standard method is an **ultrasonically welded two-piece
shell** with an **inner frame** that locates the card and prevents rattle.

### 9.1 Slab construction (baseline, D1-a)
```
  Cross-section through a sealed slab (not to scale):

   ┌──────────────────────────  TOP SHELL (clear PETG/PC)  ──────────────────────────┐
   │                                                                                  │
   │   ░░ inner frame (card-thickness spacer / well) ░░        ▓ label window ▓        │
   │   ░░ ┌────────────────────────────────┐ ░░               ▓  printed cert  ▓       │
   │   ░░ │            CARD                 │ ░░               ▓  QR + grade    ▓       │
   │   ░░ └────────────────────────────────┘ ░░                                        │
   │                                                                                  │
   └──────────────────────────  BOTTOM SHELL (clear)  ────────────────────────────────┘
          ▲ energy-director ridge runs the full weld perimeter (melts to bond) ▲
```
- **Two shell halves**, injection-moulded clear PETG or polycarbonate. One half
  carries a moulded **energy-director ridge** around the perimeter (the
  feature that focuses ultrasonic energy to form the weld).
- **Inner frame / well**: a die-cut or moulded spacer matching card thickness
  (35 / 55 / 75 / 100 / 130 pt variants) that centres the card and stops it
  sliding — selected by the grade/measurement of the card.
- **Label window**: recess for the printed cert label, sealed inside.

### 9.2 Sealing mechanism — ultrasonic welder
- **Generator** 20 kHz (or 30/35 kHz for finer parts), ~1–2 kW.
- **Converter + booster + custom horn (sonotrode)**: titanium/aluminium horn
  machined to the slab's weld-perimeter footprint, tuned to resonance.
- **Anvil/nest**: rigid fixture holding the bottom shell + card + top shell in
  registration under the horn.
- **Press**: servo or pneumatic Z press delivering controlled **trigger force**,
  **weld time/energy**, **hold/cool time**. Weld parameters are **closed-loop on
  energy (J) and collapse distance** for repeatable, leak-free seams.
- **Cycle:** descend → contact/trigger force → ultrasonic on (~0.2–0.8 s) →
  hold/cool (~0.3–0.8 s) → retract.

> **Tooling reality:** the shells (injection mould) and the matched horn are the
> **long-lead, high-cost** items ($10–40k mould; custom horn $1–5k). De-risk by
> bringing the *whole machine* up first on the **screw-down stand-in (D1-b)** —
> two CNC/3D-printed acrylic plates joined by an automated screwdriver — then
> swap in welded shells once tooling lands. The handling, vision, and controls
> are identical; only the join station changes.

### 9.3 Screw-down / one-touch alternatives
- **Screw-down (D1-b):** automated torque-screwdriver drives 4 corner screws
  through two pre-threaded acrylic plates. Reusable, no welder, no acoustic
  safety case; **not tamper-evident**, bulkier. Excellent bring-up vehicle.
- **Magnetic one-touch (D1-c):** two acrylic halves with embedded magnets;
  "sealing" is just a press. Trivial to automate, but not permanent/secure —
  fine for a demo, not for a graded product.

---

## 10. Subsystem 6 — Label printing & application

- **Printer:** integrated **thermal-transfer** (durable, smear-proof) or
  high-res inkjet label printer. Prints: grade (overall + sub-grades incl.
  centering), **cert number**, date, and a **QR/2D barcode** linking to the
  stored images + grade record.
- **Verify:** in-line barcode reader does a **print-and-verify** read-back; bad
  prints are scrapped before insertion (no mis-labelled slab leaves the cell).
- **Apply:** vacuum pick places the cut label into the slab's label window
  *before* the top shell + weld, so it is permanently sealed inside.
- **Tamper/anti-counterfeit (optional):** hologram-sticker applicator station,
  or a serialised security pattern printed on the label.

---

## 11. Subsystem 7 — Outfeed & reject handling

- **Good outfeed:** finished slabs ejected onto a gravity chute into a
  **stacker/magazine** (cushioned to avoid scuffing the fresh weld).
- **Reject paths (kept separate, with reason codes):**
  - *No-grade / detection fail* — diverted **pre-assembly**, card returned to a
    reject tray (no shell consumed).
  - *Assembly/weld fault* — finished-but-bad slab to a quarantine bin; weld-
    energy/collapse out of window flags it.
  - *Double-feed / handling fault* — pause + operator.
- **Counts & bin-full sensors** feed the HMI/dashboard.

---

## 12. Electrical & control architecture

```
   ┌────────────────────────────────────────────────────────────────────┐
   │  Industrial PC (IPC)            ── grading + recipes + HMI host      │
   │   • Python/OpenCV pipeline (this repo)                               │
   │   • GPU (future ML surface/corner)                                   │
   │   • DB (Postgres/SQLite) + image store                              │
   │            │  OPC-UA / shared local API                              │
   │            ▼                                                         │
   │  Real-time motion controller (EtherCAT master, e.g. Beckhoff/Omron)  │
   │   • Servo drives: dial index, press Z, gantry/transfer axes          │
   │   • Stepper drives: minor axes (label, hopper follower)              │
   │   • Digital I/O: vacuum valves, ionizer, air knives, lights strobe   │
   │   • Ultrasonic generator (start/ready/alarm + energy read-back)      │
   │   • Safety I/O (separate safety controller / relay)                  │
   └────────────────────────────────────────────────────────────────────┘
   Cameras → IPC over GigE Vision / USB3 Vision (hardware-triggered, strobe sync)
```

- **Topology:** single **IPC** runs the vision/grading + HMI; a deterministic
  **EtherCAT** motion bus runs the machine. They talk over **OPC-UA** (or a thin
  local socket/REST API) so the grading verdict gates the slab stations.
- **Motion:** servo on the index, transfer, and weld-press axes (precision +
  force control); steppers acceptable on low-duty minor axes.
- **Pneumatics:** clean, dry, oil-free air @ ~6 bar; **venturi vacuum
  generators** with vacuum-confirm sensors at every pick; air prep (filter-
  regulator-lubricator, but *no* oil mist on the card path).
- **Sensors:** part-present (photoelectric/fibre), double-feed (ultrasonic),
  vacuum pressure, weld force (load cell) + collapse (linear encoder), home/limit
  switches, light curtains, door interlocks.
- **HMI:** mounted touchscreen (recipes, jog, counters, fault log) + a web
  dashboard for throughput/yield/traceability.
- **Power:** 230 VAC 1Ø ~16 A typical (ultrasonic welder is the big draw);
  24 VDC control rail; UPS on the IPC for clean shutdown.

---

## 13. Software integration with the grading pipeline

The machine is the data front-end and actuation back-end for **this repo's
code**, with almost no change to the existing modules:

```
  Camera capture (S3) ─▶  in-memory BGR frame
        │
        ▼
  card_detector.detect_card(frame)            # already deskews/rectifies
        │   (background is controlled → high detection reliability)
        ▼
  centering.measure_centering(rectified)      # L/R/T/B + ratios
        │
        ▼
  grading.build_grade(h_ratio, v_ratio)       # CardGrade (centering now;
        │                                      #   corners/edges/surface = None)
        ▼
  Machine Control decision:
     overall >= accept_threshold  → assign cert #, proceed to slab
     low confidence / detect fail → re-image once, else divert to reject
        │
        ▼
  Persist: raw + rectified + multi-light images, CardGrade JSON, cert #, QR
```

**Why this drops in cleanly**
- `card_detector` already returns a rectified, top-down crop — exactly what a
  fixed, calibrated camera + controlled background produces, only now the
  *inputs* are repeatable, so detection rarely fails.
- `grading.CardGrade` already carries `corners/edges/surface = None` and
  `compute_overall()` averages only present sub-scores — so when the machine's
  **multi-angle captures** (§8.3) feed future modules, those sub-grades and the
  overall update with **no change to the machine or the core schema**.
- The machine should call the pipeline as a **library** (not the Streamlit app);
  wrap `run_pipeline()`-style logic in a headless service. Streamlit stays as the
  human review / manual-QA console.

**New software the machine needs (not in this repo):**
machine-control state machine, recipe manager, camera/trigger driver,
cert-number + traceability DB, HMI, and a thin OPC-UA/REST bridge to motion.

---

## 14. Cycle-time & throughput budget

Per-station dwell estimates (single card; mechanics-limited, grading overlaps):

| Station | Action | Time |
|---|---|---|
| S1 | Pick + double-feed + place | 2.5 s |
| S2 | Clean (ionise + air) | 1.5 s |
| S3 | Image both faces (diffuse + cross-pol) | 2.0 s |
| (IPC) | Grade (pipelined, overlaps next index) | ~0.5 s, hidden |
| S5 | Shell + frame + card transfer (vision-verified) | 3.0 s |
| S6 | Label print + insert + verify | 2.5 s |
| S7 | Ultrasonic weld + hold/cool | 1.5 s |
| S8 | Eject + record | 1.5 s |
| — | Index move | 0.5 s |

- **Sequential single-card machine (Phase-1/2):** sum ≈ **30–45 s/card** →
  **~80–120 cards/hour**.
- **Pipelined rotary dial (Phase-3):** throughput = slowest single station +
  index ≈ **3.0 + 0.5 ≈ 3.5 s** → theoretical ~1000/h, realistically
  **~300–450 finished slabs/hour** after QA holds and reject handling.
- **Bottleneck:** the card-transfer-into-shell (S5) and weld/cool (S7). If
  surface photometric capture (4 grazing shots) is enabled, S3 grows ~+1.5 s and
  may become the bottleneck — split imaging across two dial stations.

---

## 15. Tolerances & key engineering challenges

| Item | Target | Why it matters |
|---|---|---|
| Index/nest repeatability | ≤ ±0.02 mm | Stable card origin for imaging & pick-out |
| Camera axis perpendicularity | < 0.2° | Centering accuracy (less reliance on SW deskew) |
| Card-in-shell placement | ≤ ±0.1 mm | A slabbed card that looks *off-centre* is unacceptable even if the *card* is well centred |
| Weld energy repeatability | ±5 % | Leak-free, tamper-evident, no over-melt distortion |
| Pixel resolution at card | ≥ 1200 px/in (24 MP) | Edge/corner/surface detail (future) |
| Single-feed reliability | ≥ 99.5 % first-pick | Thin static-clingy cards are the #1 jam source |
| Glare suppression | No specular blowout on foils | Centering edges + surface inspection |

**Hard problems, ranked:** (1) reliable singulation of thin/static cards;
(2) glare-free imaging of foil/holo cards; (3) custom shell + horn tooling cost
& lead time; (4) repeatable card-centred placement inside the slab; (5) handling
warped/over-thick cards without forcing/damage.

---

## 16. Calibration & quality assurance

- **Geometric/optical:** checkerboard or dot-grid target → camera intrinsics +
  distortion; a **dimensional reference card** (known size, printed fiducials)
  verifies the mm-per-pixel scale and the centering math end-to-end.
- **Flat-field / shading:** capture a uniform white/grey tile per lighting mode;
  store correction maps so illumination is even across the FOV.
- **Colour/white balance:** image a reference colour card under each mode; lock
  WB; periodic re-check (LED aging).
- **Golden cards:** a set of cards with **known, independently-measured
  centering** run daily → SPC chart of the machine's reported ratios; drift →
  alert/recal.
- **Weld QA:** energy/collapse window per shell lot; periodic **destructive pull
  test** + **dye-penetrant/leak check** on samples.
- **Traceability:** every card → cert #, all captured images, `CardGrade` JSON,
  machine parameters (weld energy, timestamps), stored and QR-linked.

---

## 17. Safety & compliance

- **Enclosure & interlocks:** fully guarded cell; **interlocked doors**
  (power-off motion on open); **light curtains** at the infeed/outfeed openings;
  **E-stop** (Cat. 0/1) with a dedicated **safety relay/controller** independent
  of the IPC.
- **Ultrasonic welding:** 20 kHz is above human hearing but the assembly emits
  audible sub-harmonics and presents a **pinch hazard** — guard the press,
  acoustic-shroud it, two-hand or interlocked actuation, no-hands-in-tooling
  interlock.
- **Pneumatics:** dump-valve on E-stop, residual-pressure relief, rated tubing.
- **Electrical:** proper bonding/earthing, fused/breakered, EMC-aware
  (ultrasonic generator is noisy); UPS for clean IPC shutdown.
- **Standards (target):** machine safety **ISO 12100** (risk assessment),
  **IEC 60204-1** (electrical), region marking (**CE/UKCA** or **UL/NRTL**),
  ultrasonic equipment guarding per supplier guidance. *(Engage a compliance
  reviewer before any commercial deployment — this list is a starting point,
  not a certification.)*

---

## 18. Bill of materials (representative)

Indicative categories & rough prototype-grade budget (USD; varies widely by
region/supplier; tooling dominates).

| # | Subsystem | Representative components | Rough cost |
|---|---|---|---|
| 1 | Frame / enclosure | Aluminium extrusion, panels, interlocked doors, light tower | $3–6k |
| 2 | Rotary index + nests | Servo index table or cam indexer, reducer, 8 quick-change nests | $6–15k |
| 3 | Infeed/singulation | Hopper, vacuum pick + Z, ioniser, double-feed sensor | $3–6k |
| 4 | Imaging | 2× 24–45 MP global-shutter cameras, lenses (telecentric optional ↑↑), dome + cross-pol + grazing LEDs, strobe controllers, AR platen | $8–25k (telecentric pushes high end) |
| 5 | Transfer / pick-place | Vacuum end-effectors, servo/pneumatic axes, vision-guided | $4–10k |
| 6 | Slab sealing | Ultrasonic generator + converter + **custom horn**, servo/pneumatic press, anvil nest | $8–20k |
| 7 | **Shell tooling** | Injection mould for clear shells (+ inner-frame dies) | **$10–40k (long lead)** |
| 8 | Labelling | Thermal-transfer printer, barcode verifier, label pick-place | $3–6k |
| 9 | Controls | IPC + GPU, EtherCAT master, servo/stepper drives, I/O, safety controller, HMI, vacuum/pneumatics | $10–20k |
| 10 | Integration/eng. | Wiring, software, calibration, test, contingency | $15–40k |
| | **Prototype total** | | **≈ $70–190k** (tooling & optics are the swing) |

**Cheapest credible bring-up (Phase-1/2):** gantry instead of dial, **screw-down
holders** (skip mould + horn), single 24 MP camera + flip → cuts the build to a
small fraction of the above and validates imaging + grading + handling first.

---

## 19. Phased build roadmap

| Phase | Goal | What you build | Exit criterion |
|---|---|---|---|
| **0 — Imaging jig** | Validate that controlled imaging makes the *existing software* reliable | Fixed copy-stand: one camera, dome + cross-pol light, neutral background, manual card load → run this repo's pipeline | Centering numbers stable & repeatable on golden cards |
| **1 — Imaging cell** | Automate capture + grade, no slabbing | Gantry/dial + singulation + dual-side imaging + headless grading service + sort to good/reject bins | Hands-free image→grade→sort at target accuracy |
| **2 — Slabbing (stand-in)** | Add encapsulation with **screw-down** holders | Assembly + label + automated screwdriver join + outfeed | End-to-end card→labelled-case, no custom tooling |
| **3 — Production slab** | Swap to **ultrasonic-welded** shells; pipeline the dial | Custom shells + horn + weld station; weld QA; traceability DB; throughput tuning | 300–450 slabs/h, weld QA in spec, full traceability |
| **4 — Extend grading** | Light up corner/edge/surface | Enable multi-angle captures (already wired in §8.3) + new SW modules populating `CardGrade.corners/edges/surface` | Four-factor overall grade, no machine redesign |

---

## 20. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Thin-card double-feed / mis-pick | High | Med | Ioniser + air-fluffer + ultrasonic double-feed sensor + re-pick; per-job thickness config |
| Foil/holo glare ruins images | High | High | Cross-polarised + diffuse dome; multi-mode strobe; per-card recipe |
| Shell + horn tooling cost/lead | High | High | Phase-2 screw-down stand-in; commit mould only after imaging+grading proven |
| Card placed off-centre in slab | Med | High | Vision-verified placement to ±0.1 mm; reject on out-of-window |
| Weld leaks / over-melt distortion | Med | High | Closed-loop energy+collapse; destructive + leak sampling; SPC |
| Warped / over-thick cards | Med | Med | Adjustable nest + deeper cavity variants; flag & divert un-handleable cards |
| Detection fails on odd card art | Low–Med | Med | Controlled background by construction; re-image; manual-review queue (Streamlit) |
| Dust → false surface defects | Med | Med | De-dust station + filtered air + cleanroom-ish enclosure |
| Throughput below target | Med | Med | Pipeline dial; split imaging across two stations; parallel weld nests |
| Safety/compliance gaps | Low | High | ISO 12100 risk assessment + IEC 60204-1 + acoustic/press guarding; expert review |

---

## 21. Reference data & drawing sheet list

**Key reference dimensions**
- Standard card: 63.5 × 88.9 mm; thickness 0.30 mm (35 pt) … 1.2 mm (130 pt).
- Imaging FOV (telecentric or framed): ≥ 95 × 120 mm with margin.
- Target resolution at card plane: ≥ 1200 px/in (≥ ~47 px/mm).
- Slab outer (tooling-defined baseline): ~91 × 130 × 6 mm.

**Drawing package that would be produced from this blueprint** (not included
here — this is the design intent doc that precedes detailed CAD):
1. GA-001 General arrangement & footprint
2. ME-1xx Frame & enclosure
3. ME-2xx Rotary index + nest fixtures (incl. quick-change card pockets)
4. ME-3xx Infeed/hopper/singulator
5. ME-4xx Imaging station optomechanics (camera mounts, dome, polariser, platen)
6. ME-5xx Transfer/pick-place tooling
7. ME-6xx Slab-assembly nest + ultrasonic horn/anvil interface
8. ME-7xx Label print/apply mechanism
9. ME-8xx Outfeed/stacker/reject
10. EE-1xx Electrical schematic & panel layout
11. EE-2xx EtherCAT/I-O map & sensor list
12. SW-1xx Control state machine & recipe model
13. SW-2xx Vision/grading integration (this repo) + traceability DB schema
14. SA-1xx Safety: risk assessment, guarding, interlock & E-stop circuit
15. TL-1xx Shell injection-mould & inner-frame die tooling; horn tuning spec

---

*This blueprint deliberately mirrors the software's philosophy: prioritise
**repeatability and tunable, well-bounded subsystems** over accuracy claims,
and keep the architecture open so corner/edge/surface grading — and a real
welded slab — drop in without redesigning the core.*
