const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

let currentMode = "text";
let toastTimer;
let busy = false;
let recorder = null;
let stream = null;
let chunks = [];

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

function setBusy(value) {
  busy = value;
  $("#queryInput").disabled = value;
  $("#micButton").disabled = value;
  $(".send-button").disabled = value;
  $(".send-button").textContent = value ? "…" : "➤";
}

function addMessage(text, role) {
  const message = document.createElement("div");
  message.className = `message ${role}-message`;
  const chip = document.createElement("span");
  chip.className = role === "user" ? "user-chip" : "bot-chip";
  chip.textContent = role === "user" ? "U" : "✦";
  const bubble = document.createElement("div");
  bubble.className = role === "user" ? "bubble" : "bubble assistant-bubble";
  bubble.textContent = text;
  if (role === "user") message.append(bubble, chip);
  else message.append(chip, bubble);
  $("#conversation").append(message);
  $("#conversation").scrollTop = $("#conversation").scrollHeight;
  return bubble;
}

function getRows(data) {
  if (typeof data === "string") {
    try { data = JSON.parse(data); } catch { return { columns: [], rows: [] }; }
  }
  if (Array.isArray(data)) {
    return { columns: data.length ? Object.keys(data[0]) : [], rows: data };
  }
  if (data && typeof data === "object") {
    const rows = Array.isArray(data.rows) ? data.rows : Array.isArray(data.data) ? data.data : [];
    const columns = Array.isArray(data.columns) && data.columns.length
      ? data.columns : rows.length ? Object.keys(rows[0]) : [];
    return { columns, rows, truncated: data.truncated, rowCount: data.row_count };
  }
  return { columns: [], rows: [] };
}

function renderTable(data) {
  const { columns, rows, truncated } = getRows(data);
  const head = $("#resultsTableHead");
  const body = $("#salesTable");
  head.replaceChildren();
  body.replaceChildren();

  const header = document.createElement("tr");
  (columns.length ? columns : ["Results"]).forEach((name) => {
    const th = document.createElement("th");
    th.textContent = name;
    header.append(th);
  });
  head.append(header);

  if (!rows.length || !columns.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = Math.max(columns.length, 1);
    cell.textContent = "No tabular rows were returned.";
    row.append(cell);
    body.append(row);
    return;
  }

  rows.forEach((record) => {
    const row = document.createElement("tr");
    columns.forEach((name) => {
      const cell = document.createElement("td");
      const value = record?.[name];
      cell.textContent = value == null ? "—" :
        typeof value === "object" ? JSON.stringify(value) : String(value);
      row.append(cell);
    });
    body.append(row);
  });
  if (truncated) toast("Showing the first 500 returned rows.");
}

function getInsights(summary) {
  const lines = String(summary || "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  const bullets = lines
    .filter((s) => /^([-*•]|\d+[.)])\s+/.test(s))
    .map((s) => s.replace(/^([-*•]|\d+[.)])\s+/, "").trim())
    .filter((s) => s && !/^(chart|audio) (path|file)\s*:/i.test(s));
  return bullets.length ? bullets.slice(0, 6) : [String(summary || "No insights returned.")];
}

function setAudio(url) {
  const audio = $("#audioPlayer");
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  $("#audioProgress").style.width = "0%";
  $("#speakButton").textContent = "▶";
  $("#speakButton").disabled = !url;
  $("#stopSpeak").disabled = !url;
  $("#audioStatus").textContent = url ? "Audio ready" : "Audio was not generated";
  if (url) {
    audio.src = url;
    audio.load();
  }
}

function updateResults(result, pendingBubble) {
  const summary = result.summary || "Query completed, but no summary was returned.";
  pendingBubble.textContent = summary;
  $("#sqlCode").textContent = result.sql || "-- No SQL was returned.";
  $("#insightsList").replaceChildren();
  getInsights(summary).forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    $("#insightsList").append(li);
  });

  renderTable(result.data);
  const chartUrl = result.visualization?.chart_url;
  $("#chartFrame").classList.toggle("hidden", !chartUrl);
  $("#chartEmpty").classList.toggle("hidden", Boolean(chartUrl));
  $("#chartTitle").textContent = chartUrl ? "Interactive query visualization" : "Chart unavailable";
  if (chartUrl) $("#chartFrame").src = chartUrl;
  else {
    $("#chartFrame").removeAttribute("src");
    $("#chartEmpty").textContent = "No chart was generated for this query.";
  }
  setAudio(result.audio || null);
}

async function apiError(response) {
  try {
    const data = await response.json();
    return data.detail || data.message || `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

async function submitToBackend(url, options, label) {
  if (busy) return;
  setBusy(true);
  const userBubble = addMessage(label, "user");
  const pending = addMessage("Working on your query…", "assistant");
  try {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json();
    userBubble.textContent = result.query || label;
    updateResults(result, pending);
    toast("Query completed.");
  } catch (error) {
    pending.textContent = `Could not process this query: ${error.message}`;
    toast(error.message);
  } finally {
    setBusy(false);
    $("#queryInput").focus();
  }
}

$("#queryForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("#queryInput");
  const query = input.value.trim();
  if (!query) return toast("Enter a question about your data first.");
  input.value = "";
  submitToBackend("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  }, query);
});

$$(".mode").forEach((button) => button.addEventListener("click", () => {
  currentMode = button.dataset.mode;
  $$(".mode").forEach((item) => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-selected", String(active));
  });
  $("#queryInput").placeholder = currentMode === "voice"
    ? "Record your question with the microphone..." : "Type your question here...";
  if (currentMode === "voice") toast("Tap the microphone to start or stop recording.");
  else $("#queryInput").focus();
}));

function extensionFor(mime) {
  if (mime.includes("mp4")) return ".mp4";
  if (mime.includes("ogg")) return ".ogg";
  if (mime.includes("wav")) return ".wav";
  if (mime.includes("mpeg")) return ".mp3";
  return ".webm";
}

async function uploadRecording(blob) {
  const form = new FormData();
  form.append("file", blob, `recording${extensionFor(blob.type)}`);
  await submitToBackend("/api/voice-query", { method: "POST", body: form }, "Voice query");
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    return toast("Recording needs a supported browser and HTTPS or localhost.");
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
    const mime = types.find((type) => MediaRecorder.isTypeSupported(type));
    recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
      recorder = null;
      $("#micButton").textContent = "🎙";
      $("#micButton").setAttribute("aria-label", "Start voice recording");
      if (blob.size) await uploadRecording(blob);
      else toast("No audio was recorded.");
    };
    recorder.start();
    $("#micButton").textContent = "■";
    $("#micButton").setAttribute("aria-label", "Stop voice recording");
    toast("Recording… tap the microphone again to finish.");
  } catch (error) {
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    toast(`Microphone error: ${error.message}`);
  }
}

$("#micButton").addEventListener("click", () => {
  if (recorder?.state === "recording") recorder.stop();
  else if (!busy) startRecording();
});

$$(".view-button").forEach((button) => button.addEventListener("click", () => {
  const view = button.dataset.resultView;
  $$(".view-button").forEach((item) => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-selected", String(active));
  });
  $("#chartView").classList.toggle("hidden", view !== "chart");
  $("#tableView").classList.toggle("hidden", view !== "table");
}));

$("#copySql").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("#sqlCode").textContent);
    toast("SQL copied.");
  } catch {
    toast("Could not copy SQL. Check clipboard permissions.");
  }
});

$("#speakButton").addEventListener("click", async () => {
  try { await $("#audioPlayer").play(); }
  catch (error) { toast(`Could not play audio: ${error.message}`); }
});
$("#stopSpeak").addEventListener("click", () => {
  const audio = $("#audioPlayer");
  audio.pause();
  audio.currentTime = 0;
  $("#audioStatus").textContent = "Audio ready";
  $("#speakButton").textContent = "▶";
  $("#audioProgress").style.width = "0%";
});
$("#audioPlayer").addEventListener("play", () => {
  $("#audioStatus").textContent = "Playing…";
  $("#speakButton").textContent = "Ⅱ";
});
$("#audioPlayer").addEventListener("pause", () => {
  if (!$("#audioPlayer").ended) {
    $("#audioStatus").textContent = "Paused";
    $("#speakButton").textContent = "▶";
  }
});
$("#audioPlayer").addEventListener("ended", () => {
  $("#audioStatus").textContent = "Playback finished";
  $("#speakButton").textContent = "▶";
});
$("#audioPlayer").addEventListener("timeupdate", () => {
  const audio = $("#audioPlayer");
  $("#audioProgress").style.width = `${audio.duration ? audio.currentTime / audio.duration * 100 : 0}%`;
});

$("#themeToggle").addEventListener("click", () => {
  document.body.classList.toggle("dark");
  const dark = document.body.classList.contains("dark");
  $("#themeToggle").textContent = dark ? "☀" : "☾";
  $("#themeToggle").title = dark ? "Switch to light mode" : "Switch to dark mode";
});

$$(".nav-item").forEach((button) => button.addEventListener("click", () => {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  const views = {
    History: "Chat history is stored in Supabase. A history browser is not wired into this page yet.",
    "Data Sources": "Database credentials are configured in the backend environment.",
    Settings: "Use the moon icon to switch between light and dark themes.",
  };
  if (button.dataset.view !== "Chat") toast(views[button.dataset.view]);
}));
