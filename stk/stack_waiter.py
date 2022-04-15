from datetime import datetime, timezone

from botocore.exceptions import ClientError

from rich.table import Table
from rich.live import Live


class StackWaiter:
    def __init__(self, stack):
        self.stack = stack
        self.cfn = stack.cfn
        self.seen_events = set()
        self.start_time = datetime.now(timezone.utc)

    class ResourceEvent:
        def __init__(self, e):
            self.event_id = e["EventId"]
            self.logical_id = e["LogicalResourceId"]
            self.type = e["ResourceType"]
            self.status = e["ResourceStatus"]
            self.timestamp = e["Timestamp"].astimezone()

        def last_seen(self):
            return "%ds ago" % (datetime.now().astimezone() - self.timestamp).seconds if self.timestamp else "-"

    def wait(self, waiter_name, resources, **kwargs):
        waiter = self.cfn.get_waiter(waiter_name)
        self.resources = resources

        with Live(self.refresh_table(), refresh_per_second=1, transient=False) as live:

            def waiter_callback(response):
                live.update(self.refresh_table())
                if "Stacks" in response:
                    s = response["Stacks"][0]
                    print(s["StackStatus"])
                elif "Error" in response:
                    print(response["Error"]["Message"])

            waiter = self.wrap_waiter(waiter, waiter_callback)
            waiter.wait(WaiterConfig={"Delay": 5}, **kwargs)

    def refresh_table(self):
        self.process_new_events()
        table = Table("Logical Resource", "Type", "Status", "Last Updated")
        for _, resource in sorted(self.resources.items()):
            table.add_row(resource.logical_id, resource.type, resource.status, resource.last_seen())
        return table

    def process_new_events(self):
        try:
            paginator = self.cfn.get_paginator("describe_stack_events")
            for events in paginator.paginate(StackName=self.stack.name):
                for e in events["StackEvents"]:
                    resource = self.ResourceEvent(e)
                    if resource.timestamp >= self.start_time and resource.event_id not in self.seen_events:
                        self.resources[resource.logical_id] = resource
                        self.seen_events.add(resource.event_id)
        except ClientError as e:
            error_received = e.response["Error"]
            if (error_received["Code"] == "ValidationError") and ("does not exist" in error_received["Message"]):
                return None
            raise (e)

    def wrap_waiter(self, waiter, callback):
        orig_func = waiter._operation_method

        def wrapper(**kwargs):
            response = orig_func(**kwargs)
            callback(response)
            return response

        waiter._operation_method = wrapper

        return waiter
