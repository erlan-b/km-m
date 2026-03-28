import { type MouseEvent, type ReactNode, useEffect, useState } from "react";

import { usePageI18n } from "../../app/i18n/I18nContext";

type ModalProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
};

export function Modal({ open, title, subtitle, onClose, children }: ModalProps) {
  const { t } = usePageI18n("common");
  const [isMounted, setIsMounted] = useState(open);
  const [isOpenState, setIsOpenState] = useState(false);

  useEffect(() => {
    let mountFrame = 0;
    let openFrame = 0;
    let closeFrame = 0;
    let closeTimer = 0;

    if (open) {
      mountFrame = window.requestAnimationFrame(() => {
        setIsMounted(true);
        openFrame = window.requestAnimationFrame(() => {
          setIsOpenState(true);
        });
      });
      return () => {
        window.cancelAnimationFrame(mountFrame);
        window.cancelAnimationFrame(openFrame);
      };
    }

    closeFrame = window.requestAnimationFrame(() => {
      setIsOpenState(false);
    });
    closeTimer = window.setTimeout(() => {
      setIsMounted(false);
    }, 180);

    return () => {
      window.cancelAnimationFrame(closeFrame);
      window.clearTimeout(closeTimer);
    };
  }, [open]);

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMounted]);

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

  if (!isMounted) {
    return null;
  }

  const onBackdropClick = () => {
    onClose();
  };

  const onDialogClick = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  return (
    <div className={`app-modal-backdrop${isOpenState ? " is-open" : ""}`} role="presentation" onClick={onBackdropClick}>
      <section
        className={`app-modal${isOpenState ? " is-open" : ""}`}
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
            {t("close", "Close")}
          </button>
        </header>

        <div className="app-modal-body">
          {children}
        </div>
      </section>
    </div>
  );
}
