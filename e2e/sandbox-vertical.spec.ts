import { expect, test } from "@playwright/test";

test("deterministic full sandbox lifecycle", async ({ page }) => {
  await page.context().addCookies([
    {
      name: "lf-auth-e2e",
      value: "user",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.goto("/sandbox");

  await expect(page.getByRole("status")).toContainText("Ready");
  await expect(page.getByText("Interactive sandbox, ready to go")).toBeVisible();
  await page
    .getByRole("button", { name: /Add a responsive pricing section/ })
    .click();

  await expect(page.getByRole("status")).toContainText("Waiting for approval");
  await expect(page.getByText("assistant.message.delta")).toBeVisible();
  const approval = page.getByLabel("Approval required");
  await expect(approval.getByText("npm run validate", { exact: false })).toBeVisible();
  await expect
    .poll(() =>
      approval.locator("[class*='approvalDetails']").evaluate(
        (element) => getComputedStyle(element).overflowY,
      ),
    )
    .toBe("auto");
  const deny = page.getByRole("button", { name: "Deny" }).first();
  await expect(deny).toBeFocused();
  await page.getByRole("button", { name: "Approve" }).first().click();

  await expect(page.getByRole("status")).toContainText("Task completed");
  await expect(page.getByText("Edited 3 files. Validation passed")).toBeVisible();
  await expect(page.getByText("3 changed")).toBeVisible();

  await page.getByRole("button", { name: "Pricing.tsx" }).click();
  await expect(page.getByText("export function Pricing", { exact: false })).toBeVisible();

  await page.getByRole("tab", { name: "Validation" }).first().click();
  await expect(page.getByText("Validation passed.").first()).toBeVisible();
  await page.getByRole("tab", { name: "Usage" }).first().click();
  await expect(page.getByText("1,240")).toBeVisible();

  await page.getByRole("tab", { name: "Artifacts" }).first().click();
  await expect(page.getByText("validation-report.json")).toBeVisible();
  const artifactDownload = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download validation-report.json" })
    .click();
  await expect((await artifactDownload).suggestedFilename()).toBe(
    "validation-report.json",
  );

  const projectDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download project" }).click();
  await expect((await projectDownload).suggestedFilename()).toMatch(/\.zip$/);

  const input = page.getByLabel("Message LunarForge");
  await input.fill("Make another bounded change");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("status")).toContainText("Waiting for approval");
  await page.getByRole("button", { name: "Stop task" }).click();
  await expect(page.getByRole("status")).toContainText("Task stopped");
  await expect(page.getByText("Rollback confirmed:", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Compact context" }).click();
  await expect(
    page.getByText("Older context compacted into a safe public summary."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Reset sandbox" }).click();
  await expect(page.getByRole("status")).toContainText("Ready");
  await expect(page.getByText("Interactive sandbox, ready to go")).toBeVisible();

  await page.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByRole("status")).toContainText("No sandbox");
});
