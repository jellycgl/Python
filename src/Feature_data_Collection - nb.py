import os
import re
import csv
import json
import time
import shutil
import datetime
from typing import Tuple
from zipfile import ZipFile

from netbrain.sysapi import pluginfw
from netbrain.sysapi import datamodel
from netbrain.sysapi import devicedata
from netbrain.sysapi import certification
from netbrain.sysapi.protocol import QueryDataProtocol


# Export
FDS_NAME = 'Feature_Design_Summary'
DATA_FOLDER = 'Data'
CONF_SUFFIX = '.config'
JSON_SUFFIX = '.json'
TEXT_SUFFIX = '.txt'
ZIP_SUFFIX = '.zip'
CSV_SUFFIX = '.csv'
NB_Install_Folder = r'C:\Program Files\NetBrain\Worker Server\UserData\Temp'


# Tags
Regex_Tag = 'regex:'
Variable_Tag = '$'
Split_Tag = ';'


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


# NetBrain
INTF_TYPE = 'intfs'


class FDC_Input:
    def __init__(self) -> None:
        self.featureName = ''
        self.featureInclude = ''
        self.featureExclude = ''
        self.deviceFilter = ''
        self.cliCommand = ''
        self.maxDeviceCount = 3
        self.maxCliCommandCount = 5
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


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()


def parse_input(input):
    rows = []
    if not input:
        pluginfw.AddLog('Please enter the feature design definition')
        return rows
    root_folder = NB_Install_Folder + '\\' + FDS_NAME
    if not os.path.exists(root_folder):
        os.mkdir(root_folder)
    output_file_path = root_folder + '\\input.csv'
    with open(output_file_path, 'w') as cliFile:
        cliFile.write(input)
    with open(output_file_path, encoding='utf-8', errors='ignore') as csvFile:
        reader = csv.reader(csvFile)
        for row in reader:
            if not row:
                continue
            rows.append(row)
    os.remove(output_file_path)
    return rows


def check_row_valid(row) -> bool:
    if not row:
        return False
    if row[0] == Feature_Name:
        return False
    if len(row) > Max_CLI_Command_Count_Index + 1:
        pluginfw.AddLog('Please check this line definition: %s' % str(row))
        return False
    return True


def get_input_items(rows):
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
        if row[Max_Device_Count_Index]:
            input_item.maxDeviceCount = row[Max_Device_Count_Index]
        if row[Max_CLI_Command_Count_Index]:
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
            pluginfw.AddLog('Matched exclude condition, the config content is "%s"' % config_line)
            return False
        if match_include_condition(input_item, config_line):
            pluginfw.AddLog('Matched include condition, the config content is "%s"' % config_line)
            return True
    pluginfw.AddLog('Neither inclusion nor exclusion conditions were matched')
    return False


def get_data_from_file(file_full_path):
    original_data = ''
    with open(file_full_path, 'rb') as file_data:
        original_data = file_data.read()
    return original_data


def save_data_to_file(file_full_path, data):
    with open(file_full_path, 'w') as dataFile:
        dataFile.write(data)
    return True


def translate_from_name(file_name):
    rstr = r"[\/\\\:\*\?\"\<\>\|]"
    file_name = re.sub(rstr, "%", file_name)
    return file_name


def feature_check(input_items):
    feature_results = list()
    device_datas = dict()
    device_config = dict()
    device_feature_commands = dict()
    for input_item in input_items:
        if not input_item:
            continue
        query = input_item.get_device_filter()
        devices = datamodel.QueryDeviceObjects(query)
        if not devices:
            continue
        for device in devices:
            device_id = device.get('_id', '')
            device_name = device.get('name', '')
            if not device_name:
                continue
            config_content = ''
            if device_name in device_config.keys():
                config_content = device_config[device_name]
            else:
                config = devicedata.GetConfig(device_name)
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
            intf_query = {'devId': device_id}
            interfaces = datamodel.QueryInterfaceObjects(intf_query, INTF_TYPE)
            device_datas[device_name] = {
                'devInfo': device,
                'intfsInfo': interfaces
            }
    return feature_results, device_datas, device_feature_commands, device_config


def save_summary_file(root_folder, feature_results):
    output_file_path = root_folder + '\\' + FDS_NAME + CSV_SUFFIX
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
    save_data_to_file(output_file_path, config)


def save_cli_command(device_folder, date_time, device_name, cli_command, original_output):
    file_name = device_name + '_' + cli_command + '_' + date_time + TEXT_SUFFIX
    output_file_path = device_folder + file_name
    save_data_to_file(output_file_path, original_output)


def save_gdr_data(device_folder, date_time, device_name, device_info, interfaces_info):
    if device_info:
        file_name = device_name + '_dev_' + date_time + JSON_SUFFIX
        output_file_path = device_folder + file_name
        save_data_to_file(output_file_path, json.dumps(device_info, indent=4, cls=DateTimeEncoder))
    if interfaces_info:
        file_name = device_name + '_intf_' + date_time + JSON_SUFFIX
        output_file_path = device_folder + file_name
        save_data_to_file(output_file_path, json.dumps(interfaces_info, indent=4, cls=DateTimeEncoder))


def retrieve_command(device_name, cli_command) -> str:
    if not device_name or not cli_command:
        return ''
    rp = QueryDataProtocol()
    rp.devName = device_name
    rp.command = cli_command
    rp.commandType = 9 # cli command
    rp.datasource.type = 1 # live resource
    res = devicedata.Query(rp)
    if not res:
        return ''
    content = ''
    status = res.get('result', 'fail')
    if status == 'fail':
        content = res.get('error', '')
        if not content:
            content = res.get('livelog', '')
    content = res.get('content', '')
    return content


def upload_result(zip_file_content) -> bool:
    report_name = FDS_NAME + ZIP_SUFFIX
    export_path = FDS_NAME
    certification.export_certification_report(report_name, zip_file_content, export_path)
    return True


def save_output(results):
    stamp = int(time.time())
    date_time = time.strftime('_%Y%m%d_', time.localtime(stamp))
    root_folder = NB_Install_Folder + '\\' + FDS_NAME
    if not os.path.exists(root_folder):
        os.mkdir(root_folder)

    feature_results = results[0]
    device_datas = results[1]
    device_feature_commands = results[2]
    device_config = results[3]

    save_summary_file(root_folder, feature_results)

    device_folder = root_folder + '\\' + DATA_FOLDER
    if not os.path.exists(device_folder):
        os.mkdir(device_folder)
    device_folder = device_folder + '\\'

    for device_name, feature_cmds in device_feature_commands.items():
        for featureName, cmds in feature_cmds.items():
            for cli_command in cmds:
                if not cli_command:
                    continue
                original_output = retrieve_command(device_name, cli_command)
                device_name = translate_from_name(device_name)
                save_cli_command(device_folder, date_time, device_name, cli_command, original_output)

    for device_name, infos in device_datas.items():
        config_content = device_config.get(device_name)
        device_name = translate_from_name(device_name)
        save_config_file(device_folder, date_time, device_name, config_content)

        device_info = infos.get('devInfo')
        interfaces_info = infos.get('intfsInfo')
        save_gdr_data(device_folder, date_time, device_name, device_info, interfaces_info)

    zip_file_path = NB_Install_Folder + '\\' + FDS_NAME + ZIP_SUFFIX
    with ZipFile(zip_file_path, 'w') as zipObj:
        for folderName, subfolders, filenames in os.walk(root_folder):
            for filename in filenames:
                filePath = os.path.join(folderName, filename)
                zipObj.write(filePath)
    shutil.rmtree(root_folder)

    zip_file_content = get_data_from_file(zip_file_path)
    upload_result(zip_file_content)
    return True


def run(input):
    rows = parse_input(input)
    if not rows:
        return False

    input_items = get_input_items(rows)
    if not input_items or len(input_items) == 0:
        pluginfw.AddLog('There is no effective input information')
        return False

    results = feature_check(input_items)
    if not results:
        pluginfw.AddLog('There is no effective results')
        return False

    save_output(results)
    return True
