"""Private v1 Python profile and a trusted input-only harness."""
import ast
import json

from .contracts import TaskSpec


CUSTOM_TASK = TaskSpec("custom-python-v1", "frozen-integer-cases-v1", ("solution.py",), 3)
MAX_VALUE = 1_000_000
MAX_EXPECTED = 1_000_000_000
MAX_CASES = 4


def validate_solution(source):
    """Only a single pure expression may see the current input."""
    try:
        if not 1 <= len(source.encode("utf-8")) <= 2000:
            raise ValueError
        tree = ast.parse(source)
        function, = tree.body
        if (type(function) is not ast.FunctionDef or function.name != "solve"
                or function.decorator_list or function.returns or function.type_params
                or ast.dump(function.args) != ast.dump(ast.parse("def solve(value): pass").body[0].args)):
            raise ValueError
        statement, = function.body
        if type(statement) is not ast.Return or statement.value is None:
            raise ValueError
        nodes = list(ast.walk(statement.value))
        allowed = (ast.IfExp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Load,
                   ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
                   ast.UAdd, ast.USub, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
        if len(nodes) > 80 or any(not isinstance(node, allowed) for node in nodes):
            raise ValueError
        for node in nodes:
            if isinstance(node, ast.Name) and node.id != "value":
                raise ValueError
            if isinstance(node, ast.Constant) and (type(node.value) is not int or abs(node.value) > MAX_VALUE):
                raise ValueError
    except (SyntaxError, ValueError, TypeError, RecursionError):
        raise ValueError("UNSUPPORTED_CUSTOM_PYTHON_PROFILE") from None


def build_custom_driver(inputs):
    if (type(inputs) is not list or not 1 <= len(inputs) <= MAX_CASES
            or any(type(value) is not int or abs(value) > MAX_VALUE for value in inputs)
            or len(set(inputs)) != len(inputs)):
        raise ValueError("INVALID_CUSTOM_INPUTS")
    # Only inputs enter the container. The independently supplied answers stay with the verifier.
    return (f"inputs = {inputs!r}\n" + '''import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from billing import solve

results = []
for value in inputs:
    try:
        result = solve(value)
        if type(result) is int and abs(result) <= 1000000000:
            results.append({"input": value, "actual": result, "error": None})
        else:
            results.append({"input": value, "actual": None, "error": "UNSUPPORTED_OUTPUT"})
    except Exception as error:
        results.append({"input": value, "actual": None, "error": type(error).__name__})
print(json.dumps(results))
''').encode("utf-8")


def parse_custom_observations(stdout, inputs):
    rows = json.loads(stdout)
    if type(rows) is not list or len(rows) != len(inputs):
        raise ValueError("INVALID_CUSTOM_EVIDENCE")
    for row, value in zip(rows, inputs):
        if (type(row) is not dict or set(row) != {"input", "actual", "error"}
                or type(row["input"]) is not int or row["input"] != value
                or not (type(row["actual"]) is int and abs(row["actual"]) <= MAX_EXPECTED and row["error"] is None
                        or row["actual"] is None and type(row["error"]) is str)):
            raise ValueError("INVALID_CUSTOM_EVIDENCE")
    return rows
