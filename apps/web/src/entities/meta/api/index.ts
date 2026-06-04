// Re-export the Orval-generated OCI meta lookup hooks as the meta entity's
// data-access API (PRD §7.2, §8 /api/meta/*). Features import these via the
// slice barrel so the generated module path stays an implementation detail.
export {
  useListAvailabilityDomainsApiMetaAvailabilityDomainsGet as useAvailabilityDomains,
  useListImagesApiMetaImagesGet as useImages,
  useListSubnetsApiMetaSubnetsGet as useSubnets,
} from "@/shared/api/meta/meta";
