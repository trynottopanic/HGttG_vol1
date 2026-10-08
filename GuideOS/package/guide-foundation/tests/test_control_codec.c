#include "guide_control_codec.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){uint8_t payload[]={0xa3,0x00,0x03,0x01,0xa1,0x00,0x01,0x02,0x19,0x03,0xe8};struct guide_control_request request;uint64_t value;uint8_t reply[64];struct guide_control_value results[2]={{0,GUIDE_CONTROL_UINT,1,{0}},{1,GUIDE_CONTROL_BYTES16,0,{0}}};memset(results[1].bytes,0x55,16);assert(guide_control_decode_request(payload,sizeof(payload),&request)==0);assert(request.operation==3&&request.deadline_ns==1000);assert(guide_control_get_uint(&request,0,&value)==0&&value==1);assert(guide_control_encode_reply(reply,sizeof(reply),0,results,2)>0);payload[0]=0xbf;assert(guide_control_decode_request(payload,sizeof(payload),&request)<0);puts("GUIDE_CONTROL_CODEC_PASS");return 0;}
