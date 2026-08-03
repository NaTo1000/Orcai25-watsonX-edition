# Deployment Guide

Orcai25 currently runs as a one-shot command-line workload. It does not expose
an HTTP server or a long-running health endpoint.

## Requirements

- Python 3.10 or newer for local execution
- Docker 24 or newer for container execution
- An external key manager, immutable audit sink, TLS terminator, and monitoring
  integrations before production use

## Local Python

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --requirement requirements.txt

python orcai_security.py health
python orcai_security.py demo
python orcai_security.py compliance
python orcai_security.py all
```

Use an alternate configuration:

```bash
python orcai_security.py health --config /secure/path/security_config.json
```

The default configuration is resolved relative to `orcai_security.py`, not the
current working directory.

## Local Docker Image

Build the image:

```bash
docker build \
  --build-arg VERSION=local \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  --tag orcai25:local \
  .
```

Run the default health command with the same restrictions used by CI:

```bash
docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  orcai25:local
```

Run another command:

```bash
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges orcai25:local compliance
```

Mount a reviewed configuration file:

```bash
docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --mount type=bind,src=/secure/path/security_config.json,dst=/config.json,readonly \
  orcai25:local health --config /config.json
```

The image runs as UID/GID `10001:10001`, writes no application state, and has
no runtime package manager operation.

## Docker Compose

`compose.yaml` applies the non-root, read-only, capability-free local profile:

```bash
docker compose build
docker compose run --rm orcai
```

## Published Image

Approved releases publish multi-architecture images to:

```text
ghcr.io/nato1000/orcai25-watsonx-edition
```

Pin production consumption to the digest recorded in the release workflow
summary:

```bash
docker pull ghcr.io/nato1000/orcai25-watsonx-edition@sha256:<digest>
```

The mutable `stable` tag is an operator convenience and rollback pointer. Do
not use it where immutable deployment references are required.

## Standalone Distribution Archive

Each release uploads a `linux/amd64` Docker archive and SHA-256 checksum that do
not require registry access after download:

```bash
sha256sum --check orcai25-<version>-linux-amd64.docker.tar.sha256
docker image load --input orcai25-<version>-linux-amd64.docker.tar
```

The registry image remains the source for `linux/arm64` distribution.

## Health and Compliance Commands

The CLI exit code is the machine-readable result:

- `health` returns nonzero when the overall health result is not healthy.
- `compliance` returns nonzero when an implemented control check reports a
  violation.
- `all` runs the demonstration, health checks, and control checks.

These checks describe this process and configuration only. They are not an
external service readiness probe or compliance certification.

## Production Integration Requirements

Before embedding the library or wrapping it in a service:

1. provision root secrets and private key bundles through an HSM, KMS, or Vault;
2. persist audit, monitoring, and containment state in approved stores;
3. authenticate peer public keys and enforce authorization policy;
4. terminate TLS 1.3 and configure certificate lifecycle management;
5. add network policy, rate limiting, workload identity, and egress controls;
6. connect logs, metrics, alerts, and traces to operational systems; and
7. complete the repository's production checklist and independent review.

Do not deploy the current one-shot image as a Kubernetes `Service`; it has no
listener. Add and test an explicit service interface before creating service,
ingress, autoscaling, or availability manifests.

## Release and Rollback

Repository approvals, image publication, standalone artifacts, and rollback
are documented in [`DELIVERY.md`](DELIVERY.md).
