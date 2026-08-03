## Known issue: moving machines breaks `pulumi refresh`

`local.Command` has no `read` and only re-runs on `triggers` changes, so switching machines
leaves Pulumi believing the (now nonexistent) kind cluster/network still exist.

## Fix

Don't `pulumi destroy` — its delete commands fail against resources that never existed here.
Drop the stale resources from state and recreate instead:

```bash
pulumi state delete 'urn:pulumi:<stack>::platform-core::command:local:Command::docker:net' \
  --target-dependents --stack <stack>
pulumi up --stack <stack>
```

Repeat for each stack (`platform-sandbox`, `app-dev`).
