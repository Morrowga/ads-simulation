import { expect, test } from "@playwright/test";

test("landing and pricing work at phone width", async ({ page }) => {
  await page.goto("/en");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
  await page.goto("/en/pricing");
  await expect(page.getByText("Recommended")).toBeVisible();
  await page.goto("/en/login");
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
});
