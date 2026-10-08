#ifndef GUIDE_CONTROL_CODEC_H
#define GUIDE_CONTROL_CODEC_H

#include <stddef.h>
#include <stdint.h>

#define GUIDE_CONTROL_MAX_ARGUMENTS 8u

enum guide_control_value_type { GUIDE_CONTROL_UINT=1, GUIDE_CONTROL_BYTES16=2 };
struct guide_control_value { uint16_t key; uint8_t type; uint64_t number; uint8_t bytes[16]; };
struct guide_control_request { uint16_t operation; uint64_t deadline_ns; size_t argument_count; struct guide_control_value arguments[GUIDE_CONTROL_MAX_ARGUMENTS]; };
struct guide_control_reply { uint16_t outcome; size_t result_count; struct guide_control_value results[GUIDE_CONTROL_MAX_ARGUMENTS]; };

int guide_control_decode_request(const uint8_t *payload,size_t length,struct guide_control_request *request);
int guide_control_get_uint(const struct guide_control_request *request,uint16_t key,uint64_t *value);
int guide_control_get_bytes16(const struct guide_control_request *request,uint16_t key,uint8_t value[16]);
int guide_control_decode_reply(const uint8_t *payload,size_t length,struct guide_control_reply *reply);
int guide_control_reply_uint(const struct guide_control_reply *reply,uint16_t key,uint64_t *value);
int guide_control_reply_bytes16(const struct guide_control_reply *reply,uint16_t key,uint8_t value[16]);
size_t guide_control_encode_request(uint8_t *output,size_t capacity,uint16_t operation,
                                    const struct guide_control_value *arguments,size_t count,
                                    uint64_t deadline_ns);
size_t guide_control_encode_reply(uint8_t *output,size_t capacity,uint16_t outcome,
                                  const struct guide_control_value *results,size_t count);

#endif
