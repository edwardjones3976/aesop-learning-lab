import { createFixtureApi } from "./fixture-api.js";
import { startApp } from "./render.js";

const root = document.querySelector("#app");
const scenario = new URLSearchParams(location.search).get("scenario") ?? "default";

try {
  startApp(root, createFixtureApi({ scenario }));
} catch (error) {
  const alert = document.createElement("p");
  alert.setAttribute("role", "alert");
  alert.textContent = error instanceof Error ? error.message : "The practice page could not start.";
  root.replaceChildren(alert);
}
