import { z } from "zod";

/** InstanceConfig creation form (PRD §7.2 / §8 ConfigCreate). */
export const configCreateSchema = z.object({
  name: z.string().min(1, "Name is required"),
  credential_id: z.coerce.number().int().positive("Select a credential"),
  shape: z.string().min(1, "Shape is required").default("VM.Standard.A1.Flex"),
  ocpus: z.coerce.number().int().min(1).default(4),
  memory_gb: z.coerce.number().int().min(1).default(24),
  boot_volume_gb: z.coerce.number().int().min(1).default(50),
  image_ocid: z.string().min(1, "Image OCID is required"),
  subnet_ocid: z.string().min(1, "Subnet OCID is required"),
  availability_domain: z.string().min(1, "Availability domain is required"),
  ssh_public_key: z.string().min(1, "SSH public key is required"),
  retry_interval_sec: z.coerce.number().int().min(1).default(60),
  // Empty input → undefined (unbounded retries); otherwise a positive int.
  max_attempts: z.preprocess(
    (v) => (v === "" || v == null ? undefined : v),
    z.coerce.number().int().min(1).optional(),
  ),
  channel_ids: z.array(z.number().int()).default([]),
});

export type ConfigCreateValues = z.input<typeof configCreateSchema>;
export type ConfigCreateOutput = z.output<typeof configCreateSchema>;
