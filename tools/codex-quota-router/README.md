# Codex Quota Router v0.1

Local, zero-model-call quota guard for Codex. It combines:

- `UserPromptSubmit` preflight routing before the main model turn;
- local reading of Codex rolling quota from session JSONL;
- optional integration with `codex-usage-monitor`;
- per-turn snapshots in `~/.codex/quota-router/history.jsonl`;
- default `Luna / low`, with blocking recommendations for Terra/Sol when needed;
- quota-aware blocking when the 5-hour or weekly window is critically low.

## Important limitation

Codex hooks can block a prompt and inject context, but the current hook output schema does not expose a command that changes the active model. Therefore v0.1 cannot invisibly switch Luna -> Terra -> Sol inside the same turn. Instead it blocks *before* expensive model work and tells the user which model/effort to select. This avoids spending the wrong model's quota.

## Install on Windows

Run from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Then fully restart Codex / ChatGPT Desktop and use `/hooks` once to review/trust the new global user hooks.

## Behavior

- Simple/routine -> Luna low/medium.
- Integration/debugging -> Terra medium.
- Architecture/high-risk -> Sol medium/high.
- If current model is stronger or weaker than the recommended route, the prompt is blocked before the main turn and a switch is recommended.
- If quota is critical, heavy tasks are blocked until reset.
- Add `QUOTA_FORCE` to the request to intentionally bypass routing for an urgent task.

## Privacy

The router does not store raw prompts. It stores only a short SHA-256 hash, prompt length, route, quota snapshot, model and project cwd. It makes no model/API call of its own.

## Test

```powershell
node .\test\router.test.js
```

Expected: `router tests: PASS`.

## Status

```powershell
node $HOME\.codex\quota-router\bin\status.js
```

## Rollback

Run `uninstall.ps1`. The installer and uninstaller back up `~/.codex/hooks.json` before changing it.

## Why no profiles in v0.1

The router does not depend on Codex profiles. Current Codex releases have had reports of global hooks being discovered twice when profile layering is used, so v0.1 keeps the path simpler: one global hook layer + the model picker.
