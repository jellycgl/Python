import requests
from datetime import datetime


def get_github_file_history(file, auth=None):
    sha = file.get('sha')
    if not sha:
        return None
    try:
        history_url = f"https://github.com/api/v3/repos/netbrain/netbrain/commits?path={file['path']}"
        response = requests.get(history_url, auth=auth)
        response.raise_for_status()
        history = response.json()
        # print("\nCommit History:")
        # for commit in history:
        #     print("- Commit SHA:", commit.get('sha'))
        #     print("  Date:", commit.get('commit').get('committer').get('date'))
        #     print("  Message:", commit.get('commit').get('message'))
        return history
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Request Exception: {err}")
    except requests.exceptions.JSONDecodeError as json_err:
        print(f"JSON Decode Error: {json_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def is_created_in_2023(file, auth) -> bool:
    def is_in_2023(datetime_str):
        try:
            # Input Sample: datetime_str = "2023-01-14T10:30:00Z"
            parsed_datetime = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
            return parsed_datetime.year == 2023
        except ValueError:
            return False
    history = get_github_file_history(file, auth)
    firt_submit_time = min(commit.get('commit').get('committer').get('date') for commit in history)
    return is_in_2023(firt_submit_time)


def is_compliance(item, auth) -> bool:
    print('Commencement of compliance checks: %s' % str(item['path']))
    result = is_created_in_2023(item, auth)
    print('Completion of compliance checks: %s' % str(item['path']))
    return result


def get_github_sub_files(api_url, auth, src_type) -> list:
    files = list()
    try:
        response = requests.get(api_url, auth=auth)
        response.raise_for_status()
        contents = response.json()
        for item in contents:
            if item['type'] == 'dir':
                if src_type not in item['path']:
                    continue
                if src_type == 'driver' and item['name'] == 'python':
                    continue
                files.extend(get_github_sub_files(item['url'], auth, src_type))
            if item['type'] == 'file' and is_compliance(item, auth):
                files.append(item['path'])
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Request Exception: {err}")
    except requests.exceptions.JSONDecodeError as json_err:
        print(f"JSON Decode Error: {json_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return files


def query_github_files(username, password, repo_owner, repo_name, branch, src_type) -> list:
    api_url = f"https://github.com/api/v3/repos/{repo_owner}/{repo_name}/contents?ref={branch}"
    auth = (username, password)
    files = list()
    try:
        response = requests.get(api_url, auth=auth)
        response.raise_for_status()
        contents = response.json()
        for item in contents:
            if item['name'] in ['.gitignore', '.github', 'tool']:
                continue
            if item['type'] == 'file': # ignore root files
                continue
            files.extend(get_github_sub_files(item['url'], auth, src_type))
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Request Exception: {err}")
    except requests.exceptions.JSONDecodeError as json_err:
        print(f"JSON Decode Error: {json_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return files


if __name__ == '__main__':
    github_username = "github username"
    github_password = "github password"
    repo_owner = "repository owner"
    repo_name = "repository name"
    branch_name = "branch name"
    src_type = 'resource type'
    matched_files = query_github_files(github_username, github_password, repo_owner, repo_name, branch_name, src_type)
    print('Begin to print the matched files.')
    for matched_file in matched_files:
        print(matched_file)
    print('End to print the matched files.')

    file_path = 'matched_files.txt'
    with open(file_path, "w") as file:
        for matched_file in matched_files:
            file.write(matched_file + "\n")
