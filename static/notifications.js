const button = document.getElementById("setup-button");
if (button) {
  button.addEventListener("click", () => {
    document.getElementById("setup-form").hidden = false;
    button.setAttribute("aria-expanded", "true");
    document.getElementById("token").focus();
  });
}
