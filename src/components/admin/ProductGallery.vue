<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { useAdminStore } from '@/stores/admin'

const props = defineProps({
  /** The product's slug, or null while a new product is unsaved. */
  slug: { type: String, default: null },
})

const admin = useAdminStore()

const images = ref([])
const busy = ref(false)
const fileInput = ref(null)
const dragId = ref(null)

// A product that has not been saved has no slug, so there is nowhere to attach
// a photo yet. Saying so is better than an upload button that silently 404s.
const canUpload = computed(() => Boolean(props.slug))

/** Fetched rather than taken from the product prop: the modal is opened from
 *  the product *list*, whose lean serializer carries no gallery, so trusting
 *  the prop would show an empty gallery for every product that has photos. */
async function load() {
  if (!props.slug) {
    images.value = []
    return
  }
  const { ok, images: fresh } = await admin.fetchProductImages(props.slug)
  if (ok) images.value = fresh
}

onMounted(load)
watch(() => props.slug, load)

/** The browser's own file picker, opened from our own button. */
function pick() {
  fileInput.value?.click()
}

async function onFiles(event) {
  const files = [...event.target.files]
  // Clear immediately: picking the same file twice in a row fires no change
  // event unless the input is reset.
  event.target.value = ''
  if (!files.length || !props.slug) return

  busy.value = true

  // Sequential, not Promise.all: each upload decides its own sort_order from
  // the current end of the gallery, and in parallel they would all read the
  // same value and collide.
  for (const file of files) {
    const { ok, image } = await admin.uploadProductImage(props.slug, file)
    if (!ok) break
    images.value.push(image)
  }

  busy.value = false
}

async function remove(image) {
  busy.value = true
  const { ok } = await admin.deleteProductImage(props.slug, image.id)
  if (ok) {
    const wasCover = image.is_cover
    images.value = images.value.filter((i) => i.id !== image.id)
    // The server promotes the next photo when the cover goes; mirror that here
    // rather than refetching, so the grid never shows a gallery with no cover.
    if (wasCover && images.value.length) images.value[0].is_cover = true
  }
  busy.value = false
}

async function makeCover(image) {
  if (image.is_cover) return
  busy.value = true
  const { ok, images: fresh } = await admin.setProductCover(props.slug, image.id)
  if (ok) images.value = fresh
  busy.value = false
}

/* --- Reordering ----------------------------------------------------------
   Drag to reorder, with the list rewritten optimistically and the server
   asked to persist the same order afterwards. */

function onDragStart(image) {
  dragId.value = image.id
}

function onDrop(target) {
  const from = images.value.findIndex((i) => i.id === dragId.value)
  const to = images.value.findIndex((i) => i.id === target.id)
  dragId.value = null
  if (from === -1 || to === -1 || from === to) return

  const next = [...images.value]
  next.splice(to, 0, ...next.splice(from, 1))
  images.value = next
  persistOrder()
}

/** Keyboard reordering — dragging is not reachable without a mouse. */
function move(image, delta) {
  const from = images.value.findIndex((i) => i.id === image.id)
  const to = from + delta
  if (to < 0 || to >= images.value.length) return

  const next = [...images.value]
  next.splice(to, 0, ...next.splice(from, 1))
  images.value = next
  persistOrder()
}

async function persistOrder() {
  const order = images.value.map((i) => i.id)
  const { ok, images: fresh } = await admin.reorderProductImages(props.slug, order)
  if (ok) images.value = fresh
}
</script>

<template>
  <div class="gal">
    <div class="gal__head">
      <span class="gal__label">تصویرهای محصول</span>
      <span class="gal__count">{{ images.length }} IMAGES</span>
    </div>

    <p v-if="!canUpload" class="gal__note">
      برای افزودن تصویر، اول محصول را ذخیره کنید.
    </p>

    <template v-else>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        class="gal__file"
        @change="onFiles"
      />

      <ul v-if="images.length" class="gal__grid">
        <li
          v-for="image in images"
          :key="image.id"
          class="shot"
          :class="{ 'shot--cover': image.is_cover }"
          draggable="true"
          @dragstart="onDragStart(image)"
          @dragover.prevent
          @drop.prevent="onDrop(image)"
        >
          <img :src="image.image" :alt="image.alt_text" class="shot__img" />

          <span v-if="image.is_cover" class="shot__badge">اصلی</span>

          <div class="shot__acts">
            <button
              type="button"
              class="shot__act"
              :disabled="busy || image.is_cover"
              @click="makeCover(image)"
            >
              {{ image.is_cover ? 'تصویر اصلی' : 'اصلی کن' }}
            </button>

            <!-- Arrows, because drag-and-drop is unreachable from a keyboard. -->
            <span class="shot__nudge">
              <button type="button" class="shot__arrow" :disabled="busy" aria-label="جابه‌جایی به قبل" @click="move(image, -1)">‹</button>
              <button type="button" class="shot__arrow" :disabled="busy" aria-label="جابه‌جایی به بعد" @click="move(image, 1)">›</button>
            </span>

            <button type="button" class="shot__act shot__act--del" :disabled="busy" @click="remove(image)">
              حذف
            </button>
          </div>
        </li>
      </ul>

      <p v-else class="gal__note">هنوز تصویری اضافه نشده است.</p>

      <div class="gal__foot">
        <button type="button" class="gal__add" :disabled="busy" @click="pick">
          {{ busy ? 'در حال آپلود…' : 'افزودن تصویر' }}
        </button>
        <span class="gal__hint">اولین تصویر به‌طور خودکار تصویر اصلی می‌شود.</span>
      </div>
    </template>

    <p v-if="admin.error" class="gal__err">{{ admin.error }}</p>
  </div>
</template>

<style scoped>
/* ==========================================================================
   ProductGallery — Terminal register
   ========================================================================== */

.gal {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border: 3px solid var(--terminal-rule);
  padding: 1rem;
}

.gal__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}

.gal__label,
.gal__count,
.gal__hint,
.gal__note {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.gal__label {
  color: var(--terminal-text);
}

.gal__count,
.gal__hint {
  color: var(--terminal-dim);
}

.gal__note {
  color: var(--terminal-dim);
  margin: 0;
  letter-spacing: 0.04em;
  text-transform: none;
}

/* The real input is driven by our own button, but stays focusable rather than
   display:none so it is still reachable by keyboard. */
.gal__file {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.gal__grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  gap: 0.75rem;
}

.shot {
  position: relative;
  border: 3px solid var(--terminal-rule);
  background-color: var(--terminal-raised);
  cursor: grab;
}

.shot--cover {
  border-color: var(--accent);
}

.shot__img {
  display: block;
  inline-size: 100%;
  block-size: 7rem;
  object-fit: cover;
}

.shot__badge {
  position: absolute;
  inset-block-start: 0;
  inset-inline-start: 0;
  background-color: var(--accent);
  color: var(--terminal);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  padding: 0.125rem 0.375rem;
}

.shot__acts {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.25rem;
  padding: 0.375rem;
  border-block-start: 3px solid var(--terminal-rule);
}

.shot__act,
.shot__arrow {
  background: none;
  border: 0;
  border-radius: 0;
  cursor: pointer;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  color: var(--terminal-dim);
  padding: 0.125rem 0.25rem;
}

.shot__act:hover:not(:disabled),
.shot__arrow:hover:not(:disabled) {
  color: var(--accent);
}

.shot__act:disabled,
.shot__arrow:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.shot__act--del:hover:not(:disabled) {
  color: #d4665a;
}

.shot__arrow {
  font-size: 0.875rem;
  line-height: 1;
}

.gal__foot {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.gal__add {
  border: 3px solid var(--terminal-text);
  border-radius: 0;
  background-color: transparent;
  color: var(--terminal-text);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.4375rem 0.875rem;
  cursor: pointer;
}

.gal__add:hover:not(:disabled) {
  background-color: var(--accent);
  border-color: var(--accent);
  color: var(--terminal);
}

.gal__add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.gal__err {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  color: #d4665a;
  margin: 0;
}
</style>
