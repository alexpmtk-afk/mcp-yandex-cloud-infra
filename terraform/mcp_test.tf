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

# Terraform owns the stable container identity/foundation. Runtime revisions are
# deliberately deployed by the CI workflow because they also carry VPC,
# Redis/rate-limit environment and Lockbox secret bindings. Ignoring revision
# fields prevents a routine Terraform apply from stripping that runtime config.
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

  lifecycle {
    ignore_changes = [image, connectivity]
  }
}

resource "yandex_serverless_container_iam_member" "gateway_invoker" {
  count        = var.mcp_image_url == null ? 0 : 1
  container_id = yandex_serverless_container.mcp[0].id
  role         = "serverless-containers.containerInvoker"
  member       = "serviceAccount:${yandex_iam_service_account.gateway.id}"
}

# The TEST gateway predates the persistent Terraform state and the provider
# does not implement import for yandex_api_gateway. Keep it read-only here:
# its integration targets the stable container ID, not a mutable revision ID.
data "yandex_api_gateway" "mcp_existing" {
  api_gateway_id = var.mcp_api_gateway_id
}
