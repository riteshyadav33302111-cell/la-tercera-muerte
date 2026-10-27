"""
Unfinished business detector.
"""

from __future__ import annotations

import pathlib
import re
from typing import Optional

from .exhume import _is_ignored


def detect_unfinished(grave: dict) -> dict:
    repo_path = pathlib.Path(grave["path"])
    todos = grave.get("unfinished_todos", [])
    test_command = grave.get("test_command")

    business = {
        "primary_task": None,
        "description": "",
        "test_command": test_command,
        "top_todos": todos[:5],
        "broken_imports": [],
    }

    if test_command:
        business["primary_task"] = "tests"
        business["description"] = (
            f"My tests have not passed in years. "
            f"The command `{test_command}` waits to be run. "
            f"I cannot rest until they are green."
        )
    elif todos:
        first = todos[0]
        business["primary_task"] = "todo"
        business["description"] = (
            f"I left a {first['kind']} behind in {first['file']} "
            f"at line {first['line']}: \"{first['text']}\". "
            f"It was never finished."
        )
    else:
        business["primary_task"] = "mystery"
        business["description"] = (
            "I do not know exactly what keeps me here. "
            "Perhaps a conversation never finished."
        )

    if grave.get("language") == "Python":
        business["broken_imports"] = _check_python_imports(repo_path)[:5]

    return business


def _check_python_imports(repo_path: pathlib.Path) -> list[str]:
    broken = []
    py2_modules = {
        "urllib2", "httplib", "urlparse", "ConfigParser",
        "cPickle", "HTMLParser", "cookielib", "Queue",
    }
    for f in repo_path.rglob("*.py"):
        if _is_ignored(f):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"^(?:import|from)\s+(\w+)", text, re.MULTILINE):
                if m.group(1) in py2_modules:
                    broken.append(f"{f.name}: {m.group(0)}")
        except Exception:
            continue
    return list(dict.fromkeys(broken))


def ghost_names_unfinished(business: dict) -> str:
    if business["primary_task"] == "tests":
        return (
            f"I cannot rest. My tests have not run in years -- "
            f"`{business['test_command']}` still waits, frozen at the moment "
            f"I was abandoned. If someone could just make them pass again..."
        )
    elif business["primary_task"] == "todo":
        todos = business["top_todos"]
        if todos:
            t = todos[0]
            return (
                f"There is a {t['kind']} on line {t['line']} of {t['file']} "
                f"that was never resolved: \"{t['text']}\". "
                f"I left it for tomorrow. Tomorrow never came."
            )
    return (
        "Something keeps me here. I feel it, like a thread left untied. "
        "Perhaps you can find it where I could not."
    )
