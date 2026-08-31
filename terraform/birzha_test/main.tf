provider "yandex" {
  cloud_id                 = var.yc_cloud_id
  zone                     = var.yc_zone
  token                    = var.yc_token
  service_account_key_file = var.yc_token == null ? var.yc_service_account_key_file : null
}

locals {
  labels = {
    project     = "birzha-mcp-forecast"
    environment = "test"
    managed_by  = "terraform"
  }
}
