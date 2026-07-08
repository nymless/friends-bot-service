import exec from "k6/execution";

import { optionalEnv } from "./env_common.js";
import {
  botOffset,
  buildMessageUpdate,
  chatIdForBot,
  chatSlotForIteration,
  invokerUserId,
  loadDrawConfig,
  slotFromIndex,
} from "./draw_common.js";

export function loadRampConfig() {
  return loadDrawConfig();
}

/**
 * Ramp target selection.
 * - vu (default): sticky bot per VU, chat rotates per iteration
 * - random: random bot, chat rotates per iteration
 * - round_robin: global (bot, chat) from iterationInTest — one draw per slot per UTC day
 */
export function pickRampSlot(config, vu, iteration) {
  const pick = optionalEnv("LOAD_RAMP_BOT_PICK", "vu").toLowerCase();
  if (pick === "round_robin") {
    return slotFromIndex(exec.scenario.iterationInTest, config);
  }
  if (pick === "random") {
    return {
      botId: config.botStart + Math.floor(Math.random() * config.botCount),
      chatSlot: chatSlotForIteration(iteration, config.chatsPerBot),
    };
  }
  return {
    botId: config.botStart + (vu % config.botCount),
    chatSlot: chatSlotForIteration(iteration, config.chatsPerBot),
  };
}

/** @deprecated Use pickRampSlot; kept for callers that only need bot id. */
export function pickRampBotId(config, vu) {
  return pickRampSlot(config, vu, 0).botId;
}

export function buildRampMessageUpdate(updateId, botId, config, chatSlot) {
  const offset = botOffset(botId, config.botStart);

  if (config.command === "/stats") {
    return {
      update_id: updateId,
      message: {
        message_id: updateId,
        date: Math.floor(Date.now() / 1000),
        chat: {
          id: chatIdForBot(
            offset,
            config.chatIdBase,
            config.chatsPerBot,
            chatSlot,
          ),
          type: "group",
        },
        from: {
          id: config.userIdBase + offset,
          is_bot: false,
          first_name: "Load",
        },
        text: config.command,
      },
    };
  }
  return buildMessageUpdate(updateId, botId, config, chatSlot);
}
