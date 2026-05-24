const canvas = document.getElementById("trafficCanvas");
const ctx = canvas.getContext("2d");
const chartCanvas = document.getElementById("volumeChart");
const chartCtx = chartCanvas.getContext("2d");
const controlIds = ["carVolume", "motorVolume", "entryFlow", "exitFlow", "patience"];
let snapshot = { vehicles: [], metrics: {} };
let running = true;
let busy = false;
let history = [];
let resetTimer;

function params() {
  return {
    carVolume: Number(document.getElementById("carVolume").value),
    motorVolume: Number(document.getElementById("motorVolume").value),
    entryFlow: Number(document.getElementById("entryFlow").value),
    exitFlow: Number(document.getElementById("exitFlow").value),
    patience: Number(document.getElementById("patience").value),
    seed: document.getElementById("seed").value,
  };
}

function syncOutputs() {
  for (const id of controlIds) {
    document.getElementById(`${id}Value`).value = document.getElementById(id).value;
  }
}

function updateClock() {
  const formatter = new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "medium",
  });
  document.getElementById("clock").textContent = formatter.format(new Date());
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function reset() {
  syncOutputs();
  history = [];
  snapshot = await postJson("/api/reset", params());
  updateStats();
  draw();
}

async function step() {
  if (!running || busy) return;
  busy = true;
  try {
    snapshot = await postJson("/api/step", { steps: 2 });
    updateStats();
    draw();
  } finally {
    busy = false;
  }
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function updateStats() {
  const metrics = snapshot.metrics || {};
  const congestion = Number(metrics.congestion || 0);

  setText("congestion", `${congestion}%`);
  setText("active", metrics.active || 0);
  setText("carWaiting", metrics.carWaiting || 0);
  setText("motorWaiting", metrics.motorWaiting || 0);
  setText("avgSpeed", `${metrics.avgSpeed || 0}`);
  setText("nearCollisions", metrics.nearCollisions || 0);
  setText("overlayActive", metrics.active || 0);
  setText("overlayCarWaiting", metrics.carWaiting || 0);
  setText("overlayCongestion", `${congestion}%`);
  setText("totalVehicles", metrics.active || 0);

  const congestionElement = document.getElementById("congestion");
  congestionElement.classList.toggle("green", congestion < 40);
  congestionElement.classList.toggle("yellow", congestion >= 40 && congestion <= 80);
  congestionElement.classList.toggle("red", congestion > 80);
  document.getElementById("congestionCard").classList.toggle("alert", congestion > 80);

  history.push(Number(metrics.active || 0));
  if (history.length > 72) history.shift();
  drawChart();
  renderVehicleList();
}

function drawRoads() {
  ctx.fillStyle = "#1e1f1f";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const grid = 32;
  ctx.strokeStyle = "rgba(219,214,208,0.06)";
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += grid) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += grid) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  ctx.lineCap = "butt";
  ctx.lineJoin = "round";

  ctx.strokeStyle = "#111212";
  ctx.lineWidth = 78;
  ctx.beginPath();
  ctx.moveTo(960, 238);
  ctx.lineTo(-40, 238);
  ctx.stroke();

  ctx.strokeStyle = "rgba(220,86,72,0.62)";
  ctx.lineWidth = 84;
  ctx.beginPath();
  ctx.moveTo(710, 660);
  ctx.lineTo(610, 512);
  ctx.lineTo(510, 355);
  ctx.lineTo(430, 238);
  ctx.stroke();

  ctx.strokeStyle = "rgba(219,214,208,0.74)";
  ctx.lineWidth = 94;
  ctx.beginPath();
  ctx.moveTo(330, 660);
  ctx.lineTo(330, 278);
  ctx.lineTo(390, 238);
  ctx.stroke();

  ctx.strokeStyle = "rgba(219,214,208,0.55)";
  ctx.lineWidth = 3;
  ctx.setLineDash([20, 18]);
  ctx.beginPath();
  ctx.moveTo(930, 238);
  ctx.lineTo(0, 238);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "rgba(220,86,72,0.16)";
  ctx.beginPath();
  ctx.arc(395, 244, 58, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(220,86,72,0.54)";
  ctx.lineWidth = 1;
  ctx.stroke();

  labelPill("Jalur lambat satu arah ke kiri", 600, 188, "rgba(30,31,31,0.82)", "#dbd6d0");
  labelPill("Masuk mall", 216, 430, "rgba(30,31,31,0.82)", "#dbd6d0");
  labelPill("Keluar mall", 558, 430, "rgba(30,31,31,0.82)", "#dc5648");
}

function labelPill(text, x, y, background, color) {
  ctx.save();
  ctx.font = "400 13px Inter, sans-serif";
  const metrics = ctx.measureText(text);
  ctx.fillStyle = background;
  roundRect(ctx, x - 12, y - 19, metrics.width + 24, 28, 14);
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
  ctx.restore();
}

function drawArrow(x, y, angle, color) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(-18, -8);
  ctx.lineTo(-18, 8);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function roundRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}

function drawVehicle(vehicle) {
  ctx.save();
  ctx.translate(vehicle.x, vehicle.y);
  ctx.rotate(vehicle.angle);
  ctx.globalAlpha = vehicle.waiting ? 0.72 : 1;
  ctx.fillStyle = vehicle.type === "car" ? "#dbd6d0" : "#1e1f1f";
  ctx.strokeStyle = vehicle.nearCollision ? "#dc5648" : "#dbd6d0";
  ctx.lineWidth = vehicle.nearCollision ? 4 : 1.4;
  roundRect(ctx, -vehicle.length / 2, -vehicle.width / 2, vehicle.length, vehicle.width, 4);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function draw() {
  drawRoads();
  drawArrow(70, 238, Math.PI, "rgba(219,214,208,0.9)");
  drawArrow(330, 548, Math.PI / 2, "rgba(30,31,31,0.95)");
  drawArrow(542, 380, -2.14, "rgba(219,214,208,0.92)");
  for (const vehicle of snapshot.vehicles || []) drawVehicle(vehicle);
}

function drawChart() {
  const width = chartCanvas.width;
  const height = chartCanvas.height;
  const maxValue = Math.max(1, ...history);
  setText("chartPeak", `Peak ${maxValue}`);
  chartCtx.clearRect(0, 0, width, height);
  chartCtx.fillStyle = "#1e1f1f";
  chartCtx.fillRect(0, 0, width, height);

  chartCtx.strokeStyle = "rgba(219,214,208,0.18)";
  chartCtx.lineWidth = 1;
  for (let i = 1; i < 4; i += 1) {
    const y = (height / 4) * i;
    chartCtx.beginPath();
    chartCtx.moveTo(0, y);
    chartCtx.lineTo(width, y);
    chartCtx.stroke();
  }

  if (history.length < 2) return;

  const points = history.map((value, index) => ({
    x: (index / (history.length - 1)) * width,
    y: height - (value / maxValue) * (height - 16) - 8,
  }));

  chartCtx.beginPath();
  chartCtx.moveTo(points[0].x, height);
  for (const point of points) chartCtx.lineTo(point.x, point.y);
  chartCtx.lineTo(points[points.length - 1].x, height);
  chartCtx.closePath();
  chartCtx.fillStyle = "rgba(219,214,208,0.1)";
  chartCtx.fill();

  chartCtx.beginPath();
  for (const [index, point] of points.entries()) {
    if (index === 0) chartCtx.moveTo(point.x, point.y);
    else chartCtx.lineTo(point.x, point.y);
  }
  chartCtx.strokeStyle = "#dbd6d0";
  chartCtx.lineWidth = 2;
  chartCtx.stroke();
}

function routeLabel(route) {
  if (route === "entry") return "Jalan Utama -> Masuk Mall";
  if (route === "exit") return "Keluar Mall -> Jalan Utama";
  return "Jalan Utama -> Jalan Utama";
}

function vehicleCode(vehicle) {
  const prefix = vehicle.type === "motor" ? "MOT" : "MOB";
  return `#${prefix}-${String(vehicle.id).padStart(4, "0")}`;
}

function statusFor(vehicle) {
  if (vehicle.nearCollision) return ["Macet", "badge-jam"];
  if (vehicle.waiting) return ["Menunggu", "badge-waiting"];
  return ["Bergerak", "badge-moving"];
}

function renderVehicleList() {
  const list = document.getElementById("vehicleList");
  const vehicles = [...(snapshot.vehicles || [])]
    .sort((a, b) => Number(b.waiting) - Number(a.waiting) || b.waitTime - a.waitTime)
    .slice(0, 8);
  setText("queueCount", `${vehicles.length} item`);

  if (!vehicles.length) {
    list.innerHTML = '<div class="vehicle-item"><p>Belum ada kendaraan aktif.</p></div>';
    return;
  }

  list.innerHTML = vehicles
    .map((vehicle) => {
      const [status, className] = statusFor(vehicle);
      const wait = vehicle.waiting ? `${vehicle.waitTime || 0} detik` : "-";
      const type = vehicle.type === "car" ? "Mobil" : "Motor";
      return `
        <article class="vehicle-item">
          <div class="vehicle-title">
            <strong>${vehicleCode(vehicle)}</strong>
            <span class="badge ${className}">${status}</span>
          </div>
          <p>Rute: ${routeLabel(vehicle.route)}</p>
          <p>Est. tunggu: ${wait}</p>
          <p>Jenis: ${type}</p>
        </article>
      `;
    })
    .join("");
}

for (const id of controlIds) {
  document.getElementById(id).addEventListener("input", () => {
    syncOutputs();
    clearTimeout(resetTimer);
    resetTimer = setTimeout(reset, 180);
  });
}

document.getElementById("seed").addEventListener("change", reset);
document.getElementById("reset").addEventListener("click", reset);
document.getElementById("toggleRun").addEventListener("click", () => {
  running = !running;
  document.getElementById("toggleRun").textContent = running ? "Pause" : "Lanjut";
});
document.getElementById("fullscreen").addEventListener("click", () => {
  document.querySelector(".canvas-wrapper").requestFullscreen?.();
});

syncOutputs();
updateClock();
draw();
drawChart();
reset();
setInterval(step, 80);
setInterval(updateClock, 1000);
