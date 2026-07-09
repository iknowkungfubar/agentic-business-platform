"""Locust load test for the TurinTech Platform.

Run with:
  locust -f locustfile.py --host=http://localhost:8000
  # Then open http://localhost:8089 in browser

Headless mode (CI):
  locust -f locustfile.py --host=http://localhost:8000 \\
    --headless -u 10 -r 2 --run-time 30s --csv=results

Requires: pip install locust
"""
from locust import HttpUser, between, task


class PlatformUser(HttpUser):
    """Simulates a regular platform user."""
    wait_time = between(1, 3)

    def on_start(self):
        """Register and login on start."""
        self.email = f"loadtest-{self.runner.user_count}@test.com"
        self.password = "testpass"
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "org_name": "LoadTest",
            },
            catch_response=True,
        ) as r:
            if r.status_code == 200:
                self.token = r.json()["access_token"]
                self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def check_health(self):
        """Health endpoint is the most frequent call."""
        self.client.get("/health")

    @task(2)
    def classify(self):
        """Classify a text input."""
        if hasattr(self, "headers"):
            self.client.post(
                "/api/v1/classify",
                json={"text": "What is machine learning?"},
                headers=self.headers,
            )

    @task(2)
    def list_agents(self):
        """List agents (paginated)."""
        if hasattr(self, "headers"):
            self.client.get("/api/v1/agents?page=1&page_size=10", headers=self.headers)

    @task(1)
    def evaluate_policy(self):
        """Evaluate an action against policies."""
        if hasattr(self, "headers"):
            self.client.post(
                "/api/v1/test-policy",
                json={
                    "action": {
                        "action_type": "data_access",
                        "resource_type": "cui",
                        "authorized": False,
                    }
                },
                headers=self.headers,
            )

    @task(1)
    def eval_criteria(self):
        """List eval criteria."""
        if hasattr(self, "headers"):
            self.client.get("/api/v1/eval/criteria", headers=self.headers)

    @task(1)
    def list_policies(self):
        """List policies."""
        if hasattr(self, "headers"):
            self.client.get("/api/v1/policies", headers=self.headers)
