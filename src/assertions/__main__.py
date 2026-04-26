import importlib
import sys

from assertions._runner import run


USAGE = 'usage: python -m assertions <dotted.module>'


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    module = importlib.import_module(argv[0])
    results = run(module)
    failed = False
    for func, exc in results:
        if exc is None:
            print(f'{func.__name__} ... ok')
        else:
            print(f'{func.__name__} ... FAIL: ' f'{type(exc).__name__}: {exc}')
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
