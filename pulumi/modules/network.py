from dataclasses import dataclass
from typing import List, Optional

import pulumi_command.local as local


@dataclass
class PortMap:
    hostPort: int
    containerPort: int
    protocol: str = "TCP"


@dataclass
class NetworkConfig:
    dockerNetwork: str
    vpcCidr: str
    podCidr: str
    serviceCidr: str
    extraPortMappings: Optional[List[PortMap]] = None


def ensure_docker_network(cfg: NetworkConfig) -> local.Command:
    return local.Command(
        "docker:net",
        create=f"docker network create {cfg.dockerNetwork} --subnet {cfg.vpcCidr} || true",
        delete=f"docker network rm {cfg.dockerNetwork} || true",
    )
