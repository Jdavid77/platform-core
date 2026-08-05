"""A Python Pulumi program"""

import pulumi
from modules import network, cluster, flux

# Config

config = pulumi.Config()
network_obj = config.require_object("network")
cls_info = config.require_object("cluster-info")

# Shared Stack

shared = pulumi.StackReference("Jdavid77/pulumi-shared/shared")
issuer_url = shared.get_output("auth0_issuer_url")
client_id = shared.get_output(f"auth0_client_id_{pulumi.get_stack()}")
groups_claim = shared.get_output("oidc_groups_claim")

# Network

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

docker_net = network.ensure_docker_network(net_cfg)


# OIDC

oidc_cfg = cluster.OidcConfig(
    issuer_url=issuer_url,
    client_id=client_id,
    groups_claim=groups_claim,
)

# Cluster

cls_cfg = cluster.ClusterConfig(
    name=cls_info["name"],
    kind_image=cls_info.get("kind-image"),
    wait_seconds=cls_info.get("wait-seconds"),
    oidc=oidc_cfg,
)

cluster_manager = cluster.ClusterManager(
    config=cls_cfg,
    net=net_cfg,
    depends_on=[docker_net],
)

cluster_cmd, kind_yaml = cluster_manager.create()
kubeconfig = cluster_manager.get_kubeconfig(cluster_cmd)
k8s = cluster_manager.get_provider(kubeconfig)

# Flux (age_private_key is the SOPS key used to decrypt secrets in platform-services;
# Flux won't start syncing until that Secret exists in-cluster)
sops_cfg = pulumi.Config("sops")
flux_obj = config.require_object("flux")
flux_manager = flux.FluxOperatorManager(
    config=flux.FluxOperatorConfig(
        version=flux_obj.get("version"),
        url=flux_obj.get("url"),
        sourceName=pulumi.get_stack(),
    ),
    stack_name=pulumi.get_stack(),
    provider=k8s,
    age_private_key=sops_cfg.require_secret("agePrivateKey"),
)
operator, instance = flux_manager.install()

# Outputs
pulumi.export("kubeconfig", pulumi.Output.secret(kubeconfig.stdout))
pulumi.export("dockerNetwork", network_obj["dockerNetwork"])
pulumi.export("clusterName", cls_info["name"])
pulumi.export("kindConfig", pulumi.Output.concat(kind_yaml))
