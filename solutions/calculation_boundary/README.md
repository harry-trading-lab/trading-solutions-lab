# Calculation boundary: what the demonstration protects

The executable HTTP permission matrix demonstrates application-level access:

| Credential | Gateway static fixture | Gateway restricted calculation | Engine directly |
|---|---|---|---|
| None | 401 | 401 | 401 |
| Developer | 200 | 403 | 401 |
| Application | 200 | 200 | 401 |
| Gateway service | 401 | 401 | 200 |

`engine/server.py` and `gateway/server.py` run independently. The gateway imports
no engine module and can be packaged without engine code. The model in this public
repository is intentionally not secret. The fixture always returns a fixed example;
it does not execute or predict proprietary calculations.

Run from the repository root:

```sh
python -m unittest test_demand_solutions.TestCalculationBoundary -v
python run_demand_solutions.py --no-images --output /tmp/boundary-evidence
```

The request contract is a JSON object containing **only** `principal_cents`
(integer 0..1e12), `annual_rate_bps` (integer 0..5000) and `years` (integer 0..50).
Engine responses contain `future_value_cents` and `model`. Invalid schema yields
400, payloads over 4096 bytes yield 413, unauthorized callers receive 401/403, and
engine failures yield 502 at the gateway. The public placeholder uses annual
compounding; it is not a financial recommendation or a full planning model.

## Deployment design, not a deployment claim

For an actual private model, use **separate repositories/build artifacts**, identities
and infrastructure permissions. The developer gets the gateway integration schema,
fixture server and test data only. The production gateway is operated by a restricted
service identity; ordinary developers must not have its service token, runtime shell,
logs containing secrets, or unrestricted deployment rights. Merely placing two folders
in a repository does not protect source code. Process separation on the same OS user
is not an OS security boundary; the local harness demonstrates HTTP checks only.

Production also needs a maintained application server, TLS, network policy, identity
lifecycle/token rotation, rate limits, input/output review, monitoring, access-reviewed
backups and recovery, and audit storage with retention/tamper controls. This stdlib
HTTP server and shared-token example are for local reproducible demonstration.
The private endpoint is loopback-only by default, but loopback is not authentication.

An authorized query caller may infer properties of a model through outputs. API access
control does not make black-box extraction impossible. Define who may query, which
inputs/outputs are necessary, quotas, and what may be disclosed. Public artifacts
must not contain real client models, credentials, identifying inputs or account data.
