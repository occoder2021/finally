import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePriceFlash } from "@/hooks/usePriceFlash";

describe("usePriceFlash", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts with no flash", () => {
    const { result } = renderHook(() => usePriceFlash(100));
    expect(result.current).toBeNull();
  });

  it("flashes up when the price increases, then fades after ~550ms", () => {
    const { result, rerender } = renderHook(({ price }) => usePriceFlash(price), {
      initialProps: { price: 100 },
    });
    expect(result.current).toBeNull();

    rerender({ price: 101 });
    expect(result.current).toBe("up");

    act(() => {
      vi.advanceTimersByTime(550);
    });
    expect(result.current).toBeNull();
  });

  it("flashes down when the price decreases", () => {
    const { result, rerender } = renderHook(({ price }) => usePriceFlash(price), {
      initialProps: { price: 100 },
    });
    rerender({ price: 95 });
    expect(result.current).toBe("down");
  });

  it("does not flash when the price is unchanged", () => {
    const { result, rerender } = renderHook(({ price }) => usePriceFlash(price), {
      initialProps: { price: 100 },
    });
    rerender({ price: 100 });
    expect(result.current).toBeNull();
  });

  it("does not flash when the price is unavailable", () => {
    const { result, rerender } = renderHook(({ price }: { price: number | null }) => usePriceFlash(price), {
      initialProps: { price: null },
    });
    rerender({ price: null });
    expect(result.current).toBeNull();
  });
});
