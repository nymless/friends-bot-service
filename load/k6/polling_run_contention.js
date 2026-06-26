import http from "k6/http";
import { check } from "k6";
import {
  buildMessageUpdate,
  loadContentionConfig,
  requiredEnv,
  runContentionOptions,
} from "./draw_common.js";

const config = loadContentionConfig();
const mockUrl = requiredEnv("LOAD_TELEGRAM_MOCK_URL");

export const options = runContentionOptions(config.vus, config.iterations);

export function setup() {
  const response = http.post(`${mockUrl}/_load/reset`);
  check(response, { "reset ok": (r) => r.status === 200 });
}

export default function () {
  const updateId = config.targetBotId * 1_000_000 + __ITER + 1;

  const payload = JSON.stringify({
    bot_id: config.targetBotId,
    update: buildMessageUpdate(updateId, config.targetBotId, config),
  });

  const response = http.post(`${mockUrl}/_load/inject`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(response, {
    "inject ok": (r) => r.status === 200,
  });
}
