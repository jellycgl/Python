import os
import re
import csv
import json
import time
import shutil
import datetime
from zipfile import ZipFile

from netbrain.sysapi import pluginfw
from netbrain.sysapi import datamodel
from netbrain.sysapi import devicedata
from netbrain.sysapi import certification
from netbrain.sysapi.protocol import QueryDataProtocol


# Export
FDS_NAME = 'Feature_Design_Summary'
INPUT_NAME = 'input_file'
DATA_FOLDER = 'DeviceData'
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
Device_Type_Filter = 'Device Type Filter'
Device_Type_Filter_Index = 3
Device_Model_Filter = 'Device Model Filter'
Device_Model_Filter_Index = 4
CLI_Command = 'Cli Command'
CLI_Command_Index = 5
Max_Device_Count = 'Max Device Count'
Max_Device_Count_Index = 6
Max_CLI_Command_Count = 'Max Command Count(Per Device)'
Max_CLI_Command_Count_Index = 7


# NetBrain
INTF_TYPE = 'intfs'


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
            if chVal != prefix:
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


class FDC_Input:
    def __init__(self) -> None:
        self.featureName = ''
        self.featureInclude = ''
        self.featureExclude = ''
        self.deviceTypeFilter = ''
        self.deviceModelFilter = ''
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
        if not self.cliCommand:
            return commands
        cli_cmds = self.cliCommand.split(Split_Tag)
        for cli_cmd in cli_cmds:
            if Variable_Tag not in cli_cmd:
                commands.add(cli_cmd)
                if len(commands) == self.maxCliCommandCount:
                    return commands
            else:
                result = self.cliCommand
                for var, values in self.var2Values.items():
                    for value in values:
                        result = self.cliCommand.replace(var, value)
                        commands.add(result)
                        if len(commands) == self.maxCliCommandCount:
                            return commands
        return commands

    def clear_cache_value(self):
        self.var2Values = dict()

    def get_final_filter(self, filter_item):
        filters = filter_item.split(Split_Tag)
        if len(filters) <= 1:
            return filter_item
        final_filter = '|'.join(filters)
        return final_filter

    def get_device_filter(self) -> dict:
        dev_filter = dict()
        if not self.deviceTypeFilter and not self.deviceModelFilter:
            return dev_filter
        if self.deviceTypeFilter:
            dev_filter['subTypeName'] = {
                '$regex': self.get_final_filter(self.deviceTypeFilter), '$options': 'i'}
        if self.deviceModelFilter:
            dev_filter['model'] = {
                '$regex': self.get_final_filter(self.deviceModelFilter), '$options': 'i'}
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
    shutil.rmtree(root_folder)
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
        input_item.deviceTypeFilter = row[Device_Type_Filter_Index]
        input_item.deviceModelFilter = row[Device_Model_Filter_Index]
        input_item.cliCommand = row[CLI_Command_Index]
        if row[Max_Device_Count_Index]:
            input_item.maxDeviceCount = int(row[Max_Device_Count_Index])
        if row[Max_CLI_Command_Count_Index]:
            input_item.maxCliCommandCount = int(
                row[Max_CLI_Command_Count_Index])
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
        if len(words) == 1:
            var_name = words[0]
            var_type = 'str'
        else:
            var_name = words[1]
            var_type = words[0].replace('$', '')
        rtn.append((var_name, var_type))
    return rtn


def match_include_condition(input_item, config):
    matched_result = False
    include_conditions = input_item.get_feature_include()
    if not include_conditions:
        return matched_result
    for include_condition in include_conditions:
        if Regex_Tag not in include_condition and Variable_Tag not in include_condition:
            match_result = get_matched_content(config, include_condition)
            if not match_result:
                return False
            else:
                matched_result = True
        if Regex_Tag in include_condition:
            regex = include_condition.split(Regex_Tag)[1].strip()
            pos = regex.find(']')
            if pos == -1:
                match_result = get_matched_content(config, '', regex)
                if not match_result:
                    return False
                else:
                    matched_result = True
            else:
                var_groups = regex[1:pos]
                var_name_types = extract_var_name_type(var_groups)
                regex = regex[pos + 1:]
                groups = re.findall(regex, config, re.M)
                if not groups:
                    return False
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
                matched_result = True
        elif Variable_Tag in include_condition:
            vars = re.findall(r'\$[^ ]+', include_condition)
            real_regex = re.sub(r'\$[^ ]+', r'(\\S+)', include_condition)
            match_result = get_matched_content(config, '', real_regex)
            if not match_result:
                return False
            match_value = match_result[0]
            if isinstance(match_value, str) == 1:
                var_name = vars[0]
                if var_name not in input_item.var2Values.keys():
                    input_item.var2Values[var_name] = set()
                input_item.var2Values[var_name].add(match_value)
            if isinstance(match_value, tuple):
                for index in range(len(vars)):
                    var_name = vars[index]
                    if var_name not in input_item.var2Values.keys():
                        input_item.var2Values[var_name] = set()
                    input_item.var2Values[var_name].add(match_value[index])
            matched_result = True
    return matched_result


def match_config(input_item, config):
    # Check Feature Exclude
    exclude_conditions = input_item.get_feature_exclude()
    if exclude_conditions:
        for exclude_condition in exclude_conditions:
            if Regex_Tag not in exclude_condition:
                match_result = get_matched_content(config, exclude_condition)
                if match_result:
                    pluginfw.AddLog(
                        'Matched exclude condition, the feature exclude is %s' % str(exclude_condition))
                    return False
            else:
                exclude_condition = exclude_condition.replace(Regex_Tag, '')
                match_result = get_matched_content(
                    config, None, exclude_condition)
                if match_result:
                    pluginfw.AddLog(
                        'Matched exclude condition, the feature exclude is %s' % str(exclude_condition))
                    return False

    # Check Feature Include
    matched_result = match_include_condition(input_item, config)
    if matched_result:
        return True

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
    translator = FileNameTranslate()
    file_name = translator.translateToName(file_name)
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
                if len(feature_results) == input_item.maxDeviceCount:
                    break
                feature_name = input_item.featureName
                feature_cmds = input_item.get_cliCommand()
                input_item.clear_cache_value()
                feature_info = {
                    'FeatureName': feature_name,
                    'DeviceName': device_name,
                    'DeviceType': device.get('subTypeName', ''),
                    'DeviceModel': device.get('model', ''),
                    'DeviceDriver': device.get('driverName', ''),
                    'DeviceVendor': device.get('vendor', ''),
                    'CLICommands': Split_Tag.join(feature_cmds)
                }
                feature_results.append(feature_info)
                if len(feature_cmds) > 0:
                    if device_name not in device_feature_commands:
                        device_feature_commands[device_name] = dict()
                    if feature_name not in device_feature_commands[device_name].keys():
                        device_feature_commands[device_name][feature_name] = set(
                        )
                    for feature_cmd in feature_cmds:
                        device_feature_commands[device_name][feature_name].add(
                            feature_cmd)
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
    csv_columns = ['Feature Name', 'Device Name', 'Device Type',
                   'Vendor', 'Model', 'Driver', 'CLI Commands']
    with open(output_file_path, 'w', newline='') as csvFile:
        writer = csv.DictWriter(csvFile, fieldnames=csv_columns)
        writer.writeheader()
        for result in feature_results:
            row = {
                'Feature Name': result.get('FeatureName', ''),
                'Device Name': result.get('DeviceName', ''),
                'Device Type': result.get('DeviceType', ''),
                'Vendor': result.get('DeviceVendor', ''),
                'Model': result.get('DeviceModel', ''),
                'Driver': result.get('DeviceDriver', ''),
                'CLI Commands': result.get('CLICommands', '')
            }
            writer.writerow(row)
    return True


def save_input_file(root_folder, device_feature_commands, device_datas):
    rows = []
    dev_schemas = set()
    for dev_name in device_feature_commands.keys():
        if not dev_name:
            continue
        infos = device_datas.get(dev_name)
        if not infos:
            continue
        device_info = infos.get('devInfo')
        if not device_info or not isinstance(device_info, dict):
            continue
        row = {}
        for schema in device_info.keys():
            dev_schemas.add(schema)
            row[schema] = device_info[schema]
        rows.append(row)

    if not rows:
        return False

    output_file_path = root_folder + '\\' + INPUT_NAME + CSV_SUFFIX
    csv_columns = list(dev_schemas)
    with open(output_file_path, 'w', newline='') as csvFile:
        writer = csv.DictWriter(csvFile, fieldnames=csv_columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return True


def save_config_file(device_folder, date_time, device_name, config):
    file_name = device_name + '_conf_' + date_time + CONF_SUFFIX
    output_file_path = device_folder + file_name
    save_data_to_file(output_file_path, config)


def save_cli_command(device_folder, date_time, device_name, cli_command, original_output):
    cli_command = translate_from_name(cli_command)
    file_name = device_name + '_' + cli_command + '_' + date_time + TEXT_SUFFIX
    output_file_path = device_folder + file_name
    save_data_to_file(output_file_path, original_output)


def save_gdr_data(device_folder, date_time, device_name, device_info, interfaces_info):
    if device_info:
        file_name = device_name + '_dev_' + date_time + JSON_SUFFIX
        output_file_path = device_folder + file_name
        save_data_to_file(output_file_path, json.dumps(
            device_info, indent=4, cls=DateTimeEncoder))
    if interfaces_info:
        file_name = device_name + '_intf_' + date_time + JSON_SUFFIX
        output_file_path = device_folder + file_name
        save_data_to_file(output_file_path, json.dumps(
            interfaces_info, indent=4, cls=DateTimeEncoder))


def retrieve_command(device_name, cli_command) -> str:
    if not device_name or not cli_command:
        return ''
    rp = QueryDataProtocol()
    rp.devName = device_name
    rp.command = cli_command
    rp.commandType = 9  # cli command
    rp.datasource.type = 1  # live resource
    res = devicedata.Query(rp)
    if not res:
        return ''
    content = ''
    status = res.get('result', 'fail')
    if status == 'fail':
        content = res.get('error', '')
        if not content:
            content = res.get('livelog', '')
    else:
        content = res.get('content', '')
    return content


def upload_result(zip_file_content, timeStamp) -> bool:
    timeStamp = '_%s' % timeStamp
    report_name = FDS_NAME + timeStamp + ZIP_SUFFIX
    export_path = FDS_NAME
    certification.export_certification_report(
        report_name, zip_file_content, export_path)
    return True


def save_output(results):
    if not results:
        return False

    feature_results = results[0]
    device_datas = results[1]
    device_feature_commands = results[2]
    device_config = results[3]
    if not feature_results and not device_datas and not device_feature_commands and not device_config:
        return False

    stamp = int(time.time())
    date_time = time.strftime('%Y%m%d', time.localtime(stamp))
    root_folder = NB_Install_Folder + '\\' + FDS_NAME
    if not os.path.exists(root_folder):
        os.mkdir(root_folder)

    save_summary_file(root_folder, feature_results)

    save_input_file(root_folder, device_feature_commands, device_datas)

    device_folder = root_folder + '\\' + DATA_FOLDER
    if not os.path.exists(device_folder):
        os.mkdir(device_folder)
    device_folder = device_folder + '\\'

    for device_name, feature_cmds in device_feature_commands.items():
        device_file_name = translate_from_name(device_name)
        for featureName, cmds in feature_cmds.items():
            for cli_command in cmds:
                if not cli_command:
                    continue
                original_output = retrieve_command(device_name, cli_command)
                save_cli_command(device_folder, date_time,
                                 device_file_name, cli_command, original_output)

        config_content = device_config.get(device_name)
        save_config_file(device_folder, date_time,
                         device_file_name, config_content)

        infos = device_datas[device_name]
        device_info = infos.get('devInfo')
        interfaces_info = infos.get('intfsInfo')
        save_gdr_data(device_folder, date_time, device_file_name,
                      device_info, interfaces_info)

    zip_file_path = root_folder + ZIP_SUFFIX
    with ZipFile(zip_file_path, 'w') as zipObj:
        for folderName, subfolders, filenames in os.walk(root_folder):
            for filename in filenames:
                filePath = os.path.join(folderName, filename)
                fileInnerPath = filePath[len(root_folder) + 1:]
                zipObj.write(filePath, fileInnerPath)
    shutil.rmtree(root_folder)

    zip_file_content = get_data_from_file(zip_file_path)
    upload_result(zip_file_content, date_time)
    os.remove(zip_file_path)
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

    return save_output(results)
