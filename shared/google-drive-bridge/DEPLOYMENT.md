# Deployment standard

Each client project gets a separate Apps Script deployment built from the same bridge source.

## Per-project required inputs

- `PROJECT_ID`
- `ARCHIVE_ROOT_ID`
- `ARCHIVE_ROOT_NAME`
- `MCP_DRIVE_BRIDGE_SECRET` Script Property
- project-specific Yandex Lockbox secret binding
- project-specific Apps Script `/exec` URL

## Required Web App settings

- Execute as: owner (`Me`)
- Access: callable by the Yandex workload without interactive Google login
- Authentication: bridge shared secret + project/root validation

## Secret flow

```text
Apps Script Script Property
  MCP_DRIVE_BRIDGE_SECRET
        ↓ bootstrap only
project-specific temporary CI secret
        ↓
project-specific Yandex Lockbox
        ↓
project runtime secret env/binding
```

The temporary CI secret is not a runtime source of truth and should be deleted after successful bootstrap.

## Runtime configuration contract

Recommended generic names for new clients:

```text
GDRIVE_BRIDGE_URL
GDRIVE_BRIDGE_SECRET
GDRIVE_BRIDGE_PROJECT_ID
GDRIVE_BRIDGE_ROOT_ID
```

Existing clients may keep legacy environment-variable names during migration, but adapters must map them into the protocol v1 client configuration.

## Release discipline

Each deployment must report:
- `protocol_version`
- `bridge_release`
- `project_id`
- `root_id`
- supported capabilities

Do not cut over a client if its bridge release fails the common acceptance matrix.
