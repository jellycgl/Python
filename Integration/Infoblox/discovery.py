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
# Describe a host list for logging
# =========================================================
def _describe_targets(targets: List[str]) -> str:
    """
    Build a human label for a discovery target list.

    `targets` may hold single IPs and/or subnet CIDRs, so report whichever is
    present: "2 subnet(s)", "3 IP(s)", or "1 subnet(s) + 2 IP(s)" for a mix.
    """
    subnets = sum(1 for t in targets if "/" in t)
    ips = len(targets) - subnets
    if subnets and ips:
        return f"{subnets} subnet(s) + {ips} IP(s)"
    if subnets:
        return f"{subnets} subnet(s)"
    return f"{ips} IP(s)"


# =========================================================
# Submit Discover Task
# =========================================================
def _submit_discover_task(
    ip_list: List[str],
    checked_objs: dict,
) -> dict:

    task_id = pluginfw.GetTaskId()
    #task_id = "d86e9b34-da39-44a7-8635-a5a98bcc67a6"
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
            # hostips accepts both single IP addresses and subnet CIDRs, so a
            # discovery-by-network request can pass subnets through directly.
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
    Trigger an on-demand discovery task for the given hosts.

    `new_ips` may contain single IP addresses and/or subnet CIDRs
    (discovery-by-network); both are valid "hostips" values.
    """

    global _log_thread_stopped

    if not new_ips:
        pluginfw.AddLog(
            "No new targets to discover.",
            pluginfw.INFO,
        )
        return True

    # Deduplicate while preserving order
    unique_ips = list(dict.fromkeys(ip for ip in new_ips if ip))
    if not unique_ips:
        pluginfw.AddLog(
            "No valid targets after filtering.",
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
        f"Starting discovery for {_describe_targets(unique_ips)}: {unique_ips}",
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
