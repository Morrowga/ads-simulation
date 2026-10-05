"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import type { LiveComment } from "@/lib/sse";
import { titleCase } from "@/lib/format";

const TOPIC_VARIANT: Record<string, "success" | "danger" | "info" | "warning" | "neutral"> = {
  positive: "success",
  negative: "danger",
  price: "warning",
  product_detail: "info",
  service: "info",
  other: "neutral",
};

export function TopicChip({ topic }: { topic: string | null }) {
  const t = useTranslations("topics");
  if (!topic) return null;
  const key = topic in TOPIC_VARIANT ? topic : "other";
  return <Badge variant={TOPIC_VARIANT[key]}>{t.has(topic) ? t(topic as never) : titleCase(topic)}</Badge>;
}

/** Virtual comments, newest first, with archetype label and topic chip. Comments are in English with a language-group label. */
export function LiveComments({ comments }: { comments: LiveComment[] }) {
  const t = useTranslations("live.comments");
  if (comments.length === 0) return <p className="text-sm text-muted-foreground">{t("waiting")}</p>;
  return (
    <ul className="space-y-2" aria-label={t("label")}>
      {comments.map((c) => (
        <li key={c.id} className="rounded-md border border-border p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{c.archetype}</span>
            {c.language_group && !/speaking/i.test(c.archetype) ? (
              <span>· {t("speaking", { group: c.language_group })}</span>
            ) : null}
            {c.platform ? <span>· {titleCase(c.platform)}</span> : null}
            <span className="ml-auto">
              <TopicChip topic={c.topic} />
            </span>
          </div>
          <p className="mt-1">{c.text}</p>
        </li>
      ))}
    </ul>
  );
}
