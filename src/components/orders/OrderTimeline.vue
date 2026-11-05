<script setup>
import { computed } from 'vue'

import { formatDateTime } from '@/utils/format'

/**
 * The Timeline register.
 *
 * A vertical rail with square nodes. Completed stages fill with accent, and
 * the rail itself fills only as far as the current stage — so the amount of
 * accent on screen is literally how far the order has come.
 */
const props = defineProps({
  /** [{ status, label, state }] straight from the order's `timeline`. */
  stages: { type: Array, required: true },
  /** The order, for per-stage timestamps. Optional. */
  order: { type: Object, default: null },
  inverse: { type: Boolean, default: false },
})

// Persian labels for the pipeline. The API sends English ones.
const LABELS = {
  pending: 'ثبت سفارش',
  roasting: 'در حال رست',
  ground: 'آسیاب شده',
  packed: 'بسته‌بندی',
  shipped: 'ارسال شده',
  delivered: 'تحویل شد',
}

const NOTES = {
  pending: 'سفارش ثبت و پرداخت شد.',
  roasting: 'قهوه شما در حال رست است.',
  ground: 'طبق روش دم‌آوری انتخابی شما آسیاب شد.',
  packed: 'در بسته‌بندی یک‌طرفه با دریچه بسته شد.',
  shipped: 'تحویل پست شد.',
  delivered: 'به دست شما رسید.',
}

// Which order field timestamps each stage.
const STAMPS = {
  pending: 'placed_at',
  roasting: 'roasted_at',
  shipped: 'shipped_at',
  delivered: 'delivered_at',
}

const isCancelled = computed(() => props.stages.some((s) => s.state === 'cancelled'))

const currentIndex = computed(() => props.stages.findIndex((s) => s.state === 'current'))

/** How far the rail is filled, as a percentage of its own height. Nodes sit at
 *  even intervals, so the fill stops exactly at the current node's centre. */
const fillPercent = computed(() => {
  if (isCancelled.value || currentIndex.value < 0) return 0
  const gaps = props.stages.length - 1
  return gaps <= 0 ? 100 : (currentIndex.value / gaps) * 100
})

function timestampFor(stage) {
  const field = STAMPS[stage.status]
  return field && props.order?.[field] ? formatDateTime(props.order[field]) : ''
}
</script>

<template>
  <div
    class="rail"
    :class="{ 'rail--inverse': inverse, 'rail--cancelled': isCancelled }"
    role="list"
    aria-label="مراحل سفارش"
  >
    <!-- The rail: a full-height track with an accent fill over it. -->
    <div class="rail__track" aria-hidden="true">
      <div class="rail__fill" :style="{ height: `${fillPercent}%` }" />
    </div>

    <div
      v-for="stage in stages"
      :key="stage.status"
      class="rail__stage"
      :class="`rail__stage--${stage.state}`"
      role="listitem"
    >
      <!-- Square node. Filled with accent once reached. -->
      <span class="rail__node" aria-hidden="true" />

      <div class="rail__body">
        <div class="rail__head">
          <span class="rail__label">{{ LABELS[stage.status] || stage.label }}</span>
          <span v-if="stage.state === 'current'" class="rail__badge">اکنون</span>
        </div>

        <p v-if="timestampFor(stage)" class="rail__time">{{ timestampFor(stage) }}</p>
        <p v-else-if="stage.state !== 'upcoming'" class="rail__note">
          {{ NOTES[stage.status] }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ==========================================================================
   OrderTimeline — the Timeline register
   A vertical rail, square nodes, accent fill. Labels are mono and uppercase.
   ========================================================================== */

.rail {
  --node: 1.125rem;      /* node edge */
  --rail-w: 3px;         /* rail width, the system's border weight */
  --gutter: 2.25rem;     /* space from the rail to the text */

  position: relative;
  padding-inline-start: var(--gutter);
}

/* --- The rail -------------------------------------------------------------- */
.rail__track {
  position: absolute;
  inset-inline-start: calc((var(--node) - var(--rail-w)) / 2);
  /* Start and end at the first and last node centres, not the container edge. */
  top: calc(var(--node) / 2);
  bottom: calc(var(--node) / 2);
  width: var(--rail-w);
  background-color: var(--rule);
}

.rail__fill {
  width: 100%;
  background-color: var(--accent);
  transition: height 240ms cubic-bezier(0.2, 0, 0, 1);
}

.rail--inverse .rail__track {
  background-color: var(--terminal-rule);
}

.rail--cancelled .rail__track {
  background-color: var(--rule);
}

/* --- Stages ---------------------------------------------------------------- */
.rail__stage {
  position: relative;
  display: flex;
  gap: 0.875rem;
  padding-bottom: 2rem;
}

.rail__stage:last-child {
  padding-bottom: 0;
}

/* --- Node ------------------------------------------------------------------ */
.rail__node {
  position: absolute;
  inset-inline-start: calc(-1 * var(--gutter));
  top: 0;
  width: var(--node);
  height: var(--node);
  border: var(--rail-w) solid var(--ink);
  background-color: var(--paper);
  flex: none;
}

.rail--inverse .rail__node {
  border-color: var(--terminal-text);
  background-color: var(--terminal);
}

/* Reached: filled with accent. */
.rail__stage--done .rail__node,
.rail__stage--current .rail__node {
  background-color: var(--accent);
  border-color: var(--accent);
}

/* The current node wears a hard ring — a halo of paper then accent, so it
   reads as the live position without any glow. */
.rail__stage--current .rail__node {
  box-shadow:
    0 0 0 3px var(--paper),
    0 0 0 6px var(--accent);
}

.rail--inverse .rail__stage--current .rail__node {
  box-shadow:
    0 0 0 3px var(--terminal),
    0 0 0 6px var(--accent);
}

/* Upcoming: hollow, in the muted rule colour. */
.rail__stage--upcoming .rail__node {
  border-color: var(--rule);
  background-color: var(--paper);
}

/* Cancelled: the node is struck through with a diagonal, not coloured red —
   the rail simply stops meaning anything. */
.rail__stage--cancelled .rail__node {
  border-color: var(--rule);
  background-color: var(--paper);
}

/* --- Body ------------------------------------------------------------------ */
.rail__body {
  padding-top: 0;
  min-width: 0;
}

.rail__head {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-wrap: wrap;
  /* Optically centre the label against its node. */
  min-height: var(--node);
}

.rail__label {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  color: var(--ink);
}

.rail--inverse .rail__label {
  color: var(--terminal-text);
}

/* Stages not yet reached recede rather than disappear. */
.rail__stage--upcoming .rail__label,
.rail__stage--cancelled .rail__label {
  color: var(--ink-muted);
}

.rail--inverse .rail__stage--upcoming .rail__label {
  color: var(--terminal-dim);
}

.rail__badge {
  border: 2px solid var(--accent);
  color: var(--accent);
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.125rem 0.375rem;
}

.rail__time,
.rail__note {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  line-height: 1.6;
  color: var(--ink-muted);
  margin: 0.375rem 0 0;
}

.rail--inverse .rail__time,
.rail--inverse .rail__note {
  color: var(--terminal-dim);
}

@media (prefers-reduced-motion: reduce) {
  .rail__fill {
    transition: none;
  }
}
</style>
