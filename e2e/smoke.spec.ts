import { expect, test } from "@playwright/test";

const routes = [
  { path: "/", heading: "A safe, extensible coding agent for real projects." },
  { path: "/docs", heading: "LunarForge documentation" },
  {
    path: "/docs/permissions-and-approvals",
    heading: "Permissions and approvals",
  },
  { path: "/compare", heading: "The same task, three coding agents." },
  {
    path: "/design-system",
    heading: "Tokens, components, and interaction notes",
  },
  { path: "/login", heading: "Welcome back" },
  { path: "/privacy", heading: "Privacy notice" },
  { path: "/security", heading: "Security overview" },
  { path: "/terms", heading: "Terms of use" },
] as const;

for (const route of routes) {
  test(`${route.path} renders its primary content`, async ({ page }) => {
    const response = await page.goto(route.path);

    expect(response?.ok()).toBe(true);
    await expect(page.locator("#main")).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 1, name: route.heading }),
    ).toBeVisible();
  });
}

test("/sandbox renders the fake-service application shell", async ({ page }) => {
  await page.context().addCookies([
    {
      name: "lf-auth-e2e",
      value: "user",
      domain: "localhost",
      path: "/",
    },
  ]);
  const response = await page.goto("/sandbox");

  expect(response?.ok()).toBe(true);
  await expect(page.locator("#main")).toBeVisible();
  await expect(page.getByLabel("Transcript")).toBeVisible();
  await expect(page.getByText("Fake-service sandbox, ready to go")).toBeVisible();
});
