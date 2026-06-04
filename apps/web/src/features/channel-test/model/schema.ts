import { z } from "zod";

import { NtfyUrlError, parseNtfyUrl } from "../lib/ntfyUrl";

/**
 * Channel creation form, modelled as a zod discriminated union on `type`
 * (PRD §7.5.2 / §6 config_enc). The `config` shape changes per type:
 * discord/slack → webhook_url, telegram → bot_token+chat_id,
 * ntfy → url (single line, split into server_url/topic on submit) + advanced
 * token?/priority?/tags.
 */

/**
 * A single "ntfy URL" string that must split into a server_url + topic. The UI
 * surfaces only this one field; the transform layer parses it back into the
 * API's `{ server_url, topic }` payload. The server config_enc schema is
 * unchanged.
 */
const ntfyUrlField = z.string().superRefine((value, ctx) => {
  try {
    parseNtfyUrl(value);
  } catch (err) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message:
        err instanceof NtfyUrlError
          ? err.message
          : "Invalid ntfy URL",
    });
  }
});

/** Advanced ntfy fields, all optional and omitted from the payload when blank. */
const ntfyAdvanced = {
  token: z.string().optional(),
  // Blank → auto (server picks 5 on success / 4 on error). Coerce only when set.
  priority: z
    .union([z.literal(""), z.coerce.number().int().min(1).max(5)])
    .optional(),
  tags: z.string().optional(), // comma-separated in the UI
};

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
  url: ntfyUrlField,
  ...ntfyAdvanced,
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

// ── Edit variant ──────────────────────────────────────────────────────────
// On edit the form is prefilled with the server's masked secrets (***xxx). A
// blank or masked sensitive value means "keep the stored secret" (the server
// honours this), so URL/required rules are relaxed for those fields. A real
// new value is still expected to be a valid URL.
const keptOrUrl = z
  .string()
  .refine(
    (v) => v === "" || v.startsWith("***") || /^https?:\/\/.+/.test(v),
    "Valid webhook URL required",
  );

const discordEdit = z.object({
  type: z.literal("discord"),
  webhook_url: keptOrUrl,
});
const slackEdit = z.object({
  type: z.literal("slack"),
  webhook_url: keptOrUrl,
});
const telegramEdit = z.object({
  type: z.literal("telegram"),
  // bot_token may be kept (blank/masked); chat_id is not sensitive → required.
  bot_token: z.string(),
  chat_id: z.string().min(1, "Chat ID is required"),
});
const ntfyEdit = z.object({
  type: z.literal("ntfy"),
  url: ntfyUrlField,
  ...ntfyAdvanced,
});

export const channelEditConfigSchema = z.discriminatedUnion("type", [
  discordEdit,
  slackEdit,
  telegramEdit,
  ntfyEdit,
]);

export const channelEditSchema = z.object({
  name: z.string().min(1, "Name is required"),
  enabled: z.boolean().default(true),
  config: channelEditConfigSchema,
});

export type ChannelConfigValues = z.infer<typeof channelConfigSchema>;
export type ChannelCreateValues = z.input<typeof channelCreateSchema>;
export type ChannelCreateOutput = z.output<typeof channelCreateSchema>;
export type ChannelEditOutput = z.output<typeof channelEditSchema>;
