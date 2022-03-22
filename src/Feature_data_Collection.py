# from netbrain.sysapi import datamodel 
# from netbrain.sysapi import devicedata 
# from netbrain.sysapi import pluginfw 


import os
import re
import csv
import json
import time
import shutil
from typing import Tuple
from zipfile import ZipFile


# Export
FDS_PATH = 'Feature_Design_Summary'
CONF_SUFFIX = '.config'
JSON_SUFFIX = '.json'
TEXT_SUFFIX = '.txt'
ZIP_SUFFIX = '.zip'
CSV_SUFFIX = '.csv'
NB_Install_Folder = r'C:\Users\gchen\Desktop\Temp\Feature Summary'

# Tags
Regex_Tag = 'regex:'
Variable_Tag = '$'
Split_Tag = ';'
Regex_Type = {
    '$vlan': r'((?:\d+\-\d+|\d+)(?:,(?:\d+\-\d+|\d+))*)',
    '$var1': r'((?:\d+)(?:,\d+)*)',
    '$ospf': r''
}


# Input
Feature_Name = 'Feature Name'
Feature_Name_Index = 0
Featuer_Include = 'Feature Include'
Featuer_Include_Index = 1
Featuer_Exclude = 'Feature Exclude'
Featuer_Exclude_Index = 2
Device_Filter = 'Device Type Filter'
Device_Filter_Index = 3
Device_Filter = 'Device Model Filter'
Device_Filter_Index = 4
CLI_Command = 'Cli Command'
CLI_Command_Index = 5
Max_Device_Count = 'Max Device Count'
Max_Device_Count_Index = 6
Max_CLI_Command_Count = 'Max Command Count(Per Device)'
Max_CLI_Command_Count_Index = 7


class FDC_Input:
    def __init__(self) -> None:
        self.featureName = ''
        self.featureInclude = ''
        self.featureExclude = ''
        self.deviceFilter = ''
        self.cliCommand = ''
        self.maxDeviceCount = -1
        self.maxCliCommandCount = 10
        self.var2Values = dict()

    def get_feature_include(self) -> list:
        includes = list()
        if not self.featureInclude:
            return includes
        feature_includes = self.featureInclude.split(Split_Tag)
        for feature_include in feature_includes:
            includes.append(feature_include.strip())
        return includes

    def get_feature_exclude(self) -> list:
        exclude_conditions = list()
        if not self.featureExclude:
            return exclude_conditions
        feature_excludes = self.featureExclude.split(Split_Tag)
        for feature_exclude in feature_excludes:
            exclude_conditions.append(feature_exclude.strip())
        return exclude_conditions

    def extract_variables(self, cli_cmd) -> list:
        variables = list()
        return variables

    def get_cliCommand(self) -> list:
        commands = set()
        if not self.cliCommand or not self.var2Values:
            return commands
        cli_cmds = self.cliCommand.split(Split_Tag)
        for cli_cmd in cli_cmds:
            if Variable_Tag not in cli_cmd:
                commands.add(cli_cmd)
                if len(commands) == self.maxCliCommandCount:
                    return commands
            else:
                result = self.cliCommand
                for var, value in self.var2Values.items():
                    result = result.replace(var, value)
                commands.add(result)
                if len(commands) == self.maxCliCommandCount:
                    return commands
        return commands

    def get_device_filter(self) -> dict:
        dev_filter = dict()
        if self.deviceFilter:
            # Todo
            pass
        return dev_filter


def parse_input(input):
    rows = []
    if not input:
        print('Please enter the necessary input information')
        return rows
    input_info = json.loads(input)
    input_file_path = input_info.get('input_file_path', '')
    if not input_file_path:
        print('Please put the input file in a specific path')
        return rows
    if not os.path.exists(input_file_path):
        print('The input file could not be found at the specified path')
        return rows
    with open(input_file_path, encoding='utf-8', errors='ignore') as csvFile:
        reader = csv.reader(csvFile)
        for row in reader:
            rows.append(row)
    return rows


def check_row_valid(row) -> bool:
    if not row:
        return False
    if row[0] == Feature_Name:
        return False
    if len(row) > Max_CLI_Command_Count_Index + 1:
        print('Please check this line definition: %s' % str(row))
        return False
    return True


def get_input_items(rows) -> list[FDC_Input]:
    input_items = list()
    for row in rows:
        if not check_row_valid(row):
            continue
        input_item = FDC_Input()
        input_item.featureName = row[Feature_Name_Index]
        input_item.featureInclude = row[Featuer_Include_Index]
        input_item.featureExclude = row[Featuer_Exclude_Index]
        input_item.deviceFilter = row[Device_Filter_Index]
        input_item.cliCommand = row[CLI_Command_Index]
        input_item.maxDeviceCount = row[Max_Device_Count_Index]
        input_item.maxCliCommandCount = row[Max_CLI_Command_Count_Index]
        input_items.append(input_item)
    return input_items


def get_matched_content(data, key, regex=''):
    matched_content = ''
    if not regex:
        regex_text = '.*%s.*' % key
        matched_content = re.findall(regex_text, data)
    else:
        matched_content = re.findall(regex, data)
    return matched_content


def match_exclude_condition(input_item, config_line):
    exclude_conditions = input_item.get_feature_exclude()
    if not exclude_conditions:
        return False
    for exclude_condition in exclude_conditions:
        if Regex_Tag in exclude_condition:
            exclude_condition = exclude_condition.replace(Regex_Tag, '')
        match_result = get_matched_content(config_line, exclude_condition)
        if match_result:
            return True
    return False


def extract_var_name_type(var_groups):
    vars = var_groups.split(';')
    rtn = list()
    for var in vars:
        words = var.split(':')
        var_type = 'str' if len(words) == 1 else words[1]
        var_name = words[0]
        rtn.append((var_name, var_type))
    return rtn


def match_include_condition(input_item, config_line):
    include_conditions = input_item.get_feature_include()
    if not include_conditions:
        return False
    for include_condition in include_conditions:
        if Regex_Tag not in include_condition and Variable_Tag not in include_condition:
            match_result = get_matched_content(config_line, include_condition)
            if match_result:
                return True
        if Variable_Tag in include_condition:
            vars = re.findall(r'\$[^ ]+', include_condition)
            real_regex = re.sub(r'\$[^ ]+', r'(\\S+)', include_condition)
            match_result = get_matched_content(config_line, '', real_regex)
            if match_result:
                match_value = match_result[0]
                if isinstance(match_value, str) == 1:
                    input_item.var2Values[vars[0]] = match_value
                if isinstance(match_value, Tuple):
                    for index in range(len(vars)):
                        input_item.var2Values[vars[index]] = match_value[index]
                return True
        if Regex_Tag in include_condition:
            regex = include_condition.split(Regex_Tag)[1].strip()
            pos = regex.find(']')
            if pos == -1:
                match_result = get_matched_content(config_line, '', regex)
                if match_result:
                    return True
            else:
                var_groups = regex[1:pos]
                var_name_types = extract_var_name_type(var_groups)
                regex = regex[pos + 1:]
                groups = re.findall(regex, config_line)
                if groups:
                    for group in groups:
                        if isinstance(group, str):
                            var_name = var_name_types[0][0]
                            var_type = var_name_types[0][1]
                            vars = [group]
                            if var_type == 'list':
                                vars = group.split(',')
                            if var_name not in input_item.var2Values.keys():
                                input_item.var2Values[var_name] = set()
                            for var in vars:
                                input_item.var2Values[var_name].add(var)
                        if isinstance(group, tuple):
                            for index in group:
                                var_name = var_name_types[index][0]
                                var_type = var_name_types[index][1]
                                vars = [group]
                                if var_type == 'list':
                                    vars = group.split(',')
                                if var_name not in input_item.var2Values.keys():
                                    input_item.var2Values[var_name] = set()
                                for var in vars:
                                    input_item.var2Values[var_name].add(var)
                    return True
    return False


def match_config(input_item, config):
    config_lines = config.split('\n')
    for config_line in config_lines:
        if match_exclude_condition(input_item, config_line):
            print('Matched exclude condition, the config content is "%s"' % config_line)
            return False
        if match_include_condition(input_item, config_line):
            print('Matched include condition, the config content is "%s"' % config_line)
            return True
    print('Neither inclusion nor exclusion conditions were matched')
    return False


def get_data_from_file(file_full_path):
    original_data = ''
    with open(file_full_path, encoding='utf-8', errors='ignore') as file_data:
        original_data = file_data.read()
    return original_data


def feature_check(input_items):
    feature_results = list()
    device_datas = dict()
    device_config = dict()
    device_feature_commands = dict()
    for input_item in input_items:
        if not input_item:
            continue
        #query = input_item.get_device_filter()
        #devices = datamodel.QueryDeviceObjects(query)
        devices = [
            {
                "_id" : "2f64868e-adfa-4e69-8e0f-8b8cf6a9350d",
                "configFileFrom" : 1,
                "driverId" : "f2b4bfcd-d05e-4b42-9ae0-53cc83d2dab3",
                "driverName" : "Cisco WLC",
                "fDiscoveryTime" : "2021-12-28T19:02:30Z",
                "hasBGPConfig" : False,
                "hasEIGRPConfig" : False,
                "hasISISConfig" : False,
                "hasMulticastConfig" : False,
                "hasOSPFConfig" : False,
                "isGenericDevice" : False,
                "isIPAccouting" : False,
                "isIPSLA" : False,
                "isMulticastRouting" : False,
                "isNetflow" : False,
                "isSNMPConfig" : False,
                "isTagSwitchingIp" : True,
                "lDiscoveryTime" : "2021-12-28T19:02:30Z",
                "mainType" : 1048,
                "mainTypeName" : "WLC",
                "mgmtIP" : "192.168.32.100",
                "mgmtIntf" : "",
                "name" : "CNQBOSTW02",
                "subType" : 3033,
                "subTypeName" : "Cisco WLC",
                "vdcList" : [],
                "vpn" : None
                },
            {}
        ]
        if not devices:
            continue
        for device in devices:
            device_name = device.get('name', '')
            if not device_name:
                continue
            config_content = ''
            if device_name in device_config.keys():
                config_content = device_config[device_name]
            else:
                #config = devicedata.GetConfig(device_name)
                config = {
                    'content': get_data_from_file(r'C:\Users\gchen\Desktop\Temp\Feature Summary\Test.config')
                }
                config_content = config.get('content', '')
                if not config_content:
                    continue
                device_config[device_name] = config_content
            matched_result = match_config(input_item, config_content)
            if matched_result:
                feature_name = input_item.featureName
                feature_cmds = input_item.get_cliCommand()
                feature_info = {
                    'FeatureName': feature_name,
                    'DeviceName': device_name,
                    'DeviceType': device.get('subType', ''),
                    'DeviceModel': device.get('model', ''),
                    'DeviceDriver': device.get('driverName', ''),
                    'CLICommands': Split_Tag.join(feature_cmds)
                }
                feature_results.append(feature_info)
                if len(feature_cmds) > 0:
                    if device_name not in device_feature_commands:
                        device_feature_commands[device_name] = dict()
                    if feature_name not in device_feature_commands[device_name].keys():
                        device_feature_commands[device_name][feature_name] = set()
                    for feature_cmd in feature_cmds:
                        device_feature_commands[device_name][feature_name].add(feature_cmd)
            if device_name in device_datas.keys():
                continue
            #interfaces = datamodel.QueryInterfaceObjects(query)
            interfaces = [
                {
                    "_id" : "4ecc8e7c-8a1e-43ba-8d1b-b49a1aabae9d",
                    "bandwidth" : 10000000,
                    "belongToTopoType" : ["L2_Topo_Type"],
                    "channelGroup" : "",
                    "channelGroupMode" : "",
                    "channelList" : "",
                    "configOrder" : 15,
                    "descr" : "",
                    "devId" : "2f64868e-adfa-4e69-8e0f-8b8cf6a9350d",
                    "encapType" : "default encapsulation",
                    "hasMacAddr" : True,
                    "inAclName" : "",
                    "ipUnnumbered" : "",
                    "ipUnnumberedIp" : "",
                    "isBroadcast" : True,
                    "isChannel" : False,
                    "isIPUnnumberedIntf" : False,
                    "isL2Intf" : False,
                    "isLanIntf" : True,
                    "isLoopback" : False,
                    "isSerial" : False,
                    "isShutdown" : False,
                    "isSubIntf" : False,
                    "isTunnel" : False,
                    "isTunnelMultipoint" : False,
                    "isVirtualIntf" : False,
                    "isVlanIntf" : False,
                    "isWanIntf" : False,
                    "mplsVrf" : "",
                    "multicastMode" : "",
                    "name" : "TenGigabitEthernet0/0/1",
                    "outAclName" : "",
                    "routingProtocol" : "",
                    "shortName" : "teng0/0/1",
                    "macAddr" : "a093.5153.2cba"
                    },
                    {}
            ]
            device_datas[device_name] = {
                'devInfo': device,
                'intfsInfo': interfaces
            }
    return feature_results, device_datas, device_feature_commands, device_config


def save_summary_file(root_folder, feature_results):
    output_file_path = root_folder + '\\' + FDS_PATH + CSV_SUFFIX
    csv_columns = ['Feature Name', 'Dev Name', 'Dev Type', 'Vendor', 'Model', 'Driver', 'CLI Commands']
    with open(output_file_path, 'w', newline='') as csvFile:
        writer = csv.DictWriter(csvFile, fieldnames=csv_columns)
        writer.writeheader()
        for result in feature_results:
            row = {
                'Feature Name': result.get('FeatureName', ''),
                'Dev Name': result.get('DeviceName', ''),
                'Dev Type': result.get('DeviceType', ''),
                'Vendor': '',
                'Model': result.get('DeviceModel', ''),
                'Driver': result.get('DeviceDriver', ''),
                'CLI Commands': result.get('CliCommands', ''),
            }
            writer.writerow(row)
    return True


def save_config_file(device_folder, date_time, device_name, config):
    file_name = device_name + '_conf_' + date_time + CONF_SUFFIX
    output_file_path = device_folder + file_name
    with open(output_file_path, 'w') as configFile:
        configFile.write(config)
    configFile.close()


def save_cli_command(device_folder, date_time, device_name, cli_command, original_output):
    file_name = device_name + '_' + cli_command + '_' + date_time + TEXT_SUFFIX
    output_file_path = device_folder + file_name
    with open(output_file_path, 'w') as cliFile:
        cliFile.write(original_output)
    cliFile.close()


def save_gdr_data(device_folder, date_time, device_name, device_info, interfaces_info):
    if device_info:
        file_name = device_name + '_dev_' + date_time + JSON_SUFFIX
        output_file_path = device_folder + file_name
        with open(output_file_path, 'w') as devFile:
            devFile.write(json.dumps(device_info))
        devFile.close()
    if interfaces_info:
        file_name = device_name + '_intf_' + date_time + JSON_SUFFIX
        output_file_path = device_folder + file_name
        with open(output_file_path, 'w') as intfFile:
            intfFile.write(json.dumps(interfaces_info))
        intfFile.close()


def retrieve_command(device_name, cli_command) -> str:
    return 'Test Retrieve'


def upload_result(zip_file_content) -> bool:
    return True


def save_output(results):
    stamp = int(time.time())
    date_time = time.strftime('_%Y%m%d_', time.localtime(stamp))
    root_folder = NB_Install_Folder + '\\' + FDS_PATH
    if not os.path.exists(root_folder):
        os.mkdir(root_folder)

    feature_results = results[0]
    device_datas = results[1]
    device_feature_commands = results[2]
    device_config = results[3]

    save_summary_file(root_folder, feature_results)

    for device_name, feature_cmds in device_feature_commands.items():
        device_folder = root_folder + '\\' + device_name
        if not os.path.exists(device_folder):
            os.mkdir(device_folder)
        device_folder = device_folder + '\\'
        for featureName, cmds in feature_cmds.items():
            for cli_command in cmds:
                if not cli_command:
                    continue
                original_output = retrieve_command(device_name, cli_command)
                save_cli_command(device_folder, date_time, device_name, cli_command, original_output)

    for device_name, infos in device_datas.items():
        device_folder = root_folder + '\\' + device_name
        if not os.path.exists(device_folder):
            os.mkdir(device_folder)
        device_folder = device_folder + '\\'

        config_content = device_config.get(device_name)
        save_config_file(device_folder, date_time, device_name, config_content)

        device_info = infos.get('devInfo')
        interfaces_info = infos.get('intfsInfo')
        save_gdr_data(device_folder, date_time, device_name, device_info, interfaces_info)

    zip_file_path = NB_Install_Folder + '\\' + FDS_PATH + ZIP_SUFFIX
    with ZipFile(zip_file_path, 'w') as zipObj:
        for folderName, subfolders, filenames in os.walk(root_folder):
            for filename in filenames:
                filePath = os.path.join(folderName, filename)
                zipObj.write(filePath)
    zipObj.close()
    shutil.rmtree(root_folder)

    zip_file_content = ''
    upload_result(zip_file_content)
    return True


def run(input):
    rows = parse_input(input)
    if not rows:
        return False

    input_items = get_input_items(rows)
    if not input_items or len(input_items) == 0:
        print('There is no effective input information')
        return False

    results = feature_check(input_items)
    if not results:
        print('There is no effective results')
        return False

    save_output(results)
    return True


if __name__ == "__main__":
    input_info = {
        'input_file_path': r'C:\Users\gchen\Desktop\Temp\Feature Summary\Vendor Feature Inputs - Variable.csv'
    }
    input = json.dumps(input_info)
    run(input)
