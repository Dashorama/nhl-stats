// Browser transport only. Pure parsers and keeper rules live in Python.
import { access } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { homedir } from 'node:os';

const [command, seasonText, profile, leagueText = '5003'] = process.argv.slice(2);
const season = Number(seasonText), league = Number(leagueText);
if (!['reconcile', 'scan-trades'].includes(command) || !Number.isInteger(season) ||
    !Number.isInteger(league) || !profile) throw Error('invalid collector arguments');
await access(profile); // Never silently create an unauthenticated profile.
const { chromium } = await import(pathToFileURL(process.env.KEEPER_PLAYWRIGHT ||
  '/home/david/DrillDeck/node_modules/playwright/index.mjs').href);
const context = await chromium.launchPersistentContext(profile, {
  headless: true,
  executablePath: process.env.KEEPER_CHROMIUM ||
    `${homedir()}/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome`,
});
try {
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  await page.goto('https://hockey.fantasysports.yahoo.com/hockey/5003/draftresults',
    {waitUntil: 'domcontentloaded'});
  const options = await page.locator('#yfa-draftresults-select option').evaluateAll(
    es => es.map(e => ({value:e.value, text:e.textContent})));
  const current = Number(options.find(o => o.value === 'current')?.text.match(/\d{4}/)?.[0]);
  if (!current) throw Error('Yahoo login or season metadata unavailable; re-login manually');
  const pages = [];
  if (command === 'reconcile') {
    const option = options.find(o => o.text.includes(String(season)));
    if (!option) throw Error('requested draft season is not available in dropdown');
    // Same URL parameter used by the dropdown's change listener. Yahoo's delayed
    // YUI init can leave selectOption() without an attached event handler.
    await page.goto(`https://hockey.fantasysports.yahoo.com/hockey/5003/draftresults?draft_results_period=${option.value}`,
      {waitUntil:'domcontentloaded'});
    pages.push(await page.content());
  } else {
    if (season !== current && league === 5003)
      throw Error('historical transactions require the archived --league-id');
    let url = `https://hockey.fantasysports.yahoo.com/${season === current ? '' : `${season}/`}hockey/${league}/transactions?transactionsfilter=trade`;
    const visited = new Set();
    while (url) {
      if (visited.has(url) || visited.size >= 100) throw Error('transaction pagination incomplete');
      visited.add(url);
      await page.goto(url, {waitUntil:'domcontentloaded'});
      if (new URL(page.url()).pathname !== new URL(url).pathname)
        throw Error('transaction season/league redirect; refusing mislabeled trades');
      pages.push(await page.content());
      const next = await page.locator('a').evaluateAll(es => es.filter(e =>
        /^(Next|Next ›|Next »)$/i.test(e.textContent.trim())).map(e => e.href));
      if (next.length > 1) throw Error('ambiguous pagination');
      url = next[0] || '';
      if (url) {
        const parsed = new URL(url);
        if (parsed.origin !== 'https://hockey.fantasysports.yahoo.com' ||
            parsed.pathname !== new URL(page.url()).pathname ||
            parsed.searchParams.get('transactionsfilter') !== 'trade')
          throw Error('unexpected transaction pagination target');
      }
    }
  }
  process.stdout.write(JSON.stringify({pages, season, league_id:league}));
} finally {
  await context.close();
}
