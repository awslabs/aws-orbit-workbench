import boto3
import json
import sys
from typing import Any, Dict, List, Optional, cast



ssm_client = boto3.client(service_name="ssm")
cognito_admin_client = boto3.client(service_name='cognito-idp')

def get_teams_from_pool(userpoolid):
    groups = cognito_admin_client.list_groups(UserPoolId=userpoolid)
    valid_groups = []
    for g in groups['Groups']:
        valid_groups.append(g['GroupName'])
    return valid_groups

def list_ssm():
    res = ssm_client.get_parameters_by_path(Path='/orbit/r131b',Recursive=True)
    print(res)

def get_orbit_userpoolid(env_name):
    ssm_name = f"/orbit/{env_name}/context"
    ssm_val = ssm_client.get_parameter(Name=ssm_name)
    p = json.loads(ssm_val['Parameter']['Value'])
    return p['UserPoolId']

def add_user(userpoolid, username, email, pwd):
    response = cognito_admin_client.admin_create_user(
        UserPoolId = userpoolid,
        Username = username, 
        UserAttributes = [
        {"Name": "email_verified", "Value": "true" },
        {"Name": "email", "Value": email }
        ],
        DesiredDeliveryMediums = ['EMAIL'],
        TemporaryPassword = pwd
    )

def check_for_user(userpoolid, username)-> bool:
    response = cognito_admin_client.list_users(
        UserPoolId=userpoolid    
    ) 
    for user in response['Users']:
        if username == user['Username']:
            return True
    
    return False

def add_group_to_user(userpoolid,username,group,pwd):
    cognito_admin_client.admin_add_user_to_group(UserPoolId=userpoolid,
                                                    Username=username,
                                                    GroupName=group)

def setup_new_user(env_name, username,email,pwd):
    user_pool_id = get_orbit_userpoolid(env_name)
    teams = get_teams_from_pool(userpoolid=user_pool_id)
    if not check_for_user(user_pool_id, username):
        add_user(userpoolid=user_pool_id,
                                username = username,
                                email = email,
                                pwd=pwd
                            )
    for t in teams:
        add_group_to_user(userpoolid=user_pool_id,
                            username=username,
                            group=t,
                            pwd=pwd)


if __name__ == "__NOT_main__":
    print('For testing')

if __name__ == "__main__":
    len(sys.argv)
    if len(sys.argv) < 2:
        print("pass in your params as json like this {\"env_name\":\"r131a\", \"username\":\"orbit\",\"email\":\"someaddress@amazon.com\",\"pwd\":\"OrbitPwd1!\"}")
        print("OR")
        print("pass in your params as elements like this ---  env_name username email pwd")
        print("NOTE: order is important!!!")
    elif len(sys.argv) == 2:
        params = sys.argv[1]
        p = json.loads(params)
        u=p['username']
        e=p['env_name']
        print(f"Setting up new user in Orbit with username {u} in env {e}")
        setup_new_user(env_name=e,
                       username=u,
                       email=p['email'],
                       pwd=p['pwd']
        )
    elif len(sys.argv) == 5:
        setup_new_user(env_name=sys.argv[1],
                       username=sys.argv[2],
                       email=sys.argv[3],
                       pwd=sys.argv[4]
        )