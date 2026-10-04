CC ?= cc
CPPFLAGS ?=
CFLAGS ?= -O3 -std=c99 -Wall -Wextra -Wpedantic
SECTIONS = -ffunction-sections -fdata-sections
GC = -Wl,--gc-sections
HOST_FLAGS = $(CFLAGS) -Wno-unused-function
SHARED = ../optimized/v1.c ../optimized/v1_tables.c
CORE = v2.c v2_tables.c $(SHARED)
HEADERS = v2.h ../optimized/v1.h
HOST_HEADERS = host_oracle.h pattern_build.h ../optimized/host_reference.h ../solver.c

.PHONY: all check exhaustive hardest sweep benchmark sanitize clean
all: build/solver-v2 build/solver-v2-stats

build:
	mkdir -p build

../optimized/v1_tables.c:
	$(MAKE) -C ../optimized v1_tables.c

build/generate-tables: generate_tables.c pattern_build.c $(HOST_HEADERS) $(HEADERS) ../optimized/v1_tables.c | build
	$(CC) $(CPPFLAGS) $(HOST_FLAGS) $(SECTIONS) generate_tables.c pattern_build.c ../optimized/v1_tables.c $(GC) -o $@

v2_tables.c: build/generate-tables pattern.txt
	./build/generate-tables $$(cat pattern.txt) > $@.tmp
	mv $@.tmp $@

build/select-pattern: select_pattern.c pattern_build.c v2.c $(SHARED) $(HOST_HEADERS) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(HOST_FLAGS) $(SECTIONS) -DV2_STATS -DV2_RUNTIME_TABLES_ONLY select_pattern.c pattern_build.c v2.c $(SHARED) $(GC) -o $@

build/solver-v2: $(CORE) cli.c $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(SECTIONS) $(CORE) cli.c $(GC) -o $@

build/solver-v2-stats: $(CORE) cli.c $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(SECTIONS) -DV2_STATS $(CORE) cli.c $(GC) -o $@

build/verify-v2: $(CORE) verify.c pattern_build.c $(HOST_HEADERS) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(HOST_FLAGS) $(SECTIONS) -DV2_STATS $(CORE) verify.c pattern_build.c $(GC) -o $@

build/benchmark: $(CORE) benchmark.c $(HOST_HEADERS) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(HOST_FLAGS) $(SECTIONS) $(CORE) benchmark.c $(GC) -o $@

check: all build/verify-v2
	./build/solver-v2 --self-test
	python3 test_cli.py
	python3 audit_native.py
	./build/verify-v2 --check

hardest: build/verify-v2
	./build/verify-v2 --hardest

exhaustive: build/verify-v2
	./build/verify-v2 --all

sweep: build/select-pattern
	./build/select-pattern build/best-pattern.txt > build/pattern_sweep.csv
	diff -u pattern.txt build/best-pattern.txt

benchmark: build/benchmark
	./build/benchmark

sanitize: v2_tables.c | build
	$(CC) $(CPPFLAGS) -O1 -g -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-function $(SECTIONS) -DV2_STATS -fsanitize=address,undefined -fno-omit-frame-pointer $(CORE) verify.c pattern_build.c $(GC) -o build/verify-sanitize
	ASAN_OPTIONS=detect_leaks=0 ./build/verify-sanitize --check

clean:
	rm -rf build
