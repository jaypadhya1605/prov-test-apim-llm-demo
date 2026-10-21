"""Offline integrity and publication checks; never contacts Azure or uploads content."""

import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
GUID = re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", re.I)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I)
MODEL_CORRELATION = re.compile(
    r"\b(?:resp_|msg_|rs_|chatcmpl-|cmpl-|conv_|call_)(?!example-)[A-Za-z0-9_-]{12,}"
)
CREDENTIAL = re.compile(
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    r"|(?i:Bearer\s+[A-Za-z0-9._~+/\-=]{20,})"
    r"|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
)
PUBLIC_UUIDS = {
    "11fb06fb-712d-4ddd-98c7-e71bbd588830",
    "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd",
    "53ca6127-db72-4b80-b1b0-d745d6d5456d",
}
DOCUMENTATION_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24",
))
SECRET_FIELDS = {
    "authorization", "proxy-authorization", "ocp-apim-subscription-key",
    "apim-debug-authorization", "api-key", "access_token", "accesstoken",
    "primarykey", "secondarykey", "subscriptionkey", "client_secret",
    "password", "refresh_token", "refreshtoken",
}
BLOCKED_SUFFIXES = {
    ".pem", ".key", ".crt", ".cer", ".der", ".pfx", ".p12", ".p7b", ".p7c",
    ".jks", ".keystore", ".ppk", ".asc", ".gpg", ".pgp", ".csr", ".kdbx", ".eml", ".msg",
}


def credential_fields_clean(value):
    if isinstance(value, dict):
        name = value.get("name", value.get("key", ""))
        secret_header = isinstance(name, str) and name.lower() in SECRET_FIELDS
        for key, child in value.items():
            protected = key.lower() in SECRET_FIELDS or (secret_header and key.lower() in ("value", "values"))
            if protected and isinstance(child, str) and not child.startswith("[REDACTED"):
                return False
            if not credential_fields_clean(child):
                return False
    elif isinstance(value, list):
        return all(credential_fields_clean(child) for child in value)
    return True


def verify(root=ROOT):
    issues = []
    manifest = json.loads((root / "publication-manifest.json").read_text(encoding="utf-8"))
    entries = manifest["files"]
    recorded = {entry["path"] for entry in entries}
    actual = {path.relative_to(root).as_posix() for path in (root / "evidence").rglob("*.json")}
    if actual != recorded or len(entries) != manifest["sourceEvidenceFiles"]:
        issues.append("The evidence file set differs from the publication manifest.")
    if sum(Path(name).name.startswith("call-") for name in actual) != manifest["sourceCallRecords"]:
        issues.append("The call-record count differs from the publication manifest.")
    for entry in entries:
        path = root / entry["path"]
        if not path.resolve().is_relative_to((root / "evidence").resolve()) or not path.is_file():
            issues.append("Invalid or missing manifest path: " + entry["path"])
            continue
        content = path.read_bytes()
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            issues.append("Evidence integrity mismatch: " + entry["path"])
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in {".git", "runs", "__pycache__", ".venv", "venv"} for part in relative.parts):
            continue
        if not path.is_file():
            continue
        name = path.name.lower()
        if path.suffix.lower() in BLOCKED_SUFFIXES or name.startswith((
            "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "known_hosts",
        )) or name == "authorized_keys" or name.endswith("_rsa"):
            issues.append("Private or blocked file type: " + relative.as_posix())
            continue
        if path.name in {".env", ".gitignore"} or path.suffix == ".pyc":
            continue
        text = path.read_text(encoding="utf-8")
        reasons = []
        if CREDENTIAL.search(text):
            reasons.append("credential-like token")
        if MODEL_CORRELATION.search(text):
            reasons.append("non-pseudonymous model correlation identifier")
        for match in GUID.finditer(text):
            value = uuid.UUID(match.group())
            if str(value) not in PUBLIC_UUIDS and value.int > 4 and value.version != 5:
                reasons.append("non-pseudonymous GUID")
                break
        for match in IPV4.finditer(text):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            if not address.is_loopback and not address.is_unspecified and not any(
                address in network for network in DOCUMENTATION_NETWORKS
            ):
                reasons.append("non-documentation IP address")
                break
        if any(not match.group().lower().endswith("@example.com") for match in EMAIL.finditer(text)):
            reasons.append("non-example email address")
        if path.suffix == ".json":
            data = json.loads(text)
            if not credential_fields_clean(data):
                reasons.append("unredacted credential field")
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://", "#", "mailto:")):
                    continue
                target = target.split("#", 1)[0]
                if target and not path.parent.joinpath(*target.split("/")).exists():
                    reasons.append("missing relative documentation link")
                    break
        if reasons:
            issues.append(relative.as_posix() + ": " + ", ".join(reasons))
    for run in ("v1-v2-measured", "v1-classic-measured"):
        summary = json.loads((root / "evidence" / run / "summary.json").read_text(encoding="utf-8"))
        if summary["projectApi"] != "project" or summary["chatApi"] != "project":
            issues.append(run + ": comparison is not exact project v1 versus project v1.")
        for name, result in summary["results"].items():
            if not result["rejectionObserved"]:
                issues.append(run + ": expected rejection is missing in " + name)
        if not summary["results"]["request-mitigation"]["chatUnaffected"]:
            issues.append(run + ": mitigation affected the Chat control.")
        for call in summary["calls"]:
            if call["phase"].startswith("baseline") and (
                call["response"]["status"] != 200
                or call["actualTotalTokens"] != 167
                or call["response"]["headers"].get("x-lab-consumed") != "167"
            ):
                issues.append(run + ": baseline actual/consumed usage differs from the verified study.")
            if call["phase"] in ("quota", "tpm", "request-mitigation") and call["response"]["status"] in (403, 429):
                policy = "rate-limit-by-key" if call["phase"] == "request-mitigation" else "llm-token-limit"
                if policy not in call.get("traceSources", []) or call.get("backendStatuses") != []:
                    issues.append(run + ": rejection is not trace-confirmed as gateway-origin.")
    return issues, {
        "evidenceFiles": len(actual),
        "callRecords": manifest["sourceCallRecords"],
        "integrityAndPublicationChecksPassed": not issues,
    }


def main():
    issues, summary = verify()
    for issue in issues:
        print(issue, file=sys.stderr)
    print(json.dumps(summary, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
