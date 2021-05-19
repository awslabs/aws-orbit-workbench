#!/usr/bin/env python3

import json
import os
import fnmatch


aws_dir = '/home/jovyan/.aws/'
cache_dir = aws_dir + 'cli/cache'
creds = aws_dir + 'credentials'
fN = None

os.system ("aws s3 ls")

for file in os.listdir(cache_dir):
    if fnmatch.fnmatch(file, '*.json'):
        fN = file
        break

with open(cache_dir + "/" + fN) as f:
    data = json.load(f)


with open(creds, 'w') as out:
    l1 = '[default]'
    l2 = 'aws_access_key_id = '+ data['Credentials']['AccessKeyId']
    l3 = 'aws_secret_access_key = '+ data['Credentials']['SecretAccessKey']
    l4 = 'aws_session_token = '+ data['Credentials']['SessionToken']
    out.write('{}\n{}\n{}\n{}\n'.format(l1, l2, l3, l4))
