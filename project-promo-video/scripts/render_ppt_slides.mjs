import {existsSync, mkdirSync, readdirSync, unlinkSync, writeFileSync} from "node:fs";
import path from "node:path";
import {pathToFileURL} from "node:url";
import {chromium} from "playwright";

const args = process.argv.slice(2);

const getArg = (name, fallback = null) => {
  const index = args.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return args[index + 1] ?? fallback;
};

const hasFlag = (name) => args.includes(name);

const deckPath = getArg("--deck");
const outputDir = getArg("--output-dir");
const manifestPath = getArg("--manifest");
const width = Number(getArg("--width", "1920"));
const height = Number(getArg("--height", "1080"));
const settleMs = Number(getArg("--settle-ms", "900"));
const staticMode = !hasFlag("--keep-motion");

if (!deckPath || !outputDir) {
  console.error(
    "Usage: node render_ppt_slides.mjs --deck <index.html> --output-dir <slides-dir> [--manifest <manifest.json>]",
  );
  process.exit(1);
}

const resolvedDeck = path.resolve(deckPath);
const resolvedOutput = path.resolve(outputDir);
const resolvedManifest = manifestPath
  ? path.resolve(manifestPath)
  : path.join(resolvedOutput, "render-manifest.json");

if (!existsSync(resolvedDeck)) {
  console.error(`Deck not found: ${resolvedDeck}`);
  process.exit(1);
}

mkdirSync(resolvedOutput, {recursive: true});
for (const entry of readdirSync(resolvedOutput)) {
  if (entry.toLowerCase().endsWith(".png")) {
    unlinkSync(path.join(resolvedOutput, entry));
  }
}

const slugify = (value) => {
  const slug = String(value ?? "")
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[-\s]+/g, "-")
    .toLowerCase();
  return slug || "slide";
};

const browser = await chromium.launch({
  headless: true,
  args: ["--allow-file-access-from-files"],
});
const page = await browser.newPage({
  viewport: {width, height},
  deviceScaleFactor: 1,
});

page.on("console", (msg) => {
  if (msg.type() === "error") {
    console.error(`[browser] ${msg.text()}`);
  }
});

await page.goto(pathToFileURL(resolvedDeck).href, {waitUntil: "networkidle"});
await page.addStyleTag({
  content: `
    #nav, #hint, #overview { display: none !important; }
    body { cursor: none !important; }
  `,
});

await page.waitForSelector(".slide");

const slideMeta = await page.evaluate(() => {
  return [...document.querySelectorAll(".slide")].map((slide, index) => {
    const heading = slide.querySelector("h1,h2,blockquote,[data-title]");
    return {
      index,
      id: slide.getAttribute("data-scene-id") || slide.id || `slide-${index + 1}`,
      layoutId:
        slide.getAttribute("data-layout") ||
        slide.getAttribute("data-layout-id") ||
        slide.getAttribute("data-video-layout") ||
        "PPT",
      title:
        slide.getAttribute("data-title") ||
        (heading ? heading.textContent?.replace(/\s+/g, " ").trim() : "") ||
        `Slide ${index + 1}`,
    };
  });
});

const rendered = [];

for (const slide of slideMeta) {
  const fileName = `${String(slide.index + 1).padStart(3, "0")}-${slugify(slide.id)}.png`;
  const outputPath = path.join(resolvedOutput, fileName);

  await page.evaluate(
    ({index, staticMode}) => {
      if (staticMode && window.__setLowPowerMode) {
        window.__setLowPowerMode(true, {persist: false});
      }

      if (typeof window.go === "function") {
        window.go(index);
      } else {
        const deck = document.getElementById("deck");
        const slides = [...document.querySelectorAll(".slide")];
        const current = slides[index];
        if (deck) {
          deck.style.transition = "none";
          deck.style.transform = `translateX(${-index * 100}vw)`;
        }
        window.__currentSlideIndex = index;
        document.body.classList.toggle(
          "light-bg",
          current?.classList.contains("light") ?? false,
        );
        document.body.classList.toggle(
          "dark-bg",
          current?.classList.contains("dark") ||
            current?.classList.contains("accent") ||
            false,
        );
      }

      if (staticMode && window.__setLowPowerMode) {
        window.__setLowPowerMode(true, {persist: false});
      } else if (window.__playSlide) {
        window.__playSlide(index);
      }
    },
    {index: slide.index, staticMode},
  );

  await page.waitForTimeout(settleMs);
  await page.screenshot({path: outputPath, fullPage: false});

  rendered.push({
    ...slide,
    src: `slides/${fileName}`,
    file: outputPath,
  });
  console.log(`[${slide.index + 1}/${slideMeta.length}] ${fileName}`);
}

await browser.close();

writeFileSync(
  resolvedManifest,
  JSON.stringify(
    {
      deck: resolvedDeck,
      width,
      height,
      staticMode,
      slides: rendered,
    },
    null,
    2,
  ),
  "utf8",
);

console.log(`Manifest: ${resolvedManifest}`);
