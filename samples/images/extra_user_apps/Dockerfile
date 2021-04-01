#FROM ${jupyter_user_base}
FROM 495869084367.dkr.ecr.us-west-2.amazonaws.com/orbit-test-env-public-jupyter-user:latest
######################################
# Apps installation
######################################
RUN mkdir -p /home/jovyan/.orbit
COPY apps /home/jovyan/.orbit/apps
RUN echo "TEST"
RUN ls -R /home/jovyan/.orbit/apps
RUN chmod -R a+xr /home/jovyan/apps/*.sh
RUN /home/jovyan/apps/install-all.sh
RUN chown -R jovyan /home/jovyan/.local/share/
