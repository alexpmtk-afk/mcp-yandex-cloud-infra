variable "yc_cloud_id" {
  type    = string
  default = "b1gi4pr9msenirafh2c7"
}

variable "yc_zone" {
  type    = string
  default = "ru-central1-a"
}

variable "yc_service_account_key_file" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "yc_token" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "ci_service_account_id" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "shared_network_id" {
  description = "Existing cloud VPC network reused through Yandex multi-folder VPC"
  type        = string
  default     = "enp3vuoau0hkv7hcb6mh"
}

variable "folder_name" {
  type    = string
  default = "telegram-news-reader"
}

variable "runtime_enabled" {
  type    = bool
  default = false
}

variable "image_url" {
  type     = string
  default  = null
  nullable = true
}

variable "setup_token_sha256" {
  description = "SHA-256 of the temporary one-time setup token; plaintext token is never stored in Git"
  type        = string
  default     = "b33311a41482a4a1ccd84a293fdfc1c3097306249147e84f409920b915f07c2f"
}

variable "vm_cores" {
  type    = number
  default = 2
}

variable "vm_memory_gb" {
  type    = number
  default = 2
}

variable "state_disk_size_gb" {
  type    = number
  default = 10
}

variable "ssh_ingress_cidrs" {
  type    = list(string)
  default = []
}
