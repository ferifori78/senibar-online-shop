<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import FilterGroup from '@/components/catalog/FilterGroup.vue'
import ProductCard from '@/components/catalog/ProductCard.vue'
import { useCatalogStore } from '@/stores/catalog'
import { formatNumber } from '@/utils/format'

const catalog = useCatalogStore()
const search = ref('')

// Mobile only: the rail becomes a drawer rather than eating the top of the
// screen above the grid. Ignored entirely at desktop width, where the rail is
// always on screen.
const drawerOpen = ref(false)

// Escape closes it, like any other overlay on the site.
function onKeydown(event) {
  if (event.key === 'Escape' && drawerOpen.value) drawerOpen.value = false
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  // Leaving the page with the drawer open must not strand a locked body.
  document.body.style.overflow = ''
})

// The drawer covers the screen, so scrolling behind it moves a grid the
// reader cannot see.
watch(drawerOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})

// Narrowed to pantry alone: the coffee-only groups below would offer nothing
// but dead ends, so they come off the rail.
const onlyPantry = computed(() => {
  const kinds = catalog.filters.kind
  return kinds.length === 1 && kinds[0] === 'pantry'
})

const SORTS = [
  // The shelf order set by dragging in the panel. First, and the default, so
  // the storefront opens in the order the roaster arranged.
  { value: 'sort_order', label: 'چیدمان صنوبر' },
  { value: '-created_at', label: 'تازه‌ترین' },
  { value: 'price_per_250g', label: 'ارزان‌ترین' },
  { value: '-price_per_250g', label: 'گران‌ترین' },
  { value: '-cupping_score', label: 'بالاترین امتیاز' },
]

// Debounced so typing doesn't fire a request per keystroke.
let searchTimer
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => catalog.applyFilters({ search: value }), 300)
})

// Coffee-only groups. Kept in one list because they are hidden and cleared
// together, and a name in one place and not the other would leave an
// invisible filter applied.
const COFFEE_ONLY = ['species', 'origin_type', 'process']

function toggleArrayFilter(key, value) {
  const current = catalog.filters[key]
  const next = current.includes(value)
    ? current.filter((v) => v !== value)
    : [...current, value]

  const patch = { [key]: next }

  // Narrowing to pantry alone takes the coffee groups off the rail. Leaving
  // their values applied would empty the grid with no visible cause — the
  // filter doing it is no longer on screen to un-tick.
  if (key === 'kind' && next.length === 1 && next[0] === 'pantry') {
    for (const field of COFFEE_ONLY) patch[field] = []
  }

  catalog.applyFilters(patch)
}

function clearAll() {
  search.value = ''
  catalog.resetFilters()
}

onMounted(() => {
  catalog.fetchProducts()
  catalog.fetchFacets()
})
</script>

<template>
  <main class="register-editorial catalog">
    <header class="catalog__header">
      <p class="catalog__eyebrow">SENOBAR / CATALOG</p>
      <h1 class="catalog__title">قهوه‌ها</h1>
      <p class="catalog__lede">
        هر لات پس از سفارش رست می‌شود. تاریخ رست روی صفحه‌ی هر قهوه ثبت است.
      </p>
    </header>

    <!-- Search and sort stay full width above both columns: they act on the
         result set as a whole, not on one facet. -->
    <section class="catalog__controls" aria-label="جستجو و مرتب‌سازی">
      <div class="catalog__search">
        <label class="catalog__control-label" for="catalog-search">جستجو</label>
        <input
          id="catalog-search"
          v-model="search"
          type="search"
          class="catalog__input"
          placeholder="نام قهوه، کشور، مزرعه"
        />
      </div>

      <div class="catalog__sort">
        <label class="catalog__control-label" for="catalog-sort">مرتب‌سازی</label>
        <select
          id="catalog-sort"
          class="catalog__input"
          :value="catalog.filters.ordering"
          @change="catalog.applyFilters({ ordering: $event.target.value })"
        >
          <option v-for="sort in SORTS" :key="sort.value" :value="sort.value">
            {{ sort.label }}
          </option>
        </select>
      </div>
    </section>

    <!-- Mobile: opens the rail as a drawer. Hidden at desktop width. -->
    <button
      type="button"
      class="catalog__drawer-toggle"
      :aria-expanded="drawerOpen"
      aria-controls="catalog-filters"
      @click="drawerOpen = !drawerOpen"
    >
      <!-- Three rules: the hamburger. A CSS shape, not an icon font and not
           a pictograph. -->
      <span class="catalog__burger" aria-hidden="true">
        <span></span><span></span><span></span>
      </span>
      فیلترها
      <span v-if="catalog.activeFilterCount" class="catalog__drawer-count">
        {{ formatNumber(catalog.activeFilterCount) }}
      </span>
    </button>

    <!-- Tapping outside closes the drawer. Only rendered while it is open, so
         it never sits over the grid at desktop width. -->
    <div
      v-if="drawerOpen"
      class="catalog__scrim"
      @click="drawerOpen = false"
    />

    <div class="catalog__body">
      <!-- --- Filter rail ------------------------------------------------ -->
      <aside
        id="catalog-filters"
        class="catalog__rail"
        :class="{ 'catalog__rail--open': drawerOpen }"
        aria-label="فیلترها"
      >
        <div class="catalog__rail-head">
          <span class="catalog__rail-title">فیلترها</span>
          <button
            v-if="catalog.activeFilterCount"
            type="button"
            class="catalog__clear"
            @click="clearAll"
          >
            پاک کردن
          </button>
          <!-- Mobile only: the drawer covers the grid, so it needs a way out
               that does not depend on knowing the scrim is tappable. -->
          <button
            type="button"
            class="catalog__rail-close"
            aria-label="بستن فیلترها"
            @click="drawerOpen = false"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          </button>
        </div>

        <template v-if="catalog.facets">
          <!-- Coffee or pantry. First, because it decides whether the groups
               below it are even meaningful. -->
          <FilterGroup
            v-if="catalog.facets.kinds?.length > 1"
            label="دسته"
            :options="catalog.facets.kinds"
            :selected="catalog.filters.kind"
            @toggle="toggleArrayFilter('kind', $event)"
          />

          <!-- Species and origin are properties of coffee. Hidden once the
               customer has narrowed to pantry items, where every option would
               return nothing. -->
          <template v-if="!onlyPantry">
            <FilterGroup
              v-if="catalog.facets.species?.length"
              label="گونه"
              :options="catalog.facets.species"
              :selected="catalog.filters.species"
              @toggle="toggleArrayFilter('species', $event)"
            />

            <FilterGroup
              v-if="catalog.facets.origin_types?.length"
              label="خاستگاه"
              :options="catalog.facets.origin_types"
              :selected="catalog.filters.origin_type"
              @toggle="toggleArrayFilter('origin_type', $event)"
            />

            <FilterGroup
              v-if="catalog.facets.processes?.length"
              label="پروسس"
              :options="catalog.facets.processes"
              :selected="catalog.filters.process"
              @toggle="toggleArrayFilter('process', $event)"
            />
          </template>

          <FilterGroup
            v-if="catalog.facets.origins.length"
            label="مبدأ"
            :options="catalog.facets.origins.map((o) => ({ value: o, label: o }))"
            :selected="catalog.filters.origin"
            @toggle="toggleArrayFilter('origin', $event)"
          />

          <FilterGroup
            label="وضعیت"
            :options="[{ value: 'in_stock', label: 'فقط موجود' }]"
            :selected="catalog.filters.in_stock ? ['in_stock'] : []"
            @toggle="catalog.applyFilters({ in_stock: !catalog.filters.in_stock })"
          />
        </template>
      </aside>

      <!-- --- Results ---------------------------------------------------- -->
      <div class="catalog__results">
        <div class="catalog__summary">
          <span v-if="!catalog.loading">{{ formatNumber(catalog.count) }} محصول</span>
          <span v-else>در حال بارگذاری</span>
        </div>

        <p v-if="catalog.error" class="catalog__error" role="alert">{{ catalog.error }}</p>

        <LoadingState
          v-if="catalog.loading && !catalog.products.length"
          variant="cards"
          code="ROASTING THE LIST"
          :count="6"
          class="catalog__loading"
        />

        <EmptyState
          v-else-if="catalog.isEmpty"
          :icon="catalog.activeFilterCount || search ? 'search' : 'bean'"
          :code="catalog.activeFilterCount || search ? 'NO MATCH' : 'NO BEANS IN SIGHT'"
          :message="
            catalog.activeFilterCount || search
              ? 'محصولی با این فیلترها پیدا نشد. فیلترها را بردارید یا عبارت دیگری امتحان کنید.'
              : 'هنوز محصولی منتشر نشده است. به‌زودی لات‌های تازه اینجا خواهند بود.'
          "
          class="catalog__empty"
        >
          <BaseButton
            v-if="catalog.activeFilterCount || search"
            variant="secondary"
            @click="clearAll"
          >
            پاک کردن فیلترها
          </BaseButton>
        </EmptyState>

        <div v-else class="catalog__grid">
          <ProductCard v-for="item in catalog.products" :key="item.id" :product="item" />
        </div>

        <div v-if="catalog.hasNext" class="catalog__more">
          <BaseButton variant="secondary" :loading="catalog.loading" @click="catalog.loadMore()">
            نمایش بیشتر
          </BaseButton>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
/* ==========================================================================
   ProductListView — Editorial register
   ========================================================================== */

.catalog {
  padding: clamp(2rem, 6vw, 4.5rem) clamp(1.25rem, 5vw, 4rem) 5rem;
}

/* --- Header ---------------------------------------------------------------- */
.catalog__eyebrow {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.catalog__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(2.5rem, 8vw, 4rem);
  line-height: 1.05;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.catalog__lede {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  line-height: 1.7;
  color: var(--ink-muted);
  max-width: 34rem;
  margin: 1rem 0 0;
}

/* --- Controls -------------------------------------------------------------- */
.catalog__controls {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 1rem;
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 3px solid var(--divider);
}

@media (max-width: 40rem) {
  .catalog__controls {
    grid-template-columns: 1fr;
  }
}

.catalog__control-label {
  display: block;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.catalog__input {
  width: 100%;
  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  color: var(--ink);
  padding: 0.6875rem 0.8125rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.8125rem;
}

.catalog__input:focus {
  outline: none;
  box-shadow: 4px 4px 0 var(--accent);
}

/* --- Two columns: rail, then results ---------------------------------------
   The rail is a fixed width so the grid does not reflow as groups appear and
   disappear when the customer narrows to pantry items. */
.catalog__body {
  display: grid;
  /* 15rem, not 14: room for a long origin and for the scrollbar, without
     stranding each count so far from its label that they stop reading as a
     pair. */
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: clamp(1.5rem, 4vw, 3rem);
  margin-top: 2rem;
}

.catalog__rail {
  border-top: 3px solid var(--divider);
  padding-top: 1.5rem;
  /* Follows the grid down a long catalogue instead of scrolling out of
     reach at the top. */
  position: sticky;
  top: 1.5rem;
  align-self: start;
  max-height: calc(100vh - 3rem);
  overflow-y: auto;
  /* Room for the scrollbar. Without it the counts sit directly against the
     bar once the rail is tall enough to scroll, which is most of the time. */
  padding-inline-end: 0.875rem;
  scrollbar-width: thin;
}

.catalog__rail-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.catalog__rail-title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
}

/* --- Mobile drawer ---------------------------------------------------------
   Hidden at desktop width, where the rail is always on screen. */
.catalog__drawer-toggle,
.catalog__scrim,
.catalog__rail-close {
  display: none;
}

@media (max-width: 52rem) {
  .catalog__body {
    grid-template-columns: 1fr;
  }

  .catalog__drawer-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1.75rem;
    border: 3px solid var(--ink);
    border-radius: 0;
    background-color: var(--paper);
    color: var(--ink);
    font-family: var(--font-terminal, "Morabba", sans-serif);
    font-size: 0.6875rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 0.625rem 0.875rem;
    cursor: pointer;
  }

  .catalog__drawer-toggle:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  /* Three rules, drawn rather than iconified. */
  .catalog__burger {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    width: 0.9375rem;
    height: 0.6875rem;
  }

  .catalog__burger span {
    display: block;
    height: 3px;
    background-color: currentColor;
  }

  .catalog__drawer-count {
    background-color: var(--accent);
    color: var(--paper);
    padding: 0 0.375rem;
  }

  /* Dims the grid behind the open drawer and catches a tap outside it. */
  .catalog__scrim {
    display: block;
    position: fixed;
    inset: 0;
    background-color: color-mix(in srgb, var(--ink) 45%, transparent);
    z-index: 40;
  }

  /* Off-canvas: slides in over the grid from the start edge (right, in an
     RTL page) rather than pushing the products down the screen. */
  .catalog__rail {
    display: block;
    position: fixed;
    inset-block: 0;
    inset-inline-start: 0;
    width: min(20rem, 86vw);
    max-height: none;
    /* Both are load-bearing. The desktop rail is a grid item with
       `align-self: start`, which survives into this block and makes the
       fixed panel size to its content — taller than the screen, with the
       last group below the fold and nothing able to scroll to it, because
       an element grown to fit its content never overflows itself.
       `height: 100%` against `inset-block: 0` is what gives `overflow-y`
       something to scroll. */
    align-self: stretch;
    height: 100%;
    z-index: 50;
    background-color: var(--paper);
    border-inline-end: 3px solid var(--ink);
    border-top: 0;
    padding: 1.25rem 1.25rem 2rem;
    overflow-y: auto;
    /* Closed: parked just off screen. `visibility` keeps it out of the tab
       order while closed, which `transform` alone would not do. */
    transform: translateX(100%);
    visibility: hidden;
    transition:
      transform 160ms cubic-bezier(0.2, 0, 0, 1),
      visibility 160ms;
  }

  /* The panel enters from the right on an RTL page and from the left on an
     LTR one, so the sign follows the writing direction. */
  [dir="ltr"] .catalog__rail {
    transform: translateX(-100%);
  }

  .catalog__rail--open {
    transform: translateX(0);
    visibility: visible;
  }

  .catalog__rail-close {
    display: grid;
    place-items: center;
    margin-inline-start: auto;
    width: 1.75rem;
    height: 1.75rem;
    border: 3px solid var(--ink);
    border-radius: 0;
    background-color: var(--paper);
    color: var(--ink);
    cursor: pointer;
    padding: 0;
  }

  .catalog__rail-close svg {
    width: 0.75rem;
    height: 0.75rem;
  }

  .catalog__rail-close:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .catalog__rail {
    transition: none;
  }
}

/* --- Summary --------------------------------------------------------------- */
.catalog__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.875rem;
  border-bottom: 3px solid var(--divider);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.catalog__clear {
  border: 0;
  background: none;
  color: var(--accent);
  font: inherit;
  cursor: pointer;
  padding: 0;
  border-bottom: 2px solid var(--accent);
}

/* --- Grid ------------------------------------------------------------------ */
.catalog__grid {
  display: grid;
  /* Three per row, not as many as fit. With the rail taking a column, a
     four-up grid made each card narrow enough that the photograph stopped
     carrying the product. Fixed at three so the cards stay large. */
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(1.5rem, 3vw, 2.25rem);
  margin-top: 1.75rem;
}

@media (max-width: 64rem) {
  .catalog__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 34rem) {
  .catalog__grid {
    grid-template-columns: 1fr;
  }
}

.catalog__loading,
.catalog__empty {
  margin-top: 1.75rem;
}

.catalog__error {
  margin-top: 3rem;
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
}

.catalog__more {
  display: flex;
  justify-content: center;
  margin-top: 3rem;
}
</style>
