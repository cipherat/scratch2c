"""
scratch2c — Convert MIT Scratch 3 (.sb3) projects to compilable C code.

Pipeline:
  .sb3 file → reader → JSON → ir_builder → IR → type_inference → typed IR → codegen → C source
"""

__version__ = "0.1.0"
