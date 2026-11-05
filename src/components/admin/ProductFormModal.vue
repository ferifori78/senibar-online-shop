<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

import ProductGallery from '@/components/admin/ProductGallery.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import { useAdminStore } from '@/stores/admin'
import { formatPrice } from '@/utils/format'

const props = defineProps({
  /** Existing product to edit, or null to create a new one. */
  product: { type: Object, default: null },
})

const emit = defineEmits(['close', 'saved'])

const admin = useAdminStore()
const dialog = ref(null)
const notesText = ref('')

const PROCESSES = [
  { value: 'washed', label: 'شسته (Washed)' },
  { value: 'natural', label: 'طبیعی (Natural)' },
  { value: 'honey', label: 'عسلی (Honey)' },
  { value: 'anaerobic', label: 'بی‌هوازی (Anaerobic)' },
  { value: 'wet_hulled', label: 'Wet Hulled' },
  { value: 'other', label: 'سایر' },
]

const ROASTS = [
  { value: 'light', label: 'روشن' },
  { value: 'medium_light', label: 'روشن-متوسط' },
  { value: 'medium', label: 'متوسط' },
  { value: 'medium_dark', label: 'متوسط-تیره' },
  { value: 'dark', label: 'تیره' },
]

const SPECIES = [
  { value: 'arabica', label: 'عربیکا' },
  { value: 'robusta', label: 'روبوستا' },
  { value: 'blend', label: 'ترکیبی' },
]

// Separate from SPECIES on purpose: a blend of two arabicas is arabica *and*
// multi-origin, so the roaster answers both questions rather than one.
const ORIGIN_TYPES = [
  { value: 'single', label: 'تک‌خاستگاه' },
  { value: 'multi', label: 'چندخاستگاه' },
]

const STATUSES = [
  { value: 'draft', label: 'پیش‌نویس' },
  { value: 'published', label: 'منتشر شده' },
  { value: 'archived', label: 'بایگانی' },
]

const AXES = [
  { key: 'acidity', label: 'اسیدیته' },
  { key: 'body', label: 'بادی' },
  { key: 'sweetness', label: 'شیرینی' },
  { key: 'bitterness', label: 'تلخی' },
]

const form = reactive({
  // `lot` — a single-origin coffee, roasted in batches.
  // `pantry` — masala, instant coffee, hot chocolate: no roast, no grind,
  // no cup profile, and stock kept on the product itself.
  kind: 'lot',
  name: '',
  subtitle: '',
  description: '',
  origin_country: '',
  origin_region: '',
  farm: '',
  producer: '',
  varietal: '',
  altitude_masl: null,
  harvest_year: null,
  species: 'arabica',
  origin_type: 'single',
  process: 'washed',
  processes_extra: [],
  roast_level: 'medium',
  roast_levels_extra: [],
  cupping_score: null,
  acidity: 3,
  body: 3,
  sweetness: 3,
  bitterness: 3,
  price_per_250g: null,
  is_espresso_suitable: true,
  is_filter_suitable: true,
  status: 'draft',
  is_featured: false,

  // --- Pantry items ---
  brand: '',
  production_year: null,
  best_before: null,
  ingredients: '',
  preparation: '',
  sale_mode: 'package',
  package_grams: null,
  package_price: null,
  stock_packages: 0,
  stock_grams: 0,
  low_stock_threshold: 0,
})

/** A pantry item hides everything a roasted lot has and nothing else does. */
const isPantry = computed(() => form.kind === 'pantry')
const byPackage = computed(() => isPantry.value && form.sale_mode === 'package')

/** True until the full record has been read back for an edit. */
const loading = ref(false)

/** What the server currently holds, so `submit` can send only real changes. */
const original = ref({})

function fill(source) {
  for (const key of Object.keys(form)) {
    if (source[key] !== undefined && source[key] !== null) {
      form[key] = source[key]
    }
  }
  notesText.value = (source.flavor_notes || []).join('، ')
  original.value = { ...source }
}

/**
 * Load the product being edited.
 *
 * The row handed in by the list is the LIST payload, which carries about half
 * the fields the form has. Filling the form from it left description, farm,
 * varietal, the sensory axes and the rest at their blank defaults — and saving
 * then wrote those blanks over real data. So the full record is fetched first,
 * and the form stays disabled until it arrives.
 */
async function hydrate() {
  if (!props.product) return
  fill(props.product)

  if (!props.product.slug) return
  loading.value = true
  const { ok, data } = await admin.fetchProduct(props.product.slug)
  loading.value = false
  if (ok) fill(data)
}

/*
 * Process and roast are stored as a primary value plus a list of extras — the
 * primary is what every storefront card and filter already reads. The roaster
 * should not have to think about that split, so the UI is one flat set of
 * toggles and the first selected value is treated as the primary.
 */
function selected(primaryKey, extraKey) {
  return [form[primaryKey], ...form[extraKey]].filter(Boolean)
}

function toggle(primaryKey, extraKey, value) {
  const current = selected(primaryKey, extraKey)
  const next = current.includes(value)
    ? current.filter((v) => v !== value)
    : [...current, value]

  // At least one must remain: the primary column cannot be empty.
  if (!next.length) return

  form[primaryKey] = next[0]
  form[extraKey] = next.slice(1)
}

const processSelection = computed(() => selected('process', 'processes_extra'))
const roastSelection = computed(() => selected('roast_level', 'roast_levels_extra'))

/** Notes are typed as free text and stored as a list. */
function parseNotes() {
  return notesText.value
    .split(/[،,]/)
    .map((n) => n.trim())
    .filter(Boolean)
}

const localErrors = ref({})

function validate() {
  const errors = {}
  if (!form.name.trim()) errors.name = 'نام لازم است.'
  if (!form.origin_country.trim()) errors.origin_country = 'کشور مبدأ لازم است.'

  // A package item is priced per pack, so the 250g figure is meaningless for
  // it — requiring it here would make every masala impossible to save.
  if (byPackage.value) {
    if (!form.package_price || Number(form.package_price) <= 0) {
      errors.package_price = 'قیمت بسته باید بزرگ‌تر از صفر باشد.'
    }
    if (!form.package_grams || Number(form.package_grams) <= 0) {
      errors.package_grams = 'وزن بسته را وارد کنید.'
    }
  } else if (!form.price_per_250g || Number(form.price_per_250g) <= 0) {
    errors.price_per_250g = 'قیمت باید بزرگ‌تر از صفر باشد.'
  }

  if (form.cupping_score && (form.cupping_score < 0 || form.cupping_score > 100)) {
    errors.cupping_score = 'امتیاز باید بین ۰ و ۱۰۰ باشد.'
  }
  localErrors.value = errors
  return Object.keys(errors).length === 0
}

function errorFor(field) {
  return admin.fieldErrors[field] || localErrors.value[field] || ''
}

async function submit() {
  localErrors.value = {}
  if (!validate()) return

  let payload = { ...form, flavor_notes: parseNotes() }
  // Blank optional numbers and dates must go as null, not "" — DRF rejects an
  // empty string for an IntegerField or a DateField.
  for (const key of [
    'altitude_masl', 'harvest_year', 'cupping_score',
    'production_year', 'package_grams', 'package_price', 'best_before',
  ]) {
    if (payload[key] === '' || payload[key] === null) payload[key] = null
  }
  // price_per_250g is non-null on the model; a package item that never fills
  // it in would send null and fail. Zero is the honest value: it is not used.
  if (byPackage.value && !payload.price_per_250g) payload.price_per_250g = 0

  // Editing sends only what actually changed. The update is a PATCH, so an
  // untouched field is left alone by the server rather than overwritten —
  // which means a gap in the payload can never silently blank a column again.
  if (props.product?.slug) {
    const changed = {}
    for (const [key, value] of Object.entries(payload)) {
      const before = original.value[key]
      const same =
        Array.isArray(value) && Array.isArray(before)
          ? JSON.stringify(value) === JSON.stringify(before)
          : String(value ?? '') === String(before ?? '')
      if (!same) changed[key] = value
    }
    if (!Object.keys(changed).length) {
      emit('close')
      return
    }
    payload = changed
  }

  const { ok, data } = await admin.saveProduct(payload, props.product?.slug || null)
  if (ok) emit('saved', data)
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  hydrate()
  document.addEventListener('keydown', onKeydown)
  requestAnimationFrame(() => dialog.value?.focus())
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  admin.resetErrors()
})

watch(() => props.product, hydrate)
</script>

<template>
  <div class="scrim" @click.self="emit('close')">
    <form
      ref="dialog"
      class="modal"
      role="dialog"
      aria-modal="true"
      :aria-label="product ? 'ویرایش محصول' : 'محصول جدید'"
      tabindex="-1"
      novalidate
      @submit.prevent="submit"
    >
      <header class="modal__head">
        <span class="modal__title">
          {{ product ? `EDIT — ${product.name}` : 'NEW PRODUCT' }}
        </span>
        <button type="button" class="modal__close" aria-label="بستن" @click="emit('close')">
          <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" stroke-width="2">
            <path d="M2 2l10 10M12 2L2 12" />
          </svg>
        </button>
      </header>

      <div class="modal__body">
        <p v-if="admin.error" class="modal__err" role="alert">{{ admin.error }}</p>

        <!-- Editing is blocked until the full record arrives: typing into a
             field that is about to be overwritten loses the typing. -->
        <p v-if="loading" class="modal__loading">در حال خواندن اطلاعات محصول…</p>
        <fieldset class="plain" :disabled="loading">

        <!-- Kind -------------------------------------------------------- -->
        <!-- First, because it decides which of the sections below exist at
             all. Two buttons rather than a select: there are exactly two,
             and the choice changes the shape of the form enough that it
             should be visible, not hidden in a dropdown. -->
        <fieldset class="set">
          <legend class="set__legend">نوع محصول</legend>
          <div class="kind">
            <button
              v-for="option in [
                { value: 'lot', label: 'قهوه تک‌مبدأ', hint: 'رست، بچ، پروفایل فنجان' },
                { value: 'pantry', label: 'محصول انبار', hint: 'ماسالا، گلد، هات‌چاکلت' },
              ]"
              :key="option.value"
              type="button"
              class="kind__btn"
              :class="{ 'kind__btn--on': form.kind === option.value }"
              :aria-pressed="form.kind === option.value"
              @click="form.kind = option.value"
            >
              <span class="kind__label">{{ option.label }}</span>
              <span class="kind__hint">{{ option.hint }}</span>
            </button>
          </div>
        </fieldset>

        <!-- Identity ---------------------------------------------------- -->
        <fieldset class="set">
          <legend class="set__legend">شناسه</legend>
          <div class="set__grid">
            <label class="f f--wide">
              <span class="f__label">نام<i>*</i></span>
              <input v-model="form.name" class="f__input" :class="{ 'f__input--err': errorFor('name') }" />
              <span v-if="errorFor('name')" class="f__err">{{ errorFor('name') }}</span>
            </label>

            <label class="f f--wide">
              <span class="f__label">زیرعنوان</span>
              <input v-model="form.subtitle" class="f__input" />
            </label>

            <label class="f f--full">
              <span class="f__label">توضیحات</span>
              <textarea v-model="form.description" class="f__input f__textarea" rows="3" />
            </label>
          </div>
        </fieldset>

        <!-- Origin ------------------------------------------------------ -->
        <fieldset class="set">
          <legend class="set__legend">مبدأ</legend>
          <div class="set__grid">
            <label class="f">
              <span class="f__label">کشور<i>*</i></span>
              <input
                v-model="form.origin_country"
                class="f__input"
                :class="{ 'f__input--err': errorFor('origin_country') }"
              />
              <span v-if="errorFor('origin_country')" class="f__err">
                {{ errorFor('origin_country') }}
              </span>
            </label>

            <!-- A pantry item is usually somebody else's product, so it has
                 a brand where a lot has a farm. -->
            <label v-if="isPantry" class="f">
              <span class="f__label">برند</span>
              <input v-model="form.brand" class="f__input" />
            </label>

            <label v-if="isPantry" class="f">
              <span class="f__label">سال تولید</span>
              <input v-digits v-model.number="form.production_year" type="number" class="f__input" />
            </label>

            <label v-if="isPantry" class="f">
              <span class="f__label">تاریخ انقضا</span>
              <input v-model="form.best_before" type="date" class="f__input" />
            </label>

            <label v-if="!isPantry" class="f">
              <span class="f__label">منطقه</span>
              <input v-model="form.origin_region" class="f__input" />
            </label>

            <label v-if="!isPantry" class="f">
              <span class="f__label">مزرعه</span>
              <input v-model="form.farm" class="f__input" />
            </label>

            <template v-if="!isPantry">
              <label class="f">
                <span class="f__label">تولیدکننده</span>
                <input v-model="form.producer" class="f__input" />
              </label>

              <label class="f">
                <span class="f__label">واریته</span>
                <input v-model="form.varietal" class="f__input" />
              </label>

              <label class="f">
                <span class="f__label">ارتفاع (متر)</span>
                <input v-digits v-model.number="form.altitude_masl" type="number" class="f__input" />
              </label>

              <label class="f">
                <span class="f__label">سال برداشت</span>
                <input v-digits v-model.number="form.harvest_year" type="number" class="f__input" />
              </label>
            </template>
          </div>
        </fieldset>

        <!-- Pantry detail ----------------------------------------------- -->
        <fieldset v-if="isPantry" class="set">
          <legend class="set__legend">مشخصات</legend>
          <div class="set__grid">
            <label class="f f--full">
              <span class="f__label">مواد تشکیل‌دهنده</span>
              <textarea v-model="form.ingredients" class="f__input f__textarea" rows="2" />
            </label>

            <label class="f f--full">
              <span class="f__label">روش آماده‌سازی</span>
              <textarea
                v-model="form.preparation"
                class="f__input f__textarea"
                rows="2"
                placeholder="مثلاً: یک قاشق در ۲۰۰ میلی‌لیتر شیر داغ"
              />
            </label>
          </div>
        </fieldset>

        <!-- Pantry stock ------------------------------------------------ -->
        <fieldset v-if="isPantry" class="set">
          <legend class="set__legend">موجودی و قیمت</legend>
          <div class="set__grid">
            <label class="f f--wide">
              <span class="f__label">نحوه فروش</span>
              <select v-model="form.sale_mode" class="f__input">
                <option value="package">بسته‌ای — مشتری تعداد بسته می‌خرد</option>
                <option value="weight">وزنی — مشتری وزن انتخاب می‌کند</option>
              </select>
            </label>

            <template v-if="byPackage">
              <label class="f">
                <span class="f__label">وزن هر بسته (گرم)<i>*</i></span>
                <input
                  v-digits v-model.number="form.package_grams" type="number" min="1"
                  class="f__input" :class="{ 'f__input--err': errorFor('package_grams') }"
                />
                <span v-if="errorFor('package_grams')" class="f__err">
                  {{ errorFor('package_grams') }}
                </span>
              </label>

              <label class="f">
                <span class="f__label">قیمت هر بسته (ریال)<i>*</i></span>
                <input
                  v-digits v-model.number="form.package_price" type="number" min="0"
                  class="f__input" :class="{ 'f__input--err': errorFor('package_price') }"
                />
                <span v-if="errorFor('package_price')" class="f__err">
                  {{ errorFor('package_price') }}
                </span>
              </label>

              <label class="f">
                <span class="f__label">تعداد موجود در انبار</span>
                <input v-digits v-model.number="form.stock_packages" type="number" min="0" class="f__input" />
                <span class="f__hint">بسته</span>
              </label>
            </template>

            <template v-else>
              <label class="f">
                <span class="f__label">قیمت هر ۲۵۰ گرم (ریال)<i>*</i></span>
                <input v-digits v-model.number="form.price_per_250g" type="number" min="0" class="f__input" />
              </label>

              <label class="f">
                <span class="f__label">موجودی انبار (گرم)</span>
                <input v-digits v-model.number="form.stock_grams" type="number" min="0" class="f__input" />
                <span class="f__hint">۱۰ کیلو = ۱۰۰۰۰ گرم</span>
              </label>
            </template>

            <label class="f">
              <span class="f__label">هشدار کمبود موجودی</span>
              <input v-digits v-model.number="form.low_stock_threshold" type="number" min="0" class="f__input" />
              <span class="f__hint">
                {{ byPackage ? 'زیر این تعداد بسته هشدار بده' : 'زیر این مقدار گرم هشدار بده' }} — ۰ یعنی بدون هشدار
              </span>
            </label>
          </div>
        </fieldset>

        <!-- Cup profile ------------------------------------------------- -->
        <!-- Hidden for pantry items: masala has no cupping score, and the
             four axes are what the taste quiz scores on. -->
        <fieldset v-if="!isPantry" class="set">
          <legend class="set__legend">پروفایل فنجان</legend>
          <div class="set__grid">
            <label class="f">
              <span class="f__label">گونه</span>
              <select v-model="form.species" class="f__input">
                <option v-for="o in SPECIES" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </label>

            <label class="f">
              <span class="f__label">خاستگاه</span>
              <select v-model="form.origin_type" class="f__input">
                <option v-for="o in ORIGIN_TYPES" :key="o.value" :value="o.value">
                  {{ o.label }}
                </option>
              </select>
            </label>

            <div class="f f--full">
              <span class="f__label">پروسس — چند مورد قابل انتخاب است</span>
              <div class="checks checks--wrap">
                <button
                  v-for="o in PROCESSES"
                  :key="o.value"
                  type="button"
                  class="check"
                  :class="{ 'check--on': processSelection.includes(o.value) }"
                  :aria-pressed="processSelection.includes(o.value)"
                  @click="toggle('process', 'processes_extra', o.value)"
                >
                  <span class="check__box" aria-hidden="true" />
                  {{ o.label }}
                </button>
              </div>
              <span class="f__hint">
                اولین مورد انتخاب‌شده، پروسس اصلی است و روی کارت محصول نمایش داده می‌شود.
              </span>
            </div>

            <div class="f f--full">
              <span class="f__label">درجه رست — چند مورد قابل انتخاب است</span>
              <div class="checks checks--wrap">
                <button
                  v-for="o in ROASTS"
                  :key="o.value"
                  type="button"
                  class="check"
                  :class="{ 'check--on': roastSelection.includes(o.value) }"
                  :aria-pressed="roastSelection.includes(o.value)"
                  @click="toggle('roast_level', 'roast_levels_extra', o.value)"
                >
                  <span class="check__box" aria-hidden="true" />
                  {{ o.label }}
                </button>
              </div>
            </div>

            <label class="f">
              <span class="f__label">امتیاز کاپینگ</span>
              <input
                v-digits
                v-model.number="form.cupping_score"
                type="number"
                step="0.5"
                class="f__input"
                :class="{ 'f__input--err': errorFor('cupping_score') }"
              />
              <span v-if="errorFor('cupping_score')" class="f__err">
                {{ errorFor('cupping_score') }}
              </span>
            </label>

            <label class="f f--full">
              <span class="f__label">نت‌های طعمی</span>
              <input
                v-model="notesText"
                class="f__input"
                placeholder="یاس، برگاموت، هلو — با ویرگول جدا کنید"
              />
            </label>
          </div>

          <!-- Sensory axes: square step blocks, filled with accent. -->
          <div class="axes">
            <div v-for="axis in AXES" :key="axis.key" class="axis">
              <span class="axis__label">{{ axis.label }}</span>
              <div class="axis__steps" role="radiogroup" :aria-label="axis.label">
                <button
                  v-for="step in 5"
                  :key="step"
                  type="button"
                  role="radio"
                  class="axis__step"
                  :class="{ 'axis__step--on': step <= form[axis.key] }"
                  :aria-checked="step === form[axis.key]"
                  :aria-label="`${axis.label} ${step}`"
                  @click="form[axis.key] = step"
                />
              </div>
            </div>
          </div>
        </fieldset>

        <!-- Commerce ---------------------------------------------------- -->
        <fieldset class="set">
          <legend class="set__legend">فروش</legend>
          <div class="set__grid">
            <label v-if="!isPantry" class="f">
              <span class="f__label">قیمت ۲۵۰ گرم (ریال)<i>*</i></span>
              <input
                v-digits
                v-model.number="form.price_per_250g"
                type="number"
                class="f__input"
                :class="{ 'f__input--err': errorFor('price_per_250g') }"
              />
              <!-- Prices are charged in rial. Echoing the toman figure back is
                   what stops a rial amount being typed as though it were
                   toman — a tenfold undercharge that only shows up at the
                   gateway. -->
              <span v-if="form.price_per_250g > 0" class="f__hint">
                = {{ formatPrice(form.price_per_250g) }}
              </span>
              <span v-if="errorFor('price_per_250g')" class="f__err">
                {{ errorFor('price_per_250g') }}
              </span>
            </label>

            <label class="f">
              <span class="f__label">وضعیت</span>
              <select v-model="form.status" class="f__input">
                <option v-for="o in STATUSES" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </label>

            <div class="f f--full">
              <span class="f__label">صفحه‌ی خانه</span>
              <div class="checks">
                <button
                  type="button"
                  class="check"
                  :class="{ 'check--on': form.is_featured }"
                  :aria-pressed="form.is_featured"
                  @click="form.is_featured = !form.is_featured"
                >
                  در «محصولات پیشنهادی صنوبر» نمایش داده شود
                </button>
              </div>
              <span class="f__hint">
                تا وقتی هیچ محصولی انتخاب نشده باشد، صفحه‌ی خانه سه لات تازه را
                نشان می‌دهد. حداکثر سه محصول نمایش داده می‌شود.
              </span>
            </div>

            <div class="f f--full">
              <span class="f__label">مناسب برای</span>
              <div class="checks">
                <button
                  type="button"
                  class="check"
                  :class="{ 'check--on': form.is_espresso_suitable }"
                  :aria-pressed="form.is_espresso_suitable"
                  @click="form.is_espresso_suitable = !form.is_espresso_suitable"
                >
                  <span class="check__box" aria-hidden="true" />
                  اسپرسو
                </button>

                <button
                  type="button"
                  class="check"
                  :class="{ 'check--on': form.is_filter_suitable }"
                  :aria-pressed="form.is_filter_suitable"
                  @click="form.is_filter_suitable = !form.is_filter_suitable"
                >
                  <span class="check__box" aria-hidden="true" />
                  فیلتر
                </button>
              </div>
              <span class="f__hint">
                غیرفعال کردن اسپرسو، گزینه‌های اسپرسو و ترک را از انتخابگر آسیاب حذف می‌کند.
              </span>
            </div>
          </div>
        </fieldset>

        <!-- Gallery ------------------------------------------------------ -->
        <fieldset class="set">
          <legend class="set__legend">تصویرها</legend>
          <ProductGallery :slug="product?.slug || null" />
        </fieldset>
        </fieldset>
      </div>

      <footer class="modal__foot">
        <BaseButton type="submit" variant="primary" size="sm" inverse :loading="admin.acting">
          {{ product ? 'ذخیره تغییرات' : 'ساخت محصول' }}
        </BaseButton>
        <BaseButton
          type="button"
          variant="ghost"
          size="sm"
          inverse
          :disabled="admin.acting"
          @click="emit('close')"
        >
          انصراف
        </BaseButton>
      </footer>
    </form>
  </div>
</template>

<style scoped>
/* ==========================================================================
   ProductFormModal — Terminal register
   ========================================================================== */

.scrim {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.7);
  display: grid;
  place-items: center;
  padding: 1.5rem;
  z-index: 50;
  overflow-y: auto;
}

.modal {
  width: 100%;
  max-width: 48rem;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background-color: var(--terminal);
  color: var(--terminal-text);
  border: 3px solid var(--terminal-text);
  box-shadow: 10px 10px 0 var(--accent);
}

.modal:focus {
  outline: none;
}

.modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1rem;
  border-bottom: 3px solid var(--terminal-text);
}

.modal__title {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 600;
}

.modal__close {
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border: 2px solid var(--terminal-text);
  background: none;
  color: var(--terminal-text);
  cursor: pointer;
}

.modal__close:hover {
  background-color: var(--terminal-text);
  color: var(--terminal);
}

.modal__body {
  padding: 1rem;
  overflow-y: auto;
  flex: 1;
}

.modal__err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  padding: 0.625rem 0.75rem;
  margin: 0 0 1rem;
}

.modal__loading {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  color: var(--accent);
  margin: 0 0 1rem;
}

/* Wraps the whole form so one `disabled` covers every control. Carries no
   look of its own — the real fieldsets below do the visual work. */
.plain {
  border: 0;
  padding: 0;
  margin: 0;
  min-inline-size: 0;
}

.plain:disabled {
  opacity: 0.55;
}

/* --- Fieldsets ------------------------------------------------------------- */
.set {
  border: 0;
  border-top: 1px solid var(--terminal-rule);
  padding: 1rem 0 0;
  margin: 0 0 1.25rem;
  min-inline-size: 0;
}

.set:first-of-type {
  border-top: 0;
  padding-top: 0;
}

.set__legend {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
  padding: 0;
  margin-bottom: 0.75rem;
}

/* --- Kind toggle ---------------------------------------------------------
   Two hard-edged panels rather than a select: the choice reshapes the form
   below it, so it should be visible at a glance. */
.kind {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.kind__btn {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  align-items: flex-start;
  padding: 0.75rem 0.875rem;
  border: 3px solid var(--terminal-rule);
  border-radius: 0;
  background: none;
  color: var(--terminal-text);
  cursor: pointer;
  text-align: start;
}

.kind__btn--on {
  background-color: var(--accent);
  color: var(--paper);
  border-color: var(--accent);
}

.kind__btn:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

.kind__label {
  font-family: var(--font-editorial);
  font-size: 0.9375rem;
  font-weight: 600;
}

.kind__hint {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  opacity: 0.75;
}

@media (max-width: 34rem) {
  .kind {
    grid-template-columns: minmax(0, 1fr);
  }
}

.set__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.75rem;
}

.f {
  display: flex;
  flex-direction: column;
  gap: 0.3125rem;
  min-width: 0;
}

.f--wide {
  grid-column: span 2;
}

.f--full {
  grid-column: 1 / -1;
}

@media (max-width: 34rem) {
  .f--wide,
  .f--full {
    grid-column: auto;
  }
}

.f__label {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--terminal-dim);
}

.f__label i {
  color: var(--accent);
  font-style: normal;
  margin-inline-start: 0.1875rem;
}

.f__input {
  width: 100%;
  border: 2px solid var(--terminal-rule);
  background-color: var(--terminal);
  color: var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  padding: 0.4375rem 0.5rem;
}

.f__input::placeholder {
  color: var(--terminal-dim);
}

.f__input:focus {
  outline: none;
  border-color: var(--terminal-text);
  box-shadow: 3px 3px 0 var(--accent);
}

.f__input--err {
  border-color: #a33224;
}

.f__textarea {
  resize: vertical;
  line-height: 1.6;
}

.f__err {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  color: #d4614f;
}

.f__hint {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  line-height: 1.5;
  color: var(--terminal-dim);
}

/* --- Sensory axes ---------------------------------------------------------- */
.axes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
}

.axis {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.axis__label {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--terminal-dim);
}

.axis__steps {
  display: flex;
  gap: 0.25rem;
}

.axis__step {
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid var(--terminal-rule);
  background: none;
  cursor: pointer;
  padding: 0;
}

.axis__step--on {
  background-color: var(--accent);
  border-color: var(--accent);
}

.axis__step:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- Checks: square toggles, never round ----------------------------------- */
.checks {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

/* A row of many options needs more room between them than a pair does. */
.checks--wrap {
  gap: 0.5rem 1.25rem;
}

.check {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  border: 0;
  background: none;
  color: var(--terminal-dim);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  cursor: pointer;
  padding: 0;
}

.check--on {
  color: var(--terminal-text);
}

.check__box {
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid var(--terminal-rule);
}

.check--on .check__box {
  background-color: var(--accent);
  border-color: var(--accent);
}

.check:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- Foot ------------------------------------------------------------------ */
.modal__foot {
  display: flex;
  gap: 0.75rem;
  padding: 1rem;
  border-top: 3px solid var(--terminal-text);
}
</style>
