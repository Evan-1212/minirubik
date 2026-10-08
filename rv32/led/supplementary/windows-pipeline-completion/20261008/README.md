# RV32_5S end-to-end completion evidence (T7)

These original Windows Ripes screenshots were supplied and reviewed on
2026-10-08. The directory date records receipt/archiving, not a newly measured
execution date. No screenshot pixels were edited.

Each screenshot shows the loaded renderer-free CLI ELF, the **5-stage
processor**, **RV32I**, completion registers and a normal exit console.

| Case | Input | Loaded file | x25 | x26 | x27 | Result |
|---|---|---|---|---|---|---|
| Solved | `12345671111111` | `solved-cli.elf` | `0x600d` | `0` | `0` | PASS |
| Short | `25314672313211` | `short-cli.elf` | `0x600d` | `0` | `1` | PASS |
| Required distance-11 | `21345671111111` | `distance11-cli.elf` | `0x600d` | `0` | `0xb` (11) | PASS |

The input mapping comes from the existing build-case metadata. The visible
loaded paths are `C:/Tools/Ripes/LED-Matrix-Verified/build/*-cli.elf`.
`observations.json` records exactly what is visible and the original-image
hashes. Filenames and screenshots alone do not independently establish ELF
hashes or the Ripes executable version.

Related archived provenance and complementary evidence:

- [Windows CLI archive](../../windows-cli/20261007-160248/):
  ISS raw reports, build-case inputs, executable provenance and ELF hashes.
- [Startup walkthrough](../../windows-pipeline/20261007/WALKTHROUGH.md):
  stepped instruction stages and control signals, a separate evidence scope.
- [LED guide](../../../README.md): shared source and GUI/CLI renderer switch.

The audit inspected commit `7176c2d663446c26959e8103f05b9475380edf50`.
Its implementation/evidence checkpoint is
`8ba9a98f218932d003bbebffd717efd433d4e196`; only four README/index files
changed between those commits. Clean rebuilt CLI ELF hashes matched the
archived metadata. This directory adds evidence without changing runtime
source or historical measurements.

These captures close the three-case visual-pipeline part of T7. They are not
new retired-instruction measurements, a full-domain pipeline test, or LED
animation captures. The full 2,644-case performance gate remains the pinned
RV32_ISS renderer-off archive.

## Verify archived files

From this directory:

```sh
sha256sum -c SHA256SUMS
```

`SHA256SUMS` covers the three images, this README and `observations.json`.
