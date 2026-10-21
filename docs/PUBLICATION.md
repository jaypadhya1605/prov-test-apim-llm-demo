# Public-copy boundaries

This repository is a complete **public-safe technical reference**, not an export of private customer correspondence or credentials. Making a public repository private later cannot retract existing clones, forks, or cached copies.

## Included

- Full experiment harness, focused tests, Bicep modules, and example parameter files.
- Historical discovery and deployment-plan JSON in [.azure](../.azure/).
- All **740 historical JSON evidence files**, including **205 call records**, APIM traces, backend synthetic response bodies, policy XML, failed experiments, model-capacity changes, and final-state checks.
- The measured findings, support-recommendation analysis, call runbook, suggested email, rerun instructions, historical costs, and cleanup guidance.
- A [manifest](../publication-manifest.json) with the public evidence file list, byte sizes, and SHA-256 hashes.

## Removed or replaced before the first push

- Real subscription, tenant, principal, support-case, resource, endpoint, and owner identifiers.
- Personal addresses, workstation paths, network IPs, and internal platform-instance headers.
- Credentials, JWT/bearer values, and other access material. Original experiment evidence already redacted credentials; the publication pass applied additional privacy transformations.
- Opaque request, trace, model-response, and message identifiers were pseudonymized consistently. Public aliases preserve cross-file relationships but cannot be used to correlate with Microsoft's private support systems.
- The original encrypted email and any private attachments/correspondence are excluded. The [support summary](SUPPORT-CONTEXT.md) retains the actionable technical meaning without reproducing the private thread.

Built-in public Azure role-definition IDs and the public Bicep GUID namespace are intentionally preserved; they are platform constants, not customer identities. Other GUIDs use stable version-5 pseudonyms. Example subscription/operator GUIDs are obvious placeholders. IPs use documentation address ranges.

Numeric and Boolean evidence values were compared with the source during publication and preserved, including token counts, thresholds, statuses, timings, capacity, and rejection flags. Model/API versions, policy structure, route shape, and measured UTC chronology are retained.

The original local lab files were left unchanged. No live resources were created, changed, or invoked by this publication task.

## Historical evidence versus new executions

- [evidence](../evidence/) is the immutable, sanitized historical study.
- New harness runs go to ignored `runs/` and retain the operator's actual environment details locally.
- The public harness requires explicit environment configuration; it cannot target the original lab by default.
- Bicep examples must be overridden with the operator's approved resource names and principal before cloud deployment.
- Historical audit JSON describes the checks performed at the time of the original study. It is not a claim that a commercial security scanner certified this repository.

## Before publishing additional data

Do not commit `runs/`, local environment files, original email, or raw support traces. Prepare a separate sanitized copy, keep credential material in memory, preserve measurement parity, and update the manifest only after checking every added file.

Run the offline checks:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python '.\tools\verify_reference.py'
python -m unittest discover -s '.\tests' -v
```

These checks are useful guardrails, not a guarantee that arbitrary new files contain no sensitive information. `.gitignore` is an additional barrier, not a sanitizer, and does not remove data from existing Git history.
