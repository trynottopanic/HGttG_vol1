#include "guide_control_codec.h"

#include <string.h>

struct cursor { const uint8_t *data; size_t length,offset; };
static int take(struct cursor *c,uint8_t *value){if(c->offset>=c->length)return -1;*value=c->data[c->offset++];return 0;}
static int number(struct cursor *c,uint8_t expected,uint64_t *value){uint8_t first,info;size_t bytes,index;if(take(c,&first)<0||(first>>5)!=expected)return -1;info=first&31u;if(info<24u){*value=info;return 0;}if(info==24u)bytes=1;else if(info==25u)bytes=2;else if(info==26u)bytes=4;else if(info==27u)bytes=8;else return -1;if(c->length-c->offset<bytes)return -1;*value=0;for(index=0;index<bytes;++index)*value=(*value<<8)|c->data[c->offset++];if((bytes==1&&*value<24)||(bytes==2&&*value<=255)||(bytes==4&&*value<=65535)||(bytes==8&&*value<=UINT32_MAX))return -1;return 0;}
static int map_length(struct cursor *c,uint64_t *value){return number(c,5,value);}
static int bytes16(struct cursor *c,uint8_t value[16]){uint64_t length;if(number(c,2,&length)<0||length!=16||c->length-c->offset<16)return -1;memcpy(value,c->data+c->offset,16);c->offset+=16;return 0;}
static int decode_value(struct cursor *c,struct guide_control_value *value){uint8_t first;if(c->offset>=c->length)return -1;first=c->data[c->offset];if((first>>5)==0){value->type=GUIDE_CONTROL_UINT;return number(c,0,&value->number);}if((first>>5)==2){value->type=GUIDE_CONTROL_BYTES16;return bytes16(c,value->bytes);}return -1;}

int guide_control_decode_request(const uint8_t *payload,size_t length,struct guide_control_request *request)
{
    struct cursor c={payload,length,0};uint64_t pairs,index,key,args,previous=UINT64_MAX;
    if(payload==NULL||request==NULL){return -1;}memset(request,0,sizeof(*request));
    if(map_length(&c,&pairs)<0||pairs!=3)return -1;
    for(index=0;index<pairs;++index){
        if(number(&c,0,&key)<0||(index&&key<=previous)){return -1;}previous=key;
        if(key==0){uint64_t operation;if(number(&c,0,&operation)<0||operation==0||operation>UINT16_MAX)return -1;request->operation=(uint16_t)operation;}
        else if(key==1){
            if(map_length(&c,&args)<0||args>GUIDE_CONTROL_MAX_ARGUMENTS)return -1;
            request->argument_count=(size_t)args;previous=UINT64_MAX;
            for(size_t item=0;item<(size_t)args;++item){uint64_t argument_key;if(number(&c,0,&argument_key)<0||argument_key>UINT16_MAX||(item&&argument_key<=previous))return -1;previous=argument_key;request->arguments[item].key=(uint16_t)argument_key;if(decode_value(&c,&request->arguments[item])<0)return -1;}
            previous=key;
        } else if(key==2){if(number(&c,0,&request->deadline_ns)<0)return -1;}
        else return -1;
    }
    return c.offset==c.length&&request->operation&&request->deadline_ns?0:-1;
}

int guide_control_get_uint(const struct guide_control_request *request,uint16_t key,uint64_t *value){for(size_t i=0;i<request->argument_count;++i)if(request->arguments[i].key==key&&request->arguments[i].type==GUIDE_CONTROL_UINT){*value=request->arguments[i].number;return 0;}return -1;}
int guide_control_get_bytes16(const struct guide_control_request *request,uint16_t key,uint8_t value[16]){for(size_t i=0;i<request->argument_count;++i)if(request->arguments[i].key==key&&request->arguments[i].type==GUIDE_CONTROL_BYTES16){memcpy(value,request->arguments[i].bytes,16);return 0;}return -1;}

static int put(uint8_t *out,size_t cap,size_t *used,uint8_t value){if(*used>=cap)return -1;out[(*used)++]=value;return 0;}
static int encode_number(uint8_t *out,size_t cap,size_t *used,uint8_t major,uint64_t value){size_t bytes,index;if(value<24)return put(out,cap,used,(uint8_t)((major<<5)|value));if(value<=255)bytes=1;else if(value<=65535)bytes=2;else if(value<=UINT32_MAX)bytes=4;else bytes=8;if(put(out,cap,used,(uint8_t)((major<<5)|(bytes==1?24:bytes==2?25:bytes==4?26:27)))<0)return -1;for(index=bytes;index>0;--index)if(put(out,cap,used,(uint8_t)(value>>((index-1)*8)))<0)return -1;return 0;}
static int encode_values(uint8_t *out,size_t cap,size_t *used,const struct guide_control_value *values,size_t count){if(encode_number(out,cap,used,5,count)<0)return -1;for(size_t index=0;index<count;++index){if(index&&values[index].key<=values[index-1].key)return -1;if(encode_number(out,cap,used,0,values[index].key)<0)return -1;if(values[index].type==GUIDE_CONTROL_UINT){if(encode_number(out,cap,used,0,values[index].number)<0)return -1;}else if(values[index].type==GUIDE_CONTROL_BYTES16){if(encode_number(out,cap,used,2,16)<0||cap-*used<16)return -1;memcpy(out+*used,values[index].bytes,16);*used+=16;}else return -1;}return 0;}
size_t guide_control_encode_request(uint8_t *out,size_t cap,uint16_t operation,const struct guide_control_value *arguments,size_t count,uint64_t deadline){size_t used=0;if(out==NULL||operation==0||deadline==0||count>GUIDE_CONTROL_MAX_ARGUMENTS||encode_number(out,cap,&used,5,3)<0||encode_number(out,cap,&used,0,0)<0||encode_number(out,cap,&used,0,operation)<0||encode_number(out,cap,&used,0,1)<0||encode_values(out,cap,&used,arguments,count)<0||encode_number(out,cap,&used,0,2)<0||encode_number(out,cap,&used,0,deadline)<0)return 0;return used;}
size_t guide_control_encode_reply(uint8_t *out,size_t cap,uint16_t outcome,const struct guide_control_value *results,size_t count){size_t used=0,index;if(out==NULL||count>GUIDE_CONTROL_MAX_ARGUMENTS||encode_number(out,cap,&used,5,2)<0||encode_number(out,cap,&used,0,0)<0||encode_number(out,cap,&used,0,outcome)<0||encode_number(out,cap,&used,0,1)<0||encode_number(out,cap,&used,5,count)<0)return 0;for(index=0;index<count;++index){if(index&&results[index].key<=results[index-1].key)return 0;if(encode_number(out,cap,&used,0,results[index].key)<0)return 0;if(results[index].type==GUIDE_CONTROL_UINT){if(encode_number(out,cap,&used,0,results[index].number)<0)return 0;}else if(results[index].type==GUIDE_CONTROL_BYTES16){if(encode_number(out,cap,&used,2,16)<0||cap-used<16)return 0;memcpy(out+used,results[index].bytes,16);used+=16;}else return 0;}return used;}

int guide_control_decode_reply(const uint8_t *payload,size_t length,struct guide_control_reply *reply){struct cursor c={payload,length,0};uint64_t pairs,key,count,previous=UINT64_MAX;if(!payload||!reply)return -1;memset(reply,0,sizeof(*reply));if(map_length(&c,&pairs)<0||pairs!=2)return -1;for(size_t i=0;i<2;++i){if(number(&c,0,&key)<0||(i&&key<=previous))return -1;previous=key;if(key==0){uint64_t outcome;if(number(&c,0,&outcome)<0||outcome>UINT16_MAX)return -1;reply->outcome=(uint16_t)outcome;}else if(key==1){if(map_length(&c,&count)<0||count>GUIDE_CONTROL_MAX_ARGUMENTS)return -1;reply->result_count=(size_t)count;previous=UINT64_MAX;for(size_t j=0;j<(size_t)count;++j){uint64_t result_key;if(number(&c,0,&result_key)<0||result_key>UINT16_MAX||(j&&result_key<=previous))return -1;previous=result_key;reply->results[j].key=(uint16_t)result_key;if(decode_value(&c,&reply->results[j])<0)return -1;}previous=key;}else return -1;}return c.offset==c.length?0:-1;}
int guide_control_reply_uint(const struct guide_control_reply *reply,uint16_t key,uint64_t *value){for(size_t i=0;i<reply->result_count;++i)if(reply->results[i].key==key&&reply->results[i].type==GUIDE_CONTROL_UINT){*value=reply->results[i].number;return 0;}return -1;}
int guide_control_reply_bytes16(const struct guide_control_reply *reply,uint16_t key,uint8_t value[16]){for(size_t i=0;i<reply->result_count;++i)if(reply->results[i].key==key&&reply->results[i].type==GUIDE_CONTROL_BYTES16){memcpy(value,reply->results[i].bytes,16);return 0;}return -1;}
