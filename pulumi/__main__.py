"""A Python Pulumi program"""

import pulumi
from modules import network, cluster

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
# Network scaffolding + kind config
docker_net = network.ensure_docker_network(net_cfg)
kind_yaml = network.render_kind_config(net_cfg)
kind_cfg_file = network.write_kind_config(cls_info["name"], kind_yaml)


cls_cfg = cluster.ClusterConfig(
    name=cls_info["name"],
    kind_image=cls_info.get("kind-image"),
    wait_seconds=cls_info.get("wait-seconds"),
)
# Cluster + k8s provider
create, kubeconfig, k8s = cluster.create_kind_cluster(
    cls_cfg,
    cfg_file_path=f".pulumi/kind/{cls_cfg.name}.yaml",
    docker_network=net_cfg.dockerNetwork,
    depends_on=[docker_net, kind_cfg_file],
    replace_triggers=[kind_yaml, net_cfg.dockerNetwork, cls_cfg.kind_image or ""],
)

pulumi.export("kubeconfig", pulumi.Output.secret(kubeconfig.stdout))
pulumi.export("dockerNetwork", network_obj["dockerNetwork"])
pulumi.export("clusterName", cls_info["name"])
