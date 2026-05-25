# Phase 0 Certificate Viability Proof

## 1. Summary
Phase 0 certificate viability testing succeeded for local certificate-backed Microsoft identity authentication using the existing HB SharePoint Creator certificate bundle. The proof acquired a Microsoft Graph app-only token and safely classified claims without exposing raw token material. A minimal Graph organization probe returned `403 Authorization_RequestDenied`, which is consistent with current app permission posture for that endpoint and does not invalidate certificate auth viability.

## 2. Known Inputs
- `tenant_id`: `0e834bd7-628b-42c8-b9ec-ecebc9719be4`
- `tenant_display_name`: `Hedrick Brothers Construction`
- `tenant_domain_default`: `hedrickbrothers.com`
- `tenant_domain_initial`: `hedrickbrotherscom.onmicrosoft.com`
- `sharepoint_resource_root`: `https://hedrickbrotherscom.sharepoint.com/`
- `client_id`: `08c399eb-a394-4087-b859-659d493f8dc7`
- `app_name`: `HB SharePoint Creator`
- `certificate_key_id`: `72b2e600-eac6-4b1b-a4b1-4d48048e6667`
- `certificate_bundle_path`: `/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem`

## 3. Certificate File Visibility
Command evidence:
- `test -f "$CERT"`
- `ls -l "$CERT"`
- `stat -f "%Sp %Su %Sg %N" "$CERT"`

Observed:
- File exists: `yes`
- Owner: `bobbyfetting`
- Group: `staff`
- Mode: `-rw-------` (`600`)

Assessment:
- Current file permissions are appropriately restrictive for a local private key bundle.
- No remediation required.

## 4. Certificate Metadata
Command evidence:
- `openssl x509 -in "$CERT" -noout -subject -issuer -dates -fingerprint -sha1`
- `openssl x509 -in "$CERT" -noout -serial`

Observed metadata:
- Subject: `CN=HB SharePoint Creator Local Provisioning`
- Issuer: `CN=HB SharePoint Creator Local Provisioning`
- Valid from: `May 15 16:28:03 2026 GMT`
- Valid until: `May 15 16:28:03 2027 GMT`
- SHA-1 fingerprint: `6E:BA:F3:63:A3:F9:DB:AF:33:8A:6F:73:64:CE:12:DD:05:FB:C0:BE`
- Serial: `047DE1664F3EE68F2B5511CB83185859897F302C`

## 5. Private Key Usability Check
Command evidence:
- `openssl pkey -in "$CERT" -noout -check`

Observed:
- Result: `Key is valid`

Conclusion:
- The bundle includes a usable private key for signing client assertions.

## 6. Manifest / Known App Registration Alignment
Local app registration manifest with matching `keyCredentials` was not found in this repo scope.

Alignment performed:
- Known-values-only alignment using provided closed values (`tenant_id`, `client_id`, `certificate_key_id`).
- Runtime token claims confirmed:
  - `tid` == expected tenant
  - `appid` == expected client ID

Important limitation:
- `certificate_key_id` (`72b2e600-eac6-4b1b-a4b1-4d48048e6667`) could not be directly verified against local manifest artifacts in this repository. Full `keyCredentials.keyId` match remains externally unverified in this prompt.

## 7. Certificate-Backed Token Acquisition Result
Execution artifact:
- Proof script: `scripts/proofs/prove_certificate_auth.py`
- Runtime: local `.venv` using `msal 1.36.0`, `requests 2.34.2`

Result:
- Token acquisition: `success`
- Scope requested: `https://graph.microsoft.com/.default`
- Raw token was not printed or persisted in report output.

## 8. Safe Graph Probe Result
Probe used:
- `GET https://graph.microsoft.com/v1.0/organization?$select=id,displayName,verifiedDomains`

Result:
- HTTP status: `403`
- Sanitized error: `Authorization_RequestDenied` / `Insufficient privileges to complete the operation.`
- Tenant ID from response payload: not returned (request denied)

Interpretation:
- This is an authorization outcome for the specific probe endpoint under current app-only permissions; it does not indicate certificate signing failure.

## 9. Token Claim Classification
Safe decoded claim fields:
- `aud`: `https://graph.microsoft.com`
- `iss`: `https://sts.windows.net/0e834bd7-628b-42c8-b9ec-ecebc9719be4/`
- `appid`: `08c399eb-a394-4087-b859-659d493f8dc7`
- `tid`: `0e834bd7-628b-42c8-b9ec-ecebc9719be4`
- `roles`: present (`Sites.Selected`, `Sites.ReadWrite.All`, `Group.ReadWrite.All`, `Sites.Manage.All`, `GroupMember.ReadWrite.All`, `Sites.Create.All`, `Sites.FullControl.All`)
- `scp`: absent (`null`)
- `exp`: present
- `nbf`: present

Classification:
- Token type: **app-only**
- Basis: `roles` present and `scp` absent.

## 10. Security Findings
- Private key bundle exists with restrictive permissions (`600`).
- Private key usability validated without exposing key contents.
- Token acquisition and claims inspection performed without logging raw token.
- No mailbox/calendar/content retrieval workflows were executed.
- Probe endpoint returned authz denial; no tenant/user content was processed.

## 11. Failure Modes / Remediation
Potential failure modes and remediations:
1. Certificate file missing or weak permissions.
- Remediation: restore bundle to expected path and enforce `chmod 600`.

2. Bundle parsing/key mismatch failures in MSAL.
- Remediation: provide explicit `thumbprint` + `public_certificate` + private key in MSAL credential object (implemented in proof script).

3. Token acquisition failure from authority/network.
- Remediation: verify DNS/network to `login.microsoftonline.com`; verify tenant/client values.

4. Graph probe authorization denial.
- Remediation: treat as expected unless endpoint access is required later; do not change permissions in this phase.

## 12. Conclusion
The existing HB SharePoint Creator certificate is locally viable for certificate-backed app authentication in Phase 0. App-only token acquisition is proven with correct tenant/client claim alignment and safe classification behavior. Endpoint-level authorization for `organization` probe is currently insufficient (403), but this does not invalidate certificate viability.

## 13. Evidence Appendix
- File checks:
  - `certificate bundle exists`
  - `-rw------- 1 bobbyfetting staff ... hb-sharepoint-creator.bundle.pem`
- OpenSSL metadata:
  - Subject/issuer/dates/fingerprint/serial captured (see sections 4–5)
- Proof script output:
  - `status: success`
  - `token_type_classification: app-only`
  - `graph_probe.http_status: 403`
