"""A Python Pulumi program"""

import pulumi
from modules import network, cluster, flux

config = pulumi.Config()
network_obj = config.require_object("network")
cls_info = config.require_object("cluster-info")

# Map config -> dataclasses
net_cfg = network.NetworkConfig(
    dockerNetwork=network_obj["dockerNetwork"],
    vpcCidr=network_obj["vpcCidr"],
    podCidr=network_obj["podCidr"],
    serviceCidr=network_obj["serviceCidr"],
    extraPortMappings=[
        network.PortMap(**pm) for pm in network_obj.get("extraPortMappings", [])
    ]
    or None,
)

# Network
docker_net = network.ensure_docker_network(net_cfg)

# Cluster + k8s provider
cls_cfg = cluster.ClusterConfig(
    name=cls_info["name"],
    kind_image=cls_info.get("kind-image"),
    wait_seconds=cls_info.get("wait-seconds"),
)

cluster_manager = cluster.ClusterManager(
    config=cls_cfg,
    net=net_cfg,
    depends_on=[docker_net],
)
create, kubeconfig, k8s = cluster_manager.create()

# Flux
flux_obj = config.require_object("flux")
flux_manager = flux.FluxOperatorManager(
    config=flux.FluxOperatorConfig(
        version=flux_obj.get("version"),
        url=flux_obj.get("url"),
        sourceName=pulumi.get_stack(),
    ),
    stack_name=pulumi.get_stack(),
    provider=k8s,
)
flux_manager.install()

# Outputs
pulumi.export("kubeconfig", pulumi.Output.secret(kubeconfig.stdout))
pulumi.export("dockerNetwork", network_obj["dockerNetwork"])
pulumi.export("clusterName", cls_info["name"])
