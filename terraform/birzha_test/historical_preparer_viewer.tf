resource "yandex_iam_service_account_iam_member" "terraform_historical_preparer_federated_credential_viewer" {
  service_account_id = yandex_iam_service_account.historical_preparer.id
  role               = "iam.serviceAccounts.federatedCredentialViewer"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after        = 5
}
