import { z } from "zod";

/** Credential creation form (PRD §7.1). `private_key` is a PEM file upload. */
export const credentialCreateSchema = z.object({
  name: z.string().min(1, "Name is required"),
  tenancy_ocid: z.string().min(1, "Tenancy OCID is required"),
  user_ocid: z.string().min(1, "User OCID is required"),
  fingerprint: z.string().min(1, "Fingerprint is required"),
  region: z.string().min(1, "Region is required"),
  passphrase: z.string().optional(),
  private_key: z
    .instanceof(File, { message: "Private key file is required" })
    .refine((f) => f.size > 0, "Private key file is required"),
});

export type CredentialCreateValues = z.infer<typeof credentialCreateSchema>;
