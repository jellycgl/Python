import json
import csv
import io
from datetime import datetime

import pythonlib
from netbrain.sysapi import datamodel, pluginfw, certification
from netbrain.sysapi import duplicateip


REPORT_EXPORT_PATH = 'Third Party System/Infoblox'
REPORT_NAME_PREFIX = 'NetBrain-Infoblox-IP-Reconciliation-Report'


class ApiServer:
    def __init__(self, domainName, apiServerName):
        self.domainName = domainName
        self.apiServerName = apiServerName
        apiServer = self.getApiServer(self.domainName, self.apiServerName)
        if not apiServer:
            raise RuntimeError(
                'External API Server "{}" was not found. Create it in NetBrain '
                '(System > Integration > API Servers) using the built-in "Infoblox API Adapter" '
                'before running this plugin.'.format(self.apiServerName)
            )
        pluginfw.AddLog('Resolved External API Server "{}": {}'.format(self.apiServerName, json.dumps(apiServer)), pluginfw.INFO)
        self.id = apiServer['_id']
        self.apiAdapterId = apiServer['serverTypeId']
        self.fsId = apiServer['frontServerAndGroupId']

    def getApiServer(self, domainName, apiServerName):
        '''
        serverTypeId is API Adapter ID, which is maintained by NB Integration Team
        as built-in resource. Its ID must be static.
        '''
        query = {
            'name': apiServerName,
            '$project': {
                '_id': 1,
                'serverTypeId': 1,
                'frontServerAndGroupId': 1
            }
        }
        apiServers = datamodel.QueryDataFromDB(domainName, 'ExternalAPIServer', query)
        if len(apiServers) > 0:
            return apiServers[0]
        return []

    def forwardRequestToFS(self, func_name, api_params=None):
        # getData() resolves API server credentials via TableParams(param, root_schema='Infoblox'),
        # which reads domain_db_name/apiServerId straight off the "param" it receives (i.e. func_args).
        # They must live INSIDE func_args alongside "url"/"api_parm", not as siblings of an
        # "api_params" wrapper -- otherwise getData never sees them (or the url/query at all).
        func_args = dict(api_params) if api_params else {}
        func_args['domain_db_name'] = self.domainName
        func_args['apiServerId'] = self.id
        tech_param = {
            'module_name': self.apiAdapterId,  # API Adapter ID
            'func_name': func_name,
            'is_call_script': True,
            'apID': self.fsId,  # FS name
            'api_params': func_args,
            'func_args': json.dumps(func_args)
        }
        request_payload = json.dumps(tech_param)
        pluginfw.AddLog('Function [{}] requested - tech_param: {}'.format(func_name, request_payload), pluginfw.INFO)
        res = pythonlib.get_api_response(request_payload)
        pluginfw.AddLog('Function [{}] returned ({}) - {}'.format(func_name, type(res).__name__, str(res)[:2000]), pluginfw.INFO)
        return res


def get_json_response(api_server, api_params, context=''):
    '''Call the Infoblox API Adapter's getData and normalize the result to a python object, or None on failure.'''
    try:
        res = api_server.forwardRequestToFS('getData', api_params)
    except Exception as e:
        pluginfw.AddLog('Infoblox API call failed for {}: {}'.format(context, e), pluginfw.ERROR)
        return None

    if not res:
        pluginfw.AddLog('Infoblox API returned no data for {}'.format(context), pluginfw.WARNING)
        return None

    if isinstance(res, (dict, list)):
        data = res
    else:
        try:
            data = json.loads(res)
        except (TypeError, ValueError) as e:
            pluginfw.AddLog('Failed to parse Infoblox API response for {}: {}'.format(context, e), pluginfw.ERROR)
            return None

    if isinstance(data, dict):
        if data.get('httpStatusCode') not in (None, 200):
            pluginfw.AddLog('Infoblox API error for {}: {}'.format(context, data), pluginfw.ERROR)
            return None
        # Some adapter responses wrap list results as {"result": [...]} instead of a bare array.
        if 'result' in data:
            data = data['result']

    return data


def get_infoblox_subnets(api_server, wapi_version):
    '''
    Enumerate every subnet Infoblox knows about via ipam:statistics, mirroring the
    confirmed-working two-step getData flow: enumerate subnets first, then query each
    one individually for its addresses.

    ipam:statistics returns "network" and "cidr" as separate fields ("network" is the
    bare network address, with no mask) - they're combined here into a proper CIDR
    string (e.g. "192.168.180.0/24") since that's what ipv4address.network actually
    carries and what NetBrain's duplicateip lookup expects.
    '''
    api_params = {
        'url': '/wapi/{}/ipam:statistics'.format(wapi_version),
        'api_parm': {'query': {'_return_fields': ['network', 'cidr']}}
    }
    data = get_json_response(api_server, api_params, 'subnet enumeration (ipam:statistics)')
    subnets = []
    for item in (data or []):
        network = item.get('network')
        cidr = item.get('cidr')
        if network and cidr:
            subnets.append('{}/{}'.format(network, cidr))
    return subnets


def get_used_ips_for_subnet(api_server, wapi_version, network_view, max_results, subnet):
    '''
    Return the set of IP addresses with status=USED within the given subnet.
    The WAPI query is always scoped to a single subnet via the "network" filter
    (an unscoped/global query has been observed to return no results) - status is
    filtered client-side since the reference getData calls never filter by it either.
    '''
    query = {
        'network': subnet,
        '_return_fields': ['ip_address', 'network', 'status', 'names', 'usage'],
        '_max_results': str(max_results)
    }
    if network_view:
        query['network_view'] = network_view
    api_params = {
        'url': '/wapi/{}/ipv4address'.format(wapi_version),
        'api_parm': {'query': query}
    }
    data = get_json_response(api_server, api_params, 'used IPs of subnet {}'.format(subnet))
    records = data if isinstance(data, list) else []
    return {r.get('ip_address') for r in records if r.get('ip_address') and r.get('status') == 'USED'}


def get_infoblox_network_info(api_server, network_view, subnet):
    '''
    Return (found, comment) for the Infoblox "network" object matching the given subnet:
    found is True iff Infoblox has a network object for this subnet, comment is its
    Comment field ('' if unset or not found).

    Always queries /wapi/v2.7/network (fixed version, independent of the configurable
    wapi_version) - this is the network-level object (not ipv4address), used only for the
    subnet-granularity report.
    '''
    query = {
        'network': subnet,
        '_return_fields': ['network', 'comment']
    }
    if network_view:
        query['network_view'] = network_view
    api_params = {
        'url': '/wapi/v2.7/network',
        'api_parm': {'query': query}
    }
    data = get_json_response(api_server, api_params, 'network info of subnet {}'.format(subnet))
    records = data if isinstance(data, list) else []
    for record in records:
        if record.get('network') == subnet:
            return True, record.get('comment') or ''
    return False, ''


def get_netbrain_subnet_data(subnet, allowed_device_names):
    '''
    Return (ips, descriptions) discovered by NetBrain within the given subnet.
      - ips: set of IP addresses found on IP Interfaces in this subnet.
      - descriptions: sorted list of unique, non-empty Interface descriptions.
    If allowed_device_names is not None, only interfaces owned by those devices are
    counted (used to scope the comparison to a specific Site).

    NetBrain auto-creates an IP Interface (ipIntfs) record whenever a device Interface
    has an IPv4 or IPv6 Address configured, but "description" only lives on the parent
    physical Interface object - the ipIntf record's own description field is always
    empty. So the description has to be looked up separately via the ipIntf's
    "devInterfaceId", which points back at the owning Interface object.
    '''
    ips = set()
    interface_ids = set()
    try:
        subnet_records = duplicateip.GetSubnetIpInterfacesBySubnets([subnet])
    except Exception as e:
        pluginfw.AddLog('Failed to query NetBrain IP interfaces for subnet {}: {}'.format(subnet, e), pluginfw.ERROR)
        return ips, []

    for record in subnet_records or []:
        for ip_intf in record.get('ipIntfs', []):
            device_name = ip_intf.get('deviceName')
            if allowed_device_names is not None and device_name not in allowed_device_names:
                continue
            ip = (ip_intf.get('ip') or '').split('/')[0]
            if ip:
                ips.add(ip)
            devInterfaceId = ip_intf.get('devInterfaceId')
            if devInterfaceId:
                interface_ids.add(devInterfaceId)

    descriptions = set()
    for intf_id in interface_ids:
        try:
            intf_obj = datamodel.GetInterfaceObjectById(intf_id, 'intfs')
        except Exception as e:
            pluginfw.AddLog('Failed to query NetBrain Interface {} for description: {}'.format(intf_id, e), pluginfw.WARNING)
            continue
        descr = (intf_obj or {}).get('descr')
        if descr:
            descriptions.add(descr)

    return ips, sorted(descriptions)


def is_ip_known_in_netbrain(ip, allowed_device_names):
    '''
    Authoritative single-IP check via datamodel.GetDeviceNameFromIp, used as a fallback/
    cross-check for get_netbrain_subnet_data(): GetSubnetIpInterfacesBySubnets is a
    "duplicate IP" API keyed on Zone grouping and can miss addresses that
    GetDeviceNameFromIp still resolves directly to a device.
    '''
    device_name = datamodel.GetDeviceNameFromIp(ip)
    if not device_name:
        return False
    if allowed_device_names is not None and device_name not in allowed_device_names:
        return False
    return True


def get_site_scoped_device_names(site_path, include_child):
    '''Resolve a NetBrain Site path to the set of device names in scope.'''
    device_ids = datamodel.GetDeviceIdsFromSite(site_path, include_child) or []
    device_names = set()
    for dev_id in device_ids:
        dev_obj = datamodel.GetDeviceObjectById(dev_id)
        if dev_obj and dev_obj.get('name'):
            device_names.add(dev_obj['name'])
    return device_names


def ip_sort_key(ip):
    try:
        return (0, tuple(int(octet) for octet in ip.split('.')))
    except ValueError:
        return (1, ip)


def reconcile_subnet(subnet, infoblox_used_ips, netbrain_ips):
    '''
    Reconciliation rules:
      1. IP is USED in Infoblox but not discovered in NetBrain -> "Discover IP in NetBrain"
      2. IP is discovered in NetBrain but not registered/USED in Infoblox -> "Register IP in Infoblox"
      3. IP is present (and consistent) on both sides -> "No action"
    '''
    rows = []
    for ip in sorted(infoblox_used_ips | netbrain_ips, key=ip_sort_key):
        in_netbrain = ip in netbrain_ips
        in_infoblox = ip in infoblox_used_ips
        consistent = in_netbrain and in_infoblox
        if consistent:
            action = 'No action'
        elif in_infoblox and not in_netbrain:
            action = 'Discover IP in NetBrain'
        else:
            action = 'Register IP in Infoblox'
        rows.append([
            subnet,
            ip,
            'Yes' if in_netbrain else 'No',
            'Yes' if in_infoblox else 'No',
            'Yes' if consistent else 'No',
            action
        ])
    return rows


def reconcile_subnet_level(subnet, in_infoblox, in_netbrain):
    '''
    Same reconciliation rules as reconcile_subnet(), applied at subnet granularity instead
    of per-IP: "in_infoblox" means Infoblox has a network object for this subnet, "in_netbrain"
    means NetBrain has discovered at least one IP interface within it.
    '''
    consistent = in_infoblox and in_netbrain
    if consistent:
        action = 'No action'
    elif in_infoblox and not in_netbrain:
        action = 'Discover Subnet in NetBrain'
    else:
        action = 'Register Subnet in Infoblox'
    return [
        subnet,
        'Yes' if in_netbrain else 'No',
        'Yes' if in_infoblox else 'No',
        'Yes' if consistent else 'No',
        action
    ]


def build_ip_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Subnet', 'IP_Address', 'In_NetBrain', 'In_Infoblox', 'Consistent', 'Recommended_Action', 'Description_NetBrain'])
    writer.writerows(rows)
    return buf.getvalue()


def build_subnet_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Subnet', 'In_NetBrain', 'In_Infoblox', 'Consistent', 'Recommended_Action', 'Comment_Infoblox', 'Description_NetBrain'])
    writer.writerows(rows)
    return buf.getvalue()


def run(input):
    '''
    Fetch used IP/subnet data from Infoblox IPAM, compare it against NetBrain's
    discovered live network data, and publish a CSV reconciliation report to
    Public/Third Party System/Infoblox.

    If report.precise_to_ip is False, the report is produced at subnet granularity
    instead of per-IP: it skips the Infoblox ipv4address/NetBrain IP comparison
    entirely and instead pulls each subnet's Comment straight off the Infoblox
    "network" object (/wapi/v2.7/network).

    return True if the plugin completed successfully, False otherwise.
    '''
    params = json.loads(input) if input else {}
    infoblox_cfg = params.get('infoblox', {})
    scope_cfg = params.get('netbrain_scope', {})
    report_cfg = params.get('report', {})

    api_server_name = infoblox_cfg.get('api_server_name') or ''
    wapi_version = infoblox_cfg.get('wapi_version') or 'v2.10'
    network_view = infoblox_cfg.get('network_view') or ''
    configured_subnets = infoblox_cfg.get('subnets') or []
    max_results = infoblox_cfg.get('max_results', -100000)

    site_path = scope_cfg.get('site_path') or ''
    include_child_sites = scope_cfg.get('include_child_sites', True)

    precise_to_ip = report_cfg.get('precise_to_ip', True)

    if not api_server_name:
        pluginfw.AddLog(
            'Missing required parameter "infoblox.api_server_name". Configure the External API '
            'Server name (System > Integration > API Servers) before running this plugin.',
            pluginfw.ERROR
        )
        return False

    domain_db_name = datamodel.GetCurrentDomainInfo().get('domainDbName', '')
    pluginfw.AddLog('Current Domain DB Name: {}'.format(domain_db_name), pluginfw.INFO)

    try:
        api_server = ApiServer(domain_db_name, api_server_name)
    except RuntimeError as e:
        pluginfw.AddLog(str(e), pluginfw.ERROR)
        return False

    if configured_subnets:
        subnets = configured_subnets
        pluginfw.AddLog('Using {} explicitly configured subnet(s).'.format(len(subnets)), pluginfw.INFO)
    else:
        subnets = get_infoblox_subnets(api_server, wapi_version)
        pluginfw.AddLog('Discovered {} subnet(s) from Infoblox.'.format(len(subnets)), pluginfw.INFO)

    if not subnets:
        pluginfw.AddLog('No Infoblox subnets to reconcile. Exiting.', pluginfw.WARNING)
        return False

    allowed_device_names = None
    if site_path:
        allowed_device_names = get_site_scoped_device_names(site_path, include_child_sites)
        pluginfw.AddLog(
            'Scoping NetBrain comparison to {} device(s) under site "{}".'.format(len(allowed_device_names), site_path),
            pluginfw.INFO
        )

    if precise_to_ip:
        infoblox_used_by_subnet = {}
        for subnet in subnets:
            infoblox_used_by_subnet[subnet] = get_used_ips_for_subnet(api_server, wapi_version, network_view, max_results, subnet)

        all_rows = []
        action_counts = {'No action': 0, 'Discover IP in NetBrain': 0, 'Register IP in Infoblox': 0}
        for subnet in subnets:
            infoblox_used_ips = infoblox_used_by_subnet.get(subnet, set())
            netbrain_ips, netbrain_descrs = get_netbrain_subnet_data(subnet, allowed_device_names)
            # GetSubnetIpInterfacesBySubnets can miss addresses it should have found (it's a
            # "duplicate IP" API keyed on Zone grouping) - cross-check every Infoblox-used IP
            # directly so a known-but-missed device doesn't get misreported as "not in NetBrain".
            for ip in infoblox_used_ips - netbrain_ips:
                if is_ip_known_in_netbrain(ip, allowed_device_names):
                    netbrain_ips.add(ip)
            description_netbrain = '; '.join(netbrain_descrs)
            rows = reconcile_subnet(subnet, infoblox_used_ips, netbrain_ips)
            rows = [row + [description_netbrain] for row in rows]
            all_rows.extend(rows)
            for row in rows:
                action_counts[row[5]] = action_counts.get(row[5], 0) + 1

        csv_content = build_ip_csv(all_rows)
        summary = (
            'Reconciliation complete across {} subnet(s): {} IP row(s) total - {} consistent, {} to discover in '
            'NetBrain, {} to register in Infoblox.'.format(
                len(subnets), len(all_rows), action_counts['No action'], action_counts['Discover IP in NetBrain'],
                action_counts['Register IP in Infoblox']
            )
        )
    else:
        all_rows = []
        action_counts = {'No action': 0, 'Discover Subnet in NetBrain': 0, 'Register Subnet in Infoblox': 0}
        for subnet in subnets:
            in_infoblox, comment_infoblox = get_infoblox_network_info(api_server, network_view, subnet)
            netbrain_ips, netbrain_descrs = get_netbrain_subnet_data(subnet, allowed_device_names)
            in_netbrain = bool(netbrain_ips)
            description_netbrain = '; '.join(netbrain_descrs)
            row = reconcile_subnet_level(subnet, in_infoblox, in_netbrain)
            action_counts[row[4]] = action_counts.get(row[4], 0) + 1
            row.extend([comment_infoblox, description_netbrain])
            all_rows.append(row)

        csv_content = build_subnet_csv(all_rows)
        summary = (
            'Reconciliation complete (subnet-level) across {} subnet(s): {} consistent, {} to discover in '
            'NetBrain, {} to register in Infoblox.'.format(
                len(subnets), action_counts['No action'], action_counts['Discover Subnet in NetBrain'],
                action_counts['Register Subnet in Infoblox']
            )
        )

    time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_name = '{}_{}.csv'.format(REPORT_NAME_PREFIX, time_str)
    result = certification.export_certification_report(report_name, csv_content, export_path=REPORT_EXPORT_PATH)

    if not result.success:
        pluginfw.AddLog('Failed to export report "{}": {}'.format(report_name, result.error), pluginfw.ERROR)
        return False

    pluginfw.AddLog(
        '{} Report saved to "Public/{}/{}".'.format(summary, REPORT_EXPORT_PATH, report_name),
        pluginfw.INFO
    )
    return True
