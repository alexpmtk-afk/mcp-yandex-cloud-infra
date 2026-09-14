variable "m25_market_mirror_bridge_url" {
  description = "Existing shared Google Apps Script Web App URL. Null keeps BIRZHA mirror calls disabled until the Birzha addon is deployed into that project."
  type        = string
  default     = null
  nullable    = true
}

variable "m25_market_mirror_required" {
  description = "Fail closed when verified persistent D1 history cannot be mirrored to Google Sheets. Enable only after the shared Apps Script has the Birzha addon and live E2E passes."
  type        = bool
  default     = false
}

variable "m25_market_mirror_root_folder_id" {
  description = "Existing Google Drive folder id for Биржа/Архив рыночных данных."
  type        = string
  default     = "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2"
}

variable "m25_shared_drive_bridge_secret_id" {
  description = "Existing Marketplaces Lockbox secret containing google_drive_bridge_secret. BIRZHA reuses it; Terraform never reads the payload."
  type        = string
  default     = "e6qb8b3u57e71731j1os"
}

variable "m25_shared_drive_bridge_secret_version_id" {
  description = "Active version id of the existing shared Drive bridge secret. Supply only when enabling the Birzha bridge binding."
  type        = string
  default     = null
  nullable    = true
}

resource "yandex_lockbox_secret_iam_member" "runtime_market_mirror" {
  count       = var.m25_market_mirror_bridge_url == null ? 0 : 1
  secret_id   = var.m25_shared_drive_bridge_secret_id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${yandex_iam_service_account.runtime.id}"
  sleep_after = 10
}

output "m25_shared_drive_bridge_secret_id" {
  description = "Existing shared Lockbox secret reused by BIRZHA. No second bridge secret is created."
  value       = var.m25_shared_drive_bridge_secret_id
}
