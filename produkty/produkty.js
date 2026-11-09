(() => {
  const CATALOG_URL = "/api/catalog";
  const FALLBACK_URL = "/storage/catalog.json";
  const PC = "ProductCard-module__ba2BAq__";

  const state = {
    products: [],
    category: "all",
    inStockOnly: false,
    priceFrom: null,
    priceTo: null,
  };

  const $ = (sel) => document.querySelector(sel);

  function productList(payload) {
    const raw = payload && payload.products;
    if (Array.isArray(raw)) return raw;
    if (raw && typeof raw === "object") return Object.values(raw);
    return [];
  }

  function isVisibleProduct(p) {
    if (!p || p.archived) return false;
    // Products without images / banned categories are deleted from the DB.
    // Keep a hard guard so empty image rows never render if any reappear.
    return Boolean(String(p.image || "").trim());
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function money(n) {
    const v = Number(n) || 0;
    return (
      v.toLocaleString("bg-BG", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + "\u00a0€"
    );
  }

  function typeLabel(p) {
    const cat = (p.category || "").trim();
    const lab = (p.lab_label || "").trim();
    if (cat && lab && lab.toLowerCase() !== cat.toLowerCase()) return `${cat} · ${lab}`;
    return cat || lab || "Продукт";
  }

  function hrefFor(p) {
    return `/bg/produkt/${encodeURIComponent(p.slug || p.id || "")}`;
  }

  function filtered() {
    return state.products.filter((p) => {
      if (!isVisibleProduct(p)) return false;
      if (state.category !== "all" && (p.category || "") !== state.category) return false;
      if (state.inStockOnly && !p.in_stock) return false;
      const price = Number(p.price) || 0;
      if (state.priceFrom != null && price < state.priceFrom) return false;
      if (state.priceTo != null && price > state.priceTo) return false;
      return true;
    });
  }

  function cardHtml(p) {
    const img = esc(p.image || "");
    const title = esc(p.title || p.id || "");
    const price = money(p.price);
    const member =
      p.member_price != null && p.member_price !== ""
        ? money(p.member_price)
        : money((Number(p.price) || 0) * 0.95);
    const stockText = esc(p.stock_text || (p.in_stock ? "В наличност (5+ бр.)" : "Изчерпан"));
    const stockClass = p.in_stock ? "" : `${PC}stockOut`;
    const href = hrefFor(p);
    return `
<article class="${PC}card ">
  <div class="${PC}media">
    <button type="button" class="${PC}wish " aria-label="Добави в любими" aria-pressed="false">
      <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M20.8 4.6a5.4 5.4 0 0 0-7.6 0L12 5.8l-1.2-1.2a5.4 5.4 0 1 0-7.6 7.6L12 21l8.8-8.8a5.4 5.4 0 0 0 0-7.6Z"></path></svg>
    </button>
    <a href="${href}">${
      img
        ? `<img src="${img}" alt="${title}" loading="lazy" decoding="async" />`
        : ""
    }</a>
  </div>
  <div class="${PC}body">
    <div class="${PC}type">${esc(typeLabel(p))}</div>
    <a class="${PC}title" href="${href}"><span class="${PC}titleText">${title}</span></a>
    <div class="${PC}rating" aria-label="5.0 от 5"><span class="${PC}stars">★★★★★</span><span class="${PC}reviewCount">(5)</span></div>
    <div class="${PC}stock ${stockClass}"><span class="${PC}stockDot" aria-hidden="true"></span><span>${stockText}</span></div>
    <div class="${PC}priceGrid">
      <div class="${PC}priceCol">
        <div class="${PC}priceLabel">Редовна цена</div>
        <div class="${PC}price ">${esc(p.price_text || price)}</div>
        <div class="${PC}priceNote">Цена за 1 бр.</div>
      </div>
      <div class="${PC}priceCol ${PC}member">
        <div class="${PC}priceLabel">След вход</div>
        <div class="${PC}price">${esc(p.member_text || member)}</div>
        <div class="${PC}priceNote">Спестявате 5 %</div>
      </div>
    </div>
    <a class="${PC}cta" href="${href}" style="text-decoration:none">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" width="18" height="18"><path d="M4 5h2l2 10h9l2-7H7"></path><circle cx="10" cy="19" r="1.2"></circle><circle cx="17" cy="19" r="1.2"></circle></svg>
      Избери
    </a>
  </div>
</article>`;
  }

  function updateCounts(items) {
    const n = items.length;
    document.querySelectorAll("#hhc-apply-count").forEach((el) => {
      el.textContent = String(n);
    });
    const status = $("#hhc-live-status");
    if (status) status.textContent = `${n} продукта`;
    // Update "Всички продукти" count in sidebar if present
    document.querySelectorAll('a[href="/bg/produkty"] .Katalog-module__iT4WXq__katPocet').forEach((el) => {
      el.textContent = String(state.products.filter((p) => !p.archived).length);
    });
  }

  function render() {
    const grid = $("#hhc-product-grid");
    if (!grid) return;
    const items = filtered().sort((a, b) =>
      String(a.title || "").localeCompare(String(b.title || ""), "bg")
    );
    updateCounts(items);
    grid.innerHTML = items.map(cardHtml).join("") || `<p style="padding:24px;opacity:.7">Няма продукти по избраните филтри.</p>`;
  }

  function readFilters() {
    const stock = $("#hhc-filter-stock");
    state.inStockOnly = !!(stock && stock.checked);
    const from = $("#hhc-price-from");
    const to = $("#hhc-price-to");
    const fromV = from && String(from.value || "").trim();
    const toV = to && String(to.value || "").trim();
    state.priceFrom = fromV ? Number(String(fromV).replace(",", ".")) : null;
    state.priceTo = toV ? Number(String(toV).replace(",", ".")) : null;
    if (Number.isNaN(state.priceFrom)) state.priceFrom = null;
    if (Number.isNaN(state.priceTo)) state.priceTo = null;
  }

  function bind() {
    const apply = $("#hhc-apply-filters");
    if (apply) {
      apply.addEventListener("click", () => {
        readFilters();
        render();
      });
    }
    const stock = $("#hhc-filter-stock");
    if (stock) {
      stock.addEventListener("change", () => {
        readFilters();
        render();
      });
    }
    ["hhc-price-from", "hhc-price-to"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener("change", () => {
        readFilters();
        render();
      });
    });
  }

  async function load() {
    const status = $("#hhc-live-status");
    if (status) status.textContent = "Зареждане…";
    let payload = null;
    for (const url of [`${CATALOG_URL}?t=${Date.now()}`, FALLBACK_URL]) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) continue;
        payload = await res.json();
        break;
      } catch {
        /* next */
      }
    }
    state.products = productList(payload).filter(isVisibleProduct);
    pruneDeadCategoryNav();
    readFilters();
    render();
  }

  function pruneDeadCategoryNav() {
    // Category pages for these were deleted; remove dead sidebar/chip links.
    const kill = /greenz\s*hemp|gummies|infused\s*pre[-\s]?rolls?/i;
    document.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href") || "";
      const text = (a.textContent || "").replace(/\s+/g, " ").trim();
      if (!kill.test(href) && !kill.test(text)) return;
      if (text.length > 80) return;
      const row = a.closest("li") || a;
      row.remove();
    });
  }

  bind();
  load();
})();
