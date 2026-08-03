import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";

import matter from "gray-matter";

import { getDocPage } from "@/lib/docs";

const CONTENT_ROOT = path.join(process.cwd(), "content", "docs");

export async function loadDocSource(slug: string) {
  const metadata = getDocPage(slug);
  if (!metadata) return undefined;

  const absolute = path.resolve(CONTENT_ROOT, `${slug}.mdx`);
  const relative = path.relative(CONTENT_ROOT, absolute);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Docs path escaped the content root: ${slug}`);
  }

  const raw = await readFile(absolute, "utf8");
  const parsed = matter(raw);
  if (parsed.data.title !== metadata.title) {
    throw new Error(`Docs manifest is stale for ${slug}`);
  }
  return { metadata, source: parsed.content };
}
