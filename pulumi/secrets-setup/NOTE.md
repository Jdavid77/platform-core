## Generate the age keypair

```bash
age-keygen -o ~/.config/sops/age/platform-services.txt
```

This writes the private key file (used below) and prints the public key — put the public key in `platform-services/.sops.yaml`'s `age:` field so SOPS encrypts secrets to it.

## Get the key into Bitwarden

Don't hand-type the age private key into `sops_secrets.json` — it's multi-line (comments + the `AGE-SECRET-KEY-...` line) and manually escaping newlines in a JSON string is error-prone. Build the file with `jq --rawfile` instead, which handles escaping for you:

```bash
jq -n --rawfile key ~/.config/sops/age/platform-services.txt '{
  type: 1,
  name: "SOPS Age Key Platform Services",
  notes: "SOPS age private key used to decrypt platform-services secrets",
  fields: [{name: "private-key", value: $key, type: 0}],
  login: {uris: [], username: null, password: null, totp: null, passwordRevisionDate: null}
}' > sops_secrets.json
```

Then run `./inject_secrets.sh` to push it into Bitwarden.
