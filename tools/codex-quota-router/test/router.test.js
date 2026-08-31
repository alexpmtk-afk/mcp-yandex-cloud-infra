'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { classify, scorePrompt, tierOfModel } = require('../lib/router-core');
const policy = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'policy.json'), 'utf8'));
const now = 1_800_000_000_000;
const future = (m) => Math.floor((now + m*60000)/1000);
function usage(pUsed=20,sUsed=10,pReset=240,sReset=5000){ return {rateLimits:{primary:{usedPercent:pUsed,resetsAt:future(pReset)},secondary:{usedPercent:sUsed,resetsAt:future(sReset)}}}; }

assert.equal(tierOfModel('gpt-5.6-luna'),'luna');
assert.equal(tierOfModel('gpt-5.6-terra'),'terra');
assert.equal(tierOfModel('gpt-5.6-sol'),'sol');
assert.ok(scorePrompt('Покажи последний commit и статус workflow').score < 56);
assert.ok(scorePrompt('Проведи архитектурный redesign, миграцию базы, deployment production и полный regression').score >= 82);

let d = classify({prompt:'Покажи последний commit и статус workflow', currentModel:'gpt-5.6-luna', usage:usage(), policy, nowMs:now});
assert.equal(d.block,false);
assert.equal(d.route.tier,'luna');

d = classify({prompt:'Найди и исправь сложную интеграционную ошибку MCP между GitHub, Yandex Cloud и API, затем протестируй', currentModel:'gpt-5.6-luna', usage:usage(), policy, nowMs:now});
assert.equal(d.block,true);
assert.ok(['terra','sol'].includes(d.route.tier));

d = classify({prompt:'Проведи полный аудит, deployment и regression по GitHub, MCP и Yandex Cloud', currentModel:'gpt-5.6-terra', usage:usage(93,20,180,5000), policy, nowMs:now});
assert.equal(d.quotaBlock,true);
assert.equal(d.block,true);

d = classify({prompt:'Проведи полный аудит, deployment и regression по GitHub, MCP и Yandex Cloud QUOTA_FORCE', currentModel:'gpt-5.6-terra', usage:usage(93,20,180,5000), policy, nowMs:now});
assert.equal(d.force,true);
assert.equal(d.quotaBlock,false);

console.log('router tests: PASS');
