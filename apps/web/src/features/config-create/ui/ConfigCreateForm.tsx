"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { Controller, useForm } from "react-hook-form";

import { useChannels } from "@/entities/channel";
import {
  createConfig,
  updateConfig,
  type Config,
} from "@/entities/config";
import { useCredentials } from "@/entities/credential";
import { useAvailabilityDomains, useImages, useSubnets } from "@/entities/meta";
import { Button, Input, Label, isApiError } from "@/shared";

import {
  BOOT_VOLUME_OPTIONS,
  MAX_ATTEMPTS_OPTIONS,
  MEMORY_OPTIONS,
  OCPU_OPTIONS,
  RETRY_INTERVAL_OPTIONS,
  SHAPE_OPTIONS,
} from "../model/options";
import { configCreateSchema, type ConfigCreateValues } from "../model/schema";
import { MetaSelectField, type MetaOption } from "./MetaSelectField";
import { SelectField } from "./SelectField";

export interface ConfigCreateFormProps {
  /** create (default) submits POST; edit submits PUT to the existing id. */
  mode?: "create" | "edit";
  /** Existing config to prefill in edit mode. */
  initial?: Config;
  onCreated?: (config: Config) => void;
  /** Called after a successful create OR edit. */
  onSaved?: (config: Config) => void;
}

const TEXT_FIELDS: Array<{ name: keyof ConfigCreateValues; label: string }> = [
  { name: "name", label: "Name" },
  { name: "ssh_public_key", label: "SSH public key" },
];

/** Build form defaults from an existing config (edit) or static (create). */
function toDefaults(initial?: Config): Partial<ConfigCreateValues> {
  if (!initial) {
    return {
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
    };
  }
  return {
    name: initial.name,
    credential_id: initial.credential_id,
    shape: initial.shape,
    ocpus: initial.ocpus,
    memory_gb: initial.memory_gb,
    boot_volume_gb: initial.boot_volume_gb,
    image_ocid: initial.image_ocid,
    subnet_ocid: initial.subnet_ocid,
    availability_domain: initial.availability_domain,
    ssh_public_key: initial.ssh_public_key,
    retry_interval_sec: initial.retry_interval_sec,
    max_attempts: initial.max_attempts ?? undefined,
    channel_ids: initial.channel_ids ?? [],
  };
}

export function ConfigCreateForm({
  mode = "create",
  initial,
  onCreated,
  onSaved,
}: ConfigCreateFormProps) {
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
    defaultValues: toDefaults(initial),
  });

  // Coerce the selected credential to a number; meta lookups stay disabled
  // until a real credential is chosen.
  const rawCredentialId = watch("credential_id");
  const credentialId =
    rawCredentialId == null || rawCredentialId === ""
      ? undefined
      : Number(rawCredentialId);
  const shape = watch("shape") || "VM.Standard.A1.Flex";
  const ocpus = Number(watch("ocpus")) || 0;
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
      const payload = {
        name: values.name,
        credential_id: Number(values.credential_id),
        shape: values.shape || "VM.Standard.A1.Flex",
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
      };
      const saved =
        mode === "edit" && initial
          ? await updateConfig(initial.id, payload)
          : await createConfig(payload);
      if (mode === "create") reset();
      onCreated?.(saved);
      onSaved?.(saved);
    } catch (err) {
      setFormError(
        isApiError(err)
          ? err.message
          : `Failed to ${mode === "edit" ? "update" : "create"} config.`,
      );
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
          className="min-h-11 w-full appearance-none rounded border border-gray-300 bg-white px-3 py-2 text-base sm:min-h-0 sm:appearance-auto sm:px-2 sm:py-1 sm:text-sm"
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
        name="shape"
        render={({ field }) => (
          <SelectField
            id="shape"
            label="Shape"
            value={field.value ?? "VM.Standard.A1.Flex"}
            onChange={field.onChange}
            options={SHAPE_OPTIONS}
            allowManual
            errorMessage={errors.shape?.message as string}
          />
        )}
      />

      <Controller
        control={control}
        name="ocpus"
        render={({ field }) => (
          <SelectField
            id="ocpus"
            label="OCPUs"
            value={String(field.value ?? "")}
            onChange={(v) => field.onChange(v)}
            options={OCPU_OPTIONS}
            hint="Free Tier limit: 4 OCPUs"
            errorMessage={errors.ocpus?.message as string}
          />
        )}
      />

      <Controller
        control={control}
        name="memory_gb"
        render={({ field }) => (
          <SelectField
            id="memory_gb"
            label="Memory (GB)"
            value={String(field.value ?? "")}
            onChange={(v) => field.onChange(v)}
            options={MEMORY_OPTIONS}
            hint={
              ocpus > 0
                ? `Recommended: OCPU × 6 = ${ocpus * 6} GB`
                : "Recommended: 6 GB per OCPU"
            }
            errorMessage={errors.memory_gb?.message as string}
          />
        )}
      />

      <Controller
        control={control}
        name="boot_volume_gb"
        render={({ field }) => (
          <SelectField
            id="boot_volume_gb"
            label="Boot volume (GB)"
            value={String(field.value ?? "")}
            onChange={(v) => field.onChange(v)}
            options={BOOT_VOLUME_OPTIONS}
            hint="Free Tier total limit: 200 GB"
            errorMessage={errors.boot_volume_gb?.message as string}
          />
        )}
      />

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

      <Controller
        control={control}
        name="retry_interval_sec"
        render={({ field }) => (
          <SelectField
            id="retry_interval_sec"
            label="Retry interval"
            value={String(field.value ?? "")}
            onChange={(v) => field.onChange(v)}
            options={RETRY_INTERVAL_OPTIONS}
            errorMessage={errors.retry_interval_sec?.message as string}
          />
        )}
      />

      <Controller
        control={control}
        name="max_attempts"
        render={({ field }) => (
          <SelectField
            id="max_attempts"
            label="Max attempts"
            value={field.value == null ? "" : String(field.value)}
            onChange={(v) => field.onChange(v === "" ? undefined : v)}
            options={MAX_ATTEMPTS_OPTIONS}
            errorMessage={errors.max_attempts?.message as string}
          />
        )}
      />

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
        {isSubmitting
          ? mode === "edit"
            ? "Saving…"
            : "Creating…"
          : mode === "edit"
            ? "Save changes"
            : "Create config"}
      </Button>
    </form>
  );
}
