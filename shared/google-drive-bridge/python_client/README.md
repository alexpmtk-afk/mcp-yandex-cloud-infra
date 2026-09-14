# Python client

Reusable protocol-v1 adapter for Yandex Cloud workloads.

Example:

```python
from python_client import BridgeConfig, GoogleDriveBridgeClient

client = GoogleDriveBridgeClient(
    BridgeConfig(
        url=bridge_url,
        secret=bridge_secret,
        project_id="marketplaces",
    )
)
status = await client.health()
```

Rules:
- generate/reuse one idempotency key for one logical mutation across retries;
- never log the secret or resumable session URI;
- keep resource locks and durable job state outside the bridge client;
- validate health project/root/protocol before enabling project writes.
