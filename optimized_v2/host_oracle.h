/* Host-only independent full-state BFS, adapted unchanged from v1 verification. */
#define _POSIX_C_SOURCE 200809L
#include "v2.h"
#include "../optimized/host_reference.h"
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
