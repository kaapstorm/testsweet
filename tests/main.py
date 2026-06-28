import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from testsweet import params, test
from testsweet.__main__ import _supports_color, main


def _tty_env(**env_overrides):
    """Return a patch.dict context that acts like a TTY with a clean env."""
    clean = {k: v for k, v in os.environ.items()
             if k not in ('NO_COLOR', 'WT_SESSION', 'ANSICON')}
    clean.update(env_overrides)
    return patch.dict(os.environ, clean, clear=True)


@test
class SupportsColor:
    @params([
        # isatty, platform, version_info, env_overrides, expected
        (False, 'linux', (3, 11), {}, False),
        (True, 'linux', (3, 11), {'NO_COLOR': '1'}, False),
        (True, 'linux', (3, 11), {}, True),
        (True, 'win32', (3, 11), {}, False),
        (True, 'win32', (3, 12), {}, True),
        (True, 'win32', (3, 11), {'WT_SESSION': 'abc-123'}, True),
        (True, 'win32', (3, 11), {'ANSICON': '80x24'}, True),
    ])
    def reports_color_support(
        self, isatty, platform, version_info, env_overrides, expected,
    ):
        with (
            patch('sys.stdout') as m,
            patch('sys.platform', platform),
            patch('sys.version_info', version_info),
            _tty_env(**env_overrides),
        ):
            m.isatty.return_value = isatty
            assert _supports_color() is expected


@test
class MainCapturesOutput:
    def failing_test_output_is_replayed(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(['tests.fixtures.main.capture_demo'])
        text = buf.getvalue()
        assert rc == 1
        # The failing test's output is replayed under a capture section.
        assert 'Captured stdout' in text
        assert 'SECRET_FAIL_OUTPUT' in text

    def passing_test_output_is_suppressed(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(['tests.fixtures.main.capture_demo'])
        text = buf.getvalue()
        # The passing test printed, but its output must not leak.
        assert 'SECRET_PASS_OUTPUT' not in text
