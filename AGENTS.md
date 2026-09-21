# Repository instructions

## Release safety

- Treat `main` as student production. Do not develop, commit, or push directly to it; use a focused branch.
- Keep the Claude, Codex, OpenCode, and Gemini adapters behaviorally aligned when tutor behavior changes.
- Before pushing, run the automated checks and install the branch locally to exercise the affected tutor flow as a learner would.
- Never change a real student's LMS progress during testing; use mocks or an instructor/test account.
- Merge into `main` only after the local behavior test and automated checks pass.
