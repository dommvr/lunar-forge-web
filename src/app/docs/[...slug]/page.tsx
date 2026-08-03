import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { compileMDX } from "next-mdx-remote/rsc";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

import { DocsBar } from "@/components/docs/DocsBar";
import { DocsToc } from "@/components/docs/DocsToc";
import { docsMdxComponents } from "@/components/docs/MdxContent";
import { docsPages, getAdjacentDocs, getDocPage } from "@/lib/docs";
import { loadDocSource } from "@/lib/docs-content";

import styles from "../docs.module.css";

type PageProps = { params: Promise<{ slug: string[] }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return docsPages.map((page) => ({ slug: page.slug.split("/") }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const page = getDocPage(slug.join("/"));
  if (!page) return {};
  return { title: page.title, description: page.description };
}

export default async function DocPage({ params }: PageProps) {
  const { slug: segments } = await params;
  const slug = segments.join("/");
  const document = await loadDocSource(slug);
  if (!document) notFound();

  const { content } = await compileMDX({
    source: document.source,
    components: docsMdxComponents,
    options: {
      mdxOptions: {
        remarkPlugins: [remarkGfm],
        rehypePlugins: [rehypeSlug],
      },
    },
  });
  const { metadata } = document;
  const adjacent = getAdjacentDocs(slug);

  return (
    <>
      <DocsBar section={metadata.section} page={metadata.title} toc={metadata.headings} />
      <div className={styles.articleGrid}>
        <article className={styles.article}>
          <nav className={styles.breadcrumb} aria-label="Breadcrumb">
            <span>{metadata.section}</span>
            <span className={styles.breadcrumbSep}>/</span>
            <span className={styles.breadcrumbCurrent}>{metadata.title}</span>
          </nav>

          <h1 className={styles.articleTitle}>{metadata.title}</h1>
          <p className={styles.articleLede}>{metadata.description}</p>
          <div className={styles.meta}>
            <span>Verified {metadata.verified}</span>
            <span className={styles.metaSep}>·</span>
            <span>{metadata.version}</span>
            <span className={styles.metaSep}>·</span>
            <span>{metadata.status}</span>
          </div>

          <div className={`${styles.body} ${styles.mdx}`}>{content}</div>

          <nav className={styles.pager} aria-label="Documentation pagination">
            {adjacent.previous ? (
              <Link href={`/docs/${adjacent.previous.slug}`} className={styles.pagerCard}>
                <div className={styles.pagerLabel}>Previous</div>
                <div className={styles.pagerTitle}>← {adjacent.previous.title}</div>
              </Link>
            ) : (
              <span />
            )}
            {adjacent.next ? (
              <Link
                href={`/docs/${adjacent.next.slug}`}
                className={`${styles.pagerCard} ${styles.pagerNext}`}
              >
                <div className={styles.pagerLabel}>Next</div>
                <div className={styles.pagerTitle}>{adjacent.next.title} →</div>
              </Link>
            ) : null}
          </nav>
        </article>
        <DocsToc entries={metadata.headings} slug={slug} />
      </div>
    </>
  );
}
