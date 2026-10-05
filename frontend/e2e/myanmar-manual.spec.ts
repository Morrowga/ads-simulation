import { expect, test } from "@playwright/test";
import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  API_URL,
  loginUI,
  registerVerifiedUser,
  SAMPLE_IMAGE,
  tomorrow,
} from "./helpers";

test.describe("Myanmar manual payment → admin approval", () => {
  test("customer pays by transfer, admin approves, test runs", async ({ page, browser, request }) => {
    const user = await registerVerifiedUser(request, { country: "MM" });
    // use the trial first so the second test needs a real payment
    const login = await request.post(`${API_URL}/auth/login`, {
      data: { email: user.email, password: user.password },
    });
    const { access_token } = (await login.json()) as { access_token: string };
    const auth = { Authorization: `Bearer ${access_token}` };
    const cats = (await (await request.get(`${API_URL}/categories`, { headers: auth })).json()) as {
      code: string;
    }[];
    const tmpl = (await (
      await request.get(`${API_URL}/categories/${cats[0].code}`, { headers: auth })
    ).json()) as {
      questions: {
        key: string;
        type: string;
        required: boolean;
        default: unknown;
        options?: unknown[];
        min?: number;
      }[];
    };
    const data: Record<string, unknown> = {};
    for (const q of tmpl.questions) {
      if (!q.required || q.default !== null) continue;
      if (q.type === "text") data[q.key] = "Mya's Kitchen";
      else if (q.type === "number") data[q.key] = q.min ?? 1;
      else if (q.type === "select") data[q.key] = q.options?.[0];
      else if (q.type === "multiselect") data[q.key] = [q.options?.[0]];
      else if (q.type === "boolean") data[q.key] = true;
      else if (q.type === "sliders")
        data[q.key] = Object.fromEntries((q.options ?? []).map((o) => [String(o), 0.5]));
    }
    const prof = (await (
      await request.post(`${API_URL}/profiles`, {
        headers: auth,
        data: { name: "MM preset", category_code: cats[0].code, data, is_default: true },
      })
    ).json()) as { id: string };
    expect(prof.id).toBeTruthy();

    await loginUI(page, user.email, user.password);
    await page.goto("/en/tests/new");
    await expect(page.getByRole("button", { name: /Edit for this ad/ })).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel(/Test title/).fill("MM manual test");
    await page.getByLabel(/Primary text/).fill("Mohinga breakfast set, order now on Messenger.");
    await page.locator('input[type="file"]').setInputFiles(SAMPLE_IMAGE);
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("combobox", { name: /Country/ }).click();
    await page.getByRole("option", { name: /Myanmar/ }).click();
    await page.getByLabel("Locations").fill("Yangon");
    await page.getByRole("button", { name: "Next" }).click();
    await page.waitForURL(/step=3/);
    await page.getByRole("button", { name: /^Facebook/ }).click();
    await page.getByRole("button", { name: /^Messages/ }).click();
    await page.getByLabel("Start date").fill(tomorrow());
    await page.getByLabel(/Total budget/).fill("50000");
    await page.getByRole("button", { name: "Next" }).click();
    await page.waitForURL(/step=4/);
    await page.getByRole("button", { name: "Looks good" }).click();
    await page.waitForURL(/\/confirm$/);
    await page.getByLabel("I have checked my inputs").check();
    await page.getByRole("button", { name: "Continue to checkout" }).click();
    await page.waitForURL(/\/checkout$/);

    // The trial banner hides the paid methods while the trial is available. Either the trial runs
    // (then a duplicate test needs a real payment) or the backend refuses it (limits/review) and the
    // checkout falls back to the paid methods; both paths end at the manual tab.
    const trialButton = page.getByRole("button", { name: "Run free test" });
    await expect(trialButton.or(page.getByRole("tab", { name: /Local bank transfer/ }))).toBeVisible();
    if (await trialButton.isVisible()) {
      await trialButton.click();
      const outcome = await Promise.race([
        page.waitForURL(/\/live$/).then(() => "live" as const),
        page
          .getByRole("tab", { name: /Local bank transfer/ })
          .waitFor()
          .then(() => "manual" as const),
      ]);
      if (outcome === "live") {
        await page.waitForURL(/\/report$/, { timeout: 170_000 });
        await page.getByRole("button", { name: "Duplicate and edit" }).click();
        await page.waitForURL(/tests\/new\?id=.*step=1/);
        await page
          .getByLabel(/Primary text/)
          .fill("Mohinga breakfast set, order now on Messenger. New price!");
        await page.getByRole("button", { name: "Next" }).click();
        await page.getByRole("button", { name: "Next" }).click();
        await page.waitForURL(/step=3/);
        await page.getByRole("button", { name: "Next" }).click();
        await page.waitForURL(/step=4/);
        await page.getByRole("button", { name: "Looks good" }).click();
        await page.waitForURL(/\/confirm$/);
        await page.getByLabel("I have checked my inputs").check();
        await page.getByRole("button", { name: "Continue to checkout" }).click();
        await page.waitForURL(/\/checkout$/);
      }
    }
    const testId = page.url().split("/tests/")[1].split("/")[0];
    await expect(page.getByRole("tab", { name: /Local bank transfer/ })).toBeVisible();
    await expect(page.getByRole("tab", { name: /^Card/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Pay manually" }).click();
    await expect(page.getByText("Waiting for payment confirmation")).toBeVisible();
    const code = (await page.locator("p.font-mono.text-2xl").first().textContent())?.trim() ?? "";
    expect(code.length).toBeGreaterThan(3);
    await expect(page.getByText("Our accounts")).toBeVisible();
    await expect(page.getByText(/MMK|K\s?[0-9]/).first()).toBeVisible();

    // admin approves in another session
    const adminCtx = await browser.newContext();
    const admin = await adminCtx.newPage();
    await loginUI(admin, ADMIN_EMAIL, ADMIN_PASSWORD);
    await admin.goto("/en/admin/payments");
    await admin.getByLabel("Payment code").fill(code);
    await admin.getByRole("button", { name: "Search" }).click();
    const row = admin.getByRole("row").filter({ hasText: code });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Approve" }).click();
    await admin.getByLabel(/Transaction reference/).fill("KBZ-123456");
    await admin.getByRole("button", { name: "Approve", exact: true }).last().click();
    await expect(admin.getByText(/Order approved/)).toBeVisible();
    await adminCtx.close();

    // customer: the checkout page polls the test and moves to live; the report follows
    await page.goto(`/en/tests/${testId}/live`);
    await page.waitForURL(/\/report$/, { timeout: 170_000 });
    await expect(page.getByText("Funnel with reasons")).toBeVisible();
  });
});
