from dataclasses import dataclass

import boto3


@dataclass
class AwsSettings:
    region: str
    cfn_bucket: str
    account_id: str = None
    profile: str = None

    def client(self, service):
        session = self._session()
        return session.client(service, region_name=self.region)

    def resource(self, service):
        session = self._session()
        return session.resource(service, region_name=self.region)

    def _session(self):
        session = boto3.Session(profile_name=self.profile)
        if not hasattr(self, "_checked_account"):
            sts = session.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            if self.account_id:
                if str(account_id) != str(self.account_id):
                    raise Exception(f"Incorrect AWS Account - exected {self.account_id}, but appear to be using {account_id} ")
            else:
                self._checked_account = True

            self.account_id = account_id

        return session
