# Ownership boundary

The shared bridge repository/directory owns:
- protocol wire format;
- Apps Script transport/security implementation;
- reusable client adapter contract;
- deployment templates;
- common acceptance/security tests.

Client projects own:
- project orchestration and locks;
- business data models;
- archive structure/policies;
- provider/API logic;
- canonical commit semantics beyond the transport primitive;
- project-specific monitoring and SLOs.
