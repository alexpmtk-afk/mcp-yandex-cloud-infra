#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { classify, makeAdditionalContext, makeBlockReason, promptHash } = require('../lib/router-core');
const { appendJsonl, codexHome, loadUsage } = require('../lib/usage');

(async () => {
  const raw = await readStdin();
  let input;
  try { input = JSON.parse(raw || '{}'); } catch { process.exit(0); }
  const policy = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'policy.json'), 'utf8'));
  const usageResult = loadUsage(input.transcript_path);
  const usage = usageResult.summary || null;
  const decision = classify({ prompt: input.prompt, currentModel: input.model, usage, policy });

  appendJsonl(path.join(codexHome(), 'quota-router', 'history.jsonl'), {
    timestamp: new Date().toISOString(),
    event: 'preflight',
    requestId: input.turn_id || null,
    threadId: input.session_id || null,
    promptHash: promptHash(input.prompt),
    promptLength: String(input.prompt || '').length,
    currentModel: input.model || null,
    score: decision.score,
    selectedModel: decision.route.model,
    selectedEffort: decision.route.effort,
    quotaSource: usageResult.source,
    remaining5h: decision.quota.pRem,
    remaining7d: decision.quota.sRem,
    reset5hMinutes: decision.quota.pReset,
    reset7dMinutes: decision.quota.sReset,
    force: decision.force
  });

  if (decision.block) {
    process.stdout.write(JSON.stringify({ decision: 'block', reason: makeBlockReason(decision, policy) }));
    return;
  }

  if (policy.behavior.injectContextWhenAllowed) {
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: makeAdditionalContext(decision) }
    }));
  }
})().catch(() => process.exit(0));

function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (c) => data += c);
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', () => resolve(''));
  });
}
