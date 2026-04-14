# Getting Started

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A C compiler (`gcc`, `clang`, or `cc`)
- Linux kernel headers (only for kernel module targets)

## Install

```bash
git clone https://github.com/scratch2c/scratch2c.git
cd scratch2c
uv sync
```

This creates a `.venv`, installs the project and dev dependencies (pytest, mypy), and locks everything in `uv.lock`.

## First run

Transpile a Scratch project to a userspace C program:

```bash
uv run scratch2c my_project.sb3 -o build/my_project.c --backend userspace
```

Or use the Makefile, which also copies `scratch_runtime.h` into the build directory:

```bash
make compile-userspace SB3=my_project.sb3
./build/my_project
```

## Kernel module

```bash
make kbuild SB3=my_project.sb3
sudo insmod build/my_project.ko
journalctl -rk | head -20
sudo rmmod my_project
```

This requires `linux-headers` for your running kernel. On Arch: `sudo pacman -S linux-lts-headers`. On Debian/Ubuntu: `sudo apt install linux-headers-$(uname -r)`.

## CLI reference

```
scratch2c [-h] [-o OUTPUT] [-b {userspace,kernel}] [--dump-ir] input
```

| Flag | Description |
|------|-------------|
| `input` | Path to `.sb3` file or raw `project.json` |
| `-o` | Output file (default: stdout) |
| `-b` | Backend: `userspace` or `kernel` |
| `--dump-ir` | Print the IR to stderr instead of generating C |

## Makefile targets

| Target | Description |
|--------|-------------|
| `make sync` | Install/update dependencies |
| `make test` | Run the test suite |
| `make compile-userspace SB3=...` | Transpile + compile with `cc` |
| `make kbuild SB3=...` | Transpile + build kernel module |
| `make userspace SB3=...` | Transpile only (no compile) |
| `make kernel SB3=...` | Transpile only (no compile) |
| `make lint` | Type-check with mypy |
| `make clean` | Remove build artifacts |

The `SB3` variable defaults to `projects/fibonacci.sb3`.
