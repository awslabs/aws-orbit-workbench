<!--
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
-->
# Lake Creator Notebooks

## Description
* Lake Creator Notebooks providing examples of processing raw data and transforming it into high quality common data assets
* The notebooks in this folder will perform ETL to load data from landing zone into a bucket that can be shared with other teams
* Lake Creator is the only role that can write into the Lake buckets, 
  while other teams can read from the Lake, and write into their own buckets.

## Notebooks

#### Example-1-Build-Lake.ipynb: 

-  This notebook orchestrates the Lake loading by running the first notebook below in parallel
     for each file, and then it executes (again in parallel) the table creation.
   
#### Example-2-Extract-Files.ipynb

-  A notebook that extract Zip files using Shell and AWS CLI Commands
   
#### Example-3-Load-Database-Athena.ipynb  

-  A notebook that reads the CSV files using Athena external tables and then create Parquet Glue tables 

    