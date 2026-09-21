# Deployable Tutor

Content-free local connector and AI adapters for the OpsAndPlatforms Deployable DevOps Bootcamp.

The package never includes course lessons. It obtains them live from Frappe after the learner passes Cloudflare Access and signs into the LMS. Revoking LMS access prevents future reads.

## Install

The installer downloads a user-local copy of [cloudflared](https://developers.cloudflare.com/cloudflare-one/tutorials/cli/) when it is not already installed. No Homebrew, apt, administrator access, or PATH configuration is required.

```bash
git clone https://github.com/otuyacloud/deployable-tutor.git
cd deployable-tutor
./install.sh --claude  # or --codex / --opencode / --gemini
```

On the learner's first use, run:

```bash
python3 bin/deployable_lms.py --login
```

The connector opens the Cloudflare Access login flow, then asks for the learner's Frappe LMS email and password. The browser authentication is the one unavoidable step: it proves that this learner is allowed to use the course.

Then use `/deployable` in Claude Code, OpenCode, or Gemini CLI. Codex discovers the installed `deployable` skill; invoke it by asking for the Deployable course or using `$deployable`. The tutor acts as a lesson companion: it retrieves the existing LMS lesson, follows it from top to bottom, pauses for exercises and checkpoints, and helps without creating a separate curriculum.

When a lesson produces files, the tutor uses an existing student coursework workspace or creates `$HOME/deployable-coursework`. It creates week directories only as they are needed, keeps coursework separate from this connector repository, and validates the learner's actual files and command output against the LMS checkpoint. Frappe remains the source of truth for lessons and completion.

After completing a lesson, the tutor retrieves and offers the next lesson in the same conversation. `/deployable` is only needed to start or resume tutoring, not between lessons.

The connector stores only an expiring Frappe session: macOS uses Keychain; Ubuntu and WSL use a user-only local state file. It does not cache lessons.

## Course navigation

Week 0 is a readiness track: terminal, account, and learning-system setup before instructional Week 1. Ask the tutor to “start the course” and it will guide the next incomplete lesson, including Week 0 when appropriate. Ask for “Week 4 overview” (or any Week 0–14 overview) to open that week's actual first lesson: its overview and learning objectives. It is a normal lesson and changes progress only after evidence and the learner's explicit consent.
