#ifndef MINIRUBIK_V2_H
#define MINIRUBIK_V2_H
#include "../optimized/v1.h"

enum {
    V2_PLACEMENTS = 210,
    V2_ABSTRACT_STATES = V2_PLACEMENTS * V1_ORIS,
    V2_ROW_BYTES = (V1_ORIS + 1) / 2,
    V2_PACKED_BYTES = V2_PLACEMENTS * V2_ROW_BYTES
};
typedef struct {
    const uint8_t *projection;
    const uint32_t *row_offset;
    const uint8_t *packed;
} v2_pattern;

extern const uint8_t v2_projection[V1_PERMS];
extern const uint32_t v2_row_offset[V2_PLACEMENTS];
extern const uint8_t v2_packed[V2_PACKED_BYTES];
/* Internal cubie labels 0..6; input/report labels are one greater. */
extern const uint8_t v2_selected_cubies[3];
extern const v2_pattern v2_default_pattern;

/* Valid-coordinate precondition, as for v1_heuristic. */
unsigned v2_pattern_distance(const v2_pattern *pdb, v1_coord s);
unsigned v2_heuristic_with(const v2_pattern *pdb, v1_coord s);
unsigned v2_heuristic(v1_coord s);
int v2_solve_with(const v2_pattern *pdb, v1_coord start, uint8_t path[11]);
int v2_solve(v1_coord start, uint8_t path[11]);
size_t v2_table_bytes(void);
size_t v2_workspace_bytes(void);

#ifdef V2_STATS
typedef struct {
    uint64_t generated, expanded, pruned, permutation_lookups, pattern_lookups;
    unsigned iterations, initial_bound, final_bound;
} v2_stats;
extern v2_stats v2_last_stats;
#endif
#endif
