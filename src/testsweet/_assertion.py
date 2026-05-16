"""Best-effort source-level explanation of failed asserts.

Reads the source file referenced by the failing assertion's traceback,
locates the ``assert`` AST node, and re-evaluates its sub-expressions
in the original frame to show their values. ``Call`` sub-expressions
are deliberately skipped: re-evaluating a call would fire its side
effects a second time.

Failures (missing source, syntax errors, eval errors) silently yield
``None`` — the explainer is a nicety, not a correctness requirement.
"""
import ast
from types import FrameType, TracebackType


def assertion_source(exc: AssertionError) -> str | None:
    located = _locate_assert(exc)
    if located is None:
        return None
    _, _, assert_node = located
    return ast.unparse(assert_node)


def explain_assertion(exc: AssertionError) -> str | None:
    located = _locate_assert(exc)
    if located is None:
        return None
    frame, filename, assert_node = located

    lines = []
    seen: set[str] = set()
    for sub in _sub_exprs(assert_node.test):
        if isinstance(sub, (ast.Constant, ast.Call)):
            # Skip constants (no information) and calls (re-evaluating
            # would fire side effects a second time).
            continue
        src = ast.unparse(sub)
        if src in seen:
            continue
        seen.add(src)
        try:
            value = eval(
                compile(ast.Expression(sub), filename, 'eval'),
                frame.f_globals,
                frame.f_locals,
            )
        except Exception:
            # Sub-expression eval is best-effort; user code can raise
            # anything. Skip and move on.
            continue
        lines.append(f'  {src} = {value!r}')

    return '\n'.join(lines) if lines else None


def _locate_assert(
    exc: AssertionError,
) -> tuple[FrameType, str, ast.Assert] | None:
    tb = _innermost_tb(exc.__traceback__)
    if tb is None:
        return None
    frame = tb.tb_frame
    filename = frame.f_code.co_filename
    lineno = tb.tb_lineno
    try:
        with open(filename) as fh:
            tree = ast.parse(fh.read(), filename=filename)
    except (OSError, SyntaxError, ValueError):
        return None
    node = _find_assert(tree, lineno)
    if node is None:
        return None
    return frame, filename, node


def _innermost_tb(tb: TracebackType | None) -> TracebackType | None:
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb


def _find_assert(tree: ast.AST, lineno: int) -> ast.Assert | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and node.lineno == lineno:
            return node
    return None


def _sub_exprs(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.Compare):
        return [node.left, *node.comparators]
    if isinstance(node, ast.BoolOp):
        return node.values
    if isinstance(node, ast.UnaryOp):
        return [node.operand]
    if isinstance(node, ast.Call):
        return [node, *node.args, *(kw.value for kw in node.keywords)]
    return [node]
