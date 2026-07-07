import http from "k6/http";
import { check, sleep } from "k6";
import {
  loadTestSetup,
  loadTestTeardown,
  rampOptions,
  requiredEnv,
} from "./env_common.js";
import { buildRampMessageUpdate, loadRampConfig, pickRampSlot } from "./ramp_common.js";

const config = loadRampConfig();
const mockUrl = requiredEnv("LOAD_TELEGRAM_MOCK_URL");

export const options = rampOptions(config.botCount, "ramp");

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
  const { botId, chatSlot } = pickRampSlot(config, __VU, __ITER);
  const updateId = __ITER + botId * 1_000_000;

  const payload = JSON.stringify({
    bot_id: botId,
    update: buildRampMessageUpdate(updateId, botId, config, chatSlot),
  });

  const response = http.post(`${mockUrl}/_load/inject`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(response, {
    "inject ok": (r) => r.status === 200,
  });
  sleep(0.1);
}
