#ifndef MINIRUBIK_PATTERN_BUILD_H
#define MINIRUBIK_PATTERN_BUILD_H
#include "v2.h"

/* Host-only buffers. No object of this type belongs in the target. */
typedef struct {
    uint8_t cubies[3], projection[V1_PERMS];
    uint8_t positions[V2_PLACEMENTS][3];
    uint8_t next[3][V2_PLACEMENTS];
    uint32_t row_offset[V2_PLACEMENTS];
    uint8_t distance[V2_ABSTRACT_STATES], packed[V2_PACKED_BYTES];
    unsigned goal_q, maximum;
    v2_pattern view;
} host_pattern;

int host_build_pattern(host_pattern *pdb, const uint8_t cubies[3]);
int host_emit_pattern(const host_pattern *pdb);
#endif
