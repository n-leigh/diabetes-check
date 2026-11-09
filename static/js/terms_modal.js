(function () {
  "use strict";

  var dialog = document.getElementById("terms-dialog");
  var link = document.getElementById("terms-link");
  var checkbox = document.getElementById("consent");
  if (!dialog || !link || !checkbox || typeof dialog.showModal !== "function") {
    return;
  }

  var closeButton = document.getElementById("terms-dialog-close");
  var cancelButton = document.getElementById("terms-dialog-cancel");
  var agreeButton = document.getElementById("terms-dialog-agree");
  var focusTarget = link;

  function openDialog(event) {
    event.preventDefault();
    focusTarget = link;
    dialog.showModal();
    document.body.classList.add("terms-dialog-open");
  }

  function closeDialog(target) {
    focusTarget = target || link;
    if (dialog.open) {
      dialog.close();
    } else {
      focusTarget.focus();
    }
  }

  link.addEventListener("click", openDialog);
  link.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      openDialog(event);
    }
  });
  closeButton.addEventListener("click", function () {
    closeDialog(link);
  });
  cancelButton.addEventListener("click", function () {
    closeDialog(link);
  });
  agreeButton.addEventListener("click", function () {
    checkbox.checked = true;
    closeDialog(checkbox);
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) {
      closeDialog(link);
    }
  });
  dialog.addEventListener("cancel", function () {
    closeDialog(link);
  });
  dialog.addEventListener("close", function () {
    document.body.classList.remove("terms-dialog-open");
    focusTarget.focus();
  });
}());
