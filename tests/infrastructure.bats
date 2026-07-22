#!/usr/bin/env bats
# Infrastructure validation tests.
# Prerequisites: KUBECONFIG, DOCKER_NETWORK, PULUMI_STACK exported by the CI

@test "docker network exists" {
  run docker network inspect "$DOCKER_NETWORK"
  [ "$status" -eq 0 ]
}

@test "kubernetes cluster is accessible" {
  run kubectl get nodes --no-headers
  [ "$status" -eq 0 ]
  node_count=$(echo "$output" | wc -l)
  [ "$node_count" -ge 1 ]
}

@test "flux is healthy" {
  run flux check --pre
  [ "$status" -eq 0 ]
}
