#include "host_oracle.h"

static double measure(int version, const v1_coord states[2644])
{
    uint8_t path[11];
    double begin = now();
    for (unsigned i = 0; i < 2644; ++i) {
        int n = version == 1 ? v1_solve(states[i], path) : v2_solve(states[i], path);
        if (n != 11) fail("benchmark solution length", i);
    }
    return now() - begin;
}

int main(void)
{
    /* Both solvers are compiled without their statistics macros. BFS, input
     * construction, replay, allocation, and output are outside timed blocks.
     */
    uint8_t *distance = oracle();
    v1_coord states[2644];
    unsigned n = 0;
    for (unsigned rank = 0; rank < STATES; ++rank)
        if (distance[rank] == 11) {
            if (n == 2644) fail("d11 count", n);
            states[n++] = (v1_coord){(uint16_t)(rank / V1_ORIS), (uint16_t)(rank % V1_ORIS)};
        }
    free(distance);
    if (n != 2644) fail("d11 count", n);
    (void)measure(1, states);
    (void)measure(2, states);
    puts("repeat,order,version,states,seconds");
    for (unsigned repeat = 0; repeat < 5; ++repeat) {
        unsigned first = repeat & 1U ? 2 : 1;
        for (unsigned order = 0; order < 2; ++order) {
            unsigned version = order ? 3 - first : first;
            double seconds = measure((int)version, states);
            printf("%u,%u,v%u,2644,%.9f\n", repeat + 1, order + 1, version, seconds);
            if (fflush(stdout)) fail("benchmark output", 0);
        }
    }
    return ferror(stdout) != 0;
}
