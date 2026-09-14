# M25 Google market mirror migration.
#
# Bridge v1 target is fully isolated from Marketplaces: its own Apps Script
# deployment, secret and Lockbox binding.  The legacy shared binding is retained
# temporarily and MUST NOT be removed until Birzha v1 live acceptance + cutover.

variable "m25_birzha_bridge_v1_url" {
  description = "Dedicated Birzha Google Drive Bridge v1 Apps Script /exec URL. Null keeps v1 disabled."
  type        = string
  default     = null
  nullable    = true
}

variable "m25_birzha_bridge_v1_required" {
  description = "Fail closed when persistent D1 cannot be mirrored through the dedicated Birzha Bridge v1. Enable only after live acceptance passes."
  type        = bool
  default     = false
}

variable "m25_birzha_bridge_v1_root_folder_id" {
  description = "Fixed Google Drive root for Birzha: Биржа/Архив рыночных данных."
  type        = string
  default     = "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2"
}

variable "m25_birzha_bridge_v1_secret_id" {
  description = "Dedicated Birzha Lockbox secret id containing the Bridge v1 shared secret. Never use the Marketplaces secret id here."
  type        = string
  default     = null
  nullable    = true
}

variable "m25_birzha_bridge_v1_secret_version_id" {
  description = "Active version id of the dedicated Birzha Bridge v1 Lockbox secret."
  type        = string
  default     = null
  nullable    = true
}

variable "m25_birzha_bridge_v1_chunk_rows" {
  description = "Maximum rows per Google Sheets Bridge v1 chunk."
  type        = number
  default     = 500

  validation {
    condition     = var.m25_birzha_bridge_v1_chunk_rows >= 1 && var.m25_birzha_bridge_v1_chunk_rows <= 1000
    error_message = "m25_birzha_bridge_v1_chunk_rows must be 1..1000."
  }
}

resource "yandex_lockbox_secret_iam_member" "runtime_market_mirror_v1" {
  count       = var.m25_birzha_bridge_v1_url != null && var.m25_birzha_bridge_v1_secret_id != null ? 1 : 0
  secret_id   = var.m25_birzha_bridge_v1_secret_id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${yandex_iam_service_account.runtime.id}"
  sleep_after = 10
}

output "m25_birzha_bridge_v1_secret_id" {
  description = "Dedicated Birzha Bridge v1 Lockbox id when configured."
  value       = var.m25_birzha_bridge_v1_secret_id
}

# -----------------------------------------------------------------------------
# LEGACY SHARED MARKETPLACES ROUTE — RETAIN UNTIL EXPLICIT POST-CUTOVER CLEANUP.
# These variables/resources exist only so an eventual pre-cutover Terraform apply
# does not silently revoke the old runtime's access before Bridge v1 is accepted.
# No new Birzha runtime code should depend on them.
# -----------------------------------------------------------------------------

variable "m25_market_mirror_bridge_url" {
  description = "LEGACY: shared Marketplaces Apps Script URL. Do not use for new Birzha deployments."
  type        = string
  default     = null
  nullable    = true
}

variable "m25_market_mirror_required" {
  description = "LEGACY: old shared-route mirror requirement flag."
  type        = bool
  default     = false
}

variable "m25_market_mirror_root_folder_id" {
  description = "LEGACY: Birzha root used by the old Marketplaces bridge addon."
  type        = string
  default     = "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2"
}

variable "m25_shared_drive_bridge_secret_id" {
  description = "LEGACY: Marketplaces Lockbox secret id. Retained temporarily only for old-route IAM continuity."
  type        = string
  default     = "e6qb8b3u57e71731j1os"
}

variable "m25_shared_drive_bridge_secret_version_id" {
  description = "LEGACY: active Marketplaces shared Drive bridge secret version."
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
  description = "LEGACY Marketplaces bridge secret id; remove only after explicit cutover cleanup."
  value       = var.m25_shared_drive_bridge_secret_id
}
