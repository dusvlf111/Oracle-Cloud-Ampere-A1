"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { Controller, useForm } from "react-hook-form";

import { useChannels } from "@/entities/channel";
import { createConfig, type Config } from "@/entities/config";
import { useCredentials } from "@/entities/credential";
import { useAvailabilityDomains, useImages, useSubnets } from "@/entities/meta";
import { Button, Input, Label, isApiError } from "@/shared";

import { configCreateSchema, type ConfigCreateValues } from "../model/schema";
import { MetaSelectField, type MetaOption } from "./MetaSelectField";

export interface ConfigCreateFormProps {
  onCreated?: (config: Config) => void;
}

const TEXT_FIELDS: Array<{ name: keyof ConfigCreateValues; label: string }> = [
  { name: "name", label: "Name" },
  { name: "shape", label: "Shape" },
  { name: "ssh_public_key", label: "SSH public key" },
];

const NUMBER_FIELDS: Array<{ name: keyof ConfigCreateValues; label: string }> = [
  { name: "ocpus", label: "OCPUs" },
  { name: "memory_gb", label: "Memory (GB)" },
  { name: "boot_volume_gb", label: "Boot volume (GB)" },
  { name: "retry_interval_sec", label: "Retry interval (s)" },
  { name: "max_attempts", label: "Max attempts (optional)" },
];

export function ConfigCreateForm({ onCreated }: ConfigCreateFormProps) {
  const { data: credentials = [] } = useCredentials();
  const { data: channels = [] } = useChannels();
  const [formError, setFormError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ConfigCreateValues>({
    resolver: zodResolver(configCreateSchema),
    defaultValues: {
      name: "",
      shape: "VM.Standard.A1.Flex",
      ocpus: 4,
      memory_gb: 24,
      boot_volume_gb: 50,
      image_ocid: "",
      subnet_ocid: "",
      availability_domain: "",
      ssh_public_key: "",
      retry_interval_sec: 60,
      channel_ids: [],
    },
  });

  // Coerce the selected credential to a number; meta lookups stay disabled
  // until a real credential is chosen.
  const rawCredentialId = watch("credential_id");
  const credentialId =
    rawCredentialId == null || rawCredentialId === ""
      ? undefined
      : Number(rawCredentialId);
  const shape = watch("shape") || "VM.Standard.A1.Flex";
  const hasCredential = credentialId != null && !Number.isNaN(credentialId);

  const enabled = { query: { enabled: hasCredential } } as const;

  const adQuery = useAvailabilityDomains(
    { credential_id: credentialId ?? 0 },
    enabled,
  );
  const imageQuery = useImages(
    { credential_id: credentialId ?? 0, shape },
    enabled,
  );
  const subnetQuery = useSubnets(
    { credential_id: credentialId ?? 0 },
    enabled,
  );

  const adOptions: MetaOption[] = (adQuery.data ?? []).map((ad) => ({
    value: ad,
    label: ad,
  }));
  const imageOptions: MetaOption[] = (imageQuery.data ?? []).map((img) => ({
    value: img.ocid,
    label: `${img.display_name} (${img.os_version})`,
  }));
  const subnetOptions: MetaOption[] = (subnetQuery.data ?? []).map((s) => ({
    value: s.ocid,
    label: `${s.display_name} (${s.cidr_block})`,
  }));

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const created = await createConfig({
        name: values.name,
        credential_id: Number(values.credential_id),
        shape: values.shape,
        ocpus: Number(values.ocpus),
        memory_gb: Number(values.memory_gb),
        boot_volume_gb: Number(values.boot_volume_gb),
        image_ocid: values.image_ocid,
        subnet_ocid: values.subnet_ocid,
        availability_domain: values.availability_domain,
        ssh_public_key: values.ssh_public_key,
        retry_interval_sec: Number(values.retry_interval_sec),
        // Schema preprocesses empty input → undefined (unbounded retries).
        max_attempts:
          values.max_attempts == null ? undefined : Number(values.max_attempts),
        channel_ids: values.channel_ids ?? [],
      });
      reset();
      onCreated?.(created);
    } catch (err) {
      setFormError(isApiError(err) ? err.message : "Failed to create config.");
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
      {TEXT_FIELDS.map(({ name, label }) => (
        <div key={name} className="flex flex-col gap-1">
          <Label htmlFor={name}>{label}</Label>
          <Input id={name} {...register(name)} />
          {errors[name] && (
            <p role="alert" className="text-sm text-red-600">
              {errors[name]?.message as string}
            </p>
          )}
        </div>
      ))}

      <div className="flex flex-col gap-1">
        <Label htmlFor="credential_id">Credential</Label>
        <select
          id="credential_id"
          aria-label="Credential"
          {...register("credential_id")}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="">Select a credential…</option>
          {credentials.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {errors.credential_id && (
          <p role="alert" className="text-sm text-red-600">
            {errors.credential_id.message as string}
          </p>
        )}
      </div>

      <Controller
        control={control}
        name="availability_domain"
        render={({ field }) => (
          <MetaSelectField
            id="availability_domain"
            label="Availability domain"
            value={field.value ?? ""}
            onChange={field.onChange}
            options={adOptions}
            isLoading={adQuery.isLoading}
            isError={adQuery.isError}
            hasCredential={hasCredential}
            errorMessage={errors.availability_domain?.message as string}
          />
        )}
      />

      <Controller
        control={control}
        name="image_ocid"
        render={({ field }) => (
          <MetaSelectField
            id="image_ocid"
            label="Image OCID"
            value={field.value ?? ""}
            onChange={field.onChange}
            options={imageOptions}
            isLoading={imageQuery.isLoading}
            isError={imageQuery.isError}
            hasCredential={hasCredential}
            errorMessage={errors.image_ocid?.message as string}
          />
        )}
      />

      <Controller
        control={control}
        name="subnet_ocid"
        render={({ field }) => (
          <MetaSelectField
            id="subnet_ocid"
            label="Subnet OCID"
            value={field.value ?? ""}
            onChange={field.onChange}
            options={subnetOptions}
            isLoading={subnetQuery.isLoading}
            isError={subnetQuery.isError}
            hasCredential={hasCredential}
            errorMessage={errors.subnet_ocid?.message as string}
          />
        )}
      />

      {NUMBER_FIELDS.map(({ name, label }) => (
        <div key={name} className="flex flex-col gap-1">
          <Label htmlFor={name}>{label}</Label>
          <Input id={name} type="number" {...register(name)} />
          {errors[name] && (
            <p role="alert" className="text-sm text-red-600">
              {errors[name]?.message as string}
            </p>
          )}
        </div>
      ))}

      <fieldset className="flex flex-col gap-1">
        <legend className="text-sm font-medium">Notification channels</legend>
        <Controller
          control={control}
          name="channel_ids"
          render={({ field: { value = [], onChange } }) => (
            <div className="flex flex-col gap-1">
              {channels.length === 0 && (
                <span className="text-xs text-gray-500">No channels available.</span>
              )}
              {channels.map((ch) => {
                const checked = value.includes(ch.id);
                return (
                  <label key={ch.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      aria-label={ch.name}
                      checked={checked}
                      onChange={(e) =>
                        onChange(
                          e.target.checked
                            ? [...value, ch.id]
                            : value.filter((id) => id !== ch.id),
                        )
                      }
                    />
                    {ch.name}
                  </label>
                );
              })}
            </div>
          )}
        />
      </fieldset>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating…" : "Create config"}
      </Button>
    </form>
  );
}
