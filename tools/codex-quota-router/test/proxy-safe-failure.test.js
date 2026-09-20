'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const proxy = path.join(__dirname, '..', 'bin', 'app-server-proxy.js');
const fake = path.join(__dirname, 'fake-app-server.js');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-router-fail-'));
const policyPath = path.join(temp, 'invalid-policy.json');
fs.writeFileSync(policyPath, JSON.stringify({ thresholds: null, behavior: {} }), 'utf8');

const child = spawn(process.execPath, [proxy, process.execPath, fake], {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: {
    ...process.env,
    CODEX_HOME: path.join(temp, '.codex'),
    CODEX_ROUTER_POLICY_PATH: policyPath
  }
});

let stdout = '';
let stderr = '';
child.stdout.setEncoding('utf8');
child.stderr.setEncoding('utf8');
child.stdout.on('data', (chunk) => stdout += chunk);
child.stderr.on('data', (chunk) => stderr += chunk);

const request = {
  jsonrpc: '2.0',
  id: 99,
  method: 'turn/start',
  params: {
    threadId: 'must-not-run-on-sol',
    model: 'gpt-5.6-sol',
    effort: 'high',
    input: [{ type: 'text', text: 'Покажи список файлов.' }]
  }
};
child.stdin.end(JSON.stringify(request) + '\n');

const timer = setTimeout(() => child.kill(), 10_000);
child.on('exit', (code) => {
  clearTimeout(timer);
  try {
    assert.equal(code, 0, stderr);
    const lines = stdout.trim().split(/\r?\n/).filter(Boolean);
    assert.equal(lines.length, 1, stdout);
    const response = JSON.parse(lines[0]);
    assert.equal(response.id, 99);
    assert.equal(response.error.code, -32001);
    assert.match(response.error.message, /blocked before model execution/i);
    assert.equal(response.params, undefined, 'the original Sol request must not reach the child');
    console.log('proxy safe failure test: PASS');
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
