'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function codexHome() { return process.env.CODEX_HOME || path.join(os.homedir(), '.codex'); }

function monitorScript() {
  return path.join(codexHome(), 'plugins', 'codex-usage-monitor', 'bin', 'codex-usage-monitor.js');
}

function loadUsage(transcriptPath) {
  const monitor = monitorScript();
  if (fs.existsSync(monitor)) {
    const args = [monitor, 'json'];
    if (transcriptPath) args.push('--file', transcriptPath);
    const out = spawnSync(process.execPath, args, { encoding: 'utf8', timeout: 5000, windowsHide: true });
    if (out.status === 0 && out.stdout) {
      try { return { source: 'codex-usage-monitor', summary: JSON.parse(out.stdout) }; } catch {}
    }
  }
  return { source: 'local-jsonl', summary: summarizeTail(transcriptPath) };
}

function summarizeTail(transcriptPath) {
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return null;
  let text;
  try {
    const stat = fs.statSync(transcriptPath);
    const max = 8 * 1024 * 1024;
    const start = Math.max(0, stat.size - max);
    const fd = fs.openSync(transcriptPath, 'r');
    const buf = Buffer.alloc(stat.size - start);
    fs.readSync(fd, buf, 0, buf.length, start);
    fs.closeSync(fd);
    text = buf.toString('utf8');
    if (start > 0) text = text.slice(text.indexOf('\n') + 1);
  } catch { return null; }

  let model = null;
  let effort = null;
  let latestUsage = null;
  let totalUsage = null;
  let rateLimits = { primary: null, secondary: null };
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    let rec; try { rec = JSON.parse(line); } catch { continue; }
    const p = rec && rec.payload && typeof rec.payload === 'object' ? rec.payload : {};
    if (rec.type === 'turn_context') {
      model = p.model || (p.collaboration_mode && p.collaboration_mode.settings && p.collaboration_mode.settings.model) || model;
      effort = p.effort || (p.collaboration_mode && p.collaboration_mode.settings && p.collaboration_mode.settings.reasoning_effort) || effort;
    }
    if (rec.type === 'event_msg' && p.type === 'token_count') {
      const info = p.info || {};
      latestUsage = info.last_token_usage || latestUsage;
      totalUsage = info.total_token_usage || totalUsage;
      rateLimits = normalizeRateLimits(p.rate_limits);
    }
  }
  return { model, reasoningEffort: effort, latestUsage, totalUsage, rateLimits };
}

function normalizeRateLimits(raw) {
  if (!raw || typeof raw !== 'object') return { primary: null, secondary: null };
  return { primary: normalizeLimit(raw.primary), secondary: normalizeLimit(raw.secondary) };
}
function normalizeLimit(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const used = Number(raw.used_percent);
  const mins = Number(raw.window_minutes);
  const resets = Number(raw.resets_at);
  return {
    label: mins === 300 ? '5h' : mins === 10080 ? '7d' : (Number.isFinite(mins) ? `${mins}m` : 'limit'),
    usedPercent: Number.isFinite(used) ? Math.round(used * 10) / 10 : null,
    windowMinutes: Number.isFinite(mins) ? mins : null,
    resetsAt: Number.isFinite(resets) ? resets : null
  };
}

function appendJsonl(file, record) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, JSON.stringify(record) + os.EOL, 'utf8');
}

module.exports = { appendJsonl, codexHome, loadUsage, monitorScript, summarizeTail };
