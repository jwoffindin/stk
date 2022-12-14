from copy import copy
from dataclasses import dataclass
from typing import Any, Dict, Union

from . import log
from .stack_reference import StackReference
from .interpolated_dict import InterpolatedDict


@dataclass
class StackRefOpts:
    """
    Data class representing a stack reference. User defines config like:

    refs:
        foo_bar:
        some_other_stack:
            stack_name: "override_stack_name"
            region: ap-southeast-3

    """
    stack_name: str
    region: str
    optional: bool

class OptionalStackReference:
    def __init__(self, ref_name: str, stack: StackReference, optional: bool):
        self.stack = stack
        self.ref_name = ref_name
        self.optional = optional

    def __getitem__(self, name: str) -> Union[str, None]:
        if self.exists():
            return self.stack.output(name)
        elif self.optional:
            log.debug("returning None for %s as stack %s does not exist", name, self.stack.description())
            return None
        else:
            raise StackReferenceException(f"referenced stack {self.ref_name} {self.stack.description()} doesn't exist")

    def __getattr__(self, name: str):
        return self[name]

    def status(self):
        """Delegated to stack"""
        return self.stack.status()

    def exists(self):
        """Delegated to stack"""
        return self.stack.exists()

    def description(self):
        """Delegated to stack"""
        return self.stack.description()

    def outputs(self):
        """Delegated to stack"""
        return self.stack.outputs()

class StackReferenceException(Exception):
    pass

class StackRefs:
    DEFAULTS = {"stack_name": "{{ environment }}-{{ name }}", "optional": False}

    def __init__(self, stack_refs: Dict[str, Dict[str, str]], config: Any):
        self._stacks: Union[Dict[str, OptionalStackReference], None] = None
        self.config = config
        self.refs = stack_refs
        log.debug("defined refs: %s", self.refs)

    def __contains__(self, name: str) -> bool:
        return name in self.stacks()

    def __getitem__(self, name: str) -> OptionalStackReference:
        return self.stack(name)

    def __getattr__(self, name: str):
        if name in self.stacks().keys():
            return self.stacks()[name]
        raise StackReferenceException(f"{name} is not a known stack ref - only know about {', '.join(self.refs.keys())}")

    def exists(self, name: str):
        return self[name].exists()

    def output(self, name: str, output_name: str) -> Union[str, None]:
        """
        Return the output from stack or `None` if stack does not exist and
        stack is optional, otherwise will raise an exception.
        """
        log.info("getting output %s from stack %s", output_name, name)
        stack = self.stack(name)
        return stack.output(output_name)

    def stack(self, name: str) -> OptionalStackReference:
        """
        Returns stack object, or None if stack is optional but is not found
        """
        if name not in self.refs:
            stack_names = sorted(self.refs.keys())
            raise Exception(f"Attempt to access stack {name}, but it's not defined in config.refs - only {', '.join(stack_names)} are defined")

        ref = self.refs[name]
        log.debug("looking up stack %s, ref=%s", name, ref)

        stack = self.stacks()[name]

        log.debug("stack=%s, status=%s, exists=%s", stack, stack.status(), stack.exists())
        if stack.exists():
            log.debug("found stack")
            return stack

        log.debug("stack does not exist, ref=%s", ref)
        if ref['optional']:
            log.debug("stack doesn't exist, but it's optional")
            return stack

        raise Exception(f"Referenced stack {name}, does not exist (stack name={ref['stack_name']}, region={ref.get('region', stack.aws.region)})")

    RESERVED_KEYS = ["environment"]
    def stacks(self) -> Dict[str, OptionalStackReference]:
        if self._stacks is None:
            log.debug("START - building list of stack references")
            # _stacks is dict of {name => OptionalStackReference() for each named stack. This includes
            # stacks that don't exist.
            self._stacks = {}
            for name, cfg in self.refs.items():
                log.debug("processing name=%s: config=%s", name, cfg)
                if name in self.RESERVED_KEYS:
                    log.debug("skipping %s, reserved key", name)
                    continue

                if not cfg:
                    cfg = {}

                if not issubclass(type(cfg), dict):
                    print(f"{name} is not a valid stack reference definition (from {self.refs})")
                    exit(-1)

                # Try building dict of options. This can fail if interpolating incorrect variable or
                #try:
                final_opts = InterpolatedDict({"region": self.config.aws.region, **self.DEFAULTS, **cfg}, {"environment": self.config.environment, "name": name.replace("_", "-"), "region": self.config.aws.region})
                log.debug("Have built final_opts=%s", final_opts)
                #except Exception as ex:
                #    print(f"Unable to process settings for stack reference {name} -> {cfg} (from {self.refs})", ex)
                #    exit(-1)

                try:
                    log.info("final ops: stack reference %s: %s", name, final_opts)
                    opts = StackRefOpts(**final_opts)
                except Exception as ex:
                    log.exception("Invalid configuration for stack.refs '%s' %s: %s", name, self.refs, ex, exc_info=ex)
                    raise

                aws = self.config.aws
                if opts.region != aws.region:
                    log.debug("stack reference is in a different region")
                    aws = copy(aws)
                    aws.region = opts.region

                log.debug("Storing %s as optional stack reference", name)
                stack_ref = OptionalStackReference(name, StackReference(aws=aws, name=opts.stack_name), optional=opts.optional)

                self._stacks[name] = stack_ref
                if stack_ref.exists():
                    try:
                        log.info("stack %s %s has the following outputs: %s", name, stack_ref.description(), stack_ref.outputs())
                    except Exception as ex:
                        log.exception("unable to get outputs for stack %s", name)
                        raise ex
                else:
                    log.info("stack %s %s doesn't exist", name, stack_ref.description())
            log.debug("DONE - building list of stack references")

        return self._stacks
