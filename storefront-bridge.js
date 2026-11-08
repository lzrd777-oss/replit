(() => {
  const CATALOG_URL = "/api/catalog";
  const CATALOG_FALLBACK = "/storage/catalog.json";
  let catalog = null;

  const eurRe = /\d[\d\s\u00a0]*(?:[.,]\d{1,2})?\s*€/g;

  function cleanPageUrl(url) {
    if (!url || typeof url !== "string") return url;
    if (/^(https?:|mailto:|tel:|javascript:|#)/i.test(url)) return url;
    let next = url.replace(/\.html(?=[?#]|$)/i, "");
    if (next === "/bg" || next.startsWith("/bg?")) {
      next = next.replace(/^\/bg/, "/");
    }
    return next;
  }

  function normalizeDocumentLinks(root) {
    (root || document).querySelectorAll("a[href], form[action]").forEach((el) => {
      const attr = el.hasAttribute("href") ? "href" : "action";
      const raw = el.getAttribute(attr);
      if (!raw || !/\.html/i.test(raw)) return;
      const cleaned = cleanPageUrl(raw);
      if (cleaned !== raw) el.setAttribute(attr, cleaned);
    });
  }

  normalizeDocumentLinks(document);
  document.addEventListener(
    "click",
    (e) => {
      const a = e.target.closest("a[href]");
      if (!a) return;
      const raw = a.getAttribute("href");
      if (!raw || !/\.html/i.test(raw)) return;
      if (/^(https?:|mailto:|tel:|javascript:)/i.test(raw)) return;
      const cleaned = cleanPageUrl(raw);
      if (cleaned === raw) return;
      e.preventDefault();
      a.setAttribute("href", cleaned);
      if (e.metaKey || e.ctrlKey || e.shiftKey || a.target === "_blank") {
        window.open(cleaned, a.target || "_blank");
      } else {
        window.location.assign(cleaned);
      }
    },
    true
  );

  function slugFromHref(href) {
    if (!href) return null;
    const m = String(href).match(/\/produkt\/([^\/?#]+)/);
    return m ? decodeURIComponent(m[1].replace(/\.html$/, "")) : null;
  }

  function closestCard(el) {
    return (
      el.closest("article") ||
      el.closest("li") ||
      el.closest("[class*='ProductCard']") ||
      el.closest("[class*='Card']") ||
      el.closest("[class*='card']") ||
      el.closest("[class*='Produkt']") ||
      el.parentElement
    );
  }

  function replacePrices(root, product) {
    if (!root || !product) return;
    const texts = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!eurRe.test(node.nodeValue || "")) continue;
      eurRe.lastIndex = 0;
      texts.push(node);
    }
    texts.forEach((n, idx) => {
      const next = (n.nodeValue || "").replace(eurRe, () => {
        if (idx === 0) return product.price_text;
        if (idx === 1 && product.member_text) return product.member_text;
        return product.price_text;
      });
      n.nodeValue = next;
    });
  }

  function applyStockUi(root, product) {
    if (!root) return;
    const inStock = !!product.in_stock;
    const label = product.stock_text || (inStock ? "В наличност (5+ бр.)" : "Изчерпано");

    root.querySelectorAll('[class*="stock"]').forEach((el) => {
      if (inStock) {
        el.className = el.className
          .replace(/stockOut/g, "stockIn")
          .replace(/skladNic/g, "stock");
      } else {
        el.className = el.className.replace(/stockIn/g, "stockOut");
      }
    });

    root.querySelectorAll("*").forEach((el) => {
      if (el.children.length > 0) return;
      const t = (el.textContent || "").trim();
      if (!t) return;
      if (
        /^В наличност/.test(t) ||
        t === "Изчерпан" ||
        t === "Изчерпано" ||
        /^Последни\s+\d+/.test(t)
      ) {
        el.textContent = inStock ? label : "Изчерпано";
      }
    });
  }

  function setCtaText(el, label) {
    const nodes = [...el.childNodes].filter((n) => n.nodeType === 3);
    if (nodes.length) {
      nodes[nodes.length - 1].nodeValue = label;
      return;
    }
    el.textContent = label;
  }

  function applyCta(root, product) {
    if (!root) return;
    const inStock = !!product.in_stock;
    const onPdp = /\/produkt\//.test(location.pathname);
    root.querySelectorAll("button, a").forEach((el) => {
      const t = (el.textContent || "").trim();
      const hasCtaClass = /cta/i.test(el.className || "");
      const isKnownLabel = CTA_LABELS.has(t);
      const looksBroken =
        hasCtaClass &&
        t &&
        !isKnownLabel &&
        (t === product.title || t.length > 24);
      if (!hasCtaClass && !isKnownLabel && !looksBroken) return;

      if (inStock) {
        el.removeAttribute("disabled");
        if ("disabled" in el) el.disabled = false;
        if (
          t === "Извести ме" ||
          t === "Изчерпано" ||
          looksBroken
        ) {
          setCtaText(el, onPdp ? "Добави в количката" : "Избери");
        }
      } else if (
        t === "Избери" ||
        t === "В количката" ||
        t === "Добави в количката" ||
        looksBroken
      ) {
        if (el.tagName === "BUTTON") {
          el.disabled = true;
          el.setAttribute("disabled", "");
          setCtaText(el, "Изчерпано");
        } else if (hasCtaClass) {
          setCtaText(el, "Извести ме");
        }
      }
    });
  }

  function applyProductPage(product) {
    const h1 = document.querySelector("h1");
    if (h1 && product.title) h1.textContent = product.title;
    if (product.title) document.title = `${product.title} – HHC-STORE`;
    const root = document.querySelector("main") || document.body;
    replacePrices(root, product);
    applyStockUi(root, product);
    applyCta(root, product);
  }

  const CTA_LABELS = new Set([
    "Избери",
    "Извести ме",
    "Изчерпано",
    "Добави в количката",
    "В количката",
  ]);

  function isCtaLabel(text) {
    const t = (text || "").trim();
    if (!t) return false;
    if (CTA_LABELS.has(t)) return true;
    // Already-broken CTA that was overwritten with a long product title
    // but still uses the green CTA class.
    return false;
  }

  function applyListingCards(products) {
    document.querySelectorAll('a[href*="/produkt/"], a[href*="produkt/"]').forEach((a) => {
      const slug = slugFromHref(a.getAttribute("href"));
      if (!slug) return;
      const product = products[slug];
      const card = closestCard(a);
      if (!product || product.archived) {
        if (card && card.style) {
          card.style.display = "none";
          card.setAttribute("data-hhc-archived", "1");
        }
        return;
      }
      if (card && card.getAttribute("data-hhc-archived") === "1") {
        card.style.display = "";
        card.removeAttribute("data-hhc-archived");
      }

      // Only rewrite product TITLE links — never green CTA links labeled "Избери".
      const cls = a.className || "";
      const text = (a.textContent || "").trim();
      const isTitleLink =
        /title/i.test(cls) ||
        a.querySelector('[class*="title"]') ||
        (/titleText/i.test(cls) || a.closest('[class*="title"]'));
      const isCtaLink = /cta/i.test(cls) || isCtaLabel(text);
      if (
        product.title &&
        isTitleLink &&
        !isCtaLink &&
        a.childElementCount <= 1 &&
        text &&
        text !== product.title &&
        !CTA_LABELS.has(text)
      ) {
        const target = a.querySelector('[class*="titleText"]') || a;
        if (target.childElementCount === 0) target.textContent = product.title;
      }

      // Restore CTA links that were wrongly rewritten to the product title.
      if (/cta/i.test(cls) && text && text === product.title) {
        a.textContent = product.in_stock ? "Избери" : "Извести ме";
      }

      replacePrices(card, product);
      applyStockUi(card, product);
      applyCta(card, product);
    });
  }

  function apply() {
    if (!catalog || !catalog.products) return;
    const path = location.pathname.replace(/\.html$/, "");
    const m = path.match(/\/produkt\/([^\/]+)/);
    if (m) {
      const product = catalog.products[decodeURIComponent(m[1])];
      if (!product || product.archived) {
        document.documentElement.innerHTML =
          "<body style='background:#111;color:#eee;font-family:sans-serif;padding:40px'><h1>Продуктът не е наличен</h1><p><a href='/' style='color:#d4af37'>Към магазина</a></p></body>";
        return;
      }
      applyProductPage(product);
    }
    applyListingCards(catalog.products);
  }

  async function load() {
    try {
      let res = await fetch(`${CATALOG_URL}?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (!res.ok) {
        res = await fetch(`${CATALOG_FALLBACK}?t=${Date.now()}`, {
          cache: "no-store",
        });
      }
      if (!res.ok) return;
      catalog = await res.json();
      apply();
    } catch {
      // Storefront still works from static HTML if catalog missing.
    }
  }

  load();
  setTimeout(() => {
    normalizeDocumentLinks(document);
    apply();
  }, 400);
  setTimeout(apply, 1200);
  setTimeout(load, 2500);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) load();
  });
})();
