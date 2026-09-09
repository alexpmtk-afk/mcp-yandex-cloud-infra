provider "yandex" {
  cloud_id                 = var.yc_cloud_id
  zone                     = var.yc_zone
  token                    = var.yc_token
  service_account_key_file = var.yc_token == null ? var.yc_service_account_key_file : null
}

locals {
  labels         = { project = "telegram-news-reader", managed_by = "terraform" }
  create_runtime = var.runtime_enabled && var.image_url != null
}

resource "yandex_resourcemanager_folder" "this" {
  cloud_id    = var.yc_cloud_id
  name        = var.folder_name
  description = "Central multi-device Telegram News Reader"
  labels      = local.labels
}

resource "yandex_resourcemanager_folder_iam_member" "ci_vpc_admin" {
  count       = var.ci_service_account_id == null ? 0 : 1
  folder_id   = yandex_resourcemanager_folder.this.id
  role        = "vpc.admin"
  member      = "serviceAccount:${var.ci_service_account_id}"
  sleep_after = 5
}

resource "yandex_vpc_network" "this" {
  folder_id = yandex_resourcemanager_folder.this.id
  name      = "telegram-reader-network"
  labels    = local.labels

  depends_on = [yandex_resourcemanager_folder_iam_member.ci_vpc_admin]
}

resource "yandex_vpc_subnet" "this" {
  folder_id      = yandex_resourcemanager_folder.this.id
  name           = "telegram-reader-subnet"
  zone           = var.yc_zone
  network_id     = yandex_vpc_network.this.id
  v4_cidr_blocks = ["10.77.0.0/24"]
}

resource "yandex_container_registry" "this" {
  folder_id = yandex_resourcemanager_folder.this.id
  name      = "telegram-news-reader"
  labels    = local.labels
}

resource "yandex_iam_service_account" "runtime" {
  folder_id   = yandex_resourcemanager_folder.this.id
  name        = "telegram-reader-runtime"
  description = "Runtime identity for Telegram News Reader VM"
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_registry_pull" {
  folder_id = yandex_resourcemanager_folder.this.id
  role      = "container-registry.images.puller"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

resource "yandex_lockbox_secret" "telegram_credentials" {
  folder_id           = yandex_resourcemanager_folder.this.id
  name                = "telegram-reader-credentials"
  description         = "Populate manually with api_id, api_hash and phone; values are never stored in Git"
  deletion_protection = true
  labels              = local.labels
}

resource "yandex_lockbox_secret" "reader_auth" {
  folder_id           = yandex_resourcemanager_folder.this.id
  name                = "telegram-reader-auth"
  description         = "Generated bearer token protecting API and MCP"
  deletion_protection = true
  labels              = local.labels

  password_payload_specification {
    password_key        = "bearer_token"
    length              = 64
    include_uppercase   = true
    include_lowercase   = true
    include_digits      = true
    include_punctuation = false
  }
}

resource "yandex_lockbox_secret_version" "reader_auth" {
  secret_id = yandex_lockbox_secret.reader_auth.id
}

resource "yandex_lockbox_secret_iam_member" "runtime_credentials" {
  secret_id   = yandex_lockbox_secret.telegram_credentials.id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${yandex_iam_service_account.runtime.id}"
  sleep_after = 5
}

resource "yandex_lockbox_secret_iam_member" "runtime_auth" {
  secret_id   = yandex_lockbox_secret.reader_auth.id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${yandex_iam_service_account.runtime.id}"
  sleep_after = 5
}
