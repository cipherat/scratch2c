# scratch2c Makefile
#
# Transpile:        make userspace SB3=projects/fibonacci.sb3
# Transpile + CC:   make compile-userspace SB3=projects/fibonacci.sb3
# Kernel module:    make kbuild SB3=projects/fibonacci.sb3
#
# SB3 can also point at a raw project.json.

SB3       ?= projects/fibonacci.sb3
STEM      := $(basename $(notdir $(SB3)))
OUT_DIR   := build
CC        := cc
CFLAGS    := -Wall -Wextra -O2
RUNTIME   := runtime/scratch_runtime.h

.PHONY: test lint clean sync example-fib \
        userspace kernel compile-userspace compile-kernel kbuild

# ---------- project management ----------

sync:
	uv sync

test:
	uv run pytest tests/ -v

coverage:
	uv run pytest tests/ --cov=scratch2c --cov-report=term-missing

lint:
	uv run mypy scratch2c/

clean:
	rm -rf $(OUT_DIR) __pycache__ scratch2c/__pycache__ tests/__pycache__
	rm -rf .pytest_cache .mypy_cache *.egg-info
	find . -name "*.pyc" -delete
	find . -name "*.ko" -o -name "*.mod" -o -name "*.mod.c" \
	     -o -name "*.mod.o" -o -name "*.order" -o -name "*.symvers" \
	     -o -name ".tmp_versions" | xargs rm -rf 2>/dev/null || true

# ---------- transpile ----------

$(OUT_DIR):
	mkdir -p $(OUT_DIR)

userspace: $(OUT_DIR)
	uv run scratch2c $(SB3) -o $(OUT_DIR)/$(STEM).c --backend userspace
	cp $(RUNTIME) $(OUT_DIR)/
	@echo ""
	@echo "Compile with:  $(CC) $(CFLAGS) -o $(OUT_DIR)/$(STEM) $(OUT_DIR)/$(STEM).c"

kernel: $(OUT_DIR)
	uv run scratch2c $(SB3) -o $(OUT_DIR)/$(STEM).c --backend kernel
	cp $(RUNTIME) $(OUT_DIR)/
	@echo ""
	@echo "Build with:  make kbuild SB3=$(SB3)"

# ---------- compile ----------

# Userspace: transpile then cc
compile-userspace: userspace
	$(CC) $(CFLAGS) -o $(OUT_DIR)/$(STEM) $(OUT_DIR)/$(STEM).c
	@echo ""
	@echo "Run:  ./$(OUT_DIR)/$(STEM)"

# Kernel module: transpile then kbuild (needs linux-headers)
#   Arch:   sudo pacman -S linux-lts-headers
#   Debian: sudo apt install linux-headers-$(uname -r)
compile-kernel: kernel
	@echo "obj-m += $(STEM).o" > $(OUT_DIR)/Kbuild
	$(MAKE) -C /lib/modules/$$(uname -r)/build M=$(abspath $(OUT_DIR)) modules
	@echo ""
	@echo "Load:    sudo insmod $(OUT_DIR)/$(STEM).ko"
	@echo "Unload:  sudo rmmod $(STEM)"
	@echo "Output:  dmesg | tail"

# Alias
kbuild: compile-kernel

# ---------- examples ----------

example-fib:
	@echo "=== Userspace ==="
	uv run scratch2c tests/fixtures/fibonacci.json --backend userspace
	@echo ""
	@echo "=== Kernel Module ==="
	uv run scratch2c tests/fixtures/fibonacci.json --backend kernel
