import { useEffect, useRef, useState } from "react";

export type ScrollShadowState = { left: boolean; right: boolean };

export function useScrollShadows<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [shadows, setShadows] = useState<ScrollShadowState>({
    left: false,
    right: false,
  });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      const { scrollLeft, scrollWidth, clientWidth } = el;
      setShadows({
        left: scrollLeft > 0,
        right: scrollLeft + clientWidth < scrollWidth - 1,
      });
    };

    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    for (const child of Array.from(el.children)) ro.observe(child);

    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, []);

  return { ref, shadows };
}
