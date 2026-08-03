# Production Readiness Checklist

This repository is a reference implementation. Completing this checklist does
not replace architecture, security, legal, privacy, or compliance review.

## Implemented in This Repository

- [x] ML-KEM-1024 key encapsulation through a maintained cryptographic library
- [x] ML-DSA-87 signatures through a maintained cryptographic library
- [x] AES-256-GCM and ChaCha20-Poly1305 authenticated encryption
- [x] Unit tests for key encapsulation, signatures, encryption, tamper
  detection, replay rejection, and audit-chain integrity
- [x] Pinned Python dependencies with automated update checks
- [x] Digest-pinned, non-root, multi-stage Docker image
- [x] Hardened local Compose execution
- [x] Python and container CI
- [x] Approved multi-architecture image publishing to GHCR
- [x] SBOM and provenance generation for registry images
- [x] Checksummed standalone Docker archive
- [x] Approved rollback of the `stable` image pointer with a backup tag

## Repository and Delivery Controls

These settings cannot be created by workflow files and must be configured by a
repository administrator:

- [ ] Create the GitHub `production` environment
- [ ] Require designated reviewers for `production`
- [ ] Prevent self-review where organization policy supports it
- [ ] Restrict production deployments to protected tags or branches
- [ ] Require all CI jobs and CODEOWNERS review before merge
- [ ] Prevent direct pushes and force-pushes to the default branch
- [ ] Confirm GHCR package write access is limited to the release workflows
- [ ] Define image and artifact retention policies
- [ ] Test one release and one rollback in a non-production package

See [`docs/DELIVERY.md`](docs/DELIVERY.md) for the exact workflow and rollback
contract.

## Key and Secret Management

- [ ] Replace process-local root secrets with an HSM, cloud KMS, or Vault
- [ ] Define key ownership, access policy, rotation, revocation, and recovery
- [ ] Store ML-KEM and ML-DSA private bundles only in approved secret storage
- [ ] Add key identifiers and versions to encrypted packages
- [ ] Test rotation and rollback without reusing compromised key material
- [ ] Record all key-management operations in an immutable audit sink

## Persistence and Recovery

- [ ] Persist audit entries in immutable, append-only storage
- [ ] Persist sessions, alerts, baselines, and containment state as required
- [ ] Define backup scope, encryption, retention, and restore objectives
- [ ] Exercise restore procedures and verify cryptographic integrity
- [ ] Make schema and data migrations reversible before adding a database
- [ ] Document regional or availability-zone recovery requirements

## Transport and Identity

- [ ] Terminate TLS 1.3 with a supported proxy, gateway, or service mesh
- [ ] Automate certificate issuance, renewal, revocation, and expiry alerts
- [ ] Authenticate and authorize peer X25519 public keys before channel setup
- [ ] Add workload identity and mutual TLS where required
- [ ] Configure network policy, egress restrictions, firewall rules, and rate
  limits
- [ ] Perform protocol interoperability and downgrade-resistance testing

## Observability and Response

- [ ] Replace stdout-only notifications with approved paging and ticketing
- [ ] Forward audit and security events to a SIEM
- [ ] Export service metrics without sensitive payloads or key material
- [ ] Define alert ownership, severity, deduplication, and escalation
- [ ] Test kill-switch callbacks against real managed workloads
- [ ] Run incident-response, rollback, and disaster-recovery exercises

## Security and Compliance Validation

- [ ] Perform threat modeling for the actual deployment and data flows
- [ ] Complete independent cryptographic and application security review
- [ ] Run SAST, dependency, container, and infrastructure scanning in the
  organization-approved toolchain
- [ ] Perform penetration and abuse-case testing
- [ ] Validate threat-rule accuracy and false-positive handling
- [ ] Map controls to evidence with qualified compliance professionals
- [ ] Complete privacy impact and data-retention reviews
- [ ] Obtain required regulatory or contractual approvals

## Go-Live Gate

Production promotion should be blocked until:

1. all applicable items above have owners and evidence;
2. unresolved risks have explicit acceptance;
3. release and rollback have both been rehearsed;
4. monitoring confirms the promoted digest is running; and
5. the prior known-good digest remains available for roll-forward.
