import http from "k6/http";
import { check, sleep } from "k6";

const targetUrl = (__ENV.TARGET_URL || "http://localhost:8501").replace(/\/$/, "");
const vus = Number(__ENV.VUS || 10);
const duration = __ENV.DURATION || "30s";

export const options = {
  vus,
  duration,
  summaryTrendStats: ["min", "avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{endpoint:health}": ["p(99)<1000"],
    "http_req_duration{endpoint:root}": ["p(99)<10000"],
  },
};

export default function () {
  const health = http.get(`${targetUrl}/_stcore/health`, {
    tags: { endpoint: "health" },
  });
  check(health, {
    "health returns ok": (res) => res.status === 200 && res.body === "ok",
  });

  const root = http.get(`${targetUrl}/`, {
    tags: { endpoint: "root" },
  });
  check(root, {
    "root returns html": (res) =>
      res.status === 200 && String(res.body).toLowerCase().includes("<!doctype html"),
  });

  sleep(1);
}
