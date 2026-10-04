#include "host_oracle.h"
#include "pattern_build.h"

static int solve_checked(unsigned rank, const uint8_t *distance, uint8_t path[11])
{
    v1_coord s = {(uint16_t)(rank / V1_ORIS), (uint16_t)(rank % V1_ORIS)};
    int n = v2_solve(s, path);
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
    host_pattern *raw = malloc(sizeof *raw);
    if (!raw || !host_build_pattern(raw, v2_selected_cubies)) fail("host pattern", 0);
    if (memcmp(raw->projection, v2_projection, sizeof raw->projection) ||
        memcmp(raw->row_offset, v2_row_offset, sizeof raw->row_offset) ||
        memcmp(raw->packed, v2_packed, sizeof raw->packed)) fail("regenerated tables", 0);
    unsigned representatives[V2_PLACEMENTS], occurrences[V2_PLACEMENTS] = {0};
    for (unsigned p = 0; p < V1_PERMS; ++p) {
        unsigned q = v2_projection[p];
        if (q >= V2_PLACEMENTS) fail("projection bounds", p);
        representatives[q] = p;
        ++occurrences[q];
        /* Projection must commute with every physical move. */
        for (unsigned f = 0; f < 3; ++f) {
            unsigned nq = q;
            for (unsigned t = 0; t < 3; ++t) {
                nq = raw->next[f][nq];
                if (nq != v2_projection[oracle_p[f * 3 + t][p]])
                    fail("projection/move consistency", p);
            }
        }
    }
    unsigned maximum = 0, zeros = 0, odd = 0, even = 0;
    for (unsigned q = 0; q < V2_PLACEMENTS; ++q) {
        if (occurrences[q] != 24 || v2_row_offset[q] != q * V2_ROW_BYTES)
            fail("projection/row completeness", q);
        if ((v2_packed[v2_row_offset[q] + V2_ROW_BYTES - 1] >> 4) != 15)
            fail("odd row padding", q);
        for (unsigned o = 0; o < V1_ORIS; ++o) {
            unsigned i = q * V1_ORIS + o, d = raw->distance[i];
            v1_coord s = {(uint16_t)representatives[q], (uint16_t)o};
            if (v2_pattern_distance(&v2_default_pattern, s) != d)
                fail("H4 packed/unpacked", i);
            if (o & 1U) ++odd; else ++even;
            unsigned goal = q == raw->goal_q && o == 0;
            if (d > 11 || ((d == 0) != goal)) fail("H2 PDB value", i);
            if (d == 0) ++zeros;
            if (d > maximum) maximum = d;
            unsigned descending = goal;
            for (unsigned m = 0; m < 9; ++m) {
                unsigned nq = v2_projection[oracle_p[m][representatives[q]]];
                unsigned no = oracle_o[m][o];
                unsigned nd = raw->distance[nq * V1_ORIS + no];
                if (d > nd + 1) fail("mixed PDB edge bound", i);
                if (d == nd + 1) descending = 1;
            }
            if (!descending) fail("mixed PDB descending neighbor", i);
        }
    }
    unsigned improved = 0;
    for (unsigned rank = 0; rank < STATES; ++rank) {
        char input[15];
        v1_coord s;
        state_string(rank, input);
        if (!v1_parse(input, &s) || s.p != rank / V1_ORIS || s.o != rank % V1_ORIS)
            fail("full-domain parser/rank", rank);
        unsigned h2 = v2_heuristic(s), h1 = v1_heuristic(s);
        if (h2 > distance[rank]) fail("H1 admissibility", rank);
        if (h2 < h1) fail("v2 heuristic weaker than v1", rank);
        if (h2 > h1) ++improved;
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
    if (v2_solve(bad, path) != -1 || v1_replay(bad, path, 0)) fail("coordinate bounds", 0);
    bad = (v1_coord){0, 729};
    if (v2_solve(bad, path) != -1 || v1_replay(bad, path, 0)) fail("coordinate bounds", 1);
    bad = (v1_coord){0, 0};
    if (v2_solve(bad, NULL) != -1 || v1_replay(bad, path, 12)) fail("path bounds", 0);
    v2_pattern null_view = {NULL, NULL, NULL};
    if (v2_solve_with(NULL, bad, path) != -1 ||
        v2_solve_with(&null_view, bad, path) != -1) fail("pattern arguments", 0);
    path[0] = 9;
    if (v1_replay(bad, path, 1)) fail("invalid move accepted", 0);
    printf("{\n  \"mode\": \"check\", \"status\": \"PASS\",\n"
           "  \"oracle_states\": %u, \"oracle_diameter\": 11,\n"
           "  \"H1_states\": %u, \"parser_states\": %u,\n"
           "  \"H2\": \"PASS\", \"H4\": \"PASS\",\n"
           "  \"permutation_pdb_max\": %u, \"mixed_pdb_max\": %u,\n"
           "  \"abstract_states\": %u, \"mixed_pdb_zero_count\": %u,\n"
           "  \"H4_odd_entries\": %u, \"H4_even_entries\": %u, \"padding_rows\": %u,\n"
           "  \"heuristic_dominates_v1\": true, \"strictly_improved_states\": %u,\n"
           "  \"table_bytes\": %zu, \"workspace_bytes\": %zu,\n"
           "  \"oracle_seconds\": %.6f, \"check_seconds\": %.6f\n}\n",
           STATES, STATES, STATES, mp, maximum, V2_ABSTRACT_STATES, zeros,
           odd, even, V2_PLACEMENTS, improved, v2_table_bytes(),
           v2_workspace_bytes(), oracle_seconds, now() - begin);
    free(raw);
}

int main(int argc, char **argv)
{
    if (argc < 2 || (strcmp(argv[1], "--check") &&
                    strcmp(argv[1], "--hardest") && strcmp(argv[1], "--all"))) {
        fputs("usage: verify-v2 --check | --hardest [CSV] | --all [START COUNT]\n", stderr);
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
        total += v2_last_stats.generated;
        if (v2_last_stats.generated > maximum) {
            maximum = v2_last_stats.generated;
            worst_rank = rank;
        }
        if (v2_last_stats.expanded > max_expanded)
            max_expanded = v2_last_stats.expanded;
        if (csv) {
            char input[15];
            state_string(rank, input);
            fprintf(csv, "%u,%s,%d,%u,%u,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",",
                    rank, input, n, v2_last_stats.initial_bound,
                    v2_last_stats.iterations, v2_last_stats.generated,
                    v2_last_stats.expanded, v2_last_stats.pruned);
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
           max_expanded, worst, v2_last_stats.generated, v2_last_stats.expanded,
           oracle_seconds, search_seconds);
    free(distance);
    return fflush(stdout) != 0 || ferror(stdout);
}
