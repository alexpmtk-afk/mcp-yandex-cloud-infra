import ast
from pathlib import Path


def test_public_http_api_has_no_telegram_write_routes():
    path = Path(__file__).resolve().parents[1] / "app" / "service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = {"post", "put", "patch", "delete"}
    allowed_local_admin_writes = {"admin_whitelist", "manage_whitelist_legacy"}
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in forbidden and node.name not in allowed_local_admin_writes:
                    violations.append((node.name, decorator.func.attr))
    assert violations == []
