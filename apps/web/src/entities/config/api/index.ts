// Re-export the Orval-generated config hooks/functions as the config entity's
// data-access API.
export {
  useListConfigsApiConfigsGet as useConfigs,
  listConfigsApiConfigsGet as fetchConfigs,
  createConfigApiConfigsPost as createConfig,
  updateConfigApiConfigsConfigIdPut as updateConfig,
  deleteConfigApiConfigsConfigIdDelete as deleteConfig,
  toggleConfigApiConfigsConfigIdTogglePost as toggleConfig,
  getListConfigsApiConfigsGetQueryKey as configsQueryKey,
} from "@/shared/api/configs/configs";
