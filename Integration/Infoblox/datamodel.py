import re
import uuid
import json
from datetime import datetime, timezone, timedelta
from netbrain.sysapi import tunesettingutil, nbpymongo
from netbrain.utils import nbjson
from .protocol import DataModelApiResult

try:
    import PyDataModel
    from netbrain.sysapi import pluginfw
except:
    import traceback

    str_stack = traceback.format_exc()
    print("Failed to import 'PyDataModel':" + str_stack)


# Get tech spec node data
# @Get tech spec node data
def QueryNodeObjects(nbpath_schema, query):
    str_value = nbjson.dumps(query)
    strObj = PyDataModel.GetGDRData(nbpath_schema, str_value)
    if strObj:
        return nbjson.loads(strObj)
    else:
        return None


## query device object
#   @warning The func will return all object when query is empty.
#   @param query query condition
#   @return query result
def QueryDeviceObjects(query):
    str_value = nbjson.dumps(query)
    strObj = PyDataModel.QueryDeviceObjects(str_value)
    if strObj:
        return nbjson.loads(strObj)
    else:
        return None


## query device id list by query
# @warning The func will return all device id when query is empty.
# @param query condition
# @return device id list
def QueryDeviceIds(query):
    str_value = nbjson.dumps(query)
    strObj = PyDataModel.QueryDeviceIds(str_value)
    if strObj:
        return nbjson.loads(strObj)
    else:
        return None


## query device id list by device name
# @param devNames device names
# @return device id list
def GetDevIdsByNames(devNames):
    str_value = nbjson.dumps(devNames)
    strObj = PyDataModel.GetDevIdsByNames(str_value)
    if strObj:
        return nbjson.loads(strObj)
    else:
        return None


## set device object
# @warning The func will update the whole device object.
# @param device
# @param deviceObj  Full device object
# @par example
# @code:
#    device_name = "cisco route"
#    device_obj = GetDeviceObject(device_name)
#    device_obj["descr"] = "cisco route"
#    SetDeviceObject(device_name, device_obj)
# @endcode
def SetDeviceObject(device, deviceObj):
    strDevObj = nbjson.dumps(deviceObj)
    return PyDataModel.SetDeviceObject(device, strDevObj)


# Add device object
# @param deviceObj device object
def AddDeviceObject(deviceObj):
    strDevObj = nbjson.dumps(deviceObj)
    return PyDataModel.AddDeviceObject(strDevObj)


## Get device object by device name
# @param device device name
# @return device object
# @par example
# @code:
#    device_name = "cisco route"
#    device_obj = GetDeviceObject(device_name)
#    device_obj["descr"] = "cisco route"
#    SetDeviceObject(device_name, device_obj)
# @endcode
def GetDeviceObject(device):
    jsDevObj = PyDataModel.GetDeviceObject(device)
    if jsDevObj:
        return nbjson.loads(jsDevObj)
    else:
        return None


## Get device object by device id
# @param devId device identify
# @return device object
# @par example
# @code:
#    devId = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
#    device_obj = GetDeviceObjectById(devId)
#    device_obj["descr"] = "cisco route"
#    SetDeviceObject(device_obj["name"], device_obj)
# @endcode
def GetDeviceObjectById(devId):
    jsDevObj = PyDataModel.GetDeviceObjectById(devId)
    if jsDevObj:
        return nbjson.loads(jsDevObj)
    else:
        return None


## Get device name by IP(interface ips.ip)
# @attention The ip may be used for multi interface, but only return one
# @param strIp interface ip
# @return device name
def GetDeviceNameFromIp(strIp):
    devName = PyDataModel.GetDeviceNameFromIp(strIp)
    return devName


## Set a value for a specified property of a device.
# @param property_name (string) property name — the name of the specified device property, such as software version.
# @param device_name (string) device name — the hostname of the specified device.
# @param value the value of the property.
# @return true or false
def SetDeviceProperty(property_name, device_name, value):
    property_name = str(property_name)
    device_name = str(device_name)
    str_value = nbjson.dumps({"value": value})
    return PyDataModel.SetDeviceAttribute(device_name, property_name, str_value)


## Return the value of a specified device property.
# @param property_name (string) property name — the name of the specified device property, such as software version.
# @param device_name (string) device name — the hostname of the specified device.
# @return property value. 
# @return This func will return None, if dict or list is empty.
def GetDeviceProperty(property_name, device_name):
    property_name = str(property_name)
    device_name = str(device_name)
    str_value = PyDataModel.GetDeviceAttribute(device_name, property_name)
    # ENG-92923
    json_value = None
    if str_value:
        json_value = nbjson.loads(str_value)

    if json_value == None:
        return None
    str_value = json_value["value"]

    return str_value


## Get interface id list by intf type
#   @warning The func will return all interface id when query is empty.
# @param query (dic) query condition
# @param intf_type (string) interface type
#       - "intfs"
#       - "ipIntfs"
#       - "ip6Intfs"
#       - "greVpnIntfs"
#       - "ipsecVpnIntfs"
# @return interface id list
# @retval [{"interface id":"111", "interface type":""}, {XXX}, {XXX} ]
def QueryInterfaceIds(query, intf_type):
    str_value = nbjson.dumps(query)
    result = PyDataModel.QueryInterfaceIds(str_value, intf_type)
    if result:
        return nbjson.loads(result)
    else:
        return None


## Get interface id list by intf type
#   @warning The func will return all interface object when query is empty.
# @param query (dic) query condition
# @param intf_type (string) interface type
#       - "intfs"
#       - "ipIntfs"
#       - "ip6Intfs"
#       - "greVpnIntfs"
#       - "ipsecVpnIntfs"
# @return interface object list
# @retval [{Intf object 1},{Intf object 2}, .....]
def QueryInterfaceObjects(query, intf_type):
    str_value = nbjson.dumps(query)
    result = PyDataModel.QueryInterfaceObjects(str_value, intf_type)
    if result:
        return nbjson.loads(result)
    else:
        return None


## Set interface object
#   @warning The func will update the whole interface object.
# @param device (string) the device name
# @param intf_name (string) the interface name
# @param intf_type (string) the interface types. The interface type includes:
#       - intfs — physical interface.
#       - ipIntfs — IPv4 Interface.
#       - ip6Intfs — IPv6 interface.
#       - greVpnIntfs — GRE VPN interface.
#       - ipsecVpnIntfs — IPsec VPN interface.
# @param intf_object (dic) interface object
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return true or false
def SetInterfaceObject(device, intf_name, intf_type, intf_object, get_new=False):
    strIntObject = nbjson.dumps(intf_object)
    return PyDataModel.SetInterfaceObject(device, intf_name, intf_type, strIntObject, get_new)


## Get interface object by device name, interface name
# @param device (string) the device name
# @param intf_name (string) the interface name
# @param intf_type (string) the interface types. The interface type includes:
#       - intfs — physical interface.
#       - ipIntfs — IPv4 Interface.
#       - ip6Intfs — IPv6 interface.
#       - greVpnIntfs — GRE VPN interface.
#       - ipsecVpnIntfs — IPsec VPN interface.
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return interface object dic
def GetInterfaceObject(device, intf_name, intf_type, get_new=False):
    strObject = PyDataModel.GetInterfaceObject(device, intf_name, intf_type, get_new)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get interface object by interface id
# @param intf_id (string) the interface id
# @param intf_type (string) the interface type
#       - intfs — physical interface.
#       - ipIntfs — IPv4 Interface.
#       - ip6Intfs — IPv6 interface.
#       - greVpnIntfs — GRE VPN interface.
#       - ipsecVpnIntfs — IPsec VPN interface.
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return interface object dic
def GetInterfaceObjectById(intf_id, intf_type, get_new=False):
    strObject = PyDataModel.GetInterfaceObjectById(intf_id, intf_type, get_new)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Return interface ids of a specified device. The returned data type is list.
# @param device (string) device_name — the device name.
# @param intf_type (string) interface type
#       "" \n
#       - "intfs"
#       - "ipIntfs"
#       - "ip6Intfs"
#       - "greVpnIntfs"
#       - "ipsecVpnIntfs"
# @note If intf_type is "", the func will return interface id of all interface type
# @return interface id list
# @retval [{"interface id":"111", "interface type":""}, {XXX}, {XXX} ]
def GetInterfaceIdsByDeviceName(device, intf_type):
    strObject = PyDataModel.GetInterfaceIdsByDeviceName(device, intf_type)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get interface id by device name, interface name, interface type
# @param device (string) device name
# @param phantom_interface_name (string) phantom_interface_name
# @param phantom_interface_type (string) interface type
#       - "intfs"
#       - "ipIntfs"
#       - "ip6Intfs"
#       - "greVpnIntfs"
#       - "ipsecVpnIntfs"
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return interface id
def GetDeviceInterfaceId(device, phantom_interface_name, phantom_interface_type, get_new=False):
    if not isinstance(phantom_interface_name, str):
        raise TypeError('invalid type: \'%s\', phantom_interface_name must be str' % type(
            phantom_interface_name).__name__)
    if not isinstance(phantom_interface_type, str):
        raise TypeError('invalid type: \'%s\', phantom_interface_type must be str' % type(
            phantom_interface_type).__name__)
    if len(phantom_interface_type) == 0:
        raise ValueError('phantom_interface_type can not be empty')

    if phantom_interface_name:
        return PyDataModel.GetDeviceInterfaceId(device, phantom_interface_name, phantom_interface_type, get_new)
    return None


## Get phantom interface id by device name, interface name, interface type
# @param device (string) device name
# @param device_interface_name (string) device_interface_name
# @param phantom_interface_type (string) interface type
#       - intfs — physical interface.
#       - ipIntfs — IPv4 Interface.
#       - ip6Intfs — IPv6 interface.
#       - greVpnIntfs — GRE VPN interface.
#       - ipsecVpnIntfs — IPsec VPN interface.
# @return interface id list
# @retval [{"interface id":"111", "interface type":""}, {XXX}, {XXX} ]
def GetPhantomInterfaceIds(device, device_interface_name, phantom_interface_type):
    if not isinstance(device_interface_name, str):
        raise TypeError('invalid type: \'%s\', device_interface_name must be str' % type(
            device_interface_name).__name__)
    if not isinstance(phantom_interface_type, str):
        raise TypeError('invalid type: \'%s\', phantom_interface_type must be str' % type(
            phantom_interface_type).__name__)
    if len(phantom_interface_type) == 0:
        raise ValueError('phantom_interface_type can not be empty')

    if device_interface_name:
        strIntfList = PyDataModel.GetPhantomInterfaceIds(
            device, device_interface_name, phantom_interface_type)
        if strIntfList:
            return nbjson.loads(strIntfList)
    return None


## Return all the interface ids that belong to a specified interface type. The returned data type is list.
# @param intf_type (string) interface type
#       - intfs — physical interface.
#       - ipIntfs — IPv4 Interface.
#       - ip6Intfs — IPv6 interface.
#       - greVpnIntfs — GRE VPN interface.
#       - ipsecVpnIntfs — IPsec VPN interface.
# @return all the interfaces
# @retval [{"interface id":"111", "interface type":""}, {XXX}, {XXX} ]
def GetInterfaceIdsByType(intf_type):
    strIntfList = PyDataModel.GetInterfaceIdsByType(intf_type)
    if strIntfList:
        return nbjson.loads(strIntfList)
    else:
        return None


## Set a value for a specified interface property of a device.
# @param property_name (string) property name — the name of the specified interface property, such as SW Rev.
# @param intf_type (string) interface type — the type of the interface. The interface type includes:
#  - intfs — physical interface.
#  - ipIntfs — IPv4 Interface.
#  - ip6Intfs — IPv6 interface.
#  - ipsecVpnIntfs — IPsec VPN interface.
#  - greVpnIntfs — GRE VPN interface.
# @param device (string) device name — the hostname of the specified device.
# @param intf_name (string) interface name — the name of the interface.
# @param value the value of the property.
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return true or false
def SetInterfaceProperty(property_name, device, intf_name, intf_type, value, get_new=False):
    property_name = str(property_name)
    intf_type = str(intf_type)
    device = str(device)
    intf_name = str(intf_name)
    str_value = nbjson.dumps({"value": value})
    return PyDataModel.SetInterfaceAttribute(property_name, intf_type, device, intf_name, str_value, get_new)


## Set a value for a specified interface property of a device by Id
# @param property_name (string) property name — the name of the specified interface property, such as SW Rev.
# @param intf_type (string) interface type — the type of the interface. The interface type includes:
#  - intfs — physical interface.
#  - ipIntfs — IPv4 Interface.
#  - ip6Intfs — IPv6 interface.
#  - ipsecVpnIntfs — IPsec VPN interface.
#  - greVpnIntfs — GRE VPN interface.
# @param intf_id (string) interface id - the id of the interface
# @param value the value of the property.
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return true or false
def SetInterfacePropertyById(property_name, intf_id, intf_type, value, get_new=False):
    property_name = str(property_name)
    intf_type = str(intf_type)
    intf_id = str(intf_id)
    str_value = nbjson.dumps({"value": value})
    return PyDataModel.SetInterfaceAttributeById(property_name, intf_type, intf_id, str_value, get_new)


## Return the value of a specified interface property of a device.
# @param property_name (string) property name — the name of the specified module property, such as SW Rev.
# @param intf_type (string) interface type — the type of the interface. The interface type includes:
#  - intfs — physical interface.
#  - ipIntfs — IPv4 Interface.
#  - ip6Intfs — IPv6 interface.
#  - ipsecVpnIntfs — IPsec VPN interface.
#  - greVpnIntfs — GRE VPN interface.
# @param device (string) device name — the hostname of the specified device.
# @param intf_name (string) interface name — the name of the interface.
# @return property value. 
# @return This func will return None, if dict or list is empty.
def GetInterfaceProperty(property_name, device, intf_name, intf_type):
    property_name = str(property_name)
    intf_type = str(intf_type)
    device = str(device)
    intf_name = str(intf_name)
    str_value = PyDataModel.GetInterfaceAttribute(
        property_name, intf_type, device, intf_name)
    # ENG-92923
    json_value = None
    if str_value:
        json_value = nbjson.loads(str_value)

    if json_value == None:
        return None
    str_value = json_value["value"]

    return str_value


## Add a phantom interface.
# @param device_name (string) device name — the device name.
# @param interface_name (string) interface name — the interface name.
# @param interface_type (string) interface type — the interface types. The interface type includes:
#  - intfs — physical interface.
#  - ipIntfs — IPv4 Interface.
#  - ip6Intfs — IPv6 interface.
#  - ipsecVpnIntfs — IPsec VPN interface.
#  - greVpnIntfs — GRE VPN interface.
# @param belongs_to_topology_type (string) belongs to topo type  — the topology type that the phantom interface belongs to. The topology type includes:
#  - "L2_Topo_Type" — Layer 2 topology.
#  - "L3_Topo_Type" — IPv4 Layer 3 topology.
#  - "Ipv6_L3_Topo_Type" — IPv6 L3 Topology.
#  - "Logical_Topo_Type" — Logical Topology. 
#  - "L3_VPN_Topo_Type" — L3 VPN Tunnel topology.
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return True or False
def AddPhantomInterface(device_name, interface_name, interface_type, belongs_to_topology_type, get_new=False):
    if not isinstance(interface_name, str):
        raise TypeError('invalid type: \'%s\', interface_name must be str' % type(
            interface_name).__name__)
    str_value = PyDataModel.AddPhantomInterface(
        str(device_name), interface_name, interface_type, belongs_to_topology_type, get_new)

    if str_value:
        return nbjson.loads(str_value)
    else:
        return None


## Remove phantom interface
# @param device_name (string) device name — the device name.
# @param interface_name (string) interface name — the interface name.
# @param interface_type (string) interface type — the interface types. The interface type includes:
#  - intfs — physical interface.
#  - ipIntfs — IPv4 Interface.
#  - ip6Intfs — IPv6 interface.
#  - ipsecVpnIntfs — IPsec VPN interface.
#  - greVpnIntfs — GRE VPN interface.
# @return True or False
def RemovePhantomInterface(device_name, interface_name, interface_type):
    if not isinstance(interface_name, str):
        raise TypeError('invalid type: \'%s\', interface_name must be str' % type(
            interface_name).__name__)
    return PyDataModel.RemovePhantomInterface(str(device_name), interface_name, interface_type)


## Update one interface of one device
# @param device_name (string) device name — the device name.
# @param interface_type (string) interface type — the interface types. The interface type includes:
#  - intfs — physical interface.
#  - ipIntfs — IPv4 Interface.
#  - ip6Intfs — IPv6 interface.
#  - ipsecVpnIntfs — IPsec VPN interface.
#  - greVpnIntfs — GRE VPN interface.
# @param interface_object (dic) interface value. ex:{Interface object1}
# @param get_new (bool) Whether to use new data(When the interface data is modified in your script, it needs to be set to true in order to obtain the updated data)
# @return True or False
def UpdateOnePhantomInterface(device_name, interface_type, interface_object, get_new=False):
    strIntf = nbjson.dumps(interface_object)
    return PyDataModel.UpdateOnePhantomInterface(device_name, interface_type, strIntf, get_new)


## Update all interface of one device
# @attention If interfaces_value is "[]", this func equal to ClearPhantomInterface @see ClearPhantomInterface
# @param device_name (string) device name
# @param interface_type (string) interface type
# @param interface_objects (list) interfaces value. ex:[{Interface object1}, {Interface object2}, ....]
# @return True or False
def UpdatePhantomInterfaces(device_name, interface_type, interface_objects):
    strIntfList = nbjson.dumps(interface_objects)
    return PyDataModel.UpdatePhantomInterfaces(device_name, interface_type, strIntfList)


## delete all the intf of the device
# @param device_name (string) device name
# @param interface_type (string) interface type
# @return True or False
def ClearPhantomInterface(device_name, interface_type):
    return PyDataModel.ClearPhantomInterface(device_name, interface_type)


## Return the short name of an interface according to the corresponding device type of the device and interface name.
# @param device_name (string) device name
# @param interface_name (string) interface name
# @return The short name of an interface
def GetInterfaceShortName(device_name, interface_name):
    if interface_name:
        return PyDataModel.IfNameFullToBkn(str(device_name), str(interface_name))
    else:
        return interface_name


## Return a complete interface name by looking up the interface name translation table according to the corresponding device type of the device and interface name.
# @param device_name (string) device name
# @param interface_name (string) interface name
# @return a complete interface name
def CompleteInterfaceName(device_name, interface_name):
    if interface_name:
        return PyDataModel.CompleteInterfaceName(str(device_name), str(interface_name))
    else:
        return interface_name


## update device's module object by module name.
# @param device_name (string) device name
# @param module_name (string) module name
# @param module_object (dic) module object
# @return True or False
def SetModuleObject(device_name, module_name, module_object):
    strObject = nbjson.dumps(module_object)
    return PyDataModel.SetModuleObject(device_name, module_name, strObject)


## get device's module object by module name.
# @param device_name (string) device name
# @param module_name (string) module name
# @return object (dic) module object
def GetModuleObject(device_name, module_name):
    strObject = PyDataModel.GetModuleObject(device_name, module_name)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Set a value for a specified module property of a device.
# @param property_name (string) property name — the name of the specified module property, such as SW Rev.
# @param device_name (string) device name — the hostname of the specified device.
# @param module_name (string) module name — the name of the module.
# @param value the value of the module property.
# @return true or false
def SetModuleProperty(property_name, device_name, module_name, value):
    property_name = str(property_name)
    device_name = str(device_name)
    module_name = str(module_name)
    str_value = nbjson.dumps({"value": value})
    return PyDataModel.SetModuleAttribute(property_name, device_name, module_name, str_value)


## Return the value of a specified module property.
# @param property_name (string) property name — the name of the specified module property, such as SW Rev.
# @param device_name (string) device name — the hostname of the specified device.
# @param module_name (string) module name — the name of the module.
# @return property value. \n This func will return None, if dict or list is empty.
def GetModuleProperty(property_name, device_name, module_name):
    property_name = str(property_name)
    device_name = str(device_name)
    module_name = str(module_name)
    str_value = PyDataModel.GetModuleAttribute(
        property_name, device_name, module_name)
    # ENG-92923
    json_value = None
    if str_value:
        json_value = nbjson.loads(str_value)

    if json_value == None:
        return None
    str_value = json_value["value"]

    return str_value


## get member interface ids Belong2Channel
# @param device (string) device name
# @param intf (string) interface name
# @return interface id list
# @retval [id1, id2, ...]
def GetMemberInterfaceIdsBelong2Channel(device, intf):
    strObject = PyDataModel.GetMemberInterfaceIdsBelong2Channel(device, intf)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


# MPLSCloud API
MPLS_DYNYMIC_FILTER_KEY = 'deviceFilter'
MPLS_CE_ACCESS_PNT_KEY = 'mpls_accessPnt'
MPLS_EXCLUDE_PNT_KEY = 'exclude_accessPnt'
CLOUD_STATIC_TYPE = 0


## set internet cloud object.
# @since v2.0(2019-02-14)
# @param cloud_name (string) internet cloud name
# @param value internet cloud object,ex.
# @return true or false
# @see SetDeviceObject
def SetInternetCloud(cloud_name, value):
    return SetDeviceObject(cloud_name, value)


## get internet cloud.
# @since v2.0(2019-02-14)
# @param cloud_name (string) internet cloud name
# @return (object) internet cloud json formatted object.
# @see GetDeviceObject
def GetInternetCloud(cloud_name):
    return GetDeviceObject(cloud_name)


## set internet cloud property.
# @since v2.0(2019-02-14)
# @param property_name (string) property name
# @param cloud_name (string) internet cloud name
# @param value
# @return true or false
# @see SetDeviceProperty
def SetInternetCloudProperty(property_name, cloud_name, value):
    return SetDeviceProperty(property_name, cloud_name, value)


## get internet cloud property.
# @since v2.0(2019-02-14)
# @param property_name (string) property name
# @param cloud_name (string) internet cloud name
# @return property value. \n This func will return None, if dict or list is empty.
# @see GetDeviceProperty
def GetInternetCloudProperty(property_name, cloud_name):
    return GetDeviceProperty(property_name, cloud_name)


def SetCloudStaticProperty(cloud_name, prop):
    if not isinstance(prop, dict):
        raise Exception('prop must be a dict')

    cloud_interface = prop['cloud_interface']
    data = GetDeviceProperty('cloud', cloud_name)
    props = nbjson.loads(data)
    exsist = False

    for i in range(len(props)):
        p = props[i]
        type = p['_proto_']['type']
        if type != CLOUD_STATIC_TYPE:
            continue

        if p['cloud_interface'] == cloud_interface:
            props[i] = prop
            exsist = True

    if not exsist:
        props.append(prop)

    new_data = nbjson.dumps(props)

    SetDeviceProperty('cloud', cloud_name, new_data)


def RemoveCloudStaticProperty(cloud_name, cloud_interface):
    data = GetDeviceProperty('cloud', cloud_name)
    props = nbjson.loads(data)

    new_props = []
    for i in range(len(props)):
        prop = props[i]
        type = prop['_proto_']['type']
        name = prop['cloud_interface']
        if type == CLOUD_STATIC_TYPE and name == cloud_interface:
            continue

        new_props.append(prop)

    new_data = nbjson.dumps(new_props)
    return SetDeviceProperty('cloud', cloud_name, new_data)


## set internet cloud interface list.
# if the interface name exsist,update the interface,else add new interface.
# @since v2.0(2019-02-14)
# @deprecated not supported after IEv8.02
# @param cloudName (string) internet cloud name
# @param boudaryInterfaceList (list of object) cloud boudary interfaces.
# @par example
# @code:
# intfs=[{
#   "belongToTopoType" : ["L3_Topo_Type"],
#   "name" : "Boundary1",
#   "remoteIntfs" : [{
#       "_id" : "9479aa3c-0648-47d0-ba6e-7e5bb30426b9",
#       "devId" : "5ab3aa49-69bd-438e-be58-ca8bb467d944",
#       "ip" : "172.24.253.12/32",
#       "name" : "Loopback1 172.24.253.12/32",
#       "physicalIntfId" : "5b1c4268-dc9a-4397-ab2b-33933b1a5ba5",
#       "type" : "ipIntfs"
#     }],
#   "shortName" : "Boundary1"
# },
# {
#   "belongToTopoType" : ["L3_Topo_Type"],
#   "name" : "Boundary2",
#   "remoteIntfs" : [{
#       "_id" : "05824a4c-8496-484f-901c-b07ba2528e43",
#       "devId" : "ebcfe2cb-0b7a-4f9a-8c79-dca3a0ce18ed",
#       "ip" : "10.100.100.1/23",
#       "name" : "Vlan100 10.100.100.1/23",
#       "physicalIntfId" : "96635454-b2a8-4b69-a417-a7c84b3f59fb",
#       "type" : "ipIntfs"
#     }],
#   "shortName" : "Boundary2"
# }]
# datamodel.SetInternetCloudIntfList("Internet1",intfs)
# @endcode
# @return True or False
# @see SetInterfaceObject
def SetInternetCloudIntfList(cloudName, boudaryInterfaceList):
    ret = True

    for intfObj in boudaryInterfaceList:
        if "name" not in intfObj:
            return False

    for intfObj in boudaryInterfaceList:
        intfName = intfObj["name"]
        remoteIntfs = intfObj["remoteIntfs"]
        for remoteIntf in remoteIntfs:
            physicalIntfId = remoteIntf["physicalIntfId"]

            devId = remoteIntf["devId"]
            ip = remoteIntf["ip"]
            dev = GetDeviceObjectById(devId)
            intf = GetInterfaceObjectById(physicalIntfId, "intfs")

            edgeName = dev['name']
            edgeIntf = intf['name']

            prop = {"_proto_": {"$mark": 2, "type": 0, "updatedKeys": []},
                    "cloud_interface": intfName, "edge_device": edgeName, "edge_interface": edgeIntf, "edge_ip": ip}

            SetCloudStaticProperty(cloudName, prop)

    return ret


# Remove internet cloud interface
# @since v2.1(2019-03-04)
# @deprecated not supported after IEv8.02
def RemoveInternetCloudInterface(cloudName, interfaceName):
    RemoveCloudStaticProperty(cloudName, interfaceName)
    return RemovePhantomInterface(cloudName, interfaceName, "intfs")


## delete all the intf of the internet cloud
# @since v2.1(2019-03-04)
# @param cloudName (string) internet cloud name
# @deprecated not supported after IEv8.02
def ClearInternetCloudIntfList(cloudName):
    raise Exception('Not support function after IEv8.02')


## get internet cloud interface list.
# @since v2.0(2019-02-14)
# @param cloudName (string) internet cloud name
# @return all interfaces of internet cloud
# @see QueryInterfaceObjects
def GetInternetCloudIntfList(cloudName):
    intfsRet = GetInterfaceIdsByDeviceName(cloudName, "intfs")
    if not intfsRet:
        return None
    intfsIds = [obj["interface id"] for obj in intfsRet]

    query = {"_id": {"$in": intfsIds}}
    return QueryInterfaceObjects(query, "intfs")


## set mpls cloud property.
# @since v2.0(2019-02-14)
# @param propertyName (string) property name
# @param cloudName (string) mpls cloud name
# @param value
# @return true or false
# @see SetDeviceProperty
def SetMPLSCloudProperty(propertyName, cloudName, value):
    return SetDeviceProperty(propertyName, cloudName, value)


## get mpls cloud property.
# @since v2.0(2019-02-14)
# @param propertyName (string) property name
# @param cloudName (string) internet cloud name
# @return property value. \n This func will return None, if dict or list is empty.
# @see GetDeviceProperty
def GetMPLSCloudProperty(propertyName, cloudName):
    return GetDeviceProperty(propertyName, cloudName)


## set MPLS cloud datas.
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @param CEList (list of object) all CE list, include static CE and dynamic CE.
# @param dynamicCondition (object) dynamic CE filters.
# @param excludeCEList (list of object) exclucde CE list, devices or interfaces
# @par example
# @code:
# CEList=[{
#   "ip" : "172.24.14.6/24",
#   "ceNbrs" : [{
#       "asNum" : 65535,
#       "ceIfVpn" : "",
#       "descr" : "Static",
#       "devId" : "5ab3aa49-69bd-438e-be58-ca8bb467d944",
#       "ceName" : "BJ-R3",
#       "flag" : 0,
#       "ifname" : "d367d36d-852d-4d6c-8455-a1ece3a5c6a8",
#       "peIp" : "172.24.14.6/24",
#       "ip" : "172.24.14.6/24",
#       "ceIntfIP" : "172.24.14.4/24",
#       "ceIntfName" : "FastEthernet0/1",
#       "routingProtocol" : "",
#       "groupType" : "Static",
#       "ceVpn" : "55",
#       "mplsId" : "4b8aa1e9-1ad1-7ba5-7692-89484eef26c0"
#     }]
# }]
# dynamicCondition = {
#     "RangeOption" : 0,
#     "DeviceGroupRange" : [],
#     "SiteRange" : [],
#     "Filter" : {
#       "Conditions" : [{
#           "Schema" : "name",
#           "Operator" : 4,
#           "Expression" : "aaa"
#         }, {
#           "Schema" : "intfs.name",
#           "Operator" : 4,
#           "Expression" : "rrr"
#         }, {
#           "Schema" : "intfs.speed",
#           "Operator" : 0,
#           "Expression" : "1"
#         }],
#       "Expression" : "A and B and C"
#     }
# }
# excludeCEList=[{
#   "ip" : "172.24.14.31/24",
#   "ceNbrs" : [{
#       "asNum" : 65535,
#       "ceIfVpn" : "",
#       "descr" : "",
#       "devId" : "b987b3e5-3689-4408-bf1a-69d77f2fd341",
#       "ceName" : "BJ-R2",
#       "flag" : 2,
#       "ifname" : "26170cb8-2912-4155-b550-b15b4af65e8b",
#       "peIp" : "172.24.14.31/24",
#       "ip" : "172.24.14.31/24",
#       "ceIntfIP" : "172.24.14.3/24",
#       "ceIntfName" : "FastEthernet0/1",
#       "routingProtocol" : "ISIS L1/L2",
#       "ceVpn" : "1",
#       "groupType" : "Excluded"
#     }]
# }]
# ret = datamodel.SetMPLSCloud("Mpls2",CEList,dynamicCondition,excludeCEList)
# @endcode


def SetMPLSCloud(cloudName, CEList, dynamicCondition, excludeCEList):
    raise Exception('Not support function after IEv8.02')


## get the MPLS cloud define.
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @return (object) MPLS Object
def GetMPLSCloud(cloudName):
    return GetDeviceObject(cloudName)


def _addCeNbr2AccessPnt(ceNbrObj, accessPnt):
    peIp = ceNbrObj["peIp"]
    pePnt = None
    for pnt in accessPnt:
        ip = pnt["ip"]
        if ip == peIp:
            pePnt = pnt
            break

    if pePnt == None:
        pePnt = {
            "ip": peIp,
            "ceNbrs": [
                ceNbrObj
            ]
        }
        accessPnt.append(pePnt)
    else:
        ceNbrs = pePnt["ceNbrs"]
        isFind = False
        for index in range(len(ceNbrs)):
            ceNbr = ceNbrs[index]
            if (ceNbr["devId"] == ceNbrObj["devId"] and ceNbr["ifname"] == ceNbrObj["ifname"]):
                ceNbrs[index] = ceNbrObj
                isFind = True
                break

        if isFind == False:
            ceNbrs.append(ceNbrObj)


## add or update Mpls CE .
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @param ceNbrObjs (list) mpls CE object.
# @param flag (int) 0:static CE,1:dyncmic CE,2:exclude CE.
# ceNbrObjs example:
# @code
# [{
#     'asNum': 65535,
#     'ceIfVpn': '',
#     'ceIntfIP': '172.24.14.4/24',
#     'ceIntfName': 'FastEthernet0/1',
#     'ceName': 'BJ-R3',
#     'ceVpn': '55',
#     'descr': 'Static',
#     'devId': '5ab3aa49-69bd-438e-be58-ca8bb467d944',
#     'flag': 0,
#     'groupType': 'Static',
#     'ifname': 'd367d36d-852d-4d6c-8455-a1ece3a5c6a8',
#     'ip': '172.24.14.6/24',
#     'mplsId': '4b8aa1e9-1ad1-7ba5-7692-89484eef26c0',
#     'peIp': '172.24.14.6/24',
#     'routingProtocol': ''
# }]
# @endcode
def SetMPLSCloudCEObjects(cloudName, ceNbrObjs, flag):
    raise Exception('Not support function after IEv8.02')


# @warning func unrealized
def SetMPLSCloudStaticCE(cloudName, iPofPEinterface, cEDevice, cEInterface, VRF, routingProtocol, VPN):
    raise Exception('Not support function after IEv8.02')


## get the static CE list of MPLS cloud.
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @param ceName (string) ce device name,default is None,get all the static CE from MPLS Cloud
# @param ceIntfName (string) ce interface name,default is None,get all the static CE interface from MPLS Cloud
# @return (list of object) all the CE list.
# ex.
# @code
# ceNbrs=datamodel.GetMPLSCloudStaticCE("Mpls2",'d367d36d-852d-4d6c-8455-a1ece3a5c6a8')
# return example:
# [{
#     'asNum': 65535,
#     'ceIfVpn': '',
#     'ceIntfIP': '172.24.14.4/24',
#     'ceIntfName': 'FastEthernet0/1',
#     'ceName': 'BJ-R3',
#     'ceVpn': '55',
#     'descr': 'Static',
#     'devId': '5ab3aa49-69bd-438e-be58-ca8bb467d944',
#     'flag': 0,
#     'groupType': 'Static',
#     'ifname': 'd367d36d-852d-4d6c-8455-a1ece3a5c6a8',
#     'ip': '172.24.14.6/24',
#     'mplsId': '4b8aa1e9-1ad1-7ba5-7692-89484eef26c0',
#     'peIp': '172.24.14.6/24',
#     'routingProtocol': ''
# }]
# @endcode
def GetMPLSCloudStaticCEList(cloudName, ceName=None, ceIntfName=None):
    raise Exception('Not support function after IEv8.02')


## set the dynamic CE filter.
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @param filterCondition (object) dynamic CE filter object
# @return (bool) True if success
# ex.
# @code
# filterCondition={
#   "DeviceGroupRange" : [],
#   "Filter" : {
#     "Conditions" : [{
#         "Expression" : "R",
#         "Operator" : 4,
#         "Schema" : "name"
#       }, {
#         "Expression" : "10.25",
#         "Operator" : 1,
#         "Schema" : "mgmtIP"
#       }],
#     "Expression" : "A or B"
#   },
#   "RangeOption" : 0,
#   "SiteRange" : []
# }
# ret =  datamodel.SetMPLSCloudDynamicFilter("Mpls2",filter)
# @endcode
def SetMPLSCloudDynamicFilter(cloudName, filterCondition):
    return SetMPLSCloudProperty(MPLS_DYNYMIC_FILTER_KEY, cloudName, filterCondition)


## get the dynamic CE list of MPLS cloud.
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @param ceName (string) ce device name,default is None,get all the dynamic CE from MPLS Cloud
# @param ceIntfName (string) ce interface name,default is None,get all the dynamic CE interface from MPLS Cloud
# @return (list of object) all the CE list.
# ex.
# @code
# ceNbrs=datamodel.GetMPLSCloudStaticCE("Mpls2",'d367d36d-852d-4d6c-8455-a1ece3a5c6a8')
# return example:
# [{
#     'asNum': 65535,
#     'ceIfVpn': '',
#     'ceIntfIP': '172.24.14.4/24',
#     'ceIntfName': 'FastEthernet0/1',
#     'ceName': 'BJ-R3',
#     'ceVpn': '55',
#     'descr': 'Static',
#     'devId': '5ab3aa49-69bd-438e-be58-ca8bb467d944',
#     'flag': 1,
#     'groupType': 'Dynamic',
#     'ifname': 'd367d36d-852d-4d6c-8455-a1ece3a5c6a8',
#     'ip': '172.24.14.6/24',
#     'mplsId': '4b8aa1e9-1ad1-7ba5-7692-89484eef26c0',
#     'peIp': '172.24.14.6/24',
#     'routingProtocol': ''
# }]
# @endcode
def GetMPLSCloudDynamicCEList(cloudName, ceName=None, ceIntfName=None):
    raise Exception('Not support function after IEv8.02')


## add or update Mpls Excluce CE List.
# @since v2.0(2019-02-14)
# @param cloudName (string) mpls cloud name
# @param CEList (list) mpls exclude CE object list.
# CEList example:
# @code
# [{
#   "asNum" : 65535,
#   "ceIfVpn" : "",
#   "ceIntfIP" : "10.10.7.254/22",
#   "ceIntfName" : "Vlan20",
#   "ceName" : "sw-4500-15",
#   "ceVpn" : "3",
#   "descr" : "",
#   "devId" : "ebcfe2cb-0b7a-4f9a-8c79-dca3a0ce18ed",
#   "flag" : 2,
#   "groupType" : "Excluded",
#   "ifname" : "dddf9a2e-a648-4c53-a625-f590ef76068c",
#   "ip" : "10.10.7.242/22",
#   "peIp" : "10.10.7.242/22",
#   "routingProtocol" : ""
# }]
# @endcode
def SetMPLSCloudExcludeCEList(cloudName, CEList):
    raise Exception('Not support function after IEv8.02')


# @warning func unrealized
def GetMPLSCloudExcludeCEList(cloudName, ceName=None, ceIntfName=None):
    raise Exception('Not support function after IEv8.02')


# @warning func unrealized
def DeleteMPLSCloud(cloudName):
    return DeleteDevices([cloudName])


## get mac device by mac
# @param mac mac
# @return mac device list
def GetMacDevicesByMac(mac):
    strDeviceList = PyDataModel.GetMacDevicesByMac(mac)
    if strDeviceList:
        return nbjson.loads(strDeviceList)
    else:
        return None


## delete mac device by mac
# @param mac mac
# @return True or False
def DeleteMacDeviceByMac(mac):
    return PyDataModel.DeleteMacDeviceByMac(mac)


## delete mac device by id
# @param id (string) id
# @return True or False
def DeleteMacDeviceById(id):
    return PyDataModel.DeleteMacDeviceById(id)


## get schema type by schema name
# @param schema_name (string) schema name
# @return schema type - may be:
#  - "int"
#  - "int64"
#  - "double"
#  - "bool"
#  - "string"
#  - "list"
#  - "object"
#  - "time"
#  - "ipv4"
#  - "ipv6"
#  - "mac"
#  - "url"
#  - "file"
def GetSchemaType(schema_name):
    return PyDataModel.GetSchemaType(schema_name)


## Network settings APIs - SetDeviceCredential
# @brief Set the login credentials for a device.
# @param device_name deivce name — the hostname of the device.
# @param username user name — the username to log in to the device.
# @param password password — the password to log in to the device.
# @param privilege_username privilege_username — the username to enter the privileged mode of the device.
# @param privilege_password privilege_password — the password to enter the privileged mode of the device.
# @param access_mode access mode — the access mode, such as Telnet, SSH.
#  - 0,  -- telnet
#  - 1,  -- SSH
#  - 2,  -- SSHv2
# @param port port — the port of the access mode, such as 23.
#  -     port if 0 not change
#  -     If not find deivce setting by device name, will return False.
def SetDeviceCredential(device_name, username, password, privilege_username, privilege_password, access_mode=0, port=0):
    return PyDataModel.SetDeviceCredential(device_name, username, password, privilege_username, privilege_password,
                                           access_mode, port)


## Network settings APIs - GetProxyServerStatus
# @param fsId fsId
# @return True or False
# @return If return False, may be: 
#  - 1.Can not find Front Server by fsId. 
#  - 2.Failed to connect Front Server Controller.
def GetProxyServerStatus(fsId):
    return PyDataModel.GetProxyServerStatus(fsId)


## Network settings APIs - SetProxyServerOfDevice
# @param device_name device name
# @param fsId fsId
# @return True or False
#       If return False, may be: \n
#       1. Can not find device setting by device name. \n
#       2. device is locked. \n
#       3. Can not find server by fsId.
def SetProxyServerOfDevice(device_name, fsId):
    return PyDataModel.SetProxyServerOfDevice(device_name, fsId)


## Get device setting
# @param device name (string)
# @return device setting (dict)
# @retval example:
# @code
# {
#     'ApplianceId': 'fs36',
#     'CliSetting': {
#         'AccessMethod': 1,
#         'LoginScript': {
#             'UseLoginScript': False
#         },
#         'SSHKeyId': '',
#         'SSHPort': 22,
#         'TelnetPort': 23,
#         'TelnetProxyId': '',
#         'TelnetProxyIdForSmartCLI': ''
#     },
#     'CpuExpression': '',
#     'DependOn': None,
#     'DriverId': 'b2d313fe-43e6-4d5f-9189-b3af6b71a83a',
#     'Extension': None,
#     'ExternalServers': None,
#     'HostName': 'xxxx',
#     'LiveHostName': 'xxxx',
#     'LiveStatus': 1,
#     'Locked': False,
#     'ManageIp': 'xx.xx.xx.xx',
#     'ManageIpInt': 2887256578,
#     'MemoryExpression': '',
#     'Mode': 0,
#     'SNMPSetting': {
#         'snmpPort': 161,
#         'snmpVersion': 2,
#         'v3': {
#             'authMode': 0,
#             'authPro': 0,
#             'contextName': '',
#             'encryptPro': 0
#         }
#     },
#     'SubType': 2,
#     'Version': 420,
# }
# @endcode
def GetDeviceSetting(device):
    strDeviceSetting = PyDataModel.GetDeviceSetting(device)
    if strDeviceSetting:
        return nbjson.loads(strDeviceSetting)
    else:
        return None


## Set device setting
# @param device_setting_object device setting object
# @return True or False
def SetDeviceSetting(device_setting_object):
    strDeviceSetting = nbjson.dumps(device_setting_object)
    return PyDataModel.SetDeviceSetting(strDeviceSetting)


## get all phantom interface types
# @return interface types
# @retval ["ipIntfs", "ip6Intfs", "greVpnIntfs", "ipsecVpnIntfs"]
def GetAllPhantomInterfaceTypes():
    strObject = PyDataModel.GetAllPhantomInterfaceTypes()
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## 	Return the vendor information about a device by MAC address.
# @param mac (string) mac — the MAC address of the device.
# @return vendor string
def FindVendorByMAC(mac):
    return PyDataModel.FindVendorbyMAC(mac)


## get vendor model
# @param sysoid (string) oid
# @return [vendorName(string), modelName(string), deviceType(int)]
def GetVendorModel(sysoid):
    strObject = PyDataModel.GetVendorModel(sysoid)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## get domain info
# @return domain info (dict) {domainDbName:string, domainId:string, tenantDbName:string,tenantId:string}
# @code
# {
#     'domainDbName': 'L2Topology',
#     'domainId': '41b1067e-80f4-49ac-838a-266d9cf81651',
#     'tenantDbName': 'Topology',
#     'tenantId': '1cfb3437-f948-c751-75e7-8a3f063b7a92'
# }
# @endcode
def GetCurrentDomainInfo():
    strObject = PyDataModel.GetCurrentDomainInfo()
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## get mac info
# @param filter_list (dic) - \n
#       {"device1":["mac1", "mac2", ...], "device2":[], ....}
# @return mac info list
# @return [["host name", "port name", "vlan name", "address"], [...], ...]
def GetDeviceMACInfo(filter_list):
    strList = nbjson.dumps(filter_list)
    strObject = PyDataModel.GetDeviceMacInfo(strList)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Return the name of the site that contains the specified device.
# @param device (string) device name — the device name.
# @return site name (string)
def GetDeviceSiteName(device):
    return PyDataModel.GetDeviceSiteName(device)


## 	Return the full path of the site that contains the specified device.
# @param device (string) device name — the device name.
# @return site full path (string)
def GetDeviceSiteFullPath(device):
    return PyDataModel.GetDeviceSiteFullPath(device)


## Return all device ids in a site. The returned object type is list.
# @param site_path (string) site full path — the full path of the site, such as "My Network\Site A".
# @param include_child (bool) include child — the value type is bool and the default value is false, which means that returned value does not include devices in the site's child sites.
#  - default : False
# @return device id list
# @return ["device id1", "device id2", ...]
def GetDeviceIdsFromSite(site_path, include_child=False):
    strObject = PyDataModel.GetDeviceIdsFromSite(site_path, include_child)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## add devices to site
# @param site_path (string) site full path
# @param device_ids (list) device id lists
# @return bool
# @return True or False
def AddDevicesToSite(site_path, device_ids):
    strDeviceIds = nbjson.dumps(device_ids)
    strResult = PyDataModel.AddDevicesToSite(site_path, strDeviceIds)
    result = DataModelApiResult()
    result.unpack(strResult)
    if not result.success:
        raise Exception(result.error)
    return result.success


# -- func unrealized
# @warning func unrealized
def RemoveDevicersFromSite(siteh_path, device_ids):
    raise ("To Do")


# -- func unrealized
# @warning func unrealized
def ClearDevicesInSite(siteh_path):
    raise ("To Do")


## Return the value of the specified site property.
# @param site_path (string) site path — the full path of the site, such as "My Network\Site A".
# @param property_name (string) property name — the name of the specified site property, such as Region.
# @return property value (string)
def GetSiteProperty(property_name, site_path):
    strResult = PyDataModel.GetSiteProperty(site_path, property_name)
    result = DataModelApiResult()
    result.unpack(strResult)
    if result.success:
        return result.value
    else:
        if len(result.error) <= 0:
            raise Exception('unknown error')
        else:
            raise Exception(result.error)
    return ''


## Set a value for the specified property of a site.
# @param site_path (string) site path — the full path of the site, such as "My Network\Site A".
# @param property_name (string) property name — the name of the specified site property, such as Region.
# @param value (string) property value — the value of the site property.
# @return True or False
def SetSiteProperty(property_name, site_path, value):
    strResult = PyDataModel.SetSiteProperty(site_path, property_name, value)
    result = DataModelApiResult()
    result.unpack(strResult)
    if not result.success:
        raise Exception(result.error)
    return result.success


## Get all site paths
# @par siteCategory
# @code:
# siteCategory:
#   RootSite = 0,
#   ContainerSite = 1,
#   LeafSite = 2,
#   UnassignedSite = 3,
#   ExcludedDeviceSite = 4,
# @endcode
# @return all site paths
# site path sample:
# site_info = {
#     "sitePath": "My Network\CHBS\WSJ-210-U2-14",
#     "siteName": "WSJ-210-U2-14",
#     "siteCategory": 2
# }
def GetAllSitePath(includeUnsigned = False):
    strObject = PyDataModel.GetAllSitePath(includeUnsigned)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


def CreateSite(
        strSiteName: str,
        strParentPath: str,
        strJsonFilter: str,
        isContainerSite: bool = False,
        strContainerSiteKey: str = "",
        bCreateParentContainer: bool = True,
        isAutoSite: bool = True,
        isNewTechSite: bool = True
) -> object:
    """
    Create new site.
    Validate parent path existence, create container site if requested.
    Validate naming for auto site and new-tech:
    1. If it's auto-site, then the site must be in "My Network/Auto Site/"
    2. If it's new-tech auto-site, then the parent path has to be "My Network/Auto Site/TechRootSchema". The new-tech container site's name has to be the same with new-tech root schema.
    Validate fields with logic below for accuracy and simplicity:
    1. filter.expression -- empty or not
    2. filter.condition:
        2.1 schema must be device schema, or special case "_config", "proxyServer", "ExternalServers.ExternalServerId"
        2.2 operator must be in valid range (0 - 13 currently)
    :param strSiteName: site name. Will update site name if site key matches (dynamic search filter)
    :param strParentPath: parent path
    :param strJsonFilter: JSON string of Site Dynamic search filter, serve as "site key" which uniquely identifies a site.
        Notes: filter??operator,criteria schema ?,??valid,??????????,????API????NetBrain engineer?????????????,??????????validation?
    :param isContainerSite: Whether it's container site or leaf site
    :param strContainerSiteKey: Only works for container site. Saved into Site.CustomerAttr.
        When strContainerSiteKey is set, we will find the existing container site by the parent path and container site key.
        Otherwise, we'll match by the container site's name.
    :param bCreateParentContainer: If true, create parent container sites if they do not exist, otherwise return false.
    :param isAutoSite: If true, parent path must start with "My Network/Auto Site/"
    :param isNewTechSite: Works only when it's Auto-site. If true, will check the parent container site name, which has to be the same with NewTech Root Schema
    :return: json string of {"error":"","success":true,"value":""}
    """
    return PyDataModel.CreateSite(
        strSiteName,
        strParentPath,
        strJsonFilter,
        isContainerSite,
        strContainerSiteKey,
        bCreateParentContainer,
        isAutoSite,
        isNewTechSite
    )


def DeleteSite(
        strSiteIdList: str,
        isDeleteParentSiteIfNoChild: bool = False
) -> object:
    """
    delete site by site id list
    :param strSiteIdList: site id list to delete
    :param isDeleteParentSiteIfNoChild: after delete this site, if there's NO son (leaf or container) of the parent site, then whether delete the parent site or not
    :return: json string of {"error":"","success":true,"value":""}
    """
    return PyDataModel.DeleteSite(strSiteIdList, isDeleteParentSiteIfNoChild)


def GetAvailableValuesBySchema(
        strSchema: str,
        strTechRootSchema: str = ""
) -> object:
    """
    Get all available values (equivalent to MongoDB $group) of the provided schema/schemaType.
    Ref to param description for available schemas.
    :param strSchema:
        Supported schema keys :
            1. specific DeviceSchema _id, e.g. "loc", "vendor", etc.
                a. returns json string of List<string>, e.g. [ val_1, val_2, val_3 ]
                b. notes: Only support Device Schema, not Interface/Module. There's NO use cases for now.
            2. "apiServer": returns json string of
                [
                    {
                        "id": "xxx",  # API Server GUID, to be used in Dynamic Search Condition
                        "serverType": "SDN",  # API Server Type -- SDN/ThirdPartyPlugin/CheckPointOPSEC
                        "serverTypeId": "9a072632-b2d4-4236-b39d-0f9036396a2a",  # the TechnologySpec id of this API server
                        "newTechSchema": "Azure",  # the API server's TechnologySpec root schema
                        "parentId": null,  # for AWS Role Base Account, dynamic create, parentId is main account
                        "name": "Azure API Server",  # API Server name
                        "description": "",
                        "ip": [  # difference for each new tech type, e.g. IP, host address, client id, etc.
                            "85e16b5d-fe6a-4bfb-b474-174a88413f10"
                        ],
                        "frontServerAndGroupId": "FS1",
                        "amFrontServerId": "FS1",
                        "extraParams": null,
                        "triggerName": null
                    }
                ]
            3. "frontServer": returns json string of
                [
                    {
                        "_id": "FS1",  # FS _id, to be used in Dynamic Search Condition
                        "ipOrHostname": "1.2.3.4",
                        "isFSG": false,
                        "fsIds": []  # fs ID list if it's an FSG
                    }
                ]
    :param strTechRootSchema:
        TechnologySpec Root Schema, e.g. AWS, ACI, GCP, etc. The techspec root schema can be found in UI "Tenant Management --> Platform Management --> specific_tech --> schema_tree_root".
        Effective for DeviceSchema and API server.
        Options:
            Will only get values of specific new-tech if passed-in specific root schema.
            Will get all if passed-in "".
    :return: json string of {"error":"","success":true,"value":""}
    """
    return PyDataModel.GetAvailableValuesBySchema(
        strSchema,
        strTechRootSchema
    )


def GetUnmatchedSiteByKey(
        strJsonSiteKeyList: str,
        strParentPath: str
) -> object:
    """
    Only works for Auto-site.
    Provide list of site keys (dynamic search filter), and the parent container site path.
    Return the child leaf sites of this parent path, whose site key does not match any of the param site key, which means, those auto sites are no-longer needed.
    Validate fields with logic below for accuracy and simplicity:
    1. filter.expression -- empty or not
    2. filter.condition:
        2.1 schema must be device schema, or special case "_config", "proxyServer", "ExternalServers.ExternalServerId"
        2.2 operator must be in valid range (0 - 13 currently)
    :param strJsonSiteKeyList:
        JSON string of a list of Dynamic Search Filter object. Sample:
        {
            "expression": "A and B",
            "conditions": [{
                "schema": "subType",
                "operator": 0,
                "expression": "30313;30314;30308;30303;30300;30310;30318;30319;30315;30317;30316;30307;30306;30312;1034;30305;30311;30304;30302",
                "escapeExpression": False,
                "expressionNames": None,
                "fieldType": 0
            }, {
                "schema": "loc",
                "operator": 0,
                "expression": "us-east",
                "escapeExpression": False,
                "expressionNames": None,
                "fieldType": 0
            }]
        }
    :param strParentPath: parent container site path to look for the leaf sites among its direct children
    :return: json string of {"error":"","success":true,"value":""}
        result['value'] is JSON string of list of Site objects which does NOT match any of the input site keys. e.g.
        [
            {
                "ID": "xxx",  // site ID
                "name": "ACI-site1",  // site name
                "isLockdownMember": false,
                "parentPath": [  // parent site IDs
                    "732e8ab6-6b69-417d-ad03-2cc447100166",
                    "cd9d28cc-694c-4b51-adc5-4def3a5a6d2d",
                    "a87c2dd1-9fd8-4593-9a9a-ecbe5888e962"
                ],
                "filter": {  // dynamic search filter
                    "Expression": "A",
                    "Conditions": [
                        {
                            "Schema": "ExternalServers.ExternalServerId",
                            "Operator": 0,
                            "Expression": "332014a6-38a9-44f3-b931-0838c9e714bf",
                            "EscapeExpression": false,
                            "invalid": false,
                            "FieldType": 0
                        }
                    ]
                },
                "employeeNumber": "0",
                "operateInfo": {
                    "opUserId": "275f95c3-5744-499d-9bd8-d0d3a16b8f36",
                    "opUser": "jweidebug",
                    "opTime": "2023-07-31T20:23:17.599Z"
                },
                "deviceCount": 61,  // devices in this site
                "siteCategory": 2,  // 0 -- RootSite, 1 -- ContainerSite, 2 -- LeafSite, 3 -- UnassignedSite, 4 -- ExcludedDeviceSite
                "description": "",
                "type": "",
                "parentId": "a87c2dd1-9fd8-4593-9a9a-ecbe5888e962",
                "orderIndex": 0
            }
        ]
    """
    return PyDataModel.GetUnmatchedSiteByKey(
        strJsonSiteKeyList,
        strParentPath
    )


## Create a device group.
# @param device_group_name (string) device group name  — the name of the device group.
# @param device_group_type (int) device group type — the type of the device group, such as Public.
# - Public = 0,
# - Private = 1
# @return True or False
def CreateDeviceGroup(device_group_name, device_group_type):
    return PyDataModel.CreateDeviceGroup(device_group_name, device_group_type)


## Add a device into a device group.
# @note If device group is private, this func need opUserID (only support qapp, path, sdn, plugin)
# @param device (string) device name — the device name.
# @param device_group_name (string) device group name — the name of the device group.
# @param isStatic (bool) isStatic - whether it is static
# @param deviceGroupType (int) device group type (default 0) — the type of the device group, such as Public.
# - Public = 0,
# - Private = 1
# @return True or False
def AddDeviceToDeviceGroup(device, device_group_name, isStatic=True, deviceGroupType=0):
    return PyDataModel.AddDeviceToDeviceGroup(device, device_group_name, isStatic, deviceGroupType)


## Add devices into a device group.
# @note If device group is private, this func need opUserID (only support qapp, path, sdn, plugin)
# @param devices (list) devices name - — device name list.
# @param device_group_name (string) device group name — the name of the device group.
# @param isStatic (bool) isStatic - whether it is static
# @param deviceGroupType (int) device group type (default 0) — the type of the device group, such as Public.
# - Public = 0,
# - Private = 1
# @return True or False
def AddDevicesToDeviceGroup(devices, device_group_name, isStatic=True, deviceGroupType=0):
    strDeviceList = nbjson.dumps(devices)
    return PyDataModel.AddDevicesToDeviceGroup(strDeviceList, device_group_name, isStatic, deviceGroupType)


## Remove a device from a device group.
# @note If device group is private, this func need opUserID (only support qapp, path, sdn, plugin)
# @param device (string) device name — the device name.
# @param device_group_name (string) device group name  — the name of the device group.
# @param deviceGroupType (int) device group type (default 0) — the type of the device group, such as Public.
# - Public = 0,
# - Private = 1
# @return True or False
def RemoveDeviceFromDeviceGroup(device, device_group_name, deviceGroupType=0):
    return PyDataModel.RemoveDeviceFromDeviceGroup(device, device_group_name, deviceGroupType)


## Clear devices in a device group.
# @note If device group is private, this func need opUserID (only support qapp, path, sdn, plugin)
# @param device_group_name (string) device group name — the name of the device group.
# @param deviceGroupType (int) device group type (default 0) — the type of the device group, such as Public.
# - Public = 0,
# - Private = 1
# @return True or False
def ClearDevicesInDeviceGroup(device_group_name, deviceGroupType=0):
    return PyDataModel.ClearDevicesInDeviceGroup(device_group_name, deviceGroupType)


## Return all device ids in a device group. The returned object type is list.
# @param device_group_name (string) device group name — the name of the device group.
# @param type (int) device group type(default -1) — the type of the device group, such as Public.
# - Public = 0,
# - Private = 1
# @return device id list
# @retval ["device id1", "device id2", ...]
def GetDeviceIdsFromDeviceGroup(device_group_name, type=-1):
    strObject = PyDataModel.GetDeviceIdsFromDeviceGroup(device_group_name, type)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None

## Return all device ids in a device group. The returned object type is list.
# @param deviceGroupId (string) device group Id
# - Public = 0,
# - Private = 1
# @return device id list
# @retval ["device id1", "device id2", ...]
def GetDeviceIdsFromDeviceGroupById(deviceGroupId):
    strObject = PyDataModel.GetDeviceIdsFromDeviceGroupById(deviceGroupId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get a device group by its full path.
# @param device_group_path (string) device group full path — such as "Shared Device Groups/Test".
# @return device group object (dict), or None if not found. Call GetLastError() for error detail.
# @par example
# @code:
#    dg = GetDeviceGroup("Shared Device Groups/Test")
# @endcode
def GetDeviceGroup(device_group_path):
    strObject = PyDataModel.GetDeviceGroup(device_group_path)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Add or update a device group by its full path.
# @param device_group_path (string) device group full path — such as "Shared Device Groups/Test".
# @param condition (dict) dynamic search filter object — the filter/range definition of the device group.
# @param device_group_name (string) device group name — the display name of the device group.
# @return True or False. Call GetLastError() for error detail when False.
# @par example
# @code:
#    condition = {
#        "Filter": {
#            "expression": "A",
#            "conditions": [
#                {"schema": "mgmtIP", "operator": 0, "expression": "192.168.32.0/24"}
#            ]
#        },
#        "RangeOption": 0, "DeviceGroupRange": [], "SiteRange": []
#    }
#    AddOrUpdateDeviceGroup("Shared Device Groups/Test", condition, "Test")
# @endcode
def AddOrUpdateDeviceGroup(device_group_path, condition, device_group_name):
    strCondition = nbjson.dumps(condition)
    return PyDataModel.AddOrUpdateDeviceGroup(device_group_path, strCondition, device_group_name)


## get current map id
# @note only support qapp and path discovery
# @return current map id
def GetCurrentMapId():
    return PyDataModel.GetCurrentMapId()


## get current map page id
# @note only support qapp and path discovery
# @return current map page id


def GetCurrentMapPageId():
    return PyDataModel.GetCurrentMapPageId()


## get current runbook id
# @note only support runbook run qapp.
# @return current runbook id
def GetCurrentRunbookID():
    return PyDataModel.GetCurrentRunbookID()


## get current runbook change definition if current runbook is change runbook
# @note only support runbook run qapp.
# @return a json array [{"nodeName":"", "configChange":[ {"devName":"R1", "config":"conf t XXX " }  ], "rollback":[{"devName":"R2", "config":"conf t  XXX"}]}]
def GetCurrentChangeDefinition():
    strArray = PyDataModel.GetCurrentChangeDefinition()
    if strArray:
        return nbjson.loads(strArray)
    else:
        return None

## get runbook templete by path
# @param runbook_templete_path runbook templete path
# @return runbook templete content
def GetRunbookTemplete(runbook_templete_path):
    return PyDataModel.GetRunbookTemplete(runbook_templete_path)

## get qapp content by path
# @param qapp_path qapp path
# @return qapp content
def GetQappInfo(qapp_path):
    return PyDataModel.GetQappInfo(qapp_path)


## get dvt by path
# @param dvt_path dvt path
# @return dvt content
def GetDataViewTemplete(dvt_path):
    return PyDataModel.GetDataViewTemplete(dvt_path)


# save json to mongodb
# @warning this func can update all the db data.
def SaveDataToDB(db, collection, value):
    strJsonValue = nbjson.dumps(value)
    return PyDataModel.SaveDataToDB(db, collection, strJsonValue)


# save documents to mongodb
# @warning this func can update all the db data.
def SaveDocsToDB(db, collection, docs, precount=10000):
    if not docs:
        return True

    if len(docs) <= precount:
        return SaveDataToDB(db, collection, docs)

    ret = False
    count = len(docs)
    for i in range(count):
        offset = i * precount
        if offset >= count:
            break

        temp_docs = docs[offset: offset + precount]
        ret = SaveDataToDB(db, collection, temp_docs)
        if not ret:
            return ret

    return ret


# query data from db
# @warning this func can query all the db data.
def QueryDataFromDB(db, collection, json_value):
    strJsonValue = nbjson.dumps(json_value)
    strObject = PyDataModel.QueryDataFromDB(db, collection, strJsonValue)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


# get driver id from vendor sys oid
# @param sysObjectID system oid, e.g. 1.2.826.0.1.4616240.1.1.8510
def GetDriverIdBySysOID(sysObjectID):
    return PyDataModel.GetDriverIdBySysOID(sysObjectID)


## get driver id from vendor model
# @param vendor name of vendor, e.g. "Cisco"
# @param model name of model, e.g.  "TelePresence MCU MSE 8510"
def GetDriverIdByVendorModel(vendor, model):
    return PyDataModel.GetDriverIdByVendorModel(vendor, model)


## add Network Definition
# @param devNameExp device name expression
# @param isRegex devNameExp is regex or not.
# @param ipAddrRange ip
# @param driverId driver id
# @param subType device sub type
def AddNDTItem(devNameExp, isRegex, ipAddrRange, driverId, subType):
    return PyDataModel.AddNDTItem(devNameExp, isRegex, ipAddrRange, driverId, subType)


## return all NDT Items
# @return all NDT Item
# @retval [{item1},{item2}...]
def GetNDTItems():
    items = PyDataModel.GetNDTItems()
    return nbjson.loads(items)


## set NDT Item
# @param ndtItem (dic) ndt item
# @par example
# @code:
# AddNDTItem("device1", True, "1.2.3.4", "b2d313fe-43e6-4d5f-9189-b3af6b71a83a", 2)
# ndtItems = datemodel.GetNDTItems()
# for item in ndtItems:
#    if item["_id"] == "30ce59d2-ba6e-47ff-800e-45a431738422" :
#        item["devNameExp"] = "device2"
#        item["isRegx"] = False
#        item["ipAddrRange"] = "3.4.5.6"
#        item["driverId"] = "b2d313fe-43e6-4d5f-9189-b3af6b71a83a"
#        item["devSubType"] = 2
#        datemodel.SetNDTItem(item)
#        break
# @endcode
# @return True or False
# @retval If the parameter does not contain "_id", return false
def SetNDTItem(ndtItem):
    str_value = nbjson.dumps(ndtItem)
    return PyDataModel.SetNDTItem(str_value)


## AddDonotScanSubnet
# @param subnet (string)  format:ip/mask like 10.10.0.50/24 or ip 10.10.0.50
# @param desc   (string)  description of the subnet
# @param source   (string)  where the sunbet comes from. matching with RemoveDonotScanSubnet
# @return bool True or False
def AddDonotScanSubnet(subnet, desc=None, source=""):
    ip_net = subnet.split("/")
    if len(ip_net) == 1:
        ip_net.append("32")
    mask = int(ip_net[1])
    if len(ip_net) != 2:
        raise ValueError('subnet format error')
    ip_re = re.compile(
        '^(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|[1-9])\\.(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|\\d)\\.(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|\\d)\\.(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|\\d)$')
    if ip_re.match(ip_net[0]):
        if mask >= 8 and mask <= 32:
            if None == desc:
                desc = ""
            ipbyte = ip_net[0].split(".")
            i = int((32 - mask) / 8)
            j = 4 - i
            while j < 4:
                ipbyte[j] = str(int(ipbyte[j]) & 0x00)
                j += 1
            i = int(mask / 8)
            if i < 4:
                ipbyte[i] = str(int(ipbyte[i]) & (0xFF & (0xFF << (8 - mask % 8))))
            return PyDataModel.AddDonotScanSubnet('.'.join(ipbyte) + '/' + str(mask), desc, source)
        else:
            raise ValueError('mask must between 8 and 32, now is ' + ip_net[1])
    else:
        raise ValueError('ip format error:' + ip_net[0])


## RemoveDonotScanSubnet
# @param subnet (string)  format:ip/mask like 10.10.0.50/24 or ip 10.10.0.50
# @param source   (string)  where the sunbet comes from. matching with AddDonotScanSubnet
def RemoveDonotScanSubnet(subnet, source=""):
    ip_net = subnet.split("/")
    if len(ip_net) == 1:
        ip_net.append("32")
    mask = int(ip_net[1])
    if len(ip_net) != 2:
        raise ValueError('subnet format error')
    ip_re = re.compile(
        '^(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|[1-9])\\.(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|\\d)\\.(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|\\d)\\.(1\\d{2}|2[0-4]\\d|25[0-5]|[1-9]\\d|\\d)$')
    if ip_re.match(ip_net[0]):
        if mask >= 8 and mask <= 32:
            ipbyte = ip_net[0].split(".")
            i = int((32 - mask) / 8)
            j = 4 - i
            while j < 4:
                ipbyte[j] = str(int(ipbyte[j]) & 0x00)
                j += 1
            i = int(mask / 8)
            if i < 4:
                ipbyte[i] = str(int(ipbyte[i]) & (0xFF & (0xFF << (8 - mask % 8))))
            return PyDataModel.RemoveDonotScanSubnet('.'.join(ipbyte) + '/' + str(mask), source)
        else:
            raise ValueError('mask must between 8 and 32, now is ' + ip_net[1])
    else:
        raise ValueError('ip format error:' + ip_net[0])


## AddDonotScanDeviceSubType
# @param subtype (int)  devicetype id
# @param desc   (string)  description of the subtype
# @return bool True or False
def AddDonotScanDeviceSubType(subtype, desc=None):
    return PyDataModel.AddDonotScanDeviceSubType(subtype)


## GetDonotScan
# @return string donotscan json string like
#  {
#  "_id" : "ad77c9a6-a1a0-4593-b356",
#  "subnets" : [],
#  "subTypes" : [2001]
#  }
def GetDonotScan():
    strObject = PyDataModel.GetDonotScan()
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetUnknowSNMPSysObjectId
# @param  rtnFileds dict like this:
# @code
# {
#     "devType":1,
#     "devTypeName":1,
#     "contact":1,
#     "ftime":1,
#     "ipfrom":1,
#     "location":1,
#     "mgmtIP":1,
#     "name":1,
#     "oid":1
# }
# @endcode
# @return string josn string like this:
# @code
# [
#   {
#     "_id":"62331697-f413-48ca-9bb2-707aa131c5e5",
#     "contact":"",
#     "devType":1021,
#     "devTypeName":"Unclassified Device",
#     "ftime":{"$date":1544679511000},
#     "ipfrom":"10.10.19.252",
#     "location":"",
#     "mgmtIP":"172.27.0.77",
#     "name":"qapp-aruba-iap",
#     "oid":"1.3.6.1.4.1.14823.1.2.71"
#   }
# ]
# @endcode
def GetUnknowSNMPSysObjectId(rtnFileds=None):
    if None == rtnFileds:
        rtnFileds = {}
    strFileds = nbjson.dumps(rtnFileds)
    strObject = PyDataModel.GetUnknowSNMPSysObjectId(strFileds)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetUnclassifiedNetworkDevice
#  @param  rtnFileds dict like this:
# @code
# {
#     "subType":1,
#     "subTypeName":1,
#     "lDiscoveryTime":1,
#     "model":1,
#     "location":1,
#     "mgmtIP":1,
#     "name":1,
#     "oid":1,
#     "vendor":1
# }
# @endcode
# @return string josn string like this:
# @code
# [
#   {
#     "_id":"9e08c712-e29c-4bea-b642-1b454e7fad3e",
#     "lDiscoveryTime":{"$date":1547799697000},
#     "mgmtIP":"172.27.0.77",
#     "model":"",
#     "name":"qapp-aruba-iap",
#     "oid":"1.3.6.1.4.1.14823.1.2.71",
#     "subType":1021,
#     "subTypeName":"Unclassified Device",
#     "vendor":""
#   }
# ]
# @endcode
def GetUnclassifiedNetworkDevice(rtnFileds=None):
    if None == rtnFileds:
        rtnFileds = {}
    strFileds = nbjson.dumps(rtnFileds)
    strObject = PyDataModel.GetUnclassifiedNetworkDevice(strFileds)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetSNMPDevices
#  @param  rtnFileds dict like this:
#  @code
# {
#     "devType":1,
#     "devTypeName":1,
#     "ctime":1,
#     "model":1,
#     "mgmtIP":1,
#     "name":1,
#     "oid":1,
#     "vendor":1
# }
#  @endcode
#  @param device_name_list name list
# @return string josn string like this:
#  @code
# [
#   {
#     "_id":"8d073b95-1799-4ddc-b7ce-b971905407d5",
#     "ctime":{"$date":1547799756000},
#     "devType":2001,
#     "devTypeName":"Cisco IOS Switch",
#     "mgmtIP":"172.25.5.1",
#     "model":"catalyst356048TS",
#     "name":"BJ_L2_Core_5",
#     "oid":"1.3.6.1.4.1.9.1.634",
#     "vendor":"Cisco"
#   }
# ]
#  @endcode
def GetSNMPDevices(rtnFileds=None, device_name_list=None):
    if None == rtnFileds:
        rtnFileds = {}

    if None == device_name_list:
        device_name_list = []
    strFileds = nbjson.dumps(rtnFileds)
    strDeviceNameList = nbjson.dumps(device_name_list)
    strObject = PyDataModel.GetSNMPDevices(strFileds, strDeviceNameList)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetMissDevice
#  @param  rtnFileds dict like this:
#  @code
# {
#     "devType":1,
#     "devTypeName":1,
#     "ctime":1,
#     "model":1,
#     "mgmtIP":1,
#     "name":1,
#     "oid":1,
#     "vendor":1
# }
#  @endcode
# @param device_name_list device name list
# @return string josn string like this:
#  @code
# [
#   {
#     "_id":"0cf8ccf3-33a3-44fe-aa26-82e659f3b835",
#     "ctime":{"$date":1547799789000},
#     "devType":1004,
#     "devTypeName":"End System",
#     "mgmtIP":"172.25.6.3",
#     "model":"ciscoGatewayServer",
#     "name":"Emu_MV_GW",
#     "oid":"1.3.6.1.4.1.9.1.1",
#     "vendor":"Cisco"
#   }
# ]
#  @endcode
def GetMissDevice(rtnFileds=None, device_name_list=None):
    if None == rtnFileds:
        rtnFileds = {}

    if None == device_name_list:
        device_name_list = []
    strFileds = nbjson.dumps(rtnFileds)
    strDeviceNameList = nbjson.dumps(device_name_list)
    strObject = PyDataModel.GetMissDevice(strFileds, strDeviceNameList)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Delete Missdevice in current domain
#  @param  name (string): name of missdevice
#  @return None
def DelMissDevice(name):
    PyDataModel.DelMissDevice(name)


## Delete Missdevices in current domain
#  @param devIds device id list
#  @return True or False
def DelMissDeviceByIds(devIds):
    return PyDataModel.DelMissDevice(nbjson.dumps(devIds))


# Getunknown ips in current domain
#  @return list of unknown ip
def get_unknown_ips():
    strObject = PyDataModel.GetUnknownIPs()
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetDiscoverInput
# @param datasourceId  string  benchmarkdefineID or devicedatasourceID
# @param isTaskId      bool  default False, if datasourceId is benchmarkdefineID, the isTaskId must be seted False,otherwise the isTaskId must be seted True
# @return string json string like this
#  @code
# {
#   "accessOrder":4,
#   "cliForceTimeout":600,
#   "discoverInfo":{"comefrom":"","comefromMask":"","depth":0,"desc":"","ifname":"","ipSrc":0,"orignalProxy":"","proxy":"","subnetList":[]},
#   "discoverOption":2,
#   "domainName":"",
#   "domainOption":1,
#   "fromScan":false,
#   "hostips":["172.24.31.195"],
#   "isAllDevices":false,
#   "jumpboxOnly":false,
#   "limitRunTimeMinutes":0,
#   "maxDepth":0,
#   "pingTimeout":2,
#   "pingTryTimes":2,
#   "pollingOrder":3,
#   "scanMaskLength":24,
#   "skipPing":false,
#   "snmpIfPingFailed":true,
#   "snmpOnly":false,
#   "telnetIfPingFailed":false,
#   "updateDeviceSetting":true,
#   "useAllNap":true
# }
#  @endcode
def GetDiscoverInput(datasourceId, isTaskId=None):
    if None == isTaskId:
        isTaskId = False
    strObject = PyDataModel.GetDiscoverInput(datasourceId, isTaskId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetNewDevice
#  @param  rtnFileds dict like this:
# @code
# {
#     "devType":1,
#     "devTypeName":1,
#     "ctime":1,
#     "model":1,
#     "mgmtIP":1,
#     "name":1,
#     "oid":1,
#     "vendor":1
# }
# @endcode
# @return josn string like this:
# @code
# [
#   {
#     "_id":"a19eca8b-01b8-444a-8c3f-dc9e600a5c58",
#     "ctime":{"$date":1547799744000},
#     "devType":1004,
#     "devTypeName":"End System",
#     "mgmtIP":"10.10.32.170",
#     "model":"ciscoGatewayServer",
#     "name":"FanWei_Lab_Gateway",
#     "oid":"1.3.6.1.4.1.9.1.1",
#     "vendor":"Cisco"
#   }
# }
# @endcode
def GetNewDevice(rtnFileds=None):
    if None == rtnFileds:
        rtnFileds = {}
    strFileds = nbjson.dumps(rtnFileds)
    strObject = PyDataModel.GetNewDevice(strFileds)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## GetBenchmarkIdByName
#  @param  sourceName string benchmark name
#  @return string benchmark id
def GetBenchmarkIdByName(sourceName):
    return PyDataModel.GetBenchmarkIdByName(sourceName)


## GetBenchmarkExcludeDeviceGroup
#  @param  sourceId string benchmark id
#  @return string json string like this:
# [
#   "#ISIS test",
#   "#OSPF 10"
# ]
def GetBenchmarkExcludeDeviceGroup(sourceId):
    strObject = PyDataModel.GetBenchmarkExcludeDeviceGroup(sourceId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## SetBenchmarkExcludeDeviceGroup
#  @param  sourceId string benchmark id
#  @param  devicegroups list  group name list like ["#ISIS test","#OSPF 10"]
#  @return bool True or False
def SetBenchmarkExcludeDeviceGroup(sourceId, devicegroups):
    strDeviceGroups = nbjson.dumps(devicegroups)
    return PyDataModel.SetBenchmarkExcludeDeviceGroup(sourceId, strDeviceGroups)


## DisableBenchmarkOneProcess
#  @param  sourceId string benchmark id
#  @param  processName string  processName must be one of these:-\n
#     IPv4 L3 Topology/IPv6 L3 Topology/L2 Topology/L3 VPN Tunnel/Logical Topology/L2 Overlay Topology/
#     Recalculate Dynamic Device Groups/Recalculate MPLS Virtual Route Tables/
#     Build Default Device Data View/
#     Visual Space Templates\\Built-in Visual Space Templates\\ACI Application/
#     Visual Space Templates\\Built-in Visual Space Templates\\ACI Overlay/
#     Visual Space Templates\\Built-in Visual Space Templates\\ESXi Host to Network/
#     Visual Space Templates\\Built-in Visual Space Templates\\ESXi Physical and Virtual Relationship/
#     Visual Space Templates\\Built-in Visual Space Templates\\NSX Relationship of Components Visual Space/
#     Visual Space Templates\\Built-in Visual Space Templates\\NSX Transport Zone View Network Visual Space/
#     Schedule Update Map
#  @return bool True or False
def DisableBenchmarkOneProcess(sourceId, processName):
    return PyDataModel.DisableBenchmarkOneProcess(sourceId, processName)


## GetAllDeviceLiveCostInBMTask
#  @param  sourceId string benchmark id
#  @return string json string like this:
# @code
# [
#   {
#     "_id":"1eb46520-91de-4b6e-bb54-e6a41330b7db",
#     "arpTable":"Succeed",
#     "bgpNbrTable":"N/A",
#     "cdpTable":"Succeed",
#     "cliConfig":true,
#     "config":"Succeed",
#     "dataSourceId":"fc6195db-183b-4658-a960-392307a287f7",
#     "deviceId":"6a1f092d-5b9b-49b3-9f17-bc478a0dd6c6",
#     "deviceInfo":"Succeed",
#     "deviceName":"BJ*POP",
#     "hasConfig":true,
#     "interfaceInfo":"Succeed",
#     "macTable":"Succeed",
#     "routeTable":"Succeed",
#     "spendSecond":196,
#     "stpTable":"N/A"
#   }
# ]
# @endcode
def GetAllDeviceLiveCostInBMTask(sourceId):
    strObject = PyDataModel.GetAllDeviceLiveCostInBMTask(sourceId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get Benchmark target devices.
#  @param  sourceId (string) benchmark id
#  @return (list) device name list like:
# [
#   "Device1",
#   "Device2"
# ]
def GetBenchmarkTargetDevices(sourceId):
    strObject = PyDataModel.GetBenchmarkTargetDevices(sourceId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get SDN Api Server id of Benchmark task.
#  @param  sourceId (string) benchmark id
#  @return (list) sdn api server ids.
#  @code
#   ApiServerIds=datamodel.GetBenchmarkAPIServerIDList("24b26155-f306-77e6-a3ec-cda30f05b28b")
#   pluginfw.AddLog("ApiServerIds %s" % ApiServerIds)
#
#   => ApiServerIds ['844ce8f3-f610-4fe3-926b-cad4527f939c']
#  @endcode
def GetBenchmarkAPIServerIDList(sourceId):
    strObject = PyDataModel.GetBenchmarkSDNScopeRange(sourceId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get Benchmark SDN scope ranges.
#  @param  serverId (string) api server id,you can got it by call GetBenchmarkAPIServerIDList
#  @return (list) sdn node ids.
#  @code
#  ex.
#   ApiServerIds=datamodel.GetBenchmarkAPIServerIDList("24b26155-f306-77e6-a3ec-cda30f05b28b")
#
#   for serverId in ApiServerIds:
#       devIds = datamodel.GetSDNNodesByServerID(serverId)
#       pluginfw.AddLog("dev ids %s" % devIds)
#
#    => dev ids ['c9cc4f71-47cf-be20-059c-a37a1b3d8565',......]
#
#  @endcode
def GetSDNNodesByServerID(serverId):
    strObject = PyDataModel.GetSDNNodesByServerID(serverId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


def ValidateDictElement(key, dictIns, valueType):
    if key not in dictIns:
        raise ValueError(nbjson.dumps(dictIns) +
                         " error - " + key + " is required")
    else:
        if not isinstance(dictIns[key], valueType):
            raise ValueError(nbjson.dumps(dictIns) + " error - " +
                             key + " must be " + str(valueType) + " type")


def ValidateEmailJson(emailInfo):
    ValidateDictElement("subject", emailInfo, str)
    ValidateDictElement("body", emailInfo, str)

    if "recipients" in emailInfo:
        if not isinstance(emailInfo["recipients"], list):
            raise ValueError("recipients must be list type")
        else:
            for v in emailInfo["recipients"]:
                p = re.compile(r'[^@]+@[^@]+\.[^@]+')
                if not p.match(v):
                    raise ValueError(
                        "recipients email address " + v + " email format is wrong")

    if "Ccs" in emailInfo:
        if not isinstance(emailInfo["Ccs"], list):
            raise ValueError("Ccs must be list type")
        else:
            for v in emailInfo["Ccs"]:
                p = re.compile(r'[^@]+@[^@]+\.[^@]+')
                if not p.match(v):
                    raise ValueError("Ccs email " + v +
                                     " email format is wrong")
    else:
        if "recipients" not in emailInfo:
            raise ValueError("recipients or Ccs must at least one have value")

    if "attachments" in emailInfo:
        if not isinstance(emailInfo["attachments"], list):
            raise ValueError("attachments must be list type")
        for v in emailInfo["attachments"]:
            if not isinstance(v, dict):
                raise ValueError("attachments element must be dict")
            else:
                if not v:
                    raise ValueError(
                        "attachments" + " contains empty " + nbjson.dumps(v) + ", please check")
                else:
                    ValidateDictElement("filename", v, str)
                    ValidateDictElement("contenttype", v, str)
                    ValidateDictElement("content", v, str)


## Plugin prepare information for email
# ****
# @param emailInfo dict
# dict like this:
# @code
# {
#   "subject":"Where to go",
#   "body":"<html><head>suggest</head><body>Hi all, Let's go to the beach.</body>",
#   "recipients":["liuxiaokai@netbrain.com", "liuxiaokai@netbrain.com"],
#   "Ccs":["liuxiaokai@netbrain.com", "liuxiaokai@netbrain.com"],
#   "attachments":[{"content":"\"place\",\"location\"\n\"dalian_beach\", \"dalian\"\n\"qingdao_beach\",\"qingdao\"", "contenttype":"text/csv", "filename":"place.csv"}, {"content":"test", "contenttype":"text/plain; charset=us-ascii","filename":"test.txt"}]
# }
# @endcode
# ****
# @return bool True or False, if emailInfo json format is wrong, the function will raise exception
def SendEmail(emailInfo):
    ValidateEmailJson(emailInfo)
    strEmailInfo = nbjson.dumps(emailInfo)
    return PyDataModel.SendEmail(strEmailInfo)


## delete devices
# @param device_names (list) device name
# @return True or False
def DeleteDevices(device_names):
    strDevices = nbjson.dumps(device_names)
    return PyDataModel.DeleteDevices(strDevices)


# get all duplicate ips,duplicate ip means witch ip repeat more than once,ignore the mask,ignore the zone.
#  ex. 10.10.10.1/16 and 10.10.10.1/8 will consider as duplicate ip;

## ****
# @return [list] All duplicate ip list,each item is one duplicateIp object,not grouped by ip,retult like follow:
# @code
# [{
#     "description": "",
#     "devId": "7848d5c3-e4e3-49f5-9e57-f9bd2fb398d1",
#     "devInterfaceId": "57792cce-9417-4dee-bff3-4f22cecc3f1d",
#     "deviceName": "",
#     "ip": "10.10.2.27/22",
#     "ipInterfaceId": "89892760-d838-40f0-98ed-8033610e18ca",
#     "ipInterfaceName": "Ethernet0 10.10.2.27/22",
#     "isIpConflicted": false,
#     "nonDuplicateIP": false,
#     "vrf": "",
#     "zone": ""
# }, {
#     "description": "",
#     "devId": "016fa17c-cc69-47b7-82c1-35c2ec79b4f2",
#     "devInterfaceId": "aee8f1d7-fbbf-42f8-af90-5711275b85d5",
#     "deviceName": "",
#     "ip": "10.10.2.27/22",
#     "ipInterfaceId": "4bbd7682-6146-4770-bcb5-f061ae6b4feb",
#     "ipInterfaceName": "Ethernet0 10.10.2.27/22",
#     "isIpConflicted": false,
#     "nonDuplicateIP": false,
#     "vrf": "",
#     "zone": ""
# }]
# @endcode
def GetAllDuplicateIp():
    strDulicateIp = PyDataModel.GetAllDuplicateIp()
    if strDulicateIp:
        return nbjson.loads(strDulicateIp)
    else:
        return None


## SetLastError
# @param  error set thread local error
# @param error_number error number
def SetPyLastError(error, error_number=-1):
    PyDataModel.SetLastError(error, error_number)


# GetLastError
# @return last error string
def GetPyLastError():
    error = PyDataModel.GetLastError()
    if error:
        return error
    else:
        raise ("Unknown Error")


# GetLastErrorCode
# @return last error number
def GetPyLastErrorCode():
    return PyDataModel.GetLastErrorCode()


# ClearLastError
# @return clear last error
def ClearPyLastError():
    PyDataModel.ClearLastError()


## submit one child task to RMAgent
# @param task_name (string) task name,ex.:"DeleteDevice"
# @param task_param (dict) task parameters.
#         to launch child task to another domain, we need to add the sub json obj "tenantIdentifier":{"domainId":uuid, "tenantId":uuid} into task_param
# @param wait_seconds (int) seconds whitch wait the child task complete. if wait_seconds equal to zero. not wait the child task complete.
# @return dict ,like {'result': True, 'taskId': '80a82cb9-53ef-4111-bded-1eda87430975'},if succes,result is True,else result is False.
# @par example: we can rewrite the DeleteDevices function with native python
# @code
# def DeleteDevices(device_names):
#     query={"name":{"$in":device_names}}
#     dev_ids = datamodel.QueryDeviceIds(query)
#     param={}
#     param["param"]=';'.join(dev_ids)
#     ret = datamodel.SubmitChildTask("DeleteDevice",param,50)
#     return ret["result"]
#
# DeleteDevices(["NATT-R1","NATT-ISP"])
# @endcode
def SubmitChildTask(task_name, task_param, wait_seconds=0):
    strParam = nbjson.dumps(task_param)
    jRet = PyDataModel.SubmitChildTask(task_name, strParam, wait_seconds)
    if jRet:
        return nbjson.loads(jRet)
    else:
        return None

## wait all child task complete for some seconds
# @param wait_seconds (int) seconds whitch wait the child task complete. if wait_seconds equal to zero. not wait the child task complete.
# @return bool ,if all child task complete,result is True,else result is False.
# @par example: we can wait child task when SubmitChild task.
# @code
#     query={"name":{"$in":device_names}}
#     dev_ids = datamodel.QueryDeviceIds(query)
#     param={}
#     param["param"]=';'.join(dev_ids)
#     ret = datamodel.SubmitChildTask("DeleteDevice",param,10)
#     while not datamodel.WaitChild(10):
#        time.sleep(1)    
# @endcode
def WaitChild(wait_seconds):
    return PyDataModel.WaitChild(wait_seconds)

## get all child task status
# @param wait_seconds (int) seconds whitch wait operation.
# @return dict ,like {'result': True, 'status': []},if succes,result is True,else result is False.
# @par example: we can get child task status when SubmitChild task.
# @return dict ,like {'result': True, 'status': [{'childTaskId': '2c9583e0-9c2d-4cfe-9818-abdd2e742237', 'childTaskName': 'Discover', 'childTaskStatus': 3}]}
# @par childTaskStatus
#  - "UnknownTaskStatus = 0"
#  - "Scheduled = 1"
#  - "Started = 2"
#  - "Running = 3"
#  - "CompletedWithException = 5"
#  - "CompletedCrash = 6"
#  - "Canceled = 7"
# @code
#     query={"name":{"$in":device_names}}
#     dev_ids = datamodel.QueryDeviceIds(query)
#     param={}
#     param["param"]=';'.join(dev_ids)
#     ret = datamodel.SubmitChildTask("DeleteDevice",param,10)
#     result = datamodel.GetChildrenTaskStatus(10)
# @endcode
def GetChildrenTaskStatus(wait_seconds):
    jRet = PyDataModel.GetChildrenTaskStatus(wait_seconds)
    if jRet:
        return nbjson.loads(jRet)
    else:
        return None
    
## cancel child tasks
# @param childTaskIds (list) children task id will be canceled.
# @param wait_seconds (int) seconds whitch wait complete.
# @return bool ,Success is True,else result is False.
# @par example: we can wait child task when SubmitChild task.
# @code
#     query={"name":{"$in":device_names}}
#     dev_ids = datamodel.QueryDeviceIds(query)
#     param={}
#     param["param"]=';'.join(dev_ids)
#     ret = datamodel.SubmitChildTask("DeleteDevice",param,10)
#     datamodel.CancelChildrenTask(ret['taskId'],10)
# @endcode
def CancelChildrenTask(childTaskIds,wait_seconds):
    listOfChildrenTaskId = nbjson.dumps(childTaskIds)
    return PyDataModel.CancelChildrenTask(listOfChildrenTaskId,wait_seconds)    

# submit host name change task
# @return jobId , If failed return None
def SubmitHostNameChangeChildTask():
    jobid = str(uuid.uuid4())
    param = {}
    param['jobId'] = jobid
    param['taskType'] = 'Detect'

    if not PyDataModel.InitDetectLog(jobid):
        return None

    jRet = SubmitChildTask('HostnameChange', param, 50)
    if jRet and jRet['result']:
        PyDataModel.FinishDetect(jobid, True, '')
        return jobid

    PyDataModel.FinishDetect(jobid, False, 'Excute Hostname Change Task Failed.')
    return None


## get host name change list
# @param jobId
# @return [{HostNameChangeInfo}, {HostNameChangeInfo}, ...]
# @see:UpsertHostnameChangeList
# @see:KeepLastChangeDevice
# @par result example:
# @code
# [
#	{
#		"_id": "123456", // sn
#		"createTime": "datetime.datetime(2020, 01, 01, 11, 3, 46, 201000)",
#		"devices": [
#			{
#				"_id": "517d0f33-8c1d-4646-bbc5-c2a5f2e849a5_1",
#				"fDiscoveryTime": "datetime.datetime(2020, 01, 01, 9, 55, 57)",
#				"lDiscoveryTime": "datetime.datetime(2020, 01, 01, 9, 55, 57)",
#				"mgmtIP": "1.2.3.4",
#				"name": "device1"
#			},
#			{
#				"_id": "517d0f33-8c1d-4646-bbc5-c2a5f2e849a5",
#				"fDiscoveryTime": "datetime.datetime(2020, 01, 01, 9, 55, 57)",
#				"lDiscoveryTime": "datetime.datetime(2020, 01, 01, 9, 55, 57)",
#				"mgmtIP": "1.2.3.4",
#				"name": "device2"
#			}
#		],
#		"jobId": "abdf6ce9-8089-401a-a62d-1d9f2d2161c4"
#	}
# ]
# @endcode
def GetHostnameChangeList(jobId):
    strObject = PyDataModel.GetHostnameChangeList(jobId)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Detect and Get host name change list
# @return [{HostNameChangeInfo}, {HostNameChangeInfo}, ...]
# @see:GetHostnameChangeList
def DetectHostnameChange():
    jobId = SubmitHostNameChangeChildTask()
    if jobId:
        return GetHostnameChangeList(jobId)
    return None


## update host name change list
# @param host_name_list host name list.
# @see:GetHostnameChangeList
# @see:KeepLastChangeDevice
# @return Trur or False
def UpsertHostnameChangeList(host_name_list):
    str_host_name_list = nbjson.dumps(host_name_list)
    return PyDataModel.UpsertHostnameChangeList(str_host_name_list)


## keep last change device
# @param snInfoList (dic)host name change list
# @par snInfoList format:
# @code
#   [
#	    {
#           "sn": "67108914",
#           "deviceIds": [
#               "517d0f33-8c1d-4646-bbc5-c2a5f2e849a5_1",
#               "517d0f33-8c1d-4646-bbc5-c2a5f2e849a5"
#		    ]
#	    }
#   ]
# @endcode
# @see:GetHostnameChangeList
# @see:UpsertHostnameChangeList
# @return True or False
def KeepLastChangeDevice(snInfoList):
    str_snInfo_list = nbjson.dumps(snInfoList)
    if PyDataModel.KeepLastChangeDevice(str_snInfo_list):
        return True
    else:
        return False


## Excute Shared Tune Device
# @param condition tune parameter @see tunesettingutil.ConditionOfTDS
# @param option tune option @see tunesettingutil.OptionOfTDS
# @par example:
# @code
#       from netbrain.sysapi import tunesettingutil
#       from netbrain.sysapi import datamodel
#
#       condition = tunesettingutil.ConditionOfTDS()
#       option = tunesettingutil.OptionOfTDS()
#
#
#       device_names =["Device Name"]
#       query={"name":{"$in":device_names}}
#       dev_ids = datamodel.QueryDeviceIds(query)
#
#       condition.devIds = dev_ids
#
#       option.isCheckPing = True
#       option.isCheckSnmp = True
#       option.isCheckCliLogin = True
#       option.isCheckCliEnable = True
#
#       datamodel.ExcuteSharedTuneDevice(condition, option)
#
#       datamodel.GetTuneDeviceResultByDevIds(dev_ids)
# @endcode
# @return task id for True ,None for False
def ExcuteSharedTuneDevice(condition, option):
    tds = tunesettingutil.CreateSharedTuneDeviceSetting(condition, option)
    jRet = SubmitChildTask('LiveTuneDevice', tds, 50)
    if jRet and jRet['result']:
        return jRet['taskId']
    return None


## Excute Shared Tune one Device
# @param devId device id
# @par example:
# @code
#       from netbrain.sysapi import tunesettingutil
#		from netbrain.sysapi import datamodel
#
#		device_names =["Device Name"]
#		query={"name":{"$in":device_names}}
#		dev_ids = datamodel.QueryDeviceIds(query)
#
#		if dev_ids[0] :
#		    datamodel.ExcuteTuneOneDevice(dev_ids[0])
#		    datamodel.GetTuneDeviceResultByDevIds([dev_ids[0]])
# @endcode
# @return task id for True ,None for False
def ExcuteTuneOneDevice(devId):
    tds = tunesettingutil.CreateTuneOneDeviceSetting(devId)

    jRet = SubmitChildTask('LiveTuneOneDevice', tds, 50)
    if jRet and jRet['result']:
        return jRet['taskId']
    return None


## Excute Private Tune Devices
# @param condition tune parameter @see tunesettingutil.ConditionOfTDS
# @par example:
# @code
#       from netbrain.sysapi import tunesettingutil
#		from netbrain.sysapi import datamodel
#
#		condition = tunesettingutil.ConditionOfTDS()
#
#
#		device_names =["Device name"]
#		query={"name":{"$in":device_names}}
#		dev_ids = datamodel.QueryDeviceIds(query)
#
#		condition.devIds = dev_ids
#
#
#		datamodel.ExcutePrivateTuneDevices(condition)
#
#		datamodel.GetPrivateTuneDeviceResultByDevIds(dev_ids)
# @endcode
# @return task id for True ,None for False
def ExcutePrivateTuneDevices(condition):
    tds = tunesettingutil.CreatePrivateDeviceSetting(condition)
    jRet = SubmitChildTask('PrivateLiveTuneDevice', tds, 50)
    if jRet and jRet['result']:
        return jRet['taskId']
    return None


## Excute Private Tune one Device
# @param devId device id
# @par example:
# @code
#       from netbrain.sysapi import tunesettingutil
#		from netbrain.sysapi import datamodel
#		device_names =["Device Name"]
#		query={"name":{"$in":device_names}}
#		dev_ids = datamodel.QueryDeviceIds(query)
#
#		if dev_ids[0] :
#		    datamodel.ExcutePrivateTuneOneDevice(dev_ids[0])
#		    datamodel.GetPrivateTuneDeviceResultByDevIds([dev_ids[0]])
# @endcode
# @return task id for True ,None for False
def ExcutePrivateTuneOneDevice(devId):
    tds = tunesettingutil.CreatePrivateTuneOneDeviceSetting(devId)
    jRet = SubmitChildTask('PrivateLiveTuneOneDevice', tds, 50)
    if jRet and jRet['result']:
        return jRet['taskId']
    return None


## Get Shared Tune Device Reuslt by device ids
# @param devIds device id list
# @return tune reuslt [{result1}, {result2}, ...]
def GetTuneDeviceResultByDevIds(devIds):
    strDevIds = nbjson.dumps(devIds)
    strObject = PyDataModel.GetTuneDeviceResultByDevIds(strDevIds)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## Get Pravite Tune Device Reuslt by device ids
# @param devIds device id list
# @return tune reuslt [{result1}, {result2}, ...]
def GetPrivateTuneDeviceResultByDevIds(devIds):
    strDevIds = nbjson.dumps(devIds)
    strObject = PyDataModel.GetPrivateTuneDeviceResultByDevIds(strDevIds)
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


def GetProfileClass(device):
    mdl = PyDataModel.GetPathProfileConfig(device)
    if mdl:
        return nbjson.loads(mdl)
    else:
        return None


## Get Shared Tune Device Reuslt by device id
# @param devId device id
# @return tune reuslt
def GetTuneDeviceResultByDevId(devId):
    strObject = PyDataModel.GetTuneDeviceResultByDevId(str(devId))
    if strObject:
        return nbjson.loads(strObject)
    else:
        return None


## trigger event templete
# @note Need to use API IsAnalysisTask in QApp live mode,otherwise it will be triggered twice.
# @param message message
# @param eventTemplateName  event driven templete name
# @return True or False
# @par example
# @code
#		from netbrain.sysapi import datamodel
#       Ticket = {
#            "message" : "1111111111111111"
#       }
#
#       ret = datamodel.TriggerEventTemplate(Ticket)
#       # or trigger event by specified templete name
#       # ret = datamodel.TriggerEventTemplate(Ticket, 'New Template')
#       if not ret :
#           pluginfw.AddLog(str(datamodel.GetPyLastError()))
#    return ret
# @endcode
def TriggerEventTemplate(message, eventTemplateName=None):
    if message is None:
        return False

    strMessage = message
    if isinstance(message, dict):
        strMessage = nbjson.dumps(message)

    if not isinstance(eventTemplateName, str):
        eventTemplateName = ""

    return PyDataModel.TriggerEventTemplate(str(strMessage), eventTemplateName)


## Add or Update command template
# @param name command template name
# @param command command
# @param scope scope command scope - \n
#       0 - Public
#       2 - Pravite
# @param description description
# @param type command type - \n
#       0 - ConfigTemplate
# @return True or False
def AddOrUpdateCommandTemplate(name, command, scope, description, type=0):
    return PyDataModel.AddOrUpdateCommandTemplate(name, command, scope, description, type, 1)


## Update LayoutTag For Devices
# @param devNames device name list
# @param tagNames tag name list
# @return True or False
def UpdateLayoutTagForDevs(devNames, tagNames):
    str_devNames = nbjson.dumps(devNames)
    str_devIds = PyDataModel.GetDevIdsByNames(str_devNames)
    str_tagNames = nbjson.dumps(tagNames)
    return PyDataModel.UpdateLayoutTagForDevs(str_devIds, str_tagNames)


## Delete LayoutTag For Devices
# @param devNames device name list
# @param tagNames tag name list
# @return True or False
def DeleteLayoutTagForDevs(devNames, tagNames):
    str_devNames = nbjson.dumps(devNames)
    str_devIds = PyDataModel.GetDevIdsByNames(str_devNames)
    str_tagNames = nbjson.dumps(tagNames)
    return PyDataModel.DeleteLayoutTagForDevs(str_devIds, str_tagNames)


## Delete documents from OpenTopoInterface Collections
# @param intfIds interface id list
# @return True or False
def DeleteOpenTopoInterfaces(intfIds):
    strIds = nbjson.dumps(intfIds)
    return PyDataModel.DeleteOpenTopoInterfaces(strIds)


## Rebuild OpenTopoArpTable, OpenTopoMacTable, OpenTopoNdpTable and OpenTopoL3NeighborTable by DataEngine data
# @param devId device id
# @return True or False
def RecreateDeviceOpenTopoDETable(devId):
    return PyDataModel.RecreateDeviceOpenTopoDETable(devId)


## Get Devices which had Learned Specified Mac
# @note from V10.02
# @param mac (string) intergface mac address, like 0050.5685.2A9E
# @return devId and devName list which devices had Learned Specified Mac  \n
#
# @code
# [
#   {
#       'devId': '7b68a652-5e68-4b06-adac-fd42e7575db0',
#       'devName': 'sw-4500-15.254'
#   },
#   {
#       'devId': '99f418e7-f634-4535-a877-3a5f7a7ed5a1',
#       'devName': 'sw3560-123'
#   }
# ]
# @endcode
def GetDevicesLearnedSpecifiedMac(mac):
    strDoc = PyDataModel.GetDevicesLearnedSpecifiedMac(mac)
    if strDoc:
        return nbjson.loads(strDoc)
    else:
        return None


## Clean OpenTopoNeighborPairTable by query condition
# @param query query condition
# @return True or False
def CleanOpenTopoNeighborPairTable(query):
    q = nbjson.dumps(query)
    return PyDataModel.CleanOpenTopoNeighborPairTable(q)


## Clean CleanUnknownIP by query condition
# @param query query condition, same as mongodb query like {"name": "172.24.101.43"}
# @return True or False
def CleanUnknownIP(query):
    q = nbjson.dumps(query)
    return PyDataModel.CleanUnknownIP(q)


## Share resource in Tenants
# @param param (dict) parameters
# @return api result (dict) or None
# @par example
# @code:
# {
#    "resources":[
#        {
#            "type": "Parser",                                  # resource type, currently support Qapp, Parser, DataViewTemplate, RunbookTemplate
#            "sourcePath": "Shared Parsers in Tenant/system",   # include all resource in path and subFolders (default)
#            "sourceIsFolder": False,                            # true: path is folder, false: path is not folder, null (default): find both folder and resource.
#            "destinationFolder": "test1",
#            "overwrite": True,                                 # default true
#            "importRelatedResource": False                     # defautl false, Whether to import related resources
#        },
#    ],
#    "tenants" : ["tenantName1", "tenantName2"]
#   }
#
#   {
#   "resources": [
#   {
#       "sourcePath": "Shared Qapps in Tenant/system",
#       "tenants": {
#           "10_0a": "Success.",
#           "test": "Success.",
#           "newTenant": "Success."
#       }
#   }
#   ],
#   "statusCode": 790200,
#   "statusDescription": "Success."
#   }
# @endcode
def ShareResourceInTenants(param):
    strParam = nbjson.dumps(param)
    result = PyDataModel.ShareResourceInTenants(strParam)
    if result:
        return nbjson.loads(result)
    else:
        return None


## Judge whether the absolute path of a file or folder exists. if existing, return True, else return false.
# @param absolute_path absolute path — the absolute path of the file or folder.
# @return True or False
def NBFileOrFolderExists(absolute_path):
    if absolute_path:
        return PyDataModel.IsExist(absolute_path)
    return False


## Judge whether the file path is valid. If valid, return True, else return false.
# @param absolute_path absolute path — the absolute path of the file.
# @return True or False
def IsNBFile(absolute_path):
    if absolute_path and absolute_path.startswith('nbfile'):
        return True
    return False


## Judge whether the folder path is valid. If valid, return True, else return false.
# @param absolute_path absolute path — the absolute path of the folder.
# @return True or False
def IsNBFolder(absolute_path):
    if absolute_path and absolute_path.startswith('nbfolder'):
        return True
    return False


## Return a list containing the file path and sub-folder path of the folder in the directory.
# @param absolute_path absolute path — the absolute path of the folder.
# @return file or folder list
def ListNBDir(absolute_path):
    if absolute_path:
        return nbjson.loads(PyDataModel.GetFileList(absolute_path))
    return []


## Return the content of a file
# @param absolute_path absolute path — the absolute path of the file.
# @return file content
def ReadNBFile(absolute_path):
    if absolute_path:
        return PyDataModel.ReadFile(absolute_path)
    elif IsNBFile(absolute_path) == False:
        raise TypeError('invalid type: absolute_path format must be start with \"nbfile\"')
    return ''


## get automation data table content
# @param tableIdOrPath table id or path
# @param request -reserved parameters-
# @return automation data table content (dict) or None
# @par example
# @code:
#    request = {
#       "columnNameType": 0,    // default: 0. 0: column name, 1: display name, 2: db column name.
#       "returnColumns" : ["column1"] # Filter field returns data
#    }
#    ret = datamodel.GetTableAndDataByRequest("Shared Tables/aaa/aaa", request)
#    if ret == None:
#        err = datamodel.GetPyLastError()
#    else:
#        # dosomething
# @endcode
# @see UpdateRowForAutoTable
# @see AddRowForAutoTable
# @see DeleteRowForAutoTable
def GetTableAndDataByRequest(tableIdOrPath, request=None):
    str_request = ""
    if request != None:
        str_request = nbjson.dumps(request)
    result = PyDataModel.GetTableAndDataByRequest(tableIdOrPath, str_request)
    if result:
        return nbjson.loads(result)
    else:
        return None

## Add Or Update System Map Layout Relations
# @param relations relation list
# @return True or False
# @par example
# @code:
#    relations = [
#      {
#        "mapBriefInfo": {
#          "mapId": "36064b13-8136-4d4a-a643-0bd395265b3a",
#          "mapType": 3,
#         "isCasscade": False,
#          "rowId": ""
#        },
#        "layoutBriefInfo": {
#          "id": "1126d26a-096f-4a17-a18f-b0ffbc2a04e9",
#          "layOutStyleType": 1
#        }
#      }
#    ]
#  
#    ret = datamodel.AddOrUpdateSysMapLayoutRelations(relations)
#    
#    AddLog(str(ret), 2)
#    if not ret:
#        error = datamodel.GetPyLastError()
#        AddLog(str(error), 2)
# @endcode    
def AddOrUpdateSysMapLayoutRelations(relations):
    if relations != None and isinstance(relations, list):
        content = nbjson.dumps(relations)
        return PyDataModel.AddOrUpdateSysMapLayoutRelations(content)
        
    return None
    
## Delete System Map Layout Relations
# @param relations relation list
# @return True or False
# @par example
# @code:
#    relations = [
#      {
#        "mapBriefInfo": {
#          "mapId": "36064b13-8136-4d4a-a643-0bd395265b3a",
#          "mapType": 3,
#         "isCasscade": False,
#          "rowId": ""
#        },
#        "layoutBriefInfo": {
#          "id": "1126d26a-096f-4a17-a18f-b0ffbc2a04e9",
#          "layOutStyleType": 1
#        }
#      }
#    ]
#  
#    ret = datamodel.DeleteSysMapLayoutRelations(relations)
#    
#    AddLog(str(ret), 2)
#    if not ret:
#        error = datamodel.GetPyLastError()
#        AddLog(str(error), 2)
# @endcode  
def DeleteSysMapLayoutRelations(relations):
    if relations != None and isinstance(relations, list):
        content = nbjson.dumps(relations)
        return PyDataModel.DeleteSysMapLayoutRelations(content)
        
    return None

## Get System Map Layout Relations
# @param mapTypes map types list- \n
#       General = 1,
#       OverViewMap = 2,
#       SiteMap = 3
# @return Map Layout Relations
def GetSysMapLayoutAllRelation(mapTypes):
    if mapTypes == None or not isinstance(mapTypes, list):
        return None
    content = nbjson.dumps(mapTypes)
    relations = PyDataModel.GetSysMapLayoutAllRelation(content)
    if relations:
        return nbjson.loads(relations)
    else:
        return None

## Get layout style infomation
# @param layoutFullPath layout full path
# @return layout style infomation
# @par example
# @code:
#    layoutPath2 = "Layout Styles/New Folder/New Layout Style"
#    lay_out_info2 = datamodel.GetLayoutStyleInfo(layoutPath2)
#    AddLog(str(lay_out_info2), 2)
# @endcode
def GetLayoutStyleInfo(layoutFullPath):
    info = PyDataModel.GetLayoutStyleInfo(layoutFullPath)
    if info:
        return nbjson.loads(info)
    else:
        return None
    
## Get device id list in map.
# @param mapId mapId
# @param pageId pageId(Optional)
# @return device id list
def GetMapPageDeviceIds(mapId, pageId=""):
    devIdList = PyDataModel.GetMapPageDeviceIds(mapId, pageId)
    if devIdList:
        return nbjson.loads(devIdList)
    else:
        return None    
    

## Add Row For AutoTable
# @param tableIdOrPath table id or path
# @param request -reserved parameters-
# @return True, False or None
# @par example
# @code:
#    request = {
#        "columnNameType": 0, // default: 0. 0: column name, 1: display name, 2: db column name.
#        "rows": [
#            {
#                "column1": "value333",
#                "column2": "value444"
#                
#            }
#            ]
#    }
#   add_ret = datamodel.AddRowForAutoTable(table_path, request)
# @endcode
# @see UpdateRowForAutoTable
# @see DeleteRowForAutoTable
# @see GetTableAndDataByRequest
def AddRowForAutoTable(tableIdOrPath, request=None):
    str_request = ""
    if request != None:
        str_request = nbjson.dumps(request)
    return PyDataModel.AddRowForAutoTable(tableIdOrPath, str_request)

## Update Row For AutoTable
# @param tableIdOrPath table id or path
# @param request -reserved parameters-
# @return True, False or None
# @par example
# @code:
#    request = {
#        "columnNameType": 0,  // default: 0. 0: column name, 1: display name, 2: db column name.
#        "rows": {
#            "ce05b851-3eb7-4301-b035-8225e44faf79": // rowId, get from GetTableAndDataByRequest
#            {
#                "column1": "value888",
#                "column2": "value999"
#            }
#        }
#    }
#   add_ret = datamodel.UpdateRowForAutoTable(table_path, request)
# @endcode
# @see AddRowForAutoTable
# @see DeleteRowForAutoTable
# @see GetTableAndDataByRequest
def UpdateRowForAutoTable(tableIdOrPath, request=None):
    str_request = ""
    if request != None:
        str_request = nbjson.dumps(request)
    return PyDataModel.UpdateRowForAutoTable(tableIdOrPath, str_request)

## Delete Row For AutoTable
# @param tableIdOrPath table id or path
# @param request -reserved parameters-
# @return True, False or None
# @par example
# @code:
#    request = { "rows": ["ce05b851-3eb7-4301-b035-8225e44faf79"] } // rowId, get from GetTableAndDataByRequest
#    del_ret = datamodel.DeleteRowForAutoTable(table_path, request)
# @endcode
# @see UpdateRowForAutoTable
# @see AddRowForAutoTable
# @see GetTableAndDataByRequest
def DeleteRowForAutoTable(tableIdOrPath, request=None):
    str_request = ""
    if request != None:
        str_request = nbjson.dumps(request)
    return PyDataModel.DeleteRowForAutoTable(tableIdOrPath, str_request)

# update or insert network setting
# @param setting network setting object
# @param updateRefDeviceSetting update reference device setting
# @param type 0: telnet/ssh, 1: privilege
# @return True, False or None
# @par example
# @code:
#    # telnet/ssh
#    setting = {
#        "Alias" : "aaaaa_alias",
#        "UserName" : "aaaa",
#        "Passwd" : "aaaa",
#        "CliMode" : 0,     // 0: telnet, 2: ssh public key
#        "SSHKeyID" : "",
#    }
#    del_ret = datamodel.UpInsertNetworkSetting(setting, 0, updateRefDeviceSetting)
#
#   # privilege
#    enable_setting = {
#        "Alias" : "bbbbb_alias",
#        "EnableUserName" : "bbbb",
#        "EnablePasswd" : "bbbb"
#    }
#    bRet = datamodel.UpInsertNetworkSetting(setting, 1)
# @endcode
def UpInsertNetworkSetting(setting, type, updateRefDeviceSetting=False):
    if type == 0 and setting["UserName"].strip() == "" and setting["Passwd"].strip() == "":
        return False
    if type == 1 and setting["EnableUserName"].strip() == "" and setting["EnablePasswd"].strip() == "":
        return False
    
    if "Alias" not in setting and setting["Alias"].strip() == "":
        return False
    
    if "ID" not in setting:
        setting["ID"] = setting["Alias"]
        
    if setting["ID"] != setting["Alias"]:
        return False
    
    if setting != None:
        str_setting = nbjson.dumps(setting)
    return PyDataModel.UpInsertNetworkSetting(str_setting,type, updateRefDeviceSetting)

# get ni ids in the specified ADT columns
# @param adt table id or path
# @param columns reference names
# @return each columns ni ids
# @par example
# @code:
#   #columns = [column1, column2]
#
#   #result = 
#   {
#      "column1":[ni1, ni2,...]
#      "column2":[ni1, ni2,...]
#      "column3":[ni1, ni2,...]
#   }
# @endcode
def GetNiIdByADTColumns(strTableIdOrPath:str, columns:list[str]):
    if not strTableIdOrPath:
        return False
    
    if not columns:
        columns = []
    
    strColumns = json.dumps(columns)    
    result = PyDataModel.GetNiIdByADTColumns(strTableIdOrPath, strColumns)
    if columns:
        result = json.loads(result)
    return result

# get adt columns definition
# @param adt table id or path
# @param columns reference names
# @return each columns definittion
# @par example
# @code:
#   #columns = [column1, column2]
#
#   #result = 
#   [
#      {...},
#      {...}
#   ]
# @endcode
def GeADTDefinition(strTableIdOrPath:str, columns:list[str]):
    if not strTableIdOrPath:
        return False
    
    if not columns:
        columns = []
    
    strColumns = json.dumps(columns)    
    result = PyDataModel.GeADTDefinition(strTableIdOrPath, strColumns)
    if result:
        return json.loads(result)
    return None

## Get all alias in network setting
# @param type 0: telnet/ssh, 1: privilege, 2: snmp, 3: private key
# @return alias list
def GetAllAliasInNetworkSetting(type):
    result = PyDataModel.GetAllAliasInNetworkSetting(type)
    if result:
        return nbjson.loads(result)
    return None

## Get alias in network setting
# @param type 0: telnet/ssh, 1: privilege, 2:snmp, 3: private key
# @param alias alias name
# @return alias info
def GetAliasInfoInNetworkSetting(type, alias):
    result = PyDataModel.GetAllAliasInNetworkSetting(type, alias)
    if result:
        return nbjson.loads(result)
    return None
                    
def GetAllServerDetails():
    result = PyDataModel.GetAllServerDetails()
    if result:
        return nbjson.loads(result)
    return None

def GetKeyMetrics():
    result = PyDataModel.GetKeyMetrics()
    if result:
        return nbjson.loads(result)
    return None


## Export Resource
# @param tenantId tenantId
# @param domainId domainId
# @param strPath resource path
# @param strType resource type, "NI"
# @return base64 string
# @par example
# @code:
#    domain = datamodel.GetCurrentDomainInfo()
#    result = datamodel.ExportResource(domain["tenantId"], domain["domainId"], "Network Essential/MAC Address Navigator")
#    
#    import base64
#    binary_data = base64.b64decode(result)
#    with open("output.xni", "wb") as f:
#        f.write(binary_data)
# @endcode
def ExportResource(tenantId, domainId, strPath, strType = "NI" ):
    result = PyDataModel.ExportResource(tenantId, domainId, strType, strPath)
    if result:
        return result
    return None


## Build Auto Table
# @param tableIdOrPath table id or full path
# @param request request json object
# {
#     "intentColumns": ["Replicated_Intent"],   # intent column names need to be built, according to columnNameType
#     "columnNameType": 0,                      # name type for intent Columns, default value 0.  0: refrence name, 1: display name, 2: db column name
#     "onlyEmptyForIntentCells": True,          # true if only build empty cells for intent cells
#     "groups": ["base", "groupId"]             # groups need to be build, if group is specified, ignore intentColumns field
# }
# @param wait_seconds (int)
# @return task info json or None if table does not exist
# {
#     "taskId": ""      # taskId for build task
# }
# @par example
# @code:
#    req = {
#        "intentColumns": ["Replicated_Intent"],
#        "columnNameType": 0,
#        "onlyEmptyForIntentCells": True
#    }
#    result = datamodel.BuildAutoTable("MyDomain/MyTable", req)
#    print(result)
# @endcode
def BuildAutoTable(tableIdOrPath, request, wait_seconds=30):
    if not tableIdOrPath:
        raise ValueError('tableIdOrPath is empty.')
    
    req = json.dumps(request)  
    result = PyDataModel.BuildAutoTable(tableIdOrPath, req, wait_seconds)
    if result:
        return result
    return None


## Run Intent In ADT
# @param tableIdOrPath table id or full path
# @param request request json object
# {
#     "colName": ["c2"],   # intent column names need to be run, it should be db column name.
#     "timerId": None      # null means run once, read timer id means run by timer
#     # other advanced parameters please refer to UI operartion
# }
# @return task info json or None if table does not exist
# {
#     "id": ""     # schedule GI id for golden intent or PAF id for normal intent
# }
# @par example
# @code:
#    req = {
#        "colName": ["c2"],
#        "timerId": None
#    }
#    result = datamodel.RunIntentInADT("MyDomain/MyTable", req)
#    print(result)
# @endcode
def RunIntentInADT(tableIdOrPath, request):
    if not tableIdOrPath:
        raise ValueError('tableIdOrPath is empty.')
    
    req = json.dumps(request)  
    result = PyDataModel.RunIntentInADT(tableIdOrPath, req)
    if result:
        return result
    return None

## Save As Table
# @param sourceTableIdOrPath table id or full path of source table
# @param destTablePath full path of destination table
# @param request request json object
# {
#     "autoRename": False,   # auto rename if the name is duplicated
#     "keepRowData": False   # copy all row data to destination table
# }
# @return the new table or None if failed
# @exception ValueError invalid arguments
# @exception Exception other unexpected errors
# @example
# @code:
#    req = {
#        "autoRename": False,
#        "keepRowData": False
#    }
#    result = datamodel.CopyTable("MyDomain/MySourceTable", "MyDomain/MyDestTable", req)
#    print(result)
# @endcode
def SaveAsADT(srcTableIdOrPath, destTableIdOrPath, request):
    req = json.dumps(request)  
    result = PyDataModel.SaveAsForPython(srcTableIdOrPath, destTableIdOrPath, req)
    if result:
        return result
    return None

## Refresh ADT view
# @param srcTableIdOrPath source table id or path which is used to build map
def RefreshViewForADT(srcTableIdOrPath):
    return PyDataModel.RefreshViewForPython(srcTableIdOrPath)