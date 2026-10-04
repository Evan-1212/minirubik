CC ?= cc
CPPFLAGS ?=
CFLAGS ?= -O3 -std=c99 -Wall -Wextra -Wpedantic
HOST_FLAGS = $(CFLAGS) -Wno-unused-function
CORE = v1.c v1_tables.c

.PHONY: all check exhaustive hardest sanitize clean
all: build/solver-v1 build/solver-v1-stats

build:
	mkdir -p build

build/generate-tables: generate_tables.c host_reference.h ../solver.c v1.h | build
	$(CC) $(CPPFLAGS) $(HOST_FLAGS) generate_tables.c -o $@

v1_tables.c: build/generate-tables
	./build/generate-tables > $@.tmp
	mv $@.tmp $@

build/solver-v1: $(CORE) cli.c v1.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(CORE) cli.c -o $@

build/solver-v1-stats: $(CORE) cli.c v1.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -DV1_STATS $(CORE) cli.c -o $@

build/verify-v1: $(CORE) verify.c host_reference.h ../solver.c v1.h | build
	$(CC) $(CPPFLAGS) $(HOST_FLAGS) -DV1_STATS $(CORE) verify.c -o $@

check: all build/verify-v1
	./build/solver-v1 --self-test
	python3 test_cli.py
	./build/verify-v1 --check

hardest: build/verify-v1
	./build/verify-v1 --hardest

exhaustive: build/verify-v1
	./build/verify-v1 --all

sanitize: v1_tables.c | build
	$(CC) $(CPPFLAGS) -O1 -g -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-function -DV1_STATS -fsanitize=address,undefined -fno-omit-frame-pointer $(CORE) verify.c -o build/verify-sanitize
	./build/verify-sanitize --check

clean:
	rm -rf build
