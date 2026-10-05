import type { TestStatus } from "./types";

/** Where "open" should take the user for a test in a given status. */
export function testHref(id: string, status: TestStatus): string {
  switch (status) {
    case "draft":
      return `/tests/${id}`;
    case "awaiting_payment":
      // must pass the confirm step (checks + checkbox) every time before checkout
      return `/tests/${id}/confirm`;
    case "payment_review":
      return `/tests/${id}/checkout`;
    case "queued":
    case "running":
    case "failed":
      return `/tests/${id}/live`;
    case "completed":
      return `/tests/${id}/report`;
    default:
      return `/tests/${id}`;
  }
}