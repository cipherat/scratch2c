"""Tests for the kernel module code generation backend."""

from __future__ import annotations

from scratch2c.ir_builder import build_ir
from scratch2c.type_inference import infer_types
from scratch2c.codegen.kernel import KernelBackend


def _generate_kernel(project_json: dict) -> str:
    """Helper: build IR, infer types, generate kernel module C."""
    project = build_ir(project_json)
    infer_types(project)
    backend = KernelBackend()
    return backend.generate(project)


class TestKernelCodegen:
    """Test the kernel module C code generation backend."""

    def test_includes_kernel_headers(self, simple_say_json):
        code = _generate_kernel(simple_say_json)
        assert "#include <linux/init.h>" in code
        assert "#include <linux/module.h>" in code
        assert "#include <linux/kernel.h>" in code

    def test_module_license(self, simple_say_json):
        code = _generate_kernel(simple_say_json)
        assert 'MODULE_LICENSE("GPL")' in code

    def test_uses_printk(self, simple_say_json):
        code = _generate_kernel(simple_say_json)
        assert "printk(KERN_INFO" in code

    def test_no_printf(self, simple_say_json):
        code = _generate_kernel(simple_say_json)
        assert "printf(" not in code

    def test_init_and_exit(self, simple_say_json):
        code = _generate_kernel(simple_say_json)
        assert "static int __init scratch_init" in code
        assert "static void __exit scratch_exit" in code

    def test_static_variables(self, fibonacci_json):
        code = _generate_kernel(fibonacci_json)
        assert "static long a = 0;" in code
        assert "static long b = 1;" in code

    def test_broadcast_init_exit(self, kernel_exit_json):
        code = _generate_kernel(kernel_exit_json)
        assert "scratch_init" in code
        assert "scratch_exit" in code
        assert "module loaded" in code
        assert "module unloaded" in code

    def test_always_has_exit(self, simple_say_json):
        """Kernel modules always need module_exit, even without exit broadcasts."""
        code = _generate_kernel(simple_say_json)
        assert "scratch_exit" in code

    def test_balanced_braces(self, fibonacci_json):
        code = _generate_kernel(fibonacci_json)
        assert code.count("{") == code.count("}")

    def test_no_stdio(self, fibonacci_json):
        code = _generate_kernel(fibonacci_json)
        assert "#include <stdio.h>" not in code

    def test_module_init_exit_macros(self, simple_say_json):
        """The kernel MUST have module_init/module_exit macros or the
        functions will never be called and insmod produces no output."""
        code = _generate_kernel(simple_say_json)
        assert "module_init(scratch_init);" in code
        assert "module_exit(scratch_exit);" in code

    def test_module_macros_after_functions(self, simple_say_json):
        """module_init/module_exit must appear after the function definitions."""
        code = _generate_kernel(simple_say_json)
        init_func_pos = code.index("static int __init scratch_init")
        exit_func_pos = code.index("static void __exit scratch_exit")
        init_macro_pos = code.index("module_init(scratch_init);")
        exit_macro_pos = code.index("module_exit(scratch_exit);")
        assert init_macro_pos > init_func_pos
        assert exit_macro_pos > exit_func_pos

    def test_no_linux_sprintf_h(self, simple_say_json):
        """linux/sprintf.h doesn't exist on many kernels; snprintf
        comes from linux/kernel.h."""
        code = _generate_kernel(simple_say_json)
        assert "linux/sprintf.h" not in code

    def test_say_string_variable_uses_percent_s(self, string_ops_json):
        """A string variable passed to say MUST use %s, not %ld.

        This was the bug that caused garbage like -1041686496 in dmesg:
        printk("%ld", (long)message) reinterprets the char* pointer as
        a number. It must be printk("%s", message).
        """
        code = _generate_kernel(string_ops_json)
        # 'msg' is a string var — when say'd it must use %s
        assert 'printk(KERN_INFO "%s\\n", msg)' in code
        # And must NOT cast it to long
        assert '(long)msg' not in code
