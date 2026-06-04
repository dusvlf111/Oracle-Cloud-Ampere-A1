// Re-export the Orval-generated user/session hooks as the user entity's
// data-access API (FSD: entities own their server contract).
export {
  useMeApiAuthMeGet as useMe,
  meApiAuthMeGet as fetchMe,
  getMeApiAuthMeGetQueryKey as meQueryKey,
} from "@/shared/api/auth/auth";

export {
  useListUsersApiUsersGet as useUsers,
  listUsersApiUsersGet as fetchUsers,
  getListUsersApiUsersGetQueryKey as usersQueryKey,
  approveUserApiUsersUserIdApprovePost as approveUser,
  rejectUserApiUsersUserIdRejectPost as rejectUser,
  disableUserApiUsersUserIdDisablePost as disableUser,
  enableUserApiUsersUserIdEnablePost as enableUser,
} from "@/shared/api/users/users";
