<script setup>
import VowelledText from './VowelledText.vue'

/**
 * The Khaqani couplet, set as a poem.
 *
 * One component rather than the lines pasted into each page: a poem
 * transcribed twice eventually drifts, and a wrong word in a classical verse
 * is the kind of error a Persian reader notices immediately.
 *
 * The pun is the reason it belongs on this site at all — نوبر (first fruit of
 * the season) against صنوبر (the fir) — so the shop's name sits inside the
 * line rather than being decoration around it.
 */
defineProps({
  /** `paper` on the light ground, `sunk` for a recessed panel. */
  variant: {
    type: String,
    default: 'paper',
    validator: (v) => ['paper', 'sunk'].includes(v),
  },
})

// «صنوبر» carries its harakat here so the shop's name is vowelled wherever it
// appears. The reading is the Persian one — صِنوبَر, senobar — matching the
// brand's own latin spelling; classical Arabic would vowel it صَنَوْبَر,
// sanawbar. The rest of the couplet is left unvowelled apart from the kasra
// that the metre needs, so the marks stay meaningful rather than decorative.
const LINES = [
  'پیشِ بالایت، به بالایت فروریزم گهر',
  'زآنکه صد نوبر مرا زآن یک صِنوبَر، ساختند',
]
</script>

<template>
  <!-- <figure>/<blockquote>, not a stack of <p>: this is a quotation with an
       attribution, and the markup should say so. -->
  <figure class="verse" :class="`verse--${variant}`">
    <blockquote class="verse__quote">
      <!-- Each hemistich is its own line and must never be re-wrapped into
           prose, so they are separate elements rather than one string with a
           <br> in it. -->
      <VowelledText v-for="line in LINES" :key="line" :text="line" class="verse__line" />
    </blockquote>
    <figcaption class="verse__by">خاقانی</figcaption>
  </figure>
</template>

<style scoped>
/* ==========================================================================
   VerseBlock — Editorial register
   A ruled panel with a heavy start-edge rule, the way a pull-quote is set in
   print. No italics: the Naskh face has no true italic and a synthesised one
   distorts the letterforms.
   ========================================================================== */

.verse {
  margin: 0;
  border: 3px solid var(--ink);
  border-inline-start-width: 9px;
  padding: clamp(1.5rem, 4vw, 2.25rem) clamp(1.25rem, 4vw, 2.5rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.verse--paper {
  background-color: var(--paper);
}

.verse--sunk {
  background-color: var(--paper-sunk);
}

.verse__quote {
  margin: 0;
}

.verse__line {
  /* VowelledText renders a span; each hemistich must still be its own line. */
  display: block;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  /* Larger than body copy and loosely leaded: a couplet read at prose density
     looks like a sentence that happens to break oddly. */
  font-size: clamp(1.0625rem, 2.4vw, 1.5rem);
  line-height: 2;
  margin: 0;
  color: var(--ink);
  /* The two hemistichs are one thought; balancing keeps them from splitting
     unevenly when a narrow screen wraps them. */
  text-wrap: balance;
}

.verse__by {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

/* The attribution sits under a hairline, not beside a dash. */
.verse__by::before {
  content: '';
  display: block;
  inline-size: 2.5rem;
  border-block-start: 2px solid var(--accent);
  margin-block-end: 0.75rem;
}
</style>
