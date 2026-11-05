<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import catalogApi from '@/api/catalog'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import VerseBlock from '@/components/base/VerseBlock.vue'
import PlateQuiz from '@/components/catalog/PlateQuiz.vue'
import ProductCard from '@/components/catalog/ProductCard.vue'

// Deliberately not the catalog store: that store holds the user's filtered
// browse state, and the landing page must not overwrite it.
const featured = ref([])

// True only when these are the roaster's own picks. The heading follows,
// because calling the newest three «پیشنهادی صنوبر» would be a claim nobody
// in the shop has made.
const isPicked = ref(false)
const featuredTitle = computed(() =>
  isPicked.value ? 'محصولات پیشنهادی صنوبر' : 'تازه‌ترین لات‌ها',
)
const loading = ref(true)
const failed = ref(false)

// The three steps a bag actually goes through, stated plainly.
const STEPS = [
  {
    code: 'SOURCE',
    title: 'انتخاب لات',
    body: 'لات‌ها تک‌مبدأ و با امتیاز کاپینگ مشخص انتخاب می‌شوند. مبدأ، مزرعه و پروسس روی صفحه‌ی هر قهوه ثبت است.',
  },
  {
    code: 'ROAST',
    title: 'رست پس از سفارش',
    body: 'هیچ بسته‌ای از پیش رست نمی‌شود. تاریخ رست هر بچ روی سفارش شما ثبت می‌شود و در پیگیری قابل دیدن است.',
  },
  {
    code: 'GRIND',
    title: 'آسیاب به انتخاب شما',
    body: 'دانه کامل یا آسیاب‌شده برای اسپرسو، موکاپات، وی‌شصت یا فرنچ‌پرس — درست پیش از بسته‌بندی.',
  },
]

onMounted(async () => {
  try {
    // What the roaster picked by hand, in shelf order.
    const picked = await catalogApi.list({
      featured: true,
      ordering: 'sort_order',
      page_size: 3,
    })
    featured.value = (picked.data.results || []).slice(0, 3)
    isPicked.value = featured.value.length > 0

    // Nothing picked yet: fall back to newest and in stock, which is what
    // this section did before the checkbox existed. A landing page with an
    // empty shelf would look broken on a catalogue that is not.
    if (!featured.value.length) {
      const { data } = await catalogApi.list({
        ordering: '-created_at',
        in_stock: true,
        page_size: 3,
      })
      featured.value = (data.results || []).slice(0, 3)
    }

    // A published coffee with no roast batch yet counts as out of stock. The
    // catalogue would show it, so an empty landing page here would look like a
    // bug rather than an honest "nothing in stock".
    if (!featured.value.length) {
      const all = await catalogApi.list({ ordering: '-created_at', page_size: 3 })
      featured.value = (all.data.results || []).slice(0, 3)
    }
  } catch {
    // A landing page must still render without the API. The section below
    // degrades to a link into the catalog rather than an error banner.
    failed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="register-editorial home">
    <!-- --- Hero ----------------------------------------------------------- -->
    <section class="hero">
      <div class="hero__text">
        <p class="hero__eyebrow">SENOBAR / SPECIALTY COFFEE</p>
        <h1 class="hero__title">قهوه‌ای که پس از سفارش شما رست می‌شود.</h1>
        <p class="hero__lede">
          لات‌های تک‌مبدأ، در بچ‌های کوچک. تاریخ رست روی هر بسته ثبت است و آسیاب
          را خودتان انتخاب می‌کنید.
        </p>

        <!-- The couplet is where the name comes from, so it sits with the
             name rather than further down the page. Above the buttons: it is
             something to read, not another thing to click past. -->
        <VerseBlock class="hero__verse" />

        <div class="hero__actions">
          <RouterLink to="/products">
            <BaseButton variant="primary">دیدن قهوه‌ها</BaseButton>
          </RouterLink>
          <RouterLink to="/products" class="hero__aside">
            هر لات با امتیاز کاپینگ و یادداشت‌های چشایی
          </RouterLink>
        </div>
      </div>

      <!-- The specimen plate, which is also the taste questionnaire. At rest
           it is the sheet it always was — the name in the centre, coffee
           glyphs around it. Started, the centre carries the question and the
           surrounding cells its answers, so the grid that was decoration
           becomes the thing itself. -->
      <PlateQuiz />
    </section>

    <!-- --- Process -------------------------------------------------------- -->
    <section class="steps" aria-labelledby="steps-title">
      <header class="steps__head">
        <h2 id="steps-title" class="section__title">از لات تا فنجان</h2>
        <RouterLink to="/about" class="steps__more">داستان ما</RouterLink>
      </header>

      <ol class="steps__list">
        <li v-for="(step, i) in STEPS" :key="step.code" class="step">
          <span class="step__index">{{ String(i + 1).padStart(2, '0') }}</span>
          <p class="step__code">{{ step.code }}</p>
          <h3 class="step__title">{{ step.title }}</h3>
          <p class="step__body">{{ step.body }}</p>
        </li>
      </ol>
    </section>

    <!-- --- Featured ------------------------------------------------------- -->
    <section class="featured" aria-labelledby="featured-title">
      <header class="featured__head">
        <h2 id="featured-title" class="section__title">{{ featuredTitle }}</h2>
        <RouterLink to="/products" class="featured__all">همه‌ی قهوه‌ها</RouterLink>
      </header>

      <LoadingState v-if="loading" variant="cards" code="PULLING THE LATEST" :count="3" />

      <EmptyState
        v-else-if="!featured.length"
        icon="bean"
        code="NO BEANS IN SIGHT"
        :message="
          failed
            ? 'فهرست قهوه‌ها در دسترس نیست. کمی بعد دوباره امتحان کنید.'
            : 'هنوز لات موجودی منتشر نشده است. به‌زودی قهوه‌های تازه اینجا خواهند بود.'
        "
      >
        <RouterLink to="/products">
          <BaseButton variant="secondary">رفتن به کاتالوگ</BaseButton>
        </RouterLink>
      </EmptyState>

      <div v-else class="featured__grid">
        <ProductCard v-for="item in featured" :key="item.id" :product="item" />
      </div>
    </section>

    <!-- --- Closing note --------------------------------------------------- -->
    <section class="note">
      <p class="note__code">FRESHNESS</p>
      <p class="note__body">
        قهوه دو تا چهار هفته پس از رست در بهترین حالت خود است. ما بیرون از این
        بازه چیزی نمی‌فروشیم.
      </p>
      <RouterLink to="/products">
        <BaseButton variant="secondary">شروع کنید</BaseButton>
      </RouterLink>
    </section>
  </main>
</template>

<style scoped>
/* ==========================================================================
   HomeView — Editorial register
   ========================================================================== */

.home {
  padding: 0 clamp(1.25rem, 5vw, 4rem) 4rem;
}

.section__title {
  font-family: var(--font-display, "Morabba", sans-serif);
  font-size: clamp(1.75rem, 5vw, 2.5rem);
  line-height: 1.15;
  /* 900 has a real file behind it (Morabba Black), so this is a drawn weight
     rather than one the browser fakes. */
  font-weight: 900;
  margin: 0;
}

/* --- Hero ------------------------------------------------------------------ */
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(2rem, 6vw, 5rem);
  padding-block: clamp(3rem, 9vw, 6.5rem);
}

@media (max-width: 56rem) {
  .hero {
    /* minmax(0, …) rather than a bare 1fr: a grid track defaults to its
       item's min-content width, and the plate then refuses to shrink and
       pushes the page into a horizontal scroll on a phone. */
    grid-template-columns: minmax(0, 1fr);
  }
}

.hero__eyebrow {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.hero__title {
  font-family: var(--font-display, "Morabba", sans-serif);
  /* Capped well below the old 4.5rem: at that size the Persian sentence broke
     to four lines and out-shouted the plate beside it. Two or three lines is
     the shape this hero wants.

     Trimmed again for Morabba, which sets the same sentence appreciably wider
     than Vazirmatn — measured at 56px, 140px of stacked height against 70px,
     i.e. one line became two. */
  font-size: clamp(1.75rem, 3.8vw, 2.75rem);
  line-height: 1.3;
  /* A 900 face: see .section__title. */
  font-weight: 900;
  margin: 1.25rem 0 0;
  /* `ch` is measured on the Latin zero, which is far narrower than Persian
     glyphs, so a ch-based cap wraps much earlier than it reads. */
  max-width: 24ch;
}

.hero__lede {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1rem, 2vw, 1.1875rem);
  line-height: 1.8;
  color: var(--ink-muted);
  max-width: 36rem;
  margin: 1.5rem 0 0;
}

/* In the hero the couplet is part of the text column, not a panel of its own:
   a full box here would put a second framed rectangle beside the specimen
   plate and the two would compete. Only the heavy start rule is kept, which
   is what marks it as quoted. */
.hero__verse {
  margin-top: 2rem;
  max-width: 36rem;      /* the lede's measure, so the column stays one shape */
  border-block: 0;
  border-inline-end: 0;
  padding: 0.25rem 1.25rem 0.25rem 0;
  background-color: transparent;
}

.hero__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin-top: 2.5rem;
}

.hero__aside {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  text-decoration: none;
  border-block-end: 2px solid var(--rule);
}

.hero__aside:hover {
  color: var(--ink);
  border-block-end-color: var(--accent);
}

/* Specimen plate: a nine-square grid with one cell struck in the accent. */



/* The glyphs sit back from the rules so the plate reads as a specimen sheet
   rather than a toolbar of icons. */


/* --- Steps ----------------------------------------------------------------- */
.steps {
  padding-block: clamp(3rem, 7vw, 5rem);
  border-block-start: 3px solid var(--divider);
}

.steps__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.steps__more {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  text-decoration: none;
  border-block-end: 2px solid var(--accent);
}

.steps__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: clamp(1.5rem, 4vw, 3rem);
  list-style: none;
  padding: 0;
  margin: 2.5rem 0 0;
}

.step {
  border-block-start: 3px solid var(--ink);
  padding-block-start: 1.25rem;
}

.step__index {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  color: var(--accent);
}

.step__code {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0.5rem 0 0;
}

.step__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.375rem;
  font-weight: 600;
  margin: 0.5rem 0 0;
}

.step__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.8;
  color: var(--ink-muted);
  margin: 0.75rem 0 0;
}

/* --- Featured -------------------------------------------------------------- */
.featured {
  padding-block: clamp(3rem, 7vw, 5rem);
  border-block-start: 3px solid var(--divider);
}

.featured__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 2.5rem;
}

.featured__all {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  text-decoration: none;
  border-block-end: 2px solid var(--accent);
}

.featured__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  gap: clamp(1.5rem, 3vw, 2.25rem);
}

/* --- Taste quiz ------------------------------------------------------------ */

/* --- Note ------------------------------------------------------------------ */
.note {
  border: 3px solid var(--ink);
  box-shadow: 6px 6px 0 var(--shadow);
  padding: clamp(1.75rem, 5vw, 3rem);
}

.note__code {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.note__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.125rem, 3vw, 1.625rem);
  line-height: 1.6;
  margin: 0.875rem 0 1.75rem;
  max-width: 42rem;
}
</style>
