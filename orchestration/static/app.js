"use strict";

const state = {
  apiKey: sessionStorage.getItem("orcai_api_key") || "",
  models: [],
};

const byId = (id) => document.getElementById(id);
const make = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

function showMessage(message, error = false) {
  const target = byId("message");
  target.textContent = message;
  target.classList.toggle("error", error);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.apiKey) headers.set("X-API-Key", state.apiKey);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

async function loadPublicProfile() {
  try {
    const health = await api("/healthz");
    byId("health-status").textContent = "Engine online";
    byId("health-status").classList.add("ok");
    if (health.status !== "ok") throw new Error("Unhealthy");
  } catch {
    byId("health-status").textContent = "Engine unavailable";
  }
  try {
    const profile = await api("/api/v1/public/naydoev1");
    byId("profile-name").textContent = profile.name;
    byId("profile-model").textContent = profile.model_number;
    byId("profile-serial").textContent = profile.serial_number;
    byId("profile-registry").textContent = profile.registry_scope;
    byId("profile-source").textContent = profile.source_verified ? "Verified public Hub record" : "Awaiting public Hub verification";
    byId("profile-hash").textContent = `SHA-256 attestation ${profile.registration_hash}`;
  } catch {
    byId("profile-hash").textContent = "Run the VPS bootstrap command to issue the platform identity.";
  }
}

function setModelOptions() {
  ["runner-model", "skill-model", "benchmark-model"].forEach((id) => {
    const select = byId(id);
    select.replaceChildren();
    state.models.forEach((model) => {
      const option = make("option", "", `${model.name} · ${model.source_repo || "local"}`);
      option.value = model.id;
      select.append(option);
    });
  });
}

function tag(text, ok = false) {
  return make("span", `tag${ok ? " ok" : ""}`, text);
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
  showMessage("Command copied to clipboard.");
}

async function revealCommands(model, container) {
  try {
    const commands = await api(`/api/v1/models/${model.id}/commands`);
    const box = make("div", "command-box");
    Object.entries(commands).forEach(([name, command]) => {
      const row = make("div", "command-row");
      row.append(make("code", "", `${name}: ${command}`));
      const button = make("button", "button quiet", "Copy");
      button.type = "button";
      button.addEventListener("click", () => copyText(command));
      row.append(button);
      box.append(row);
    });
    container.querySelector(".command-box")?.remove();
    container.append(box);
  } catch (error) {
    showMessage(error.message, true);
  }
}

function renderModels(models) {
  state.models = models;
  setModelOptions();
  const root = byId("models");
  root.replaceChildren();
  models.forEach((model) => {
    const card = make("article", "data-card");
    card.append(make("p", "eyebrow", model.name === "NayDoeV1" ? "PRIMARY CONDUCTOR" : "MODEL"));
    card.append(make("h3", "", model.source_repo || model.name));
    card.append(tag(model.source_verified ? "Hub verified" : "Registry only", model.source_verified));
    if (model.role_title) card.append(make("p", "", model.role_title));
    card.append(make("p", "", `Model ${model.model_number} · Serial ${model.serial_number}`));
    const actions = make("div", "card-actions");
    const commands = make("button", "button secondary", "Copy / paste menu");
    commands.type = "button";
    commands.addEventListener("click", () => revealCommands(model, card));
    actions.append(commands);
    card.append(actions);
    root.append(card);
  });
}

function renderList(rootId, items, renderer, emptyText) {
  const root = byId(rootId);
  root.replaceChildren();
  if (!items.length) {
    root.append(make("p", "", emptyText));
    return;
  }
  items.forEach((item) => root.append(renderer(item)));
}

function renderSkills(skills) {
  renderList("skills", skills, (skill) => {
    const item = make("article", "list-item");
    const header = make("header");
    header.append(make("strong", "", skill.name), tag(skill.enabled ? "Enabled" : "Disabled", skill.enabled));
    item.append(header, make("p", "", skill.description));
    const remove = make("button", "button danger", "Delete");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      try {
        await api(`/api/v1/skills/${skill.id}`, { method: "DELETE" });
        await loadSkills();
      } catch (error) { showMessage(error.message, true); }
    });
    item.append(remove);
    return item;
  }, "No skills registered.");
}

function renderRuns(payload) {
  renderList("runs", payload.runs, (run) => {
    const item = make("article", "list-item");
    const header = make("header");
    header.append(make("strong", "", `${run.runner} · :${run.port}`), tag(run.status, run.status === "running"));
    item.append(header, make("p", "", run.command.join(" ")));
    if (run.status === "running") {
      const stop = make("button", "button danger", "Stop");
      stop.type = "button";
      stop.addEventListener("click", async () => {
        try {
          await api(`/api/v1/runners/${run.id}/stop`, { method: "POST" });
          await loadRuns();
        } catch (error) { showMessage(error.message, true); }
      });
      item.append(stop);
    }
    return item;
  }, "No model processes.");
}

function renderBenchmarks(benchmarks) {
  renderList("benchmarks", benchmarks, (benchmark) => {
    const item = make("article", "list-item");
    const header = make("header");
    header.append(make("strong", "", benchmark.model_name), tag(benchmark.status, benchmark.status === "completed"));
    item.append(header);
    item.append(make("p", "", `Tasks: ${benchmark.tasks.join(", ")}`));
    if (benchmark.evidence_sha256) item.append(make("p", "", `Evidence SHA-256: ${benchmark.evidence_sha256}`));
    if (benchmark.error) item.append(make("p", "", benchmark.error));
    return item;
  }, "No benchmark evidence yet.");
}

function renderQuantumProviders(providers) {
  const root = byId("quantum-providers");
  root.replaceChildren();
  providers.forEach((provider) => {
    const card = make("article", "data-card");
    card.append(make("p", "eyebrow", provider.provider.toUpperCase()));
    card.append(make("h3", "", provider.display_name));
    card.append(tag(provider.sdk_installed ? "SDK ready" : "SDK missing", provider.sdk_installed));
    card.append(tag(provider.credentials_configured ? "Credentials detected" : "Credentials needed", provider.credentials_configured));
    card.append(make("p", "", provider.access_note));
    root.append(card);
  });
}

function renderQuantumJobs(jobs) {
  renderList("quantum-jobs", jobs, (job) => {
    const item = make("article", "list-item");
    const header = make("header");
    header.append(make("strong", "", `${job.provider} · ${job.target}`), tag(job.status, job.status === "completed"));
    item.append(header, make("p", "", `${job.shots} shots · ${job.backend_mode}`));
    if (job.error) item.append(make("p", "", job.error));
    if (job.provider === "ionq" && job.provider_job_id && !["completed", "failed", "cancelled"].includes(job.status)) {
      const refresh = make("button", "button secondary", "Refresh IonQ");
      refresh.type = "button";
      refresh.addEventListener("click", async () => {
        try {
          await api(`/api/v1/quantum/jobs/${job.id}/refresh`, { method: "POST" });
          await loadQuantum();
        } catch (error) { showMessage(error.message, true); }
      });
      item.append(refresh);
    }
    return item;
  }, "No quantum jobs.");
}

function renderEvents(events) {
  const root = byId("events");
  root.replaceChildren();
  events.forEach((event) => {
    const row = make("div", "event-row");
    row.append(
      make("span", "", new Date(event.created_at).toLocaleString()),
      make("strong", "", event.severity),
      make("span", "", event.event_type),
      make("span", "", `${event.actor} → ${event.resource}`)
    );
    root.append(row);
  });
}

async function loadModels() { renderModels(await api("/api/v1/models")); }
async function loadSkills() { renderSkills(await api("/api/v1/skills")); }
async function loadRuns() { renderRuns(await api("/api/v1/runners")); }
async function loadBenchmarks() { renderBenchmarks(await api("/api/v1/benchmarks")); }
async function loadEvents() { renderEvents(await api("/api/v1/events?limit=100")); }
async function loadQuantum() {
  const [providers, jobs] = await Promise.all([api("/api/v1/quantum/providers"), api("/api/v1/quantum/jobs")]);
  renderQuantumProviders(providers);
  renderQuantumJobs(jobs);
}

async function loadDashboard() {
  try {
    await api("/api/v1/auth/whoami");
    byId("dashboard").hidden = false;
    byId("api-key").value = state.apiKey;
    await Promise.all([loadModels(), loadSkills(), loadRuns(), loadBenchmarks(), loadQuantum(), loadEvents()]);
    showMessage("Zero Trust verification passed.");
  } catch (error) {
    byId("dashboard").hidden = true;
    showMessage(error.message, true);
  }
}

byId("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  state.apiKey = byId("api-key").value.trim();
  sessionStorage.setItem("orcai_api_key", state.apiKey);
  await loadDashboard();
});

byId("disconnect").addEventListener("click", () => {
  state.apiKey = "";
  sessionStorage.removeItem("orcai_api_key");
  byId("api-key").value = "";
  byId("dashboard").hidden = true;
  showMessage("API key cleared from this tab.");
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab, .panel").forEach((node) => node.classList.remove("active"));
    tab.classList.add("active");
    byId(tab.dataset.panel).classList.add("active");
  });
});

byId("refresh-models").addEventListener("click", async () => {
  try {
    renderModels(await api("/api/v1/models/refresh", { method: "POST" }));
    showMessage("Live Hugging Face catalog refreshed.");
  } catch (error) { showMessage(error.message, true); }
});

byId("skill-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/v1/skills", {
      method: "POST",
      body: JSON.stringify({
        name: byId("skill-name").value,
        description: byId("skill-description").value,
        system_prompt: byId("skill-prompt").value,
        allowed_models: [byId("skill-model").value],
      }),
    });
    event.target.reset();
    setModelOptions();
    await loadSkills();
    showMessage("Skill registered without executable code.");
  } catch (error) { showMessage(error.message, true); }
});

byId("runner-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/v1/runners", {
      method: "POST",
      body: JSON.stringify({
        model_id: byId("runner-model").value,
        runner: byId("runner-engine").value,
        port: Number(byId("runner-port").value),
      }),
    });
    await loadRuns();
    showMessage("Model runner started.");
  } catch (error) { showMessage(error.message, true); }
});

byId("benchmark-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const tasks = [...document.querySelectorAll("input[name=task]:checked")].map((input) => input.value);
  const limitValue = byId("benchmark-limit").value;
  try {
    await api("/api/v1/benchmarks", {
      method: "POST",
      body: JSON.stringify({
        model_id: byId("benchmark-model").value,
        tasks,
        limit: limitValue ? Number(limitValue) : null,
      }),
    });
    await loadBenchmarks();
    showMessage("Benchmark recorded. Scores appear only after a real harness run.");
  } catch (error) { showMessage(error.message, true); }
});

byId("quantum-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/v1/quantum/jobs", {
      method: "POST",
      body: JSON.stringify({
        provider: byId("quantum-provider").value,
        backend_mode: byId("quantum-mode").value,
        target: byId("quantum-target").value || null,
        circuit: JSON.parse(byId("quantum-circuit").value),
        shots: Number(byId("quantum-shots").value),
        confirm_hardware: byId("quantum-confirm").checked,
      }),
    });
    await loadQuantum();
    showMessage("Quantum job submitted to the configured adapter.");
  } catch (error) { showMessage(error.message, true); }
});

byId("refresh-events").addEventListener("click", () => loadEvents().catch((error) => showMessage(error.message, true)));

loadPublicProfile();
if (state.apiKey) loadDashboard();
