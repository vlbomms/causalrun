"""A deliberately small Python expression language for read-only receipt checks."""
import ast
from .contracts import Rejected, digest

ALLOWED = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.Compare, ast.Eq, ast.NotEq, ast.In, ast.NotIn,
    ast.Name, ast.Load, ast.Constant, ast.Subscript, ast.Call,
)
NAMES = {'action_id', 'payload', 'evidence', 'isinstance', 'dict', 'digest'}


def compile_verifier(source):
    if not isinstance(source, str) or len(source.encode()) > 8192:
        raise Rejected('Verifier source must be at most 8 KiB', 400)
    try:
        module = ast.parse(source)
    except SyntaxError:
        raise Rejected('Verifier source is not valid Python', 400) from None
    if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
        raise Rejected('Verifier must contain only def verify(action_id, payload, evidence)', 400)
    function = module.body[0]
    arguments = function.args
    if (function.name != 'verify' or function.decorator_list or function.returns
            or arguments.posonlyargs or arguments.vararg or arguments.kwarg
            or arguments.kwonlyargs or arguments.defaults
            or [item.arg for item in arguments.args] != ['action_id', 'payload', 'evidence']
            or any(item.annotation for item in arguments.args)
            or len(function.body) != 1 or not isinstance(function.body[0], ast.Return)):
        raise Rejected('Verifier must be one pure return expression with three arguments', 400)
    if function.body[0].value is None:
        raise Rejected('Verifier must return an expression', 400)
    expression = ast.Expression(body=function.body[0].value)
    nodes = list(ast.walk(expression))
    if len(nodes) > 256:
        raise Rejected('Verifier expression is too large', 400)
    for node in nodes:
        if not isinstance(node, ALLOWED):
            raise Rejected('Verifier forbids imports, attributes, assignments, loops, and arbitrary calls', 400)
        if isinstance(node, ast.Name) and node.id not in NAMES:
            raise Rejected('Verifier references an unsupported name', 400)
        if isinstance(node, ast.Constant) and not isinstance(node.value, (str, bool, type(None))):
            raise Rejected('Verifier supports only string, boolean, and null literals', 400)
        if isinstance(node, ast.Subscript) and not (
                isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
            raise Rejected('Verifier subscripts must use literal field names', 400)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise Rejected('Verifier calls must use the supported helpers', 400)
            if node.func.id == 'digest' and len(node.args) == 1:
                continue
            if (node.func.id == 'isinstance' and len(node.args) == 2
                    and isinstance(node.args[1], ast.Name) and node.args[1].id == 'dict'):
                continue
            raise Rejected('Only digest(value) and isinstance(value, dict) are permitted', 400)
    # This compiles only the whitelisted expression, never the supplied module.
    return compile(ast.fix_missing_locations(expression), '<approved-verifier>', 'eval')


def confirms(source, action_id, payload, evidence):
    expression = compile_verifier(source)
    try:
        answer = eval(expression, {'__builtins__': {}}, {
            'action_id': action_id, 'payload': payload, 'evidence': evidence,
            'isinstance': isinstance, 'dict': dict, 'digest': digest,
        })
        # Truthy objects are insufficient, and false never means non-execution.
        return answer is True
    except (KeyError, TypeError, ValueError):
        return False
