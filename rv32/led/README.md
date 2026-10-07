# LED Matrix renderer for asm-v5

[Repository home](../../README.md) · [RV32I guide](../README.md)
· [Measurement index](../../measurements/README.md)

This source tree adds an unfolded-net renderer to the validated asm-v5 solver
at commit `4b5ec97dc97170e85d20efdbce360a77caf872bb`. It does not change any
historical source or measurements. Windows Ripes GUI end-state checks now pass
for the three cases. The user also observed all 12 frames of the distance-11
animation; its initial and sampled intermediate facelet colors match the
independent geometrical model. See [Windows GUI evidence](supplementary/windows-gui/WINDOWS_GUI.md)
for the exact evidence scope. Supplementary Linux/Unicorn results remain separate.

## Build and open

From the repository root, with GNU RISC-V tools on PATH:

```sh
python3 rv32/led/build.py
```

Build outputs are under `rv32/build/led/`. The script generates three cases:

| Case | Input | Expected HTM length | Frames |
|---|---|---:|---:|
| solved | `12345671111111` | 0 | 1 |
| short | `25314672313211` | 1 (`R'`) | 2 |
| distance11 | `21345671111111` | 11 | 12 |

An arbitrary valid input is supported:

```sh
python3 rv32/led/build.py --state 41532672313211 --expected 11
```

Omit `--expected` when the optimal length is unknown. The solver still computes
an optimal path. `--delay 300000` is the default GUI pause loop; change it if
the animation is too slow or too fast. This is a number of loop iterations,
not a time in milliseconds. Avoid large delays on a visual pipeline model.

In the pinned Windows Ripes `v2.2.6-106-g5b8a616`:

1. Instantiate **LED Matrix 0** in the I/O tab; Width **35**, Height **25**.
   Height is listed first. Check the three exported symbols, then assemble.
2. Load `short-gui.s` as **Assembly**, not ELF, and build in the editor.
   The source deliberately leaves the device symbols undefined so Ripes
   supplies the real address and dimensions. Change/rebuild after modifying
   device parameters. A second matrix named `LED Matrix 1` will not substitute
   for the first instance.
3. Run on `RV32_ISS` without ISA extensions. The input frame appears first;
   after the actual solver returns, the returned `R'` produces a solved frame.
4. Reset between cases. Repeat with `solved-gui.s` and `distance11-gui.s`.
   The latter follows `R B' D2 R' B R' B' R D2 R B` for this deterministic
   solver version; the renderer reads the computed bytes and contains no
   prerecorded solution.
5. At completion, x25 is `0x600d`, x26 is status `0`, and x27 is length
   `0`, `1`, or `11`. `result_path` and `led_frame_count` remain inspectable
   in memory. `led_frame_count` is updated after every complete draw, making
   that store a useful debugger breakpoint. Each half/inverse turn adds one
   frame after all of its quarter-turn updates.

The program leaves the solved display visible when it exits. Do not reset
before capturing it. Store initial/intermediate/final screenshots and the
peripheral symbols/model settings as evidence of the actual GUI test.

## Shared source and renderer switch

`target.S` is the asm-v1 target driver with calls guarded by `.if RENDER`.
`render.S` guards its complete code/data/workspace. GNU assembler processes
the switch for ELF builds. `build.py` specializes the same switch when
generating Ripes sources. Ripes at `5b8a616` does not list `.if`/`.endif`
among its GNU directives, so they are resolved before the source is opened;
`.zero` is used rather than unsupported `.space`. Expressions in `.word`
contain no intervening whitespace, and a one-byte sentinel retains the
otherwise trailing `__stack_top` label.

The GUI/CLI generated sources come from the same functions and table bytes;
the switch adds only renderer calls/code/constants/workspace. Both Ripes
sources initialize the same supplied state and validate the result. The
compiler/assembler may lower address pseudo-instructions differently; compare
the same artifact format when measuring performance.

| Artifact | Purpose |
|---|---|
| `*-gui.s` | Real GUI; references `LED_MATRIX_0_BASE/WIDTH/HEIGHT` |
| `*-cli.s` | Ripes assembly with renderer removed; no LED references |
| `*-cli.elf` | Formal renderer-free ELF measurement convention preserved |
| `*-renderer-test.elf` | Supplementary emulator test; LED symbols bound to RAM at `0x200000` |

**Do not load renderer-test ELF as the GUI program**: its RAM binding is
deliberately not a peripheral address. Do not measure GUI delay-loop counts
against the renderer-free instruction limit.

## Geometric mapping

Use exterior views of the six faces, with U above F and D below F.

| Face | Corner labels, top-left/top-right/bottom-left/bottom-right | Pixel origin |
|---|---|---|
| U | 7,4,0,1 | (9,0) |
| L | 7,0,6,3 | (0,7) |
| F | 0,1,3,2 | (9,7) |
| R | 1,4,2,5 | (18,7) |
| B | 4,7,5,6 | (27,7) |
| D | 3,2,6,5 | (9,14) |

Each facelet covers 4 columns by 3 rows. A face covers 8 by 6 pixels;
separator columns are 8,17,26 and separator rows 6,13. The occupied bounding
box is 35 by 20, and rows 20..24 stay black. Six distinguishable palette
colors are white U, green F, orange L, red R, blue B, yellow D. Each pixel
is stored as `0x00RRGGBB` at `BASE + 4*(y*WIDTH+x)`. The code forms row
offsets by additions and uses no multiply/divide instruction.

The fixed corner is label 0, and the seven input labels are 1..7. Cyclic
local face orders of positions/cubies 0..7 are:

| Label | Local slots 0,1,2 |
|---:|---|
| 0 | U,F,L |
| 1 | U,R,F |
| 2 | D,F,R |
| 3 | D,L,F |
| 4 | U,B,R |
| 5 | D,R,B |
| 6 | D,B,L |
| 7 | U,L,B |

For local face slot k at destination i, occupant c=p[i] and twist o[i],
the color is `corner_faces[c][(k+o[i])%3]`. These orders and the plus sign
agree with the solver's twists, confirmed by independent spatial rotations:
R maps (x,y,z) to (x,z,-y) on x=1, B maps to (-y,x,z) on z=-1, and D maps
to (z,y,-x) on y=-1. The same rotation is applied to sticker normals.

`led_begin` parses the already validated character input into p[8]/o[8].
`led_animate` reads `result_path` and its returned length, applies the real
moves through the small physical cubie model, and redraws after each HTM move.
It runs after the original coordinate replay and expected-length gate pass.
It never runs the solver twice. Invalid inputs do not draw; a dimension
mismatch returns target status 5 rather than writing outside the device.

## Size, memory, and validation scope

GNU-linked ELF audits (including the reserved 4,096-byte stack):

| Build | `.text` bytes | Static data bytes |
|---|---:|---:|
| renderer off | 1,428 | 126,488 |
| renderer test on, delay=0 | 2,176 | 126,728 |

The added static data is 192 bytes of constants plus 36 bytes of workspace
and 12 bytes of alignment. The resulting total remains below 131,072 bytes.
The maximum allocated call-stack depth remains 80 bytes:
target(32)+solver(48), versus target(32)+animate(32) or target(32)+begin(16).
The standalone Ripes source has a separate data layout and a one-byte
end-label sentinel; ELF byte sizes must not be presented as its exact sizes.

Three renderer-off ELF executable instruction streams are byte-identical
to the archived asm-v5 streams. Complete ELF hashes differ because the new
objects introduce metadata/absolute symbols. Historical sources, full
distance-11 records, and their hashes are unchanged.

Supplementary checks:

```sh
python3 -m venv /tmp/minirubik-led-tests
/tmp/minirubik-led-tests/bin/pip install unicorn==2.1.4 pyelftools==0.32
/tmp/minirubik-led-tests/bin/python rv32/led/testing/validate.py
```

Pillow is optional for `--preview`. `validate.py` compares every LED pixel
against an independent 3-D sticker model for the three complete executables
and all nine move IDs on 30 randomized legal states (270 state/move pairs).
It also checks ABI preservation, MMIO bounds, invalid-input status, incorrect
expected-length status, identical GUI/CLI solver paths, and solved final frames.
The animated preview is an emulator-derived illustration, not a Ripes capture.

The Linux Ripes AppImage from the same `5b8a616` version also passes nine
supplementary runs: CLI ELF, CLI source, and GUI source with synthetic RAM LED
symbols for each of the three cases. Renderer-off ELF counts are unchanged
(557,753,1,468,209). Standalone CLI-source counts are +7 (564,760,1,468,216),
due to its source assembly/layout; those are not replacements for the archived
ELF numbers. Renderer-source RAM test counts, with delay disabled, are
7,452 / 11,355 / 1,513,772. Linux binary/platform checks do not establish the
Windows binary's actual LED peripheral display.

Evidence: [supplementary/](supplementary/) contains the build audits, independent frame hashes,
Ripes reports/logs, command provenance, and unchanged-core comparison.
Windows GUI evidence: [windows-gui/](supplementary/windows-gui/) records the three final
LED displays/register results, the distance-11 initial and step-5 screenshots,
and the user-observed 12-frame sequence.

The archived `solved-led.png` and `distance11-led-final.png` are byte-identical
copies of one image. They are retained under their historical names, but must
not be counted as two independent screen captures. Case-specific register
captures and status records are listed in the GUI evidence guide. The initial
and move-5 distance-11 images provide separate sampled animation evidence.

The LED sources were integrated into the user WSL repository. Newly built CLI
ELFs passed Windows RV32_ISS checks for solved, short, and distance11, with
retired instruction counts of 557, 753, and 1,468,209. Reports and build
provenance are archived in [windows-cli/20261007-160248/](supplementary/windows-cli/20261007-160248/).

The same three CLI ELF cases also completed in Windows RV32_5S with forwarding
and hazard detection, using RV32I only. Each returned x25=0x600d and x26=0;
x27 was 0, 1, and 11 respectively. These are the three-case visual-pipeline
checks for T7; they do not replace testing any additional grader-supplied state.

The instruction-level walkthrough and ten original screenshots are archived
in [windows-pipeline/20261007/WALKTHROUGH.md](supplementary/windows-pipeline/20261007/WALKTHROUGH.md).
They cover IF/ID/EX/MEM/WB, store signals and memory contents, jump flushing,
register write enable, destination/data, and the selected WB multiplexer path.
The walkthrough distinguishes observed values from uncaptured transitions.
No historical distance-11 gate was rerun for this integration. The
[HackMD report](https://hackmd.io/TMhkNvaMTGOpdAZwlM0ZgA) now includes the LED
mapping, Windows observations, instruction walkthrough and results discussion.
Earlier pending-integration statements in the archived GUI guide describe
the state when those captures were packaged; the current status is recorded here.

Requirement source: [Homework 1](https://hackmd.io/@sysprog/2026-arch-homework1),
Visualization on the LED Matrix. Tool compatibility source:
[Ripes GNU directives at 5b8a616](https://github.com/mortbopet/Ripes/blob/5b8a616/src/assembler/gnudirectives.cpp).
