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

output "publisher_service_account_id" {
  description = "Dedicated BIRZHA Forecast image publisher service account ID."
  value       = yandex_iam_service_account.publisher.id
}

output "publisher_oidc_federation_id" {
  description = "GitHub Actions OIDC workload identity federation ID for image publishing."
  value       = yandex_iam_workload_identity_oidc_federation.github_image_publisher.id
}

output "publisher_federated_credential_id" {
  description = "Federated credential ID binding GitHub main to the publisher service account."
  value       = yandex_iam_workload_identity_federated_credential.github_image_publisher.id
}

output "ydb_database_id" {
  description = "Durable YDB database used for Forecast and Outcome state."
  value       = yandex_ydb_database_serverless.state.id
}

output "ydb_connection_string" {
  description = "Full YDB SDK endpoint configured in the runtime container."
  value       = yandex_ydb_database_serverless.state.ydb_full_endpoint
}

output "mcp_auth_secret_id" {
  description = "Lockbox secret holding the generated MCP TEST bearer token."
  value       = yandex_lockbox_secret.mcp_auth.id
}

output "mcp_auth_secret_version_id" {
  description = "Pinned Lockbox version injected into the MCP TEST container."
  value       = yandex_lockbox_secret_version.mcp_auth.id
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
