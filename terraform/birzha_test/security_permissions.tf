# The deployment identity needs Lockbox metadata visibility when creating a
# Serverless Container revision that references a Lockbox secret. Payload access
# remains separately scoped to the single MCP authentication secret.
resource "yandex_lockbox_secret_iam_member" "deployer_mcp_auth_metadata" {
  secret_id   = yandex_lockbox_secret.mcp_auth.id
  role        = "lockbox.viewer"
  member      = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after = 10
}
