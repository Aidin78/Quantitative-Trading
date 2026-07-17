import type { CausalGraph, TimelineEntry } from "@/lib/api";

export function buildGraphTree(
  graph: CausalGraph | undefined,
  timeline: TimelineEntry[],
): Array<{ node: CausalGraph["nodes"][0]; depth: number }> {
  if (!graph?.nodes.length) {
    return timeline.map((e, i) => ({
      node: {
        id: e.event_id ?? `t-${i}`,
        event_type: String(e.event_type),
        event_family: String(e.event_family ?? ""),
        event_time: String(e.event_time),
      },
      depth: i,
    }));
  }
  const children: Record<string, string[]> = {};
  for (const edge of graph.edges) {
    children[edge.from] = children[edge.from] ?? [];
    children[edge.from].push(edge.to);
  }
  const byId = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
  const visited = new Set<string>();
  const result: Array<{ node: CausalGraph["nodes"][0]; depth: number }> = [];

  function walk(id: string, depth: number) {
    if (visited.has(id)) return;
    visited.add(id);
    const node = byId[id];
    if (node) result.push({ node, depth });
    for (const child of children[id] ?? []) {
      walk(child, depth + 1);
    }
  }

  const roots = graph.roots.length ? graph.roots : graph.nodes.map((n) => n.id);
  for (const root of roots) {
    walk(root, 0);
  }
  for (const node of graph.nodes) {
    if (!visited.has(node.id)) {
      result.push({ node, depth: 0 });
    }
  }
  return result;
}
