import { readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

import matter from "gray-matter";
import GithubSlugger from "github-slugger";

const ROOT = process.cwd();
const CONTENT_ROOT = path.join(ROOT, "content", "docs");
const OUTPUT = path.join(ROOT, "src", "generated", "docs-manifest.json");
const REQUIRED = [
  "title",
  "description",
  "section",
  "sectionOrder",
  "order",
  "status",
  "version",
  "verified",
];

function plainText(value) {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[`*~{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function extractHeadings(source) {
  const slugger = new GithubSlugger();
  const headings = [];
  let fenced = false;

  for (const line of source.split(/\r?\n/)) {
    if (/^\s*```/.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) continue;
    const match = /^(##|###)\s+(.+?)\s*#*\s*$/.exec(line);
    if (!match) continue;
    const title = plainText(match[2]);
    headings.push({
      id: slugger.slug(title),
      title,
      level: match[1].length === 2 ? 0 : 1,
    });
  }
  return headings;
}

function searchText(source) {
  return plainText(
    source
      .replace(/^---[\s\S]*?---/m, " ")
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/^#{1,6}\s+/gm, " ")
      .replace(/<Callout[^>]*>|<\/Callout>/g, " "),
  ).slice(0, 12_000);
}

function assertMetadata(file, data) {
  for (const key of REQUIRED) {
    if (data[key] === undefined || data[key] === "") {
      throw new Error(`${file}: missing frontmatter field ${key}`);
    }
  }
  if (!Number.isInteger(data.sectionOrder) || !Number.isInteger(data.order)) {
    throw new Error(`${file}: sectionOrder and order must be integers`);
  }
  if (data.keywords !== undefined && !Array.isArray(data.keywords)) {
    throw new Error(`${file}: keywords must be an array`);
  }
}

export async function buildManifest(contentRoot = CONTENT_ROOT) {
  const files = (await readdir(contentRoot, { recursive: true }))
    .filter((file) => file.endsWith(".mdx") && !file.startsWith("_generated"))
    .sort();
  const pages = [];
  const seenSlugs = new Set();
  const seenPositions = new Set();

  for (const file of files) {
    const absolute = path.join(contentRoot, file);
    const raw = await readFile(absolute, "utf8");
    const { data, content } = matter(raw);
    assertMetadata(file, data);
    const slug = file.replace(/\\/g, "/").replace(/\.mdx$/, "");
    const position = `${data.sectionOrder}:${data.order}`;
    if (seenSlugs.has(slug)) throw new Error(`Duplicate docs slug: ${slug}`);
    if (seenPositions.has(position)) {
      throw new Error(`Duplicate docs navigation position: ${position}`);
    }
    seenSlugs.add(slug);
    seenPositions.add(position);
    pages.push({
      slug,
      title: String(data.title),
      description: String(data.description),
      section: String(data.section),
      sectionOrder: data.sectionOrder,
      order: data.order,
      status: String(data.status),
      version: String(data.version),
      verified: String(data.verified),
      featured: data.featured === true,
      keywords: (data.keywords ?? []).map(String),
      headings: extractHeadings(content),
      searchText: searchText(content),
    });
  }

  pages.sort(
    (left, right) =>
      left.sectionOrder - right.sectionOrder || left.order - right.order,
  );
  return { schemaVersion: 1, pages };
}

const manifest = await buildManifest();
const rendered = `${JSON.stringify(manifest, null, 2)}\n`;
if (process.argv.includes("--check")) {
  const existing = await readFile(OUTPUT, "utf8").catch(() => "");
  if (existing !== rendered) {
    throw new Error("Docs manifest is stale. Run npm run docs:generate.");
  }
} else {
  await writeFile(OUTPUT, rendered, "utf8");
}
