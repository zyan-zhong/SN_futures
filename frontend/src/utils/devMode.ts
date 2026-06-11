export function isDevConsoleEnabled() {
  const envValue = String(import.meta.env.VITE_SN_ENABLE_DEV_CONSOLE ?? "").toLowerCase();
  if (envValue === "1" || envValue === "true") return true;
  if (typeof window === "undefined") return false;
  return (
    window.localStorage.getItem("SN_ENABLE_DEV_CONSOLE") === "1" ||
    window.localStorage.getItem("sn_enable_dev_console") === "1"
  );
}
