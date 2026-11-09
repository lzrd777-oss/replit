(() => {
  const KEY = "hhc_cart_v1";
  const CATALOG_URL = "/api/catalog";
  const CATALOG_FALLBACK = "/storage/catalog.json";
  const DEFAULT_COLORS = ["Baby Blue", "Forest Green", "Deep Purple", "Deep Red"];

  let catalog = null;
  const pdp = {
    product: null,
    slots: 0,
    picks: [],
    color: "",
  };

  const CTA_ADD = new Set([
    "Избери",
    "Добави в количката",
    "В количката",
    "+ Добави",
  ]);

  function readCart() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch {
      return [];
    }
  }

  function writeCart(items) {
    localStorage.setItem(KEY, JSON.stringify(items));
    updateCartBadge();
    window.dispatchEvent(new Event("hhc-cart-changed"));
  }

  function cartCount() {
    return readCart().reduce((n, it) => n + (it.qty || 1), 0);
  }

  function updateCartBadge() {
    const n = cartCount();
    document.querySelectorAll('a[href*="kosik"], a[href*="/checkout"]').forEach((a) => {
      let badge = a.querySelector(".hhc-cart-badge");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "hhc-cart-badge";
        badge.style.cssText =
          "display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;padding:0 5px;margin-left:4px;border-radius:999px;background:#39e26a;color:#041208;font-size:11px;font-weight:800;line-height:1;";
        a.appendChild(badge);
      }
      badge.textContent = String(n);
      badge.style.display = n ? "inline-flex" : "none";
    });
  }

  function slugFromHref(href) {
    if (!href) return null;
    const m = String(href).match(/\/produkt\/([^\/?#]+)/);
    return m ? decodeURIComponent(m[1].replace(/\.html$/, "")) : null;
  }

  function currentProductId() {
    const path = location.pathname.replace(/\.html$/, "");
    const m = path.match(/\/produkt\/([^\/]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function productFromContext(el) {
    const pid = currentProductId();
    if (pid && catalog?.products?.[pid]) return catalog.products[pid];
    const link =
      el.closest("a[href*='/produkt/']") ||
      el.closest("article, li, [class*='Card'], [class*='card']")?.querySelector(
        "a[href*='/produkt/']"
      ) ||
      el.parentElement?.querySelector("a[href*='/produkt/']");
    const slug = slugFromHref(link?.getAttribute("href"));
    return slug ? catalog?.products?.[slug] : null;
  }

  function flavorSlotCount(product) {
    const flavors = product.flavors || [];
    if (!flavors.length) return 0;
    let slots = Number(product.flavor_slots) || 0;
    if (!slots && String(product.title || "").toLowerCase().startsWith("2x")) slots = 2;
    if (!slots) slots = Math.min(2, flavors.length);
    return slots;
  }

  function needsConfig(product) {
    if (!product) return false;
    return flavorSlotCount(product) > 0 || resolveColors(product).length > 0;
  }

  function resolveColors(product) {
    if (Array.isArray(product.colors) && product.colors.length) return product.colors;
    const pageColors = readDomColors();
    if (pageColors.length) return pageColors;
    const title = String(product.title || "");
    const isBundle =
      /^2x/i.test(title) || title.includes("+") || (product.flavors || []).length > 0;
    if (isBundle && /ccell|palm\s*pro|m4/i.test(title)) return DEFAULT_COLORS.slice();
    return [];
  }

  function readDomColors() {
    return [...document.querySelectorAll('button[class*="vcard"]')]
      .map((b) =>
        (b.textContent || "")
          .replace(/\s+/g, " ")
          .replace(/В наличност.*/i, "")
          .replace(/Изчерпан.*/i, "")
          .trim()
      )
      .filter(Boolean);
  }

  function deviceLabel(product) {
    const title = String(product.title || "");
    const parts = title.split("+");
    if (parts.length > 1) return parts[parts.length - 1].trim();
    if (/ccell/i.test(title)) return "CCELL";
    return "устройството";
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

  function ensureStyles() {
    if (document.getElementById("hhc-cart-styles")) return;
    const style = document.createElement("style");
    style.id = "hhc-cart-styles";
    style.textContent = `
      .hhc-modal-root{position:fixed;inset:0;z-index:99999;display:flex;align-items:flex-end;justify-content:center;background:rgba(0,0,0,.72);padding:16px;font-family:"Segoe UI",Arial,sans-serif}
      @media(min-width:720px){.hhc-modal-root{align-items:center}}
      .hhc-modal{width:min(520px,100%);max-height:min(92vh,820px);overflow:auto;background:#0d1210;color:#f3f6f4;border:1px solid #243028;border-radius:18px;padding:20px 18px 18px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
      .hhc-modal h2{margin:0;font-size:22px;font-weight:800}
      .hhc-modal .hhc-count{float:right;color:#8b968f;font-size:14px;font-weight:700;margin-top:4px}
      .hhc-modal .hhc-hint{color:#8b968f;font-size:13px;margin:8px 0 14px}
      .hhc-flavor-list,.hhc-color-list{display:flex;flex-direction:column;gap:8px;margin-bottom:14px}
      .hhc-choice{display:flex;align-items:flex-start;gap:10px;padding:12px;border:1px solid #243028;border-radius:12px;cursor:pointer;background:#121816}
      .hhc-choice:hover,.hhc-choice.selected{border-color:#39e26a;background:rgba(57,226,106,.06)}
      .hhc-choice .name{font-weight:700;font-size:14px}
      .hhc-choice .desc{color:#8b968f;font-size:12px;margin-top:2px}
      .hhc-actions{display:flex;gap:10px;margin-top:8px}
      .hhc-actions button{flex:1;border:0;border-radius:12px;padding:13px 12px;font-weight:800;cursor:pointer}
      .hhc-btn-ghost{background:#1a221e;color:#f3f6f4}
      .hhc-btn-green{background:#39e26a;color:#041208}
      .hhc-btn-green:disabled{opacity:.4;cursor:not-allowed}
      .hhc-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#121816;border:1px solid #39e26a;color:#f3f6f4;padding:12px 16px;border-radius:12px;z-index:100000;font-family:"Segoe UI",Arial,sans-serif;font-size:14px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
      button[class*="pozice"][data-hhc-filled="1"]{border-style:solid !important;border-color:#39e26a !important;background:rgba(57,226,106,.08) !important}
    `;
    document.head.appendChild(style);
  }

  function toast(msg) {
    ensureStyles();
    const el = document.createElement("div");
    el.className = "hhc-toast";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2200);
  }

  function slotButtons() {
    return [...document.querySelectorAll("button")].filter((b) => {
      const aria = b.getAttribute("aria-label") || "";
      const cls = b.className || "";
      return /Позиция\s*\d/i.test(aria) || /pozice/i.test(cls);
    });
  }

  function findCtaButton() {
    return (
      document.querySelector('button[class*="cta"]') ||
      [...document.querySelectorAll("button")].find((b) => {
        const t = (b.textContent || "").replace(/\s+/g, " ").trim();
        return (
          t === "Добави в количката" ||
          /^Изберете още\s+\d/.test(t) ||
          t === "Изчерпано" ||
          t === "Извести ме"
        );
      }) ||
      null
    );
  }

  function filledCount() {
    return pdp.picks.filter(Boolean).length;
  }

  function pdpReady() {
    const flavorsOk = !pdp.slots || filledCount() === pdp.slots;
    const colors = pdp.product ? resolveColors(pdp.product) : [];
    const colorOk = !colors.length || !!pdp.color;
    return flavorsOk && colorOk;
  }

  function updatePdpCta() {
    const btn = findCtaButton();
    if (!btn || !pdp.product) return;
    if (!pdp.product.in_stock) {
      btn.disabled = true;
      btn.textContent = "Изчерпано";
      return;
    }
    const left = Math.max(0, pdp.slots - filledCount());
    if (left > 0) {
      btn.disabled = false;
      btn.textContent = `Изберете още ${left}`;
      return;
    }
    const colors = resolveColors(pdp.product);
    if (colors.length && !pdp.color) {
      btn.disabled = false;
      btn.textContent = "Изберете цвят";
      return;
    }
    btn.disabled = false;
    btn.textContent = "Добави в количката";
  }

  function paintSlot(btn, flavorName, index) {
    if (!btn) return;
    if (flavorName) {
      btn.setAttribute("data-hhc-filled", "1");
      btn.setAttribute("aria-label", `Позиция ${index + 1}: ${flavorName}`);
      btn.innerHTML = "";
      const plus = document.createElement("div");
      plus.textContent = flavorName;
      plus.style.cssText =
        "font-weight:800;font-size:13px;color:#39e26a;margin-bottom:6px;word-break:break-word";
      const lab = document.createElement("div");
      lab.textContent = "Избран вкус";
      lab.style.cssText = "font-weight:700;font-size:13px";
      const sub = document.createElement("div");
      sub.textContent = `Позиция ${index + 1}`;
      sub.style.cssText = "color:#8b968f;font-size:12px;margin-top:4px";
      btn.append(plus, lab, sub);
    }
  }

  function openFlavorPickerForSlot(slotIndex) {
    if (!pdp.product) return;
    const flavors = pdp.product.flavors || [];
    if (!flavors.length) {
      toast("Няма добавени вкусове в админа");
      return;
    }
    ensureStyles();
    const root = document.createElement("div");
    root.className = "hhc-modal-root";
    root.innerHTML = `<div class="hhc-modal" role="dialog" aria-modal="true"></div>`;
    document.body.appendChild(root);
    const modal = root.querySelector(".hhc-modal");
    modal.innerHTML = `
      <div class="hhc-count">${filledCount()} / ${pdp.slots}</div>
      <h2>Изберете вкус</h2>
      <p class="hhc-hint">Позиция ${slotIndex + 1}</p>
      <div class="hhc-flavor-list">
        ${flavors
          .map(
            (f, i) => `
          <div class="hhc-choice ${pdp.picks[slotIndex] === f.name ? "selected" : ""}" data-flavor="${i}">
            <div>
              <div class="name">${escapeHtml(f.name)}</div>
              ${f.description ? `<div class="desc">${escapeHtml(f.description)}</div>` : ""}
            </div>
          </div>`
          )
          .join("")}
      </div>
      <div class="hhc-actions">
        <button type="button" class="hhc-btn-ghost" data-close>Затвори</button>
      </div>`;

    root.addEventListener("click", (e) => {
      if (e.target === root || e.target.closest("[data-close]")) {
        root.remove();
        return;
      }
      const choice = e.target.closest("[data-flavor]");
      if (!choice) return;
      const f = flavors[Number(choice.dataset.flavor)];
      if (!f) return;
      pdp.picks[slotIndex] = f.name;
      const btns = slotButtons();
      paintSlot(btns[slotIndex], f.name, slotIndex);
      updatePdpCta();
      updateCounterLabel();
      root.remove();
    });
  }

  function updateCounterLabel() {
    const nodes = [...document.querySelectorAll("*")].filter(
      (el) => el.children.length === 0 && /^\d+\s*\/\s*\d+$/.test((el.textContent || "").trim())
    );
    nodes.forEach((el) => {
      el.textContent = `${filledCount()} / ${pdp.slots}`;
    });
  }

  function openConfigurator(product, { goCheckout = true } = {}) {
    ensureStyles();
    const flavors = product.flavors || [];
    const slots = flavorSlotCount(product);
    const colors = resolveColors(product);
    const picks = Array(slots).fill("");
    let activeSlot = 0;
    let color = colors[0] || "";
    let view = slots ? "slots" : "colors";

    const root = document.createElement("div");
    root.className = "hhc-modal-root";
    root.innerHTML = `<div class="hhc-modal" role="dialog" aria-modal="true"></div>`;
    document.body.appendChild(root);
    const modal = root.querySelector(".hhc-modal");

    function close() {
      root.remove();
    }
    function filled() {
      return picks.filter(Boolean).length;
    }
    function canContinue() {
      return (!slots || picks.every(Boolean)) && (!colors.length || !!color);
    }

    function render() {
      if (view === "flavor-pick") {
        modal.innerHTML = `
          <div class="hhc-count">${filled()} / ${slots}</div>
          <h2>Изберете вкус</h2>
          <p class="hhc-hint">Позиция ${activeSlot + 1}</p>
          <div class="hhc-flavor-list">
            ${flavors
              .map(
                (f, i) => `
              <div class="hhc-choice ${picks[activeSlot] === f.name ? "selected" : ""}" data-flavor="${i}">
                <div>
                  <div class="name">${escapeHtml(f.name)}</div>
                  ${f.description ? `<div class="desc">${escapeHtml(f.description)}</div>` : ""}
                </div>
              </div>`
              )
              .join("")}
          </div>
          <div class="hhc-actions">
            <button type="button" class="hhc-btn-ghost" data-back>Назад</button>
          </div>`;
        return;
      }
      if (view === "colors") {
        modal.innerHTML = `
          <h2>Изберете цвят – ${escapeHtml(deviceLabel(product))}</h2>
          <p class="hhc-hint">Изберете цвят за устройството в комплекта.</p>
          <div class="hhc-color-list">
            ${colors
              .map(
                (c) => `
              <div class="hhc-choice ${color === c ? "selected" : ""}" data-color="${escapeAttr(c)}">
                <div class="name">${escapeHtml(c)}</div>
              </div>`
              )
              .join("")}
          </div>
          <div class="hhc-actions">
            ${slots ? `<button type="button" class="hhc-btn-ghost" data-to-slots>Назад</button>` : `<button type="button" class="hhc-btn-ghost" data-close>Затвори</button>`}
            <button type="button" class="hhc-btn-green" data-add ${canContinue() ? "" : "disabled"}>Добави в количката</button>
          </div>`;
        return;
      }
      modal.innerHTML = `
        <div class="hhc-count">${filled()} / ${slots}</div>
        <h2>Изберете ${slots} вкуса</h2>
        <p class="hhc-hint">Изберете точно ${slots} вкуса за този продукт.</p>
        <div class="hhc-flavor-list">
          ${picks
            .map(
              (v, i) => `
            <div class="hhc-choice ${activeSlot === i ? "selected" : ""}" data-slot="${i}">
              <div>
                <div class="name">${v ? escapeHtml(v) : "Изберете вкус"}</div>
                <div class="desc">Позиция ${i + 1}</div>
              </div>
            </div>`
            )
            .join("")}
        </div>
        <div class="hhc-actions">
          <button type="button" class="hhc-btn-ghost" data-close>Затвори</button>
          <button type="button" class="hhc-btn-green" data-next ${filled() === slots ? "" : "disabled"}>
            ${colors.length ? "Изберете цвят →" : "Добави в количката"}
          </button>
        </div>`;
    }

    function addToCart() {
      if (!canContinue()) return;
      const items = readCart();
      items.push({
        product_id: product.id,
        title: product.title,
        price: product.price,
        image: product.image,
        qty: 1,
        flavors: picks.filter(Boolean),
        color: color || "",
      });
      writeCart(items);
      close();
      toast("Добавено в количката");
      if (goCheckout) setTimeout(() => (location.href = "/checkout"), 350);
    }

    root.addEventListener("click", (e) => {
      if (e.target === root || e.target.closest("[data-close]")) return close();
      const slot = e.target.closest("[data-slot]");
      if (slot) {
        activeSlot = Number(slot.dataset.slot);
        view = "flavor-pick";
        render();
        return;
      }
      const flavor = e.target.closest("[data-flavor]");
      if (flavor) {
        const f = flavors[Number(flavor.dataset.flavor)];
        if (f) picks[activeSlot] = f.name;
        view = "slots";
        render();
        return;
      }
      if (e.target.closest("[data-back]") || e.target.closest("[data-to-slots]")) {
        view = "slots";
        render();
        return;
      }
      if (e.target.closest("[data-next]")) {
        if (filled() !== slots) return;
        if (colors.length) {
          view = "colors";
          render();
        } else addToCart();
        return;
      }
      const colorEl = e.target.closest("[data-color]");
      if (colorEl) {
        color = colorEl.dataset.color;
        render();
        return;
      }
      if (e.target.closest("[data-add]")) addToCart();
    });

    render();
  }

  function addSimple(product) {
    const items = readCart();
    const existing = items.find(
      (i) => i.product_id === product.id && !(i.flavors || []).length && !i.color
    );
    if (existing) existing.qty = (existing.qty || 1) + 1;
    else {
      items.push({
        product_id: product.id,
        title: product.title,
        price: product.price,
        image: product.image,
        qty: 1,
        flavors: [],
        color: "",
      });
    }
    writeCart(items);
    toast("Добавено в количката");
    setTimeout(() => (location.href = "/checkout"), 350);
  }

  function addConfiguredFromPdp() {
    if (!pdp.product || !pdpReady()) {
      if (pdp.slots && filledCount() < pdp.slots) {
        const empty = pdp.picks.findIndex((x) => !x);
        openFlavorPickerForSlot(empty < 0 ? 0 : empty);
      } else {
        toast("Изберете цвят");
      }
      return;
    }
    const items = readCart();
    items.push({
      product_id: pdp.product.id,
      title: pdp.product.title,
      price: pdp.product.price,
      image: pdp.product.image,
      qty: 1,
      flavors: pdp.picks.filter(Boolean),
      color: pdp.color || "",
    });
    writeCart(items);
    toast("Добавено в количката");
    setTimeout(() => (location.href = "/checkout"), 350);
  }

  function isPdpCta(el) {
    if (!el || el.tagName !== "BUTTON") return false;
    const t = (el.textContent || "").replace(/\s+/g, " ").trim();
    return (
      /cta/i.test(el.className || "") ||
      t === "Добави в количката" ||
      /^Изберете още\s+\d/.test(t) ||
      t === "Изберете цвят"
    );
  }

  function isSlotButton(el) {
    if (!el || el.tagName !== "BUTTON") return false;
    const aria = el.getAttribute("aria-label") || "";
    return /Позиция\s*\d/i.test(aria) || /pozice/i.test(el.className || "");
  }

  function isColorCard(el) {
    if (!el) return false;
    const btn = el.closest('button[class*="vcard"]');
    return !!btn;
  }

  function handleCta(el, e) {
    const text = (el.textContent || "").replace(/\s+/g, " ").trim();
    const isCta =
      CTA_ADD.has(text) ||
      /cta/i.test(el.className || "") ||
      text === "Добави в количката";
    if (!isCta) return false;

    const product = productFromContext(el);
    if (!product) return false;
    if (!product.in_stock) return true;

    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();

    // On PDP with native slots, use PDP state instead of modal when possible.
    if (pdp.product && pdp.product.id === product.id && slotButtons().length) {
      addConfiguredFromPdp();
      return true;
    }

    if (needsConfig(product)) openConfigurator(product);
    else addSimple(product);
    return true;
  }

  function bindClicks() {
    document.addEventListener(
      "click",
      (e) => {
        const slotBtn = e.target.closest("button");
        if (slotBtn && isSlotButton(slotBtn) && pdp.product) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
          const btns = slotButtons();
          const idx = Math.max(0, btns.indexOf(slotBtn));
          openFlavorPickerForSlot(idx);
          return;
        }

        const colorBtn = e.target.closest('button[class*="vcard"]');
        if (colorBtn && pdp.product) {
          const name = (colorBtn.textContent || "")
            .replace(/\s+/g, " ")
            .replace(/В наличност.*/i, "")
            .replace(/Изчерпан.*/i, "")
            .trim();
          if (name && !colorBtn.disabled) {
            e.preventDefault();
            e.stopPropagation();
            pdp.color = name;
            document.querySelectorAll('button[class*="vcard"]').forEach((b) => {
              b.style.outline = "";
              b.style.boxShadow = "";
            });
            colorBtn.style.outline = "2px solid #39e26a";
            colorBtn.style.boxShadow = "0 0 0 3px rgba(57,226,106,.2)";
            updatePdpCta();
          }
        }

        if (slotBtn && isPdpCta(slotBtn) && pdp.product) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
          addConfiguredFromPdp();
          return;
        }

        const el = e.target.closest("a, button");
        if (!el) return;
        handleCta(el, e);
      },
      true
    );
  }

  function initPdp() {
    const pid = currentProductId();
    if (!pid || !catalog?.products?.[pid]) return;
    const product = catalog.products[pid];
    pdp.product = product;
    pdp.slots = flavorSlotCount(product);
    pdp.picks = Array(pdp.slots).fill("");
    pdp.color = "";

    // Prefer first available color card as default if only one enabled? leave empty until chosen.
    updatePdpCta();
    updateCounterLabel();

    // If admin has flavors but page has no slot UI, nothing else to hydrate.
    if (pdp.slots && !slotButtons().length) {
      // Keep listing/CTA modal flow.
    }
  }

  async function loadCatalog() {
    try {
      let res = await fetch(`${CATALOG_URL}?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) {
        res = await fetch(`${CATALOG_FALLBACK}?t=${Date.now()}`, { cache: "no-store" });
      }
      if (!res.ok) return;
      catalog = await res.json();
    } catch {
      /* ignore */
    }
  }

  async function init() {
    await loadCatalog();
    bindClicks();
    initPdp();
    updateCartBadge();
    window.addEventListener("hhc-cart-changed", updateCartBadge);
    setTimeout(initPdp, 600);
    setTimeout(initPdp, 1500);

    const pending = sessionStorage.getItem("hhc_pending_product");
    if (pending && catalog?.products?.[pending]) {
      sessionStorage.removeItem("hhc_pending_product");
      const p = catalog.products[pending];
      if (needsConfig(p)) openConfigurator(p);
      else addSimple(p);
    }
  }

  window.HHCCart = {
    openConfigurator,
    addSimple,
    readCart,
    writeCart,
  };

  init();
})();
