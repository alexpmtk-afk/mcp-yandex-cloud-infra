terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    endpoints = {
      s3 = "https://storage.yandexcloud.net"
    }

    # Reuse the already-proven central remote-state bucket, but isolate BIRZHA
    # with its own state key. No new bucket is created by this configuration.
    bucket = "marketplaces-mcp-tfstate-b1gnd0dqoq3ljod88i8t"
    key    = "birzha-mcp-forecast/test/terraform.tfstate"
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
