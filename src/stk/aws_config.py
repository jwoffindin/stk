from dataclasses import dataclass

import boto3

from . import log


@dataclass
class AwsSettings:
    """Dataobject for AWS settings"""
    region: str
    cfn_bucket: str
    account_id: str = None
    profile: str = None
    role_arn: str = None
    web_identity_token: str = None
    aws_access_key: str = None
    aws_secret_key: str = None
    aws_session_token: str = None

    def __post_init__(self):
        self.__session = None
        self.__checked_account = False

    def client(self, service):
        """Returns boto client for given service"""
        session = self._session()
        log.info("client(%s), account_id=%s", service, self.account_id)
        return session.client(service, region_name=self.region)

    def resource(self, service):
        """Returns boto resource for given service"""
        session = self._session()
        log.info("resource(%s), account_id=%s", service, self.account_id)
        return session.resource(service, region_name=self.region)

    def get_account_id(self):
        """
        Ensure account-id has been retrieved
        """
        self._session()
        return self.account_id

    def _session(self):
        if not self.__session:
            session = self._session_from_access_key() or self._session_from_role() or self._session_from_profile() or self._session_from_env()

            if not self.__checked_account:
                sts = session.client("sts")
                account_id: str = sts.get_caller_identity()["Account"]
                if self.account_id:
                    if account_id != str(self.account_id):
                        raise ValueError(f"Incorrect AWS Account - expected {self.account_id}, but appear to be using {account_id} ")

                self.__checked_account = True
                self.account_id = account_id

            self.__session = session

        return self.__session

    def _session_from_role(self):
        """Assume role if explicitly set"""
        if self.role_arn and self.role_arn != "None":
            if self.web_identity_token and self.web_identity_token != "None":
                short_token = self.web_identity_token[:8] + '\u2026' * (len(self.web_identity_token) > 8)
                log.info("assuming role %s using web token %s", self.role_arn, short_token)
                role = boto3.client('sts').assume_role_with_web_identity(RoleArn=self.role_arn, RoleSessionName='stk-web-session-role', WebIdentityToken=self.web_identity_token)
            else:
                log.info("assuming role %s", self.role_arn)
                role = boto3.client('sts').assume_role(RoleArn=self.role_arn, RoleSessionName="stk-session-role")

            credentials = role['Credentials']
            return boto3.Session(credentials['AccessKeyId'], credentials['SecretAccessKey'], credentials['SessionToken'])

    def _session_from_profile(self):
        """Assume role if profile is set"""
        if self.profile:
            return boto3.Session(profile_name=str(self.profile))

    def _session_from_access_key(self):
        """Returns a boto3.Session if access keys are set"""
        access_keys = self._access_keys()
        if access_keys['aws_access_key_id'] and access_keys['aws_secret_access_key']:
            log.info("using sts access key")
            return boto3.Session(**access_keys)

    def _session_from_env(self):
        return boto3.Session()

    def _access_keys(self):
        """Returns a dict of access keys for use with boto3.Session, with 'None' (string) values set to None"""
        sts_auths = [self.aws_access_key, self.aws_secret_key, self.aws_session_token]

        result = {}
        for i, key in enumerate(["aws_access_key_id", "aws_secret_access_key", "aws_session_token"]):
            value = sts_auths[i]
            result[key] = value if value and value != "None" else None

        return result
