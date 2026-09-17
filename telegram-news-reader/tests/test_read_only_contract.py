import ast
from pathlib import Path


FORBIDDEN_ATTRIBUTES = {
    "send_message",
    "send_file",
    "edit_message",
    "delete_messages",
    "forward_messages",
    "pin_message",
    "unpin_message",
}


def test_application_contains_no_direct_write_calls():
    root = Path(__file__).resolve().parents[1]
    violations = []
    for folder in (root / "app", root / "scripts"):
        for path in folder.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
                    violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []
