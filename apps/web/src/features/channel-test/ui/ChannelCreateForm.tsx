"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { useForm } from "react-hook-form";

import { createChannel, CHANNEL_TYPES, type Channel } from "@/entities/channel";
import { Button, Input, Label, isApiError } from "@/shared";

import {
  channelCreateSchema,
  type ChannelCreateValues,
  type ChannelCreateOutput,
} from "../model/schema";
import { toChannelCreatePayload } from "../model/transform";

export interface ChannelCreateFormProps {
  onCreated?: (channel: Channel) => void;
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

export function ChannelCreateForm({ onCreated }: ChannelCreateFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChannelCreateValues>({
    resolver: zodResolver(channelCreateSchema),
    defaultValues: {
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
      const payload = toChannelCreatePayload(values as ChannelCreateOutput);
      const created = await createChannel(payload);
      reset();
      onCreated?.(created);
    } catch (err) {
      setFormError(isApiError(err) ? err.message : "Failed to create channel.");
    }
  });

  const configErrors = errors.config as Record<string, { message?: string }> | undefined;

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
          {...register("config.type", { onChange: (e) => onTypeChange(e.target.value) })}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          {CHANNEL_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {(type === "discord" || type === "slack") && (
        <div className="flex flex-col gap-1">
          <Label htmlFor="webhook_url">Webhook URL</Label>
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
            <Label htmlFor="bot_token">Bot token</Label>
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
            <Label htmlFor="token">Token (optional)</Label>
            <Input id="token" {...register("config.token")} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="priority">Priority (1–5)</Label>
            <Input id="priority" type="number" min={1} max={5} {...register("config.priority")} />
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
        {isSubmitting ? "Creating…" : "Create channel"}
      </Button>
    </form>
  );
}
