'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { findLatestQuotaSummary, sanitizeSummary } = require('../lib/usage');

const nowMs = 1_800_000_000_000;
const epoch = (offsetMinutes) => Math.floor((nowMs + offsetMinutes * 60_000) / 1000);
const limit = (usedPercent, offsetMinutes) => ({ usedPercent, resetsAt: epoch(offsetMinutes) });
const summary = (primary, secondary) => ({ rateLimits: { primary, secondary } });

let actual = sanitizeSummary(summary(limit(90, -1), limit(25, 300)), nowMs);
assert.equal(actual.rateLimits.primary, null, 'expired 5h window must be unknown');
assert.equal(actual.rateLimits.secondary.usedPercent, 25, 'valid 7d window must remain');

actual = sanitizeSummary(summary(limit(90, -1), limit(25, -2)), nowMs);
assert.equal(actual.rateLimits.primary, null, 'expired 5h window must be removed');
assert.equal(actual.rateLimits.secondary, null, 'expired 7d window must be removed');

actual = sanitizeSummary(summary(limit(40, 60), limit(25, 300)), nowMs);
assert.equal(actual.rateLimits.primary.usedPercent, 40);
assert.equal(actual.rateLimits.secondary.usedPercent, 25);

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-router-usage-'));
const previousHome = process.env.CODEX_HOME;
try {
  process.env.CODEX_HOME = temp;
  const sessions = path.join(temp, 'sessions');
  fs.mkdirSync(sessions, { recursive: true });
  const expiredFile = path.join(sessions, 'expired.jsonl');
  const validFile = path.join(sessions, 'valid.jsonl');
  writeTranscript(expiredFile, 91, -5, 81, -2);
  writeTranscript(validFile, 41, 90, 31, 400);
  fs.utimesSync(expiredFile, new Date(nowMs - 120_000), new Date(nowMs - 120_000));
  fs.utimesSync(validFile, new Date(nowMs - 60_000), new Date(nowMs - 60_000));

  const fallback = findLatestQuotaSummary(null, nowMs);
  assert.ok(fallback, 'a valid fallback should be found');
  assert.equal(path.resolve(fallback.file), path.resolve(validFile));
  assert.equal(fallback.summary.rateLimits.primary.usedPercent, 41);
  assert.equal(fallback.summary.rateLimits.secondary.usedPercent, 31);
} finally {
  if (previousHome === undefined) delete process.env.CODEX_HOME;
  else process.env.CODEX_HOME = previousHome;
  fs.rmSync(temp, { recursive: true, force: true });
}

console.log('usage expiry tests: PASS');

function writeTranscript(file, primaryUsed, primaryResetMinutes, secondaryUsed, secondaryResetMinutes) {
  const record = {
    type: 'event_msg',
    payload: {
      type: 'token_count',
      info: {},
      rate_limits: {
        primary: { used_percent: primaryUsed, window_minutes: 300, resets_at: epoch(primaryResetMinutes) },
        secondary: { used_percent: secondaryUsed, window_minutes: 10080, resets_at: epoch(secondaryResetMinutes) }
      }
    }
  };
  fs.writeFileSync(file, JSON.stringify(record) + '\n', 'utf8');
}
