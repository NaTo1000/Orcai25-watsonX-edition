# Container Delivery and Rollback

## Trust Model

`ci.yml` has read-only repository permissions. Image publication and rollback
are separate manual or release-triggered workflows with `packages: write`.
Both production workflows target the GitHub `production` environment.

Workflow files cannot configure environment reviewers or branch protection.
A repository administrator must complete the settings below before relying on
the approval gates.

## Required GitHub Settings

1. In **Settings → Environments**, create `production`.
2. Add required reviewers from the release or operations team.
3. Prevent self-review when the repository plan and organization policy
   support it.
4. Restrict deployment branches and tags to the protected release policy.
5. Protect the default branch and require:
   - all `CI` jobs;
   - CODEOWNERS review;
   - conversation resolution; and
   - no direct or force pushes.
6. Confirm Actions can write the repository's GHCR package while ordinary
   workflows and contributors cannot.

Without required reviewers on `production`, the workflow `environment` field
records a deployment but does not create a human approval gate.

## Continuous Integration

`.github/workflows/ci.yml` runs on pushes and pull requests:

- Python 3.10, 3.12, and 3.14 dependency installation;
- bytecode compilation;
- unit tests;
- CLI health execution;
- Docker build;
- hardened container execution; and
- runtime UID verification.

All external actions are pinned to immutable commit SHAs.

## Publishing

`.github/workflows/release-image.yml` runs for a published GitHub release or by
manual dispatch with an existing semantic-version tag. Manual publishing checks
out that tag rather than labeling the selected branch head as a release.

After `production` approval, it:

1. validates the semantic version;
2. builds a loadable `linux/amd64` Docker archive and checksum;
3. preserves the current `stable` manifest as `rollback-<run-id>` when stable
   will move;
4. publishes a `linux/amd64` and `linux/arm64` GHCR image;
5. attaches SBOM and provenance attestations to the registry image; and
6. attaches the standalone files to a GitHub release when release-triggered;
   and
7. verifies and records the published digest.

Image tags:

- `<version>` identifies the release;
- `sha-<full-commit>` identifies source immutably; and
- `stable` points to the approved current release.

A non-prerelease GitHub release promotes `stable`. Manual dispatch requires an
existing tag and only promotes it when `promote_stable` is selected.

## Standalone Distribution

Download the files from the GitHub release, or use the
`orcai25-<version>-linux-amd64-docker` workflow artifact, then:

```bash
sha256sum --check orcai25-<version>-linux-amd64.docker.tar.sha256
docker image load --input orcai25-<version>-linux-amd64.docker.tar
```

The workflow artifact is retained for 30 days unless repository policy
overrides or removes it. Release-triggered files are also attached to the
GitHub release. Copy approved assets to the organization's distribution store
when a separate retention policy is required.

## Rollback

Rollback changes the GHCR `stable` pointer. It does not automatically restart
or redeploy downstream workloads.

1. Identify a known-good `sha256:<digest>` from a release summary. Version and
   `sha-<commit>` tags are accepted for convenience, but a digest is the
   authoritative production rollback target.
2. Open **Actions → Roll back stable container image → Run workflow**.
3. Enter the target and type `ROLLBACK`.
4. A required reviewer approves the `production` environment deployment.
5. The workflow resolves the immutable target digest.
6. If needed, it preserves the current stable manifest as
   `rollback-backup-<run-id>`.
7. It promotes the target digest to `stable`, verifies the resulting digest,
   and writes both digests to the workflow summary.
8. Redeploy downstream systems using the verified digest and monitor them.

If the selected target already equals `stable`, the workflow verifies and
records the no-op. To reverse a rollback, run the same workflow with the
preserved backup digest or release tag.

## Rollback Verification

Before closing the change:

- confirm GHCR `stable` resolves to the workflow's restored digest;
- confirm each deployment references or has pulled that digest;
- run workload-specific health and smoke checks;
- verify alerts and error rates; and
- retain the workflow run URL in the incident or change record.

Application data and schema rollback are outside this workflow because the
current image has no database. Add reversible migration controls before
introducing persistent schemas.
