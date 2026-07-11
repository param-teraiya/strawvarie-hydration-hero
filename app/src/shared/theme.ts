// Applies the user's theme preference. "system" follows the OS; "light"/"dark"
// force it by stamping data-theme on <html> (the CSS handles the rest).
export function applyTheme(pref: "system" | "light" | "dark"): void {
  const root = document.documentElement;
  if (pref === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", pref);
  }
}
