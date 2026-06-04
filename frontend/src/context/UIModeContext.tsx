import { createContext, useContext, type ReactNode } from "react";

export type UIMode = "simple" | "professional";

export type UIModeContextValue = {
  uiMode: UIMode;
  setUIMode: (mode: UIMode) => void;
};

const UIModeContext = createContext<UIModeContextValue>({
  uiMode: "simple",
  setUIMode: () => undefined
});

export function UIModeProvider({
  value,
  children
}: {
  value: UIModeContextValue;
  children: ReactNode;
}) {
  return <UIModeContext.Provider value={value}>{children}</UIModeContext.Provider>;
}

export function useUIMode() {
  return useContext(UIModeContext);
}
