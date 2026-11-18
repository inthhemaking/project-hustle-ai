HUSTLE AI — INSTALLABLE IPHONE WEB APP (PWA)

WHAT THIS IS
This is a separate, mobile-first installable web app. It is not an App Store native app. On iPhone, open its HTTPS address in Safari, tap Share, then Add to Home Screen. It launches in a standalone app-style window.

FILES
index.html, styles.css, app.js, manifest.webmanifest, sw.js, icons/

PUBLISH WITH GITHUB PAGES
1. Open https://github.com/inthhemaking/project-hustle-ai
2. Add the files and icons folder from this package to the repository root. Do NOT replace app.py or requirements.txt; those are the existing Streamlit project and remain separate.
3. Commit the files.
4. In GitHub, open Settings → Pages.
5. Under Build and deployment, choose Deploy from a branch; choose main and /(root), then Save.
6. Wait for GitHub Pages to publish. The expected address is https://inthhemaking.github.io/project-hustle-ai/ .
7. On the iPhone, open that address in Safari (not an in-app browser), tap Share → Add to Home Screen → Add.

IMPORTANT LIMITATIONS IN THIS FIRST PWA BUILD
- ESPN data is requested directly from the iPhone browser. If ESPN blocks cross-origin browser requests or changes its public response format, a small hosted API proxy will be needed. The browser request has not been verified on a real iPhone in this environment.
- The pick tracker is stored locally on the iPhone/browser. It does not sync across devices and may be lost if Safari website data is cleared. Add a persistent backend before relying on it for long-term records.
- The app shell can open offline after it has been loaded once; live ESPN data requires internet.
- Injury records are normalized into readable cards. The age label is calculated from ESPN's report date when present; missing dates are explicitly shown as not supplied. Reports older than 24 hours are separated for verification. A fresh fetch does not guarantee ESPN has published a fresh report.
- This package is a PWA front-end, not a replacement for the existing Streamlit backend. Keep the old Streamlit app until the PWA data calls and workflows are verified.
