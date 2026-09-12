resource "yandex_resourcemanager_folder_iam_member" "publisher_ydb_viewer" {
  folder_id = yandex_resourcemanager_folder.birzha_test.id
  role      = "ydb.viewer"
  member    = "serviceAccount:${yandex_iam_service_account.publisher.id}"
}
