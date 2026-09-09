terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    endpoints = {
      s3 = "https://storage.yandexcloud.net"
    }
    bucket = "marketplaces-mcp-tfstate-b1gnd0dqoq3ljod88i8t"
    key    = "telegram-news-reader/prod/terraform.tfstate"
    region = "ru-central1"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_lockfile                = true
  }

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "= 0.224.0"
    }
  }
}
