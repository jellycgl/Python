## Infoblox NetBrain Integration Plugin

### Overview

This plugin integrates **Infoblox IPAM** (IP Address Management) with the **NetBrain** network automation platform. It reads network address data from Infoblox via the WAPI REST interface and drives two core operations in NetBrain:

1. **Device Discovery** — fetch IP addresses or subnets from Infoblox and trigger NetBrain on-demand discovery tasks
2. **Dynamic Device Group Management** — build and maintain NetBrain Dynamic Device Groups based on Infoblox custom attributes (`extattrs`)

---

### Architecture

The plugin is composed of five modules:

| Module | Responsibility |
|--------|---------------|
| `main.py` | Plugin entry point — parses input and routes each request to the appropriate handler |
| `api_server.py` | Wraps the NetBrain External API Server and forwards WAPI calls through the Front Server |
| `infoblox.py` | Vendor-specific layer — defines WAPI endpoints, response normalization, IP extraction, and group-mapping logic |
| `discovery.py` | Builds and submits NetBrain on-demand discovery tasks |
| `dynamic_group.py` | Creates, updates, and reads NetBrain Dynamic Device Groups via `AddOrUpdateDeviceGroup` |

> **Extensibility:** `infoblox.py` is the only vendor-specific file. To support a different vendor, copy it, adjust the parsing logic, and change a single import line in `main.py`.

---

### Feature 1 — Device Discovery

Set `"purpose": "discovery"` on a request to activate this flow.

Two discovery modes are supported via the `discovery_by` field:

**By IP address (default)**
- If `ip_address` is provided → discover exactly those IPs
- If none provided → enumerate all subnets from `/wapi/v2.10/network`, then query `/wapi/v2.10/ipv4address` per subnet to collect all addresses, and discover the full set

**By network/subnet**
- If `network` (CIDR) is provided → discover exactly those subnets
- If none provided → enumerate all subnets from Infoblox and discover them all

Both single IPs and CIDR subnets are valid `hostips` values for NetBrain discovery. Discovery tasks are submitted as **On-Demand Discover Tasks**, and execution logs stream back in real time.

**Supported request parameters:**

| Parameter | Description |
|-----------|-------------|
| `discovery_by` | `"ip_address"` (default) or `"network"` |
| `ip_address` | One or more specific IPs to discover |
| `network` | One or more specific subnet CIDRs to discover |
| `api_url` | Override the default WAPI IPv4 endpoint |
| `subnet_url` | Override the default WAPI subnet endpoint |
| `_return_fields` | WAPI fields to include in the response |
| `ip_keys` | Response field(s) to extract IP/subnet values from |
| `result_filter` | Conditions records must satisfy (e.g. `[{"status": "USED"}]`) |

---

### Feature 2 — Dynamic Device Group Management

Set `"purpose": "dynamic_group"` on a request to activate this flow.

**How it works:**

1. Queries `/wapi/v2.7/network` (with `extattrs`) to retrieve all network records
2. Groups each subnet by the value of a user-chosen column (`group_by`, e.g. `"Zone"`)
3. Produces a mapping such as `{"CORE": ["10.0.104.0/24", ...], "EDGE": [...]}`
4. Creates or updates one NetBrain Dynamic Device Group per entry under the configured parent folder
5. Each group's filter selects devices whose Management IP falls inside any of the group's subnets (OR-combined conditions)

**Supported request parameters:**

| Parameter | Description |
|-----------|-------------|
| `group_by` | Infoblox attribute to group by (e.g. `"Zone"`, `"Building"`) — required |
| `group_value_field` | Field to collect as the group value (default `"network"`) |
| `api_url` | Override the default WAPI network endpoint |
| `_return_fields` | WAPI fields to request (default includes `network`, `extattrs`, etc.) |
| `result_filter` | Pre-filter records before grouping |
| `device_group_parent` | Parent folder for created groups (default `"Shared Device Groups"`) |
| `device_group_schema` | Device attribute to match against (default `"mgmtIP"`) |
| `device_group_operator` | Match operator (default `0` = Match) |

---

### Plugin Input Format

The plugin accepts a JSON object with the following top-level fields:

```json
{
  "apiServerName": "infoblox",
  "apiRequests": [
    {
      "enable": true,
      "purpose": "discovery",
      "discovery_by": "network",
      "api_url": "/wapi/v2.10/ipv4address",
      "subnet_url": "/wapi/v2.10/network",
      "_return_fields": [
        "ip_address", "names", "mac_address", "dhcp_client_identifier",
        "status", "types", "discover_now_status", "usage",
        "lease_state", "username", "discovered_data", "network", "fingerprint"
      ],
      "ip_address": [],
      "network": [],
      "result_filter": []
    },
    {
      "enable": false,
      "purpose": "dynamic_group",
      "api_url": "/wapi/v2.7/network",
      "_return_fields": ["network", "network_view", "comment", "extattrs"],
      "group_by": "Zone",
      "group_value_field": "network",
      "device_group_parent": "Shared Device Groups",
      "device_group_schema": "mgmtIP",
      "device_group_operator": 0,
      "result_filter": []
    }
  ],
  "testLimit": 1,
  "dryRun": false
}
```

**Top-level fields:**

| Field | Description |
|-------|-------------|
| `apiServerName` | Name of the configured NetBrain External API Server |
| `apiRequests` | Array of request objects; each must have `enable: true` to run |
| `testLimit` | (Optional) Cap the number of records processed per request — useful for testing |
| `dryRun` | (Optional) When `true`, log all intended actions without submitting discovery tasks or modifying device groups |

**Per-request fields (discovery):**

| Field | Description |
|-------|-------------|
| `enable` | Set to `true` to run this request; `false` to skip |
| `purpose` | `"discovery"` |
| `discovery_by` | `"ip_address"` (default) or `"network"` |
| `api_url` | WAPI IPv4 address endpoint (default `/wapi/v2.10/ipv4address`) |
| `subnet_url` | WAPI subnet enumeration endpoint (default `/wapi/v2.10/network`) |
| `_return_fields` | Fields to request back from the WAPI IPv4 endpoint |
| `ip_address` | One or more specific IPs to discover; empty array = fetch all |
| `network` | One or more specific subnet CIDRs to discover; empty array = fetch all |
| `ip_keys` | Response field(s) to extract IP/subnet values from (default `["ip_address"]`) |
| `result_filter` | Filter conditions records must satisfy before extraction (e.g. `[{"status": "USED"}]`); empty array = no filter |

**Per-request fields (dynamic_group):**

| Field | Description |
|-------|-------------|
| `enable` | Set to `true` to run this request; `false` to skip |
| `purpose` | `"dynamic_group"` |
| `api_url` | WAPI network endpoint (default `/wapi/v2.7/network`) |
| `_return_fields` | Fields to request back from the WAPI network endpoint |
| `group_by` | Infoblox attribute to group subnets by (e.g. `"Zone"`, `"Building"`) — **required** |
| `group_value_field` | Response field to collect as the group member value (default `"network"`) |
| `device_group_parent` | Parent folder for created groups (default `"Shared Device Groups"`) |
| `device_group_schema` | Device attribute to match against (default `"mgmtIP"`) |
| `device_group_operator` | DySearchOperator value (default `0` = Match) |
| `result_filter` | Filter conditions applied before grouping; empty array = no filter |

---

### Response Handling

The plugin normalizes Infoblox WAPI responses defensively — handling bare lists, JSON strings, wrapper objects (`{"result": [...]}`, `{"data": [...]}`, `{"items": [...]}`), and literal `null` returns (treated as empty, not an error). Non-200 HTTP status codes are logged and treated as empty responses.

---

### Logging

All significant steps emit structured log entries via `pluginfw.AddLog` at `INFO`, `WARNING`, or `ERROR` level. Key events logged include:

- API Server resolved and its metadata
- Each WAPI request URL and query parameters
- Raw response type, length, and content
- Number of records matched, filtered, and extracted
- Discovery task submission result
- Dynamic Group upsert success or failure per group
