# TEST-only foundation and MCP service. No credential values are stored here.
locals {
  labels = {
    project     = "marketplaces-mcp"
    environment = "test"
    managed_by  = "terraform"
  }

  # The CI key file is ephemeral and already supplied to the provider. Resolve
  # only its non-secret service-account ID so Terraform can manage the minimum
  # service-specific roles required by TEST deployment.
  terraform_deployer_service_account_id = var.yc_service_account_key_file == null ? null : try(
    jsondecode(file(var.yc_service_account_key_file)).service_account_id,
    jsondecode(file(var.yc_service_account_key_file)).serviceAccountId,
    null,
  )
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

resource "yandex_resourcemanager_folder_iam_member" "runtime_archive_storage_editor" {
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  role      = "storage.editor"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

# Terraform itself also needs Object Storage lifecycle access. Keep this as a
# narrow service-specific role instead of storage.admin/editor at cloud scope.
resource "yandex_resourcemanager_folder_iam_member" "deployer_archive_storage_editor" {
  count     = local.terraform_deployer_service_account_id == null ? 0 : 1
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  role      = "storage.editor"
  member    = "serviceAccount:${local.terraform_deployer_service_account_id}"
}

# The GitHub Actions deployer builds the TEST image and pushes it to the TEST
# Container Registry. Grant only the dedicated image-pusher role required for
# that operation; runtime keeps the separate pull-only role above.
resource "yandex_resourcemanager_folder_iam_member" "deployer_registry_image_pusher" {
  count     = local.terraform_deployer_service_account_id == null ? 0 : 1
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  role      = "container-registry.images.pusher"
  member    = "serviceAccount:${local.terraform_deployer_service_account_id}"
}

resource "yandex_lockbox_secret" "marketplace_credentials" {
  folder_id           = yandex_resourcemanager_folder.mcp_test.id
  name                = "marketplaces-mcp-api-credentials"
  description         = "TEST MCP marketplace credentials. Values are added out of band, never in Terraform."
  deletion_protection = true
  labels              = local.labels
}

# Dedicated Shared Google Drive Bridge Protocol v1 credential container.
# The secret value is bootstrapped out of band only after the isolated
# Marketplaces Apps Script deployment passes identity/root checks. Never reuse
# the legacy marketplace credential bundle for this bridge.
resource "yandex_lockbox_secret" "marketplaces_google_drive_bridge_v1" {
  folder_id           = yandex_resourcemanager_folder.mcp_test.id
  name                = "marketplaces-google-drive-bridge-v1"
  description         = "Dedicated TEST credential for Marketplaces Google Drive Bridge Protocol v1. Value is added out of band after live bridge validation."
  deletion_protection = true
  labels              = local.labels
}

# Authoritative shared file archive. The bucket is private. Runtime and
# Terraform use IAM tokens only and this stack creates no Object Storage static
# access key. Versioning is enabled immediately after Terraform apply via the
# native Yandex CLI/API path because the Terraform resource's S3 versioning
# argument requires storage.admin while Yandex's native Bucket.Update supports
# versioning with the narrower storage.editor role.
resource "yandex_storage_bucket" "marketplace_archive" {
  folder_id     = yandex_resourcemanager_folder.mcp_test.id
  bucket        = "marketplaces-mcp-archive-${yandex_resourcemanager_folder.mcp_test.id}"
  force_destroy = false

  depends_on = [
    yandex_resourcemanager_folder_iam_member.deployer_archive_storage_editor,
    yandex_resourcemanager_folder_iam_member.deployer_registry_image_pusher,
  ]
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
  memory             = 2048
  cores              = 1
  execution_timeout  = "600s"
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
