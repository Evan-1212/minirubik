#include "../optimized_v2/v2.h"

/* These are linked from a separate assembly object. No LTO is used, so the
   C compiler cannot specialize the search for a known input or answer. */
extern const char cube_input[15];
extern const int expected_length; /* -1 disables the optional known-length check. */

uint8_t result_path[V1_MAX_DEPTH];
int result_length;

int target_main(void)
{
    v1_coord start;
    result_length = -1;
    if (!v1_parse(cube_input, &start)) return 1;
    int length = v2_solve(start, result_path);
    result_length = length;
    if (length < 0 || length > V1_MAX_DEPTH) return 2;
    if (!v1_replay(start, result_path, (unsigned)length)) return 3;
    if (expected_length >= 0 && length != expected_length) return 4;
    return 0;
}
