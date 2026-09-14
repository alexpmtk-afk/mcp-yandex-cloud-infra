/**
 * Manual setup helpers for a project-specific deployment.
 *
 * Add exactly one project config file defining BRIDGE_DEPLOYMENT_CONFIG,
 * then run installBridgeConfig() once from the Apps Script editor.
 * Run createBridgeSecretOnce() only when bootstrapping/rotating the secret.
 */
function installBridgeConfig() {
  if (typeof BRIDGE_DEPLOYMENT_CONFIG !== 'object' || !BRIDGE_DEPLOYMENT_CONFIG) {
    throw new Error('BRIDGE_DEPLOYMENT_CONFIG is missing');
  }
  const c = BRIDGE_DEPLOYMENT_CONFIG;
  if (!c.projectId || !c.rootId || !c.rootName) throw new Error('deployment config is incomplete');
  const props = PropertiesService.getScriptProperties();
  props.setProperties({
    MCP_DRIVE_BRIDGE_PROJECT_ID: String(c.projectId),
    MCP_DRIVE_BRIDGE_ROOT_ID: String(c.rootId),
    MCP_DRIVE_BRIDGE_ROOT_NAME: String(c.rootName),
    MCP_DRIVE_BRIDGE_SHEETS_ENABLED: c.sheetsEnabled ? 'true' : 'false',
    MCP_DRIVE_BRIDGE_SMALL_MAX_BYTES: String(c.smallMaxBytes || 5242880)
  }, false);
  const root = DriveApp.getFolderById(String(c.rootId));
  if (root.getName() !== String(c.rootName)) throw new Error('wrong_root');
  return {
    configured: true,
    project_id: String(c.projectId),
    root_id: root.getId(),
    root_name: root.getName(),
    sheets_enabled: Boolean(c.sheetsEnabled),
    secret_present: Boolean(props.getProperty('MCP_DRIVE_BRIDGE_SECRET'))
  };
}

function createBridgeSecretOnce() {
  const props = PropertiesService.getScriptProperties();
  const existing = String(props.getProperty('MCP_DRIVE_BRIDGE_SECRET') || '').trim();
  if (existing) {
    return {created: false, secret: existing, length: existing.length};
  }
  const secret = [Utilities.getUuid(), Utilities.getUuid(), Utilities.getUuid()]
    .join('')
    .replace(/-/g, '');
  props.setProperty('MCP_DRIVE_BRIDGE_SECRET', secret);
  return {created: true, secret: secret, length: secret.length};
}

function rotateBridgeSecret() {
  const secret = [Utilities.getUuid(), Utilities.getUuid(), Utilities.getUuid()]
    .join('')
    .replace(/-/g, '');
  PropertiesService.getScriptProperties().setProperty('MCP_DRIVE_BRIDGE_SECRET', secret);
  return {rotated: true, secret: secret, length: secret.length};
}

function bridgeSetupCheck() {
  const cfg = config_();
  const result = health_(cfg);
  if (result.project_id !== cfg.projectId || result.root_id !== cfg.rootId) {
    throw new Error('bridge_setup_check_failed');
  }
  return result;
}
