"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scratch2c.ir_builder import build_ir
from scratch2c.type_inference import infer_types


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fibonacci_json() -> dict:
    """Load the Fibonacci project.json fixture."""
    return json.loads((FIXTURES_DIR / "fibonacci.json").read_text())


@pytest.fixture
def fibonacci_project(fibonacci_json):
    """Build and type-infer the Fibonacci project."""
    project = build_ir(fibonacci_json)
    infer_types(project)
    return project


@pytest.fixture
def simple_say_json() -> dict:
    """A minimal project: green flag → say 'hello'."""
    return {
        "targets": [{
            "isStage": True,
            "name": "Stage",
            "variables": {},
            "blocks": {
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "say1",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                },
                "say1": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "hat",
                    "inputs": {
                        "MESSAGE": [1, [10, "hello"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
            },
        }],
    }


@pytest.fixture
def if_else_json() -> dict:
    """A project with if/else: if (x > 5) say 'big' else say 'small'."""
    return {
        "targets": [{
            "isStage": True,
            "name": "Stage",
            "variables": {
                "var_x": ["x", "10"],
            },
            "blocks": {
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "ifelse1",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                },
                "ifelse1": {
                    "opcode": "control_if_else",
                    "next": None,
                    "parent": "hat",
                    "inputs": {
                        "CONDITION": [2, "gt1"],
                        "SUBSTACK": [2, "say_big"],
                        "SUBSTACK2": [2, "say_small"],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "gt1": {
                    "opcode": "operator_gt",
                    "next": None,
                    "parent": "ifelse1",
                    "inputs": {
                        "OPERAND1": [3, "var_x_rep", [10, ""]],
                        "OPERAND2": [1, [10, "5"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "var_x_rep": {
                    "opcode": "data_variable",
                    "next": None,
                    "parent": "gt1",
                    "inputs": {},
                    "fields": {
                        "VARIABLE": ["x", "var_x"],
                    },
                    "shadow": False,
                    "topLevel": False,
                },
                "say_big": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "ifelse1",
                    "inputs": {
                        "MESSAGE": [1, [10, "big"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "say_small": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "ifelse1",
                    "inputs": {
                        "MESSAGE": [1, [10, "small"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
            },
        }],
    }


@pytest.fixture
def procedure_json() -> dict:
    """A project with a custom block (procedure) that takes an argument."""
    return {
        "targets": [{
            "isStage": True,
            "name": "Stage",
            "variables": {},
            "blocks": {
                "procdef": {
                    "opcode": "procedures_definition",
                    "next": "say_arg",
                    "parent": None,
                    "inputs": {
                        "custom_block": [1, "proto1"],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                },
                "proto1": {
                    "opcode": "procedures_prototype",
                    "next": None,
                    "parent": "procdef",
                    "inputs": {
                        "arg1_id": [1, "arg1_reporter"],
                    },
                    "fields": {},
                    "shadow": True,
                    "topLevel": False,
                    "mutation": {
                        "proccode": "greet %s",
                        "argumentids": "[\"arg1_id\"]",
                        "argumentnames": "[\"name\"]",
                        "argumentdefaults": "[\"\"]",
                        "warp": "false",
                    },
                },
                "arg1_reporter": {
                    "opcode": "argument_reporter_string_number",
                    "next": None,
                    "parent": "proto1",
                    "inputs": {},
                    "fields": {
                        "VALUE": ["name", None],
                    },
                    "shadow": True,
                    "topLevel": False,
                },
                "say_arg": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "procdef",
                    "inputs": {
                        "MESSAGE": [3, "arg_rep_in_say", [10, ""]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "arg_rep_in_say": {
                    "opcode": "argument_reporter_string_number",
                    "next": None,
                    "parent": "say_arg",
                    "inputs": {},
                    "fields": {
                        "VALUE": ["name", None],
                    },
                    "shadow": False,
                    "topLevel": False,
                },
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "call1",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                },
                "call1": {
                    "opcode": "procedures_call",
                    "next": None,
                    "parent": "hat",
                    "inputs": {
                        "arg1_id": [1, [10, "42"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                    "mutation": {
                        "proccode": "greet %s",
                        "argumentids": "[\"arg1_id\"]",
                        "warp": "false",
                    },
                },
            },
        }],
    }


@pytest.fixture
def string_ops_json() -> dict:
    """A project using join and length."""
    return {
        "targets": [{
            "isStage": True,
            "name": "Stage",
            "variables": {
                "var_msg": ["msg", ""],
            },
            "blocks": {
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "set_msg",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                },
                "set_msg": {
                    "opcode": "data_setvariableto",
                    "next": "say_msg",
                    "parent": "hat",
                    "inputs": {
                        "VALUE": [3, "join1", [10, ""]],
                    },
                    "fields": {
                        "VARIABLE": ["msg", "var_msg"],
                    },
                    "shadow": False,
                    "topLevel": False,
                },
                "join1": {
                    "opcode": "operator_join",
                    "next": None,
                    "parent": "set_msg",
                    "inputs": {
                        "STRING1": [1, [10, "hello "]],
                        "STRING2": [1, [10, "world"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "say_msg": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "set_msg",
                    "inputs": {
                        "MESSAGE": [3, "var_msg_rep", [10, ""]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "var_msg_rep": {
                    "opcode": "data_variable",
                    "next": None,
                    "parent": "say_msg",
                    "inputs": {},
                    "fields": {
                        "VARIABLE": ["msg", "var_msg"],
                    },
                    "shadow": False,
                    "topLevel": False,
                },
            },
        }],
    }


@pytest.fixture
def repeat_until_json() -> dict:
    """A project with repeat_until: count up until x >= 5."""
    return {
        "targets": [{
            "isStage": True,
            "name": "Stage",
            "variables": {
                "var_x": ["x", "0"],
            },
            "blocks": {
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "repeat_until1",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                },
                "repeat_until1": {
                    "opcode": "control_repeat_until",
                    "next": None,
                    "parent": "hat",
                    "inputs": {
                        "CONDITION": [2, "gt_cond"],
                        "SUBSTACK": [2, "change_x"],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "gt_cond": {
                    "opcode": "operator_gt",
                    "next": None,
                    "parent": "repeat_until1",
                    "inputs": {
                        "OPERAND1": [3, "var_x_rep", [10, ""]],
                        "OPERAND2": [1, [10, "5"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "var_x_rep": {
                    "opcode": "data_variable",
                    "next": None,
                    "parent": "gt_cond",
                    "inputs": {},
                    "fields": {
                        "VARIABLE": ["x", "var_x"],
                    },
                    "shadow": False,
                    "topLevel": False,
                },
                "change_x": {
                    "opcode": "data_changevariableby",
                    "next": "say_x",
                    "parent": "repeat_until1",
                    "inputs": {
                        "VALUE": [1, [4, "1"]],
                    },
                    "fields": {
                        "VARIABLE": ["x", "var_x"],
                    },
                    "shadow": False,
                    "topLevel": False,
                },
                "say_x": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "change_x",
                    "inputs": {
                        "MESSAGE": [3, "var_x_rep2", [10, ""]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "var_x_rep2": {
                    "opcode": "data_variable",
                    "next": None,
                    "parent": "say_x",
                    "inputs": {},
                    "fields": {
                        "VARIABLE": ["x", "var_x"],
                    },
                    "shadow": False,
                    "topLevel": False,
                }
            }
        }]
    }


@pytest.fixture
def kernel_exit_json() -> dict:
    """A project with both init and exit broadcast handlers (kernel module pattern)."""
    return {
        "targets": [{
            "isStage": True,
            "name": "Stage",
            "variables": {},
            "blocks": {
                "hat_init": {
                    "opcode": "event_whenbroadcastreceived",
                    "next": "say_init",
                    "parent": None,
                    "inputs": {},
                    "fields": {
                        "BROADCAST_OPTION": ["init", "broadcast_init_id"],
                    },
                    "shadow": False,
                    "topLevel": True,
                },
                "say_init": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "hat_init",
                    "inputs": {
                        "MESSAGE": [1, [10, "module loaded"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
                "hat_exit": {
                    "opcode": "event_whenbroadcastreceived",
                    "next": "say_exit",
                    "parent": None,
                    "inputs": {},
                    "fields": {
                        "BROADCAST_OPTION": ["exit", "broadcast_exit_id"],
                    },
                    "shadow": False,
                    "topLevel": True,
                },
                "say_exit": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "hat_exit",
                    "inputs": {
                        "MESSAGE": [1, [10, "module unloaded"]],
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False,
                },
            },
        }],
    }
