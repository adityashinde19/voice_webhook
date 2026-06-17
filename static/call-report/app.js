const elements = {
  missing: document.querySelector("#missing-state"),
  loading: document.querySelector("#loading-state"),
  error: document.querySelector("#error-state"),
  report: document.querySelector("#report"),
  errorMessage: document.querySelector("#error-message"),
  retryButton: document.querySelector("#retry-button"),
  callForm: document.querySelector("#call-form"),
  callInput: document.querySelector("#call-id-input"),
  eventType: document.querySelector("#event-type"),
  reportDate: document.querySelector("#report-date"),
  reportTime: document.querySelector("#report-time"),
  customerNumber: document.querySelector("#customer-number"),
  durationMain: document.querySelector("#duration-main"),
  durationSub: document.querySelector("#duration-sub"),
  sentimentMain: document.querySelector("#sentiment-main"),
  sentimentSub: document.querySelector("#sentiment-sub"),
  costMain: document.querySelector("#cost-main"),
  summaryText: document.querySelector("#summary-text"),
  highlights: document.querySelector("#highlights"),
  chartLine: document.querySelector("#chart-line"),
  chartFill: document.querySelector("#chart-fill"),
  chartPoints: document.querySelector("#chart-points"),
  chartInsight: document.querySelector("#chart-insight"),
  audio: document.querySelector("#recording-audio"),
  audioDuration: document.querySelector("#audio-duration"),
  playButton: document.querySelector("#play-recording"),
  playWideButton: document.querySelector("#play-recording-wide"),
  downloadAudio: document.querySelector("#download-audio"),
  transcriptList: document.querySelector("#transcript-list"),
  toggleTranscript: document.querySelector("#toggle-transcript"),
  downloadReport: document.querySelector("#download-report"),
  copyLink: document.querySelector("#copy-link"),
  ratioMain: document.querySelector("#ratio-main"),
  confidenceMain: document.querySelector("#confidence-main"),
  inquiryMain: document.querySelector("#inquiry-main"),
};

let currentReport = null;

const sampleReport = {
  receivedAt: "2026-06-17T10:27:28",
  eventType: "end-of-call-report",
  timestamp: 1781672251799,
  callId: "demo-call-id",
  customerNumber: "+1 229 682 3466",
  transcript:
    "AI: Hello, thank you for requesting an AI voice agent demonstration.\nUser: Hello, could you please help me understand your services?\nAI: Sure, StreamWave offers a family-first streaming experience with premium entertainment, multiple profiles, offline downloads, and parental controls.\nUser: Okay, thank you so much. Have a good day.\nAI: You're welcome, have a great day.",
  recordingUrl: "",
  sentiment: "positive",
  durationSeconds: 50.099,
  durationMinutes: 0.835,
  durationMs: 50099,
  cost: 0.0941,
  summary:
    "The user asked about StreamWave services. The AI explained the service benefits, including multiple profiles, multi-device streaming, offline downloads, and parental controls. The call ended after the user thanked the AI for the information.",
};

function getCallId() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("callId") || params.get("call_id");
  if (fromQuery) return fromQuery.trim();

  const lastSegment = window.location.pathname.split("/").filter(Boolean).pop();
  if (lastSegment && lastSegment !== "index.html" && lastSegment !== "call-report") {
    return decodeURIComponent(lastSegment);
  }
  return "";
}

function getApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("apiBase");
  const configured = window.CALL_REPORT_API_BASE || "";
  return (fromQuery || configured).replace(/\/$/, "");
}

function showState(name) {
  for (const [key, node] of Object.entries({
    missing: elements.missing,
    loading: elements.loading,
    error: elements.error,
    report: elements.report,
  })) {
    node.classList.toggle("hidden", key !== name);
  }
}

function formatDateParts(value) {
  if (!value) return { date: "-", time: "-" };
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { date: String(value), time: "-" };
  return {
    date: date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }),
    time: date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
  };
}

function formatDuration(seconds, minutes, milliseconds) {
  const sec = Number(seconds ?? (milliseconds ? milliseconds / 1000 : 0));
  const min = Number(minutes ?? (sec ? sec / 60 : 0));
  return {
    main: sec ? `${Math.round(sec)} sec` : "-",
    sub: min ? `${min.toFixed(2)} min` : "-",
  };
}

function formatMoney(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? `$${amount.toFixed(2)}` : "-";
}

function normalizeSentiment(value) {
  const sentiment = String(value || "neutral").toLowerCase();
  if (sentiment.includes("positive")) return "positive";
  if (sentiment.includes("negative")) return "negative";
  return "neutral";
}

function sentimentMeta(sentiment) {
  return {
    positive: {
      label: "Positive",
      sub: "Great experience",
      points: [32, 46, 68, 92],
      insight: "Call ended on a positive resolution.",
      confidence: "92%",
    },
    neutral: {
      label: "Neutral",
      sub: "Stable interaction",
      points: [44, 50, 54, 56],
      insight: "Call stayed balanced without strong positive or negative signals.",
      confidence: "78%",
    },
    negative: {
      label: "Negative",
      sub: "Needs review",
      points: [58, 48, 34, 22],
      insight: "Call ended with negative sentiment and should be reviewed.",
      confidence: "64%",
    },
  }[sentiment];
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function buildHighlights(report, sentiment) {
  const highlights = [];
  if (report.customerNumber) highlights.push("Customer number captured for follow-up.");
  if (report.summary) highlights.push(...String(report.summary).split(/(?<=[.!?])\s+/).filter(Boolean).slice(0, 2));
  if (report.recordingUrl) highlights.push("Call recording is available for audit.");
  highlights.push(`Overall customer sentiment is ${sentiment}.`);
  return highlights.slice(0, 4);
}

function parseTranscript(text) {
  if (!text) return [];
  return String(text)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(AI|Assistant|Agent|User|Customer):\s*(.*)$/i);
      if (!match) return { speaker: "Conversation", text: line, type: "ai" };
      const speaker = match[1].toLowerCase().startsWith("user") || match[1].toLowerCase().startsWith("customer")
        ? "User"
        : "AI Agent";
      return { speaker, text: match[2], type: speaker === "User" ? "user" : "ai" };
    });
}

function renderChart(points) {
  const xs = [52, 165, 280, 392];
  const toY = (value) => 168 - (value / 100) * 138;
  const coords = points.map((point, index) => [xs[index], toY(point)]);
  const line = coords.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x} ${y}`).join(" ");
  const fill = `${line} L392 168 L52 168 Z`;

  elements.chartLine.setAttribute("d", line);
  elements.chartFill.setAttribute("d", fill);
  elements.chartPoints.innerHTML = coords
    .map(([x, y]) => `<circle class="chart-point" cx="${x}" cy="${y}" r="6"></circle>`)
    .join("");
}

function renderTranscript(messages) {
  if (!messages.length) {
    elements.transcriptList.innerHTML = '<p class="empty-copy">No transcript received.</p>';
    elements.toggleTranscript.disabled = true;
    return;
  }

  elements.toggleTranscript.disabled = messages.length <= 4;
  elements.transcriptList.innerHTML = messages
    .map((message) => `
      <article class="message ${message.type}">
        <span class="avatar" aria-hidden="true">${message.type === "user" ? "U" : "AI"}</span>
        <div>
          <strong>${escapeHtml(message.speaker)}</strong>
          <p>${escapeHtml(message.text)}</p>
        </div>
      </article>
    `)
    .join("");
}

function estimateTalkRatio(messages) {
  if (!messages.length) return "-";
  const totals = messages.reduce(
    (acc, message) => {
      acc[message.type] += message.text.length;
      return acc;
    },
    { ai: 0, user: 0 },
  );
  const total = totals.ai + totals.user;
  if (!total) return "-";
  return `AI ${Math.round((totals.ai / total) * 100)}%`;
}

function renderReport(report) {
  currentReport = report;
  const sentiment = normalizeSentiment(report.sentiment);
  const sentimentInfo = sentimentMeta(sentiment);
  const dateParts = formatDateParts(report.receivedAt);
  const duration = formatDuration(report.durationSeconds, report.durationMinutes, report.durationMs);
  const messages = parseTranscript(report.transcript);

  document.body.dataset.sentiment = sentiment;
  elements.eventType.textContent = report.eventType || "End-of-call report";
  elements.reportDate.textContent = dateParts.date;
  elements.reportTime.textContent = dateParts.time;
  elements.customerNumber.textContent = report.customerNumber || "Number unavailable";
  elements.durationMain.textContent = duration.main;
  elements.durationSub.textContent = duration.sub;
  elements.sentimentMain.textContent = sentimentInfo.label;
  elements.sentimentSub.textContent = sentimentInfo.sub;
  elements.costMain.textContent = formatMoney(report.cost);
  elements.summaryText.textContent = report.summary || "No summary received.";
  elements.highlights.innerHTML = buildHighlights(report, sentimentInfo.label.toLowerCase())
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  elements.chartInsight.textContent = sentimentInfo.insight;
  elements.confidenceMain.textContent = sentimentInfo.confidence;
  elements.inquiryMain.textContent = report.summary ? "Detected" : "Unknown";
  elements.ratioMain.textContent = estimateTalkRatio(messages);

  renderChart(sentimentInfo.points);
  renderTranscript(messages);

  if (report.recordingUrl) {
    elements.audio.src = report.recordingUrl;
    elements.downloadAudio.href = report.recordingUrl;
    elements.downloadAudio.removeAttribute("aria-disabled");
  } else {
    elements.downloadAudio.href = "#";
    elements.downloadAudio.setAttribute("aria-disabled", "true");
  }

  elements.audioDuration.textContent = duration.main;
  showState("report");
}

async function loadReport() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("demo") === "1") {
    renderReport(sampleReport);
    return;
  }

  const callId = getCallId();
  if (!callId) {
    showState("missing");
    return;
  }

  showState("loading");
  const url = `${getApiBase()}/api/calls/${encodeURIComponent(callId)}`;
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(response.status === 404 ? "No report was found for this call id." : "The report API returned an error.");
    }
    renderReport(await response.json());
  } catch (error) {
    elements.errorMessage.textContent = error.message || "Unable to load this call report.";
    showState("error");
  }
}

function togglePlayback() {
  if (!elements.audio.src) return;
  if (elements.audio.paused) {
    elements.audio.play();
  } else {
    elements.audio.pause();
  }
}

elements.callForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = elements.callInput.value.trim();
  if (!value) return;
  const params = new URLSearchParams(window.location.search);
  params.set("callId", value);
  window.location.search = params.toString();
});

elements.retryButton.addEventListener("click", loadReport);
elements.playButton.addEventListener("click", togglePlayback);
elements.playWideButton.addEventListener("click", togglePlayback);
elements.audio.addEventListener("play", () => {
  elements.playWideButton.textContent = "Pause Recording";
});
elements.audio.addEventListener("pause", () => {
  elements.playWideButton.textContent = "Play Recording";
});
elements.toggleTranscript.addEventListener("click", () => {
  elements.transcriptList.classList.toggle("expanded");
  elements.toggleTranscript.textContent = elements.transcriptList.classList.contains("expanded")
    ? "Collapse Transcript"
    : "View Full Transcript";
});
elements.downloadReport.addEventListener("click", () => {
  if (!currentReport) return;
  const blob = new Blob([JSON.stringify(currentReport, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${currentReport.callId || "call-report"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});
elements.copyLink.addEventListener("click", async () => {
  await navigator.clipboard.writeText(window.location.href);
  elements.copyLink.textContent = "Copied";
  setTimeout(() => {
    elements.copyLink.textContent = "Copy Link";
  }, 1400);
});

loadReport();
