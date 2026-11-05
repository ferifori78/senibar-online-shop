<script setup>
import { computed } from 'vue'

/**
 * Persian text with its harakat, optionally set larger than the letters.
 *
 * A combining mark cannot be sized on its own in CSS — it inherits the
 * font-size of the run it sits in, and enlarging that enlarges the letters
 * too. So the string is split and each mark wrapped in its own span, which
 * can then be scaled while the base letters stay put.
 *
 * That split has a real cost, and it is why `enlarge` exists. A combining
 * mark has no width of its own and is positioned by the shaper, relative to
 * the glyph it follows. Putting it in its own element takes it out of that
 * shaping run, so the browser can only place it at the run boundary — the
 * edge between two letters — instead of over the letter's centre. In
 * Morabba the fatha of صِنوبَر then sits between the ب and the ر rather than
 * above the ب, and no vertical nudge can fix it: raising the mark just walks
 * it up the wrong column and eventually off the word. Measured, not guessed:
 * the mark's box was read at the ب/ر boundary while the ب's own box sat
 * 28px to its right.
 *
 * So the split is only worth paying for when the marks actually need
 * enlarging. Morabba places its own harakat correctly — verified by
 * rendering the word as plain text beside the split version — and asks for
 * nothing.
 *
 * The marks are kept in the DOM as real characters inside those spans rather
 * than redrawn, so the text still copies, searches and reads correctly to a
 * screen reader — `aria-hidden` on the wrappers would strip the vowelling
 * from the accessible name, which is the opposite of the intent.
 */
const props = defineProps({
  /** The text, with harakat already in it. */
  text: { type: String, required: true },
  /**
   * Mark size, relative to the letters. 1 leaves them alone.
   *
   * Capped per face — see FACES. The font positions a mark at an offset
   * proportional to its own size, so past some multiple the mark drifts off
   * the letter it belongs to, or collides with it. Measured in a browser, not
   * assumed. Bigger is not available; it is broken.
   */
  scale: { type: Number, default: 1.5 },
  /**
   * Which face the text is set in, so the marks can be tuned to it.
   *
   * Not detected: a component cannot ask "what font am I inheriting" without
   * measuring, and the answer changes while a webfont loads. The caller knows.
   *
   * Defaults to `display` because Morabba now sets the whole site — every
   * caller is in it. Leaving the old `editorial` default would have applied
   * Vazirmatn's corrections to Morabba's marks, which is the bug this prop
   * exists to prevent.
   */
  face: {
    type: String,
    default: 'display',
    validator: (v) => v === 'editorial' || v === 'display',
  },
})

/*
 * Per-face behaviour.
 *
 * `enlarge: false` means "leave the text alone entirely" — no splitting, no
 * spans, no offsets. That is the right answer for any face that positions its
 * own harakat well, because the split is what breaks the positioning (see the
 * note at the top).
 *
 * editorial — the numbers fitted for Vazirmatn, which set the site's text
 *   before Morabba replaced it. Vazirmatn sets its harakat small, and
 *   enlarging them was worth the cost of the split there. The face is gone
 *   from the CSS, so nothing reaches this now; re-measure rather than trust
 *   these if a second family is ever reintroduced.
 *
 * display (Morabba) — places both marks correctly by itself, over the right
 *   letters. Confirmed by rendering the plain string beside the split one:
 *   plain is right, split is not. Nothing to fix, so nothing is done.
 */
const FACES = {
  editorial: {
    enlarge: true,
    max: 1.5,
    // Fitted across scales 1.0/1.25/1.5; both sides land on the same gap.
    above: (s) => -0.5127 * s + 0.5203,
    below: (s) => 0.4023 * s - 0.6373,
  },
  display: {
    enlarge: false,
  },
}

const face = computed(() => FACES[props.face] || FACES.editorial)
const markScale = computed(() => Math.min(props.scale, face.value.max ?? 1))

/*
 * Where the mark sits, once it has been enlarged.
 *
 * Enlarging a mark moves it away from its letter, and by different amounts on
 * each side — so a single pair of fixed offsets only ever looks right at one
 * scale. Worse, the font's own placement is not symmetric to begin with:
 * measured on rendered pixels at scale 1, a fatha sits 73px clear of its
 * letter at 96px type while a kasra sits 30px — the mark below is set much
 * tighter than the one above.
 *
 * These two lines correct both problems at once. They were fitted to gaps
 * measured off screenshots (render with marks, render without, difference the
 * images, and count the clear pixels between each mark's ink and its letter's
 * ink) across scales 1.0, 1.25 and 1.5. Both sides land on the same gap —
 * 0.79em, the spacing the fatha already had at the design scale, which reads
 * as attached to its letter without touching it.
 *
 * Derived from measurement, not taste. Re-measure before changing them.
 */
const markOffset = computed(() => {
  if (!face.value.enlarge) return { above: '0em', below: '0em' }
  const s = markScale.value
  return {
    above: `${face.value.above(s).toFixed(3)}em`,
    below: `${face.value.below(s).toFixed(3)}em`,
  }
})

/** Unicode combining marks — the harakat are all in this range. */
const HARAKAT = /[ً-ْٰٓ-ٕ]/

/**
 * The marks that sit *below* the letter rather than above it.
 *
 * They need their own nudge: enlarging a mark moves it away from the letter
 * along whichever side it lives on, so one correction cannot serve both. A
 * kasra drifts down while a fatha drifts up, and they need pulling back in
 * opposite directions.
 */
const BELOW = new Set([
  'ِ', // kasra
  'ٍ', // kasratan
  'ٕ', // hamza below
])

/**
 * Split into runs of plain text and single marks.
 *
 * One span per mark rather than one per character: fewer elements, and the
 * letters stay in unbroken runs so the shaper still joins them. Breaking a
 * Persian word into one span per letter would disconnect the cursive
 * joining and render it as isolated forms.
 */
const parts = computed(() => {
  // One run, untouched, when the face needs no help: the shaper then places
  // every mark over the letter it belongs to, which is the whole point.
  if (!face.value.enlarge) return [{ mark: false, value: props.text }]

  const out = []
  let buffer = ''
  for (const char of props.text) {
    if (HARAKAT.test(char)) {
      if (buffer) {
        out.push({ mark: false, value: buffer })
        buffer = ''
      }
      out.push({ mark: true, value: char, below: BELOW.has(char) })
    } else {
      buffer += char
    }
  }
  if (buffer) out.push({ mark: false, value: buffer })
  return out
})
</script>

<template><span class="vow"><template v-for="(part, i) in parts" :key="i"><span
  v-if="part.mark"
  class="vow__mark"
  :class="part.below ? 'vow__mark--below' : 'vow__mark--above'"
  :style="{
    fontSize: `${markScale}em`,
    verticalAlign: part.below ? markOffset.below : markOffset.above,
  }"
>{{ part.value }}</span><template v-else>{{ part.value }}</template></template></span></template>

<style scoped>
/* No whitespace is allowed between the spans above — Persian is cursive, and
   a newline in the template would insert a space that breaks the joining and
   splits the word visually. Hence the run-together markup. */

.vow {
  /* The enlarged marks would otherwise push the line box taller than the
     text around them. */
  line-height: inherit;
}

.vow__mark {
  /* A mark has no advance width of its own, so scaling it cannot shift the
     letters sideways; only its own height changes. */
  line-height: 0;
  font-weight: inherit;
  color: var(--accent);
  /* Sized with font-size and nothing else. A transform (or anything that
     makes this an inline-block — including a width) gives the mark its own
     box, which detaches it from the letter and breaks the cursive joining of
     the whole word: the letters render as isolated forms. Verified in a
     browser. `vertical-align` is the one nudge that leaves shaping alone. */
}

/* The vertical nudge is not here: it depends on the scale, so it is computed
   per mark in the script above and applied inline. The classes remain as the
   hook that says which side a mark belongs to. */
</style>
