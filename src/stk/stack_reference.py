from .aws_config import AwsSettings
from .basic_stack import BasicStack

class StackReference(BasicStack):
    def __init__(self, aws: AwsSettings, name: str):
        # self._status = None
        super().__init__(aws, name)

    def status(self):
        if not hasattr(self, "_status"):
            self._status = super().status()
        return self._status

    def describe_stack(self):
        """
        For references, cache the describe_stack - we're not expecting
        it to change.
        """
        if not hasattr(self, "_describe_stack_result"):
            self._describe_stack_result = super().describe_stack()
        return self._describe_stack_result

    def description(self):
        """
        return a description of the stack (name and region) to help user find
        it in AWS console
        """
        try:
            status = self.status()
        except Exception:
            status = "?"

        return f"\[cfn_name={self.name},region={self.aws.region},status={status}\]"
