"use client";

/**
 * Drag-and-drop / tap-to-choose media upload with client-side type, size and duration checks.
 * When a test exists the file uploads immediately (XMLHttpRequest, progress shown); before that,
 * files are queued in memory and uploaded when the draft is created on the server.
 */
import { FileVideo, Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useApiError } from "@/hooks/use-api-error";
import { upload } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/format";
import { IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS, VIDEO_TYPES } from "@/lib/schemas";
import type { AssetOut } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface QueuedFile {
  id: string;
  file: File;
  previewUrl: string;
  kind: "image" | "video";
  durationS: number | null;
  width: number | null;
  height: number | null;
}

export type UploadCheckError = "type" | "image_size" | "video_size" | "video_length";

function probe(file: File, url: string): Promise<Pick<QueuedFile, "durationS" | "width" | "height">> {
  return new Promise((resolve) => {
    if (file.type.startsWith("video/")) {
      const v = document.createElement("video");
      v.preload = "metadata";
      v.onloadedmetadata = () =>
        resolve({ durationS: v.duration, width: v.videoWidth, height: v.videoHeight });
      v.onerror = () => resolve({ durationS: null, width: null, height: null });
      v.src = url;
    } else {
      const img = new Image();
      img.onload = () => resolve({ durationS: null, width: img.naturalWidth, height: img.naturalHeight });
      img.onerror = () => resolve({ durationS: null, width: null, height: null });
      img.src = url;
    }
  });
}

export async function checkAndDescribe(
  file: File,
): Promise<{ ok: true; item: QueuedFile } | { ok: false; error: UploadCheckError }> {
  const isImage = IMAGE_TYPES.includes(file.type);
  const isVideo = VIDEO_TYPES.includes(file.type);
  if (!isImage && !isVideo) return { ok: false, error: "type" };
  if (isImage && file.size > MAX_IMAGE_BYTES) return { ok: false, error: "image_size" };
  if (isVideo && file.size > MAX_VIDEO_BYTES) return { ok: false, error: "video_size" };
  const url = URL.createObjectURL(file);
  const meta = await probe(file, url);
  if (isVideo && meta.durationS !== null && meta.durationS > MAX_VIDEO_SECONDS) {
    URL.revokeObjectURL(url);
    return { ok: false, error: "video_length" };
  }
  return {
    ok: true,
    item: {
      id: `${file.name}-${file.size}-${Date.now()}`,
      file,
      previewUrl: url,
      kind: isVideo ? "video" : "image",
      ...meta,
    },
  };
}

export function UploadDropzone({
  testId,
  assets,
  queued,
  onQueuedChange,
  onUploaded,
  onDeleteAsset,
  disabled = false,
}: {
  testId: string | null;
  assets: AssetOut[];
  queued: QueuedFile[];
  onQueuedChange: (update: (q: QueuedFile[]) => QueuedFile[]) => void;
  onUploaded: (asset: AssetOut) => void;
  onDeleteAsset: (assetId: string) => Promise<void>;
  disabled?: boolean;
}) {
  const t = useTranslations("wizard.upload");
  const msg = useApiError();
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [checkError, setCheckError] = useState<UploadCheckError | null>(null);
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [deleting, setDeleting] = useState<string | null>(null);

  const startUpload = useCallback(
    async (item: QueuedFile) => {
      if (!testId) return;
      setProgress((p) => ({ ...p, [item.id]: 0 }));
      try {
        const asset = await upload<AssetOut>(`/tests/${testId}/assets`, item.file, (pct) =>
          setProgress((p) => ({ ...p, [item.id]: pct })),
        );
        onUploaded(asset);
        onQueuedChange((q) => q.filter((x) => x.id !== item.id));
        URL.revokeObjectURL(item.previewUrl);
      } catch (e) {
        setUploadError(e);
        onQueuedChange((q) => q.filter((x) => x.id !== item.id));
      } finally {
        setProgress((p) => {
          const { [item.id]: _removed, ...rest } = p;
          return rest;
        });
      }
    },
    [testId, onUploaded, onQueuedChange],
  );

  const addFiles = useCallback(
    async (files: FileList | File[]) => {
      setCheckError(null);
      setUploadError(null);
      const list = Array.from(files);
      const accepted: QueuedFile[] = [];
      for (const f of list) {
        const r = await checkAndDescribe(f);
        if (r.ok) accepted.push(r.item);
        else setCheckError(r.error);
      }
      if (accepted.length === 0) return;
      onQueuedChange((q) => [...q, ...accepted]);
      if (testId) for (const item of accepted) void startUpload(item);
    },
    [testId, onQueuedChange, startUpload],
  );

  useEffect(() => () => queued.forEach((q) => URL.revokeObjectURL(q.previewUrl)), []); // eslint-disable-line react-hooks/exhaustive-deps -- revoke on unmount only

  const removeQueued = (id: string) => {
    const item = queued.find((q) => q.id === id);
    if (item) URL.revokeObjectURL(item.previewUrl);
    onQueuedChange((q) => q.filter((x) => x.id !== id));
  };

  const deleteAsset = async (id: string) => {
    setDeleting(id);
    try {
      await onDeleteAsset(id);
    } catch (e) {
      setUploadError(e);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        aria-label={t("dropzoneLabel")}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!disabled && e.dataTransfer.files.length) void addFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors touch-target",
          drag ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <Upload className="mb-2 h-6 w-6 text-muted-foreground" aria-hidden />
        <p className="text-sm font-medium">{t("dropTitle")}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("dropHelp", {
            image: MAX_IMAGE_BYTES / 1024 / 1024,
            video: MAX_VIDEO_BYTES / 1024 / 1024,
            seconds: MAX_VIDEO_SECONDS,
          })}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={[...IMAGE_TYPES, ...VIDEO_TYPES].join(",")}
          multiple
          className="sr-only"
          disabled={disabled}
          onChange={(e) => {
            if (e.target.files?.length) void addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {checkError ? (
        <p role="alert" className="text-sm text-danger">
          {t(`errors.${checkError}`, {
            image: MAX_IMAGE_BYTES / 1024 / 1024,
            video: MAX_VIDEO_BYTES / 1024 / 1024,
            seconds: MAX_VIDEO_SECONDS,
          })}
        </p>
      ) : null}
      {uploadError ? <p className="text-sm text-danger">{msg(uploadError)}</p> : null}
      {assets.length + queued.length > 0 ? (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {assets.map((a) => (
            <li key={a.id} className="relative overflow-hidden rounded-lg border border-border">
              <div className="aspect-square bg-zinc-900">
                {a.kind === "video" ? (
                  a.url ? (
                    <video
                      src={a.url}
                      className="h-full w-full object-contain"
                      muted
                      playsInline
                      aria-label={t("videoPreview")}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-zinc-400">
                      <FileVideo aria-hidden />
                    </div>
                  )
                ) : a.url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- user asset served by the API host
                  <img src={a.url} alt="" className="h-full w-full object-contain" />
                ) : null}
              </div>
              <div className="flex items-center justify-between gap-2 p-2 text-xs">
                <span className="truncate text-muted-foreground">
                  {a.kind === "video" ? `${formatDuration(a.duration_s)} · ` : ""}
                  {a.width && a.height ? `${a.width}×${a.height} · ` : ""}
                  {formatBytes(a.size_bytes)}
                </span>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={t("remove")}
                  disabled={disabled || deleting === a.id}
                  onClick={() => deleteAsset(a.id)}
                  className="h-8 w-8"
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            </li>
          ))}
          {queued.map((q) => (
            <li key={q.id} className="relative overflow-hidden rounded-lg border border-dashed border-border">
              <div className="aspect-square bg-zinc-900">
                {q.kind === "video" ? (
                  <video
                    src={q.previewUrl}
                    className="h-full w-full object-contain"
                    muted
                    playsInline
                    aria-label={t("videoPreview")}
                  />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element -- local object URL
                  <img src={q.previewUrl} alt="" className="h-full w-full object-contain" />
                )}
              </div>
              <div className="space-y-1 p-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-muted-foreground">
                    {q.kind === "video" && q.durationS ? `${formatDuration(q.durationS)} · ` : ""}
                    {formatBytes(q.file.size)}
                  </span>
                  {progress[q.id] === undefined ? (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label={t("remove")}
                      onClick={() => removeQueued(q.id)}
                      className="h-8 w-8"
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  ) : null}
                </div>
                {progress[q.id] !== undefined ? (
                  <div className="flex items-center gap-2">
                    <Progress
                      value={progress[q.id]}
                      className="h-1.5"
                      aria-label={t("uploading", { pct: progress[q.id] })}
                    />
                    <span className="tabular">{progress[q.id]}%</span>
                  </div>
                ) : !testId ? (
                  <p className="text-muted-foreground">{t("queued")}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
