import { expect, test } from "@playwright/test";

test.describe("smoke", () => {
  test("login and decision monitor visible", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill("changeme");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(
      page.getByRole("heading", { name: "Decision Monitor" }),
    ).toBeVisible();
  });

  test("navigate analytics and experiments", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Analytics" }).click();
    await expect(
      page.getByRole("heading", { name: "Analytics" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Experiments" }).click();
    await expect(
      page.getByRole("heading", { name: "Experiments" }),
    ).toBeVisible();
  });

  test("validation page loads", async ({ page }) => {
    await page.goto("/validation");
    await expect(
      page.getByRole("heading", { name: "Validation Harness" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Walk-Forward" }),
    ).toBeVisible();
  });
});
