import { type MouseEvent, useEffect } from "react";

type ImagePreviewOverlayProps = {
  open: boolean;
  imageSrc: string | null;
  imageAlt: string;
  onClose: () => void;
  onDownload: () => void;
  downloadLabel: string;
  downloadingLabel: string;
  closeLabel: string;
  isDownloading: boolean;
};

export function ImagePreviewOverlay({
  open,
  imageSrc,
  imageAlt,
  onClose,
  onDownload,
  downloadLabel,
  downloadingLabel,
  closeLabel,
  isDownloading,
}: ImagePreviewOverlayProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open || !imageSrc) {
    return null;
  }

  const stopPropagation = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  return (
    <div className="image-preview-overlay" role="presentation" onClick={onClose}>
      <div className="image-preview-toolbar" onClick={stopPropagation}>
        <button type="button" className="btn btn-primary" onClick={onDownload} disabled={isDownloading}>
          {isDownloading ? downloadingLabel : downloadLabel}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          {closeLabel}
        </button>
      </div>

      <section
        className="image-preview-canvas"
        role="dialog"
        aria-modal="true"
        aria-label={imageAlt}
        onClick={stopPropagation}
      >
        <img className="image-preview-image" src={imageSrc} alt={imageAlt} />
      </section>
    </div>
  );
}
