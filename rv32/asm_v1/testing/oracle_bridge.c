/* Supplementary host oracle for testing the NEW assembly, not target code. */
#include "../../../optimized_v2/host_oracle.h"
static uint8_t *exact;
void test_init(void) { if (!exact) exact = oracle(); }
unsigned test_distance(unsigned rank) { return exact[rank]; }
void test_encode(unsigned rank, char out[15]) { state_string(rank, out); }
int test_physical_replay(unsigned rank, const uint8_t *path, unsigned n)
{
    if (n > 11) return 0;
    state_t s;
    unrank_state(rank, &s);
    for (unsigned i = 0; i < n; ++i) {
        if (path[i] >= 9) return 0;
        s = apply_move(s, path[i]);
    }
    return rank_state(&s) == 0;
}
unsigned test_h(unsigned p, unsigned o)
{
    v1_coord s = {(uint16_t)p, (uint16_t)o};
    return v2_heuristic(s);
}
