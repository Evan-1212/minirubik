#include "pattern_build.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    uint8_t selected[3];
    if (argc != 4) {
        fputs("usage: generate-tables CUBIE1 CUBIE2 CUBIE3 (input labels 1..7)\n", stderr);
        return 2;
    }
    for (unsigned k = 0; k < 3; ++k) {
        if (argv[k + 1][0] < '1' || argv[k + 1][0] > '7' || argv[k + 1][1]) return 2;
        selected[k] = (uint8_t)(argv[k + 1][0] - '1');
    }
    host_pattern *pdb = malloc(sizeof *pdb);
    if (!pdb || !host_build_pattern(pdb, selected)) {
        free(pdb);
        fputs("pattern generation failed\n", stderr);
        return 1;
    }
    fprintf(stderr, "pattern=%u%u%u states=%u maximum=%u goal_q=%u packed_bytes=%u\n",
            selected[0] + 1, selected[1] + 1, selected[2] + 1,
            V2_ABSTRACT_STATES, pdb->maximum, pdb->goal_q, V2_PACKED_BYTES);
    int ok = host_emit_pattern(pdb);
    free(pdb);
    return ok ? 0 : 1;
}
