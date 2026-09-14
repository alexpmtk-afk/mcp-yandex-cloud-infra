# Changelog

## 1.0.0-alpha.2

- Implemented `large_download_start` and `large_download_poll` through Google Drive `files.download` long-running operations.
- Added opaque server-side download tickets bound to a root-validated file and Drive operation.
- Kept Apps Script as control plane; large file bytes flow from Google download URI directly to the Yandex client.
- Added exact byte-count and SHA256 validation for large downloads.
- Added Google download URI host validation and no-logging rule.
- Added independent-resource concurrency acceptance and a live cross-project concurrency/root-isolation runner.
- Extended common acceptance so the same ~16 MiB fixture must pass resumable upload and verified direct download.

## 1.0.0-alpha.1

- Established multi-project isolation model.
- Defined protocol v1 envelope, idempotency and structured errors.
- Defined Drive file and Google Sheets capability sets.
- Added Marketplaces and Birzha client migration profiles.
- Added security/concurrency acceptance matrix.
