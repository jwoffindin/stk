from datetime import datetime, timezone


class StackWaiter:
    def __init__(self, stack):
        self.stack = stack
        self.cfn = stack.cfn
        self.seen_events = set()
        self.start_time = datetime.now(timezone.utc)

    def wrap_waiter(self, waiter, callback):
        orig_func = waiter._operation_method

        def wrapper(**kwargs):
            response = orig_func(**kwargs)
            callback(response)
            return response

        waiter._operation_method = wrapper

        return waiter

    def new_events(self):
        new_events = []
        paginator = self.cfn.get_paginator("describe_stack_events")
        for events in paginator.paginate(StackName=self.stack.name):
            for e in events["StackEvents"]:
                if e["Timestamp"] >= self.start_time and e["EventId"] not in self.seen_events:
                    self.seen_events.add(e["EventId"])
                    new_events.append(e)
        return sorted(new_events, key=lambda e: e["Timestamp"])

    def waiter_callback(self, response):
        if "Stacks" in response:
            s = response["Stacks"][0]
            for event in self.new_events():
                print(event)
            print(s["StackStatus"])
        elif "Error" in response:
            print(response["Error"]["Message"])

    def wait(self, waiter_name, **kwargs):
        waiter = self.cfn.get_waiter(waiter_name)

        waiter = self.wrap_waiter(waiter, self.waiter_callback)
        waiter.wait(WaiterConfig={"Delay": 5}, **kwargs)
