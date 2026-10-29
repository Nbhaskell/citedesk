import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { app } from "../copy";
import { shortcutKey } from "../hooks/shortcuts";
import { Footer } from "./Footer";
import { ShortcutHelp } from "./ShortcutHelp";
import { StatusProvider, useStatus } from "./StatusProvider";
import { TopBar } from "./TopBar";
import styles from "./Shell.module.css";

const SECTIONS: Record<string, string> = { "/insights": "Insights", "/settings": "Settings" };

/** "(2 urgent) Insights – Citedesk": what needs attention shows on the browser tab. */
export function tabTitle(urgent: number, attention: number, path: string): string {
  const prefix = urgent > 0 ? `(${urgent} urgent) ` : attention > 0 ? `(${attention}) ` : "";
  const section = SECTIONS[path];
  return `${prefix}${section ? `${section} – ` : ""}${app.name}`;
}

function Frame() {
  const { data } = useStatus();
  const { pathname } = useLocation();
  const main = useRef<HTMLElement>(null);
  const shownPath = useRef(pathname);
  const [helpOpen, setHelpOpen] = useState(false);

  // ? opens the shortcut list from any screen (not while typing, not when shortcuts are off).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (shortcutKey(event) !== "?") return;
      event.preventDefault();
      setHelpOpen(true);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const urgent = data?.attention.urgent_open ?? 0;
  const attention = data
    ? data.attention.needs_review + data.attention.escalated + data.attention.failed
    : 0;

  useEffect(() => {
    document.title = tabTitle(urgent, attention, pathname);
  }, [urgent, attention, pathname]);

  // After moving to another page, focus its content so a keyboard or screen reader user starts
  // there, not back in the header. Only when the page really changed: not on the first load, and
  // not when a development build runs its effects twice.
  useEffect(() => {
    if (shownPath.current === pathname) return;
    shownPath.current = pathname;
    main.current?.focus();
  }, [pathname]);

  return (
    <div className={styles.frame}>
      <a href="#main" className="skip-link">
        {app.skipToContent}
      </a>
      <TopBar />
      <main id="main" ref={main} tabIndex={-1} className={styles.main}>
        <Outlet />
      </main>
      <Footer onOpenShortcuts={() => setHelpOpen(true)} />
      {helpOpen ? <ShortcutHelp onClose={() => setHelpOpen(false)} /> : null}
    </div>
  );
}

export function Shell() {
  return (
    <StatusProvider>
      <Frame />
    </StatusProvider>
  );
}
