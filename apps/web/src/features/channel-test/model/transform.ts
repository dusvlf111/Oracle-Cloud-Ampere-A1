import type { ChannelCreate } from "@/shared/api/schemas/channelCreate";

import type { ChannelCreateOutput, ChannelEditOutput } from "./schema";

/**
 * Map validated form output to the API's `ChannelCreate`/`ChannelUpdate`
 * payload (PRD §8). For ntfy the comma-separated `tags` string is split into an
 * array. Used for both create and edit — on edit the server keeps the stored
 * secret when a sensitive field is blank or the masked (***...) echo.
 */
export function toChannelCreatePayload(
  values: ChannelCreateOutput | ChannelEditOutput,
): ChannelCreate {
  const { name, enabled, config } = values;
  const base = { name, enabled };

  switch (config.type) {
    case "discord":
    case "slack":
      return {
        ...base,
        type: config.type,
        config: { type: config.type, webhook_url: config.webhook_url },
      };
    case "telegram":
      return {
        ...base,
        type: "telegram",
        config: {
          type: "telegram",
          bot_token: config.bot_token,
          chat_id: config.chat_id,
        },
      };
    case "ntfy": {
      const tags = (config.tags ?? "")
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      return {
        ...base,
        type: "ntfy",
        config: {
          type: "ntfy",
          server_url: config.server_url,
          topic: config.topic,
          token: config.token || undefined,
          priority: config.priority,
          tags,
        },
      };
    }
  }
}
