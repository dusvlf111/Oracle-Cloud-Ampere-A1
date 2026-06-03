"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { configsQueryKey, toggleConfig, type Config } from "@/entities/config";

/**
 * Toggle a config's `enabled` flag with an optimistic cache update.
 *
 * - `onMutate` flips `enabled` for the target config in the cached list so the
 *   UI reacts instantly.
 * - `onError` rolls back to the snapshot.
 * - `onSettled` invalidates the configs query so the server state wins.
 */
export function useToggleConfig() {
  const queryClient = useQueryClient();
  const key = configsQueryKey();

  return useMutation({
    mutationFn: (configId: number) => toggleConfig(configId),
    onMutate: async (configId: number) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Config[]>(key);
      queryClient.setQueryData<Config[]>(key, (old) =>
        (old ?? []).map((c) =>
          c.id === configId ? { ...c, enabled: !c.enabled } : c,
        ),
      );
      return { previous };
    },
    onError: (_err, _configId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(key, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
}
