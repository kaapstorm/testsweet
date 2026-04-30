import pathlib
import sys
import traceback

from testsweet._assertion import assertion_source, explain_assertion
from testsweet._config import load_config
from testsweet._runner import run
from testsweet._targets import discover_targets


def main(argv: list[str]) -> int:
    saved_sys_path = list(sys.path)
    try:
        config = load_config(pathlib.Path.cwd())
        groups = discover_targets(argv, config)
        failures: list[tuple[str, Exception]] = []
        for module, names in groups:
            for name, exc in run(module, names=names):
                full_name = f'{module.__name__}.{name}'
                if exc is None:
                    print(f'{full_name} ... ok')
                else:
                    detail = str(exc)
                    if not detail and isinstance(exc, AssertionError):
                        detail = assertion_source(exc) or ''
                    print(
                        f'{full_name} ... FAIL: {type(exc).__name__}: {detail}'
                    )
                    failures.append((full_name, exc))
        for full_name, exc in failures:
            print()
            print('=' * 70)
            print(f'FAIL: {full_name}')
            print('-' * 70)
            tb = exc.__traceback__.tb_next if exc.__traceback__ else None
            traceback.print_exception(type(exc), exc, tb, file=sys.stdout)
            if isinstance(exc, AssertionError):
                explanation = explain_assertion(exc)
                if explanation is not None:
                    print(explanation)
        return 1 if failures else 0
    finally:
        sys.path[:] = saved_sys_path


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
