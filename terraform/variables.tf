variable "yc_cloud_id" {
  description = "Yandex Cloud cloud ID."
  type        = string
  default     = "b1gi4pr9msenirafh2c7"
}

variable "yc_folder_id" {
  description = "Optional provider folder ID. TEST resources create their own folder."
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
  description = "Deployment environment name."
  type        = string
  default     = "test"

  validation {
    condition     = var.environment == "test"
    error_message = "This configuration is TEST-only."
  }
}

variable "test_folder_name" {
  description = "Dedicated Yandex Cloud TEST folder name."
  type        = string
  default     = "marketplaces-mcp-test"
}

variable "mcp_image_url" {
  description = "Immutable container image URL. Omit to apply only the TEST foundation."
  type        = string
  default     = null
  nullable    = true
}

variable "mcp_api_gateway_id" {
  description = "Existing TEST API Gateway ID; read-only because the provider cannot import it."
  type        = string
  default     = "d5deoa6cl4irtmkp5ad6"
}
