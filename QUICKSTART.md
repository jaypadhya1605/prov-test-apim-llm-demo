# Quick reference

**Verdict:** the reported flat-4 consumed-token defect was not reproduced. Exact project v1 Responses and project v1 Chat both accounted for 167 actual tokens and enforced quota/TPM on classic and v2 gateways. Keep the customer case open until the customer's failing environment is validated.

| Need | Reference |
|---|---|
| What happened, why, and what was actually fixed | [Full findings](README.md) |
| Side-by-side numbers | [Verified results](evidence/verified-results.json) |
| What to do during a customer call | [Support context and 40-minute runbook](docs/SUPPORT-CONTEXT.md) |
| Every successful and failed run | [Evidence index](docs/EVIDENCE-INDEX.md) |
| What remains deployed in the original study | [Sanitized final-state snapshot](evidence/final-state.json) |
| Privacy boundaries and exclusions | [Publication notes](docs/PUBLICATION.md) |

## Read and validate without Azure access

Python's standard library is sufficient; no pip installation is needed. The original harness was tested with Python 3.14. These checks do not authenticate, deploy, invoke a model, or create certificate files:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s '.\tests' -v
python '.\tools\verify_reference.py'
az bicep build --file '.\infra\main.bicep' --stdout | Out-Null
```

The verifier checks all 740 historical JSON files against the [SHA-256 manifest](publication-manifest.json), validates the exact-route results, and checks for obvious credentials or unsanitized identifiers. It is not a full security scanner.

## Configure a new, isolated Azure lab

**Cloud commands below create billable resources or change lab policies.** They are examples, not commands run by cloning or testing this repository. Existing Azure CLI/Bicep and authorization to create resources and role assignments are required. New subscriptions need model quota and regional/model availability checks; catalog visibility alone is insufficient.

The repository contains aliases, not the original live names or IDs. Set your own values in the current PowerShell process. [.env.sample](.env.sample) documents the same settings; the harness does not automatically load dotenv files.

```powershell
$env:AZURE_SUBSCRIPTION_ID = '<your-subscription-guid>'
$env:LAB_RESOURCE_GROUP = '<your-isolated-lab-resource-group>'
$env:LAB_FOUNDRY_ACCOUNT = '<your-globally-unique-foundry-account>'
$env:LAB_PROJECT_NAME = '<your-foundry-project>'
$env:LAB_MODEL_DEPLOYMENT = 'lab-model'
$env:LAB_APIM_CLASSIC_NAME = '<your-globally-unique-classic-gateway>'
$env:LAB_APIM_V2_NAME = '<your-globally-unique-v2-gateway>'
$env:LAB_CALLER_IP = ''
```

Use a verified stable egress IP only if available. Empty `LAB_CALLER_IP` keeps operator-scoped Entra validation and APIM subscription authentication, but does not apply an IP allowlist.

Sign in to the target tenant using your organization's approved method. Do not export certificates or persist tokens. Determine the operator object ID from a **subscription-scoped ARM token**, not an unscoped home-tenant directory lookup. This prints only the object ID:

```powershell
$operatorObjectId = python -c "import lab; t=lab.cli_json('account','get-access-token','--resource','https://management.azure.com/'); print(lab.token_claims(t['accessToken'])['oid'])"
$publisherEmail = '<your-contact-email>'

$parameters = @(
  '.\infra\main.bicepparam'
  "operatorObjectId=$operatorObjectId"
  "publisherEmail=$publisherEmail"
  "foundryName=$env:LAB_FOUNDRY_ACCOUNT"
  "projectName=$env:LAB_PROJECT_NAME"
  "deploymentName=$env:LAB_MODEL_DEPLOYMENT"
  "classicGatewayName=$env:LAB_APIM_CLASSIC_NAME"
  "v2GatewayName=$env:LAB_APIM_V2_NAME"
  "callerIp=$env:LAB_CALLER_IP"
)

# Use an existing authorized isolated RG, or create a new one deliberately.
az group create --subscription $env:AZURE_SUBSCRIPTION_ID `
  --name $env:LAB_RESOURCE_GROUP --location 'eastus2'

az deployment group what-if --subscription $env:AZURE_SUBSCRIPTION_ID `
  --resource-group $env:LAB_RESOURCE_GROUP `
  --template-file '.\infra\main.bicep' --parameters $parameters

# Run only after inspecting the preview and approving the recurring costs.
az deployment group create --subscription $env:AZURE_SUBSCRIPTION_ID `
  --resource-group $env:LAB_RESOURCE_GROUP --name 'apim-token-repro' `
  --mode Incremental --template-file '.\infra\main.bicep' --parameters $parameters
```

The [main parameter file](infra/main.bicepparam) and [standalone Foundry parameter file](infra/modules/foundry.bicepparam) are **examples**. Their placeholder operator GUID must be overridden. Match names between Bicep and the harness; never paste the historical aliases and expect access to the original lab.

## Run bounded experiments

New results go to ignored `runs/`, not the published historical [evidence](evidence/) directory. No original study record is overwritten. The default 120-record safety ceiling applies to new runs in that checkout.

```powershell
python '.\lab.py' direct --gateway v2 --project-api project --run-id 'my-direct'
python '.\lab.py' run --gateway v2 --project-api project --run-id 'my-v2'
python '.\lab.py' run --gateway classic --project-api project --run-id 'my-classic'

# Focused rerun instead of unnecessarily repeating the baseline:
python '.\lab.py' run --gateway v2 --project-api project `
  --phases tpm mitigation --run-id 'my-v2-focused'
```

`--project-api project` is exact project v1 Responses versus project v1 Chat. `project-preview` deliberately uses the preview Responses route and account Chat controls. It is not a fallback. `--max-total-calls` raises the total new-run ceiling only when deliberately supplied.

The `backend` action temporarily changes the shared model deployment capacity. Do not run it concurrently with other tests. It restores capacity and token policies in `finally`, then waits for live backend headers to confirm restoration; propagation can take many minutes.

## What to check first

1. Confirm HTTP 200 with integer backend `usage.total_tokens` before interpreting consumed/remaining headers.
2. Check the returned `x-lab-phase` and trace to ensure the intended policy propagated.
3. Use low, fresh token counters: 220 hourly quota should eventually yield APIM 403; 300 TPM should yield APIM 429. Verify the rejecting component, not status alone.
4. A request-throttle 429 is mitigation, not proof that token accounting was repaired.
5. Keep raw customer traces in an approved support channel. Do not commit new live `runs/` output directly to this public repository.

## Cost and shutdown

The original study's retail estimate was **USD 6.51/day for both gateways**, plus model tokens and applicable extras. It is historical pricing, not a current quote or actual bill. There is no automatic expiry.

Delete only your explicitly identified lab gateways and Foundry account when finished. Deleting a Foundry account removes its model/project children. Do not delete an existing shared resource group or assume disabling an API stops APIM charges.
