import http from "k6/http";
import { check } from "k6";
import {
  buildMessageUpdate,
  happyPathSlot,
  loadDrawConfig,
  loadTestSetup,
  loadTestTeardown,
  requiredEnv,
  runHappyOptions,
} from "./draw_common.js";

const config = loadDrawConfig();
const mockUrl = requiredEnv("LOAD_TELEGRAM_MOCK_URL");

export const options = runHappyOptions(config.botCount);

export function setup() {
  const timing = loadTestSetup();
  const response = http.post(`${mockUrl}/_load/reset`);
  check(response, { "reset ok": (r) => r.status === 200 });
  return timing;
}

export function teardown(data) {
  loadTestTeardown(data);
}

export default function () {
  const { botId, chatSlot } = happyPathSlot(__VU, config);
  const updateId = botId * 1_000_000 + chatSlot + 1;

  const payload = JSON.stringify({
    bot_id: botId,
    update: buildMessageUpdate(updateId, botId, config, chatSlot),
  });

  const response = http.post(`${mockUrl}/_load/inject`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(response, {
    "inject ok": (r) => r.status === 200,
  });
}
