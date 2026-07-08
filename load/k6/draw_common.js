import {
  envInt,
  requiredEnv,
  runContentionOptions,
  runHappyOptions,
} from "./env_common.js";

export {
  requiredEnv,
  runHappyOptions,
  runContentionOptions,
  loadTestSetup,
  loadTestTeardown,
} from "./env_common.js";

export function loadDrawConfig() {
  const botStart = Number(requiredEnv("LOAD_BOT_ID_START"));
  const botCount = Number(requiredEnv("LOAD_BOT_COUNT"));
  const chatIdBase = Number(requiredEnv("LOAD_CHAT_ID_BASE"));
  const userIdBase = Number(requiredEnv("LOAD_USER_ID_BASE"));
  const playersPerChat = Number(requiredEnv("LOAD_PLAYERS_PER_CHAT"));
  const chatsPerBot = envInt("LOAD_CHATS_PER_BOT", 1);
  const command = requiredEnv("LOAD_K6_COMMAND");
  return {
    botStart,
    botCount,
    chatIdBase,
    userIdBase,
    playersPerChat,
    chatsPerBot,
    command,
  };
}

export function botOffset(botId, botStart) {
  return botId - botStart;
}

export function chatIdForBot(offset, chatIdBase, chatsPerBot, chatSlot) {
  return chatIdBase + offset * chatsPerBot + chatSlot;
}

export function chatSlotForIteration(iteration, chatsPerBot) {
  return iteration % chatsPerBot;
}

export function drawSlotCount(config) {
  return config.botCount * config.chatsPerBot;
}

/** Maps a linear slot index to (botId, chatSlot); wraps at botCount * chatsPerBot. */
export function slotFromIndex(index, config) {
  const totalSlots = drawSlotCount(config);
  const slot = ((index % totalSlots) + totalSlots) % totalSlots;
  const botOffset = Math.floor(slot / config.chatsPerBot);
  const chatSlot = slot % config.chatsPerBot;
  return {
    botId: config.botStart + botOffset,
    chatSlot,
  };
}

/** One VU per happy-path slot; with chatsPerBot=1 matches legacy bot-per-VU layout. */
export function happyPathSlot(vu, config) {
  return slotFromIndex(vu - 1, config);
}

export function invokerUserId(offset, userIdBase, playersPerChat) {
  return userIdBase + offset * playersPerChat;
}

export function buildMessageUpdate(updateId, botId, config, chatSlot = 0) {
  const offset = botOffset(botId, config.botStart);
  return {
    update_id: updateId,
    message: {
      message_id: updateId,
      date: Math.floor(Date.now() / 1000),
      chat: {
        id: chatIdForBot(offset, config.chatIdBase, config.chatsPerBot, chatSlot),
        type: "group",
      },
      from: {
        id: invokerUserId(offset, config.userIdBase, config.playersPerChat),
        is_bot: false,
        first_name: "Load",
      },
      text: config.command,
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
