(function () {
  var countdowns = document.querySelectorAll("[data-auction-countdown]");

  countdowns.forEach(function (countdown) {
    var endTime = Date.parse(countdown.dataset.auctionEnds);
    if (!Number.isFinite(endTime)) return;

    function updateCountdown() {
      var remaining = endTime - Date.now();
      if (remaining <= 0) {
        countdown.textContent = "Auction ended";
        return false;
      }

      var totalSeconds = Math.floor(remaining / 1000);
      var hours = Math.floor(totalSeconds / 3600);
      var minutes = Math.floor((totalSeconds % 3600) / 60);
      var seconds = totalSeconds % 60;
      countdown.textContent =
        "Ends in " + hours + "h " + minutes + "m " + seconds + "s";
      return true;
    }

    if (updateCountdown()) {
      var timer = window.setInterval(function () {
        if (!updateCountdown()) {
          window.clearInterval(timer);
          window.location.reload();
        }
      }, 1000);
    }
  });
})();
