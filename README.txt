HUSTLE AI — ROSTER SEARCH FIX

This update replaces the ESPN search endpoint (which is returning HTTP 403) with a searchable player directory built from ESPN's NBA team roster endpoints through your Cloudflare Worker.

FILES
- index.html
- app.js
- styles.css
- sw.js
- manifest.webmanifest
- icons/

DEPLOY
1. Open your GitHub repository: inthhemaking/project-hustle-ai
2. Upload/replace the files above in the repository root (keep the icons folder).
3. Commit the changes to main.
4. Wait for GitHub Pages to finish publishing.
5. On iPhone Safari, open the HUSTLE AI app and refresh. If it still shows old code, close the installed app, open the site in Safari, reload once, then Add to Home Screen app again if needed.

PLAYER SEARCH
- The first search builds an NBA roster index by requesting each team's /roster route through the Worker. This can take several seconds.
- The index is cached on the device for 12 hours. Subsequent searches are local and fast.
- Both Player Research and Prop Analyzer use the same roster index.
- If one or more team roster endpoints fail, the index can still be built if at least 30 players were returned. A very incomplete index shows an error instead of pretending there are no matches.

CLOUDFLARE WORKER
Keep the existing Worker URL configured in app.js. Do not replace the Worker code for this update.

IMPORTANT
The user verified that the Worker can return NBA team data and the Lakers roster endpoint returns JSON player data. This update has not been deployed to GitHub Pages or live-tested on the user's iPhone yet. ESPN game-log availability remains dependent on the separate ESPN gamelog endpoint.
