#!/usr/bin/env python3
"""Build the existing v2 C algorithm for Ripes; no third-party Python packages."""
import argparse
import datetime
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from inspect_elf import inspect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build" / "gcc"
PREFIX = "riscv64-unknown-elf-"
FLAGS = ["-O2", "-march=rv32i", "-mabi=ilp32", "-std=c99", "-ffreestanding",
         "-ffunction-sections", "-fdata-sections", "-Wall", "-Wextra", "-Werror"]
CORE = ["optimized/v1.c", "optimized/v1_tables.c", "optimized_v2/v2.c",
        "optimized_v2/v2_tables.c", "rv32/target_main.c"]
CASES = [("solved", "12345671111111", 0),
         ("short", "25314672313211", 1),
         ("distance11", "21345671111111", 11)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="Build one arbitrary valid 14-character input")
    parser.add_argument("--expected", type=int, default=-1,
                        help="Optional known optimal length; default -1")
    args = parser.parse_args()
    cases = CASES
    if args.state is not None:
        s = args.state
        if (len(s) != 14 or sorted(s[:7]) != list("1234567") or
            any(c not in "123" for c in s[7:]) or
            sum(int(c) - 1 for c in s[7:]) % 3):
            parser.error("--state must encode a valid cube")
        if not -1 <= args.expected <= 11:
            parser.error("--expected must be -1 or 0..11")
        cases = [("custom", s, args.expected)]
    elif args.expected != -1:
        parser.error("--expected requires --state")
    for tool in ("gcc", "ld", "readelf", "objdump", "nm"):
        if not shutil.which(PREFIX + tool):
            raise SystemExit("Missing tool: " + PREFIX + tool)
    BUILD.mkdir(parents=True, exist_ok=True)
    commands = []
    def run(argv):
        commands.append(argv)
        print(shlex.join(argv), flush=True)
        subprocess.run(argv, cwd=ROOT, check=True)

    objects = []
    for src in CORE:
        obj = BUILD / (src.replace("/", "_") + ".o")
        run([PREFIX + "gcc", *FLAGS, "-fstack-usage", "-c", src, "-o", str(obj)])
        objects.append(str(obj))
    startup = BUILD / "start.o"
    run([PREFIX + "gcc", "-march=rv32i", "-mabi=ilp32", "-c", "rv32/start.S",
         "-o", str(startup)])
    summaries = []
    for label, state, expected in cases:
        input_s = BUILD / (label + "-input.S")
        input_s.write_text('.section .rodata.input,"a",@progbits\n'
                           '.globl cube_input\ncube_input:\n'
                           f'.asciz "{state}"\n.balign 4\n'
                           '.globl expected_length\nexpected_length:\n'
                           f'.word {expected}\n')
        input_o = input_s.with_suffix(".o")
        run([PREFIX + "gcc", "-march=rv32i", "-mabi=ilp32", "-c", str(input_s),
             "-o", str(input_o)])
        elf = BUILD / (label + ".elf")
        run([PREFIX + "gcc", "-O2", "-march=rv32i", "-mabi=ilp32", "-nostdlib",
             "-Wl,--gc-sections", "-Wl,--build-id=none", "-Wl,-T,rv32/link.ld",
             "-Wl,-Map," + str(elf.with_suffix(".map")),
             str(startup), *objects, str(input_o), "-o", str(elf)])
        report = inspect(elf)
        summaries.append(dict(case=label, input=state, expected_length=expected,
                              elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                              **report))
        print(f"AUDIT PASS {label}: .text={report['text_bytes']} B; "
              f"static data including 4096 B stack={report['static_data_bytes']} B")
    sources = [ROOT / p for p in CORE] + [ROOT / "optimized/v1.h",
               ROOT / "optimized_v2/v2.h"] + sorted(p for p in HERE.iterdir()
               if p.is_file()) + [BUILD / (c[0] + "-input.S") for c in cases]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sources}
    def git(*args):
        p = subprocess.run(["git", *args], cwd=ROOT, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return p.stdout.strip() if p.returncode == 0 else None
    provenance = dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        platform=platform.platform(), host=platform.node(),
        gcc=subprocess.check_output([PREFIX + "gcc", "--version"], text=True).splitlines()[0],
        linker=subprocess.check_output([PREFIX + "ld", "--version"], text=True).splitlines()[0],
        source_commit=git("rev-parse", "HEAD"), worktree_status=git("status", "--short"),
        note="Source hashes identify uncommitted harness files as well as C sources.",
        c_flags=FLAGS, renderer=False, statistics=False, lto=False,
        measurement_scope="Startup, parse, solve, replay, length check, exit ecall",
        sha256=hashes)
    (BUILD / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (BUILD / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    (BUILD / "cases.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print("BASELINE_BUILD=PASS (Ripes execution is still required)")


if __name__ == "__main__":
    main()
