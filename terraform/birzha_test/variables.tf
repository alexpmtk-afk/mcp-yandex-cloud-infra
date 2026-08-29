variable "yc_cloud_id" {
  description = "Yandex Cloud cloud ID."
  type        = string
  default     = "b1gi4pr9msenirafh2c7"
}

variable "yc_service_account_key_file" {
  description = "Ephemeral path to the GitHub Actions service-account key file."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}

variable "yc_zone" {
  description = "Default Yandex Cloud availability zone."
  type        = string
  default     = "ru-central1-a"
}

variable "test_folder_name" {
  description = "Dedicated BIRZHA Forecast TEST folder."
  type        = string
  default     = "birzha-mcp-forecast-test"
}

variable "mcp_image_url" {
  description = "Immutable BIRZHA MCP image URL. Leave null for foundation-only bootstrap; apply with a container requires a pushed image pinned to source commit/digest."
  type        = string
  default     = null
  nullable    = true
}

variable "mcp_allowed_hosts" {
  description = "Comma-separated exact Host values accepted by MCP transport security. Initial remote deployment uses a fail-closed placeholder; the next revision must use the real API Gateway domain."
  type        = string
  default     = "__remote_host_not_configured__.invalid"
}

variable "mcp_allowed_origins" {
  description = "Comma-separated Origin values accepted by MCP transport security when Origin is present. Empty means no Origin header is accepted."
  type        = string
  default     = ""
}

variable "source_commit_sha" {
  description = "Exact birzha-mcp-forecast source commit represented by the container image."
  type        = string
  default     = "0000000000000000000000000000000000000000"

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.source_commit_sha))
    error_message = "source_commit_sha must be a full 40-character Git commit SHA."
  }
}
