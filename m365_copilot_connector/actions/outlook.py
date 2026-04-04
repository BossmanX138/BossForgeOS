"""Outlook action handlers backed by Microsoft Graph API."""

import os
from typing import Any, Dict, List

import msal
import requests

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_access_token() -> str:
    tenant_id = _required_env("M365_TENANT_ID")
    client_id = _required_env("M365_CLIENT_ID")
    client_secret = _required_env("M365_CLIENT_SECRET")

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )

    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    token = result.get("access_token")
    if not token:
        error = result.get("error_description") or result.get("error") or "Unknown auth error"
        raise RuntimeError(f"Microsoft Graph authentication failed: {error}")
    return token


def _mailbox_user() -> str:
    return _required_env("M365_MAILBOX_USER")


def _graph_headers() -> Dict[str, str]:
    token = _get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _normalize_messages(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": msg.get("id"),
            "subject": msg.get("subject"),
            "from": (msg.get("from") or {}).get("emailAddress", {}).get("address"),
            "receivedDateTime": msg.get("receivedDateTime"),
            "bodyPreview": msg.get("bodyPreview"),
            "isRead": msg.get("isRead"),
        }
        for msg in items
    ]


def read_email(folder: str = "inbox", max_results: int = 10) -> Dict[str, Any]:
    max_results = max(1, min(int(max_results), 50))
    user = _mailbox_user()
    url = f"{GRAPH_BASE_URL}/users/{user}/mailFolders/{folder}/messages"
    params = {
        "$top": max_results,
        "$orderby": "receivedDateTime DESC",
        "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead",
    }

    response = requests.get(url, headers=_graph_headers(), params=params, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"Graph read email failed ({response.status_code}): {response.text}")

    payload = response.json()
    items = payload.get("value", [])
    return {
        "emails": _normalize_messages(items),
        "count": len(items),
        "folder": folder,
        "mailbox": user,
    }


def send_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    user = _mailbox_user()
    url = f"{GRAPH_BASE_URL}/users/{user}/sendMail"
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body,
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to,
                    }
                }
            ],
        },
        "saveToSentItems": True,
    }

    response = requests.post(url, headers=_graph_headers(), json=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"Graph send email failed ({response.status_code}): {response.text}")

    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "mailbox": user,
    }
