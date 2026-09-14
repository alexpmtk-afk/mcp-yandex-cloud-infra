# Client integration checklist

Before cutover, each client team/chat must confirm:

- [ ] project has its own Apps Script deployment
- [ ] project has its own secret
- [ ] project has its own fixed Drive root
- [ ] project has its own Yandex Lockbox binding
- [ ] client sends `project_id`
- [ ] client generates `request_id`
- [ ] every mutation sends stable `idempotency_key`
- [ ] client retains project-side resource locks/orchestration
- [ ] deep health validates project/root/protocol
- [ ] common security acceptance passes
- [ ] project-specific transport acceptance passes
- [ ] old shared credential/deployment path is disabled only after rollback window
