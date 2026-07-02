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
     NetBrain Dynamic Device Groups themselves via the data-model API
     (datamodel.AddOrUpdateDeviceGroup / datamodel.GetDeviceGroup). Each group
     becomes a dynamic device group whose filter selects every device whose
     Mgmt IP falls inside one of the group's subnets.

The grouping/parsing itself lives in the vendor file (infoblox.build_group_mapping)
so that supporting a new vendor only means editing that one file.
"""

from typing import Dict, List

from netbrain.sysapi import datamodel, pluginfw


# =========================================================
# Dynamic-search filter defaults
# =========================================================
# These are only fallbacks. How a grouped value maps to a device-group filter
# (which schema key, which operator, which parent folder) is configured in the
# Input request -- see main.py, which reads "device_group_schema",
# "device_group_operator" and "device_group_parent" and forwards them here.

# Default schema key the engine matches against. A subnet in CIDR form
# (e.g. "10.0.104.0/24") combined with the Match operator selects every device
# whose Mgmt IP falls inside that subnet.
DEFAULT_SCHEMA = "mgmtIP"

# Default DySearchOperator.Match -- "Matches" (regex/wildcard/CIDR). See the
# device group dynamic-search variable reference for the full operator set.
DEFAULT_OPERATOR = 0

# Default parent folder the per-group Dynamic Groups are created under.
DEFAULT_PARENT_PATH = "Shared Device Groups"


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
# Filter helpers
# =========================================================
def _column_letter(index: int) -> str:
    """
    Map a 0-based condition index to its Excel-style letter (0->A, 25->Z,
    26->AA, ...). Filter.expression references each condition positionally by
    these letters, in order A, B, C....
    """
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _build_condition(
    subnets: List[str],
    schema: str = DEFAULT_SCHEMA,
    operator: int = DEFAULT_OPERATOR,
) -> dict:
    """
    Build a dynamic-search condition object that selects any device whose
    `schema` field matches one of the given values.

    Each value becomes one condition (schema + operator); the conditions are
    OR-combined in Filter.expression ("A or B or C ...").

    :param subnets:  match values, e.g. CIDRs ["10.0.104.0/24", ...].
    :param schema:   schema key the engine matches against (e.g. "mgmtIP").
    :param operator: DySearchOperator value (e.g. 0 = Match).
    :return: condition dict accepted by datamodel.AddOrUpdateDeviceGroup.
    """
    conditions = []
    letters = []
    for i, subnet in enumerate(subnets):
        conditions.append(
            {
                "schema": schema,
                "operator": operator,
                "expression": subnet,
            }
        )
        letters.append(_column_letter(i))

    return {
        "Filter": {
            "expression": " or ".join(letters),
            "conditions": conditions,
        },
        "RangeOption": 0,
        "DeviceGroupRange": [],
        "SiteRange": [],
    }


def _extract_subnets(
    device_group: dict,
    schema: str = DEFAULT_SCHEMA,
) -> List[str]:
    """
    Pull the match-value list back out of a device group object returned by
    datamodel.GetDeviceGroup, i.e. the inverse of _build_condition.

    Walks the (possibly nested / differently-cased) object for a Filter with
    `conditions`, and returns the `expression` of each condition whose schema
    equals `schema`. Defensive about shape so we don't break if the stored
    object differs.
    """
    subnets: List[str] = []
    if not isinstance(device_group, dict):
        return subnets

    # Locate the conditions list regardless of casing / nesting under Filter.
    conditions = None
    for key in ("Filter", "filter"):
        filt = device_group.get(key)
        if isinstance(filt, dict):
            conditions = filt.get("conditions") or filt.get("Conditions")
            break
    if conditions is None:
        conditions = device_group.get("conditions") or device_group.get("Conditions")

    if not isinstance(conditions, list):
        return subnets

    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        cond_schema = cond.get("schema") or cond.get("Schema")
        if cond_schema != schema:
            continue
        expression = cond.get("expression")
        if expression is None:
            expression = cond.get("Expression")
        if expression:
            value = str(expression).strip()
            if value and value not in subnets:
                subnets.append(value)

    return subnets


def _group_path(parent_path: str, name: str) -> str:
    """Full device-group path: '<parent>/<name>'."""
    return f"{parent_path.rstrip('/')}/{name}"


# =========================================================
# Upsert Dynamic Groups (datamodel.AddOrUpdateDeviceGroup)
# =========================================================
def upsert_dynamic_groups(
    mapping: Dict[str, List[str]],
    parent_path: str = DEFAULT_PARENT_PATH,
    schema: str = DEFAULT_SCHEMA,
    operator: int = DEFAULT_OPERATOR,
    dry_run: bool = False,
) -> bool:
    """
    Create or update NetBrain Dynamic Device Groups from the mapping.

    For each {name: [subnet, ...]} entry a dynamic device group is created (or
    updated) at "<parent_path>/<name>" whose filter selects every device whose
    `schema` field matches one of the subnets.

    :param mapping:     {group_name: [subnet, ...]}.
    :param parent_path: Parent folder for the groups (default
                        "Shared Device Groups").
    :param schema:      schema key to match against (default "mgmtIP").
    :param operator:    DySearchOperator value (default 0 = Match).
    :param dry_run:     When True, log the intended call instead of executing it.
    :return: True if every group was upserted successfully, False otherwise.
    """
    if not mapping:
        return True

    pluginfw.AddLog(
        f"{'[DRY RUN] ' if dry_run else ''}Upserting {len(mapping)} "
        f"Dynamic Device Group(s) under '{parent_path}'.",
        pluginfw.INFO,
    )

    all_ok = True
    for name, subnets in mapping.items():
        if not subnets:
            pluginfw.AddLog(
                f"Dynamic Group '{name}' has no subnets; skipping.",
                pluginfw.WARNING,
            )
            continue

        path = _group_path(parent_path, name)
        condition = _build_condition(subnets, schema, operator)

        if dry_run:
            pluginfw.AddLog(
                f"[DRY RUN] Would call AddOrUpdateDeviceGroup("
                f"path={path!r}, name={name!r}, "
                f"filter={condition['Filter']['expression']!r}, "
                f"subnets={subnets})",
                pluginfw.INFO,
            )
            continue

        ok = datamodel.AddOrUpdateDeviceGroup(path, condition, name)
        if ok:
            pluginfw.AddLog(
                f"Upserted Dynamic Group '{path}' with {len(subnets)} "
                f"subnet condition(s).",
                pluginfw.INFO,
            )
        else:
            all_ok = False
            pluginfw.AddLog(
                f"Failed to upsert Dynamic Group '{path}': "
                f"{datamodel.GetPyLastError()}",
                pluginfw.ERROR,
            )

    return all_ok


# =========================================================
# Get Dynamic Groups (datamodel.GetDeviceGroup)
# =========================================================
def get_dynamic_groups(
    names: List[str],
    parent_path: str = DEFAULT_PARENT_PATH,
    schema: str = DEFAULT_SCHEMA,
) -> Dict[str, List[str]]:
    """
    Read existing Dynamic Device Groups and normalize them back into the
    {group_name: [subnet, ...]} mapping shape (inverse of upsert).

    :param names:       Group names to fetch (each read at
                        "<parent_path>/<name>").
    :param parent_path: Parent folder for the groups (default
                        "Shared Device Groups").
    :param schema:      schema key whose condition values to extract (default
                        "mgmtIP"); must match what upsert used.
    :return: {group_name: [subnet, ...]} for the groups that exist.
    """
    result: Dict[str, List[str]] = {}
    if not names:
        return result

    for name in names:
        path = _group_path(parent_path, name)
        device_group = datamodel.GetDeviceGroup(path)
        if not device_group:
            pluginfw.AddLog(
                f"Dynamic Group '{path}' not found: "
                f"{datamodel.GetPyLastError()}",
                pluginfw.WARNING,
            )
            continue

        result[name] = _extract_subnets(device_group, schema)

    return result
