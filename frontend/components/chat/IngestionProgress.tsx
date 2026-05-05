"use client";

import {
  STAGE_LABELS,
  STAGE_ORDER,
  type StageEvent,
  type StageName,
} from "@/lib/types";

interface Props {
  stages: StageEvent[];
  currentStage?: StageName;
  currentStageMessage?: string;
}

export function IngestionProgress({
  stages,
  currentStage,
  currentStageMessage,
}: Props) {
  const seen = new Set(stages.map((s) => s.stage));
  const currentIdx = currentStage ? STAGE_ORDER.indexOf(currentStage) : -1;

  return (
    <div className="rounded-lg border border-base-300/60 bg-base-100/60 p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="loading loading-spinner loading-xs text-primary" />
        <span className="text-sm">
          {currentStageMessage ??
            (currentStage ? STAGE_LABELS[currentStage] : "Working...")}
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
        {STAGE_ORDER.map((stage, idx) => {
          const done = seen.has(stage) && idx < currentIdx;
          const active = stage === currentStage;
          return (
            <li
              key={stage}
              className={[
                "flex items-center gap-1.5",
                done
                  ? "text-success"
                  : active
                    ? "text-primary"
                    : "text-base-content/40",
              ].join(" ")}
            >
              <span
                className={[
                  "inline-block h-1.5 w-1.5 rounded-full",
                  done
                    ? "bg-success"
                    : active
                      ? "bg-primary animate-pulse"
                      : "bg-base-content/20",
                ].join(" ")}
              />
              {STAGE_LABELS[stage]}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
