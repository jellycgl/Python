import json
from typing import Dict, List, Optional
from .api_server import ApiServer
from .discovery import discover_new_ips, _DISCOVERABLE_MAIN_TYPES


from netbrain.utils import nbjson
from netbrain.sysapi import datamodel
from netbrain.sysapi import pluginfw


# Candidate keys for the device's management IP in the EcoStruxure response.
_DEVICE_IP_KEYS = (
    "mgmtIP",
    "managementIp",
    "ipAddress",
    "ip",
    "primaryIp",
)


def _extract_device_ip(device: dict) -> str:
    for key in _DEVICE_IP_KEYS:
        value = device.get(key)
        if value:
            return value
    return ""


# =========================================================
# Device Location Update Logic
# =========================================================
def update_device_loc(device: dict) -> Dict[str, str]:
    """
    Update device location and return detailed result.

    Returns:
        {
            "status": "success" | "not_found" | "failed" | "skipped",
            "device": "hostname",
            "reason": "detailed reason",
            "ip": "management IP" (set for not_found and undiscovered shells),
            "is_end_system": True when the matched NetBrain device is an
                             un-identified End-System shell (candidate for
                             re-discovery); already-identified End Systems such
                             as APC PDUs (mainType 1004) are NOT flagged.
        }
    """

    if not device:
        return {
            "status": "failed",
            "device": "",
            "reason": "Empty device data",
            "ip": "",
            "is_end_system": False,
        }

    device_name = device.get("hostname")
    if not device_name:
        return {
            "status": "failed",
            "device": "",
            "reason": "Missing hostname",
            "ip": "",
            "is_end_system": False,
        }

    nb_device = datamodel.GetDeviceObject(device_name)
    if not nb_device:
        return {
            "status": "not_found",
            "device": device_name,
            "reason": "Device not found in NetBrain",
            "ip": _extract_device_ip(device),
            "is_end_system": False,
        }

    # An existing device that is still an un-identified End-System shell should
    # be re-discovered (to promote it to a fully managed device), on top of its
    # location update. Already-identified End Systems (e.g. an APC PDU at
    # mainType 1004) are NOT re-discovered -- they are already discovered.
    # Flag the shell and carry its management IP for the discovery task.
    is_end_system = nb_device.get("mainType") in _DISCOVERABLE_MAIN_TYPES
    end_system_ip = _extract_device_ip(device) if is_end_system else ""

    new_location = device.get("location", "")
    current_location = nb_device.get("loc", "")

    if not new_location:
        return {
            "status": "skipped",
            "device": device_name,
            "reason": "Location empty in API data",
            "ip": end_system_ip,
            "is_end_system": is_end_system,
        }

    if new_location == current_location:
        return {
            "status": "skipped",
            "device": device_name,
            "reason": "Location unchanged",
            "ip": end_system_ip,
            "is_end_system": is_end_system,
        }

    try:
        result = datamodel.SetDeviceProperty(
            "loc",
            device_name,
            new_location,
        )

        if result:
            return {
                "status": "success",
                "device": device_name,
                "reason": "Location updated",
                "ip": end_system_ip,
                "is_end_system": is_end_system,
            }

        return {
            "status": "failed",
            "device": device_name,
            "reason": "SetDeviceProperty returned False",
            "ip": end_system_ip,
            "is_end_system": is_end_system,
        }

    except Exception as exc:
        return {
            "status": "failed",
            "device": device_name,
            "reason": f"Exception: {exc}",
            "ip": end_system_ip,
            "is_end_system": is_end_system,
        }


# =========================================================
# Handle API Request
# =========================================================
def handle_device_api_request(
    api_server: ApiServer,
    api_param: dict,
    test_limit: Optional[int] = None,
) -> List[str]:
    """
    Process a 'devices' API request and update locations.

    Returns the management IPs that are candidates for discovery: devices not
    found in NetBrain, plus existing End Systems (which get re-discovered to be
    promoted to fully managed devices). Returns an empty list when there are
    none or when the request itself fails.
    """

    response = api_server.forward_request_to_fs(
        "get_data",
        api_param,
    )

    if not response:
        pluginfw.AddLog(
            "No response received from API Server.",
            pluginfw.WARNING,
        )
        return []

    try:
        parsed = (
            response
            if isinstance(response, list)
            else json.loads(response)
        )
    except Exception as exc:
        pluginfw.AddLog(
            f"Invalid API response format: {exc}",
            pluginfw.ERROR,
        )
        return []

    # Normalize response to a list of devices
    if isinstance(parsed, dict):
        # Adjust key based on actual API response structure (e.g. "data", "devices", "items")
        devices = (
            parsed.get("data")
            or parsed.get("devices")
            or parsed.get("items")
            or []
        )
    elif isinstance(parsed, list):
        devices = parsed
    else:
        pluginfw.AddLog(
            f"Unexpected API response type: {type(parsed)}",
            pluginfw.ERROR,
        )
        return []

    if not devices:
        pluginfw.AddLog(
            "No devices found in API response.",
            pluginfw.WARNING,
        )
        return []

    # =============================
    # Test Mode Control
    # =============================
    if test_limit and isinstance(test_limit, int):
        devices = devices[:test_limit]
        pluginfw.AddLog(
            f"Test mode enabled. Processing first {test_limit} devices only.",
            pluginfw.INFO,
        )

    # =============================
    # Result Summary Structure
    # =============================
    summary: Dict[str, List[str]] = {
        "success": [],
        "not_found": [],
        "failed": [],
        "skipped": [],
    }

    not_found_ips: List[str] = []
    not_found_missing_ip: List[str] = []
    end_system_ips: List[str] = []

    # =============================
    # Process Devices
    # =============================
    for device in devices:
        result = update_device_loc(device)

        status = result["status"]
        device_name = result["device"]
        reason = result["reason"]

        summary[status].append(f"{device_name} ({reason})")

        if status == "not_found":
            ip = result.get("ip", "")
            if ip:
                not_found_ips.append(ip)
            else:
                not_found_missing_ip.append(device_name)
        elif result.get("is_end_system"):
            # Existing End System: its location was already handled above;
            # also queue it for re-discovery so NetBrain can upgrade it.
            ip = result.get("ip", "")
            if ip:
                end_system_ips.append(ip)

    # =============================
    # Print Summary Report
    # =============================
    pluginfw.AddLog("========== LOC Update Summary ==========", pluginfw.INFO)

    pluginfw.AddLog(
        f"Success ({len(summary['success'])})",
        pluginfw.INFO,
    )
    for item in summary["success"]:
        pluginfw.AddLog(f"  - {item}", pluginfw.INFO)

    pluginfw.AddLog(
        f"Not Found ({len(summary['not_found'])})",
        pluginfw.WARNING,
    )
    for item in summary["not_found"]:
        pluginfw.AddLog(f"  - {item}", pluginfw.WARNING)

    pluginfw.AddLog(
        f"Failed ({len(summary['failed'])})",
        pluginfw.ERROR,
    )
    for item in summary["failed"]:
        pluginfw.AddLog(f"  - {item}", pluginfw.ERROR)

    pluginfw.AddLog(
        f"Skipped ({len(summary['skipped'])})",
        pluginfw.INFO,
    )
    for item in summary["skipped"]:
        pluginfw.AddLog(f"  - {item}", pluginfw.INFO)

    if not_found_missing_ip:
        pluginfw.AddLog(
            f"Not-found devices without an IP (cannot discover): "
            f"{not_found_missing_ip}",
            pluginfw.WARNING,
        )

    if end_system_ips:
        pluginfw.AddLog(
            f"Existing End System(s) queued for re-discovery "
            f"({len(end_system_ips)}): {end_system_ips}",
            pluginfw.INFO,
        )

    pluginfw.AddLog("=========================================", pluginfw.INFO)

    return not_found_ips + end_system_ips


# =========================================================
# Get Domain Name
# =========================================================
def get_domain_name() -> str:
    domain_details = datamodel.GetCurrentDomainInfo()
    return domain_details.get("domainDbName", "")


# =========================================================
# Plugin Entry Point
# =========================================================
def run(input_data: str) -> bool:
    """
    Plugin entry point.

    Fetches device data from EcoStruxure, then:
      1. Updates the location (loc) of devices that already exist in NetBrain.
      2. Triggers an on-demand discovery task for device IPs that NetBrain
         does not yet know about.
    """

    # -------------------------
    # Parse Input
    # -------------------------
    try:
        plugin_input = nbjson.loads(input_data)
    except Exception as exc:
        pluginfw.AddLog(
            f"Input JSON invalid: {exc}",
            pluginfw.ERROR,
        )
        return False

    # -------------------------
    # Get Domain
    # -------------------------
    domain_name = get_domain_name()

    pluginfw.AddLog(
        f"Current Domain DB Name: {domain_name}",
        pluginfw.INFO,
    )

    if not domain_name:
        pluginfw.AddLog(
            "Failed to get current domain name.",
            pluginfw.ERROR,
        )
        return False

    # -------------------------
    # Validate Input
    # -------------------------
    api_server_name = plugin_input.get("apiServerName")
    if not api_server_name:
        pluginfw.AddLog(
            "API Server Name missing in input.",
            pluginfw.ERROR,
        )
        return False

    api_requests = plugin_input.get("apiRequests")
    if not api_requests:
        pluginfw.AddLog(
            "API Requests missing in input.",
            pluginfw.ERROR,
        )
        return False

    test_limit = plugin_input.get("testLimit")

    # -------------------------
    # Initialize API Server
    # -------------------------
    api_server = ApiServer(
        domain_name,
        api_server_name,
    )

    # -------------------------
    # Process Requests
    # -------------------------
    discovery_candidate_ips: List[str] = []

    for request in api_requests:

        category = request.get("category")
        if not category:
            pluginfw.AddLog(
                "API request category missing.",
                pluginfw.ERROR,
            )
            continue

        if category == "devices":

            api_url = request.get("api_url")
            if not api_url:
                pluginfw.AddLog(
                    "API URL missing in devices request.",
                    pluginfw.ERROR,
                )
                continue

            not_found_ips = handle_device_api_request(
                api_server,
                {"api_url": api_url},
                test_limit=test_limit,
            )
            discovery_candidate_ips.extend(not_found_ips)

    # -------------------------
    # Trigger Discovery for new devices
    # -------------------------
    if discovery_candidate_ips:
        pluginfw.AddLog(
            f"Triggering NetBrain discovery for "
            f"{len(discovery_candidate_ips)} new device IP(s).",
            pluginfw.INFO,
        )
        discover_new_ips(discovery_candidate_ips)
    else:
        pluginfw.AddLog(
            "No new devices to discover.",
            pluginfw.INFO,
        )

    return True
