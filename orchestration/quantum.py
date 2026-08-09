"""Credential-backed adapters for quantum simulators and cloud providers."""

import importlib.util
import json
import math
import os
import threading
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from orchestration.database import OrchestrationDatabase


SUPPORTED_GATES = {
    "cnot",
    "cz",
    "h",
    "rx",
    "ry",
    "rz",
    "s",
    "t",
    "x",
    "y",
    "z",
}


def provider_secret(name: str) -> Optional[str]:
    """Read a provider credential from an environment variable or file."""
    secret_file = os.environ.get(f"{name}_FILE")
    if secret_file:
        try:
            with open(secret_file, encoding="utf-8") as handle:
                value = handle.read(4097)
        except OSError as exc:
            raise RuntimeError(f"Could not read {name}_FILE") from exc
        if len(value) > 4096:
            raise RuntimeError(f"{name}_FILE exceeds the size limit")
        return value.strip() or None
    return os.environ.get(name)


def validate_circuit(circuit: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the provider-neutral circuit representation."""
    if not isinstance(circuit, dict):
        raise ValueError("Circuit must be an object")
    qubits = circuit.get("qubits")
    gates = circuit.get("gates")
    if not isinstance(qubits, int) or not 1 <= qubits <= 120:
        raise ValueError("Circuit qubits must be between 1 and 120")
    if not isinstance(gates, list) or not 1 <= len(gates) <= 10000:
        raise ValueError("Circuit must contain between 1 and 10000 gates")

    normalized = []
    for gate in gates:
        if not isinstance(gate, dict):
            raise ValueError("Each gate must be an object")
        name = str(gate.get("gate", "")).lower()
        if name not in SUPPORTED_GATES:
            raise ValueError(f"Unsupported gate: {name}")
        target = gate.get("target")
        if not isinstance(target, int) or not 0 <= target < qubits:
            raise ValueError("Gate target is outside the circuit")
        normalized_gate = {"gate": name, "target": target}
        if name in {"cnot", "cz"}:
            control = gate.get("control")
            if (
                not isinstance(control, int)
                or not 0 <= control < qubits
                or control == target
            ):
                raise ValueError("Controlled gate has an invalid control")
            normalized_gate["control"] = control
        if name in {"rx", "ry", "rz"}:
            angle = gate.get("angle")
            if (
                not isinstance(angle, (int, float))
                or not math.isfinite(float(angle))
            ):
                raise ValueError("Rotation gate requires a finite angle")
            normalized_gate["angle"] = float(angle)
        normalized.append(normalized_gate)
    return {"qubits": qubits, "gates": normalized}


class QuantumProviderManager:
    """Submit allowlisted circuits without storing provider credentials."""

    IONQ_API_URL = "https://api.ionq.co/v0.4"

    def __init__(
        self,
        database: OrchestrationDatabase,
        event_callback: Optional[Callable[[str, str, Dict], None]] = None,
        opener: Optional[Callable] = None,
    ):
        self.database = database
        self.event_callback = event_callback
        self._urlopen = opener or urlopen
        self._tenants: Dict[str, str] = {}

    def provider_status(self) -> List[Dict[str, Any]]:
        ibm_target = os.environ.get("ORCAI_IBM_NIGHTHAWK_TARGET")
        rigetti_target = os.environ.get("ORCAI_RIGETTI_QPU_TARGET")
        return [
            {
                "id": "ibm_nighthawk",
                "provider": "IBM Quantum",
                "display_name": "IBM Nighthawk (120 qubits)",
                "kind": "hardware",
                "sdk_installed": self._module_available(
                    "qiskit_ibm_runtime"
                ),
                "credentials_configured": bool(
                    provider_secret("IBM_QUANTUM_API_KEY")
                    or provider_secret("QISKIT_IBM_TOKEN")
                ),
                "target_configured": bool(ibm_target),
                "target": ibm_target,
                "access_note": (
                    "IBM-issued entitlement is required; free access is "
                    "not assumed or granted by Orcai25."
                ),
            },
            {
                "id": "ionq",
                "provider": "IonQ",
                "display_name": "IonQ Cloud",
                "kind": "simulator_and_hardware",
                "sdk_installed": True,
                "credentials_configured": bool(
                    provider_secret("IONQ_API_KEY")
                ),
                "target_configured": True,
                "target": "ionq.simulator",
                "access_note": (
                    "Simulator or hardware availability follows the "
                    "connected IonQ account."
                ),
            },
            {
                "id": "rigetti",
                "provider": "Rigetti QCS",
                "display_name": "Rigetti QCS / local QVM",
                "kind": "simulator_and_hardware",
                "sdk_installed": self._module_available("pyquil"),
                "credentials_configured": bool(
                    os.environ.get("QCS_SETTINGS_FILE_PATH")
                    or os.environ.get("QCS_CLIENT_CREDENTIALS_CLIENT_ID")
                ),
                "target_configured": bool(rigetti_target),
                "target": rigetti_target or "9q-square-qvm",
                "access_note": (
                    "Local QVM is free; QPU execution requires a Rigetti "
                    "reservation and credentials."
                ),
            },
            {
                "id": "pennylane",
                "provider": "PennyLane",
                "display_name": "PennyLane default.qubit",
                "kind": "local_simulator",
                "sdk_installed": self._module_available("pennylane"),
                "credentials_configured": True,
                "target_configured": True,
                "target": "default.qubit",
                "access_note": "Local simulator; no cloud credential required.",
            },
        ]

    @staticmethod
    def _module_available(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def submit(
        self,
        tenant_id: str,
        provider: str,
        backend_mode: str,
        target: Optional[str],
        circuit: Dict[str, Any],
        shots: int,
        confirm_hardware: bool,
    ) -> Dict[str, Any]:
        if provider not in {"ibm_nighthawk", "ionq", "rigetti", "pennylane"}:
            raise ValueError("Unsupported quantum provider")
        if backend_mode not in {"simulator", "hardware"}:
            raise ValueError("Quantum backend mode must be simulator or hardware")
        if not isinstance(shots, int) or not 1 <= shots <= 10000:
            raise ValueError("Shots must be between 1 and 10000")
        if backend_mode == "hardware" and not confirm_hardware:
            raise ValueError("Hardware jobs require explicit cost confirmation")

        normalized_circuit = validate_circuit(circuit)
        resolved_target = self._resolve_target(
            provider,
            backend_mode,
            target,
        )
        job = self.database.create_quantum_job(
            tenant_id,
            provider,
            backend_mode,
            resolved_target,
            normalized_circuit,
            shots,
        )
        self._tenants[job["id"]] = tenant_id
        self._emit(
            job["id"],
            "queued",
            {
                "provider": provider,
                "backend_mode": backend_mode,
                "target": resolved_target,
            },
        )
        threading.Thread(
            target=self._execute,
            args=(job,),
            daemon=True,
        ).start()
        return job

    def _resolve_target(
        self,
        provider: str,
        backend_mode: str,
        requested_target: Optional[str],
    ) -> str:
        if provider == "pennylane":
            if backend_mode != "simulator":
                raise ValueError("PennyLane adapter is limited to local simulation")
            return "default.qubit"

        if provider == "ibm_nighthawk":
            if backend_mode != "hardware":
                raise ValueError(
                    "Use PennyLane for local simulation; Nighthawk is hardware"
                )
            configured = os.environ.get("ORCAI_IBM_NIGHTHAWK_TARGET")
            if not configured:
                raise RuntimeError(
                    "ORCAI_IBM_NIGHTHAWK_TARGET is not configured"
                )
            if requested_target and requested_target != configured:
                raise ValueError("IBM target is not allowlisted")
            return configured

        if provider == "ionq":
            if backend_mode == "simulator":
                return "ionq.simulator"
            allowed = {
                value.strip()
                for value in os.environ.get(
                    "ORCAI_IONQ_HARDWARE_TARGETS",
                    "",
                ).split(",")
                if value.strip()
            }
            if not requested_target or requested_target not in allowed:
                raise ValueError("IonQ hardware target is not allowlisted")
            return requested_target

        if backend_mode == "simulator":
            return os.environ.get(
                "ORCAI_RIGETTI_QVM_TARGET",
                "9q-square-qvm",
            )
        configured = os.environ.get("ORCAI_RIGETTI_QPU_TARGET")
        if not configured:
            raise RuntimeError("ORCAI_RIGETTI_QPU_TARGET is not configured")
        if requested_target and requested_target != configured:
            raise ValueError("Rigetti target is not allowlisted")
        return configured

    def _execute(self, job: Dict[str, Any]):
        job_id = job["id"]
        try:
            provider = job["provider"]
            if provider == "pennylane":
                result = self._run_pennylane(job)
                self.database.update_quantum_job(
                    job_id,
                    "completed",
                    result=result,
                )
                self._emit(job_id, "completed", result)
            elif provider == "ionq":
                response = self._submit_ionq(job)
                self.database.update_quantum_job(
                    job_id,
                    "submitted",
                    provider_job_id=response["id"],
                    result={"provider_status": response.get("status")},
                )
                self._emit(
                    job_id,
                    "submitted",
                    {"provider_job_id": response["id"]},
                )
            elif provider == "ibm_nighthawk":
                provider_job_id = self._submit_ibm(job)
                self.database.update_quantum_job(
                    job_id,
                    "submitted",
                    provider_job_id=provider_job_id,
                )
                self._emit(
                    job_id,
                    "submitted",
                    {"provider_job_id": provider_job_id},
                )
            else:
                result = self._run_rigetti(job)
                self.database.update_quantum_job(
                    job_id,
                    "completed",
                    result=result,
                )
                self._emit(job_id, "completed", result)
        except Exception as exc:
            self.database.update_quantum_job(
                job_id,
                "failed",
                error=str(exc),
            )
            self._emit(job_id, "failed", {"error": str(exc)})

    def _run_pennylane(self, job: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import pennylane as qml
        except ImportError as exc:
            raise RuntimeError("PennyLane is not installed") from exc

        circuit = job["circuit"]
        device = qml.device(
            "default.qubit",
            wires=circuit["qubits"],
            shots=job["shots"],
        )

        @qml.qnode(device)
        def execute():
            self._apply_pennylane_gates(qml, circuit["gates"])
            return qml.counts(wires=range(circuit["qubits"]))

        counts = execute()
        return {
            "counts": {
                str(key): int(value)
                for key, value in dict(counts).items()
            }
        }

    @staticmethod
    def _apply_pennylane_gates(qml, gates: List[Dict[str, Any]]):
        single_gates = {
            "h": qml.Hadamard,
            "s": qml.S,
            "t": qml.T,
            "x": qml.PauliX,
            "y": qml.PauliY,
            "z": qml.PauliZ,
        }
        rotations = {"rx": qml.RX, "ry": qml.RY, "rz": qml.RZ}
        for gate in gates:
            name = gate["gate"]
            if name in single_gates:
                single_gates[name](wires=gate["target"])
            elif name in rotations:
                rotations[name](gate["angle"], wires=gate["target"])
            elif name == "cnot":
                qml.CNOT(wires=[gate["control"], gate["target"]])
            elif name == "cz":
                qml.CZ(wires=[gate["control"], gate["target"]])

    def _submit_ionq(self, job: Dict[str, Any]) -> Dict[str, Any]:
        api_key = provider_secret("IONQ_API_KEY")
        if not api_key:
            raise RuntimeError("IONQ_API_KEY is not configured")
        payload = {
            "name": f"orcai-{job['id'][:12]}",
            "backend": job["target"],
            "shots": job["shots"],
            "input": {
                "format": "ionq.circuit.v0",
                "qubits": job["circuit"]["qubits"],
                "circuit": self._ionq_gates(job["circuit"]["gates"]),
            },
        }
        request = Request(
            f"{self.IONQ_API_URL}/jobs",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"apiKey {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Orcai25-Orchestrator/1.0",
            },
            method="POST",
        )
        try:
            with self._urlopen(request, timeout=30) as response:
                body = response.read(1024 * 1024 + 1)
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"IonQ submission failed: {exc}") from exc
        if len(body) > 1024 * 1024:
            raise RuntimeError("IonQ response exceeded size limit")
        data = json.loads(body)
        if not isinstance(data, dict) or not data.get("id"):
            raise RuntimeError("IonQ returned an invalid job response")
        return data

    @staticmethod
    def _ionq_gates(gates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted = []
        for gate in gates:
            name = gate["gate"]
            item: Dict[str, Any] = {"gate": name}
            if name in {"cnot", "cz"}:
                item["controls"] = [gate["control"]]
                item["targets"] = [gate["target"]]
            else:
                item["target"] = gate["target"]
            if name in {"rx", "ry", "rz"}:
                item["rotation"] = gate["angle"] / (2 * math.pi)
            converted.append(item)
        return converted

    def _submit_ibm(self, job: Dict[str, Any]) -> str:
        try:
            from qiskit import QuantumCircuit, transpile
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        except ImportError as exc:
            raise RuntimeError(
                "qiskit and qiskit-ibm-runtime are not installed"
            ) from exc

        token = (
            provider_secret("IBM_QUANTUM_API_KEY")
            or provider_secret("QISKIT_IBM_TOKEN")
        )
        if not token:
            raise RuntimeError("IBM Quantum credential is not configured")
        kwargs = {
            "channel": os.environ.get(
                "IBM_QUANTUM_CHANNEL",
                "ibm_cloud",
            ),
            "token": token,
        }
        instance = os.environ.get("IBM_QUANTUM_CRN")
        if instance:
            kwargs["instance"] = instance
        service = QiskitRuntimeService(**kwargs)
        backend = service.backend(job["target"])
        circuit = QuantumCircuit(job["circuit"]["qubits"])
        self._apply_qiskit_gates(circuit, job["circuit"]["gates"])
        circuit.measure_all()
        compiled = transpile(circuit, backend)
        sampler = SamplerV2(mode=backend)
        submitted = sampler.run([compiled], shots=job["shots"])
        return submitted.job_id()

    @staticmethod
    def _apply_qiskit_gates(circuit, gates: List[Dict[str, Any]]):
        for gate in gates:
            name = gate["gate"]
            if name in {"h", "s", "t", "x", "y", "z"}:
                getattr(circuit, name)(gate["target"])
            elif name in {"rx", "ry", "rz"}:
                getattr(circuit, name)(gate["angle"], gate["target"])
            elif name in {"cnot", "cz"}:
                method = circuit.cx if name == "cnot" else circuit.cz
                method(gate["control"], gate["target"])

    def _run_rigetti(self, job: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from pyquil import Program, get_qc
            from pyquil.gates import CNOT, CZ, H, MEASURE, RX, RY, RZ, S, T, X, Y, Z
        except ImportError as exc:
            raise RuntimeError("pyquil is not installed") from exc

        gate_map = {"h": H, "s": S, "t": T, "x": X, "y": Y, "z": Z}
        rotation_map = {"rx": RX, "ry": RY, "rz": RZ}
        program = Program()
        readout = program.declare("ro", "BIT", job["circuit"]["qubits"])
        for gate in job["circuit"]["gates"]:
            name = gate["gate"]
            if name in gate_map:
                program += gate_map[name](gate["target"])
            elif name in rotation_map:
                program += rotation_map[name](
                    gate["angle"],
                    gate["target"],
                )
            elif name == "cnot":
                program += CNOT(gate["control"], gate["target"])
            elif name == "cz":
                program += CZ(gate["control"], gate["target"])
        for qubit in range(job["circuit"]["qubits"]):
            program += MEASURE(qubit, readout[qubit])
        program.wrap_in_numshots_loop(job["shots"])

        quantum_computer = get_qc(
            job["target"],
            as_qvm=job["backend_mode"] == "simulator",
        )
        result = quantum_computer.run(quantum_computer.compile(program))
        rows = result.readout_data.get("ro", [])
        counts: Dict[str, int] = {}
        for row in rows:
            bit_string = "".join(str(int(bit)) for bit in reversed(row))
            counts[bit_string] = counts.get(bit_string, 0) + 1
        return {"counts": counts}

    def refresh_ionq_job(
        self,
        tenant_id: str,
        job_id: str,
    ) -> Dict[str, Any]:
        job = self.database.get_quantum_job(tenant_id, job_id)
        if not job:
            raise KeyError("Quantum job not found")
        if job["provider"] != "ionq" or not job["provider_job_id"]:
            return job
        api_key = provider_secret("IONQ_API_KEY")
        if not api_key:
            raise RuntimeError("IONQ_API_KEY is not configured")
        request = Request(
            f"{self.IONQ_API_URL}/jobs/{job['provider_job_id']}",
            headers={
                "Authorization": f"apiKey {api_key}",
                "Accept": "application/json",
                "User-Agent": "Orcai25-Orchestrator/1.0",
            },
        )
        with self._urlopen(request, timeout=15) as response:
            data = json.loads(response.read(1024 * 1024))
        provider_status = str(data.get("status", "unknown")).lower()
        status = {
            "completed": "completed",
            "failed": "failed",
            "canceled": "cancelled",
            "cancelled": "cancelled",
        }.get(provider_status, "submitted")
        self.database.update_quantum_job(
            job_id,
            status,
            result=data,
            error=data.get("failure", {}).get("error")
            if isinstance(data.get("failure"), dict)
            else None,
        )
        self._emit(job_id, status, {"provider_status": provider_status})
        return self.database.get_quantum_job(tenant_id, job_id)

    def _emit(self, job_id: str, status: str, details: Dict[str, Any]):
        if self.event_callback:
            self.event_callback(
                job_id,
                status,
                {
                    **details,
                    "tenant_id": self._tenants.get(job_id),
                },
            )
