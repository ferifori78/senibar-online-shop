<script setup>
/**
 * The Senobar loading state.
 *
 * No spinner. Two devices instead, both built from squares:
 *   `bar`   — a determinate-looking track with an accent block sweeping it
 *   `rows`  — skeleton placeholders shaped like the content being loaded
 *
 * Both step rather than ease, matching the button physics: this system moves
 * in discrete positions, never a smooth glide.
 */
defineProps({
  variant: {
    type: String,
    default: 'bar',
    validator: (v) => ['bar', 'rows', 'cards', 'inline'].includes(v),
  },
  /** Monospace status text. */
  code: { type: String, default: 'LOADING' },
  /** How many skeletons to draw for `rows` and `cards`. */
  count: { type: Number, default: 3 },
  inverse: { type: Boolean, default: false },
})
</script>

<template>
  <div class="load" :class="{ 'load--inverse': inverse }" role="status" aria-live="polite">
    <!-- Bar: a sweeping block in a framed track. -->
    <template v-if="variant === 'bar'">
      <p class="load__code">{{ code }}<span class="load__dots" aria-hidden="true" /></p>
      <div class="load__track" aria-hidden="true">
        <span class="load__block" />
      </div>
    </template>

    <!-- Inline: for a button or a table cell. -->
    <p v-else-if="variant === 'inline'" class="load__code load__code--inline">
      {{ code }}<span class="load__dots" aria-hidden="true" />
    </p>

    <!-- Skeletons shaped like what is coming. -->
    <div v-else class="load__skeletons" :class="`load__skeletons--${variant}`" aria-hidden="true">
      <div v-for="n in count" :key="n" class="skel" :style="{ animationDelay: `${n * 90}ms` }">
        <span class="skel__plate" />
        <span class="skel__lines">
          <span class="skel__line skel__line--wide" />
          <span class="skel__line" />
          <span class="skel__line skel__line--short" />
        </span>
      </div>
    </div>

    <span class="sr-only">{{ code }}</span>
  </div>
</template>

<style scoped>
/* ==========================================================================
   LoadingState — both registers
   Squares that step. No arcs, no blur, no easing.
   ========================================================================== */

.load {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.load__code {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.load__code--inline {
  font-size: 0.625rem;
}

/* Three dots that arrive one at a time, in steps. */
.load__dots::after {
  content: "";
  animation: dots 1.2s steps(4, end) infinite;
}

@keyframes dots {
  0% { content: ""; }
  25% { content: "."; }
  50% { content: ".."; }
  75% { content: "..."; }
  100% { content: ""; }
}

/* --- Bar ------------------------------------------------------------------- */
.load__track {
  height: 0.75rem;
  border: 3px solid var(--ink);
  overflow: hidden;
}

.load__block {
  display: block;
  width: 30%;
  height: 100%;
  background-color: var(--accent);
  animation: sweep 1.2s steps(7, end) infinite;
}

@keyframes sweep {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(333%);
  }
}

/* --- Skeletons ------------------------------------------------------------- */
.load__skeletons {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.load__skeletons--cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  gap: 1.5rem;
}

.skel {
  display: flex;
  gap: 1rem;
  border: 3px solid var(--rule);
  padding: 1rem;
  /* Staggered so the block reads as a list filling in, not a single flash. */
  animation: pulse 1.6s steps(2, end) infinite;
}

.load__skeletons--cards .skel {
  flex-direction: column;
}

.skel__plate {
  width: 4rem;
  height: 4rem;
  background-color: var(--paper-sunk);
  flex: none;
}

.load__skeletons--cards .skel__plate {
  width: 100%;
  height: 8rem;
}

.skel__lines {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  padding-top: 0.25rem;
}

.skel__line {
  height: 0.6875rem;
  background-color: var(--paper-sunk);
  width: 60%;
}

.skel__line--wide {
  width: 85%;
}

.skel__line--short {
  width: 35%;
}

@keyframes pulse {
  50% {
    opacity: 0.55;
  }
}

/* --- Terminal register ----------------------------------------------------- */
.load--inverse .load__code {
  color: var(--terminal-dim);
}

.load--inverse .load__track {
  border-color: var(--terminal-text);
}

.load--inverse .skel {
  border-color: var(--terminal-rule);
}

.load--inverse .skel__plate,
.load--inverse .skel__line {
  background-color: var(--terminal-raised);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

@media (prefers-reduced-motion: reduce) {
  .load__block {
    animation-duration: 3s;
  }
  .load__dots::after,
  .skel {
    animation: none;
  }
  .load__dots::after {
    content: "…";
  }
}
</style>
