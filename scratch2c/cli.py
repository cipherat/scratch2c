"""
scratch2c command-line interface.

Usage:
    python -m scratch2c input.sb3 -o output.c --backend userspace
    python -m scratch2c input.sb3 --backend kernel
"""

from __future__ import annotations

import argparse
import sys

from .reader import read_sb3
from .ir_builder import build_ir
from .type_inference import infer_types
from .codegen import get_backend


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the scratch2c CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        prog="scratch2c",
        description="Convert Scratch 3 (.sb3) projects to compilable C code.",
    )
    parser.add_argument(
        "input",
        help="Path to .sb3 file or raw project.json",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "-b", "--backend",
        default="userspace",
        choices=["userspace", "kernel"],
        help="Code generation target (default: userspace)",
    )
    parser.add_argument(
        "--dump-ir",
        action="store_true",
        help="Dump the IR to stderr instead of generating code (for debugging)",
    )

    args = parser.parse_args(argv)

    try:
        # Stage 1: Read the .sb3 / JSON file
        project_json = read_sb3(args.input)

        # Stage 2: Build the IR
        project = build_ir(project_json)

        # Stage 3: Run type inference
        infer_types(project)

        # Optional: dump IR for debugging
        if args.dump_ir:
            import pprint
            pprint.pprint(project, stream=sys.stderr)
            return 0

        # Stage 4: Generate code
        backend = get_backend(args.backend)
        code = backend.generate(project)

        # Write output
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            print(code, end="")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Internal error: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
