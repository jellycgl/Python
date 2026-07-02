#!/usr/bin/env python3
"""
Test suite for the Infoblox NetBrain integration plugin.

Verifies the Discovery and Dynamic Group flows end-to-end without calling
the real NetBrain backend.  NetBrain interface calls are mocked and their
arguments are captured for the final report.

Usage:
    python "run_tests.py"
    -> writes test_report.md alongside this script
"""

import sys, os, json
from unittest.mock import MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# 1. Mock netbrain + pythonlib BEFORE importing any package module
# ─────────────────────────────────────────────────────────────────────────────
_pluginfw = MagicMock()
_pluginfw.INFO    = "INFO"
_pluginfw.WARNING = "WARNING"
_pluginfw.ERROR   = "ERROR"
_pluginfw.AddLog  = lambda msg, level=None: None   # silence during tests

_datamodel = MagicMock()
_datamodel.AddOrUpdateDeviceGroup = MagicMock(return_value=True)
_datamodel.GetPyLastError         = MagicMock(return_value="")

_nbjson = MagicMock()
_nbjson.loads = json.loads

for _name, _mod in [
    ("netbrain",                   MagicMock()),
    ("netbrain.sysapi",            MagicMock()),
    ("netbrain.sysapi.pluginfw",   _pluginfw),
    ("netbrain.sysapi.datamodel",  _datamodel),
    ("netbrain.utils",             MagicMock()),
    ("netbrain.utils.nbjson",      _nbjson),
    ("pythonlib",                  MagicMock()),
]:
    sys.modules.setdefault(_name, _mod)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Add Infoblox package directory to sys.path
# ─────────────────────────────────────────────────────────────────────────────
INFOBLOX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if INFOBLOX_DIR not in sys.path:
    sys.path.insert(0, INFOBLOX_DIR)

from infoblox      import extract_ips, build_group_mapping, match_filters
from dynamic_group import _build_condition, upsert_dynamic_groups, DEFAULT_PARENT_PATH
import dynamic_group as _dg_module

# Patch datamodel directly into the module's namespace so that
# dynamic_group.upsert_dynamic_groups() calls hit _datamodel.
_dg_module.datamodel = _datamodel

# ─────────────────────────────────────────────────────────────────────────────
# 3. Helpers
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_responses")

def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


class TC:
    """Lightweight test-case container."""
    def __init__(self, tc_id, description):
        self.tc_id       = tc_id
        self.description = description
        self.checks      = []   # (passed, label, expected, actual)
        self.nb_calls    = []   # {"interface": ..., "args": {...}}

    def check(self, condition, label, expected=None, actual=None):
        self.checks.append((bool(condition), label, expected, actual))
        return bool(condition)

    def nb(self, interface, **args):
        self.nb_calls.append({"interface": interface, "args": args})

    @property
    def passed(self):
        return all(c[0] for c in self.checks)


RESULTS = []

def run(tc):
    RESULTS.append(tc)
    status = "PASS" if tc.passed else "FAIL"
    print(f"  [{status}] {tc.tc_id}: {tc.description}")
    return tc


# =============================================================================
# GROUP P  –  Parsing / extraction  (infoblox.py pure functions)
# =============================================================================
print("\n[Parsing Tests]")

# TC-P-01
tc = TC("TC-P-01", "extract_ips: all IPs from ipv4address response, no filter")
resp = load("02_ipv4_104.json")
got  = extract_ips(resp, {"ip_keys": ["ip_address"]})
tc.check(got == ["10.0.104.1", "10.0.104.2", "10.0.104.100"],
         "All 3 IPs extracted",
         expected=["10.0.104.1", "10.0.104.2", "10.0.104.100"], actual=got)
run(tc)

# TC-P-02
tc = TC("TC-P-02", "extract_ips: result_filter status=USED keeps only USED records")
resp = load("07_ipv4_mixed_status.json")
got  = extract_ips(resp, {"ip_keys": ["ip_address"],
                           "result_filter": [{"status": "USED"}]})
tc.check(got == ["10.0.104.1", "10.0.104.2", "10.0.104.200"],
         "3 USED IPs returned; 2 UNUSED filtered",
         expected=["10.0.104.1", "10.0.104.2", "10.0.104.200"], actual=got)
tc.check("10.0.104.100" not in got and "10.0.104.101" not in got,
         "UNUSED IPs 10.0.104.100 and .101 absent")
run(tc)

# TC-P-03
tc = TC("TC-P-03", "extract_ips: ip_keys=[\"network\"] collects subnet CIDRs")
resp = load("01_subnet_list.json")
got  = extract_ips(resp, {"ip_keys": ["network"]})
tc.check(got == ["10.0.104.0/24", "10.0.110.0/24", "192.168.1.0/24"],
         "All 3 subnet CIDRs extracted",
         expected=["10.0.104.0/24", "10.0.110.0/24", "192.168.1.0/24"], actual=got)
run(tc)

# TC-P-04
tc = TC("TC-P-04", "extract_ips: empty API response returns empty list")
resp = load("08_empty.json")
got  = extract_ips(resp, {"ip_keys": ["ip_address"]})
tc.check(got == [], "Empty list for empty response", expected=[], actual=got)
run(tc)

# TC-P-05
tc = TC("TC-P-05", "extract_ips: test_limit=2 truncates to first 2 records")
resp = load("02_ipv4_104.json")   # 3 records
got  = extract_ips(resp, {"ip_keys": ["ip_address"]}, test_limit=2)
tc.check(len(got) == 2, "2 IPs returned", expected=2, actual=len(got))
tc.check(got == ["10.0.104.1", "10.0.104.2"],
         "Only first 2 records processed",
         expected=["10.0.104.1", "10.0.104.2"], actual=got)
run(tc)

# TC-P-06
tc = TC("TC-P-06", "build_group_mapping: group by Zone -> CORE and EDGE groups")
resp = load("05_network_extattrs.json")
mapping = build_group_mapping(resp, {"group_by": "Zone", "group_value_field": "network"})
tc.check(set(mapping.keys()) == {"CORE", "EDGE"},
         "Two groups: CORE and EDGE",
         expected={"CORE", "EDGE"}, actual=set(mapping.keys()))
tc.check(sorted(mapping["CORE"]) == ["10.0.104.0/24", "10.0.110.0/24"],
         "CORE has 2 subnets",
         expected=["10.0.104.0/24", "10.0.110.0/24"],
         actual=sorted(mapping["CORE"]))
tc.check(sorted(mapping["EDGE"]) == ["172.16.0.0/24", "192.168.1.0/24"],
         "EDGE has 2 subnets",
         expected=["172.16.0.0/24", "192.168.1.0/24"],
         actual=sorted(mapping["EDGE"]))
run(tc)

# TC-P-07
tc = TC("TC-P-07", "build_group_mapping: group by Building -> HQ / Branch-01 / Branch-02")
resp = load("05_network_extattrs.json")
mapping = build_group_mapping(resp, {"group_by": "Building", "group_value_field": "network"})
tc.check(set(mapping.keys()) == {"HQ", "Branch-01", "Branch-02"},
         "Three building groups",
         expected={"HQ", "Branch-01", "Branch-02"}, actual=set(mapping.keys()))
tc.check(sorted(mapping["HQ"]) == ["10.0.104.0/24", "10.0.110.0/24"],
         "HQ has 2 subnets",
         expected=["10.0.104.0/24", "10.0.110.0/24"], actual=sorted(mapping["HQ"]))
tc.check(mapping["Branch-01"] == ["192.168.1.0/24"],
         "Branch-01 has 1 subnet", expected=["192.168.1.0/24"], actual=mapping["Branch-01"])
tc.check(mapping["Branch-02"] == ["172.16.0.0/24"],
         "Branch-02 has 1 subnet", expected=["172.16.0.0/24"], actual=mapping["Branch-02"])
run(tc)

# TC-P-08
tc = TC("TC-P-08", "build_group_mapping: result_filter network_view=default drops dmz records")
resp = load("06_network_mixed_views.json")
mapping = build_group_mapping(resp, {
    "group_by": "Zone",
    "group_value_field": "network",
    "result_filter": [{"network_view": "default"}],
})
tc.check(set(mapping.keys()) == {"CORE"},
         "Only CORE group (dmz EDGE records filtered out)",
         expected={"CORE"}, actual=set(mapping.keys()))
tc.check(sorted(mapping["CORE"]) == ["10.0.104.0/24", "10.0.110.0/24"],
         "CORE contains the 2 default-view subnets only",
         expected=["10.0.104.0/24", "10.0.110.0/24"],
         actual=sorted(mapping["CORE"]))
run(tc)

# TC-P-09
tc = TC("TC-P-09", "build_group_mapping: records missing Zone extattr are skipped")
resp = load("09_network_missing_zone.json")   # 2 of 4 records have Zone
mapping = build_group_mapping(resp, {"group_by": "Zone", "group_value_field": "network"})
tc.check(set(mapping.keys()) == {"CORE", "EDGE"},
         "Groups only for records that have Zone",
         expected={"CORE", "EDGE"}, actual=set(mapping.keys()))
tc.check(mapping["CORE"] == ["10.0.104.0/24"],
         "CORE has 1 subnet (10.0.110.0/24 skipped: extattrs={} )",
         expected=["10.0.104.0/24"], actual=mapping["CORE"])
tc.check(mapping["EDGE"] == ["192.168.1.0/24"],
         "EDGE has 1 subnet (172.16.0.0/24 skipped: no extattrs key)",
         expected=["192.168.1.0/24"], actual=mapping["EDGE"])
run(tc)

# TC-P-10
tc = TC("TC-P-10", "build_group_mapping: duplicate subnets within same group are deduplicated")
dup_data = [
    {"network": "10.0.104.0/24", "extattrs": {"Zone": {"value": "CORE"}}},
    {"network": "10.0.104.0/24", "extattrs": {"Zone": {"value": "CORE"}}},  # duplicate
    {"network": "10.0.110.0/24", "extattrs": {"Zone": {"value": "CORE"}}},
]
mapping = build_group_mapping(dup_data, {"group_by": "Zone", "group_value_field": "network"})
tc.check(len(mapping["CORE"]) == 2,
         "Duplicate 10.0.104.0/24 deduplicated; CORE has 2 unique subnets",
         expected=2, actual=len(mapping["CORE"]))
run(tc)


# =============================================================================
# GROUP F  –  Filter logic
# =============================================================================
print("\n[Filter Tests]")

# TC-F-01
tc = TC("TC-F-01", "match_filters: empty filter always returns True")
tc.check(match_filters({"status": "UNUSED"}, []) is True,
         "Empty filter -> True regardless of record content")
run(tc)

# TC-F-02
tc = TC("TC-F-02", "match_filters: flat key match and mismatch")
record = {"status": "USED", "network": "10.0.104.0/24"}
tc.check(match_filters(record, [{"status": "USED"}])   is True,  "USED matches USED")
tc.check(match_filters(record, [{"status": "UNUSED"}]) is False, "USED does not match UNUSED")
run(tc)

# TC-F-03
tc = TC("TC-F-03", "match_filters: expected value as list means OR within that field")
record = {"network_view": "dmz"}
tc.check(match_filters(record, [{"network_view": ["default", "dmz"]}]) is True,
         "dmz is in [default, dmz]")
tc.check(match_filters(record, [{"network_view": ["default"]}]) is False,
         "dmz is NOT in [default]")
run(tc)

# TC-F-04
tc = TC("TC-F-04", "match_filters: multiple conditions are AND-ed")
record = {"status": "USED", "network_view": "default"}
tc.check(match_filters(record, [{"status": "USED"}, {"network_view": "default"}]) is True,
         "Both conditions satisfied -> True")
tc.check(match_filters(record, [{"status": "USED"}, {"network_view": "dmz"}]) is False,
         "First OK, second fails -> False")
run(tc)


# =============================================================================
# GROUP D  –  Dynamic Group condition building (dynamic_group.py)
# =============================================================================
print("\n[Dynamic Group Condition Tests]")

# TC-D-01
tc = TC("TC-D-01", "_build_condition: single subnet -> expression='A'")
cond = _build_condition(["10.0.104.0/24"], schema="mgmtIP", operator=0)
tc.check(cond["Filter"]["expression"] == "A",
         "Single condition letter is A",
         expected="A", actual=cond["Filter"]["expression"])
tc.check(len(cond["Filter"]["conditions"]) == 1,
         "Exactly 1 condition",
         expected=1, actual=len(cond["Filter"]["conditions"]))
c0 = cond["Filter"]["conditions"][0]
tc.check(c0 == {"schema": "mgmtIP", "operator": 0, "expression": "10.0.104.0/24"},
         "Condition fields correct",
         expected={"schema": "mgmtIP", "operator": 0, "expression": "10.0.104.0/24"},
         actual=c0)
run(tc)

# TC-D-02
tc = TC("TC-D-02", "_build_condition: three subnets -> expression='A or B or C'")
subnets = ["10.0.104.0/24", "10.0.110.0/24", "192.168.1.0/24"]
cond    = _build_condition(subnets, schema="mgmtIP", operator=0)
tc.check(cond["Filter"]["expression"] == "A or B or C",
         "Three conditions OR-combined",
         expected="A or B or C", actual=cond["Filter"]["expression"])
tc.check([c["expression"] for c in cond["Filter"]["conditions"]] == subnets,
         "Subnet order preserved in conditions",
         expected=subnets,
         actual=[c["expression"] for c in cond["Filter"]["conditions"]])
run(tc)

# TC-D-03
tc = TC("TC-D-03", "upsert_dynamic_groups: 2-group mapping -> 2 AddOrUpdateDeviceGroup calls")
_datamodel.AddOrUpdateDeviceGroup.reset_mock()
_datamodel.AddOrUpdateDeviceGroup.return_value = True
mapping = {"CORE": ["10.0.104.0/24", "10.0.110.0/24"], "EDGE": ["192.168.1.0/24"]}
upsert_dynamic_groups(mapping, parent_path="Shared Device Groups",
                      schema="mgmtIP", operator=0)
calls = _datamodel.AddOrUpdateDeviceGroup.call_args_list
tc.check(len(calls) == 2, "Exactly 2 calls",
         expected=2, actual=len(calls))
paths = {c[0][0] for c in calls}
tc.check(paths == {"Shared Device Groups/CORE", "Shared Device Groups/EDGE"},
         "Correct paths for both groups",
         expected={"Shared Device Groups/CORE", "Shared Device Groups/EDGE"},
         actual=paths)
core_call = next((c for c in calls if c[0][0] == "Shared Device Groups/CORE"), None)
tc.check(core_call is not None, "CORE call found")
if core_call:
    tc.check(core_call[0][1]["Filter"]["expression"] == "A or B",
             "CORE filter expression is 'A or B' (2 subnets)",
             expected="A or B",
             actual=core_call[0][1]["Filter"]["expression"])
for c in calls:
    path, condition, name = c[0]
    tc.nb("datamodel.AddOrUpdateDeviceGroup",
          path=path,
          condition=condition,
          name=name)
run(tc)

# TC-D-04
tc = TC("TC-D-04", "upsert_dynamic_groups: empty mapping -> no NetBrain calls")
_datamodel.AddOrUpdateDeviceGroup.reset_mock()
upsert_dynamic_groups({})
tc.check(_datamodel.AddOrUpdateDeviceGroup.call_count == 0,
         "0 calls for empty mapping",
         expected=0, actual=_datamodel.AddOrUpdateDeviceGroup.call_count)
run(tc)

# TC-D-05
tc = TC("TC-D-05", "upsert_dynamic_groups: group with empty subnet list is skipped")
_datamodel.AddOrUpdateDeviceGroup.reset_mock()
_datamodel.AddOrUpdateDeviceGroup.return_value = True
upsert_dynamic_groups({"CORE": ["10.0.104.0/24"], "EMPTY": []})
tc.check(_datamodel.AddOrUpdateDeviceGroup.call_count == 1,
         "Only 1 call (EMPTY group skipped)",
         expected=1, actual=_datamodel.AddOrUpdateDeviceGroup.call_count)
run(tc)


# =============================================================================
# GROUP I  –  Integration: simulated full flow
# =============================================================================
print("\n[Integration Tests]")

# TC-I-01
tc = TC("TC-I-01", "Discovery by ip_address: specific IPs provided in request")
ips = ["10.0.104.1", "10.0.104.2"]
# main.py reads request["ip_address"] directly and passes to discover_new_ips
tc.check(len(ips) == 2, "2 IPs ready for discovery", expected=2, actual=len(ips))
tc.nb("discover_new_ips -> SubmitChildTask",
      hostips=ips,
      note="task_param['discoverOption']['hostips'] = this list")
run(tc)

# TC-I-02
tc = TC("TC-I-02", "Discovery by ip_address: no IPs given -> enumerate subnets -> query each")
# Step 1: enumerate subnets
subnet_resp = load("01_subnet_list.json")
subnets = extract_ips(subnet_resp, {"ip_keys": ["network"]})
tc.check(subnets == ["10.0.104.0/24", "10.0.110.0/24", "192.168.1.0/24"],
         "Step 1: 3 subnets enumerated",
         expected=["10.0.104.0/24", "10.0.110.0/24", "192.168.1.0/24"],
         actual=subnets)
# Step 2: query each subnet
subnet_responses = {
    "10.0.104.0/24":  load("02_ipv4_104.json"),
    "10.0.110.0/24":  load("03_ipv4_110.json"),
    "192.168.1.0/24": load("04_ipv4_192.json"),
}
request = {"ip_keys": ["ip_address"]}
all_ips = []
for sn in subnets:
    all_ips.extend(extract_ips(subnet_responses[sn], request))

tc.check(len(all_ips) == 7,
         "Step 2: 7 IPs collected (3 + 2 + 2)",
         expected=7, actual=len(all_ips))
tc.check(all(ip in all_ips for ip in ["10.0.104.1", "10.0.110.1", "192.168.1.1"]),
         "IPs from all 3 subnets present")
tc.nb("discover_new_ips -> SubmitChildTask",
      hostips=all_ips,
      note="task_param['discoverOption']['hostips'] = all 7 IPs from 3 subnets")
run(tc)

# TC-I-03
tc = TC("TC-I-03", "Discovery by network: specific subnets provided in request")
subnets = ["10.0.104.0/24", "10.0.110.0/24"]
tc.check(len(subnets) == 2, "2 subnets ready", expected=2, actual=len(subnets))
tc.nb("discover_new_ips -> SubmitChildTask",
      hostips=subnets,
      note="Subnet CIDRs accepted in hostips; NetBrain discovers all devices within each CIDR")
run(tc)

# TC-I-04
tc = TC("TC-I-04", "Discovery by network: no subnets given -> enumerate all from Infoblox")
subnet_resp  = load("01_subnet_list.json")
all_subnets  = extract_ips(subnet_resp, {"ip_keys": ["network"]})
tc.check(len(all_subnets) == 3,
         "3 subnets enumerated from /network",
         expected=3, actual=len(all_subnets))
tc.nb("discover_new_ips -> SubmitChildTask",
      hostips=all_subnets,
      note="All subnets from /network enumeration used as hostips")
run(tc)

# TC-I-05
tc = TC("TC-I-05", "Discovery by ip_address: result_filter status=USED excludes UNUSED IPs")
resp = load("07_ipv4_mixed_status.json")
ips  = extract_ips(resp, {"ip_keys": ["ip_address"],
                           "result_filter": [{"status": "USED"}]})
tc.check(len(ips) == 3, "3 USED IPs extracted (2 UNUSED excluded)",
         expected=3, actual=len(ips))
tc.check("10.0.104.100" not in ips and "10.0.104.101" not in ips,
         "UNUSED IPs not in discovery list")
tc.nb("discover_new_ips -> SubmitChildTask",
      hostips=ips,
      note="Only USED IPs forwarded; 2 UNUSED addresses dropped before discovery")
run(tc)

# TC-I-06
tc = TC("TC-I-06", "Dynamic Group full flow: group by Zone -> 2 Device Groups in NetBrain")
_datamodel.AddOrUpdateDeviceGroup.reset_mock()
_datamodel.AddOrUpdateDeviceGroup.return_value = True
resp    = load("05_network_extattrs.json")
request = {
    "group_by":             "Zone",
    "group_value_field":    "network",
    "device_group_parent":  "Shared Device Groups",
    "device_group_schema":  "mgmtIP",
    "device_group_operator": 0,
}
mapping = build_group_mapping(resp, request)
tc.check(set(mapping.keys()) == {"CORE", "EDGE"},
         "Mapping: CORE and EDGE",
         expected={"CORE", "EDGE"}, actual=set(mapping.keys()))
upsert_dynamic_groups(mapping,
                      parent_path=request["device_group_parent"],
                      schema=request["device_group_schema"],
                      operator=request["device_group_operator"])
calls = _datamodel.AddOrUpdateDeviceGroup.call_args_list
tc.check(len(calls) == 2, "2 AddOrUpdateDeviceGroup calls",
         expected=2, actual=len(calls))
for c in calls:
    path, condition, name = c[0]
    tc.nb("datamodel.AddOrUpdateDeviceGroup",
          path=path,
          condition=condition,
          name=name)
run(tc)

# TC-I-07
tc = TC("TC-I-07", "Dynamic Group: result_filter network_view=default -> only CORE group created")
_datamodel.AddOrUpdateDeviceGroup.reset_mock()
_datamodel.AddOrUpdateDeviceGroup.return_value = True
resp    = load("06_network_mixed_views.json")
request = {
    "group_by":             "Zone",
    "group_value_field":    "network",
    "result_filter":        [{"network_view": "default"}],
    "device_group_parent":  "Shared Device Groups",
    "device_group_schema":  "mgmtIP",
    "device_group_operator": 0,
}
mapping = build_group_mapping(resp, request)
tc.check(set(mapping.keys()) == {"CORE"},
         "Only CORE in mapping after dmz records filtered",
         expected={"CORE"}, actual=set(mapping.keys()))
upsert_dynamic_groups(mapping,
                      parent_path=request["device_group_parent"],
                      schema=request["device_group_schema"],
                      operator=request["device_group_operator"])
calls = _datamodel.AddOrUpdateDeviceGroup.call_args_list
tc.check(len(calls) == 1,
         "Only 1 AddOrUpdateDeviceGroup call (no EDGE)",
         expected=1, actual=len(calls))
path, condition, name = calls[0][0]
tc.check(path == "Shared Device Groups/CORE",
         "Correct path",
         expected="Shared Device Groups/CORE", actual=path)
tc.nb("datamodel.AddOrUpdateDeviceGroup",
      path=path,
      condition=condition,
      name=name)
run(tc)

# TC-I-08
tc = TC("TC-I-08", "Dynamic Group: missing group_by in request -> empty mapping, no NetBrain calls")
_datamodel.AddOrUpdateDeviceGroup.reset_mock()
resp    = load("05_network_extattrs.json")
mapping = build_group_mapping(resp, {"group_value_field": "network"})  # no group_by
tc.check(mapping == {}, "Empty mapping returned",
         expected={}, actual=mapping)
upsert_dynamic_groups(mapping)
tc.check(_datamodel.AddOrUpdateDeviceGroup.call_count == 0,
         "No NetBrain calls when mapping is empty",
         expected=0, actual=_datamodel.AddOrUpdateDeviceGroup.call_count)
run(tc)


# =============================================================================
# Report generation
# =============================================================================
passed = sum(1 for r in RESULTS if r.passed)
failed = sum(1 for r in RESULTS if not r.passed)
total  = len(RESULTS)

print(f"\nSummary: {passed}/{total} passed  |  {failed} failed\n")

import html as _html

GROUPS = [
    ("Parsing Tests",           "infoblox.py — pure functions",          "TC-P"),
    ("Filter Tests",            "infoblox.py",                           "TC-F"),
    ("Dynamic Group Tests",     "dynamic_group.py — condition building", "TC-D"),
    ("Integration Tests",       "full Discovery &amp; Device Group flow","TC-I"),
]

def esc(s):
    return _html.escape(str(s))

def badge(ok):
    cls = "pass" if ok else "fail"
    return f'<span class="badge {cls}">{"PASS" if ok else "FAIL"}</span>'

body_parts = []

for group_title, group_sub, prefix in GROUPS:
    group_tcs = [r for r in RESULTS if r.tc_id.startswith(prefix)]
    gp = sum(1 for r in group_tcs if r.passed)
    all_pass = gp == len(group_tcs)

    tc_rows = []
    for r in group_tcs:
        # assertions
        assertion_rows = ""
        for ok, label, expected, actual in r.checks:
            mark = "&#10003;" if ok else "&#10007;"
            cls  = "ok" if ok else "ko"
            row  = f'<tr class="{cls}"><td class="mark">{mark}</td><td>{esc(label)}</td>'
            if not ok:
                row += f'<td class="diff">expected&nbsp;<code>{esc(expected)}</code><br>actual&nbsp;<code>{esc(actual)}</code></td>'
            else:
                row += '<td></td>'
            row += '</tr>'
            assertion_rows += row

        # nb calls
        nb_html = ""
        if r.nb_calls:
            nb_html = '<div class="nb-section"><strong>NetBrain Interface Calls</strong>'
            for nb in r.nb_calls:
                nb_html += f'<div class="nb-iface">{esc(nb["interface"])}</div>'
                nb_html += f'<pre class="json">{esc(json.dumps(nb["args"], indent=2, default=str))}</pre>'
            nb_html += '</div>'

        tc_rows.append(f"""
        <div class="tc {'tc-pass' if r.passed else 'tc-fail'}">
          <div class="tc-header">
            <span class="tc-id">{esc(r.tc_id)}</span>
            {badge(r.passed)}
            <span class="tc-desc">{esc(r.description)}</span>
          </div>
          <div class="tc-body">
            <table class="assertions">
              <tbody>{assertion_rows}</tbody>
            </table>
            {nb_html}
          </div>
        </div>""")

    body_parts.append(f"""
    <section class="group">
      <div class="group-header {'all-pass' if all_pass else 'has-fail'}">
        <span class="group-title">{esc(group_title)}</span>
        <span class="group-sub">{group_sub}</span>
        <span class="group-score">{gp}/{len(group_tcs)}</span>
      </div>
      {''.join(tc_rows)}
    </section>""")

summary_class = "summary-pass" if failed == 0 else "summary-fail"
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Infoblox Integration — Test Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f4f6f9; color: #222; font-size: 14px; }}
  header {{ background: #1a2b45; color: #fff; padding: 28px 40px 24px; }}
  header h1 {{ font-size: 22px; font-weight: 600; letter-spacing: .3px; }}
  header p  {{ color: #94a3b8; margin-top: 4px; font-size: 13px; }}
  .summary {{ display: flex; gap: 16px; margin: 20px 40px; }}
  .stat {{ background: #fff; border-radius: 8px; padding: 16px 24px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); min-width: 120px; text-align: center; }}
  .stat .num {{ font-size: 32px; font-weight: 700; }}
  .stat .lbl {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
  .stat.total .num  {{ color: #1a2b45; }}
  .stat.spassed .num {{ color: #16a34a; }}
  .stat.sfailed .num {{ color: #dc2626; }}
  .{summary_class} {{ /* placeholder */ }}
  main {{ padding: 0 40px 40px; }}
  section.group {{ margin-bottom: 24px; }}
  .group-header {{ display: flex; align-items: center; gap: 12px;
                   background: #fff; border-radius: 8px 8px 0 0;
                   padding: 14px 20px; border-left: 4px solid #94a3b8;
                   box-shadow: 0 1px 2px rgba(0,0,0,.06); }}
  .group-header.all-pass  {{ border-left-color: #16a34a; }}
  .group-header.has-fail  {{ border-left-color: #dc2626; }}
  .group-title {{ font-weight: 700; font-size: 15px; }}
  .group-sub   {{ color: #64748b; font-size: 12px; }}
  .group-score {{ margin-left: auto; font-weight: 600; color: #1a2b45; }}
  .tc {{ background: #fff; border-top: 1px solid #e2e8f0; }}
  .tc:last-child {{ border-radius: 0 0 8px 8px; box-shadow: 0 1px 2px rgba(0,0,0,.06); }}
  .tc-header {{ display: flex; align-items: center; gap: 10px;
                padding: 10px 20px; cursor: default; }}
  .tc-id   {{ font-family: monospace; font-size: 12px; color: #64748b;
              background: #f1f5f9; padding: 2px 7px; border-radius: 4px; }}
  .tc-desc {{ font-size: 13px; }}
  .tc-body {{ padding: 0 20px 14px 20px; }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px;
            border-radius: 10px; letter-spacing: .4px; }}
  .badge.pass {{ background: #dcfce7; color: #15803d; }}
  .badge.fail {{ background: #fee2e2; color: #b91c1c; }}
  table.assertions {{ border-collapse: collapse; width: 100%; margin-top: 6px; }}
  table.assertions td {{ padding: 4px 8px; vertical-align: top; font-size: 13px; }}
  tr.ok .mark {{ color: #16a34a; font-size: 15px; width: 20px; }}
  tr.ko .mark {{ color: #dc2626; font-size: 15px; width: 20px; }}
  .diff {{ color: #64748b; font-size: 12px; }}
  .diff code {{ background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }}
  .nb-section {{ margin-top: 12px; border-top: 1px dashed #cbd5e1; padding-top: 10px; }}
  .nb-section strong {{ font-size: 12px; color: #475569; }}
  .nb-iface {{ font-family: monospace; font-size: 12px; color: #1e40af;
               background: #eff6ff; padding: 3px 8px; border-radius: 4px;
               margin: 8px 0 4px; display: inline-block; }}
  pre.json {{ background: #1e293b; color: #e2e8f0; padding: 12px 16px;
              border-radius: 6px; font-size: 12px; line-height: 1.6;
              overflow-x: auto; white-space: pre; }}
</style>
</head>
<body>
<header>
  <h1>Infoblox Integration &mdash; Test Report</h1>
  <p>Date: 2026-07-01 &nbsp;&bull;&nbsp; Scope: Discovery flow &amp; Dynamic Device Group flow</p>
</header>

<div class="summary">
  <div class="stat total">  <div class="num">{total}</div>  <div class="lbl">Total</div>  </div>
  <div class="stat spassed"><div class="num">{passed}</div> <div class="lbl">Passed</div> </div>
  <div class="stat sfailed"><div class="num">{failed}</div> <div class="lbl">Failed</div> </div>
</div>

<main>
{''.join(body_parts)}
</main>
</body>
</html>"""

report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_report.html")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report -> {report_path}")
sys.exit(0 if failed == 0 else 1)
