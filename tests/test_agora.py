import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora


class Fake:
    def __init__(self, name, fail=0):
        self.name, self.fail, self.prompts = name, fail, []

    def check(self):
        return "subscription"

    def answer(self, prompt, timeout):
        self.prompts.append(json.loads(prompt.split("INPUT_JSON:\n", 1)[1]))
        if len(self.prompts) == self.fail:
            raise agora.AgoraError("Subscription limit reached")
        return f"{self.name}-{len(self.prompts)}"


class DebateTests(unittest.TestCase):
    def test_independence_and_symmetric_rounds(self):
        providers = {name: Fake(name) for name in ("codex", "claude")}
        with tempfile.TemporaryDirectory() as folder:
            result = agora.debate(providers, "question", "rules", 2, 30, Path(folder))
            self.assertEqual(result["status"], "completed")
            self.assertEqual(len(result["turns"]), 7)
            for name, peer in (("codex", "claude"), ("claude", "codex")):
                prompts = providers[name].prompts
                self.assertNotIn("peer_previous_answer", prompts[0])
                self.assertEqual(prompts[1]["peer_previous_answer"], f"{peer}-1")
                self.assertEqual(prompts[2]["peer_previous_answer"], f"{peer}-2")
            self.assertEqual(result["verification"], "not_performed")

    def test_failure_preserves_partial_without_retry(self):
        providers = {"codex": Fake("codex"), "claude": Fake("claude", fail=2)}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(agora.AgoraError):
                agora.debate(providers, "q", "r", 1, 30, Path(folder))
            record = json.loads((Path(folder) / "transcript.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "stopped")
            self.assertEqual(len(record["turns"]), 3)
            self.assertIsNone(record["summary"])
            self.assertEqual(len(providers["claude"].prompts), 2)

    def test_deadline_stops_before_generation(self):
        providers = {name: Fake(name) for name in ("codex", "claude")}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(agora.AgoraError):
                agora.debate(providers, "q", "r", 1, 30, Path(folder), 0)
            self.assertFalse(providers["codex"].prompts)

    def test_api_auth_rejected(self):
        with patch.object(agora, "executable", return_value="claude.exe"):
            provider = agora.Provider("claude", ".")
        for method in ("api_key", "api_key_helper", "oauth_token", "third_party"):
            response = json.dumps({"loggedIn": True, "authMethod": method,
                                   "apiProvider": "firstParty", "subscriptionType": "pro"})
            with patch.object(agora, "invoke", return_value=(0, response, "")):
                with self.assertRaises(agora.AgoraError):
                    provider.check()

    def test_codex_api_auth_rejected(self):
        with patch.object(agora, "executable", return_value="codex.exe"):
            provider = agora.Provider("codex", ".")
        with patch.object(agora, "invoke", return_value=(0, "Logged in using an API key", "")):
            with self.assertRaises(agora.AgoraError):
                provider.check()

    def test_credential_overrides_removed(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake", "CODEX_API_KEY": "fake",
                                    "CLAUDE_CODE_OAUTH_TOKEN": "fake", "CLAUDE_CODE_USE_BEDROCK": "1"}):
            env = agora.clean_env()
        for key in ("ANTHROPIC_API_KEY", "CODEX_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK"):
            self.assertNotIn(key, env)

    def test_expired_session_is_actionable(self):
        with patch.object(agora, "executable", return_value="claude.exe"):
            provider = agora.Provider("claude", ".")
        response = json.dumps({"is_error": True, "result": "Failed to authenticate: OAuth session expired"})
        with patch.object(provider, "check"), patch.object(agora, "invoke", return_value=(1, response, "")):
            with self.assertRaisesRegex(agora.AgoraError, "login-claude.cmd"):
                provider.answer("test", 30)


if __name__ == "__main__":
    unittest.main()
