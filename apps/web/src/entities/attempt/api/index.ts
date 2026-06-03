// Re-export the Orval-generated attempts hooks as the attempt entity's
// data-access API (PRD §7.4, §8).
export {
  useListAttemptsApiAttemptsGet as useAttempts,
  listAttemptsApiAttemptsGet as fetchAttempts,
  getListAttemptsApiAttemptsGetQueryKey as attemptsQueryKey,
} from "@/shared/api/attempts/attempts";
