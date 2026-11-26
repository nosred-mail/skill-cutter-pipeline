#!/usr/bin/env node
/**
 * Renderiza thumbnails HTML (9:16 em 1080x1920 e/ou 16:9 em 1280x720) para PNG
 * usando Playwright + Chrome/Edge local (ou Chromium do Playwright/HyperFrames).
 *
 * Uso:
 *   node render_thumbs.mjs --html9x16 thumb_9x16.html --out9x16 capa_9x16.png \
 *                          --html16x9 thumb_16x9.html --out16x9 capa_16x9.png
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--') && i + 1 < argv.length) {
      out[a.slice(2)] = argv[++i];
    }
  }
  return out;
}

async function loadPlaywright() {
  const home = os.homedir();
  const candidates = [
    'playwright',
    path.join(process.cwd(), 'node_modules', 'playwright', 'index.mjs'),
    path.join(home, '.agents', 'skills', 'hyperframes', 'node_modules', 'playwright', 'index.mjs'),
    path.join(home, '.claude', 'skills', 'hyperframes', 'node_modules', 'playwright', 'index.mjs'),
    path.join(home, '.gemini', 'config', 'skills', 'hyperframes', 'node_modules', 'playwright', 'index.mjs'),
  ];
  for (const c of candidates) {
    try {
      const spec = c === 'playwright' ? c : pathToFileURL(c).href;
      return await import(spec);
    } catch {
      // try next
    }
  }
  throw new Error('Playwright nao encontrado. Instale `playwright` ou a CLI do HyperFrames.');
}

function findBrowserExecutable() {
  if (process.env.HYPERFRAMES_BROWSER_PATH && fs.existsSync(process.env.HYPERFRAMES_BROWSER_PATH)) {
    return process.env.HYPERFRAMES_BROWSER_PATH;
  }
  const win = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  ];
  const mac = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  ];
  const linux = ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  const list = process.platform === 'win32' ? win : process.platform === 'darwin' ? mac : linux;
  return list.find((p) => fs.existsSync(p));
}

const args = parseArgs(process.argv);
if (!args.html9x16 && !args.html16x9) {
  console.error('Informe --html9x16/--out9x16 e/ou --html16x9/--out16x9');
  process.exit(1);
}

const { chromium } = await loadPlaywright();
const executablePath = findBrowserExecutable();
const browser = await chromium.launch({
  ...(executablePath ? { executablePath } : {}),
  headless: true,
});

try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const rendered = [];

  if (args.html9x16 && args.out9x16) {
    await page.setViewportSize({ width: 1080, height: 1920 });
    await page.goto(pathToFileURL(path.resolve(args.html9x16)).href, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    fs.mkdirSync(path.dirname(path.resolve(args.out9x16)), { recursive: true });
    await page.screenshot({ path: path.resolve(args.out9x16) });
    rendered.push(path.resolve(args.out9x16));
  }

  if (args.html16x9 && args.out16x9) {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(pathToFileURL(path.resolve(args.html16x9)).href, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    fs.mkdirSync(path.dirname(path.resolve(args.out16x9)), { recursive: true });
    await page.screenshot({ path: path.resolve(args.out16x9) });
    rendered.push(path.resolve(args.out16x9));
  }

  console.log(JSON.stringify({ ok: true, rendered }, null, 2));
} finally {
  await browser.close();
}
