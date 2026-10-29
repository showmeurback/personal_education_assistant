import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/golos-text";
import "@fontsource-variable/unbounded";
import "./index.css";
import App from "./App";
import { ThemeProvider } from "next-themes";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* тема — класс dark на <html>; выбор хранится в localStorage, по умолчанию — как в системе */}
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem storageKey="pea-theme" disableTransitionOnChange>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </ThemeProvider>
  </StrictMode>
);
