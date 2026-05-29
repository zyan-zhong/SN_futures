const FIRST_RUN_KEY = "firstRunCompleted";

export function hasCompletedFirstRun(): boolean {
  try {
    return window.localStorage.getItem(FIRST_RUN_KEY) === "true";
  } catch {
    return false;
  }
}

export function markFirstRunCompleted(): void {
  try {
    window.localStorage.setItem(FIRST_RUN_KEY, "true");
  } catch {
    // localStorage may be disabled by the browser; the terminal still works.
  }
}

export function shouldPromptForConfiguration(alphaConfigured?: boolean, newsConfigured?: boolean): boolean {
  if (hasCompletedFirstRun()) return false;
  return !alphaConfigured || !newsConfigured;
}

