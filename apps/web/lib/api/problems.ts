import { apiRequest } from "@/lib/api/client";

export type ProblemCluster = {
  id: string;
  canonical_title: string;
  category: string;
  occurrence_count: number;
};

export function listProblemClusters(): Promise<ProblemCluster[]> {
  return apiRequest<ProblemCluster[]>("/problems/clusters", {
    method: "GET",
    fallbackError: "list_clusters_failed",
  });
}

export function relinkOccurrenceCluster(
  occurrenceId: string,
  input: { cluster_id: string } | { new_cluster_title: string },
): Promise<ProblemCluster> {
  return apiRequest<ProblemCluster>(`/problems/occurrences/${occurrenceId}/cluster`, {
    method: "PATCH",
    body: input,
    fallbackError: "relink_cluster_failed",
  });
}
