"""Tests for the type inference pass."""

from __future__ import annotations

from scratch2c.ir import ScratchType
from scratch2c.ir_builder import build_ir
from scratch2c.type_inference import infer_types


class TestTypeInference:
    """Test the two-pass type resolver."""

    def test_fibonacci_variables_are_long(self, fibonacci_json):
        """All Fibonacci variables should be inferred as LONG."""
        project = build_ir(fibonacci_json)
        infer_types(project)
        for var in project.all_variables().values():
            assert var.inferred_type == ScratchType.LONG, (
                f"Variable '{var.name}' should be LONG, got {var.inferred_type}"
            )

    def test_string_variable_from_join(self, string_ops_json):
        """A variable assigned from join() should be STRING."""
        project = build_ir(string_ops_json)
        infer_types(project)
        msg_var = project.all_variables()["var_msg"]
        assert msg_var.inferred_type == ScratchType.STRING

    def test_numeric_initial_value_defaults_long(self):
        """Variables with numeric initial values and no other context → LONG."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"var_x": ["x", "42"]},
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
        project = build_ir(project_json)
        infer_types(project)
        x_var = project.all_variables()["var_x"]
        # Unassigned but no string context → defaults to LONG
        assert x_var.inferred_type == ScratchType.LONG

    def test_change_variable_forces_long(self):
        """changevariableby always forces LONG type."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"var_x": ["x", "0"]},
                "blocks": {
                    "hat": {
                        "opcode": "event_whenflagclicked",
                        "next": "change1",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                    },
                    "change1": {
                        "opcode": "data_changevariableby",
                        "next": None,
                        "parent": "hat",
                        "inputs": {"VALUE": [1, [4, "1"]]},
                        "fields": {"VARIABLE": ["x", "var_x"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        project = build_ir(project_json)
        infer_types(project)
        assert project.all_variables()["var_x"].inferred_type == ScratchType.LONG

    def test_arithmetic_assignment_forces_long(self, if_else_json):
        """Variable 'x' used in comparison → stays LONG (from initial numeric value)."""
        project = build_ir(if_else_json)
        infer_types(project)
        x_var = project.all_variables()["var_x"]
        assert x_var.inferred_type == ScratchType.LONG

    def test_string_literal_assignment(self):
        """Assigning a non-numeric string literal → STRING."""
        project_json = {
            "targets": [{
                "isStage": True,
                "name": "Stage",
                "variables": {"var_name": ["name", ""]},
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
                        "inputs": {"VALUE": [1, [10, "hello"]]},
                        "fields": {"VARIABLE": ["name", "var_name"]},
                        "shadow": False,
                        "topLevel": False,
                    },
                },
            }],
        }
        project = build_ir(project_json)
        infer_types(project)
        assert project.all_variables()["var_name"].inferred_type == ScratchType.STRING

    def test_boolean_initial_values(self):
        """JSON true/false must become "1"/"0", not "True"/"False".

        Scratch stores booleans as JSON true/false. Python's json.loads
        turns these into True/False. str(True) gives "True" which is not
        a valid C literal — it must be normalized to "1"/"0".
        """
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
        project = build_ir(project_json)
        infer_types(project)
        v1 = project.all_variables()["v1"]
        v2 = project.all_variables()["v2"]
        assert v1.initial_value == "1", f"True should become '1', got '{v1.initial_value}'"
        assert v2.initial_value == "0", f"False should become '0', got '{v2.initial_value}'"
        assert v1.inferred_type == ScratchType.LONG
        assert v2.inferred_type == ScratchType.LONG
