variable "yc_cloud_id" {
  description = "Yandex Cloud cloud ID."
  type        = string
  default     = "b1gi4pr9msenirafh2c7"
}

variable "yc_folder_id" {
  description = "Optional provider folder ID. The canonical Marketplace runtime creates and owns its folder."
  type        = string
  default     = null
  nullable    = true
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

variable "environment" {
  description = "Deployment environment name for the single canonical Marketplace runtime."
  type        = string
  default     = "production"

  validation {
    condition     = var.environment == "production"
    error_message = "Marketplaces uses one canonical production runtime."
  }
}

variable "marketplaces_folder_name" {
  description = "Canonical Yandex Cloud folder name for Marketplace MCP."
  type        = string
  default     = "marketplaces-mcp"
}

variable "mcp_image_url" {
  description = "Immutable container image URL. Omit to apply only the Marketplace foundation."
  type        = string
  default     = null
  nullable    = true
}

variable "mcp_api_gateway_id" {
  description = "Existing canonical Marketplace API Gateway ID; read-only because the provider cannot import it."
  type        = string
  default     = "d5deoa6cl4irtmkp5ad6"
}
