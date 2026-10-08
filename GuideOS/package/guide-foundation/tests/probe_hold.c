#include <signal.h>
#include <unistd.h>
static volatile sig_atomic_t stop;
static void handler(int value){(void)value;stop=1;}
int main(void){signal(SIGTERM,handler);while(!stop)pause();return 0;}
