/** Единственная точка обращения к бекенду. */

import { API_BASE } from "./config.js";

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
