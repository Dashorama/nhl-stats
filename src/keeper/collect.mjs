// Browser transport only. Pure parsers and keeper rules live in Python.
import { access, readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { homedir } from 'node:os';

const [command, seasonText, profile, leagueText] = process.argv.slice(2);
const seasons = JSON.parse(await readFile(new URL('./seasons.json', import.meta.url), 'utf8'));
const season = Number(seasonText), league = Number(leagueText ?? seasons[seasonText]);
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
  const origin = 'https://hockey.fantasysports.yahoo.com';
  let root = `${origin}/hockey/${league}`;
  async function draftSeason() {
    await page.goto(`${root}/draftresults`, {waitUntil: 'domcontentloaded'});
    const options = await page.locator('#yfa-draftresults-select option').evaluateAll(
      es => es.map(e => ({value:e.value, text:e.textContent})));
    return Number(options.find(o => o.value === 'current')?.text.match(/\d{4}/)?.[0]);
  }
  // Prefer the season-specific bare ID. Yahoo currently requires the year-prefixed
  // archive on this authenticated host; validate that archive's own draft season.
  if (await draftSeason() !== season) {
    root = `${origin}/${season}/hockey/${league}`;
    if (await draftSeason() !== season)
      throw Error('Yahoo login or requested season metadata unavailable; re-login manually');
  }
  const pages = [];
  let transactionCount = 0;
  if (command === 'reconcile') {
    pages.push(await page.content());
  } else {
    let url = `${root}/transactions?transactionsfilter=trade`;
    const visited = new Set();
    while (url) {
      if (visited.size >= 100) throw Error('transaction pagination incomplete');
      visited.add(url);
      await page.goto(url, {waitUntil:'domcontentloaded'});
      if (new URL(page.url()).pathname !== new URL(url).pathname)
        throw Error('transaction season/league redirect; refusing mislabeled trades');
      pages.push(await page.content());
      const meta = await page.locator('body').evaluate(body => ({
        tradeCount: body.querySelectorAll('table.Tst-transaction-table .F-trade').length,
        pagers: [...body.querySelectorAll('ul.pagingnavlist')].map(pager => {
          const last = pager.querySelector('li.last');
          return {href: last?.querySelector('a')?.href || null,
                  terminal: Boolean(last?.classList.contains('F-shade'))};
        }),
      }));
      if (meta.pagers.some(p => !p.href && !p.terminal))
        throw Error('unrecognized pagination marker');
      const next = [...new Set(meta.pagers.filter(p => p.href).map(p => p.href))];
      if (next.length > 1 || (next.length && meta.pagers.some(p => p.terminal)))
        throw Error('ambiguous pagination');
      if (meta.tradeCount > 25 || (next.length && meta.tradeCount !== 25))
        throw Error('unsupported transaction page size');
      if (!next.length && meta.tradeCount === 25 && !meta.pagers.some(p => p.terminal))
        throw Error('missing terminal pagination evidence on full page');
      transactionCount += meta.tradeCount;
      url = next[0] || '';
      if (url) {
        const parsed = new URL(url, page.url());
        if (parsed.origin !== 'https://hockey.fantasysports.yahoo.com' ||
            parsed.pathname !== new URL(page.url()).pathname ||
            parsed.searchParams.get('transactionsfilter') !== 'trade')
          throw Error('unexpected transaction pagination target');
        if (visited.has(parsed.href)) throw Error('transaction pagination incomplete: cycle');
        const offset = Number(new URL(page.url()).searchParams.get('count') || 0);
        if (parsed.searchParams.get('count') !== String(offset + 25))
          throw Error('unexpected transaction pagination offset');
        url = parsed.href;
      }
    }
  }
  process.stdout.write(JSON.stringify({pages, season, league_id:league,
    ...(command === 'scan-trades' ? {complete:true, transaction_count:transactionCount} : {})}));
} finally {
  await context.close();
}
