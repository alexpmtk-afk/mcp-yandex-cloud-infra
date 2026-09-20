# Codex Quota Router v0.4

Local, zero-model-call per-turn router for Codex Desktop.

## v0.3 architecture

On Windows, Codex Desktop supports the `CODEX_CLI_PATH` environment override. v0.3 uses that supported launch point instead of replacing the relocated OpenAI `codex.exe` binary.

Flow:

```text
Codex Desktop
  -> CODEX_CLI_PATH
  -> ~/.codex/quota-router/codex-router.exe
  -> app-server-proxy.js
  -> current original %LOCALAPPDATA%/OpenAI/Codex/bin/<hash>/codex.exe
```

The standalone launcher automatically discovers the newest relocated original Codex binary after Desktop updates. `CODEX_ROUTER_REAL_EXE` remains available as an explicit override for diagnostics/tests.

The proxy preserves the existing `threadId` and rewrites only `turn/start` routing fields. It can therefore select Luna / Terra / Sol and reasoning effort per new turn while the existing chat/thread continues normally. If the selected route cannot be applied and verified, the proxy returns a local protocol error and does not forward the original expensive request.

## Routing

- Simple/routine -> Luna low/medium.
- Integration/debugging -> Terra medium.
- Architecture/high-risk -> Sol medium/high.
- `QUOTA_FORCE` can intentionally bypass routing.

The router does not call a model itself and does not store raw prompts. Route history stores prompt hash/length plus routing metadata.

Expired 5-hour and 7-day usage windows are treated as unknown. Fallback discovery skips expired snapshots instead of displaying stale remaining quota.

## Standalone install on Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\install-standalone.ps1 -CodexHome $HOME\.codex
```

The installer:

- copies router runtime files under `~/.codex/quota-router`;
- compiles `codex-router.exe` as a separate launcher;
- smoke-tests it against the current original Codex binary;
- registers `CODEX_CLI_PATH` for the target Windows user;
- does not replace or modify OpenAI's `codex.exe`.

A full Codex Desktop restart is required after installation.

## Standalone rollback

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-standalone.ps1 -CodexHome $HOME\.codex
```

The previous `CODEX_CLI_PATH` value is restored if one existed.

## Tests

CI verifies:

- router unit tests;
- proxy routing unit tests;
- transparent stdio proxy e2e;
- BOM-prefixed JSONL and safe-failure regressions;
- expired quota and fallback selection regressions;
- standalone launcher compilation;
- automatic discovery of the newest original Codex binary;
- launcher + proxy + `turn/start` routing e2e with preserved `threadId`;
- standalone installer simulation;
- legacy v0.1 hook regression/rollback tests.

## Legacy v0.1 hook layer

The original global hook guard remains available as a secondary quota/preflight safety layer. It is no longer the mechanism responsible for automatic model switching in v0.3.
