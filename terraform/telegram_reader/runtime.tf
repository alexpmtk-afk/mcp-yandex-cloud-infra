data "yandex_compute_image" "ubuntu" {
  count     = local.create_runtime ? 1 : 0
  family    = "ubuntu-2404-lts-oslogin"
  folder_id = "standard-images"
}

resource "yandex_vpc_address" "public" {
  count     = local.create_runtime ? 1 : 0
  folder_id = yandex_resourcemanager_folder.this.id
  name      = "telegram-reader-public-ip"
  external_ipv4_address { zone_id = var.yc_zone }
  labels = local.labels
}

resource "yandex_vpc_security_group" "runtime" {
  count      = local.create_runtime ? 1 : 0
  folder_id  = yandex_resourcemanager_folder.this.id
  name       = "telegram-reader-runtime"
  network_id = var.shared_network_id

  ingress {
    protocol       = "TCP"
    description    = "HTTPS for API/MCP and one-time setup"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 443
  }
  ingress {
    protocol       = "TCP"
    description    = "HTTP for ACME redirect/challenge"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 80
  }
  dynamic "ingress" {
    for_each = toset(var.ssh_ingress_cidrs)
    content {
      protocol       = "TCP"
      description    = "Temporary administrative SSH"
      v4_cidr_blocks = [ingress.value]
      port           = 22
    }
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "yandex_compute_disk" "state" {
  count     = local.create_runtime ? 1 : 0
  folder_id = yandex_resourcemanager_folder.this.id
  name      = "telegram-reader-state"
  type      = "network-hdd"
  zone      = var.yc_zone
  size      = var.state_disk_size_gb
  labels    = local.labels

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [yandex_resourcemanager_folder_iam_member.ci_compute_admin]
}

resource "yandex_compute_instance" "runtime" {
  count                     = local.create_runtime ? 1 : 0
  folder_id                 = yandex_resourcemanager_folder.this.id
  name                      = "telegram-news-reader"
  hostname                  = "telegram-news-reader"
  zone                      = var.yc_zone
  platform_id               = "standard-v3"
  service_account_id        = yandex_iam_service_account.runtime.id
  allow_stopping_for_update = true

  resources {
    cores         = var.vm_cores
    memory        = var.vm_memory_gb
    core_fraction = 20
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu[0].id
      size     = 10
      type     = "network-hdd"
    }
  }

  secondary_disk {
    disk_id     = yandex_compute_disk.state[0].id
    device_name = "telegram-state"
    auto_delete = false
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.this.id
    nat                = true
    nat_ip_address     = yandex_vpc_address.public[0].external_ipv4_address[0].address
    security_group_ids = [yandex_vpc_security_group.runtime[0].id]
  }

  metadata = {
    user-data = templatefile("${path.module}/cloud-init/runtime.yaml.tftpl", {
      credentials_secret_id = yandex_lockbox_secret.telegram_credentials.id
      auth_secret_id        = yandex_lockbox_secret.reader_auth.id
      image_url             = var.image_url
      public_ip             = yandex_vpc_address.public[0].external_ipv4_address[0].address
      setup_token_sha256    = var.setup_token_sha256
    })
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    yandex_lockbox_secret_iam_member.runtime_credentials,
    yandex_lockbox_secret_iam_member.runtime_credentials_setup_editor,
    yandex_lockbox_secret_iam_member.runtime_auth,
    yandex_resourcemanager_folder_iam_member.runtime_registry_pull,
    yandex_resourcemanager_folder_iam_member.ci_compute_admin,
    yandex_resourcemanager_folder_iam_member.ci_sa_user,
  ]
}
