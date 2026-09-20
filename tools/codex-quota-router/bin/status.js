#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { codexHome, loadUsage } = require('../lib/usage');

const home = codexHome();
const installDir = path.join(home, 'quota-router');
const launcher = path.join(installDir, 'codex-router.exe');
const markerPath = path.join(installDir, 'standalone-install.json');
const historyPath = path.join(installDir, 'history.jsonl');
const usage = loadUsage(null);
const summary = usage.summary || {};
const primary = summary.rateLimits && summary.rateLimits.primary;
const secondary = summary.rateLimits && summary.rateLimits.secondary;
const lastRoute = readLastRoute(historyPath);
const marker = readJson(markerPath);
const configuredCliPath = process.env.CODEX_CLI_PATH || null;

const output = {
  routerVersion: (marker && marker.version) || '0.4.0',
  active: Boolean(fs.existsSync(launcher) && configuredCliPath && samePath(configuredCliPath, launcher)),
  launcherPath: fs.existsSync(launcher) ? launcher : null,
  realCodexPath: discoverRealCodex(),
  CODEX_CLI_PATH: configuredCliPath,
  lastModel: lastRoute ? lastRoute.selectedModel : null,
  lastEffort: lastRoute ? lastRoute.selectedEffort : null,
  lastScore: lastRoute ? lastRoute.score : null,
  remaining5h: remaining(primary),
  remaining7d: remaining(secondary),
  reset5h: resetIso(primary),
  reset7d: resetIso(secondary),
  quotaSource: usage.source,
  quotaFreshness: usage.observedAt,
  lastRouteTimestamp: lastRoute ? lastRoute.timestamp : null,
  historyPath
};

console.log(JSON.stringify(output, null, 2));

function remaining(limit) {
  return limit && typeof limit.usedPercent === 'number' ? Math.max(0, 100 - limit.usedPercent) : null;
}

function resetIso(limit) {
  return limit && Number.isFinite(Number(limit.resetsAt)) ? new Date(Number(limit.resetsAt) * 1000).toISOString() : null;
}

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); } catch { return null; }
}

function readLastRoute(file) {
  if (!fs.existsSync(file)) return null;
  try {
    const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean);
    for (let index = lines.length - 1; index >= 0; index -= 1) {
      const record = JSON.parse(lines[index]);
      if (record.event === 'proxy-route') return record;
    }
  } catch {}
  return null;
}

function discoverRealCodex() {
  if (process.env.CODEX_ROUTER_REAL_EXE && fs.existsSync(process.env.CODEX_ROUTER_REAL_EXE)) {
    return path.resolve(process.env.CODEX_ROUTER_REAL_EXE);
  }
  const local = process.env.LOCALAPPDATA;
  if (!local) return null;
  const root = path.join(local, 'OpenAI', 'Codex', 'bin');
  const candidates = [];
  walk(root, candidates);
  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs || b.file.localeCompare(a.file));
  return candidates.length ? candidates[0].file : null;
}

function walk(directory, outputFiles) {
  let entries;
  try { entries = fs.readdirSync(directory, { withFileTypes: true }); } catch { return; }
  for (const entry of entries) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(full, outputFiles);
    else if (entry.isFile() && entry.name.toLowerCase() === 'codex.exe' && !samePath(full, launcher)) {
      try { outputFiles.push({ file: full, mtimeMs: fs.statSync(full).mtimeMs }); } catch {}
    }
  }
}

function samePath(left, right) {
  try { return path.resolve(left).toLowerCase() === path.resolve(right).toLowerCase(); }
  catch { return false; }
}
