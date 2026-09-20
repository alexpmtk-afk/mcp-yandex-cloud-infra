#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { appendJsonl, codexHome, loadUsage } = require('../lib/usage');

(async () => {
  const raw = await readStdin();
  let input = {}; try { input = JSON.parse(raw || '{}'); } catch {}
  const result = loadUsage(input.transcript_path);
  const s = result.summary || {};
  const p = s.rateLimits && s.rateLimits.primary;
  const w = s.rateLimits && s.rateLimits.secondary;
  const remaining = (x) => x && typeof x.usedPercent === 'number' ? Math.max(0, 100 - x.usedPercent) : null;
  const r5 = remaining(p), r7 = remaining(w);
  appendJsonl(path.join(codexHome(), 'quota-router', 'history.jsonl'), {
    timestamp: new Date().toISOString(), event: 'stop', requestId: input.turn_id || null, threadId: input.session_id || null,
    promptHash: null, promptLength: null, currentModel: input.model || s.model || null, score: null,
    selectedModel: input.model || s.model || null, selectedEffort: s.reasoningEffort || null,
    remaining5h: r5, remaining7d: r7,
    reset5hMinutes: null, reset7dMinutes: null, quotaSource: result.source, quotaObservedAt: result.observedAt, force: false
  });
  const out = { continue: true };
  if ((r5 !== null && r5 <= 20) || (r7 !== null && r7 <= 15)) {
    const bits = [];
    if (r5 !== null) bits.push(`5h ${r5.toFixed(1)}% left`);
    if (r7 !== null) bits.push(`7d ${r7.toFixed(1)}% left`);
    out.systemMessage = `Quota warning: ${bits.join('; ')}. Prefer Luna/low and targeted work until reset.`;
  }
  process.stdout.write(JSON.stringify(out));
})().catch(() => process.stdout.write('{"continue":true}'));

function readStdin() {
  return new Promise((resolve) => { let d=''; process.stdin.setEncoding('utf8'); process.stdin.on('data', c=>d+=c); process.stdin.on('end',()=>resolve(d)); process.stdin.on('error',()=>resolve('')); });
}
