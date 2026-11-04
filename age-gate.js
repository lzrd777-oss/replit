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
      } catch {
        // Embedded previews may block cookies.
      }
      try {
        localStorage.setItem("hhc:entered", "1");
      } catch {
        // Embedded previews may also block local storage.
      }

      // Carry this explicit confirmation to the destination even if the
      // embedded browser refuses cookies and local storage.
      window.location.assign("/bg.html?age_confirmed=1");
    },
    { capture: true },
  );

  ageGate.querySelectorAll("button")[1]?.addEventListener("click", () => {
    window.location.assign("https://www.google.com/");
  });
})();
