import { optionalEnv, requiredEnv } from "./env_common.js";
import {
  botOffset,
  buildMessageUpdate,
  chatIdForBot,
} from "./draw_common.js";

export function loadRampConfig() {
  return {
    botStart: Number(requiredEnv("LOAD_BOT_ID_START")),
    botCount: Number(requiredEnv("LOAD_BOT_COUNT")),
    chatIdBase: Number(requiredEnv("LOAD_CHAT_ID_BASE")),
    userIdBase: Number(requiredEnv("LOAD_USER_ID_BASE")),
    playersPerChat: Number(requiredEnv("LOAD_PLAYERS_PER_CHAT")),
    command: requiredEnv("LOAD_K6_COMMAND"),
  };
}

/** Default vu: sticky bot per VU (__VU % botCount). Set LOAD_RAMP_BOT_PICK=random to shuffle. */
export function pickRampBotId(config, vu) {
  const pick = optionalEnv("LOAD_RAMP_BOT_PICK", "vu").toLowerCase();
  if (pick === "random") {
    return config.botStart + Math.floor(Math.random() * config.botCount);
  }
  return config.botStart + (vu % config.botCount);
}

export function buildRampMessageUpdate(updateId, botId, config) {
  if (config.command === "/stats") {
    const offset = botOffset(botId, config.botStart);
    return {
      update_id: updateId,
      message: {
        message_id: updateId,
        date: Math.floor(Date.now() / 1000),
        chat: { id: chatIdForBot(offset, config.chatIdBase), type: "group" },
        from: {
          id: config.userIdBase + offset,
          is_bot: false,
          first_name: "Load",
        },
        text: config.command,
      },
    };
  }
  return buildMessageUpdate(updateId, botId, config);
}
