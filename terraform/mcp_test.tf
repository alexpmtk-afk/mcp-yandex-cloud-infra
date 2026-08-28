# TEST-only foundation and MCP service. No credential values are stored here.
locals {
  labels = {
    project     = "marketplaces-mcp"
    environment = "test"
    managed_by  = "terraform"
  }
}

resource "yandex_resourcemanager_folder" "mcp_test" {
  cloud_id    = var.yc_cloud_id
  name        = var.test_folder_name
  description = "Isolated TEST environment for marketplaces MCP"
  labels      = local.labels
}

resource "yandex_container_registry" "mcp" {
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  name      = "marketplaces-mcp"
  labels    = local.labels
}

resource "yandex_iam_service_account" "runtime" {
  folder_id   = yandex_resourcemanager_folder.mcp_test.id
  name        = "marketplaces-mcp-runtime"
  description = "Runtime identity for the TEST MCP container"
}

resource "yandex_iam_service_account" "gateway" {
  folder_id   = yandex_resourcemanager_folder.mcp_test.id
  name        = "marketplaces-mcp-gateway"
  description = "Identity used by API Gateway to invoke the private MCP container"
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_registry_pull" {
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  role      = "container-registry.images.puller"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_lockbox_viewer" {
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

resource "yandex_lockbox_secret" "marketplace_credentials" {
  folder_id           = yandex_resourcemanager_folder.mcp_test.id
  name                = "marketplaces-mcp-api-credentials"
  description         = "TEST MCP marketplace credentials. Values are added out of band, never in Terraform."
  deletion_protection = true
  labels              = local.labels
}

resource "yandex_serverless_container" "mcp" {
  count              = var.mcp_image_url == null ? 0 : 1
  folder_id          = yandex_resourcemanager_folder.mcp_test.id
  name               = "marketplaces-mcp-test"
  description        = "Private Streamable HTTP MCP service"
  memory             = 512
  cores              = 1
  execution_timeout  = "60s"
  service_account_id = yandex_iam_service_account.runtime.id
  image {
    url = var.mcp_image_url
  }
  labels = local.labels
}

resource "yandex_serverless_container_iam_member" "gateway_invoker" {
  count        = var.mcp_image_url == null ? 0 : 1
  container_id = yandex_serverless_container.mcp[0].id
  role         = "serverless-containers.containerInvoker"
  member       = "serviceAccount:${yandex_iam_service_account.gateway.id}"
}

resource "yandex_api_gateway" "mcp" {
  count             = var.mcp_image_url == null ? 0 : 1
  folder_id         = yandex_resourcemanager_folder.mcp_test.id
  name              = "marketplaces-mcp-test"
  description       = "TEST gateway for the private MCP container"
  execution_timeout = "60"
  labels            = local.labels
  spec = templatefile("${path.module}/mcp_gateway.yaml.tftpl", {
    container_id       = yandex_serverless_container.mcp[0].id
    service_account_id = yandex_iam_service_account.gateway.id
  })
}
