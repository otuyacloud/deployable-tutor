#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"

install_claude() {
  mkdir -p "$HOME/.claude/commands" "$HOME/.claude/scripts"
  cp "$ROOT/claude/deployable.md" "$HOME/.claude/commands/deployable.md"
  cp "$ROOT/bin/deployable_lms.py" "$HOME/.claude/scripts/deployable_lms.py"
  chmod 700 "$HOME/.claude/scripts/deployable_lms.py"
  echo "Installed /deployable for Claude Code."
}

install_codex() {
  TARGET="${CODEX_HOME:-$HOME/.codex}/skills/deployable"
  mkdir -p "$TARGET/scripts"
  cp "$ROOT/codex/skills/deployable/SKILL.md" "$TARGET/SKILL.md"
  cp "$ROOT/bin/deployable_lms.py" "$TARGET/scripts/deployable_lms.py"
  chmod 700 "$TARGET/scripts/deployable_lms.py"
  echo "Installed the deployable skill for Codex."
}

install_opencode() {
  TARGET="$HOME/.config/opencode"
  mkdir -p "$TARGET/commands" "$TARGET/scripts"
  cp "$ROOT/opencode/deployable.md" "$TARGET/commands/deployable.md"
  cp "$ROOT/bin/deployable_lms.py" "$TARGET/scripts/deployable_lms.py"
  chmod 700 "$TARGET/scripts/deployable_lms.py"
  echo "Installed /deployable for OpenCode."
}

install_gemini() {
  TARGET="$HOME/.gemini"
  mkdir -p "$TARGET/commands" "$TARGET/scripts"
  cp "$ROOT/gemini/deployable.toml" "$TARGET/commands/deployable.toml"
  cp "$ROOT/bin/deployable_lms.py" "$TARGET/scripts/deployable_lms.py"
  chmod 700 "$TARGET/scripts/deployable_lms.py"
  echo "Installed /deployable for Gemini CLI."
}

case "$MODE" in
  --claude) install_claude ;;
  --codex) install_codex ;;
  --opencode) install_opencode ;;
  --gemini) install_gemini ;;
  *) echo "Usage: ./install.sh --claude | --codex | --opencode | --gemini"; exit 2 ;;
esac
