"""Tests for the IR builder (JSON → IR conversion)."""

from __future__ import annotations

from scratch2c.ir import (
    BinaryOp, CallExpr, ChangeVariable, HatKind, IfThenElse, Literal,
    ProcedureCall, Repeat, RepeatUntil, Say, SetVariable, VariableRef,
)
from scratch2c.ir_builder import build_ir


class TestBuildIR:
    """Test building IR from project JSON."""

    def test_fibonacci_has_one_sprite(self, fibonacci_json):
        project = build_ir(fibonacci_json)
        assert len(project.sprites) == 1
        assert project.sprites[0].name == "Stage"

    def test_fibonacci_has_variables(self, fibonacci_json):
        project = build_ir(fibonacci_json)
        stage = project.sprites[0]
        assert len(stage.variables) == 5
        names = {v.name for v in stage.variables.values()}
        assert names == {"a", "b", "n", "count", "temp"}

    def test_fibonacci_has_one_script(self, fibonacci_json):
        project = build_ir(fibonacci_json)
        stage = project.sprites[0]
        assert len(stage.scripts) == 1
        assert stage.scripts[0].hat.kind == HatKind.FLAG_CLICKED

    def test_fibonacci_body_structure(self, fibonacci_json):
        """The body should be: set a, set b, set n, say a, repeat { ... }."""
        project = build_ir(fibonacci_json)
        body = project.sprites[0].scripts[0].body
        assert len(body) == 5
        assert isinstance(body[0], SetVariable)
        assert body[0].var_name == "a"
        assert isinstance(body[1], SetVariable)
        assert body[1].var_name == "b"
        assert isinstance(body[2], SetVariable)
        assert body[2].var_name == "n"
        assert isinstance(body[3], Say)
        assert isinstance(body[4], Repeat)

    def test_fibonacci_repeat_body(self, fibonacci_json):
        """Inside the repeat: set temp = a+b, set a = b, set b = temp, say a, change n."""
        project = build_ir(fibonacci_json)
        repeat_stmt = project.sprites[0].scripts[0].body[4]
        assert isinstance(repeat_stmt, Repeat)
        assert len(repeat_stmt.body) == 5
        # temp = a + b
        set_temp = repeat_stmt.body[0]
        assert isinstance(set_temp, SetVariable)
        assert set_temp.var_name == "temp"
        assert isinstance(set_temp.value, BinaryOp)
        assert set_temp.value.operator == "+"

    def test_simple_say(self, simple_say_json):
        project = build_ir(simple_say_json)
        body = project.sprites[0].scripts[0].body
        assert len(body) == 1
        assert isinstance(body[0], Say)
        assert isinstance(body[0].message, Literal)
        assert body[0].message.value == "hello"

    def test_if_else(self, if_else_json):
        project = build_ir(if_else_json)
        body = project.sprites[0].scripts[0].body
        assert len(body) == 1
        stmt = body[0]
        assert isinstance(stmt, IfThenElse)
        assert isinstance(stmt.condition, BinaryOp)
        assert stmt.condition.operator == ">"
        assert len(stmt.then_body) == 1
        assert len(stmt.else_body) == 1

    def test_procedure_with_args(self, procedure_json):
        project = build_ir(procedure_json)
        stage = project.sprites[0]
        assert len(stage.procedures) == 1
        proc_name = list(stage.procedures.keys())[0]
        proc = stage.procedures[proc_name]
        assert len(proc.param_names) == 1
        assert proc.param_names[0] == "name"
        # Body has a say statement that reads the argument
        assert len(proc.body) == 1
        assert isinstance(proc.body[0], Say)

    def test_procedure_call_in_script(self, procedure_json):
        project = build_ir(procedure_json)
        body = project.sprites[0].scripts[0].body
        assert len(body) == 1
        assert isinstance(body[0], ProcedureCall)
        assert len(body[0].args) == 1

    def test_repeat_until(self, repeat_until_json):
        project = build_ir(repeat_until_json)
        body = project.sprites[0].scripts[0].body
        assert len(body) == 1
        stmt = body[0]
        assert isinstance(stmt, RepeatUntil)
        assert isinstance(stmt.condition, BinaryOp)
        assert stmt.condition.operator == ">"
        assert len(stmt.body) == 2  # change x, say x

    def test_string_operations(self, string_ops_json):
        project = build_ir(string_ops_json)
        body = project.sprites[0].scripts[0].body
        assert len(body) == 2
        set_msg = body[0]
        assert isinstance(set_msg, SetVariable)
        assert isinstance(set_msg.value, CallExpr)
        assert set_msg.value.func == "scratch_join"

    def test_broadcast_init_exit(self, kernel_exit_json):
        project = build_ir(kernel_exit_json)
        scripts = project.sprites[0].scripts
        assert len(scripts) == 2
        kinds = {s.hat.kind for s in scripts}
        assert HatKind.BROADCAST_INIT in kinds
        assert HatKind.BROADCAST_EXIT in kinds

    def test_empty_project(self):
        project = build_ir({"targets": []})
        assert len(project.sprites) == 0

    def test_variable_reporter_in_expression(self, fibonacci_json):
        """The say block should contain a VariableRef, not a Literal."""
        project = build_ir(fibonacci_json)
        say_stmt = project.sprites[0].scripts[0].body[3]
        assert isinstance(say_stmt, Say)
        assert isinstance(say_stmt.message, VariableRef)
        assert say_stmt.message.var_name == "a"
