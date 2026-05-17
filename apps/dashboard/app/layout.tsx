import type { Metadata } from "next";
import "./styles.css";
import { ConvexClientProvider } from "../components/convex-client-provider";

export const metadata: Metadata = {
  title: "Mia",
  description: "Personal iMessage AI agent — web and desktop control center",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ConvexClientProvider>{children}</ConvexClientProvider>
      </body>
    </html>
  );
}
