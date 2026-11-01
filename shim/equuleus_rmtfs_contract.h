/* SPDX-License-Identifier: MIT
 * Equuleus RMTFS preflight contract. CPU-owned until a separate SCM stage.
 */
#pragma once
#include <stdint.h>
#define EQ_RMT_POOL 0xa8000000ull
#define EQ_RMT_PAGE 0x4000ull
#define EQ_RMT_DATA (EQ_RMT_POOL + 2 * EQ_RMT_PAGE)
#define EQ_RMT_BYTES 0x200000ull
#define EQ_RMT_SPAN (EQ_RMT_BYTES + 3 * EQ_RMT_PAGE)
#define EQ_RMT_MAGIC 0x363531544d525145ull
#define EQ_RMT_GUARD 0xa5b6c7d8e9fa0b1cull
struct eq_rmt_contract {
 uint64_t magic, version, pool, span, data, bytes, guard, checksum;
};
static inline uint64_t eq_rmt_checksum(const struct eq_rmt_contract *c)
{
 return c->magic ^ c->version ^ c->pool ^ c->span ^ c->data ^ c->bytes ^ c->guard;
}
static inline int eq_rmt_valid(const struct eq_rmt_contract *c)
{
 return c->magic==EQ_RMT_MAGIC && c->version==1 && c->pool==EQ_RMT_POOL &&
 c->span==EQ_RMT_SPAN && c->data==EQ_RMT_DATA && c->bytes==EQ_RMT_BYTES &&
 c->guard==EQ_RMT_GUARD && c->checksum==eq_rmt_checksum(c);
}
static inline int eq_rmt_overlap(uint64_t a,uint64_t n,uint64_t b,uint64_t s)
{
 if (a>UINT64_MAX-n || b>UINT64_MAX-s) return 1;
 return n && s && a<b+s && b<a+n;
}
static inline int eq_rmt_boot_ranges_ok(uint64_t rd_start,uint64_t rd_end,
 uint64_t dtb,uint64_t dt_size,uint64_t shim_start,uint64_t shim_end,
 uint64_t kernel,uint64_t kernel_size,uint64_t fb,uint64_t fb_size)
{
 return kernel>=0x100000000ull && kernel_size && kernel<=UINT64_MAX-kernel_size &&
 rd_end>rd_start && shim_end>shim_start && dt_size>=40 && dt_size<=0x1000000 &&
 !eq_rmt_overlap(EQ_RMT_POOL,EQ_RMT_SPAN,rd_start,rd_end-rd_start) &&
 !eq_rmt_overlap(EQ_RMT_POOL,EQ_RMT_SPAN,dtb,dt_size) &&
 !eq_rmt_overlap(EQ_RMT_POOL,EQ_RMT_SPAN,shim_start,shim_end-shim_start) &&
 !eq_rmt_overlap(EQ_RMT_POOL,EQ_RMT_SPAN,fb,fb_size);
}
