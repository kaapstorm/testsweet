import io

from testsweet import test
from testsweet._outcomes import (
    Errored,
    Failed,
    Passed,
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
Results = list[tuple[str, Outcome]]


def _capture(full_name, outcome):
    buf = io.StringIO()
    print_failure_detail(full_name, outcome, file=buf)
    return buf.getvalue()


@test
class FormatResultLine:
    def pass_outcome(self):
        assert format_result_line('mod.t', Passed()) == 'mod.t ... ok'

    def skipped_with_reason(self):
        line = format_result_line('mod.t', Skipped('not yet'))
        assert line == 'mod.t ... skipped: not yet'

    def skipped_without_reason(self):
        line = format_result_line('mod.t', Skipped())
        assert line == 'mod.t ... skipped'

    def xfailed_with_reason(self):
        line = format_result_line(
            'mod.t', XFailed(ValueError('boom'), 'see #42'),
        )
        assert line == 'mod.t ... xfailed: see #42'

    def xfailed_without_reason(self):
        line = format_result_line('mod.t', XFailed(ValueError('boom')))
        assert line == 'mod.t ... xfailed'

    def xpassed_with_reason(self):
        line = format_result_line('mod.t', XPassed('see #42'))
        assert line == 'mod.t ... XPASSED: see #42'

    def xpassed_without_reason(self):
        line = format_result_line('mod.t', XPassed())
        assert line == 'mod.t ... XPASSED'

    def failed_for_assertion_error(self):
        outcome = Failed(AssertionError('1 == 2'))
        line = format_result_line('mod.t', outcome)
        assert line == 'mod.t ... FAIL: AssertionError: 1 == 2'

    def errored_for_other_exception(self):
        outcome = Errored(TypeError("'int' object is not iterable"))
        line = format_result_line('mod.t', outcome)
        assert line == (
            "mod.t ... ERROR: TypeError: 'int' object is not iterable"
        )


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
class FormatResultLineColor:
    def pass_has_green_ok(self):
        line = format_result_line('mod.t', Passed(), use_color=True)
        assert '\x1b[32m' in line
        assert 'ok' in line

    def fail_has_red_status(self):
        line = format_result_line('mod.t', Failed(AssertionError('x')), use_color=True)
        assert '\x1b[' in line
        assert 'FAIL' in line

    def error_has_red_status(self):
        line = format_result_line('mod.t', Errored(TypeError('x')), use_color=True)
        assert '\x1b[' in line
        assert 'ERROR' in line

    def skipped_has_yellow_status(self):
        line = format_result_line('mod.t', Skipped(), use_color=True)
        assert '\x1b[33m' in line
        assert 'skipped' in line

    def xfailed_has_yellow_status(self):
        line = format_result_line('mod.t', XFailed(ValueError('x')), use_color=True)
        assert '\x1b[33m' in line
        assert 'xfailed' in line

    def xpassed_has_magenta_status(self):
        line = format_result_line('mod.t', XPassed(), use_color=True)
        assert '\x1b[' in line
        assert 'XPASSED' in line

    def no_color_by_default(self):
        line = format_result_line('mod.t', Passed())
        assert '\x1b[' not in line


@test
class SummarizeColor:
    def passed_count_is_green(self):
        result = summarize([('a', Passed())], use_color=True)
        assert '\x1b[32m' in result

    def failed_count_is_red(self):
        result = summarize([('a', Failed(AssertionError()))], use_color=True)
        assert '\x1b[1;31m' in result

    def no_color_by_default(self):
        result = summarize([('a', Passed())])
        assert '\x1b[' not in result


@test
class SummarizeTiming:
    def elapsed_appended_to_summary(self):
        results = [('a', Passed())]
        out = summarize(results, elapsed=1.5)
        assert out == '1 passed in 1.50s'

    def elapsed_zero(self):
        out = summarize([('a', Passed())], elapsed=0.0)
        assert out == '1 passed in 0.00s'

    def no_elapsed_omits_timing(self):
        out = summarize([('a', Passed())])
        assert 'in' not in out

    def elapsed_on_empty_results(self):
        out = summarize([], elapsed=0.5)
        assert out == '0 tests in 0.50s'


@test
class Summarize:
    def empty_results(self):
        assert summarize([]) == '0 tests'

    def all_passes(self):
        results = [('a', Passed()), ('b', Passed())]
        assert summarize(results) == '2 passed'

    def mixed_outcomes(self):
        results: Results = [
            ('p1', Passed()),
            ('p2', Passed()),
            ('f1', Failed(AssertionError('x'))),
            ('e1', Errored(TypeError('y'))),
            ('s1', Skipped('later')),
            ('xf1', XFailed(ValueError('z'))),
            ('xp1', XPassed()),
        ]
        assert summarize(results) == (
            '2 passed, 1 failed, 1 error, '
            '1 skipped, 1 xfailed, 1 xpassed'
        )

    def zero_categories_omitted(self):
        results = [('s1', Skipped()), ('s2', Skipped())]
        assert summarize(results) == '2 skipped'

    def category_order_is_stable(self):
        # Insertion order in `results` doesn't matter — summarize
        # always emits passed → failed → error → skipped → xfailed
        # → xpassed.
        results: Results = [
            ('xp1', XPassed()),
            ('p1', Passed()),
            ('s1', Skipped()),
            ('f1', Failed(AssertionError())),
        ]
        assert summarize(results) == (
            '1 passed, 1 failed, 1 skipped, 1 xpassed'
        )
