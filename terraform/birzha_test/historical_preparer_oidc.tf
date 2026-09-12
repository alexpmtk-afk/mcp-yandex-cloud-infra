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

resource "yandex_iam_workload_identity_federated_credential" "github_historical_preparer" {
  service_account_id  = yandex_iam_service_account.historical_preparer.id
  federation_id       = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
  external_subject_id = "repo:alexpmtk-afk@309119594/birzha-mcp-forecast@1350648480:ref:refs/heads/main"
}

output "historical_preparer_service_account_id" {
  description = "Temporary OIDC service account used only for governed historical YDB preparation."
  value       = yandex_iam_service_account.historical_preparer.id
}
