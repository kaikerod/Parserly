"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { FileText, ShieldCheck, UploadCloud, XCircle } from "lucide-react";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
];

interface DropzoneProps {
  disabled?: boolean;
  selectedFile?: File | null;
  onFileAccepted: (file: File) => void;
}

export function Dropzone({ disabled = false, selectedFile, onFileAccepted }: DropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function handleFile(file: File | undefined) {
    if (!file || disabled) {
      return;
    }

    const validationError = validateResumeFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    onFileAccepted(file);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFile(event.target.files?.[0]);
    event.target.value = "";
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }

  function handleDragLeave(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleFile(event.dataTransfer.files?.[0]);
  }

  return (
    <div className="space-y-4">
      <label
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          "focus-ring group panel-grid flex min-h-[18rem] cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-8 text-center transition",
          isDragging
            ? "border-acid bg-acid/10 shadow-panel"
            : "border-line bg-night/40 hover:border-acid/70 hover:bg-night/60",
          disabled ? "pointer-events-none opacity-70" : ""
        ].join(" ")}
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <input
          ref={inputRef}
          className="sr-only"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={handleInputChange}
          disabled={disabled}
        />

        <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-md border border-acid/30 bg-acid text-ink shadow-tool transition group-hover:-translate-y-1">
          <UploadCloud className="h-7 w-7" aria-hidden="true" />
        </div>

        <div className="max-w-md space-y-2">
          <p className="font-display text-2xl font-semibold leading-tight text-paper">
            Solte seu currículo aqui
          </p>
          <p className="text-sm leading-6 text-paper/60">
            Aceitamos PDF ou DOCX até 5 MB. A validação acontece antes do envio.
          </p>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-xs font-semibold uppercase text-paper/60">
          <span className="rounded-md border border-line/70 bg-graphite px-3 py-1">PDF</span>
          <span className="rounded-md border border-line/70 bg-graphite px-3 py-1">DOCX</span>
          <span className="rounded-md border border-line/70 bg-graphite px-3 py-1">5 MB</span>
        </div>
      </label>

      {selectedFile ? (
        <div className="flex items-start gap-3 rounded-md border border-line/70 bg-night px-4 py-3 shadow-tool">
          <FileText className="mt-0.5 h-5 w-5 shrink-0 text-acid" aria-hidden="true" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-paper">{selectedFile.name}</p>
            <p className="text-xs text-paper/55">{formatFileSize(selectedFile.size)}</p>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="flex items-start gap-3 rounded-md border border-coral/35 bg-coral/10 px-4 py-3 text-sm text-paper">
          <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden="true" />
          <p>{error}</p>
        </div>
      ) : (
        <div className="flex items-start gap-3 text-sm text-paper/60">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-teal" aria-hidden="true" />
          <p>O arquivo é enviado apenas quando passa pelas regras de formato e tamanho.</p>
        </div>
      )}
    </div>
  );
}

function validateResumeFile(file: File): string | null {
  const fileName = file.name.toLowerCase();
  const hasAcceptedExtension = ACCEPTED_EXTENSIONS.some((extension) =>
    fileName.endsWith(extension)
  );
  const hasAcceptedMimeType = ACCEPTED_MIME_TYPES.includes(file.type);

  if (!hasAcceptedExtension || (file.type && !hasAcceptedMimeType)) {
    return "Formato inválido. Envie um currículo em PDF ou DOCX.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "Arquivo muito grande. O limite máximo é 5 MB.";
  }

  return null;
}

function formatFileSize(size: number) {
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}
