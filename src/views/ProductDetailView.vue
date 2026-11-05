<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import GrindSelector from '@/components/catalog/GrindSelector.vue'
import ProductCarousel from '@/components/catalog/ProductCarousel.vue'
import WeightSelector from '@/components/catalog/WeightSelector.vue'
import { useCartStore } from '@/stores/cart'
import { useCatalogStore } from '@/stores/catalog'
import {
  formatDate,
  formatNumber,
  formatPrice,
  formatWeight,
  freshnessLabel,
  freshnessState,
} from '@/utils/format'

const route = useRoute()
const catalog = useCatalogStore()
const cart = useCartStore()

const weight = ref(250)
const grind = ref('whole')
const quantity = ref(1)
const added = ref(false)

const product = computed(() => catalog.product)
const batch = computed(() => product.value?.current_batch)

/** A pantry item: no roast, no grind, no cup profile. */
const isPantry = computed(() => product.value?.kind === 'pantry')
/** ...and sold as a sealed pack, so its weight is stated rather than chosen. */
const isPackage = computed(() => isPantry.value && product.value?.sale_mode === 'package')

const selectedOption = computed(() =>
  product.value?.price_options?.find((o) => o.weight_grams === weight.value),
)

const lineTotal = computed(() =>
  selectedOption.value ? Number(selectedOption.value.price) * quantity.value : 0,
)

// A coffee we don't roast for espresso shouldn't offer espresso or turkish —
// both need the fine end of the grinder.
const unavailableGrinds = computed(() =>
  product.value && !product.value.is_espresso_suitable ? ['espresso', 'turkish'] : [],
)

const cupAxes = computed(() => {
  // A pantry item has no cup profile; the serializer still returns the four
  // columns because they are not nullable, and they would render as a real
  // measured profile of 3/5 across the board.
  if (isPantry.value) return []

  const profile = product.value?.cup_profile
  if (!profile) return []
  return [
    { key: 'acidity', label: 'اسیدیته', value: profile.acidity },
    { key: 'body', label: 'بادی', value: profile.body },
    { key: 'sweetness', label: 'شیرینی', value: profile.sweetness },
    { key: 'bitterness', label: 'تلخی', value: profile.bitterness },
  ]
})

const specs = computed(() => {
  const p = product.value
  if (!p) return []

  // A pantry item carries the model's defaults in `process` and `roast_level`
  // because those columns are not nullable — printing them would tell the
  // customer that hot chocolate is washed and medium roast.
  if (isPantry.value) {
    return [
      { label: 'برند', value: p.brand },
      { label: 'کشور', value: p.origin_country },
      { label: 'وزن بسته', value: p.package_grams ? formatWeight(p.package_grams) : '' },
      { label: 'سال تولید', value: p.production_year ? formatNumber(p.production_year) : '' },
      { label: 'تاریخ انقضا', value: p.best_before ? formatDate(p.best_before) : '' },
    ].filter((row) => row.value)
  }

  return [
    { label: 'کشور', value: p.origin_country },
    { label: 'منطقه', value: p.origin_region },
    { label: 'مزرعه', value: p.farm },
    { label: 'تولیدکننده', value: p.producer },
    { label: 'واریته', value: p.varietal },
    { label: 'ارتفاع', value: p.altitude_masl ? `${formatNumber(p.altitude_masl)} متر` : '' },
    // A lot can carry more than one process or be offered at more than one
    // roast; both are listed, falling back to the single value.
    {
      label: (p.all_processes || []).length > 1 ? 'پروسس‌ها' : 'پروسس',
      value: (p.all_processes || []).map((x) => x.label).join('، ') || p.process_display,
    },
    {
      label: (p.all_roast_levels || []).length > 1 ? 'درجه‌های رست' : 'درجه رست',
      value: (p.all_roast_levels || []).map((x) => x.label).join('، ') || p.roast_level_display,
    },
    { label: 'امتیاز کاپینگ', value: p.cupping_score ? formatNumber(p.cupping_score) : '' },
    { label: 'برداشت', value: p.harvest_year ? formatNumber(p.harvest_year) : '' },
  ].filter((row) => row.value)
})

async function addToCart() {
  await cart.add(product.value, {
    weight_grams: weight.value,
    grind_type: grind.value,
    quantity: quantity.value,
  })
  added.value = true
  setTimeout(() => (added.value = false), 2000)
}

watch(
  () => route.params.slug,
  (slug) => {
    if (slug) catalog.fetchProduct(slug)
  },
  { immediate: true },
)

// Reset the configurator when the coffee changes, and drop an unavailable
// grind rather than silently ordering something we can't make.
watch(product, (value) => {
  // A package has exactly one weight — its own. Leaving this at 250 would
  // price a 200g pack against the wrong line and add the wrong weight to the
  // cart, where the server would then correct it and the totals would jump.
  weight.value =
    value?.kind === 'pantry' && value?.sale_mode === 'package'
      ? value.package_grams || 250
      : 250
  quantity.value = 1
  grind.value = 'whole'
  if (value && unavailableGrinds.value.includes(grind.value)) {
    grind.value = 'whole'
  }
})
</script>

<template>
  <main class="register-editorial detail">
    <div v-if="catalog.detailLoading" class="detail__loading">در حال بارگذاری…</div>

    <div v-else-if="!product" class="detail__missing">
      <!-- Nothing loaded, so `kind` is unknown here — «محصول» is right for
           either. -->
      <p class="detail__missing-text">{{ catalog.error || 'این محصول پیدا نشد.' }}</p>
      <RouterLink to="/products"><BaseButton variant="secondary">بازگشت به لیست</BaseButton></RouterLink>
    </div>

    <template v-else>
      <nav class="detail__crumbs" aria-label="مسیر">
        <RouterLink to="/products" class="detail__crumb">قهوه‌ها</RouterLink>
        <span class="detail__crumb-sep" aria-hidden="true">/</span>
        <span>{{ product.name }}</span>
      </nav>

      <div class="detail__layout">
        <!-- ---------------------------------------------------- Left: the coffee -->
        <section class="detail__intro">
          <!-- Every photo the roaster uploaded, not just the cover. With one
               photo this renders as the plain plate it always was. -->
          <ProductCarousel
            :images="product.images || []"
            :fallback="product.image"
            :name="product.name"
          >
            <template #tab>
              <span class="detail__origin-tab">{{ product.origin_country }}</span>
            </template>
          </ProductCarousel>

          <!-- Roast date panel. The freshness light is the one circular shape.
               Skipped entirely for a pantry item: masala is not roasted, so
               both "roasted on" and "not roasted yet" are the wrong thing to
               say — the second reads as a missing value rather than one that
               never applied. -->
          <div v-if="!isPantry && batch" class="detail__roast">
            <div class="detail__roast-head">
              <span class="detail__roast-label">تاریخ رست</span>
              <span class="detail__freshness">
                <span class="status-light" :data-state="freshnessState(batch.freshness)" />
                {{ freshnessLabel(batch.freshness) }}
              </span>
            </div>
            <p class="detail__roast-date">{{ formatDate(batch.roast_date) }}</p>
            <p class="detail__roast-meta">
              {{ formatNumber(batch.days_since_roast) }} روز پیش · لات {{ batch.batch_code }}
            </p>
          </div>
          <div v-else-if="!isPantry" class="detail__roast detail__roast--none">
            <span class="detail__roast-label">تاریخ رست</span>
            <p class="detail__roast-meta">هنوز بچی برای این قهوه رست نشده است.</p>
          </div>
        </section>

        <!-- ------------------------------------------------ Right: the purchase -->
        <section class="detail__buy">
          <p class="detail__eyebrow">{{ product.species_display }} / {{ product.process_display }}</p>
          <h1 class="detail__title">{{ product.name }}</h1>
          <p v-if="product.subtitle" class="detail__subtitle">{{ product.subtitle }}</p>

          <ul v-if="product.flavor_notes?.length" class="detail__notes">
            <li v-for="note in product.flavor_notes" :key="note" class="detail__note">{{ note }}</li>
          </ul>

          <div class="detail__rule" aria-hidden="true" />

          <!-- A sealed pack has one size, stated rather than chosen. Offering
               a selector with a single option asks the customer to make a
               decision that does not exist. -->
          <p v-if="isPackage" class="detail__pack">
            بسته‌ی {{ formatNumber(product.package_grams) }} گرمی
          </p>
          <WeightSelector v-else v-model="weight" :options="product.price_options || []" />

          <!-- No grind for a pantry item: nothing here is ground to order. -->
          <template v-if="!isPantry">
            <div class="detail__gap" />
            <GrindSelector v-model="grind" :unavailable="unavailableGrinds" />
          </template>

          <div class="detail__rule" aria-hidden="true" />

          <!-- Quantity + total + primary action -->
          <div class="detail__order">
            <div class="detail__qty">
              <span class="detail__field-label">تعداد</span>
              <div class="detail__stepper">
                <button
                  type="button"
                  class="detail__step"
                  aria-label="کاهش"
                  :disabled="quantity <= 1"
                  @click="quantity = Math.max(1, quantity - 1)"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" stroke-width="2">
                    <path d="M3 7h8" />
                  </svg>
                </button>
                <span class="detail__qty-value" aria-live="polite">{{ formatNumber(quantity) }}</span>
                <button
                  type="button"
                  class="detail__step"
                  aria-label="افزایش"
                  :disabled="quantity >= 20"
                  @click="quantity = Math.min(20, quantity + 1)"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" stroke-width="2">
                    <path d="M3 7h8M7 3v8" />
                  </svg>
                </button>
              </div>
            </div>

            <div class="detail__total">
              <span class="detail__field-label">جمع</span>
              <p class="detail__total-value">{{ formatPrice(lineTotal) }}</p>
              <p class="detail__total-meta">
                {{ formatWeight(weight * quantity) }} · {{ product.is_in_stock ? 'موجود' : 'ناموجود' }}
              </p>
            </div>
          </div>

          <BaseButton
            variant="primary"
            size="lg"
            block
            :disabled="!product.is_in_stock"
            @click="addToCart"
          >
            {{ added ? 'به سبد اضافه شد' : product.is_in_stock ? 'افزودن به سبد خرید' : 'ناموجود' }}
          </BaseButton>

          <!-- Counted in the unit the customer actually buys. «۸ کیلوگرم
               باقی مانده» for forty sealed 200g packs is a figure nobody can
               act on, and «این لات» is a roast batch a pantry item never has. -->
          <p v-if="isPackage && product.available_packages" class="detail__stock">
            {{ formatNumber(product.available_packages) }} بسته باقی مانده است.
          </p>
          <p v-else-if="!isPackage && product.available_grams" class="detail__stock">
            {{ formatWeight(product.available_grams) }}
            {{ isPantry ? 'از این محصول' : 'از این لات' }} باقی مانده است.
          </p>
        </section>
      </div>

      <!-- ------------------------------------------------------ Below the fold -->
      <div class="detail__lower">
        <section v-if="product.description" class="detail__prose">
          <h2 class="detail__section-title">
            {{ isPantry ? 'درباره این محصول' : 'درباره این قهوه' }}
          </h2>
          <p class="detail__body-text">{{ product.description }}</p>
        </section>

        <section v-if="cupAxes.length" class="detail__profile">
          <h2 class="detail__section-title">پروفایل فنجان</h2>
          <ul class="detail__axes">
            <li v-for="axis in cupAxes" :key="axis.key" class="detail__axis">
              <span class="detail__axis-label">{{ axis.label }}</span>
              <span class="detail__scale" :aria-label="`${axis.label}: ${axis.value} از ۵`">
                <span
                  v-for="step in 5"
                  :key="step"
                  class="detail__step-block"
                  :class="{ 'detail__step-block--on': step <= axis.value }"
                  aria-hidden="true"
                />
              </span>
            </li>
          </ul>
        </section>

        <section v-if="specs.length" class="detail__specs">
          <h2 class="detail__section-title">مشخصات</h2>
          <dl class="detail__spec-list">
            <div v-for="row in specs" :key="row.label" class="detail__spec-row">
              <dt class="detail__spec-label">{{ row.label }}</dt>
              <dd class="detail__spec-value">{{ row.value }}</dd>
            </div>
          </dl>
        </section>

        <!-- Pantry items only: what is in it, and how to make it. -->
        <section v-if="product.ingredients" class="detail__specs">
          <h2 class="detail__section-title">مواد تشکیل‌دهنده</h2>
          <p class="detail__prose">{{ product.ingredients }}</p>
        </section>

        <section v-if="product.preparation" class="detail__specs">
          <h2 class="detail__section-title">روش آماده‌سازی</h2>
          <p class="detail__prose">{{ product.preparation }}</p>
        </section>

        <section v-if="catalog.batches.length" class="detail__batches">
          <h2 class="detail__section-title">بچ‌های موجود</h2>
          <ul class="detail__batch-list">
            <li v-for="b in catalog.batches" :key="b.id" class="detail__batch">
              <span class="status-light" :data-state="freshnessState(b.freshness)" />
              <span class="detail__batch-code">{{ b.batch_code }}</span>
              <span class="detail__batch-date">{{ formatDate(b.roast_date) }}</span>
              <span class="detail__batch-age">{{ freshnessLabel(b.freshness) }}</span>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </main>
</template>

<style scoped>
/* ==========================================================================
   ProductDetailView — Editorial register
   Two columns above the fold: the coffee on one side, the purchase on the
   other. Everything below is ruled prose and data.
   ========================================================================== */

.detail {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
}

.detail__loading,
.detail__missing {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  padding: 6rem 0;
}

.detail__missing {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1.5rem;
}

/* --- Breadcrumbs ----------------------------------------------------------- */
.detail__crumbs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 2.5rem;
}

.detail__crumb {
  color: var(--ink-muted);
  text-decoration: none;
  border-bottom: 2px solid transparent;
}
.detail__crumb:hover {
  color: var(--ink);
  border-bottom-color: var(--accent);
}

/* --- Layout ---------------------------------------------------------------- */
.detail__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: clamp(2rem, 5vw, 4rem);
  align-items: start;
}

@media (max-width: 56rem) {
  .detail__layout {
    grid-template-columns: 1fr;
  }
}

/* --- Plate ----------------------------------------------------------------- */
/* The plate, the image and the placeholder now live in ProductCarousel; only
   the origin tab is still owned here, slotted over the carousel's plate. */
.detail__origin-tab {
  position: absolute;
  inset-block-start: 0;
  inset-inline-start: 0;
  background-color: var(--ink);
  color: var(--paper);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.5rem 0.875rem;
}

/* --- Roast panel ----------------------------------------------------------- */
.detail__roast {
  border: 3px solid var(--ink);
  padding: 1.25rem;
  margin-top: 2.5rem;
}

.detail__roast-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.detail__roast-label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.detail__freshness {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.detail__roast-date {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0.625rem 0 0;
}

.detail__roast-meta {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
  margin: 0.375rem 0 0;
}

.detail__roast--none {
  border-color: var(--rule);
}

/* --- Buy column ------------------------------------------------------------ */
.detail__eyebrow {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.detail__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(2rem, 5vw, 3rem);
  line-height: 1.1;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.detail__subtitle {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  line-height: 1.65;
  color: var(--ink-muted);
  margin: 0.75rem 0 0;
}

.detail__notes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  list-style: none;
  padding: 0;
  margin: 1.25rem 0 0;
}

.detail__note {
  border: 2px solid var(--ink);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.25rem 0.5rem;
}

.detail__rule {
  height: 3px;
  background-color: var(--ink);
  margin: 2rem 0;
}

.detail__gap {
  height: 2rem;
}

/* --- Order row ------------------------------------------------------------- */
.detail__order {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.detail__field-label {
  display: block;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin-bottom: 0.625rem;
}

.detail__stepper {
  display: inline-flex;
  align-items: stretch;
  border: 3px solid var(--ink);
}

.detail__step {
  display: grid;
  place-items: center;
  width: 2.25rem;
  border: 0;
  background-color: var(--paper);
  color: var(--ink);
  cursor: pointer;
}

.detail__step:hover:not(:disabled) {
  background-color: var(--ink);
  color: var(--paper);
}

.detail__step:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.detail__step:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -3px;
}

.detail__qty-value {
  display: grid;
  place-items: center;
  min-width: 2.75rem;
  padding: 0.5rem 0;
  border-inline: 3px solid var(--ink);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.875rem;
  font-weight: 500;
}

.detail__total {
  text-align: end;
}

.detail__total-value {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0;
}

.detail__total-meta {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0.25rem 0 0;
}

.detail__stock {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
  margin: 1rem 0 0;
  text-align: center;
}

/* --- Lower sections -------------------------------------------------------- */
.detail__lower {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: clamp(2rem, 4vw, 3.5rem);
  margin-top: clamp(3.5rem, 8vw, 6rem);
  padding-top: 3rem;
  border-top: 3px solid var(--divider);
}

.detail__section-title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin: 0 0 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 3px solid var(--ink);
}

.detail__body-text {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  line-height: 1.85;
  margin: 0;
}

/* Cup profile: five square blocks per axis, filled to the score. */
.detail__axes {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.detail__axis {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.detail__axis-label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.detail__scale {
  display: inline-flex;
  gap: 0.25rem;
}

.detail__step-block {
  width: 1.125rem;
  height: 1.125rem;
  border: 2px solid var(--ink);
  background-color: transparent;
}

.detail__step-block--on {
  background-color: var(--accent);
}

/* Specs: a ruled definition list, not a table. */
.detail__spec-list {
  margin: 0;
}

.detail__spec-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--rule);
}

.detail__spec-label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.detail__spec-value {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  margin: 0;
  text-align: end;
}

/* Free text on a pantry item: ingredients, how to prepare it. */
.detail__prose {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.9;
  margin: 0;
  color: var(--ink-muted);
}

/* The pack size, stated where a weight selector would otherwise sit. */
.detail__pack {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  margin: 0;
  padding: 0.5rem 0.75rem;
  border: 3px solid var(--ink);
  display: inline-block;
}

/* --- Batches --------------------------------------------------------------- */
.detail__batch-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.detail__batch {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--rule);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
}

.detail__batch-code {
  font-weight: 500;
}

.detail__batch-date,
.detail__batch-age {
  color: var(--ink-muted);
}

.detail__batch-age {
  margin-inline-start: auto;
  text-transform: uppercase;
}
</style>
