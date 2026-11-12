"use strict";

const $ = (id) => document.getElementById(id);
const API = ""; // same origin

let state = {
  file: null,
  isVideo: false,
  img: null,          // HTMLImageElement for photos
  rotation: 0,        // 0/90/180/270
  grayscale: false,
};

// ---------- Upload handling ----------
const dz = $("uploadCard");
$("pickBtn").addEventListener("click", (e) => { e.stopPropagation(); $("fileInput").click(); });
dz.addEventListener("click", () => $("fileInput").click());
$("fileInput").addEventListener("change", (e) => handleFile(e.target.files[0]));
["dragover", "dragenter"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("hover"); }));
["dragleave", "drop"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("hover"); }));
dz.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
$("newFileBtn").addEventListener("click", () => location.reload());

async function handleFile(file) {
  if (!file) return;
  state.file = file;
  state.isVideo = file.type.startsWith("video/");
  state.rotation = 0;
  state.grayscale = false;
  $("uploadCard").classList.add("hidden");
  $("results").classList.remove("hidden");

  const canvas = $("canvas");
  const video = $("video");
  if (state.isVideo) {
    canvas.classList.add("hidden");
    video.classList.remove("hidden");
    $("editorControls").classList.add("hidden");
    $("autoCropCard").classList.add("hidden");
    video.src = URL.createObjectURL(file);
  } else {
    video.classList.add("hidden");
    canvas.classList.remove("hidden");
    $("editorControls").classList.remove("hidden");
    $("autoCropCard").classList.remove("hidden");
    const img = new Image();
    img.onload = () => { state.img = img; drawCanvas(); };
    img.src = URL.createObjectURL(file);
  }
  await analyze(file);
}

// ---------- Canvas editor ----------
function currentFilter() {
  const b = 100 + Number($("brightness").value);       // %
  const c = 100 + Number($("contrast").value);          // %
  const s = state.grayscale ? 0 : Number($("saturation").value);
  return `brightness(${b}%) contrast(${c}%) saturate(${s}%)`;
}
function drawCanvas() {
  if (!state.img) return;
  const canvas = $("canvas");
  const ctx = canvas.getContext("2d");
  const rot = state.rotation % 360;
  const swap = rot === 90 || rot === 270;
  const iw = state.img.naturalWidth, ih = state.img.naturalHeight;
  canvas.width = swap ? ih : iw;
  canvas.height = swap ? iw : ih;
  ctx.save();
  ctx.filter = currentFilter();
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.rotate((rot * Math.PI) / 180);
  ctx.drawImage(state.img, -iw / 2, -ih / 2);
  ctx.restore();
}
["brightness", "contrast", "saturation"].forEach((id) =>
  $(id).addEventListener("input", drawCanvas));
$("rotateBtn").addEventListener("click", () => { state.rotation = (state.rotation + 90) % 360; drawCanvas(); });
$("grayscaleBtn").addEventListener("click", () => { state.grayscale = !state.grayscale; drawCanvas(); });
$("resetBtn").addEventListener("click", () => {
  $("brightness").value = 0; $("contrast").value = 0; $("saturation").value = 100;
  state.rotation = 0; state.grayscale = false; drawCanvas();
});
$("downloadEditBtn").addEventListener("click", () => {
  $("canvas").toBlob((blob) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "edited.jpg";
    a.click();
  }, "image/jpeg", 0.95);
});
$("safeZoneToggle").addEventListener("change", (e) =>
  $("safeZone").classList.toggle("hidden", !e.target.checked));

// ---------- Analyze ----------
async function analyze(file) {
  setScore(null, "Analyzing…", "");
  $("tips").innerHTML = "";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(`${API}/api/analyze`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    renderAnalysis(await res.json());
  } catch (err) {
    setScore(null, "Error", "bad");
    $("tips").innerHTML = `<li class="bad">${err.message}</li>`;
  }
}

function setScore(num, verdictText, cls) {
  $("scoreNum").textContent = num == null ? "--" : num;
  const ring = $("scoreRing");
  const deg = num == null ? 0 : (num / 100) * 360;
  const color = cls === "good" ? "var(--good)" : cls === "okay" ? "var(--okay)"
    : cls === "bad" ? "var(--bad)" : "var(--accent)";
  ring.style.background = `conic-gradient(${color} ${deg}deg, var(--panel-2) 0deg)`;
  const v = $("verdict");
  v.textContent = verdictText;
  v.className = "verdict " + (cls || "");
}

function renderAnalysis(data) {
  const cls = data.verdict === "Good" ? "good" : data.verdict === "Okay" ? "okay" : "bad";
  setScore(data.score, `${data.verdict_bn} (${data.verdict})`, cls);

  $("tips").innerHTML = data.tips.map((t) =>
    `<li class="${t.category === "ok" ? "ok" : ""}">${t.bn}<span class="en">${t.en}</span></li>`
  ).join("");

  const m = data.metrics;
  const rows = [];
  const push = (k, v) => rows.push(`<div><b>${k}</b><span>${v}</span></div>`);
  push("Resolution", `${m.width}×${m.height}`);
  push("Aspect ratio", m.aspect_ratio);
  if (data.type === "photo") {
    push("Blur (sharpness)", m.blur);
    push("Brightness", m.brightness);
    push("Contrast", m.contrast);
    push("Noise", m.noise);
    push("Faces detected", m.faces.length);
  } else {
    push("Duration", `${m.duration_seconds}s`);
    push("FPS", m.fps);
    push("Shakiness", m.shakiness);
    push("Brightness", m.brightness);
  }
  $("metrics").innerHTML = rows.join("");

  renderPlatforms(data.platform_fit, data.type);
  renderPoseHint(data);
}

function renderPlatforms(fits, type) {
  const isPhoto = type === "photo";
  $("fitAllBtn").classList.toggle("hidden", !isPhoto);
  $("platformGrid").innerHTML = fits.map((f) => {
    const p = f.platform;
    const lenOk = !f.length || f.length.fits;
    const ok = f.fits && lenOk;
    const icon = ok ? "✅" : "⚠️";
    const msgs = f.messages.slice();
    if (f.length && !f.length.fits) msgs.push(f.length.message);
    const fixBtn = isPhoto
      ? `<div class="pf-actions">
           <button class="btn mini fix-btn" data-pid="${p.id}" data-pname="${p.name}">✂️ Fix &amp; download</button>
         </div>
         <div class="pf-thumb" id="thumb-${p.id}"></div>`
      : "";
    return `<div class="pf ${ok ? "fit" : "nofit"}">
      <div class="pf-head"><span class="pf-name">${p.name}</span><span class="pf-status">${icon}</span></div>
      <div class="pf-spec">${p.width}×${p.height} · ${p.ratio}${type === "video" && p.max_video_seconds ? " · max " + p.max_video_seconds + "s" : ""}</div>
      <div class="pf-msg">${msgs.join("<br>")}</div>
      ${fixBtn}
    </div>`;
  }).join("");
}

// Per-platform "Fix & download" (event delegation)
$("platformGrid").addEventListener("click", async (e) => {
  const btn = e.target.closest(".fix-btn");
  if (!btn || !state.file || state.isVideo) return;
  const pid = btn.dataset.pid;
  const thumb = $(`thumb-${pid}`);
  btn.disabled = true; btn.textContent = "…";
  try {
    const fd = new FormData();
    fd.append("file", state.file);
    fd.append("platform_id", pid);
    fd.append("fmt", "JPEG");
    const res = await fetch(`${API}/api/fit`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    thumb.innerHTML = `<a href="${url}" download="${pid}.jpg"><img src="${url}" alt="${pid}"/></a>
      <span class="muted">click to download</span>`;
    // Auto-download too.
    const a = document.createElement("a"); a.href = url; a.download = `${pid}.jpg`; a.click();
  } catch (err) {
    thumb.innerHTML = `<span class="muted">Error: ${err.message}</span>`;
  } finally {
    btn.disabled = false; btn.innerHTML = "✂️ Fix &amp; download";
  }
});

// Fit for ALL platforms -> ZIP
$("fitAllBtn").addEventListener("click", async () => {
  if (!state.file || state.isVideo) return;
  const btn = $("fitAllBtn");
  btn.disabled = true; const old = btn.textContent; btn.textContent = "Generating ZIP…";
  try {
    const fd = new FormData();
    fd.append("file", state.file);
    fd.append("fmt", "JPEG");
    const res = await fetch(`${API}/api/fit_all`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "all_platforms.zip";
    a.click();
  } catch (err) {
    alert("Fit-all failed: " + err.message);
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
});

// ---------- Platforms list + Auto crop ----------
async function loadPlatforms() {
  try {
    const res = await fetch(`${API}/api/platforms`);
    const { platforms } = await res.json();
    $("cropPlatform").innerHTML = platforms
      .map((p) => `<option value="${p.id}">${p.name} (${p.width}×${p.height})</option>`)
      .join("");
  } catch { /* backend not up yet */ }
  try {
    const h = await (await fetch(`${API}/health`)).json();
    const badge = $("ffmpegBadge");
    badge.classList.remove("hidden");
    badge.textContent = h.ffmpeg ? "video convert: on" : "video convert: off (no ffmpeg)";
  } catch { /* ignore */ }
}

$("cropBtn").addEventListener("click", async () => {
  if (!state.file || state.isVideo) return;
  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("platform_id", $("cropPlatform").value);
  fd.append("fmt", "JPEG");
  $("cropResult").innerHTML = "<p class='muted'>Generating…</p>";
  try {
    const res = await fetch(`${API}/api/fit`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const w = res.headers.get("X-Fit-Width"), h = res.headers.get("X-Fit-Height");
    $("cropResult").innerHTML = `<img src="${url}" alt="cropped" /><p class="muted">${w}×${h}</p>`;
    const dl = $("cropDownload");
    dl.href = url;
    dl.download = `${$("cropPlatform").value}.jpg`;
    dl.classList.remove("hidden");
  } catch (err) {
    $("cropResult").innerHTML = `<p class="muted">Error: ${err.message}</p>`;
  }
});

// ---------- Pose & Shooting Coach ----------
function grid(w, h) {
  const s = 'stroke="rgba(255,255,255,.22)" stroke-width="1"';
  return `<rect x="1.5" y="1.5" width="${w - 3}" height="${h - 3}" rx="4" fill="none" stroke="rgba(255,255,255,.45)" stroke-width="2"/>
    <line x1="${w / 3}" y1="4" x2="${w / 3}" y2="${h - 4}" ${s}/>
    <line x1="${2 * w / 3}" y1="4" x2="${2 * w / 3}" y2="${h - 4}" ${s}/>
    <line x1="4" y1="${h / 3}" x2="${w - 4}" y2="${h / 3}" ${s}/>
    <line x1="4" y1="${2 * h / 3}" x2="${w - 4}" y2="${2 * h / 3}" ${s}/>`;
}
function person(cx, headY, r, color) {
  color = color || "#6c8cff";
  return `<g fill="${color}"><circle cx="${cx}" cy="${headY}" r="${r}"/>
    <path d="M ${cx - 2.4 * r} ${headY + 8 * r} L ${cx - 1.5 * r} ${headY + 2.2 * r}
    Q ${cx} ${headY + 1.1 * r} ${cx + 1.5 * r} ${headY + 2.2 * r}
    L ${cx + 2.4 * r} ${headY + 8 * r} Z"/></g>`;
}
function dot(x, y) { return `<circle cx="${x}" cy="${y}" r="3.2" fill="#34d399"/>`; }

const POSES = {
  photo: [
    {
      id: "thirds", title: "Rule of Thirds",
      svg: `<svg viewBox="0 0 120 150">${grid(120, 150)}${person(40, 50, 6)}${dot(40, 50)}</svg>`,
      tips: [
        { bn: "Mukh/chokh upor-er third line-e rakhun (majhkhane noy).", en: "Put the face/eyes on the upper third line, not dead center." },
        { bn: "Subject-ke ekta grid intersection-e boshan.", en: "Place the subject on a grid intersection." },
      ], triggers: ["composition"],
    },
    {
      id: "framing", title: "Headroom & Framing",
      svg: `<svg viewBox="0 0 120 150">${grid(120, 150)}
        ${person(60, 40, 7)}
        <text x="60" y="18" fill="#fbbf24" font-size="9" text-anchor="middle">headroom ↕</text></svg>`,
      tips: [
        { bn: "Mathar upore ektu jayga (headroom) rakhun — mukh kete jeno na jay.", en: "Leave a little headroom — don't cut off the head." },
        { bn: "Full-body hole pa-o frame-e rakhun.", en: "For full body, keep the feet in frame too." },
      ], triggers: ["composition"],
    },
    {
      id: "lighting", title: "Light & Angle",
      svg: `<svg viewBox="0 0 120 150">${grid(120, 150)}
        <circle cx="20" cy="30" r="9" fill="#fbbf24"/>
        <line x1="28" y1="36" x2="48" y2="52" stroke="#fbbf24" stroke-width="2"/>
        ${person(70, 55, 6)}</svg>`,
      tips: [
        { bn: "Alo-r dike mukh korun (janala/soft light). Backlight edan.", en: "Face the light (window/soft light). Avoid backlight." },
        { bn: "Camera ektu upor theke — jawline sundor dekhabe.", en: "Shoot slightly from above — flatters the jawline." },
      ], triggers: ["brightness", "contrast", "noise", "blur"],
    },
    {
      id: "group", title: "Group Photo",
      svg: `<svg viewBox="0 0 120 150">${grid(120, 150)}
        ${person(35, 55, 5)}${person(60, 48, 5.5)}${person(85, 55, 5)}</svg>`,
      tips: [
        { bn: "Height alada korun (keu boshbe, keu darabe), majhe gap kom.", en: "Stagger heights (some sit, some stand); minimize gaps." },
        { bn: "Shobai ektu bhitor-er dike jhukun, frame bhorun.", en: "Everyone lean slightly inward; fill the frame." },
      ], triggers: [],
    },
  ],
  video: [
    {
      id: "vertical", title: "Vertical (Reels/Story/TikTok)",
      svg: `<svg viewBox="0 0 90 150">${grid(90, 150)}
        <rect x="3" y="3" width="84" height="20" fill="rgba(248,113,113,.28)"/>
        <rect x="3" y="124" width="84" height="23" fill="rgba(248,113,113,.28)"/>
        ${person(45, 60, 8)}
        <text x="45" y="16" fill="#fff" font-size="7" text-anchor="middle">UI zone</text></svg>`,
      tips: [
        { bn: "9:16 vertical-e phone dhorun. Subject center safe-zone-e rakhun.", en: "Hold the phone vertical (9:16). Keep the subject in the center safe zone." },
        { bn: "Upor/niche-r lal jaygay important kichu rakhben na.", en: "Keep key content out of the red top/bottom UI zones." },
      ], triggers: ["resolution"],
    },
    {
      id: "horizontal", title: "Horizontal (YouTube)",
      svg: `<svg viewBox="0 0 160 90">${grid(160, 90)}${person(54, 34, 6)}${dot(53, 30)}</svg>`,
      tips: [
        { bn: "YouTube-er jonno 16:9 landscape-e tulun, eye-level e.", en: "For YouTube shoot 16:9 landscape, at eye level." },
        { bn: "Subject-ke third line-e boshie samne takate din (look room).", en: "Place the subject on a third line, leaving look room ahead." },
      ], triggers: [],
    },
    {
      id: "steady", title: "Hold Steady",
      svg: `<svg viewBox="0 0 160 90">
        <rect x="66" y="20" width="28" height="50" rx="5" fill="#6c8cff"/>
        <rect x="70" y="26" width="20" height="34" fill="#0b0d12"/>
        <path d="M40 45 H58" stroke="#34d399" stroke-width="3"/><path d="M58 40 L58 50 L50 45 Z" fill="#34d399"/>
        <path d="M120 45 H102" stroke="#34d399" stroke-width="3"/><path d="M102 40 L102 50 L110 45 Z" fill="#34d399"/>
        <text x="80" y="84" fill="#9aa0b0" font-size="9" text-anchor="middle">brace / gimbal</text></svg>`,
      tips: [
        { bn: "Kunui shorire chepe dhorun ba gimbal use korun — shaky komabe.", en: "Tuck elbows to your body or use a gimbal — reduces shake." },
        { bn: "Pan/move khub aste korun, jhatka noy.", en: "Pan/move slowly and smoothly, no jerks." },
      ], triggers: ["shaky", "blur", "fps"],
    },
    {
      id: "vlight", title: "Lighting & Background",
      svg: `<svg viewBox="0 0 160 90">${grid(160, 90)}
        <circle cx="20" cy="24" r="9" fill="#fbbf24"/>
        <line x1="28" y1="30" x2="55" y2="42" stroke="#fbbf24" stroke-width="2"/>
        ${person(90, 34, 6)}</svg>`,
      tips: [
        { bn: "Alo mukh-er samne rakhun. Andhokar hole noise/grain barbe.", en: "Keep light in front of the face. Darkness adds noise/grain." },
        { bn: "Background porishkar rakhun, distraction komabe.", en: "Keep the background clean to reduce distraction." },
      ], triggers: ["brightness", "contrast", "noise"],
    },
  ],
};

let poseMode = "photo";

function renderPoses() {
  const cats = new Set((state.lastAnalysis?.tips || []).map((t) => t.category));
  $("poseGuides").innerHTML = POSES[poseMode].map((p) => {
    const hot = p.triggers.some((t) => cats.has(t));
    return `<div class="pose ${hot ? "highlight" : ""}">
      ${p.svg}
      <h4>${p.title}${hot ? " ⭐" : ""}</h4>
      <ul>${p.tips.map((t) => `<li>${t.bn}<br><span class="en">${t.en}</span></li>`).join("")}</ul>
    </div>`;
  }).join("");
}

function renderPoseHint(data) {
  // Switch to the matching mode for the uploaded media, then show a tailored hint.
  poseMode = data.type === "video" ? "video" : "photo";
  [...document.querySelectorAll("#poseTabs button")].forEach((b) =>
    b.classList.toggle("primary", b.dataset.mode === poseMode));

  const cats = new Set(data.tips.map((t) => t.category));
  const hint = $("poseHint");
  const names = POSES[poseMode].filter((p) => p.triggers.some((t) => cats.has(t))).map((p) => p.title);
  if (names.length && !cats.has("ok")) {
    hint.classList.remove("hidden");
    hint.innerHTML = `Apnar ${data.type}-er jonno ei guide-gulo dekhun (⭐): <b>${names.join(", ")}</b>.
      <span class="en" style="color:var(--muted)"> — focus on the starred guides below.</span>`;
  } else {
    hint.classList.add("hidden");
  }
  renderPoses();
}

$("poseTabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-mode]");
  if (!b) return;
  poseMode = b.dataset.mode;
  [...document.querySelectorAll("#poseTabs button")].forEach((x) =>
    x.classList.toggle("primary", x === b));
  renderPoses();
});

// Store analysis for pose context + initial render.
const _origRenderAnalysis = renderAnalysis;
renderAnalysis = function (data) { state.lastAnalysis = data; _origRenderAnalysis(data); };
renderPoses();

loadPlatforms();
