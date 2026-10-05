import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import messages from "../messages/en.json";
import { PlatformPreview } from "@/components/preview/platform-preview";
import type { PreviewAd } from "@/components/preview/types";

const ad: PreviewAd = {
  pageName: "Mya's Kitchen",
  caption: "x".repeat(200),
  headline: "Lunch set",
  cta: "order_now",
  postType: "paid",
  media: null,
};

function wrap(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  );
}

describe("PlatformPreview", () => {
  it("labels previews as X-style without logos and truncates at See more", () => {
    wrap(<PlatformPreview platform="facebook" placement="feed" ad={ad} />);
    expect(screen.getByText(/Preview \(Facebook-style/)).toBeInTheDocument();
    expect(screen.getAllByText("See more").length).toBeGreaterThan(0);
    expect(screen.getByText("Sponsored")).toBeInTheDocument();
  });
  it("renders a TikTok-style in-feed preview with the beta badge", () => {
    wrap(
      <PlatformPreview
        platform="tiktok"
        placement="in_feed"
        ad={ad}
        platformInfo={{
          code: "tiktok",
          name: "TikTok",
          status: "beta",
          version: 1,
          placements: [],
          ad_specs: {},
          post_types: [],
          supported_goals: {},
          actions: [],
          organic: {},
        }}
      />,
    );
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });
});
