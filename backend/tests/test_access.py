import unittest

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.access import ApiAccessMiddleware
from app.core.config import Settings


class AccessTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(ApiAccessMiddleware, token="a" * 32)
        app.add_middleware(CORSMiddleware, allow_origins=["https://lkaiwee.github.io"],
                           allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
        app.get("/api/health")(lambda: {"status": "ok"})
        app.get("/api/access")(lambda: {"authentication_required": True})
        app.get("/api/portfolio")(lambda: {"positions": []})
        app.post("/api/portfolio")(lambda: {"created": True})
        self.client = TestClient(app)

    def test_data_and_docs_require_owner_token(self):
        for path in ["/api/portfolio", "/docs", "/openapi.json"]:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post("/api/portfolio").status_code, 401)
        self.assertEqual(self.client.get("/api/portfolio", headers={"Authorization": "Bearer wrong"}).status_code, 401)

    def test_valid_owner_can_read_and_write(self):
        headers = {"Authorization": "Bearer " + "a" * 32}
        response = self.client.get("/api/portfolio", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.post("/api/portfolio", headers=headers).status_code, 200)

    def test_public_health_and_access_status(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/access").status_code, 200)

    def test_cors_preflight_and_auth_error_reach_pages(self):
        headers = {"Origin": "https://lkaiwee.github.io", "Access-Control-Request-Method": "GET",
                   "Access-Control-Request-Headers": "authorization"}
        self.assertEqual(self.client.options("/api/portfolio", headers=headers).status_code, 200)
        response = self.client.get("/api/portfolio", headers={"Origin": "https://lkaiwee.github.io"})
        self.assertEqual(response.headers["access-control-allow-origin"], "https://lkaiwee.github.io")
        self.assertNotIn("access-control-allow-origin", self.client.get("/api/portfolio", headers={"Origin": "https://untrusted.example"}).headers)

    def test_required_auth_rejects_missing_or_short_token(self):
        for token in ["", "short"]:
            with self.assertRaises(ValueError):
                Settings(_env_file=None, api_auth_required=True, api_access_token=token)

    def test_neon_connection_url_uses_installed_driver(self):
        settings = Settings(_env_file=None, database_url="postgresql://u:p@db.example/db?sslmode=require")
        self.assertEqual(settings.database_url, "postgresql+psycopg://u:p@db.example/db?sslmode=require")


if __name__ == "__main__":
    unittest.main()
