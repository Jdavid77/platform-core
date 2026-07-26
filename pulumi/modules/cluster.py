from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pulumi_command.local as local
import yaml
from pulumi import Input, Output, ResourceOptions
from pulumi_kubernetes import Provider

from .network import NetworkConfig


@dataclass
class OidcConfig:
    issuer_url: Input[str]
    client_id: Input[str] = "kubernetes"
    username_claim: str = "email"
    groups_claim: Input[str] = "https://platform.internal/roles"


@dataclass
class ClusterConfig:
    name: str
    oidc: OidcConfig
    kind_image: Optional[str] = None
    wait_seconds: int = 60


class ClusterManager:

    def __init__(self, config: ClusterConfig, net: NetworkConfig, depends_on=None):
        self.config = config
        self.net = net
        self.depends_on = depends_on or []

    def _render_kind_config(self) -> Output[str]:
        oidc = self.config.oidc

        def build(vals: list) -> str:
            issuer_url, client_id, groups_claim = vals
            api_server_cfg: Dict[str, Any] = {
                "extraArgs": {
                    "oidc-issuer-url": issuer_url,
                    "oidc-client-id": client_id,
                    "oidc-username-claim": oidc.username_claim,
                    "oidc-groups-claim": groups_claim,
                }
            }
            node: Dict[str, Any] = {
                "role": "control-plane",
                "extraPortMappings": [
                    vars(pm) for pm in (self.net.extraPortMappings or [])
                ],
                "kubeadmConfigPatches": [
                    yaml.safe_dump(
                        {"kind": "ClusterConfiguration", "apiServer": api_server_cfg}
                    )
                ],
            }
            return yaml.safe_dump(
                {
                    "kind": "Cluster",
                    "apiVersion": "kind.x-k8s.io/v1alpha4",
                    "networking": {
                        "podSubnet": self.net.podCidr,
                        "serviceSubnet": self.net.serviceCidr,
                    },
                    "nodes": [node, {"role": "worker"}],
                },
                sort_keys=False,
            )

        return Output.all(
            Output.from_input(oidc.issuer_url),
            Output.from_input(oidc.client_id),
            Output.from_input(oidc.groups_claim),
        ).apply(build)

    def create(self) -> Tuple[local.Command, Output[str]]:
        kind_yaml = self._render_kind_config()
        create_cmd = (
            f"printf '%s' \"$KIND_CONFIG\" | "
            f'KIND_EXPERIMENTAL_DOCKER_NETWORK="{self.net.dockerNetwork}" '
            f"kind create cluster"
            f" --name {self.config.name}"
            f" --config -"
            f" --image {self.config.kind_image}"
            f" --wait {self.config.wait_seconds}s"
        )
        cluster = local.Command(
            "kind:create",
            create=create_cmd,
            delete=f"kind delete cluster --name {self.config.name}",
            environment={"KIND_CONFIG": kind_yaml},
            triggers=[
                kind_yaml,
                self.net.dockerNetwork,
                self.net.vpcCidr,
                self.config.kind_image or "",
            ],
            opts=ResourceOptions(
                depends_on=self.depends_on, delete_before_replace=True
            ),
        )
        return cluster, kind_yaml

    def get_kubeconfig(self, cluster: local.Command) -> local.Command:
        get_cmd = f"kind get kubeconfig --name {self.config.name}"
        return local.Command(
            "kind:kubeconfig",
            create=get_cmd,
            update=get_cmd,
            triggers=[cluster.id],
            opts=ResourceOptions(depends_on=[cluster]),
        )

    def get_provider(self, kubeconfig: local.Command) -> Provider:
        return Provider(
            "k8s",
            kubeconfig=kubeconfig.stdout,
            enable_server_side_apply=True,
        )
