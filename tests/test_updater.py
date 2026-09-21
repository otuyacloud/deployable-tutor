import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import deployable_update  # noqa: E402


def adapter(runtime: str, tool: str = "claude") -> bytes:
    bootstrap = (
        f"Before any LMS action, run `{deployable_update.BOOTSTRAP_COMMANDS[tool]}` exactly once for this invocation. "
        "Follow only <<<DEPLOYABLE_RUNTIME_START>>> through <<<DEPLOYABLE_RUNTIME_END>>>.\n"
    )
    body = bootstrap + (
        "<!-- DEPLOYABLE_RUNTIME_START -->\n"
        f"{runtime}\n"
        "<!-- DEPLOYABLE_RUNTIME_END -->\n"
    )
    if tool == "gemini":
        return f'description = "Test adapter"\n\nprompt = """\n{body}"""\n'.encode()
    frontmatters = {
        "claude": '---\ndescription: Test adapter\nargument-hint: "[week N lesson M | week N overview]"\n---\n',
        "codex": "---\nname: deployable\ndescription: Test adapter\n---\n",
        "opencode": "---\ndescription: Test adapter\n---\n",
    }
    return f"{frontmatters[tool]}{body}".encode()


class UpdaterTests(unittest.TestCase):
    def test_extracts_only_runtime_section(self):
        runtime = "Use the LMS lesson as the curriculum. " * 10
        self.assertEqual(deployable_update.extract_runtime(adapter(runtime)), runtime.strip())

    def test_rejects_adapter_without_runtime_markers(self):
        with self.assertRaises(ValueError):
            deployable_update.extract_runtime(b"no runtime markers")

    def test_activation_preserves_previous_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter_path = root / "commands" / "deployable.md"
            connector_path = root / "scripts" / "deployable_lms.py"
            old_adapter = adapter("old runtime instructions " * 20)
            new_adapter = adapter("new runtime instructions " * 20)
            old_connector = b"print('old')\n"
            new_connector = b"print('new')\n"
            adapter_path.parent.mkdir()
            connector_path.parent.mkdir()
            adapter_path.write_bytes(old_adapter)
            connector_path.write_bytes(old_connector)

            deployable_update.activate("claude", adapter_path, connector_path, new_adapter, new_connector)

            self.assertEqual(adapter_path.read_bytes(), new_adapter)
            self.assertEqual(connector_path.read_bytes(), new_connector)
            self.assertEqual(deployable_update.previous_path(adapter_path).read_bytes(), old_adapter)
            self.assertEqual(deployable_update.previous_path(connector_path).read_bytes(), old_connector)

    def test_fetches_and_activates_candidate_from_local_main(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=source, check=True)
            for relative in deployable_update.ADAPTER_SOURCES.values():
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(adapter("runtime instructions from local main " * 15, tool=next(
                    tool for tool, candidate in deployable_update.ADAPTER_SOURCES.items() if candidate == relative
                )))
            connector = source / deployable_update.CONNECTOR_SOURCE
            connector.parent.mkdir(parents=True, exist_ok=True)
            connector.write_text("print('connector')\n")
            subprocess.run(["git", "add", "."], cwd=source, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=source, check=True)

            commit, fetched_adapter, fetched_connector = deployable_update.fetch_candidate(
                "claude", root / "cache.git", str(source), "main"
            )
            installed_adapter = root / "installed" / "commands" / "deployable.md"
            installed_connector = root / "installed" / "scripts" / "deployable_lms.py"
            deployable_update.activate("claude", installed_adapter, installed_connector, fetched_adapter, fetched_connector)

            self.assertEqual(len(commit), 40)
            self.assertIn(b"runtime instructions from local main", installed_adapter.read_bytes())
            self.assertEqual(installed_connector.read_bytes(), b"print('connector')\n")

    def test_invalid_connector_is_not_accepted(self):
        with self.assertRaises(SyntaxError):
            deployable_update.validate_payload("claude", adapter("valid runtime " * 20), b"def broken(:\n")

    def test_invalid_gemini_toml_is_rejected(self):
        invalid = adapter("valid runtime " * 20, tool="gemini").replace(b'description = "Test adapter"', b'description = "Test adapter')
        with self.assertRaises(ValueError):
            deployable_update.validate_payload("gemini", invalid, b"print('ok')\n")

    def test_python_310_gemini_fallback_accepts_only_expected_envelope(self):
        valid = (Path(__file__).resolve().parents[1] / "gemini" / "deployable.toml").read_bytes()
        invalid = valid.replace(b"\nprompt =", b"\nextra = true\n\nprompt =", 1)
        with patch.object(deployable_update, "tomllib", None):
            deployable_update.validate_payload("gemini", valid, b"print('ok')\n")
            with self.assertRaises(ValueError):
                deployable_update.validate_payload("gemini", invalid, b"print('ok')\n")

    def test_broken_bootstrap_is_rejected(self):
        broken = adapter("valid runtime " * 20).replace(b"deployable_update.py", b"missing_updater.py")
        with self.assertRaises(ValueError):
            deployable_update.validate_payload("claude", broken, b"print('ok')\n")

    def test_broken_markdown_frontmatter_is_rejected(self):
        broken = adapter("valid runtime " * 20).replace(b"description:", b"description")
        with self.assertRaises(ValueError):
            deployable_update.validate_payload("claude", broken, b"print('ok')\n")

    def test_unclosed_markdown_frontmatter_quote_is_rejected(self):
        real = (Path(__file__).resolve().parents[1] / "claude" / "deployable.md").read_bytes()
        broken = real.replace(b"description: Guide", b'description: "Guide', 1)
        with self.assertRaises(ValueError):
            deployable_update.validate_payload("claude", broken, b"print('ok')\n")

    def test_implicit_yaml_boolean_description_is_rejected(self):
        real = (Path(__file__).resolve().parents[1] / "codex" / "skills" / "deployable" / "SKILL.md").read_bytes()
        start = real.index(b"description:")
        end = real.index(b"\n", start)
        broken = real[:start] + b"description: true" + real[end:]
        with self.assertRaises(ValueError):
            deployable_update.validate_payload("codex", broken, b"print('ok')\n")

    def test_wrong_tool_updater_path_is_rejected(self):
        real = (Path(__file__).resolve().parents[1] / "claude" / "deployable.md").read_bytes()
        broken = real.replace(b"$HOME/.claude/scripts", b"$HOME/.gemini/scripts", 1)
        with self.assertRaises(ValueError):
            deployable_update.validate_payload("claude", broken, b"print('ok')\n")

    def test_python_310_fallback_rejects_unclosed_gemini_description(self):
        real = (Path(__file__).resolve().parents[1] / "gemini" / "deployable.toml").read_bytes()
        broken = real.replace(b'top to bottom"', b"top to bottom", 1)
        with patch.object(deployable_update, "tomllib", None):
            with self.assertRaises(ValueError):
                deployable_update.validate_payload("gemini", broken, b"print('ok')\n")

    def test_noop_commit_preserves_previous_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter_path = root / "deployable.md"
            connector_path = root / "deployable_lms.py"
            version_path = root / "version"
            current_adapter = adapter("current runtime " * 20)
            previous_adapter = adapter("previous runtime " * 20)
            current_connector = b"print('current')\n"
            previous_connector = b"print('previous')\n"
            adapter_path.write_bytes(current_adapter)
            connector_path.write_bytes(current_connector)
            deployable_update.previous_path(adapter_path).write_bytes(previous_adapter)
            deployable_update.previous_path(connector_path).write_bytes(previous_connector)

            runtime, changed = deployable_update.apply_candidate(
                "claude", adapter_path, connector_path, version_path, "a" * 40, current_adapter, current_connector
            )

            self.assertFalse(changed)
            self.assertIn("current runtime", runtime)
            self.assertEqual(deployable_update.previous_path(adapter_path).read_bytes(), previous_adapter)
            self.assertEqual(deployable_update.previous_path(connector_path).read_bytes(), previous_connector)

    def test_version_write_retry_does_not_replace_previous_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter_path = root / "deployable.md"
            connector_path = root / "deployable_lms.py"
            version_path = root / "version"
            old_adapter = adapter("old runtime " * 20)
            new_adapter = adapter("new runtime " * 20)
            old_connector = b"print('old')\n"
            new_connector = b"print('new')\n"
            adapter_path.write_bytes(old_adapter)
            connector_path.write_bytes(old_connector)
            real_atomic_write = deployable_update.atomic_write

            def fail_version(path, content, mode):
                if path == version_path:
                    raise OSError("simulated version write failure")
                return real_atomic_write(path, content, mode)

            with patch.object(deployable_update, "atomic_write", side_effect=fail_version):
                with self.assertRaises(OSError):
                    deployable_update.apply_candidate(
                        "claude", adapter_path, connector_path, version_path, "b" * 40, new_adapter, new_connector
                    )

            saved_previous = deployable_update.previous_path(adapter_path).read_bytes()
            runtime, changed = deployable_update.apply_candidate(
                "claude", adapter_path, connector_path, version_path, "b" * 40, new_adapter, new_connector
            )
            self.assertFalse(changed)
            self.assertIn("new runtime", runtime)
            self.assertEqual(deployable_update.previous_path(adapter_path).read_bytes(), saved_previous)


if __name__ == "__main__":
    unittest.main()
