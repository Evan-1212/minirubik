/* HOST ONLY: enumerate the exact distance-11 shell using the existing
 * independent cubie-move BFS. No target tables or solver are executed here. */
#include "../../optimized_v2/host_oracle.h"
int main(void)
{
    uint8_t *distance = oracle();
    unsigned count = 0;
    for (unsigned rank = 0; rank < STATES; ++rank) {
        if (distance[rank] == 11) {
            char state[15];
            state_string(rank, state);
            printf("%u,%s\n", rank, state);
            ++count;
        }
    }
    free(distance);
    if (count != 2644) fail("distance-11 count", count);
    return 0;
}
