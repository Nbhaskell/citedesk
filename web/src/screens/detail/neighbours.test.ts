import { describe, expect, it } from "vitest";
import { neighbours, readQueueState } from "./neighbours";

describe("readQueueState", () => {
  it("reads the ids the queue passed along", () => {
    expect(readQueueState({ queue: [4, 7, 9] })).toEqual([4, 7, 9]);
  });

  it.each([
    ["nothing", undefined],
    ["null", null],
    ["a string", "7"],
    ["no queue", {}],
    ["a queue that is not a list", { queue: "1,2" }],
    ["ids that are not whole positive numbers", { queue: [1, 2.5, 3] }],
    ["a zero id", { queue: [0, 1] }],
    ["a negative id", { queue: [-1, 2] }],
    ["text among the ids", { queue: [1, "2"] }],
    [
      "a list longer than any queue page set",
      { queue: Array.from({ length: 1001 }, (_, n) => n + 1) },
    ],
  ])("reads %s as no list at all", (_name, state) => {
    expect(readQueueState(state)).toEqual([]);
  });
});

describe("neighbours", () => {
  const ids = [4, 7, 9];

  it("names the one before and the one after, and where this one stands", () => {
    expect(neighbours(ids, 7)).toEqual({ previous: 4, next: 9, position: 2, total: 3 });
  });

  it("has no previous at the start and no next at the end", () => {
    expect(neighbours(ids, 4)).toEqual({ previous: null, next: 7, position: 1, total: 3 });
    expect(neighbours(ids, 9)).toEqual({ previous: 7, next: null, position: 3, total: 3 });
  });

  it("is nothing for an inquiry that is not in the list, or an empty list", () => {
    expect(neighbours(ids, 5)).toBeNull();
    expect(neighbours([], 5)).toBeNull();
  });

  it("is nothing when the list is only this inquiry: there is nowhere to go", () => {
    expect(neighbours([7], 7)).toBeNull();
  });
});
