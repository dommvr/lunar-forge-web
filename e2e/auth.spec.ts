import { expect, test, type Page } from "@playwright/test";

async function useIdentity(page: Page, value: string) {
  await page.context().addCookies([
    {
      name: "lf-auth-e2e",
      value,
      domain: "localhost",
      path: "/",
    },
  ]);
}

test("anonymous visitors are sent from sandbox to password login", async ({
  page,
}) => {
  await page.goto("/sandbox");

  await expect(page).toHaveURL(/\/login\?next=%2Fsandbox$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByText("Access is invite-only.")).toBeVisible();
});

test("an invited user can render the protected sandbox", async ({ page }) => {
  await useIdentity(page, "user");
  await page.goto("/sandbox");

  await expect(page.getByLabel("Transcript")).toBeVisible();
});

test("an ordinary user cannot render the admin shell", async ({ page }) => {
  await useIdentity(page, "user");
  await page.goto("/admin");

  await expect(page).toHaveURL(/\/sandbox\?error=admin_required$/);
  await expect(page.getByLabel("Transcript")).toBeVisible();
});

test("an admin at aal1 is required to complete TOTP", async ({ page }) => {
  await useIdentity(page, "admin-aal1");
  await page.goto("/admin");

  await expect(page).toHaveURL(/\/auth\/mfa\?next=%2Fadmin$/);
  await expect(page.getByRole("heading", { name: "Verify it’s you" })).toBeVisible();
});

test("an admin at aal2 can render the protected admin shell", async ({ page }) => {
  await useIdentity(page, "admin-aal2");
  await page.goto("/admin");

  await expect(page.getByRole("heading", { name: "Administration" })).toBeVisible();
  await expect(page.getByText("MFA verified")).toBeVisible();
});

test("logout clears the session and protects the next request", async ({ page }) => {
  await useIdentity(page, "admin-aal2");
  await page.goto("/admin");
  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/sandbox");
  await expect(page).toHaveURL(/\/login\?next=%2Fsandbox$/);
});
