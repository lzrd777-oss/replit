(() => {
  const ageGate = document.querySelector("[data-age-gate-root]");
  const acceptButton = ageGate?.querySelector("button");

  if (!ageGate || !acceptButton) return;

  acceptButton.addEventListener(
    "click",
    () => {
      let confirmationSaved = false;
      try {
        document.cookie =
          "hhc_age_verified=true; path=/; max-age=2592000; samesite=lax";
        confirmationSaved = /(^|;\s*)hhc_age_verified=true/.test(document.cookie);
      } catch {
        // Embedded previews may block cookies.
      }
      try {
        localStorage.setItem("hhc:entered", "1");
        confirmationSaved =
          localStorage.getItem("hhc:entered") === "1" || confirmationSaved;
      } catch {
        // Embedded previews may also block local storage.
      }

      if (confirmationSaved) {
        if (location.pathname === "/" || location.pathname === "/index.html") {
          window.location.assign("/bg.html");
        } else {
          window.location.reload();
        }
        return;
      }

      // Still let an explicitly confirmed visitor enter this page when their
      // browser refuses persistent storage in the preview iframe.
      for (const element of document.body.children) {
        if (element instanceof HTMLElement) element.inert = false;
      }
      document.documentElement.removeAttribute("data-age-gate");
      ageGate.style.display = "none";
      window.dispatchEvent(new Event("hhc:entered"));
    },
    { capture: true },
  );

  ageGate.querySelectorAll("button")[1]?.addEventListener("click", () => {
    window.location.assign("https://www.google.com/");
  });
})();
