/**
 * One-time owner bootstrap for Google Drive Bridge v1.
 *
 * This file is deployed only for the bootstrap version and is removed before
 * the final Bridge v1.0.0 deployment. BRIDGE_BOOTSTRAP_CONFIG contains only
 * a disposable bootstrap token and non-secret project/root metadata.
 * The durable Bridge secret is accepted only in the POST body and is written
 * directly to Script Properties; it is never embedded in Apps Script source.
 */

function bootstrapJson_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}

function bootstrapError_(code, message) {
  return {ok: false, phase: 'bootstrap', error: {code: code, message: message}};
}

function bootstrapConfig_() {
  if (typeof BRIDGE_BOOTSTRAP_CONFIG !== 'object' || !BRIDGE_BOOTSTRAP_CONFIG) {
    throw new Error('BOOTSTRAP_CONFIG_MISSING');
  }
  const cfg = BRIDGE_BOOTSTRAP_CONFIG;
  const token = String(cfg.token || '').trim();
  const projectId = String(cfg.projectId || '').trim();
  const rootId = String(cfg.rootId || '').trim();
  const rootName = String(cfg.rootName || '').trim();
  if (!token || token.length < 40 || !projectId || !rootId || !rootName) {
    throw new Error('BOOTSTRAP_CONFIG_INVALID');
  }
  return {
    token: token,
    projectId: projectId,
    rootId: rootId,
    rootName: rootName,
    sheetsEnabled: Boolean(cfg.sheetsEnabled),
    smallMaxBytes: Number(cfg.smallMaxBytes || 5242880)
  };
}

function bootstrapAssertToken_(provided, cfg) {
  const value = String(provided || '').trim();
  if (!value || value !== cfg.token) throw new Error('BOOTSTRAP_UNAUTHORIZED');
}

function bootstrapValidateRoot_(cfg) {
  const root = DriveApp.getFolderById(cfg.rootId);
  const actualName = root.getName();
  if (actualName !== cfg.rootName) throw new Error('BOOTSTRAP_WRONG_ROOT');
  return {id: root.getId(), name: actualName};
}

function doGet(e) {
  try {
    const cfg = bootstrapConfig_();
    bootstrapAssertToken_(e && e.parameter && e.parameter.bootstrap_token, cfg);
    const root = bootstrapValidateRoot_(cfg);
    return bootstrapJson_({
      ok: true,
      phase: 'bootstrap_authorized',
      project_id: cfg.projectId,
      root_id: root.id,
      root_name: root.name,
      sheets_enabled: cfg.sheetsEnabled
    });
  } catch (err) {
    return bootstrapJson_(bootstrapError_(String(err && err.message || 'BOOTSTRAP_FAILED'), 'bootstrap authorization failed'));
  }
}

function doPost(e) {
  let body = {};
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const cfg = bootstrapConfig_();
    bootstrapAssertToken_(body.bootstrap_token, cfg);
    if (String(body.action || '') !== 'bootstrap_install') throw new Error('BOOTSTRAP_BAD_ACTION');
    const secret = String(body.secret || '').trim();
    if (secret.length < 48) throw new Error('BOOTSTRAP_SECRET_INVALID');
    const root = bootstrapValidateRoot_(cfg);

    const lock = LockService.getScriptLock();
    lock.waitLock(30000);
    try {
      const props = PropertiesService.getScriptProperties();
      const current = {
        secret: String(props.getProperty('MCP_DRIVE_BRIDGE_SECRET') || ''),
        projectId: String(props.getProperty('MCP_DRIVE_BRIDGE_PROJECT_ID') || ''),
        rootId: String(props.getProperty('MCP_DRIVE_BRIDGE_ROOT_ID') || ''),
        rootName: String(props.getProperty('MCP_DRIVE_BRIDGE_ROOT_NAME') || '')
      };
      const alreadyConfigured = Boolean(current.secret || current.projectId || current.rootId || current.rootName);
      if (alreadyConfigured) {
        const same = current.secret === secret &&
          current.projectId === cfg.projectId &&
          current.rootId === cfg.rootId &&
          current.rootName === cfg.rootName;
        if (!same) throw new Error('BOOTSTRAP_CONFIGURATION_CONFLICT');
        return bootstrapJson_({
          ok: true,
          phase: 'bootstrap_installed',
          project_id: cfg.projectId,
          root_id: root.id,
          replayed: true
        });
      }
      props.setProperties({
        MCP_DRIVE_BRIDGE_SECRET: secret,
        MCP_DRIVE_BRIDGE_PROJECT_ID: cfg.projectId,
        MCP_DRIVE_BRIDGE_ROOT_ID: cfg.rootId,
        MCP_DRIVE_BRIDGE_ROOT_NAME: cfg.rootName,
        MCP_DRIVE_BRIDGE_SMALL_MAX_BYTES: String(Math.floor(cfg.smallMaxBytes)),
        MCP_DRIVE_BRIDGE_SHEETS_ENABLED: cfg.sheetsEnabled ? 'true' : 'false'
      }, false);
      return bootstrapJson_({
        ok: true,
        phase: 'bootstrap_installed',
        project_id: cfg.projectId,
        root_id: root.id,
        replayed: false
      });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return bootstrapJson_(bootstrapError_(String(err && err.message || 'BOOTSTRAP_FAILED'), 'bootstrap install failed'));
  }
}
