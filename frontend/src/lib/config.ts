/** Public runtime configuration (NEXT_PUBLIC_* only; no secrets ever reach the browser). */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
export const STRIPE_MODE = process.env.NEXT_PUBLIC_STRIPE_MODE === "live" ? "live" : "test";
export const DEFAULT_LOCALE = process.env.NEXT_PUBLIC_DEFAULT_LOCALE ?? "en";
export const APP_NAME = "ADVAR";
