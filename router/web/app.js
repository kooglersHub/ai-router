"use strict";

const $ = (selector) => document.querySelector(selector);
const page = $("#page");
const activeStatuses = new Set(["queued", "running", "checking", "handoff"]);
const names = {
  codex: "Codex",
  gemini: "Gemini CLI",
  freebuff: "Freebuff",
  kit: "KIT KI-Toolbox",
};

function kitRemaining() {
  return Math.max(0, state.settings.kit_budget - state.settings.kit_used);
}
const statusNames = {
  queued: "Wartet",
  running: "In Arbeit",
  checking: "Wird geprüft",
  handoff: "Terminal öffnen",
  review: "Ergebnis prüfen",
  done: "Abgeschlossen",
  demo_complete: "Demo abgeschlossen",
  failed: "Fehlgeschlagen",
  cancelled: "Abgebrochen",
  interrupted: "Unterbrochen",
};
let state = null;
let taskTab = "overview";
let busy = false;
let toastTimer;

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[character],
  );
}

function icon(name) {
  return `<img src="/icons/${name}.svg" alt="">`;
}

function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 6000);
}

function route() {
  const path = location.pathname;
  if (path.startsWith("/task/"))
    return { view: "detail", id: path.split("/")[2] };
  return {
    view:
      { "/tasks": "tasks", "/agents": "agents", "/settings": "settings" }[
        path
      ] || "overview",
  };
}

function navigate(path) {
  history.pushState({}, "", path);
  taskTab = "overview";
  render();
  window.scrollTo({ top: 0 });
}

function badge(task) {
  let tone = "";
  if (["done", "demo_complete"].includes(task.status)) tone = "positive";
  if (activeStatuses.has(task.status) || task.status === "review")
    tone = "working";
  if (["failed", "interrupted"].includes(task.status)) tone = "error";
  return `<span class="badge ${tone}">${escapeHtml(statusNames[task.status] || task.status)}</span>`;
}

function dateLabel(value) {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function timeLabel(value) {
  return new Intl.DateTimeFormat("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function heading(title, description, action = "") {
  return `<div class="page-heading"><div><h1>${title}</h1><p>${description}</p></div>${action}</div>`;
}

function taskRows(tasks) {
  if (!tasks.length)
    return `<div class="empty">${icon("inbox")}<div><strong>Noch keine Aufgaben</strong><p>Beschreibe oben deinen ersten Auftrag. Im Demo-Modus kannst du den Ablauf ausprobieren</p></div></div>`;
  return `<div class="task-table">${tasks
    .map(
      (task) => `<button class="task-row" data-task="${task.id}">
    <div><strong>${escapeHtml(task.title)}</strong><small>${escapeHtml(dateLabel(task.created_at))} · ${task.mode === "demo" ? "Demo" : escapeHtml(names[task.agent])}</small></div>
    <span>${task.mode === "demo" ? "Simulation" : escapeHtml(names[task.agent])}</span><div>${badge(task)}</div>${icon("chevron-right")}</button>`,
    )
    .join("")}</div>`;
}

function guide() {
  return `<aside class="guide"><h3>Du gibst die Richtung vor</h3><ol class="steps">
    <li><span class="step-number">1</span><div><strong>Aufgabe beschreiben</strong><p>Was soll sich ändern? Je konkreter dein Auftrag, desto besser das Ergebnis</p></div></li>
    <li><span class="step-number">2</span><div><strong>Agent arbeiten lassen</strong><p>Eine eigene Arbeitskopie hält die Änderungen von deinem Hauptprojekt getrennt</p></div></li>
    <li><span class="step-number">3</span><div><strong>Ergebnis prüfen</strong><p>Änderungen ansehen, Tests ausführen und entscheiden, was du behältst</p></div></li>
    </ol><div class="guide-note">${icon("shield-check")}<p>Dein Hauptbranch bleibt in deiner Hand. Der Router führt keine automatischen Merges oder Deployments aus</p></div></aside>`;
}

function renderOverview() {
  const active = state.tasks.find((task) => activeStatuses.has(task.status));
  page.innerHTML =
    heading(
      "Deine nächste Aufgabe",
      "Beschreibe, was erledigt werden soll. Den Rest gehst du Schritt für Schritt durch.",
    ) +
    (active
      ? `<div class="notice"><strong>Eine Aufgabe ist gerade aktiv.</strong> ${escapeHtml(active.title)} <a href="/task/${active.id}">Aufgabe öffnen</a></div>`
      : "") +
    `<div class="workspace-grid"><section class="panel"><div class="panel-header"><div><h2>Was soll erledigt werden?</h2><p class="panel-intro">Ein klarer Auftrag ist alles, was du zum Starten brauchst</p></div></div>
    <form id="task-form" class="composer">
      <div class="field"><label for="task-description">Dein Auftrag</label><textarea id="task-description" name="description" placeholder="Was funktioniert noch nicht? Was soll danach anders sein?" maxlength="20000" required></textarea></div>
      <div class="field form-row"><div><label for="agent">Agent</label><select id="agent" name="agent"><option value="auto">Automatisch auswählen</option><option value="codex">Codex</option><option value="freebuff">Freebuff · im Terminal</option><option value="gemini">Gemini CLI</option><option value="kit">KIT KI-Toolbox · Umsetzungsplan</option></select></div><div><label for="project">Projektordner</label><input id="project" name="repo" value="${escapeHtml(state.settings.repo)}" required><p class="field-help">Lokales Git-Projekt mit mindestens einem Commit</p></div></div>
      <div class="field"><label>Wie möchtest du starten?</label><div class="segmented"><label><input type="radio" name="mode" value="demo" checked><span>Erst ausprobieren</span></label><label><input type="radio" name="mode" value="live"><span>Echte Aufgabe</span></label></div><p class="mode-note" id="mode-note">Demo: kein Agentenaufruf, keine Änderungen und keine Kosten</p></div>
      <label class="check-label" id="consent-label" hidden><input type="checkbox" name="consent"><span id="consent-text">Ich gebe diesen Agentenaufruf frei. Der Agent darf das Projekt an seinen Dienst übertragen und in der Arbeitskopie bearbeiten. Es gelten mein Zugang und dessen mögliche Kosten</span></label>
      <details class="advanced"><summary>Erfolgskriterien und weitere Optionen</summary>
        <div class="field"><label for="task-title">Kurzer Titel (optional)</label><input id="task-title" name="title" placeholder="Wird sonst aus deinem Auftrag übernommen" maxlength="200"></div>
        <div class="field"><label for="criteria">Woran erkennst du ein gutes Ergebnis?</label><textarea id="criteria" name="criteria" placeholder="Zum Beispiel: Filter kombinierbar, vorhandene Tests bestehen" maxlength="10000"></textarea></div>
        <div class="form-row field"><div><label for="task-type">Aufgabentyp</label><select id="task-type" name="task_type"><option value="bugfix">Fehler beheben</option><option value="feature">Funktion ergänzen</option><option value="research">Analysieren</option><option value="tests">Tests ergänzen</option></select></div><div><label for="difficulty">Umfang</label><select id="difficulty" name="difficulty"><option value="easy">Klein</option><option value="medium" selected>Mittel</option><option value="hard">Groß</option></select></div></div>
        <div class="form-row field"><div><label for="timeout">Zeitlimit in Minuten</label><input id="timeout" name="timeout" type="number" min="1" max="120" value="15"></div><div><label for="budget">Budget für Vorprüfung in US-Dollar</label><input id="budget" name="budget" type="number" min="0" step="0.01" placeholder="Optional"><p class="field-help">Benötigt Kostenschätzung in den Einstellungen; kein hartes Provider-Limit</p></div></div>
      </details><div id="form-error" role="alert"></div><div class="form-footer"><span>Eine Aufgabe zur Zeit · Änderungen separat</span><button class="primary" type="submit" ${active ? "disabled" : ""}>Demo starten ${icon("arrow-right")}</button></div>
    </form></section>${guide()}</div><div class="section-heading"><h2>Letzte Aufgaben</h2><a href="/tasks">Alle ansehen</a></div>${taskRows(state.tasks.slice(0, 4))}`;
  const form = $("#task-form");
  form.addEventListener("change", (event) => {
    if (["agent", "mode"].includes(event.target.name)) {
      form.elements.consent.checked = false;
    }
    const live = form.elements.mode.value === "live";
    const freebuff = form.elements.agent.value === "freebuff";
    const kit = form.elements.agent.value === "kit";
    $("#consent-text").textContent = kit
      ? "Ich gebe Titel, Auftragstext und Erfolgskriterien für einen Aufruf der KIT KI-Toolbox frei"
      : "Ich gebe diesen Agentenaufruf frei. Der Agent darf das Projekt an seinen Dienst übertragen und in der Arbeitskopie bearbeiten. Es gelten mein Zugang und dessen mögliche Kosten";
    $("#consent-label").hidden = !live;
    form.elements.consent.required = live;
    $("#mode-note").textContent = live
      ? kit
        ? `KIT erstellt einen Plan. ${kitRemaining().toLocaleString("de-DE")} Tokens im lokalen Budget verfügbar`
        : freebuff
          ? "Freebuff wird vorbereitet. Du öffnest und bedienst die Sitzung im Terminal"
          : "Der ausgewählte Agent darf echte Änderungen in einer eigenen Arbeitskopie vornehmen"
      : "Demo: kein Agentenaufruf, keine Änderungen und keine Kosten";
    form.querySelector("button[type=submit]").innerHTML =
      `${live ? (kit ? "KIT-Plan erstellen" : freebuff ? "Freebuff vorbereiten" : "Aufgabe starten") : "Demo starten"} ${icon("arrow-right")}`;
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    const values = Object.fromEntries(new FormData(form));
    values.title =
      values.title.trim() ||
      values.description.trim().split("\n")[0].slice(0, 100);
    values.consent = form.elements.consent.checked;
    values.timeout = Number(values.timeout) * 60;
    values.budget = values.budget === "" ? null : Number(values.budget);
    try {
      const task = await post("/api/tasks", values);
      await refresh();
      navigate(`/task/${task.id}`);
    } catch (error) {
      $("#form-error").innerHTML =
        `<div class="error-message">${escapeHtml(error.message)}</div>`;
      button.disabled = false;
    } finally {
      busy = false;
    }
  });
}

function renderTasks() {
  page.innerHTML =
    heading(
      "Deine Aufgaben",
      "Aufträge, Fortschritt und Ergebnisse an einem Ort.",
      '<a href="/" class="primary">Neue Aufgabe</a>',
    ) +
    `<div class="list-toolbar"><input type="search" id="task-search" placeholder="Aufgaben durchsuchen" aria-label="Aufgaben durchsuchen"><select id="task-filter" aria-label="Status filtern"><option value="all">Alle Aufgaben</option><option value="active">In Arbeit</option><option value="review">Zu prüfen</option><option value="complete">Abgeschlossen</option></select></div><div id="task-list">${taskRows(state.tasks)}</div>`;
  const filter = () => {
    const search = $("#task-search").value.toLocaleLowerCase("de");
    const type = $("#task-filter").value;
    const tasks = state.tasks.filter(
      (task) =>
        task.title.toLocaleLowerCase("de").includes(search) &&
        (type === "all" ||
          (type === "active" && activeStatuses.has(task.status)) ||
          (type === "review" && task.status === "review") ||
          (type === "complete" &&
            ["done", "demo_complete"].includes(task.status))),
    );
    $("#task-list").innerHTML = tasks.length
      ? taskRows(tasks)
      : '<div class="empty"><div><strong>Keine passenden Aufgaben</strong><p>Ändere den Suchbegriff oder den Statusfilter</p></div></div>';
  };
  $("#task-search").addEventListener("input", filter);
  $("#task-filter").addEventListener("change", filter);
}

function renderAgents() {
  page.innerHTML =
    heading(
      "Deine Agenten",
      "Welche Werkzeuge bereitstehen – und wie du sie verwendest.",
    ) +
    `<div class="agent-grid">${state.agents
      .map(
        (
          agent,
        ) => `<section class="panel agent-card"><div class="agent-symbol">${escapeHtml(agent.name.slice(0, 1))}</div><h2>${escapeHtml(agent.name)}</h2><p>${escapeHtml(agent.description)}</p>
    ${
      agent.id === "kit"
        ? `<div class="agent-detail"><span>API-Key</span><strong>${agent.installed ? "Hinterlegt" : "Einrichtung erforderlich"}</strong></div><div class="agent-detail"><span>Lokales Budget</span><strong>${kitRemaining().toLocaleString("de-DE")} Tokens übrig</strong></div>`
        : `<div class="agent-detail"><span>Installation</span><strong>${agent.installed ? "Vorhanden" : "Nicht installiert"}</strong></div><div class="agent-detail"><span>Bedienung</span><strong>${agent.kind === "interactive" ? "Im Terminal" : "Über die Oberfläche"}</strong></div>
    <div class="agent-detail"><span>Anmeldung</span><strong>Beim ersten Aufruf prüfen</strong></div><div class="agent-detail"><span>Kontingent</span><strong>${state.settings.quotas[agent.id] === null ? "Nicht erfasst" : `${state.settings.quotas[agent.id]} Aufgaben`}</strong></div>`
    }
    <a class="text-button" href="#install-${agent.id}" data-install="${agent.id}">Einrichtung ansehen</a></section>`,
      )
      .join("")}</div>
    <div class="section-heading"><h2>Freebuff ist eingebunden</h2></div><section class="panel"><h3>Ein Terminal-Schritt gehört dazu</h3><p class="panel-intro">Freebuff 0.2.36 nimmt keine automatischen Prompt-Aufträge per CLI an. Der Router bereitet eine eigene Arbeitskopie vor. Du kopierst den Auftrag, öffnest Freebuff und prüfst das Ergebnis anschließend wieder hier</p>
    <div class="install-block" id="install-freebuff"><h3>Freebuff starten</h3><p class="small muted">Lokal installiert; die Anmeldung erfolgt im Freebuff-Terminal</p><pre>node .local/agents/node_modules/freebuff/index.js</pre><p class="footer-note">Kosten und verfügbare Nutzung richten sich nach deinem Freebuff-Zugang. Der Router kennt dein Guthaben nicht</p><a class="text-button" href="https://freebuff.com/cli" target="_blank" rel="noreferrer">Offizielle Freebuff-Anleitung</a></div>
    <details class="advanced" id="install-codex"><summary>Codex einrichten</summary><p>Codex CLI muss im Suchpfad liegen und angemeldet sein. Der Router verwendet workspace-write und deaktiviert keine Schutzmechanismen</p><pre>codex</pre></details>
    <details class="advanced" id="install-gemini"><summary>Gemini CLI einrichten</summary><p>Lokale Installation mit pnpm, danach im Terminal anmelden</p><pre>pnpm --dir .local/agents add @google/gemini-cli\nnode .local/agents/node_modules/@google/gemini-cli/dist/index.js</pre></details>
    <details class="advanced" id="install-kit"><summary>KIT KI-Toolbox einrichten</summary><p>Starte den Router mit <code>.\\start-router.ps1 -Kit</code> und gib den Key in PowerShell ein. Lege anschließend unter <a href="/settings">Einstellungen</a> dein Tokenbudget fest</p></details></section>
    <p class="footer-note">„Vorhanden“ bestätigt die Installation, nicht eine aktive Anmeldung oder ein kostenloses Kontingent</p>`;
}

function renderSettings() {
  page.innerHTML =
    heading(
      "Deine Einstellungen",
      "Einmal einrichten. Bei jeder Aufgabe die Kontrolle behalten.",
    ) +
    `<div class="settings-layout"><form id="settings-form"><section class="panel settings-panel"><h2>Standardprojekt</h2><p>Hier starten neue Aufgaben. Du kannst den Ordner pro Auftrag ändern</p><div class="field"><label for="settings-repo">Lokaler Git-Projektordner</label><input id="settings-repo" name="repo" value="${escapeHtml(state.settings.repo)}" required></div></section>
    <section class="panel settings-panel"><h2>Kontingente und Kostenschätzungen</h2><p>Manuelle Planungswerte. Leere Felder bedeuten „unbekannt“, nicht „kostenlos“</p><div class="quota-row quota-head"><span>Agent</span><span>Aufgaben übrig</span><span>US-Dollar / Aufgabe</span></div>
    ${state.agents
      .filter((agent) => agent.id !== "kit")
      .map(
        (agent) =>
          `<div class="quota-row"><label for="quota-${agent.id}">${escapeHtml(agent.name)}</label><input id="quota-${agent.id}" type="number" min="0" step="1" name="quota-${agent.id}" value="${state.settings.quotas[agent.id] ?? ""}" placeholder="Unbekannt" aria-label="${agent.name}: Aufgaben übrig"><input type="number" min="0" step="0.01" name="cost-${agent.id}" value="${state.settings.estimated_costs[agent.id] ?? ""}" placeholder="Unbekannt" aria-label="${agent.name}: Kostenschätzung"></div>`,
      )
      .join("")}
    <p class="field-help">Bei 0 Aufgaben wird ein Agent nicht ausgewählt. Automatische Aufrufe reduzieren den manuellen Zähler; Freebuff wird manuell gepflegt. Ein Budget kann echte Provider-Kosten nicht hart begrenzen</p></section>
    <section class="panel settings-panel" id="kit-budget"><h2>KIT-Tokenbudget</h2><p id="kit-balance">${kitRemaining().toLocaleString("de-DE")} Tokens übrig · ${state.settings.kit_used.toLocaleString("de-DE")} angerechnet</p><div class="form-row"><div><label for="kit-total">Gesamtbudget in Tokens</label><input id="kit-total" name="kit_budget" type="number" min="0" max="9007199254740991" step="1" required value="${state.settings.kit_budget}"></div><div><label for="kit-output">Maximale Antwort-Tokens</label><input id="kit-output" name="kit_output_limit" type="number" min="1" max="4096" step="1" required value="${state.settings.kit_output_limit}"></div></div><p>Das Budget gilt für diesen Router. Eingabe und Antwort werden vorab geschätzt und mit der KIT-Verbrauchsmeldung abgeglichen</p></section>
    <section class="panel settings-panel"><h2>Tests nach der Umsetzung</h2><p>Testkommandos werden nur nach deinem Klick ausgeführt. Sie gelten als lokaler Code und laufen in der Arbeitskopie</p><details class="advanced"><summary>Testbefehle konfigurieren</summary><label class="detail-label" for="test-commands">JSON-Liste mit Programmen und Argumenten</label><textarea id="test-commands" name="tests" spellcheck="false">${escapeHtml(JSON.stringify(state.settings.tests, null, 2))}</textarea><p class="field-help">Beispiel: [["python", "-m", "unittest", "discover", "-s", "tests"]]</p></details></section>
    <div id="settings-error" role="alert"></div><button class="primary" type="submit">Einstellungen speichern</button><p class="footer-note">Alle Angaben werden lokal gespeichert</p></form><aside class="settings-aside"><h3>Dein Projekt bleibt getrennt</h3><p>Jede echte Aufgabe bekommt eine eigene Git-Arbeitskopie. Nicht eingecheckte Änderungen aus deinem Projektordner werden nicht mitgenommen</p><h3>Kosten bleiben sichtbar</h3><p>Ein vorhandenes Abo oder eine installierte CLI sagt nichts über verfügbare Kontingente aus. Deshalb braucht jeder echte Auftrag deine Freigabe</p><h3>Ein Schritt nach dem anderen</h3><p>Der Router führt höchstens eine Aufgabe gleichzeitig aus. Kein unbeaufsichtigter Wechsel auf einen kostenpflichtigen Dienst</p></aside></div>`;
  $("#settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(form));
      const quotas = {};
      const costs = {};
      for (const agent of state.agents.filter((item) => item.id !== "kit")) {
        quotas[agent.id] =
          values[`quota-${agent.id}`] === ""
            ? null
            : Number(values[`quota-${agent.id}`]);
        costs[agent.id] =
          values[`cost-${agent.id}`] === ""
            ? null
            : Number(values[`cost-${agent.id}`]);
      }
      await post("/api/settings", {
        repo: values.repo,
        quotas,
        estimated_costs: costs,
        tests: JSON.parse(values.tests),
        kit_budget: Number(values.kit_budget),
        kit_output_limit: Number(values.kit_output_limit),
      });
      await refresh();
      $("#settings-error").innerHTML = "";
      $("#kit-balance").textContent =
        `${kitRemaining().toLocaleString("de-DE")} Tokens übrig · ${state.settings.kit_used.toLocaleString("de-DE")} angerechnet`;
      toast("Einstellungen gespeichert");
    } catch (error) {
      $("#settings-error").innerHTML =
        `<div class="error-message">${escapeHtml(error.message)}</div>`;
    } finally {
      button.disabled = false;
    }
  });
}

function taskNotice(task) {
  if (task.mode === "demo")
    return '<div class="notice task-state-note"><strong>Dies ist eine Demo.</strong> Kein Agent wurde aufgerufen, keine Datei verändert und kein Test ausgeführt</div>';
  if (task.agent === "kit")
    return '<div class="notice task-state-note">KIT erstellt einen Plan aus dem Auftragstext. Die Umsetzung erfolgt als separater Auftrag</div>';
  if (task.status === "handoff")
    return '<div class="notice task-state-note"><strong>Dein nächster Schritt:</strong> Auftrag kopieren, Freebuff öffnen und dort einfügen. Schließe danach das Terminal und klicke auf „Ergebnis prüfen“</div>';
  if (task.status === "review")
    return '<div class="notice task-state-note"><strong>Das Ergebnis ist bereit.</strong> Lies die Änderungen, prüfe deine Kriterien und führe bei Bedarf Tests aus. Es wurde nichts in deinen Hauptbranch übernommen</div>';
  if (task.status === "running")
    return '<div class="notice task-state-note"><strong>Der Agent arbeitet.</strong> Die Seite aktualisiert den Status automatisch. Die CLI-Ausgabe erscheint nach Ende des Aufrufs</div>';
  if (task.status === "interrupted")
    return '<div class="notice task-state-note">Der Server wurde neu gestartet. Deine Arbeitskopie ist erhalten. Du kannst vorhandene Änderungen erneut prüfen</div>';
  return "";
}

function detailContent(task) {
  const kitPlan =
    task.agent === "kit" && task.mode === "live" && task.output
      ? `<h3>KIT-Umsetzungsplan</h3><pre>${escapeHtml(task.output)}</pre>`
      : "";
  if (taskTab === "changes")
    return task.diff
      ? `<div class="detail-label">${task.files.length} geänderte Datei(en)</div><pre>${escapeHtml(task.diff)}</pre>`
      : '<p class="muted">Noch keine Änderungen erfasst. Bei einer echten Aufgabe erst „Ergebnis prüfen“ wählen</p>';
  if (taskTab === "tests")
    return `<div class="notice">${task.test_status === "passed" ? "Die konfigurierten Tests sind bestanden. Akzeptanzkriterien müssen trotzdem geprüft werden." : task.test_status === "failed" ? "Mindestens ein Test ist fehlgeschlagen. Details stehen unten." : "Noch keine Tests ausgeführt. Ein beendeter Agentenaufruf ist kein bestandener Test."}</div>${task.test_results.map((result) => `<h3>${escapeHtml(result.command.join(" "))} · Exitcode ${result.exit_code}</h3><pre>${escapeHtml(result.output)}</pre>`).join("")}${task.tests.length === 0 ? '<p>Keine Tests konfiguriert. <a href="/settings">Einstellungen öffnen</a></p>' : ""}`;
  if (taskTab === "output")
    return `<pre>${escapeHtml(task.output || "Noch keine Agentenausgabe vorhanden")}</pre>`;
  return `${kitPlan}<div class="detail-section"><div class="detail-label">Dein Auftrag</div><p class="detail-description">${escapeHtml(task.description)}</p></div>${task.criteria ? `<div class="detail-section"><div class="detail-label">Akzeptanzkriterien</div><p class="detail-description">${escapeHtml(task.criteria)}</p></div>` : ""}<div class="detail-section"><div class="detail-label">Ablauf</div>${task.events.map((event) => `<div class="event"><time>${timeLabel(event.time)}</time><div>${escapeHtml(event.message)}</div></div>`).join("")}</div>`;
}

function renderDetail(taskId) {
  const task = state.tasks.find((item) => item.id === taskId);
  if (!task) {
    page.innerHTML = heading(
      "Aufgabe nicht gefunden",
      "Diese Aufgabe ist in diesem Arbeitsbereich nicht gespeichert.",
      '<a class="secondary" href="/">Zur Übersicht</a>',
    );
    return;
  }
  const kit = task.agent === "kit";
  const reviewing = !kit && ["review", "done"].includes(task.status);
  const tabs = kit
    ? [["overview", "Überblick"]]
    : [
        ["overview", "Überblick"],
        ["changes", "Änderungen"],
        ["tests", "Tests"],
        ["output", "Agentenausgabe"],
      ];
  const terminal = task.agent === "freebuff" && task.status === "handoff";
  const canReview =
    task.worktree &&
    ["handoff", "review", "failed", "interrupted", "cancelled"].includes(
      task.status,
    );
  page.innerHTML =
    `<a href="/tasks" class="page-back">${icon("arrow-left")}Alle Aufgaben</a>` +
    heading(
      escapeHtml(task.title),
      `${task.mode === "demo" ? "Demo" : escapeHtml(names[task.agent])} · ${escapeHtml(dateLabel(task.created_at))}`,
      badge(task),
    ) +
    taskNotice(task) +
    `<div class="task-detail-grid"><section class="panel"><div class="progress-track"><div class="progress-item complete"><span class="step-number">1</span>Auftrag</div><span class="progress-line"></span><div class="progress-item ${reviewing || (task.mode === "demo" && task.status === "demo_complete") ? "complete" : "current"}"><span class="step-number">2</span>Ausführung</div><span class="progress-line"></span><div class="progress-item ${reviewing ? "current" : ""}"><span class="step-number">3</span>Prüfung</div></div>
    <h2>${task.status === "handoff" ? "Weiter mit Freebuff" : escapeHtml(statusNames[task.status])}</h2>${task.error ? `<div class="error-message" role="alert">${escapeHtml(task.error)}</div>` : ""}
    <div class="action-row">${terminal ? '<button class="primary" data-action="terminal">Freebuff öffnen</button><button class="secondary" data-copy="prompt">Auftrag kopieren</button>' : ""}
    ${canReview ? '<button class="' + (terminal ? "secondary" : "primary") + '" data-action="review">Ergebnis prüfen</button>' : ""}
    ${canReview && state.settings.tests.length ? '<button class="secondary" data-action="test">Tests ausführen</button>' : ""}
    ${task.status === "review" ? '<button class="secondary" data-action="finish">Prüfung bestätigen</button>' : ""}
    ${activeStatuses.has(task.status) ? '<button class="quiet" data-action="abort">' + (terminal ? "Aufgabe beenden" : "Abbrechen") + "</button>" : ""}
    ${task.mode === "demo" && task.status === "demo_complete" ? '<a class="primary" href="/">Eigene Aufgabe erstellen</a>' : ""}</div>
    <div class="detail-tabs" role="tablist" aria-label="Aufgabendetails">${tabs
      .map(
        ([key, label]) =>
          `<button role="tab" aria-selected="${taskTab === key}" data-tab="${key}" class="${taskTab === key ? "active" : ""}">${label}</button>`,
      )
      .join(
        "",
      )}</div><div class="detail-section" role="tabpanel">${detailContent(task)}</div></section>
    <aside class="panel"><h3>Auf einen Blick</h3><dl class="detail-meta"><div><dt>Agent</dt><dd>${escapeHtml(names[task.agent])}${task.mode === "demo" ? " · nur Auswahl simuliert" : ""}</dd></div><div><dt>Projekt</dt><dd>${escapeHtml(task.repo.split(/[\\/]/).pop())}</dd></div><div><dt>Dauer</dt><dd>${task.duration === null ? "Noch nicht erfasst" : `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(task.duration)} Sekunden`}</dd></div>${task.kit_tokens_reserved != null ? `<div><dt>KIT-Tokens</dt><dd>${(task.kit_tokens_actual ?? task.kit_tokens_reserved).toLocaleString("de-DE")}${task.kit_tokens_actual == null ? " reserviert" : " gemeldet"}</dd></div>` : ""}<div><dt>Kosten</dt><dd>${task.mode === "demo" ? "Kein Agentenaufruf" : "Nicht vom Dienst gemeldet"}</dd></div><div><dt>Tests</dt><dd>${{ passed: "Bestanden", failed: "Fehlgeschlagen", not_run: "Nicht ausgeführt" }[task.test_status]}</dd></div></dl>
    ${task.worktree ? `<details class="advanced"><summary>Arbeitskopie und Branch</summary><div class="detail-label">Ordner</div><p class="inline-code">${escapeHtml(task.worktree)}</p><div class="action-row"><button class="text-button" data-copy="path">Pfad kopieren</button></div><div class="detail-label field">Branch</div><p class="inline-code">${escapeHtml(task.branch)}</p></details>` : ""}</aside></div>`;
}

async function post(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Router-Token": state.token,
    },
    body: JSON.stringify(data),
  });
  const value = await response.json();
  if (!response.ok)
    throw new Error(value.error || "Die Aktion konnte nicht ausgeführt werden");
  return value;
}

async function refresh() {
  const response = await fetch("/api/state", { cache: "no-store" });
  if (!response.ok) throw new Error("Der lokale Router ist nicht erreichbar");
  state = await response.json();
  $("#connection").textContent = "Verbunden · lokal";
  $("#task-count").textContent = state.tasks.length || "";
}

function render() {
  const current = route();
  const activeNav = current.view === "detail" ? "tasks" : current.view;
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.classList.toggle("active", link.dataset.nav === activeNav);
    if (link.dataset.nav === activeNav)
      link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("#breadcrumb").textContent = {
    overview: "Übersicht",
    tasks: "Aufgaben",
    agents: "Agenten",
    settings: "Einstellungen",
    detail: "Aufgabe",
  }[current.view];
  document.title = `${$("#breadcrumb").textContent} · AI Router`;
  if (current.view === "overview") renderOverview();
  if (current.view === "tasks") renderTasks();
  if (current.view === "agents") renderAgents();
  if (current.view === "settings") renderSettings();
  if (current.view === "detail") renderDetail(current.id);
}

document.addEventListener("click", async (event) => {
  const taskLink = event.target.closest("[data-task]");
  if (taskLink) {
    navigate(`/task/${taskLink.dataset.task}`);
    return;
  }
  const tab = event.target.closest("[data-tab]");
  if (tab) {
    taskTab = tab.dataset.tab;
    renderDetail(route().id);
    return;
  }
  const install = event.target.closest("[data-install]");
  if (install) {
    event.preventDefault();
    const section = $(`#install-${install.dataset.install}`);
    if (section.tagName === "DETAILS") section.open = true;
    section.scrollIntoView({ block: "center" });
    return;
  }
  const internalLink = event.target.closest('a[href^="/"]');
  if (internalLink && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    navigate(internalLink.getAttribute("href"));
    return;
  }
  const copy = event.target.closest("[data-copy]");
  if (copy) {
    const task = state.tasks.find((item) => item.id === route().id);
    const prompt = `${task.title}\n\n${task.description}\n\nAkzeptanzkriterien:\n${task.criteria}\n\nNur in dieser Arbeitskopie arbeiten. Keine Merges, Pushes oder Deployments.`;
    try {
      await navigator.clipboard.writeText(
        copy.dataset.copy === "path" ? task.worktree : prompt,
      );
      toast("In die Zwischenablage kopiert");
    } catch {
      toast(
        "Kopieren nicht möglich. Markiere den Text und kopiere ihn manuell",
      );
    }
    return;
  }
  const actionButton = event.target.closest("[data-action]");
  if (actionButton && !busy) {
    busy = true;
    actionButton.disabled = true;
    const action = actionButton.dataset.action;
    try {
      const endpoint = action === "test" ? "review" : action;
      await post(`/api/tasks/${route().id}/${endpoint}`, {
        run_tests: action === "test",
      });
      await refresh();
      if (action === "test") taskTab = "tests";
      render();
      if (action === "terminal") toast("Freebuff wird im Terminal geöffnet");
    } catch (error) {
      toast(error.message);
      actionButton.disabled = false;
    } finally {
      busy = false;
    }
  }
});

$("#help-button").addEventListener("click", () =>
  $("#help-dialog").showModal(),
);
$("#close-help").addEventListener("click", () => $("#help-dialog").close());
window.addEventListener("popstate", render);

async function poll() {
  try {
    const previous = JSON.stringify(state?.tasks);
    await refresh();
    if (
      !busy &&
      route().view === "detail" &&
      previous !== JSON.stringify(state.tasks)
    )
      render();
  } catch {
    $("#connection").textContent = "Verbindung unterbrochen";
  } finally {
    setTimeout(poll, 2000);
  }
}

refresh()
  .then(() => {
    render();
    poll();
  })
  .catch((error) => {
    page.innerHTML =
      heading("Router nicht erreichbar", escapeHtml(error.message)) +
      "<p>Starte start-router.ps1 im Projektordner und lade die Seite neu</p>";
  });
