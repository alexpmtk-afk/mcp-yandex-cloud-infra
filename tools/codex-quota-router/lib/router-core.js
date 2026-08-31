'use strict';

const crypto = require('node:crypto');

const MODEL_RANK = { luna: 1, terra: 2, sol: 3 };

const KEYWORDS = {
  low: [
    /\bstatus\b/i, /\bdiff\b/i, /\blog\b/i, /\blist\b/i, /\bread\b/i,
    /покажи/i, /прочитай/i, /посмотри/i, /статус/i, /список/i, /коммит/i
  ],
  medium: [
    /\bfix\b/i, /\bdebug\b/i, /\btest\b/i, /\bintegrat/i, /\brefactor\b/i,
    /исправ/i, /отлад/i, /тест/i, /интеграц/i, /рефактор/i, /mcp/i, /github/i
  ],
  heavy: [
    /\bdeploy\b/i, /\bmigrat/i, /\barchitect/i, /\bproduction\b/i,
    /\bfull regression\b/i, /\bfull audit\b/i, /\bmulti[- ]?repo\b/i,
    /разверн/i, /миграц/i, /архитект/i, /продакш/i, /полный аудит/i,
    /полный регресс/i, /нескольк.*репозитор/i, /yandex cloud/i, /cloud/i
  ],
  critical: [
    /\bdestructive\b/i, /\bsecurity\b/i, /\bcredential/i, /\bsecret/i,
    /\bdatabase migration\b/i, /\bdelete\b/i, /\bdrop\b/i,
    /безопасност/i, /секрет/i, /удал/i, /деструктив/i, /баз.*данн.*миграц/i
  ]
};

function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }

function scorePrompt(prompt) {
  const text = String(prompt || '');
  let score = 12;
  const len = text.length;
  if (len > 500) score += 6;
  if (len > 1500) score += 8;
  if (len > 4000) score += 8;

  const counts = {};
  for (const [group, patterns] of Object.entries(KEYWORDS)) {
    counts[group] = patterns.filter((re) => re.test(text)).length;
  }
  score += Math.min(8, counts.low * 1);
  score += Math.min(18, counts.medium * 4);
  score += Math.min(36, counts.heavy * 10);
  score += Math.min(30, counts.critical * 10);
  if (counts.heavy >= 3) score += 20;
  if (counts.critical >= 2) score += 12;

  const systems = ['github', 'mcp', 'yandex', 'cloud', 'docker', 'terraform', 'drive', 'database', 'redis', 'valkey', 'api']
    .filter((x) => text.toLowerCase().includes(x));
  if (systems.length >= 3) score += 8;
  if (systems.length >= 5) score += 8;

  if (/\b(проведи|сделай|реализуй|исправь|разверни|перепиши)\b/i.test(text)) score += 4;
  const architectureSignal = /architect|архитект|redesign|перепроект/i.test(text);
  const migrationSignal = /migrat|миграц|deploy|разверн|production|продакш/i.test(text);
  if (architectureSignal && migrationSignal) score = Math.max(score, 84);
  if (/\b(только|лишь|один|одну|одного|кратко|quick|single)\b/i.test(text) && counts.heavy === 0) score -= 5;

  return { score: clamp(score, 0, 100), counts, systems };
}

function routeForScore(score, policy) {
  const t = policy.thresholds;
  if (score >= t.solHigh) return { model: 'gpt-5.6-sol', effort: 'high', tier: 'sol' };
  if (score >= t.solMedium) return { model: 'gpt-5.6-sol', effort: 'medium', tier: 'sol' };
  if (score >= t.terraMedium) return { model: 'gpt-5.6-terra', effort: 'medium', tier: 'terra' };
  if (score >= t.lunaMedium) return { model: 'gpt-5.6-luna', effort: 'medium', tier: 'luna' };
  return { model: 'gpt-5.6-luna', effort: 'low', tier: 'luna' };
}

function tierOfModel(model) {
  const m = String(model || '').toLowerCase();
  if (m.includes('luna')) return 'luna';
  if (m.includes('terra')) return 'terra';
  if (m.includes('sol') || m === 'gpt-5.6' || m.endsWith('/gpt-5.6')) return 'sol';
  return 'unknown';
}

function remaining(limit) {
  if (!limit || typeof limit.usedPercent !== 'number') return null;
  return clamp(100 - limit.usedPercent, 0, 100);
}

function minutesUntilReset(limit, nowMs = Date.now()) {
  if (!limit || !limit.resetsAt) return null;
  const resetMs = Number(limit.resetsAt) * 1000;
  if (!Number.isFinite(resetMs)) return null;
  return Math.max(0, Math.round((resetMs - nowMs) / 60000));
}

function quotaState(usage, policy, nowMs = Date.now()) {
  const primary = usage && usage.rateLimits ? usage.rateLimits.primary : null;
  const secondary = usage && usage.rateLimits ? usage.rateLimits.secondary : null;
  const pRem = remaining(primary);
  const sRem = remaining(secondary);
  const pReset = minutesUntilReset(primary, nowMs);
  const sReset = minutesUntilReset(secondary, nowMs);
  const q = policy.quota;

  const primaryCritical = pRem !== null && pRem <= q.critical5hRemaining && !(pReset !== null && pReset <= q.resetSoonMinutes);
  const weeklyCritical = sRem !== null && sRem <= q.criticalWeeklyRemaining && !(sReset !== null && sReset <= q.resetSoonMinutes);
  const primaryLow = pRem !== null && pRem <= q.low5hRemaining && (pReset === null || pReset > q.resetSoonMinutes);
  const weeklyLow = sRem !== null && sRem <= q.lowWeeklyRemaining && (sReset === null || sReset > q.resetSoonMinutes);

  return { primary, secondary, pRem, sRem, pReset, sReset, primaryCritical, weeklyCritical, primaryLow, weeklyLow };
}

function classify({ prompt, currentModel, usage, policy, nowMs = Date.now() }) {
  const scored = scorePrompt(prompt);
  const route = routeForScore(scored.score, policy);
  const quota = quotaState(usage, policy, nowMs);
  const force = policy.behavior.allowForceMarker && String(prompt || '').includes(policy.behavior.forceMarker);

  let quotaBlock = false;
  let quotaReason = null;

  if (!force && policy.behavior.blockHeavyWhenQuotaCritical) {
    if ((quota.primaryCritical || quota.weeklyCritical) && scored.score >= policy.thresholds.lunaMedium) {
      quotaBlock = true;
      quotaReason = quota.primaryCritical ? '5-hour quota is critical' : 'weekly quota is critical';
    } else if ((quota.primaryLow || quota.weeklyLow) && scored.score >= policy.thresholds.terraMedium) {
      quotaBlock = true;
      quotaReason = quota.primaryLow ? '5-hour quota is low for a heavy task' : 'weekly quota is low for a heavy task';
    }
  }

  const currentTier = tierOfModel(currentModel);
  const targetTier = route.tier;
  const currentRank = MODEL_RANK[currentTier] || 0;
  const targetRank = MODEL_RANK[targetTier] || 0;

  let modelMismatch = false;
  let mismatchDirection = null;
  if (!force && policy.behavior.enforceModelMatch && currentTier !== 'unknown' && targetTier !== 'unknown' && currentTier !== targetTier) {
    modelMismatch = true;
    mismatchDirection = currentRank > targetRank ? 'downgrade' : 'upgrade';
  }

  const block = quotaBlock || modelMismatch;
  return {
    score: scored.score,
    signals: scored,
    route,
    quota,
    currentModel,
    currentTier,
    force,
    block,
    quotaBlock,
    quotaReason,
    modelMismatch,
    mismatchDirection
  };
}

function shortQuota(q) {
  const parts = [];
  if (q.pRem !== null) parts.push(`5h ${q.pRem.toFixed(1)}% left${q.pReset !== null ? `, reset ~${q.pReset}m` : ''}`);
  if (q.sRem !== null) parts.push(`7d ${q.sRem.toFixed(1)}% left${q.sReset !== null ? `, reset ~${q.sReset}m` : ''}`);
  return parts.length ? parts.join('; ') : 'quota data unavailable';
}

function makeBlockReason(decision, policy) {
  const quota = shortQuota(decision.quota);
  if (decision.quotaBlock) {
    return `QUOTA GUARD: blocked before model work. ${decision.quotaReason}. ${quota}. Recommended route: ${decision.route.model} / ${decision.route.effort}. If this task is urgent and you intentionally accept quota use, resend with ${policy.behavior.forceMarker}.`;
  }
  const verb = decision.mismatchDirection === 'downgrade' ? 'save quota' : 'raise capability';
  return `QUOTA ROUTER: switch model before expensive work to ${verb}. Current: ${decision.currentModel}. Recommended: ${decision.route.model} / ${decision.route.effort}. Task score: ${decision.score}/100. ${quota}. After switching, resend the same request. Use ${policy.behavior.forceMarker} only to intentionally bypass routing.`;
}

function makeAdditionalContext(decision) {
  return `Quota Router preflight: route=${decision.route.model}/${decision.route.effort}; task_score=${decision.score}/100; ${shortQuota(decision.quota)}. Use targeted reads/tests first; avoid repeated full scans and unnecessary parallel agents.`;
}

function promptHash(prompt) {
  return crypto.createHash('sha256').update(String(prompt || '')).digest('hex').slice(0, 16);
}

module.exports = {
  classify,
  makeAdditionalContext,
  makeBlockReason,
  minutesUntilReset,
  promptHash,
  quotaState,
  routeForScore,
  scorePrompt,
  shortQuota,
  tierOfModel
};
