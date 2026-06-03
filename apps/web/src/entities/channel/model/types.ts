import type { ChannelRead } from "@/shared/api/schemas/channelRead";

/** NotificationChannel as returned by the API (sensitive config masked). */
export type Channel = ChannelRead;

export const CHANNEL_TYPES = ["discord", "slack", "telegram", "ntfy"] as const;
export type ChannelType = (typeof CHANNEL_TYPES)[number];
