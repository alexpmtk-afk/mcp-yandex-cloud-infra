# Implementation status

Current branch: `feature/google-drive-bridge-v1`

Implemented in this branch:
- shared architecture and protocol v1;
- project isolation model;
- Marketplaces client profile;
- Birzha client profile;
- deployment standard;
- acceptance matrix;
- migration plan;
- Apps Script manifest baseline.

Next implementation items before production cutover:
- shared Apps Script runtime source;
- reusable Python client adapter;
- project-specific deployment/bootstrap templates;
- executable acceptance tests;
- Marketplaces reference migration;
- Birzha reference migration;
- cross-project concurrent acceptance.

No production client has been cut over by this branch yet.
