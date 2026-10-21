# Synthetic APIM token-policy lab

**The reported "consumed tokens stays at 4" defect did not reproduce.** The original study deployed real Azure resources and measured the exact project v1 route. Keep/reopen the customer's support case until the customer's original failing environment is validated; a healthy separate lab is not a causal fix.

**Start here:** [Quick reference and setup](QUICKSTART.md) | [Customer-call runbook](docs/SUPPORT-CONTEXT.md) | [All evidence](docs/EVIDENCE-INDEX.md) | [Public-copy boundaries](docs/PUBLICATION.md)

This public copy contains the complete technical study and **740 sanitized JSON evidence files**, including 205 call records. Names, support IDs, cloud identities, network addresses, and correlation IDs below are aliases, not live connection information. The original encrypted email and private correspondence are excluded. Measurements are preserved; the [publication manifest](publication-manifest.json) records every evidence file's SHA-256 hash.

## What was built

Example subscription alias: `00000000-0000-0000-0000-000000000001`

Example resource-group alias: `rg-apim-token-lab`

Resource location: East US 2. The resource group's West US metadata does not constrain its resources.

| Resource | Configuration |
|---|---|
| `apim-lab-classic-example` | APIM Developer, classic gateway, system-assigned managed identity |
| `apim-lab-v2-example` | APIM Basic v2, system-assigned managed identity |
| `ai-token-lab-example` | Foundry AIServices account; project management enabled; local/key authentication disabled |
| `project-token-lab` | Real Foundry project |
| `lab-model` | `gpt-5-mini`, version `2025-08-07`, GlobalStandard, normal capacity 100 |

Normal model capacity advertises 100 RPM and 100,000 TPM, deliberately above the APIM limits being tested. This is quota allocation for a pay-per-token deployment, not provisioned-throughput billing.

The corrected full Incremental deployment **succeeded**: [deployment evidence](evidence/infrastructure-reconcile/deployment.json).

Public endpoints were explicitly approved. APIM requires both an APIM subscription key and an Entra token for the designated operator in the deployment tenant. Corporate egress rotated between several public IPs, so a single-IP allowlist was unreliable and was replaced by these identity controls. APIM uses managed identities for backend access. Keys and tokens are obtained in memory, not written to configuration files. No certificate or private-key files are needed.

This is an operator-only, synthetic-data lab, not a production deployment or a PHI-approved environment.

## Route availability and reproduction fidelity

The exact project **v1 Responses** endpoint initially returned 404 even though the project existed and project Chat/preview Responses worked. It subsequently returned 200. No particular change was isolated as the causal fix for that transient 404. The study therefore continued on the exact v1 route rather than stopping at preview results:

| Backend route | Observed result |
|---|---|
| `/api/projects/project-token-lab/openai/v1/responses` | Initially 404, later **200**, actual usage available |
| `/api/projects/project-token-lab/openai/v1/chat/completions` | 200, actual usage available |
| `/api/projects/project-token-lab/openai/responses?api-version=2025-11-15-preview` | 200, actual usage available |
| Account `/openai/v1/responses` | 200, actual usage available |
| Account `/openai/v1/chat/completions` | 200, actual usage available |

Adding `api-version` to the `/v1` project path was also tested: the service rejects that combination with 400. The preview path is therefore a separate, explicitly labeled diagnostic variant, not an invisible rewrite of the reported failing route.

Evidence: [initial direct controls](evidence/direct-controls/), [project probes](evidence/project-probes/), [API-version probes](evidence/project-api-version-probes/), and [successful exact-v1 direct controls](evidence/v1-direct-verified/summary.json).

the customer's actual model/version, region, gateway tier/version, complete effective policy, OpenAPI schema, and Foundry gateway topology were unavailable. The originally considered `gpt-4o-mini` was rejected by deployment preflight as deprecating, despite appearing in the catalog with quota. Selecting `gpt-5-mini` is another documented fidelity difference, **not a fix for the customer's issue**.

## Measured accounting and enforcement

All ordinary test calls are non-streaming, use equivalent synthetic prompts and the same model deployment, and cap output at 128 tokens. Successful ordinary calls reported **167 actual total tokens**. The policy's `x-lab-consumed` header also reported **167**, not 4.

Both `estimate-prompt-tokens=true` and `false` were tested. Counters are isolated by run, phase, API, operation, and the real `context.Subscription.Id`; the caller subscription stays the same.

The final comparisons use the **exact project v1 Responses route** against **project v1 Chat Completions**, on the same project and deployment:

| Test | Developer / classic | Basic v2 |
|---|---|---|
| Successful call: actual / APIM consumed | 167 / 167 | 167 / 167 |
| Project Responses baseline quota, estimation enabled | 9833, 9666, 9499 | 9833, 9666, 9833 |
| Project Responses, 220-token hourly quota | 200, 200, **403** | 200, 200, **403** |
| Chat, 220-token hourly quota | 200, 200, **403** | 200, 200, **403** |
| Project Responses, 300 TPM | 200, 200, **429** | 200, 200, **429** |
| Chat, 300 TPM | 200, 200, **429** | 200, 200, **429** |
| Project request throttle, configured 3 calls / 60 seconds | 200, 200, 200, **429** | 200, 200, 200, 200, **429** |
| Chat control after project-only mitigation | **200** | **200** |
| Caller without Entra authentication | **401** | **401** |

The enforcement rejections above were checked against APIM traces: the appropriate limiter ran and no backend response was received for those rejected calls. They were not mistaken for backend throttling, authentication failures, or the initial IP-filter failures. Both complete exact-route suites passed.

**These are not exact billing or spend ceilings.** Two completed 167-token calls already total 334 tokens before the 220-token quota blocks the next request. Non-streaming completion usage is learned after a call; remaining headers can lag, and period boundaries and distributed throttling affect observations. Some baseline quota headers were stale or non-monotonic, including the v2 Responses sequence shown above. The estimation-disabled v2 Responses sequence was 9833, 9666, 9499. This distinguishes a remaining-header anomaly from all accounting staying at 4 with no later enforcement.

The Basic v2 request limiter allowed a fourth successful call despite a setting of three. Microsoft explicitly documents that distributed rate limiting is not completely accurate. The experiment proves request throttling works, not an exact three-call or financial guarantee.

Evidence:

- [Verified exact-v1 results](evidence/verified-results.json).
- [Complete exact-v1 v2 suite](evidence/v1-v2-measured/summary.json) and [complete exact-v1 classic suite](evidence/v1-classic-measured/summary.json).
- [v2 baseline and quota](evidence/v2-measured/) and [completed v2 enforcement/mitigation](evidence/v2-enforcement-mitigation/summary.json).
- [classic baseline](evidence/classic-measured/) and [completed classic enforcement/mitigation](evidence/classic-enforcement-mitigation/summary.json).
- The earlier suites used explicitly labeled preview/account controls. Earlier failed runs are intentionally retained: an invalid TPM-only policy attribute and a not-yet-available trace interrupted two runs. Later focused runs completed the missing phases before the exact-v1 suites; neither interruption is the customer's token-accounting bug.

## What support's recommendations mean

### 1. Preserve matched evidence before changing policy

This is the most important step. Compare backend `usage.total_tokens`, APIM consumed/remaining headers, and subsequent enforcement on the same deployment and caller. Save raw synthetic backend responses, UTC times, request IDs, and traces. A constant header alone does not prove that persisted counters or enforcement are broken.

The harness uses current debug credentials and `listTrace`, not the obsolete `Ocp-Apim-Trace` mechanism. Its outbound trace preserves the backend body before returning it.

### 2. Replace only the affected operation's token limiter with request throttling

This mitigation was demonstrated on the exact project v1 Responses operation on both gateway generations, as well as in the earlier preview controls. Authentication, managed identity, subscription identity, and inherited policies were preserved. Same-project v1 Chat continued working. The counter key uses a stable APIM subscription value, not a rotating client IP.

It is a **mitigation**, not a token-accounting repair. Requests can have very different token costs. Do not treat a request rate as a token quota or spending cap.

### 3. Rely on Foundry/project/model protection only after verifying what it actually is

The linked Foundry project/model token-limit feature uses **APIM / AI Gateway**. Moving the same accounting policy into that layer is not automatically independent protection from an APIM accounting defect. The lab's Basic v2 gateway was not associated with Foundry's native control-plane governance feature.

A separate native-deployment experiment temporarily reduces `lab-model` to capacity 1, checks its advertised **1 RPM / 1000 TPM**, removes APIM token limiting on the test operations, and verifies whether any 429 is actually received from the backend. Capacity and operation token policies are restored in `finally`.

The initial three small calls all succeeded at 167 tokens each; ARM metadata alone did **not** establish that the low limits had reached the backend. In the larger-input experiment, the first accepted 2017-token call still advertised the old **100 RPM / 100,000 TPM**. The next project preview Responses call and the account Responses control both returned **backend-origin 429**, advertising the new **1 RPM / 1000 TPM**, with APIM token limiting removed. This validates independent backend rate protection on those paths, not a strict first-request token cutoff.

Restoration was asynchronous too. ARM reported capacity 100 and `Succeeded`, but some project calls still advertised 1 RPM / 1000 TPM and were throttled. The final check waited for **three consecutive successful exact-v1 Responses calls advertising 100 RPM / 100,000 TPM** before starting exact-route accounting tests. Its earlier direct 429s also establish that native protection reached the exact project v1 route.

Evidence: [native large-input experiment](evidence/native-large-input-protection/summary.json) and [verified data-plane restoration](evidence/runtime-restored-final/runtime-restoration.json). The helper now waits for live header confirmation, with a bounded timeout; ARM success is not treated as proof of immediate runtime propagation. Do not infer a per-project hourly quota or hard spending limit from deployment-rate protection.

## How to understand "what, why, and resolved"

- **What the customer reported:** the Responses route apparently retains a small estimate while the Chat route performs normal accounting.
- **Why that might occur:** APIM can estimate prompt tokens before sending the call, then reconcile with non-streaming response usage. If response usage is not recognized or the effective route/policy differs, the estimate could remain. This is support's hypothesis, not an independently established root cause.
- **What this lab established:** exact project v1 Responses and project v1 Chat both reconcile to 167 actual tokens and enforce quota/TPM limits on both gateway generations. The same-project request-only mitigation blocks Responses without blocking Chat. Remaining-header anomalies can occur despite working enforcement. The original 404 cleared, but its precise cause was not isolated.
- **What was resolved here:** deployment/authentication/experiment reliability issues, plus demonstrated request-based mitigation. No causal fix for the customer's original symptom was established.
- **Closure criterion:** a before/after change must restore actual accounting and quota/TPM rejection on the customer's previously failing exact route, or Microsoft engineering must confirm and validate the service-side fix. Healthy neighboring routes are insufficient.

Lab setup issues repaired along the way were a wrong home-tenant principal, concurrent Foundry child provisioning, a deprecating model, rotating egress IPs, policy propagation, and asynchronous backend quota propagation. These are lab setup findings, not evidence for the customer's root cause.

Gateway policy changes are now checked with an authenticated, no-inference 204 probe before measured calls. The probe runs after inherited authentication and before the limiter, returns no model output, and consumes no model tokens. A fixed five-second sleep had demonstrably tested an old policy. Trace retrieval retries only the specific not-yet-available 404 condition and fails explicitly if still unavailable.

## Rerun

No Python packages are required. These local checks do not call Azure or incur model charges:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s '.\tests' -v
python '.\tools\verify_reference.py'
az bicep build --file '.\infra\main.bicep' --stdout | Out-Null
```

Infrastructure is in [main.bicep](infra/main.bicep) and the example [main.bicepparam](infra/main.bicepparam). Follow the [configuration and deployment guide](QUICKSTART.md) to set your own subscription, names, and target-tenant operator principal. The public harness fails before any Azure call if configuration is missing or the subscription is still an example. Every CLI/management operation is explicitly scoped; no global subscription default is changed.

The Bicep deploys resources and identity restrictions. [lab.py](lab.py) configures the APIs, operation policies, traces, and measurements.

The original study used a 120-record initial ceiling, expanded deliberately to **240 total** when the exact v1 route became available; it finished with **205 records**. Probes and a few earlier diagnostic requests are separate control traffic. Those historical records are retained in [evidence](evidence/).

In the public harness, new results go to ignored `runs/`, so published evidence is not overwritten or counted against a new checkout's default **120-record** live-run ceiling. After configuring your own environment:

```powershell
python '.\lab.py' run --gateway v2 --project-api project `
  --run-id 'manual-v2-new-batch'

# Or run only the needed phases; do not repeat the baseline unnecessarily.
python '.\lab.py' run --gateway classic --project-api project `
  --phases tpm mitigation --run-id 'manual-classic-focused'
```

Do not run the native-capacity experiment concurrently with other model tests: it changes their shared deployment, and runtime propagation can take many minutes. `--project-api project` selects exact v1 Responses **and project v1 Chat**. `--project-api project-preview` deliberately selects preview Responses with account Chat controls; it is not a silent fallback.

## Persistent state, costs, and cleanup

The normal operation policy is 10,000 TPM plus a 10,000-token hourly quota. These are **per isolated lab counter**, not an account-wide aggregate budget across APIs or both gateways. Request-only mitigation and reduced backend capacity are temporary experiments.

Final live inspection verified **all 12 operation token policies**, both operator identity gates, managed-identity backend configuration, disabled Foundry local authentication, and normal model capacity 100. Invalid APIM subscription credentials returned 401 on both gateways. See [persistent-state proof](evidence/final-state.json).

The original study persisted **205 call records**, below its explicitly allocated 240-record ceiling. Its 21 unit tests, Bicep compilation, and full Azure deployment succeeded. The public version adds configuration and snapshot-integrity tests. Historical credential-pattern checks are recorded in [the evidence audit](evidence/credential-audit/audit.json); this is not an automated security-scanner assessment.

Retail gateway estimates retrieved for this study:

| Gateway | USD/hour | USD/day |
|---|---:|---:|
| Developer | 0.06580 | 1.57920 |
| Basic v2 | 0.20548 | 4.93152 |
| **Both** | **0.27128** | **6.51072** |

Model tokens and applicable extras are additional. Actual billing was not queried; taxes, discounts, and other charges are excluded. Resources were left running after the original study for learning. **No expiry or automatic teardown is configured.** Disabling an API does not stop APIM's standing charges.

To stop charges later, delete only these named lab gateways and Foundry account after confirming they are no longer needed; deleting the Foundry account also removes its project/model children. Recheck the resource-group inventory before considering deletion of the entire group, which existed before this task.

## Suggested email to the customer

**Subject: SR SUPPORT-CASE-REDACTED - validation results and next steps**

Hi the customer,

We built a separate Azure lab and tested the same model behind classic and v2 APIM gateways, including project v1 Responses against project v1 Chat. Both account for 167 actual tokens and enforce low token quotas/TPM limits. We did see some stale remaining-quota headers, but not the flat-4 consumed-token symptom. Operation-scoped request throttling also works without affecting Chat, but it is a mitigation rather than a token-accounting fix.

We have not reproduced your flat-4 symptom, so these results do not establish a fix in your environment. We recommend keeping the case open, or reopening it if necessary. On our call, let's capture a matched failing v1 Responses call and working Chat call, including raw backend usage, effective policies, timestamps, request IDs, and traces. Support can then investigate the environment-specific difference, and we can validate any proposed fix against your original failing path before closing.

Thanks.

## References

- [llm-token-limit behavior, supported APIs, estimation, and quota caveats](https://learn.microsoft.com/azure/api-management/llm-token-limit-policy).
- [Request rate limiting and distributed-accuracy caveat](https://learn.microsoft.com/azure/api-management/rate-limit-by-key-policy).
- [Current APIM request tracing](https://learn.microsoft.com/azure/api-management/api-management-howto-api-inspector).
- [Foundry project/model token limits use AI Gateway](https://learn.microsoft.com/azure/foundry/control-plane/how-to-enforce-limits-models).
- [Azure OpenAI deployment quota and rate management](https://learn.microsoft.com/azure/foundry/openai/how-to/quota).
