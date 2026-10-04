#define _POSIX_C_SOURCE 200809L
#include "v1.h"
#include "host_reference.h"
#include <inttypes.h>
#include <time.h>

/* Oracle moves are rebuilt from baseline state_t operations, independently
 * of the generated target tables. Only this HOST executable allocates BFS.
 */
static uint16_t oracle_p[9][V1_PERMS], oracle_o[9][V1_ORIS];
static const unsigned expected_histogram[12] = {
    1, 9, 54, 321, 1847, 9992, 50136, 227536,
    870072, 1887748, 623800, 2644
};

static double now(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) exit(1);
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

static void fail(const char *what, unsigned index)
{
    fprintf(stderr, "FAIL: %s at index %u\n", what, index);
    exit(1);
}

static void state_string(unsigned rank, char out[15])
{
    state_t s;
    unrank_state(rank, &s);
    for (unsigned i = 0; i < 7; ++i) {
        out[i] = (char)('1' + s.p[i]);
        out[7 + i] = (char)('1' + s.o[i]);
    }
    out[14] = 0;
}

static uint8_t *oracle(void)
{
    state_t s;
    for (unsigned p = 0; p < V1_PERMS; ++p) {
        unrank_state(p * V1_ORIS, &s);
        for (unsigned m = 0; m < 9; ++m) {
            state_t n = apply_move(s, (uint8_t)m);
            oracle_p[m][p] = (uint16_t)(rank_state(&n) / V1_ORIS);
        }
    }
    for (unsigned o = 0; o < V1_ORIS; ++o) {
        unrank_state(o, &s);
        for (unsigned m = 0; m < 9; ++m) {
            state_t n = apply_move(s, (uint8_t)m);
            oracle_o[m][o] = (uint16_t)(rank_state(&n) % V1_ORIS);
        }
    }
    uint8_t *distance = malloc(STATES);
    uint32_t *q = malloc((size_t)STATES * sizeof *q);
    unsigned histogram[12] = {0};
    if (!distance || !q) fail("host allocation", 0);
    memset(distance, 255, STATES);
    q[0] = 0;
    distance[0] = 0;
    histogram[0] = 1;
    unsigned head = 0, tail = 1;
    while (head < tail) {
        unsigned rank = q[head++], p = rank / V1_ORIS, o = rank % V1_ORIS;
        for (unsigned m = 0; m < 9; ++m) {
            unsigned next = oracle_p[m][p] * V1_ORIS + oracle_o[m][o];
            if (distance[next] != 255) continue;
            unsigned d = distance[rank] + 1U;
            if (d > 11 || tail >= STATES) fail("oracle bounds", rank);
            distance[next] = (uint8_t)d;
            ++histogram[d];
            q[tail++] = next;
        }
    }
    free(q);
    if (tail != STATES) fail("oracle reachability", tail);
    for (unsigned d = 0; d < 12; ++d)
        if (histogram[d] != expected_histogram[d]) fail("oracle histogram", d);
    return distance;
}

static unsigned verify_pdb(unsigned n, const uint8_t *distance, int permutation)
{
    unsigned maximum = 0;
    for (unsigned i = 0; i < n; ++i) {
        unsigned d = distance[i], descending = (i == 0);
        if (d > 11 || ((d == 0) != (i == 0))) fail("PDB value", i);
        if (d > maximum) maximum = d;
        for (unsigned m = 0; m < 9; ++m) {
            unsigned next = permutation ? oracle_p[m][i] : oracle_o[m][i];
            if (d > 1U + distance[next]) fail("PDB edge bound", i);
            if (d == 1U + distance[next]) descending = 1;
        }
        if (!descending) fail("PDB descending neighbor", i);
    }
    return maximum;
}

static int solve_checked(unsigned rank, const uint8_t *distance, uint8_t path[11])
{
    v1_coord s = {(uint16_t)(rank / V1_ORIS), (uint16_t)(rank % V1_ORIS)};
    int n = v1_solve(s, path);
    if (n < 0 || n != distance[rank]) fail("nonoptimal solution", rank);
    if (!v1_replay(s, path, (unsigned)n)) fail("coordinate replay", rank);
    /* Replay with the original cubie model, not the target transition code. */
    state_t physical;
    unrank_state(rank, &physical);
    for (int i = 0; i < n; ++i) {
        if (path[i] >= 9) fail("invalid returned move", rank);
        if (i && path[i] / 3 == path[i - 1] / 3) fail("same-face path", rank);
        physical = apply_move(physical, path[i]);
    }
    if (rank_state(&physical) != 0) fail("physical replay", rank);
    return n;
}

static void check(const uint8_t *distance, double oracle_seconds)
{
    double begin = now();
    for (unsigned f = 0; f < 3; ++f) {
        for (unsigned p = 0; p < V1_PERMS; ++p)
            if (v1_perm_next[f][p] != oracle_p[f * 3][p])
                fail("permutation transition", p);
        for (unsigned o = 0; o < V1_ORIS; ++o)
            if (v1_ori_next[f][o] != oracle_o[f * 3][o])
                fail("orientation transition", o);
    }
    unsigned mp = verify_pdb(V1_PERMS, v1_perm_dist, 1);
    unsigned mo = verify_pdb(V1_ORIS, v1_ori_dist, 0);
    for (unsigned rank = 0; rank < STATES; ++rank) {
        char input[15];
        v1_coord s;
        state_string(rank, input);
        if (!v1_parse(input, &s) || s.p != rank / V1_ORIS || s.o != rank % V1_ORIS)
            fail("full-domain parser/rank", rank);
        if (v1_heuristic(s) > distance[rank]) fail("H1 admissibility", rank);
    }
    const char *cases[] = {
        "12345671111111", "25314672313211", "21345671111111",
        "62345713133111", "24316572122213", "25713642221111",
        "24513763133333", "43752611332133", "25416373331111"
    };
    uint8_t path[11];
    for (unsigned i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        state_t s;
        if (!parse_state(cases[i], &s)) fail("test fixture", i);
        solve_checked(rank_state(&s), distance, path);
    }
    v1_coord bad = {5040, 0};
    if (v1_solve(bad, path) != -1 || v1_replay(bad, path, 0))
        fail("coordinate bounds", 0);
    bad = (v1_coord){0, 729};
    if (v1_solve(bad, path) != -1 || v1_replay(bad, path, 0))
        fail("coordinate bounds", 1);
    bad = (v1_coord){0, 0};
    if (v1_solve(bad, NULL) != -1 || v1_replay(bad, path, 12))
        fail("path bounds", 0);
    path[0] = 9;
    if (v1_replay(bad, path, 1)) fail("invalid move accepted", 0);
    printf("{\n  \"mode\": \"check\", \"status\": \"PASS\",\n"
           "  \"oracle_states\": %u, \"oracle_diameter\": 11,\n"
           "  \"H1_states\": %u, \"parser_states\": %u,\n"
           "  \"H2\": \"PASS\", \"H4\": \"N/A: byte tables, no packing\",\n"
           "  \"permutation_pdb_max\": %u, \"orientation_pdb_max\": %u,\n"
           "  \"table_bytes\": %zu, \"workspace_bytes\": %zu,\n"
           "  \"oracle_seconds\": %.6f, \"check_seconds\": %.6f\n}\n",
           STATES, STATES, STATES, mp, mo, v1_table_bytes(),
           v1_workspace_bytes(), oracle_seconds, now() - begin);
}

int main(int argc, char **argv)
{
    if (argc < 2 || (strcmp(argv[1], "--check") &&
                    strcmp(argv[1], "--hardest") && strcmp(argv[1], "--all"))) {
        fputs("usage: verify-v1 --check | --hardest [CSV] | --all [START COUNT]\n", stderr);
        return 2;
    }
    int hardest = strcmp(argv[1], "--hardest") == 0;
    int is_check = strcmp(argv[1], "--check") == 0;
    if ((is_check && argc != 2) || (hardest && argc != 2 && argc != 3) ||
        (!is_check && !hardest && argc != 2 && argc != 4)) return 2;
    unsigned first = 0, count = STATES;
    if (argc == 4) {
        char *end;
        unsigned long a = strtoul(argv[2], &end, 10);
        if (!argv[2][0] || *end || a >= STATES) return 2;
        unsigned long b = strtoul(argv[3], &end, 10);
        if (!argv[3][0] || *end || b == 0 || b > STATES - a) return 2;
        first = (unsigned)a;
        count = (unsigned)b;
    }
    double begin = now();
    uint8_t *distance = oracle();
    double oracle_seconds = now() - begin;
    if (is_check) {
        check(distance, oracle_seconds);
        free(distance);
        return fflush(stdout) != 0 || ferror(stdout);
    }
    FILE *csv = NULL;
    if (hardest && argc == 3) {
        csv = fopen(argv[2], "w");
        if (!csv) { perror(argv[2]); free(distance); return 1; }
        fputs("rank,state,length,initial_bound,iterations,generated,expanded,pruned,solution\n", csv);
    }
    begin = now();
    unsigned checked = 0, worst_rank = 0;
    uint64_t total = 0, maximum = 0, max_expanded = 0;
    uint8_t path[11];
    for (unsigned rank = first; rank < first + count; ++rank) {
        if (hardest && distance[rank] != 11) continue;
        int n = solve_checked(rank, distance, path);
        ++checked;
        total += v1_last_stats.generated;
        if (v1_last_stats.generated > maximum) {
            maximum = v1_last_stats.generated;
            worst_rank = rank;
        }
        if (v1_last_stats.expanded > max_expanded)
            max_expanded = v1_last_stats.expanded;
        if (csv) {
            char input[15];
            state_string(rank, input);
            fprintf(csv, "%u,%s,%d,%u,%u,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",",
                    rank, input, n, v1_last_stats.initial_bound,
                    v1_last_stats.iterations, v1_last_stats.generated,
                    v1_last_stats.expanded, v1_last_stats.pruned);
            for (int i = 0; i < n; ++i)
                fprintf(csv, "%s%s", i ? " " : "", move_names[path[i]]);
            fputc('\n', csv);
        }
        if (!hardest && checked % 100000 == 0)
            fprintf(stderr, "checked=%u/%u elapsed=%.1fs\n", checked, count, now() - begin);
    }
    double search_seconds = now() - begin;
    if (csv && fclose(csv) != 0) fail("CSV write", 0);
    if (checked != (hardest ? 2644U : count)) fail("search coverage", checked);
    char worst[15];
    state_string(worst_rank, worst);
    state_t sample;
    if (!parse_state("21345671111111", &sample)) fail("sample parse", 0);
    solve_checked(rank_state(&sample), distance, path);
    printf("{\n  \"mode\": \"%s\", \"status\": \"PASS\",\n"
           "  \"start_rank\": %u, \"states_checked\": %u,\n"
           "  \"optimal_lengths_and_physical_replay\": true,\n"
           "  \"total_generated\": %" PRIu64 ", \"max_generated\": %" PRIu64 ",\n"
           "  \"max_expanded\": %" PRIu64 ", \"worst_generated_state\": \"%s\",\n"
           "  \"sample_generated\": %" PRIu64 ", \"sample_expanded\": %" PRIu64 ",\n"
           "  \"oracle_seconds\": %.6f, \"search_validation_seconds\": %.6f,\n"
           "  \"Ripes_retired_instructions\": null\n}\n",
           hardest ? "hardest" : "all", first, checked, total, maximum,
           max_expanded, worst, v1_last_stats.generated, v1_last_stats.expanded,
           oracle_seconds, search_seconds);
    free(distance);
    return fflush(stdout) != 0 || ferror(stdout);
}
