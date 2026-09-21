import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_each_tool_installs_and_emits_cached_runtime(self):
        layouts = {
            "claude": ("--claude", ".claude/commands/deployable.md", ".claude/scripts"),
            "codex": ("--codex", ".codex/skills/deployable/SKILL.md", ".codex/skills/deployable/scripts"),
            "opencode": ("--opencode", ".config/opencode/commands/deployable.md", ".config/opencode/scripts"),
            "gemini": ("--gemini", ".gemini/commands/deployable.toml", ".gemini/scripts"),
        }
        for tool, (mode, adapter_relative, scripts_relative) in layouts.items():
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                fake_bin = home / "fake-bin"
                fake_bin.mkdir()
                cloudflared = fake_bin / "cloudflared"
                cloudflared.write_text("#!/bin/sh\nexit 0\n")
                cloudflared.chmod(0o700)
                env = os.environ.copy()
                env.update(
                    {
                        "HOME": str(home),
                        "CODEX_HOME": str(home / ".codex"),
                        "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                        "DEPLOYABLE_TUTOR_SKIP_UPDATE": "1",
                    }
                )

                subprocess.run([str(ROOT / "install.sh"), mode], cwd=ROOT, env=env, check=True, capture_output=True)

                adapter = home / adapter_relative
                scripts = home / scripts_relative
                updater = scripts / "deployable_update.py"
                connector = scripts / "deployable_lms.py"
                self.assertTrue(adapter.is_file())
                self.assertTrue(updater.is_file() and os.access(updater, os.X_OK))
                self.assertTrue(connector.is_file() and os.access(connector, os.X_OK))

                result = subprocess.run(
                    ["python3", str(updater), "--tool", tool],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertIn("<<<DEPLOYABLE_RUNTIME_START>>>", result.stdout)
                self.assertIn("<<<DEPLOYABLE_RUNTIME_END>>>", result.stdout)
                self.assertIn("--next", result.stdout)


if __name__ == "__main__":
    unittest.main()
