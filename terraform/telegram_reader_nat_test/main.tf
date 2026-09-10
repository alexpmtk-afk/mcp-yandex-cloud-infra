terraform {
  required_version = ">= 1.9.0"
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "0.224.0"
    }
  }
}

variable "yc_service_account_key_file" {
  type      = string
  sensitive = true
}

provider "yandex" {
  cloud_id                 = "b1gi4pr9msenirafh2c7"
  folder_id                = "b1gk4p83brasi8g811jv"
  zone                     = "ru-central1-a"
  service_account_key_file = var.yc_service_account_key_file
}

data "yandex_compute_image" "ubuntu" {
  family    = "ubuntu-2404-lts-oslogin"
  folder_id = "standard-images"
}

resource "yandex_vpc_gateway" "nat" {
  folder_id   = "b1gk4p83brasi8g811jv"
  name        = "telegram-nat-egress-probe"
  description = "Temporary NAT gateway for Telegram connectivity probe"
  shared_egress_gateway {}
}

resource "yandex_vpc_route_table" "nat" {
  folder_id  = "b1gk4p83brasi8g811jv"
  name       = "telegram-nat-egress-probe"
  network_id = "enp3vuoau0hkv7hcb6mh"

  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = yandex_vpc_gateway.nat.id
  }
}

resource "yandex_vpc_subnet" "probe" {
  folder_id      = "b1gk4p83brasi8g811jv"
  name           = "telegram-nat-egress-probe"
  zone           = "ru-central1-a"
  network_id     = "enp3vuoau0hkv7hcb6mh"
  v4_cidr_blocks = ["10.77.2.0/28"]
  route_table_id = yandex_vpc_route_table.nat.id
}

resource "yandex_vpc_security_group" "probe" {
  folder_id  = "b1gk4p83brasi8g811jv"
  name       = "telegram-nat-egress-probe"
  network_id = "enp3vuoau0hkv7hcb6mh"

  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "yandex_compute_instance" "probe" {
  folder_id   = "b1gk4p83brasi8g811jv"
  name        = "telegram-nat-egress-probe"
  hostname    = "telegram-nat-egress-probe"
  zone        = "ru-central1-a"
  platform_id = "standard-v3"

  resources {
    cores         = 2
    memory        = 1
    core_fraction = 20
  }

  scheduling_policy {
    preemptible = true
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = 10
      type     = "network-hdd"
    }
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.probe.id
    nat                = false
    security_group_ids = [yandex_vpc_security_group.probe.id]
  }

  metadata = {
    serial-port-enable = "1"
    user-data          = file("${path.module}/probe-cloud-init.yaml")
  }
}

output "probe_id" {
  value = yandex_compute_instance.probe.id
}
