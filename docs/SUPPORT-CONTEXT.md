# Support context and call runbook

This is a technical summary, not a publication of the customer's original email. Personal names, the real support number, correspondence, and tenant details are intentionally omitted.

## Original report and support position

- The customer reported different behavior with the same model, subscription, and `llm-token-limit` policy.
- On non-streaming `projects/{project}/openai/v1/responses`, consumed tokens stayed at **4** and the TPM/quota headers did not decrement.
- Chat Completions decremented normally.
- Support's working explanation was that the project Responses path appeared to remain in estimate-only accounting. That was not an independently established engineering root cause.
- Support recommended capturing matched evidence before changes, removing the token limiter only from the affected operation, using verified Foundry/model protections, and substituting request throttling if immediate APIM protection was needed.
- The earlier case closure was administrative for lack of response, not proof that accounting was repaired.

The original learning goals were to reproduce the customer setup as closely as possible, determine whether the failure occurred, test each recommendation, and explain a verified cause/fix without confusing mitigation with resolution.

## What the lab adds

The [final exact-v1 suites](../evidence/verified-results.json) compare project Responses and project Chat on the same real model, using both classic and Basic v2 gateways. Both estimation settings reported **167 consumed / 167 actual tokens**. Token quotas and TPM were enforced. The flat-4 consumed-token symptom did not reproduce.

Some remaining-quota headers were stale or non-monotonic even though subsequent enforcement worked. The lab therefore supports checking enforcement directly rather than treating header arithmetic as the sole test.

Operation-scoped request throttling worked, but Basic v2 allowed one extra successful request in this small test. Native model rate protection also produced backend-origin 429s, but its asynchronous propagation and shared deployment scope do not prove a hard per-project hourly token quota.

## Forty-minute call

### 0-5 minutes: freeze the baseline

Record, without exposing secrets:

- Exact backend URL, route/API version, model deployment/version, region, gateway tier/generation, and timestamp.
- Caller APIM subscription ID and identity source. Do not record subscription keys or bearer credentials.
- Complete effective policy at global, product, API, and operation scope, including inherited `<base />` behavior and outbound transformations.
- API/OpenAPI schema and whether the call is truly non-streaming.

Do not remove protections or change several things at once before saving the failing baseline.

### 5-15 minutes: capture one matched pair

Use equivalent synthetic prompts and the same model/caller:

1. One failing exact project v1 Responses request.
2. One working Chat Completions request.

For each, capture UTC time, request ID, raw backend response body/usage, APIM consumed/remaining headers, and trace. Current APIM tracing uses debug credentials and `listTrace`; the old `Ocp-Apim-Trace` mechanism is not the reference workflow.

Check whether usage is already missing or changed before APIM accounting. Preserve response bodies with `preserveContent: true` when tracing a synthetic test. Use an approved support channel for raw customer material, not public GitHub.

### 15-25 minutes: prove enforcement

Use fresh stable counter keys and sequential completed requests. Check policy propagation first; the harness's authenticated 204 probe avoids spending inference tokens on policy-readiness checks.

- Keep TPM high and set only a small quota for the quota test. A policy quota exhaustion returns **403**, not 429.
- Keep quota out of the way and use a low TPM for the rate test. A token-rate rejection returns **429**.
- Inspect the trace to identify the rejecting policy and confirm whether a backend request actually occurred.
- Account for token-window replenishment, UTC fixed quota resets, response-based usage updates, and distributed counter timing.
- Recheck `estimate-prompt-tokens=false` only after retaining the original baseline.

In the lab, two 167-token responses crossed a 220-token quota and the next call was blocked. This is successful subsequent enforcement, not an exact 220-token spend ceiling.

### 25-35 minutes: test the narrow mitigation

At the Responses operation only:

1. Preserve inherited authentication and unrelated protections.
2. Replace `llm-token-limit` with request throttling keyed to a stable APIM subscription or client identity.
3. Demonstrate an APIM-generated request-throttle 429.
4. Confirm a Chat control still returns 200.
5. Document explicitly that this caps request rate approximately, not token cost.

Before relying on "Foundry limits," establish which component enforces them. The documented Foundry control-plane token feature uses APIM/AI Gateway; it is not automatically independent from the same accounting implementation.

### 35-40 minutes: decide the next action

| Observation | Decision |
|---|---|
| Consumed stays 4, actual usage is larger, and crossed limits fail to reject while Chat works | Keep/reopen; provide matched evidence for engineering investigation |
| Remaining headers are stale but usage accounting and later rejection work | Separate reporting/counter-visibility issue from missing enforcement |
| Backend usage is missing or has an unexpected shape | Investigate backend response/route/schema before blaming persisted APIM counters |
| Request throttling works but original token behavior is unverified | Mitigation only; do not call the defect fixed |
| A specific change restores accounting and rejection on the previously failing route | Validate the before/after result with the customer before closure |

Record the final protection state and roll back temporary low backend capacity. Verify live rate-limit headers, not just ARM `Succeeded`.

## Suggested email

**Subject: SR &lt;private support number&gt; - validation results and next steps**

Hi,

We built a separate Azure lab and compared project v1 Responses with project v1 Chat through classic and v2 APIM gateways. Both accounted for actual usage and enforced low token quotas/TPM limits. We saw some stale remaining-quota headers, but not the flat-4 consumed-token symptom.

Operation-scoped request throttling worked without affecting Chat. This is a temporary request-rate safeguard, not a token-accounting fix or hard spending cap.

These results do not prove the customer's environment is resolved. We recommend keeping the case open, or reopening it if necessary, while we capture a matched failing Responses call and working Chat call with effective policies, raw backend usage, timestamps, request IDs, and traces. A proposed fix should be validated against the original failing route before closure.

Thanks.
