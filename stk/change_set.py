from __future__ import annotations
from typing import List

from botocore.exceptions import WaiterError
from rich.console import Console
from rich.table import Table
from rich import box

from .stack_waiter import StackWaiter
from .template import RenderedTemplate
from .basic_stack import BasicStack


class ChangeSet:
    ROW_STYLES = {"Add": "green", "Remove": "red", "Modify": "yellow"}

    def __init__(self, stack: BasicStack, name: str):
        self.stack = stack
        self.name = name
        self.cfn = stack.cfn

    def create(self, template: RenderedTemplate, change_set_type: str):
        stack = self.stack
        template_url = stack.bucket.upload(template).as_http()
        self.cfn.create_change_set(
            StackName=stack.name,
            TemplateURL=template_url,
            ChangeSetName=self.name,
            ChangeSetType=change_set_type,
            Capabilities=template.iam_capabilities(),
        )

        try:
            self.wait("change_set_create_complete")
        except WaiterError as ex:
            pass

        return self

    def execute(self):
        self.cfn.execute_change_set(**self._descriptor())
        return self

    def delete(self):
        res = self.cfn.delete_change_set(**self._descriptor())
        return res["ResponseMetadata"]["HTTPStatusCode"] == 200

    def available(self, change_set=None) -> bool:
        if not change_set:
            change_set = self.cfn.describe_change_set(**self._descriptor())

        if change_set and "ExecutionStatus" in change_set:
            return change_set["ExecutionStatus"] == "AVAILABLE"

    def wait(self, waiter_name: str):
        StackWaiter(self.stack).wait_for_change_set(waiter_name, self)

    def summary(self) -> Table:
        change_set = self.cfn.describe_change_set(**self._descriptor())

        if self.available(change_set):
            detail = Table("Resource", "Type", "Action", "Details", box=box.SIMPLE)
            for chg in self.changes(change_set):
                row_style = self.ROW_STYLES.get(chg["Action"], "")
                detail.add_row(chg["LogicalResourceId"], chg["ResourceType"], chg["Action"], self.humanize_change_detail(chg.get("Details")), style=row_style)
            return detail

        summary = Table("Property", "Value", title="Change Set", box=box.SIMPLE)
        summary.add_row("Stack Name", change_set.get("StackName", "-"))
        summary.add_row("Stack ID", change_set.get("StackId", "-"))
        summary.add_row("Execution Status", change_set.get("ExecutionStatus", "-"))
        summary.add_row("Status", change_set.get("Status", "-"))
        summary.add_row("Reason", change_set.get("StatusReason", "-"))

        return summary

    def changes(self, cs=None):
        if not cs:
            id = self._descriptor()
            cs = self.cfn.describe_change_set(**self._descriptor())

        if "Changes" in cs:
            for change in cs["Changes"]:
                if "ResourceChange" in change:
                    rs = change["ResourceChange"]
                    yield (rs)

    def resources(self) -> dict:
        """
        Returns list of resources and types in change set. This is used to pre-populate status
        table when executing the change set.

        :returns: dict<LogicalResourceId,ResourceType>
        """
        ret_val = {}
        for rc in self.changes():
            ret_val[rc["LogicalResourceId"]] = rc["ResourceType"]
        return ret_val

    def humanize_change_detail(self, change_details: List[dict]) -> str:
        ret_val = []
        for change in change_details or []:
            try:
                target = change["Target"]
                target_name = "[b]%s.%s[/b]" % (target["Attribute"], target["Name"])
                if change["ChangeSource"] == "DirectModification":
                    ret_val.append(f"{target_name} changed")
                elif change["ChangeSource"] == "ResourceAttribute":
                    ret_val.append(f"{target_name} changed by {change['CausingEntity']}")
                else:
                    ret_val.append(str(change))
            except Exception as ex:
                print(ex)
                ret_val.append(str(change))
        return "\n".join(ret_val)

    def _descriptor(self) -> dict:
        id = {"StackName": self.stack.name, "ChangeSetName": self.name}
        if not hasattr(self, "id"):
            change_set = self.cfn.describe_change_set(**id)
            self.id = change_set["ChangeSetId"]

        return {"ChangeSetName": self.id}
