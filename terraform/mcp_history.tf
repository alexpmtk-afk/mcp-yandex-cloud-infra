# Durable canonical WB ORDERS history for the TEST marketplaces MCP.
# The database stores only server-owned historical data; marketplace credentials
# remain in Lockbox and are never written here.
resource "yandex_ydb_database_serverless" "orders_history" {
  folder_id           = yandex_resourcemanager_folder.mcp_test.id
  name                = "marketplaces-orders-history"
  description         = "Canonical WB ORDERS historical store for marketplaces MCP TEST"
  deletion_protection = true
  labels              = local.labels
}

# The runtime creates/updates its own two schema tables and therefore needs
# read/write/schema permissions. Scope the service role to this TEST folder;
# no primitive editor role is granted.
resource "yandex_resourcemanager_folder_iam_member" "runtime_ydb_editor" {
  folder_id = yandex_resourcemanager_folder.mcp_test.id
  role      = "ydb.editor"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

output "marketplace_orders_ydb_endpoint" {
  description = "Full TLS YDB SDK endpoint for the canonical WB ORDERS history store"
  value       = yandex_ydb_database_serverless.orders_history.ydb_full_endpoint
}
