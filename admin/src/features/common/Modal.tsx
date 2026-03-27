import { type MouseEvent, type ReactNode, useEffect } from "react";

type ModalProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
};

export function Modal({ open, title, subtitle, onClose, children }: ModalProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const onBackdropClick = () => {
    onClose();
  };

  const onDialogClick = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  return (
    <div className="app-modal-backdrop" role="presentation" onClick={onBackdropClick}>
      <section
        className="app-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={onDialogClick}
      >
        <header className="app-modal-head">
          <div>
            <strong>{title}</strong>
            {subtitle ? <span>{subtitle}</span> : null}
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </header>

        <div className="app-modal-body">
          {children}
        </div>
      </section>
    </div>
  );
}
