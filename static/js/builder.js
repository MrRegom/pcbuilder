(function () {
  "use strict";

  const WHATSAPP_NUMBER = "56923724818"; // numero publico de Invasion Gamer (visible en su propio sitio)

  const STEPS = JSON.parse(document.getElementById("builder-steps-data").textContent);
  const selections = {}; // step key -> product id
  const chosenCache = {}; // step key -> product object (para mostrar nombre/precio sin refetch)

  const stepsWrap = document.getElementById("builder-steps");
  const overlay = document.getElementById("picker-overlay");
  const pickerTitle = document.getElementById("picker-title");
  const pickerOptions = document.getElementById("picker-options");
  const pickerClose = document.getElementById("picker-close");

  function money(n) {
    if (n === null || n === undefined) return "-";
    return "$" + Math.round(n).toLocaleString("es-CL");
  }

  // ---------------- Animacion de carga a pantalla completa (CSS/JS, sin IA) ----------------
  const FSL_MESSAGES = [
    "Leyendo tu mensaje...",
    "Revisando el catálogo real...",
    "Verificando compatibilidad...",
    "Armando tu recomendación...",
  ];

  function showFullscreenLoading() {
    const el = document.getElementById("fullscreen-loading");
    const textEl = document.getElementById("fsl-text");
    const barFill = el.querySelector(".fsl-bar-fill");
    textEl.textContent = FSL_MESSAGES[0];
    // reinicia la animacion de la barra (si no, la segunda vez no vuelve a correr)
    barFill.style.animation = "none";
    void barFill.offsetWidth;
    barFill.style.animation = "";
    el.hidden = false;

    let i = 0;
    return setInterval(() => {
      i = (i + 1) % FSL_MESSAGES.length;
      textEl.textContent = FSL_MESSAGES[i];
    }, 550);
  }

  function hideFullscreenLoading(timer) {
    clearInterval(timer);
    document.getElementById("fullscreen-loading").hidden = true;
  }

  function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

  // la respuesta real llega casi al instante (todo corre local) asi que se fuerza
  // un mínimo de despliegue para que la animación se alcance a ver.
  async function fetchWithShow(url, minMs = 1300) {
    const [res] = await Promise.all([fetch(url), sleep(minMs)]);
    return res;
  }

  // ---------------- Modo: tabs ----------------
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".mode-tab").forEach((t) => t.classList.remove("is-active"));
      document.querySelectorAll(".mode-panel").forEach((p) => p.classList.remove("is-active"));
      tab.classList.add("is-active");
      document.getElementById("mode-" + tab.dataset.mode).classList.add("is-active");
    });
  });

  // ---------------- Modo recomendado ----------------
  const rResults = document.getElementById("r-results");

  function recommendCardHTML(p) {
    return `
      <a class="card" href="${p.url}" target="_blank" rel="noopener">
        <div class="card-media">${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" loading="lazy">` : ""}</div>
        <div class="card-body">
          <span class="card-brand">${p.brand || "Invasión Gamer"}</span>
          <h3>${p.name}</h3>
          <span class="card-price">${money(p.price_low)}</span>
          <p class="card-reason">${p.reason}</p>
        </div>
      </a>`;
  }

  document.getElementById("r-submit").addEventListener("click", async () => {
    const presupuesto = document.getElementById("r-presupuesto").value || "0";
    const uso = document.getElementById("r-uso").value;
    const timer = showFullscreenLoading();
    const res = await fetchWithShow(`/api/armador/recomendar/?presupuesto=${encodeURIComponent(presupuesto)}&uso=${encodeURIComponent(uso)}`);
    const data = await res.json();
    hideFullscreenLoading(timer);
    if (!data.results.length) {
      rResults.innerHTML = "<p>No encontré equipos armados en stock para ese criterio.</p>";
      return;
    }
    rResults.innerHTML = data.results.map(recommendCardHTML).join("");
  });

  // ---------------- Texto libre (reglas, no IA) ----------------
  const tTexto = document.getElementById("t-texto");
  const tResponse = document.getElementById("t-response");
  const tNotes = document.getElementById("t-notes");
  const tResults = document.getElementById("t-results");

  async function askFreeText(text) {
    if (!text.trim()) return;
    const timer = showFullscreenLoading();

    const res = await fetchWithShow("/api/armador/interpretar/?texto=" + encodeURIComponent(text));
    const data = await res.json();
    hideFullscreenLoading(timer);

    tResponse.hidden = false;
    tNotes.innerHTML = data.notes.map((n) => `<p>💬 ${n}</p>`).join("");

    if (!data.results.length) {
      tResults.innerHTML = "<p>No encontré equipos armados en stock para ese criterio.</p>";
      return;
    }
    tResults.innerHTML = data.results.map(recommendCardHTML).join("");
  }

  document.getElementById("t-submit").addEventListener("click", () => askFreeText(tTexto.value));
  tTexto.addEventListener("keydown", (e) => { if (e.key === "Enter") askFreeText(tTexto.value); });

  // ---------------- Modo por piezas ----------------
  function renderSteps() {
    stepsWrap.innerHTML = STEPS.map((s) => {
      const chosen = chosenCache[s.key];
      return `
        <div class="step-row" data-step="${s.key}">
          <span class="step-label">${s.label}</span>
          <span class="step-choice">
            ${chosen
              ? `<span class="name">${chosen.name}</span><span class="price">${money(chosen.price_low)}</span>`
              : `<span class="empty">Sin elegir</span>`}
          </span>
          <button type="button" class="btn btn-outline" data-pick="${s.key}">${chosen ? "Cambiar" : "Elegir"}</button>
        </div>`;
    }).join("");

    stepsWrap.querySelectorAll("[data-pick]").forEach((btn) => {
      btn.addEventListener("click", () => openPicker(btn.dataset.pick));
    });
  }

  async function openPicker(stepKey) {
    const step = STEPS.find((s) => s.key === stepKey);
    pickerTitle.textContent = "Elegir " + step.label;
    pickerOptions.innerHTML = "<p>Cargando opciones compatibles…</p>";
    overlay.hidden = false;

    const params = new URLSearchParams({ step: stepKey });
    Object.entries(selections).forEach(([k, v]) => { if (v) params.set(k, v); });

    const res = await fetch("/api/armador/opciones/?" + params.toString());
    const data = await res.json();

    if (!data.options.length) {
      pickerOptions.innerHTML = `<p class="picker-empty">No hay ${step.label.toLowerCase()} compatibles en stock con lo que ya elegiste.</p>`;
      return;
    }

    pickerOptions.innerHTML = data.options.map((p) => `
      <a class="card" href="#" data-choose="${p.id}">
        <div class="card-media">${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" loading="lazy">` : ""}</div>
        <div class="card-body">
          <span class="card-brand">${p.brand || p.component_type_label}</span>
          <h3>${p.name}</h3>
          <span class="card-price">${money(p.price_low)}</span>
        </div>
      </a>`).join("");

    pickerOptions.querySelectorAll("[data-choose]").forEach((el) => {
      const product = data.options.find((p) => String(p.id) === el.dataset.choose);
      el.addEventListener("click", (evt) => {
        evt.preventDefault();
        selections[stepKey] = product.id;
        chosenCache[stepKey] = product;
        closePicker();
        renderSteps();
        refreshSummary();
      });
    });
  }

  function closePicker() { overlay.hidden = true; }
  pickerClose.addEventListener("click", closePicker);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closePicker(); });

  const summaryItems = document.getElementById("summary-items");
  const summaryTotal = document.getElementById("summary-total");
  const summaryWarnings = document.getElementById("summary-warnings");
  const whatsappCta = document.getElementById("whatsapp-cta");

  async function refreshSummary() {
    const params = new URLSearchParams();
    Object.entries(selections).forEach(([k, v]) => { if (v) params.set(k, v); });
    const res = await fetch("/api/armador/resumen/?" + params.toString());
    const data = await res.json();

    summaryItems.innerHTML = data.items.map((it) => `
      <div class="summary-item"><span>${it.label}</span><span>${money(it.price)}</span></div>
    `).join("") || `<p class="picker-empty">Todavía no eliges piezas.</p>`;

    summaryTotal.textContent = money(data.total);

    summaryWarnings.innerHTML = data.warnings.map((w) => `<div class="summary-warning">⚠ ${w}</div>`).join("");

    if (data.items.length >= 2) {
      const lines = data.items.map((it) => `• ${it.label}: ${it.name} (${money(it.price)})`);
      const text = `Hola! Arme esta configuración en el prototipo de armador:\n\n${lines.join("\n")}\n\nTotal: ${money(data.total)}\n\n¿Me pueden cotizar esta compatibilidad?`;
      whatsappCta.href = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
      whatsappCta.hidden = false;
    } else {
      whatsappCta.hidden = true;
    }
  }

  renderSteps();
  refreshSummary();
})();
