"""
scratch2c intermediate representation.

Every Scratch project passes through this IR between parsing and code generation.
The IR is deliberately simpler than Scratch's JSON graph — it flattens the
block-linked-list structure into statement sequences and expression trees,
which map naturally to C's control flow.

Design rule: the IR knows nothing about C, printf, or printk. It is a
target-agnostic description of what the Scratch program *means*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Union


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ScratchType(Enum):
    """Inferred C type for a Scratch variable.

    Scratch variables are dynamically typed (number or string). We resolve
    them statically by inspecting how they are used. UNKNOWN means the type
    inference pass hasn't run yet or couldn't determine the type.
    """
    UNKNOWN = auto()
    LONG = auto()
    STRING = auto()


# ---------------------------------------------------------------------------
# Expressions (reporters)
# ---------------------------------------------------------------------------

@dataclass
class Literal:
    """A constant value embedded in the block graph."""
    value: str  # always stored as string; backends cast as needed

@dataclass
class VariableRef:
    """A read of a variable by its Scratch ID."""
    var_id: str
    var_name: str

@dataclass
class BinaryOp:
    """An infix operation: arithmetic, comparison, or boolean."""
    operator: str  # e.g. "+", "-", "*", "/", "%", "<", ">", "==", "&&", "||"
    left: Expression
    right: Expression

@dataclass
class UnaryOp:
    """A prefix operation (currently only logical NOT)."""
    operator: str  # "!"
    operand: Expression

@dataclass
class CallExpr:
    """A built-in reporter that returns a value.

    Examples: join(a, b), letter_of(idx, s), length(s), ltoa(n)
    """
    func: str
    args: list[Expression] = field(default_factory=list)

@dataclass
class ProcedureCallExpr:
    """A user-defined procedure used as an expression (rare in Scratch)."""
    proc_name: str
    args: list[Expression] = field(default_factory=list)


# Union of all expression nodes
Expression = Union[Literal, VariableRef, BinaryOp, UnaryOp, CallExpr, ProcedureCallExpr]


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@dataclass
class SetVariable:
    """Assign a value to a variable."""
    var_id: str
    var_name: str
    value: Expression

@dataclass
class ChangeVariable:
    """Increment a variable by a value (always numeric)."""
    var_id: str
    var_name: str
    delta: Expression

@dataclass
class Say:
    """Output a value (maps to printf/printk depending on backend)."""
    message: Expression
    duration: Expression | None = None  # sayforsecs: ignored in C, emitted as comment

@dataclass
class Repeat:
    """repeat (n) { body }"""
    count: Expression
    body: list[Statement] = field(default_factory=list)

@dataclass
class Forever:
    """forever { body } — an infinite loop."""
    body: list[Statement] = field(default_factory=list)

@dataclass
class RepeatUntil:
    """repeat until (cond) { body } — while (!cond) { body }"""
    condition: Expression
    body: list[Statement] = field(default_factory=list)

@dataclass
class WaitUntil:
    """wait until (cond) — spin loop until condition is true."""
    condition: Expression

@dataclass
class IfThen:
    """if (cond) { body }"""
    condition: Expression
    then_body: list[Statement] = field(default_factory=list)

@dataclass
class IfThenElse:
    """if (cond) { then } else { else }"""
    condition: Expression
    then_body: list[Statement] = field(default_factory=list)
    else_body: list[Statement] = field(default_factory=list)

@dataclass
class Stop:
    """stop [this script] — emitted as return."""
    pass

@dataclass
class Wait:
    """wait (n) secs — no-op in C, emitted as a comment."""
    duration: Expression

@dataclass
class ProcedureCall:
    """Call a user-defined procedure."""
    proc_name: str
    args: list[Expression] = field(default_factory=list)


# Union of all statement nodes
Statement = Union[
    SetVariable, ChangeVariable, Say, Repeat, Forever, RepeatUntil,
    WaitUntil, IfThen, IfThenElse, Stop, Wait, ProcedureCall,
]


# ---------------------------------------------------------------------------
# Top-level structures
# ---------------------------------------------------------------------------

class HatKind(Enum):
    """What event triggers a script."""
    FLAG_CLICKED = auto()       # event_whenflagclicked → main / module_init
    BROADCAST_INIT = auto()     # whenbroadcastreceived "init" → module_init
    BROADCAST_EXIT = auto()     # whenbroadcastreceived "exit" → module_exit
    BROADCAST_OTHER = auto()    # other broadcasts (emitted as named functions)

@dataclass
class HatBlock:
    """The event that starts a script."""
    kind: HatKind
    broadcast_name: str | None = None  # only for BROADCAST_*

@dataclass
class Procedure:
    """A user-defined custom block (procedure)."""
    name: str
    param_names: list[str] = field(default_factory=list)
    param_ids: list[str] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)

@dataclass
class Script:
    """A top-level script: a hat block followed by a statement sequence."""
    hat: HatBlock
    body: list[Statement] = field(default_factory=list)

@dataclass
class Variable:
    """A Scratch variable with its inferred C type."""
    var_id: str
    name: str
    initial_value: str = "0"
    inferred_type: ScratchType = ScratchType.UNKNOWN

@dataclass
class Sprite:
    """One sprite (or the stage). Scratch projects have at least one."""
    name: str
    variables: dict[str, Variable] = field(default_factory=dict)   # var_id → Variable
    scripts: list[Script] = field(default_factory=list)
    procedures: dict[str, Procedure] = field(default_factory=dict) # proc_name → Procedure

@dataclass
class Project:
    """The root IR node for an entire Scratch project."""
    sprites: list[Sprite] = field(default_factory=list)

    def all_variables(self) -> dict[str, Variable]:
        """Flatten variables across all sprites (Scratch 3 scopes are per-sprite
        but for simple projects they're effectively global)."""
        result: dict[str, Variable] = {}
        for sprite in self.sprites:
            result.update(sprite.variables)
        return result

    def all_procedures(self) -> dict[str, Procedure]:
        """Flatten procedures across all sprites."""
        result: dict[str, Procedure] = {}
        for sprite in self.sprites:
            result.update(sprite.procedures)
        return result
