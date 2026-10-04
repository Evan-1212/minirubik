"""CLI contract and move replay, without relying on one exact optimal path."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCE = ((1, 4, 2, 0, 3, 5, 6), (0, 1, 2, 4, 5, 6, 3), (0, 2, 5, 3, 1, 4, 6))
TWIST = ((1, 2, 0, 2, 1, 0, 0), (0, 0, 0, 1, 2, 1, 2), (0, 0, 0, 0, 0, 0, 0))
NAMES = ("R", "R2", "R'", "B", "B2", "B'", "D", "D2", "D'")


def replay(state, moves):
    p = [int(x) - 1 for x in state[:7]]
    o = [int(x) - 1 for x in state[7:]]
    for name in moves:
        m = NAMES.index(name)
        f, turns = divmod(m, 3)
        for _ in range(turns + 1):
            p = [p[i] for i in SOURCE[f]]
            o = [(o[j] + TWIST[f][i]) % 3 for i, j in enumerate(SOURCE[f])]
    return p == list(range(7)) and o == [0] * 7


vectors = []
for line in (ROOT.parent / "tests/solutions.txt").read_text().splitlines():
    if not line or line.startswith("#"):
        continue
    state, solution = line.split("|")
    vectors.append((state, len(solution.split())))
vectors.append(("25314672313211", 1))
invalid = [[], ["12345671111111"] * 2]
invalid += [["12345671111111"[:i]] for i in range(14)]
invalid += [[s] for s in (
    "123456711111111", "02345671111111", "82345671111111",
    "12345671111110", "12345671111114", "1234567111111a",
    "11345671111111", "12345671111112", "1234567111111é")]

outputs = {}
for binary in ("solver-v2", "solver-v2-stats"):
    exe = ROOT / "build" / binary
    outputs[binary] = []
    for state, length in vectors:
        result = subprocess.run([exe, state], capture_output=True, text=True, check=True)
        moves = result.stdout.split()
        assert result.stdout == " ".join(moves) + "\n", (binary, "format")
        assert len(moves) == length and replay(state, moves), (binary, state)
        outputs[binary].append(result.stdout)
    for args in invalid:
        result = subprocess.run([exe, *args], capture_output=True)
        assert result.returncode == 2 and not result.stdout, (binary, args)
    result = subprocess.run(["sh", "-c", '"$1" 12345671111111 >&-', "sh", str(exe)],
                            capture_output=True)
    assert result.returncode == 1, (binary, "closed stdout")
assert outputs["solver-v2"] == outputs["solver-v2-stats"]
print(f"PASS: {len(vectors)} optimal/replayed CLI vectors, {len(invalid)} rejection cases per build; stats builds agree; closed stdout detected")
