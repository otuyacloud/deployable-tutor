#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"

install_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    return
  fi

  TARGET="$HOME/.local/share/deployable-tutor/bin/cloudflared"
  mkdir -p "$(dirname "$TARGET")"
  OS="$(uname -s)"
  ARCH="$(uname -m)"
  case "$OS:$ARCH" in
    Darwin:arm64) URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"; ARCHIVE=1 ;;
    Darwin:x86_64) URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"; ARCHIVE=1 ;;
    Linux:x86_64) URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"; ARCHIVE=0 ;;
    Linux:aarch64|Linux:arm64) URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"; ARCHIVE=0 ;;
    *) echo "Unsupported platform for automatic cloudflared setup: $OS/$ARCH" >&2; echo "Install cloudflared manually, then rerun this installer." >&2; exit 1 ;;
  esac

  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "Installing the Deployable connection helper..."
  curl -fsSL "$URL" -o "$TMP/cloudflared-download"
  if [ "$ARCHIVE" -eq 1 ]; then
    tar -xzf "$TMP/cloudflared-download" -C "$TMP"
    mv "$TMP/cloudflared" "$TARGET"
  else
    mv "$TMP/cloudflared-download" "$TARGET"
  fi
  chmod 700 "$TARGET"
}

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
  --claude) install_cloudflared; install_claude ;;
  --codex) install_cloudflared; install_codex ;;
  --opencode) install_cloudflared; install_opencode ;;
  --gemini) install_cloudflared; install_gemini ;;
  *) echo "Usage: ./install.sh --claude | --codex | --opencode | --gemini"; exit 2 ;;
esac
