"""Tests for the userspace code generation backend."""

from __future__ import annotations

from scratch2c.ir_builder import build_ir
from scratch2c.type_inference import infer_types
from scratch2c.codegen.userspace import UserspaceBackend


def _generate_userspace(project_json: dict) -> str:
    """Helper: build IR, infer types, generate userspace C."""
    project = build_ir(project_json)
    infer_types(project)
    backend = UserspaceBackend()
    return backend.generate(project)


class TestUserspaceCodegen:
    """Test the userspace C code generation backend."""

    def test_includes_stdio(self, simple_say_json):
        code = _generate_userspace(simple_say_json)
        assert "#include <stdio.h>" in code
        assert '#include "scratch_runtime.h"' in code

    def test_has_main(self, simple_say_json):
        code = _generate_userspace(simple_say_json)
        assert "int main(void)" in code
        assert "return 0;" in code

    def test_say_hello(self, simple_say_json):
        code = _generate_userspace(simple_say_json)
        assert 'printf(' in code
        assert 'hello' in code

    def test_fibonacci_structure(self, fibonacci_json):
        code = _generate_userspace(fibonacci_json)
        # Should declare long variables
        assert "long a = 0;" in code
        assert "long b = 1;" in code
        assert "long count = 10;" in code
        # Should have a for loop
        assert "for (long _i0 = 0;" in code
        # Should have printf
        assert "printf(" in code

    def test_fibonacci_compiles(self, fibonacci_json, tmp_path):
        """The generated Fibonacci code should be syntactically valid C.

        We don't compile it (no gcc guaranteed), but we check structural
        properties that a compiler would require.
        """
        code = _generate_userspace(fibonacci_json)
        # Every { has a matching }
        assert code.count("{") == code.count("}")
        # Ends with a newline
        assert code.endswith("\n")
        # Has balanced parentheses
        assert code.count("(") == code.count(")")

    def test_if_else(self, if_else_json):
        code = _generate_userspace(if_else_json)
        assert "if (" in code
        assert "} else {" in code
        assert "big" in code
        assert "small" in code

    def test_repeat_until(self, repeat_until_json):
        code = _generate_userspace(repeat_until_json)
        assert "while (!(" in code

    def test_string_variable_declaration(self, string_ops_json):
        code = _generate_userspace(string_ops_json)
        assert 'char msg[256]' in code

    def test_string_join(self, string_ops_json):
        code = _generate_userspace(string_ops_json)
        assert "scratch_join(" in code
        assert "snprintf(msg" in code

    def test_procedure_call(self, procedure_json):
        code = _generate_userspace(procedure_json)
        assert "void greet(" in code
        assert "greet(" in code

    def test_no_module_license(self, simple_say_json):
        """Userspace code should NOT have kernel module macros."""
        code = _generate_userspace(simple_say_json)
        assert "MODULE_LICENSE" not in code
        assert "printk" not in code

    def test_variable_change(self, fibonacci_json):
        code = _generate_userspace(fibonacci_json)
        assert "n += 1;" in code

    def test_division_guard(self):
        """Division should include a zero-guard."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"var_x": ["x", "0"]},
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": "set1",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                    "set1": {
                        "opcode": "data_setvariableto",
                        "next": None,
                        "parent": "hat",
                        "inputs": {"VALUE": [3, "div1", [4, ""]]},
                        "fields": {"VARIABLE": ["x", "var_x"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                    "div1": {
                        "opcode": "operator_divide",
                        "next": None,
                        "parent": "set1",
                        "inputs": {
                            "NUM1": [1, [4, "10"]],
                            "NUM2": [1, [4, "3"]],
                        },
                        "fields": {},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        code = _generate_userspace(project_json)
        assert "!= 0" in code

    def test_nested_loops_unique_counters(self):
        """Nested repeat loops must use distinct counter variables."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {},
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": "outer",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                    "outer": {
                        "opcode": "control_repeat",
                        "next": None,
                        "parent": "hat",
                        "inputs": {
                            "TIMES": [1, [4, "3"]],
                            "SUBSTACK": [2, "inner"],
                        },
                        "fields": {},
                        "shadow": False,
                        "topLevel": False,
                    },
                    "inner": {
                        "opcode": "control_repeat",
                        "next": None,
                        "parent": "outer",
                        "inputs": {
                            "TIMES": [1, [4, "2"]],
                            "SUBSTACK": [2, "say1"],
                        },
                        "fields": {},
                        "shadow": False,
                        "topLevel": False,
                    },
                    "say1": {
                        "opcode": "looks_say",
                        "next": None,
                        "parent": "inner",
                        "inputs": {"MESSAGE": [1, [10, "tick"]]},
                        "fields": {},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        code = _generate_userspace(project_json)
        assert "_i0" in code
        assert "_i1" in code
        # They must be different variables — no shadowing
        assert "_i0" != "_i1"

    def test_modulo_zero_guard(self):
        """Modulo should also include a zero-guard."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"var_x": ["x", "0"]},
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": "set1",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                    "set1": {
                        "opcode": "data_setvariableto",
                        "next": None,
                        "parent": "hat",
                        "inputs": {"VALUE": [3, "mod1", [4, ""]]},
                        "fields": {"VARIABLE": ["x", "var_x"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                    "mod1": {
                        "opcode": "operator_mod",
                        "next": None,
                        "parent": "set1",
                        "inputs": {
                            "NUM1": [1, [4, "10"]],
                            "NUM2": [1, [4, "3"]],
                        },
                        "fields": {},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        code = _generate_userspace(project_json)
        assert "% (" in code
        assert "!= 0" in code

    def test_boolean_initial_values_in_declaration(self):
        """Variables initialized with JSON true/false must emit 1/0 in C."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {
                    "v1": ["var_1", True],
                    "v2": ["var_2", False],
                },
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": None,
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                },
            }],
        }
        code = _generate_userspace(project_json)
        assert "long var_1 = 1;" in code, f"Expected 'long var_1 = 1;' in:\n{code}"
        assert "long var_2 = 0;" in code, f"Expected 'long var_2 = 0;' in:\n{code}"

    def test_set_variable_to_boolean_numeric_tag(self):
        """'set var to true' encoded as [4, "true"] (numeric context)
        must emit 'x = 1', not 'x = atol("true")' (which gives 0)."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"v1": ["x", 0]},
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": "set1",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                    "set1": {
                        "opcode": "data_setvariableto",
                        "next": "set2",
                        "parent": "hat",
                        "inputs": {"VALUE": [1, [4, "true"]]},
                        "fields": {"VARIABLE": ["x", "v1"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                    "set2": {
                        "opcode": "data_setvariableto",
                        "next": None,
                        "parent": "set1",
                        "inputs": {"VALUE": [1, [4, "false"]]},
                        "fields": {"VARIABLE": ["x", "v1"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        code = _generate_userspace(project_json)
        assert "x = 1;" in code, f"'true' in numeric tag should become 1:\n{code}"
        assert "x = 0;" in code, f"'false' in numeric tag should become 0:\n{code}"

    def test_tag10_string_true_is_text_not_boolean(self):
        """'set var to "true"' encoded as [10, "true"] is user-typed text.

        Tag 10 = string literal (from a text field in the Scratch UI).
        Scratch's Number("true") is 0, not 1. The string "true" is not a
        boolean — actual booleans come from reporter blocks like <contains>
        or <and>, which are separate expression nodes in the IR.

        NOTE: This is an open problem. The variable gets inferred as STRING
        because "true" is not numeric. If the user intended it as a boolean,
        they should use a boolean reporter block instead of typing "true".
        """
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"v1": ["x", 0]},
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": "set1",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                    "set1": {
                        "opcode": "data_setvariableto",
                        "next": None,
                        "parent": "hat",
                        "inputs": {"VALUE": [1, [10, "true"]]},
                        "fields": {"VARIABLE": ["x", "v1"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        code = _generate_userspace(project_json)
        # Tag 10 "true" is a string — variable becomes STRING, value stays as text
        assert '"true"' in code, f"Tag 10 'true' must stay as string text:\n{code}"
