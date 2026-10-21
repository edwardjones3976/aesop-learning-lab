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
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error(`Server at ${url} failed to respond within ${timeoutMs}ms`);
}

function initSeededDb(dbPath, learnerId) {
  return new Promise((resolve, reject) => {
    const pyCode = [
      'import sqlite3, sys',
      'from aesop_lab.storage.sqlite import SQLiteStore',
      'db_file = sys.argv[1]',
      'uid = sys.argv[2]',
      'store = SQLiteStore(db_file)',
      'store.close()',
      'conn = sqlite3.connect(db_file)',
      'conn.execute("INSERT INTO learner_identity VALUES (1, ?)", (uid,))',
      'conn.commit()',
      'conn.close()',
    ].join('; ');

    const proc = spawn('python', ['-c', pyCode, dbPath, learnerId], {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stderr = '';
    proc.stderr.on('data', chunk => { stderr += chunk.toString(); });
    proc.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(`Failed to init db (exit ${code}): ${stderr}`));
    });
    proc.on('error', reject);
  });
}

async function startServerForLearner(learnerId) {
  const port = await getFreePort();
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aesop-smoke-'));
  const tempDbPath = path.join(tempDir, 'test.db');

  await initSeededDb(tempDbPath, learnerId);

  const serverBaseUrl = `http://127.0.0.1:${port}`;
  const pythonScript = path.join(repoRoot, 'scripts', 'run_foreman.py');
  const serverProcess = spawn('python', [pythonScript, '--port', String(port), '--db', tempDbPath], {
    cwd: repoRoot,
    stdio: 'ignore',
  });

  await waitForServer(serverBaseUrl);

  const cleanup = async () => {
    if (serverProcess) {
      serverProcess.kill();
      await new Promise(r => serverProcess.on('close', r));
    }
    if (tempDir) {
      try {
        fs.rmSync(tempDir, { recursive: true, force: true });
      } catch (_) {
        // best-effort cleanup
      }
    }
  };

  return { serverBaseUrl, cleanup };
}

// Learner IDs are chosen for the current protocol's seed (v8): user_0 is assigned text, user_9 diagram.
const testCases = [
  { width: 1280, height: 800, label: '1280x800', theme: 'light', condition: 'text', learnerId: 'user_0' },
  { width: 1280, height: 800, label: '1280x800', theme: 'dark', condition: 'diagram', learnerId: 'user_9' },
  { width: 375, height: 800, label: '375x800', theme: 'light', condition: 'diagram', learnerId: 'user_9' },
  { width: 375, height: 800, label: '375x800', theme: 'dark', condition: 'text', learnerId: 'user_0' },
];

for (const c of testCases) {
  test(`smoke Foreman UI at ${c.label} in ${c.theme} theme (${c.condition} condition)`, async ({ page }) => {
    const { serverBaseUrl, cleanup } = await startServerForLearner(c.learnerId);

    try {
      const consoleErrors = [];
      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      page.on('pageerror', err => {
        consoleErrors.push(err.message || String(err));
      });

      await page.setViewportSize({ width: c.width, height: c.height });
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
      await themeSelect.selectOption(c.theme);
      expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(c.theme);

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

      // Verify the experimental lesson condition matches expectations
      const diagramElement = page.locator('figure.lesson-diagram');
      if (c.condition === 'diagram') {
        await expect(diagramElement).toBeVisible();
      } else {
        await expect(diagramElement).toHaveCount(0);
      }

      // (d) The How this works panel (details.rail-panel) can be opened and representative child contents are visible at both widths.
      const railPanel = page.locator('details.rail-panel');
      const railSummary = railPanel.locator('summary');
      await railSummary.click();
      await expect(railPanel).toHaveAttribute('open', '');
      await expect(railPanel).toBeVisible();
      // Assert representative children (.side-intro and .rail-card) are visible
      await expect(railPanel.locator('.side-intro')).toBeVisible();
      await expect(railPanel.locator('.rail-card').first()).toBeVisible();

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
      await expect(completeButton).toBeVisible();
      await completeButton.click();

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

      // Rendered Quiet-view checks in practice state after the first lesson:
      // with #focus checked, assert via Playwright's toBeVisible() that .notice and .why are visible and that details.workspace-evidence is hidden, at both widths.
      await focusCheck.check();
      await expect(page.locator('.notice')).toBeVisible();
      await expect(page.locator('.why')).toBeVisible();
      await expect(page.locator('details.workspace-evidence')).toBeHidden();
      await focusCheck.uncheck();
      await expect(page.locator('details.workspace-evidence')).toBeVisible();

      expect(consoleErrors).toEqual([]);
    } finally {
      await cleanup();
    }
  });
}


test('deletion survives reload until explicit restart and keeps minutes preferences', async ({ page }) => {
  const server = await startServerForLearner('delete-reload-test');
  try {
    await page.goto(server.serverBaseUrl, { waitUntil: 'networkidle' });
    await page.locator('details.settings-panel > summary').click();
    await expect(page.locator('#content')).not.toBeEmpty();
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#delete').click();
    await expect(page.locator('#start-again')).toBeVisible();
    await page.locator('#minutes').selectOption('45');
    await page.reload();
    await expect(page.getByText('Your data was deleted', { exact: true })).toBeVisible();
    await expect(page.locator('#minutes')).toHaveValue('45');
    const data = await page.request.get(server.serverBaseUrl + '/api/v2/export');
    expect((await data.json()).learnerIdentity).toEqual([]);
    await page.locator('#start-again').click();
    await expect(page.locator('#start-again')).toHaveCount(0);
    await expect.poll(async () => {
      const response = await page.request.get(server.serverBaseUrl + '/api/v2/export');
      return (await response.json()).learnerIdentity.length;
    }).toBe(1);
  } finally {
    await server.cleanup();
  }
});
