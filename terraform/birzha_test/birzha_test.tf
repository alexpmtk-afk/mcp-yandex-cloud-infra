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

resource "yandex_iam_service_account" "publisher" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-publisher"
  description = "Dedicated CI identity allowed only to publish BIRZHA MCP Forecast images"
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_registry_pull" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  role      = "container-registry.images.puller"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

resource "yandex_container_registry_iam_binding" "publisher_push" {
  registry_id = yandex_container_registry.birzha.id
  role        = "container-registry.images.pusher"
  members     = ["serviceAccount:${yandex_iam_service_account.publisher.id}"]
}

resource "yandex_resourcemanager_folder_iam_member" "terraform_wif_viewer" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  role      = "iam.workloadIdentityFederations.viewer"
  member    = "serviceAccount:${var.terraform_deployer_service_account_id}"
}

resource "yandex_resourcemanager_folder_iam_member" "terraform_ydb_viewer" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  role      = "ydb.viewer"
  member    = "serviceAccount:${var.terraform_deployer_service_account_id}"
}

resource "yandex_resourcemanager_folder_iam_member" "ydb_bootstrap_admin" {
  count       = var.ydb_bootstrap_enabled ? 1 : 0
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  role        = "ydb.admin"
  member      = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 60
}

resource "yandex_iam_service_account_iam_member" "terraform_federated_credential_viewer" {
  service_account_id = yandex_iam_service_account.publisher.id
  role               = "iam.serviceAccounts.federatedCredentialViewer"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
}

resource "yandex_resourcemanager_folder_iam_member" "wif_bootstrap_editor" {
  count       = var.wif_bootstrap_deployer_service_account_id == null ? 0 : 1
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  role        = "iam.workloadIdentityFederations.editor"
  member      = "serviceAccount:${var.wif_bootstrap_deployer_service_account_id}"
  sleep_after = 5
}

resource "yandex_resourcemanager_folder_iam_member" "wif_bootstrap_user" {
  count       = var.wif_bootstrap_deployer_service_account_id == null ? 0 : 1
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  role        = "iam.workloadIdentityFederations.user"
  member      = "serviceAccount:${var.wif_bootstrap_deployer_service_account_id}"
  sleep_after = 5
}

resource "yandex_iam_service_account_iam_member" "wif_bootstrap_federated_credential_editor" {
  count              = var.wif_bootstrap_deployer_service_account_id == null ? 0 : 1
  service_account_id = yandex_iam_service_account.publisher.id
  role               = "iam.serviceAccounts.federatedCredentialEditor"
  member             = "serviceAccount:${var.wif_bootstrap_deployer_service_account_id}"
  sleep_after        = 5
}

resource "yandex_resourcemanager_folder_iam_member" "federated_credential_update_user" {
  count       = var.federated_credential_update_deployer_service_account_id == null ? 0 : 1
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  role        = "iam.workloadIdentityFederations.user"
  member      = "serviceAccount:${var.federated_credential_update_deployer_service_account_id}"
  sleep_after = 5
}

resource "yandex_iam_service_account_iam_member" "federated_credential_update_editor" {
  count              = var.federated_credential_update_deployer_service_account_id == null ? 0 : 1
  service_account_id = yandex_iam_service_account.publisher.id
  role               = "iam.serviceAccounts.federatedCredentialEditor"
  member             = "serviceAccount:${var.federated_credential_update_deployer_service_account_id}"
  sleep_after        = 5
}

resource "yandex_iam_workload_identity_oidc_federation" "github_image_publisher" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-github-publisher"
  description = "GitHub Actions OIDC federation for BIRZHA TEST image publishing"
  disabled    = false
  audiences   = ["https://github.com/alexpmtk-afk"]
  issuer      = "https://token.actions.githubusercontent.com"
  jwks_url    = "https://token.actions.githubusercontent.com/.well-known/jwks"
  labels      = local.labels
  depends_on  = [yandex_resourcemanager_folder_iam_member.wif_bootstrap_editor]
}

resource "yandex_iam_workload_identity_federated_credential" "github_image_publisher" {
  service_account_id  = yandex_iam_service_account.publisher.id
  federation_id       = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
  external_subject_id = "repo:alexpmtk-afk@309119594/birzha-mcp-forecast@1350648480:ref:refs/heads/main"
  depends_on = [
    yandex_resourcemanager_folder_iam_member.wif_bootstrap_user,
    yandex_iam_service_account_iam_member.wif_bootstrap_federated_credential_editor,
    yandex_resourcemanager_folder_iam_member.federated_credential_update_user,
    yandex_iam_service_account_iam_member.federated_credential_update_editor,
  ]
}

resource "yandex_ydb_database_serverless" "state" {
  folder_id           = yandex_resourcemanager_folder.birzha_test.id
  name                = "birzha-mcp-forecast-state"
  description         = "Durable immutable Forecast Journal and append-only Outcome state"
  deletion_protection = true
  labels              = local.labels
  depends_on          = [yandex_resourcemanager_folder_iam_member.ydb_bootstrap_admin]
}

resource "yandex_ydb_database_iam_binding" "runtime_editor" {
  database_id = yandex_ydb_database_serverless.state.id
  role        = "ydb.editor"
  members     = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}

resource "yandex_lockbox_secret" "mcp_auth" {
  folder_id           = yandex_resourcemanager_folder.birzha_test.id
  name                = "birzha-mcp-forecast-test-auth"
  description         = "Generated bearer token protecting the BIRZHA MCP TEST endpoint"
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

resource "yandex_lockbox_secret_version" "mcp_auth" {
  secret_id = yandex_lockbox_secret.mcp_auth.id
}

resource "yandex_lockbox_secret_iam_member" "runtime_mcp_auth" {
  secret_id   = yandex_lockbox_secret.mcp_auth.id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${yandex_iam_service_account.runtime.id}"
  sleep_after = 10
}

resource "yandex_lockbox_secret_iam_member" "deployer_mcp_auth" {
  secret_id   = yandex_lockbox_secret.mcp_auth.id
  role        = "lockbox.payloadViewer"
  member      = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 10
}

resource "yandex_serverless_container" "mcp" {
  count              = var.mcp_image_url == null ? 0 : 1
  folder_id          = yandex_resourcemanager_folder.birzha_test.id
  name               = "birzha-mcp-forecast-test"
  description        = "Private Streamable HTTP BIRZHA MCP Forecast TEST service"
  memory             = 512
  cores              = 1
  concurrency        = 1
  execution_timeout  = "120s"
  service_account_id = yandex_iam_service_account.runtime.id

  runtime {
    type = "http"
  }

  secrets {
    id                   = yandex_lockbox_secret.mcp_auth.id
    version_id           = yandex_lockbox_secret_version.mcp_auth.id
    key                  = "bearer_token"
    environment_variable = "BIRZHA_MCP_BEARER_TOKEN"
  }

  image {
    url = var.mcp_image_url
    environment = {
      MCP_ALLOWED_HOSTS       = var.mcp_allowed_hosts
      MCP_ALLOWED_ORIGINS     = var.mcp_allowed_origins
      BIRZHA_SOURCE_COMMIT    = var.source_commit_sha
      BIRZHA_STATE_BACKEND    = "ydb"
      BIRZHA_REQUIRE_MCP_AUTH = "true"
      YDB_CONNECTION_STRING   = yandex_ydb_database_serverless.state.ydb_full_endpoint
    }
  }

  labels = merge(local.labels, {
    source_sha = substr(var.source_commit_sha, 0, 16)
  })
  depends_on = [
    yandex_ydb_database_iam_binding.runtime_editor,
    yandex_lockbox_secret_iam_member.runtime_mcp_auth,
  ]
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
  execution_timeout = "120"
  labels            = local.labels

  spec = templatefile("${path.module}/gateway.yaml.tftpl", {
    container_id       = yandex_serverless_container.mcp[0].id
    service_account_id = yandex_iam_service_account.gateway.id
  })

  depends_on = [yandex_serverless_container_iam_member.gateway_invoker]
}
