output "test_folder_id" {
  value = yandex_resourcemanager_folder.mcp_test.id
}

output "container_registry_id" {
  value = yandex_container_registry.mcp.id
}

output "lockbox_secret_id" {
  value     = yandex_lockbox_secret.marketplace_credentials.id
  sensitive = true
}

output "mcp_gateway_url" {
  value = var.mcp_image_url == null ? null : "https://${data.yandex_api_gateway.mcp_existing.domain}"
}

output "wb_orders_ydb_endpoint" {
  description = "Connection string for the selective canonical WB ORDERS Historical Store."
  value       = yandex_ydb_database_serverless.marketplace_history.ydb_full_endpoint
}

output "wb_orders_ydb_database_id" {
  description = "YDB database ID for the selective canonical WB ORDERS Historical Store."
  value       = yandex_ydb_database_serverless.marketplace_history.id
}
