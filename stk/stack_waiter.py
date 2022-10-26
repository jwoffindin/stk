from datetime import datetime, timezone
from time import sleep
from botocore.exceptions import ClientError

from rich import box
from rich.table import Table
from rich.live import Live

from . import console

class StackWaiter:
    def __init__(self, stack):
        self.stack = stack
        self.cfn = stack.cfn
        self.seen_events = set()
        self.start_time = datetime.now(timezone.utc)

    class ResourceEvent:
        def __init__(self, *args, **kwargs):
            if kwargs:
                self.logical_id = kwargs["logical_id"]
                self.type = kwargs["type"]
                self.status = "-"
                self.timestamp = None
            elif len(args) > 0:
                assert len(args) == 1
                event = args[0]

                self.logical_id = event["LogicalResourceId"]
                self.type = event["ResourceType"]
                self.event_id = event["EventId"]
                self.status = event["ResourceStatus"]
                self.status_reason = event.get("ResourceStatusReason", None)
                self.timestamp = event["Timestamp"].astimezone()

        def last_seen(self):
            return "%ds ago" % (datetime.now().astimezone() - self.timestamp).seconds if self.timestamp else "-"

    def wait_for_change_set(self, waiter_name, change_set):
        waiter = self.cfn.get_waiter(waiter_name)

        def waiter_callback(response):
            if "Stacks" in response:
                s = response["Stacks"][0]
                # status.update(s["StackStatus"])
                print(s["StackStatus"])
            elif "Error" in response:
                # status.update(response["Error"]["Message"])
                print(response["Error"]["Message"])
                pass

        wrapped_waiter = self.wrap_waiter(waiter, waiter_callback)
        wrapped_waiter.wait(WaiterConfig={"Delay": 5, "MaxAttempts": 720}, StackName=self.stack.name, ChangeSetName=change_set.name)

    def wait_for_stack(self, waiter_name, resources: dict = None):
        """
        Wait for stack change to complete

        :param waiter_name: waiter name. Refer to <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html#waiters>
        :param resources: used to pre-populate the status update table. It is an (optional) dict with resource logical ID key and resource type as value.
        """
        waiter = self.cfn.get_waiter(waiter_name)

        # If we are applying a change set, we know what resources will be changed, so can
        # pre-populate the table with resources.
        self.resources = {self.stack.name: StackWaiter.ResourceEvent(logical_id=self.stack.name, type="AWS::CloudFormation::Stack")}

        if resources:
            for name, resource_type in resources.items():
                self.resources[name] = StackWaiter.ResourceEvent(logical_id=name, type=resource_type)

        # Wait with a live-updated table showing resources to be changed, and their current
        # state.
        try:
            with Live(self.refresh_table(), refresh_per_second=1, transient=False, console=console) as live:

                def waiter_callback(response):
                    # print(response)
                    live.update(self.refresh_table())
                    if "Stacks" in response:
                        # Update status of stack object (pseudo-resource)
                        stacks = response["Stacks"]
                        if len(stacks) > 0:
                            self.resources[self.stack.name].status = response["Stacks"][0]["StackStatus"]
                    elif "Error" in response:
                        console.log(response["Error"]["Message"])

                waiter = self.wrap_waiter(waiter, waiter_callback)
                waiter.wait(WaiterConfig={"Delay": 2, "MaxAttempts": 1800}, StackName=self.stack.name)

                # Perform a final update so the status table reflects end state
                live.update(self.refresh_table())
        except ClientError as e:
            error_received = e.response["Error"]
            if (error_received["Code"] == "ValidationError") and ("does not exist" in error_received["Message"]):
                return None
            raise (e)

    def refresh_table(self):
        self.process_new_events()
        table = Table("Logical Resource", "Type", "Status", "Last Updated", box=box.SIMPLE)
        for _, resource in sorted(self.resources.items()):
            table.add_row(resource.logical_id, resource.type, resource.status, resource.last_seen())
        return table

    def process_new_events(self):
        paginator = self.cfn.get_paginator("describe_stack_events")
        # Use stack identifier in case stack has been deleted+*
        for events in paginator.paginate(StackName=self.stack.name):
            for e in events["StackEvents"]:
                resource = self.ResourceEvent(e)
                if resource.timestamp >= self.start_time and resource.event_id not in self.seen_events:
                    self.resources[resource.logical_id] = resource
                    self.seen_events.add(resource.event_id)
                    if resource.status_reason:
                        console.log(resource.logical_id + ": " + resource.status_reason)

    def wrap_waiter(self, waiter, callback):
        orig_func = waiter._operation_method

        def wrapper(**kwargs):
            response = orig_func(**kwargs)
            callback(response)
            return response

        waiter._operation_method = wrapper

        return waiter
