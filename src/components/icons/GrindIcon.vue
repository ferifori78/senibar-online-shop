<script setup>
/**
 * Linear SVG glyphs for each grind method. No emoji, no fills — every icon is
 * a 24x24 stroke drawing that inherits currentColor, so it reads correctly on
 * paper, on accent, and in the Terminal register alike.
 */
defineProps({
  method: { type: String, required: true },
  size: { type: [Number, String], default: 24 },
})
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="square"
    stroke-linejoin="miter"
    aria-hidden="true"
    focusable="false"
  >
    <!-- Whole bean: the bean outline with its centre crease. -->
    <template v-if="method === 'whole'">
      <ellipse cx="12" cy="12" rx="6.5" ry="9" transform="rotate(-35 12 12)" />
      <path d="M7.5 16.5C10 14 14 10 16.5 7.5" />
    </template>

    <!-- Espresso: portafilter — basket, spout, handle. -->
    <template v-else-if="method === 'espresso'">
      <path d="M4 6h13v3a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V6Z" />
      <path d="M17 7.5h3" />
      <path d="M10.5 14v3" />
      <path d="M8 20h5" />
      <path d="M8 20l2.5-3M13 20l-2.5-3" />
    </template>

    <!-- Moka pot: the stacked octagonal body with its handle. -->
    <template v-else-if="method === 'moka_pot'">
      <path d="M7 4h9l-1.5 6h-6L7 4Z" />
      <path d="M8.5 10h6l1.5 9a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1l1.5-9Z" />
      <path d="M16 12h2.5a1.5 1.5 0 0 1 0 3H16" />
      <path d="M7 4h9" />
    </template>

    <!-- V60: the cone, its ribs, and the carafe rim beneath. -->
    <template v-else-if="method === 'v60'">
      <path d="M4 5h16l-7 10h-2L4 5Z" />
      <path d="M9 5v10M15 5l-3 10" />
      <path d="M12 15v3" />
      <path d="M7 21h10" />
    </template>

    <!-- Chemex: the hourglass vessel with its collar. -->
    <template v-else-if="method === 'chemex'">
      <path d="M6 3h12l-4.5 8.5L18 21H6l4.5-9.5L6 3Z" />
      <path d="M9.5 10.5h5" />
    </template>

    <!-- AeroPress: the cylinder with its plunger pressed in. -->
    <template v-else-if="method === 'aeropress'">
      <path d="M8 8h8v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V8Z" />
      <path d="M10 8V4h4v4" />
      <path d="M6 8h12" />
      <path d="M9 15h6" />
    </template>

    <!-- French press: the beaker, plunger rod, and filter disc. -->
    <template v-else-if="method === 'french_press'">
      <path d="M7 6h10v13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V6Z" />
      <path d="M12 2v10" />
      <path d="M9 3h6" />
      <path d="M8 12h8" />
      <path d="M17 9h2.5a1.5 1.5 0 0 1 0 4H17" />
    </template>

    <!-- Cold brew: the jar with its slow drips. -->
    <template v-else-if="method === 'cold_brew'">
      <path d="M6 7h12v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V7Z" />
      <path d="M5 4h14v3H5z" />
      <path d="M9 12v4M12 11v5M15 12v4" />
    </template>

    <!-- Turkish: the cezve — narrow body and long straight handle. -->
    <template v-else-if="method === 'turkish'">
      <path d="M6 7h9v9a4 4 0 0 1-4 4h-1a4 4 0 0 1-4-4V7Z" />
      <path d="M5 7h11" />
      <path d="M15 9h5" />
      <path d="M14 5l2-2" />
    </template>

    <!-- Fallback: a plain square, so an unknown method never renders blank. -->
    <template v-else>
      <rect x="5" y="5" width="14" height="14" />
    </template>
  </svg>
</template>
