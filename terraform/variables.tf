variable "yc_cloud_id" {
  description = "Yandex Cloud cloud ID. Supplied only when cloud-connected plan/apply is enabled."
  type        = string
  default     = null
  nullable    = true
}

variable "yc_folder_id" {
  description = "Yandex Cloud folder ID for the target environment."
  type        = string
  default     = null
  nullable    = true
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
    condition     = contains(["test", "final"], var.environment)
    error_message = "environment must be either test or final."
  }
}
