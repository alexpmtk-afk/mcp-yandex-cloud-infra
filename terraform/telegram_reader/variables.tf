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
