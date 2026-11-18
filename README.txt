HUSTLE AI — CLOUDFLARE PROXY CONNECTED UPDATE

WHAT CHANGED
- All ESPN requests now use your deployed Cloudflare Worker:
  https://hustle-ai-espn-proxy.workmanquintavius.workers.dev
- Player Research and Prop Analyzer share one more tolerant ESPN player-result parser.
- Prop player search has a short debounce, loading feedback, and visible errors.
- Game-log requests use the NBA season end year (e.g. 2027 during Nov 2026).
- Request timeouts and clearer proxy/API errors were added.
- Service worker cache was bumped so the new JavaScript can replace the older cached version.

PUBLISH THE UPDATE
1. Open your GitHub repository: https://github.com/inthhemaking/project-hustle-ai
2. Upload/replace the files in this package at the repository root:
   index.html, app.js, styles.css, sw.js, manifest.webmanifest, and the icons/ folder.
3. Do NOT replace app.py or requirements.txt.
4. Commit the changes to the main branch.
5. Wait for GitHub Pages to publish the update.
6. On your iPhone, open the app in Safari and refresh it. If it still shows the old version, close the installed HUSTLE AI app completely, open the GitHub Pages URL in Safari, refresh, then Add to Home Screen/open again if needed.

PROXY STATUS
The Worker was confirmed by the user to return ESPN NBA team JSON from:
https://hustle-ai-espn-proxy.workmanquintavius.workers.dev/site/sports/basketball/nba/teams

PLAYER SEARCH TESTS AFTER PUBLISH
Search for:
- LeBron James
- Stephen Curry
- Nikola Jokic

Then select each result. Confirm the game log loads. Prop Analyzer should use the same search and selected player.

IMPORTANT
- The Cloudflare Worker is already deployed separately. Do not paste the PWA JavaScript into Cloudflare.
- This package does not change the Cloudflare Worker code.
- ESPN's public endpoints and response shapes can change. The team endpoint success confirms the proxy route works for that endpoint, but player search and game logs still require live end-to-end testing after publishing.
- Picks and parlays remain local to this iPhone/browser and are not cloud-synced.
- Keep the old Streamlit app until the PWA is tested successfully.
