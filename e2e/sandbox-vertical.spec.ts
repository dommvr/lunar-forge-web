import { expect, test } from "@playwright/test";

test("fake FastAPI vertical slice streams approval, files, and artifacts", async ({
  page,
}) => {
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
  await page
    .getByRole("button", { name: /Add a responsive pricing section/ })
    .click();

  await expect(page.getByRole("status")).toContainText("Waiting for approval");
  const deny = page.getByRole("button", { name: "Deny" }).first();
  await expect(deny).toBeFocused();
  await page.getByRole("button", { name: "Approve" }).first().click();

  await expect(page.getByRole("status")).toContainText("Task completed");
  await expect(page.getByText("3 changed")).toBeVisible();
  await page.getByRole("tab", { name: "Artifacts" }).first().click();
  await expect(page.getByText("validation-report.json · 4.1 KB")).toBeVisible();

  await page.getByRole("button", { name: "Reset sandbox" }).click();
  await expect(page.getByRole("status")).toContainText("Ready");
  await expect(page.getByText("Fake-service sandbox, ready to go")).toBeVisible();
});
