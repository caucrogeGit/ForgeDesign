#!/usr/bin/env bash
# Qualification FD-ACCEPTANCE-001 : run.sh <dossier-de-travail> [étape ...]
#
# Étapes (toutes par défaut, dans cet ordre) :
#   wheels    construit les roues Forge Design, Circuit, Flowchart ; inspecte la roue
#   install   venv neuf, installation hors ligne depuis les roues ; pip check
#   projects  venv Forge 1.0.0rc9 et projets A, B, C, D (build_projects.py)
#   startup   démarrage depuis /tmp, HOME, un projet Forge : aucun projet implicite
#   security  écoute 127.0.0.1 uniquement, garde Host/Origin
#   browsers  parcours complet Chromium puis Firefox, modules actifs, instantanés
#   nojs      parcours Firefox sans JavaScript
#   measures  performance, commandes runtime, endurance mémoire
#   shutdown  preview réelle active, Ctrl+C (SIGINT), aucun processus restant
#
# Variables : CIRCUIT_REPO, FLOWCHART_REPO (dépôts des modules, par défaut à côté
# de ce dépôt), PYTHON (interpréteur de base), PORT (8765).
# Tout est écrit sous <dossier-de-travail> ; aucun projet utilisateur n'est lu.
set -euo pipefail

KIT=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$KIT/../.." && pwd)
[ $# -ge 1 ] || { sed -n '2,18p' "$0"; exit 2; }
mkdir -p "$1"
WORK=$(cd "$1" && pwd)
shift
STAGES=${*:-"wheels install projects startup security browsers nojs measures shutdown"}
CIRCUIT_REPO=${CIRCUIT_REPO:-$REPO/../ForgeDesign-Circuit}
FLOWCHART_REPO=${FLOWCHART_REPO:-$REPO/../ForgeDesign-Flowchart}
PYTHON=${PYTHON:-python3}
PORT=${PORT:-8765}
RESULTS=$WORK/results
PROJECTS=$WORK/projects
FD=$WORK/fd-venv
mkdir -p "$RESULTS"

log() { printf '\n== %s\n' "$*"; }
probe() { "$PYTHON" "$KIT/probes.py" "$@"; }

# Serveur réel isolé : HOME et XDG propres au dossier de travail.
SERVER_PID=""
server_start() {
  local cwd=$1; shift
  rm -rf "$WORK/home" && mkdir -p "$WORK/home"
  (cd "$cwd" && exec env -u XDG_CONFIG_HOME -u XDG_STATE_HOME -u XDG_DATA_HOME \
    -u XDG_CACHE_HOME HOME="$WORK/home" "$PYTHON" -c \
    'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execv(sys.argv[1], sys.argv[1:])' \
    "$FD/bin/forge-design" --no-browser "$@" >"$RESULTS/server-$(date +%s%N).log" 2>&1) &
  SERVER_PID=$!
  for _ in $(seq 100); do
    curl -s -o /dev/null "http://127.0.0.1:$PORT/" && return 0
    sleep 0.1
  done
  echo "serveur non démarré" >&2
  return 1
}
server_stop() {
  local signal=${1:-TERM}
  [ -n "$SERVER_PID" ] || return 0
  kill -"$signal" "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
  SERVER_PID=""
}
trap 'server_stop TERM' EXIT

# Écritures attendues et documentées, par projet ; tout le reste est inattendu.
allowed() {
  case $1 in
    B-write) echo ".forge-design .forge-design/locks .forge-design/locks/design-fd3f841edd23559ec492bfeac366d3e784d18a0cb70549aed8d6940740fceecd.lock .forge-design/history.jsonl mvc/circuit/demo.circuit.json \
mvc/flowchart/simple.flow.json mvc/views/contacts/list.design.json \
storage/logs/errors.dev.jsonl" ;;
    C-check) echo "CONTROLLER_IMPORTED" ;;
    *) echo "" ;;
  esac
}

diff_all() {
  local tag=$1
  for project in "$PROJECTS"/*/; do
    local name
    name=$(basename "$project")
    # shellcheck disable=SC2046
    probe diff "$RESULTS/snap-before-$tag-$name.json" "$RESULTS/snap-after-$tag-$name.json" \
      $(allowed "$name") >"$RESULTS/diff-$tag-$name.json" \
      && echo "  $name : conforme" || echo "  $name : ÉCART $(cat "$RESULTS/diff-$tag-$name.json")"
  done
}

snapshot_all() {
  local tag=$1
  for project in "$PROJECTS"/*/; do
    probe snapshot "$project" "$RESULTS/snap-$tag-$(basename "$project").json" >/dev/null
  done
}

stage_wheels() {
  log "Roues"
  rm -rf "$WORK/wheels" && mkdir -p "$WORK/wheels"
  for source in "$REPO" "$CIRCUIT_REPO" "$FLOWCHART_REPO"; do
    local had_build=0
    [ -d "$source/build" ] && had_build=1
    git -C "$source" status --short | sed "s|^|  $(basename "$source") : |"
    "$PYTHON" -m pip wheel --no-deps -q -w "$WORK/wheels" "$source"
    [ $had_build -eq 1 ] || rm -rf "$source/build"
  done
  ls "$WORK/wheels"
  probe wheel "$WORK"/wheels/forge_design-*.whl "$REPO" | tee "$RESULTS/wheel.json"
}

stage_install() {
  log "Installation hors ligne"
  rm -rf "$WORK/deps" "$FD"
  "$PYTHON" -m pip download -q -d "$WORK/deps" "$WORK"/wheels/*.whl
  "$PYTHON" -m venv "$FD"
  "$FD/bin/pip" install -q --no-index --find-links "$WORK/wheels" --find-links "$WORK/deps" \
    forge-design forge-design-circuit forge-design-flowchart
  "$FD/bin/pip" check | tee "$RESULTS/pip-check.txt"
  "$FD/bin/forge-design" --version | tee "$RESULTS/version.txt"
  "$FD/bin/pip" list 2>/dev/null | grep -i forge | tee "$RESULTS/installed.txt"
}

stage_projects() {
  log "Venv Forge et projets"
  if [ ! -x "$WORK/forge-venv/bin/python" ]; then
    "$PYTHON" -m venv "$WORK/forge-venv"
    "$WORK/forge-venv/bin/pip" install -q "forge-mvc==1.0.0rc9" "forge-mvc-sqlite==1.0.0rc9" \
      "forge-mvc-entities==1.0.0rc9"
  fi
  "$WORK/forge-venv/bin/pip" check
  "$PYTHON" "$KIT/build_projects.py" "$WORK" "$WORK/forge-venv"
}

stage_startup() {
  log "Démarrage depuis plusieurs dossiers courants"
  for cwd in /tmp "$WORK/home-cwd" "$PROJECTS/A"; do
    mkdir -p "$cwd"
    local started=$(date +%s%N)
    server_start "$cwd"
    local ready=$(( ($(date +%s%N) - started) / 1000000 ))
    local page
    page=$(curl -s "http://127.0.0.1:$PORT/")
    local implicit=no
    grep -q "Aucun projet" <<<"$page" || implicit=yes
    echo "{\"cwd\": \"$cwd\", \"ready_ms\": $ready, \"projet_implicite\": \"$implicit\"}" \
      | tee -a "$RESULTS/startup.jsonl"
    server_stop TERM
  done
}

stage_security() {
  log "Sécurité locale"
  server_start /tmp
  probe listen "$SERVER_PID" | tee "$RESULTS/listen.json"
  probe hostguard "$PORT" | tee "$RESULTS/hostguard.json"
  server_stop TERM
}

stage_browsers() {
  log "Navigateurs (modules actifs)"
  "$PYTHON" "$KIT/build_projects.py" "$WORK" "$WORK/forge-venv" >/dev/null
  for browser in chromium firefox; do
    snapshot_all "before-$browser"
    server_start /tmp --module forge_design_circuit --module forge_design_flowchart
    PROJECTS="$PROJECTS" WORK="$WORK" node "$KIT/browser.mjs" "$browser" \
      "http://127.0.0.1:$PORT" | tee "$RESULTS/browser-$browser.txt" || true
    server_stop TERM
    snapshot_all "after-$browser"
    diff_all "$browser" | tee "$RESULTS/diff-$browser.txt"
    # Projets, serveur et profils navigateur : rien ne doit survivre.
    probe strays "$WORK" >"$RESULTS/strays-$browser.json" || true; tail -n 1 "$RESULTS/strays-$browser.json"
    "$PYTHON" "$KIT/build_projects.py" "$WORK" "$WORK/forge-venv" >/dev/null
  done
}

stage_nojs() {
  log "Firefox sans JavaScript"
  server_start /tmp --module forge_design_circuit --module forge_design_flowchart
  PROJECTS="$PROJECTS" WORK="$WORK" node "$KIT/nojs.mjs" "http://127.0.0.1:$PORT" \
    | tee "$RESULTS/nojs.txt" || true
  server_stop TERM
  probe strays "$WORK" >"$RESULTS/strays-nojs.json" || true; tail -n 1 "$RESULTS/strays-nojs.json"
  "$PYTHON" "$KIT/build_projects.py" "$WORK" "$WORK/forge-venv" >/dev/null
}

stage_measures() {
  log "Mesures"
  server_start /tmp
  probe perf "$PORT" "$PROJECTS/B" 7 | tee "$RESULTS/perf-B.json"
  probe perf "$PORT" "$PROJECTS/D" 5 | tee "$RESULTS/perf-D.json"
  probe runtime "$PORT" "$PROJECTS/A" 5 | tee "$RESULTS/runtime-A.json"
  server_stop TERM
  # Endurance avec modules actifs, sur le projet qui porte leurs ressources.
  server_start /tmp --module forge_design_circuit --module forge_design_flowchart
  probe endurance "$PORT" "$SERVER_PID" "$PROJECTS/B-write" | tee "$RESULTS/endurance.json"
  server_stop TERM
}

stage_shutdown() {
  log "Arrêt par Ctrl+C avec preview réelle active"
  # A-preview comparé avant/après : arrêt des processus ET aucune écriture.
  probe snapshot "$PROJECTS/A-preview" "$RESULTS/snap-before-shutdown-A-preview.json" >/dev/null
  server_start /tmp
  curl -s -o /dev/null -X POST -H "Origin: http://127.0.0.1:$PORT" \
    -H "Sec-Fetch-Site: same-origin" --data-urlencode "path=$PROJECTS/A-preview" \
    "http://127.0.0.1:$PORT/inspector"
  curl -s -o /dev/null -w 'preview %{http_code}\n' -X POST \
    -H "Origin: http://127.0.0.1:$PORT" -H "Sec-Fetch-Site: same-origin" \
    --data-urlencode "design=contacts/list.design.json" \
    "http://127.0.0.1:$PORT/editor/real-preview/start" | tee "$RESULTS/shutdown.txt"
  probe tree "$SERVER_PID" | tee -a "$RESULTS/shutdown.txt"
  probe listen "$SERVER_PID" | tee -a "$RESULTS/shutdown.txt" || true
  server_stop INT
  sleep 1
  probe strays "$PROJECTS" >>"$RESULTS/shutdown.txt" || true; tail -n 1 "$RESULTS/shutdown.txt"
  probe snapshot "$PROJECTS/A-preview" "$RESULTS/snap-after-shutdown-A-preview.json" >/dev/null
  probe diff "$RESULTS/snap-before-shutdown-A-preview.json" \
    "$RESULTS/snap-after-shutdown-A-preview.json" >"$RESULTS/diff-shutdown-A-preview.json" \
    && echo "  A-preview : conforme" | tee -a "$RESULTS/shutdown.txt" \
    || echo "  A-preview : ÉCART $(cat "$RESULTS/diff-shutdown-A-preview.json")" | tee -a "$RESULTS/shutdown.txt"
}

for stage in $STAGES; do
  "stage_$stage"
done
log "Résultats : $RESULTS"
