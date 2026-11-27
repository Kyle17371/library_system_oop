document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-confirm]");
  if (button && !confirm(button.dataset.confirm)) event.preventDefault();
});
function requestCopy(button) {
  const form = button.closest("form");
  const copyId = form.querySelector("select").value;
  if (!copyId) { alert("Choose a physical copy first."); return; }
  form.action = "/borrow/" + copyId;
  form.onsubmit = null;
  form.submit();
}
