"""
Dynamic Group handling for the Infoblox integration.

A "dynamic group" request (purpose="dynamic_group") queries the Infoblox
/network endpoint with extattrs, then groups the returned subnets by a
user-chosen column (e.g. "Zone"). The result is a mapping:

    {"CORE": ["10.0.104.0/24", "10.0.110.0/24", ...], "EDGE": [...], ...}

This module is responsible for what happens to that mapping:

  1. store_group_mapping() -- persist the name -> subnet-list mapping by
     calling the customer's own Python API (their database of record).

  2. upsert_dynamic_groups() / get_dynamic_groups() -- create/update/read the
     Dynamic Groups themselves. The backing APIs do not exist yet; these are
     reserved entry points so main.py already calls the right seams. Fill in
     the request bodies once the upsert / get endpoints are available
     (likely just those two: an upsert and a get).

The grouping/parsing itself lives in the vendor file (infoblox.build_group_mapping)
so that supporting a new vendor only means editing that one file.
"""

from typing import Dict, List

from netbrain.sysapi import pluginfw


# =========================================================
# Persist the name -> subnet-list mapping (customer DB)
# =========================================================
def store_group_mapping(group_by: str, mapping: Dict[str, List[str]]) -> bool:
    """
    Persist the Dynamic Group mapping to the customer's own datastore.

    The customer exposes a Python API that writes the {group_name: [subnet]}
    mapping into their database. Wire that call in here.

    :param group_by: The column the mapping was grouped by (e.g. "Zone"),
                     passed through for context/labeling on the storage side.
    :param mapping:  {group_name: [subnet, ...]} produced by
                     infoblox.build_group_mapping().
    :return: True on success.
    """
    if not mapping:
        pluginfw.AddLog(
            "No Dynamic Group mapping to store.",
            pluginfw.INFO,
        )
        return True

    pluginfw.AddLog(
        f"Storing Dynamic Group mapping grouped by '{group_by}': "
        f"{len(mapping)} group(s) -> "
        f"{ {name: len(subnets) for name, subnets in mapping.items()} }",
        pluginfw.INFO,
    )

    # ---------------------------------------------------------------
    # TODO(customer-api): call the customer's Python API to write the
    # mapping into their database, e.g.:
    #
    #     import my_company_api
    #     my_company_api.save_dynamic_group_mapping(group_by, mapping)
    #
    # Until that API is wired in, we only log the mapping above so the rest
    # of the flow can be exercised end to end.
    # ---------------------------------------------------------------
    for name, subnets in mapping.items():
        pluginfw.AddLog(
            f"  Dynamic Group '{name}': {subnets}",
            pluginfw.INFO,
        )

    return True


# =========================================================
# Reserved: upsert Dynamic Groups (API not available yet)
# =========================================================
def upsert_dynamic_groups(mapping: Dict[str, List[str]]) -> bool:
    """
    Create or update Dynamic Groups from the mapping.

    RESERVED: the Infoblox/customer upsert endpoint is not available yet.
    When it lands, build one upsert call per group (name + member subnets)
    and forward it, mirroring how ApiServer.forward_request_to_fs is used
    elsewhere. For now this is a no-op placeholder so main.py already routes
    here.

    :param mapping: {group_name: [subnet, ...]}.
    :return: True (no-op) until the endpoint exists.
    """
    if not mapping:
        return True

    pluginfw.AddLog(
        f"[reserved] upsert_dynamic_groups: would upsert {len(mapping)} "
        f"Dynamic Group(s) once the upsert API is available.",
        pluginfw.INFO,
    )

    # ---------------------------------------------------------------
    # TODO(dynamic-group-api): implement once the upsert endpoint exists.
    #
    #   for name, subnets in mapping.items():
    #       body = {"name": name, "members": subnets}
    #       api_server.forward_request_to_fs("upsertDynamicGroup", {...})
    # ---------------------------------------------------------------
    return True


# =========================================================
# Reserved: get Dynamic Groups (API not available yet)
# =========================================================
def get_dynamic_groups(names: List[str] | None = None) -> Dict[str, List[str]]:
    """
    Read existing Dynamic Groups (optionally filtered by name).

    RESERVED: the get endpoint is not available yet. When it lands, forward a
    get request and normalize the response into {group_name: [subnet, ...]}.

    :param names: Optional list of group names to fetch; None = all.
    :return: {} (no-op) until the endpoint exists.
    """
    pluginfw.AddLog(
        "[reserved] get_dynamic_groups: returns nothing until the get API "
        "is available.",
        pluginfw.INFO,
    )

    # ---------------------------------------------------------------
    # TODO(dynamic-group-api): implement once the get endpoint exists.
    #
    #   response = api_server.forward_request_to_fs("getDynamicGroups", {...})
    #   return normalize_dynamic_groups(response)
    # ---------------------------------------------------------------
    return {}
