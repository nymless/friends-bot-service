import http from "k6/http";
import { check } from "k6";
import {
  buildMessageUpdate,
  loadDrawConfig,
  requiredEnv,
  runHappyOptions,
} from "./draw_common.js";

const config = loadDrawConfig();
const mockUrl = requiredEnv("LOAD_TELEGRAM_MOCK_URL");

export const options = runHappyOptions(config.botCount);

export function setup() {
  const response = http.post(`${mockUrl}/_load/reset`);
  check(response, { "reset ok": (r) => r.status === 200 });
}

export default function () {
  const botId = config.botStart + (__VU - 1);
  const updateId = botId * 1_000_000 + 1;

  const payload = JSON.stringify({
    bot_id: botId,
    update: buildMessageUpdate(updateId, botId, config),
  });

  const response = http.post(`${mockUrl}/_load/inject`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(response, {
    "inject ok": (r) => r.status === 200,
  });
}
