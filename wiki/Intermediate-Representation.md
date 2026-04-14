# Intermediate Representation

The IR is defined in `scratch2c/ir.py` using Python dataclasses. It represents the program's meaning without any target-specific encoding.

## Hierarchy

```
Project
 └─ Sprite[]
     ├─ variables: dict[str, Variable]
     ├─ scripts: list[Script]
     │   ├─ hat: HatBlock
     │   └─ body: list[Statement]
     └─ procedures: dict[str, Procedure]
         ├─ param_names, param_ids
         └─ body: list[Statement]
```

## Statements

Statements are things that do something. Each maps to one or more Scratch opcodes:

```python
SetVariable(var_id, var_name, value: Expression)       # data_setvariableto
ChangeVariable(var_id, var_name, delta: Expression)     # data_changevariableby
Say(message: Expression, duration: Expression | None)   # looks_say, looks_sayforsecs
Repeat(count: Expression, body: list[Statement])        # control_repeat
Forever(body: list[Statement])                          # control_forever
RepeatUntil(condition: Expression, body: list[Statement])  # control_repeat_until
WaitUntil(condition: Expression)                        # control_wait_until
IfThen(condition: Expression, then_body: list[Statement])  # control_if
IfThenElse(condition, then_body, else_body)              # control_if_else
Stop()                                                   # control_stop
Wait(duration: Expression)                               # control_wait
ProcedureCall(proc_name: str, args: list[Expression])    # procedures_call
```

## Expressions

Expressions return a value. They form trees:

```python
Literal(value: str)                      # constant — always stored as string
VariableRef(var_id: str, var_name: str)  # variable read
BinaryOp(operator: str, left, right)     # +, -, *, /, %, <, >, ==, &&, ||
UnaryOp(operator: str, operand)          # !
CallExpr(func: str, args: list)          # scratch_join, scratch_contains, etc.
```

`Literal.value` is always a string. Numbers are stored as `"42"`, not `42`. This simplifies the IR — type resolution happens in the type inference pass, not at parse time.

## Hat blocks

```python
class HatKind(Enum):
    FLAG_CLICKED       # event_whenflagclicked → main / module_init
    BROADCAST_INIT     # whenbroadcastreceived "init" → module_init
    BROADCAST_EXIT     # whenbroadcastreceived "exit" → module_exit
    BROADCAST_OTHER    # other broadcasts → named function
```

## Variables

```python
@dataclass
class Variable:
    var_id: str
    name: str
    initial_value: str = "0"
    inferred_type: ScratchType = ScratchType.UNKNOWN  # set by type_inference
```

`inferred_type` starts as `UNKNOWN` and is set to `LONG` or `STRING` by the type inference pass. Code generation reads this to decide how to declare and assign the variable.

## Helpers

`Project.all_variables()` flattens variables across all sprites into a single dict. This is necessary because Stage variables are global in Scratch but are defined on the Stage target, while code that uses them may be on Sprite1.

`Project.all_procedures()` does the same for custom blocks.
