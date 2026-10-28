import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Announce = (message: string, options?: { assertive?: boolean }) => void;

const AnnounceContext = createContext<Announce>(() => {});

/** Say something to a screen reader without moving focus. Polite unless it stops a decision. */
export function useAnnounce(): Announce {
  return useContext(AnnounceContext);
}

const NBSP = String.fromCharCode(0xa0);

// A repeated message is changed by a trailing non-breaking space so it is announced again.
function next(previous: string, message: string): string {
  return previous === message ? message + NBSP : message;
}

export function LiveRegionProvider({ children }: { children: ReactNode }) {
  const [polite, setPolite] = useState("");
  const [assertive, setAssertive] = useState("");

  const announce = useCallback<Announce>((message, options) => {
    if (options?.assertive) setAssertive((previous) => next(previous, message));
    else setPolite((previous) => next(previous, message));
  }, []);
  const value = useMemo(() => announce, [announce]);

  return (
    <AnnounceContext.Provider value={value}>
      {children}
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
        {polite}
      </div>
      <div role="alert" aria-live="assertive" aria-atomic="true" className="visually-hidden">
        {assertive}
      </div>
    </AnnounceContext.Provider>
  );
}
