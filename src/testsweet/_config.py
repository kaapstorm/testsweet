import pathlib
import tomllib
from dataclasses import dataclass, field


_VALID_KEYS = frozenset({'include_paths', 'exclude_paths', 'test_files'})


class ConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class DiscoveryConfig:
    include_paths: tuple[str, ...] = field(default=())
    exclude_paths: tuple[str, ...] = field(default=())
    test_files: tuple[str, ...] = field(default=())
    project_root: pathlib.Path | None = field(default=None)


def load_config(start: pathlib.Path) -> DiscoveryConfig:
    pyproject = _find_pyproject(start)
    if pyproject is None:
        return DiscoveryConfig()
    project_root = pyproject.parent.resolve()
    raw = tomllib.loads(pyproject.read_text())
    section = raw.get('tool', {}).get('testsweet', {}).get('discovery', {})
    return _build_config(section, project_root)


def _find_pyproject(start: pathlib.Path) -> pathlib.Path | None:
    current = start.resolve()
    while True:
        candidate = current / 'pyproject.toml'
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def _build_config(
    section: dict,
    project_root: pathlib.Path,
) -> DiscoveryConfig:
    unknown = set(section) - _VALID_KEYS
    if unknown:
        raise ConfigurationError(
            f'unknown key {sorted(unknown)[0]!r} in '
            f'[tool.testsweet.discovery]'
        )
    return DiscoveryConfig(
        include_paths=_to_string_tuple(
            section.get('include_paths', []),
            'include_paths',
        ),
        exclude_paths=_to_string_tuple(
            section.get('exclude_paths', []),
            'exclude_paths',
        ),
        test_files=_to_string_tuple(
            section.get('test_files', []),
            'test_files',
        ),
        project_root=project_root,
    )


def _to_string_tuple(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigurationError(
            f'tool.testsweet.discovery.{key} must be a list of strings'
        )
    for item in value:
        if not isinstance(item, str):
            raise ConfigurationError(
                f'tool.testsweet.discovery.{key} must be a list of strings'
            )
    return tuple(value)
