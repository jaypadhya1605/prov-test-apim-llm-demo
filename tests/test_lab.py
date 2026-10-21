import io
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

import lab


class LabTests(unittest.TestCase):
    def test_http_accepts_management_json_with_utf8_bom(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {"Content-Type": "application/json"}
        response.read.return_value = b'\xef\xbb\xbf{"properties": {"value": "<policies />"}}'
        with patch.object(lab.urllib.request, "urlopen", return_value=response):
            result = lab.http("GET", "https://management.azure.com/example")
        self.assertEqual(result["body"]["properties"]["value"], "<policies />")

    def test_call_ceiling_requires_positive_explicit_value(self):
        self.assertEqual(lab.Lab("v2", "unit-test").max_total_calls, 120)
        self.assertEqual(lab.Lab("v2", "unit-test", max_total_calls=180).max_total_calls, 180)
        with self.assertRaises(lab.LabError):
            lab.Lab("v2", "unit-test", max_total_calls=0)

    def test_exact_project_comparison_uses_project_chat(self):
        instance = lab.Lab("v2", "unit-test", project_api="project")
        self.assertEqual(instance.comparison_routes()[:2], (("project", "responses"), ("project", "chat")))
        preview = lab.Lab("v2", "unit-test", project_api="project-preview")
        self.assertEqual(preview.comparison_routes()[1], ("account", "chat"))

    def test_runtime_restoration_requires_three_matching_backend_samples(self):
        instance = lab.Lab("v2", "unit-test")
        def record(capacity):
            return {"actualTotalTokens": 20, "response": {"status": 200, "headers": {
                "x-ratelimit-limit-requests": str(capacity),
                "x-ratelimit-limit-tokens": str(capacity * 1000),
            }}}
        with patch.object(instance, "call", side_effect=[record(n) for n in (100, 1, 100, 100, 100)]) as call, \
                patch.object(lab.time, "sleep"), patch.object(lab, "save_json"):
            instance.wait_backend_capacity(100)
        self.assertEqual(call.call_count, 5)

    def test_custom_synthetic_payload_is_sent_and_recorded_without_substitution(self):
        instance = lab.Lab("v2", "unit-test")
        request = {**lab.payload("responses"), "input": "synthetic " * 20}
        reply = {"status": 200, "headers": {}, "body": {"usage": {"total_tokens": 50}}}
        with patch.object(lab.Path, "rglob", return_value=iter(())), \
                patch.object(instance, "token", return_value="sample-value"), \
                patch.object(lab, "http", return_value=reply) as http, \
                patch.object(lab, "save_json"), patch("builtins.print"):
            record = instance.call("project-preview", "responses", "native", direct=True, request_body=request)
        self.assertEqual(http.call_args.args[3], request)
        self.assertEqual(record["requestBody"], request)

    def test_role_guid_matches_arm_bicep(self):
        self.assertEqual(
            lab.bicep_guid("scope", "principal", "role"),
            "0f761181-d230-57d6-9a09-8d94e57723e2",
        )

    def test_redacts_headers_and_keeps_usage(self):
        value = {
            "Authorization": "Bearer example",
            "headers": [{"name": "Ocp-Apim-Subscription-Key", "value": "example"}],
            "usage": {"input_tokens": 10, "total_tokens": 20},
            "message": "Token Bearer example",
        }
        clean = lab.sanitize(value)
        self.assertEqual(clean["Authorization"], "[REDACTED]")
        self.assertEqual(clean["headers"][0]["value"], "[REDACTED]")
        self.assertEqual(clean["usage"]["total_tokens"], 20)
        self.assertNotIn("example", clean["message"])

    def test_redacts_embedded_jwt(self):
        token = ".".join(("eyJhbGciOiJub25lIn0", "eyJzdWIiOiJ1bml0LXRlc3QifQ", "not-a-signature"))
        self.assertEqual(lab.sanitize("value=" + token), "value=[REDACTED-JWT]")

    def test_new_runs_do_not_overwrite_published_evidence(self):
        instance = lab.Lab("v2", "unit-test")
        self.assertEqual(instance.directory, lab.ROOT / "runs" / "unit-test")
        self.assertNotIn(lab.ROOT / "evidence", instance.directory.parents)

    def test_missing_configuration_exits_before_any_azure_call(self):
        with patch.dict(lab.os.environ, {}, clear=True), \
                patch.object(lab.sys, "argv", ["lab.py", "configure"]), \
                patch.object(lab, "cli_json") as cli, \
                patch.object(lab.sys, "stderr", new_callable=io.StringIO) as stderr:
            with self.assertRaises(SystemExit) as error:
                lab.main()
        self.assertEqual(error.exception.code, 2)
        self.assertIn("AZURE_SUBSCRIPTION_ID", stderr.getvalue())
        cli.assert_not_called()

    def test_placeholder_subscription_exits_before_any_azure_call(self):
        environment = {name: "example" for name in lab.REQUIRED_ENVIRONMENT}
        with patch.dict(lab.os.environ, environment), \
                patch.object(lab, "SUBSCRIPTION", "00000000-0000-0000-0000-000000000001"), \
                patch.object(lab.sys, "argv", ["lab.py", "direct"]), \
                patch.object(lab, "cli_json") as cli, \
                patch.object(lab.sys, "stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as error:
                lab.main()
        self.assertEqual(error.exception.code, 2)
        cli.assert_not_called()

    def test_redacts_known_secret_inside_embedded_trace_json(self):
        secret = "example-subscription-credential"
        lab.SECRET_VALUES.add(secret)
        try:
            self.assertNotIn(secret, lab.sanitize('{"message":"' + secret + '"}'))
        finally:
            lab.SECRET_VALUES.remove(secret)

    def test_policy_uses_actual_stable_subscription(self):
        policy = ET.fromstring(lab.operation_policy("run", "baseline", estimate=False))
        limit = policy.find("inbound/llm-token-limit")
        self.assertEqual(limit.get("estimate-prompt-tokens"), "false")
        self.assertIn("context.Subscription.Id", limit.get("counter-key"))
        self.assertEqual(limit.get("token-quota-period"), "Hourly")
        self.assertIsNotNone(policy.find("inbound/base"))

    def test_tpm_only_has_no_quota(self):
        limit = ET.fromstring(lab.operation_policy("run", "tpm", tpm=300, quota=None)).find("inbound/llm-token-limit")
        self.assertEqual(limit.get("tokens-per-minute"), "300")
        self.assertIsNone(limit.get("token-quota"))
        self.assertIsNone(limit.get("remaining-quota-tokens-header-name"))

    def test_quota_only_has_no_tpm_header(self):
        limit = ET.fromstring(lab.operation_policy("run", "quota", tpm=None, quota=220)).find("inbound/llm-token-limit")
        self.assertIsNone(limit.get("tokens-per-minute"))
        self.assertIsNone(limit.get("remaining-tokens-header-name"))
        self.assertEqual(limit.get("remaining-quota-tokens-header-name"), "x-lab-quota")

    def test_probe_returns_before_token_limit_but_after_inherited_authentication(self):
        inbound = ET.fromstring(lab.operation_policy("run", "phase")).find("inbound")
        self.assertEqual([child.tag for child in inbound], ["base", "choose", "llm-token-limit"])
        response = inbound.find("choose/when/return-response")
        self.assertEqual(response.find("set-status").get("code"), "204")
        self.assertEqual(response.find("set-header/value").text, "phase")

    def test_waits_for_matching_gateway_policy_without_model_calls(self):
        instance = lab.Lab("v2", "unit-test")
        instance.subscription_key = "sample-value"
        replies = [
            {"status": 204, "headers": {"x-lab-phase": phase}, "body": ""}
            for phase in ("old", "new")
        ]
        with patch.object(instance, "token", return_value="sample-value"), \
                patch.object(lab, "http", side_effect=replies) as http, \
                patch.object(lab.time, "sleep"), patch.object(lab, "save_json"):
            instance.wait_phase("project-preview", "responses", "new")
        self.assertEqual(http.call_count, 2)
        self.assertEqual(http.call_args.args[2]["x-lab-probe"], "true")
        self.assertEqual(http.call_args.args[3], {})

    def test_backend_rejection_cannot_be_mistaken_for_policy_rejection(self):
        instance = lab.Lab("v2", "unit-test")
        record = {
            "response": {"status": 429}, "traceSources": ["llm-token-limit"],
            "backendStatuses": [429],
        }
        with self.assertRaises(lab.LabError):
            instance.require_rejection(record, 429, "llm-token-limit")
        record["backendStatuses"] = []
        instance.require_rejection(record, 429, "llm-token-limit")

    def test_trace_extracts_real_backend_response_status(self):
        trace = {"traceEntries": {"backend": [
            {"source": "request-forwarder", "data": {"request": {}}},
            {"source": "request-forwarder", "data": {"response": {"status": {"code": 429}}}},
        ]}}
        self.assertEqual(lab.trace_backend_statuses(trace), [429])

    def test_trace_retries_only_not_yet_available_results(self):
        instance = lab.Lab("classic", "unit-test")
        trace = {"traceEntries": {}}
        with patch.object(instance, "arm", side_effect=[None, trace]) as arm, \
                patch.object(lab.time, "sleep"):
            self.assertEqual(instance.get_trace("sample-trace-id"), trace)
        self.assertEqual(arm.call_count, 2)
        self.assertIs(arm.call_args.kwargs["allow_not_found"], True)

    def test_request_mitigation_replaces_only_operation_token_policy(self):
        policy = ET.fromstring(lab.operation_policy("run", "requests", calls=3))
        self.assertIsNone(policy.find("inbound/llm-token-limit"))
        self.assertEqual(policy.find("inbound/rate-limit-by-key").get("calls"), "3")
        self.assertIsNotNone(policy.find("inbound/base"))

    def test_missing_usage_is_not_reported_as_zero(self):
        self.assertIsNone(lab.usage_total({"error": "test"}))
        self.assertEqual(lab.usage_total({"usage": {"total_tokens": 44}}), 44)

    def test_nonstreaming_payload_shapes(self):
        responses = lab.payload("responses")
        chat = lab.payload("chat")
        self.assertIs(responses["stream"], False)
        self.assertIs(chat["stream"], False)
        self.assertIn("input", responses)
        self.assertIn("messages", chat)
        self.assertEqual(responses["max_output_tokens"], 128)

    def test_openapi_paths_match_project_and_account_routes(self):
        paths = lab.schema()["paths"]
        self.assertEqual(paths["/responses"]["post"]["operationId"], "responses")
        self.assertEqual(paths["/chat/completions"]["post"]["operationId"], "chat")


if __name__ == "__main__":
    unittest.main()
