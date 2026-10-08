mergeInto(LibraryManager.library, {
  DesertRVReviewReady: function() {
    document.dispatchEvent(new CustomEvent('desert-rv-review-ready'));
  }
});
