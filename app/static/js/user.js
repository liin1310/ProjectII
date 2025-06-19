/////////////////////////////////////////////////////////////////////////////////////////////////////////
/////////////////////////Nav/////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////
function toggleGenres() {
  const hiddenGenres = document.querySelectorAll(".genre-item.hidden");
  const toggleIcon = document.getElementById("toggle-icon");

  hiddenGenres.forEach((genre) => {
    genre.classList.toggle("hidden");
  });

  toggleIcon.classList.toggle("fa-chevron-down");
  toggleIcon.classList.toggle("fa-chevron-up");
}
document.addEventListener("DOMContentLoaded", function () {
  const profile = document.querySelector(".user-profile");
  const icon = document.getElementById("profileIcon");

  icon.addEventListener("click", function (e) {
    e.stopPropagation();
    profile.classList.toggle("show-dropdown");
  });

  // Click ngoài để đóng
  document.addEventListener("click", function () {
    profile.classList.remove("show-dropdown");
  });
});
/////////////////////////////////////////////////////////////////////////////////////////////////////////
///////////////////////// Book /////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////
// Chia sẻ sách
function shareBook() {
  const url = window.location.href;
  const title = "{{ book.title }}";
  if (navigator.share) {
    navigator
      .share({
        title: title,
        url: url,
      })
      .catch(console.error);
  } else {
    alert(
      "Chức năng chia sẻ không được hỗ trợ trên trình duyệt này. Bạn có thể sao chép link: " +
        url
    );
  }
}
