// Sync Lean proof body visibility with LaTeX proof toggle
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.sbs-container').forEach(function(container) {
    var expandIcon = container.querySelector('.expand-proof');
    var leanProofBody = container.querySelector('.lean-proof-body');

    if (!expandIcon || !leanProofBody) return;

    // Watch for plastex.js changing the expand icon text (▶ ↔ ▼)
    var observer = new MutationObserver(function() {
      // ▼ means expanded, ▶ means collapsed
      var isExpanded = expandIcon.textContent.trim() === '▼';
      leanProofBody.style.display = isExpanded ? 'inline' : 'none';
    });

    observer.observe(expandIcon, { childList: true, characterData: true, subtree: true });
  });
});
