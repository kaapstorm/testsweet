import ast
from types import TracebackType


def explain_assertion(exc: AssertionError) -> str | None:
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

    assert_node = _find_assert(tree, lineno)
    if assert_node is None:
        return None

    lines = []
    seen: set[str] = set()
    for sub in _sub_exprs(assert_node.test):
        if isinstance(sub, ast.Constant):
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
            continue
        lines.append(f'  {src} = {value!r}')

    return '\n'.join(lines) if lines else None


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
