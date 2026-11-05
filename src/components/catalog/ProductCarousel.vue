<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

/**
 * The product gallery, as a carousel.
 *
 * One photo is shown at a time inside the square plate the product page
 * already uses; the rest are reachable by arrows, thumbnails, keyboard, or a
 * swipe. With a single photo it renders exactly as the old single image did —
 * no controls, no thumbnails — so a product with one picture is not given
 * furniture it does not need.
 */
const props = defineProps({
  /** The gallery rows from the product payload. */
  images: { type: Array, default: () => [] },
  /** The product's cover, used when the gallery is empty. */
  fallback: { type: String, default: '' },
  /** Alt text: the coffee's name. */
  name: { type: String, required: true },
})

/** Photos to show, newest API shape first, falling back to the cover. */
const slides = computed(() => {
  if (props.images?.length) return props.images
  return props.fallback ? [{ id: 'cover', image: props.fallback, alt_text: '' }] : []
})

const index = ref(0)
const many = computed(() => slides.value.length > 1)

// A product whose gallery shrinks (or a different product on the same route)
// must not leave the index pointing past the end.
watch(slides, (list) => {
  if (index.value > list.length - 1) index.value = 0
})

function go(to) {
  const count = slides.value.length
  if (!count) return
  // Wrap both ways: at the last photo "next" returns to the first, which is
  // what a small gallery should do rather than dead-ending.
  index.value = (to + count) % count
}

const next = () => go(index.value + 1)
const previous = () => go(index.value - 1)

/**
 * Arrow keys follow the reading direction, not the array.
 *
 * The page is RTL, so the visually-left arrow means "next" — mapping
 * ArrowLeft to `previous` would move the carousel the opposite way from the
 * button sitting under the reader's finger.
 */
function onKey(event) {
  if (event.key === 'ArrowLeft') next()
  else if (event.key === 'ArrowRight') previous()
  else return
  event.preventDefault()
}

/* --- Swipe ---------------------------------------------------------------
   Pointer events rather than touch events, so a mouse drag works too. */
const startX = ref(null)

function onPointerDown(event) {
  startX.value = event.clientX
}

function onPointerUp(event) {
  if (startX.value === null) return
  const delta = event.clientX - startX.value
  startX.value = null
  // Below this, it was a tap or a jitter, not a swipe.
  if (Math.abs(delta) < 40) return
  // Dragging leftward (negative) advances, matching the arrow mapping above.
  if (delta < 0) next()
  else previous()
}

onBeforeUnmount(() => {
  startX.value = null
})

defineExpose({ next, previous })
</script>

<template>
  <div class="car">
    <div
      class="car__plate"
      :class="{ 'car__plate--interactive': many }"
      :tabindex="many ? 0 : undefined"
      :role="many ? 'group' : undefined"
      :aria-roledescription="many ? 'گالری تصویر' : undefined"
      :aria-label="many ? `تصویرهای ${name}` : undefined"
      @keydown="many && onKey($event)"
      @pointerdown="many && onPointerDown($event)"
      @pointerup="many && onPointerUp($event)"
    >
      <template v-if="slides.length">
        <!-- Every slide stays in the DOM and is hidden with `hidden`, rather
             than swapped with v-if: the browser then keeps the decoded images
             and moving between them is instant instead of a white flash. -->
        <img
          v-for="(slide, i) in slides"
          :key="slide.id"
          :src="slide.image"
          :alt="slide.alt_text || name"
          class="car__image"
          :hidden="i !== index"
          :draggable="false"
          :loading="i === 0 ? 'eager' : 'lazy'"
        />
      </template>

      <div v-else class="car__placeholder" aria-hidden="true">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5">
          <ellipse cx="24" cy="24" rx="13" ry="18" transform="rotate(-35 24 24)" />
          <path d="M15 33C20 28 28 20 33 15" />
        </svg>
      </div>

      <slot name="tab" />

      <!-- Controls only exist when there is somewhere to go. -->
      <template v-if="many">
        <!-- Each glyph points outward, the way its button travels: "previous"
             sits on the left and points left, "next" sits on the right and
             points right. -->
        <button type="button" class="car__arrow car__arrow--prev" aria-label="تصویر قبلی" @click="previous">
          <span aria-hidden="true">‹</span>
        </button>
        <button type="button" class="car__arrow car__arrow--next" aria-label="تصویر بعدی" @click="next">
          <span aria-hidden="true">›</span>
        </button>

        <p class="car__count" aria-hidden="true">
          {{ (index + 1).toLocaleString('fa-IR') }} / {{ slides.length.toLocaleString('fa-IR') }}
        </p>

        <!-- A live region so the count is announced without moving focus. -->
        <p class="car__sr" role="status" aria-live="polite">
          تصویر {{ index + 1 }} از {{ slides.length }}
        </p>
      </template>
    </div>

    <!-- Thumbnails, below the plate rather than over the photo. -->
    <ul v-if="many" class="car__thumbs">
      <li v-for="(slide, i) in slides" :key="slide.id">
        <button
          type="button"
          class="car__thumb"
          :class="{ 'car__thumb--on': i === index }"
          :aria-label="`رفتن به تصویر ${i + 1}`"
          :aria-current="i === index ? 'true' : undefined"
          @click="index = i"
        >
          <img :src="slide.image" alt="" class="car__thumb-img" :draggable="false" loading="lazy" />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* ==========================================================================
   ProductCarousel — Editorial register
   The plate keeps the square, the 3px rule and the hard shadow the product
   page already establishes; the controls are square ink buttons, not the
   round translucent overlays a stock carousel ships with.
   ========================================================================== */

.car {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.car__plate {
  position: relative;
  aspect-ratio: 1;
  border: 3px solid var(--ink);
  box-shadow: 10px 10px 0 var(--shadow);
  background-color: var(--paper-sunk);
  overflow: hidden;
}

.car__plate--interactive {
  /* A swipe should not select the image or the text under it. */
  touch-action: pan-y;
  user-select: none;
}

.car__plate:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 4px;
}

.car__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.car__placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--rule);
}
.car__placeholder svg {
  width: 35%;
  height: 35%;
}

/* --- Arrows ---------------------------------------------------------------- */
.car__arrow {
  position: absolute;
  inset-block-start: 50%;
  transform: translateY(-50%);
  width: 2.5rem;
  height: 2.5rem;
  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  color: var(--ink);
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
}

/* Physical sides, deliberately: these are positions on screen, and the arrow
   glyphs above are chosen to match. "Next" sits on the right and "previous"
   on the left, the way carousels are laid out generally — the thumbnail strip
   below runs left-to-right to agree with it. */
.car__arrow--next {
  right: 0.75rem;
}
.car__arrow--prev {
  left: 0.75rem;
}

.car__arrow:hover {
  background-color: var(--accent);
  border-color: var(--accent);
  color: var(--paper);
}

.car__arrow:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.car__count {
  position: absolute;
  inset-block-end: 0;
  inset-inline-start: 0;
  margin: 0;
  padding: 0.25rem 0.625rem;
  background-color: var(--ink);
  color: var(--paper);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
}

/* Announced, never shown: the visible count above is aria-hidden because it
   reads as "1 / 4" rather than as a sentence. */
.car__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

/* --- Thumbnails ------------------------------------------------------------ */
.car__thumbs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  /* Left-to-right even on this RTL page, so the strip runs the same way the
     arrows do: first photo on the left under "previous", last on the right
     under "next". A right-to-left strip would contradict them. */
  direction: ltr;
  justify-content: flex-start;
}

.car__thumb {
  display: block;
  width: 4rem;
  height: 4rem;
  padding: 0;
  border: 3px solid var(--rule);
  border-radius: 0;
  background: none;
  cursor: pointer;
  overflow: hidden;
}

.car__thumb--on {
  border-color: var(--accent);
}

.car__thumb:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

.car__thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

@media (prefers-reduced-motion: reduce) {
  .car__arrow {
    transition: none;
  }
}
</style>
