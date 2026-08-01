import { DocsSidebar } from "@/components/docs/DocsSidebar";
import { SiteNav } from "@/components/SiteNav";

import styles from "./docs.module.css";

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <SiteNav variant="docs" />
      <div className={styles.shell}>
        <DocsSidebar />
        <main id="main">{children}</main>
      </div>
    </>
  );
}
