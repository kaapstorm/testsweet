import io

from testsweet import params, test
from testsweet._outcomes import (
    Errored,
    Failed,
    Passed,
    Result,
    Skipped,
    XFailed,
    XPassed,
)
from testsweet._report import (
    format_result_line,
    print_failure_detail,
    summarize,
)

Outcome = Passed | Failed | Errored | Skipped | XFailed | XPassed
Results = list[Result]


def _capture(full_name, outcome):
    buf = io.StringIO()
    print_failure_detail(full_name, outcome, file=buf)
    return buf.getvalue()


def _capture_io(full_name, outcome, stdout='', stderr=''):
    buf = io.StringIO()
    print_failure_detail(
        full_name, outcome, stdout=stdout, stderr=stderr, file=buf,
    )
    return buf.getvalue()


@test
class FormatResultLine:
    @params([
        (Passed(), 'mod.t ... ok'),
        (Skipped('not yet'), 'mod.t ... skipped: not yet'),
        (Skipped(), 'mod.t ... skipped'),
        (XFailed(ValueError('boom'), 'see #42'), 'mod.t ... xfailed: see #42'),
        (XFailed(ValueError('boom')), 'mod.t ... xfailed'),
        (XPassed('see #42'), 'mod.t ... XPASSED: see #42'),
        (XPassed(), 'mod.t ... XPASSED'),
        (
            Failed(AssertionError('1 == 2')),
            'mod.t ... FAIL: AssertionError: 1 == 2',
        ),
        (
            Errored(TypeError("'int' object is not iterable")),
            "mod.t ... ERROR: TypeError: 'int' object is not iterable",
        ),
    ])
    def formats_outcome(self, outcome, expected):
        assert format_result_line('mod.t', outcome) == expected


@test
class PrintFailureDetail:
    def passed_emits_nothing(self):
        assert _capture('mod.t', Passed()) == ''

    def skipped_emits_nothing(self):
        assert _capture('mod.t', Skipped('reason')) == ''

    def xfailed_emits_nothing(self):
        assert _capture('mod.t', XFailed(ValueError('x'), 'r')) == ''

    def xpassed_emits_marker_message(self):
        out = _capture('mod.t', XPassed('see #42'))
        assert 'XPASSED' in out
        assert 'mod.t' in out
        assert '@xfail' in out
        assert 'remove the marker' in out

    def xpassed_does_not_emit_traceback(self):
        out = _capture('mod.t', XPassed())
        assert 'Traceback' not in out

    def failed_emits_traceback_block(self):
        try:
            assert 1 == 2
        except AssertionError as exc:
            out = _capture('mod.t', Failed(exc))
        assert 'FAIL: mod.t' in out
        assert 'AssertionError' in out

    def errored_emits_error_block(self):
        try:
            raise TypeError('nope')
        except TypeError as exc:
            out = _capture('mod.t', Errored(exc))
        assert 'ERROR: mod.t' in out
        assert 'TypeError' in out


@test
class PrintFailureDetailCaptured:
    def failed_shows_captured_stdout(self):
        try:
            assert 1 == 2
        except AssertionError as exc:
            out = _capture_io('mod.t', Failed(exc), stdout='hello\n')
        assert 'Captured stdout' in out
        assert 'hello' in out

    def failed_shows_captured_stderr(self):
        try:
            assert 1 == 2
        except AssertionError as exc:
            out = _capture_io('mod.t', Failed(exc), stderr='boom\n')
        assert 'Captured stderr' in out
        assert 'boom' in out

    def errored_shows_captured_output(self):
        try:
            raise TypeError('nope')
        except TypeError as exc:
            out = _capture_io('mod.t', Errored(exc), stdout='trace me\n')
        assert 'Captured stdout' in out
        assert 'trace me' in out

    def empty_capture_emits_no_section(self):
        try:
            assert 1 == 2
        except AssertionError as exc:
            out = _capture_io('mod.t', Failed(exc))
        assert 'Captured stdout' not in out
        assert 'Captured stderr' not in out

    def xpassed_shows_captured_output(self):
        out = _capture_io('mod.t', XPassed('see #42'), stdout='ran anyway\n')
        assert 'Captured stdout' in out
        assert 'ran anyway' in out


@test
class FormatResultLineColor:
    @params([
        (Passed(), '\x1b[32m', 'ok'),
        (Failed(AssertionError('x')), '\x1b[', 'FAIL'),
        (Errored(TypeError('x')), '\x1b[', 'ERROR'),
        (Skipped(), '\x1b[33m', 'skipped'),
        (XFailed(ValueError('x')), '\x1b[33m', 'xfailed'),
        (XPassed(), '\x1b[', 'XPASSED'),
    ])
    def colors_status(self, outcome, color_code, status):
        line = format_result_line('mod.t', outcome, use_color=True)
        assert color_code in line
        assert status in line

    def no_color_by_default(self):
        line = format_result_line('mod.t', Passed())
        assert '\x1b[' not in line


@test
class SummarizeColor:
    def passed_count_is_green(self):
        result = summarize([Result('a', Passed())], use_color=True)
        assert '\x1b[32m' in result

    def failed_count_is_red(self):
        result = summarize(
            [Result('a', Failed(AssertionError()))],
            use_color=True,
        )
        assert '\x1b[1;31m' in result

    def no_color_by_default(self):
        result = summarize([Result('a', Passed())])
        assert '\x1b[' not in result


@test
class SummarizeTiming:
    @params([
        ([Result('a', Passed())], 1.5, '1 passed in 1.50s'),
        ([Result('a', Passed())], 0.0, '1 passed in 0.00s'),
        ([Result('a', Passed())], None, '1 passed'),
        ([], 0.5, '0 tests in 0.50s'),
    ])
    def renders_elapsed(self, results, elapsed, expected):
        assert summarize(results, elapsed=elapsed) == expected


@test
class Summarize:
    def empty_results(self):
        assert summarize([]) == '0 tests'

    def all_passes(self):
        results = [Result('a', Passed()), Result('b', Passed())]
        assert summarize(results) == '2 passed'

    def mixed_outcomes(self):
        results: Results = [
            Result('p1', Passed()),
            Result('p2', Passed()),
            Result('f1', Failed(AssertionError('x'))),
            Result('e1', Errored(TypeError('y'))),
            Result('s1', Skipped('later')),
            Result('xf1', XFailed(ValueError('z'))),
            Result('xp1', XPassed()),
        ]
        assert summarize(results) == (
            '2 passed, 1 failed, 1 error, '
            '1 skipped, 1 xfailed, 1 xpassed'
        )

    def zero_categories_omitted(self):
        results = [Result('s1', Skipped()), Result('s2', Skipped())]
        assert summarize(results) == '2 skipped'

    def category_order_is_stable(self):
        # Insertion order in `results` doesn't matter — summarize
        # always emits passed → failed → error → skipped → xfailed
        # → xpassed.
        results: Results = [
            Result('xp1', XPassed()),
            Result('p1', Passed()),
            Result('s1', Skipped()),
            Result('f1', Failed(AssertionError())),
        ]
        assert summarize(results) == (
            '1 passed, 1 failed, 1 skipped, 1 xpassed'
        )
