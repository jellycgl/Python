#!/usr/bin/env python3
"""
Test suite for the Infoblox IP Reconciliation plugin
(Infoblox/Infoblox_IP_Reconciliation/python/main.py).

Scope: verify parsing, reconciliation logic, CSV building and the full run()
orchestration across a range of scenarios. NetBrain's own middle layer
(External API Server resolution, Front Server, duplicateip/certification/
datamodel lookups) is stubbed out with fixture data -- only the plugin's own
code is exercised. The Infoblox WAPI response is fed in as if
pythonlib.get_api_response() had already echoed it back, so the request
construction (URL/query) and response parsing are verified end to end.

Usage:
    python "run_ip_reconciliation_tests.py"
    -> writes ip_reconciliation_test_report.html alongside this script
"""

import sys, os, json, types
from unittest.mock import MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# 1. Build fake "netbrain" / "pythonlib" modules BEFORE importing the plugin
#    Real ModuleType (not MagicMock) for netbrain.sysapi so that
#    "from netbrain.sysapi import datamodel" resolves to OUR mock via a plain
#    getattr, instead of MagicMock's auto-attribute fallback silently handing
#    back an unrelated stub.
# ─────────────────────────────────────────────────────────────────────────────
_pluginfw = MagicMock()
_pluginfw.INFO, _pluginfw.WARNING, _pluginfw.ERROR = "INFO", "WARNING", "ERROR"
_pluginfw.AddLog = lambda msg, level=None: None

_datamodel = MagicMock()
_certification = MagicMock()
_duplicateip = MagicMock()

_pythonlib = types.ModuleType("pythonlib")
_pythonlib.get_api_response = lambda payload: None  # replaced per-scenario

_netbrain = types.ModuleType("netbrain")
_netbrain_sysapi = types.ModuleType("netbrain.sysapi")
_netbrain_sysapi.pluginfw = _pluginfw
_netbrain_sysapi.datamodel = _datamodel
_netbrain_sysapi.certification = _certification
_netbrain_sysapi.duplicateip = _duplicateip
_netbrain.sysapi = _netbrain_sysapi

sys.modules["netbrain"] = _netbrain
sys.modules["netbrain.sysapi"] = _netbrain_sysapi
sys.modules["netbrain.sysapi.pluginfw"] = _pluginfw
sys.modules["netbrain.sysapi.datamodel"] = _datamodel
sys.modules["netbrain.sysapi.certification"] = _certification
sys.modules["netbrain.sysapi.duplicateip"] = _duplicateip
sys.modules["pythonlib"] = _pythonlib

# ─────────────────────────────────────────────────────────────────────────────
# 2. Load the plugin module directly from its file (it isn't a package)
# ─────────────────────────────────────────────────────────────────────────────
import importlib.util

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_PATH = os.path.join(
    os.path.dirname(THIS_DIR),
    "Infoblox", "Infoblox_IP_Reconciliation", "python", "main.py",
)

_spec = importlib.util.spec_from_file_location("ip_reconciliation_main", PLUGIN_PATH)
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Fixture helpers
# ─────────────────────────────────────────────────────────────────────────────
FIX_DIR = os.path.join(THIS_DIR, "ip_reconciliation")
API_DIR = os.path.join(FIX_DIR, "api_responses")
NB_DIR = os.path.join(FIX_DIR, "netbrain_mocks")


def load_api(filename):
    with open(os.path.join(API_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def load_nb(filename):
    with open(os.path.join(NB_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


IP_INTERFACES = load_nb("ip_interfaces_by_subnet.json")
DEVICE_NAME_BY_IP = load_nb("device_name_by_ip.json")
SITE_SCOPE = load_nb("site_scope.json")


class ExportResult:
    def __init__(self, success, error=None):
        self.success = success
        self.error = error


def make_wapi_stub(subnet_stats, ipv4_by_subnet, api_calls):
    """
    Build a fake pythonlib.get_api_response(request_payload) that plays the
    role of "the API echo": it parses the outgoing request (url + query,
    exactly as ApiServer.forwardRequestToFS assembles it) and returns the
    canned fixture for that endpoint, mirroring a live Infoblox WAPI response.
    """

    def _stub(request_payload):
        tech_param = json.loads(request_payload)
        params = tech_param["api_params"]
        url = params["url"]
        query = params.get("api_parm", {}).get("query", {})
        api_calls.append({"url": url, "query": query})

        if "ipam:statistics" in url:
            return json.dumps(subnet_stats)

        if "ipv4address" in url:
            network = query.get("network")
            return json.dumps(ipv4_by_subnet.get(network, []))

        return json.dumps(None)

    return _stub


def wire_netbrain_side(
    ip_interfaces=None,
    device_name_by_ip=None,
    site_devices=None,
    export_result=None,
    api_server_found=True,
):
    """Reset and reconfigure the NetBrain-side mocks for one scenario."""
    _datamodel.reset_mock()
    _certification.reset_mock()
    _duplicateip.reset_mock()

    _datamodel.GetCurrentDomainInfo.return_value = {"domainDbName": "TestDomain"}
    _datamodel.QueryDataFromDB.return_value = (
        [{"_id": "srv-1", "serverTypeId": "adapter-1", "frontServerAndGroupId": "fs-1"}]
        if api_server_found else []
    )

    ip_interfaces = ip_interfaces if ip_interfaces is not None else IP_INTERFACES
    _duplicateip.GetSubnetIpInterfacesBySubnets.side_effect = (
        lambda subnets: ip_interfaces.get(subnets[0], [])
    )

    device_name_by_ip = device_name_by_ip if device_name_by_ip is not None else DEVICE_NAME_BY_IP
    _datamodel.GetDeviceNameFromIp.side_effect = lambda ip: device_name_by_ip.get(ip)

    site_devices = site_devices if site_devices is not None else SITE_SCOPE
    _datamodel.GetDeviceIdsFromSite.side_effect = (
        lambda path, include_child: site_devices["device_ids"] if path == site_devices["site_path"] else []
    )
    _datamodel.GetDeviceObjectById.side_effect = (
        lambda dev_id: site_devices["device_objects"].get(dev_id)
    )

    export_result = export_result if export_result is not None else ExportResult(True)
    _certification.export_certification_report.return_value = export_result


# ─────────────────────────────────────────────────────────────────────────────
# 4. Lightweight test-case container (same shape as run_tests.py)
# ─────────────────────────────────────────────────────────────────────────────
class TC:
    def __init__(self, tc_id, description):
        self.tc_id = tc_id
        self.description = description
        self.checks = []
        self.nb_calls = []

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
# GROUP U — Unit tests: pure / helper functions
# =============================================================================
print("\n[Unit Tests]")

# TC-U-01
tc = TC("TC-U-01", "get_json_response: bare list response parses as-is")
wire_netbrain_side()
# Direct call without a real ApiServer: a dummy stand-in whose
# forwardRequestToFS returns the fixture list directly.
dummy = types.SimpleNamespace(forwardRequestToFS=lambda fn, params: load_api("03_ipv4_10_0_104_mixed.json"))
got = plugin.get_json_response(dummy, {}, "ctx")
tc.check(isinstance(got, list) and len(got) == 5,
         "5 records parsed from bare list", expected=5, actual=len(got) if isinstance(got, list) else got)
run(tc)

# TC-U-02
tc = TC("TC-U-02", 'get_json_response: {"result": [...]} wrapper is unwrapped')
dummy = types.SimpleNamespace(forwardRequestToFS=lambda fn, params: load_api("06_ipv4_wrapped_result.json"))
got = plugin.get_json_response(dummy, {}, "ctx")
tc.check(isinstance(got, list) and len(got) == 1,
         "Wrapper unwrapped to 1 record", expected=1, actual=len(got) if isinstance(got, list) else got)
run(tc)

# TC-U-03
tc = TC("TC-U-03", "get_json_response: httpStatusCode != 200 treated as error -> None")
dummy = types.SimpleNamespace(forwardRequestToFS=lambda fn, params: load_api("07_api_error.json"))
got = plugin.get_json_response(dummy, {}, "ctx")
tc.check(got is None, "None returned for HTTP 400 response", expected=None, actual=got)
run(tc)

# TC-U-04
tc = TC("TC-U-04", "get_json_response: empty/falsy raw response -> None (no exception)")
dummy = types.SimpleNamespace(forwardRequestToFS=lambda fn, params: None)
got = plugin.get_json_response(dummy, {}, "ctx")
tc.check(got is None, "None returned for empty response", expected=None, actual=got)
run(tc)

# TC-U-05 / TC-U-06
tc = TC("TC-U-05", "get_infoblox_subnets: builds CIDR strings from network+cidr, skips entries missing cidr")
dummy = types.SimpleNamespace(
    forwardRequestToFS=lambda fn, params: json.dumps(load_api("02_subnet_stats_missing_cidr.json"))
)
subnets = plugin.get_infoblox_subnets(dummy, "v2.12")
tc.check(subnets == ["10.0.104.0/24", "10.0.110.0/24"],
         "2 CIDRs built; entry without cidr skipped",
         expected=["10.0.104.0/24", "10.0.110.0/24"], actual=subnets)
run(tc)

# TC-U-07
tc = TC("TC-U-07", "get_used_ips_for_subnet: only status=USED addresses are kept")
dummy = types.SimpleNamespace(
    forwardRequestToFS=lambda fn, params: json.dumps(load_api("03_ipv4_10_0_104_mixed.json"))
)
used = plugin.get_used_ips_for_subnet(dummy, "v2.12", "", -100000, "10.0.104.0/24")
tc.check(used == {"10.0.104.1", "10.0.104.2", "10.0.104.3", "10.0.104.5"},
         "4 USED IPs kept; 1 UNUSED (.4) excluded",
         expected={"10.0.104.1", "10.0.104.2", "10.0.104.3", "10.0.104.5"}, actual=used)
run(tc)

# TC-U-08
tc = TC("TC-U-08", "get_used_ips_for_subnet: network_view is included in the query when provided")
captured = {}
def _capture(fn, params):
    captured.update(params["api_parm"]["query"])
    return json.dumps(load_api("04_ipv4_10_0_110_all_used.json"))
dummy = types.SimpleNamespace(forwardRequestToFS=_capture)
plugin.get_used_ips_for_subnet(dummy, "v2.12", "default", -100000, "10.0.110.0/24")
tc.check(captured.get("network_view") == "default",
         "network_view='default' present in query", expected="default", actual=captured.get("network_view"))
tc.check(captured.get("network") == "10.0.110.0/24",
         "query scoped to the requested subnet", expected="10.0.110.0/24", actual=captured.get("network"))
run(tc)

# TC-U-09
tc = TC("TC-U-09", "ip_sort_key: numeric dotted-quad ordering, non-IP strings sort after valid IPs")
ips = ["10.0.104.10", "10.0.104.2", "not-an-ip", "10.0.104.1"]
got = sorted(ips, key=plugin.ip_sort_key)
tc.check(got == ["10.0.104.1", "10.0.104.2", "10.0.104.10", "not-an-ip"],
         "Numeric order for valid IPs; invalid IP pushed last",
         expected=["10.0.104.1", "10.0.104.2", "10.0.104.10", "not-an-ip"], actual=got)
run(tc)

# TC-U-10
tc = TC("TC-U-10", "reconcile_subnet: classifies consistent / discover / register correctly")
rows = plugin.reconcile_subnet(
    "10.0.104.0/24",
    infoblox_used_ips={"10.0.104.1", "10.0.104.3"},
    netbrain_ips={"10.0.104.1", "10.0.104.10"},
)
by_ip = {r[1]: r for r in rows}
tc.check(by_ip["10.0.104.1"][5] == "No action", "Present both sides -> No action",
         expected="No action", actual=by_ip["10.0.104.1"][5])
tc.check(by_ip["10.0.104.3"][5] == "Discover IP in NetBrain",
         "Infoblox-only -> Discover IP in NetBrain",
         expected="Discover IP in NetBrain", actual=by_ip["10.0.104.3"][5])
tc.check(by_ip["10.0.104.10"][5] == "Register IP in Infoblox",
         "NetBrain-only -> Register IP in Infoblox",
         expected="Register IP in Infoblox", actual=by_ip["10.0.104.10"][5])
run(tc)

# TC-U-11
tc = TC("TC-U-11", "build_csv: header row and data rows are formatted correctly")
csv_text = plugin.build_csv([["10.0.104.0/24", "10.0.104.1", "Yes", "Yes", "Yes", "No action"]])
lines = csv_text.strip().splitlines()
tc.check(lines[0] == "Subnet,IP_Address,In_NetBrain,In_Infoblox,Consistent,Recommended_Action",
         "Header row matches spec", expected="Subnet,IP_Address,...", actual=lines[0])
tc.check(lines[1] == "10.0.104.0/24,10.0.104.1,Yes,Yes,Yes,No action",
         "Data row formatted correctly",
         expected="10.0.104.0/24,10.0.104.1,Yes,Yes,Yes,No action", actual=lines[1])
run(tc)

# TC-U-12
tc = TC("TC-U-12", "is_ip_known_in_netbrain: fallback resolves/rejects based on GetDeviceNameFromIp + site scope")
wire_netbrain_side()
tc.check(plugin.is_ip_known_in_netbrain("10.0.104.5", None) is True,
         "Known IP with no site scope -> True")
tc.check(plugin.is_ip_known_in_netbrain("10.0.104.3", None) is False,
         "Unresolvable IP -> False")
tc.check(plugin.is_ip_known_in_netbrain("10.0.104.5", {"SomeOtherDevice"}) is False,
         "Resolved but device outside site scope -> False")
run(tc)

# TC-U-13
tc = TC("TC-U-13", "get_site_scoped_device_names: resolves a site path to its device names")
wire_netbrain_side()
names = plugin.get_site_scoped_device_names(SITE_SCOPE["site_path"], True)
tc.check(names == {"R1", "R2"}, "Site resolves to R1 and R2",
         expected={"R1", "R2"}, actual=names)
tc.nb("datamodel.GetDeviceIdsFromSite", site_path=SITE_SCOPE["site_path"], include_child=True)
tc.nb("datamodel.GetDeviceObjectById", resolved_names=sorted(names))
run(tc)


# =============================================================================
# GROUP I — Integration: full run() orchestration
# =============================================================================
print("\n[Integration Tests]")


def base_input(**overrides):
    payload = {
        "infoblox": {
            "api_server_name": "Infoblox API Server",
            "wapi_version": "v2.12",
            "network_view": "",
            "subnets": [],
            "max_results": -100000,
        },
        "netbrain_scope": {
            "site_path": "",
            "include_child_sites": True,
        },
    }
    for k, v in overrides.items():
        section, field = k.split(".")
        payload[section][field] = v
    return json.dumps(payload)


# TC-I-01
tc = TC("TC-I-01", "Explicit subnets, mixed reconciliation, is_ip_known_in_netbrain fallback recovers .5")
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("01_subnet_stats.json"),
    ipv4_by_subnet={"10.0.104.0/24": load_api("03_ipv4_10_0_104_mixed.json")},
    api_calls=api_calls,
)
ok = plugin.run(base_input(**{"infoblox.subnets": ["10.0.104.0/24"]}))
tc.check(ok is True, "run() returns True", expected=True, actual=ok)
export_call = _certification.export_certification_report.call_args
tc.check(export_call is not None, "export_certification_report was called")
csv_text = export_call.args[1] if export_call else ""
tc.check("10.0.104.1,Yes,Yes,Yes,No action" in csv_text, "10.0.104.1 consistent -> No action")
tc.check("10.0.104.2,Yes,Yes,Yes,No action" in csv_text, "10.0.104.2 consistent -> No action")
tc.check("10.0.104.3,No,Yes,No,Discover IP in NetBrain" in csv_text,
         ".3 stays 'Discover IP in NetBrain' (fallback also misses it)")
tc.check("10.0.104.5,Yes,Yes,Yes,No action" in csv_text,
         ".5 recovered by is_ip_known_in_netbrain fallback -> No action")
tc.check("10.0.104.10,Yes,No,No,Register IP in Infoblox" in csv_text,
         ".10 is NetBrain-only -> Register IP in Infoblox")
tc.nb("certification.export_certification_report",
      export_path=plugin.REPORT_EXPORT_PATH,
      csv_preview=csv_text.strip().splitlines())
run(tc)

# TC-I-02
tc = TC("TC-I-02", "No subnets configured -> auto-discover via ipam:statistics (missing-cidr entry skipped)")
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("02_subnet_stats_missing_cidr.json"),
    ipv4_by_subnet={
        "10.0.104.0/24": load_api("03_ipv4_10_0_104_mixed.json"),
        "10.0.110.0/24": load_api("04_ipv4_10_0_110_all_used.json"),
    },
    api_calls=api_calls,
)
ok = plugin.run(base_input())
tc.check(ok is True, "run() returns True", expected=True, actual=ok)
stat_calls = [c for c in api_calls if "ipam:statistics" in c["url"]]
tc.check(len(stat_calls) == 1, "Subnet enumeration called once", expected=1, actual=len(stat_calls))
ipv4_networks_queried = {c["query"].get("network") for c in api_calls if "ipv4address" in c["url"]}
tc.check(ipv4_networks_queried == {"10.0.104.0/24", "10.0.110.0/24"},
         "Only the 2 valid subnets were queried (10.0.200.0 dropped: no cidr)",
         expected={"10.0.104.0/24", "10.0.110.0/24"}, actual=ipv4_networks_queried)
tc.nb("pythonlib.get_api_response(ipam:statistics)", requests=stat_calls)
run(tc)

# TC-I-03
tc = TC("TC-I-03", "network_view filter is forwarded into every ipv4address query")
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("01_subnet_stats.json"),
    ipv4_by_subnet={"10.0.110.0/24": load_api("04_ipv4_10_0_110_all_used.json")},
    api_calls=api_calls,
)
ok = plugin.run(base_input(**{
    "infoblox.subnets": ["10.0.110.0/24"],
    "infoblox.network_view": "default",
}))
tc.check(ok is True, "run() returns True", expected=True, actual=ok)
ipv4_calls = [c for c in api_calls if "ipv4address" in c["url"]]
tc.check(all(c["query"].get("network_view") == "default" for c in ipv4_calls),
         "network_view='default' present on every ipv4address call")
run(tc)

# TC-I-04
tc = TC("TC-I-04", "Site scoping: devices outside the site are excluded, changing the recommended action")
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("01_subnet_stats.json"),
    ipv4_by_subnet={"10.0.104.0/24": load_api("03_ipv4_10_0_104_mixed.json")},
    api_calls=api_calls,
)
ok = plugin.run(base_input(**{
    "infoblox.subnets": ["10.0.104.0/24"],
    "netbrain_scope.site_path": SITE_SCOPE["site_path"],
}))
tc.check(ok is True, "run() returns True", expected=True, actual=ok)
csv_text = _certification.export_certification_report.call_args.args[1]
tc.check("10.0.104.10,No,No,No,Discover IP in NetBrain" not in csv_text
         and "10.0.104.10" not in csv_text,
         "SW1's .10 (outside site R1/R2) is excluded from the NetBrain side entirely")
tc.check("10.0.104.1,Yes,Yes,Yes,No action" in csv_text,
         "R1's .1 still consistent (device is inside the site)")
tc.nb("datamodel.GetDeviceIdsFromSite -> device scope", site_path=SITE_SCOPE["site_path"], allowed=["R1", "R2"])
run(tc)

# TC-I-05
tc = TC("TC-I-05", "Missing infoblox.api_server_name -> run() returns False without any API/NetBrain calls")
wire_netbrain_side()
_pythonlib.get_api_response = lambda payload: (_ for _ in ()).throw(AssertionError("should not be called"))
input_json = json.dumps({"infoblox": {}, "netbrain_scope": {}})
ok = plugin.run(input_json)
tc.check(ok is False, "run() returns False", expected=False, actual=ok)
tc.check(_datamodel.QueryDataFromDB.call_count == 0, "No ApiServer resolution attempted")
run(tc)

# TC-I-06
tc = TC("TC-I-06", "External API Server not found in NetBrain -> run() returns False")
wire_netbrain_side(api_server_found=False)
_pythonlib.get_api_response = lambda payload: (_ for _ in ()).throw(AssertionError("should not be called"))
ok = plugin.run(base_input())
tc.check(ok is False, "run() returns False when ApiServer lookup is empty", expected=False, actual=ok)
run(tc)

# TC-I-07
tc = TC("TC-I-07", "No subnets resolved from Infoblox (empty ipam:statistics) -> run() returns False")
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("08_subnet_stats_empty.json"),
    ipv4_by_subnet={},
    api_calls=api_calls,
)
ok = plugin.run(base_input())
tc.check(ok is False, "run() returns False; nothing to reconcile", expected=False, actual=ok)
tc.check(_certification.export_certification_report.call_count == 0,
         "No report exported when there are no subnets")
run(tc)

# TC-I-08
tc = TC("TC-I-08", "certification.export_certification_report failure -> run() returns False")
api_calls = []
wire_netbrain_side(export_result=ExportResult(False, "Public folder quota exceeded"))
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("01_subnet_stats.json"),
    ipv4_by_subnet={"192.168.1.0/24": load_api("05_ipv4_192_168_1_empty.json")},
    api_calls=api_calls,
)
ok = plugin.run(base_input(**{"infoblox.subnets": ["192.168.1.0/24"]}))
tc.check(ok is False, "run() returns False on export failure", expected=False, actual=ok)
tc.nb("certification.export_certification_report -> failure",
      error="Public folder quota exceeded")
run(tc)

# TC-I-09
tc = TC("TC-I-09", 'Infoblox has zero USED IPs in a subnet; NetBrain-only devices -> all rows "Register IP in Infoblox"')
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("01_subnet_stats.json"),
    ipv4_by_subnet={"192.168.1.0/24": load_api("05_ipv4_192_168_1_empty.json")},
    api_calls=api_calls,
)
ok = plugin.run(base_input(**{"infoblox.subnets": ["192.168.1.0/24"]}))
tc.check(ok is True, "run() returns True", expected=True, actual=ok)
csv_text = _certification.export_certification_report.call_args.args[1]
tc.check("192.168.1.50,Yes,No,No,Register IP in Infoblox" in csv_text,
         "EdgeRouter's 192.168.1.50 flagged for registration in Infoblox")
run(tc)

# TC-I-10
tc = TC("TC-I-10", 'ipv4address response wrapped as {"result": [...]} is unwrapped through the full run() flow')
api_calls = []
wire_netbrain_side()
_pythonlib.get_api_response = make_wapi_stub(
    subnet_stats=load_api("01_subnet_stats.json"),
    ipv4_by_subnet={"10.0.110.0/24": load_api("06_ipv4_wrapped_result.json")},
    api_calls=api_calls,
)
ok = plugin.run(base_input(**{"infoblox.subnets": ["10.0.110.0/24"]}))
tc.check(ok is True, "run() returns True", expected=True, actual=ok)
csv_text = _certification.export_certification_report.call_args.args[1]
tc.check("10.0.110.1,Yes,Yes,Yes,No action" in csv_text,
         "Wrapped result still reconciled correctly (10.0.110.1 consistent)")
run(tc)


# =============================================================================
# Report generation
# =============================================================================
passed = sum(1 for r in RESULTS if r.passed)
failed = sum(1 for r in RESULTS if not r.passed)
total = len(RESULTS)

print(f"\nSummary: {passed}/{total} passed  |  {failed} failed\n")

import html as _html

GROUPS = [
    ("Unit Tests", "main.py — helper &amp; parsing functions", "TC-U"),
    ("Integration Tests", "main.py — full run() orchestration", "TC-I"),
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
        assertion_rows = ""
        for ok, label, expected, actual in r.checks:
            mark = "&#10003;" if ok else "&#10007;"
            cls = "ok" if ok else "ko"
            row = f'<tr class="{cls}"><td class="mark">{mark}</td><td>{esc(label)}</td>'
            if not ok:
                row += f'<td class="diff">expected&nbsp;<code>{esc(expected)}</code><br>actual&nbsp;<code>{esc(actual)}</code></td>'
            else:
                row += '<td></td>'
            row += '</tr>'
            assertion_rows += row

        nb_html = ""
        if r.nb_calls:
            nb_html = '<div class="nb-section"><strong>NetBrain / API Interface Calls</strong>'
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

html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Infoblox IP Reconciliation — Test Report</title>
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
  .note {{ margin: 0 40px 20px; background: #fffbeb; border: 1px solid #fde68a;
           border-radius: 8px; padding: 12px 18px; font-size: 12.5px; color: #78350f; }}
</style>
</head>
<body>
<header>
  <h1>Infoblox IP Reconciliation &mdash; Test Report</h1>
  <p>Plugin under test: Infoblox/Infoblox_IP_Reconciliation/python/main.py</p>
</header>

<div class="note">
  <strong>Scope note:</strong> the real NetBrain middle layer (External API Server / Front Server routing,
  and the <code>duplicateip</code> / <code>datamodel</code> / <code>certification</code> interfaces) is stubbed
  with fixture data from <code>Test Data/ip_reconciliation/netbrain_mocks/</code>. The Infoblox WAPI response is
  fed in as the assumed "API echo" from <code>Test Data/ip_reconciliation/api_responses/</code>, so this report
  verifies request construction, response parsing, reconciliation logic, CSV generation and error handling in
  the plugin itself &mdash; not connectivity to a live NetBrain or Infoblox system.
</div>

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

report_path = os.path.join(THIS_DIR, "ip_reconciliation_test_report.html")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(html_out)

print(f"Report -> {report_path}")
sys.exit(0 if failed == 0 else 1)
