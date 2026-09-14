terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    endpoints = {
      s3 = "https://storage.yandexcloud.net"
    }

    bucket = "marketplaces-mcp-tfstate-b1gnd0dqoq3ljod88i8t"
    key    = "marketplaces-mcp/test/image-publisher.tfstate"
    region = "ru-central1"

    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_lockfile                = true
  }

  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
}

variable "yc_cloud_id" {
  type    = string
  default = "b1gi4pr9msenirafh2c7"
}

variable "folder_id" {
  type = string
}

variable "deployer_service_account_key_file" {
  type      = string
  sensitive = true
}

provider "yandex" {
  cloud_id                 = var.yc_cloud_id
  folder_id                = var.folder_id
  zone                     = "ru-central1-a"
  service_account_key_file = var.deployer_service_account_key_file
}

locals {
  labels = {
    project     = "marketplaces-mcp"
    environment = "test"
    component   = "image-publisher"
    managed_by  = "terraform"
  }
}

resource "yandex_iam_service_account" "publisher" {
  folder_id   = var.folder_id
  name        = "marketplaces-mcp-image-publisher"
  description = "Dedicated TEST identity allowed only to publish Marketplaces MCP images"
}

resource "yandex_resourcemanager_folder_iam_member" "publisher_registry_image_pusher" {
  folder_id = var.folder_id
  role      = "container-registry.images.pusher"
  member    = "serviceAccount:${yandex_iam_service_account.publisher.id}"
}

resource "yandex_iam_workload_identity_oidc_federation" "github_image_publisher" {
  folder_id   = var.folder_id
  name        = "marketplaces-mcp-github-image-publisher"
  description = "GitHub Actions OIDC federation for Marketplaces MCP TEST image publishing"
  disabled    = false
  audiences   = ["https://github.com/alexpmtk-afk"]
  issuer      = "https://token.actions.githubusercontent.com"
  jwks_url    = "https://token.actions.githubusercontent.com/.well-known/jwks"
  labels      = local.labels
}

resource "yandex_iam_workload_identity_federated_credential" "github_image_publisher" {
  service_account_id  = yandex_iam_service_account.publisher.id
  federation_id       = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
  external_subject_id = "repo:alexpmtk-afk@309119594/marketplaces-mcp-ru@1349601380:ref:refs/heads/main"
}

output "publisher_service_account_id" {
  value = yandex_iam_service_account.publisher.id
}

output "publisher_oidc_federation_id" {
  value = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
}

output "publisher_federated_credential_id" {
  value = yandex_iam_workload_identity_federated_credential.github_image_publisher.id
}
