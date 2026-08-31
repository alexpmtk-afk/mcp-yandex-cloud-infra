'use strict';

const { classify } = require('./router-core');

function extractPrompt(params) {
  const input = params && Array.isArray(params.input) ? params.input : [];
  return input
    .filter((item) => item && item.type === 'text' && typeof item.text === 'string')
    .map((item) => item.text)
    .join('\n')
    .trim();
}

function currentModelFromParams(params) {
  if (!params || typeof params !== 'object') return null;
  if (typeof params.model === 'string' && params.model) return params.model;
  const cm = params.collaborationMode;
  if (cm && cm.settings && typeof cm.settings.model === 'string') return cm.settings.model;
  return null;
}

function applyRouteToParams(params, route) {
  const next = { ...(params || {}) };
  next.model = route.model;
  next.effort = route.effort;

  // Codex documents collaborationMode as taking precedence over model/effort.
  // Preserve the selected mode and developer instructions, but route its model
  // settings too so Desktop requests cannot silently override the router.
  if (next.collaborationMode && typeof next.collaborationMode === 'object') {
    const cm = { ...next.collaborationMode };
    const settings = { ...(cm.settings || {}) };
    settings.model = route.model;
    settings.reasoning_effort = route.effort;
    cm.settings = settings;
    next.collaborationMode = cm;
  }

  return next;
}

function rewriteClientMessage(message, { policy, usage = null, nowMs = Date.now() } = {}) {
  if (!message || typeof message !== 'object' || message.method !== 'turn/start') {
    return { message, routed: false, decision: null, prompt: '' };
  }
  if (!policy) throw new Error('policy is required');

  const params = message.params && typeof message.params === 'object' ? message.params : {};
  const prompt = extractPrompt(params);
  if (!prompt) return { message, routed: false, decision: null, prompt: '' };

  const currentModel = currentModelFromParams(params);
  const decision = classify({ prompt, currentModel, usage, policy, nowMs });
  const routedParams = applyRouteToParams(params, decision.route);

  return {
    message: { ...message, params: routedParams },
    routed: true,
    decision,
    prompt
  };
}

module.exports = {
  applyRouteToParams,
  currentModelFromParams,
  extractPrompt,
  rewriteClientMessage
};
