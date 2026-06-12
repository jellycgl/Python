"""
Vendor parsing logic for Infoblox.

This is the only vendor-specific file. To support a new vendor, copy this
script (e.g. to `cisco.py`), keep the same public names (FUNC_NAME and
extract_ips), and adjust the parsing functions to match that vendor's API
response. main.py stays unchanged except for the one import line.

The default parsing is config-driven and generic:
  - `ip_keys`       : which response keys hold an IP / subnet value to collect
  - `result_filter` : conditions a record must satisfy to be kept
Both support flat keys ("ip_address") and nested keys ("a.b.ip_address").
"""

import json
from typing import Any, List

from netbrain.sysapi import pluginfw


# Adapter function the plugin calls to send a single WAPI request. The plugin
# (main.py) plays the orchestration role: it calls getData repeatedly -- once
# to enumerate subnets, then once per subnet for ipv4address.
FUNC_NAME = "getData"

# Default WAPI endpoints (overridable per request via "subnet_url"/"api_url").
# SUBNET_URL enumerates every subnet; IPV4_URL returns the addresses within a
# subnet.
#
# NOTE: enumeration uses the "network" object, which a bare GET returns in
# full. "ipam:statistics" is NOT usable here -- it reports utilization for a
# single network and REQUIRES a network/network_view parameter, so a bare call
# returns null. Each "network" record still carries the CIDR in "network".
SUBNET_URL = "/wapi/v2.10/network"
IPV4_URL = "/wapi/v2.10/ipv4address"

# Endpoint used to build Dynamic Groups. Returns one record per network/subnet,
# each carrying its custom "extattrs" (Building/City/Zone/...). The CIDR is in
# "network". Overridable per request via "api_url".
NETWORK_URL = "/wapi/v2.7/network"

# Default fields requested when building Dynamic Groups. "extattrs" carries the
# user-selectable grouping columns (Zone, Building, City, ...); "network" is the
# subnet value collected into each group.
DYNAMIC_GROUP_RETURN_FIELDS = [
    "network",
    "network_view",
    "comment",
    "extattrs",
]

# Fields requested back from /wapi/v2.10/ipv4address. Mirrors the reference
# adapter script exactly; sent as api_parm.query._return_fields on that call.
RETURN_FIELDS = [
    "ip_address",
    "names",
    "mac_address",
    "dhcp_client_identifier",
    "status",
    "types",
    "discover_now_status",
    "usage",
    "lease_state",
    "username",
    "discovered_data",
    "network",
    "fingerprint",
]


# =========================================================
# Response normalization
# =========================================================
def normalize_records(response: Any) -> List[dict]:
    """
    Normalize the adapter response into a flat list of record dicts.

    The value may arrive as a list, a JSON string, or a wrapper dict
    ({"result"/"data"/"items": [...]}).
    """
    if not response:
        return []

    try:
        parsed = (
            response
            if isinstance(response, (list, dict))
            else json.loads(response)
        )
    except Exception as exc:
        pluginfw.AddLog(
            f"Invalid API response format: {exc}",
            pluginfw.ERROR,
        )
        return []

    # A literal JSON "null" (or empty body) just means "no results" -- not an
    # error. Treat it as an empty record set.
    if parsed is None:
        pluginfw.AddLog(
            "API returned null (no results for this query).",
            pluginfw.INFO,
        )
        return []

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):
        records = (
            parsed.get("result")
            or parsed.get("data")
            or parsed.get("items")
            or []
        )
        if isinstance(records, list):
            return records
        pluginfw.AddLog(
            f"Unexpected records container type: {type(records)}",
            pluginfw.ERROR,
        )
        return []

    pluginfw.AddLog(
        f"Unexpected API response type: {type(parsed)}",
        pluginfw.ERROR,
    )
    return []


# =========================================================
# Nested-key access
# =========================================================
def get_nested_value(record: Any, key: str) -> Any:
    """
    Read a value from a record by a flat or dotted/nested key.

    Examples:
        get_nested_value(rec, "ip_address")
        get_nested_value(rec, "discovered_data.os")
        get_nested_value(rec, "a.b.c.network")

    Returns None if any level along the path is missing or not a dict.
    """
    if record is None or not key:
        return None

    current = record
    for part in str(key).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


# =========================================================
# Result filtering
# =========================================================
def _scalar_equal(actual: Any, expected: Any) -> bool:
    # Case-insensitive compare for strings (e.g. status "USED").
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().lower() == expected.strip().lower()
    return actual == expected


def _value_matches(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    # Allow expected to be a list -> match if actual equals any of them.
    if isinstance(expected, (list, tuple, set)):
        return any(_scalar_equal(actual, item) for item in expected)
    return _scalar_equal(actual, expected)


def match_filters(record: dict, result_filter: List[dict]) -> bool:
    """
    Return True if `record` satisfies every condition in `result_filter`.

    result_filter is a list of condition dicts; all conditions (and all
    key/value pairs within each) must match (logical AND). Keys may be
    flat or nested. Example: [{"status": "USED"}, {"a.b.type": "HOST"}]
    """
    if not result_filter:
        return True

    for condition in result_filter:
        if not isinstance(condition, dict):
            continue
        for key, expected in condition.items():
            actual = get_nested_value(record, key)
            if not _value_matches(actual, expected):
                return False
    return True


# =========================================================
# Public entry: extract IP / subnet values for discovery
# =========================================================
def extract_ips(
    response: Any,
    request: dict,
    test_limit: int | None = None,
) -> List[str]:
    """
    Parse one API response into a list of IP / subnet strings to discover.

    :param response: Raw adapter response for this request.
    :param request:  The apiRequest dict; reads "ip_keys" and "result_filter".
    :param test_limit: Optional cap on the number of records processed.
    """
    records = normalize_records(response)
    if not records:
        pluginfw.AddLog(
            "No records returned from API.",
            pluginfw.WARNING,
        )
        return []

    ip_keys = request.get("ip_keys") or ["ip_address"]
    result_filter = request.get("result_filter") or []

    if test_limit and isinstance(test_limit, int):
        records = records[:test_limit]
        pluginfw.AddLog(
            f"Test mode enabled. Processing first {test_limit} records only.",
            pluginfw.INFO,
        )

    values: List[str] = []
    matched = 0

    for record in records:
        if not isinstance(record, dict):
            continue
        if not match_filters(record, result_filter):
            continue
        matched += 1
        for key in ip_keys:
            value = get_nested_value(record, key)
            if value:
                values.append(str(value).strip())

    pluginfw.AddLog(
        f"Matched {matched}/{len(records)} record(s); extracted "
        f"{len(values)} value(s) for keys {ip_keys}.",
        pluginfw.INFO,
    )

    return values


# =========================================================
# Dynamic Group: read a column value (top-level or extattrs)
# =========================================================
def read_attr(record: dict, field: str) -> Any:
    """
    Read one column value from a network record for Dynamic Group building.

    Infoblox returns top-level fields (e.g. "network", "network_view") flat,
    but custom attributes live under extattrs.<name>.value, for example:

        {"extattrs": {"Zone": {"value": "CORE"}}}

    So `field="network"` reads the CIDR directly, while `field="Zone"`
    resolves to extattrs.Zone.value. A dotted path is honored as-is.
    Returns None when the field is absent.
    """
    if not field:
        return None

    direct = get_nested_value(record, field)
    if isinstance(direct, dict):
        # The field pointed straight at an extattr object {"value": ...}.
        if "value" in direct:
            return direct.get("value")
    elif direct is not None:
        return direct

    # Fall back to the Infoblox custom-attribute location.
    return get_nested_value(record, f"extattrs.{field}.value")


# =========================================================
# Dynamic Group: build {group_name -> [subnet, ...]} mapping
# =========================================================
def build_group_mapping(
    response: Any,
    request: dict,
    test_limit: int | None = None,
) -> dict:
    """
    Parse a /network (+extattrs) response into a Dynamic Group mapping.

    Groups records by the column named in `request["group_by"]` (e.g. "Zone")
    and collects the value of `request["group_value_field"]` (default
    "network") into each group. For the table in the spec, group_by="Zone"
    yields {"CORE": ["10.0.104.0/24", ...], ...} -- every network whose Zone is
    CORE lands in the "CORE" group.

    :param response:   Raw adapter response for this request.
    :param request:    The apiRequest dict; reads "group_by",
                       "group_value_field" and optional "result_filter".
    :param test_limit: Optional cap on the number of records processed.
    :return: Ordered dict {group_name: [subnet, ...]} with de-duplicated values.
    """
    records = normalize_records(response)
    if not records:
        pluginfw.AddLog(
            "No records returned from API for Dynamic Group build.",
            pluginfw.WARNING,
        )
        return {}

    group_by = request.get("group_by")
    if not group_by:
        pluginfw.AddLog(
            "Dynamic Group request missing 'group_by'; cannot build mapping.",
            pluginfw.ERROR,
        )
        return {}

    value_field = request.get("group_value_field") or "network"
    result_filter = request.get("result_filter") or []

    if test_limit and isinstance(test_limit, int):
        records = records[:test_limit]
        pluginfw.AddLog(
            f"Test mode enabled. Processing first {test_limit} records only.",
            pluginfw.INFO,
        )

    mapping: dict = {}
    matched = 0

    for record in records:
        if not isinstance(record, dict):
            continue
        if not match_filters(record, result_filter):
            continue

        group_name = read_attr(record, group_by)
        value = read_attr(record, value_field)
        if group_name is None or value is None:
            continue

        group_name = str(group_name).strip()
        value = str(value).strip()
        if not group_name or not value:
            continue

        matched += 1
        members = mapping.setdefault(group_name, [])
        if value not in members:
            members.append(value)

    total_values = sum(len(v) for v in mapping.values())
    pluginfw.AddLog(
        f"Built {len(mapping)} Dynamic Group(s) from {matched}/{len(records)} "
        f"record(s) by '{group_by}' -> '{value_field}' "
        f"({total_values} value(s)).",
        pluginfw.INFO,
    )

    return mapping
