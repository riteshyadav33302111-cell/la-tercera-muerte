"""
Resurrection agent: runs inside a Docker sandbox and tries to fix the
ghost's unfinished business using the coder LLM.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Optional

from .llm import coder_chat
from .memory import retrieve


MAX_ATTEMPTS = 5
SANDBOX_TIMEOUT = 300  # seconds


def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def _build_sandbox_image(repo_path: pathlib.Path, language: str) -> str:
    """Build a Docker image for the given language."""
    base_images = {
        "Python": "python:3.11-slim",
        "JavaScript": "node:20-slim",
        "TypeScript": "node:20-slim",
        "Ruby": "ruby:3.2-slim",
        "Go": "golang:1.21-alpine",
        "Java": "eclipse-temurin:17-jdk-slim",
        "Rust": "rust:1.73-slim",
    }
    base = base_images.get(language, "ubuntu:22.04")

    dockerfile = f"""FROM {base}
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt 2>/dev/null || npm install 2>/dev/null || bundle install 2>/dev/null || true
"""
    sandbox_dir = repo_path / ".tercera" / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    (sandbox_dir / "Dockerfile").write_text(dockerfile)

    # Copy repo into sandbox
    sandbox_app = sandbox_dir / "app"
    if sandbox_app.exists():
        shutil.rmtree(sandbox_app)
    shutil.copytree(
        repo_path,
        sandbox_app,
        ignore=shutil.ignore_patterns(".tercera", ".git", "__pycache__", "*.pyc"),
    )

    image_name = f"tercera-sandbox-{repo_path.name.lower()[:20]}"
    subprocess.run(
        ["docker", "build", "-t", image_name, "."],
        cwd=str(sandbox_dir),
        capture_output=True,
        timeout=120,
    )
    return image_name


def _run_in_container(image: str, command: str, timeout: int = 60) -> dict:
    """Run a command in a Docker container and return {ok, stdout, stderr}."""
    result = subprocess.run(
        ["docker", "run", "--rm", "--network=none",
         "--memory=512m", "--cpus=1",
         image, "sh", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
        "returncode": result.returncode,
    }


def _run_locally(repo_path: pathlib.Path, command: str, timeout: int = 60) -> dict:
    """Fallback: run command locally (less safe but works without Docker)."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(repo_path),
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
        "returncode": result.returncode,
    }


def _apply_diff(repo_path: pathlib.Path, diff_text: str) -> bool:
    """Apply a unified diff to the repo."""
    patch_file = repo_path / ".tercera" / "repair.patch"
    patch_file.write_text(diff_text, encoding="utf-8")
    result = subprocess.run(
        ["git", "apply", "--ignore-whitespace", str(patch_file)],
        cwd=str(repo_path),
        capture_output=True,
    )
    return result.returncode == 0


def _extract_diff(text: str) -> str:
    """Extract a unified diff from LLM output."""
    import re
    # Look for ```diff ... ``` blocks
    m = re.search(r"```diff\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Look for raw diff
    m = re.search(r"(--- .+\n\+\+\+ .+\n(?:[@\-\+ ].+\n?)+)", text, re.DOTALL)
    if m:
        return m.group(1)
    return ""


def resurrect(grave: dict, progress_cb=None) -> dict:
    """
    The resurrection ritual: attempt to fix the ghost's unfinished business.

    Returns {
        "success": bool,
        "message": str,
        "attempts": int,
        "final_output": str,
        "patches": list[str],
    }
    """
    repo_path = pathlib.Path(grave["path"])
    language = grave.get("language", "Unknown")
    test_cmd = grave.get("test_command")
    todos = grave.get("unfinished_todos", [])

    use_docker = _docker_available()

    if not test_cmd and not todos:
        return {
            "success": False,
            "message": "🕯️ No unfinished business detected. The spirit may already be at peace.",
            "attempts": 0,
            "final_output": "",
            "patches": [],
        }

    # Determine what to fix
    if test_cmd:
        task_desc = f"Make the test suite pass. Run: {test_cmd}"
        fix_command = test_cmd
    else:
        t = todos[0]
        task_desc = f"Resolve the {t['kind']} comment on line {t['line']} of {t['file']}: \"{t['text']}\""
        fix_command = test_cmd or "echo 'No test command'"

    if progress_cb:
        progress_cb(0, MAX_ATTEMPTS, f"Starting resurrection ({'Docker' if use_docker else 'local'})...")

    # Build sandbox
    working_dir = repo_path
    image = None
    if use_docker:
        try:
            image = _build_sandbox_image(repo_path, language)
            working_dir = repo_path / ".tercera" / "sandbox" / "app"
        except Exception:
            use_docker = False

    patches = []
    last_output = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if progress_cb:
            progress_cb(attempt, MAX_ATTEMPTS, f"Attempt {attempt}/{MAX_ATTEMPTS}...")

        # Run tests
        try:
            if use_docker and image:
                result = _run_in_container(image, fix_command)
            else:
                result = _run_locally(working_dir, fix_command)
        except subprocess.TimeoutExpired:
            result = {"ok": False, "stdout": "", "stderr": "Timeout", "returncode": -1}

        last_output = result["stdout"] + "\n" + result["stderr"]

        if result["ok"]:
            return {
                "success": True,
                "message": f"🕯️ The spirit is at peace. Tests passed on attempt {attempt}.",
                "attempts": attempt,
                "final_output": last_output,
                "patches": patches,
            }

        # Ask the coder LLM for a fix
        relevant = retrieve(result["stderr"][:500], grave, top_k=3)
        context_code = "\n\n".join(
            f"// {c['file']}:{c['start_line']}\n{c['text']}" for c in relevant
        ) if relevant else "No relevant code retrieved."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a code repair assistant. Your goal is to fix the failing code. "
                    "Return ONLY a unified diff (```diff ... ```) that can be applied with `git apply`. "
                    "Make minimal changes. Do not explain."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: {task_desc}\n\n"
                    f"Error output (attempt {attempt}):\n{result['stderr'][-2000:]}\n\n"
                    f"Relevant code:\n{context_code}\n\n"
                    f"Return a unified diff to fix this error."
                ),
            },
        ]

        try:
            llm_response = coder_chat(messages)
            diff_text = _extract_diff(llm_response)
            if diff_text:
                applied = _apply_diff(working_dir, diff_text)
                if applied:
                    patches.append(diff_text)
        except Exception as e:
            if progress_cb:
                progress_cb(attempt, MAX_ATTEMPTS, f"LLM error: {e}")

        time.sleep(1)

    return {
        "success": False,
        "message": f"👻 The spirit remains restless after {MAX_ATTEMPTS} attempts.",
        "attempts": MAX_ATTEMPTS,
        "final_output": last_output,
        "patches": patches,
    }
