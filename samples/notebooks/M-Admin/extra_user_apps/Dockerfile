FROM ${jupyter_user_base}

USER root
######################################
# Apps installation
######################################
RUN mkdir -p /opt/orbit/extra_user_apps
COPY apps /opt/orbit/extra_user_apps/apps
RUN ls -R /opt/orbit/extra_user_apps/apps
RUN chmod -R a+xr /opt/orbit/extra_user_apps/apps/*.sh
RUN /opt/orbit/extra_user_apps/apps/install-all.sh
RUN chown -R jovyan /opt/orbit/extra_user_apps


USER $NB_UID

#RUN fix-permissions /opt/install

# apt-get may result in root-owned directories/files under $HOME
#RUN chown -R $NB_UID:$NB_GID $HOME
RUN fix-permissions /opt/orbit/extra_user_apps