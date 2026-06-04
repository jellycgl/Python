import json
import pythonlib

from netbrain.sysapi import datamodel
from netbrain.sysapi import pluginfw


class ApiServer:
    """
    Wrapper class for NetBrain External API Server.
    Responsible for retrieving API Server metadata and
    forwarding requests to the corresponding Front Server.
    """

    def __init__(self, domain_name: str, api_server_name: str):
        """
        Initialize ApiServer instance.

        :param domain_name: NetBrain domain database name
        :param api_server_name: Configured API Server name
        """
        if not api_server_name:
            raise ValueError("api_server_name must be provided")

        self.domain_name = domain_name
        self.api_server_name = api_server_name

        api_server = self._get_api_server()

        if not api_server:
            raise RuntimeError(
                f"API Server '{self.api_server_name}' not found "
                f"in domain '{self.domain_name}'"
            )

        pluginfw.AddLog(
            f"API Server retrieved: {json.dumps(api_server)}", pluginfw.WARNING
        )

        self.id = api_server["_id"]
        self.api_adapter_id = api_server["serverTypeId"]
        self.front_server_id = api_server["frontServerAndGroupId"]

    def _get_api_server(self) -> dict:
        """
        Retrieve API Server metadata from database.

        :return: API Server document or empty dict if not found
        """
        query = {
            "name": self.api_server_name,
            "$project": {
                "_id": 1,
                "serverTypeId": 1,
                "frontServerAndGroupId": 1,
            },
        }

        api_servers = datamodel.QueryDataFromDB(
            self.domain_name,
            "ExternalAPIServer",
            query,
        )

        if api_servers:
            return api_servers[0]

        return {}

    def forward_request_to_fs(
        self,
        func_name: str,
        api_params: dict | None = None,
    ) -> dict:
        """
        Forward request to Front Server via API Adapter.

        :param func_name: Adapter function name
        :param api_params: Parameters passed to adapter
        :return: API response dict
        """
        if api_params is None:
            api_params = {}

        tech_param = {
            "module_name": self.api_adapter_id,
            "func_name": func_name,
            "is_call_script": True,
            "domain_db_name": self.domain_name,
            "apiServerId": self.id,
            "apID": self.front_server_id,
            "api_params": api_params,
        }

        tech_param["func_args"] = json.dumps(tech_param)

        pluginfw.AddLog(
            f"Function [{func_name}] requested - {api_params}", pluginfw.INFO
        )

        try:
            response = pythonlib.get_api_response(
                json.dumps(tech_param)
            )
        except Exception as exc:
            pluginfw.AddLog(
                f"Function [{func_name}] execution failed - {exc}",
                pluginfw.ERROR,
            )
            return {}

        pluginfw.AddLog(
            f"Function [{func_name}] returned - {response}", pluginfw.INFO
        )

        if (
            isinstance(response, dict)
            and response.get("httpStatusCode") != 200
        ):
            pluginfw.AddLog(
                f"Function [{func_name}] returned non-200 status: "
                f"{response.get('httpStatusCode')}",
                pluginfw.WARNING,
            )
            return {}

        return response
