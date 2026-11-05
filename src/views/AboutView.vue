<script setup>
import { RouterLink } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import VerseBlock from '@/components/base/VerseBlock.vue'

// The four things a customer can actually hold us to. Stated as commitments,
// not adjectives — each one is visible somewhere in the product or the order.
const PRINCIPLES = [
  {
    code: 'TRACEABILITY',
    title: 'مبدأ مشخص',
    body: 'هیچ لاتی بدون کشور، منطقه و پروسس منتشر نمی‌شود. هرجا مزرعه و تولیدکننده را بدانیم، روی صفحه‌ی همان قهوه می‌نویسیم.',
  },
  {
    code: 'ROAST DATE',
    title: 'تاریخ رست، نه تاریخ انقضا',
    body: 'روی هر بسته تاریخ رست ثبت است. تاریخ انقضای دوساله چیزی درباره‌ی قهوه نمی‌گوید؛ تاریخ رست می‌گوید.',
  },
  {
    code: 'SMALL BATCH',
    title: 'بچ کوچک',
    body: 'در دفعات کم و پیوسته رست می‌کنیم. انبار بزرگ یعنی قهوه‌ای که پیش از رسیدن به شما بخش زیادی از عمرش را از دست داده است.',
  },
  {
    code: 'NO BLENDING AWAY',
    title: 'بدون پنهان‌کاری',
    body: 'اگر لاتی از بازه‌ی بهینه‌اش بیرون برود، آن را نمی‌فروشیم و در ترکیب پنهانش نمی‌کنیم.',
  },
]

// The freshness window we actually operate on, drawn as a ruled scale.
const WINDOW = [
  { day: 'روز ۰', note: 'رست' },
  { day: 'روز ۳', note: 'شروع بازه', on: true },
  { day: 'روز ۱۴', note: 'اوج', on: true },
  { day: 'روز ۲۸', note: 'پایان بازه' },
]
</script>

<template>
  <main class="register-editorial about">
    <!-- --- Opening -------------------------------------------------------- -->
    <header class="lede">
      <p class="lede__eyebrow">SENOBAR / OUR STORY</p>
      <h1 class="lede__title">داستان ما</h1>
      <p class="lede__body">
        صنوبر از یک نارضایتی ساده شروع شد: قهوه‌ای که می‌خریدیم معلوم نبود کِی رست
        شده است. روی بسته تاریخ انقضا بود، نه تاریخ رست — و این دو یک چیز نیستند.
      </p>
    </header>

    <!-- --- The name ------------------------------------------------------- -->
    <!-- Placed before the narrative rather than after it: the page is called
         "our story" and the name is where the story starts. -->
    <section class="naming" aria-labelledby="naming-title">
      <h2 id="naming-title" class="section__title">چرا صنوبر</h2>

      <VerseBlock variant="sunk" />

      <!-- The shop's own reading of the couplet, in its register: the verse
           supplies the pun, this carries it into what we sell. Set apart from
           the plain gloss below, which explains rather than declares. -->
      <p class="naming__creed">
        در پیشگاهِ شکوهِ «صنوبر»، گوهرهایِ نایابِ قهوه را به شما تقدیم می‌کنیم؛
        ما از دلِ این نام، صدها طعمِ نوبرانه را برای ذائقه‌ی جست‌وجوگرِ شما
        برگزیده‌ایم. در هر فنجانِ قهوه، گوهری نهفته است که با تازگی و اصالت،
        جان و حالِ شما را جلا می‌دهد.
      </p>

      <p class="naming__gloss">
        خاقانی در این بیت «نوبر» را کنار «صنوبر» می‌گذارد: از یک درخت، صد میوه‌ی
        نوبرانه. اسم را از همین‌جا برداشتیم — یک درخت، و هر بار نخستین محصول
        فصل. قهوه هم میوه است، و ما فقط در بازه‌ای که تازه است می‌فروشیمش.
      </p>
    </section>

    <!-- --- Narrative ------------------------------------------------------ -->
    <section class="story" aria-labelledby="story-title">
      <h2 id="story-title" class="section__title">از کجا شروع شد</h2>

      <div class="story__cols">
        <p class="story__para">
          شفافیت، چیزی است که در بازارِ قهوه مفقود شده است. کافی نیست بدانید قهوه
          از کجا آمده؛ باید بدانید دقیقاً چه زمانی رست شده است. پاسخِ «تازه است»،
          برای ما کافی نیست؛ ما به عدد نیاز داریم.
        </p>
        <p class="story__para">
          ما رست‌خانه‌ای را بنیان گذاشتیم که در آن، هر چیز با عدد تعریف می‌شود:
          تاریخِ رست، امتیازِ کاپینگ و وزنِ دقیقِ خروجی.
        </p>
        <p class="story__para">
          در «صنوبر»، ما از پیش تولید نمی‌کنیم. سفارش شما، دستورِ شروعِ کار ماست.
          لاتِ شما در بچِ بعدی رست می‌شود و درست در لحظه‌ی نهایی، طبق انتخاب شما
          آسیاب می‌گردد. ما این زمانِ انتظار را آگاهانه انتخاب کرده‌ایم؛ تا شما،
          طعمِ واقعیِ تازگی را بچشید.
        </p>
      </div>
    </section>

    <!-- --- Freshness window ------------------------------------------------ -->
    <section class="window" aria-labelledby="window-title">
      <h2 id="window-title" class="section__title">بازه‌ای که در آن می‌فروشیم</h2>
      <p class="window__lede">
        قهوه بلافاصله پس از رست هنوز گاز می‌دهد و طعمش بسته است؛ بعد از حدود چهار
        هفته هم شروع به از دست دادن عطرش می‌کند. ما بین این دو می‌فروشیم.
      </p>

      <ol class="scale">
        <li v-for="mark in WINDOW" :key="mark.day" class="scale__mark">
          <span class="scale__node" :class="{ 'scale__node--on': mark.on }" aria-hidden="true" />
          <span class="scale__day">{{ mark.day }}</span>
          <span class="scale__note">{{ mark.note }}</span>
        </li>
      </ol>
    </section>

    <!-- --- Principles ------------------------------------------------------ -->
    <section class="principles" aria-labelledby="principles-title">
      <h2 id="principles-title" class="section__title">چهار قولی که می‌دهیم</h2>

      <ul class="principles__list">
        <li v-for="item in PRINCIPLES" :key="item.code" class="principle">
          <p class="principle__code">{{ item.code }}</p>
          <h3 class="principle__title">{{ item.title }}</h3>
          <p class="principle__body">{{ item.body }}</p>
        </li>
      </ul>
    </section>

    <!-- --- Closing --------------------------------------------------------- -->
    <section class="close">
      <p class="close__code">SENOBAR</p>
      <p class="close__body">
        اگر سؤالی درباره‌ی یک لات دارید — از ارتفاع کشت تا پروفایل رست — بپرسید.
        پاسخ می‌دهیم.
      </p>
      <div class="close__actions">
        <RouterLink to="/products">
          <BaseButton variant="primary">دیدن قهوه‌ها</BaseButton>
        </RouterLink>
        <RouterLink to="/support">
          <BaseButton variant="secondary">تماس با ما</BaseButton>
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<style scoped>
/* ==========================================================================
   AboutView — Editorial register
   ========================================================================== */

.about {
  padding: 0 clamp(1.25rem, 5vw, 4rem) 4rem;
}

.section__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.75rem, 5vw, 2.5rem);
  line-height: 1.15;
  font-weight: 600;
  margin: 0;
}

/* --- Opening --------------------------------------------------------------- */
.lede {
  padding-block: clamp(3rem, 8vw, 6rem);
  max-width: 46rem;
}

.lede__eyebrow {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.lede__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(2.5rem, 8vw, 4.5rem);
  line-height: 1.05;
  font-weight: 600;
  margin: 1rem 0 0;
}

.lede__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.0625rem, 2.2vw, 1.3125rem);
  line-height: 1.8;
  color: var(--ink-muted);
  margin: 1.75rem 0 0;
}

/* --- Story ----------------------------------------------------------------- */
.naming,
.story,
.window,
.principles {
  padding-block: clamp(2.5rem, 7vw, 4.5rem);
  border-block-start: 3px solid var(--divider);
}

.naming > :not(:first-child) {
  margin-block-start: 2rem;
}

/* Held to the measure of the prose around it. At full page width the two
   hemistichs sit marooned in a very wide panel and stop reading as a couplet. */
.naming > figure {
  max-width: 44rem;
}

/* The creed is the voice of the shop, so it is set at reading size in full
   ink — a step above the gloss, a step below the verse. */
.naming__creed {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.0625rem, 1.6vw, 1.25rem);
  line-height: 2;
  color: var(--ink);
  max-width: 44rem;
  margin-block-end: 0;
}

/* The gloss explains the pun; it is commentary, so it is set at the muted
   weight the other secondary copy on this page uses. */
.naming__gloss {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  line-height: 1.9;
  color: var(--ink-muted);
  max-width: 44rem;
  margin-block-end: 0;
}

.story__cols {
  columns: 2;
  column-gap: clamp(2rem, 5vw, 4rem);
  margin-top: 2rem;
}

@media (max-width: 48rem) {
  .story__cols {
    columns: 1;
  }
}

.story__para {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  line-height: 1.9;
  margin: 0 0 1.25rem;
  /* Keeps a paragraph from splitting across the column break mid-sentence. */
  break-inside: avoid;
}

/* --- Freshness scale ------------------------------------------------------- */
.window__lede {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  line-height: 1.8;
  color: var(--ink-muted);
  max-width: 42rem;
  margin: 1.5rem 0 0;
}

.scale {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  list-style: none;
  padding: 0;
  margin: 2.75rem 0 0;
  border-block-start: 3px solid var(--ink);
}

@media (max-width: 40rem) {
  .scale {
    grid-template-columns: repeat(2, 1fr);
  }
}

.scale__mark {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1.25rem 0.75rem 0 0;
}

/* Square node, filled with the accent inside the window. */
.scale__node {
  width: 0.875rem;
  height: 0.875rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  margin-block-end: 0.25rem;
}

.scale__node--on {
  background-color: var(--accent);
}

.scale__day {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.scale__note {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  color: var(--ink-muted);
}

/* --- Principles ------------------------------------------------------------ */
.principles__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: clamp(1.5rem, 4vw, 3rem);
  list-style: none;
  padding: 0;
  margin: 2.5rem 0 0;
}

.principle {
  border-block-start: 3px solid var(--ink);
  padding-block-start: 1.25rem;
}

.principle__code {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0;
}

.principle__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.375rem;
  font-weight: 600;
  margin: 0.625rem 0 0;
}

.principle__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.8;
  color: var(--ink-muted);
  margin: 0.75rem 0 0;
}

/* --- Closing --------------------------------------------------------------- */
.close {
  border: 3px solid var(--ink);
  box-shadow: 6px 6px 0 var(--shadow);
  padding: clamp(1.75rem, 5vw, 3rem);
}

.close__code {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.close__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.125rem, 3vw, 1.625rem);
  line-height: 1.6;
  margin: 0.875rem 0 1.75rem;
  max-width: 42rem;
}

.close__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
</style>
