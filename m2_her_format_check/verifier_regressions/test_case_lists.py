"""Both published case lists must lead to the implementation they describe."""

import ast
import re
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["text", "stream", "compat"])
def test_bilingual_case_lists_cover_every_function(module):
    root = Path(__file__).resolve().parents[1]
    source = f"m2_her_{module}_tests.py"
    tree = ast.parse((root / source).read_text(encoding="utf-8"))
    functions = sorted(
        ("_".join(fn.name.split("_")[1:3]), fn.name, source, str(fn.lineno))
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_")
    )
    for suffix in ("", "_en"):
        page = root / "docs" / f"m2_her_{module}_cases{suffix}.md"
        references = re.findall(
            r"^\| (\d\d_\d\d) \| \[`(test_\w+)`\]\(\.\./(\w+\.py)#L(\d+)\)",
            page.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        assert sorted(references) == functions, page
