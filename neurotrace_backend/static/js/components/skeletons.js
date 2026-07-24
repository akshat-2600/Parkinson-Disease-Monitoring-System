/* ============================================================
   js/components/skeletons.js — Skeleton loader HTML builders
   ============================================================ */

const Skeletons = (() => {

  function dashboardSkeleton() {
    return `
      <div class="skeleton skeleton-card mb-4" style="height:110px"></div>
      <div class="grid-4 section-gap">
        <div class="skeleton skeleton-card" style="height:100px"></div>
        <div class="skeleton skeleton-card" style="height:100px"></div>
        <div class="skeleton skeleton-card" style="height:100px"></div>
        <div class="skeleton skeleton-card" style="height:100px"></div>
      </div>
      <div class="grid-2 section-gap">
        <div class="skeleton skeleton-card" style="height:260px"></div>
        <div class="skeleton skeleton-card" style="height:260px"></div>
      </div>
      <div class="skeleton skeleton-card" style="height:220px;margin-bottom:20px"></div>
      <div class="grid-2">
        <div class="skeleton skeleton-card" style="height:200px"></div>
        <div class="skeleton skeleton-card" style="height:200px"></div>
      </div>`;
  }

  function explanationSkeleton() {
    return `
      <div class="grid-2 section-gap">
        <div class="skeleton skeleton-card" style="height:260px"></div>
        <div class="skeleton skeleton-card" style="height:260px"></div>
      </div>
      <div class="grid-2 section-gap">
        <div class="skeleton skeleton-card" style="height:220px"></div>
        <div class="skeleton skeleton-card" style="height:220px"></div>
      </div>
      <div class="skeleton skeleton-card" style="height:120px"></div>`;
  }

  function recommendationsSkeleton() {
    return Array.from({ length: 4 }, () =>
      `<div class="skeleton skeleton-card" style="height:130px"></div>`
    ).join('');
  }

  function historySkeleton() {
    return `
      <div class="skeleton skeleton-card section-gap" style="height:240px"></div>
      <div class="grid-2 section-gap">
        <div class="skeleton skeleton-card" style="height:200px"></div>
        <div class="skeleton skeleton-card" style="height:200px"></div>
      </div>
      <div class="skeleton skeleton-card" style="height:200px"></div>`;
  }

  return { dashboardSkeleton, explanationSkeleton, recommendationsSkeleton, historySkeleton };
})();
