provider "yandex" {
  cloud_id                 = var.yc_cloud_id
  folder_id                = var.yc_folder_id
  zone                     = var.yc_zone
  service_account_key_file = var.yc_service_account_key_file
}
