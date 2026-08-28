provider "yandex" {
  cloud_id  = var.yc_cloud_id
  folder_id = var.yc_folder_id
  zone      = var.yc_zone
}

# Bootstrap intentionally defines no Yandex Cloud resources.
# Resource creation will be introduced only after GitHub ↔ Yandex Cloud
# Workload Identity Federation is configured and verified.
