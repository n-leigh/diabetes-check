(() => {
  const trigger = document.getElementById("terms-link");
  const dialog = document.getElementById("terms-dialog");
  const checkbox = document.querySelector('input[name="consent"][value="1"]');
  const agreeButton = document.getElementById("terms-agree");

  if (!trigger || !dialog || !checkbox || !agreeButton || typeof dialog.showModal !== "function") {
    return;
  }

  let focusAfterClose = trigger;

  const closeDialog = (focusTarget = trigger) => {
    focusAfterClose = focusTarget;
    if (dialog.open) {
      dialog.close();
    }
  };

  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    if (!dialog.open) {
      focusAfterClose = trigger;
      document.documentElement.classList.add("terms-dialog-open");
      dialog.showModal();
    }
  });

  trigger.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (!dialog.open) {
        focusAfterClose = trigger;
        document.documentElement.classList.add("terms-dialog-open");
        dialog.showModal();
      }
    }
  });

  dialog.querySelectorAll("[data-terms-close]").forEach((button) => {
    button.addEventListener("click", () => closeDialog());
  });

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDialog();
  });

  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
    }
  });

  dialog.addEventListener("close", () => {
    document.documentElement.classList.remove("terms-dialog-open");
    focusAfterClose.focus();
    focusAfterClose = trigger;
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      closeDialog();
    }
  });

  agreeButton.addEventListener("click", () => {
    checkbox.checked = true;
    closeDialog(checkbox);
  });
})();
