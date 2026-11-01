#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
bool equios_splash_render(volatile uint32_t *,unsigned,unsigned,unsigned,const uint8_t *,size_t);
bool equios_splash_show(void);
