from pathlib import Path

BRIDGE = Path('shared/google-drive-bridge/bridge.gs')
OLD = """function config_() {
  const props = PropertiesService.getScriptProperties();
  const secret = String(props.getProperty(PROP_SECRET) || '').trim();
  const projectId = String(props.getProperty(PROP_PROJECT) || '').trim();
  const rootId = String(props.getProperty(PROP_ROOT_ID) || '').trim();
  const rootName = String(props.getProperty(PROP_ROOT_NAME) || '').trim();
  if (!secret || !projectId || !rootId || !rootName) throw bridgeError_('NOT_CONFIGURED', 'bridge Script Properties are incomplete', false);
  const root = DriveApp.getFolderById(rootId);
  if (root.getName() !== rootName) throw bridgeError_('WRONG_ROOT', 'configured root name does not match Drive', false);
  const maxRaw = Number(props.getProperty(PROP_SMALL_MAX) || DEFAULT_SMALL_MAX);
  const maxBytes = Number.isFinite(maxRaw) && maxRaw > 0 ? Math.floor(maxRaw) : DEFAULT_SMALL_MAX;
  const sheetsEnabled = String(props.getProperty(PROP_SHEETS) || 'false').toLowerCase() === 'true';
  return {secret: secret, projectId: projectId, rootId: rootId, rootName: rootName, maxBytes: maxBytes, sheetsEnabled: sheetsEnabled};
}
"""
NEW = """function config_() {
  const props = PropertiesService.getScriptProperties();
  const injected = (typeof BRIDGE_DEPLOYMENT_CONFIG === 'object' && BRIDGE_DEPLOYMENT_CONFIG) ? BRIDGE_DEPLOYMENT_CONFIG : {};
  const secret = String(props.getProperty(PROP_SECRET) || injected.secret || '').trim();
  const projectId = String(props.getProperty(PROP_PROJECT) || injected.projectId || '').trim();
  const rootId = String(props.getProperty(PROP_ROOT_ID) || injected.rootId || '').trim();
  const rootName = String(props.getProperty(PROP_ROOT_NAME) || injected.rootName || '').trim();
  if (!secret || !projectId || !rootId || !rootName) throw bridgeError_('NOT_CONFIGURED', 'bridge deployment configuration is incomplete', false);
  const root = DriveApp.getFolderById(rootId);
  if (root.getName() !== rootName) throw bridgeError_('WRONG_ROOT', 'configured root name does not match Drive', false);
  const maxRaw = Number(props.getProperty(PROP_SMALL_MAX) || injected.smallMaxBytes || DEFAULT_SMALL_MAX);
  const maxBytes = Number.isFinite(maxRaw) && maxRaw > 0 ? Math.floor(maxRaw) : DEFAULT_SMALL_MAX;
  const sheetsRaw = props.getProperty(PROP_SHEETS);
  const sheetsEnabled = sheetsRaw === null ? Boolean(injected.sheetsEnabled) : String(sheetsRaw).toLowerCase() === 'true';
  return {secret: secret, projectId: projectId, rootId: rootId, rootName: rootName, maxBytes: maxBytes, sheetsEnabled: sheetsEnabled};
}
"""

s = BRIDGE.read_text(encoding='utf-8')
if NEW not in s:
    if OLD not in s:
        raise SystemExit('canonical config_ block not found; refusing fuzzy patch')
    BRIDGE.write_text(s.replace(OLD, NEW, 1), encoding='utf-8')

for name in ('marketplaces_config.gs', 'birzha_config.gs'):
    p = Path('shared/google-drive-bridge/deploy') / name
    s = p.read_text(encoding='utf-8')
    if "secret: ''" not in s:
        marker = '  projectId:'
        if marker not in s:
            raise SystemExit(f'project config marker missing: {p}')
        s = s.replace(
            marker,
            "  // Secret value is injected only into the private Apps Script project at deploy time.\n  secret: '',\n  projectId:",
            1,
        )
        p.write_text(s, encoding='utf-8')

print('BRIDGE_V1_SOURCE_PATCH=PASS')
