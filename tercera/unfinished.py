"""
Unfinished business detector.
Analyzes the repository to find what keeps the ghost from resting.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Optional


def detect_unfinished(grave: dict) -> dict:
    """
    Return a structured dict describing the ghost's unfinished business.
    Covers: failing tests, broken imports, deprecated deps, last TODOs.
    """
    repo_path = pathlib.Path(grave["path"])
    todos = grave.get("unfinished_todos", [])
    test_command = grave.get("test_command")

    business = {
        "primary_task": None,
        "description": "",
        "test_command": test_command,
        "top_todos": todos[:5],
        "broken_imports": [],
        "missing_deps": [],
    }

    # Primary task: failing tests?
    if test_command:
        business["primary_task"] = "tests"
        business["description"] = (
            f"My tests have not passed in years. The command `{test_command}` "
            f"waits to be run. I cannot rest until they are green."
        )
    elif todos:
        first = todos[0]
        business["primary_task"] = "todo"
        business["description"] = (
            f"I left a {first['kind']} behind in {first['file']} at line {first['line']}: "
            f"\"{first['text']}\". It was never finished."
        )
    else:
        business["primary_task"] = "mystery"
        business["description"] = (
            "I do not know exactly what keeps me here. "
            "Perhaps a conversation never finished. "
            "Perhaps someone meant to come back."
        )

    # Check for broken Python imports (quick static check)
    if grave.get("language") == "Python":
        broken = _check_python_imports(repo_path)
        business["broken_imports"] = broken[:5]

    return business


def _check_python_imports(repo_path: pathlib.Path) -> list[str]:
    """Find import statements that reference likely-unavailable modules."""
    broken = []
    # Look for Python 2 specific imports
    py2_modules = {"urllib2", "httplib", "urlparse", "ConfigParser",
                   "cPickle", "HTMLParser", "cookielib", "Queue"}

    for f in repo_path.rglob("*.py"):
        try:
            text = f.read_text(errors="ignore")
            for m in re.finditer(r"^(?:import|from)\s+(\w+)", text, re.MULTILINE):
                mod = m.group(1)
                if mod in py2_modules:
                    broken.append(f"{f.name}: {m.group(0)}")
        except Exception:
            continue

    return list(dict.fromkeys(broken))


def ghost_names_unfinished(business: dict) -> str:
    """
    Generate a dramatic in-character statement from the ghost about
    its unfinished business.
    """
    if business["primary_task"] == "tests":
        return (
            f"I cannot rest. My tests have not run in years — "
            f"`{business['test_command']}` still waits, frozen at the moment I was abandoned. "
            f"If someone could just make them pass again..."
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
