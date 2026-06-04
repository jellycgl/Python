from typing import List

from netbrain.utils import nbjson
from netbrain.sysapi import datamodel
from netbrain.sysapi import pluginfw

from .api_server import ApiServer
from .discovery import discover_new_ips

# Vendor parser. To support a different vendor, copy infoblox.py to
# <vendor>.py, adjust its functions, and change only this import line.
from .infoblox import (
    FUNC_NAME,
    IPV4_URL,
    RETURN_FIELDS,
    SUBNET_URL,
    extract_ips,
)


# =========================================================
# Get Domain Name
# =========================================================
def get_domain_name() -> str:
    domain_details = datamodel.GetCurrentDomainInfo()
    return domain_details.get("domainDbName", "")


# =========================================================
# Resolve the subnets to query (explicit, or auto-enumerate)
# =========================================================
def _as_list(value) -> List[str]:
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def _resolve_subnets(api_server, request, test_limit=None) -> List[str]:
    """
    Determine the subnets whose ipv4address records we will fetch.

    - If the request gives "network" (list or string), use exactly those --
      we only query the specified subnet(s).
    - Otherwise enumerate every subnet via SUBNET_URL (ipam:statistics,
      overridable with "subnet_url") and collect each record's "network"
      CIDR -- mirroring the reference adapter flow.

    The enumeration call sends NO _return_fields: ipam:statistics has its own
    schema (the rich ipv4address field set is invalid there), and the default
    fields already include "network".
    """
    explicit = _as_list(request.get("network"))
    if explicit:
        return explicit

    subnet_url = request.get("subnet_url") or SUBNET_URL
    pluginfw.AddLog(
        f"No network specified; enumerating subnets from {subnet_url}",
        pluginfw.INFO,
    )
    # Send a non-empty query: this adapter returns a bare "null" when
    # api_parm.query is empty. Asking only for the "network" field is harmless
    # (every network object has it) and is what we extract below.
    response = api_server.forward_request_to_fs(
        FUNC_NAME,
        {"url": subnet_url, "api_parm": {"query": {"_return_fields": ["network"]}}},
    )
    # ipam:statistics records carry the subnet CIDR in "network".
    return extract_ips(
        response,
        {"ip_keys": ["network"]},
        test_limit=test_limit,
    )


def _fetch_and_collect(
    api_server, ipv4_url, query, request, test_limit, discovery_ips
):
    """Call getData for one query and append the extracted IPs."""
    pluginfw.AddLog(
        f"Querying {ipv4_url} query={query}",
        pluginfw.INFO,
    )
    # Mirror the reference getData(rtn_params) call: url + api_parm.query.
    response = api_server.forward_request_to_fs(
        FUNC_NAME,
        {"url": ipv4_url, "api_parm": {"query": query}},
    )
    discovery_ips.extend(extract_ips(response, request, test_limit=test_limit))


# =========================================================
# Plugin Entry Point
# =========================================================
def run(input_data: str) -> bool:
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
    discovery_ips: List[str] = []

    for request in api_requests:

        # Endpoint that returns the addresses (overridable; defaults to
        # ipv4address). _return_fields defaults to the full ipv4address set.
        ipv4_url = request.get("api_url") or IPV4_URL
        return_fields = request.get("_return_fields") or RETURN_FIELDS

        # If specific IPs are given, query those directly -- no subnet step.
        ip_addresses = _as_list(request.get("ip_address"))
        if ip_addresses:
            for ip in ip_addresses:
                _fetch_and_collect(
                    api_server,
                    ipv4_url,
                    {"ip_address": ip, "_return_fields": return_fields},
                    request,
                    test_limit,
                    discovery_ips,
                )
            continue

        # Otherwise: query by subnet. Use the network(s) given in the input,
        # or enumerate every subnet first (the reference two-step flow).
        subnets = _resolve_subnets(api_server, request, test_limit)
        if not subnets:
            pluginfw.AddLog(
                "No subnets resolved for request; nothing to query.",
                pluginfw.WARNING,
            )
            continue

        pluginfw.AddLog(
            f"Querying {len(subnets)} subnet(s) for ipv4address records.",
            pluginfw.INFO,
        )
        for subnet in subnets:
            _fetch_and_collect(
                api_server,
                ipv4_url,
                {"network": subnet, "_return_fields": return_fields},
                request,
                test_limit,
                discovery_ips,
            )

    # -------------------------
    # Trigger Discovery
    # -------------------------
    if discovery_ips:
        pluginfw.AddLog(
            f"Triggering NetBrain discovery for {len(discovery_ips)} value(s).",
            pluginfw.INFO,
        )
        discover_new_ips(discovery_ips)
    else:
        pluginfw.AddLog(
            "No IPs to discover.",
            pluginfw.INFO,
        )

    return True
