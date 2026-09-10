output "folder_id" { value = yandex_resourcemanager_folder.this.id }
output "registry_id" { value = yandex_container_registry.this.id }
output "runtime_service_account_id" { value = yandex_iam_service_account.runtime.id }
output "telegram_credentials_secret_id" { value = yandex_lockbox_secret.telegram_credentials.id }
output "reader_auth_secret_id" { value = yandex_lockbox_secret.reader_auth.id }
output "runtime_public_ip" { value = local.create_runtime ? yandex_vpc_address.public[0].external_ipv4_address[0].address : null }
output "runtime_mcp_url" { value = local.create_runtime ? "https://${replace(yandex_vpc_address.public[0].external_ipv4_address[0].address, ".", "-")}.sslip.io/mcp/" : null }
