"""
Abstract base for code generation backends.

Every backend converts a typed Project IR into C source code. The base class
provides the tree-walking skeleton; subclasses override the target-specific
parts (headers, print function, main wrapper, etc.).

To add a new backend (e.g., Arduino):
  1. Create a new file in scratch2c/codegen/
  2. Subclass CodegenBackend
  3. Override the abstract methods
  4. Register it in __init__.py

That's it — the tree walker and expression emitter are shared.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from ..ir import (
    BinaryOp, CallExpr, ChangeVariable, Expression, Forever, HatBlock,
    HatKind, IfThen, IfThenElse, Literal, Procedure, ProcedureCall,
    ProcedureCallExpr, Project, Repeat, RepeatUntil, Say, ScratchType,
    Script, SetVariable, Statement, Stop, UnaryOp, Variable, VariableRef,
    Wait, WaitUntil,
)


class CodegenBackend(ABC):
    """Base class for C code generation backends.

    Subclasses must implement the abstract methods that define target-specific
    behavior (what headers to include, how to print, how to wrap main, etc.).
    The tree walker and expression emitter are provided here.
    """

    def __init__(self) -> None:
        self._indent: int = 0
        self._lines: list[str] = []
        self._loop_counter: int = 0  # unique suffix for loop variables

    # -------------------------------------------------------------------
    # Abstract interface — each backend must implement these
    # -------------------------------------------------------------------

    @abstractmethod
    def file_header(self) -> list[str]:
        """Return the lines that go at the top of the file (includes, etc.)."""
        ...

    @abstractmethod
    def file_footer(self) -> list[str]:
        """Return the lines that go at the bottom of the file."""
        ...

    @abstractmethod
    def emit_say(self, expr_code: str, is_string: bool) -> str:
        """Return a C statement that outputs a value (printf, printk, etc.).

        Args:
            expr_code: The C expression to print.
            is_string: True if expr_code evaluates to a char*/string,
                       False if it evaluates to a long/integer.
        """
        ...

    @abstractmethod
    def main_function_name(self) -> str:
        """Return the name of the entry function (main, module_init, etc.)."""
        ...

    @abstractmethod
    def main_signature_open(self) -> str:
        """Return the opening of the main function including the brace."""
        ...

    @abstractmethod
    def main_signature_close(self) -> str:
        """Return the closing of the main function (return + brace)."""
        ...

    @abstractmethod
    def exit_function_name(self) -> str:
        """Return the name of the exit function (for kernel modules)."""
        ...

    @abstractmethod
    def exit_signature_open(self) -> str:
        """Return the opening of the exit function."""
        ...

    @abstractmethod
    def exit_signature_close(self) -> str:
        """Return the closing of the exit function."""
        ...

    @abstractmethod
    def declare_long_variable(self, c_name: str, initial: str) -> str:
        """Return a declaration for a long variable."""
        ...

    @abstractmethod
    def declare_string_variable(self, c_name: str, initial: str) -> str:
        """Return a declaration for a string variable."""
        ...

    @abstractmethod
    def wait_comment(self, duration_code: str) -> str:
        """Return a comment for a wait block (no-op in most targets)."""
        ...

    def emit_stop(self) -> str:
        """Return the C statement for 'stop this script'.

        Default is 'return;' which works in void functions (procedures).
        Backends override this if main returns int (kernel init returns 0).
        """
        return "return;"

    # -------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------

    def generate(self, project: Project) -> str:
        """Generate C source code from a typed Project IR.

        Args:
            project: A Project with type inference already run.

        Returns:
            A complete C source file as a string.
        """
        self._indent = 0
        self._lines = []
        self._loop_counter = 0

        # File header
        self._lines.extend(self.file_header())
        self._emit("")

        # Global variable declarations
        all_vars = project.all_variables()
        if all_vars:
            self._emit("/* --- Variables --- */")
            for var in all_vars.values():
                c_name = _c_varname(var.name)
                if var.inferred_type == ScratchType.STRING:
                    self._emit(self.declare_string_variable(c_name, var.initial_value))
                else:
                    init_val = var.initial_value
                    try:
                        int(init_val)
                    except ValueError:
                        init_val = "0"
                    self._emit(self.declare_long_variable(c_name, init_val))
            self._emit("")

        # Forward declarations for procedures
        all_procs = project.all_procedures()
        if all_procs:
            self._emit("/* --- Forward declarations --- */")
            for proc in all_procs.values():
                sig = self._proc_signature(proc)
                self._emit(f"{sig};")
            self._emit("")

        # Procedure definitions
        for proc in all_procs.values():
            self._emit_procedure(proc, all_vars)

        # Scripts grouped by hat kind
        init_scripts: list[Script] = []
        exit_scripts: list[Script] = []
        other_scripts: list[Script] = []

        for sprite in project.sprites:
            for script in sprite.scripts:
                if script.hat.kind in (HatKind.FLAG_CLICKED, HatKind.BROADCAST_INIT):
                    init_scripts.append(script)
                elif script.hat.kind == HatKind.BROADCAST_EXIT:
                    exit_scripts.append(script)
                else:
                    other_scripts.append(script)

        # Emit "other" broadcast handlers as standalone functions
        for script in other_scripts:
            bname = script.hat.broadcast_name or "handler"
            func_name = _c_varname(bname)
            self._emit(f"void {func_name}(void) {{")
            self._indent += 1
            self._emit_body(script.body, all_vars)
            self._indent -= 1
            self._emit("}")
            self._emit("")

        # Main / init function
        self._emit(self.main_signature_open())
        self._indent += 1
        for script in init_scripts:
            self._emit_body(script.body, all_vars)
        self._emit(self.main_signature_close())
        self._indent -= 1
        self._emit("}")
        self._emit("")

        # Exit function (only emitted if there are exit scripts or backend needs it)
        if exit_scripts or self._needs_exit():
            self._emit(self.exit_signature_open())
            self._indent += 1
            for script in exit_scripts:
                self._emit_body(script.body, all_vars)
            close = self.exit_signature_close()
            if close:
                self._emit(close)
            self._indent -= 1
            self._emit("}")
            self._emit("")

        # File footer
        self._lines.extend(self.file_footer())

        return "\n".join(self._lines) + "\n"

    def _needs_exit(self) -> bool:
        """Override in backends that always need an exit function (kernel)."""
        return False

    # -------------------------------------------------------------------
    # Statement emission
    # -------------------------------------------------------------------

    def _emit_body(self, stmts: list[Statement], variables: dict[str, Variable]) -> None:
        """Emit a sequence of statements."""
        for stmt in stmts:
            self._emit_statement(stmt, variables)

    def _emit_statement(self, stmt: Statement, variables: dict[str, Variable]) -> None:
        """Dispatch a statement to the appropriate emitter."""
        if isinstance(stmt, SetVariable):
            c_name = _c_varname(stmt.var_name)
            var = variables.get(stmt.var_id)
            if var and var.inferred_type == ScratchType.STRING:
                val_code = self._emit_expr_as_string(stmt.value, variables)
                self._emit(f'snprintf({c_name}, sizeof({c_name}), "%s", {val_code});')
            else:
                val_code = self._emit_expr_as_long(stmt.value, variables)
                self._emit(f"{c_name} = {val_code};")

        elif isinstance(stmt, ChangeVariable):
            c_name = _c_varname(stmt.var_name)
            delta_code = self._emit_expr_as_long(stmt.delta, variables)
            self._emit(f"{c_name} += {delta_code};")

        elif isinstance(stmt, Say):
            msg_type = _expr_type(stmt.message, variables)
            if msg_type == ScratchType.STRING:
                val_code = self._emit_expr_as_string(stmt.message, variables)
                self._emit(self.emit_say(val_code, is_string=True))
            else:
                val_code = self._emit_expr_as_long(stmt.message, variables)
                self._emit(self.emit_say(val_code, is_string=False))
            if stmt.duration is not None:
                dur = self._emit_expr_as_long(stmt.duration, variables)
                self._emit(f"/* sayforsecs: duration {dur}s ignored in C */")

        elif isinstance(stmt, Repeat):
            count_code = self._emit_expr_as_long(stmt.count, variables)
            ivar = f"_i{self._loop_counter}"
            self._loop_counter += 1
            self._emit(f"for (long {ivar} = 0; {ivar} < {count_code}; {ivar}++) {{")
            self._indent += 1
            self._emit_body(stmt.body, variables)
            self._indent -= 1
            self._emit("}")

        elif isinstance(stmt, Forever):
            self._emit("while (1) {")
            self._indent += 1
            self._emit_body(stmt.body, variables)
            self._indent -= 1
            self._emit("}")

        elif isinstance(stmt, RepeatUntil):
            cond_code = self._emit_expr_as_long(stmt.condition, variables)
            self._emit(f"while (!({cond_code})) {{")
            self._indent += 1
            self._emit_body(stmt.body, variables)
            self._indent -= 1
            self._emit("}")

        elif isinstance(stmt, WaitUntil):
            cond_code = self._emit_expr_as_long(stmt.condition, variables)
            self._emit("/* WARNING: spin-wait — burns CPU until condition is true */")
            self._emit(f"while (!({cond_code})) {{ /* spin */ }}")

        elif isinstance(stmt, IfThen):
            cond_code = self._emit_expr_as_long(stmt.condition, variables)
            self._emit(f"if ({cond_code}) {{")
            self._indent += 1
            self._emit_body(stmt.then_body, variables)
            self._indent -= 1
            self._emit("}")

        elif isinstance(stmt, IfThenElse):
            cond_code = self._emit_expr_as_long(stmt.condition, variables)
            self._emit(f"if ({cond_code}) {{")
            self._indent += 1
            self._emit_body(stmt.then_body, variables)
            self._indent -= 1
            self._emit("} else {")
            self._indent += 1
            self._emit_body(stmt.else_body, variables)
            self._indent -= 1
            self._emit("}")

        elif isinstance(stmt, Stop):
            self._emit(self.emit_stop())

        elif isinstance(stmt, Wait):
            dur_code = self._emit_expr_as_long(stmt.duration, variables)
            self._emit(self.wait_comment(dur_code))

        elif isinstance(stmt, ProcedureCall):
            args_code = ", ".join(
                self._emit_expr_as_long(a, variables) for a in stmt.args
            )
            self._emit(f"{stmt.proc_name}({args_code});")

    # -------------------------------------------------------------------
    # Expression emission
    # -------------------------------------------------------------------

    def _emit_expr_as_long(self, expr: Expression, variables: dict[str, Variable]) -> str:
        """Emit an expression in a numeric context, casting if needed."""
        if isinstance(expr, Literal):
            try:
                return str(int(expr.value))
            except ValueError:
                try:
                    return str(int(float(expr.value)))
                except ValueError:
                    # String literal used in numeric context — atol
                    return f'atol("{_escape_c(expr.value)}")'

        if isinstance(expr, VariableRef):
            c_name = _c_varname(expr.var_name)
            var = variables.get(expr.var_id)
            if var and var.inferred_type == ScratchType.STRING:
                return f"atol({c_name})"
            return c_name

        if isinstance(expr, BinaryOp):
            left = self._emit_expr_as_long(expr.left, variables)
            right = self._emit_expr_as_long(expr.right, variables)
            if expr.operator == "/":
                return f"(({right}) != 0 ? ({left}) / ({right}) : 0)"
            if expr.operator == "%":
                return f"(({right}) != 0 ? ({left}) % ({right}) : 0)"
            return f"(({left}) {expr.operator} ({right}))"

        if isinstance(expr, UnaryOp):
            operand = self._emit_expr_as_long(expr.operand, variables)
            return f"({expr.operator}({operand}))"

        if isinstance(expr, CallExpr):
            if expr.func in ("scratch_join", "scratch_letter_of"):
                # String-returning function used in numeric context
                inner = self._emit_call(expr, variables)
                return f"atol({inner})"
            if expr.func == "scratch_strlen":
                args = ", ".join(
                    self._emit_expr_as_string(a, variables) for a in expr.args
                )
                return f"scratch_strlen({args})"
            return self._emit_call(expr, variables)

        if isinstance(expr, ProcedureCallExpr):
            args = ", ".join(self._emit_expr_as_long(a, variables) for a in expr.args)
            return f"{expr.proc_name}({args})"

        return "0"

    def _emit_expr_as_string(self, expr: Expression, variables: dict[str, Variable]) -> str:
        """Emit an expression in a string context, converting if needed."""
        if isinstance(expr, Literal):
            try:
                float(expr.value)
                # Numeric literal used as string — wrap in ltoa
                return f'scratch_ltoa({int(float(expr.value))})'
            except ValueError:
                return f'"{_escape_c(expr.value)}"'

        if isinstance(expr, VariableRef):
            c_name = _c_varname(expr.var_name)
            var = variables.get(expr.var_id)
            if var and var.inferred_type == ScratchType.STRING:
                return c_name
            return f"scratch_ltoa({c_name})"

        if isinstance(expr, CallExpr):
            return self._emit_call(expr, variables)

        if isinstance(expr, BinaryOp):
            # Numeric result used as string
            numeric = self._emit_expr_as_long(expr, variables)
            return f"scratch_ltoa({numeric})"

        if isinstance(expr, UnaryOp):
            numeric = self._emit_expr_as_long(expr, variables)
            return f"scratch_ltoa({numeric})"

        # Fallback
        return f'scratch_ltoa({self._emit_expr_as_long(expr, variables)})'

    def _emit_call(self, expr: CallExpr, variables: dict[str, Variable]) -> str:
        """Emit a built-in function call."""
        if expr.func == "scratch_join":
            args = ", ".join(
                self._emit_expr_as_string(a, variables) for a in expr.args
            )
            return f"scratch_join({args})"
        if expr.func == "scratch_strlen":
            args = ", ".join(
                self._emit_expr_as_string(a, variables) for a in expr.args
            )
            return f"scratch_strlen({args})"
        if expr.func == "scratch_letter_of":
            idx = self._emit_expr_as_long(expr.args[0], variables) if expr.args else "0"
            s = self._emit_expr_as_string(expr.args[1], variables) if len(expr.args) > 1 else '""'
            return f"scratch_letter_of({idx}, {s})"

        # Generic fallback
        args = ", ".join(self._emit_expr_as_long(a, variables) for a in expr.args)
        return f"{expr.func}({args})"

    # -------------------------------------------------------------------
    # Procedure helpers
    # -------------------------------------------------------------------

    def _proc_signature(self, proc: Procedure) -> str:
        """Build a C function signature for a procedure."""
        params = ", ".join(f"long {_c_varname(p)}" for p in proc.param_names)
        if not params:
            params = "void"
        return f"void {proc.name}({params})"

    def _emit_procedure(self, proc: Procedure, variables: dict[str, Variable]) -> None:
        """Emit a complete procedure definition."""
        sig = self._proc_signature(proc)
        self._emit(f"{sig} {{")
        self._indent += 1
        # Build a temporary variables dict that includes parameters as LONG
        proc_vars = dict(variables)
        for pid, pname in zip(proc.param_ids, proc.param_names):
            proc_vars[f"__arg_{pname}"] = Variable(
                var_id=f"__arg_{pname}", name=pname, inferred_type=ScratchType.LONG
            )
        self._emit_body(proc.body, proc_vars)
        self._indent -= 1
        self._emit("}")
        self._emit("")

    # -------------------------------------------------------------------
    # Output helpers
    # -------------------------------------------------------------------

    def _emit(self, line: str) -> None:
        """Append an indented line to the output."""
        if line == "":
            self._lines.append("")
        else:
            prefix = "    " * self._indent
            self._lines.append(f"{prefix}{line}")


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _c_varname(name: str) -> str:
    """Convert a Scratch variable name to a valid C identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = "var_" + cleaned
    # Avoid C keywords
    c_keywords = {"int", "long", "char", "return", "if", "else", "while", "for",
                  "do", "break", "continue", "void", "static", "const", "main"}
    if cleaned in c_keywords:
        cleaned = "s_" + cleaned
    return cleaned


def _escape_c(s: str) -> str:
    """Escape a string for inclusion in a C string literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _expr_type(expr: Expression, variables: dict[str, Variable]) -> ScratchType:
    """Determine the type of an expression (quick heuristic for say dispatch)."""
    if isinstance(expr, Literal):
        try:
            float(expr.value)
            return ScratchType.LONG
        except ValueError:
            return ScratchType.STRING

    if isinstance(expr, VariableRef):
        var = variables.get(expr.var_id)
        if var:
            return var.inferred_type
        return ScratchType.LONG

    if isinstance(expr, BinaryOp):
        return ScratchType.LONG

    if isinstance(expr, UnaryOp):
        return ScratchType.LONG

    if isinstance(expr, CallExpr):
        if expr.func in ("scratch_join", "scratch_letter_of"):
            return ScratchType.STRING
        if expr.func == "scratch_strlen":
            return ScratchType.LONG
        return ScratchType.UNKNOWN

    return ScratchType.UNKNOWN
