#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { appendJsonl, codexHome, loadUsage } = require('../lib/usage');
const { promptHash } = require('../lib/router-core');
const { rewriteClientMessage } = require('../lib/proxy-core');

const realExe = process.argv[2] || process.env.CODEX_ROUTER_REAL_EXE;
const childArgs = process.argv.slice(3);

if (!realExe) {
  process.stderr.write('Codex Auto Router: real codex executable was not provided.\n');
  process.exit(127);
}

const policyPath = process.env.CODEX_ROUTER_POLICY_PATH || path.join(__dirname, '..', 'policy.json');
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

function stripLeadingBom(value) {
  return value && value.charCodeAt(0) === 0xFEFF ? value.slice(1) : value;
}

function forwardLine(rawLine) {
  const normalizedLine = stripLeadingBom(rawLine);
  let out = normalizedLine;
  let message = null;
  try {
    message = JSON.parse(normalizedLine);
    if (process.env.CODEX_ROUTER_DISABLE !== '1') {
      const usageResult = message.method === 'turn/start' ? loadUsage(null) : { source: null, summary: null };
      const result = rewriteClientMessage(message, { policy, usage: usageResult.summary });
      if (result.routed) {
        out = JSON.stringify(result.message);
        const d = result.decision;
        appendJsonl(historyFile, {
          timestamp: new Date().toISOString(),
          event: 'proxy-route',
          requestId: message.id ?? null,
          threadId: message.params && message.params.threadId ? message.params.threadId : null,
          promptHash: promptHash(result.prompt),
          promptLength: result.prompt.length,
          currentModel: d.currentModel || null,
          score: d.score,
          selectedModel: d.route.model,
          selectedEffort: d.route.effort,
          quotaSource: usageResult.source,
          quotaObservedAt: usageResult.observedAt,
          remaining5h: d.quota.pRem,
          remaining7d: d.quota.sRem,
          reset5hMinutes: d.quota.pReset,
          reset7dMinutes: d.quota.sReset,
          force: d.force
        });
      }
    }
  } catch (err) {
    if (message && message.method === 'turn/start') {
      recordRouteError(message);
      process.stdout.write(JSON.stringify({
        ...(message.jsonrpc ? { jsonrpc: message.jsonrpc } : {}),
        id: message.id ?? null,
        error: {
          code: -32001,
          message: 'Codex Auto Router could not safely apply the selected model. The turn was blocked before model execution.'
        }
      }) + '\n');
      return;
    }
  }
  child.stdin.write(out + '\n');
}

function recordRouteError(message) {
  try {
    const params = message.params && typeof message.params === 'object' ? message.params : {};
    appendJsonl(historyFile, {
      timestamp: new Date().toISOString(),
      event: 'proxy-route-error',
      requestId: message.id ?? null,
      threadId: params.threadId || null,
      promptHash: null,
      promptLength: null,
      currentModel: params.model || null,
      score: null,
      selectedModel: null,
      selectedEffort: null,
      quotaSource: null,
      quotaObservedAt: null,
      remaining5h: null,
      remaining7d: null,
      reset5hMinutes: null,
      reset7dMinutes: null,
      force: false
    });
  } catch {}
}
