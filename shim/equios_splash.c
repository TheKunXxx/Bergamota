/* EQSP: LE header,256 ARGB8888 colors, LE16 run length + palette index.
 * Validate the complete stream before writing the native framebuffer. */
#include "equios_splash.h"
static unsigned sp16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
bool equios_splash_render(volatile uint32_t *fb,unsigned w,unsigned h,unsigned pitch,const uint8_t *p,size_t n)
{
 if(!fb || !p || w!=1080 || h!=2248 || pitch<w || pitch>4096 || n<1036 ||
    p[0]!='E' || p[1]!='Q' || p[2]!='S' || p[3]!='P' || sp16(p+4)!=w || sp16(p+6)!=h || sp16(p+8)!=256 || sp16(p+10) || (n-1036)%3)return false;
 unsigned pixels=w*h,total=0;
 for(size_t at=1036;at<n;at+=3){unsigned run=sp16(p+at);if(!run || run>pixels-total)return false;total+=run;}
 if(total!=pixels)return false;
 total=0;
 for(size_t at=1036;at<n;at+=3){
  unsigned run=sp16(p+at),index=p[at+2];const uint8_t *c=p+12+index*4;
  uint32_t color=(uint32_t)c[0]|(uint32_t)c[1]<<8|(uint32_t)c[2]<<16|(uint32_t)c[3]<<24;
  while(run--){fb[(total/w)*pitch+total%w]=color;total++;}
 }
 return true;
}
#if defined(BOARD_EQUULEUS) && defined(EQUULEUS_SPLASH)
#include "console.h"
__asm__(".pushsection .rodata.splash,\"a\"\n.balign 4\n.global equios_splash_begin\n.global equios_splash_end\nequios_splash_begin:\n.incbin \"assets/equios-splash.rle\"\nequios_splash_end:\n.popsection\n");
extern const uint8_t equios_splash_begin[],equios_splash_end[];
bool equios_splash_show(void){return equios_splash_render(con_fb,FB_W,FB_H,FB_STRIDE/4,equios_splash_begin,(size_t)((uintptr_t)equios_splash_end-(uintptr_t)equios_splash_begin));}
#else
bool equios_splash_show(void){return false;}
#endif
