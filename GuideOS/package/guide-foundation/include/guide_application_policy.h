#ifndef GUIDE_APPLICATION_POLICY_H
#define GUIDE_APPLICATION_POLICY_H
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#define GUIDE_APPLICATION_REGISTRY "/var/lib/guideos/applications"
/* Canonical, owner-installed runtime records, never cartridge declarations. */
struct guide_application_policy {
    uint64_t code, capabilities, private_bytes;
    char id[64], module[64], entry[64], digest[65], binding[65], version[49];
    unsigned format, testing;
};
static inline int guide_policy_identifier(const char *s,int dotted) {
    if(!s[0]||!((s[0]>='a'&&s[0]<='z')||s[0]=='_'))return 0;
    for(;*s;++s)if(!((*s>='a'&&*s<='z')||(*s>='0'&&*s<='9')||*s=='_'||(dotted&&(*s=='.'||*s=='-'))))return 0;
    return 1;
}
static inline int guide_application_policy_load(uint64_t code,struct guide_application_policy *p) {
    char path[256],body[2048]={0},canonical[2048];struct stat st;unsigned long long a,b,c;ssize_t n;int fd;
    if(code<10000||code>UINT32_MAX)return -1;
    snprintf(path,sizeof(path),GUIDE_APPLICATION_REGISTRY "/%llu.policy",(unsigned long long)code);
    fd=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)return -1;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_uid!=0||(st.st_mode&022)||st.st_size<=0||st.st_size>2047){close(fd);return -1;}
    n=read(fd,body,sizeof(body)-1);close(fd);if(n!=st.st_size)return -1;
    memset(p,0,sizeof(*p));
    p->format=(code==10010 && !strncmp(body,"format=3\n",9))?3:2;
    if(sscanf(body+9,"code=%llu\nid=%63s\nmodule=%63s\nentry=%63s\nsha256=%64s\ncapabilities=%llu\nprivate_bytes=%llu\nversion=%48s\nbinding=%64s\n",&a,p->id,p->module,p->entry,p->digest,&b,&c,p->version,p->binding)!=9)return -1;
    if((p->format==2 && strncmp(body,"format=2\n",9))||a!=code||!guide_policy_identifier(p->id,1)||!guide_policy_identifier(p->module,0)||!guide_policy_identifier(p->entry,0)||strlen(p->digest)!=64||strlen(p->binding)!=64||(b&~254ULL)||c==0||(p->format==2?c>524288:(b!=0||c!=536870912||strcmp(p->id,"planegotchi")||strcmp(p->module,"guide_planegotchi_worker")||strcmp(p->entry,"main"))))return -1;
    for(size_t i=0;i<64;++i)if(!strchr("0123456789abcdef",p->digest[i])||!strchr("0123456789abcdef",p->binding[i]))return -1;
    for(size_t i=0;p->version[i];++i)if(!isalnum((unsigned char)p->version[i])&&p->version[i]!='.'&&p->version[i]!='-')return -1;
    if(!p->version[0]||!strcmp(p->version,".")||!strcmp(p->version,".."))return -1;
    snprintf(canonical,sizeof(canonical),"format=%u\ncode=%llu\nid=%s\nmodule=%s\nentry=%s\nsha256=%s\ncapabilities=%llu\nprivate_bytes=%llu\nversion=%s\nbinding=%s\n",p->format,a,p->id,p->module,p->entry,p->digest,b,c,p->version,p->binding);
    if(strcmp(body,canonical))return -1;
    /* The trusted publisher emits runtime_policy first. Compare the complete
       escaped scalar, including its delimiter, not a substring of arbitrary JSON. */
    char prefix[4096]="{\"runtime_policy\":\"",record[4096]={0};size_t used=strlen(prefix);
    for(size_t i=0;body[i];++i){if(body[i]=='\n'){prefix[used++]='\\';prefix[used++]='n';}else prefix[used++]=body[i];}
    memcpy(prefix+used,"\",\"state\":\"",11);used+=11;prefix[used]=0;
    int parent=open(p->format==3?"/var/lib/guideos/system-applications":GUIDE_APPLICATION_REGISTRY,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(parent<0)return -1;
    int app=openat(parent,p->id,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);close(parent);if(app<0)return -1;
    if(fstat(app,&st)||st.st_uid!=0||(st.st_mode&022)){close(app);return -1;}
    fd=openat(app,"installation.json",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);close(app);if(fd<0)return -1;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_uid!=0||(st.st_mode&022)||st.st_size<=0||st.st_size>32768){close(fd);return -1;}
    n=read(fd,record,sizeof(record)-1);close(fd);if(n<0||(size_t)n<used+10||memcmp(record,prefix,used))return -1;
    if(!strncmp(record+used,"committed\",",11))p->testing=0;
    else if(!strncmp(record+used,"testing\",",9))p->testing=1;
    else if(!strncmp(record+used,"preparing\",",11))p->testing=2;
    else return -1;
    p->code=a;p->capabilities=b;p->private_bytes=c;return 0;
}
#endif
