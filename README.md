# Deployable Tutor

Content-free local connector and AI adapters for the OpsAndPlatforms Deployable DevOps Bootcamp.

The package never includes course lessons. It obtains them live from Frappe after the learner passes Cloudflare Access and signs into the LMS. Revoking LMS access prevents future reads.

## Install

Prerequisite: install [cloudflared](https://developers.cloudflare.com/cloudflare-one/tutorials/cli/) for the learner's operating system.

```bash
git clone https://github.com/otuyacloud/deployable-tutor.git
cd deployable-tutor
./install.sh --claude  # or --codex / --opencode / --gemini
```

On the learner's first use, run:

```bash
cloudflared access login https://lms.opsandplatforms.com
python3 ~/.claude/scripts/deployable_lms.py --login
```

Then use `/deployable` in Claude Code, OpenCode, or Gemini CLI. Codex discovers the installed `deployable` skill; invoke it by asking for the Deployable course or using `$deployable`.

The connector stores only an expiring Frappe session: macOS uses Keychain; Ubuntu and WSL use a user-only local state file. It does not cache lessons.
