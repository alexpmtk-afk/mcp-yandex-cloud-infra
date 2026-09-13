variable "m24_infra_oidc_bootstrap_enabled" {
  description = "Temporary switch granting the central infra deployer only the permissions needed to create its GitHub OIDC federated credential. Must return to false after bootstrap."
  type        = bool
  default     = false
}

resource "yandex_resourcemanager_folder_iam_member" "m24_infra_oidc_federation_user_bootstrap" {
  count       = var.m24_infra_oidc_bootstrap_enabled ? 1 : 0
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  role        = "iam.workloadIdentityFederations.user"
  member      = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 5
}

resource "yandex_iam_service_account_iam_member" "m24_infra_oidc_credential_editor_bootstrap" {
  count              = var.m24_infra_oidc_bootstrap_enabled ? 1 : 0
  service_account_id = var.terraform_deployer_service_account_id
  role               = "iam.serviceAccounts.federatedCredentialEditor"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after        = 5
}

resource "yandex_iam_service_account_iam_member" "terraform_infra_deployer_federated_credential_viewer" {
  service_account_id = var.terraform_deployer_service_account_id
  role               = "iam.serviceAccounts.federatedCredentialViewer"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after        = 5
}

resource "yandex_iam_workload_identity_federated_credential" "github_infra_deployer" {
  service_account_id  = var.terraform_deployer_service_account_id
  federation_id       = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
  external_subject_id = "repo:alexpmtk-afk@309119594/mcp-yandex-cloud-infra@1349853397:ref:refs/heads/main"

  depends_on = [
    yandex_resourcemanager_folder_iam_member.m24_infra_oidc_federation_user_bootstrap,
    yandex_iam_service_account_iam_member.m24_infra_oidc_credential_editor_bootstrap,
    yandex_iam_service_account_iam_member.terraform_infra_deployer_federated_credential_viewer,
  ]
}

output "m24_infra_deployer_oidc_credential_id" {
  description = "GitHub OIDC federated credential for the BIRZHA Terraform deployer."
  value       = yandex_iam_workload_identity_federated_credential.github_infra_deployer.id
}
