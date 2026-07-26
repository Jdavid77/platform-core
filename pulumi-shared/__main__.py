"""Shared platform infrastructure — Auth0 IdP"""

from modules.auth0 import (
    Auth0ClientConfig,
    Auth0RoleConfig,
    create_groups_action,
    create_kubernetes_client,
    create_role,
)

import pulumi

# Config
config = pulumi.Config()
auth0_cfg = pulumi.Config("auth0")
clusters = config.require_object("clusters")
roles = config.require_object("roles")

# Action
create_groups_action()

# Roles
for role in roles:
    role_cfg = Auth0RoleConfig(
        name=role["name"],
        description=role.get("description", ""),
    )
    create_role(role_cfg)

# Clients
k8s_clients = {
    cluster: create_kubernetes_client(Auth0ClientConfig(name=f"kubernetes-{cluster}"))
    for cluster in clusters
}

# Outputs
pulumi.export(
    "auth0_issuer_url",
    pulumi.Output.concat("https://", auth0_cfg.require("domain"), "/"),
)
for cluster, client in k8s_clients.items():
    pulumi.export(f"auth0_client_id_{cluster}", client.client_id)
