"""Check the linked native solver; this does not certify RV32I sections."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parent
exe = ROOT / "build/solver-v2"
sections = {}
for line in subprocess.check_output(["size", "-A", exe], text=True).splitlines():
    fields = line.split()
    if len(fields) == 3 and fields[0].startswith("."):
        sections[fields[0]] = int(fields[1])
data = {k: v for k, v in sections.items()
        if k.startswith((".data", ".bss", ".rodata"))}
symbols = subprocess.check_output(["nm", "-S", exe], text=True)
for dead in ("v1_solve", "v1_ori_dist", "v1_last_stats", "v2_last_stats",
             "baseline_cli_main", "pattern_build_unused_baseline_main",
             "host_build_pattern"):
    assert not any(line.split()[-1] == dead for line in symbols.splitlines()), dead
undefined = subprocess.check_output(["nm", "-u", exe], text=True)
for forbidden in ("malloc", "calloc", "realloc", "free"):
    assert not any(line.split()[-1].split("@")[0] == forbidden
                   for line in undefined.splitlines()), forbidden
assert sum(data.values()) <= 128 * 1024, data
print(json.dumps({
    "native_static_sections": data,
    "native_static_bytes_including_data_rel_ro": sum(data.values()),
    "native_text_bytes": sections[".text"],
    "unused_v1_search_orientation_pdb_and_stats_removed": True,
    "host_generators_not_linked": True,
    "target_RV32I_certified": False,
}, indent=2))
