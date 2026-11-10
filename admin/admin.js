(() => {
  const STATUS = {
    new_order: { label: "ЧАКАЩА", action: "new_order" },
    in_process: { label: "ПРИЕТА", action: "in_process" },
    shipped: { label: "ИЗПЪЛНЕНА", action: "shipped" },
    declined: { label: "ОТКАЗАНА", action: "declined" },
  };

  const state = {
    view: "products",
    products: [],
    orders: [],
    stats: null,
    productCat: "all",
    productStatus: "active",
    productQuery: "",
    orderStatus: "all",
    orderQuery: "",
    editing: null,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  async function api(path, options = {}) {
    const res = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (!res.ok) {
      const err = new Error((data && data.error) || res.statusText || "Request failed");
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function eur(n) {
    const v = Number(n) || 0;
    return (
      v.toLocaleString("bg-BG", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " €"
    );
  }

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("bg-BG", {
      day: "numeric",
      month: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function showLogin(show, message = "") {
    // Public /admin never shows a login form — unauthorized users see 404.
    if (show) {
      location.replace("/404");
      return;
    }
    $("#login-screen").classList.add("hidden");
    $("#app").classList.remove("hidden");
    const err = $("#login-error");
    if (err) {
      if (message) {
        err.textContent = message;
        err.classList.remove("hidden");
      } else {
        err.classList.add("hidden");
      }
    }
  }

  async function refreshAll() {
    const [stats, products, orders] = await Promise.all([
      api("/api/admin/stats"),
      api("/api/admin/products"),
      api("/api/admin/orders"),
    ]);
    state.stats = stats;
    state.products = products.products || [];
    state.orders = orders.orders || [];
    render();
  }

  function renderStats() {
    const s = state.stats || {
      orders: { new_order: 0, in_process: 0, shipped: 0, declined: 0 },
      turnover: 0,
    };
    $("#stats-row").innerHTML = `
      <article class="stat-card">
        <div>
          <div class="stat-label">ЧАКАЩИ ПОРЪЧКИ</div>
          <div class="stat-value">${s.orders.new_order || 0}</div>
        </div>
        <div class="stat-icon gold">⏳</div>
      </article>
      <article class="stat-card">
        <div>
          <div class="stat-label">ПРИЕТИ</div>
          <div class="stat-value">${s.orders.in_process || 0}</div>
        </div>
        <div class="stat-icon green">✓</div>
      </article>
      <article class="stat-card">
        <div>
          <div class="stat-label">ИЗПЪЛНЕНИ</div>
          <div class="stat-value">${s.orders.shipped || 0}</div>
        </div>
        <div class="stat-icon brown">📦</div>
      </article>
      <article class="stat-card">
        <div>
          <div class="stat-label">ОБЩ ОБОРОТ</div>
          <div class="stat-value">${eur(s.turnover)}</div>
        </div>
        <div class="stat-icon blue">💶</div>
      </article>
    `;
    $("#orders-pill").textContent = `${s.orders.new_order || 0} нови`;
    $("#products-pill").textContent = String(s.products_total || 0);
  }

  function setView(view) {
    state.view = view;
    $("#view-orders").classList.toggle("hidden", view !== "orders");
    $("#view-products").classList.toggle("hidden", view !== "products");
    $("#tab-orders").classList.toggle("active", view === "orders");
    $("#tab-products").classList.toggle("active", view === "products");
  }

  function categoryCounts() {
    const active = state.products.filter((p) => !p.archived);
    const map = { all: active.length };
    for (const p of active) {
      map[p.category] = (map[p.category] || 0) + 1;
    }
    return map;
  }

  function filteredProducts() {
    const q = state.productQuery.trim().toLowerCase();
    return state.products.filter((p) => {
      if (state.productStatus === "active" && p.archived) return false;
      if (state.productStatus === "archived" && !p.archived) return false;
      if (state.productStatus === "in_stock" && (p.archived || !p.in_stock)) return false;
      if (state.productStatus === "out" && (p.archived || p.in_stock)) return false;
      if (state.productCat !== "all" && p.category !== state.productCat) return false;
      if (!q) return true;
      return (
        (p.title || "").toLowerCase().includes(q) ||
        (p.id || "").toLowerCase().includes(q) ||
        (p.lab_label || "").toLowerCase().includes(q)
      );
    });
  }

  function renderProductFilters() {
    const cats = categoryCounts();
    const preferred = ["THC-X", "HXC", "CCELL", "Изгодни Сетове", "Ароматерапия", "Други"];
    const catKeys = ["all", ...preferred.filter((k) => cats[k]), ...Object.keys(cats).filter((k) => k !== "all" && !preferred.includes(k))];
    $("#product-cat-filters").innerHTML = catKeys
      .map((key) => {
        const label = key === "all" ? `Всички (${cats.all || 0})` : `${key} (${cats[key] || 0})`;
        return `<button type="button" class="pill ${state.productCat === key ? "active" : ""}" data-cat="${key}">${label}</button>`;
      })
      .join("");

    const s = state.stats || {};
    const statusPills = [
      ["in_stock", `<span class="dot green"></span>В наличност (${s.in_stock || 0})`],
      ["out", `<span class="dot red"></span>Изчерпани (${s.out_of_stock || 0})`],
      ["archived", `<span class="dot brown"></span>Архив (${s.archived || 0})`],
      ["active", "Активни"],
    ];
    $("#product-status-filters").innerHTML = statusPills
      .map(
        ([key, label]) =>
          `<button type="button" class="pill ${state.productStatus === key ? "active" : ""}" data-pstatus="${key}">${label}</button>`
      )
      .join("");
  }

  function renderProducts() {
    renderProductFilters();
    const list = filteredProducts();
    const grid = $("#products-grid");
    if (!list.length) {
      grid.innerHTML = `<div class="empty">Няма продукти за показване.</div>`;
      return;
    }
    grid.innerHTML = list
      .map((p) => {
        const stockClass = p.in_stock ? "" : "out";
        const stockBadge = p.archived ? "Архив" : p.in_stock ? "В наличност" : "Изчерпан";
        const stockLine = p.archived
          ? "Архивиран"
          : `${p.stock_text || (p.in_stock ? "В наличност" : "Изчерпан")}${p.volume ? ` · ${p.volume}` : ""}`;
        return `
        <article class="product-card" data-id="${p.id}">
          <div class="product-media">
            <span class="badge-stock ${stockClass}">${stockBadge}</span>
            ${p.lab_label ? `<span class="badge-lab">${escapeHtml(p.lab_label)}</span>` : ""}
            ${p.image ? `<img src="${escapeAttr(p.image)}" alt="" loading="lazy" />` : ""}
          </div>
          <div class="product-body">
            <h3 class="product-title">${escapeHtml(p.title)}</h3>
            <div class="product-meta">ID: ${escapeHtml(p.id)} · ${escapeHtml(p.category || "")}</div>
            <div class="product-stock-line ${stockClass}">• ${escapeHtml(stockLine)}</div>
            <div class="product-price">${eur(p.price)}</div>
            <div class="product-actions">
              <button type="button" class="btn btn-red" data-act="toggle-stock">${
                p.in_stock ? "Направи Изчерпан" : "Върни в наличност"
              }</button>
              <button type="button" class="btn btn-dark" data-act="archive">${
                p.archived ? "Възстанови" : "Архивирай"
              }</button>
              <button type="button" class="btn btn-gold" data-act="edit">✎ Редактирай</button>
              <button type="button" class="btn btn-red btn-icon" data-act="delete" title="Изтрий">🗑</button>
            </div>
          </div>
        </article>`;
      })
      .join("");
  }

  function filteredOrders() {
    const q = state.orderQuery.trim().toLowerCase();
    return state.orders.filter((o) => {
      if (state.orderStatus !== "all" && o.status !== state.orderStatus) return false;
      if (!q) return true;
      return (
        String(o.id).toLowerCase().includes(q) ||
        (o.customer_name || "").toLowerCase().includes(q) ||
        (o.phone || "").toLowerCase().includes(q)
      );
    });
  }

  function renderOrderFilters() {
    const counts = { all: state.orders.length, ...Object.fromEntries(Object.keys(STATUS).map((k) => [k, 0])) };
    for (const o of state.orders) counts[o.status] = (counts[o.status] || 0) + 1;
    const items = [
      ["all", `Всички (${counts.all})`],
      ["new_order", `Чакащи (${counts.new_order || 0})`],
      ["in_process", `Приети (${counts.in_process || 0})`],
      ["shipped", `Изпълнени (${counts.shipped || 0})`],
      ["declined", `Отказани (${counts.declined || 0})`],
    ];
    $("#order-filters").innerHTML = items
      .map(
        ([key, label]) =>
          `<button type="button" class="pill ${state.orderStatus === key ? "active" : ""}" data-ostatus="${key}">${label}</button>`
      )
      .join("");
  }

  function renderOrders() {
    renderOrderFilters();
    const list = filteredOrders();
    const root = $("#orders-list");
    if (!list.length) {
      root.innerHTML = `<div class="empty">Няма поръчки за показване.</div>`;
      return;
    }
    root.innerHTML = list
      .map((o) => {
        const itemsHtml = (o.items || [])
          .map(
            (it) => `
          <div class="order-item">
            <div>
              <div>${escapeHtml(it.title)} × ${it.qty}</div>
              ${it.volume ? `<div class="item-variant">Разфасовка: ${escapeHtml(it.volume)}</div>` : ""}
              ${it.options ? `<div class="item-variant">${escapeHtml(it.options)}</div>` : ""}
            </div>
            <div>${eur((it.unit_price || 0) * (it.qty || 1))}</div>
          </div>`
          )
          .join("");
        const st = o.status || "new_order";
        return `
        <article class="order-card" data-id="${escapeAttr(o.id)}">
          <div>
            <div class="order-id">#${escapeHtml(o.id)}</div>
            <div class="order-time">🕒 ${escapeHtml(formatDate(o.created_at))}</div>
            <div class="order-customer">${escapeHtml(o.customer_name || "")}</div>
            <div class="order-phone">📞 ${escapeHtml(o.phone || "")}</div>
            <div class="ship-box">
              <div><span>Град:</span> ${escapeHtml(o.city || "")}</div>
              <div><span>Куриер:</span> ${escapeHtml(o.courier || "")}</div>
              <div><span>Офис / Адрес:</span> ${escapeHtml(o.address || "")}</div>
            </div>
          </div>
          <div>
            <div class="items-head">АРТИКУЛИ (${(o.items || []).reduce((n, i) => n + (i.qty || 0), 0)} БР.)</div>
            ${itemsHtml}
            <div class="order-total">
              <span>ОБЩО ЗА ПЛАЩАНЕ:</span>
              <strong>${eur(o.total)}</strong>
            </div>
          </div>
          <div class="status-col">
            <div class="status-label">ТЕКУЩ СТАТУС</div>
            <div class="status-badge ${st}">${STATUS[st]?.label || st}</div>
            <div class="status-actions">
              <button type="button" class="btn btn-green" data-status="in_process">✓ Приеми</button>
              <button type="button" class="btn btn-blue" data-status="shipped">📦 Изпълнена</button>
              <button type="button" class="btn btn-red" data-status="declined">✕ Откажи</button>
              <button type="button" class="btn btn-dark" data-status="new_order">↩ Нова поръчка</button>
            </div>
          </div>
        </article>`;
      })
      .join("");
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(str) {
    return escapeHtml(str).replace(/'/g, "&#39;");
  }

  function openProductModal(product) {
    state.editing = product;
    const isNew = !product?.id;
    $("#modal-title").textContent = isNew
      ? "Нов продукт"
      : `Редакция: ${product.title || product.id}`;
    const flavors = product?.flavors || [];
    $("#product-form").innerHTML = `
      <div class="form-grid">
        <label class="field"><span>ЗАГЛАВИЕ НА ПРОДУКТА</span>
          <input name="title" value="${escapeAttr(product?.title || "")}" required /></label>
        <label class="field"><span>КАТЕГОРИЯ</span>
          <select name="category">
            ${["THC-X", "HXC", "CCELL", "Изгодни Сетове", "Ароматерапия", "Други"]
              .map(
                (c) =>
                  `<option value="${c}" ${product?.category === c ? "selected" : ""}>${c}</option>`
              )
              .join("")}
          </select></label>
        <label class="field"><span>ЦЕНА В EUR (€)</span>
          <input name="price" type="number" step="0.01" min="0" value="${product?.price ?? ""}" required /></label>
        <label class="field"><span>СТАРА ЦЕНА В EUR</span>
          <input name="old_price" type="number" step="0.01" min="0" placeholder="напр. 95.00" value="${
            product?.old_price ?? ""
          }" /></label>
        <label class="field"><span>РАЗФАСОВКА / ОБЕМ</span>
          <input name="volume" value="${escapeAttr(product?.volume || "")}" placeholder="1 ml" /></label>
        <label class="field"><span>ЛАБОРАТОРЕН ЕТИКЕТ</span>
          <input name="lab_label" value="${escapeAttr(product?.lab_label || "")}" placeholder="99% THC-X" /></label>
        <label class="field"><span>СТАТУС НА НАЛИЧНОСТ</span>
          <select name="in_stock">
            <option value="1" ${product?.in_stock !== false ? "selected" : ""}>В наличност (Активиран за покупка)</option>
            <option value="0" ${product?.in_stock === false ? "selected" : ""}>Изчерпан</option>
          </select></label>
        <label class="field"><span>ТЕКСТ ЗА НАЛИЧНОСТ НА КАРТАТА</span>
          <input name="stock_text" value="${escapeAttr(
            product?.stock_text || "В наличност (5+ бр.)"
          )}" /></label>
        <div class="field full"><span>СНИМКА НА ПРОДУКТА</span>
          <div class="image-row">
            <img id="preview-image" src="${escapeAttr(product?.image || "")}" alt="" />
            <input name="image" value="${escapeAttr(product?.image || "")}" placeholder="https://..." />
          </div>
        </div>
        <label class="field full"><span>СПЕЦИФИКАЦИИ (SPECS)</span>
          <input name="specs" value="${escapeAttr(product?.specs || "")}" /></label>
        <label class="field full"><span>ЕТИКЕТИ / ЗНАЧКИ (РАЗДЕЛИ СЪС ЗАПЕТАЯ)</span>
          <input name="tags" value="${escapeAttr(product?.tags || "")}" /></label>
        <label class="field full"><span>КРАТКО ОПИСАНИЕ</span>
          <input name="short_description" value="${escapeAttr(
            product?.short_description || ""
          )}" placeholder="Кратко изречение за картата на продукта..." /></label>
        <label class="field full"><span>ПЪЛНО ЛАБОРАТОРНО ОПИСАНИЕ</span>
          <textarea name="full_description">${escapeHtml(
            product?.full_description || ""
          )}</textarea></label>
        <div class="field full">
          <span>ВКУСОВЕ / ТЕРПЕНИ</span>
          <div id="flavors-list">
            ${flavors
              .map(
                (f, i) => `
              <div class="flavor-row" data-idx="${i}">
                <input name="flavor_name" placeholder="Име" value="${escapeAttr(f.name || "")}" />
                <input name="flavor_desc" placeholder="Описание" value="${escapeAttr(f.description || "")}" />
                <button type="button" class="btn btn-red" data-remove-flavor="${i}">✕</button>
              </div>`
              )
              .join("")}
          </div>
          <button type="button" class="btn btn-dark" id="add-flavor">+ Добави Вкус</button>
        </div>
        ${
          isNew
            ? `<label class="field full"><span>ID / SLUG</span>
          <input name="id" required placeholder="thc-x-vape-pen-99-example" /></label>`
            : `<input type="hidden" name="id" value="${escapeAttr(product.id)}" />`
        }
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-dark" data-close="1">Отказ</button>
        <button type="submit" class="btn btn-gold">💾 Запази Продукта</button>
      </div>
    `;
    $("#modal-root").classList.remove("hidden");
    $("#modal-root").setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    $("#modal-root").classList.add("hidden");
    $("#modal-root").setAttribute("aria-hidden", "true");
    state.editing = null;
  }

  function readForm(form) {
    const fd = new FormData(form);
    const flavors = [];
    const names = fd.getAll("flavor_name");
    const descs = fd.getAll("flavor_desc");
    for (let i = 0; i < names.length; i++) {
      if (!names[i] && !descs[i]) continue;
      flavors.push({ name: String(names[i] || ""), description: String(descs[i] || "") });
    }
    const inStock = fd.get("in_stock") === "1";
    const old = fd.get("old_price");
    return {
      id: String(fd.get("id") || "").trim(),
      title: String(fd.get("title") || "").trim(),
      category: String(fd.get("category") || "Други"),
      price: Number(fd.get("price") || 0),
      old_price: old === "" || old == null ? null : Number(old),
      volume: String(fd.get("volume") || "").trim(),
      lab_label: String(fd.get("lab_label") || "").trim(),
      in_stock: inStock,
      stock_text: String(fd.get("stock_text") || (inStock ? "В наличност (5+ бр.)" : "Изчерпан")),
      image: String(fd.get("image") || "").trim(),
      specs: String(fd.get("specs") || "").trim(),
      tags: String(fd.get("tags") || "").trim(),
      short_description: String(fd.get("short_description") || "").trim(),
      full_description: String(fd.get("full_description") || "").trim(),
      flavors,
      archived: Boolean(state.editing?.archived),
      slug: String(fd.get("id") || state.editing?.slug || "").trim(),
      sku: state.editing?.sku || String(fd.get("id") || "").trim(),
      member_price: state.editing?.member_price ?? null,
    };
  }

  function render() {
    renderStats();
    setView(state.view);
    renderProducts();
    renderOrders();
  }

  function bind() {
    $("#login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/admin/login", {
          method: "POST",
          body: JSON.stringify({ password: $("#login-password").value }),
        });
        showLogin(false);
        await refreshAll();
      } catch (err) {
        showLogin(true, err.message || "Грешна парола");
      }
    });

    $("#logout-btn").addEventListener("click", async () => {
      await api("/api/admin/logout", { method: "POST", body: "{}" });
      showLogin(true);
    });

    $$(".tab").forEach((btn) =>
      btn.addEventListener("click", () => {
        state.view = btn.dataset.view;
        render();
      })
    );

    $("#product-cat-filters").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cat]");
      if (!btn) return;
      state.productCat = btn.dataset.cat;
      renderProducts();
    });
    $("#product-status-filters").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-pstatus]");
      if (!btn) return;
      state.productStatus = btn.dataset.pstatus;
      renderProducts();
    });
    $("#product-search").addEventListener("input", (e) => {
      state.productQuery = e.target.value;
      renderProducts();
    });
    $("#order-filters").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-ostatus]");
      if (!btn) return;
      state.orderStatus = btn.dataset.ostatus;
      renderOrders();
    });
    $("#order-search").addEventListener("input", (e) => {
      state.orderQuery = e.target.value;
      renderOrders();
    });
    $("#refresh-orders").addEventListener("click", () => refreshAll().catch(console.error));

    $("#archive-all").addEventListener("click", async () => {
      if (!confirm("Архивиране на всички активни продукти?")) return;
      await api("/api/admin/products/archive-all", { method: "POST", body: "{}" });
      await refreshAll();
    });
    $("#restore-all").addEventListener("click", async () => {
      await api("/api/admin/products/restore-all", { method: "POST", body: "{}" });
      await refreshAll();
    });
    $("#new-product").addEventListener("click", () =>
      openProductModal({
        title: "",
        category: "THC-X",
        price: 0,
        in_stock: true,
        stock_text: "В наличност (5+ бр.)",
        flavors: [],
        archived: false,
      })
    );

    $("#products-grid").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      const card = btn.closest("[data-id]");
      const id = card?.dataset.id;
      const product = state.products.find((p) => p.id === id);
      if (!product) return;
      const act = btn.dataset.act;
      try {
        if (act === "edit") openProductModal(product);
        if (act === "delete") {
          if (!confirm(`Изтриване на „${product.title}“?`)) return;
          await api(`/api/admin/products/${encodeURIComponent(id)}`, { method: "DELETE" });
          await refreshAll();
        }
        if (act === "archive") {
          const path = product.archived ? "restore" : "archive";
          await api(`/api/admin/products/${encodeURIComponent(id)}/${path}`, {
            method: "POST",
            body: "{}",
          });
          await refreshAll();
        }
        if (act === "toggle-stock") {
          await api(`/api/admin/products/${encodeURIComponent(id)}/stock`, {
            method: "POST",
            body: JSON.stringify({
              in_stock: !product.in_stock,
              stock_text: !product.in_stock ? "В наличност (5+ бр.)" : "Изчерпан",
            }),
          });
          await refreshAll();
        }
      } catch (err) {
        alert(err.message || "Грешка");
      }
    });

    $("#orders-list").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-status]");
      if (!btn) return;
      const card = btn.closest("[data-id]");
      const id = card?.dataset.id;
      try {
        await api(`/api/admin/orders/${encodeURIComponent(id)}/status`, {
          method: "POST",
          body: JSON.stringify({ status: btn.dataset.status }),
        });
        await refreshAll();
      } catch (err) {
        alert(err.message || "Грешка");
      }
    });

    $("#modal-root").addEventListener("click", (e) => {
      if (e.target.dataset.close) closeModal();
    });

    $("#product-form").addEventListener("click", (e) => {
      if (e.target.id === "add-flavor") {
        e.preventDefault();
        const list = $("#flavors-list");
        const row = document.createElement("div");
        row.className = "flavor-row";
        row.innerHTML = `
          <input name="flavor_name" placeholder="Име" />
          <input name="flavor_desc" placeholder="Описание" />
          <button type="button" class="btn btn-red" data-remove-flavor>✕</button>`;
        list.appendChild(row);
      }
      if (e.target.matches("[data-remove-flavor], [data-remove-flavor] *") || e.target.dataset.removeFlavor != null) {
        e.preventDefault();
        e.target.closest(".flavor-row")?.remove();
      }
    });

    $("#product-form").addEventListener("input", (e) => {
      if (e.target.name === "image") {
        $("#preview-image").src = e.target.value;
      }
    });

    $("#product-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = readForm(e.target);
      if (!payload.id || !payload.title) {
        alert("ID и заглавие са задължителни.");
        return;
      }
      try {
        const exists = state.products.some((p) => p.id === payload.id);
        if (exists || state.editing?.id) {
          await api(`/api/admin/products/${encodeURIComponent(payload.id)}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
        } else {
          await api("/api/admin/products", {
            method: "POST",
            body: JSON.stringify(payload),
          });
        }
        closeModal();
        await refreshAll();
      } catch (err) {
        alert(err.message || "Грешка при запис");
      }
    });
  }

  async function boot() {
    document.documentElement.style.visibility = "hidden";
    try {
      const session = await api("/api/admin/session");
      if (!session.ok) {
        location.replace("/404");
        return;
      }
      document.documentElement.style.visibility = "";
      $("#login-screen").classList.add("hidden");
      $("#app").classList.remove("hidden");
      bind();
      await refreshAll();
    } catch {
      location.replace("/404");
    }
  }

  boot();
})();
