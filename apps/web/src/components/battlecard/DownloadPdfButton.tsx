"use client";

import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getPdfUrl } from "@/lib/api";

export function DownloadPdfButton({ runId, disabled }: { runId?: string; disabled?: boolean }) {
  if (!runId) {
    return <Button disabled>PDF unavailable</Button>;
  }

  return (
    <Button
      variant="secondary"
      disabled={disabled}
      onClick={() => {
        window.open(getPdfUrl(runId), "_blank", "noopener,noreferrer");
      }}
    >
      <Download className="mr-2 h-4 w-4" /> Download PDF
    </Button>
  );
}
