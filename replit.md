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

Verification confirmed that the initial age-verification screen renders, the
homepage aliases and contact page respond, and private files return 404.
Screens beyond the age-verification interaction were not visually verified.
The original ZIP contains no `.woff2` fonts and omits some decorative images
referenced by the pages. Browser logs also report malformed imported `srcset`
attributes. These are limitations of the imported snapshot, not dependencies
that the static server can install.
