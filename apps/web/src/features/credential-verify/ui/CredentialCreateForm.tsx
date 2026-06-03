"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { Controller, useForm } from "react-hook-form";

import { createCredential, type Credential } from "@/entities/credential";
import { Button, Input, Label, isApiError } from "@/shared";

import {
  credentialCreateSchema,
  type CredentialCreateValues,
} from "../model/schema";

export interface CredentialCreateFormProps {
  onCreated?: (credential: Credential) => void;
}

const FIELDS: Array<{ name: keyof CredentialCreateValues; label: string }> = [
  { name: "name", label: "Name" },
  { name: "tenancy_ocid", label: "Tenancy OCID" },
  { name: "user_ocid", label: "User OCID" },
  { name: "fingerprint", label: "Fingerprint" },
  { name: "region", label: "Region" },
  { name: "passphrase", label: "Passphrase (optional)" },
];

/**
 * Multipart credential-creation form. Submits a `FormData` body (private key
 * file + fields) via the generated `createCredential` client, which the
 * `httpClient` mutator sends as `multipart/form-data` (PRD §8).
 */
export function CredentialCreateForm({ onCreated }: CredentialCreateFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CredentialCreateValues>({
    resolver: zodResolver(credentialCreateSchema),
    defaultValues: {
      name: "",
      tenancy_ocid: "",
      user_ocid: "",
      fingerprint: "",
      region: "",
      passphrase: "",
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const created = await createCredential({
        name: values.name,
        tenancy_ocid: values.tenancy_ocid,
        user_ocid: values.user_ocid,
        fingerprint: values.fingerprint,
        region: values.region,
        passphrase: values.passphrase || undefined,
        // Orval types binary uploads as `string`; pass the File at runtime.
        private_key: values.private_key as unknown as string,
      });
      reset();
      onCreated?.(created);
    } catch (err) {
      setFormError(
        isApiError(err) ? err.message : "Failed to create credential.",
      );
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
      {FIELDS.map(({ name, label }) => (
        <div key={name} className="flex flex-col gap-1">
          <Label htmlFor={name}>{label}</Label>
          <Input id={name} {...register(name)} />
          {errors[name] && (
            <p role="alert" className="text-sm text-red-600">
              {errors[name]?.message}
            </p>
          )}
        </div>
      ))}

      <div className="flex flex-col gap-1">
        <Label htmlFor="private_key">Private key (PEM)</Label>
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
            {errors.private_key.message}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating…" : "Create credential"}
      </Button>
    </form>
  );
}
