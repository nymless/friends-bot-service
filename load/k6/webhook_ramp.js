import http from "k6/http";
import { check, sleep } from "k6";
import {
  loadTestSetup,
  loadTestTeardown,
  rampOptions,
  requiredEnv,
} from "./env_common.js";
import {
  buildRampMessageUpdate,
  loadRampConfig,
  pickRampSlot,
  rampUpdateId,
} from "./ramp_common.js";

const config = loadRampConfig();
const baseUrl = requiredEnv("LOAD_BASE_URL");
const secret = requiredEnv("WEBHOOK_SECRET_TOKEN");

export const options = rampOptions(config.botCount, "ramp");

export function setup() {
  return loadTestSetup();
}

export function teardown(data) {
  loadTestTeardown(data);
}

export default function () {
  const { botId, chatSlot } = pickRampSlot(config, __VU, __ITER);
  const updateId = rampUpdateId(botId, chatSlot);

  const payload = JSON.stringify(
    buildRampMessageUpdate(updateId, botId, config, chatSlot),
  );

  const response = http.post(`${baseUrl}/webhook/${botId}`, payload, {
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Bot-Api-Secret-Token": secret,
    },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });
  sleep(0.1);
}
