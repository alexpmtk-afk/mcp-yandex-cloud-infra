'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const proxy = path.join(__dirname, '..', 'bin', 'app-server-proxy.js');
const fake = path.join(__dirname, 'fake-app-server.js');
const codexHome = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-router-proxy-'));

const child = spawn(process.execPath, [proxy, process.execPath, fake], {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: { ...process.env, CODEX_HOME: codexHome }
});

let stdout = '';
let stderr = '';
child.stdout.setEncoding('utf8');
child.stderr.setEncoding('utf8');
child.stdout.on('data', (c) => stdout += c);
child.stderr.on('data', (c) => stderr += c);

const request = {
  method: 'turn/start',
  id: 42,
  params: {
    threadId: 'existing-old-thread',
    model: 'gpt-5.6-sol',
    effort: 'medium',
    collaborationMode: {
      mode: 'default',
      settings: {
        model: 'gpt-5.6-sol',
        reasoning_effort: 'medium',
        developer_instructions: 'preserve-me'
      }
    },
    input: [{ type: 'text', text: 'Покажи список файлов в текущей папке. Ничего не изменяй.', text_elements: [] }]
  }
};

// Regression: Windows/.NET wrappers can put U+FEFF before the first JSONL value.
// The proxy must normalize it instead of failing open and silently keeping Sol.
child.stdin.write('\uFEFF' + JSON.stringify(request) + '\n');
child.stdin.end();

const timer = setTimeout(() => {
  child.kill();
  console.error(stderr);
  throw new Error('proxy e2e timed out');
}, 10000);

child.on('exit', (code) => {
  clearTimeout(timer);
  try {
    assert.equal(code, 0, stderr);
    const lines = stdout.trim().split(/\r?\n/).filter(Boolean);
    assert.equal(lines.length, 1, stdout);
    const actual = JSON.parse(lines[0]);
    assert.equal(actual.id, 42);
    assert.equal(actual.params.threadId, 'existing-old-thread');
    assert.equal(actual.params.model, 'gpt-5.6-luna');
    assert.equal(actual.params.effort, 'low');
    assert.equal(actual.params.collaborationMode.settings.model, 'gpt-5.6-luna');
    assert.equal(actual.params.collaborationMode.settings.reasoning_effort, 'low');
    assert.equal(actual.params.collaborationMode.settings.developer_instructions, 'preserve-me');
    assert.deepEqual(actual.params.input, request.params.input);

    const historyText = fs.readFileSync(path.join(codexHome, 'quota-router', 'history.jsonl'), 'utf8');
    assert.equal(historyText.includes(request.params.input[0].text), false, 'raw prompt leaked to history');
    const record = JSON.parse(historyText.trim());
    const allowed = new Set([
      'timestamp','event','requestId','threadId','promptHash','promptLength','currentModel','score',
      'selectedModel','selectedEffort','quotaSource','quotaObservedAt','remaining5h','remaining7d',
      'reset5hMinutes','reset7dMinutes','force'
    ]);
    assert.deepEqual(Object.keys(record).filter((key) => !allowed.has(key)), []);
    console.log('proxy e2e BOM/privacy regression: PASS');
  } finally {
    fs.rmSync(codexHome, { recursive: true, force: true });
  }
});
