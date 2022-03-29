import glob
import json
import os
import time
import zipfile

from netbrain.sysapi import (
    datamodel,
    pluginfw,
    protocol,
    devicedata,
)

FDS_PATH = 'Feature_Design_Summary'
NB_Install_Folder = r'C:\Program Files\NetBrain\Worker Server\UserData\Temp'

DEBUG = True
CONF_KEY = 'conf'
DEV_KEY = 'dev'
INTF_KEY = 'intf'
INTF_TYPE = 'intfs'


def dpt(msg, level=pluginfw.INFO):
    if DEBUG:
        pluginfw.AddLog(msg, level)
        print(msg)


class FileNameTranslate:
    def __init__(self) -> None:
        self.invalidChars = dict()
        self.invalidChars['/'] = 'A'
        self.invalidChars['\\'] = 'B'
        self.invalidChars[':'] = 'C'
        self.invalidChars['*'] = 'D'
        self.invalidChars['?'] = 'E'
        self.invalidChars['\"'] = 'F'
        self.invalidChars['<'] = 'G'
        self.invalidChars['>'] = 'H'
        self.invalidChars['|'] = 'I'
        self.invalidChars['$'] = 'J'

    def translateToName(self, name, prefix='X') -> str:
        file_name = ''
        for index in range(len(name)):
            chVal = name[index]
            if chVal == prefix:
                file_name = file_name + prefix
                file_name = file_name + prefix
                continue
            if chVal not in self.invalidChars.keys():
                file_name = file_name + chVal
                continue
            file_name = file_name + prefix
            charReplace = self.invalidChars[chVal]
            file_name = file_name + charReplace
        return file_name

    def get_invalid_char(self, value) -> str:
        for chVal, chRep in self.invalidChars.items():
            if chRep == value:
                return chVal
        return ''

    def translateFromName(self, orign, prefix='X') -> str:
        name = ""
        char_index = -1
        for index in range(len(orign)):
            char_index = char_index + 1
            if char_index == len(orign):
                return name
            chVal = orign[char_index]
            if chVal != prefix and chVal not in self.invalidChars.values():
                name = name + chVal
                continue
            char_index = char_index + 1
            if char_index >= len(orign):
                return orign
            chVal = orign[char_index]
            if chVal is None:
                break
            if chVal == prefix:
                name = name + prefix
            elif chVal in self.invalidChars.values():
                org_char = self.get_invalid_char(chVal)
                if org_char not in self.invalidChars.keys():
                    return orign
                name = name + org_char
            else:
                name = name + prefix
                name = name + chVal
        return name


class ImportDeviceData:
    def __init__(self, device_json_path):
        self._dev_name = ''
        self._driver_id = ''
        self._init_device(device_json_path)

    def _init_device(self, device_json_path):
        if not device_json_path:
            return False
        with open(r'%s' % device_json_path) as f:
            dev_obj = json.loads(f.read())
        self._dev_name = dev_obj.get('name')
        self._driver_id = dev_obj.get('driverId')

    def import_config_object(self, conf_path):
        '''
        set device properties base on C++ API
        @param device_name(string): 'R1'
        @param device_json_path(string): 'C:\\Program Files\\NetBrain\\Worker\\Temp\\UserData\\R1_conf_20220324.config'
        @return True or False
        '''
        if not conf_path:
            return False
        with open(r'%s' % conf_path) as f:
            config = f.read()
        if devicedata.ImportConfig(self._driver_id, config):
            time.sleep(0.1)
            msg = 'Import configuration of %s successfully' % self._dev_name
            dpt(msg)
            return True
        else:
            msg = 'Failed to import configuration of %s' % self._dev_name
            dpt(msg, pluginfw.ERROR)
        return False

    def update_device_object(self, device_json_path):
        '''
        set device properties base on C++ API
        @param device_name(string): 'R1'
        @param device_json_path(string): 'C:\\Program Files\\NetBrain\\Worker\\Temp\\UserData\\R1_dev_20220324.json'
        @return True or False
        '''
        if not device_json_path:
            return False
        with open(r'%s' % device_json_path) as f:
            new_dev_obj = json.loads(f.read())
        dev_obj = datamodel.GetDeviceObject(self._dev_name)
        if not dev_obj:
            msg = 'No device %s was found, Preparing to create new device' % self._dev_name
            dpt(msg, pluginfw.WARNING)
            self.add_device_object(new_dev_obj)
            return False
        dev_id = dev_obj.get('_id')
        new_dev_obj['_id'] = dev_id
        if datamodel.SetDeviceObject(self._dev_name, new_dev_obj):
            msg = 'Update device properties of %s successfully' % self._dev_name
            dpt(msg)
            return True
        else:
            msg = 'Failed to update device properties of %s' % self._dev_name
            dpt(msg, pluginfw.ERROR)
            msg = json.dumps(new_dev_obj, indent=2)
            dpt(msg)
        return False

    def add_device_object(self, device_object):
        if datamodel.AddDeviceObject(device_object):
            msg = 'Add device %s into database successfully' % self._dev_name
            dpt(msg)
            return True
        else:
            msg = 'Failed to add device %s into database' % self._dev_name
            dpt(msg, pluginfw.ERROR)
            msg = json.dumps(device_object, indent=2)
            dpt(msg)

    def update_interfaces_object(self, interfaces_json_path):
        '''
        set interface properties base on C++ API
        @param device_name(string): 'R1'
        @param interfaces_json_path(string): 'C:\\Program Files\\NetBrain\\Worker\\Temp\\UserData\\R1_intf_20220324.json'
        @return True or False
        '''
        if not (interfaces_json_path and self._dev_name):
            return False
        dev_obj = datamodel.GetDeviceObject(self._dev_name)
        if not dev_obj:
            msg = 'Skip update interface, because lack of device %s' % self._dev_name
            dpt(msg, pluginfw.ERROR)
            return False
        with open(r'%s' % interfaces_json_path) as f:
            new_intfs_obj = json.loads(f.read())
        for new_intf_obj in new_intfs_obj:
            intf_name = new_intf_obj.get('name')
            if 'operateInfo' in new_intf_obj:
                new_intf_obj.pop('operateInfo')
            old_intf_obj = datamodel.GetInterfaceObject(self._dev_name, intf_name, INTF_TYPE)
            if not old_intf_obj:
                msg = 'No interface %s.%s was found, Preparing to create new interface' % (self._dev_name, intf_name)
                dpt(msg, pluginfw.WARNING)
                self.add_interface_object(new_intf_obj)
                return False

            new_intf_obj['_id'] = old_intf_obj.get('_id')
            if 'devId' in new_intf_obj:
                new_intf_obj.pop('devId')
            if datamodel.SetInterfaceObject(self._dev_name, intf_name, INTF_TYPE, new_intf_obj):
                msg = 'Update interface properties of %s.%s successfully' % (self._dev_name, intf_name)
                dpt(msg)
            else:
                msg = 'Failed to update interface properties of %s.%s' % (self._dev_name, intf_name)
                dpt(msg, pluginfw.ERROR)
                msg = json.dumps(new_intf_obj, indent=2)
                dpt(msg)

        return True

    def add_interface_object(self, interface_object):
        intf_name = interface_object.get('name')
        if datamodel.AddPhantomInterface(self._dev_name, intf_name, INTF_TYPE, "L2_Topo_Type"):
            msg = 'Add %s.%s into database successfully' % (self._dev_name, intf_name)
            dpt(msg)
            if datamodel.SetInterfaceObject(self._dev_name, intf_name, INTF_TYPE, interface_object):
                msg = 'Update interface properties of %s.%s successfully' % (self._dev_name, intf_name)
                dpt(msg)
            else:
                msg = 'Failed to update interface properties of %s.%s' % (self._dev_name, intf_name)
                dpt(msg, pluginfw.ERROR)
                msg = json.dumps(interface_object, indent=2)
                dpt(msg)
        else:
            msg = 'Failed to add %s.%s into database' % (self._dev_name, intf_name)
            dpt(msg, pluginfw.ERROR)
            msg = json.dumps(interface_object, indent=2)
            dpt(msg)

    def import_command(self, cli_command, command_txt_path):
        '''
        save cli command result base on C++ API
        @param device_name(string): 'R1'
        @param command_txt_path(string): 'C:\\Program Files\\NetBrain\\Worker\\Temp\\UserData\\R1_show version_20220324.txt'
        @return True or False
        '''
        if not command_txt_path:
            return False
        with open(r'%s' % command_txt_path) as f:
            cli_outputs = f.read()
        protocoldata = protocol.ImportOriginalTextProtocol()
        protocoldata.devName = self._dev_name
        protocoldata.commandType = 9
        protocoldata.command = cli_command
        protocoldata.original = cli_outputs
        if devicedata.ImportDeviceDataByCLI(protocoldata):
            msg = 'Import cli command <%s> of %s successfully' % (cli_command, self._dev_name)
            dpt(msg)
            return True
        else:
            msg = 'Failed to import cli command <%s> of %s' % (cli_command, self._dev_name)
            pluginfw.AddLog(msg, pluginfw.ERROR)
        return False


def parse_input(input):
    input_info = json.loads(input)
    input_file_path = input_info.get('input_file_path', '')
    if not input_file_path:
        pluginfw.AddLog('Please put the input file in a specific path')
        return ''
    if not os.path.exists(input_file_path):
        pluginfw.AddLog('The input file could not be found at the specified path')
        return ''
    unzip_folder = NB_Install_Folder + '\\' + FDS_PATH
    with zipfile.ZipFile(input_file_path, "r") as zipFile:
        zipFile.extractall(unzip_folder)
    return unzip_folder


# Simulate discovery process
def init_devices_database(devices_js_list) -> dict:
    res = dict()
    if not devices_js_list:
        return res
    for dev_json_path in devices_js_list:
        dev_name, datatype, timestamp = parse_device_info_by_filename(os.path.basename(dev_json_path))
        res.setdefault(dev_name, ImportDeviceData(dev_json_path))
    return res


def translate_from_name(file_name):
    translator = FileNameTranslate()
    file_name = translator.translateToName(file_name)
    return file_name


def parse_device_info_by_filename(file_name):
    file_name = os.path.splitext(file_name)[0]

    # Parse index
    _time_index = file_name.rfind('_')
    _datatype_index = file_name[:_time_index].rfind('_')

    # Find keywords base on index
    deviceName = file_name[:_datatype_index]
    dataType = file_name[_datatype_index + 1:_time_index]
    timestamp = file_name[_time_index + 1::]

    return (deviceName, dataType, timestamp)


def run(input):
    unzip_folder = parse_input(input)
    if not unzip_folder:
        return False

    data_folder = unzip_folder + '\\DeviceData'
    pluginfw.AddLog(data_folder)

    for folderName, subfolders, filenames in os.walk(data_folder):
        init_devices = init_devices_database(glob.glob(r'%s\*_%s_????????.json' % (folderName, DEV_KEY)))
        if not init_devices:
            msg = 'No device json was found in the %s' % folderName
            dpt(msg, pluginfw.ERROR)
            continue

        filenames = sorted(filenames)
        for file_name in filenames:
            file_full_path = os.path.join(folderName, file_name)
            dev_name, datatype, timestamp = parse_device_info_by_filename(file_name)
            if dev_name not in init_devices:
                msg = 'No device json of %s was found' % dev_name
                dpt(msg, pluginfw.ERROR)
                continue
            device_data = init_devices.get(dev_name)
            if datatype == CONF_KEY:
                device_data.import_config_object(file_full_path)
            elif datatype == DEV_KEY:
                device_data.update_device_object(file_full_path)
            elif datatype == INTF_KEY:
                device_data.update_interfaces_object(file_full_path)
            elif len(datatype.split()) > 1:
                device_data.import_command(datatype, file_full_path)

    return True
