resource "yandex_iam_service_account_iam_member" "terraform_runtime_user" {
  service_account_id = yandex_iam_service_account.runtime.id
  role               = "iam.serviceAccounts.user"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after        = 10
}

resource "yandex_resourcemanager_folder_iam_member" "terraform_secret_revision_editor" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  role        = "functions.editor"
  member      = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 30
}
