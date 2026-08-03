import manifest from "@/generated/docs-manifest.json";

export type TocEntry = { id: string; title: string; level: 0 | 1 };

export type DocPageMeta = {
  slug: string;
  title: string;
  description: string;
  section: string;
  sectionOrder: number;
  order: number;
  status: string;
  version: string;
  verified: string;
  featured: boolean;
  keywords: string[];
  headings: TocEntry[];
  searchText: string;
};

export type NavGroup = { title: string; items: NavItem[] };
export type NavItem = { label: string; href: string };
export type OverviewSection = {
  title: string;
  items: { title: string; description: string; href: string }[];
};

export const docsPages = manifest.pages as DocPageMeta[];

export const docsNav: NavGroup[] = docsPages.reduce<NavGroup[]>((groups, page) => {
  let group = groups.find((candidate) => candidate.title === page.section);
  if (!group) {
    group = { title: page.section, items: [] };
    groups.push(group);
  }
  group.items.push({ label: page.title, href: `/docs/${page.slug}` });
  return groups;
}, []);

export const docsOverview: OverviewSection[] = docsNav.map((group) => ({
  title: group.title,
  items: group.items.map((item) => {
    const page = docsPages.find((candidate) => candidate.title === item.label);
    if (!page) throw new Error(`Missing docs metadata for ${item.label}`);
    return {
      title: page.title,
      description: page.description,
      href: item.href,
    };
  }),
}));

export function getDocPage(slug: string) {
  return docsPages.find((page) => page.slug === slug);
}

export function getAdjacentDocs(slug: string) {
  const index = docsPages.findIndex((page) => page.slug === slug);
  return {
    previous: index > 0 ? docsPages[index - 1] : undefined,
    next: index >= 0 && index < docsPages.length - 1 ? docsPages[index + 1] : undefined,
  };
}

export type SearchKind = "page" | "event" | "api" | "go";
export type SearchResult = {
  kind: SearchKind;
  title: string;
  description: string;
  href: string;
  searchText?: string;
};

const pageResults: SearchResult[] = docsPages.map((page) => ({
  kind: "page",
  title: page.title,
  description: page.description,
  href: `/docs/${page.slug}`,
  searchText: [page.searchText, ...page.keywords].join(" "),
}));

const headingResults: SearchResult[] = docsPages.flatMap((page) => {
  const kind =
    page.slug === "event-protocol"
      ? "event"
      : page.slug === "public-python-api"
        ? "api"
        : undefined;
  if (!kind) return [];
  return page.headings.map((heading) => ({
    kind,
    title: heading.title,
    description: page.description,
    href: `/docs/${page.slug}#${heading.id}`,
    searchText: page.searchText,
  }));
});

export const searchIndex: SearchResult[] = [...pageResults, ...headingResults];

export const recentPages: SearchResult[] = docsPages
  .filter((page) => page.featured)
  .slice(0, 4)
  .map((page) => ({
    kind: "page",
    title: page.title,
    description: page.description,
    href: `/docs/${page.slug}`,
    searchText: page.searchText,
  }));

export const searchActions: SearchResult[] = [
  {
    kind: "go",
    title: "Open the sandbox",
    description: "Open the deterministic sandbox UI preview",
    href: "/sandbox",
  },
  {
    kind: "go",
    title: "Open the comparison",
    description: "One task, three coding-agent presentation fixtures",
    href: "/compare",
  },
];
