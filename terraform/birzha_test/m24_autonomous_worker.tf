variable "m24_worker_image_url" {
  description = "Immutable BIRZHA M24 image URL for the private autonomous orchestration worker. Null keeps the worker and timer disabled."
  type        = string
  default     = null
  nullable    = true
}

variable "m24_worker_source_sha" {
  description = "Exact birzha-mcp-forecast source commit represented by the M24 worker image."
  type        = string
  default     = "0000000000000000000000000000000000000000"

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.m24_worker_source_sha))
    error_message = "m24_worker_source_sha must be a full 40-character Git commit SHA."
  }
}

resource "yandex_iam_service_account" "orchestrator_timer" {
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-orchestrator-timer"
  description = "Least-privilege identity used only by the timer to invoke the private M24 orchestration worker"
}

resource "yandex_iam_service_account_iam_member" "terraform_orchestrator_timer_user" {
  service_account_id = yandex_iam_service_account.orchestrator_timer.id
  role               = "iam.serviceAccounts.user"
  member             = "serviceAccount:${var.terraform_deployer_service_account_id}"
  sleep_after        = 5
}

resource "yandex_serverless_container" "orchestrator_worker" {
  count              = var.m24_worker_image_url == null ? 0 : 1
  folder_id          = yandex_resourcemanager_folder.birzha_test.id
  name               = "birzha-mcp-forecast-orchestrator"
  description        = "Private autonomous orchestration worker; no public API Gateway"
  memory             = 512
  cores              = 1
  concurrency        = 1
  execution_timeout  = "120s"
  service_account_id = yandex_iam_service_account.runtime.id

  runtime {
    type = "http"
  }

  dynamic "secrets" {
    for_each = var.m25_market_mirror_bridge_url == null ? [] : [1]
    content {
      id                   = var.m25_shared_drive_bridge_secret_id
      version_id           = var.m25_shared_drive_bridge_secret_version_id
      key                  = "google_drive_bridge_secret"
      environment_variable = "BIRZHA_MARKET_MIRROR_BRIDGE_SECRET"
    }
  }

  image {
    url     = var.m24_worker_image_url
    command = ["python", "-m", "birzha.worker"]
    environment = {
      BIRZHA_STATE_BACKEND                = "ydb"
      BIRZHA_ORCHESTRATOR_WORKER          = "true"
      BIRZHA_SOURCE_COMMIT                = var.m24_worker_source_sha
      YDB_CONNECTION_STRING               = yandex_ydb_database_serverless.state.ydb_full_endpoint
      BIRZHA_MARKET_MIRROR_REQUIRED       = var.m25_market_mirror_required ? "true" : "false"
      BIRZHA_MARKET_MIRROR_BRIDGE_URL     = coalesce(var.m25_market_mirror_bridge_url, "")
      BIRZHA_MARKET_MIRROR_ROOT_FOLDER_ID = var.m25_market_mirror_root_folder_id
    }
  }

  labels = merge(local.labels, {
    component  = "orchestrator-worker"
    source_sha = substr(var.m24_worker_source_sha, 0, 16)
  })

  lifecycle {
    precondition {
      condition     = !var.m25_market_mirror_required || var.m25_market_mirror_bridge_url != null
      error_message = "m25_market_mirror_bridge_url must be set before mandatory market mirror is enabled."
    }
    precondition {
      condition = (
        var.m25_market_mirror_bridge_url == null ||
        var.m25_shared_drive_bridge_secret_version_id != null
      )
      error_message = "m25_shared_drive_bridge_secret_version_id is required when the shared Drive bridge is enabled."
    }
  }

  depends_on = [
    yandex_ydb_database_iam_binding.runtime_editor,
    yandex_resourcemanager_folder_iam_member.runtime_registry_pull,
    yandex_lockbox_secret_iam_member.runtime_market_mirror,
  ]
}

resource "yandex_serverless_container_iam_member" "orchestrator_timer_invoker" {
  count        = var.m24_worker_image_url == null ? 0 : 1
  container_id = yandex_serverless_container.orchestrator_worker[0].id
  role         = "serverless-containers.containerInvoker"
  member       = "serviceAccount:${yandex_iam_service_account.orchestrator_timer.id}"
}

resource "yandex_function_trigger" "orchestrator_timer" {
  count       = var.m24_worker_image_url == null ? 0 : 1
  folder_id   = yandex_resourcemanager_folder.birzha_test.id
  name        = "birzha-mcp-forecast-orchestrator-timer"
  description = "Invoke one safe autonomous orchestration tick every minute"

  timer {
    cron_expression = "* * ? * * *"
    payload         = "m24-orchestration-tick"
  }

  container {
    id                 = yandex_serverless_container.orchestrator_worker[0].id
    service_account_id = yandex_iam_service_account.orchestrator_timer.id
    retry_attempts     = 2
    retry_interval     = 20
  }

  depends_on = [
    yandex_serverless_container_iam_member.orchestrator_timer_invoker,
    yandex_iam_service_account_iam_member.terraform_orchestrator_timer_user,
  ]
}

output "m24_orchestrator_worker_container_id" {
  description = "Private M24 autonomous worker container ID when enabled."
  value       = try(yandex_serverless_container.orchestrator_worker[0].id, null)
}

output "m24_orchestrator_timer_trigger_id" {
  description = "Timer trigger ID that invokes the private M24 worker every minute when enabled."
  value       = try(yandex_function_trigger.orchestrator_timer[0].id, null)
}

output "m24_orchestrator_timer_service_account_id" {
  description = "Least-privilege service account used by the M24 timer trigger."
  value       = yandex_iam_service_account.orchestrator_timer.id
}
