# minirubik

This fork develops the original C solver into a memory-bounded IDA* solver,
hand-written RV32I assembly, and a Ripes LED Matrix demonstration for
Computer Architecture Homework 1. Solutions remain shortest under the
half-turn metric (HTM).

## Start here

| Goal | Entry point |
| --- | --- |
| Read the design, measurements and discussion | [HackMD report](https://hackmd.io/TMhkNvaMTGOpdAZwlM0ZgA) |
| Build the selected native C solver | [C Version 2](optimized_v2/README.md) |
| Find the final RV32I implementation and its earlier checkpoints | [RV32I guide](rv32/README.md) |
| Run the LED demo or build renderer-free CLI ELF files | [LED / CLI integration](rv32/led/README.md) |
| Inspect measured results and original evidence | [Measurement index](measurements/README.md) |
| Follow the store, jump flush and register-write walkthrough | [Windows pipeline walkthrough](rv32/led/supplementary/windows-pipeline/20261007/WALKTHROUGH.md) |
| Inspect the incremental report history | [Historical HackMD revisions](docs/history/README.md) |

## Quick start

Run these commands from the repository root in Ubuntu/WSL. Native builds
require a C compiler, Make and Python 3:

```sh
make -C optimized_v2
./optimized_v2/build/solver-v2 21345671111111
make -C optimized_v2 check
```

For the final RV32I CLI and LED artifacts, put the GNU
`riscv64-unknown-elf-` tools on PATH, then run:

```sh
python3 rv32/led/build.py --delay 3000000
```

Outputs are generated under `rv32/build/led/`. In the pinned Windows Ripes
`v2.2.6-106-g5b8a616`, instantiate **LED Matrix 0**, Width **35**, Height **25**,
then load `short-gui.s` as Assembly and run on `RV32_ISS` with RV32I only.
The [LED guide](rv32/led/README.md) covers all three cases, custom inputs,
completion registers and the renderer switch. Use `*-cli.elf` for formal
renderer-free measurements; `*-renderer-test.elf` is a supplementary RAM test.

Running `make` at the repository root builds the original BFS programs,
`solver` and `mini`. It does not build the optimized C or RV32I versions.

## Recorded results

The implementation and evidence checkpoint is
[`8ba9a98`](https://github.com/Evan-1212/minirubik/tree/8ba9a98f218932d003bbebffd717efd433d4e196).
The renderer-free assembly v5 has **1,428 bytes of linked `.text`** and
**126,488 bytes of static data**, including its reserved 4,096-byte stack.
On the pinned Windows `RV32_ISS`, all **2,644 distance-11 states** passed
replay, optimal-length and instruction-budget checks. The measured maximum
was **4,391,914 retired instructions**; the required input `21345671111111`
took **1,468,209**. See the [measurement index](measurements/README.md) for
the raw records and measurement boundaries.

The LED integration retains the renderer-free instruction stream and animates
the computed solution. Windows GUI observations and three-case `RV32_5S`
checks are documented separately from the complete distance-11 `RV32_ISS`
test. This is not exhaustive assembly testing over all 3,674,160 states.

## Repository layout and history

| Location | Role |
| --- | --- |
| `solver.c`, `mini.c`, `report.md`, `tests/` | Original BFS baseline, explanation and tests |
| `optimized/` | C v1 and shared coordinate/transition-table code used by later versions |
| `optimized_v2/` | Selected C v2 with the packed mixed pattern database |
| `rv32/` | GCC reference, assembly refinements, complete target gate, LED integration |
| `measurements/` | Host and Windows Ripes measurement archives |
| `docs/history/` | Preserved earlier HackMD revisions |

Earlier directories are also dependencies: the final assembly uses the v5
parser, v4 search, v1 replay and shared C-generated tables. Some historical
README files and build scripts are protected by source hashes. Their
pending-work statements describe those checkpoints; the current status is
summarized in the [RV32I guide](rv32/README.md). Preserve these directories and
the original evidence when rebuilding. Generated executables normally go into
ignored build directories; the archived distance-11 template ELF is retained
as measurement evidence.

## Original C99 BFS solver

The sections below describe the upstream baseline. Its original design report
is [`report.md`](report.md); the assignment's optimization report is linked above.

An optimal C99 solver for the 2×2×2 Rubik’s Cube. It builds a breadth-first
table for all 3,674,160 states and solves every valid position in at most 11
half-turn-metric moves.

## Why a cube is a graph

Ernő Rubik created the original cube in 1974 to demonstrate how parts can move
independently without breaking the whole. A 3×3 cube has 20 moving pieces and
about 4.3 × 10¹⁹ reachable arrangements. The smaller 2×2 cube keeps the eight
corners and removes the edges and fixed centers. [Philo Li’s formula-free
introduction](https://philoli.com/zh/blog/solve-rubiks-cube-without-formulas/)
offers the key intuition: every turn is reversible, turns can be composed, and
their order matters—`R U` is generally not `U R`.

Human solvers use those facts to move a few pieces while restoring the rest;
the commutator `A B A⁻¹ B⁻¹` is the standard example. This program uses the
same group structure differently: it treats every valid arrangement as a node,
every face turn as an edge, and searches the entire graph once. It does not use
the article’s 3×3 Roux stages or a library of memorized algorithms.

The solver gives the eight corner positions the numbers `0–7`. The 2.5D
walkthrough below shows where those numbers are on the physical cube.

## How it works

1. Fix one corner to remove whole-cube rotations.
2. Rank the remaining corner permutation and six independent orientations into
   a dense integer.
3. Breadth-first search outward from solved using `R`, `B`, and `D`, including
   inverse and half turns.
4. Store one move toward solved for every state; following those moves gives an
   optimal solution of at most 11 moves.

## Build and run

```sh
make
make check
make prove   # optional: Frama-C WP proof, needs frama-c and alt-ergo
./solver 21345671111111
```

`make` builds two binaries. `solver` is the documented one, with contracts, a
`--self-test` mode, and diagnostics on stderr. `mini` is a golfed variant that
solves the same input and prints the same line, kept as a readability contrast;
it has no `--self-test` and prints nothing on failure, and it trades roughly
eight times the runtime and three times the memory for its brevity.

The 14-digit argument describes the scramble and the printed line is the
solution. Both formats are explained below.

### Reading the 14-digit input

The program receives one 14-digit code with no spaces. For explanation, split
it into two groups:

```diagram
2134567 1111111
└── P ─┘ └── O ─┘
  cubies   twists
```

Imagine seven numbered seats and seven students. A position is a seat fixed in
space; a cubie is the physical corner that can move to another seat. In the
solved cube, cubie 1 sits in position 1, cubie 2 in position 2, and so on.
The real cube has no printed numbers; `0–7` are labels used only by this solver.

#### Step 1: Hold the cube in one direction

Keep `FRONT` facing you and `UP` pointing upward. Position `0` is the corner
nearest the upper-left of the front face. It is an anchor for describing the
other corners; the physical cubie is not glued in place.

```diagram
                              BACK
                    ·───────────────·
                   ╱               ╱│
                  ╱        UP     ╱ │
                 ╱               ╱  │
              [0]───────────────·   │
               │                │   │
               │     FRONT      │ R │
               │                │   ·
               │                │  ╱
               │                │ ╱
               │                │╱
               ·────────────────·
```

`R` marks the narrow `RIGHT` face.

#### Step 2: Separate the front and back layers

A 2×2×2 cube has only corner cubies. Looking from the fixed direction, four
corner positions touch the front face and four touch the back face. Each
bracketed number below names one whole corner, not one colored sticker:

```diagram
 FRONT LAYER                          BACK LAYER

 upper-left   upper-right             upper-left   upper-right
     [0]────────[1]                       [7]────────[4]
      │          │                         │          │
      │          │       front ↔ back      │          │
     [3]────────[2]                       [6]────────[5]
 down-left    down-right               down-left    down-right
```

The front layer runs clockwise from its upper-left corner as `0, 1, 2, 3`.
The back layer is drawn as if seen through the cube from the front: `7` is
upper-left, followed clockwise by `4, 5, 6`.

#### Step 3: Join the two layers into positions 0–7

Slide the back square up and to the right, the same direction the cube recedes
in Step 1, to get the complete 2.5D position map. The back edges are drawn
through the front face rather than hidden behind it:

```diagram
                           BACK
                      [7]────────[4]
                     ╱ │        ╱ │
                  [0]──│─────[1]  │
                   │   │      │   │
                   │  [6]─────│──[5]
                   │ ╱        │ ╱
                  [3]────────[2]
                      FRONT
```

The seven characters of `P` describe positions `1, 2, 3, 4, 5, 6, 7` in that
order; the anchor at position `0` is left out.

#### Step 4: Put the cubies into those positions

Compare the position map on the left with the filled cube on the right. Read
`P = 2134567` from left to right to fill the positions. The arrows below the
figure identify the two positions that change.

```diagram
 POSITION MAP                             AFTER P = 2134567
 (fixed seats)                            (cubies now in seats)

     [7]────────[4]                           [7]────────[4]
    ╱ │        ╱ │                           ╱ │        ╱ │
 [0]──│─────[1]  │                        [0]──│─────[2]  │
  │   │      │   │                         │   │      │   │
  │  [6]─────│──[5]                        │  [6]─────│──[5]
  │ ╱        │ ╱                           │ ╱        │ ╱
 [3]────────[2]                           [3]────────[1]
     FRONT                                    FRONT

 position:     1 2 3 4 5 6 7
 P says:       2 1 3 4 5 6 7
               │ │ └───────── cubies 3–7 stay in their matching seats
               │ └─────────── put cubie 1 in position 2: [2] becomes [1]
               └───────────── put cubie 2 in position 1: [1] becomes [2]
```

So the first two digits, `21`, exchange the two corners on the front-right
edge. The remaining digits, `34567`, leave the other five movable corners
where they were. `P` must contain every digit from `1` through `7` exactly
once; otherwise a cubie would be missing or duplicated.

The seven seats named by `P` are:

| Position | Corner of the cube |
| :---: | :--- |
| 1 | front, upper, right |
| 2 | front, down, right |
| 3 | front, down, left |
| 4 | back, upper, right |
| 5 | back, down, right |
| 6 | back, down, left |
| 7 | back, upper, left |

The second group, `O = 1111111`, describes the twist of the cubie in each of
those same seven positions:

| Digit | Meaning |
| :---: | :--- |
| 1 | not twisted |
| 2 | twisted by +120° |
| 3 | twisted by −120° |

Here every orientation digit is `1`, so the two corners change places without
being twisted. For a valid cube, convert orientation digits to `0`, `1`, and
`2`; their sum must be divisible by three. The solved code is
`12345671111111`. `make check` uses the exchanged-corner example above.

## Reading the solution

```sh
$ ./solver 21345671111111
B' R' D2 R' B R B' R D2 B R'
```

Each token is one face turn. Apply them left to right; after the last one the
cube is solved.

| Token | Meaning |
| :---: | :--- |
| `R` | turn the `RIGHT` face 90° clockwise |
| `B` | turn the `BACK` face 90° clockwise |
| `D` | turn the `DOWN` face 90° clockwise |

Clockwise means clockwise as seen by someone looking directly at that face from
outside the cube, so you have to walk around to the back to read `B` and look up
from underneath to read `D`. Two suffixes modify a turn:

| Suffix | Meaning |
| :---: | :--- |
| none | 90° clockwise |
| `'` | 90° counterclockwise, the inverse |
| `2` | 180°, direction does not matter |

`R`, `B`, and `D` are the only faces that appear, because turning `UP`, `FRONT`,
or `LEFT` would move the anchor at position `0`. A turn counts as one move
whichever suffix it carries, which is the half-turn metric; under that metric no
position needs more than 11 moves. Solving an already-solved cube prints an
empty line.

See [`report.md`](report.md) for the model, algorithm, diagrams, and Frama-C
validation notes.
