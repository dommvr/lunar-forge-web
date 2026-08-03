import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const manifest = JSON.parse(
  await readFile(path.join(ROOT, "src/generated/docs-manifest.json"), "utf8"),
);
const pages = new Map(manifest.pages.map((page) => [`/docs/${page.slug}`, page]));
const failures = [];

async function filesUnder(directory, extensions) {
  const entries = await readdir(directory, { recursive: true });
  return entries
    .filter((entry) => extensions.some((extension) => entry.endsWith(extension)))
    .map((entry) => path.join(directory, entry));
}

const files = [
  ...(await filesUnder(path.join(ROOT, "content/docs"), [".mdx"])),
  ...(await filesUnder(path.join(ROOT, "src"), [".ts", ".tsx"])),
];

for (const file of files) {
  const source = await readFile(file, "utf8");
  const links = [];
  const patterns = [
    /\]\((\/docs(?:\/[a-z0-9][a-z0-9-/]*)?(?:#[a-z0-9-]+)?)\)/g,
    /\bhref\s*(?:=|:)\s*["'](\/docs(?:\/[a-z0-9][a-z0-9-/]*)?(?:#[a-z0-9-]+)?)["']/g,
  ];
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) links.push(match[1]);
  }
  for (const href of links) {
    const [route, anchor] = href.split("#");
    if (route === "/docs") continue;
    const page = pages.get(route);
    if (!page) {
      failures.push(`${path.relative(ROOT, file)}: missing route ${route}`);
      continue;
    }
    if (anchor && !page.headings.some((heading) => heading.id === anchor)) {
      failures.push(`${path.relative(ROOT, file)}: missing anchor ${href}`);
    }
  }
}

for (const page of manifest.pages) {
  if (!page.headings.length) {
    failures.push(`content/docs/${page.slug}.mdx: page has no generated headings`);
  }
}

if (failures.length) {
  throw new Error(`Docs link check failed:\n${failures.join("\n")}`);
}

console.log(`Checked ${manifest.pages.length} docs routes and ${files.length} source files.`);
