import type { ChannelCreate } from "@/shared/api/schemas/channelCreate";
import type { NtfyConfig } from "@/shared/api/schemas/ntfyConfig";

import { parseNtfyUrl } from "../lib/ntfyUrl";

import type { ChannelCreateOutput, ChannelEditOutput } from "./schema";

/**
 * Map validated form output to the API's `ChannelCreate`/`ChannelUpdate`
 * payload (PRD §8). For ntfy the single `url` field is split into
 * `{ server_url, topic }`, and the advanced fields (token/priority/tags) are
 * omitted when blank. Used for both create and edit — on edit the server keeps
 * the stored secret when a sensitive field is blank or the masked (***...) echo.
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
      const { server_url, topic } = parseNtfyUrl(config.url);
      const tags = (config.tags ?? "")
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      // Advanced fields are optional: omit when blank so the server applies its
      // own defaults (priority auto, no token/tags).
      const ntfyCfg: NtfyConfig = { type: "ntfy", server_url, topic };
      if (config.token) ntfyCfg.token = config.token;
      if (typeof config.priority === "number") {
        ntfyCfg.priority = config.priority;
      }
      if (tags.length > 0) ntfyCfg.tags = tags;
      return {
        ...base,
        type: "ntfy",
        config: ntfyCfg,
      };
    }
  }
}
