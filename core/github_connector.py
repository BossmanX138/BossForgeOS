"""
GitHub Connector for CodeMage
- Securely interacts with GitHub API for issues, PRs, and repo status
- No token leaks in logs/events
- Token from env GITHUB_TOKEN or vault (if integrated)
"""

import os
import requests
from typing import Optional

GITHUB_API = "https://api.github.com"

class GitHubConnector:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            raise RuntimeError("GitHub token not set in env or provided to GitHubConnector")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "BossForgeOS-GitHubConnector"
        }

    def create_issue(self, owner: str, repo: str, title: str, body: str = "") -> dict:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
        resp = requests.post(url, headers=self.headers, json={"title": title, "body": body})
        return self._safe_response(resp)

    def list_prs(self, owner: str, repo: str, state: str = "open") -> dict:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls?state={state}"
        resp = requests.get(url, headers=self.headers)
        return self._safe_response(resp)

    def repo_status(self, owner: str, repo: str) -> dict:
        url = f"{GITHUB_API}/repos/{owner}/{repo}"
        resp = requests.get(url, headers=self.headers)
        return self._safe_response(resp)

    def _safe_response(self, resp: requests.Response) -> dict:
        # Never log or emit the token
        try:
            data = resp.json()
        except Exception:
            data = {"ok": False, "error": "Invalid JSON from GitHub"}
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "error": data.get("message", "Unknown error")}
        return {"ok": True, "data": data}
