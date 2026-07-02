# Infoblox Integration — Test Report

**Date**: 2026-07-01  
**Result**: 27/27 passed  |  0 failed

---

## Parsing Tests (infoblox.py — pure functions)  (10/10)

### TC-P-01 — extract_ips: all IPs from ipv4address response, no filter

**Result**: `PASS`

**Assertions**

- `[OK]` All 3 IPs extracted

### TC-P-02 — extract_ips: result_filter status=USED keeps only USED records

**Result**: `PASS`

**Assertions**

- `[OK]` 3 USED IPs returned; 2 UNUSED filtered
- `[OK]` UNUSED IPs 10.0.104.100 and .101 absent

### TC-P-03 — extract_ips: ip_keys=["network"] collects subnet CIDRs

**Result**: `PASS`

**Assertions**

- `[OK]` All 3 subnet CIDRs extracted

### TC-P-04 — extract_ips: empty API response returns empty list

**Result**: `PASS`

**Assertions**

- `[OK]` Empty list for empty response

### TC-P-05 — extract_ips: test_limit=2 truncates to first 2 records

**Result**: `PASS`

**Assertions**

- `[OK]` 2 IPs returned
- `[OK]` Only first 2 records processed

### TC-P-06 — build_group_mapping: group by Zone -> CORE and EDGE groups

**Result**: `PASS`

**Assertions**

- `[OK]` Two groups: CORE and EDGE
- `[OK]` CORE has 2 subnets
- `[OK]` EDGE has 2 subnets

### TC-P-07 — build_group_mapping: group by Building -> HQ / Branch-01 / Branch-02

**Result**: `PASS`

**Assertions**

- `[OK]` Three building groups
- `[OK]` HQ has 2 subnets
- `[OK]` Branch-01 has 1 subnet
- `[OK]` Branch-02 has 1 subnet

### TC-P-08 — build_group_mapping: result_filter network_view=default drops dmz records

**Result**: `PASS`

**Assertions**

- `[OK]` Only CORE group (dmz EDGE records filtered out)
- `[OK]` CORE contains the 2 default-view subnets only

### TC-P-09 — build_group_mapping: records missing Zone extattr are skipped

**Result**: `PASS`

**Assertions**

- `[OK]` Groups only for records that have Zone
- `[OK]` CORE has 1 subnet (10.0.110.0/24 skipped: extattrs={} )
- `[OK]` EDGE has 1 subnet (172.16.0.0/24 skipped: no extattrs key)

### TC-P-10 — build_group_mapping: duplicate subnets within same group are deduplicated

**Result**: `PASS`

**Assertions**

- `[OK]` Duplicate 10.0.104.0/24 deduplicated; CORE has 2 unique subnets

## Filter Tests (infoblox.py)  (4/4)

### TC-F-01 — match_filters: empty filter always returns True

**Result**: `PASS`

**Assertions**

- `[OK]` Empty filter -> True regardless of record content

### TC-F-02 — match_filters: flat key match and mismatch

**Result**: `PASS`

**Assertions**

- `[OK]` USED matches USED
- `[OK]` USED does not match UNUSED

### TC-F-03 — match_filters: expected value as list means OR within that field

**Result**: `PASS`

**Assertions**

- `[OK]` dmz is in [default, dmz]
- `[OK]` dmz is NOT in [default]

### TC-F-04 — match_filters: multiple conditions are AND-ed

**Result**: `PASS`

**Assertions**

- `[OK]` Both conditions satisfied -> True
- `[OK]` First OK, second fails -> False

## Dynamic Group Condition Tests (dynamic_group.py)  (5/5)

### TC-D-01 — _build_condition: single subnet -> expression='A'

**Result**: `PASS`

**Assertions**

- `[OK]` Single condition letter is A
- `[OK]` Exactly 1 condition
- `[OK]` Condition fields correct

### TC-D-02 — _build_condition: three subnets -> expression='A or B or C'

**Result**: `PASS`

**Assertions**

- `[OK]` Three conditions OR-combined
- `[OK]` Subnet order preserved in conditions

### TC-D-03 — upsert_dynamic_groups: 2-group mapping -> 2 AddOrUpdateDeviceGroup calls

**Result**: `PASS`

**Assertions**

- `[OK]` Exactly 2 calls
- `[OK]` Correct paths for both groups
- `[OK]` CORE call found
- `[OK]` CORE filter expression is 'A or B' (2 subnets)

**NetBrain Interface Calls**

**`datamodel.AddOrUpdateDeviceGroup`**
```json
{
  "path": "Shared Device Groups/CORE",
  "name": "CORE",
  "filter_expression": "A or B",
  "conditions": [
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "10.0.104.0/24"
    },
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "10.0.110.0/24"
    }
  ]
}
```
**`datamodel.AddOrUpdateDeviceGroup`**
```json
{
  "path": "Shared Device Groups/EDGE",
  "name": "EDGE",
  "filter_expression": "A",
  "conditions": [
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "192.168.1.0/24"
    }
  ]
}
```

### TC-D-04 — upsert_dynamic_groups: empty mapping -> no NetBrain calls

**Result**: `PASS`

**Assertions**

- `[OK]` 0 calls for empty mapping

### TC-D-05 — upsert_dynamic_groups: group with empty subnet list is skipped

**Result**: `PASS`

**Assertions**

- `[OK]` Only 1 call (EMPTY group skipped)

## Integration Tests — full flow simulation  (8/8)

### TC-I-01 — Discovery by ip_address: specific IPs provided in request

**Result**: `PASS`

**Assertions**

- `[OK]` 2 IPs ready for discovery

**NetBrain Interface Calls**

**`discover_new_ips -> SubmitChildTask`**
```json
{
  "hostips": [
    "10.0.104.1",
    "10.0.104.2"
  ],
  "note": "task_param['discoverOption']['hostips'] = this list"
}
```

### TC-I-02 — Discovery by ip_address: no IPs given -> enumerate subnets -> query each

**Result**: `PASS`

**Assertions**

- `[OK]` Step 1: 3 subnets enumerated
- `[OK]` Step 2: 7 IPs collected (3 + 2 + 2)
- `[OK]` IPs from all 3 subnets present

**NetBrain Interface Calls**

**`discover_new_ips -> SubmitChildTask`**
```json
{
  "hostips": [
    "10.0.104.1",
    "10.0.104.2",
    "10.0.104.100",
    "10.0.110.1",
    "10.0.110.2",
    "192.168.1.1",
    "192.168.1.254"
  ],
  "note": "task_param['discoverOption']['hostips'] = all 7 IPs from 3 subnets"
}
```

### TC-I-03 — Discovery by network: specific subnets provided in request

**Result**: `PASS`

**Assertions**

- `[OK]` 2 subnets ready

**NetBrain Interface Calls**

**`discover_new_ips -> SubmitChildTask`**
```json
{
  "hostips": [
    "10.0.104.0/24",
    "10.0.110.0/24"
  ],
  "note": "Subnet CIDRs accepted in hostips; NetBrain discovers all devices within each CIDR"
}
```

### TC-I-04 — Discovery by network: no subnets given -> enumerate all from Infoblox

**Result**: `PASS`

**Assertions**

- `[OK]` 3 subnets enumerated from /network

**NetBrain Interface Calls**

**`discover_new_ips -> SubmitChildTask`**
```json
{
  "hostips": [
    "10.0.104.0/24",
    "10.0.110.0/24",
    "192.168.1.0/24"
  ],
  "note": "All subnets from /network enumeration used as hostips"
}
```

### TC-I-05 — Discovery by ip_address: result_filter status=USED excludes UNUSED IPs

**Result**: `PASS`

**Assertions**

- `[OK]` 3 USED IPs extracted (2 UNUSED excluded)
- `[OK]` UNUSED IPs not in discovery list

**NetBrain Interface Calls**

**`discover_new_ips -> SubmitChildTask`**
```json
{
  "hostips": [
    "10.0.104.1",
    "10.0.104.2",
    "10.0.104.200"
  ],
  "note": "Only USED IPs forwarded; 2 UNUSED addresses dropped before discovery"
}
```

### TC-I-06 — Dynamic Group full flow: group by Zone -> 2 Device Groups in NetBrain

**Result**: `PASS`

**Assertions**

- `[OK]` Mapping: CORE and EDGE
- `[OK]` 2 AddOrUpdateDeviceGroup calls

**NetBrain Interface Calls**

**`datamodel.AddOrUpdateDeviceGroup`**
```json
{
  "path": "Shared Device Groups/CORE",
  "name": "CORE",
  "filter_expression": "A or B",
  "conditions": [
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "10.0.104.0/24"
    },
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "10.0.110.0/24"
    }
  ]
}
```
**`datamodel.AddOrUpdateDeviceGroup`**
```json
{
  "path": "Shared Device Groups/EDGE",
  "name": "EDGE",
  "filter_expression": "A or B",
  "conditions": [
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "192.168.1.0/24"
    },
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "172.16.0.0/24"
    }
  ]
}
```

### TC-I-07 — Dynamic Group: result_filter network_view=default -> only CORE group created

**Result**: `PASS`

**Assertions**

- `[OK]` Only CORE in mapping after dmz records filtered
- `[OK]` Only 1 AddOrUpdateDeviceGroup call (no EDGE)
- `[OK]` Correct path

**NetBrain Interface Calls**

**`datamodel.AddOrUpdateDeviceGroup`**
```json
{
  "path": "Shared Device Groups/CORE",
  "name": "CORE",
  "filter_expression": "A or B",
  "conditions": [
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "10.0.104.0/24"
    },
    {
      "schema": "mgmtIP",
      "operator": 0,
      "expression": "10.0.110.0/24"
    }
  ]
}
```

### TC-I-08 — Dynamic Group: missing group_by in request -> empty mapping, no NetBrain calls

**Result**: `PASS`

**Assertions**

- `[OK]` Empty mapping returned
- `[OK]` No NetBrain calls when mapping is empty
