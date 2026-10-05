import { expect, test } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginUI } from "./helpers";

test.describe("admin panel", () => {
  test("overview, queue and settings editors load", async ({ page }) => {
    await loginUI(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto("/en/admin");
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await expect(page.getByText("Revenue", { exact: true })).toBeVisible();
    await page.goto("/en/admin/payments");
    await expect(page.getByRole("heading", { name: "Manual orders" })).toBeVisible();
    await page.goto("/en/admin/countries");
    await expect(page.getByText("Myanmar", { exact: true })).toBeVisible();
    await expect(page.getByText("Version history").first()).toBeVisible();
    await page.goto("/en/admin/categories");
    await expect(page.getByRole("button", { name: "Draft with AI" })).toBeVisible();
    await page.getByRole("button", { name: "Preview profile form" }).click();
    await expect(page.getByText("Business basics")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.goto("/en/admin/platforms");
    await expect(page.getByText("Version history").first()).toBeVisible();
    await page.goto("/en/admin/scenarios");
    await expect(page.getByRole("heading", { name: "Scenarios" })).toBeVisible();
    await page.goto("/en/admin/weights");
    await expect(page.getByText("Behaviour weights", { exact: true })).toBeVisible();
    await page.goto("/en/admin/fx-rates");
    await expect(page.getByRole("heading", { name: "Exchange rates" })).toBeVisible();
    await page.goto("/en/admin/prices");
    await expect(page.getByRole("heading", { name: "Prices" })).toBeVisible();
    await page.goto("/en/admin/settings");
    await expect(page.getByText("Manual payment (Myanmar)")).toBeVisible();
    await page.goto("/en/admin/users");
    await expect(page.getByText(ADMIN_EMAIL).first()).toBeVisible();
  });

  test("non-admin users are redirected away from /admin", async ({ page }) => {
    await page.goto("/en/admin");
    await page.waitForURL(/\/login/);
  });
});
