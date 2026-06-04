/**
 * Major OCI commercial regions offered as a dropdown in the credential form.
 * Not exhaustive — the form keeps a "Manual input" toggle for the long
 * tail. `value` is the region identifier OCI expects (e.g. `ap-chuncheon-1`).
 */
export interface OciRegionOption {
  value: string;
  label: string;
}

export const OCI_REGIONS: readonly OciRegionOption[] = [
  { value: "ap-chuncheon-1", label: "Chuncheon (ap-chuncheon-1)" },
  { value: "ap-seoul-1", label: "Seoul (ap-seoul-1)" },
  { value: "ap-tokyo-1", label: "Tokyo (ap-tokyo-1)" },
  { value: "ap-osaka-1", label: "Osaka (ap-osaka-1)" },
  { value: "ap-singapore-1", label: "Singapore (ap-singapore-1)" },
  { value: "ap-mumbai-1", label: "Mumbai (ap-mumbai-1)" },
  { value: "ap-sydney-1", label: "Sydney (ap-sydney-1)" },
  { value: "us-ashburn-1", label: "Ashburn (us-ashburn-1)" },
  { value: "us-phoenix-1", label: "Phoenix (us-phoenix-1)" },
  { value: "us-sanjose-1", label: "San Jose (us-sanjose-1)" },
  { value: "ca-toronto-1", label: "Toronto (ca-toronto-1)" },
  { value: "eu-frankfurt-1", label: "Frankfurt (eu-frankfurt-1)" },
  { value: "eu-amsterdam-1", label: "Amsterdam (eu-amsterdam-1)" },
  { value: "eu-zurich-1", label: "Zurich (eu-zurich-1)" },
  { value: "uk-london-1", label: "London (uk-london-1)" },
  { value: "sa-saopaulo-1", label: "São Paulo (sa-saopaulo-1)" },
] as const;
