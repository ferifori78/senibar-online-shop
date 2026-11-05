<script setup>
import { computed } from 'vue'

/**
 * The Senobar mark: the supplied artwork — a leaf whose right half is drawn as
 * the word «صنوبر» in calligraphy.
 *
 * Shipped as a transparent PNG rather than redrawn as vector: the calligraphy
 * is the identity of the mark and cannot be approximated by paths. The file is
 * exported at 2x the largest rendered size so it stays sharp on retina, and
 * trimmed to the artwork's own bounds so the leaf is not floating inside its
 * own padding.
 *
 * Single source for every place the logo appears — storefront header, auth
 * pages, admin panel, footer — so the copies never drift apart.
 *
 * The green is baked into the artwork, so unlike the old vector this cannot
 * take `currentColor`; `light` selects a pre-tinted file instead.
 */
const props = defineProps({
  /** Height of the mark in pixels; the width follows the artwork's proportions. */
  size: { type: [Number, String], default: 22 },
  /** Use the lightened artwork, for the Terminal register's dark ground.
   *
   *  The stock green measures 2.6:1 on the panel background and is genuinely
   *  hard to see; the light variant is the same mark at 6.4:1. */
  light: { type: Boolean, default: false },
  /** Show the Persian wordmark beside the mark.
   *
   *  Off by default now: the artwork already contains «صنوبر», so setting this
   *  prints the name twice. */
  wordmark: { type: Boolean, default: false },
  /** And the latin one under it, at label scale. */
  latin: { type: Boolean, default: false },
})

/** The artwork's own aspect ratio, from the trimmed PNG (701x1084). */
const RATIO = 701 / 1084

// Both dimensions are set on the tag so the browser reserves the right box
// before the image arrives and the header does not jump as it loads.
const width = computed(() => Math.round(Number(props.size) * RATIO))

const src = computed(() => (props.light ? '/logo-light.png' : '/logo.png'))
const srcset = computed(() =>
  props.light
    ? '/logo-light.png 1x, /logo-light@2x.png 2x'
    : '/logo.png 1x, /logo@2x.png 2x',
)
</script>

<template>
  <span class="brand">
    <!-- Decorative: the name is carried as real text beside it, or by the page
         heading. Marking it alt="" keeps a screen reader from announcing the
         shop's name twice. -->
    <img
      class="brand__glyph"
      :src="src"
      :srcset="srcset"
      :width="width"
      :height="size"
      alt=""
      decoding="async"
    />

    <span v-if="wordmark || latin" class="brand__text">
      <span v-if="wordmark" class="brand__word">صنوبر</span>
      <span v-if="latin" class="brand__latin">SENOBAR</span>
    </span>
  </span>
</template>

<style scoped>
.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
}

.brand__glyph {
  flex: none;
  /* The width and height attributes carry the real numbers and reserve the
     box before the file loads; this keeps the ratio if a narrow container
     ever squeezes the width. */
  object-fit: contain;
}

.brand__text {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  line-height: 1;
}

.brand__word {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.375rem;
  font-weight: 600;
}

.brand__latin {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  color: var(--ink-muted);
}
</style>
