import { describe, expect, it } from "vitest";

import { docsNav, docsPages, searchIndex } from "./docs";

describe("generated docs metadata", () => {
  it("keeps navigation and search routes backed by content", () => {
    const routes = new Set(docsPages.map((page) => `/docs/${page.slug}`));

    for (const group of docsNav) {
      for (const item of group.items) expect(routes).toContain(item.href);
    }
    for (const result of searchIndex) {
      expect(routes).toContain(result.href.split("#")[0]);
    }
  });

  it("generates stable, unique heading ids for every page", () => {
    for (const page of docsPages) {
      expect(page.headings.length, page.slug).toBeGreaterThan(0);
      expect(new Set(page.headings.map((heading) => heading.id)).size).toBe(
        page.headings.length,
      );
    }

    expect(
      docsPages.find((page) => page.slug === "permissions-and-approvals")
        ?.headings,
    ).toEqual(
      expect.arrayContaining([
        { id: "how-the-gate-works", title: "How the gate works", level: 0 },
        { id: "event-payload", title: "Event payload", level: 1 },
      ]),
    );
  });
});
