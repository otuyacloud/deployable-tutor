#!/usr/bin/env python3
"""Safely refresh Deployable tutor runtime files from production main."""

import argparse
import fcntl
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 on Ubuntu 22.04
    tomllib = None


REPO_URL = "https://github.com/otuyacloud/deployable-tutor.git"
REF = "main"
RUNTIME_START = b"<!-- DEPLOYABLE_RUNTIME_START -->"
RUNTIME_END = b"<!-- DEPLOYABLE_RUNTIME_END -->"
OUTPUT_START = "<<<DEPLOYABLE_RUNTIME_START>>>"
OUTPUT_END = "<<<DEPLOYABLE_RUNTIME_END>>>"
ADAPTER_SOURCES = {
    "claude": "claude/deployable.md",
    "codex": "codex/skills/deployable/SKILL.md",
    "opencode": "opencode/deployable.md",
    "gemini": "gemini/deployable.toml",
}
CONNECTOR_SOURCE = "bin/deployable_lms.py"
BOOTSTRAP_COMMANDS = {
    "claude": 'python3 "$HOME/.claude/scripts/deployable_update.py" --tool claude',
    "codex": 'python3 "${CODEX_HOME:-$HOME/.codex}/skills/deployable/scripts/deployable_update.py" --tool codex',
    "opencode": 'python3 "$HOME/.config/opencode/scripts/deployable_update.py" --tool opencode',
    "gemini": 'python3 \\"$HOME/.gemini/scripts/deployable_update.py\\" --tool gemini',
}


def tool_paths(tool: str) -> tuple[Path, Path]:
    home = Path.home()
    if tool == "claude":
        return home / ".claude" / "commands" / "deployable.md", home / ".claude" / "scripts" / "deployable_lms.py"
    if tool == "codex":
        root = Path(os.environ.get("CODEX_HOME", home / ".codex")) / "skills" / "deployable"
        return root / "SKILL.md", root / "scripts" / "deployable_lms.py"
    if tool == "opencode":
        root = home / ".config" / "opencode"
        return root / "commands" / "deployable.md", root / "scripts" / "deployable_lms.py"
    if tool == "gemini":
        root = home / ".gemini"
        return root / "commands" / "deployable.toml", root / "scripts" / "deployable_lms.py"
    raise ValueError(f"Unsupported tool: {tool}")


def cache_root() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "deployable-tutor"


def state_root() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "deployable-tutor"


def extract_runtime(adapter: bytes) -> str:
    if adapter.count(RUNTIME_START) != 1 or adapter.count(RUNTIME_END) != 1:
        raise ValueError("Tutor adapter must contain exactly one runtime marker pair.")
    try:
        start = adapter.index(RUNTIME_START) + len(RUNTIME_START)
        end = adapter.index(RUNTIME_END, start)
    except ValueError as error:
        raise ValueError("Tutor adapter is missing runtime markers.") from error
    runtime = adapter[start:end].decode("utf-8").strip()
    if len(runtime) < 200:
        raise ValueError("Tutor runtime is unexpectedly short.")
    return runtime


def validate_adapter(tool: str, adapter: bytes) -> str:
    text = adapter.decode("utf-8")
    runtime = extract_runtime(adapter)
    bootstrap = text.split(RUNTIME_START.decode(), maxsplit=1)[0]
    expected_bootstrap = f"Before any LMS action, run `{BOOTSTRAP_COMMANDS[tool]}` exactly once for this invocation."
    if bootstrap.count(expected_bootstrap) != 1:
        raise ValueError("Tutor adapter has an invalid update bootstrap.")
    if OUTPUT_START not in bootstrap or OUTPUT_END not in bootstrap:
        raise ValueError("Tutor adapter bootstrap is missing output markers.")
    if tool == "gemini":
        lines = text.splitlines()
        if (
            len(lines) < 5
            or re.fullmatch(r'description = "[^"\\]*"', lines[0]) is None
            or lines[1] != ""
            or lines[2] != 'prompt = """'
            or lines[-1] != '"""'
            or any('"""' in line for line in lines[3:-1])
        ):
            raise ValueError("Gemini adapter has an invalid TOML envelope.")
        if tomllib is not None:
            parsed = tomllib.loads(text)
            if not isinstance(parsed.get("prompt"), str):
                raise ValueError("Gemini adapter is missing its prompt.")
    else:
        if not text.startswith("---\n"):
            raise ValueError("Markdown adapter has invalid frontmatter.")
        end = text.find("\n---\n", 4)
        if end == -1:
            raise ValueError("Markdown adapter has invalid frontmatter.")
        fields: list[tuple[str, str]] = []
        for line in text[4:end].splitlines():
            if not line.strip():
                continue
            if ":" not in line:
                raise ValueError("Markdown adapter has invalid frontmatter.")
            key, value = (part.strip() for part in line.split(":", maxsplit=1))
            if not key or not value or any(not (character.isalnum() or character in "_-") for character in key):
                raise ValueError("Markdown adapter has invalid frontmatter.")
            fields.append((key, value))
        expected_keys = {
            "claude": ["description", "argument-hint"],
            "codex": ["name", "description"],
            "opencode": ["description"],
        }[tool]
        if [key for key, _ in fields] != expected_keys:
            raise ValueError("Markdown adapter has unexpected frontmatter fields.")
        values = dict(fields)
        description = values["description"]
        if " " not in description or re.fullmatch(r"[A-Za-z][A-Za-z0-9 .,;/()_-]*", description) is None:
            raise ValueError("Markdown adapter description must use the supported plain-scalar form.")
        if tool == "claude" and values["argument-hint"] != '"[week N lesson M | week N overview]"':
            raise ValueError("Claude adapter has an invalid argument hint.")
        if "description" not in values:
            raise ValueError("Markdown adapter is missing its description.")
        if tool == "codex" and values.get("name") != "deployable":
            raise ValueError("Codex adapter is missing its skill name.")
    return runtime


def validate_payload(tool: str, adapter: bytes, connector: bytes) -> str:
    runtime = validate_adapter(tool, adapter)
    compile(connector.decode("utf-8"), CONNECTOR_SOURCE, "exec")
    return runtime


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def run_git(git_dir: Path, *args: str, timeout: int = 15) -> subprocess.CompletedProcess[bytes]:
    command = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "--git-dir",
        str(git_dir),
        *args,
    ]
    return subprocess.run(command, check=True, capture_output=True, timeout=timeout, env=git_env())


def ensure_cache(git_dir: Path, repo_url: str = REPO_URL) -> None:
    if not (git_dir / "HEAD").exists():
        git_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="repo-", dir=git_dir.parent))
        try:
            subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", "init", "--bare", "--quiet", str(staging)],
                check=True,
                capture_output=True,
                timeout=10,
                env=git_env(),
            )
            run_git(staging, "remote", "add", "origin", repo_url)
            os.replace(staging, git_dir)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    remote = run_git(git_dir, "remote", "get-url", "origin").stdout.decode().strip()
    if remote != repo_url:
        raise RuntimeError("Managed update cache has an unexpected remote.")


def fetch_candidate(tool: str, git_dir: Path, repo_url: str = REPO_URL, ref: str = REF) -> tuple[str, bytes, bytes]:
    ensure_cache(git_dir, repo_url)
    run_git(git_dir, "fetch", "--quiet", "--no-tags", "--depth=1", "origin", ref)
    commit = run_git(git_dir, "rev-parse", "FETCH_HEAD").stdout.decode().strip()
    adapter = run_git(git_dir, "show", f"{commit}:{ADAPTER_SOURCES[tool]}").stdout
    connector = run_git(git_dir, "show", f"{commit}:{CONNECTOR_SOURCE}").stdout
    validate_payload(tool, adapter, connector)
    return commit, adapter, connector


def previous_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.previous")


def stage_file(path: Path, content: bytes, mode: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        staged.chmod(mode)
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    staged = stage_file(path, content, mode)
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def activate(tool: str, adapter_path: Path, connector_path: Path, adapter: bytes, connector: bytes) -> None:
    validate_payload(tool, adapter, connector)
    targets = [(adapter_path, adapter, 0o600), (connector_path, connector, 0o700)]
    originals: dict[Path, tuple[bytes, int] | None] = {}
    staged: dict[Path, Path] = {}
    for path, content, mode in targets:
        originals[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
        staged[path] = stage_file(path, content, mode)
    try:
        for path, _, _ in targets:
            original = originals[path]
            if original is not None:
                atomic_write(previous_path(path), original[0], original[1])
        replaced: list[Path] = []
        try:
            for path, _, _ in targets:
                os.replace(staged[path], path)
                replaced.append(path)
        except Exception:
            for path in reversed(replaced):
                original = originals[path]
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, original[0], original[1])
            raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)


def read_valid(tool: str, adapter_path: Path, connector_path: Path) -> tuple[bytes, bytes, str]:
    adapter = adapter_path.read_bytes()
    connector = connector_path.read_bytes()
    return adapter, connector, validate_payload(tool, adapter, connector)


def restore_previous(tool: str, adapter_path: Path, connector_path: Path) -> tuple[bytes, bytes, str]:
    adapter = previous_path(adapter_path).read_bytes()
    connector = previous_path(connector_path).read_bytes()
    runtime = validate_payload(tool, adapter, connector)
    atomic_write(adapter_path, adapter, 0o600)
    atomic_write(connector_path, connector, 0o700)
    return adapter, connector, runtime


def apply_candidate(
    tool: str,
    adapter_path: Path,
    connector_path: Path,
    version_path: Path,
    commit: str,
    adapter: bytes,
    connector: bytes,
) -> tuple[str, bool]:
    validate_payload(tool, adapter, connector)
    current_adapter, current_connector, current_runtime = read_valid(tool, adapter_path, connector_path)
    changed = adapter != current_adapter or connector != current_connector
    if changed:
        activate(tool, adapter_path, connector_path, adapter, connector)
        current_runtime = extract_runtime(adapter)
    installed_version = version_path.read_text().strip() if version_path.exists() else ""
    if commit != installed_version:
        atomic_write(version_path, f"{commit}\n".encode(), 0o600)
    return current_runtime, changed


def emit_runtime(runtime: str) -> None:
    sys.stdout.write(f"{OUTPUT_START}\n{runtime}\n{OUTPUT_END}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the Deployable tutor runtime.")
    parser.add_argument("--tool", required=True, choices=sorted(ADAPTER_SOURCES))
    args = parser.parse_args()

    adapter_path, connector_path = tool_paths(args.tool)
    root = state_root()
    root.mkdir(parents=True, exist_ok=True)
    cache = cache_root()
    cache.mkdir(parents=True, exist_ok=True)
    lock_path = cache / "update.lock"
    version_path = root / f"version-{args.tool}"

    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            current_adapter, current_connector, runtime = read_valid(args.tool, adapter_path, connector_path)
        except (OSError, UnicodeError, ValueError, SyntaxError):
            try:
                current_adapter, current_connector, runtime = restore_previous(args.tool, adapter_path, connector_path)
                print("Deployable restored the previous working runtime.", file=sys.stderr)
            except (OSError, UnicodeError, ValueError, SyntaxError):
                print("Deployable has no valid installed runtime. Rerun install.sh.", file=sys.stderr)
                return 2

        if os.environ.get("DEPLOYABLE_TUTOR_SKIP_UPDATE") != "1":
            try:
                commit, adapter, connector = fetch_candidate(args.tool, cache / "repo.git")
                runtime, changed = apply_candidate(
                    args.tool, adapter_path, connector_path, version_path, commit, adapter, connector
                )
                if changed:
                    print(f"Deployable updated to {commit[:8]}.", file=sys.stderr)
            except (OSError, UnicodeError, ValueError, RuntimeError, SyntaxError, subprocess.SubprocessError) as error:
                print(f"Deployable update unavailable; using the installed runtime ({error}).", file=sys.stderr)

        emit_runtime(runtime)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
