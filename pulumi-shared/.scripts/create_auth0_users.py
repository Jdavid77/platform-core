#!/usr/bin/env python3
"""Create Auth0 users and optionally assign roles.

Credentials are pulled from the pulumi-shared stack config (auth0:domain,
auth0:clientId, auth0:clientSecret). Run from the pulumi-shared directory
or pass --stack to specify the stack name.

Usage:
  # Single user
  python .scripts/create_auth0_users.py --email alice@example.com --name "Alice" --role platform-admin

  # Bulk from file (one JSON object per line)
  python .scripts/create_auth0_users.py --file users.jsonl

File format (users.jsonl):
  {"email": "alice@example.com", "name": "Alice", "role": "platform-admin"}
  {"email": "bob@example.com",   "name": "Bob",   "role": "platform-viewer"}

Note: users are created with a temporary password derived from their email.
      You can log in and change it manually via the Auth0 dashboard.
"""

import argparse
import json
import subprocess
import sys
import urllib.request
from typing import Optional

SCRIPT_DIR = __import__("pathlib").Path(__file__).parent
PULUMI_DIR = SCRIPT_DIR.parent


def _pulumi_config_get(key: str, stack: str, secret: bool = False) -> str:
    cmd = ["pulumi", "config", "get", key, "--stack", stack]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PULUMI_DIR)
    if result.returncode != 0:
        print(f"Failed to get pulumi config '{key}': {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def _request(method: str, url: str, token: str, body: Optional[dict] = None):
    data = json.dumps(body).encode() if body else None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def get_mgmt_token(domain: str, client_id: str, client_secret: str) -> str:
    body = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://{domain}/oauth/token",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


class Auth0Client:
    def __init__(self, domain: str, token: str):
        self.base = f"https://{domain}/api/v2"
        self.token = token

    def create_user(self, payload: dict) -> dict:
        return _request("POST", f"{self.base}/users", self.token, payload)

    def list_roles(self) -> list:
        return _request("GET", f"{self.base}/roles", self.token)

    def assign_role(self, user_id: str, role_id: str):
        _request("POST", f"{self.base}/users/{user_id}/roles", self.token, {"roles": [role_id]})


def get_client(stack: str) -> tuple["Auth0Client", str]:
    domain = _pulumi_config_get("auth0:domain", stack)
    client_id = _pulumi_config_get("auth0:clientId", stack, secret=True)
    client_secret = _pulumi_config_get("auth0:clientSecret", stack, secret=True)
    token = get_mgmt_token(domain, client_id, client_secret)
    return Auth0Client(domain, token), domain


def get_role_id(client: "Auth0Client", role_name: str) -> str:
    roles = client.list_roles()
    for role in roles:
        if role["name"] == role_name:
            return role["id"]
    available = [r["name"] for r in roles]
    print(f"Role '{role_name}' not found. Available: {available}", file=sys.stderr)
    sys.exit(1)


def create_user(client: "Auth0Client", email: str, name: str, role: Optional[str]) -> dict:
    pwd = _temp_password(email)
    user = client.create_user({
        "email": email,
        "name": name,
        "connection": "Username-Password-Authentication",
        "password": pwd,
        "email_verified": False,
    })

    print(f"  Created: {email} (id={user['user_id']}, password={pwd})")

    if role:
        role_id = get_role_id(client, role)
        client.assign_role(user["user_id"], role_id)
        print(f"  Assigned role: {role}")

    return user


def _temp_password(email: str) -> str:
    # Generates a deterministic temporary password that satisfies Auth0's policy.
    # Users must reset on first login — trigger a password reset email after creation.
    import hashlib
    h = hashlib.sha256(email.encode()).hexdigest()[:12]
    return f"Tmp!{h}"


def main():
    parser = argparse.ArgumentParser(description="Create Auth0 users")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="User email address")
    group.add_argument("--file", help="Path to .jsonl file with user definitions")
    parser.add_argument("--name", help="User display name (required with --email)")
    parser.add_argument("--role", help="Auth0 role to assign (optional)")
    parser.add_argument("--stack", default="shared", help="Pulumi stack name (default: shared)")
    args = parser.parse_args()

    if args.email and not args.name:
        parser.error("--name is required when using --email")

    client, _ = get_client(args.stack)

    users_to_create = []
    if args.email:
        users_to_create = [{"email": args.email, "name": args.name, "role": args.role}]
    else:
        with open(args.file) as f:
            for line in f:
                line = line.strip()
                if line:
                    users_to_create.append(json.loads(line))

    for u in users_to_create:
        print(f"\nProcessing {u['email']}...")
        try:
            create_user(client, u["email"], u["name"], u.get("role") or args.role)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
