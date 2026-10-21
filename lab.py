"""Bounded, synthetic APIM/Foundry experiments; Azure credentials stay in memory."""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
EVIDENCE_ROOT = ROOT / "runs"
REQUIRED_ENVIRONMENT = (
    "AZURE_SUBSCRIPTION_ID", "LAB_RESOURCE_GROUP", "LAB_FOUNDRY_ACCOUNT",
    "LAB_PROJECT_NAME", "LAB_MODEL_DEPLOYMENT", "LAB_APIM_CLASSIC_NAME", "LAB_APIM_V2_NAME",
)
SUBSCRIPTION = os.environ.get("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000001")
GROUP = os.environ.get("LAB_RESOURCE_GROUP", "rg-apim-token-lab")
SCOPE = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{GROUP}"
ACCOUNT = os.environ.get("LAB_FOUNDRY_ACCOUNT", "ai-token-lab-example")
PROJECT = os.environ.get("LAB_PROJECT_NAME", "project-token-lab")
MODEL = os.environ.get("LAB_MODEL_DEPLOYMENT", "lab-model")
CALLER_IP = os.environ.get("LAB_CALLER_IP", "")
GATEWAYS = {
    "classic": os.environ.get("LAB_APIM_CLASSIC_NAME", "apim-lab-classic-example"),
    "v2": os.environ.get("LAB_APIM_V2_NAME", "apim-lab-v2-example"),
}
APIM_VERSION = "2024-05-01"
PROJECT_URL = f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}/openai/v1"
ACCOUNT_URL = f"https://{ACCOUNT}.openai.azure.com/openai/v1"
API_BASES = {
    "project": PROJECT_URL,
    "project-preview": PROJECT_URL.removesuffix("/v1"),
    "account": ACCOUNT_URL,
}
PROMPT = (
    "For a synthetic gateway test, write a numbered list of thirty ordinary household "
    "objects, each followed by a short sentence about its everyday use. "
    "Do not discuss private information."
)
SECRET_NAMES = {
    "authorization", "proxy-authorization", "ocp-apim-subscription-key",
    "apim-debug-authorization", "api-key", "access_token", "accesstoken",
    "primarykey", "secondarykey", "subscriptionkey", "client_secret",
}
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/\-=]+")
SECRET_VALUES = set()


class LabError(RuntimeError):
    pass


def sanitize(value):
    if isinstance(value, dict):
        header_name = value.get("name", value.get("key", ""))
        secret_header = isinstance(header_name, str) and header_name.lower() in SECRET_NAMES
        return {
            key: "[REDACTED]"
            if key.lower() in SECRET_NAMES or (secret_header and key.lower() in ("value", "values"))
            else sanitize(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    if isinstance(value, str):
        for secret in SECRET_VALUES:
            value = value.replace(secret, "[REDACTED]")
        return JWT.sub("[REDACTED-JWT]", BEARER.sub("Bearer [REDACTED]", value))
    return value


def save_json(path, value):
    if path.suffix != ".json" or ROOT not in path.resolve().parents:
        raise LabError("Evidence must be a JSON file inside the lab workspace.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize(value), indent=2) + "\n", encoding="utf-8")


def utc():
    return datetime.now(timezone.utc).isoformat()


def bicep_guid(*parts):
    return str(uuid.uuid5(uuid.UUID("11fb06fb-712d-4ddd-98c7-e71bbd588830"), "-".join(parts)))


def token_claims(token):
    encoded = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))


def cli_json(*args):
    executable = shutil.which("az")
    if executable is None:
        raise LabError("Azure CLI is not installed.")
    result = subprocess.run(
        [executable, *args, "--subscription", SUBSCRIPTION, "--output", "json"],
        capture_output=True, text=True, check=False,
        env={**os.environ, "AZURE_EXTENSION_USE_DYNAMIC_INSTALL": "no"},
    )
    if result.returncode:
        raise LabError(f"Azure CLI failed: {sanitize(result.stderr.strip())}")
    return json.loads(result.stdout)


def http(method, url, headers=None, body=None, timeout=90):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = dict(headers or {})
    if data is not None:
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read().decode("utf-8-sig")
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        if raw and "json" in response_headers.get("content-type", ""):
            content = json.loads(raw)
        else:
            content = raw
        return {
            "status": response.status,
            "headers": response_headers,
            "body": content,
        }


def usage_total(body):
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None
    total = usage.get("total_tokens")
    return total if isinstance(total, int) else None


def trace_backend_statuses(trace):
    statuses = []
    for entry in trace.get("traceEntries", {}).get("backend", []):
        data = entry.get("data")
        if not isinstance(data, dict):
            continue
        response = data.get("response")
        if not isinstance(response, dict):
            continue
        status = response.get("status")
        code = status.get("code") if isinstance(status, dict) else status
        if isinstance(code, int):
            statuses.append(code)
    return statuses


def payload(operation):
    common = {"model": MODEL, "stream": False}
    if operation == "responses":
        return {
            **common, "input": PROMPT, "max_output_tokens": 128,
            "store": False, "reasoning": {"effort": "minimal"},
        }
    return {
        **common, "messages": [{"role": "user", "content": PROMPT}],
        "max_completion_tokens": 128, "reasoning_effort": "minimal",
    }


def schema():
    usage = {
        "type": "object",
        "properties": {
            key: {"type": "integer"}
            for key in (
                "input_tokens", "output_tokens", "prompt_tokens",
                "completion_tokens", "total_tokens",
            )
        },
    }
    paths = {}
    for operation, path in (("responses", "/responses"), ("chat", "/chat/completions")):
        fields = {
            "model": {"type": "string"}, "stream": {"type": "boolean"},
            "max_output_tokens": {"type": "integer"},
            "max_completion_tokens": {"type": "integer"},
        }
        if operation == "responses":
            fields["input"] = {"type": "string"}
        else:
            fields["messages"] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"}, "content": {"type": "string"},
                    },
                },
            }
        paths[path] = {
            "post": {
                "operationId": operation,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": fields},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Successful model response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object", "properties": {"usage": usage},
                                },
                            },
                        },
                    },
                },
            },
        }
    return {"openapi": "3.0.3", "info": {"title": "Synthetic LLM lab", "version": "1.0"}, "paths": paths}


def operation_policy(run_id, phase, estimate=True, tpm=10000, quota=10000, calls=None):
    key = (
        f'@("{run_id}:{phase}:" + context.Api.Id + ":" + '
        'context.Operation.Id + ":" + context.Subscription.Id)'
    )
    if calls is None:
        limit = {
            "counter-key": key, "estimate-prompt-tokens": str(estimate).lower(),
            "tokens-consumed-header-name": "x-lab-consumed",
        }
        if tpm is not None:
            limit["tokens-per-minute"] = str(tpm)
            limit["remaining-tokens-header-name"] = "x-lab-tpm"
        if quota is not None:
            limit["token-quota"] = str(quota)
            limit["token-quota-period"] = "Hourly"
            limit["remaining-quota-tokens-header-name"] = "x-lab-quota"
        element = ET.Element("llm-token-limit", limit)
    else:
        element = ET.Element("rate-limit-by-key", {
            "counter-key": key, "calls": str(calls), "renewal-period": "60",
            "remaining-calls-header-name": "x-lab-calls",
        })
    policy = ET.Element("policies")
    inbound = ET.SubElement(policy, "inbound")
    ET.SubElement(inbound, "base")
    choose = ET.SubElement(inbound, "choose")
    probe = ET.SubElement(choose, "when", {
        "condition": '@(context.Request.Headers.GetValueOrDefault("x-lab-probe", "") == "true")',
    })
    response = ET.SubElement(probe, "return-response")
    ET.SubElement(response, "set-status", {"code": "204", "reason": "Policy ready"})
    header = ET.SubElement(response, "set-header", {"name": "x-lab-phase", "exists-action": "override"})
    ET.SubElement(header, "value").text = phase
    inbound.append(element)
    backend = ET.SubElement(policy, "backend")
    ET.SubElement(backend, "base")
    outbound = ET.SubElement(policy, "outbound")
    ET.SubElement(outbound, "base")
    header = ET.SubElement(outbound, "set-header", {"name": "x-lab-phase", "exists-action": "override"})
    ET.SubElement(header, "value").text = phase
    on_error = ET.SubElement(policy, "on-error")
    ET.SubElement(on_error, "base")
    return ET.tostring(policy, encoding="unicode")


class Lab:
    def __init__(self, gateway, run_id=None, project_api="project", max_total_calls=120):
        if max_total_calls < 1:
            raise LabError("The explicit total-call safety ceiling must be positive.")
        self.gateway = GATEWAYS[gateway]
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + gateway
        if not re.fullmatch(r"[A-Za-z0-9-]+", self.run_id):
            raise LabError("Run ID must contain only letters, digits, or hyphens.")
        self.directory = EVIDENCE_ROOT / self.run_id
        self.tokens = {}
        self.debug_tokens = {}
        self.subscription_key = None
        self.records = []
        self.project_api = project_api
        self.max_total_calls = max_total_calls
        self.service_path = f"{SCOPE}/providers/Microsoft.ApiManagement/service/{self.gateway}"
        self.url = f"https://{self.gateway}.azure-api.net"

    def token(self, resource):
        cached = self.tokens.get(resource)
        if cached is None or time.time() + 300 > int(cached["expires_on"]):
            cached = cli_json("account", "get-access-token", "--resource", resource)
            self.tokens[resource] = cached
            SECRET_VALUES.add(cached["accessToken"])
        return cached["accessToken"]

    def arm(self, method, path, body=None, version=APIM_VERSION, allow_not_found=False):
        if not path.startswith(SCOPE + "/"):
            raise LabError("Management operations are restricted to the authorized resource group.")
        separator = "&" if "?" in path else "?"
        url = f"https://management.azure.com{path}{separator}api-version={version}"
        result = http(
            method, url, {
                "Authorization": "Bearer " + self.token("https://management.azure.com/"),
                "Accept": "application/json",
            },
            body,
        )
        if allow_not_found and result["status"] == 404:
            return None
        if result["status"] not in (200, 201, 202, 204):
            raise LabError(f"ARM {method} {path}: {result['status']} {sanitize(result['body'])}")
        return result["body"]

    def wait_ready(self, seconds=2700):
        deadline = time.monotonic() + seconds
        previous = None
        account_path = f"{SCOPE}/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT}"
        while time.monotonic() < deadline:
            service = self.arm("GET", self.service_path, allow_not_found=True)
            model = self.arm(
                "GET", account_path + f"/deployments/{MODEL}",
                version="2025-06-01", allow_not_found=True,
            )
            project = self.arm(
                "GET", account_path + f"/projects/{PROJECT}",
                version="2025-06-01", allow_not_found=True,
            )
            states = (
                service["properties"]["provisioningState"] if service else "NotCreated",
                model["properties"]["provisioningState"] if model else "NotCreated",
                project["properties"]["provisioningState"] if project else "NotCreated",
            )
            if states != previous:
                print(f"{utc()} gateway/model readiness: {states}", flush=True)
                previous = states
            if any(state in ("Failed", "Canceled") for state in states):
                raise LabError(f"Resource provisioning failed: {states}")
            if states == ("Succeeded", "Succeeded", "Succeeded"):
                save_json(self.directory / "resources.json", {"gateway": service, "model": model, "project": project})
                return
            time.sleep(20)
        raise LabError("Timed out waiting for the gateway and model to finish provisioning.")

    def configure(self):
        claims = token_claims(self.token("https://management.azure.com/"))
        tenant, operator = claims["tid"], claims["oid"]
        security = (
            '<policies><inbound>'
            + (f'<ip-filter action="allow"><address>{CALLER_IP}</address></ip-filter>' if CALLER_IP else "") +
            f'<validate-azure-ad-token tenant-id="{tenant}" output-token-variable-name="lab-caller">'
            '<audiences><audience>https://cognitiveservices.azure.com</audience></audiences>'
            f'<required-claims><claim name="oid" match="all"><value>{operator}</value></claim></required-claims>'
            '</validate-azure-ad-token></inbound><backend><forward-request /></backend>'
            '<outbound /><on-error /></policies>'
        )
        self.arm("PUT", self.service_path + "/policies/policy", {
            "properties": {"format": "rawxml", "value": security},
        })
        service = self.arm("GET", self.service_path)
        principal = service["identity"]["principalId"]
        account = f"{SCOPE}/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT}"
        for scope, role, suffix in (
            (account, "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd", "openai-user"),
            (account + f"/projects/{PROJECT}", "53ca6127-db72-4b80-b1b0-d745d6d5456d", "foundry-user"),
        ):
            role_name = bicep_guid(scope, self.gateway, suffix)
            self.arm(
                "PUT", scope + "/providers/Microsoft.Authorization/roleAssignments/" + role_name,
                {"properties": {
                    "roleDefinitionId": f"/subscriptions/{SUBSCRIPTION}/providers/Microsoft.Authorization/roleDefinitions/{role}",
                    "principalId": principal, "principalType": "ServicePrincipal",
                }},
                version="2022-04-01",
            )
        secrets = self.arm("POST", self.service_path + "/subscriptions/repro/listSecrets", {})
        self.subscription_key = secrets["primaryKey"]
        SECRET_VALUES.update((secrets["primaryKey"], secrets["secondaryKey"]))
        for api, base in API_BASES.items():
            api_path = self.service_path + "/apis/lab-" + api
            self.arm("PUT", api_path, {
                "properties": {
                    "displayName": f"Synthetic {api} model routes",
                    "path": "lab-" + api, "protocols": ["https"],
                    "subscriptionRequired": True, "serviceUrl": base,
                    "format": "openapi+json", "value": json.dumps(schema()),
                    "apiType": "http",
                },
            })
            resource = "https://ai.azure.com" if api.startswith("project") else "https://cognitiveservices.azure.com"
            query = (
                '<set-query-parameter name="api-version" exists-action="override">'
                '<value>2025-11-15-preview</value></set-query-parameter>'
                if api == "project-preview" else ""
            )
            policy = (
                '<policies><inbound><base />'
                f'<authentication-managed-identity resource="{resource}" />'
                + query +
                '</inbound><backend><base /></backend><outbound><base />'
                '<trace source="lab-backend-body" severity="information">'
                '<message>@(context.Response.Body.As&lt;string&gt;(preserveContent: true))</message>'
                '</trace></outbound><on-error><base /></on-error></policies>'
            )
            self.arm("PUT", api_path + "/policies/policy", {
                "properties": {"format": "rawxml", "value": policy},
            })
            debug = self.arm("POST", self.service_path + "/gateways/managed/listDebugCredentials", {
                "apiId": api_path, "purposes": ["tracing"], "credentialsExpireAfter": "PT1H",
            })
            self.debug_tokens[api] = debug["token"]
            SECRET_VALUES.add(debug["token"])
            for operation in ("responses", "chat"):
                self.set_policy(api, operation, "safe")
        save_json(self.directory / "openapi.json", schema())
        for api in API_BASES:
            for operation in ("responses", "chat"):
                self.wait_phase(api, operation, "safe")

    def set_policy(self, api, operation, phase, **kwargs):
        value = operation_policy(self.run_id, phase, **kwargs)
        path = self.service_path + f"/apis/lab-{api}/operations/{operation}/policies/policy"
        self.arm("PUT", path, {"properties": {"format": "rawxml", "value": value}})
        save_json(self.directory / f"policy-{api}-{operation}-{phase}.json", {
            "resource": path, "phase": phase, "xml": value,
        })

    def wait_phase(self, api, operation, phase, seconds=180):
        path = "/responses" if operation == "responses" else "/chat/completions"
        deadline = time.monotonic() + seconds
        attempts = []
        while time.monotonic() < deadline:
            result = http("POST", self.url + "/lab-" + api + path, {
                "Authorization": "Bearer " + self.token("https://cognitiveservices.azure.com"),
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "x-lab-probe": "true",
            }, {}, timeout=30)
            attempts.append({"utc": utc(), "response": result})
            current = result["headers"].get("x-lab-phase")
            if result["status"] == 204 and current == phase:
                save_json(self.directory / f"probe-{api}-{operation}-{phase}.json", attempts)
                return
            if result["status"] == 401:
                raise LabError(f"Policy probe was denied authentication: {api}/{operation}.")
            time.sleep(3)
        save_json(self.directory / f"probe-{api}-{operation}-{phase}.json", attempts)
        raise LabError(f"Gateway did not expose policy phase {phase} on {api}/{operation} within {seconds}s.")

    def get_trace(self, trace_id, seconds=45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            trace = self.arm(
                "POST", self.service_path + "/gateways/managed/listTrace",
                {"traceId": trace_id}, allow_not_found=True,
            )
            if trace is not None:
                return trace
            time.sleep(3)
        raise LabError(f"APIM trace {trace_id} was still unavailable after {seconds}s.")

    def call(self, api, operation, phase, direct=False, authenticated=True, request_body=None):
        count = sum(1 for _ in EVIDENCE_ROOT.rglob("call-*.json"))
        if count >= self.max_total_calls:
            raise LabError(f"The lab-wide {self.max_total_calls}-request safety ceiling has been reached.")
        path = "/responses" if operation == "responses" else "/chat/completions"
        resource = "https://ai.azure.com" if api.startswith("project") else "https://cognitiveservices.azure.com"
        headers = {"x-ms-client-request-id": str(uuid.uuid4())}
        if direct:
            url = API_BASES[api] + path
            if api == "project-preview":
                url += "?api-version=2025-11-15-preview"
        else:
            url = self.url + "/lab-" + api + path
            headers["Ocp-Apim-Subscription-Key"] = self.subscription_key
            headers["Apim-Debug-Authorization"] = self.debug_tokens[api]
            resource = "https://cognitiveservices.azure.com"
        if authenticated:
            headers["Authorization"] = "Bearer " + self.token(resource)
        request_body = payload(operation) if request_body is None else request_body
        started = utc()
        clock = time.monotonic()
        result = http("POST", url, headers, request_body)
        record = {
            "utc": started, "elapsedSeconds": round(time.monotonic() - clock, 3),
            "api": api, "operation": operation, "phase": phase, "direct": direct,
            "requestId": headers["x-ms-client-request-id"], "url": url,
            "requestBody": request_body, "response": result,
            "actualTotalTokens": usage_total(result["body"]),
        }
        filename = f"call-{count + 1:03d}-{api}-{operation}-{phase}.json"
        save_json(self.directory / filename, record)
        trace_id = result["headers"].get("apim-trace-id")
        if trace_id:
            trace = self.get_trace(trace_id)
            save_json(self.directory / filename.replace("call-", "trace-"), trace)
            record["backendStatuses"] = trace_backend_statuses(trace)
            record["traceSources"] = sorted({
                entry["source"]
                for entries in trace.get("traceEntries", {}).values()
                for entry in entries if "source" in entry
            })
            save_json(self.directory / filename, record)
        elif not direct:
            record["traceMissing"] = True
            save_json(self.directory / filename, record)
        self.records.append(record)
        selected = {
            key: value for key, value in result["headers"].items()
            if key.startswith("x-lab-") or key == "retry-after"
        }
        print(json.dumps({
            "phase": phase, "route": f"{api}/{operation}", "status": result["status"],
            "actualTokens": record["actualTotalTokens"], "headers": selected,
            "elapsedSeconds": record["elapsedSeconds"],
        }), flush=True)
        return record

    def require_success(self, record, phase=None):
        if record["response"]["status"] != 200:
            raise LabError(f"Model request failed: {sanitize(record['response'])}")
        if record["actualTotalTokens"] is None:
            raise LabError("Successful response has no integer usage.total_tokens; inspect the saved evidence.")
        if phase is not None and record["response"]["headers"].get("x-lab-phase") != phase:
            raise LabError("Policy phase did not match; propagation or an unexpected policy must be investigated.")

    def require_rejection(self, record, status, policy):
        if (
            record["response"]["status"] != status
            or policy not in record.get("traceSources", [])
            or record.get("backendStatuses") != []
        ):
            raise LabError(f"Expected a trace-confirmed {policy} HTTP {status}, not an authentication or backend error.")

    def comparison_routes(self):
        chat_api = "project" if self.project_api == "project" else "account"
        return ((self.project_api, "responses"), (chat_api, "chat"), ("account", "responses"))

    def wait_backend_capacity(self, capacity, seconds=1800):
        deadline = time.monotonic() + seconds
        matches = 0
        observations = []
        request_body = {**payload("responses"), "input": "Reply OK.", "max_output_tokens": 16}
        while time.monotonic() < deadline:
            record = self.call("project", "responses", "capacity-restoration",
                               direct=True, request_body=request_body)
            observations.append(record)
            result = record["response"]
            if result["status"] not in (200, 429):
                raise LabError(f"Unexpected backend response while verifying restored capacity: {sanitize(result)}")
            headers = result["headers"]
            matches = matches + 1 if (
                result["status"] == 200
                and record["actualTotalTokens"] is not None
                and headers.get("x-ratelimit-limit-requests") == str(capacity)
                and headers.get("x-ratelimit-limit-tokens") == str(capacity * 1000)
            ) else 0
            if matches >= 3:
                save_json(self.directory / "runtime-restoration.json", {
                    "verifiedCapacity": capacity, "consecutiveMatchingResponses": matches,
                    "observations": observations,
                })
                return
            time.sleep(30)
        save_json(self.directory / "runtime-restoration.json", {
            "verifiedCapacity": None, "expectedCapacity": capacity, "observations": observations,
        })
        raise LabError(f"Backend headers did not confirm restored capacity {capacity} within {seconds}s.")

    def direct(self):
        failures = []
        routes = self.comparison_routes()
        extra_chat = "account" if self.project_api == "project" else "project"
        for api, operation in (*routes, (extra_chat, "chat")):
            record = self.call(api, operation, "direct", direct=True)
            if (api, operation) in routes[:2]:
                if record["response"]["status"] != 200 or record["actualTotalTokens"] is None:
                    failures.append(f"{api}/{operation}: HTTP {record['response']['status']}")
        save_json(self.directory / "summary.json", {"kind": "direct-endpoint-validation", "calls": self.records})
        if failures:
            raise LabError("Primary direct validation failed: " + "; ".join(failures))

    def suite(self, phases=("baseline", "quota", "tpm", "mitigation")):
        routes = self.comparison_routes()
        chat_api = routes[1][0]
        self.configure()
        results = {}
        try:
            unauthenticated = self.call(chat_api, "chat", "unauthenticated", authenticated=False)
            if unauthenticated["response"]["status"] not in (401, 403):
                raise LabError("The gateway did not reject a caller without Entra authentication.")
            for estimate in ((True, False) if "baseline" in phases else ()):
                phase = "baseline-estimate-" + str(estimate).lower()
                for api, operation in routes:
                    self.set_policy(api, operation, phase, estimate=estimate)
                for api, operation in routes:
                    self.wait_phase(api, operation, phase)
                for api, operation in routes:
                    for _ in range(3):
                        self.require_success(self.call(api, operation, phase), phase)
            for phase, settings, expected_status in (
                ("quota", {"tpm": 10000, "quota": 220}, 403),
                ("tpm", {"tpm": 300, "quota": None}, 429),
            ):
                if phase not in phases:
                    continue
                for api, operation in routes[:2]:
                    self.set_policy(api, operation, phase, **settings)
                for api, operation in routes[:2]:
                    self.wait_phase(api, operation, phase)
                for api, operation in routes[:2]:
                    calls = []
                    for _ in range(5):
                        record = self.call(api, operation, phase)
                        calls.append(record)
                        status = record["response"]["status"]
                        if status == expected_status:
                            self.require_rejection(record, expected_status, "llm-token-limit")
                            break
                        self.require_success(record, phase)
                    results[f"{phase}-{api}-{operation}"] = {
                        "expectedRejection": expected_status,
                        "statuses": [call["response"]["status"] for call in calls],
                        "completedActualTokens": sum(
                            call["actualTotalTokens"] for call in calls
                            if call["actualTotalTokens"] is not None
                        ),
                        "rejectionObserved": calls[-1]["response"]["status"] == expected_status,
                    }
            if "mitigation" in phases:
                self.set_policy(chat_api, "chat", "chat-control")
                self.set_policy(self.project_api, "responses", "request-mitigation", calls=3)
                self.wait_phase(chat_api, "chat", "chat-control")
                self.wait_phase(self.project_api, "responses", "request-mitigation")
                mitigation = []
                for _ in range(5):
                    record = self.call(self.project_api, "responses", "request-mitigation")
                    mitigation.append(record["response"]["status"])
                    if record["response"]["status"] == 429:
                        self.require_rejection(record, 429, "rate-limit-by-key")
                        break
                    self.require_success(record, "request-mitigation")
                control = self.call(chat_api, "chat", "chat-control")
                self.require_success(control, "chat-control")
                results["request-mitigation"] = {
                    "statuses": mitigation, "rejectionObserved": mitigation[-1] == 429,
                    "chatUnaffected": control["response"]["status"] == 200,
                    "isTokenAccountingFix": False,
                }
        finally:
            for api, operation in routes:
                self.set_policy(api, operation, "safe-final")
            if ("project", "chat") not in routes:
                self.set_policy("project", "chat", "safe-final")
            for api, operation in routes:
                self.wait_phase(api, operation, "safe-final")
            save_json(self.directory / "summary.json", {
                "gateway": self.gateway, "runId": self.run_id,
                "projectApi": self.project_api, "chatApi": chat_api, "phases": list(phases),
                "results": results, "calls": self.records,
                "finalPolicy": "Token accounting enabled with 10000 TPM and hourly token quota.",
            })
        print(json.dumps(results, indent=2), flush=True)

    def backend(self):
        self.configure()
        path = f"{SCOPE}/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT}/deployments/{MODEL}"
        original = self.arm("GET", path, version="2025-06-01")
        properties = original["properties"]
        restore = {
            "sku": {"name": original["sku"]["name"], "capacity": original["sku"]["capacity"]},
            "properties": {
                "model": {key: properties["model"][key] for key in ("format", "name", "version")},
                "versionUpgradeOption": properties["versionUpgradeOption"],
                "raiPolicyName": properties["raiPolicyName"],
            },
        }
        save_json(self.directory / "model-before.json", original)
        phase = "native-backend-limit"
        routes = ((self.project_api, "responses"), ("account", "responses"))
        for api, operation in routes:
            self.set_policy(api, operation, phase, calls=1000)
            self.wait_phase(api, operation, phase)
        records = []
        try:
            self.arm("PUT", path, {
                **restore, "sku": {"name": original["sku"]["name"], "capacity": 1},
            }, version="2025-06-01")
            self.wait_ready(seconds=300)
            reduced = self.arm("GET", path, version="2025-06-01")
            save_json(self.directory / "model-reduced.json", reduced)
            limits = {
                item["key"]: item["count"]
                for item in reduced["properties"].get("rateLimits", [])
                if item.get("renewalPeriod") == 60
            }
            if reduced["sku"]["capacity"] != 1 or limits != {"request": 1, "token": 1000}:
                raise LabError(f"The native experiment requires verified 1 RPM/1000 TPM limits, received {limits}.")
            time.sleep(65)
            request_body = {
                **payload("responses"),
                "input": "synthetic " * 2000 + "Reply with one short confirmation.",
                "max_output_tokens": 16,
            }
            rejected = {}
            for api, operation in routes:
                rejected[api] = False
                for _ in range(2):
                    record = self.call(api, operation, phase, request_body=request_body)
                    records.append(record)
                    if record["response"]["status"] == 429:
                        if 429 not in record.get("backendStatuses", []):
                            raise LabError("The 429 was not confirmed in the backend response trace.")
                        rejected[api] = True
                        break
                    self.require_success(record, phase)
            if not all(rejected.values()):
                raise LabError(f"Backend throttling was not observed on every tested route: {rejected}.")
        finally:
            self.arm("PUT", path, restore, version="2025-06-01")
            self.wait_ready(seconds=300)
            restored = self.arm("GET", path, version="2025-06-01")
            if restored["sku"]["capacity"] != original["sku"]["capacity"]:
                raise LabError("The backend capacity was not restored.")
            save_json(self.directory / "model-restored.json", restored)
            for api, operation in routes:
                self.set_policy(api, operation, "safe-final")
                self.wait_phase(api, operation, "safe-final")
            self.wait_backend_capacity(original["sku"]["capacity"])
            save_json(self.directory / "summary.json", {
                "kind": "native-deployment-protection", "calls": records,
                "restoredCapacity": restored["sku"]["capacity"],
                "proves": "Deployment rate protection, not per-project hourly quota or a token-accounting fix.",
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("direct", "run", "configure", "wait", "backend"))
    parser.add_argument("--gateway", choices=tuple(GATEWAYS), default="v2")
    parser.add_argument("--run-id")
    parser.add_argument("--project-api", choices=("project", "project-preview"), default="project")
    parser.add_argument("--phases", nargs="+", choices=("baseline", "quota", "tpm", "mitigation"),
                        default=("baseline", "quota", "tpm", "mitigation"))
    parser.add_argument("--max-total-calls", type=int, default=120,
                        help="Explicit workspace-wide persisted-call ceiling; raise deliberately for another bounded batch.")
    args = parser.parse_args()
    if args.max_total_calls < 1:
        parser.error("--max-total-calls must be positive")
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.environ.get(name)]
    if missing:
        parser.error("Set the lab environment before making Azure calls: " + ", ".join(missing))
    try:
        subscription = uuid.UUID(SUBSCRIPTION)
    except ValueError:
        parser.error("AZURE_SUBSCRIPTION_ID must be your real subscription GUID, not a placeholder.")
    if subscription.int <= 4:
        parser.error("AZURE_SUBSCRIPTION_ID must not be a public example identifier.")
    lab = Lab(args.gateway, args.run_id, args.project_api, args.max_total_calls)
    try:
        if args.action == "direct":
            lab.direct()
        else:
            lab.wait_ready()
            if args.action == "run":
                lab.suite(args.phases)
            elif args.action == "backend":
                lab.backend()
            elif args.action == "configure":
                lab.configure()
    except (LabError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        save_json(lab.directory / "failure.json", {"utc": utc(), "error": str(error)})
        print(f"ERROR: {sanitize(str(error))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
