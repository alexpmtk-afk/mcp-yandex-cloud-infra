output "test_folder_id" {
  description = "Dedicated BIRZHA Forecast TEST folder ID."
  value       = yandex_resourcemanager_folder.birzha_test.id
}

output "container_registry_id" {
  description = "BIRZHA Forecast TEST Container Registry ID."
  value       = yandex_container_registry.birzha.id
}

output "runtime_service_account_id" {
  description = "BIRZHA Forecast runtime service account ID."
  value       = yandex_iam_service_account.runtime.id
}

output "gateway_service_account_id" {
  description = "BIRZHA Forecast gateway service account ID."
  value       = yandex_iam_service_account.gateway.id
}

output "serverless_container_id" {
  description = "BIRZHA Forecast TEST Serverless Container ID, once an image is configured."
  value       = try(yandex_serverless_container.mcp[0].id, null)
}

output "api_gateway_id" {
  description = "BIRZHA Forecast TEST API Gateway ID, once an image is configured."
  value       = try(yandex_api_gateway.mcp[0].id, null)
}

output "api_gateway_domain" {
  description = "Real API Gateway domain. After first creation, feed this exact value back through mcp_allowed_hosts for the next container revision."
  value       = try(yandex_api_gateway.mcp[0].domain, null)
}

output "mcp_endpoint" {
  description = "Remote MCP endpoint after Gateway creation."
  value       = try("https://${yandex_api_gateway.mcp[0].domain}/mcp", null)
}
