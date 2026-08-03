# Orcai25 WatsonX Edition - Implementation Summary

## Status

Orcai25 is an executable security reference stack. It demonstrates zero-trust
request checks, post-quantum cryptography, AI behavior rules, containment,
audit-chain integrity, compliance control checks, and monitoring.

It is **not** a compliance certification or a complete production security
platform. Production use still requires persistent storage, external key
management, authenticated transport TLS, operational integrations, and an
independent security review. Track those items in
[`PRODUCTION_CHECKLIST.md`](PRODUCTION_CHECKLIST.md).

## Implemented Components

| Component | Path | Current implementation |
| --- | --- | --- |
| Zero trust | `core/zero_trust_architecture.py` | HMAC session tokens, MFA gates, behavior score checks, and deny-by-default resource checks |
| Post-quantum crypto | `core/quantum_resistant_crypto.py` | FIPS 203 ML-KEM-1024, FIPS 204 ML-DSA-87, AES-256-GCM, and HKDF-SHA3-512 via `cryptography` |
| AI threat rules | `core/ai_threat_detection.py` | Deterministic indicators for adversarial input, exfiltration, escalation, resource abuse, poisoning, and prompt injection |
| Secure envelope | `core/secure_communication.py` | X25519, AES-256-GCM or ChaCha20-Poly1305, channel binding, freshness checks, and replay rejection |
| AI containment | `emergency_protocols/rogue_ai_containment.py` | Five response levels, containment state, kill-switch callbacks, and circuit breaking |
| Audit and controls | `audit/compliance_framework.py` | HMAC-linked in-memory audit entries and executable control checks |
| Monitoring | `monitoring/security_monitor.py` | In-memory baselines, anomaly alerts, event correlation, and health checks |

The secure envelope is application-level encryption. It does not implement a
TLS listener, certificate validation, or peer identity provisioning.

## Dependencies

Runtime dependencies are pinned in `requirements.txt`:

- `cryptography`
- `cffi`
- `pycparser`

Dependabot monitors Python packages, the Docker base image, and GitHub Actions.
GitHub Actions are pinned to full commit SHAs.

## Container Delivery

- `Dockerfile` builds a two-stage, non-root image from a digest-pinned Python
  base.
- `compose.yaml` runs the health command with no network, a read-only root
  filesystem, no Linux capabilities, and `no-new-privileges`.
- `.github/workflows/ci.yml` tests Python 3.10, 3.12, and 3.14, then builds and
  executes the hardened image.
- `.github/workflows/release-image.yml` publishes `linux/amd64` and
  `linux/arm64` images with SBOM and provenance attestations after approval.
- Every release also produces a checksummed, loadable `linux/amd64` Docker
  archive.
- `.github/workflows/rollback-image.yml` preserves the current stable digest
  and atomically promotes an approved prior digest.

See [`docs/DELIVERY.md`](docs/DELIVERY.md) for required GitHub environment
settings, release operations, and rollback instructions.

## Validation

```bash
python -m pip install --requirement requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q orcai_security.py core audit emergency_protocols monitoring tests
python orcai_security.py health
docker build -t orcai25:local .
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges orcai25:local
```

## Known Operational Gaps

- Runtime keys and state remain process-local.
- Audit entries, alerts, metrics, baselines, and containment state are not
  persisted.
- Transport TLS, certificates, peer-key authentication, rate limiting, and
  network policy must be supplied by the deployment.
- Compliance checks confirm configured booleans; they do not prove regulatory
  compliance.
- Threat and anomaly detection are rule-based reference logic, not validated
  machine-learning models.
- The image is a one-shot CLI workload, not an HTTP service.
