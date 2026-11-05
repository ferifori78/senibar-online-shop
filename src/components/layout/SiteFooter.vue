<script setup>
import { RouterLink } from 'vue-router'

import BrandMark from '@/components/base/BrandMark.vue'
import { panelPath } from '@/constants/panel'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const year = new Date().getFullYear()
</script>

<template>
  <footer class="foot">
    <div class="foot__grid">
      <div class="foot__col">
        <!-- The mark spells the name, so the label below it would repeat it. -->
        <BrandMark :size="56" class="foot__mark" />
        <p class="foot__text">
          رست‌خانه‌ی قهوه‌ی تخصصی. هر لات پس از سفارش رست می‌شود و تاریخ رست روی
          هر بسته ثبت است.
        </p>
        <RouterLink to="/about" class="foot__link">داستان ما</RouterLink>
      </div>

      <nav class="foot__col" aria-label="فروشگاه">
        <p class="foot__label">فروشگاه</p>
        <RouterLink to="/products" class="foot__link">قهوه‌ها</RouterLink>
        <RouterLink to="/cart" class="foot__link">سبد خرید</RouterLink>
        <RouterLink v-if="auth.isAuthenticated" to="/orders" class="foot__link">
          پیگیری سفارش
        </RouterLink>
      </nav>

      <nav class="foot__col" aria-label="حساب">
        <p class="foot__label">حساب</p>
        <template v-if="auth.isAuthenticated">
          <RouterLink to="/account" class="foot__link">حساب من</RouterLink>
          <RouterLink to="/support" class="foot__link">پشتیبانی</RouterLink>
          <RouterLink v-if="auth.isStaff" :to="panelPath()" class="foot__link">پنل مدیریت</RouterLink>
        </template>
        <template v-else>
          <RouterLink to="/login" class="foot__link">ورود</RouterLink>
          <RouterLink to="/register" class="foot__link">ثبت‌نام</RouterLink>
        </template>
      </nav>
    </div>

    <!-- Trust seals. Both are issued against senobar.shop and must load from
         the issuer's own domain to stay valid, so these are the one place in
         the site that renders a remote image. -->
    <section class="seals" aria-label="نشان‌های اعتماد">
      <a
        href="https://bitpay.ir/certificate-394376-senobar.shop"
        target="_blank"
        rel="noopener"
        class="seal"
      >
        <img
          src="https://bitpay.ir/theme/public/images/trusted-logo.svg"
          alt="نشان اعتماد بیت‌پی"
          loading="lazy"
        />
      </a>

      <a
        referrerpolicy="origin"
        target="_blank"
        rel="noopener"
        href="https://trustseal.enamad.ir/?id=7571135&Code=lXtQAHD7BmEIicEk3FW7dnsV9wvK2UCF"
        class="seal"
      >
        <img
          referrerpolicy="origin"
          src="https://trustseal.enamad.ir/logo.aspx?id=7571135&Code=lXtQAHD7BmEIicEk3FW7dnsV9wvK2UCF"
          alt="نماد اعتماد الکترونیکی"
          code="lXtQAHD7BmEIicEk3FW7dnsV9wvK2UCF"
          loading="lazy"
        />
      </a>
    </section>

    <p class="foot__rule">SENOBAR — {{ year }}</p>
  </footer>
</template>

<style scoped>
/* ==========================================================================
   SiteFooter — Editorial register
   ========================================================================== */

.foot {
  border-block-start: 3px solid var(--divider);
  padding: clamp(2.5rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 2rem;
}

.foot__grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) repeat(2, minmax(0, 1fr));
  gap: clamp(2rem, 5vw, 4rem);
}

@media (max-width: 44rem) {
  .foot__grid {
    grid-template-columns: 1fr;
    gap: 2rem;
  }
}

.foot__col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.625rem;
}

.foot__mark {
  margin-block-end: 0.25rem;
}

.foot__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0 0 0.25rem;
}

.foot__text {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.8;
  color: var(--ink-muted);
  max-width: 30rem;
  margin: 0;
}

.foot__link {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1rem;
  color: var(--ink);
  text-decoration: none;
  border-block-end: 2px solid transparent;
}

.foot__link:hover {
  border-block-end-color: var(--accent);
}

.foot__link:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

/* --- Trust seals ----------------------------------------------------------- */
.seals {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-block-start: clamp(2rem, 5vw, 3rem);
}

/* Framed like everything else, so a third-party badge does not read as a
   foreign object dropped onto the page. */
.seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  padding: 0.5rem;
  width: 6.5rem;
  height: 6.5rem;
}

.seal:hover {
  box-shadow: 4px 4px 0 var(--shadow);
}

.seal:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.seal img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  display: block;
}

.foot__rule {
  margin: clamp(2.5rem, 6vw, 4rem) 0 0;
  padding-block-start: 1.25rem;
  border-block-start: 3px solid var(--divider);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  color: var(--ink-muted);
}
</style>
