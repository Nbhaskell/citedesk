// While a dialog is open the page behind it must not react to keys. A flag on the document is
// enough: the single-key shortcuts check it (shortcuts.ts) and so do the Escape handlers.
const FLAG = "dialogOpen";

export function setModalOpen(open: boolean): void {
  if (open) document.documentElement.dataset[FLAG] = "true";
  else delete document.documentElement.dataset[FLAG];
}

export function modalOpen(): boolean {
  return document.documentElement.dataset[FLAG] === "true";
}
