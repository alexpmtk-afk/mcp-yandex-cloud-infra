#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { codexHome, loadUsage } = require('../lib/usage');

const home = codexHome();
const history = path.join(home, 'quota-router', 'history.jsonl');
const result = loadUsage(null);
const s = result.summary || {};
const rem = (x) => x && typeof x.usedPercent === 'number' ? Math.max(0, 100 - x.usedPercent) : null;
const p = s.rateLimits && s.rateLimits.primary;
const w = s.rateLimits && s.rateLimits.secondary;
const out = {
  codexHome: home,
  usageSource: result.source,
  model: s.model || null,
  reasoningEffort: s.reasoningEffort || null,
  remaining5h: rem(p),
  remaining7d: rem(w),
  reset5h: p && p.resetsAt ? new Date(p.resetsAt * 1000).toISOString() : null,
  reset7d: w && w.resetsAt ? new Date(w.resetsAt * 1000).toISOString() : null,
  historyFile: history,
  historyExists: fs.existsSync(history)
};
console.log(JSON.stringify(out, null, 2));
