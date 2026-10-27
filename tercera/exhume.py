"""
Exhumation: reads a git repository and extracts everything the ghost needs.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Optional

import git


# ---------------------------------------------------------------------------
# Shared ignore set used by every rglob in this project
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    ".git", "node_modules", ".tercera", "venv", ".venv",
    "__pycache__", "dist", "build", ".tox", ".eggs",
}


def _is_ignored(path: pathlib.Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


# ---------------------------------------------------------------------------
# Manifest / CI files used for cause-of-death detection
# ---------------------------------------------------------------------------

_MANIFEST_NAMES = {
    "setup.py", "setup.cfg", "pyproject.toml",
    "requirements.txt", "requirements-dev.txt",
    "package.json", "package-lock.json",
    "bower.json",
    "Gruntfile.js", "Gruntfile.coffee",
    ".travis.yml", ".circleci/config.yml",
    "Gemfile", "Gemfile.lock",
    "Makefile", "tox.ini",
}

DEATH_CAUSES = [
    (re.compile(r"python_requires\s*=.*?['\"]2\.", re.I),
     "Succumbed to Python 2 end-of-life (January 1, 2020)"),
    (re.compile(r"Programming Language.*Python.*::\s*2\.", re.I),
     "Classified under Python 2 — a lineage that ceased support in 2020"),
    (re.compile(r"travis-ci\.org", re.I),
     "Its heartbeat monitor (Travis CI) went silent"),
    (re.compile(r"circleci\.com.*v1", re.I),
     "Its pipeline crumbled when CircleCI deprecated v1"),
    (re.compile(r"bower", re.I),
     "Nourished by Bower, a dependency manager that itself died"),
    (re.compile(r"grunt", re.I),
     "Animated by Grunt, now a relic of another era"),
    (re.compile(r"coffeescript", re.I),
     "Dreamt in CoffeeScript, a language that passed quietly"),
    (re.compile(r"left-pad", re.I),
     "Starved when left-pad vanished from npm (March 2016)"),
    (re.compile(r"""node['"]\s*:\s*['"]0\.\d""", re.I),
     "Required Node.js 0.x — a version that departed long ago"),
    (re.compile(r"""ruby['"]\s*:\s*['"]1\.[89]""", re.I),
     "Breathed on Ruby 1.x, an unsupported branch"),
    (re.compile(r"flash", re.I),
     "Built for Adobe Flash — extinguished December 31, 2020"),
]

LONE_MAINTAINER_THRESHOLD = 0.88


def _detect_cause_of_death(
    repo_path: pathlib.Path, authors: list[tuple[str, int]]
) -> str:
    """Check only manifest/CI files for known death-cause patterns."""
    for f in repo_path.rglob("*"):
        if _is_ignored(f):
            continue
        if f.is_file() and f.name in _MANIFEST_NAMES:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                for pattern, cause in DEATH_CAUSES:
                    if pattern.search(text):
                        return cause
            except Exception:
                continue

    if authors:
        total = sum(c for _, c in authors)
        top_pct = authors[0][1] / total if total else 0
        if top_pct >= LONE_MAINTAINER_THRESHOLD:
            return (
                f"Its keeper ({authors[0][0]}) walked away, "
                "and no one else knew the way"
            )

    return "Cause unknown — some ghosts keep their secrets"


def _detect_language(repo_path: pathlib.Path) -> str:
    ext_count: dict[str, int] = collections.Counter()
    for f in repo_path.rglob("*"):
        if _is_ignored(f):
            continue
        if f.is_file() and f.suffix:
            ext_count[f.suffix.lower()] += 1

    lang_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".rb": "Ruby", ".go": "Go", ".java": "Java", ".rs": "Rust",
        ".c": "C", ".cpp": "C++", ".cs": "C#", ".php": "PHP",
        ".swift": "Swift", ".kt": "Kotlin", ".ex": "Elixir",
        ".clj": "Clojure", ".hs": "Haskell", ".ml": "OCaml",
    }
    for ext, _ in ext_count.most_common(10):
        if ext in lang_map:
            return lang_map[ext]
    return "Unknown"


def _extract_todos(repo_path: pathlib.Path) -> list[dict]:
    """Find TODO/FIXME/HACK/XXX comments (case-sensitive, word-boundary)."""
    todos = []
    source_exts = {
        ".py", ".js", ".ts", ".rb", ".go", ".java", ".rs",
        ".c", ".cpp", ".cs", ".php", ".swift", ".kt",
    }
    _pat = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b\s*:?\s*(.*)")

    for f in repo_path.rglob("*"):
        if _is_ignored(f):
            continue
        if not (f.is_file() and f.suffix.lower() in source_exts):
            continue
        try:
            for i, line in enumerate(
                f.read_text(encoding="utf-8", errors="ignore").splitlines()
            ):
                m = _pat.search(line)
                if m:
                    todos.append({
                        "file": str(f.relative_to(repo_path)),
                        "line": i + 1,
                        "kind": m.group(1),
                        "text": m.group(2).strip()[:200],
                    })
        except Exception:
            continue

    return todos[:60]


def _extract_dependencies(repo_path: pathlib.Path) -> list[str]:
    """Parse requirements.txt, setup.py, package.json, and Gemfile."""
    deps: list[str] = []

    # Python requirements.txt (highest priority — most explicit)
    for req_file in ["requirements.txt", "requirements-dev.txt"]:
        p = repo_path / req_file
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    m = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
                    if m:
                        deps.append(m.group(1))
            if deps:
                return list(dict.fromkeys(deps))[:50]

    # Python setup.py — try two patterns:
    #   1. install_requires=['pkg1', 'pkg2']  (literal list)
    #   2. var = ['pkg1']; install_requires=var  (variable reference)
    setup_py = repo_path / "setup.py"
    if setup_py.exists():
        text = setup_py.read_text(encoding="utf-8", errors="ignore")
        # Pattern 1: literal list inline
        m1 = re.search(r"install_requires\s*=\s*\[([^\]]*)\]", text, re.DOTALL)
        if m1:
            deps += re.findall(r"['\"]([A-Za-z0-9_\-\.]+)['\"]", m1.group(1))
        else:
            # Pattern 2: variable reference  (e.g. required = ['x']; install_requires=required)
            var_m = re.search(r"([a-zA-Z_]\w*)\s*=\s*\[([^\]]*)\]", text)
            if var_m:
                var_name = var_m.group(1)
                if re.search(r"install_requires\s*=\s*" + re.escape(var_name), text):
                    deps += re.findall(r"['\"]([A-Za-z0-9_\-\.]+)['\"]", var_m.group(2))
        if deps:
            return list(dict.fromkeys(deps))[:50]

    # Node package.json
    pkg = repo_path / "package.json"
    if pkg.exists():
        try:
            import json as _json
            data = _json.loads(pkg.read_text(encoding="utf-8"))
            deps += list(data.get("dependencies", {}).keys())[:30]
            deps += list(data.get("devDependencies", {}).keys())[:15]
        except Exception:
            pass
        if deps:
            return list(dict.fromkeys(deps))[:50]

    # Ruby Gemfile
    gemfile = repo_path / "Gemfile"
    if gemfile.exists():
        text = gemfile.read_text(encoding="utf-8", errors="ignore")
        deps += re.findall(r"gem ['\"]([^'\"]+)['\"]", text)[:30]

    return list(dict.fromkeys(d.strip() for d in deps if d.strip()))[:50]


def _get_era_samples(commits: list) -> list[str]:
    if not commits:
        return []
    step = max(1, len(commits) // 30)
    return [c.message.strip()[:120] for c in commits[::step]][:30]


def _get_test_command(repo_path: pathlib.Path) -> Optional[str]:
    """Detect test command. Prefer pytest when tests/ dir or test_*.py exist."""
    # pytest detection: tests/ directory or test_*.py files at repo root
    has_tests_dir = (repo_path / "tests").is_dir()
    has_test_files = any(
        f for f in repo_path.glob("test_*.py") if not _is_ignored(f)
    )
    if has_tests_dir or has_test_files:
        return "pytest"

    # config-file hints
    if (repo_path / "pytest.ini").exists():
        return "pytest"
    if (repo_path / "setup.cfg").exists():
        text = (repo_path / "setup.cfg").read_text(encoding="utf-8", errors="ignore")
        if "[tool:pytest]" in text or "[pytest]" in text:
            return "pytest"

    # Node
    if (repo_path / "package.json").exists():
        try:
            import json as _json
            data = _json.loads(
                (repo_path / "package.json").read_text(encoding="utf-8")
            )
            if "test" in data.get("scripts", {}):
                return "npm test"
        except Exception:
            pass

    # Makefile
    if (repo_path / "Makefile").exists():
        text = (repo_path / "Makefile").read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^test:", text, re.MULTILINE):
            return "make test"

    # Ruby
    if (repo_path / "Gemfile").exists():
        return "bundle exec rspec"

    return None


def exhume(path: str) -> dict:
    """
    Exhume a git repository and return the grave dict.
    This is the first ritual: Exhumacion.
    """
    repo_path = pathlib.Path(path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository not found: {path}")

    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        raise ValueError(f"Not a git repository: {path}")

    commits = list(repo.iter_commits(max_count=2000))
    if not commits:
        raise ValueError("Repository has no commits -- nothing to exhume")

    first_commit = commits[-1]
    last_commit = commits[0]

    author_counter: collections.Counter = collections.Counter()
    for c in commits:
        author_counter[c.author.name] += 1
    authors = author_counter.most_common(20)

    born_dt = datetime.fromtimestamp(first_commit.committed_date, tz=timezone.utc)
    died_dt = datetime.fromtimestamp(last_commit.committed_date, tz=timezone.utc)
    age_days = (died_dt - born_dt).days
    silence_days = (datetime.now(tz=timezone.utc) - died_dt).days

    todos = _extract_todos(repo_path)
    deps = _extract_dependencies(repo_path)
    language = _detect_language(repo_path)
    cause = _detect_cause_of_death(repo_path, authors)
    era_samples = _get_era_samples(commits)
    test_command = _get_test_command(repo_path)

    try:
        remote_urls = [r.url for r in repo.remotes]
    except Exception:
        remote_urls = []

    readme_text = ""
    for rname in ["README.md", "README.rst", "README.txt", "README"]:
        rpath = repo_path / rname
        if rpath.exists():
            readme_text = rpath.read_text(encoding="utf-8", errors="ignore")[:3000]
            break

    return {
        "name": repo_path.name,
        "path": str(repo_path),
        "language": language,
        "born": born_dt.isoformat(),
        "died": died_dt.isoformat(),
        "age_days": age_days,
        "silence_days": silence_days,
        "first_commit": {
            "sha": first_commit.hexsha[:8],
            "message": first_commit.message.strip()[:200],
            "author": first_commit.author.name,
            "date": born_dt.isoformat(),
        },
        "last_commit": {
            "sha": last_commit.hexsha[:8],
            "message": last_commit.message.strip()[:200],
            "author": last_commit.author.name,
            "date": died_dt.isoformat(),
        },
        "family": authors,
        "total_commits": len(commits),
        "cause_of_death": cause,
        "unfinished_todos": todos,
        "dependencies": deps,
        "era_samples": era_samples,
        "test_command": test_command,
        "remote_urls": remote_urls,
        "readme_excerpt": readme_text[:1500],
    }


def save_grave(grave: dict, output_path: Optional[str] = None) -> pathlib.Path:
    if output_path is None:
        out = pathlib.Path(grave["path"]) / ".tercera" / "grave.json"
    else:
        out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(grave, f, indent=2, default=str)
    return out


def load_grave(repo_path: str) -> dict:
    p = pathlib.Path(repo_path) / ".tercera" / "grave.json"
    if not p.exists():
        raise FileNotFoundError(
            f"No grave found at {p}. Run 'tercera exhume' first."
        )
    with open(p, encoding="utf-8") as f:
        return json.load(f)
