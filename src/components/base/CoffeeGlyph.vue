<script setup>
/**
 * The coffee vocabulary of the specimen plate, drawn as line vector.
 *
 * One component rather than eight files: they share a 32x32 frame, a single
 * stroke weight and `currentColor`, so they read as one set and recolour with
 * whatever cell they sit in. No fills — the plate is line work, and a filled
 * glyph would compete with the accent cell for attention.
 */
defineProps({
  name: {
    type: String,
    required: true,
    validator: (v) =>
      ['bean', 'cherry', 'dripper', 'moka', 'cup', 'portafilter', 'grinder', 'scale'].includes(v),
  },
})
</script>

<template>
  <svg
    class="glyph"
    viewBox="0 0 32 32"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <!-- Bean: the ellipse plus the S-shaped centre crease that makes it a
         coffee bean rather than a seed. Both sit in one rotated group so the
         crease can never drift off the body. -->
    <g v-if="name === 'bean'" transform="rotate(-30 16 16)">
      <ellipse cx="16" cy="16" rx="8" ry="11" />
      <path d="M16 5.5c-3 3.5-3 17 0 21" />
    </g>

    <!-- Cherry: the fruit the bean is picked from, stem meeting the fruit. -->
    <g v-else-if="name === 'cherry'">
      <circle cx="16" cy="19.5" r="8.5" />
      <path d="M16 11V6.5" />
      <path d="M16 7.5c2.5-3 5.5-2.5 7-2" />
    </g>

    <!-- Pour-over dripper: the cone seated directly on the carafe below it.
         Drawn touching, not floating — a cone with a gap under it reads as two
         unrelated shapes rather than one brewer. -->
    <g v-else-if="name === 'dripper'">
      <path d="M5 6h22l-8 12H13L5 6Z" />
      <path d="M9 11h14" />
      <path d="M13 18v3" />
      <path d="M10.5 21h11l-1.5 6h-8l-1.5-6Z" />
    </g>

    <!-- Moka pot: the waisted body every Iranian kitchen knows — a narrow
         upper chamber flaring into a wider base, with the handle on the right.
         The taper is the whole silhouette; drawn with parallel sides it reads
         as a tin. -->
    <g v-else-if="name === 'moka'">
      <!-- Body kept left of centre so the handle has clear air to its right;
           drawn against the outline it merges into the silhouette. -->
      <!-- Upper chamber: narrow at the lid, widening to the waist. -->
      <path d="M11 6h5l2.5 8H8.5L11 6Z" />
      <!-- Lower chamber: mirrors it, widening again to the base. -->
      <path d="M8.5 14h10l2 12H6.5l2-12Z" />
      <!-- Lid knob. -->
      <path d="M12.5 6V4h2v2" />
      <!-- Handle, standing off the body. -->
      <path d="M19 16.5c3.5.5 4 6 .5 7" />
    </g>

    <!-- Cup on a saucer, seen from the side. -->
    <g v-else-if="name === 'cup'">
      <path d="M8 11h14v7a7 7 0 0 1-14 0v-7Z" />
      <path d="M22 13h1.5a3.5 3.5 0 0 1 0 7H22" />
      <path d="M6 26h20" />
    </g>

    <!-- Portafilter, handle toward the reader: the espresso half of the shop. -->
    <g v-else-if="name === 'portafilter'">
      <path d="M6 10h20v3a5 5 0 0 1-5 5H11a5 5 0 0 1-5-5v-3Z" />
      <path d="M14 18h4l-.7 8h-2.6L14 18Z" />
      <path d="M9 7h14" />
    </g>

    <!-- Hand grinder: hopper, crank, and the catch below. -->
    <g v-else-if="name === 'grinder'">
      <path d="M10 12h12v6a6 6 0 0 1-6 6 6 6 0 0 1-6-6v-6Z" />
      <path d="M16 12V7" />
      <path d="M16 7h5" />
      <path d="M21 7v2.5" />
      <path d="M10 16h12" />
    </g>

    <!-- Scale: the brew-ratio instrument, with its readout. -->
    <g v-else>
      <rect x="5" y="12" width="22" height="12" rx="1" />
      <path d="M9 16h7" />
      <path d="M9 20h4" />
      <circle cx="22" cy="18" r="2" />
      <path d="M12 12V9h8v3" />
    </g>
  </svg>
</template>

<style scoped>
.glyph {
  inline-size: clamp(1.75rem, 4.5vw, 2.75rem);
  block-size: auto;
}
</style>
