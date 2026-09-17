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

case "$MODE" in
  --claude) install_claude ;;
  --codex) install_codex ;;
  --opencode) install_opencode ;;
  *) echo "Usage: ./install.sh --claude | --codex | --opencode"; exit 2 ;;
esac
