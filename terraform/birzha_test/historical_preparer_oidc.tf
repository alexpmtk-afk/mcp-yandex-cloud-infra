variable "historical_preparer_bootstrap_enabled" {
  description = "Temporary switch granting the infra deployer only the permissions required to create the historical preparer federated credential. Must be false after bootstrap."
  type        = bool
  default     = false
}

resource "yandex_iam_service_account" "historical_preparer" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-historical-preparer"
  description = "Temporary CI identity for governed BIRZHA historical YDB preparation"
}

resource "yandex_resourcemanager_folder_iam_member" "historical_preparer_ydb_editor" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  role      = "ydb.editor"
  member    = "serviceAccount:${yandex_iam_service_account.historical_preparer.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "historical_preparer_wif_user_bootstrap" {
  count      = var.historical_preparer_bootstrap_enabled ? 1 : 0
  folder_id  = yandex_resourcemanager_folder.birzha_test.id
  role       = "iam.workloadIdentityFederations.user"
  member     = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 5
}

resource "yandex_iam_service_account_iam_member" "historical_preparer_credential_editor_bootstrap" {
  count              = var.historical_preparer_bootstrap_enabled ? 1 : 0
  service_account_id = yandex_iam_service_account.historical_preparer.id
  role               = "iam.serviceAccounts.federatedCredentialEditor"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after        = 5
}

resource "yandex_iam_workload_identity_federated_credential" "github_historical_preparer" {
  service_account_id  = yandex_iam_service_account.historical_preparer.id
  federation_id       = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
  external_subject_id = "repo:alexpmtk-afk@309119594/birzha-mcp-forecast@1350648480:ref:refs/heads/main"
  depends_on = [
    yandex_resourcemanager_folder_iam_member.historical_preparer_wif_user_bootstrap,
    yandex_iam_service_account_iam_member.historical_preparer_credential_editor_bootstrap,
  ]
}

output "historical_preparer_service_account_id" {
  description = "Temporary OIDC service account used only for governed historical YDB preparation."
  value       = yandex_iam_service_account.historical_preparer.id
}
