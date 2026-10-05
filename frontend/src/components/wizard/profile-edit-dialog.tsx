"use client";

/** "Edit for this ad": edit the preset's answers, then choose how to save (5.3). */
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import {
  initialProfileData,
  missingRequired,
  ProfileForm,
  type ProfileData,
} from "@/components/profile/profile-form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useCategory } from "@/lib/queries";
import type { ProfileOut } from "@/lib/types";
import type { ProfileChoice } from "@/lib/wizard-draft";

type Mode = ProfileChoice["mode"];

export function ProfileEditDialog({
  open,
  onOpenChange,
  profile,
  initialChanges,
  onSave,
  saving = false,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  profile: ProfileOut;
  initialChanges: Record<string, unknown>;
  onSave: (choice: ProfileChoice) => Promise<void>;
  saving?: boolean;
}) {
  const t = useTranslations("wizard.preset.editDialog");
  const tv = useTranslations("validation");
  const template = useCategory(profile.category_code);
  const [data, setData] = useState<ProfileData>({});
  const [stage, setStage] = useState<"edit" | "mode">("edit");
  const [mode, setMode] = useState<Mode>("one_time");
  const [newName, setNewName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setData(initialProfileData(template.data, { ...(profile.data as ProfileData), ...initialChanges }));
      setStage("edit");
      setMode("one_time");
      setNewName(t("newPresetDefault", { name: profile.name }));
      setErrors({});
    }
  }, [open, template.data, profile, initialChanges, t]);

  /** Only keys whose value differs from the preset are sent as `changes`. */
  const diff = (): Record<string, unknown> => {
    const base = profile.data as ProfileData;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(data)) if (JSON.stringify(base[k]) !== JSON.stringify(v)) out[k] = v;
    return out;
  };

  const next = () => {
    const missing = missingRequired(template.data, data);
    if (missing.length) {
      setErrors(Object.fromEntries(missing.map((k) => [k, tv("required")])));
      return;
    }
    setErrors({});
    setStage("mode");
  };

  const save = async () => {
    await onSave({
      profile_id: profile.id,
      mode,
      changes: diff(),
      new_preset_name: mode === "new_preset" ? newName : null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{stage === "edit" ? t("title", { name: profile.name }) : t("howToSave")}</DialogTitle>
          <DialogDescription>{stage === "edit" ? t("description") : t("howToSaveBody")}</DialogDescription>
        </DialogHeader>
        {stage === "edit" ? (
          template.data ? (
            <ProfileForm template={template.data} data={data} onChange={setData} errors={errors} />
          ) : (
            <PageSkeleton rows={2} />
          )
        ) : (
          <div className="space-y-4">
            <RadioGroup value={mode} onValueChange={(v) => setMode(v as Mode)}>
              {(["one_time", "update_preset", "new_preset"] as Mode[]).map((m) => (
                <label
                  key={m}
                  className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 ${mode === m ? "border-primary bg-primary/5" : "border-border"}`}
                >
                  <RadioGroupItem value={m} id={`mode-${m}`} className="mt-0.5" />
                  <span>
                    <span className="block text-sm font-medium">{t(`modes.${m}.title`)}</span>
                    <span className="block text-xs text-muted-foreground">{t(`modes.${m}.body`)}</span>
                  </span>
                </label>
              ))}
            </RadioGroup>
            {mode === "new_preset" ? (
              <FormField id="new_preset_name" label={t("newPresetName")} required>
                <Input
                  id="new_preset_name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  maxLength={120}
                />
              </FormField>
            ) : null}
          </div>
        )}
        <DialogFooter>
          {stage === "mode" ? (
            <Button variant="outline" onClick={() => setStage("edit")} disabled={saving}>
              {t("back")}
            </Button>
          ) : (
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t("cancel")}
            </Button>
          )}
          {stage === "edit" ? (
            <Button onClick={next} disabled={!template.data}>
              {t("continue")}
            </Button>
          ) : (
            <Button onClick={save} loading={saving} disabled={mode === "new_preset" && !newName.trim()}>
              {t("save")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
