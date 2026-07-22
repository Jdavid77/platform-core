from dataclasses import dataclass, field
from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import ReleaseArgs, Release
from pulumi import ResourceOptions
from pulumi_kubernetes import Provider


@dataclass
class FluxOperatorConfig:
    version: Optional[str] = None
    namespace: str = "flux-system"
    components: List[str] = field(default_factory=lambda: [
        "source-controller",
        "kustomize-controller",
        "helm-controller",
        "notification-controller"
    ])
    url: Optional[str] = None
    sourceName: Optional[str] = None


class FluxOperatorManager:

    def __init__(
        self,
        config: FluxOperatorConfig,
        stack_name: str,
        provider: Optional[k8s.Provider] = None,
    ):
        self.config = config
        self.stack_name = stack_name
        self.provider = provider

    def install_operator(self) -> Release:
        deps = [self.provider] if self.provider else []
        return Release(
            "flux-operator",
            ReleaseArgs(
                chart="oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator",
                namespace=self.config.namespace,
                create_namespace=True,
                values={
                    "serviceMonitor": {"create": False},
                    "web": {
                        "networkPolicy": {"create": False},
                        "httpRoute": {"enabled": False},
                    },
                },
            ),
            opts=ResourceOptions(provider=self.provider, depends_on=deps, retain_on_delete=True),
        )

    def install_instance(self, operator: Release) -> k8s.apiextensions.CustomResource:

        sync = (
            {
                "url": self.config.url,
                "kind": "GitRepository",
                "ref": "refs/heads/main",
                "interval": "30m",
                "name": self.config.sourceName,
                "path": f"clusters/{self.stack_name}"

            }
            if self.config.url
            else None
        )
        spec: dict = {
            "distribution": {
                "version": self.config.version,
                "registry": "ghcr.io/fluxcd",
            },
            "components": self.config.components,
        }
        if sync:
            spec["sync"] = sync

        return k8s.apiextensions.CustomResource(
            "flux-instance",
            api_version="fluxcd.controlplane.io/v1",
            kind="FluxInstance",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="flux",
                namespace=self.config.namespace,
            ),
            spec=spec,
            opts=ResourceOptions(provider=self.provider, depends_on=[operator], retain_on_delete=True),
        )

    def install(self):
        operator = self.install_operator()
        return operator, self.install_instance(operator)
