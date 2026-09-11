# Selective durable history for canonical Wildberries ORDERS.
#
# This is intentionally not a general marketplace warehouse. The application
# stores only canonical supplier/orders rows needed to preserve business metric
# continuity beyond the provider retention window.
resource "yandex_ydb_database_serverless" "marketplace_history" {
  folder_id           = yandex_resourcemanager_folder.mcp_test.id
  name                = "marketplaces-mcp-history"
  description         = "Durable canonical WB ORDERS history for Marketplaces MCP TEST"
  deletion_protection = true
  labels              = local.labels
}

resource "yandex_ydb_database_iam_binding" "runtime_history_editor" {
  database_id = yandex_ydb_database_serverless.marketplace_history.id
  role        = "ydb.editor"
  members     = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}
