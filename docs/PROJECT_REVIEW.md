# Project review and Wi-Fi scan repair

Reviewed on 2026-11-06. This review traces the deployed V2 architecture and scan
failure, with a broader inspection of the legacy portal, services, installation,
agent networking modules, and tests. It is not a certification of every router
feature or a live Ubuntu hardware test.

## How the project runs

- `frontend/`: React dashboard. Browser API requests use the same origin, so a
  secondary laptop opens the Ubuntu gateway URL rather than running its own agent.
- `backend/`: FastAPI API, authentication, database records, analytics and agent
  client. The production Docker image also serves the built React application.
- `network-agent/`: privileged host daemon on port 8091. It calls Ubuntu tools
  and owns network operations; the backend container does not own the Wi-Fi radio.
- `captive-portal/`: separate HTTP portal on port 8088, proxying guest API requests.
- `docker-compose.yml`: database, backend/dashboard and captive portal containers.
  The agent is installed separately by systemd under `/opt/wifirouter/network-agent`.
- `web.py`, `helper.py`, root HTML/JS and `install.sh`/`update.sh`: legacy V1
  implementation. Its Wi-Fi page links to router administration and has no scanner.
- `scripts/development/run_dev.py`: explicitly simulated development environment.

## Scan defects fixed

1. `agent.main` referenced `Any` without importing it. Importing the daemon failed
   before its HTTP server could start on the deployed Python versions.
2. The backend allowed five seconds while scan subprocesses could take much longer.
   It now allows 45 seconds for a bounded 25-second nmcli attempt plus 10-second
   iwlist fallback.
3. Scanning did not scope nmcli to the selected wireless interface. It now requests
   fresh results using `device wifi list ifname ... --rescan yes`.
4. Wireless discovery depended on `wl*` names, with a hard-coded fallback adapter.
   Discovery now uses wireless sysfs attributes; explicit service configuration
   remains supported. New service templates no longer force `wlp2s0`.
5. Command and agent failures could become invented access points or a silent empty
   list. Real Wi-Fi requests now report failures as HTTP 503 to the dashboard;
   simulated fallback is only available with explicit backend simulation enabled.
6. The UI ignored request errors and used initial loading state for rescans. It now
   shows errors, active rescans, empty results and simulation labels.
7. The parser mishandled escaped backslashes and collapsed access points by SSID.
   It now parses escaped fields, preserves separate BSSIDs and includes hidden APs.
8. Upgrade instructions restarted stale installed agent code. They now copy updated
   agent sources before restarting the service and rebuilding the web application.

A separate small fix makes legacy HTML/JS reads explicitly UTF-8 after the existing
legacy tests exposed Windows decoding errors.

## Findings outside the scan repair

- The Wi-Fi **Connect** button is still an alert placeholder; scanning does not
  implement switching the gateway's upstream connection.
- Other agent modules and non-Wi-Fi backend requests still have mock fallbacks.
  DHCP discovery can show sample devices when discovery is empty, and analytics
  generates a sample curve when history is absent. These need a separate pass to
  make production telemetry consistently truthful.
- Architecture documentation describes loopback-only agent binding, while production
  service units bind `0.0.0.0` for Docker host access. Actual deployment configuration
  should be used when assessing agent network exposure.
- Traffic-control commands create classes without per-device packet classification
  in `bandwidth/manager.py`, and subprocess return codes are not checked there.
  Real per-device shaping needs its own Linux integration verification.

## Validation

- Network-agent suite: 17 tests passed, including nine scan/startup regressions.
- Backend API tests: two existing API tests and six Wi-Fi tests passed.
- Backend security unit tests: four passed.
- Legacy portal suite: 30 passed after the UTF-8 fix.
- `npm run build --prefix frontend`: TypeScript and production build passed.
- Wi-Fi HTTP integration coverage runs an actual local agent HTTP server, calls it
  through the FastAPI route/client, and checks success and failure propagation.
  Only the operating-system scan command is mocked.
- `git diff --check`: passed.

The frontend build reports its existing large-bundle warning. Python tests emit
library deprecation/resource warnings. No real Ubuntu radio, systemd service,
Docker deployment, or interactive browser session was available for validation.
See `docs/troubleshooting/TROUBLESHOOTING.md` section 5 for deployment and hardware
verification commands.
