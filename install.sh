#!/usr/bin/env bash
set -euo pipefail

# ── CianaParrot Installer ────────────────────────────────────────────────────
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/emanueleielo/ciana-parrot/main/install.sh | bash
#   bash install.sh [--dry-run] [--no-prompt] [--help]

REPO_URL="https://github.com/emanueleielo/ciana-parrot.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/ciana-parrot}"
GATEWAY_PORT=9842
SERVICE_NAME="dev.cianaparrot.gateway"

# ── Flags ─────────────────────────────────────────────────────────────────────

DRY_RUN=false
NO_PROMPT=false

for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY_RUN=true ;;
    --no-prompt) NO_PROMPT=true ;;
    -h|--help)
      echo "Usage: bash install.sh [--dry-run] [--no-prompt] [--help]"
      echo ""
      echo "  --dry-run     Preview actions without making changes"
      echo "  --no-prompt   Non-interactive mode (reads from env vars)"
      echo "  --help        Show this help message"
      exit 0
      ;;
    *) ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${GREEN}[+]${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}[!]${RESET} %s\n" "$1"; }
error() { printf "${RED}[x]${RESET} %s\n" "$1" >&2; exit 1; }
step()  { printf "\n${CYAN}${BOLD}── %s${RESET}\n" "$1"; }

# ── stdin workaround for curl | bash ─────────────────────────────────────────
# When piped, stdin is the script itself — redirect to the real terminal.

if [ "$NO_PROMPT" = false ] && [ "$DRY_RUN" = false ] && [ ! -t 0 ]; then
  if [ -e /dev/tty ]; then
    exec </dev/tty
  else
    NO_PROMPT=true
    warn "No terminal available — switching to --no-prompt mode."
  fi
fi

run() {
  if [ "$DRY_RUN" = true ]; then
    printf "${YELLOW}[dry-run]${RESET} "
    printf "%q " "$@"
    printf "\n"
  else
    "$@"
  fi
}

prompt_value() {
  local label="$1" var="$2" required="${3:-false}" secret="${4:-false}"
  local value

  # In no-prompt mode, read from environment
  if [ "$NO_PROMPT" = true ]; then
    value="${!var:-}"
    if [ -z "$value" ] && [ "$required" = true ]; then
      error "Missing required env var: $var"
    fi
    echo "$value"
    return
  fi

  if [ "$required" = true ]; then
    while true; do
      printf "  %s: " "$label" >&2
      if [ "$secret" = true ]; then
        read -r -s value
        printf "\n" >&2
      else
        read -r value
      fi
      if [ -n "$value" ]; then break; fi
      warn "This field is required."
    done
  else
    printf "  %s (Enter to skip): " "$label" >&2
    if [ "$secret" = true ]; then
      read -r -s value
      printf "\n" >&2
    else
      read -r value
    fi
  fi
  echo "$value"
}

generate_token() {
  # Generate a random token using available tools
  if command -v openssl &>/dev/null; then
    openssl rand -hex 16
  else
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 32
  fi
}

os_type() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux)  echo "linux" ;;
    *)      echo "unknown" ;;
  esac
}

# ── 1. Check prerequisites ───────────────────────────────────────────────────

step "Checking prerequisites"

HAS_ERRORS=false

# Docker
if ! command -v docker &>/dev/null; then
  warn "Docker not found."
  if [ "$(os_type)" = "macos" ]; then
    warn "  Install: https://docs.docker.com/desktop/install/mac-install/"
  else
    warn "  Install: https://docs.docker.com/engine/install/"
  fi
  HAS_ERRORS=true
elif ! docker ps &>/dev/null; then
  warn "Docker is installed but the daemon is not running."
  if [ "$(os_type)" = "macos" ]; then
    warn "  Open Docker Desktop and try again."
  else
    warn "  Run: sudo systemctl start docker"
    warn "  To avoid sudo: sudo usermod -aG docker \$USER && newgrp docker"
  fi
  HAS_ERRORS=true
else
  info "Docker: $(docker --version | head -1)"
fi

# Docker Compose — detect plugin vs standalone
COMPOSE_CMD=""
if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
  info "Docker Compose: $(docker compose version --short 2>/dev/null || echo 'ok')"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
  info "Docker Compose (standalone): $(docker-compose --version)"
else
  warn "Docker Compose not found."
  warn "  It should be included with Docker Desktop."
  warn "  Or install: https://docs.docker.com/compose/install/"
  HAS_ERRORS=true
fi

# Git
if command -v git &>/dev/null; then
  info "Git: $(git --version)"
else
  warn "Git not found."
  if [ "$(os_type)" = "macos" ]; then
    warn "  Install: xcode-select --install"
  else
    warn "  Install: sudo apt install git"
  fi
  HAS_ERRORS=true
fi

# Make
if command -v make &>/dev/null; then
  info "Make: available"
else
  warn "Make not found."
  if [ "$(os_type)" = "macos" ]; then
    warn "  Install: xcode-select --install"
  else
    warn "  Install: sudo apt install build-essential"
  fi
  HAS_ERRORS=true
fi

# Python3 (needed for host gateway)
if command -v python3 &>/dev/null; then
  info "Python3: $(python3 --version)"
else
  warn "Python3 not found (needed for host gateway)."
  if [ "$(os_type)" = "macos" ]; then
    warn "  Install: brew install python3"
  else
    warn "  Install: sudo apt install python3 python3-venv"
  fi
  HAS_ERRORS=true
fi

if [ "$HAS_ERRORS" = true ]; then
  if [ "$DRY_RUN" = true ]; then
    warn "Some prerequisites are missing (continuing in dry-run mode)."
  else
    error "Fix the issues above and re-run the installer."
  fi
fi

# ── 2. Clone or update repo ──────────────────────────────────────────────────

step "Setting up repository"

if [ ! -d "$INSTALL_DIR" ]; then
  info "Cloning to $INSTALL_DIR..."
  run git clone "$REPO_URL" "$INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  info "Repository exists at $INSTALL_DIR"
  cd "$INSTALL_DIR"
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    warn "Local changes detected — skipping git pull to preserve your work."
    run git fetch origin
  else
    info "No local changes — pulling latest..."
    run git pull origin main
  fi
else
  error "$INSTALL_DIR exists but is not a git repository."
fi

if [ -d "$INSTALL_DIR" ]; then
  cd "$INSTALL_DIR"
else
  [ "$DRY_RUN" = true ] && info "Would cd to $INSTALL_DIR (does not exist yet)"
fi

# ── 3. Setup .env ────────────────────────────────────────────────────────────

step "Configuring environment"

set_env_var() {
  local key="$1" value="$2" file="$INSTALL_DIR/.env"
  local tmpfile="${file}.tmp"

  if [ "$DRY_RUN" = true ]; then
    info "[dry-run] Would set ${key} in .env"
    return
  fi

  if grep -q "^${key}=" "$file" 2>/dev/null; then
    # Update existing — rewrite line without sed (safe for any value)
    k="$key" v="$value" awk 'BEGIN{FS=OFS="="} $1==ENVIRON["k"]{print ENVIRON["k"]"="ENVIRON["v"]; next} {print}' "$file" > "$tmpfile"
    chmod 600 "$tmpfile"
    mv "$tmpfile" "$file"
  elif grep -q "^# *${key}=" "$file" 2>/dev/null; then
    # Uncomment and set
    k="$key" v="$value" awk '{if($0 ~ "^# *"ENVIRON["k"]"="){print ENVIRON["k"]"="ENVIRON["v"]}else{print}}' "$file" > "$tmpfile"
    chmod 600 "$tmpfile"
    mv "$tmpfile" "$file"
  else
    echo "${key}=${value}" >> "$file"
  fi
  chmod 600 "$file"
}

env_var_is_set() {
  # Check if a key exists in .env with a real value (not empty, not a placeholder)
  local key="$1"
  local val
  val=$(grep "^${key}=" "$INSTALL_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2-)
  # Empty
  [ -z "$val" ] && return 1
  # Common placeholder patterns
  [[ "$val" == *"..."* ]] && return 1
  [[ "$val" =~ ^YOUR_ ]] && return 1
  [[ "$val" =~ ^CHANGEME ]] && return 1
  [[ "$val" =~ ^\<.*\>$ ]] && return 1
  [[ "$val" =~ ^xxx+$ ]] && return 1
  return 0
}

if [ -f "$INSTALL_DIR/.env" ]; then
  info ".env already exists — checking for missing variables..."

  # Add any new variables from .env.example that aren't in .env
  UPDATED=false
  while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
    key="${line%%=*}"
    if ! grep -q "^${key}=" "$INSTALL_DIR/.env" 2>/dev/null; then
      if [ "$DRY_RUN" = true ]; then
        info "[dry-run] Would add missing variable: $key"
      else
        echo "$line" >> "$INSTALL_DIR/.env"
        chmod 600 "$INSTALL_DIR/.env"
        info "Added missing variable: $key"
      fi
      UPDATED=true
    fi
  done < "$INSTALL_DIR/.env.example"

  if [ "$UPDATED" = false ]; then
    info ".env is up to date."
  fi

  # Check required vars have real values
  REQUIRED_VARS=("TELEGRAM_BOT_TOKEN" "ANTHROPIC_API_KEY")
  for var in "${REQUIRED_VARS[@]}"; do
    if ! env_var_is_set "$var"; then
      if [ "$NO_PROMPT" = true ]; then
        error "$var is missing or has a placeholder value in .env"
      elif [ "$DRY_RUN" = false ]; then
        warn "$var is missing or has a placeholder value."
        NEW_VAL=$(prompt_value "$var" "$var" true true)
        set_env_var "$var" "$NEW_VAL"
      fi
    fi
  done

  # Ensure gateway tokens exist
  if ! grep -q "^GATEWAY_TOKEN=" "$INSTALL_DIR/.env" 2>/dev/null || ! env_var_is_set "GATEWAY_TOKEN"; then
    GW_TOKEN="ciana-gw-$(generate_token)"
    set_env_var "GATEWAY_TOKEN" "$GW_TOKEN"
    set_env_var "CC_BRIDGE_TOKEN" "$GW_TOKEN"
    info "Gateway token generated automatically."
  fi
else
  info "Creating .env from template..."
  run cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  run chmod 600 "$INSTALL_DIR/.env"

  if [ "$DRY_RUN" = true ]; then
    info "Would prompt for API keys (skipping in dry-run)"
  elif [ "$NO_PROMPT" = true ]; then
    # Read from environment variables
    TELEGRAM_TOKEN=$(prompt_value "Telegram Bot Token" TELEGRAM_BOT_TOKEN true true)
    set_env_var "TELEGRAM_BOT_TOKEN" "$TELEGRAM_TOKEN"

    ANTHROPIC_KEY=$(prompt_value "Anthropic API Key" ANTHROPIC_API_KEY true true)
    set_env_var "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"

    GW_TOKEN="ciana-gw-$(generate_token)"
    set_env_var "GATEWAY_TOKEN" "$GW_TOKEN"
    set_env_var "CC_BRIDGE_TOKEN" "$GW_TOKEN"

    # Optional — set only if present in env
    for var in OPENAI_API_KEY BRAVE_API_KEY GH_TOKEN GEMINI_API_KEY ELEVENLABS_API_KEY; do
      [ -n "${!var:-}" ] && set_env_var "$var" "${!var}"
    done

    info ".env configured from environment variables."
  else
    printf "\n  Enter your API keys below. Secrets are never displayed.\n"
    printf "\n  ${BOLD}Telegram Bot:${RESET} Open Telegram, search @BotFather, send /newbot and follow the steps.\n"
    printf "  Copy the token it gives you and paste it below.\n\n"

    # Required (secret=true hides input)
    TELEGRAM_TOKEN=$(prompt_value "Telegram Bot Token" TELEGRAM_BOT_TOKEN true true)
    set_env_var "TELEGRAM_BOT_TOKEN" "$TELEGRAM_TOKEN"

    ANTHROPIC_KEY=$(prompt_value "Anthropic API Key" ANTHROPIC_API_KEY true true)
    set_env_var "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"

    # Auto-generate gateway token
    GW_TOKEN="ciana-gw-$(generate_token)"
    set_env_var "GATEWAY_TOKEN" "$GW_TOKEN"
    set_env_var "CC_BRIDGE_TOKEN" "$GW_TOKEN"
    info "Gateway token generated automatically."

    # Optional (all secrets)
    printf "\n  Optional keys (press Enter to skip):\n\n"

    OPENAI_KEY=$(prompt_value "OpenAI API Key (voice transcription + image gen)" OPENAI_API_KEY false true)
    [ -n "$OPENAI_KEY" ] && set_env_var "OPENAI_API_KEY" "$OPENAI_KEY"

    BRAVE_KEY=$(prompt_value "Brave Search API Key (or uses DuckDuckGo)" BRAVE_API_KEY false true)
    [ -n "$BRAVE_KEY" ] && set_env_var "BRAVE_API_KEY" "$BRAVE_KEY"

    GH_KEY=$(prompt_value "GitHub Token" GH_TOKEN false true)
    [ -n "$GH_KEY" ] && set_env_var "GH_TOKEN" "$GH_KEY"

    GEMINI_KEY=$(prompt_value "Gemini API Key (image gen + PDF)" GEMINI_API_KEY false true)
    [ -n "$GEMINI_KEY" ] && set_env_var "GEMINI_API_KEY" "$GEMINI_KEY"

    ELEVENLABS_KEY=$(prompt_value "ElevenLabs API Key (text-to-speech)" ELEVENLABS_API_KEY false true)
    [ -n "$ELEVENLABS_KEY" ] && set_env_var "ELEVENLABS_API_KEY" "$ELEVENLABS_KEY"

    info ".env configured."
  fi
fi

# ── 4. Build and start Docker ────────────────────────────────────────────────

step "Building and starting CianaParrot"

if [ -n "$COMPOSE_CMD" ]; then
  run $COMPOSE_CMD build
  run $COMPOSE_CMD up -d
else
  run make build
  run make up
fi

if [ "$DRY_RUN" = false ] && [ -n "$COMPOSE_CMD" ]; then
  sleep 3
  if $COMPOSE_CMD ps --format json 2>/dev/null | grep -q '"running"'; then
    info "Docker container is running."
  elif $COMPOSE_CMD ps 2>/dev/null | grep -q "Up"; then
    info "Docker container is running."
  else
    warn "Container may not be running. Check: make logs"
  fi
fi

# ── 5. Setup gateway ─────────────────────────────────────────────────────────

step "Setting up host gateway"

# Check if port is in use (with fallback for systems without lsof)
port_in_use() {
  if command -v lsof &>/dev/null; then
    lsof -i ":$GATEWAY_PORT" &>/dev/null
  elif command -v ss &>/dev/null; then
    ss -ltn "sport = :$GATEWAY_PORT" 2>/dev/null | grep -q LISTEN
  elif curl -sf "http://localhost:$GATEWAY_PORT/health" &>/dev/null; then
    return 0
  else
    return 1
  fi
}

if port_in_use; then
  EXISTING_PID=""
  if command -v lsof &>/dev/null; then
    EXISTING_PID=$(lsof -t -i ":$GATEWAY_PORT" 2>/dev/null | head -1 || true)
  fi
  if [ -n "$EXISTING_PID" ]; then
    warn "Port $GATEWAY_PORT is already in use (PID: $EXISTING_PID)."
  else
    warn "Port $GATEWAY_PORT is already in use."
  fi
  warn "If that's a previous gateway, it's already running — skipping."
else
  # Setup venv for gateway
  if [ ! -d "$INSTALL_DIR/.venv" ]; then
    info "Creating Python venv for gateway..."
    run python3 -m venv "$INSTALL_DIR/.venv"
  fi

  # Install/update gateway dependencies (always, so re-runs pick up changes)
  if [ -f "$INSTALL_DIR/src/gateway/requirements.txt" ]; then
    run "$INSTALL_DIR/.venv/bin/pip" install -q --upgrade -r "$INSTALL_DIR/src/gateway/requirements.txt"
  else
    run "$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pyyaml "pydantic>=2,<3" python-dotenv
  fi

  SETUP_SERVICE=false
  if [ "$NO_PROMPT" = false ] && [ "$DRY_RUN" = false ]; then
    printf "\n  Start gateway automatically on boot? [Y/n] "
    read -r ANSWER
    ANSWER="${ANSWER:-Y}"
    if [[ "$ANSWER" =~ ^[Yy] ]]; then
      SETUP_SERVICE=true
    fi
  fi

  if [ "$SETUP_SERVICE" = true ] && [ "$DRY_RUN" = false ]; then
    OS=$(os_type)

    if [ "$OS" = "macos" ]; then
      # launchd user agent
      PLIST_DIR="$HOME/Library/LaunchAgents"
      PLIST_FILE="$PLIST_DIR/${SERVICE_NAME}.plist"
      LOG_DIR="$INSTALL_DIR/logs"
      mkdir -p "$PLIST_DIR" "$LOG_DIR"

      cat > "$PLIST_FILE" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/.venv/bin/python</string>
        <string>${INSTALL_DIR}/src/gateway/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/gateway.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/gateway.log</string>
</dict>
</plist>
PLIST

      # Unload first if already loaded (idempotent)
      launchctl bootout "gui/$(id -u)/$SERVICE_NAME" 2>/dev/null || true
      launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"
      info "Gateway registered as launchd service (starts on boot)."
      info "  Logs: $LOG_DIR/gateway.log"
      info "  Stop: launchctl bootout gui/$(id -u)/$SERVICE_NAME"

    elif [ "$OS" = "linux" ]; then
      # systemd user service
      UNIT_DIR="$HOME/.config/systemd/user"
      mkdir -p "$UNIT_DIR"
      UNIT_FILE="$UNIT_DIR/cianaparrot-gateway.service"

      cat > "$UNIT_FILE" <<UNIT
[Unit]
Description=CianaParrot Host Gateway
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/src/gateway/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT

      systemctl --user daemon-reload
      systemctl --user enable --now cianaparrot-gateway.service
      info "Gateway registered as systemd user service (starts on boot)."
      info "  Logs: journalctl --user -u cianaparrot-gateway -f"
      info "  Stop: systemctl --user stop cianaparrot-gateway"

    fi
  else
    # Background process — clean stale pidfile
    if [ -f "$INSTALL_DIR/.gateway.pid" ]; then
      OLD_PID=$(cat "$INSTALL_DIR/.gateway.pid" 2>/dev/null)
      if [ -n "$OLD_PID" ] && ! kill -0 "$OLD_PID" 2>/dev/null; then
        rm -f "$INSTALL_DIR/.gateway.pid"
      fi
    fi
    info "Starting gateway in background..."
    if [ "$DRY_RUN" = false ]; then
      mkdir -p "$INSTALL_DIR/logs"
      nohup "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/src/gateway/server.py" \
        > "$INSTALL_DIR/logs/gateway.log" 2>&1 &
      GW_PID=$!
      echo "$GW_PID" > "$INSTALL_DIR/.gateway.pid"
      info "Gateway started (PID: $GW_PID)."
      info "  Logs: tail -f $INSTALL_DIR/logs/gateway.log"
      info "  Stop: kill \$(cat $INSTALL_DIR/.gateway.pid)"
    else
      run nohup ".venv/bin/python" src/gateway/server.py
    fi
  fi

  # Verify gateway is running
  if [ "$DRY_RUN" = false ]; then
    sleep 2
    if curl -sf "http://localhost:$GATEWAY_PORT/health" &>/dev/null; then
      info "Gateway is healthy on port $GATEWAY_PORT."
    else
      warn "Gateway may not be ready yet. Check: tail -f $INSTALL_DIR/logs/gateway.log"
    fi
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────

step "CianaParrot is ready!"

printf "
  ${GREEN}${BOLD}Open Telegram, find your bot, and send /start${RESET}

  Useful commands (run from ${INSTALL_DIR}):
    ${CYAN}make logs${RESET}      Follow bot logs
    ${CYAN}make down${RESET}      Stop the bot
    ${CYAN}make restart${RESET}   Rebuild and restart
    ${CYAN}make gateway${RESET}   Start gateway manually (if not using a service)

  Re-run installer with flags:
    ${CYAN}bash install.sh --dry-run${RESET}       Preview without changes
    ${CYAN}bash install.sh --no-prompt${RESET}      Non-interactive (reads env vars)

  Or via curl:
    ${CYAN}curl -fsSL .../install.sh | bash -s -- --dry-run${RESET}
    ${CYAN}curl -fsSL .../install.sh | bash -s -- --no-prompt${RESET}

"
