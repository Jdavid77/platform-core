from dataclasses import dataclass, field

import pulumi_auth0 as auth0

from pulumi import ResourceOptions


@dataclass
class Auth0ClientConfig:
    name: str
    callbacks: list[str] = field(default_factory=lambda: ["http://localhost:8000"])
    allowed_logout_urls: list[str] = field(
        default_factory=lambda: ["http://localhost:8000"]
    )
    web_origins: list[str] = field(default_factory=lambda: ["http://localhost:8000"])


@dataclass
class Auth0RoleConfig:
    name: str
    description: str


def create_kubernetes_client(config: Auth0ClientConfig) -> auth0.Client:
    return auth0.Client(
        f"auth0:client:{config.name}",
        auth0.ClientArgs(
            name=config.name,
            app_type="native",
            oidc_conformant=True,
            callbacks=config.callbacks,
            allowed_logout_urls=config.allowed_logout_urls,
            web_origins=config.web_origins,
            grant_types=["authorization_code", "refresh_token"],
            jwt_configuration=auth0.ClientJwtConfigurationArgs(alg="RS256"),
        ),
    )


def create_role(config: Auth0RoleConfig) -> None:
    auth0.Role(
        f"auth0:role:{config.name}",
        auth0.RoleArgs(name=config.name, description=config.description),
    )


# Action code that copies app_metadata.groups into the ID token
# https://auth0.com/docs/manage-users/access-control/sample-use-cases-actions-with-authorization#add-user-roles-to-tokens
_GROUPS_ACTION_CODE = """\
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://platform.internal';
  if (event.authorization) {
    api.idToken.setCustomClaim(`${namespace}/roles`, event.authorization.roles);
  }
};
"""


def create_groups_action() -> auth0.TriggerAction:
    action = auth0.Action(
        "auth0:action:add-groups-claim",
        auth0.ActionArgs(
            name="Add groups claim",
            runtime="node18",
            deploy=True,
            code=_GROUPS_ACTION_CODE,
            supported_triggers=auth0.ActionSupportedTriggersArgs(
                id="post-login", version="v3"
            ),
        ),
    )
    return auth0.TriggerAction(
        "auth0:trigger:post-login-groups",
        auth0.TriggerActionArgs(
            trigger="post-login",
            action_id=action.id,
            display_name="Add groups claim",
        ),
        opts=ResourceOptions(depends_on=[action]),
    )
