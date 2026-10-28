# Reference architecture: aml-triage at Bayside Community Bank (M10-L08)

Synthetic organization, fictional hosts. This is a pattern to adapt, not a turnkey deployment.

```
 caller ──> authenticating gateway ──> agent container (no internet route; read-only; non-root; no secrets)
                                         │  internal network only
                       ┌─────────────────┴──────────────────┐
                 model-gateway                         egress-proxy
          (IAM role; signs; PrivateLink)        (allowlist; injects 15-min token; logs)
                       │                                    │
          Amazon Bedrock, us.* profile          core-banking.bayside.example
```

| File | What it shows |
|---|---|
| `Dockerfile` | Non-root user, no secrets baked in, deploy by digest |
| `compose.yaml` | Agent on an `internal: true` network; the only exits are the gateway and the proxy; hardened container flags |
| `egress-proxy/squid.conf` | Allowlist for tool traffic, `deny all` last, every request logged |

The agent holds no credentials: the gateway signs model requests with the task's IAM role, and the proxy adds a
short-lived, scoped token to tool requests. Retention (WORM audit storage, transcript sweep) and identity are declared
in `src/sentinel/deploy/policies/deployment.yaml`.

```bash
uv run python -m sentinel.deploy reference deploy/reference --agent aml-triage   # static checks (REF-001..013)
uv run python -m sentinel.deploy preflight                                         # the whole fleet
```

Before relying on this pattern, confirm with AWS and your bank's third-party risk team: PrivateLink for Bedrock in
your region, the inference profiles you allow, model availability, and the agreements in place.
