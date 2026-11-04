# Imported website

This project contains a static website export, not the original Next.js source
or backend. Preserve the existing HTML, JavaScript, CSS, and asset structure.

## Running

Use the **Start application** workflow, or run `python3 server.py`.
The server listens on `0.0.0.0:5000` and uses only Python's standard library;
no dependency installation or secrets are needed.

The homepage is available at `/`, `/bg`, `/bg/`, and `/bg.html`.
Imported HTML pages also support extensionless paths, such as `/bg/kontakt`.
Only public website files are served; configuration, the import ZIP, source
files, and directory listings are not exposed.

## Limitations

This setup serves the pages and assets included in the import. It does not
recreate missing pages, original API endpoints, authentication, search,
checkout, payment processing, or other server-side services. Bundled scripts
may still reference the original site's services. Do not treat this static
copy as a working independent store or submit personal information through it.

The local age-gate handler is injected into all imported HTML pages. Accepting
the age prompt always navigates to the homepage, including from subpages.
Explicit confirmation is carried to the destination in the URL so the homepage
opens even when Preview blocks cookies and local storage. Declining still leaves
the site.
Verification confirmed that a real pointer click on the age-confirmation button
opens the homepage with the prompt hidden and the page content unlocked.
The homepage aliases and contact page respond, and private files return 404.
The original ZIP contains no `.woff2` fonts and omits some decorative images
referenced by the pages. Browser logs also report malformed imported `srcset`
attributes. These are limitations of the imported snapshot, not dependencies
that the static server can install.
