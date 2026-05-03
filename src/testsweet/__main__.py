import pathlib
import sys

from testsweet._config import load_config
from testsweet._loaders import scoped_sys_path
from testsweet._plugins import load_plugins, session_for, unit_wrapper
from testsweet._report import format_result_line, print_failure_detail
from testsweet._runner import run
from testsweet._targets import discover_targets


_USAGE = """\
Usage: testsweet [-h | --help] [TARGET ...]
       python -m testsweet [-h | --help] [TARGET ...]

Run testsweet tests. Each TARGET selects what to run:

  <module>            Dotted module path (e.g. tests.foo)
  <module>.<unit>     A specific function or class within a module
  <module>.<Class>.<method>
                      A specific method of a test class
  <path/to/file.py>   A single Python file
  <path/to/dir>       A directory (walked recursively)

With no TARGET, testsweet walks the current working directory using any
[tool.testsweet.discovery] configuration in pyproject.toml.

Options:
  -h, --help          Show this help message and exit.
"""


def main(argv: list[str]) -> int:
    if any(arg in ('-h', '--help') for arg in argv):
        print(_USAGE, end='')
        return 0
    with scoped_sys_path():
        config = load_config(pathlib.Path.cwd())
        plugins = load_plugins()
        wrap_unit = unit_wrapper(plugins)
        failures: list[tuple[str, Exception]] = []
        with session_for(plugins):
            groups = discover_targets(argv, config)
            for module, names in groups:
                for name, exc in run(
                    module, names=names, wrap_unit=wrap_unit,
                ):
                    full_name = f'{module.__name__}.{name}'
                    print(format_result_line(full_name, exc))
                    if exc is not None:
                        failures.append((full_name, exc))
        for full_name, exc in failures:
            print_failure_detail(full_name, exc)
        return 1 if failures else 0


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == '__main__':
    cli()
