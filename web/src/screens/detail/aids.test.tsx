import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { InquiryDetail } from "../../api/types";
import { ReadingAids } from "./aids";

type Support = NonNullable<InquiryDetail["support"]>;

const support = (over: Partial<Support> = {}): Support => ({
  greeting_name: "Cecily",
  figures: [
    {
      figure: "$149",
      sentence: "Drain cleaning for one fixture starts at $149.",
      origins: [
        {
          source_index: 0,
          file: "pricing.md",
          section: "Pricing > Drain cleaning",
          line: "Drain cleaning, one fixture (sink, tub, shower or toilet): $149 (starting price)",
        },
      ],
      from_message: false,
      mismatch: false,
    },
  ],
  sentences: [
    {
      text: "Drain cleaning for one fixture starts at $149.",
      status: "supported",
      source_index: 0,
      asks_for: [],
    },
    {
      text: "Platinum customers get priority forever.",
      status: "unsupported",
      source_index: null,
      asks_for: [],
    },
  ],
  ...over,
});

function show(s: Support, name: string | null = "Cecily Marsh", open = vi.fn()) {
  render(
    <ReadingAids
      support={s}
      senderName={name}
      senderEmail="cecily@example.com"
      onOpenSource={open}
    />,
  );
  return open;
}

describe("ReadingAids", () => {
  it("shows the greeting name beside the sender", () => {
    show(support());
    expect(screen.getByText("Cecily")).toBeTruthy();
    expect(screen.getByText("Cecily Marsh")).toBeTruthy();
    expect(screen.queryByText(/not the sender's name/)).toBeNull();
  });

  it("warns when the greeting name is not the sender's", () => {
    show(support({ greeting_name: "Marcus" }));
    expect(screen.getByText(/not the sender's name/)).toBeTruthy();
  });

  it("does not warn when the sender gave no name or the greeting has none", () => {
    show(support(), null);
    expect(screen.queryByText(/not the sender's name/)).toBeNull();
  });

  it("skips a title when comparing names", () => {
    show(support({ greeting_name: "Cecily" }), "Ms Cecily Marsh");
    expect(screen.queryByText(/not the sender's name/)).toBeNull();
  });

  it("shows the line each figure comes from and opens its passage", () => {
    const open = show(support());
    expect(screen.getByText(/Drain cleaning, one fixture/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open passage 0" }));
    expect(open).toHaveBeenCalledWith(0);
  });

  it("says when a price sits in a line about something else", () => {
    const s = support();
    s.figures[0]!.mismatch = true;
    show(s);
    expect(screen.getByText(/about something else/)).toBeTruthy();
  });

  it("says when a figure is in no document, and when it is the customer's own", () => {
    const s = support();
    s.figures = [
      { figure: "$500", sentence: "x", origins: [], from_message: false, mismatch: false },
      { figure: "$300", sentence: "y", origins: [], from_message: true, mismatch: false },
    ];
    show(s);
    expect(screen.getByText(/Not in your documents/)).toBeTruthy();
    expect(screen.getByText(/customer's own message/)).toBeTruthy();
  });

  it("lists only the sentences no source backs, and counts them", () => {
    show(support());
    expect(screen.getByText(/Platinum customers get priority forever/)).toBeTruthy();
    expect(screen.getByText("(1 of 2 sentences marked)")).toBeTruthy();
    expect(screen.queryAllByText(/Drain cleaning for one fixture starts at \$149\./)).toHaveLength(
      0,
    );
  });

  it("says plainly that no mark does not mean the reply is right", () => {
    const s = support();
    s.sentences = [s.sentences[0]!];
    show(s);
    expect(screen.getByText(/does not mean the reply is right/)).toBeTruthy();
  });

  it("shows text from the draft as text, never as markup", () => {
    const s = support();
    s.sentences = [
      {
        text: "<img src=x onerror=alert(1)> free pipes",
        status: "unsupported",
        source_index: null,
        asks_for: [],
      },
    ];
    const { container } = render(
      <ReadingAids support={s} senderName="A" senderEmail={null} onOpenSource={() => {}} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });

  it("lists a sympathy line the message does not call for, apart from the unsourced ones", () => {
    const s = support();
    s.sentences = [
      {
        text: "We're sorry to hear you did it yourself.",
        status: "tone",
        source_index: null,
        asks_for: [],
      },
    ];
    show(s);
    expect(screen.getByText("Tone to check")).toBeTruthy();
    expect(screen.getByText(/We're sorry to hear you did it yourself\./)).toBeTruthy();
    expect(screen.getByText(/0 of 1 sentences marked/)).toBeTruthy();
  });

  it("shows no tone section when no line is marked for tone", () => {
    show(support());
    expect(screen.queryByText("Tone to check")).toBeNull();
  });

  it("lists a question for something the customer already gave, naming the detail", () => {
    const s = support();
    s.sentences = [
      {
        text: "Please provide the neighbourhood or address area.",
        status: "asks_known",
        source_index: null,
        asks_for: ["area"],
      },
    ];
    show(s);
    expect(screen.getByText("Asks for something the customer already gave")).toBeTruthy();
    expect(screen.getByText(/Asks for the area:/)).toBeTruthy();
    expect(screen.getByText(/Please provide the neighbourhood/)).toBeTruthy();
  });

  it("names every detail when a sentence asks for two", () => {
    const s = support();
    s.sentences = [
      {
        text: "Confirm both.",
        status: "asks_known",
        source_index: null,
        asks_for: ["area", "property type"],
      },
    ];
    show(s);
    expect(screen.getByText(/Asks for the area and the property type:/)).toBeTruthy();
  });
});
