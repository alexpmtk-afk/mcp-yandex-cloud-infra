from pathlib import Path

REPLACEMENTS = {
    '.github/workflows/marketplaces-drive-bridge-v1-acceptance.yml': {
        'LOCKBOX_NAME: marketplaces-google-drive-bridge-v1': 'LOCKBOX_NAME: marketplaces-mcp-api-credentials',
        'LOCKBOX_KEY: gdrive_bridge_secret': 'LOCKBOX_KEY: gdrive_bridge_v1_secret',
        'Resolve dedicated Bridge v1 credential': 'Resolve Marketplaces project Bridge v1 credential',
        'DEDICATED_MARKETPLACES_BRIDGE_CREDENTIAL=RESOLVED': 'MARKETPLACES_PROJECT_BRIDGE_V1_CREDENTIAL=RESOLVED',
    },
    '.github/workflows/birzha-drive-bridge-v1-acceptance.yml': {
        'LOCKBOX_NAME: birzha-google-drive-bridge-v1': 'LOCKBOX_NAME: birzha-mcp-forecast-test-auth',
        'LOCKBOX_KEY: gdrive_bridge_secret': 'LOCKBOX_KEY: gdrive_bridge_v1_secret',
        'Resolve dedicated Birzha Bridge credential': 'Resolve Birzha project Bridge v1 credential',
        'DEDICATED_BIRZHA_BRIDGE_CREDENTIAL=RESOLVED': 'BIRZHA_PROJECT_BRIDGE_V1_CREDENTIAL=RESOLVED',
    },
    '.github/workflows/marketplaces-drive-bridge-v1-cutover-gate.yml': {
        'LOCKBOX_NAME: marketplaces-google-drive-bridge-v1': 'LOCKBOX_NAME: marketplaces-mcp-api-credentials',
    },
    '.github/workflows/birzha-drive-bridge-v1-cutover-gate.yml': {
        'LOCKBOX_NAME: birzha-google-drive-bridge-v1': 'LOCKBOX_NAME: birzha-mcp-forecast-test-auth',
    },
    'shared/google-drive-bridge/EXTERNAL_OWNER_GATES.md': {
        'new dedicated Yandex Lockbox creation': 'new dedicated Yandex Lockbox creation (no longer required: v1 uses a new key in each already-isolated project Lockbox)',
    },
}

for filename, replacements in REPLACEMENTS.items():
    p = Path(filename)
    if not p.exists():
        if filename.endswith('EXTERNAL_OWNER_GATES.md'):
            continue
        raise SystemExit(f'missing file: {filename}')
    s = p.read_text(encoding='utf-8')
    for old, new in replacements.items():
        if old not in s and new not in s:
            raise SystemExit(f'expected token missing in {filename}: {old}')
        s = s.replace(old, new)
    p.write_text(s, encoding='utf-8')

# Runtime must consume only the new v1 key; the old key remains intact for legacy rollback.
p = Path('terraform/birzha_test/m25_market_mirror.tf')
s = p.read_text(encoding='utf-8')
s = s.replace(
    'Dedicated Birzha Google Drive Bridge v1 Lockbox secret ID. Must never reference the Marketplaces Lockbox.',
    'Birzha project Lockbox secret ID containing the isolated gdrive_bridge_v1_secret key. Must never reference the Marketplaces Lockbox.',
)
s = s.replace(
    'Dedicated Birzha Google Drive Bridge v1 Lockbox version ID.',
    'Birzha project Lockbox version ID containing gdrive_bridge_v1_secret.',
)
p.write_text(s, encoding='utf-8')

print('BRIDGE_V1_WORKFLOW_MIGRATION_PATCH=PASS')
