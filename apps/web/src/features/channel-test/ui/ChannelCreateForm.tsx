"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { useForm } from "react-hook-form";

import {
  createChannel,
  updateChannel,
  CHANNEL_TYPES,
  type Channel,
} from "@/entities/channel";
import { Button, Input, Label, isApiError } from "@/shared";

import {
  channelCreateSchema,
  channelEditSchema,
  type ChannelCreateValues,
  type ChannelCreateOutput,
  type ChannelEditOutput,
} from "../model/schema";
import { toChannelCreatePayload } from "../model/transform";

export interface ChannelCreateFormProps {
  /** create (default) POSTs; edit PUTs to the existing channel. */
  mode?: "create" | "edit";
  /** Existing channel to prefill in edit mode (sensitive config masked). */
  initial?: Channel;
  onCreated?: (channel: Channel) => void;
  /** Called after a successful create OR edit. */
  onSaved?: (channel: Channel) => void;
}

function defaultsForType(type: string): ChannelCreateValues["config"] {
  switch (type) {
    case "discord":
      return { type: "discord", webhook_url: "" };
    case "slack":
      return { type: "slack", webhook_url: "" };
    case "telegram":
      return { type: "telegram", bot_token: "", chat_id: "" };
    default:
      return { type: "ntfy", server_url: "", topic: "", priority: 3 };
  }
}

/** Build form defaults from an existing channel (edit) — masked secrets kept. */
function defaultsFromChannel(ch: Channel): ChannelCreateValues {
  const cfg = (ch.config ?? {}) as Record<string, unknown>;
  const type = ch.type;
  const base = { name: ch.name, enabled: ch.enabled };
  switch (type) {
    case "discord":
    case "slack":
      return {
        ...base,
        config: { type, webhook_url: String(cfg.webhook_url ?? "") },
      };
    case "telegram":
      return {
        ...base,
        config: {
          type: "telegram",
          bot_token: String(cfg.bot_token ?? ""),
          chat_id: String(cfg.chat_id ?? ""),
        },
      };
    default:
      return {
        ...base,
        config: {
          type: "ntfy",
          server_url: String(cfg.server_url ?? ""),
          topic: String(cfg.topic ?? ""),
          token: cfg.token ? String(cfg.token) : "",
          priority: typeof cfg.priority === "number" ? cfg.priority : 3,
          tags: Array.isArray(cfg.tags) ? cfg.tags.join(", ") : "",
        },
      };
  }
}

export function ChannelCreateForm({
  mode = "create",
  initial,
  onCreated,
  onSaved,
}: ChannelCreateFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const isEdit = mode === "edit";
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChannelCreateValues>({
    resolver: zodResolver(isEdit ? channelEditSchema : channelCreateSchema),
    defaultValues:
      isEdit && initial
        ? defaultsFromChannel(initial)
        : {
            name: "",
            enabled: true,
            config: { type: "discord", webhook_url: "" },
          },
  });

  const type = watch("config.type");

  const onTypeChange = (next: string) => {
    // Reset the config sub-object so stale fields don't fail validation.
    setValue("config", defaultsForType(next), { shouldValidate: false });
  };

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload = toChannelCreatePayload(
        values as ChannelCreateOutput | ChannelEditOutput,
      );
      const saved =
        isEdit && initial
          ? await updateChannel(initial.id, payload)
          : await createChannel(payload);
      if (!isEdit) reset();
      onCreated?.(saved);
      onSaved?.(saved);
    } catch (err) {
      setFormError(
        isApiError(err)
          ? err.message
          : `Failed to ${isEdit ? "update" : "create"} channel.`,
      );
    }
  });

  const configErrors = errors.config as
    | Record<string, { message?: string }>
    | undefined;

  const secretHint = isEdit ? " (변경 시에만 입력)" : "";

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
      <div className="flex flex-col gap-1">
        <Label htmlFor="name">Name</Label>
        <Input id="name" {...register("name")} />
        {errors.name && (
          <p role="alert" className="text-sm text-red-600">
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="config.type">Type</Label>
        <select
          id="config.type"
          aria-label="Type"
          disabled={isEdit}
          {...register("config.type", {
            onChange: (e) => onTypeChange(e.target.value),
          })}
          className="min-h-11 w-full appearance-none rounded border border-gray-300 bg-white px-3 py-2 text-base disabled:opacity-60 sm:min-h-0 sm:appearance-auto sm:px-2 sm:py-1 sm:text-sm"
        >
          {CHANNEL_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {isEdit && (
          <p className="text-xs text-gray-500">
            타입은 편집 시 변경할 수 없습니다.
          </p>
        )}
      </div>

      {(type === "discord" || type === "slack") && (
        <div className="flex flex-col gap-1">
          <Label htmlFor="webhook_url">Webhook URL{secretHint}</Label>
          <Input id="webhook_url" {...register("config.webhook_url")} />
          {configErrors?.webhook_url && (
            <p role="alert" className="text-sm text-red-600">
              {configErrors.webhook_url.message}
            </p>
          )}
        </div>
      )}

      {type === "telegram" && (
        <>
          <div className="flex flex-col gap-1">
            <Label htmlFor="bot_token">Bot token{secretHint}</Label>
            <Input id="bot_token" {...register("config.bot_token")} />
            {configErrors?.bot_token && (
              <p role="alert" className="text-sm text-red-600">
                {configErrors.bot_token.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="chat_id">Chat ID</Label>
            <Input id="chat_id" {...register("config.chat_id")} />
            {configErrors?.chat_id && (
              <p role="alert" className="text-sm text-red-600">
                {configErrors.chat_id.message}
              </p>
            )}
          </div>
        </>
      )}

      {type === "ntfy" && (
        <>
          <div className="flex flex-col gap-1">
            <Label htmlFor="server_url">Server URL</Label>
            <Input id="server_url" {...register("config.server_url")} />
            {configErrors?.server_url && (
              <p role="alert" className="text-sm text-red-600">
                {configErrors.server_url.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="topic">Topic</Label>
            <Input id="topic" {...register("config.topic")} />
            {configErrors?.topic && (
              <p role="alert" className="text-sm text-red-600">
                {configErrors.topic.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="token">Token (optional){secretHint}</Label>
            <Input id="token" {...register("config.token")} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="priority">Priority (1–5)</Label>
            <Input
              id="priority"
              type="number"
              min={1}
              max={5}
              {...register("config.priority")}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="tags">Tags (comma-separated)</Label>
            <Input id="tags" {...register("config.tags")} />
          </div>
        </>
      )}

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting
          ? isEdit
            ? "Saving…"
            : "Creating…"
          : isEdit
            ? "Save changes"
            : "Create channel"}
      </Button>
    </form>
  );
}
