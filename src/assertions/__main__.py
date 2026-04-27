import sys
from types import ModuleType

from assertions._runner import run
from assertions._targets import parse_target


USAGE = 'usage: python -m assertions [<target>...]'


def main(argv: list[str]) -> int:
    if not argv:
        argv = ['.']
    saved_sys_path = list(sys.path)
    try:
        groups: list[tuple[ModuleType, list[str] | None]] = []
        for arg in argv:
            for module, names in parse_target(arg):
                _add_to_groups(groups, module, names)
        failed = False
        for module, merged_names in groups:
            results = run(module, names=merged_names)
            for name, exc in results:
                if exc is None:
                    print(f'{name} ... ok')
                else:
                    print(f'{name} ... FAIL: {type(exc).__name__}: {exc}')
                    failed = True
        return 1 if failed else 0
    finally:
        sys.path[:] = saved_sys_path


def _add_to_groups(
    groups: list[tuple[ModuleType, list[str] | None]],
    module: ModuleType,
    names: list[str] | None,
) -> None:
    for i, (existing_module, existing_names) in enumerate(groups):
        if existing_module is module:
            if existing_names is None or names is None:
                groups[i] = (module, None)
            else:
                groups[i] = (module, existing_names + names)
            return
    groups.append((module, names))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
