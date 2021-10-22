FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/k8s-utilities:1.0.0

RUN pip install boto3

RUN mkdir -p /opt/orbit/scripts

COPY images/utility-data/src/utility-data/*.sh /opt/orbit/scripts/
COPY images/utility-data/src/utility-data/*.py /opt/orbit/scripts/

RUN mkdir -p /opt/orbit/data
RUN mkdir -p /opt/orbit/data/vscode
COPY images/utility-data/extensions/ /opt/orbit/data/vscode/extensions/

#RUN mkdir -p /opt/orbit/data/vscode/drivers
#RUN curl -fsSL https://marketplace.visualstudio.com/_apis/public/gallery/publishers/mtxr/vsextensions/sqltools-driver-pg/0.2.0/vspackage \
#-o /opt/orbit/data/vscode/drivers/mtxr.sqltools-driver-pg-0.2.0.gz
#RUN gunzip /opt/orbit/data/vscode/drivers/mtxr.sqltools-driver-pg-0.2.0.gz
#RUN mv /opt/orbit/data/vscode/drivers/mtxr.sqltools-driver-pg-0.2.0 /opt/orbit/data/vscode/drivers/mtxr.sqltools-driver-pg-0.2.0.vsix

# CMS Date
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


# CMS Schema Files
RUN mkdir -p /opt/orbit/cms/schema
COPY cli/aws_orbit/data/cms/schema /opt/orbit/cms/schema


# Sagemaker Data
RUN wget https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data \
 -P /opt/orbit/data/sagemaker -q
RUN wget https://github.com/mnielsen/neural-networks-and-deep-learning/raw/master/data/mnist.pkl.gz \
 -P /opt/orbit/data/sagemaker -q

# Sample Manifests
RUN mkdir -p /opt/orbit/samples/manifests
RUN mkdir -p /opt/orbit/samples/notebooks
COPY samples/manifests /opt/orbit/samples/manifests
COPY samples/notebooks /opt/orbit/samples/notebooks

RUN chmod -R a+xr /opt/orbit/

ENTRYPOINT ["bash"]
#ENTRYPOINT ["bash", "/opt/orbit/scripts/stage_all_data.sh"]
#CMD ["env-r17-jui"]
