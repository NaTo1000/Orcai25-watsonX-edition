# NayDoeV1 VPS Orchestration

This repository includes a VPS-deployable control plane for:

- Coordinating every Orcai25 security component through one event pipeline
- Issuing tenant API keys and storing only their `scrypt` hashes
- Registering NayDoeV1 inside the Orcai25 registry
- Discovering public Hugging Face models owned by `NaTo10000`
- Producing safe copy/paste commands for model downloads and servers
- Starting allowlisted vLLM or llama.cpp processes without shell execution
- Creating declarative skills that cannot contain executable Python
- Running reproducible `lm-evaluation-harness` comparisons
- Submitting credential-backed PennyLane, IonQ, Rigetti, and IBM jobs
- Serving a dedicated website and versioned REST API

## Identity boundary

The bootstrap command issues NayDoeV1:

- Model number: `NDV1-ORCH-V1`
- A unique `NDV1-<date>-<entropy>` serial number
- Role: **Conductor of Orchestrated Symphonies**
- A SHA-256 registration attestation

This is a genuine identity in the local tenant registry. It is not an
assertion of government registration, legal certification, a public Hugging
Face repository, or recognition by IBM, IonQ, Rigetti, or Xanadu. The live
Hugging Face refresh changes `source_verified` only when the official Hub API
returns the exact repository.

No public `NaTo10000/NayDoeV1` record could be verified while this feature was
implemented. The service therefore starts with that source marked unverified
instead of inventing external provenance.

## Requirements

- Linux VPS
- Python 3.10 or newer
- Nginx and a valid TLS certificate
- A dedicated unprivileged service account
- Optional GPU drivers for local model servers
- Optional provider-issued credentials for cloud quantum hardware

## Install

The following assumes the repository is installed at `/opt/orcai25`.

```bash
sudo useradd --system --home /var/lib/orcai25 --shell /usr/sbin/nologin orcai
sudo install -d -o orcai -g orcai -m 0700 /var/lib/orcai25 /var/log/orcai25
sudo install -d -o root -g orcai -m 0750 /etc/orcai25/credentials

cd /opt/orcai25
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Optional measured benchmarks:

```bash
.venv/bin/pip install -r requirements-benchmark.txt
```

Optional local PennyLane, IBM, and Rigetti adapters:

```bash
.venv/bin/pip install -r requirements-quantum.txt
```

IonQ uses its official HTTPS API directly and requires no additional package.

## Create the security secret

Do not put a secret in Git or in the example environment file.

```bash
sudo sh -c 'umask 077; openssl rand -hex 32 > /etc/orcai25/credentials/security-secret'
sudo chown root:orcai /etc/orcai25/credentials/security-secret
sudo chmod 0640 /etc/orcai25/credentials/security-secret
```

## Configure the service

```bash
sudo cp deploy/orchestrator.env.example /etc/orcai25/orchestrator.env
sudo chown root:orcai /etc/orcai25/orchestrator.env
sudo chmod 0640 /etc/orcai25/orchestrator.env
sudo editor /etc/orcai25/orchestrator.env
```

At minimum, replace `naydoev1.example.com` with the real domain in:

- `/etc/orcai25/orchestrator.env`
- `deploy/nginx-naydoev1.conf`

## Bootstrap NayDoeV1 and issue the first API key

Run this once as the service account:

```bash
sudo -u orcai \
  ORCAI_DATABASE_PATH=/var/lib/orcai25/orchestration.db \
  ORCAI_RUNTIME_DIRECTORY=/var/lib/orcai25/runtime \
  ORCAI_SECURITY_SECRET_FILE=/etc/orcai25/credentials/security-secret \
  /opt/orcai25/.venv/bin/python -m orchestration init \
  --tenant-name "NayDoeV1 Operations" \
  --tenant-slug naydoev1
```

The command prints:

1. The platform model number
2. The unique serial number
3. The registration hash
4. A key beginning with `orc_live_`

Copy the API key immediately into a password manager. The plaintext value is
not stored and cannot be recovered. Create a replacement key when needed:

```bash
sudo -u orcai \
  ORCAI_DATABASE_PATH=/var/lib/orcai25/orchestration.db \
  /opt/orcai25/.venv/bin/python -m orchestration create-key \
  --tenant-slug naydoev1 \
  --name automation \
  --scopes read,skills,benchmark
```

## Start systemd

```bash
sudo cp deploy/orcai-orchestrator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orcai-orchestrator
sudo systemctl status orcai-orchestrator
curl --fail http://127.0.0.1:8080/healthz
```

The service binds to loopback. Nginx is the public TLS boundary.

## Configure Nginx

Obtain a certificate for the real domain, update the example paths, then:

```bash
sudo cp deploy/nginx-naydoev1.conf /etc/nginx/sites-available/naydoev1
sudo ln -s /etc/nginx/sites-available/naydoev1 /etc/nginx/sites-enabled/naydoev1
sudo nginx -t
sudo systemctl reload nginx
```

Visit `https://<domain>/`. Paste the API key into the zero-trust entry panel.
The key is retained only in that tab's `sessionStorage`.

## Hugging Face model menu

The website's **Refresh NaTo10000** action requests:

```text
https://huggingface.co/api/models?author=NaTo10000&limit=100
```

Only valid repositories whose returned owner exactly matches `NaTo10000` are
registered. Each model card exposes copy/paste commands for:

- `hf download`
- `vllm serve`
- `llama-server`
- `lm_eval`

The backend never passes these display strings to a shell. Process control
uses fixed argument arrays and supports only `vllm` and `llama-server`.

## Skills creator

Skills are data records containing:

- Name and description
- A system prompt
- An allowlist of model IDs

Skills cannot upload or execute source code. Prompt-injection controls inspect
the prompt before registration. This keeps the skills creator useful without
turning it into remote code execution.

## Real model benchmarks

The benchmark service uses EleutherAI's `lm-evaluation-harness` and allows:

- ARC Challenge
- GSM8K
- HellaSwag
- MMLU
- TruthfulQA MC2
- WinoGrande

For every execution it stores:

- Exact command arguments
- Model repository and revision
- Harness version
- Selected tasks
- Host/Python/GPU metadata
- Raw result JSON
- SHA-256 of the result evidence

If `lm_eval` is missing or fails, the database records that state and does not
create a score. NayDoeV1 therefore has no claimed benchmark result until a real
run completes. Run identical tasks and limits for NayDoeV1 and comparison
models before comparing their metrics.

## Quantum providers

### PennyLane

`pennylane` uses the local `default.qubit` simulator. It requires no cloud
credential:

```bash
.venv/bin/pip install -r requirements-quantum.txt
```

### IonQ

Place the provider-issued key in a root-owned file:

```bash
sudo sh -c 'umask 077; cat > /etc/orcai25/credentials/ionq-api-key'
sudo chown root:orcai /etc/orcai25/credentials/ionq-api-key
sudo chmod 0640 /etc/orcai25/credentials/ionq-api-key
```

The service reads the file named by `IONQ_API_KEY_FILE`. Simulator or hardware
availability and charges come from the IonQ account. Hardware target names
must be explicitly allowlisted in `ORCAI_IONQ_HARDWARE_TARGETS`.

### Rigetti

The simulator path uses the local QVM/quilc services through `pyquil`.
Rigetti QPU access requires the provider's QCS settings file, a reservation,
and the exact current target from that account:

```text
QCS_SETTINGS_FILE_PATH=/etc/orcai25/credentials/qcs-settings.toml
ORCAI_RIGETTI_QPU_TARGET=<provider-listed-target>
```

The service does not hardcode a historical Rigetti QPU name.

### IBM Nighthawk

Nighthawk is IBM's 120-qubit processor. Orcai25 does not grant or simulate an
IBM hardware entitlement. Configure it only after the target appears in the
authenticated IBM account:

```text
IBM_QUANTUM_API_KEY_FILE=/etc/orcai25/credentials/ibm-quantum-api-key
IBM_QUANTUM_CRN=<account-instance>
ORCAI_IBM_NIGHTHAWK_TARGET=<exact backend returned by IBM>
```

No backend alias is enabled by default. The claimed free Nighthawk pipeline
could not be independently verified; request IBM account or partner evidence
before enabling it. PennyLane local simulation remains available without
hardware access.

All hardware submissions require `confirm_hardware: true`. The service never
silently falls back from requested paid hardware to a simulator.

## API examples

Use a key from a password manager; do not write it into scripts committed to
Git:

```bash
export ORCAI_API_KEY='<key shown by bootstrap>'

curl --fail \
  -H "X-API-Key: ${ORCAI_API_KEY}" \
  https://naydoev1.example.com/api/v1/models
```

Submit a local Bell-state circuit:

```bash
curl --fail -X POST \
  -H "X-API-Key: ${ORCAI_API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{
    "provider": "pennylane",
    "backend_mode": "simulator",
    "shots": 1024,
    "confirm_hardware": false,
    "circuit": {
      "qubits": 2,
      "gates": [
        {"gate": "h", "target": 0},
        {"gate": "cnot", "control": 0, "target": 1}
      ]
    }
  }' \
  https://naydoev1.example.com/api/v1/quantum/jobs
```

Interactive endpoint documentation is available at `/api/docs`.

## Security operations

- Permit public inbound traffic only to Nginx ports 80/443.
- Keep port 8080 bound to loopback.
- Store provider credentials in mode-0640 or stricter files.
- Back up `/var/lib/orcai25/orchestration.db`.
- Rotate API keys and revoke old keys through `/api/v1/auth/keys`.
- Review `/api/v1/events` and system logs.
- Treat model files as untrusted artifacts.
- Run model processes under the dedicated service account.
- Do not expose QVM, quilc, vLLM, or llama.cpp ports directly to the internet.

The repository still contains explicitly simulated educational cryptography in
its legacy core. Nginx TLS and provider SDK TLS—not those placeholders—protect
the deployed HTTP and cloud-provider connections.
