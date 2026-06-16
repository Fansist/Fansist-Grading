# Fansist ScanSlab — Self-Service Scan · Slab · Grade Kiosk (Design)

> **Concept:** a staffed-retail or unattended **kiosk** that lets a customer grade
> a card *without ever shipping it*. Drop the raw card in; the kiosk **3D-scans**
> it, sends the **digital model** to a remote human grader, and **encapsulates the
> card in a slab carrying a unique code** — grade area left blank. The customer
> **takes the slabbed card home**, checks status online with the code, and once it's
> graded **returns to any kiosk to laser-print the grade onto the slab**.
>
> This document is the machine design. It reuses subsystems from the existing
> hardware docs (`docs/HARDWARE_BLUEPRINT.md`, `docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md`)
> for handling/sealing, and the software in this repo for submission, grading and
> the status site (`submission.py`, `grader_portal.py`, `web_report.py`).

---

## 1. User flow

```
 DROP-OFF (kiosk)                         AT HOME                 PICK-UP (any kiosk)
 ┌───────────────────────────┐   ┌──────────────────────┐   ┌────────────────────────┐
 │ insert raw card           │   │ enter code on website │   │ insert/scan the slab   │
 │ → 3D SCAN (front+back)    │   │  → "in review"        │   │ → kiosk verifies GRADED │
 │ → model sent to grader    │   │  → later "GRADED 9"   │   │ → LASER-PRINT grade     │
 │ → SLAB the card + CODE    │──▶│  → "ready to print"   │──▶│   onto the slab panel  │
 │ → customer leaves w/ slab │   └──────────────────────┘   │ → status: PRINTED      │
 └───────────────────────────┘                              └────────────────────────┘
        status: IN_REVIEW                                          status: PRINTED
```

Card is protected (slabbed) from the moment of drop-off; the grade is added later,
on-demand, without ever opening the slab.

---

## 2. System overview

One floor-standing or counter-top **kiosk** with two operating modes (the same
machine does both):

- **Intake mode** (drop-off): scan → transmit model → slab + code.
- **Finishing mode** (pick-up): read code → verify graded → laser-mark grade.

```
  ┌──────────────────────────────────────────────────────────────┐
  │  TOUCHSCREEN HMI + payment + card-slot                        │
  │  ┌─────────────── 3D SCAN HEAD (intake) ───────────────────┐  │
  │  │  photometric-stereo dome (multi-LED) + 60MP camera      │  │
  │  │  + structured-light projector (warp) ; dual-side via    │  │
  │  │  glass platen / flip                                    │  │
  │  └─────────────────────────────────────────────────────────┘  │
  │  ┌────────── SLAB ASSEMBLY (intake) ───────────────────────┐  │
  │  │ shell magazine · inner frame · code-label printer ·     │  │
  │  │ ultrasonic seal · eject to customer tray                │  │
  │  └─────────────────────────────────────────────────────────┘  │
  │  ┌────────── GRADE-MARK STATION (finishing) ───────────────┐  │
  │  │ slab nest + code reader + GALVO LASER MARKER (grade)    │  │
  │  └─────────────────────────────────────────────────────────┘  │
  │  Industrial PC · motion controller · network · UPS           │
  └──────────────────────────────────────────────────────────────┘
        Mains 230 VAC · network (model upload, status sync)
        Footprint ~0.6 × 0.6 m counter unit (or 1.8 m floor kiosk)
```

---

## 3. Subsystem 1 — Card intake & handling

- **Slot + singulation:** a motorized intake slot accepts one raw card (loose or
  in a penny sleeve). Anti-static ioniser + a vacuum/friction transport moves the
  card to the scan platen. Double-feed and presence sensors. (Same handling family
  as the SlabStation spec.)
- **Cleaning:** ioniser + soft air to remove dust before scanning (dust reads as a
  surface defect in the model).
- **Registration nest** on a glass platen so both faces are reachable.

---

## 4. Subsystem 2 — 3D scan / digital-model capture (the technical core)

A flat card's grade is dominated by **micro-surface** (scratches, dents, print
lines, edge/corner whitening) and **centering**. A useful "3D scan" is therefore
a high-resolution **relightable surface model**, not a coarse mesh. Two modalities:

1. **Photometric stereo / RTI (primary).** A dome of **N = 16–24 high-CRI LEDs**
   at known positions is fired one at a time while a fixed **60–100 MP global-
   shutter camera** captures one frame per light. From the per-pixel shading we
   solve for **surface normals**, integrate them into a **height map**, and recover
   the **albedo (true colour)**. Result, per side:
   `{ albedo RGB, normal map, height/depth map }` at ≳ 2000 px/in. This is exactly
   the signal that makes scratches/dents/whitening visible — the grader can
   **relight** the surface interactively, like TAG's photometric-stereo report.
   - **Cross-polarised** capture pass separates diffuse vs. specular (holo/foil).
2. **Structured-light / laser-line (secondary, optional).** A projector or laser
   line gives macro **warp/bow/thickness** geometry (for "card is bent" defects),
   complementing the micro-surface from (1).

- **Both faces:** dual scan heads (above + below a clear AR platen), or one head
  with a flip/transport. Front and back each get the full model.
- **Output — the "digital model":** a packaged, **relightable** dataset per side
  (albedo + normals + height + the raw light stack), plus the structured-light
  geometry, plus an objective **centering measurement** (reuse `centering.py` on
  the albedo). Stored and uploaded to the grader (see §8/§9).
- Capture time target: ≈ 10–25 s for both sides (LED stack + processing).

> The existing `surface.py` already has the `extra_frames=` hook and the hardware
> blueprint already specifies multi-angle lighting — this scan head is the
> production realisation of that capture.

---

## 5. Subsystem 3 — Slab assembly & sealing (with code, grade blank)

The card is encapsulated **before** grading so the customer can take it home
protected. The slab is designed so the grade can be **added later without opening**.

- **Shell:** clear two-piece (PETG/PC), from a magazine; **inner frame** sizes to
  the card. Same sealing family as the SlabStation/industrial slab (ultrasonic
  weld) — the kiosk has a compact **ultrasonic welder + nest**.
- **Code label (sealed inside):** a printed **unique serial + QR** (the QR encodes
  the status URL `…/status/<code>`) is placed in a label window and sealed in —
  tamper-evident, scannable through the clear shell.
- **Grade panel (left blank):** a reserved **frosted / laser-markable zone** on the
  outer shell face where the grade will be marked at pick-up. Frosting gives high
  laser-mark contrast and is moulded into the shell.
- **Eject:** finished slab to the customer tray. Status set to `IN_REVIEW`.

See `docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md` §9 for the shell/weld tooling
detail; the only additions here are the **moulded grade panel** and the
**sealed code label**.

---

## 6. Subsystem 4 — Code generation & tracking

- Each slab gets a **globally unique code** (= the submission/cert id, e.g.
  `FAN-XXXXXXXXXX`) minted at intake. The QR encodes the **status URL**; the
  human-readable serial is printed beside it.
- The code is the single key linking: the physical slab ↔ the digital model ↔ the
  grader's verdict ↔ the status website ↔ the pick-up laser-mark.
- Anti-counterfeit: the sealed-inside QR + serial, optionally a security pattern or
  hologram; the website confirms authenticity (the code must exist and be graded).

---

## 7. Subsystem 5 — Grade-mark station (pick-up / finishing)

When the customer returns with the slab after it's graded:

- **Read the code** (camera/QR scanner reads the sealed QR through the shell).
- **Verify** against the backend: status must be `GRADED`. If still `IN_REVIEW`,
  the HMI says "not graded yet"; if already `PRINTED`, it declines (idempotent).
- **Mark the grade:** a **galvo UV or fibre laser marker** engraves the overall
  grade + sub-grades + cert serial into the slab's frosted **grade panel** — fast
  (1–3 s), permanent, tamper-evident, **no opening of the slab**.
- Status → `PRINTED`. The DIG report URL/QR already on the slab now resolves to the
  finished grade.

*Why laser, not a printed sticker:* the slab is sealed and the grade must be
permanent and tamper-evident; laser-marking a moulded frosted zone achieves both
in a self-service machine. (A thermal-label applicator is the lower-cost
alternative if permanence/tamper-evidence is relaxed.)

---

## 8. Digital model & data

| Artifact (per side) | Purpose |
|---|---|
| Albedo RGB (high-res) | true-colour reference; centering measurement |
| Normal map | micro-surface relief (scratches, print lines, dents) |
| Height/depth map | integrated relief; whitening/edge wear |
| Raw light stack (N frames) | lets the grader **relight** freely (RTI viewer) |
| Structured-light geometry | macro warp/bow/thickness |
| Centering metrics | objective L/R, T/B from `centering.py` |

Packaged per submission and uploaded to the grading backend. The **grader views it
in an interactive relightable viewer** (web), inspects every defect under chosen
lighting, and enters the grade — the same human-grading product already in this
repo (`grader_portal.py`), upgraded from flat images to the relightable model.

---

## 9. Status / tracking website (built in this repo)

The code on the slab drives a public **status site** — exactly the "enter the code,
is it graded yet?" flow:

- `web_report.py` serves **`/status/<code>`**: shows `IN_REVIEW` / `GRADED` /
  `PRINTED`, reveals the grade once graded, and tells the customer to return to a
  kiosk to print it. The full DIG report is at `/card/<code>`.
- `submission.py` carries the lifecycle: `pending_review (IN_REVIEW) → graded →
  printed`, with `mark_printed()` the action the **pick-up kiosk** calls after a
  successful laser-mark.
- The kiosk's finishing mode is represented by `kiosk.py` (`status` / `print`).

So the digital half of this machine is already implemented and tested; the kiosk
is the physical front-end to it.

---

## 10. Control & software architecture

```
  Kiosk IPC (touch HMI, payment, scan processing, marking control)
    • capture: fire LED stack, run photometric-stereo solve, build model
    • submission.create_submission(model, code) → upload to backend
    • finishing: read code → backend status → if GRADED, drive laser → mark_printed
    │  network
    ▼
  Backend (this repo): submission store · grader_portal (grader UI) ·
                       web_report (/status, /card, registry)
    • motion/marking via a real-time controller (laser galvo, transport, welder)
```

- Motion/marking: a motion controller (EtherCAT) drives the transport, ultrasonic
  press, and the **laser galvo + safety interlocks**.
- Payment & identity: card reader / app login at the HMI; receipt = the code.

---

## 11. Slab design (physical)

```
  ┌──────────────────────────────────────────────┐
  │  ░░ GRADE PANEL (frosted, laser-markable) ░░   │  ← blank at drop-off,
  │  ░░  [ marked at pick-up: 9  ·  cert# ]   ░░   │     laser-marked at pick-up
  │  ┌──────────────────────────────────────────┐ │
  │  │            CARD (in inner frame)          │ │
  │  └──────────────────────────────────────────┘ │
  │  [QR → /status/<code>]   FAN-XXXXXXXXXX        │  ← sealed-in code label
  └──────────────────────────────────────────────┘
        clear two-piece shell, ultrasonically welded
```

- Moulded **frosted grade panel** (laser contrast), **sealed code label** (QR +
  serial), clear shell, inner frame. Otherwise identical to the standard slab.

---

## 12. Electrical & safety

- **Laser safety is the dominant hazard:** the marker must be a **fully enclosed
  Class-1** assembly — interlocked door, beam shroud, no exposed beam, E-stop.
  (Marking is internal to the kiosk; the customer never sees the beam.)
- Ultrasonic weld guarding (pinch/acoustic), pneumatics dump on E-stop, mains
  behind a certified panel, UPS for clean shutdown.
- Standards target: ISO 12100, IEC 60204-1, **IEC 60825 (laser)**, region marking
  (CE/UKCA or UL). *Engage a laser-safety + compliance reviewer before deployment.*

---

## 13. Bill of materials & cost (indicative)

A kiosk is materially more than the tabletop SlabStation — the **3D scan head** and
the **laser marker** dominate.

| Subsystem | Representative parts | Rough cost |
|---|---|---|
| Enclosure / kiosk chassis | Sheet-metal cabinet, HMI touchscreen, card slot, trays | $2–5k |
| 3D scan head | 60–100 MP camera, 16–24 high-CRI LEDs + driver, dome, AR platen, polarisers, (structured-light projector) | $6–18k |
| Card handling | Intake, singulation, transport, ioniser, sensors | $3–7k |
| Slab assembly | Shell magazine, inner-frame feeder, code-label printer, ultrasonic welder + nest | $10–22k |
| **Grade-mark laser** | Enclosed Class-1 **galvo UV/fibre marker** + controller | $8–20k |
| Controls | IPC, motion controller, drives, I/O, safety controller, UPS | $8–16k |
| Integration / SW / test | Wiring, calibration, the relightable viewer, contingency | $15–40k |
| **Kiosk total** | | **≈ $60–130k** |
| **Shell tooling (one-time)** | Injection mould for the frosted-panel/code-label shell | **$15–45k** |

Honest note: this is **capital equipment** (a graded-on-site kiosk), not a
consumer device — the value is throughput + the "no-shipping, slab-in-minutes"
experience at a retail location. A lighter **scan-and-slab-only** kiosk (defer the
laser to a single staffed finishing station) cuts the per-kiosk cost substantially.

---

## 14. Sequence of operations

**Intake (drop-off):**
1. Customer pays / logs in; inserts card.
2. Clean → register on platen.
3. **3D scan** front; flip/second head; scan back → build digital model.
4. Mint **code**; upload model + centering to backend → submission `IN_REVIEW`.
5. Assemble slab (shell + inner frame + sealed code label, **grade panel blank**)
   → ultrasonic weld → eject to customer.
6. HMI shows the code + status URL.

**Finishing (pick-up, after grading):**
1. Customer inserts/scans the slab; kiosk reads the code.
2. Backend check: `GRADED`? If not, inform; if yes, proceed.
3. **Laser-mark** the grade + cert into the grade panel.
4. `mark_printed` → status `PRINTED`; eject.

---

## 15. Throughput

- Intake: scan (10–25 s) + slab assembly/weld (10–20 s) ≈ **45–90 s/card** →
  ~40–80 cards/hour per kiosk (grading itself happens off-board, asynchronously).
- Finishing: read + laser-mark ≈ **10–20 s/slab**.

---

## 16. CAD / manufacturing deliverables (to produce)

**Provided now — Rev A CAD** in [`hardware/kiosk/`](../hardware/kiosk/) (parametric
`generate_kiosk.py`): a dimensioned **general-arrangement 3D model** (STL — cabinet
panels, internal module envelopes, the LED scan dome, and the redesigned
**slab_v2** with code-label recess + frosted grade panel), the **sheet-metal
cabinet flat patterns** (DXF — front with HMI/card-slot/tray cutouts, back with
service door + vents, sides, top, bottom + a nest sheet), and renders. A
sheet-metal shop can quote the DXF directly.

**Still to produce (detailed design):**- Kiosk GA + sheet-metal cabinet drawings.
- Scan-head optomechanics (camera/LED-dome/platen/polariser mounts) + the
  photometric-stereo calibration procedure.
- Slab shell injection mould **with the frosted grade panel + code-label window**.
- Laser-marker enclosure + interlock/safety circuit.
- Transport / slab-assembly / weld nests (reuse SlabStation tooling family).
- Controls schematic + EtherCAT/I-O map + laser safety circuit.
- Software: the relightable model viewer for graders; kiosk control app;
  status/print integration (the submission/web_report/kiosk code in this repo).

---

## 17. Open decisions & phasing

1. **Grade marking:** enclosed **laser** (permanent/tamper-evident, recommended)
   vs **thermal-label applicator** (cheaper, less permanent).
2. **Scan modality:** photometric-stereo only (micro-surface) vs + structured-light
   (also macro warp). Recommend photometric first; add structured-light later.
3. **Both-sides capture:** dual heads (no moving card) vs flip transport.
4. **Kiosk vs split stations:** one machine does scan+slab+mark, or a cheap
   scan+slab kiosk + a single staffed laser-finishing station.
5. **Slab sealing:** ultrasonic weld (permanent) vs screw-down (reusable, lets the
   grade be an *insert* rather than a laser mark — simplest, least secure).

**Phasing:** (0) bench scan head + relightable viewer + the status site (software,
mostly done) → (1) scan-and-slab kiosk, staffed laser finishing → (2) integrated
self-service scan/slab/mark kiosk.

---

## 18. Risk register (highlights)

| Risk | Mitigation |
|---|---|
| Laser safety in a public machine | Fully enclosed Class-1, interlocks, E-stop, IEC 60825, expert review |
| Photometric model misses defects on holo/foil | Cross-polarised pass; structured-light for warp; grader relighting |
| Marking a slab whose grade isn't ready | Backend status gate (`GRADED` required) before the laser fires |
| Slab tampering / fake grades | Sealed-in code, website authentication, laser-into-frosted-panel permanence |
| Shell tooling cost/lead (frosted panel) | Phase the laser/finishing; prove scan+slab first |
| Dust/scratches introduced by handling | Ioniser + soft air + clean transport; QC the model before upload |

---

*Companion: `submission.py` / `grader_portal.py` / `web_report.py` implement the
submission, human-grading and status/print software for this machine; the prior
hardware docs cover the shared handling/sealing subsystems.*
