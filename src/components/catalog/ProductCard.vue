<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { formatNumber, formatPrice } from '@/utils/format'

const props = defineProps({
  product: { type: Object, required: true },
})

// The API reports stock as `available_grams`; the list endpoint annotates it.
const inStock = computed(() => props.product.is_in_stock ?? props.product.available_grams > 0)

// Three notes is what fits on one line without wrapping the card.
const notes = computed(() => (props.product.flavor_notes || []).slice(0, 3))

const isPantry = computed(() => props.product.kind === 'pantry')

/*
 * The corner tab. A blend has no single country — the cleanup migration
 * cleared that column and recorded the fact in `origin_type` instead — so it
 * says «ترکیبی». An empty tab would be a black rectangle with nothing in it.
 */
const originTab = computed(() => {
  if (props.product.origin_country) return props.product.origin_country
  return props.product.origin_type === 'multi' ? 'ترکیبی' : ''
})
const byPackage = computed(() => props.product.sale_mode === 'package')

/*
 * `process` and `roast_level` are not nullable, so masala tea carries the
 * column defaults and would read «MEDIUM · WASHED» — a roast profile invented
 * for something that was never roasted. A pantry item shows its brand
 * instead, and nothing at all when it has none.
 */
const meta = computed(() => {
  if (!isPantry.value) {
    return [props.product.process_display, props.product.roast_level_display].filter(Boolean)
  }
  return [props.product.brand].filter(Boolean)
})

/** What the footer price actually buys. */
const price = computed(() =>
  isPantry.value && byPackage.value ? props.product.package_price : props.product.price_per_250g,
)

const unit = computed(() => {
  // A sealed pack is priced per pack, at whatever size it is. Printing
  // «۲۵۰ گرم» under a 200g pack of masala would state the wrong weight for
  // the price beside it.
  if (isPantry.value && byPackage.value) {
    return props.product.package_grams ? `${formatNumber(props.product.package_grams)} گرم` : 'هر بسته'
  }
  return '۲۵۰ گرم'
})
</script>

<template>
  <article class="card" :class="{ 'card--sold-out': !inStock }">
    <RouterLink :to="`/products/${product.slug}`" class="card__link">
      <!-- Image plate. Square, framed, with the origin overlaid as a tab. -->
      <div class="card__plate">
        <img v-if="product.image" :src="product.image" :alt="product.name" class="card__image" />
        <!-- No image yet: a ruled placeholder, not a broken frame. -->
        <div v-else class="card__placeholder" aria-hidden="true">
          <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5">
            <ellipse cx="24" cy="24" rx="13" ry="18" transform="rotate(-35 24 24)" />
            <path d="M15 33C20 28 28 20 33 15" />
          </svg>
        </div>

        <span v-if="originTab" class="card__origin">{{ originTab }}</span>

        <span v-if="!inStock" class="card__stamp">ناموجود</span>
      </div>

      <div class="card__body">
        <h3 class="card__name">{{ product.name }}</h3>
        <p v-if="product.origin_region" class="card__region">{{ product.origin_region }}</p>

        <ul v-if="notes.length" class="card__notes">
          <li v-for="note in notes" :key="note" class="card__note">{{ note }}</li>
        </ul>

        <div v-if="meta.length" class="card__meta">
          <template v-for="(item, index) in meta" :key="item">
            <span v-if="index" class="card__meta-sep" aria-hidden="true" />
            <span>{{ item }}</span>
          </template>
        </div>
      </div>

      <footer class="card__footer">
        <span class="card__price">{{ formatPrice(price) }}</span>
        <span class="card__unit">{{ unit }}</span>
      </footer>
    </RouterLink>
  </article>
</template>

<style scoped>
/* ==========================================================================
   ProductCard — Editorial register
   A framed slab that lifts onto a harder shadow on hover. Square throughout.
   ========================================================================== */

.card {
  border: 3px solid var(--ink);
  background-color: var(--paper);
  box-shadow: 6px 6px 0 var(--shadow);
  transition:
    transform 90ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 90ms cubic-bezier(0.2, 0, 0, 1);
}

@media (hover: hover) {
  .card:hover {
    transform: translate(-3px, -3px);
    box-shadow: 9px 9px 0 var(--shadow);
  }
}

.card:focus-within {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.card__link {
  display: flex;
  flex-direction: column;
  height: 100%;
  color: inherit;
  text-decoration: none;
}
.card__link:focus-visible {
  outline: none; /* the card itself takes the ring */
}

/* --- Plate ----------------------------------------------------------------- */
.card__plate {
  position: relative;
  aspect-ratio: 1;
  border-bottom: 3px solid var(--ink);
  background-color: var(--paper-sunk);
  overflow: hidden;
}

.card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.card__placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--rule);
}
.card__placeholder svg {
  width: 40%;
  height: 40%;
}

/* Origin sits as a tab in the corner, framed on two sides. */
.card__origin {
  position: absolute;
  inset-block-start: 0;
  inset-inline-start: 0;
  background-color: var(--ink);
  color: var(--paper);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.375rem 0.625rem;
}

.card__stamp {
  position: absolute;
  inset-block-end: 0.75rem;
  inset-inline-start: 0.75rem;
  background-color: var(--paper);
  color: var(--ink);
  border: 3px solid var(--ink);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.25rem 0.5rem;
}

.card--sold-out .card__image,
.card--sold-out .card__placeholder {
  opacity: 0.45;
}

/* --- Body ------------------------------------------------------------------ */
.card__body {
  padding: 1.125rem 1.125rem 0.75rem;
  flex: 1;
}

.card__name {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.25rem;
  line-height: 1.25;
  font-weight: 600;
  margin: 0;
}

.card__region {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  color: var(--ink-muted);
  margin: 0.25rem 0 0;
}

.card__notes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  list-style: none;
  padding: 0;
  margin: 0.875rem 0 0;
}

.card__note {
  border: 2px solid var(--rule);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-muted);
  padding: 0.1875rem 0.4375rem;
}

.card__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.875rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.card__meta-sep {
  width: 3px;
  height: 3px;
  background-color: var(--ink-muted);
}

/* --- Footer ---------------------------------------------------------------- */
.card__footer {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.875rem 1.125rem;
  border-top: 3px solid var(--ink);
}

.card__price {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  font-weight: 600;
}

.card__unit {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

@media (prefers-reduced-motion: reduce) {
  .card {
    transition: none;
  }
}
</style>
