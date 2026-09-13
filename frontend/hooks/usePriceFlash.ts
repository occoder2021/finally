"use client";

import { useEffect, useRef, useState } from "react";

export type FlashDirection = "up" | "down" | null;

/** Brief green/red background flash on price change, fading over ~550ms
 * (PLAN.md §2 / §10). Compares against the previously seen value itself
 * rather than trusting the server's `direction` field, so it fires exactly
 * once per actual change regardless of how the caller re-renders. */
export function usePriceFlash(price: number | null | undefined): FlashDirection {
  const [flash, setFlash] = useState<FlashDirection>(null);
  const prevRef = useRef<number | null | undefined>(price);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = price;

    if (prev == null || price == null || price === prev) return;

    setFlash(price > prev ? "up" : "down");
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setFlash(null), 550);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [price]);

  return flash;
}
