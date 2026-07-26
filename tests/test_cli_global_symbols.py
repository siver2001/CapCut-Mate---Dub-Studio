import builtins
import dis
import importlib
import inspect
import pkgutil
import types
import unittest

import tools.dub_studio.cli_parts as cli_parts_package


class CliGlobalSymbolTests(unittest.TestCase):
    def test_all_loaded_cli_globals_resolve(self):
        missing: set[tuple[str, str, int, str]] = set()
        builtin_names = set(dir(builtins))

        def inspect_code(
            module_name: str,
            namespace: dict,
            qualified_name: str,
            code: types.CodeType,
        ) -> None:
            for instruction in dis.get_instructions(code):
                if instruction.opname != "LOAD_GLOBAL":
                    continue
                name = str(instruction.argval)
                if name not in namespace and name not in builtin_names:
                    missing.add(
                        (module_name, qualified_name, code.co_firstlineno, name)
                    )
            for value in code.co_consts:
                if isinstance(value, types.CodeType):
                    inspect_code(
                        module_name,
                        namespace,
                        f"{qualified_name}.{value.co_name}",
                        value,
                    )

        for module_info in pkgutil.iter_modules(cli_parts_package.__path__):
            if module_info.name.startswith("_"):
                continue
            module_name = f"{cli_parts_package.__name__}.{module_info.name}"
            module = importlib.import_module(module_name)
            for name, obj in vars(module).items():
                if inspect.isfunction(obj) and obj.__module__ == module_name:
                    inspect_code(module_name, obj.__globals__, name, obj.__code__)
                elif inspect.isclass(obj) and obj.__module__ == module_name:
                    for member_name, member in vars(obj).items():
                        if inspect.isfunction(member):
                            inspect_code(
                                module_name,
                                member.__globals__,
                                f"{name}.{member_name}",
                                member.__code__,
                            )

        formatted = [
            f"{module}:{line} {qualified_name}: {name}"
            for module, qualified_name, line, name in sorted(missing)
        ]
        self.assertEqual(
            formatted,
            [],
            "Unresolved globals can crash an untested runtime branch:\n"
            + "\n".join(formatted),
        )


if __name__ == "__main__":
    unittest.main()
