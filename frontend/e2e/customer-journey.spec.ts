import { expect, test } from "@playwright/test";
import { createProfileUI, loginUI, registerVerifiedUser, SAMPLE_IMAGE, tomorrow } from "./helpers";

test.describe("customer journey: profile → wizard → confirm → free trial → live → report", () => {
  test("runs a first test for free and opens the report", async ({ page, request }) => {
    const user = await registerVerifiedUser(request, { country: "TH" });
    await loginUI(page, user.email, user.password);
    await expect(page.getByRole("heading", { name: /Hello/ })).toBeVisible();
    await expect(page.getByText("Your first test is free")).toBeVisible();

    await createProfileUI(page);

    // wizard step 0: preset preselected (default)
    await page.goto("/en/tests/new");
    await expect(page.getByRole("button", { name: /Edit for this ad/ })).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();

    // step 1: ad
    await page.getByLabel(/Test title/).fill("E2E lunch set");
    await page.getByLabel(/Primary text/).fill("Lunch set 199 THB today only. Come hungry! ".repeat(4));
    await page.getByLabel("Headline").fill("Lunch set 199");
    await page.locator('input[type="file"]').setInputFiles(SAMPLE_IMAGE);
    await expect(page.getByText("Ready to upload")).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();

    // step 2: audience → creates the server draft and uploads media
    await page.getByRole("combobox", { name: /Country/ }).click();
    await page.getByRole("option", { name: /Thailand/ }).click();
    await page.getByLabel("Locations").fill("Bangkok, Sukhumvit");
    await page.getByRole("button", { name: "Next" }).click();
    await page.waitForURL(/tests\/new\?id=.*step=3/);

    // step 3: platforms & schedule
    await page.getByRole("button", { name: /^Facebook/ }).click();
    await page.getByLabel("Start date").fill(tomorrow());
    await page.getByLabel(/Total budget/).fill("3000");
    await page.getByRole("button", { name: "Next" }).click();
    await page.waitForURL(/step=4/);
    await expect(page.getByText(/Preview \(Facebook-style/)).toBeVisible();
    await page.getByRole("button", { name: "Looks good" }).click();

    // confirm
    await page.waitForURL(/\/confirm$/);
    await expect(page.getByRole("heading", { name: "Confirm your test" })).toBeVisible();
    await page.getByLabel("I have checked my inputs").check();
    await page.getByRole("button", { name: "Continue to checkout" }).click();

    // checkout with trial
    await page.waitForURL(/\/checkout$/);
    await expect(page.getByText("Your first test is free")).toBeVisible();
    await page.getByRole("button", { name: "Run free test" }).click();

    // live → report
    await page.waitForURL(/\/live$/);
    await expect(
      page
        .getByText(/Analysing ad|Building audience|Customers reacting|Running simulations|Writing reasons/)
        .first(),
    ).toBeVisible();
    await page.waitForURL(/\/report$/, { timeout: 170_000 });
    await expect(page.getByText("Funnel with reasons")).toBeVisible();
    await expect(page.getByText(/Method note/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Why\?/ }).first()).toBeVisible();
    // no advice words in report reasons
    const body = await page.locator("main").innerText();
    expect(body).not.toMatch(/\byou should\b/i);

    // dashboard shows the completed test with a score
    await page.goto("/en/dashboard");
    await expect(page.getByText("E2E lunch set")).toBeVisible();
    await expect(page.getByText("Completed").first()).toBeVisible();
  });
});
