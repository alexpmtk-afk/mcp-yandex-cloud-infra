variable "m25_market_mirror_bridge_url" {
  description = "Deployed Google Apps Script Web App URL for the BIRZHA market-data mirror. Null keeps runtime mirror calls disabled."
  type        = string
  default     = null
  nullable    = true
}

variable "m25_market_mirror_required" {
  description = "Fail closed when verified persistent D1 history cannot be mirrored to Google Sheets. Enable only after the Apps Script bridge is deployed."
  type        = bool
  default     = false
}

variable "m25_market_mirror_root_folder_id" {
  description = "Existing Google Drive folder id for Биржа/Архив рыночных данных."
  type        = string
  default     = "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2"
}

resource "yandex_lockbox_secret" "market_mirror" {
  folder_id           = yandex_resourcemanager_folder.birzha_test.id
  name                = "birzha-market-mirror-bridge"
  description         = "Shared secret for BIRZHA Yandex runtime -> Google Apps Script market mirror bridge"
  deletion_protection = true
  labels              = local.labels

  password_payload_specification {
    password_key        = "bridge_secret"
    length              = 64
    include_uppercase   = true
    include_lowercase   = true
    include_digits      = true
    include_punctuation = false
  }
}

resource "yandex_lockbox_secret_version" "market_mirror" {
  secret_id = yandex_lockbox_secret.market_mirror.id
}

resource "yandex_lockbox_secret_iam_member" "runtime_market_mirror" {
  secret_id   = yandex_lockbox_secret.market_mirror.id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${yandex_iam_service_account.runtime.id}"
  sleep_after = 10
}

resource "yandex_lockbox_secret_iam_member" "deployer_market_mirror" {
  secret_id   = yandex_lockbox_secret.market_mirror.id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 10
}

output "m25_market_mirror_secret_id" {
  description = "Lockbox secret id whose bridge_secret value must also be set as Apps Script property BIRZHA_MARKET_MIRROR_SECRET."
  value       = yandex_lockbox_secret.market_mirror.id
}
