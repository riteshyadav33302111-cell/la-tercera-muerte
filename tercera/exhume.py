"""
Exhumation: reads a git repository and extracts everything the ghost needs to remember.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Optional

import git


# ---------------------------------------------------------------------------
# Cause of death heuristics
# ---------------------------------------------------------------------------

DEATH_CAUSES = [
    (re.compile(r"python_requires.*['\"]2\.", re.I), "Succumbed to Python 2 end-of-life (January 1, 2020)"),
    (re.compile(r"Programming Language.*Python.*2\.", re.I), "Classified under Python 2 — a lineage that ceased support in 2020"),
    (re.compile(r"travis-ci\.org", re.I), "Its heartbeat monitor (Travis CI) went silent"),
    (re.compile(r"circleci\.com.*v1", re.I), "Its pipeline crumbled when CircleCI deprecated v1"),
    (re.compile(r"bower\.json", re.I), "Nourished by Bower, a dependency manager that itself died"),
    (re.compile(r"grunt", re.I), "Animated by Grunt, now a relic of another era"),
    (re.compile(r"coffeescript", re.I), "Dreamt in CoffeeScript, a language that passed quietly"),
    (re.compile(r"left-pad", re.I), "Starved when left-pad vanished from npm (March 2016)"),
    (re.compile(r"node.*['\"]0\.\d", re.I), "Required Node.js 0.x — a version that departed long ago"),
    (re.compile(r"ruby.*['\"]1\.[89]", re.I), "Breathed on Ruby 1.x, an unsupported branch"),
    (re.compile(r"flash", re.I), "Built for Adobe Flash — extinguished December 31, 2020"),
]

LONE_MAINTAINER_THRESHOLD = 0.88


def _detect_cause_of_death(repo_path: pathlib.Path, authors: list[tuple[str, int]]) -> str:
    """Run heuristics over repo files to determine cause of death."""
    # Check file contents for known patterns
    for f in repo_path.rglob("*"):
        if f.is_file() and f.stat().st_size < 1_000_000:
            try:
                text = f.read_text(errors="ignore")
                for pattern, cause in DEATH_CAUSES:
                    if pattern.search(text):
                        return cause
            except Exception:
                continue

    # Lone maintainer
    if authors:
        total = sum(c for _, c in authors)
        top_pct = authors[0][1] / total if total else 0
        if top_pct >= LONE_MAINTAINER_THRESHOLD:
            return f"Its keeper ({authors[0][0]}) walked away, and no one else knew the way"

    return "Cause unknown — some ghosts keep their secrets"


def _detect_language(repo_path: pathlib.Path) -> str:
    """Very simple language detection by file extension frequency."""
    ext_count: dict[str, int] = collections.Counter()
    for f in repo_path.rglob("*"):
        if f.is_file() and f.suffix:
            ext_count[f.suffix.lower()] += 1

    lang_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".rb": "Ruby", ".go": "Go", ".java": "Java", ".rs": "Rust",
        ".c": "C", ".cpp": "C++", ".cs": "C#", ".php": "PHP",
        ".swift": "Swift", ".kt": "Kotlin", ".ex": "Elixir",
        ".clj": "Clojure", ".hs": "Haskell", ".ml": "OCaml",
    }

    for ext, count in ext_count.most_common(10):
        if ext in lang_map:
            return lang_map[ext]

    return "Unknown"


def _extract_todos(repo_path: pathlib.Path) -> list[dict]:
    """Find TODO/FIXME/HACK/XXX comments — the ghost's unfinished business."""
    todos = []
    source_exts = {".py", ".js", ".ts", ".rb", ".go", ".java", ".rs",
                   ".c", ".cpp", ".cs", ".php", ".swift", ".kt"}

    for f in repo_path.rglob("*"):
        if f.is_file() and f.suffix.lower() in source_exts:
            try:
                for i, line in enumerate(f.read_text(errors="ignore").splitlines()):
                    m = re.search(r"(TODO|FIXME|HACK|XXX|BUG|BROKEN)\s*:?\s*(.*)", line, re.I)
                    if m:
                        todos.append({
                            "file": str(f.relative_to(repo_path)),
                            "line": i + 1,
                            "kind": m.group(1).upper(),
                            "text": m.group(2).strip()[:200],
                        })
            except Exception:
                continue

    return todos[:60]


def _extract_dependencies(repo_path: pathlib.Path) -> list[str]:
    """Extract dependency names from common manifest files."""
    deps = []

    # Python
    for req_file in ["requirements.txt", "requirements-dev.txt", "setup.py", "setup.cfg", "pyproject.toml"]:
        p = repo_path / req_file
        if p.exists():
            text = p.read_text(errors="ignore")
            deps += re.findall(r"^([A-Za-z0-9_\-\.]+)", text, re.MULTILINE)[:30]
            break

    # Node
    pkg = repo_path / "package.json"
    if pkg.exists():
        try:
            import json as _json
            data = _json.loads(pkg.read_text())
            deps += list(data.get("dependencies", {}).keys())[:30]
            deps += list(data.get("devDependencies", {}).keys())[:15]
        except Exception:
            pass

    # Ruby
    gemfile = repo_path / "Gemfile"
    if gemfile.exists():
        text = gemfile.read_text(errors="ignore")
        deps += re.findall(r"gem ['\"]([^'\"]+)['\"]", text)[:30]

    return list(dict.fromkeys(d.strip() for d in deps if d.strip()))[:50]


def _get_era_samples(commits: list) -> list[str]:
    """Sample commit messages evenly across history for era-detection."""
    if not commits:
        return []
    step = max(1, len(commits) // 30)
    return [c.message.strip()[:120] for c in commits[::step]][:30]


def _get_test_command(repo_path: pathlib.Path) -> Optional[str]:
    """Guess the test command from the project files."""
    if (repo_path / "pytest.ini").exists() or (repo_path / "setup.cfg").exists():
        return "pytest"
    if (repo_path / "package.json").exists():
        try:
            import json as _json
            data = _json.loads((repo_path / "package.json").read_text())
            if "test" in data.get("scripts", {}):
                return "npm test"
        except Exception:
            pass
    if (repo_path / "Makefile").exists():
        text = (repo_path / "Makefile").read_text(errors="ignore")
        if re.search(r"^test:", text, re.MULTILINE):
            return "make test"
    if (repo_path / "Gemfile").exists():
        return "bundle exec rspec"
    return None


def exhume(path: str) -> dict:
    """
    Exhume a git repository and return the grave.json dict.

    This is the first ritual: Exhumación.
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
        raise ValueError("Repository has no commits — nothing to exhume")

    first_commit = commits[-1]
    last_commit = commits[0]

    # Authors
    author_counter: collections.Counter = collections.Counter()
    for c in commits:
        author_counter[c.author.name] += 1

    authors = author_counter.most_common(20)

    # Time calculations
    born_dt = datetime.fromtimestamp(first_commit.committed_date, tz=timezone.utc)
    died_dt = datetime.fromtimestamp(last_commit.committed_date, tz=timezone.utc)
    age_days = (died_dt - born_dt).days
    silence_days = (datetime.now(tz=timezone.utc) - died_dt).days

    # Collect data
    todos = _extract_todos(repo_path)
    deps = _extract_dependencies(repo_path)
    language = _detect_language(repo_path)
    cause = _detect_cause_of_death(repo_path, authors)
    era_samples = _get_era_samples(commits)
    test_command = _get_test_command(repo_path)

    # Branch/fork info
    try:
        remote_urls = [r.url for r in repo.remotes]
    except Exception:
        remote_urls = []

    # README
    readme_text = ""
    for rname in ["README.md", "README.rst", "README.txt", "README"]:
        rpath = repo_path / rname
        if rpath.exists():
            readme_text = rpath.read_text(errors="ignore")[:3000]
            break

    grave = {
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
        "language": language,
        "cause_of_death": cause,
        "unfinished_todos": todos,
        "dependencies": deps,
        "era_samples": era_samples,
        "test_command": test_command,
        "remote_urls": remote_urls,
        "readme_excerpt": readme_text[:1500],
    }

    return grave


def save_grave(grave: dict, output_path: Optional[str] = None) -> pathlib.Path:
    """Save grave.json to disk."""
    if output_path is None:
        out = pathlib.Path(grave["path"]) / ".tercera" / "grave.json"
    else:
        out = pathlib.Path(output_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(grave, f, indent=2, default=str)

    return out


def load_grave(repo_path: str) -> dict:
    """Load a previously saved grave.json."""
    p = pathlib.Path(repo_path) / ".tercera" / "grave.json"
    if not p.exists():
        raise FileNotFoundError(f"No grave found at {p}. Run 'tercera exhume' first.")
    with open(p, encoding="utf-8") as f:
        return json.load(f)
