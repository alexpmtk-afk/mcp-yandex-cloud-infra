import crypto from 'node:crypto';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

function encodeJson(value) {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

async function getIamToken(key) {
  const now = Math.floor(Date.now() / 1000);
  const unsigned = `${encodeJson({ alg: 'PS256', typ: 'JWT', kid: key.id })}.${encodeJson({
    aud: 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
    iss: key.service_account_id,
    iat: now,
    exp: now + 3600,
  })}`;
  const signature = crypto.sign('sha256', Buffer.from(unsigned), {
    key: key.private_key,
    padding: crypto.constants.RSA_PKCS1_PSS_PADDING,
    saltLength: 32,
  }).toString('base64url');
  const jwt = `${unsigned}.${signature}`;
  const response = await fetch('https://iam.api.cloud.yandex.net/iam/v1/tokens', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jwt }),
  });
  if (!response.ok) throw new Error(`IAM token HTTP ${response.status}: ${await response.text()}`);
  const payload = await response.json();
  if (!payload.iamToken) throw new Error('IAM token missing');
  return payload.iamToken;
}

async function getMcpToken(iamToken) {
  const secretId = process.env.MCP_AUTH_SECRET_ID;
  const versionId = process.env.MCP_AUTH_VERSION_ID;
  const url = `https://payload.lockbox.api.cloud.yandex.net/lockbox/v1/secrets/${encodeURIComponent(secretId)}/payload?versionId=${encodeURIComponent(versionId)}`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${iamToken}` } });
  if (!response.ok) throw new Error(`Lockbox HTTP ${response.status}: ${await response.text()}`);
  const payload = await response.json();
  const entry = (payload.entries || []).find((item) => item.key === 'bearer_token');
  if (!entry?.textValue) throw new Error('bearer_token missing in Lockbox payload');
  return entry.textValue;
}

function resultSummary(result) {
  return {
    isError: Boolean(result.isError),
    structured: result.structuredContent ?? null,
    text: (result.content || []).map((item) => item?.text).filter(Boolean),
  };
}

async function call(client, name, args) {
  try {
    return resultSummary(await client.callTool({ name, arguments: args }));
  } catch (error) {
    return { thrown: true, errorType: error?.constructor?.name || 'Error', error: String(error?.message || error) };
  }
}

const key = JSON.parse(process.env.YC_SERVICE_ACCOUNT_KEY_JSON || '{}');
if (!key.id || !key.service_account_id || !key.private_key) throw new Error('YC service account key fields missing');
const iamToken = await getIamToken(key);
const mcpToken = await getMcpToken(iamToken);

const transport = new StreamableHTTPClientTransport(new URL(process.env.MCP_ENDPOINT), {
  requestInit: { headers: { Authorization: `Bearer ${mcpToken}` } },
});
const client = new Client({ name: 'birzha-history-diag', version: '1.0.0' }, { capabilities: {} });
await client.connect(transport);

const probes = {};
probes.resolve = await call(client, 'market.resolve_instrument', { symbol: 'SBER' });
probes.candles = await call(client, 'market.candles', {
  symbol: 'SBER', timeframe: 'D1', from_date: '2026-09-01', till_date: '2026-09-05', completed_only: true,
});
probes.coverage = await call(client, 'history.coverage', { secid: 'SBER', timeframe: 'D1' });
probes.sync = await call(client, 'history.sync', {
  symbol: 'SBER', timeframe: 'D1', from_date: '2026-09-01', till_date: '2026-09-05',
});
await client.close();

const calendarUrl = 'https://iss.moex.com/iss/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json?iss.meta=off&iss.only=history,history.cursor&history.columns=TRADEDATE&from=2026-09-01&till=2026-09-05';
const calendarResponse = await fetch(calendarUrl);
if (!calendarResponse.ok) throw new Error(`MOEX calendar HTTP ${calendarResponse.status}`);
const calendarPayload = await calendarResponse.json();
const calendarRows = calendarPayload?.history?.data?.length || 0;

const safe = {
  resolve: probes.resolve,
  candles: probes.candles?.structured ? {
    isError: probes.candles.isError,
    count: probes.candles.structured.count,
    secid: probes.candles.structured.instrument?.secid,
  } : probes.candles,
  coverage: probes.coverage,
  sync: probes.sync,
  rawMoexCalendarRows: calendarRows,
};
console.log(`BIRZHA_HISTORY_PROBES=${JSON.stringify(safe)}`);
if (calendarRows <= 0) process.exitCode = 2;
