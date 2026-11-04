(() => {
  const ageGate = document.querySelector("[data-age-gate-root]");
  const acceptButton = ageGate?.querySelector("button");

  if (!ageGate || !acceptButton) return;

  acceptButton.addEventListener(
    "click",
    () => {
      try {
        document.cookie =
          "hhc_age_verified=true; path=/; max-age=2592000; samesite=lax";
        localStorage.setItem("hhc:entered", "1");
      } catch {
        // The current page can still be opened if browser storage is disabled.
      }

      for (const element of document.body.children) {
        if (element instanceof HTMLElement) element.inert = false;
      }

      document.documentElement.removeAttribute("data-age-gate");
      window.dispatchEvent(new Event("hhc:entered"));
    },
    { capture: true },
  );
})();
