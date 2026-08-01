"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { CommandMenu } from "./CommandMenu";

type SearchApi = { open: () => void };

const SearchContext = createContext<SearchApi>({ open: () => {} });

export function useSearch() {
  return useContext(SearchContext);
}

/**
 * Owns the ⌘K command menu for the whole app so any surface — the navbar
 * search field, the docs drawer — can open the same instance.
 */
export function SearchProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const api = useMemo<SearchApi>(
    () => ({ open: () => setOpen(true) }),
    [],
  );
  const onOpenChange = useCallback((next: boolean) => setOpen(next), []);

  return (
    <SearchContext.Provider value={api}>
      {children}
      <CommandMenu open={open} onOpenChange={onOpenChange} />
    </SearchContext.Provider>
  );
}
