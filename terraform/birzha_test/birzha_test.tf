resource "yandex_resourcemanager_folder" "birzha_test" {
  cloud_id    = var.yc_cloud_id
  name        = var.test_folder_name
  description = "Isolated TEST environment for BIRZHA MCP Forecast"
  labels      = local.labels
}

resource "yandex_container_registry" "birzha" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  name      = "birzha-mcp-forecast"
  labels    = local.labels
}

resource "yandex_iam_service_account" "runtime" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-runtime"
  description = "Runtime identity for the BIRZHA MCP Forecast TEST container"
}

resource "yandex_iam_service_account" "gateway" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-gateway"
  description = "Identity used by API Gateway to invoke the private BIRZHA MCP container"
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_registry_pull" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  role      = "container-registry.images.puller"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

resource "yandex_serverless_container" "mcp" {
  count              = var.mcp_image_url == null ? 0 : 1
  folder_id          = yandex_resourcemanager_folder.birzha_test.id
  name               = "birzha-mcp-forecast-test"
  description        = "Private Streamable HTTP BIRZHA MCP Forecast TEST service"
  memory             = 512
  cores              = 1
  execution_timeout  = "60s"
  service_account_id = yandex_iam_service_account.runtime.id

  runtime {
    type = "http"
  }

  image {
    url = var.mcp_image_url
    environment = {
      MCP_ALLOWED_HOSTS   = var.mcp_allowed_hosts
      MCP_ALLOWED_ORIGINS = var.mcp_allowed_origins
      BIRZHA_SOURCE_COMMIT = var.source_commit_sha
    }
  }

  labels = merge(local.labels, {
    source_sha = substr(var.source_commit_sha, 0, 16)
  })
}

resource "yandex_serverless_container_iam_member" "gateway_invoker" {
  count        = var.mcp_image_url == null ? 0 : 1
  container_id = yandex_serverless_container.mcp[0].id
  role         = "serverless-containers.containerInvoker"
  member       = "serviceAccount:${yandex_iam_service_account.gateway.id}"
}

resource "yandex_api_gateway" "mcp" {
  count             = var.mcp_image_url == null ? 0 : 1
  folder_id         = yandex_resourcemanager_folder.birzha_test.id
  name              = "birzha-mcp-forecast-test-gateway"
  description       = "Public TEST gateway to the private BIRZHA MCP Forecast container"
  execution_timeout = "60s"
  labels            = local.labels

  spec = templatefile("${path.module}/gateway.yaml.tftpl", {
    container_id       = yandex_serverless_container.mcp[0].id
    service_account_id = yandex_iam_service_account.gateway.id
  })

  depends_on = [yandex_serverless_container_iam_member.gateway_invoker]
}
