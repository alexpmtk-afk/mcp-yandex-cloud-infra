#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { appendJsonl, codexHome } = require('../lib/usage');
const { promptHash } = require('../lib/router-core');
const { rewriteClientMessage } = require('../lib/proxy-core');

const realExe = process.argv[2] || process.env.CODEX_ROUTER_REAL_EXE;
const childArgs = process.argv.slice(3);

if (!realExe) {
  process.stderr.write('Codex Auto Router: real codex executable was not provided.\n');
  process.exit(127);
}

const policyPath = path.join(__dirname, '..', 'policy.json');
const policy = JSON.parse(fs.readFileSync(policyPath, 'utf8'));
const historyFile = path.join(codexHome(), 'quota-router', 'history.jsonl');

const child = spawn(realExe, childArgs, {
  cwd: process.cwd(),
  env: process.env,
  windowsHide: true,
  stdio: ['pipe', 'pipe', 'pipe']
});

child.stdout.pipe(process.stdout);
child.stderr.pipe(process.stderr);

let pending = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  pending += chunk;
  for (;;) {
    const nl = pending.indexOf('\n');
    if (nl < 0) break;
    const line = pending.slice(0, nl);
    pending = pending.slice(nl + 1);
    forwardLine(line);
  }
});

process.stdin.on('end', () => {
  if (pending.length) forwardLine(pending);
  child.stdin.end();
});

process.stdin.on('error', () => child.stdin.end());
child.on('error', (err) => {
  process.stderr.write(`Codex Auto Router: failed to start real Codex: ${err.message}\n`);
  process.exitCode = 127;
});
child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(typeof code === 'number' ? code : 1);
});

function forwardLine(rawLine) {
  let out = rawLine;
  try {
    const message = JSON.parse(rawLine);
    if (process.env.CODEX_ROUTER_DISABLE !== '1') {
      const result = rewriteClientMessage(message, { policy });
      if (result.routed) {
        out = JSON.stringify(result.message);
        const d = result.decision;
        appendJsonl(historyFile, {
          at: new Date().toISOString(),
          event: 'proxy-route',
          requestId: message.id ?? null,
          threadId: message.params && message.params.threadId ? message.params.threadId : null,
          promptHash: promptHash(result.prompt),
          promptLength: result.prompt.length,
          currentModel: d.currentModel || null,
          score: d.score,
          selectedModel: d.route.model,
          selectedEffort: d.route.effort,
          force: d.force
        });
      }
    }
  } catch (err) {
    // Fail open: protocol traffic must keep flowing even if routing fails.
    try {
      appendJsonl(historyFile, {
        at: new Date().toISOString(),
        event: 'proxy-error',
        error: String(err && err.message ? err.message : err).slice(0, 500)
      });
    } catch {}
  }
  child.stdin.write(out + '\n');
}
