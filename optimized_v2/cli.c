#include "v2.h"
#include <stdio.h>
#include <string.h>
#ifdef V2_STATS
#include <inttypes.h>
#endif

static const char names[9][3] = {
    "R", "R2", "R'", "B", "B2", "B'", "D", "D2", "D'"
};
static uint8_t path[V1_MAX_DEPTH];

static int self_test(void)
{
    static const char states[3][15] = {
        "12345671111111", "25314672313211", "21345671111111"
    };
    static const unsigned lengths[3] = {0, 1, 11};
    for (unsigned i = 0; i < 3; ++i) {
        v1_coord s;
        if (!v1_parse(states[i], &s))
            return 1;
        int n = v2_solve(s, path);
        if (n != (int)lengths[i] || !v1_replay(s, path, (unsigned)n))
            return 1;
    }
    puts("3 cases passed: solved, one-move scramble, distance-11");
    return fflush(stdout) != 0 || ferror(stdout);
}

int main(int argc, char **argv)
{
    v1_coord s;
    if (argc == 2 && strcmp(argv[1], "--self-test") == 0)
        return self_test();
    if (argc != 2 || !v1_parse(argv[1], &s)) {
        fputs("usage: solver-v2 PPPPPPPOOOOOOO | --self-test\n", stderr);
        return 2;
    }
    int n = v2_solve(s, path);
    if (n < 0 || !v1_replay(s, path, (unsigned)n)) {
        fputs("internal search/path validation failure\n", stderr);
        return 1;
    }
    for (int i = 0; i < n; ++i)
        printf("%s%s", i ? " " : "", names[path[i]]);
    putchar('\n');
#ifdef V2_STATS
    fprintf(stderr,
        "length=%d initial_bound=%u final_bound=%u iterations=%u "
        "generated=%" PRIu64 " expanded=%" PRIu64 " pruned=%" PRIu64 "\n",
        n, v2_last_stats.initial_bound, v2_last_stats.final_bound,
        v2_last_stats.iterations, v2_last_stats.generated,
        v2_last_stats.expanded, v2_last_stats.pruned);
#endif
    return fflush(stdout) != 0 || ferror(stdout);
}
