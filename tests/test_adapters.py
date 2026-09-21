import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import deployable_update  # noqa: E402


class AdapterTests(unittest.TestCase):
    def test_every_adapter_has_bootstrap_and_complete_runtime(self):
        for tool, relative in deployable_update.ADAPTER_SOURCES.items():
            with self.subTest(tool=tool):
                content = (ROOT / relative).read_bytes()
                bootstrap = content.split(deployable_update.RUNTIME_START, maxsplit=1)[0].decode()
                runtime = deployable_update.extract_runtime(content)
                self.assertIn("deployable_update.py", bootstrap)
                self.assertIn(f"--tool {tool}", bootstrap)
                self.assertIn("--next", runtime)
                self.assertIn("--complete", runtime)
                self.assertIn("coursework workspace", runtime)

    def test_gemini_adapter_is_valid_toml(self):
        with (ROOT / "gemini" / "deployable.toml").open("rb") as handle:
            parsed = tomllib.load(handle)
        self.assertIn("prompt", parsed)

    def test_codex_skill_keeps_required_frontmatter(self):
        content = (ROOT / "codex" / "skills" / "deployable" / "SKILL.md").read_text()
        self.assertTrue(content.startswith("---\n"))
        frontmatter = content.split("---", maxsplit=2)[1]
        self.assertIn("name: deployable", frontmatter)
        self.assertIn("description:", frontmatter)


if __name__ == "__main__":
    unittest.main()
