from datetime import datetime, timezone

from botocore.exceptions import ClientError

from rich.table import Table
from rich.live import Live
from rich.console import Console


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
                self.timestamp = event["Timestamp"].astimezone()

        def last_seen(self):
            return "%ds ago" % (datetime.now().astimezone() - self.timestamp).seconds if self.timestamp else "-"

    def wait_for_change_set(self, waiter_name, change_set_name):
        waiter = self.cfn.get_waiter(waiter_name)
        with Console().status("Waiting for change set...") as status:

            def waiter_callback(response):
                if "Stacks" in response:
                    s = response["Stacks"][0]
                    status.update(s["StackStatus"])
                elif "Error" in response:
                    status.update(response["Error"]["Message"])

            waiter = self.wrap_waiter(waiter, waiter_callback)
            waiter.wait(WaiterConfig={"Delay": 5}, ChangeSetName=change_set_name)

    def wait_for_stack(self, waiter_name, change_set, **kwargs):
        waiter = self.cfn.get_waiter(waiter_name)

        # If we are applying a change set, we know what resources will be changed, so can
        # pre-populate the table with resources.
        self.resources = self.resources_in_changeset(change_set) if change_set else {}

        # Wait with a live-updated table showing resources to be changed, and their current
        # state.
        if self.resources:
            with Live(self.refresh_table(), refresh_per_second=1, transient=False) as live:

                def waiter_callback(response):
                    live.update(self.refresh_table())
                    if "Stacks" in response:
                        pass
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

    def resources_in_changeset(self, cs):
        stack_name = self.stack.name
        resources = {
            stack_name: StackWaiter.ResourceEvent(
                logical_id=stack_name,
                type="AWS::CloudFormation::Stack",
            )
        }

        for change in cs["Changes"]:
            if "ResourceChange" in change:
                rc = change["ResourceChange"]
                resources[rc["LogicalResourceId"]] = StackWaiter.ResourceEvent(
                    logical_id=rc["LogicalResourceId"],
                    type=rc["ResourceType"],
                )
        return resources
