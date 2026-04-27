import pathlib
import sys

from assertions._config import load_config
from assertions._runner import run
from assertions._targets import discover_targets


def main(argv: list[str]) -> int:
    saved_sys_path = list(sys.path)
    try:
        config = load_config(pathlib.Path.cwd())
        groups = discover_targets(argv, config)
        failed = False
        for module, names in groups:
            for name, exc in run(module, names=names):
                if exc is None:
                    print(f'{name} ... ok')
                else:
                    print(f'{name} ... FAIL: {type(exc).__name__}: {exc}')
                    failed = True
        return 1 if failed else 0
    finally:
        sys.path[:] = saved_sys_path


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
