ARG BASE_IMAGE=1234567890.dkr.ecr.us-west-2.amazonaws.com/orbit/k8s-utilities:base
FROM $BASE_IMAGE as utilbase

RUN pip install boto3

RUN mkdir -p /opt/orbit/scripts
RUN mkdir -p /opt/orbit/data
RUN mkdir -p /opt/orbit/samples/manifests
RUN mkdir -p /opt/orbit/samples/notebooks
RUN mkdir -p /opt/orbit/cms/schema

COPY src/utility-data/*.sh /opt/orbit/scripts/
COPY src/utility-data/*.py /opt/orbit/scripts/

COPY cms/schema /opt/orbit/cms/schema

#=================   END utilbase  =================

FROM utilbase AS rawdata

# CMS Data
RUN wget https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_Beneficiary_Summary_File_Sample_1.zip \
 -P /opt/orbit/data/cms -q 
RUN wget http://downloads.cms.gov/files/DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.zip \ 
 -P /opt/orbit/data/cms -q
RUN wget http://downloads.cms.gov/files/DE1_0_2008_to_2010_Carrier_Claims_Sample_1B.zip \ 
 -P /opt/orbit/data/cms -q
RUN wget https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.zip \ 
 -P /opt/orbit/data/cms -q
RUN wget https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.zip \ 
 -P /opt/orbit/data/cms -q
RUN wget http://downloads.cms.gov/files/DE1_0_2008_to_2010_Prescription_Drug_Events_Sample_1.zip \ 
 -P /opt/orbit/data/cms -q
RUN wget https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2009_Beneficiary_Summary_File_Sample_1.zip \ 
 -P /opt/orbit/data/cms -q
RUN wget https://www.cms.gov/Research-Statistics-Data-and-Systems/Statistics-Trends-and-Reports/SynPUFs/Downloads/DE1_0_2010_Beneficiary_Summary_File_Sample_20.zip \ 
 -P /opt/orbit/data/cms -q


#=================   END rawdata  =================

FROM rawdata AS smdata

# Sagemaker Data
RUN wget https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data \
 -P /opt/orbit/data/sagemaker -q
RUN wget https://github.com/mnielsen/neural-networks-and-deep-learning/raw/master/data/mnist.pkl.gz \
 -P /opt/orbit/data/sagemaker -q


#=================   END smdata  =================  

FROM smdata AS notebooks

# Sample Manifests
COPY samples/manifests /opt/orbit/samples/manifests
COPY samples/notebooks /opt/orbit/samples/notebooks

RUN chmod -R a+xr /opt/orbit/

ENTRYPOINT ["bash"]

