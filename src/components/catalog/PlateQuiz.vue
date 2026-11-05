<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import CoffeeGlyph from '@/components/base/CoffeeGlyph.vue'
import VowelledText from '@/components/base/VowelledText.vue'
import { catalogApi } from '@/api/catalog'
import { parseApiError } from '@/api/client'
import { formatNumber, formatPrice } from '@/utils/format'

/*
 * The specimen plate, doing the work of the taste questionnaire.
 *
 * At rest it is exactly the plate it always was — a 3x3 sheet of coffee
 * glyphs around the shop's name. Started, the centre cell carries the
 * question and the surrounding cells become its answers, so the grid that was
 * decoration turns into the thing itself. Answered cells stay filled, which
 * makes the plate its own progress bar: no extra element is added to the page
 * to show how far along the reader is.
 */

// Where the glyphs sit at rest. Two cells are deliberately empty so the sheet
// breathes and the eye is not asked to read eight things at once.
const PLATE = [
  { n: 1, glyph: 'bean' },
  { n: 2, glyph: null },
  { n: 3, glyph: 'cherry' },
  { n: 4, glyph: 'dripper' },
  { n: 5, center: true },
  { n: 6, glyph: 'moka' },
  { n: 7, glyph: 'cup' },
  // Directly under the name, and empty at rest: the invitation goes here
  // rather than in the caption, so the thing you click sits inside the plate
  // it is about instead of beneath it in the small print.
  { n: 8, glyph: null, invite: true },
  { n: 9, glyph: 'portafilter' },
]

/*
 * A cell is a small square, and Persian option labels run long. These are the
 * short forms used inside the grid; the full label from the server stays as
 * the title, so nothing is lost to someone who hovers or reads slowly.
 */
const SHORT = {
  espresso: 'اسپرسو',
  filter: 'فیلتر',
  french_press: 'فرنچ‌پرس',
  unsure: 'نمی‌دانم',
  black: 'ساده',
  milk: 'با شیر',
  both: 'هر دو',
  fruity: 'میوه‌ای',
  sweet: 'شیرین',
  chocolate: 'شکلاتی',
  unusual: 'غیرمنتظره',
  love: 'زیاد',
  some: 'کمی',
  avoid: 'نه',
  light: 'سبک',
  medium: 'متعادل',
  heavy: 'سنگین',
  classic: 'کلاسیک',
  open: 'باز',
  adventurous: 'ماجراجو',
}

function shortLabel(option) {
  return SHORT[option.value] || option.label
}

const questions = ref([])
const answers = ref({})
const index = ref(0)
const results = ref(null)
const loading = ref(false)
const error = ref('')
const started = ref(false)

const current = computed(() => questions.value[index.value] || null)
const total = computed(() => questions.value.length)
const isLast = computed(() => index.value === total.value - 1)

/*
 * The eight cells around the centre, filled with this question's options.
 *
 * Options are laid into the cells the glyphs occupied, in order; anything
 * left over stays an empty cell rather than being padded with something to
 * click. A question has three or four options, so most of the sheet stays
 * open — which is what it looked like at rest.
 */
/*
 * Where options go, in order. Not simply "every cell except the centre":
 * filling left-to-right leaves a question with four options scattered across
 * the top row and one side, with three empty cells beneath — which reads as
 * a mistake rather than as breathing room.
 *
 * Instead they ring the centre, starting at its right (the start edge in an
 * RTL layout) and going round. Three or four options — which every question
 * has — then sit adjacent to the question they answer.
 *
 *   0 1 2      the ring order, by cell index:
 *   3 · 5        5 (right of centre), 2, 1, 0, 3, 6, 7, 8
 *   6 7 8
 *
 * This is the pool the options are dealt into; which one lands where is
 * shuffled below.
 */
const OUTER = [5, 2, 1, 0, 3, 6, 7, 8]

/*
 * ...and then shuffled, so the options scatter across the sheet instead of
 * arriving in the same arc every time.
 *
 * The draw is taken from the ring rather than from all eight cells: the ring
 * is the set that sits adjacent to the question, so shuffling within it moves
 * the options around without ever stranding one in a far corner.
 *
 * It is computed once per question and cached, not on every render. A
 * `computed` that called Math.random() would deal a new hand on any unrelated
 * re-render — the option under the reader's cursor would move as they clicked
 * it — and going back a step would show a question they had already answered
 * rearranged, which reads as a different question.
 */
const layouts = ref({})

function shuffled(n) {
  const slots = OUTER.slice(0, n)
  for (let i = slots.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[slots[i], slots[j]] = [slots[j], slots[i]]
  }
  return slots
}

/*
 * Dealt here, on the way in to a question — never from inside the `cells`
 * computed. A computed that writes to a ref it also reads is a side effect in
 * a cache: Vue holds the value it produced, and a second run of the quiz
 * re-renders from that cache instead of re-dealing. It shuffled correctly on
 * a fresh page load and repeated the same arrangement on every restart after
 * it, which is exactly the shape that bug takes. Found in a browser; the unit
 * tests could not see it, since each mounts a new component.
 */
function deal(question) {
  if (!question || layouts.value[question.key]) return
  layouts.value = {
    ...layouts.value,
    [question.key]: shuffled(question.options.length),
  }
}

// Every path that lands on a question deals it: starting, moving on, going
// back. Watching `current` catches all three in one place.
watch(current, (question) => deal(question), { immediate: true })

const cells = computed(() => {
  const out = PLATE.map((cell) => ({ ...cell, option: null }))
  if (!started.value || !current.value) return out

  const slots = layouts.value[current.value.key] || OUTER
  current.value.options.forEach((option, i) => {
    const slot = slots[i]
    // `rank` is the option's place in the question, kept alongside the cell
    // it occupies: the square can hold them in any arrangement, but a column
    // needs first-to-last, and only the rank knows which is which.
    if (slot !== undefined) Object.assign(out[slot], { option, rank: i })
  })
  return out
})

onMounted(async () => {
  try {
    const { data } = await catalogApi.quiz()
    questions.value = data.questions || []
  } catch (err) {
    error.value = parseApiError(err).message
  }
})

function begin() {
  if (!questions.value.length) return
  started.value = true
  index.value = 0
  results.value = null
  answers.value = {}
  // Cleared so a second run deals a new arrangement rather than replaying the
  // first one. Within a run the layout is held, so stepping back shows the
  // question exactly as it was answered.
  layouts.value = {}
  // Dealt here rather than left to the watcher: restarting returns to question
  // zero, so `current` often does not change and the watcher never fires. That
  // is the difference between a fresh page load, which reshuffles, and a
  // restart in place, which would not.
  deal(current.value)
  error.value = ''
}

async function choose(option) {
  if (!option) return
  answers.value = { ...answers.value, [current.value.key]: option.value }

  if (!isLast.value) {
    index.value += 1
    return
  }
  await submit()
}

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await catalogApi.recommend(answers.value)
    results.value = data
  } catch (err) {
    error.value = parseApiError(err).message
  } finally {
    loading.value = false
  }
}

function back() {
  if (index.value > 0) index.value -= 1
}

function reset() {
  started.value = false
  results.value = null
  answers.value = {}
  layouts.value = {}
  index.value = 0
  error.value = ''
}

/*
 * A score is not a promise. Below this the coffee is offered as the nearest
 * thing we have rather than as an answer, and its mismatches are shown.
 */
const STRONG = 75

function isStrong(item) {
  return item.score >= STRONG
}

const topIsWeak = computed(
  () => results.value?.results?.length && !isStrong(results.value.results[0]),
)

/** The label under the plate changes with what the plate is doing. */
const plateLabel = computed(() => {
  if (results.value) return 'YOUR MATCH / پیشنهاد ما'
  if (started.value) return `QUESTION ${index.value + 1} OF ${total.value}`
  return 'SMALL BATCH / ROASTED TO ORDER'
})
</script>

<template>
  <div class="plate" :class="{ 'plate--busy': started }">
    <!-- Results replace the grid entirely: three coffees will not fit in a
         3x3 sheet, and cramming them in would make both unreadable. -->
    <div v-if="results" class="picks">
      <p v-if="!results.results.length" class="picks__none">
        هنوز قهوه‌ای برای پیشنهاد نداریم.
        <RouterLink to="/products" class="picks__link">کاتالوگ را ببینید</RouterLink>
      </p>

      <template v-else>
        <p class="picks__verdict">
          {{
            topIsWeak
              ? 'دقیقاً چنین قهوه‌ای نداریم، ولی این‌ها نزدیک‌ترین‌اند:'
              : 'بر اساس ذائقه‌تان:'
          }}
        </p>

        <ol class="picks__list">
          <li v-for="(item, i) in results.results" :key="item.product.slug" class="pick">
            <div class="pick__head">
              <RouterLink :to="`/products/${item.product.slug}`" class="pick__name">
                {{ item.product.name }}
              </RouterLink>
              <span class="pick__score" :class="{ 'pick__score--weak': !isStrong(item) }">
                {{ formatNumber(Math.round(item.score)) }}٪
              </span>
            </div>

            <p class="pick__origin">
              {{ item.product.origin_country }} — {{ formatPrice(item.product.price_per_250g) }}
            </p>

            <ul v-if="item.reasons.length" class="pick__reasons">
              <li v-for="reason in item.reasons.slice(0, 3)" :key="reason">{{ reason }}</li>
            </ul>
            <!-- Shown, not hidden: a recommendation that lists only what is
                 good about a coffee is advertising, not advice. -->
            <ul v-if="item.against.length" class="pick__against">
              <li v-for="note in item.against" :key="note">{{ note }}</li>
            </ul>

            <RouterLink :to="`/products/${item.product.slug}`" class="pick__cta">
              <BaseButton
                :variant="i === 0 && item.product.is_in_stock ? 'primary' : 'secondary'"
                size="sm"
              >
                {{ item.product.is_in_stock ? 'دیدن و خرید' : 'دیدن این قهوه' }}
              </BaseButton>
            </RouterLink>
          </li>
        </ol>
      </template>

      <button type="button" class="plate__again" @click="reset">از نو</button>
    </div>

    <!-- The sheet itself: at rest a specimen plate, started a questionnaire. -->
    <div v-else class="plate__grid">
      <template v-for="cell in cells" :key="cell.n">
        <!-- Centre: the name at rest, the question once started. -->
        <div v-if="cell.center" class="cell cell--centre">
          <VowelledText
            v-if="!started"
            class="cell__name"
            text="صِنوبَر"
            :scale="1.5"
            face="display"
          />
          <p v-else class="cell__question">{{ current?.title }}</p>
        </div>

        <!-- An answer. -->
        <button
          v-else-if="cell.option"
          type="button"
          class="cell cell--option"
          :class="{ 'cell--picked': answers[current.key] === cell.option.value }"
          :style="{ '--rank': cell.rank }"
          :title="cell.option.label"
          :disabled="loading"
          @click="choose(cell.option)"
        >
          <span class="cell__label">{{ shortLabel(cell.option) }}</span>
          <!-- The full wording, for anyone the short form does not serve. -->
          <span class="cell__full">{{ cell.option.label }}</span>
        </button>

        <!-- At rest, the cell under the name asks the question that starts
             the whole thing. Once started it is an ordinary cell again. -->
        <button
          v-else-if="cell.invite && !started"
          type="button"
          class="cell cell--invite plate__start"
          :disabled="!questions.length"
          @click="begin"
        >
          کدام قهوه مالِ شماست؟
        </button>

        <!-- At rest: a glyph, or one of the two deliberately empty cells. -->
        <div v-else class="cell">
          <CoffeeGlyph v-if="!started && cell.glyph" :name="cell.glyph" class="cell__glyph" />
        </div>
      </template>
    </div>

    <!-- The plate's own caption, doubling as the step counter. -->
    <p class="plate__label">
      <span>{{ plateLabel }}</span>
      <!-- The invitation used to live here; it is inside the plate now. What
           stays is the step counter and the way back. -->
      <button v-if="started && !results && index > 0" type="button" class="plate__back" @click="back">
        قبلی
      </button>
    </p>

    <p v-if="error" class="plate__error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
/* ==========================================================================
   PlateQuiz — Editorial register
   The specimen plate from the hero, which becomes the taste questionnaire.
   ========================================================================== */

.plate {
  border: 3px solid var(--ink);
  background-color: var(--paper);
  box-shadow: 6px 6px 0 var(--shadow);
  /* The shadow is painted outside the border box and is not counted in
     layout, so without this margin it hangs over the page edge on a phone. */
  margin-inline-end: 6px;
  margin-block-end: 6px;
  min-width: 0;
}

.plate__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  aspect-ratio: 1;
}

.cell {
  display: grid;
  place-items: center;
  padding: 0.5rem;
  min-width: 0;
  /* Ink, not the green divider: these are the plate's own grid lines, and in
     green they compete with the accent cell they surround. */
  border-inline-end: 3px solid var(--ink);
  border-block-end: 3px solid var(--ink);
}

/* The right column and bottom row would double the outer frame. */
.cell:nth-child(3n) {
  border-inline-end: 0;
}

.cell:nth-child(n + 7) {
  border-block-end: 0;
}

.cell--centre {
  background-color: var(--accent);
}

/* The glyphs sit back from the rules so the plate reads as a specimen sheet
   rather than a toolbar of icons. */
.cell__glyph {
  color: var(--ink);
  opacity: 0.55;
}

.cell__name {
  font-family: var(--font-display, "Morabba", sans-serif);
  font-size: clamp(1.125rem, 3.2vw, 1.75rem);
  /* A 900 display cut — see the note on --font-display in globals.css. */
  font-weight: 900;
  color: var(--paper);
  letter-spacing: 0.02em;
}

/* The cell is already filled with accent, so the marks take the paper colour
   like the letters rather than the accent they default to. */
.cell__name :deep(.vow__mark) {
  color: var(--paper);
}

.cell__question {
  margin: 0;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(0.8125rem, 1.6vw, 1.0625rem);
  line-height: 1.5;
  font-weight: 600;
  color: var(--paper);
  text-align: center;
}

/* --- The invitation, in the cell below the name ---------------------------- */
.cell--invite {
  /* Paper, not accent: the centre cell is already filled, and two filled
     cells stacked would read as one block rather than as name-and-prompt.
     The accent is carried by the text and the underline instead. */
  background: none;
  color: var(--accent);
  cursor: pointer;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(0.75rem, 1.6vw, 0.9375rem);
  line-height: 1.45;
  font-weight: 600;
  text-align: center;
  text-wrap: balance;
  /* A <button> keeps none of the .cell div rules. */
  border-radius: 0;
  border-block-start: 0;
  border-inline-start: 0;
  border-inline-end: 3px solid var(--ink);
  border-block-end: 3px solid var(--ink);
}

.cell--invite:nth-child(3n) {
  border-inline-end: 0;
}

.cell--invite:nth-child(n + 7) {
  border-block-end: 0;
}

.cell--invite:hover:not(:disabled) {
  background-color: var(--accent);
  color: var(--paper);
}

.cell--invite:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -6px;
}

.cell--invite:disabled {
  color: var(--ink-muted);
  cursor: not-allowed;
}

/* --- Options --------------------------------------------------------------- */
.cell--option {
  background: none;
  border-radius: 0;
  cursor: pointer;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  color: var(--ink);
  /* Re-stated: a <button> does not inherit the div rules above. */
  border-inline-end: 3px solid var(--ink);
  border-block-end: 3px solid var(--ink);
  border-block-start: 0;
  border-inline-start: 0;
}

.cell--option:nth-child(3n) {
  border-inline-end: 0;
}

.cell--option:nth-child(n + 7) {
  border-block-end: 0;
}

.cell--option:hover:not(:disabled) {
  background-color: var(--paper-sunk);
}

.cell--option:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -6px;
}

/* Answered cells stay filled, so the sheet fills as the reader advances and
   is its own progress bar. */
.cell--picked {
  background-color: var(--accent);
  color: var(--paper);
}

.cell__label {
  font-size: clamp(0.8125rem, 1.7vw, 1rem);
  line-height: 1.4;
  font-weight: 600;
  text-align: center;
}

/* The full wording is carried for screen readers and for the wide layout;
   in a small cell only the short form is shown. */
.cell__full {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

/* --- Caption --------------------------------------------------------------- */
.plate__label {
  /* Inside the plate box, so it follows the box. */
  border-block-start: 3px solid var(--ink);
  margin: 0;
  padding: 0.625rem 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  color: var(--ink-muted);
}

/* .plate__start is deliberately absent: it is a cell in the grid now, styled
   as .cell--invite above, and these caption rules would strip its borders. */
.plate__back,
.plate__again {
  background: none;
  border: 0;
  border-radius: 0;
  padding: 0;
  cursor: pointer;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
  color: var(--accent);
  border-block-end: 2px solid var(--accent);
}

.plate__error {
  border-block-start: 3px solid #a33224;
  margin: 0;
  padding: 0.625rem 0.75rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  color: #a33224;
}

/* --- Results --------------------------------------------------------------- */
.picks {
  padding: clamp(1rem, 3vw, 1.5rem);
}

.picks__verdict,
.picks__none {
  margin: 0 0 1rem;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.7;
}

.picks__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.pick {
  border: 3px solid var(--ink);
  padding: 0.875rem;
}

.pick__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.pick__name {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--ink);
  text-decoration: none;
  border-block-end: 2px solid transparent;
}

.pick__name:hover {
  border-block-end-color: var(--accent);
}

.pick__score {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 1rem;
  font-weight: 700;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
  flex: none;
}

.pick__score--weak {
  color: var(--ink-muted);
}

.pick__origin {
  margin: 0.25rem 0 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  color: var(--ink-muted);
}

.pick__reasons,
.pick__against {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.8125rem;
  line-height: 1.7;
}

.pick__reasons li::before {
  content: "+";
  color: var(--accent);
  margin-inline-end: 0.375rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
}

.pick__against {
  color: var(--ink-muted);
}

.pick__against li::before {
  content: "−";
  margin-inline-end: 0.375rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
}

.pick__cta {
  display: inline-block;
  margin-top: 0.75rem;
  text-decoration: none;
}

.picks__link {
  color: var(--accent);
  text-decoration: none;
  border-block-end: 2px solid var(--accent);
}

.plate__again {
  margin-top: 1rem;
}

/* --- Phones ----------------------------------------------------------------
   A 3x3 grid on a 390px screen gives each cell about 110px, which is enough
   for a button and not enough for a Persian phrase. Once the questionnaire is
   running the sheet opens into a single column so the options can be read;
   at rest it stays the plate it always was. */
@media (max-width: 34rem) {
  .plate--busy .plate__grid {
    grid-template-columns: 1fr;
    aspect-ratio: auto;
  }

  .plate--busy .cell {
    border-inline-end: 0;
    border-block-end: 3px solid var(--ink);
    min-height: 3.25rem;
  }

  /* `:last-child` is document order, which reordering makes meaningless.
     The plate's own bottom rule closes the stack instead. */
  .plate--busy .cell {
    border-block-end: 3px solid var(--ink);
  }

  /* The centre cell is first in a column, where the question belongs.
     `order` is set per cell rather than only on the centre: the ring order
     that reads correctly around a square puts the first option at the
     bottom of a column, which is backwards. Each cell carries its own
     option index so a column lists them first to last. */
  .plate--busy .plate__grid {
    display: flex;
    flex-direction: column;
  }

  .plate--busy .cell--centre {
    order: -1;
    padding: 1rem 0.75rem;
  }

  .plate--busy .cell--option {
    order: var(--rank, 0);
  }

  .plate--busy .cell__question {
    font-size: 1rem;
  }

  /* An empty cell in a column is a blank strip, not breathing room. */
  .plate--busy .cell:not(.cell--option):not(.cell--centre) {
    display: none;
  }

  /* With room to read, the full wording is used rather than the short form. */
  .plate--busy .cell__label {
    display: none;
  }

  .plate--busy .cell__full {
    position: static;
    width: auto;
    height: auto;
    margin: 0;
    overflow: visible;
    clip-path: none;
    white-space: normal;
    font-size: 0.9375rem;
    font-weight: 600;
    text-align: center;
  }
}
</style>
