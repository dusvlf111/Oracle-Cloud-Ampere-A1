"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { Controller, useForm } from "react-hook-form";

import {
  createCredential,
  updateCredential,
  type Credential,
} from "@/entities/credential";
import { Button, Input, Label, OCI_REGIONS, isApiError } from "@/shared";

import {
  credentialCreateSchema,
  credentialEditSchema,
  type CredentialFormValues,
} from "../model/schema";
import { OciConfigPaste } from "./OciConfigPaste";

export interface CredentialCreateFormProps {
  /** create (default) POSTs; edit PUTs to the existing credential. */
  mode?: "create" | "edit";
  /** Existing credential to prefill in edit mode (sensitive fields masked). */
  initial?: Credential;
  onCreated?: (credential: Credential) => void;
  /** Called after a successful create OR edit. */
  onSaved?: (credential: Credential) => void;
}

const TEXT_FIELDS: Array<{ name: keyof CredentialFormValues; label: string }> = [
  { name: "name", label: "Name" },
  { name: "tenancy_ocid", label: "Tenancy OCID" },
  { name: "user_ocid", label: "User OCID" },
  { name: "fingerprint", label: "Fingerprint" },
];

const REGION_SELECT_CLASS =
  "min-h-11 w-full appearance-none rounded border border-gray-300 bg-white px-3 py-2 text-base sm:min-h-0 sm:appearance-auto sm:px-2 sm:py-1 sm:text-sm";

/**
 * Credential create/edit form. Submits a multipart `FormData` body (fields +
 * optional PEM upload). On edit, sensitive fields are prefilled with the
 * server's masked echo; resubmitting the mask keeps the stored value
 * (server-side). The private key is optional on edit (kept if not re-uploaded).
 * The OCI config paste area (Task C) prefills the OCID / fingerprint / region.
 */
export function CredentialCreateForm({
  mode = "create",
  initial,
  onCreated,
  onSaved,
}: CredentialCreateFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const isEdit = mode === "edit";

  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CredentialFormValues>({
    resolver: zodResolver(isEdit ? credentialEditSchema : credentialCreateSchema),
    defaultValues: {
      name: initial?.name ?? "",
      tenancy_ocid: initial?.tenancy_ocid ?? "",
      user_ocid: initial?.user_ocid ?? "",
      fingerprint: initial?.fingerprint ?? "",
      region: initial?.region ?? "",
      passphrase: "",
    },
  });

  // Region uses a dropdown of major regions + a "Manual input" fallback for the
  // long tail (or a prefilled value that isn't in the list).
  const region = watch("region") ?? "";
  const regionInList = OCI_REGIONS.some((r) => r.value === region);
  const [regionManual, setRegionManual] = React.useState(
    region !== "" && !regionInList,
  );
  const useRegionManual = regionManual || (region !== "" && !regionInList);

  const applyParsed = React.useCallback(
    (fields: {
      tenancy_ocid?: string;
      user_ocid?: string;
      fingerprint?: string;
      region?: string;
    }) => {
      const opts = { shouldValidate: true, shouldDirty: true } as const;
      if (fields.tenancy_ocid) setValue("tenancy_ocid", fields.tenancy_ocid, opts);
      if (fields.user_ocid) setValue("user_ocid", fields.user_ocid, opts);
      if (fields.fingerprint) setValue("fingerprint", fields.fingerprint, opts);
      if (fields.region) {
        setValue("region", fields.region, opts);
        // If the pasted region isn't one of the presets, flip to manual entry.
        if (!OCI_REGIONS.some((r) => r.value === fields.region)) {
          setRegionManual(true);
        }
      }
    },
    [setValue],
  );

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const body = {
        name: values.name,
        tenancy_ocid: values.tenancy_ocid,
        user_ocid: values.user_ocid,
        fingerprint: values.fingerprint,
        region: values.region,
        passphrase: values.passphrase || undefined,
        // Orval types binary uploads as `string`; pass the File at runtime.
        // On edit an omitted file keeps the existing key on the server.
        private_key: values.private_key as unknown as string | undefined,
      };
      const saved =
        isEdit && initial
          ? await updateCredential(initial.id, body)
          : await createCredential(
              body as typeof body & { private_key: string },
            );
      if (!isEdit) {
        reset();
        setRegionManual(false);
      }
      onCreated?.(saved);
      onSaved?.(saved);
    } catch (err) {
      setFormError(
        isApiError(err)
          ? err.message
          : `Failed to ${isEdit ? "update" : "create"} credential.`,
      );
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
      <OciConfigPaste onParsed={applyParsed} />

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

      <Controller
        control={control}
        name="region"
        render={({ field }) => (
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="region">Region</Label>
              <button
                type="button"
                className="text-xs text-blue-600 underline"
                aria-pressed={useRegionManual}
                onClick={() => setRegionManual((m) => !m)}
              >
                {useRegionManual ? "Choose from list" : "Manual input"}
              </button>
            </div>
            {useRegionManual ? (
              <Input
                id="region"
                aria-label="Region"
                value={field.value ?? ""}
                onChange={(e) => field.onChange(e.target.value)}
              />
            ) : (
              <select
                id="region"
                aria-label="Region"
                className={REGION_SELECT_CLASS}
                value={field.value ?? ""}
                onChange={(e) => field.onChange(e.target.value)}
              >
                <option value="">Select region…</option>
                {OCI_REGIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            )}
            {errors.region && (
              <p role="alert" className="text-sm text-red-600">
                {errors.region.message as string}
              </p>
            )}
          </div>
        )}
      />

      <div className="flex flex-col gap-1">
        <Label htmlFor="passphrase">
          {isEdit ? "Passphrase (enter only to change)" : "Passphrase (optional)"}
        </Label>
        <Input id="passphrase" type="password" {...register("passphrase")} />
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="private_key">
          {isEdit ? "Private key (re-upload only to change)" : "Private key (PEM)"}
        </Label>
        <Controller
          control={control}
          name="private_key"
          render={({ field: { onChange, ref } }) => (
            <input
              id="private_key"
              type="file"
              accept=".pem,application/x-pem-file"
              ref={ref}
              onChange={(e) => onChange(e.target.files?.[0])}
            />
          )}
        />
        {errors.private_key && (
          <p role="alert" className="text-sm text-red-600">
            {errors.private_key.message as string}
          </p>
        )}
      </div>

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
            : "Create credential"}
      </Button>
    </form>
  );
}
