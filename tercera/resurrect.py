"""
Resurrection agent.

Phase 5 fixes:
- COPY app/ .  in Dockerfile (build context puts repo under sandbox/app/)
- Deps + pytest installed in image; tests run via bind-mount so patches take
  effect each attempt without rebuilding the image
- docker build return code checked; raises on failure
- Both stdout and stderr sent to the coder model
- No test command -> never report success; return "patch proposed, no tests"
- --unsafe-local is opt-in only, runs on a temp copy, never the real repo
- When diff fails to apply, ask coder for the full corrected file content
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Optional


MAX_ATTEMPTS = 5
SANDBOX_TIMEOUT = 300


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def _docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _write_dockerfile(sandbox_dir: pathlib.Path, language: str) -> None:
    """Write a Dockerfile that installs deps + pytest, but does NOT bake code."""
    base_images = {
        "Python":     "python:3.11-slim",
        "JavaScript": "node:20-slim",
        "TypeScript": "node:20-slim",
        "Ruby":       "ruby:3.2-slim",
        "Go":         "golang:1.21-alpine",
        "Java":       "eclipse-temurin:17-jdk-slim",
        "Rust":       "rust:1.73-slim",
    }
    base = base_images.get(language, "python:3.11-slim")

    if language == "Python":
        install_block = (
            "COPY app/ .\n"
            "RUN pip install pytest 2>/dev/null || true\n"
            "RUN pip install -r requirements.txt 2>/dev/null "
            "|| pip install -e . 2>/dev/null || true"
        )
    elif language in ("JavaScript", "TypeScript"):
        install_block = "COPY app/ .\nRUN npm install 2>/dev/null || true"
    elif language == "Ruby":
        install_block = "COPY app/ .\nRUN bundle install 2>/dev/null || true"
    else:
        install_block = "COPY app/ .\n"

    dockerfile = f"FROM {base}\nWORKDIR /app\n{install_block}\n"
    (sandbox_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")


def _build_image(sandbox_dir: pathlib.Path, image_name: str) -> None:
    """Build Docker image. Raises RuntimeError if build fails."""
    result = subprocess.run(
        ["docker", "build", "-t", image_name, "."],
        cwd=str(sandbox_dir),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Docker build failed (exit {result.returncode}):\n"
            f"{result.stderr[-2000:]}"
        )


def _run_with_mount(
    image: str,
    app_dir: pathlib.Path,
    command: str,
    timeout: int = 120,
) -> dict:
    """
    Run tests via bind-mount so patches on disk take effect immediately
    without rebuilding the image.
    """
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network=none",
            "--memory=512m", "--cpus=1",
            "-v", f"{app_dir}:/app",
            "-w", "/app",
            image,
            "sh", "-c", command,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    combined = (result.stdout + "\n" + result.stderr).strip()
    return {
        "ok": result.returncode == 0,
        "output": combined[-6000:],
        "returncode": result.returncode,
    }


# ---------------------------------------------------------------------------
# Local (unsafe) helpers
# ---------------------------------------------------------------------------

def _run_locally(work_dir: pathlib.Path, command: str, timeout: int = 120) -> dict:
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True,
        timeout=timeout, cwd=str(work_dir),
    )
    combined = (result.stdout + "\n" + result.stderr).strip()
    return {
        "ok": result.returncode == 0,
        "output": combined[-6000:],
        "returncode": result.returncode,
    }


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------

def _apply_diff(work_dir: pathlib.Path, diff_text: str) -> bool:
    patch_file = work_dir / ".tercera_patch.diff"
    patch_file.write_text(diff_text, encoding="utf-8")
    result = subprocess.run(
        ["git", "apply", "--ignore-whitespace", str(patch_file)],
        cwd=str(work_dir),
        capture_output=True,
    )
    patch_file.unlink(missing_ok=True)
    return result.returncode == 0


def _extract_diff(text: str) -> str:
    m = re.search(r"```diff\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r"(--- .+\n\+\+\+ .+\n(?:[@\-\+ ].+\n?)+)", text, re.DOTALL)
    if m:
        return m.group(1)
    return ""


def _extract_file_block(text: str) -> tuple[str, str]:
    """
    Extract a full-file replacement when the LLM returns:
        FILE: path/to/file.py
        ```python
        ...content...
        ```
    Returns (filepath, content) or ("", "").
    """
    fm = re.search(r"FILE:\s*([^\n]+)\n", text)
    cm = re.search(r"```[a-z]*\n(.*?)```", text, re.DOTALL)
    if fm and cm:
        return fm.group(1).strip(), cm.group(1)
    return "", ""


def _apply_full_file(work_dir: pathlib.Path, filepath: str, content: str) -> bool:
    target = work_dir / filepath
    if not target.exists():
        return False
    try:
        target.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _ask_coder_for_fix(
    task_desc: str,
    error_output: str,
    context_code: str,
    attempt: int,
    prefer_full_file: bool = False,
) -> str:
    from .llm import coder_chat

    if prefer_full_file:
        fmt_instruction = (
            "Return the full corrected content of the affected file using this format:\n"
            "FILE: path/to/file.py\n"
            "```python\n"
            "<full corrected file content>\n"
            "```\n"
            "If multiple files need changing, return one file at a time."
        )
    else:
        fmt_instruction = (
            "Return ONLY a unified diff (```diff ... ```) applicable with `git apply`. "
            "Make minimal changes. Do not explain."
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a code repair assistant. Fix the failing code. "
                + fmt_instruction
            ),
        },
        {
            "role": "user",
            "content": (
                f"Task: {task_desc}\n\n"
                f"Error output (attempt {attempt}):\n{error_output[-3000:]}\n\n"
                f"Relevant code:\n{context_code}\n\n"
            ),
        },
    ]
    return coder_chat(messages)


# ---------------------------------------------------------------------------
# Main resurrection entry point
# ---------------------------------------------------------------------------

def resurrect(
    grave: dict,
    attempts: int = MAX_ATTEMPTS,
    no_docker: bool = False,
    max_attempts: Optional[int] = None,
    use_docker: Optional[bool] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    Attempt to fix the ghost's unfinished business.

    Returns {success, message, attempts, final_output, patches}
    """
    if max_attempts is not None:
        attempts = max_attempts
    if use_docker is not None:
        no_docker = not use_docker
    use_docker_effective = not no_docker

    from .memory import retrieve

    repo_path = pathlib.Path(grave["path"])
    language = grave.get("language", "Unknown")
    test_cmd = grave.get("test_command")
    todos = grave.get("unfinished_todos", [])

    # No test command -> can't verify, never claim success
    if not test_cmd and not todos:
        return {
            "success": False,
            "message": "No unfinished business detected. The spirit may already be at peace.",
            "attempts": 0,
            "final_output": "",
            "patches": [],
        }

    task_desc = (
        f"Make the test suite pass. Run: {test_cmd}"
        if test_cmd else
        f"Resolve {todos[0]['kind']} in {todos[0]['file']}:{todos[0]['line']}: "
        f"\"{todos[0]['text']}\""
    )

    if progress_cb:
        progress_cb(0, attempts, "Preparing...")

    patches: list[str] = []
    last_output = ""

    # ── Docker path ────────────────────────────────────────────────────────
    if use_docker_effective and _docker_available() and test_cmd:
        sandbox_dir = repo_path / ".tercera" / "sandbox"
        app_dir = sandbox_dir / "app"

        # Fresh copy of repo into sandbox/app/
        if app_dir.exists():
            shutil.rmtree(app_dir)
        shutil.copytree(
            repo_path, app_dir,
            ignore=shutil.ignore_patterns(".tercera", ".git", "__pycache__", "*.pyc"),
        )

        image_name = f"tercera-{repo_path.name.lower()[:20]}"
        _write_dockerfile(sandbox_dir, language)

        try:
            if progress_cb:
                progress_cb(0, attempts, "Building Docker image...")
            _build_image(sandbox_dir, image_name)
        except RuntimeError as e:
            return {
                "success": False,
                "message": f"Docker build failed: {e}",
                "attempts": 0,
                "final_output": str(e),
                "patches": [],
            }

        for attempt in range(1, attempts + 1):
            if progress_cb:
                progress_cb(attempt, attempts, f"Docker attempt {attempt}/{attempts}...")

            try:
                result = _run_with_mount(image_name, app_dir, test_cmd)
            except subprocess.TimeoutExpired:
                result = {"ok": False, "output": "Timeout", "returncode": -1}

            last_output = result["output"]

            if result["ok"]:
                return {
                    "success": True,
                    "message": f"The spirit is at peace. Tests passed on attempt {attempt}.",
                    "attempts": attempt,
                    "final_output": last_output,
                    "patches": patches,
                }

            # Ask coder LLM for a fix
            try:
                memories = retrieve(result["output"][:500], grave, top_k=3)
                context_code = "\n\n".join(
                    f"// {c['file']}:{c.get('start_line','?')}\n{c['text'][:400]}"
                    for c in memories
                ) if memories else "(no relevant code retrieved)"

                llm_resp = _ask_coder_for_fix(
                    task_desc, last_output, context_code, attempt
                )
                diff_text = _extract_diff(llm_resp)

                if diff_text and _apply_diff(app_dir, diff_text):
                    patches.append(diff_text)
                else:
                    # Diff failed — ask for full file replacement
                    llm_resp2 = _ask_coder_for_fix(
                        task_desc, last_output, context_code,
                        attempt, prefer_full_file=True,
                    )
                    fp, fc = _extract_file_block(llm_resp2)
                    if fp and fc and _apply_full_file(app_dir, fp, fc):
                        patches.append(f"# full-file replacement: {fp}")
            except Exception:
                pass

            time.sleep(1)

        if not test_cmd:
            return {
                "success": False,
                "message": "Patch proposed, no tests to verify.",
                "attempts": attempts,
                "final_output": last_output,
                "patches": patches,
            }

        return {
            "success": False,
            "message": f"The spirit remains restless after {attempts} attempts.",
            "attempts": attempts,
            "final_output": last_output,
            "patches": patches,
        }

    # ── Unsafe local path (opt-in only, works on a temp copy) ─────────────
    if not use_docker_effective:
        with tempfile.TemporaryDirectory(prefix="tercera_local_") as tmp:
            work_dir = pathlib.Path(tmp) / "repo"
            shutil.copytree(
                repo_path, work_dir,
                ignore=shutil.ignore_patterns(".tercera", ".git", "__pycache__"),
            )

            if not test_cmd:
                return {
                    "success": False,
                    "message": "Patch proposed, no tests to verify.",
                    "attempts": 0,
                    "final_output": "",
                    "patches": [],
                }

            for attempt in range(1, attempts + 1):
                if progress_cb:
                    progress_cb(attempt, attempts, f"Local attempt {attempt}/{attempts}...")

                try:
                    result = _run_locally(work_dir, test_cmd)
                except subprocess.TimeoutExpired:
                    result = {"ok": False, "output": "Timeout", "returncode": -1}

                last_output = result["output"]

                if result["ok"]:
                    return {
                        "success": True,
                        "message": f"Tests passed locally on attempt {attempt}.",
                        "attempts": attempt,
                        "final_output": last_output,
                        "patches": patches,
                    }

                try:
                    memories = retrieve(result["output"][:500], grave, top_k=3)
                    context_code = "\n\n".join(
                        f"// {c['file']}:{c.get('start_line','?')}\n{c['text'][:400]}"
                        for c in memories
                    ) if memories else ""

                    llm_resp = _ask_coder_for_fix(
                        task_desc, last_output, context_code, attempt
                    )
                    diff_text = _extract_diff(llm_resp)

                    if diff_text and _apply_diff(work_dir, diff_text):
                        patches.append(diff_text)
                    else:
                        llm_resp2 = _ask_coder_for_fix(
                            task_desc, last_output, context_code,
                            attempt, prefer_full_file=True,
                        )
                        fp, fc = _extract_file_block(llm_resp2)
                        if fp and fc and _apply_full_file(work_dir, fp, fc):
                            patches.append(f"# full-file: {fp}")
                except Exception:
                    pass

                time.sleep(1)

    return {
        "success": False,
        "message": (
            "Docker is unavailable and --unsafe-local was not requested. "
            "Install Docker or pass --unsafe-local to run locally."
            if use_docker_effective else
            f"The spirit remains restless after {attempts} attempts."
        ),
        "attempts": attempts,
        "final_output": last_output,
        "patches": patches,
    }
