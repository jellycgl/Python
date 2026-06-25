import json
import time
import pythonutil
from netbrain.techspec.common import httputil as requests


# Bump this whenever the adapter changes so a Test Connection can confirm which
# version the Front Server is actually running (it caches the module in memory;
# editing the file on disk is NOT enough -- the worker must reload it).
_ADAPTER_VERSION = "ensure_token-v2"


# =========================================================
# Global Token Cache (OAuth only)
# =========================================================
_cached_access_token = None
_cached_refresh_token = None
_cached_endpoint = None
_cached_username = None
_cached_password = None
_token_expiry = 0  # epoch seconds; 0 means unknown / expired

# Refresh the token this many seconds BEFORE it actually expires,
# so a long-running request never sends an about-to-die token.
_TOKEN_EXPIRY_SKEW = 60


# =========================================================
# Extract Parameters
# =========================================================
def extract_param(param):

    if isinstance(param, str):
        param = json.loads(param)

    username = ''
    password = ''
    endpoint = ''
    auth_id = ''
    api_server_id = ''
    api_params = {}
    serv_info = {}
    is_enable_auth = False

    if 'apiServerId' in param:
        api_server_id = param['apiServerId']
        serv_info = pythonutil.GetApiServerInfo(api_server_id)
        username = serv_info.get('username', '')
        password = serv_info.get('password', '')
        endpoint = serv_info.get('endpoint', '')
        is_enable_auth = serv_info.get('isEnableApiAuthenticator', False)
        auth_id = serv_info.get('authenticatorId', '')
        api_params = param.get('api_params', {})
    else:
        username = param.get('username', '')
        password = param.get('password', '')
        endpoint = param.get('endpoint', '')
        api_params = param.get('api_params', {})

    return endpoint, username, password, is_enable_auth, auth_id, api_params


# =========================================================
# OAuth Login
# =========================================================
def _oauth_login(endpoint, username, password):

    global _cached_access_token, _cached_refresh_token, _cached_endpoint
    global _cached_username, _cached_password, _token_expiry

    token_url = f"{endpoint}/oauth/token"

    token_body = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    response = requests.post(
        token_url,
        data=token_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=False,
    )

    if response.status_code != 200:
        raise Exception(f"OAuth login failed: {response.text}")

    token_json = response.json()

    _cached_access_token = token_json.get("access_token")
    _cached_refresh_token = token_json.get("refresh_token")
    _cached_endpoint = endpoint
    # Remember credentials so we can silently re-login when the
    # refresh token is also expired/invalid.
    _cached_username = username
    _cached_password = password
    _token_expiry = _compute_expiry(token_json)

    if not _cached_access_token:
        raise Exception("OAuth response missing access_token")


# =========================================================
# OAuth Refresh
# =========================================================
def _oauth_refresh():

    global _cached_access_token, _cached_refresh_token, _cached_endpoint
    global _token_expiry

    if not _cached_refresh_token or not _cached_endpoint:
        raise Exception("No refresh token available")

    token_url = f"{_cached_endpoint}/oauth/token"

    refresh_body = {
        "grant_type": "refresh_token",
        "refresh_token": _cached_refresh_token,
    }

    response = requests.post(
        token_url,
        data=refresh_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=False,
    )

    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.text}")

    token_json = response.json()

    _cached_access_token = token_json.get("access_token")
    # Some servers rotate the refresh token on every refresh; keep the new one.
    if token_json.get("refresh_token"):
        _cached_refresh_token = token_json.get("refresh_token")
    _token_expiry = _compute_expiry(token_json)

    if not _cached_access_token:
        raise Exception("Refresh did not return access_token")


# =========================================================
# Token Helpers
# =========================================================
def _compute_expiry(token_json):
    """Return the epoch second at which the access token should be
    considered expired, based on the OAuth `expires_in` field."""
    expires_in = token_json.get("expires_in")
    try:
        expires_in = int(expires_in)
    except (TypeError, ValueError):
        # Server didn't tell us; assume a conservative 5 minutes.
        expires_in = 300
    return time.time() + expires_in


def _ensure_token(endpoint, username, password):
    """Guarantee a valid (non-expired) access token before a request.

    - Different endpoint or no token  -> full password login.
    - Token expired / about to expire -> try refresh, fall back to login.
    """
    global _cached_access_token

    if _cached_access_token is None or _cached_endpoint != endpoint:
        _oauth_login(endpoint, username, password)
        return

    if time.time() < (_token_expiry - _TOKEN_EXPIRY_SKEW):
        return  # still valid

    # Expired or about to expire: refresh, and if that fails, re-login.
    try:
        _oauth_refresh()
    except Exception:
        _oauth_login(endpoint, username, password)


# =========================================================
# GET DATA
# =========================================================
def get_data(param):

    global _cached_access_token, _cached_endpoint

    endpoint, username, password, is_enable_auth, auth_id, api_params = extract_param(param)

    api_path = api_params.get("api_url", "")
    url_params = api_params.get("url_params", {})

    full_url = endpoint + api_path

    try:
        if is_enable_auth:

            response = requests.get(
                full_url,
                authenticatorId=auth_id,
                params=url_params,
                verify=False,
            )

            if response.status_code == 200:
                json_response = response.json()
                return json_response.get('result', json_response)

            return response.text
        else:
            # Proactively make sure we have a valid token (login / refresh
            # based on expires_in) before sending the request.
            _ensure_token(endpoint, username, password)

            headers = {
                "Authorization": f"Bearer {_cached_access_token}",
                "Accept": "application/json",
            }

            response = requests.get(
                full_url,
                headers=headers,
                params=url_params,
                verify=False,
            )

            # Safety net: if the server still rejects the token (401),
            # try a refresh, and if that fails do a full re-login,
            # then retry the request once.
            if response.status_code == 401:
                try:
                    _oauth_refresh()
                except Exception:
                    _oauth_login(endpoint, username, password)

                headers["Authorization"] = f"Bearer {_cached_access_token}"

                response = requests.get(
                    full_url,
                    headers=headers,
                    params=url_params,
                    verify=False,
                )

            if response.status_code == 200:
                json_response = response.json()
                return json_response.get('result', json_response)

            return response.text

    except Exception as e:
        return str(e)


# =========================================================
# TEST CONNECTION
# =========================================================
def _test(param):
    try:
        format_param = json.loads(param)
    except Exception:
        return json.dumps({
            "isFailed": True,
            "msg": "Invalid JSON format."
        })

    endpoint = format_param.get("endpoint", "")
    username = format_param.get("username", "")
    password = format_param.get("password", "")
    is_enable_auth = format_param.get("isEnableApiAuthenticator", False)
    auth_id = format_param.get("authenticatorId", "")
    if not endpoint:
        return json.dumps({
            "isFailed": True,
            "msg": "Missing endpoint."
        })

    try:
        if is_enable_auth:
            response = requests.get(
                endpoint,
                authenticatorId=auth_id,
                verify=False,
            )
            if response.status_code in (200, 401, 403):
                return json.dumps({
                    "isFailed": False,
                    "msg": f"Endpoint reachable via NetBrain Authenticator. "
                           f"[adapter: {_ADAPTER_VERSION}]"
                })

            return json.dumps({
                "isFailed": True,
                "msg": f"Unexpected response: {response.status_code}"
            })
        else:
            _oauth_login(endpoint, username, password)
            return json.dumps({
                "isFailed": False,
                "msg": f"OAuth authentication successful. "
                       f"[adapter: {_ADAPTER_VERSION}]"
            })
    except Exception as e:
        return json.dumps({
            "isFailed": True,
            "msg": str(e)
        })
