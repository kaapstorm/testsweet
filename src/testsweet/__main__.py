import argparse
import os
import pathlib
import sys

from testsweet._config import load_config
from testsweet._loaders import scoped_sys_path
from testsweet._plugins import load_plugins, session_for, unit_wrapper
from testsweet._outcomes import Errored, Failed, Outcome, XPassed
from testsweet._report import (
    format_result_line,
    print_failure_detail,
    summarize,
)
from testsweet._runner import run
from testsweet._tag_filter import make_tag_filter
from testsweet._targets import discover_targets


_USAGE = """\
Usage: testsweet [-h | --help] [-t TAG]... [-T TAG]... [TARGET ...]
       python -m testsweet [-h | --help] [-t TAG]... [-T TAG]... [TARGET ...]

Run testsweet tests. Each TARGET selects what to run:

  <module>            Dotted module path (e.g. tests.foo)
  <module>.<unit>     A specific function or class within a module
  <module>.<Class>.<method>
                      A specific method of a test class
  <path/to/file.py>   A single Python file
  <path/to/dir>       A directory (walked recursively)

With no TARGET, testsweet walks the current working directory using any
[tool.testsweet.discovery] configuration in pyproject.toml.

Tag filters select tests by their @tag decorators. A method's effective
tags are the union of its class's tags and its own.

Options:
  -h, --help          Show this help message and exit.
  -t, --tag TAG       Run only tests with this tag (repeat for OR).
  -T, --exclude-tag TAG
                      Skip tests with this tag (repeat). A test runs
                      iff it matches some --tag (or none was given)
                      AND has no --exclude-tag.
"""


def _supports_color() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.environ.get('NO_COLOR'):
        return False
    if sys.platform == 'win32':
        # VT processing is auto-enabled from Python 3.12+. On older
        # versions, accept Windows Terminal (WT_SESSION) and ANSICON.
        return (
            sys.version_info >= (3, 12)
            or bool(os.environ.get('WT_SESSION'))
            or bool(os.environ.get('ANSICON'))
        )
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '-t', '--tag',
        action='append', default=[], dest='include_tags', metavar='TAG',
    )
    parser.add_argument(
        '-T', '--exclude-tag',
        action='append', default=[], dest='exclude_tags', metavar='TAG',
    )
    parser.add_argument('targets', nargs='*')
    return parser


def main(argv: list[str]) -> int:
    if any(arg in ('-h', '--help') for arg in argv):
        print(_USAGE, end='')
        return 0
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        # argparse prints to stderr and calls sys.exit on error.
        return int(exc.code or 2)
    include = frozenset(args.include_tags)
    exclude = frozenset(args.exclude_tags)
    overlap = include & exclude
    if overlap:
        joined = ', '.join(sorted(overlap))
        print(
            f'error: tag(s) cannot be both --tag and --exclude-tag: '
            f'{joined}',
            file=sys.stderr,
        )
        return 2
    keep = (
        make_tag_filter(include, exclude)
        if (include or exclude) else None
    )
    with scoped_sys_path():
        # `python -m testsweet` prepends the cwd to sys.path, but the
        # installed console script does not (sys.path[0] is its own bin
        # directory). Put the cwd on the path so dotted targets resolve
        # against the project the same way under both invocations.
        cwd = str(pathlib.Path.cwd())
        if cwd not in sys.path:
            sys.path.insert(0, cwd)
        config = load_config(pathlib.Path.cwd())
        plugins = load_plugins()
        wrap_unit = unit_wrapper(plugins)
        use_color = _supports_color()
        results: list[tuple[str, Outcome]] = []
        real_failures: list[tuple[str, Outcome]] = []
        with session_for(plugins):
            groups = discover_targets(args.targets, config)
            for module, names in groups:
                for name, outcome in run(
                    module,
                    names=names,
                    wrap_unit=wrap_unit,
                    keep=keep,
                ):
                    full_name = f'{module.__name__}.{name}'
                    print(format_result_line(full_name, outcome, use_color=use_color))
                    results.append((full_name, outcome))
                    if isinstance(outcome, (Failed, Errored, XPassed)):
                        real_failures.append((full_name, outcome))
        for full_name, outcome in real_failures:
            print_failure_detail(full_name, outcome)
        print(summarize(results, use_color=use_color))
        return 1 if real_failures else 0


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == '__main__':
    cli()
