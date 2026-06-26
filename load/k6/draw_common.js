export function requiredEnv(name) {
  const value = __ENV[name];
  if (value === undefined || value === "") {
    throw new Error(`missing required env: ${name} (set in .env.load)`);
  }
  return value;
}

export function loadDrawConfig() {
  const botStart = Number(requiredEnv("LOAD_BOT_ID_START"));
  const botCount = Number(requiredEnv("LOAD_BOT_COUNT"));
  const chatIdBase = Number(requiredEnv("LOAD_CHAT_ID_BASE"));
  const userIdBase = Number(requiredEnv("LOAD_USER_ID_BASE"));
  const playersPerChat = Number(requiredEnv("LOAD_PLAYERS_PER_CHAT"));
  const command = requiredEnv("LOAD_DRAW_COMMAND");
  return {
    botStart,
    botCount,
    chatIdBase,
    userIdBase,
    playersPerChat,
    command,
  };
}

export function botOffset(botId, botStart) {
  return botId - botStart;
}

export function chatIdForBot(offset, chatIdBase) {
  return chatIdBase + offset;
}

export function invokerUserId(offset, userIdBase, playersPerChat) {
  return userIdBase + offset * playersPerChat;
}

export function buildMessageUpdate(updateId, botId, config) {
  const offset = botOffset(botId, config.botStart);
  return {
    update_id: updateId,
    message: {
      message_id: updateId,
      date: Math.floor(Date.now() / 1000),
      chat: { id: chatIdForBot(offset, config.chatIdBase), type: "group" },
      from: {
        id: invokerUserId(offset, config.userIdBase, config.playersPerChat),
        is_bot: false,
        first_name: "Load",
      },
      text: config.command,
    },
  };
}

export function runHappyOptions(botCount) {
  return {
    scenarios: {
      draw_happy: {
        executor: "per-vu-iterations",
        vus: botCount,
        iterations: 1,
        maxDuration: "30m",
      },
    },
    thresholds: {
      http_req_failed: ["rate<0.01"],
    },
  };
}

export function loadContentionConfig() {
  const base = loadDrawConfig();
  const vus = Number(requiredEnv("LOAD_CONTENTION_VUS"));
  const iterations = Number(requiredEnv("LOAD_CONTENTION_ITERATIONS"));
  const targetBotId = Number(
    __ENV.LOAD_CONTENTION_BOT_ID || String(base.botStart),
  );
  return { ...base, vus, iterations, targetBotId };
}

export function runContentionOptions(vus, iterations) {
  return {
    scenarios: {
      draw_contention: {
        executor: "shared-iterations",
        vus,
        iterations,
        maxDuration: "10m",
      },
    },
    thresholds: {
      http_req_failed: ["rate<0.01"],
    },
  };
}
