import type { ComponentProps, ReactNode } from "react";
import { isValidElement } from "react";
import Link from "next/link";
import type { MDXComponents } from "mdx/types";

import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";

import styles from "@/app/docs/docs.module.css";

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return nodeText(node.props.children);
  }
  return "";
}

function Heading2({ id, children }: ComponentProps<"h2">) {
  const label = nodeText(children);
  return (
    <h2 id={id} className={styles.h2}>
      {children}
      {id ? (
        <a className={styles.anchor} href={`#${id}`} aria-label={`Link to ${label}`}>
          #
        </a>
      ) : null}
    </h2>
  );
}

function Heading3({ id, children }: ComponentProps<"h3">) {
  const label = nodeText(children);
  return (
    <h3 id={id} className={styles.h3}>
      {children}
      {id ? (
        <a className={styles.anchor} href={`#${id}`} aria-label={`Link to ${label}`}>
          #
        </a>
      ) : null}
    </h3>
  );
}

function DocsLink({ href = "", children, ...props }: ComponentProps<"a">) {
  if (href.startsWith("/")) {
    return (
      <Link href={href} className={styles.bodyLink}>
        {children}
      </Link>
    );
  }
  return (
    <a href={href} className={styles.bodyLink} {...props}>
      {children}
    </a>
  );
}

function Preformatted({ children }: ComponentProps<"pre">) {
  const codeChild = isValidElement<{ className?: string; children?: ReactNode }>(children)
    ? children
    : undefined;
  const language = codeChild?.props.className?.replace(/^language-/, "") || "text";
  const copyText = nodeText(codeChild?.props.children ?? children).replace(/\n$/, "");
  return (
    <CodeBlock label={language} copyText={copyText}>
      {codeChild?.props.children ?? children}
    </CodeBlock>
  );
}

function Table({ children }: ComponentProps<"table">) {
  return (
    <div className={styles.table}>
      <div className={styles.tableScroll}>
        <table className={styles.markdownTable}>{children}</table>
      </div>
    </div>
  );
}

export const docsMdxComponents: MDXComponents = {
  Callout,
  CodeBlock,
  h2: Heading2,
  h3: Heading3,
  p: (props) => <p className={styles.p} {...props} />,
  a: DocsLink,
  code: (props) => <code className={styles.code} {...props} />,
  pre: Preformatted,
  ul: (props) => <ul className={styles.mdxList} {...props} />,
  ol: (props) => <ol className={styles.procedure} {...props} />,
  li: (props) => <li className={styles.mdxListItem} {...props} />,
  blockquote: (props) => <blockquote className={styles.blockquote} {...props} />,
  table: Table,
  thead: (props) => <thead className={styles.markdownTableHead} {...props} />,
  th: (props) => <th className={styles.markdownTableCell} {...props} />,
  td: (props) => <td className={styles.markdownTableCell} {...props} />,
  hr: () => <hr className={styles.mdxRule} />,
};
