import { z } from "zod";

/**
 * Channel creation form, modelled as a zod discriminated union on `type`
 * (PRD §7.5.2 / §6 config_enc). The `config` shape changes per type:
 * discord/slack → webhook_url, telegram → bot_token+chat_id,
 * ntfy → server_url/topic/token?/priority/tags.
 */

const discordConfig = z.object({
  type: z.literal("discord"),
  webhook_url: z.string().url("Valid webhook URL required"),
});

const slackConfig = z.object({
  type: z.literal("slack"),
  webhook_url: z.string().url("Valid webhook URL required"),
});

const telegramConfig = z.object({
  type: z.literal("telegram"),
  bot_token: z.string().min(1, "Bot token is required"),
  chat_id: z.string().min(1, "Chat ID is required"),
});

const ntfyConfig = z.object({
  type: z.literal("ntfy"),
  server_url: z.string().url("Valid server URL required"),
  topic: z.string().min(1, "Topic is required"),
  token: z.string().optional(),
  priority: z.coerce.number().int().min(1).max(5).default(3),
  tags: z.string().optional(), // comma-separated in the UI
});

export const channelConfigSchema = z.discriminatedUnion("type", [
  discordConfig,
  slackConfig,
  telegramConfig,
  ntfyConfig,
]);

export const channelCreateSchema = z.object({
  name: z.string().min(1, "Name is required"),
  enabled: z.boolean().default(true),
  config: channelConfigSchema,
});

export type ChannelConfigValues = z.infer<typeof channelConfigSchema>;
export type ChannelCreateValues = z.input<typeof channelCreateSchema>;
export type ChannelCreateOutput = z.output<typeof channelCreateSchema>;
