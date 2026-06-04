import { z } from "zod";

/**
 * Credential form schema (PRD §7.1). `private_key` is a PEM file upload.
 *
 * On create the key file is required; on edit it is optional (omitting it keeps
 * the existing key on the server). The form selects the schema by `mode`.
 */
const baseShape = {
  name: z.string().min(1, "Name is required"),
  tenancy_ocid: z.string().min(1, "Tenancy OCID is required"),
  user_ocid: z.string().min(1, "User OCID is required"),
  fingerprint: z.string().min(1, "Fingerprint is required"),
  region: z.string().min(1, "Region is required"),
  passphrase: z.string().optional(),
};

export const credentialCreateSchema = z.object({
  ...baseShape,
  private_key: z
    .instanceof(File, { message: "Private key file is required" })
    .refine((f) => f.size > 0, "Private key file is required"),
});

/** Edit variant: the key file is optional (kept if not re-uploaded). */
export const credentialEditSchema = z.object({
  ...baseShape,
  private_key: z.instanceof(File).optional(),
});

export type CredentialCreateValues = z.infer<typeof credentialCreateSchema>;
export type CredentialEditValues = z.infer<typeof credentialEditSchema>;
/** Shared union the form component uses (edit is the looser superset). */
export type CredentialFormValues = z.infer<typeof credentialEditSchema>;
