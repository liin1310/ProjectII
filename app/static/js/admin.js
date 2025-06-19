document.querySelector("#search-form").addEventListener("submit", function (e) {
  const categorySelect = document.querySelector('select[name="category"]');
  if (!categorySelect.value) {
    e.preventDefault();
    alert("Vui lòng chọn ít nhất một danh mục!");
  }
});
