// Re-export the Orval-generated channel hooks/functions as the channel
// entity's data-access API.
export {
  useListChannelsApiChannelsGet as useChannels,
  listChannelsApiChannelsGet as fetchChannels,
  createChannelApiChannelsPost as createChannel,
  updateChannelApiChannelsChannelIdPut as updateChannel,
  deleteChannelApiChannelsChannelIdDelete as deleteChannel,
  testChannelApiChannelsChannelIdTestPost as testChannel,
  getListChannelsApiChannelsGetQueryKey as channelsQueryKey,
} from "@/shared/api/channels/channels";
