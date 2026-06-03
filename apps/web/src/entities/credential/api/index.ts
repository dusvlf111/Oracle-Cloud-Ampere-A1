// Re-export the Orval-generated credential hooks/functions as the credential
// entity's data-access API. Features/pages import these via the slice barrel
// so the generated module path stays an implementation detail.
export {
  useListCredentialsApiCredentialsGet as useCredentials,
  createCredentialApiCredentialsPost as createCredential,
  verifyCredentialApiCredentialsCredentialIdVerifyPost as verifyCredential,
  deleteCredentialApiCredentialsCredentialIdDelete as deleteCredential,
  getListCredentialsApiCredentialsGetQueryKey as credentialsQueryKey,
} from "@/shared/api/credentials/credentials";
