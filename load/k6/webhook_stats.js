import http from "k6/http";
import { check, sleep } from "k6";

function requiredEnv(name) {
  const value = __ENV[name];
  if (value === undefined || value === "") {
    throw new Error(`missing required env: ${name} (set in .env.load)`);
  }
  return value;
}

const baseUrl = requiredEnv("LOAD_BASE_URL");
const secret = requiredEnv("WEBHOOK_SECRET_TOKEN");
const botStart = Number(requiredEnv("LOAD_BOT_ID_START"));
const botCount = Number(requiredEnv("LOAD_BOT_COUNT"));
const chatIdBase = Number(requiredEnv("LOAD_CHAT_ID_BASE"));
const userIdBase = Number(requiredEnv("LOAD_USER_ID_BASE"));

export const options = {
  scenarios: {
    webhook_light: {
      executor: "ramping-arrival-rate",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 20,
      maxVUs: 100,
      stages: [
        { target: 10, duration: "30s" },
        { target: 50, duration: "1m" },
        { target: 10, duration: "30s" },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const botId = botStart + (__VU % botCount);
  const offset = botId - botStart;
  const updateId = __ITER + botId * 1_000_000;

  const payload = JSON.stringify({
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
  });

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
