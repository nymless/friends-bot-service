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
const baseUrl = requiredEnv("LOAD_BASE_URL");
const secret = requiredEnv("WEBHOOK_SECRET_TOKEN");

export const options = runHappyOptions(config.botCount);

export function setup() {
  return loadTestSetup();
}

export function teardown(data) {
  loadTestTeardown(data);
}

export default function () {
  const { botId, chatSlot } = happyPathSlot(__VU, config);
  const updateId = botId * 1_000_000 + chatSlot + 1;

  const payload = JSON.stringify(buildMessageUpdate(updateId, botId, config, chatSlot));

  const response = http.post(`${baseUrl}/webhook/${botId}`, payload, {
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Bot-Api-Secret-Token": secret,
    },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });
}
