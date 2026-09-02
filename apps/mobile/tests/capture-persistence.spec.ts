import { expect, test } from "@playwright/test";

test("capacity picker is available without a new capture", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("See what fits without capturing").click();

  await expect(page.getByText("How much room do you have?")).toBeVisible();
  await expect(page.getByText("Show me what fits")).toBeVisible();
});

test("capture survives unavailable backend and app restart", async ({ page }) => {
  await page.route("**/v1/captures", (route) => route.abort());
  await page.goto("/");
  await page.getByPlaceholder("Put it here as it comes to you").fill("Keep the smoke test evidence");
  await page.getByLabel("Save text thought").click();

  await expect(page.getByText("Kept.")).toBeVisible();
  await expect(page.getByText("Saved on this device")).toBeVisible();

  await page.reload();
  await page.getByLabel("Diagnostics").click();
  await expect(page.getByText("text capture")).toBeVisible();
  await expect(page.getByText(/failed.*attempt 1/)).toBeVisible();
});

test("architecture inspector is complete and responsive", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Diagnostics").click();

  await expect(page.getByText("Architecture inspector")).toBeVisible();
  for (const section of [
    "Latest end-to-end process",
    "Local persistence",
    "Durable orchestration",
    "Agent runs",
    "Latest deterministic ranking",
    "Feedback events",
    "Learned calibration",
  ]) {
    await expect(page.getByText(section, { exact: true })).toBeVisible();
  }
  await expect(
    page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
  ).resolves.toBe(true);

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(
    page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
  ).resolves.toBe(true);
});
