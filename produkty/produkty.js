(() => {
  const CATALOG_URL = "/api/catalog";
  const FALLBACK_URL = "/storage/catalog.json";

  const state = {
    products: [],
    query: "",
    category: "all",
    stock: "all",
  };

  const $ = (sel) => document.querySelector(sel);

  function productList(payload) {
    const raw = payload && payload.products;
    if (Array.isArray(raw)) return raw;
    if (raw && typeof raw === "object") return Object.values(raw);
    return [];
  }

  function productHref(p) {
    const slug = encodeURIComponent(p.slug || p.id || "");
    return `/bg/produkt/${slug}`;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function filtered() {
    const q = state.query.trim().toLowerCase();
    return state.products.filter((p) => {
      if (p.archived) return false;
      if (state.category !== "all" && (p.category || "") !== state.category) return false;
      if (state.stock === "in" && !p.in_stock) return false;
      if (state.stock === "out" && p.in_stock) return false;
      if (!q) return true;
      const hay = `${p.title || ""} ${p.category || ""} ${p.lab_label || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }

  function fillCategories() {
    const cats = [...new Set(state.products.map((p) => p.category).filter(Boolean))].sort(
      (a, b) => a.localeCompare(b, "bg")
    );
    const sel = $("#category-filter");
    sel.innerHTML =
      `<option value="all">Всички категории</option>` +
      cats.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  }

  function render() {
    const items = filtered();
    $("#count-label").textContent = `${items.length} продукта`;
    const grid = $("#product-grid");
    const empty = $("#empty-state");
    if (!items.length) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    grid.innerHTML = items
      .map((p) => {
        const img = p.image
          ? `<img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.title)}" loading="lazy" />`
          : `<span style="color:#8b968f">Няма снимка</span>`;
        const stockClass = p.in_stock ? "" : "out";
        const stockText = p.stock_text || (p.in_stock ? "В наличност" : "Изчерпан");
        return `
          <a class="card" href="${productHref(p)}">
            <div class="card-media">${img}</div>
            <div class="card-body">
              <div class="card-cat">${escapeHtml(p.category || "")}</div>
              <h2 class="card-title">${escapeHtml(p.title || p.id)}</h2>
              <div class="card-meta">
                <span class="price">${escapeHtml(p.price_text || "")}</span>
                <span class="stock ${stockClass}">${escapeHtml(stockText)}</span>
              </div>
            </div>
          </a>`;
      })
      .join("");
  }

  async function loadCatalog() {
    $("#status").textContent = "Зареждане на продукти…";
    $("#status").classList.remove("hidden");
    let payload = null;
    for (const url of [`${CATALOG_URL}?t=${Date.now()}`, FALLBACK_URL]) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) continue;
        payload = await res.json();
        break;
      } catch {
        /* try next */
      }
    }
    $("#status").classList.add("hidden");
    state.products = productList(payload).sort((a, b) =>
      String(a.title || "").localeCompare(String(b.title || ""), "bg")
    );
    fillCategories();
    render();
  }

  function bind() {
    $("#search-input").addEventListener("input", (e) => {
      state.query = e.target.value || "";
      render();
    });
    $("#category-filter").addEventListener("change", (e) => {
      state.category = e.target.value || "all";
      render();
    });
    $("#stock-filter").addEventListener("change", (e) => {
      state.stock = e.target.value || "all";
      render();
    });
  }

  bind();
  loadCatalog();
})();
