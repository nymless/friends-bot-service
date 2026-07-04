import http from "k6/http";
import { check } from "k6";
import {
  buildMessageUpdate,
  loadContentionConfig,
  loadTestSetup,
  loadTestTeardown,
  requiredEnv,
  runContentionOptions,
} from "./draw_common.js";

const config = loadContentionConfig();
const baseUrl = requiredEnv("LOAD_BASE_URL");
const secret = requiredEnv("WEBHOOK_SECRET_TOKEN");

export const options = runContentionOptions(config.vus, config.iterations);

export function setup() {
  return loadTestSetup();
}

export function teardown(data) {
  loadTestTeardown(data);
}

export default function () {
  const updateId = config.targetBotId * 1_000_000 + __ITER + 1;

  const payload = JSON.stringify(
    buildMessageUpdate(updateId, config.targetBotId, config),
  );

  const response = http.post(
    `${baseUrl}/webhook/${config.targetBotId}`,
    payload,
    {
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": secret,
      },
    },
  );

  check(response, {
    "status is 200": (r) => r.status === 200,
  });
}
