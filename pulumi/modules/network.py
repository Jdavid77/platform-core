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
    # Idempotent: succeed only if network already exists with the correct subnet
    create = (
        f"docker network create {cfg.dockerNetwork} --subnet {cfg.vpcCidr} 2>/dev/null || "
        f"docker network inspect {cfg.dockerNetwork} "
        f"--format '{{{{range .IPAM.Config}}}}{{{{.Subnet}}}}{{{{end}}}}' | grep -qF {cfg.vpcCidr}"
    )
    return local.Command(
        "docker:net",
        create=create,
        delete=f"docker network rm {cfg.dockerNetwork} || true",
        triggers=[cfg.dockerNetwork, cfg.vpcCidr],
    )
