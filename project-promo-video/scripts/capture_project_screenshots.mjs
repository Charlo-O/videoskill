import fs from "node:fs/promises";
import path from "node:path";
import {devices, chromium, firefox, webkit} from "playwright";

const SUPPORTED_BROWSERS = {
  chromium,
  firefox,
  webkit,
};

function printHelp() {
  console.log(`Usage:
  node capture_project_screenshots.mjs \\
    --base-url http://127.0.0.1:3000 \\
    --plan ../references/screenshot-plan.example.json \\
    --output-dir F:\\captures

Options:
  --base-url <url>             Base URL of the already-running project.
  --plan <file>                JSON capture plan file.
  --output-dir <dir>           Directory to write screenshots and manifest.
  --browser <name>             chromium | firefox | webkit. Default: chromium
  --device <name>              Optional Playwright device preset.
  --storage-state <file>       Load Playwright storage state from file.
  --save-storage-state <file>  Save storage state after capture.
  --headed                     Run with a visible browser.
  --help                       Show this help text.
`);
}

function parseArgs(argv) {
  const args = {
    browser: "chromium",
    headed: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--headed") {
      args.headed = true;
      continue;
    }

    if (token === "--help") {
      args.help = true;
      continue;
    }

    if (!token.startsWith("--")) {
      throw new Error(`Unexpected argument: ${token}`);
    }

    const key = token.slice(2);
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for ${token}`);
    }

    args[key.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
    index += 1;
  }

  return args;
}

async function readPlan(planFile) {
  const planText = await fs.readFile(planFile, "utf8");
  const plan = JSON.parse(planText);
  if (!Array.isArray(plan.shots) || plan.shots.length === 0) {
    throw new Error("Capture plan must contain a non-empty shots array.");
  }

  return plan;
}

function ensurePngFileName(name) {
  return path.extname(name) ? name : `${name}.png`;
}

function buildUrl(baseUrl, routePath) {
  return new URL(routePath || "/", baseUrl).toString();
}

function clampTimeout(value, fallbackValue) {
  const parsed = Number(value);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }

  return fallbackValue;
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, {recursive: true});
}

async function applyHiddenSelectors(page, selectors) {
  if (!Array.isArray(selectors) || selectors.length === 0) {
    return;
  }

  const selectorText = selectors.join(", ");
  await page.addStyleTag({
    content: `${selectorText} { visibility: hidden !important; opacity: 0 !important; }`,
  });
}

async function runAction(page, action, defaultTimeoutMs) {
  switch (action.type) {
    case "click":
      await page.locator(action.selector).click({
        timeout: clampTimeout(action.timeoutMs, defaultTimeoutMs),
      });
      return;
    case "fill":
      await page.locator(action.selector).fill(action.value ?? "", {
        timeout: clampTimeout(action.timeoutMs, defaultTimeoutMs),
      });
      return;
    case "press":
      await page.locator(action.selector).press(action.key ?? "Enter", {
        timeout: clampTimeout(action.timeoutMs, defaultTimeoutMs),
      });
      return;
    case "hover":
      await page.locator(action.selector).hover({
        timeout: clampTimeout(action.timeoutMs, defaultTimeoutMs),
      });
      return;
    case "select":
      await page.locator(action.selector).selectOption(action.value, {
        timeout: clampTimeout(action.timeoutMs, defaultTimeoutMs),
      });
      return;
    case "wait":
      await page.waitForTimeout(clampTimeout(action.ms, 500));
      return;
    default:
      throw new Error(`Unsupported action type: ${action.type}`);
  }
}

async function captureShot({
  page,
  baseUrl,
  outputDir,
  shot,
  plan,
  defaultTimeoutMs,
}) {
  const url = buildUrl(baseUrl, shot.path);
  const waitUntil = shot.waitUntil ?? plan.waitUntil ?? "networkidle";
  const outputFileName = ensurePngFileName(shot.name);
  const outputPath = path.resolve(outputDir, outputFileName);
  const timeoutMs = clampTimeout(shot.timeoutMs, defaultTimeoutMs);

  await page.goto(url, {waitUntil, timeout: timeoutMs});

  if (shot.waitForSelector) {
    await page.locator(shot.waitForSelector).waitFor({
      state: shot.waitForState ?? "visible",
      timeout: timeoutMs,
    });
  }

  if (plan.waitAfterNavigationMs || shot.waitAfterNavigationMs) {
    await page.waitForTimeout(
      clampTimeout(shot.waitAfterNavigationMs, plan.waitAfterNavigationMs),
    );
  }

  for (const action of shot.actions ?? []) {
    await runAction(page, action, timeoutMs);
  }

  await applyHiddenSelectors(page, plan.hideSelectors ?? []);
  await applyHiddenSelectors(page, shot.hideSelectors ?? []);

  if (shot.waitBeforeScreenshotMs) {
    await page.waitForTimeout(clampTimeout(shot.waitBeforeScreenshotMs, 300));
  }

  if (shot.selector) {
    await page.locator(shot.selector).screenshot({
      path: outputPath,
      timeout: timeoutMs,
    });
  } else {
    await page.screenshot({
      path: outputPath,
      fullPage: Boolean(shot.fullPage ?? plan.fullPage ?? false),
    });
  }

  return {
    name: outputFileName,
    path: shot.path ?? "/",
    url,
    selector: shot.selector ?? null,
    fullPage: Boolean(shot.fullPage ?? plan.fullPage ?? false),
    outputPath,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }

  if (!args.baseUrl || !args.plan || !args.outputDir) {
    printHelp();
    throw new Error("Missing required options.");
  }

  if (!SUPPORTED_BROWSERS[args.browser]) {
    throw new Error(`Unsupported browser: ${args.browser}`);
  }

  const plan = await readPlan(path.resolve(args.plan));
  const outputDir = path.resolve(args.outputDir);
  const browserType = SUPPORTED_BROWSERS[args.browser];
  const timeoutMs = clampTimeout(args.timeoutMs ?? plan.timeoutMs, 15000);

  await ensureDir(outputDir);

  const launchOptions = {
    headless: !args.headed,
  };
  const browser = await browserType.launch(launchOptions);

  try {
    const deviceConfig = args.device ? devices[args.device] : null;
    if (args.device && !deviceConfig) {
      throw new Error(`Unknown device preset: ${args.device}`);
    }

    const contextOptions = {
      ignoreHTTPSErrors: true,
      storageState: args.storageState ? path.resolve(args.storageState) : undefined,
      viewport: deviceConfig
        ? undefined
        : plan.viewport ?? {
            width: 1440,
            height: 900,
          },
      ...deviceConfig,
    };

    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();
    page.setDefaultTimeout(timeoutMs);

    const captures = [];
    for (const shot of plan.shots) {
      console.log(`Capturing ${shot.name} -> ${shot.path ?? "/"}`);
      const result = await captureShot({
        page,
        baseUrl: args.baseUrl,
        outputDir,
        shot,
        plan,
        defaultTimeoutMs: timeoutMs,
      });
      captures.push(result);
    }

    if (args.saveStorageState) {
      await context.storageState({path: path.resolve(args.saveStorageState)});
    }

    const manifestPath = path.join(outputDir, "capture-manifest.json");
    await fs.writeFile(
      manifestPath,
      JSON.stringify(
        {
          baseUrl: args.baseUrl,
          browser: args.browser,
          device: args.device ?? null,
          captures,
        },
        null,
        2,
      ),
      "utf8",
    );

    console.log(`Saved ${captures.length} screenshot(s) to ${outputDir}`);
    console.log(`Manifest: ${manifestPath}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
