from typing import List

from netbrain.utils import nbjson
from netbrain.sysapi import datamodel
from netbrain.sysapi import pluginfw

from .api_server import ApiServer
from .discovery import discover_new_ips
from .dynamic_group import (
    store_group_mapping,
    upsert_dynamic_groups,
)

# Vendor parser. To support a different vendor, copy infoblox.py to
# <vendor>.py, adjust its functions, and change only this import line.
from .infoblox import (
    DYNAMIC_GROUP_RETURN_FIELDS,
    FUNC_NAME,
    IPV4_URL,
    NETWORK_URL,
    RETURN_FIELDS,
    SUBNET_URL,
    build_group_mapping,
    extract_ips,
)


# Per-request "purpose": what the API call is used for.
PURPOSE_DISCOVERY = "discovery"
PURPOSE_DYNAMIC_GROUP = "dynamic_group"

# For a discovery request, what kind of value drives the discovery.
DISCOVERY_BY_IP = "ip_address"
DISCOVERY_BY_NETWORK = "network"


# =========================================================
# Get Domain Name
# =========================================================
def get_domain_name() -> str:
    domain_details = datamodel.GetCurrentDomainInfo()
    return domain_details.get("domainDbName", "")


# =========================================================
# Small helpers
# =========================================================
def _as_list(value) -> List[str]:
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def _enumerate_all_subnets(api_server, request, test_limit=None) -> List[str]:
    """
    Enumerate every subnet CIDR from SUBNET_URL (overridable with
    "subnet_url"), collecting each record's "network" field.

    The enumeration call sends a minimal _return_fields=["network"]: this
    adapter returns a bare "null" when api_parm.query is empty, and asking for
    just "network" is harmless (every network object has it).
    """
    subnet_url = request.get("subnet_url") or SUBNET_URL
    pluginfw.AddLog(
        f"Enumerating subnets from {subnet_url}",
        pluginfw.INFO,
    )
    response = api_server.forward_request_to_fs(
        FUNC_NAME,
        {"url": subnet_url, "api_parm": {"query": {"_return_fields": ["network"]}}},
    )
    return extract_ips(
        response,
        {"ip_keys": ["network"]},
        test_limit=test_limit,
    )


def _fetch_and_collect(
    api_server, ipv4_url, query, request, test_limit, discovery_values
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
    discovery_values.extend(extract_ips(response, request, test_limit=test_limit))


# =========================================================
# Purpose 1: Discovery
# =========================================================
def _process_discovery(api_server, request, test_limit):
    """
    Resolve the values to feed NetBrain discovery for one discovery request.

    discovery_by="ip_address" (default):
      - specific "ip_address" given  -> discover exactly those IPs.
      - none given                   -> fetch every ipv4address from Infoblox
                                        and discover all of them.

    discovery_by="network":
      - specific "network" given     -> discover exactly those subnets.
      - none given                   -> enumerate every subnet from Infoblox
                                        and discover all of them.

    NetBrain discovery's "hostips" accepts both single IPs and subnet CIDRs,
    so subnets can be handed to discovery directly.

    Resolving the values and triggering discovery both live here: the Dynamic
    Group path never touches discovery.
    """
    discovery_by = (request.get("discovery_by") or DISCOVERY_BY_IP).strip().lower()
    discovery_values: List[str] = []

    # ---- Discover by whole subnet --------------------------------------
    if discovery_by == DISCOVERY_BY_NETWORK:
        subnets = _as_list(request.get("network"))
        if subnets:
            pluginfw.AddLog(
                f"Discovery by network: using {len(subnets)} specified "
                f"subnet(s).",
                pluginfw.INFO,
            )
        else:
            subnets = _enumerate_all_subnets(api_server, request, test_limit)
            pluginfw.AddLog(
                f"Discovery by network: no subnet specified; using all "
                f"{len(subnets)} subnet(s) from Infoblox.",
                pluginfw.INFO,
            )
        discovery_values.extend(subnets)

    # ---- Discover by IP address (specified) ----------------------------
    elif _as_list(request.get("ip_address")):
        ips = _as_list(request.get("ip_address"))
        pluginfw.AddLog(
            f"Discovery by ip_address: using {len(ips)} specified IP(s).",
            pluginfw.INFO,
        )
        discovery_values.extend(ips)

    # ---- Discover by IP address (none specified -> fetch all) ----------
    else:
        # The adapter rejects an empty query, so enumerate subnets first then
        # query each subnet for its addresses (the reference two-step flow).
        ipv4_url = request.get("api_url") or IPV4_URL
        return_fields = request.get("_return_fields") or RETURN_FIELDS

        subnets = _enumerate_all_subnets(api_server, request, test_limit)
        if subnets:
            pluginfw.AddLog(
                f"Discovery by ip_address: no IP specified; querying all "
                f"{len(subnets)} subnet(s) for addresses.",
                pluginfw.INFO,
            )
            for subnet in subnets:
                _fetch_and_collect(
                    api_server,
                    ipv4_url,
                    {"network": subnet, "_return_fields": return_fields},
                    request,
                    test_limit,
                    discovery_values,
                )
        else:
            pluginfw.AddLog(
                "Discovery by ip_address: no subnets resolved; nothing to "
                "query.",
                pluginfw.WARNING,
            )

    # ---- Trigger discovery for this request ----------------------------
    if discovery_values:
        pluginfw.AddLog(
            f"Triggering NetBrain discovery for {len(discovery_values)} "
            f"value(s).",
            pluginfw.INFO,
        )
        discover_new_ips(discovery_values)
    else:
        pluginfw.AddLog(
            "No IPs/subnets to discover for this request.",
            pluginfw.INFO,
        )


# =========================================================
# Purpose 2: Dynamic Group
# =========================================================
def _process_dynamic_group(api_server, request, test_limit):
    """
    Build Dynamic Groups from a /network (+extattrs) response.

    The user picks the grouping column via "group_by" (e.g. "Zone"); every
    record's "group_value_field" (default "network") is collected into the
    group named by that column's value. The resulting {name: [subnet]} mapping
    is persisted via the customer's API; creating/updating the Dynamic Group
    objects themselves is reserved until those endpoints exist.
    """
    group_by = request.get("group_by")
    if not group_by:
        pluginfw.AddLog(
            "Dynamic Group request missing 'group_by'; skipping.",
            pluginfw.WARNING,
        )
        return

    api_url = request.get("api_url") or NETWORK_URL
    return_fields = request.get("_return_fields") or DYNAMIC_GROUP_RETURN_FIELDS

    pluginfw.AddLog(
        f"Building Dynamic Groups by '{group_by}' from {api_url}",
        pluginfw.INFO,
    )
    response = api_server.forward_request_to_fs(
        FUNC_NAME,
        {"url": api_url, "api_parm": {"query": {"_return_fields": return_fields}}},
    )

    mapping = build_group_mapping(response, request, test_limit=test_limit)
    if not mapping:
        pluginfw.AddLog(
            "No Dynamic Group mapping produced; nothing to store.",
            pluginfw.WARNING,
        )
        return

    # Persist the name -> subnet-list mapping (customer DB), then upsert the
    # Dynamic Group objects (reserved until the upsert endpoint is available).
    store_group_mapping(group_by, mapping)
    upsert_dynamic_groups(mapping)


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
    # Process Requests by purpose
    # -------------------------
    # Each purpose owns its full flow: a discovery request resolves its values
    # AND triggers discovery; a dynamic_group request builds and persists its
    # mapping. The dynamic_group path never touches discovery.
    for request in api_requests:
        if not request.get("enable"):
            pluginfw.AddLog(
                f"Request purpose '{request.get('purpose')}' not enabled; "
                f"skipping.",
                pluginfw.INFO,
            )
            continue

        purpose = (request.get("purpose") or PURPOSE_DISCOVERY).strip().lower()

        if purpose == PURPOSE_DYNAMIC_GROUP:
            _process_dynamic_group(api_server, request, test_limit)
        elif purpose == PURPOSE_DISCOVERY:
            _process_discovery(api_server, request, test_limit)
        else:
            pluginfw.AddLog(
                f"Unknown request purpose '{purpose}'; skipping.",
                pluginfw.WARNING,
            )

    return True
