import http from "k6/http";
import { check, sleep } from "k6";
import { requiredEnv, statsRampOptions, loadTestSetup, loadTestTeardown } from "./env_common.js";

const mockUrl = requiredEnv("LOAD_TELEGRAM_MOCK_URL");
const botStart = Number(requiredEnv("LOAD_BOT_ID_START"));
const botCount = Number(requiredEnv("LOAD_BOT_COUNT"));
const chatIdBase = Number(requiredEnv("LOAD_CHAT_ID_BASE"));
const userIdBase = Number(requiredEnv("LOAD_USER_ID_BASE"));

export const options = statsRampOptions(botCount);

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
  const botId = botStart + (__VU % botCount);
  const offset = botId - botStart;
  const updateId = __ITER + botId * 1_000_000;

  const payload = JSON.stringify({
    bot_id: botId,
    update: {
      update_id: updateId,
      message: {
        message_id: updateId,
        date: Math.floor(Date.now() / 1000),
        chat: { id: chatIdBase + offset, type: "group" },
        from: {
          id: userIdBase + offset,
          is_bot: false,
          first_name: "Load",
        },
        text: "/stats",
      },
    },
  });

  const response = http.post(`${mockUrl}/_load/inject`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(response, {
    "inject ok": (r) => r.status === 200,
  });
  sleep(0.1);
}
