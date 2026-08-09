import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from fastapi.testclient import TestClient

from orchestration.api import create_app
from orchestration.service import OrchestrationService


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        with redirect_stdout(io.StringIO()):
            self.service = OrchestrationService(
                database_path=str(root / "api.db"),
                runtime_directory=str(root / "runtime"),
            )
            bootstrap = self.service.bootstrap(
                "API Test Tenant",
                "api-test",
            )
        self.api_key = bootstrap["api_key"]["api_key"]
        self.model_id = bootstrap["identity"]["id"]
        self.client = TestClient(create_app(self.service))
        self.client.__enter__()
        self.headers = {"X-API-Key": self.api_key}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def test_public_health_profile_and_security_headers(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        profile = self.client.get("/api/v1/public/naydoev1")
        self.assertEqual(profile.status_code, 404)

    def test_authentication_and_tenant_models(self):
        self.assertEqual(
            self.client.get("/api/v1/models").status_code,
            401,
        )
        with redirect_stdout(io.StringIO()):
            response = self.client.get(
                "/api/v1/models",
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "NayDoeV1")

    def test_create_skill_and_key_lifecycle(self):
        with redirect_stdout(io.StringIO()):
            skill = self.client.post(
                "/api/v1/skills",
                headers=self.headers,
                json={
                    "name": "API Skill",
                    "description": "Created through the API",
                    "system_prompt": "Answer precisely.",
                    "allowed_models": [self.model_id],
                },
            )
        self.assertEqual(skill.status_code, 201, skill.text)

        with redirect_stdout(io.StringIO()):
            key_response = self.client.post(
                "/api/v1/auth/keys",
                headers=self.headers,
                json={"name": "readonly", "scopes": ["read"]},
            )
        self.assertEqual(key_response.status_code, 201)
        new_key = key_response.json()
        self.assertTrue(new_key["api_key"].startswith("orc_live_"))

        with redirect_stdout(io.StringIO()):
            revoke = self.client.delete(
                f"/api/v1/auth/keys/{new_key['id']}",
                headers=self.headers,
            )
        self.assertEqual(revoke.status_code, 204)
        self.assertEqual(
            self.client.get(
                "/api/v1/models",
                headers={"X-API-Key": new_key["api_key"]},
            ).status_code,
            401,
        )

    def test_quantum_provider_endpoint_does_not_claim_access(self):
        with redirect_stdout(io.StringIO()):
            response = self.client.get(
                "/api/v1/quantum/providers",
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200)
        nighthawk = response.json()[0]
        self.assertFalse(nighthawk["target_configured"])
        self.assertIn("not assumed", nighthawk["access_note"])


if __name__ == "__main__":
    unittest.main()
