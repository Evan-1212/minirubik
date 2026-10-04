#ifndef MINIRUBIK_V1_H
#define MINIRUBIK_V1_H

#include <stddef.h>
#include <stdint.h>

enum { V1_PERMS = 5040, V1_ORIS = 729, V1_MAX_DEPTH = 11 };
typedef struct { uint16_t p, o; } v1_coord;

/* These four arrays are generated on the HOST, never built by the solver. */
extern const uint16_t v1_perm_next[3][V1_PERMS];
extern const uint16_t v1_ori_next[3][V1_ORIS];
extern const uint8_t v1_perm_dist[V1_PERMS];
extern const uint8_t v1_ori_dist[V1_ORIS];

int v1_parse(const char *input, v1_coord *out);
unsigned v1_heuristic(v1_coord s);
/* Returns length 0..11, or -1 for invalid coordinates / internal failure.
 * path must have at least V1_MAX_DEPTH bytes. Search uses static workspace:
 * it is not reentrant. No heap, recursion, floating point, or runtime tables.
 */
int v1_solve(v1_coord start, uint8_t path[V1_MAX_DEPTH]);
int v1_replay(v1_coord start, const uint8_t *path, unsigned length);
size_t v1_table_bytes(void);
size_t v1_workspace_bytes(void);

/* Host diagnostic build ONLY. Omitted entirely unless V1_STATS is defined. */
#ifdef V1_STATS
typedef struct {
    uint64_t generated, expanded, pruned;
    unsigned iterations, initial_bound, final_bound;
} v1_stats;
extern v1_stats v1_last_stats;
#endif
#endif
