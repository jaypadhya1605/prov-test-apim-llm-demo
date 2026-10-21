# Evidence index

All **740 original JSON evidence files** are included as a public-safe historical snapshot. There are **205 call records** across 26 run folders, plus the root-level final-state and verified-results files. Identifiers are aliases; numeric/Boolean measurements are preserved. The [manifest](../publication-manifest.json) lists every file and its public SHA-256.

## Read these first

1. [Verified exact-project-v1 comparison](../evidence/verified-results.json).
2. [Complete exact-v1 Basic v2 suite](../evidence/v1-v2-measured/summary.json).
3. [Complete exact-v1 Developer/classic suite](../evidence/v1-classic-measured/summary.json).
4. [Final persistent controls](../evidence/final-state.json).
5. [Backend-origin throttling](../evidence/native-large-input-protection/summary.json) and [live quota restoration](../evidence/runtime-restored-final/runtime-restoration.json).
6. [Successful direct exact-v1 controls](../evidence/v1-direct-verified/summary.json).

## Complete run catalog

"Failure retained" means that run stopped or a hypothesis was not validated. A summary written during restoration does not by itself mean the run completed. Later successful runs supersede interrupted checks without deleting them.

| Run | JSON files | Call records | Purpose / outcome |
|---|---:|---:|---|
| [account-runtime-control](../evidence/account-runtime-control/) | 1 | 1 | Account control during asynchronous backend restoration |
| [capacity-validation](../evidence/capacity-validation/) | 1 | 0 | Normal deployment capacity and advertised limits |
| [classic-enforcement-mitigation](../evidence/classic-enforcement-mitigation/) | 70 | 18 | Completed preview quota, TPM, and request mitigation on classic |
| [classic-measured](../evidence/classic-measured/) | 84 | 23 | Preview baseline; failure retained when trace retrieval briefly returned 404 |
| [credential-audit](../evidence/credential-audit/) | 1 | 0 | Historical local evidence/credential checks, not a commercial scanner |
| [direct-controls](../evidence/direct-controls/) | 3 | 3 | Account Responses/Chat and project Chat controls |
| [direct-initial](../evidence/direct-initial/) | 2 | 1 | Initial direct diagnostic; failure retained |
| [direct-verified](../evidence/direct-verified/) | 2 | 1 | Early exact-project route failure retained |
| [exact-route-final](../evidence/exact-route-final/) | 6 | 3 | Exact v1 Responses became available; mixed results while old native limits persisted |
| [final-state](../evidence/final-state/) | 2 | 0 | Invalid-subscription controls on both gateways |
| [infrastructure-reconcile](../evidence/infrastructure-reconcile/) | 2 | 0 | Corrected what-if and full successful Incremental deployment |
| [native-large-input-protection](../evidence/native-large-input-protection/) | 32 | 3 | Backend-origin 429 on preview and account Responses; model restored in ARM |
| [native-model-protection](../evidence/native-model-protection/) | 29 | 3 | Small calls did not prove native throttling; failure retained |
| [project-api-version-probes](../evidence/project-api-version-probes/) | 2 | 0 | v1-plus-query rejection and working preview route |
| [project-probes](../evidence/project-probes/) | 3 | 1 | Project existence/endpoint diagnostics |
| [runtime-restoration-check](../evidence/runtime-restoration-check/) | 1 | 0 | ARM-versus-runtime restoration comparison |
| [runtime-restored-final](../evidence/runtime-restored-final/) | 10 | 9 | Three consecutive successful exact-v1 responses confirmed normal live limits |
| [v1-classic-measured](../evidence/v1-classic-measured/) | 117 | 36 | Complete exact-project-v1 suite on Developer/classic; passed |
| [v1-direct-verified](../evidence/v1-direct-verified/) | 5 | 4 | All exact project/account direct controls returned 200 with usage |
| [v1-v2-measured](../evidence/v1-v2-measured/) | 119 | 37 | Complete exact-project-v1 suite on Basic v2; passed |
| [v2-configure](../evidence/v2-configure/) | 6 | 0 | Initial policy/API configuration artifacts |
| [v2-enforcement-mitigation](../evidence/v2-enforcement-mitigation/) | 58 | 14 | Completed preview TPM and request mitigation on v2 |
| [v2-initial-account-baseline](../evidence/v2-initial-account-baseline/) | 10 | 1 | Initial request denied by the mismatched egress-IP allowlist |
| [v2-measured](../evidence/v2-measured/) | 89 | 25 | Preview baseline/quota worked; failure retained for invalid TPM-only policy attribute |
| [v2-preview-suite](../evidence/v2-preview-suite/) | 21 | 2 | Rotating egress IP still denied by the old allowlist; failure retained |
| [v2-preview-verified](../evidence/v2-preview-verified/) | 62 | 20 | Actual usage worked; policy-phase mismatch revealed propagation delay |

## File conventions

| Pattern | Meaning |
|---|---|
| `call-*.json` | UTC time, route, synthetic payload, HTTP status/body/headers, actual usage, and trace-derived backend status |
| `trace-*.json` | APIM inbound/backend/outbound events; use these to locate the component that rejected the request |
| `policy-*.json` | Exact operation policy XML and phase applied during that experiment |
| `probe-*.json` | Authenticated no-inference policy-propagation checks |
| `resources.json`, `model-*.json` | Gateway/project/model configuration or capacity before/reduced/restored |
| `summary.json` | Run results and calls; also written during restoration, so inspect any failure artifact |
| `failure.json` | Explicit reason an experiment stopped |
| `openapi.json` | Imported operation IDs, request schema, and response usage shape |

The historical filename numbering is retained. Some early diagnostic POSTs were stored under probe-specific names rather than the `call-*` convention, so 205 call records is not a claim that exactly 205 HTTP requests occurred. Control-plane and 204 policy probes are not model inference.

## Useful interpretation checks

- Baseline: `actualTotalTokens` and `x-lab-consumed` should both be 167 in the completed exact-v1 suites.
- Quota: 220-token policy, two 167-token completions, then APIM 403; this is subsequent enforcement, not a hard spend cap.
- TPM: 300-token-per-minute policy, then trace-confirmed APIM 429.
- Mitigation: `rate-limit-by-key` rejects Responses while the same-project Chat control remains 200.
- Backend protection: a 429 in `backendStatuses` means the model/backend rejected the call; do not mislabel it an APIM policy rejection.
- Final restoration: verify runtime `x-ratelimit-limit-requests=100` and `x-ratelimit-limit-tokens=100000`, not only ARM capacity/state.

For original, unredacted request-ID correlation, use the authorized private support channel. Public aliases cannot identify the live tenant or support record.
