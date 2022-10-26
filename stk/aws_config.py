from dataclasses import dataclass

import boto3
import logging

log = logging.getLogger("aws_config")


@dataclass
class AwsSettings:
    region: str
    cfn_bucket: str
    account_id: str = None
    profile: str = None
    role_arn: str = None
    web_identity_token: str = None

    def __post_init__(self):
        self.__session = None

    def client(self, service):
        session = self._session()
        log.info(f"client({service}), account_id={self.account_id}")
        return session.client(service, region_name=self.region)

    def resource(self, service):
        session = self._session()
        log.info(f"resource({service}), account_id={self.account_id}")
        return session.resource(service, region_name=self.region)

    def get_account_id(self):
        """
        Ensure account-id has been retrieved
        """
        self._session()
        return self.account_id

    def _session(self):
        if not self.__session:
            if self.role_arn and self.role_arn != "None":
                if self.web_identity_token and self.web_identity_token != "None":
                    short_token = self.web_identity_token[:8] + '\u2026' * (len(self.web_identity_token) > 8)
                    log.info(f"assuming role {self.role_arn} using web token {short_token}")
                    role = boto3.client('sts').assume_role_with_web_identity(RoleArn=self.role_arn, RoleSessionName='stk-web-session-role', WebIdentityToken=self.web_identity_token)
                else:
                    log.info(f"assuming role {self.role_arn}")
                    role = boto3.client('sts').assume_role(RoleArn=self.role_arn, RoleSessionName="stk-session-role")

                credentials = role['Credentials']
                session = boto3.Session(credentials['AccessKeyId'], credentials['SecretAccessKey'], credentials['SessionToken'])
            elif self.profile:
                session = boto3.Session(profile_name=str(self.profile))
            else:
                session = boto3.Session()

            if not hasattr(self, "_checked_account"):
                sts = session.client("sts")
                account_id = sts.get_caller_identity()["Account"]
                if self.account_id:
                    if str(account_id) != str(self.account_id):
                        raise Exception(f"Incorrect AWS Account - expected {self.account_id}, but appear to be using {account_id} ")

                self._checked_account = True
                self.account_id = account_id

            self.__session = session

        return self.__session
