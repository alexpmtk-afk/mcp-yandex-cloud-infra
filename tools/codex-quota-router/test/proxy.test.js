'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { rewriteClientMessage } = require('../lib/proxy-core');

const policy = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'policy.json'), 'utf8'));

function turn(prompt, model = 'gpt-5.6-sol', effort = 'medium', withCollab = false) {
  const params = {
    threadId: 'old-thread-123',
    input: [{ type: 'text', text: prompt, text_elements: [] }],
    model,
    effort
  };
  if (withCollab) {
    params.collaborationMode = {
      mode: 'default',
      settings: {
        model,
        reasoning_effort: effort,
        developer_instructions: 'keep existing instructions'
      }
    };
  }
  return { method: 'turn/start', id: 7, params };
}

function routed(prompt, expectedModel, expectedEffort, withCollab = false) {
  const original = turn(prompt, 'gpt-5.6-sol', 'medium', withCollab);
  const result = rewriteClientMessage(original, { policy });
  assert.equal(result.routed, true, prompt);
  assert.equal(result.message.params.threadId, 'old-thread-123');
  assert.equal(result.message.params.model, expectedModel, prompt);
  assert.equal(result.message.params.effort, expectedEffort, prompt);
  assert.deepEqual(result.message.params.input, original.params.input);
  if (withCollab) {
    assert.equal(result.message.params.collaborationMode.mode, 'default');
    assert.equal(result.message.params.collaborationMode.settings.model, expectedModel);
    assert.equal(result.message.params.collaborationMode.settings.reasoning_effort, expectedEffort);
    assert.equal(result.message.params.collaborationMode.settings.developer_instructions, 'keep existing instructions');
  }
}

routed('Покажи список файлов в текущей папке. Ничего не изменяй.', 'gpt-5.6-luna', 'low', true);
routed('Исправь тест интеграции MCP и GitHub.', 'gpt-5.6-luna', 'medium');
routed('Найди и исправь сложную интеграционную ошибку MCP между GitHub, Yandex Cloud и API, затем протестируй.', 'gpt-5.6-terra', 'medium');
routed('Проведи архитектурный redesign и deployment production системы.', 'gpt-5.6-sol', 'medium');
routed('Проведи архитектурный redesign, migration и deployment production, полный security audit, проверь secrets и удали устаревшие данные.', 'gpt-5.6-sol', 'high');

const forced = turn('Покажи список файлов QUOTA_FORCE', 'gpt-5.6-sol', 'medium', true);
const forcedResult = rewriteClientMessage(forced, { policy });
assert.equal(forcedResult.routed, false);
assert.deepEqual(forcedResult.message, forced);

const notification = { method: 'initialized', params: {} };
const untouched = rewriteClientMessage(notification, { policy });
assert.equal(untouched.routed, false);
assert.deepEqual(untouched.message, notification);

const withoutSettings = turn('Покажи список файлов. Ничего не изменяй.');
withoutSettings.params.collaborationMode = { mode: 'default' };
const withoutSettingsResult = rewriteClientMessage(withoutSettings, { policy });
assert.deepEqual(withoutSettingsResult.message.params.collaborationMode, { mode: 'default' });

assert.throws(
  () => rewriteClientMessage(turn('Покажи список файлов.'), { policy: { thresholds: null } }),
  /Cannot read|incomplete/,
  'an invalid policy must fail instead of preserving the expensive model'
);

console.log('proxy tests: PASS');
