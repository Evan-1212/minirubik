#ifndef MINIRUBIK_HOST_REFERENCE_H
#define MINIRUBIK_HOST_REFERENCE_H
/* Host-only adapter to the pinned, UNMODIFIED baseline. Never link this
 * translation unit into the target: it deliberately includes heap/BFS code.
 */
#define main baseline_cli_main
#include "../solver.c"
#undef main
#endif
