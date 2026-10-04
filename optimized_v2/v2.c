#include "v2.h"

typedef struct {
    uint16_t p, o, cursor_p, cursor_o;
    uint8_t face, turn, previous_face;
} frame;
static frame frames[V1_MAX_DEPTH + 1];

#ifdef V2_STATS
v2_stats v2_last_stats;
#define COUNT(field) (++v2_last_stats.field)
#else
#define COUNT(field) ((void)0)
#endif

unsigned v2_pattern_distance(const v2_pattern *pdb, v1_coord s)
{
    unsigned q = pdb->projection[s.p];
    unsigned offset = pdb->row_offset[q] + (s.o >> 1);
    unsigned shift = (s.o & 1U) << 2;
    COUNT(pattern_lookups);
    return (pdb->packed[offset] >> shift) & 15U;
}

unsigned v2_heuristic_with(const v2_pattern *pdb, v1_coord s)
{
    COUNT(permutation_lookups);
    unsigned hp = v1_perm_dist[s.p];
    unsigned hm = v2_pattern_distance(pdb, s);
    return hp > hm ? hp : hm;
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

int v2_solve_with(const v2_pattern *pdb, v1_coord start, uint8_t path[11])
{
#ifdef V2_STATS
    v2_last_stats = (v2_stats){0};
#endif
    if (!pdb || !pdb->projection || !pdb->row_offset || !pdb->packed ||
        !path || start.p >= V1_PERMS || start.o >= V1_ORIS)
        return -1;
    unsigned first_bound = v2_heuristic_with(pdb, start);
#ifdef V2_STATS
    v2_last_stats.initial_bound = first_bound;
#endif
    if (start.p == 0 && start.o == 0) return 0;
    for (unsigned bound = first_bound; bound <= V1_MAX_DEPTH; ++bound) {
        unsigned depth = 0;
#ifdef V2_STATS
        ++v2_last_stats.iterations;
        v2_last_stats.final_bound = bound;
#endif
        enter(0, start, 3);
        for (;;) {
            frame *f = &frames[depth];
            if (f->face == 3) {
                if (depth == 0) break;
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
            ++f->turn;
            COUNT(generated);
            v1_coord next = {f->cursor_p, f->cursor_o};
            unsigned child_depth = depth + 1;
            if (child_depth > bound) {
                COUNT(pruned);
                continue;
            }
            unsigned remaining = bound - child_depth;
            /* Short-circuit max(hp, hm) > remaining. If hp already fails,
             * do not pay for projection, row lookup, or nibble unpacking.
             */
            COUNT(permutation_lookups);
            if (v1_perm_dist[next.p] > remaining ||
                v2_pattern_distance(pdb, next) > remaining) {
                COUNT(pruned);
                continue;
            }
            path[depth] = (uint8_t)move;
            if (next.p == 0 && next.o == 0) return (int)child_depth;
            if (child_depth < bound) {
                unsigned previous_face = f->face;
                depth = child_depth;
                enter(depth, next, previous_face);
            }
        }
    }
    return -1;
}

#ifndef V2_RUNTIME_TABLES_ONLY
unsigned v2_heuristic(v1_coord s)
{
    return v2_heuristic_with(&v2_default_pattern, s);
}
int v2_solve(v1_coord start, uint8_t path[11])
{
    return v2_solve_with(&v2_default_pattern, start, path);
}
#endif

size_t v2_table_bytes(void)
{
    /* Live table payload; excludes the view's pointers and alignment.
     * Linker GC removes the unused v1 orientation-only PDB/search frames.
     */
    return sizeof v1_perm_next + sizeof v1_ori_next + sizeof v1_perm_dist +
           sizeof v2_projection + sizeof v2_row_offset + sizeof v2_packed;
}
size_t v2_workspace_bytes(void) { return sizeof frames; }
