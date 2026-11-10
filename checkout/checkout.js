(() => {
  const KEY = "hhc_cart_v1";
  const PROMO_KEY = "hhc_promo_v1";
  const EUR_TO_BGN = 1.95583;
  const MAX_QTY = 100;

  const state = {
    step: 1,
    catalog: null,
    promo: localStorage.getItem(PROMO_KEY) || "",
    submitting: false,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  function money(n) {
    const v = Number(n) || 0;
    return (
      v.toLocaleString("bg-BG", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " €"
    );
  }

  function bgn(n) {
    const v = (Number(n) || 0) * EUR_TO_BGN;
    return (
      v.toLocaleString("bg-BG", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " лв."
    );
  }

  function clampQty(n) {
    const v = Number(n) || 1;
    return Math.min(MAX_QTY, Math.max(1, v));
  }

  function readCart() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw.map((it) => ({ ...it, qty: clampQty(it.qty) }));
    } catch {
      return [];
    }
  }

  function writeCart(items) {
    localStorage.setItem(KEY, JSON.stringify(items));
    window.dispatchEvent(new Event("hhc-cart-changed"));
  }

  function deliveryType() {
    return ($('input[name="delivery_type"]:checked') || {}).value || "office";
  }

  function shippingCost() {
    return deliveryType() == "address" ? 5 : 4;
  }

  function cartSubtotal(items) {
    return items.reduce((s, it) => s + (Number(it.price) || 0) * (it.qty || 1), 0);
  }

  function discountAmount(subtotal) {
    if ((state.promo || "").toUpperCase() === "VIP10") {
      return Math.round(subtotal * 0.1 * 100) / 100;
    }
    return 0;
  }

  function totals(items) {
    const subtotal = cartSubtotal(items);
    const discount = discountAmount(subtotal);
    const shipping = items.length ? shippingCost() : 0;
    const total = Math.max(0, subtotal - discount) + shipping;
    return { subtotal, discount, shipping, total };
  }

  function setStep(n) {
    state.step = n;
    for (let i = 1; i <= 3; i++) {
      $(`#step-${i}`).classList.toggle("hidden", i !== n);
      const ind = $(`[data-step-indicator="${i}"]`);
      ind.classList.toggle("active", i === n);
      ind.classList.toggle("done", i < n);
    }
    const title = $("#summary-title");
    if (title) {
      title.textContent = n === 1 ? "Обобщение на поръчката" : "Обобщение на поръчката";
    }
    updateSummary();
  }

  function updateSummary() {
    const items = readCart();
    const t = totals(items);
    $("#sum-subtotal").textContent = money(t.subtotal);
    $("#sum-shipping").textContent = money(t.shipping);
    $("#sum-total").textContent = money(t.total);
    $("#sum-bgn").textContent = bgn(t.total);
    const drow = $("#discount-row");
    if (t.discount > 0) {
      drow.classList.remove("hidden");
      $("#sum-discount").textContent = "−" + money(t.discount);
    } else {
      drow.classList.add("hidden");
    }
    const btn = $("#confirm-btn");
    btn.disabled = !items.length || state.submitting;
    if (state.step === 1) btn.textContent = "Потвърди поръчката →";
    else if (state.step === 2) btn.textContent = "Продължи →";
    else btn.textContent = "Потвърди поръчката →";
  }

  function itemOptions(it) {
    const bits = [];
    if (it.flavors && it.flavors.length) bits.push("Вкусове: " + it.flavors.join(", "));
    if (it.color) bits.push("Цвят: " + it.color);
    return bits.join(" · ");
  }

  function renderCart() {
    const items = readCart();
    const root = $("#cart-items");
    const empty = $("#empty-cart");
    const upsell = $("#upsell-wrap");

    if (!items.length) {
      root.innerHTML = "";
      empty.classList.remove("hidden");
      upsell.classList.add("hidden");
      updateSummary();
      return;
    }
    empty.classList.add("hidden");
    upsell.classList.remove("hidden");

    root.innerHTML = items
      .map(
        (it, idx) => `
      <article class="cart-item" data-idx="${idx}">
        <img src="${escapeAttr(it.image || "/icon.svg")}" alt="" />
        <div>
          <h4>${escapeHtml(it.title || it.product_id)}</h4>
          <div class="stock">В наличност</div>
          ${itemOptions(it) ? `<div class="meta-line">${escapeHtml(itemOptions(it))}</div>` : ""}
          <div class="qty">
            <button type="button" data-qty="-1" aria-label="Намали">−</button>
            <span>${it.qty || 1}</span>
            <button type="button" data-qty="1" aria-label="Увеличи">+</button>
          </div>
        </div>
        <div class="item-side">
          <div class="item-price">${money((it.price || 0) * (it.qty || 1))}</div>
          <button type="button" class="remove-btn" data-remove>🗑 Премахни</button>
        </div>
      </article>`
      )
      .join("");

    renderUpsells(items);
    updateSummary();
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function renderUpsells(cartItems) {
    const products = Object.values((state.catalog && state.catalog.products) || {});
    const inCart = new Set(cartItems.map((i) => i.product_id));
    const picks = products
      .filter((p) => p && !p.archived && p.in_stock && !inCart.has(p.id) && !(p.flavors || []).length)
      .slice(0, 4);
    const list = $("#upsell-list");
    if (!picks.length) {
      $("#upsell-wrap").classList.add("hidden");
      return;
    }
    list.innerHTML = picks
      .map(
        (p) => `
      <article class="upsell-card" data-add="${escapeAttr(p.id)}">
        <img src="${escapeAttr(p.image || "/icon.svg")}" alt="" />
        <div class="t">${escapeHtml(p.title)}</div>
        <div class="p">${escapeHtml(p.price_text || money(p.price))}</div>
        <button type="button">+ Добави</button>
      </article>`
      )
      .join("");
  }

  async function loadCatalog() {
    try {
      let res = await fetch(`/api/catalog?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) {
        res = await fetch(`/storage/catalog.json?t=${Date.now()}`, { cache: "no-store" });
      }
      if (!res.ok) return;
      state.catalog = await res.json();
    } catch {
      /* ignore */
    }
  }

  function addProduct(productId) {
    const p = state.catalog?.products?.[productId];
    if (!p || !p.in_stock) return;
    if ((p.flavors || []).length) {
      // Bundles with flavors go through the storefront picker.
      sessionStorage.setItem("hhc_pending_product", productId);
      location.href = `/bg/produkt/${encodeURIComponent(productId)}`;
      return;
    }
    const items = readCart();
    const existing = items.find((i) => i.product_id === productId && !i.flavors?.length && !i.color);
    if (existing) existing.qty = Math.min(MAX_QTY, (existing.qty || 1) + 1);
    else {
      items.push({
        product_id: p.id,
        title: p.title,
        price: p.price,
        image: p.image,
        qty: 1,
        flavors: [],
        color: "",
      });
    }
    writeCart(items);
    renderCart();
  }

  async function submitOrder() {
    const items = readCart();
    if (!items.length) return;
    const form = $("#checkout-form");
    if (!form.reportValidity()) {
      $("#form-error").textContent = "Моля, попълнете задължителните полета.";
      return;
    }
    const fd = new FormData(form);
    state.submitting = true;
    updateSummary();
    $("#form-error").textContent = "";
    try {
      const payload = {
        first_name: fd.get("first_name"),
        last_name: fd.get("last_name"),
        phone: fd.get("phone"),
        email: fd.get("email"),
        city: fd.get("city"),
        postal_code: fd.get("postal_code"),
        address: fd.get("address"),
        delivery_type: deliveryType(),
        payment: "cod",
        shipping: shippingCost(),
        promo_code: state.promo,
        items: items.map((it) => ({
          product_id: it.product_id,
          qty: it.qty || 1,
          flavors: it.flavors || [],
          color: it.color || "",
          unit_price: it.price,
          title: it.title,
        })),
      };
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || "Грешка при изпращане на поръчката");
      }
      writeCart([]);
      localStorage.removeItem(PROMO_KEY);
      $("#success-id").textContent = data.order?.id || "";
      $("#success-overlay").classList.remove("hidden");
    } catch (err) {
      $("#form-error").textContent = err.message || "Грешка при изпращане";
    } finally {
      state.submitting = false;
      updateSummary();
    }
  }

  function onConfirm() {
    const items = readCart();
    if (!items.length) return;
    if (state.step === 1) {
      setStep(2);
      return;
    }
    if (state.step === 2) {
      setStep(3);
      return;
    }
    submitOrder();
  }

  function bind() {
    $("#confirm-btn").addEventListener("click", onConfirm);

    $("#cart-items").addEventListener("click", (e) => {
      const card = e.target.closest(".cart-item");
      if (!card) return;
      const idx = Number(card.dataset.idx);
      const items = readCart();
      if (e.target.closest("[data-remove]")) {
        items.splice(idx, 1);
        writeCart(items);
        renderCart();
        return;
      }
      const qtyBtn = e.target.closest("[data-qty]");
      if (qtyBtn) {
        const delta = Number(qtyBtn.dataset.qty);
        items[idx].qty = Math.min(MAX_QTY, Math.max(1, (items[idx].qty || 1) + delta));
        writeCart(items);
        renderCart();
      }
    });

    $("#upsell-list").addEventListener("click", (e) => {
      const card = e.target.closest("[data-add]");
      if (!card) return;
      addProduct(card.dataset.add);
    });

    $$('input[name="delivery_type"]').forEach((el) => {
      el.addEventListener("change", () => {
        $$("#delivery-options .option-card").forEach((c) => c.classList.remove("selected"));
        el.closest(".option-card")?.classList.add("selected");
        updateSummary();
      });
    });

    $("#promo-btn").addEventListener("click", () => {
      const code = ($("#promo-input").value || "").trim().toUpperCase();
      const msg = $("#promo-msg");
      if (!code) {
        state.promo = "";
        localStorage.removeItem(PROMO_KEY);
        msg.textContent = "";
        msg.className = "promo-msg";
        updateSummary();
        return;
      }
      if (code === "VIP10") {
        state.promo = code;
        localStorage.setItem(PROMO_KEY, code);
        msg.textContent = "Приложена отстъпка 10%";
        msg.className = "promo-msg ok";
      } else {
        state.promo = "";
        localStorage.removeItem(PROMO_KEY);
        msg.textContent = "Невалиден код";
        msg.className = "promo-msg bad";
      }
      updateSummary();
    });

    if (state.promo) {
      $("#promo-input").value = state.promo;
      if (state.promo.toUpperCase() === "VIP10") {
        $("#promo-msg").textContent = "Приложена отстъпка 10%";
        $("#promo-msg").className = "promo-msg ok";
      }
    }

    $$('[data-step-indicator]').forEach((el) => {
      el.style.cursor = "pointer";
      el.addEventListener("click", () => {
        const n = Number(el.dataset.stepIndicator);
        if (!readCart().length) return;
        if (n <= state.step || n === 1) setStep(n);
      });
    });
  }

  function bindMenu() {
    const bar = $("#topbar");
    const btn = $("#menu-toggle");
    if (!bar || !btn) return;
    btn.addEventListener("click", () => {
      const open = bar.classList.toggle("nav-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  async function init() {
    await loadCatalog();
    bind();
    bindMenu();
    renderCart();
    setStep(1);
  }

  init();
})();
