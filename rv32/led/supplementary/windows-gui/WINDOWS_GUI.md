# Windows Ripes LED GUI validation

The user ran the three supplied assembly cases on Windows Ripes with
`RV32_ISS`, `RV32I`, and LED Matrix 0 configured at 35 columns by 25 rows.
The visible peripheral exports give BASE=`0xf0000000`, SIZE=`0xdac` (3,500
bytes), WIDTH=`0x23` (35), HEIGHT=`0x19` (25).

| Case | Completion x25 | Status x26 | Length x27 | Final display | Result |
|---|---|---|---|---|---|
| solved | `0x600d` | `0` | `0` | Six uniform faces | PASS |
| short | `0x600d` | `0` | `1` | Six uniform faces | PASS |
| distance11 | `0x600d` | `0` | `0xb` (11) | Six uniform faces | PASS |

The solved colors are white U, orange L, green F, red R, blue B, yellow D.
The one-column/row separators and the five unused bottom rows remain black.
The short case was reset and run a second time before its evidence was taken;
this is a normal independent rerun, and its completion values are valid.

## Distance-11 animation

The original animation was visible but too fast to count. Its final display
and completion registers passed. After increasing the renderer pause, the
user explicitly confirmed seeing **12 frames**: the initial state and one
new state after each of the **11 emitted HTM moves**. Initial and intermediate
screenshots from this slower run were preserved. The exact final LED_DELAY
constant has not yet been recorded; this affects presentation speed, not the
path or the meaning of the renderer-free instruction counts.

The supplied path from the existing verified execution is:

`R B' D2 R' B R' B' R D2 R B`

The screenshot color comparison samples one interior LED in each of the 24
facelets and compares the resulting colors to the existing emulator preview,
whose frames were checked against independent 3-D sticker rotations:

| Screenshot | Matching frame index | Meaning |
|---|---:|---|
| distance11-led-initial.png | 0 | Input `21345671111111` |
| distance11-led-intermediate-step5.png | 5 | After `R B' D2 R' B` |

All 24 sampled facelet colors match exactly. This is a comparison of the
sampled color blocks, not a pixel-by-pixel comparison of the entire screenshot.
The screenshots do not record every frame; the full 12-frame count is a
manual observation reported by the user. Reference frame hashes and the
executable/geometry validation are preserved separately under
`../supplementary-validation.json`. Sampling details and RGB values are in
`distance11-screenshot-comparison.json`.

The final distance-11 register/display images are from the earlier fast run;
the initial/intermediate images and 12-frame observation are from the slowed
rerun. They must not be described as one continuous video recording.

## Evidence files

- `solved-led.png`, `solved-registers.png`, `solved-status.json`
- `short-led-final.png`, `short-registers.png`, `short-status.json`
- `distance11-led-initial.png`, `distance11-led-intermediate-step5.png`
- `distance11-led-final.png`, `distance11-registers.png`, `distance11-status.json`
- `distance11-screenshot-comparison.json`, `summary.json`

No solver compile/run or full 2,644-state gate was repeated while documenting
these GUI results. The original formal measurement artifacts remain unchanged.
The Linux RAM-symbol renderer tests remain supplementary, and are not used
as substitutes for these actual Windows peripheral screenshots.

Remaining integration: install the new source/evidence in the user's WSL
repository, confirm the renderer-free new artifacts on the pinned Windows
Ripes, then perform visual-pipeline T7 and the instruction-level walkthrough.
The existing pin identifies the previously recorded Ripes binary; these
screenshots alone do not independently establish its executable hash/version.
