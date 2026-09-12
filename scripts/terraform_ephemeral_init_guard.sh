#!/usr/bin/env bash
set -euo pipefail

TF_DIR="${1:?terraform directory is required}"
EXPECTED_PROVIDER="${2:?provider source is required, e.g. yandex-cloud/yandex}"
EXPECTED_VERSION="${3:?provider version is required}"
LOCK_FILE="${TF_DIR}/.terraform.lock.hcl"

if [[ ! -f "${TF_DIR}/main.tf" ]]; then
  echo "EPHEMERAL_TERRAFORM_LOCK_GUARD=ERROR reason=main_tf_missing dir=${TF_DIR}" >&2
  exit 2
fi

# A fresh ephemeral directory has no dependency lock file by definition.
# Never use -lockfile=readonly until Terraform has materialized one.
if [[ ! -s "${LOCK_FILE}" ]]; then
  echo "EPHEMERAL_TERRAFORM_LOCK_MODE=CREATE"
  terraform -chdir="${TF_DIR}" init -backend=false -input=false
else
  echo "EPHEMERAL_TERRAFORM_LOCK_MODE=REUSE"
fi

if [[ ! -s "${LOCK_FILE}" ]]; then
  echo "EPHEMERAL_TERRAFORM_LOCK_GUARD=ERROR reason=lockfile_not_created" >&2
  exit 3
fi

python - "${LOCK_FILE}" "${EXPECTED_PROVIDER}" "${EXPECTED_VERSION}" <<'PY'
from pathlib import Path
import sys

lock_path = Path(sys.argv[1])
provider = sys.argv[2]
version = sys.argv[3]
text = lock_path.read_text(encoding="utf-8")
header = f'provider "registry.terraform.io/{provider}" {{'
if header not in text:
    raise SystemExit(f"expected provider missing from lockfile: {provider}")
block = text.split(header, 1)[1].split("}", 1)[0]
needle = f'version = "{version}"'
if needle not in block:
    raise SystemExit(
        f"provider version mismatch for {provider}: expected {version}"
    )
print(f"EPHEMERAL_TERRAFORM_PROVIDER_LOCK=PASS provider={provider} version={version}")
PY

# Prove the generated lock is now sufficient for a strict reproducible init.
terraform -chdir="${TF_DIR}" init -backend=false -input=false -lockfile=readonly
terraform -chdir="${TF_DIR}" validate

echo "EPHEMERAL_TERRAFORM_LOCK_GUARD=PASS"
