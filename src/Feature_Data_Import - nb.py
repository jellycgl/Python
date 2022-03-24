import glob
import json
# # from fileinput import filename
import os
import re
import zipfile

from netbrain.sysapi import (
    datamodel,
    pluginfw,
    protocol,
    devicedata,
)

FDS_PATH = 'Feature_Design_Summary'
NB_Install_Folder = r'C:\Program Files\NetBrain\Worker Server\Temp\UserData'

DEBUG = True
CONF_KEY = '_conf_'
DEV_KEY = '_dev_'
INTF_KEY = '_intf_'
INTF_TYPE = 'intfs'
DEV_NAMEW_of_REGEX = re.compile(r'(.+?)_.*?_').search
CMD_KEY_of_REGEX = re.compile(r'_(\S+ .*?)_').search


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
            msg = 'Import configuration of %s successfully' % self._dev_name
            dpt(msg, pluginfw.WARNING)
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
            msg = 'Failed to get device object of %s' % self._dev_name
            dpt(msg, pluginfw.ERROR)
            return False
        dev_id = dev_obj.get('_id')
        new_dev_obj['_id'] = dev_id
        if datamodel.SetDeviceObject(self._dev_name, new_dev_obj):
            msg = 'Update device properties of %s successfully' % self._dev_name
            dpt(msg, pluginfw.WARNING)
            return True
        else:
            msg = 'Failed to update device properties of %s' % self._dev_name
            dpt(msg, pluginfw.ERROR)
        return False

    def update_interfaces_object(self, interfaces_json_path):
        '''
        set interface properties base on C++ API
        @param device_name(string): 'R1'
        @param interfaces_json_path(string): 'C:\\Program Files\\NetBrain\\Worker\\Temp\\UserData\\R1_intf_20220324.json'
        @return True or False
        '''
        if not interfaces_json_path:
            return False
        with open(r'%s' % interfaces_json_path) as f:
            new_intfs_obj = json.loads(f.read())
        for new_intf_obj in new_intfs_obj:
            intf_name = new_intf_obj.get('name')
            old_intf_obj = datamodel.GetInterfaceObject(self._dev_name, intf_name, INTF_TYPE)
            if not old_intf_obj:
                old_intf_id = new_intf_obj.get('_id')
            else:
                old_intf_id = old_intf_obj.get('_id')
            new_intf_obj['_id'] = old_intf_id
            if 'operateInfo' in new_intf_obj:
                new_intf_obj.pop('operateInfo')
            if 'devId' in new_intf_obj:
                new_intf_obj.pop('devId')
            if datamodel.SetInterfaceObject(self._dev_name, intf_name, INTF_TYPE, new_intf_obj):
                msg = 'Update interface properties of %s.%s successfully' % (self._dev_name, intf_name)
                dpt(msg, pluginfw.WARNING)
            else:
                msg = 'Failed to update interface properties of %s.%s' % (self._dev_name, intf_name)
                dpt(msg, pluginfw.ERROR)
        return True

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
            dpt(msg, pluginfw.WARNING)
            return True
        else:
            msg = 'Failed to import cli command <%s> of %s' % (cli_command, self._dev_name)
            pluginfw.AddLog(msg, pluginfw.ERROR)
        return False


def parse_input(input):
    input_info = json.loads(input)
    input_file_path = input_info.get('input_file_path', '')
    if not input_file_path:
        print('Please put the input file in a specific path')
        return ''
    if not os.path.exists(input_file_path):
        print('The input file could not be found at the specified path')
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
        dev_path = os.path.split(dev_json_path)[-1]
        dev_name = dev_path[:dev_path.find(DEV_KEY)]
        res.setdefault(dev_name, ImportDeviceData(dev_json_path))
    return res


def run(input):
    unzip_folder = parse_input(input)
    if not unzip_folder:
        return False

    data_folder = unzip_folder + '\\DeviceData'

    for folderName, subfolders, filenames in os.walk(data_folder):
        init_devices = init_devices_database(glob.glob(r'%s\*_dev_*.json' % folderName))
        if not init_devices:
            msg = 'No device json was found in the %s' % folderName
            dpt(msg, pluginfw.ERROR)
            continue

        filenames = sorted(filenames)
        for file_name in filenames:
            file_full_path = os.path.join(folderName, file_name)
            dev_name_search = DEV_NAMEW_of_REGEX(file_name)
            dev_name = dev_name_search.group(1) if dev_name_search else ''
            if dev_name not in init_devices:
                msg = 'No device json of %s was found' % dev_name
                dpt(msg, pluginfw.ERROR)
                continue
            device_data = init_devices.get(dev_name)
            if file_name.rfind(CONF_KEY) != -1:
                device_data.import_config_object(file_full_path)
            elif file_name.rfind(DEV_KEY) != -1:
                device_data.update_device_object(file_full_path)
            elif file_name.rfind(INTF_KEY) != -1:
                device_data.update_interfaces_object(file_full_path)
            elif CMD_KEY_of_REGEX(file_name):
                cli_cmd = CMD_KEY_of_REGEX(file_name).group(1)
                device_data.import_command(cli_cmd, file_full_path)

    return True
