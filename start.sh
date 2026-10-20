#!/bin/bash

# Lab Launcher - Startup Script
# ==========================================
# Serves the launcher dashboard (launcher/index.html) and starts every
# app marked "enabled" in launcher/config.json by running its own start.sh.
# Ctrl+C stops the apps and releases their ports, then asks whether the
# dashboard should be stopped too.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER_DIR="$ROOT/launcher"
CONFIG="$LAUNCHER_DIR/config.json"
LOG_DIR="$LAUNCHER_DIR/logs"
GRACE_TICKS=10          # shutdown grace period: 10 x 0.2s = 2s
mkdir -p "$LOG_DIR"

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

OK="${GREEN}✔${NC}"
WARN="${YELLOW}!${NC}"
FAIL="${RED}✘${NC}"
ARROW="${CYAN}→${NC}"
ASK="${CYAN}?${NC}"
RULE="──────────────────────────────────────────────────────────────"

# Each service gets its own process group (job control), so we can signal the whole tree.
set -m

PIDS=()                 # app process groups (the dashboard is tracked separately)
NAMES=()
APP_PORTS=()
CLAIMED_PORTS=" "
DASH_PID=""
LAUNCHER_PORT=""
INTERRUPTED=0           # set by Ctrl+C
STOPPING=0              # 1 while apps are being stopped
FORCE=0                 # set by a second Ctrl+C while stopping
APPS_STOPPED=0
DASH_STOPPED=0

if [ ! -f "$CONFIG" ]; then
    echo -e "${FAIL} Missing $CONFIG"
    exit 1
fi

# Emit one tab-separated line per app: enabled, name, dir, start, url, ports (space separated)
read_apps() {
    python3 - "$CONFIG" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
print("TITLE\t%s" % cfg.get("title", "Lab Launcher"))
print("PORT\t%s" % cfg.get("launcherPort", 8999))
for a in cfg.get("apps", []):
    print("APP\t%s\t%s\t%s\t%s\t%s\t%s" % (
        "1" if a.get("enabled", True) else "0",
        a["name"], a["dir"], a.get("start", "./start.sh"), a.get("url", ""),
        " ".join(str(p) for p in a.get("ports", []))))
PY
}

# Only processes that are LISTENING on the port (not browsers connected to it).
listener_pids() {
    lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null
}

# True while any process is left in this process group.
group_alive() {
    kill -0 -- "-$1" 2>/dev/null
}

banner() {
    echo ""
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${DIM}  $RULE${NC}"
}

# Stop every app (not the dashboard) and release their ports.
stop_apps() {
    [ "$APPS_STOPPED" = "1" ] && return
    APPS_STOPPED=1
    [ "${#PIDS[@]}" = "0" ] && return
    STOPPING=1
    local started=$SECONDS total=${#PIDS[@]} i pid

    banner "Shutting down"
    echo -e "  $ARROW Stopping $total apps ${DIM}(Ctrl+C again to force)${NC}"

    # Ask nicely: TERM the whole group of each app, so each app runs its own cleanup.
    local state=()
    for i in "${!PIDS[@]}"; do
        pid="${PIDS[$i]}"
        state[$i]=""
        kill -TERM -- "-$pid" 2>/dev/null || true
        kill -CONT -- "-$pid" 2>/dev/null || true
    done

    # Grace period (2s). Checks the whole group, so a lingering uvicorn/vite is noticed
    # even after its wrapper script has exited.
    local tick pending
    for ((tick = 0; tick <= GRACE_TICKS; tick++)); do
        pending=0
        for i in "${!PIDS[@]}"; do
            [ -n "${state[$i]}" ] && continue
            if group_alive "${PIDS[$i]}"; then
                pending=1
            else
                state[$i]="stopped"
                printf "  %b %-26s %b\n" "$OK" "${NAMES[$i]}" "${DIM}stopped${NC}"
            fi
        done
        [ "$pending" = "0" ] && break
        [ "$FORCE" = "1" ] && break
        [ "$tick" -lt "$GRACE_TICKS" ] && sleep 0.2
    done

    # Force kill whatever is still running.
    for i in "${!PIDS[@]}"; do
        [ -n "${state[$i]}" ] && continue
        kill -KILL -- "-${PIDS[$i]}" 2>/dev/null || true
        state[$i]="forced"
        printf "  %b %-26s %b\n" "$WARN" "${NAMES[$i]}" "${YELLOW}force stopped${NC}"
    done

    # Release every app port, even if a child escaped its process group.
    echo -e "  $ARROW Releasing ports"
    sleep 0.3
    local entry lp leftover freed=() stuck=()
    for entry in "${APP_PORTS[@]}"; do
        for lp in $entry; do
            leftover="$(listener_pids "$lp")"
            if [ -n "$leftover" ]; then
                echo "$leftover" | xargs kill -KILL 2>/dev/null || true
                freed+=("$lp")
            fi
        done
    done
    if [ "${#freed[@]}" -gt 0 ]; then
        sleep 0.3
        for lp in "${freed[@]}"; do
            [ -n "$(listener_pids "$lp")" ] && stuck+=("$lp")
        done
    fi

    if [ "${#stuck[@]}" -gt 0 ]; then
        echo -e "  $FAIL Could not release port(s): ${stuck[*]}"
    elif [ "${#freed[@]}" -gt 0 ]; then
        echo -e "  $OK All ports released ${DIM}(cleared lingering: ${freed[*]})${NC}"
    else
        echo -e "  $OK All ports released"
    fi

    echo -e "${DIM}  $RULE${NC}"
    echo -e "  ${GREEN}${BOLD}Apps stopped${NC} ${DIM}in $((SECONDS - started))s${NC}"
    STOPPING=0
}

# Stop the dashboard web server and release its port.
stop_dashboard() {
    [ "$DASH_STOPPED" = "1" ] && return
    DASH_STOPPED=1
    [ -z "$DASH_PID" ] && return

    kill -TERM -- "-$DASH_PID" 2>/dev/null || true
    local n
    for n in 1 2 3 4 5; do
        group_alive "$DASH_PID" || break
        sleep 0.2
    done
    kill -KILL -- "-$DASH_PID" 2>/dev/null || true

    local leftover
    leftover="$(listener_pids "$LAUNCHER_PORT")"
    [ -n "$leftover" ] && echo "$leftover" | xargs kill -KILL 2>/dev/null || true

    echo -e "  $OK Dashboard stopped ${DIM}(port $LAUNCHER_PORT released)${NC}"
}

# Runs on every exit path (errors, kill, etc.): stop whatever is still running, no questions.
cleanup_all() {
    trap - EXIT
    stop_apps
    stop_dashboard
}

# Ctrl+C only sets a flag; the main loop reacts. A second Ctrl+C while the apps
# are stopping skips the grace period.
on_int() {
    if [ "$STOPPING" = "1" ]; then
        FORCE=1
    else
        INTERRUPTED=1
    fi
}

# Ctrl+C: stop the apps, then ask about the dashboard.
shutdown_interactive() {
    INTERRUPTED=0
    echo ""
    stop_apps

    echo ""
    local ans=""
    printf "  %b Also stop the dashboard (http://localhost:%s)? [y/N] " "$ASK" "$LAUNCHER_PORT"
    # Ctrl+C at the prompt (read fails or the flag is set) means: stop everything.
    if ! read -r -n 1 ans </dev/tty 2>/dev/null; then ans="y"; fi
    [ "$INTERRUPTED" = "1" ] && ans="y"
    echo ""
    INTERRUPTED=0

    case "$ans" in
        y|Y)
            stop_dashboard
            echo -e "${DIM}  $RULE${NC}"
            echo -e "  ${GREEN}${BOLD}Shutdown complete${NC}"
            echo ""
            exit 0
            ;;
    esac

    echo -e "  $OK Dashboard left running: ${CYAN}${BOLD}http://localhost:$LAUNCHER_PORT${NC}"
    echo -e "  ${DIM}Press Ctrl+C to stop it.${NC}"
    echo ""
    while [ "$INTERRUPTED" = "0" ] && group_alive "$DASH_PID"; do
        sleep 2 &
        wait $!
    done
    echo ""
    stop_dashboard
    echo -e "${DIM}  $RULE${NC}"
    echo -e "  ${GREEN}${BOLD}Shutdown complete${NC}"
    echo ""
    exit 0
}

trap on_int INT
trap 'exit 0' TERM
trap cleanup_all EXIT

APPS_OUT="$(read_apps)" || { echo -e "${FAIL} Could not read config.json"; exit 1; }
LAUNCHER_PORT="$(echo "$APPS_OUT" | awk -F'\t' '$1=="PORT"{print $2}')"
TITLE="$(echo "$APPS_OUT" | awk -F'\t' '$1=="TITLE"{print $2}')"

banner "$TITLE"
echo -e "  $ARROW Starting services"

# Dashboard
if [ -n "$(listener_pids "$LAUNCHER_PORT")" ]; then
    echo -e "  $FAIL Port $LAUNCHER_PORT (dashboard) is already in use. Change launcherPort in config.json."
    exit 1
fi
(cd "$LAUNCHER_DIR" && exec python3 -m http.server "$LAUNCHER_PORT" --bind 127.0.0.1 \
    >"$LOG_DIR/dashboard.log" 2>&1) &
DASH_PID=$!
printf "  %b %-26s %b\n" "$OK" "Dashboard" "${DIM}http://localhost:$LAUNCHER_PORT${NC}"

# Apps
STARTED=0
while IFS=$'\t' read -r kind enabled name dir start url ports; do
    [ "$kind" = "APP" ] || continue

    if [ "$enabled" != "1" ]; then
        printf "  %b %-26s %b\n" "${DIM}-${NC}" "$name" "${DIM}disabled in config.json${NC}"
        continue
    fi

    app_dir="$ROOT/$dir"
    if [ ! -f "$app_dir/${start#./}" ]; then
        printf "  %b %-26s %b\n" "$FAIL" "$name" "${RED}${dir}/${start#./} not found${NC}"
        continue
    fi

    clash=""
    for p in $ports; do
        case "$CLAIMED_PORTS" in *" $p "*) clash="$clash $p" ;; esac
    done
    if [ -n "$clash" ]; then
        printf "  %b %-26s %b\n" "$FAIL" "$name" "${RED}port(s)$clash already used by another app${NC}"
        continue
    fi
    for p in $ports; do CLAIMED_PORTS="$CLAIMED_PORTS$p "; done

    log="$LOG_DIR/$(echo "$dir" | tr '[:upper:]' '[:lower:]').log"
    (cd "$app_dir" && exec bash "$start" </dev/null >"$log" 2>&1) &
    PIDS+=($!)
    NAMES+=("$name")
    APP_PORTS+=("$ports")
    STARTED=$((STARTED + 1))
    printf "  %b %-26s %b\n" "$OK" "$name" "${DIM}${url}${NC}"
done <<< "$APPS_OUT"

echo -e "${DIM}  $RULE${NC}"
echo -e "  ${BOLD}$STARTED apps starting.${NC} Open the dashboard:  ${CYAN}${BOLD}http://localhost:$LAUNCHER_PORT${NC}"
echo -e "  ${DIM}Dots turn green once each app is up (first start can take a minute while frontends build).${NC}"
echo -e "  ${DIM}Logs: launcher/logs/   |   Press Ctrl+C to stop the apps.${NC}"
echo ""

# Stay in the foreground, and report any app that exits on its own.
# Waiting on a background sleep (instead of sleeping directly) lets Ctrl+C act immediately.
REPORTED=" "
while true; do
    [ "$INTERRUPTED" = "1" ] && shutdown_interactive
    for i in "${!PIDS[@]}"; do
        pid="${PIDS[$i]}"
        if ! kill -0 "$pid" 2>/dev/null; then
            case "$REPORTED" in *" $pid "*) ;; *)
                REPORTED="$REPORTED$pid "
                echo -e "  $WARN ${NAMES[$i]} exited unexpectedly ${DIM}(see launcher/logs/)${NC}"
            ;; esac
        fi
    done
    sleep 2 &
    wait $!
done
