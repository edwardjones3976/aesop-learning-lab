import { createFixtureApi } from "./fixture-api.js";
import { createHttpApi } from "./http-api.js";
import { startApp } from "./render.js";

const root = document.querySelector("#app");
const scenario = new URLSearchParams(location.search).get("scenario") ?? "default";
const fixture = new URLSearchParams(location.search).has("scenario");

try {
  startApp(root, fixture ? createFixtureApi({ scenario }) : createHttpApi());
} catch (error) {
  const alert = document.createElement("p");
  alert.setAttribute("role", "alert");
  alert.textContent = error instanceof Error ? error.message : "The practice page could not start.";
  root.replaceChildren(alert);
}
