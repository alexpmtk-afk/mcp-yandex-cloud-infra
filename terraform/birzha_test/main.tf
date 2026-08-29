provider "yandex" {
  cloud_id                 = var.yc_cloud_id
  zone                     = var.yc_zone
  service_account_key_file = var.yc_service_account_key_file
}

locals {
  labels = {
    project     = "birzha-mcp-forecast"
    environment = "test"
    managed_by  = "terraform"
  }
}
