#include "host_oracle.h"
#include "pattern_build.h"

int main(int argc, char **argv)
{
    if (argc != 2) {
        fputs("usage: select-pattern OUTPUT_PATTERN_FILE > sweep.csv\n", stderr);
        return 2;
    }
    uint8_t *distance = oracle();
    unsigned hardest[2644], count = 0;
    for (unsigned rank = 0; rank < STATES; ++rank)
        if (distance[rank] == 11) {
            if (count == 2644) fail("too many d11 states", count);
            hardest[count++] = rank;
        }
    if (count != 2644) fail("d11 count", count);
    host_pattern *pdb = malloc(sizeof *pdb);
    if (!pdb) fail("host allocation", 0);
    uint64_t best_max = UINT64_MAX, best_total = UINT64_MAX;
    uint8_t best[3] = {0}, path[11];
    puts("cubies,max_distance,states_checked,total_generated,max_generated,max_expanded,total_pattern_lookups,worst_state,search_validation_seconds");
    for (unsigned a = 0; a < 5; ++a)
        for (unsigned b = a + 1; b < 6; ++b)
            for (unsigned c = b + 1; c < 7; ++c) {
                uint8_t chosen[3] = {(uint8_t)a, (uint8_t)b, (uint8_t)c};
                if (!host_build_pattern(pdb, chosen)) fail("pattern build", a);
                uint64_t total = 0, maximum = 0, max_expanded = 0, queries = 0;
                unsigned worst = 0;
                double begin = now();
                for (unsigned i = 0; i < count; ++i) {
                    unsigned rank = hardest[i];
                    v1_coord s = {(uint16_t)(rank / V1_ORIS), (uint16_t)(rank % V1_ORIS)};
                    int n = v2_solve_with(&pdb->view, s, path);
                    if (n != 11 || !v1_replay(s, path, 11)) fail("candidate solution", rank);
                    state_t physical;
                    unrank_state(rank, &physical);
                    for (unsigned j = 0; j < 11; ++j) physical = apply_move(physical, path[j]);
                    if (rank_state(&physical)) fail("candidate physical replay", rank);
                    total += v2_last_stats.generated;
                    queries += v2_last_stats.pattern_lookups;
                    if (v2_last_stats.generated > maximum) {
                        maximum = v2_last_stats.generated;
                        worst = rank;
                    }
                    if (v2_last_stats.expanded > max_expanded)
                        max_expanded = v2_last_stats.expanded;
                }
                char state[15];
                state_string(worst, state);
                printf("%u%u%u,%u,%u,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%s,%.6f\n",
                       a + 1, b + 1, c + 1, pdb->maximum, count,
                       total, maximum, max_expanded, queries, state, now() - begin);
                if (fflush(stdout) != 0) fail("CSV write", 0);
                fprintf(stderr, "pattern=%u%u%u max_generated=%" PRIu64 " total=%" PRIu64 "\n",
                        a + 1, b + 1, c + 1, maximum, total);
                if (maximum < best_max || (maximum == best_max && total < best_total)) {
                    best_max = maximum;
                    best_total = total;
                    memcpy(best, chosen, 3);
                }
            }
    FILE *out = fopen(argv[1], "w");
    if (!out) { perror(argv[1]); return 1; }
    fprintf(out, "%u %u %u\n", best[0] + 1, best[1] + 1, best[2] + 1);
    if (fclose(out) != 0) fail("pattern output", 0);
    fprintf(stderr, "selected=%u%u%u max_generated=%" PRIu64 " total=%" PRIu64 "\n",
            best[0] + 1, best[1] + 1, best[2] + 1, best_max, best_total);
    free(pdb);
    free(distance);
    return 0;
}
