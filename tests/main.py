import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from testsweet import test
from testsweet.__main__ import _supports_color, main


def _tty_env(**env_overrides):
    """Return a patch.dict context that acts like a TTY with a clean env."""
    clean = {k: v for k, v in os.environ.items()
             if k not in ('NO_COLOR', 'WT_SESSION', 'ANSICON')}
    clean.update(env_overrides)
    return patch.dict(os.environ, clean, clear=True)


@test
class SupportsColor:
    def not_a_tty_returns_false(self):
        with patch('sys.stdout') as m, _tty_env():
            m.isatty.return_value = False
            assert not _supports_color()

    def no_color_env_returns_false(self):
        with patch('sys.stdout') as m, _tty_env(NO_COLOR='1'):
            m.isatty.return_value = True
            assert not _supports_color()

    def non_windows_tty_returns_true(self):
        with (
            patch('sys.stdout') as m,
            patch('sys.platform', 'linux',),
            _tty_env()
        ):
            m.isatty.return_value = True
            assert _supports_color()

    def windows_old_python_no_extras_returns_false(self):
        with patch('sys.stdout') as m, \
             patch('sys.platform', 'win32'), \
             patch('sys.version_info', (3, 11)), \
             _tty_env():
            m.isatty.return_value = True
            assert not _supports_color()

    def windows_python_312_returns_true(self):
        with patch('sys.stdout') as m, \
             patch('sys.platform', 'win32'), \
             patch('sys.version_info', (3, 12)), \
             _tty_env():
            m.isatty.return_value = True
            assert _supports_color()

    def windows_wt_session_returns_true(self):
        with patch('sys.stdout') as m, \
             patch('sys.platform', 'win32'), \
             patch('sys.version_info', (3, 11)), \
             _tty_env(WT_SESSION='abc-123'):
            m.isatty.return_value = True
            assert _supports_color()

    def windows_ansicon_returns_true(self):
        with patch('sys.stdout') as m, \
             patch('sys.platform', 'win32'), \
             patch('sys.version_info', (3, 11)), \
             _tty_env(ANSICON='80x24'):
            m.isatty.return_value = True
            assert _supports_color()


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
