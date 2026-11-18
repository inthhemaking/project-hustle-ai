HUSTLE AI — DIRECT ESPN GAME LOG FIX

WHAT THIS UPDATE FIXES
- Removes the Cloudflare Worker URL from the app. ESPN requests are made directly from the iPhone browser.
- Fixes ESPN game-log parsing: ESPN stores game metadata in an events object and stat rows inside seasonTypes[].categories[].events[]. The previous parser treated events as an array and did not join the stat rows to their dates/opponents.
- Correctly reads made/attempted values such as 4-10 as 4 made three-pointers.
- Keeps the existing on-device NBA player index so Player Research and Prop Analyzer do not need to rebuild the roster directory on every visit.
- Preserves the existing tracker, saved picks, parlays, design, and local storage keys.

FILES
- index.html
- app.js
- styles.css
- sw.js
- manifest.webmanifest
- icons/

INSTALL
1. In your GitHub repository, replace the files in the ZIP at the repository root (keep the icons folder).
2. Commit the changes to main and wait for GitHub Pages to publish.
3. On iPhone, close the installed HUSTLE AI app completely, open https://inthhemaking.github.io/project-hustle-ai/ in Safari, reload, then reopen the home-screen app.

IMPORTANT
- This build does not call the Cloudflare Worker.
- Existing roster search data is reused from localStorage under hustle_player_index. If the browser's website data has been cleared, the app may need a new player index; ESPN's team-roster endpoints can have browser CORS restrictions.
- ESPN is an unofficial public data source and can change or rate-limit requests.
- The parser is validated against the documented ESPN v3 gamelog response shape. Live ESPN requests could not be exercised from this build environment, so the ZIP is not represented as live-network tested.
