"use client";

import { ConvexProvider, ConvexReactClient } from "convex/react";
import { useMemo } from "react";

export function ConvexClientProvider({
  children,
  url,
}: {
  children: React.ReactNode;
  url?: string;
}) {
  const convex = useMemo(() => {
    if (!url) {
      return null;
    }
    return new ConvexReactClient(url);
  }, [url]);

  if (!convex) {
    return children;
  }

  return <ConvexProvider client={convex}>{children}</ConvexProvider>;
}
