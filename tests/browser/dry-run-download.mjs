import { chromium } from '@playwright/test';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import net from 'node:net';
// Choose an unused loopback port rather than touching an owner's running preview.
const probe = net.createServer();
await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
const port = probe.address().port;
await new Promise(resolve => probe.close(resolve));
const base = `http://127.0.0.1:${port}`;
const dir = mkdtempSync(path.join(os.tmpdir(), 'aesop-download-'));
const server = spawn('py', ['scripts/run_foreman.py', '--port', String(port), '--db', path.join(dir, 'fresh.sqlite3')]);
let browser;
try {
  let ready = false;
  for (let i = 0; i < 100; i++) {
    assert.equal(server.exitCode, null, 'temporary server exited');
    try { if ((await fetch(base + '/api/v2/overview')).ok) { ready = true; break; } } catch {}
    await new Promise(r => setTimeout(r, 100));
  }
  assert(ready);
  browser = await chromium.launch();
  const page = await browser.newPage({acceptDownloads: true});
  await page.goto(base + '/');
  await page.locator('#complete').waitFor();
  console.log('notice:', await page.locator('.notice').innerText());
  await page.locator('#complete').click();
  await page.locator('#save').waitFor();
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#export').click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(), 'aesop-foreman-data.json');
  const downloaded = JSON.parse(readFileSync(await download.path(), 'utf8'));
  assert(downloaded.displayPreferences);
  assert(downloaded.experimentAssignments.length > 0);
  const output = path.join(dir, 'overview-SYNTHETIC.json');
  execFileSync('curl.exe', ['-s', base + '/api/v2/overview', '-o', output]);
  assert.deepEqual(downloaded.derived.overview, JSON.parse(readFileSync(output, 'utf8')));
  console.log('PASS: actual download filename, raw assignments, displayPreferences, derived.overview, curl.exe cross-check');
} finally {
  if (browser) await browser.close();
  if (server.exitCode === null) {
    const exited = new Promise(r => server.once('exit', r));
    server.kill();
    await exited;
  }
  rmSync(dir, {recursive: true, force: true});
}
