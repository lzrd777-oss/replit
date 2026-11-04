---
name: Preview interaction checks
description: How to verify entry into the imported site without mistaking a DOM change for a working user flow.
---

Test age-confirmation entry through the proxied development URL with real
pointer input, then inspect the rendered destination and scrolling. Include
desktop, mobile, and browser-storage-blocked cases.

**Why:** The user still reported being unable to view the site after an earlier
test only activated the button programmatically and checked that the overlay
became hidden. That was not enough evidence for the user-visible outcome.

**How to apply:** Verify the homepage is actually visible and scrollable after
confirmation, and verify direct entry to a subpage. Do not assume browser
storage is available inside an embedded preview, and do not remove the age
prompt without the visitor explicitly confirming.
