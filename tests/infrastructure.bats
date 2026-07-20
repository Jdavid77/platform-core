setup_file() {
    # Run once before all tests
    pulumi stack output kubeconfig --show-secrets --stack "$PULUMI_STACK" > kubeconfig.yaml
    export KUBECONFIG="$PWD/kubeconfig.yaml"
    export DOCKER_NETWORK=$(pulumi stack output dockerNetwork --stack "$PULUMI_STACK")
    export CLUSTER_NAME=$(pulumi stack output clusterName --stack "$PULUMI_STACK")
}

teardown_file() {
  # Cleanup after all tests
  rm -f kubeconfig.yaml
}

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
