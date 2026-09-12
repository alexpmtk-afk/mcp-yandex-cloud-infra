#!/usr/bin/env bash
set -euo pipefail

TF_DIR="${1:?terraform directory is required}"
EXPECTED_PROVIDER="${2:?provider source is required, e.g. yandex-cloud/yandex}"
EXPECTED_VERSION="${3:?provider version is required}"
LOCK_FILE="${TF_DIR}/.terraform.lock.hcl"
VERSION_JSON="${TF_DIR}/.terraform-version.json"

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

# Do not parse .terraform.lock.hcl text manually. Ask Terraform for the
# machine-readable provider selection so HCL formatting cannot break the guard.
terraform -chdir="${TF_DIR}" version -json > "${VERSION_JSON}"
python - "${VERSION_JSON}" "${EXPECTED_PROVIDER}" "${EXPECTED_VERSION}" <<'PY'
import json
from pathlib import Path
import sys

version_path = Path(sys.argv[1])
provider = sys.argv[2]
expected = sys.argv[3]
payload = json.loads(version_path.read_text(encoding="utf-8"))
address = f"registry.terraform.io/{provider}"
selected = (payload.get("provider_selections") or {}).get(address)
if selected != expected:
    raise SystemExit(
        f"provider selection mismatch for {provider}: expected {expected}, got {selected!r}"
    )
print(f"EPHEMERAL_TERRAFORM_PROVIDER_LOCK=PASS provider={provider} version={selected}")
PY
rm -f "${VERSION_JSON}"

# Prove the generated lock is now sufficient for a strict reproducible init.
terraform -chdir="${TF_DIR}" init -backend=false -input=false -lockfile=readonly
terraform -chdir="${TF_DIR}" validate

echo "EPHEMERAL_TERRAFORM_LOCK_GUARD=PASS"
