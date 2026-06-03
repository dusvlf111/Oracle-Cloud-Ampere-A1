"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/shared";

import { logout } from "../model/logout";

export interface LogoutButtonProps {
  /** Called after the session is cleared (e.g. router.replace('/login')). */
  onSuccess?: () => void;
}

export function LogoutButton({ onSuccess }: LogoutButtonProps) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      // Invalidate the cached session ("me") so guards refetch.
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      onSuccess?.();
    },
  });

  return (
    <Button
      variant="outline"
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      {mutation.isPending ? "Signing out..." : "Sign out"}
    </Button>
  );
}
