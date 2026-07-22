import base64
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pulumi_command.local as local
import yaml
from pulumi import ResourceOptions
from pulumi_kubernetes import Provider

from .network import NetworkConfig


@dataclass
class ClusterConfig:
    name: str
    kind_image: Optional[str] = None
    wait_seconds: int = 60


class ClusterManager:

    def __init__(
        self,
        config: ClusterConfig,
        net: NetworkConfig,
        depends_on=None,
    ):
        self.config = config
        self.net = net
        self.depends_on = depends_on or []

    def render_kind_config(self) -> str:
        node: Dict[str, Any] = {"role": "control-plane"}
        if self.net.extraPortMappings:
            node["extraPortMappings"] = [vars(pm) for pm in self.net.extraPortMappings]
        kind_cfg: Dict[str, Any] = {
            "kind": "Cluster",
            "apiVersion": "kind.x-k8s.io/v1alpha4",
            "networking": {
                "podSubnet": self.net.podCidr,
                "serviceSubnet": self.net.serviceCidr,
            },
            "nodes": [node, {"role": "worker"}],
        }
        return yaml.safe_dump(kind_cfg, sort_keys=False)

    def write_kind_config(self, yaml_content: str) -> local.Command:
        path = f".pulumi/kind/{self.config.name}.yaml"
        b64 = base64.b64encode(yaml_content.encode("utf-8")).decode("ascii")
        script = (
            "bash -euo pipefail -lc "
            f"'mkdir -p .pulumi/kind\n"
            f'base64 -d > {path} <<"EOF"\n'
            f"{b64}\n"
            "EOF\n'"
        )
        return local.Command(
            "kind:cfg",
            create=script,
            delete=f'rm -f "{path}"',
            triggers=[yaml_content, path],
        )

    def create(self) -> Tuple[local.Command, local.Command, Provider]:
        kind_yaml = self.render_kind_config()
        kind_cfg_file = self.write_kind_config(kind_yaml)
        replace_triggers = [
            kind_yaml,
            self.net.dockerNetwork,
            self.net.vpcCidr,
            self.config.kind_image or "",
        ]

        create_cmd = (
            f'KIND_EXPERIMENTAL_DOCKER_NETWORK="{self.net.dockerNetwork}" '
            "kind create cluster"
            f" --name {self.config.name}"
            f' --config ".pulumi/kind/{self.config.name}.yaml"'
            f" --image {self.config.kind_image}"
            f" --wait {self.config.wait_seconds}s"
        )
        # delete_before_replace=True because kind cannot upgrade a cluster in-place
        cluster = local.Command(
            "kind:create",
            create=create_cmd,
            delete=f"kind delete cluster --name {self.config.name}",
            triggers=replace_triggers,
            opts=ResourceOptions(
                depends_on=self.depends_on + [kind_cfg_file],
                delete_before_replace=True,
            ),
        )
        get_kubeconfig = f"kind get kubeconfig --name {self.config.name}"
        kubeconfig = local.Command(
            "kind:kubeconfig",
            create=get_kubeconfig,
            update=get_kubeconfig,
            triggers=[cluster.id],
            opts=ResourceOptions(depends_on=[cluster]),
        )
        provider = Provider(
            "k8s",
            kubeconfig=kubeconfig.stdout,
            enable_server_side_apply=True,
        )
        return cluster, kubeconfig, provider
