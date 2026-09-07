(function () {
  "use strict";

  const els = {
    q: document.getElementById("f-q"),
    tipo: document.getElementById("f-tipo"),
    marca: document.getElementById("f-marca"),
    precioMin: document.getElementById("f-precio-min"),
    precioMax: document.getElementById("f-precio-max"),
    stock: document.getElementById("f-stock"),
    orden: document.getElementById("f-orden"),
    reset: document.getElementById("f-reset"),
    grid: document.getElementById("result-grid"),
    count: document.getElementById("result-count"),
    loadMore: document.getElementById("load-more"),
  };

  let currentPage = 1;
  let debounceTimer = null;

  function money(n) {
    if (n === null || n === undefined) return "-";
    return "$" + Math.round(n).toLocaleString("es-CL");
  }

  function buildParams(page) {
    const p = new URLSearchParams();
    if (els.q.value.trim()) p.set("q", els.q.value.trim());
    if (els.tipo.value) p.set("tipo", els.tipo.value);
    if (els.marca.value) p.set("marca", els.marca.value);
    if (els.precioMin.value) p.set("precio_min", els.precioMin.value);
    if (els.precioMax.value) p.set("precio_max", els.precioMax.value);
    if (els.stock.checked) p.set("stock", "1");
    p.set("orden", els.orden.value);
    p.set("page", page);
    return p;
  }

  function cardHTML(p) {
    const cornerBadge = p.discount_pct > 0
      ? `<span class="card-badge-corner badge-discount">-${p.discount_pct}% OFF</span>`
      : (!p.in_stock ? `<span class="card-badge-corner badge-out-corner">Agotado</span>` : "");

    return `
      <a class="card" href="${p.url}" target="_blank" rel="noopener">
        <div class="card-media">
          ${cornerBadge}
          ${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" loading="lazy">` : ""}
        </div>
        <div class="card-body">
          <span class="card-brand">${p.brand || p.component_type_label}</span>
          <h3>${p.name}</h3>
          ${p.in_stock ? `<span class="card-badge badge-stock">Stock</span>` : ""}
          <span class="card-price">
            ${p.discount_pct > 0 ? `<span class="card-price-old">${money(p.price_high)}</span>` : ""}
            ${money(p.price_low)}
          </span>
        </div>
      </a>`;
  }

  async function runSearch(page) {
    currentPage = page || 1;
    els.count.textContent = "Buscando…";
    const res = await fetch("/api/productos/?" + buildParams(currentPage).toString());
    const data = await res.json();

    if (currentPage === 1) {
      els.grid.innerHTML = data.results.map(cardHTML).join("");
    } else {
      els.grid.insertAdjacentHTML("beforeend", data.results.map(cardHTML).join(""));
    }

    els.count.textContent = `${data.total} producto${data.total === 1 ? "" : "s"} encontrado${data.total === 1 ? "" : "s"}`;
    els.loadMore.hidden = !data.has_next;
  }

  function debouncedSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => runSearch(1), 250);
  }

  [els.q, els.precioMin, els.precioMax].forEach((el) => el.addEventListener("input", debouncedSearch));
  [els.tipo, els.marca, els.stock, els.orden].forEach((el) => el.addEventListener("change", () => runSearch(1)));

  els.reset.addEventListener("click", () => {
    els.q.value = "";
    els.tipo.value = "";
    els.marca.value = "";
    els.precioMin.value = "";
    els.precioMax.value = "";
    els.stock.checked = true;
    els.orden.value = "relevancia";
    runSearch(1);
  });

  els.loadMore.addEventListener("click", () => runSearch(currentPage + 1));

  // leer query params iniciales (para poder linkear una busqueda desde el armador, etc.)
  const initial = new URLSearchParams(window.location.search);
  if (initial.get("tipo")) els.tipo.value = initial.get("tipo");
  if (initial.get("q")) els.q.value = initial.get("q");

  runSearch(1);
})();
