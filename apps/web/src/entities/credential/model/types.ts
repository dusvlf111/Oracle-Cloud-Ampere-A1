import type { CredentialRead } from "@/shared/api/schemas/credentialRead";

/** OCI credential as returned by the API (sensitive fields server-masked). */
export type Credential = CredentialRead;
