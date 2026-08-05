from dataclasses import dataclass, field
from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import ReleaseArgs, Release
from pulumi import Input, ResourceOptions


@dataclass
class FluxOperatorConfig:
    version: Optional[str] = None
    namespace: str = "flux-system"
    components: List[str] = field(
        default_factory=lambda: [
            "source-controller",
            "kustomize-controller",
            "helm-controller",
            "notification-controller",
        ]
    )
    url: Optional[str] = None
    sourceName: Optional[str] = None


class FluxOperatorManager:

    def __init__(
        self,
        config: FluxOperatorConfig,
        stack_name: str,
        provider: Optional[k8s.Provider] = None,
        age_private_key: Optional[Input[str]] = None,
    ):
        self.config = config
        self.stack_name = stack_name
        self.provider = provider
        self.age_private_key = age_private_key

    def _install_operator(self) -> Release:
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
            opts=ResourceOptions(
                provider=self.provider, depends_on=deps, retain_on_delete=True
            ),
        )

    def _install_age_secret(
        self, operator: Release, age_private_key: Input[str]
    ) -> k8s.core.v1.Secret:
        return k8s.core.v1.Secret(
            "sops-age",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="sops-age",
                namespace=self.config.namespace,
            ),
            string_data={"age.agekey": age_private_key},
            opts=ResourceOptions(
                provider=self.provider, depends_on=[operator], retain_on_delete=True
            ),
        )

    def _install_instance(
        self, operator: Release, depends_on: Optional[List] = None
    ) -> k8s.apiextensions.CustomResource:

        sync = (
            {
                "url": self.config.url,
                "kind": "GitRepository",
                "ref": "refs/heads/main",
                "interval": "30m",
                "name": self.config.sourceName,
                "path": f"clusters/{self.stack_name}",
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
            opts=ResourceOptions(
                provider=self.provider,
                depends_on=[operator, *(depends_on or [])],
                retain_on_delete=True,
            ),
        )

    def install(self) -> tuple[Release, k8s.apiextensions.CustomResource]:
        operator = self._install_operator()

        instance_deps = []
        if self.age_private_key is not None:
            instance_deps.append(self._install_age_secret(operator, self.age_private_key))

        return operator, self._install_instance(operator, depends_on=instance_deps)
