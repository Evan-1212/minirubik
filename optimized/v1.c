#include "v1.h"

/* The cursor keeps a face's three siblings in sequence. Thus R, R2, R'
 * together use three quarter-turn table advances, not 1+2+3 advances.
 */
typedef struct {
    uint16_t p, o, cursor_p, cursor_o;
    uint8_t face, turn, previous_face;
} frame;
static frame frames[V1_MAX_DEPTH + 1];

#ifdef V1_STATS
v1_stats v1_last_stats;
#define COUNT(field) (++v1_last_stats.field)
#else
#define COUNT(field) ((void)0)
#endif

static unsigned smaller_after(const uint8_t p[7], unsigned i)
{
    unsigned n = 0;
    for (unsigned j = i + 1; j < 7; ++j)
        n += p[j] < p[i];
    return n;
}

int v1_parse(const char *input, v1_coord *out)
{
    uint8_t p[7];
    unsigned seen = 0, sum = 0, o = 0, rank;
    if (!input || !out)
        return 0;
    /* Reject at the first NUL, before reading any later position. */
    for (unsigned i = 0; i < 7; ++i) {
        unsigned digit = (unsigned)(unsigned char)input[i] - '1';
        if (digit >= 7 || (seen & (1U << digit)))
            return 0;
        p[i] = (uint8_t)digit;
        seen |= 1U << digit;
    }
    for (unsigned i = 0; i < 7; ++i) {
        unsigned digit = (unsigned)(unsigned char)input[7 + i] - '1';
        if (digit >= 3)
            return 0;
        sum += digit;
        if (i < 6)
            o = (o << 1) + o + digit;
    }
    if (input[14] != '\0')
        return 0;
    while (sum >= 3)
        sum -= 3;
    if (sum != 0)
        return 0;

    /* Fixed mixed radices: no variable multiply/divide helper is needed. */
    rank = smaller_after(p, 0);
    rank = (rank << 2) + (rank << 1) + smaller_after(p, 1); /* x6 */
    rank = (rank << 2) + rank + smaller_after(p, 2);       /* x5 */
    rank = (rank << 2) + smaller_after(p, 3);              /* x4 */
    rank = (rank << 1) + rank + smaller_after(p, 4);       /* x3 */
    rank = (rank << 1) + smaller_after(p, 5);              /* x2 */
    out->p = (uint16_t)rank;
    out->o = (uint16_t)o;
    return 1;
}

unsigned v1_heuristic(v1_coord s)
{
    unsigned hp = v1_perm_dist[s.p], ho = v1_ori_dist[s.o];
    return hp > ho ? hp : ho;
}

static void enter(unsigned depth, v1_coord s, unsigned previous_face)
{
    frame *f = &frames[depth];
    f->p = f->cursor_p = s.p;
    f->o = f->cursor_o = s.o;
    f->face = f->turn = 0;
    f->previous_face = (uint8_t)previous_face;
    COUNT(expanded);
}

int v1_solve(v1_coord start, uint8_t path[V1_MAX_DEPTH])
{
    unsigned first_bound;
#ifdef V1_STATS
    v1_last_stats = (v1_stats){0};
#endif
    if (!path || start.p >= V1_PERMS || start.o >= V1_ORIS)
        return -1;
    first_bound = v1_heuristic(start);
#ifdef V1_STATS
    v1_last_stats.initial_bound = first_bound;
#endif
    if (start.p == 0 && start.o == 0)
        return 0;

    /* Integer thresholds keep this first version simple. Admissibility
     * ensures that a shortest solution survives the threshold d(start).
     */
    for (unsigned bound = first_bound; bound <= V1_MAX_DEPTH; ++bound) {
        unsigned depth = 0;
#ifdef V1_STATS
        ++v1_last_stats.iterations;
        v1_last_stats.final_bound = bound;
#endif
        enter(0, start, 3); /* 3 means no previous face at the root. */
        for (;;) {
            frame *f = &frames[depth];
            if (f->face == 3) {
                if (depth == 0)
                    break;
                --depth;
                continue;
            }
            if (f->face == f->previous_face || f->turn == 3) {
                ++f->face;
                f->turn = 0;
                f->cursor_p = f->p;
                f->cursor_o = f->o;
                continue;
            }
            f->cursor_p = v1_perm_next[f->face][f->cursor_p];
            f->cursor_o = v1_ori_next[f->face][f->cursor_o];
            unsigned move = (f->face << 1) + f->face + f->turn;
            ++f->turn; /* Saved before descent, so backtracking resumes. */
            COUNT(generated);
            v1_coord next = {f->cursor_p, f->cursor_o};
            unsigned child_depth = depth + 1;
            if (child_depth > bound ||
                v1_heuristic(next) > bound - child_depth) {
                COUNT(pruned);
                continue;
            }
            path[depth] = (uint8_t)move;
            if (next.p == 0 && next.o == 0)
                return (int)child_depth;
            if (child_depth < bound) {
                unsigned previous_face = f->face;
                depth = child_depth;
                enter(depth, next, previous_face);
            }
        }
    }
    return -1;
}

int v1_replay(v1_coord start, const uint8_t *path, unsigned length)
{
    if (!path || length > V1_MAX_DEPTH ||
        start.p >= V1_PERMS || start.o >= V1_ORIS)
        return 0;
    for (unsigned i = 0; i < length; ++i) {
        unsigned move = path[i], face, turns;
        if (move >= 9)
            return 0;
        /* Explicit ranges avoid /3 and %3 even in the validation path. */
        if (move < 3) { face = 0; turns = move + 1; }
        else if (move < 6) { face = 1; turns = move - 2; }
        else { face = 2; turns = move - 5; }
        for (unsigned t = 0; t < turns; ++t) {
            start.p = v1_perm_next[face][start.p];
            start.o = v1_ori_next[face][start.o];
        }
    }
    return start.p == 0 && start.o == 0;
}

size_t v1_table_bytes(void)
{
    return sizeof v1_perm_next + sizeof v1_ori_next +
           sizeof v1_perm_dist + sizeof v1_ori_dist;
}

size_t v1_workspace_bytes(void) { return sizeof frames; }
