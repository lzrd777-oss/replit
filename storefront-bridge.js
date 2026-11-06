(() => {
  const CATALOG_URL = "/storage/catalog.json";
  let catalog = null;

  const eurRe = /\d[\d\s\u00a0]*(?:[.,]\d{1,2})?\s*€/g;

  function slugFromHref(href) {
    if (!href) return null;
    const m = String(href).match(/\/produkt\/([^\/?#]+)/);
    return m ? decodeURIComponent(m[1].replace(/\.html$/, "")) : null;
  }

  function closestCard(el) {
    return (
      el.closest("article") ||
      el.closest("li") ||
      el.closest("[class*='Card']") ||
      el.closest("[class*='card']") ||
      el.closest("[class*='Produkt']") ||
      el.closest("section") ||
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
        // first price = regular, second often member
        if (idx === 0) return product.price_text;
        if (idx === 1 && product.member_text) return product.member_text;
        return product.price_text;
      });
      n.nodeValue = next;
    });
  }

  function applyStock(root, product) {
    if (!root) return;
    root.querySelectorAll("*").forEach((el) => {
      const t = (el.textContent || "").trim();
      if (!t) return;
      if (/^В наличност/.test(t) || t === "Изчерпан" || t === "Изчерпано") {
        if (el.children.length === 0) el.textContent = product.stock_text;
      }
    });
  }

  function applyProductPage(product) {
    const h1 = document.querySelector("h1");
    if (h1 && product.title) h1.textContent = product.title;
    if (product.title) document.title = `${product.title} – HHC-STORE`;
    replacePrices(document.querySelector("main") || document.body, product);
    applyStock(document.querySelector("main") || document.body, product);
  }

  function applyListingCards(products) {
    document.querySelectorAll('a[href*="/produkt/"]').forEach((a) => {
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
      // Update link/title text if this anchor is the title
      if (a.textContent && a.textContent.trim().length > 3 && product.title) {
        const onlyText = a.childElementCount === 0;
        if (onlyText) a.textContent = product.title;
      }
      replacePrices(card, product);
      applyStock(card, product);
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
      const res = await fetch(`${CATALOG_URL}?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (!res.ok) return;
      catalog = await res.json();
      apply();
    } catch {
      // Storefront still works from static HTML if catalog missing.
    }
  }

  load();
  // Re-apply after Next hydration / late paints.
  setTimeout(apply, 400);
  setTimeout(apply, 1200);
  setTimeout(load, 2500);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) load();
  });
})();
