import { test, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..');

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const address = srv.address();
      const port = typeof address === 'object' && address !== null ? address.port : 0;
      srv.close(err => {
        if (err) reject(err);
        else resolve(port);
      });
    });
    srv.on('error', reject);
  });
}

async function waitForServer(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch (_) {
      // server not ready yet
    }
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error(`Server at ${url} failed to respond within ${timeoutMs}ms`);
}

let serverProcess = null;
let serverBaseUrl = '';
let tempDbDir = '';

test.beforeAll(async () => {
  const port = await getFreePort();
  tempDbDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aesop-smoke-'));
  const tempDbPath = path.join(tempDbDir, 'test.db');

  serverBaseUrl = `http://127.0.0.1:${port}`;

  const pythonScript = path.join(repoRoot, 'scripts', 'run_foreman.py');
  serverProcess = spawn('python', [pythonScript, '--port', String(port), '--db', tempDbPath], {
    cwd: repoRoot,
    stdio: 'ignore',
  });

  await waitForServer(serverBaseUrl);
});

test.afterAll(async () => {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
  if (tempDbDir) {
    try {
      fs.rmSync(tempDbDir, { recursive: true, force: true });
    } catch (_) {
      // best-effort cleanup
    }
  }
});

const viewports = [
  { width: 1280, height: 800, label: '1280x800' },
  { width: 375, height: 800, label: '375x800' },
];

const themes = ['light', 'dark'];

for (const vp of viewports) {
  for (const th of themes) {
    test(`smoke Foreman UI at ${vp.label} in ${th} theme`, async ({ page }) => {
      const consoleErrors = [];
      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      page.on('pageerror', err => {
        consoleErrors.push(err.message || String(err));
      });

      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto(serverBaseUrl, { waitUntil: 'networkidle' });

      // Open settings panel if closed (summary "YOUR SETTING")
      const settingsPanel = page.locator('details.settings-panel');
      if (await settingsPanel.count() > 0) {
        const isOpen = await settingsPanel.evaluate(el => el.hasAttribute('open'));
        if (!isOpen) {
          await settingsPanel.locator('summary').click();
        }
      }

      // Theme selection (set the #theme select)
      const themeSelect = page.locator('#theme');
      await themeSelect.selectOption(th);
      expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(th);

      // (a) The page loads with no console errors and no horizontal overflow (document.documentElement.scrollWidth <= innerWidth).
      expect(consoleErrors).toEqual([]);
      const overflowCheck = await page.evaluate(() => {
        return {
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
          overflows: document.documentElement.scrollWidth > window.innerWidth,
        };
      });
      expect(overflowCheck.overflows, `Page overflows horizontally: scrollWidth=${overflowCheck.scrollWidth}, innerWidth=${overflowCheck.innerWidth}`).toBe(false);

      // (d) The How this works panel (details.rail-panel) can be opened and is visible at both widths.
      const railPanel = page.locator('details.rail-panel');
      const railSummary = railPanel.locator('summary');
      await railSummary.click();
      await expect(railPanel).toHaveAttribute('open', '');
      await expect(railPanel).toBeVisible();

      // (c) With Quiet view on (#focus), .workspace-evidence is not visible and .notice is visible.
      const focusCheck = page.locator('#focus');
      await focusCheck.check();
      await expect(page.locator('.notice')).toBeVisible();
      await expect(page.locator('.workspace-evidence')).toBeHidden();
      // Turn Quiet view off for subsequent checks
      await focusCheck.uncheck();
      await expect(page.locator('.workspace-evidence')).toBeVisible();

      // (b) After completing the first lesson (click #complete), the activity card appears before details.workspace-evidence in #content, and the evidence panel is closed.
      const completeButton = page.locator('#complete');
      if (await completeButton.isVisible()) {
        await completeButton.click();
      }

      // Wait for activity card to appear in #content
      const activityCard = page.locator('#content .activity-card');
      await expect(activityCard).toBeVisible();

      const evidenceDetails = page.locator('#content details.workspace-evidence');
      await expect(evidenceDetails).toBeVisible();
      // verify evidence panel is closed
      const isOpen = await evidenceDetails.evaluate(el => el.hasAttribute('open'));
      expect(isOpen).toBe(false);

      // verify activity card appears BEFORE details.workspace-evidence in #content
      const orderCheck = await page.evaluate(() => {
        const content = document.querySelector('#content');
        if (!content) return { found: false };
        const activity = content.querySelector('.activity-card');
        const evidence = content.querySelector('details.workspace-evidence');
        if (!activity || !evidence) return { found: false, hasActivity: !!activity, hasEvidence: !!evidence };
        const position = activity.compareDocumentPosition(evidence);
        // Node.DOCUMENT_POSITION_FOLLOWING is 4, which means evidence follows activity
        return {
          found: true,
          evidenceFollowsActivity: Boolean(position & Node.DOCUMENT_POSITION_FOLLOWING),
        };
      });
      expect(orderCheck.found).toBe(true);
      expect(orderCheck.evidenceFollowsActivity).toBe(true);

      // Also verify again no horizontal overflow and no console errors after completing lesson
      const postOverflowCheck = await page.evaluate(() => {
        return {
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
          overflows: document.documentElement.scrollWidth > window.innerWidth,
        };
      });
      expect(postOverflowCheck.overflows, `Page overflows horizontally after lesson complete: scrollWidth=${postOverflowCheck.scrollWidth}, innerWidth=${postOverflowCheck.innerWidth}`).toBe(false);

      // Check quiet view again when on the activity step
      await focusCheck.check();
      await expect(page.locator('.notice')).toBeVisible();
      await expect(page.locator('.workspace-evidence')).toBeHidden();
      await focusCheck.uncheck();

      expect(consoleErrors).toEqual([]);
    });
  }
}
