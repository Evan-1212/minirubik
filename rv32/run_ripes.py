#!/usr/bin/env python3
"""Run the GCC reference using Windows Ripes from WSL and archive raw telemetry."""
import argparse
import csv
import datetime
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build" / "gcc"
RIPES = Path("/mnt/c/Tools/Ripes/Ripes.exe")
RUN_ROOT = Path("/mnt/c/Tools/Ripes/hw1_stage4")


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def powershell_string(value):
    return "'" + value.replace("'", "''") + "'"


def windows_path(path):
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processor", choices=["RV32_ISS", "RV32_5S"],
                        default="RV32_ISS")
    args = parser.parse_args()
    for tool in ("powershell.exe", "wslpath"):
        if not shutil.which(tool):
            raise SystemExit("Run this script in WSL; missing " + tool)
    if not RIPES.is_file():
        raise SystemExit("Ripes executable not found: " + str(RIPES))
    if not (BUILD / "cases.json").is_file():
        raise SystemExit("Run python3 rv32/build_baseline.py first")
    cases = json.loads((BUILD / "cases.json").read_text())
    provenance = json.loads((BUILD / "provenance.json").read_text())
    for name, digest in provenance["sha256"].items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != digest:
            raise SystemExit("Source changed after build; rebuild first: " + name)
    for case in cases:
        if sha256(BUILD / case["elf"]) != case["elf_sha256"]:
            raise SystemExit("ELF changed after audit; rebuild first")

    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + args.processor + "-" + uuid.uuid4().hex[:6]
    working = RUN_ROOT / run_id
    archive = ROOT / "measurements" / "stage4-gcc" / run_id
    working.mkdir(parents=True, exist_ok=False)
    archive.mkdir(parents=True, exist_ok=False)
    for name in ("provenance.json", "commands.json", "cases.json"):
        shutil.copy2(BUILD / name, archive / name)
    for pattern in ("*.su", "*.audit.json", "*.sections.txt", "*.symbols.txt", "*.disasm.txt", "*.map"):
        for path in BUILD.glob(pattern):
            shutil.copy2(path, archive / path.name)
    environment = dict(timestamp_utc=now.isoformat(), processor=args.processor,
        pinned_ripes_version="v2.2.6-106-g5b8a616 (version recorded in Stage 1)",
        ripes_executable=windows_path(RIPES), ripes_sha256=sha256(RIPES),
        windows_working_directory=windows_path(working), renderer=False,
        measurement_scope=provenance["measurement_scope"],
        status="INCOMPLETE", commands=[])
    environment_path = archive / "ripes-environment.json"
    environment_path.write_text(json.dumps(environment, indent=2) + "\n")
    rows = []
    for case in cases:
        label = case["case"]
        shutil.copy2(BUILD / case["elf"], working / case["elf"])
        report_name = label + ".json"
        arguments = (f"--mode cli --src {case['elf']} -t elf --proc {args.processor} "
                     f"--timeout 120000 --iret --regs --runinfo --exectime --json "
                     f"--output {report_name}")
        command = ("$ErrorActionPreference = 'Stop'; "
                   "$p = Start-Process -FilePath " + powershell_string(windows_path(RIPES)) +
                   " -WorkingDirectory " + powershell_string(windows_path(working)) +
                   " -ArgumentList " + powershell_string(arguments) +
                   " -PassThru -Wait; exit $p.ExitCode")
        environment["commands"].append(command)
        environment_path.write_text(json.dumps(environment, indent=2) + "\n")
        print(f"Running {label}: {case['input']} on {args.processor}", flush=True)
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=150)
        (archive / (label + ".launch.log")).write_text(result.stdout)
        raw = working / report_name
        if raw.exists():
            shutil.copy2(raw, archive / report_name)
        if result.returncode or not raw.is_file():
            raise SystemExit(f"Ripes failed (exit {result.returncode}). Evidence: {archive}\n" + result.stdout)
        report = json.loads(raw.read_text(encoding="utf-8-sig"))
        registers = report.get("registers", report.get("regs", {}))
        def register(index, alias):
            for key in ("x" + str(index), alias):
                if key in registers:
                    value = registers[key]
                    return int(value, 0) if isinstance(value, str) else int(value)
            raise ValueError("Missing register " + str(index) + "; inspect " + str(raw))
        completed, status, length = register(25, "s9"), register(26, "s10"), register(27, "s11")
        iret = int(report.get("# instructions retired", report.get("iret", -1)))
        if completed != 0x600d or status != 0 or not 0 <= length <= 11 or iret <= 0:
            raise SystemExit(f"Target validation failed: marker={completed}, status={status}, length={length}, iret={iret}; evidence: {archive}")
        if case["expected_length"] >= 0 and length != case["expected_length"]:
            raise SystemExit("Unexpected solution length; evidence: " + str(archive))
        row = dict(case=label, input=case["input"], processor=args.processor,
                   length=length, status=status, retired_instructions=iret,
                   execution_ms=report.get("execution time (ms)", ""),
                   text_bytes=case["text_bytes"], static_data_bytes=case["static_data_bytes"])
        rows.append(row)
        with (archive / "summary.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            writer.writeheader()
            writer.writerows(rows)
        print(f"PASS {label}: length={length}, iret={iret}, .text={case['text_bytes']} B", flush=True)
    environment["status"] = "PASS"
    environment_path.write_text(json.dumps(environment, indent=2) + "\n")
    print(f"TARGET_SMOKE=PASS ({len(rows)} cases; not the full distance-11 gate)")
    print("Evidence: " + str(archive.relative_to(ROOT)))


if __name__ == "__main__":
    main()
