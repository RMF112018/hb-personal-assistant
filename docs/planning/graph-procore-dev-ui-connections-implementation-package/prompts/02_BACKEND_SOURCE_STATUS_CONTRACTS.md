# P01 — Backend Environment and Source Status Contracts

Create/adapt browser-safe backend routes for environment and aggregate source status.

Required:
- inventory current FastAPI route conventions;
- add/adapt `/api/environment`;
- add/adapt `/api/sources/status`;
- include environment mode, source mode, live-read flags, Graph summary, Procore summary, scheduler/refresh summary if available;
- return user-safe errors;
- never call live Graph/Procore clients from status.

Tests:
- endpoint returns 200;
- no token/secret/cache path in response;
- live clients are not called;
- Dev live refresh action is disabled by default.
