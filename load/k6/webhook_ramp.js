import http from "k6/http";
import { check, sleep } from "k6";
import {
  loadTestSetup,
  loadTestTeardown,
  rampOptions,
  requiredEnv,
} from "./env_common.js";
import { buildRampMessageUpdate, loadRampConfig, pickRampBotId } from "./ramp_common.js";

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
  const botId = pickRampBotId(config, __VU);
  const updateId = __ITER + botId * 1_000_000;

  const payload = JSON.stringify(
    buildRampMessageUpdate(updateId, botId, config),
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
