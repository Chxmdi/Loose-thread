import { expect, test } from "@playwright/test";

test("capture survives unavailable backend and app restart", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Put it here as it comes to you").fill("Keep the smoke test evidence");
  await page.getByLabel("Save text thought").click();

  await expect(page.getByText("Kept.")).toBeVisible();
  await expect(page.getByText("Saved on this device")).toBeVisible();

  await page.reload();
  await page.getByLabel("Diagnostics").click();
  await expect(page.getByText(/text · failed · attempt 1/)).toBeVisible();
});
