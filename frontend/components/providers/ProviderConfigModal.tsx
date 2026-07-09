"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { Modal } from "@/components/ui/Modal";
import { api, type ProviderConfig, type ProviderParamField } from "@/lib/api";
import { requiredFeaturesForProvider } from "@/lib/providerMetadata";

function paramValueToString(value: unknown, field: ProviderParamField): string {
  if (field.type === "bool") return value ? "true" : "false";
  if (value == null) return "";
  return String(value);
}

function parseParamValue(raw: string, field: ProviderParamField): unknown {
  if (field.type === "bool") return raw === "true";
  if (field.type === "int") return parseInt(raw, 10);
  return parseFloat(raw);
}

function resolveParamFields(provider: ProviderConfig): ProviderParamField[] {
  if (provider.param_fields && provider.param_fields.length > 0) {
    return provider.param_fields;
  }
  return Object.keys(provider.params).map((key) => ({
    key,
    label: key.replace(/_/g, " "),
    type: "float" as const,
    description: "",
  }));
}

type ProviderConfigModalProps = {
  provider: ProviderConfig;
  open: boolean;
  onClose: () => void;
};

export function ProviderConfigModal({
  provider,
  open,
  onClose,
}: ProviderConfigModalProps) {
  const qc = useQueryClient();
  const paramFields = resolveParamFields(provider);
  const featureChips = requiredFeaturesForProvider(provider.provider_id);
  const [weight, setWeight] = useState(String(provider.weight));
  const [params, setParams] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setWeight(String(provider.weight));
    const next: Record<string, string> = {};
    for (const field of resolveParamFields(provider)) {
      next[field.key] = paramValueToString(provider.params[field.key], field);
    }
    setParams(next);
  }, [provider, open]);

  const save = useMutation({
    mutationFn: () => {
      const parsed: Record<string, unknown> = {};
      for (const field of paramFields) {
        parsed[field.key] = parseParamValue(params[field.key] ?? "", field);
      }
      return api.patchProvider(provider.provider_id, {
        weight: parseFloat(weight),
        params: parsed,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      onClose();
    },
  });

  const reset = useMutation({
    mutationFn: () => api.resetProvider(provider.provider_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
    },
  });

  const isDirty =
    parseFloat(weight) !== provider.weight ||
    paramFields.some(
      (field) =>
        params[field.key] !==
        paramValueToString(provider.params[field.key], field),
    );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={provider.name ?? provider.provider_id.replace(/_/g, " ")}
      subtitle={provider.summary}
    >
      <div className="space-y-6">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted">
            Required features
          </p>
          <div className="flex flex-wrap gap-1">
            {featureChips.map((f) => (
              <span
                key={f}
                className="rounded bg-[var(--background)] px-2 py-0.5 font-mono text-[10px] text-muted"
              >
                {f}
              </span>
            ))}
          </div>
        </div>

        {provider.rules?.length ? (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted">
              Signal logic
            </p>
            <ol className="list-decimal space-y-1.5 pl-5 text-sm text-muted">
              {provider.rules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ol>
          </div>
        ) : null}

        <div>
          <FieldLabel label="Weight" />
          <input
            type="number"
            min={0}
            step={0.1}
            className="input-field mt-2"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {paramFields.map((field) => (
            <div key={field.key}>
              <FieldLabel label={field.label} tooltip={field.description} />
              {field.type === "bool" ? (
                <select
                  className="input-field mt-2"
                  value={params[field.key] ?? "false"}
                  onChange={(e) =>
                    setParams((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                >
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : (
                <input
                  type="number"
                  className="input-field mt-2"
                  value={params[field.key] ?? ""}
                  min={field.min ?? undefined}
                  max={field.max ?? undefined}
                  step={field.step ?? (field.type === "int" ? 1 : 0.01)}
                  onChange={(e) =>
                    setParams((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                />
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 border-t border-[var(--border)] pt-4">
          <button
            type="button"
            className="btn-primary text-xs"
            onClick={() => save.mutate()}
            disabled={save.isPending || !isDirty}
          >
            {save.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            {save.isPending ? "Saving…" : "Save changes"}
          </button>
          <button
            type="button"
            className="btn-secondary text-xs"
            onClick={() => reset.mutate()}
            disabled={reset.isPending}
          >
            {reset.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RotateCcw className="h-3.5 w-3.5" />
            )}
            {reset.isPending ? "Resetting…" : "Reset to defaults"}
          </button>
          <button
            type="button"
            className="btn-secondary text-xs"
            onClick={onClose}
          >
            Cancel
          </button>
        </div>

        {save.error ? (
          <p className="text-sm text-danger">
            {save.error instanceof Error
              ? save.error.message
              : "Failed to save"}
          </p>
        ) : null}
        {reset.error ? (
          <p className="text-sm text-danger">
            {reset.error instanceof Error
              ? reset.error.message
              : "Failed to reset"}
          </p>
        ) : null}
        {reset.isSuccess ? (
          <p className="text-sm text-[var(--success)]">
            Restored default parameters.
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
