import time
from typing import List

from netbrain.sysapi import pluginfw
from netbrain.sysapi import datamodel as sysmodel


_log_thread_stopped = False


# =========================================================
# Build Network Info for Discovery
# =========================================================
def _get_all_frontserver(domain_info: dict) -> list:
    tenant_id = domain_info.get("tenantId", "")
    data = sysmodel.QueryDataFromDB(
        "NGSystem",
        "FrontServerAndGroup",
        {
            "registered": True,
            "isFSG": False,
            "tenantInfo._id": tenant_id,
            "$project": {"_id": 1},
        },
    )
    return [fs["_id"] for fs in data] if data else []


def _get_collection_ids(db: str, collection: str) -> list:
    data = sysmodel.QueryDataFromDB(
        db,
        collection,
        {"$project": {"_id": 1}},
    )
    return [item["_id"] for item in data] if data else []


def _build_network_info(domain_info: dict) -> dict:
    db = domain_info.get("domainDbName", "")
    return {
        "networkServer": _get_all_frontserver(domain_info),
        "telnetInfo": _get_collection_ids(db, "TelnetInfo"),
        "enablePasswd": _get_collection_ids(db, "EnablePasswd"),
        "snmpRoInfo": _get_collection_ids(db, "SnmpRoInfo"),
        "sshPrivateKey": [],
        "jumpbox": [],
    }


# =========================================================
# Discovery Log Streaming
# =========================================================
def _retrieve_log_thread(source_id: str) -> None:
    global _log_thread_stopped

    skip = 0
    domain_info = sysmodel.GetCurrentDomainInfo()
    db = domain_info.get("domainDbName", "")

    while not _log_thread_stopped:
        logs = sysmodel.QueryDataFromDB(
            db,
            "BenchmarkSummaryLog",
            {
                "dataSourceId": source_id,
                "$project": {"msg": 1},
                "$skip": skip,
            },
        )

        for data in logs:
            pluginfw.AddLog(
                f"Discover Execution Log: {data.get('msg', '')}",
                pluginfw.INFO,
            )

        skip += len(logs)
        time.sleep(1)


# =========================================================
# Filter: discover only un-identified End-System shells
# =========================================================
# An "End System" in NetBrain is a permanent device category (servers, PDUs,
# UPS, IP phones, ...), NOT a "not yet discovered" marker. A fully discovered
# device can still be an End System -- e.g. an APC PDU/UPS comes in as
# mainType 1004, vendor "APC". So mainType alone cannot tell "needs discovery"
# from "already discovered".
#
# These mainType codes are hosts NetBrain has SEEN (via a neighbor's
# ARP/MAC/route table) but has NOT yet identified. They are the shells worth
# (re)discovering so NetBrain can promote them to a concrete device.
_DISCOVERABLE_MAIN_TYPES = frozenset(
    {
        1005,  # Unknown End System
        1036,  # Unknown IP
    }
)

# Already-identified End Systems: a concrete device type is assigned, so these
# have already been discovered and must NOT be discovered again. APC PDU/UPS
# lands here as 1004 (vendor "APC"), which is why it kept being re-discovered
# before this distinction was made.
_IDENTIFIED_END_SYSTEM_MAIN_TYPES = frozenset(
    {
        1004,  # End System (e.g. APC PDU/UPS, servers)
        1027,  # IP Phone
        1028,  # Call Manager
    }
)

# Kept for callers that still need the full End-System set (any of the above).
_END_SYSTEM_MAIN_TYPES = _DISCOVERABLE_MAIN_TYPES | _IDENTIFIED_END_SYSTEM_MAIN_TYPES


def _get_main_type_by_ip(ip: str):
    """
    Resolve the device that owns `ip` in NetBrain and return its mainType.

    Returns the integer mainType, or None when no device is found for the IP
    (a brand-new host NetBrain doesn't know yet) or the lookup fails.
    """
    try:
        dev_name = sysmodel.GetDeviceNameFromIp(ip)
        if not dev_name:
            return None
        dev_obj = sysmodel.GetDeviceObject(dev_name)
        if not dev_obj:
            return None
        return dev_obj.get("mainType")
    except Exception as exc:
        pluginfw.AddLog(
            f"Device lookup failed for {ip}: {exc}.",
            pluginfw.WARNING,
        )
        return None


def _filter_end_system_ips(ips: List[str]) -> List[str]:
    """
    Keep only IPs worth discovering: un-identified End-System shells (decided
    by the device's mainType). Three groups are excluded:
      - Already-identified End Systems (e.g. APC PDU at mainType 1004): already
        discovered, so NOT re-discovered.
      - Network Devices: ignored.
      - IPs that don't resolve to any device (mainType is None): not
        discovered, but collected and reported in the final summary log.
    """
    discover_ips: List[str] = []
    already_discovered_ips: List[str] = []
    network_device_ips: List[str] = []
    unresolved_ips: List[str] = []

    for ip in ips:
        main_type = _get_main_type_by_ip(ip)
        if main_type in _DISCOVERABLE_MAIN_TYPES:
            discover_ips.append(ip)
        elif main_type in _IDENTIFIED_END_SYSTEM_MAIN_TYPES:
            already_discovered_ips.append(ip)
        elif main_type is None:
            unresolved_ips.append(ip)
        else:
            network_device_ips.append(ip)

    if already_discovered_ips:
        pluginfw.AddLog(
            f"Skipping {len(already_discovered_ips)} IP(s) already discovered "
            f"as identified End Systems (e.g. APC); not re-discovering: "
            f"{already_discovered_ips}",
            pluginfw.INFO,
        )

    if network_device_ips:
        pluginfw.AddLog(
            f"Ignoring {len(network_device_ips)} IP(s) that are Network "
            f"Devices in NetBrain: {network_device_ips}",
            pluginfw.INFO,
        )

    if unresolved_ips:
        pluginfw.AddLog(
            f"Skipping {len(unresolved_ips)} IP(s) that did not resolve to an "
            f"End System in NetBrain (not discovered): {unresolved_ips}",
            pluginfw.WARNING,
        )

    return discover_ips


# =========================================================
# Submit Discover Task
# =========================================================
def _submit_discover_task(
    ip_list: List[str],
    checked_objs: dict,
) -> dict:

    task_id = pluginfw.GetTaskId()
    op_user = pluginfw.GetOpUserName()
    op_user_id = pluginfw.GetOpUserId()
    domain_info = sysmodel.GetCurrentDomainInfo()

    task_param = {
        "_id": task_id,
        "startTime": "",
        "srcType": "ondemand discover task",
        "discoverOption": {
            "useAllNap": True,
            "discoverOption": 2138,
            "fromScan": True,
            "snmpIfPingFailed": False,
            "snmpOnly": False,
            "telnetIfPingFailed": False,
            "updateDeviceSetting": True,
            "pingTimeout": 2,
            "pingTryTimes": 2,
            "jumpboxOnly": False,
            "skipPing": False,
            "pollingOrder": 3,
            "accessOrder": 4,
            "domainOption": 1,
            "domainName": "",
            "maxDepth": 0,
            "scanMaskLength": 24,
            "cliForceTimeout": 600,
            "discoverInfo": {
                "proxy": "",
                "orignalProxy": "",
                "comefrom": "",
                "comefromMask": "",
                "ifname": "",
                "desc": "",
                "depth": 0,
                "ipSrc": 0,
                "subnetList": [],
            },
            "hostips": ip_list,
            "apiServers": [],
            "isAllDevices": False,
            "limitRunTimeMinutes": 0,
            "checkedObjs": checked_objs,
            "isBenchmark": False,
            "benchmarkTask": "",
        },
        "pluginExecPoints": [],
        "domain": domain_info,
        "opUser": op_user,
        "opUserId": op_user_id,
        "dataSource": {
            "sourceId": task_id,
            "sourceType": "ondemand discover task",
            "opUser": op_user,
        },
    }

    return sysmodel.SubmitChildTask("Discover", task_param, 3600)


# =========================================================
# Public Entry: Discover New IPs
# =========================================================
def discover_new_ips(new_ips: List[str]) -> bool:
    """
    Trigger an on-demand discovery task for the given management IPs.
    """

    global _log_thread_stopped

    if not new_ips:
        pluginfw.AddLog(
            "No new IPs to discover.",
            pluginfw.INFO,
        )
        return True

    # Deduplicate while preserving order
    unique_ips = list(dict.fromkeys(ip for ip in new_ips if ip))
    if not unique_ips:
        pluginfw.AddLog(
            "No valid IPs after filtering.",
            pluginfw.INFO,
        )
        return True

    # Discover only End Systems; IPs that are already Network Devices in
    # NetBrain are ignored.
    unique_ips = _filter_end_system_ips(unique_ips)
    if not unique_ips:
        pluginfw.AddLog(
            "No End-System IPs to discover (all candidates are Network Devices).",
            pluginfw.INFO,
        )
        return True

    domain_info = sysmodel.GetCurrentDomainInfo()
    checked_objs = _build_network_info(domain_info)

    if not checked_objs:
        pluginfw.AddLog(
            "Failed to build network settings for discovery.",
            pluginfw.ERROR,
        )
        return False

    _log_thread_stopped = False

    task_id = pluginfw.GetTaskId()
    log_thread = pluginfw.Thread(
        target=_retrieve_log_thread,
        args=(task_id,),
    )
    log_thread.start()

    pluginfw.AddLog(
        f"Starting discovery for {len(unique_ips)} new IP(s): {unique_ips}",
        pluginfw.INFO,
    )

    try:
        result = _submit_discover_task(unique_ips, checked_objs)
        pluginfw.AddLog(
            f"Discovery task submitted. Result: {result}",
            pluginfw.INFO,
        )
        return True
    except Exception as exc:
        pluginfw.AddLog(
            f"Discovery task failed: {exc}",
            pluginfw.ERROR,
        )
        return False
    finally:
        _log_thread_stopped = True
        log_thread.join()
