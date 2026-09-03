import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";

interface Props {
  open: boolean;
  label: string;
  src: string | null;
  onClose: () => void;
}

/** Fullscreen 9:16 video preview. Owns its own focus trap and restores focus
 *  to the element that opened it (the still) on close. */
export function PreviewModal({ open, label, src, onClose }: Props) {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    // Remember the trigger so we can return focus on close.
    const prev = document.activeElement as HTMLElement | null;
    const raf = requestAnimationFrame(() => closeRef.current?.focus());
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && modalRef.current) {
        const focusables = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], video, [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && src && (
        <motion.div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-label={`${label} rendered video`}
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="modal-body"
            ref={modalRef}
            onClick={(e) => e.stopPropagation()}
            initial={{ scale: 0.92, y: 14 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.95, y: 8 }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
          >
            <video src={src} controls autoPlay className="modal-video" />
            <button ref={closeRef} className="btn ghost" onClick={onClose}>
              <X size={14} aria-hidden="true" /> Close
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
