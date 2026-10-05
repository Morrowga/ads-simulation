import { expect, type APIRequestContext, type Page } from "@playwright/test";
import path from "node:path";

export const API_URL = process.env.API_URL ?? "http://localhost:8000/api/v1";
export const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://localhost:8025";
export const ADMIN_EMAIL = process.env.SEED_ADMIN_EMAIL ?? "admin@advar.local";
export const ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD ?? "admin12345";
export const SAMPLE_IMAGE =
  process.env.SAMPLE_IMAGE ?? path.resolve(__dirname, "../../backend/samples/sample_ad.jpg");

export function uniqueEmail(prefix: string): string {
  return `${prefix}.${Date.now()}.${Math.floor(Math.random() * 1e6)}@example.test`;
}

/** Pull the newest verification / reset link for an address from Mailpit's API. */
export async function latestLink(request: APIRequestContext, to: string, pathPart: string): Promise<string> {
  for (let i = 0; i < 30; i++) {
    const res = await request.get(
      `${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(`to:${to}`)}&limit=5`,
    );
    if (res.ok()) {
      const data = (await res.json()) as { messages: { ID: string }[] };
      for (const m of data.messages ?? []) {
        const msg = (await (await request.get(`${MAILPIT_URL}/api/v1/message/${m.ID}`)).json()) as {
          Text: string;
        };
        const match = msg.Text.match(new RegExp(`https?://[^\\s"']*${pathPart}[^\\s"']*`));
        if (match) return match[0];
      }
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`no e-mail with ${pathPart} for ${to}`);
}

/** Register through the API and verify via the e-mail link, so UI tests can start logged in. */
export async function registerVerifiedUser(
  request: APIRequestContext,
  opts: { country?: string; name?: string } = {},
): Promise<{ email: string; password: string }> {
  const email = uniqueEmail("e2e");
  const password = "Passw0rd!e2e";
  const res = await request.post(`${API_URL}/auth/register`, {
    data: { email, password, name: opts.name ?? "E2E User", country: opts.country ?? "TH", locale: "en" },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const link = await latestLink(request, email, "verify-email");
  const token = new URL(link).searchParams.get("token");
  const v = await request.post(`${API_URL}/auth/verify-email`, { data: { token } });
  expect(v.ok(), await v.text()).toBeTruthy();
  return { email, password };
}

export async function loginUI(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/en/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(/\/(dashboard|admin)/);
}

export async function createProfileUI(page: Page, name = "Dine-in main"): Promise<void> {
  await page.goto("/en/profiles/new");
  await page.locator("#name").fill(name);
  await page.locator("#category").click();
  await page
    .getByRole("option", { name: /Restaurant/i })
    .first()
    .click();
  await expect(page.getByText("Business basics")).toBeVisible();
  // answer every template question generically: text/number inputs, selects, multiselect groups
  for (const el of await page.locator('[id^="q-"]').all()) {
    const tag = await el.evaluate((n) => n.tagName.toLowerCase());
    const role = await el.getAttribute("role");
    const type = await el.getAttribute("type");
    if (tag === "input" && type === "number") {
      if ((await el.inputValue()) === "")
        await el.fill(String(Math.max(1, Number((await el.getAttribute("min")) ?? 1))));
    } else if (tag === "input") {
      if ((await el.inputValue()) === "") await el.fill("Burmese home cooking, noodles and curries");
    } else if (tag === "button" && role === "combobox") {
      if (((await el.textContent()) ?? "").includes("Choose")) {
        await el.click();
        await page.getByRole("option").first().click();
      }
    } else if (tag === "div" && role === "group") {
      const first = el.getByRole("checkbox").first();
      if ((await first.count()) > 0 && (await first.getAttribute("data-state")) !== "checked")
        await first.click();
    }
  }
  await page.getByRole("button", { name: "Create profile" }).click();
  await page.waitForURL(/\/profiles\/[0-9a-f-]+$/);
}

export function tomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}
