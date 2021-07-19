ARG BASE_IMAGE=${jupyter_user_base}
FROM "$BASE_IMAGE"

######################################
# Apache Spark ARGs
######################################

ARG spark_version="3.0.3"
ARG hadoop_version="3.2"
ARG spark_checksum="22fc9a6042769d13c01f3b07f0dfae9d5d1e408244870833c5e703eb43669ce14c875f7cec47a07f1cf2ee3e65dfb1363977644bcd686481ccc0e0715d2760d5"
ARG openjdk_version="11"

ENV APACHE_SPARK_VERSION="${spark_version}" HADOOP_VERSION="${hadoop_version}"

######################################
# JRE
######################################

USER root

RUN apt-get -y update && \
    apt-get install --no-install-recommends -y \
    "openjdk-${openjdk_version}-jre-headless" \
    ca-certificates-java && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

######################################
# Apache Spark installation
######################################

WORKDIR /tmp
RUN wget -q $(wget -qO- https://www.apache.org/dyn/closer.lua/spark/spark-${APACHE_SPARK_VERSION}/spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz\?as_json | \
    python -c "import sys, json; content=json.load(sys.stdin); print(content['preferred']+content['path_info'])") && \
    echo "${spark_checksum} *spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz" | sha512sum -c - && \
    tar xzf "spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz" -C /usr/local --owner root --group root --no-same-owner && \
    rm "spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz"
WORKDIR /usr/local

######################################
# Apache Spark configuration
######################################

ENV SPARK_HOME=/usr/local/spark
ENV SPARK_OPTS="--driver-java-options=-Xms1024M --driver-java-options=-Xmx4096M --driver-java-options=-Dlog4j.logLevel=info" \
    PATH=$PATH:$SPARK_HOME/bin

RUN ln -s "spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}" spark && \
    # Add a link in the before_notebook hook in order to source automatically PYTHONPATH
    mkdir -p /usr/local/bin/before-notebook.d && \
    ln -s "${SPARK_HOME}/sbin/spark-config.sh" /usr/local/bin/before-notebook.d/spark-config.sh

# Fix Spark installation for Java 11 and Apache Arrow library
# see: https://github.com/apache/spark/pull/27356, https://spark.apache.org/docs/latest/#downloading
RUN cp -p "$SPARK_HOME/conf/spark-defaults.conf.template" "$SPARK_HOME/conf/spark-defaults.conf" && \
    echo 'spark.driver.extraJavaOptions="-Dio.netty.tryReflectionSetAccessible=true"' >> $SPARK_HOME/conf/spark-defaults.conf && \
    echo 'spark.executor.extraJavaOptions="-Dio.netty.tryReflectionSetAccessible=true"' >> $SPARK_HOME/conf/spark-defaults.conf

######################################
# Apache Spark R configuration
######################################

ENV R_LIBS_USER $SPARK_HOME/R/lib
RUN fix-permissions $R_LIBS_USER
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-dejavu \
    gfortran \
    gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

######################################
# Spylon Kernel
######################################

RUN chown -R jovyan /home/jovyan/.jupyter/

USER $NB_UID
WORKDIR $HOME

RUN conda install --quiet --yes 'spylon-kernel=0.4*' && \
    conda clean --all -f -y && \
    python -m spylon_kernel install --sys-prefix && \
    rm -rf "/home/${NB_USER}/.local" && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

######################################
# R packages
######################################

RUN conda install --quiet --yes \
    'r-base=4.0.3' \
    'r-ggplot2=3.3*' \
    'r-irkernel=1.1*' \
    'r-rcurl=1.98*' \
    'r-sparklyr=1.5*' \
    && \
    conda clean --all -f -y && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"
