# PowerShell Admin Bridge

Purpose: narrowly scoped elevated Windows operations that the normal `NETWORK SERVICE` PowerShell Bridge cannot perform, such as registering or updating a Task Scheduler task for an interactive user-session collector.

Runner label: `codex-bridge-admin`.
Expected Windows service identity: `NT AUTHORITY\SYSTEM`.

## Safety contract

- The normal bridge remains the default transport.
- Use this admin bridge only when an operation has failed specifically because the normal runner lacks Windows privileges.
- Every new executable PowerShell command still follows the canonical approval gate: show exact command -> explicit user approval -> execute exactly that command.
- One approved command -> one commit -> one workflow run -> terminal result.
- Never place passwords, tokens, private keys, cookies, or other secrets in `command.ps1` or logs.
- Fetch the command from the triggering `GITHUB_SHA`, never from moving branch HEAD.
- Do not use the admin runner to launch the marketplace browser. It may only create/manage the interactive Task Scheduler task. The actual Ozon collector must run as `Win10_Game_OS` in the interactive Windows session.

## Current Marketplace Card Monitor use

The normal runner proved alive on 2026-09-07 but received `0x80070005 Access is denied` from `Register-ScheduledTask`. The admin bridge is the intended escalation path for that narrow Windows operation.
