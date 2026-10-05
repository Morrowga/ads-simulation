import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import messages from "../messages/en.json";
import { ScoreBadge } from "@/components/layout/score-badge";
import { StatusBadge } from "@/components/layout/status-badge";

function wrap(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  );
}

describe("ScoreBadge", () => {
  it("always shows the number and a text label", () => {
    wrap(<ScoreBadge score={72} />);
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
  });
  it("labels the amber and red bands", () => {
    wrap(<ScoreBadge score={55} />);
    expect(screen.getByText("Medium")).toBeInTheDocument();
    wrap(<ScoreBadge score={12} />);
    expect(screen.getByText("Low")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders the running status with the accent dot", () => {
    wrap(<StatusBadge status="running" />);
    expect(screen.getByText("Running")).toBeInTheDocument();
  });
});
