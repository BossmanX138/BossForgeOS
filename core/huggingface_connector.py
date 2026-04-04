"""
Hugging Face Connector for Devlot Agent
- Securely interacts with Hugging Face Hub for model/dataset search, download, and listing
- No token leaks in logs/events
- Token from env HUGGINGFACE_TOKEN or anonymous if not set
"""

import os
import requests
from typing import Optional

HF_API = "https://huggingface.co/api"

class HuggingFaceConnector:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("HUGGINGFACE_TOKEN", "")
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "BossForgeOS-HuggingFaceConnector"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def search_models(self, query: str, limit: int = 10) -> dict:
        url = f"{HF_API}/models"
        params = {"search": query, "limit": limit}
        resp = requests.get(url, headers=self.headers, params=params)
        return self._safe_response(resp)

    def list_models(self, author: Optional[str] = None, limit: int = 10) -> dict:
        url = f"{HF_API}/models"
        params = {"author": author, "limit": limit} if author else {"limit": limit}
        resp = requests.get(url, headers=self.headers, params=params)
        return self._safe_response(resp)

    def download_model(self, repo_id: str, filename: str, dest_path: str) -> dict:
        url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        resp = requests.get(url, headers=self.headers, stream=True)
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return {"ok": True, "path": dest_path}
        return {"ok": False, "status": resp.status_code, "error": resp.text}

    def _safe_response(self, resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except Exception:
            data = {"ok": False, "error": "Invalid JSON from Hugging Face"}
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "error": data.get("error", "Unknown error")}
        return {"ok": True, "data": data}
